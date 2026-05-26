"""
snapshot_service.py — Captura datos reales de Firebird → SQLite simulador.

Conecta a la BD Firebird real, extrae los datos y los guarda en la BD SQLite
del simulador. Permite trabajar offline con datos reales.

PRINCIPIO FUNDAMENTAL:
  El simulador debe ser un ESPEJO EXACTO de la BD real — mismas tablas, mismas
  columnas, mismos metadatos. El esquema SQLite se genera DINÁMICAMENTE desde el
  schema de Firebird al hacer build-snapshot, sin depender de schema.py manual.

Estrategia de captura:
  0. Sincronización de esquema: leer columnas/PKs de Firebird → crear/alterar
     tablas SQLite para que tengan EXACTAMENTE las mismas columnas.

  1. Tablas de referencia (sin fecha): FAMILIA, ALMACEN, RECURSO, PROVEED,
     ARTICULO, CLIENTE, PROYECTOS, PROYVAR, PRESUPROYE
     → hasta MAX_ROWS_PER_TABLE filas (MAX_PROYECTO_ROWS para tablas de proyectos)

  2. Tablas con fecha (DOCCAB, CAJA, ESTALMACEN)
     → WHERE FECHA >= primer día del mes actual menos SNAPSHOT_MONTHS_BACK

  3. DOCCAB por proyectos (sin límite de fecha)
     → WHERE CODPROYECTO IS NOT NULL — histórico completo de facturas y
       presupuestos de proyectos, esencial para el informe de ejecución.

  4. DOCLIN → líneas de todos los DOCCAB capturados (steps 2+3)

  5. DOCDESTINO → relaciones presupuesto→factura/pedido de los DOCCAB capturados

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.modules.db_simulator.constants import (
    SimulatorConfig as Cfg,
    SimulatorLog,
    JDDCTableNames,
    JDDCDateColumns,
)
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.schema import TABLE_CREATION_ORDER

logger = logging.getLogger(__name__)


# ─── Mapeo tipos Firebird → SQLite ────────────────────────────────────────────
# Ref: https://firebirdsql.org/refdocs/langrefupd25-rdb-fields.html
_FIREBIRD_TYPE_TO_SQLITE: Dict[int, str] = {
    7:   "INTEGER",   # SMALLINT
    8:   "INTEGER",   # INTEGER
    9:   "INTEGER",   # QUAD (obsoleto)
    10:  "REAL",      # FLOAT
    11:  "REAL",      # D_FLOAT (obsoleto)
    12:  "TEXT",      # DATE (solo fecha, guardada como ISO string)
    13:  "TEXT",      # TIME (guardada como HH:MM:SS string)
    14:  "TEXT",      # CHAR
    16:  "REAL",      # INT64 / BIGINT / DECIMAL / NUMERIC (con escala)
    23:  "INTEGER",   # BOOLEAN (Firebird 3+)
    27:  "REAL",      # DOUBLE PRECISION
    35:  "TEXT",      # TIMESTAMP (guardado como ISO string)
    37:  "TEXT",      # VARCHAR
    261: "TEXT",      # BLOB (almacenado como texto cuando es sub_type 1)
}


def _fb_type_to_sqlite(field_type: int) -> str:
    """Convierte un tipo Firebird (código numérico) al tipo SQLite equivalente."""
    return _FIREBIRD_TYPE_TO_SQLITE.get(field_type, "TEXT")


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
    El esquema SQLite se sincroniza dinámicamente con el de Firebird:
    mismas columnas, mismos tipos, mismas PKs.
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

            # ── 0. Sincronizar esquema desde Firebird ──────────────────────────
            # Todas las tablas objetivo deben tener las mismas columnas que Firebird
            all_target_tables = list(dict.fromkeys(
                JDDCTableNames.REFERENCE_TABLES
                + JDDCTableNames.DATE_TABLES
                + JDDCTableNames.LINKED_TABLES
            ))
            for table in all_target_tables:
                self._sync_schema_from_firebird(table)

            self._clear_sim_tables()
            counts: Dict[str, int] = {}

            # ── 1. Tablas de referencia (sin filtro de fecha) ──────────────────
            #    Incluye PROYECTOS, PROYVAR, PRESUPROYE con límite amplio
            for table in JDDCTableNames.REFERENCE_TABLES:
                counts[table] = self._capture_reference_table(table)

            # ── 2. Tablas con fecha (filtro por cutoff) ────────────────────────
            doccab_ids: List[int] = []
            for table in JDDCTableNames.DATE_TABLES:
                n, ids = self._capture_date_table(table, cutoff)
                counts[table] = n
                if table == JDDCTableNames.DOCCAB:
                    doccab_ids = list(ids)

            # ── 3. DOCCAB adicional: histórico completo por proyecto ───────────
            #    Sin límite de fecha — facturas/presupuestos de proyectos pueden
            #    ser de meses o años atrás. Esencial para %Ejecución correcto.
            n_proy, proy_ids = self._capture_doccab_by_project()
            counts["DOCCAB_PROYECTO"] = n_proy
            all_doccab_ids = list(set(doccab_ids) | set(proy_ids))

            # ── 4. DOCLIN enlazado a todos los DOCCAB capturados ──────────────
            counts[JDDCTableNames.DOCLIN] = self._capture_doclin(all_doccab_ids)

            # ── 5. DOCDESTINO enlazado a todos los DOCCAB capturados ──────────
            #    Necesario para tasa de éxito de presupuestos (TIPO=0→13)
            counts[JDDCTableNames.DOCDESTINO] = self._capture_docdestino(all_doccab_ids)

            self._sim_driver.conn.commit()
            total = sum(v for k, v in counts.items() if k != "DOCCAB_PROYECTO")
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

    # ─── Sincronización de esquema desde Firebird ─────────────────────────────

    def _sync_schema_from_firebird(self, table: str) -> None:
        """
        Sincroniza el esquema SQLite de una tabla con el schema real de Firebird.

        - Si la tabla NO existe en SQLite: la crea con TODAS las columnas de Firebird
          (mismos nombres, tipos traducidos, PKs).
        - Si la tabla YA existe: añade solo columnas nuevas (ADD COLUMN aditivo,
          jamás DROP ni ALTER de tipo — preserva datos existentes).

        Tipos Firebird → SQLite: VARCHAR/CHAR/BLOB → TEXT, INTEGER/SMALLINT → INTEGER,
        FLOAT/DOUBLE/DECIMAL/NUMERIC → REAL, DATE/TIMESTAMP → TEXT (ISO string).
        """
        fb_cols = self._get_firebird_columns_typed(table)
        if not fb_cols:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: no se encontraron columnas en Firebird — "
                f"usando esquema estático de schema.py"
            )
            return

        sim_conn = self._sim_driver.conn
        cur = sim_conn.cursor()

        # Columnas existentes en SQLite
        cur.execute(f"PRAGMA table_info({table})")
        existing: Set[str] = {r[1].upper() for r in cur.fetchall()}

        if not existing:
            # ── Crear tabla nueva con todas las columnas de Firebird ─────────
            fb_pks = self._get_firebird_pks(table)
            col_defs = []
            for col_name, col_type in fb_cols:
                sqlite_type = _fb_type_to_sqlite(col_type)
                col_defs.append(f"{col_name} {sqlite_type}")

            if fb_pks:
                pk_str = ", ".join(fb_pks)
                create_sql = (
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    f"({', '.join(col_defs)}, PRIMARY KEY ({pk_str}))"
                )
            else:
                create_sql = (
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    f"({', '.join(col_defs)})"
                )
            cur.execute(create_sql)
            logger.info(
                f"{SimulatorLog.SNAPSHOT} {table}: tabla creada "
                f"({len(fb_cols)} cols desde Firebird, PKs: {fb_pks})"
            )
        else:
            # ── Añadir columnas nuevas (aditivo, jamás DROP) ──────────────────
            added = 0
            for col_name, col_type in fb_cols:
                if col_name.upper() not in existing:
                    sqlite_type = _fb_type_to_sqlite(col_type)
                    try:
                        cur.execute(
                            f"ALTER TABLE {table} ADD COLUMN "
                            f"{col_name} {sqlite_type} DEFAULT NULL"
                        )
                        added += 1
                    except sqlite3.OperationalError:
                        pass  # Ya existe (race condition)
            if added:
                logger.info(
                    f"{SimulatorLog.SNAPSHOT} {table}: {added} columnas nuevas añadidas"
                )

        sim_conn.commit()

    def _get_firebird_columns_typed(
        self, table: str
    ) -> List[Tuple[str, int]]:
        """
        Devuelve [(col_name, field_type_code), ...] ordenado por posición.
        Consulta RDB$RELATION_FIELDS + RDB$FIELDS en Firebird.
        """
        try:
            sql = (
                "SELECT TRIM(rf.RDB$FIELD_NAME) AS FIELD_NAME, "
                "       f.RDB$FIELD_TYPE        AS FIELD_TYPE "
                "FROM RDB$RELATION_FIELDS rf "
                "JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE "
                f"WHERE TRIM(rf.RDB$RELATION_NAME) = '{table}' "
                "ORDER BY rf.RDB$FIELD_POSITION"
            )
            rows = self._fb_query(sql)
            return [
                (r["FIELD_NAME"].strip(), int(r["FIELD_TYPE"] or 37))
                for r in rows
                if r.get("FIELD_NAME")
            ]
        except Exception as e:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: error obteniendo columnas Firebird ({e})"
            )
            return []

    def _get_firebird_pks(self, table: str) -> List[str]:
        """
        Devuelve la lista de columnas PK de una tabla Firebird.
        Consulta RDB$RELATION_CONSTRAINTS + RDB$INDEX_SEGMENTS.
        """
        try:
            sql = (
                "SELECT TRIM(seg.RDB$FIELD_NAME) AS FIELD_NAME "
                "FROM RDB$RELATION_CONSTRAINTS rc "
                "JOIN RDB$INDEX_SEGMENTS seg ON seg.RDB$INDEX_NAME = rc.RDB$INDEX_NAME "
                f"WHERE TRIM(rc.RDB$RELATION_NAME) = '{table}' "
                "  AND rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY' "
                "ORDER BY seg.RDB$FIELD_POSITION"
            )
            rows = self._fb_query(sql)
            return [r["FIELD_NAME"].strip() for r in rows if r.get("FIELD_NAME")]
        except Exception as e:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: error obteniendo PKs ({e})"
            )
            return []

    # ─── Captura de tablas ────────────────────────────────────────────────────

    def _capture_reference_table(self, table: str) -> int:
        """
        Captura hasta MAX_ROWS_PER_TABLE filas sin filtro de fecha.
        Para tablas de proyectos usa MAX_PROYECTO_ROWS (más amplio) porque
        PROYECTOS/PROYVAR/PRESUPROYE tienen más registros que el resto.
        """
        _PROJECT_TABLES = {
            JDDCTableNames.PROYECTOS,
            JDDCTableNames.PROYVAR,
            JDDCTableNames.PRESUPROYE,
        }
        limit = Cfg.MAX_PROYECTO_ROWS if table in _PROJECT_TABLES else Cfg.MAX_ROWS_PER_TABLE
        try:
            rows = self._fb_query(
                f"SELECT FIRST {limit} * FROM {table}"
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

    def _capture_doccab_by_project(self) -> Tuple[int, List[int]]:
        """
        Captura TODOS los DOCCAB que tienen CODPROYECTO relleno, sin límite de fecha.

        Necesario porque el análisis económico de proyectos requiere el historial
        completo: facturas y presupuestos de un proyecto pueden ser de hace años.
        El filtro por cutoff del step 2 solo daría actividad del último mes.

        Usa INSERT OR IGNORE, por lo que los DOCCAB ya capturados en el step 2
        no se duplican.
        """
        limit = Cfg.MAX_DOCCAB_PROYECTO_ROWS
        try:
            rows = self._fb_query(
                f"SELECT FIRST {limit} * FROM DOCCAB "
                f"WHERE CODPROYECTO IS NOT NULL AND TRIM(CODPROYECTO) <> '' "
                f"ORDER BY FECHA DESC"
            )
            if rows:
                self._bulk_insert(JDDCTableNames.DOCCAB, rows)
            ids = [r.get("CODIGO") for r in rows if r.get("CODIGO") is not None]
            logger.info(
                f"{SimulatorLog.SNAPSHOT} DOCCAB[proyecto]: {len(rows)} filas "
                f"(histórico completo, sin límite fecha)"
            )
            return len(rows), ids
        except Exception as e:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} DOCCAB[proyecto]: error capturando ({e})"
            )
            return 0, []

    def _capture_docdestino(self, doccab_ids: List[int]) -> int:
        """
        Captura relaciones DOCDESTINO para los DOCCAB capturados.
        Necesaria para calcular tasa de éxito de presupuestos (presupuesto→factura).
        """
        if not doccab_ids:
            return 0
        try:
            total = 0
            batch_size = 500
            for i in range(0, len(doccab_ids), batch_size):
                batch = doccab_ids[i:i + batch_size]
                placeholders = ",".join(str(x) for x in batch)
                rows = self._fb_query(
                    f"SELECT * FROM DOCDESTINO "
                    f"WHERE CODDOCUMENTO IN ({placeholders})"
                )
                if rows:
                    self._bulk_insert(JDDCTableNames.DOCDESTINO, rows)
                    total += len(rows)
            logger.info(f"{SimulatorLog.SNAPSHOT} DOCDESTINO: {total} filas")
            return total
        except Exception as e:
            logger.warning(f"{SimulatorLog.SNAPSHOT} DOCDESTINO: error capturando ({e})")
            return 0

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
        garantizando compatibilidad cuando el esquema Firebird tiene más columnas
        (por ejemplo si _sync_schema_from_firebird no llegó a ejecutarse).
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
