"""
phase_verify.py — Fase de Verificación de Resultados (Fase 5b).

Verifica que la respuesta generada por la IA en Fase 5 NO contiene datos
inventados — todos los valores numéricos y nombres de entidades deben
aparecer en los resultados SQL reales.

Principio DEVIA: la IA NUNCA inventa datos. Esta fase es la red de seguridad
que detecta y corrige cualquier invención antes de mostrar la respuesta al usuario.

Flujo:
  1. Extraer valores clave de la respuesta IA (nombres, importes, conteos)
  2. Verificar que cada valor aparece en los datos SQL reales
  3. Si hay valores inventados → marcar como "no verificado" y añadir aviso
  4. Si todos los valores están verificados → añadir sello de fiabilidad

Integración:
  - Se llama desde agent.py después de _phase5_synthesize()
  - Modifica result.final_answer añadiendo el bloque de verificación
  - NO bloquea la respuesta — solo añade contexto de fiabilidad
"""

import logging
import re
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class PhaseVerifyMixin:
    """
    Mixin con la fase de verificación de resultados.
    Requiere: self.budget, self._fmt_investigation()
    """

    async def _phase5b_verify(
        self,
        question: str,
        result,
        cfg: Dict,
    ):
        """
        Fase 5b: Verificación de resultados.

        Compara los valores en la respuesta IA con los datos SQL reales.
        Añade un bloque de verificación al final de la respuesta.

        Retorna el resultado modificado (result.final_answer actualizado).
        """
        from backend.modules.chat.deep_analysis.models import PhaseResult, SubPhaseResult
        phase = PhaseResult(phase_id="5b", phase_name="Verificación de Resultados", success=True)
        logger.info("[DEEP AGENT] ═══ FASE 5b: VERIFICACIÓN DE RESULTADOS ═══")

        if not result.final_answer:
            logger.warning("[DEEP AGENT] Fase 5b: sin respuesta que verificar")
            phase.success = False
            return phase

        # ── Extraer datos reales de las consultas SQL ─────────────────────────
        real_data = self._extract_real_values(result.sql_queries)
        successful_queries = [q for q in result.sql_queries if not q.get("error") and q.get("rows", 0) > 0]
        failed_queries = [q for q in result.sql_queries if q.get("error")]

        # ── Verificar la respuesta ────────────────────────────────────────────
        verification = self._verify_response_against_data(
            response=result.final_answer,
            real_data=real_data,
            successful_queries=successful_queries,
            failed_queries=failed_queries,
        )

        # ── Construir bloque de verificación ─────────────────────────────────
        verify_block = self._build_verification_block(verification, successful_queries, failed_queries)

        # ── Añadir bloque a la respuesta ──────────────────────────────────────
        # Insertar antes del bloque <details> si existe, o al final
        if "<details>" in result.final_answer:
            result.final_answer = result.final_answer.replace(
                "\n\n<details>",
                f"\n\n{verify_block}\n\n<details>",
                1
            )
        else:
            result.final_answer = result.final_answer + f"\n\n{verify_block}"

        # ── Registrar en fases ────────────────────────────────────────────────
        phase.data = {
            "verified": verification["verified"],
            "invented_count": verification["invented_count"],
            "total_checked": verification["total_checked"],
            "reliability": verification["reliability"],
        }
        phase.sub_phases.extend([
            SubPhaseResult(
                "5b.1 Extracción de valores reales",
                True,
                f"{len(real_data['all_values'])} valores únicos de {len(successful_queries)} consultas"
            ),
            SubPhaseResult(
                "5b.2 Verificación de respuesta",
                verification["verified"],
                f"{verification['verified_count']}/{verification['total_checked']} valores verificados"
            ),
            SubPhaseResult(
                "5b.3 Bloque de fiabilidad",
                True,
                verification["reliability"]
            ),
        ])

        logger.info(
            f"[DEEP AGENT] Fase 5b: {verification['verified_count']}/{verification['total_checked']} "
            f"valores verificados | fiabilidad: {verification['reliability']}"
        )
        return phase

    def _extract_real_values(self, sql_queries: List[Dict]) -> Dict:
        """
        Extrae todos los valores reales de los resultados SQL.

        Retorna un dict con:
          - all_values: set de todos los valores (strings y números)
          - numeric_values: set de valores numéricos
          - string_values: set de valores de texto
          - by_query: dict de objetivo → valores
        """
        all_values: Set[str] = set()
        numeric_values: Set[float] = set()
        string_values: Set[str] = set()
        by_query: Dict[str, List] = {}

        for q in sql_queries:
            if q.get("error") or not q.get("data"):
                continue
            objetivo = q.get("objetivo", "?")
            q_values = []
            for row in q.get("data", []):
                for col, val in row.items():
                    if val is None:
                        continue
                    str_val = str(val).strip()
                    if not str_val or str_val == "(sin datos)":
                        continue
                    all_values.add(str_val.upper())
                    q_values.append(str_val)
                    # Detectar numéricos
                    try:
                        num = float(str_val.replace(",", ".").replace(".", "", str_val.count(".") - 1))
                        numeric_values.add(num)
                        all_values.add(str(int(num)) if num == int(num) else str_val)
                    except (ValueError, AttributeError):
                        string_values.add(str_val.upper())
            by_query[objetivo] = q_values

        return {
            "all_values": all_values,
            "numeric_values": numeric_values,
            "string_values": string_values,
            "by_query": by_query,
        }

    def _verify_response_against_data(
        self,
        response: str,
        real_data: Dict,
        successful_queries: List[Dict],
        failed_queries: List[Dict],
    ) -> Dict:
        """
        Verifica que los valores en la respuesta aparecen en los datos reales.

        Estrategia:
        1. Si no hay datos reales (todas las queries fallaron) → marcar como no verificable
        2. Extraer valores de tablas Markdown en la respuesta
        3. Verificar cada valor contra real_data
        4. Calcular score de fiabilidad

        Retorna dict con métricas de verificación.
        """
        has_real_data = len(successful_queries) > 0
        all_real_values = real_data.get("all_values", set())

        if not has_real_data:
            return {
                "verified": False,
                "verified_count": 0,
                "invented_count": 0,
                "total_checked": 0,
                "reliability": "no_data",
                "detail": "No hay datos reales para verificar — todas las consultas fallaron.",
                "invented_values": [],
            }

        # Extraer valores de tablas Markdown en la respuesta
        table_values = self._extract_table_values_from_markdown(response)

        if not table_values:
            # No hay tabla en la respuesta — verificación no aplicable
            return {
                "verified": True,
                "verified_count": 0,
                "invented_count": 0,
                "total_checked": 0,
                "reliability": "no_table",
                "detail": "La respuesta no contiene tabla de datos — verificación no aplicable.",
                "invented_values": [],
            }

        # Verificar cada valor de la tabla
        verified_count = 0
        invented_values = []
        total_checked = 0

        for val in table_values:
            val_upper = val.upper().strip()
            # Ignorar valores muy cortos, fechas, porcentajes, etc.
            if len(val_upper) < 3:
                continue
            if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', val_upper):
                continue  # Fechas — no verificar
            if val_upper.endswith('%') or val_upper.endswith('€'):
                continue  # Porcentajes/monedas — no verificar
            if val_upper in ('(SIN DATOS)', 'N/A', 'NULL', '-', '---'):
                continue  # Valores vacíos — no verificar

            total_checked += 1
            # Verificar si el valor aparece en los datos reales
            found = (
                val_upper in all_real_values
                or any(val_upper in rv for rv in all_real_values)
                or any(rv in val_upper for rv in all_real_values if len(rv) > 5)
            )
            if found:
                verified_count += 1
            else:
                invented_values.append(val)

        invented_count = len(invented_values)

        # Calcular fiabilidad
        if total_checked == 0:
            reliability = "no_table"
        elif invented_count == 0:
            reliability = "alta"
        elif invented_count <= 2 or (invented_count / total_checked) < 0.2:
            reliability = "media"
        else:
            reliability = "baja"

        verified = invented_count == 0 or reliability in ("alta", "media")

        return {
            "verified": verified,
            "verified_count": verified_count,
            "invented_count": invented_count,
            "total_checked": total_checked,
            "reliability": reliability,
            "detail": f"{verified_count}/{total_checked} valores verificados contra datos reales.",
            "invented_values": invented_values[:5],  # Máximo 5 para no saturar
        }

    def _extract_table_values_from_markdown(self, response: str) -> List[str]:
        """
        Extrae valores de celdas de tablas Markdown en la respuesta.

        Solo extrae valores de la sección ## 📊 Respuesta Principal.
        Ignora cabeceras y separadores.
        """
        values = []
        # Buscar la sección de respuesta principal
        main_section_match = re.search(
            r'##\s*📊\s*Respuesta Principal(.*?)(?=##\s*[🔍⚠️💡🚀]|\Z)',
            response,
            re.DOTALL | re.IGNORECASE
        )
        if not main_section_match:
            # Intentar extraer cualquier tabla Markdown
            section_text = response
        else:
            section_text = main_section_match.group(1)

        # Extraer filas de tabla Markdown (| val1 | val2 | ...)
        for line in section_text.split('\n'):
            line = line.strip()
            if not line.startswith('|') or not line.endswith('|'):
                continue
            # Ignorar separadores (| --- | --- |)
            if re.match(r'^\|[\s\-|]+\|$', line):
                continue
            # Extraer celdas
            cells = [c.strip() for c in line.split('|') if c.strip()]
            # Ignorar cabeceras (primera fila de la tabla)
            if all(c.isupper() or c.replace(' ', '').isupper() for c in cells if c):
                continue
            values.extend(cells)

        return values

    def _build_verification_block(
        self,
        verification: Dict,
        successful_queries: List[Dict],
        failed_queries: List[Dict],
    ) -> str:
        """
        Construye el bloque Markdown de verificación para mostrar al usuario.

        El bloque incluye:
        - Sello de fiabilidad (✅/⚠️/❌)
        - Número de consultas exitosas vs fallidas
        - Valores verificados vs no verificados
        - Aviso si hay valores no verificados
        """
        reliability = verification.get("reliability", "no_data")
        verified_count = verification.get("verified_count", 0)
        total_checked = verification.get("total_checked", 0)
        invented_values = verification.get("invented_values", [])
        invented_count = verification.get("invented_count", 0)

        n_ok = len(successful_queries)
        n_fail = len(failed_queries)
        n_total = n_ok + n_fail

        # Sello de fiabilidad
        if reliability == "alta":
            sello = "✅ **Datos verificados** — todos los valores provienen de la base de datos real"
            sello_icon = "✅"
        elif reliability == "media":
            sello = "⚠️ **Datos mayormente verificados** — algunos valores pueden ser aproximados"
            sello_icon = "⚠️"
        elif reliability == "no_data":
            sello = "❌ **Sin datos verificables** — las consultas no devolvieron resultados"
            sello_icon = "❌"
        elif reliability == "no_table":
            sello = "ℹ️ **Respuesta sin tabla** — verificación no aplicable"
            sello_icon = "ℹ️"
        else:
            sello = "⚠️ **Fiabilidad reducida** — algunos valores no pudieron verificarse"
            sello_icon = "⚠️"

        lines = [
            "---",
            f"### {sello_icon} Verificación de Fiabilidad",
            "",
            f"**{sello}**",
            "",
        ]

        # Estadísticas de consultas
        if n_total > 0:
            lines.append(f"**Consultas ejecutadas:** {n_ok}/{n_total} exitosas")
            if n_fail > 0:
                lines.append(
                    f"> ⚠️ {n_fail} consulta{'s' if n_fail != 1 else ''} no pudo{'dieron' if n_fail != 1 else ''} "
                    f"ejecutarse — los datos de esas consultas no están disponibles."
                )
            lines.append("")

        # Estadísticas de verificación
        if total_checked > 0:
            lines.append(
                f"**Valores verificados:** {verified_count}/{total_checked} "
                f"({'100%' if total_checked == verified_count else f'{int(verified_count/total_checked*100)}%'})"
            )
            lines.append("")

        # Aviso si hay valores no verificados
        if invented_count > 0 and invented_values:
            lines.append(
                f"> ⚠️ **{invented_count} valor{'es' if invented_count != 1 else ''} no verificado{'s' if invented_count != 1 else ''}** "
                f"— no aparece{'n' if invented_count != 1 else ''} en los datos de la base de datos. "
                f"Toma estos valores con precaución."
            )
            lines.append("")

        # Nota sobre el modo simulación
        lines.extend([
            "> 📌 **Nota:** Los datos mostrados provienen del simulador de base de datos JDDC.",
            "> Los valores reales pueden diferir si la base de datos ha cambiado desde la última sincronización.",
        ])

        return "\n".join(lines)
