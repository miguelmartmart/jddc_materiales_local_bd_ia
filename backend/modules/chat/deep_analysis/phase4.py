"""
phase4.py — Fases 4 y 4b del DeepAnalysisAgent.

  Fase 4:  Análisis crítico profundo (anomalías, calidad, contexto, limitaciones, hipótesis)
  Fase 4b: Aprendizaje permanente (KnowledgeStore — columnas, conteos, distribuciones, reglas)

Integración con SIUO:
  - Registra feedback en siuo_query_log.json tras cada análisis (Fase 4)
  - Persiste columnas, conteos y distribuciones en KnowledgeStore (Fase 4b)
"""

import logging
import re
from typing import Dict, List

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
)

logger = logging.getLogger(__name__)


class Phase4Mixin:
    """
    Mixin con las fases 4 y 4b del agente.
    Requiere: self.orchestrator, self.budget,
              self._parse_json(), self._fmt_exploration(), self._fmt_investigation()
    """

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 4: ANÁLISIS CRÍTICO PROFUNDO
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase4_analyze(
        self, question: str, result: EpicAnalysisResult, cfg: Dict
    ) -> PhaseResult:
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
            "3. INCONSISTENCIAS ESTRUCTURALES:\n"
            "   - Datos en columnas incorrectas\n"
            "   - Columnas con contenido MIXTO\n"
            "   - Registros con estructura HETEROGÉNEA\n"
            "4. CONTEXTO NEGOCIO: 1 instalación = N presupuestos, SAT≠ventas\n"
            "5. LIMITACIONES SQL: LEFT JOINs, COUNT(DISTINCT) vs COUNT(*)\n"
            "6. PATRONES OCULTOS: estacionalidad, concentración\n"
            "7. HIPÓTESIS: causas de tasas bajas, nulos, anomalías\n\n"
            "Responde SOLO JSON:\n"
            '{"warnings":[],"anomalies":[],"data_quality_issues":[],'
            '"structural_issues":[],"business_insights":[],'
            '"sql_limitations":[],"hidden_patterns":[],"hypotheses":[],"suggestions":[],'
            '"reliability_score":"alto","reliability_reason":"motivo en una frase"}\n'
            'IMPORTANTE: reliability_score DEBE ser exactamente una de estas 3 opciones: "alto", "medio" o "bajo".'
        )
        data_summary = self.budget.truncate_to_fit(
            data_summary_full, system, exploration_summary, question
        )
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
                # Normalizar reliability_score si el modelo devolvió valor no esperado
                rs = analysis.get("reliability_score", "")
                if rs not in ("alto", "medio", "bajo"):
                    # Intentar extraer de texto libre ("confiabilidad media" → "medio")
                    rs_lower = str(rs).lower()
                    if "alto" in rs_lower or "high" in rs_lower:
                        analysis["reliability_score"] = "alto"
                    elif "bajo" in rs_lower or "low" in rs_lower:
                        analysis["reliability_score"] = "bajo"
                    else:
                        # Fallback determinista: calcular por ratio de queries exitosas
                        total = len(result.sql_queries)
                        ok = sum(1 for q in result.sql_queries if not q.get("error") and q.get("rows", 0) > 0)
                        ratio = ok / total if total > 0 else 0
                        analysis["reliability_score"] = "alto" if ratio >= 0.7 else "medio" if ratio >= 0.4 else "bajo"
                        analysis["reliability_reason"] = f"Calculado: {ok}/{total} consultas exitosas"

            # ── Detección determinista de anomalías (independiente de la IA) ──────
            # Detecta resultados sospechosamente bajos comparando consultas del mismo tipo.
            # Esto garantiza que phase 3b siempre investigue cuando hay datos raros,
            # incluso si la IA no los detecta como anomalías.
            self._detect_count_anomalies(result)

            if analysis:
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
                self._register_siuo_feedback(question, result, analysis)
            else:
                phase.success = False
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 4 error: {e}")
            phase.success = False
            phase.error = str(e)
        return phase

    def _detect_count_anomalies(self, result: EpicAnalysisResult) -> None:
        """
        Detección DETERMINISTA de anomalías en conteos SQL.

        REGLA CLAVE: Solo compara valores del MISMO tipo semántico.
        - Conteos (N, COUNT, NUMERO_*) se comparan entre sí
        - Importes (TOTAL_EUR, IMPORTE, SUMA) se comparan entre sí
        - NUNCA se compara un conteo con un importe (evita falsos positivos)

        Cuando detecta una anomalía real, la añade a result.anomalies y result.warnings
        para que phase 3b la investigue automáticamente.
        """
        if not result.sql_queries:
            return

        # Palabras clave de CONTEOS (enteros, unidades)
        _COUNT_KEYS = {'COUNT', 'N_', 'NUMERO_', 'NUM_', 'CANTIDAD', 'TOTAL_DOCS',
                       'N_FACTURAS', 'N_DOCS', 'N_PRESUPUESTOS', 'NUMERO_FACTURAS',
                       'NUMERO_DOCS', 'NUMERO_CLIENTES', 'NUMERO_ARTICULOS'}
        # Palabras clave de IMPORTES (decimales, euros)
        _AMOUNT_KEYS = {'TOTAL_EUR', 'IMPORTE', 'SUMA', 'TOTAL_IMPORTE', 'PROMEDIO',
                        'MEDIA', 'PRECIO', 'COSTE', 'FACTURACION', 'TOTAL_FACTURA',
                        'TOTAL_EUR', 'PROMEDIO_EUR', 'MEDIA_EUR', 'TOTAL_FINAL'}

        def _is_count_col(col: str) -> bool:
            cu = col.upper()
            return any(k in cu for k in _COUNT_KEYS)

        def _is_amount_col(col: str) -> bool:
            cu = col.upper()
            return any(k in cu for k in _AMOUNT_KEYS)

        # Recopilar conteos y importes por separado
        counts: List[Dict] = []
        for q in result.sql_queries:
            if q.get("error") or not q.get("data"):
                continue
            data = q.get("data", [])
            objetivo = q.get("objetivo", "")
            rows = q.get("rows", 0)

            for row in data[:3]:
                for col, val in row.items():
                    if not isinstance(val, (int, float)) or val < 0:
                        continue
                    col_upper = col.upper()
                    # Solo incluir si es claramente un conteo (no un importe)
                    if _is_count_col(col) and not _is_amount_col(col):
                        # Verificar que el valor parece un conteo (entero o casi entero)
                        if isinstance(val, float) and val > 1000:
                            continue  # Probablemente un importe, no un conteo
                        counts.append({
                            "objetivo": objetivo,
                            "col": col,
                            "val": val,
                            "rows": rows,
                        })

        if len(counts) < 2:
            return

        # Encontrar el conteo máximo de referencia (solo entre conteos reales)
        max_count = max(c["val"] for c in counts if c["val"] > 0) if counts else 0
        if max_count <= 1:
            return

        # Detectar conteos sospechosamente bajos (< 5% del máximo)
        # Solo alertar si la diferencia es significativa Y el valor es pequeño en términos absolutos
        threshold = max(2, max_count * 0.05)
        for c in counts:
            val = c["val"]
            # Solo alertar si: val es pequeño, max es grande, y la diferencia es real
            if 0 < val <= threshold and max_count > 10 and (max_count / max(val, 1)) > 5:
                anomaly_msg = (
                    f"⚠️ ANOMALÍA: '{c['objetivo']}' devuelve {int(val)} registro(s) "
                    f"pero el máximo conocido es {int(max_count)}. "
                    f"Posible filtro de fecha/tipo incorrecto o datos incompletos."
                )
                if anomaly_msg not in result.anomalies:
                    result.anomalies.append(anomaly_msg)
                    result.warnings.append(anomaly_msg)
                    logger.warning(
                        f"[DEEP AGENT] 🔍 Anomalía detectada: {c['objetivo']} → {val} "
                        f"(máx={max_count}, umbral={threshold:.1f})"
                    )

        # Detectar si hay consultas con 0 resultados cuando debería haber datos
        zero_results = [q for q in result.sql_queries if q.get("rows", 0) == 0 and not q.get("error")]
        if zero_results and max_count > 5:
            for q in zero_results[:3]:
                objetivo = q.get("objetivo", "")
                # Solo alertar si el objetivo sugiere que debería haber datos
                if any(k in objetivo.lower() for k in [
                    'factura', 'presupuesto', 'albaran', 'pedido', 'cliente', 'articulo'
                ]):
                    anomaly_msg = (
                        f"⚠️ ANOMALÍA: '{objetivo}' devuelve 0 resultados. "
                        f"Verificar si el filtro es correcto o si hay datos para ese período."
                    )
                    if anomaly_msg not in result.anomalies:
                        result.anomalies.append(anomaly_msg)
                        logger.warning(f"[DEEP AGENT] 🔍 Cero resultados: {objetivo}")

    def _register_siuo_feedback(
        self, question: str, result: EpicAnalysisResult, analysis: Dict
    ) -> None:
        try:
            retriever = get_context_retriever()
            tables_used = list({
                q.get("sql", "").split("FROM")[-1].split()[0].strip()
                for q in result.sql_queries
                if q.get("sql") and "FROM" in q.get("sql", "").upper()
            })
            was_correct = analysis.get("reliability_score", "bajo") in ("alto", "medio")
            sqls_used = " | ".join(q.get("sql", "")[:100] for q in result.sql_queries[:3])
            retriever.register_feedback(
                question=question,
                sql_used=sqls_used,
                was_correct=was_correct,
                tables_used=tables_used,
            )
            logger.info(f"[SIUO] Feedback registrado: correcto={was_correct}")
        except Exception as e:
            logger.debug(f"[SIUO] No se pudo registrar feedback: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # FASE 4b: APRENDIZAJE PERMANENTE
    # ─────────────────────────────────────────────────────────────────────────

    async def _phase4b_learn_and_persist(
        self, question: str, phase2_data: Dict,
        result: EpicAnalysisResult, analysis: Dict
    ) -> PhaseResult:
        """
        Persiste en KnowledgeStore:
          - Columnas reales (RDB$RELATION_FIELDS) por tabla
          - Conteos reales de registros
          - Distribuciones de TIPO, ESTADOPEND, ESTADOPENDVENCOM, DOCDESTINO
          - Reglas de negocio descubiertas
          - Patrones SQL exitosos
        """
        phase = PhaseResult(phase_id="4b", phase_name="Aprendizaje Permanente", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 4b: APRENDIZAJE PERMANENTE ═══")

        if get_knowledge_store is None:
            phase.success = False
            phase.error = "KnowledgeStore no importado"
            return phase

        discoveries: List[str] = []
        try:
            store = get_knowledge_store()
        except Exception as e:
            logger.warning(f"[DEEP AGENT] KnowledgeStore no disponible: {e}")
            phase.success = False
            phase.error = f"KnowledgeStore error: {e}"
            return phase

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
                # Guardar como lista de dicts (mismo formato que devuelve SQL)
                # No convertir a dict: causa errores en _fmt_exploration y lecturas posteriores
                if tipo_dist and isinstance(tipo_dist, list) and table == "DOCCAB":
                    try:
                        updates["tipo_distribution"] = [
                            {"TIPO": r.get("TIPO", "?"), "N": r.get("N", 0)}
                            for r in tipo_dist if isinstance(r, dict)
                        ]
                    except Exception:
                        pass
                if updates:
                    changed = store.update_table(table, updates)
                    if changed:
                        discoveries.append(f"{table}: metadatos actualizados")
                        store.log_discovery("record_count", table, updates, question)

            # ── 2. Extraer conocimiento de los resultados SQL ─────────────────
            for q in result.sql_queries:
                objetivo = q.get("objetivo", "")
                data = q.get("data", [])
                sql = q.get("sql", "")
                rows = q.get("rows", 0)
                if not data or q.get("error"):
                    continue

                # ESTADOPEND
                if "ESTADOPEND" in objetivo and "presupuesto" in objetivo.lower() and "VENCOM" not in objetivo:
                    estadopend_map = {str(r.get("ESTADOPEND", "?")): r.get("N", 0) for r in data}
                    store.update_table("DOCCAB", {
                        "estadopend_distribution": estadopend_map,
                        "_nota_estadopend": f"ESTADOPEND en presupuestos: {estadopend_map}",
                    })
                    store.log_discovery("estadopend", "DOCCAB", estadopend_map, question)
                    discoveries.append(f"DOCCAB.ESTADOPEND: {estadopend_map}")

                # ESTADOPENDVENCOM
                if "ESTADOPENDVENCOM" in objetivo and "presupuesto" in objetivo.lower():
                    vencom_map = {str(r.get("ESTADOPENDVENCOM", "?")): r.get("N", 0) for r in data}
                    store.update_table("DOCCAB", {
                        "estadopendvencom_distribution": vencom_map,
                        "_nota_estadopendvencom": (
                            f"ESTADOPENDVENCOM en presupuestos: {vencom_map}. "
                            "Indica estado desde el punto de vista del vendedor/comercial."
                        ),
                    })
                    store.log_discovery("estadopend", "DOCCAB",
                                        {"vencom": vencom_map}, question)
                    discoveries.append(f"DOCCAB.ESTADOPENDVENCOM: {vencom_map}")

                # Cruce ESTADOPEND x ESTADOPENDVENCOM
                if "Cruce ESTADOPEND" in objetivo and data:
                    cruce_map = [
                        {"ep": str(r.get("ESTADOPEND", "?")),
                         "epv": str(r.get("ESTADOPENDVENCOM", "?")),
                         "n": r.get("N", 0)}
                        for r in data[:10]
                    ]
                    store.update_table("DOCCAB", {"estadopend_cruce": cruce_map})
                    store.log_discovery("estadopend", "DOCCAB", {"cruce": cruce_map}, question)
                    discoveries.append(f"DOCCAB.ESTADOPEND cruce: {len(cruce_map)} combinaciones")

                # Conversión a factura/pedido
                if "convertidos a factura" in objetivo.lower() and data:
                    row = data[0]
                    a_factura = row.get("A_FACTURA", 0)
                    a_pedido = row.get("A_PEDIDO", 0)
                    a_albaran = row.get("A_ALBARAN", 0)
                    total_dest = row.get("TOTAL_CON_DESTINO", 0)
                    store.update_table("DOCCAB", {
                        "conversion_distribution": {
                            "a_factura": a_factura, "a_pedido": a_pedido,
                            "a_albaran": a_albaran, "total": total_dest
                        },
                        "_nota_conversion": (
                            f"Presupuestos con destino: {total_dest}. "
                            f"Factura={a_factura}, Pedido={a_pedido}, Albarán={a_albaran}."
                        ),
                    })
                    store.log_discovery("docdestino", "DOCCAB",
                                        {"a_factura": a_factura, "a_pedido": a_pedido}, question)
                    discoveries.append(f"DOCCAB conversión: factura={a_factura}, pedido={a_pedido}")
                    if a_factura > 0 or a_pedido > 0:
                        store.add_business_rule(
                            f"'Aceptado' = presupuesto convertido a factura (TIPO=13, {a_factura}) "
                            f"o pedido (TIPO=12, {a_pedido}) via DOCDESTINO",
                            table="DOCCAB", confidence="alto"
                        )

                # Columnas de estado en DOCCAB
                if "Columnas de DOCCAB" in objetivo and "ESTADO" in objetivo:
                    cols_estado = [
                        r.get("RDB$FIELD_NAME", "").strip()
                        for r in data if r.get("RDB$FIELD_NAME")
                    ]
                    if cols_estado:
                        store.update_table("DOCCAB", {"columns_estado": cols_estado})
                        discoveries.append(f"DOCCAB columnas estado: {cols_estado}")

                # Presupuestos con/sin documento destino
                if "documento destino vinculado" in objetivo.lower() and data:
                    row = data[0]
                    total_p = row.get("TOTAL_PRESUPUESTOS", 0)
                    con_dest = row.get("CON_DESTINO", 0)
                    if total_p:
                        pct = round(con_dest / total_p * 100, 1)
                        store.update_table("DOCCAB", {
                            "_nota_docdestino": (
                                f"De {total_p} presupuestos: {con_dest} tienen destino ({pct}%)."
                            )
                        })
                        store.log_discovery("docdestino", "DOCCAB",
                                            {"total": total_p, "con": con_dest, "pct": pct}, question)
                        discoveries.append(f"DOCCAB→DOCDESTINO: {con_dest}/{total_p} ({pct}%)")
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
                        discoveries.append(f"DOCDESTINO tipos: {tipo_dest_map}")

                # Patrón SQL exitoso
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

            logger.info(f"[DEEP AGENT] Fase 4b: {len(discoveries)} descubrimientos persistidos")
            phase.data = {
                "discoveries": discoveries,
                "tables_updated": list(phase2_data.keys()),
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
