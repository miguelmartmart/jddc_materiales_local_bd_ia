"""
helpers.py — Helpers compartidos del DeepAnalysisAgent.

Contiene:
  - _safe_sql, _parse_json, _ai_fix_sql
  - _fmt_conversation_history, _fmt_exploration, _fmt_investigation
  - _build_warnings_html (Markdown puro, sin HTML)
  - _emergency_fallback
  - _METADATA_PATH, _load_metadata_json, _get_siuo_columns, _get_siuo_record_count
  - _extract_columns_from_context
  - _phase0_lan_optimize

Todos estos métodos se inyectan en DeepAnalysisAgent via HelpersAgentMixin.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HelpersAgentMixin:
    """
    Mixin con helpers compartidos para DeepAnalysisAgent.
    Requiere que la clase base tenga:
      self.orchestrator, self.db_context, self.budget, self.sql_executor
    """

    # ─────────────────────────────────────────────────────────────────────────
    # SQL + JSON
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

    # ─────────────────────────────────────────────────────────────────────────
    # FORMATEO DE DATOS PARA PROMPTS
    # ─────────────────────────────────────────────────────────────────────────

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

    # ─────────────────────────────────────────────────────────────────────────
    # WARNINGS Y FALLBACK
    # ─────────────────────────────────────────────────────────────────────────

    def _build_warnings_html(self, result) -> str:
        """
        Construye bloque Markdown de advertencias (NO HTML) para el frontend.

        PROBLEMA ANTERIOR: Se generaba HTML con <div> y las anomalías eran
        objetos Python serializados como str (ej: {'type': ..., 'description': ...}).
        SOLUCIÓN: Usar Markdown puro + extraer texto legible de dicts/strings.
        """
        if not result.warnings and not result.anomalies:
            return ""

        def _to_text(item) -> str:
            if isinstance(item, str):
                return item.strip()
            if isinstance(item, dict):
                for field in ("description", "details", "message", "text", "rule", "reason"):
                    val = item.get(field)
                    if val and isinstance(val, str) and len(val) > 5:
                        return val.strip()
                parts = []
                for k, v in item.items():
                    if k not in ("type", "column", "table", "impact") and v:
                        parts.append(f"{v}")
                return " — ".join(parts[:2]) if parts else str(item)
            return str(item)

        lines = []
        if result.anomalies:
            lines.append("### 🔴 Anomalías detectadas")
            for a in result.anomalies[:5]:
                text = _to_text(a)
                if text:
                    lines.append(f"- {text}")
            lines.append("")

        if result.warnings:
            lines.append("### ⚠️ Advertencias")
            for w in result.warnings[:5]:
                text = _to_text(w)
                if text:
                    lines.append(f"- {text}")
            lines.append("")

        return "\n".join(lines)

    def _emergency_fallback(self, result) -> str:
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
    # METADATOS SIUO (resiliencia multi-fuente)
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
            table_data = (
                tables.get(table)
                or tables.get(table.upper())
                or tables.get(table.lower())
            )
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

    def _get_siuo_record_count(self, table: str):
        try:
            meta = self._load_metadata_json()
            tables = meta.get("tables", {})
            table_data = (
                tables.get(table)
                or tables.get(table.upper())
                or tables.get(table.lower())
            )
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

    # ─────────────────────────────────────────────────────────────────────────
    # OPTIMIZACIÓN LAN
    # ─────────────────────────────────────────────────────────────────────────

    def _phase0_lan_optimize(self, cfg: Dict) -> Dict:
        """
        Detecta si se usa modelo LAN y ajusta cfg en consecuencia.
        NO reduce max_sqls — solo activa lan_mode y cuenta patrones conocidos.
        """
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
                from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
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
                    f"[DEEP AGENT] Modo LAN | prompt conciso | "
                    f"{known_sqls_count} patrones en KnowledgeStore"
                )
            else:
                logger.info(
                    f"[DEEP AGENT] Modo internet | prompt completo | "
                    f"{known_sqls_count} patrones en KnowledgeStore"
                )
        except Exception as e:
            logger.debug(f"[DEEP AGENT] _phase0_lan_optimize: {e}")
            cfg.setdefault("lan_mode", False)
            cfg.setdefault("known_sqls_count", 0)
        return cfg
