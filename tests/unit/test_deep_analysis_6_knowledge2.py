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

class TestPhase2KnowledgeStoreCache:
    """
    Tests para el cache-first del KnowledgeStore en _explore_table.
    Si hay datos frescos (< 7 días), se usan sin queries a la BD.
    """

    async def test_cache_hit_skips_sql_queries(self):
        """Con cache fresco, no se ejecutan queries a la BD."""
        from datetime import datetime, timedelta
        agent = make_agent()
        # BD que lanzaría excepción si se consulta
        agent.sql_executor = AsyncMock(side_effect=Exception("NO DEBERÍA LLAMARSE"))

        fresh_date = (datetime.now() - timedelta(days=1)).isoformat()
        cached_data = {
            "columns_real": ["TIPO", "FECHA", "IMPORTETOTAL", "CODCLIENTE"],
            "record_count_real": 74034,
            "_updated_at": fresh_date,
        }

        mock_store = MagicMock()
        mock_store.get_table.return_value = cached_data

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 12, "explore_tables": 4}
            info = await agent._explore_table("DOCCAB", cfg)

        # No debe haber llamado al sql_executor
        agent.sql_executor.assert_not_called()
        # Debe usar los datos del cache
        assert info["total"] == 74034
        assert "TIPO" in info["columns"]
        assert info.get("_from_cache") is True

    async def test_cache_miss_executes_sql(self):
        """Sin cache, se ejecutan queries a la BD."""
        agent = make_agent()
        sql_called = [False]

        async def executor(sql):
            sql_called[0] = True
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 1000}]
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}, {"COL": "FECHA"}]
            return [{"NULOS": 0}]

        agent.sql_executor = executor

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}  # Cache vacío

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = await agent._explore_table("DOCCAB", cfg)

        assert sql_called[0] is True

    async def test_stale_cache_re_explores(self):
        """Cache obsoleto (> 7 días) → re-explora desde la BD."""
        from datetime import datetime, timedelta
        agent = make_agent()
        sql_called = [False]

        async def executor(sql):
            sql_called[0] = True
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 999}]
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}]
            return [{"NULOS": 0}]

        agent.sql_executor = executor

        stale_date = (datetime.now() - timedelta(days=10)).isoformat()
        cached_data = {
            "columns_real": ["TIPO"],
            "record_count_real": 100,
            "_updated_at": stale_date,
        }

        mock_store = MagicMock()
        mock_store.get_table.return_value = cached_data

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = await agent._explore_table("DOCCAB", cfg)

        # Debe haber re-explorado (sql_called=True)
        assert sql_called[0] is True
        # El conteo debe ser el nuevo (999), no el del cache (100)
        assert info.get("total") == 999

    async def test_force_refresh_ignores_cache(self):
        """cfg['force_refresh']=True → ignora el cache aunque sea fresco."""
        from datetime import datetime, timedelta
        agent = make_agent()
        sql_called = [False]

        async def executor(sql):
            sql_called[0] = True
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 500}]
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}]
            return [{"NULOS": 0}]

        agent.sql_executor = executor

        fresh_date = (datetime.now() - timedelta(hours=1)).isoformat()
        cached_data = {
            "columns_real": ["TIPO", "FECHA"],
            "record_count_real": 74034,
            "_updated_at": fresh_date,
        }

        mock_store = MagicMock()
        mock_store.get_table.return_value = cached_data

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2, "force_refresh": True}
            info = await agent._explore_table("DOCCAB", cfg)

        # Debe haber re-explorado a pesar del cache fresco
        assert sql_called[0] is True

    async def test_cache_hit_restores_tipo_distribution(self):
        """Cache hit restaura tipo_distribution si está cacheada."""
        from datetime import datetime, timedelta
        agent = make_agent()
        agent.sql_executor = AsyncMock(side_effect=Exception("NO DEBERÍA LLAMARSE"))

        fresh_date = (datetime.now() - timedelta(hours=2)).isoformat()
        cached_data = {
            "columns_real": ["TIPO", "FECHA"],
            "record_count_real": 5000,
            "_updated_at": fresh_date,
            "tipo_distribution": [{"TIPO": 0, "N": 3000}, {"TIPO": 13, "N": 2000}],
        }

        mock_store = MagicMock()
        mock_store.get_table.return_value = cached_data

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 12, "explore_tables": 4}
            info = await agent._explore_table("DOCCAB", cfg)

        assert info.get("tipo_distribution") is not None
        assert len(info["tipo_distribution"]) == 2

    async def test_cache_no_crash_on_store_error(self):
        """Si el KnowledgeStore falla, continúa con exploración normal."""
        agent = make_agent()
        sql_called = [False]

        async def executor(sql):
            sql_called[0] = True
            if "COUNT(*)" in sql and "NULOS" not in sql:
                return [{"TOTAL": 100}]
            if "RDB$RELATION_FIELDS" in sql:
                return [{"COL": "TIPO"}]
            return [{"NULOS": 0}]

        agent.sql_executor = executor

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            side_effect=Exception("KnowledgeStore no disponible")
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = await agent._explore_table("DOCCAB", cfg)

        # No debe lanzar excepción, debe explorar desde la BD
        assert isinstance(info, dict)
        assert sql_called[0] is True


# ─── Tests NUEVOS: Persistencia en KnowledgeStore tras exploración ────────────

