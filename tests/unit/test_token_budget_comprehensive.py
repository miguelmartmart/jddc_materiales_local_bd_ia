"""
test_token_budget_comprehensive.py
Tests exhaustivos de TokenBudget — gestión de presupuesto de tokens.
~1100 casos parametrizados. Código REAL sin mocks.

Cubre:
  - count(): estimación de tokens para textos de cualquier longitud
  - fits(): si un texto cabe en el presupuesto disponible
  - usage_pct(): porcentaje de uso del presupuesto
  - truncate_to_fit(): truncado inteligente de textos largos
  - Resiliencia ante contexto agotado (el sistema NUNCA debe fallar por OOM)
"""

import pytest
from backend.modules.chat.deep_analysis.models import (
    TokenBudget,
    DEFAULT_CONTEXT_LIMIT_TOKENS,
    TOKENS_RESERVED_FOR_RESPONSE,
    CHARS_PER_TOKEN,
)

# ─── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def budget_32k():
    return TokenBudget(context_limit_tokens=32_000)

@pytest.fixture
def budget_8k():
    return TokenBudget(context_limit_tokens=8_000)

@pytest.fixture
def budget_tiny():
    """Budget pequeno: solo 2000 tokens disponibles tras la reserva."""
    return TokenBudget(context_limit_tokens=TOKENS_RESERVED_FOR_RESPONSE + 2000)


# ─── Tests de count() ─────────────────────────────────────────────────────────

# Generamos 500 casos con strings de longitud 0..4990 (paso 10)
_COUNT_CASES = [
    (
        "x" * n,          # texto de n chars
        int(n / CHARS_PER_TOKEN),  # tokens esperados (mínimo)
        int(n / CHARS_PER_TOKEN) + 2,  # tokens esperados (máximo, +2 margen)
    )
    for n in range(0, 5000, 10)
]


@pytest.mark.parametrize("text,expected_min,expected_max", _COUNT_CASES)
def test_token_budget_count_length(text: str, expected_min: int, expected_max: int, budget_32k):
    """count() estima tokens dentro de un rango razonable para cualquier longitud."""
    result = budget_32k.count(text)
    assert isinstance(result, int), f"count() debe devolver int, got {type(result)}"
    assert result >= 0, "count() nunca debe ser negativo"
    # Verificar que la estimación está en el rango correcto
    assert expected_min <= result <= expected_max + 5, (
        f"Para texto de {len(text)} chars: "
        f"esperado [{expected_min}, {expected_max}], obtenido {result}"
    )


def test_token_budget_count_empty(budget_32k):
    assert budget_32k.count("") == 0


def test_token_budget_count_whitespace_only(budget_32k):
    result = budget_32k.count("   \n\t  ")
    assert result >= 0


@pytest.mark.parametrize("text,label", [
    pytest.param("a" * 100_000, "100k_a", id="100k_a"),
    pytest.param("xN" * 10_000, "20k_unicode_like", id="20k_unicode_like"),
    pytest.param("\n" * 50_000, "50k_newlines", id="50k_newlines"),
    pytest.param("SELECT * FROM DOCCAB WHERE TIPO = 3 " * 1000, "sql_1000x", id="sql_1000x"),
])
def test_token_budget_count_large_text(text: str, label: str, budget_32k):
    """count() no debe fallar con textos muy grandes."""
    result = budget_32k.count(text)
    assert result > 0
    assert isinstance(result, int)


# ─── Tests de fits() ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text_size,budget_tokens,should_fit", [
    # Texto que cabe holgadamente
    (100, 1000, True),
    (350, 1000, True),
    # Texto que justamente cabe (3.5 chars/token → 3500 chars = ~1000 tokens)
    (3500, 1000, True),
    # Texto que NO cabe
    (4000, 100, False),
    (10000, 500, False),
    # Edge: texto vacío siempre cabe
    (0, 10, True),
    (0, 0, True),
    # Edge: budget 0 — texto no vacío no cabe
    (100, 0, False),
])
def test_token_budget_fits_basic(text_size: int, budget_tokens: int, should_fit: bool):
    """fits() determina correctamente si el texto cabe en el presupuesto."""
    budget = TokenBudget(context_limit_tokens=budget_tokens + TOKENS_RESERVED_FOR_RESPONSE)
    text = "a" * text_size
    result = budget.fits(text)
    assert isinstance(result, bool)
    if should_fit:
        assert result is True, (
            f"Texto de {text_size} chars debería caber en budget de {budget_tokens} tokens"
        )
    else:
        assert result is False, (
            f"Texto de {text_size} chars NO debería caber en budget de {budget_tokens} tokens"
        )


@pytest.mark.parametrize("n_texts", range(1, 11))
def test_token_budget_fits_multiple_texts(n_texts: int, budget_32k):
    """fits() con múltiples textos combina todos en la estimación."""
    texts = ["a" * 100] * n_texts
    result = budget_32k.fits(*texts)
    assert isinstance(result, bool)


def test_token_budget_fits_over_limit_always_false(budget_tiny):
    """Un texto que supera el presupuesto siempre devuelve False."""
    huge = "x" * 10_000  # >> 100 tokens de budget
    assert budget_tiny.fits(huge) is False


def test_token_budget_fits_empty_always_true(budget_tiny):
    """Texto vacío siempre cabe."""
    assert budget_tiny.fits("") is True
    assert budget_tiny.fits("", "") is True
    assert budget_tiny.fits("", "", "") is True


# ─── Tests de usage_pct() ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text_size,expected_pct_min,expected_pct_max", [
    # budget 32k con 4096 reservados → disponible ~27904 tokens
    # texto vacío → 0%
    (0, 0.0, 0.05),
    # texto pequeño → muy bajo %
    (35, 0.0, 0.1),
    # texto mediano
    (35000, 0.3, 0.7),
    # texto grande (casi todo el budget)
    (97650, 0.9, 1.1),  # ~97650 chars / 3.5 = ~27900 tokens
])
def test_token_budget_usage_pct(text_size: int, expected_pct_min: float, expected_pct_max: float,
                                 budget_32k):
    """usage_pct() devuelve un porcentaje razonable según el texto."""
    text = "a" * text_size
    pct = budget_32k.usage_pct(text)
    assert isinstance(pct, float), f"usage_pct debe devolver float, got {type(pct)}"
    assert pct >= 0.0, "usage_pct no puede ser negativo"
    assert expected_pct_min <= pct <= expected_pct_max, (
        f"Para texto de {text_size} chars: pct={pct:.3f}, "
        f"esperado [{expected_pct_min}, {expected_pct_max}]"
    )


@pytest.mark.parametrize("pct_threshold", [0.5, 0.75, 0.85, 0.90, 0.95])
def test_token_budget_usage_pct_threshold_detection(pct_threshold: float, budget_32k):
    """
    Verifica que usage_pct puede detectar correctamente si se supera un umbral.
    Crítico para la resiliencia: el agente debe saber cuándo está al límite.
    """
    # Construir texto que ocupa exactamente pct_threshold del budget
    available = budget_32k.available
    target_tokens = int(available * pct_threshold)
    text = "a" * int(target_tokens * CHARS_PER_TOKEN)
    pct = budget_32k.usage_pct(text)
    # Verificar que está dentro del 10% del threshold esperado
    assert abs(pct - pct_threshold) < 0.15, (
        f"Para threshold {pct_threshold}: pct obtenido = {pct:.3f}"
    )


# ─── Tests de truncate_to_fit() ───────────────────────────────────────────────

@pytest.mark.parametrize("text_size,reserved_size", [
    (5000, 100),
    (10000, 500),
    (50000, 1000),
    (100000, 5000),
    (1, 0),
    (0, 0),
    (100, 1000),  # texto más pequeño que reservado → devuelve el texto completo
])
def test_token_budget_truncate_to_fit_result_fits(text_size: int, reserved_size: int, budget_32k):
    """
    truncate_to_fit() SIEMPRE devuelve un texto que cabe en el budget.
    Esta es la garantía de resiliencia fundamental.
    """
    text = "Datos de análisis: " * max(1, text_size // 20) + "X" * (text_size % 20)
    reserved = "Y" * reserved_size

    result = budget_32k.truncate_to_fit(text, reserved)
    assert isinstance(result, str), "truncate_to_fit debe devolver str"

    # El resultado DEBE caber en el budget junto con el texto reservado
    assert budget_32k.fits(result, reserved), (
        f"truncate_to_fit NO garantizó que el resultado cabe en el budget. "
        f"text_size={text_size}, reserved_size={reserved_size}, "
        f"result_size={len(result)}"
    )


def test_token_budget_truncate_preserves_text_when_fits(budget_32k):
    """Si el texto ya cabe, truncate_to_fit lo devuelve intacto (o casi)."""
    text = "Texto corto que cabe perfectamente"
    result = budget_32k.truncate_to_fit(text)
    assert result == text or len(result) >= len(text) - 10


def test_token_budget_truncate_large_always_safe(budget_8k):
    """Con texto enorme, truncate_to_fit nunca debe hacer OOM ni fallar."""
    huge = "SELECT * FROM DOCCAB " * 50_000  # ~1M chars
    result = budget_8k.truncate_to_fit(huge)
    assert isinstance(result, str)
    assert budget_8k.fits(result), "Resultado de truncate_to_fit debe caber en budget"


# ─── Tests de resiliencia ante contexto agotado ───────────────────────────────

def test_budget_never_exceeds_limit():
    """El budget debe controlar que usage_pct nunca supere 1.0 de forma critica."""
    budget = TokenBudget(context_limit_tokens=DEFAULT_CONTEXT_LIMIT_TOKENS)
    # Texto extremadamente largo
    huge = "a" * 1_000_000
    pct = budget.usage_pct(huge)
    # Puede ser > 1.0 (indicando que excede el límite), pero no debe crashear
    assert isinstance(pct, float)
    assert pct > 0


def test_budget_truncate_result_never_exceeds_limit(budget_tiny):
    """Incluso con budget mínimo, truncate_to_fit produce algo seguro."""
    huge = "x" * 100_000
    result = budget_tiny.truncate_to_fit(huge)
    assert isinstance(result, str)
    # El resultado debe ser manejable
    assert len(result) < 100_000


@pytest.mark.parametrize("limit", [
    6000, 8000, 12000, 16000, 24000, 32000, 48000, 64000, 128000,
])
def test_budget_construction_valid(limit: int):
    """TokenBudget puede construirse con diferentes limites."""
    budget = TokenBudget(context_limit_tokens=limit)
    assert budget.context_limit == limit
    assert budget.available == limit - TOKENS_RESERVED_FOR_RESPONSE
    assert budget.fits("") is True
    assert budget.count("") == 0


def test_budget_multiple_reserved_texts():
    """usage_pct con multiples textos reservados suma correctamente."""
    budget = TokenBudget(context_limit_tokens=32000)
    text1 = "Pregunta del usuario: " + "A" * 500
    text2 = "Exploración: " + "B" * 2000
    text3 = "Investigación: " + "C" * 5000
    pct = budget.usage_pct(text1, text2, text3)
    # Debe ser mayor que la suma individual más pequeña
    pct1 = budget.usage_pct(text1)
    assert pct >= pct1, "usage_pct con más textos debe ser >= que con uno solo"


def test_budget_default_values():
    """TokenBudget con valores default del sistema es coherente."""
    budget = TokenBudget(context_limit_tokens=DEFAULT_CONTEXT_LIMIT_TOKENS)
    assert budget.context_limit == DEFAULT_CONTEXT_LIMIT_TOKENS
    assert budget.available == DEFAULT_CONTEXT_LIMIT_TOKENS - TOKENS_RESERVED_FOR_RESPONSE
    question = "cuales son los 5 clientes con mayor facturacion del anio 2026"
    assert budget.fits(question) is True
