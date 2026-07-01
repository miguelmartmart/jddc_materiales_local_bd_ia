"""
test_deep_analysis_agent.py — Tests unitarios del DeepAnalysisAgent v2.0.

Cubre:
  - detect_depth(): auto-detección de profundidad
  - TokenBudget: conteo, fits, truncate, usage_pct
  - Fase 1: fallback si la IA falla
  - Fase 2: exploración de tablas (mock de sql_executor)
  - Fase 3: SQLs fijos (distribución temporal + instalaciones)
  - Fase 4: registro de feedback SIUO
  - Fallback de emergencia
  - Análisis completo con mocks
  - Helpers SIUO: _get_siuo_columns, _get_siuo_record_count, _extract_columns_from_context
    * Flujo real: BD falla → SIUO JSON → db_context texto
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.modules.chat.deep_analysis.models import (
    AnalysisDepth, TokenBudget, detect_depth,
    EpicAnalysisResult, PhaseResult, SubPhaseResult,
    DEPTH_CONFIG, DEFAULT_CONTEXT_LIMIT_TOKENS,
)
from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_orchestrator(response: str = '{"intent":"test","category":"ventas","complexity":"epic"}'):
    """Crea un orchestrator mock que devuelve siempre la misma respuesta."""
    orch = MagicMock()
    orch.execute_with_fallback = AsyncMock(return_value=(response, None))
    orch.context_limit_tokens = 32000
    return orch


def make_sql_executor(rows: list = None):
    """Crea un sql_executor mock que devuelve filas predefinidas."""
    rows = rows or [{"TOTAL": 1234}]
    return MagicMock(return_value=rows)


def make_agent(
    orchestrator=None,
    sql_rows=None,
    db_context="TABLA: DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL",
):
    orch = orchestrator or make_orchestrator()
    executor = make_sql_executor(sql_rows)
    return DeepAnalysisAgent(
        orchestrator=orch,
        db_context=db_context,
        sql_executor=executor,
    )


# ─── Tests: detect_depth ─────────────────────────────────────────────────────

class TestSIUOMetadataHelpers:
    """
    Tests del flujo real de resiliencia de metadatos:
      BD real → SIUO JSON (db_metadata_optimized.json) → db_context texto

    Verifican que cuando la BD Firebird no está disponible, el agente
    obtiene columnas y conteos desde fuentes alternativas sin lanzar excepción.
    """

    # ── _load_metadata_json ───────────────────────────────────────────────────

    def test_load_metadata_json_file_not_found(self):
        """Si el fichero no existe, devuelve {} sin excepción."""
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", "/ruta/inexistente/metadata.json"):
            result = agent._load_metadata_json()
        assert result == {}

    def test_load_metadata_json_corrupted(self, tmp_path):
        """Si el fichero está corrupto (JSON inválido), devuelve {} sin excepción."""
        bad_file = tmp_path / "bad_metadata.json"
        bad_file.write_text("esto no es json {{{", encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(bad_file)):
            result = agent._load_metadata_json()
        assert result == {}

    def test_load_metadata_json_valid(self, tmp_path):
        """Si el fichero es válido, devuelve el dict correctamente."""
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO", "FECHA"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            result = agent._load_metadata_json()
        assert result == meta

    # ── _get_siuo_columns ─────────────────────────────────────────────────────

    def test_get_siuo_columns_format_dict_list(self, tmp_path):
        """Formato {"columns": ["COL1", "COL2"]} → devuelve lista de strings."""
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO", "FECHA", "IMPORTETOTAL"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert cols == ["TIPO", "FECHA", "IMPORTETOTAL"]

    def test_get_siuo_columns_format_dict_of_dicts(self, tmp_path):
        """Formato {"columns": [{"name": "COL1"}, ...]} → devuelve lista de strings."""
        meta = {"tables": {"DOCCAB": {"columns": [
            {"name": "TIPO", "type": "INTEGER"},
            {"name": "FECHA", "type": "DATE"},
        ]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert "TIPO" in cols
        assert "FECHA" in cols

    def test_get_siuo_columns_format_list_direct(self, tmp_path):
        """Formato lista directa [{"name": "COL1"}, ...] → devuelve lista de strings."""
        meta = {"tables": {"DOCCAB": [
            {"name": "TIPO"}, {"name": "FECHA"}, {"name": "CODCLIENTE"}
        ]}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert "TIPO" in cols
        assert "CODCLIENTE" in cols

    def test_get_siuo_columns_table_not_found(self, tmp_path):
        """Si la tabla no está en el JSON, devuelve lista vacía."""
        meta = {"tables": {"CLIENTE": {"columns": ["CODIGO", "NOMBRE"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert cols == []

    def test_get_siuo_columns_case_insensitive(self, tmp_path):
        """La búsqueda de tabla es case-insensitive."""
        meta = {"tables": {"doccab": {"columns": ["TIPO", "FECHA"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            cols = agent._get_siuo_columns("DOCCAB")
        assert "TIPO" in cols

    def test_get_siuo_columns_no_file(self):
        """Sin fichero de metadatos, devuelve lista vacía sin excepción."""
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"):
            cols = agent._get_siuo_columns("DOCCAB")
        assert cols == []

    # ── _get_siuo_record_count ────────────────────────────────────────────────

    def test_get_siuo_record_count_found(self, tmp_path):
        """Si existe record_count en el JSON, lo devuelve como int."""
        meta = {"tables": {"DOCCAB": {"record_count": 5432, "columns": ["TIPO"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count == 5432

    def test_get_siuo_record_count_row_count_field(self, tmp_path):
        """También acepta el campo 'row_count'."""
        meta = {"tables": {"DOCCAB": {"row_count": 999}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count == 999

    def test_get_siuo_record_count_not_found(self, tmp_path):
        """Si no hay conteo en el JSON, devuelve None."""
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count is None

    def test_get_siuo_record_count_no_file(self):
        """Sin fichero, devuelve None sin excepción."""
        agent = make_agent()
        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"):
            count = agent._get_siuo_record_count("DOCCAB")
        assert count is None

    # ── _extract_columns_from_context ─────────────────────────────────────────

    def test_extract_columns_pattern1_cols(self):
        """Patrón 'TABLA | Cols: COL1, COL2' → extrae columnas."""
        agent = make_agent(db_context="DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL, CODCLIENTE")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert "TIPO" in cols
        assert "FECHA" in cols
        assert "IMPORTETOTAL" in cols

    def test_extract_columns_pattern2_parentheses(self):
        """Patrón 'TABLA (COL1, COL2)' → extrae columnas."""
        agent = make_agent(db_context="DOCCAB (TIPO, FECHA, SERIE, IMPORTETOTAL)")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert "TIPO" in cols
        assert "SERIE" in cols

    def test_extract_columns_pattern3_newline(self):
        """Patrón 'TABLA\\nColumnas: COL1, COL2' → extrae columnas."""
        agent = make_agent(db_context="DOCCAB\nColumnas: TIPO, FECHA, IMPORTETOTAL")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert "TIPO" in cols
        assert "FECHA" in cols

    def test_extract_columns_empty_context(self):
        """Con db_context vacío, devuelve lista vacía sin excepción."""
        agent = make_agent(db_context="")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert cols == []

    def test_extract_columns_table_not_in_context(self):
        """Si la tabla no está en el contexto, devuelve lista vacía."""
        agent = make_agent(db_context="CLIENTE | Cols: CODIGO, NOMBRE, TELEFONO")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert cols == []

    def test_extract_columns_no_exception_on_bad_input(self):
        """Con input malformado, no lanza excepción."""
        agent = make_agent(db_context="[[[invalid regex content")
        cols = agent._extract_columns_from_context("DOCCAB")
        assert isinstance(cols, list)

    # ── Flujo real: BD falla → SIUO JSON → db_context ────────────────────────

    async def test_explore_table_fallback_to_siuo_json(self, tmp_path):
        """
        Flujo real: BD Firebird falla → columnas obtenidas desde SIUO JSON.
        Verifica que _explore_table usa _get_siuo_columns como fallback.
        """
        meta = {"tables": {"DOCCAB": {"columns": ["TIPO", "FECHA", "IMPORTETOTAL", "CODCLIENTE", "SERIE"]}}}
        meta_file = tmp_path / "metadata.json"
        meta_file.write_text(json.dumps(meta), encoding="utf-8")

        # BD falla para todo
        agent = make_agent()
        agent.sql_executor = AsyncMock(side_effect=Exception("Firebird no disponible"))

        # Mockear KnowledgeStore para que devuelva cache vacío (sin datos de DOCCAB)
        mock_store = MagicMock()
        mock_store.get_table.return_value = {}  # Cache vacío → fuerza exploración real

        with patch.object(type(agent), "_METADATA_PATH", str(meta_file)), \
             patch("backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
                   return_value=mock_store):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = await agent._explore_table("DOCCAB", cfg)

        # Columnas obtenidas desde SIUO JSON
        assert "TIPO" in info.get("columns", [])
        assert info.get("columns_source") == "siuo_metadata"
        assert info.get("has_tipo") is True
        assert info.get("has_serie") is True

    async def test_explore_table_fallback_to_db_context(self):
        """
        Flujo real: BD falla + SIUO JSON vacío → columnas desde db_context texto.
        """
        agent = make_agent(db_context="DOCCAB | Cols: TIPO, FECHA, IMPORTETOTAL")
        agent.sql_executor = AsyncMock(side_effect=Exception("Firebird no disponible"))

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}  # Cache vacío

        # Sin fichero de metadatos
        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"), \
             patch("backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
                   return_value=mock_store):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = await agent._explore_table("DOCCAB", cfg)

        # Columnas obtenidas desde db_context
        assert "TIPO" in info.get("columns", [])
        assert info.get("columns_source") == "db_context_text"

    async def test_explore_table_all_sources_fail_no_exception(self):
        """
        Flujo real: BD falla + SIUO JSON vacío + db_context sin info.
        El agente continúa sin excepción con columnas vacías.
        """
        agent = make_agent(db_context="Sin información de tablas aquí.")
        agent.sql_executor = AsyncMock(side_effect=Exception("Firebird no disponible"))

        mock_store = MagicMock()
        mock_store.get_table.return_value = {}  # Cache vacío

        with patch.object(type(agent), "_METADATA_PATH", "/no/existe.json"), \
             patch("backend.modules.chat.deep_analysis.phase2_explore.get_knowledge_store",
                   return_value=mock_store):
            cfg = {"max_sqls": 4, "explore_tables": 2}
            info = await agent._explore_table("DOCCAB", cfg)

        # No lanza excepción, devuelve info con columnas vacías
        assert isinstance(info, dict)
        assert info.get("columns", []) == []
        assert info.get("columns_source") == "unknown"


# ─── Tests NUEVOS: _build_warnings_html → Markdown puro ─────────────────────

