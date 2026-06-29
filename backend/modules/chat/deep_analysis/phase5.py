"""
phase5.py — Fase 5 del DeepAnalysisAgent: Síntesis Épica.

Genera la respuesta final en Markdown con:
  - Respuesta principal con datos reales en tabla
  - Análisis crítico
  - Advertencias y objeciones (Markdown puro, sin HTML)
  - Contexto de negocio
  - Sugerencias y próximos pasos
  - Detalles técnicos en bloque <details> (construido en Python, no por la IA)

Principios:
  - NO genera HTML crudo — solo Markdown puro
  - El bloque <details> se construye en Python para garantizar contenido real
  - _strip_html_from_markdown() limpia cualquier HTML que la IA genere
"""

import logging
import re
from typing import Dict

from backend.modules.chat.deep_analysis.models import (
    EpicAnalysisResult, PhaseResult, SubPhaseResult,
)

logger = logging.getLogger(__name__)


class Phase5Mixin:
    """
    Mixin con la fase 5 del agente.
    Requiere: self.orchestrator, self.budget,
              self._fmt_investigation(), self._build_warnings_html(),
              self._emergency_fallback()
    """

    async def _phase5_synthesize(
        self, question: str, result: EpicAnalysisResult, cfg: Dict
    ) -> PhaseResult:
        phase = PhaseResult(phase_id="5", phase_name="Síntesis Épica", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 5: SÍNTESIS ÉPICA ═══")

        from datetime import datetime
        now = datetime.now()
        fecha_actual = now.strftime("%d/%m/%Y")
        hora_actual = now.strftime("%H:%M")
        anio_actual = now.year

        # Buscar datos de análisis en las fases ejecutadas
        analysis_data = {}
        for ph in result.phases:
            if ph.phase_id == "4" and ph.data:
                analysis_data = ph.data
                break

        data_summary_full = self._fmt_investigation(result.sql_queries)
        warnings_html = self._build_warnings_html(result)

        # ── Detectar si hay datos reales disponibles ──────────────────────────
        # Si todas las consultas fallaron o devolvieron 0 filas, la IA NO debe
        # inventar datos — debe indicar que no hay información disponible.
        successful_queries = [q for q in result.sql_queries if not q.get("error") and q.get("rows", 0) > 0]
        has_real_data = len(successful_queries) > 0

        # ── Construir bloque <details> en Python (no por la IA) ──────────────
        def _clean_error(err: str) -> str:
            """Limpia mensajes de error técnicos internos para presentación al usuario."""
            if not err:
                return err
            err = re.sub(r'^\[SIM\]\s*', '', err)
            err = re.sub(r'^Error en query:\s*', '', err, flags=re.IGNORECASE)
            if "incomplete input" in err.lower():
                return "SQL incompleto (modelo truncó la consulta)"
            if "no such table" in err.lower():
                m = re.search(r'no such table:\s*(\S+)', err, re.IGNORECASE)
                return f"Tabla no encontrada: {m.group(1)}" if m else "Tabla no encontrada"
            if "no such column" in err.lower():
                m = re.search(r'no such column:\s*(\S+)', err, re.IGNORECASE)
                return f"Columna no encontrada: {m.group(1)}" if m else "Columna no encontrada"
            # Cortar tras "Usa solo:" para no exponer lista técnica de tablas
            if "Usa solo:" in err:
                err = err[:err.index("Usa solo:")].rstrip(". ")
            if "Tablas disponibles:" in err:
                err = err[:err.index("Tablas disponibles:")].rstrip(". ")
            # Limitar longitud
            return err[:200]

        ok_queries = [q for q in result.sql_queries[:8] if q.get("sql") and not q.get("error")]
        err_queries = [q for q in result.sql_queries[:8] if q.get("sql") and q.get("error")]
        sqls_details = "\n\n".join(
            f"**{q['objetivo']}** ({q.get('rows', 0)} filas)\n"
            f"```sql\n{q['sql']}\n```"
            for q in ok_queries
        )
        if err_queries:
            sqls_details += (
                "\n\n**Consultas con error (" + str(len(err_queries)) + "):** "
                + " | ".join(
                    f"`{q['objetivo'][:35]}` → {_clean_error(q.get('error', ''))}"
                    for q in err_queries
                )
            )
        reliability_score = analysis_data.get("reliability_score", "?")
        reliability_reason = analysis_data.get("reliability_reason", "")

        # Formatear limitaciones SQL como texto legible (no como dicts Python)
        def _fmt_limitation(lim) -> str:
            if isinstance(lim, dict):
                desc = lim.get("description") or lim.get("details") or lim.get("message") or ""
                lim_type = lim.get("type", "")
                if desc:
                    return desc.strip()
                if lim_type:
                    return f"[{lim_type}] {' — '.join(str(v) for k, v in lim.items() if k != 'type' and v)}"
                return str(lim)
            return str(lim).strip()

        limitations = "\n".join(
            f"• {_fmt_limitation(l)}" for l in analysis_data.get("sql_limitations", [])[:5]
        )
        # Extraer nombres de tablas reales (excluir CTEs, keywords SQL y funciones)
        _from_join_re = re.compile(r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)', re.IGNORECASE)
        _cte_re = re.compile(r'\bWITH\s+(\w+)\s+AS\s*\(', re.IGNORECASE)
        _cte_comma_re = re.compile(r',\s*(\w+)\s+AS\s*\(', re.IGNORECASE)
        _SQL_KW = {
            'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS',
            'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'NATURAL',
            'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'CURRENT_TIME',
            'FECHA', 'NOMBRE', 'CODIGO', 'TIPO', 'IMPORTE',
        }
        # Recopilar nombres de CTEs para excluirlos (no son tablas reales)
        all_cte_names: set = set()
        for q in result.sql_queries:
            if q.get("sql"):
                all_cte_names.update(m.group(1).upper() for m in _cte_re.finditer(q["sql"]))
                all_cte_names.update(m.group(1).upper() for m in _cte_comma_re.finditer(q["sql"]))

        tables_used = list({
            m.group(1).upper()
            for q in result.sql_queries if q.get("sql")
            for m in _from_join_re.finditer(q["sql"])
            if m.group(1).upper() not in _SQL_KW
            and m.group(1).upper() not in all_cte_names
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

        # ── Regla de foco temático genérica ──────────────────────────────────
        # La IA debe responder EXACTAMENTE sobre lo que pregunta el usuario.
        # No debe desviar la respuesta hacia temas relacionados pero no pedidos.
        # Esta regla es genérica: aplica a cualquier pregunta, no solo artículos.
        _topic_focus_rule = (
            "• FOCO OBLIGATORIO: Responde EXACTAMENTE sobre lo que pregunta el usuario. "
            "No desvíes la respuesta hacia temas relacionados pero no pedidos. "
            "Si los datos disponibles no responden directamente la pregunta, indícalo claramente "
            "en lugar de responder sobre un tema diferente.\n"
        )

        # ── System prompt: solo Markdown, sin HTML, sin <details> ─────────────
        # Regla anti-invención: si no hay datos reales, la IA debe decirlo
        # explícitamente en lugar de inventar nombres/valores plausibles.
        _no_data_rule = (
            "• CRÍTICO: Las consultas SQL no devolvieron datos reales (0 filas o errores). "
            "En la sección '## 📊 Respuesta Principal' escribe EXACTAMENTE: "
            "'No hay datos disponibles en la base de datos para responder esta pregunta. "
            "Las consultas ejecutadas no devolvieron resultados.' "
            "NO inventes nombres de clientes, importes, ni ningún valor. "
            "Puedes analizar por qué puede no haber datos y qué hacer.\n"
        ) if not has_real_data else ""

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
            "• PROHIBIDO inventar datos, nombres de clientes, importes o cualquier valor "
            "que no aparezca explícitamente en los DATOS proporcionados abajo.\n"
            "• Si los DATOS muestran ERROR o 0 filas, NO inventes una tabla con datos.\n"
            "• NO generar HTML ni etiquetas <div>, <span>, <details>.\n"
            "• Para presupuestos: 1 instalación = N presupuestos.\n"
            f"• El año {anio_actual} es el año ACTUAL, no futurista.\n"
            "• Incluir tabla por año/serie si hay datos temporales.\n"
            "• TIPOS DE DOCUMENTO en DOCCAB.TIPO (etiquetas OBLIGATORIAS y EXACTAS): "
            "0=Presupuesto cliente | 1=Pedido cliente | 2=Albarán cliente | 3=Factura cliente | "
            "10=Presupuesto prov | 11=Pedido prov | 12=Albarán prov | 13=Factura prov | "
            "21=Mov.almacén. "
            "NUNCA llames 'Albarán' o 'Pedido' a TIPO=0 (es Presupuesto). "
            "En tablas de distribución de TIPO, muestra TODOS los tipos encontrados, "
            "no solo los 3 primeros. Usa las etiquetas exactas de esta lista.\n"
            + _topic_focus_rule
            + _no_data_rule
            + "• CRÍTICO: PROHIBIDO mencionar nombres de tablas de la BD (DOCCAB, CLIENTE, etc.) "
            "como si el usuario las conociera o como si fueran parte de la respuesta. "
            "Si aparecen errores con nombres de tablas en los datos, NO los repitas ni expandas. "
            "NUNCA inventes listas de tablas disponibles — el usuario no necesita saber esto.\n"
            + "• ESTRUCTURA COMPLETA OBLIGATORIA: Tu respuesta DEBE incluir las 5 secciones: "
            "## 📊 Respuesta Principal, ## 🔍 Análisis Crítico, ## ⚠️ Advertencias y Objeciones, "
            "## 💡 Contexto de Negocio, ## 🚀 Sugerencias y Próximos Pasos. "
            "NUNCA dejes una sección sin contenido. Si se queda sin espacio, resume las últimas "
            "secciones en 2-3 líneas en lugar de cortarlas.\n"
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
                # ── Detección de respuesta cortada + continuación ─────────────
                resp = await self._continue_if_truncated(resp, system, question, result)

                # ── Quality gate: reintento si la síntesis es de baja calidad ─
                resp = await self._retry_if_low_quality(
                    resp, question, result, successful_queries, fecha_actual, anio_actual
                )
                # ─────────────────────────────────────────────────────────────

                resp_clean = self._strip_html_from_markdown(resp)
                final = resp_clean
                if warnings_html:
                    final += "\n\n---\n\n## 🔎 Evidencias y Aclaraciones\n\n" + warnings_html
                final += details_block
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
                logger.warning("[DEEP AGENT] Fase 5: IA no disponible — usando fallback con datos crudos")
                result.ai_unavailable = True
                phase.success = False
                result.final_answer = self._emergency_fallback(result)
        except Exception as e:
            logger.error(f"[DEEP AGENT] Fase 5 error: {e}")
            result.ai_unavailable = True
            phase.success = False
            phase.error = str(e)
            result.final_answer = self._emergency_fallback(result)
        return phase

    async def _retry_if_low_quality(
        self,
        resp: str,
        question: str,
        result: "EpicAnalysisResult",
        successful_queries: list,
        fecha_actual: str,
        anio_actual: int,
    ) -> str:
        """
        Detecta síntesis de baja calidad y reintenta con prompt más directo.

        Indicadores de mala calidad:
        - Respuesta corta (<400 chars)
        - No contiene ninguna tabla Markdown (sin '|')
        - Contiene frases de fracaso como "no se pudo ejecutar"
        - Sección principal dice "no hay datos" cuando SÍ hay consultas exitosas
        """
        _FAILURE_PHRASES = [
            "no se pudo ejecutar",
            "no se pudo calcular",
            "error en la consulta",
            "cannot read property",
            "no pudo procesar",
            "fallo crítico",
            "0 resultados** (no se",
            "no disponible** (no hay",
        ]
        _REQUIRED_FINAL = ["## 🚀 Sugerencias", "## 💡 Contexto"]

        def _is_low_quality(text: str) -> bool:
            t = text.lower()
            if len(text.strip()) < 400:
                return True
            if "|" not in text and successful_queries:
                return True
            # Respuesta truncada (le falta alguna sección final)
            if not all(s in text for s in _REQUIRED_FINAL):
                return True
            if any(p in t for p in _FAILURE_PHRASES):
                return True
            return False

        if not _is_low_quality(resp):
            return resp

        logger.warning(
            f"[DEEP AGENT] ⚠️ Síntesis de baja calidad detectada ({len(resp)} chars). "
            "Reintentando con prompt directo..."
        )

        # Construir raw data de las consultas exitosas para forzar tabla concreta
        raw_data_lines = []
        for q in successful_queries[:6]:
            rows_preview = q.get("data", [])[:5]
            raw_data_lines.append(
                f"CONSULTA '{q['objetivo']}' ({q.get('rows', 0)} filas):\n"
                + "\n".join(str(r) for r in rows_preview)
            )
        raw_data_text = "\n\n".join(raw_data_lines) if raw_data_lines else "Sin datos disponibles"

        retry_system = (
            f"Eres un analista de datos experto. HOY ES {fecha_actual} (año {anio_actual}).\n"
            "TAREA: Genera una respuesta CONCISA y CON TABLA MARKDOWN a partir de los datos brutos.\n\n"
            "ESTRUCTURA:\n"
            "## 📊 Respuesta Principal\n"
            "[TABLA MARKDOWN con los datos reales — columnas claras, valores exactos]\n\n"
            "## 🔍 Análisis Crítico\n[2-4 párrafos de interpretación]\n\n"
            "## ⚠️ Advertencias y Objeciones\n[Lista con •]\n\n"
            "## 💡 Contexto de Negocio\n[1-2 párrafos]\n\n"
            "## 🚀 Sugerencias y Próximos Pasos\n[Lista numerada]\n\n"
            "REGLAS:\n"
            "• USA SOLO los datos que aparecen abajo — CERO INVENCIÓN.\n"
            "• Si hay números, ponlos en una tabla Markdown bien formateada.\n"
            "• TIPOS DOCCAB: 0=Presupuesto | 2=Albarán cliente | 3=Factura cliente | "
            "11=Pedido prov | 12=Albarán prov | 13=Factura prov.\n"
            "• Solo Markdown puro, sin HTML, sin <details>.\n"
        )
        retry_user = (
            f"PREGUNTA: {question}\n\n"
            f"DATOS DISPONIBLES:\n{raw_data_text}\n\n"
            "Genera la respuesta con tabla Markdown real a partir de estos datos."
        )

        try:
            retry_resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=retry_system,
                user_message=retry_user,
                preferred_model_id="jddcia-qwen3-30b",
            )
            if retry_resp and len(retry_resp.strip()) > len(resp.strip()):
                logger.info(
                    f"[DEEP AGENT] ✅ Reintento de calidad OK: "
                    f"{len(resp)} → {len(retry_resp)} chars"
                )
                return retry_resp
            logger.warning(
                "[DEEP AGENT] Reintento de calidad no mejoró la respuesta — usando original"
            )
        except Exception as e:
            logger.error(f"[DEEP AGENT] Error en reintento de calidad: {e}")

        return resp

    def _needs_extra_investigation(self, result: "EpicAnalysisResult") -> bool:
        """
        Evalúa si la síntesis actual tiene calidad insuficiente y necesita más datos.

        Returns True solo cuando la respuesta indica explícitamente ausencia de datos
        Y hay margen de presupuesto para seguir investigando.
        """
        answer = result.final_answer or ""
        if len(answer.strip()) >= 600:
            return False  # Respuesta suficientemente larga → no reinvestigar

        _POOR_INDICATORS = [
            "sin datos suficientes", "datos insuficientes",
            "no se pudo responder", "sin datos disponibles",
            "no hay datos", "0 resultados en todas",
            "no existen registros", "no dispongo de datos",
            "la consulta no devolvió", "consultas fallidas",
        ]
        ans_lower = answer.lower()
        if not any(p in ans_lower for p in _POOR_INDICATORS):
            return False  # No indica falta de datos — respuesta válida aunque corta

        if len(result.sql_queries) >= 20:
            return False  # Demasiadas queries ya ejecutadas — evitar presupuesto excesivo

        return True

    async def _continue_if_truncated(
        self,
        resp: str,
        system: str,
        question: str,
        result: "EpicAnalysisResult",
        max_continuations: int = 3,
    ) -> str:
        """
        Detecta si la respuesta fue cortada por límite de tokens y la continúa.

        Estrategia ultra-resiliente:
        1. Detecta si la respuesta está incompleta (no termina en sección completa)
        2. Si está cortada, pide al modelo que continúe desde donde paró
        3. Repite hasta max_continuations veces o hasta que la respuesta esté completa
        4. Si no se puede completar, añade un aviso amigable al usuario

        Indicadores de respuesta cortada:
        - No contiene las secciones obligatorias (## 🚀 Sugerencias)
        - Termina en mitad de una frase (sin punto, sin salto de línea doble)
        - Termina en mitad de una tabla Markdown (sin fila de cierre)
        - Termina en mitad de una lista (sin elemento final)
        """
        _REQUIRED_SECTIONS = [
            "## 🚀 Sugerencias",
            "## 💡 Contexto",
            "## ⚠️ Advertencias",
        ]
        _MAX_RESP_LEN = 20000  # Límite de seguridad para evitar bucles infinitos

        def _is_truncated(text: str) -> bool:
            """Detecta si la respuesta está incompleta."""
            text = text.strip()
            if not text:
                return True
            # Todas las secciones finales obligatorias deben estar presentes (no solo alguna)
            if not all(s in text for s in _REQUIRED_SECTIONS):
                return True
            # Verificar que cada sección obligatoria tiene contenido real (no solo el encabezado)
            for section in _REQUIRED_SECTIONS:
                idx = text.find(section)
                if idx != -1:
                    after = text[idx + len(section):].lstrip()
                    # Buscar cuánto contenido hay hasta la siguiente sección o fin
                    next_section_idx = len(after)
                    for other in _REQUIRED_SECTIONS:
                        if other in after:
                            next_section_idx = min(next_section_idx, after.find(other))
                    section_content = after[:next_section_idx].strip()
                    if len(section_content) < 30:
                        return True  # Sección sin contenido real
            # Verificar que no termina en mitad de frase
            last_char = text[-1] if text else ""
            if last_char not in (".", "!", "?", "\n", "*", "-", ">", "|"):
                last_line = text.split("\n")[-1].strip()
                if last_line and not last_line.endswith((".", "!", "?", "*", "-", "|")):
                    if len(last_line) < 80 and not last_line.startswith("#"):
                        return True
            return False

        if not _is_truncated(resp):
            logger.info("[DEEP AGENT] Fase 5: respuesta completa (sin truncado)")
            return resp

        logger.warning(
            f"[DEEP AGENT] ⚠️ Respuesta truncada detectada ({len(resp)} chars). "
            f"Iniciando continuación automática (máx {max_continuations} intentos)..."
        )

        full_resp = resp
        for attempt in range(1, max_continuations + 1):
            if len(full_resp) > _MAX_RESP_LEN:
                logger.warning(
                    f"[DEEP AGENT] Respuesta ya muy larga ({len(full_resp)} chars). "
                    f"Deteniendo continuación."
                )
                break

            # Construir prompt de continuación con referencia a datos reales
            # CRÍTICO: sin datos de referencia el modelo inventa cifras distintas a las reales
            tail = full_resp[-600:] if len(full_resp) > 600 else full_resp
            ok_refs = [q for q in result.sql_queries if not q.get("error") and q.get("rows", 0) > 0]
            data_ref = "\n".join(
                f"• {q['objetivo']}: {q.get('rows', 0)} filas"
                + (f" → {q.get('data', [{}])[0]}" if q.get("data") else "")
                for q in ok_refs[:5]
            )[:600]
            continuation_system = (
                "Eres un analista de datos experto. Estás completando una respuesta "
                "que fue cortada por límite de tokens. "
                "CONTINÚA desde donde se cortó. REGLAS ESTRICTAS:\n"
                "• NO repitas secciones ya escritas (## ⚠️ Advertencias, ## 🔍 Análisis, etc.)\n"
                "• USA SOLO los datos de DATOS REALES proporcionados abajo — CERO INVENCIÓN de cifras\n"
                "• Completa SOLO las secciones que faltan del texto ya generado\n"
                "• Solo Markdown puro, sin HTML, sin <details>"
            )
            continuation_user = (
                f"PREGUNTA ORIGINAL: {question}\n\n"
                + (f"DATOS REALES (referencia para no inventar):\n{data_ref}\n\n" if data_ref else "")
                + f"TEXTO YA GENERADO (últimas líneas):\n...{tail}\n\n"
                f"CONTINÚA desde aquí. NO repitas secciones ya presentes. "
                f"Empieza directamente con la continuación."
            )

            try:
                continuation, _ = await self.orchestrator.execute_with_fallback(
                    system_prompt=continuation_system,
                    user_message=continuation_user,
                    preferred_model_id="jddcia-qwen3-30b",
                )
                if continuation and continuation.strip():
                    full_resp = full_resp.rstrip() + "\n\n" + continuation.strip()
                    logger.info(
                        f"[DEEP AGENT] Continuación {attempt}/{max_continuations}: "
                        f"+{len(continuation)} chars → total {len(full_resp)} chars"
                    )
                    if not _is_truncated(full_resp):
                        logger.info(
                            f"[DEEP AGENT] ✅ Respuesta completada en {attempt} continuación(es)"
                        )
                        return full_resp
                else:
                    logger.warning(
                        f"[DEEP AGENT] Continuación {attempt}: IA no devolvió texto. "
                        f"Deteniendo."
                    )
                    break
            except Exception as cont_err:
                logger.error(
                    f"[DEEP AGENT] Error en continuación {attempt}: {cont_err}"
                )
                break

        # Si después de todos los intentos sigue incompleta, añadir aviso amigable
        if _is_truncated(full_resp):
            logger.warning(
                f"[DEEP AGENT] ⚠️ No se pudo completar la respuesta tras "
                f"{max_continuations} intentos. Añadiendo aviso al usuario."
            )
            full_resp += (
                "\n\n---\n"
                "> ⚠️ **Nota:** Esta respuesta fue generada en partes debido al volumen "
                "de datos analizados. Si deseas ver el análisis completo, puedes pedir "
                "'continúa el análisis' o hacer preguntas más específicas sobre "
                "alguna sección concreta."
            )

        return full_resp

    def _strip_html_from_markdown(self, text: str) -> str:
        """
        Elimina etiquetas HTML del texto Markdown generado por la IA.
        Preserva el contenido de texto dentro de las etiquetas.
        Convierte <strong>, <em>, <li> a equivalentes Markdown.
        """
        try:
            # Eliminar bloques <details> (los reemplazamos con nuestro bloque Python)
            text = re.sub(r'<details>.*?</details>', '', text, flags=re.DOTALL | re.IGNORECASE)
            # Preservar contenido de <div>, <span>, <p>
            text = re.sub(r'<div[^>]*>(.*?)</div>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n', text, flags=re.DOTALL | re.IGNORECASE)
            # Convertir a Markdown
            text = re.sub(r'<(strong|b)>(.*?)</(strong|b)>', r'**\2**', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<(em|i)>(.*?)</(em|i)>', r'*\2*', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<ul[^>]*>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'</ul>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1\n', text, flags=re.DOTALL | re.IGNORECASE)
            # Limpiar etiquetas HTML residuales
            text = re.sub(r'<[^>]+>', '', text)
            # Limpiar líneas vacías múltiples (máx 2 consecutivas)
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text.strip()
        except Exception:
            return text
