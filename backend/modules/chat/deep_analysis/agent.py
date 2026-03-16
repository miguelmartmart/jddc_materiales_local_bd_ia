"""
agent.py — DeepAnalysisAgent: orquestador principal del análisis épico multi-fase.

Hereda de:
  Phases12Mixin  (phases_1_2.py) — Fases 0, 1, 2
  Phases345Mixin (phases_3_4_5.py) — Fases 3, 4, 5

Responsabilidades:
  - Inicialización (orchestrator, db_context, budget, sql_normalizer)
  - Integración con SIUO (ContextRetriever) para contexto jerárquico
  - Orquestación de las 5 fases con resiliencia total
  - Helpers compartidos (_safe_sql, _parse_json, _fmt_*, _build_warnings_html)
  - Fallback de emergencia si todo falla
  - Limpieza de ficheros temporales al finalizar
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.modules.chat.deep_analysis.models import (
    AnalysisDepth, DEPTH_CONFIG, EpicAnalysisResult, TokenBudget,
    detect_depth, DEFAULT_CONTEXT_LIMIT_TOKENS,
)
from backend.modules.chat.deep_analysis.phases_1_2 import Phases12Mixin
from backend.modules.chat.deep_analysis.phases_3_4_5 import Phases345Mixin

logger = logging.getLogger(__name__)


class DeepAnalysisAgent(Phases12Mixin, Phases345Mixin):
    """
    Agente de análisis profundo multi-fase ÉPICO v2.0.

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

        logger.info("[DEEP AGENT] DeepAnalysisAgent v2.0 inicializado")

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
        Ejecuta el análisis épico multi-fase.

        Args:
            question:             Pregunta del usuario en lenguaje natural.
            conversation_history: Historial de conversación previo (para contexto acumulado).
            depth:                Nivel de profundidad (auto-detectado si None).

        Returns:
            Respuesta final en Markdown con análisis completo.
        """
        conversation_history = conversation_history or []
        detected_depth = depth or detect_depth(question)
        cfg = dict(DEPTH_CONFIG[detected_depth])  # copia mutable

        result = EpicAnalysisResult(question=question, depth=detected_depth)
        logger.info(
            f"[DEEP AGENT] ══════════════════════════════════════════\n"
            f"[DEEP AGENT] ANÁLISIS ÉPICO: '{question[:80]}'\n"
            f"[DEEP AGENT] Profundidad: {detected_depth.value.upper()} | "
            f"max_sqls={cfg['max_sqls']} | explore_tables={cfg['explore_tables']}\n"
            f"[DEEP AGENT] Historial: {len(conversation_history)} mensajes\n"
            f"[DEEP AGENT] ══════════════════════════════════════════"
        )

        try:
            # FASE 0: Ajuste de presupuesto de tokens
            cfg = self._phase0_budget(cfg, question, conversation_history)

            # FASE 1: Comprensión épica
            phase1 = await self._phase1_understand(question, result, cfg, conversation_history)
            result.phases.append(phase1)
            phase1_data = phase1.data or {}

            # FASE 2: Exploración total
            phase2 = await self._phase2_explore(question, phase1_data, result, cfg)
            result.phases.append(phase2)
            phase2_data = phase2.data or {}

            # FASE 3: Investigación multi-angular
            phase3 = await self._phase3_investigate(question, phase1_data, phase2_data, result, cfg)
            result.phases.append(phase3)

            # FASE 4: Análisis crítico profundo
            phase4 = await self._phase4_analyze(question, result, cfg)
            result.phases.append(phase4)

            # FASE 5: Síntesis épica
            phase5 = await self._phase5_synthesize(question, result, cfg)
            result.phases.append(phase5)

            # Limpieza de ficheros temporales
            self._cleanup_partial_files(result)

            if result.final_answer:
                logger.info(
                    f"[DEEP AGENT] ✅ Análisis completado: "
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
            # Intentar parsear directamente
            return json.loads(text.strip())
        except Exception:
            pass
        # Buscar bloque JSON en el texto
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
        for msg in history[-6:]:  # últimos 6 mensajes
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
            if error:
                lines.append(f"• [{objetivo}] ERROR: {error}")
            else:
                lines.append(f"• [{objetivo}] {rows} filas")
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

    # Ruta al fichero de metadatos persistente (misma que sql_corrector.py)
    _METADATA_PATH = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "core", "config", "db_metadata_optimized.json"
    ))

    def _load_metadata_json(self) -> Dict:
        """
        Carga db_metadata_optimized.json de forma segura.
        Devuelve {} si no existe o está corrupto.
        Ultra-resiliente: nunca lanza excepción.
        """
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
        """
        Obtiene columnas de una tabla desde db_metadata_optimized.json.

        Estructura esperada del JSON:
          {"tables": {"DOCCAB": {"columns": ["TIPO", "FECHA", ...], ...}}}
          o {"tables": {"DOCCAB": [{"name": "TIPO"}, ...]}}

        Devuelve lista vacía si no encuentra nada.
        Ultra-resiliente: nunca lanza excepción.
        """
        try:
            meta = self._load_metadata_json()
            tables = meta.get("tables", {})
            table_data = tables.get(table) or tables.get(table.upper()) or tables.get(table.lower())
            if not table_data:
                return []

            # Formato 1: {"columns": ["COL1", "COL2", ...]}
            if isinstance(table_data, dict):
                cols = table_data.get("columns", [])
                if cols and isinstance(cols, list):
                    # Puede ser lista de strings o lista de dicts {"name": "COL"}
                    result = []
                    for c in cols:
                        if isinstance(c, str):
                            result.append(c.strip())
                        elif isinstance(c, dict):
                            name = c.get("name") or c.get("column_name") or c.get("col")
                            if name:
                                result.append(str(name).strip())
                    return [c for c in result if c]

            # Formato 2: lista directa de dicts [{"name": "COL1"}, ...]
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
        """
        Obtiene el conteo de registros de una tabla desde db_metadata_optimized.json.

        IMPORTANTE: Este conteo es de los metadatos SIUO (muestras), NO de la BD real.
        Solo se usa como fallback cuando la BD no está disponible.

        Devuelve None si no encuentra el dato.
        Ultra-resiliente: nunca lanza excepción.
        """
        try:
            meta = self._load_metadata_json()
            tables = meta.get("tables", {})
            table_data = tables.get(table) or tables.get(table.upper()) or tables.get(table.lower())
            if not table_data or not isinstance(table_data, dict):
                return None

            # Buscar en varios campos posibles
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

    def _extract_columns_from_context(self, table: str) -> List[str]:
        """
        Extrae columnas de una tabla desde el texto libre de db_context.

        Busca patrones como:
          - "DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL"
          - "TABLA: DOCCAB\nColumnas: TIPO, FECHA"
          - "DOCCAB (TIPO, FECHA, IMPORTETOTAL)"
          - "DOCCAB: TIPO | FECHA | IMPORTETOTAL"

        Devuelve lista vacía si no encuentra nada.
        Ultra-resiliente: nunca lanza excepción.
        """
        if not self.db_context or not table:
            return []
        try:
            ctx = self.db_context
            table_upper = table.upper()

            # Patrón 1: "TABLA | Cols: COL1, COL2, ..."
            m = re.search(
                rf'{re.escape(table_upper)}\s*\|[^\n]*[Cc]ols?:\s*([^\n|]+)',
                ctx, re.IGNORECASE
            )
            if m:
                return [c.strip() for c in m.group(1).split(",") if c.strip()]

            # Patrón 2: "TABLA (COL1, COL2, ...)"
            m = re.search(
                rf'{re.escape(table_upper)}\s*\(([^)]+)\)',
                ctx, re.IGNORECASE
            )
            if m:
                return [c.strip() for c in m.group(1).split(",") if c.strip()]

            # Patrón 3: "TABLA\nColumnas: COL1, COL2" o "TABLA\nCols: COL1, COL2"
            m = re.search(
                rf'{re.escape(table_upper)}\s*\n\s*[Cc]olumnas?:\s*([^\n]+)',
                ctx, re.IGNORECASE
            )
            if m:
                return [c.strip() for c in m.group(1).split(",") if c.strip()]

            # Patrón 4: "TABLA: COL1 | COL2 | COL3" (separado por pipes)
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
