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

        # ── System prompt: solo Markdown, sin HTML, sin <details> ─────────────
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
