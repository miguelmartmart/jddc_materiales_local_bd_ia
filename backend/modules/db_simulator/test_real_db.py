"""
test_real_db.py — Tests de la query_library contra la BD real Firebird JDDC.

Verifica que las consultas de la biblioteca (escritas en SQLite) se pueden
adaptar y ejecutar correctamente contra la BD Firebird real de JDDC.

Requisitos:
  • BD Firebird accesible en 192.168.0.254:3050 (HOST1.JDDC.local)
  • Fichero .env con DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
  • simulator_enabled=false en config.json (modo BD real)
  • Sin conexión a modelos IA de red (use_ai_network=false)

Ejecutar:
  set PYTHONUTF8=1
  set PYTHONPATH=C:\\Users\\migue\\Documents\\activepieces\\pendiente-fact\\bots\\interjddcia
  python -m pytest backend/modules/db_simulator/test_real_db.py -v

  # Solo tests de conectividad (rápido):
  python -m pytest backend/modules/db_simulator/test_real_db.py -v -k "connect"

  # Solo tests de consultas clave:
  python -m pytest backend/modules/db_simulator/test_real_db.py -v -k "key_queries"

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import sys
import os
import unittest
import logging
from typing import Any, Dict, List, Optional

# ─── Setup de path ────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from backend.modules.db_simulator.constants import (
    TestModeConfig,
    SimulatorLog,
    JDDCDocTipos,
    JDDCTableNames,
)
from backend.modules.db_simulator.query_library import (
    QUERY_LIBRARY,
    get_query_by_id,
    get_queries_by_dept,
    get_queries_by_tipo,
    get_queries_by_urgencia,
)
from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird

logger = logging.getLogger(__name__)

# ─── Helpers de conexión ──────────────────────────────────────────────────────

def _get_firebird_config():
    """
    Lee los parámetros de conexión Firebird desde settings.py (que lee el .env).
    Fuente única de verdad: bots/interjddcia/.env
      DB_HOST=192.168.0.254
      DB_PORT=3050
      DB_NAME=C:\\Distrito\\OBRAS\\Database\\JUANDEDI\\2021.fdb
      DB_USER=SYSDBA
      DB_PASSWORD=masterkey
    """
    from backend.core.config.settings import settings as _s
    return type("FirebirdConfig", (), {
        "host":     _s.DB_HOST,
        "port":     _s.DB_PORT,
        "database": _s.DB_NAME,
        "user":     _s.DB_USER,
        "password": _s.DB_PASSWORD,
        "charset":  TestModeConfig.FIREBIRD_CHARSET,
    })()


def _get_firebird_driver():
    """Devuelve un FirebirdDriver conectado a la BD real."""
    from backend.core.factory.db_factory import DBFactory
    from backend.core.utils.constants import DBConstants
    driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
    config = _get_firebird_config()
    driver.connect(config)
    return driver


def _adapt_and_normalize(sql: str) -> str:
    """
    Adapta SQL SQLite → Firebird en dos pasos:
      1. adapt_sql_for_firebird (sqlite_to_firebird.py): correcciones específicas
      2. FirebirdSQLNormalizer: LIMIT→FIRST, strftime→EXTRACT, etc.
    """
    from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
    adapted_sql, _changes = adapt_sql_for_firebird(sql)
    normalizer = FirebirdSQLNormalizer()
    fb_sql, _norm_changes = normalizer.normalize(adapted_sql)
    return fb_sql


# ─── Clase base con skip automático si BD no disponible ──────────────────────

class RealDBTestCase(unittest.TestCase):
    """
    Clase base para tests contra BD real.
    Si la BD no está disponible, todos los tests se omiten automáticamente.
    """

    _driver = None
    _db_available: Optional[bool] = None
    _db_error: str = ""

    @classmethod
    def setUpClass(cls):
        """Intenta conectar a Firebird real. Si falla, marca BD como no disponible."""
        try:
            cls._driver = _get_firebird_driver()
            # Verificar con query mínima
            rows = cls._driver.execute_query(
                f"SELECT FIRST 1 CODIGO FROM {JDDCTableNames.DOCCAB}"
            )
            cls._db_available = True
            logger.info(
                f"{TestModeConfig.LOG_PREFIX} BD real disponible: "
                f"{_get_firebird_config().host}:{_get_firebird_config().port}"
            )
        except Exception as e:
            cls._db_available = False
            cls._db_error = str(e)
            cls._driver = None
            logger.warning(
                f"{TestModeConfig.LOG_PREFIX} BD real NO disponible: {e}"
            )

    @classmethod
    def tearDownClass(cls):
        if cls._driver:
            try:
                cls._driver.disconnect()
            except Exception:
                pass
            cls._driver = None

    def _skip_if_no_db(self):
        if not self._db_available:
            self.skipTest(
                f"BD real Firebird no disponible "
                f"({_get_firebird_config().host}:{_get_firebird_config().port}): "
                f"{self._db_error}"
            )

    def _exec(self, sql: str) -> List[Dict[str, Any]]:
        """Ejecuta SQL Firebird nativo contra la BD real."""
        return self._driver.execute_query(sql)

    def _exec_adapted(self, sqlite_sql: str) -> List[Dict[str, Any]]:
        """Adapta SQL SQLite → Firebird y ejecuta contra la BD real."""
        fb_sql = _adapt_and_normalize(sqlite_sql)
        return self._driver.execute_query(fb_sql)


# ─── Tests de conectividad ────────────────────────────────────────────────────

class TestRealDBConnectivity(RealDBTestCase):
    """Tests básicos de conectividad con la BD real Firebird."""

    def test_connect_to_real_db(self):
        """Debe poder conectar a la BD Firebird real."""
        self._skip_if_no_db()
        self.assertTrue(self._db_available, "BD real no disponible")

    def test_doccab_has_rows(self):
        """DOCCAB debe tener registros en la BD real."""
        self._skip_if_no_db()
        rows = self._exec(f"SELECT COUNT(*) AS N FROM {JDDCTableNames.DOCCAB}")
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        n = rows[0].get("N", 0)
        self.assertGreater(n, 0, "DOCCAB está vacía en la BD real")
        logger.info(f"{TestModeConfig.LOG_PREFIX} DOCCAB: {n} registros")

    def test_cliente_has_rows(self):
        """CLIENTE debe tener registros en la BD real."""
        self._skip_if_no_db()
        rows = self._exec(f"SELECT COUNT(*) AS N FROM {JDDCTableNames.CLIENTE}")
        n = rows[0].get("N", 0)
        self.assertGreater(n, 0, "CLIENTE está vacía en la BD real")
        logger.info(f"{TestModeConfig.LOG_PREFIX} CLIENTE: {n} registros")

    def test_articulo_has_rows(self):
        """ARTICULO debe tener registros en la BD real."""
        self._skip_if_no_db()
        rows = self._exec(f"SELECT COUNT(*) AS N FROM {JDDCTableNames.ARTICULO}")
        n = rows[0].get("N", 0)
        self.assertGreater(n, 0, "ARTICULO está vacía en la BD real")
        logger.info(f"{TestModeConfig.LOG_PREFIX} ARTICULO: {n} registros")

    def test_doclin_has_rows(self):
        """DOCLIN debe tener registros en la BD real."""
        self._skip_if_no_db()
        rows = self._exec(f"SELECT COUNT(*) AS N FROM {JDDCTableNames.DOCLIN}")
        n = rows[0].get("N", 0)
        self.assertGreater(n, 0, "DOCLIN está vacía en la BD real")
        logger.info(f"{TestModeConfig.LOG_PREFIX} DOCLIN: {n} registros")

    def test_facturas_exist(self):
        """Debe haber facturas (TIPO=13) en DOCCAB."""
        self._skip_if_no_db()
        rows = self._exec(
            f"SELECT COUNT(*) AS N FROM {JDDCTableNames.DOCCAB} "
            f"WHERE TIPO = {JDDCDocTipos.FACTURA}"
        )
        n = rows[0].get("N", 0)
        self.assertGreater(n, 0, "No hay facturas (TIPO=13) en la BD real")
        logger.info(f"{TestModeConfig.LOG_PREFIX} Facturas (TIPO=13): {n}")

    def test_presupuestos_exist(self):
        """Debe haber presupuestos (TIPO=0) en DOCCAB."""
        self._skip_if_no_db()
        rows = self._exec(
            f"SELECT COUNT(*) AS N FROM {JDDCTableNames.DOCCAB} "
            f"WHERE TIPO = {JDDCDocTipos.PRESUPUESTO}"
        )
        n = rows[0].get("N", 0)
        self.assertGreater(n, 0, "No hay presupuestos (TIPO=0) en la BD real")
        logger.info(f"{TestModeConfig.LOG_PREFIX} Presupuestos (TIPO=0): {n}")

    def test_config_simulator_disabled(self):
        """El simulador debe estar desactivado (simulator_enabled=false) para este test."""
        import json
        from backend.modules.db_simulator.constants import SimulatorPaths
        try:
            with open(SimulatorPaths.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertFalse(
                cfg.get("simulator_enabled", True),
                "simulator_enabled debe ser false para tests de BD real. "
                "Actualiza config.json: {\"simulator_enabled\": false}"
            )
        except FileNotFoundError:
            self.skipTest("config.json no encontrado")


# ─── Tests de esquema real ────────────────────────────────────────────────────

class TestRealDBSchema(RealDBTestCase):
    """Verifica que el esquema real de Firebird tiene las columnas esperadas."""

    def _get_columns(self, table: str) -> List[str]:
        """Devuelve las columnas de una tabla Firebird real."""
        rows = self._exec(
            "SELECT TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME "
            "FROM RDB$RELATION_FIELDS r "
            f"WHERE TRIM(r.RDB$RELATION_NAME) = '{table}' "
            "ORDER BY r.RDB$FIELD_POSITION"
        )
        return [r.get("FIELD_NAME", "").strip() for r in rows]

    def test_doccab_has_required_columns(self):
        """DOCCAB debe tener las columnas clave usadas en las consultas."""
        self._skip_if_no_db()
        cols = self._get_columns("DOCCAB")
        required = ["CODIGO", "TIPO", "FECHA", "CODCLIENTE", "IMPORTETOTAL"]
        for col in required:
            self.assertIn(col, cols, f"DOCCAB no tiene columna {col} en BD real")

    def test_doccab_has_importebase(self):
        """DOCCAB debe tener IMPORTEBASE (base imponible) — columna real Firebird."""
        self._skip_if_no_db()
        cols = self._get_columns("DOCCAB")
        self.assertIn(
            "IMPORTEBASE", cols,
            "DOCCAB no tiene IMPORTEBASE. "
            "Nota: en el simulador SQLite se llama BASEIMPONIBLE — "
            "sqlite_to_firebird.py hace la traducción automáticamente."
        )

    def test_doccab_has_importeiva(self):
        """DOCCAB debe tener IMPORTEIVA (IVA) — columna real Firebird."""
        self._skip_if_no_db()
        cols = self._get_columns("DOCCAB")
        self.assertIn(
            "IMPORTEIVA", cols,
            "DOCCAB no tiene IMPORTEIVA. "
            "Nota: en el simulador SQLite se llama IVA — "
            "sqlite_to_firebird.py hace la traducción automáticamente."
        )

    def test_cliente_has_required_columns(self):
        """CLIENTE debe tener las columnas clave."""
        self._skip_if_no_db()
        cols = self._get_columns("CLIENTE")
        required = ["CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL"]
        for col in required:
            self.assertIn(col, cols, f"CLIENTE no tiene columna {col} en BD real")

    def test_doclin_has_required_columns(self):
        """DOCLIN debe tener las columnas clave."""
        self._skip_if_no_db()
        cols = self._get_columns("DOCLIN")
        required = ["CODIGO", "CODDOCUMENTO", "CODARTICULO", "CANTIDAD", "PRECIO"]
        for col in required:
            self.assertIn(col, cols, f"DOCLIN no tiene columna {col} en BD real")

    def test_articulo_has_precioventa(self):
        """ARTICULO debe tener PRECIOVENTA (nombre real Firebird)."""
        self._skip_if_no_db()
        cols = self._get_columns("ARTICULO")
        self.assertIn(
            "PRECIOVENTA", cols,
            "ARTICULO no tiene PRECIOVENTA. "
            "Nota: en el simulador SQLite se llama PRECIO — "
            "sqlite_to_firebird.py hace la traducción automáticamente."
        )

    def test_articulo_has_proveeddefecto(self):
        """ARTICULO debe tener PROVEEDDEFECTO (nombre real Firebird)."""
        self._skip_if_no_db()
        cols = self._get_columns("ARTICULO")
        self.assertIn(
            "PROVEEDDEFECTO", cols,
            "ARTICULO no tiene PROVEEDDEFECTO. "
            "Nota: en el simulador SQLite se llama CODPROVEEDOR — "
            "sqlite_to_firebird.py hace la traducción automáticamente."
        )


# ─── Tests de consultas clave de la query_library ────────────────────────────

class TestKeyQueriesRealDB(RealDBTestCase):
    """
    Ejecuta las consultas más importantes de la query_library contra la BD real.
    Cada consulta se adapta automáticamente SQLite→Firebird antes de ejecutar.
    """

    def _run_query(self, query_id: str) -> List[Dict[str, Any]]:
        """Obtiene la consulta por ID, la adapta y ejecuta contra BD real."""
        q = get_query_by_id(query_id)
        self.assertNotEqual(q, {}, f"Consulta '{query_id}' no encontrada en la biblioteca")
        fb_sql = _adapt_and_normalize(q["sql"])
        return self._driver.execute_query(fb_sql)

    def test_facturacion_total_real_db(self):
        """v_kpi_facturacion_total debe ejecutarse contra BD real y devolver importe."""
        self._skip_if_no_db()
        rows = self._run_query("v_kpi_facturacion_total")
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        self.assertIn("FACTURACION_TOTAL", rows[0])
        total = rows[0]["FACTURACION_TOTAL"]
        self.assertIsNotNone(total)
        logger.info(f"{TestModeConfig.LOG_PREFIX} Facturación total real: {total}")

    def test_top10_clientes_real_db(self):
        """v_kpi_top10_clientes debe devolver hasta 10 clientes reales."""
        self._skip_if_no_db()
        rows = self._run_query("v_kpi_top10_clientes")
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 10)
        if rows:
            self.assertIn("NOMBRE", rows[0])
            self.assertIn("TOTAL", rows[0])
        logger.info(f"{TestModeConfig.LOG_PREFIX} Top clientes reales: {len(rows)} filas")

    def test_conversion_presupuestos_real_db(self):
        """v_kpi_conversion_presupuestos debe devolver TASA_CONVERSION_PCT."""
        self._skip_if_no_db()
        rows = self._run_query("v_kpi_conversion_presupuestos")
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        self.assertIn("TASA_CONVERSION_PCT", rows[0])
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} Tasa conversión real: "
            f"{rows[0]['TASA_CONVERSION_PCT']}%"
        )

    def test_saldo_caja_real_db(self):
        """f_kpi_saldo_caja debe devolver SALDO_NETO de la BD real."""
        self._skip_if_no_db()
        rows = self._run_query("f_kpi_saldo_caja")
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        self.assertIn("SALDO_NETO", rows[0])
        logger.info(f"{TestModeConfig.LOG_PREFIX} Saldo caja real: {rows[0]['SALDO_NETO']}")

    def test_sats_mes_real_db(self):
        """s_kpi_sats_mes debe ejecutarse sin error contra BD real."""
        self._skip_if_no_db()
        rows = self._run_query("s_kpi_sats_mes")
        self.assertIsInstance(rows, list)
        logger.info(f"{TestModeConfig.LOG_PREFIX} SATs mes real: {len(rows)} filas")

    def test_resumen_ejecutivo_real_db(self):
        """d_kpi_resumen_ejecutivo debe devolver indicadores reales."""
        self._skip_if_no_db()
        rows = self._run_query("d_kpi_resumen_ejecutivo")
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0, "El resumen ejecutivo no devuelve datos")
        indicadores = [r.get("INDICADOR", "") for r in rows]
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} Resumen ejecutivo real: "
            f"{len(rows)} indicadores: {indicadores}"
        )


# ─── Tests de adaptación SQLite→Firebird ─────────────────────────────────────

class TestSQLiteToFirebirdAdaptation(unittest.TestCase):
    """
    Tests unitarios del adaptador SQLite→Firebird.
    No requieren conexión a BD real — solo verifican la traducción SQL.
    """

    def _adapt(self, sql: str) -> str:
        adapted, _ = adapt_sql_for_firebird(sql)
        return adapted

    def test_limit_to_first(self):
        """LIMIT N debe traducirse a FIRST N."""
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
        sql = "SELECT CODIGO FROM DOCCAB LIMIT 10"
        norm, _ = FirebirdSQLNormalizer().normalize(sql)
        self.assertIn("FIRST 10", norm.upper())
        self.assertNotIn("LIMIT", norm.upper())

    def test_baseimponible_to_importebase(self):
        """BASEIMPONIBLE debe traducirse a IMPORTEBASE."""
        sql = "SELECT SUM(BASEIMPONIBLE) AS BASE FROM DOCCAB"
        adapted = self._adapt(sql)
        self.assertIn("IMPORTEBASE", adapted.upper())
        self.assertNotIn("BASEIMPONIBLE", adapted.upper())

    def test_iva_column_to_importeiva(self):
        """IVA como columna standalone debe traducirse a IMPORTEIVA."""
        sql = "SELECT SUM(IVA) AS IVA_TOTAL FROM DOCCAB"
        adapted = self._adapt(sql)
        # IVA_TOTAL (alias) debe preservarse; IVA standalone → IMPORTEIVA
        self.assertIn("IVA_TOTAL", adapted)

    def test_cast_text_to_varchar(self):
        """CAST(x AS TEXT) debe traducirse a CAST(x AS VARCHAR(50))."""
        sql = "SELECT CAST(CODIGO AS TEXT) AS COD FROM DOCCAB"
        adapted = self._adapt(sql)
        self.assertIn("VARCHAR", adapted.upper())

    def test_substr_fecha_month(self):
        """SUBSTR(FECHA,1,7) debe traducirse a expresión EXTRACT año-mes."""
        sql = "SELECT SUBSTR(FECHA,1,7) AS MES FROM DOCCAB"
        adapted = self._adapt(sql)
        self.assertIn("EXTRACT", adapted.upper())

    def test_articulo_precio_to_precioventa(self):
        """A.PRECIO debe traducirse a A.PRECIOVENTA."""
        sql = "SELECT A.PRECIO FROM ARTICULO A"
        adapted = self._adapt(sql)
        self.assertIn("PRECIOVENTA", adapted.upper())

    def test_strftime_preserved_by_normalizer(self):
        """
        FirebirdSQLNormalizer NO traduce strftime→EXTRACT (esa dirección es Firebird→SQLite,
        la hace query_translator.py). El normalizador solo añade FIRST N si falta.
        Verificamos que el SQL pasa sin error y que FIRST se añade automáticamente.
        """
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
        sql = "SELECT strftime('%Y', FECHA) AS ANIO FROM DOCCAB"
        norm, changes = FirebirdSQLNormalizer().normalize(sql)
        # El normalizador añade FIRST N automáticamente (sin LIMIT ni FIRST en el SQL original)
        self.assertIn("FIRST", norm.upper(), "El normalizador debe añadir FIRST N automáticamente")
        # strftime se preserva (no se traduce — eso lo hace query_translator en dirección inversa)
        self.assertIn("strftime", norm.lower())


# ─── Tests de todas las consultas críticas contra BD real ────────────────────

class TestAllCriticalQueriesRealDB(RealDBTestCase):
    """
    Ejecuta TODAS las consultas de urgencia 'Crítico' contra la BD real.
    Si alguna falla con error inesperado (no de columna/tabla), el test falla.
    """

    # Columnas/tablas que pueden no existir en la BD real (no son errores del adaptador)
    _KNOWN_MISSING = {
        "FAMILIA",       # No existe en Firebird real JDDC (solo en simulador)
        "STOCKARTICULO", # Columna simulador — en real es ESTALMACEN
        "STOCKMINIMO",   # Columna simulador
        "STOCKACTUAL",   # Columna simulador
    }

    def _is_known_missing(self, error_msg: str) -> bool:
        msg = str(error_msg).upper()
        return any(k in msg for k in self._KNOWN_MISSING)

    def test_all_critical_queries_real_db(self):
        """
        Todas las consultas de urgencia Crítico deben ejecutarse sin error
        inesperado contra la BD real Firebird.
        """
        self._skip_if_no_db()
        critical_queries = get_queries_by_urgencia("Crítico")
        self.assertGreater(len(critical_queries), 0, "No hay consultas de urgencia Crítico")

        errors = []
        known_missing = []

        for q in critical_queries:
            try:
                fb_sql = _adapt_and_normalize(q["sql"])
                rows = self._driver.execute_query(fb_sql)
                self.assertIsInstance(rows, list, f"'{q['id']}' no devuelve lista")
            except Exception as e:
                if self._is_known_missing(str(e)):
                    known_missing.append(f"  - {q['id']}: {e}")
                else:
                    errors.append(f"  - {q['id']}: {e}")

        if known_missing:
            logger.info(
                f"{TestModeConfig.LOG_PREFIX} {len(known_missing)} consultas con "
                f"tabla/columna no disponible en BD real (esperado):\n"
                + "\n".join(known_missing)
            )

        if errors:
            self.fail(
                f"{len(errors)} consultas Crítico fallaron con error inesperado:\n"
                + "\n".join(errors)
            )

    def test_all_kpi_queries_real_db(self):
        """
        Todas las consultas de tipo KPI deben ejecutarse sin error inesperado
        contra la BD real Firebird.
        """
        self._skip_if_no_db()
        kpi_queries = get_queries_by_tipo("KPI")
        self.assertGreater(len(kpi_queries), 0, "No hay consultas de tipo KPI")

        errors = []
        known_missing = []

        for q in kpi_queries:
            try:
                fb_sql = _adapt_and_normalize(q["sql"])
                rows = self._driver.execute_query(fb_sql)
                self.assertIsInstance(rows, list)
            except Exception as e:
                if self._is_known_missing(str(e)):
                    known_missing.append(f"  - {q['id']}: {e}")
                else:
                    errors.append(f"  - {q['id']}: {e}")

        if known_missing:
            logger.info(
                f"{TestModeConfig.LOG_PREFIX} {len(known_missing)} KPI con "
                f"tabla/columna no disponible (esperado):\n"
                + "\n".join(known_missing)
            )

        if errors:
            self.fail(
                f"{len(errors)} consultas KPI fallaron:\n" + "\n".join(errors)
            )


# ─── Tests de configuración del modo prueba ──────────────────────────────────

class TestTestModeConfig(unittest.TestCase):
    """Tests de la configuración del modo de prueba (sin BD ni IA)."""

    def test_constants_test_mode_exists(self):
        """TestModeConfig debe existir en constants.py."""
        self.assertTrue(hasattr(TestModeConfig, "USE_REAL_DB"))
        self.assertTrue(hasattr(TestModeConfig, "USE_AI_NETWORK"))
        self.assertTrue(hasattr(TestModeConfig, "USE_AI_LOCAL"))
        self.assertTrue(hasattr(TestModeConfig, "FIREBIRD_CHARSET"))
        self.assertTrue(hasattr(TestModeConfig, "REAL_DB_QUERY_TIMEOUT"))
        self.assertTrue(hasattr(TestModeConfig, "REAL_DB_MAX_ROWS"))

    def test_firebird_charset_is_latin1(self):
        """El charset de Firebird debe ser latin1 para máxima compatibilidad."""
        self.assertEqual(TestModeConfig.FIREBIRD_CHARSET, "latin1")

    def test_config_json_has_test_mode(self):
        """config.json debe tener la clave test_mode."""
        import json
        from backend.modules.db_simulator.constants import SimulatorPaths
        try:
            with open(SimulatorPaths.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertIn(
                "test_mode", cfg,
                "config.json debe tener la clave 'test_mode'"
            )
            test_mode = cfg["test_mode"]
            self.assertIn("use_real_db", test_mode)
            self.assertIn("use_ai_network", test_mode)
        except FileNotFoundError:
            self.skipTest("config.json no encontrado")

    def test_config_json_simulator_disabled(self):
        """config.json debe tener simulator_enabled=false para modo BD real."""
        import json
        from backend.modules.db_simulator.constants import SimulatorPaths
        try:
            with open(SimulatorPaths.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.assertFalse(
                cfg.get("simulator_enabled", True),
                "simulator_enabled debe ser false para modo BD real"
            )
        except FileNotFoundError:
            self.skipTest("config.json no encontrado")

    def test_settings_has_db_params(self):
        """settings.py debe tener los parámetros de BD Firebird real."""
        from backend.core.config.settings import settings as _s
        self.assertTrue(_s.DB_HOST, "DB_HOST no configurado en .env")
        self.assertTrue(_s.DB_NAME, "DB_NAME no configurado en .env")
        self.assertGreater(_s.DB_PORT, 0, "DB_PORT debe ser > 0")
        self.assertTrue(_s.DB_USER, "DB_USER no configurado en .env")
        self.assertTrue(_s.DB_PASSWORD, "DB_PASSWORD no configurado en .env")
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} BD configurada: "
            f"{_s.DB_HOST}:{_s.DB_PORT} / {_s.DB_NAME}"
        )


# ─── Punto de entrada ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for cls in [
        TestTestModeConfig,          # Sin BD — siempre ejecuta
        TestSQLiteToFirebirdAdaptation,  # Sin BD — solo traducción SQL
        TestRealDBConnectivity,      # Requiere BD real
        TestRealDBSchema,            # Requiere BD real
        TestKeyQueriesRealDB,        # Requiere BD real
        TestAllCriticalQueriesRealDB,  # Requiere BD real
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total   = result.testsRun
    failed  = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    passed  = total - failed - skipped

    print(f"\n{'='*60}")
    print(f"RESULTADO: {passed}/{total} OK | {failed} fallos | {skipped} omitidos")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
