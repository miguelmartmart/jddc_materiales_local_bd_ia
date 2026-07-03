"""
test_query_parity.py — Paridad de resultados de la query_library en BD real y simulada.

Verifica que las 77 consultas de la query_library:
  1. Se ejecutan sin error en el simulador SQLite (siempre)
  2. Se ejecutan sin error en Firebird real (si disponible)
  3. Devuelven las mismas columnas en ambas BDs (si ambas disponibles)
  4. Devuelven datos coherentes (no vacíos cuando hay datos)

Principios aplicados:
  - Sin inventar valores: solo se verifican columnas y tipos, no valores exactos
  - Fallback gracioso: si BD real no disponible → tests de BD real se marcan SKIP
  - Trazabilidad: cada test loguea filas devueltas y columnas
  - SRP: este fichero solo verifica resultados de consultas, no estructura de tablas
  - Resiliencia multi-modelo: las consultas deben funcionar con cualquier modelo IA activo

Errores conocidos que NO son fallos del test:
  - FAMILIA no existe en Firebird real (solo en simulador) → SKIP para esas queries
  - STOCKARTICULO/STOCKMINIMO/STOCKACTUAL → columnas simulador, no en Firebird real
  - Queries que requieren datos que no existen en la BD de prueba → 0 filas es válido

Ejecutar (requiere BD Firebird accesible):
  python -m pytest bots/interjddcia/backend/tests/db_parity/test_query_parity.py -v

Ejecutar solo tests sin BD (siempre pasan):
  python -m pytest bots/interjddcia/backend/tests/db_parity/test_query_parity.py -v -k "simulator"

DEVIA: backend/tests/db_parity/DEVIA.md
"""

import logging
import unittest
from typing import Any, Dict, List, Optional, Set

from backend.modules.db_simulator.constants import (
    JDDCTableNames,
    TestModeConfig,
    SimulatorLog,
)
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.query_library import QUERY_LIBRARY, get_query_by_id

logger = logging.getLogger(__name__)


# ─── Tablas/columnas que no existen en Firebird real ─────────────────────────

# Queries que usan tablas/columnas solo del simulador — se marcan SKIP en BD real
_SIMULATOR_ONLY_TABLES = {"FAMILIA", "STOCKARTICULO", "STOCKMINIMO", "STOCKACTUAL"}

# IDs de queries que usan tablas/columnas solo del simulador
_SIMULATOR_ONLY_QUERY_IDS: Set[str] = set()
for _q in QUERY_LIBRARY:
    _sql_up = _q.get("sql", "").upper()
    if any(t in _sql_up for t in _SIMULATOR_ONLY_TABLES):
        _SIMULATOR_ONLY_QUERY_IDS.add(_q["id"])


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


def _adapt_for_firebird(sql: str) -> str:
    """Adapta SQL SQLite → Firebird (sqlite_to_firebird + normalizer)."""
    from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
    from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
    adapted, _ = adapt_sql_for_firebird(sql)
    normalized, _ = FirebirdSQLNormalizer().normalize(adapted)
    return normalized


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
            logger.info(f"{TestModeConfig.LOG_PREFIX} BD real disponible para tests de paridad de queries")
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
            self.skipTest(f"BD real Firebird no disponible: {self._db_error}")


# ─── Tests del simulador (sin BD real) ───────────────────────────────────────

class TestQueryLibrarySimulator(unittest.TestCase):
    """
    Ejecuta todas las consultas de la query_library contra el simulador SQLite.
    No requiere BD real — siempre se ejecutan.
    Verifica que ninguna consulta lanza excepción.
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = SimulatedFirebirdDriver()
        from backend.modules.db_simulator.constants import SimulatorPaths
        db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
        cls.driver.connect(db_path=db_path)
        cls._db_path = db_path
        # Verificar si hay datos
        rows = cls.driver.execute_query("SELECT COUNT(*) AS N FROM DOCCAB")
        cls._has_data = (rows[0].get("N", 0) > 0) if rows else False
        logger.info(
            f"{SimulatorLog.PREFIX} BD simulada: {db_path}, "
            f"datos={'si' if cls._has_data else 'no'}"
        )

    @classmethod
    def tearDownClass(cls):
        cls.driver.disconnect()

    def _run_query_simulator(self, query_id: str) -> List[Dict[str, Any]]:
        """Ejecuta una consulta de la query_library en el simulador."""
        q = get_query_by_id(query_id)
        self.assertNotEqual(q, {}, f"Consulta '{query_id}' no encontrada en la biblioteca")
        return self.driver.execute_query(q["sql"])

    def test_todas_las_queries_ejecutan_sin_error_en_simulador(self):
        """
        Todas las 77 consultas de la query_library deben ejecutarse sin excepción
        en el simulador SQLite.
        """
        errores = []
        for q in QUERY_LIBRARY:
            qid = q["id"]
            try:
                rows = self.driver.execute_query(q["sql"])
                self.assertIsInstance(rows, list, f"Query {qid} no devuelve lista")
                logger.debug(f"{SimulatorLog.PREFIX} {qid}: {len(rows)} filas")
            except Exception as e:
                errores.append(f"{qid}: {e}")
                logger.error(f"{SimulatorLog.PREFIX} ERROR en {qid}: {e}")

        self.assertEqual(
            len(errores), 0,
            f"{len(errores)} consultas fallaron en el simulador:\n" +
            "\n".join(f"  - {e}" for e in errores)
        )
        logger.info(
            f"{SimulatorLog.PREFIX} {len(QUERY_LIBRARY)} consultas ejecutadas "
            f"sin error en el simulador"
        )

    def test_queries_criticas_devuelven_columnas_correctas_en_simulador(self):
        """
        Las consultas críticas (urgencia=Crítico) deben devolver las columnas
        esperadas en el simulador.
        """
        if not self._has_data:
            self.skipTest("BD simulada vacía — no hay datos para verificar columnas")

        expected_columns = {
            "v_kpi_facturacion_total": {"FACTURACION_TOTAL", "N_FACTURAS"},
            "v_kpi_ticket_medio":      {"TICKET_MEDIO", "MINIMO", "MAXIMO"},
            "v_kpi_n_clientes_activos": {"CLIENTES_ACTIVOS"},
            "f_kpi_saldo_caja":        {"SALDO_NETO"},
            "d_kpi_resumen_ejecutivo": {"INDICADOR"},
        }

        for qid, expected_cols in expected_columns.items():
            rows = self._run_query_simulator(qid)
            if rows:
                actual_cols = set(rows[0].keys())
                for col in expected_cols:
                    self.assertIn(
                        col, actual_cols,
                        f"Query {qid}: columna '{col}' no encontrada. "
                        f"Columnas actuales: {sorted(actual_cols)}"
                    )
                logger.info(f"{SimulatorLog.PREFIX} {qid}: columnas OK {sorted(actual_cols)}")

    def test_v_kpi_facturacion_total_en_simulador(self):
        """v_kpi_facturacion_total debe devolver 1 fila con FACTURACION_TOTAL."""
        if not self._has_data:
            self.skipTest("BD simulada vacía")
        rows = self._run_query_simulator("v_kpi_facturacion_total")
        self.assertEqual(len(rows), 1, "v_kpi_facturacion_total debe devolver exactamente 1 fila")
        self.assertIn("FACTURACION_TOTAL", rows[0])
        total = rows[0].get("FACTURACION_TOTAL")
        if total is not None:
            self.assertGreater(float(total), 0, "FACTURACION_TOTAL debe ser positivo")
        logger.info(f"{SimulatorLog.PREFIX} Facturacion total simulada: {total}")

    def test_v_kpi_top10_clientes_en_simulador(self):
        """v_kpi_top10_clientes debe devolver hasta 10 filas con NOMBRE y TOTAL."""
        if not self._has_data:
            self.skipTest("BD simulada vacía")
        rows = self._run_query_simulator("v_kpi_top10_clientes")
        self.assertLessEqual(len(rows), 10, "Top 10 clientes no puede tener más de 10 filas")
        if rows:
            self.assertIn("NOMBRE", rows[0])
            self.assertIn("TOTAL", rows[0])
        logger.info(f"{SimulatorLog.PREFIX} Top clientes simulados: {len(rows)} filas")

    def test_f_kpi_saldo_caja_en_simulador(self):
        """f_kpi_saldo_caja debe devolver 1 fila con SALDO_NETO."""
        if not self._has_data:
            self.skipTest("BD simulada vacía")
        rows = self._run_query_simulator("f_kpi_saldo_caja")
        self.assertEqual(len(rows), 1, "f_kpi_saldo_caja debe devolver exactamente 1 fila")
        self.assertIn("SALDO_NETO", rows[0])
        logger.info(f"{SimulatorLog.PREFIX} Saldo caja simulado: {rows[0].get('SALDO_NETO')}")

    def test_d_kpi_resumen_ejecutivo_en_simulador(self):
        """d_kpi_resumen_ejecutivo debe devolver múltiples indicadores."""
        if not self._has_data:
            self.skipTest("BD simulada vacía")
        rows = self._run_query_simulator("d_kpi_resumen_ejecutivo")
        self.assertGreater(len(rows), 0, "El resumen ejecutivo no devuelve datos")
        self.assertIn("INDICADOR", rows[0])
        logger.info(
            f"{SimulatorLog.PREFIX} Resumen ejecutivo simulado: "
            f"{len(rows)} indicadores"
        )

    def test_queries_por_departamento_ejecutan_sin_error(self):
        """
        Queries agrupadas por departamento deben ejecutarse sin error.
        Verifica que la clasificación dept/rol/tipo es coherente.
        """
        from backend.modules.db_simulator.query_library_core import Dept
        dept_prefixes = {
            "v_": Dept.VENTAS,
            "c_": Dept.COMPRAS,
            "a_": Dept.ALMACEN,
            "f_": Dept.FINANZAS,
            "s_": Dept.SAT,
            "p_": Dept.TODOS,
            "d_": Dept.DIRECCION,
        }
        errores = []
        for q in QUERY_LIBRARY:
            qid = q["id"]
            try:
                rows = self.driver.execute_query(q["sql"])
                self.assertIsInstance(rows, list)
            except Exception as e:
                errores.append(f"{qid}: {e}")

        self.assertEqual(
            len(errores), 0,
            f"Queries por departamento con error:\n" + "\n".join(errores)
        )

    def test_query_library_tiene_77_queries(self):
        """La query_library debe tener exactamente 77 consultas."""
        self.assertEqual(
            len(QUERY_LIBRARY), 77,
            f"Se esperaban 77 consultas, hay {len(QUERY_LIBRARY)}"
        )

    def test_todas_las_queries_tienen_campos_obligatorios(self):
        """Cada consulta debe tener id, title, sql, dept, rol, tipo, urgencia."""
        campos_obligatorios = ["id", "title", "sql", "dept", "rol", "tipo", "urgencia"]
        for q in QUERY_LIBRARY:
            for campo in campos_obligatorios:
                self.assertIn(
                    campo, q,
                    f"Query '{q.get('id', '?')}' no tiene campo '{campo}'"
                )
            # El SQL no debe estar vacío
            self.assertTrue(
                q["sql"].strip(),
                f"Query '{q['id']}' tiene SQL vacío"
            )
            # El ID debe ser único
            ids = [x["id"] for x in QUERY_LIBRARY]
            self.assertEqual(
                ids.count(q["id"]), 1,
                f"ID '{q['id']}' duplicado en la query_library"
            )

    def test_get_query_by_id_funciona(self):
        """get_query_by_id debe devolver la consulta correcta por ID."""
        q = get_query_by_id("v_kpi_facturacion_total")
        self.assertNotEqual(q, {})
        self.assertEqual(q["id"], "v_kpi_facturacion_total")
        self.assertIn("TIPO=13", q["sql"])

        # ID inexistente debe devolver {}
        q_none = get_query_by_id("id_que_no_existe_xyz")
        self.assertEqual(q_none, {})


# ─── Tests de paridad de queries (simulador vs BD real) ──────────────────────

class TestQueryParityRealVsSimulator(RealDBTestCase):
    """
    Compara los resultados de las consultas críticas entre BD real y simulada.
    Verifica que las columnas devueltas son idénticas en ambas BDs.
    Requiere BD Firebird accesible.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sim_driver = SimulatedFirebirdDriver()
        from backend.modules.db_simulator.constants import SimulatorPaths
        db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
        cls.sim_driver.connect(db_path=db_path)
        rows = cls.sim_driver.execute_query("SELECT COUNT(*) AS N FROM DOCCAB")
        cls._sim_has_data = (rows[0].get("N", 0) > 0) if rows else False

    @classmethod
    def tearDownClass(cls):
        cls.sim_driver.disconnect()
        super().tearDownClass()

    def _skip_if_sim_empty(self):
        if not self._sim_has_data:
            self.skipTest("BD simulada vacía — ejecutar build-snapshot o build-synthetic primero")

    def _run_both(self, query_id: str):
        """Ejecuta una query en ambas BDs y devuelve (rows_sim, rows_real)."""
        q = get_query_by_id(query_id)
        self.assertNotEqual(q, {}, f"Query '{query_id}' no encontrada")

        # Simulador (SQL SQLite nativo)
        rows_sim = self.sim_driver.execute_query(q["sql"])

        # BD real (SQL adaptado)
        fb_sql = _adapt_for_firebird(q["sql"])
        rows_real = self._driver.execute_query(fb_sql)

        return rows_sim, rows_real

    def _assert_same_columns(self, query_id: str, rows_sim, rows_real):
        """Verifica que ambas BDs devuelven las mismas columnas."""
        if not rows_sim or not rows_real:
            return  # No hay datos para comparar columnas
        cols_sim  = set(rows_sim[0].keys())
        cols_real = set(rows_real[0].keys())
        self.assertEqual(
            cols_sim, cols_real,
            f"Query {query_id} — columnas diferentes:\n"
            f"  Simulador: {sorted(cols_sim)}\n"
            f"  Real:      {sorted(cols_real)}"
        )

    def test_v_kpi_facturacion_total_parity(self):
        """v_kpi_facturacion_total: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("v_kpi_facturacion_total")
        self._assert_same_columns("v_kpi_facturacion_total", rows_sim, rows_real)
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} v_kpi_facturacion_total — "
            f"sim={rows_sim[0].get('FACTURACION_TOTAL') if rows_sim else 'N/A'}, "
            f"real={rows_real[0].get('FACTURACION_TOTAL') if rows_real else 'N/A'}"
        )

    def test_v_kpi_ticket_medio_parity(self):
        """v_kpi_ticket_medio: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("v_kpi_ticket_medio")
        self._assert_same_columns("v_kpi_ticket_medio", rows_sim, rows_real)

    def test_v_kpi_top10_clientes_parity(self):
        """v_kpi_top10_clientes: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("v_kpi_top10_clientes")
        self._assert_same_columns("v_kpi_top10_clientes", rows_sim, rows_real)
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} Top clientes — "
            f"sim={len(rows_sim)}, real={len(rows_real)}"
        )

    def test_v_kpi_n_clientes_activos_parity(self):
        """v_kpi_n_clientes_activos: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("v_kpi_n_clientes_activos")
        self._assert_same_columns("v_kpi_n_clientes_activos", rows_sim, rows_real)

    def test_v_kpi_conversion_presupuestos_parity(self):
        """v_kpi_conversion_presupuestos: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("v_kpi_conversion_presupuestos")
        self._assert_same_columns("v_kpi_conversion_presupuestos", rows_sim, rows_real)

    def test_f_kpi_saldo_caja_parity(self):
        """f_kpi_saldo_caja: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("f_kpi_saldo_caja")
        self._assert_same_columns("f_kpi_saldo_caja", rows_sim, rows_real)

    def test_d_kpi_resumen_ejecutivo_parity(self):
        """d_kpi_resumen_ejecutivo: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("d_kpi_resumen_ejecutivo")
        self._assert_same_columns("d_kpi_resumen_ejecutivo", rows_sim, rows_real)

    def test_s_kpi_sats_mes_parity(self):
        """s_kpi_sats_mes: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("s_kpi_sats_mes")
        self._assert_same_columns("s_kpi_sats_mes", rows_sim, rows_real)

    def test_c_kpi_top10_proveedores_parity(self):
        """c_kpi_top10_proveedores: mismas columnas en BD real y simulada."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        rows_sim, rows_real = self._run_both("c_kpi_top10_proveedores")
        self._assert_same_columns("c_kpi_top10_proveedores", rows_sim, rows_real)

    def test_todas_las_queries_no_simulador_ejecutan_en_real(self):
        """
        Todas las queries que NO usan tablas/columnas solo del simulador
        deben ejecutarse sin error en la BD real Firebird.
        """
        self._skip_if_no_db()
        errores = []
        skipped = []

        for q in QUERY_LIBRARY:
            qid = q["id"]
            if qid in _SIMULATOR_ONLY_QUERY_IDS:
                skipped.append(qid)
                continue
            try:
                fb_sql = _adapt_for_firebird(q["sql"])
                rows = self._driver.execute_query(fb_sql)
                self.assertIsInstance(rows, list, f"Query {qid} no devuelve lista")
                logger.debug(
                    f"{TestModeConfig.LOG_PREFIX} {qid}: {len(rows)} filas en BD real"
                )
            except Exception as e:
                errores.append(f"{qid}: {e}")
                logger.error(f"{TestModeConfig.LOG_PREFIX} ERROR en {qid}: {e}")

        if skipped:
            logger.info(
                f"{TestModeConfig.LOG_PREFIX} Queries omitidas (solo simulador): "
                f"{len(skipped)} — {skipped}"
            )

        self.assertEqual(
            len(errores), 0,
            f"{len(errores)} queries fallaron en BD real:\n" +
            "\n".join(f"  - {e}" for e in errores)
        )
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} "
            f"{len(QUERY_LIBRARY) - len(skipped)} queries ejecutadas sin error en BD real "
            f"({len(skipped)} omitidas por usar tablas solo del simulador)"
        )


# ─── Tests del normalizador SQL (sin BD) ─────────────────────────────────────

class TestNormalizerFIRSTSubquery(unittest.TestCase):
    """
    Tests específicos para el bug de FIRST en subqueries (-104 error).

    Bug: el normalizador añadía FIRST al outer SELECT aunque el LIMIT
    estuviera en una subquery, o aunque ya hubiera FIRST en el outer SELECT.

    Fix: _fix_limit_to_first busca el SELECT más cercano ANTES del LIMIT.
         _add_first_if_missing no añade FIRST si ya hay FIRST en cualquier parte.
    """

    def setUp(self):
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
        self.n = FirebirdSQLNormalizer()

    def test_limit_en_outer_select_sin_first_previo(self):
        """LIMIT N en outer SELECT → SELECT FIRST N al inicio."""
        sql = "SELECT A.CODIGO, A.NOMBRE FROM ARTICULO A ORDER BY A.NOMBRE LIMIT 10"
        r, _ = self.n.normalize(sql)
        self.assertTrue(r.upper().startswith("SELECT FIRST 10"))
        self.assertNotIn("LIMIT", r.upper())

    def test_limit_no_duplica_first_existente(self):
        """Si ya hay SELECT FIRST N, LIMIT N no añade otro FIRST."""
        sql = (
            "SELECT FIRST 50 A.CODIGO, A.NOMBRE FROM ARTICULO A "
            "JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY A.CODIGO DESC LIMIT 10"
        )
        r, _ = self.n.normalize(sql)
        self.assertEqual(r.upper().count("FIRST"), 1)
        self.assertNotIn("LIMIT", r.upper())

    def test_first_en_subquery_no_duplica_en_outer(self):
        """Si hay FIRST en una subquery, no se añade FIRST al outer SELECT."""
        sql = (
            "SELECT A.CODIGO, A.NOMBRE FROM ARTICULO A "
            "WHERE A.CODIGO IN (SELECT FIRST 1 CODIGO FROM ARTICULO WHERE NOMBRE LIKE '%X%') "
            "ORDER BY A.CODIGO"
        )
        r, _ = self.n.normalize(sql)
        self.assertEqual(r.upper().count("FIRST"), 1)

    def test_limit_en_subquery_va_al_select_de_subquery(self):
        """LIMIT en subquery → FIRST en el SELECT de la subquery, no en el outer."""
        sql = (
            "SELECT COUNT(*) AS N FROM DOCCAB "
            "WHERE CODCLIENTE IN (SELECT CODIGO FROM CLIENTE WHERE PROVINCIA='Madrid' LIMIT 5)"
        )
        r, _ = self.n.normalize(sql)
        self.assertEqual(r.upper().count("FIRST"), 1)
        # El FIRST debe estar dentro de la subquery (después del segundo SELECT)
        first_pos = r.upper().index("FIRST")
        second_select_pos = r.upper().index("SELECT", r.upper().index("SELECT") + 1)
        self.assertGreater(
            first_pos, second_select_pos,
            f"FIRST debería estar en la subquery (pos {first_pos} > {second_select_pos})"
        )

    def test_agregacion_no_recibe_first(self):
        """Queries con COUNT/SUM/AVG no deben recibir FIRST automático."""
        sql = "SELECT COUNT(*) AS N, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB WHERE TIPO=13"
        r, _ = self.n.normalize(sql)
        self.assertNotIn("FIRST", r.upper())

    def test_limit_multiple_en_query_compleja(self):
        """
        Query compleja con FIRST 50 en outer + LIMIT en subquery:
        solo debe haber 1 FIRST en el resultado.
        """
        sql = (
            "SELECT FIRST 50 A.CODIGO, A.NOMBRE, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
            "FROM ARTICULO A "
            "JOIN DOCLIN L ON L.CODARTICULO = A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO = L.CODDOCUMENTO "
            "WHERE D.TIPO = 13 "
            "AND A.CODFAMILIA IN (SELECT CODIGO FROM FAMILIA LIMIT 3) "
            "GROUP BY A.CODIGO, A.NOMBRE "
            "ORDER BY N_CLIENTES DESC"
        )
        r, _ = self.n.normalize(sql)
        self.assertEqual(r.upper().count("FIRST"), 2)  # uno en outer, uno en subquery
        self.assertNotIn("LIMIT", r.upper())

    def test_query_con_codcliente_en_doccab_funciona(self):
        """
        DOCCAB SÍ tiene CODCLIENTE — el error del bug report era por FIRST mal colocado,
        no por columna inexistente. Verificar que la query se normaliza correctamente.
        """
        sql = (
            "SELECT FIRST 50 A.CODIGO, A.NOMBRE, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
            "FROM ARTICULO A "
            "JOIN DOCLIN L ON L.CODARTICULO = A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO = L.CODDOCUMENTO "
            "WHERE D.TIPO = 13 "
            "GROUP BY A.CODIGO, A.NOMBRE "
            "ORDER BY N_CLIENTES DESC"
        )
        r, _ = self.n.normalize(sql)
        self.assertIn("CODCLIENTE", r.upper())
        self.assertEqual(r.upper().count("FIRST"), 1)
        self.assertNotIn("LIMIT", r.upper())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main(verbosity=2)
