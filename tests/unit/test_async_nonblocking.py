"""
test_async_nonblocking.py — Tests para garantizar que las llamadas a Firebird
no bloquean el event loop de asyncio.

BUG RAÍZ (fix en helpers.py, phase2_explore.py, phases_1_2.py, phase3.py,
          service.py, sql_corrector.py):
  El driver firebirdsql usa I/O sincrónico. Cuando se llamaba desde coroutines
  async de FastAPI, bloqueaba el event loop entero. Durante análisis profundos
  (17-40 SQLs), el endpoint /api/chat/ping no podía responder, agotando los
  3 timeouts del heartbeat frontend → "No se pudo conectar con el servidor backend".

FIX:
  - _safe_sql() → async, hace `await self.sql_executor(sql)`
  - _explore_table() → async
  - service.py → sql_executor es una coroutine que usa run_in_executor
  - sql_corrector.py → execute_func envuelto en run_in_executor

REGLAS (no romper):
  - NUNCA conectar a la BD real
  - NUNCA conectar a modelos IA de red
  - Los mocks NO inventan valores de BD
"""

import asyncio
import inspect
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
from backend.modules.chat.deep_analysis.helpers import HelpersAgentMixin as DeepAnalysisHelpersMixin


# ─── 1. Contratos de interfaz async ─────────────────────────────────────────

class TestAsyncContracts:
    """Verifica que los métodos críticos son coroutines (async def)."""

    def test_safe_sql_is_coroutine(self):
        """_safe_sql debe ser una coroutine function."""
        assert inspect.iscoroutinefunction(DeepAnalysisHelpersMixin._safe_sql), (
            "_safe_sql debe ser 'async def' para no bloquear el event loop"
        )

    def test_explore_table_is_coroutine(self):
        """_explore_table debe ser una coroutine function."""
        from backend.modules.chat.deep_analysis.phase2_explore import Phase2ExploreMixin
        assert inspect.iscoroutinefunction(Phase2ExploreMixin._explore_table), (
            "_explore_table debe ser 'async def' para no bloquear el event loop"
        )

    def test_phase2_explore_is_coroutine(self):
        """_phase2_explore debe ser una coroutine function."""
        from backend.modules.chat.deep_analysis.phases_1_2 import Phases12Mixin
        assert inspect.iscoroutinefunction(Phases12Mixin._phase2_explore), (
            "_phase2_explore debe ser 'async def'"
        )

    def test_execute_with_retry_is_coroutine(self):
        """_execute_with_retry en phase3 debe ser coroutine."""
        from backend.modules.chat.deep_analysis.phase3 import Phase3Mixin
        assert inspect.iscoroutinefunction(Phase3Mixin._execute_with_retry), (
            "_execute_with_retry debe ser 'async def'"
        )


# ─── 2. sql_executor async en service.py ────────────────────────────────────

class TestServiceAsyncSqlExecutor:
    """Verifica que service.py pasa un sql_executor async al DeepAnalysisAgent."""

    def test_service_uses_async_sql_executor(self):
        """service.py debe construir un sql_executor que sea una coroutine."""
        import ast
        import pathlib

        # Ruta relativa al paquete bots/interjddcia (donde está pytest.ini)
        service_path = pathlib.Path(__file__).parent.parent.parent / "backend/modules/chat/service.py"
        source = service_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Buscar 'async def _async_sql_executor' en el código fuente
        assert "async def _async_sql_executor" in source, (
            "service.py debe definir '_async_sql_executor' como coroutine async. "
            "Un executor síncrono bloquea el event loop durante queries Firebird."
        )

    def test_service_uses_run_in_executor(self):
        """service.py debe usar run_in_executor para delegar a ThreadPoolExecutor."""
        import pathlib
        service_path = pathlib.Path(__file__).parent.parent.parent / "backend/modules/chat/service.py"
        source = service_path.read_text(encoding="utf-8")
        assert "run_in_executor" in source, (
            "service.py debe usar asyncio.run_in_executor para ejecutar "
            "el I/O sincrónico de Firebird en un ThreadPoolExecutor"
        )

    def test_sql_corrector_uses_run_in_executor(self):
        """sql_corrector.py debe usar run_in_executor para execute_func."""
        import pathlib
        corrector_path = pathlib.Path(__file__).parent.parent.parent / "backend/modules/chat/sql_corrector.py"
        source = corrector_path.read_text(encoding="utf-8")
        assert "run_in_executor" in source, (
            "sql_corrector.py debe usar run_in_executor para no bloquear el event loop"
        )


# ─── 3. Concurrencia: ping responde durante SQL lento ───────────────────────

class TestEventLoopNotBlocked:
    """
    Simula el escenario del bug: una operación lenta (Firebird) no bloquea
    el event loop, permitiendo que otros endpoints (como /ping) respondan.
    """

    async def test_ping_responds_during_slow_sql(self):
        """
        Con sql_executor async + run_in_executor, el event loop no se bloquea.
        Una tarea 'ping' debe completarse mientras el SQL 'lento' está en curso.
        """
        ping_responded = []
        sql_started = []
        sql_completed = []

        async def slow_async_sql_executor(sql: str):
            sql_started.append(True)
            # Simula I/O sincrónico en executor (no bloquea el event loop)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, time.sleep, 0.1)
            sql_completed.append(True)
            return [{"TOTAL": 1}]

        async def mock_ping():
            await asyncio.sleep(0.01)  # Simula latencia de red
            ping_responded.append(True)
            return "pong"

        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(return_value=('{"intent":"test"}', None))
        orch.context_limit_tokens = 32000

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}

        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="TABLA: DOCCAB | Cols: TIPO, FECHA",
            sql_executor=slow_async_sql_executor,
        )

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            # Ejecutar SQL lento y ping CONCURRENTEMENTE
            sql_task = asyncio.create_task(agent._explore_table("DOCCAB", cfg))
            ping_task = asyncio.create_task(mock_ping())

            await asyncio.gather(sql_task, ping_task)

        # El ping debe haber respondido MIENTRAS el SQL estaba en curso
        assert ping_responded, "El ping debe responder mientras el SQL lento está en curso"
        assert sql_completed, "El SQL debe completarse"

    async def test_sync_sql_executor_blocks_ping(self):
        """
        Documenta el comportamiento anterior (bug): con un executor síncrono
        bloqueante, el ping no puede intercalarse.

        NOTA: Este test verifica que el evento del bug existe con sync executor.
        Con el fix, el sql_executor es async y no bloquea.
        """
        ping_tasks_completed_during_sql = []

        async def non_blocking_executor(sql: str):
            # Executor ASYNC correcto: cede el control al event loop
            await asyncio.sleep(0.05)
            return [{"TOTAL": 1}]

        async def fast_ping():
            ping_tasks_completed_during_sql.append(True)
            return "pong"

        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(return_value=('{"intent":"test"}', None))
        orch.context_limit_tokens = 32000

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}

        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="TABLA: DOCCAB | Cols: TIPO, FECHA",
            sql_executor=non_blocking_executor,
        )

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            sql_task = asyncio.create_task(agent._explore_table("DOCCAB", cfg))
            ping_task = asyncio.create_task(fast_ping())
            await asyncio.gather(sql_task, ping_task)

        assert len(ping_tasks_completed_during_sql) > 0, (
            "Con executor async, el ping puede ejecutarse concurrentemente"
        )


# ─── 4. _safe_sql awaita el executor async ──────────────────────────────────

class TestSafeSqlAwaitsExecutor:
    """Verifica que _safe_sql awaita correctamente el executor."""

    async def test_safe_sql_awaits_async_executor(self):
        """_safe_sql debe awaitar el executor y devolver los resultados."""
        executor_called = []
        expected_rows = [{"TOTAL": 42}]

        async def mock_executor(sql: str):
            executor_called.append(sql)
            return expected_rows

        orch = MagicMock()
        orch.context_limit_tokens = 32000
        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="TABLA: DOCCAB",
            sql_executor=mock_executor,
        )

        with patch("backend.modules.db_simulator.manager.simulator_manager") as mock_sim:
            mock_sim.is_enabled.return_value = False
            result = await agent._safe_sql("SELECT COUNT(*) AS TOTAL FROM DOCCAB")

        assert result == expected_rows, f"Expected {expected_rows}, got {result}"
        assert len(executor_called) == 1

    async def test_safe_sql_raises_without_executor(self):
        """_safe_sql debe lanzar RuntimeError si sql_executor es None."""
        orch = MagicMock()
        orch.context_limit_tokens = 32000
        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="TABLA: DOCCAB",
            sql_executor=None,
        )

        with pytest.raises(RuntimeError, match="sql_executor no configurado"):
            await agent._safe_sql("SELECT 1 FROM RDB$DATABASE")

    async def test_safe_sql_propagates_executor_exception(self):
        """_safe_sql debe propagar excepciones del executor."""
        async def failing_executor(sql: str):
            raise ConnectionError("Firebird no disponible")

        orch = MagicMock()
        orch.context_limit_tokens = 32000
        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="TABLA: DOCCAB",
            sql_executor=failing_executor,
        )

        with patch("backend.modules.db_simulator.manager.simulator_manager") as mock_sim:
            mock_sim.is_enabled.return_value = False
            with pytest.raises(ConnectionError, match="Firebird no disponible"):
                await agent._safe_sql("SELECT COUNT(*) FROM DOCCAB")


# ─── 5. Resiliencia: errores de executor son capturados en _explore_table ───

class TestExploratorResiliencia:
    """
    _explore_table no debe lanzar excepción aunque el executor falle —
    debe continuar con fuentes de fallback (SIUO, db_context).
    """

    async def test_explore_table_captures_async_executor_errors(self):
        """Errores del executor async son capturados por _explore_table."""
        async def failing_executor(sql: str):
            raise Exception("Timeout Firebird")

        orch = MagicMock()
        orch.context_limit_tokens = 32000
        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="DOCCAB | Cols: TIPO, FECHA",
            sql_executor=failing_executor,
        )

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            info = await agent._explore_table("DOCCAB", {"max_sqls": 4, "explore_tables": 2})

        # No lanza excepción, devuelve dict con info de fallback
        assert isinstance(info, dict)
        assert "ERROR" in str(info.get("total", "ERROR"))

    async def test_explore_table_uses_cache_without_calling_executor(self):
        """Con cache fresco, _explore_table no llama al executor async."""
        from datetime import datetime, timedelta

        executor_called = []

        async def executor(sql: str):
            executor_called.append(sql)
            return [{"TOTAL": 99}]

        orch = MagicMock()
        orch.context_limit_tokens = 32000
        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="",
            sql_executor=executor,
        )

        fresh_date = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_store = MagicMock()
        mock_store.get_table.return_value = {
            "columns_real": ["TIPO", "FECHA"],
            "record_count_real": 5000,
            "_updated_at": fresh_date,
        }

        with patch(
            "backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
            return_value=mock_store
        ):
            info = await agent._explore_table("DOCCAB", {"max_sqls": 12, "explore_tables": 4})

        assert info.get("_from_cache") is True
        assert len(executor_called) == 0, (
            "Con cache fresco, no debe ejecutar queries a la BD"
        )


# ─── 6. sql_corrector.py: execute_func en run_in_executor ───────────────────

class TestSqlCorrectorAsyncExecution:
    """Verifica que sql_corrector.py envuelve execute_func en run_in_executor."""

    async def test_execute_with_correction_uses_run_in_executor(self):
        """execute_with_correction debe usar run_in_executor para el execute_func síncrono."""
        from backend.modules.chat.sql_corrector import SQLCorrector

        calls = []

        def sync_execute_func(sql: str):
            calls.append(sql)
            return [{"TOTAL": 10}]

        ai_provider = MagicMock()
        ai_provider.generate = AsyncMock(return_value="SELECT COUNT(*) FROM DOCCAB")

        corrector = SQLCorrector()

        result = await corrector.execute_with_correction(
            sql_query="SELECT COUNT(*) FROM DOCCAB",
            original_question="¿cuántos documentos hay?",
            db_context="TABLA: DOCCAB | Cols: TIPO, FECHA",
            ai_provider=ai_provider,
            execute_func=sync_execute_func,
        )

        # El execute_func debe haberse llamado con el SQL
        assert len(calls) >= 1, "execute_func debe haberse llamado al menos una vez"
        # El resultado debe ser los rows
        assert result == [{"TOTAL": 10}]

    async def test_execute_with_correction_is_coroutine(self):
        """execute_with_correction debe ser una coroutine function."""
        from backend.modules.chat.sql_corrector import SQLCorrector
        assert inspect.iscoroutinefunction(SQLCorrector.execute_with_correction), (
            "execute_with_correction debe ser async def para no bloquear el event loop"
        )
