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
    # DOCLIN no tiene FECHA — la fecha del documento está en DOCCAB.FECHA
    # El fix determinista se hace en el normalizer (paso 20)
    "FECHA":           "__NEEDS_JOIN_DOCCAB__",  # señal especial → paso 20
}

# ─── Semántica de tablas de relación (JOIN info crítico) ─────────────────────
# Para tablas que vinculan documentos entre sí, la IA necesita saber exactamente
# qué columna es el origen y cuál el destino, y cómo calcular tasas correctamente.
# CRÍTICO: sin esta info, la IA genera LEFT JOIN + WHERE en tabla derecha = 0 resultados.
RELATION_TABLE_JOIN_INFO: dict = {
    "DOCDESTINO": {
        "origin_col":  "CODDOCUMENTO",        # FK al documento ORIGEN (presupuesto TIPO=0)
        "dest_col":    "CODDOCUMENTODESTINO",  # FK al documento DESTINO (factura/pedido)
        "join_origin": "DOCCAB c ON c.CODIGO = dd.CODDOCUMENTO",
        "join_dest":   "DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO",
        "tasa_sql": (
            "SELECT COUNT(DISTINCT c.CODIGO) AS PRESUPUESTOS_CREADOS, "
            "COUNT(DISTINCT dd.CODDOCUMENTO) AS PRESUPUESTOS_ACEPTADOS, "
            "CAST(COUNT(DISTINCT dd.CODDOCUMENTO) * 100.0 / "
            "NULLIF(COUNT(DISTINCT c.CODIGO), 0) AS NUMERIC(5,2)) AS TASA_EXITO "
            "FROM DOCCAB c "
            "LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO "
            "WHERE c.TIPO = 0"
        ),
        "note": (
            "DOCDESTINO: CODDOCUMENTO=origen(presupuesto), CODDOCUMENTODESTINO=destino(factura/pedido). "
            "Para tasa de éxito: COUNT(DISTINCT dd.CODDOCUMENTO) / COUNT(DISTINCT c.CODIGO). "
            "NUNCA usar LEFT JOIN DOCDESTINO + WHERE d.TIPO IN (...) — convierte LEFT en INNER JOIN. "
            "Correcto: LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO (sin WHERE en dd/d)."
        ),
    },
}

# ─── Columnas de fecha por tabla ──────────────────────────────────────────────
# Qué columna de fecha tiene cada tabla (para corrección determinista).
# Si la tabla NO tiene fecha propia, indica la tabla relacionada y cómo hacer JOIN.
TABLE_DATE_COLUMNS: Dict[str, Dict] = {
    "DOCLIN": {
        "has_date": False,
        "date_col": None,
        "date_via_join": {
            "join_table": "DOCCAB",
            "join_on": "DOCCAB.CODIGO = L.CODDOCUMENTO",
            "date_col": "DOCCAB.FECHA",
            "alias": "C",
            "note": "DOCLIN no tiene FECHA. La fecha del documento está en DOCCAB.FECHA (JOIN por CODDOCUMENTO)"
        }
    },
    "DOCCAB": {
        "has_date": True,
        "date_col": "FECHA",
        "date_via_join": None,
    },
    "ARTICULO": {
        "has_date": False,
        "date_col": None,
        "date_via_join": {
            "join_table": "DOCCAB",
            "join_on": "DOCCAB.CODIGO = L.CODDOCUMENTO",
            "date_col": "DOCCAB.FECHA",
            "note": "ARTICULO no tiene fecha. Para filtrar por fecha de compra: JOIN DOCLIN + JOIN DOCCAB"
        }
    },
}

# ─── Tablas con pocos registros (posible dato mal ubicado) ───────────────────
# Si una consulta usa estas tablas como fuente principal de datos,
# se debe advertir al usuario en la justificación (en rojo).
#
# NOTA IMPORTANTE: El record_count aquí es el número de registros de MUESTRA
# guardados en los metadatos SIUO, NO el número real de registros en la BD.
# DOCCAB tiene miles de registros reales — NO incluirla aquí.
# Solo incluir tablas que realmente tienen pocos datos en producción.
LOW_RECORD_TABLES: Dict[str, Dict] = {
    "DOCLINDOCASOC": {
        "record_count": 4,
        "warning": "DOCLINDOCASOC solo tiene 4 registros. Posiblemente no se use activamente."
    },
    "CONDICIO": {
        "record_count": 1,
        "warning": "CONDICIO solo tiene 1 registro. Verificar si la tabla está en uso."
    },
    "EQUIVAL": {
        "record_count": 4,
        "warning": "EQUIVAL solo tiene 4 registros de equivalencias de artículos."
    },
    "CLIENTEDOCUM": {
        "record_count": 0,
        "warning": "CLIENTEDOCUM está vacía (0 registros). No hay documentos de clientes cargados."
    },
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

# ─── Funciones NO soportadas en Firebird 2.5 → reemplazar determinísticamente ─
# Formato: (patron_regex, funcion_reemplazo_callable_o_str, descripcion)
# ROUND(x, n) → CAST(x * 10^n AS BIGINT) / CAST(10^n AS DOUBLE PRECISION)
# Firebird 2.5 no tiene ROUND(). Firebird 3.0+ sí la tiene.
# Usamos CAST(x AS NUMERIC(15,2)) para 2 decimales (caso más común).
# Para n decimales arbitrarios usamos la fórmula con potencias de 10.
UNSUPPORTED_FUNCTIONS: List[Tuple[str, str, str]] = [
    # ROUND(expr, n) → CAST(CAST(expr * POWER(10, n) + 0.5 AS BIGINT) AS DOUBLE PRECISION) / POWER(10, n)
    # Simplificado para los casos más comunes (0, 1, 2 decimales):
    # Se maneja en el normalizador con regex de captura de grupos.
    # Aquí solo documentamos la regla; la implementación está en _fix_unsupported_functions.
    ("ROUND", "CAST_NUMERIC", "ROUND(x,n) → CAST(x AS NUMERIC(15,n)) [Firebird 2.5 no tiene ROUND]"),
    # TRUNC/TRUNCATE → CAST(x AS INTEGER)
    ("TRUNC",    "CAST_INTEGER", "TRUNC(x) → CAST(x AS INTEGER)"),
    ("TRUNCATE", "CAST_INTEGER", "TRUNCATE(x,n) → CAST(x AS INTEGER)"),
    # NVL → COALESCE (Firebird 2.5 tiene COALESCE pero no NVL)
    ("NVL", "COALESCE", "NVL(a,b) → COALESCE(a,b)"),
    # IFNULL → COALESCE
    ("IFNULL", "COALESCE", "IFNULL(a,b) → COALESCE(a,b)"),
    # ISNULL → COALESCE
    ("ISNULL", "COALESCE", "ISNULL(a,b) → COALESCE(a,b)"),
]

# ─── Funciones de agregación (no añadir FIRST N) ─────────────────────────────
AGGREGATE_FUNCTIONS: List[str] = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'ROUND', 'CAST']
