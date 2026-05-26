"""
query_translator.py — Traductor de SQL Firebird a SQL SQLite.

Convierte la sintaxis específica de Firebird 2.5 a SQLite de forma determinista,
sin necesidad de IA. Se aplica antes de ejecutar cualquier query en el simulador.

Traducciones implementadas:
  • SELECT FIRST N              → SELECT … LIMIT N
  • EXTRACT(PART FROM x)        → CAST(strftime('%X', x) AS INTEGER)
  • CURRENT_DATE                → date('now')
  • CURRENT_TIMESTAMP           → datetime('now')
  • SUBSTRING(c FROM p FOR l)   → SUBSTR(c, p, l)
  • CAST(x AS DATE)             → date(x)
  • CAST(x AS TIMESTAMP)        → datetime(x)
  • CAST(x AS NUMERIC(p,s))     → ROUND(CAST(x AS REAL), s)
  • CAST(x AS NUMERIC)          → CAST(x AS REAL)
  • CAST(x AS VARCHAR(n))       → CAST(x AS TEXT)
  • col STARTING WITH 'x'       → col LIKE 'x%'
  • col CONTAINING 'x'          → col LIKE '%x%'
  • ORDER BY … NULLS LAST/FIRST → ORDER BY … (eliminado, SQLite no lo soporta)
  • RDB$RELATIONS/FIELDS        → interceptado en driver.py (no llega aquí)

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
import re
from typing import Tuple, List

from backend.modules.db_simulator.constants import SimulatorLog

logger = logging.getLogger(__name__)

# ─── Mapa EXTRACT part → formato strftime ────────────────────────────────────

_EXTRACT_FMT: dict = {
    "YEAR":   "%Y",
    "MONTH":  "%m",
    "DAY":    "%d",
    "HOUR":   "%H",
    "MINUTE": "%M",
    "SECOND": "%S",
}

# ─── Traductor principal ──────────────────────────────────────────────────────

class FirebirdToSQLiteTranslator:
    """
    Traduce SQL Firebird 2.5 a SQL SQLite compatible.
    Instanciar una vez (sin estado interno) y reutilizar.
    """

    def translate(self, sql: str) -> Tuple[str, List[str]]:
        """
        Ejecuta todas las traducciones en orden.

        Returns:
            (sql_traducido, lista_de_cambios_aplicados)
        """
        changes: List[str] = []

        sql, c = self._translate_first_to_limit(sql)
        changes.extend(c)

        sql, c = self._translate_extract(sql)
        changes.extend(c)

        sql, c = self._translate_current_datetime(sql)
        changes.extend(c)

        sql, c = self._translate_substring(sql)
        changes.extend(c)

        sql, c = self._translate_cast_date(sql)
        changes.extend(c)

        sql, c = self._translate_cast_numeric(sql)
        changes.extend(c)

        sql, c = self._translate_cast_varchar(sql)
        changes.extend(c)

        sql, c = self._translate_starting_with(sql)
        changes.extend(c)

        sql, c = self._translate_containing(sql)
        changes.extend(c)

        sql, c = self._translate_nulls_order(sql)
        changes.extend(c)

        sql, c = self._translate_trim_rdb(sql)
        changes.extend(c)

        if changes:
            logger.debug(
                f"{SimulatorLog.TRANSLATE} {len(changes)} traducciones aplicadas: "
                f"{', '.join(changes)}"
            )
        return sql, changes

    # ── SELECT FIRST N → SELECT … LIMIT N ────────────────────────────────────

    def _translate_first_to_limit(self, sql: str) -> Tuple[str, List[str]]:
        """
        SELECT [DISTINCT] FIRST N … → SELECT [DISTINCT] … LIMIT N

        Firebird coloca FIRST después de SELECT; SQLite usa LIMIT al final.
        """
        pattern = re.compile(
            r'\bSELECT\s+(DISTINCT\s+)?FIRST\s+(\d+)\s+',
            re.IGNORECASE
        )
        match = pattern.search(sql)
        if not match:
            return sql, []

        n           = match.group(2)
        distinct    = (match.group(1) or "").strip()
        replacement = f"SELECT {distinct + ' ' if distinct else ''}"
        sql = pattern.sub(replacement, sql, count=1)

        # Añadir LIMIT al final (antes de ';' si existe)
        sql = sql.rstrip()
        if sql.endswith(";"):
            sql = sql[:-1].rstrip() + f" LIMIT {n};"
        else:
            sql = sql + f" LIMIT {n}"

        return sql, [f"FIRST {n} → LIMIT {n}"]

    # ── EXTRACT(PART FROM col) → CAST(strftime('%X', col) AS INTEGER) ─────────

    def _translate_extract(self, sql: str) -> Tuple[str, List[str]]:
        """
        EXTRACT(MONTH FROM FECHA) → CAST(strftime('%m', FECHA) AS INTEGER)
        """
        pattern = re.compile(
            r'\bEXTRACT\s*\(\s*(\w+)\s+FROM\s+([^)]+?)\s*\)',
            re.IGNORECASE
        )
        changes: List[str] = []

        def _replacer(m: re.Match) -> str:
            part = m.group(1).upper()
            col  = m.group(2).strip()
            fmt  = _EXTRACT_FMT.get(part)
            if fmt:
                changes.append(f"EXTRACT({part}) → strftime('{fmt}')")
                return f"CAST(strftime('{fmt}', {col}) AS INTEGER)"
            # Parte no reconocida: dejar como está
            return m.group(0)

        sql = pattern.sub(_replacer, sql)
        return sql, changes

    # ── CURRENT_DATE / CURRENT_TIMESTAMP ──────────────────────────────────────

    def _translate_current_datetime(self, sql: str) -> Tuple[str, List[str]]:
        changes: List[str] = []

        new_sql = re.sub(r'\bCURRENT_TIMESTAMP\b', "datetime('now')", sql, flags=re.IGNORECASE)
        if new_sql != sql:
            changes.append("CURRENT_TIMESTAMP → datetime('now')")
        sql = new_sql

        new_sql = re.sub(r'\bCURRENT_DATE\b', "date('now')", sql, flags=re.IGNORECASE)
        if new_sql != sql:
            changes.append("CURRENT_DATE → date('now')")
        sql = new_sql

        return sql, changes

    # ── SUBSTRING(col FROM p FOR l) → SUBSTR(col, p, l) ──────────────────────

    def _translate_substring(self, sql: str) -> Tuple[str, List[str]]:
        pattern = re.compile(
            r'\bSUBSTRING\s*\(\s*(.+?)\s+FROM\s+(\d+)\s+FOR\s+(\d+)\s*\)',
            re.IGNORECASE
        )
        changes: List[str] = []

        def _replacer(m: re.Match) -> str:
            changes.append("SUBSTRING…FROM…FOR → SUBSTR")
            return f"SUBSTR({m.group(1).strip()}, {m.group(2)}, {m.group(3)})"

        sql = pattern.sub(_replacer, sql)
        return sql, changes

    # ── CAST(x AS DATE) → date(x) ─────────────────────────────────────────────

    def _translate_cast_date(self, sql: str) -> Tuple[str, List[str]]:
        """
        SQLite no tiene tipo DATE; date() es la función equivalente.
        Solo aplica a CAST AS DATE/TIMESTAMP, no a otros tipos.
        """
        changes: List[str] = []

        pattern_date = re.compile(r'\bCAST\s*\((.+?)\s+AS\s+DATE\s*\)', re.IGNORECASE)
        new_sql = pattern_date.sub(
            lambda m: (changes.append("CAST AS DATE → date()") or f"date({m.group(1).strip()})"),
            sql
        )
        sql = new_sql

        pattern_ts = re.compile(r'\bCAST\s*\((.+?)\s+AS\s+TIMESTAMP\s*\)', re.IGNORECASE)
        new_sql = pattern_ts.sub(
            lambda m: (changes.append("CAST AS TIMESTAMP → datetime()") or f"datetime({m.group(1).strip()})"),
            sql
        )
        sql = new_sql

        return sql, changes

    # ── CAST(x AS NUMERIC(p,s)) → ROUND(CAST(x AS REAL), s) ─────────────────

    def _translate_cast_numeric(self, sql: str) -> Tuple[str, List[str]]:
        """
        SQLite no tiene NUMERIC(p,s). Conversiones:
          CAST(x AS NUMERIC(p,s)) → ROUND(CAST(x AS REAL), s)
          CAST(x AS NUMERIC(p))   → CAST(x AS REAL)
          CAST(x AS NUMERIC)      → CAST(x AS REAL)
          CAST(x AS DECIMAL(p,s)) → igual que NUMERIC
        """
        changes: List[str] = []

        # NUMERIC(p,s) o DECIMAL(p,s) con dos parámetros
        pat_ps = re.compile(
            r'\bCAST\s*\((.+?)\s+AS\s+(?:NUMERIC|DECIMAL)\s*\(\s*\d+\s*,\s*(\d+)\s*\)\s*\)',
            re.IGNORECASE
        )
        def _rep_ps(m: re.Match) -> str:
            changes.append(f"CAST AS NUMERIC(p,s) → ROUND(CAST AS REAL, {m.group(2)})")
            return f"ROUND(CAST({m.group(1).strip()} AS REAL), {m.group(2)})"
        sql = pat_ps.sub(_rep_ps, sql)

        # NUMERIC(p) o DECIMAL(p) con un parámetro, o sin parámetros
        pat_n = re.compile(
            r'\bCAST\s*\((.+?)\s+AS\s+(?:NUMERIC|DECIMAL)(?:\s*\(\s*\d+\s*\))?\s*\)',
            re.IGNORECASE
        )
        def _rep_n(m: re.Match) -> str:
            changes.append("CAST AS NUMERIC → CAST AS REAL")
            return f"CAST({m.group(1).strip()} AS REAL)"
        sql = pat_n.sub(_rep_n, sql)

        return sql, changes

    # ── CAST(x AS VARCHAR(n)) → CAST(x AS TEXT) ──────────────────────────────

    def _translate_cast_varchar(self, sql: str) -> Tuple[str, List[str]]:
        """
        SQLite no tiene tipos VARCHAR(n) ni CHAR(n).
          CAST(x AS VARCHAR(n)) → CAST(x AS TEXT)
          CAST(x AS CHAR(n))    → CAST(x AS TEXT)
        """
        changes: List[str] = []
        pattern = re.compile(
            r'\bCAST\s*\((.+?)\s+AS\s+(?:VARCHAR|CHAR)\s*(?:\(\s*\d+\s*\))?\s*\)',
            re.IGNORECASE
        )
        def _rep(m: re.Match) -> str:
            changes.append("CAST AS VARCHAR/CHAR → CAST AS TEXT")
            return f"CAST({m.group(1).strip()} AS TEXT)"
        sql = pattern.sub(_rep, sql)
        return sql, changes

    # ── col STARTING WITH 'x' → col LIKE 'x%' ────────────────────────────────

    def _translate_starting_with(self, sql: str) -> Tuple[str, List[str]]:
        """
        Operador Firebird-only.
          col STARTING WITH 'abc' → col LIKE 'abc%'

        Solo traduce literales de cadena (el caso habitual generado por Qwen3).
        Para parámetros posicionales (?), el LIKE con concatenación puede dar
        problemas, así que se omite esa variante.
        """
        changes: List[str] = []
        pattern = re.compile(
            r"\bSTARTING\s+WITH\s+'([^']*)'",
            re.IGNORECASE
        )
        def _rep(m: re.Match) -> str:
            changes.append(f"STARTING WITH '{m.group(1)}' → LIKE '{m.group(1)}%'")
            return f"LIKE '{m.group(1)}%'"
        sql = pattern.sub(_rep, sql)
        return sql, changes

    # ── col CONTAINING 'x' → col LIKE '%x%' ──────────────────────────────────

    def _translate_containing(self, sql: str) -> Tuple[str, List[str]]:
        """
        Operador Firebird-only (búsqueda de subcadena, case-insensitive en Firebird).
          col CONTAINING 'abc' → col LIKE '%abc%'

        Nota: Firebird CONTAINING es case-insensitive; SQLite LIKE también lo es
        para caracteres ASCII. El comportamiento es equivalente.
        """
        changes: List[str] = []
        pattern = re.compile(
            r"\bCONTAINING\s+'([^']*)'",
            re.IGNORECASE
        )
        def _rep(m: re.Match) -> str:
            changes.append(f"CONTAINING '{m.group(1)}' → LIKE '%{m.group(1)}%'")
            return f"LIKE '%{m.group(1)}%'"
        sql = pattern.sub(_rep, sql)
        return sql, changes

    # ── ORDER BY col NULLS LAST/FIRST → ORDER BY col ─────────────────────────

    def _translate_nulls_order(self, sql: str) -> Tuple[str, List[str]]:
        """
        SQLite no soporta NULLS LAST / NULLS FIRST en ORDER BY.
        Eliminar la cláusula: SQLite por defecto pone NULLs primero en ASC,
        últimos en DESC — comportamiento suficiente para la mayoría de queries.
        """
        changes: List[str] = []
        pattern = re.compile(r'\s+NULLS\s+(?:LAST|FIRST)\b', re.IGNORECASE)
        new_sql = pattern.sub('', sql)
        if new_sql != sql:
            changes.append("NULLS LAST/FIRST → eliminado (no soportado en SQLite)")
        return new_sql, changes

    # ── TRIM(RDB$…) — limpieza residual de tokens de sistema ─────────────────

    def _translate_trim_rdb(self, sql: str) -> Tuple[str, List[str]]:
        """
        Elimina TRIM() alrededor de nombres RDB$ que pudieran escapar
        al interceptor de system queries del driver.
        Solo actúa si queda algún RDB$ sin interceptar.
        """
        if "RDB$" not in sql.upper():
            return sql, []
        # Si llega aquí es porque el driver no interceptó la query → aviso
        logger.warning(f"{SimulatorLog.TRANSLATE} Query con RDB$ no interceptada: {sql[:80]}")
        return sql, []


# ─── Singleton exportable ─────────────────────────────────────────────────────

_translator = FirebirdToSQLiteTranslator()


def translate_firebird_sql(sql: str) -> Tuple[str, List[str]]:
    """
    Función de conveniencia: traduce SQL Firebird → SQLite.

    Returns:
        (sql_traducido, cambios_aplicados)
    """
    return _translator.translate(sql)
