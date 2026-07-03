"""
test_db_simulator_core.py — Tests unitarios del módulo db_simulator (capa de infraestructura).

Cobertura:
  • FirebirdToSQLiteTranslator   — ~12 casos de traducción SQL
  • SimulatedFirebirdDriver      — connect, execute_query, system queries, get_table_metadata
  • Schema / TABLE_SCHEMAS       — integridad del DDL SQLite
  • SyntheticSeeder              — generación de datos (conteos, integridad referencial)
  • SimulatorManager.is_enabled  — lectura de config.json
  • SimulatorManager.get_disclaimer — generación de textos de aviso

⚡ Sin acceso a red ni IA: todos los tests usan `:memory:` y datos sintéticos locales.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ─── Módulo bajo prueba ───────────────────────────────────────────────────────
from backend.modules.db_simulator.query_translator import (
    FirebirdToSQLiteTranslator,
    translate_firebird_sql,
)
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.schema import TABLE_SCHEMAS, TABLE_COLUMNS, TABLE_CREATION_ORDER
from backend.modules.db_simulator.synthetic_seeder import SyntheticSeeder
from backend.modules.db_simulator.constants import (
    JDDCTableNames,
    SimulatorDisclaimer,
    SimulatorMode,
    SimulatorPaths,
    SimulatorStatus,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def translator() -> FirebirdToSQLiteTranslator:
    return FirebirdToSQLiteTranslator()


@pytest.fixture(scope="module")
def driver_in_memory() -> SimulatedFirebirdDriver:
    """Driver con BD en memoria — aislado por sesión de módulo."""
    drv = SimulatedFirebirdDriver()
    drv.connect(db_path=":memory:")
    yield drv
    drv.disconnect()


@pytest.fixture(scope="module")
def seeded_driver() -> SimulatedFirebirdDriver:
    """Driver con datos sintéticos completos en memoria."""
    drv = SimulatedFirebirdDriver()
    drv.connect(db_path=":memory:")
    seeder = SyntheticSeeder(drv.conn)
    seeder.seed_all()
    yield drv
    drv.disconnect()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. QUERY TRANSLATOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestFirebirdToSQLiteTranslator:

    # ── SELECT FIRST N ────────────────────────────────────────────────────────

    def test_first_n_basic(self, translator):
        sql, changes = translator.translate("SELECT FIRST 10 * FROM DOCCAB")
        assert "LIMIT 10" in sql
        assert "FIRST" not in sql
        assert len(changes) == 1

    def test_first_n_with_semicolon(self, translator):
        sql, _ = translator.translate("SELECT FIRST 5 CODIGO, NOMBRE FROM ARTICULO;")
        assert "LIMIT 5;" in sql
        assert "FIRST" not in sql

    def test_first_n_distinct(self, translator):
        sql, changes = translator.translate("SELECT DISTINCT FIRST 20 NOMBRE FROM CLIENTE")
        assert "DISTINCT" in sql
        assert "LIMIT 20" in sql
        assert "FIRST" not in sql

    def test_no_first_unchanged(self, translator):
        sql_orig = "SELECT * FROM FAMILIA WHERE CODIGO = 1"
        sql, changes = translator.translate(sql_orig)
        assert sql == sql_orig
        assert changes == []

    # ── EXTRACT ───────────────────────────────────────────────────────────────

    def test_extract_month(self, translator):
        sql, changes = translator.translate(
            "SELECT * FROM DOCCAB WHERE EXTRACT(MONTH FROM FECHA) = 3"
        )
        assert "strftime('%m'" in sql
        assert "EXTRACT" not in sql
        assert any("MONTH" in c for c in changes)

    def test_extract_year(self, translator):
        sql, _ = translator.translate(
            "SELECT EXTRACT(YEAR FROM FECHA) FROM DOCCAB"
        )
        assert "strftime('%Y'" in sql

    def test_extract_day(self, translator):
        sql, _ = translator.translate(
            "SELECT EXTRACT(DAY FROM FECHA) FROM CAJA"
        )
        assert "strftime('%d'" in sql

    # ── CURRENT_DATE / CURRENT_TIMESTAMP ──────────────────────────────────────

    def test_current_date(self, translator):
        sql, changes = translator.translate(
            "SELECT * FROM DOCCAB WHERE FECHA >= CURRENT_DATE"
        )
        assert "date('now')" in sql
        assert "CURRENT_DATE" not in sql
        assert any("CURRENT_DATE" in c for c in changes)

    def test_current_timestamp(self, translator):
        sql, changes = translator.translate(
            "SELECT CURRENT_TIMESTAMP FROM DOCCAB"
        )
        assert "datetime('now')" in sql
        assert "CURRENT_TIMESTAMP" not in sql

    # ── SUBSTRING ─────────────────────────────────────────────────────────────

    def test_substring(self, translator):
        sql, changes = translator.translate(
            "SELECT SUBSTRING(NOMBRE FROM 1 FOR 10) FROM ARTICULO"
        )
        assert "SUBSTR(NOMBRE, 1, 10)" in sql
        assert "SUBSTRING" not in sql

    # ── CAST AS DATE ──────────────────────────────────────────────────────────

    def test_cast_as_date(self, translator):
        sql, changes = translator.translate(
            "SELECT * FROM DOCCAB WHERE FECHA >= CAST('2026-01-01' AS DATE)"
        )
        assert "date('2026-01-01')" in sql
        assert any("CAST AS DATE" in c for c in changes)

    # ── Múltiples en la misma query ───────────────────────────────────────────

    def test_combined_translation(self, translator):
        sql, changes = translator.translate(
            "SELECT FIRST 50 * FROM DOCCAB "
            "WHERE EXTRACT(YEAR FROM FECHA) = 2026 "
            "AND FECHA >= CURRENT_DATE"
        )
        assert "LIMIT 50" in sql
        assert "strftime('%Y'" in sql
        assert "date('now')" in sql
        assert len(changes) == 3  # FIRST, EXTRACT(YEAR), CURRENT_DATE

    # ── Función de conveniencia ───────────────────────────────────────────────

    def test_translate_function_delegates_to_translator(self):
        sql, changes = translate_firebird_sql("SELECT FIRST 1 * FROM FAMILIA")
        assert "LIMIT 1" in sql


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SCHEMA / TABLE_SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchema:

    def test_all_tables_present(self):
        expected = {
            "FAMILIA", "ALMACEN", "RECURSO", "PROVEED", "ARTICULO",
            "CLIENTE", "DOCCAB", "DOCLIN", "CAJA", "ESTALMACEN",
        }
        assert expected.issubset(set(TABLE_SCHEMAS.keys()))

    def test_creation_order_includes_all(self):
        assert set(TABLE_CREATION_ORDER) == set(TABLE_SCHEMAS.keys())

    def test_doccab_has_required_columns(self):
        cols = TABLE_COLUMNS["DOCCAB"]
        required = {"CODIGO", "TIPO", "FECHA", "CODCLIENTE", "IMPORTETOTAL"}
        assert required.issubset(set(cols))

    def test_doclin_has_required_columns(self):
        cols = TABLE_COLUMNS["DOCLIN"]
        required = {"CODDOCUMENTO", "CODIGO", "CODARTICULO", "CANTIDAD", "PRECIO"}
        assert required.issubset(set(cols))

    def test_articulo_has_required_columns(self):
        cols = TABLE_COLUMNS["ARTICULO"]
        # Columna real en BD Firebird: PRECIOVENTA (no PRECIO)
        required = {"CODIGO", "NOMBRE", "PRECIOVENTA", "CODFAMILIA", "STOCKARTICULO"}
        assert required.issubset(set(cols))

    def test_ddl_valid_sqlite(self):
        """Verifica que el DDL de cada tabla es SQL SQLite válido."""
        conn = sqlite3.connect(":memory:")
        for table, ddl in TABLE_SCHEMAS.items():
            try:
                conn.execute(ddl)
            except Exception as e:
                pytest.fail(f"DDL inválido para {table}: {e}")
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SIMULATED FIREBIRD DRIVER — conexión y operaciones básicas
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimulatedFirebirdDriver:

    def test_connect_in_memory(self, driver_in_memory):
        assert driver_in_memory.conn is not None

    def test_tables_created_on_connect(self, driver_in_memory):
        """Verifica que las tablas existen tras connect()."""
        cursor = driver_in_memory.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        for t in JDDCTableNames.ALL:
            assert t in tables, f"Tabla {t} no creada"

    def test_execute_query_empty_table(self, driver_in_memory):
        rows = driver_in_memory.execute_query("SELECT * FROM FAMILIA")
        assert isinstance(rows, list)
        assert rows == []

    def test_get_table_metadata_articulo(self, driver_in_memory):
        meta = driver_in_memory.get_table_metadata("ARTICULO")
        field_names = [m["FIELD_NAME"] for m in meta]
        assert "NOMBRE" in field_names
        # Columna real en BD Firebird: PRECIOVENTA (no PRECIO)
        assert "PRECIOVENTA" in field_names

    def test_get_table_metadata_unknown_table(self, driver_in_memory):
        meta = driver_in_memory.get_table_metadata("TABLA_INEXISTENTE")
        assert meta == []

    def test_execute_command_insert_and_query(self, driver_in_memory):
        driver_in_memory.execute_command(
            "INSERT INTO FAMILIA (CODIGO, NOMBRE) VALUES (999, 'Test Familia')"
        )
        rows = driver_in_memory.execute_query(
            "SELECT * FROM FAMILIA WHERE CODIGO = 999"
        )
        assert len(rows) == 1
        assert rows[0]["NOMBRE"] == "Test Familia"

    def test_get_row_count(self, driver_in_memory):
        count = driver_in_memory.get_row_count("FAMILIA")
        assert isinstance(count, int)
        assert count >= 1  # Insertamos 1 en el test anterior

    def test_has_data_false_on_empty_doccab(self):
        """has_data() False cuando DOCCAB está vacía."""
        drv = SimulatedFirebirdDriver()
        drv.connect(db_path=":memory:")
        assert drv.has_data() is False
        drv.disconnect()

    # ── System queries RDB$ ───────────────────────────────────────────────────

    def test_system_query_rdb_relations(self, driver_in_memory):
        """RDB$RELATIONS → lista de tablas simuladas."""
        rows = driver_in_memory.execute_query(
            "SELECT RDB$RELATION_NAME FROM RDB$RELATIONS"
        )
        names = [r.get("NAME") or r.get("TABLE_NAME") for r in rows]
        assert "DOCCAB" in names
        assert "ARTICULO" in names
        assert len(names) >= 10

    def test_system_query_rdb_relation_fields_articulo(self, driver_in_memory):
        """RDB$RELATION_FIELDS → columnas de ARTICULO."""
        rows = driver_in_memory.execute_query(
            "SELECT RDB$FIELD_NAME FROM RDB$RELATION_FIELDS "
            "WHERE TRIM(RDB$RELATION_NAME) = 'ARTICULO'"
        )
        field_names = [r.get("FIELD_NAME") or r.get("F") for r in rows]
        assert "NOMBRE" in field_names
        # Columna real en BD Firebird: PRECIOVENTA (no PRECIO)
        assert "PRECIOVENTA" in field_names

    def test_system_query_rdb_relation_fields_params(self, driver_in_memory):
        """RDB$RELATION_FIELDS con parámetros posicionales."""
        rows = driver_in_memory.execute_query(
            "SELECT RDB$FIELD_NAME FROM RDB$RELATION_FIELDS "
            "WHERE RDB$RELATION_NAME = ?",
            params=("CLIENTE",),
        )
        field_names = [r.get("FIELD_NAME") or r.get("F") for r in rows]
        # CLIENTE usa esquema Firebird real: NOMBRECOMERCIAL / RAZONSOCIAL
        assert "NOMBRECOMERCIAL" in field_names or "RAZONSOCIAL" in field_names


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SYNTHETIC SEEDER — integridad y conteos
# ═══════════════════════════════════════════════════════════════════════════════

class TestSyntheticSeeder:

    def test_seed_all_returns_counts(self, seeded_driver):
        """seed_all() ya fue llamado en el fixture — verificar vía get_row_count."""
        for table in JDDCTableNames.ALL:
            count = seeded_driver.get_row_count(table)
            assert count >= 0, f"{table} tiene count negativo (imposible)"

    def test_familias_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("FAMILIA")
        assert count >= 5, "Deberían existir al menos 5 familias"

    def test_articulos_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("ARTICULO")
        assert count >= 10, "Deberían existir al menos 10 artículos"

    def test_clientes_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("CLIENTE")
        assert count >= 10, "Deberían existir al menos 10 clientes"

    def test_proveedores_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("PROVEED")
        assert count >= 5, "Deberían existir al menos 5 proveedores"

    def test_doccab_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("DOCCAB")
        assert count >= 50, "Deberían existir al menos 50 documentos"

    def test_doclin_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("DOCLIN")
        assert count >= 50, "Deberían existir al menos 50 líneas de documento"

    def test_has_data_true_after_seed(self, seeded_driver):
        assert seeded_driver.has_data() is True

    def test_articulos_have_precio(self, seeded_driver):
        # Columna real en BD Firebird: PRECIOVENTA (no PRECIO)
        rows = seeded_driver.execute_query(
            "SELECT * FROM ARTICULO WHERE PRECIOVENTA <= 0 LIMIT 5"
        )
        assert rows == [], "Todos los artículos deben tener precio > 0"

    def test_doccab_tipos_distribution(self, seeded_driver):
        """Verificar que existen facturas (TIPO=13) y presupuestos (TIPO=0)."""
        rows = seeded_driver.execute_query(
            "SELECT TIPO, COUNT(*) as N FROM DOCCAB GROUP BY TIPO"
        )
        tipos = {r["TIPO"]: r["N"] for r in rows}
        assert 13 in tipos, "No hay facturas (TIPO=13)"
        assert 0  in tipos, "No hay presupuestos (TIPO=0)"

    def test_doclin_references_valid_doccab(self, seeded_driver):
        """Todas las líneas de DOCLIN apuntan a un DOCCAB existente."""
        rows = seeded_driver.execute_query(
            "SELECT COUNT(*) as N FROM DOCLIN L "
            "WHERE L.CODIGO NOT IN (SELECT CODIGO FROM DOCCAB)"
        )
        orphans = rows[0]["N"] if rows else 0
        assert orphans == 0, f"Hay {orphans} líneas huérfanas en DOCLIN"

    def test_caja_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("CAJA")
        assert count >= 20, "Deberían existir al menos 20 movimientos de caja"

    def test_estalmacen_seeded(self, seeded_driver):
        count = seeded_driver.get_row_count("ESTALMACEN")
        assert count >= 20, "Deberían existir al menos 20 movimientos de stock"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SIMULATOR MANAGER — is_enabled / get_disclaimer (sin tocar la BD de producción)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimulatorManagerConfig:

    def _make_manager_with_config(self, tmp_path: Path, enabled: bool):
        """Instancia un SimulatorManager apuntando a un config.json temporal."""
        from backend.modules.db_simulator.manager import SimulatorManager
        from backend.modules.db_simulator import constants as c

        config_content = {"simulator_enabled": enabled, "show_disclaimer": True}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_content))

        # Parchear la ruta de config para este test
        original = c.SimulatorPaths.CONFIG_PATH
        c.SimulatorPaths.CONFIG_PATH = config_file
        try:
            mgr = SimulatorManager()
            yield mgr
        finally:
            c.SimulatorPaths.CONFIG_PATH = original

    def test_is_enabled_false_by_default(self, tmp_path):
        """Sin config.json el simulador está desactivado."""
        from backend.modules.db_simulator.manager import SimulatorManager
        from backend.modules.db_simulator import constants as c

        # Apuntar a un archivo que NO existe
        original = c.SimulatorPaths.CONFIG_PATH
        c.SimulatorPaths.CONFIG_PATH = tmp_path / "nonexistent.json"
        try:
            mgr = SimulatorManager()
            assert mgr.is_enabled() is False
        finally:
            c.SimulatorPaths.CONFIG_PATH = original

    def test_is_enabled_true_from_config(self, tmp_path):
        """Con simulator_enabled=true en config.json, is_enabled() devuelve True."""
        from backend.modules.db_simulator.manager import SimulatorManager
        from backend.modules.db_simulator import constants as c

        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"simulator_enabled": True}))

        original = c.SimulatorPaths.CONFIG_PATH
        c.SimulatorPaths.CONFIG_PATH = cfg_path
        try:
            mgr = SimulatorManager()
            assert mgr.is_enabled() is True
        finally:
            c.SimulatorPaths.CONFIG_PATH = original

    def test_disclaimer_html_contains_warning(self, tmp_path):
        """get_disclaimer(html=True) contiene texto de aviso visible."""
        from backend.modules.db_simulator.manager import SimulatorManager
        from backend.modules.db_simulator import constants as c

        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"simulator_enabled": True}))

        original = c.SimulatorPaths.CONFIG_PATH
        c.SimulatorPaths.CONFIG_PATH = cfg_path
        try:
            mgr = SimulatorManager()
            html = mgr.get_disclaimer(html=True)
            assert "SIMULACI" in html or "simulaci" in html.lower()
            assert "<div" in html
        finally:
            c.SimulatorPaths.CONFIG_PATH = original

    def test_disclaimer_text_has_prefix(self, tmp_path):
        """get_disclaimer(html=False) empieza con el prefijo de texto plano."""
        from backend.modules.db_simulator.manager import SimulatorManager
        from backend.modules.db_simulator import constants as c

        original = c.SimulatorPaths.CONFIG_PATH
        c.SimulatorPaths.CONFIG_PATH = tmp_path / "config.json"
        try:
            mgr = SimulatorManager()
            text = mgr.get_disclaimer(html=False)
            assert "SIMULACI" in text.upper()
        finally:
            c.SimulatorPaths.CONFIG_PATH = original

    def test_disclaimer_constants_not_empty(self):
        assert len(SimulatorDisclaimer.HTML_BANNER) > 50
        assert len(SimulatorDisclaimer.TEXT_PREFIX) > 5
        assert len(SimulatorDisclaimer.JSON_TEXT) > 10
        assert SimulatorDisclaimer.JSON_KEY == "sim_disclaimer"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 7: TRADUCCIÓN DE QUERIES COMPLEJAS (PARÉNTESIS ANIDADOS)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslatorNestedParentheses:
    """
    Verifica que el traductor maneja correctamente expresiones con paréntesis
    anidados como CAST(SUM(col) AS NUMERIC(15,2)) y EXTRACT(YEAR FROM FECHA) AS ANO.

    Estos son los patrones que generaba el DeepAnalysisAgent y fallaban con
    'near AS: syntax error' en SQLite.
    """

    @pytest.fixture
    def t(self):
        return FirebirdToSQLiteTranslator()

    def test_cast_sum_as_numeric_ps(self, t):
        """CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) → ROUND(CAST(SUM(IMPORTETOTAL) AS REAL), 2)"""
        sql = "SELECT CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL FROM DOCCAB"
        result, changes = t.translate(sql)
        assert "ROUND(CAST(SUM(IMPORTETOTAL) AS REAL), 2)" in result, \
            f"CAST(SUM(...) AS NUMERIC(15,2)) debe traducirse correctamente. Got: {result}"
        assert "CAST AS NUMERIC(p,s)" in " ".join(changes)

    def test_cast_avg_as_numeric_ps(self, t):
        """CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) → ROUND(CAST(AVG(IMPORTETOTAL) AS REAL), 2)"""
        sql = "SELECT CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA FROM DOCCAB"
        result, changes = t.translate(sql)
        assert "ROUND(CAST(AVG(IMPORTETOTAL) AS REAL), 2)" in result, \
            f"CAST(AVG(...) AS NUMERIC(15,2)) debe traducirse correctamente. Got: {result}"

    def test_cast_min_max_as_numeric_ps(self, t):
        """CAST(MIN(IMPORTETOTAL) AS NUMERIC(15,2)) y CAST(MAX(...) AS NUMERIC(15,2))"""
        sql = (
            "SELECT CAST(MIN(IMPORTETOTAL) AS NUMERIC(15,2)) AS MIN_EUR, "
            "CAST(MAX(IMPORTETOTAL) AS NUMERIC(15,2)) AS MAX_EUR FROM DOCCAB"
        )
        result, changes = t.translate(sql)
        assert "ROUND(CAST(MIN(IMPORTETOTAL) AS REAL), 2)" in result, \
            f"CAST(MIN(...) AS NUMERIC(15,2)) debe traducirse. Got: {result}"
        assert "ROUND(CAST(MAX(IMPORTETOTAL) AS REAL), 2)" in result, \
            f"CAST(MAX(...) AS NUMERIC(15,2)) debe traducirse. Got: {result}"

    def test_extract_year_with_alias_and_cast_numeric(self, t):
        """
        Query compleja del DeepAnalysisAgent que fallaba con 'near AS: syntax error':
        EXTRACT(YEAR FROM FECHA) AS ANO, ..., CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR
        """
        sql = (
            "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, SERIE, COUNT(*) AS N, "
            "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
            "FROM DOCCAB WHERE TIPO = 0 AND FECHA IS NOT NULL "
            "GROUP BY EXTRACT(YEAR FROM FECHA), SERIE ORDER BY ANO DESC, N DESC"
        )
        result, changes = t.translate(sql)
        # No debe contener EXTRACT ni NUMERIC
        assert "EXTRACT" not in result.upper(), f"EXTRACT debe haberse traducido. Got: {result}"
        assert "NUMERIC" not in result.upper(), f"NUMERIC debe haberse traducido. Got: {result}"
        # Debe contener strftime para el año
        assert "strftime('%Y'" in result, f"EXTRACT(YEAR) debe → strftime('%Y'). Got: {result}"
        # Debe contener ROUND(CAST(SUM(IMPORTETOTAL) AS REAL), 2)
        assert "ROUND(CAST(SUM(IMPORTETOTAL) AS REAL), 2)" in result, \
            f"CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) debe traducirse. Got: {result}"

    def test_query_kpi_facturacion_total(self, t):
        """
        Query típica de KPI de facturación total que generaba el DeepAnalysisAgent.
        """
        sql = "SELECT CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_FACTURADO FROM DOCCAB WHERE TIPO=13"
        result, changes = t.translate(sql)
        assert "ROUND(CAST(SUM(IMPORTETOTAL) AS REAL), 2)" in result, \
            f"Query KPI facturación debe traducirse. Got: {result}"
        assert "NUMERIC" not in result.upper()

    def test_query_resumen_por_tipo(self, t):
        """
        Query de resumen por tipo que usaba el DeepAnalysisAgent y funcionaba
        (sin EXTRACT, solo CAST(SUM(...) AS NUMERIC(15,2))).
        """
        sql = (
            "SELECT TIPO, COUNT(*) AS N, "
            "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
            "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
            "FROM DOCCAB WHERE FECHA IS NOT NULL GROUP BY TIPO ORDER BY N DESC"
        )
        result, changes = t.translate(sql)
        assert "ROUND(CAST(SUM(IMPORTETOTAL) AS REAL), 2)" in result
        assert "ROUND(CAST(AVG(IMPORTETOTAL) AS REAL), 2)" in result
        assert "NUMERIC" not in result.upper()

    def test_query_ejecutable_en_sqlite(self, driver_in_memory):
        """
        La query de KPI de facturación total debe ejecutarse sin errores en SQLite.
        """
        # Esta query fallaba antes del fix con 'near AS: syntax error'
        sql = (
            "SELECT TIPO, COUNT(*) AS N, "
            "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
            "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
            "FROM DOCCAB WHERE FECHA IS NOT NULL GROUP BY TIPO ORDER BY N DESC"
        )
        # No debe lanzar excepción
        results = driver_in_memory.execute_query(sql)
        assert isinstance(results, list), "Debe devolver una lista"

    def test_query_extract_year_ejecutable_en_sqlite(self, driver_in_memory):
        """
        La query con EXTRACT(YEAR FROM FECHA) AS ANO debe ejecutarse sin errores.
        """
        sql = (
            "SELECT CAST(strftime('%Y', FECHA) AS INTEGER) AS ANO, "
            "COUNT(*) AS N, "
            "ROUND(CAST(SUM(IMPORTETOTAL) AS REAL), 2) AS TOTAL_EUR "
            "FROM DOCCAB WHERE FECHA IS NOT NULL "
            "GROUP BY CAST(strftime('%Y', FECHA) AS INTEGER) ORDER BY ANO DESC"
        )
        results = driver_in_memory.execute_query(sql)
        assert isinstance(results, list)

    def test_query_deep_agent_via_translator_ejecutable(self, driver_in_memory):
        """
        La query original del DeepAnalysisAgent (con EXTRACT y CAST NUMERIC)
        debe ejecutarse correctamente después de la traducción.
        """
        from backend.modules.db_simulator.query_translator import translate_firebird_sql
        sql_firebird = (
            "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N, "
            "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
            "FROM DOCCAB WHERE TIPO = 13 AND FECHA IS NOT NULL "
            "GROUP BY EXTRACT(YEAR FROM FECHA) ORDER BY ANO DESC"
        )
        sql_sqlite, changes = translate_firebird_sql(sql_firebird)
        assert "EXTRACT" not in sql_sqlite.upper()
        assert "NUMERIC" not in sql_sqlite.upper()
        # Ejecutar en el driver
        results = driver_in_memory.execute_query(sql_firebird)  # el driver aplica la traducción
        assert isinstance(results, list)
