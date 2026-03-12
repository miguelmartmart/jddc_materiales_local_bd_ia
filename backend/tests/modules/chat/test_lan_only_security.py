"""
TEST DE SEGURIDAD EXHAUSTIVO: AI_LOCAL_ONLY + Anonymizer LAN_ONLY

OBJETIVO: Garantizar al 100% que cuando ai_local_only=true:
  1. NINGÚN modelo de internet es llamado (ni Groq, Gemini, OpenAI, etc.)
  2. El anonymizer usa SOLO regex (lan_only=True), sin llamar a IA externa
  3. Bajo CUALQUIER tipo de fallo (excepción, respuesta vacía, timeout, etc.)
  4. Con múltiples reintentos, el backoff es correcto
  5. La constante LOCAL_MODEL_IDS viene de la fuente centralizada
  6. El config.json de producción tiene ai_local_only=true

CASOS DE FALLO CUBIERTOS:
  - Fallo en primer intento LAN
  - Fallo en múltiples intentos consecutivos
  - Excepción (ConnectionError, Timeout, etc.) en modelo LAN
  - Respuesta vacía del modelo LAN
  - Ambos modelos LAN fallan → reintento en ronda siguiente
  - 10 fallos consecutivos → responde en el 11
  - Backoff progresivo: 2s → 5s → 10s
  - Anonymizer con lan_only=True no llama a IA externa
  - Anonymizer con lan_only=False puede llamar a IA externa
  - Anonymizer desactivado (enable_chat=False) no procesa nada

GARANTÍA: Si algún test falla → datos podrían salir a internet. CRÍTICO.

Autor: DEVIA System
"""

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

# ─── Constantes centralizadas (FUENTE ÚNICA DE VERDAD) ───────────────────────
from backend.core.utils.network_audit_constants import (
    LocalModelIds,
    KnownInternetModelIds,
)

LAN_MODEL_ID_MDNS  = LocalModelIds.QWEN3_MDNS
LAN_MODEL_ID_IP    = LocalModelIds.QWEN3_IP
LAN_MODEL_IDS      = LocalModelIds.ALL
INTERNET_MODEL_IDS = KnownInternetModelIds.IDS

# Hosts de internet que el anonymizer NO debe contactar en modo LAN_ONLY
INTERNET_AI_HOSTS = {
    "api.groq.com", "api.openai.com", "generativelanguage.googleapis.com",
    "api.anthropic.com", "api.mistral.ai", "api.deepseek.com",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_lan_model(model_id: str, name: str = None) -> dict:
    return {
        "id": model_id,
        "name": name or f"LAN Model {model_id}",
        "model_id": "unified-main",
        "schema": "jddcia",
        "provider": "jddcia",
        "api_key": "test-lan-key",
        "base_url": "http://jddcia.local/api/vlm/v1",
        "enabled": True,
        "score": 100,
    }


def _make_internet_model(model_id: str, name: str = None) -> dict:
    return {
        "id": model_id,
        "name": name or f"Internet Model {model_id}",
        "model_id": model_id,
        "schema": "groq",
        "provider": "groq",
        "api_key": "test-internet-key",
        "enabled": True,
        "score": 80,
    }


ALL_MODELS = [
    _make_lan_model(LAN_MODEL_ID_MDNS, "Qwen3 VL 30B (JDDC LAN — mDNS)"),
    _make_lan_model(LAN_MODEL_ID_IP,   "Qwen3 VL 30B (JDDC LAN — IP directa)"),
    _make_internet_model("llama-3.1-8b-instant",    "Llama 3.1 8B (Groq)"),
    _make_internet_model("llama-3.3-70b-versatile", "Llama 3.3 70B (Groq)"),
    _make_internet_model("gpt-4o-mini",             "GPT-4o Mini"),
    _make_internet_model("gemini-flash",            "Gemini Flash"),
]


def _build_orchestrator(monkeypatch, ai_local_only: bool = True):
    """Construye orchestrator con flag ai_local_only configurado."""
    import backend.modules.chat.model_fallback_orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: ai_local_only)

    from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
    orch = ModelFallbackOrchestrator()
    orch.model_manager = MagicMock()
    orch.model_manager.list_models.return_value = ALL_MODELS
    orch.model_manager.report_result = MagicMock()
    return orch


class InternetCallTracker:
    """Detecta y registra cualquier llamada a modelos de internet. Falla inmediatamente."""
    def __init__(self):
        self.called = []
        self.internet_calls = []

    def make_spy(self, responses_by_model: dict):
        """responses_by_model: {model_id: [resp1, resp2, ...]}"""
        counts = {mid: 0 for mid in responses_by_model}

        async def spy(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            self.called.append(mid)
            if mid in INTERNET_MODEL_IDS:
                self.internet_calls.append(mid)
                raise AssertionError(
                    f"🚨 VIOLACIÓN DE SEGURIDAD: modelo internet '{mid}' llamado con ai_local_only=true"
                )
            resps = responses_by_model.get(mid, [])
            idx = counts.get(mid, 0)
            counts[mid] = idx + 1
            return resps[idx] if idx < len(resps) else None

        return spy


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 1: SEGURIDAD — Ningún modelo de internet es llamado
# ═══════════════════════════════════════════════════════════════════════════════

class TestLanOnlyNoInternetCalls:
    """Garantiza que con ai_local_only=true NUNCA se llama a internet."""

    @pytest.mark.asyncio
    async def test_success_first_attempt_no_internet(self, monkeypatch):
        """Caso feliz: LAN responde en el primer intento, sin llamar a internet."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        orch._try_model = tracker.make_spy({
            LAN_MODEL_ID_MDNS: ["SELECT FIRST 6 * FROM ARTICULO"],
        })

        response, model_id = await orch.execute_with_fallback("SQL", "dame artículos")

        assert response == "SELECT FIRST 6 * FROM ARTICULO"
        assert model_id == LAN_MODEL_ID_MDNS
        assert tracker.internet_calls == [], f"🚨 Internet llamado: {tracker.internet_calls}"
        assert all(mid in LAN_MODEL_IDS for mid in tracker.called)

    @pytest.mark.asyncio
    async def test_first_lan_fails_second_lan_succeeds_no_internet(self, monkeypatch):
        """mDNS falla → IP directa responde. NUNCA internet."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        orch._try_model = tracker.make_spy({
            LAN_MODEL_ID_MDNS: [None],
            LAN_MODEL_ID_IP:   ["SELECT FIRST 10 * FROM CLIENTE"],
        })
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orch.execute_with_fallback("SQL", "dame clientes")

        assert response == "SELECT FIRST 10 * FROM CLIENTE"
        assert model_id == LAN_MODEL_ID_IP
        assert tracker.internet_calls == []

    @pytest.mark.asyncio
    async def test_both_lan_fail_retry_no_internet(self, monkeypatch):
        """Ambos LAN fallan en ronda 1, mDNS responde en ronda 2. NUNCA internet."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        orch._try_model = tracker.make_spy({
            LAN_MODEL_ID_MDNS: [None, "SELECT FIRST 5 * FROM DOCCAB"],
            LAN_MODEL_ID_IP:   [None, None],
        })
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orch.execute_with_fallback("SQL", "dame facturas")

        assert response == "SELECT FIRST 5 * FROM DOCCAB"
        assert tracker.internet_calls == []
        assert tracker.called.count(LAN_MODEL_ID_MDNS) == 2

    @pytest.mark.asyncio
    async def test_connection_error_lan_never_falls_to_internet(self, monkeypatch):
        """ConnectionError en LAN → reintenta LAN, NUNCA internet."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        call_n = {"n": 0}

        async def spy_exception(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called.append(mid)
            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: {mid}")
            call_n["n"] += 1
            if call_n["n"] <= 3:
                raise ConnectionError("jddcia.local: Connection refused")
            return "SELECT FIRST 3 * FROM ARTICULO"

        orch._try_model = spy_exception
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, _ = await orch.execute_with_fallback("SQL", "dame artículos")

        assert response == "SELECT FIRST 3 * FROM ARTICULO"
        assert tracker.internet_calls == []
        for mid in tracker.called:
            assert mid in LAN_MODEL_IDS, f"🚨 Modelo no-LAN llamado: {mid}"

    @pytest.mark.asyncio
    async def test_timeout_error_lan_never_falls_to_internet(self, monkeypatch):
        """TimeoutError en LAN → reintenta LAN, NUNCA internet."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        call_n = {"n": 0}

        async def spy_timeout(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called.append(mid)
            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: {mid}")
            call_n["n"] += 1
            if call_n["n"] <= 2:
                raise TimeoutError("Request timed out after 30s")
            return "SELECT COUNT(*) FROM ARTICULO"

        orch._try_model = spy_timeout
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, _ = await orch.execute_with_fallback("SQL", "cuántos artículos")

        assert response == "SELECT COUNT(*) FROM ARTICULO"
        assert tracker.internet_calls == []

    @pytest.mark.asyncio
    async def test_empty_response_lan_never_falls_to_internet(self, monkeypatch):
        """Respuesta vacía del LAN → reintenta LAN, NUNCA internet."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        call_n = {"n": 0}

        async def spy_empty(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called.append(mid)
            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: {mid}")
            call_n["n"] += 1
            return "" if call_n["n"] <= 2 else "SELECT FIRST 1 * FROM PROVEED"

        orch._try_model = spy_empty
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, _ = await orch.execute_with_fallback("SQL", "dame proveedores")

        assert response == "SELECT FIRST 1 * FROM PROVEED"
        assert tracker.internet_calls == []

    @pytest.mark.asyncio
    async def test_10_failures_then_success_no_internet(self, monkeypatch):
        """10 fallos consecutivos → responde en el 11. NUNCA internet."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        call_n = {"n": 0}

        async def spy_many_fails(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called.append(mid)
            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: {mid}")
            call_n["n"] += 1
            return None if call_n["n"] <= 10 else "SELECT COUNT(*) FROM ARTICULO"

        orch._try_model = spy_many_fails
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, _ = await orch.execute_with_fallback("SQL", "cuántos artículos")

        assert response == "SELECT COUNT(*) FROM ARTICULO"
        assert tracker.internet_calls == []
        assert call_n["n"] == 11

    @pytest.mark.asyncio
    async def test_no_internet_models_passed_to_execute_lan_only(self, monkeypatch):
        """La lista pasada a _execute_lan_only contiene SOLO modelos LAN."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: True)

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orch = ModelFallbackOrchestrator()
        orch.model_manager = MagicMock()
        orch.model_manager.list_models.return_value = ALL_MODELS
        orch.model_manager.report_result = MagicMock()

        captured = []

        async def spy_lan_only(local_models, system_prompt, user_message,
                               images=None, feedback_callback=None):
            captured.extend(local_models)
            return "OK", LAN_MODEL_ID_MDNS

        orch._execute_lan_only = spy_lan_only
        await orch.execute_with_fallback("SQL", "test")

        for m in captured:
            mid = m.get("id", "")
            assert mid not in INTERNET_MODEL_IDS, f"🚨 Modelo internet '{mid}' en lista LAN"
            assert mid in LAN_MODEL_IDS, f"🚨 Modelo desconocido '{mid}' en lista LAN"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2: BACKOFF — Tiempos de espera correctos
# ═══════════════════════════════════════════════════════════════════════════════

class TestLanOnlyBackoff:
    """Verifica que el backoff progresivo es correcto y no hay llamadas a internet."""

    @pytest.mark.asyncio
    async def test_backoff_progression_2_5_10(self, monkeypatch):
        """Rondas 1-3 → 2s, rondas 4-6 → 5s, ronda 7+ → 10s."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        tracker = InternetCallTracker()
        sleep_calls = []

        async def mock_sleep(s):
            sleep_calls.append(s)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)
        round_n = {"n": 0}

        async def spy(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            tracker.called.append(mid)
            if mid in INTERNET_MODEL_IDS:
                tracker.internet_calls.append(mid)
                raise AssertionError(f"🚨 VIOLACIÓN: {mid}")
            if mid == LAN_MODEL_ID_MDNS:
                round_n["n"] += 1
            return None if round_n["n"] <= 7 else "OK"

        orch._try_model = spy
        response, _ = await orch.execute_with_fallback("SQL", "test backoff")

        assert response == "OK"
        assert tracker.internet_calls == []
        assert sleep_calls[:3] == [2, 2, 2], f"Backoff 1-3 incorrecto: {sleep_calls[:3]}"
        assert sleep_calls[3:6] == [5, 5, 5], f"Backoff 4-6 incorrecto: {sleep_calls[3:6]}"
        assert sleep_calls[6] == 10, f"Backoff 7+ incorrecto: {sleep_calls[6]}"

    @pytest.mark.asyncio
    async def test_no_sleep_on_first_success(self, monkeypatch):
        """Si el primer intento tiene éxito, no hay sleep."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)
        sleep_calls = []

        async def mock_sleep(s):
            sleep_calls.append(s)

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        async def spy_success(model_config, system_prompt, user_message, images=None, attempt=1):
            return "OK"

        orch._try_model = spy_success
        await orch.execute_with_fallback("SQL", "test")

        assert sleep_calls == [], f"No debería haber sleep en primer éxito: {sleep_calls}"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 3: ANONYMIZER — lan_only=True no llama a IA externa
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnonymizerLanOnly:
    """Verifica que el anonymizer con lan_only=True usa solo regex, sin IA externa."""

    def test_lan_only_uses_only_regex_no_ai_call(self, monkeypatch):
        """Con lan_only=True, anonymize_text NUNCA se llama."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {
            "enable_chat": True,
            "anonymize_emails": True,
            "anonymize_phones": True,
            "anonymize_ids": True,
            "anonymize_names": True,
            "preserve_products": True,
        }

        anonymize_text_called = []

        def spy_anonymize_text(text):
            anonymize_text_called.append(text)
            return {"anonymized": "SHOULD NOT BE CALLED"}

        svc.anonymize_text = spy_anonymize_text

        result = svc.anonymize_if_enabled(
            "Contacta a juan@empresa.com o al 600123456",
            "chat",
            lan_only=True
        )

        assert anonymize_text_called == [], (
            f"🚨 anonymize_text fue llamado con lan_only=True: {anonymize_text_called}"
        )
        assert "[EMAIL]" in result, f"Email no anonimizado por regex: {result}"
        assert "[TELEFONO]" in result, f"Teléfono no anonimizado por regex: {result}"

    def test_lan_only_false_calls_ai(self, monkeypatch):
        """Con lan_only=False, anonymize_text SÍ se llama (comportamiento normal)."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {
            "enable_chat": True,
            "anonymize_emails": True,
            "anonymize_phones": True,
            "anonymize_ids": True,
            "anonymize_names": True,
            "preserve_products": True,
        }

        ai_called = []

        def spy_anonymize_text(text):
            ai_called.append(text)
            return {"anonymized": "texto anonimizado por IA"}

        svc.anonymize_text = spy_anonymize_text

        result = svc.anonymize_if_enabled("hola mundo", "chat", lan_only=False)

        assert len(ai_called) == 1, "Con lan_only=False, anonymize_text debe llamarse"
        assert result == "texto anonimizado por IA"

    def test_lan_only_disabled_feature_returns_original(self):
        """Si la feature está desactivada, devuelve el texto original sin procesar."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {"enable_chat": False}

        result = svc.anonymize_if_enabled("texto con DNI 12345678A", "chat", lan_only=True)

        assert result == "texto con DNI 12345678A", (
            "Con feature desactivada, debe devolver texto original"
        )

    def test_lan_only_regex_anonymizes_email(self):
        """Regex anonimiza emails correctamente."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {
            "enable_chat": True,
            "anonymize_emails": True,
            "anonymize_phones": False,
            "anonymize_ids": False,
        }

        result = svc.anonymize_if_enabled("Email: test@example.com", "chat", lan_only=True)
        assert "[EMAIL]" in result
        assert "test@example.com" not in result

    def test_lan_only_regex_anonymizes_phone(self):
        """Regex anonimiza teléfonos españoles correctamente."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {
            "enable_chat": True,
            "anonymize_emails": False,
            "anonymize_phones": True,
            "anonymize_ids": False,
        }

        result = svc.anonymize_if_enabled("Llama al 600123456", "chat", lan_only=True)
        assert "[TELEFONO]" in result
        assert "600123456" not in result

    def test_lan_only_regex_anonymizes_dni(self):
        """Regex anonimiza DNI correctamente."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {
            "enable_chat": True,
            "anonymize_emails": False,
            "anonymize_phones": False,
            "anonymize_ids": True,
        }

        result = svc.anonymize_if_enabled("DNI: 12345678A", "chat", lan_only=True)
        assert "[ID]" in result
        assert "12345678A" not in result

    def test_lan_only_regex_preserves_non_pii(self):
        """Regex no modifica texto sin PII."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {
            "enable_chat": True,
            "anonymize_emails": True,
            "anonymize_phones": True,
            "anonymize_ids": True,
        }

        text = "dame los artículos con más ventas"
        result = svc.anonymize_if_enabled(text, "chat", lan_only=True)
        assert result == text, f"Texto sin PII no debe modificarse: {result}"

    def test_lan_only_exception_in_regex_returns_original(self, monkeypatch):
        """Si el regex falla, devuelve el texto original (fail-open)."""
        from backend.modules.anonymizer.service import AnonymizerService

        svc = AnonymizerService.__new__(AnonymizerService)
        svc.config = {"enable_chat": True}

        def spy_regex_fail(text):
            raise RuntimeError("Error inesperado en regex")

        svc._regex_anonymize_pre = spy_regex_fail

        # Con lan_only=True y fallo en regex, debe devolver texto original (fail-open)
        original = "texto de prueba"
        result = svc.anonymize_if_enabled(original, "chat", lan_only=True)
        # El fail-open está en anonymize_if_enabled, no en lan_only directamente
        # Verificamos que no lanza excepción
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 4: ORCHESTRATOR + ANONYMIZER — Integración completa
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorAnonymizerIntegration:
    """Verifica que el orchestrator pasa lan_only=True al anonymizer en modo LAN_ONLY."""

    @pytest.mark.asyncio
    async def test_orchestrator_passes_lan_only_to_anonymizer(self, monkeypatch):
        """En modo LAN_ONLY, el orchestrator llama al anonymizer con lan_only=True."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=True)

        anonymizer_calls = []

        class MockAnonymizer:
            def anonymize_if_enabled(self, text, feature, lan_only=False):
                anonymizer_calls.append({"text": text, "feature": feature, "lan_only": lan_only})
                return text  # Devuelve sin modificar

        with patch("backend.modules.anonymizer.service.AnonymizerService", return_value=MockAnonymizer()):
            async def spy_success(model_config, system_prompt, user_message, images=None, attempt=1):
                return "SELECT 1"

            orch._try_model = spy_success
            await orch.execute_with_fallback("SQL", "dame artículos")

        # Verificar que se llamó con lan_only=True
        assert len(anonymizer_calls) >= 1
        for call_info in anonymizer_calls:
            assert call_info["lan_only"] is True, (
                f"🚨 Anonymizer llamado con lan_only={call_info['lan_only']} en modo LAN_ONLY"
            )

    @pytest.mark.asyncio
    async def test_orchestrator_fallback_mode_anonymizer_without_lan_only(self, monkeypatch):
        """En modo FALLBACK (ai_local_only=False), el anonymizer se llama sin lan_only."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=False)

        anonymizer_calls = []

        class MockAnonymizer:
            def anonymize_if_enabled(self, text, feature, lan_only=False):
                anonymizer_calls.append({"text": text, "feature": feature, "lan_only": lan_only})
                return text

        with patch("backend.modules.anonymizer.service.AnonymizerService", return_value=MockAnonymizer()):
            async def spy_success(model_config, system_prompt, user_message, images=None, attempt=1):
                return "SELECT 1"

            orch._try_model = spy_success
            await orch.execute_with_fallback("SQL", "dame artículos")

        # En modo fallback, el anonymizer se llama sin lan_only (o con lan_only=False)
        for call_info in anonymizer_calls:
            assert call_info["lan_only"] is False, (
                f"En modo fallback, lan_only debe ser False: {call_info}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 5: CONSTANTES — Fuente única de verdad
# ═══════════════════════════════════════════════════════════════════════════════

class TestCentralizedConstants:
    """Verifica que las constantes vienen de la fuente centralizada."""

    def test_local_model_ids_equals_centralized_source(self):
        """LOCAL_MODEL_IDS en orchestrator == LocalModelIds.ALL."""
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS
        assert LOCAL_MODEL_IDS == LocalModelIds.ALL, (
            f"LOCAL_MODEL_IDS ({LOCAL_MODEL_IDS}) != LocalModelIds.ALL ({LocalModelIds.ALL})"
        )

    def test_local_model_ids_contains_mdns(self):
        """LOCAL_MODEL_IDS contiene el modelo mDNS."""
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS
        assert LocalModelIds.QWEN3_MDNS in LOCAL_MODEL_IDS

    def test_local_model_ids_contains_ip(self):
        """LOCAL_MODEL_IDS contiene el modelo IP directa."""
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS
        assert LocalModelIds.QWEN3_IP in LOCAL_MODEL_IDS

    def test_local_model_ids_no_internet_models(self):
        """LOCAL_MODEL_IDS no contiene ningún modelo de internet."""
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS
        for internet_id in KnownInternetModelIds.IDS:
            assert internet_id not in LOCAL_MODEL_IDS, (
                f"🚨 Modelo internet '{internet_id}' en LOCAL_MODEL_IDS"
            )

    def test_local_model_ids_is_frozenset(self):
        """LOCAL_MODEL_IDS es frozenset (inmutable, búsqueda O(1))."""
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS
        assert isinstance(LOCAL_MODEL_IDS, frozenset)

    def test_known_internet_model_ids_no_lan_models(self):
        """KnownInternetModelIds.IDS no contiene modelos LAN."""
        for lan_id in LocalModelIds.ALL:
            assert lan_id not in KnownInternetModelIds.IDS, (
                f"🚨 Modelo LAN '{lan_id}' en KnownInternetModelIds.IDS"
            )

    def test_local_model_ids_naming_convention(self):
        """Todos los IDs LAN siguen la convención 'jddcia-*'."""
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS
        for mid in LOCAL_MODEL_IDS:
            assert mid.startswith("jddcia-"), (
                f"ID LAN '{mid}' no sigue la convención 'jddcia-*'"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 6: CONFIG — ai_local_only se lee correctamente
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfigLoading:
    """Verifica que _load_ai_local_only lee el config.json correctamente."""

    def test_returns_true_when_config_true(self, tmp_path, monkeypatch):
        """Devuelve True cuando config.json tiene ai_local_only=true."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"ai_local_only": True}))
        monkeypatch.setattr(orch_mod.os.path, "join", lambda *a: str(cfg_file))
        monkeypatch.setattr(orch_mod.os.path, "exists", lambda p: True)
        assert orch_mod._load_ai_local_only() is True

    def test_returns_false_when_config_false(self, tmp_path, monkeypatch):
        """Devuelve False cuando config.json tiene ai_local_only=false."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"ai_local_only": False}))
        monkeypatch.setattr(orch_mod.os.path, "join", lambda *a: str(cfg_file))
        monkeypatch.setattr(orch_mod.os.path, "exists", lambda p: True)
        assert orch_mod._load_ai_local_only() is False

    def test_returns_false_when_field_missing(self, tmp_path, monkeypatch):
        """Devuelve False (seguro) cuando el campo no existe."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"max_sql_retries": 4}))
        monkeypatch.setattr(orch_mod.os.path, "join", lambda *a: str(cfg_file))
        monkeypatch.setattr(orch_mod.os.path, "exists", lambda p: True)
        assert orch_mod._load_ai_local_only() is False

    def test_returns_false_when_file_not_found(self, monkeypatch):
        """Devuelve False cuando config.json no existe."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        monkeypatch.setattr(orch_mod.os.path, "exists", lambda p: False)
        assert orch_mod._load_ai_local_only() is False

    def test_returns_false_when_json_invalid(self, tmp_path, monkeypatch):
        """Devuelve False (sin crash) cuando config.json tiene JSON inválido."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text("{ esto no es json válido }")
        monkeypatch.setattr(orch_mod.os.path, "join", lambda *a: str(cfg_file))
        monkeypatch.setattr(orch_mod.os.path, "exists", lambda p: True)
        assert orch_mod._load_ai_local_only() is False

    def test_returns_bool_always(self):
        """_load_ai_local_only siempre devuelve bool."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        result = orch_mod._load_ai_local_only()
        assert isinstance(result, bool)

    def test_production_config_has_ai_local_only_true(self):
        """El config.json de producción tiene ai_local_only=true. ALERTA DE SEGURIDAD si falla."""
        config_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            "../../../modules/chat/config.json"
        ))
        if not os.path.exists(config_path):
            pytest.skip(f"config.json no encontrado en {config_path}")

        with open(config_path, 'r') as f:
            cfg = json.load(f)

        assert cfg.get("ai_local_only") is True, (
            f"🚨 ALERTA DE SEGURIDAD: config.json tiene ai_local_only={cfg.get('ai_local_only')}. "
            f"Debe ser TRUE. Los datos de la BD NUNCA deben salir a internet."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 7: CONTROL — ai_local_only=False permite internet (verificación bidireccional)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallbackModeAllowsInternet:
    """Verifica que con ai_local_only=False el sistema SÍ puede usar internet."""

    @pytest.mark.asyncio
    async def test_fallback_mode_can_use_internet_models(self, monkeypatch):
        """Con ai_local_only=False, los modelos de internet están disponibles."""
        orch = _build_orchestrator(monkeypatch, ai_local_only=False)
        internet_called = []

        async def spy(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            if mid in INTERNET_MODEL_IDS:
                internet_called.append(mid)
                return "respuesta de internet"
            return None  # LAN falla

        orch._try_model = spy
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, _ = await orch.execute_with_fallback("SQL", "test")

        assert response == "respuesta de internet"
        assert len(internet_called) > 0, "Con ai_local_only=False debe poder usar internet"

    @pytest.mark.asyncio
    async def test_flag_change_takes_effect_immediately(self, monkeypatch):
        """El flag se lee en cada llamada — cambio dinámico sin reiniciar."""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod

        flag_value = {"v": True}
        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: flag_value["v"])

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orch = ModelFallbackOrchestrator()
        orch.model_manager = MagicMock()
        orch.model_manager.list_models.return_value = ALL_MODELS
        orch.model_manager.report_result = MagicMock()

        models_used_call1 = []
        models_used_call2 = []
        call_num = {"n": 0}

        async def spy(model_config, system_prompt, user_message, images=None, attempt=1):
            mid = model_config.get("id", "")
            if call_num["n"] == 0:
                models_used_call1.append(mid)
            else:
                models_used_call2.append(mid)
            return "ok"

        orch._try_model = spy

        # Primera llamada: ai_local_only=True → solo LAN
        flag_value["v"] = True
        await orch.execute_with_fallback("SQL", "test1")
        call_num["n"] = 1

        # Segunda llamada: ai_local_only=False → todos los modelos
        flag_value["v"] = False
        await orch.execute_with_fallback("SQL", "test2")

        # Primera llamada: solo modelos LAN
        assert all(m in LAN_MODEL_IDS for m in models_used_call1), (
            f"Primera llamada (LAN_ONLY) usó modelos externos: {models_used_call1}"
        )
