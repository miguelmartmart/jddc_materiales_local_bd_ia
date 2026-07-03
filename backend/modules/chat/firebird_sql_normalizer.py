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
  20. DOCLIN.FECHA / L.FECHA → JOIN DOCCAB para obtener fecha del documento
  21. Funciones no soportadas en FB 2.5: ROUND→CAST, NVL/IFNULL/ISNULL→COALESCE,
      TRUNC/TRUNCATE→CAST
  22. LEFT JOIN + WHERE en tabla derecha → convierte implícitamente en INNER JOIN.
      Detecta y advierte. Para DOCDESTINO: reescribe con COUNT(DISTINCT) correcto.

Constantes en: firebird_sql_constants.py (única fuente de verdad)
Autor: DEVIA System · v1.4.0
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
    TABLE_DATE_COLUMNS,
    UNSUPPORTED_FUNCTIONS,
    RELATION_TABLE_JOIN_INFO,
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
            self._fix_doclin_fecha_join_doccab,      # paso 20
            self._fix_unsupported_functions,          # paso 21
            self._fix_left_join_where_killer,         # paso 22
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
            # Extraer columna desconocida — puede ser "FECHA", "L.FECHA", "L", etc.
            # Firebird puede reportar el nombre con o sin prefijo de tabla
            m = re.search(r'Column unknown\s+([\w.]+)', error_message, re.IGNORECASE)
            if m:
                bad_raw = m.group(1).strip()
                # Extraer solo el nombre de columna (sin prefijo de tabla)
                bad = bad_raw.split('.')[-1].upper()

                # Caso especial: FECHA en DOCLIN → necesita JOIN DOCCAB
                # Detectar si el error menciona FECHA (con o sin prefijo alias)
                is_fecha_error = (
                    bad == "FECHA" or
                    "FECHA" in bad_raw.upper() or
                    re.search(r'\bL\.FECHA\b', error_message, re.IGNORECASE) or
                    re.search(r'\bDOCLIN\.FECHA\b', error_message, re.IGNORECASE)
                )
                if is_fecha_error and re.search(r'\bDOCLIN\b', sql, re.IGNORECASE):
                    fixed, c = self._fix_doclin_fecha_join_doccab(sql)
                    if c:
                        changes.extend(c)
                        return fixed, changes

                if bad in COLUMN_UNKNOWN_MAP:
                    good = COLUMN_UNKNOWN_MAP[bad]
                    if good == "__NEEDS_JOIN_DOCCAB__":
                        # Señal especial: intentar fix de JOIN DOCCAB
                        fixed, c = self._fix_doclin_fecha_join_doccab(sql)
                        if c:
                            changes.extend(c)
                            return fixed, changes
                    else:
                        new_sql = re.sub(rf'\b{bad}\b', good, sql, flags=re.IGNORECASE)
                        if new_sql != sql:
                            changes.append(f"Columna desconocida: {bad} → {good}")
                            return new_sql, changes

        if "TOKEN UNKNOWN" in err_up:
            sql, c = self._fix_limit_to_first(sql)
            changes.extend(c)

        # "Function unknown ROUND/NVL/TRUNC/..." → corrección determinista
        if "FUNCTION UNKNOWN" in err_up:
            sql, c = self._fix_unsupported_functions(sql)
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

    def _fix_doclin_fecha_join_doccab(self, sql: str) -> Step:
        """
        Paso 20: DOCLIN no tiene columna FECHA.
        La fecha del documento está en DOCCAB.FECHA (JOIN por CODDOCUMENTO).

        Detecta queries que usan DOCLIN (o alias L) con referencias a FECHA
        y añade JOIN DOCCAB C ON C.CODIGO = L.CODDOCUMENTO, sustituyendo
        L.FECHA / DOCLIN.FECHA por C.FECHA en toda la query.

        Casos detectados:
          - L.FECHA, DOCLIN.FECHA en WHERE/SELECT/ORDER BY
          - EXTRACT(... FROM L.FECHA), EXTRACT(... FROM DOCLIN.FECHA)
        """
        up = sql.upper()

        # Solo actuar si hay DOCLIN en la query
        if not re.search(r'\bDOCLIN\b', up):
            return sql, []

        # Detectar si hay referencia a FECHA en contexto de DOCLIN
        # Patrones: L.FECHA, DOCLIN.FECHA, o simplemente FECHA cuando DOCLIN está presente
        has_doclin_fecha = bool(
            re.search(r'\bL\.FECHA\b', up) or
            re.search(r'\bDOCLIN\.FECHA\b', up) or
            re.search(r'\bFECHA\b', up)  # FECHA genérica cuando DOCLIN está presente
        )

        if not has_doclin_fecha:
            return sql, []

        # Si ya tiene JOIN DOCCAB, solo sustituir referencias de fecha
        already_has_doccab = bool(re.search(r'\bDOCCAB\b', up))

        changes = []

        if not already_has_doccab:
            # Detectar alias de DOCLIN (ej: DOCLIN L, DOCLIN AS L)
            alias_m = re.search(r'\bDOCLIN\s+(?:AS\s+)?(\w+)\b', sql, re.IGNORECASE)
            doclin_alias = alias_m.group(1) if alias_m else "L"

            # Añadir JOIN DOCCAB C ON C.CODIGO = {alias}.CODDOCUMENTO
            # Buscar el FROM DOCLIN ... y añadir el JOIN después
            join_clause = f" JOIN DOCCAB C ON C.CODIGO = {doclin_alias}.CODDOCUMENTO"

            # Insertar el JOIN después de la cláusula FROM ... DOCLIN [alias]
            # Patrón: FROM ... DOCLIN [alias] [WHERE|GROUP|ORDER|JOIN]
            from_pattern = re.compile(
                r'(\bFROM\b.+?\bDOCLIN\b(?:\s+(?:AS\s+)?\w+)?)',
                re.IGNORECASE | re.DOTALL
            )
            m = from_pattern.search(sql)
            if m:
                insert_pos = m.end()
                # No insertar si ya hay un JOIN inmediatamente después
                rest = sql[insert_pos:].lstrip()
                if not rest.upper().startswith('JOIN') and not rest.upper().startswith('INNER') and not rest.upper().startswith('LEFT'):
                    sql = sql[:insert_pos] + join_clause + sql[insert_pos:]
                    changes.append(f"JOIN DOCCAB C añadido (DOCLIN no tiene FECHA, fecha está en DOCCAB.FECHA)")
            else:
                # Fallback: añadir antes del WHERE
                where_m = re.search(r'\bWHERE\b', sql, re.IGNORECASE)
                if where_m:
                    sql = sql[:where_m.start()] + join_clause + " " + sql[where_m.start():]
                    changes.append(f"JOIN DOCCAB C añadido antes de WHERE (DOCLIN.FECHA → DOCCAB.FECHA)")

        # Sustituir referencias de fecha: L.FECHA → C.FECHA, DOCLIN.FECHA → C.FECHA
        fecha_alias = "C"
        sql_new = re.sub(r'\bL\.FECHA\b', f'{fecha_alias}.FECHA', sql, flags=re.IGNORECASE)
        if sql_new != sql:
            changes.append(f"L.FECHA → {fecha_alias}.FECHA (fecha en DOCCAB)")
            sql = sql_new

        sql_new = re.sub(r'\bDOCLIN\.FECHA\b', f'{fecha_alias}.FECHA', sql, flags=re.IGNORECASE)
        if sql_new != sql:
            changes.append(f"DOCLIN.FECHA → {fecha_alias}.FECHA (fecha en DOCCAB)")
            sql = sql_new

        # Si hay FECHA genérica sin prefijo de tabla en WHERE/EXTRACT y DOCCAB ya está,
        # prefijamos con C. para evitar ambigüedad
        if already_has_doccab or changes:
            # Solo prefijamos FECHA sin prefijo de tabla (no L.FECHA ni C.FECHA ya corregidas)
            sql_new = re.sub(
                r'(?<![A-Za-z0-9_.])FECHA(?!\s*\w)',  # FECHA no precedida ni seguida de identificador
                f'{fecha_alias}.FECHA',
                sql,
                flags=re.IGNORECASE
            )
            if sql_new != sql and sql_new != sql:
                changes.append(f"FECHA → {fecha_alias}.FECHA (prefijo tabla añadido)")
                sql = sql_new

        if changes:
            logger.info(f"[SQL NORMALIZER paso 20] DOCLIN.FECHA → JOIN DOCCAB: {changes}")

        return sql, changes

    # ── Utilidades internas ───────────────────────────────────────────────────

    @staticmethod
    def _find_matching_paren(s: str, open_pos: int) -> int:
        """
        Dado el índice del '(' de apertura en s, devuelve el índice del ')'
        de cierre correspondiente (con paréntesis balanceados).
        Devuelve -1 si no se encuentra.
        """
        depth = 0
        i = open_pos
        while i < len(s):
            if s[i] == '(':
                depth += 1
            elif s[i] == ')':
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    @staticmethod
    def _split_top_level_args(inner: str) -> List[str]:
        """
        Divide los argumentos de una función al nivel 0 de paréntesis.
        Ej: "(COUNT(A) * 100.0) / COUNT(B), 2" → ["(COUNT(A) * 100.0) / COUNT(B)", "2"]
        """
        args: List[str] = []
        depth = 0
        current: List[str] = []
        for ch in inner:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            args.append(''.join(current).strip())
        return args

    def _replace_function_calls(
        self,
        sql: str,
        func_name: str,
        replacer,  # callable(args: List[str]) -> str
    ) -> str:
        """
        Reemplaza todas las llamadas a func_name(...) en sql usando replacer.
        Maneja paréntesis anidados a cualquier profundidad.

        replacer recibe la lista de argumentos al nivel 0 y devuelve el
        string de reemplazo. Si replacer devuelve None, no se reemplaza.
        """
        result = []
        i = 0
        pattern = re.compile(r'\b' + re.escape(func_name) + r'\s*\(', re.IGNORECASE)
        while i < len(sql):
            m = pattern.search(sql, i)
            if not m:
                result.append(sql[i:])
                break
            # Añadir texto antes de la función
            result.append(sql[i:m.start()])
            # Encontrar el paréntesis de cierre
            open_pos = m.end() - 1  # posición del '('
            close_pos = self._find_matching_paren(sql, open_pos)
            if close_pos == -1:
                # Paréntesis no balanceado → dejar sin cambios
                result.append(sql[m.start():])
                i = len(sql)
                break
            # Extraer contenido entre paréntesis
            inner = sql[open_pos + 1:close_pos]
            args = self._split_top_level_args(inner)
            replacement = replacer(args)
            if replacement is not None:
                result.append(replacement)
            else:
                result.append(sql[m.start():close_pos + 1])
            i = close_pos + 1
        return ''.join(result)

    def _fix_unsupported_functions(self, sql: str) -> Step:
        """
        Paso 21: Reemplaza funciones no soportadas en Firebird 2.5.

        Firebird 2.5 NO tiene:
          - ROUND(x, n)       → CAST(x AS NUMERIC(15, n))
                                Para n=0: CAST(x AS INTEGER)
                                Para n=1: CAST(x AS NUMERIC(15,1))
                                Para n=2: CAST(x AS NUMERIC(15,2))  ← caso más común
          - TRUNC(x) / TRUNCATE(x,n) → CAST(x AS INTEGER)
          - NVL(a, b)         → COALESCE(a, b)
          - IFNULL(a, b)      → COALESCE(a, b)
          - ISNULL(a, b)      → COALESCE(a, b)

        Firebird 3.0+ sí tiene ROUND(), pero la BD objetivo es 2.5.

        Estrategia ROUND:
          ROUND(expr, n) → CAST(expr AS NUMERIC(15, n))
          ROUND(expr)    → CAST(expr AS INTEGER)   [sin segundo argumento]

        Usa _replace_function_calls() que maneja paréntesis anidados a cualquier
        profundidad (CASE WHEN ... IN (12,13) THEN ... END, subqueries, etc.)
        """
        changes: List[str] = []
        s = sql

        # ── ROUND(expr, n) / ROUND(expr) ─────────────────────────────────────
        def _round_replacer(args: List[str]) -> str:
            if not args:
                return "CAST(0 AS INTEGER)"
            expr = args[0].strip()
            if len(args) >= 2:
                n_str = args[1].strip()
                try:
                    n = int(n_str)
                    if n == 0:
                        return f"CAST({expr} AS INTEGER)"
                    return f"CAST({expr} AS NUMERIC(15,{n}))"
                except ValueError:
                    return f"CAST({expr} AS NUMERIC(15,2))"
            else:
                return f"CAST({expr} AS INTEGER)"

        new_s = self._replace_function_calls(s, "ROUND", _round_replacer)
        if new_s != s:
            changes.append("ROUND(x,n) → CAST(x AS NUMERIC(15,n)) [Firebird 2.5 no tiene ROUND]")
            s = new_s

        # ── TRUNC(x) / TRUNCATE(x, n) → CAST(x AS INTEGER) ──────────────────
        def _trunc_replacer(args: List[str]) -> str:
            expr = args[0].strip() if args else "0"
            return f"CAST({expr} AS INTEGER)"

        new_s = self._replace_function_calls(s, "TRUNCATE", _trunc_replacer)
        if new_s != s:
            changes.append("TRUNCATE(x) → CAST(x AS INTEGER) [Firebird 2.5]")
            s = new_s

        new_s = self._replace_function_calls(s, "TRUNC", _trunc_replacer)
        if new_s != s:
            changes.append("TRUNC(x) → CAST(x AS INTEGER) [Firebird 2.5]")
            s = new_s

        # ── NVL(a, b) → COALESCE(a, b) ───────────────────────────────────────
        def _nvl_replacer(args: List[str]) -> str:
            if len(args) >= 2:
                return f"COALESCE({args[0].strip()}, {args[1].strip()})"
            return None  # no reemplazar si no hay 2 args

        new_s = self._replace_function_calls(s, "NVL", _nvl_replacer)
        if new_s != s:
            changes.append("NVL(a,b) → COALESCE(a,b) [Firebird 2.5]")
            s = new_s

        # ── IFNULL(a, b) → COALESCE(a, b) ────────────────────────────────────
        new_s = self._replace_function_calls(s, "IFNULL", _nvl_replacer)
        if new_s != s:
            changes.append("IFNULL(a,b) → COALESCE(a,b) [Firebird 2.5]")
            s = new_s

        # ── ISNULL(a, b) → COALESCE(a, b) ────────────────────────────────────
        new_s = self._replace_function_calls(s, "ISNULL", _nvl_replacer)
        if new_s != s:
            changes.append("ISNULL(a,b) → COALESCE(a,b) [Firebird 2.5]")
            s = new_s

        # ── CAST(x AS TEXT) → CAST(x AS VARCHAR(100)) ────────────────────────
        # Firebird 2.5 no tiene tipo TEXT. VARCHAR(100) es equivalente seguro.
        import re as _re
        new_s = _re.sub(r'\bAS\s+TEXT\b', 'AS VARCHAR(100)', s, flags=_re.IGNORECASE)
        if new_s != s:
            changes.append("CAST(x AS TEXT) → CAST(x AS VARCHAR(100)) [Firebird 2.5 no tiene TEXT]")
            s = new_s

        if changes:
            logger.info(f"[SQL NORMALIZER paso 21] Funciones no soportadas corregidas: {changes}")

        return s, changes

    def _fix_left_join_where_killer(self, sql: str) -> Step:
        """
        Paso 22: Detecta el patrón LEFT JOIN + WHERE en tabla derecha que convierte
        implícitamente el LEFT JOIN en INNER JOIN, eliminando filas sin match.

        PROBLEMA CLÁSICO:
          SELECT c.CODIGO, COUNT(dd.CODDOCUMENTO) AS ACEPTADOS
          FROM DOCCAB c
          LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
          LEFT JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO
          WHERE c.TIPO = 0
          AND d.TIPO IN (12, 13)   ← ❌ KILLER: d es tabla derecha del LEFT JOIN
                                      NULL IN (12,13) = FALSE → elimina filas sin destino

        SOLUCIÓN DETERMINISTA para DOCDESTINO (tasa de éxito):
          Reescribir con COUNT(DISTINCT) sobre DOCDESTINO directamente.
          No necesita JOIN a la tabla destino para contar presupuestos aceptados.

        SOLUCIÓN GENERAL (otros casos):
          Añadir advertencia en los cambios para que el usuario sepa que el SQL
          puede devolver 0 resultados si no hay matches en la tabla derecha.
          No reescribir automáticamente (demasiado arriesgado sin contexto).

        RIESGOS SIMILARES detectados:
          - LEFT JOIN tabla2 ON ... WHERE tabla2.col = valor
          - LEFT JOIN tabla2 ON ... WHERE tabla2.col IS NOT NULL
          - LEFT JOIN tabla2 ON ... WHERE tabla2.col IN (...)
          - LEFT JOIN tabla2 ON ... WHERE tabla2.col > N
        """
        changes: List[str] = []
        up = sql.upper()

        # Solo actuar si hay LEFT JOIN
        if not re.search(r'\bLEFT\s+(?:OUTER\s+)?JOIN\b', up):
            return sql, []

        # ── Caso especial: DOCDESTINO con tasa de éxito ───────────────────────
        # Detectar: LEFT JOIN DOCDESTINO + LEFT JOIN DOCCAB d + WHERE d.TIPO IN (...)
        # Este es el bug exacto que causó "0 presupuestos aceptados"
        has_docdestino_left = bool(re.search(
            r'\bLEFT\s+(?:OUTER\s+)?JOIN\s+DOCDESTINO\b', up
        ))
        has_doccab_double = bool(re.search(
            r'\bLEFT\s+(?:OUTER\s+)?JOIN\s+DOCCAB\b', up
        ))
        has_tipo_filter_on_right = bool(
            re.search(r'\bWHERE\b.+\b\w\s*\.\s*TIPO\s+IN\b', up, re.DOTALL) or
            re.search(r'\bAND\b.+\b\w\s*\.\s*TIPO\s+IN\b', up, re.DOTALL) or
            re.search(r'\bWHERE\b.+\b\w\s*\.\s*TIPO\s*=\s*\d', up, re.DOTALL) or
            re.search(r'\bAND\b.+\b\w\s*\.\s*TIPO\s*=\s*\d', up, re.DOTALL)
        )

        if has_docdestino_left and has_doccab_double and has_tipo_filter_on_right:
            # Reescribir con la SQL canónica de tasa de éxito desde RELATION_TABLE_JOIN_INFO
            info = RELATION_TABLE_JOIN_INFO.get("DOCDESTINO", {})
            canonical_sql = info.get("tasa_sql", "")
            if canonical_sql:
                changes.append(
                    "⚠️ PASO 22 — LEFT JOIN killer detectado: LEFT JOIN DOCDESTINO + WHERE d.TIPO IN (...) "
                    "convierte LEFT JOIN en INNER JOIN implícito → 0 presupuestos sin destino contados. "
                    "Reescrito con COUNT(DISTINCT) canónico para tasa de éxito."
                )
                logger.warning(
                    "[SQL NORMALIZER paso 22] LEFT JOIN killer DOCDESTINO detectado y corregido. "
                    "SQL original devolvería 0 aceptados. Reescrito con tasa canónica."
                )
                return canonical_sql, changes

        # ── Caso general: LEFT JOIN + WHERE en tabla derecha ──────────────────
        # Detectar alias de tablas en LEFT JOIN
        left_join_aliases: List[str] = []
        for m in re.finditer(
            r'\bLEFT\s+(?:OUTER\s+)?JOIN\s+\w+\s+(?:AS\s+)?(\w+)\b',
            sql, re.IGNORECASE
        ):
            alias = m.group(1).upper()
            # Excluir palabras clave SQL
            if alias not in ('ON', 'WHERE', 'AND', 'OR', 'SET', 'BY', 'AS'):
                left_join_aliases.append(alias)

        if not left_join_aliases:
            return sql, changes

        # Buscar WHERE/AND con condiciones sobre alias de tabla derecha
        # Patrón: alias.columna = valor / alias.columna IN (...) / alias.columna IS NOT NULL
        where_m = re.search(r'\bWHERE\b(.+)$', sql, re.IGNORECASE | re.DOTALL)
        if not where_m:
            return sql, changes

        where_clause = where_m.group(1)
        killer_found = False
        for alias in left_join_aliases:
            # Buscar condiciones que filtran sobre el alias de la tabla derecha
            # Excluir IS NULL (que es válido con LEFT JOIN para "no tiene")
            killer_patterns = [
                rf'\b{alias}\s*\.\s*\w+\s+IN\s*\(',
                rf'\b{alias}\s*\.\s*\w+\s*=\s*',
                rf'\b{alias}\s*\.\s*\w+\s*<>\s*',
                rf'\b{alias}\s*\.\s*\w+\s+IS\s+NOT\s+NULL',
                rf'\b{alias}\s*\.\s*\w+\s*>\s*',
                rf'\b{alias}\s*\.\s*\w+\s*<\s*',
            ]
            for pat in killer_patterns:
                if re.search(pat, where_clause, re.IGNORECASE):
                    killer_found = True
                    changes.append(
                        f"⚠️ PASO 22 — LEFT JOIN killer detectado: alias '{alias}' (tabla derecha) "
                        f"aparece en WHERE con condición de filtro. "
                        f"Esto convierte el LEFT JOIN en INNER JOIN implícito: "
                        f"filas sin match en '{alias}' serán eliminadas (NULL no pasa el filtro). "
                        f"Si quieres incluir filas sin match, mueve la condición al ON del JOIN "
                        f"o usa: AND ({alias}.col = valor OR {alias}.col IS NULL)."
                    )
                    logger.warning(
                        f"[SQL NORMALIZER paso 22] LEFT JOIN killer detectado: alias '{alias}' "
                        f"en WHERE. SQL puede devolver 0 resultados si no hay matches."
                    )
                    break
            if killer_found:
                break

        return sql, changes
