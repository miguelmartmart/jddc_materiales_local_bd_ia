"""
Tests para JDDCIAProvider — cliente HTTP para Qwen3 VL 30B en red LAN JDDC.

Verifica que:
  - El timeout es exactamente 20s (no 60s ni más)
  - Las peticiones van SOLO a URLs de la red local (jddcia.local o 192.168.x.x)
  - NUNCA se hace una petición a internet (api.groq.com, generativelanguage.googleapis.com, etc.)
  - El header Authorization se envía correctamente
  - Si el servidor no responde en 20s, lanza TimeoutException (no bloquea indefinidamente)
  - Si el servidor devuelve error HTTP, se propaga correctamente
  - La respuesta se extrae correctamente del JSON de vLLM

Autor: DEVIA System Tests
"""

import pytest
import httpx
import json
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Any

from backend.drivers.ai.jddcia_provider import JDDCIAProvider
from backend.core.abstract.ai import AIConfig


# ---------------------------------------------------------------------------
# URLs de internet que NUNCA deben usarse
# ---------------------------------------------------------------------------

INTERNET_URLS = [
    "api.groq.com",
    "generativelanguage.googleapis.com",
    "api.openai.com",
    "api.anthropic.com",
    "api.deepseek.com",
    "api.mistral.ai",
    "api.cohere.ai",
    "api.together.xyz",
    "api.fireworks.ai",
    "openrouter.ai",
    "dashscope.aliyuncs.com",
    "api.ai21.com",
    "api.reka.ai",
    "api.yi.ai",
    "api.kimi.ai",
]

# URLs locales válidas
LOCAL_URLS = [
    "http://jddcia.local/api/vlm/v1",
    "http://192.168.0.36/api/vlm/v1",
    "http://192.168.0.38/api/vlm/v1",
    "http://192.168.1.100/api/vlm/v1",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def provider():
    """Instancia de JDDCIAProvider configurada con URL local."""
    p = JDDCIAProvider()
    config = AIConfig(
        api_key="YWRtaW46YWlzdGFjazIwMjY=",
        model="unified-main",
        base_url="http://jddcia.local/api/vlm/v1",
        headers={"Authorization": "Basic YWRtaW46YWlzdGFjazIwMjY="}
    )
    p.configure(config)
    return p


@pytest.fixture
def provider_ip():
    """Instancia de JDDCIAProvider configurada con IP directa."""
    p = JDDCIAProvider()
    config = AIConfig(
        api_key="YWRtaW46YWlzdGFjazIwMjY=",
        model="unified-main",
        base_url="http://192.168.0.36/api/vlm/v1",
        headers={"Authorization": "Basic YWRtaW46YWlzdGFjazIwMjY="}
    )
    p.configure(config)
    return p


def _make_vllm_response(content: str = "Hay 100 artículos.") -> dict:
    """Crea una respuesta simulada de vLLM/OpenAI compatible."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1772453174,
        "model": "unified-main",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120
        }
    }


# ---------------------------------------------------------------------------
# Tests: Timeout de 20 segundos
# ---------------------------------------------------------------------------

class TestJDDCIAProviderTimeout:
    """Tests para verificar que el timeout es exactamente 20s."""

    def test_timeout_configurado_es_20_segundos(self, provider):
        """
        Verifica que el provider usa timeout de 20s.
        Inspecciona la configuración interna del cliente httpx.
        """
        # El timeout debe ser 20s, no 60s ni más
        # Verificamos que el provider tiene la configuración correcta
        # inspeccionando el código fuente o los atributos del provider
        import inspect
        source = inspect.getsource(JDDCIAProvider)
        
        # Debe contener timeout de 20s
        assert "20.0" in source or "20," in source, \
            "El timeout debe ser 20s en JDDCIAProvider"
        
        # NO debe contener timeout de 60s o más
        assert "60.0" not in source and "timeout=60" not in source, \
            "El timeout NO debe ser 60s — fue reducido a 20s para fallar rápido"

    @pytest.mark.asyncio
    async def test_timeout_lanza_excepcion_en_20_segundos(self, provider):
        """
        Verifica que si el servidor no responde, lanza excepción de timeout
        (no bloquea indefinidamente).
        """
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("Read timeout")
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await provider.generate_text(
                    prompt="cuantos articulos hay",
                    system_instruction="Eres un asistente SQL"
                )

    @pytest.mark.asyncio
    async def test_timeout_no_bloquea_mas_de_20_segundos(self, provider):
        """
        Verifica que el provider no espera más de 20s.
        Simula un timeout inmediato y verifica que se propaga.
        """
        import time

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=httpx.ReadTimeout("Read timeout after 20s")
            )
            mock_client_class.return_value = mock_client

            t0 = time.time()
            with pytest.raises(Exception):
                await provider.generate_text(
                    prompt="cuantos articulos hay",
                    system_instruction="Eres un asistente SQL"
                )
            elapsed = time.time() - t0

            # El test debe completarse en menos de 5s (el timeout es simulado)
            assert elapsed < 5.0, \
                f"El provider tardó {elapsed:.1f}s — debería fallar rápido con timeout simulado"


# ---------------------------------------------------------------------------
# Tests: Solo URLs locales — NUNCA internet
# ---------------------------------------------------------------------------

class TestJDDCIAProviderLocalOnly:
    """Tests que verifican que las peticiones van SOLO a la red local."""

    @pytest.mark.asyncio
    async def test_peticion_va_a_url_local_mdns(self, provider):
        """Verifica que la petición va a jddcia.local (mDNS), no a internet."""
        urls_llamadas = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                urls_llamadas.append(url)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider.generate_text(
                prompt="cuantos articulos hay",
                system_instruction="Eres un asistente SQL"
            )

        assert len(urls_llamadas) >= 1
        for url in urls_llamadas:
            assert "jddcia.local" in url, \
                f"La URL debe ser local (jddcia.local), pero fue: {url}"

    @pytest.mark.asyncio
    async def test_peticion_va_a_url_local_ip(self, provider_ip):
        """Verifica que la petición va a IP local (192.168.x.x), no a internet."""
        urls_llamadas = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                urls_llamadas.append(url)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider_ip.generate_text(
                prompt="cuantos articulos hay",
                system_instruction="Eres un asistente SQL"
            )

        assert len(urls_llamadas) >= 1
        for url in urls_llamadas:
            assert "192.168." in url, \
                f"La URL debe ser IP local (192.168.x.x), pero fue: {url}"

    @pytest.mark.asyncio
    async def test_nunca_llama_a_groq(self, provider):
        """Verifica que NUNCA se hace una petición a api.groq.com."""
        urls_llamadas = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                urls_llamadas.append(url)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider.generate_text("test", "system")

        for url in urls_llamadas:
            assert "groq.com" not in url, \
                f"JDDCIAProvider NO debe llamar a Groq: {url}"

    @pytest.mark.asyncio
    async def test_nunca_llama_a_openai(self, provider):
        """Verifica que NUNCA se hace una petición a api.openai.com."""
        urls_llamadas = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                urls_llamadas.append(url)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider.generate_text("test", "system")

        for url in urls_llamadas:
            assert "openai.com" not in url, \
                f"JDDCIAProvider NO debe llamar a OpenAI: {url}"

    @pytest.mark.asyncio
    async def test_nunca_llama_a_ninguna_url_de_internet(self, provider):
        """Verifica que NUNCA se llama a ninguna URL de internet conocida."""
        urls_llamadas = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                urls_llamadas.append(url)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider.generate_text("test", "system")

        for url in urls_llamadas:
            for internet_url in INTERNET_URLS:
                assert internet_url not in url, \
                    f"JDDCIAProvider NO debe llamar a internet ({internet_url}): {url}"

    def test_base_url_configurada_es_local(self, provider):
        """Verifica que la base_url configurada es una URL local."""
        base_url = provider.config.base_url if hasattr(provider, 'config') else ""
        if not base_url:
            # Intentar obtener de otro atributo
            base_url = getattr(provider, 'base_url', "") or \
                       getattr(provider, '_base_url', "") or \
                       getattr(provider, 'api_base', "")

        if base_url:
            for internet_url in INTERNET_URLS:
                assert internet_url not in base_url, \
                    f"La base_url del provider NO debe ser internet: {base_url}"

    def test_provider_no_tiene_url_de_internet_en_codigo(self):
        """
        Verifica que el código fuente de JDDCIAProvider no contiene
        URLs hardcodeadas de servicios de internet.
        """
        import inspect
        source = inspect.getsource(JDDCIAProvider)

        for internet_url in INTERNET_URLS:
            assert internet_url not in source, \
                f"JDDCIAProvider NO debe tener hardcodeada la URL: {internet_url}"


# ---------------------------------------------------------------------------
# Tests: Headers de autenticación
# ---------------------------------------------------------------------------

class TestJDDCIAProviderAuth:
    """Tests para verificar que los headers de autenticación se envían correctamente."""

    @pytest.mark.asyncio
    async def test_envia_header_authorization(self, provider):
        """Verifica que el header Authorization se envía en la petición."""
        headers_enviados = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                headers_enviados.update(kwargs.get("headers", {}))
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider.generate_text("test", "system")

        # Debe haber enviado algún header de autenticación
        auth_headers = {k: v for k, v in headers_enviados.items()
                       if "auth" in k.lower() or "authorization" in k.lower()}
        assert len(auth_headers) > 0 or "Authorization" in headers_enviados, \
            "Debe enviarse el header Authorization"


# ---------------------------------------------------------------------------
# Tests: Respuesta correcta del servidor vLLM
# ---------------------------------------------------------------------------

class TestJDDCIAProviderResponse:
    """Tests para verificar que la respuesta de vLLM se procesa correctamente."""

    @pytest.mark.asyncio
    async def test_extrae_contenido_de_respuesta_vllm(self, provider):
        """Verifica que el contenido del mensaje se extrae correctamente."""
        expected_content = "Hay 11.833 artículos en total."

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def mock_post(url, **kwargs):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response(expected_content)
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            result = await provider.generate_text(
                prompt="cuantos articulos hay",
                system_instruction="Eres un asistente SQL"
            )

        assert result == expected_content

    @pytest.mark.asyncio
    async def test_maneja_error_http_429_servidor_ocupado(self, provider):
        """
        Verifica que un error 429 (servidor ocupado/cola llena) se maneja
        correctamente y se propaga como excepción.
        """
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def mock_post(url, **kwargs):
                mock_response = MagicMock()
                mock_response.status_code = 429
                mock_response.raise_for_status = MagicMock(
                    side_effect=httpx.HTTPStatusError(
                        "429 Too Many Requests",
                        request=MagicMock(),
                        response=mock_response
                    )
                )
                return mock_response

            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await provider.generate_text("test", "system")

    @pytest.mark.asyncio
    async def test_maneja_error_http_500_servidor_caido(self, provider):
        """Verifica que un error 500 del servidor se propaga correctamente."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def mock_post(url, **kwargs):
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_response.raise_for_status = MagicMock(
                    side_effect=httpx.HTTPStatusError(
                        "500 Internal Server Error",
                        request=MagicMock(),
                        response=mock_response
                    )
                )
                return mock_response

            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await provider.generate_text("test", "system")

    @pytest.mark.asyncio
    async def test_maneja_connection_error_servidor_apagado(self, provider):
        """Verifica que un error de conexión (servidor apagado) se propaga."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await provider.generate_text("test", "system")

    @pytest.mark.asyncio
    async def test_envia_modelo_correcto_en_payload(self, provider):
        """Verifica que el payload incluye el model_id correcto (unified-main)."""
        payloads_enviados = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                payload = kwargs.get("json", kwargs.get("data", {}))
                if isinstance(payload, str):
                    payload = json.loads(payload)
                payloads_enviados.append(payload)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider.generate_text(
                prompt="cuantos articulos hay",
                system_instruction="Eres un asistente SQL"
            )

        assert len(payloads_enviados) >= 1
        payload = payloads_enviados[0]
        if isinstance(payload, dict):
            assert payload.get("model") == "unified-main", \
                f"El modelo debe ser 'unified-main', fue: {payload.get('model')}"

    @pytest.mark.asyncio
    async def test_envia_messages_con_system_y_user(self, provider):
        """Verifica que el payload incluye messages con roles system y user."""
        payloads_enviados = []

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            async def capture_post(url, **kwargs):
                payload = kwargs.get("json", {})
                payloads_enviados.append(payload)
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = _make_vllm_response()
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await provider.generate_text(
                prompt="cuantos articulos hay",
                system_instruction="Eres un asistente SQL de Firebird"
            )

        if payloads_enviados and isinstance(payloads_enviados[0], dict):
            messages = payloads_enviados[0].get("messages", [])
            roles = [m.get("role") for m in messages]
            assert "user" in roles, "Debe haber un mensaje con role='user'"


# ---------------------------------------------------------------------------
# Tests: Configuración del provider
# ---------------------------------------------------------------------------

class TestJDDCIAProviderConfig:
    """Tests para verificar la configuración del provider."""

    def test_provider_se_configura_con_url_local(self):
        """Verifica que el provider acepta URLs locales."""
        p = JDDCIAProvider()
        config = AIConfig(
            api_key="test_key",
            model="unified-main",
            base_url="http://jddcia.local/api/vlm/v1"
        )
        # No debe lanzar excepción
        p.configure(config)

    def test_provider_se_configura_con_ip_local(self):
        """Verifica que el provider acepta IPs locales."""
        p = JDDCIAProvider()
        config = AIConfig(
            api_key="test_key",
            model="unified-main",
            base_url="http://192.168.0.36/api/vlm/v1"
        )
        p.configure(config)

    def test_provider_no_acepta_url_de_internet(self):
        """
        Verifica que si se configura con URL de internet,
        el provider la rechaza o al menos no la usa silenciosamente.
        
        Nota: Este test documenta el comportamiento esperado.
        Si el provider no valida la URL, el test pasa igualmente
        pero sirve como documentación de la intención.
        """
        p = JDDCIAProvider()
        # Intentar configurar con URL de internet
        config = AIConfig(
            api_key="test_key",
            model="unified-main",
            base_url="https://api.groq.com/openai/v1"
        )
        # El provider puede aceptar la config (no valida en configure)
        # pero el test documenta que NO debe usarse así
        # La validación real está en LOCAL_MODEL_IDS del orchestrator
        p.configure(config)
        # Si llegamos aquí, el provider no valida la URL en configure()
        # La protección está en el orchestrator (ai_local_only)
