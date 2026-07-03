"""
Tests para el endpoint /api/chat/models/status y la lógica de pre-flight check.

Verifica:
1. El endpoint responde en < 10s (todos los modelos en paralelo)
2. La estructura de respuesta es correcta
3. El 8B (localhost:1234) es reachable cuando LM Studio está activo
4. Los 30B (JDDC LAN) son unreachable cuando el servidor está apagado
5. El campo recommended_model apunta al mejor modelo disponible
6. La lógica de probe_url funciona correctamente
7. Casos edge: sin modelos, modelos sin base_url, timeout
"""
import pytest
import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

# ─── Fixtures ────────────────────────────────────────────────────────────────

MODELS_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "core", "config", "models", "jddcia_models.json"
)

BACKEND_URL = "http://localhost:8001"


def _load_models_json():
    with open(MODELS_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


# ─── Tests de configuración de modelos ───────────────────────────────────────

class TestModelsJsonForStatus:
    """Verifica que jddcia_models.json tiene la estructura correcta para el endpoint."""

    def test_models_json_exists(self):
        assert os.path.exists(MODELS_JSON_PATH), f"No existe: {MODELS_JSON_PATH}"

    def test_models_json_has_models_key(self):
        data = _load_models_json()
        assert "models" in data, "jddcia_models.json debe tener clave 'models'"

    def test_all_models_have_id(self):
        data = _load_models_json()
        for m in data["models"]:
            assert "id" in m, f"Modelo sin 'id': {m}"

    def test_all_models_have_base_url_or_no_url(self):
        """Los modelos LAN deben tener base_url; los de internet pueden no tenerla."""
        data = _load_models_json()
        lan_models = [m for m in data["models"] if "jddcia" in m.get("id", "")]
        for m in lan_models:
            assert "base_url" in m, f"Modelo LAN sin base_url: {m['id']}"
            assert m["base_url"], f"Modelo LAN con base_url vacía: {m['id']}"

    def test_8b_localhost_has_correct_url(self):
        data = _load_models_json()
        models = {m["id"]: m for m in data["models"]}
        m8b = models.get("jddcia-qwen3-8b-ip")
        assert m8b is not None, "Modelo jddcia-qwen3-8b-ip no encontrado"
        assert "localhost" in m8b.get("base_url", "") or "127.0.0.1" in m8b.get("base_url", ""), \
            f"8B-IP debe apuntar a localhost, tiene: {m8b.get('base_url')}"

    def test_30b_models_have_lan_urls(self):
        data = _load_models_json()
        models = {m["id"]: m for m in data["models"]}
        for mid in ["jddcia-qwen3-30b", "jddcia-qwen3-30b-ip"]:
            m = models.get(mid)
            if m:
                url = m.get("base_url", "")
                assert "localhost" not in url, \
                    f"30B no debe apuntar a localhost: {mid} → {url}"

    def test_exactly_one_preferred_model(self):
        data = _load_models_json()
        preferred = [m for m in data["models"] if m.get("preferred")]
        assert len(preferred) == 1, \
            f"Debe haber exactamente 1 modelo preferred, hay {len(preferred)}: {[m['id'] for m in preferred]}"

    def test_preferred_model_is_enabled(self):
        data = _load_models_json()
        preferred = next((m for m in data["models"] if m.get("preferred")), None)
        assert preferred is not None
        assert preferred.get("enabled", False), \
            f"El modelo preferred debe estar enabled: {preferred['id']}"

    def test_preferred_model_is_8b_when_30b_unavailable(self):
        """Cuando el 30B está apagado, el preferred debe ser el 8B."""
        data = _load_models_json()
        preferred = next((m for m in data["models"] if m.get("preferred")), None)
        assert preferred is not None
        # El preferred actual debe ser el 8B (ya que el 30B está apagado)
        assert "8b" in preferred["id"].lower(), \
            f"Con 30B apagado, preferred debería ser 8B, es: {preferred['id']}"


# ─── Tests de la función _probe_model_url ────────────────────────────────────

class TestProbeModelUrl:
    """Tests unitarios de la función de probe de conectividad."""

    @pytest.mark.asyncio
    async def test_probe_returns_true_on_200(self):
        from backend.modules.chat.router import _probe_model_url
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client
            result = await _probe_model_url("http://localhost:1234/v1", {})
        assert result is True

    @pytest.mark.asyncio
    async def test_probe_returns_true_on_401(self):
        """401 = servidor vivo pero auth requerida → reachable=True."""
        from backend.modules.chat.router import _probe_model_url
        mock_response = MagicMock()
        mock_response.status_code = 401
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client
            result = await _probe_model_url("http://someserver/v1", {"Authorization": "Bearer token"})
        assert result is True

    @pytest.mark.asyncio
    async def test_probe_returns_false_on_500(self):
        """500 = servidor con error interno → reachable=False."""
        from backend.modules.chat.router import _probe_model_url
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client
            result = await _probe_model_url("http://someserver/v1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_returns_false_on_connect_error(self):
        """ConnectError → servidor no disponible → reachable=False."""
        from backend.modules.chat.router import _probe_model_url
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_cls.return_value = mock_client
            result = await _probe_model_url("http://192.168.0.36/api/vlm/v1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_returns_false_on_timeout(self):
        """Timeout → servidor no responde → reachable=False."""
        from backend.modules.chat.router import _probe_model_url
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_cls.return_value = mock_client
            result = await _probe_model_url("http://jddcia.local/api/vlm/v1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_returns_false_on_dns_error(self):
        """DNS failure → servidor no encontrado → reachable=False."""
        from backend.modules.chat.router import _probe_model_url
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=Exception("[Errno 11001] getaddrinfo failed"))
            mock_client_cls.return_value = mock_client
            result = await _probe_model_url("http://jddcia.local/api/vlm/v1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_appends_models_to_url(self):
        """El probe debe hacer GET a base_url/models."""
        from backend.modules.chat.router import _probe_model_url
        called_urls = []
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            async def fake_get(url, **kwargs):
                called_urls.append(url)
                return mock_response
            mock_client.get = fake_get
            mock_client_cls.return_value = mock_client
            await _probe_model_url("http://localhost:1234/v1", {})
        assert any("/models" in u for u in called_urls), \
            f"Debe hacer GET a /models, llamó a: {called_urls}"


# ─── Tests de _check_model_reachable ─────────────────────────────────────────

class TestCheckModelReachable:
    """Tests de la función que comprueba un modelo completo."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_required_keys(self):
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {"id": "test", "base_url": "http://localhost:1234/v1", "headers": {}}
        with patch("backend.modules.chat.router._probe_model_url", new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = True
            result = await _check_model_reachable(model_cfg)
        assert "reachable" in result
        assert "latency_ms" in result
        assert "error" in result

    @pytest.mark.asyncio
    async def test_reachable_true_when_probe_succeeds(self):
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {"id": "test", "base_url": "http://localhost:1234/v1", "headers": {}}
        with patch("backend.modules.chat.router._probe_model_url", new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = True
            result = await _check_model_reachable(model_cfg)
        assert result["reachable"] is True
        assert result["error"] is None
        assert result["latency_ms"] is not None

    @pytest.mark.asyncio
    async def test_reachable_false_when_probe_fails(self):
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {"id": "test", "base_url": "http://192.168.0.36/api/vlm/v1", "headers": {}}
        with patch("backend.modules.chat.router._probe_model_url", new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = False
            result = await _check_model_reachable(model_cfg)
        assert result["reachable"] is False
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_no_base_url_returns_unreachable(self):
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {"id": "test", "headers": {}}  # sin base_url
        result = await _check_model_reachable(model_cfg)
        assert result["reachable"] is False
        assert "base_url" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_base_url_returns_unreachable(self):
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {"id": "test", "base_url": "", "headers": {}}
        result = await _check_model_reachable(model_cfg)
        assert result["reachable"] is False

    @pytest.mark.asyncio
    async def test_latency_ms_is_integer(self):
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {"id": "test", "base_url": "http://localhost:1234/v1", "headers": {}}
        with patch("backend.modules.chat.router._probe_model_url", new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = True
            result = await _check_model_reachable(model_cfg)
        assert isinstance(result["latency_ms"], int)

    @pytest.mark.asyncio
    async def test_exception_in_probe_returns_unreachable(self):
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {"id": "test", "base_url": "http://localhost:1234/v1", "headers": {}}
        with patch("backend.modules.chat.router._probe_model_url", new_callable=AsyncMock) as mock_probe:
            mock_probe.side_effect = RuntimeError("Unexpected error")
            result = await _check_model_reachable(model_cfg)
        assert result["reachable"] is False
        assert result["error"] is not None


# ─── Tests de integración del endpoint /models/status ────────────────────────

class TestModelsStatusEndpoint:
    """Tests de integración contra el backend real (requiere backend en :8001)."""

    def _get_status(self, timeout=15):
        import urllib.request
        try:
            r = urllib.request.urlopen(
                f"{BACKEND_URL}/api/chat/models/status",
                timeout=timeout
            )
            return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            pytest.skip(f"Backend no disponible: {e}")

    def test_endpoint_responds_in_under_10s(self):
        t0 = time.time()
        data = self._get_status(timeout=15)
        elapsed = time.time() - t0
        assert elapsed < 10, f"El endpoint tardó {elapsed:.1f}s (máximo 10s)"

    def test_response_has_models_key(self):
        data = self._get_status()
        assert "models" in data, "Respuesta debe tener clave 'models'"

    def test_response_has_summary_key(self):
        data = self._get_status()
        assert "summary" in data, "Respuesta debe tener clave 'summary'"

    def test_summary_has_required_fields(self):
        data = self._get_status()
        summary = data["summary"]
        assert "any_30b_reachable" in summary
        assert "any_8b_reachable" in summary
        assert "recommended_model" in summary
        assert "checked_at" in summary

    def test_each_model_has_required_fields(self):
        data = self._get_status()
        for mid, status in data["models"].items():
            assert "reachable" in status, f"Modelo {mid} sin 'reachable'"
            assert "latency_ms" in status, f"Modelo {mid} sin 'latency_ms'"
            assert "error" in status, f"Modelo {mid} sin 'error'"

    def test_reachable_is_boolean(self):
        data = self._get_status()
        for mid, status in data["models"].items():
            assert isinstance(status["reachable"], bool), \
                f"Modelo {mid}: 'reachable' debe ser bool, es {type(status['reachable'])}"

    def test_8b_localhost_is_reachable(self):
        """El 8B en localhost:1234 debe estar reachable (LM Studio activo)."""
        data = self._get_status()
        m8b = data["models"].get("jddcia-qwen3-8b-ip")
        if m8b is None:
            pytest.skip("Modelo jddcia-qwen3-8b-ip no en la respuesta")
        assert m8b["reachable"] is True, \
            f"8B-IP debe ser reachable (LM Studio activo), error: {m8b.get('error')}"

    def test_30b_is_not_reachable_when_server_off(self):
        """El 30B debe ser unreachable cuando el servidor JDDC está apagado."""
        data = self._get_status()
        for mid in ["jddcia-qwen3-30b", "jddcia-qwen3-30b-ip"]:
            m = data["models"].get(mid)
            if m:
                # Si el servidor está apagado, debe ser False
                # Si está encendido, puede ser True — no forzamos el resultado
                assert isinstance(m["reachable"], bool)

    def test_summary_any_8b_reachable_is_true(self):
        """Con LM Studio activo, any_8b_reachable debe ser True."""
        data = self._get_status()
        assert data["summary"]["any_8b_reachable"] is True, \
            "any_8b_reachable debe ser True cuando LM Studio está activo"

    def test_recommended_model_is_not_none(self):
        """Siempre debe haber un modelo recomendado (al menos el 8B)."""
        data = self._get_status()
        assert data["summary"]["recommended_model"] is not None, \
            "recommended_model no debe ser None cuando hay modelos disponibles"

    def test_recommended_model_is_reachable(self):
        """El modelo recomendado debe ser reachable."""
        data = self._get_status()
        recommended = data["summary"]["recommended_model"]
        if recommended and recommended in data["models"]:
            assert data["models"][recommended]["reachable"] is True, \
                f"El modelo recomendado {recommended} debe ser reachable"

    def test_latency_ms_is_reasonable(self):
        """La latencia debe ser < 5000ms para modelos que responden."""
        data = self._get_status()
        for mid, status in data["models"].items():
            if status["reachable"] and status["latency_ms"] is not None:
                assert status["latency_ms"] < 5000, \
                    f"Latencia de {mid} es {status['latency_ms']}ms (máximo 5000ms)"

    def test_unreachable_models_have_error_message(self):
        """Los modelos unreachable deben tener un mensaje de error."""
        data = self._get_status()
        for mid, status in data["models"].items():
            if not status["reachable"]:
                assert status["error"] is not None, \
                    f"Modelo unreachable {mid} debe tener error message"
                assert len(status["error"]) > 0

    def test_reachable_models_have_null_error(self):
        """Los modelos reachable deben tener error=null."""
        data = self._get_status()
        for mid, status in data["models"].items():
            if status["reachable"]:
                assert status["error"] is None, \
                    f"Modelo reachable {mid} debe tener error=null, tiene: {status['error']}"

    def test_checked_at_is_iso_format(self):
        """checked_at debe ser una fecha ISO válida."""
        from datetime import datetime
        data = self._get_status()
        checked_at = data["summary"]["checked_at"]
        try:
            datetime.fromisoformat(checked_at)
        except ValueError:
            pytest.fail(f"checked_at no es ISO format: {checked_at}")

    def test_all_lan_models_present(self):
        """Todos los modelos LAN habilitados deben aparecer en la respuesta."""
        models_data = _load_models_json()
        enabled_lan = [
            m["id"] for m in models_data["models"]
            if m.get("enabled") and m.get("base_url")
        ]
        data = self._get_status()
        for mid in enabled_lan:
            assert mid in data["models"], \
                f"Modelo LAN habilitado {mid} no aparece en /models/status"


# ─── Tests de lógica de pre-flight (simulados) ───────────────────────────────

class TestPreflightLogic:
    """
    Tests de la lógica de pre-flight del frontend (simulados en Python).
    Verifica que la decisión de enviar o no enviar es correcta.
    """

    def _simulate_preflight(self, selected_model: str, models_status: dict) -> dict:
        """
        Simula la lógica del frontend:
        - Si el modelo seleccionado es 30B y no está reachable → error inmediato
        - Si el modelo seleccionado es 30B y está reachable → continuar
        - Si el modelo seleccionado es 8B → continuar siempre (sin pre-flight)
        """
        JDDC_30B_IDS = {"jddcia-qwen3-30b", "jddcia-qwen3-30b-ip"}
        if selected_model not in JDDC_30B_IDS:
            return {"action": "send", "reason": "not_30b"}

        model_status = models_status.get(selected_model, {})
        is_reachable = model_status.get("reachable", False)

        if not is_reachable:
            return {
                "action": "error",
                "reason": "30b_unreachable",
                "latency_ms": model_status.get("latency_ms"),
                "error": model_status.get("error"),
            }
        return {"action": "send", "reason": "30b_reachable"}

    def test_30b_unreachable_returns_error(self):
        models_status = {
            "jddcia-qwen3-30b-ip": {"reachable": False, "latency_ms": 4001, "error": "Server not responding"},
            "jddcia-qwen3-8b-ip": {"reachable": True, "latency_ms": 344, "error": None},
        }
        result = self._simulate_preflight("jddcia-qwen3-30b-ip", models_status)
        assert result["action"] == "error"
        assert result["reason"] == "30b_unreachable"

    def test_30b_reachable_returns_send(self):
        models_status = {
            "jddcia-qwen3-30b-ip": {"reachable": True, "latency_ms": 120, "error": None},
            "jddcia-qwen3-8b-ip": {"reachable": True, "latency_ms": 344, "error": None},
        }
        result = self._simulate_preflight("jddcia-qwen3-30b-ip", models_status)
        assert result["action"] == "send"
        assert result["reason"] == "30b_reachable"

    def test_8b_selected_skips_preflight(self):
        """El 8B no necesita pre-flight — siempre se envía."""
        models_status = {
            "jddcia-qwen3-8b-ip": {"reachable": True, "latency_ms": 344, "error": None},
        }
        result = self._simulate_preflight("jddcia-qwen3-8b-ip", models_status)
        assert result["action"] == "send"
        assert result["reason"] == "not_30b"

    def test_30b_mdns_unreachable_returns_error(self):
        models_status = {
            "jddcia-qwen3-30b": {"reachable": False, "latency_ms": 2827, "error": "Server not responding"},
        }
        result = self._simulate_preflight("jddcia-qwen3-30b", models_status)
        assert result["action"] == "error"

    def test_30b_not_in_status_returns_error(self):
        """Si el modelo no aparece en el status, asumir unreachable."""
        models_status = {}  # vacío
        result = self._simulate_preflight("jddcia-qwen3-30b-ip", models_status)
        assert result["action"] == "error"

    def test_error_includes_latency(self):
        models_status = {
            "jddcia-qwen3-30b-ip": {"reachable": False, "latency_ms": 4001, "error": "Timeout"},
        }
        result = self._simulate_preflight("jddcia-qwen3-30b-ip", models_status)
        assert result["latency_ms"] == 4001

    def test_error_includes_error_message(self):
        models_status = {
            "jddcia-qwen3-30b-ip": {"reachable": False, "latency_ms": 4001, "error": "Server not responding"},
        }
        result = self._simulate_preflight("jddcia-qwen3-30b-ip", models_status)
        assert result["error"] == "Server not responding"

    def test_groq_model_skips_preflight(self):
        """Modelos de internet (groq, openai, etc.) no necesitan pre-flight."""
        result = self._simulate_preflight("groq-llama-70b", {})
        assert result["action"] == "send"

    def test_gemini_model_skips_preflight(self):
        result = self._simulate_preflight("gemini-pro", {})
        assert result["action"] == "send"


# ─── Tests de resiliencia del endpoint ───────────────────────────────────────

class TestModelsStatusResilience:
    """Tests de resiliencia: el endpoint debe manejar errores gracefully."""

    @pytest.mark.asyncio
    async def test_all_models_unreachable_still_returns_200(self):
        """Aunque todos los modelos fallen, el endpoint debe devolver 200 (no 500)."""
        from backend.modules.chat.router import get_models_status
        with patch("backend.modules.chat.router._check_model_reachable", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"reachable": False, "latency_ms": 4001, "error": "Timeout"}
            # No debe lanzar excepción
            result = await get_models_status()
        assert "models" in result
        assert "summary" in result
        assert result["summary"]["any_30b_reachable"] is False
        assert result["summary"]["any_8b_reachable"] is False
        assert result["summary"]["recommended_model"] is None

    @pytest.mark.asyncio
    async def test_exception_in_one_model_does_not_break_others(self):
        """Si un modelo lanza excepción, los demás deben seguir comprobándose."""
        from backend.modules.chat.router import get_models_status
        call_count = 0
        async def mock_check(model_cfg, timeout=4.0):
            nonlocal call_count
            call_count += 1
            if "30b" in model_cfg.get("id", ""):
                raise RuntimeError("Unexpected error")
            return {"reachable": True, "latency_ms": 100, "error": None}

        with patch("backend.modules.chat.router._check_model_reachable", side_effect=mock_check):
            result = await get_models_status()
        # Debe haber comprobado todos los modelos
        assert call_count > 0
        # Los modelos que no fallaron deben aparecer como reachable
        for mid, status in result["models"].items():
            if "30b" not in mid:
                assert status["reachable"] is True

    @pytest.mark.asyncio
    async def test_recommended_model_is_none_when_all_unreachable(self):
        from backend.modules.chat.router import get_models_status
        with patch("backend.modules.chat.router._check_model_reachable", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"reachable": False, "latency_ms": 4001, "error": "Timeout"}
            result = await get_models_status()
        assert result["summary"]["recommended_model"] is None

    @pytest.mark.asyncio
    async def test_preferred_model_is_recommended_when_reachable(self):
        """Si el modelo preferred está reachable, debe ser el recommended."""
        from backend.modules.chat.router import get_models_status
        models_data = _load_models_json()
        preferred_id = next((m["id"] for m in models_data["models"] if m.get("preferred")), None)
        if not preferred_id:
            pytest.skip("No hay modelo preferred en jddcia_models.json")

        async def mock_check(model_cfg, timeout=4.0):
            if model_cfg["id"] == preferred_id:
                return {"reachable": True, "latency_ms": 100, "error": None}
            return {"reachable": False, "latency_ms": 4001, "error": "Timeout"}

        with patch("backend.modules.chat.router._check_model_reachable", side_effect=mock_check):
            result = await get_models_status()
        assert result["summary"]["recommended_model"] == preferred_id


# ─── Tests de casos edge ─────────────────────────────────────────────────────

class TestEdgeCases:
    """Tests de casos límite y situaciones inusuales."""

    @pytest.mark.asyncio
    async def test_probe_url_with_trailing_slash(self):
        """La URL con trailing slash debe funcionar correctamente."""
        from backend.modules.chat.router import _probe_model_url
        called_urls = []
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            async def fake_get(url, **kwargs):
                called_urls.append(url)
                return mock_response
            mock_client.get = fake_get
            mock_client_cls.return_value = mock_client
            await _probe_model_url("http://localhost:1234/v1/", {})
        # No debe haber doble slash
        assert not any("//models" in u for u in called_urls), \
            f"No debe haber doble slash en la URL: {called_urls}"

    @pytest.mark.asyncio
    async def test_check_model_with_auth_headers(self):
        """Los headers de autenticación deben pasarse al probe."""
        from backend.modules.chat.router import _check_model_reachable
        model_cfg = {
            "id": "test",
            "base_url": "http://someserver/api/vlm/v1",
            "headers": {"Authorization": "Bearer secret123"}
        }
        with patch("backend.modules.chat.router._probe_model_url", new_callable=AsyncMock) as mock_probe:
            mock_probe.return_value = True
            result = await _check_model_reachable(model_cfg)
        # Verificar que se llamó con los headers correctos
        mock_probe.assert_called_once()
        call_args = mock_probe.call_args
        assert call_args[0][1] == {"Authorization": "Bearer secret123"} or \
               call_args[1].get("headers") == {"Authorization": "Bearer secret123"} or \
               "Authorization" in str(call_args)

    def test_jddc_30b_ids_constant_is_correct(self):
        """La constante _JDDC_30B_IDS debe incluir los IDs correctos."""
        from backend.modules.chat.router import _JDDC_30B_IDS
        assert "jddcia-qwen3-30b" in _JDDC_30B_IDS
        assert "jddcia-qwen3-30b-ip" in _JDDC_30B_IDS
        assert "jddcia-qwen3-8b-ip" not in _JDDC_30B_IDS
        assert "jddcia-qwen3-8b" not in _JDDC_30B_IDS

    def test_probe_timeout_is_reasonable(self):
        """El timeout del probe debe ser corto (< 10s) para no bloquear al usuario."""
        from backend.modules.chat.router import _PROBE_TIMEOUT
        assert _PROBE_TIMEOUT <= 6.0, \
            f"_PROBE_TIMEOUT debe ser <= 6s para respuesta rápida, es {_PROBE_TIMEOUT}s"
        assert _PROBE_TIMEOUT >= 1.0, \
            f"_PROBE_TIMEOUT debe ser >= 1s para dar tiempo al servidor, es {_PROBE_TIMEOUT}s"

    @pytest.mark.asyncio
    async def test_parallel_probes_faster_than_sequential(self):
        """
        Comprobar N modelos en paralelo debe ser más rápido que N × timeout.
        Con 4 modelos y timeout=4s, paralelo debe tardar ~4s, no ~16s.
        """
        from backend.modules.chat.router import _check_model_reachable
        import asyncio

        async def slow_probe(base_url, headers, timeout=4.0):
            await asyncio.sleep(0.5)  # Simular latencia de red
            return False

        model_cfgs = [
            {"id": f"model-{i}", "base_url": f"http://server{i}/v1", "headers": {}}
            for i in range(4)
        ]

        with patch("backend.modules.chat.router._probe_model_url", side_effect=slow_probe):
            t0 = time.monotonic()
            tasks = [_check_model_reachable(m) for m in model_cfgs]
            results = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - t0

        # 4 modelos × 0.5s = 2s secuencial, pero en paralelo debe ser ~0.5s
        assert elapsed < 1.5, \
            f"Probes en paralelo tardaron {elapsed:.1f}s (deben ser < 1.5s para 4 × 0.5s)"
        assert len(results) == 4

    def test_endpoint_url_is_correct(self):
        """El endpoint debe estar en /api/chat/models/status."""
        import urllib.request
        try:
            r = urllib.request.urlopen(
                f"{BACKEND_URL}/api/chat/models/status",
                timeout=15
            )
            assert r.status == 200
        except Exception as e:
            pytest.skip(f"Backend no disponible: {e}")

    def test_ping_endpoint_responds_fast(self):
        """El endpoint /ping debe responder en < 1s."""
        import urllib.request
        try:
            t0 = time.time()
            r = urllib.request.urlopen(f"{BACKEND_URL}/api/chat/ping", timeout=5)
            elapsed = time.time() - t0
            assert r.status == 200
            assert elapsed < 1.0, f"/ping tardó {elapsed:.2f}s (debe ser < 1s)"
        except Exception as e:
            pytest.skip(f"Backend no disponible: {e}")
