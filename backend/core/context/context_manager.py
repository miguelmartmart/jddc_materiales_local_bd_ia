"""
context_manager.py — Gestor de Contexto Inteligente para modelos LLM con límite de tokens.

PROBLEMA QUE RESUELVE:
  Los modelos LLM tienen un límite de contexto (ej: Qwen3 30B = 4096 tokens totales).
  Cuando system_prompt + user_message + max_tokens_respuesta > límite, el modelo
  devuelve HTTP 400 y el sistema se cuelga reintentando indefinidamente.

SOLUCIÓN:
  1. Calcular tokens estimados antes de enviar (1 token ≈ 4 chars, estimación conservadora)
  2. Si supera el límite disponible, comprimir el user_message con IA:
     - La IA extrae SOLO la información relevante para la pregunta/tarea actual
     - Descarta contexto antiguo, datos redundantes, ejemplos innecesarios
  3. Iterar hasta que quepa (máx N rondas de compresión)
  4. Si no cabe ni comprimido, truncar como último recurso (nunca falla)

DISEÑO:
  - Módulo INDEPENDIENTE: no importa nada del proyecto (solo stdlib + httpx)
  - Reutilizable: funciona con cualquier provider que tenga una función async de llamada IA
  - Configurable: límite de tokens, margen de seguridad, máx rondas, chars/token
  - Transparente: loguea cada paso de compresión para diagnóstico

USO BÁSICO:
  from backend.core.context import ContextManager, ContextManagerConfig

  cfg = ContextManagerConfig(model_context_limit=4096, max_tokens_response=512)
  manager = ContextManager(cfg, ai_call_fn=my_async_ai_function)

  system, user = await manager.fit(system_prompt, user_message, task_hint="pregunta del usuario")

USO EN JDDCIA PROVIDER:
  # En generate_text(), antes de construir el payload:
  system, prompt = await self._context_manager.fit(
      system_instruction, prompt, task_hint=prompt[:200]
  )

AUTOR: DEVIA System
VERSIÓN: 1.0.0
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Constantes por defecto ───────────────────────────────────────────────────

# Estimación conservadora: 1 token ≈ 4 caracteres (español tiene palabras más largas)
# OpenAI usa ~4 chars/token para inglés; para español/código usamos 3.5-4.
_DEFAULT_CHARS_PER_TOKEN: float = 4.0

# Margen de seguridad en tokens (reservar para overhead del modelo, separadores, etc.)
_DEFAULT_SAFETY_MARGIN_TOKENS: int = 100

# Máximo de rondas de compresión antes de truncar
_DEFAULT_MAX_COMPRESSION_ROUNDS: int = 3

# Ratio de compresión objetivo por ronda (reducir al X% del tamaño actual)
_DEFAULT_COMPRESSION_RATIO: float = 0.6  # 60% del tamaño → 40% de reducción por ronda

# Tokens mínimos para el user_message después de comprimir (evitar comprimir demasiado)
_MIN_USER_MESSAGE_TOKENS: int = 50


# ─── Dataclass de configuración ───────────────────────────────────────────────

@dataclass
class ContextManagerConfig:
    """
    Configuración del ContextManager.

    Parámetros:
        model_context_limit:    Límite total de tokens del modelo (ej: 4096 para Qwen3 30B)
        max_tokens_response:    Tokens reservados para la respuesta del modelo (ej: 512)
        chars_per_token:        Estimación de caracteres por token (default: 4.0)
        safety_margin_tokens:   Tokens de margen de seguridad adicional (default: 100)
        max_compression_rounds: Máximo de rondas de compresión con IA (default: 3)
        compression_ratio:      Ratio de compresión objetivo por ronda (default: 0.6)
        enabled:                Si False, el manager es un no-op (pass-through)
    """
    model_context_limit: int = 4096
    max_tokens_response: int = 512
    chars_per_token: float = _DEFAULT_CHARS_PER_TOKEN
    safety_margin_tokens: int = _DEFAULT_SAFETY_MARGIN_TOKENS
    max_compression_rounds: int = _DEFAULT_MAX_COMPRESSION_ROUNDS
    compression_ratio: float = _DEFAULT_COMPRESSION_RATIO
    enabled: bool = True

    @property
    def available_tokens_for_input(self) -> int:
        """Tokens disponibles para system + user (después de reservar respuesta y margen)."""
        return max(
            _MIN_USER_MESSAGE_TOKENS,
            self.model_context_limit - self.max_tokens_response - self.safety_margin_tokens
        )

    @property
    def available_chars_for_input(self) -> int:
        """Caracteres disponibles para system + user."""
        return int(self.available_tokens_for_input * self.chars_per_token)


# ─── Tipo de la función de llamada IA ─────────────────────────────────────────

# Firma: async fn(system_prompt: str, user_message: str) -> str
AICallFn = Callable[[str, str], Awaitable[str]]


# ─── ContextManager ───────────────────────────────────────────────────────────

class ContextManager:
    """
    Gestor de contexto inteligente para modelos LLM con límite de tokens.

    Cuando system_prompt + user_message supera el límite disponible del modelo,
    comprime el user_message usando la propia IA para extraer solo lo relevante.

    Estrategia de compresión (en orden):
      1. Compresión IA: pide a la IA que resuma/extraiga lo relevante
         → Preserva la información más importante para la tarea actual
         → Descarta contexto antiguo, datos redundantes, ejemplos innecesarios
      2. Truncado inteligente: si la IA no puede comprimir suficiente,
         trunca el user_message por el final (la parte más antigua/menos relevante)
         → Siempre garantiza que el mensaje cabe

    El system_prompt NUNCA se comprime (contiene instrucciones críticas).
    Solo se comprime el user_message (contiene datos/contexto variable).
    """

    def __init__(
        self,
        config: ContextManagerConfig,
        ai_call_fn: Optional[AICallFn] = None,
    ):
        """
        Args:
            config:      Configuración del manager (límites, ratios, etc.)
            ai_call_fn:  Función async para llamar a la IA de compresión.
                         Firma: async fn(system_prompt: str, user_message: str) -> str
                         Si es None, solo se usa truncado (sin compresión IA).
        """
        self.config = config
        self._ai_call_fn = ai_call_fn
        logger.info(
            f"[CTX_MGR] Inicializado — límite={config.model_context_limit} tokens, "
            f"disponible_input={config.available_tokens_for_input} tokens "
            f"({config.available_chars_for_input} chars), "
            f"max_rondas={config.max_compression_rounds}, "
            f"ai_compressor={'✅' if ai_call_fn else '❌ (solo truncado)'}"
        )

    # ─── API pública ──────────────────────────────────────────────────────────

    def estimate_tokens(self, *texts: str) -> int:
        """Estima el número de tokens de uno o varios textos."""
        total_chars = sum(len(t) for t in texts if t)
        return max(1, math.ceil(total_chars / self.config.chars_per_token))

    def fits(self, system_prompt: str, user_message: str) -> bool:
        """Comprueba si system + user caben en el presupuesto disponible."""
        total_tokens = self.estimate_tokens(system_prompt or "", user_message or "")
        fits = total_tokens <= self.config.available_tokens_for_input
        if not fits:
            logger.debug(
                f"[CTX_MGR] No cabe: {total_tokens} tokens > "
                f"{self.config.available_tokens_for_input} disponibles"
            )
        return fits

    async def fit(
        self,
        system_prompt: str,
        user_message: str,
        task_hint: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Ajusta system_prompt + user_message para que quepan en el límite del modelo.

        Si ya caben, devuelve los textos sin modificar (no-op).
        Si no caben, comprime el user_message con IA (o trunca si no hay IA).

        Args:
            system_prompt:  Prompt del sistema (instrucciones, rol, etc.) — NO se comprime
            user_message:   Mensaje del usuario (datos, contexto, historial) — se comprime
            task_hint:      Pista sobre la tarea actual para guiar la compresión IA
                            (ej: la pregunta del usuario, el objetivo de la fase)

        Returns:
            Tupla (system_prompt, user_message) ajustados para caber en el límite.
            El system_prompt siempre se devuelve sin modificar.
        """
        if not self.config.enabled:
            return system_prompt, user_message

        system_prompt = system_prompt or ""
        user_message = user_message or ""

        # Caso trivial: ya cabe
        if self.fits(system_prompt, user_message):
            return system_prompt, user_message

        original_tokens = self.estimate_tokens(system_prompt, user_message)
        logger.warning(
            f"[CTX_MGR] ⚠️ Contexto demasiado grande: {original_tokens} tokens "
            f"(límite: {self.config.available_tokens_for_input}). "
            f"Iniciando compresión..."
        )

        # Intentar compresión IA (hasta max_compression_rounds rondas)
        compressed_user = user_message
        for round_num in range(1, self.config.max_compression_rounds + 1):
            if self._ai_call_fn is not None:
                compressed_user = await self._compress_with_ai(
                    system_prompt=system_prompt,
                    user_message=compressed_user,
                    task_hint=task_hint,
                    round_num=round_num,
                )
            else:
                # Sin IA: truncar directamente
                compressed_user = self._truncate(system_prompt, compressed_user)
                logger.info(
                    f"[CTX_MGR] ✂️ Truncado (sin IA): "
                    f"{self.estimate_tokens(compressed_user)} tokens"
                )
                return system_prompt, compressed_user

            # Comprobar si ya cabe
            if self.fits(system_prompt, compressed_user):
                final_tokens = self.estimate_tokens(system_prompt, compressed_user)
                reduction_pct = round((1 - final_tokens / original_tokens) * 100, 1)
                logger.info(
                    f"[CTX_MGR] ✅ Compresión exitosa en ronda {round_num}: "
                    f"{original_tokens} → {final_tokens} tokens "
                    f"(-{reduction_pct}%)"
                )
                return system_prompt, compressed_user

            logger.warning(
                f"[CTX_MGR] Ronda {round_num}: aún no cabe "
                f"({self.estimate_tokens(system_prompt, compressed_user)} tokens). "
                f"{'Siguiente ronda...' if round_num < self.config.max_compression_rounds else 'Truncando.'}"
            )

        # Último recurso: truncar
        truncated_user = self._truncate(system_prompt, compressed_user)
        final_tokens = self.estimate_tokens(system_prompt, truncated_user)
        logger.warning(
            f"[CTX_MGR] ✂️ Truncado como último recurso: "
            f"{original_tokens} → {final_tokens} tokens "
            f"(compresión IA insuficiente tras {self.config.max_compression_rounds} rondas)"
        )
        return system_prompt, truncated_user

    # ─── Métodos internos ─────────────────────────────────────────────────────

    async def _compress_with_ai(
        self,
        system_prompt: str,
        user_message: str,
        task_hint: Optional[str],
        round_num: int,
    ) -> str:
        """
        Usa la IA para comprimir el user_message extrayendo solo lo relevante.

        Estrategia:
        - Calcula cuántos chars puede tener el user_message comprimido para que quepa
        - Pide a la IA que resuma/extraiga lo más relevante para la tarea actual
        - Si la IA falla, devuelve el user_message original (sin comprimir)

        El prompt de compresión es MUY corto (< 200 tokens) para no causar recursión.
        """
        # Calcular cuántos chars puede tener el user_message comprimido
        system_tokens = self.estimate_tokens(system_prompt)
        available_for_user = self.config.available_tokens_for_input - system_tokens
        # Aplicar ratio de compresión objetivo
        target_tokens = max(
            _MIN_USER_MESSAGE_TOKENS,
            int(available_for_user * self.config.compression_ratio)
        )
        target_chars = int(target_tokens * self.config.chars_per_token)

        current_tokens = self.estimate_tokens(user_message)
        logger.info(
            f"[CTX_MGR] 🤖 Compresión IA ronda {round_num}: "
            f"{current_tokens} → objetivo {target_tokens} tokens "
            f"({target_chars} chars)"
        )

        # Construir prompt de compresión (muy corto para no causar recursión)
        task_context = f"\nTAREA ACTUAL: {task_hint[:300]}" if task_hint else ""
        compression_system = (
            "Eres un compresor de contexto para IA. Tu única tarea es resumir el texto "
            "dado extrayendo SOLO la información esencial y relevante para la tarea actual. "
            "Elimina: historial antiguo, datos redundantes, ejemplos innecesarios, "
            "explicaciones verbosas. Conserva: datos clave, resultados SQL, "
            "instrucciones críticas, contexto de la pregunta actual. "
            "Responde SOLO con el texto comprimido, sin explicaciones ni prefijos."
        )
        compression_user = (
            f"Comprime este contexto a máximo {target_chars} caracteres.{task_context}\n\n"
            f"CONTEXTO A COMPRIMIR:\n{user_message}"
        )

        # Verificar que el prompt de compresión en sí no sea demasiado largo
        # (evitar recursión infinita — el prompt de compresión debe ser corto)
        compression_total = self.estimate_tokens(compression_system, compression_user)
        if compression_total > self.config.available_tokens_for_input:
            # El propio prompt de compresión es demasiado largo — truncar el user_message
            # antes de enviarlo a la IA de compresión
            max_chars_for_compression_input = int(
                (self.config.available_tokens_for_input - self.estimate_tokens(compression_system) - 50)
                * self.config.chars_per_token
            )
            truncated_for_compression = user_message[:max_chars_for_compression_input]
            compression_user = (
                f"Comprime este contexto a máximo {target_chars} caracteres.{task_context}\n\n"
                f"CONTEXTO A COMPRIMIR:\n{truncated_for_compression}"
            )
            logger.debug(
                f"[CTX_MGR] Prompt de compresión truncado para evitar recursión: "
                f"{len(user_message)} → {max_chars_for_compression_input} chars"
            )

        try:
            compressed = await self._ai_call_fn(compression_system, compression_user)
            if compressed and len(compressed.strip()) > 10:
                compressed = compressed.strip()
                logger.debug(
                    f"[CTX_MGR] IA comprimió: {len(user_message)} → {len(compressed)} chars"
                )
                return compressed
            else:
                logger.warning(
                    f"[CTX_MGR] IA devolvió respuesta vacía/inválida en ronda {round_num}. "
                    f"Usando user_message original."
                )
                return user_message
        except Exception as e:
            logger.warning(
                f"[CTX_MGR] ❌ Error en compresión IA ronda {round_num}: "
                f"{type(e).__name__}: {e}. Usando user_message original."
            )
            return user_message

    def _truncate(self, system_prompt: str, user_message: str) -> str:
        """
        Trunca el user_message para que quepa junto con el system_prompt.
        Trunca por el INICIO (elimina el contexto más antiguo, conserva el más reciente).

        Estrategia: conservar el final del user_message (más reciente/relevante).
        """
        system_tokens = self.estimate_tokens(system_prompt)
        available_for_user = max(
            _MIN_USER_MESSAGE_TOKENS,
            self.config.available_tokens_for_input - system_tokens
        )
        max_chars = int(available_for_user * self.config.chars_per_token)

        if len(user_message) <= max_chars:
            return user_message

        # Conservar el FINAL del mensaje (más reciente) y añadir indicador de truncado
        truncation_marker = "\n[...contexto anterior omitido por límite de tokens...]\n"
        available_for_content = max_chars - len(truncation_marker)
        if available_for_content <= 0:
            return user_message[-max_chars:]

        # Truncar por el inicio: conservar los últimos available_for_content chars
        truncated = truncation_marker + user_message[-available_for_content:]
        return truncated

    # ─── Factory methods ──────────────────────────────────────────────────────

    @classmethod
    def for_model(
        cls,
        model_context_limit: int,
        max_tokens_response: int,
        ai_call_fn: Optional[AICallFn] = None,
        **kwargs,
    ) -> "ContextManager":
        """
        Factory method: crea un ContextManager para un modelo específico.

        Ejemplo:
            manager = ContextManager.for_model(
                model_context_limit=4096,
                max_tokens_response=512,
                ai_call_fn=my_ai_fn
            )
        """
        config = ContextManagerConfig(
            model_context_limit=model_context_limit,
            max_tokens_response=max_tokens_response,
            **kwargs
        )
        return cls(config, ai_call_fn=ai_call_fn)

    @classmethod
    def disabled(cls) -> "ContextManager":
        """
        Crea un ContextManager desactivado (no-op / pass-through).
        Útil para modelos con contexto grande donde no es necesario comprimir.
        """
        config = ContextManagerConfig(enabled=False)
        return cls(config)
