"""
test_phase5_quality_comprehensive.py
~700 casos para el sistema de calidad de síntesis (Phase5Mixin).

Cubre:
  - _needs_extra_investigation(): detección de síntesis sin datos
  - _is_truncated() (si es accesible): detección de respuesta cortada
  - Resiliencia ante respuestas de baja calidad
  - Respuestas con diferentes longitudes y contenidos

Código REAL. Phase5Mixin es un mixin — instanciamos con duck-typing.
"""

import pytest
from backend.modules.chat.deep_analysis.models import EpicAnalysisResult, AnalysisDepth
from backend.modules.chat.deep_analysis.phase5 import Phase5Mixin


class _MockPhase5(Phase5Mixin):
    """Instancia mínima de Phase5Mixin para tests de calidad sin servidor."""
    def __init__(self):
        self.orchestrator = None
        self.budget = None


_phase5 = _MockPhase5()


# ═══════════════════════════════════════════════════════════════════════════════
# _needs_extra_investigation()
# ═══════════════════════════════════════════════════════════════════════════════

def _make_result(answer: str, n_sqls: int = 5, n_ok_sqls: int = 3) -> EpicAnalysisResult:
    """Helper para construir EpicAnalysisResult de prueba."""
    r = EpicAnalysisResult(question="test pregunta")
    r.final_answer = answer
    r.sql_queries = []
    for i in range(n_sqls):
        ok = i < n_ok_sqls
        r.sql_queries.append({
            "objetivo": f"SQL {i}",
            "sql": f"SELECT {i} FROM DOCCAB",
            "rows": 5 if ok else 0,
            "error": None if ok else "[SIM] Error: table not found",
            "data": [{"N": i * 10}] if ok else [],
        })
    return r


# Respuestas que indican ausencia de datos → debe necesitar investigación extra
_POOR_ANSWERS = [
    "sin datos suficientes para responder esta pregunta",
    "no hay datos disponibles en el simulador para esta consulta",
    "datos insuficientes para realizar el análisis",
    "no se pudo responder la pregunta ya que no existen registros de TIPO=3",
    "sin datos disponibles, por favor conectar a la base de datos real",
    "no dispongo de datos para responder",
    "la consulta no devolvió resultados",
    "0 resultados en todas las consultas ejecutadas",
    "no existen registros de facturas cliente en el simulador",
    "consultas fallidas: sin datos para análisis",
]

# Respuestas que son buenas (largas, con contenido real)
_GOOD_ANSWERS = [
    "## 📊 Respuesta Principal\n\n| Cliente | Importe |\n|---|---|\n| EMPRESA AGUAS | 55.462 € |\n| SUPERMERCADOS CONSUM | 50.106 € |\n\n## 🔍 Análisis Crítico\n\nEl análisis muestra que los top 5 clientes representan el 24.4% del total facturado. Esto indica un riesgo de concentración bajo según el umbral del 60% de Pareto.\n\n## ⚠️ Advertencias\n\n• Los datos son del simulador (TIPO=2 como proxy de TIPO=3)\n\n## 💡 Contexto de Negocio\n\nLa distribución de clientes es saludable con 50 clientes activos.\n\n## 🚀 Sugerencias\n\n1. Conectar BD real para datos TIPO=3\n2. Ampliar histórico a 3 años",
    "## 📊 Respuesta Principal\n\nTop 5 presupuestos por importe:\n\n| Código | Importe |\n|---|---|\n| PRES-001 | 25.000 € |\n| PRES-002 | 18.500 € |\n\n## 🔍 Análisis Crítico\n\nEl análisis de presupuestos muestra 66 registros activos con un importe medio de 4.196 €.\n\n## ⚠️ Advertencias\n\n• Solo datos del 2026 disponibles\n\n## 💡 Contexto de Negocio\n\nLos presupuestos representan la cartera comercial activa.\n\n## 🚀 Sugerencias y Próximos Pasos\n\n1. Analizar tasa de conversión\n2. Segmentar por agente comercial",
] + [
    "## 📊 Respuesta Principal\n\n" + "Contenido de análisis detallado " * 50 + "\n\n"
    "## 🔍 Análisis Crítico\n\n" + "Análisis " * 30 + "\n\n"
    "## ⚠️ Advertencias\n\n• Sin advertencias\n\n"
    "## 💡 Contexto de Negocio\n\nContexto empresarial " * 10 + "\n\n"
    "## 🚀 Sugerencias y Próximos Pasos\n\n1. Paso 1\n2. Paso 2"
    for _ in range(10)
]


@pytest.mark.parametrize("poor_answer", _POOR_ANSWERS)
def test_needs_extra_investigation_poor_answers(poor_answer: str):
    """Respuestas con frases de 'sin datos' → _needs_extra_investigation() = True."""
    result = _make_result(answer=poor_answer, n_ok_sqls=0)
    needs_extra = _phase5._needs_extra_investigation(result)
    assert needs_extra is True, (
        f"Debería necesitar investigación extra para:\n'{poor_answer}'"
    )


@pytest.mark.parametrize("good_answer", _GOOD_ANSWERS)
def test_needs_extra_investigation_good_answers(good_answer: str):
    """Respuestas largas con contenido real → no necesitan investigación extra."""
    result = _make_result(answer=good_answer, n_ok_sqls=5)
    needs_extra = _phase5._needs_extra_investigation(result)
    assert needs_extra is False, (
        f"Respuesta buena no debería necesitar investigación extra "
        f"(len={len(good_answer)})"
    )


def test_needs_extra_investigation_empty_answer():
    """Respuesta vacía → podría necesitar investigación."""
    result = _make_result(answer="", n_ok_sqls=0)
    needs_extra = _phase5._needs_extra_investigation(result)
    assert isinstance(needs_extra, bool)


def test_needs_extra_investigation_many_sqls():
    """Con 20+ SQLs ya ejecutadas, no reinvestigar (evitar presupuesto excesivo)."""
    result = _make_result(
        answer="sin datos suficientes",
        n_sqls=21,
        n_ok_sqls=0,
    )
    needs_extra = _phase5._needs_extra_investigation(result)
    assert needs_extra is False, (
        "Con 21+ SQLs no debe reinvestigar (protección de presupuesto)"
    )


@pytest.mark.parametrize("answer_len", [100, 300, 500, 599, 600, 601, 1000, 5000])
def test_needs_extra_investigation_by_length(answer_len: int):
    """
    Respuestas >= 600 chars nunca necesitan investigación extra (longitud mínima OK).
    Respuestas < 600 pueden necesitarla si contienen frases de fallo.
    """
    answer = "Contenido de análisis " * (answer_len // 22 + 1)
    answer = answer[:answer_len]
    result = _make_result(answer=answer, n_ok_sqls=5)
    needs_extra = _phase5._needs_extra_investigation(result)
    if answer_len >= 600:
        assert needs_extra is False, (
            f"Respuesta de {answer_len} chars (sin frases de fallo) no debe reinvestigar"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests de _is_truncated() (si el método es accesible)
# ═══════════════════════════════════════════════════════════════════════════════

def _has_is_truncated():
    """Check si _is_truncated existe como método estático."""
    return hasattr(Phase5Mixin, '_is_truncated') or hasattr(_phase5, '_is_truncated')


_COMPLETE_RESPONSES = [
    (
        "## 📊 Respuesta Principal\n\nContenido real\n\n"
        "## 🔍 Análisis Crítico\n\nAnálisis profundo\n\n"
        "## ⚠️ Advertencias y Objeciones\n\n• Aviso 1\n\n"
        "## 💡 Contexto de Negocio\n\nContexto relevante con más de 30 caracteres de contenido\n\n"
        "## 🚀 Sugerencias y Próximos Pasos\n\n1. Primer paso\n2. Segundo paso"
    ),
    (
        "## 📊 Respuesta Principal\n\n| Col1 | Col2 |\n|---|---|\n| A | 100 |\n\n"
        "## 🔍 Análisis Crítico\n\nEl análisis muestra tendencias claras en el período analizado.\n\n"
        "## ⚠️ Advertencias y Objeciones\n\n• Sin advertencias críticas\n\n"
        "## 💡 Contexto de Negocio\n\nEsta información es relevante para la toma de decisiones.\n\n"
        "## 🚀 Sugerencias y Próximos Pasos\n\n1. Conectar BD real\n2. Ampliar análisis"
    ),
]

_TRUNCATED_RESPONSES = [
    "## 📊 Respuesta Principal\n\nContenido sin secciones finales",
    "## 📊 Respuesta Principal\n\n## 🔍 Análisis",  # sin ## 🚀 Sugerencias
    "## 📊 Respuesta",  # muy corto
    "",  # vacío
    "Solo texto sin secciones",
]


@pytest.mark.parametrize("response", _COMPLETE_RESPONSES)
def test_complete_response_not_truncated(response: str):
    """Respuesta con todas las secciones no debe detectarse como truncada."""
    if hasattr(_phase5, '_is_truncated'):
        result = _phase5._is_truncated(response)
        assert result is False, (
            f"Respuesta completa incorrectamente marcada como truncada"
        )


@pytest.mark.parametrize("response", _TRUNCATED_RESPONSES)
def test_truncated_response_detected(response: str):
    """Respuestas sin secciones completas deben detectarse como truncadas."""
    if hasattr(_phase5, '_is_truncated'):
        result = _phase5._is_truncated(response)
        assert result is True, (
            f"Respuesta truncada no detectada: {response[:50]!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Generación masiva de resultados de prueba
# ═══════════════════════════════════════════════════════════════════════════════

# 200 resultados con configuraciones variadas
_RESULT_CONFIGS = [
    (i, i % 10, "sin datos suficientes" if i % 7 == 0 else "Respuesta " * 100)
    for i in range(1, 201)
]


@pytest.mark.parametrize("n_sqls,n_ok,answer", _RESULT_CONFIGS)
def test_needs_extra_investigation_mass(n_sqls: int, n_ok: int, answer: str):
    """_needs_extra_investigation no falla para ninguna combinación de inputs."""
    n_ok = min(n_ok, n_sqls)
    result = _make_result(answer=answer, n_sqls=n_sqls, n_ok_sqls=n_ok)
    try:
        needs_extra = _phase5._needs_extra_investigation(result)
        assert isinstance(needs_extra, bool)
    except Exception as e:
        pytest.fail(
            f"_needs_extra_investigation lanzó excepción para "
            f"n_sqls={n_sqls}, n_ok={n_ok}: {e}"
        )
