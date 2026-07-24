from typing import Dict, Any, List, Optional
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
from backend.modules.chat.request_trace import RequestTrace, PhaseTrace
import logging
import os
import base64
import asyncio
import time
import uuid

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
        # ── Clasificador de intenciones por IA (genérico, sin keywords) ──────
        # Se inicializa lazy en process_message para evitar imports circulares
        self._intent_classifier = None
        
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

    def _determine_database_mode(self, context: Dict[str, Any]) -> str:
        db_mode = context.get("db_mode")
        if db_mode == "simulator" or context.get("use_simulator"):
            return "simulator"
        if db_mode == "no_db" or context.get("no_db"):
            return "no_db"
        return "real"

    def _init_request_trace(self, context: Dict[str, Any]) -> RequestTrace:
        model_requested = context.get("preferred_model_id") or context.get("model_id")
        db_mode = self._determine_database_mode(context)
        trace_id = context.get("_trace_id") or str(uuid.uuid4())
        context["_trace_id"] = trace_id

        hard_timeout_ms = 120000 if context.get("deep_analysis") else 60000
        trace = RequestTrace.create(
            trace_id=trace_id,
            timeout_ms=hard_timeout_ms,
            model_requested=model_requested,
            database_mode=db_mode,
        )
        context["_request_trace"] = trace.to_dict()
        context["_request_deadline_monotonic"] = time.monotonic() + (hard_timeout_ms / 1000.0)
        return trace

    @staticmethod
    def _remaining_budget_ms(deadline_monotonic: float) -> int:
        return int(max(0.0, deadline_monotonic - time.monotonic()) * 1000)

    def _phase_timeout_s(self, deadline_monotonic: float, phase_budget_ms: int) -> float:
        remaining = self._remaining_budget_ms(deadline_monotonic)
        if remaining <= 0:
            raise TimeoutError("REQUEST_DEADLINE_EXCEEDED")
        return max(0.1, min(phase_budget_ms, remaining) / 1000.0)

    @staticmethod
    def _safe_results_preview(rows: List[Dict[str, Any]], max_rows: int = 3) -> str:
        if not rows:
            return "No se obtuvieron filas."
        cols = list(rows[0].keys()) if isinstance(rows[0], dict) else []
        return (
            f"Filas devueltas: {len(rows)}. "
            f"Columnas: {', '.join(cols[:8]) if cols else 'N/A'}. "
            f"Muestra: {rows[:max_rows]}"
        )


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

    def _is_clarification_request(self, message: str) -> bool:
        """
        Detecta si el usuario pide más detalle/justificación sobre la respuesta anterior.
        Estas peticiones NO generan nueva SQL — usan el historial de conversación.

        Ejemplos: "justifica", "explica", "en detalle", "por qué", "cómo lo calculaste",
                  "detállame", "amplía", "más información", "no entiendo".
        """
        msg = message.lower().strip()
        clarification_keywords = [
            "justifica", "justifícame", "justificame",
            "explica", "explícame", "explicame",
            "en detalle", "detállame", "detallame", "más detalle", "mas detalle",
            "por qué", "por que", "cómo lo calculaste", "como lo calculaste",
            "cómo llegaste", "como llegaste", "cómo obtuviste", "como obtuviste",
            "amplía", "amplia", "más información", "mas informacion",
            "no entiendo", "no lo entiendo", "qué significa", "que significa",
            "qué quiere decir", "que quiere decir",
            "profundiza", "profundízame", "profundizame",
            "dime más", "dime mas", "cuéntame más", "cuentame mas",
            "cómo verifico", "como verifico", "cómo compruebo", "como compruebo",
            "es fiable", "es correcto", "estás seguro", "estas seguro",
        ]
        return any(k in msg for k in clarification_keywords)

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
                preferred_model_id=context.get('preferred_model_id') or context.get('model_id'),
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

        # ── ProgressTracker: helper para reportar fases al frontend ──────────
        # El frontend hace polling a GET /api/chat/progress/{request_id}
        # y muestra las fases en tiempo real en el bubble "Pensando..."
        _progress_id = context.get('_progress_request_id')
        def _phase(phase: str, detail: str = "") -> None:
            """Reporta una fase al tracker (no-op si no hay request_id)."""
            if _progress_id:
                try:
                    from backend.modules.chat.progress_tracker import tracker as _tracker
                    _tracker.add_phase(_progress_id, phase, detail)
                except Exception:
                    pass  # Nunca fallar por el tracker

        trace = self._init_request_trace(context)
        deadline_monotonic = context.get("_request_deadline_monotonic", time.monotonic() + 60.0)

        def _start_phase(name: str, budget_ms: Optional[int] = None) -> PhaseTrace:
            return trace.start_phase(phase_name=name, timeout_budget_ms=budget_ms)

        def _finish_phase(
            phase_obj: PhaseTrace,
            status: str,
            model_actual: Optional[str] = None,
            sql_execution_ms: Optional[int] = None,
            rows_returned: Optional[int] = None,
            exception: Optional[Exception] = None,
        ) -> None:
            stats = getattr(self.model_orchestrator, "last_execution_stats", {}) or {}
            trace.finish_phase(
                phase_obj,
                status=status,
                model_actual=model_actual,
                retry_number=int(stats.get("retries", 0)),
                fallback_number=int(stats.get("fallbacks", 0)),
                sql_execution_ms=sql_execution_ms,
                rows_returned=rows_returned,
                exception=exception,
            )
            context["_request_trace"] = trace.to_dict()

        def _return_with_trace(value: str, status: str = "ok") -> str:
            trace.mark_done(status)
            context["_request_trace"] = trace.to_dict()
            return value

        # ══════════════════════════════════════════════════════════════════════
        # MODO BD — Resolución de fuente de datos con cadena de fallback
        # Prioridad: db_mode explícito > use_simulator > no_db > auto-detect
        # Cadena de fallback: Real BD → Simulador → Sin BD
        # ══════════════════════════════════════════════════════════════════════
        db_mode_explicit = context.get('db_mode')       # "real" | "simulator" | "no_db" | None
        use_simulator_flag = context.get('use_simulator', False)
        no_db_flag = context.get('no_db', False)
        db_params = context.get('db_params')
        db_params_empty = not db_params or not db_params.get('host') or not db_params.get('database')

        # Resolver modo efectivo desde el selector explícito del frontend
        if db_mode_explicit == 'no_db':
            no_db_flag = True
        elif db_mode_explicit == 'simulator':
            use_simulator_flag = True
            no_db_flag = False
        elif db_mode_explicit == 'real':
            use_simulator_flag = False
            no_db_flag = False

        # Comprobar disponibilidad del simulador
        simulator_available = False
        simulator_has_data = False
        try:
            from backend.modules.db_simulator.manager import simulator_manager
            simulator_available = simulator_manager.is_enabled()
            if simulator_available:
                _sim_st = simulator_manager.get_status()
                _rc = _sim_st.get("row_counts", {})
                simulator_has_data = bool(_rc) and any(v > 0 for v in _rc.values())
        except Exception as sim_err:
            logger.warning(f"[CHAT] No se pudo consultar el simulador: {sim_err}")

        # ── Modo Sin BD ───────────────────────────────────────────────────────
        if no_db_flag:
            logger.info("[CHAT] Modo Sin BD (conversacional puro)")
            _resp_no_db = await self._chat_no_db(message, context)
            return _return_with_trace(_resp_no_db)

        # ── Modo Simulador explícito ──────────────────────────────────────────
        if use_simulator_flag:
            if simulator_available and simulator_has_data:
                logger.info("[CHAT] Modo Simulador explícito — usando SQLite")
                db_params = {}
                db_params_empty = False
                context['db_params'] = db_params
            else:
                logger.warning("[CHAT] Simulador solicitado pero no disponible/sin datos → fallback Sin BD")
                _resp_sim_fb = await self._chat_no_db(message, context)
                return _return_with_trace(_resp_sim_fb)

        # ── Auto-detect: sin params reales → intentar simulador → sin BD ─────
        elif db_params_empty:
            if simulator_available and simulator_has_data:
                logger.info("[CHAT] Sin params reales; simulador disponible → usando simulador")
                db_params = {}
                db_params_empty = False
                context['db_params'] = db_params
            else:
                logger.info(f"[CHAT] Sin BD (db_params_empty={db_params_empty}, simulador no disponible)")
                _resp_auto_no_db = await self._chat_no_db(message, context)
                return _return_with_trace(_resp_auto_no_db)

        # ══════════════════════════════════════════════════════════════════════
        # FASE 1 — CLASIFICACIÓN DE INTENCIÓN POR IA (genérica, sin keywords)
        # ══════════════════════════════════════════════════════════════════════
        # El IntentClassifier usa el modelo IA local (Qwen3 30B LAN) para
        # determinar qué quiere el usuario en UNA sola llamada ligera.
        # Funciona con cualquier idioma, sinónimo, paráfrasis o expresión
        # coloquial — no depende de listas de palabras clave hardcodeadas.
        #
        # Si la IA falla (timeout, error de red), usa un clasificador
        # determinista de fallback basado en patrones semánticos amplios.
        # ══════════════════════════════════════════════════════════════════════
        from backend.modules.chat.intent_classifier import IntentClassifier, IntentType

        # Inicializar clasificador lazy (evita imports circulares en __init__)
        if self._intent_classifier is None:
            self._intent_classifier = IntentClassifier(orchestrator=self.model_orchestrator)

        conv_history = context.get('conversation_history', [])

        # Forzar deep_analysis si el checkbox del frontend está activo
        _force_deep = context.get('deep_analysis', False)

        _phase("🧠 Clasificando intención...", "IA analizando tu pregunta")
        _intent_phase = _start_phase("intent_classification", budget_ms=5000)
        try:
            _intent_timeout_s = self._phase_timeout_s(deadline_monotonic, 5000)
            intent = await asyncio.wait_for(
                self._intent_classifier.classify(
                    message,
                    conv_history,
                    preferred_model_id=context.get('preferred_model_id') or context.get('model_id'),
                ),
                timeout=_intent_timeout_s,
            )
            _finish_phase(
                _intent_phase,
                status="ok",
                model_actual=(getattr(self.model_orchestrator, "last_execution_stats", {}) or {}).get("model_used"),
            )
        except Exception as _intent_err:
            logger.warning(
                "[FASE1] intent_classification falló (%s) → fallback determinista",
                _intent_err,
            )
            intent = self._intent_classifier._classify_deterministic(message, conv_history)
            _finish_phase(
                _intent_phase,
                status="degraded",
                model_actual="deterministic-fallback",
                exception=_intent_err,
            )
            _phase(
                "⚠️ Clasificación degradada",
                "La IA tardó más de lo esperado; uso un clasificador determinista para continuar",
            )
        logger.info(
            f"[FASE1] Intención: {intent.intent} "
            f"(conf={intent.confidence:.2f}, force_deep={_force_deep}) | {intent.reasoning}"
        )
        _phase(
            f"✅ Intención detectada: {intent.intent}",
            f"Confianza {intent.confidence:.0%} · {'Análisis profundo' if _force_deep else 'Consulta estándar'}"
        )

        # ── FASE 1a: CONVERSACIONAL ───────────────────────────────────────────
        # RESILIENCIA: CONVERSACIONAL siempre bypasea DeepAnalysis, incluso con
        # force_deep=True. El checkbox "🔬 Análisis" solo aplica a consultas de
        # datos (DB_QUERY). Un saludo/pregunta general NUNCA activa el agente
        # multi-fase — sería un desperdicio de recursos y causaría errores 400
        # por contexto demasiado grande en el modelo local.
        if intent.is_conversational():
            logger.info(
                f"[FASE1] 💬 Conversacional → chat sin BD "
                f"(force_deep ignorado para intención conversacional)"
            )
            _resp_conv = await self._chat_no_db(message, context)
            return _return_with_trace(_resp_conv)

        # ── FASE 1b: ACLARACIÓN/JUSTIFICACIÓN ────────────────────────────────
        # El usuario pide más detalle sobre la respuesta anterior.
        # NO generamos nueva SQL — usamos el historial de conversación.
        # RESILIENCIA: igual que CONVERSACIONAL, CLARIFICATION no activa
        # DeepAnalysis aunque force_deep=True — el agente necesita datos nuevos.
        if intent.is_clarification():
            last_assistant_msg = ""
            last_user_question = ""
            for m in reversed(conv_history):
                if m.get('role') == 'assistant' and not last_assistant_msg:
                    last_assistant_msg = m.get('content', '')[:2000]
                elif m.get('role') == 'user' and last_assistant_msg and not last_user_question:
                    last_user_question = m.get('content', '')
                    break

            if last_assistant_msg:
                logger.info("[FASE1] 💬 Aclaración → justificación profunda sin nueva SQL")
                clarification_system = (
                    "Eres DEVIA, el asistente de datos de JDDC (empresa de climatización). "
                    "El usuario quiere entender mejor o verificar la respuesta que acabas de dar. "
                    "\n\n"
                    "REGLAS ABSOLUTAS:\n"
                    "• NUNCA escribas código SQL, ni una sola línea.\n"
                    "• NUNCA uses términos técnicos: 'query', 'tabla', 'columna', 'JOIN', 'WHERE', "
                    "'SELECT', 'FROM', 'GROUP BY', 'base de datos', 'registro', 'campo'.\n"
                    "• NUNCA uses # o ## para títulos. Usa **negrita** o emojis.\n"
                    "• Habla SIEMPRE en lenguaje de negocio.\n"
                    "• Los importes SIEMPRE en formato europeo: 1.234,56 EUR\n"
                    "• NUNCA inventes datos. Usa SOLO la información de la respuesta anterior.\n"
                    "\n"
                    "TU OBJETIVO: Explicar en profundidad POR QUÉ el dato es correcto y fiable, "
                    "usando únicamente la información que ya tienes de la respuesta anterior. "
                    "Desglosa el razonamiento paso a paso en lenguaje de negocio. "
                    "Indica cómo el usuario puede verificarlo manualmente en el programa de gestión. "
                    "Si hay matices o limitaciones, menciónalos con ⚠️."
                )
                clarification_prompt = (
                    f"PREGUNTA ORIGINAL DEL USUARIO: {last_user_question}\n\n"
                    f"RESPUESTA QUE DI ANTERIORMENTE:\n{last_assistant_msg}\n\n"
                    f"NUEVA PETICIÓN DEL USUARIO: {message}\n\n"
                    "INSTRUCCIONES:\n"
                    "1. Explica en detalle el razonamiento detrás de la respuesta anterior.\n"
                    "2. Desglosa los datos: qué documentos/registros se contaron, qué período, "
                    "qué se incluyó y qué se excluyó — en lenguaje de negocio.\n"
                    "3. Indica cómo el usuario puede verificarlo manualmente en el programa de gestión "
                    "(sin mencionar SQL ni términos técnicos).\n"
                    "4. Si hay limitaciones o matices importantes, menciónalos con ⚠️.\n"
                    "5. Propón una verificación adicional si es útil.\n"
                    "6. SIN código SQL. SIN términos técnicos. SIN # o ##.\n"
                    "7. Completa SIEMPRE la respuesta. No la cortes a mitad."
                )
                clarification_response, _ = await self.model_orchestrator.execute_with_fallback(
                    system_prompt=clarification_system,
                    user_message=clarification_prompt,
                    feedback_callback=None,
                    preferred_model_id=context.get('preferred_model_id') or context.get('model_id')
                )
                if clarification_response:
                    logger.info("[FASE1] ✅ Justificación profunda generada")
                    return clarification_response
                logger.warning("[FASE1] ⚠️ Justificación profunda falló — continuando con flujo normal")
            else:
                # Sin historial → tratar como DB_QUERY
                logger.info("[FASE1] Sin historial para aclaración → redirigiendo a DB_QUERY")

        # ── FASE 1c: ANÁLISIS PROFUNDO ────────────────────────────────────────
        # DEVIA — Ultra-resiliente:
        # El DeepAnalysisAgent tiene un timeout global configurable.
        # Si supera el timeout → fallback al flujo normal (no error al usuario).
        # El timeout se calcula dinámicamente según el modo BD y el modelo LAN.
        _wants_deep = _force_deep or intent.is_deep_analysis()
        _is_fast_db_intent = intent.intent in (IntentType.DB_QUERY, IntentType.UNKNOWN)
        _run_deep_before_fast = _wants_deep and (not _is_fast_db_intent)
        _run_deep_after_fast = _wants_deep and _is_fast_db_intent

        if _run_deep_before_fast:
            logger.info("[CHAT] 🔬 Activando DeepAnalysisAgent (análisis multi-fase)")
            _phase("🔬 Iniciando análisis profundo multi-fase...", "DeepAnalysisAgent v3.0")
            _deep_phase = _start_phase("deep_analysis", budget_ms=self._remaining_budget_ms(deadline_monotonic))
            try:
                from backend.modules.chat.deep_analysis_agent import DeepAnalysisAgent
                # Obtener contexto SIUO (mismo esquema Firebird siempre —
                # el simulador traduce la sintaxis transparentemente)
                try:
                    retriever = get_context_retriever()
                    db_context, _ = retriever.get_context(message)
                except Exception:
                    db_context = get_semantic_schema()

                _deep_db_params = context.get('db_params')

                async def _async_sql_executor(q: str) -> list:
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(
                        None, self._execute_sql, q, _deep_db_params
                    )

                agent = DeepAnalysisAgent(
                    orchestrator=self.model_orchestrator,
                    db_context=db_context,
                    sql_executor=_async_sql_executor,
                    sql_normalizer=self.sql_normalizer,
                    # Pasar el progress tracker para que el agente reporte fases
                    progress_id=_progress_id,
                    preferred_model_id=context.get('preferred_model_id') or context.get('model_id'),
                )
                # Limpiar prefijo /deep del mensaje
                clean_msg = message.strip()
                for prefix in ["/deep ", "/deep", "/analisis ", "/analisis"]:
                    if clean_msg.lower().startswith(prefix):
                        clean_msg = clean_msg[len(prefix):].strip()
                        break

                conv_history = context.get('conversation_history', [])

                # ── Sin timeout en el backend ─────────────────────────────────
                # DEVIA: el backend espera todo lo que necesite el modelo LAN.
                # El frontend gestiona la espera con heartbeat + extensiones de
                # timeout automáticas (chat-recovery.js): mientras el backend
                # responda al ping /health, el frontend sigue esperando.
                # No hay asyncio.wait_for aquí — el backend no corta la conexión.
                _phase(
                    "⏳ Análisis profundo en curso...",
                    "El modelo LAN está procesando — el frontend seguirá esperando"
                )
                logger.info("[CHAT] 🔬 DeepAgent iniciado (sin timeout de backend)")

                _deep_timeout_s = self._phase_timeout_s(deadline_monotonic, self._remaining_budget_ms(deadline_monotonic))
                result = await asyncio.wait_for(agent.analyze(clean_msg, conv_history), timeout=_deep_timeout_s)
                logger.info("[CHAT] ✅ DeepAnalysisAgent completado")
                _phase("✅ Análisis profundo completado", f"{len(result)} chars de respuesta")
                _finish_phase(
                    _deep_phase,
                    status="ok",
                    model_actual=(getattr(self.model_orchestrator, "last_execution_stats", {}) or {}).get("model_used"),
                )
                trace.mark_done("ok")
                context["_request_trace"] = trace.to_dict()
                return result

            except Exception as e:
                logger.error(f"[CHAT] ❌ DeepAnalysisAgent falló: {e} — continuando con flujo normal")
                _finish_phase(_deep_phase, status="failed", exception=e)
                _phase(
                    "⚠️ Análisis profundo falló — usando flujo estándar",
                    str(e)[:80]
                )
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
            _is_simulator_active = False
            try:
                from backend.modules.db_simulator.manager import simulator_manager as _sm
                if _sm.is_enabled():
                    _is_simulator_active = True
                    from backend.modules.db_simulator.schema import TABLE_SCHEMAS
                    _sim_tables = ", ".join(sorted(TABLE_SCHEMAS.keys()))
                    _sim_note = (
                        f"\n⚠️ MODO SIMULADOR ACTIVO (SQLite local — snapshot de Firebird).\n"
                        f"TABLAS DISPONIBLES (SOLO ESTAS): {_sim_tables}\n"
                        f"NO generes SQL contra tablas que no estén en esta lista.\n"
                        f"Escribe SQL con sintaxis SQLite (LIMIT N en lugar de FIRST N, "
                        f"strftime en lugar de EXTRACT) — el sistema convierte automáticamente.\n"
                        f"PROYECTOS y DOCCAB.CODPROYECTO están disponibles en el simulador.\n"
                    )
            except Exception:
                pass

            # ── Razonamiento semántico multi-fase ────────────────────────────
            # DEVIA: antes de construir el system_prompt, el SemanticReasoningEngine
            # analiza la pregunta para detectar el dominio de negocio (proyectos,
            # certificaciones, retenciones, etc.) y enriquece el contexto con
            # conocimiento JDDC específico + hints SQL deterministas.
            # Ultra-resiliente: si falla, continúa con el prompt base sin modificar.
            _reasoning_enrichment = ""
            try:
                from backend.modules.chat.semantic_reasoning_engine import get_reasoning_engine
                _reasoning_engine = get_reasoning_engine()
                _reasoning_result = _reasoning_engine.reason(
                    question=message,
                    db_context=db_context,
                    is_simulator=_is_simulator_active,
                )
                if _reasoning_result.confidence >= 0.5:
                    # Construir bloque de enriquecimiento para el system_prompt
                    _parts = []
                    if _reasoning_result.business_context:
                        _parts.append(_reasoning_result.business_context)
                    if _reasoning_result.hints:
                        _hints_txt = "\n".join(f"  • {h}" for h in _reasoning_result.hints)
                        _parts.append(f"\n🎯 HINTS SQL PARA ESTA CONSULTA:\n{_hints_txt}")
                    if _reasoning_result.filters_suggested:
                        _filters_txt = "\n".join(f"  • {f}" for f in _reasoning_result.filters_suggested)
                        _parts.append(f"\n🔍 FILTROS SUGERIDOS:\n{_filters_txt}")
                    if _parts:
                        _reasoning_enrichment = "\n".join(_parts)
                    logger.info(
                        f"[REASONING] Dominio={_reasoning_result.domain} "
                        f"conf={_reasoning_result.confidence:.0%} "
                        f"hints={len(_reasoning_result.hints)} "
                        f"steps={_reasoning_result.reasoning_steps}"
                    )
                    _phase(
                        f"🧩 Dominio detectado: {_reasoning_result.domain}",
                        f"Confianza {_reasoning_result.confidence:.0%} · "
                        f"{len(_reasoning_result.hints)} hints SQL"
                    )
            except Exception as _re:
                logger.warning(f"[REASONING] SemanticReasoningEngine falló: {_re} — continuando sin enriquecimiento")

            system_prompt = f"""Firebird 2.5 SQL. Convierte preguntas a SQL válido.
{history_context}
{db_context}{_sim_note}
{_reasoning_enrichment}
REGLAS(no negociar):
• FIRST N no LIMIT/TOP/ROWS: SELECT FIRST 10 CODIGO FROM ARTICULO
• UPPER(col) LIKE UPPER('%x%') para texto (Firebird es case-sensitive)
• BLOB(DESCRIPCION en ARTICULO/DOCCAB) → NO usar en GROUP BY/ORDER BY/SELECT si hay GROUP BY; usa DESCRIPCIONCORTA o NOMBRE
• ARTICULO.STOCK no existe → usar STOCKARTICULO
• DOCCAB.TIPO (verificado): 0=presupuesto, 1=pedido_cli, 2=albaran_cli, 3=factura_cli, 10=presupuesto_prov, 11=pedido_prov, 12=albaran_prov, 13=factura_prov
• CERTIFICACIONES DE OBRA: facturas (TIPO=3) con CODPROYECTO no nulo → JOIN PROYECTOS ON PROYECTOS.CODIGO=DOCCAB.CODPROYECTO
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
TIPOS DE DOCUMENTOS (TABLA DOCCAB, COLUMNA TIPO) — VERIFICADO CON BD REAL JDDC:
- Para "facturas" (cliente) -> WHERE TIPO = 3
- Para "albaranes" (cliente) -> WHERE TIPO = 2
- Para "presupuestos" (cliente) -> WHERE TIPO = 0
- Para "pedidos" (cliente) -> WHERE TIPO = 1
- Para "facturas proveedor" -> WHERE TIPO = 13
- Para "albaranes proveedor" -> WHERE TIPO = 12
- Para "pedidos proveedor" -> WHERE TIPO = 11
- Para "presupuestos proveedor" -> WHERE TIPO = 10
- Para "certificaciones de obra" -> TIPO = 3 (factura cliente) con CODPROYECTO no nulo
- Para "SAT" u "órdenes de trabajo" -> WHERE TIPO = 2 (albarán cliente con descripción SAT)
NOTA: TIPO=13 es factura PROVEEDOR (compras), TIPO=3 es factura CLIENTE (ventas).

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
        _phase("🤖 Generando consulta SQL...", "IA construyendo la consulta a la base de datos")
        _sql_gen_phase = _start_phase("sql_selection_or_generation", budget_ms=15000)
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
        try:
            _sql_gen_timeout_s = self._phase_timeout_s(deadline_monotonic, 15000)
            response_text, used_model_id = await asyncio.wait_for(
                self.model_orchestrator.execute_with_fallback(
                    system_prompt=system_prompt,
                    user_message=message,
                    images=context.get('images'),
                    feedback_callback=None,  # TODO: Implement real-time feedback to user
                    preferred_model_id=context.get('preferred_model_id') or context.get('model_id'),
                    execution_policy={"max_retries_per_model": 1, "max_models": 2},
                    deadline_monotonic=deadline_monotonic,
                ),
                timeout=_sql_gen_timeout_s,
            )
            _finish_phase(_sql_gen_phase, status="ok", model_actual=used_model_id)
        except Exception as _sql_gen_err:
            _finish_phase(_sql_gen_phase, status="failed", exception=_sql_gen_err)
            return _return_with_trace("Se agotó el tiempo durante sql_selection_or_generation.", status="failed")
        
        if not response_text:
            logger.error(f"[AI PROVIDER] ❌ Todos los modelos fallaron — activando resiliencia adaptativa")
            # ── RESILIENCIA ADAPTATIVA ────────────────────────────────────────────
            # Cuando la IA no está disponible, el AdaptiveResilienceEngine genera
            # una respuesta de calidad usando datos reales del simulador SQLite.
            # NUNCA devuelve "no disponible" si hay datos en el simulador.
            # DEVIA: backend/modules/chat/adaptive_resilience.py
            try:
                from backend.modules.chat.adaptive_resilience import get_resilience_engine

                # Crear executor async que usa el mismo mecanismo que el chat
                _db_params_for_resilience = context.get('db_params')
                async def _resilience_sql_executor(q: str) -> list:
                    import asyncio as _asyncio
                    loop = _asyncio.get_running_loop()
                    return await loop.run_in_executor(
                        None, self._execute_sql, q, _db_params_for_resilience
                    )

                resilience_engine = get_resilience_engine(
                    sql_executor=_resilience_sql_executor
                )
                resilience_result = await resilience_engine.generate_response(
                    question=message,
                    context=context,
                )
                logger.info(
                    f"[RESILIENCE] Respuesta adaptativa generada: "
                    f"dominio={resilience_result.domain} "
                    f"calidad={resilience_result.quality} "
                    f"filas={resilience_result.data_rows} "
                    f"sqls={resilience_result.sqls_successful}/{resilience_result.sqls_executed}"
                )
                if resilience_result.quality in ("high", "medium"):
                    _phase(
                        "✅ Respuesta generada (modo sin IA)",
                        f"Dominio: {resilience_result.domain} · {resilience_result.data_rows} filas"
                    )
                    return resilience_result.response
                # Si la calidad es baja pero hay algo, devolver igualmente
                if resilience_result.response and resilience_result.data_rows > 0:
                    return resilience_result.response
            except Exception as _res_err:
                logger.error(f"[RESILIENCE] AdaptiveResilienceEngine falló: {_res_err}")

            # Último recurso: mensaje de error informativo
            return (
                "❌ El servidor de IA no está disponible en este momento.\n"
                "Comprueba que el servidor Qwen3 esté activo e inténtalo de nuevo.\n\n"
                "💡 **Mientras tanto**, puedes:\n"
                "- Verificar que el servidor LAN (http://jddcia.local) esté activo\n"
                "- Usar el simulador de BD para consultas básicas\n"
                "- Cambiar a modo 'Sin IA' en Configuración para respuestas deterministas"
            )
        
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
                    # asyncio ya importado a nivel de módulo — NO reimportar aquí
                    # (reimportarlo como local rompe closures que usan asyncio en la misma función)
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
                _phase("🗄️ Ejecutando consulta en la base de datos...", sql_query[:80] + ("..." if len(sql_query) > 80 else ""))

                _sql_val_phase = _start_phase("sql_validation", budget_ms=5000)
                _finish_phase(_sql_val_phase, status="ok")
                _firebird_phase = _start_phase("firebird_execution", budget_ms=15000)
                _firebird_started = time.monotonic()
                
                # Execute with auto-correction
                try:
                    _firebird_timeout_s = self._phase_timeout_s(deadline_monotonic, 15000)
                    results = await asyncio.wait_for(
                        self.sql_corrector.execute_with_correction(
                            sql_query=sql_query,
                            original_question=message,
                            db_context=db_context,
                            ai_provider=provider,
                            execute_func=lambda q: self._execute_sql(q, context.get('db_params')),
                            max_retries=min(1, self.config.get("max_sql_retries", 1))
                        ),
                        timeout=_firebird_timeout_s,
                    )
                    _sql_ms = int((time.monotonic() - _firebird_started) * 1000)
                    _finish_phase(_firebird_phase, status="ok", sql_execution_ms=_sql_ms, rows_returned=len(results))
                except Exception as _fb_err:
                    _sql_ms = int((time.monotonic() - _firebird_started) * 1000)
                    _finish_phase(_firebird_phase, status="failed", sql_execution_ms=_sql_ms, exception=_fb_err)
                    raise
                
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
                        "REGLAS ABSOLUTAS — NUNCA las incumplas:\n"
                        "• NUNCA escribas código SQL, ni una sola línea. Ni en el cuerpo ni en los detalles.\n"
                        "• NUNCA uses términos técnicos: 'query', 'tabla', 'columna', 'JOIN', 'WHERE', "
                        "'SELECT', 'FROM', 'GROUP BY', 'base de datos', 'registro', 'campo'.\n"
                        "• NUNCA uses símbolos Markdown de estructura como # o ## para títulos. "
                        "Usa texto en negrita (**texto**) o emojis para destacar secciones.\n"
                        "• Habla SIEMPRE en lenguaje de negocio: 'facturas emitidas', 'clientes activos', "
                        "'importe total', 'período analizado', 'documentos incluidos'.\n"
                        "• Los importes SIEMPRE en formato europeo: 1.234,56 EUR\n"
                        "• Nulos o vacíos → '(sin datos)'\n"
                        "• NUNCA inventes datos. Usa SOLO los resultados proporcionados.\n"
                        "\n"
                        "ANÁLISIS OBLIGATORIO — menciona SIEMPRE si aplica:\n"
                        "1. ¿Los datos son coherentes? ¿Hay valores extremos o sospechosos?\n"
                        "2. ¿Qué período cubre la consulta? ¿Hay datos de todos los meses?\n"
                        "3. ¿Qué tipos de documentos se incluyen/excluyen y por qué?\n"
                        "4. ¿El resultado responde completamente a la pregunta o hay matices?\n"
                        "\n"
                        "FORMATO OBLIGATORIO — usa EXACTAMENTE esta estructura:\n"
                        "1. Respuesta directa en lenguaje natural (párrafo o tabla Markdown)\n"
                        "2. Análisis crítico breve (2-3 puntos clave, sin # ni ##)\n"
                        "3. Bloque <details> con justificación de negocio (SIN SQL, SIN términos técnicos)\n"
                        "4. Propuesta de verificación adicional al final (💡)\n"
                        "\n"
                        "SOBRE EL BLOQUE <details>:\n"
                        "• Es para usuarios de negocio que quieren entender POR QUÉ el dato es fiable.\n"
                        "• Explica en lenguaje de negocio: qué documentos se contaron, qué período, "
                        "qué se excluyó, cómo verificarlo en el programa de gestión (sin mencionar SQL).\n"
                        "• NUNCA incluyas código SQL dentro del bloque <details>.\n"
                        "• Puedes mencionar nombres de conceptos de negocio (facturas, albaranes, "
                        "presupuestos, clientes, artículos) pero NO nombres técnicos de tablas.\n"
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
                            f"ADVERTENCIA INTERNA: Las siguientes fuentes de datos tienen muy pocos registros "
                            f"y los datos podrían estar incompletos: "
                            f"{[t for t in tables_in_query if t.upper() in LOW_RECORD_TABLES]}\n\n"
                            if any(t.upper() in LOW_RECORD_TABLES for t in tables_in_query) else ""
                        ) +
                        "INSTRUCCIONES — responde con esta estructura EXACTA (respeta el HTML):\n\n"
                        "**📊 Respuesta**\n"
                        "[Respuesta directa en lenguaje de negocio. "
                        "Tabla Markdown si hay múltiples resultados (usa | col | col | formato). "
                        "Importes en formato europeo (1.234,56 EUR). "
                        "SIN términos técnicos. SIN código SQL. SIN símbolos # o ##.]\n\n"
                        "**🔍 Análisis**\n"
                        "[2-3 puntos clave: coherencia de los datos, período cubierto, "
                        "qué tipos de documentos se incluyen, matices importantes. "
                        "En lenguaje de negocio, sin términos técnicos.]\n\n"
                        "<details>\n"
                        "<summary>📋 Ver justificación detallada</summary>\n\n"
                        + low_record_html +
                        "**Período analizado:** [rango de fechas de los datos, en lenguaje natural]\n\n"
                        "**Qué incluye este cálculo:** [en lenguaje de negocio: qué tipos de documentos "
                        "se consideraron — facturas emitidas, albaranes, presupuestos aceptados, etc. "
                        "SIN mencionar nombres técnicos de tablas ni SQL]\n\n"
                        "**Qué NO incluye:** [qué se excluyó y por qué, en lenguaje de negocio]\n\n"
                        "**Cómo verificarlo:** [cómo el usuario puede comprobar el dato en el programa "
                        "de gestión — por ejemplo: 'Ve a Facturación > Listado de facturas, filtra por "
                        "el año 2026 y suma la columna Total'. SIN mencionar SQL ni términos técnicos.]\n\n"
                        "**Fiabilidad:** [si el dato es completo, parcial, o tiene limitaciones conocidas. "
                        "Indica el nivel de confianza: alto, medio, bajo y por qué.]\n\n"
                        "**Datos de respaldo:** [2-3 datos adicionales de los resultados que corroboran "
                        "la cifra principal — por ejemplo: número de documentos, media por documento, "
                        "rango mínimo/máximo. Esto demuestra que el dato es correcto.]\n\n"
                        "</details>\n\n"
                        "---\n"
                        "💡 *¿Quieres que profundice más? Puedo analizar los datos uno a uno, "
                        "comparar con períodos anteriores, o desglosar por cliente, artículo o tipo de documento.*\n\n"
                        "REGLAS ABSOLUTAS:\n"
                        "1. NO inventes datos. Usa SOLO los resultados proporcionados.\n"
                        "2. Si no hay resultados, dilo claramente y sugiere por qué.\n"
                        "3. NUNCA escribas código SQL en ninguna parte de la respuesta.\n"
                        "4. NUNCA uses # o ## para títulos. Usa **negrita** o emojis.\n"
                        "5. Si hay datos sospechosos (negativos, nulos, valores extremos), "
                        "menciónalos con ⚠️ en lenguaje de negocio.\n"
                        "6. El bloque <details>...</details> debe estar SIEMPRE presente.\n"
                        "7. La propuesta 💡 debe estar SIEMPRE al final.\n"
                        "8. Completa SIEMPRE la respuesta. No la cortes a mitad."
                    )
                    
                    _phase(
                        f"📊 Interpretando {n_rows} resultado{'s' if n_rows != 1 else ''}...",
                        "IA generando respuesta en lenguaje de negocio"
                    )
                    logger.info(f"[AI PROVIDER] Solicitando interpretacion WEB (Qwen3 LAN preferido)...")
                    _interpret_phase = _start_phase("result_interpretation", budget_ms=20000)
                    try:
                        _interpret_timeout_s = self._phase_timeout_s(deadline_monotonic, 20000)
                        final_response, _ = await asyncio.wait_for(
                            self.model_orchestrator.execute_with_fallback(
                                system_prompt=interpretation_system,
                                user_message=interpretation_prompt,
                                feedback_callback=None,
                                preferred_model_id=context.get('preferred_model_id') or context.get('model_id'),
                                execution_policy={"max_retries_per_model": 1, "max_models": 2},
                                deadline_monotonic=deadline_monotonic,
                            ),
                            timeout=_interpret_timeout_s,
                        )
                        _finish_phase(
                            _interpret_phase,
                            status="ok",
                            model_actual=(getattr(self.model_orchestrator, "last_execution_stats", {}) or {}).get("model_used"),
                            rows_returned=n_rows,
                        )
                    except Exception as _interp_err:
                        _finish_phase(_interpret_phase, status="failed", exception=_interp_err, rows_returned=n_rows)
                        final_response = (
                            "Se han obtenido datos de la BD real. "
                            "El análisis adicional no pudo completarse dentro del tiempo establecido.\n\n"
                            f"analysis_status: TIMEOUT\n"
                            f"data_status: AVAILABLE\n"
                            f"degraded_response: true\n"
                            f"{self._safe_results_preview(results)}"
                        )
                    
                    if not final_response:
                        final_response = (
                            f"He obtenido {len(results)} resultados, pero no he podido generar "
                            f"una explicacion detallada. Datos: {results[:5]}"
                        )
                
                logger.info(f"[AI PROVIDER] 📥 Interpretación recibida")
                logger.info(f"[RESPUESTA FINAL] {final_response}")
                logger.info("="*80)

                # analysis=true no bloquea el fast path: solo enriquece si queda presupuesto
                if _run_deep_after_fast:
                    _remaining = self._remaining_budget_ms(deadline_monotonic)
                    if _remaining >= 10000:
                        _post_deep_phase = _start_phase("deep_analysis", budget_ms=_remaining)
                        try:
                            from backend.modules.chat.deep_analysis_agent import DeepAnalysisAgent
                            try:
                                retriever = get_context_retriever()
                                post_db_context, _ = retriever.get_context(message)
                            except Exception:
                                post_db_context = get_semantic_schema()

                            async def _post_async_sql_executor(q: str) -> list:
                                loop = asyncio.get_running_loop()
                                return await loop.run_in_executor(None, self._execute_sql, q, context.get('db_params'))

                            post_agent = DeepAnalysisAgent(
                                orchestrator=self.model_orchestrator,
                                db_context=post_db_context,
                                sql_executor=_post_async_sql_executor,
                                sql_normalizer=self.sql_normalizer,
                                progress_id=_progress_id,
                                preferred_model_id=context.get('preferred_model_id') or context.get('model_id'),
                            )
                            _post_timeout_s = self._phase_timeout_s(deadline_monotonic, _remaining)
                            post_result = await asyncio.wait_for(post_agent.analyze(message, conv_history), timeout=_post_timeout_s)
                            _finish_phase(
                                _post_deep_phase,
                                status="ok",
                                model_actual=(getattr(self.model_orchestrator, "last_execution_stats", {}) or {}).get("model_used"),
                            )
                            final_response = (
                                f"{final_response}\n\n"
                                "---\n"
                                "Análisis adicional completado:\n"
                                f"{post_result}"
                            )
                        except Exception as _post_err:
                            _finish_phase(_post_deep_phase, status="failed", exception=_post_err)
                            final_response = (
                                f"{final_response}\n\n"
                                "---\n"
                                "analysis_status: TIMEOUT\n"
                                "data_status: AVAILABLE\n"
                                "degraded_response: true\n"
                                "El análisis adicional no pudo completarse dentro del tiempo restante."
                            )
                
                _delivery_phase = _start_phase("response_delivery", budget_ms=self._remaining_budget_ms(deadline_monotonic))
                _finish_phase(_delivery_phase, status="ok")
                trace.mark_done("ok")
                context["_request_trace"] = trace.to_dict()
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
        _delivery_phase = _start_phase("response_delivery", budget_ms=self._remaining_budget_ms(deadline_monotonic))
        _finish_phase(_delivery_phase, status="ok")
        trace.mark_done("ok")
        context["_request_trace"] = trace.to_dict()
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

        SEGURIDAD: El DatabaseSecurityGuard valida el SQL ANTES de ejecutarlo.
        Cualquier intento de escritura (INSERT/UPDATE/DELETE/DROP/etc.) es bloqueado
        con DatabaseSecurityError. Esta validación es OBLIGATORIA y no se puede
        desactivar — protege la BD real de modificaciones accidentales o maliciosas.
        """
        logger.info(f"[DATABASE] Preparando ejecución de consulta...")

        # ── SEGURIDAD: Validación de solo lectura (OBLIGATORIA) ───────────────
        # Se ejecuta SIEMPRE, tanto en modo simulador como en modo real.
        # El guard tiene 6 capas de validación y es fail-safe (bloquea ante duda).
        try:
            from backend.core.security.db_security_guard import (
                get_db_security_guard, DatabaseSecurityError
            )
            _guard = get_db_security_guard()
            _guard.validate_or_raise(query, context="chat_service._execute_sql")
        except DatabaseSecurityError as _sec_err:
            logger.critical(f"[SECURITY] 🚨 CONSULTA BLOQUEADA: {_sec_err}")
            raise ValueError(
                f"⛔ Consulta bloqueada por seguridad: solo se permiten consultas de lectura (SELECT). "
                f"Detalle: {_sec_err}"
            )
        except Exception as _sec_import_err:
            # Si el módulo de seguridad no carga, BLOQUEAR por fail-safe
            logger.critical(
                f"[SECURITY] 🚨 Módulo de seguridad no disponible — bloqueando consulta: {_sec_import_err}"
            )
            raise ValueError(
                "⛔ Sistema de seguridad no disponible — consulta bloqueada por precaución."
            )

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
