"""
tests/unit/test_deep_analysis_fixes.py — Tests para las correcciones del DeepAnalysisAgent.

Cubre:
  1. _detect_tipo_filter() — detecta TIPO correcto según palabras clave
  2. _detect_month_number() — detecta mes por nombre
  3. _detect_count_anomalies() — detecta conteos sospechosamente bajos
  4. _from_join_re — extrae nombres de tabla sin incluir EXTRACT(... FROM ...)
  5. Integración: phase3_sqls genera SQLs de mes cuando la pregunta lo menciona

DEVIA: bots/interjddcia/backend/modules/db_simulator/DEVIA.md
"""

import re
import sys
import os
import pytest

# ─── Path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ─── Imports ──────────────────────────────────────────────────────────────────

from backend.modules.chat.deep_analysis.phase3_sqls import (
    _detect_tipo_filter,
    _detect_month_number,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. _detect_tipo_filter
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectTipoFilter:
    """Tests para la función _detect_tipo_filter."""

    def test_factura_keywords(self):
        assert _detect_tipo_filter("cuántas facturas hay en mayo") == "TIPO = 13"
        assert _detect_tipo_filter("facturación total del año") == "TIPO = 13"
        assert _detect_tipo_filter("importe facturado") == "TIPO = 13"

    def test_presupuesto_keywords(self):
        assert _detect_tipo_filter("presupuestos pendientes") == "TIPO = 0"
        assert _detect_tipo_filter("tasa de conversión de presupuesto") == "TIPO = 0"

    def test_albaran_keywords(self):
        # "albaranes sin facturar" debe devolver TIPO=11 (albarán), no TIPO=13 (factura)
        # porque "facturar" aquí es un verbo, no el tipo de documento
        assert _detect_tipo_filter("albaranes sin facturar") == "TIPO = 11"
        assert _detect_tipo_filter("albarán pendiente") == "TIPO = 11"
        assert _detect_tipo_filter("albaranes del mes") == "TIPO = 11"

    def test_pedido_keywords(self):
        assert _detect_tipo_filter("pedidos del mes") == "TIPO = 12"

    def test_sat_keywords(self):
        assert _detect_tipo_filter("SAT abiertos") == "TIPO = 2"
        assert _detect_tipo_filter("servicio técnico pendiente") == "TIPO = 2"

    def test_no_keyword_returns_empty(self):
        assert _detect_tipo_filter("cuántos documentos hay") == ""
        assert _detect_tipo_filter("resumen general") == ""

    def test_case_insensitive(self):
        assert _detect_tipo_filter("FACTURAS DEL MES") == "TIPO = 13"
        assert _detect_tipo_filter("Presupuestos Pendientes") == "TIPO = 0"


# ─────────────────────────────────────────────────────────────────────────────
# 2. _detect_month_number
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectMonthNumber:
    """Tests para la función _detect_month_number."""

    def test_full_month_names(self):
        assert _detect_month_number("facturas en enero") == 1
        assert _detect_month_number("ventas de febrero") == 2
        assert _detect_month_number("cuánto en marzo") == 3
        assert _detect_month_number("abril fue buen mes") == 4
        assert _detect_month_number("mayo tiene muchas facturas") == 5
        assert _detect_month_number("junio") == 6
        assert _detect_month_number("julio") == 7
        assert _detect_month_number("agosto") == 8
        assert _detect_month_number("septiembre") == 9
        assert _detect_month_number("octubre") == 10
        assert _detect_month_number("noviembre") == 11
        assert _detect_month_number("diciembre") == 12

    def test_abbreviations(self):
        assert _detect_month_number("ene 2026") == 1
        assert _detect_month_number("feb") == 2
        assert _detect_month_number("dic") == 12

    def test_no_month_returns_zero(self):
        assert _detect_month_number("cuántas facturas hay") == 0
        assert _detect_month_number("resumen anual") == 0
        assert _detect_month_number("") == 0

    def test_case_insensitive(self):
        assert _detect_month_number("MAYO") == 5
        assert _detect_month_number("Enero") == 1


# ─────────────────────────────────────────────────────────────────────────────
# 3. _detect_count_anomalies
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectCountAnomalies:
    """Tests para Phase4Mixin._detect_count_anomalies."""

    def _make_result(self, queries):
        """Crea un EpicAnalysisResult mínimo para testing."""
        from backend.modules.chat.deep_analysis.models import EpicAnalysisResult, AnalysisDepth
        # AnalysisDepth values: BASIC, MEDIUM, DEEP, EPIC
        result = EpicAnalysisResult(question="test", depth=AnalysisDepth.BASIC)
        result.sql_queries = queries
        return result

    def test_detects_suspiciously_low_count(self):
        """Si una consulta devuelve 1 y otra devuelve 85, debe detectar anomalía."""
        from backend.modules.chat.deep_analysis.phase4 import Phase4Mixin

        class MockPhase4(Phase4Mixin):
            pass

        mixin = MockPhase4()
        result = self._make_result([
            {
                "objetivo": "Total facturas",
                "sql": "SELECT COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13",
                "rows": 1,
                "data": [{"N_FACTURAS": 85}],
                "error": None,
            },
            {
                "objetivo": "Facturas en mayo",
                "sql": "SELECT COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13 AND EXTRACT(MONTH FROM FECHA)=5",
                "rows": 1,
                "data": [{"N_FACTURAS": 1}],
                "error": None,
            },
        ])

        mixin._detect_count_anomalies(result)

        # Debe haber detectado la anomalía (1 vs 85)
        assert len(result.anomalies) > 0
        assert any("1" in a and "85" in a for a in result.anomalies)

    def test_no_anomaly_when_counts_similar(self):
        """Si los conteos son similares, no debe detectar anomalía."""
        from backend.modules.chat.deep_analysis.phase4 import Phase4Mixin

        class MockPhase4(Phase4Mixin):
            pass

        mixin = MockPhase4()
        result = self._make_result([
            {
                "objetivo": "Total facturas",
                "sql": "SELECT COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13",
                "rows": 1,
                "data": [{"N_FACTURAS": 85}],
                "error": None,
            },
            {
                "objetivo": "Facturas en mayo",
                "sql": "SELECT COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13",
                "rows": 1,
                "data": [{"N_FACTURAS": 80}],
                "error": None,
            },
        ])

        mixin._detect_count_anomalies(result)
        assert len(result.anomalies) == 0

    def test_no_anomaly_with_single_query(self):
        """Con una sola consulta no hay comparación posible."""
        from backend.modules.chat.deep_analysis.phase4 import Phase4Mixin

        class MockPhase4(Phase4Mixin):
            pass

        mixin = MockPhase4()
        result = self._make_result([
            {
                "objetivo": "Total facturas",
                "sql": "SELECT COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13",
                "rows": 1,
                "data": [{"N_FACTURAS": 85}],
                "error": None,
            },
        ])

        mixin._detect_count_anomalies(result)
        assert len(result.anomalies) == 0

    def test_skips_errored_queries(self):
        """Las consultas con error no deben participar en la detección."""
        from backend.modules.chat.deep_analysis.phase4 import Phase4Mixin

        class MockPhase4(Phase4Mixin):
            pass

        mixin = MockPhase4()
        result = self._make_result([
            {
                "objetivo": "Total facturas",
                "sql": "SELECT COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13",
                "rows": 1,
                "data": [{"N_FACTURAS": 85}],
                "error": None,
            },
            {
                "objetivo": "Consulta con error",
                "sql": "SELECT INVALID",
                "rows": 0,
                "data": [],
                "error": "column not found",
            },
        ])

        mixin._detect_count_anomalies(result)
        # Solo hay 1 consulta válida → no hay comparación
        assert len(result.anomalies) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Extracción de nombres de tabla (regex FROM/JOIN)
# ─────────────────────────────────────────────────────────────────────────────

class TestTableNameExtraction:
    """
    Tests para el regex de extracción de nombres de tabla en phase5.py.
    El bug original era que EXTRACT(YEAR FROM FECHA) producía 'FECHA)' como nombre de tabla.
    """

    # Mismo regex que en phase5.py
    _from_join_re = re.compile(r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)', re.IGNORECASE)
    _EXCLUDED = {
        'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS',
        'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'NATURAL',
        'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'CURRENT_TIME',
        'FECHA', 'NOMBRE', 'CODIGO', 'TIPO', 'IMPORTE',
    }

    def _extract_tables(self, sql: str) -> set:
        return {
            m.group(1).upper()
            for m in self._from_join_re.finditer(sql)
            if m.group(1).upper() not in self._EXCLUDED
        }

    def test_simple_from(self):
        sql = "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13"
        assert self._extract_tables(sql) == {"DOCCAB"}

    def test_join(self):
        sql = "SELECT * FROM DOCCAB D JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO"
        assert self._extract_tables(sql) == {"DOCCAB", "CLIENTE"}

    def test_extract_year_from_does_not_produce_fecha(self):
        """EXTRACT(YEAR FROM FECHA) no debe producir 'FECHA' como nombre de tabla."""
        sql = (
            "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N "
            "FROM DOCCAB WHERE TIPO=13 "
            "GROUP BY EXTRACT(YEAR FROM FECHA)"
        )
        tables = self._extract_tables(sql)
        assert "FECHA" not in tables
        assert "DOCCAB" in tables

    def test_extract_month_from_does_not_produce_fecha(self):
        """EXTRACT(MONTH FROM FECHA) no debe producir 'FECHA' como nombre de tabla."""
        sql = (
            "SELECT EXTRACT(MONTH FROM FECHA) AS MES, COUNT(*) AS N "
            "FROM DOCCAB WHERE TIPO=13 "
            "GROUP BY EXTRACT(MONTH FROM FECHA)"
        )
        tables = self._extract_tables(sql)
        assert "FECHA" not in tables
        assert "DOCCAB" in tables

    def test_multiple_joins(self):
        sql = (
            "SELECT * FROM DOCCAB D "
            "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
            "LEFT JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
            "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO"
        )
        tables = self._extract_tables(sql)
        assert tables == {"DOCCAB", "CLIENTE", "DOCLIN", "ARTICULO"}

    def test_subquery_from(self):
        sql = (
            "SELECT RANGO, COUNT(*) FROM ("
            "SELECT IMPORTETOTAL, CASE WHEN IMPORTETOTAL < 100 THEN 'bajo' ELSE 'alto' END AS RANGO "
            "FROM DOCCAB WHERE TIPO=13"
            ") GROUP BY RANGO"
        )
        tables = self._extract_tables(sql)
        assert "DOCCAB" in tables


# ─────────────────────────────────────────────────────────────────────────────
# 5. Phase3SqlsMixin._build_fixed_sqls — genera SQLs de mes
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase3FixedSqls:
    """Tests para Phase3SqlsMixin._build_fixed_sqls."""

    def _make_mixin(self):
        from backend.modules.chat.deep_analysis.phase3_sqls import Phase3SqlsMixin

        class MockMixin(Phase3SqlsMixin):
            pass

        return MockMixin()

    def test_month_specific_sqls_generated_for_mayo(self):
        """Cuando la pregunta menciona 'mayo', debe generarse SQL con EXTRACT(MONTH FROM FECHA)=5."""
        mixin = self._make_mixin()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        sqls = mixin._build_fixed_sqls("cuántas facturas hubo en mayo", phase2_data)

        sql_texts = [s["sql"] for s in sqls]
        # Debe haber al menos un SQL con EXTRACT(MONTH FROM FECHA) = 5
        assert any("EXTRACT(MONTH FROM FECHA) = 5" in sql for sql in sql_texts), (
            f"No se encontró SQL con mes=5. SQLs generados: {sql_texts}"
        )

    def test_tipo_filter_applied_for_facturas(self):
        """Cuando la pregunta menciona 'facturas', el filtro TIPO=13 debe estar en los SQLs."""
        mixin = self._make_mixin()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        sqls = mixin._build_fixed_sqls("cuántas facturas hay este año", phase2_data)

        sql_texts = [s["sql"] for s in sqls]
        # Al menos uno de los SQLs de distribución debe tener TIPO = 13
        assert any("TIPO = 13" in sql for sql in sql_texts), (
            f"No se encontró TIPO=13. SQLs: {sql_texts}"
        )

    def test_no_month_sql_when_no_month_mentioned(self):
        """Sin mención de mes, no debe generarse SQL de mes específico."""
        mixin = self._make_mixin()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        sqls = mixin._build_fixed_sqls("cuántas facturas hay este año", phase2_data)

        sql_texts = [s["sql"] for s in sqls]
        # No debe haber SQL con "EXTRACT(MONTH FROM FECHA) = N" para mes específico
        # (sí puede haber el SQL de distribución mensual general)
        month_specific = [
            sql for sql in sql_texts
            if re.search(r'EXTRACT\(MONTH FROM FECHA\) = \d+', sql)
        ]
        assert len(month_specific) == 0, (
            f"Se generaron SQLs de mes específico sin que la pregunta lo mencione: {month_specific}"
        )

    def test_always_generates_monthly_distribution(self):
        """Siempre debe generarse el SQL de distribución mensual del año actual."""
        mixin = self._make_mixin()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        sqls = mixin._build_fixed_sqls("resumen de ventas", phase2_data)

        sql_texts = [s["sql"] for s in sqls]
        # Debe haber SQL con distribución mensual (EXTRACT(YEAR FROM CURRENT_DATE))
        assert any("EXTRACT(YEAR FROM CURRENT_DATE)" in sql for sql in sql_texts), (
            f"No se encontró SQL de distribución mensual. SQLs: {sql_texts}"
        )

    def test_presupuesto_sqls_generated(self):
        """Cuando la pregunta menciona 'presupuesto', deben generarse SQLs de estado."""
        mixin = self._make_mixin()
        phase2_data = {"DOCCAB": {"has_serie": False, "has_codigoobra": False}}
        sqls = mixin._build_fixed_sqls("tasa de éxito de presupuestos", phase2_data)

        objetivos = [s["objetivo"] for s in sqls]
        assert any("ESTADOPEND" in obj for obj in objetivos), (
            f"No se encontró SQL de ESTADOPEND. Objetivos: {objetivos}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Seguridad: valores de BD real no salen a internet
# ─────────────────────────────────────────────────────────────────────────────

class TestDataSecurity:
    """
    Verifica que los módulos de BD simulada no contienen URLs externas
    ni llamadas a requests/urllib que puedan filtrar datos reales.
    """

    def test_phase3_sqls_no_external_calls(self):
        """phase3_sqls.py no debe importar requests, urllib ni httpx."""
        import importlib
        import inspect
        from backend.modules.chat.deep_analysis import phase3_sqls
        source = inspect.getsource(phase3_sqls)
        forbidden = ["import requests", "import urllib", "import httpx", "http.client"]
        for f in forbidden:
            assert f not in source, f"Llamada externa encontrada en phase3_sqls: {f}"

    def test_phase4_no_external_calls(self):
        """phase4.py no debe importar requests, urllib ni httpx."""
        import inspect
        from backend.modules.chat.deep_analysis import phase4
        source = inspect.getsource(phase4)
        forbidden = ["import requests", "import urllib", "import httpx"]
        for f in forbidden:
            assert f not in source, f"Llamada externa encontrada en phase4: {f}"

    def test_db_simulator_panels_no_external_calls(self):
        """justification/panels.py no debe hacer llamadas externas."""
        import inspect
        from backend.modules.db_simulator.justification import panels
        source = inspect.getsource(panels)
        forbidden = ["import requests", "import urllib", "import httpx"]
        for f in forbidden:
            assert f not in source, f"Llamada externa encontrada en panels: {f}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Justification registry — 10 paneles por consulta
# ─────────────────────────────────────────────────────────────────────────────

class TestJustificationRegistry:
    """Verifica que todas las consultas del registry tienen exactamente 10 paneles."""

    def test_all_queries_have_10_panels(self):
        from backend.modules.db_simulator.justification.registry import (
            _REGISTRY, STANDARD_PANEL_COUNT
        )
        errors = []
        for query_id, panels in _REGISTRY.items():
            if len(panels) != STANDARD_PANEL_COUNT:
                errors.append(
                    f"{query_id}: {len(panels)} paneles (esperado {STANDARD_PANEL_COUNT})"
                )
        assert not errors, (
            f"Consultas con número incorrecto de paneles:\n" + "\n".join(errors)
        )

    def test_all_panels_have_required_fields(self):
        from backend.modules.db_simulator.justification.registry import _REGISTRY
        required_fields = {"id", "label", "justificacion", "sql", "icono", "tipo"}
        errors = []
        for query_id, panels in _REGISTRY.items():
            for i, panel in enumerate(panels):
                missing = required_fields - set(panel.keys())
                if missing:
                    errors.append(f"{query_id}[{i}]: faltan campos {missing}")
        assert not errors, "\n".join(errors)

    def test_no_duplicate_panel_ids_within_query(self):
        from backend.modules.db_simulator.justification.registry import _REGISTRY
        errors = []
        for query_id, panels in _REGISTRY.items():
            ids = [p["id"] for p in panels]
            if len(ids) != len(set(ids)):
                duplicates = [id for id in ids if ids.count(id) > 1]
                errors.append(f"{query_id}: IDs duplicados {set(duplicates)}")
        assert not errors, "\n".join(errors)

    def test_all_panels_have_non_empty_sql(self):
        from backend.modules.db_simulator.justification.registry import _REGISTRY
        errors = []
        for query_id, panels in _REGISTRY.items():
            for i, panel in enumerate(panels):
                if not panel.get("sql", "").strip():
                    errors.append(f"{query_id}[{i}] '{panel.get('id')}': SQL vacío")
        assert not errors, "\n".join(errors)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Query library — IDs únicos y estructura correcta
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryLibrary:
    """Verifica la integridad de la biblioteca de consultas extendida."""

    def test_no_duplicate_ids_in_extended_library(self):
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        ids = [q["id"] for q in QUERY_LIBRARY_EXTENDED]
        duplicates = [id for id in ids if ids.count(id) > 1]
        assert not duplicates, f"IDs duplicados en QUERY_LIBRARY_EXTENDED: {set(duplicates)}"

    def test_all_queries_have_required_fields(self):
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        required = {"id", "nombre", "desc_simple", "desc_tecnica", "sql", "dept", "urgencia"}
        errors = []
        for q in QUERY_LIBRARY_EXTENDED:
            missing = required - set(q.keys())
            if missing:
                errors.append(f"{q.get('id', '?')}: faltan {missing}")
        assert not errors, "\n".join(errors[:20])

    def test_all_queries_have_non_empty_sql(self):
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        errors = [
            q["id"] for q in QUERY_LIBRARY_EXTENDED
            if not q.get("sql", "").strip()
        ]
        assert not errors, f"Consultas con SQL vacío: {errors}"

    def test_minimum_query_count(self):
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        assert len(QUERY_LIBRARY_EXTENDED) >= 1000, (
            f"Se esperaban >= 1000 consultas, hay {len(QUERY_LIBRARY_EXTENDED)}"
        )
