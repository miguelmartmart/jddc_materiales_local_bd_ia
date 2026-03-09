"""
ResponseSummarizer — Resúmenes paginados de resultados de BD.

RESPONSABILIDAD:
  Cuando una consulta devuelve muchos registros, resume los resultados
  en N líneas y pregunta al usuario si quiere ver más o todos.

PRINCIPIO:
  - Si hay <= SUMMARY_THRESHOLD registros → mostrar todos directamente
  - Si hay > SUMMARY_THRESHOLD → mostrar resumen + preguntar
  - El resumen lo genera Qwen3 LAN (nunca internet)
  - Si Qwen3 no está disponible → resumen determinista local

PAGINACIÓN:
  El estado de paginación se guarda en el historial de conversación
  para que el usuario pueda pedir "muéstrame los siguientes 10" o
  "dame todos" y el sistema sepa qué datos mostrar.

CONSTANTES:
  Todas en constants.py → SummaryConfig
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Constantes (importadas de constants.py) ──────────────────────────────────
# Evitar importar settings aquí — solo constantes de comportamiento

SUMMARY_THRESHOLD   = 15   # Más de N registros → resumir (web)
SUMMARY_LINES       = 10   # Líneas en el resumen
PAGE_SIZE_DEFAULT   = 10   # Registros por página al paginar (web)
PAGE_SIZE_MAX       = 100  # Máximo que se puede pedir de una vez

# ─── Constantes MetaGlass (gafas) ─────────────────────────────────────────────
# Leídas de variables de entorno para ser configurables sin redeployar
# Valores por defecto conservadores para TTS (listas cortas)
METAGLASS_PAGINATION_THRESHOLD = int(os.environ.get("METAGLASS_PAGINATION_THRESHOLD", "5"))
METAGLASS_PAGE_SIZE            = int(os.environ.get("METAGLASS_PAGE_SIZE", "3"))

# Campos prioritarios para mostrar en resúmenes (orden de preferencia)
DISPLAY_PRIORITY = [
    "NOMBRE", "DESCRIPCION", "DESCRIPCIONCORTA", "RAZONSOCIAL",
    "REFERENCIA", "CODIGO", "CODART", "CODCLI", "NUMDOC",
    "TITULO", "CONCEPTO", "FAMILIA", "CATEGORIA",
]

# Campos numéricos para incluir en resúmenes
NUMERIC_FIELDS = [
    "TOTAL", "IMPORTE", "PRECIO", "CANTIDAD", "STOCK",
    "BASE", "TOTALIVA", "DESCUENTO", "MARGEN",
]

# Frases EXACTAS que indican paginación (no palabras sueltas para evitar falsos positivos)
PAGINATION_TRIGGERS = {
    "ver todos", "ver todas", "muéstrame todos", "muéstrame todas",
    "mostrar todos", "mostrar todas", "dame todos", "dame todas",
    "lista completa", "todos los resultados", "todas las resultados",
    "el resto", "los demás", "las demás",
    "siguiente página", "siguiente pagina", "más resultados", "mas resultados",
    "continúa", "continua", "siguiente",
}

# Palabras de acción de paginación (solo válidas si van con número)
PAGINATION_ACTION_WORDS = {"dame", "muestra", "muéstrame", "ver", "mostrar"}

# Palabras que indican número específico
PAGINATION_NUMBER_WORDS = {
    "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "veinte": 20, "treinta": 30, "cincuenta": 50,
    "cien": 100, "todos": -1, "todas": -1,
}


# ─── Clase principal ──────────────────────────────────────────────────────────

class ResponseSummarizer:
    """
    Genera respuestas resumidas con paginación para resultados de BD.

    Uso en ChatService:
        summarizer = ResponseSummarizer()
        response, pagination_state = summarizer.summarize(
            question=message,
            results=results,
            sql_query=sql_query,
        )
        # Si pagination_state no es None, guardar en historial
    """

    def summarize(
        self,
        question: str,
        results: List[Dict[str, Any]],
        sql_query: str,
        max_lines: int = SUMMARY_LINES,
    ) -> Tuple[str, Optional[Dict]]:
        """
        Genera respuesta resumida si hay muchos resultados.

        Returns:
            (response_text, pagination_state)
            - response_text: texto para mostrar al usuario
            - pagination_state: dict con datos para paginación, o None si no aplica
        """
        n = len(results)

        if n == 0:
            return "No se encontraron resultados para tu consulta.", None

        if n <= SUMMARY_THRESHOLD:
            # Pocos resultados → mostrar todos directamente
            return self._format_all(results, question), None

        # Muchos resultados → resumir y preguntar
        summary = self._build_summary(results, question, max_lines)
        pagination_state = {
            "full_results": results,
            "sql_query":    sql_query,
            "question":     question,
            "total":        n,
            "shown":        0,
            "page_size":    PAGE_SIZE_DEFAULT,
        }

        response = (
            f"{summary}\n\n"
            f"📊 **Total encontrado: {n} registros**\n"
            f"¿Quieres ver más? Puedes decir:\n"
            f"• *\"muéstrame los primeros 10\"*\n"
            f"• *\"dame todos\"*\n"
            f"• *\"siguiente página\"*"
        )

        return response, pagination_state

    def handle_pagination_request(
        self,
        message: str,
        pagination_state: Dict,
    ) -> Tuple[str, Optional[Dict]]:
        """
        Maneja una petición de paginación del usuario.
        Detecta si quiere ver más, todos, o un número específico.

        Returns:
            (response_text, updated_pagination_state)
            - Si updated_pagination_state es None → paginación terminada
        """
        results  = pagination_state.get("full_results", [])
        shown    = pagination_state.get("shown", 0)
        total    = pagination_state.get("total", len(results))
        question = pagination_state.get("question", "")

        # Detectar cuántos quiere ver
        n_requested = self._detect_requested_count(message)

        if n_requested == -1:
            # Quiere todos
            remaining = results[shown:]
            response  = self._format_all(remaining, question, prefix=f"Aquí están todos los {total} resultados:")
            return response, None  # Paginación terminada

        if n_requested is None:
            # "siguiente" o "más" → página siguiente
            n_requested = pagination_state.get("page_size", PAGE_SIZE_DEFAULT)

        # Limitar al máximo
        n_requested = min(n_requested, PAGE_SIZE_MAX)

        # Obtener la página
        start = shown
        end   = min(shown + n_requested, total)
        page  = results[start:end]

        if not page:
            return "Ya has visto todos los resultados.", None

        new_shown = end
        remaining = total - new_shown

        response = self._format_page(page, start, total, question)

        if remaining > 0:
            response += (
                f"\n\n📄 Mostrando {start+1}-{end} de {total}. "
                f"Quedan {remaining} registros.\n"
                f"¿Quieres ver más? Di *\"siguiente\"*, *\"dame {PAGE_SIZE_DEFAULT} más\"* o *\"todos\"*."
            )
            updated_state = {**pagination_state, "shown": new_shown}
            return response, updated_state
        else:
            response += f"\n\n✅ Has visto todos los {total} resultados."
            return response, None

    # ─── MetaGlass: paginación por voz ───────────────────────────────────────

    def summarize_for_metaglass(
        self,
        question: str,
        results: List[Dict[str, Any]],
        sql_query: str,
        threshold: int = METAGLASS_PAGINATION_THRESHOLD,
        page_size: int = METAGLASS_PAGE_SIZE,
    ) -> Tuple[str, Optional[Dict]]:
        """
        Versión MetaGlass del summarize.

        DIFERENCIAS con summarize() web:
          - Umbral mucho más bajo (5 vs 15) — el TTS no puede leer listas largas
          - Si hay > threshold registros → pregunta si quiere ir listando poco a poco
          - La pregunta es en lenguaje natural, sin Markdown
          - page_size más pequeño (3 vs 10) — para que el TTS sea cómodo

        Args:
            question:  Pregunta original del usuario
            results:   Resultados de la BD
            sql_query: SQL ejecutado
            threshold: Umbral configurable (default: METAGLASS_PAGINATION_THRESHOLD)
            page_size: Registros por página (default: METAGLASS_PAGE_SIZE)

        Returns:
            (response_text, pagination_state)
            - response_text: texto SIN Markdown, listo para TTS
            - pagination_state: dict para paginación, o None si no aplica
        """
        n = len(results)

        if n == 0:
            return "No encontré ningún resultado para tu consulta.", None

        if n <= threshold:
            # Pocos resultados → mostrar todos directamente (sin Markdown)
            return self._format_for_voice(results, question), None

        # Muchos resultados → preguntar si quiere listar poco a poco
        display_key = self._find_display_key(results)
        first_items = []
        for row in results[:2]:
            val = row.get(display_key, "") if display_key else ""
            if val:
                first_items.append(str(val).strip())

        if first_items:
            preview = f"Los primeros son: {', '.join(first_items)}."
        else:
            preview = ""

        pagination_state = {
            "full_results": results,
            "sql_query":    sql_query,
            "question":     question,
            "total":        n,
            "shown":        0,
            "page_size":    page_size,
            "client":       "metaglass",
        }

        response = (
            f"Encontré {n} resultados. {preview} "
            f"¿Quieres que te los vaya listando de {page_size} en {page_size}?"
        ).strip()

        return response, pagination_state

    def handle_metaglass_pagination(
        self,
        message: str,
        pagination_state: Dict,
        use_ai: bool = True,
    ) -> Tuple[str, Optional[Dict]]:
        """
        Maneja la respuesta del usuario a la pregunta de paginación MetaGlass.

        Usa IA (Qwen3 LAN) para interpretar la intención si use_ai=True.
        Fallback determinista si la IA no está disponible.

        Args:
            message:          Respuesta del usuario ("sí", "no", "dame todos", etc.)
            pagination_state: Estado de paginación guardado
            use_ai:           Si True, usar IA para interpretar la intención

        Returns:
            (response_text, updated_pagination_state)
        """
        # Detectar intención: sí/no/todos/número
        intent = self._detect_metaglass_intent(message, use_ai)

        if intent == "no":
            return "De acuerdo, no te listo los resultados.", None

        if intent == "todos":
            results  = pagination_state.get("full_results", [])
            shown    = pagination_state.get("shown", 0)
            question = pagination_state.get("question", "")
            remaining = results[shown:]
            return self._format_for_voice(remaining, question), None

        # "sí" o número → dar la siguiente página
        return self.handle_pagination_request(message, pagination_state)

    def _detect_metaglass_intent(self, message: str, use_ai: bool = True) -> str:
        """
        Detecta la intención del usuario para paginación MetaGlass.

        Usa IA (Qwen3 LAN) si está disponible, fallback determinista si no.

        Returns:
            "si"    → quiere ver los resultados poco a poco
            "no"    → no quiere ver los resultados
            "todos" → quiere ver todos de una vez
            "numero:N" → quiere ver N registros
        """
        if use_ai:
            try:
                return self._detect_intent_with_ai(message)
            except Exception as e:
                logger.debug(f"[MetaGlass] IA no disponible para intent: {e} — usando fallback")

        return self._detect_intent_deterministic(message)

    def _detect_intent_with_ai(self, message: str) -> str:
        """
        Usa Qwen3 LAN para interpretar la intención del usuario.
        Solo se llama si Qwen3 está disponible (LAN, nunca internet).
        """
        try:
            from backend.modules.chat.llm_client import get_llm_client
            client = get_llm_client()

            prompt = (
                f"El usuario ha respondido: '{message}'\n"
                f"Clasifica su intención en UNA de estas opciones:\n"
                f"- si: quiere ver los resultados poco a poco\n"
                f"- no: no quiere ver los resultados\n"
                f"- todos: quiere ver todos los resultados de una vez\n"
                f"Responde SOLO con una palabra: si, no, o todos."
            )

            resp = client.complete(prompt, max_tokens=5, temperature=0.0)
            intent = resp.strip().lower()

            if intent in ("si", "sí", "yes"):
                return "si"
            elif intent in ("no", "nope"):
                return "no"
            elif intent in ("todos", "todas", "all"):
                return "todos"
            else:
                # Si la IA devuelve algo inesperado, usar fallback
                logger.debug(f"[MetaGlass] IA devolvió intent inesperado: '{intent}' — fallback")
                return self._detect_intent_deterministic(message)

        except Exception as e:
            logger.debug(f"[MetaGlass] Error en IA intent: {e}")
            raise

    def _detect_intent_deterministic(self, message: str) -> str:
        """
        Detección determinista de intención (sin IA).
        Fallback cuando Qwen3 no está disponible.
        """
        msg_lower = message.lower().strip()

        # "todos" / "todas" / "de una vez"
        if any(w in msg_lower for w in ["todos", "todas", "todo", "de una vez", "completo", "completa"]):
            return "todos"

        # "no" / "no gracias" / "no quiero"
        if any(w in msg_lower for w in ["no", "nope", "para", "stop", "basta", "suficiente"]):
            # Evitar falsos positivos: "no, dame todos" → "todos"
            if any(w in msg_lower for w in ["todos", "todas", "todo"]):
                return "todos"
            return "no"

        # "sí" / "vale" / "adelante" / "venga"
        if any(w in msg_lower for w in [
            "sí", "si", "yes", "vale", "adelante", "venga", "claro",
            "por favor", "ok", "okay", "siguiente", "más", "mas"
        ]):
            return "si"

        # Por defecto: asumir "sí" (el usuario quiere ver los resultados)
        return "si"

    def _format_for_voice(
        self,
        results: List[Dict],
        question: str,
    ) -> str:
        """
        Formatea resultados para TTS (sin Markdown).
        Versión compacta para MetaGlass.
        """
        if not results:
            return "No hay resultados."

        n = len(results)
        display_key = self._find_display_key(results)
        numeric_key = self._find_numeric_key(results)

        if n == 1:
            row = results[0]
            parts = []
            if display_key and row.get(display_key):
                parts.append(str(row[display_key]).strip())
            if numeric_key and row.get(numeric_key) is not None:
                try:
                    val_f = float(row[numeric_key])
                    parts.append(
                        f"{val_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                except (ValueError, TypeError):
                    parts.append(str(row[numeric_key]))
            return f"El resultado es: {', '.join(parts)}." if parts else "Se encontró un registro."

        # Múltiples resultados: listar sin Markdown
        values = []
        for row in results:
            val = row.get(display_key, "") if display_key else ""
            if val:
                values.append(str(val).strip())

        if not values:
            return f"Se encontraron {n} resultados."

        if len(values) <= 3:
            return f"Los {n} resultados son: {', '.join(values)}."
        else:
            return (
                f"Los {n} resultados son: {', '.join(values[:3])}, "
                f"y {n - 3} más."
            )

    def is_pagination_request(self, message: str) -> bool:
        """
        Detecta si el mensaje es una petición de paginación.

        REGLA: Solo es paginación si:
          1. Contiene una frase exacta de PAGINATION_TRIGGERS, O
          2. Contiene una palabra de acción (dame/muestra/ver) + número explícito
             (NO solo "dame artículos más vendidos" — eso es una pregunta de negocio)
        """
        import re
        msg_lower = message.lower().strip()

        # 1. Frases exactas de paginación
        if any(trigger in msg_lower for trigger in PAGINATION_TRIGGERS):
            return True

        # 2. Acción + número dígitos: "dame 20", "muéstrame 5", "ver 10"
        #    IMPORTANTE: el número debe estar presente explícitamente
        has_number = bool(re.search(r'\b\d+\b', msg_lower))
        has_action = any(w in msg_lower for w in PAGINATION_ACTION_WORDS)
        if has_number and has_action:
            return True

        return False

    # ─── Helpers de formato ───────────────────────────────────────────────────

    def _build_summary(
        self,
        results: List[Dict],
        question: str,
        max_lines: int,
    ) -> str:
        """Genera un resumen de los primeros N resultados."""
        display_key = self._find_display_key(results)
        numeric_key = self._find_numeric_key(results)

        lines = [f"**Resumen de los primeros {max_lines} resultados:**\n"]

        for i, row in enumerate(results[:max_lines]):
            parts = []

            # Campo principal (nombre/descripción)
            if display_key:
                val = row.get(display_key, "")
                if val:
                    parts.append(str(val).strip())

            # Campo numérico (total/precio/cantidad)
            if numeric_key:
                val = row.get(numeric_key)
                if val is not None:
                    try:
                        val_f = float(val)
                        parts.append(f"{numeric_key}: {val_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    except (ValueError, TypeError):
                        parts.append(f"{numeric_key}: {val}")

            # Si no hay campos conocidos, usar los primeros 2 campos
            if not parts:
                for k, v in list(row.items())[:2]:
                    if v is not None:
                        parts.append(f"{k}: {v}")

            line = f"{i+1}. {' — '.join(parts)}" if parts else f"{i+1}. (sin datos)"
            lines.append(line)

        return "\n".join(lines)

    def _format_all(
        self,
        results: List[Dict],
        question: str,
        prefix: str = "",
    ) -> str:
        """Formatea todos los resultados para mostrar."""
        if not results:
            return "No hay resultados."

        display_key = self._find_display_key(results)
        numeric_key = self._find_numeric_key(results)
        n = len(results)

        header = prefix or f"**{n} resultado{'s' if n != 1 else ''}:**\n"
        lines  = [header]

        for i, row in enumerate(results):
            parts = []
            if display_key and row.get(display_key):
                parts.append(str(row[display_key]).strip())
            if numeric_key and row.get(numeric_key) is not None:
                try:
                    val_f = float(row[numeric_key])
                    parts.append(f"{val_f:,.2f}€".replace(",", "X").replace(".", ",").replace("X", "."))
                except (ValueError, TypeError):
                    parts.append(str(row[numeric_key]))
            if not parts:
                for k, v in list(row.items())[:3]:
                    if v is not None:
                        parts.append(f"{k}: {v}")
            lines.append(f"{i+1}. {' — '.join(parts)}" if parts else f"{i+1}. -")

        return "\n".join(lines)

    def _format_page(
        self,
        page: List[Dict],
        start_idx: int,
        total: int,
        question: str,
    ) -> str:
        """Formatea una página de resultados."""
        display_key = self._find_display_key(page)
        numeric_key = self._find_numeric_key(page)
        lines = []

        for i, row in enumerate(page):
            idx   = start_idx + i + 1
            parts = []
            if display_key and row.get(display_key):
                parts.append(str(row[display_key]).strip())
            if numeric_key and row.get(numeric_key) is not None:
                try:
                    val_f = float(row[numeric_key])
                    parts.append(f"{val_f:,.2f}€".replace(",", "X").replace(".", ",").replace("X", "."))
                except (ValueError, TypeError):
                    parts.append(str(row[numeric_key]))
            if not parts:
                for k, v in list(row.items())[:3]:
                    if v is not None:
                        parts.append(f"{k}: {v}")
            lines.append(f"{idx}. {' — '.join(parts)}" if parts else f"{idx}. -")

        return "\n".join(lines)

    def _find_display_key(self, results: List[Dict]) -> Optional[str]:
        """Encuentra el campo más adecuado para mostrar como texto principal."""
        if not results:
            return None
        available = {k.upper(): k for k in results[0].keys()}
        for priority in DISPLAY_PRIORITY:
            if priority in available:
                return available[priority]
        # Fallback: primer campo de texto
        for k, v in results[0].items():
            if isinstance(v, str) and v.strip():
                return k
        return list(results[0].keys())[0] if results[0] else None

    def _find_numeric_key(self, results: List[Dict]) -> Optional[str]:
        """Encuentra el campo numérico más relevante."""
        if not results:
            return None
        available = {k.upper(): k for k in results[0].keys()}
        for field in NUMERIC_FIELDS:
            if field in available:
                return available[field]
        # Fallback: primer campo numérico
        for k, v in results[0].items():
            if isinstance(v, (int, float)) and k.upper() not in ("ID", "TIPO", "ESTADO"):
                return k
        return None

    def _detect_requested_count(self, message: str) -> Optional[int]:
        """
        Detecta cuántos registros quiere ver el usuario.
        Returns:
            -1  → todos
            N   → número específico
            None → "siguiente página" (usar page_size por defecto)
        """
        import re
        msg_lower = message.lower().strip()

        # "todos" / "todas"
        if any(w in msg_lower for w in ["todos", "todas", "todo", "completo", "completa"]):
            return -1

        # Número en palabras
        for word, num in PAGINATION_NUMBER_WORDS.items():
            if word in msg_lower:
                return num

        # Número en dígitos: "dame 20", "muéstrame 5"
        match = re.search(r'\b(\d+)\b', msg_lower)
        if match:
            n = int(match.group(1))
            if 1 <= n <= PAGE_SIZE_MAX:
                return n

        # "siguiente", "más" → None (usar page_size por defecto)
        return None


# ─── Singleton ────────────────────────────────────────────────────────────────

_summarizer_instance: Optional[ResponseSummarizer] = None


def get_response_summarizer() -> ResponseSummarizer:
    global _summarizer_instance
    if _summarizer_instance is None:
        _summarizer_instance = ResponseSummarizer()
    return _summarizer_instance
