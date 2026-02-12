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
from backend.modules.chat.sql_corrector import SQLCorrector
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

class ChatService:
    
    def __init__(self):
        self.sql_corrector = SQLCorrector()
        self.model_orchestrator = ModelFallbackOrchestrator()
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


    async def process_message(self, message: str, context: Dict[str, Any]) -> str:
        logger.info("="*80)
        logger.info(f"{LogPrefixes.CHAT_SERVICE} {LogEmojis.NEW_MESSAGE} NUEVO MENSAJE RECIBIDO")
        logger.info(f"{LogPrefixes.EMISOR} Usuario")
        logger.info(f"{LogPrefixes.MENSAJE} {message}")
        logger.info(f"{LogPrefixes.CONTEXTO} model_id={context.get('model_id')}")
        logger.info("="*80)
        
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
        
        # 1. Get DB Schema Context - Use semantic schema
        logger.info(f"[DATABASE] Generando esquema semántico optimizado...")
        db_context = get_semantic_schema()
        logger.info(f"[DATABASE] Esquema semántico: {len(db_context)} caracteres (optimizado para tokens)")
        
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
            # Standard SQL Mode
            system_prompt = f"""
Eres un asistente experto en bases de datos Firebird SQL.
Convierte preguntas en lenguaje natural a consultas SQL válidas.
{history_context}
{db_context}

INSTRUCCIONES CRÍTICAS:
1. Usa SOLO las tablas y columnas del esquema arriba
2. Para "productos" → tabla ARTICULO
3. Para "clientes" → tabla CLIENTE  
4. Para "facturas/ventas" → tabla DOCCAB
5. Genera SQL válido para Firebird 2.5
6. Delimita SQL con ```sql y ```
7. Si no requiere SQL, responde directamente
8. IMPORTANTE: Para limitar resultados usa FIRST N (ej: SELECT FIRST 10...)
9. NUNCA uses LIMIT, ROWS, o TOP - solo FIRST es válido en Firebird
"""
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
                sql_query = response_text.split(SQLDelimiters.START)[1].split(SQLDelimiters.END)[0].strip()
                
                # Limpiar query: remover punto y coma al final
                sql_query = sql_query.rstrip(';').strip()
                
                # Añadir FIRST si es SELECT y no tiene FIRST, y NO es una consulta de agregación simple
                sql_upper = sql_query.upper()
                is_aggregate = any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN('])
                
                if sql_upper.startswith(SQLKeywords.SELECT) and SQLKeywords.FIRST not in sql_upper and not is_aggregate:
                    # Insertar FIRST después de SELECT
                    sql_query = sql_query[:6] + f' {SQLKeywords.FIRST} {SQLLimits.DEFAULT_FIRST}' + sql_query[6:]
                    logger.info(f"{LogPrefixes.SQL} {LogEmojis.WARNING} Añadido FIRST {SQLLimits.DEFAULT_FIRST} automáticamente para limitar resultados")
                
                logger.info(f"[SQL] Consulta extraída: {sql_query}")
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
                # Check if we need user confirmation before sending data to AI
                require_confirmation = getattr(settings, 'REQUIRE_DB_DATA_CONFIRMATION', True)
                confirm_sending = context.get('confirm_data_sending', False) if context else False
                
                if require_confirmation and results and not confirm_sending:
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
                interpretation_prompt = (
                    f"Pregunta original: {message}\n"
                    f"Consulta SQL ejecutada: {sql_query}\n"
                    f"Resultados obtenidos: {results}\n\n"
                    "Responde al usuario siguiendo estas REGLAS ESTRICTAS:\n"
                    "1. NO inventes datos. Usa SOLO los resultados proporcionados.\n"
                    "2. Sé objetivo y directo. Evita frases subjetivas como 'Es importante destacar', 'Los precios pueden variar', etc.\n"
                    "3. Los precios están en EUROS (EUR). Nunca uses el símbolo $.\n"
                    "4. Presenta los datos de forma clara y concisa (lista o tabla si es apropiado).\n"
                    "5. Si no hay resultados, dilo claramente."
                )
                
                logger.info(f"[AI PROVIDER] 📤 Solicitando interpretación de resultados...")
                
                # Use ModelFallbackOrchestrator for interpretation to handle rate limits
                final_response, _ = await self.model_orchestrator.execute_with_fallback(
                    system_prompt="Eres un asistente experto en análisis de datos.",
                    user_message=interpretation_prompt,
                    feedback_callback=None
                )
                
                if not final_response:
                    final_response = f"He obtenido {len(results)} resultados, pero no he podido generar una explicación detallada en este momento debido a una alta carga en los servidores de IA. Aquí tienes los datos crudos: {results[:5]}"
                
                logger.info(f"[AI PROVIDER] 📥 Interpretación recibida")
                logger.info(f"[RESPUESTA FINAL] {final_response}")
                logger.info("="*80)
                
                return final_response
            except Exception as e:
                logger.error(f"[ERROR SQL] ❌ Error ejecutando consulta: {str(e)}")
                logger.error(f"[ERROR SQL] Consulta fallida: {sql_query}")
                return f"Intenté ejecutar una consulta pero falló: {str(e)}\nConsulta: {sql_query}"
        
        logger.info(f"[RESPUESTA FINAL] {response_text}")
        logger.info("="*80)
        return response_text



    def _get_db_context(self, db_params: Dict[str, Any]) -> str:
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
            
            # Get detailed info for important tables (limit to avoid token overflow)
            important_tables = ['ARTICULO', 'CLIENTE', 'FACTURA', 'PROVEEDOR', 'PEDIDO']
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
        logger.info(f"[DATABASE] Preparando ejecución de consulta...")
        
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            driver = None
            try:
                logger.info(f"[DATABASE] Intento {retry_count + 1}/{max_retries}")
                
                driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
                
                # Map username to user for DBConfig
                config_params = db_params.copy()
                if 'username' in config_params:
                    config_params['user'] = config_params.pop('username')
                
                # Filter out non-DB params
                if 'confirm_data_sending' in config_params:
                    del config_params['confirm_data_sending']
                
                config = DBConfig(**config_params)
                
                logger.info(f"[DATABASE] Conectando para ejecutar consulta...")
                driver.connect(config)
                
                logger.info(f"[DATABASE] Ejecutando: {query}")
                results = driver.execute_query(query)
                
                logger.info(f"[DATABASE] ✓ Consulta ejecutada: {len(results)} filas retornadas")
                
                return results
                
            except Exception as e:
                last_error = e
                retry_count += 1
                logger.error(f"[DATABASE] ❌ Error en intento {retry_count}: {str(e)}")
                
                if retry_count < max_retries:
                    import time
                    wait_time = retry_count * 0.5  # Espera incremental
                    logger.info(f"[DATABASE] Esperando {wait_time}s antes de reintentar...")
                    time.sleep(wait_time)
            finally:
                if driver:
                    try:
                        driver.disconnect()
                        logger.info(f"[DATABASE] ✓ Desconectado")
                    except:
                        pass
        
        # Si llegamos aquí, todos los intentos fallaron
        error_msg = f"Error después de {max_retries} intentos: {str(last_error)}"
        logger.error(f"[DATABASE] ❌ {error_msg}")
        raise Exception(error_msg)
