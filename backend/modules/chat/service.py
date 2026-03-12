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
            system_prompt = f"""Firebird 2.5 SQL. Convierte preguntas a SQL válido.
{history_context}
{db_context}
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
                        "Eres un asistente experto en análisis de datos Firebird. "
                        "REGLA ABSOLUTA: MUESTRA LOS DATOS TAL CUAL ESTÁN EN LA BASE DE DATOS. "
                        "Si un campo está vacío o es nulo, muéstralo como '(sin nombre)' o '(vacío)'. "
                        "NUNCA digas que hay un error de datos. NUNCA sugiereas verificar la tabla. "
                        "NUNCA inventes diagnósticos. Los datos vacíos son datos válidos. "
                        "Tu única misión es presentar los resultados de forma clara y añadir la justificación técnica."
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
                        f"SQL EJECUTADO:\n```sql\n{sql_query}\n```\n\n"
                        f"RESULTADOS ({n_rows} filas, columnas: {', '.join(cols_used)}):\n{results}\n\n"
                        + (
                            f"ADVERTENCIA DE DATOS: Las siguientes tablas tienen muy pocos registros "
                            f"y los datos podrían estar mal ubicados: "
                            f"{[t for t in tables_in_query if t.upper() in LOW_RECORD_TABLES]}\n\n"
                            if any(t.upper() in LOW_RECORD_TABLES for t in tables_in_query) else ""
                        ) +
                        "INSTRUCCIONES — responde con esta estructura EXACTA (respeta el HTML):\n\n"
                        "[Aquí va la respuesta directa a la pregunta. Lista o tabla Markdown si hay múltiples resultados. "
                        "Precios en EUR. NO inventes datos. Sin encabezados extra.]\n\n"
                        "<details>\n"
                        "<summary>🔍 Ver justificación y fuentes</summary>\n\n"
                        + low_record_html +
                        "**Tablas consultadas:** [lista las tablas del SQL]\n\n"
                        "**Columnas devueltas:** [lista las columnas del resultado]\n\n"
                        "**Registros devueltos:** [número exacto]\n\n"
                        "**SQL ejecutado:**\n"
                        "```sql\n"
                        "[copia aquí el SQL exacto]\n"
                        "```\n\n"
                        "**Cómo verificarlo:** [indica el campo clave para buscar en la BD, "
                        "ej: busca ARTICULO.CODIGO = X en la tabla ARTICULO]\n\n"
                        "**Razonamiento:** [explica brevemente qué tablas se unieron, "
                        "qué filtros se aplicaron y por qué el resultado responde a la pregunta. "
                        "Si alguna tabla tiene pocos registros, indícalo en ROJO con <span style='color:#c0392b'>texto</span>]\n\n"
                        "</details>\n\n"
                        "REGLAS:\n"
                        "1. NO inventes datos. Usa SOLO los resultados proporcionados.\n"
                        "2. Si no hay resultados, dilo claramente y sugiere por qué.\n"
                        "3. Sé objetivo. Sin frases como 'Es importante destacar'.\n"
                        "4. Si hay datos sospechosos (negativos, nulos, tablas con pocos registros), "
                        "menciónalos en ROJO con <span style='color:#c0392b'>texto</span>.\n"
                        "5. El bloque <details>...</details> debe estar SIEMPRE al final, "
                        "después de la respuesta principal."
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
