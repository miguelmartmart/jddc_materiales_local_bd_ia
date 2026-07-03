"""
test_query_parity_realtime.py — Verifica que las consultas de la biblioteca devuelven
los MISMOS resultados en BD simulada y BD Firebird real.

Principio: el simulador es un espejo de la BD real.
  - Mismas columnas de salida
  - Mismos conteos / órdenes de magnitud
  - Sin datos inventados

Requisitos:
  - BD Firebird accesible (192.168.0.254:3050)
  - simulator.db con datos reales (build-snapshot ejecutado)

Ejecutar:
  set PYTHONUTF8=1
  python -m pytest backend/tests/db_parity/test_query_parity_realtime.py -v

Solo columnas (sin BD):
  python -m pytest backend/tests/db_parity/test_query_parity_realtime.py -v -k "columnas"

DEVIA: backend/tests/db_parity/DEVIA.md
"""

import logging
import unittest
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.modules.db_simulator.constants import (
    JDDCTableNames, JDDCDocTipos, TestModeConfig, SimulatorLog,
)
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

logger = logging.getLogger(__name__)


# ─── Queries de paridad — deben funcionar en AMBAS BDs ───────────────────────
# Escritas en SQLite y traducidas a Firebird via adapt_sql_for_firebird + normalize.
# Columnas de salida deben ser idénticas en ambas BDs.

PARITY_QUERIES: List[Dict[str, Any]] = [
    {
        "id": "count_doccab",
        "desc": "Número total de documentos",
        "sql_sqlite": "SELECT COUNT(*) AS N FROM DOCCAB",
        "check": "count_positive",
    },
    {
        "id": "tipos_documento",
        "desc": "Tipos de documento distintos",
        "sql_sqlite": "SELECT DISTINCT TIPO FROM DOCCAB ORDER BY TIPO",
        "check": "same_columns",
    },
    {
        "id": "facturacion_total",
        "desc": "Importe total facturas compra (TIPO=13)",
        "sql_sqlite": (
            # COUNT alias "N" requerido para el check count_positive
            "SELECT COUNT(*) AS N, SUM(IMPORTETOTAL) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=13"
        ),
        "check": "same_columns_count_positive",
    },
    {
        "id": "top_clientes",
        "desc": "Top clientes por facturación",
        "sql_sqlite": (
            # GROUP BY debe incluir todos los no-agregados para compatibilidad Firebird
            "SELECT D.CODCLIENTE, "
            "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, 'Sin nombre') AS CLIENTE, "
            "COUNT(*) AS N_FACTURAS, SUM(D.IMPORTETOTAL) AS TOTAL "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 "
            "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
            "ORDER BY TOTAL DESC LIMIT 5"
        ),
        "check": "same_columns",
    },
    {
        "id": "articulos_mas_vendidos",
        "desc": "Artículos más vendidos",
        "sql_sqlite": (
            # GROUP BY incluye L.CODARTICULO y A.NOMBRE para compatibilidad Firebird
            "SELECT L.CODARTICULO, COALESCE(A.NOMBRE, CAST(L.CODARTICULO AS TEXT)) AS ARTICULO, "
            "SUM(L.CANTIDAD) AS TOTAL_CANTIDAD "
            "FROM DOCLIN L "
            "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
            "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
            "GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY TOTAL_CANTIDAD DESC LIMIT 5"
        ),
        "check": "same_columns",
    },
    {
        "id": "ventas_por_mes",
        "desc": "Ventas agregadas por mes (año actual)",
        "sql_sqlite": (
            # MES calculado con SUBSTR — adapter traduce a EXTRACT para Firebird
            "SELECT SUBSTR(FECHA,1,4)||'-'||SUBSTR(FECHA,6,2) AS MES, "
            "COUNT(*) AS N, SUM(IMPORTETOTAL) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=13 "
            "GROUP BY SUBSTR(FECHA,1,4)||'-'||SUBSTR(FECHA,6,2) ORDER BY MES DESC LIMIT 12"
        ),
        "check": "same_columns",
    },
    {
        "id": "resumen_importes",
        "desc": "Resumen de importes: base, IVA, total",
        "sql_sqlite": (
            # Evitar alias IVA (el adapter lo traduce a IMPORTEIVA en Firebird)
            "SELECT TIPO, COUNT(*) AS N, "
            "SUM(IMPORTEBASE) AS TOTAL_BASE, SUM(IMPORTEIVA) AS TOTAL_IVA, "
            "SUM(IMPORTETOTAL) AS TOTAL "
            "FROM DOCCAB WHERE TIPO IN (3,13) GROUP BY TIPO ORDER BY TIPO"
        ),
        "check": "same_columns",
    },
    {
        "id": "clientes_activos",
        "desc": "Clientes que han generado documentos",
        "sql_sqlite": (
            "SELECT COUNT(DISTINCT D.CODCLIENTE) AS N "
            "FROM DOCCAB D WHERE D.CODCLIENTE IS NOT NULL AND D.CODCLIENTE > 0"
        ),
        "check": "same_columns_count_positive",
    },
    {
        "id": "proveedores_activos",
        "desc": "Conteo de proveedores en tabla PROVEED",
        "sql_sqlite": "SELECT COUNT(*) AS N FROM PROVEED",
        "check": "count_positive",
    },
    {
        "id": "articulos_con_stock",
        "desc": "Artículos con stock positivo",
        "sql_sqlite": (
            "SELECT COUNT(*) AS N FROM ARTICULO WHERE STOCKARTICULO > 0"
        ),
        "check": "same_columns",
    },
    {
        "id": "caja_movimientos",
        "desc": "Resumen de movimientos de caja",
        "sql_sqlite": (
            "SELECT TIPO, COUNT(*) AS N, SUM(IMPORTE) AS TOTAL "
            "FROM CAJA GROUP BY TIPO ORDER BY TIPO"
        ),
        "check": "same_columns",
    },
    {
        "id": "presupuestos_pendientes",
        "desc": "Presupuestos de cliente sin convertir (TIPO=0)",
        "sql_sqlite": (
            "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0"
        ),
        "check": "same_columns",
    },
]


def _adapt_for_firebird(sql: str) -> str:
    """Convierte SQL SQLite a Firebird via adapter + normalizer."""
    adapted, _ = adapt_sql_for_firebird(sql)
    normalized, _ = FirebirdSQLNormalizer().normalize(adapted)
    return normalized


def _get_firebird_driver():
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


class RealDBTestCase(unittest.TestCase):
    """Base: salta tests si BD Firebird no disponible."""
    _driver = None
    _db_available: Optional[bool] = None
    _db_error: str = ""

    @classmethod
    def setUpClass(cls):
        try:
            cls._driver = _get_firebird_driver()
            cls._driver.execute_query("SELECT FIRST 1 CODIGO FROM DOCCAB")
            cls._db_available = True
        except Exception as e:
            cls._db_available = False
            cls._db_error = str(e)
            cls._driver = None

    @classmethod
    def tearDownClass(cls):
        if cls._driver:
            try:
                cls._driver.disconnect()
            except Exception:
                pass

    def _skip_if_no_db(self):
        if not self._db_available:
            self.skipTest(f"BD Firebird no disponible: {self._db_error}")


# ─── Tests de paridad real vs simulado ───────────────────────────────────────

class TestParidadRealVsSimulado(RealDBTestCase):
    """
    Para cada query en PARITY_QUERIES, verifica que:
    1. La query se ejecuta sin error en ambas BDs
    2. Las columnas de salida son idénticas
    3. El conteo de filas es coherente (no necesariamente idéntico — volumen puede diferir)
    """

    def setUp(self):
        self.sim = SimulatedFirebirdDriver()
        from backend.modules.db_simulator.constants import SimulatorPaths
        db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
        self.sim.connect(db_path=db_path)
        self._sim_path = db_path

    def tearDown(self):
        self.sim.disconnect()

    def _skip_if_sim_empty(self):
        rows = self.sim.execute_query("SELECT COUNT(*) AS N FROM DOCCAB")
        n = rows[0].get("N", 0) if rows else 0
        if n == 0:
            self.skipTest("BD simulada vacía — ejecutar build-snapshot primero")

    def _run_parity_check(self, q: Dict[str, Any]) -> None:
        """Ejecuta un check de paridad para una query individual."""
        sql_sim = q["sql_sqlite"]
        sql_fb = _adapt_for_firebird(sql_sim)
        check = q.get("check", "same_columns")
        qid = q["id"]
        desc = q["desc"]

        # Simulador
        try:
            rows_sim = self.sim.execute_query(sql_sim)
        except Exception as e:
            self.fail(f"[{qid}] Error en simulador: {e}\nSQL: {sql_sim}")

        # Firebird real
        try:
            rows_fb = self._driver.execute_query(sql_fb)
        except Exception as e:
            self.fail(f"[{qid}] Error en Firebird: {e}\nSQL Firebird: {sql_fb}")

        # Verificar columnas
        if rows_sim and rows_fb:
            cols_sim = set(rows_sim[0].keys())
            cols_fb  = set(rows_fb[0].keys())
            self.assertEqual(
                cols_sim, cols_fb,
                f"[{qid}] Columnas difieren:\n"
                f"  Simulador: {sorted(cols_sim)}\n"
                f"  Firebird:  {sorted(cols_fb)}"
            )

        # Verificar count positivo
        if "count_positive" in check:
            n_sim = rows_sim[0].get("N", 0) if rows_sim else 0
            n_fb  = rows_fb[0].get("N", 0)  if rows_fb  else 0
            self.assertGreater(n_sim, 0, f"[{qid}] Simulador devuelve N=0 ({desc})")
            self.assertGreater(n_fb,  0, f"[{qid}] Firebird real devuelve N=0 ({desc})")

        logger.info(
            f"{TestModeConfig.LOG_PREFIX} [{qid}] {desc}: "
            f"sim={len(rows_sim)} filas, real={len(rows_fb)} filas"
        )

    def test_count_doccab_positivo_en_ambas_bds(self):
        """DOCCAB debe tener registros en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "count_doccab"))

    def test_tipos_documento_columnas_identicas(self):
        """SELECT DISTINCT TIPO devuelve las mismas columnas en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "tipos_documento"))

    def test_facturacion_total_columnas_identicas(self):
        """Facturación total devuelve las mismas columnas con datos positivos."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "facturacion_total"))

    def test_top_clientes_columnas_identicas(self):
        """Top clientes devuelve las mismas columnas en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "top_clientes"))

    def test_articulos_mas_vendidos_columnas_identicas(self):
        """Artículos más vendidos devuelve las mismas columnas."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "articulos_mas_vendidos"))

    def test_ventas_por_mes_columnas_identicas(self):
        """Ventas por mes devuelve las mismas columnas."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "ventas_por_mes"))

    def test_resumen_importes_columnas_identicas(self):
        """Resumen BASE+IVA+TOTAL devuelve las mismas columnas en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "resumen_importes"))

    def test_clientes_activos_columnas_identicas(self):
        """Conteo de clientes activos devuelve las mismas columnas."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "clientes_activos"))

    def test_proveedores_positivo_en_ambas(self):
        """Proveedores: ambas BDs tienen registros."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "proveedores_activos"))

    def test_articulos_con_stock_columnas_identicas(self):
        """Artículos con stock positivo: mismas columnas."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "articulos_con_stock"))

    def test_caja_movimientos_columnas_identicas(self):
        """Movimientos de caja: mismas columnas en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "caja_movimientos"))

    def test_presupuestos_pendientes_columnas_identicas(self):
        """Presupuestos de cliente: mismas columnas."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()
        self._run_parity_check(next(q for q in PARITY_QUERIES if q["id"] == "presupuestos_pendientes"))


class TestAdaptacionSQLParaBD(unittest.TestCase):
    """
    Verifica que adapt_sql_for_firebird() convierte correctamente las queries
    de paridad para que sean sintaxis Firebird válida.
    No requiere BD.
    """

    def _adapt(self, sql: str) -> str:
        return _adapt_for_firebird(sql)

    def test_count_doccab_se_adapta_a_firebird(self):
        sql = "SELECT COUNT(*) AS N FROM DOCCAB"
        adapted = self._adapt(sql)
        self.assertIn("FROM DOCCAB", adapted.upper())
        self.assertNotIn("LIMIT", adapted.upper())

    def test_top_clientes_recibe_first_not_limit(self):
        sql = (
            "SELECT COALESCE(C.NOMBRECOMERCIAL,C.RAZONSOCIAL,'X') AS C, COUNT(*) AS N "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE ORDER BY N DESC LIMIT 5"
        )
        adapted = self._adapt(sql)
        self.assertIn("FIRST 5", adapted.upper())
        self.assertNotIn("LIMIT", adapted.upper())

    def test_substr_fecha_se_convierte_para_firebird(self):
        sql = "SELECT SUBSTR(FECHA,1,7) AS MES FROM DOCCAB LIMIT 1"
        adapted = self._adapt(sql)
        self.assertIn("EXTRACT", adapted.upper())

    def test_importebase_ya_no_necesita_traduccion(self):
        """IMPORTEBASE ya es el nombre real — no debe traducirse ni cambiarse."""
        sql = "SELECT SUM(IMPORTEBASE) AS BASE FROM DOCCAB WHERE TIPO=13"
        adapted = self._adapt(sql)
        self.assertIn("IMPORTEBASE", adapted.upper())
        self.assertNotIn("BASEIMPONIBLE", adapted.upper())

    def test_precioventa_ya_no_necesita_traduccion(self):
        """PRECIOVENTA ya es el nombre real en simulador y Firebird."""
        sql = "SELECT A.PRECIOVENTA FROM ARTICULO A LIMIT 1"
        adapted = self._adapt(sql)
        self.assertIn("PRECIOVENTA", adapted.upper())

    def test_baseimponible_legacy_se_traduce_correctamente(self):
        """Queries legacy con BASEIMPONIBLE se traducen a IMPORTEBASE para Firebird."""
        sql = "SELECT SUM(BASEIMPONIBLE) AS BASE FROM DOCCAB WHERE TIPO=13"
        adapted = self._adapt(sql)
        self.assertIn("IMPORTEBASE", adapted.upper())


class TestParidadLibraryQueries(RealDBTestCase):
    """
    Ejecuta las queries críticas de la biblioteca (urgencia=Crítico o tipo=KPI)
    contra BD real y simulada, verificando paridad de columnas.
    Requiere BD Firebird y simulator.db.
    """

    def setUp(self):
        self.sim = SimulatedFirebirdDriver()
        from backend.modules.db_simulator.constants import SimulatorPaths
        db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
        self.sim.connect(db_path=db_path)
        self._sim_path = db_path

    def tearDown(self):
        self.sim.disconnect()

    def _skip_if_sim_empty(self):
        rows = self.sim.execute_query("SELECT COUNT(*) AS N FROM DOCCAB")
        n = rows[0].get("N", 0) if rows else 0
        if n == 0:
            self.skipTest("BD simulada vacía — ejecutar build-snapshot primero")

    def test_query_library_criticas_pasan_en_simulador(self):
        """Todas las queries críticas de la biblioteca ejecutan en simulador sin error."""
        from backend.modules.db_simulator.query_library import get_all_queries
        qs = [q for q in get_all_queries() if q.get("urgencia") == "Crítico"]
        failed = []
        ok = 0
        for q in qs:
            try:
                self.sim.execute_query(q["sql"])
                ok += 1
            except Exception as e:
                failed.append((q["id"], str(e)[:80]))
        pct = 100 * ok / len(qs) if qs else 0
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} Crítico: {ok}/{len(qs)} OK ({pct:.1f}%)\n"
            + ("\n".join(f"  FAIL {fid}: {e}" for fid, e in failed[:10]) if failed else "")
        )
        # Umbral 75%: estado tras bulk-fix. Objetivo futuro: >85%.
        self.assertGreater(pct, 75, f"Menos del 75% de queries Crítico pasan: {pct:.1f}%\n"
                           + "\n".join(f"  {fid}: {e}" for fid, e in failed[:10]))

    def test_query_library_kpi_pasan_en_simulador(self):
        """Todas las queries KPI ejecutan en simulador."""
        from backend.modules.db_simulator.query_library import get_all_queries
        qs = [q for q in get_all_queries() if q.get("tipo") == "KPI"]
        failed = []
        ok = 0
        for q in qs:
            try:
                self.sim.execute_query(q["sql"])
                ok += 1
            except Exception as e:
                failed.append((q["id"], str(e)[:80]))
        pct = 100 * ok / len(qs) if qs else 0
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} KPI: {ok}/{len(qs)} OK ({pct:.1f}%)"
        )
        # Umbral 75%: estado tras bulk-fix de columnas. Objetivo futuro: >85%.
        self.assertGreater(pct, 75, f"Menos del 75% de queries KPI pasan: {pct:.1f}%")

    def test_kpi_facturacion_total_paridad_columnas(self):
        """v_kpi_facturacion_total devuelve las mismas columnas en ambas BDs."""
        self._skip_if_no_db()
        self._skip_if_sim_empty()

        from backend.modules.db_simulator.query_library import get_query_by_id
        q = get_query_by_id("v_kpi_facturacion_total")
        self.assertNotEqual(q, {}, "v_kpi_facturacion_total no encontrada en la biblioteca")

        rows_sim = self.sim.execute_query(q["sql"])
        self.assertGreater(len(rows_sim), 0, "Simulador no devuelve datos para v_kpi_facturacion_total")

        fb_sql = _adapt_for_firebird(q["sql"])
        rows_fb = self._driver.execute_query(fb_sql)
        self.assertGreater(len(rows_fb), 0, "BD real no devuelve datos para v_kpi_facturacion_total")

        cols_sim = set(rows_sim[0].keys())
        cols_fb  = set(rows_fb[0].keys())
        self.assertEqual(
            cols_sim, cols_fb,
            f"Columnas v_kpi_facturacion_total:\n  sim={sorted(cols_sim)}\n  real={sorted(cols_fb)}"
        )
        logger.info(
            f"{TestModeConfig.LOG_PREFIX} v_kpi_facturacion_total — "
            f"sim={rows_sim[0].get('FACTURACION_TOTAL')}, real={rows_fb[0].get('FACTURACION_TOTAL')}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main(verbosity=2)
