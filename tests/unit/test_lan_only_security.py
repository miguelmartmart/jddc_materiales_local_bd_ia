"""
TEST DE SEGURIDAD: AI_LOCAL_ONLY — Garantía de no salida a internet

OBJETIVO: Verificar al 100% que cuando ai_local_only=true, NINGUNA llamada
a modelos de internet se realiza, bajo NINGUNA circunstancia:
  - Fallo del modelo LAN en el primer intento
  - Fallo del modelo LAN en múltiples intentos consecutivos
  - Excepción inesperada en el modelo LAN
  - Modelo LAN devuelve respuesta vacía
  - Múltiples modelos LAN configurados, todos fallan
  - Modelo LAN falla N veces y luego responde (reintentos infinitos)

GARANTÍA: Si alguno de estos tests falla, significa que datos del usuario
podrían estar saliendo a internet. CRÍTICO.

Constantes centralizadas en:
  backend/core/utils/network_audit_constants.py
    → LocalModelIds.ALL       — IDs de modelos LAN
    → KnownInternetModelIds.IDS — IDs de modelos de internet

Autor: DEVIA System
"""

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Constantes centralizadas (FUENTE ÚNICA DE VERDAD) ───────────────────────
from backend.core.utils.network_audit_constants import (
    LocalModelIds,
    KnownInternetModelIds,
)

# Aliases cortos para legibilidad en los tests
LAN_MODEL_ID_MDNS  = LocalModelIds.QWEN3_MDNS   # "jddcia-qwen3-30b"
LAN_MODEL_ID_IP    = LocalModelIds.QWEN3_IP      # "jddcia-qwen3-30b-ip"
LAN_MODEL_IDS      = LocalModelIds.ALL           # frozenset con ambos
INTERNET_MODEL_IDS = KnownInternetModelIds.IDS   # frozenset con todos los externos


# ─── Helpers: crear modelos de prueba ────────────────────────────────────────

def _make_lan_model(model_id: str, name: str) -> dict:
    """Crea un modelo LAN de prueba."""
    return {
        "id": model_id,
        "name": name,
        "model_id": "unified-main",
        "schema": "jddcia",
        "provider": "jddcia",
        "api_key": "test-lan-key",
        "base_url": "http://jddcia.local/api/vlm/v1",
        "enabled": True,
        "score": 100,
    }


def _make_internet_model(model_id: str, name: str) -> dict:
    """Crea un modelo de internet de prueba."""
    return {
        "id": model_id,
        "name": name,
        "model_id": model_id,
        "schema": "groq",
        "provider": "groq",
        "api_key": "test-internet-key",
        "enabled": True,
        "score": 80,
    }


# Lista mixta: modelos LAN + modelos de internet
ALL_MODELS = [
    _make_lan_model(LAN_MODEL_ID_MDNS, "Qwen3 VL 30B (JDDC LAN — mDNS)"),
    _make_lan_model(LAN_MODEL_ID_IP,   "Qwen3 VL 30B (JDDC LAN — IP directa)"),
    _make_internet_model("llama-3.1-8b-instant",    "Llama 3.1 8B (Groq)"),
    _make_internet_model("llama-3.3-70b-versatile", "Llama 3.3 70B (Groq)"),
    _make_internet_model("gemma-3-4b",              "Gemma 3 4B (Groq)"),
    _make_internet_model("gpt-4o-mini",             "GPT-4o Mini"),
    _make_internet_model("gemini-flash",            "Gemini Flash"),
]


# ─── Helper: construir orchestrator con ai_local_only=true ───────────────────

def _build_orchestrator_lan_only(monkeypatch):
    """
    Construye un ModelFallbackOrchestrator con:
      - ai_local_only=true (parcheado en el módulo)
      - ModelManager mockeado para devolver ALL_MODELS
    """
    import backend.modules.chat.model_fallback_orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: True)

    from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
    orchestrator = ModelFallbackOrchestrator()
    orchestrator.model_manager = MagicMock()
    orchestrator.model_manager.list_models.return_value = ALL_MODELS
    orchestrator.model_manager.report_result = MagicMock()
    return orchestrator


# ─── Tracker de llamadas a modelos ───────────────────────────────────────────

class InternetCallTracker:
    """
    Intercepta llamadas a _try_model y registra qué modelos se intentaron.
    Lanza AssertionError inmediatamente si se intenta llamar a un modelo de internet.
    """
    def __init__(self):
        self.called_model_ids = []
        self.internet_calls = []

    def make_spy(self, lan_responses: dict):
        """
        lan_responses: {model_id: [resp1, resp2, ...]} — respuestas a devolver en orden.
        Si la lista se agota, devuelve None (fallo).
        """
        call_counts = {mid: 0 for mid in lan_responses}

        async def spy_try_model(model_config, system_prompt, user_message,
                                images=None, attempt=1):
            mid = model_config.get("id", "")
            self.called_model_ids.append(mid)

            # ¡CRÍTICO! Si se llama a un modelo de internet, el test FALLA inmediatamente
            if mid in INTERNET_MODEL_IDS:
                self.internet_calls.append(mid)
                raise AssertionError(
                    f"🚨 VIOLACIÓN DE SEGURIDAD: Se intentó llamar al modelo de internet '{mid}' "
                    f"con ai_local_only=true. Los datos del usuario NUNCA deben salir a internet."
                )

            # Modelo LAN: devolver respuesta según secuencia configurada
            responses = lan_responses.get(mid, [])
            idx = call_counts.get(mid, 0)
            call_counts[mid] = idx + 1
            return responses[idx] if idx < len(responses) else None

        return spy_try_model


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════════════════════

class TestLanOnlySecurity:
    """
    Suite de tests que garantizan que con ai_local_only=true,
    NINGÚN dato sale a internet bajo ninguna circunstancia.
    """

    @pytest.mark.asyncio
    async def test_lan_only_success_first_attempt(self, monkeypatch):
        """
        CASO FELIZ: El modelo LAN responde en el primer intento.
        Verificar que solo se llama al modelo LAN y no a ningún modelo de internet.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()

        spy = tracker.make_spy({
            LAN_MODEL_ID_MDNS: ["SELECT FIRST 6 * FROM ARTICULO"],
            LAN_MODEL_ID_IP:   [],
        })
        orchestrator._try_model = spy

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="Eres un asistente SQL.",
            user_message="dame los 6 artículos con más compras",
        )

        assert response == "SELECT FIRST 6 * FROM ARTICULO"
        assert model_id == LAN_MODEL_ID_MDNS
        assert len(tracker.internet_calls) == 0, (
            f"🚨 Se llamaron modelos de internet: {tracker.internet_calls}"
        )
        assert all(mid in LAN_MODEL_IDS for mid in tracker.called_model_ids)

    @pytest.mark.asyncio
    async def test_lan_only_first_fails_second_lan_succeeds(self, monkeypatch):
        """
        El modelo LAN mDNS falla, el modelo LAN IP directa responde.
        NUNCA se debe llamar a internet.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()

        spy = tracker.make_spy({
            LAN_MODEL_ID_MDNS: [None],                              # Falla
            LAN_MODEL_ID_IP:   ["SELECT FIRST 10 * FROM CLIENTE"],  # Éxito
        })
        orchestrator._try_model = spy
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="dame los clientes",
        )

        assert response == "SELECT FIRST 10 * FROM CLIENTE"
        assert model_id == LAN_MODEL_ID_IP
        assert len(tracker.internet_calls) == 0, (
            f"🚨 VIOLACIÓN: modelos de internet llamados: {tracker.internet_calls}"
        )

    @pytest.mark.asyncio
    async def test_lan_only_both_lan_fail_then_succeed_on_retry(self, monkeypatch):
        """
        Ambos modelos LAN fallan en la ronda 1.
        En la ronda 2, el primer modelo LAN responde.
        NUNCA se llama a internet entre medias.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()

        spy = tracker.make_spy({
            LAN_MODEL_ID_MDNS: [None, "SELECT FIRST 5 * FROM DOCCAB"],  # Falla, luego éxito
            LAN_MODEL_ID_IP:   [None, None],                             # Siempre falla
        })
        orchestrator._try_model = spy
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="dame las facturas",
        )

        assert response == "SELECT FIRST 5 * FROM DOCCAB"
        assert model_id == LAN_MODEL_ID_MDNS
        assert len(tracker.internet_calls) == 0, (
            f"🚨 VIOLACIÓN: modelos de internet llamados: {tracker.internet_calls}"
        )
        mdns_calls = tracker.called_model_ids.count(LAN_MODEL_ID_MDNS)
        assert mdns_calls == 2, f"Se esperaban 2 llamadas a mDNS, hubo {mdns_calls}"

    @pytest.mark.asyncio
    async def test_lan_only_exception_in_lan_never_falls_to_internet(self, monkeypatch):
        """
        El modelo LAN lanza una excepción (ConnectionError, Timeout, etc.).
        NUNCA se debe hacer fallback a internet.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()
        call_count = {"n": 0}

        async def spy_with_exception(model_config, system_prompt, user_message,
                                     images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called_model_ids.append(mid)

            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: modelo internet '{mid}' llamado")

            call_count["n"] += 1
            if call_count["n"] <= 3:
                raise ConnectionError("jddcia.local: Connection refused")
            return "SELECT FIRST 3 * FROM ARTICULO"

        orchestrator._try_model = spy_with_exception
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="dame artículos",
        )

        assert response == "SELECT FIRST 3 * FROM ARTICULO"
        assert len(tracker.internet_calls) == 0, (
            f"🚨 VIOLACIÓN: modelos de internet llamados: {tracker.internet_calls}"
        )
        for mid in tracker.called_model_ids:
            assert mid in LAN_MODEL_IDS, f"🚨 Se llamó a modelo no-LAN: {mid}"

    @pytest.mark.asyncio
    async def test_lan_only_empty_response_never_falls_to_internet(self, monkeypatch):
        """
        El modelo LAN devuelve respuesta vacía (string vacío o None).
        NUNCA se debe hacer fallback a internet.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()
        call_count = {"n": 0}

        async def spy_empty_then_ok(model_config, system_prompt, user_message,
                                    images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called_model_ids.append(mid)

            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: modelo internet '{mid}' llamado")

            call_count["n"] += 1
            if call_count["n"] <= 2:
                return ""  # Respuesta vacía
            return "SELECT FIRST 1 * FROM PROVEED"

        orchestrator._try_model = spy_empty_then_ok
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="dame proveedores",
        )

        assert response == "SELECT FIRST 1 * FROM PROVEED"
        assert len(tracker.internet_calls) == 0

    @pytest.mark.asyncio
    async def test_lan_only_many_failures_still_no_internet(self, monkeypatch):
        """
        El modelo LAN falla 10 veces consecutivas.
        En ningún momento se llama a internet.
        En el intento 11, responde.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()
        call_count = {"n": 0}

        async def spy_many_fails(model_config, system_prompt, user_message,
                                 images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called_model_ids.append(mid)

            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: modelo internet '{mid}' llamado")

            call_count["n"] += 1
            if call_count["n"] <= 10:
                return None
            return "SELECT COUNT(*) FROM ARTICULO"

        orchestrator._try_model = spy_many_fails
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="cuántos artículos hay",
        )

        assert response == "SELECT COUNT(*) FROM ARTICULO"
        assert len(tracker.internet_calls) == 0, (
            f"🚨 VIOLACIÓN tras 10 fallos: modelos internet llamados: {tracker.internet_calls}"
        )
        assert call_count["n"] == 11

    @pytest.mark.asyncio
    async def test_lan_only_backoff_increases_with_failures(self, monkeypatch):
        """
        Verificar que el backoff aumenta progresivamente:
          rondas 1-3  → sleep(2)
          rondas 4-6  → sleep(5)
          ronda 7+    → sleep(10)
        Y que NUNCA se llama a internet durante las esperas.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        round_count = {"n": 0}

        async def spy_fail_7_rounds(model_config, system_prompt, user_message,
                                    images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called_model_ids.append(mid)

            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: modelo internet '{mid}' llamado")

            if mid == LAN_MODEL_ID_MDNS:
                round_count["n"] += 1

            if round_count["n"] <= 7:
                return None
            return "OK"

        orchestrator._try_model = spy_fail_7_rounds

        response, _ = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="test backoff",
        )

        assert response == "OK"
        assert len(tracker.internet_calls) == 0

        # Verificar backoff: primeras 3 rondas → 2s, siguientes 3 → 5s, última → 10s
        assert sleep_calls[:3] == [2, 2, 2], f"Backoff rondas 1-3 incorrecto: {sleep_calls[:3]}"
        assert sleep_calls[3:6] == [5, 5, 5], f"Backoff rondas 4-6 incorrecto: {sleep_calls[3:6]}"
        assert sleep_calls[6] == 10, f"Backoff ronda 7+ incorrecto: {sleep_calls[6]}"

    @pytest.mark.asyncio
    async def test_lan_only_flag_false_allows_internet(self, monkeypatch):
        """
        CONTROL: Cuando ai_local_only=FALSE, el sistema SÍ puede usar modelos de internet.
        Este test verifica que el flag funciona correctamente en ambas direcciones.
        """
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: False)

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orchestrator = ModelFallbackOrchestrator()
        orchestrator.model_manager = MagicMock()
        orchestrator.model_manager.list_models.return_value = ALL_MODELS
        orchestrator.model_manager.report_result = MagicMock()

        internet_called = []

        async def spy_all_models(model_config, system_prompt, user_message,
                                 images=None, attempt=1):
            mid = model_config.get("id", "")
            if mid in INTERNET_MODEL_IDS:
                internet_called.append(mid)
                return "respuesta de internet"
            return None  # LAN falla

        orchestrator._try_model = spy_all_models
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="test",
        )

        assert response == "respuesta de internet"
        assert len(internet_called) > 0, "Con ai_local_only=False debería llamar a internet"

    @pytest.mark.asyncio
    async def test_lan_only_no_internet_models_in_prioritized_list(self, monkeypatch):
        """
        Verificar que cuando ai_local_only=true, la lista de modelos que se pasa
        a _execute_lan_only contiene SOLO modelos LAN (no modelos de internet).
        """
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: True)

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orchestrator = ModelFallbackOrchestrator()
        orchestrator.model_manager = MagicMock()
        orchestrator.model_manager.list_models.return_value = ALL_MODELS
        orchestrator.model_manager.report_result = MagicMock()

        captured_local_models = []

        async def spy_execute_lan_only(local_models, system_prompt, user_message,
                                       images=None, feedback_callback=None):
            captured_local_models.extend(local_models)
            return "OK", LAN_MODEL_ID_MDNS

        orchestrator._execute_lan_only = spy_execute_lan_only

        await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="test",
        )

        # Verificar que NINGÚN modelo de internet está en la lista LAN
        for model in captured_local_models:
            mid = model.get("id", "")
            assert mid not in INTERNET_MODEL_IDS, (
                f"🚨 Modelo de internet '{mid}' incluido en lista LAN"
            )
            assert mid in LAN_MODEL_IDS, (
                f"🚨 Modelo desconocido '{mid}' en lista LAN"
            )

    @pytest.mark.asyncio
    async def test_lan_only_feedback_callback_never_triggers_internet(self, monkeypatch):
        """
        Verificar que el feedback_callback se llama correctamente durante reintentos
        y que en ningún momento se llama a internet.
        """
        orchestrator = _build_orchestrator_lan_only(monkeypatch)
        tracker = InternetCallTracker()
        feedback_messages = []

        def feedback_cb(msg):
            feedback_messages.append(msg)

        call_count = {"n": 0}

        async def spy(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called_model_ids.append(mid)
            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: {mid}")
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return None
            return "SELECT 1 FROM RDB$DATABASE"

        orchestrator._try_model = spy
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, _ = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="test feedback",
            feedback_callback=feedback_cb,
        )

        assert response == "SELECT 1 FROM RDB$DATABASE"
        assert len(tracker.internet_calls) == 0
        assert len(feedback_messages) > 0, "Se esperaban mensajes de feedback durante reintentos"
        for msg in feedback_messages:
            assert "internet" not in msg.lower(), (
                f"Mensaje de feedback menciona internet: {msg}"
            )

    def test_local_model_ids_constant_from_centralized_source(self):
        """
        Verificar que LOCAL_MODEL_IDS en el orchestrator viene de la fuente
        centralizada (network_audit_constants.LocalModelIds) y contiene
        exactamente los IDs correctos sin ningún modelo de internet.
        """
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS

        # Debe contener los modelos LAN definidos en LocalModelIds
        assert LocalModelIds.QWEN3_MDNS in LOCAL_MODEL_IDS, (
            f"'{LocalModelIds.QWEN3_MDNS}' debe estar en LOCAL_MODEL_IDS"
        )
        assert LocalModelIds.QWEN3_IP in LOCAL_MODEL_IDS, (
            f"'{LocalModelIds.QWEN3_IP}' debe estar en LOCAL_MODEL_IDS"
        )

        # Debe ser exactamente igual a LocalModelIds.ALL (fuente única de verdad)
        assert LOCAL_MODEL_IDS == LocalModelIds.ALL, (
            f"LOCAL_MODEL_IDS ({LOCAL_MODEL_IDS}) debe ser igual a "
            f"LocalModelIds.ALL ({LocalModelIds.ALL})"
        )

        # Ningún modelo de internet debe estar en LOCAL_MODEL_IDS
        for internet_id in KnownInternetModelIds.IDS:
            assert internet_id not in LOCAL_MODEL_IDS, (
                f"🚨 Modelo de internet '{internet_id}' encontrado en LOCAL_MODEL_IDS"
            )

    def test_load_ai_local_only_returns_bool(self):
        """
        Test unitario: _load_ai_local_only() devuelve bool en todos los casos.
        """
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        result = orch_mod._load_ai_local_only()
        assert isinstance(result, bool), "_load_ai_local_only debe devolver bool"

    @pytest.mark.asyncio
    async def test_lan_only_config_true_by_default_in_production(self):
        """
        Verificar que el config.json de producción tiene ai_local_only=true.
        Este test falla si alguien cambia el config a false sin querer.
        ALERTA DE SEGURIDAD si falla.
        """
        config_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            "../../backend/modules/chat/config.json"
        ))

        if not os.path.exists(config_path):
            pytest.skip(f"config.json no encontrado en {config_path}")

        with open(config_path, 'r') as f:
            cfg = json.load(f)

        assert cfg.get("ai_local_only") is True, (
            f"🚨 ALERTA DE SEGURIDAD: config.json tiene ai_local_only={cfg.get('ai_local_only')}. "
            f"Debe ser TRUE para garantizar que los datos no salen a internet. "
            f"Si quieres usar modelos de internet, hazlo conscientemente cambiando este valor."
        )
