"""
FirebirdSQLNormalizer — Normalización determinista de SQL para Firebird 2.5

Este módulo aplica TODAS las correcciones que se pueden hacer de forma determinista
(por código, sin IA) antes de enviar el SQL a Firebird.

Principio: Todo lo que es predecible y tiene una regla fija → código determinista.
           Solo lo que requiere entender la intención → IA.

Correcciones aplicadas (en orden):
  1.  Eliminar comentarios SQL (-- y /* */)
  2.  Normalizar whitespace: multilínea → una línea, múltiples espacios → uno
  3.  Eliminar punto y coma final
  4.  Eliminar backticks (MySQL syntax)
  5.  Comillas dobles en nombres de columna/tabla → sin comillas
  6.  LIMIT N / ROWS N / TOP N → SELECT FIRST N
  7.  Añadir FIRST N automáticamente si no existe (no en agregaciones)
  8.  ILIKE → UPPER(col) LIKE UPPER(val)
  9.  col LIKE 'val' → UPPER(col) LIKE UPPER('val') (case-insensitive)
  10. != → <> (Firebird usa <>)
  11. TRUE/FALSE → 'T'/'F' (Firebird usa strings para booleanos)
  12. NOW() / GETDATE() → CURRENT_TIMESTAMP
  13. CURRENT_DATE() → CURRENT_DATE (sin paréntesis)
  14. SYSDATE → CURRENT_DATE
  15. CONCAT(a, b) → a || b
  16. SUBSTRING(col, pos, len) → SUBSTRING(col FROM pos FOR len)
  17. OFFSET N → eliminar (no soportado en FB 2.5)
  18. Columnas erróneas conocidas (STOCK → STOCKARTICULO, etc.)
  19. Alias con comillas dobles → sin comillas

Autor: DEVIA System
Versión: 1.0.0
"""

import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

# Límite por defecto de filas para SELECT sin FIRST
DEFAULT_FIRST_LIMIT = 100

# Columnas erróneas conocidas que la IA genera frecuentemente
# Formato: (patron_regex, reemplazo, descripcion)
KNOWN_COLUMN_FIXES: List[Tuple[str, str, str]] = [
    # ARTICULO
    (r'\bSTOCK\b', 'STOCKARTICULO', 'STOCK → STOCKARTICULO (columna real en tabla ARTICULO)'),
    # Añadir más aquí según se descubran errores frecuentes del LLM
]


class FirebirdSQLNormalizer:
    """
    Normalizador determinista de SQL para Firebird 2.5.
    
    Aplica todas las correcciones posibles por código antes de enviar
    el SQL a Firebird, minimizando los errores que requieren corrección por IA.
    
    Uso:
        normalizer = FirebirdSQLNormalizer()
        sql_limpio, cambios = normalizer.normalize(sql_bruto)
    """

    def normalize(self, sql: str) -> Tuple[str, List[str]]:
        """
        Aplica todas las normalizaciones deterministas al SQL.
        
        Args:
            sql: SQL generado por la IA (puede tener errores de sintaxis Firebird)
            
        Returns:
            Tupla (sql_normalizado, lista_de_cambios_aplicados)
        """
        changes = []
        original = sql

        # Aplicar cada paso en orden
        sql, c = self._remove_sql_comments(sql)
        changes.extend(c)

        sql, c = self._normalize_whitespace(sql)
        changes.extend(c)

        sql, c = self._remove_trailing_semicolon(sql)
        changes.extend(c)

        sql, c = self._remove_backticks(sql)
        changes.extend(c)

        sql, c = self._remove_double_quote_identifiers(sql)
        changes.extend(c)

        sql, c = self._fix_limit_to_first(sql)
        changes.extend(c)

        sql, c = self._add_first_if_missing(sql)
        changes.extend(c)

        sql, c = self._fix_ilike(sql)
        changes.extend(c)

        sql, c = self._fix_like_case_insensitive(sql)
        changes.extend(c)

        sql, c = self._fix_not_equal(sql)
        changes.extend(c)

        sql, c = self._fix_boolean_literals(sql)
        changes.extend(c)

        sql, c = self._fix_datetime_functions(sql)
        changes.extend(c)

        sql, c = self._fix_concat(sql)
        changes.extend(c)

        sql, c = self._fix_substring(sql)
        changes.extend(c)

        sql, c = self._remove_offset(sql)
        changes.extend(c)

        sql, c = self._fix_known_columns(sql)
        changes.extend(c)

        sql, c = self._fix_alias_quotes(sql)
        changes.extend(c)

        # Log resumen
        if changes:
            logger.info(f"[SQL NORMALIZER] ✅ {len(changes)} correcciones deterministas aplicadas:")
            for change in changes:
                logger.info(f"[SQL NORMALIZER]   • {change}")
        else:
            logger.debug(f"[SQL NORMALIZER] ✓ SQL ya era válido para Firebird 2.5")

        return sql.strip(), changes

    # -------------------------------------------------------------------------
    # Paso 1: Eliminar comentarios SQL
    # -------------------------------------------------------------------------
    def _remove_sql_comments(self, sql: str) -> Tuple[str, List[str]]:
        """Elimina comentarios -- y /* */ del SQL."""
        changes = []
        
        # Comentarios de bloque: /* ... */
        new_sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        if new_sql != sql:
            changes.append("Eliminados comentarios de bloque /* ... */")
            sql = new_sql
        
        # Comentarios de línea: -- ...
        new_sql = re.sub(r'--[^\n]*', ' ', sql)
        if new_sql != sql:
            changes.append("Eliminados comentarios de línea --")
            sql = new_sql
        
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 2: Normalizar whitespace
    # -------------------------------------------------------------------------
    def _normalize_whitespace(self, sql: str) -> Tuple[str, List[str]]:
        """
        Convierte SQL multilínea a una sola línea.
        Qwen3 genera SQL con columnas en líneas separadas:
          SELECT\n    CODIGO,\n    NOMBRE,...
        Firebird requiere que FIRST esté en la misma línea que SELECT.
        """
        changes = []
        new_sql = re.sub(r'\s+', ' ', sql).strip()
        if new_sql != sql.strip():
            changes.append("SQL multilínea normalizado a una línea")
        return new_sql, changes

    # -------------------------------------------------------------------------
    # Paso 3: Eliminar punto y coma final
    # -------------------------------------------------------------------------
    def _remove_trailing_semicolon(self, sql: str) -> Tuple[str, List[str]]:
        """Elimina el punto y coma final (Firebird no lo necesita en queries simples)."""
        changes = []
        new_sql = sql.rstrip(';').strip()
        if new_sql != sql:
            changes.append("Eliminado punto y coma final")
        return new_sql, changes

    # -------------------------------------------------------------------------
    # Paso 4: Eliminar backticks (MySQL syntax)
    # -------------------------------------------------------------------------
    def _remove_backticks(self, sql: str) -> Tuple[str, List[str]]:
        """
        Elimina backticks que la IA genera para MySQL.
        `NOMBRE` → NOMBRE
        """
        changes = []
        if '`' in sql:
            new_sql = sql.replace('`', '')
            changes.append("Eliminados backticks (MySQL syntax) → Firebird no los usa")
            return new_sql, changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 5: Comillas dobles en identificadores → sin comillas
    # -------------------------------------------------------------------------
    def _remove_double_quote_identifiers(self, sql: str) -> Tuple[str, List[str]]:
        """
        Elimina comillas dobles en nombres de columna/tabla.
        "NOMBRE" → NOMBRE
        Nota: Solo elimina si son identificadores simples (sin espacios dentro).
        """
        changes = []
        # Patrón: "IDENTIFICADOR" donde IDENTIFICADOR no tiene espacios
        pattern = re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"')
        new_sql = pattern.sub(r'\1', sql)
        if new_sql != sql:
            changes.append('Eliminadas comillas dobles en identificadores ("COL" → COL)')
            return new_sql, changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 6: LIMIT N / ROWS N / TOP N → SELECT FIRST N
    # -------------------------------------------------------------------------
    def _fix_limit_to_first(self, sql: str) -> Tuple[str, List[str]]:
        """
        Convierte LIMIT N, ROWS N, TOP N a SELECT FIRST N.
        Firebird 2.5 solo soporta SELECT FIRST N.
        """
        changes = []

        # LIMIT N (al final o en cualquier posición)
        limit_match = re.search(r'\bLIMIT\s+(\d+)', sql, re.IGNORECASE)
        if limit_match:
            limit_val = limit_match.group(1)
            # Eliminar LIMIT N
            sql = re.sub(r'\bLIMIT\s+\d+', '', sql, flags=re.IGNORECASE)
            # Añadir FIRST N si no existe ya
            if not re.search(r'\bSELECT\s+FIRST\s+\d+', sql, re.IGNORECASE):
                sql = re.sub(r'\bSELECT\s+', f'SELECT FIRST {limit_val} ', sql, count=1, flags=re.IGNORECASE)
            changes.append(f"LIMIT {limit_val} → SELECT FIRST {limit_val}")

        # TOP N (SQL Server syntax)
        top_match = re.search(r'\bSELECT\s+TOP\s+(\d+)\s+', sql, re.IGNORECASE)
        if top_match:
            top_val = top_match.group(1)
            sql = re.sub(r'\bSELECT\s+TOP\s+\d+\s+', f'SELECT FIRST {top_val} ', sql, count=1, flags=re.IGNORECASE)
            changes.append(f"SELECT TOP {top_val} → SELECT FIRST {top_val}")

        # ROWS N (alternativa usada por algunas IAs)
        rows_match = re.search(r'\bROWS\s+(\d+)', sql, re.IGNORECASE)
        if rows_match:
            rows_val = rows_match.group(1)
            sql = re.sub(r'\bROWS\s+\d+(\s+TO\s+\d+)?', '', sql, flags=re.IGNORECASE)
            if not re.search(r'\bSELECT\s+FIRST\s+\d+', sql, re.IGNORECASE):
                sql = re.sub(r'\bSELECT\s+', f'SELECT FIRST {rows_val} ', sql, count=1, flags=re.IGNORECASE)
            changes.append(f"ROWS {rows_val} → SELECT FIRST {rows_val}")

        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 7: Añadir FIRST N si no existe
    # -------------------------------------------------------------------------
    def _add_first_if_missing(self, sql: str) -> Tuple[str, List[str]]:
        """
        Añade SELECT FIRST N si el SELECT no tiene FIRST y no es una agregación.
        Las agregaciones (COUNT, SUM, AVG, MAX, MIN) no necesitan FIRST.
        """
        changes = []
        sql_upper = sql.upper()

        # Solo para SELECT
        if not sql_upper.lstrip().startswith('SELECT'):
            return sql, changes

        # Ya tiene FIRST
        if re.search(r'\bFIRST\s+\d+', sql_upper):
            return sql, changes

        # Es una agregación pura → no añadir FIRST
        is_aggregate = any(
            re.search(rf'\b{agg}\s*\(', sql_upper)
            for agg in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']
        )
        if is_aggregate:
            return sql, changes

        # Añadir FIRST N usando regex (maneja cualquier cantidad de espacios)
        new_sql = re.sub(
            r'^(\s*SELECT\s+)',
            f'SELECT FIRST {DEFAULT_FIRST_LIMIT} ',
            sql,
            count=1,
            flags=re.IGNORECASE
        )
        if new_sql != sql:
            changes.append(f"Añadido FIRST {DEFAULT_FIRST_LIMIT} automáticamente (sin límite explícito)")
            return new_sql, changes

        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 8: ILIKE → UPPER(col) LIKE UPPER(val)
    # -------------------------------------------------------------------------
    def _fix_ilike(self, sql: str) -> Tuple[str, List[str]]:
        """
        Convierte ILIKE (PostgreSQL) a UPPER(col) LIKE UPPER(val).
        Firebird no tiene ILIKE.
        """
        changes = []
        if not re.search(r'\bILIKE\b', sql, re.IGNORECASE):
            return sql, changes

        pattern = re.compile(r'\b([a-zA-Z0-9_.]+)\s+ILIKE\s+(\'[^\']*\')', re.IGNORECASE)
        new_sql = pattern.sub(lambda m: f"UPPER({m.group(1)}) LIKE UPPER({m.group(2)})", sql)
        if new_sql != sql:
            changes.append("ILIKE → UPPER(col) LIKE UPPER(val) (Firebird no tiene ILIKE)")
            return new_sql, changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 9: col LIKE 'val' → UPPER(col) LIKE UPPER('val')
    # -------------------------------------------------------------------------
    def _fix_like_case_insensitive(self, sql: str) -> Tuple[str, List[str]]:
        """
        Hace todas las búsquedas LIKE case-insensitive.
        Firebird es case-sensitive por defecto.
        No modifica los que ya tienen UPPER().
        """
        changes = []
        # Patrón: identificador LIKE 'valor' (sin UPPER ya aplicado)
        pattern = re.compile(
            r'\b(?<!UPPER\()([a-zA-Z0-9_.]+)\s+LIKE\s+(\'[^\']*\')',
            re.IGNORECASE
        )

        def replace_like(match):
            col = match.group(1)
            val = match.group(2)
            # No modificar si ya tiene UPPER
            if col.upper().startswith('UPPER'):
                return match.group(0)
            return f"UPPER({col}) LIKE UPPER({val})"

        new_sql = pattern.sub(replace_like, sql)
        if new_sql != sql:
            changes.append("LIKE → UPPER(col) LIKE UPPER(val) (case-insensitive para Firebird)")
            return new_sql, changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 10: != → <>
    # -------------------------------------------------------------------------
    def _fix_not_equal(self, sql: str) -> Tuple[str, List[str]]:
        """
        Convierte != a <> (Firebird usa <> para 'distinto de').
        Aunque Firebird 2.5 acepta != en algunos contextos, <> es el estándar.
        """
        changes = []
        if '!=' in sql:
            new_sql = sql.replace('!=', '<>')
            changes.append("!= → <> (operador estándar Firebird)")
            return new_sql, changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 11: TRUE/FALSE → 'T'/'F'
    # -------------------------------------------------------------------------
    def _fix_boolean_literals(self, sql: str) -> Tuple[str, List[str]]:
        """
        Convierte TRUE/FALSE a 'T'/'F'.
        Firebird 2.5 no tiene tipo BOOLEAN nativo; usa CHAR(1) con 'T'/'F'.
        Nota: Firebird 3+ sí tiene BOOLEAN, pero la BD usa 2.5.
        """
        changes = []
        new_sql = sql

        # TRUE → 'T' (solo como valor, no dentro de palabras)
        new_sql_t = re.sub(r'\bTRUE\b', "'T'", new_sql, flags=re.IGNORECASE)
        if new_sql_t != new_sql:
            changes.append("TRUE → 'T' (Firebird 2.5 usa CHAR 'T'/'F' para booleanos)")
            new_sql = new_sql_t

        # FALSE → 'F'
        new_sql_f = re.sub(r'\bFALSE\b', "'F'", new_sql, flags=re.IGNORECASE)
        if new_sql_f != new_sql:
            changes.append("FALSE → 'F' (Firebird 2.5 usa CHAR 'T'/'F' para booleanos)")
            new_sql = new_sql_f

        return new_sql, changes

    # -------------------------------------------------------------------------
    # Paso 12: Funciones de fecha incorrectas
    # -------------------------------------------------------------------------
    def _fix_datetime_functions(self, sql: str) -> Tuple[str, List[str]]:
        """
        Corrige funciones de fecha que la IA genera para otros SGBD.
        """
        changes = []
        new_sql = sql

        # NOW() → CURRENT_TIMESTAMP
        if re.search(r'\bNOW\s*\(\s*\)', new_sql, re.IGNORECASE):
            new_sql = re.sub(r'\bNOW\s*\(\s*\)', 'CURRENT_TIMESTAMP', new_sql, flags=re.IGNORECASE)
            changes.append("NOW() → CURRENT_TIMESTAMP")

        # GETDATE() → CURRENT_TIMESTAMP (SQL Server)
        if re.search(r'\bGETDATE\s*\(\s*\)', new_sql, re.IGNORECASE):
            new_sql = re.sub(r'\bGETDATE\s*\(\s*\)', 'CURRENT_TIMESTAMP', new_sql, flags=re.IGNORECASE)
            changes.append("GETDATE() → CURRENT_TIMESTAMP")

        # SYSDATE → CURRENT_DATE (Oracle)
        if re.search(r'\bSYSDATE\b', new_sql, re.IGNORECASE):
            new_sql = re.sub(r'\bSYSDATE\b', 'CURRENT_DATE', new_sql, flags=re.IGNORECASE)
            changes.append("SYSDATE → CURRENT_DATE")

        # CURRENT_DATE() → CURRENT_DATE (sin paréntesis en Firebird)
        if re.search(r'\bCURRENT_DATE\s*\(\s*\)', new_sql, re.IGNORECASE):
            new_sql = re.sub(r'\bCURRENT_DATE\s*\(\s*\)', 'CURRENT_DATE', new_sql, flags=re.IGNORECASE)
            changes.append("CURRENT_DATE() → CURRENT_DATE (sin paréntesis en Firebird)")

        # CURRENT_TIMESTAMP() → CURRENT_TIMESTAMP (sin paréntesis)
        if re.search(r'\bCURRENT_TIMESTAMP\s*\(\s*\)', new_sql, re.IGNORECASE):
            new_sql = re.sub(r'\bCURRENT_TIMESTAMP\s*\(\s*\)', 'CURRENT_TIMESTAMP', new_sql, flags=re.IGNORECASE)
            changes.append("CURRENT_TIMESTAMP() → CURRENT_TIMESTAMP (sin paréntesis en Firebird)")

        return new_sql, changes

    # -------------------------------------------------------------------------
    # Paso 13: CONCAT(a, b) → a || b
    # -------------------------------------------------------------------------
    def _fix_concat(self, sql: str) -> Tuple[str, List[str]]:
        """
        Convierte CONCAT(a, b) a a || b.
        Firebird usa || para concatenación, no CONCAT().
        Solo para CONCAT de 2 argumentos simples (sin anidamiento).
        """
        changes = []
        # Patrón simple: CONCAT(expr1, expr2) donde expr no contiene paréntesis
        pattern = re.compile(r'\bCONCAT\s*\(\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)', re.IGNORECASE)
        new_sql = pattern.sub(lambda m: f"({m.group(1).strip()} || {m.group(2).strip()})", sql)
        if new_sql != sql:
            changes.append("CONCAT(a, b) → a || b (Firebird usa || para concatenación)")
            return new_sql, changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 14: SUBSTRING(col, pos, len) → SUBSTRING(col FROM pos FOR len)
    # -------------------------------------------------------------------------
    def _fix_substring(self, sql: str) -> Tuple[str, List[str]]:
        """
        Convierte SUBSTRING(col, pos, len) a SUBSTRING(col FROM pos FOR len).
        Firebird usa la sintaxis SQL estándar con FROM/FOR.
        """
        changes = []
        # Patrón: SUBSTRING(col, pos, len) — 3 argumentos separados por comas
        pattern = re.compile(
            r'\bSUBSTRING\s*\(\s*([^,()]+?)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
            re.IGNORECASE
        )
        new_sql = pattern.sub(
            lambda m: f"SUBSTRING({m.group(1).strip()} FROM {m.group(2)} FOR {m.group(3)})",
            sql
        )
        if new_sql != sql:
            changes.append("SUBSTRING(col, pos, len) → SUBSTRING(col FROM pos FOR len)")
            return new_sql, changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 15: Eliminar OFFSET N
    # -------------------------------------------------------------------------
    def _remove_offset(self, sql: str) -> Tuple[str, List[str]]:
        """
        Elimina OFFSET N (no soportado en Firebird 2.5).
        Firebird 2.5 no tiene OFFSET; Firebird 3+ usa OFFSET/FETCH.
        """
        changes = []
        if re.search(r'\bOFFSET\s+\d+', sql, re.IGNORECASE):
            new_sql = re.sub(r'\bOFFSET\s+\d+', '', sql, flags=re.IGNORECASE)
            changes.append("OFFSET N eliminado (no soportado en Firebird 2.5)")
            return new_sql.strip(), changes
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 16: Columnas erróneas conocidas
    # -------------------------------------------------------------------------
    def _fix_known_columns(self, sql: str) -> Tuple[str, List[str]]:
        """
        Corrige nombres de columna erróneos que la IA genera frecuentemente.
        Usa word-boundary para no reemplazar subcadenas (ej: STOCK no reemplaza STOCKARTICULO).
        """
        changes = []
        for pattern, replacement, description in KNOWN_COLUMN_FIXES:
            if re.search(pattern, sql, re.IGNORECASE):
                new_sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
                if new_sql != sql:
                    changes.append(f"Columna corregida: {description}")
                    sql = new_sql
        return sql, changes

    # -------------------------------------------------------------------------
    # Paso 17: Alias con comillas dobles → sin comillas
    # -------------------------------------------------------------------------
    def _fix_alias_quotes(self, sql: str) -> Tuple[str, List[str]]:
        """
        Elimina comillas dobles en alias de columna.
        SELECT col AS "alias" → SELECT col AS alias
        """
        changes = []
        pattern = re.compile(r'\bAS\s+"([^"]+)"', re.IGNORECASE)
        new_sql = pattern.sub(r'AS \1', sql)
        if new_sql != sql:
            changes.append('Alias con comillas dobles → sin comillas (AS "alias" → AS alias)')
            return new_sql, changes
        return sql, changes
