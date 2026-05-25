"""
driver.py — SimulatedFirebirdDriver: drop-in replacement de FirebirdDriver.

Implementa la misma interfaz DatabaseDriver que FirebirdDriver pero usa
una BD SQLite local en lugar de conectar a Firebird 2.5.

Características:
  • Intercepta queries RDB$ (system tables) y devuelve metadatos simulados
  • Traduce SQL Firebird → SQLite antes de ejecutar (via query_translator)
  • Auto-inicializa tablas SQLite si no existen
  • Compatible con las signaturas exactas de FirebirdDriver
  • Sin estado externo: cada connect() abre SQLite, disconnect() lo cierra

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional

from backend.core.abstract.database import DatabaseDriver, DBConfig
from backend.modules.db_simulator.constants import SimulatorLog, SimulatorPaths, JDDCTableNames
from backend.modules.db_simulator.schema import TABLE_SCHEMAS, TABLE_CREATION_ORDER, TABLE_INDEXES, TABLE_COLUMNS
from backend.modules.db_simulator.query_translator import translate_firebird_sql

logger = logging.getLogger(__name__)

# ─── Lista de tablas simuladas (para responder RDB$RELATIONS) ─────────────────
_SIMULATED_TABLE_NAMES = list(TABLE_SCHEMAS.keys())


class SimulatedFirebirdDriver(DatabaseDriver):
    """
    Driver SQLite que actúa como Firebird frente al resto del sistema.
    Acepta exactamente el mismo contrato que FirebirdDriver.
    """

    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None

    # ─── Interfaz DatabaseDriver ──────────────────────────────────────────────

    def connect(
        self,
        config: Optional[DBConfig] = None,
        db_path: Optional[str] = None,
    ) -> sqlite3.Connection:
        """
        Abre la BD SQLite del simulador.

        - config    : ignorado (compatibilidad con FirebirdDriver)
        - db_path   : ruta explícita; si es None usa SimulatorPaths.DB_PATH.
                      Pasar ":memory:" para tests de aislamiento total.
        """
        try:
            actual_path = db_path or str(SimulatorPaths.DB_PATH)
            if actual_path != ":memory:":
                SimulatorPaths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(actual_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._ensure_tables()
            logger.debug(f"{SimulatorLog.DRIVER} Conectado a SQLite: {actual_path}")
            return self.conn
        except Exception as e:
            raise Exception(f"{SimulatorLog.DRIVER} Error abriendo SQLite: {e}") from e

    def disconnect(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            finally:
                self.conn = None
        logger.debug(f"{SimulatorLog.DRIVER} Desconectado de SQLite")

    def execute_query(
        self, query: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta una query SELECT.
        1. Intercepta queries de sistema (RDB$)
        2. Traduce Firebird SQL → SQLite
        3. Ejecuta en SQLite
        4. Devuelve lista de dicts (igual que FirebirdDriver)
        """
        if not self.conn:
            self.connect()

        # ── 1. System queries (RDB$) ─────────────────────────────────────────
        if "RDB$" in query.upper():
            return self._handle_system_query(query, params)

        # ── 2. Traducción Firebird → SQLite ──────────────────────────────────
        translated_sql, changes = translate_firebird_sql(query)
        if changes:
            logger.debug(
                f"{SimulatorLog.QUERY} Traducido ({len(changes)} cambios): "
                f"{translated_sql[:120]}"
            )
        else:
            logger.debug(f"{SimulatorLog.QUERY} Sin cambios: {translated_sql[:120]}")

        # ── 3. Ejecución ─────────────────────────────────────────────────────
        try:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(translated_sql, params)
            else:
                cursor.execute(translated_sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(
                f"{SimulatorLog.QUERY} Error SQLite: {e}\n"
                f"  SQL original : {query[:200]}\n"
                f"  SQL traducido: {translated_sql[:200]}"
            )
            raise Exception(f"[SIM] Error en query: {e}") from e

    def execute_command(
        self, command: str, params: Optional[tuple] = None
    ) -> int:
        """Ejecuta INSERT/UPDATE/DELETE. Devuelve filas afectadas."""
        if not self.conn:
            self.connect()
        try:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(command, params)
            else:
                cursor.execute(command)
            self.conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"{SimulatorLog.DRIVER} Error execute_command: {e}")
            raise

    def get_table_metadata(self, table_name: str) -> List[Dict[str, Any]]:
        """Devuelve metadatos de columnas para la tabla indicada."""
        cols = TABLE_COLUMNS.get(table_name.upper(), [])
        return [{"FIELD_NAME": c} for c in cols]

    # ─── Utilidades internas ─────────────────────────────────────────────────

    def _ensure_tables(self) -> None:
        """
        Crea las tablas SQLite si no existen e incorpora las columnas nuevas
        a tablas ya existentes (migración aditiva: nunca destruye datos).

        Regla: CREATE TABLE IF NOT EXISTS solo crea tablas nuevas; para tablas
        existentes usamos ALTER TABLE … ADD COLUMN, que SQLite ignora si la
        columna ya existe (lanza OperationalError → silenciado).
        """
        cursor = self.conn.cursor()

        # ── 1. Crear tablas nuevas ────────────────────────────────────────────
        for table in TABLE_CREATION_ORDER:
            ddl = TABLE_SCHEMAS.get(table, "")
            if ddl:
                cursor.execute(ddl)

        # ── 2. Migración aditiva de columnas (SOLO ADD COLUMN, jamás DROP) ───
        # Ampliar esta lista cuando se añadan columnas al esquema de tablas
        # existentes. Usar DEFAULT para todas (SQLite no permite NOT NULL sin DEFAULT
        # en ALTER TABLE).
        _COLUMN_MIGRATIONS: List[tuple] = [
            # (tabla, columna, definición SQLite)
            ("DOCCAB", "SERIE",       "TEXT DEFAULT 'A'"),
            ("DOCCAB", "ESTADOPEND",  "INTEGER DEFAULT 0"),
            ("DOCCAB", "CODPROYECTO", "TEXT DEFAULT NULL"),
        ]
        for table, col, col_def in _COLUMN_MIGRATIONS:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                logger.info(
                    f"{SimulatorLog.DRIVER} Migración: {table}.{col} añadida"
                )
            except sqlite3.OperationalError:
                pass  # Columna ya existe — estado esperado en la mayoría de ejecuciones

        # ── 3. Índices (idempotentes por CREATE … IF NOT EXISTS) ─────────────
        for indexes in TABLE_INDEXES.values():
            for idx in indexes:
                try:
                    cursor.execute(idx)
                except Exception:
                    pass  # Índice ya existe o tabla aún no tiene la columna

        self.conn.commit()

    def _handle_system_query(
        self, query: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        Responde a queries de sistema Firebird (RDB$RELATIONS, RDB$RELATION_FIELDS).
        Devuelve los metadatos de las tablas simuladas.
        """
        q = query.upper()

        # ── RDB$RELATIONS → lista de tablas ──────────────────────────────────
        if "RDB$RELATIONS" in q and "RDB$RELATION_FIELDS" not in q:
            logger.debug(f"{SimulatorLog.DRIVER} System query: lista de tablas")
            return [{"NAME": t, "TABLE_NAME": t} for t in _SIMULATED_TABLE_NAMES]

        # ── RDB$RELATION_FIELDS → columnas de una tabla ───────────────────────
        if "RDB$RELATION_FIELDS" in q:
            table_name = _extract_table_from_fields_query(query, params)
            cols = TABLE_COLUMNS.get(table_name.upper(), []) if table_name else []
            logger.debug(
                f"{SimulatorLog.DRIVER} System query: columnas de {table_name} "
                f"→ {len(cols)} campos"
            )
            return [{"FIELD_NAME": c, "F": c} for c in cols]

        logger.warning(f"{SimulatorLog.DRIVER} System query no reconocida: {query[:100]}")
        return []

    def get_row_count(self, table_name: str) -> int:
        """Devuelve el número de filas de una tabla simulada."""
        if not self.conn:
            self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row = cursor.fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def has_data(self) -> bool:
        """True si al menos DOCCAB tiene registros."""
        try:
            return self.get_row_count("DOCCAB") > 0
        except Exception:
            return False


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_table_from_fields_query(query: str, params: Optional[tuple]) -> Optional[str]:
    """
    Extrae el nombre de tabla de una query RDB$RELATION_FIELDS.
    Busca primero en params (formato paramétrico), luego en la cláusula WHERE.
    """
    if params and len(params) > 0:
        return str(params[0]).strip()

    # Buscar TRIM(RDB$RELATION_NAME) = 'TABLA' o RDB$RELATION_NAME = 'TABLA'
    patterns = [
        r"TRIM\s*\(\s*RDB\$RELATION_NAME\s*\)\s*=\s*'([^']+)'",
        r"RDB\$RELATION_NAME\s*=\s*'([^']+)'",
        r"TRIM\s*\(\s*RDB\$RELATION_NAME\s*\)\s*=\s*'([^']+)'",
    ]
    for pat in patterns:
        m = re.search(pat, query, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return None
