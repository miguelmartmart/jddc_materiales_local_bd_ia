"""
snapshot_service.py — Captura datos reales de Firebird → SQLite simulador.

Conecta a la BD Firebird real, extrae los datos del último mes y los guarda
en la BD SQLite del simulador. Permite trabajar offline con datos reales.

Estrategia de captura:
  • Tablas de referencia (sin fecha): FAMILIA, ALMACEN, RECURSO, PROVEED,
    ARTICULO, CLIENTE  → se capturan todas (hasta MAX_ROWS_PER_TABLE)
  • Tablas con fecha (DOCCAB, CAJA, ESTALMACEN) → WHERE FECHA >= primer día
    del mes actual menos SNAPSHOT_MONTHS_BACK
  • DOCLIN → líneas de los DOCCAB capturados (via IN clause)

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from backend.modules.db_simulator.constants import (
    SimulatorConfig as Cfg,
    SimulatorLog,
    JDDCTableNames,
    JDDCDateColumns,
)
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.schema import TABLE_CREATION_ORDER

logger = logging.getLogger(__name__)


# ─── Fecha de corte ───────────────────────────────────────────────────────────

def _cutoff_date() -> str:
    """Devuelve la fecha de corte en formato 'YYYY-MM-DD'."""
    today = date.today()
    month = today.month - Cfg.SNAPSHOT_MONTHS_BACK
    year  = today.year
    if month <= 0:
        month += 12
        year  -= 1
    return f"{year:04d}-{month:02d}-01"


# ─── SnapshotService ─────────────────────────────────────────────────────────

class SnapshotService:
    """
    Toma un snapshot de la BD Firebird real y lo guarda en SQLite.
    Usa DirectFirebirdConn para no depender del driver simulado.
    """

    def __init__(self, db_params: Dict[str, Any]):
        self.db_params  = db_params
        self._fb_conn   = None
        self._sim_driver: Optional[SimulatedFirebirdDriver] = None

    # ─── Entrada pública ──────────────────────────────────────────────────────

    def run(self) -> Dict[str, int]:
        """
        Ejecuta el snapshot completo.
        Returns: dict tabla→filas_capturadas
        """
        cutoff = _cutoff_date()
        logger.info(
            f"{SimulatorLog.SNAPSHOT} Iniciando snapshot "
            f"(desde {cutoff}) — BD: {self.db_params.get('database', '?')}"
        )
        try:
            self._connect_firebird()
            self._sim_driver = SimulatedFirebirdDriver()
            self._sim_driver.connect()
            self._clear_sim_tables()

            counts: Dict[str, int] = {}

            # 1. Tablas de referencia (sin filtro de fecha)
            for table in JDDCTableNames.REFERENCE_TABLES:
                counts[table] = self._capture_reference_table(table)

            # 2. Tablas con fecha (filtro por cutoff)
            doccab_ids: List[int] = []
            for table in JDDCTableNames.DATE_TABLES:
                n, ids = self._capture_date_table(table, cutoff)
                counts[table] = n
                if table == JDDCTableNames.DOCCAB:
                    doccab_ids = ids

            # 3. DOCLIN enlazado a DOCCAB capturado
            counts[JDDCTableNames.DOCLIN] = self._capture_doclin(doccab_ids)

            self._sim_driver.conn.commit()
            total = sum(counts.values())
            logger.info(
                f"{SimulatorLog.SNAPSHOT} ✅ Snapshot completado: "
                f"{total} registros → {counts}"
            )
            return counts

        except Exception as e:
            logger.error(f"{SimulatorLog.SNAPSHOT} ❌ Error en snapshot: {e}", exc_info=True)
            raise
        finally:
            self._disconnect_firebird()
            if self._sim_driver:
                self._sim_driver.disconnect()

    # ─── Captura de tablas ────────────────────────────────────────────────────

    def _capture_reference_table(self, table: str) -> int:
        """Captura hasta MAX_ROWS_PER_TABLE filas sin filtro de fecha."""
        try:
            rows = self._fb_query(
                f"SELECT FIRST {Cfg.MAX_ROWS_PER_TABLE} * FROM {table}"
            )
            if rows:
                self._bulk_insert(table, rows)
            logger.info(f"{SimulatorLog.SNAPSHOT} {table}: {len(rows)} filas")
            return len(rows)
        except Exception as e:
            logger.warning(f"{SimulatorLog.SNAPSHOT} {table}: error capturando ({e})")
            return 0

    def _capture_date_table(
        self, table: str, cutoff: str
    ) -> Tuple[int, List[int]]:
        """
        Captura filas con FECHA >= cutoff.
        Devuelve (n_filas, lista_codigos) para DOCCAB.
        """
        date_col = JDDCDateColumns.MAP.get(table, "FECHA")
        limit    = Cfg.MAX_ROWS_PER_TABLE
        try:
            rows = self._fb_query(
                f"SELECT FIRST {limit} * FROM {table} "
                f"WHERE {date_col} >= CAST('{cutoff}' AS DATE) "
                f"ORDER BY {date_col} DESC"
            )
            if rows:
                self._bulk_insert(table, rows)
            ids = [r.get("CODIGO") for r in rows if r.get("CODIGO") is not None]
            logger.info(f"{SimulatorLog.SNAPSHOT} {table}: {len(rows)} filas (desde {cutoff})")
            return len(rows), ids
        except Exception as e:
            logger.warning(f"{SimulatorLog.SNAPSHOT} {table}: error capturando ({e})")
            return 0, []

    def _capture_doclin(self, doccab_ids: List[int]) -> int:
        """Captura líneas de documento para los DOCCAB capturados."""
        if not doccab_ids:
            return 0
        try:
            # SQLite tiene límite de 999 en IN clause; usamos lotes
            total = 0
            batch_size = 500
            for i in range(0, len(doccab_ids), batch_size):
                batch = doccab_ids[i:i + batch_size]
                placeholders = ",".join(str(x) for x in batch)
                rows = self._fb_query(
                    f"SELECT FIRST {Cfg.MAX_DOCLIN_ROWS} * FROM DOCLIN "
                    f"WHERE CODIGO IN ({placeholders})"
                )
                if rows:
                    self._bulk_insert("DOCLIN", rows)
                    total += len(rows)
            logger.info(f"{SimulatorLog.SNAPSHOT} DOCLIN: {total} filas")
            return total
        except Exception as e:
            logger.warning(f"{SimulatorLog.SNAPSHOT} DOCLIN: error capturando ({e})")
            return 0

    # ─── Inserción masiva en SQLite ───────────────────────────────────────────

    def _bulk_insert(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """
        Inserta filas en la tabla SQLite del simulador (INSERT OR IGNORE).
        Filtra automáticamente las columnas de Firebird que no existen en SQLite,
        garantizando compatibilidad cuando el esquema Firebird tiene más columnas.
        """
        if not rows:
            return
        sim_conn: sqlite3.Connection = self._sim_driver.conn

        # Columnas reales del esquema SQLite para esta tabla
        cur = sim_conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        known_cols: set = {r[1].upper() for r in cur.fetchall()}

        # Columnas del resultado de Firebird que existen en SQLite
        fb_cols = list(rows[0].keys())
        cols    = [c for c in fb_cols if c.upper() in known_cols]
        if not cols:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: ninguna columna Firebird coincide con SQLite"
            )
            return

        ph      = ",".join(["?"] * len(cols))
        col_str = ",".join(cols)
        sql     = f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({ph})"
        data    = []
        for row in rows:
            vals = []
            for col in cols:
                v = row[col]
                # Convertir date/datetime a string ISO
                if hasattr(v, "isoformat"):
                    v = v.isoformat()
                vals.append(v)
            data.append(tuple(vals))
        sim_conn.cursor().executemany(sql, data)

    def _clear_sim_tables(self) -> None:
        """Limpia todas las tablas del simulador en orden inverso FK."""
        sim_conn = self._sim_driver.conn
        for table in reversed(TABLE_CREATION_ORDER):
            try:
                sim_conn.cursor().execute(f"DELETE FROM {table}")
            except Exception:
                pass

    # ─── Conexión a Firebird ──────────────────────────────────────────────────

    def _connect_firebird(self) -> None:
        """Conecta directamente a Firebird usando firebirdsql."""
        import firebirdsql
        p = self.db_params
        user     = p.get("user") or p.get("username") or "SYSDBA"
        password = p.get("password", "masterkey")
        self._fb_conn = firebirdsql.connect(
            host=p.get("host", "localhost"),
            port=int(p.get("port", 3050)),
            database=p.get("database", ""),
            user=user,
            password=password,
            charset=p.get("charset", "latin1"),
        )
        logger.info(f"{SimulatorLog.SNAPSHOT} Conectado a Firebird: {p.get('host')}:{p.get('port')}")

    def _disconnect_firebird(self) -> None:
        if self._fb_conn:
            try:
                self._fb_conn.close()
            except Exception:
                pass
            self._fb_conn = None

    def _fb_query(self, sql: str) -> List[Dict[str, Any]]:
        """Ejecuta una query en Firebird y devuelve lista de dicts."""
        cur = self._fb_conn.cursor()
        cur.execute(sql)
        if not cur.description:
            return []
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        result = []
        for row in rows:
            d = {}
            for col, val in zip(cols, row):
                if isinstance(val, bytes):
                    try:
                        val = val.decode("latin1", errors="replace").strip()
                    except Exception:
                        val = str(val)
                d[col] = val
            result.append(d)
        return result
