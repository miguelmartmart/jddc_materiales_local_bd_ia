"""
phase3.py — Fase 3 y Fase 3b del DeepAnalysisAgent.

  Fase 3:  Investigación multi-angular (SQLs dinámicos + fijos, expansión, resumen progresivo)
  Fase 3b: Resolución activa de inconsistencias detectadas en Fase 4

Los SQLs fijos y de resolución están en:
  → phase3_sqls.py (Phase3SqlsMixin)

Integración con SIUO:
  - Usa get_context_retriever() para contexto jerárquico optimizado
  - Usa get_knowledge_store() para patrones conocidos y columnas cacheadas
"""

import logging
import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple

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
from backend.modules.chat.deep_analysis.phase3_sqls import Phase3SqlsMixin

logger = logging.getLogger(__name__)


class Phase3Mixin(Phase3SqlsMixin):
    """
    Mixin con las fases 3 y 3b del agente.
    Hereda Phase3SqlsMixin para _build_fixed_sqls y _build_resolution_sqls.
    Requiere: self.orchestrator, self.budget, self.db_context,
              self.sql_normalizer, self.sql_corrector,
              self._safe_sql(), self._parse_json(), self._ai_fix_sql(),
              self._fmt_exploration(), self._fmt_investigation()
    """

    @staticmethod
    def _detect_incomplete_sql(sql: str) -> str:
        """
        Detecta SQL claramente incompleto/truncado antes de enviarlo al motor SQLite.
        Devuelve una cadena descriptiva del problema, o '' si el SQL parece correcto.
        """
        import re as _re
        s = sql.strip()
        if not s:
            return "vacío"
        # Paréntesis desbalanceados
        if s.count('(') != s.count(')'):
            return "paréntesis desbalanceados"
        # String literal no cerrado: número impar de comillas simples sin escapar
        # (excluir '\'  y '' que son escape/empty en SQL)
        stripped_escaped = _re.sub(r"''", '', s)  # quitar empty strings ''
        # contar comillas simples que no van precedidas de \
        single_quotes = len(_re.findall(r"(?<!\\)'", stripped_escaped))
        if single_quotes % 2 != 0:
            return "string no cerrado (comillas impares)"
        # SQL demasiado corto para ser válido
        if len(s) < 10:
            return "SQL demasiado corto"
        # SELECT sin FROM (excepto SELECT 1, SELECT COUNT sin tabla, etc.)
        upper = s.upper()
        if upper.startswith('SELECT') and 'FROM' not in upper and 'VALUES' not in upper:
            # Permitir SELECT sin FROM si es expresión simple (SELECT 1, SELECT 'a', etc.)
            # pero rechazar si parece truncado (tiene WHERE, GROUP BY, etc. sin FROM)
            if any(k in upper for k in ('WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'JOIN')):
                return "SELECT con cláusulas pero sin FROM"
        return ""

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

        fixed_sqls = self._build_fixed_sqls(question, phase2_data)
        siuo_context = self._get_siuo_context(question, n_sqls)
        schema_for_prompt = self.budget.truncate_to_fit(siuo_context, exploration_summary, question)

        sub_q_str = "; ".join(str(q) for q in sub_questions[:3])
        issues_str = "; ".join(str(p) for p in potential_issues[:2])
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
            result.ai_unavailable = True
            await self._execute_fixed_sqls(fixed_sqls, result, phase)
            phase.success = len(result.sql_queries) > 0
            return phase

        if not response or not isinstance(response, str):
            logger.warning("[DEEP AGENT] Fase 3: respuesta IA vacía — usando solo SQLs fijos")
            result.ai_unavailable = True
            await self._execute_fixed_sqls(fixed_sqls, result, phase)
            phase.success = len(result.sql_queries) > 0
            return phase

        # Expansión dinámica si la IA pide más SQLs
        extra_match = re.search(r'<!--\s*NECESITO_MAS_SQLS:\s*(\d+)\s*-->', response)
        if extra_match:
            extra_needed = int(extra_match.group(1))
            new_max = min(n_sqls + extra_needed, MAX_SQLS_ABSOLUTE)
            if new_max > n_sqls:
                logger.info(f"[DEEP AGENT] IA solicita {extra_needed} SQLs adicionales → máximo: {new_max}")
                cfg["max_sqls"] = new_max
                n_sqls = new_max

        sql_blocks = re.findall(r'```sql\s*(.*?)```', response, re.DOTALL | re.IGNORECASE)
        if not sql_blocks:
            sql_blocks = [l.strip() for l in response.split('\n') if l.strip().upper().startswith('SELECT')]

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

            # Detectar SQL claramente incompleto antes de enviarlo al motor
            _sql_incomplete_reason = self._detect_incomplete_sql(sql)
            if _sql_incomplete_reason:
                logger.warning(
                    f"[DEEP AGENT] SQL {i+1} incompleto ({_sql_incomplete_reason}) — omitiendo"
                )
                entry = {"objetivo": objetivo, "sql": sql, "rows": 0, "data": [],
                         "error": f"SQL incompleto ({_sql_incomplete_reason})"}
                result.sql_queries.append(entry)
                phase.sub_phases.append(SubPhaseResult(
                    f"3.{i+1} {objetivo[:40]}", False, entry
                ))
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
            else:
                entry["error"] = sql_error
                result.sql_queries.append(entry)

            phase.sub_phases.append(SubPhaseResult(
                f"3.{i+1} {objetivo[:40]}", sql_result is not None, entry
            ))

            inv_text = self._fmt_investigation(result.sql_queries)
            if self.budget.usage_pct(inv_text) > SUMMARY_THRESHOLD:
                await self._progressive_summary(result, question)

        phase.success = executed_ok > 0
        phase.data = result.sql_queries
        logger.info(f"[DEEP AGENT] Fase 3 OK: {executed_ok}/{len(all_blocks)} SQLs exitosos")
        return phase

    def _build_phase3_system(
        self, schema: str, exploration: str, n_sqls: int,
        lan_mode: bool = False, known_patterns_text: str = ""
    ) -> str:
        # Detectar si el simulador está activo para adaptar la sintaxis SQL
        _sim_active = False
        try:
            from backend.modules.db_simulator.manager import simulator_manager as _sm
            _sim_active = _sm.is_enabled()
        except Exception:
            pass

        # Mapeo de TIPO verificado con el usuario (2026-06-25):
        # 0=presupuesto_cliente, 1=pedido_cliente, 2=albarán_cliente, 3=factura_cliente
        # 10=presupuesto_prov, 11=pedido_prov, 12=albarán_prov, 13=factura_prov
        # 21=mov.almacén, 31=recuento, 51=certificación, 52=producción, 61=cert.subcontrata
        # En DOCCAB, todos los tipos pueden tener CODCLIENTE (compras vinculadas a proyecto cliente)
        _tipo_rules = (
            "• DOCCAB.TIPO (VERIFICADO): "
            "0=presupuesto_cliente | 1=pedido_cliente | 2=albarán_cliente | 3=factura_cliente | "
            "10=presupuesto_prov | 11=pedido_prov | 12=albarán_prov | 13=factura_prov | "
            "21=mov.almacén | 31=recuento | 51=certificación\n"
            "• CRÍTICO — etiquetas obligatorias: TIPO=0→'Presupuesto', TIPO=2→'Albarán cliente', "
            "TIPO=3→'Factura cliente', TIPO=11→'Pedido proveedor', TIPO=13→'Factura proveedor'. "
            "NUNCA llames 'Albarán' a TIPO=0 (es Presupuesto). NUNCA omitas tipos del resultado.\n"
            "• Albaranes de cliente pendientes de facturar → WHERE TIPO=2 AND CODIGO NOT IN "
            "(SELECT CODDOCUMENTO FROM DOCDESTINO WHERE ...)\n"
            "• TODOS los tipos tienen CODCLIENTE: las compras (11,12,13) se vinculan al cliente-proyecto\n"
        )

        if _sim_active:
            # Simulador SQLite: usar LIMIT N (SQLite no soporta FIRST N)
            rules = (
                "REGLAS SQL (modo simulador SQLite):\n"
                "• LIMIT N al final de la query (NO FIRST N, NO TOP N)\n"
                "• Usar INNER JOIN cuando la relación es obligatoria (evita filas nulas)\n"
                + _tipo_rules
                + "• SUM(), COUNT(), AVG() funcionan igual que en Firebird\n"
                "• DOCLIN sin FECHA → JOIN DOCCAB ON DOCLIN.CODDOCUMENTO=DOCCAB.CODIGO\n"
                "• Filtrar siempre por DOCCAB.TIPO para evitar mezclar tipos de documento\n"
            )
        else:
            # Base de datos real Firebird 2.5
            rules = (
                "REGLAS FIREBIRD 2.5:\n"
                "• FIRST N (no LIMIT/TOP) • UPPER(col) LIKE UPPER('%x%')\n"
                + _tipo_rules
                + "• NO ROUND() → CAST(x AS NUMERIC(15,2)) • BLOB→NO GROUP BY\n"
                "• DOCDESTINO vincula origen→destino • DOCLIN sin FECHA→JOIN DOCCAB\n"
                "• Filtrar siempre por DOCCAB.TIPO para evitar mezclar tipos de documento\n"
            )
        if lan_mode:
            known_section = (
                f"\nSQLs YA CUBIERTOS (no repetir):\n{known_patterns_text}\n"
                if known_patterns_text else ""
            )
            return (
                f"Experto SQL Firebird 2.5. Genera {n_sqls} consultas para investigar la pregunta.\n\n"
                f"ESQUEMA:\n{schema}\n\nEXPLORACIÓN:\n{exploration}\n\n"
                f"{rules}{known_section}"
                f"Genera EXACTAMENTE {n_sqls} SQLs. Cada uno: -- [OBJETIVO: ...] + SELECT.\n"
                "Ángulos: principal, calidad, duplicados, temporal(año/serie), "
                "por cliente/agente, outliers, totales, cruce tablas, instalaciones únicas.\n"
                "Si necesitas más: <!-- NECESITO_MAS_SQLS: N -->\n"
                "Formato: ```sql\n-- [OBJETIVO: ...]\nSELECT ...\n```\n"
            )
        else:
            known_section = (
                f"\nPATRONES YA CONOCIDOS (no repetir):\n{known_patterns_text}\n"
                if known_patterns_text else ""
            )
            return (
                "Eres un experto en SQL Firebird 2.5. Genera múltiples consultas SQL para investigar "
                "una pregunta desde TODOS los ángulos posibles.\n\n"
                f"ESQUEMA OPTIMIZADO (SIUO):\n{schema}\n\n"
                f"EXPLORACIÓN REAL DE TABLAS:\n{exploration}\n\n"
                f"{rules}\n{known_section}"
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
        try:
            if get_knowledge_store is None:
                return ""
            store = get_knowledge_store()
            keywords = [w.lower() for w in question.split() if len(w) > 4]
            patterns = store.get_patterns_for_intent(keywords)
            if not patterns:
                return ""
            lines = []
            for p in patterns[:4]:
                intent = p.get("intent", "?")[:60]
                sql_preview = p.get("sql", "")[:120].replace("\n", " ")
                rows = p.get("rows_returned", "?")
                lines.append(f"• [{intent}] → {sql_preview}... ({rows} filas)")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _get_known_patterns_text: {e}")
            return ""

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

    async def _execute_with_retry(
        self, sql: str, objetivo: str
    ) -> Tuple[Optional[List], Optional[str]]:
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

    async def _progressive_summary(self, result: EpicAnalysisResult, question: str) -> None:
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

    def _get_siuo_context(self, question: str, n_sqls: int) -> str:
        try:
            from backend.modules.db_explorer.context_retriever import get_context_retriever
            retriever = get_context_retriever()
            max_tokens = min(1500 + n_sqls * 100, 3000)
            context, meta = retriever.get_context(question, max_tokens=max_tokens)
            tables = meta.get("tables_used", [])
            source = meta.get("source", "?")
            logger.info(f"[SIUO] Contexto: {len(tables)} tablas, fuente={source}")
            return context
        except Exception as e:
            logger.warning(f"[SIUO] Fallback a db_context: {e}")
            return self.db_context[:2000] if self.db_context else ""

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 3b: RESOLUCIÓN DE INCONSISTENCIAS
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase3b_resolve_inconsistencies(
        self, question: str, result: EpicAnalysisResult, cfg: Dict
    ) -> PhaseResult:
        phase = PhaseResult(phase_id="3b", phase_name="Resolución de Inconsistencias", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 3b: RESOLUCIÓN DE INCONSISTENCIAS ═══")

        from datetime import datetime
        anio_actual = datetime.now().year

        all_issues = result.anomalies[:6] + result.warnings[:6]
        if not all_issues:
            phase.data = {"resolution_sqls": 0, "reason": "sin inconsistencias"}
            return phase

        logger.info(f"[DEEP AGENT] Fase 3b: {len(all_issues)} inconsistencias a resolver")
        resolution_sqls = self._build_resolution_sqls(all_issues, question, anio_actual)

        if not resolution_sqls:
            resolution_sqls = await self._ai_generate_resolution_sqls(
                question, all_issues, result, anio_actual, cfg
            )

        executed_ok = 0
        for i, sql_dict in enumerate(resolution_sqls[:6]):
            sql = sql_dict.get("sql", "")
            objetivo = sql_dict.get("objetivo", f"Resolución {i+1}")
            if not sql:
                continue
            _sql3b_reason = self._detect_incomplete_sql(sql)
            if _sql3b_reason:
                logger.warning(
                    f"[DEEP AGENT] 3b SQL {i+1} incompleto ({_sql3b_reason}) — omitiendo"
                )
                entry = {"objetivo": objetivo, "sql": sql, "rows": 0, "data": [],
                         "error": f"SQL incompleto ({_sql3b_reason})", "is_resolution": True}
                result.sql_queries.append(entry)
                phase.sub_phases.append(SubPhaseResult(
                    f"3b.{i+1} {objetivo[:40]}", False, entry
                ))
                continue
            if self.sql_normalizer:
                try:
                    sql, _ = self.sql_normalizer.normalize(sql)
                except Exception:
                    pass
            sql_result, sql_error = await self._execute_with_retry(sql, objetivo)
            entry = {"objetivo": objetivo, "sql": sql, "rows": 0, "data": [], "error": None,
                     "is_resolution": True}
            if sql_result is not None:
                entry["rows"] = len(sql_result)
                entry["data"] = sql_result[:MAX_ROWS_IN_SUMMARY]
                result.sql_queries.append(entry)
                executed_ok += 1
                if sql_result:
                    result.business_insights.append(
                        f"[RESOLUCIÓN] {objetivo}: {len(sql_result)} filas encontradas"
                    )
            else:
                entry["error"] = sql_error
                result.sql_queries.append(entry)
            phase.sub_phases.append(SubPhaseResult(
                f"3b.{i+1} {objetivo[:40]}", sql_result is not None, entry
            ))

        phase.success = executed_ok > 0
        phase.data = {
            "resolution_sqls": len(resolution_sqls),
            "executed_ok": executed_ok,
            "issues_addressed": len(all_issues),
        }
        return phase

    async def _ai_generate_resolution_sqls(
        self, question: str, issues: List, result: EpicAnalysisResult,
        anio_actual: int, cfg: Dict
    ) -> List[Dict]:
        try:
            issues_text = "\n".join(f"• {i}" for i in issues[:5])
            data_preview = self._fmt_investigation(result.sql_queries[:3])
            system = (
                f"Eres un experto en Firebird 2.5. HOY ES {anio_actual}. "
                "Genera SQLs para RESOLVER (no solo reportar) las inconsistencias. "
                "Máximo 4 bloques ```sql ... ``` con -- [OBJETIVO: ...] antes de cada uno."
            )
            user_msg = (
                f"PREGUNTA: {question}\n\nINCONSISTENCIAS:\n{issues_text}\n\n"
                f"DATOS ACTUALES:\n{data_preview[:1000]}"
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            if not resp:
                return []
            sql_blocks = re.findall(r'```sql\s*(.*?)```', resp, re.DOTALL | re.IGNORECASE)
            sqls = []
            for i, block in enumerate(sql_blocks[:4]):
                objetivo = self._extract_objetivo(block, i)
                sql = re.sub(r'--\s*\[OBJETIVO:[^\]]*\]', '', block).strip()
                if sql:
                    sqls.append({"objetivo": objetivo, "sql": sql})
            return sqls
        except Exception as e:
            logger.warning(f"[DEEP AGENT] _ai_generate_resolution_sqls: {e}")
            return []
