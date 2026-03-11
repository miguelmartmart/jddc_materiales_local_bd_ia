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
Versión: 1.1.0
"""

import asyncio
import logging
import json
import os
# DEVIA: backend/modules/chat/DEVIA_ROBUSTNESS.md
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from backend.core.config.model_manager import ModelManager
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.utils.constants import (
    ModelFallbackConfig,
    UserFeedbackMessages,
    LogPrefixes,
    LogEmojis
)

logger = logging.getLogger(__name__)

# IDs de modelos locales (red LAN JDDC, sin internet)
LOCAL_MODEL_IDS = {"jddcia-qwen3-30b", "jddcia-qwen3-30b-ip"}


def _load_ai_local_only() -> bool:
    """
    Lee el flag ai_local_only del config.json del chat.
    Si es True, solo se usan modelos locales (red LAN JDDC).
    Si es False, se usa el sistema de fallback multi-modelo completo.
    
    Para cambiar el modo: editar backend/modules/chat/config.json
      "ai_local_only": true   → Solo Qwen3 LAN (sin internet)
      "ai_local_only": false  → Fallback completo (Groq, Gemini, OpenAI, etc.)
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            return bool(cfg.get("ai_local_only", False))
    except Exception as e:
        logger.warning(f"[AI_LOCAL_ONLY] No se pudo leer config.json: {e}")
    return False


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
        """Inicializa el orchestrator con configuración de modelos."""
        self.model_manager = ModelManager()
        self.retry_delay = ModelFallbackConfig.RETRY_DELAY_SECONDS
        self.max_retries_per_model = ModelFallbackConfig.MAX_RETRIES_PER_MODEL
        
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
        
        logger.info(f"{LogPrefixes.AI_PROVIDER} {LogEmojis.SEARCH} Modelos disponibles ordenados por Prioridad:")
        if not sorted_models:
            logger.warning(f"  {LogEmojis.WARNING} No se encontraron modelos habilitados.")
            
        for idx, model in enumerate(sorted_models, 1):
            marker = "⭐ " if model['id'] == preferred_model_id else ""
            logger.info(f"  {idx}. {marker}{model.get('name')} (Score: {model.get('score')})")
        
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
            
            # Crear configuración
            ai_config_params = {
                'api_key': api_key,
                'model': model_config['model_id']
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
            logger.error(
                f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} "
                f"Error con {model_name}: {str(e)}"
            )
            # Try to extract status code if available
            err_code = getattr(e, "status_code", None)
            if not err_code and hasattr(e, "response") and hasattr(e.response, "status_code"):
                err_code = e.response.status_code
            
            self.model_manager.report_result(model_id, False, error_type=str(err_code) if err_code else None, error_msg=str(e))
            return None
    
    async def execute_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        images: Optional[List[str]] = None,
        feedback_callback: Optional[callable] = None,
        preferred_model_id: str = None
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
        prioritized_models = self._get_prioritized_models(preferred_model_id)
        
        if not prioritized_models:
            logger.error(f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} No hay modelos disponibles")
            if feedback_callback:
                feedback_callback(UserFeedbackMessages.ALL_MODELS_FAILED)
            return None, None

        # --- MODO AI_LOCAL_ONLY ---
        # Lee el flag en cada llamada (sin reiniciar el servidor) para que el cambio
        # en config.json surta efecto inmediatamente.
        ai_local_only = _load_ai_local_only()
        if ai_local_only:
            local_models = [m for m in prioritized_models if m.get('id') in LOCAL_MODEL_IDS]
            if local_models:
                logger.info(
                    f"{LogPrefixes.AI_PROVIDER} 🔒 Modo AI_LOCAL_ONLY activo — "
                    f"usando solo modelos LAN: {[m['name'] for m in local_models]}"
                )
                prioritized_models = local_models
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
        for model_idx, model_config in enumerate(prioritized_models):
            model_name = model_config.get('name', 'Unknown')
            model_id = model_config.get('id', '')
            
            # Notificar cambio de modelo (excepto el primero)
            if model_idx > 0 and feedback_callback:
                feedback_callback(
                    UserFeedbackMessages.SWITCHING_MODEL.format(model_name=model_name)
                )
            
            # Intentar con este modelo (1 intento inicial + reintentos)
            for attempt in range(1, self.max_retries_per_model + 2):
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
                                max_attempts=self.max_retries_per_model + 1
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
                    return response, model_id
                
                # Si falló y quedan reintentos, esperar
                if attempt < self.max_retries_per_model + 1:
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
        
        return None, None
