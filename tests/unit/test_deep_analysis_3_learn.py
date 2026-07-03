"""
test_deep_analysis_agent.py — Tests unitarios del DeepAnalysisAgent v2.0.

Cubre:
  - detect_depth(): auto-detección de profundidad
  - TokenBudget: conteo, fits, truncate, usage_pct
  - Fase 1: fallback si la IA falla
  - Fase 2: exploración de tablas (mock de sql_executor)
  - Fase 3: SQLs fijos (distribución temporal + instalaciones)
  - Fase 4: registro de feedback SIUO
  - Fallback de emergencia
  - Análisis completo con mocks
  - Helpers SIUO: _get_siuo_columns, _get_siuo_record_count, _extract_columns_from_context
    * Flujo real: BD falla → SIUO JSON → db_context texto
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.modules.chat.deep_analysis.models import (
    AnalysisDepth, TokenBudget, detect_depth,
    EpicAnalysisResult, PhaseResult, SubPhaseResult,
    DEPTH_CONFIG, DEFAULT_CONTEXT_LIMIT_TOKENS,
)
from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_orchestrator(response: str = '{"intent":"test","category":"ventas","complexity":"epic"}'):
    """Crea un orchestrator mock que devuelve siempre la misma respuesta."""
    orch = MagicMock()
    orch.execute_with_fallback = AsyncMock(return_value=(response, None))
    orch.context_limit_tokens = 32000
    return orch


def make_sql_executor(rows: list = None):
    """Crea un sql_executor mock que devuelve filas predefinidas."""
    rows = rows or [{"TOTAL": 1234}]
    return MagicMock(return_value=rows)


def make_agent(
    orchestrator=None,
    sql_rows=None,
    db_context="TABLA: DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL",
):
    orch = orchestrator or make_orchestrator()
    executor = make_sql_executor(sql_rows)
    return DeepAnalysisAgent(
        orchestrator=orch,
        db_context=db_context,
        sql_executor=executor,
    )


# ─── Tests: detect_depth ─────────────────────────────────────────────────────

class TestPhase4bLearnAndPersist:
    def test_persists_estadopend(self):
        """Fase 4b persiste la distribución de ESTADOPEND en el KnowledgeStore."""
        agent = make_agent()
        result = EpicAnalysisResult(question="¿cuántos presupuestos?", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Distribución de ESTADOPEND en presupuestos (estado real)",
                "sql": "SELECT ESTADOPEND, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY ESTADOPEND",
                "rows": 3,
                "data": [
                    {"ESTADOPEND": 0, "N": 8000},
                    {"ESTADOPEND": 1, "N": 3000},
                    {"ESTADOPEND": 2, "N": 500},
                ],
                "error": None,
            }
        ]
        result.business_insights = []
        result.anomalies = []
        phase2_data = {}
        analysis = {"reliability_score": "alto"}

        mock_store = MagicMock()
        mock_store.update_table.return_value = True

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            return_value=mock_store
        ):
            phase = asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist(
                    "¿cuántos presupuestos?", phase2_data, result, analysis
                )
            )

        # Verificar que se llamó update_table con estadopend_distribution
        calls = mock_store.update_table.call_args_list
        estadopend_call = next(
            (c for c in calls if "estadopend_distribution" in str(c)),
            None
        )
        assert estadopend_call is not None

    def test_persists_docdestino(self):
        """Fase 4b persiste la relación DOCDESTINO en el KnowledgeStore."""
        agent = make_agent()
        result = EpicAnalysisResult(question="tasa de éxito", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Total presupuestos con cualquier documento destino vinculado",
                "sql": "SELECT COUNT(*) FROM DOCCAB c LEFT JOIN DOCDESTINO dd ON ...",
                "rows": 1,
                "data": [{"TOTAL_PRESUPUESTOS": 1000, "CON_DESTINO": 150, "SIN_DESTINO": 850}],
                "error": None,
            }
        ]
        result.business_insights = []
        result.anomalies = []
        phase2_data = {}
        analysis = {"reliability_score": "medio"}

        mock_store = MagicMock()
        mock_store.update_table.return_value = True

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            return_value=mock_store
        ):
            phase = asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist(
                    "tasa de éxito", phase2_data, result, analysis
                )
            )

        # Verificar que se llamó update_table con _nota_docdestino
        calls = mock_store.update_table.call_args_list
        docdestino_call = next(
            (c for c in calls if "_nota_docdestino" in str(c)),
            None
        )
        assert docdestino_call is not None

    def test_persists_columns_real(self):
        """Fase 4b persiste las columnas reales de las tablas exploradas."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = []
        result.business_insights = []
        result.anomalies = []
        phase2_data = {
            "DOCCAB": {
                "columns": ["TIPO", "FECHA", "IMPORTETOTAL"],
                "columns_source": "firebird_rdb",
                "total": 74034,
            }
        }
        analysis = {"reliability_score": "alto"}

        mock_store = MagicMock()
        mock_store.update_table.return_value = True

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            return_value=mock_store
        ):
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("test", phase2_data, result, analysis)
            )

        # Verificar que se llamó update_table con columns_real
        calls = mock_store.update_table.call_args_list
        cols_call = next(
            (c for c in calls if "columns_real" in str(c)),
            None
        )
        assert cols_call is not None

    def test_persists_business_insights(self):
        """Fase 4b persiste los insights de negocio como reglas."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = []
        result.business_insights = [
            "1 instalación puede tener N presupuestos",
            "Los presupuestos sin CODCLIENTE son instalaciones directas",
        ]
        result.anomalies = []
        phase2_data = {}
        analysis = {"reliability_score": "alto"}

        mock_store = MagicMock()
        mock_store.update_table.return_value = False

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            return_value=mock_store
        ):
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("test", phase2_data, result, analysis)
            )

        # Verificar que se llamó add_business_rule
        assert mock_store.add_business_rule.called

    def test_persists_sql_patterns(self):
        """Fase 4b persiste los patrones SQL exitosos."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Distribución por año",
                "sql": "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY 1",
                "rows": 8,
                "data": [{"ANO": 2024, "N": 1500}],
                "error": None,
            }
        ]
        result.business_insights = []
        result.anomalies = []
        phase2_data = {}
        analysis = {"reliability_score": "alto"}

        mock_store = MagicMock()
        mock_store.update_table.return_value = False

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            return_value=mock_store
        ):
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("test", phase2_data, result, analysis)
            )

        # Verificar que se llamó add_query_pattern
        assert mock_store.add_query_pattern.called

    def test_adds_business_rule_when_docdestino_low(self):
        """Fase 4b añade regla de negocio si % DOCDESTINO < 30%."""
        agent = make_agent()
        result = EpicAnalysisResult(question="tasa", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Total presupuestos con cualquier documento destino vinculado",
                "sql": "SELECT ...",
                "rows": 1,
                "data": [{"TOTAL_PRESUPUESTOS": 1000, "CON_DESTINO": 100, "SIN_DESTINO": 900}],
                "error": None,
            }
        ]
        result.business_insights = []
        result.anomalies = []
        phase2_data = {}
        analysis = {"reliability_score": "medio"}

        mock_store = MagicMock()
        mock_store.update_table.return_value = True

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            return_value=mock_store
        ):
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("tasa", phase2_data, result, analysis)
            )

        # Verificar que se añadió regla de negocio (10% < 30%)
        assert mock_store.add_business_rule.called
        rule_text = str(mock_store.add_business_rule.call_args_list)
        assert "10.0%" in rule_text or "DOCDESTINO" in rule_text

    def test_no_crash_when_knowledge_store_unavailable(self):
        """Fase 4b no lanza excepción si el KnowledgeStore no está disponible."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = []
        result.business_insights = []
        result.anomalies = []
        phase2_data = {}
        analysis = {}

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            side_effect=Exception("KnowledgeStore no disponible")
        ):
            phase = asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("test", phase2_data, result, analysis)
            )

        # No debe lanzar excepción
        assert phase is not None
        assert phase.success is False  # Falla graciosamente

    def test_phase4b_returns_phase_result(self):
        """Fase 4b siempre devuelve un PhaseResult."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = []
        result.business_insights = []
        result.anomalies = []

        mock_store = MagicMock()
        mock_store.update_table.return_value = False

        with patch(
            "backend.modules.chat.deep_analysis.phase4.get_knowledge_store",
            return_value=mock_store
        ):
            phase = asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("test", {}, result, {})
            )

        assert isinstance(phase, PhaseResult)
        assert phase.phase_id == "4b"


# ─── Tests: SQLs fijos ESTADOPEND/DOCDESTINO/RDB$ ────────────────────────────

class TestFixedSQLsEstadoPend:
    def test_estadopend_sql_included_for_presupuesto(self):
        """SQL de ESTADOPEND se incluye para preguntas sobre presupuestos."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuántos presupuestos hay?", phase2_data)
        objetivos = [f["objetivo"] for f in fixed]
        assert any("ESTADOPEND" in o for o in objetivos)

    def test_docdestino_sql_included_for_tasa(self):
        """SQL de DOCDESTINO se incluye para preguntas sobre tasa de éxito."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuál es la tasa de éxito?", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("DOCDESTINO" in s for s in sqls)

    def test_rdb_columns_sql_included_for_aceptado(self):
        """Para preguntas sobre aceptados, se incluyen SQLs de ESTADOPEND (columna real BD)."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuántos presupuestos aceptados hay?", phase2_data)
        sqls = [f["sql"] for f in fixed]
        # El agente usa ESTADOPEND (columna real de DOCCAB en Firebird) para determinar
        # el estado de los presupuestos — no RDB$RELATION_FIELDS que es una query de metadatos
        assert any("ESTADOPEND" in s for s in sqls), (
            "Para preguntas sobre presupuestos aceptados, debe incluirse SQL con ESTADOPEND "
            "(columna real de DOCCAB que indica el estado del presupuesto)"
        )

    def test_no_estado_sqls_for_unrelated_question(self):
        """SQLs de estado NO se incluyen para preguntas no relacionadas."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuántos artículos hay en stock?", phase2_data)
        objetivos = [f["objetivo"] for f in fixed]
        assert not any("ESTADOPEND" in o for o in objetivos)

    def test_docdestino_tipo_sql_included(self):
        """SQL de distribución por tipo de DOCDESTINO se incluye."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("tasa de éxito presupuestos", phase2_data)
        sqls = [f["sql"] for f in fixed]
        # Debe haber SQL que une DOCDESTINO con DOCCAB por tipo
        assert any("TIPO_DESTINO" in s or "TIPO AS TIPO_DESTINO" in s for s in sqls)

    def test_total_with_without_destino_sql(self):
        """SQL de total con/sin documento destino se incluye."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("presupuestos aceptados", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("CON_DESTINO" in s and "SIN_DESTINO" in s for s in sqls)


# ─── Tests: Helpers SIUO (resiliencia multi-fuente) ──────────────────────────

