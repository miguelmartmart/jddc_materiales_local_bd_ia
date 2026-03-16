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

        system = self._build_phase3_system(schema_for_prompt, exploration_summary, n_sqls)
        user_msg = (
            f"PREGUNTA: {question}\n\n"
            f"SUB-PREGUNTAS: {sub_questions}\n\n"
            f"POSIBLES PROBLEMAS: {potential_issues}\n\n"
            f"CONTEXTO: {phase1_data.get('business_context', '')}"
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

    def _build_phase3_system(self, schema: str, exploration: str, n_sqls: int) -> str:
        return (
            "Eres un experto en SQL Firebird 2.5. Genera múltiples consultas SQL para investigar "
            "una pregunta desde TODOS los ángulos posibles.\n\n"
            f"ESQUEMA OPTIMIZADO (SIUO):\n{schema}\n\n"
            f"EXPLORACIÓN REAL DE TABLAS:\n{exploration}\n\n"
            "REGLAS CRÍTICAS FIREBIRD 2.5:\n"
            "• FIRST N en lugar de LIMIT/TOP\n"
            "• UPPER(col) LIKE UPPER('%x%') para texto\n"
            "• DOCCAB.TIPO: 0=presupuesto, 13=factura, 11=albaran, 12=pedido, 2=SAT\n"
            "• NO usar ROUND() → CAST(x AS NUMERIC(15,2))\n"
            "• BLOB (DESCRIPCION) → NO en GROUP BY\n"
            "• DOCDESTINO vincula documentos origen→destino\n"
            "• DOCLIN no tiene FECHA propia → JOIN DOCCAB para obtener FECHA\n\n"
            f"Genera EXACTAMENTE {n_sqls} consultas SQL. Cada una precedida por:\n"
            "-- [OBJETIVO: descripción clara]\n\n"
            "ÁNGULOS OBLIGATORIOS:\n"
            "1. Consulta principal\n2. Calidad (nulos, vacíos)\n3. Duplicados\n"
            "4. Distribución temporal (año/mes/serie) — SIEMPRE\n"
            "5. Por cliente/agente/categoría\n6. Outliers\n7. Totales/promedios\n"
            "8. Cruce con tabla relacionada\n9. Instalaciones únicas vs presupuestos\n"
            "10-12+. Análisis adicionales\n\n"
            "Si necesitas más SQLs: <!-- NECESITO_MAS_SQLS: N -->\n\n"
            "Formato: ```sql\n-- [OBJETIVO: ...]\nSELECT ...\n```\n"
        )

    def _build_fixed_sqls(self, question: str, phase2_data: Dict) -> List[Dict]:
        """SQLs fijos que SIEMPRE se incluyen según el contexto de la pregunta."""
        fixed = []
        msg = question.lower()
        doccab_info = phase2_data.get("DOCCAB", {})
        has_serie = doccab_info.get("has_serie", False)
        has_codigoobra = doccab_info.get("has_codigoobra", False)

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

        exploration_data = result.phases[1].data if len(result.phases) > 1 else {}
        exploration_summary = self._fmt_exploration(exploration_data)
        data_summary_full = self._fmt_investigation(result.sql_queries)

        system = (
            "Eres un analista de datos crítico, experto en climatización y Firebird 2.5. "
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

        analysis_data = result.phases[3].data if len(result.phases) > 3 else {}
        data_summary_full = self._fmt_investigation(result.sql_queries)
        warnings_html = self._build_warnings_html(result)

        system = (
            "Eres un analista de datos experto y consultor de negocio. "
            "Genera una respuesta ÉPICA, COMPLETA y ULTRA-FIABLE.\n\n"
            "ESTRUCTURA OBLIGATORIA:\n"
            "## 📊 Respuesta Principal\n[Datos reales en tabla Markdown.]\n\n"
            "## 🔍 Análisis Crítico\n[Interpretación profunda.]\n\n"
            "## ⚠️ Advertencias y Objeciones\n[Advertencias importantes.]\n\n"
            "## 💡 Contexto de Negocio\n[Perspectiva del sector.]\n\n"
            "## 🚀 Sugerencias y Próximos Pasos\n[Acciones recomendadas.]\n\n"
            "<details>\n<summary>🔬 Ver detalles técnicos</summary>\n"
            "[SQLs, tablas, fiabilidad, limitaciones]\n</details>\n\n"
            "REGLAS:\n"
            "• NO inventar datos.\n"
            "• Para presupuestos: 1 instalación = N presupuestos.\n"
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
        sqls_text = "\n".join(
            f"```sql\n-- {q['objetivo']}\n{q['sql']}\n```"
            for q in result.sql_queries[:6] if q.get("sql")
        )

        user_msg = (
            f"PREGUNTA: {question}\n\nPROFUNDIDAD: {result.depth.value.upper()}\n\n"
            f"DATOS ({len(result.sql_queries)} consultas):\n{data_summary}\n\n"
            f"ADVERTENCIAS:\n{w_text}\nANOMALÍAS:\n{a_text}\n"
            f"INSIGHTS:\n{i_text}\nCALIDAD:\n{q_text}\n"
            f"HIPÓTESIS:\n{h_text}\nLIMITACIONES:\n{l_text}\n"
            f"SUGERENCIAS:\n{s_text}\n"
            f"FIABILIDAD: {analysis_data.get('reliability_score','?')} — "
            f"{analysis_data.get('reliability_reason','')}\n\n"
            f"SQLs:\n{sqls_text}"
        )

        try:
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            if resp:
                result.final_answer = (warnings_html + "\n\n" + resp) if warnings_html else resp
                phase.data = result.final_answer
                phase.sub_phases.extend([
                    SubPhaseResult("5.1 Respuesta principal", True, "OK"),
                    SubPhaseResult("5.2 Análisis crítico", True, "OK"),
                    SubPhaseResult("5.3 Advertencias", True, f"{len(result.warnings)}"),
                    SubPhaseResult("5.4 Contexto negocio", True, "OK"),
                    SubPhaseResult("5.5 Sugerencias", True, f"{len(result.suggestions)}"),
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

    # ─────────────────────────────────────────────────────────────────────────
    # HELPER: Contexto SIUO optimizado
    # ─────────────────────────────────────────────────────────────────────────

    def _get_siuo_context(self, question: str, n_sqls: int) -> str:
        """
        Obtiene el contexto optimizado del SIUO para la pregunta.
        Usa más tokens si hay más SQLs disponibles (más contexto = mejores SQLs).
        Fallback al db_context si el SIUO no está disponible.
        """
        try:
            from backend.modules.db_explorer.context_retriever import get_context_retriever
            retriever = get_context_retriever()
            # Más SQLs → más tokens de contexto (hasta 8000)
            max_tokens = min(2000 + n_sqls * 500, 8000)
            context, meta = retriever.get_context(question, max_tokens=max_tokens)
            tables = meta.get("tables_used", [])
            source = meta.get("source", "?")
            logger.info(f"[SIUO] Contexto obtenido: {len(tables)} tablas, fuente={source}")
            return context
        except Exception as e:
            logger.warning(f"[SIUO] Fallback a db_context: {e}")
            return self.db_context
