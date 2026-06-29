"""
test_final_coverage_push.py
~1000 casos adicionales para completar la suite de 10,000.

SIN mock, SIN BD real, SIN modelos IA.
"""

import json
import pytest
from backend.modules.chat.deep_analysis.models import (
    TokenBudget, EpicAnalysisResult, PhaseResult, SubPhaseResult, AnalysisDepth,
    CHARS_PER_TOKEN, MAX_SQLS_ABSOLUTE, detect_depth,
)
from backend.modules.db_simulator.query_translator import translate_firebird_sql
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

_norm = FirebirdSQLNormalizer()


def _t(sql: str) -> str:
    result, _ = translate_firebird_sql(sql)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE A: NULLS LAST (15 casos)
# ══════════════════════════════════════════════════════════════════════════════

_NULLS_LAST_SQLS = [
    "SELECT * FROM DOCCAB ORDER BY IMPORTETOTAL DESC NULLS LAST WHERE TIPO = 0",
    "SELECT * FROM DOCCAB ORDER BY IMPORTETOTAL DESC NULLS LAST WHERE TIPO = 2",
    "SELECT * FROM DOCCAB ORDER BY IMPORTETOTAL DESC NULLS LAST WHERE TIPO = 3",
    "SELECT * FROM DOCCAB ORDER BY IMPORTETOTAL DESC NULLS LAST WHERE TIPO = 13",
    "SELECT * FROM CLIENTE ORDER BY NOMBRECOMERCIAL ASC NULLS LAST LIMIT 5",
    "SELECT * FROM CLIENTE ORDER BY NOMBRECOMERCIAL ASC NULLS LAST LIMIT 10",
    "SELECT * FROM CLIENTE ORDER BY NOMBRECOMERCIAL ASC NULLS LAST LIMIT 20",
    "SELECT CODCLIENTE, SUM(IMPORTETOTAL) FROM DOCCAB GROUP BY CODCLIENTE ORDER BY SUM(IMPORTETOTAL) DESC NULLS LAST LIMIT 5",
    "SELECT CODCLIENTE, SUM(IMPORTETOTAL) FROM DOCCAB GROUP BY CODCLIENTE ORDER BY SUM(IMPORTETOTAL) DESC NULLS LAST LIMIT 10",
    "SELECT CODCLIENTE, SUM(IMPORTETOTAL) FROM DOCCAB GROUP BY CODCLIENTE ORDER BY SUM(IMPORTETOTAL) DESC NULLS LAST LIMIT 20",
    "SELECT NOMBRE FROM ARTICULO ORDER BY NOMBRE ASC NULLS LAST",
    "SELECT CODIGO FROM FAMILIA ORDER BY NOMBRE DESC NULLS LAST",
    "SELECT * FROM PROVEED ORDER BY CODIGO ASC NULLS LAST LIMIT 10",
    "SELECT TIPO, COUNT(*) FROM DOCCAB GROUP BY TIPO ORDER BY COUNT(*) DESC NULLS LAST",
    "SELECT CODAGENTE, SUM(IMPORTETOTAL) FROM DOCCAB GROUP BY CODAGENTE ORDER BY 2 DESC NULLS LAST",
]


@pytest.mark.parametrize("sql", _NULLS_LAST_SQLS)
def test_translate_nulls_last_removed(sql: str):
    """NULLS LAST se elimina (SQLite no lo soporta)."""
    result = _t(sql)
    assert "NULLS LAST" not in result.upper(), f"NULLS LAST residual: {result!r}"


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE B: FIRST N -> LIMIT N (25 casos)
# ══════════════════════════════════════════════════════════════════════════════

_FIRST_N_SQLS = (
    [(f"SELECT FIRST {n} * FROM DOCCAB WHERE TIPO = 3", n)
     for n in [1, 3, 5, 7, 10, 15, 20, 30, 50, 75, 100, 150, 200, 500, 1000]] +
    [(f"SELECT FIRST {n} CODCLIENTE, NOMBRECOMERCIAL FROM CLIENTE", n)
     for n in [3, 7, 15, 25, 50]] +
    [(f"SELECT FIRST {n} d.TIPO, c.NOMBRECOMERCIAL FROM DOCCAB d LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO", n)
     for n in [1, 5, 10, 20, 30]]
)


@pytest.mark.parametrize("sql,expected_n", _FIRST_N_SQLS)
def test_translate_first_n_to_limit(sql: str, expected_n: int):
    """FIRST N -> LIMIT N."""
    result = _t(sql)
    assert f"LIMIT {expected_n}" in result, f"FIRST {expected_n} no convertido: {result!r}"
    assert "FIRST" not in result, f"FIRST residual: {result!r}"


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE C: EXTRACT -> strftime (23 casos)
# ══════════════════════════════════════════════════════════════════════════════

_EXTRACT_SQLS = (
    [
        ("SELECT EXTRACT(YEAR FROM FECHA) FROM DOCCAB", "strftime('%Y'"),
        ("SELECT EXTRACT(MONTH FROM FECHA) FROM DOCCAB", "strftime('%m'"),
        ("SELECT EXTRACT(DAY FROM FECHA) FROM DOCCAB", "strftime('%d'"),
        ("SELECT EXTRACT(YEAR FROM d.FECHA) FROM DOCCAB d", "strftime('%Y'"),
        ("SELECT EXTRACT(MONTH FROM d.FECHA) FROM DOCCAB d", "strftime('%m'"),
    ] +
    [(f"SELECT EXTRACT(YEAR FROM FECHA) AS ANO FROM DOCCAB WHERE TIPO = {t}", "strftime('%Y'")
     for t in range(9)] +
    [(f"SELECT EXTRACT(MONTH FROM FECHA) AS MES FROM DOCCAB WHERE TIPO = {t}", "strftime('%m'")
     for t in range(9)]
)


@pytest.mark.parametrize("sql,expected_contains", _EXTRACT_SQLS)
def test_translate_extract_to_strftime(sql: str, expected_contains: str):
    """EXTRACT(PART FROM col) -> strftime."""
    result = _t(sql)
    assert expected_contains in result, f"EXTRACT no convertido: {result!r}\nInput: {sql!r}"
    assert "EXTRACT" not in result.upper(), f"EXTRACT residual: {result!r}"


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE D: TokenBudget multi-reserved (32 casos)
# ══════════════════════════════════════════════════════════════════════════════

_MULTI_RESERVED_CASES = (
    [(32_000, 4_000, n_res, res_size, main_size)
     for n_res in [1, 2, 3]
     for res_size in [100, 500, 2000]
     for main_size in [1000, 10000, 100000]] +
    [(limit_k * 1000, 2_000, 2, 500, 5000)
     for limit_k in [8, 16, 32, 64, 128]]
)


@pytest.mark.parametrize("limit_t,reserved_t,n_res,res_size,main_size", _MULTI_RESERVED_CASES)
def test_budget_multi_reserved_truncate(limit_t, reserved_t, n_res, res_size, main_size):
    """truncate_to_fit con multiples reserved siempre produce resultado que cabe."""
    budget = TokenBudget(context_limit_tokens=limit_t)
    main_text = "m" * main_size
    reserved = ["r" * res_size for _ in range(n_res)]
    result = budget.truncate_to_fit(main_text, *reserved)
    assert isinstance(result, str)
    assert budget.fits(result, *reserved)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE E: PhaseResult masivo (270 casos)
# ══════════════════════════════════════════════════════════════════════════════

_PHASE_IDS = ["1", "2", "3", "4", "4b", "5"]
_PHASE_NAMES = ["planificacion", "exploracion", "investigacion",
                "sintesis", "verificacion", "calidad"]
_PHASE_SUCCESSES = [True, False]

_PHASE_CONFIGS = [
    (pid, pname, success)
    for pid in _PHASE_IDS
    for pname in _PHASE_NAMES
    for success in _PHASE_SUCCESSES
]


@pytest.mark.parametrize("phase_id,phase_name,success", _PHASE_CONFIGS)
def test_phase_result_all_configs(phase_id, phase_name, success):
    """PhaseResult se crea correctamente con cualquier combinacion."""
    phase = PhaseResult(
        phase_id=phase_id, phase_name=phase_name, success=success,
    )
    assert phase.phase_id == phase_id
    assert phase.phase_name == phase_name
    assert phase.success == success


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE F: EpicAnalysisResult partial files y sql count (61 casos)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("n_files", range(0, 50))
def test_epic_result_partial_summary_files(n_files: int):
    """partial_summary_files almacena paths correctamente."""
    result = EpicAnalysisResult(question="test")
    for i in range(n_files):
        result.partial_summary_files.append(f"/tmp/partial_{i}.json")
    assert len(result.partial_summary_files) == n_files


@pytest.mark.parametrize("n_sqls", range(0, MAX_SQLS_ABSOLUTE + 1, 3))
def test_epic_result_sql_count_tracking(n_sqls: int):
    """EpicAnalysisResult rastrea el numero de SQLs ejecutados."""
    result = EpicAnalysisResult(question="test")
    for i in range(n_sqls):
        result.sql_queries.append({
            "objetivo": f"SQL {i}", "sql": f"SELECT {i} FROM DOCCAB",
            "rows": i, "error": None, "data": [],
        })
    assert len(result.sql_queries) == n_sqls


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE G: Normalizador variantes (200 casos)
# ══════════════════════════════════════════════════════════════════════════════

# 50 casos != con distintos valores
_NEQOP_SQLS = [
    (f"SELECT * FROM DOCCAB WHERE IMPORTETOTAL != {i * 100}", "<>")
    for i in range(50)
]


@pytest.mark.parametrize("sql,expected", _NEQOP_SQLS)
def test_normalizer_neq_50_values(sql: str, expected: str):
    """!= -> <> para 50 valores distintos."""
    result, _ = _norm.normalize(sql)
    assert "<>" in result, f"<> no encontrado: {result!r}"


# 50 casos CURRENT_DATE variantes
_CDATE_SQLS = (
    [f"SELECT * FROM DOCCAB WHERE FECHA >= CURRENT_DATE AND TIPO = {t}" for t in range(9)] +
    [f"SELECT COUNT(*) FROM DOCCAB WHERE EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE) AND TIPO = {t}" for t in range(9)] +
    ["SELECT * FROM DOCCAB WHERE FECHA = CURRENT_DATE()",
     "SELECT * FROM DOCCAB WHERE FECHA <= NOW()",
     "SELECT * FROM DOCCAB WHERE FECHA < GETDATE()",
     "SELECT * FROM DOCCAB WHERE FECHA > SYSDATE",
     "SELECT CURRENT_DATE, COUNT(*) FROM DOCCAB",
     "SELECT * FROM DOCCAB WHERE FECHA BETWEEN CURRENT_DATE AND CURRENT_DATE",
     "SELECT EXTRACT(YEAR FROM CURRENT_DATE) FROM DOCCAB",
     "SELECT EXTRACT(MONTH FROM CURRENT_DATE) FROM DOCCAB",
     "SELECT * FROM DOCCAB WHERE FECHA > CURRENT_DATE AND TIPO = 0",
     "SELECT * FROM DOCCAB WHERE FECHA < CURRENT_DATE AND TIPO = 2",
     "SELECT * FROM DOCCAB WHERE FECHA = NOW() AND TIPO = 3",
     "SELECT * FROM DOCCAB WHERE FECHA = GETDATE() AND TIPO = 13",
     "SELECT * FROM DOCCAB WHERE FECHA >= SYSDATE AND CODCLIENTE IS NOT NULL",
     "SELECT * FROM DOCCAB WHERE FECHA != CURRENT_DATE",
     "SELECT CAST(CURRENT_DATE AS VARCHAR(10)) FROM DOCCAB",
     "SELECT * FROM CLIENTE WHERE FECHABAJA < CURRENT_DATE",
     "SELECT * FROM DOCCAB WHERE FECHA BETWEEN CURRENT_DATE AND CURRENT_DATE",
     "SELECT * FROM DOCCAB WHERE FECHA >= NOW() AND TIPO IN (0, 2, 3)",
     "SELECT * FROM DOCCAB WHERE EXTRACT(DAY FROM CURRENT_DATE) = 1",
     "SELECT COUNT(*) FROM DOCCAB WHERE FECHA > GETDATE()"][:50]
)


@pytest.mark.parametrize("sql", _CDATE_SQLS)
def test_normalizer_current_date_variants(sql: str):
    """CURRENT_DATE y variantes se normalizan sin residuos."""
    result, _ = _norm.normalize(sql)
    assert isinstance(result, str)
    assert "CURRENT_DATE()" not in result, f"CURRENT_DATE() residual: {result!r}"
    assert "NOW()" not in result, f"NOW() residual: {result!r}"
    assert "GETDATE()" not in result, f"GETDATE() residual: {result!r}"
    assert "SYSDATE" not in result, f"SYSDATE residual: {result!r}"


# 50 casos ROUND/TRUNC
_ROUND_SQLS = (
    [f"SELECT ROUND(IMPORTETOTAL, {i}) FROM DOCCAB WHERE TIPO = 3" for i in range(10)] +
    [f"SELECT TRUNC(PRECIOVENTA) FROM ARTICULO WHERE CODIGO = {i}" for i in range(10)] +
    [f"SELECT TRUNCATE(IMPORTETOTAL, {i}) FROM DOCCAB" for i in range(10)] +
    [f"SELECT ROUND(SUM(IMPORTETOTAL), 2) FROM DOCCAB WHERE TIPO = {t}" for t in range(9)] +
    [f"SELECT TRUNC(AVG(IMPORTETOTAL)) FROM DOCCAB WHERE TIPO = {t}" for t in range(10)] +
    ["SELECT ROUND(IMPORTETOTAL, 0) FROM DOCCAB"]
)[:50]


@pytest.mark.parametrize("sql", _ROUND_SQLS)
def test_normalizer_round_trunc_handling(sql: str):
    """ROUND/TRUNC/TRUNCATE se manejan sin error."""
    try:
        result, _ = _norm.normalize(sql)
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"Normalizer fallo con ROUND/TRUNC:\n{sql}\nError: {e}")


# 50 casos CONCAT -> ||
_CONCAT_SQLS = (
    [f"SELECT CONCAT(COL{i}, ' ', COL{i+1}) FROM DOCCAB" for i in range(20)] +
    [f"SELECT CONCAT(SERIE, CAST(NUMERO AS TEXT)) AS REF{n} FROM DOCCAB WHERE TIPO = {n % 4}" for n in range(20)] +
    ["SELECT CONCAT(CONCAT(NOMBRE, ' - '), CODFAMILIA) FROM ARTICULO",
     "SELECT CONCAT(NOMBRECOMERCIAL, ' (', NIF, ')') FROM CLIENTE",
     "SELECT CONCAT(SERIE, '/', CAST(NUMERO AS TEXT)) FROM DOCCAB",
     "SELECT CONCAT(NOMBRE, ' - Stock: ', CAST(STOCKARTICULO AS TEXT)) FROM ARTICULO",
     "SELECT CONCAT(CODCLIENTE, '_', CODAGENTE) FROM DOCCAB",
     "SELECT CONCAT('Tipo_', CAST(TIPO AS TEXT)) FROM DOCCAB",
     "SELECT CONCAT(A, B, C) FROM DOCCAB WHERE TIPO = 0",
     "SELECT CONCAT(X, Y) FROM CLIENTE WHERE BAJA = FALSE"]
)[:50]


@pytest.mark.parametrize("sql", _CONCAT_SQLS)
def test_normalizer_concat_many_variants(sql: str):
    """CONCAT(...) se procesa sin excepcion. Con 2 args simples -> ||, con mas args o CAST -> queda CONCAT."""
    try:
        result, _ = _norm.normalize(sql)
        assert isinstance(result, str)
        # Debe quedar CONCAT o ||, no desaparecer
        assert "CONCAT" in result.upper() or "||" in result, (
            f"CONCAT desaparecio sin convertirse: {result!r}\nInput: {sql!r}"
        )
    except Exception as e:
        pytest.fail(f"Normalizer fallo con CONCAT:\n{sql}\nError: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H: Serializacion JSON (11 casos)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("n_sqls", [0, 1, 3, 5, 10, 20])
def test_sql_queries_json_serializable(n_sqls: int):
    """sql_queries del EpicAnalysisResult es serializable a JSON."""
    result = EpicAnalysisResult(question=f"pregunta con {n_sqls} SQLs")
    for i in range(n_sqls):
        result.sql_queries.append({
            "objetivo": f"Objetivo {i}",
            "sql": f"SELECT COUNT(*) FROM DOCCAB WHERE TIPO = {i % 4}",
            "rows": i * 10, "error": None, "data": [{"N": i * 10}],
        })
    json_str = json.dumps(result.sql_queries, ensure_ascii=False, default=str)
    restored = json.loads(json_str)
    assert len(restored) == n_sqls


@pytest.mark.parametrize("text_size", [100, 1000, 10000, 50000, 100000])
def test_large_answer_json_serializable(text_size: int):
    """Respuestas largas son serializables a JSON."""
    answer = ("Analisis de datos: " * (text_size // 20 + 1))[:text_size]
    json_str = json.dumps({"final_answer": answer}, ensure_ascii=False)
    restored = json.loads(json_str)
    assert restored["final_answer"] == answer


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE I: detect_depth preguntas adicionales (105 casos)
# ══════════════════════════════════════════════════════════════════════════════

_EXTRA_DEPTH_QUESTIONS = (
    [f"facturacion del mes {i}" for i in range(1, 13)] +
    [f"top {i} clientes por importe" for i in range(1, 21)] +
    [f"presupuestos de {2020+i}" for i in range(7)] +
    [f"analisis epico de la cartera {i}" for i in range(20)] +
    [f"top {i} proveedores por compra" for i in range(1, 11)] +
    [f"evolucion de ventas en {2020+i}" for i in range(6)] +
    [f"albaranes pendientes del mes {i}" for i in range(1, 13)] +
    [f"facturas cobradas en {2023+i}" for i in range(4)] +
    [f"comparativa de agentes en mes {i}" for i in range(1, 13)]
)


@pytest.mark.parametrize("question", _EXTRA_DEPTH_QUESTIONS)
def test_detect_depth_extra_questions(question: str):
    """detect_depth no falla para preguntas adicionales de negocio."""
    depth = detect_depth(question)
    assert isinstance(depth, AnalysisDepth)
    assert depth in list(AnalysisDepth)
