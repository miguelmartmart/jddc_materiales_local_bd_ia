"""
agent.py — DeepAnalysisAgent: orquestador principal del análisis épico multi-fase.

Hereda de:
  HelpersAgentMixin (helpers.py)    — helpers compartidos, metadatos SIUO, LAN
  Phases12Mixin     (phases_1_2.py) — Fases 0, 1, 2
  Phases345Mixin    (phases_3_4_5.py) — Fases 3, 3b, 4, 4b, 5

Responsabilidades:
  - Inicialización (orchestrator, db_context, budget, sql_normalizer)
  - Orquestación del BUCLE DE INVESTIGACIÓN ITERATIVA con salida inteligente
  - Fallback de emergencia si todo falla
  - Limpieza de ficheros temporales al finalizar

BUCLE DE INVESTIGACIÓN:
  Fase3 → Fase4 → Fase3b → decisión IA → repetir hasta MAX_INVESTIGATION_CYCLES
  Salida: IA dice "no hay más" O fiabilidad alta + pocas anomalías O presupuesto agotado
"""

import logging
from typing import Dict, List, Optional, Tuple

from backend.modules.chat.deep_analysis.models import (
    AnalysisDepth, DEPTH_CONFIG, EpicAnalysisResult, TokenBudget,
    detect_depth, DEFAULT_CONTEXT_LIMIT_TOKENS,
    MAX_INVESTIGATION_CYCLES, MIN_ISSUES_TO_CONTINUE,
    RELIABILITY_EXIT_THRESHOLD, MAX_SQLS_PER_CYCLE,
)
from backend.modules.chat.deep_analysis.helpers import HelpersAgentMixin
from backend.modules.chat.deep_analysis.phases_1_2 import Phases12Mixin
from backend.modules.chat.deep_analysis.phases_3_4_5 import Phases345Mixin
from backend.modules.chat.deep_analysis.phase_verify import PhaseVerifyMixin

# Importación a nivel de módulo para permitir mocking en tests
try:
    from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
except ImportError:
    get_knowledge_store = None  # type: ignore

logger = logging.getLogger(__name__)


class DeepAnalysisAgent(HelpersAgentMixin, Phases12Mixin, Phases345Mixin, PhaseVerifyMixin):
    """
    Agente de análisis profundo multi-fase ÉPICO v3.0.

    Uso:
        agent = DeepAnalysisAgent(orchestrator, db_context, sql_executor, sql_normalizer)
        answer = await agent.analyze("¿cuántos presupuestos hay?", conversation_history)
    """

    def __init__(
        self,
        orchestrator,
        db_context: str,
        sql_executor=None,
        sql_normalizer=None,
        sql_corrector=None,
        context_limit_tokens: int = DEFAULT_CONTEXT_LIMIT_TOKENS,
    ):
        self.orchestrator    = orchestrator
        self.db_context      = db_context
        self.sql_executor    = sql_executor
        self.sql_normalizer  = sql_normalizer
        self.sql_corrector   = sql_corrector
        self.budget          = TokenBudget(context_limit_tokens)

        # Intentar obtener el límite real del modelo desde el orchestrator
        try:
            model_limit = getattr(orchestrator, "context_limit_tokens", None)
            if model_limit and isinstance(model_limit, int) and model_limit > 0:
                self.budget = TokenBudget(model_limit)
                logger.info(f"[DEEP AGENT] Límite de contexto del modelo: {model_limit} tokens")
        except Exception:
            pass

        logger.info("[DEEP AGENT] DeepAnalysisAgent v3.0 inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # API PÚBLICA
    # ─────────────────────────────────────────────────────────────────────────

    async def analyze(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None,
        depth: Optional[AnalysisDepth] = None,
    ) -> str:
        """
        Ejecuta el análisis épico multi-fase con BUCLE DE INVESTIGACIÓN ITERATIVA.

        Flujo:
          Fase 0  → Presupuesto de tokens + optimización LAN
          Fase 1  → Comprensión épica (intención, sub-preguntas, tablas)
          Fase 2  → Exploración total (conteo, columnas, muestreo)
          BUCLE (hasta MAX_INVESTIGATION_CYCLES):
            Fase 3  → Investigación multi-angular (SQLs dinámicos + fijos)
            Fase 4  → Análisis crítico (anomalías, calidad, contexto)
            Fase 3b → Resolución de inconsistencias detectadas
            → IA decide si continuar o salir
          Fase 4b → Aprendizaje permanente (KnowledgeStore)
          Fase 5  → Síntesis épica (respuesta amigable para el usuario)
        """
        conversation_history = conversation_history or []
        detected_depth = depth or detect_depth(question)
        cfg = dict(DEPTH_CONFIG[detected_depth])  # copia mutable

        result = EpicAnalysisResult(question=question, depth=detected_depth)
        logger.info(
            f"[DEEP AGENT] ══════════════════════════════════════════\n"
            f"[DEEP AGENT] ANÁLISIS ÉPICO v3.0: '{question[:80]}'\n"
            f"[DEEP AGENT] Profundidad: {detected_depth.value.upper()} | "
            f"max_sqls={cfg['max_sqls']} | explore_tables={cfg['explore_tables']}\n"
            f"[DEEP AGENT] Historial: {len(conversation_history)} mensajes\n"
            f"[DEEP AGENT] Bucle máx: {MAX_INVESTIGATION_CYCLES} ciclos\n"
            f"[DEEP AGENT] ══════════════════════════════════════════"
        )

        try:
            # ── FASE 0: Ajuste de presupuesto de tokens ───────────────────────
            cfg = self._phase0_budget(cfg, question, conversation_history)
            cfg = self._phase0_lan_optimize(cfg)

            # ── FASE 1: Comprensión épica ─────────────────────────────────────
            phase1 = await self._phase1_understand(question, result, cfg, conversation_history)
            result.phases.append(phase1)
            phase1_data = phase1.data or {}

            # ── FASE 2: Exploración total ─────────────────────────────────────
            phase2 = await self._phase2_explore(question, phase1_data, result, cfg)
            result.phases.append(phase2)
            phase2_data = phase2.data or {}

            # ── BUCLE DE INVESTIGACIÓN ITERATIVA ─────────────────────────────
            last_analysis_data: Dict = {}
            for cycle in range(MAX_INVESTIGATION_CYCLES):
                result.investigation_cycles = cycle + 1
                logger.info(f"[DEEP AGENT] ── CICLO {cycle + 1}/{MAX_INVESTIGATION_CYCLES} ──")

                # Fase 3: Investigación multi-angular
                cycle_cfg = dict(cfg)
                if cycle > 0:
                    cycle_cfg["max_sqls"] = min(cfg["max_sqls"], MAX_SQLS_PER_CYCLE)

                phase3 = await self._phase3_investigate(
                    question, phase1_data, phase2_data, result, cycle_cfg
                )
                result.phases.append(phase3)

                # Fase 4: Análisis crítico profundo
                phase4 = await self._phase4_analyze(question, result, cycle_cfg)
                result.phases.append(phase4)
                last_analysis_data = phase4.data if phase4.data else {}

                # Fase 3b: Resolución de inconsistencias detectadas
                phase3b = await self._phase3b_resolve_inconsistencies(
                    question, result, cycle_cfg
                )
                result.phases.append(phase3b)

                # Decisión de continuar el bucle
                should_continue, reason = await self._should_continue_investigation(
                    question, result, last_analysis_data, cycle
                )
                logger.info(
                    f"[DEEP AGENT] Ciclo {cycle + 1}: continuar={should_continue} | {reason}"
                )
                if not should_continue:
                    logger.info(f"[DEEP AGENT] Bucle terminado: {reason}")
                    break

            logger.info(
                f"[DEEP AGENT] Bucle completado: {result.investigation_cycles} ciclos, "
                f"{len(result.sql_queries)} SQLs totales"
            )

            # ── FASE 4b: Aprendizaje permanente ──────────────────────────────
            phase4b = await self._phase4b_learn_and_persist(
                question, phase2_data, result, last_analysis_data
            )
            result.phases.append(phase4b)

            # ── FASE 5: Síntesis épica ────────────────────────────────────────
            phase5 = await self._phase5_synthesize(question, result, cfg)
            result.phases.append(phase5)

            # ── BUCLE DE CALIDAD POST-SÍNTESIS ────────────────────────────────
            # Cierra el ciclo: evaluación de calidad → si insuficiente → investigación
            # adicional (máx. 1 ciclo extra) → re-síntesis.
            if self._needs_extra_investigation(result):
                logger.info(
                    "[DEEP AGENT] ⟳ Evaluación post-síntesis: calidad insuficiente "
                    "→ ciclo extra de investigación"
                )
                _extra_cfg = {**cfg, "max_sqls": min(cfg.get("max_sqls", 5), 4)}
                phase3_extra = await self._phase3_investigate(
                    question, phase1_data, phase2_data, result, _extra_cfg
                )
                result.phases.append(phase3_extra)
                result.investigation_cycles += 1
                phase5 = await self._phase5_synthesize(question, result, cfg)
                result.phases.append(phase5)
                logger.info("[DEEP AGENT] ✅ Ciclo extra de calidad completado")

            # ── FASE 5b: Verificación de resultados ───────────────────────────
            # Verifica que la respuesta IA no contiene datos inventados.
            # Añade sello de fiabilidad al final de la respuesta.
            try:
                phase5b = await self._phase5b_verify(question, result, cfg)
                result.phases.append(phase5b)
            except Exception as verify_err:
                logger.warning(f"[DEEP AGENT] Fase 5b (verificación) falló: {verify_err}")

            # Limpieza de ficheros temporales
            self._cleanup_partial_files(result)

            if result.final_answer:
                logger.info(
                    f"[DEEP AGENT] Análisis completado: "
                    f"{result.investigation_cycles} ciclos, "
                    f"{len(result.sql_queries)} SQLs, "
                    f"{len(result.warnings)} warnings, "
                    f"{len(result.final_answer)} chars"
                )
                return result.final_answer
            else:
                return self._emergency_fallback(result)

        except Exception as e:
            logger.error(f"[DEEP AGENT] Error crítico en análisis: {e}", exc_info=True)
            self._cleanup_partial_files(result)
            return self._emergency_fallback(result)

    # ─────────────────────────────────────────────────────────────────────────
    # DECISIÓN DE CONTINUAR EL BUCLE
    # ─────────────────────────────────────────────────────────────────────────

    async def _should_continue_investigation(
        self,
        question: str,
        result: EpicAnalysisResult,
        analysis_data: Dict,
        cycle: int,
    ) -> Tuple[bool, str]:
        """
        Decide si el bucle de investigación debe continuar.

        Criterios de SALIDA:
          1. Último ciclo → siempre parar
          2. Presupuesto de tokens casi agotado (>85%)
          3. Fiabilidad alta + pocas anomalías → suficiente
          4. Sin anomalías ni warnings → convergió

        Criterios de CONTINUACIÓN:
          1. Hay anomalías sin resolver
          2. La IA detecta inconsistencias estructurales
          3. Fiabilidad baja o media con hipótesis sin verificar
        """
        # Criterio 1: último ciclo → siempre parar
        if cycle >= MAX_INVESTIGATION_CYCLES - 1:
            return False, f"Máximo de ciclos alcanzado ({MAX_INVESTIGATION_CYCLES})"

        # Criterio 2: presupuesto de tokens casi agotado
        data_text = self._fmt_investigation(result.sql_queries)
        if self.budget.usage_pct(data_text) > 0.85:
            return False, "Presupuesto de tokens casi agotado (>85%)"

        # Criterio 3: fiabilidad alta + pocas anomalías → suficiente
        reliability = analysis_data.get("reliability_score", "medio")
        n_anomalies = len(result.anomalies)
        n_warnings = len(result.warnings)
        if reliability == RELIABILITY_EXIT_THRESHOLD and n_anomalies < MIN_ISSUES_TO_CONTINUE:
            return False, f"Fiabilidad={reliability}, anomalías={n_anomalies} → análisis completo"

        # Criterio 4: sin anomalías ni warnings → convergió
        if n_anomalies == 0 and n_warnings == 0:
            return False, "Sin anomalías ni advertencias — análisis convergido"

        # Criterio 5: preguntar a la IA si hay más que investigar
        try:
            continue_decision = await self._ai_continue_decision(
                question, result, analysis_data, cycle
            )
            if continue_decision is not None:
                should = continue_decision.get("continue", False)
                reason = continue_decision.get("reason", "decisión IA")
                new_angles = continue_decision.get("new_angles", [])
                if new_angles:
                    result.business_insights.append(
                        f"[BUCLE] Nuevos ángulos: {'; '.join(new_angles[:3])}"
                    )
                return should, reason
        except Exception as e:
            logger.warning(f"[DEEP AGENT] _ai_continue_decision falló: {e}")

        # Por defecto: continuar si hay anomalías sin resolver
        if n_anomalies >= MIN_ISSUES_TO_CONTINUE or n_warnings >= MIN_ISSUES_TO_CONTINUE:
            return True, f"Hay {n_anomalies} anomalías y {n_warnings} warnings sin resolver"

        return False, "Sin criterios de continuación — análisis suficiente"

    async def _ai_continue_decision(
        self,
        question: str,
        result: EpicAnalysisResult,
        analysis_data: Dict,
        cycle: int,
    ) -> Optional[Dict]:
        """
        Pide a la IA que decida si hay más que investigar.
        Devuelve JSON: {"continue": bool, "reason": str, "new_angles": [...]}
        """
        try:
            anomalies_text = "\n".join(f"• {a}" for a in result.anomalies[:5])
            warnings_text = "\n".join(f"• {w}" for w in result.warnings[:5])
            resolved = [q for q in result.sql_queries if q.get("is_resolution")]
            resolved_text = "\n".join(
                f"• {q['objetivo']}: {q.get('rows', 0)} filas" for q in resolved[:4]
            )
            reliability = analysis_data.get("reliability_score", "?")
            hypotheses = "\n".join(
                f"• {h}" for h in analysis_data.get("hypotheses", [])[:3]
            )

            system = (
                "Eres un analista de datos experto. Decide si hay más que investigar.\n\n"
                "CONTINUAR si: inconsistencias sin resolver, datos mixtos en columnas, "
                "fiabilidad baja/media con hipótesis sin verificar.\n"
                "PARAR si: todas las inconsistencias explicadas, fiabilidad alta, "
                "no hay nuevos ángulos de valor.\n\n"
                'Responde SOLO JSON: {"continue": true/false, "reason": "...", '
                '"new_angles": ["ángulo1"]}'
            )
            data_preview = self._fmt_investigation(result.sql_queries[-4:])
            user_msg = self.budget.truncate_to_fit(
                f"PREGUNTA: {question}\n\nCICLO: {cycle + 1}/{MAX_INVESTIGATION_CYCLES}\n"
                f"FIABILIDAD: {reliability}\n\nANOMALÍAS:\n{anomalies_text}\n\n"
                f"ADVERTENCIAS:\n{warnings_text}\n\nRESOLUCIONES:\n{resolved_text}\n\n"
                f"HIPÓTESIS:\n{hypotheses}\n\nÚLTIMOS DATOS:\n{data_preview}",
                system
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system,
                user_message=user_msg,
                preferred_model_id="jddcia-qwen3-30b"
            )
            return self._parse_json(resp)
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _ai_continue_decision: {e}")
            return None
