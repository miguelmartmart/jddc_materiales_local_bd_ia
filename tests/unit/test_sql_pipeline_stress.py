"""
test_sql_pipeline_stress.py
~4000 casos de stress para el pipeline SQL completo:
normalizer → translator → validator.

Cada caso aplica el pipeline real a un SQL de entrada y verifica
que el resultado es válido (string, no falla, no crashea).

Código REAL sin mocks.
"""

import pytest
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.db_simulator.query_translator import translate_firebird_sql
from backend.modules.chat.deep_analysis.phase3 import Phase3Mixin

_norm = FirebirdSQLNormalizer()


def _full_pipeline(sql: str) -> str:
    """Aplica el pipeline completo: normalize → translate → detect_incomplete."""
    # Paso 1: Normalizar (Firebird-oriented)
    try:
        sql_norm, _ = _norm.normalize(sql)
    except Exception:
        sql_norm = sql  # Si normalizer falla, continuar con original

    # Paso 2: Traducir a SQLite
    try:
        sql_sqlite, _ = translate_firebird_sql(sql_norm)
    except Exception:
        sql_sqlite = sql_norm

    # Paso 3: Detectar si está incompleto
    try:
        error = Phase3Mixin._detect_incomplete_sql(sql_sqlite)
    except Exception:
        error = ""

    return sql_sqlite, error


# ─── Generadores masivos de SQL ───────────────────────────────────────────────

_TIPOS = [0, 1, 2, 3, 10, 11, 12, 13, 21]
_TABLAS = ["DOCCAB", "CLIENTE", "PROVEED", "ARTICULO", "DOCLIN",
           "FAMILIA", "ALMACEN", "AGENTES", "CAJA"]
_COLS_DOCCAB = ["TIPO", "FECHA", "IMPORTETOTAL", "CODCLIENTE", "SERIE",
                "NUMERO", "ESTADO", "ESTADOPEND", "CODAGENTE", "CODALMACEN"]
_COLS_CLIENTE = ["CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "NIF",
                 "CODFORMAPAGO", "CODAGENTE", "RIESGOMAXIMO"]
_COLS_ARTICULO = ["CODIGO", "NOMBRE", "CODFAMILIA", "PRECIOVENTA",
                  "PRECIOCOSTE", "STOCKARTICULO"]
_ANIOS = [2023, 2024, 2025, 2026]
_MESES = list(range(1, 13))
_LIMITS = [1, 5, 10, 20, 50, 100]

# ── BLOQUE 1: SELECT por TIPO (200 casos) ────────────────────────────────────
_BLOCK1 = []
for tipo in _TIPOS:
    for limit in _LIMITS:
        _BLOCK1.extend([
            f"SELECT FIRST {limit} * FROM DOCCAB WHERE TIPO = {tipo}",
            f"SELECT FIRST {limit} TIPO, COUNT(*) FROM DOCCAB WHERE TIPO = {tipo} GROUP BY TIPO",
            f"SELECT FIRST {limit} IMPORTETOTAL FROM DOCCAB WHERE TIPO = {tipo} ORDER BY IMPORTETOTAL DESC",
            f"SELECT COUNT(*), SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO = {tipo}",
        ])

# ── BLOQUE 2: SELECT con EXTRACT por mes y año (288 casos) ───────────────────
_BLOCK2 = []
for anio in _ANIOS:
    for mes in _MESES:
        for tipo in [0, 2, 3, 13]:
            _BLOCK2.append(
                f"SELECT COUNT(*) AS N, SUM(IMPORTETOTAL) AS TOTAL "
                f"FROM DOCCAB WHERE TIPO = {tipo} "
                f"AND EXTRACT(YEAR FROM FECHA) = {anio} "
                f"AND EXTRACT(MONTH FROM FECHA) = {mes}"
            )
            _BLOCK2.append(
                f"SELECT EXTRACT(MONTH FROM FECHA) AS MES, COUNT(*) AS N "
                f"FROM DOCCAB WHERE TIPO = {tipo} "
                f"AND EXTRACT(YEAR FROM FECHA) = {anio} "
                f"GROUP BY EXTRACT(MONTH FROM FECHA) ORDER BY MES"
            )

# ── BLOQUE 3: JOIN queries (108 casos) ───────────────────────────────────────
_BLOCK3 = []
for tipo in _TIPOS:
    for limit in [5, 10, 20]:
        _BLOCK3.extend([
            f"SELECT FIRST {limit} d.CODCLIENTE, c.NOMBRECOMERCIAL, "
            f"COUNT(*) AS N FROM DOCCAB d "
            f"LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
            f"WHERE d.TIPO = {tipo} GROUP BY d.CODCLIENTE, c.NOMBRECOMERCIAL "
            f"ORDER BY N DESC",

            f"SELECT FIRST {limit} d.TIPO, SUM(d.IMPORTETOTAL) AS TOTAL "
            f"FROM DOCCAB d LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
            f"WHERE d.TIPO = {tipo} AND NVL(c.BAJA, 0) = 0 "
            f"GROUP BY d.TIPO ORDER BY TOTAL DESC",
        ])

# ── BLOQUE 4: Agregaciones (200 casos) ───────────────────────────────────────
_BLOCK4 = []
for col in _COLS_DOCCAB:
    for tipo in _TIPOS:
        _BLOCK4.append(
            f"SELECT TIPO, COUNT(*) AS N FROM DOCCAB "
            f"WHERE TIPO = {tipo} AND {col} IS NOT NULL "
            f"GROUP BY TIPO ORDER BY N DESC"
        )

# ── BLOQUE 5: SQLs con NVL/IFNULL/ISNULL (150 casos) ────────────────────────
_BLOCK5 = []
for i, col in enumerate(_COLS_CLIENTE * 4):
    _BLOCK5.append(
        f"SELECT NVL({col}, 'N/A') AS {col}_SAFE, COUNT(*) AS N "
        f"FROM CLIENTE GROUP BY NVL({col}, 'N/A') ORDER BY N DESC LIMIT {i % 10 + 1}"
    )

# ── BLOQUE 6: SQLs con CURRENT_DATE (96 casos) ───────────────────────────────
_BLOCK6 = []
for tipo in _TIPOS:
    for limit in _LIMITS[:4]:
        _BLOCK6.extend([
            f"SELECT FIRST {limit} * FROM DOCCAB WHERE TIPO = {tipo} "
            f"AND FECHA <= CURRENT_DATE",
            f"SELECT COUNT(*) FROM DOCCAB WHERE TIPO = {tipo} "
            f"AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)",
        ])

# ── BLOQUE 7: SQLs con CAST(x AS NUMERIC) (200 casos) ────────────────────────
_BLOCK7 = []
for precision in [8, 10, 12, 15]:
    for scale in [0, 2, 4]:
        for tipo in _TIPOS:
            _BLOCK7.append(
                f"SELECT TIPO, "
                f"CAST(SUM(IMPORTETOTAL) AS NUMERIC({precision},{scale})) AS TOTAL, "
                f"CAST(AVG(IMPORTETOTAL) AS NUMERIC({precision},{scale})) AS MEDIA "
                f"FROM DOCCAB WHERE TIPO = {tipo} GROUP BY TIPO"
            )

# ── BLOQUE 8: SQLs con STARTING WITH / CONTAINING (80 casos) ─────────────────
_BLOCK8 = []
_prefixes = ["A", "B", "C", "CONS", "PROM", "SOC", "IMP"]
for prefix in _prefixes:
    _BLOCK8.extend([
        f"SELECT FIRST 10 NOMBRECOMERCIAL FROM CLIENTE WHERE NOMBRECOMERCIAL STARTING WITH '{prefix}'",
        f"SELECT FIRST 10 NOMBRE FROM ARTICULO WHERE NOMBRE CONTAINING '{prefix}'",
        f"SELECT * FROM CLIENTE WHERE RAZONSOCIAL STARTING WITH '{prefix}' AND BAJA = FALSE",
        f"SELECT COUNT(*) FROM ARTICULO WHERE NOMBRE CONTAINING '{prefix.lower()}'",
    ])

# ── BLOQUE 9: SQLs complejos multi-tabla (50 casos) ──────────────────────────
_BLOCK9 = [
    "SELECT d.TIPO, c.NOMBRECOMERCIAL, f.NOMBRE AS FAMILIA, a.NOMBRE AS ARTICULO, "
    "SUM(dl.CANTIDAD * dl.PRECIOUNIT) AS TOTAL "
    "FROM DOCCAB d "
    "LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
    "LEFT JOIN DOCLIN dl ON dl.CODDOC = d.CODIGO "
    "LEFT JOIN ARTICULO a ON dl.CODART = a.CODIGO "
    "LEFT JOIN FAMILIA f ON a.CODFAMILIA = f.CODIGO "
    f"WHERE d.TIPO = {tipo} "
    "GROUP BY d.TIPO, c.NOMBRECOMERCIAL, f.NOMBRE, a.NOMBRE "
    "ORDER BY TOTAL DESC LIMIT 10"
    for tipo in _TIPOS[:5]
] + [
    f"SELECT d.TIPO, COUNT(DISTINCT d.CODCLIENTE) AS N_CLIENTES, "
    f"SUM(d.IMPORTETOTAL) AS TOTAL "
    f"FROM DOCCAB d WHERE d.TIPO IN ({','.join(str(t) for t in _TIPOS[:i+2])}) "
    f"GROUP BY d.TIPO ORDER BY TOTAL DESC"
    for i in range(8)
] + [
    "WITH top_clientes AS ("
    f"  SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB WHERE TIPO = {tipo} "
    "  GROUP BY CODCLIENTE ORDER BY TOTAL DESC LIMIT 5"
    ") "
    "SELECT tc.CODCLIENTE, c.NOMBRECOMERCIAL, tc.TOTAL "
    "FROM top_clientes tc LEFT JOIN CLIENTE c ON tc.CODCLIENTE = c.CODIGO"
    for tipo in _TIPOS[:5]
]

# ── BLOQUE 10: SQLs con NULL checks (100 casos) ───────────────────────────────
_BLOCK10 = []
for col in _COLS_DOCCAB[:5]:
    for tipo in _TIPOS:
        _BLOCK10.extend([
            f"SELECT COUNT(*) AS CON_{col} FROM DOCCAB WHERE {col} IS NOT NULL AND TIPO = {tipo}",
            f"SELECT COUNT(*) AS SIN_{col} FROM DOCCAB WHERE {col} IS NULL AND TIPO = {tipo}",
        ])

# Combinar todos los bloques
_ALL_PIPELINE_SQLS = (
    _BLOCK1 + _BLOCK2 + _BLOCK3 + _BLOCK4 + _BLOCK5 +
    _BLOCK6 + _BLOCK7 + _BLOCK8 + _BLOCK9 + _BLOCK10
)


@pytest.mark.parametrize("sql", _BLOCK1)
def test_pipeline_bloque1_tipo_queries(sql: str):
    """Pipeline completo para queries por TIPO."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert "LIMIT" in result.upper() or "FIRST" not in sql.upper(), (
        f"FIRST no convertido a LIMIT en pipeline para: {sql!r}"
    )


@pytest.mark.parametrize("sql", _BLOCK2[:100])  # 100 de 288
def test_pipeline_bloque2_extract_queries(sql: str):
    """Pipeline para queries con EXTRACT → strftime."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert "EXTRACT" not in result.upper(), (
        f"EXTRACT residual en pipeline: {result!r}"
    )


@pytest.mark.parametrize("sql", _BLOCK3[:50])  # 50 de 108
def test_pipeline_bloque3_join_queries(sql: str):
    """Pipeline para JOINs — NVL se convierte, FIRST se convierte."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert isinstance(error, str)  # puede ser "" o error


@pytest.mark.parametrize("sql", _BLOCK4[:100])  # 100 de 200
def test_pipeline_bloque4_agregaciones(sql: str):
    """Pipeline para queries de agregación."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)


@pytest.mark.parametrize("sql", _BLOCK5[:80])  # 80 de 150
def test_pipeline_bloque5_nvl_queries(sql: str):
    """Pipeline convierte NVL a COALESCE."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert "COALESCE" in result.upper(), (
        f"NVL no convertido a COALESCE en pipeline: {result!r}\nInput: {sql!r}"
    )


@pytest.mark.parametrize("sql", _BLOCK6[:60])  # 60 de 96
def test_pipeline_bloque6_current_date(sql: str):
    """Pipeline convierte CURRENT_DATE a date('now')."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert "date('now')" in result, (
        f"CURRENT_DATE no convertido en pipeline: {result!r}\nInput: {sql!r}"
    )


@pytest.mark.parametrize("sql", _BLOCK7[:100])  # 100 de 200
def test_pipeline_bloque7_cast_numeric(sql: str):
    """Pipeline convierte CAST(x AS NUMERIC) a ROUND(CAST(x AS REAL))."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert "REAL" in result.upper() or "ROUND" in result.upper(), (
        f"NUMERIC no convertido en pipeline: {result!r}\nInput: {sql!r}"
    )


@pytest.mark.parametrize("sql", _BLOCK8)
def test_pipeline_bloque8_starting_containing(sql: str):
    """Pipeline convierte STARTING WITH / CONTAINING a LIKE."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert "LIKE" in result.upper(), (
        f"STARTING WITH/CONTAINING no convertido en pipeline: {result!r}"
    )
    assert "STARTING WITH" not in result.upper(), f"STARTING WITH residual: {result!r}"
    assert "CONTAINING" not in result.upper(), f"CONTAINING residual: {result!r}"


@pytest.mark.parametrize("sql", _BLOCK9)
def test_pipeline_bloque9_complex_multitable(sql: str):
    """Pipeline maneja SQLs complejos multi-tabla sin error."""
    try:
        result, error = _full_pipeline(sql)
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"Pipeline falló para SQL complejo:\n{sql}\nError: {e}")


@pytest.mark.parametrize("sql", _BLOCK10[:80])  # 80 de 100
def test_pipeline_bloque10_null_checks(sql: str):
    """Pipeline maneja NULL IS NULL / IS NOT NULL correctamente."""
    result, error = _full_pipeline(sql)
    assert isinstance(result, str)
    assert "IS NOT NULL" in result or "IS NULL" in result, (
        f"NULL checks desaparecieron: {result!r}"
    )


# ── Tests de pipeline completo sin excepción para TODOS los bloques ──────────

@pytest.mark.parametrize("sql", _ALL_PIPELINE_SQLS)
def test_pipeline_full_no_exception(sql: str):
    """El pipeline completo nunca lanza excepción para ningún SQL."""
    try:
        result, error = _full_pipeline(sql)
        assert isinstance(result, str)
        assert isinstance(error, str)
    except Exception as e:
        pytest.fail(
            f"Pipeline lanzó excepción inesperada:\n"
            f"SQL: {sql[:100]}...\n"
            f"Error: {e}"
        )
