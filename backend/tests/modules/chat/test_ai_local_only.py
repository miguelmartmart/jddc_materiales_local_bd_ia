"""
Tests para el modo AI_LOCAL_ONLY del ModelFallbackOrchestrator.

Verifica que cuando ai_local_only=true:
  - NUNCA se ejecuta ningún modelo externo (Groq, Gemini, OpenAI, etc.)
  - SOLO se usan modelos con ID en LOCAL_MODEL_IDS (jddcia-qwen3-30b, jddcia-qwen3-30b-ip)
  - Si no hay modelos locales habilitados, devuelve (None, None) sin intentar internet
  - El flag se lee en cada llamada (sin reiniciar el servidor)
  - Si ai_local_only=false, el fallback completo funciona normalmente

Autor: DEVIA System Tests
"""

import pytest
import json
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
from typing import Dict, Any, List, Optional

from backend.modules.chat.model_fallback_orchestrator import (
    ModelFallbackOrchestrator,
    LOCAL_MODEL_IDS,
    _load_ai_local_only,
)


# ---------------------------------------------------------------------------
# Datos de prueba: modelos simulados
# ---------------------------------------------------------------------------

def _make_local_model(model_id: str = "jddcia-qwen3-30b") -> Dict[str, Any]:
    """Crea un modelo local simulado (Qwen3 LAN)."""
    return {
        "id": model_id,
        "name": "Qwen3 VL 30B (JDDC LAN)",
        "model_id": "unified-main",
        "schema": None,  # Los modelos jddcia tienen schema=None
        "provider": "jddcia",
        "api_key": "YWRtaW46YWlzdGFjazIwMjY=",
        "base_url": "http://jddcia.local/api/vlm/v1",
        "headers": {"Authorization": "Basic YWRtaW46YWlzdGFjazIwMjY="},
        "enabled": True,
        "score": 100,
    }


def _make_external_model(model_id: str = "groq-llama-70b", name: str = "Groq LLaMA 70B") -> Dict[str, Any]:
    """Crea un modelo externo simulado (internet)."""
    return {
        "id": model_id,
        "name": name,
        "model_id": "llama-3.3-70b-versatile",
        "schema": "groq",
        "provider": "groq",
        "api_key": "gsk_fake_key_for_testing",
        "base_url": None,
        "headers": None,
        "enabled": True,
        "score": 80,
    }


# Lista mixta: local + externos
MIXED_MODELS = [
    _make_local_model("jddcia-qwen3-30b"),
    _make_external_model("groq-llama-70b", "Groq LLaMA 70B"),
    _make_external_model("gemini-flash", "Gemini 1.5 Flash"),
    _make_external_model("openai-gpt4o", "OpenAI GPT-4o"),
    _make_external_model("deepseek-v3", "DeepSeek V3"),
]

ONLY_LOCAL_MODELS = [
    _make_local_model("jddcia-qwen3-30b"),
    _make_local_model("jddcia-qwen3-30b-ip"),
]

ONLY_EXTERNAL_MODELS = [
    _make_external_model("groq-llama-70b"),
    _make_external_model("gemini-flash"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orchestrator():
    """Crea un ModelFallbackOrchestrator con ModelManager mockeado."""
    with patch("backend.modules.chat.model_fallback_orchestrator.ModelManager") as mock_mm_class:
        mock_mm = MagicMock()
        mock_mm_class.return_value = mock_mm
        orch = ModelFallbackOrchestrator()
        orch.model_manager = mock_mm
        yield orch, mock_mm


# ---------------------------------------------------------------------------
# Tests: _load_ai_local_only
# ---------------------------------------------------------------------------

class TestLoadAiLocalOnly:
    """Tests para la función _load_ai_local_only que lee el config.json."""

    def test_devuelve_true_cuando_config_tiene_true(self, tmp_path):
        """Verifica que devuelve True cuando ai_local_only=true en config.json."""
        config = {"ai_local_only": True, "max_sql_retries": 4}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        with patch("backend.modules.chat.model_fallback_orchestrator.os.path.dirname",
                   return_value=str(tmp_path)):
            with patch("backend.modules.chat.model_fallback_orchestrator.os.path.join",
                       return_value=str(config_file)):
                result = _load_ai_local_only()
        assert result is True

    def test_devuelve_false_cuando_config_tiene_false(self, tmp_path):
        """Verifica que devuelve False cuando ai_local_only=false en config.json."""
        config = {"ai_local_only": False, "max_sql_retries": 4}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        with patch("backend.modules.chat.model_fallback_orchestrator.os.path.dirname",
                   return_value=str(tmp_path)):
            with patch("backend.modules.chat.model_fallback_orchestrator.os.path.join",
                       return_value=str(config_file)):
                result = _load_ai_local_only()
        assert result is False

    def test_devuelve_false_cuando_campo_no_existe(self, tmp_path):
        """Verifica que devuelve False (seguro) cuando el campo no existe en config."""
        config = {"max_sql_retries": 4}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        with patch("backend.modules.chat.model_fallback_orchestrator.os.path.dirname",
                   return_value=str(tmp_path)):
            with patch("backend.modules.chat.model_fallback_orchestrator.os.path.join",
                       return_value=str(config_file)):
                result = _load_ai_local_only()
        assert result is False

    def test_devuelve_false_cuando_archivo_no_existe(self, tmp_path):
        """Verifica que devuelve False cuando config.json no existe."""
        nonexistent = str(tmp_path / "nonexistent.json")
        with patch("backend.modules.chat.model_fallback_orchestrator.os.path.join",
                   return_value=nonexistent):
            result = _load_ai_local_only()
        assert result is False

    def test_devuelve_false_cuando_json_invalido(self, tmp_path):
        """Verifica que devuelve False (sin crash) cuando config.json tiene JSON inválido."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ esto no es json válido }")

        with patch("backend.modules.chat.model_fallback_orchestrator.os.path.join",
                   return_value=str(config_file)):
            result = _load_ai_local_only()
        assert result is False


# ---------------------------------------------------------------------------
# Tests: LOCAL_MODEL_IDS — constante de modelos locales
# ---------------------------------------------------------------------------

class TestLocalModelIds:
    """Tests para verificar que LOCAL_MODEL_IDS contiene los modelos correctos."""

    def test_contiene_modelo_mdns(self):
        """Verifica que el modelo mDNS (jddcia.local) está en LOCAL_MODEL_IDS."""
        assert "jddcia-qwen3-30b" in LOCAL_MODEL_IDS

    def test_contiene_modelo_ip_directa(self):
        """Verifica que el modelo IP directa está en LOCAL_MODEL_IDS."""
        assert "jddcia-qwen3-30b-ip" in LOCAL_MODEL_IDS

    def test_no_contiene_modelos_externos(self):
        """Verifica que ningún modelo externo está en LOCAL_MODEL_IDS."""
        external_ids = [
            "groq-llama-70b", "gemini-flash", "openai-gpt4o",
            "deepseek-v3", "claude-3-5-sonnet", "mistral-large",
            "cohere-command-r", "together-llama", "fireworks-llama",
        ]
        for ext_id in external_ids:
            assert ext_id not in LOCAL_MODEL_IDS, \
                f"Modelo externo '{ext_id}' NO debería estar en LOCAL_MODEL_IDS"

    def test_es_un_set(self):
        """Verifica que LOCAL_MODEL_IDS es un set (búsqueda O(1))."""
        assert isinstance(LOCAL_MODEL_IDS, set)


# ---------------------------------------------------------------------------
# Tests: execute_with_fallback con ai_local_only=True
# ---------------------------------------------------------------------------

class TestAiLocalOnlyTrue:
    """
    Tests que verifican que con ai_local_only=True NUNCA se ejecuta
    ningún modelo externo (Groq, Gemini, OpenAI, etc.).
    """

    @pytest.mark.asyncio
    async def test_solo_usa_modelo_local_cuando_hay_mixtos(self, orchestrator):
        """
        Con ai_local_only=True y lista mixta de modelos,
        SOLO debe intentar el modelo local, NUNCA los externos.
        """
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS

        modelos_intentados = []

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            modelos_intentados.append(model_config["id"])
            if model_config["id"] in LOCAL_MODEL_IDS:
                return "Respuesta del modelo local"
            return None

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            response, model_id = await orch.execute_with_fallback(
                system_prompt="Eres un asistente SQL",
                user_message="cuantos articulos hay"
            )

        # Solo debe haber intentado el modelo local
        assert response == "Respuesta del modelo local"
        assert model_id == "jddcia-qwen3-30b"
        assert len(modelos_intentados) == 1
        assert modelos_intentados[0] == "jddcia-qwen3-30b"

        # NUNCA debe haber intentado modelos externos
        externos_intentados = [m for m in modelos_intentados if m not in LOCAL_MODEL_IDS]
        assert externos_intentados == [], \
            f"Se intentaron modelos externos cuando no debería: {externos_intentados}"

    @pytest.mark.asyncio
    async def test_nunca_intenta_groq_cuando_local_only(self, orchestrator):
        """Verifica específicamente que Groq NUNCA se intenta con ai_local_only=True."""
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS

        groq_intentado = False

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            nonlocal groq_intentado
            if "groq" in model_config["id"]:
                groq_intentado = True
            if model_config["id"] in LOCAL_MODEL_IDS:
                return "ok"
            return None

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            await orch.execute_with_fallback("system", "mensaje")

        assert not groq_intentado, "Groq NO debe intentarse cuando ai_local_only=True"

    @pytest.mark.asyncio
    async def test_nunca_intenta_gemini_cuando_local_only(self, orchestrator):
        """Verifica específicamente que Gemini NUNCA se intenta con ai_local_only=True."""
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS

        gemini_intentado = False

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            nonlocal gemini_intentado
            if "gemini" in model_config["id"]:
                gemini_intentado = True
            if model_config["id"] in LOCAL_MODEL_IDS:
                return "ok"
            return None

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            await orch.execute_with_fallback("system", "mensaje")

        assert not gemini_intentado, "Gemini NO debe intentarse cuando ai_local_only=True"

    @pytest.mark.asyncio
    async def test_nunca_intenta_openai_cuando_local_only(self, orchestrator):
        """Verifica específicamente que OpenAI NUNCA se intenta con ai_local_only=True."""
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS

        openai_intentado = False

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            nonlocal openai_intentado
            if "openai" in model_config["id"]:
                openai_intentado = True
            if model_config["id"] in LOCAL_MODEL_IDS:
                return "ok"
            return None

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            await orch.execute_with_fallback("system", "mensaje")

        assert not openai_intentado, "OpenAI NO debe intentarse cuando ai_local_only=True"

    @pytest.mark.asyncio
    async def test_devuelve_none_none_si_no_hay_modelos_locales_habilitados(self, orchestrator):
        """
        Con ai_local_only=True pero sin modelos locales habilitados,
        debe devolver (None, None) SIN intentar modelos externos.
        """
        orch, mock_mm = orchestrator
        # Solo hay modelos externos disponibles
        mock_mm.list_models.return_value = ONLY_EXTERNAL_MODELS

        modelos_intentados = []

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            modelos_intentados.append(model_config["id"])
            return "respuesta externa"

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            response, model_id = await orch.execute_with_fallback("system", "mensaje")

        assert response is None
        assert model_id is None
        # NUNCA debe haber intentado ningún modelo
        assert modelos_intentados == [], \
            f"No debería haber intentado ningún modelo, pero intentó: {modelos_intentados}"

    @pytest.mark.asyncio
    async def test_devuelve_none_none_si_no_hay_modelos_disponibles(self, orchestrator):
        """Con ai_local_only=True y lista vacía de modelos, devuelve (None, None)."""
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = []

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            response, model_id = await orch.execute_with_fallback("system", "mensaje")

        assert response is None
        assert model_id is None

    @pytest.mark.asyncio
    async def test_usa_ambos_modelos_locales_si_el_primero_falla(self, orchestrator):
        """
        Con ai_local_only=True y dos modelos locales,
        si el primero falla debe intentar el segundo (también local).
        """
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = ONLY_LOCAL_MODELS
        orch.max_retries_per_model = 0  # Sin reintentos para simplificar

        modelos_intentados = []

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            modelos_intentados.append(model_config["id"])
            if model_config["id"] == "jddcia-qwen3-30b":
                return None  # Primer modelo falla
            if model_config["id"] == "jddcia-qwen3-30b-ip":
                return "Respuesta del modelo IP"  # Segundo modelo funciona
            return None

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            response, model_id = await orch.execute_with_fallback("system", "mensaje")

        assert response == "Respuesta del modelo IP"
        assert model_id == "jddcia-qwen3-30b-ip"
        # Solo modelos locales intentados
        for m in modelos_intentados:
            assert m in LOCAL_MODEL_IDS, f"Modelo externo '{m}' no debería haberse intentado"

    @pytest.mark.asyncio
    async def test_devuelve_none_si_modelo_local_falla_sin_fallback_externo(self, orchestrator):
        """
        Con ai_local_only=True, si el modelo local falla,
        NO debe hacer fallback a modelos externos. Devuelve (None, None).
        """
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS
        orch.max_retries_per_model = 0

        modelos_intentados = []

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            modelos_intentados.append(model_config["id"])
            return None  # Todos fallan

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            response, model_id = await orch.execute_with_fallback("system", "mensaje")

        assert response is None
        assert model_id is None
        # Solo debe haber intentado modelos locales
        externos = [m for m in modelos_intentados if m not in LOCAL_MODEL_IDS]
        assert externos == [], \
            f"Se intentaron modelos externos cuando no debería: {externos}"

    @pytest.mark.asyncio
    async def test_flag_se_lee_en_cada_llamada(self, orchestrator):
        """
        Verifica que el flag ai_local_only se lee en cada llamada,
        permitiendo cambio dinámico sin reiniciar el servidor.
        """
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS
        orch.max_retries_per_model = 0

        modelos_primera_llamada = []
        modelos_segunda_llamada = []
        llamada_num = [0]

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            if llamada_num[0] == 0:
                modelos_primera_llamada.append(model_config["id"])
            else:
                modelos_segunda_llamada.append(model_config["id"])
            return "ok"

        orch._try_model = mock_try_model

        # Primera llamada: ai_local_only=True → solo local
        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=True):
            await orch.execute_with_fallback("system", "mensaje1")

        llamada_num[0] = 1

        # Segunda llamada: ai_local_only=False → todos los modelos
        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=False):
            await orch.execute_with_fallback("system", "mensaje2")

        # Primera llamada: solo modelos locales
        assert all(m in LOCAL_MODEL_IDS for m in modelos_primera_llamada), \
            f"Primera llamada usó modelos externos: {modelos_primera_llamada}"

        # Segunda llamada: el primer modelo intentado puede ser cualquiera (fallback completo)
        # Solo verificamos que se intentó al menos un modelo
        assert len(modelos_segunda_llamada) >= 1


# ---------------------------------------------------------------------------
# Tests: execute_with_fallback con ai_local_only=False
# ---------------------------------------------------------------------------

class TestAiLocalOnlyFalse:
    """
    Tests que verifican que con ai_local_only=False el fallback
    completo funciona normalmente (puede usar modelos externos).
    """

    @pytest.mark.asyncio
    async def test_usa_todos_los_modelos_cuando_local_only_false(self, orchestrator):
        """Con ai_local_only=False, todos los modelos están disponibles."""
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS
        orch.max_retries_per_model = 0

        modelos_disponibles = []

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            modelos_disponibles.append(model_config["id"])
            return "ok"

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=False):
            response, model_id = await orch.execute_with_fallback("system", "mensaje")

        # Con fallback completo, el primer modelo de la lista se intenta
        assert response == "ok"
        assert len(modelos_disponibles) >= 1

    @pytest.mark.asyncio
    async def test_puede_usar_groq_cuando_local_only_false(self, orchestrator):
        """Con ai_local_only=False, Groq puede usarse como fallback."""
        orch, mock_mm = orchestrator
        # Solo Groq disponible (sin modelos locales)
        mock_mm.list_models.return_value = [_make_external_model("groq-llama-70b")]
        orch.max_retries_per_model = 0

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            return "Respuesta de Groq"

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=False):
            response, model_id = await orch.execute_with_fallback("system", "mensaje")

        assert response == "Respuesta de Groq"
        assert model_id == "groq-llama-70b"

    @pytest.mark.asyncio
    async def test_fallback_a_externo_cuando_local_falla_y_local_only_false(self, orchestrator):
        """Con ai_local_only=False, si el local falla hace fallback a externo."""
        orch, mock_mm = orchestrator
        mock_mm.list_models.return_value = MIXED_MODELS
        orch.max_retries_per_model = 0

        async def mock_try_model(model_config, system_prompt, user_message, images=None, attempt=1):
            if model_config["id"] in LOCAL_MODEL_IDS:
                return None  # Local falla
            return "Respuesta externa"  # Externo funciona

        orch._try_model = mock_try_model

        with patch("backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
                   return_value=False):
            response, model_id = await orch.execute_with_fallback("system", "mensaje")

        assert response == "Respuesta externa"
        assert model_id not in LOCAL_MODEL_IDS
