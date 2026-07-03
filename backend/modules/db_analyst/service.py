"""
service.py — AnalystService: núcleo del módulo Analista BD.

Flujo para cada mensaje:
  1. Recuperar contexto SIUO (índices en RAM, <1ms)
  2. Construir system prompt con esquema + reglas SQL
  3. Llamar a Qwen3 LAN via ModelFallbackOrchestrator
  4. Extraer SQL de la respuesta
  5. Normalizar SQL (FirebirdSQLNormalizer, determinista)
  6. Ejecutar con auto-corrección (SQLCorrector, hasta 3 reintentos con IA)
  7. Interpretar resultados con Qwen3 → respuesta con justificación en <details>
  8. Devolver (response_text, Provenance) con toda la trazabilidad

Diferencias respecto a ChatService:
  - Siempre devuelve Provenance completa (SQL, raw_results, tablas, tokens)
  - Sin soporte de imágenes ni voz (módulo solo para análisis de BD)
  - Sin confirmación de datos (transparencia total es el objetivo)
  - Compatible con simulador y BD real mediante la misma interfaz
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.chat.sql_corrector import SQLCorrector
from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
from backend.modules.db_analyst.models import Provenance

logger = logging.getLogger(__name__)

_SYSTEM_INTERPRET = (
    "Eres un analista de datos experto. Interpreta los resultados SQL con visión crítica. "
    "REGLAS: Muestra datos tal cual están en la BD. Nunca inventes datos. "
    "Menciona duplicados, anomalías o calidad de datos si los detectas. "
    "Responde primero directamente a la pregunta, luego justificación en <details>."
)

_SYSTEM_JUSTIFY = (
    "Eres un analista de datos. Tu tarea es EXPLICAR CON DETALLE la evidencia que "
    "respalda una respuesta anterior. Debes mostrar: "
    "el SQL exacto que se ejecutó, de qué tablas provienen los datos, "
    "qué filas específicas justifican la respuesta, y cómo interpretar los valores."
)


class AnalystService:
    """Chat analítico sobre BD simulada/real con procedencia completa."""

    def __init__(self):
        self.sql_normalizer = FirebirdSQLNormalizer()
        self.sql_corrector = SQLCorrector()
        self.orchestrator = ModelFallbackOrchestrator()

    # ── Helpers de BD ─────────────────────────────────────────────────────────

    def _get_data_source(self) -> str:
        try:
            from backend.modules.db_simulator.manager import simulator_manager
            return "simulator" if simulator_manager.is_enabled() else "firebird"
        except Exception:
            return "unknown"

    def _execute_sql_sync(self, query: str) -> List[Dict[str, Any]]:
        from backend.modules.db_simulator.manager import simulator_manager
        if simulator_manager.is_enabled():
            from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
            simulator_manager.ensure_ready()
            drv = SimulatedFirebirdDriver()
            drv.connect()
            try:
                return drv.execute_query(query)
            finally:
                drv.disconnect()
        else:
            from backend.core.factory.db_factory import DBFactory
            from backend.core.abstract.database import DBConfig
            from backend.core.utils.constants import DBConstants
            from backend.core.config.settings import settings
            drv = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
            cfg = DBConfig(
                host=settings.DB_HOST, port=settings.DB_PORT,
                database=settings.DB_NAME, user=settings.DB_USER,
                password=settings.DB_PASSWORD,
            )
            drv.connect(cfg)
            try:
                return drv.execute_query(query)
            finally:
                drv.disconnect()

    async def _execute_sql(self, query: str) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute_sql_sync, query)

    # ── Contexto SIUO ─────────────────────────────────────────────────────────

    def _get_siuo_context(self, message: str) -> Tuple[str, Dict[str, Any]]:
        try:
            from backend.modules.db_explorer.context_retriever import get_context_retriever
            retriever = get_context_retriever()
            return retriever.get_context(message)
        except Exception as e:
            logger.warning(f"[ANALYST] SIUO context failed: {e}, usando fallback")
            from backend.core.config.database_metadata import get_semantic_schema
            return get_semantic_schema(), {"source": "fallback", "tables_used": [], "keywords_found": [], "tokens_estimated": 0}

    # ── System prompt SQL ─────────────────────────────────────────────────────

    def _build_system_prompt(self, db_context: str, history: List[Dict], data_source: str) -> str:
        sim_note = ""
        if data_source == "simulator":
            try:
                from backend.modules.db_simulator.schema import TABLE_SCHEMAS
                sim_tables = ", ".join(sorted(TABLE_SCHEMAS.keys()))
                sim_note = (
                    f"\n⚠️ SIMULADOR ACTIVO (SQLite — snapshot Firebird).\n"
                    f"TABLAS DISPONIBLES (SOLO ESTAS): {sim_tables}\n"
                    f"Usa sintaxis Firebird — el sistema convierte a SQLite.\n"
                )
            except Exception:
                pass

        history_text = ""
        if history:
            recent = history[-6:]
            history_text = "\n\n=== HISTORIAL CONVERSACIÓN ===\n"
            for m in recent:
                role = "Usuario" if m["role"] == "user" else "Asistente"
                history_text += f"{role}: {m['content'][:400]}\n"
            history_text += "=== FIN HISTORIAL ===\n"

        return f"""Firebird 2.5 SQL. Convierte preguntas a SQL válido.
{history_text}
{db_context}{sim_note}
REGLAS (no negociar):
• FIRST N no LIMIT/TOP: SELECT FIRST 10 CODIGO FROM ARTICULO
• UPPER(col) LIKE UPPER('%x%') para búsquedas de texto (Firebird es case-sensitive)
• DOCCAB.TIPO: 13=factura, 12=pedido, 11=albaran, 0=presupuesto, 3=abono, 2=SAT, 10=contrato
• Fechas: EXTRACT(MONTH FROM FECHA), EXTRACT(YEAR FROM FECHA); NO DATEADD dentro de EXTRACT
• Mes pasado: (EXTRACT(YEAR FROM FECHA)*12+EXTRACT(MONTH FROM FECHA))=(EXTRACT(YEAR FROM CURRENT_DATE)*12+EXTRACT(MONTH FROM CURRENT_DATE)-1)
• BLOB (DESCRIPCION en ARTICULO/DOCCAB) → no usar en GROUP BY/ORDER BY si hay GROUP BY
• Delimita SQL con ```sql y ```; si no requiere SQL responde directamente"""

    # ── Proceso principal ──────────────────────────────────────────────────────

    async def process(
        self,
        message: str,
        history: List[Dict[str, str]],
        model_id: Optional[str] = None,
    ) -> Tuple[str, Provenance]:
        """
        Procesa un mensaje y devuelve (response_text, provenance).
        La provenance contiene el SQL, tablas, datos brutos y metadatos SIUO.
        """
        t0 = time.monotonic()
        data_source = self._get_data_source()
        prov = Provenance(data_source=data_source)

        # 1. SIUO context
        db_context, ctx_meta = self._get_siuo_context(message)
        prov.tables_used = ctx_meta.get("tables_used", [])
        prov.siuo_keywords = ctx_meta.get("keywords_found", [])
        prov.siuo_source = ctx_meta.get("source", "unknown")
        prov.context_tokens = ctx_meta.get("tokens_estimated", 0)

        # 2. System prompt
        system_prompt = self._build_system_prompt(db_context, history, data_source)

        # 3. Llamar al modelo
        preferred = model_id or "jddcia-qwen3-30b"
        response_text, used_model = await self.orchestrator.execute_with_fallback(
            system_prompt=system_prompt,
            user_message=message,
            preferred_model_id=preferred,
        )
        prov.model_used = used_model

        if not response_text:
            prov.execution_time_ms = int((time.monotonic() - t0) * 1000)
            prov.requires_db = False
            return "No se pudo generar respuesta (modelo no disponible).", prov

        # 4. ¿Hay SQL?
        sql_blocks = re.findall(r'```sql\s*(.*?)```', response_text, re.DOTALL)
        if not sql_blocks:
            # Respuesta conversacional directa
            prov.requires_db = False
            prov.execution_time_ms = int((time.monotonic() - t0) * 1000)
            return response_text, prov

        # 5. Normalizar SQL
        sql_raw = max(sql_blocks, key=len).strip()
        prov.sql_generated = sql_raw
        sql_normalized, norm_changes = self.sql_normalizer.normalize(sql_raw)
        prov.sql_executed = sql_normalized
        if norm_changes:
            logger.info(f"[ANALYST] {len(norm_changes)} correcciones deterministas SQL")

        # 6. Ejecutar con auto-corrección
        try:
            # Obtener provider para corrección IA (opcional)
            from backend.core.config.model_manager import model_manager
            from backend.core.factory.ai_factory import AIFactory
            from backend.core.abstract.ai import AIConfig
            model_cfg = model_manager.get_model(used_model)
            ai_provider = None
            if model_cfg:
                provider_schema = model_cfg.get("schema", model_cfg.get("provider"))
                ai_provider = AIFactory.get_provider(provider_schema)
                cfg_params = {"api_key": model_cfg.get("api_key"), "model": model_cfg["model_id"]}
                if model_cfg.get("base_url"):
                    cfg_params["base_url"] = model_cfg["base_url"]
                if model_cfg.get("headers"):
                    cfg_params["headers"] = model_cfg["headers"]
                ai_provider.configure(AIConfig(**cfg_params))

            raw_results = await self.sql_corrector.execute_with_correction(
                sql_query=sql_normalized,
                original_question=message,
                db_context=db_context,
                ai_provider=ai_provider,
                execute_func=lambda q: self._execute_sql_sync(q),
                max_retries=3,
            )
        except Exception as e:
            logger.error(f"[ANALYST] SQL error: {e}")
            prov.raw_results = []
            prov.execution_time_ms = int((time.monotonic() - t0) * 1000)
            return (
                f"{response_text}\n\n"
                f"⚠️ **Error ejecutando SQL:** {str(e)}\n\n"
                f"```sql\n{sql_normalized}\n```",
                prov,
            )

        prov.raw_results = raw_results[:50]  # max 50 filas en procedencia

        # 7. Interpretar con Qwen3 → respuesta con <details> de justificación
        n_rows = len(raw_results)
        cols = list(raw_results[0].keys()) if raw_results else []
        preview = raw_results[:10]

        # Tablas detectadas en el SQL para enriquecer la justificación
        try:
            tables_in_sql = self.sql_corrector._extract_tables_from_sql(sql_normalized)
        except Exception:
            tables_in_sql = prov.tables_used

        interp_prompt = (
            f"PREGUNTA DEL USUARIO: {message}\n\n"
            f"SQL EJECUTADO:\n```sql\n{sql_normalized}\n```\n\n"
            f"RESULTADOS ({n_rows} filas, columnas: {', '.join(cols)}):\n{preview}\n\n"
            f"FUENTE DE DATOS: {data_source.upper()}\n\n"
            "Responde con ESTA ESTRUCTURA EXACTA (respeta el HTML):\n\n"
            "[Respuesta directa a la pregunta. Tabla Markdown si hay múltiples filas. "
            "Precios en EUR. Sin inventar datos.]\n\n"
            "<details>\n"
            "<summary>🔍 Ver justificación y fuentes</summary>\n\n"
            f"**Fuente de datos:** {data_source}\n\n"
            f"**Tablas consultadas:** {', '.join(tables_in_sql) if tables_in_sql else '(ver SQL)'}\n\n"
            f"**Columnas devueltas:** {', '.join(cols)}\n\n"
            f"**Registros devueltos:** {n_rows}\n\n"
            "**SQL ejecutado:**\n"
            f"```sql\n{sql_normalized}\n```\n\n"
            "**Cómo verificarlo:** [indica cómo buscar estos datos directamente en la BD, "
            "qué campo clave usar, qué filtro aplicar]\n\n"
            "**Razonamiento:** [explica qué tablas se unieron, qué filtros se aplicaron "
            "y por qué el resultado responde a la pregunta. Si hay datos sospechosos "
            "(negativos, nulos, tablas con pocos registros), indícalos en "
            "<span style='color:#c0392b'>rojo</span>]\n\n"
            "</details>\n\n"
            "REGLAS:\n"
            "1. NO inventes datos. Usa SOLO los resultados proporcionados.\n"
            "2. Si no hay resultados, dilo claramente y sugiere por qué.\n"
            "3. El bloque <details>...</details> debe estar SIEMPRE al final."
        )

        final, _ = await self.orchestrator.execute_with_fallback(
            system_prompt=_SYSTEM_INTERPRET,
            user_message=interp_prompt,
            preferred_model_id="jddcia-qwen3-30b",
        )

        if not final:
            final = (
                f"Obtenidos {n_rows} resultados.\n\n"
                f"```sql\n{sql_normalized}\n```\n\nDatos: {preview}"
            )

        prov.execution_time_ms = int((time.monotonic() - t0) * 1000)
        return final, prov

    # ── Justificación de respuesta anterior ───────────────────────────────────

    async def justify(
        self,
        original_question: str,
        provenance: Provenance,
        followup: str = "",
        model_id: Optional[str] = None,
    ) -> str:
        """
        Genera una justificación detallada a partir de la procedencia guardada.
        El usuario puede preguntar 'por qué' o 'de dónde sale' y obtiene
        la evidencia exacta con datos brutos y SQL.
        """
        if not provenance.sql_executed and not provenance.raw_results:
            return (
                "La respuesta anterior no requirió consulta a la base de datos, "
                "fue generada directamente por el modelo de IA basándose en la "
                "pregunta y el historial de conversación."
            )

        raw_preview = provenance.raw_results[:20] if provenance.raw_results else []
        n_rows = len(provenance.raw_results) if provenance.raw_results else 0

        justify_prompt = (
            f"PREGUNTA ORIGINAL: {original_question}\n\n"
            f"{'PREGUNTA DE SEGUIMIENTO: ' + followup + chr(10) + chr(10) if followup else ''}"
            f"EVIDENCIA DE LA RESPUESTA:\n\n"
            f"Fuente de datos: {provenance.data_source}\n"
            f"Modelo utilizado: {provenance.model_used or 'desconocido'}\n"
            f"Tablas SIUO identificadas: {', '.join(provenance.tables_used) or 'ninguna'}\n"
            f"Keywords SIUO: {', '.join(provenance.siuo_keywords) or 'ninguna'}\n"
            f"Tokens de contexto: {provenance.context_tokens}\n\n"
            f"SQL GENERADO POR IA:\n```sql\n{provenance.sql_generated or '(sin SQL)'}\n```\n\n"
            f"SQL EJECUTADO (tras normalización):\n```sql\n{provenance.sql_executed or '(sin SQL)'}\n```\n\n"
            f"DATOS BRUTOS DEVUELTOS POR LA BD ({n_rows} filas totales, mostrando {len(raw_preview)}):\n"
            f"{raw_preview}\n\n"
            "Explica DETALLADAMENTE:\n"
            "1. Qué SQL se ejecutó y por qué responde a la pregunta\n"
            "2. De qué filas/registros específicos proviene cada parte de la respuesta\n"
            "3. Cómo verificar estos datos directamente en la BD (campo clave, filtro exacto)\n"
            "4. Si hay alguna limitación o posible imprecisión en los datos\n"
            "5. Si el usuario puede confiar al 100% en la respuesta, y si no, por qué"
        )

        result, _ = await self.orchestrator.execute_with_fallback(
            system_prompt=_SYSTEM_JUSTIFY,
            user_message=justify_prompt,
            preferred_model_id=model_id or "jddcia-qwen3-30b",
        )

        return result or "No se pudo generar la justificación (modelo no disponible)."
