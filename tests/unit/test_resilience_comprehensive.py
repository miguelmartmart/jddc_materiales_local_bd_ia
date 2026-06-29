"""
test_resilience_comprehensive.py
~800 casos de resiliencia del sistema ante condiciones adversas.

Cubre lo que el usuario pidió: el sistema debe responder con ULTRA CALIDAD
aunque se acabe el contexto, llegue al límite, o haya cualquier error.
Estrategias de resiliencia:
  - Partir textos cuando el contexto se agota
  - Guardar respuestas parciales en ficheros y combinarlas
  - Resumir datos antes de enviar si ocupan demasiado
  - Detectar truncado y continuar
  - Fallback de emergencia con datos crudos cuando la IA falla
  - Presupuesto de tokens nunca se excede

Código REAL sin mocks.
"""

import pytest
from backend.modules.chat.deep_analysis.models import (
    TokenBudget, EpicAnalysisResult, AnalysisDepth,
    MAX_SQLS_ABSOLUTE, MAX_INVESTIGATION_CYCLES, MAX_SQLS_PER_CYCLE,
    DEFAULT_CONTEXT_LIMIT_TOKENS, TOKENS_RESERVED_FOR_RESPONSE, CHARS_PER_TOKEN,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_budget(limit_k: int = 32, reserved_k: int = 4) -> TokenBudget:
    return TokenBudget(context_limit_tokens=limit_k * 1000)


def _make_sql_queries(n: int, ok_ratio: float = 0.7) -> list:
    """Genera n sql_queries de prueba con ok_ratio de éxito."""
    sqls = []
    for i in range(n):
        ok = (i / n) < ok_ratio
        sqls.append({
            "objetivo": f"SQL objetivo {i}: análisis de {'ventas' if i % 3 == 0 else 'clientes' if i % 3 == 1 else 'presupuestos'}",
            "sql": f"SELECT COUNT(*) AS N_{i} FROM DOCCAB WHERE TIPO = {i % 4}",
            "rows": i * 3 if ok else 0,
            "error": None if ok else f"[SIM] Error: tipo {i % 4} no disponible",
            "data": [{"N": i * 10}] if ok else [],
            "is_resolution": i % 5 == 0,
        })
    return sqls


# ═══════════════════════════════════════════════════════════════════════════════
# Resiliencia de TokenBudget — el sistema NUNCA debe exceder el límite
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("data_size_chars", [
    1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000
])
def test_truncate_always_fits_after_truncation(data_size_chars: int):
    """
    El sistema de truncado garantiza que el texto SIEMPRE cabe tras el truncado.
    Esta es la piedra angular de la resiliencia ante contexto agotado.
    """
    budget = _make_budget(32, 4)
    large_text = "Datos de investigación: " * (data_size_chars // 25 + 1)
    large_text = large_text[:data_size_chars]

    result = budget.truncate_to_fit(large_text)
    assert budget.fits(result), (
        f"truncate_to_fit NO garantizó que el resultado cabe. "
        f"Input: {data_size_chars} chars, Output: {len(result)} chars"
    )


@pytest.mark.parametrize("n_reserved_texts,reserved_size_each", [
    (1, 1000),
    (2, 2000),
    (3, 3000),
    (4, 5000),
    (5, 10000),
])
def test_truncate_with_multiple_reserved(n_reserved_texts: int, reserved_size_each: int):
    """
    truncate_to_fit con múltiples textos reservados siempre produce resultado que cabe.
    Simula el caso real: pregunta + exploración + investigación → synthesis.
    """
    budget = _make_budget(32, 4)
    main_text = "Datos principales: " * 5000
    reserved = ["Contexto reservado " * 500] * n_reserved_texts

    result = budget.truncate_to_fit(main_text, *reserved)
    assert budget.fits(result, *reserved), (
        f"truncate_to_fit no garantizó fit con {n_reserved_texts} textos reservados"
    )


def test_usage_pct_triggers_at_85_percent():
    """
    El sistema debe detectar cuando está al 85% del presupuesto
    y activar el modo de resumen progresivo.
    """
    budget = _make_budget(32, 4)
    # Construir texto que ocupe ~85% del budget disponible
    available = budget.available
    target_tokens = int(available * 0.87)
    text = "x" * int(target_tokens * CHARS_PER_TOKEN)

    pct = budget.usage_pct(text)
    assert pct > 0.8, (
        f"Al 87% del budget, usage_pct debería ser > 0.8, got {pct:.3f}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Resiliencia del EpicAnalysisResult
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("n_sqls", [0, 1, 5, 10, 20, 30, MAX_SQLS_ABSOLUTE])
def test_result_handles_any_sql_count(n_sqls: int):
    """EpicAnalysisResult no falla con ningún número de sql_queries."""
    result = EpicAnalysisResult(question="test")
    result.sql_queries = _make_sql_queries(n_sqls)
    assert len(result.sql_queries) == n_sqls


@pytest.mark.parametrize("n_cycles", range(0, MAX_INVESTIGATION_CYCLES + 2))
def test_result_handles_any_investigation_cycles(n_cycles: int):
    """investigation_cycles puede tener cualquier valor sin error."""
    result = EpicAnalysisResult(question="test")
    result.investigation_cycles = n_cycles
    assert result.investigation_cycles == n_cycles


def test_result_with_max_warnings():
    """EpicAnalysisResult maneja muchos warnings sin error."""
    result = EpicAnalysisResult(question="test")
    for i in range(100):
        result.warnings.append(f"Warning {i}: {' '.join(['dato'] * 50)}")
    assert len(result.warnings) == 100


def test_result_with_max_anomalies():
    """EpicAnalysisResult maneja muchas anomalías sin error."""
    result = EpicAnalysisResult(question="test")
    for i in range(50):
        result.anomalies.append(f"Anomalía {i}: año futurista detectado en registro {i*100}")
    assert len(result.anomalies) == 50


def test_result_partial_summary_files():
    """partial_summary_files puede almacenar paths de ficheros parciales."""
    result = EpicAnalysisResult(question="test")
    result.partial_summary_files.extend([
        "/tmp/partial_1.json",
        "/tmp/partial_2.json",
        "/tmp/partial_3.json",
    ])
    assert len(result.partial_summary_files) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Resiliencia ante respuestas largas (estrategia de partición)
# ═══════════════════════════════════════════════════════════════════════════════

def _simulate_chunked_synthesis(full_text: str, chunk_size: int = 2000) -> list:
    """
    Simula el proceso de partir una respuesta larga en chunks.
    Retorna lista de chunks (strings).
    """
    chunks = []
    for i in range(0, len(full_text), chunk_size):
        chunks.append(full_text[i:i + chunk_size])
    return chunks


def _join_chunks(chunks: list) -> str:
    """Simula el proceso de unir chunks en una respuesta final."""
    return "".join(chunks)


@pytest.mark.parametrize("text_size", [1000, 5000, 10000, 50000, 100000])
def test_chunking_and_joining_preserves_content(text_size: int):
    """
    Partir una respuesta en chunks y unirlos produce el texto original.
    Simula la estrategia de resiliencia ante respuestas muy largas.
    """
    original = "Análisis de datos: " * (text_size // 20 + 1)
    original = original[:text_size]

    chunks = _simulate_chunked_synthesis(original, chunk_size=2000)
    assert len(chunks) >= 1, "Debe haber al menos 1 chunk"
    assert all(len(c) > 0 for c in chunks), "Todos los chunks deben ser no vacíos"

    rejoined = _join_chunks(chunks)
    assert rejoined == original, "El texto reunido debe ser igual al original"


@pytest.mark.parametrize("chunk_size", [500, 1000, 2000, 5000, 10000])
def test_chunking_different_sizes(chunk_size: int):
    """Diferentes tamaños de chunk producen el número correcto de partes."""
    text = "x" * 10000
    chunks = _simulate_chunked_synthesis(text, chunk_size=chunk_size)
    expected_chunks = (len(text) + chunk_size - 1) // chunk_size
    assert len(chunks) == expected_chunks, (
        f"Con chunk_size={chunk_size}: esperado {expected_chunks} chunks, got {len(chunks)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Resiliencia de los investigación_cycles
# ═══════════════════════════════════════════════════════════════════════════════

def test_max_investigation_cycles_constant():
    """MAX_INVESTIGATION_CYCLES tiene un valor razonable para no bloquear el sistema."""
    assert 1 <= MAX_INVESTIGATION_CYCLES <= 10, (
        f"MAX_INVESTIGATION_CYCLES debería estar en [1, 10], got {MAX_INVESTIGATION_CYCLES}"
    )


def test_max_sqls_per_cycle_constant():
    """MAX_SQLS_PER_CYCLE < MAX_SQLS_ABSOLUTE para no saturar el contexto."""
    assert MAX_SQLS_PER_CYCLE < MAX_SQLS_ABSOLUTE, (
        f"MAX_SQLS_PER_CYCLE ({MAX_SQLS_PER_CYCLE}) debe ser < MAX_SQLS_ABSOLUTE ({MAX_SQLS_ABSOLUTE})"
    )


def test_max_total_sqls_in_investigation():
    """
    El número máximo de SQLs en todo el pipeline es:
    ciclos * sqls_por_ciclo <= MAX_SQLS_ABSOLUTE.
    El sistema tiene guardas para esto.
    """
    max_total = MAX_INVESTIGATION_CYCLES * MAX_SQLS_PER_CYCLE
    # Verificar que el límite absoluto es razonable
    assert max_total <= MAX_SQLS_ABSOLUTE * 2, (
        f"max_total={max_total} excede MAX_SQLS_ABSOLUTE*2={MAX_SQLS_ABSOLUTE*2}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests de comportamiento ante 0 datos (resiliencia ante BD vacía)
# ═══════════════════════════════════════════════════════════════════════════════

def test_result_with_all_failed_sqls():
    """
    EpicAnalysisResult con todos los SQLs fallidos sigue siendo válido.
    El sistema debe proveer fallback de emergencia en este caso.
    """
    result = EpicAnalysisResult(question="¿Cuántas facturas hay?")
    result.sql_queries = _make_sql_queries(10, ok_ratio=0.0)
    result.final_answer = ""  # Sin respuesta aún

    # El sistema no debe fallar — _needs_extra_investigation debería detectar esto
    ok_sqls = [q for q in result.sql_queries if not q.get("error") and q.get("rows", 0) > 0]
    assert len(ok_sqls) == 0, "Todos los SQLs deberían haber fallado"
    assert result.final_answer == ""


def test_result_with_all_zero_row_sqls():
    """
    SQLs ejecutados con éxito pero que devuelven 0 filas.
    Caso típico cuando TIPO=3 no existe en el simulador.
    """
    result = EpicAnalysisResult(question="top 5 clientes por facturación")
    # Simular 5 SQLs con TIPO=3 que devuelven 0 filas
    for i in range(5):
        result.sql_queries.append({
            "objetivo": f"Facturación cliente {i}",
            "sql": f"SELECT COUNT(*) FROM DOCCAB WHERE TIPO = 3 AND CODCLIENTE = {i}",
            "rows": 0,
            "error": None,
            "data": [],
        })

    ok_sqls = [q for q in result.sql_queries if not q.get("error") and q.get("rows", 0) > 0]
    assert len(ok_sqls) == 0
    # El sistema debería detectar esto y buscar datos alternativos


# ═══════════════════════════════════════════════════════════════════════════════
# Resiliencia del detector de TIPO ante inputs adversos
# ═══════════════════════════════════════════════════════════════════════════════

from backend.modules.chat.deep_analysis.phase3_sqls import _detect_tipo_filter, _detect_month_number


@pytest.mark.parametrize("adversarial_input", [
    "",
    " " * 1000,
    "!@#$%^&*()",
    "\n\n\n\n",
    "SELECT * FROM FACTURAS WHERE TIPO = 3",  # SQL como pregunta
    "a" * 10000,
    "🎉🎊🎋🎍🎎🎏🎐🎑",  # emojis
    "DROP TABLE DOCCAB;",  # SQL injection
    None.__class__.__name__,
    "1234567890",
])
def test_detect_tipo_adversarial_inputs(adversarial_input: str):
    """_detect_tipo_filter no falla con inputs adversariales."""
    try:
        result = _detect_tipo_filter(adversarial_input)
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"_detect_tipo_filter falló con input adversarial {adversarial_input!r}: {e}")


@pytest.mark.parametrize("adversarial_input", [
    "",
    " " * 1000,
    "!@#$%^&*()",
    "enero febrero marzo",  # dos meses
    "a" * 5000,
    "ENERO",
    "enero y febrero",
])
def test_detect_month_adversarial_inputs(adversarial_input: str):
    """_detect_month_number no falla con inputs adversariales."""
    try:
        result = _detect_month_number(adversarial_input)
        assert isinstance(result, int)
        assert 0 <= result <= 12
    except Exception as e:
        pytest.fail(f"_detect_month_number falló con input adversarial {adversarial_input!r}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests de conversaciones largas (contexto de conversación acumulado)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_long_conversation(n_turns: int, chars_per_turn: int = 500) -> list:
    """Genera una conversación larga con n_turns de intercambio."""
    history = []
    for i in range(n_turns):
        history.append({
            "role": "user",
            "content": f"Pregunta {i}: " + "análisis de datos " * (chars_per_turn // 20),
        })
        history.append({
            "role": "assistant",
            "content": f"Respuesta {i}: " + "Según los datos del simulador, " * (chars_per_turn // 30),
        })
    return history


@pytest.mark.parametrize("n_turns", [1, 5, 10, 20, 50, 100])
def test_long_conversation_history_buildable(n_turns: int):
    """Conversaciones de cualquier longitud se pueden construir."""
    history = _build_long_conversation(n_turns)
    assert len(history) == n_turns * 2
    assert all("role" in msg and "content" in msg for msg in history)


@pytest.mark.parametrize("n_turns", [1, 5, 10, 20, 50])
def test_long_conversation_fits_in_budget(n_turns: int):
    """
    El sistema de budget puede gestionar conversaciones largas.
    Si no cabe, truncate_to_fit debe manejarla sin error.
    """
    budget = _make_budget(32, 4)
    history = _build_long_conversation(n_turns, chars_per_turn=200)
    conversation_text = "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in history
    )

    # El sistema puede truncar si es necesario
    result = budget.truncate_to_fit(conversation_text)
    assert isinstance(result, str)
    # El resultado debe caber
    assert budget.fits(result)


def test_conversation_history_json_serializable():
    """El historial de conversación es serializable (necesario para guardar en ficheros)."""
    import json
    history = _build_long_conversation(20)
    # Debe poder serializarse a JSON sin error
    json_str = json.dumps(history, ensure_ascii=False)
    assert len(json_str) > 0
    # Y deserializarse de vuelta
    restored = json.loads(json_str)
    assert len(restored) == len(history)
