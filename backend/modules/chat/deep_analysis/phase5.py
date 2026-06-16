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
        sqls_details = "\n\n".join(
            f"**{q['objetivo']}** ({q.get('rows', 0)} filas)\n"
            f"```sql\n{q['sql']}\n```"
            + (f"\n⚠️ Error: {q['error']}" if q.get('error') else "")
            for q in result.sql_queries[:8] if q.get("sql")
        )
        reliability_score = analysis_data.get("reliability_score", "?")
        reliability_reason = analysis_data.get("reliability_reason", "")
        limitations = "\n".join(
            f"• {l}" for l in analysis_data.get("sql_limitations", [])[:5]
        )
        # Extraer nombres de tablas reales (evitar EXTRACT(... FROM ...) y similares)
        # Solo extraer el primer token después de FROM/JOIN que sea un identificador válido
        _table_name_re = re.compile(r'[A-Z_][A-Z0-9_]*', re.IGNORECASE)
        _from_join_re = re.compile(r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)', re.IGNORECASE)
        tables_used = list({
            m.group(1).upper()
            for q in result.sql_queries if q.get("sql")
            for m in _from_join_re.finditer(q["sql"])
            # Excluir palabras clave SQL y funciones que no son tablas
            if m.group(1).upper() not in {
                'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS',
                'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'NATURAL',
                'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'CURRENT_TIME',
                'FECHA', 'NOMBRE', 'CODIGO', 'TIPO', 'IMPORTE',
            }
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

        # ── Detección de tema principal para mantener el foco ─────────────────
        # Si la pregunta es sobre artículos/rotación, la IA debe responder sobre
        # artículos — no sobre instalaciones, presupuestos u otros temas.
        _art_kw = ["artículo", "articulo", "producto", "item", "referencia"]
        _art_mov_kw = ["rotación", "rotacion", "vendido", "comprado", "negociar",
                       "volumen", "candidatos", "frecuencia", "demanda", "popular"]
        _is_article_topic = (
            any(k in question.lower() for k in _art_kw) and
            any(k in question.lower() for k in _art_mov_kw)
        )
        _topic_focus_rule = (
            f"• FOCO OBLIGATORIO: La pregunta es sobre ARTÍCULOS/PRODUCTOS. "
            f"Tu respuesta DEBE centrarse en artículos, su rotación y volumen de ventas. "
            f"NO menciones instalaciones, presupuestos ni otros temas no relacionados. "
            f"Si los datos de artículos son escasos, indícalo claramente.\n"
        ) if _is_article_topic else ""

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
            + _topic_focus_rule
            + _no_data_rule
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
                # Si el modelo alcanzó max_tokens, la respuesta se corta a mitad.
                # Detectamos esto y pedimos al modelo que continúe desde donde paró.
                resp = await self._continue_if_truncated(resp, system, question, result)
                # ─────────────────────────────────────────────────────────────

                resp_clean = self._strip_html_from_markdown(resp)
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
            # Verificar que contiene al menos una sección obligatoria final
            has_final_section = any(s in text for s in _REQUIRED_SECTIONS)
            if not has_final_section:
                return True
            # Verificar que no termina en mitad de frase
            last_char = text[-1] if text else ""
            if last_char not in (".", "!", "?", "\n", "*", "-", ">", "|"):
                # Puede estar cortado en mitad de palabra
                last_line = text.split("\n")[-1].strip()
                if last_line and not last_line.endswith((".", "!", "?", "*", "-", "|")):
                    # Si la última línea es corta y no termina en puntuación → cortado
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

            # Construir prompt de continuación
            # Enviamos los últimos 500 chars para que el modelo sepa dónde paró
            tail = full_resp[-500:] if len(full_resp) > 500 else full_resp
            continuation_system = (
                "Eres un analista de datos experto. Estás completando una respuesta "
                "que fue cortada por límite de tokens. "
                "CONTINÚA exactamente desde donde se cortó, sin repetir lo ya escrito. "
                "Completa las secciones que faltan: "
                "## ⚠️ Advertencias y Objeciones, ## 💡 Contexto de Negocio, "
                "## 🚀 Sugerencias y Próximos Pasos. "
                "Solo Markdown puro, sin HTML, sin <details>."
            )
            continuation_user = (
                f"PREGUNTA ORIGINAL: {question}\n\n"
                f"TEXTO YA GENERADO (últimas líneas):\n...{tail}\n\n"
                f"CONTINÚA desde aquí, completando las secciones que faltan. "
                f"NO repitas lo ya escrito. Empieza directamente con la continuación."
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
