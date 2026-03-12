"""
TEST DE RESILIENCIA: jddcia_provider.py v1.3 + model_fallback_orchestrator.py v1.2

Cubre los bugs corregidos en PENDIENTE-FACT2:

1. _probe_url: NO acepta 404 como válido (evita cachear el router)
2. _READ_TIMEOUT: se lee de config.json (lan_read_timeout_s=60)
3. _save_ip_cache: solo se llama cuando _probe_url devuelve True (200/401)
4. generate_text: loguea type(e).__name__ + mensaje completo
5. _get_working_base_url: limpia cache automáticamente si IP cacheada falla
6. _load_lan_max_retries: lee lan_max_retries de config.json
7. _execute_lan_only: respeta max_retries y devuelve (None, None) al agotarlos

Autor: DEVIA System
"""

import asyncio
import json
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 1: _probe_url — rechaza 404, acepta solo 200/401
# ═══════════════════════════════════════════════════════════════════════════════

class TestProbeUrlRejects404:
    """
    _probe_url debe rechazar 404 para evitar cachear el router.
    Bug anterior: aceptaba 404 → router (192.168.0.1) se cacheaba como gateway.
    """

    @pytest.mark.asyncio
    async def test_probe_url_accepts_200(self):
        """200 OK → gateway válido → True"""
        from backend.drivers.ai.jddcia_provider import _probe_url

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _probe_url(mock_client, "http://jddcia.local/api/vlm/v1", "Basic test")
        assert result is True, "200 debe ser aceptado como gateway válido"

    @pytest.mark.asyncio
    async def test_probe_url_accepts_401(self):
        """401 Unauthorized → servidor existe, auth incorrecta → True"""
        from backend.drivers.ai.jddcia_provider import _probe_url

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _probe_url(mock_client, "http://jddcia.local/api/vlm/v1", "Basic test")
        assert result is True, "401 debe ser aceptado (servidor existe, auth incorrecta)"

    @pytest.mark.asyncio
    async def test_probe_url_rejects_404(self):
        """
        404 → puede ser el ROUTER devolviendo HTML → False
        Bug corregido: antes aceptaba 404, causando que 192.168.0.1 (router)
        se cacheara como gateway válido.
        """
        from backend.drivers.ai.jddcia_provider import _probe_url

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _probe_url(mock_client, "http://192.168.0.1/api/vlm/v1", "Basic test")
        assert result is False, (
            "404 NO debe ser aceptado — puede ser el router devolviendo HTML. "
            "Bug anterior: aceptar 404 cacheaba el router como gateway."
        )

    @pytest.mark.asyncio
    async def test_probe_url_rejects_500(self):
        """500 → error del servidor → False"""
        from backend.drivers.ai.jddcia_provider import _probe_url

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _probe_url(mock_client, "http://192.168.0.36/api/vlm/v1", "Basic test")
        assert result is False, "500 no debe ser aceptado"

    @pytest.mark.asyncio
    async def test_probe_url_rejects_302_redirect(self):
        """302 Redirect → no es el gateway → False"""
        from backend.drivers.ai.jddcia_provider import _probe_url

        mock_response = MagicMock()
        mock_response.status_code = 302

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _probe_url(mock_client, "http://192.168.0.1/api/vlm/v1", "Basic test")
        assert result is False, "302 no debe ser aceptado"

    @pytest.mark.asyncio
    async def test_probe_url_returns_false_on_connection_error(self):
        """ConnectError → host no existe → False (no lanza excepción)"""
        import httpx
        from backend.drivers.ai.jddcia_provider import _probe_url

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await _probe_url(mock_client, "http://192.168.0.36/api/vlm/v1", "Basic test")
        assert result is False, "ConnectError debe devolver False, no lanzar excepción"

    @pytest.mark.asyncio
    async def test_probe_url_returns_false_on_timeout(self):
        """ReadTimeout → host no responde → False (no lanza excepción)"""
        import httpx
        from backend.drivers.ai.jddcia_provider import _probe_url

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ReadTimeout("Read timeout"))

        result = await _probe_url(mock_client, "http://192.168.0.36/api/vlm/v1", "Basic test")
        assert result is False, "ReadTimeout debe devolver False, no lanzar excepción"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2: _load_read_timeout — lee de config.json
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadTimeoutFromConfig:
    """
    _READ_TIMEOUT debe leerse de config.json (lan_read_timeout_s).
    Bug anterior: hardcodeado a 8s, insuficiente para Qwen3 30B (necesita 30-60s).
    """

    def test_load_read_timeout_reads_from_config(self, tmp_path):
        """Lee lan_read_timeout_s=60 de config.json"""
        config = {"lan_read_timeout_s": 60, "ai_local_only": True}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        from backend.drivers.ai import jddcia_provider
        original_path = jddcia_provider._CONFIG_JSON_PATH
        try:
            jddcia_provider._CONFIG_JSON_PATH = str(config_file)
            timeout = jddcia_provider._load_read_timeout()
            assert timeout == 60.0, f"Esperado 60.0, obtenido {timeout}"
        finally:
            jddcia_provider._CONFIG_JSON_PATH = original_path

    def test_load_read_timeout_uses_default_if_config_missing(self, tmp_path):
        """Si config.json no existe, usa _READ_TIMEOUT_DEFAULT (60s)"""
        from backend.drivers.ai import jddcia_provider
        original_path = jddcia_provider._CONFIG_JSON_PATH
        try:
            jddcia_provider._CONFIG_JSON_PATH = str(tmp_path / "nonexistent.json")
            timeout = jddcia_provider._load_read_timeout()
            assert timeout == jddcia_provider._READ_TIMEOUT_DEFAULT, (
                f"Esperado default {jddcia_provider._READ_TIMEOUT_DEFAULT}, obtenido {timeout}"
            )
        finally:
            jddcia_provider._CONFIG_JSON_PATH = original_path

    def test_load_read_timeout_uses_default_if_key_missing(self, tmp_path):
        """Si lan_read_timeout_s no está en config.json, usa default"""
        config = {"ai_local_only": True}  # Sin lan_read_timeout_s
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        from backend.drivers.ai import jddcia_provider
        original_path = jddcia_provider._CONFIG_JSON_PATH
        try:
            jddcia_provider._CONFIG_JSON_PATH = str(config_file)
            timeout = jddcia_provider._load_read_timeout()
            assert timeout == jddcia_provider._READ_TIMEOUT_DEFAULT
        finally:
            jddcia_provider._CONFIG_JSON_PATH = original_path

    def test_load_read_timeout_custom_value(self, tmp_path):
        """Valor personalizado (30s) se lee correctamente"""
        config = {"lan_read_timeout_s": 30}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        from backend.drivers.ai import jddcia_provider
        original_path = jddcia_provider._CONFIG_JSON_PATH
        try:
            jddcia_provider._CONFIG_JSON_PATH = str(config_file)
            timeout = jddcia_provider._load_read_timeout()
            assert timeout == 30.0
        finally:
            jddcia_provider._CONFIG_JSON_PATH = original_path

    def test_default_timeout_is_sufficient_for_qwen3(self):
        """
        El timeout por defecto debe ser >= 30s para Qwen3 30B.
        Qwen3 30B puede tardar 30-60s en la primera inferencia.
        """
        from backend.drivers.ai.jddcia_provider import _READ_TIMEOUT_DEFAULT
        assert _READ_TIMEOUT_DEFAULT >= 30.0, (
            f"_READ_TIMEOUT_DEFAULT={_READ_TIMEOUT_DEFAULT}s es insuficiente para Qwen3 30B. "
            f"Debe ser >= 30s."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 3: Cache de IP — no cachear 404, limpiar cache corrupta
# ═══════════════════════════════════════════════════════════════════════════════

class TestIpCacheAntiRouter:
    """
    La cache de IP no debe guardar IPs que devuelven 404 (router).
    Si la IP cacheada ya no funciona, se debe limpiar automáticamente.
    """

    def test_save_ip_cache_writes_file(self, tmp_path):
        """_save_ip_cache escribe el archivo correctamente"""
        from backend.drivers.ai import jddcia_provider
        original_cache = jddcia_provider._IP_CACHE_FILE
        cache_file = str(tmp_path / "test_cache.json")
        try:
            jddcia_provider._IP_CACHE_FILE = cache_file
            jddcia_provider._save_ip_cache("192.168.0.38", 80, "http://192.168.0.38/api/vlm/v1")
            assert os.path.exists(cache_file)
            with open(cache_file) as f:
                data = json.load(f)
            assert data["ip"] == "192.168.0.38"
            assert data["port"] == 80
            assert data["base_url"] == "http://192.168.0.38/api/vlm/v1"
        finally:
            jddcia_provider._IP_CACHE_FILE = original_cache

    def test_clear_ip_cache_removes_file(self, tmp_path):
        """_clear_ip_cache elimina el archivo de cache"""
        from backend.drivers.ai import jddcia_provider
        original_cache = jddcia_provider._IP_CACHE_FILE
        cache_file = str(tmp_path / "test_cache.json")
        try:
            jddcia_provider._IP_CACHE_FILE = cache_file
            # Crear el archivo primero
            with open(cache_file, 'w') as f:
                json.dump({"ip": "192.168.0.1", "port": 80, "base_url": "http://192.168.0.1/api/vlm/v1"}, f)
            assert os.path.exists(cache_file)
            # Limpiar
            jddcia_provider._clear_ip_cache()
            assert not os.path.exists(cache_file), "Cache debe eliminarse tras _clear_ip_cache()"
        finally:
            jddcia_provider._IP_CACHE_FILE = original_cache

    def test_clear_ip_cache_safe_if_no_file(self, tmp_path):
        """_clear_ip_cache no lanza excepción si el archivo no existe"""
        from backend.drivers.ai import jddcia_provider
        original_cache = jddcia_provider._IP_CACHE_FILE
        try:
            jddcia_provider._IP_CACHE_FILE = str(tmp_path / "nonexistent.json")
            # No debe lanzar excepción
            jddcia_provider._clear_ip_cache()
        finally:
            jddcia_provider._IP_CACHE_FILE = original_cache

    @pytest.mark.asyncio
    async def test_get_working_base_url_clears_cache_when_cached_ip_fails(self, tmp_path):
        """
        Si la IP cacheada ya no responde (probe falla), se limpia la cache
        y se inicia autodescubrimiento.
        Bug anterior: la cache corrupta (router) se quedaba indefinidamente.
        """
        import httpx
        from backend.drivers.ai import jddcia_provider

        # Crear cache con IP del router (que devuelve 404)
        cache_file = str(tmp_path / "test_cache.json")
        with open(cache_file, 'w') as f:
            json.dump({
                "ip": "192.168.0.1",
                "port": 80,
                "base_url": "http://192.168.0.1/api/vlm/v1"
            }, f)

        original_cache = jddcia_provider._IP_CACHE_FILE
        jddcia_provider._IP_CACHE_FILE = cache_file

        try:
            provider = jddcia_provider.JDDCIAProvider()
            provider._configured_base_url = "http://jddcia.local/api/vlm/v1"
            provider.api_key = "test-key"

            probe_calls = []

            async def mock_probe(client, url, auth_header):
                probe_calls.append(url)
                # Todas las URLs fallan (incluyendo la cacheada del router)
                return False

            discover_called = []

            async def mock_discover(auth_header):
                discover_called.append(True)
                return None  # No encontrado

            with patch.object(jddcia_provider, '_probe_url', mock_probe), \
                 patch.object(jddcia_provider, '_discover_gateway_ip', mock_discover):
                result = await provider._get_working_base_url()

            # La cache debe haberse limpiado
            assert not os.path.exists(cache_file), (
                "La cache debe eliminarse cuando la IP cacheada no responde"
            )
            # El autodescubrimiento debe haberse iniciado
            assert len(discover_called) > 0, "Debe iniciarse autodescubrimiento tras fallo de cache"

        finally:
            jddcia_provider._IP_CACHE_FILE = original_cache


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 4: generate_text — logging de excepciones con type(e).__name__
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateTextExceptionLogging:
    """
    generate_text debe loguear type(e).__name__ para diagnóstico.
    Bug anterior: el log solo mostraba str(e), sin el tipo de excepción.
    Esto hacía imposible distinguir ReadTimeout de ConnectError de JSONDecodeError.
    """

    @pytest.mark.asyncio
    async def test_generate_text_logs_exception_type_on_timeout(self, caplog):
        """ReadTimeout se loguea con su tipo completo"""
        import httpx
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig
        import logging

        provider = JDDCIAProvider()
        provider.configure(AIConfig(
            api_key="test-key",
            model="unified-main",
            base_url="http://jddcia.local/api/vlm/v1"
        ))

        async def mock_get_working_url():
            return "http://jddcia.local/api/vlm/v1"

        with patch.object(provider, '_get_working_base_url', mock_get_working_url):
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(
                    side_effect=httpx.ReadTimeout("Read operation timed out")
                )
                mock_client_cls.return_value = mock_client

                with caplog.at_level(logging.ERROR, logger="backend.drivers.ai.jddcia_provider"):
                    with pytest.raises(httpx.ReadTimeout):
                        await provider.generate_text("test prompt")

        # Verificar que el log contiene el tipo de excepción
        error_logs = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("ReadTimeout" in msg for msg in error_logs), (
            f"El log debe contener 'ReadTimeout'. Logs encontrados: {error_logs}"
        )

    @pytest.mark.asyncio
    async def test_generate_text_logs_exception_type_on_connect_error(self, caplog):
        """ConnectError se loguea con su tipo completo"""
        import httpx
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig
        import logging

        provider = JDDCIAProvider()
        provider.configure(AIConfig(
            api_key="test-key",
            model="unified-main",
            base_url="http://jddcia.local/api/vlm/v1"
        ))

        async def mock_get_working_url():
            return "http://jddcia.local/api/vlm/v1"

        with patch.object(provider, '_get_working_base_url', mock_get_working_url):
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(
                    side_effect=httpx.ConnectError("Connection refused")
                )
                mock_client_cls.return_value = mock_client

                with caplog.at_level(logging.ERROR, logger="backend.drivers.ai.jddcia_provider"):
                    with pytest.raises(httpx.ConnectError):
                        await provider.generate_text("test prompt")

        error_logs = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("ConnectError" in msg for msg in error_logs), (
            f"El log debe contener 'ConnectError'. Logs encontrados: {error_logs}"
        )

    @pytest.mark.asyncio
    async def test_generate_text_raises_on_404(self):
        """
        404 en /chat/completions lanza excepción con mensaje descriptivo.
        (Diferente de 404 en /models — aquí es un error real del gateway)
        """
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        provider.configure(AIConfig(
            api_key="test-key",
            model="unified-main",
            base_url="http://jddcia.local/api/vlm/v1"
        ))

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        async def mock_get_working_url():
            return "http://jddcia.local/api/vlm/v1"

        with patch.object(provider, '_get_working_base_url', mock_get_working_url):
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                with pytest.raises(Exception) as exc_info:
                    await provider.generate_text("test prompt")

        assert "404" in str(exc_info.value), "La excepción debe mencionar 404"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 5: _load_lan_max_retries — lee de config.json
# ═══════════════════════════════════════════════════════════════════════════════

class TestLanMaxRetriesFromConfig:
    """
    _load_lan_max_retries debe leer lan_max_retries de config.json.
    Bug anterior: el orchestrator usaba un bucle infinito (while True sin límite).
    """

    def test_load_lan_max_retries_reads_from_config(self, tmp_path):
        """Lee lan_max_retries=10 de config.json"""
        config = {"lan_max_retries": 10, "ai_local_only": True}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        original_path = orch_mod._CONFIG_JSON_PATH
        try:
            orch_mod._CONFIG_JSON_PATH = str(config_file)
            retries = orch_mod._load_lan_max_retries()
            assert retries == 10, f"Esperado 10, obtenido {retries}"
        finally:
            orch_mod._CONFIG_JSON_PATH = original_path

    def test_load_lan_max_retries_uses_default_if_missing(self, tmp_path):
        """Si lan_max_retries no está en config.json, usa default (10)"""
        config = {"ai_local_only": True}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        original_path = orch_mod._CONFIG_JSON_PATH
        try:
            orch_mod._CONFIG_JSON_PATH = str(config_file)
            retries = orch_mod._load_lan_max_retries()
            assert retries == orch_mod._LAN_MAX_RETRIES_DEFAULT
        finally:
            orch_mod._CONFIG_JSON_PATH = original_path

    def test_load_lan_max_retries_uses_default_if_config_missing(self, tmp_path):
        """Si config.json no existe, usa default (10)"""
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        original_path = orch_mod._CONFIG_JSON_PATH
        try:
            orch_mod._CONFIG_JSON_PATH = str(tmp_path / "nonexistent.json")
            retries = orch_mod._load_lan_max_retries()
            assert retries == orch_mod._LAN_MAX_RETRIES_DEFAULT
        finally:
            orch_mod._CONFIG_JSON_PATH = original_path

    def test_load_lan_max_retries_rejects_zero(self, tmp_path):
        """lan_max_retries=0 es inválido → usa default"""
        config = {"lan_max_retries": 0}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        original_path = orch_mod._CONFIG_JSON_PATH
        try:
            orch_mod._CONFIG_JSON_PATH = str(config_file)
            retries = orch_mod._load_lan_max_retries()
            assert retries == orch_mod._LAN_MAX_RETRIES_DEFAULT, (
                "lan_max_retries=0 debe usar el default"
            )
        finally:
            orch_mod._CONFIG_JSON_PATH = original_path

    def test_load_lan_max_retries_rejects_negative(self, tmp_path):
        """lan_max_retries=-1 es inválido → usa default"""
        config = {"lan_max_retries": -1}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        original_path = orch_mod._CONFIG_JSON_PATH
        try:
            orch_mod._CONFIG_JSON_PATH = str(config_file)
            retries = orch_mod._load_lan_max_retries()
            assert retries == orch_mod._LAN_MAX_RETRIES_DEFAULT
        finally:
            orch_mod._CONFIG_JSON_PATH = original_path

    def test_load_lan_max_retries_custom_value(self, tmp_path):
        """Valor personalizado (5) se lee correctamente"""
        config = {"lan_max_retries": 5}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        original_path = orch_mod._CONFIG_JSON_PATH
        try:
            orch_mod._CONFIG_JSON_PATH = str(config_file)
            retries = orch_mod._load_lan_max_retries()
            assert retries == 5
        finally:
            orch_mod._CONFIG_JSON_PATH = original_path

    def test_production_config_has_lan_max_retries(self):
        """
        El config.json de producción tiene lan_max_retries definido y > 0.
        """
        config_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            "../../backend/modules/chat/config.json"
        ))
        if not os.path.exists(config_path):
            pytest.skip(f"config.json no encontrado en {config_path}")

        with open(config_path) as f:
            cfg = json.load(f)

        assert "lan_max_retries" in cfg, (
            "config.json debe tener lan_max_retries definido"
        )
        assert cfg["lan_max_retries"] > 0, (
            f"lan_max_retries debe ser > 0, obtenido: {cfg['lan_max_retries']}"
        )

    def test_production_config_has_lan_read_timeout(self):
        """
        El config.json de producción tiene lan_read_timeout_s definido y >= 30.
        """
        config_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            "../../backend/modules/chat/config.json"
        ))
        if not os.path.exists(config_path):
            pytest.skip(f"config.json no encontrado en {config_path}")

        with open(config_path) as f:
            cfg = json.load(f)

        assert "lan_read_timeout_s" in cfg, (
            "config.json debe tener lan_read_timeout_s definido"
        )
        assert cfg["lan_read_timeout_s"] >= 30, (
            f"lan_read_timeout_s debe ser >= 30s para Qwen3 30B, "
            f"obtenido: {cfg['lan_read_timeout_s']}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 6: _execute_lan_only — respeta max_retries, devuelve (None, None)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecuteLanOnlyMaxRetries:
    """
    _execute_lan_only debe respetar lan_max_retries y devolver (None, None)
    cuando se agotan las rondas.
    Bug anterior: bucle infinito (while True sin límite de rondas).
    """

    @pytest.mark.asyncio
    async def test_execute_lan_only_returns_none_after_max_retries(self, monkeypatch):
        """
        Si todos los modelos LAN fallan durante max_retries rondas,
        _execute_lan_only devuelve (None, None).
        """
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: True)
        monkeypatch.setattr(orch_mod, "_load_lan_max_retries", lambda: 3)  # Solo 3 rondas

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orchestrator = ModelFallbackOrchestrator()
        orchestrator.model_manager = MagicMock()
        orchestrator.model_manager.list_models.return_value = [
            {
                "id": "jddcia-qwen3-30b",
                "name": "Qwen3 VL 30B (JDDC LAN)",
                "model_id": "unified-main",
                "schema": "jddcia",
                "provider": "jddcia",
                "api_key": "test-key",
                "base_url": "http://jddcia.local/api/vlm/v1",
                "enabled": True,
                "score": 100,
            }
        ]
        orchestrator.model_manager.report_result = MagicMock()

        call_count = {"n": 0}

        async def always_fail(model_config, system_prompt, user_message, images=None, attempt=1):
            call_count["n"] += 1
            return None  # Siempre falla

        orchestrator._try_model = always_fail
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="test max retries",
        )

        assert response is None, "Debe devolver None tras agotar max_retries"
        assert model_id is None, "Debe devolver None model_id tras agotar max_retries"
        assert call_count["n"] == 3, (
            f"Con max_retries=3 y 1 modelo, debe haber exactamente 3 llamadas. "
            f"Hubo {call_count['n']}"
        )

    @pytest.mark.asyncio
    async def test_execute_lan_only_respects_max_retries_from_config(self, monkeypatch, tmp_path):
        """
        max_retries se lee de config.json en cada llamada.
        Cambiar config.json surte efecto sin reiniciar el servidor.
        """
        import backend.modules.chat.model_fallback_orchestrator as orch_mod

        # Crear config.json temporal con max_retries=2
        config = {"lan_max_retries": 2, "ai_local_only": True}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        original_path = orch_mod._CONFIG_JSON_PATH
        orch_mod._CONFIG_JSON_PATH = str(config_file)

        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: True)

        try:
            from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
            orchestrator = ModelFallbackOrchestrator()
            orchestrator.model_manager = MagicMock()
            orchestrator.model_manager.list_models.return_value = [
                {
                    "id": "jddcia-qwen3-30b",
                    "name": "Qwen3 VL 30B",
                    "model_id": "unified-main",
                    "schema": "jddcia",
                    "provider": "jddcia",
                    "api_key": "test-key",
                    "base_url": "http://jddcia.local/api/vlm/v1",
                    "enabled": True,
                    "score": 100,
                }
            ]
            orchestrator.model_manager.report_result = MagicMock()

            call_count = {"n": 0}

            async def always_fail(model_config, system_prompt, user_message, images=None, attempt=1):
                call_count["n"] += 1
                return None

            orchestrator._try_model = always_fail
            monkeypatch.setattr(asyncio, "sleep", AsyncMock())

            response, model_id = await orchestrator.execute_with_fallback(
                system_prompt="SQL",
                user_message="test",
            )

            assert response is None
            assert call_count["n"] == 2, (
                f"Con lan_max_retries=2 en config.json, deben ser 2 llamadas. "
                f"Hubo {call_count['n']}"
            )
        finally:
            orch_mod._CONFIG_JSON_PATH = original_path

    @pytest.mark.asyncio
    async def test_execute_lan_only_feedback_on_exhaustion(self, monkeypatch):
        """
        Cuando se agotan las rondas, se llama al feedback_callback con mensaje de error.
        """
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: True)
        monkeypatch.setattr(orch_mod, "_load_lan_max_retries", lambda: 2)

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orchestrator = ModelFallbackOrchestrator()
        orchestrator.model_manager = MagicMock()
        orchestrator.model_manager.list_models.return_value = [
            {
                "id": "jddcia-qwen3-30b",
                "name": "Qwen3 VL 30B",
                "model_id": "unified-main",
                "schema": "jddcia",
                "provider": "jddcia",
                "api_key": "test-key",
                "base_url": "http://jddcia.local/api/vlm/v1",
                "enabled": True,
                "score": 100,
            }
        ]
        orchestrator.model_manager.report_result = MagicMock()

        feedback_messages = []

        async def always_fail(model_config, system_prompt, user_message, images=None, attempt=1):
            return None

        orchestrator._try_model = always_fail
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="test",
            feedback_callback=lambda msg: feedback_messages.append(msg),
        )

        assert response is None
        # Debe haber un mensaje de error final
        assert any("❌" in msg or "no disponible" in msg.lower() for msg in feedback_messages), (
            f"Debe haber mensaje de error al agotar reintentos. Mensajes: {feedback_messages}"
        )

    @pytest.mark.asyncio
    async def test_execute_lan_only_succeeds_before_max_retries(self, monkeypatch):
        """
        Si el modelo responde antes de agotar max_retries, devuelve la respuesta.
        """
        import backend.modules.chat.model_fallback_orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "_load_ai_local_only", lambda: True)
        monkeypatch.setattr(orch_mod, "_load_lan_max_retries", lambda: 10)

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orchestrator = ModelFallbackOrchestrator()
        orchestrator.model_manager = MagicMock()
        orchestrator.model_manager.list_models.return_value = [
            {
                "id": "jddcia-qwen3-30b",
                "name": "Qwen3 VL 30B",
                "model_id": "unified-main",
                "schema": "jddcia",
                "provider": "jddcia",
                "api_key": "test-key",
                "base_url": "http://jddcia.local/api/vlm/v1",
                "enabled": True,
                "score": 100,
            }
        ]
        orchestrator.model_manager.report_result = MagicMock()

        call_count = {"n": 0}

        async def fail_twice_then_succeed(model_config, system_prompt, user_message,
                                          images=None, attempt=1):
            call_count["n"] += 1
            if call_count["n"] < 3:
                return None
            return "SELECT FIRST 10 * FROM ARTICULO"

        orchestrator._try_model = fail_twice_then_succeed
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        response, model_id = await orchestrator.execute_with_fallback(
            system_prompt="SQL",
            user_message="dame artículos",
        )

        assert response == "SELECT FIRST 10 * FROM ARTICULO"
        assert model_id == "jddcia-qwen3-30b"
        assert call_count["n"] == 3, f"Debe haber 3 llamadas (2 fallos + 1 éxito). Hubo {call_count['n']}"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 7: Integración — _try_model loguea tipo de excepción
# ═══════════════════════════════════════════════════════════════════════════════

class TestTryModelExceptionLogging:
    """
    _try_model debe loguear type(e).__name__ para diagnóstico.
    Bug anterior: solo logueaba str(e), sin el tipo.
    """

    @pytest.mark.asyncio
    async def test_try_model_logs_exception_type(self, monkeypatch, caplog):
        """
        Cuando el provider lanza una excepción, _try_model loguea el tipo.
        """
        import logging
        import backend.modules.chat.model_fallback_orchestrator as orch_mod

        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        orchestrator = ModelFallbackOrchestrator()
        orchestrator.model_manager = MagicMock()
        orchestrator.model_manager.report_result = MagicMock()

        model_config = {
            "id": "jddcia-qwen3-30b",
            "name": "Qwen3 VL 30B",
            "model_id": "unified-main",
            "schema": "jddcia",
            "provider": "jddcia",
            "api_key": "test-key",
            "base_url": "http://jddcia.local/api/vlm/v1",
        }

        import httpx
        from backend.core.factory.ai_factory import AIFactory

        mock_provider = AsyncMock()
        mock_provider.configure = MagicMock()
        mock_provider.generate_text = AsyncMock(
            side_effect=httpx.ReadTimeout("Read operation timed out after 60s")
        )

        with patch.object(AIFactory, 'get_provider', return_value=mock_provider):
            with caplog.at_level(logging.ERROR, logger="backend.modules.chat.model_fallback_orchestrator"):
                result = await orchestrator._try_model(
                    model_config=model_config,
                    system_prompt="SQL",
                    user_message="test",
                    attempt=1
                )

        assert result is None, "_try_model debe devolver None cuando el provider lanza excepción"

        error_logs = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("ReadTimeout" in msg for msg in error_logs), (
            f"El log debe contener 'ReadTimeout'. Logs: {error_logs}"
        )
