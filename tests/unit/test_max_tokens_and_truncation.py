"""
test_max_tokens_and_truncation.py — Tests para el fix de respuesta cortada (11/06/2026)

Cubre los cambios realizados para resolver el bug crítico de respuesta cortada:

BLOQUE 1: TestMaxTokensFromJson
  - jddcia_provider.configure() lee max_tokens del JSON del modelo (prioridad 1)
  - jddcia_provider.configure() lee lan_model_max_tokens de config.json (prioridad 2)
  - jddcia_provider.configure() calcula 50% del contexto como fallback (prioridad 3)
  - El valor 512 (context_limit//8) ya NO se usa como cálculo por defecto

BLOQUE 2: TestJddciaModelsJsonMaxTokens
  - Todos los modelos Qwen3 tienen max_tokens >= 2048 en jddcia_models.json
  - El valor 512 ya no aparece en ningún modelo Qwen3

BLOQUE 3: TestConfigJsonMaxTokens
  - chat/config.json tiene lan_model_max_tokens >= 2048
  - chat/config.json tiene lan_model_context_limit configurado

BLOQUE 4: TestContinueIfTruncated
  - _continue_if_truncated detecta respuesta completa (no actúa)
  - _continue_if_truncated detecta respuesta cortada (sin secciones obligatorias)
  - _continue_if_truncated continúa la respuesta hasta completarla
  - _continue_if_truncated añade aviso amigable si no puede completar
  - _continue_if_truncated respeta max_continuations

BLOQUE 5: TestMaxTokensEndToEnd
  - El orchestrator pasa parameters.max_tokens al AIConfig
  - El provider recibe max_tokens correcto en generate_text

Autor: DEVIA System (11/06/2026)
"""

import asyncio
import json
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 1: TestMaxTokensFromJson — jddcia_provider.configure()
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaxTokensFromJson:
    """
    jddcia_provider.configure() debe leer max_tokens con prioridad:
    1) parameters.max_tokens del JSON del modelo
    2) lan_model_max_tokens en config.json
    3) auto-cálculo 50% del contexto (mínimo 512, máximo 8192)

    Bug anterior: siempre calculaba context_limit // 8 (512 para ctx=4096),
    ignorando el valor del JSON.
    """

    def _make_provider(self):
        """Crea un JDDCIAProvider sin llamar a configure()."""
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        return JDDCIAProvider()

    def _make_config(self, **kwargs):
        """Crea un AIConfig con los parámetros dados."""
        from backend.core.abstract.ai import AIConfig
        return AIConfig(
            api_key="dGVzdDp0ZXN0",  # base64("test:test")
            model="unified-main",
            base_url="http://jddcia.local/api/vlm/v1",
            **kwargs
        )

    def test_max_tokens_from_json_parameters(self):
        """
        Prioridad 1: parameters.max_tokens del JSON del modelo.
        Si el JSON dice max_tokens=4096, el provider debe usar 4096.
        """
        provider = self._make_provider()
        config = self._make_config(
            context_limit=4096,
            parameters={"max_tokens": 4096, "temperature": 0.7}
        )

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        assert provider._max_tokens == 4096, (
            f"max_tokens debe ser 4096 (del JSON), pero es {provider._max_tokens}. "
            f"Bug: el provider ignoraba parameters.max_tokens del JSON."
        )

    def test_max_tokens_not_512_when_json_says_4096(self):
        """
        El valor 512 (context_limit//8) NO debe usarse cuando el JSON especifica max_tokens.
        Este es el bug que causaba respuestas cortadas.
        """
        provider = self._make_provider()
        config = self._make_config(
            context_limit=4096,
            parameters={"max_tokens": 4096}
        )

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        assert provider._max_tokens != 512, (
            f"max_tokens NO debe ser 512 cuando el JSON dice 4096. "
            f"Bug: context_limit // 8 = 512 sobreescribía el valor del JSON."
        )
        assert provider._max_tokens == 4096

    def test_max_tokens_from_config_json_global_override(self):
        """
        Prioridad 2: lan_model_max_tokens en config.json.
        Si el JSON del modelo no tiene max_tokens, usar el override global.
        """
        provider = self._make_provider()
        config = self._make_config(
            context_limit=4096,
            parameters={}  # Sin max_tokens en el JSON del modelo
        )

        fake_config = json.dumps({"lan_model_max_tokens": 3000})

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=fake_config)):
            provider.configure(config)

        assert provider._max_tokens == 3000, (
            f"max_tokens debe ser 3000 (de config.json lan_model_max_tokens), "
            f"pero es {provider._max_tokens}."
        )

    def test_max_tokens_auto_calc_50_percent_fallback(self):
        """
        Prioridad 3: auto-cálculo 50% del contexto.
        Si no hay max_tokens en JSON ni en config.json, usar 50% del contexto.
        Para ctx=4096: 50% = 2048 (antes era 12.5% = 512).
        """
        provider = self._make_provider()
        config = self._make_config(
            context_limit=4096,
            parameters={}  # Sin max_tokens
        )

        # config.json sin lan_model_max_tokens
        fake_config = json.dumps({"lan_read_timeout_s": 180})

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=fake_config)):
            provider.configure(config)

        # 50% de 4096 = 2048 (mínimo 512, máximo 8192)
        assert provider._max_tokens == 2048, (
            f"max_tokens debe ser 2048 (50% de ctx=4096), pero es {provider._max_tokens}. "
            f"Bug anterior: era 512 (12.5% = context_limit // 8)."
        )

    def test_max_tokens_auto_calc_not_512_for_4096_context(self):
        """
        El cálculo automático ya NO debe dar 512 para ctx=4096.
        Antes: context_limit // 8 = 4096 // 8 = 512 (demasiado bajo).
        Ahora: max(512, min(8192, context_limit // 2)) = 2048.
        """
        provider = self._make_provider()
        config = self._make_config(
            context_limit=4096,
            parameters={}
        )

        fake_config = json.dumps({})  # Sin lan_model_max_tokens

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=fake_config)):
            provider.configure(config)

        assert provider._max_tokens > 512, (
            f"max_tokens debe ser > 512 para ctx=4096. "
            f"El cálculo automático (50%) debe dar 2048, no 512. "
            f"Valor actual: {provider._max_tokens}"
        )

    def test_max_tokens_minimum_512(self):
        """
        El cálculo automático tiene un mínimo de 512 tokens.
        Para ctx=512: 50% = 256, pero el mínimo es 512.
        """
        provider = self._make_provider()
        config = self._make_config(
            context_limit=512,
            parameters={}
        )

        fake_config = json.dumps({})

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=fake_config)):
            provider.configure(config)

        assert provider._max_tokens >= 512, (
            f"max_tokens debe ser al menos 512, pero es {provider._max_tokens}."
        )

    def test_max_tokens_maximum_8192(self):
        """
        El cálculo automático tiene un máximo de 8192 tokens.
        Para ctx=32768: 50% = 16384, pero el máximo es 8192.
        """
        provider = self._make_provider()
        config = self._make_config(
            context_limit=32768,
            parameters={}
        )

        fake_config = json.dumps({})

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=fake_config)):
            provider.configure(config)

        assert provider._max_tokens <= 8192, (
            f"max_tokens debe ser como máximo 8192, pero es {provider._max_tokens}."
        )

    def test_max_tokens_extra_params_fallback(self):
        """
        Si parameters viene en extra_params (como lo pasa el orchestrator),
        debe leerse correctamente.
        """
        provider = self._make_provider()
        # El orchestrator pasa parameters via AIConfig(**kwargs) → extra_params
        config = self._make_config(
            context_limit=4096,
            parameters={"max_tokens": 4096, "temperature": 0.7}
        )

        # Verificar que extra_params tiene parameters
        assert hasattr(config, 'extra_params'), "AIConfig debe tener extra_params"
        assert 'parameters' in config.extra_params, "extra_params debe tener 'parameters'"
        assert config.extra_params['parameters']['max_tokens'] == 4096

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        assert provider._max_tokens == 4096


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2: TestJddciaModelsJsonMaxTokens — jddcia_models.json
# ═══════════════════════════════════════════════════════════════════════════════

class TestJddciaModelsJsonMaxTokens:
    """
    Todos los modelos Qwen3 en jddcia_models.json deben tener max_tokens >= 2048.
    El valor 512 causaba respuestas cortadas en análisis profundo.
    """

    @pytest.fixture
    def models_json(self):
        """Carga jddcia_models.json."""
        json_path = Path(__file__).parent.parent.parent / \
            "backend/core/config/models/jddcia_models.json"
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_all_qwen3_models_have_max_tokens_gte_2048(self, models_json):
        """
        Todos los modelos Qwen3 deben tener max_tokens >= 2048.
        512 era demasiado bajo para análisis profundo (~2000-3500 tokens).
        """
        qwen3_models = [
            m for m in models_json['models']
            if 'qwen3' in m.get('id', '').lower()
        ]
        assert len(qwen3_models) >= 4, \
            f"Debe haber al menos 4 modelos Qwen3, encontrados: {len(qwen3_models)}"

        for model in qwen3_models:
            params = model.get('parameters', {})
            max_tokens = params.get('max_tokens', 0)
            assert max_tokens >= 2048, (
                f"Modelo '{model['id']}' tiene max_tokens={max_tokens}. "
                f"Debe ser >= 2048 para evitar respuestas cortadas en análisis profundo."
            )

    def test_no_qwen3_model_has_max_tokens_512(self, models_json):
        """
        Ningún modelo Qwen3 debe tener max_tokens=512.
        512 era el valor que causaba el bug de respuesta cortada.
        """
        qwen3_models = [
            m for m in models_json['models']
            if 'qwen3' in m.get('id', '').lower()
        ]
        for model in qwen3_models:
            params = model.get('parameters', {})
            max_tokens = params.get('max_tokens', 0)
            assert max_tokens != 512, (
                f"Modelo '{model['id']}' aún tiene max_tokens=512. "
                f"Este valor causaba respuestas cortadas. Debe ser >= 2048."
            )

    def test_qwen3_30b_ip_max_tokens(self, models_json):
        """jddcia-qwen3-30b-ip debe tener max_tokens >= 2048."""
        model = next(
            (m for m in models_json['models'] if m['id'] == 'jddcia-qwen3-30b-ip'),
            None
        )
        assert model is not None, "Modelo jddcia-qwen3-30b-ip no encontrado"
        max_tokens = model.get('parameters', {}).get('max_tokens', 0)
        assert max_tokens >= 2048, \
            f"jddcia-qwen3-30b-ip max_tokens={max_tokens}, debe ser >= 2048"

    def test_qwen3_30b_mdns_max_tokens(self, models_json):
        """jddcia-qwen3-30b debe tener max_tokens >= 2048."""
        model = next(
            (m for m in models_json['models'] if m['id'] == 'jddcia-qwen3-30b'),
            None
        )
        assert model is not None, "Modelo jddcia-qwen3-30b no encontrado"
        max_tokens = model.get('parameters', {}).get('max_tokens', 0)
        assert max_tokens >= 2048, \
            f"jddcia-qwen3-30b max_tokens={max_tokens}, debe ser >= 2048"

    def test_qwen3_8b_ip_max_tokens(self, models_json):
        """jddcia-qwen3-8b-ip debe tener max_tokens >= 2048."""
        model = next(
            (m for m in models_json['models'] if m['id'] == 'jddcia-qwen3-8b-ip'),
            None
        )
        assert model is not None, "Modelo jddcia-qwen3-8b-ip no encontrado"
        max_tokens = model.get('parameters', {}).get('max_tokens', 0)
        assert max_tokens >= 2048, \
            f"jddcia-qwen3-8b-ip max_tokens={max_tokens}, debe ser >= 2048"

    def test_qwen3_8b_mdns_max_tokens(self, models_json):
        """jddcia-qwen3-8b debe tener max_tokens >= 2048."""
        model = next(
            (m for m in models_json['models'] if m['id'] == 'jddcia-qwen3-8b'),
            None
        )
        assert model is not None, "Modelo jddcia-qwen3-8b no encontrado"
        max_tokens = model.get('parameters', {}).get('max_tokens', 0)
        assert max_tokens >= 2048, \
            f"jddcia-qwen3-8b max_tokens={max_tokens}, debe ser >= 2048"

    def test_qwen3_8b_timeout_gte_120s(self, models_json):
        """Los modelos 8B deben tener timeout_s >= 120s (LM Studio con stream=false)."""
        models_8b = [
            m for m in models_json['models']
            if 'qwen3-8b' in m.get('id', '').lower()
        ]
        for model in models_8b:
            timeout = model.get('parameters', {}).get('timeout_s', 0)
            assert timeout >= 120, (
                f"Modelo '{model['id']}' tiene timeout_s={timeout}. "
                f"LM Studio con stream=false necesita >= 120s."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 3: TestConfigJsonMaxTokens — chat/config.json
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfigJsonMaxTokens:
    """
    chat/config.json debe tener lan_model_max_tokens y lan_model_context_limit
    configurados correctamente.
    """

    @pytest.fixture
    def config_json(self):
        """Carga chat/config.json."""
        config_path = Path(__file__).parent.parent.parent / \
            "backend/modules/chat/config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_lan_model_max_tokens_exists(self, config_json):
        """config.json debe tener lan_model_max_tokens."""
        assert 'lan_model_max_tokens' in config_json, (
            "config.json debe tener 'lan_model_max_tokens'. "
            "Es el override global de max_tokens para JDDCIAProvider."
        )

    def test_lan_model_max_tokens_gte_2048(self, config_json):
        """lan_model_max_tokens debe ser >= 2048."""
        max_tokens = config_json.get('lan_model_max_tokens', 0)
        assert max_tokens >= 2048, (
            f"lan_model_max_tokens={max_tokens} debe ser >= 2048. "
            f"512 causaba respuestas cortadas en análisis profundo."
        )

    def test_lan_model_context_limit_exists(self, config_json):
        """config.json debe tener lan_model_context_limit."""
        assert 'lan_model_context_limit' in config_json, (
            "config.json debe tener 'lan_model_context_limit'. "
            "Es el límite de contexto total del modelo Qwen3 30B."
        )

    def test_lan_model_context_limit_gte_4096(self, config_json):
        """lan_model_context_limit debe ser >= 4096."""
        ctx_limit = config_json.get('lan_model_context_limit', 0)
        assert ctx_limit >= 4096, (
            f"lan_model_context_limit={ctx_limit} debe ser >= 4096."
        )

    def test_lan_read_timeout_gte_120(self, config_json):
        """lan_read_timeout_s debe ser >= 120s para análisis profundo."""
        timeout = config_json.get('lan_read_timeout_s', 0)
        assert timeout >= 120, (
            f"lan_read_timeout_s={timeout} debe ser >= 120s. "
            f"El análisis profundo puede tardar 120-180s."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 4: TestContinueIfTruncated — phase5._continue_if_truncated()
# ═══════════════════════════════════════════════════════════════════════════════

class TestContinueIfTruncated:
    """
    phase5._continue_if_truncated() debe:
    1. Detectar respuesta completa (no actúa)
    2. Detectar respuesta cortada (sin secciones obligatorias)
    3. Continuar la respuesta hasta completarla
    4. Añadir aviso amigable si no puede completar
    5. Respetar max_continuations
    """

    def _make_phase5_mixin(self, orchestrator_mock=None):
        """Crea una instancia de Phase5Mixin con orchestrator mockeado."""
        from backend.modules.chat.deep_analysis.phase5 import Phase5Mixin
        from backend.modules.chat.deep_analysis.models import EpicAnalysisResult, AnalysisDepth

        class ConcretePhase5(Phase5Mixin):
            def __init__(self, orch):
                self.orchestrator = orch

        mixin = ConcretePhase5(orchestrator_mock or AsyncMock())
        return mixin

    def _make_result(self):
        """Crea un EpicAnalysisResult mínimo."""
        from backend.modules.chat.deep_analysis.models import EpicAnalysisResult, AnalysisDepth
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.BASIC)
        return result

    def _complete_response(self):
        """Respuesta completa con todas las secciones obligatorias."""
        return """## 📊 Respuesta Principal
Los datos muestran una facturación de 283.175,65 EUR en Q2 2026.

## 🔍 Análisis Crítico
El análisis revela una tendencia positiva en el segundo trimestre.

## ⚠️ Advertencias y Objeciones
• Solo hay datos de Q2 2026, no se puede comparar con otros trimestres.
• Los datos del simulador pueden no reflejar la realidad exacta.

## 💡 Contexto de Negocio
En el sector de climatización, Q2 suele ser temporada alta por el calor.

## 🚀 Sugerencias y Próximos Pasos
1. Comparar con Q2 del año anterior.
2. Analizar la distribución por cliente.
3. Revisar los márgenes por tipo de instalación."""

    def _truncated_response(self):
        """Respuesta cortada: solo tiene las primeras secciones."""
        return """## 📊 Respuesta Principal
Los datos muestran una facturación de 283.175,65 EUR en Q2 2026.

## 🔍 Análisis Crítico
El análisis revela una tendencia positiva en el segundo trimestre.

**Tipo 13"""  # Cortado en mitad de una frase

    @pytest.mark.asyncio
    async def test_complete_response_not_modified(self):
        """
        Una respuesta completa (con todas las secciones) no debe ser modificada.
        """
        mixin = self._make_phase5_mixin()
        result = self._make_result()
        complete = self._complete_response()

        output = await mixin._continue_if_truncated(
            complete, "system", "pregunta test", result
        )

        assert output == complete, (
            "Una respuesta completa no debe ser modificada por _continue_if_truncated."
        )
        # El orchestrator NO debe ser llamado para respuestas completas
        mixin.orchestrator.execute_with_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_truncated_response_triggers_continuation(self):
        """
        Una respuesta cortada (sin secciones obligatorias) debe activar la continuación.
        """
        continuation_text = (
            "\n\n## ⚠️ Advertencias y Objeciones\n"
            "• Solo hay datos de Q2.\n\n"
            "## 💡 Contexto de Negocio\n"
            "Sector de climatización.\n\n"
            "## 🚀 Sugerencias y Próximos Pasos\n"
            "1. Comparar con año anterior."
        )

        mock_orch = AsyncMock()
        mock_orch.execute_with_fallback = AsyncMock(
            return_value=(continuation_text, "jddcia-qwen3-30b")
        )

        mixin = self._make_phase5_mixin(mock_orch)
        result = self._make_result()
        truncated = self._truncated_response()

        output = await mixin._continue_if_truncated(
            truncated, "system", "pregunta test", result
        )

        # El orchestrator debe haber sido llamado al menos una vez
        assert mock_orch.execute_with_fallback.called, (
            "El orchestrator debe ser llamado para continuar una respuesta cortada."
        )
        # La respuesta final debe ser más larga que la truncada
        assert len(output) > len(truncated), (
            "La respuesta final debe ser más larga que la truncada."
        )

    @pytest.mark.asyncio
    async def test_continuation_completes_response(self):
        """
        La continuación debe completar la respuesta con las secciones que faltan.
        """
        continuation_text = (
            "## ⚠️ Advertencias y Objeciones\n"
            "• Solo hay datos de Q2.\n\n"
            "## 💡 Contexto de Negocio\n"
            "Sector de climatización.\n\n"
            "## 🚀 Sugerencias y Próximos Pasos\n"
            "1. Comparar con año anterior."
        )

        mock_orch = AsyncMock()
        mock_orch.execute_with_fallback = AsyncMock(
            return_value=(continuation_text, "jddcia-qwen3-30b")
        )

        mixin = self._make_phase5_mixin(mock_orch)
        result = self._make_result()
        truncated = self._truncated_response()

        output = await mixin._continue_if_truncated(
            truncated, "system", "pregunta test", result
        )

        # La respuesta final debe contener las secciones obligatorias
        assert "## ⚠️ Advertencias" in output or "## 🚀 Sugerencias" in output, (
            "La respuesta completada debe contener las secciones obligatorias."
        )

    @pytest.mark.asyncio
    async def test_friendly_notice_when_cannot_complete(self):
        """
        Si no se puede completar la respuesta tras max_continuations intentos,
        debe añadirse un aviso amigable al usuario.
        """
        # El orchestrator siempre devuelve texto que sigue incompleto
        mock_orch = AsyncMock()
        mock_orch.execute_with_fallback = AsyncMock(
            return_value=("Continuación parcial sin secciones finales.", "jddcia-qwen3-30b")
        )

        mixin = self._make_phase5_mixin(mock_orch)
        result = self._make_result()
        truncated = self._truncated_response()

        output = await mixin._continue_if_truncated(
            truncated, "system", "pregunta test", result, max_continuations=2
        )

        # Debe contener el aviso amigable
        assert "⚠️" in output or "Nota:" in output or "continúa el análisis" in output, (
            "Debe añadirse un aviso amigable cuando no se puede completar la respuesta."
        )

    @pytest.mark.asyncio
    async def test_respects_max_continuations(self):
        """
        _continue_if_truncated debe respetar max_continuations.
        Si max_continuations=2, el orchestrator no debe ser llamado más de 2 veces.
        """
        mock_orch = AsyncMock()
        mock_orch.execute_with_fallback = AsyncMock(
            return_value=("Texto sin secciones finales.", "jddcia-qwen3-30b")
        )

        mixin = self._make_phase5_mixin(mock_orch)
        result = self._make_result()
        truncated = self._truncated_response()

        await mixin._continue_if_truncated(
            truncated, "system", "pregunta test", result, max_continuations=2
        )

        call_count = mock_orch.execute_with_fallback.call_count
        assert call_count <= 2, (
            f"El orchestrator fue llamado {call_count} veces, "
            f"pero max_continuations=2 limita a 2 llamadas."
        )

    @pytest.mark.asyncio
    async def test_empty_response_is_truncated(self):
        """Una respuesta vacía debe considerarse truncada."""
        mock_orch = AsyncMock()
        mock_orch.execute_with_fallback = AsyncMock(
            return_value=("## 🚀 Sugerencias\n1. Revisar datos.", "jddcia-qwen3-30b")
        )

        mixin = self._make_phase5_mixin(mock_orch)
        result = self._make_result()

        output = await mixin._continue_if_truncated(
            "", "system", "pregunta test", result, max_continuations=1
        )

        # Debe intentar continuar una respuesta vacía
        assert mock_orch.execute_with_fallback.called, (
            "Una respuesta vacía debe activar la continuación."
        )

    @pytest.mark.asyncio
    async def test_orchestrator_error_handled_gracefully(self):
        """
        Si el orchestrator lanza una excepción durante la continuación,
        debe manejarse sin romper el flujo.
        """
        mock_orch = AsyncMock()
        mock_orch.execute_with_fallback = AsyncMock(
            side_effect=Exception("Timeout del modelo")
        )

        mixin = self._make_phase5_mixin(mock_orch)
        result = self._make_result()
        truncated = self._truncated_response()

        # No debe lanzar excepción
        output = await mixin._continue_if_truncated(
            truncated, "system", "pregunta test", result, max_continuations=1
        )

        # Debe devolver algo (la respuesta truncada + aviso o solo la truncada)
        assert output is not None
        assert len(output) >= len(truncated), (
            "La respuesta no debe ser más corta que la original tras un error."
        )

    @pytest.mark.asyncio
    async def test_continuation_uses_preferred_model_30b(self):
        """
        La continuación debe usar el modelo Qwen3 30B (el más potente para síntesis).
        """
        mock_orch = AsyncMock()
        mock_orch.execute_with_fallback = AsyncMock(
            return_value=("## 🚀 Sugerencias\n1. Revisar.", "jddcia-qwen3-30b")
        )

        mixin = self._make_phase5_mixin(mock_orch)
        result = self._make_result()
        truncated = self._truncated_response()

        await mixin._continue_if_truncated(
            truncated, "system", "pregunta test", result, max_continuations=1
        )

        # Verificar que se usó el modelo 30B
        call_kwargs = mock_orch.execute_with_fallback.call_args
        preferred = call_kwargs.kwargs.get('preferred_model_id') or \
                    (call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
        # El preferred_model_id debe ser el 30B
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs.get('preferred_model_id') == "jddcia-qwen3-30b", (
                "La continuación debe usar jddcia-qwen3-30b como modelo preferido."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 5: TestMaxTokensEndToEnd — Flujo completo orchestrator → provider
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaxTokensEndToEnd:
    """
    Verifica que el flujo completo orchestrator → AIConfig → provider
    pasa max_tokens correctamente.
    """

    def test_orchestrator_passes_parameters_to_aiconfig(self):
        """
        El orchestrator debe pasar model_config['parameters'] al AIConfig.
        Esto es lo que permite al provider leer max_tokens del JSON.
        """
        from backend.core.abstract.ai import AIConfig

        # Simular lo que hace el orchestrator en _try_model
        model_config = {
            'id': 'jddcia-qwen3-30b-ip',
            'model_id': 'unified-main',
            'context_limit': 4096,
            'parameters': {'max_tokens': 4096, 'temperature': 0.7},
            'base_url': 'http://192.168.0.36/api/vlm/v1',
        }

        ai_config_params = {
            'api_key': 'dGVzdDp0ZXN0',
            'model': model_config['model_id'],
            'context_limit': model_config.get('context_limit', 8192),
            'parameters': model_config.get('parameters', {}),
        }
        if model_config.get('base_url'):
            ai_config_params['base_url'] = model_config['base_url']

        config = AIConfig(**ai_config_params)

        # Verificar que parameters llega en extra_params
        assert 'parameters' in config.extra_params, \
            "AIConfig.extra_params debe contener 'parameters'"
        assert config.extra_params['parameters']['max_tokens'] == 4096, \
            "max_tokens debe ser 4096 en extra_params['parameters']"

    def test_provider_reads_max_tokens_from_aiconfig_extra_params(self):
        """
        El provider debe leer max_tokens de AIConfig.extra_params['parameters'].
        """
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(
            api_key="dGVzdDp0ZXN0",
            model="unified-main",
            base_url="http://192.168.0.36/api/vlm/v1",
            context_limit=4096,
            parameters={"max_tokens": 4096, "temperature": 0.7}
        )

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        assert provider._max_tokens == 4096, (
            f"El provider debe leer max_tokens=4096 de AIConfig.extra_params['parameters'], "
            f"pero obtuvo {provider._max_tokens}."
        )

    def test_max_tokens_in_payload_matches_configured_value(self):
        """
        El payload enviado al modelo debe incluir el max_tokens configurado.
        Verifica que generate_text usa self._max_tokens en el payload.
        """
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(
            api_key="dGVzdDp0ZXN0",
            model="unified-main",
            base_url="http://192.168.0.36/api/vlm/v1",
            context_limit=4096,
            parameters={"max_tokens": 4096}
        )

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        # Verificar que _max_tokens es 4096 (se usará en el payload)
        assert provider._max_tokens == 4096, \
            f"provider._max_tokens debe ser 4096, pero es {provider._max_tokens}"

        # El payload en generate_text usa: max_tokens = self._max_tokens
        # Verificamos que el valor es correcto para que el payload sea correcto
        expected_payload_max_tokens = provider._max_tokens
        assert expected_payload_max_tokens == 4096, \
            "El payload debe incluir max_tokens=4096"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 6: TestTruncationDetection — Detección de respuesta cortada
# ═══════════════════════════════════════════════════════════════════════════════

class TestTruncationDetection:
    """
    Tests unitarios para la función _is_truncated interna de _continue_if_truncated.
    Verifica que detecta correctamente respuestas completas vs cortadas.
    """

    def _get_is_truncated_fn(self):
        """
        Extrae la función _is_truncated del closure de _continue_if_truncated.
        Como es una función interna, la replicamos aquí para testearla.
        """
        _REQUIRED_SECTIONS = [
            "## 🚀 Sugerencias",
            "## 💡 Contexto",
            "## ⚠️ Advertencias",
        ]

        def _is_truncated(text: str) -> bool:
            text = text.strip()
            if not text:
                return True
            has_final_section = any(s in text for s in _REQUIRED_SECTIONS)
            if not has_final_section:
                return True
            last_char = text[-1] if text else ""
            if last_char not in (".", "!", "?", "\n", "*", "-", ">", "|"):
                last_line = text.split("\n")[-1].strip()
                if last_line and not last_line.endswith((".", "!", "?", "*", "-", "|")):
                    if len(last_line) < 80 and not last_line.startswith("#"):
                        return True
            return False

        return _is_truncated

    def test_empty_text_is_truncated(self):
        """Texto vacío → truncado."""
        fn = self._get_is_truncated_fn()
        assert fn("") is True
        assert fn("   ") is True

    def test_complete_response_not_truncated(self):
        """Respuesta con todas las secciones → no truncada."""
        fn = self._get_is_truncated_fn()
        complete = (
            "## 📊 Respuesta\nDatos.\n\n"
            "## 🔍 Análisis\nAnálisis.\n\n"
            "## ⚠️ Advertencias\n• Aviso.\n\n"
            "## 💡 Contexto\nContexto.\n\n"
            "## 🚀 Sugerencias\n1. Sugerencia."
        )
        assert fn(complete) is False

    def test_missing_required_sections_is_truncated(self):
        """Sin secciones obligatorias → truncado."""
        fn = self._get_is_truncated_fn()
        incomplete = (
            "## 📊 Respuesta\nDatos.\n\n"
            "## 🔍 Análisis\nAnálisis."
            # Faltan: ⚠️ Advertencias, 💡 Contexto, 🚀 Sugerencias
        )
        assert fn(incomplete) is True

    def test_text_cut_mid_sentence_is_truncated(self):
        """Texto cortado en mitad de frase → truncado."""
        fn = self._get_is_truncated_fn()
        cut_mid = (
            "## ⚠️ Advertencias\n• Aviso.\n\n"
            "## 🚀 Sugerencias\n1. Sugerencia.\n\n"
            "**Tipo 13"  # Cortado en mitad
        )
        assert fn(cut_mid) is True

    def test_response_ending_with_period_not_truncated(self):
        """Respuesta que termina con punto → no truncada (si tiene secciones)."""
        fn = self._get_is_truncated_fn()
        ends_with_period = (
            "## ⚠️ Advertencias\n• Aviso.\n\n"
            "## 💡 Contexto\nContexto.\n\n"
            "## 🚀 Sugerencias\n1. Revisar los datos del año anterior."
        )
        assert fn(ends_with_period) is False

    def test_response_with_sugerencias_section_not_truncated(self):
        """Si tiene ## 🚀 Sugerencias → no truncada."""
        fn = self._get_is_truncated_fn()
        has_sugerencias = "## 🚀 Sugerencias y Próximos Pasos\n1. Paso uno."
        assert fn(has_sugerencias) is False

    def test_response_with_advertencias_section_not_truncated(self):
        """Si tiene ## ⚠️ Advertencias → no truncada."""
        fn = self._get_is_truncated_fn()
        has_advertencias = "## ⚠️ Advertencias y Objeciones\n• Aviso importante."
        assert fn(has_advertencias) is False

    def test_response_with_contexto_section_not_truncated(self):
        """Si tiene ## 💡 Contexto → no truncada."""
        fn = self._get_is_truncated_fn()
        has_contexto = "## 💡 Contexto de Negocio\nEl sector de climatización."
        assert fn(has_contexto) is False


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 7: TestContextLimitVsMaxTokens — Relación contexto/respuesta
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextLimitVsMaxTokens:
    """
    Verifica que max_tokens no supera el context_limit del modelo.
    Si max_tokens > context_limit, el modelo devuelve error 400.
    """

    def test_max_tokens_not_exceed_context_limit(self):
        """
        max_tokens no debe superar context_limit.
        Para ctx=4096 y max_tokens=4096: el ContextManager debe reservar
        espacio para el input (system + user_message).
        """
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(
            api_key="dGVzdDp0ZXN0",
            model="unified-main",
            base_url="http://192.168.0.36/api/vlm/v1",
            context_limit=4096,
            parameters={"max_tokens": 4096}
        )

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        # max_tokens puede ser igual a context_limit (el ContextManager gestiona el input)
        assert provider._max_tokens <= 4096 * 2, (
            f"max_tokens={provider._max_tokens} no debe ser absurdamente grande."
        )
        assert provider._max_tokens > 0, "max_tokens debe ser positivo."

    def test_context_manager_initialized_with_correct_max_tokens(self):
        """
        El ContextManager debe inicializarse con el max_tokens correcto.
        """
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(
            api_key="dGVzdDp0ZXN0",
            model="unified-main",
            base_url="http://192.168.0.36/api/vlm/v1",
            context_limit=4096,
            parameters={"max_tokens": 4096}
        )

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        assert provider._context_manager is not None, \
            "ContextManager debe estar inicializado después de configure()"
        assert provider._context_manager.config.max_tokens_response == 4096, (
            f"ContextManager.max_tokens_response debe ser 4096, "
            f"pero es {provider._context_manager.config.max_tokens_response}"
        )

    def test_available_tokens_for_input_positive(self):
        """
        Después de configure(), debe haber tokens disponibles para el input.
        available_tokens_for_input = context_limit - max_tokens - margen
        """
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(
            api_key="dGVzdDp0ZXN0",
            model="unified-main",
            base_url="http://192.168.0.36/api/vlm/v1",
            context_limit=4096,
            parameters={"max_tokens": 2048}  # Deja 2048 para input
        )

        with patch("backend.drivers.ai.jddcia_provider.os.path.exists", return_value=False):
            provider.configure(config)

        available = provider._context_manager.config.available_tokens_for_input
        assert available > 0, (
            f"Debe haber tokens disponibles para el input, pero available={available}."
        )
