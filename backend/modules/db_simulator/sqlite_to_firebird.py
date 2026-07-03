"""
sqlite_to_firebird.py - Adaptador SQL SQLite -> Firebird 2.5.

Complementa FirebirdSQLNormalizer con correcciones especificas para las consultas
de la query_library, que estan escritas en SQLite y deben ejecutarse contra la BD
real Firebird.

Diferencias clave SQLite vs Firebird 2.5 que maneja este modulo:
  1. CAST(x AS TEXT)               -> CAST(x AS VARCHAR(100))  (balance de parentesis)
  2. SUBSTR(FECHA,1,7)             -> EXTRACT(YEAR)*100 + EXTRACT(MONTH)
  3. SUBSTR(FECHA,1,4)             -> CAST(EXTRACT(YEAR FROM FECHA) AS VARCHAR(4))
  4. SUBSTR(col,a,b) generico      -> SUBSTRING(col FROM a FOR b)
  5. JULIANDAY(...)                -> fallback query
  6. BASEIMPONIBLE                 -> IMPORTEBASE  (nombre real Firebird DOCCAB)
  7. IVA (columna standalone)      -> IMPORTEIVA   (nombre real Firebird DOCCAB)
  8. LPAD(x, n, '0')               -> RIGHT('0' || x, n)
  9. date('now','start of month')  -> DATEADD(DAY, -(EXTRACT(DAY FROM CURRENT_DATE)-1), CURRENT_DATE)
 10. date('now','-N days')         -> DATEADD(DAY, -N, CURRENT_DATE)
 11. date('now','-N months')       -> DATEADD(MONTH, -N, CURRENT_DATE)
 12. date('now','-N years')        -> DATEADD(YEAR, -N, CURRENT_DATE)
 13. date('now')                   -> CURRENT_DATE
 14. strftime('%w', col)           -> EXTRACT(WEEKDAY FROM col)
 15. strftime('%Y', col)           -> EXTRACT(YEAR FROM col)
 16. strftime('%m', col)           -> EXTRACT(MONTH FROM col)
 17. strftime('%d', col)           -> EXTRACT(DAY FROM col)
 18. L.UNIDADES                    -> L.CANTIDAD  (nombre real Firebird DOCLIN)
 19. A.PRECIO (con alias tabla)    -> A.PRECIOVENTA
 20. A.CODPROVEEDOR (con alias)    -> A.PROVEEDDEFECTO

Nota: LIMIT->FIRST lo maneja FirebirdSQLNormalizer (se aplica despues de este adaptador).

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import re
from typing import Tuple, List

# ─── Constantes ───────────────────────────────────────────────────────────────

_JULIANDAY_FALLBACK = (
    "SELECT 'Antiguedad no disponible' AS NOTA, "
    "COUNT(*) AS N_DOCS, CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL "
    "FROM DOCCAB WHERE IMPORTETOTAL > 0"
)

_SQLITE_ONLY_COLUMNS = {
    "BASEIMPONIBLE": "IMPORTEBASE",
}

_IVA_COLUMN_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_.])IVA(?![A-Za-z0-9_])',
    re.IGNORECASE,
)
_IVA_ALIAS_GUARD = re.compile(
    r'\bAS\s+IVA\b',
    re.IGNORECASE,
)  # Detecta alias "AS IVA" para excluirlos de la traducción

# strftime patterns: (patron, reemplazo_func)
_STRFTIME_PATTERNS = [
    (re.compile(r"strftime\s*\(\s*'%w'\s*,\s*([^,)]+?)\s*\)", re.IGNORECASE),
     lambda m: f"EXTRACT(WEEKDAY FROM {m.group(1).strip()})"),
    (re.compile(r"strftime\s*\(\s*'%Y'\s*,\s*([^,)]+?)\s*\)", re.IGNORECASE),
     lambda m: f"EXTRACT(YEAR FROM {m.group(1).strip()})"),
    (re.compile(r"strftime\s*\(\s*'%m'\s*,\s*([^,)]+?)\s*\)", re.IGNORECASE),
     lambda m: f"EXTRACT(MONTH FROM {m.group(1).strip()})"),
    (re.compile(r"strftime\s*\(\s*'%d'\s*,\s*([^,)]+?)\s*\)", re.IGNORECASE),
     lambda m: f"EXTRACT(DAY FROM {m.group(1).strip()})"),
]

# date() SQLite patterns
_DATE_NOW_START_MONTH = re.compile(
    r"date\s*\(\s*'now'\s*,\s*'start\s+of\s+month'\s*\)",
    re.IGNORECASE,
)
_DATE_NOW_MINUS_DAYS = re.compile(
    r"date\s*\(\s*'now'\s*,\s*'-(\d+)\s+days?'\s*\)",
    re.IGNORECASE,
)
_DATE_NOW_MINUS_MONTHS = re.compile(
    r"date\s*\(\s*'now'\s*,\s*'-(\d+)\s+months?'\s*\)",
    re.IGNORECASE,
)
_DATE_NOW_MINUS_YEARS = re.compile(
    r"date\s*\(\s*'now'\s*,\s*'-(\d+)\s+years?'\s*\)",
    re.IGNORECASE,
)
_DATE_NOW_PLAIN = re.compile(
    r"date\s*\(\s*'now'\s*\)",
    re.IGNORECASE,
)

# SUBSTR patterns
_SUBSTR_FECHA_MONTH_PATTERN = re.compile(
    r"SUBSTR\(\s*(\w+)\s*,\s*1\s*,\s*7\s*\)",
    re.IGNORECASE,
)
_SUBSTR_FECHA_YEAR_PATTERN = re.compile(
    r"SUBSTR\(\s*(\w+)\s*,\s*1\s*,\s*4\s*\)",
    re.IGNORECASE,
)
_SUBSTR_GENERIC_PATTERN = re.compile(
    r'SUBSTR\(([^)]+)\)',
    re.IGNORECASE,
)

_LPAD_PATTERN = re.compile(
    r"LPAD\(\s*([^,]+?)\s*,\s*(\d+)\s*,\s*'0'\s*\)",
    re.IGNORECASE,
)

_DATE_COLUMNS = {"FECHA", "FECHAENTREGA", "FECHAVENCIMIENTO", "FECHAPAGO", "FECHAALTA"}

# L.UNIDADES -> L.CANTIDAD (nombre real en Firebird DOCLIN)
# Aplica con cualquier alias de tabla de una sola letra o "LIN"
_UNIDADES_PATTERN = re.compile(
    r'\b([A-Za-z][A-Za-z0-9]*)\.UNIDADES\b',
    re.IGNORECASE,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_date_column(col: str) -> bool:
    return col.upper().strip() in _DATE_COLUMNS


def _find_matching_paren(s: str, open_pos: int) -> int:
    """Encuentra el paréntesis de cierre correspondiente al '(' en open_pos."""
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


def _replace_cast_text(sql: str) -> Tuple[str, bool]:
    """
    Reemplaza CAST(expr AS TEXT) -> CAST(expr AS VARCHAR(100)) usando balance
    de parentesis para capturar expresiones anidadas como CAST(CAST(...) AS TEXT).

    El regex simple [^)]+ no funciona con parentesis anidados.
    """
    pattern = re.compile(r'\bCAST\s*\(', re.IGNORECASE)
    result = []
    i = 0
    changed = False
    while i < len(sql):
        m = pattern.search(sql, i)
        if not m:
            result.append(sql[i:])
            break
        result.append(sql[i:m.start()])
        open_pos = m.end() - 1  # posicion del '('
        close_pos = _find_matching_paren(sql, open_pos)
        if close_pos == -1:
            result.append(sql[m.start():])
            break
        inner = sql[open_pos + 1:close_pos]
        # Verificar si termina en "AS TEXT" (ignorando espacios)
        as_text_match = re.search(r'\s+AS\s+TEXT\s*$', inner, re.IGNORECASE)
        if as_text_match:
            expr = inner[:as_text_match.start()]
            result.append(f"CAST({expr} AS VARCHAR(100))")
            changed = True
        else:
            result.append(sql[m.start():close_pos + 1])
        i = close_pos + 1
    return ''.join(result), changed


def _replace_substr_fecha_month(m: re.Match) -> str:
    col = m.group(1).strip()
    if _is_date_column(col):
        return f"EXTRACT(YEAR FROM {col}) * 100 + EXTRACT(MONTH FROM {col})"
    return f"SUBSTRING({col} FROM 1 FOR 7)"


def _replace_substr_fecha_year(m: re.Match) -> str:
    col = m.group(1).strip()
    if _is_date_column(col):
        return f"CAST(EXTRACT(YEAR FROM {col}) AS VARCHAR(4))"
    return f"SUBSTRING({col} FROM 1 FOR 4)"


def _replace_substr_generic(m: re.Match) -> str:
    args = [a.strip() for a in m.group(1).split(',')]
    if len(args) == 3:
        return f"SUBSTRING({args[0]} FROM {args[1]} FOR {args[2]})"
    if len(args) == 2:
        return f"SUBSTRING({args[0]} FROM {args[1]})"
    return m.group(0)


# ─── Función principal ────────────────────────────────────────────────────────

def adapt_sql_for_firebird(sql: str) -> Tuple[str, List[str]]:
    """
    Adapta SQL escrito para SQLite a Firebird 2.5.

    Devuelve:
      (sql_adaptado, lista_de_cambios_aplicados)

    Uso tipico:
      adapted, changes = adapt_sql_for_firebird(original_sql)
      fb_sql, _ = FirebirdSQLNormalizer().normalize(adapted)
      rows = fb_driver.execute_query(fb_sql)
    """
    changes: List[str] = []

    # ── 1. JULIANDAY -> fallback ───────────────────────────────────────────
    if "JULIANDAY" in sql.upper():
        changes.append("JULIANDAY->fallback")
        return _JULIANDAY_FALLBACK, changes

    # ── 2. strftime() -> EXTRACT() ────────────────────────────────────────
    # Debe ir ANTES de date() para evitar conflictos.
    for pat, replacer in _STRFTIME_PATTERNS:
        new_sql = pat.sub(replacer, sql)
        if new_sql != sql:
            changes.append("strftime->EXTRACT")
            sql = new_sql

    # ── 3. date() SQLite -> Firebird ──────────────────────────────────────
    # Orden: mas especificos primero.
    # NOTA CRITICA: Esta BD Firebird 2.5 NO tiene DATEADD.
    # Usar aritmetica directa de fechas: CURRENT_DATE - N
    # Primer dia del mes: CURRENT_DATE - EXTRACT(DAY FROM CURRENT_DATE) + 1
    new_sql = _DATE_NOW_START_MONTH.sub(
        "(CURRENT_DATE - EXTRACT(DAY FROM CURRENT_DATE) + 1)", sql
    )
    if new_sql != sql:
        changes.append("date(now,start_of_month)->CURRENT_DATE-DAY+1")
        sql = new_sql

    # date('now','-N years') -> CURRENT_DATE - N*365 (aproximacion)
    new_sql = _DATE_NOW_MINUS_YEARS.sub(
        lambda m: f"(CURRENT_DATE - {int(m.group(1))*365})", sql
    )
    if new_sql != sql:
        changes.append("date(now,-N_years)->CURRENT_DATE-N*365")
        sql = new_sql

    # date('now','-N months') -> CURRENT_DATE - N*30 (aproximacion)
    new_sql = _DATE_NOW_MINUS_MONTHS.sub(
        lambda m: f"(CURRENT_DATE - {int(m.group(1))*30})", sql
    )
    if new_sql != sql:
        changes.append("date(now,-N_months)->CURRENT_DATE-N*30")
        sql = new_sql

    # date('now','-N days') -> CURRENT_DATE - N
    new_sql = _DATE_NOW_MINUS_DAYS.sub(
        lambda m: f"(CURRENT_DATE - {m.group(1)})", sql
    )
    if new_sql != sql:
        changes.append("date(now,-N_days)->CURRENT_DATE-N")
        sql = new_sql

    new_sql = _DATE_NOW_PLAIN.sub("CURRENT_DATE", sql)
    if new_sql != sql:
        changes.append("date(now)->CURRENT_DATE")
        sql = new_sql

    # ── 4. CAST(x AS TEXT) -> CAST(x AS VARCHAR(100)) ─────────────────────
    # Usa balance de parentesis para capturar expresiones anidadas.
    new_sql, changed = _replace_cast_text(sql)
    if changed:
        changes.append("CAST_TEXT->VARCHAR100")
        sql = new_sql

    # ── 5. SUBSTR(FECHA,1,7) -> EXTRACT year-month ────────────────────────
    new_sql = _SUBSTR_FECHA_MONTH_PATTERN.sub(_replace_substr_fecha_month, sql)
    if new_sql != sql:
        changes.append("SUBSTR_FECHA_MONTH->EXTRACT")
        sql = new_sql

    # ── 6. SUBSTR(FECHA,1,4) -> EXTRACT year ──────────────────────────────
    new_sql = _SUBSTR_FECHA_YEAR_PATTERN.sub(_replace_substr_fecha_year, sql)
    if new_sql != sql:
        changes.append("SUBSTR_FECHA_YEAR->EXTRACT")
        sql = new_sql

    # ── 7. SUBSTR(x,a,b) generico -> SUBSTRING(x FROM a FOR b) ───────────
    new_sql = _SUBSTR_GENERIC_PATTERN.sub(_replace_substr_generic, sql)
    if new_sql != sql:
        changes.append("SUBSTR->SUBSTRING")
        sql = new_sql

    # ── 8. BASEIMPONIBLE -> IMPORTEBASE ───────────────────────────────────
    for col, replacement in _SQLITE_ONLY_COLUMNS.items():
        pattern = re.compile(r'\b' + re.escape(col) + r'\b', re.IGNORECASE)
        new_sql = pattern.sub(replacement, sql)
        if new_sql != sql:
            changes.append(f"{col}->{replacement}")
            sql = new_sql

    # ── 9. Columnas ARTICULO: A.PRECIO -> A.PRECIOVENTA, etc. ─────────────
    _articulo_aliases = r'(?:[Aa][Rr][Tt]?|[Aa])\.'
    for old_col, new_col in [('PRECIO', 'PRECIOVENTA'), ('CODPROVEEDOR', 'PROVEEDDEFECTO')]:
        pat = re.compile(
            r'(' + _articulo_aliases + r')' + r'\b' + re.escape(old_col) + r'\b',
            re.IGNORECASE,
        )
        new_sql = pat.sub(lambda m, nc=new_col: m.group(1) + nc, sql)
        if new_sql != sql:
            changes.append(f"ARTICULO.{old_col}->{new_col}")
            sql = new_sql
        if old_col == 'CODPROVEEDOR':
            pat_bare = re.compile(
                r'(?<!\.)(?<![A-Za-z0-9_])\b' + re.escape(old_col) + r'\b',
                re.IGNORECASE,
            )
            new_sql = pat_bare.sub(new_col, sql)
            if new_sql != sql:
                changes.append(f"bare.{old_col}->{new_col}")
                sql = new_sql

    # ── 10. IVA (columna standalone) -> IMPORTEIVA ────────────────────────
    # Preservar aliases: temporalmente proteger "AS IVA" antes de la sustitución.
    _IVA_ALIAS_PLACEHOLDER = "__IVA_ALIAS_PLACEHOLDER__"
    sql_protected = _IVA_ALIAS_GUARD.sub(f"AS {_IVA_ALIAS_PLACEHOLDER}", sql)
    new_sql = _IVA_COLUMN_PATTERN.sub('IMPORTEIVA', sql_protected)
    new_sql = new_sql.replace(_IVA_ALIAS_PLACEHOLDER, "IVA")
    if new_sql != sql:
        changes.append("IVA_col->IMPORTEIVA")
        sql = new_sql

    # ── 11. L.UNIDADES -> L.CANTIDAD (nombre real en Firebird DOCLIN) ─────
    # En Firebird DOCLIN la columna de cantidad se llama CANTIDAD, no UNIDADES.
    new_sql = _UNIDADES_PATTERN.sub(lambda m: f"{m.group(1)}.CANTIDAD", sql)
    if new_sql != sql:
        changes.append("UNIDADES->CANTIDAD")
        sql = new_sql

    # ── 12. LPAD(x, n, '0') -> RIGHT('0' || x, n) ────────────────────────
    new_sql = _LPAD_PATTERN.sub(
        lambda m: f"RIGHT('0' || {m.group(1)}, {m.group(2)})", sql
    )
    if new_sql != sql:
        changes.append("LPAD->RIGHT")
        sql = new_sql

    # ── 13. Eliminar caracteres fuera de latin-1 de literales SQL ─────────
    def _strip_non_latin1(m: re.Match) -> str:
        content = m.group(1)
        safe = content.encode('latin-1', errors='replace').decode('latin-1')
        return "'" + safe + "'"

    new_sql = re.sub(r"'([^']*)'", _strip_non_latin1, sql)
    if new_sql != sql:
        changes.append("non_latin1->stripped")
        sql = new_sql

    return sql.strip(), changes
