"""
phase2_explore.py — Exploración de tablas para Fase 2 del DeepAnalysisAgent.

Contiene:
  - _explore_table(): conteo, columnas, muestreo, distribución TIPO, nulos
    con CACHE-FIRST (KnowledgeStore) y resiliencia multi-fuente de metadatos
  - _ask_for_extra_tables(): expansión dinámica de tablas via IA

Fuentes de metadatos (en orden de prioridad):
  1. KnowledgeStore (cache, si datos < 7 días)
  2. RDB$RELATION_FIELDS (BD real Firebird)
  3. db_metadata_optimized.json (SIUO)
  4. db_context texto (esquema cargado en el agente)
"""

import logging
from typing import Dict, List

try:
    from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
except ImportError:
    get_knowledge_store = None  # type: ignore

logger = logging.getLogger(__name__)


class Phase2ExploreMixin:
    """
    Mixin con la exploración de tablas para Fase 2.
    Requiere: self._safe_sql(), self._get_siuo_columns(),
              self._get_siuo_record_count(), self._extract_columns_from_context(),
              self._fmt_exploration(), self.budget, self.db_context,
              self.orchestrator, self._parse_json()
    """

    async def _explore_table(self, table: str, cfg: Dict) -> Dict:
        """
        Explora una tabla: conteo, columnas, muestreo, distribución TIPO, nulos.

        CACHE-FIRST: Si el KnowledgeStore tiene datos frescos (< 7 días), los usa
        directamente sin queries a la BD. Solo re-explora si los datos son obsoletos
        o cfg["force_refresh"] es True.

        RESILIENCIA MULTI-FUENTE:
          1. KnowledgeStore (cache)
          2. RDB$RELATION_FIELDS (BD real)
          3. db_metadata_optimized.json (SIUO)
          4. db_context texto
        """
        info: Dict = {}

        # ── CACHE-FIRST ───────────────────────────────────────────────────────
        if not cfg.get("force_refresh", False):
            try:
                if get_knowledge_store is not None:
                    store = get_knowledge_store()
                    cached = store.get_table(table)
                    if cached and cached.get("columns_real") and cached.get("record_count_real") is not None:
                        from datetime import datetime, timedelta
                        updated_at_str = cached.get("_updated_at", "")
                        is_fresh = False
                        if updated_at_str:
                            try:
                                updated_at = datetime.fromisoformat(updated_at_str)
                                is_fresh = (datetime.now() - updated_at) < timedelta(days=7)
                            except Exception:
                                is_fresh = False

                        if is_fresh:
                            logger.info(
                                f"[DEEP AGENT] CACHE HIT: {table} — "
                                f"{cached['record_count_real']} registros, "
                                f"{len(cached['columns_real'])} columnas"
                            )
                            info["total"] = cached["record_count_real"]
                            info["total_source"] = "knowledge_store_cache"
                            info["columns"] = cached["columns_real"]
                            info["columns_source"] = "knowledge_store_cache"
                            cols_upper = [c.upper() for c in info["columns"]]
                            info["has_fecha"]      = "FECHA" in cols_upper
                            info["has_importe"]    = any(c in cols_upper for c in ["IMPORTETOTAL", "IMPORTE", "TOTAL"])
                            info["has_codcliente"] = "CODCLIENTE" in cols_upper
                            info["has_tipo"]       = "TIPO" in cols_upper
                            info["has_codigoobra"] = "CODIGOOBRA" in cols_upper
                            info["has_serie"]      = "SERIE" in cols_upper
                            if cached.get("tipo_distribution"):
                                info["tipo_distribution"] = cached["tipo_distribution"]
                            if cached.get("null_codcliente") is not None:
                                info["null_codcliente"] = cached["null_codcliente"]
                            if cached.get("sample"):
                                info["sample"] = cached["sample"]
                            info["_from_cache"] = True
                            return info
                        else:
                            logger.info(f"[DEEP AGENT] CACHE STALE: {table} — re-explorando...")
            except Exception as e:
                logger.debug(f"[DEEP AGENT] KnowledgeStore cache check falló para {table}: {e}")

        # ── EXPLORACIÓN REAL ──────────────────────────────────────────────────
        logger.info(f"[DEEP AGENT] Explorando tabla {table} desde BD...")

        # Conteo de registros
        try:
            r = await self._safe_sql(f"SELECT COUNT(*) AS TOTAL FROM {table}")
            info["total"] = r[0].get("TOTAL", 0) if r else 0
        except Exception as e:
            info["total"] = f"ERROR: {e}"
            try:
                siuo_count = self._get_siuo_record_count(table)
                if siuo_count is not None:
                    info["total_siuo"] = siuo_count
                    info["total_source"] = "siuo_metadata"
            except Exception:
                pass

        # Columnas — Fuente 1: RDB$RELATION_FIELDS
        columns_from_db = []
        try:
            r = await self._safe_sql(
                f"SELECT TRIM(RDB$FIELD_NAME) AS COL FROM RDB$RELATION_FIELDS "
                f"WHERE TRIM(RDB$RELATION_NAME)='{table}' ORDER BY RDB$FIELD_POSITION"
            )
            columns_from_db = [row.get("COL", "") for row in r] if r else []
        except Exception as e:
            logger.warning(f"[DEEP AGENT] RDB$RELATION_FIELDS falló para {table}: {e}")

        if columns_from_db:
            info["columns"] = columns_from_db
            info["columns_source"] = "firebird_rdb"
        else:
            # Fuente 2: SIUO JSON
            siuo_cols = self._get_siuo_columns(table)
            if siuo_cols:
                info["columns"] = siuo_cols
                info["columns_source"] = "siuo_metadata"
            else:
                # Fuente 3: db_context texto
                ctx_cols = self._extract_columns_from_context(table)
                if ctx_cols:
                    info["columns"] = ctx_cols
                    info["columns_source"] = "db_context_text"
                else:
                    info["columns"] = []
                    info["columns_source"] = "unknown"

        # Detección de columnas clave
        cols_upper = [c.upper() for c in info.get("columns", [])]
        info["has_fecha"]      = "FECHA" in cols_upper
        info["has_importe"]    = any(c in cols_upper for c in ["IMPORTETOTAL", "IMPORTE", "TOTAL"])
        info["has_codcliente"] = "CODCLIENTE" in cols_upper
        info["has_tipo"]       = "TIPO" in cols_upper
        info["has_codigoobra"] = "CODIGOOBRA" in cols_upper
        info["has_serie"]      = "SERIE" in cols_upper

        # Muestreo (solo DEEP/EPIC)
        if cfg["max_sqls"] >= 8:
            try:
                cols_sample = ", ".join(info["columns"][:6]) if info["columns"] else "*"
                r = await self._safe_sql(f"SELECT FIRST 3 {cols_sample} FROM {table}")
                info["sample"] = r[:3] if r else []
            except Exception:
                info["sample"] = []

        # Distribución por TIPO (solo DOCCAB)
        if info.get("has_tipo") and table == "DOCCAB":
            try:
                r = await self._safe_sql("SELECT TIPO, COUNT(*) AS N FROM DOCCAB GROUP BY TIPO ORDER BY N DESC")
                info["tipo_distribution"] = r[:10] if r else []
            except Exception:
                info["tipo_distribution"] = []

        # Nulos en CODCLIENTE
        if info.get("has_codcliente") and cfg["max_sqls"] >= 6:
            try:
                r = await self._safe_sql(f"SELECT COUNT(*) AS NULOS FROM {table} WHERE CODCLIENTE IS NULL")
                info["null_codcliente"] = r[0].get("NULOS", 0) if r else 0
            except Exception:
                info["null_codcliente"] = "?"

        # ── PERSISTIR en KnowledgeStore ───────────────────────────────────────
        try:
            if get_knowledge_store is not None and info.get("columns"):
                store = get_knowledge_store()
                updates: Dict = {}
                if info.get("columns_source") == "firebird_rdb":
                    updates["columns_real"] = info["columns"]
                if isinstance(info.get("total"), int):
                    updates["record_count_real"] = info["total"]
                if info.get("tipo_distribution"):
                    updates["tipo_distribution"] = info["tipo_distribution"]
                if info.get("null_codcliente") is not None and info.get("null_codcliente") != "?":
                    updates["null_codcliente"] = info["null_codcliente"]
                if info.get("sample"):
                    updates["sample"] = info["sample"]
                if updates:
                    store.update_table(table, updates)
                    store.log_discovery(
                        "record_count" if "record_count_real" in updates else "columns_real",
                        table,
                        {"record_count": updates.get("record_count_real"),
                         "columns_count": len(info.get("columns", []))},
                    )
        except Exception as e:
            logger.debug(f"[DEEP AGENT] No se pudo persistir {table} en KnowledgeStore: {e}")

        return info

    async def _ask_for_extra_tables(
        self, question: str, exploration: Dict, cfg: Dict
    ) -> List[str]:
        """Pregunta a la IA si necesita explorar tablas adicionales."""
        try:
            explored = list(exploration.keys())
            exploration_summary = self._fmt_exploration(exploration)
            schema_snippet = self.budget.truncate_to_fit(
                self.db_context[:3000], exploration_summary, question
            )
            system = (
                "Eres un experto en Firebird 2.5. Indica qué tablas adicionales se necesitan "
                "para responder la pregunta. Responde SOLO JSON array (máximo 4): "
                '[\"TABLA1\"] o [] si no se necesitan más.'
            )
            user_msg = (
                f"PREGUNTA: {question}\n\nTABLAS YA EXPLORADAS: {explored}\n\n"
                f"RESUMEN:\n{exploration_summary}\n\nESQUEMA:\n{schema_snippet}"
            )
            resp, _ = await self.orchestrator.execute_with_fallback(
                system_prompt=system, user_message=user_msg, preferred_model_id="jddcia-qwen3-30b"
            )
            extra = self._parse_json(resp)
            if isinstance(extra, list):
                new_tables = [t for t in extra if t not in exploration][:4]
                if new_tables:
                    logger.info(f"[DEEP AGENT] IA solicita tablas adicionales: {new_tables}")
                return new_tables
        except Exception as e:
            logger.warning(f"[DEEP AGENT] No se pudieron obtener tablas adicionales: {e}")
        return []
