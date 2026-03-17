"""
phases_3_4_5.py — Fases 3, 4 y 5 del DeepAnalysisAgent.

  Fase 3: Investigación multi-angular (SQLs dinámicos + fijos, expansión, resumen progresivo)
  Fase 4: Análisis crítico profundo (anomalías, calidad, contexto, limitaciones, hipótesis)
  Fase 5: Síntesis épica (respuesta principal, análisis, advertencias, sugerencias)

Integración con SIUO:
  - Usa get_context_retriever() para obtener contexto jerárquico optimizado
  - Registra feedback en siuo_query_log.json tras cada análisis
  - Actualiza db_metadata_optimized.json con columnas descubiertas en Fase 2
"""

import json
import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple

# Importación a nivel de módulo para permitir mocking en tests
try:
    from backend.modules.db_explorer.context_retriever import get_context_retriever
except ImportError:
    get_context_retriever = None  # type: ignore

try:
    from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
except ImportError:
    get_knowledge_store = None  # type: ignore

from backend.modules.chat.deep_analysis.models import (
    EpicAnalysisResult, PhaseResult, SubPhaseResult,
    MAX_SQLS_ABSOLUTE, MAX_ROWS_IN_SUMMARY, SUMMARY_THRESHOLD,
)

logger = logging.getLogger(__name__)


class Phases345Mixin:
    """
    Mixin con las fases 3, 4 y 5 del agente.
    Requiere que la clase base tenga:
      self.orchestrator, self.db_context, self.budget (TokenBudget),
      self.sql_normalizer, self.sql_corrector,
      self._safe_sql(), self._parse_json(),
      self._fmt_exploration(), self._fmt_investigation(),
      self._build_warnings_html(), self._emergency_fallback()
    """

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

        # SQLs fijos (distribución temporal + instalaciones únicas)
        fixed_sqls = self._build_fixed_sqls(question, phase2_data)

        # Obtener contexto SIUO optimizado para la pregunta
        siuo_context = self._get_siuo_context(question, n_sqls)

        schema_for_prompt = self.budget.truncate_to_fit(
            siuo_context, exploration_summary, question
        )

        # Limitar sub_questions y potential_issues para no inflar el prompt
        sub_q_str = "; ".join(str(q) for q in sub_questions[:3])
        issues_str = "; ".join(str(p) for p in potential_issues[:2])

        # Obtener patrones conocidos del KnowledgeStore para enriquecer el prompt
        # (la IA sabe qué SQLs ya están cubiertos y genera solo los nuevos)
        known_patterns_text = self._get_known_patterns_text(question, cfg)

        lan_mode = cfg.get("lan_mode", False)
        system = self._build_phase3_system(
            schema_for_prompt, exploration_summary, n_sqls,
            lan_mode=lan_mode, known_patterns_text=known_patterns_text
        )
        user_msg = (
            f"PREGUNTA: {question}\n\n"
            f"SUB-PREGUNTAS: {sub_q_str}\n\n"
            f"POSIBLES PROBLEMAS: {issues_str}"
        )

        try:
            response, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 3 IA falló: {e}")
            phase.error = str(e)
            await self._execute_fixed_sqls(fixed_sqls, result, phase)
            phase.success = len(result.sql_queries) > 0
            return phase

        # Guardia: si la IA devolvió None o vacío, usar solo SQLs fijos
        if not response or not isinstance(response, str):
            logger.warning("[DEEP AGENT] Fase 3: respuesta IA vacía — usando solo SQLs fijos")
            await self._execute_fixed_sqls(fixed_sqls, result, phase)
            phase.success = len(result.sql_queries) > 0
            return phase

        # Detectar si la IA pide más SQLs (expansión dinámica)
        extra_match = re.search(r'<!--\s*NECESITO_MAS_SQLS:\s*(\d+)\s*-->', response)
        if extra_match:
            extra_needed = int(extra_match.group(1))
            new_max = min(n_sqls + extra_needed, MAX_SQLS_ABSOLUTE)
            if new_max > n_sqls:
                logger.info(f"[DEEP AGENT] IA solicita {extra_needed} SQLs adicionales → máximo: {new_max}")
                cfg["max_sqls"] = new_max
                n_sqls = new_max

        # Extraer bloques SQL
        sql_blocks = re.findall(r'```sql\s*(.*?)```', response, re.DOTALL | re.IGNORECASE)
        if not sql_blocks:
            sql_blocks = [l.strip() for l in response.split('\n') if l.strip().upper().startswith('SELECT')]

        # Combinar SQLs de la IA + SQLs fijos
        all_blocks = list(sql_blocks) + fixed_sqls
        executed_ok = 0

        for i, sql_raw in enumerate(all_blocks[:n_sqls]):
            sql = sql_raw.strip() if isinstance(sql_raw, str) else sql_raw.get("sql", "").strip()
            objetivo = (
                sql_raw.get("objetivo", f"Consulta {i+1}")
                if isinstance(sql_raw, dict)
                else self._extract_objetivo(sql_raw, i)
            )
            if not sql:
                continue

            if self.sql_normalizer:
                try:
                    sql, _ = self.sql_normalizer.normalize(sql)
                except Exception:
                    pass

            logger.info(f"[DEEP AGENT] SQL {i+1}/{len(all_blocks)}: {objetivo[:60]}")
            sql_result, sql_error = await self._execute_with_retry(sql, objetivo)

            entry = {"objetivo": objetivo, "sql": sql, "rows": 0, "data": [], "error": None}
            if sql_result is not None:
                entry["rows"] = len(sql_result)
                entry["data"] = sql_result[:MAX_ROWS_IN_SUMMARY]
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

            # Resumen progresivo si los datos superan el umbral
            inv_text = self._fmt_investigation(result.sql_queries)
            if self.budget.usage_pct(inv_text) > SUMMARY_THRESHOLD:
                logger.info(f"[DEEP AGENT] Resumen progresivo activado")
                await self._progressive_summary(result, question)

        phase.success = executed_ok > 0
        phase.data = result.sql_queries
        logger.info(f"[DEEP AGENT] Fase 3 OK: {executed_ok}/{len(all_blocks)} SQLs exitosos")
        return phase

    def _build_phase3_system(
        self, schema: str, exploration: str, n_sqls: int,
        lan_mode: bool = False, known_patterns_text: str = ""
    ) -> str:
        """
        Construye el system prompt para Fase 3.

        lan_mode=True → prompt más conciso (menos tokens = menos tiempo de generación LAN).
        known_patterns_text → SQLs ya cubiertos por KnowledgeStore (la IA genera solo los nuevos).

        CALIDAD: No se reduce el número de SQLs. Se reduce el TEXTO del prompt
        para que el modelo LAN genere más rápido sin timeout.
        """
        rules = (
            "REGLAS FIREBIRD 2.5:\n"
            "• FIRST N (no LIMIT/TOP) • UPPER(col) LIKE UPPER('%x%')\n"
            "• DOCCAB.TIPO: 0=presupuesto,13=factura,11=albaran,12=pedido,2=SAT\n"
            "• NO ROUND() → CAST(x AS NUMERIC(15,2)) • BLOB→NO GROUP BY\n"
            "• DOCDESTINO vincula origen→destino • DOCLIN sin FECHA→JOIN DOCCAB\n"
        )

        if lan_mode:
            # Prompt conciso para modelo LAN — mismos SQLs, menos texto de instrucciones
            known_section = (
                f"\nSQLs YA CUBIERTOS (no repetir):\n{known_patterns_text}\n"
                if known_patterns_text else ""
            )
            return (
                f"Experto SQL Firebird 2.5. Genera {n_sqls} consultas para investigar la pregunta.\n\n"
                f"ESQUEMA:\n{schema}\n\nEXPLORACIÓN:\n{exploration}\n\n"
                f"{rules}"
                f"{known_section}"
                f"Genera EXACTAMENTE {n_sqls} SQLs. Cada uno: -- [OBJETIVO: ...] + SELECT.\n"
                "Ángulos: principal, calidad, duplicados, temporal(año/serie), "
                "por cliente/agente, outliers, totales, cruce tablas, instalaciones únicas.\n"
                "Si necesitas más: <!-- NECESITO_MAS_SQLS: N -->\n"
                "Formato: ```sql\n-- [OBJETIVO: ...]\nSELECT ...\n```\n"
            )
        else:
            # Prompt completo para modelo internet (GPT-4, Claude, etc.)
            known_section = (
                f"\nPATRONES YA CONOCIDOS (no repetir, generar solo los nuevos):\n{known_patterns_text}\n"
                if known_patterns_text else ""
            )
            return (
                "Eres un experto en SQL Firebird 2.5. Genera múltiples consultas SQL para investigar "
                "una pregunta desde TODOS los ángulos posibles.\n\n"
                f"ESQUEMA OPTIMIZADO (SIUO):\n{schema}\n\n"
                f"EXPLORACIÓN REAL DE TABLAS:\n{exploration}\n\n"
                f"{rules}\n"
                f"{known_section}"
                f"Genera EXACTAMENTE {n_sqls} consultas SQL. Cada una precedida por:\n"
                "-- [OBJETIVO: descripción clara]\n\n"
                "ÁNGULOS OBLIGATORIOS:\n"
                "1. Consulta principal\n2. Calidad (nulos, vacíos)\n3. Duplicados\n"
                "4. Distribución temporal (año/mes/serie) — SIEMPRE\n"
                "5. Por cliente/agente/categoría\n6. Outliers\n7. Totales/promedios\n"
                "8. Cruce con tabla relacionada\n9. Instalaciones únicas vs presupuestos\n"
                "10-12+. Análisis adicionales específicos de la pregunta\n\n"
                "Si necesitas más SQLs: <!-- NECESITO_MAS_SQLS: N -->\n\n"
                "Formato: ```sql\n-- [OBJETIVO: ...]\nSELECT ...\n```\n"
            )

    def _get_known_patterns_text(self, question: str, cfg: Dict) -> str:
        """
        Obtiene los patrones SQL conocidos del KnowledgeStore relevantes para la pregunta.
        Devuelve texto formateado para incluir en el prompt de Fase 3.
        La IA puede así evitar regenerar SQLs ya conocidos y centrarse en los nuevos.
        """
        try:
            if get_knowledge_store is None:
                return ""
            store = get_knowledge_store()
            # Extraer palabras clave de la pregunta para buscar patrones relevantes
            keywords = [w.lower() for w in question.split() if len(w) > 4]
            patterns = store.get_patterns_for_intent(keywords)
            if not patterns:
                return ""
            lines = []
            for p in patterns[:4]:  # máx 4 patrones para no inflar el prompt
                intent = p.get("intent", "?")[:60]
                sql_preview = p.get("sql", "")[:120].replace("\n", " ")
                rows = p.get("rows_returned", "?")
                lines.append(f"• [{intent}] → {sql_preview}... ({rows} filas)")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _get_known_patterns_text: {e}")
            return ""

    def _build_fixed_sqls(self, question: str, phase2_data: Dict) -> List[Dict]:
        """
        SQLs fijos que SIEMPRE se incluyen según el contexto de la pregunta.

        PRIORIDAD 3 — KnowledgeStore en Fase 2:
        Si el KnowledgeStore ya conoce las columnas de DOCCAB (de sesiones anteriores),
        usa esa información para generar SQLs más precisos sin necesidad de consultar RDB$.
        """
        fixed = []
        msg = question.lower()
        doccab_info = phase2_data.get("DOCCAB", {})
        has_serie = doccab_info.get("has_serie", False)
        has_codigoobra = doccab_info.get("has_codigoobra", False)

        # ── PRIORIDAD 3: Enriquecer con columnas conocidas del KnowledgeStore ─
        # Si la BD no estaba disponible en Fase 2, el KnowledgeStore puede tener
        # las columnas reales de sesiones anteriores
        if not has_serie or not has_codigoobra:
            try:
                if get_knowledge_store is not None:
                    store = get_knowledge_store()
                    known = store.get_table("DOCCAB")
                    known_cols = [c.upper() for c in known.get("columns_real", [])]
                    if known_cols:
                        if not has_serie and "SERIE" in known_cols:
                            has_serie = True
                            logger.info("[DEEP AGENT] SERIE detectada desde KnowledgeStore")
                        if not has_codigoobra and "CODIGOOBRA" in known_cols:
                            has_codigoobra = True
                            logger.info("[DEEP AGENT] CODIGOOBRA detectada desde KnowledgeStore")
            except Exception as e:
                logger.debug(f"[DEEP AGENT] KnowledgeStore no disponible en _build_fixed_sqls: {e}")

        # SQL FIJO 1: Distribución temporal (SIEMPRE para DOCCAB)
        if "DOCCAB" in phase2_data:
            if has_serie:
                fixed.append({
                    "objetivo": "Distribución por año y serie",
                    "sql": (
                        "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, SERIE, COUNT(*) AS N, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                        "FROM DOCCAB WHERE TIPO = 0 AND FECHA IS NOT NULL "
                        "GROUP BY EXTRACT(YEAR FROM FECHA), SERIE "
                        "ORDER BY ANO DESC, N DESC"
                    )
                })
            else:
                fixed.append({
                    "objetivo": "Distribución por año",
                    "sql": (
                        "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                        "FROM DOCCAB WHERE TIPO = 0 AND FECHA IS NOT NULL "
                        "GROUP BY EXTRACT(YEAR FROM FECHA) ORDER BY ANO DESC"
                    )
                })

        # SQL FIJO 2: Instalaciones únicas vs presupuestos
        if any(k in msg for k in ["presupuesto", "instalación", "instalacion", "tasa", "éxito"]):
            if has_codigoobra:
                fixed.append({
                    "objetivo": "Presupuestos vs instalaciones únicas (CODIGOOBRA)",
                    "sql": (
                        "SELECT COUNT(*) AS TOTAL_PRESUPUESTOS, "
                        "COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS, "
                        "COUNT(DISTINCT CODIGOOBRA) AS OBRAS_DISTINTAS, "
                        "CAST(COUNT(*) AS NUMERIC(15,2)) / NULLIF(COUNT(DISTINCT CODIGOOBRA), 0) "
                        "AS PRESUPUESTOS_POR_OBRA FROM DOCCAB WHERE TIPO = 0"
                    )
                })
            else:
                fixed.append({
                    "objetivo": "Presupuestos vs clientes únicos",
                    "sql": (
                        "SELECT COUNT(*) AS TOTAL_PRESUPUESTOS, "
                        "COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS, "
                        "CAST(COUNT(*) AS NUMERIC(15,2)) / NULLIF(COUNT(DISTINCT CODCLIENTE), 0) "
                        "AS PRESUPUESTOS_POR_CLIENTE FROM DOCCAB WHERE TIPO = 0"
                    )
                })

        # SQL FIJO 3: Investigación de estado de presupuestos (SIEMPRE para tasa/éxito/aceptado)
        if any(k in msg for k in ["presupuesto", "tasa", "éxito", "exito", "aceptado", "aceptados"]):
            # 3a: Distribución de ESTADOPEND en presupuestos (columna real de DOCCAB)
            fixed.append({
                "objetivo": "Distribución de ESTADOPEND en presupuestos (estado real)",
                "sql": (
                    "SELECT ESTADOPEND, COUNT(*) AS N "
                    "FROM DOCCAB WHERE TIPO = 0 "
                    "GROUP BY ESTADOPEND ORDER BY N DESC"
                )
            })
            # 3b: Presupuestos con documento destino por TIPO del destino
            fixed.append({
                "objetivo": "Presupuestos aceptados por tipo de documento destino (factura/pedido)",
                "sql": (
                    "SELECT d.TIPO AS TIPO_DESTINO, COUNT(DISTINCT dd.CODDOCUMENTO) AS N_PRESUPUESTOS "
                    "FROM DOCDESTINO dd "
                    "JOIN DOCCAB c ON c.CODIGO = dd.CODDOCUMENTO AND c.TIPO = 0 "
                    "JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO "
                    "GROUP BY d.TIPO ORDER BY N_PRESUPUESTOS DESC"
                )
            })
            # 3c: Total presupuestos con AL MENOS UN documento destino (cualquier tipo)
            fixed.append({
                "objetivo": "Total presupuestos con cualquier documento destino vinculado",
                "sql": (
                    "SELECT COUNT(DISTINCT c.CODIGO) AS TOTAL_PRESUPUESTOS, "
                    "COUNT(DISTINCT dd.CODDOCUMENTO) AS CON_DESTINO, "
                    "COUNT(DISTINCT c.CODIGO) - COUNT(DISTINCT dd.CODDOCUMENTO) AS SIN_DESTINO "
                    "FROM DOCCAB c "
                    "LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO "
                    "WHERE c.TIPO = 0"
                )
            })
            # 3d: Explorar si hay columna ACEPTADO o similar en DOCCAB via RDB$RELATION_FIELDS
            fixed.append({
                "objetivo": "Columnas de DOCCAB que contienen ESTADO o ACEPTA (metadatos BD)",
                "sql": (
                    "SELECT FIRST 20 RDB$FIELD_NAME "
                    "FROM RDB$RELATION_FIELDS "
                    "WHERE RDB$RELATION_NAME = 'DOCCAB' "
                    "AND (UPPER(RDB$FIELD_NAME) LIKE '%ESTADO%' "
                    "OR UPPER(RDB$FIELD_NAME) LIKE '%ACEPTA%' "
                    "OR UPPER(RDB$FIELD_NAME) LIKE '%SEGUIM%' "
                    "OR UPPER(RDB$FIELD_NAME) LIKE '%RESULT%') "
                    "ORDER BY RDB$FIELD_POSITION"
                )
            })

        return fixed

    async def _execute_fixed_sqls(
        self, fixed_sqls: List[Dict], result: EpicAnalysisResult, phase: PhaseResult
    ) -> None:
        for i, sql_dict in enumerate(fixed_sqls):
            sql = sql_dict.get("sql", "")
            objetivo = sql_dict.get("objetivo", f"SQL fijo {i+1}")
            if not sql:
                continue
            if self.sql_normalizer:
                try:
                    sql, _ = self.sql_normalizer.normalize(sql)
                except Exception:
                    pass
            sql_result, sql_error = await self._execute_with_retry(sql, objetivo)
            entry = {"objetivo": objetivo, "sql": sql, "rows": 0, "data": [], "error": None}
            if sql_result is not None:
                entry["rows"] = len(sql_result)
                entry["data"] = sql_result[:MAX_ROWS_IN_SUMMARY]
                result.sql_queries.append(entry)
            else:
                entry["error"] = sql_error
                result.sql_queries.append(entry)
            phase.sub_phases.append(SubPhaseResult(
                f"3.fijo.{i+1} {objetivo[:40]}", sql_result is not None, entry
            ))

    def _extract_objetivo(self, sql_raw: str, index: int) -> str:
        m = re.search(r'--\s*\[OBJETIVO:\s*(.*?)\]', sql_raw)
        return m.group(1).strip() if m else f"Consulta {index+1}"

    async def _execute_with_retry(self, sql: str, objetivo: str) -> Tuple[Optional[List], Optional[str]]:
        last_error = None
        for attempt in range(2):
            try:
                return self._safe_sql(sql), None
            except Exception as e:
                last_error = str(e)
                if attempt == 0 and self.sql_corrector:
                    try:
                        fixed = await self._ai_fix_sql(sql, last_error)
                        if fixed and fixed != sql:
                            sql = fixed
                    except Exception:
                        pass
        return None, last_error

    # ─── Resumen progresivo ───────────────────────────────────────────────────

    async def _progressive_summary(self, result: EpicAnalysisResult, question: str) -> None:
        """Resume los datos acumulados cuando superan el presupuesto de tokens."""
        full_data = self._fmt_investigation(result.sql_queries)
        tokens_used = self.budget.count(full_data)
        logger.info(f"[PROGRESSIVE SUMMARY] {tokens_used} tokens → resumiendo...")

        try:
            system = (
                "Resume estos resultados SQL de forma ULTRA-COMPACTA "
                "manteniendo TODOS los números clave, tendencias y anomalías. "
                "≤ 30% del tamaño original. Formato: bullet points con datos exactos."
            )
            data_to_summarize = self.budget.truncate_to_fit(full_data, system, question)
            summary, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system,
                user_message=f"PREGUNTA: {question}\n\nDATOS:\n{data_to_summarize}",
                preferred_model_id="jddcia-qwen3-30b"
            )
            if summary:
                summary_tokens = self.budget.count(summary)
                if summary_tokens > self.budget.available * 0.4:
                    filepath = self._dump_to_file(summary, result)
                    result.sql_queries = [{
                        "objetivo": "RESUMEN PARCIAL (volcado a disco)",
                        "sql": "", "rows": len(result.sql_queries),
                        "data": [{"resumen_file": filepath, "preview": summary[:500]}],
                        "error": None
                    }]
                else:
                    result.sql_queries = [{
                        "objetivo": "RESUMEN COMPRIMIDO",
                        "sql": "", "rows": len(result.sql_queries),
                        "data": [{"resumen": summary}], "error": None
                    }]
        except Exception as e:
            logger.error(f"[PROGRESSIVE SUMMARY] Error: {e}")

    def _dump_to_file(self, content: str, result: EpicAnalysisResult) -> str:
        try:
            fd, filepath = tempfile.mkstemp(prefix="devia_deep_", suffix=".txt")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(f"# Resumen — {result.question}\n\n{content}")
            result.partial_summary_files.append(filepath)
            return filepath
        except Exception as e:
            logger.error(f"[DUMP TO FILE] {e}")
            return ""

    def _cleanup_partial_files(self, result: EpicAnalysisResult) -> None:
        for filepath in result.partial_summary_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 4: ANÁLISIS CRÍTICO PROFUNDO
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase4_analyze(self, question: str, result: EpicAnalysisResult, cfg: Dict) -> PhaseResult:
        phase = PhaseResult(phase_id="4", phase_name="Análisis Crítico Profundo", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 4: ANÁLISIS CRÍTICO PROFUNDO ═══")

        if not result.sql_queries:
            phase.success = False
            phase.error = "Sin datos de investigación"
            return phase

        from datetime import datetime
        anio_actual = datetime.now().year
        fecha_actual = datetime.now().strftime("%d/%m/%Y")

        exploration_data = result.phases[1].data if len(result.phases) > 1 else {}
        exploration_summary = self._fmt_exploration(exploration_data)
        data_summary_full = self._fmt_investigation(result.sql_queries)

        system = (
            f"Eres un analista de datos crítico, experto en climatización y Firebird 2.5. "
            f"HOY ES {fecha_actual} (año {anio_actual}). "
            f"Los datos con año {anio_actual} son REALES y ACTUALES, NO futuristas. "
            "Analiza con MÁXIMA PROFUNDIDAD.\n\n"
            "DIMENSIONES OBLIGATORIAS:\n"
            "1. ANOMALÍAS ESTADÍSTICAS: outliers, distribuciones inusuales\n"
            "2. CALIDAD DE DATOS: nulos, duplicados, fechas incoherentes\n"
            "3. CONTEXTO NEGOCIO: 1 instalación = N presupuestos, SAT≠ventas\n"
            "4. LIMITACIONES SQL: LEFT JOINs, COUNT(DISTINCT) vs COUNT(*)\n"
            "5. PATRONES OCULTOS: estacionalidad, concentración\n"
            "6. HIPÓTESIS: causas de tasas bajas, nulos, anomalías\n\n"
            "Responde SOLO JSON:\n"
            '{"warnings":[],"anomalies":[],"data_quality_issues":[],"business_insights":[],'
            '"sql_limitations":[],"hidden_patterns":[],"hypotheses":[],"suggestions":[],'
            '"reliability_score":"alto|medio|bajo","reliability_reason":""}'
        )
        data_summary = self.budget.truncate_to_fit(data_summary_full, system, exploration_summary, question)
        user_msg = (
            f"PREGUNTA: {question}\n\n"
            f"EXPLORACIÓN:\n{exploration_summary}\n\n"
            f"RESULTADOS:\n{data_summary}"
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
                result.warnings = list(dict.fromkeys(result.warnings))
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
                    f"fiabilidad={analysis.get('reliability_score','?')}"
                )
                # Registrar feedback en SIUO para autoaprendizaje
                self._register_siuo_feedback(question, result, analysis)
            else:
                phase.success = False
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 4 error: {e}")
            phase.success = False
            phase.error = str(e)
        return phase

    def _register_siuo_feedback(
        self, question: str, result: EpicAnalysisResult, analysis: Dict
    ) -> None:
        """Registra feedback en el SIUO para mejorar el autoaprendizaje."""
        try:
            # Usa la importación a nivel de módulo para permitir mocking en tests
            retriever = get_context_retriever()
            tables_used = list({
                q.get("sql", "").split("FROM")[-1].split()[0].strip()
                for q in result.sql_queries if q.get("sql") and "FROM" in q.get("sql", "").upper()
            })
            # Considerar correcto si fiabilidad es alta o media
            was_correct = analysis.get("reliability_score", "bajo") in ("alto", "medio")
            sqls_used = " | ".join(q.get("sql", "")[:100] for q in result.sql_queries[:3])
            retriever.register_feedback(
                question=question,
                sql_used=sqls_used,
                was_correct=was_correct,
                tables_used=tables_used,
            )
            logger.info(f"[SIUO] Feedback registrado: correcto={was_correct}, tablas={tables_used}")
        except Exception as e:
            logger.debug(f"[SIUO] No se pudo registrar feedback: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 5: SÍNTESIS ÉPICA
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase5_synthesize(self, question: str, result: EpicAnalysisResult, cfg: Dict) -> PhaseResult:
        phase = PhaseResult(phase_id="5", phase_name="Síntesis Épica", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 5: SÍNTESIS ÉPICA ═══")

        from datetime import datetime
        now = datetime.now()
        fecha_actual = now.strftime("%d/%m/%Y")
        hora_actual = now.strftime("%H:%M")
        anio_actual = now.year

        analysis_data = result.phases[3].data if len(result.phases) > 3 else {}
        data_summary_full = self._fmt_investigation(result.sql_queries)
        warnings_html = self._build_warnings_html(result)

        # ── Construir bloque <details> con contenido real ─────────────────────
        # Se construye AQUÍ (en Python) para garantizar que siempre tenga contenido.
        # La IA NO genera el bloque <details> — solo genera el texto Markdown.
        sqls_details = "\n\n".join(
            f"**{q['objetivo']}** ({q.get('rows', 0)} filas)\n"
            f"```sql\n{q['sql']}\n```"
            + (f"\n⚠️ Error: {q['error']}" if q.get('error') else "")
            for q in result.sql_queries[:8] if q.get("sql")
        )
        reliability_score = analysis_data.get("reliability_score", "?")
        reliability_reason = analysis_data.get("reliability_reason", "")
        limitations = "\n".join(f"• {l}" for l in analysis_data.get("sql_limitations", [])[:5])
        tables_used = list({
            part.strip().split()[0].upper()
            for q in result.sql_queries if q.get("sql") and "FROM" in q.get("sql", "").upper()
            for part in re.split(r'\bFROM\b|\bJOIN\b', q["sql"], flags=re.IGNORECASE)[1:]
            if part.strip()
        })
        details_block = (
            "\n\n<details>\n"
            "<summary>🔬 Ver detalles técnicos</summary>\n\n"
            f"**Fecha del análisis:** {fecha_actual} {hora_actual}\n\n"
            f"**Tablas consultadas:** {', '.join(sorted(tables_used)) if tables_used else 'N/A'}\n\n"
            f"**Fiabilidad:** {reliability_score} — {reliability_reason}\n\n"
            + (f"**Limitaciones SQL:**\n{limitations}\n\n" if limitations else "")
            + f"**Consultas ejecutadas ({len(result.sql_queries)}):**\n\n{sqls_details}\n\n"
            "</details>"
        )

        # ── System prompt SIN bloque <details> — lo añadimos nosotros ────────
        system = (
            f"Eres un analista de datos experto y consultor de negocio. "
            f"HOY ES {fecha_actual} (año {anio_actual}). "
            f"Los datos de la BD son REALES y ACTUALES — si aparece el año {anio_actual}, "
            f"es correcto, NO es futurista.\n\n"
            "Genera una respuesta ÉPICA, COMPLETA y ULTRA-FIABLE.\n\n"
            "ESTRUCTURA OBLIGATORIA (solo Markdown, SIN HTML, SIN <details>):\n"
            "## 📊 Respuesta Principal\n[Datos reales en tabla Markdown.]\n\n"
            "## 🔍 Análisis Crítico\n[Interpretación profunda.]\n\n"
            "## ⚠️ Advertencias y Objeciones\n[Lista Markdown con •]\n\n"
            "## 💡 Contexto de Negocio\n[Perspectiva del sector.]\n\n"
            "## 🚀 Sugerencias y Próximos Pasos\n[Lista numerada.]\n\n"
            "REGLAS CRÍTICAS:\n"
            "• NO inventar datos.\n"
            "• NO generar HTML ni etiquetas <div>, <span>, <details>.\n"
            "• Para presupuestos: 1 instalación = N presupuestos.\n"
            f"• El año {anio_actual} es el año ACTUAL, no futurista.\n"
            "• Incluir tabla por año/serie si hay datos temporales.\n"
        )

        data_summary = self.budget.truncate_to_fit(data_summary_full, system, question)
        w_text = "\n".join(f"• {w}" for w in result.warnings[:8])
        a_text = "\n".join(f"• {a}" for a in result.anomalies[:5])
        i_text = "\n".join(f"• {i}" for i in result.business_insights[:5])
        q_text = "\n".join(f"• {q}" for q in result.data_quality_issues[:5])
        h_text = "\n".join(f"• {h}" for h in analysis_data.get("hypotheses", [])[:4])
        l_text = "\n".join(f"• {l}" for l in analysis_data.get("sql_limitations", [])[:4])
        s_text = "\n".join(f"• {s}" for s in result.suggestions[:5])

        user_msg = (
            f"PREGUNTA: {question}\n\n"
            f"FECHA ACTUAL: {fecha_actual} (año {anio_actual})\n\n"
            f"PROFUNDIDAD: {result.depth.value.upper()}\n\n"
            f"DATOS ({len(result.sql_queries)} consultas):\n{data_summary}\n\n"
            f"ADVERTENCIAS:\n{w_text}\nANOMALÍAS:\n{a_text}\n"
            f"INSIGHTS:\n{i_text}\nCALIDAD:\n{q_text}\n"
            f"HIPÓTESIS:\n{h_text}\nLIMITACIONES:\n{l_text}\n"
            f"SUGERENCIAS:\n{s_text}\n"
            f"FIABILIDAD: {reliability_score} — {reliability_reason}"
        )

        try:
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            if resp:
                # Limpiar cualquier HTML que la IA haya generado en el texto Markdown
                resp_clean = self._strip_html_from_markdown(resp)
                # Combinar: advertencias HTML (si las hay) + respuesta Markdown + detalles técnicos
                final = ""
                if warnings_html:
                    final += warnings_html + "\n\n"
                final += resp_clean + details_block
                result.final_answer = final
                phase.data = result.final_answer
                phase.sub_phases.extend([
                    SubPhaseResult("5.1 Respuesta principal", True, "OK"),
                    SubPhaseResult("5.2 Análisis crítico", True, "OK"),
                    SubPhaseResult("5.3 Advertencias", True, f"{len(result.warnings)}"),
                    SubPhaseResult("5.4 Contexto negocio", True, "OK"),
                    SubPhaseResult("5.5 Sugerencias", True, f"{len(result.suggestions)}"),
                    SubPhaseResult("5.6 Detalles técnicos", True, f"{len(result.sql_queries)} SQLs"),
                ])
                logger.info("[DEEP AGENT] Fase 5 OK")
            else:
                phase.success = False
                result.final_answer = self._emergency_fallback(result)
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 5 error: {e}")
            phase.success = False
            phase.error = str(e)
            result.final_answer = self._emergency_fallback(result)
        return phase

    def _strip_html_from_markdown(self, text: str) -> str:
        """
        Elimina etiquetas HTML del texto Markdown generado por la IA.
        Preserva el bloque <details> si la IA lo generó (lo reemplazamos nosotros).
        Solo elimina <div>, <span>, <p> y similares que no deberían estar en Markdown.
        """
        try:
            # Eliminar bloques <details>...</details> que la IA pueda haber generado
            # (los reemplazamos con nuestro bloque construido en Python)
            text = re.sub(r'<details>.*?</details>', '', text, flags=re.DOTALL | re.IGNORECASE)
            # Eliminar <div ...>...</div> y <span ...>...</span> con su contenido
            # pero PRESERVAR el texto dentro de ellos
            text = re.sub(r'<div[^>]*>(.*?)</div>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n', text, flags=re.DOTALL | re.IGNORECASE)
            # Eliminar etiquetas sueltas que no tienen contenido útil
            text = re.sub(r'<(strong|b)>(.*?)</(strong|b)>', r'**\2**', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<(em|i)>(.*?)</(em|i)>', r'*\2*', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<ul[^>]*>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'</ul>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1\n', text, flags=re.DOTALL | re.IGNORECASE)
            # Limpiar etiquetas HTML residuales
            text = re.sub(r'<[^>]+>', '', text)
            # Limpiar líneas vacías múltiples
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text.strip()
        except Exception:
            return text

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 4b: APRENDIZAJE PERMANENTE (actualiza metadatos SIUO en disco)
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase4b_learn_and_persist(
        self, question: str, phase2_data: Dict,
        result: EpicAnalysisResult, analysis: Dict
    ) -> PhaseResult:
        """
        Fase 4b: Aprendizaje permanente épico.

        Delega en KnowledgeStore (knowledge_store.py) para persistir:
          - Columnas reales (RDB$RELATION_FIELDS) por tabla
          - Conteos reales de registros
          - Distribuciones de TIPO, ESTADOPEND, DOCDESTINO
          - Reglas de negocio descubiertas
          - Patrones SQL exitosos
          - Log append-only de descubrimientos (JSONL)

        Estructura en disco (core/config/knowledge/):
          tables/DOCCAB.json, tables/CLIENTE.json, ...
          index.json, business_rules.json, query_patterns.json
          discoveries_log.jsonl

        GARANTÍA LAN: No se envía ningún dato a internet.
        """
        phase = PhaseResult(phase_id="4b", phase_name="Aprendizaje Permanente", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 4b: APRENDIZAJE PERMANENTE ═══")

        if get_knowledge_store is None:
            logger.warning("[DEEP AGENT] KnowledgeStore no disponible — saltando Fase 4b")
            phase.success = False
            phase.error = "KnowledgeStore no importado"
            return phase

        discoveries: List[str] = []
        store = get_knowledge_store()

        try:
            # ── 1. Persistir metadatos de tablas exploradas en Fase 2 ─────────
            for table, info in phase2_data.items():
                if not isinstance(info, dict):
                    continue

                updates: Dict = {}
                cols = info.get("columns", [])
                cols_source = info.get("columns_source", "unknown")
                total = info.get("total")

                if cols and cols_source == "firebird_rdb":
                    updates["columns_real"] = cols
                    updates["columns_source"] = "firebird_rdb"

                if isinstance(total, int) and total > 0:
                    updates["record_count_real"] = total

                tipo_dist = info.get("tipo_distribution", [])
                if tipo_dist and table == "DOCCAB":
                    tipo_map = {str(r.get("TIPO", "?")): r.get("N", 0) for r in tipo_dist}
                    updates["tipo_distribution"] = tipo_map

                if updates:
                    changed = store.update_table(table, updates)
                    if changed:
                        discoveries.append(f"{table}: metadatos actualizados ({list(updates.keys())})")
                        store.log_discovery("record_count", table, updates, question)

            # ── 2. Extraer conocimiento de los resultados SQL ─────────────────
            for q in result.sql_queries:
                objetivo = q.get("objetivo", "")
                data = q.get("data", [])
                sql = q.get("sql", "")
                rows = q.get("rows", 0)
                if not data or q.get("error"):
                    continue

                # ESTADOPEND en presupuestos
                if "ESTADOPEND" in objetivo and "presupuesto" in objetivo.lower():
                    estadopend_map = {str(r.get("ESTADOPEND", "?")): r.get("N", 0) for r in data}
                    total_pend = sum(estadopend_map.values())
                    nota = (
                        f"ESTADOPEND en presupuestos (TIPO=0): {estadopend_map}. "
                        f"Total={total_pend}. "
                        "Verificar qué valor indica 'aceptado' en el contexto de negocio."
                    )
                    store.update_table("DOCCAB", {
                        "estadopend_distribution": estadopend_map,
                        "_nota_estadopend": nota,
                    })
                    store.log_discovery("estadopend", "DOCCAB", estadopend_map, question)
                    discoveries.append(f"DOCCAB.ESTADOPEND: {estadopend_map}")

                # Columnas de estado en DOCCAB (desde RDB$)
                if "Columnas de DOCCAB" in objetivo and "ESTADO" in objetivo:
                    cols_estado = [
                        r.get("RDB$FIELD_NAME", "").strip()
                        for r in data if r.get("RDB$FIELD_NAME")
                    ]
                    if cols_estado:
                        store.update_table("DOCCAB", {"columns_estado": cols_estado})
                        store.log_discovery("columns_estado", "DOCCAB", cols_estado, question)
                        discoveries.append(f"DOCCAB columnas estado: {cols_estado}")

                # Presupuestos con/sin documento destino
                if "documento destino vinculado" in objetivo.lower() and data:
                    row = data[0]
                    total_p = row.get("TOTAL_PRESUPUESTOS", 0)
                    con_dest = row.get("CON_DESTINO", 0)
                    sin_dest = row.get("SIN_DESTINO", 0)
                    if total_p:
                        pct = round(con_dest / total_p * 100, 1)
                        nota_dest = (
                            f"De {total_p} presupuestos: {con_dest} tienen documento destino "
                            f"({pct}%), {sin_dest} no tienen destino. "
                            "DOCDESTINO puede NO ser el indicador correcto de 'aceptado'."
                        )
                        store.update_table("DOCCAB", {"_nota_docdestino": nota_dest})
                        store.log_discovery("docdestino", "DOCCAB",
                                            {"total": total_p, "con": con_dest, "sin": sin_dest, "pct": pct},
                                            question)
                        discoveries.append(f"DOCCAB→DOCDESTINO: {con_dest}/{total_p} ({pct}%)")
                        # Regla de negocio si la tasa es baja
                        if pct < 30:
                            store.add_business_rule(
                                f"Solo el {pct}% de presupuestos tienen documento destino — "
                                "DOCDESTINO no es indicador fiable de 'aceptado'",
                                table="DOCCAB", confidence="alto"
                            )

                # Distribución por tipo de documento destino
                if "tipo de documento destino" in objetivo.lower():
                    tipo_dest_map = {
                        str(r.get("TIPO_DESTINO", "?")): r.get("N_PRESUPUESTOS", 0)
                        for r in data
                    }
                    if tipo_dest_map:
                        store.update_table("DOCCAB", {"docdestino_tipo_distribution": tipo_dest_map})
                        store.log_discovery("docdestino", "DOCCAB", tipo_dest_map, question)
                        discoveries.append(f"DOCDESTINO tipos: {tipo_dest_map}")

                # Registrar patrón SQL exitoso (solo SQLs con datos reales)
                if sql and rows > 0 and len(sql) > 30:
                    tables_in_sql = list({
                        part.strip().split()[0].upper()
                        for part in re.split(r'\bFROM\b|\bJOIN\b', sql, flags=re.IGNORECASE)[1:]
                        if part.strip()
                    })
                    store.add_query_pattern(
                        intent=objetivo[:100],
                        sql=sql,
                        tables=tables_in_sql,
                        rows_returned=rows,
                        reliability=analysis.get("reliability_score", "medio") if analysis else "medio",
                    )

            # ── 3. Persistir reglas de negocio del análisis ───────────────────
            for insight in result.business_insights[:5]:
                if insight and len(insight) > 15:
                    store.add_business_rule(insight, confidence="medio", source="deep_analysis_ia")

            for anomaly in result.anomalies[:3]:
                if anomaly and len(anomaly) > 15:
                    store.log_discovery("anomaly", None, anomaly, question)

            # ── 4. Log final de la sesión ─────────────────────────────────────
            store.log_discovery("sql_pattern", None, {
                "question": question[:80],
                "sqls_ok": sum(1 for q in result.sql_queries if not q.get("error")),
                "sqls_total": len(result.sql_queries),
                "reliability": analysis.get("reliability_score", "?") if analysis else "?",
                "discoveries": len(discoveries),
            }, question)

            logger.info(f"[DEEP AGENT] ✅ Fase 4b: {len(discoveries)} descubrimientos persistidos")
            for d in discoveries:
                logger.info(f"[DEEP AGENT]   📚 {d}")

            phase.data = {
                "discoveries": discoveries,
                "tables_updated": list(phase2_data.keys()),
                "knowledge_base": store._base,
            }
            phase.sub_phases.extend([
                SubPhaseResult("4b.1 Tablas actualizadas", True, list(phase2_data.keys())),
                SubPhaseResult("4b.2 Descubrimientos", True, discoveries),
                SubPhaseResult("4b.3 Reglas negocio", True, f"{len(result.business_insights)} insights"),
            ])

        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 4b error: {e}", exc_info=True)
            phase.success = False
            phase.error = str(e)

        return phase

    # ─────────────────────────────────────────────────────────────────────────
    # HELPER: Contexto SIUO optimizado
    # ─────────────────────────────────────────────────────────────────────────

    def _get_siuo_context(self, question: str, n_sqls: int) -> str:
        """
        Obtiene el contexto optimizado del SIUO para la pregunta.
        LÍMITE ESTRICTO: máx 3000 tokens para no saturar el modelo LAN.
        Fallback al db_context si el SIUO no está disponible.
        """
        try:
            from backend.modules.db_explorer.context_retriever import get_context_retriever
            retriever = get_context_retriever()
            # LÍMITE ESTRICTO: máx 3000 tokens para no saturar el modelo LAN (Qwen3 30B)
            # El modelo LAN tiene 32K de contexto pero genera timeout con prompts >4K tokens
            max_tokens = min(1500 + n_sqls * 100, 3000)
            context, meta = retriever.get_context(question, max_tokens=max_tokens)
            tables = meta.get("tables_used", [])
            source = meta.get("source", "?")
            logger.info(f"[SIUO] Contexto obtenido: {len(tables)} tablas, fuente={source}, max_tokens={max_tokens}")
            return context
        except Exception as e:
            logger.warning(f"[SIUO] Fallback a db_context: {e}")
            # Truncar db_context a 2000 chars para no saturar el modelo
            return self.db_context[:2000] if self.db_context else ""
