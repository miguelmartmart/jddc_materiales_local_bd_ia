"""
deep_analysis_agent.py — Agente de Análisis Profundo Multi-Fase ÉPICO

Sistema ultra-resiliente que analiza cualquier pregunta con profundidad máxima.

ARQUITECTURA DE FASES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FASE 1 — COMPRENSIÓN ÉPICA (5 subfases)
  1.1 Detección de intención principal
  1.2 Descomposición en sub-preguntas
  1.3 Identificación de tablas candidatas
  1.4 Evaluación de profundidad requerida (auto-detectada)
  1.5 Identificación de posibles problemas de datos

FASE 2 — EXPLORACIÓN TOTAL (6 subfases)
  2.1 Conteo de registros en tablas candidatas
  2.2 Análisis de columnas disponibles
  2.3 Detección de columnas clave (PKs, FKs, fechas, importes)
  2.4 Muestreo de datos reales (primeras filas)
  2.5 Detección de tablas relacionadas (JOINs posibles)
  2.6 Verificación de integridad referencial básica

FASE 3 — INVESTIGACIÓN MULTI-ANGULAR (8 subfases)
  3.1 Consulta principal (responde la pregunta directamente)
  3.2 Verificación de calidad de datos (nulos, vacíos)
  3.3 Detección de duplicados
  3.4 Análisis temporal (distribución por fechas/meses/años)
  3.5 Análisis por cliente/agente/categoría
  3.6 Detección de valores extremos (outliers)
  3.7 Consulta de contexto adicional (totales, promedios)
  3.8 Verificación cruzada con tablas relacionadas

FASE 4 — ANÁLISIS CRÍTICO PROFUNDO (7 subfases)
  4.1 Análisis de anomalías estadísticas
  4.2 Evaluación de calidad de datos
  4.3 Análisis de contexto de negocio
  4.4 Detección de limitaciones del SQL
  4.5 Identificación de patrones ocultos
  4.6 Evaluación de fiabilidad de los resultados
  4.7 Generación de hipótesis explicativas

FASE 5 — SÍNTESIS ÉPICA (5 subfases)
  5.1 Respuesta directa con datos reales
  5.2 Análisis crítico y advertencias
  5.3 Contexto de negocio y perspectiva
  5.4 Sugerencias de mejora y próximos pasos
  5.5 Justificación técnica completa

Principios:
- EPIC por defecto: máxima profundidad en todas las preguntas
- Ultra-resiliente: cada subfase tiene try/except independiente
- Autoconfigurable: detecta tablas, columnas y relaciones automáticamente
- Transparente: log detallado de cada subfase
"""

import logging
import asyncio
import re
import json
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AnalysisDepth(Enum):
    BASIC = "basic"       # 1 SQL, respuesta rápida
    MEDIUM = "medium"     # 3-4 SQLs, análisis moderado
    DEEP = "deep"         # 6-8 SQLs, análisis profundo
    EPIC = "epic"         # 8-12 SQLs, análisis épico completo


@dataclass
class SubPhaseResult:
    """Resultado de una subfase."""
    name: str
    success: bool
    data: Any = None
    error: Optional[str] = None


@dataclass
class PhaseResult:
    """Resultado de una fase principal con sus subfases."""
    phase_id: str
    phase_name: str
    success: bool
    sub_phases: List[SubPhaseResult] = field(default_factory=list)
    data: Any = None
    error: Optional[str] = None


@dataclass
class EpicAnalysisResult:
    """Resultado completo del análisis épico."""
    question: str
    depth: AnalysisDepth = AnalysisDepth.EPIC
    phases: List[PhaseResult] = field(default_factory=list)
    final_answer: str = ""
    sql_queries: List[Dict] = field(default_factory=list)   # [{objetivo, sql, rows, data}]
    warnings: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    business_insights: List[str] = field(default_factory=list)
    data_quality_issues: List[str] = field(default_factory=list)


# ─── Detección automática de profundidad ─────────────────────────────────────

def detect_depth(message: str) -> AnalysisDepth:
    """
    Detecta automáticamente el nivel de profundidad requerido.
    Por defecto EPIC — solo reduce si la pregunta es claramente simple.
    """
    msg = message.lower()

    # Siempre EPIC si hay palabras de análisis profundo
    epic_keywords = [
        "analiza", "análisis", "investiga", "profundidad", "detalle", "completo",
        "exhaustivo", "a fondo", "todo", "tasa", "éxito", "porcentaje", "tendencia",
        "comparativa", "evolución", "histórico", "por qué", "causa", "problema",
        "anomalía", "duplicado", "calidad", "fiabilidad", "perspectiva",
    ]
    if any(k in msg for k in epic_keywords):
        return AnalysisDepth.EPIC

    # DEEP para preguntas con múltiples dimensiones
    deep_keywords = [
        "cuántos", "cuánto", "total", "suma", "promedio", "media",
        "más", "menos", "mejor", "peor", "top", "ranking",
        "clientes", "agentes", "familias", "categorías",
    ]
    if any(k in msg for k in deep_keywords):
        return AnalysisDepth.DEEP

    # MEDIUM para preguntas de listado
    medium_keywords = ["lista", "muestra", "dame", "ver", "mostrar"]
    if any(k in msg for k in medium_keywords):
        return AnalysisDepth.MEDIUM

    # EPIC por defecto — siempre máxima profundidad
    return AnalysisDepth.EPIC


# ─── Configuración por nivel de profundidad ───────────────────────────────────

DEPTH_CONFIG = {
    AnalysisDepth.BASIC:  {"max_sqls": 2,  "explore_tables": 2, "sub_phases": 2},
    AnalysisDepth.MEDIUM: {"max_sqls": 4,  "explore_tables": 4, "sub_phases": 4},
    AnalysisDepth.DEEP:   {"max_sqls": 8,  "explore_tables": 6, "sub_phases": 6},
    AnalysisDepth.EPIC:   {"max_sqls": 12, "explore_tables": 8, "sub_phases": 8},
}


class DeepAnalysisAgent:
    """
    Agente de análisis épico multi-fase para Firebird 2.5.

    Uso:
        agent = DeepAnalysisAgent(orchestrator, execute_sql_func, db_context)
        result = await agent.analyze("¿cuál es la tasa de éxito de presupuestos?")
    """

    def __init__(
        self,
        orchestrator,
        execute_sql: Callable,
        db_context: str,
        sql_normalizer=None,
        sql_corrector=None,
        depth: Optional[AnalysisDepth] = None,  # None = auto-detectar
    ):
        self.orchestrator = orchestrator
        self.execute_sql = execute_sql
        self.db_context = db_context
        self.sql_normalizer = sql_normalizer
        self.sql_corrector = sql_corrector
        self._forced_depth = depth  # si None, se auto-detecta

    # ─────────────────────────────────────────────────────────────────────────
    # PUNTO DE ENTRADA
    # ─────────────────────────────────────────────────────────────────────────

    async def analyze(self, question: str, context: Dict[str, Any] = None) -> str:
        context = context or {}

        # Determinar profundidad
        depth = self._forced_depth or detect_depth(question)
        cfg = DEPTH_CONFIG[depth]

        result = EpicAnalysisResult(question=question, depth=depth)
        logger.info(f"[DEEP AGENT] 🚀 Análisis {depth.value.upper()} iniciado: '{question[:80]}'")
        logger.info(f"[DEEP AGENT] Config: max_sqls={cfg['max_sqls']}, explore={cfg['explore_tables']}")

        # ── FASE 1: COMPRENSIÓN ───────────────────────────────────────────────
        phase1 = await self._phase1_understand(question, result, cfg)
        result.phases.append(phase1)

        # ── FASE 2: EXPLORACIÓN ───────────────────────────────────────────────
        phase2 = await self._phase2_explore(question, phase1.data or {}, result, cfg)
        result.phases.append(phase2)

        # ── FASE 3: INVESTIGACIÓN ─────────────────────────────────────────────
        phase3 = await self._phase3_investigate(question, phase1.data or {}, phase2.data or {}, result, cfg)
        result.phases.append(phase3)

        # ── FASE 4: ANÁLISIS CRÍTICO ──────────────────────────────────────────
        phase4 = await self._phase4_analyze(question, result, cfg)
        result.phases.append(phase4)

        # ── FASE 5: SÍNTESIS ÉPICA ────────────────────────────────────────────
        phase5 = await self._phase5_synthesize(question, result, cfg)
        result.phases.append(phase5)

        final = result.final_answer or self._emergency_fallback(result)
        logger.info(
            f"[DEEP AGENT] ✅ Completado. SQLs={len(result.sql_queries)}, "
            f"warnings={len(result.warnings)}, anomalies={len(result.anomalies)}"
        )
        return final

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 1: COMPRENSIÓN ÉPICA
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase1_understand(self, question: str, result: EpicAnalysisResult, cfg: Dict) -> PhaseResult:
        phase = PhaseResult(phase_id="1", phase_name="Comprensión Épica", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 1: COMPRENSIÓN ÉPICA ═══")

        # 1.1 Detección de intención
        intent_data = await self._sub_detect_intent(question)
        phase.sub_phases.append(SubPhaseResult("1.1 Intención", bool(intent_data), intent_data))

        # 1.2 Descomposición en sub-preguntas
        sub_questions = await self._sub_decompose(question, intent_data)
        phase.sub_phases.append(SubPhaseResult("1.2 Sub-preguntas", bool(sub_questions), sub_questions))

        # 1.3 Tablas candidatas
        tables_hint = await self._sub_identify_tables(question, intent_data)
        phase.sub_phases.append(SubPhaseResult("1.3 Tablas candidatas", bool(tables_hint), tables_hint))

        # 1.4 Profundidad requerida (auto-detectada)
        depth_info = {
            "detected": result.depth.value,
            "reason": self._explain_depth(question, result.depth),
        }
        phase.sub_phases.append(SubPhaseResult("1.4 Profundidad", True, depth_info))

        # 1.5 Posibles problemas de datos
        potential_issues = await self._sub_identify_issues(question, intent_data)
        phase.sub_phases.append(SubPhaseResult("1.5 Posibles problemas", True, potential_issues))

        phase.data = {
            "intent": intent_data,
            "sub_questions": sub_questions,
            "tables_hint": tables_hint,
            "depth": result.depth.value,
            "potential_issues": potential_issues,
            "business_context": intent_data.get("business_context", "") if isinstance(intent_data, dict) else "",
        }
        logger.info(f"[DEEP AGENT] Fase 1 OK: {len(sub_questions)} sub-preguntas, {len(tables_hint)} tablas")
        return phase

    async def _sub_detect_intent(self, question: str) -> Dict:
        try:
            system = (
                "Analiza la intención de esta pregunta sobre una BD Firebird de empresa de climatización. "
                "Responde SOLO JSON:\n"
                '{"intent":"descripción","category":"ventas|clientes|stock|sat|financiero|otro",'
                '"business_context":"contexto relevante","complexity":"simple|medium|complex|epic"}'
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=question, preferred_model_id="jddcia-qwen3-30b"
            )
            return self._parse_json(resp) or {"intent": question, "category": "otro", "complexity": "epic"}
        except Exception as e:
            return {"intent": question, "category": "otro", "complexity": "epic", "error": str(e)}

    async def _sub_decompose(self, question: str, intent: Dict) -> List[str]:
        try:
            system = (
                "Descompón esta pregunta en sub-preguntas investigables para Firebird 2.5. "
                "Responde SOLO con JSON array: [\"pregunta1\", \"pregunta2\", ...]"
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system,
                user_message=f"Pregunta: {question}\nContexto: {intent.get('business_context','')}",
                preferred_model_id="jddcia-qwen3-30b"
            )
            arr = self._parse_json(resp)
            if isinstance(arr, list):
                return arr
            return [question]
        except Exception:
            return [question]

    async def _sub_identify_tables(self, question: str, intent: Dict) -> List[str]:
        """Identifica tablas candidatas basándose en la pregunta y el esquema."""
        tables = []
        msg = question.lower()

        # Reglas deterministas por palabras clave
        if any(k in msg for k in ["presupuesto", "factura", "albaran", "pedido", "documento", "tasa", "éxito"]):
            tables.extend(["DOCCAB", "DOCLIN", "DOCDESTINO"])
        if any(k in msg for k in ["cliente", "clientes"]):
            tables.extend(["CLIENTE", "DOCVAR"])
        if any(k in msg for k in ["artículo", "articulo", "producto", "stock"]):
            tables.extend(["ARTICULO", "DOCLIN"])
        if any(k in msg for k in ["agente", "vendedor", "comercial"]):
            tables.extend(["AGENTE", "AGEGAST"])
        if any(k in msg for k in ["sat", "reparación", "reparacion", "orden de trabajo"]):
            tables.extend(["DOCCAB"])  # TIPO=2
        if any(k in msg for k in ["proveedor"]):
            tables.extend(["PROVEEDOR"])
        if any(k in msg for k in ["familia", "categoría", "categoria"]):
            tables.extend(["FAMILIA"])

        # Siempre incluir DOCCAB si no está (tabla central)
        if not tables:
            tables = ["DOCCAB", "DOCLIN", "CLIENTE", "ARTICULO"]

        # Deduplicar manteniendo orden
        seen = set()
        return [t for t in tables if not (t in seen or seen.add(t))]

    async def _sub_identify_issues(self, question: str, intent: Dict) -> List[str]:
        """Identifica posibles problemas de datos a investigar."""
        issues = []
        msg = question.lower()

        if "presupuesto" in msg:
            issues.append("Un cliente puede tener múltiples presupuestos para la misma instalación")
            issues.append("Presupuestos sin cliente asignado (CODCLIENTE nulo)")
            issues.append("Presupuestos con fecha futura o muy antigua (error de entrada)")
        if "tasa" in msg or "éxito" in msg or "aceptado" in msg:
            issues.append("La tasa puede estar distorsionada por presupuestos duplicados")
            issues.append("Presupuestos informales no registrados en el sistema")
            issues.append("Definición de 'aceptado' puede variar (pedido, albarán, factura)")
        if "cliente" in msg:
            issues.append("Clientes duplicados con diferente CODIGO pero mismo nombre")
            issues.append("Clientes sin actividad reciente (inactivos)")
        if "factura" in msg or "importe" in msg:
            issues.append("Facturas con importe 0 o negativo (abonos)")
            issues.append("Facturas sin cliente asignado")

        return issues

    def _explain_depth(self, question: str, depth: AnalysisDepth) -> str:
        reasons = {
            AnalysisDepth.EPIC: "Pregunta compleja que requiere análisis multi-dimensional",
            AnalysisDepth.DEEP: "Pregunta con múltiples dimensiones de análisis",
            AnalysisDepth.MEDIUM: "Pregunta moderada con contexto adicional útil",
            AnalysisDepth.BASIC: "Pregunta simple y directa",
        }
        return reasons.get(depth, "Análisis épico por defecto")

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 2: EXPLORACIÓN TOTAL
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase2_explore(
        self, question: str, phase1_data: Dict, result: EpicAnalysisResult, cfg: Dict
    ) -> PhaseResult:
        phase = PhaseResult(phase_id="2", phase_name="Exploración Total", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 2: EXPLORACIÓN TOTAL ═══")

        tables = phase1_data.get("tables_hint", ["DOCCAB", "DOCLIN", "CLIENTE"])[:cfg["explore_tables"]]
        exploration = {}

        for table in tables:
            table_info = {}

            # 2.1 Conteo de registros
            try:
                r = self._safe_sql(f"SELECT COUNT(*) AS TOTAL FROM {table}")
                table_info["total"] = r[0].get("TOTAL", 0) if r else 0
                logger.info(f"[DEEP AGENT] {table}: {table_info['total']} registros")
            except Exception as e:
                table_info["total"] = f"ERROR: {e}"

            # 2.2 Columnas disponibles
            try:
                r = self._safe_sql(
                    f"SELECT TRIM(RDB$FIELD_NAME) AS COL, RDB$FIELD_POSITION AS POS "
                    f"FROM RDB$RELATION_FIELDS WHERE TRIM(RDB$RELATION_NAME)='{table}' "
                    f"ORDER BY RDB$FIELD_POSITION"
                )
                table_info["columns"] = [row.get("COL", "") for row in r] if r else []
            except Exception:
                table_info["columns"] = []

            # 2.3 Detección de columnas clave
            cols_upper = [c.upper() for c in table_info.get("columns", [])]
            table_info["has_fecha"] = "FECHA" in cols_upper
            table_info["has_importe"] = any(c in cols_upper for c in ["IMPORTETOTAL", "IMPORTE", "TOTAL"])
            table_info["has_codcliente"] = "CODCLIENTE" in cols_upper
            table_info["has_tipo"] = "TIPO" in cols_upper

            # 2.4 Muestreo de datos (primeras 3 filas)
            if cfg["max_sqls"] >= 8:  # Solo en DEEP/EPIC
                try:
                    cols_sample = ", ".join(table_info["columns"][:6]) if table_info["columns"] else "*"
                    r = self._safe_sql(f"SELECT FIRST 3 {cols_sample} FROM {table}")
                    table_info["sample"] = r[:3] if r else []
                except Exception:
                    table_info["sample"] = []

            # 2.5 Distribución por TIPO si existe
            if table_info.get("has_tipo") and table == "DOCCAB":
                try:
                    r = self._safe_sql(
                        "SELECT TIPO, COUNT(*) AS N FROM DOCCAB GROUP BY TIPO ORDER BY N DESC"
                    )
                    table_info["tipo_distribution"] = r[:10] if r else []
                except Exception:
                    table_info["tipo_distribution"] = []

            # 2.6 Nulos en columnas clave
            if table_info.get("has_codcliente") and cfg["max_sqls"] >= 6:
                try:
                    r = self._safe_sql(
                        f"SELECT COUNT(*) AS NULOS FROM {table} WHERE CODCLIENTE IS NULL"
                    )
                    table_info["null_codcliente"] = r[0].get("NULOS", 0) if r else 0
                except Exception:
                    table_info["null_codcliente"] = "?"

            exploration[table] = table_info

        phase.data = exploration
        phase.sub_phases.append(SubPhaseResult("2.x Exploración tablas", True, exploration))
        logger.info(f"[DEEP AGENT] Fase 2 OK: {len(exploration)} tablas exploradas")
        return phase

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 3: INVESTIGACIÓN MULTI-ANGULAR
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase3_investigate(
        self, question: str, phase1_data: Dict, phase2_data: Dict,
        result: EpicAnalysisResult, cfg: Dict
    ) -> PhaseResult:
        phase = PhaseResult(phase_id="3", phase_name="Investigación Multi-Angular", success=False)
        logger.info("[DEEP AGENT] ═══ FASE 3: INVESTIGACIÓN MULTI-ANGULAR ═══")

        exploration_summary = self._fmt_exploration(phase2_data)
        sub_questions = phase1_data.get("sub_questions", [question])
        potential_issues = phase1_data.get("potential_issues", [])
        n_sqls = cfg["max_sqls"]

        # Construir prompt para generar múltiples SQLs
        system = (
            "Eres un experto en SQL Firebird 2.5. Genera múltiples consultas SQL para investigar "
            "una pregunta desde TODOS los ángulos posibles.\n\n"
            f"ESQUEMA COMPLETO:\n{self.db_context[:5000]}\n\n"
            f"EXPLORACIÓN REAL DE TABLAS:\n{exploration_summary}\n\n"
            "REGLAS CRÍTICAS FIREBIRD 2.5:\n"
            "• FIRST N en lugar de LIMIT/TOP\n"
            "• UPPER(col) LIKE UPPER('%x%') para texto\n"
            "• DOCCAB.TIPO: 0=presupuesto, 13=factura, 11=albaran, 12=pedido, 2=SAT\n"
            "• NO usar ROUND() → CAST(x AS NUMERIC(15,2))\n"
            "• BLOB (DESCRIPCION en DOCCAB/ARTICULO) → NO en GROUP BY\n"
            "• DOCDESTINO vincula documentos origen→destino\n"
            "• Para 'presupuestos aceptados': JOIN DOCDESTINO ON CODDOCUMENTO=DOCCAB.CODIGO\n\n"
            f"Genera EXACTAMENTE {n_sqls} consultas SQL. Cada una precedida por:\n"
            "-- [OBJETIVO: descripción clara]\n\n"
            "ÁNGULOS A CUBRIR (adapta según la pregunta):\n"
            "1. Consulta principal que responde directamente\n"
            "2. Verificación de calidad (nulos, vacíos, inconsistencias)\n"
            "3. Detección de duplicados o registros anómalos\n"
            "4. Distribución temporal (por año/mes)\n"
            "5. Distribución por cliente/agente/categoría\n"
            "6. Valores extremos (máximos, mínimos, outliers)\n"
            "7. Contexto adicional (totales, promedios, medianas)\n"
            "8. Verificación cruzada con tabla relacionada\n"
            "9-12. Análisis adicionales según la complejidad\n\n"
            "Formato OBLIGATORIO:\n"
            "```sql\n-- [OBJETIVO: descripción]\nSELECT ...\n```\n"
        )

        user_msg = (
            f"PREGUNTA: {question}\n\n"
            f"SUB-PREGUNTAS: {sub_questions}\n\n"
            f"POSIBLES PROBLEMAS A INVESTIGAR: {potential_issues}\n\n"
            f"CONTEXTO: {phase1_data.get('business_context', '')}"
        )

        try:
            response, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 3 IA falló: {e}")
            phase.error = str(e)
            return phase

        # Extraer bloques SQL
        sql_blocks = re.findall(r'```sql\s*(.*?)```', response, re.DOTALL | re.IGNORECASE)
        if not sql_blocks:
            sql_blocks = [l.strip() for l in response.split('\n') if l.strip().upper().startswith('SELECT')]

        executed_ok = 0
        for i, sql_raw in enumerate(sql_blocks[:n_sqls]):
            sql = sql_raw.strip()
            if not sql:
                continue

            objetivo_m = re.search(r'--\s*\[OBJETIVO:\s*(.*?)\]', sql)
            objetivo = objetivo_m.group(1).strip() if objetivo_m else f"Consulta {i+1}"

            # Normalizar
            if self.sql_normalizer:
                try:
                    sql, _ = self.sql_normalizer.normalize(sql)
                except Exception:
                    pass

            logger.info(f"[DEEP AGENT] SQL {i+1}/{len(sql_blocks)}: {objetivo[:60]}")

            # Ejecutar con reintentos y auto-corrección
            sql_result, sql_error = await self._execute_with_retry(sql, objetivo)

            entry = {"objetivo": objetivo, "sql": sql, "rows": 0, "data": [], "error": None}
            if sql_result is not None:
                entry["rows"] = len(sql_result)
                entry["data"] = sql_result[:50]
                result.sql_queries.append(entry)
                executed_ok += 1
                logger.info(f"[DEEP AGENT] ✓ SQL {i+1}: {len(sql_result)} filas")
            else:
                entry["error"] = sql_error
                result.sql_queries.append(entry)
                logger.warning(f"[DEEP AGENT] ✗ SQL {i+1} falló: {sql_error}")

            phase.sub_phases.append(SubPhaseResult(
                f"3.{i+1} {objetivo[:40]}", sql_result is not None, entry
            ))

        phase.success = executed_ok > 0
        phase.data = result.sql_queries
        logger.info(f"[DEEP AGENT] Fase 3 OK: {executed_ok}/{len(sql_blocks)} SQLs exitosos")
        return phase

    async def _execute_with_retry(self, sql: str, objetivo: str) -> Tuple[Optional[List], Optional[str]]:
        """Ejecuta SQL con hasta 2 reintentos y auto-corrección."""
        last_error = None
        for attempt in range(2):
            try:
                result = self._safe_sql(sql)
                return result, None
            except Exception as e:
                last_error = str(e)
                if attempt == 0 and self.sql_corrector:
                    # Intentar corrección automática
                    try:
                        fixed = await self._ai_fix_sql(sql, last_error)
                        if fixed and fixed != sql:
                            sql = fixed
                            logger.info(f"[DEEP AGENT] SQL auto-corregido para: {objetivo[:40]}")
                    except Exception:
                        pass
        return None, last_error

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 4: ANÁLISIS CRÍTICO PROFUNDO
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase4_analyze(self, question: str, result: EpicAnalysisResult, cfg: Dict) -> PhaseResult:
        phase = PhaseResult(phase_id="4", phase_name="Análisis Crítico Profundo", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 4: ANÁLISIS CRÍTICO PROFUNDO ═══")

        exploration_data = result.phases[1].data if len(result.phases) > 1 else {}
        investigation_data = result.sql_queries

        if not investigation_data:
            phase.success = False
            phase.error = "Sin datos de investigación"
            return phase

        data_summary = self._fmt_investigation(investigation_data)
        exploration_summary = self._fmt_exploration(exploration_data)

        system = (
            "Eres un analista de datos crítico, experto en negocios de climatización y en Firebird 2.5. "
            "Analiza los datos con MÁXIMA PROFUNDIDAD y PENSAMIENTO CRÍTICO.\n\n"
            "DIMENSIONES DE ANÁLISIS OBLIGATORIAS:\n\n"
            "1. ANOMALÍAS ESTADÍSTICAS:\n"
            "   - Valores extremos (outliers) que distorsionan medias\n"
            "   - Distribuciones inusuales (todo concentrado en un período)\n"
            "   - Tasas imposibles o sospechosas\n\n"
            "2. CALIDAD DE DATOS:\n"
            "   - Campos nulos en columnas críticas\n"
            "   - Duplicados (mismo cliente, misma fecha, mismo importe)\n"
            "   - Fechas incoherentes (futuras, muy antiguas, fin < inicio)\n"
            "   - Importes negativos o cero donde no deberían\n\n"
            "3. CONTEXTO DE NEGOCIO (CLIMATIZACIÓN):\n"
            "   - 1 instalación puede tener N presupuestos (versiones, revisiones)\n"
            "   - Presupuestos ≠ instalaciones únicas\n"
            "   - Tasa de éxito baja puede ser: datos no migrados, presupuestos informales,\n"
            "     cancelaciones no registradas, sector con baja conversión\n"
            "   - SAT (TIPO=2) son órdenes de trabajo, no ventas\n\n"
            "4. LIMITACIONES DEL SQL:\n"
            "   - LEFT JOINs pueden inflar/deflactar conteos\n"
            "   - COUNT(DISTINCT) vs COUNT(*) — diferencia crítica\n"
            "   - Filtros que excluyen datos válidos\n\n"
            "5. PATRONES OCULTOS:\n"
            "   - Estacionalidad (más presupuestos en verano)\n"
            "   - Concentración en pocos clientes\n"
            "   - Tendencias temporales\n\n"
            "6. HIPÓTESIS EXPLICATIVAS:\n"
            "   - Si la tasa es baja, ¿por qué?\n"
            "   - Si hay muchos nulos, ¿migración incompleta?\n\n"
            "Responde SOLO con JSON válido:\n"
            "{\n"
            '  "warnings": ["advertencia crítica 1", ...],\n'
            '  "anomalies": ["anomalía detectada 1", ...],\n'
            '  "data_quality_issues": ["problema de calidad 1", ...],\n'
            '  "business_insights": ["insight de negocio 1", ...],\n'
            '  "sql_limitations": ["limitación SQL 1", ...],\n'
            '  "hidden_patterns": ["patrón oculto 1", ...],\n'
            '  "hypotheses": ["hipótesis 1", ...],\n'
            '  "suggestions": ["sugerencia de análisis adicional 1", ...],\n'
            '  "reliability_score": "alto|medio|bajo",\n'
            '  "reliability_reason": "explicación"\n'
            "}"
        )

        user_msg = (
            f"PREGUNTA: {question}\n\n"
            f"EXPLORACIÓN DE TABLAS:\n{exploration_summary}\n\n"
            f"RESULTADOS DE INVESTIGACIÓN:\n{data_summary}"
        )

        try:
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            analysis = self._parse_json(resp)
            if analysis:
                result.warnings.extend(analysis.get("warnings", []))
                result.anomalies.extend(analysis.get("anomalies", []))
                result.data_quality_issues.extend(analysis.get("data_quality_issues", []))
                result.business_insights.extend(analysis.get("business_insights", []))
                result.suggestions.extend(analysis.get("suggestions", []))
                result.warnings.extend(analysis.get("data_quality_issues", []))

                phase.data = analysis
                phase.sub_phases.extend([
                    SubPhaseResult("4.1 Anomalías", True, analysis.get("anomalies", [])),
                    SubPhaseResult("4.2 Calidad datos", True, analysis.get("data_quality_issues", [])),
                    SubPhaseResult("4.3 Contexto negocio", True, analysis.get("business_insights", [])),
                    SubPhaseResult("4.4 Limitaciones SQL", True, analysis.get("sql_limitations", [])),
                    SubPhaseResult("4.5 Patrones ocultos", True, analysis.get("hidden_patterns", [])),
                    SubPhaseResult("4.6 Hipótesis", True, analysis.get("hypotheses", [])),
                    SubPhaseResult("4.7 Fiabilidad", True, {
                        "score": analysis.get("reliability_score", "?"),
                        "reason": analysis.get("reliability_reason", ""),
                    }),
                ])
                logger.info(
                    f"[DEEP AGENT] Fase 4 OK: {len(result.warnings)} warnings, "
                    f"{len(result.anomalies)} anomalías, fiabilidad={analysis.get('reliability_score','?')}"
                )
            else:
                phase.success = False
                phase.error = "JSON inválido en análisis"
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 4 error: {e}")
            phase.success = False
            phase.error = str(e)

        return phase

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 5: SÍNTESIS ÉPICA
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase5_synthesize(self, question: str, result: EpicAnalysisResult, cfg: Dict) -> PhaseResult:
        phase = PhaseResult(phase_id="5", phase_name="Síntesis Épica", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 5: SÍNTESIS ÉPICA ═══")

        analysis_data = result.phases[3].data if len(result.phases) > 3 else {}
        data_summary = self._fmt_investigation(result.sql_queries)

        # Construir HTML de advertencias
        warnings_html = self._build_warnings_html(result)

        system = (
            "Eres un analista de datos experto y consultor de negocio. "
            "Genera una respuesta ÉPICA, COMPLETA y ULTRA-FIABLE que incluya:\n\n"
            "ESTRUCTURA OBLIGATORIA:\n\n"
            "## 📊 Respuesta Principal\n"
            "[Datos reales en tabla Markdown. Números formateados. Sin inventar.]\n\n"
            "## 🔍 Análisis Crítico\n"
            "[Interpretación profunda. ¿Qué significan estos números? ¿Son fiables?]\n\n"
            "## ⚠️ Advertencias y Objeciones\n"
            "[Lista de advertencias importantes. Problemas de datos. Limitaciones.]\n\n"
            "## 💡 Contexto de Negocio\n"
            "[Perspectiva del sector. Factores externos. Comparativas si aplica.]\n\n"
            "## 🚀 Sugerencias y Próximos Pasos\n"
            "[Qué analizar a continuación. Cómo mejorar los datos. Acciones recomendadas.]\n\n"
            "<details>\n"
            "<summary>🔬 Ver detalles técnicos completos</summary>\n\n"
            "[SQLs ejecutados, tablas consultadas, fiabilidad, limitaciones técnicas]\n\n"
            "</details>\n\n"
            "REGLAS ABSOLUTAS:\n"
            "• NO inventar datos. Solo usar los resultados proporcionados.\n"
            "• Si la tasa de éxito es baja, explicar TODAS las posibles causas.\n"
            "• Para presupuestos: SIEMPRE mencionar que 1 instalación = N presupuestos.\n"
            "• Ser directo, objetivo, sin frases vacías.\n"
            "• Incluir números exactos de los resultados.\n"
        )

        user_msg = (
            f"PREGUNTA: {question}\n\n"
            f"PROFUNDIDAD: {result.depth.value.upper()}\n\n"
            f"DATOS RECOPILADOS ({len(result.sql_queries)} consultas):\n{data_summary}\n\n"
            f"ADVERTENCIAS ({len(result.warnings)}):\n" +
            "\n".join(f"• {w}" for w in result.warnings[:8]) + "\n\n"
            f"ANOMALÍAS ({len(result.anomalies)}):\n" +
            "\n".join(f"• {a}" for a in result.anomalies[:5]) + "\n\n"
            f"INSIGHTS DE NEGOCIO:\n" +
            "\n".join(f"• {i}" for i in result.business_insights[:5]) + "\n\n"
            f"PROBLEMAS DE CALIDAD:\n" +
            "\n".join(f"• {q}" for q in result.data_quality_issues[:5]) + "\n\n"
            f"HIPÓTESIS:\n" +
            "\n".join(f"• {h}" for h in analysis_data.get("hypotheses", [])[:4]) + "\n\n"
            f"LIMITACIONES SQL:\n" +
            "\n".join(f"• {l}" for l in analysis_data.get("sql_limitations", [])[:4]) + "\n\n"
            f"SUGERENCIAS:\n" +
            "\n".join(f"• {s}" for s in result.suggestions[:5]) + "\n\n"
            f"FIABILIDAD: {analysis_data.get('reliability_score','?')} — {analysis_data.get('reliability_reason','')}\n\n"
            f"SQLs EJECUTADOS:\n" +
            "\n".join(f"```sql\n-- {q['objetivo']}\n{q['sql']}\n```" for q in result.sql_queries[:6])
        )

        try:
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            if resp:
                # Inyectar advertencias HTML al inicio
                final = (warnings_html + "\n\n" + resp) if warnings_html else resp
                result.final_answer = final
                phase.data = final
                phase.sub_phases.extend([
                    SubPhaseResult("5.1 Respuesta principal", True, "OK"),
                    SubPhaseResult("5.2 Análisis crítico", True, "OK"),
                    SubPhaseResult("5.3 Advertencias", True, f"{len(result.warnings)} advertencias"),
                    SubPhaseResult("5.4 Contexto negocio", True, "OK"),
                    SubPhaseResult("5.5 Sugerencias", True, f"{len(result.suggestions)} sugerencias"),
                ])
                logger.info("[DEEP AGENT] Fase 5 OK: síntesis épica generada")
            else:
                phase.success = False
                result.final_answer = self._emergency_fallback(result)
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 5 error: {e}")
            phase.success = False
            phase.error = str(e)
            result.final_answer = self._emergency_fallback(result)

        return phase

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _safe_sql(self, sql: str) -> List[Dict]:
        try:
            return self.execute_sql(sql) or []
        except Exception as e:
            raise e

    async def _ai_fix_sql(self, sql: str, error: str) -> str:
        try:
            system = "Corrige este SQL Firebird 2.5. Devuelve SOLO el SQL corregido sin markdown."
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system,
                user_message=f"SQL:\n{sql}\n\nError:\n{error}\n\nEsquema:\n{self.db_context[:1500]}"
            )
            if "```sql" in resp:
                return resp.split("```sql")[1].split("```")[0].strip()
            return resp.strip()
        except Exception:
            return sql

    def _parse_json(self, text: str) -> Optional[Any]:
        if not text:
            return None
        # Intentar extraer JSON del texto
        for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
            m = re.search(pattern, text)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
        return None

    def _fmt_exploration(self, exploration: Dict) -> str:
        if not exploration:
            return "(sin exploración)"
        lines = []
        for table, info in exploration.items():
            if isinstance(info, dict):
                total = info.get("total", "?")
                cols = info.get("columns", [])
                tipo_dist = info.get("tipo_distribution", [])
                null_cli = info.get("null_codcliente", "?")
                lines.append(f"• {table}: {total} registros | {len(cols)} columnas")
                if cols:
                    lines.append(f"  Columnas: {', '.join(cols[:12])}{'...' if len(cols)>12 else ''}")
                if tipo_dist:
                    dist_str = ", ".join(f"TIPO={r.get('TIPO','?')}:{r.get('N','?')}" for r in tipo_dist[:5])
                    lines.append(f"  Distribución TIPO: {dist_str}")
                if null_cli != "?":
                    lines.append(f"  CODCLIENTE nulos: {null_cli}")
        return "\n".join(lines)

    def _fmt_investigation(self, queries: List[Dict]) -> str:
        if not queries:
            return "(sin resultados)"
        lines = []
        for q in queries:
            objetivo = q.get("objetivo", "?")
            rows = q.get("rows", 0)
            error = q.get("error")
            data = q.get("data", [])
            sql = q.get("sql", "")

            if error:
                lines.append(f"\n### ✗ {objetivo}\nError: {error}")
            else:
                lines.append(f"\n### ✓ {objetivo} ({rows} filas)")
                if sql:
                    lines.append(f"SQL: `{sql[:150]}{'...' if len(sql)>150 else ''}`")
                for row in data[:5]:
                    lines.append(f"  → {row}")
                if rows > 5:
                    lines.append(f"  ... y {rows-5} filas más")
        return "\n".join(lines)

    def _build_warnings_html(self, result: EpicAnalysisResult) -> str:
        html_parts = []
        for w in result.warnings[:6]:
            html_parts.append(f'<p style="color:#e67e22;font-weight:bold;">⚠️ {w}</p>')
        for a in result.anomalies[:3]:
            html_parts.append(f'<p style="color:#c0392b;font-weight:bold;">🚨 ANOMALÍA: {a}</p>')
        for q in result.data_quality_issues[:3]:
            html_parts.append(f'<p style="color:#8e44ad;font-weight:bold;">🔍 CALIDAD: {q}</p>')
        return "\n".join(html_parts)

    def _emergency_fallback(self, result: EpicAnalysisResult) -> str:
        """Respuesta de emergencia si todo falla."""
        parts = [f"## Análisis de: {result.question}\n"]
        if result.sql_queries:
            ok = [q for q in result.sql_queries if not q.get("error")]
            parts.append(f"Se ejecutaron {len(result.sql_queries)} consultas ({len(ok)} exitosas).\n")
            for q in ok[:3]:
                parts.append(f"\n**{q['objetivo']}** ({q['rows']} filas)")
                for row in q.get("data", [])[:3]:
                    parts.append(f"- {row}")
        if result.warnings:
            parts.append("\n### ⚠️ Advertencias\n" + "\n".join(f"- {w}" for w in result.warnings[:5]))
        if result.anomalies:
            parts.append("\n### 🚨 Anomalías\n" + "\n".join(f"- {a}" for a in result.anomalies[:3]))
        if result.suggestions:
            parts.append("\n### 💡 Sugerencias\n" + "\n".join(f"- {s}" for s in result.suggestions[:3]))
        if not result.sql_queries:
            parts.append("No se pudieron obtener datos. Verifica la conexión a la base de datos.")
        return "\n".join(parts)
