"""
firebird_sql_normalizer.py — Normalización determinista de SQL para Firebird 2.5

Principio: Todo lo que es predecible y tiene una regla fija → código determinista.
           Solo lo que requiere entender la intención → IA.

Correcciones (en orden de aplicación):
  1.  Comentarios SQL (-- y /* */)
  2.  Whitespace: multilínea → una línea
  3.  Punto y coma final
  4.  Backticks (MySQL)
  5.  Comillas dobles en identificadores
  6.  LIMIT/ROWS/TOP N → SELECT FIRST N
  7.  Añadir FIRST N si falta (no en agregaciones)
  8.  ILIKE → UPPER(col) LIKE UPPER(val)
  9.  LIKE → UPPER(col) LIKE UPPER(val)
  10. != → <>
  11. TRUE/FALSE → 'T'/'F'
  12. Funciones de fecha (NOW, GETDATE, SYSDATE, CURRENT_DATE(), CURRENT_TIMESTAMP())
  13. CONCAT(a,b) → a || b
  14. SUBSTRING(col,pos,len) → SUBSTRING(col FROM pos FOR len)
  15. OFFSET N → eliminar
  16. Columnas erróneas conocidas (STOCK → STOCKARTICULO, etc.)
  17. Alias con comillas dobles
  18. BLOB en GROUP BY/SELECT → eliminar/sustituir
  19. Patrón artículos más comprados sin JOIN → reescribir con JOIN DOCLIN

Constantes en: firebird_sql_constants.py (única fuente de verdad)
Autor: DEVIA System · v1.2.0
"""

import re
import logging
from typing import Tuple, List

from backend.modules.chat.firebird_sql_constants import (
    DEFAULT_FIRST_LIMIT,
    KNOWN_COLUMN_FIXES,
    BLOB_COLUMNS_BY_TABLE,
    BLOB_REPLACEMENT_COL,
    COLUMN_UNKNOWN_MAP,
    DATETIME_FIXES,
    AGGREGATE_FUNCTIONS,
)

logger = logging.getLogger(__name__)

# ─── Tipo alias ───────────────────────────────────────────────────────────────
Step = Tuple[str, List[str]]   # (sql_resultado, cambios_aplicados)


class FirebirdSQLNormalizer:
    """
    Normalizador determinista de SQL para Firebird 2.5.

    Uso:
        n = FirebirdSQLNormalizer()
        sql_ok, cambios = n.normalize(sql_bruto)
        # Post-error (sin IA):
        sql_ok, cambios = n.fix_after_error(sql_fallido, mensaje_error)
    """

    # ── Pipeline principal ────────────────────────────────────────────────────

    def normalize(self, sql: str) -> Step:
        """Aplica todas las normalizaciones deterministas en orden."""
        changes: List[str] = []
        steps = [
            self._remove_sql_comments,
            self._normalize_whitespace,
            self._remove_trailing_semicolon,
            self._remove_backticks,
            self._remove_double_quote_identifiers,
            self._fix_limit_to_first,
            self._add_first_if_missing,
            self._fix_ilike,
            self._fix_like_case_insensitive,
            self._fix_not_equal,
            self._fix_boolean_literals,
            self._fix_datetime_functions,
            self._fix_concat,
            self._fix_substring,
            self._remove_offset,
            self._fix_known_columns,
            self._fix_alias_quotes,
            self._fix_blob_in_groupby,
            self._fix_articulos_mas_compras,
        ]
        for step in steps:
            sql, c = step(sql)
            changes.extend(c)

        if changes:
            logger.info(f"[SQL NORMALIZER] ✅ {len(changes)} correcciones aplicadas")
            for ch in changes:
                logger.info(f"[SQL NORMALIZER]   • {ch}")
        else:
            logger.debug("[SQL NORMALIZER] ✓ SQL ya válido para Firebird 2.5")

        return sql.strip(), changes

    def fix_after_error(self, sql: str, error_message: str) -> Step:
        """
        Correcciones deterministas POST-ERROR basadas en el mensaje de Firebird.
        Evita una segunda llamada a la IA para errores conocidos.

        Errores manejados:
          - "conversion error from string BLOB" → eliminar BLOB de GROUP BY/SELECT
          - "Column unknown X"                  → mapear a columna correcta
          - "Token unknown LIMIT/TOP/ROWS"      → convertir a FIRST N
        """
        changes: List[str] = []
        err_up = error_message.upper()

        if "BLOB" in err_up and "CONVERSION" in err_up:
            sql, c = self._fix_blob_in_groupby(sql)
            changes.extend(c)
            if not changes:
                sql, c = self._fix_articulos_mas_compras(sql)
                changes.extend(c)
            return sql, changes

        if "COLUMN UNKNOWN" in err_up:
            m = re.search(r'Column unknown\s+(\w+)', error_message, re.IGNORECASE)
            if m:
                bad = m.group(1).upper()
                if bad in COLUMN_UNKNOWN_MAP:
                    good = COLUMN_UNKNOWN_MAP[bad]
                    new_sql = re.sub(rf'\b{bad}\b', good, sql, flags=re.IGNORECASE)
                    if new_sql != sql:
                        changes.append(f"Columna desconocida: {bad} → {good}")
                        return new_sql, changes

        if "TOKEN UNKNOWN" in err_up:
            sql, c = self._fix_limit_to_first(sql)
            changes.extend(c)

        return sql, changes

    # ── Pasos individuales ────────────────────────────────────────────────────

    def _remove_sql_comments(self, sql: str) -> Step:
        changes = []
        s = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        if s != sql:
            changes.append("Eliminados comentarios /* ... */")
            sql = s
        s = re.sub(r'--[^\n]*', ' ', sql)
        if s != sql:
            changes.append("Eliminados comentarios --")
            sql = s
        return sql, changes

    def _normalize_whitespace(self, sql: str) -> Step:
        s = re.sub(r'\s+', ' ', sql).strip()
        return s, (["SQL multilínea → una línea"] if s != sql.strip() else [])

    def _remove_trailing_semicolon(self, sql: str) -> Step:
        s = sql.rstrip(';').strip()
        return s, (["Eliminado punto y coma final"] if s != sql else [])

    def _remove_backticks(self, sql: str) -> Step:
        if '`' not in sql:
            return sql, []
        return sql.replace('`', ''), ["Eliminados backticks (MySQL → Firebird)"]

    def _remove_double_quote_identifiers(self, sql: str) -> Step:
        s = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"').sub(r'\1', sql)
        return s, (['Comillas dobles en identificadores eliminadas'] if s != sql else [])

    def _fix_limit_to_first(self, sql: str) -> Step:
        changes = []
        # LIMIT N
        m = re.search(r'\bLIMIT\s+(\d+)', sql, re.IGNORECASE)
        if m:
            v = m.group(1)
            sql = re.sub(r'\bLIMIT\s+\d+', '', sql, flags=re.IGNORECASE)
            if not re.search(r'\bSELECT\s+FIRST\s+\d+', sql, re.IGNORECASE):
                sql = re.sub(r'\bSELECT\s+', f'SELECT FIRST {v} ', sql, count=1, flags=re.IGNORECASE)
            changes.append(f"LIMIT {v} → SELECT FIRST {v}")
        # TOP N
        m = re.search(r'\bSELECT\s+TOP\s+(\d+)\s+', sql, re.IGNORECASE)
        if m:
            v = m.group(1)
            sql = re.sub(r'\bSELECT\s+TOP\s+\d+\s+', f'SELECT FIRST {v} ', sql, count=1, flags=re.IGNORECASE)
            changes.append(f"SELECT TOP {v} → SELECT FIRST {v}")
        # ROWS N
        m = re.search(r'\bROWS\s+(\d+)', sql, re.IGNORECASE)
        if m:
            v = m.group(1)
            sql = re.sub(r'\bROWS\s+\d+(\s+TO\s+\d+)?', '', sql, flags=re.IGNORECASE)
            if not re.search(r'\bSELECT\s+FIRST\s+\d+', sql, re.IGNORECASE):
                sql = re.sub(r'\bSELECT\s+', f'SELECT FIRST {v} ', sql, count=1, flags=re.IGNORECASE)
            changes.append(f"ROWS {v} → SELECT FIRST {v}")
        return sql, changes

    def _add_first_if_missing(self, sql: str) -> Step:
        up = sql.upper()
        if not up.lstrip().startswith('SELECT'):
            return sql, []
        if re.search(r'\bFIRST\s+\d+', up):
            return sql, []
        if any(re.search(rf'\b{a}\s*\(', up) for a in AGGREGATE_FUNCTIONS):
            return sql, []
        s = re.sub(r'^(\s*SELECT\s+)', f'SELECT FIRST {DEFAULT_FIRST_LIMIT} ',
                   sql, count=1, flags=re.IGNORECASE)
        return (s, [f"Añadido FIRST {DEFAULT_FIRST_LIMIT} automáticamente"]) if s != sql else (sql, [])

    def _fix_ilike(self, sql: str) -> Step:
        if not re.search(r'\bILIKE\b', sql, re.IGNORECASE):
            return sql, []
        s = re.compile(r'\b([a-zA-Z0-9_.]+)\s+ILIKE\s+(\'[^\']*\')', re.IGNORECASE).sub(
            lambda m: f"UPPER({m.group(1)}) LIKE UPPER({m.group(2)})", sql)
        return (s, ["ILIKE → UPPER(col) LIKE UPPER(val)"]) if s != sql else (sql, [])

    def _fix_like_case_insensitive(self, sql: str) -> Step:
        def _replace(m):
            col, val = m.group(1), m.group(2)
            return m.group(0) if col.upper().startswith('UPPER') else f"UPPER({col}) LIKE UPPER({val})"
        s = re.compile(r'\b(?<!UPPER\()([a-zA-Z0-9_.]+)\s+LIKE\s+(\'[^\']*\')',
                       re.IGNORECASE).sub(_replace, sql)
        return (s, ["LIKE → UPPER(col) LIKE UPPER(val)"]) if s != sql else (sql, [])

    def _fix_not_equal(self, sql: str) -> Step:
        if '!=' not in sql:
            return sql, []
        return sql.replace('!=', '<>'), ["!= → <>"]

    def _fix_boolean_literals(self, sql: str) -> Step:
        changes, s = [], sql
        t = re.sub(r'\bTRUE\b', "'T'", s, flags=re.IGNORECASE)
        if t != s:
            changes.append("TRUE → 'T'")
            s = t
        f = re.sub(r'\bFALSE\b', "'F'", s, flags=re.IGNORECASE)
        if f != s:
            changes.append("FALSE → 'F'")
            s = f
        return s, changes

    def _fix_datetime_functions(self, sql: str) -> Step:
        changes, s = [], sql
        for pattern, replacement, desc in DATETIME_FIXES:
            t = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
            if t != s:
                changes.append(desc)
                s = t
        return s, changes

    def _fix_concat(self, sql: str) -> Step:
        s = re.compile(r'\bCONCAT\s*\(\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)', re.IGNORECASE).sub(
            lambda m: f"({m.group(1).strip()} || {m.group(2).strip()})", sql)
        return (s, ["CONCAT(a,b) → a || b"]) if s != sql else (sql, [])

    def _fix_substring(self, sql: str) -> Step:
        s = re.compile(
            r'\bSUBSTRING\s*\(\s*([^,()]+?)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', re.IGNORECASE
        ).sub(lambda m: f"SUBSTRING({m.group(1).strip()} FROM {m.group(2)} FOR {m.group(3)})", sql)
        return (s, ["SUBSTRING(col,pos,len) → SUBSTRING(col FROM pos FOR len)"]) if s != sql else (sql, [])

    def _remove_offset(self, sql: str) -> Step:
        if not re.search(r'\bOFFSET\s+\d+', sql, re.IGNORECASE):
            return sql, []
        s = re.sub(r'\bOFFSET\s+\d+', '', sql, flags=re.IGNORECASE).strip()
        return s, ["OFFSET N eliminado (no soportado en Firebird 2.5)"]

    def _fix_known_columns(self, sql: str) -> Step:
        changes = []
        for pattern, replacement, desc in KNOWN_COLUMN_FIXES:
            s = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
            if s != sql:
                changes.append(f"Columna corregida: {desc}")
                sql = s
        return sql, changes

    def _fix_alias_quotes(self, sql: str) -> Step:
        s = re.compile(r'\bAS\s+"([^"]+)"', re.IGNORECASE).sub(r'AS \1', sql)
        return (s, ['AS "alias" → AS alias']) if s != sql else (sql, [])

    def _fix_blob_in_groupby(self, sql: str) -> Step:
        """
        Elimina columnas BLOB de GROUP BY y las sustituye en SELECT por NOMBRE.
        Firebird lanza "conversion error from string BLOB" en GROUP BY sobre BLOB.
        """
        changes = []
        if "GROUP BY" not in sql.upper():
            return sql, changes

        # Detectar tablas presentes en la query
        blob_cols: set = set()
        for tbl, cols in BLOB_COLUMNS_BY_TABLE.items():
            if re.search(rf'\b{tbl}\b', sql, re.IGNORECASE):
                blob_cols.update(cols)

        if not blob_cols:
            return sql, changes

        # ── Limpiar GROUP BY ──────────────────────────────────────────────────
        gb_m = re.search(r'\bGROUP\s+BY\s+(.+?)(?:\s+(?:ORDER|HAVING|UNION)\b|$)', sql, re.IGNORECASE)
        if not gb_m:
            gb_m = re.search(r'\bGROUP\s+BY\s+(.+)$', sql, re.IGNORECASE)

        if gb_m:
            gb_clause = gb_m.group(1).strip()
            gb_cols = [c.strip() for c in gb_clause.split(',')]
            clean_gb, removed = [], []
            for col in gb_cols:
                col_name = col.split('.')[-1].strip().upper()
                (removed if col_name in blob_cols else clean_gb).append(col)

            if removed:
                new_gb = ("GROUP BY " + ", ".join(clean_gb)) if clean_gb else ""
                sql = re.sub(r'\bGROUP\s+BY\s+' + re.escape(gb_clause), new_gb, sql, flags=re.IGNORECASE)
                changes.append(f"BLOB eliminado de GROUP BY: {', '.join(removed)}")

        # ── Limpiar SELECT ────────────────────────────────────────────────────
        sel_m = re.search(r'\bSELECT\s+(?:FIRST\s+\d+\s+)?(.+?)\s+FROM\b',
                          sql, re.IGNORECASE | re.DOTALL)
        if sel_m and "GROUP BY" in sql.upper():
            sel_str = sel_m.group(1).strip()
            sel_cols = [c.strip() for c in sel_str.split(',')]
            clean_sel, replaced = [], []
            for col in sel_cols:
                col_name = re.split(r'\bAS\b', col.split('.')[-1].strip(), flags=re.IGNORECASE)[0].strip().upper()
                if col_name in blob_cols:
                    prefix = (col.split('.')[0].strip() + '.') if '.' in col else ''
                    new_col = f"{prefix}{BLOB_REPLACEMENT_COL}"
                    clean_sel.append(new_col)
                    replaced.append(f"{col} → {new_col}")
                else:
                    clean_sel.append(col)

            if replaced:
                first_m = re.search(r'\bSELECT\s+(FIRST\s+\d+\s+)', sql, re.IGNORECASE)
                first_clause = first_m.group(1) if first_m else ""
                sql = re.sub(
                    r'\bSELECT\s+(?:FIRST\s+\d+\s+)?' + re.escape(sel_str),
                    f'SELECT {first_clause}{", ".join(clean_sel)}',
                    sql, count=1, flags=re.IGNORECASE
                )
                changes.append(f"BLOB en SELECT sustituido: {'; '.join(replaced)}")

        return sql, changes

    def _fix_articulos_mas_compras(self, sql: str) -> Step:
        """
        Detecta SELECT ... FROM ARTICULO GROUP BY ... ORDER BY COUNT(*) DESC sin JOIN
        y lo reescribe con JOIN DOCLIN para contar compras reales.
        """
        up = sql.upper()
        if not re.search(r'\bFROM\s+ARTICULO\b', up):
            return sql, []
        if "GROUP BY" not in up or not re.search(r'ORDER\s+BY\s+.*COUNT\s*\(\s*\*\s*\)', up):
            return sql, []
        if re.search(r'\bJOIN\s+(DOCLIN|DOCCAB)\b', up):
            return sql, []

        m = re.search(r'\bSELECT\s+FIRST\s+(\d+)\b', sql, re.IGNORECASE)
        n = m.group(1) if m else str(DEFAULT_FIRST_LIMIT)
        corrected = (
            f"SELECT FIRST {n} A.CODIGO, A.NOMBRE, COUNT(*) AS NCOMPRAS "
            f"FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO = A.CODIGO "
            f"GROUP BY A.CODIGO, A.NOMBRE ORDER BY NCOMPRAS DESC"
        )
        return corrected, ["Patrón 'artículos más comprados' → JOIN DOCLIN añadido (COUNT(*) real)"]
