"""
snapshot_service.py — Captura UNIVERSAL datos reales de Firebird → SQLite simulador.

PRINCIPIO FUNDAMENTAL:
  El simulador debe ser un ESPEJO EXACTO de la BD real — mismas tablas, mismas
  columnas, mismos metadatos (PKs, tipos). El esquema SQLite se genera DINÁMICAMENTE
  desde Firebird al hacer build-snapshot, sin depender de schema.py manual.

Estrategia de captura UNIVERSAL (sin nombres de tabla hardcodeados):

  0. Descubrimiento — leer RDB$RELATIONS para obtener todas las tablas de usuario
     (no vistas, no tablas de sistema).

  1. Análisis — para cada tabla:
       • Columnas y tipos (RDB$RELATION_FIELDS + RDB$FIELDS)
       • PKs (RDB$RELATION_CONSTRAINTS + RDB$INDEX_SEGMENTS)
       • FKs (RDB$REF_CONSTRAINTS + RDB$INDEX_SEGMENTS × 2)
       • Columna de fecha (por nombre canónico o tipo Firebird DATE/TIMESTAMP)
       • Conteo de filas con timeout (hilo separado, 8 s máx.)
       → Categoría: TINY / SMALL / MEDIUM / LARGE / MEGA / SKIP

  2. Ordenación topológica (Kahn) — padres FK antes que hijos.

  3. Sincronización de esquema — crear / alterar tablas SQLite (aditivo, nunca DROP).

  4. Captura por categoría:
       TINY   (<500):     SELECT * — sin límite
       SMALL  (<5K):      SELECT FIRST 1 000 *
       MEDIUM (<50K):     FIRST 2 000, últimos 3 meses si tiene fecha
       LARGE  (<500K):    FIRST 5 000, últimos 3 meses si tiene fecha
       MEGA   (<10M):     FIRST 1 000, último 1 mes si tiene fecha
       SKIP   (>10M, sin fecha): omitir con aviso — demasiado grande

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
import sqlite3
import threading
from dataclasses import dataclass, field as dc_field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.modules.db_simulator.constants import SimulatorLog
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver

logger = logging.getLogger(__name__)


# ─── Mapeo tipos Firebird → SQLite ────────────────────────────────────────────
# Referencia: https://firebirdsql.org/refdocs/langrefupd25-rdb-fields.html

_FIREBIRD_TYPE_TO_SQLITE: Dict[int, str] = {
    7:   "INTEGER",   # SMALLINT
    8:   "INTEGER",   # INTEGER
    9:   "INTEGER",   # QUAD (obsoleto)
    10:  "REAL",      # FLOAT
    11:  "REAL",      # D_FLOAT (obsoleto)
    12:  "TEXT",      # DATE (guardado como ISO string 'YYYY-MM-DD')
    13:  "TEXT",      # TIME (guardado como 'HH:MM:SS')
    14:  "TEXT",      # CHAR
    16:  "REAL",      # INT64 / BIGINT / DECIMAL / NUMERIC (con escala)
    23:  "INTEGER",   # BOOLEAN (Firebird 3+)
    27:  "REAL",      # DOUBLE PRECISION
    35:  "TEXT",      # TIMESTAMP (guardado como ISO string)
    37:  "TEXT",      # VARCHAR
    261: "TEXT",      # BLOB (sub_type 1 = texto)
}

# Tipos Firebird que representan fecha/timestamp
_FB_DATE_TYPES: frozenset = frozenset({12, 35})   # DATE=12, TIMESTAMP=35

# Lista de prioridad para detectar la columna de fecha de una tabla
# (el primer nombre que exista en la tabla gana)
_DATE_COL_PRIORITY: Tuple[str, ...] = (
    "FECHA", "FECHADOC", "FECHAFACT", "FECHAEMISION", "FECHACREACION",
    "FECHAALTA", "FECHAMODIF", "FECHA_DOC", "FECHA_EMISION", "FECEMI",
    "FECDOC", "FECALTA", "FECHAVENC", "FECHAVENCIMIENTO",
    "DATECREATED", "DATEMODIFIED", "CREATED_AT", "UPDATED_AT",
)

# Centinela devuelto cuando COUNT(*) supera el timeout
_COUNT_TIMEOUT: int = 999_999_999


def _fb_type_to_sqlite(field_type: int) -> str:
    """Convierte código de tipo Firebird al tipo SQLite equivalente."""
    return _FIREBIRD_TYPE_TO_SQLITE.get(field_type, "TEXT")


def _cutoff_date(months_back: int) -> str:
    """Devuelve fecha de corte 'YYYY-MM-DD' retrocediendo months_back meses."""
    today = date.today()
    month = today.month - months_back
    year  = today.year
    while month <= 0:
        month += 12
        year  -= 1
    return f"{year:04d}-{month:02d}-01"


# ─── Categorías de captura ────────────────────────────────────────────────────

class CaptureCategory(str, Enum):
    TINY   = "tiny"    # < 500 filas:   capturar todo sin límite
    SMALL  = "small"   # 500 – 5K:      FIRST 1 000
    MEDIUM = "medium"  # 5K – 50K:      FIRST 2 000, últimos 3 meses si hay fecha
    LARGE  = "large"   # 50K – 500K:    FIRST 5 000, últimos 3 meses si hay fecha
    MEGA   = "mega"    # 500K – 10M:    FIRST 1 000, último 1 mes si hay fecha
    SKIP   = "skip"    # > 10M sin fecha: omitir — riesgo de saturación


class CaptureThresholds:
    """Límites y parámetros de cada categoría."""
    TINY_MAX   = 500
    SMALL_MAX  = 5_000
    MEDIUM_MAX = 50_000
    LARGE_MAX  = 500_000
    MEGA_MAX   = 10_000_000

    # 0 = sin FIRST (captura total)
    TINY_LIMIT   = 0
    SMALL_LIMIT  = 1_000
    MEDIUM_LIMIT = 2_000
    LARGE_LIMIT  = 5_000
    MEGA_LIMIT   = 1_000

    MEDIUM_MONTHS = 3
    LARGE_MONTHS  = 3
    MEGA_MONTHS   = 1

    COUNT_TIMEOUT_SECS: float = 8.0


# ─── Información de tabla ─────────────────────────────────────────────────────

@dataclass
class TableInfo:
    name:      str
    row_count: int
    category:  CaptureCategory
    date_col:  Optional[str]              # Nombre de columna de fecha, o None
    pks:       List[str]                  # Columnas PK en orden
    fks:       List[Dict[str, str]]       # [{child_col, parent_table, parent_col}]
    all_cols:  List[Tuple[str, int]]      # [(nombre_columna, fb_type_code)]


# ─── SnapshotService ─────────────────────────────────────────────────────────

class SnapshotService:
    """
    Captura universal de datos Firebird → SQLite del simulador.

    Auto-descubre todas las tablas de usuario, las clasifica por volumen,
    respeta dependencias FK y captura con límites adecuados a cada categoría.

    Interfaz pública: SnapshotService(db_params).run() → Dict[str, int]
    """

    def __init__(self, db_params: Dict[str, Any]):
        self.db_params   = db_params
        self._fb_conn    = None
        self._sim_driver: Optional[SimulatedFirebirdDriver] = None

    # ─── Entrada pública ──────────────────────────────────────────────────────

    def run(self) -> Dict[str, int]:
        """
        Ejecuta el snapshot universal completo.
        Returns: {tabla: filas_capturadas}
        """
        logger.info(
            f"{SimulatorLog.SNAPSHOT} ══════════════════════════════════════\n"
            f"{SimulatorLog.SNAPSHOT} Iniciando snapshot universal "
            f"→ BD: {self.db_params.get('database', '?')}"
        )
        try:
            self._connect_firebird()
            self._sim_driver = SimulatedFirebirdDriver()
            self._sim_driver.connect()

            # ── 0. Descubrir tablas de usuario ────────────────────────────────
            all_tables = self._discover_all_tables()
            logger.info(
                f"{SimulatorLog.SNAPSHOT} Tablas de usuario en Firebird: "
                f"{len(all_tables)}"
            )

            # ── 1. Obtener todas las FKs de una vez ───────────────────────────
            all_fks = self._get_all_fks()

            # ── 2. Analizar cada tabla ────────────────────────────────────────
            table_infos: Dict[str, TableInfo] = {}
            for tbl in all_tables:
                info = self._analyze_table(tbl, all_fks.get(tbl, []))
                table_infos[tbl] = info
                date_hint = f" [fecha:{info.date_col}]" if info.date_col else ""
                logger.info(
                    f"{SimulatorLog.SNAPSHOT} {tbl}: "
                    f"{info.row_count:,} filas → {info.category.value}{date_hint}"
                )

            # ── 3. Ordenar por dependencias FK (topológico) ───────────────────
            capture_order = self._build_capture_order(table_infos)
            capturable = [
                t for t in capture_order
                if table_infos[t].category != CaptureCategory.SKIP
            ]
            skipped = [
                t for t in capture_order
                if table_infos[t].category == CaptureCategory.SKIP
            ]
            if skipped:
                logger.warning(
                    f"{SimulatorLog.SNAPSHOT} Tablas OMITIDAS (>10M sin fecha): "
                    f"{skipped}"
                )

            # ── 4. Sincronizar esquema SQLite con Firebird ────────────────────
            for tbl in capturable:
                self._sync_schema_from_firebird(table_infos[tbl])

            # ── 5. Limpiar tablas antes de repoblar (orden inverso para FKs) ──
            self._clear_sim_tables(capturable)

            # ── 6. Capturar datos en orden topológico ─────────────────────────
            counts: Dict[str, int] = {}
            for tbl in capturable:
                counts[tbl] = self._capture_table(table_infos[tbl])

            self._sim_driver.conn.commit()
            total = sum(counts.values())
            logger.info(
                f"{SimulatorLog.SNAPSHOT} ✅ Snapshot completado: "
                f"{total:,} registros en {len(capturable)} tablas\n"
                f"{SimulatorLog.SNAPSHOT} ══════════════════════════════════════"
            )
            return counts

        except Exception as e:
            logger.error(
                f"{SimulatorLog.SNAPSHOT} ❌ Error en snapshot: {e}",
                exc_info=True
            )
            raise
        finally:
            self._disconnect_firebird()
            if self._sim_driver:
                self._sim_driver.disconnect()

    # ─── Descubrimiento de tablas ─────────────────────────────────────────────

    def _discover_all_tables(self) -> List[str]:
        """
        Devuelve todos los nombres de tablas de usuario en Firebird.
        Excluye vistas (RDB$VIEW_BLR IS NULL) y tablas de sistema (RDB$SYSTEM_FLAG=0).
        """
        sql = (
            "SELECT TRIM(RDB$RELATION_NAME) AS TNAME "
            "FROM RDB$RELATIONS "
            "WHERE RDB$SYSTEM_FLAG = 0 "
            "  AND RDB$VIEW_BLR IS NULL "
            "ORDER BY RDB$RELATION_NAME"
        )
        rows = self._fb_query(sql)
        return [r["TNAME"].strip() for r in rows if r.get("TNAME")]

    # ─── Análisis de tabla ────────────────────────────────────────────────────

    def _analyze_table(
        self, table: str, fks: List[Dict[str, str]]
    ) -> TableInfo:
        """Analiza una tabla y devuelve su TableInfo completo."""
        all_cols = self._get_firebird_columns_typed(table)
        pks      = self._get_firebird_pks(table)
        date_col = self._find_date_column(all_cols)
        count    = self._count_table_rows(table)
        category = self._categorize_table(count, date_col)
        return TableInfo(
            name=table,
            row_count=count,
            category=category,
            date_col=date_col,
            pks=pks,
            fks=fks,
            all_cols=all_cols,
        )

    def _find_date_column(
        self, cols: List[Tuple[str, int]]
    ) -> Optional[str]:
        """
        Detecta la columna de fecha más relevante para filtrar por periodo.

        Prioridad:
          1. Nombre exacto en _DATE_COL_PRIORITY (en el orden de la lista)
          2. Primera columna cuyo tipo Firebird es DATE (12) o TIMESTAMP (35)

        Returns: nombre de columna o None.
        """
        col_upper: Dict[str, str] = {c[0].upper(): c[0] for c in cols}

        for canonical in _DATE_COL_PRIORITY:
            if canonical.upper() in col_upper:
                return col_upper[canonical.upper()]

        for col_name, col_type in cols:
            if col_type in _FB_DATE_TYPES:
                return col_name

        return None

    def _categorize_table(
        self, row_count: int, date_col: Optional[str]
    ) -> CaptureCategory:
        """Clasifica la tabla en una categoría de captura según su volumen."""
        T = CaptureThresholds
        if row_count <= T.TINY_MAX:
            return CaptureCategory.TINY
        if row_count <= T.SMALL_MAX:
            return CaptureCategory.SMALL
        if row_count <= T.MEDIUM_MAX:
            return CaptureCategory.MEDIUM
        if row_count <= T.LARGE_MAX:
            return CaptureCategory.LARGE
        if row_count <= T.MEGA_MAX:
            return CaptureCategory.MEGA
        # > 10M: solo capturar si hay columna de fecha (muestra del último mes)
        if date_col:
            return CaptureCategory.MEGA
        return CaptureCategory.SKIP

    # ─── Conteo con timeout ───────────────────────────────────────────────────

    def _count_table_rows(self, table: str) -> int:
        """
        Cuenta filas de una tabla Firebird con timeout para evitar bloqueos.

        Usa un hilo daemon con conexión Firebird propia.
        Si supera COUNT_TIMEOUT_SECS devuelve _COUNT_TIMEOUT (≡ MEGA).
        Si la conexión falla devuelve TINY_MAX (asume tabla pequeña).
        """
        result_holder:    List[int]       = []
        exception_holder: List[Exception] = []

        def _do_count() -> None:
            import firebirdsql
            p = self.db_params
            user     = p.get("user") or p.get("username") or "SYSDBA"
            password = p.get("password", "masterkey")
            try:
                conn = firebirdsql.connect(
                    host=p.get("host", "localhost"),
                    port=int(p.get("port", 3050)),
                    database=p.get("database", ""),
                    user=user,
                    password=password,
                    charset=p.get("charset", "latin1"),
                )
                cur = conn.cursor()
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row = cur.fetchone()
                result_holder.append(int(row[0]) if row else 0)
                conn.close()
            except Exception as e:
                exception_holder.append(e)

        t = threading.Thread(target=_do_count, daemon=True)
        t.start()
        t.join(timeout=CaptureThresholds.COUNT_TIMEOUT_SECS)

        if t.is_alive():
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: COUNT(*) timeout "
                f"({CaptureThresholds.COUNT_TIMEOUT_SECS}s) → tratado como MEGA"
            )
            return _COUNT_TIMEOUT

        if exception_holder:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: error COUNT(*) "
                f"({exception_holder[0]}) → asumiendo TINY"
            )
            return CaptureThresholds.TINY_MAX

        return result_holder[0] if result_holder else 0

    # ─── Relaciones FK (una sola query para toda la BD) ───────────────────────

    def _get_all_fks(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Obtiene TODAS las relaciones FK de la base de datos en una sola consulta.
        Returns: {tabla_hija: [{child_col, parent_table, parent_col}]}
        """
        sql = (
            "SELECT "
            "  TRIM(rc_child.RDB$RELATION_NAME)  AS CHILD_TABLE, "
            "  TRIM(seg_child.RDB$FIELD_NAME)    AS CHILD_COL, "
            "  TRIM(rc_parent.RDB$RELATION_NAME) AS PARENT_TABLE, "
            "  TRIM(seg_parent.RDB$FIELD_NAME)   AS PARENT_COL "
            "FROM RDB$RELATION_CONSTRAINTS rc_child "
            "JOIN RDB$REF_CONSTRAINTS refc "
            "  ON refc.RDB$CONSTRAINT_NAME = rc_child.RDB$CONSTRAINT_NAME "
            "JOIN RDB$RELATION_CONSTRAINTS rc_parent "
            "  ON rc_parent.RDB$CONSTRAINT_NAME = refc.RDB$CONST_NAME_UQ "
            "JOIN RDB$INDEX_SEGMENTS seg_child "
            "  ON seg_child.RDB$INDEX_NAME = rc_child.RDB$INDEX_NAME "
            "JOIN RDB$INDEX_SEGMENTS seg_parent "
            "  ON seg_parent.RDB$INDEX_NAME = rc_parent.RDB$INDEX_NAME "
            "  AND seg_parent.RDB$FIELD_POSITION = seg_child.RDB$FIELD_POSITION "
            "WHERE rc_child.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY' "
            "ORDER BY "
            "  TRIM(rc_child.RDB$RELATION_NAME), "
            "  seg_child.RDB$FIELD_POSITION"
        )
        result: Dict[str, List[Dict[str, str]]] = {}
        try:
            rows = self._fb_query(sql)
            for r in rows:
                child = (r.get("CHILD_TABLE") or "").strip()
                if not child:
                    continue
                result.setdefault(child, []).append({
                    "child_col":    (r.get("CHILD_COL")    or "").strip(),
                    "parent_table": (r.get("PARENT_TABLE") or "").strip(),
                    "parent_col":   (r.get("PARENT_COL")   or "").strip(),
                })
        except Exception as e:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} Error leyendo FKs globales ({e}); "
                f"se continuará sin información de FK"
            )
        return result

    # ─── Ordenación topológica ────────────────────────────────────────────────

    def _build_capture_order(
        self, table_infos: Dict[str, TableInfo]
    ) -> List[str]:
        """
        Ordena las tablas para que los padres FK se capturen antes que los hijos.
        Algoritmo de Kahn (BFS). Los ciclos detectados se añaden al final.
        """
        table_set = set(table_infos.keys())

        # Para cada tabla, qué padres necesita (que también estén en nuestra lista)
        in_edges: Dict[str, Set[str]] = {t: set() for t in table_set}
        for tbl, info in table_infos.items():
            for fk in info.fks:
                parent = fk.get("parent_table", "")
                if parent in table_set and parent != tbl:
                    in_edges[tbl].add(parent)

        order: List[str] = []
        remaining = {t: set(deps) for t, deps in in_edges.items()}

        while remaining:
            ready = sorted(t for t, deps in remaining.items() if not deps)
            if not ready:
                # Ciclo detectado — añadir resto en orden alfabético
                cycle_tables = sorted(remaining.keys())
                logger.warning(
                    f"{SimulatorLog.SNAPSHOT} Ciclo FK detectado entre: "
                    f"{cycle_tables} — capturando en orden arbitrario"
                )
                order.extend(cycle_tables)
                break
            for t in ready:
                order.append(t)
                del remaining[t]
                for deps in remaining.values():
                    deps.discard(t)

        return order

    # ─── Sincronización de esquema SQLite ────────────────────────────────────

    def _sync_schema_from_firebird(self, info: TableInfo) -> None:
        """
        Sincroniza el esquema SQLite con el real de Firebird.

        • Tabla inexistente → CREATE TABLE con todas las columnas y PKs de Firebird
        • Tabla existente   → ADD COLUMN para columnas nuevas (aditivo, jamás DROP)

        Los tipos Firebird se traducen al equivalente SQLite más próximo.
        """
        table = info.name
        if not info.all_cols:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: sin columnas en Firebird "
                f"— esquema no sincronizado"
            )
            return

        sim_conn = self._sim_driver.conn
        cur = sim_conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        existing: Set[str] = {r[1].upper() for r in cur.fetchall()}

        if not existing:
            # ── Crear tabla con columnas + PK de Firebird ─────────────────────
            col_defs = [
                f"{col_name} {_fb_type_to_sqlite(col_type)}"
                for col_name, col_type in info.all_cols
            ]
            if info.pks:
                pk_str = ", ".join(info.pks)
                ddl = (
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    f"({', '.join(col_defs)}, PRIMARY KEY ({pk_str}))"
                )
            else:
                ddl = (
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    f"({', '.join(col_defs)})"
                )
            cur.execute(ddl)
            logger.info(
                f"{SimulatorLog.SNAPSHOT} {table}: tabla creada "
                f"({len(info.all_cols)} cols, PKs={info.pks}, "
                f"{len(info.fks)} FKs referenciadas)"
            )
        else:
            # ── Añadir solo columnas nuevas (jamás DROP) ──────────────────────
            added = 0
            for col_name, col_type in info.all_cols:
                if col_name.upper() not in existing:
                    sqlite_type = _fb_type_to_sqlite(col_type)
                    try:
                        cur.execute(
                            f"ALTER TABLE {table} ADD COLUMN "
                            f"{col_name} {sqlite_type} DEFAULT NULL"
                        )
                        added += 1
                    except sqlite3.OperationalError:
                        pass  # Columna ya existe (condición de carrera)
            if added:
                logger.info(
                    f"{SimulatorLog.SNAPSHOT} {table}: {added} columnas añadidas"
                )

        sim_conn.commit()

    # ─── Captura de datos ─────────────────────────────────────────────────────

    def _capture_table(self, info: TableInfo) -> int:
        """
        Captura datos de Firebird a SQLite según la categoría de la tabla.
        Returns: número de filas insertadas en SQLite.
        """
        table = info.name
        cat   = info.category
        T     = CaptureThresholds

        try:
            rows: List[Dict[str, Any]] = []

            if cat == CaptureCategory.TINY:
                # Sin límite FIRST: queremos absolutamente todos los registros
                rows = self._fb_query(f"SELECT * FROM {table}")

            elif cat == CaptureCategory.SMALL:
                rows = self._fb_query(
                    f"SELECT FIRST {T.SMALL_LIMIT} * FROM {table}"
                )

            elif cat == CaptureCategory.MEDIUM:
                if info.date_col:
                    cutoff = _cutoff_date(T.MEDIUM_MONTHS)
                    rows = self._fb_query(
                        f"SELECT FIRST {T.MEDIUM_LIMIT} * FROM {table} "
                        f"WHERE {info.date_col} >= CAST('{cutoff}' AS DATE) "
                        f"ORDER BY {info.date_col} DESC"
                    )
                else:
                    rows = self._fb_query(
                        f"SELECT FIRST {T.MEDIUM_LIMIT} * FROM {table}"
                    )

            elif cat == CaptureCategory.LARGE:
                if info.date_col:
                    cutoff = _cutoff_date(T.LARGE_MONTHS)
                    rows = self._fb_query(
                        f"SELECT FIRST {T.LARGE_LIMIT} * FROM {table} "
                        f"WHERE {info.date_col} >= CAST('{cutoff}' AS DATE) "
                        f"ORDER BY {info.date_col} DESC"
                    )
                else:
                    rows = self._fb_query(
                        f"SELECT FIRST {T.LARGE_LIMIT} * FROM {table}"
                    )

            elif cat == CaptureCategory.MEGA:
                if info.date_col:
                    cutoff = _cutoff_date(T.MEGA_MONTHS)
                    rows = self._fb_query(
                        f"SELECT FIRST {T.MEGA_LIMIT} * FROM {table} "
                        f"WHERE {info.date_col} >= CAST('{cutoff}' AS DATE) "
                        f"ORDER BY {info.date_col} DESC"
                    )
                else:
                    # Sin columna de fecha pero MEGA → muestra mínima de los primeros
                    rows = self._fb_query(
                        f"SELECT FIRST {T.MEGA_LIMIT} * FROM {table}"
                    )

            else:  # SKIP — no debería llegar aquí (filtrado antes)
                logger.warning(
                    f"{SimulatorLog.SNAPSHOT} {table}: categoría SKIP llegó a "
                    f"_capture_table — ignorado"
                )
                return 0

            if rows:
                self._bulk_insert(table, rows)

            # Mensaje de log con información de filtro temporal si aplica
            date_note = ""
            if info.date_col and cat not in (
                CaptureCategory.TINY, CaptureCategory.SMALL
            ):
                months = (
                    T.MEGA_MONTHS if cat == CaptureCategory.MEGA
                    else T.MEDIUM_MONTHS
                )
                date_note = f" (desde {_cutoff_date(months)})"

            logger.info(
                f"{SimulatorLog.SNAPSHOT} {table}: {len(rows)} filas "
                f"[{cat.value}]{date_note}"
            )
            return len(rows)

        except Exception as e:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: error capturando "
                f"[{cat.value}] ({e})"
            )
            return 0

    # ─── Inserción masiva en SQLite ───────────────────────────────────────────

    def _bulk_insert(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """
        Inserta filas en la tabla SQLite del simulador usando INSERT OR IGNORE.

        • Filtra columnas de Firebird que no existen en SQLite (tolerancia a esquemas
          que aún no estén completamente sincronizados).
        • Convierte date/datetime → string ISO.
        • Convierte bytes → str latin1 (campos CHAR/VARCHAR de Firebird).
        """
        if not rows:
            return
        sim_conn: sqlite3.Connection = self._sim_driver.conn

        cur = sim_conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        known_cols: Set[str] = {r[1].upper() for r in cur.fetchall()}

        fb_cols = list(rows[0].keys())
        cols    = [c for c in fb_cols if c.upper() in known_cols]
        if not cols:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: ninguna columna de Firebird "
                f"coincide con SQLite — filas descartadas"
            )
            return

        ph      = ",".join(["?"] * len(cols))
        col_str = ",".join(cols)
        sql     = f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({ph})"

        data: List[tuple] = []
        for row in rows:
            vals = []
            for col in cols:
                v = row.get(col)
                if hasattr(v, "isoformat"):
                    v = v.isoformat()
                elif isinstance(v, bytes):
                    try:
                        v = v.decode("latin1", errors="replace").strip()
                    except Exception:
                        v = str(v)
                vals.append(v)
            data.append(tuple(vals))

        sim_conn.cursor().executemany(sql, data)

    def _clear_sim_tables(self, tables: List[str]) -> None:
        """
        Limpia las tablas indicadas en orden inverso al de captura (respeta FKs).
        Solo borra las tablas que vamos a repoblar — no toca el resto.
        """
        sim_conn = self._sim_driver.conn
        for table in reversed(tables):
            try:
                sim_conn.cursor().execute(f"DELETE FROM {table}")
            except Exception:
                pass

    # ─── Metadatos de Firebird ────────────────────────────────────────────────

    def _get_firebird_columns_typed(
        self, table: str
    ) -> List[Tuple[str, int]]:
        """
        Devuelve [(nombre_columna, field_type_code), ...] en orden de posición.
        Consulta RDB$RELATION_FIELDS + RDB$FIELDS.
        """
        try:
            sql = (
                "SELECT TRIM(rf.RDB$FIELD_NAME) AS FIELD_NAME, "
                "       f.RDB$FIELD_TYPE        AS FIELD_TYPE "
                "FROM RDB$RELATION_FIELDS rf "
                "JOIN RDB$FIELDS f "
                "  ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE "
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
                f"{SimulatorLog.SNAPSHOT} {table}: error leyendo columnas ({e})"
            )
            return []

    def _get_firebird_pks(self, table: str) -> List[str]:
        """
        Devuelve las columnas PK de una tabla Firebird en orden de posición.
        Consulta RDB$RELATION_CONSTRAINTS + RDB$INDEX_SEGMENTS.
        """
        try:
            sql = (
                "SELECT TRIM(seg.RDB$FIELD_NAME) AS FIELD_NAME "
                "FROM RDB$RELATION_CONSTRAINTS rc "
                "JOIN RDB$INDEX_SEGMENTS seg "
                "  ON seg.RDB$INDEX_NAME = rc.RDB$INDEX_NAME "
                f"WHERE TRIM(rc.RDB$RELATION_NAME) = '{table}' "
                "  AND rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY' "
                "ORDER BY seg.RDB$FIELD_POSITION"
            )
            rows = self._fb_query(sql)
            return [r["FIELD_NAME"].strip() for r in rows if r.get("FIELD_NAME")]
        except Exception as e:
            logger.warning(
                f"{SimulatorLog.SNAPSHOT} {table}: error leyendo PKs ({e})"
            )
            return []

    # ─── Conexión a Firebird ──────────────────────────────────────────────────

    def _connect_firebird(self) -> None:
        """Abre conexión directa a Firebird usando firebirdsql."""
        import firebirdsql
        p        = self.db_params
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
        logger.info(
            f"{SimulatorLog.SNAPSHOT} Conectado a Firebird: "
            f"{p.get('host')}:{p.get('port')}"
        )

    def _disconnect_firebird(self) -> None:
        if self._fb_conn:
            try:
                self._fb_conn.close()
            except Exception:
                pass
            self._fb_conn = None

    def _fb_query(self, sql: str) -> List[Dict[str, Any]]:
        """Ejecuta una consulta en Firebird y devuelve lista de dicts."""
        cur = self._fb_conn.cursor()
        cur.execute(sql)
        if not cur.description:
            return []
        cols  = [d[0] for d in cur.description]
        rows_ = cur.fetchall()
        result = []
        for row in rows_:
            d: Dict[str, Any] = {}
            for col, val in zip(cols, row):
                if isinstance(val, bytes):
                    try:
                        val = val.decode("latin1", errors="replace").strip()
                    except Exception:
                        val = str(val)
                d[col] = val
            result.append(d)
        return result
