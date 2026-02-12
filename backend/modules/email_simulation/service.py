import logging
import json
from typing import Dict, Any, Optional
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

class EmailSimulationService:
    async def simulate_next_step(self, email_data: Dict) -> Dict[str, Any]:
        """
        Simulates the next step for a given email (REPLY, IGNORE, USER_ACTION).
        Returns a structured dictionary with the action, reasoning, and simulated content.
        """
        
        # 1. Prepare Context
        context = f"""
        Asunto: {email_data.get('subject', '(Sin Asunto)')}
        Remitente: {email_data.get('sender', 'Desconocido')}
        Cuerpo: {email_data.get('body', '')[:4000]}
        """

        # 2. Define Schema
        schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string", 
                    "enum": ["REPLY", "IGNORE", "USER_ACTION"],
                    "description": "REPLY: La IA puede redactar una respuesta autónoma. IGNORE: Spam o irrelevante. USER_ACTION: Requiere que el usuario haga algo manual fuera del correo (pagar, llamar, verificar en sistema)."
                },
                "reasoning": {
                    "type": "string",
                    "description": "Breve explicación de por qué se eligió esta acción."
                },
                "simulation_content": {
                    "type": "string",
                    "description": "Si es REPLY: El borrador del correo de respuesta. Si es USER_ACTION: Descripción paso a paso de lo que debe hacer el usuario. Si es IGNORE: Explicación de por qué se ignora."
                }
            },
            "required": ["action", "reasoning", "simulation_content"]
        }

        # 3. Get Models (Iterate for resilience)
        from backend.core.config.model_manager import model_manager
        from backend.modules.interaction_history.service import InteractionHistoryService
        
        history = InteractionHistoryService()
        
        candidates = model_manager.list_models(enabled_only=True, capability="text")
        failed_providers = set()
        last_error = None
        
        for model_config in candidates:
            # FAIL-FAST
            provider_name = model_config.get('provider')
            if provider_name in failed_providers:
                continue
                
            try:
                logger.info(f"Simulating email action with model: {model_config['model_id']}")
                
                provider = AIFactory.get_provider(provider_name)
                
                # Configure provider
                api_key = model_config.get('api_key')
                if not api_key: continue
                
                config_dict = {'api_key': api_key, 'model': model_config['model_id']}
                if model_config.get('base_url'): config_dict['base_url'] = model_config['base_url']
                
                provider.configure(AIConfig(**config_dict))
    
                # 4. Generate
                prompt = f"""
                Analiza el siguiente correo y determina el mejor SIGUIENTE PASO.
                Actúa como un asistente ejecutivo altamente eficiente.
    
                CORREO:
                {context}
    
                OBJETIVO:
                Simular la acción que tomaría un humano experto.
                """
    
                print(f"\n--- [DEBUG] START SIMULATION ({model_config['model_id']}) ---")
                print(f"CONTEXT PREVIEW:\n{context[:500]}...")

                response = await provider.generate_json(
                    prompt=prompt,
                    schema=schema,
                    system_instruction="Eres un motor de simulación de decisiones empresariales."
                )
                
                print(f"--- [DEBUG] AI SIMULATION RESPONSE ---")
                print(json.dumps(response, indent=2, ensure_ascii=False))
                print(f"--- [DEBUG] END SIMULATION ---\n")
                
                # Report success
                model_manager.report_result(model_config['id'], True)
                
                # --- HISTORY LOGGING (SUCCESS) ---
                history.log_interaction(
                    module="SIMULATION",
                    action="SIMULATE_NEXT_STEP",
                    input_context=context[:2000],
                    output_result=json.dumps(response),
                    model_id=model_config['model_id'],
                    metadata={"subject": email_data.get('subject'), "sender": email_data.get('sender'), "status": "SUCCESS"}
                )
                # -----------------------
    
                return response
    
            except Exception as e:
                logger.warning(f"Error in email simulation with {model_config['id']}: {e}")
                
                error_str = str(e).lower()
                error_type = 'quota' if '429' in error_str or 'quota' in error_str else 'other'
                
                model_manager.report_result(model_config['id'], False, error_type)
                
                # --- HISTORY LOGGING (FAILURE) ---
                history.log_interaction(
                    module="SIMULATION",
                    action="SIMULATE_NEXT_STEP",
                    input_context=context[:2000],
                    output_result=f"ERROR: {str(e)}",
                    model_id=model_config['model_id'],
                    metadata={"subject": email_data.get('subject'), "sender": email_data.get('sender'), "status": "FAILURE", "error_type": error_type}
                )
                # -----------------------
                
                if error_type == 'quota' or '401' in error_str:
                     failed_providers.add(provider_name)
                
                last_error = e
                continue
                
        if last_error:
            raise last_error
        else:
             raise Exception("No registered AI models available or all failed.")
