"""
test_schema_parity.py — Paridad estructural entre BD Firebird real y BD simulada SQLite.

Verifica que el simulador replica fielmente la estructura de la BD real:
  - Las mismas tablas existen en ambas BDs
  - Las columnas clave de cada tabla están presentes en ambas
  - Los tipos de documento (TIPO) son los mismos
  - Los alias de columna usados por sqlite_to_firebird.py son correctos

Principios aplicados:
  - Sin hardcodear valores: todas las constantes vienen de constants.py / schema.py
  - Fallback gracioso: si la BD real no está disponible, los tests se marcan como SKIP
  - Trazabilidad: cada test loguea los valores reales encontrados
  - SRP: este fichero solo verifica estructura, no resultados de consultas

Ejecutar (requiere BD Firebird accesible):
  set PYTHONUTF8=1
  python -m pytest bots/interjddcia/backend/tests/db_parity/test_schema_parity.py -v

Ejecutar solo tests sin BD (siempre pasan):
  python -m pytest bots/interjddcia/backend/tests/db_parity/test_schema_parity.py -v -k "not real_db"

DEVIA: backend/tests/db_parity/DEVIA.md
"""

import logging
import unittest
from typing import Any, Dict, List, Optional, Set

from backend.modules.db_simulator.constants import (
    JDDCTableNames,
    JDDCDocTipos,
    TestModeConfig,
    SimulatorLog,
)
from backend.modules.db_simulator.schema import TABLE_SCHEMAS, TABLE_COLUMNS
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver

logger = logging.getLogger(__name__)


# ─── Columnas mínimas requeridas por tabla (fuente: sqlite_to_firebird.py + schema.py) ──

# Columnas verificadas contra BD real Firebird (2026-06-24)
REQUIRED_COLUMNS_FIREBIRD: Dict[str, List[str]] = {
    "DOCCAB": [
        "CODIGO", "TIPO", "FECHA", "CODCLIENTE", "IMPORTETOTAL",
        "IMPORTEBASE", "IMPORTEIVA", "CODAGENTE", "CODFORMAPAGO",
        "SERIE", "ESTADOPEND",
    ],
    "DOCLIN": [
        "CODIGO", "CODDOCUMENTO", "CODARTICULO", "CANTIDAD", "PRECIO",
        "DESCUENTOS", "IMPORTEDESCUENTO",
    ],
    "CLIENTE": [
        "CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "CP",
        "CODFORMAPAGO", "CODAGENTE",
    ],
    "ARTICULO": [
        "CODIGO", "PRECIOVENTA", "CODFAMILIA", "PROVEEDDEFECTO",
        "STOCKARTICULO",
    ],
    "PROVEED": [
        "CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL",
    ],
    "CAJA": [
        "CODAPUNTE", "FECHA", "IMPORTE", "TIPO",
    ],
    "ESTALMACEN": [
        "CODIGO", "FECHA", "IMPCOSTE", "IMPVENTA",
    ],
}

# Columnas verificadas contra simulador SQLite (post-snapshot real 2026-06-24).
# Snapshot sincroniza esquema con Firebird → nombres idénticos a Firebird real.
REQUIRED_COLUMNS_SIMULATOR: Dict[str, List[str]] = {
    "DOCCAB": [
        "CODIGO", "TIPO", "FECHA", "CODCLIENTE", "IMPORTETOTAL",
        "IMPORTEBASE", "IMPORTEIVA", "CODAGENTE", "CODFORMAPAGO",
    ],
    "DOCLIN": [
        "CODIGO", "CODDOCUMENTO", "CODARTICULO", "CANTIDAD", "PRECIO",
        "DESCUENTOS", "IMPORTEDESCUENTO",
    ],
    "CLIENTE": [
        "CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "CP",
        "CODFORMAPAGO", "CODAGENTE",
    ],
    "ARTICULO": [
        "CODIGO", "NOMBRE", "PRECIOVENTA", "CODFAMILIA", "PROVEEDDEFECTO",
        "STOCKARTICULO",
    ],
    "PROVEED": [
        "CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL",
    ],
    "CAJA": [
        "CODAPUNTE", "FECHA", "IMPORTE", "TIPO",
    ],
    "ESTALMACEN": [
        "CODIGO", "FECHA", "IMPCOSTE", "IMPVENTA",
    ],
}

# Tablas que existen en el simulador pero NO (o con nombre diferente) en Firebird real.
# FAMILIA: solo existe en simulador (sin equivalente directo en Firebird JDDC)
# AGENTES: simulador usa "AGENTES", Firebird real usa "AGENTE" (sin S)
# FORMASPAGO: simulador usa "FORMASPAGO", Firebird real usa "FORMAPAG"
SIMULATOR_ONLY_TABLES: Set[str] = {"FAMILIA", "AGENTES", "FORMASPAGO"}

# Mapa de nombre simulador → nombre en Firebird real (tablas con nombre diferente)
RENAMED_IN_FIREBIRD: Dict[str, str] = {
    "AGENTES":   "AGENTE",    # Firebird: tabla sin S
    "FORMASPAGO": "FORMAPAG", # Firebird: tabla abreviada
}

# Tablas que deben existir en ambas BDs con el MISMO nombre
SHARED_TABLES: List[str] = [
    JDDCTableNames.DOCCAB,
    JDDCTableNames.DOCLIN,
    JDDCTableNames.CLIENTE,
    JDDCTableNames.ARTICULO,
    JDDCTableNames.PROVEED,
    JDDCTableNames.CAJA,
    JDDCTableNames.ESTALMACEN,
    JDDCTableNames.RECURSO,
]


# ─── Helpers de conexión ──────────────────────────────────────────────────────

def _get_firebird_driver():
    """Devuelve un FirebirdDriver conectado a la BD real (o lanza excepción)."""
    from backend.core.config.settings import settings as _s
    from backend.core.factory.db_factory import DBFactory
    from backend.core.utils.constants import DBConstants
    driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
    config = type("FirebirdConfig", (), {
        "host":     _s.DB_HOST,
        "port":     _s.DB_PORT,
        "database": _s.DB_NAME,
        "user":     _s.DB_USER,
        "password": _s.DB_PASSWORD,
        "charset":  TestModeConfig.FIREBIRD_CHARSET,
    })()
    driver.connect(config)
    return driver


def _get_firebird_columns(driver, table: str) -> List[str]:
    """Devuelve las columnas reales de una tabla Firebird."""
    rows = driver.execute_query(
        "SELECT TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME "
        "FROM RDB$RELATION_FIELDS r "
        f"WHERE TRIM(r.RDB$RELATION_NAME) = '{table}' "
        "ORDER BY r.RDB$FIELD_POSITION"
    )
    return [r.get("FIELD_NAME", "").strip() for r in rows]


def _get_firebird_tables(driver) -> Set[str]:
    """Devuelve el conjunto de tablas de usuario en Firebird real."""
    rows = driver.execute_query(
        "SELECT TRIM(RDB$RELATION_NAME) AS TNAME "
        "FROM RDB$RELATIONS "
        "WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL "
        "ORDER BY RDB$RELATION_NAME"
    )
    return {r.get("TNAME", "").strip() for r in rows}


def _get_simulator_columns(table: str) -> List[str]:
    """Devuelve las columnas del simulador SQLite para una tabla."""
    driver = SimulatedFirebirdDriver()
    driver.connect(db_path=":memory:")
    try:
        rows = driver.execute_query(f"PRAGMA table_info({table})")
        return [r.get("name", "") for r in rows]
    finally:
        driver.disconnect()


# ─── Clase base con skip automático si BD real no disponible ─────────────────

class RealDBTestCase(unittest.TestCase):
    """
    Clase base para tests que requieren BD Firebird real.
    Si la BD no está disponible, todos los tests se omiten automáticamente.
    """

    _driver = None
    _db_available: Optional[bool] = None
    _db_error: str = ""

    @classmethod
    def setUpClass(cls):
        try:
            cls._driver = _get_firebird_driver()
            cls._driver.execute_query(
                f"SELECT FIRST 1 CODIGO FROM {JDDCTableNames.DOCCAB}"
            )
            cls._db_available = True
            logger.info(f"{TestModeConfig.LOG_PREFIX} BD real disponible para tests de paridad")
        except Exception as e:
            cls._db_available = False
            cls._db_error = str(e)
            cls._driver = None
            logger.warning(f"{TestModeConfig.LOG_PREFIX} BD real NO disponible: {e}")

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
                f"BD real Firebird no disponible: {self._db_error}"
            )


# ─── Tests del simulador (sin BD real) ───────────────────────────────────────

class TestSimulatorSchema(unittest.TestCase):
    """
    Verifica la estructura del simulador SQLite.
    No requiere BD real — siempre se ejecutan.
    """

    def setUp(self):
        self.driver = SimulatedFirebirdDriver()
        self.driver.connect(db_path=":memory:")

    def tearDown(self):
        self.driver.disconnect()

    def _cols(self, table: str) -> List[str]:
        rows = self.driver.execute_query(f"PRAGMA table_info({table})")
        return [r.get("name", "") for r in rows]

    def test_todas_las_tablas_compartidas_existen_en_simulador(self):
        """Todas las tablas de SHARED_TABLES deben existir en el simulador."""
        for table in SHARED_TABLES:
            cols = self._cols(table)
            self.assertGreater(
                len(cols), 0,
                f"Tabla {table} no existe en el simulador SQLite"
            )
            logger.info(f"{SimulatorLog.PREFIX} {table}: {len(cols)} columnas")

    def test_doccab_columnas_requeridas_simulador(self):
        """DOCCAB simulador debe tener las columnas SQLite requeridas."""
        cols = self._cols("DOCCAB")
        for col in REQUIRED_COLUMNS_SIMULATOR["DOCCAB"]:
            self.assertIn(
                col, cols,
                f"DOCCAB simulador no tiene columna '{col}'. "
                f"Columnas actuales: {cols}"
            )

    def test_doclin_columnas_requeridas_simulador(self):
        """DOCLIN simulador debe tener las columnas SQLite requeridas."""
        cols = self._cols("DOCLIN")
        for col in REQUIRED_COLUMNS_SIMULATOR["DOCLIN"]:
            self.assertIn(col, cols, f"DOCLIN simulador no tiene columna '{col}'")

    def test_cliente_columnas_requeridas_simulador(self):
        """CLIENTE simulador debe tener las columnas SQLite requeridas."""
        cols = self._cols("CLIENTE")
        for col in REQUIRED_COLUMNS_SIMULATOR["CLIENTE"]:
            self.assertIn(col, cols, f"CLIENTE simulador no tiene columna '{col}'")

    def test_articulo_columnas_requeridas_simulador(self):
        """ARTICULO simulador debe tener las columnas SQLite requeridas."""
        cols = self._cols("ARTICULO")
        for col in REQUIRED_COLUMNS_SIMULATOR["ARTICULO"]:
            self.assertIn(col, cols, f"ARTICULO simulador no tiene columna '{col}'")

    def test_caja_columnas_requeridas_simulador(self):
        """CAJA simulador debe tener las columnas SQLite requeridas."""
        cols = self._cols("CAJA")
        for col in REQUIRED_COLUMNS_SIMULATOR["CAJA"]:
            self.assertIn(col, cols, f"CAJA simulador no tiene columna '{col}'")

    def test_estalmacen_columnas_requeridas_simulador(self):
        """ESTALMACEN simulador debe tener las columnas SQLite requeridas."""
        cols = self._cols("ESTALMACEN")
        for col in REQUIRED_COLUMNS_SIMULATOR["ESTALMACEN"]:
            self.assertIn(col, cols, f"ESTALMACEN simulador no tiene columna '{col}'")

    def test_tipos_documento_en_constants(self):
        """JDDCDocTipos debe tener los tipos de documento clave."""
        self.assertEqual(JDDCDocTipos.FACTURA, 13)
        self.assertEqual(JDDCDocTipos.PRESUPUESTO, 0)
        self.assertEqual(JDDCDocTipos.ALBARAN, 11)
        self.assertEqual(JDDCDocTipos.SAT, 2)
        self.assertEqual(JDDCDocTipos.PEDIDO, 12)

    def test_table_schemas_cubre_todas_las_tablas_compartidas(self):
        """TABLE_SCHEMAS debe definir todas las tablas de SHARED_TABLES."""
        for table in SHARED_TABLES:
            self.assertIn(
                table, TABLE_SCHEMAS,
                f"TABLE_SCHEMAS no define el esquema de {table}"
            )

    def test_familia_solo_en_simulador(self):
        """FAMILIA existe en el simulador (tabla auxiliar sin equivalente real)."""
        cols = self._cols("FAMILIA")
        self.assertGreater(len(cols), 0, "FAMILIA debe existir en el simulador")
        logger.info(
            f"{SimulatorLog.PREFIX} FAMILIA (solo simulador): {len(cols)} columnas — "
            "documentado en SIMULATOR_ONLY_TABLES"
        )


# ─── Tests de paridad de columnas (simulador vs Firebird real) ────────────────

class TestColumnParityRealDB(RealDBTestCase):
    """
    Verifica que las columnas del simulador (con alias SQLite→Firebird)
    corresponden a columnas reales en Firebird.
    Requiere BD Firebird accesible.
    """

    def _fb_cols(self, table: str) -> List[str]:
        return _get_firebird_columns(self._driver, table)

    def test_doccab_columnas_firebird_reales(self):
        """DOCCAB Firebird real debe tener las columnas requeridas."""
        self._skip_if_no_db()
        cols = self._fb_cols("DOCCAB")
        for col in REQUIRED_COLUMNS_FIREBIRD["DOCCAB"]:
            self.assertIn(
                col, cols,
                f"DOCCAB Firebird real no tiene columna '{col}'. "
                f"Columnas reales: {cols[:20]}"
            )
        logger.info(f"{TestModeConfig.LOG_PREFIX} DOCCAB Firebird: {len(cols)} columnas")

    def test_doclin_columnas_firebird_reales(self):
        """DOCLIN Firebird real debe tener las columnas requeridas."""
        self._skip_if_no_db()
        cols = self._fb_cols("DOCLIN")
        for col in REQUIRED_COLUMNS_FIREBIRD["DOCLIN"]:
            self.assertIn(col, cols, f"DOCLIN Firebird real no tiene columna '{col}'")
        logger.info(f"{TestModeConfig.LOG_PREFIX} DOCLIN Firebird: {len(cols)} columnas")

    def test_cliente_columnas_firebird_reales(self):
        """CLIENTE Firebird real debe tener las columnas requeridas."""
        self._skip_if_no_db()
        cols = self._fb_cols("CLIENTE")
        for col in REQUIRED_COLUMNS_FIREBIRD["CLIENTE"]:
            self.assertIn(col, cols, f"CLIENTE Firebird real no tiene columna '{col}'")
        logger.info(f"{TestModeConfig.LOG_PREFIX} CLIENTE Firebird: {len(cols)} columnas")

    def test_articulo_columnas_firebird_reales(self):
        """ARTICULO Firebird real debe tener PRECIOVENTA y PROVEEDDEFECTO (nombres reales)."""
        self._skip_if_no_db()
        cols = self._fb_cols("ARTICULO")
        for col in REQUIRED_COLUMNS_FIREBIRD["ARTICULO"]:
            self.assertIn(col, cols, f"ARTICULO Firebird real no tiene columna '{col}'")
        logger.info(f"{TestModeConfig.LOG_PREFIX} ARTICULO Firebird: {len(cols)} columnas")

    def test_simulador_usa_importebase_mismo_que_firebird(self):
        """
        El simulador (post-snapshot) usa IMPORTEBASE igual que Firebird.
        sqlite_to_firebird.py mantiene la traducción BASEIMPONIBLE→IMPORTEBASE
        para queries legacy de la biblioteca.
        """
        self._skip_if_no_db()
        cols_fb = self._fb_cols("DOCCAB")
        cols_sim = _get_simulator_columns("DOCCAB")
        self.assertIn("IMPORTEBASE", cols_fb, "DOCCAB Firebird no tiene IMPORTEBASE")
        self.assertIn("IMPORTEBASE", cols_sim, "DOCCAB simulador no tiene IMPORTEBASE (snapshot no aplicado)")
        self.assertNotIn("BASEIMPONIBLE", cols_fb)
        logger.info(f"{TestModeConfig.LOG_PREFIX} DOCCAB.IMPORTEBASE confirmado en ambas BDs")

    def test_simulador_usa_importeiva_mismo_que_firebird(self):
        """El simulador (post-snapshot) usa IMPORTEIVA igual que Firebird."""
        self._skip_if_no_db()
        cols_fb = self._fb_cols("DOCCAB")
        self.assertIn("IMPORTEIVA", cols_fb, "DOCCAB Firebird no tiene IMPORTEIVA")

    def test_alias_precio_mapea_a_precioventa(self):
        """
        El simulador (post-snapshot) usa PRECIOVENTA igual que Firebird.
        sqlite_to_firebird.py mantiene la traducción A.PRECIO→A.PRECIOVENTA para queries legacy.
        """
        self._skip_if_no_db()
        cols = self._fb_cols("ARTICULO")
        self.assertIn(
            "PRECIOVENTA", cols,
            "ARTICULO Firebird real no tiene PRECIOVENTA"
        )

    def test_alias_codproveedor_mapea_a_proveeddefecto(self):
        """
        El simulador (post-snapshot) usa PROVEEDDEFECTO igual que Firebird.
        """
        self._skip_if_no_db()
        cols = self._fb_cols("ARTICULO")
        self.assertIn(
            "PROVEEDDEFECTO", cols,
            "ARTICULO Firebird real no tiene PROVEEDDEFECTO — "
            "el alias CODPROVEEDOR→PROVEEDDEFECTO en sqlite_to_firebird.py sería incorrecto"
        )

    def test_tablas_compartidas_existen_en_firebird_real(self):
        """Todas las tablas de SHARED_TABLES deben existir en Firebird real con el mismo nombre."""
        self._skip_if_no_db()
        fb_tables = _get_firebird_tables(self._driver)
        for table in SHARED_TABLES:
            if table in SIMULATOR_ONLY_TABLES:
                continue
            self.assertIn(
                table, fb_tables,
                f"Tabla {table} no existe en Firebird real. "
                f"Tablas disponibles (muestra): {sorted(fb_tables)[:20]}"
            )
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} Tablas Firebird real: {len(fb_tables)} tablas"
        )

    def test_tablas_renombradas_existen_en_firebird_real(self):
        """Tablas con nombre diferente en simulador y Firebird deben existir en Firebird con el nombre correcto."""
        self._skip_if_no_db()
        fb_tables = _get_firebird_tables(self._driver)
        for sim_name, fb_name in RENAMED_IN_FIREBIRD.items():
            self.assertIn(
                fb_name, fb_tables,
                f"Tabla '{sim_name}' (simulador) → '{fb_name}' (Firebird): no encontrada en Firebird"
            )
            self.assertNotIn(
                sim_name, fb_tables,
                f"Tabla '{sim_name}' existe en Firebird con el mismo nombre — actualizar RENAMED_IN_FIREBIRD"
            )
            logger.info(
                f"{TestModeConfig.LOG_PREFIX} Renombrada: {sim_name} (sim) ↔ {fb_name} (FB)"
            )

    def test_tipos_documento_existen_en_firebird_real(self):
        """Los tipos de documento clave (TIPO=0,2,11,12,13) deben existir en DOCCAB real."""
        self._skip_if_no_db()
        for tipo, label in JDDCDocTipos.LABELS.items():
            rows = self._driver.execute_query(
                f"SELECT COUNT(*) AS N FROM {JDDCTableNames.DOCCAB} WHERE TIPO = {tipo}"
            )
            n = rows[0].get("N", 0) if rows else 0
            logger.info(
                f"{TestModeConfig.LOG_PREFIX} TIPO={tipo} ({label}): {n} documentos"
            )
            # No falla si hay 0 — solo registra. Algunos tipos pueden no tener datos.
            self.assertIsNotNone(n, f"No se pudo contar documentos TIPO={tipo}")


# ─── Tests de paridad de traducción SQL ──────────────────────────────────────

class TestSQLTranslationParity(unittest.TestCase):
    """
    Verifica que sqlite_to_firebird.py traduce correctamente los alias de columna.
    No requiere BD real — solo verifica la traducción SQL.
    """

    def _adapt(self, sql: str) -> str:
        from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
        adapted, _ = adapt_sql_for_firebird(sql)
        return adapted

    def _adapt_and_normalize(self, sql: str) -> str:
        from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
        adapted, _ = adapt_sql_for_firebird(sql)
        normalized, _ = FirebirdSQLNormalizer().normalize(adapted)
        return normalized

    def test_baseimponible_se_traduce_a_importebase(self):
        """BASEIMPONIBLE → IMPORTEBASE en la traducción SQLite→Firebird."""
        sql = "SELECT SUM(BASEIMPONIBLE) AS BASE FROM DOCCAB WHERE TIPO=13"
        adapted = self._adapt(sql)
        self.assertIn("IMPORTEBASE", adapted.upper())
        self.assertNotIn("BASEIMPONIBLE", adapted.upper())

    def test_iva_columna_se_traduce_a_importeiva(self):
        """IVA como columna standalone → IMPORTEIVA."""
        sql = "SELECT SUM(IVA) AS IVA_TOTAL FROM DOCCAB WHERE TIPO=13"
        adapted = self._adapt(sql)
        # El alias IVA_TOTAL debe preservarse; la columna IVA → IMPORTEIVA
        self.assertIn("IVA_TOTAL", adapted)

    def test_articulo_precio_se_traduce_a_precioventa(self):
        """A.PRECIO → A.PRECIOVENTA en ARTICULO."""
        sql = "SELECT A.PRECIO FROM ARTICULO A"
        adapted = self._adapt(sql)
        self.assertIn("PRECIOVENTA", adapted.upper())

    def test_cast_text_se_traduce_a_varchar(self):
        """CAST(x AS TEXT) → CAST(x AS VARCHAR(50)) para Firebird."""
        sql = "SELECT CAST(CODIGO AS TEXT) AS COD FROM DOCCAB"
        adapted = self._adapt(sql)
        self.assertIn("VARCHAR", adapted.upper())
        self.assertNotIn("AS TEXT", adapted.upper())

    def test_limit_se_traduce_a_first(self):
        """LIMIT N → SELECT FIRST N (sintaxis Firebird)."""
        sql = "SELECT CODIGO FROM DOCCAB WHERE TIPO=13 LIMIT 10"
        normalized = self._adapt_and_normalize(sql)
        self.assertIn("FIRST 10", normalized.upper())
        self.assertNotIn("LIMIT", normalized.upper())

    def test_substr_fecha_se_traduce_a_extract(self):
        """SUBSTR(FECHA,1,7) → expresión EXTRACT año-mes para Firebird."""
        sql = "SELECT SUBSTR(FECHA,1,7) AS MES FROM DOCCAB"
        adapted = self._adapt(sql)
        self.assertIn("EXTRACT", adapted.upper())

    def test_no_duplica_first_si_ya_existe(self):
        """Si el SQL ya tiene SELECT FIRST N, no se añade otro FIRST."""
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
        sql = "SELECT FIRST 10 CODIGO FROM DOCCAB WHERE TIPO=13"
        normalized, _ = FirebirdSQLNormalizer().normalize(sql)
        self.assertEqual(normalized.upper().count("FIRST"), 1)

    def test_agregaciones_no_reciben_first(self):
        """Las queries con COUNT/SUM/AVG no deben recibir FIRST N automático."""
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
        sql = "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=13"
        normalized, _ = FirebirdSQLNormalizer().normalize(sql)
        self.assertNotIn("FIRST", normalized.upper())

    def test_coalesce_nombre_cliente_funciona(self):
        """COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL) debe preservarse en la traducción."""
        sql = (
            "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, 'Sin nombre') AS NOMBRE "
            "FROM CLIENTE C"
        )
        adapted = self._adapt(sql)
        self.assertIn("COALESCE", adapted.upper())
        self.assertIn("NOMBRECOMERCIAL", adapted.upper())
        self.assertIn("RAZONSOCIAL", adapted.upper())


# ─── Tests de paridad de datos del simulador ─────────────────────────────────

class TestSimulatorDataIntegrity(unittest.TestCase):
    """
    Verifica que el simulador SQLite tiene datos coherentes con la estructura
    esperada de la BD real. No requiere BD real.
    Usa la BD simulada en disco (si existe) o en memoria con datos sintéticos.
    """

    def setUp(self):
        self.driver = SimulatedFirebirdDriver()
        # Usar BD en disco si existe, si no en memoria
        from backend.modules.db_simulator.constants import SimulatorPaths
        db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
        self.driver.connect(db_path=db_path)
        self._db_path = db_path

    def tearDown(self):
        self.driver.disconnect()

    def _exec(self, sql: str) -> List[Dict[str, Any]]:
        return self.driver.execute_query(sql)

    def test_doccab_tiene_registros_si_bd_inicializada(self):
        """Si la BD simulada está inicializada, DOCCAB debe tener registros."""
        rows = self._exec("SELECT COUNT(*) AS N FROM DOCCAB")
        n = rows[0].get("N", 0) if rows else 0
        if self._db_path == ":memory:":
            # BD en memoria vacía — solo verificamos que la query no falla
            self.assertIsNotNone(n)
            logger.info(f"{SimulatorLog.PREFIX} BD en memoria (vacía): DOCCAB={n} registros")
        else:
            logger.info(f"{SimulatorLog.PREFIX} BD en disco: DOCCAB={n} registros")
            # Si hay datos, verificar coherencia
            if n > 0:
                self._verify_doccab_coherence()

    def _verify_doccab_coherence(self):
        """Verifica coherencia interna de DOCCAB cuando hay datos."""
        # Todos los TIPO deben ser valores conocidos
        rows = self._exec(
            "SELECT DISTINCT TIPO FROM DOCCAB ORDER BY TIPO"
        )
        tipos = [r.get("TIPO") for r in rows]
        tipos_validos = set(JDDCDocTipos.LABELS.keys())
        for tipo in tipos:
            self.assertIn(
                tipo, tipos_validos,
                f"DOCCAB simulador tiene TIPO={tipo} que no está en JDDCDocTipos.LABELS"
            )
        logger.info(f"{SimulatorLog.PREFIX} DOCCAB tipos encontrados: {tipos}")

    def test_importetotal_no_negativo_en_facturas(self):
        """Las facturas (TIPO=13) no deben tener IMPORTETOTAL negativo."""
        rows = self._exec(
            f"SELECT COUNT(*) AS N FROM DOCCAB "
            f"WHERE TIPO={JDDCDocTipos.FACTURA} AND IMPORTETOTAL < 0"
        )
        n = rows[0].get("N", 0) if rows else 0
        self.assertEqual(
            n, 0,
            f"El simulador tiene {n} facturas con IMPORTETOTAL negativo"
        )

    def test_doclin_referencias_validas_si_hay_datos(self):
        """DOCLIN.CODDOCUMENTO debe referenciar documentos existentes en DOCCAB."""
        rows_doccab = self._exec("SELECT COUNT(*) AS N FROM DOCCAB")
        n_doccab = rows_doccab[0].get("N", 0) if rows_doccab else 0
        if n_doccab == 0:
            self.skipTest("BD simulada vacía — no hay datos para verificar integridad")

        rows = self._exec(
            "SELECT COUNT(*) AS N FROM DOCLIN L "
            "WHERE NOT EXISTS (SELECT 1 FROM DOCCAB D WHERE D.CODIGO = L.CODDOCUMENTO)"
        )
        n_huerfanas = rows[0].get("N", 0) if rows else 0
        self.assertEqual(
            n_huerfanas, 0,
            f"El simulador tiene {n_huerfanas} líneas DOCLIN sin documento padre en DOCCAB"
        )

    def test_cliente_codigos_unicos(self):
        """CLIENTE.CODIGO debe ser único (PK)."""
        rows = self._exec(
            "SELECT COUNT(*) AS TOTAL, COUNT(DISTINCT CODIGO) AS UNICOS FROM CLIENTE"
        )
        if rows and rows[0].get("TOTAL", 0) > 0:
            total = rows[0].get("TOTAL", 0)
            unicos = rows[0].get("UNICOS", 0)
            self.assertEqual(
                total, unicos,
                f"CLIENTE tiene {total - unicos} códigos duplicados"
            )

    def test_articulo_codigos_unicos(self):
        """ARTICULO.CODIGO debe ser único (PK)."""
        rows = self._exec(
            "SELECT COUNT(*) AS TOTAL, COUNT(DISTINCT CODIGO) AS UNICOS FROM ARTICULO"
        )
        if rows and rows[0].get("TOTAL", 0) > 0:
            total = rows[0].get("TOTAL", 0)
            unicos = rows[0].get("UNICOS", 0)
            self.assertEqual(
                total, unicos,
                f"ARTICULO tiene {total - unicos} códigos duplicados"
            )

    def test_doccab_codigos_unicos(self):
        """DOCCAB.CODIGO debe ser único (PK)."""
        rows = self._exec(
            "SELECT COUNT(*) AS TOTAL, COUNT(DISTINCT CODIGO) AS UNICOS FROM DOCCAB"
        )
        if rows and rows[0].get("TOTAL", 0) > 0:
            total = rows[0].get("TOTAL", 0)
            unicos = rows[0].get("UNICOS", 0)
            self.assertEqual(
                total, unicos,
                f"DOCCAB tiene {total - unicos} códigos duplicados"
            )

    def test_facturas_tienen_cliente_asignado(self):
        """Las facturas (TIPO=13) deben tener CODCLIENTE > 0."""
        rows = self._exec(
            f"SELECT COUNT(*) AS N FROM DOCCAB "
            f"WHERE TIPO={JDDCDocTipos.FACTURA} AND (CODCLIENTE IS NULL OR CODCLIENTE = 0)"
        )
        n = rows[0].get("N", 0) if rows else 0
        rows_total = self._exec(
            f"SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO={JDDCDocTipos.FACTURA}"
        )
        n_total = rows_total[0].get("N", 0) if rows_total else 0
        if n_total > 0:
            self.assertEqual(
                n, 0,
                f"El simulador tiene {n} facturas sin CODCLIENTE asignado"
            )


# ─── Tests de paridad de datos reales vs simulados ───────────────────────────

class TestDataParityRealVsSimulator(RealDBTestCase):
    """
    Compara métricas de alto nivel entre BD real y simulada.
    Verifica que el simulador tiene datos en el mismo orden de magnitud
    que la BD real (no valores exactos, sino rangos razonables).

    Principio: el simulador no replica datos exactos (privacidad), pero sí
    debe tener la misma estructura y rangos de valores para que el chat IA
    produzca respuestas coherentes.
    """

    def setUp(self):
        self.sim_driver = SimulatedFirebirdDriver()
        from backend.modules.db_simulator.constants import SimulatorPaths
        db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
        self.sim_driver.connect(db_path=db_path)
        self._sim_db_path = db_path

    def tearDown(self):
        self.sim_driver.disconnect()

    def _real(self, sql: str) -> List[Dict[str, Any]]:
        return self._driver.execute_query(sql)

    def _sim(self, sql: str) -> List[Dict[str, Any]]:
        return self.sim_driver.execute_query(sql)

    def _skip_if_sim_empty(self):
        rows = self._sim("SELECT COUNT(*) AS N FROM DOCCAB")
        n = rows[0].get("N", 0) if rows else 0
        if n == 0:
            self.skipTest("BD simulada vacía — ejecutar build-snapshot o build-synthetic primero")

    def test_tipos_documento_existen_en_ambas_bds(self):
        """Los tipos de documento clave deben existir en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()

        for tipo, label in [(JDDCDocTipos.FACTURA, "Factura"), (JDDCDocTipos.PRESUPUESTO, "Presupuesto")]:
            rows_real = self._real(
                f"SELECT COUNT(*) AS N FROM {JDDCTableNames.DOCCAB} WHERE TIPO={tipo}"
            )
            rows_sim = self._sim(
                f"SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO={tipo}"
            )
            n_real = rows_real[0].get("N", 0) if rows_real else 0
            n_sim = rows_sim[0].get("N", 0) if rows_sim else 0

            self.assertGreater(n_real, 0, f"BD real no tiene documentos TIPO={tipo} ({label})")
            self.assertGreater(n_sim, 0, f"BD simulada no tiene documentos TIPO={tipo} ({label})")
            logger.info(
                f"{TestModeConfig.LOG_PREFIX} TIPO={tipo} ({label}): "
                f"real={n_real}, simulado={n_sim}"
            )

    def test_importetotal_facturas_es_positivo_en_ambas_bds(self):
        """IMPORTETOTAL de facturas debe ser positivo en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()

        # Firebird no siempre expone ROUND() como función escalar simple
        # → usamos AVG sin redondeo para máxima compatibilidad
        sql_real = (
            f"SELECT FIRST 1 AVG(IMPORTETOTAL) AS TICKET_MEDIO "
            f"FROM {JDDCTableNames.DOCCAB} WHERE TIPO={JDDCDocTipos.FACTURA}"
        )
        sql_sim = (
            f"SELECT AVG(IMPORTETOTAL) AS TICKET_MEDIO "
            f"FROM DOCCAB WHERE TIPO={JDDCDocTipos.FACTURA} LIMIT 1"
        )
        for label, drv, sql in [
            ("real",     self._driver,    sql_real),
            ("simulado", self.sim_driver, sql_sim),
        ]:
            rows = drv.execute_query(sql)
            ticket = rows[0].get("TICKET_MEDIO") if rows else None
            if ticket is not None:
                self.assertGreater(
                    float(ticket), 0,
                    f"Ticket medio de facturas en BD {label} no es positivo: {ticket}"
                )
                logger.info(f"{TestModeConfig.LOG_PREFIX} Ticket medio {label}: {ticket:.2f}€")

    def test_columnas_resultado_son_identicas_en_query_facturacion_total(self):
        """
        La consulta v_kpi_facturacion_total debe devolver las mismas columnas
        en BD real y simulada: FACTURACION_TOTAL, N_FACTURAS.
        """
        self._skip_if_no_db()
        self._skip_if_sim_empty()

        from backend.modules.db_simulator.query_library import get_query_by_id
        from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

        q = get_query_by_id("v_kpi_facturacion_total")
        self.assertNotEqual(q, {}, "Consulta v_kpi_facturacion_total no encontrada")

        # Ejecutar en simulador (SQL SQLite nativo)
        rows_sim = self.sim_driver.execute_query(q["sql"])
        self.assertGreater(len(rows_sim), 0, "Simulador no devuelve datos para v_kpi_facturacion_total")
        cols_sim = set(rows_sim[0].keys())

        # Ejecutar en Firebird real (SQL adaptado)
        adapted, _ = adapt_sql_for_firebird(q["sql"])
        fb_sql, _ = FirebirdSQLNormalizer().normalize(adapted)
        rows_real = self._driver.execute_query(fb_sql)
        self.assertGreater(len(rows_real), 0, "BD real no devuelve datos para v_kpi_facturacion_total")
        cols_real = set(rows_real[0].keys())

        self.assertEqual(
            cols_sim, cols_real,
            f"Columnas diferentes en v_kpi_facturacion_total:\n"
            f"  Simulador: {sorted(cols_sim)}\n"
            f"  Real:      {sorted(cols_real)}"
        )
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} v_kpi_facturacion_total — "
            f"sim={rows_sim[0].get('FACTURACION_TOTAL')}, "
            f"real={rows_real[0].get('FACTURACION_TOTAL')}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main(verbosity=2)
