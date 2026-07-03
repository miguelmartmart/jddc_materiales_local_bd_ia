"""
test_context_manager.py — Tests del ContextManager inteligente.

Cubre:
  1. ContextManagerConfig — cálculos de tokens disponibles
  2. ContextManager.estimate_tokens() — estimación de tokens
  3. ContextManager.fits() — comprobación de si cabe
  4. ContextManager.fit() — compresión con IA (mock) y truncado
  5. ContextManager._truncate() — truncado inteligente
  6. ContextManager._compress_with_ai() — compresión con IA mock
  7. ContextManager.disabled() — modo no-op
  8. ContextManager.for_model() — factory method
  9. Integración: flujo completo con IA mock que falla → truncado
  10. Integración: flujo completo con IA mock que comprime en 1 ronda
  11. Integración: flujo completo con IA mock que necesita 2 rondas

Ejecutar:
  cd bots/interjddcia
  python -X utf8 -m pytest backend/core/context/test_context_manager.py -v

AUTOR: DEVIA System
"""

import asyncio
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

from backend.core.context.context_manager import (
    ContextManager,
    ContextManagerConfig,
    _DEFAULT_CHARS_PER_TOKEN,
    _DEFAULT_SAFETY_MARGIN_TOKENS,
    _DEFAULT_MAX_COMPRESSION_ROUNDS,
    _MIN_USER_MESSAGE_TOKENS,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_text(tokens: int, chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN) -> str:
    """Genera un texto de exactamente N tokens (aproximado)."""
    chars = int(tokens * chars_per_token)
    # Usar palabras de 4 chars + espacio = 5 chars/palabra ≈ 1.25 tokens/palabra
    word = "test"
    words_needed = max(1, chars // (len(word) + 1))
    return (word + " ") * words_needed


def make_config(
    context_limit: int = 4096,
    max_tokens_response: int = 512,
    safety_margin: int = 100,
    max_rounds: int = 3,
    compression_ratio: float = 0.6,
) -> ContextManagerConfig:
    return ContextManagerConfig(
        model_context_limit=context_limit,
        max_tokens_response=max_tokens_response,
        safety_margin_tokens=safety_margin,
        max_compression_rounds=max_rounds,
        compression_ratio=compression_ratio,
    )


# ─── Tests: ContextManagerConfig ──────────────────────────────────────────────

class TestContextManagerConfig:

    def test_available_tokens_for_input_basic(self):
        """Tokens disponibles = límite - respuesta - margen."""
        cfg = make_config(context_limit=4096, max_tokens_response=512, safety_margin=100)
        expected = 4096 - 512 - 100  # = 3484
        assert cfg.available_tokens_for_input == expected

    def test_available_tokens_never_below_minimum(self):
        """Nunca devuelve menos que _MIN_USER_MESSAGE_TOKENS."""
        cfg = make_config(context_limit=100, max_tokens_response=90, safety_margin=20)
        # 100 - 90 - 20 = -10 → debe devolver _MIN_USER_MESSAGE_TOKENS
        assert cfg.available_tokens_for_input == _MIN_USER_MESSAGE_TOKENS

    def test_available_chars_for_input(self):
        """Chars disponibles = tokens disponibles × chars_per_token."""
        cfg = make_config(context_limit=4096, max_tokens_response=512, safety_margin=100)
        expected_tokens = 4096 - 512 - 100  # 3484
        expected_chars = int(expected_tokens * _DEFAULT_CHARS_PER_TOKEN)
        assert cfg.available_chars_for_input == expected_chars

    def test_enabled_default_true(self):
        cfg = ContextManagerConfig()
        assert cfg.enabled is True

    def test_disabled_config(self):
        cfg = ContextManagerConfig(enabled=False)
        assert cfg.enabled is False


# ─── Tests: estimate_tokens ───────────────────────────────────────────────────

class TestEstimateTokens:

    def setup_method(self):
        self.manager = ContextManager(make_config())

    def test_empty_string(self):
        assert self.manager.estimate_tokens("") == 1  # max(1, ...)

    def test_none_handled(self):
        # None no se pasa directamente, pero si se pasa texto vacío
        assert self.manager.estimate_tokens("", "") == 1

    def test_single_text(self):
        text = "a" * 400  # 400 chars / 4.0 = 100 tokens
        assert self.manager.estimate_tokens(text) == 100

    def test_multiple_texts(self):
        t1 = "a" * 400   # 100 tokens
        t2 = "b" * 800   # 200 tokens
        assert self.manager.estimate_tokens(t1, t2) == 300

    def test_ceiling_applied(self):
        text = "a" * 5   # 5 / 4.0 = 1.25 → ceil = 2
        assert self.manager.estimate_tokens(text) == 2


# ─── Tests: fits ──────────────────────────────────────────────────────────────

class TestFits:

    def setup_method(self):
        # 4096 ctx, 512 respuesta, 100 margen → 3484 tokens disponibles
        self.manager = ContextManager(make_config())

    def test_empty_fits(self):
        assert self.manager.fits("", "") is True

    def test_small_texts_fit(self):
        system = make_text(100)
        user = make_text(200)
        assert self.manager.fits(system, user) is True

    def test_exactly_at_limit_fits(self):
        # 3484 tokens disponibles
        available = self.manager.config.available_tokens_for_input
        # Generar texto de exactamente available tokens
        total_chars = int(available * _DEFAULT_CHARS_PER_TOKEN)
        text = "a" * total_chars
        assert self.manager.fits("", text) is True

    def test_over_limit_does_not_fit(self):
        # Generar texto que supera el límite
        available = self.manager.config.available_tokens_for_input
        total_chars = int((available + 100) * _DEFAULT_CHARS_PER_TOKEN)
        text = "a" * total_chars
        assert self.manager.fits("", text) is False

    def test_system_counts_toward_limit(self):
        available = self.manager.config.available_tokens_for_input
        # system usa 2000 tokens, user usa 2000 tokens → total 4000 > 3484
        system = make_text(2000)
        user = make_text(2000)
        assert self.manager.fits(system, user) is False


# ─── Tests: _truncate ─────────────────────────────────────────────────────────

class TestTruncate:

    def setup_method(self):
        self.manager = ContextManager(make_config())

    def test_short_text_not_truncated(self):
        system = make_text(100)
        user = make_text(100)
        result = self.manager._truncate(system, user)
        assert result == user  # No se trunca

    def test_long_text_truncated(self):
        system = make_text(100)
        # user muy largo — supera el límite
        user = "x" * 100000
        result = self.manager._truncate(system, user)
        # Debe ser más corto que el original
        assert len(result) < len(user)
        # Debe caber junto con system
        assert self.manager.fits(system, result)

    def test_truncated_contains_marker(self):
        system = make_text(100)
        user = "x" * 100000
        result = self.manager._truncate(system, user)
        assert "[...contexto anterior omitido" in result

    def test_truncated_preserves_end(self):
        """El truncado conserva el FINAL del mensaje (más reciente)."""
        system = ""
        # Texto con inicio y final distinguibles
        user = "INICIO_" + "x" * 50000 + "_FINAL"
        result = self.manager._truncate(system, user)
        assert "_FINAL" in result
        assert "INICIO_" not in result  # El inicio se elimina


# ─── Tests: fit() con IA mock ─────────────────────────────────────────────────

class TestFitWithAI:

    def setup_method(self):
        # Config con límite pequeño para facilitar las pruebas
        # 1000 ctx, 200 respuesta, 50 margen → 750 tokens disponibles
        self.config = make_config(
            context_limit=1000,
            max_tokens_response=200,
            safety_margin=50,
            max_rounds=3,
            compression_ratio=0.6,
        )

    @pytest.mark.asyncio
    async def test_fit_noop_when_fits(self):
        """Si ya cabe, devuelve sin modificar."""
        manager = ContextManager(self.config)
        system = make_text(100)
        user = make_text(100)
        s_out, u_out = await manager.fit(system, user)
        assert s_out == system
        assert u_out == user

    @pytest.mark.asyncio
    async def test_fit_disabled_is_noop(self):
        """Si enabled=False, siempre devuelve sin modificar."""
        manager = ContextManager.disabled()
        system = "x" * 100000
        user = "y" * 100000
        s_out, u_out = await manager.fit(system, user)
        assert s_out == system
        assert u_out == user

    @pytest.mark.asyncio
    async def test_fit_truncates_when_no_ai(self):
        """Sin función IA, trunca directamente."""
        manager = ContextManager(self.config, ai_call_fn=None)
        system = make_text(100)
        user = "x" * 100000  # Muy largo
        s_out, u_out = await manager.fit(system, user)
        assert s_out == system  # System no se toca
        assert len(u_out) < len(user)
        assert manager.fits(system, u_out)

    @pytest.mark.asyncio
    async def test_fit_compresses_with_ai_one_round(self):
        """La IA comprime en 1 ronda y el resultado cabe.
        
        Config: ctx=1000, response=200, margin=50 → disponible=750 tokens
        system=50 tokens → disponible para user = 700 tokens = 2800 chars
        
        La IA devuelve 200 tokens (800 chars) → cabe con system(50) = 250 < 750 ✅
        """
        system = make_text(50)   # 50 tokens
        user = make_text(1000)   # 1000 tokens → no cabe (750 disponibles)

        # IA devuelve texto que SÍ cabe: 200 tokens = 800 chars
        # Con system(50) = 250 tokens total < 750 disponibles ✅
        compressed_text = "c" * 800  # 800 chars / 4 = 200 tokens → cabe
        # No usar strip() aquí — el ContextManager hace strip() internamente

        ai_mock = AsyncMock(return_value=compressed_text)
        manager = ContextManager(self.config, ai_call_fn=ai_mock)

        s_out, u_out = await manager.fit(system, user, task_hint="test task")

        assert s_out == system  # System no se toca
        # El resultado debe caber (puede ser el comprimido o truncado del comprimido)
        assert manager.fits(system, u_out)
        ai_mock.assert_called_once()  # Solo 1 ronda de compresión IA
        # El resultado debe contener el texto comprimido (o parte de él)
        assert len(u_out) <= len(compressed_text) + 100  # No más largo que el comprimido

    @pytest.mark.asyncio
    async def test_fit_compresses_with_ai_two_rounds(self):
        """La IA necesita 2 rondas para comprimir suficiente.
        
        Config: ctx=1000, response=200, margin=50 → disponible=750 tokens
        system=50 tokens → disponible para user = 700 tokens
        
        Ronda 1: IA devuelve 720 tokens → aún no cabe (720 > 700)
        Ronda 2: IA devuelve 300 tokens → cabe (300 < 700)
        """
        system = make_text(50)
        user = make_text(1000)  # No cabe

        # Ronda 1: devuelve texto que AÚN no cabe (720 tokens > 700 disponibles para user)
        round_1_result = "r1 " * 960  # 960 chars / 4 = 240 tokens... necesitamos más
        # Calculamos: disponible para user = 750 - 50(system) = 700 tokens = 2800 chars
        # Ronda 1 debe superar 2800 chars para no caber
        round_1_result = "x" * 3000  # 3000 chars / 4 = 750 tokens > 700 → no cabe
        round_1_result = round_1_result.strip()

        # Ronda 2: devuelve texto que SÍ cabe (300 tokens < 700)
        round_2_result = "y" * 1200  # 1200 chars / 4 = 300 tokens < 700 → cabe
        round_2_result = round_2_result.strip()

        call_count = 0
        async def ai_mock_fn(sys, usr):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return round_1_result
            return round_2_result

        manager = ContextManager(self.config, ai_call_fn=ai_mock_fn)
        s_out, u_out = await manager.fit(system, user)

        assert s_out == system
        assert call_count == 2  # 2 rondas
        assert manager.fits(system, u_out)

    @pytest.mark.asyncio
    async def test_fit_falls_back_to_truncate_when_ai_fails(self):
        """Si la IA falla en todas las rondas, trunca como último recurso."""
        system = make_text(50)
        user = "x" * 100000

        # IA siempre falla
        ai_mock = AsyncMock(side_effect=Exception("IA no disponible"))
        manager = ContextManager(self.config, ai_call_fn=ai_mock)

        s_out, u_out = await manager.fit(system, user)

        assert s_out == system
        assert len(u_out) < len(user)
        assert manager.fits(system, u_out)

    @pytest.mark.asyncio
    async def test_fit_falls_back_to_truncate_when_ai_returns_empty(self):
        """Si la IA devuelve vacío, trunca como último recurso."""
        system = make_text(50)
        user = "x" * 100000

        # IA devuelve vacío
        ai_mock = AsyncMock(return_value="")
        manager = ContextManager(self.config, ai_call_fn=ai_mock)

        s_out, u_out = await manager.fit(system, user)

        assert s_out == system
        assert manager.fits(system, u_out)

    @pytest.mark.asyncio
    async def test_fit_system_never_modified(self):
        """El system_prompt NUNCA se modifica, solo el user_message."""
        system = "INSTRUCCIONES CRÍTICAS: " + "x" * 10000
        user = "y" * 100000

        ai_mock = AsyncMock(return_value=make_text(200))
        manager = ContextManager(self.config, ai_call_fn=ai_mock)

        s_out, u_out = await manager.fit(system, user)

        # System siempre igual
        assert s_out == system
        # User fue comprimido
        assert len(u_out) < len(user)

    @pytest.mark.asyncio
    async def test_fit_with_task_hint_passed_to_ai(self):
        """El task_hint se pasa a la IA en el prompt de compresión."""
        system = make_text(50)
        user = make_text(1000)
        task_hint = "¿cuántos artículos hay en stock?"

        captured_args = []
        async def ai_capture_fn(sys_prompt, usr_msg):
            captured_args.append((sys_prompt, usr_msg))
            return make_text(300)

        manager = ContextManager(self.config, ai_call_fn=ai_capture_fn)
        await manager.fit(system, user, task_hint=task_hint)

        assert len(captured_args) > 0
        # El task_hint debe aparecer en el user_message de compresión
        _, compression_user = captured_args[0]
        assert task_hint in compression_user


# ─── Tests: factory methods ───────────────────────────────────────────────────

class TestFactoryMethods:

    def test_for_model_creates_correct_config(self):
        manager = ContextManager.for_model(
            model_context_limit=8192,
            max_tokens_response=1024,
        )
        assert manager.config.model_context_limit == 8192
        assert manager.config.max_tokens_response == 1024
        assert manager.config.enabled is True

    def test_for_model_with_ai_fn(self):
        ai_fn = AsyncMock()
        manager = ContextManager.for_model(
            model_context_limit=4096,
            max_tokens_response=512,
            ai_call_fn=ai_fn,
        )
        assert manager._ai_call_fn is ai_fn

    def test_disabled_creates_noop_manager(self):
        manager = ContextManager.disabled()
        assert manager.config.enabled is False

    @pytest.mark.asyncio
    async def test_disabled_manager_is_noop(self):
        manager = ContextManager.disabled()
        system = "x" * 100000
        user = "y" * 100000
        s_out, u_out = await manager.fit(system, user)
        assert s_out == system
        assert u_out == user


# ─── Tests: integración con Qwen3 30B (config real) ──────────────────────────

class TestQwen3Integration:
    """Tests con la configuración real del modelo Qwen3 30B (4096 tokens)."""

    QWEN3_CONTEXT = 4096
    QWEN3_MAX_RESPONSE = 512
    QWEN3_SAFETY_MARGIN = 100
    # Disponible para input: 4096 - 512 - 100 = 3484 tokens = 13936 chars

    def setup_method(self):
        self.config = ContextManagerConfig(
            model_context_limit=self.QWEN3_CONTEXT,
            max_tokens_response=self.QWEN3_MAX_RESPONSE,
            safety_margin_tokens=self.QWEN3_SAFETY_MARGIN,
        )

    def test_available_tokens(self):
        expected = self.QWEN3_CONTEXT - self.QWEN3_MAX_RESPONSE - self.QWEN3_SAFETY_MARGIN
        assert self.config.available_tokens_for_input == expected  # 3484

    def test_typical_deep_agent_prompt_fits(self):
        """Un prompt típico del DeepAgent (~2118 tokens) debe caber."""
        manager = ContextManager(self.config)
        # Simular prompt típico del DeepAgent
        system = make_text(300)   # ~300 tokens de instrucciones
        user = make_text(1800)    # ~1800 tokens de contexto/datos
        # Total: 2100 tokens < 3484 disponibles → debe caber
        assert manager.fits(system, user) is True

    def test_oversized_deep_agent_prompt_does_not_fit(self):
        """Un prompt demasiado grande (>3484 tokens) no debe caber."""
        manager = ContextManager(self.config)
        system = make_text(500)
        user = make_text(3500)  # Total 4000 > 3484
        assert manager.fits(system, user) is False

    @pytest.mark.asyncio
    async def test_oversized_prompt_gets_compressed(self):
        """Un prompt demasiado grande se comprime hasta caber."""
        # Simular el caso real: 2118 tokens de entrada + 2048 max_tokens → HTTP 400
        # Con el ContextManager, el prompt se comprime antes de enviarse
        system = make_text(500)
        user = make_text(3500)  # Demasiado grande

        # IA comprime a 2000 tokens → cabe con system(500) = 2500 < 3484
        compressed = make_text(2000)
        ai_mock = AsyncMock(return_value=compressed)

        manager = ContextManager(self.config, ai_call_fn=ai_mock)
        s_out, u_out = await manager.fit(system, user, task_hint="análisis de ventas")

        assert s_out == system
        assert manager.fits(system, u_out)
        ai_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_tokens_400_error_scenario(self):
        """
        Simula el escenario exacto del error HTTP 400:
        - Input: 2118 tokens
        - max_tokens pedido: 2048
        - Contexto modelo: 4096
        - 2118 + 2048 = 4166 > 4096 → ERROR

        Con ContextManager:
        - Disponible para input: 3484 tokens
        - 2118 < 3484 → CABE sin comprimir
        - max_tokens = 512 (no 2048) → 2118 + 512 = 2630 < 4096 → OK
        """
        manager = ContextManager(self.config)
        # Prompt de 2118 tokens (el caso real del DeepAgent)
        system = make_text(300)
        user = make_text(1818)  # 300 + 1818 = 2118 tokens

        # Debe caber sin comprimir
        assert manager.fits(system, user) is True

        # Verificar que con max_tokens=512 (no 2048) no hay overflow
        total_with_response = 2118 + self.QWEN3_MAX_RESPONSE  # 2118 + 512 = 2630
        assert total_with_response < self.QWEN3_CONTEXT  # 2630 < 4096 ✅


# ─── Tests: _compress_with_ai internals ──────────────────────────────────────

class TestCompressWithAI:

    def setup_method(self):
        self.config = make_config(
            context_limit=1000,
            max_tokens_response=200,
            safety_margin=50,
        )

    @pytest.mark.asyncio
    async def test_compress_returns_ai_result(self):
        """_compress_with_ai devuelve el resultado de la IA."""
        compressed = "contexto comprimido relevante"
        ai_mock = AsyncMock(return_value=compressed)
        manager = ContextManager(self.config, ai_call_fn=ai_mock)

        result = await manager._compress_with_ai(
            system_prompt="system",
            user_message="user " * 1000,
            task_hint="tarea",
            round_num=1,
        )
        assert result == compressed

    @pytest.mark.asyncio
    async def test_compress_returns_original_on_ai_error(self):
        """Si la IA falla, devuelve el user_message original."""
        original_user = "mensaje original"
        ai_mock = AsyncMock(side_effect=Exception("error"))
        manager = ContextManager(self.config, ai_call_fn=ai_mock)

        result = await manager._compress_with_ai(
            system_prompt="system",
            user_message=original_user,
            task_hint=None,
            round_num=1,
        )
        assert result == original_user

    @pytest.mark.asyncio
    async def test_compress_returns_original_on_empty_response(self):
        """Si la IA devuelve vacío, devuelve el user_message original."""
        original_user = "mensaje original"
        ai_mock = AsyncMock(return_value="   ")  # Solo espacios
        manager = ContextManager(self.config, ai_call_fn=ai_mock)

        result = await manager._compress_with_ai(
            system_prompt="system",
            user_message=original_user,
            task_hint=None,
            round_num=1,
        )
        assert result == original_user


# ─── Punto de entrada para ejecución directa ─────────────────────────────────

if __name__ == "__main__":
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "pytest",
         __file__, "-v", "--tb=short"],
        cwd=str(__file__).split("backend")[0].rstrip("/\\")
    )
    sys.exit(result.returncode)
