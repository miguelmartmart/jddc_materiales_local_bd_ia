"""
firebird_sql_constants.py — Constantes para el normalizador SQL de Firebird 2.5

ÚNICA FUENTE DE VERDAD para:
  - Límites de filas por defecto
  - Columnas erróneas conocidas (LLM → real)
  - Columnas BLOB por tabla
  - Mapeo de columnas desconocidas tras error
  - Tipos de documento DOCCAB

Para añadir una nueva corrección: editar SOLO este fichero.
"""

from typing import List, Tuple, Dict, Set

# ─── Límites ──────────────────────────────────────────────────────────────────

# Filas máximas por defecto cuando el SELECT no tiene FIRST N
DEFAULT_FIRST_LIMIT: int = 100

# ─── Columnas erróneas conocidas ──────────────────────────────────────────────
# La IA genera nombres incorrectos; aquí los mapeamos al nombre real en Firebird.
# Formato: (patron_regex_word_boundary, reemplazo, descripcion_legible)
KNOWN_COLUMN_FIXES: List[Tuple[str, str, str]] = [
    (r'\bSTOCK\b',        'STOCKARTICULO', 'STOCK → STOCKARTICULO (columna real en ARTICULO)'),
    (r'\bPRECIO\b',       'PRECIOVENTA',   'PRECIO → PRECIOVENTA (columna real en ARTICULO)'),
    (r'\bNOMBRE_CLIENTE\b', 'RAZONSOCIAL', 'NOMBRE_CLIENTE → RAZONSOCIAL (columna real en CLIENTE)'),
]

# ─── Columnas BLOB por tabla ──────────────────────────────────────────────────
# Firebird lanza "conversion error from string BLOB" si se usa GROUP BY sobre BLOB.
# Formato: tabla_en_mayusculas → set de columnas BLOB en mayúsculas
BLOB_COLUMNS_BY_TABLE: Dict[str, Set[str]] = {
    "ARTICULO":  {"DESCRIPCION", "OBSERVACIONES", "NOTAS", "TEXTOAMPLIADO"},
    "DOCCAB":    {"DESCRIPCION", "OBSERVACIONES", "NOTAS", "TEXTOPIE", "TEXTOCABECERA"},
    "DOCLIN":    {"DESCRIPCION", "OBSERVACIONES", "NOTAS"},
    "CLIENTE":   {"OBSERVACIONES", "NOTAS"},
    "PROVEEDOR": {"OBSERVACIONES", "NOTAS"},
}

# Columna de reemplazo preferida cuando se elimina un BLOB del SELECT
BLOB_REPLACEMENT_COL: str = "NOMBRE"

# ─── Mapeo de columnas desconocidas (post-error) ──────────────────────────────
# Se usa en fix_after_error cuando Firebird devuelve "Column unknown X".
COLUMN_UNKNOWN_MAP: Dict[str, str] = {
    "STOCK":           "STOCKARTICULO",
    "DESCRIPCION":     "DESCRIPCIONCORTA",   # DESCRIPCION es BLOB en ARTICULO
    "PRECIO":          "PRECIOVENTA",
    "NOMBRE_CLIENTE":  "RAZONSOCIAL",
    "NOMBRE_PROVEEDOR": "RAZONSOCIAL",
    "IMPORTE":         "IMPORTETOTAL",
    "TOTAL":           "IMPORTETOTAL",
}

# ─── Tipos de documento DOCCAB ────────────────────────────────────────────────
# Referencia rápida para el system prompt y para tests.
DOCCAB_TIPOS: Dict[str, int] = {
    "factura":        13,
    "albaran":        11,
    "presupuesto":    0,
    "pedido":         12,
    "abono":          3,
    "recibo":         61,
    "contrato":       10,
    "certificacion":  51,
    "sat":            2,
    "orden_trabajo":  2,
}

# ─── Funciones de fecha a reemplazar ─────────────────────────────────────────
# Formato: (patron_regex, reemplazo, descripcion)
DATETIME_FIXES: List[Tuple[str, str, str]] = [
    (r'\bNOW\s*\(\s*\)',              'CURRENT_TIMESTAMP', 'NOW() → CURRENT_TIMESTAMP'),
    (r'\bGETDATE\s*\(\s*\)',          'CURRENT_TIMESTAMP', 'GETDATE() → CURRENT_TIMESTAMP'),
    (r'\bSYSDATE\b',                  'CURRENT_DATE',      'SYSDATE → CURRENT_DATE'),
    (r'\bCURRENT_DATE\s*\(\s*\)',     'CURRENT_DATE',      'CURRENT_DATE() → CURRENT_DATE'),
    (r'\bCURRENT_TIMESTAMP\s*\(\s*\)', 'CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP() → CURRENT_TIMESTAMP'),
]

# ─── Funciones de agregación (no añadir FIRST N) ─────────────────────────────
AGGREGATE_FUNCTIONS: List[str] = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']
