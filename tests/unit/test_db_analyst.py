"""
test_db_analyst.py — Tests unitarios del módulo Analista BD.

CAPA: unit (sin LLM real, sin BD Firebird real)
MÓDULO: backend.modules.db_analyst
EJECUTAR: .venv/Scripts/pytest tests/unit/test_db_analyst.py -v -s

COBERTURA:
  - AnalystSessionStore: CRUD de sesiones y mensajes con provenance
  - Provenance: serialización/deserialización Pydantic
  - AnalystService._build_system_prompt: incluye historial, nota simulador, reglas SQL
  - AnalystService._execute_sql_sync: ejecuta contra simulador SQLite (sin Firebird real)
  - AnalystService.process (mocked): flujo completo con LLM mockeado
  - Endpoints HTTP (TestClient): /status, /session/new, /sessions, /chat (mocked)
"""

import sys
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Añadir raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.modules.db_analyst.models import Provenance, AnalystChatRequest
from backend.modules.db_analyst.session_store import AnalystSessionStore


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def store(tmp_path):
    """AnalystSessionStore con BD SQLite temporal."""
    db_path = str(tmp_path / "test_analyst.db")
    return AnalystSessionStore(db_path=db_path)


@pytest.fixture
def sample_prov():
    return Provenance(
        sql_generated="SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13",
        sql_executed="SELECT FIRST 100 COUNT(*) FROM DOCCAB WHERE TIPO=13",
        raw_results=[{"COUNT": 23}],
        tables_used=["DOCCAB"],
        siuo_keywords=["facturas"],
        siuo_source="concept_index",
        context_tokens=487,
        data_source="simulator",
        model_used="jddcia-qwen3-30b",
        execution_time_ms=1250,
        requires_db=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Provenance (modelo Pydantic)
# ═══════════════════════════════════════════════════════════════════════════════

class TestProvenance:
    def test_defaults(self):
        p = Provenance()
        assert p.data_source == "simulator"
        assert p.tables_used == []
        assert p.requires_db is True
        assert p.raw_results is None

    def test_serialization_roundtrip(self, sample_prov):
        json_str = sample_prov.model_dump_json()
        restored = Provenance.model_validate_json(json_str)
        assert restored.sql_generated == sample_prov.sql_generated
        assert restored.raw_results == sample_prov.raw_results
        assert restored.tables_used == ["DOCCAB"]
        assert restored.execution_time_ms == 1250

    def test_partial_provenance(self):
        """Respuesta conversacional sin SQL."""
        p = Provenance(requires_db=False, data_source="simulator")
        assert p.sql_executed is None
        assert p.raw_results is None
        assert p.requires_db is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: AnalystSessionStore
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalystSessionStore:
    def test_create_session(self, store):
        sid = store.create_session(model_id="test-model", title="Test session")
        assert len(sid) == 36  # UUID

    def test_list_sessions_empty(self, store):
        assert store.list_sessions() == []

    def test_list_sessions_after_create(self, store):
        import time
        store.create_session(title="Primera")
        time.sleep(0.01)  # asegurar updated_at diferente
        store.create_session(title="Segunda")
        sessions = store.list_sessions()
        assert len(sessions) == 2
        titles = [s.title for s in sessions]
        assert "Primera" in titles
        assert "Segunda" in titles

    def test_update_title(self, store):
        sid = store.create_session(title="Viejo")
        store.update_title(sid, "Nuevo")
        sessions = store.list_sessions()
        assert sessions[0].title == "Nuevo"

    def test_delete_session(self, store):
        sid = store.create_session(title="Para borrar")
        assert len(store.list_sessions()) == 1
        store.delete_session(sid)
        assert store.list_sessions() == []

    def test_add_message_without_provenance(self, store):
        sid = store.create_session()
        msg_id = store.add_message(sid, "user", "¿Cuántos clientes hay?")
        assert msg_id is not None

    def test_add_message_with_provenance(self, store, sample_prov):
        sid = store.create_session()
        store.add_message(sid, "user", "¿Cuántas facturas?")
        msg_id = store.add_message(sid, "assistant", "Hay 23 facturas.", provenance=sample_prov)
        assert msg_id is not None

    def test_get_messages(self, store, sample_prov):
        sid = store.create_session()
        store.add_message(sid, "user", "¿Cuántas facturas?")
        store.add_message(sid, "assistant", "Hay 23 facturas.", provenance=sample_prov)
        msgs = store.get_messages(sid)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert msgs[1].provenance is not None
        assert msgs[1].provenance.tables_used == ["DOCCAB"]

    def test_get_messages_provenance_roundtrip(self, store, sample_prov):
        sid = store.create_session()
        store.add_message(sid, "assistant", "Respuesta", provenance=sample_prov)
        msgs = store.get_messages(sid)
        p = msgs[0].provenance
        assert p.sql_generated == "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13"
        assert p.raw_results == [{"COUNT": 23}]
        assert p.execution_time_ms == 1250

    def test_get_last_assistant_message(self, store, sample_prov):
        sid = store.create_session()
        store.add_message(sid, "user", "Pregunta 1")
        store.add_message(sid, "assistant", "Respuesta 1", provenance=sample_prov)
        store.add_message(sid, "user", "Pregunta 2")
        store.add_message(sid, "assistant", "Respuesta 2")
        last = store.get_last_assistant_message(sid)
        assert last.content == "Respuesta 2"

    def test_get_last_assistant_message_none(self, store):
        sid = store.create_session()
        assert store.get_last_assistant_message(sid) is None

    def test_messages_empty_session(self, store):
        sid = store.create_session()
        assert store.get_messages(sid) == []

    def test_cascade_delete_messages(self, store):
        sid = store.create_session()
        store.add_message(sid, "user", "Hola")
        store.delete_session(sid)
        assert store.get_messages(sid) == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: AnalystService._build_system_prompt
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildSystemPrompt:
    def setup_method(self):
        from backend.modules.db_analyst.service import AnalystService
        self.service = AnalystService()

    def test_contains_sql_rules(self):
        prompt = self.service._build_system_prompt("esquema", [], "firebird")
        assert "FIRST N" in prompt or "FIRST" in prompt
        assert "TIPO" in prompt

    def test_contains_history(self):
        history = [
            {"role": "user", "content": "¿Cuántos clientes hay?"},
            {"role": "assistant", "content": "Hay 60 clientes."},
        ]
        prompt = self.service._build_system_prompt("esquema", history, "simulator")
        assert "¿Cuántos clientes hay?" in prompt
        assert "HISTORIAL" in prompt

    def test_simulator_note_when_simulator(self):
        prompt = self.service._build_system_prompt("esquema", [], "simulator")
        assert "SIMULADOR" in prompt or "simulator" in prompt.lower()

    def test_no_simulator_note_when_firebird(self):
        prompt = self.service._build_system_prompt("esquema", [], "firebird")
        assert "SIMULADOR ACTIVO" not in prompt

    def test_history_truncated_to_last_6(self):
        history = [
            {"role": "user", "content": f"Pregunta {i}"}
            for i in range(10)
        ]
        prompt = self.service._build_system_prompt("esquema", history, "simulator")
        # Solo las últimas 6 (Pregunta 4..9)
        assert "Pregunta 9" in prompt
        assert "Pregunta 0" not in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: AnalystService._execute_sql_sync (contra simulador SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteSqlSync:
    def setup_method(self):
        from backend.modules.db_analyst.service import AnalystService
        self.service = AnalystService()

    def test_simple_query_against_simulator(self):
        """Ejecuta SELECT COUNT(*) contra el simulador — debe devolver resultado."""
        with patch("backend.modules.db_simulator.manager.simulator_manager") as mock_mgr:
            mock_mgr.is_enabled.return_value = True
            mock_mgr.ensure_ready.return_value = None

            from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
            with patch.object(SimulatedFirebirdDriver, "execute_query", return_value=[{"C": 5}]):
                with patch.object(SimulatedFirebirdDriver, "connect", return_value=None):
                    with patch.object(SimulatedFirebirdDriver, "disconnect", return_value=None):
                        result = self.service._execute_sql_sync("SELECT COUNT(*) AS C FROM ARTICULO")
                        assert result == [{"C": 5}]

    def test_returns_list(self):
        with patch("backend.modules.db_simulator.manager.simulator_manager") as mock_mgr:
            mock_mgr.is_enabled.return_value = True
            mock_mgr.ensure_ready.return_value = None

            from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
            with patch.object(SimulatedFirebirdDriver, "execute_query", return_value=[]):
                with patch.object(SimulatedFirebirdDriver, "connect", return_value=None):
                    with patch.object(SimulatedFirebirdDriver, "disconnect", return_value=None):
                        result = self.service._execute_sql_sync("SELECT * FROM FAMILIA")
                        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: AnalystService.process (LLM mockeado)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalystServiceProcess:
    def setup_method(self):
        from backend.modules.db_analyst.service import AnalystService
        self.service = AnalystService()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_process_conversational_no_sql(self):
        """Si la IA no genera SQL, la respuesta es conversacional (requires_db=False)."""
        self.service.orchestrator.execute_with_fallback = AsyncMock(
            return_value=("Hola, ¿en qué puedo ayudarte?", "test-model")
        )
        with patch("backend.modules.db_analyst.service.AnalystService._get_data_source", return_value="simulator"):
            with patch("backend.modules.db_analyst.service.AnalystService._get_siuo_context",
                       return_value=("esquema", {"source": "concept_index", "tables_used": [], "keywords_found": [], "tokens_estimated": 0})):
                response, prov = self._run(self.service.process("hola", [], "test-model"))
                assert "Hola" in response
                assert prov.requires_db is False
                assert prov.sql_generated is None

    def test_process_with_sql_response(self):
        """Si la IA genera SQL, se ejecuta y se interpreta."""
        sql = "SELECT COUNT(*) AS C FROM DOCCAB WHERE TIPO=13"
        llm_responses = [
            (f"Aquí el SQL:\n```sql\n{sql}\n```", "test-model"),  # 1ª llamada: genera SQL
            ("Hay 23 facturas en la BD.", "test-model"),            # 2ª llamada: interpreta
        ]
        call_count = [0]
        async def mock_fallback(**kwargs):
            r = llm_responses[call_count[0]]
            call_count[0] += 1
            return r

        self.service.orchestrator.execute_with_fallback = mock_fallback

        with patch("backend.modules.db_analyst.service.AnalystService._get_data_source", return_value="simulator"):
            with patch("backend.modules.db_analyst.service.AnalystService._get_siuo_context",
                       return_value=("esquema", {"source": "concept_index", "tables_used": ["DOCCAB"], "keywords_found": ["facturas"], "tokens_estimated": 200})):
                with patch.object(self.service.sql_corrector, "execute_with_correction",
                                  new=AsyncMock(return_value=[{"C": 23}])):
                    with patch("backend.core.config.model_manager.model_manager.get_model", return_value=None):
                        response, prov = self._run(self.service.process("¿Cuántas facturas hay?", [], "test-model"))
                        assert prov.sql_generated == sql
                        assert prov.raw_results == [{"C": 23}]
                        assert prov.requires_db is True
                        assert "facturas" in response.lower() or "23" in response

    def test_process_sql_error_returns_error_message(self):
        """Si el SQL falla, devuelve mensaje de error con el SQL."""
        sql = "SELECT COUNT(*) FROM DOCCAB"
        self.service.orchestrator.execute_with_fallback = AsyncMock(
            return_value=(f"```sql\n{sql}\n```", "test-model")
        )
        with patch("backend.modules.db_analyst.service.AnalystService._get_data_source", return_value="simulator"):
            with patch("backend.modules.db_analyst.service.AnalystService._get_siuo_context",
                       return_value=("esquema", {"source": "fallback", "tables_used": [], "keywords_found": [], "tokens_estimated": 0})):
                with patch.object(self.service.sql_corrector, "execute_with_correction",
                                  new=AsyncMock(side_effect=Exception("tabla no existe"))):
                    with patch("backend.core.config.model_manager.model_manager.get_model", return_value=None):
                        response, prov = self._run(self.service.process("Consulta rota", [], "test-model"))
                        assert "Error" in response or "error" in response
                        assert prov.raw_results == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Router HTTP (FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalystRouter:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from backend.modules.db_analyst.router import router

        app = FastAPI()
        app.include_router(router, prefix="/api/db-analyst")
        self.client = TestClient(app)

    def test_status_endpoint(self):
        with patch("backend.modules.db_simulator.manager.simulator_manager") as mock_mgr:
            mock_mgr.is_enabled.return_value = True
            mock_mgr.get_status.return_value = {"status": "ready"}
            with patch("backend.modules.db_explorer.deep_indexer_service.TABLE_INDEX_PATH") as mock_path:
                with patch("backend.modules.db_explorer.deep_indexer_service._load_json", return_value={"T1": {}, "T2": {}}):
                    res = self.client.get("/api/db-analyst/status")
                    assert res.status_code == 200
                    data = res.json()
                    assert "data_source" in data
                    assert "siuo_ready" in data

    def test_new_session(self):
        res = self.client.post("/api/db-analyst/session/new")
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert len(data["session_id"]) == 36

    def test_list_sessions_empty(self):
        res = self.client.get("/api/db-analyst/sessions")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_get_session_empty(self):
        new_res = self.client.post("/api/db-analyst/session/new")
        sid = new_res.json()["session_id"]
        res = self.client.get(f"/api/db-analyst/session/{sid}")
        assert res.status_code == 200
        assert res.json()["messages"] == []

    def test_delete_session(self):
        new_res = self.client.post("/api/db-analyst/session/new")
        sid = new_res.json()["session_id"]
        del_res = self.client.delete(f"/api/db-analyst/session/{sid}")
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

    def test_chat_endpoint_mocked(self):
        """Test del endpoint /chat con LLM y BD mockeados."""
        from backend.modules.db_analyst import router as router_module

        with patch.object(router_module._service, "process",
                          new=AsyncMock(return_value=(
                              "Hay 60 clientes.",
                              Provenance(data_source="simulator", requires_db=True, tables_used=["CLIENTE"])
                          ))):
            res = self.client.post("/api/db-analyst/chat", json={
                "message": "¿Cuántos clientes hay?",
                "model_id": "jddcia-qwen3-30b",
            })
            assert res.status_code == 200
            data = res.json()
            assert "response" in data
            assert "provenance" in data
            assert "session_id" in data
            assert data["provenance"]["tables_used"] == ["CLIENTE"]

    def test_justify_without_session_fails(self):
        """Justificar sin sesión con mensajes debe retornar 404."""
        new_res = self.client.post("/api/db-analyst/session/new")
        sid = new_res.json()["session_id"]
        res = self.client.post("/api/db-analyst/chat/justify", json={"session_id": sid})
        assert res.status_code == 404
