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

class TestPhase2KnowledgeStorePersistence:
    """
    Tests para la persistencia automática en KnowledgeStore
    tras explorar una tabla desde la BD.
    """

    async def test_persists_columns_after_real_exploration(self):
        """Tras exploración real, persiste columnas en KnowledgeStore."""
        agent = make_agent()

        async def executor(sql):
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 1000}]
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}, {"COL": "FECHA"}, {"COL": "IMPORTETOTAL"}]
            return [{"NULOS": 5}]

        agent.sql_executor = executor

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}  # Cache vacío

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            await agent._explore_table("DOCCAB", cfg)

        # Verificar que se llamó update_table con columns_real
        calls = mock_store.update_table.call_args_list
        assert any("columns_real" in str(c) for c in calls)

    async def test_persists_record_count_after_real_exploration(self):
        """Tras exploración real, persiste el conteo en KnowledgeStore."""
        agent = make_agent()

        async def executor(sql):
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 74034}]
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}]
            return [{"NULOS": 0}]

        agent.sql_executor = executor

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            await agent._explore_table("DOCCAB", cfg)

        calls = mock_store.update_table.call_args_list
        assert any("record_count_real" in str(c) for c in calls)

    async def test_does_not_persist_siuo_columns(self):
        """NO persiste columnas obtenidas de SIUO (solo de BD real)."""
        from unittest.mock import patch as mock_patch
        agent = make_agent()
        # BD falla → columnas de SIUO
        agent.sql_executor = AsyncMock(side_effect=Exception("BD no disponible"))

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            with patch.object(agent, "_get_siuo_columns", return_value=["TIPO", "FECHA"]):
                cfg = {"max_sqls": 4, "explore_tables": 2}
                await agent._explore_table("DOCCAB", cfg)

        # NO debe persistir columns_real (fuente no es firebird_rdb)
        calls = mock_store.update_table.call_args_list
        assert not any("columns_real" in str(c) for c in calls)

    async def test_no_crash_on_persistence_error(self):
        """Si la persistencia falla, la exploración continúa sin excepción."""
        agent = make_agent()

        async def executor(sql):
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 100}]
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}]
            return [{"NULOS": 0}]

        agent.sql_executor = executor

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}
        mock_store.update_table.side_effect = Exception("Error al persistir")

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = await agent._explore_table("DOCCAB", cfg)

        # No debe lanzar excepción
        assert isinstance(info, dict)
        assert info.get("total") == 100


# ─── Tests NUEVOS: Fase 4b ESTADOPENDVENCOM ──────────────────────────────────

class TestPhase4bEstadoPendVenCom:
    """
    Tests para la persistencia de ESTADOPENDVENCOM en KnowledgeStore (Fase 4b).
    """

    def test_persists_estadopendvencom_distribution(self):
        """Fase 4b persiste la distribución de ESTADOPENDVENCOM."""
        agent = make_agent()
        result = EpicAnalysisResult(question="tasa de éxito", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Distribución de ESTADOPENDVENCOM en presupuestos (estado comercial)",
                "sql": "SELECT ESTADOPENDVENCOM, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY ESTADOPENDVENCOM",
                "rows": 3,
                "data": [
                    {"ESTADOPENDVENCOM": 0, "N": 7000},
                    {"ESTADOPENDVENCOM": 1, "N": 2500},
                    {"ESTADOPENDVENCOM": 2, "N": 300},
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
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("tasa de éxito", phase2_data, result, analysis)
            )

        calls = mock_store.update_table.call_args_list
        vencom_call = next(
            (c for c in calls if "estadopendvencom_distribution" in str(c)),
            None
        )
        assert vencom_call is not None

    def test_persists_cruce_estadopend(self):
        """Fase 4b persiste el cruce ESTADOPEND x ESTADOPENDVENCOM."""
        agent = make_agent()
        result = EpicAnalysisResult(question="tasa", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Cruce ESTADOPEND x ESTADOPENDVENCOM (definición real de aceptado)",
                "sql": "SELECT ESTADOPEND, ESTADOPENDVENCOM, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY ESTADOPEND, ESTADOPENDVENCOM",
                "rows": 4,
                "data": [
                    {"ESTADOPEND": 0, "ESTADOPENDVENCOM": 0, "N": 6000},
                    {"ESTADOPEND": 0, "ESTADOPENDVENCOM": 1, "N": 2000},
                    {"ESTADOPEND": 1, "ESTADOPENDVENCOM": 1, "N": 1500},
                    {"ESTADOPEND": 2, "ESTADOPENDVENCOM": 2, "N": 300},
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
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("tasa", phase2_data, result, analysis)
            )

        calls = mock_store.update_table.call_args_list
        cruce_call = next(
            (c for c in calls if "estadopend_cruce" in str(c)),
            None
        )
        assert cruce_call is not None

    def test_persists_conversion_distribution(self):
        """Fase 4b persiste la distribución de conversión factura/pedido."""
        agent = make_agent()
        result = EpicAnalysisResult(question="tasa", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Presupuestos convertidos a factura (TIPO=13) o pedido (TIPO=12)",
                "sql": "SELECT SUM(CASE WHEN d.TIPO = 13 THEN 1 ELSE 0 END) AS A_FACTURA ...",
                "rows": 1,
                "data": [
                    {"A_FACTURA": 750, "A_PEDIDO": 95, "A_ALBARAN": 20, "A_OTRO": 14, "TOTAL_CON_DESTINO": 879}
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
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("tasa", phase2_data, result, analysis)
            )

        calls = mock_store.update_table.call_args_list
        conv_call = next(
            (c for c in calls if "conversion_distribution" in str(c)),
            None
        )
        assert conv_call is not None

    def test_adds_business_rule_for_conversion(self):
        """Fase 4b añade regla de negocio cuando hay conversiones a factura/pedido."""
        agent = make_agent()
        result = EpicAnalysisResult(question="tasa", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Presupuestos convertidos a factura (TIPO=13) o pedido (TIPO=12)",
                "sql": "SELECT ...",
                "rows": 1,
                "data": [
                    {"A_FACTURA": 750, "A_PEDIDO": 95, "A_ALBARAN": 20, "A_OTRO": 14, "TOTAL_CON_DESTINO": 879}
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
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("tasa", phase2_data, result, analysis)
            )

        # Debe haber añadido regla de negocio sobre "aceptado"
        assert mock_store.add_business_rule.called
        rule_text = str(mock_store.add_business_rule.call_args_list)
        assert "750" in rule_text or "factura" in rule_text.lower() or "Aceptado" in rule_text

    def test_estadopend_not_confused_with_vencom(self):
        """ESTADOPEND y ESTADOPENDVENCOM se persisten en campos separados."""
        agent = make_agent()
        result = EpicAnalysisResult(question="tasa", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {
                "objetivo": "Distribución de ESTADOPEND en presupuestos (estado real)",
                "sql": "SELECT ESTADOPEND, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY ESTADOPEND",
                "rows": 2,
                "data": [{"ESTADOPEND": 0, "N": 8000}, {"ESTADOPEND": 1, "N": 2000}],
                "error": None,
            },
            {
                "objetivo": "Distribución de ESTADOPENDVENCOM en presupuestos (estado comercial)",
                "sql": "SELECT ESTADOPENDVENCOM, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY ESTADOPENDVENCOM",
                "rows": 2,
                "data": [{"ESTADOPENDVENCOM": 0, "N": 7500}, {"ESTADOPENDVENCOM": 1, "N": 2500}],
                "error": None,
            },
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
            asyncio.get_event_loop().run_until_complete(
                agent._phase4b_learn_and_persist("tasa", phase2_data, result, analysis)
            )

        calls_str = str(mock_store.update_table.call_args_list)
        # Ambos campos deben estar presentes
        assert "estadopend_distribution" in calls_str
        assert "estadopendvencom_distribution" in calls_str
