"""
agent.py — DeepAnalysisAgent: orquestador principal del análisis épico multi-fase.

Hereda de:
  Phases12Mixin  (phases_1_2.py) — Fases 0, 1, 2
  Phases345Mixin (phases_3_4_5.py) — Fases 3, 3b, 4, 4b, 5

Responsabilidades:
  - Inicialización (orchestrator, db_context, budget, sql_normalizer)
  - Integración con SIUO (ContextRetriever) para contexto jerárquico
  - Orquestación del BUCLE DE INVESTIGACIÓN ITERATIVA con salida inteligente
  - Helpers compartidos (_safe_sql, _parse_json, _fmt_*, _build_warnings_html)
  - Fallback de emergencia si todo falla
  - Limpieza de ficheros temporales al finalizar

BUCLE DE INVESTIGACIÓN:
  El agente entra en un bucle Fase3→Fase4→Fase3b que se repite hasta que:
    a) La IA decide que ya no hay más que investigar (continue=false)
    b) Se alcanza MAX_INVESTIGATION_CYCLES (parámetro centralizado en models.py)
    c) La fiabilidad es "alto" y hay pocas anomalías sin resolver
  Esto garantiza que las inconsistencias detectadas se RESUELVEN, no solo se reportan.

CALIDAD DE DATOS ESTRUCTURALES:
  El agente detecta y analiza:
    - Datos en columnas incorrectas (ej: código en campo descripción)
    - Columnas con contenido mixto (ej: "COD001 - Nombre - Descripción" en un campo)
    - Registros con estructura inconsistente (algunos con código+nombre, otros sin)
    - Valores nulos donde no debería haberlos
    - Formatos de datos heterogéneos en la misma columna
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.modules.chat.deep_analysis.models import (
    AnalysisDepth, DEPTH_CONFIG, EpicAnalysisResult, TokenBudget,
    detect_depth, DEFAULT_CONTEXT_LIMIT_TOKENS,
    MAX_INVESTIGATION_CYCLES, MIN_ISSUES_TO_CONTINUE,
    RELIABILITY_EXIT_THRESHOLD, MAX_SQLS_PER_CYCLE,
)
from backend.modules.chat.deep_analysis.phases_1_2 import Phases12Mixin
from backend.modules.chat.deep_analysis.phases_3_4_5 import Phases345Mixin

# Importación a nivel de módulo para permitir mocking en tests
try:
    from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
except ImportError:
    get_knowledge_store = None  # type: ignore

logger = logging.getLogger(__name__)


class DeepAnalysisAgent(Phases12Mixin, Phases345Mixin):
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

        Args:
            question:             Pregunta del usuario en lenguaje natural.
            conversation_history: Historial de conversación previo.
            depth:                Nivel de profundidad (auto-detectado si None).

        Returns:
            Respuesta final en Markdown con análisis completo y amigable.
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
            # Cada ciclo: Fase 3 → Fase 4 → Fase 3b → decisión de continuar
            # Salida: IA dice "no hay más que investigar" O se alcanza el máximo
            last_analysis_data: Dict = {}
            for cycle in range(MAX_INVESTIGATION_CYCLES):
                result.investigation_cycles = cycle + 1
                logger.info(
                    f"[DEEP AGENT] ── CICLO {cycle + 1}/{MAX_INVESTIGATION_CYCLES} ──"
                )

                # Fase 3: Investigación multi-angular
                # En ciclos > 0, reducir SQLs para no saturar el contexto
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

                # ── Decisión de continuar el bucle ────────────────────────────
                should_continue, reason = await self._should_continue_investigation(
                    question, result, last_analysis_data, cycle
                )
                logger.info(
                    f"[DEEP AGENT] Ciclo {cycle + 1}: continuar={should_continue} | {reason}"
                )
                if not should_continue:
                    logger.info(f"[DEEP AGENT] ✅ Bucle terminado: {reason}")
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

            # Limpieza de ficheros temporales
            self._cleanup_partial_files(result)

            if result.final_answer:
                logger.info(
                    f"[DEEP AGENT] ✅ Análisis completado: "
                    f"{result.investigation_cycles} ciclos, "
                    f"{len(result.sql_queries)} SQLs, "
                    f"{len(result.warnings)} warnings, "
                    f"{len(result.final_answer)} chars"
                )
                return result.final_answer
            else:
                return self._emergency_fallback(result)

        except Exception as e:
            logger.error(f"[DEEP AGENT] ❌ Error crítico en análisis: {e}", exc_info=True)
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

        Criterios de SALIDA (no continuar):
          1. Fiabilidad "alto" + pocas anomalías sin resolver → suficiente
          2. Sin anomalías ni warnings nuevos en este ciclo → convergió
          3. Presupuesto de tokens casi agotado → parar
          4. Último ciclo (cycle == MAX_INVESTIGATION_CYCLES - 1) → siempre parar

        Criterios de CONTINUACIÓN:
          1. Hay anomalías sin resolver (año futurista, tipo incorrecto, etc.)
          2. La IA detecta inconsistencias estructurales en los datos
          3. Hay columnas con contenido mixto o datos en columnas incorrectas
          4. La fiabilidad es "bajo" o "medio"

        La IA también puede votar explícitamente con un JSON de decisión.
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
                    # Guardar los nuevos ángulos para que Fase 3 los use en el siguiente ciclo
                    result.business_insights.append(
                        f"[BUCLE] Nuevos ángulos a investigar: {'; '.join(new_angles[:3])}"
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

        La IA evalúa:
          - ¿Quedan inconsistencias sin resolver?
          - ¿Hay columnas con datos mixtos o en columnas incorrectas?
          - ¿Los datos tienen estructuras heterogéneas?
          - ¿Hay ángulos de análisis no explorados?

        Devuelve JSON: {"continue": bool, "reason": str, "new_angles": [...]}
        """
        try:
            anomalies_text = "\n".join(f"• {a}" for a in result.anomalies[:5])
            warnings_text = "\n".join(f"• {w}" for w in result.warnings[:5])
            resolved = [q for q in result.sql_queries if q.get("is_resolution")]
            resolved_text = "\n".join(
                f"• {q['objetivo']}: {q.get('rows', 0)} filas"
                for q in resolved[:4]
            )
            reliability = analysis_data.get("reliability_score", "?")
            hypotheses = "\n".join(
                f"• {h}" for h in analysis_data.get("hypotheses", [])[:3]
            )

            system = (
                "Eres un analista de datos experto. Decide si hay más que investigar "
                "en esta base de datos Firebird para responder la pregunta.\n\n"
                "CRITERIOS PARA CONTINUAR:\n"
                "• Hay inconsistencias estructurales sin resolver (datos en columnas incorrectas)\n"
                "• Hay columnas con contenido mixto (código+nombre+descripción en un campo)\n"
                "• Hay registros con estructura heterogénea (algunos con código, otros sin él)\n"
                "• Hay anomalías de datos sin explicación confirmada\n"
                "• La fiabilidad es baja o media y hay hipótesis sin verificar\n\n"
                "CRITERIOS PARA PARAR:\n"
                "• Todas las inconsistencias tienen explicación confirmada con datos\n"
                "• La fiabilidad es alta\n"
                "• No hay nuevos ángulos de análisis que aporten valor\n\n"
                "Responde SOLO JSON:\n"
                '{"continue": true/false, "reason": "explicación breve", '
                '"new_angles": ["ángulo1", "ángulo2"]}'
            )
            data_preview = self._fmt_investigation(result.sql_queries[-4:])
            user_msg = self.budget.truncate_to_fit(
                f"PREGUNTA: {question}\n\n"
                f"CICLO ACTUAL: {cycle + 1}/{MAX_INVESTIGATION_CYCLES}\n"
                f"FIABILIDAD: {reliability}\n\n"
                f"ANOMALÍAS SIN RESOLVER:\n{anomalies_text}\n\n"
                f"ADVERTENCIAS:\n{warnings_text}\n\n"
                f"RESOLUCIONES EJECUTADAS:\n{resolved_text}\n\n"
                f"HIPÓTESIS:\n{hypotheses}\n\n"
                f"ÚLTIMOS DATOS:\n{data_preview}",
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

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS COMPARTIDOS (usados por los mixins)
    # ─────────────────────────────────────────────────────────────────────────

    def _safe_sql(self, sql: str) -> List[Dict]:
        """Ejecuta SQL de forma segura. Lanza excepción si falla."""
        if self.sql_executor:
            return self.sql_executor(sql)
        raise RuntimeError("sql_executor no configurado")

    def _parse_json(self, text: str) -> Optional[Any]:
        """Extrae y parsea JSON de una respuesta de texto."""
        if not text:
            return None
        try:
            return json.loads(text.strip())
        except Exception:
            pass
        for pattern in [r'```json\s*(.*?)```', r'```\s*([\[{].*?[\]}])\s*```', r'([\[{].*[\]}])']:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1).strip())
                except Exception:
                    pass
        return None

    async def _ai_fix_sql(self, sql: str, error: str) -> Optional[str]:
        """Pide a la IA que corrija un SQL fallido."""
        try:
            system = (
                "Eres un experto en Firebird 2.5. Corrige el SQL que falló. "
                "Responde SOLO con el SQL corregido, sin explicaciones."
            )
            user_msg = self.budget.truncate_to_fit(
                f"SQL FALLIDO:\n{sql}\n\nERROR:\n{error}\n\nEsquema:\n{self.db_context[:1000]}",
                system
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            if resp:
                blocks = re.findall(r'```sql\s*(.*?)```', resp, re.DOTALL | re.IGNORECASE)
                return blocks[0].strip() if blocks else resp.strip()
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _ai_fix_sql error: {e}")
        return None

    def _fmt_conversation_history(self, history: List[Dict]) -> str:
        """Formatea el historial de conversación para incluir en prompts."""
        if not history:
            return ""
        lines = []
        for msg in history[-6:]:
            role = msg.get("role", "user")
            content = str(msg.get("content", ""))[:300]
            lines.append(f"[{role.upper()}]: {content}")
        return "\n".join(lines)

    def _fmt_exploration(self, exploration: Dict) -> str:
        """Formatea los datos de exploración de tablas para prompts."""
        if not exploration:
            return "Sin datos de exploración."
        lines = []
        for table, info in exploration.items():
            if not isinstance(info, dict):
                continue
            total = info.get("total", "?")
            cols = ", ".join(info.get("columns", [])[:8])
            tipo_dist = info.get("tipo_distribution", [])
            tipo_str = ""
            if tipo_dist:
                tipo_str = " | TIPOS: " + ", ".join(
                    f"TIPO={r.get('TIPO','?')}:{r.get('N','?')}" for r in tipo_dist[:5]
                )
            null_cc = info.get("null_codcliente")
            null_str = f" | NULOS_CODCLIENTE={null_cc}" if null_cc is not None else ""
            lines.append(f"• {table}: {total} registros | Cols: {cols}{tipo_str}{null_str}")
        return "\n".join(lines)

    def _fmt_investigation(self, sql_queries: List[Dict]) -> str:
        """Formatea los resultados de investigación para prompts."""
        if not sql_queries:
            return "Sin resultados de investigación."
        lines = []
        for q in sql_queries:
            objetivo = q.get("objetivo", "?")
            rows = q.get("rows", 0)
            data = q.get("data", [])
            error = q.get("error")
            is_res = " [RESOLUCIÓN]" if q.get("is_resolution") else ""
            if error:
                lines.append(f"• [{objetivo}]{is_res} ERROR: {error}")
            else:
                lines.append(f"• [{objetivo}]{is_res} {rows} filas")
                for row in data[:3]:
                    lines.append(f"  {row}")
        return "\n".join(lines)

    def _build_warnings_html(self, result: EpicAnalysisResult) -> str:
        """Construye HTML de advertencias para mostrar en el frontend."""
        if not result.warnings and not result.anomalies:
            return ""
        parts = []
        if result.warnings:
            items = "".join(f"<li>{w}</li>" for w in result.warnings[:5])
            parts.append(
                f'<div style="background:#fff3cd;border-left:4px solid #ffc107;'
                f'padding:8px 12px;margin:8px 0;border-radius:4px">'
                f'<strong>⚠️ Advertencias</strong><ul style="margin:4px 0">{items}</ul></div>'
            )
        if result.anomalies:
            items = "".join(f"<li>{a}</li>" for a in result.anomalies[:3])
            parts.append(
                f'<div style="background:#f8d7da;border-left:4px solid #dc3545;'
                f'padding:8px 12px;margin:8px 0;border-radius:4px">'
                f'<strong>🔴 Anomalías detectadas</strong><ul style="margin:4px 0">{items}</ul></div>'
            )
        return "\n".join(parts)

    def _emergency_fallback(self, result: EpicAnalysisResult) -> str:
        """Respuesta de emergencia si todo falla — siempre devuelve algo útil."""
        parts = [f"## 📊 Análisis de: {result.question}\n"]

        if result.sql_queries:
            parts.append(f"Se ejecutaron {len(result.sql_queries)} consultas:\n")
            for q in result.sql_queries[:5]:
                objetivo = q.get("objetivo", "?")
                rows = q.get("rows", 0)
                error = q.get("error")
                if error:
                    parts.append(f"- ❌ **{objetivo}**: {error}")
                else:
                    parts.append(f"- ✅ **{objetivo}**: {rows} filas")
                    for row in q.get("data", [])[:2]:
                        parts.append(f"  `{row}`")
        else:
            parts.append("No se pudieron ejecutar consultas SQL.")

        if result.warnings:
            parts.append("\n**⚠️ Advertencias:**")
            parts.extend(f"- {w}" for w in result.warnings[:3])

        parts.append(
            "\n> ⚠️ La síntesis automática no pudo completarse. "
            "Los datos anteriores son los resultados directos de la base de datos."
        )
        return "\n".join(parts)

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE METADATOS SIUO (resiliencia multi-fuente)
    # ─────────────────────────────────────────────────────────────────────────

    _METADATA_PATH = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "core", "config", "db_metadata_optimized.json"
    ))

    def _load_metadata_json(self) -> Dict:
        try:
            path = self._METADATA_PATH
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _load_metadata_json: {e}")
        return {}

    def _get_siuo_columns(self, table: str) -> List[str]:
        try:
            meta = self._load_metadata_json()
            tables = meta.get("tables", {})
            table_data = tables.get(table) or tables.get(table.upper()) or tables.get(table.lower())
            if not table_data:
                return []
            if isinstance(table_data, dict):
                cols = table_data.get("columns", [])
                if cols and isinstance(cols, list):
                    result = []
                    for c in cols:
                        if isinstance(c, str):
                            result.append(c.strip())
                        elif isinstance(c, dict):
                            name = c.get("name") or c.get("column_name") or c.get("col")
                            if name:
                                result.append(str(name).strip())
                    return [c for c in result if c]
            if isinstance(table_data, list):
                result = []
                for c in table_data:
                    if isinstance(c, str):
                        result.append(c.strip())
                    elif isinstance(c, dict):
                        name = c.get("name") or c.get("column_name") or c.get("col")
                        if name:
                            result.append(str(name).strip())
                return [c for c in result if c]
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _get_siuo_columns({table}): {e}")
        return []

    def _get_siuo_record_count(self, table: str) -> Optional[int]:
        try:
            meta = self._load_metadata_json()
            tables = meta.get("tables", {})
            table_data = tables.get(table) or tables.get(table.upper()) or tables.get(table.lower())
            if not table_data or not isinstance(table_data, dict):
                return None
            for field in ("record_count", "row_count", "total_rows", "count", "rows"):
                val = table_data.get(field)
                if val is not None:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _get_siuo_record_count({table}): {e}")
        return None

    def _phase0_lan_optimize(self, cfg: Dict) -> Dict:
        try:
            is_lan = False
            try:
                preferred = getattr(self.orchestrator, "preferred_model_id", None)
                if preferred and "jddcia" in str(preferred).lower():
                    is_lan = True
                ai_mode = getattr(self.orchestrator, "ai_mode", None)
                if ai_mode and "local" in str(ai_mode).lower():
                    is_lan = True
            except Exception:
                pass

            known_sqls_count = 0
            try:
                # Usa el import a nivel de módulo para permitir mocking en tests
                if get_knowledge_store is not None:
                    store = get_knowledge_store()
                    patterns = store.get_patterns_for_intent([])
                    known_sqls_count = len(patterns) if patterns else 0
            except Exception:
                pass

            cfg["lan_mode"] = is_lan
            cfg["known_sqls_count"] = known_sqls_count

            if is_lan:
                logger.info(
                    f"[DEEP AGENT] 🏠 Modo LAN | prompt conciso | "
                    f"{known_sqls_count} patrones en KnowledgeStore"
                )
            else:
                logger.info(
                    f"[DEEP AGENT] 🌐 Modo internet | prompt completo | "
                    f"{known_sqls_count} patrones en KnowledgeStore"
                )
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _phase0_lan_optimize: {e}")
            cfg.setdefault("lan_mode", False)
            cfg.setdefault("known_sqls_count", 0)
        return cfg

    def _extract_columns_from_context(self, table: str) -> List[str]:
        if not self.db_context or not table:
            return []
        try:
            ctx = self.db_context
            table_upper = table.upper()
            m = re.search(
                rf'{re.escape(table_upper)}\s*\|[^\n]*[Cc]ols?:\s*([^\n|]+)',
                ctx, re.IGNORECASE
            )
            if m:
                return [c.strip() for c in m.group(1).split(",") if c.strip()]
            m = re.search(
                rf'{re.escape(table_upper)}\s*\(([^)]+)\)',
                ctx, re.IGNORECASE
            )
            if m:
                return [c.strip() for c in m.group(1).split(",") if c.strip()]
            m = re.search(
                rf'{re.escape(table_upper)}\s*\n\s*[Cc]olumnas?:\s*([^\n]+)',
                ctx, re.IGNORECASE
            )
            if m:
                return [c.strip() for c in m.group(1).split(",") if c.strip()]
            m = re.search(
                rf'{re.escape(table_upper)}\s*:\s*([A-Z_][A-Z0-9_\s|,]+)',
                ctx, re.IGNORECASE
            )
            if m:
                raw = m.group(1)
                sep = "|" if "|" in raw else ","
                return [c.strip() for c in raw.split(sep) if c.strip() and len(c.strip()) < 40]
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _extract_columns_from_context({table}): {e}")
        return []
