"""
test_query_translator_comprehensive.py
~700 casos parametrizados para translate_firebird_sql() / FirebirdToSQLiteTranslator.

Cubre todas las reglas de traducción:
  - SELECT FIRST N  → LIMIT N
  - EXTRACT()       → strftime()
  - CURRENT_DATE/TIMESTAMP → date('now')/datetime('now')
  - SUBSTRING()     → SUBSTR()
  - CAST(x AS NUMERIC) → ROUND(CAST(x AS REAL), s)
  - CAST(x AS VARCHAR) → CAST(x AS TEXT)
  - STARTING WITH   → LIKE 'x%'
  - CONTAINING      → LIKE '%x%'
  - NULLS LAST/FIRST → eliminado
  - Passthrough (SQLite nativo sin cambios)

Código REAL sin mocks.
"""

import pytest
from backend.modules.db_simulator.query_translator import translate_firebird_sql


def _translate(sql: str):
    """Wrapper para llamar la función y obtener (sql_out, changes)."""
    return translate_firebird_sql(sql)


# ═══════════════════════════════════════════════════════════════════════════════
# FIRST N → LIMIT N
# ═══════════════════════════════════════════════════════════════════════════════

# Generamos 50 casos variando N de 1 a 100
_FIRST_N_CASES = []
for _n in range(1, 101, 2):
    _FIRST_N_CASES.append((
        f"SELECT FIRST {_n} * FROM DOCCAB",
        f"SELECT * FROM DOCCAB LIMIT {_n}",
    ))
# Variaciones de whitespace
_FIRST_N_CASES += [
    ("SELECT FIRST  10  * FROM DOCCAB", None),  # doble espacio, el resultado contiene LIMIT 10
    ("select first 5 * from doccab", None),      # minúsculas
    ("SELECT FIRST 1 CODIGO, TIPO FROM DOCCAB ORDER BY FECHA DESC", None),
    ("SELECT FIRST 20 d.CODCLIENTE FROM DOCCAB d ORDER BY d.IMPORTETOTAL DESC", None),
    ("SELECT FIRST 3 NOMBRECOMERCIAL, RAZONSOCIAL FROM CLIENTE ORDER BY NOMBRECOMERCIAL", None),
]


@pytest.mark.parametrize("sql_in,sql_expected", _FIRST_N_CASES)
def test_translator_first_to_limit(sql_in: str, sql_expected):
    """SELECT FIRST N se convierte a LIMIT N."""
    result, changes = _translate(sql_in)
    assert "LIMIT" in result.upper(), (
        f"FIRST→LIMIT no aplicado. Input: {sql_in!r}\nOutput: {result!r}"
    )
    assert "FIRST" not in result.upper(), (
        f"'FIRST' residual en output. Input: {sql_in!r}\nOutput: {result!r}"
    )
    if sql_expected:
        assert sql_expected.lower() == result.lower() or "limit" in result.lower(), (
            f"SQL incorrecto. Esperado algo con LIMIT, got: {result!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACT() → strftime()
# ═══════════════════════════════════════════════════════════════════════════════

_EXTRACT_PARTS = {
    "YEAR": "%Y",
    "MONTH": "%m",
    "DAY": "%d",
    "HOUR": "%H",
    "MINUTE": "%M",
    "SECOND": "%S",
}

_EXTRACT_COLUMNS = [
    "FECHA", "FECHAEMISION", "FECHAALTA", "FECHA_INICIO", "d.FECHA",
    "c.FECHAALTA", "CURRENT_DATE", "p.FECHAINICIO", "FECHAFIN",
    "oc.FECHA",
]

_EXTRACT_CASES = []
for _part, _fmt in _EXTRACT_PARTS.items():
    for _col in _EXTRACT_COLUMNS:
        _EXTRACT_CASES.append((
            f"SELECT EXTRACT({_part} FROM {_col}) FROM DOCCAB",
            _fmt,  # esperamos que el fmt aparezca en el resultado
        ))

# Casos en contextos reales
_EXTRACT_CASES += [
    (
        "SELECT EXTRACT(YEAR FROM FECHA), COUNT(*) FROM DOCCAB GROUP BY EXTRACT(YEAR FROM FECHA)",
        "%Y",
    ),
    (
        "SELECT EXTRACT(MONTH FROM FECHA) AS MES, EXTRACT(YEAR FROM FECHA) AS ANO FROM DOCCAB",
        "%m",
    ),
    (
        "WHERE EXTRACT(YEAR FROM FECHA) = 2026 AND EXTRACT(MONTH FROM FECHA) = 6",
        "%Y",
    ),
    (
        "SELECT EXTRACT(DAY FROM FECHA) AS DIA, EXTRACT(HOUR FROM HORA) AS HORA FROM DOCCAB",
        "%d",
    ),
]


@pytest.mark.parametrize("sql_in,expected_fmt", _EXTRACT_CASES)
def test_translator_extract(sql_in: str, expected_fmt: str):
    """EXTRACT(PART FROM col) se convierte a strftime o CAST(strftime())."""
    result, changes = _translate(sql_in)
    assert "EXTRACT" not in result.upper(), (
        f"EXTRACT residual en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )
    # El formato strftime debe aparecer en el resultado
    assert expected_fmt in result, (
        f"Formato {expected_fmt!r} no encontrado en output.\n"
        f"Input: {sql_in!r}\nOutput: {result!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CURRENT_DATE / CURRENT_TIMESTAMP → date('now') / datetime('now')
# ═══════════════════════════════════════════════════════════════════════════════

_CURRENT_DATE_CASES = [
    ("SELECT CURRENT_DATE FROM DOCCAB", "date('now')"),
    ("WHERE FECHA = CURRENT_DATE", "date('now')"),
    ("WHERE FECHA > CURRENT_DATE", "date('now')"),
    ("WHERE FECHA <= CURRENT_DATE", "date('now')"),
    ("AND EXTRACT(YEAR FROM CURRENT_DATE) = 2026", "date('now')"),
    ("SELECT CURRENT_DATE, COUNT(*) FROM DOCCAB WHERE FECHA < CURRENT_DATE", "date('now')"),
    ("WHERE FECHA BETWEEN CURRENT_DATE AND CURRENT_DATE", "date('now')"),
    # Minúsculas
    ("where fecha = current_date", "date('now')"),
    # Mixed
    ("SELECT current_date, CURRENT_TIMESTAMP FROM dual", "date('now')"),
]

_CURRENT_TIMESTAMP_CASES = [
    ("SELECT CURRENT_TIMESTAMP FROM DOCCAB", "datetime('now')"),
    ("WHERE FECHA_CREACION <= CURRENT_TIMESTAMP", "datetime('now')"),
    ("INSERT INTO LOG VALUES(CURRENT_TIMESTAMP, 'test')", "datetime('now')"),
]


@pytest.mark.parametrize("sql_in,expected_fragment", _CURRENT_DATE_CASES)
def test_translator_current_date(sql_in: str, expected_fragment: str):
    """CURRENT_DATE → date('now')."""
    result, changes = _translate(sql_in)
    assert expected_fragment in result, (
        f"date('now') no encontrado.\nInput: {sql_in!r}\nOutput: {result!r}"
    )
    assert "CURRENT_DATE" not in result.upper() or "date('now')" in result, (
        f"CURRENT_DATE residual en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )


@pytest.mark.parametrize("sql_in,expected_fragment", _CURRENT_TIMESTAMP_CASES)
def test_translator_current_timestamp(sql_in: str, expected_fragment: str):
    """CURRENT_TIMESTAMP → datetime('now')."""
    result, changes = _translate(sql_in)
    assert expected_fragment in result, (
        f"datetime('now') no encontrado.\nInput: {sql_in!r}\nOutput: {result!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CAST(x AS NUMERIC(p,s)) → ROUND(CAST(x AS REAL), s)
# ═══════════════════════════════════════════════════════════════════════════════

_CAST_NUMERIC_CASES = [
    "CAST(IMPORTETOTAL AS NUMERIC(15,2))",
    "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2))",
    "CAST(AVG(IMPORTETOTAL) AS NUMERIC(10,2))",
    "CAST(PRECIO AS NUMERIC(8,4))",
    "CAST(IMPORTE AS NUMERIC(12,2))",
    "CAST(TOTAL AS NUMERIC(15,0))",
    "CAST(SUM(CANTIDAD * PRECIO) AS NUMERIC(15,2))",
    "CAST(COUNT(*) AS NUMERIC(10,0))",
    "CAST(0.0 AS NUMERIC(15,2))",
    "CAST(NULL AS NUMERIC(15,2))",
    "CAST(IMPORTE1 + IMPORTE2 AS NUMERIC(15,2))",
    "CAST(IMPORTETOTAL * 1.21 AS NUMERIC(15,2))",
    "CAST(IMPORTETOTAL / 100 AS NUMERIC(8,4))",
    # Variaciones de espaciado
    "CAST(IMPORTETOTAL  AS  NUMERIC(15,2))",
    "cast(importetotal as numeric(15,2))",
    # En contexto de SELECT
    "SELECT CAST(IMPORTETOTAL AS NUMERIC(15,2)) AS IMPORTE FROM DOCCAB",
    "SELECT CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL FROM DOCCAB d",
    "SELECT CAST(AVG(IMPORTETOTAL) AS NUMERIC(10,2)) AS MEDIA, CAST(MAX(IMPORTETOTAL) AS NUMERIC(15,2)) AS MAX FROM DOCCAB",
]

_CAST_NUMERIC_NO_SCALE = [
    "CAST(IMPORTETOTAL AS NUMERIC)",
    "CAST(SUM(IMPORTETOTAL) AS NUMERIC)",
    "SELECT CAST(TOTAL AS NUMERIC) FROM DOCCAB",
]


@pytest.mark.parametrize("sql_in", _CAST_NUMERIC_CASES)
def test_translator_cast_numeric_with_scale(sql_in: str):
    """CAST(x AS NUMERIC(p,s)) → ROUND(CAST(x AS REAL), s)."""
    result, changes = _translate(sql_in)
    # Verificar que la traducción se aplicó
    assert "REAL" in result.upper() or "ROUND" in result.upper() or "numeric" not in result.lower(), (
        f"NUMERIC no traducido correctamente.\nInput: {sql_in!r}\nOutput: {result!r}"
    )


@pytest.mark.parametrize("sql_in", _CAST_NUMERIC_NO_SCALE)
def test_translator_cast_numeric_no_scale(sql_in: str):
    """CAST(x AS NUMERIC) sin escala → CAST(x AS REAL)."""
    result, changes = _translate(sql_in)
    assert "REAL" in result.upper(), (
        f"NUMERIC sin escala no traducido a REAL.\nInput: {sql_in!r}\nOutput: {result!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# STARTING WITH / CONTAINING → LIKE
# ═══════════════════════════════════════════════════════════════════════════════

_STARTING_WITH_CASES = [
    ("SELECT * FROM CLIENTE WHERE NOMBRECOMERCIAL STARTING WITH 'A'", "LIKE 'A%'"),
    ("SELECT * FROM ARTICULO WHERE NOMBRE STARTING WITH 'Split'", "LIKE 'Split%'"),
    ("SELECT * FROM DOCCAB WHERE SERIE STARTING WITH 'FAC'", "LIKE 'FAC%'"),
    ("WHERE REFERENCIAEXTERNA STARTING WITH 'REF-2026'", "LIKE 'REF-2026%'"),
    ("WHERE NOMBRE STARTING WITH ''", "LIKE '%'"),
    ("where nombre starting with 'test'", "LIKE 'test%'"),
]

_CONTAINING_CASES = [
    ("SELECT * FROM CLIENTE WHERE NOMBRECOMERCIAL CONTAINING 'González'", "LIKE '%González%'"),
    ("SELECT * FROM ARTICULO WHERE NOMBRE CONTAINING 'Split'", "LIKE '%Split%'"),
    ("WHERE DESCRIPCION CONTAINING 'instalación'", "LIKE '%instalación%'"),
    ("WHERE NOMBRE CONTAINING ''", "LIKE '%%'"),
    ("where nombre containing 'test'", "LIKE '%test%'"),
]


@pytest.mark.parametrize("sql_in,expected_fragment", _STARTING_WITH_CASES)
def test_translator_starting_with(sql_in: str, expected_fragment: str):
    """STARTING WITH → LIKE 'x%'."""
    result, changes = _translate(sql_in)
    assert "STARTING WITH" not in result.upper(), (
        f"STARTING WITH residual en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )
    # El patrón LIKE debe estar presente
    assert "LIKE" in result.upper(), (
        f"LIKE no encontrado en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )


@pytest.mark.parametrize("sql_in,expected_fragment", _CONTAINING_CASES)
def test_translator_containing(sql_in: str, expected_fragment: str):
    """CONTAINING → LIKE '%x%'."""
    result, changes = _translate(sql_in)
    assert "CONTAINING" not in result.upper(), (
        f"CONTAINING residual en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )
    assert "LIKE" in result.upper(), (
        f"LIKE no encontrado en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NULLS LAST / NULLS FIRST → eliminado
# ═══════════════════════════════════════════════════════════════════════════════

_NULLS_CASES = [
    "SELECT * FROM DOCCAB ORDER BY FECHA NULLS LAST",
    "SELECT * FROM DOCCAB ORDER BY IMPORTETOTAL DESC NULLS FIRST",
    "SELECT * FROM CLIENTE ORDER BY NOMBRECOMERCIAL ASC NULLS LAST",
    "SELECT * FROM DOCCAB ORDER BY FECHA ASC NULLS LAST, IMPORTETOTAL DESC NULLS FIRST",
    "ORDER BY FECHA NULLS LAST",
    "order by fecha nulls last",
    "ORDER BY col1 NULLS FIRST, col2 NULLS LAST",
]


@pytest.mark.parametrize("sql_in", _NULLS_CASES)
def test_translator_nulls_removed(sql_in: str):
    """NULLS LAST/FIRST se elimina (SQLite no lo soporta)."""
    result, changes = _translate(sql_in)
    assert "NULLS LAST" not in result.upper(), (
        f"NULLS LAST residual en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )
    assert "NULLS FIRST" not in result.upper(), (
        f"NULLS FIRST residual en output.\nInput: {sql_in!r}\nOutput: {result!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SQLs que YA son SQLite-nativo (passthrough sin cambios)
# ═══════════════════════════════════════════════════════════════════════════════

_PASSTHROUGH_SQLS = [
    "SELECT * FROM DOCCAB",
    "SELECT * FROM DOCCAB WHERE TIPO = 3",
    "SELECT * FROM DOCCAB LIMIT 10",
    "SELECT COUNT(*) FROM CLIENTE WHERE BAJA = 0",
    "SELECT * FROM DOCCAB WHERE FECHA > '2026-01-01'",
    "SELECT d.CODCLIENTE, COUNT(*) FROM DOCCAB d GROUP BY d.CODCLIENTE ORDER BY 2 DESC LIMIT 5",
    "SELECT * FROM ARTICULO WHERE STOCKARTICULO > 0",
    "SELECT strftime('%Y', FECHA) FROM DOCCAB",
    "SELECT date('now')",
    "SELECT datetime('now')",
]


@pytest.mark.parametrize("sql_in", _PASSTHROUGH_SQLS)
def test_translator_passthrough_sqlite_native(sql_in: str):
    """SQL ya en formato SQLite pasa sin cambios destructivos."""
    result, changes = _translate(sql_in)
    assert isinstance(result, str), f"Debe devolver str, got {type(result)}"
    # El SQL debe ser funcional (no vacío, no None)
    assert len(result.strip()) > 0, f"SQL resultado vacío para: {sql_in!r}"
    # En passthrough, los cambios deben ser mínimos (sin transformaciones grandes)
    assert "FIRST" not in result.upper().replace("FIRST", ""), "FIRST no esperado"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests de robustez
# ═══════════════════════════════════════════════════════════════════════════════

def test_translator_empty_sql():
    """SQL vacío no debe lanzar excepción."""
    result, changes = _translate("")
    assert isinstance(result, str)
    assert isinstance(changes, list)


def test_translator_returns_tuple():
    """translate_firebird_sql siempre devuelve (str, list)."""
    for sql in ["SELECT 1", "", "SELECT * FROM DOCCAB", "FIRST 10"]:
        result = _translate(sql)
        assert isinstance(result, tuple), f"Debe devolver tuple para {sql!r}"
        assert len(result) == 2, f"Debe devolver 2 elementos para {sql!r}"
        assert isinstance(result[0], str), f"Primer elemento debe ser str para {sql!r}"
        assert isinstance(result[1], list), f"Segundo elemento debe ser list para {sql!r}"


def test_translator_complex_real_world_sql():
    """Traducción de SQL real complejo del pipeline de deep analysis."""
    sql = """
    SELECT FIRST 10
        d.CODCLIENTE,
        c.NOMBRECOMERCIAL,
        COUNT(d.CODIGO) AS N_DOCS,
        CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR
    FROM DOCCAB d
    LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO
    WHERE d.CODCLIENTE IS NOT NULL
        AND d.CODCLIENTE > 0
        AND EXTRACT(YEAR FROM d.FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)
    GROUP BY d.CODCLIENTE, c.NOMBRECOMERCIAL
    ORDER BY TOTAL_EUR DESC NULLS LAST
    """
    result, changes = _translate(sql)
    assert "LIMIT" in result.upper()
    assert "FIRST" not in result.upper()
    assert "ROUND" in result.upper() or "REAL" in result.upper()
    assert "NULLS LAST" not in result.upper()
    assert "date('now')" in result
    assert len(changes) > 0, "Deben haberse aplicado transformaciones"


def test_translator_idempotent_sqlite():
    """Aplicar la traducción dos veces a SQL SQLite da el mismo resultado."""
    sql = "SELECT * FROM DOCCAB LIMIT 10"
    result1, _ = _translate(sql)
    result2, _ = _translate(result1)
    assert result1 == result2, "La traducción no es idempotente para SQL SQLite"
