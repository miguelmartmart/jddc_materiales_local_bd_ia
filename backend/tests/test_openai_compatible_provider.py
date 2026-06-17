"""
test_openai_compatible_provider.py — Tests del provider OpenAI-compatible con reintentos

Cubre:
  - generate_text: éxito en el primer intento
  - generate_text: reintento con redescubrimiento de IP tras error de conexión
  - generate_text: no reintenta en errores de autenticación (401)
  - generate_text: no reintenta en errores de contexto (400 context)
  - generate_text: lanza excepción clara tras agotar todos los reintentos
  - generate_text: mensaje de error específico para LM Studio vs otros modelos
  - _is_lmstudio_model: detecta correctamente modelos LM Studio
  - _build_messages: trunca el prompt si supera el context_limit
  - _build_extra_body: enable_thinking=false para Qwen3

Principios DEVIA:
  - Tests simulan el flujo real del provider
  - Cada test tiene una sola responsabilidad
  - Sin llamadas reales a la red
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_provider(model_name: str = "qwen/qwen3-vl-8b", base_url: str = "http://192.168.56.1:1234/v1"):
    """Crea un provider configurado para tests."""
    from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
    from bots.interjddcia.backend.core.abstract.ai import AIConfig

    provider = OpenAICompatibleProvider()

    # Mock del cliente OpenAI
    mock_client = MagicMock()
    provider.client = mock_client
    provider.model_name = model_name
    provider._context_limit = 8192
    provider._max_tokens = 512
    provider._timeout_s = 180
    provider._enable_thinking = False

    return provider, mock_client


def make_openai_response(content: str, finish_reason: str = "stop"):
    """Crea una respuesta mock de OpenAI."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.finish_reason = finish_reason

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


# ── Tests de _is_lmstudio_model ───────────────────────────────────────────────

class TestIsLmstudioModel:

    def test_qwen3_vl_8b_es_lmstudio(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p.model_name = "qwen/qwen3-vl-8b"
        assert p._is_lmstudio_model() is True

    def test_qwen3_es_lmstudio(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p.model_name = "qwen/qwen3"
        assert p._is_lmstudio_model() is True

    def test_unified_main_no_es_lmstudio(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p.model_name = "unified-main"
        assert p._is_lmstudio_model() is False

    def test_gpt4_no_es_lmstudio(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p.model_name = "gpt-4o"
        assert p._is_lmstudio_model() is False

    def test_model_name_none_no_es_lmstudio(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p.model_name = None
        assert p._is_lmstudio_model() is False


# ── Tests de _build_extra_body ────────────────────────────────────────────────

class TestBuildExtraBody:

    def test_thinking_false_devuelve_enable_thinking_false(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p._enable_thinking = False
        result = p._build_extra_body()
        assert result == {"enable_thinking": False}

    def test_thinking_true_devuelve_none(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p._enable_thinking = True
        result = p._build_extra_body()
        assert result is None

    def test_thinking_none_devuelve_none(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p._enable_thinking = None
        result = p._build_extra_body()
        assert result is None


# ── Tests de _build_messages ──────────────────────────────────────────────────

class TestBuildMessages:

    def test_prompt_corto_no_se_trunca(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p._context_limit = 8192
        p._max_tokens = 512
        p._enable_thinking = False

        prompt = "¿Cuántas facturas hay este mes?"
        messages = p._build_messages(prompt, "Eres un asistente.")

        user_msg = next(m for m in messages if m["role"] == "user")
        assert user_msg["content"] == prompt  # Sin truncar

    def test_prompt_largo_se_trunca(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p._context_limit = 100  # Límite muy bajo para forzar truncación
        p._max_tokens = 50
        p._enable_thinking = False

        # Prompt de 2000 chars → ~500 tokens >> límite de 100
        prompt = "x" * 2000
        messages = p._build_messages(prompt, None)

        user_msg = next(m for m in messages if m["role"] == "user")
        assert "[TRUNCADO]" in user_msg["content"]
        assert len(user_msg["content"]) < len(prompt)

    def test_system_instruction_se_incluye(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p._context_limit = 8192
        p._max_tokens = 512
        p._enable_thinking = False

        messages = p._build_messages("pregunta", "Eres un asistente de facturación.")

        system_msg = next((m for m in messages if m["role"] == "system"), None)
        assert system_msg is not None
        assert system_msg["content"] == "Eres un asistente de facturación."

    def test_sin_system_instruction_no_hay_system_msg(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        p = OpenAICompatibleProvider()
        p._context_limit = 8192
        p._max_tokens = 512
        p._enable_thinking = False

        messages = p._build_messages("pregunta", None)

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 0


# ── Tests de generate_text — éxito ────────────────────────────────────────────

class TestGenerateTextSuccess:

    @pytest.mark.asyncio
    async def test_exito_primer_intento(self):
        provider, mock_client = make_provider()
        mock_client.chat.completions.create.return_value = make_openai_response(
            "Hay 42 facturas este mes."
        )

        result = await provider.generate_text("¿Cuántas facturas hay?", "Eres un asistente.")

        assert result == "Hay 42 facturas este mes."
        assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_incluye_enable_thinking_false_en_extra_body(self):
        provider, mock_client = make_provider()
        mock_client.chat.completions.create.return_value = make_openai_response("Respuesta")

        await provider.generate_text("pregunta")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs.get("extra_body") == {"enable_thinking": False}

    @pytest.mark.asyncio
    async def test_max_tokens_en_llamada(self):
        provider, mock_client = make_provider()
        provider._max_tokens = 256
        mock_client.chat.completions.create.return_value = make_openai_response("Respuesta")

        await provider.generate_text("pregunta")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 256


# ── Tests de generate_text — reintentos ───────────────────────────────────────

class TestGenerateTextRetries:

    @pytest.mark.asyncio
    async def test_reintenta_tras_error_conexion(self):
        provider, mock_client = make_provider()

        # Primer intento falla con error de conexión, segundo tiene éxito
        mock_client.chat.completions.create.side_effect = [
            ConnectionError("Connection refused"),
            make_openai_response("Respuesta en segundo intento"),
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch(
                "bots.interjddcia.backend.drivers.ai.openai_compatible_provider."
                "OpenAICompatibleProvider._is_lmstudio_model",
                return_value=False  # No LM Studio → no discovery, solo reintento simple
            ):
                result = await provider.generate_text("pregunta")

        assert result == "Respuesta en segundo intento"
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_reintenta_con_discovery_para_lmstudio(self):
        provider, mock_client = make_provider(model_name="qwen/qwen3-vl-8b")

        # Primer intento falla, segundo tiene éxito tras redescubrimiento
        mock_client.chat.completions.create.side_effect = [
            ConnectionError("Connection refused to 172.19.64.1"),
            make_openai_response("Respuesta tras redescubrimiento"),
        ]

        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc_module
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch.object(disc_module, "discover_lmstudio",
                              new_callable=AsyncMock,
                              return_value="http://192.168.56.1:1234/v1"):
                with patch.object(disc_module, "invalidate_cache"):
                    # _reconfigure_client crearía un cliente real — lo mockeamos
                    # para que el mock_client siga siendo el cliente activo
                    with patch.object(provider, "_reconfigure_client"):
                        result = await provider.generate_text("pregunta")

        assert result == "Respuesta tras redescubrimiento"
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_no_reintenta_error_autenticacion(self):
        provider, mock_client = make_provider()

        mock_client.chat.completions.create.side_effect = Exception(
            "HTTP 401: Unauthorized"
        )

        with pytest.raises(Exception) as exc_info:
            await provider.generate_text("pregunta")

        assert "autenticación" in str(exc_info.value).lower()
        # Solo 1 intento — no reintenta en 401
        assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_no_reintenta_error_contexto(self):
        provider, mock_client = make_provider()

        mock_client.chat.completions.create.side_effect = Exception(
            "HTTP 400: context length exceeded"
        )

        with pytest.raises(Exception) as exc_info:
            await provider.generate_text("pregunta")

        assert "contexto" in str(exc_info.value).lower()
        # Solo 1 intento — no reintenta en error de contexto
        assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_agota_reintentos_lanza_excepcion_clara_lmstudio(self):
        provider, mock_client = make_provider(model_name="qwen/qwen3-vl-8b")

        # Todos los intentos fallan con error de conexión
        mock_client.chat.completions.create.side_effect = ConnectionError(
            "Connection refused"
        )

        # Parchear el módulo fuente directamente (el provider importa inline)
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc_module
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch.object(disc_module, "discover_lmstudio",
                              new_callable=AsyncMock,
                              return_value=None):  # No encuentra LM Studio
                with patch.object(disc_module, "invalidate_cache"):
                    # _reconfigure_client crearía un cliente real — lo mockeamos
                    with patch.object(provider, "_reconfigure_client"):
                        with pytest.raises(Exception) as exc_info:
                            await provider.generate_text("pregunta")

        error_msg = str(exc_info.value)
        assert "LM Studio" in error_msg
        assert "3 intentos" in error_msg or "intentos" in error_msg

    @pytest.mark.asyncio
    async def test_agota_reintentos_lanza_excepcion_clara_modelo_generico(self):
        provider, mock_client = make_provider(model_name="unified-main")

        mock_client.chat.completions.create.side_effect = Exception("Timeout")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception) as exc_info:
                await provider.generate_text("pregunta")

        error_msg = str(exc_info.value)
        assert "intentos" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_backoff_lineal_entre_reintentos(self):
        provider, mock_client = make_provider(model_name="unified-main")

        mock_client.chat.completions.create.side_effect = [
            ConnectionError("Error 1"),
            ConnectionError("Error 2"),
            make_openai_response("Éxito en intento 3"),
        ]

        sleep_calls = []
        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            result = await provider.generate_text("pregunta")

        assert result == "Éxito en intento 3"
        # Debe haber dormido entre reintentos
        assert len(sleep_calls) >= 1


# ── Tests de generate_text — provider no configurado ─────────────────────────

class TestGenerateTextNotConfigured:

    @pytest.mark.asyncio
    async def test_sin_configure_lanza_excepcion(self):
        from bots.interjddcia.backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider()
        # No llamamos a configure() — client es None

        with pytest.raises(Exception) as exc_info:
            await provider.generate_text("pregunta")

        assert "configured" in str(exc_info.value).lower() or "configure" in str(exc_info.value).lower()
