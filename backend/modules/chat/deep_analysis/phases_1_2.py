"""
phases_1_2.py — Fases 0, 1 y 2 del DeepAnalysisAgent.

  Fase 0: Presupuesto de tokens (ajuste dinámico de max_sqls/explore_tables)
  Fase 1: Comprensión épica (intención, sub-preguntas, tablas, profundidad, problemas)
  Fase 2: Exploración total (conteo, columnas, muestreo, distribución TIPO, nulos)
           + expansión dinámica de tablas si la IA lo solicita

La exploración real de tablas (_explore_table, _ask_for_extra_tables) está en:
  → phase2_explore.py (Phase2ExploreMixin)
"""

import logging
from typing import Dict, List

from backend.modules.chat.deep_analysis.models import (
    AnalysisDepth, EpicAnalysisResult, PhaseResult, SubPhaseResult,
    MAX_SQLS_ABSOLUTE,
)
from backend.modules.chat.deep_analysis.phase2_explore import Phase2ExploreMixin

logger = logging.getLogger(__name__)

try:
    from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
except ImportError:
    get_knowledge_store = None  # type: ignore


class Phases12Mixin(Phase2ExploreMixin):
    """
    Mixin con las fases 0, 1 y 2 del agente.
    Hereda Phase2ExploreMixin para _explore_table y _ask_for_extra_tables.
    Requiere: self.orchestrator, self.db_context, self.budget (TokenBudget),
              self._safe_sql(), self._parse_json(), self._fmt_exploration(),
              self._fmt_conversation_history()
    """

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 0: PRESUPUESTO DE TOKENS
    # ─────────────────────────────────────────────────────────────────────────

    def _phase0_budget(
        self, cfg: Dict, question: str, conversation_history: List[Dict]
    ) -> Dict:
        """Ajusta max_sqls y explore_tables según el presupuesto de tokens disponible."""
        history_text = self._fmt_conversation_history(conversation_history)
        fixed_tokens = (
            self.budget.count(self.db_context) +
            self.budget.count(history_text) +
            self.budget.count(question) +
            500  # overhead de prompts del sistema
        )
        available_for_data = self.budget.available - fixed_tokens

        logger.info(
            f"[TOKEN BUDGET] Tokens fijos: {fixed_tokens} | "
            f"Disponible para datos: {available_for_data}"
        )

        tokens_per_sql   = 800
        tokens_per_table = 400

        max_sqls_by_budget = max(2, int(available_for_data * 0.6 / tokens_per_sql))
        max_sqls_by_budget = min(max_sqls_by_budget, MAX_SQLS_ABSOLUTE)
        cfg["max_sqls"] = min(cfg["max_sqls"], max_sqls_by_budget)

        max_tables_by_budget = max(2, int(available_for_data * 0.3 / tokens_per_table))
        cfg["explore_tables"] = min(cfg["explore_tables"], max_tables_by_budget)

        logger.info(
            f"[TOKEN BUDGET] Config ajustada: max_sqls={cfg['max_sqls']}, "
            f"explore_tables={cfg['explore_tables']}"
        )
        return cfg

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 1: COMPRENSIÓN ÉPICA
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase1_understand(
        self, question: str, result: EpicAnalysisResult,
        cfg: Dict, conversation_history: List[Dict]
    ) -> PhaseResult:
        phase = PhaseResult(phase_id="1", phase_name="Comprensión Épica", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 1: COMPRENSIÓN ÉPICA ═══")

        history_text = self._fmt_conversation_history(conversation_history)

        intent_data = await self._sub_detect_intent(question, history_text)
        phase.sub_phases.append(SubPhaseResult("1.1 Intención", bool(intent_data), intent_data))

        sub_questions = await self._sub_decompose(question, intent_data, history_text)
        phase.sub_phases.append(SubPhaseResult("1.2 Sub-preguntas", bool(sub_questions), sub_questions))

        tables_hint = await self._sub_identify_tables(question, intent_data)
        phase.sub_phases.append(SubPhaseResult("1.3 Tablas candidatas", bool(tables_hint), tables_hint))

        depth_info = {
            "detected": result.depth.value,
            "reason": self._explain_depth(question, result.depth),
        }
        phase.sub_phases.append(SubPhaseResult("1.4 Profundidad", True, depth_info))

        potential_issues = self._sub_identify_issues(question)
        phase.sub_phases.append(SubPhaseResult("1.5 Posibles problemas", True, potential_issues))

        phase.data = {
            "intent": intent_data,
            "sub_questions": sub_questions,
            "tables_hint": tables_hint,
            "depth": result.depth.value,
            "potential_issues": potential_issues,
            "business_context": intent_data.get("business_context", "") if isinstance(intent_data, dict) else "",
            "conversation_context": history_text[:500] if history_text else "",
        }
        logger.info(f"[DEEP AGENT] Fase 1 OK: {len(sub_questions)} sub-preguntas, {len(tables_hint)} tablas")
        return phase

    async def _sub_detect_intent(self, question: str, history_text: str) -> Dict:
        try:
            from datetime import datetime
            fecha_actual = datetime.now().strftime("%d/%m/%Y")
            anio_actual = datetime.now().year
            history_section = f"\nHISTORIAL PREVIO:\n{history_text}\n" if history_text else ""
            system = (
                f"Analiza la intención de esta pregunta sobre una BD Firebird de empresa de climatización. "
                f"HOY ES {fecha_actual} (año {anio_actual}). "
                "Considera el historial de conversación para entender el contexto acumulado. "
                "Responde SOLO JSON:\n"
                '{"intent":"descripción","category":"ventas|clientes|stock|sat|financiero|otro",'
                '"business_context":"contexto relevante","complexity":"simple|medium|complex|epic",'
                '"references_previous":"true|false","previous_context":"qué se preguntó antes si aplica"}'
            )
            user_msg = self.budget.truncate_to_fit(
                f"{history_section}\nPREGUNTA ACTUAL: {question}", system
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            return self._parse_json(resp) or {"intent": question, "category": "otro", "complexity": "epic"}
        except Exception as e:
            return {"intent": question, "category": "otro", "complexity": "epic", "error": str(e)}

    async def _sub_decompose(self, question: str, intent: Dict, history_text: str) -> List[str]:
        try:
            history_section = f"HISTORIAL: {history_text[:300]}\n" if history_text else ""
            system = (
                "Descompón esta pregunta en sub-preguntas investigables para Firebird 2.5. "
                "Usa el historial para entender referencias implícitas. "
                "Responde SOLO con JSON array: [\"pregunta1\", \"pregunta2\", ...]"
            )
            user_msg = self.budget.truncate_to_fit(
                f"{history_section}Pregunta: {question}\n"
                f"Contexto: {intent.get('business_context','')}\n"
                f"Referencia previa: {intent.get('previous_context','')}",
                system
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            arr = self._parse_json(resp)
            return arr if isinstance(arr, list) else [question]
        except Exception:
            return [question]

    async def _sub_identify_tables(self, question: str, intent: Dict) -> List[str]:
        """Identifica tablas candidatas (determinista + KnowledgeStore)."""
        tables = []
        msg = question.lower()

        if any(k in msg for k in ["presupuesto", "factura", "albaran", "pedido", "documento", "tasa", "éxito"]):
            tables.extend(["DOCCAB", "DOCLIN", "DOCDESTINO"])
        if any(k in msg for k in ["cliente", "clientes"]):
            tables.extend(["CLIENTE", "DOCVAR"])
        if any(k in msg for k in ["artículo", "articulo", "producto", "stock"]):
            tables.extend(["ARTICULO", "DOCLIN"])
        if any(k in msg for k in ["agente", "vendedor", "comercial"]):
            tables.extend(["AGENTE", "AGEGAST"])
        if any(k in msg for k in ["sat", "reparación", "reparacion", "orden de trabajo"]):
            tables.extend(["DOCCAB"])
        if any(k in msg for k in ["proveedor"]):
            tables.extend(["PROVEEDOR"])
        if any(k in msg for k in ["familia", "categoría", "categoria"]):
            tables.extend(["FAMILIA"])
        if any(k in msg for k in ["instalación", "instalacion", "obra", "codigoobra"]):
            tables.extend(["DOCCAB", "DOCDESTINO"])

        if not tables:
            tables = ["DOCCAB", "DOCLIN", "CLIENTE", "ARTICULO"]

        # Enriquecer con KnowledgeStore (tablas con >100 registros y TIPO/FECHA)
        try:
            if get_knowledge_store is not None:
                store = get_knowledge_store()
                index = store.get_index()
                known_tables = index.get("tables", {})
                for tname, tinfo in known_tables.items():
                    rc = tinfo.get("record_count", 0)
                    if isinstance(rc, int) and rc > 100 and tname not in tables:
                        if tinfo.get("has_tipo") or tinfo.get("has_fecha"):
                            tables.append(tname)
        except Exception as e:
            logger.debug(f"[DEEP AGENT] KnowledgeStore no disponible en Fase 1: {e}")

        seen: set = set()
        return [t for t in tables if not (t in seen or seen.add(t))]

    def _sub_identify_issues(self, question: str) -> List[str]:
        """Identifica posibles problemas de datos (determinista)."""
        issues = []
        msg = question.lower()

        if "presupuesto" in msg:
            issues.append("Un cliente puede tener múltiples presupuestos para la misma instalación")
            issues.append("Presupuestos sin cliente asignado (CODCLIENTE nulo)")
        if "tasa" in msg or "éxito" in msg or "aceptado" in msg:
            issues.append("La tasa puede estar distorsionada por presupuestos duplicados")
            issues.append("Definición de 'aceptado' puede variar (pedido, albarán, factura)")
        if "instalación" in msg or "instalacion" in msg:
            issues.append("Una instalación puede tener N presupuestos — total presupuestos ≠ total instalaciones")
        if "cliente" in msg:
            issues.append("Clientes duplicados con diferente CODIGO pero mismo nombre")
        if "factura" in msg or "importe" in msg:
            issues.append("Facturas con importe 0 o negativo (abonos)")

        return issues

    def _explain_depth(self, question: str, depth: AnalysisDepth) -> str:
        reasons = {
            AnalysisDepth.EPIC:   "Pregunta compleja que requiere análisis multi-dimensional",
            AnalysisDepth.DEEP:   "Pregunta con múltiples dimensiones de análisis",
            AnalysisDepth.MEDIUM: "Pregunta moderada con contexto adicional útil",
            AnalysisDepth.BASIC:  "Pregunta simple y directa",
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
        exploration: Dict = {}

        for table in tables:
            exploration[table] = await self._explore_table(table, cfg)

        # Expansión dinámica (solo DEEP/EPIC)
        if cfg["max_sqls"] >= 8:
            extra_tables = await self._ask_for_extra_tables(question, exploration, cfg)
            for extra_table in extra_tables:
                if extra_table not in exploration:
                    logger.info(f"[DEEP AGENT] Explorando tabla adicional: {extra_table}")
                    exploration[extra_table] = await self._explore_table(extra_table, cfg)
                    cfg["explore_tables"] = len(exploration)

        phase.data = exploration
        phase.sub_phases.append(SubPhaseResult("2.x Exploración tablas", True, exploration))
        logger.info(f"[DEEP AGENT] Fase 2 OK: {len(exploration)} tablas exploradas")
        return phase
