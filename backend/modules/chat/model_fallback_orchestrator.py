"""
Model Fallback Orchestrator - Sistema robusto de fallback entre modelos IA

Este módulo implementa un sistema de reintentos y fallback entre múltiples modelos
de IA para garantizar la generación exitosa de consultas SQL.

Características:
- Reintentos automáticos con delays configurables
- Fallback entre modelos ordenados por prioridad
- Logging detallado de cada intento
- Feedback claro al usuario durante el proceso
- Modo AI_LOCAL_ONLY: usa solo la IA local Qwen3 LAN, sin salir a internet

Autor: DEVIA System
Versión: 1.2.0
"""

import asyncio
import logging
import json
import os
# DEVIA: backend/modules/chat/DEVIA_ROBUSTNESS.md
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from backend.core.config.model_manager import ModelManager, model_manager as _model_manager_singleton
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.utils.constants import (
    ModelFallbackConfig,
    UserFeedbackMessages,
    LogPrefixes,
    LogEmojis
)
from backend.core.utils.network_audit_constants import LocalModelIds

logger = logging.getLogger(__name__)

# IDs de modelos locales (red LAN JDDC, sin internet)
# FUENTE ÚNICA DE VERDAD: backend/core/utils/network_audit_constants.py → LocalModelIds
LOCAL_MODEL_IDS: frozenset = LocalModelIds.ALL

# Path del config.json (fuente única de verdad para flags y timeouts)
_CONFIG_JSON_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# Valor por defecto para lan_max_retries si config.json no está disponible.
# 10 rondas × backoff progresivo = ~60s de espera máxima antes de rendirse.
_LAN_MAX_RETRIES_DEFAULT = 10


def _load_chat_config() -> dict:
    """
    Lee el config.json del chat y devuelve el dict completo.
    Devuelve {} si no existe o está corrupto (fail-safe).
    Se llama en cada petición para que los cambios en config.json
    surtan efecto sin reiniciar el servidor.
    """
    try:
        if os.path.exists(_CONFIG_JSON_PATH):
            with open(_CONFIG_JSON_PATH, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"[CHAT_CONFIG] No se pudo leer config.json: {e}")
    return {}


def _load_ai_local_only() -> bool:
    """
    Lee el flag ai_local_only del config.json del chat.
    Si es True, solo se usan modelos locales (red LAN JDDC).
    Si es False, se usa el sistema de fallback multi-modelo completo.

    Para cambiar el modo: editar backend/modules/chat/config.json
      "ai_local_only": true   → Solo Qwen3 LAN (sin internet)
      "ai_local_only": false  → Fallback completo (Groq, Gemini, OpenAI, etc.)
    """
    return bool(_load_chat_config().get("ai_local_only", False))


def _load_lan_max_retries() -> int:
    """
    Lee lan_max_retries del config.json del chat.
    Controla cuántas rondas de reintento se hacen en modo LAN_ONLY antes de
    devolver (None, None).

    Rango recomendado: 5-15. Con backoff progresivo:
      rondas 1-3  → 2s de espera → 6s total
      rondas 4-6  → 5s de espera → 15s total
      rondas 7+   → 10s de espera → 10s × (N-6) total

    Si es 0 o negativo, se usa el default (10).
    Si config.json no existe, se usa el default (10).
    """
    cfg = _load_chat_config()
    value = cfg.get("lan_max_retries", _LAN_MAX_RETRIES_DEFAULT)
    try:
        retries = int(value)
        if retries <= 0:
            logger.warning(
                f"[LAN_MAX_RETRIES] Valor inválido en config.json: {value}. "
                f"Usando default {_LAN_MAX_RETRIES_DEFAULT}."
            )
            return _LAN_MAX_RETRIES_DEFAULT
        return retries
    except (TypeError, ValueError):
        logger.warning(
            f"[LAN_MAX_RETRIES] No se pudo parsear lan_max_retries={value!r}. "
            f"Usando default {_LAN_MAX_RETRIES_DEFAULT}."
        )
        return _LAN_MAX_RETRIES_DEFAULT


class ModelFallbackOrchestrator:
    """
    Orquestador de fallback entre modelos IA con reintentos automáticos.

    Gestiona la ejecución de consultas a modelos IA con estrategia de fallback:
    1. Intenta con modelo de mayor prioridad
    2. Si falla, espera y reintenta
    3. Si falla de nuevo, cambia al siguiente modelo
    4. Repite hasta agotar modelos o tener éxito
    """

    def __init__(self):
        """Inicializa el orchestrator reutilizando el singleton ModelManager."""
        self.model_manager = _model_manager_singleton  # singleton — no crear instancia nueva
        self.retry_delay = ModelFallbackConfig.RETRY_DELAY_SECONDS
        self.max_retries_per_model = ModelFallbackConfig.MAX_RETRIES_PER_MODEL
        self.preferred_model_id: Optional[str] = None
        self.last_execution_stats: Dict[str, Any] = {
            "attempts": 0,
            "retries": 0,
            "fallbacks": 0,
            "models_tried": [],
            "model_used": None,
            "aborted_by_deadline": False,
        }

    def _get_prioritized_models(self, preferred_model_id: str = None) -> List[Dict[str, Any]]:
        """
        Obtiene lista de modelos disponibles ordenados por prioridad (Score > Tier).
        Si se especifica preferred_model_id, ese modelo se coloca primero (si existe y está habilitado).

        Returns:
            Lista de configuraciones de modelos ordenada.
        """
        # ModelManager.list_models already sorts by Blocked -> Score -> Tier
        sorted_models = self.model_manager.list_models(enabled_only=True) or []

        # If preferred model is requested, move it to top
        if preferred_model_id:
            preferred_model = next((m for m in sorted_models if m['id'] == preferred_model_id), None)
            if preferred_model:
                # Remove from current position and insert at beginning
                sorted_models = [m for m in sorted_models if m['id'] != preferred_model_id]
                sorted_models.insert(0, preferred_model)
                logger.info(f"{LogPrefixes.AI_PROVIDER} ⭐ Modelo PREFERIDO seleccionado: {preferred_model['name']}")

        # Solo loguear resumen (no la lista completa de 189 modelos — demasiado ruido)
        if sorted_models:
            top3 = [f"{m.get('name')} (Score:{m.get('score')})" for m in sorted_models[:3]]
            logger.debug(
                f"{LogPrefixes.AI_PROVIDER} {LogEmojis.SEARCH} "
                f"{len(sorted_models)} modelos disponibles. Top3: {', '.join(top3)}"
            )
        else:
            logger.warning(f"  {LogEmojis.WARNING} No se encontraron modelos habilitados.")

        return sorted_models

    async def _try_model(
        self,
        model_config: Dict[str, Any],
        system_prompt: str,
        user_message: str,
        images: Optional[List[str]] = None,
        attempt: int = 1
    ) -> Optional[str]:
        """
        Intenta generar respuesta con un modelo específico.

        Args:
            model_config: Configuración del modelo a usar
            system_prompt: Prompt del sistema
            user_message: Mensaje del usuario
            attempt: Número de intento actual

        Returns:
            Respuesta del modelo o None si falla
        """
        model_name = model_config.get('name', 'Unknown')
        model_id = model_config.get('id', '')

        try:
            logger.info(
                f"{LogPrefixes.AI_PROVIDER} {LogEmojis.SEND} "
                f"Intentando con {model_name} (intento {attempt}/{self.max_retries_per_model + 1})"
            )

            # Configurar provider
            provider_schema = model_config.get('schema', model_config.get('provider'))
            provider = AIFactory.get_provider(provider_schema)

            api_key = model_config.get('api_key')
            if not api_key:
                logger.error(f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} No API key para {model_name}")
                return None

            # Crear configuración — pasar model_config completa via extra_params
            # El provider (OpenAICompatibleProvider) la usa para context_limit, max_tokens, timeout_s, etc.
            ai_config_params = {
                'api_key': api_key,
                'model': model_config['model_id'],
                # Extra params para providers que los soporten (ej: OpenAICompatibleProvider)
                'context_limit': model_config.get('context_limit', 8192),
                'parameters': model_config.get('parameters', {}),
                'model_id_logical': model_config.get('id', ''),
            }
            if model_config.get('base_url'):
                ai_config_params['base_url'] = model_config['base_url']
            if model_config.get('headers'):
                ai_config_params['headers'] = model_config['headers']

            ai_config = AIConfig(**ai_config_params)
            provider.configure(ai_config)

            # Generar respuesta
            response = await provider.generate_text(
                prompt=user_message,
                system_instruction=system_prompt,
                images=images
            )

            if response:
                logger.info(
                    f"{LogPrefixes.AI_PROVIDER} {LogEmojis.SUCCESS} "
                    f"Respuesta exitosa de {model_name}"
                )
                self.model_manager.report_result(model_id, True)
                return response
            else:
                logger.warning(
                    f"{LogPrefixes.AI_PROVIDER} {LogEmojis.WARNING} "
                    f"Respuesta vacía de {model_name}"
                )
                self.model_manager.report_result(model_id, False, error_type="empty", error_msg="empty response")
                return None

        except Exception as e:
            # Loguear tipo de excepción completo para diagnóstico (ej: ReadTimeout, ConnectError)
            logger.error(
                f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} "
                f"Error con {model_name}: {type(e).__name__}: {str(e)}"
            )
            # Try to extract status code if available
            err_code = getattr(e, "status_code", None)
            if not err_code and hasattr(e, "response") and hasattr(e.response, "status_code"):
                err_code = e.response.status_code

            self.model_manager.report_result(model_id, False, error_type=str(err_code) if err_code else None, error_msg=str(e))
            return None

    async def _execute_lan_only(
        self,
        local_models: List[Dict[str, Any]],
        system_prompt: str,
        user_message: str,
        images: Optional[List[str]] = None,
        feedback_callback: Optional[callable] = None,
        max_retries_override: Optional[int] = None,
        max_models_override: Optional[int] = None,
        deadline_monotonic: Optional[float] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Modo AI_LOCAL_ONLY: reintenta SOLO los modelos LAN hasta lan_max_retries rondas.

        Política de reintentos con backoff progresivo:
          rondas 1-3  → espera 2s entre rondas
          rondas 4-6  → espera 5s entre rondas
          ronda 7+    → espera 10s entre rondas (máximo)

        El número máximo de rondas se lee de config.json (lan_max_retries=10).
        Si se agotan las rondas, devuelve (None, None) con log de error.

        GARANTÍA: NUNCA llama a ningún modelo de internet.
        """
        # Anonimizar mensaje — SOLO con regex (lan_only=True), NUNCA llama a IA externa
        # Garantía: ningún dato sale a internet durante la anonimización en modo LAN_ONLY
        try:
            from backend.modules.anonymizer.service import AnonymizerService
            anonymizer = AnonymizerService()
            user_message = anonymizer.anonymize_if_enabled(user_message, "chat", lan_only=True)
        except Exception as anon_err:
            logger.warning(f"[LAN_ONLY] Anonymizer skipped: {anon_err}")

        # Leer lan_max_retries de config.json en cada llamada (sin reiniciar el servidor)
        max_retries = max_retries_override if max_retries_override is not None else _load_lan_max_retries()
        logger.info(
            f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] Máximo de rondas: {max_retries} "
            f"(config.json → lan_max_retries)"
        )

        # Modelos que fallaron permanentemente en esta sesión (405, context exceeded, etc.)
        # No se reintentarán en rondas posteriores — ahorran tiempo cuando el servidor está caído
        _permanently_failed: set = set()

        attempt_global = 0
        while True:
            attempt_global += 1
            # Backoff progresivo
            if attempt_global <= 3:
                backoff = 2
            elif attempt_global <= 6:
                backoff = 5
            else:
                backoff = 10

            # Filtrar modelos que ya fallaron permanentemente
            active_models = [m for m in local_models if m.get('id', '') not in _permanently_failed]
            if max_models_override is not None:
                active_models = active_models[:max_models_override]
            if not active_models:
                logger.error(
                    f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] ❌ Todos los modelos LAN fallaron permanentemente. "
                    f"No hay modelos disponibles para reintentar."
                )
                break

            logger.info(
                f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] Ronda {attempt_global}/{max_retries} — "
                f"probando {len(active_models)} modelos LAN..."
            )

            for model_config in active_models:
                if deadline_monotonic is not None and asyncio.get_running_loop().time() >= deadline_monotonic:
                    logger.warning("[LAN_ONLY] Deadline agotado antes de intentar otro modelo")
                    if stats is not None:
                        stats["aborted_by_deadline"] = True
                    return None, None

                model_name = model_config.get('name', 'Unknown')
                model_id = model_config.get('id', '')
                if stats is not None:
                    stats["attempts"] = int(stats.get("attempts", 0)) + 1
                    if model_id not in stats.get("models_tried", []):
                        stats.setdefault("models_tried", []).append(model_id)

                logger.info(
                    f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] Intentando {model_name} "
                    f"(ronda global {attempt_global}/{max_retries})"
                )

                try:
                    response = await self._try_model(
                        model_config=model_config,
                        system_prompt=system_prompt,
                        user_message=user_message,
                        images=images,
                        attempt=attempt_global
                    )
                except Exception as e:
                    # Loguear tipo de excepción completo para diagnóstico
                    logger.warning(
                        f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] ⚠️ Excepción en {model_name}: "
                        f"{type(e).__name__}: {e}"
                    )
                    response = None

                    # Detectar fallos permanentes: no reintentar en rondas siguientes
                    err_str = str(e).lower()
                    err_type = type(e).__name__
                    is_permanent = (
                        "405" in err_str or
                        "not allowed" in err_str or
                        "context size" in err_str or
                        "context_size" in err_str or
                        "badrequesterror" in err_type.lower() or
                        "context" in err_str and "exceeded" in err_str
                    )
                    if is_permanent:
                        _permanently_failed.add(model_id)
                        logger.warning(
                            f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] ⛔ {model_name} marcado como "
                            f"fallo permanente ({err_type}) — no se reintentará en esta sesión"
                        )

                if response:
                    logger.info(
                        f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] ✅ Respuesta de {model_name} "
                        f"en ronda {attempt_global}"
                    )
                    if stats is not None:
                        stats["model_used"] = model_id
                    return response, model_id

                # Detectar fallo permanente desde _try_model (captura interna)
                # _try_model devuelve None tanto para errores transitorios como permanentes
                # Verificar el último error reportado al model_manager
                last_err = self.model_manager.get_last_error(model_id) if hasattr(self.model_manager, 'get_last_error') else None
                if last_err:
                    err_lower = str(last_err).lower()
                    if "405" in err_lower or "not allowed" in err_lower or "context size" in err_lower or ("context" in err_lower and "exceeded" in err_lower):
                        _permanently_failed.add(model_id)
                        logger.warning(
                            f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] ⛔ {model_name} marcado como "
                            f"fallo permanente (via model_manager) — no se reintentará"
                        )

            # Todos los modelos LAN fallaron en esta ronda
            # Comprobar si se han agotado las rondas
            if attempt_global >= max_retries:
                logger.error(
                    f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] ❌ Se agotaron las {max_retries} rondas "
                    f"de reintento. La IA local no está disponible. "
                    f"(Aumenta lan_max_retries en config.json para más reintentos)"
                )
                if feedback_callback:
                    feedback_callback(
                        f"❌ IA local no disponible tras {max_retries} intentos. "
                        f"Verifica que el servidor Qwen3 30B esté levantado."
                    )
                return None, None

            logger.warning(
                f"{LogPrefixes.AI_PROVIDER} 🔒 [LAN_ONLY] ⚠️ Todos los modelos LAN fallaron "
                f"en ronda {attempt_global}/{max_retries}. Reintentando en {backoff}s... "
                f"(NUNCA se usará internet)"
            )
            if feedback_callback:
                feedback_callback(
                    f"⏳ IA local no disponible (intento {attempt_global}/{max_retries}). "
                    f"Reintentando en {backoff}s..."
                )
            await asyncio.sleep(backoff)

    async def execute_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        images: Optional[List[str]] = None,
        feedback_callback: Optional[callable] = None,
        preferred_model_id: str = None,
        execution_policy: Optional[Dict[str, int]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Ejecuta generación de respuesta con fallback entre modelos.

        Args:
            system_prompt: Prompt del sistema
            user_message: Mensaje del usuario
            feedback_callback: Función opcional para enviar feedback al usuario
            preferred_model_id: ID del modelo preferido (intentar primero)

        Returns:
            Tupla (respuesta, model_id) o (None, None) si todos fallan
        """
        self.preferred_model_id = preferred_model_id
        stats: Dict[str, Any] = {
            "attempts": 0,
            "retries": 0,
            "fallbacks": 0,
            "models_tried": [],
            "model_used": None,
            "aborted_by_deadline": False,
        }

        max_retries_override = None
        max_models_override = None
        if execution_policy:
            if execution_policy.get("max_retries_per_model") is not None:
                max_retries_override = max(0, int(execution_policy["max_retries_per_model"]))
            if execution_policy.get("max_models") is not None:
                max_models_override = max(1, int(execution_policy["max_models"]))

        prioritized_models = self._get_prioritized_models(preferred_model_id)
        if max_models_override is not None:
            prioritized_models = prioritized_models[:max_models_override]

        if not prioritized_models:
            logger.error(f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} No hay modelos disponibles")
            if feedback_callback:
                feedback_callback(UserFeedbackMessages.ALL_MODELS_FAILED)
            return None, None

        # --- MODO AI_LOCAL_ONLY ---
        # Lee el flag en cada llamada (sin reiniciar el servidor) para que el cambio
        # en config.json surta efecto inmediatamente.
        #
        # Cuando ai_local_only=true:
        #   - SOLO se usan los modelos LAN (jddcia-qwen3-30b / jddcia-qwen3-30b-ip)
        #   - Se reintenta hasta lan_max_retries rondas con backoff progresivo
        #   - NUNCA se hace fallback a modelos de internet
        ai_local_only = _load_ai_local_only()
        if ai_local_only:
            local_models = [m for m in prioritized_models if m.get('id') in LOCAL_MODEL_IDS]
            if local_models:
                logger.info(
                    f"{LogPrefixes.AI_PROVIDER} 🔒 Modo AI_LOCAL_ONLY activo — "
                    f"usando SOLO modelos LAN (sin fallback a internet): {[m['name'] for m in local_models]}"
                )
                result = await self._execute_lan_only(
                    local_models=local_models,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    images=images,
                    feedback_callback=feedback_callback,
                    max_retries_override=max_retries_override,
                    max_models_override=max_models_override,
                    deadline_monotonic=deadline_monotonic,
                    stats=stats,
                )
                self.last_execution_stats = stats
                return result
            else:
                logger.error(
                    f"{LogPrefixes.AI_PROVIDER} ❌ Modo AI_LOCAL_ONLY activo pero "
                    f"ningún modelo local está habilitado (IDs esperados: {LOCAL_MODEL_IDS}). "
                    f"Verifica que jddcia-qwen3-30b esté enabled=true en jddcia_models.json"
                )
                return None, None
        else:
            logger.info(
                f"{LogPrefixes.AI_PROVIDER} 🌐 Modo FALLBACK completo activo — "
                f"usando {len(prioritized_models)} modelos (incluye internet)"
            )
        # --------------------------

        # --- GLOBAL ANONYMIZER INTEGRATION ---
        try:
            from backend.modules.anonymizer.service import AnonymizerService
            anonymizer = AnonymizerService()
            # Anonymize User Message if enabled for 'chat'
            # Note: We don't anonymize System Prompt as it defines rules, not data.
            user_message = anonymizer.anonymize_if_enabled(user_message, "chat")
        except Exception as anon_err:
            logger.warning(f"Anonymizer skipped due to error: {anon_err}")
        # -------------------------------------

        # Iterar por cada modelo
        retries_per_model = (
            max_retries_override
            if max_retries_override is not None
            else self.max_retries_per_model
        )

        for model_idx, model_config in enumerate(prioritized_models):
            if deadline_monotonic is not None and asyncio.get_running_loop().time() >= deadline_monotonic:
                logger.warning("[FALLBACK] Deadline agotado antes de cambiar de modelo")
                stats["aborted_by_deadline"] = True
                self.last_execution_stats = stats
                return None, None

            model_name = model_config.get('name', 'Unknown')
            model_id = model_config.get('id', '')
            if model_idx > 0:
                stats["fallbacks"] = int(stats.get("fallbacks", 0)) + 1
            if model_id not in stats.get("models_tried", []):
                stats.setdefault("models_tried", []).append(model_id)

            # Notificar cambio de modelo (excepto el primero)
            if model_idx > 0 and feedback_callback:
                feedback_callback(
                    UserFeedbackMessages.SWITCHING_MODEL.format(model_name=model_name)
                )

            # Intentar con este modelo (1 intento inicial + reintentos)
            for attempt in range(1, retries_per_model + 2):
                if deadline_monotonic is not None and asyncio.get_running_loop().time() >= deadline_monotonic:
                    logger.warning("[FALLBACK] Deadline agotado antes de nuevo intento")
                    stats["aborted_by_deadline"] = True
                    self.last_execution_stats = stats
                    return None, None

                stats["attempts"] = int(stats.get("attempts", 0)) + 1
                if attempt > 1:
                    stats["retries"] = int(stats.get("retries", 0)) + 1
                # Feedback al usuario
                if feedback_callback:
                    if attempt == 1:
                        feedback_callback(
                            UserFeedbackMessages.TRYING_MODEL.format(model_name=model_name)
                        )
                    else:
                        feedback_callback(
                            UserFeedbackMessages.RETRYING_MODEL.format(
                                model_name=model_name,
                                attempt=attempt,
                                max_attempts=retries_per_model + 1
                            )
                        )

                # Intentar generación
                response = await self._try_model(
                    model_config=model_config,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    images=images,
                    attempt=attempt
                )

                if response:
                    # ¡Éxito!
                    if feedback_callback:
                        feedback_callback(
                            UserFeedbackMessages.SUCCESS.format(model_name=model_name)
                        )
                    stats["model_used"] = model_id
                    self.last_execution_stats = stats
                    return response, model_id

                # Si falló y quedan reintentos, esperar
                if attempt < retries_per_model + 1:
                    logger.info(
                        f"{LogPrefixes.AI_PROVIDER} ⏳ "
                        f"Esperando {self.retry_delay}s antes de reintentar..."
                    )
                    if feedback_callback:
                        feedback_callback(
                            UserFeedbackMessages.WAITING.format(seconds=self.retry_delay)
                        )
                    await asyncio.sleep(self.retry_delay)

        # Todos los modelos fallaron
        logger.error(
            f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} "
            f"Todos los modelos fallaron después de reintentos"
        )
        if feedback_callback:
            feedback_callback(UserFeedbackMessages.ALL_MODELS_FAILED)
        self.last_execution_stats = stats
        return None, None
