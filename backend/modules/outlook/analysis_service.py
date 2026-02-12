import logging
from collections import Counter
from typing import List, Dict, Any, Optional
from datetime import datetime

import json
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

class EmailAnalyzer:
    def __init__(self):
        # Initialize without specific provider to allow dynamic fallback
        self.ai = None
        from backend.modules.interaction_history.service import InteractionHistoryService
        self.history = InteractionHistoryService()
        
        # Initialize Anonymizer
        try:
            from backend.modules.anonymizer.service import AnonymizerService
            self.anonymizer = AnonymizerService()
        except Exception as e:
            logger.warning(f"Failed to initialize Anonymizer: {e}")
            self.anonymizer = None

    def calculate_stats(self, emails: List[Dict], total_unread: int = 0) -> Dict[str, Any]:
        """Calculates deterministic statistics from email list."""
        
        # --- EXCLUSION FILTERING ---
        from .analysis_config import analysis_config
        filtered_emails = [e for e in emails if not analysis_config.should_exclude(e)]
        
        # Adjust total_unread if we filtered out unread emails?
        # Ideally, we should filter unread count too, but that comes from API directly.
        # For this function, we just operate on the list provided.
        emails = filtered_emails
        # ---------------------------

        if not emails:
            return {"total_analyzed": 0, "unread_total": total_unread, "daily_breakdown": [], "emails_with_attachments": 0}

        # Structure: Map Date -> { total, unread, read, senders: [] }
        import email.utils
        
        # Translation map for day names
        days_map = {
            'Mon': 'Lunes', 'Tue': 'Martes', 'Wed': 'Miércoles', 
            'Thu': 'Jueves', 'Fri': 'Viernes', 'Sat': 'Sábado', 'Sun': 'Domingo'
        }
        
        daily_stats = {}
        
        for e in emails:
            date_raw = str(e.get('date', ''))
            is_read = e.get('is_read', False)
            sender = e.get('sender', 'Desconocido')
            if "<" in sender and ">" in sender:
                sender = sender.split("<")[1].split(">")[0]
            
            try:
                # Parse RFC 2822 date
                dt_tuple = email.utils.parsedate_tz(date_raw)
                if dt_tuple:
                    dt = datetime.fromtimestamp(email.utils.mktime_tz(dt_tuple))
                    
                    # Group by "YYYY-MM-DD" for sorting, but display "DayName"
                    sort_key = dt.strftime('%Y-%m-%d')
                    day_name_en = dt.strftime('%a')
                    day_name_es = days_map.get(day_name_en, day_name_en)
                    display_key = f"{day_name_es}" # Just day name or full date if preferred by user
                    
                    if sort_key not in daily_stats:
                        daily_stats[sort_key] = {
                            "date": sort_key,
                            "day_name": day_name_es,
                            "total": 0,
                            "unread": 0,
                            "read": 0,
                            "senders": []
                        }
                    
                    daily_stats[sort_key]["total"] += 1
                    if is_read:
                        daily_stats[sort_key]["read"] += 1
                    else:
                        daily_stats[sort_key]["unread"] += 1
                    
                    daily_stats[sort_key]["senders"].append(sender)
            except:
                pass
                
        # Convert to sorted list
        timeline = []
        for key in sorted(daily_stats.keys(), reverse=True): # Newest days first
            stat = daily_stats[key]
            # Compress senders (top 5 unique)
            senders_counts = Counter(stat['senders']).most_common(5)
            senders_str = ", ".join([f"{name} ({count})" if count > 1 else name for name, count in senders_counts])
            
            timeline.append({
                "date": stat["day_name"], # Use day name as requested
                "full_date": stat["date"],
                "counts": f"{stat['unread']} sin leer, {stat['read']} leídos",
                "senders": senders_str
            })
        
        attach_count = sum(1 for e in emails if e.get('attachments') and len(e['attachments']) > 0)
        
        return {
            "total_analyzed": len(emails),
            "unread_total": total_unread,
            "daily_breakdown": timeline,
            "emails_with_attachments": attach_count
        }

    async def _try_generate(self, context: str, schema: dict) -> Dict[str, Any]:
        """Tries to generate response using available enabled models."""
        from backend.core.config.model_manager import model_manager
        
        # Get smart-sorted models (Elite > High > Score)
        models_to_try = model_manager.list_models(enabled_only=True, capability="text")

        
        last_error = None

        failed_providers = set()
        
        for model_config in models_to_try:
            model_id = model_config['id']
            provider_name = model_config.get('provider')
            
            # FAIL-FAST: Skip if this provider already failed with a critical error
            if provider_name in failed_providers:
                continue

            try:
                # 1. Get Provider
                provider = AIFactory.get_provider(provider_name)
                
                # 2. Configure
                api_key = model_config.get('api_key')
                if not api_key:
                    continue # Skip if no key (e.g. env var missing)

                config_dict = {
                    'api_key': api_key,
                    'model': model_config['model_id']
                }
                if model_config.get('base_url'):
                    config_dict['base_url'] = model_config['base_url']
                if model_config.get('headers'):
                    config_dict['headers'] = model_config['headers']
                
                provider.configure(AIConfig(**config_dict))

                logger.info(f"Analyzing with model: {model_id} ({provider_name}) (Score: {model_config.get('score')})")
                
                # --- LOGGING START ---
                prompt_text = f"Analiza este correo y extrae información estructurada:\n{context}"
                logger.info(f"\n{'='*50}\n[AI EMAIL ANALYSIS REQUEST] Model: {model_id}\nPROMPT:\n{prompt_text}\n{'='*50}")
                # --- LOGGING END ---

                # Taxonomy Guide for the AI
                taxonomy_guide = """
                GUÍA DE CATEGORIZACIÓN (ESTRICTA):
                1. Trabajo:
                   - Incluye: Ofertas de EMPLEO explícitas, propuestas de proyectos profesionales, mensajes de LinkedIn (conexiones, recruiters), comunicaciones internas de trabajo.
                   - NO INCLUYE: Ofertas de productos, servicios, software o descuentos.
                   - Subcategorías DESC: "Oferta de Ingeniero Senior", "Conexión de Recruiter", "Presupuesto Proyecto X".
                2. Publicidad:
                   - Incluye: Newsletters, promociones de productos, rebajas, ofertas comerciales (Black Friday, Fin de Año), spam comercial.
                   - CUALQUIER correo que diga "¡Oferta!", "Descuento", "Compra ahora" ES PUBLICIDAD.
                   - Subcategorías DESC: "Promo Fin de Año", "Newsletter de IA", "Oferta Software SaaS".
                3. Factura:
                   - Incluye: Recibos de compra, facturas, confirmaciones de pago, transacciones bancarias.
                   - Subcategorías DESC: "Recibo Google Play", "Factura Hosting", "Pago Suscripción".
                4. Notificación:
                   - Incluye: Alertas de seguridad, actualizaciones de estado, reembolsos, resumen semanal (digest), avisos de sistema.
                   - Subcategorías DESC: "Alerta de Seguridad", "Reembolso Aprobado", "Resumen Semanal Quora".
                5. Personal:
                   - Incluye: Correos de amigos, familia, o asuntos puramente personales no comerciales.
                   - Subcategorías DESC: "Mensaje de Juan", "Cena Familiar".

                REGLA DE ORO: La 'subcategory' debe ser DESCRIPTIVA basada EXCLUSIVAMENTE en el contenido del correo.
                
                ⛔ PROHIBIDO:
                - NO COPIES estos ejemplos si no aparecen en el correo.
                - NO inventes temas. Si no hay info suficiente, pon "Contenido Indefinido".
                - IGNORA pies de página legales, avisos de virus y texto de confidencialidad.

                CASOS ESPECIALES:
                - Si el correo es breve y menciona "adjunto", "aquí tienes", "presupuesto":
                  -> Summary: "Envío de documentación/presupuesto adjunto"
                  -> Category: "Trabajo" (o "Factura" si se menciona).
                  -> Subcategory: "Envío de Documentos".
                """

                response = await provider.generate_json(
                    prompt=prompt_text,
                    schema=schema,
                    system_instruction=f"Eres un asistente ejecutivo experto en clasificación de correos. {taxonomy_guide}"
                )
                
                # --- LOGGING START ---
                logger.info(f"\n{'='*50}\n[AI EMAIL ANALYSIS RESPONSE] Model: {model_id}\nDATA:\n{response}\n{'='*50}")
                # --- LOGGING END ---
                
                # Report Success
                model_manager.report_result(model_id, True)
                
                # --- HISTORY LOGGING (SUCCESS) ---
                self.history.log_interaction(
                    module="OUTLOOK",
                    action="ANALYSIS",
                    input_context=prompt_text[:2000], # Limit context size
                    output_result=json.dumps(response),
                    model_id=model_id,
                    metadata={"context": "Email Analysis Batch", "status": "SUCCESS"}
                )
                # -----------------------

                return response
            except Exception as e:
                logger.warning(f"Model {model_id} failed: {e}")
                
                # Determine error type for scoring
                error_str = str(e).lower()
                error_type = 'quota' if '429' in error_str or 'quota' in error_str else 'other'
                model_manager.report_result(model_id, False, error_type)
                
                # --- HISTORY LOGGING (FAILURE) ---
                self.history.log_interaction(
                    module="OUTLOOK",
                    action="ANALYSIS",
                    input_context=prompt_text[:2000] if 'prompt_text' in locals() else "Pre-prompt failure",
                    output_result=f"ERROR: {str(e)}",
                    model_id=model_id,
                    metadata={"context": "Email Analysis Batch", "status": "FAILURE", "error_type": error_type}
                )
                # -----------------------
                
                # FAIL-FAST: Mark provider as failed if critical
                if error_type == 'quota' or '401' in error_str:
                    logger.warning(f"CRITICAL ERROR (Combinable) for provider {provider_name}: {e}. Skipping other models from this provider.")
                    failed_providers.add(provider_name)
                
                last_error = e
                continue
        
        if last_error:
            raise last_error
        else:
            raise Exception("No available models found to process the request.")

    async def generate_reply_suggestion(self, email_context: str, sender: str) -> str:
        """Generates a draft reply based on the email context."""
        
        # Fallback template if AI fails
        fallback_template = f"""Estimado/a {sender.split('@')[0] if '@' in sender else sender},

Gracias por su correo.

[Por favor, complete aquí su respuesta]

Saludos cordiales,
[Su nombre]"""
        
        # --- ANONYMIZER INTEGRATION ---
        if self.anonymizer:
            email_context = self.anonymizer.anonymize_if_enabled(email_context, "outlook")

        prompt = f"""
        Actúa como un asistente ejecutivo profesional. 
        Redacta una respuesta de correo electrónico formal, amable y concisa para el siguiente correo recibido de '{sender}'.
        
        Contenido del correo original:
        "{email_context[:2000]}"
        
        Instrucciones:
        - Saludo apropiado.
        - Agradece el correo.
        - Dejar espacios [...] para que el usuario complete detalles específicos si faltan.
        - Despedida profesional.
        - Idioma: Español.
        - Solo devuelve el cuerpo del correo, sin introducciones ni explicaciones extra.
        """
        
        try:
            # Try to get an AI model using the same logic as analyze_content
            model = None
            failed_providers = set()
            
            # Use settings.AI_MODELS or model_manager to iterate
            # Ideally we should use model_manager to get specific models, but legacy code uses settings.AI_MODELS.
            # Let's align with model_manager for consistency if possible, or stick to existing logic but safe.
            # Actually, let's use model_manager if possible, but the original code iterates settings.AI_MODELS directly.
            # We will enhance the loop over settings.AI_MODELS to fail-fast.
            
            # Refactor to use model_manager for robustness
            from backend.core.config.model_manager import model_manager
            candidates = model_manager.list_models(enabled_only=True, capability="text")
            
            response_text = None
            
            for model_config in candidates:
                model_id = model_config['id']
                provider_name = model_config.get('provider')
                
                if provider_name in failed_providers:
                    continue
                    
                try:
                    ai_config = AIConfig(
                        provider=provider_name,
                        model=model_config.get('model_id'),
                        api_key=model_config.get('api_key'),
                        temperature=0.3
                    )
                    
                    if not ai_config.api_key: continue
                    
                    # Manual configuration if not using factory full loading
                    model = AIFactory.create(ai_config)
                    logger.info(f"Using model for reply: {model_config.get('model_id')} ({provider_name})")
                    
                    # --- LOGGING START ---
                    logger.info(f"\n{'='*50}\n[AI REPLY GENERATION REQUEST]\nPROMPT:\n{prompt}\n{'='*50}")
                    # --- LOGGING END ---
        
                    response = await model.generate_content_async(prompt)
                    response_text = response.text.strip()
                    
                    # --- LOGGING START ---
                    logger.info(f"\n{'='*50}\n[AI REPLY GENERATION RESPONSE]\nTEXT:\n{response_text}\n{'='*50}")
                    # --- LOGGING END ---
        
                    # --- HISTORY LOGGING (SUCCESS) ---
                    self.history.log_interaction(
                        module="OUTLOOK",
                        action="REPLY_SUGGESTION",
                        input_context=prompt[:2000],
                        output_result=response_text,
                        model_id=model_id,
                        metadata={"sender": sender, "status": "SUCCESS"}
                    )
                    # -----------------------
                    
                    model_manager.report_result(model_id, True)
                    return response_text
                    
                except Exception as e:
                    logger.warning(f"Model {model_config.get('model_id')} failed for reply: {e}")
                    
                    error_str = str(e).lower()
                    error_type = 'quota' if '429' in error_str or 'quota' in error_str else 'other'
                    
                    # --- HISTORY LOGGING (FAILURE) ---
                    self.history.log_interaction(
                        module="OUTLOOK",
                        action="REPLY_SUGGESTION",
                        input_context=prompt[:2000],
                        output_result=f"ERROR: {str(e)}",
                        model_id=model_config.get('id', 'unknown'),
                        metadata={"sender": sender, "status": "FAILURE", "error_type": error_type}
                    )
                    # -----------------------
                    
                    if error_type == 'quota' or '401' in error_str:
                         failed_providers.add(provider_name)

                    continue
            
            if not response_text:
                logger.warning("No AI model available for reply generation, using fallback template")
                return fallback_template
            
        except Exception as e:
            logger.error(f"Error generating reply suggestion: {e}")
            return fallback_template

    async def analyze_content(self, emails: List[Dict]) -> List[Dict]:
        """Summarizes each email and its attachments using AI."""
        # --- EXCLUSION FILTERING ---
        from .analysis_config import analysis_config
        filtered_emails = [e for e in emails if not analysis_config.should_exclude(e)]
        if len(filtered_emails) < len(emails):
            logger.info(f"Filtered {len(emails) - len(filtered_emails)} emails due to exclusion rules.")
        
        emails = filtered_emails
        # ---------------------------

        results = []
        
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Resumen rico en entidades (nombres, importes, puestos). Ej: 'Recibo de 4.99€ de Google Play' ó 'Oferta para puesto de Senior Dev en Startup'."},
                "category": {"type": "string", "enum": ["Trabajo", "Personal", "Notificación", "Factura", "Publicidad", "Otro"], "description": "Categoría principal según taxonomía."},
                "subcategory": {"type": "string", "description": "Tipo ESPECÍFICO y DESCRIPTIVO. No uses una sola palabra. Ej: 'Oferta de Ingeniero', 'Recibo de Suscripción', 'Newsletter de Tecnología'."},
                "priority": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
                "action_needed": {"type": "boolean", "description": "True si requiere acción del usuario (pagar, responder, confirmar)"},
                "attachments_analysis": {"type": "string", "description": "Resumen del contenido de los adjuntos si existen, o 'Sin adjuntos'"}
            },
            "required": ["summary", "category", "subcategory", "priority", "action_needed"]
        }

        for email in emails:
            # Base result structure (ensures ID/metadata always exists)
            # Clean attachments for frontend (remove content to reduce payload size)
            clean_attachments = []
            for att in email.get('attachments', []):
                clean_attachments.append({
                    "filename": att.get('filename'),
                    "content_type": att.get('content_type'),
                    "size": att.get('size', 0)
                })
            
            result_item = {
                "id": email['id'],
                "subject": email.get('subject', '(Sin Asunto)'),
                "sender": email.get('sender', 'Desconocido'),
                "date": email.get('date', ''),
                "is_read": email.get('is_read', False),
                "attachments": clean_attachments,  # Metadata only, no content
                "ai_data": {}
            }
            
            try:
                # Prepare context
                context = f"Asunto: {email.get('subject')}\nRemitente: {email.get('sender')}\nCuerpo: {email.get('body')[:3000]}" # Limit body
                
                atts = email.get('attachments', [])
                if atts:
                    context += "\nADJUNTOS:"
                    for att in atts:
                        context += f"\n- {att['filename']} ({att['content_type']})"
                        if att.get('content'):
                             # Limit attachment content significantly to save tokens
                             context += f"\n  Contenido: {att['content'][:1000]}"
                        else:
                             context += f"\n  (Binario o sin texto extraíble)"

                # --- ANONYMIZER INTEGRATION ---
                if self.anonymizer:
                    context = self.anonymizer.anonymize_if_enabled(context, "outlook")
                # ------------------------------

                # Try to generate with fallback
                ai_response = await self._try_generate(context, schema)
                result_item["ai_data"] = ai_response
                # Add body preview for frontend toggle
                result_item["ai_data"]["body_preview"] = email.get('body')[:15000] # Pass 15k chars
                
            except Exception as e:
                logger.error(f"Error AI analyzing email {email.get('id')}: {e}")
                result_item["ai_data"] = {
                    "summary": f"Error al analizar: {str(e)[:50]}...", 
                    "category": "Error", 
                    "priority": "Baja"
                }
            
            results.append(result_item)
        
        return results

    async def analyze_deeply(self, context: str) -> Dict[str, Any]:
        """Performs a deep analysis of a single email."""
        from backend.core.config.model_manager import model_manager

        # Use High or Elite models for deep analysis
        models_to_try = model_manager.list_models(enabled_only=True, capability="text")
        
        # Schema: STRICT STRUCTURE ONLY (No descriptions to avoid AI confusion)
        # Detailed descriptions are moved to the PROMPT.
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "useful_conclusions": {"type": "array", "items": {"type": "string"}},
                "action_items": {"type": "array", "items": {"type": "string"}},
                "key_dates": {"type": "array", "items": {"type": "string"}},
                "sentiment": {"type": "string"}
            },
            "required": ["summary", "useful_conclusions", "action_items", "key_dates", "sentiment"]
        }

        last_error = None
        failed_providers = set()
        
        for model_config in models_to_try:
            model_id = model_config['id']
            # ... (existing loop setup) ...
            provider_name = model_config.get('provider')
            
            # FAIL-FAST
            if provider_name in failed_providers:
                continue

            try:
                # 1. Provide & Configure
                provider = AIFactory.get_provider(provider_name)
                
                api_key = model_config.get('api_key')
                if not api_key: continue

                config_dict = {'api_key': api_key, 'model': model_config['model_id']}
                if model_config.get('base_url'): config_dict['base_url'] = model_config['base_url']
                
                provider.configure(AIConfig(**config_dict))
                
                logger.info(f"Deep Analysis with model: {model_id}")

                # --- ANONYMIZER INTEGRATION ---
                if self.anonymizer:
                    context = self.anonymizer.anonymize_if_enabled(context, "outlook")
                # ------------------------------

                prompt_text = f"""
                Realiza un ANÁLISIS PROFUNDO de este correo electrónico.
                Tu objetivo es extraer inteligencia accionable.

                CORREO:
                {context}
                
                DEBUG INFO: Context Length: {len(context)}

                GUÍA DE EXTRACCIÓN (Output Guidelines):
                1. summary: Resumen ejecutivo detallado del correo.
                2. useful_conclusions: Lista de conclusiones prácticas, deducciones o puntos clave.
                3. action_items: Lista de tareas o acciones explícitas o implícitas requeridas.
                4. key_dates: TODAS las fechas, plazos, horas o eventos mencionados.
                5. sentiment: Tono del correo (Urgente, Amable, Queja, etc) y estado emocional.
                """
                
                print(f"\n--- [DEBUG] START DEEP ANALYSIS ({model_id}) ---")
                print(f"PROMPT PREVIEW:\n{prompt_text[:500]}...")

                response = await provider.generate_json(
                    prompt=prompt_text, 
                    schema=schema,
                    system_instruction="Eres un analista de inteligencia empresarial. Tu trabajo es diseccionar comunicaciones y extraer valor crítico."
                )

                print(f"--- [DEBUG] AI RESPONSE ---")
                print(json.dumps(response, indent=2, ensure_ascii=False))
                print(f"--- [DEBUG] END DEEP ANALYSIS ---\n")

                
                model_manager.report_result(model_id, True)

                # --- HISTORY LOGGING (SUCCESS) ---
                self.history.log_interaction(
                    module="OUTLOOK",
                    action="DEEP_ANALYSIS",
                    input_context=prompt_text[:2000],
                    output_result=json.dumps(response),
                    model_id=model_id,
                    metadata={"context": "Deep Analysis Single Email", "status": "SUCCESS"}
                )
                # -----------------------

                return response

            except Exception as e:
                logger.warning(f"Deep Analysis Model {model_id} failed: {e}")
                
                error_str = str(e).lower()
                error_type = 'quota' if '429' in error_str or 'quota' in error_str else 'other'
                model_manager.report_result(model_id, False, error_type)

                # --- HISTORY LOGGING (FAILURE) ---
                self.history.log_interaction(
                    module="OUTLOOK",
                    action="DEEP_ANALYSIS",
                    input_context=prompt_text[:2000] if 'prompt_text' in locals() else "Pre-prompt failure",
                    output_result=f"ERROR: {str(e)}",
                    model_id=model_id,
                    metadata={"context": "Deep Analysis Single Email", "status": "FAILURE", "error_type": error_type}
                )
                # -----------------------
                
                if error_type == 'quota' or '401' in error_str:
                     failed_providers.add(provider_name)
                
                last_error = e
                continue
        
        if last_error:
            raise last_error
        else:
            raise Exception("No available models found for deep analysis.")

    async def generate_global_digest(self, analysis_results: List[Dict[str, Any]]) -> str:
        """Generates a global summary of the analyzed emails."""
        from backend.core.config.model_manager import model_manager
        
        if not analysis_results:
            return "No hay correos importantes para resumir."

        # Filter meaningful emails (ignore spam/promotions if possible, or just take top high priority)
        important_emails = [
            e for e in analysis_results 
            if e.get('ai_data') and e['ai_data'].get('category') in ['Trabajo', 'Factura', 'Notificación', 'Personal']
        ]

        if not important_emails:
            return "El buzón contiene solo correos de baja prioridad o publicidad."

        # Create a context string
        context_lines = []
        for e in important_emails[:15]: # Limit to top 15 to fit in context
            ai = e['ai_data']
            context_lines.append(f"- {e.get('subject')} (De: {e.get('sender')}): {ai.get('summary')} [{ai.get('priority')}]")
        
        context = "\n".join(context_lines)

        # Select Model
        model_config = model_manager.get_best_model(capability="text", preferred_provider="groq") or \
                       model_manager.get_best_model(capability="text")
        
        if not model_config:
            return "No se pudo generar el resumen global (Modelo no disponible)."

        try:
            provider = AIFactory.get_provider(model_config['provider'])
            api_key = model_config.get('api_key')
            config_dict = {'api_key': api_key, 'model': model_config['model_id']}
            if model_config.get('base_url'): config_dict['base_url'] = model_config['base_url']
            provider.configure(AIConfig(**config_dict))

            # --- ANONYMIZER INTEGRATION ---
            if self.anonymizer:
                context = self.anonymizer.anonymize_if_enabled(context, "outlook")
            # ------------------------------

            prompt = f"""
            Genera un RESUMEN GLOBAL EJECUTIVO (estilo "Morning Briefing") de estos correos.
            
            CORREOS:
            {context}

            OBJETIVO:
            - Destacar lo MÁS crítico que el usuario debe saber ya.
            - Mencionar facturas pendientes o tareas urgentes.
            - Ignorar trivialidades.
            - Formato: Un párrafo denso pero legible, usar emojis clave. Máximo 5 líneas.
            - Empieza directamente con el contenido.
            """

            response = await provider.generate_text(
                prompt=prompt, 
                system_instruction="Eres un asistente ejecutivo inteligente."
            )
            model_manager.report_result(model_config['id'], True)
            return response

        except Exception as e:
            logger.error(f"Global digest failed: {e}")
            return "No se pudo generar el resumen global debido a un error técnico."
