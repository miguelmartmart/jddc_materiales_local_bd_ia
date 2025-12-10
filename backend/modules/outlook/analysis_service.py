import logging
from collections import Counter
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

class EmailAnalyzer:
    def __init__(self):
        # Initialize without specific provider to allow dynamic fallback
        self.ai = None

    def calculate_stats(self, emails: List[Dict], total_unread: int = 0) -> Dict[str, Any]:
        """Calculates deterministic statistics from email list."""
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
                "date": stat["day_name"], // Use day name as requested
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
        
        # Get all enabled models
        enabled_models = model_manager.list_models(enabled_only=True)
        if not enabled_models:
            raise Exception("No AI models enabled in configuration.")

        # Sort preference: 'flash' > 'gemini' > others (heuristic for speed/cost)
        def sort_key(m):
            mid = m['id'].lower()
            if 'flash' in mid: return 0
            if 'gemini' in mid: return 1
            if 'gpt' in mid: return 2
            return 3
            
        models_to_try = sorted(enabled_models, key=sort_key)
        
        last_error = None

        for model_config in models_to_try:
            model_id = model_config['id']
            try:
                # 1. Get Provider
                provider_name = model_config['provider']
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

                logger.info(f"Analyzing with model: {model_id} ({provider_name})")
                return await provider.generate_json(
                    prompt=f"Analiza este correo y extrae información estructurada:\n{context}",
                    schema=schema,
                    system_instruction="Eres un asistente ejecutivo de IA. Tu misión es leer correos y extraer resúmenes precisos y útiles. Sé breve y directo."
                )
            except Exception as e:
                logger.warning(f"Model {model_id} failed: {e}")
                last_error = e
                continue
        
        raise last_error

    async def analyze_content(self, emails: List[Dict]) -> List[Dict]:
        """Summarizes each email and its attachments using AI."""
        results = []
        
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Resumen muy breve (1-2 frases) del propósito del correo"},
                "category": {"type": "string", "enum": ["Trabajo", "Personal", "Notificación", "Spam", "Factura", "Otro"]},
                "priority": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
                "attachments_analysis": {"type": "string", "description": "Resumen del contenido de los adjuntos si existen, o 'Sin adjuntos'"}
            },
            "required": ["summary", "category", "priority"]
        }

        for email in emails:
            # Base result structure (ensures ID/metadata always exists)
            result_item = {
                "id": email['id'],
                "subject": email.get('subject', '(Sin Asunto)'),
                "sender": email.get('sender', 'Desconocido'),
                "date": email.get('date', ''),
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

                # Try to generate with fallback
                ai_response = await self._try_generate(context, schema)
                result_item["ai_data"] = ai_response
                
            except Exception as e:
                logger.error(f"Error AI analyzing email {email.get('id')}: {e}")
                result_item["ai_data"] = {
                    "summary": f"Error al analizar: {str(e)[:50]}...", 
                    "category": "Error", 
                    "priority": "Baja"
                }
            
            results.append(result_item)
        
        return results
        """Tries to generate response using available models in order of preference."""
        
        # Models to try in order. 
        # Note: 'gemini' provider usually maps to a specific model in config, 
        # but we can re-configure it or try different provider keys if we had them.
        # For this project, we assume 'gemini' provider wraps the Google GenAI lib.
        # We will try to re-configure the provider with different model names if the first fails.
        
        models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro", "gemini-pro"]
        
        last_error = None

        for model_name in models_to_try:
            try:
                # Re-init provider with specific model
                provider = AIFactory.get_provider("gemini")
                
                if settings.GEMINI_API_KEY:
                    provider.configure(AIConfig(
                        api_key=settings.GEMINI_API_KEY,
                        model=model_name
                    ))
                else:
                    raise Exception("No GEMINI_API_KEY found")

                logger.info(f"Analyzing with model: {model_name}")
                return await provider.generate_json(
                    prompt=f"Analiza este correo y extrae información estructurada:\n{context}",
                    schema=schema,
                    system_instruction="Eres un asistente ejecutivo de IA. Tu misión es leer correos y extraer resúmenes precisos y útiles. Sé breve y directo."
                )
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
                last_error = e
                continue
        
        raise last_error

    async def analyze_content(self, emails: List[Dict]) -> List[Dict]:
        """Summarizes each email and its attachments using AI."""
        results = []
        
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Resumen muy breve (1-2 frases) del propósito del correo"},
                "category": {"type": "string", "enum": ["Trabajo", "Personal", "Notificación", "Spam", "Factura", "Otro"]},
                "priority": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
                "attachments_analysis": {"type": "string", "description": "Resumen del contenido de los adjuntos si existen, o 'Sin adjuntos'"}
            },
            "required": ["summary", "category", "priority"]
        }

        for email in emails:
            # Base result structure (ensures ID/metadata always exists)
            result_item = {
                "id": email['id'],
                "subject": email.get('subject', '(Sin Asunto)'),
                "sender": email.get('sender', 'Desconocido'),
                "date": email.get('date', ''),
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

                # Try to generate with fallback
                ai_response = await self._try_generate(context, schema)
                result_item["ai_data"] = ai_response
                
            except Exception as e:
                logger.error(f"Error AI analyzing email {email.get('id')}: {e}")
                result_item["ai_data"] = {
                    "summary": f"Error al analizar: {str(e)[:50]}...", 
                    "category": "Error", 
                    "priority": "Baja"
                }
            
            results.append(result_item)
        
        return results
        """Calculates deterministic statistics from email list."""
        if not emails:
            return {"total_analyzed": 0, "unread_total": total_unread, "senders_breakdown": [], "timeline": [], "emails_with_attachments": 0}

        # 1. Senders
        senders = [e.get('sender', 'Desconocido') for e in emails]
        sender_counts = Counter(senders).most_common(10) # Top 10

        # 2. Timeline (Day)
        timeline = []
        for e in emails:
            # Date format example: "Wed, 10 Dec 2025 17:08:56 +0000"
            date_raw = str(e.get('date', ''))
            # Try to grab just the "Wed, 10 Dec 2025" part.
            # Splitting by space usually works well for RFC2822
            parts = date_raw.split()
            if len(parts) >= 4:
                day_str = " ".join(parts[:4])
                timeline.append(day_str)
            else:
                timeline.append(date_raw[:16] if len(date_raw) > 16 else date_raw)
        
        timeline_counts = Counter(timeline).most_common(10)
        
        # 3. Attachments
        attach_count = sum(1 for e in emails if e.get('attachments') and len(e['attachments']) > 0)
        
        return {
            "total_analyzed": len(emails),
            "unread_total": total_unread,
            "senders_breakdown": [{"name": k, "value": v} for k, v in sender_counts],
            "timeline": [{"date": k, "count": v} for k, v in timeline_counts],
            "emails_with_attachments": attach_count
        }

    async def analyze_content(self, emails: List[Dict]) -> List[Dict]:
        """Summarizes each email and its attachments using AI."""
        # self.ai is now dynamic, so we use _try_generate

        results = []
        
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Resumen muy breve (1-2 frases) del propósito del correo"},
                "category": {"type": "string", "enum": ["Trabajo", "Personal", "Notificación", "Spam", "Factura", "Otro"]},
                "priority": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
                "attachments_analysis": {"type": "string", "description": "Resumen del contenido de los adjuntos si existen, o 'Sin adjuntos'"}
            },
            "required": ["summary", "category", "priority"]
        }

        for email in emails:
            # Base result structure (ensures ID/metadata always exists)
            result_item = {
                "id": email['id'],
                "subject": email.get('subject', '(Sin Asunto)'),
                "sender": email.get('sender', 'Desconocido'),
                "date": email.get('date', ''),
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

                # Correctly call the internal fallback method
                ai_response = await self._try_generate(context, schema)
                result_item["ai_data"] = ai_response
                
            except Exception as e:
                logger.error(f"Error AI analyzing email {email.get('id')}: {e}")
                result_item["ai_data"] = {
                    "summary": f"no se pudo analizar: {str(e)[:100]}", 
                    "category": "Error", 
                    "priority": "Baja",
                    "attachments_analysis": "Error"
                }
            
            results.append(result_item)
        
        return results
