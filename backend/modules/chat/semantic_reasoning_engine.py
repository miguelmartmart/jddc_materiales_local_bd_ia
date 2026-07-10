"""
semantic_reasoning_engine.py — Motor de Razonamiento Semántico Multi-Fase para DEVIA.

RESPONSABILIDAD:
    Antes de generar SQL, razona sobre la pregunta del usuario para:
    1. Deducir el dominio de negocio (proyectos, obras, certificaciones, retenciones...)
    2. Inferir las tablas y relaciones correctas aunque el usuario use vocabulario coloquial
    3. Enriquecer el contexto con conocimiento de negocio JDDC específico
    4. Generar hints SQL deterministas que guíen al modelo IA

PRINCIPIOS DEVIA:
    - Ultra-resiliente: si falla cualquier fase, devuelve el contexto original sin modificar
    - Sin inventar datos: solo razona sobre lo que existe en el esquema
    - Determinista primero, IA como enriquecimiento opcional
    - Funciona con BD real y simulador (mismo esquema lógico)
    - Modular: cada dominio de negocio es un handler independiente

DOMINIOS DE NEGOCIO JDDC:
    - Proyectos/Obras: PROYECTOS, OBRACAB, PERIOBRA, PRESUPROYE, DOCCAB(CODPROYECTO)
    - Certificaciones: DOCCAB con CODPROYECTO (facturación parcial por período de obra)
    - Retenciones: PROYECTOS.TIPORETENCION, PROYECTOS.PORCRETENCION, PROYECTOS.DIASDEVOLUCIONRETENCION
    - Documentos: DOCCAB (TIPO: 0=presupuesto, 1=pedido_cli, 2=albaran_cli, 3=factura_cli,
                          10=presupuesto_prov, 11=pedido_prov, 12=albaran_prov, 13=factura_prov)
    - Artículos/Stock: ARTICULO, DOCLIN, ESTALMACEN
    - Clientes/Proveedores: CLIENTE, PROVEED, AGENTES

FLUJO:
    [1] Detectar dominio de negocio (determinista, O(1))
    [2] Aplicar handler del dominio → enriquecer contexto con hints SQL
    [3] Opcionalmente: llamada ligera a IA para razonamiento adicional
    [4] Devolver contexto enriquecido + hints para el system prompt

DEVIA: backend/modules/chat/DEVIA.MD
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Tipos de dominio de negocio ─────────────────────────────────────────────

class BusinessDomain:
    PROYECTOS_OBRAS      = "proyectos_obras"       # Proyectos, obras, instalaciones
    CERTIFICACIONES      = "certificaciones"        # Certificaciones de obra (facturación parcial)
    RETENCIONES          = "retenciones"            # Retenciones de garantía, avales
    DOCUMENTOS           = "documentos"             # Facturas, albaranes, pedidos, presupuestos
    ARTICULOS_STOCK      = "articulos_stock"        # Artículos, stock, inventario
    CLIENTES_PROVEEDORES = "clientes_proveedores"   # Clientes, proveedores, agentes
    FINANCIERO           = "financiero"             # Caja, cobros, pagos, tesorería
    GENERAL              = "general"                # Sin dominio específico detectado


@dataclass
class ReasoningResult:
    """Resultado del razonamiento semántico."""
    domain: str = BusinessDomain.GENERAL
    confidence: float = 0.0
    hints: List[str] = field(default_factory=list)          # Hints SQL deterministas
    business_context: str = ""                               # Contexto de negocio para el prompt
    tables_suggested: List[str] = field(default_factory=list)  # Tablas sugeridas
    filters_suggested: List[str] = field(default_factory=list) # Filtros SQL sugeridos
    reasoning_steps: List[str] = field(default_factory=list)   # Pasos de razonamiento (para logs)
    enriched_question: str = ""                              # Pregunta enriquecida con contexto


# ─── Conocimiento de negocio JDDC ────────────────────────────────────────────

JDDC_BUSINESS_KNOWLEDGE = {
    "certificaciones_obra": """
CONOCIMIENTO DE NEGOCIO — CERTIFICACIONES DE OBRA (JDDC):
• Una CERTIFICACIÓN es una facturación parcial de una obra/proyecto.
• Cada obra tiene varias certificaciones (normalmente mensuales).
• En la BD: las certificaciones son documentos DOCCAB con CODPROYECTO no nulo.
• TIPO de documento para certificaciones: TIPO=3 (factura cliente) con CODPROYECTO.
• Relación: PROYECTOS.CODIGO = DOCCAB.CODPROYECTO
• Para listar certificaciones por proyecto:
  SELECT p.NOMBRE, d.NUMERO, d.FECHA, d.IMPORTETOTAL
  FROM PROYECTOS p JOIN DOCCAB d ON d.CODPROYECTO = p.CODIGO
  WHERE d.TIPO = 3
  ORDER BY p.NOMBRE, d.FECHA
""",
    "retenciones": """
CONOCIMIENTO DE NEGOCIO — RETENCIONES Y AVALES (JDDC):
• La RETENCIÓN es un porcentaje del importe de obra que el cliente retiene como garantía.
• Se cobra al finalizar el período de garantía (normalmente 1 año tras fin de obra).
• PROYECTOS.TIPORETENCION: 0=sin retención, 1=aval bancario previo, 2=aval al finalizar, 3=sin aval
• PROYECTOS.PORCRETENCION: porcentaje retenido (ej: 5.0 = 5%)
• PROYECTOS.DIASDEVOLUCIONRETENCION: días hasta devolución de retención
• Tipos de aval:
  - Tipo 1: Aval bancario entregado ANTES de la obra (cubre el período de garantía)
  - Tipo 2: Aval entregado AL FINALIZAR la obra (JDDC cobra retenciones, aval cubre garantía)
  - Tipo 3: SIN aval — el cliente paga al finalizar el período de garantía
""",
    "proyectos_obras": """
CONOCIMIENTO DE NEGOCIO — PROYECTOS Y OBRAS (JDDC):
• PROYECTOS: tabla maestra de proyectos/obras de instalación.
• OBRACAB: cabecera de obra (datos de ejecución, fases, recursos).
• PERIOBRA: períodos de obra (certificaciones por período).
• PRESUPROYE: relación presupuesto → proyecto (un proyecto puede tener varios presupuestos).
• DOCCAB.CODPROYECTO: vincula cualquier documento (factura, albarán, pedido) a un proyecto.
• Para ver documentos de un proyecto: WHERE DOCCAB.CODPROYECTO = 'CODIGO_PROYECTO'
• PROYECTOS.CODIGO es TEXT (no INTEGER) — usar comillas en SQL.
""",
    "documentos_tipo": """
MAPEO DOCCAB.TIPO (verificado con usuario JDDC):
• TIPO=0:  Presupuesto cliente
• TIPO=1:  Pedido cliente
• TIPO=2:  Albarán cliente
• TIPO=3:  Factura cliente
• TIPO=10: Presupuesto proveedor
• TIPO=11: Pedido proveedor
• TIPO=12: Albarán proveedor
• TIPO=13: Factura proveedor
REGLA: TIPO=0 es PRESUPUESTO, NUNCA Albarán.
""",
}


# ─── Patrones de detección de dominio ────────────────────────────────────────

# Cada patrón: (regex, dominio, confianza, keywords_adicionales)
DOMAIN_PATTERNS = [
    # Certificaciones (muy específico — alta prioridad)
    (
        r'\b(certificaci[oó]n|certificaciones|certif[íi]caci[oó]n|certif[íi]caciones|'
        r'facturaci[oó]n parcial|factura parcial|factura de obra|'
        r'periodo de obra|per[íi]odo de obra|liquidaci[oó]n parcial)\b',
        BusinessDomain.CERTIFICACIONES, 0.95,
        ["DOCCAB", "PROYECTOS", "PERIOBRA"]
    ),
    # Retenciones y avales
    (
        r'\b(retenci[oó]n|retenciones|aval|avales|garant[íi]a de obra|'
        r'devoluci[oó]n de retenci[oó]n|periodo de garant[íi]a|'
        r'fin de garant[íi]a|cobro de retenci[oó]n)\b',
        BusinessDomain.RETENCIONES, 0.90,
        ["PROYECTOS", "DOCCAB"]
    ),
    # Proyectos y obras (general)
    (
        r'\b(proyecto|proyectos|obra|obras|instalaci[oó]n|instalaciones|'
        r'contrato de obra|ejecuci[oó]n de obra|obra civil|'
        r'presupuesto de obra|licitaci[oó]n)\b',
        BusinessDomain.PROYECTOS_OBRAS, 0.85,
        ["PROYECTOS", "OBRACAB", "PRESUPROYE", "DOCCAB"]
    ),
    # Documentos financieros
    (
        r'\b(factura|facturas|albar[aá]n|albaranes|pedido|pedidos|'
        r'presupuesto|presupuestos|abono|abonos|contrato|contratos)\b',
        BusinessDomain.DOCUMENTOS, 0.80,
        ["DOCCAB", "DOCLIN"]
    ),
    # Artículos y stock
    (
        r'\b(art[íi]culo|art[íi]culos|producto|productos|stock|inventario|'
        r'almac[eé]n|almacenes|existencias|referencia)\b',
        BusinessDomain.ARTICULOS_STOCK, 0.80,
        ["ARTICULO", "DOCLIN", "ESTALMACEN"]
    ),
    # Clientes y proveedores
    (
        r'\b(cliente|clientes|proveedor|proveedores|agente|agentes|'
        r'comercial|comerciales)\b',
        BusinessDomain.CLIENTES_PROVEEDORES, 0.75,
        ["CLIENTE", "PROVEED", "AGENTES"]
    ),
    # Financiero
    (
        r'\b(caja|cobro|cobros|pago|pagos|tesorería|tesoreria|'
        r'recibo|recibos|vencimiento|vencimientos|liquidez)\b',
        BusinessDomain.FINANCIERO, 0.75,
        ["CAJA", "DOCCAB"]
    ),
]


# ─── SemanticReasoningEngine ──────────────────────────────────────────────────

class SemanticReasoningEngine:
    """
    Motor de razonamiento semántico multi-fase para DEVIA.

    Analiza la pregunta del usuario ANTES de generar SQL para:
    1. Detectar el dominio de negocio
    2. Inferir tablas y relaciones correctas
    3. Enriquecer el contexto con conocimiento JDDC específico
    4. Generar hints SQL deterministas

    Ultra-resiliente: cualquier fallo devuelve el contexto original sin modificar.
    """

    def __init__(self):
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), domain, confidence, tables)
            for pattern, domain, confidence, tables in DOMAIN_PATTERNS
        ]

    def reason(self, question: str, db_context: str = "", is_simulator: bool = False) -> ReasoningResult:
        """
        Razona sobre la pregunta y devuelve un ReasoningResult enriquecido.

        Args:
            question: Pregunta del usuario en lenguaje natural
            db_context: Contexto de BD actual (del SIUO o fallback)
            is_simulator: True si se usa el simulador SQLite

        Returns:
            ReasoningResult con hints, contexto de negocio y tablas sugeridas
        """
        result = ReasoningResult(enriched_question=question)

        try:
            # FASE 1: Detectar dominio de negocio
            domain, confidence, tables = self._detect_domain(question)
            result.domain = domain
            result.confidence = confidence
            result.tables_suggested = tables
            result.reasoning_steps.append(
                f"Dominio detectado: {domain} (confianza={confidence:.0%})"
            )

            # FASE 2: Aplicar handler del dominio
            handler = self._get_domain_handler(domain)
            if handler:
                handler(question, result, is_simulator)
                result.reasoning_steps.append(
                    f"Handler aplicado: {domain} → {len(result.hints)} hints generados"
                )

            # FASE 3: Enriquecer pregunta con contexto de negocio
            if result.business_context:
                result.enriched_question = (
                    f"{question}\n\n"
                    f"[CONTEXTO DE NEGOCIO JDDC]\n{result.business_context}"
                )

            logger.info(
                f"[REASONING] Dominio={domain} conf={confidence:.0%} "
                f"tablas={tables} hints={len(result.hints)}"
            )

        except Exception as e:
            logger.warning(f"[REASONING] Error en razonamiento semántico: {e} — usando contexto original")
            result.domain = BusinessDomain.GENERAL
            result.confidence = 0.0

        return result

    def build_enriched_system_prompt(
        self,
        base_prompt: str,
        result: ReasoningResult,
        is_simulator: bool = False
    ) -> str:
        """
        Construye el system prompt enriquecido con el razonamiento semántico.

        Inserta el conocimiento de negocio y los hints SQL ANTES del prompt base,
        para que el modelo IA los tenga en cuenta al generar SQL.

        Args:
            base_prompt: System prompt original del chat
            result: Resultado del razonamiento semántico
            is_simulator: True si se usa el simulador SQLite

        Returns:
            System prompt enriquecido
        """
        if result.domain == BusinessDomain.GENERAL or result.confidence < 0.5:
            return base_prompt  # Sin enriquecimiento si no hay dominio claro

        enrichment_parts = []

        # Contexto de negocio JDDC
        if result.business_context:
            enrichment_parts.append(result.business_context)

        # Hints SQL deterministas
        if result.hints:
            hints_text = "\n".join(f"  • {h}" for h in result.hints)
            enrichment_parts.append(
                f"\n🎯 HINTS SQL PARA ESTA CONSULTA:\n{hints_text}"
            )

        # Tablas sugeridas
        if result.tables_suggested:
            sim_note = " (disponibles en simulador)" if is_simulator else ""
            enrichment_parts.append(
                f"\n📋 TABLAS RELEVANTES{sim_note}: {', '.join(result.tables_suggested)}"
            )

        # Filtros sugeridos
        if result.filters_suggested:
            filters_text = "\n".join(f"  • {f}" for f in result.filters_suggested)
            enrichment_parts.append(
                f"\n🔍 FILTROS SUGERIDOS:\n{filters_text}"
            )

        if not enrichment_parts:
            return base_prompt

        enrichment = "\n".join(enrichment_parts)
        return f"{enrichment}\n\n{base_prompt}"

    # ─── Detección de dominio ─────────────────────────────────────────────────

    def _detect_domain(self, question: str) -> Tuple[str, float, List[str]]:
        """
        Detecta el dominio de negocio de la pregunta.
        Devuelve (dominio, confianza, tablas_sugeridas).
        """
        best_domain = BusinessDomain.GENERAL
        best_confidence = 0.0
        best_tables: List[str] = []

        for compiled_pattern, domain, confidence, tables in self._compiled_patterns:
            if compiled_pattern.search(question):
                if confidence > best_confidence:
                    best_domain = domain
                    best_confidence = confidence
                    best_tables = tables

        return best_domain, best_confidence, best_tables

    def _get_domain_handler(self, domain: str):
        """Devuelve el handler para el dominio dado."""
        handlers = {
            BusinessDomain.CERTIFICACIONES:      self._handle_certificaciones,
            BusinessDomain.RETENCIONES:          self._handle_retenciones,
            BusinessDomain.PROYECTOS_OBRAS:      self._handle_proyectos_obras,
            BusinessDomain.DOCUMENTOS:           self._handle_documentos,
            BusinessDomain.ARTICULOS_STOCK:      self._handle_articulos_stock,
            BusinessDomain.CLIENTES_PROVEEDORES: self._handle_clientes_proveedores,
            BusinessDomain.FINANCIERO:           self._handle_financiero,
        }
        return handlers.get(domain)

    # ─── Handlers por dominio ─────────────────────────────────────────────────

    def _handle_certificaciones(self, question: str, result: ReasoningResult, is_sim: bool) -> None:
        """
        Handler para consultas sobre certificaciones de obra.

        Una certificación es una factura parcial de una obra/proyecto.
        En la BD: DOCCAB con CODPROYECTO no nulo y TIPO=3 (factura cliente).
        """
        result.business_context = JDDC_BUSINESS_KNOWLEDGE["certificaciones_obra"]
        result.tables_suggested = ["PROYECTOS", "DOCCAB", "DOCLIN"]

        # Detectar si pregunta por un proyecto específico
        q_lower = question.lower()

        # Hint principal: JOIN entre PROYECTOS y DOCCAB
        result.hints.append(
            "Las certificaciones son documentos DOCCAB con CODPROYECTO no nulo y TIPO=3 (factura cliente)"
        )
        result.hints.append(
            "JOIN: PROYECTOS.CODIGO = DOCCAB.CODPROYECTO"
        )

        # Detectar si quiere agrupar por proyecto
        if any(w in q_lower for w in ["cada proyecto", "por proyecto", "cada obra", "por obra"]):
            result.hints.append(
                "Para agrupar por proyecto: GROUP BY PROYECTOS.CODIGO, PROYECTOS.NOMBRE"
            )
            result.filters_suggested.append(
                "WHERE DOCCAB.CODPROYECTO IS NOT NULL AND DOCCAB.TIPO = 3"
            )
            # SQL de ejemplo
            if is_sim:
                result.hints.append(
                    "SQL ejemplo (simulador): SELECT p.NOMBRE, COUNT(d.CODIGO) as NUM_CERT, "
                    "SUM(d.IMPORTETOTAL) as TOTAL FROM PROYECTOS p "
                    "JOIN DOCCAB d ON d.CODPROYECTO = p.CODIGO "
                    "WHERE d.TIPO = 3 GROUP BY p.CODIGO, p.NOMBRE ORDER BY p.NOMBRE"
                )
            else:
                result.hints.append(
                    "SQL ejemplo (Firebird): SELECT FIRST 50 p.NOMBRE, COUNT(d.CODIGO) as NUM_CERT, "
                    "SUM(d.IMPORTETOTAL) as TOTAL FROM PROYECTOS p "
                    "JOIN DOCCAB d ON d.CODPROYECTO = p.CODIGO "
                    "WHERE d.CODPROYECTO IS NOT NULL AND d.TIPO = 3 "
                    "GROUP BY p.CODIGO, p.NOMBRE ORDER BY p.NOMBRE"
                )
        else:
            result.filters_suggested.append(
                "WHERE DOCCAB.CODPROYECTO IS NOT NULL AND DOCCAB.TIPO = 3"
            )

        result.reasoning_steps.append(
            "Certificaciones detectadas → JOIN PROYECTOS+DOCCAB con TIPO=3 y CODPROYECTO no nulo"
        )

    def _handle_retenciones(self, question: str, result: ReasoningResult, is_sim: bool) -> None:
        """
        Handler para consultas sobre retenciones y avales de obra.
        """
        result.business_context = JDDC_BUSINESS_KNOWLEDGE["retenciones"]
        result.tables_suggested = ["PROYECTOS", "DOCCAB"]

        q_lower = question.lower()

        result.hints.append(
            "Retenciones en PROYECTOS: TIPORETENCION (0=sin, 1=aval previo, 2=aval al finalizar, 3=sin aval), "
            "PORCRETENCION (porcentaje), DIASDEVOLUCIONRETENCION (días hasta devolución)"
        )

        if "aval" in q_lower:
            result.hints.append(
                "Tipos de aval: TIPORETENCION=1 (aval previo), TIPORETENCION=2 (aval al finalizar), "
                "TIPORETENCION=3 (sin aval — cliente paga al finalizar garantía)"
            )
            result.filters_suggested.append(
                "WHERE PROYECTOS.TIPORETENCION IN (1, 2, 3)"
            )
        elif "devolucion" in q_lower or "devolución" in q_lower or "cobrar" in q_lower:
            result.hints.append(
                "Para ver retenciones pendientes de cobro: proyectos con TIPORETENCION=3 "
                "y FECHAFIN + DIASDEVOLUCIONRETENCION <= fecha actual"
            )

        result.reasoning_steps.append(
            "Retenciones detectadas → PROYECTOS.TIPORETENCION + PORCRETENCION"
        )

    def _handle_proyectos_obras(self, question: str, result: ReasoningResult, is_sim: bool) -> None:
        """
        Handler para consultas generales sobre proyectos y obras.
        """
        result.business_context = JDDC_BUSINESS_KNOWLEDGE["proyectos_obras"]
        result.tables_suggested = ["PROYECTOS", "DOCCAB", "PRESUPROYE"]

        q_lower = question.lower()

        result.hints.append(
            "PROYECTOS.CODIGO es TEXT (no INTEGER) — usar comillas en filtros: WHERE CODIGO = 'P001'"
        )
        result.hints.append(
            "Para ver documentos de un proyecto: JOIN DOCCAB ON DOCCAB.CODPROYECTO = PROYECTOS.CODIGO"
        )

        if "presupuesto" in q_lower:
            result.hints.append(
                "Presupuestos de proyecto en PRESUPROYE: "
                "JOIN PRESUPROYE ON PRESUPROYE.CODPROYECTO = PROYECTOS.CODIGO"
            )
            result.tables_suggested.append("PRESUPROYE")

        if any(w in q_lower for w in ["factura", "facturado", "facturacion", "facturación"]):
            result.hints.append(
                "Facturación de obra: DOCCAB con CODPROYECTO no nulo y TIPO=3"
            )
            result.filters_suggested.append("WHERE DOCCAB.TIPO = 3 AND DOCCAB.CODPROYECTO IS NOT NULL")

        result.reasoning_steps.append(
            "Proyectos/obras detectados → PROYECTOS + JOIN DOCCAB por CODPROYECTO"
        )

    def _handle_documentos(self, question: str, result: ReasoningResult, is_sim: bool) -> None:
        """
        Handler para consultas sobre documentos (facturas, albaranes, pedidos, presupuestos).
        """
        result.business_context = JDDC_BUSINESS_KNOWLEDGE["documentos_tipo"]
        result.tables_suggested = ["DOCCAB", "DOCLIN"]

        q_lower = question.lower()

        # Detectar tipo de documento
        tipo_map = {
            "factura": ("3", "factura cliente"),
            "facturas": ("3", "factura cliente"),
            "albaran": ("2", "albarán cliente"),
            "albarán": ("2", "albarán cliente"),
            "albaranes": ("2", "albarán cliente"),
            "pedido": ("1", "pedido cliente"),
            "pedidos": ("1", "pedido cliente"),
            "presupuesto": ("0", "presupuesto cliente"),
            "presupuestos": ("0", "presupuesto cliente"),
            "abono": ("3", "abono/factura rectificativa"),
        }

        for keyword, (tipo, label) in tipo_map.items():
            if keyword in q_lower:
                result.filters_suggested.append(f"WHERE DOCCAB.TIPO = {tipo}  -- {label}")
                result.hints.append(f"Tipo de documento detectado: {label} (TIPO={tipo})")
                break

        result.reasoning_steps.append("Documentos detectados → DOCCAB + DOCLIN")

    def _handle_articulos_stock(self, question: str, result: ReasoningResult, is_sim: bool) -> None:
        """Handler para consultas sobre artículos y stock."""
        result.tables_suggested = ["ARTICULO", "DOCLIN", "ESTALMACEN"]
        result.hints.append("ARTICULO.STOCK no existe → usar STOCKARTICULO")
        result.hints.append("Para ventas de artículos: JOIN DOCLIN ON DOCLIN.CODARTICULO = ARTICULO.CODIGO")
        result.reasoning_steps.append("Artículos/stock detectados → ARTICULO + DOCLIN")

    def _handle_clientes_proveedores(self, question: str, result: ReasoningResult, is_sim: bool) -> None:
        """
        Handler para consultas sobre clientes, proveedores y agentes comerciales.

        PRINCIPIO DEVIA — Inferencia genérica:
          Deduce dinámicamente qué tablas son relevantes según el contenido
          semántico de la pregunta, sin hardcodear casos concretos.
          Cada sub-dominio (clientes, proveedores, agentes) puede coexistir.
        """
        q_lower = question.lower()

        # ── Inferencia de sub-dominio: qué entidades menciona la pregunta ──
        menciona_proveedor = any(w in q_lower for w in [
            "proveedor", "proveedores", "suministrador", "suministradores",
        ])
        menciona_agente = any(w in q_lower for w in [
            "agente", "agentes", "comercial", "comerciales",
        ])
        menciona_cliente = any(w in q_lower for w in [
            "cliente", "clientes",
        ])

        # Si no se menciona ninguna entidad específica → asumir clientes (caso más común)
        if not menciona_proveedor and not menciona_agente and not menciona_cliente:
            menciona_cliente = True

        # ── Construir tables_suggested de forma genérica ──
        tables: list = []
        if menciona_proveedor:
            tables.append("PROVEED")
            result.hints.append("Compras a proveedores: DOCCAB con TIPO=13 (factura proveedor)")
        if menciona_agente:
            tables.append("AGENTES")
            result.hints.append("Agentes comerciales: AGENTES.CODIGO = CLIENTE.CODAGENTE = DOCCAB.CODAGENTE")
        if menciona_cliente or not tables:
            tables.append("CLIENTE")
            result.hints.append("Ventas a clientes: DOCCAB con TIPO=3 (factura cliente)")

        # DOCCAB siempre relevante para vincular documentos con clientes/proveedores
        tables.append("DOCCAB")

        # Eliminar duplicados preservando orden
        seen: set = set()
        result.tables_suggested = [t for t in tables if not (t in seen or seen.add(t))]

        result.reasoning_steps.append(
            f"Clientes/proveedores detectados → tablas inferidas: {result.tables_suggested}"
        )

    def _handle_financiero(self, question: str, result: ReasoningResult, is_sim: bool) -> None:
        """Handler para consultas financieras (caja, cobros, pagos)."""
        result.tables_suggested = ["CAJA", "DOCCAB"]
        result.hints.append("Movimientos de caja en tabla CAJA: TIPO=1 cobro, TIPO=2 pago")
        result.reasoning_steps.append("Financiero detectado → CAJA + DOCCAB")


# ─── Singleton ────────────────────────────────────────────────────────────────

_engine_instance: Optional[SemanticReasoningEngine] = None


def get_reasoning_engine() -> SemanticReasoningEngine:
    """
    Devuelve la instancia singleton del motor de razonamiento.
    Thread-safe para uso en FastAPI (single-process).
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SemanticReasoningEngine()
        logger.info("[REASONING] SemanticReasoningEngine inicializado")
    return _engine_instance
