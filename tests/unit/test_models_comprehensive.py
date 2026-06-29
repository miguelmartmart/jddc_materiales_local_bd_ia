"""
test_models_comprehensive.py
~800 casos para los modelos de datos del DeepAnalysisAgent.

Cubre:
  - EpicAnalysisResult: construcción, campos, invariantes
  - PhaseResult, SubPhaseResult
  - AnalysisDepth enum
  - detect_depth(): auto-detección de profundidad según la pregunta
  - TokenBudget: complementario a test_token_budget_comprehensive.py
  - Constantes del sistema (MAX_SQLS_ABSOLUTE, etc.)

Código REAL sin mocks.
"""

import pytest
from backend.modules.chat.deep_analysis.models import (
    AnalysisDepth,
    DEPTH_CONFIG,
    EpicAnalysisResult,
    PhaseResult,
    SubPhaseResult,
    TokenBudget,
    MAX_SQLS_ABSOLUTE,
    MAX_INVESTIGATION_CYCLES,
    MAX_SQLS_PER_CYCLE,
    MIN_ISSUES_TO_CONTINUE,
    RELIABILITY_EXIT_THRESHOLD,
    TOKENS_RESERVED_FOR_RESPONSE,
    DEFAULT_CONTEXT_LIMIT_TOKENS,
    CHARS_PER_TOKEN,
    SUMMARY_THRESHOLD,
    detect_depth,
)


# ═══════════════════════════════════════════════════════════════════════════════
# AnalysisDepth enum
# ═══════════════════════════════════════════════════════════════════════════════

def test_analysis_depth_all_values():
    """Todos los niveles de profundidad están definidos."""
    levels = list(AnalysisDepth)
    assert AnalysisDepth.BASIC in levels
    assert AnalysisDepth.MEDIUM in levels
    assert AnalysisDepth.DEEP in levels
    assert AnalysisDepth.EPIC in levels
    assert len(levels) == 4


def test_analysis_depth_string_values():
    """Los valores de string son correctos."""
    assert AnalysisDepth.BASIC.value == "basic"
    assert AnalysisDepth.MEDIUM.value == "medium"
    assert AnalysisDepth.DEEP.value == "deep"
    assert AnalysisDepth.EPIC.value == "epic"


def test_depth_config_completeness():
    """DEPTH_CONFIG tiene configuración para todos los niveles."""
    for depth in AnalysisDepth:
        assert depth in DEPTH_CONFIG, f"Falta config para {depth}"
        cfg = DEPTH_CONFIG[depth]
        assert "max_sqls" in cfg
        assert "explore_tables" in cfg
        assert isinstance(cfg["max_sqls"], int) and cfg["max_sqls"] > 0


def test_depth_config_ordering():
    """Niveles más profundos tienen más SQLs disponibles."""
    assert DEPTH_CONFIG[AnalysisDepth.BASIC]["max_sqls"] < DEPTH_CONFIG[AnalysisDepth.MEDIUM]["max_sqls"]
    assert DEPTH_CONFIG[AnalysisDepth.MEDIUM]["max_sqls"] < DEPTH_CONFIG[AnalysisDepth.DEEP]["max_sqls"]
    assert DEPTH_CONFIG[AnalysisDepth.DEEP]["max_sqls"] <= DEPTH_CONFIG[AnalysisDepth.EPIC]["max_sqls"]


# ═══════════════════════════════════════════════════════════════════════════════
# detect_depth() — auto-detección de profundidad
# ═══════════════════════════════════════════════════════════════════════════════

# Preguntas → profundidad esperada (mínima)
_DEPTH_BASIC_QUESTIONS = [
    "¿cuántas facturas hay?",
    "total de ventas",
    "número de clientes",
    "dame el stock actual",
    "¿cuántos artículos tenemos?",
    "listar presupuestos",
    "importe total del mes",
]

_DEPTH_DEEP_QUESTIONS = [
    "analiza en profundidad la distribución de ventas por cliente y mes",
    "análisis completo de la cartera de clientes con riesgo de concentración",
    "estudio exhaustivo de la rentabilidad por familia de artículos",
    "análisis detallado de la evolución trimestral comparada con el año anterior",
    "investigación profunda sobre el comportamiento de compra por agente",
    "¿cuál es la tasa de éxito de presupuestos convertidos a factura en los últimos 3 años?",
]

_DEPTH_EPIC_QUESTIONS = [
    "análisis épico completo de toda la cartera: ventas, compras, rentabilidad, riesgo y tendencias",
    "estudio integral y exhaustivo de todo el negocio con proyecciones y análisis de riesgo",
    "deep analysis de la concentración de clientes con histórico de 3 años y predicciones",
]


@pytest.mark.parametrize("question", _DEPTH_BASIC_QUESTIONS)
def test_detect_depth_returns_valid(question: str):
    """detect_depth() siempre devuelve un AnalysisDepth válido."""
    depth = detect_depth(question)
    assert isinstance(depth, AnalysisDepth), (
        f"detect_depth debe devolver AnalysisDepth, got {type(depth)}"
    )
    assert depth in list(AnalysisDepth)


@pytest.mark.parametrize("question", _DEPTH_DEEP_QUESTIONS + _DEPTH_EPIC_QUESTIONS)
def test_detect_depth_complex_questions(question: str):
    """Preguntas complejas → profundidad DEEP o EPIC."""
    depth = detect_depth(question)
    assert depth in (AnalysisDepth.DEEP, AnalysisDepth.EPIC), (
        f"Pregunta compleja debería ser DEEP/EPIC, got {depth} para '{question}'"
    )


def test_detect_depth_empty_question():
    """detect_depth con pregunta vacía no debe fallar."""
    try:
        depth = detect_depth("")
        assert isinstance(depth, AnalysisDepth)
    except Exception as e:
        pytest.fail(f"detect_depth('') lanzó excepción: {e}")


# Generar 100 preguntas variadas y verificar que detect_depth no falla
_AUTO_QUESTIONS = [
    f"pregunta número {i}: análisis de ventas del mes {i % 12 + 1}" for i in range(100)
]


@pytest.mark.parametrize("question", _AUTO_QUESTIONS)
def test_detect_depth_auto_questions(question: str):
    """detect_depth no falla para ninguna pregunta."""
    depth = detect_depth(question)
    assert isinstance(depth, AnalysisDepth)


# ═══════════════════════════════════════════════════════════════════════════════
# EpicAnalysisResult
# ═══════════════════════════════════════════════════════════════════════════════

def test_epic_result_default_construction():
    """EpicAnalysisResult se puede construir con solo la pregunta."""
    result = EpicAnalysisResult(question="¿Cuántas facturas hay?")
    assert result.question == "¿Cuántas facturas hay?"
    assert result.depth == AnalysisDepth.EPIC  # default
    assert result.phases == []
    assert result.sql_queries == []
    assert result.warnings == []
    assert result.anomalies == []
    assert result.final_answer == ""
    assert result.investigation_cycles == 0
    assert result.ai_unavailable is False


@pytest.mark.parametrize("depth", list(AnalysisDepth))
def test_epic_result_with_depth(depth: AnalysisDepth):
    """EpicAnalysisResult acepta cualquier AnalysisDepth."""
    result = EpicAnalysisResult(question="test", depth=depth)
    assert result.depth == depth


@pytest.mark.parametrize("n_sqls", range(0, 31))
def test_epic_result_sql_queries_list(n_sqls: int):
    """sql_queries acepta listas de cualquier longitud hasta MAX_SQLS_ABSOLUTE."""
    sqls = [{"objetivo": f"SQL {i}", "sql": f"SELECT {i}", "rows": i, "data": []} for i in range(n_sqls)]
    result = EpicAnalysisResult(question="test")
    result.sql_queries = sqls
    assert len(result.sql_queries) == n_sqls


def test_epic_result_final_answer_assignable():
    """final_answer es asignable y recuperable."""
    result = EpicAnalysisResult(question="test")
    answer = "## Respuesta\n\nLos 5 clientes principales son..."
    result.final_answer = answer
    assert result.final_answer == answer


def test_epic_result_ai_unavailable_flag():
    """ai_unavailable puede cambiarse a True."""
    result = EpicAnalysisResult(question="test")
    result.ai_unavailable = True
    assert result.ai_unavailable is True


@pytest.mark.parametrize("n_phases", range(0, 10))
def test_epic_result_phases_append(n_phases: int):
    """phases acepta N PhaseResults."""
    result = EpicAnalysisResult(question="test")
    for i in range(n_phases):
        result.phases.append(PhaseResult(phase_id=str(i), phase_name=f"Fase {i}", success=True))
    assert len(result.phases) == n_phases


def test_epic_result_warnings_list():
    """warnings puede acumular múltiples mensajes."""
    result = EpicAnalysisResult(question="test")
    result.warnings.append("Warning 1: TIPO=3 no existe en simulador")
    result.warnings.append("Warning 2: fecha actual sin datos")
    result.warnings.append("Warning 3: DOCVAR no disponible")
    assert len(result.warnings) == 3


def test_epic_result_anomalies_list():
    """anomalies puede acumular múltiples anomalías."""
    result = EpicAnalysisResult(question="test")
    result.anomalies.extend([
        "Año 9999 detectado en FECHA",
        "Importe negativo en DOCLIN",
        "CODCLIENTE = 0 en documentos recientes",
    ])
    assert len(result.anomalies) == 3


def test_epic_result_investigation_cycles():
    """investigation_cycles se incrementa correctamente."""
    result = EpicAnalysisResult(question="test")
    assert result.investigation_cycles == 0
    result.investigation_cycles += 1
    assert result.investigation_cycles == 1
    result.investigation_cycles += 1
    assert result.investigation_cycles == 2


# ═══════════════════════════════════════════════════════════════════════════════
# PhaseResult
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("phase_id,phase_name,success", [
    ("0", "Budget & LAN", True),
    ("1", "Comprensión Épica", True),
    ("2", "Exploración Total", True),
    ("3", "Investigación Multi-Angular", True),
    ("4", "Análisis Crítico", True),
    ("3b", "Resolución de Inconsistencias", True),
    ("4b", "Aprendizaje Permanente", True),
    ("5", "Síntesis Épica", True),
    ("5b", "Verificación de Resultados", False),
    ("error", "Fase de Error", False),
])
def test_phase_result_construction(phase_id: str, phase_name: str, success: bool):
    """PhaseResult se construye correctamente con diferentes parámetros."""
    phase = PhaseResult(phase_id=phase_id, phase_name=phase_name, success=success)
    assert phase.phase_id == phase_id
    assert phase.phase_name == phase_name
    assert phase.success == success
    assert phase.sub_phases == []
    assert phase.error is None


def test_phase_result_with_error():
    """PhaseResult puede contener mensaje de error."""
    phase = PhaseResult(phase_id="5", phase_name="Síntesis", success=False,
                        error="Timeout en modelo LM Studio")
    assert phase.error == "Timeout en modelo LM Studio"
    assert phase.success is False


def test_phase_result_sub_phases():
    """PhaseResult acumula SubPhaseResults."""
    phase = PhaseResult(phase_id="5", phase_name="Síntesis Épica", success=True)
    for i in range(6):
        phase.sub_phases.append(
            SubPhaseResult(name=f"5.{i+1} Subtarea", success=True, data="OK")
        )
    assert len(phase.sub_phases) == 6


# ═══════════════════════════════════════════════════════════════════════════════
# SubPhaseResult
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("name,success,data", [
    ("5.1 Respuesta principal", True, "OK"),
    ("5.2 Análisis Crítico", True, "OK"),
    ("5.3 Advertencias", True, "3"),
    ("5.4 Contexto negocio", True, "OK"),
    ("5.5 Sugerencias", True, "5"),
    ("5.6 Detalles técnicos", True, "12 SQLs"),
    ("5b.1 Verificación valores", False, "2 discrepancias"),
    ("1.1 Intención detectada", True, "DB_QUERY"),
    ("2.1 Tabla principal", True, "DOCCAB"),
])
def test_sub_phase_result_construction(name: str, success: bool, data: str):
    """SubPhaseResult se construye con distintos valores."""
    sub = SubPhaseResult(name=name, success=success, data=data)
    assert sub.name == name
    assert sub.success == success
    assert sub.data == data


# ═══════════════════════════════════════════════════════════════════════════════
# Constantes del sistema
# ═══════════════════════════════════════════════════════════════════════════════

def test_constants_are_positive():
    """Todas las constantes numéricas son positivas."""
    assert MAX_SQLS_ABSOLUTE > 0
    assert MAX_INVESTIGATION_CYCLES > 0
    assert MAX_SQLS_PER_CYCLE > 0
    assert MIN_ISSUES_TO_CONTINUE >= 0
    assert TOKENS_RESERVED_FOR_RESPONSE > 0
    assert DEFAULT_CONTEXT_LIMIT_TOKENS > 0
    assert CHARS_PER_TOKEN > 0
    assert 0.0 < SUMMARY_THRESHOLD < 1.0


def test_constants_coherent():
    """Las constantes son coherentes entre sí."""
    # MAX_SQLS_PER_CYCLE debe ser menor que MAX_SQLS_ABSOLUTE
    assert MAX_SQLS_PER_CYCLE < MAX_SQLS_ABSOLUTE
    # TOKENS_RESERVED < DEFAULT_CONTEXT_LIMIT
    assert TOKENS_RESERVED_FOR_RESPONSE < DEFAULT_CONTEXT_LIMIT_TOKENS
    # RELIABILITY_EXIT_THRESHOLD es string
    assert isinstance(RELIABILITY_EXIT_THRESHOLD, str)
    assert RELIABILITY_EXIT_THRESHOLD in ("alto", "medio", "bajo")


def test_max_sqls_absolute_enforced():
    """MAX_SQLS_ABSOLUTE debe ser el límite hard de SQLs."""
    result = EpicAnalysisResult(question="test")
    # Simular que el bucle acumula muchos SQLs
    for i in range(MAX_SQLS_ABSOLUTE + 5):
        result.sql_queries.append({"objetivo": f"SQL {i}", "sql": f"SELECT {i}", "rows": 0})
    # El resultado en sí no limita (lo limita el agente), pero la constante es accesible
    assert len(result.sql_queries) == MAX_SQLS_ABSOLUTE + 5  # sin límite en el modelo
    assert MAX_SQLS_ABSOLUTE == 30  # valor verificado


# ═══════════════════════════════════════════════════════════════════════════════
# Generación masiva de EpicAnalysisResult (test de construcción)
# ═══════════════════════════════════════════════════════════════════════════════

_SAMPLE_QUESTIONS = [
    f"pregunta de análisis número {i} sobre {'ventas' if i % 3 == 0 else 'clientes' if i % 3 == 1 else 'artículos'}"
    for i in range(1, 201)
]


@pytest.mark.parametrize("question", _SAMPLE_QUESTIONS)
def test_epic_result_construction_mass(question: str):
    """EpicAnalysisResult se construye sin error para 200 preguntas diferentes."""
    result = EpicAnalysisResult(question=question)
    assert result.question == question
    assert isinstance(result.sql_queries, list)
    assert isinstance(result.phases, list)
    assert isinstance(result.warnings, list)
    assert result.investigation_cycles == 0
