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

class TestDetectDepth:
    def test_epic_keywords(self):
        assert detect_depth("analiza en profundidad los presupuestos") == AnalysisDepth.EPIC

    def test_epic_tasa(self):
        assert detect_depth("¿cuál es la tasa de éxito?") == AnalysisDepth.EPIC

    def test_epic_tendencia(self):
        assert detect_depth("muéstrame la tendencia histórica") == AnalysisDepth.EPIC

    def test_deep_cuantos(self):
        assert detect_depth("¿cuántos clientes hay?") == AnalysisDepth.DEEP

    def test_deep_total(self):
        assert detect_depth("total de facturas del año") == AnalysisDepth.DEEP

    def test_medium_lista(self):
        assert detect_depth("lista los artículos") == AnalysisDepth.MEDIUM

    def test_epic_default(self):
        # Sin palabras clave → EPIC por defecto
        assert detect_depth("hola") == AnalysisDepth.EPIC

    def test_epic_investigar(self):
        assert detect_depth("investiga los duplicados") == AnalysisDepth.EPIC


# ─── Tests: TokenBudget ──────────────────────────────────────────────────────

class TestTokenBudget:
    def test_count_empty(self):
        b = TokenBudget(32000)
        assert b.count("") == 0

    def test_count_text(self):
        b = TokenBudget(32000)
        text = "a" * 350  # 350 chars / 3.5 = 100 tokens
        assert b.count(text) == 100

    def test_fits_small(self):
        b = TokenBudget(32000)
        assert b.fits("hello world") is True

    def test_fits_too_large(self):
        b = TokenBudget(1000)  # muy pequeño
        huge = "x" * 100000
        assert b.fits(huge) is False

    def test_truncate_no_change(self):
        b = TokenBudget(32000)
        text = "short text"
        result = b.truncate_to_fit(text)
        assert result == text

    def test_truncate_cuts(self):
        b = TokenBudget(500)  # muy pequeño
        text = "x" * 10000
        result = b.truncate_to_fit(text)
        assert len(result) < len(text)
        assert "TRUNCADO" in result

    def test_usage_pct_zero(self):
        b = TokenBudget(32000)
        assert b.usage_pct("") == 0.0

    def test_usage_pct_full(self):
        b = TokenBudget(100)
        huge = "x" * 100000
        pct = b.usage_pct(huge)
        assert pct >= 1.0


# ─── Tests: Fase 1 fallback ──────────────────────────────────────────────────

class TestPhase1Fallback:
    def test_fallback_on_ai_error(self):
        """Si la IA falla en detectar intención, usa valores por defecto."""
        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(side_effect=Exception("IA no disponible"))
        orch.context_limit_tokens = 32000
        agent = make_agent(orchestrator=orch)

        async def run():
            result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
            cfg = dict(DEPTH_CONFIG[AnalysisDepth.EPIC])
            phase = await agent._phase1_understand("test", result, cfg, [])
            return phase

        phase = asyncio.get_event_loop().run_until_complete(run())
        # Debe completarse sin excepción
        assert phase is not None
        # La subfase 1.1 debe tener datos de fallback
        intent_sub = next((s for s in phase.sub_phases if "1.1" in s.name), None)
        assert intent_sub is not None
        assert intent_sub.data is not None

    def test_tables_hint_presupuesto(self):
        """Palabras clave 'presupuesto' → DOCCAB en tablas candidatas."""
        agent = make_agent()

        async def run():
            return await agent._sub_identify_tables("¿cuántos presupuestos hay?", {})

        tables = asyncio.get_event_loop().run_until_complete(run())
        assert "DOCCAB" in tables

    def test_tables_hint_cliente(self):
        agent = make_agent()

        async def run():
            return await agent._sub_identify_tables("dame los clientes activos", {})

        tables = asyncio.get_event_loop().run_until_complete(run())
        assert "CLIENTE" in tables

    def test_issues_presupuesto(self):
        agent = make_agent()
        issues = agent._sub_identify_issues("¿cuántos presupuestos hay?")
        assert any("instalación" in i.lower() for i in issues)

    def test_issues_tasa(self):
        agent = make_agent()
        issues = agent._sub_identify_issues("¿cuál es la tasa de éxito?")
        assert any("duplicado" in i.lower() or "distorsionada" in i.lower() for i in issues)


# ─── Tests: Fase 2 exploración ───────────────────────────────────────────────

class TestPhase2Exploration:
    def test_explore_table_count(self):
        """_explore_table debe obtener el conteo de registros."""
        executor = MagicMock(return_value=[{"TOTAL": 5000}])
        agent = make_agent(sql_rows=[{"TOTAL": 5000}])
        agent.sql_executor = executor

        cfg = {"max_sqls": 12, "explore_tables": 4}
        info = agent._explore_table("DOCCAB", cfg)
        assert info["total"] == 5000

    def test_explore_table_columns(self):
        """_explore_table debe obtener columnas desde RDB$RELATION_FIELDS."""
        call_count = [0]

        def executor(sql):
            call_count[0] += 1
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}, {"COL": "FECHA"}, {"COL": "IMPORTETOTAL"}]
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 100}]
            return [{"NULOS": 0}]

        agent = make_agent()
        agent.sql_executor = executor
        cfg = {"max_sqls": 12, "explore_tables": 4}
        info = agent._explore_table("DOCCAB", cfg)
        assert "TIPO" in info["columns"]
        assert info["has_tipo"] is True
        assert info["has_fecha"] is True

    def test_explore_table_sql_error(self):
        """Si el SQL falla, _explore_table no lanza excepción."""
        agent = make_agent()
        agent.sql_executor = MagicMock(side_effect=Exception("Firebird error"))
        cfg = {"max_sqls": 4, "explore_tables": 2}
        info = agent._explore_table("DOCCAB", cfg)
        assert "ERROR" in str(info.get("total", ""))


# ─── Tests: Fase 3 SQLs fijos ────────────────────────────────────────────────

class TestPhase3FixedSQLs:
    def test_fixed_sqls_doccab_with_serie(self):
        """Con DOCCAB y SERIE → SQL de distribución por año y serie."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": True, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuántos presupuestos hay?", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("SERIE" in s for s in sqls)
        assert any("EXTRACT(YEAR" in s for s in sqls)

    def test_fixed_sqls_doccab_without_serie(self):
        """Sin SERIE → SQL de distribución solo por año."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("presupuestos", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("EXTRACT(YEAR" in s for s in sqls)

    def test_fixed_sqls_instalaciones_codigoobra(self):
        """Con CODIGOOBRA → SQL de instalaciones únicas."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": True}}
        fixed = agent._build_fixed_sqls("tasa de éxito de presupuestos", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("CODIGOOBRA" in s for s in sqls)

    def test_fixed_sqls_instalaciones_fallback(self):
        """Sin CODIGOOBRA → SQL de clientes únicos."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("tasa de éxito de presupuestos", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("CODCLIENTE" in s for s in sqls)

    def test_extract_objetivo(self):
        agent = make_agent()
        sql = "-- [OBJETIVO: Distribución por año]\nSELECT COUNT(*) FROM DOCCAB"
        obj = agent._extract_objetivo(sql, 0)
        assert obj == "Distribución por año"

    def test_extract_objetivo_fallback(self):
        agent = make_agent()
        sql = "SELECT COUNT(*) FROM DOCCAB"
        obj = agent._extract_objetivo(sql, 3)
        assert obj == "Consulta 4"


# ─── Tests: Fase 4 SIUO feedback ─────────────────────────────────────────────

class TestPhase4SIUOFeedback:
    def test_register_feedback_called(self):
        """_register_siuo_feedback debe llamar a retriever.register_feedback."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {"objetivo": "test", "sql": "SELECT COUNT(*) FROM DOCCAB", "rows": 5, "data": [], "error": None}
        ]
        analysis = {"reliability_score": "alto", "reliability_reason": "datos completos"}

        mock_retriever = MagicMock()
        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever",
            return_value=mock_retriever
        ):
            agent._register_siuo_feedback("test", result, analysis)
            mock_retriever.register_feedback.assert_called_once()
            call_kwargs = mock_retriever.register_feedback.call_args
            assert call_kwargs[1]["was_correct"] is True

    def test_register_feedback_low_reliability(self):
        """Fiabilidad 'bajo' → was_correct=False."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = []
        analysis = {"reliability_score": "bajo", "reliability_reason": "pocos datos"}

        mock_retriever = MagicMock()
        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever",
            return_value=mock_retriever
        ):
            agent._register_siuo_feedback("test", result, analysis)
            call_kwargs = mock_retriever.register_feedback.call_args
            assert call_kwargs[1]["was_correct"] is False

    def test_register_feedback_no_crash_on_error(self):
        """Si el SIUO no está disponible, no debe lanzar excepción."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = []
        analysis = {"reliability_score": "alto"}

        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever",
            side_effect=Exception("SIUO no disponible")
        ):
            # No debe lanzar excepción
            agent._register_siuo_feedback("test", result, analysis)


# ─── Tests: Fallback de emergencia ───────────────────────────────────────────

class TestEmergencyFallback:
    def test_fallback_with_data(self):
        agent = make_agent()
        result = EpicAnalysisResult(question="¿cuántos presupuestos?", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {"objetivo": "Conteo total", "sql": "SELECT COUNT(*) FROM DOCCAB", "rows": 1234, "data": [{"TOTAL": 1234}], "error": None}
        ]
        answer = agent._emergency_fallback(result)
        assert "1234" in answer or "Conteo total" in answer
        assert "presupuestos" in answer.lower()

    def test_fallback_with_error(self):
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.sql_queries = [
            {"objetivo": "SQL fallido", "sql": "SELECT ...", "rows": 0, "data": [], "error": "Firebird error"}
        ]
        answer = agent._emergency_fallback(result)
        assert "❌" in answer or "Firebird error" in answer

    def test_fallback_empty(self):
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        answer = agent._emergency_fallback(result)
        assert len(answer) > 0
        assert "test" in answer


# ─── Tests: Análisis completo con mocks ──────────────────────────────────────

class TestFullAnalysisMock:
    def test_full_analysis_returns_string(self):
        """El análisis completo debe devolver un string no vacío."""
        synthesis_response = (
            "## 📊 Respuesta Principal\n"
            "Hay 1234 presupuestos en total.\n\n"
            "## 🔍 Análisis Crítico\nDatos fiables.\n"
        )
        analysis_response = json.dumps({
            "warnings": ["Posibles duplicados"],
            "anomalies": [],
            "data_quality_issues": [],
            "business_insights": ["1 instalación = N presupuestos"],
            "sql_limitations": [],
            "hidden_patterns": [],
            "hypotheses": [],
            "suggestions": ["Verificar duplicados"],
            "reliability_score": "alto",
            "reliability_reason": "datos completos",
        })

        call_count = [0]

        async def mock_execute(system_prompt, user_message, preferred_model_id=None):
            call_count[0] += 1
            # Fase 1: intención
            if "intención" in system_prompt or "intent" in system_prompt.lower():
                return ('{"intent":"test","category":"ventas","complexity":"epic"}', None)
            # Fase 1: sub-preguntas
            if "sub-preguntas" in system_prompt or "Descompón" in system_prompt:
                return ('["¿cuántos presupuestos hay?"]', None)
            # Fase 3: SQLs
            if "EXACTAMENTE" in system_prompt or "ángulos" in system_prompt.lower():
                return ('```sql\n-- [OBJETIVO: Conteo total]\nSELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO=0\n```', None)
            # Fase 4: análisis
            if "reliability_score" in system_prompt:
                return (analysis_response, None)
            # Fase 5: síntesis
            return (synthesis_response, None)

        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(side_effect=mock_execute)
        orch.context_limit_tokens = 32000

        def sql_executor(sql):
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}, {"COL": "FECHA"}, {"COL": "IMPORTETOTAL"}, {"COL": "CODCLIENTE"}]
            if "NULOS" in sql:
                return [{"NULOS": 0}]
            if "TIPO_DISTRIBUTION" in sql or "GROUP BY TIPO" in sql:
                return [{"TIPO": 0, "N": 1234}]
            return [{"TOTAL": 1234}]

        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="TABLA: DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL",
            sql_executor=sql_executor,
        )

        with patch("backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever") as mock_cr:
            mock_cr.return_value.get_context.return_value = ("ESQUEMA SIUO", {"tables_used": ["DOCCAB"], "source": "siuo"})
            mock_cr.return_value.register_feedback = MagicMock()

            answer = asyncio.get_event_loop().run_until_complete(
                agent.analyze("¿cuántos presupuestos hay?", conversation_history=[])
            )

        assert isinstance(answer, str)
        assert len(answer) > 50

    def test_full_analysis_with_history(self):
        """El análisis debe aceptar historial de conversación."""
        orch = make_orchestrator('{"intent":"test","category":"ventas","complexity":"epic"}')
        agent = make_agent(orchestrator=orch)

        history = [
            {"role": "user", "content": "¿cuántos clientes hay?"},
            {"role": "assistant", "content": "Hay 500 clientes."},
        ]

        with patch("backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever") as mock_cr:
            mock_cr.return_value.get_context.return_value = ("ESQUEMA", {"tables_used": [], "source": "fallback"})
            mock_cr.return_value.register_feedback = MagicMock()

            answer = asyncio.get_event_loop().run_until_complete(
                agent.analyze("¿y cuántos presupuestos?", conversation_history=history)
            )

        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_full_analysis_ai_total_failure(self):
        """Si la IA falla completamente, debe devolver el fallback de emergencia."""
        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(side_effect=Exception("IA completamente caída"))
        orch.context_limit_tokens = 32000
        agent = make_agent(orchestrator=orch)

        with patch("backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever") as mock_cr:
            mock_cr.return_value.get_context.side_effect = Exception("SIUO no disponible")

            answer = asyncio.get_event_loop().run_until_complete(
                agent.analyze("test pregunta")
            )

        assert isinstance(answer, str)
        assert len(answer) > 0  # Siempre devuelve algo


# ─── Tests: Helpers ──────────────────────────────────────────────────────────

class TestHelpers:
    def test_parse_json_direct(self):
        agent = make_agent()
        result = agent._parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_in_block(self):
        agent = make_agent()
        result = agent._parse_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_array(self):
        agent = make_agent()
        result = agent._parse_json('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_parse_json_invalid(self):
        agent = make_agent()
        result = agent._parse_json("esto no es JSON")
        assert result is None

    def test_fmt_conversation_history_empty(self):
        agent = make_agent()
        result = agent._fmt_conversation_history([])
        assert result == ""

    def test_fmt_conversation_history_with_messages(self):
        agent = make_agent()
        history = [
            {"role": "user", "content": "¿cuántos clientes?"},
            {"role": "assistant", "content": "Hay 500 clientes."},
        ]
        result = agent._fmt_conversation_history(history)
        assert "USER" in result
        assert "ASSISTANT" in result
        assert "clientes" in result

    def test_fmt_exploration_empty(self):
        agent = make_agent()
        result = agent._fmt_exploration({})
        assert "Sin datos" in result

    def test_fmt_exploration_with_data(self):
        agent = make_agent()
        exploration = {
            "DOCCAB": {
                "total": 5000,
                "columns": ["TIPO", "FECHA", "IMPORTETOTAL"],
                "has_tipo": True,
                "tipo_distribution": [{"TIPO": 0, "N": 1234}],
                "null_codcliente": 10,
            }
        }
        result = agent._fmt_exploration(exploration)
        assert "DOCCAB" in result
        assert "5000" in result

    def test_build_warnings_html_empty(self):
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        html = agent._build_warnings_html(result)
        assert html == ""

    def test_build_warnings_html_with_warnings(self):
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.warnings = ["Advertencia 1", "Advertencia 2"]
        result.anomalies = ["Anomalía detectada"]
        html = agent._build_warnings_html(result)
        assert "Advertencia 1" in html
        assert "Anomalía detectada" in html
        assert "<div" in html


# ─── Tests: _phase0_lan_optimize ─────────────────────────────────────────────

class TestPhase0LanOptimize:
    def test_detects_lan_model_by_preferred_id(self):
        """Detecta modelo LAN si preferred_model_id contiene 'jddcia'."""
        orch = make_orchestrator()
        orch.preferred_model_id = "jddcia-qwen3-30b"
        agent = make_agent(orchestrator=orch)
        cfg = {"max_sqls": 12, "explore_tables": 6}
        result = agent._phase0_lan_optimize(cfg)
        assert result["lan_mode"] is True

    def test_detects_lan_model_by_ai_mode(self):
        """Detecta modelo LAN si ai_mode contiene 'local'."""
        orch = make_orchestrator()
        orch.ai_mode = "AI_LOCAL_ONLY"
        agent = make_agent(orchestrator=orch)
        cfg = {"max_sqls": 12, "explore_tables": 6}
        result = agent._phase0_lan_optimize(cfg)
        assert result["lan_mode"] is True

    def test_internet_model_not_lan(self):
        """Modelo sin 'jddcia' ni 'local' → lan_mode=False."""
        orch = make_orchestrator()
        # Sin preferred_model_id ni ai_mode
        agent = make_agent(orchestrator=orch)
        cfg = {"max_sqls": 12, "explore_tables": 6}
        result = agent._phase0_lan_optimize(cfg)
        assert result["lan_mode"] is False

    def test_sets_known_sqls_count(self):
        """Establece known_sqls_count con los patrones del KnowledgeStore."""
        agent = make_agent()
        cfg = {"max_sqls": 12, "explore_tables": 6}

        mock_store = MagicMock()
        mock_store.get_patterns_for_intent.return_value = [{"intent": "test"}] * 5

        with patch(
            "backend.modules.chat.deep_analysis.agent.get_knowledge_store",
            return_value=mock_store
        ):
            result = agent._phase0_lan_optimize(cfg)

        assert result["known_sqls_count"] == 5

    def test_no_crash_on_knowledge_store_error(self):
        """No lanza excepción si el KnowledgeStore falla."""
        agent = make_agent()
        cfg = {"max_sqls": 12, "explore_tables": 6}

        with patch(
            "backend.modules.chat.deep_analysis.agent.get_knowledge_store",
            side_effect=Exception("KnowledgeStore no disponible")
        ):
            result = agent._phase0_lan_optimize(cfg)

        assert "lan_mode" in result
        assert "known_sqls_count" in result

    def test_does_not_reduce_max_sqls(self):
        """La optimización LAN NO reduce max_sqls (principio de calidad)."""
        orch = make_orchestrator()
        orch.preferred_model_id = "jddcia-qwen3-30b"
        agent = make_agent(orchestrator=orch)
        cfg = {"max_sqls": 12, "explore_tables": 6}
        result = agent._phase0_lan_optimize(cfg)
        assert result["max_sqls"] == 12  # Sin cambio

    def test_returns_cfg_dict(self):
        """Siempre devuelve un dict con las claves esperadas."""
        agent = make_agent()
        cfg = {"max_sqls": 8, "explore_tables": 4}
        result = agent._phase0_lan_optimize(cfg)
        assert isinstance(result, dict)
        assert "lan_mode" in result
        assert "known_sqls_count" in result


# ─── Tests: _build_phase3_system ─────────────────────────────────────────────

class TestBuildPhase3System:
    def test_lan_mode_prompt_shorter(self):
        """El prompt LAN es más corto que el prompt completo."""
        agent = make_agent()
        schema = "DOCCAB: TIPO, FECHA"
        exploration = "DOCCAB: 1000 registros"
        prompt_lan = agent._build_phase3_system(schema, exploration, 8, lan_mode=True)
        prompt_full = agent._build_phase3_system(schema, exploration, 8, lan_mode=False)
        assert len(prompt_lan) < len(prompt_full)

    def test_lan_mode_includes_n_sqls(self):
        """El prompt LAN incluye el número de SQLs requeridos."""
        agent = make_agent()
        prompt = agent._build_phase3_system("schema", "exploration", 6, lan_mode=True)
        assert "6" in prompt

    def test_full_mode_includes_angulos(self):
        """El prompt completo incluye los ángulos obligatorios."""
        agent = make_agent()
        prompt = agent._build_phase3_system("schema", "exploration", 12, lan_mode=False)
        assert "ÁNGULOS OBLIGATORIOS" in prompt

    def test_both_modes_include_firebird_rules(self):
        """Ambos modos incluyen las reglas de Firebird 2.5."""
        agent = make_agent()
        for lan_mode in [True, False]:
            prompt = agent._build_phase3_system("schema", "exploration", 8, lan_mode=lan_mode)
            assert "FIRST N" in prompt or "FIRST" in prompt
            assert "TIPO" in prompt

    def test_lan_mode_with_known_patterns(self):
        """El prompt LAN incluye los patrones conocidos si se proporcionan."""
        agent = make_agent()
        known = "• [presupuestos por año] → SELECT EXTRACT(YEAR FROM FECHA)... (10 filas)"
        prompt = agent._build_phase3_system("schema", "exploration", 8, lan_mode=True, known_patterns_text=known)
        assert "presupuestos por año" in prompt
        assert "no repetir" in prompt.lower() or "YA CUBIERTOS" in prompt

    def test_full_mode_with_known_patterns(self):
        """El prompt completo incluye los patrones conocidos si se proporcionan."""
        agent = make_agent()
        known = "• [presupuestos por año] → SELECT EXTRACT(YEAR FROM FECHA)... (10 filas)"
        prompt = agent._build_phase3_system("schema", "exploration", 12, lan_mode=False, known_patterns_text=known)
        assert "presupuestos por año" in prompt

    def test_no_known_patterns_no_section(self):
        """Sin patrones conocidos, no aparece la sección de patrones."""
        agent = make_agent()
        prompt = agent._build_phase3_system("schema", "exploration", 8, lan_mode=True, known_patterns_text="")
        assert "YA CUBIERTOS" not in prompt

    def test_includes_expansion_marker(self):
        """Ambos modos incluyen el marcador de expansión dinámica."""
        agent = make_agent()
        for lan_mode in [True, False]:
            prompt = agent._build_phase3_system("schema", "exploration", 8, lan_mode=lan_mode)
            assert "NECESITO_MAS_SQLS" in prompt


# ─── Tests: _get_known_patterns_text ─────────────────────────────────────────

class TestGetKnownPatternsText:
    def test_returns_string(self):
        """Siempre devuelve un string."""
        agent = make_agent()
        result = agent._get_known_patterns_text("¿cuántos presupuestos hay?", {})
        assert isinstance(result, str)

    def test_returns_patterns_from_store(self):
        """Devuelve patrones del KnowledgeStore formateados."""
        agent = make_agent()
        mock_store = MagicMock()
        mock_store.get_patterns_for_intent.return_value = [
            {
                "intent": "presupuestos por año",
                "sql": "SELECT EXTRACT(YEAR FROM FECHA) AS ANO FROM DOCCAB WHERE TIPO=0 GROUP BY 1",
                "rows_returned": 10,
            }
        ]

        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
            return_value=mock_store
        ):
            result = agent._get_known_patterns_text("¿cuántos presupuestos hay?", {})

        assert "presupuestos por año" in result
        assert "10 filas" in result

    def test_empty_store_returns_empty_string(self):
        """Con store vacío, devuelve string vacío."""
        agent = make_agent()
        mock_store = MagicMock()
        mock_store.get_patterns_for_intent.return_value = []

        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
            return_value=mock_store
        ):
            result = agent._get_known_patterns_text("test", {})

        assert result == ""

    def test_no_crash_on_store_error(self):
        """No lanza excepción si el KnowledgeStore falla."""
        agent = make_agent()
        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
            side_effect=Exception("KnowledgeStore no disponible")
        ):
            result = agent._get_known_patterns_text("test", {})

        assert result == ""

    def test_max_4_patterns(self):
        """Devuelve máximo 4 patrones para no inflar el prompt."""
        agent = make_agent()
        mock_store = MagicMock()
        mock_store.get_patterns_for_intent.return_value = [
            {"intent": f"intent {i}", "sql": f"SELECT {i} FROM DOCCAB WHERE TIPO=0", "rows_returned": i}
            for i in range(10)
        ]

        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
            return_value=mock_store
        ):
            result = agent._get_known_patterns_text("test", {})

        # Máximo 4 líneas de patrones
        lines = [l for l in result.split("\n") if l.strip().startswith("•")]
        assert len(lines) <= 4

    def test_extracts_keywords_from_question(self):
        """Extrae palabras clave de la pregunta (>4 chars)."""
        agent = make_agent()
        mock_store = MagicMock()
        mock_store.get_patterns_for_intent.return_value = []

        with patch(
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
            return_value=mock_store
        ):
            agent._get_known_patterns_text("¿cuántos presupuestos hay este año?", {})

        # Verificar que se llamó con keywords de >4 chars
        call_args = mock_store.get_patterns_for_intent.call_args[0][0]
        assert all(len(k) > 4 for k in call_args)


# ─── Tests: Fase 3 response=None (fix bug) ───────────────────────────────────

class TestPhase3ResponseNone:
    def test_none_response_uses_fixed_sqls(self):
        """Si la IA devuelve None, se usan los SQLs fijos sin TypeError."""
        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(return_value=(None, None))
        orch.context_limit_tokens = 32000
        agent = make_agent(orchestrator=orch)

        async def run():
            result = EpicAnalysisResult(question="¿cuántos presupuestos?", depth=AnalysisDepth.EPIC)
            cfg = {"max_sqls": 8, "explore_tables": 4, "lan_mode": False, "known_sqls_count": 0}
            phase1_data = {
                "sub_questions": ["¿cuántos presupuestos?"],
                "potential_issues": [],
            }
            phase2_data = {
                "DOCCAB": {
                    "has_serie": True, "has_codigoobra": False,
                    "columns": ["TIPO", "FECHA"], "total": 1000,
                }
            }
            with patch("backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever") as mock_cr:
                mock_cr.return_value.get_context.return_value = ("ESQUEMA", {"tables_used": [], "source": "fallback"})
                phase = await agent._phase3_investigate(
                    "¿cuántos presupuestos?", phase1_data, phase2_data, result, cfg
                )
            return phase

        phase = asyncio.get_event_loop().run_until_complete(run())
        # No debe lanzar TypeError — debe completarse
        assert phase is not None

    def test_empty_string_response_uses_fixed_sqls(self):
        """Si la IA devuelve string vacío, se usan los SQLs fijos."""
        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(return_value=("", None))
        orch.context_limit_tokens = 32000
        agent = make_agent(orchestrator=orch)

        async def run():
            result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
            cfg = {"max_sqls": 4, "explore_tables": 2, "lan_mode": False, "known_sqls_count": 0}
            phase1_data = {"sub_questions": ["test"], "potential_issues": []}
            phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False, "columns": [], "total": 0}}
            with patch("backend.modules.chat.deep_analysis.phases_3_4_5.get_context_retriever") as mock_cr:
                mock_cr.return_value.get_context.return_value = ("", {"tables_used": [], "source": "fallback"})
                phase = await agent._phase3_investigate(
                    "test", phase1_data, phase2_data, result, cfg
                )
            return phase

        phase = asyncio.get_event_loop().run_until_complete(run())
        assert phase is not None


# ─── Tests: Fase 4b aprendizaje permanente ───────────────────────────────────

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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phases_3_4_5.get_knowledge_store",
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
        """SQL de RDB$RELATION_FIELDS se incluye para preguntas sobre aceptados."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuántos presupuestos aceptados hay?", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("RDB$RELATION_FIELDS" in s for s in sqls)

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

class TestSIUOMetadataHelpers:
    """
    Tests del flujo real de resiliencia de metadatos:
      BD real → SIUO JSON (db_metadata_optimized.json) → db_context texto

    Verifican que cuando la BD Firebird no está disponible, el agente
    obtiene columnas y conteos desde fuentes alternativas sin lanzar excepción.
    """

    # ── _load_metadata_json ───────────────────────────────────────────────────

    def test_load_metadata_json_file_not_found(self):
        """Si el fichero no existe, devuelve {} sin excepción."""
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", "/ruta/inexistente/metadata.json"):
            result = agent._load_metadata_json()
        assert result == {}

    def test_load_metadata_json_corrupted(self, tmp_path):
        """Si el fichero está corrupto (JSON inválido), devuelve {} sin excepción."""
        bad_file = tmp_path / "bad_metadata.json"
        bad_file.write_text("esto no es json {{{", encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(bad_file)):
            result = agent._load_metadata_json()
        assert result == {}

    def test_load_metadata_json_valid(self, tmp_path):
        """Si el fichero es válido, devuelve el dict correctamente."""
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO", "FECHA"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            result = agent._load_metadata_json()
        assert result == meta

    # ── _get_siuo_columns ─────────────────────────────────────────────────────

    def test_get_siuo_columns_format_dict_list(self, tmp_path):
        """Formato {"columns": ["COL1", "COL2"]} → devuelve lista de strings."""
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO", "FECHA", "IMPORTETOTAL"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert cols == ["TIPO", "FECHA", "IMPORTETOTAL"]

    def test_get_siuo_columns_format_dict_of_dicts(self, tmp_path):
        """Formato {"columns": [{"name": "COL1"}, ...]} → devuelve lista de strings."""
        meta = {"tables": {"DOCCAB": {"columns": [
            {"name": "TIPO", "type": "INTEGER"},
            {"name": "FECHA", "type": "DATE"},
        ]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert "TIPO" in cols
        assert "FECHA" in cols

    def test_get_siuo_columns_format_list_direct(self, tmp_path):
        """Formato lista directa [{"name": "COL1"}, ...] → devuelve lista de strings."""
        meta = {"tables": {"DOCCAB": [
            {"name": "TIPO"}, {"name": "FECHA"}, {"name": "CODCLIENTE"}
        ]}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert "TIPO" in cols
        assert "CODCLIENTE" in cols

    def test_get_siuo_columns_table_not_found(self, tmp_path):
        """Si la tabla no está en el JSON, devuelve lista vacía."""
        meta = {"tables": {"CLIENTE": {"columns": ["CODIGO", "NOMBRE"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert cols == []

    def test_get_siuo_columns_case_insensitive(self, tmp_path):
        """La búsqueda de tabla es case-insensitive."""
        meta = {"tables": {"doccab": {"columns": ["TIPO", "FECHA"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert "TIPO" in cols

    def test_get_siuo_columns_no_file(self):
        """Sin fichero de metadatos, devuelve lista vacía sin excepción."""
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"):
            cols = agent._get_siuo_columns("DOCCAB")
        assert cols == []

    # ── _get_siuo_record_count ────────────────────────────────────────────────

    def test_get_siuo_record_count_found(self, tmp_path):
        """Si existe record_count en el JSON, lo devuelve como int."""
        meta = {"tables": {"DOCCAB": {"record_count": 5432, "columns": ["TIPO"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count == 5432

    def test_get_siuo_record_count_row_count_field(self, tmp_path):
        """También acepta el campo 'row_count'."""
        meta = {"tables": {"DOCCAB": {"row_count": 999}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count == 999

    def test_get_siuo_record_count_not_found(self, tmp_path):
        """Si no hay conteo en el JSON, devuelve None."""
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count is None

    def test_get_siuo_record_count_no_file(self):
        """Sin fichero, devuelve None sin excepción."""
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count is None

    # ── _extract_columns_from_context ─────────────────────────────────────────

    def test_extract_columns_pattern1_cols(self):
        """Patrón 'TABLA | Cols: COL1, COL2' → extrae columnas."""
        agent = make_agent(db_context="DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL, CODCLIENTE")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert "TIPO" in cols
        assert "FECHA" in cols
        assert "IMPORTETOTAL" in cols

    def test_extract_columns_pattern2_parentheses(self):
        """Patrón 'TABLA (COL1, COL2)' → extrae columnas."""
        agent = make_agent(db_context="DOCCAB (TIPO, FECHA, SERIE, IMPORTETOTAL)")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert "TIPO" in cols
        assert "SERIE" in cols

    def test_extract_columns_pattern3_newline(self):
        """Patrón 'TABLA\\nColumnas: COL1, COL2' → extrae columnas."""
        agent = make_agent(db_context="DOCCAB\nColumnas: TIPO, FECHA, IMPORTETOTAL")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert "TIPO" in cols
        assert "FECHA" in cols

    def test_extract_columns_empty_context(self):
        """Con db_context vacío, devuelve lista vacía sin excepción."""
        agent = make_agent(db_context="")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert cols == []

    def test_extract_columns_table_not_in_context(self):
        """Si la tabla no está en el contexto, devuelve lista vacía."""
        agent = make_agent(db_context="CLIENTE | Cols: CODIGO, NOMBRE, TELEFONO")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert cols == []

    def test_extract_columns_no_exception_on_bad_input(self):
        """Con input malformado, no lanza excepción."""
        agent = make_agent(db_context="[[[invalid regex content")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert isinstance(cols, list)

    # ── Flujo real: BD falla → SIUO JSON → db_context ────────────────────────

    def test_explore_table_fallback_to_siuo_json(self, tmp_path):
        """
        Flujo real: BD Firebird falla → columnas obtenidas desde SIUO JSON.
        Verifica que _explore_table usa _get_siuo_columns como fallback.
        """
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO", "FECHA", "IMPORTETOTAL", "CODCLIENTE", "SERIE"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")

        # BD falla para todo
        agent = make_agent()
        agent.sql_executor = MagicMock(side_effect=Exception("Firebird no disponible"))

        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = agent._explore_table("DOCCAB", cfg)

        # Columnas obtenidas desde SIUO JSON
        assert "TIPO" in info.get("columns", [])
        assert info.get("columns_source") == "siuo_metadata"
        assert info.get("has_tipo") is True
        assert info.get("has_serie") is True

    def test_explore_table_fallback_to_db_context(self):
        """
        Flujo real: BD falla + SIUO JSON vacío → columnas desde db_context texto.
        """
        agent = make_agent(db_context="DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL")
        agent.sql_executor = MagicMock(side_effect=Exception("Firebird no disponible"))

        # Sin fichero de metadatos
        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = agent._explore_table("DOCCAB", cfg)

        # Columnas obtenidas desde db_context
        assert "TIPO" in info.get("columns", [])
        assert info.get("columns_source") == "db_context_text"

    def test_explore_table_all_sources_fail_no_exception(self):
        """
        Flujo real: BD falla + SIUO JSON vacío + db_context sin info.
        El agente continúa sin excepción con columnas vacías.
        """
        agent = make_agent(db_context="Sin información de tablas aquí.")
        agent.sql_executor = MagicMock(side_effect=Exception("Firebird no disponible"))

        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = agent._explore_table("DOCCAB", cfg)

        # No lanza excepción, devuelve info con columnas vacías
        assert isinstance(info, dict)
        assert info.get("columns", []) == []
        assert info.get("columns_source") == "unknown"
