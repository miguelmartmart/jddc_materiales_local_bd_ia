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
            "backend.modules.chat.deep_analysis.knowledge_store.get_knowledge_store",
            return_value=mock_store
        ):
            result = agent._phase0_lan_optimize(cfg)

        assert result["known_sqls_count"] == 5

    def test_no_crash_on_knowledge_store_error(self):
        """No lanza excepción si el KnowledgeStore falla."""
        agent = make_agent()
        cfg = {"max_sqls": 12, "explore_tables": 6}

        with patch(
            "backend.modules.chat.deep_analysis.knowledge_store.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phase3.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phase3.get_knowledge_store",
            return_value=mock_store
        ):
            result = agent._get_known_patterns_text("test", {})

        assert result == ""

    def test_no_crash_on_store_error(self):
        """No lanza excepción si el KnowledgeStore falla."""
        agent = make_agent()
        with patch(
            "backend.modules.chat.deep_analysis.phase3.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phase3.get_knowledge_store",
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
            "backend.modules.chat.deep_analysis.phase3.get_knowledge_store",
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
            with patch("backend.modules.chat.deep_analysis.phase4.get_context_retriever") as mock_cr:
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
            with patch("backend.modules.chat.deep_analysis.phase4.get_context_retriever") as mock_cr:
                mock_cr.return_value.get_context.return_value = ("", {"tables_used": [], "source": "fallback"})
                phase = await agent._phase3_investigate(
                    "test", phase1_data, phase2_data, result, cfg
                )
            return phase

        phase = asyncio.get_event_loop().run_until_complete(run())
        assert phase is not None


# ─── Tests: Fase 4b aprendizaje permanente ───────────────────────────────────

