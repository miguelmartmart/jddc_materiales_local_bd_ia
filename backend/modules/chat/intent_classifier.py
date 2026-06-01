"""
intent_classifier.py — Clasificador de intenciones por IA (genérico, sin keywords hardcodeadas).

RESPONSABILIDAD:
    Determina en UNA sola llamada ligera al modelo IA local qué tipo de intención
    tiene el mensaje del usuario, considerando el historial de conversación.

FASES DE INTERPRETACIÓN:
    FASE 1 — Clasificación de intención (esta clase)
        → El modelo IA analiza el mensaje + historial y devuelve un JSON con:
          - intent: CONVERSATIONAL | DB_QUERY | CLARIFICATION | DEEP_ANALYSIS | IMAGE_GEN | COMMAND
          - confidence: 0.0-1.0
          - reasoning: breve explicación (para logs)
          - needs_history: bool (si la respuesta depende del historial)

    FASE 2 — Acción según intención (en service.py)
        → CONVERSATIONAL  → _chat_no_db() directo
        → DB_QUERY        → generar SQL + ejecutar + interpretar
        → CLARIFICATION   → justificación profunda desde historial (sin nueva SQL)
        → DEEP_ANALYSIS   → DeepAnalysisAgent
        → IMAGE_GEN       → generación de imagen
        → COMMAND         → comando especial (/deep, DEBUG_TABLES, etc.)

    FASE 3 — Respuesta de calidad (en service.py)
        → Interpretación con lenguaje de negocio, sin SQL visible, con justificación

VENTAJAS SOBRE KEYWORDS:
    - Funciona con cualquier idioma, sinónimo, paráfrasis o expresión coloquial
    - "¿Me puedes decir cuánto vendimos?" → DB_QUERY (sin keyword "factura")
    - "No me queda claro" → CLARIFICATION (sin keyword "justifica")
    - "Hazme un resumen completo" → DEEP_ANALYSIS (sin keyword "analiza en profundidad")
    - "Dibuja un logo" → IMAGE_GEN (sin keyword "generar imagen")

FALLBACK DETERMINISTA:
    Si la IA falla (timeout, error de red), se usa un clasificador determinista
    basado en patrones semánticos amplios (no solo keywords exactas).

CARGADO EN: backend/modules/chat/service.py
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


# ─── Tipos de intención ───────────────────────────────────────────────────────

class IntentType:
    CONVERSATIONAL = "CONVERSATIONAL"   # Saludo, pregunta general, charla
    DB_QUERY       = "DB_QUERY"         # Consulta de datos de la empresa
    CLARIFICATION  = "CLARIFICATION"    # Pide más detalle sobre respuesta anterior
    DEEP_ANALYSIS  = "DEEP_ANALYSIS"    # Análisis profundo multi-fase
    IMAGE_GEN      = "IMAGE_GEN"        # Generación de imagen
    COMMAND        = "COMMAND"          # Comando especial (/deep, DEBUG_*, etc.)
    UNKNOWN        = "UNKNOWN"          # No clasificado → tratar como DB_QUERY por seguridad


@dataclass
class IntentResult:
    intent: str = IntentType.UNKNOWN
    confidence: float = 0.5
    reasoning: str = ""
    needs_history: bool = False
    raw_response: str = ""

    def is_db_related(self) -> bool:
        return self.intent in (IntentType.DB_QUERY, IntentType.DEEP_ANALYSIS, IntentType.UNKNOWN)

    def is_clarification(self) -> bool:
        return self.intent == IntentType.CLARIFICATION

    def is_conversational(self) -> bool:
        return self.intent == IntentType.CONVERSATIONAL

    def is_deep_analysis(self) -> bool:
        return self.intent == IntentType.DEEP_ANALYSIS

    def is_image_gen(self) -> bool:
        return self.intent == IntentType.IMAGE_GEN

    def is_command(self) -> bool:
        return self.intent == IntentType.COMMAND


# ─── Clasificador principal ───────────────────────────────────────────────────

class IntentClassifier:
    """
    Clasificador de intenciones por IA.

    Usa el modelo IA local (Qwen3 30B LAN) para clasificar la intención
    del usuario en UNA sola llamada ligera (system prompt mínimo, respuesta JSON).

    Si la IA falla, usa el clasificador determinista de fallback.
    """

    # System prompt ultra-compacto para minimizar tokens y latencia
    _SYSTEM_PROMPT = """Eres un clasificador de intenciones para un asistente de empresa.
Analiza el mensaje del usuario y el historial reciente. Responde SOLO con JSON válido.

TIPOS DE INTENCIÓN:
- CONVERSATIONAL: saludo, despedida, agradecimiento, pregunta general no relacionada con datos de empresa, charla
- DB_QUERY: consulta de datos de la empresa (ventas, facturas, clientes, artículos, stock, presupuestos, pedidos, cobros, pagos, proveedores, agentes, estadísticas, informes, comparativas, tendencias, etc.)
- CLARIFICATION: el usuario pide más detalle, explicación, justificación o verificación sobre la RESPUESTA ANTERIOR del asistente (no sobre datos nuevos)
- DEEP_ANALYSIS: análisis exhaustivo, investigación profunda, estudio completo de datos desde cero
- IMAGE_GEN: el usuario pide crear, dibujar, generar o diseñar una imagen
- COMMAND: comando especial que empieza por / o DEBUG_

REGLAS:
- Si hay duda entre DB_QUERY y CLARIFICATION: si el usuario hace referencia a "lo que dijiste", "ese dato", "eso que me diste", "el resultado anterior" → CLARIFICATION. Si pide datos nuevos → DB_QUERY.
- Si hay duda entre CONVERSATIONAL y DB_QUERY: si menciona cualquier concepto de negocio (aunque sea vagamente) → DB_QUERY.
- UNKNOWN no existe: siempre elige el tipo más probable.

FORMATO DE RESPUESTA (JSON estricto, sin texto adicional):
{"intent":"DB_QUERY","confidence":0.95,"reasoning":"El usuario pregunta por ventas","needs_history":false}"""

    def __init__(self, orchestrator=None):
        """
        Args:
            orchestrator: ModelFallbackOrchestrator para llamadas a la IA.
                         Si es None, solo usa el clasificador determinista.
        """
        self.orchestrator = orchestrator

    async def classify(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> IntentResult:
        """
        Clasifica la intención del mensaje usando IA + fallback determinista.

        Args:
            message: Mensaje del usuario
            conversation_history: Historial reciente de la conversación

        Returns:
            IntentResult con el tipo de intención y metadatos
        """
        # 1. Detección rápida de comandos (sin llamar a IA)
        if self._is_command(message):
            return IntentResult(
                intent=IntentType.COMMAND,
                confidence=1.0,
                reasoning="Comando especial detectado",
            )

        # 2. Construir contexto de historial para la IA
        history_summary = self._build_history_summary(conversation_history)

        # 3. Llamada a IA para clasificación
        if self.orchestrator:
            try:
                result = await self._classify_with_ai(message, history_summary)
                if result:
                    logger.info(
                        f"[INTENT] IA → {result.intent} "
                        f"(conf={result.confidence:.2f}) | {result.reasoning}"
                    )
                    return result
            except Exception as e:
                logger.warning(f"[INTENT] IA falló ({e}), usando fallback determinista")

        # 4. Fallback determinista
        result = self._classify_deterministic(message, conversation_history)
        logger.info(
            f"[INTENT] Fallback → {result.intent} "
            f"(conf={result.confidence:.2f}) | {result.reasoning}"
        )
        return result

    async def _classify_with_ai(
        self, message: str, history_summary: str
    ) -> Optional[IntentResult]:
        """Llama al modelo IA y parsea la respuesta JSON."""
        user_message = f"HISTORIAL RECIENTE:\n{history_summary}\n\nMENSAJE ACTUAL: {message}"

        response, _ = await self.orchestrator.execute_with_fallback(
            system_prompt=self._SYSTEM_PROMPT,
            user_message=user_message,
            preferred_model_id="jddcia-qwen3-30b",
        )

        if not response:
            return None

        # Parsear JSON de la respuesta
        return self._parse_ai_response(response.strip())

    def _parse_ai_response(self, raw: str) -> Optional[IntentResult]:
        """Parsea la respuesta JSON del clasificador IA."""
        # Extraer JSON aunque haya texto extra
        json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if not json_match:
            logger.warning(f"[INTENT] No se encontró JSON en respuesta IA: {raw[:100]}")
            return None

        try:
            data = json.loads(json_match.group())
            intent = data.get("intent", IntentType.UNKNOWN).upper()

            # Validar que el intent es uno de los tipos conocidos
            valid_intents = {
                IntentType.CONVERSATIONAL, IntentType.DB_QUERY,
                IntentType.CLARIFICATION, IntentType.DEEP_ANALYSIS,
                IntentType.IMAGE_GEN, IntentType.COMMAND, IntentType.UNKNOWN,
            }
            if intent not in valid_intents:
                intent = IntentType.UNKNOWN

            return IntentResult(
                intent=intent,
                confidence=float(data.get("confidence", 0.7)),
                reasoning=str(data.get("reasoning", ""))[:200],
                needs_history=bool(data.get("needs_history", False)),
                raw_response=raw,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"[INTENT] Error parseando JSON IA: {e} | raw={raw[:100]}")
            return None

    def _classify_deterministic(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> IntentResult:
        """
        Clasificador determinista de fallback.

        Usa patrones semánticos amplios (no solo keywords exactas) para
        cubrir el máximo de casos posibles sin IA.
        """
        msg = message.lower().strip()
        words = set(msg.split())
        has_history = bool(conversation_history)

        # ── CONVERSACIONAL obvio ──────────────────────────────────────────────
        # Solo para mensajes muy cortos o saludos/despedidas inequívocos
        conversational_patterns = [
            r'^(hola|hey|buenas?|buenos?\s+d[ií]as?|buenas?\s+tardes?|buenas?\s+noches?)[\s!.,]*$',
            r'^(gracias|muchas\s+gracias|de\s+nada|ok|vale|perfecto|entendido|genial|bien)[\s!.,]*$',
            r'^(adi[oó]s|hasta\s+luego|hasta\s+pronto|bye|chao)[\s!.,]*$',
            r'^(s[ií]|no|claro|por\s+supuesto)[\s!.,]*$',
            r'^(c[oó]mo\s+est[aá]s|qu[eé]\s+tal|qu[eé]\s+eres|qui[eé]n\s+eres)[\s?]*$',
            r'^(qu[eé]\s+puedes\s+hacer|ayuda|help)[\s?]*$',
        ]
        for pattern in conversational_patterns:
            if re.match(pattern, msg):
                return IntentResult(
                    intent=IntentType.CONVERSATIONAL,
                    confidence=0.95,
                    reasoning="Patrón conversacional obvio",
                )

        # ── GENERACIÓN DE IMAGEN ──────────────────────────────────────────────
        image_patterns = [
            r'\b(dibuja|crea|genera|diseña|hazme|pinta|ilustra)\b.*(imagen|foto|dibujo|logo|icono|ilustraci[oó]n)',
            r'\b(imagen|foto|dibujo|logo)\b.*(de|con|para|sobre)',
            r'\bgenera\s+una\s+(imagen|foto)',
        ]
        for pattern in image_patterns:
            if re.search(pattern, msg):
                return IntentResult(
                    intent=IntentType.IMAGE_GEN,
                    confidence=0.9,
                    reasoning="Petición de generación de imagen",
                )

        # ── ACLARACIÓN/JUSTIFICACIÓN (requiere historial) ─────────────────────
        # Detecta cuando el usuario hace referencia a la respuesta anterior
        if has_history:
            clarification_patterns = [
                # Referencias directas a la respuesta anterior
                r'\b(eso|ese\s+dato|ese\s+resultado|esa\s+cifra|lo\s+que\s+(dijiste|me\s+diste|calculaste|obtuviste))\b',
                # Peticiones de explicación/verificación
                r'\b(por\s+qu[eé]|c[oó]mo\s+(lo|llegaste|calculaste|obtuviste|sabes))\b',
                r'\b(no\s+(entiendo|me\s+queda\s+claro|lo\s+veo\s+claro))\b',
                r'\b(justifica|verifica|comprueba|confirma|demuestra)\b',
                r'\b(es\s+(correcto|fiable|exacto|seguro)|est[aá]s\s+seguro)\b',
                r'\b(m[aá]s\s+detalle|en\s+detalle|con\s+m[aá]s\s+detalle|ampli[ao]|profundiza)\b',
                r'\b(c[oó]mo\s+(verifico|compruebo|lo\s+veo))\b',
                r'\b(qu[eé]\s+(significa|quiere\s+decir|incluye|excluye))\b',
                r'\b(cu[eé]ntame\s+m[aá]s|dime\s+m[aá]s|explica(me)?)\b',
            ]
            for pattern in clarification_patterns:
                if re.search(pattern, msg):
                    return IntentResult(
                        intent=IntentType.CLARIFICATION,
                        confidence=0.85,
                        reasoning="Petición de aclaración sobre respuesta anterior",
                        needs_history=True,
                    )

        # ── ANÁLISIS PROFUNDO ─────────────────────────────────────────────────
        deep_patterns = [
            r'\b(an[aá]lisis\s+(profundo|completo|exhaustivo|detallado))\b',
            r'\b(analiza\s+(en\s+profundidad|todo|exhaustivamente|a\s+fondo))\b',
            r'\b(investiga(r)?|estudio\s+completo|informe\s+completo)\b',
            r'\b(profundamente|a\s+fondo|con\s+todo\s+el\s+detalle)\b',
            r'^/deep\b',
            r'^/an[aá]lisis\b',
        ]
        for pattern in deep_patterns:
            if re.search(pattern, msg):
                return IntentResult(
                    intent=IntentType.DEEP_ANALYSIS,
                    confidence=0.88,
                    reasoning="Petición de análisis profundo",
                )

        # ── CONSULTA DE BD (semántica amplia) ────────────────────────────────
        # Patrones semánticos que cubren muchas formas de pedir datos
        db_semantic_patterns = [
            # Verbos de consulta (cualquier objeto)
            r'\b(dame|mu[eé]strame|lista|listado|busca|encuentra|dime|cu[eé]ntame|qu[eé]\s+hay)\b',
            r'\b(cu[aá]ntos?|cu[aá]ntas?|cu[aá]nto|total|suma|promedio|media|m[aá]ximo|m[ií]nimo)\b',
            r'\b(top|ranking|mejores?|peores?|m[aá]s\s+vendidos?|menos\s+vendidos?)\b',
            r'\b(evoluci[oó]n|tendencia|comparativa|hist[oó]rico|estad[ií]stica|informe|resumen)\b',
            # Conceptos de negocio (amplio)
            r'\b(factura|presupuesto|albar[aá]n|pedido|abono|contrato|recibo|cobro|pago)\b',
            r'\b(cliente|proveedor|agente|comercial|trabajador|empleado|t[eé]cnico)\b',
            r'\b(art[ií]culo|producto|familia|referencia|stock|inventario|almac[eé]n)\b',
            r'\b(venta|compra|facturaci[oó]n|ingreso|gasto|beneficio|margen)\b',
            r'\b(instalaci[oó]n|mantenimiento|sat|obra|proyecto|presupuestado)\b',
            r'\b(importe|precio|coste|costo|valor|euros?|eur)\b',
            r'\b(mes|trimestre|a[nñ]o|semana|fecha|per[ií]odo|rango)\b',
            r'\b(split|aire\s+acondicionado|climatizaci[oó]n|refrigerante|gas)\b',
        ]
        for pattern in db_semantic_patterns:
            if re.search(pattern, msg):
                return IntentResult(
                    intent=IntentType.DB_QUERY,
                    confidence=0.82,
                    reasoning="Patrón semántico de consulta de datos",
                )

        # ── DEFAULT: si hay BD disponible y el mensaje no es obvio → DB_QUERY ─
        # Es mejor intentar una consulta SQL y fallar graciosamente que
        # ignorar una petición legítima de datos.
        # Umbral reducido a >2 palabras para capturar frases cortas como
        # "artículos más caros", "top clientes", "ventas enero", etc.
        if len(msg.split()) > 2:
            return IntentResult(
                intent=IntentType.DB_QUERY,
                confidence=0.55,
                reasoning="Mensaje no clasificado → intentar consulta BD por defecto",
            )

        # Mensaje muy corto (1-2 palabras) y no clasificado → conversacional
        return IntentResult(
            intent=IntentType.CONVERSATIONAL,
            confidence=0.6,
            reasoning="Mensaje corto no clasificado → conversacional",
        )

    def _is_command(self, message: str) -> bool:
        """Detecta comandos especiales sin llamar a IA."""
        msg = message.strip()
        return (
            msg.startswith("/")
            or msg.startswith("DEBUG_")
            or msg == "DEBUG_TABLES"
        )

    def _build_history_summary(
        self, conversation_history: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Construye un resumen compacto del historial para el clasificador."""
        if not conversation_history:
            return "(sin historial previo)"

        recent = conversation_history[-4:]  # Últimos 4 mensajes
        lines = []
        for m in recent:
            role = m.get("role", "user")
            content = m.get("content", "")[:150]  # Truncar para minimizar tokens
            if role == "user":
                lines.append(f"Usuario: {content}")
            elif role == "assistant":
                lines.append(f"Asistente: {content}")

        return "\n".join(lines) if lines else "(sin historial previo)"
