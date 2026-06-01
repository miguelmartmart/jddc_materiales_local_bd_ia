from typing import Dict, Any, List
# DEVIA: backend/modules/chat/DEVIA.md
import json
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.config.settings import settings
from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import (
    DBConstants, DBDefaults, LogPrefixes, LogEmojis,
    SQLDelimiters, SQLLimits, SQLKeywords
)
from backend.drivers.db.firebird_queries import QUERY_TABLES, QUERY_TABLE_COLUMNS
from backend.core.config.database_metadata import get_semantic_schema, get_table_for_concept
from backend.modules.db_explorer.context_retriever import get_context_retriever
from backend.modules.chat.sql_corrector import SQLCorrector
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
import logging
import os
import base64
import asyncio

# Image Services Integration
from backend.modules.images.service import ImageService
from backend.modules.images.core.storage import LocalStorageManager

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# ─── Delegación a chat_voice_interpreter (única fuente de verdad) ─────────────
from backend.modules.chat.chat_voice_interpreter import (
    interpret_results_for_voice as _interpret_voice_impl,
    clean_for_tts as _clean_tts_impl,
)


def interpret_results_for_voice(message: str, results: list, sql_query: str) -> str:
    """
    Interpreta resultados de BD de forma DETERMINISTA para clientes de voz (gafas Meta).

    DELEGACIÓN: Esta función delega a chat_voice_interpreter.py (única fuente de verdad).
    El fix del bug TOTAL/COUNT está en chat_voice_interpreter._interpret_single_value.

    Elimina la segunda llamada a IA para clientes de voz, reduciendo el tiempo total
    de respuesta de ~42s a ~22s y evitando timeouts en Android (60s).
    """
    return _interpret_voice_impl(message, results, sql_query)


def _interpret_results_for_voice_LEGACY(message: str, results: list, sql_query: str) -> str:
    """LEGACY — NO usar. Solo referencia histórica. BUG: confunde TOTAL con COUNT."""
    if not results:
        return "No encontré ningún resultado para tu consulta."
    
    n = len(results)
    
    # Caso 1: Resultado de COUNT/SUM/AVG/MAX/MIN (una sola fila, una sola columna numérica)
    if n == 1 and len(results[0]) == 1:
        key = list(results[0].keys())[0]
        val = results[0][key]
        
        # Detectar tipo de consulta por palabras clave en el mensaje
        msg_lower = message.lower()
        
        if any(w in msg_lower for w in ['cuántos', 'cuantos', 'total', 'número', 'numero', 'cantidad']):
            # Formatear número
            if isinstance(val, float):
                val_str = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            else:
                val_str = str(val)
            
            # Detectar qué se está contando
            if any(w in msg_lower for w in ['artículo', 'articulo', 'producto']):
                return f"Hay {val_str} artículos en la base de datos."
            elif any(w in msg_lower for w in ['cliente']):
                return f"Hay {val_str} clientes en la base de datos."
            elif any(w in msg_lower for w in ['factura']):
                return f"Hay {val_str} facturas en la base de datos."
            elif any(w in msg_lower for w in ['proveedor']):
                return f"Hay {val_str} proveedores en la base de datos."
            elif any(w in msg_lower for w in ['pedido']):
                return f"Hay {val_str} pedidos en la base de datos."
            elif any(w in msg_lower for w in ['albarán', 'albaran']):
                return f"Hay {val_str} albaranes en la base de datos."
            else:
                return f"El resultado es {val_str}."
        
        elif any(w in msg_lower for w in ['suma', 'total', 'importe', 'facturado']):
            if isinstance(val, (int, float)):
                val_str = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                return f"El total es {val_str} euros."
            return f"El resultado es {val}."
        
        else:
            return f"El resultado es {val}."
    
    # Caso 2: Una sola fila con múltiples columnas (detalle de un registro)
    if n == 1:
        row = results[0]
        parts = []
        for key, val in row.items():
            if val is None:
                continue
            key_clean = key.replace('_', ' ').title()
            if isinstance(val, float):
                val_str = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                parts.append(f"{key_clean}: {val_str}")
            else:
                parts.append(f"{key_clean}: {val}")
        
        if parts:
            return "El registro encontrado tiene: " + ", ".join(parts) + "."
        return "Se encontró un registro pero sin datos relevantes."
    
    # Caso 3: Múltiples filas — extraer el campo más relevante (NOMBRE, DESCRIPCION, etc.)
    # Prioridad de campos para mostrar en voz
    VOICE_PRIORITY_FIELDS = [
        'NOMBRE', 'DESCRIPCION', 'DESCRIPCIONCORTA', 'RAZONSOCIAL',
        'NOMBRE_CLIENTE', 'NOMBRE_ARTICULO', 'TITULO', 'CONCEPTO',
        'NUMERO', 'CODIGO', 'REFERENCIA', 'REF'
    ]
    
    # Encontrar el campo más relevante disponible en los resultados
    available_keys = list(results[0].keys()) if results else []
    display_key = None
    for priority_key in VOICE_PRIORITY_FIELDS:
        for avail_key in available_keys:
            if avail_key.upper() == priority_key:
                display_key = avail_key
                break
        if display_key:
            break
    
    # Si no hay campo prioritario, usar el primero disponible
    if not display_key and available_keys:
        display_key = available_keys[0]
    
    if not display_key:
        return f"Se encontraron {n} resultados."
    
    # Extraer valores del campo seleccionado
    values = []
    for row in results:
        val = row.get(display_key)
        if val is not None:
            val_str = str(val).strip()
            if val_str:
                values.append(val_str)
    
    if not values:
        return f"Se encontraron {n} resultados pero sin datos de texto."
    
    # Formatear según cantidad
    msg_lower = message.lower()
    
    # Detectar si el usuario pidió un número específico
    import re as _re
    num_match = _re.search(r'\b(un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|\d+)\b', msg_lower)
    
    if len(values) == 1:
        return f"El resultado es: {values[0]}."
    elif len(values) == 2:
        return f"Los dos resultados son: {values[0]} y {values[1]}."
    elif len(values) <= 5:
        last = values[-1]
        rest = values[:-1]
        return f"Los {len(values)} resultados son: {', '.join(rest)} y {last}."
    else:
        # Más de 5: mostrar los primeros 3 y decir cuántos hay en total
        primeros = values[:3]
        return (
            f"Encontré {n} resultados. Los primeros son: "
            f"{', '.join(primeros)}, y así sucesivamente."
        )


def clean_for_tts(text: str) -> str:
    """
    Limpia el texto de formato Markdown para que el TTS de las gafas Meta
    lo lea de forma natural, sin decir 'asterisco', 'almohadilla', etc.
    
    Se aplica SIEMPRE a todas las respuestas del backend.
    """
    import re
    
    # 1. Negrita y cursiva: **texto** → texto, *texto* → texto, __texto__ → texto
    text = re.sub(r'\*{1,3}([^*\n]+?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_\n]+?)_{1,3}', r'\1', text)
    
    # 2. Código inline: `texto` → texto
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 3. Bloques de código: ```...``` → eliminar completamente (no se leen en voz)
    text = re.sub(r'```[\s\S]*?```', '', text, flags=re.MULTILINE)
    
    # 4. Encabezados: ### Título → Título
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # 5. Listas numeradas: "1. Elemento" → "Elemento" (el TTS ya dice el número si está en el texto)
    #    Pero mantenemos el número para que suene natural: "1. X" → "Primero, X" no, mejor "uno: X"
    #    Simplemente quitamos el punto: "1. " → "1, "
    text = re.sub(r'^(\d+)\.\s+', r'\1, ', text, flags=re.MULTILINE)
    
    # 6. Listas con guión o asterisco: "- Elemento" → "Elemento"
    text = re.sub(r'^[\-\*\•]\s+', '', text, flags=re.MULTILINE)
    
    # 7. Links Markdown: [texto](url) → texto
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # 8. Imágenes Markdown: ![alt](url) → eliminar
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
    
    # 9. Líneas horizontales: --- o *** → eliminar
    text = re.sub(r'^[\-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # 10. Emojis problemáticos para TTS: mantener solo los que suenan bien
    #     Los emojis en general el TTS los ignora o los lee raro, los eliminamos
    text = re.sub(r'[^\w\s\.,;:!¡?¿\-\(\)\/€%ñÑáéíóúÁÉÍÓÚüÜ\n]', ' ', text)
    
    # 11. Múltiples espacios → un espacio
    text = re.sub(r'  +', ' ', text)
    
    # 12. Múltiples líneas vacías → una sola línea vacía
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 13. Trim final
    text = text.strip()
    
    return text


class ChatService:
    
    def __init__(self):
        self.sql_corrector = SQLCorrector()
        self.sql_normalizer = FirebirdSQLNormalizer()
        self.model_orchestrator = ModelFallbackOrchestrator()
        self._load_config()
        self.image_service = ImageService()
        self.storage = LocalStorageManager()
        
    async def _analyze_images(self, images: List[str]) -> str:
        """
        Analyzes uploaded images using the ImageService.
        Returns a combined description string.
        """
        descriptions = []
        for i, img_data in enumerate(images):
            try:
                # Decode Base64 (handle data:image/png;base64, prefix)
                if "," in img_data:
                    header, encoded = img_data.split(",", 1)
                    mime_type = header.split(":")[1].split(";")[0]
                else:
                    encoded = img_data
                    mime_type = "image/png" # Default fallback
                
                content = base64.b64decode(encoded)
                
                # Save to temp storage
                path = await self.storage.save_file(content, mime_type, job_id=f"chat_analysis_{i}", role="temp")
                
                # Call Image Service
                result = await self.image_service.describe_image(user_id="chat_user", image_path=path)
                desc = result.get("description", "No description available")
                descriptions.append(f"Imagen {i+1}: {desc}")
                
            except Exception as e:
                logger.error(f"Error analysing image {i}: {e}")
                descriptions.append(f"Imagen {i+1}: Error al analizar ({str(e)})")
        
        return "\n".join(descriptions)

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config = {"max_sql_retries": DBDefaults.MAX_SQL_CORRECTION_RETRIES}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config.update(json.load(f))
            except Exception as e:
                logger.warning(f"Error loading chat config: {e}")


    async def _ai_requires_database(self, message: str) -> bool:
        """
        Usa la IA local (Qwen3) para detectar si el mensaje requiere consultar la BD.
        Llamada ultraligera: system prompt mínimo, respuesta de 1 token (SI/NO).

        Devuelve True  → el mensaje necesita SQL/datos de la BD
        Devuelve False → es conversacional, filosófico, general, etc.

        Fallback determinista si la IA falla: busca palabras clave de datos.
        """
        try:
            system_prompt = (
                "Eres un clasificador de intenciones. "
                "Responde SOLO con 'SI' o 'NO', sin explicaciones.\n"
                "Pregunta: ¿Este mensaje requiere consultar una base de datos "
                "de empresa (facturas, clientes, presupuestos, stock, ventas, etc.)?\n"
                "SI = necesita datos de BD. NO = es conversacional, filosófico o general."
            )
            response, _ = await self.model_orchestrator.execute_with_fallback(
                system_prompt=system_prompt,
                user_message=message,
                preferred_model_id="jddcia-qwen3-30b",
            )
            if response:
                answer = response.strip().upper()[:10]
                needs_db = answer.startswith("SI") or answer.startswith("SÍ") or answer.startswith("YES")
                logger.info(f"[INTENT] IA clasificacion BD: '{answer}' → needs_db={needs_db}")
                return needs_db
        except Exception as e:
            logger.warning(f"[INTENT] IA clasificacion fallo ({e}), usando fallback determinista")

        # Fallback determinista si la IA no responde
        return self._requires_database_fallback(message)

    def _requires_database_fallback(self, message: str) -> bool:
        """Fallback determinista: detecta palabras clave de datos."""
        msg = message.lower().strip()
        db_keywords = [
            "factura", "presupuesto", "albaran", "pedido", "abono", "contrato",
            "cliente", "proveedor", "agente", "articulo", "producto", "familia",
            "importe", "precio", "total", "cobro", "pago", "facturado", "ventas",
            "compras", "stock", "inventario", "cuantos", "cuantas", "cuanto",
            "dame", "muestra", "lista", "listado", "busca", "encuentra",
            "suma", "promedio", "media", "tasa", "porcentaje", "distribucion",
            "evolucion", "tendencia", "comparativa", "historico", "estadistica",
            "split", "instalacion", "mantenimiento", "sat",
        ]
        return any(k in msg for k in db_keywords)

    def _is_conversational_message(self, message: str) -> bool:
        """
        Detección RÁPIDA y DETERMINISTA de mensajes conversacionales obvios.
        Solo para saludos/despedidas explícitas — el resto lo decide la IA.
        """
        msg = message.lower().strip()
        words = msg.split()

        # Patrones conversacionales explícitos (siempre conversacional sin llamar a IA)
        conversational_starts = [
            "hola", "buenos dias", "buenas tardes", "buenas noches", "buenas",
            "gracias", "de nada", "ok", "vale", "perfecto", "entendido",
            "adios", "hasta luego", "hasta pronto", "bye",
            "como estas", "como te llamas", "quien eres", "que eres",
            "que puedes hacer", "ayuda", "help",
            "si", "no", "claro", "por supuesto", "genial", "bien",
        ]
        for pat in conversational_starts:
            if msg == pat or msg.startswith(pat + " ") or msg.startswith(pat + ","):
                return True

        # Mensajes muy cortos sin palabras de datos → conversacional
        if len(words) <= 3 and not self._requires_database_fallback(message):
            return True

        return False

    def _is_deep_analysis_request(self, message: str) -> bool:
        """
        Detecta si el usuario quiere un análisis profundo multi-fase.

        IMPORTANTE: Palabras como "justifica", "detalla", "explica" NO activan
        el DeepAnalysisAgent — son peticiones de aclaración sobre la respuesta
        anterior, no análisis nuevos. El DeepAgent solo se activa con comandos
        explícitos o peticiones de análisis completo desde cero.
        """
        msg = message.lower().strip()
        # Comando explícito
        if msg.startswith("/deep") or msg.startswith("/analisis"):
            return True
        # Palabras clave de análisis profundo DESDE CERO (no aclaraciones)
        # EXCLUIDAS: "justifica", "detalla", "explica", "en detalle", "detallado"
        # porque son peticiones de aclaración sobre la respuesta anterior.
        deep_keywords = [
            "analiza en profundidad", "análisis profundo", "análisis completo",
            "investiga", "analiza todo",
            "con todo el detalle", "profundamente", "a fondo",
            "analiza los datos", "investiga los datos", "estudio completo",
            "análisis exhaustivo", "analiza exhaustivamente",
            "en profundidad", "dime en profundidad",
            "tasa de éxito", "tasa exito", "tasa de aceptacion",
        ]
        return any(k in msg for k in deep_keywords)

    async def _chat_no_db(self, message: str, context: Dict[str, Any]) -> str:
        """
        Modo chat conversacional puro sin BD (o con simulador activo sin parámetros reales).
        Se activa cuando no hay db_params, no_db=True, o fallo de conexion.
        Usa la IA local directamente. Incluye historial de conversación y reglas Firebird
        en el system_prompt para mantener coherencia multi-turno.
        """
        logger.info("[CHAT] Modo SIN BD - chat conversacional puro")
        try:
            conv_history = context.get('conversation_history', [])
            history_context = ""
            if conv_history:
                recent = conv_history[-6:]
                history_context = "\n\n=== CONTEXTO DE CONVERSACIÓN ANTERIOR ===\n"
                for m in recent:
                    role = m.get('role', 'user')
                    content = m.get('content', '')[:300]
                    if role == 'user':
                        history_context += f"Usuario: {content}\n"
                    elif role == 'assistant':
                        history_context += f"Asistente: {content}\n"
                history_context += "=== FIN DEL CONTEXTO ===\n"
                logger.info(f"[CHAT] Incluyendo {len(recent)} mensajes de historial en el contexto (no-db)")

            system_prompt = (
                "Eres DEVIA, el asistente inteligente de JDDC. "
                "Puedes responder preguntas generales, ayudar con analisis, "
                "explicar conceptos de negocio, climatizacion, facturacion, "
                "y cualquier consulta del usuario. "
                "En este momento no tienes acceso a la base de datos, "
                "pero puedes ayudar con todo lo demas. "
                "Responde siempre en espanol, de forma clara y util.\n"
                "REGLAS SQL Firebird (para referencia): usa FIRST N (no LIMIT/TOP), "
                "UPPER(col) LIKE UPPER('%x%') para texto, "
                "DOCCAB.TIPO: 13=factura, 11=albaran, 0=presupuesto, 12=pedido, 3=abono, 2=SAT."
            )

            if history_context:
                system_prompt += history_context

            response, model_used = await self.model_orchestrator.execute_with_fallback(
                system_prompt=system_prompt,
                user_message=message,
                images=context.get('images'),
                preferred_model_id=context.get('model_id'),
            )

            if response:
                logger.info(f"[CHAT] Respuesta sin BD generada con {model_used}")
                return response
            else:
                return "Lo siento, no pude generar una respuesta. La IA local no esta disponible."

        except Exception as e:
            logger.error(f"[CHAT] Error en modo sin BD: {e}")
            return f"Error al procesar el mensaje: {str(e)}"

    async def process_message(self, message: str, context: Dict[str, Any]) -> str:
        logger.info("="*80)
        logger.info(f"{LogPrefixes.CHAT_SERVICE} {LogEmojis.NEW_MESSAGE} NUEVO MENSAJE RECIBIDO")
        logger.info(f"{LogPrefixes.EMISOR} Usuario")
        logger.info(f"{LogPrefixes.MENSAJE} {message}")
        logger.info(f"{LogPrefixes.CONTEXTO} model_id={context.get('model_id')}")
        logger.info("="*80)

        # MODO SIN BD - chat conversacional puro
        # Se activa si: no_db=True, db_params ausente/vacio, o fallo de conexion
        no_db_flag = context.get('no_db', False)
        db_params = context.get('db_params')
        db_params_empty = not db_params or not db_params.get('host') or not db_params.get('database')

        simulator_available = False
        try:
            from backend.modules.db_simulator.manager import simulator_manager
            simulator_available = simulator_manager.is_enabled()
        except Exception as sim_err:
            logger.warning(f"[CHAT] No se pudo consultar el simulador: {sim_err}")

        if simulator_available and db_params_empty and not no_db_flag:
            logger.info("[CHAT] Simulador activo y no hay parámetros reales; usando simulador para generar respuestas SQL")
            db_params = {}
            db_params_empty = False
            context['db_params'] = db_params

        if no_db_flag or db_params_empty:
            logger.info(f"[CHAT] Sin BD (no_db={no_db_flag}, db_params_empty={db_params_empty})")
            return await self._chat_no_db(message, context)

        # ── ANÁLISIS PROFUNDO MULTI-FASE ──────────────────────────────────────
        # Se activa con:
        #   1. Checkbox frontend: context.get('deep_analysis', False) == True
        #   2. Comando explícito: /deep, /analisis
        #   3. Palabras clave: "analiza en profundidad", "investiga", etc.
        # Detección de intención: ¿requiere BD o es conversacional/general?
        # _is_conversational_message: detección rápida determinista (saludos, mensajes cortos)
        # _ai_requires_database: clasificación IA para el resto (una llamada ligera a Qwen3)
        _is_conv = self._is_conversational_message(message)
        if not _is_conv:
            _needs_db = await self._ai_requires_database(message)
            if not _needs_db:
                logger.info("[CHAT] 💬 IA clasificó como NO requiere BD — chat conversacional directo")
                return await self._chat_no_db(message, context)

        _wants_deep = context.get('deep_analysis', False) or self._is_deep_analysis_request(message)
        if _wants_deep and not _is_conv:
            logger.info("[CHAT] 🔬 Activando DeepAnalysisAgent (análisis multi-fase)")
            try:
                from backend.modules.chat.deep_analysis_agent import DeepAnalysisAgent
                # Obtener contexto SIUO (mismo esquema Firebird siempre —
                # el simulador traduce la sintaxis transparentemente)
                try:
                    retriever = get_context_retriever()
                    db_context, _ = retriever.get_context(message)
                except Exception:
                    db_context = get_semantic_schema()

                agent = DeepAnalysisAgent(
                    orchestrator=self.model_orchestrator,
                    db_context=db_context,
                    sql_executor=lambda q: self._execute_sql(q, context.get('db_params')),
                    sql_normalizer=self.sql_normalizer,
                )
                # Limpiar prefijo /deep del mensaje
                clean_msg = message.strip()
                for prefix in ["/deep ", "/deep", "/analisis ", "/analisis"]:
                    if clean_msg.lower().startswith(prefix):
                        clean_msg = clean_msg[len(prefix):].strip()
                        break

                conv_history = context.get('conversation_history', [])
                result = await agent.analyze(clean_msg, conv_history)
                logger.info("[CHAT] ✅ DeepAnalysisAgent completado")
                return result
            except Exception as e:
                logger.error(f"[CHAT] ❌ DeepAnalysisAgent falló: {e} — continuando con flujo normal")
                # Fall-through al flujo normal si el agente falla

        # DEBUG: List tables command
        if message.strip() == "DEBUG_TABLES":
            try:
                logger.info("[DEBUG] Ejecutando comando DEBUG_TABLES")
                driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
                
                # Map username to user for DBConfig
                config_params = context.get('db_params', {}).copy()
                if 'username' in config_params:
                    config_params['user'] = config_params.pop('username')
                
                config = DBConfig(**config_params)
                driver.connect(config)
                # List tables
                query = "SELECT TRIM(RDB$RELATION_NAME) as NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 ORDER BY RDB$RELATION_NAME"
                results = driver.execute_query(query)
                tables = [r['NAME'] for r in results]
                
                # Find candidates
                keywords = ['FACT', 'VENT', 'CAB', 'ALB']
                candidates = []
                for t in tables:
                    if any(k in t for k in keywords):
                        try:
                            count_res = driver.execute_query(f"SELECT COUNT(*) as C FROM {t}")
                            count = count_res[0]['C']
                            candidates.append(f"{t} ({count} filas)")
                            
                            # Log columns for candidates
                            col_res = driver.execute_query(f"SELECT TRIM(RDB$FIELD_NAME) as F FROM RDB$RELATION_FIELDS WHERE TRIM(RDB$RELATION_NAME) = '{t}'")
                            cols = [c['F'] for c in col_res]
                            logger.info(f"[DEBUG] Tabla {t}: {', '.join(cols)}")
                        except:
                            candidates.append(f"{t} (Error leyendo)")
                
                driver.disconnect()
                return f"Tablas encontradas ({len(tables)}): {', '.join(tables)}\n\nCandidatos facturas:\n" + "\n".join(candidates)
            except Exception as e:
                logger.error(f"[DEBUG ERROR] {str(e)}")
                return f"Error debug: {str(e)}"
        
        # DEBUG: Inspect columns command
        if message.strip().startswith("DEBUG_COLUMNS"):
            try:
                table_name = message.strip().split(" ")[1]
                logger.info(f"[DEBUG] Inspeccionando tabla {table_name}")
                driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
                
                config_params = context.get('db_params', {}).copy()
                if 'username' in config_params:
                    config_params['user'] = config_params.pop('username')
                
                config = DBConfig(**config_params)
                driver.connect(config)
                
                query = f"""
                SELECT TRIM(RDB$FIELD_NAME) as FIELD_NAME
                FROM RDB$RELATION_FIELDS 
                WHERE TRIM(RDB$RELATION_NAME) = '{table_name}'
                ORDER BY RDB$FIELD_POSITION
                """
                results = driver.execute_query(query)
                columns = [r['FIELD_NAME'] for r in results]
                
                # Data sampling removed for privacy and performance
                sample = ""


                driver.disconnect()
                return f"Columnas de {table_name}:\n" + "\n".join(columns) + sample
            except Exception as e:
                return f"Error debug columns: {str(e)}"
        
        # 1. Get DB Schema Context — SIUO v2 si disponible, fallback v1
        try:
            retriever = get_context_retriever()
            db_context, ctx_meta = retriever.get_context(message)
            source = ctx_meta.get("source", "fallback")
            tables = ctx_meta.get("tables_used", [])
            tokens = ctx_meta.get("tokens_estimated", 0)
            logger.info(
                f"[DATABASE] Contexto SIUO ({source}): "
                f"{len(tables)} tablas, ~{tokens} tokens, {len(db_context)} chars"
            )
        except Exception as _ctx_err:
            logger.warning(f"[DATABASE] ContextRetriever fallo ({_ctx_err}), usando fallback v1")
            db_context = get_semantic_schema()
            logger.info(f"[DATABASE] Esquema v1: {len(db_context)} caracteres")
        
        # 2. Build conversation history context
        from backend.core.utils.constants import UILimits
        conversation_history = context.get('conversation_history', [])
        
        # Limit to last N messages
        max_history = UILimits.CONVERSATION_MEMORY_MESSAGES
        recent_history = conversation_history[-max_history:] if len(conversation_history) > max_history else conversation_history
        
        # Format conversation history for prompt
        history_context = ""
        if recent_history:
            history_context = "\n\n=== CONTEXTO DE CONVERSACIÓN ANTERIOR ===\n"
            for msg in recent_history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'user':
                    history_context += f"Usuario: {content}\n"
                elif role == 'assistant':
                    history_context += f"Asistente: {content}\n"
            history_context += "=== FIN DEL CONTEXTO ===\n"
            logger.info(f"[CHAT] Incluyendo {len(recent_history)} mensajes de historial en el contexto")
        
        # 3. Intent Detection & Prompt Engineering
        # Check for visual intent keywords
        msg_lower = message.lower()
        visual_keywords = ["que se ve", "que hay", "describe", "analiza la imagen", "que puedes ver", "descripción"]
        is_visual_request = context.get('images') and any(k in msg_lower for k in visual_keywords)
        
        system_prompt = ""
        
        if is_visual_request:
            logger.info(f"[CHAT] 👁️ Intención Visual Detectada (Bypassing SQL Mode)")
            system_prompt = f"""
Eres un asistente experto en análisis visual.
Tu trabajo es DESCRIBIR las imágenes que el usuario ha subido, basándote únicamente en el análisis proporcionado.
NO tienes acceso a ninguna base de datos SQL.
NO intentes generar consultas SQL.
Si ves texto en la imagen, transcríbelo pero NO lo busques en ninguna tabla.

{history_context}
"""
        else:
            # Standard SQL Mode — system prompt ultra-compacto para minimizar tokens
            # ── Nota simulador (solo si está activo) ─────────────────────────
            _sim_note = ""
            try:
                from backend.modules.db_simulator.manager import simulator_manager as _sm
                if _sm.is_enabled():
                    from backend.modules.db_simulator.schema import TABLE_SCHEMAS
                    _sim_tables = ", ".join(sorted(TABLE_SCHEMAS.keys()))
                    _sim_note = (
                        f"\n⚠️ MODO SIMULADOR ACTIVO (SQLite local — snapshot de Firebird).\n"
                        f"TABLAS DISPONIBLES (SOLO ESTAS): {_sim_tables}\n"
                        f"NO generes SQL contra tablas que no estén en esta lista.\n"
                        f"Escribe SQL con sintaxis Firebird (FIRST N, EXTRACT, etc.) — "
                        f"el sistema lo convierte a SQLite automáticamente.\n"
                    )
            except Exception:
                pass

            system_prompt = f"""Firebird 2.5 SQL. Convierte preguntas a SQL válido.
{history_context}
{db_context}{_sim_note}
REGLAS(no negociar):
• FIRST N no LIMIT/TOP/ROWS: SELECT FIRST 10 CODIGO FROM ARTICULO
• UPPER(col) LIKE UPPER('%x%') para texto (Firebird es case-sensitive)
• BLOB(DESCRIPCION en ARTICULO/DOCCAB) → NO usar en GROUP BY/ORDER BY/SELECT si hay GROUP BY; usa DESCRIPCIONCORTA o NOMBRE
• ARTICULO.STOCK no existe → usar STOCKARTICULO
• DOCCAB.TIPO: 13=factura,12=pedido,11=albaran,0=presupuesto,3=abono,2=SAT
• Fechas: EXTRACT(MONTH FROM FECHA), EXTRACT(YEAR FROM FECHA); NO DATEADD dentro de EXTRACT
• Mes pasado: (EXTRACT(YEAR FROM FECHA)*12+EXTRACT(MONTH FROM FECHA))=(EXTRACT(YEAR FROM CURRENT_DATE)*12+EXTRACT(MONTH FROM CURRENT_DATE)-1)
• Artículos con más compras → JOIN DOCLIN ON DOCLIN.CODIGO=ARTICULO.CODIGO GROUP BY ARTICULO.CODIGO,ARTICULO.NOMBRE ORDER BY COUNT(*) DESC
• Delimita SQL con ```sql y ```; si no requiere SQL responde directamente
EJEMPLO COMPLETO(artículos con más compras):
```sql
SELECT FIRST 5 A.CODIGO, A.NOMBRE, COUNT(*) AS NCOMPRAS FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO=A.CODIGO GROUP BY A.CODIGO, A.NOMBRE ORDER BY NCOMPRAS DESC
```"""
        # Dynamic Context Injection based on History
        last_ai_msg = ""
        if 'conversation_history' in context:
            history = context['conversation_history']
            if history and len(history) > 0:
                # Get last message from assistant
                for msg in reversed(history):
                    if msg.get('role') == 'assistant':
                        last_ai_msg = msg.get('content', '')
                        break
        
        # Check if previous message was an image generation
        if "[GENERAR_IMAGEN:" in last_ai_msg or "¡Imagen Generada!" in last_ai_msg or "Job ID:" in last_ai_msg:
             logger.info(f"[CHAT] 🎨 Contexto detectado: SEGUIMIENTO DE IMAGEN")
             system_prompt += """
SITUACIÓN: Acabas de generar una imagen.
ANALIZA LA INTENCIÓN DEL USUARIO:
1. MODIFICACIÓN: Si pide cambios (ej: "ponle más luz", "quita el fondo", "hazlo azul"), RESPONDE con [GENERAR_IMAGEN: ...] y el prompt ajustado.
2. ANÁLISIS/PREGUNTA: Si pregunta "¿qué es?", "¿qué ves?", "describe la imagen", RESPONDE TEXTUALMENTE explicando qué generaste (básate en el prompt que escribiste antes).
3. SQL: Si pide buscar datos (ej: "tengo esto en stock?"), genera SQL.

NO generes imágenes si solo te preguntan qué hay en la anterior.
"""

        system_prompt += """
TIPOS DE DOCUMENTOS (TABLA DOCCAB, COLUMNA TIPO):
- Para "facturas" -> WHERE TIPO = 13
- Para "albaranes" -> WHERE TIPO = 11
- Para "presupuestos" -> WHERE TIPO = 0
- Para "pedidos" -> WHERE TIPO = 12
- Para "abonos" -> WHERE TIPO = 3
- Para "recibos" -> WHERE TIPO = 61
- Para "contratos" -> WHERE TIPO = 10
- Para "certificaciones" -> WHERE TIPO = 51
- Para "ordenes de trabajo" o "SAT" -> WHERE TIPO = 2

TERMINOLOGÍA ESPECÍFICA (CONTEXTO AIRE ACONDICIONADO):
- "Split" se refiere a equipos de aire acondicionado.
- "Gas" se refiere a refrigerantes (R-32, R-410A, etc.).

BÚSQUEDAS DE TEXTO (OBLIGATORIO CASE INSENSITIVE):
- SIEMPRE usa `UPPER(columna) LIKE UPPER('%texto%')` para CUALQUIER búsqueda de texto.
- NUNCA uses `LIKE '%TEXTO%'` directo, ya que Firebird es case-sensitive.
- Ejemplo CORRECTO: `WHERE UPPER(NOMBRE) LIKE UPPER('%SPLIT%')`
- Ejemplo INCORRECTO: `WHERE NOMBRE LIKE '%SPLIT%'`

11. Ejemplos CORRECTOS para consultas de fechas:
    - "facturas de este mes":
      WHERE EXTRACT(MONTH FROM FECHA) = EXTRACT(MONTH FROM CURRENT_DATE)
      AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)
    
    - "facturas del mes pasado" (USAR ESTA SINTAXIS):
      WHERE FECHA >= CAST(EXTRACT(YEAR FROM CURRENT_DATE) || '-' || 
                          CASE WHEN EXTRACT(MONTH FROM CURRENT_DATE) = 1 THEN 12 
                               ELSE EXTRACT(MONTH FROM CURRENT_DATE) - 1 END || '-01' AS DATE)
      AND FECHA < CAST(EXTRACT(YEAR FROM CURRENT_DATE) || '-' || 
                       EXTRACT(MONTH FROM CURRENT_DATE) || '-01' AS DATE)
    
    - ALTERNATIVA MÁS SIMPLE para "mes pasado" (RECOMENDADA):
      WHERE (EXTRACT(YEAR FROM FECHA) * 12 + EXTRACT(MONTH FROM FECHA)) = 
            (EXTRACT(YEAR FROM CURRENT_DATE) * 12 + EXTRACT(MONTH FROM CURRENT_DATE) - 1)
    
    - "hace 2 meses":
      WHERE (EXTRACT(YEAR FROM FECHA) * 12 + EXTRACT(MONTH FROM FECHA)) = 
            (EXTRACT(YEAR FROM CURRENT_DATE) * 12 + EXTRACT(MONTH FROM CURRENT_DATE) - 2)

12. NUNCA uses DATEADD dentro de EXTRACT - NO FUNCIONA en Firebird 2.5

13. REGLA DE AÑO ACTUAL (CRÍTICA):
    - Si el usuario menciona un mes (ej: "octubre", "noviembre") SIN especificar año, ASUME SIEMPRE EL AÑO ACTUAL.
    - EJEMPLO: "facturas de octubre" -> 
      WHERE EXTRACT(MONTH FROM FECHA) = 10 
      AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)
    - SOLO si el usuario dice explícitamente "de todos los años" o "histórico", omite el filtro de año.

    - SOLO si el usuario dice explícitamente "de todos los años" o "histórico", omite el filtro de año.

CAPACIDADES DE GENERACIÓN DE IMAGEN:
- PUEDES generar imágenes si el usuario lo pide (ej: "dibuja un gato", "crea una imagen de...").
- Para generar una imagen, responde SOLAMENTE con este comando:
  [GENERAR_IMAGEN: <detalle_del_prompt>]
- Ejemplo: Si el usuario dice "dibuja un paisaje", responde:
  [GENERAR_IMAGEN: paisaje futurista con montañas de neón, alta calidad]
- NO generes SQL para peticiones de dibujo.
- MODIFICACIÓN DE IMÁGENES:
  - Si el usuario pide "cambia X por Y" o "hazlo más rojo" sobre una imagen generada anteriormente:
  - RESPONDE con un NUEVO comando [GENERAR_IMAGEN: ...] que combine el contexto anterior con el cambio.
  - Ejemplo: Si antes dibujaste un "pájaro azul" y el usuario dice "ponlo verde", responde:
    [GENERAR_IMAGEN: pájaro verde detallado, alta calidad...]
  - NO INTENTES EJECUTAR SQL PARA MODIFICAR IMÁGENES.

"""
        logger.info(f"[AI PROVIDER] 📤 Usando sistema de fallback multi-modelo...")
        logger.info(f"[AI PROVIDER] System Prompt:\n{system_prompt}")
        logger.info(f"[AI PROVIDER] User Message: {message}")
        
        if context.get('images'):
            logger.info(f"{LogPrefixes.CONTEXTO} 📸 Imágenes adjuntas: {len(context['images'])}")
            
            # Perform Image Analysis BEFORE sending to SQL/Text AI
            try:
                logger.info("[CHAT] 🖼️ Iniciando análisis visual profundo...")
                image_analysis = await self._analyze_images(context['images'])
                logger.info(f"[CHAT] 🕵️ Resultado análisis visual: {image_analysis}")
                
                # Inject analysis into the conversation context
                # This ensures the LLM 'sees' the image content textually
                system_prompt += f"\n\n[SISTEMA DE VISIÓN]: El usuario ha adjuntado imágenes. Análisis automático pre-generado:\n{image_analysis}\n\n"
                system_prompt += "=== REGLAS PRIORITARIAS PARA IMÁGENES (SOBRESCRIBEN TODO LO DEMÁS) ===\n"
                system_prompt += "1. SI EL USUARIO PREGUNTA '¿Qué es esto?', '¿Qué ves?', 'Describe la imagen':\n"
                system_prompt += "   - TU OBJETIVO ES DESCRIBIR VISUALMENTE. Tienes el análisis arriba.\n"
                system_prompt += "   - PROHIBIDO GENERAR SQL. No busques en la base de datos palabras que veas en la imagen (como 'DEVIA' o marcas).\n"
                system_prompt += "   - Responde ÚNICAMENTE basándote en el texto del [SISTEMA DE VISIÓN].\n"
                system_prompt += "2. SOLO genera SQL si el usuario vincula explícitamente la imagen con la DB (ej: '¿Tenemos stock de este producto?', 'Busca el precio de lo que ves').\n"
                system_prompt += "3. Ante la duda entre describir o buscar: DESCRIBE y pregunta si quiere buscar.\n"
                system_prompt += "========================================================================\n"
                
            except Exception as e:
                logger.error(f"[CHAT] ❌ Falló el análisis de imagen: {e}")

        # Use ModelFallbackOrchestrator for robust multi-model generation
        response_text, used_model_id = await self.model_orchestrator.execute_with_fallback(
            system_prompt=system_prompt,
            user_message=message,
            images=context.get('images'),
            feedback_callback=None,  # TODO: Implement real-time feedback to user
            preferred_model_id=context.get('model_id')
        )
        
        if not response_text:
            logger.error(f"[AI PROVIDER] ❌ Todos los modelos fallaron")
            return "❌ No se pudo generar la consulta con ningún modelo disponible. Por favor, inténtalo más tarde."
        
        logger.info(f"[AI PROVIDER] ✅ Respuesta generada con modelo: {used_model_id}")
        logger.info(f"[AI PROVIDER] Respuesta completa: {response_text}")
        
        # Configure provider for SQL correction and result interpretation
        from backend.core.config.model_manager import model_manager
        model_config = model_manager.get_model(used_model_id)
        
        if model_config:
            provider_schema = model_config.get('schema', model_config.get('provider'))
            provider = AIFactory.get_provider(provider_schema)
            
            ai_config_params = {
                'api_key': model_config.get('api_key'),
                'model': model_config['model_id']
            }
            if model_config.get('base_url'):
                ai_config_params['base_url'] = model_config['base_url']
            if model_config.get('headers'):
                ai_config_params['headers'] = model_config['headers']
            
            ai_config = AIConfig(**ai_config_params)
            provider.configure(ai_config)
        else:
            logger.warning(f"[AI PROVIDER] ⚠️ No se pudo configurar provider para interpretación")
            provider = None
        
        
        # 5. Check for Image Generation Command
        if "[GENERAR_IMAGEN:" in response_text:
            try:
                logger.info(f"[IMAGE GEN] 🎨 Detectada solicitud de imagen")
                import re
                match = re.search(r"\[GENERAR_IMAGEN:(.*?)\]", response_text, re.DOTALL)
                if match:
                    img_prompt = match.group(1).strip()
                    logger.info(f"[IMAGE GEN] Prompt: {img_prompt}")
                    
                    # Call Image Service
                    from backend.modules.images.schemas import GenerateRequest
                    
                    # Async generation (fire and forget for the chat, but user gets job ID)
                    req = GenerateRequest(prompt=img_prompt)
                    job_response = await self.image_service.generate_image(req, user_id="chat_user")
                    
                    # WAIT FOR JOB COMPLETION to show the image directly
                    import asyncio
                    # Poll max 60s
                    job_data = None
                    for _ in range(30):
                        await asyncio.sleep(2)
                        job_data = await self.image_service.get_job(job_response.job_id)
                        if job_data and job_data.get("status") in ["COMPLETED", "FAILED"]:
                            break
                    
                    if job_data and job_data.get("status") == "COMPLETED":
                         # Construct image URL
                         # Assuming backend serves output images at /api/images/files/output/{filename}
                         # We need to ensure ImageRouter has this endpoint or similar.
                         # For now, we assume the filename is available.
                         result_data = job_data.get("result_data", {})
                         files = result_data.get("files", [])
                         
                         img_markdown = ""
                         if files:
                             # Use the first file
                             filename = files[0]
                             # URL relative to frontend
                             # TODO: Ensure Router exposes file serving
                             img_url = f"/api/images/files/output/{filename}" 
                             img_markdown = f"\n\n![Propuesta de diseño]({img_url})"
                         
                         return f"🎨 ¡Imagen Generada!\n\n📄 **Prompt:** {img_prompt}\n{img_markdown}\n\n(ID: `{job_response.job_id}`)"
                    elif job_data and job_data.get("status") == "FAILED":
                         error = job_data.get("error", "Unknown error")
                         return f"❌ Falló la generación: {error}"
                    else:
                         return f"⏳ La imagen se está generando en segundo plano (tarda más de lo esperado).\n🆔 **Job ID:** `{job_response.job_id}`"
                         
            except Exception as e:
                logger.error(f"[IMAGE GEN] Error request: {e}", exc_info=True)
                return f"❌ Error al intentar generar la imagen: {str(e)}"

        # 6. Execute SQL if present
        if "```sql" in response_text:
            logger.info(f"[SQL] 🔍 Detectada consulta SQL en la respuesta")
            try:
                # ── SELECCIÓN DEL SQL MÁS COMPLETO ──────────────────────────────────
                # La IA a veces genera varios bloques SQL (paso 1, paso 2, consulta final).
                # El primer bloque suele ser el más simple (ej: COUNT(*) básico).
                # El ÚLTIMO bloque suele ser el más completo (con JOINs, CASE WHEN, etc.).
                # Usamos el bloque con más caracteres como heurística de "más completo".
                # ────────────────────────────────────────────────────────────────────
                import re as _re_sql
                sql_blocks = _re_sql.findall(r'```sql\s*(.*?)```', response_text, _re_sql.DOTALL)
                if sql_blocks:
                    # Elegir el bloque más largo (más completo)
                    sql_query = max(sql_blocks, key=len).strip()
                    logger.info(f"[SQL] {len(sql_blocks)} bloques SQL encontrados — usando el más completo ({len(sql_query)} chars)")
                else:
                    sql_query = response_text.split(SQLDelimiters.START)[1].split(SQLDelimiters.END)[0].strip()
                
                # ── NORMALIZACIÓN DETERMINISTA ──────────────────────────────────────────
                # FirebirdSQLNormalizer aplica en un solo paso todas las correcciones
                # que se pueden hacer por código (sin IA):
                #   • Multilínea → una línea
                #   • LIMIT/TOP/ROWS → FIRST N
                #   • Añade FIRST N si falta (no en agregaciones)
                #   • ILIKE / LIKE → UPPER(col) LIKE UPPER(val)
                #   • != → <>, TRUE/FALSE → 'T'/'F'
                #   • NOW()/GETDATE()/SYSDATE → CURRENT_TIMESTAMP/CURRENT_DATE
                #   • CONCAT(a,b) → a || b, SUBSTRING(c,p,l) → SUBSTRING(c FROM p FOR l)
                #   • OFFSET N → eliminar, backticks → sin comillas
                #   • Columnas erróneas conocidas (STOCK → STOCKARTICULO)
                # ────────────────────────────────────────────────────────────────────────
                sql_query, norm_changes = self.sql_normalizer.normalize(sql_query)
                if norm_changes:
                    logger.info(f"[SQL NORMALIZER] {len(norm_changes)} correcciones deterministas aplicadas")
                
                logger.info(f"[SQL] Consulta normalizada: {sql_query}")
                logger.info(f"[DATABASE] 🔄 Ejecutando consulta SQL...")
                
                # Execute with auto-correction
                results = await self.sql_corrector.execute_with_correction(
                    sql_query=sql_query,
                    original_question=message,
                    db_context=db_context,
                    ai_provider=provider,
                    execute_func=lambda q: self._execute_sql(q, context.get('db_params')),
                    max_retries=self.config.get("max_sql_retries", 3)
                )
                
                logger.info(f"[DATABASE] ✓ Consulta ejecutada exitosamente")
                logger.info(f"[DATABASE] Resultados: {len(results)} filas")
                logger.info(f"[DATABASE] Datos: {results[:3] if len(results) > 3 else results}")  # First 3 rows
                
                # --- DATA PRIVACY CHECK ---
                # confirm_data_sending values:
                #   None  → client didn't send the field (Android/voice) → auto-confirm, skip check
                #   False → web client, pending user confirmation → block and ask
                #   True  → web client confirmed → proceed
                require_confirmation = getattr(settings, 'REQUIRE_DB_DATA_CONFIRMATION', True)
                confirm_data_sending = context.get('confirm_data_sending') if context else None
                # Only block if web client explicitly has it as False (pending confirmation)
                client_needs_confirmation = (require_confirmation and results and confirm_data_sending is False)
                
                if client_needs_confirmation:
                    logger.info(f"[PRIVACY] 🛑 Deteniendo para confirmación de usuario")
                    return {
                        "status": "confirmation_required",
                        "message": "Por favor confirma el envío de estos datos a la IA.",
                        "sql": sql_query,
                        "data_preview": results[:5], # Send a preview
                        "total_rows": len(results),
                        "full_data": results # Send full data to frontend to hold
                    }
                # --------------------------
                
                # 6. Interpret Results
                # Detect if client is voice/Android (confirm_data_sending is None = not sent)
                is_voice_client = (context.get('confirm_data_sending') is None)
                
                if is_voice_client:
                    # ── INTERPRETACIÓN DETERMINISTA PARA VOZ ────────────────────────────
                    # Para clientes de voz (gafas Meta), usamos interpret_results_for_voice()
                    # en lugar de una segunda llamada a IA.
                    #
                    # Beneficio: elimina ~20s de la segunda llamada a IA, reduciendo el
                    # tiempo total de ~42s a ~22s y evitando el timeout de 60s en Android.
                    #
                    # La función es 100% determinista: formatea los datos directamente
                    # en lenguaje natural sin necesidad de IA.
                    # ────────────────────────────────────────────────────────────────────
                    logger.info(f"[TTS] 🔊 Interpretación determinista para voz (sin 2ª llamada IA)")
                    final_response = interpret_results_for_voice(message, results, sql_query)
                    final_response = clean_for_tts(final_response)
                    logger.info(f"[TTS] Respuesta voz: {final_response}")
                else:
                    # WEB INTERPRETER: Respuesta con justificación en desplegable HTML
                    # La justificación va dentro de <details><summary> para que el usuario
                    # pueda desplegarla si quiere. marked.parse() preserva HTML inline.
                    interpretation_system = (
                        "Eres DEVIA, el asistente de datos de JDDC (empresa de climatización). "
                        "Interpretas resultados de base de datos para usuarios SIN conocimientos técnicos. "
                        "\n\n"
                        "REGLAS CRÍTICAS:\n"
                        "• NUNCA muestres código SQL al usuario. El SQL es interno, no lo verbalices.\n"
                        "• NUNCA uses términos técnicos como 'query', 'tabla', 'columna', 'JOIN', 'WHERE'.\n"
                        "• Habla en lenguaje de negocio: 'facturas', 'clientes', 'importes', 'período'.\n"
                        "• Muestra los datos tal cual están. Nulos → '(sin datos)'.\n"
                        "• NUNCA inventes datos ni diagnósticos sin base en los resultados.\n"
                        "• Los importes siempre en formato europeo: 1.234,56 EUR\n"
                        "\n"
                        "ANÁLISIS OBLIGATORIO — menciona SIEMPRE si aplica:\n"
                        "1. ¿Los datos son coherentes? ¿Hay valores extremos o sospechosos?\n"
                        "2. ¿Qué período cubre la consulta? ¿Hay datos de todos los meses?\n"
                        "3. ¿Qué tipos de documentos se incluyen/excluyen y por qué?\n"
                        "4. ¿El resultado responde completamente a la pregunta o hay matices?\n"
                        "\n"
                        "FORMATO OBLIGATORIO — usa EXACTAMENTE esta estructura HTML:\n"
                        "1. Respuesta directa en lenguaje natural (párrafo o tabla Markdown)\n"
                        "2. Análisis crítico breve (2-3 puntos clave)\n"
                        "3. Bloque <details> con justificación para quien quiera profundizar\n"
                        "4. Propuesta de verificación adicional al final\n"
                    )
                    n_rows = len(results)
                    cols_used = list(results[0].keys()) if results else []
                    # Detectar tablas con pocos registros para advertencia en rojo
                    from backend.modules.chat.firebird_sql_constants import LOW_RECORD_TABLES
                    from backend.modules.chat.sql_corrector import SQLCorrector as _SC
                    _sc_tmp = _SC()
                    tables_in_query = _sc_tmp._extract_tables_from_sql(sql_query)
                    low_record_html = ""
                    for _tbl in tables_in_query:
                        if _tbl.upper() in LOW_RECORD_TABLES:
                            _info = LOW_RECORD_TABLES[_tbl.upper()]
                            low_record_html += (
                                f'<p style="color:#c0392b;font-weight:bold;">⚠️ ADVERTENCIA: '
                                f'{_info["warning"]}</p>\n'
                            )

                    interpretation_prompt = (
                        f"PREGUNTA DEL USUARIO: {message}\n\n"
                        f"DATOS OBTENIDOS ({n_rows} registros, campos: {', '.join(cols_used)}):\n{results}\n\n"
                        + (
                            f"ADVERTENCIA INTERNA: Las siguientes tablas tienen muy pocos registros "
                            f"y los datos podrían estar incompletos: "
                            f"{[t for t in tables_in_query if t.upper() in LOW_RECORD_TABLES]}\n\n"
                            if any(t.upper() in LOW_RECORD_TABLES for t in tables_in_query) else ""
                        ) +
                        "INSTRUCCIONES — responde con esta estructura EXACTA (respeta el HTML):\n\n"
                        "## 📊 Respuesta Principal\n"
                        "[Aquí va la respuesta directa en lenguaje de negocio. "
                        "Tabla Markdown si hay múltiples resultados. "
                        "Importes en formato europeo (1.234,56 EUR). "
                        "NO uses términos técnicos. NO muestres SQL.]\n\n"
                        "🔍 Análisis Crítico\n"
                        "[2-3 puntos clave sobre los datos: coherencia, período, tipos incluidos, matices importantes]\n\n"
                        "<details>\n"
                        "<summary>📋 Ver justificación detallada</summary>\n\n"
                        + low_record_html +
                        "**Período analizado:** [indica el rango de fechas de los datos]\n\n"
                        "**Qué incluye este cálculo:** [explica en lenguaje de negocio qué tipos de documentos/registros se consideran]\n\n"
                        "**Qué NO incluye:** [explica qué se excluye y por qué]\n\n"
                        "**Cómo verificarlo manualmente:** [indica cómo el usuario podría comprobar el dato en el programa de gestión, sin mencionar SQL]\n\n"
                        "**Fiabilidad del dato:** [indica si el dato es completo, parcial, o tiene limitaciones conocidas]\n\n"
                        "</details>\n\n"
                        "---\n"
                        "💡 *¿Quieres que justifique estos datos con más detalle? Puedo analizar los registros uno a uno, "
                        "comparar con períodos anteriores, o desglosar por cliente/artículo/tipo.*\n\n"
                        "REGLAS:\n"
                        "1. NO inventes datos. Usa SOLO los resultados proporcionados.\n"
                        "2. Si no hay resultados, dilo claramente y sugiere por qué.\n"
                        "3. NUNCA muestres código SQL en la respuesta al usuario.\n"
                        "4. Si hay datos sospechosos (negativos, nulos, valores extremos), "
                        "menciónalos con ⚠️ en lenguaje de negocio.\n"
                        "5. El bloque <details>...</details> debe estar SIEMPRE presente, "
                        "después de la respuesta principal y el análisis crítico.\n"
                        "6. La propuesta de verificación adicional (💡) debe estar SIEMPRE al final."
                    )
                    
                    logger.info(f"[AI PROVIDER] Solicitando interpretacion WEB (Qwen3 LAN preferido)...")
                    final_response, _ = await self.model_orchestrator.execute_with_fallback(
                        system_prompt=interpretation_system,
                        user_message=interpretation_prompt,
                        feedback_callback=None,
                        preferred_model_id="jddcia-qwen3-30b"
                    )
                    
                    if not final_response:
                        final_response = (
                            f"He obtenido {len(results)} resultados, pero no he podido generar "
                            f"una explicacion detallada. Datos: {results[:5]}"
                        )
                
                logger.info(f"[AI PROVIDER] 📥 Interpretación recibida")
                logger.info(f"[RESPUESTA FINAL] {final_response}")
                logger.info("="*80)
                
                return final_response
            except Exception as e:
                error_str = str(e)
                logger.error(f"[ERROR SQL] ❌ Error ejecutando consulta: {error_str}")
                logger.error(f"[ERROR SQL] Consulta fallida: {sql_query}")

                # ── Placeholder sin resolver: la IA no pudo determinar el valor ──
                # El corrector detectó <ID_DEL_TRABAJADOR> etc. y no pudo resolverlo.
                # Devolvemos un mensaje amigable pidiendo el dato concreto al usuario.
                if error_str.startswith("PLACEHOLDER_UNRESOLVED:"):
                    placeholder_names = error_str.replace("PLACEHOLDER_UNRESOLVED:", "").strip()
                    # Mapear nombres de placeholder a preguntas amigables
                    friendly_hints = {
                        "ID_DEL_TRABAJADOR": "el nombre o código del trabajador",
                        "NOMBRE_DEL_TRABAJADOR": "el nombre del trabajador",
                        "ID_DEL_CLIENTE": "el nombre o código del cliente",
                        "NOMBRE_DEL_CLIENTE": "el nombre del cliente",
                        "ID_DEL_ARTICULO": "el nombre o referencia del artículo",
                        "CODIGO_DEL_ARTICULO": "la referencia o nombre del artículo",
                        "ID_DEL_PROVEEDOR": "el nombre del proveedor",
                        "ID_DEL_AGENTE": "el nombre del agente",
                    }
                    # Intentar dar una pista específica
                    hints = []
                    for ph in placeholder_names.split(","):
                        ph = ph.strip().upper()
                        hint = friendly_hints.get(ph)
                        if hint:
                            hints.append(hint)
                    if hints:
                        dato_pedido = " y ".join(hints)
                        return (
                            f"Para responder a tu pregunta necesito que me indiques {dato_pedido}. "
                            f"Por ejemplo: dime el nombre completo o el código y te lo busco enseguida. 😊"
                        )
                    else:
                        return (
                            f"Para responder necesito un dato más concreto. "
                            f"¿Puedes indicarme el nombre o código exacto que buscas? 😊"
                        )

                return f"Intenté ejecutar una consulta pero falló: {error_str}\nConsulta: {sql_query}"
        
        # Para clientes de voz: limpiar Markdown de respuestas de texto libre también
        is_voice_client = (context.get('confirm_data_sending') is None)
        if is_voice_client and isinstance(response_text, str):
            response_text = clean_for_tts(response_text)
            logger.info(f"[TTS] 🔊 Respuesta de texto libre limpiada para voz")
        
        logger.info(f"[RESPUESTA FINAL] {response_text}")
        logger.info("="*80)
        return response_text



    def _get_db_context(self, db_params: Dict[str, Any]) -> str:
        from backend.modules.db_simulator.manager import simulator_manager as _sim_mgr
        if not db_params and _sim_mgr.is_enabled():
            logger.info("[DATABASE] No hay parámetros reales pero el simulador está activo — construyendo contexto desde la BD simulada")
            try:
                from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
                driver = SimulatedFirebirdDriver()
                driver.connect()
                tables = driver.execute_query(QUERY_TABLES)
                table_names = [t['TABLE_NAME'] for t in tables if not t['TABLE_NAME'].startswith('RDB$')]
                schema_parts = [f"Base de datos simulada con {len(table_names)} tablas de usuario.\n"]
                schema_parts.append(f"Tablas disponibles: {', '.join(table_names)}\n")
                # Tablas principales de la BD JDDC (nombres reales, no genéricos)
                important_tables = [
                    'DOCCAB',      # Documentos: facturas, presupuestos, albaranes, SATs, pedidos
                    'DOCLIN',      # Líneas de documento (FK→DOCCAB.CODIGO)
                    'CLIENTE',     # Clientes
                    'ARTICULO',    # Artículos / productos / servicios
                    'PROYECTOS',   # Obras/proyectos
                    'PROYVAR',     # NIF y razón social por proyecto
                    'PRESUPROYE',  # Relación presupuesto↔proyecto
                    'PROVEED',     # Proveedores
                    'DOCDESTINO',  # Relación presupuesto→factura/pedido
                ]
                available_important = [t for t in important_tables if t in table_names]
                for table_name in available_important:
                    try:
                        columns = driver.execute_query(QUERY_TABLE_COLUMNS, (table_name,))
                        if columns:
                            col_details = [f"  - {c['FIELD_NAME']} ({c.get('FIELD_TYPE', 'UNKNOWN')})" for c in columns]
                            schema_parts.append(f"\nTabla: {table_name}")
                            schema_parts.append(f"Columnas ({len(columns)}):")
                            schema_parts.extend(col_details)
                    except Exception as e:
                        logger.warning(f"[DATABASE] No se pudo obtener esquema simulado de {table_name}: {e}")
                driver.disconnect()
                return "\n".join(schema_parts)
            except Exception as e:
                logger.error(f"[DATABASE] Error construyendo contexto simulado: {e}")
                return f"Error obteniendo esquema del simulador: {str(e)}"

        if not db_params:
            logger.warning("[DATABASE] No hay parámetros de conexión")
            return "No hay conexión a base de datos definida."
            
        try:
            logger.info(f"[DATABASE] Conectando a: {db_params.get('host')}:{db_params.get('port')}")
            logger.info(f"[DATABASE] Base de datos: {db_params.get('database')}")
            
            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
            # Map username to user for DBConfig
            config_params = db_params.copy()
            if 'username' in config_params:
                config_params['user'] = config_params.pop('username')
            config = DBConfig(**config_params)
            driver.connect(config)
            
            logger.info(f"[DATABASE] ✓ Conexión establecida")
            
            # Get all user tables (excluding system tables)
            logger.info(f"[DATABASE] Consultando lista de tablas...")
            tables = driver.execute_query(QUERY_TABLES)
            table_names = [t['TABLE_NAME'] for t in tables if not t['TABLE_NAME'].startswith('RDB$')]
            logger.info(f"[DATABASE] Tablas de usuario encontradas: {len(table_names)}")
            logger.info(f"[DATABASE] Tablas: {', '.join(table_names[:10])}")  # Log first 10
            
            # Build detailed schema for main tables
            schema_parts = [f"Base de datos Firebird con {len(table_names)} tablas de usuario.\n"]
            schema_parts.append(f"Tablas disponibles: {', '.join(table_names)}\n")
            
            # Tablas principales de la BD JDDC (nombres reales)
            important_tables = [
                'DOCCAB',      # Documentos: facturas, presupuestos, albaranes, SATs, pedidos
                'DOCLIN',      # Líneas de documento
                'CLIENTE',     # Clientes
                'ARTICULO',    # Artículos / productos / servicios
                'PROYECTOS',   # Obras/proyectos
                'PROYVAR',     # NIF y razón social por proyecto
                'PRESUPROYE',  # Relación presupuesto↔proyecto
                'PROVEED',     # Proveedores
                'DOCDESTINO',  # Relación presupuesto→factura/pedido
            ]
            available_important = [t for t in important_tables if t in table_names]
            
            logger.info(f"[DATABASE] Obteniendo esquema detallado de {len(available_important)} tablas principales...")
            
            for table_name in available_important:
                try:
                    logger.info(f"[DATABASE] Consultando columnas de {table_name}...")
                    columns = driver.execute_query(QUERY_TABLE_COLUMNS, (table_name,))
                    
                    if columns:
                        col_details = []
                        for c in columns:
                            col_info = f"  - {c['FIELD_NAME']} ({c['FIELD_TYPE']})"
                            col_details.append(col_info)
                        
                        schema_parts.append(f"\nTabla: {table_name}")
                        schema_parts.append(f"Columnas ({len(columns)}):")
                        schema_parts.extend(col_details)
                        
                        logger.info(f"[DATABASE] {table_name}: {len(columns)} columnas")
                except Exception as e:
                    logger.warning(f"[DATABASE] No se pudo obtener esquema de {table_name}: {str(e)}")
            
            schema = "\n".join(schema_parts)
            
            driver.disconnect()
            logger.info(f"[DATABASE] ✓ Desconectado")
            logger.info(f"[DATABASE] Esquema generado: {len(schema)} caracteres, {len(available_important)} tablas detalladas")
            
            return schema
        except Exception as e:
            logger.error(f"[DATABASE ERROR] ❌ {str(e)}")
            return f"Error obteniendo esquema: {str(e)}"

    def _execute_sql(self, query: str, db_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ejecuta SQL contra la BD configurada.

        Lógica de selección de BD (sin fallback automático):
          - simulator_enabled=true  → SQLite local (BD simulada)
          - simulator_enabled=false → Firebird real (sin fallback)

        IMPORTANTE: No usa time.sleep() para no bloquear el event loop de asyncio.
        Un único intento — si falla, lanza excepción inmediatamente.
        """
        logger.info(f"[DATABASE] Preparando ejecución de consulta...")

        # ── MODO SIMULADOR (activación servidor) ──────────────────────────────
        # El simulador se activa SOLO si simulator_enabled=true en
        # backend/modules/db_simulator/config.json (parámetro servidor).
        # El cliente NO puede activarlo — seguridad y control centralizado.
        from backend.modules.db_simulator.manager import simulator_manager as _sim_mgr
        if _sim_mgr.is_enabled():
            logger.info("[DATABASE] 🎭 Modo simulador activo (config.json) — usando SQLite local")
            from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
            _sim_mgr.ensure_ready()
            driver = SimulatedFirebirdDriver()
            driver.connect()
            try:
                return driver.execute_query(query)
            finally:
                driver.disconnect()
        # ─────────────────────────────────────────────────────────────────────

        # ── MODO FIREBIRD REAL ────────────────────────────────────────────────
        # Si no hay db_params (ej: petición desde gafas sin parámetros),
        # usar los valores del .env como fallback
        if not db_params:
            logger.info(f"[DATABASE] Sin db_params en contexto — usando configuración del .env")
            db_params = {
                "host": settings.DB_HOST,
                "port": settings.DB_PORT,
                "database": settings.DB_NAME,
                "user": settings.DB_USER,
                "password": settings.DB_PASSWORD,
            }

        driver = None
        try:
            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)

            # Map username to user for DBConfig
            config_params = db_params.copy()
            if 'username' in config_params:
                config_params['user'] = config_params.pop('username')

            # Filter out non-DB params
            if 'confirm_data_sending' in config_params:
                del config_params['confirm_data_sending']

            config = DBConfig(**config_params)

            logger.info(f"[DATABASE] Conectando a Firebird {config_params.get('host')}:{config_params.get('port')}...")
            driver.connect(config)

            logger.info(f"[DATABASE] Ejecutando: {query[:120]}")
            results = driver.execute_query(query)

            logger.info(f"[DATABASE] ✓ {len(results)} filas retornadas")
            return results

        except Exception as e:
            logger.error(f"[DATABASE] ❌ Error Firebird: {str(e)}")
            raise
        finally:
            if driver:
                try:
                    driver.disconnect()
                except Exception:
                    pass
