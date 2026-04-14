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

class TestBuildWarningsMarkdown:
    """
    Tests para el fix de HTML crudo en la respuesta.
    _build_warnings_html ahora genera Markdown puro, no HTML con <div>.
    """

    def test_empty_result_returns_empty_string(self):
        """Sin warnings ni anomalías → string vacío."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        assert agent._build_warnings_html(result) == ""

    def test_no_html_tags_in_output(self):
        """La salida NO debe contener etiquetas HTML."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.warnings = ["Advertencia importante"]
        result.anomalies = ["Anomalía detectada"]
        output = agent._build_warnings_html(result)
        assert "<div" not in output
        assert "<ul" not in output
        assert "<li" not in output
        assert "style=" not in output
        assert "background:" not in output

    def test_dict_anomaly_extracts_description(self):
        """Anomalía como dict → extrae campo 'description'."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.anomalies = [
            {
                "type": "anomalia_estadistica",
                "description": "El 99.1% de los presupuestos tienen documento destino",
                "value": 0.991,
                "column": "TIPO_DESTINO",
            }
        ]
        result.warnings = []
        output = agent._build_warnings_html(result)
        # Debe mostrar la descripción, no el dict crudo
        assert "El 99.1% de los presupuestos" in output
        assert "{'type'" not in output
        assert "anomalia_estadistica" not in output

    def test_dict_warning_extracts_description(self):
        """Warning como dict → extrae campo 'description' o 'details'."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.warnings = [
            {
                "type": "data_quality",
                "description": "Hay 150 presupuestos sin CODCLIENTE asignado",
                "impact": "alto",
            }
        ]
        result.anomalies = []
        output = agent._build_warnings_html(result)
        assert "150 presupuestos sin CODCLIENTE" in output
        assert "{'type'" not in output

    def test_dict_uses_details_if_no_description(self):
        """Si no hay 'description', usa 'details'."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.anomalies = [
            {
                "type": "anomalia",
                "details": "Tasa de éxito calculada: 2.69% (8 aceptados / 306 enviados)",
            }
        ]
        result.warnings = []
        output = agent._build_warnings_html(result)
        assert "2.69%" in output

    def test_string_anomaly_shown_directly(self):
        """Anomalía como string → se muestra directamente."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.anomalies = ["Tasa de éxito anormalmente baja: 2.69%"]
        result.warnings = []
        output = agent._build_warnings_html(result)
        assert "2.69%" in output

    def test_markdown_headers_present(self):
        """La salida usa headers Markdown (###)."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.anomalies = ["Anomalía 1"]
        result.warnings = ["Advertencia 1"]
        output = agent._build_warnings_html(result)
        assert "###" in output

    def test_max_5_anomalies_shown(self):
        """Se muestran máximo 5 anomalías."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.anomalies = [f"Anomalía {i}" for i in range(10)]
        result.warnings = []
        output = agent._build_warnings_html(result)
        # Contar cuántas anomalías aparecen
        count = sum(1 for i in range(10) if f"Anomalía {i}" in output)
        assert count <= 5

    def test_max_5_warnings_shown(self):
        """Se muestran máximo 5 advertencias."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.warnings = [f"Advertencia {i}" for i in range(10)]
        result.anomalies = []
        output = agent._build_warnings_html(result)
        count = sum(1 for i in range(10) if f"Advertencia {i}" in output)
        assert count <= 5

    def test_dict_fallback_concatenates_values(self):
        """Dict sin 'description' ni 'details' → concatena valores relevantes."""
        agent = make_agent()
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.EPIC)
        result.anomalies = [
            {
                "type": "anomalia",
                "rule": "Solo el 10% de presupuestos se convierten",
                "confidence": "alto",
            }
        ]
        result.warnings = []
        output = agent._build_warnings_html(result)
        # Debe mostrar algo del dict, no el repr completo
        assert "{'type'" not in output
        # Debe contener algún valor del dict
        assert len(output) > 10


# ─── Tests NUEVOS: _strip_html_from_markdown ─────────────────────────────────

class TestStripHtmlFromMarkdown:
    """Tests para la limpieza de HTML residual en la respuesta Markdown."""

    def test_removes_div_tags(self):
        """Elimina etiquetas <div> pero preserva el contenido."""
        agent = make_agent()
        text = '<div style="color:red">Texto importante</div>'
        result = agent._strip_html_from_markdown(text)
        assert "Texto importante" in result
        assert "<div" not in result

    def test_removes_span_tags(self):
        """Elimina etiquetas <span> pero preserva el contenido."""
        agent = make_agent()
        text = 'Texto con <span class="highlight">resaltado</span> aquí'
        result = agent._strip_html_from_markdown(text)
        assert "resaltado" in result
        assert "<span" not in result

    def test_converts_strong_to_markdown(self):
        """Convierte <strong> a **bold**."""
        agent = make_agent()
        text = "Texto con <strong>negrita</strong> aquí"
        result = agent._strip_html_from_markdown(text)
        assert "**negrita**" in result
        assert "<strong>" not in result

    def test_converts_em_to_markdown(self):
        """Convierte <em> a *italic*."""
        agent = make_agent()
        text = "Texto con <em>cursiva</em> aquí"
        result = agent._strip_html_from_markdown(text)
        assert "*cursiva*" in result
        assert "<em>" not in result

    def test_converts_li_to_bullet(self):
        """Convierte <li> a bullet points."""
        agent = make_agent()
        text = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = agent._strip_html_from_markdown(text)
        assert "Item 1" in result
        assert "Item 2" in result
        assert "<li>" not in result

    def test_removes_details_block(self):
        """Elimina bloques <details> generados por la IA (los reemplazamos nosotros)."""
        agent = make_agent()
        text = "Texto antes\n<details><summary>Ver más</summary>\nContenido\n</details>\nTexto después"
        result = agent._strip_html_from_markdown(text)
        assert "Texto antes" in result
        assert "Texto después" in result
        assert "<details>" not in result

    def test_preserves_markdown_content(self):
        """El Markdown puro no se modifica."""
        agent = make_agent()
        text = "## Título\n\n- Item 1\n- Item 2\n\n**Negrita** y *cursiva*"
        result = agent._strip_html_from_markdown(text)
        assert "## Título" in result
        assert "- Item 1" in result
        assert "**Negrita**" in result

    def test_no_exception_on_empty_string(self):
        """No lanza excepción con string vacío."""
        agent = make_agent()
        result = agent._strip_html_from_markdown("")
        assert result == ""

    def test_cleans_multiple_blank_lines(self):
        """Limpia líneas vacías múltiples (máx 2 consecutivas)."""
        agent = make_agent()
        text = "Línea 1\n\n\n\n\nLínea 2"
        result = agent._strip_html_from_markdown(text)
        assert "Línea 1" in result
        assert "Línea 2" in result
        assert "\n\n\n" not in result


# ─── Tests NUEVOS: SQLs ESTADOPENDVENCOM (fix tasa de éxito) ─────────────────

class TestFixedSQLsEstadoPendVenCom:
    """
    Tests para los nuevos SQLs fijos 3e-3h que investigan la tasa de éxito
    correctamente usando ESTADOPENDVENCOM y conversión a factura/pedido.
    """

    def test_estadopendvencom_sql_included(self):
        """SQL 3e: ESTADOPENDVENCOM se incluye para preguntas sobre tasa/éxito."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("tasa de éxito presupuestos", phase2_data)
        sqls = [f["sql"] for f in fixed]
        assert any("ESTADOPENDVENCOM" in s for s in sqls)

    def test_estadopendvencom_sql_objetivo(self):
        """SQL 3e tiene objetivo descriptivo sobre estado comercial."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("tasa de éxito", phase2_data)
        objetivos = [f["objetivo"] for f in fixed]
        assert any("ESTADOPENDVENCOM" in o and ("comercial" in o.lower() or "estado" in o.lower())
                   for o in objetivos)

    def test_cruce_estadopend_vencom_sql_included(self):
        """SQL 3f: Cruce ESTADOPEND x ESTADOPENDVENCOM se incluye."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("presupuestos aceptados", phase2_data)
        sqls = [f["sql"] for f in fixed]
        # Debe haber un SQL con ambas columnas en GROUP BY
        assert any("ESTADOPEND" in s and "ESTADOPENDVENCOM" in s for s in sqls)

    def test_conversion_factura_pedido_sql_included(self):
        """SQL 3g: Conversión a factura/pedido se incluye."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("tasa de éxito", phase2_data)
        sqls = [f["sql"] for f in fixed]
        # Debe haber SQL con A_FACTURA y A_PEDIDO
        assert any("A_FACTURA" in s and "A_PEDIDO" in s for s in sqls)

    def test_conversion_sql_uses_tipo_13_and_12(self):
        """SQL 3g usa TIPO=13 (factura) y TIPO=12 (pedido)."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("tasa de éxito", phase2_data)
        sqls = [f["sql"] for f in fixed]
        conversion_sql = next((s for s in sqls if "A_FACTURA" in s), None)
        assert conversion_sql is not None
        assert "TIPO = 13" in conversion_sql or "TIPO=13" in conversion_sql
        assert "TIPO = 12" in conversion_sql or "TIPO=12" in conversion_sql

    def test_muestra_presupuestos_sql_included(self):
        """SQL 3h: Muestra de presupuestos con valores reales de ESTADOPEND."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("presupuestos aceptados", phase2_data)
        sqls = [f["sql"] for f in fixed]
        # Debe haber SQL con FIRST 10 y ESTADOPEND y ESTADOPENDVENCOM
        assert any("FIRST 10" in s and "ESTADOPEND" in s and "ESTADOPENDVENCOM" in s
                   for s in sqls)

    def test_all_new_sqls_for_exito_keyword(self):
        """Para 'éxito', se incluyen todos los SQLs 3a-3h."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuál es la tasa de éxito?", phase2_data)
        sqls_text = " ".join(f["sql"] for f in fixed)
        # Verificar presencia de los 4 nuevos SQLs
        assert "ESTADOPENDVENCOM" in sqls_text          # 3e
        assert "GROUP BY ESTADOPEND, ESTADOPENDVENCOM" in sqls_text  # 3f
        assert "A_FACTURA" in sqls_text                 # 3g
        assert "FIRST 10" in sqls_text                  # 3h

    def test_new_sqls_not_included_for_stock_question(self):
        """Los nuevos SQLs NO se incluyen para preguntas sobre stock."""
        agent = make_agent()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        fixed = agent._build_fixed_sqls("¿cuántos artículos hay en stock?", phase2_data)
        sqls_text = " ".join(f["sql"] for f in fixed)
        assert "ESTADOPENDVENCOM" not in sqls_text
        assert "A_FACTURA" not in sqls_text


# ─── Tests NUEVOS: KnowledgeStore cache-first en Fase 2 ──────────────────────

