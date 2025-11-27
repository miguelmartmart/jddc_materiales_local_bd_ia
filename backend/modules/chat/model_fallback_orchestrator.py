"""
Model Fallback Orchestrator - Sistema robusto de fallback entre modelos IA

Este módulo implementa un sistema de reintentos y fallback entre múltiples modelos
de IA para garantizar la generación exitosa de consultas SQL.

Características:
- Reintentos automáticos con delays configurables
- Fallback entre modelos ordenados por prioridad
- Logging detallado de cada intento
- Feedback claro al usuario durante el proceso

Autor: DEVIA System
Versión: 1.0.0
"""

import asyncio
import logging
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
        
    def _get_prioritized_models(self) -> List[Dict[str, Any]]:
        """
        Obtiene lista de modelos disponibles ordenados por prioridad.
        
        Returns:
            Lista de configuraciones de modelos ordenada por prioridad descendente
        """
        all_models = self.model_manager.list_models()
        enabled_models = [m for m in all_models if m.get('enabled', False)]
        
        # Ordenar por prioridad definida en constantes
        def get_priority(model: Dict[str, Any]) -> int:
            model_id = model.get('id', '')
            return ModelFallbackConfig.MODEL_PRIORITY.get(model_id, 0)
        
        sorted_models = sorted(enabled_models, key=get_priority, reverse=True)
        
        logger.info(f"{LogPrefixes.AI_PROVIDER} {LogEmojis.SEARCH} Modelos disponibles ordenados por prioridad:")
        for idx, model in enumerate(sorted_models, 1):
            priority = get_priority(model)
            logger.info(f"  {idx}. {model.get('name')} (prioridad: {priority})")
        
        return sorted_models
    
    async def _try_model(
        self,
        model_config: Dict[str, Any],
        system_prompt: str,
        user_message: str,
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
                system_instruction=system_prompt
            )
            
            if response:
                logger.info(
                    f"{LogPrefixes.AI_PROVIDER} {LogEmojis.SUCCESS} "
                    f"Respuesta exitosa de {model_name}"
                )
                return response
            else:
                logger.warning(
                    f"{LogPrefixes.AI_PROVIDER} {LogEmojis.WARNING} "
                    f"Respuesta vacía de {model_name}"
                )
                return None
                
        except Exception as e:
            logger.error(
                f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} "
                f"Error con {model_name}: {str(e)}"
            )
            return None
    
    async def execute_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        feedback_callback: Optional[callable] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Ejecuta generación de respuesta con fallback entre modelos.
        
        Args:
            system_prompt: Prompt del sistema
            user_message: Mensaje del usuario
            feedback_callback: Función opcional para enviar feedback al usuario
            
        Returns:
            Tupla (respuesta, model_id) o (None, None) si todos fallan
        """
        prioritized_models = self._get_prioritized_models()
        
        if not prioritized_models:
            logger.error(f"{LogPrefixes.AI_PROVIDER} {LogEmojis.ERROR} No hay modelos disponibles")
            if feedback_callback:
                feedback_callback(UserFeedbackMessages.ALL_MODELS_FAILED)
            return None, None
        
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
