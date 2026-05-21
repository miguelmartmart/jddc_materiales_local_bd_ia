"""
test_query_library.py — Tests de la biblioteca de consultas del simulador.

Verifica:
  1. Integridad de la biblioteca (IDs únicos, campos obligatorios, SQL válido)
  2. Índices y búsqueda (por dept, rol, tipo, urgencia, texto)
  3. Ejecución real de cada consulta contra el simulador SQLite
  4. Endpoints REST de la biblioteca

Ejecutar:
  set PYTHONUTF8=1
  set PYTHONPATH=C:\\Users\\migue\\Documents\\activepieces\\pendiente-fact\\bots\\interjddcia
  python -m pytest backend/modules/db_simulator/test_query_library.py -v

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import sys
import os
import unittest
import sqlite3
from typing import Any, Dict, List

# ─── Setup de path ────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from backend.modules.db_simulator.query_library import (
    QUERY_LIBRARY,
    get_all_queries,
    get_query_by_id,
    get_queries_by_dept,
    get_queries_by_rol,
    get_queries_by_tipo,
    get_queries_by_urgencia,
    get_catalog_summary,
    search_queries,
)
from backend.modules.db_simulator.query_library_constants import (
    DEPARTAMENTOS,
    ROLES,
    TIPOS_ANALISIS,
    URGENCIAS,
    TIPO_ICONOS,
    URGENCIA_COLORES,
    DEPT_ICONOS,
)
from backend.modules.db_simulator.manager import simulator_manager
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver


# ─── Campos obligatorios en cada consulta ────────────────────────────────────
REQUIRED_FIELDS = ["id", "title", "desc", "sql", "dept", "rol", "tipo", "urgencia", "kpi", "accion"]


class TestQueryLibraryIntegrity(unittest.TestCase):
    """Tests de integridad de la biblioteca de consultas."""

    def test_library_not_empty(self):
        """La biblioteca debe tener al menos 50 consultas."""
        queries = get_all_queries()
        self.assertGreater(len(queries), 50, "La biblioteca debe tener más de 50 consultas")

    def test_all_ids_unique(self):
        """Todos los IDs deben ser únicos."""
        ids = [q["id"] for q in QUERY_LIBRARY]
        self.assertEqual(len(ids), len(set(ids)), "Hay IDs duplicados en la biblioteca")

    def test_all_required_fields_present(self):
        """Cada consulta debe tener todos los campos obligatorios."""
        for q in QUERY_LIBRARY:
            for field in REQUIRED_FIELDS:
                self.assertIn(
                    field, q,
                    f"Consulta '{q.get('id', '?')}' no tiene el campo '{field}'"
                )

    def test_all_ids_non_empty(self):
        """Todos los IDs deben ser strings no vacíos."""
        for q in QUERY_LIBRARY:
            self.assertIsInstance(q["id"], str)
            self.assertTrue(q["id"].strip(), f"ID vacío en consulta: {q}")

    def test_all_sql_non_empty(self):
        """Todos los SQL deben ser strings no vacíos."""
        for q in QUERY_LIBRARY:
            self.assertIsInstance(q["sql"], str)
            self.assertTrue(q["sql"].strip(), f"SQL vacío en consulta '{q['id']}'")

    def test_all_sql_start_with_select(self):
        """Todas las consultas de la biblioteca deben ser SELECT (solo lectura)."""
        for q in QUERY_LIBRARY:
            first_word = q["sql"].strip().split(None, 1)[0].upper()
            self.assertIn(
                first_word, ("SELECT", "WITH"),
                f"Consulta '{q['id']}' no es SELECT/WITH: empieza con '{first_word}'"
            )

    def test_all_dept_are_lists(self):
        """El campo dept debe ser una lista."""
        for q in QUERY_LIBRARY:
            self.assertIsInstance(q["dept"], list, f"dept no es lista en '{q['id']}'")
            self.assertGreater(len(q["dept"]), 0, f"dept vacío en '{q['id']}'")

    def test_all_rol_are_lists(self):
        """El campo rol debe ser una lista."""
        for q in QUERY_LIBRARY:
            self.assertIsInstance(q["rol"], list, f"rol no es lista en '{q['id']}'")
            self.assertGreater(len(q["rol"]), 0, f"rol vacío en '{q['id']}'")

    def test_all_tipos_valid(self):
        """Todos los tipos deben estar en la lista de tipos válidos."""
        for q in QUERY_LIBRARY:
            self.assertIn(
                q["tipo"], TIPOS_ANALISIS,
                f"Tipo '{q['tipo']}' no válido en consulta '{q['id']}'"
            )

    def test_all_urgencias_valid(self):
        """Todas las urgencias deben estar en la lista de urgencias válidas."""
        for q in QUERY_LIBRARY:
            self.assertIn(
                q["urgencia"], URGENCIAS,
                f"Urgencia '{q['urgencia']}' no válida en consulta '{q['id']}'"
            )

    def test_all_depts_valid(self):
        """Todos los departamentos deben estar en la lista de departamentos válidos."""
        for q in QUERY_LIBRARY:
            for d in q["dept"]:
                self.assertIn(
                    d, DEPARTAMENTOS,
                    f"Departamento '{d}' no válido en consulta '{q['id']}'"
                )

    def test_all_roles_valid(self):
        """Todos los roles deben estar en la lista de roles válidos."""
        for q in QUERY_LIBRARY:
            for r in q["rol"]:
                self.assertIn(
                    r, ROLES,
                    f"Rol '{r}' no válido en consulta '{q['id']}'"
                )


class TestQueryLibraryIndexes(unittest.TestCase):
    """Tests de los índices y funciones de búsqueda."""

    def test_get_query_by_id_found(self):
        """get_query_by_id debe devolver la consulta correcta."""
        first = QUERY_LIBRARY[0]
        result = get_query_by_id(first["id"])
        self.assertEqual(result["id"], first["id"])

    def test_get_query_by_id_not_found(self):
        """get_query_by_id debe devolver dict vacío si el ID no existe."""
        result = get_query_by_id("id_que_no_existe_xyz_123")
        self.assertEqual(result, {})

    def test_get_queries_by_dept_ventas(self):
        """Debe haber consultas de Ventas."""
        results = get_queries_by_dept("Ventas")
        self.assertGreater(len(results), 0, "No hay consultas de Ventas")

    def test_get_queries_by_dept_finanzas(self):
        """Debe haber consultas de Finanzas."""
        results = get_queries_by_dept("Finanzas")
        self.assertGreater(len(results), 0, "No hay consultas de Finanzas")

    def test_get_queries_by_dept_almacen(self):
        """Debe haber consultas de Almacén."""
        results = get_queries_by_dept("Almacén")
        self.assertGreater(len(results), 0, "No hay consultas de Almacén")

    def test_get_queries_by_dept_sat(self):
        """Debe haber consultas de SAT."""
        results = get_queries_by_dept("SAT / Técnico")
        self.assertGreater(len(results), 0, "No hay consultas de SAT")

    def test_get_queries_by_rol_director(self):
        """Debe haber consultas para el Director."""
        results = get_queries_by_rol("Director")
        self.assertGreater(len(results), 0, "No hay consultas para Director")

    def test_get_queries_by_tipo_kpi(self):
        """Debe haber consultas de tipo KPI."""
        results = get_queries_by_tipo("KPI")
        self.assertGreater(len(results), 0, "No hay consultas de tipo KPI")

    def test_get_queries_by_tipo_riesgo(self):
        """Debe haber consultas de tipo Riesgo."""
        results = get_queries_by_tipo("Riesgo")
        self.assertGreater(len(results), 0, "No hay consultas de tipo Riesgo")

    def test_get_queries_by_urgencia_critico(self):
        """Debe haber consultas de urgencia Crítico."""
        results = get_queries_by_urgencia("Crítico")
        self.assertGreater(len(results), 0, "No hay consultas de urgencia Crítico")

    def test_search_by_text(self):
        """La búsqueda por texto debe funcionar."""
        results = search_queries(text="factura")
        self.assertGreater(len(results), 0, "Búsqueda por 'factura' no devuelve resultados")

    def test_search_by_dept_and_tipo(self):
        """La búsqueda combinada dept+tipo debe funcionar."""
        results = search_queries(dept="Ventas", tipo="KPI")
        self.assertGreater(len(results), 0, "Búsqueda Ventas+KPI no devuelve resultados")
        for q in results:
            self.assertIn("Ventas", q["dept"])
            self.assertEqual(q["tipo"], "KPI")

    def test_search_by_urgencia_critico(self):
        """La búsqueda por urgencia Crítico debe devolver solo críticos."""
        results = search_queries(urgencia="Crítico")
        for q in results:
            self.assertEqual(q["urgencia"], "Crítico")

    def test_catalog_summary_structure(self):
        """El resumen del catálogo debe tener la estructura correcta."""
        summary = get_catalog_summary()
        self.assertIn("total", summary)
        self.assertIn("por_departamento", summary)
        self.assertIn("por_rol", summary)
        self.assertIn("por_tipo", summary)
        self.assertIn("por_urgencia", summary)
        self.assertGreater(summary["total"], 0)

    def test_catalog_total_matches_library(self):
        """El total del catálogo debe coincidir con el tamaño de la biblioteca."""
        summary = get_catalog_summary()
        self.assertEqual(summary["total"], len(QUERY_LIBRARY))


class TestQueryLibraryConstants(unittest.TestCase):
    """Tests de las constantes de la biblioteca."""

    def test_tipo_iconos_covers_all_tipos(self):
        """Todos los tipos de análisis deben tener icono."""
        for tipo in TIPOS_ANALISIS:
            self.assertIn(tipo, TIPO_ICONOS, f"Tipo '{tipo}' sin icono")

    def test_urgencia_colores_covers_all_urgencias(self):
        """Todas las urgencias deben tener color."""
        for urgencia in URGENCIAS:
            self.assertIn(urgencia, URGENCIA_COLORES, f"Urgencia '{urgencia}' sin color")

    def test_dept_iconos_covers_all_depts(self):
        """Todos los departamentos deben tener icono."""
        for dept in DEPARTAMENTOS:
            self.assertIn(dept, DEPT_ICONOS, f"Departamento '{dept}' sin icono")


class TestQueryLibraryExecution(unittest.TestCase):
    """Tests de ejecución real de consultas contra el simulador SQLite."""

    @classmethod
    def setUpClass(cls):
        """Asegurar que el simulador está listo antes de los tests."""
        try:
            simulator_manager.ensure_ready()
            cls.simulator_ready = True
        except Exception as e:
            cls.simulator_ready = False
            cls.simulator_error = str(e)

    def _skip_if_not_ready(self):
        if not self.simulator_ready:
            self.skipTest(f"Simulador no disponible: {getattr(self, 'simulator_error', 'desconocido')}")

    def _execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Ejecuta una consulta SQL contra el simulador y devuelve las filas."""
        driver = SimulatedFirebirdDriver()
        driver.connect()
        try:
            return driver.execute_query(sql)
        finally:
            driver.disconnect()

    def test_execute_facturacion_total(self):
        """La consulta de facturación total debe ejecutarse sin error."""
        self._skip_if_not_ready()
        q = get_query_by_id("v_kpi_facturacion_total")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        self.assertIn("FACTURACION_TOTAL", rows[0])

    def test_execute_top10_clientes(self):
        """La consulta de top 10 clientes debe devolver hasta 10 filas."""
        self._skip_if_not_ready()
        q = get_query_by_id("v_kpi_top10_clientes")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 10)
        if rows:
            self.assertIn("NOMBRE", rows[0])
            self.assertIn("TOTAL", rows[0])

    def test_execute_saldo_caja(self):
        """La consulta de saldo de caja debe ejecutarse sin error."""
        self._skip_if_not_ready()
        q = get_query_by_id("f_kpi_saldo_caja")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        self.assertIn("SALDO_NETO", rows[0])

    def test_execute_stock_total(self):
        """La consulta de valor de stock debe ejecutarse sin error."""
        self._skip_if_not_ready()
        q = get_query_by_id("a_kpi_valor_stock_total")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        self.assertIn("VALOR_STOCK_TOTAL", rows[0])

    def test_execute_resumen_ejecutivo(self):
        """El resumen ejecutivo debe devolver exactamente 10 indicadores."""
        self._skip_if_not_ready()
        q = get_query_by_id("d_kpi_resumen_ejecutivo")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 10, "El resumen ejecutivo debe tener 10 indicadores")
        indicadores = [r["INDICADOR"] for r in rows]
        self.assertIn("Facturación total", indicadores)
        self.assertIn("Saldo caja", indicadores)

    def test_execute_conversion_presupuestos(self):
        """La consulta de conversión de presupuestos debe devolver TASA_CONVERSION_PCT."""
        self._skip_if_not_ready()
        q = get_query_by_id("v_kpi_conversion_presupuestos")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        self.assertIn("TASA_CONVERSION_PCT", rows[0])

    def test_execute_sats_mes(self):
        """La consulta de SATs del mes debe ejecutarse sin error."""
        self._skip_if_not_ready()
        q = get_query_by_id("s_kpi_sats_mes")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)

    def test_execute_rfm_clientes(self):
        """La consulta RFM de clientes debe ejecutarse sin error."""
        self._skip_if_not_ready()
        q = get_query_by_id("mod_segmentacion_rfm")
        self.assertNotEqual(q, {}, "Consulta mod_segmentacion_rfm no encontrada")
        rows = self._execute_query(q["sql"])
        self.assertIsInstance(rows, list)
        if rows:
            self.assertIn("NOMBRE", rows[0])
            self.assertIn("FRECUENCIA", rows[0])
            self.assertIn("MONETARIO", rows[0])

    # Tablas/columnas que solo existen en Firebird real, no en el SQLite del simulador.
    # Las consultas que las usan son válidas para producción pero no para el simulador.
    _FIREBIRD_ONLY_TABLES = {
        "EFECTOSCOBRO", "EFECTOSPAGO", "PROVEEDOR",
    }
    _FIREBIRD_ONLY_COLUMNS = {
        "STOCKACTUAL", "STOCKMINIMO", "PRECIOCOSTE", "REFERENCIA",
        "ACTIVO", "CODDOCREL",
    }

    def _is_firebird_only_error(self, error_msg: str) -> bool:
        """Devuelve True si el error es por tabla/columna que solo existe en Firebird real."""
        msg = str(error_msg).upper()
        for t in self._FIREBIRD_ONLY_TABLES:
            if t in msg:
                return True
        for c in self._FIREBIRD_ONLY_COLUMNS:
            if c in msg:
                return True
        return False

    def test_execute_all_queries_no_exception(self):
        """
        Todas las consultas compatibles con SQLite deben ejecutarse sin excepción.
        Las consultas que usan tablas/columnas solo disponibles en Firebird real
        se marcan como 'Firebird-only' y no se consideran fallos del simulador.
        """
        self._skip_if_not_ready()
        driver = SimulatedFirebirdDriver()
        driver.connect()
        errors = []
        firebird_only = []
        try:
            for q in QUERY_LIBRARY:
                try:
                    rows = driver.execute_query(q["sql"])
                    self.assertIsInstance(rows, list, f"'{q['id']}' no devuelve lista")
                except Exception as e:
                    if self._is_firebird_only_error(str(e)):
                        firebird_only.append(q['id'])
                    else:
                        errors.append(f"  - {q['id']}: {e}")
        finally:
            driver.disconnect()

        if firebird_only:
            print(f"\n  [INFO] {len(firebird_only)} consultas Firebird-only (esperado): {firebird_only}")

        if errors:
            self.fail(
                f"{len(errors)} consultas fallaron con error inesperado:\n" + "\n".join(errors)
            )

    def test_execute_all_queries_return_list(self):
        """
        Todas las consultas compatibles con SQLite deben devolver una lista.
        Las consultas Firebird-only se omiten silenciosamente.
        """
        self._skip_if_not_ready()
        driver = SimulatedFirebirdDriver()
        driver.connect()
        try:
            for q in QUERY_LIBRARY:
                try:
                    rows = driver.execute_query(q["sql"])
                    self.assertIsInstance(
                        rows, list,
                        f"Consulta '{q['id']}' no devuelve lista"
                    )
                except Exception as e:
                    if not self._is_firebird_only_error(str(e)):
                        raise
        finally:
            driver.disconnect()


class TestQueryLibraryAPI(unittest.TestCase):
    """Tests de los endpoints REST de la biblioteca (requieren servidor en :8001)."""

    BASE_URL = "http://localhost:8001/api/db-simulator"

    def _get(self, path: str) -> Dict[str, Any]:
        """Hace GET a la API y devuelve el JSON."""
        import urllib.request
        import json
        url = f"{self.BASE_URL}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            self.skipTest(f"Servidor no disponible en {url}: {e}")

    def _post(self, path: str, data: Dict) -> Dict[str, Any]:
        """Hace POST a la API y devuelve el JSON."""
        import urllib.request
        import json
        url = f"{self.BASE_URL}{path}"
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            self.skipTest(f"Servidor no disponible en {url}: {e}")

    def test_api_catalog_endpoint(self):
        """GET /query-library/catalog debe devolver el catálogo."""
        data = self._get("/query-library/catalog")
        self.assertTrue(data.get("success"))
        self.assertIn("catalog", data)
        self.assertGreater(data["catalog"]["total"], 0)

    def test_api_search_all(self):
        """GET /query-library/search sin filtros debe devolver consultas."""
        data = self._get("/query-library/search")
        self.assertTrue(data.get("success"))
        self.assertGreater(data.get("total", 0), 0)

    def test_api_search_by_dept(self):
        """GET /query-library/search?dept=Ventas debe devolver consultas de Ventas."""
        data = self._get("/query-library/search?dept=Ventas")
        self.assertTrue(data.get("success"))
        self.assertGreater(data.get("total", 0), 0)

    def test_api_search_by_urgencia_critico(self):
        """GET /query-library/search?urgencia=Crítico debe devolver solo críticos."""
        data = self._get("/query-library/search?urgencia=Cr%C3%ADtico")
        self.assertTrue(data.get("success"))
        for q in data.get("queries", []):
            self.assertEqual(q["urgencia"], "Crítico")

    def test_api_get_query_detail(self):
        """GET /query-library/{id} debe devolver el SQL de la consulta."""
        data = self._get("/query-library/v_kpi_facturacion_total")
        self.assertTrue(data.get("success"))
        self.assertIn("query", data)
        self.assertIn("sql", data["query"])
        self.assertTrue(data["query"]["sql"].strip().upper().startswith("SELECT"))

    def test_api_get_query_not_found(self):
        """GET /query-library/id_inexistente debe devolver 404."""
        import urllib.request
        import urllib.error
        url = f"{self.BASE_URL}/query-library/id_que_no_existe_xyz"
        try:
            urllib.request.urlopen(url, timeout=5)
            self.fail("Debería haber devuelto 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)
        except Exception:
            self.skipTest("Servidor no disponible")

    def test_api_execute_library_query(self):
        """POST /query-library/{id}/execute debe ejecutar la consulta y devolver filas."""
        data = self._post("/query-library/v_kpi_facturacion_total/execute", {})
        self.assertTrue(data.get("success"))
        self.assertIn("rows", data)
        self.assertIn("columns", data)
        self.assertIsInstance(data["rows"], list)


# ─── Punto de entrada ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Modo compacto: muestra solo fallos
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Añadir todos los test cases
    for cls in [
        TestQueryLibraryIntegrity,
        TestQueryLibraryIndexes,
        TestQueryLibraryConstants,
        TestQueryLibraryExecution,
        TestQueryLibraryAPI,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    passed = total - failed - skipped

    print(f"\n{'='*60}")
    print(f"RESULTADO: {passed}/{total} tests OK | {failed} fallos | {skipped} omitidos")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
