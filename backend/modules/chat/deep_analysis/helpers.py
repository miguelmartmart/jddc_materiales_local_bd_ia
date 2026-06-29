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
        """
        Ejecuta SQL de forma segura aplicando normalización previa.

        Flujo de normalización:
        1. sql_normalizer.normalize() — correcciones semánticas (columnas, tablas, etc.)
           NOTA: el normalizer convierte LIMIT→FIRST (sintaxis Firebird). Si el executor
           es el simulador SQLite, el driver ya aplica translate_firebird_sql internamente
           (FIRST→LIMIT), por lo que el resultado es correcto.
        2. Si el simulador está activo Y el executor NO es el driver del simulador
           (caso: executor externo), aplicar translate_firebird_sql explícitamente
           para garantizar compatibilidad SQLite.
        """
        if not self.sql_executor:
            raise RuntimeError("sql_executor no configurado")

        # Paso 1: Normalización semántica (Firebird-oriented)
        if self.sql_normalizer:
            try:
                sql_norm, changes = self.sql_normalizer.normalize(sql)
                if changes:
                    logger.debug(
                        f"[DEEP AGENT] sql_normalizer aplicó {len(changes)} cambios: "
                        f"{', '.join(changes[:3])}"
                    )
                sql = sql_norm
            except Exception as norm_err:
                logger.warning(f"[DEEP AGENT] sql_normalizer falló ({norm_err}), usando SQL original")

        # Paso 2: Si el simulador está activo, garantizar sintaxis SQLite
        # El driver del simulador aplica translate_firebird_sql internamente,
        # pero si el executor es un wrapper externo puede no hacerlo.
        # Aplicamos la traducción aquí como capa de seguridad adicional.
        try:
            from backend.modules.db_simulator.manager import simulator_manager as _sm
            if _sm.is_enabled():
                from backend.modules.db_simulator.query_translator import translate_firebird_sql
                sql_sqlite, sqlite_changes = translate_firebird_sql(sql)
                if sqlite_changes:
                    logger.debug(
                        f"[DEEP AGENT] translate_firebird_sql (simulador): "
                        f"{', '.join(sqlite_changes[:3])}"
                    )
                    sql = sql_sqlite

                # Paso 3: Validar tablas contra el esquema del simulador
                # Si la IA genera SQL con tablas que no existen en el simulador
                # (ej: DOCVAR, C, REPARA), lanzar error descriptivo en lugar de
                # dejar que SQLite falle con "no such table: X".
                # IMPORTANTE: ValueError se propaga — el corrector SQL lo captura
                # y pide a la IA que reescriba la consulta con tablas válidas.
                sql = self._validate_and_fix_tables_for_simulator(sql)
        except ValueError:
            # Tabla desconocida — propagar para que el corrector SQL actúe
            raise
        except Exception as trans_err:
            logger.debug(f"[DEEP AGENT] translate_firebird_sql no aplicado: {trans_err}")

        return self.sql_executor(sql)

    # ── Tablas conocidas del simulador (sincronizado con schema.py) ───────────
    # Se usa para validar SQL antes de ejecutar y evitar "no such table: X".
    _SIMULATOR_TABLES = frozenset({
        "FAMILIA", "ALMACEN", "RECURSO", "PROVEED", "ARTICULO", "CLIENTE",
        "DOCCAB", "DOCLIN", "CAJA", "ESTALMACEN", "PROYECTOS", "PROYVAR",
        "PRESUPROYE", "DOCDESTINO", "AGENTES", "TIPOSIVA", "TARIFAS",
        "FORMASPAGO", "SERIES", "AVISOS",
    })

    # Mapa de tablas Firebird-only → equivalente en simulador (o None si no hay)
    _FIREBIRD_TABLE_ALIASES: Dict[str, Optional[str]] = {
        "DOCVAR":    None,       # Variables de documento — no existe en simulador
        "C":         "CLIENTE",  # Alias frecuente de CLIENTE
        "REPARA":    None,       # Reparaciones — no existe en simulador
        "REPARACION": None,
        "PEDIDOS":   "DOCCAB",   # Pedidos son DOCCAB con TIPO específico
        "FACTURAS":  "DOCCAB",   # Facturas son DOCCAB con TIPO específico
        "PRESUPUESTOS": "DOCCAB",# Presupuestos son DOCCAB con TIPO específico
        "ALBARANES": "DOCCAB",   # Albaranes son DOCCAB con TIPO específico
        "COMPRAS":   "DOCCAB",   # Compras son DOCCAB con TIPO específico
        "ARTICULOS": "ARTICULO", # Plural → singular
        "CLIENTES":  "CLIENTE",  # Plural → singular
        "PROVEEDORES": "PROVEED",# Plural → abreviado
        "AGENTE":    "AGENTES",  # Singular → plural
    }

    def _validate_and_fix_tables_for_simulator(self, sql: str) -> str:
        """
        Valida las tablas referenciadas en el SQL contra el esquema del simulador.

        Si encuentra tablas desconocidas:
        1. Intenta sustituirlas por el equivalente conocido (_FIREBIRD_TABLE_ALIASES)
        2. Si no hay equivalente, lanza ValueError con mensaje descriptivo
           para que el corrector SQL pueda actuar antes de mostrar error al usuario.

        Principio: el usuario NUNCA debe ver "no such table: X" — el sistema
        debe detectarlo antes y corregirlo o informar de forma útil.
        """
        import re
        # Extraer nombres de tablas del SQL (FROM y JOIN)
        _from_join_re = re.compile(
            r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)',
            re.IGNORECASE
        )
        # Palabras clave SQL que no son tablas
        _SQL_KEYWORDS = frozenset({
            'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS',
            'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'NATURAL',
            'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'CURRENT_TIME',
            'DUAL', 'SYSIBM',
        })

        # Extraer nombres de CTEs (WITH name AS ...) para no confundirlos con tablas reales
        _cte_re = re.compile(r'\bWITH\s+(\w+)\s+AS\s*\(', re.IGNORECASE)
        cte_names = {m.group(1).upper() for m in _cte_re.finditer(sql)}
        # También detectar CTEs adicionales en la cláusula WITH (coma, nombre AS)
        _cte_comma_re = re.compile(r',\s*(\w+)\s+AS\s*\(', re.IGNORECASE)
        cte_names.update(m.group(1).upper() for m in _cte_comma_re.finditer(sql))

        tables_in_sql = [
            m.group(1).upper()
            for m in _from_join_re.finditer(sql)
            if m.group(1).upper() not in _SQL_KEYWORDS
            and m.group(1).upper() not in cte_names  # excluir CTEs definidas en este SQL
        ]

        unknown_tables = [
            t for t in tables_in_sql
            if t not in self._SIMULATOR_TABLES
        ]

        if not unknown_tables:
            return sql  # Todo OK

        # Intentar sustituir tablas desconocidas por equivalentes
        fixed_sql = sql
        truly_unknown = []
        for table in unknown_tables:
            alias = self._FIREBIRD_TABLE_ALIASES.get(table)
            if alias is not None:
                # Sustituir en el SQL (case-insensitive, palabra completa)
                fixed_sql = re.sub(
                    rf'\b{re.escape(table)}\b',
                    alias,
                    fixed_sql,
                    flags=re.IGNORECASE
                )
                logger.info(
                    f"[DEEP AGENT] Tabla simulador: {table} → {alias} (alias automático)"
                )
            else:
                truly_unknown.append(table)

        if truly_unknown:
            # Tablas sin equivalente — lanzar error descriptivo para el corrector
            # NOTA: no incluir "Tablas disponibles" en el mensaje de error que va al usuario
            # porque el AI de síntesis las lee y puede inventar más nombres a partir de esa lista
            raise ValueError(
                f"Tabla(s) no disponible(s) en el simulador: {', '.join(truly_unknown)}. "
                f"Usa solo: {', '.join(sorted(self._SIMULATOR_TABLES))}."
            )

        return fixed_sql

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
            # Defensa: tipo_distribution debe ser lista de dicts; ignorar si es dict o incorrecto
            if tipo_dist and isinstance(tipo_dist, list):
                try:
                    tipo_str = " | TIPOS: " + ", ".join(
                        f"TIPO={r.get('TIPO','?')}:{r.get('N','?')}" for r in tipo_dist[:5]
                    )
                except Exception:
                    tipo_str = ""
            null_cc = info.get("null_codcliente")
            null_str = f" | NULOS_CODCLIENTE={null_cc}" if null_cc is not None else ""
            lines.append(f"• {table}: {total} registros | Cols: {cols}{tipo_str}{null_str}")
        return "\n".join(lines)

    # ── Constante centralizada: nombres de meses en español ──────────────────
    _MESES_ES = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }

    @classmethod
    def _format_row_values(cls, row: Dict) -> Dict:
        """
        Formatea valores de una fila de resultados SQL de forma determinista.

        Transformaciones aplicadas:
          - Columnas MES/MONTH con valor 1-12 → nombre del mes en español
          - Importes float → formato europeo (1.234,56)
          - None → '(sin datos)'

        Principio DEVIA: lógica determinista centralizada, sin IA, reutilizable.
        """
        formatted = {}
        for col, val in row.items():
            col_upper = col.upper()
            if val is None:
                formatted[col] = "(sin datos)"
            elif col_upper in ("MES", "MONTH", "NUMERO_MES", "NUM_MES") and isinstance(val, (int, float)):
                mes_num = int(val)
                formatted[col] = cls._MESES_ES.get(mes_num, str(mes_num))
            elif isinstance(val, float) and any(k in col_upper for k in (
                "IMPORTE", "TOTAL", "PRECIO", "COSTE", "PROMEDIO", "MEDIA",
                "EUR", "FACTURA", "SUMA", "MONTO",
            )):
                # Formato europeo: 1.234,56
                formatted[col] = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                formatted[col] = val
        return formatted

    def _fmt_investigation(self, sql_queries: List[Dict]) -> str:
        """
        Formatea los resultados de investigación para prompts.

        Aplica _format_row_values() a cada fila para que la IA reciba
        los datos ya formateados (meses en español, importes en formato europeo).

        IMPORTANTE: Los datos se formatean como texto legible (col: valor),
        NO como dicts Python crudos. Esto evita que la IA repita literalmente
        "{col: val, col2: val2}" en la respuesta al usuario.
        """
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
                lines.append(f"• [{objetivo}]{is_res} {rows} resultado{'s' if rows != 1 else ''}")
                for row in data[:3]:
                    formatted = self._format_row_values(row)
                    # Formatear como "col1=val1, col2=val2" en lugar de dict Python
                    row_str = ", ".join(
                        f"{k}={v}" for k, v in formatted.items()
                        if v is not None and str(v) not in ("", "(sin datos)")
                    )
                    if row_str:
                        lines.append(f"  → {row_str}")
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
        """
        Respuesta de emergencia si la síntesis IA falla — siempre devuelve algo útil.

        Lógica de mensajes:
          - Si hay datos SQL exitosos + IA falló → mostrar datos formateados con nota de síntesis parcial
          - Si IA completamente inaccesible (ai_unavailable=True) → aviso claro de servidor caído
          - Si no hay datos ni IA → mensaje de fallo total

        Principio DEVIA: nunca mostrar datos crudos sin contexto; siempre formatear.
        """
        from datetime import datetime
        _now = datetime.now().strftime("%d/%m/%Y %H:%M")
        parts = [f"## 📊 {result.question}\n"]

        ai_down = getattr(result, "ai_unavailable", False)
        successful = [q for q in result.sql_queries if not q.get("error")] if result.sql_queries else []
        failed = [q for q in result.sql_queries if q.get("error")] if result.sql_queries else []

        # ── Caso 1: Hay datos pero la síntesis IA falló ──────────────────────
        if successful and not ai_down:
            parts.append(
                f"> ℹ️ **Datos obtenidos correctamente** ({len(successful)} consulta"
                f"{'s' if len(successful) != 1 else ''} exitosa{'s' if len(successful) != 1 else ''})."
                f" La síntesis automática no pudo completarse — se muestran los datos directos.\n"
            )
            for q in successful[:6]:
                objetivo = q.get("objetivo", "?")
                rows = q.get("rows", 0)
                data = q.get("data", [])
                parts.append(f"\n**{objetivo}** — {rows} resultado{'s' if rows != 1 else ''}")
                if data:
                    # Construir tabla Markdown con los datos formateados
                    first_row = self._format_row_values(data[0])
                    headers = list(first_row.keys())
                    parts.append("| " + " | ".join(headers) + " |")
                    parts.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in data[:10]:
                        fmt = self._format_row_values(row)
                        parts.append("| " + " | ".join(str(fmt.get(h, "")) for h in headers) + " |")
                parts.append("")

        # ── Caso 2: IA completamente inaccesible ─────────────────────────────
        elif ai_down:
            parts.append(
                "> ❌ **El servidor de IA no está disponible en este momento.**\n"
                "> Comprueba que el servidor Qwen3 esté activo e inténtalo de nuevo.\n"
            )
            if successful:
                parts.append(
                    f"Se obtuvieron **{len(successful)} consulta"
                    f"{'s' if len(successful) != 1 else ''}** de la base de datos "
                    f"(sin interpretación IA):\n"
                )
                for q in successful[:5]:
                    objetivo = q.get("objetivo", "?")
                    rows = q.get("rows", 0)
                    data = q.get("data", [])
                    parts.append(f"\n**{objetivo}** — {rows} resultado{'s' if rows != 1 else ''}")
                    if data:
                        first_row = self._format_row_values(data[0])
                        headers = list(first_row.keys())
                        parts.append("| " + " | ".join(headers) + " |")
                        parts.append("| " + " | ".join(["---"] * len(headers)) + " |")
                        for row in data[:5]:
                            fmt = self._format_row_values(row)
                            parts.append("| " + " | ".join(str(fmt.get(h, "")) for h in headers) + " |")
                    parts.append("")

        # ── Caso 3: Sin datos ni IA ───────────────────────────────────────────
        else:
            parts.append(
                "> ❌ No se pudieron obtener datos ni generar una respuesta.\n"
                "> Comprueba la conexión a la base de datos e inténtalo de nuevo."
            )

        # ── Consultas con error (siempre mostrar si las hay) ─────────────────
        if failed:
            parts.append(f"\n**Consultas con error ({len(failed)}):**")
            for q in failed[:3]:
                parts.append(f"- ❌ {q.get('objetivo', '?')}: `{q.get('error', '')}`")

        # ── Advertencias relevantes ───────────────────────────────────────────
        real_warnings = [
            w for w in result.warnings[:3]
            if isinstance(w, str) and not w.startswith("⚠️ ANOMALÍA")
        ]
        if real_warnings:
            parts.append("\n**⚠️ Advertencias:**")
            parts.extend(f"- {w}" for w in real_warnings)

        parts.append(f"\n*Análisis generado: {_now}*")
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
