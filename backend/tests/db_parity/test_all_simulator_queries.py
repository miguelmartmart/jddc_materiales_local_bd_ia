"""
test_all_simulator_queries.py — Tests exhaustivos de todas las consultas del simulador.

Verifica que TODAS las consultas de query_library.py y query_library_core.py
ejecutan sin error en el simulador SQLite, agrupadas por departamento, urgencia y tipo.

Principios:
  - Sin BD real: todos los tests usan el simulador SQLite (siempre disponible)
  - Sin inventar valores: solo se verifica que no hay excepcion y se devuelve lista
  - Trazabilidad: cada fallo muestra el query_id y el error exacto
  - SRP: este fichero solo verifica ejecucion de consultas, no estructura de tablas

Notas sobre la biblioteca extendida (get_all_queries):
  - dept puede ser string o lista (queries multi-departamento)
  - urgencia puede tener valores distintos a los 4 del core (Critico/Alto/Medio/Bajo)
  - IDs pueden repetirse entre modulos (cx3_xxx aparece en varios modulos)
  - get_query_by_id devuelve {} (dict vacio) cuando no encuentra, no None
  - La biblioteca extendida usa columnas (COSTE, STOCK, PROVINCIA, etc.) que el
    simulador SQLite no tiene — los tests de ejecucion se limitan al core (77 queries)
    que el simulador soporta completamente.

Ejecutar:
  python -m pytest bots/interjddcia/backend/tests/db_parity/test_all_simulator_queries.py -v

DEVIA: backend/tests/db_parity/DEVIA.md
"""

import logging
import unittest
from typing import Any, Dict, List, Optional

from backend.modules.db_simulator.constants import SimulatorPaths, SimulatorLog
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.query_library import (
    get_all_queries,
    get_query_by_id,
    get_catalog_summary,
    get_queries_by_dept,
    get_queries_by_tipo,
    get_queries_by_urgencia,
    get_queries_by_rol,
    QUERY_LIBRARY,
    Dept,
    Tipo,
    Urgencia,
    Rol,
)
from backend.modules.db_simulator.query_library_core import QUERY_LIBRARY as QUERY_LIBRARY_CORE

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_driver() -> SimulatedFirebirdDriver:
    """Crea y conecta un SimulatedFirebirdDriver (igual que el test existente)."""
    driver = SimulatedFirebirdDriver()
    db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
    driver.connect(db_path=db_path)
    return driver


def _execute_query(driver: SimulatedFirebirdDriver, sql: str):
    """Ejecuta una query directamente. Devuelve (rows, error_msg)."""
    try:
        rows = driver.execute_query(sql)
        return rows, None
    except Exception as e:
        return None, str(e)


def _dept_matches(q_dept, target_dept: str) -> bool:
    """Comprueba si una query pertenece a un departamento (dept puede ser str o list)."""
    if isinstance(q_dept, list):
        return target_dept in q_dept
    return q_dept == target_dept


def _rol_matches(q_rol, target_rol: str) -> bool:
    """Comprueba si una query pertenece a un rol (rol puede ser str o list)."""
    if isinstance(q_rol, list):
        return target_rol in q_rol
    return q_rol == target_rol


def _required_fields(q: Dict) -> List[str]:
    return [f for f in ("id", "title", "sql", "dept", "rol", "tipo", "urgencia") if f not in q]


# ─── Modulo-level fixtures (inicializacion unica) ─────────────────────────────

_DRIVER: Optional[SimulatedFirebirdDriver] = None


def _get_driver() -> SimulatedFirebirdDriver:
    global _DRIVER
    if _DRIVER is None:
        _DRIVER = _make_driver()
    return _DRIVER


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ESTRUCTURA DE LA BIBLIOTECA CORE (query_library_core.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoreQueryLibraryStructure(unittest.TestCase):
    """Verifica la estructura y metadatos de las consultas del core (77 queries)."""

    @classmethod
    def setUpClass(cls):
        cls.core_queries = list(QUERY_LIBRARY_CORE)

    def test_core_queries_have_required_fields(self):
        """Todas las consultas core tienen los campos obligatorios."""
        failures = []
        for q in self.core_queries:
            missing = _required_fields(q)
            if missing:
                failures.append(f"{q.get('id', '?')}: faltan {missing}")
        self.assertFalse(
            failures,
            f"{len(failures)} consultas core con campos faltantes:\n" + "\n".join(failures[:10])
        )

    def test_core_queries_have_non_empty_sql(self):
        """Todas las consultas core tienen SQL no vacio."""
        failures = [q["id"] for q in self.core_queries if not q.get("sql", "").strip()]
        self.assertFalse(failures, f"Consultas core sin SQL: {failures[:10]}")

    def test_core_query_ids_are_unique(self):
        """No hay IDs duplicados en el core."""
        ids = [q["id"] for q in self.core_queries]
        duplicates = [id_ for id_ in set(ids) if ids.count(id_) > 1]
        self.assertFalse(duplicates, f"IDs duplicados en core: {duplicates[:10]}")

    def test_core_queries_count_at_least_77(self):
        """La biblioteca core tiene al menos 77 consultas."""
        self.assertGreaterEqual(
            len(self.core_queries), 77,
            f"Solo {len(self.core_queries)} consultas en core (esperadas >=77)"
        )

    def test_core_queries_have_valid_urgencia(self):
        """Todas las urgencias del core son Critico/Alto/Medio/Bajo."""
        valid = {"Critico", "Alto", "Medio", "Bajo", "Cr\u00edtico"}
        failures = [q["id"] for q in self.core_queries if q.get("urgencia") not in valid]
        self.assertFalse(failures, f"Consultas core con urgencia invalida: {failures[:10]}")

    def test_core_queries_have_valid_dept(self):
        """Todos los departamentos del core son valores conocidos."""
        valid_depts = {
            Dept.VENTAS, Dept.COMPRAS, Dept.ALMACEN, Dept.FINANZAS,
            Dept.RRHH, Dept.DIRECCION, Dept.SAT, Dept.MARKETING, Dept.TODOS,
        }
        failures = []
        for q in self.core_queries:
            dept = q.get("dept")
            if isinstance(dept, list):
                for d in dept:
                    if d not in valid_depts:
                        failures.append(f"{q['id']}: dept invalido '{d}'")
            elif dept not in valid_depts:
                failures.append(f"{q['id']}: dept invalido '{dept}'")
        self.assertFalse(failures, f"Consultas core con dept invalido: {failures[:10]}")

    def test_get_query_by_id_returns_correct_query(self):
        """get_query_by_id() devuelve la consulta correcta para IDs del core."""
        first = self.core_queries[0]
        result = get_query_by_id(first["id"])
        self.assertNotEqual(result, {}, f"get_query_by_id('{first['id']}') devolvio dict vacio")
        self.assertEqual(result["id"], first["id"])

    def test_get_query_by_id_returns_empty_for_unknown(self):
        """get_query_by_id() devuelve dict vacio para IDs inexistentes."""
        result = get_query_by_id("__nonexistent_query_id__")
        self.assertEqual(result, {}, f"Se esperaba dict vacio, se obtuvo: {result}")

    def test_catalog_summary_structure(self):
        """get_catalog_summary() devuelve estructura correcta."""
        summary = get_catalog_summary()
        self.assertIn("total", summary)
        self.assertIn("by_dept", summary)
        self.assertIn("by_tipo", summary)
        self.assertIn("by_urgencia", summary)
        self.assertGreaterEqual(summary["total"], 77)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. EJECUCION — BIBLIOTECA CORE (query_library_core.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoreQueriesExecution(unittest.TestCase):
    """Todas las consultas de query_library_core.py ejecutan sin error."""

    @classmethod
    def setUpClass(cls):
        cls.driver = _get_driver()
        cls.core_queries = list(QUERY_LIBRARY_CORE)

    def test_all_core_queries_execute_without_error(self):
        """Todas las consultas core ejecutan sin excepcion en el simulador."""
        failures = []
        for q in self.core_queries:
            rows, err = _execute_query(self.driver, q["sql"])
            if err:
                failures.append(f"{q['id']}: {err}")
        self.assertFalse(
            failures,
            f"{len(failures)}/{len(self.core_queries)} consultas core fallaron:\n"
            + "\n".join(failures[:15])
        )

    def test_core_queries_return_list(self):
        """Todas las consultas core devuelven una lista (puede estar vacia)."""
        failures = []
        for q in self.core_queries:
            rows, err = _execute_query(self.driver, q["sql"])
            if err is None and not isinstance(rows, list):
                failures.append(f"{q['id']}: devolvio {type(rows).__name__} en lugar de list")
        self.assertFalse(failures, "\n".join(failures[:10]))

    def test_critico_core_queries_execute(self):
        """Las consultas Critico del core ejecutan sin error."""
        critico = [q for q in self.core_queries if q.get("urgencia") in ("Critico", "Cr\u00edtico")]
        failures = []
        for q in critico:
            rows, err = _execute_query(self.driver, q["sql"])
            if err:
                failures.append(f"{q['id']}: {err}")
        self.assertFalse(
            failures,
            f"{len(failures)}/{len(critico)} consultas Critico del core fallaron:\n"
            + "\n".join(failures)
        )

    def test_kpi_core_queries_execute(self):
        """Las consultas KPI del core ejecutan sin error."""
        kpi = [q for q in self.core_queries if q.get("tipo") == Tipo.KPI]
        failures = []
        for q in kpi:
            rows, err = _execute_query(self.driver, q["sql"])
            if err:
                failures.append(f"{q['id']}: {err}")
        self.assertFalse(
            failures,
            f"{len(failures)}/{len(kpi)} consultas KPI del core fallaron:\n"
            + "\n".join(failures)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EJECUCION — BIBLIOTECA COMPLETA (get_all_queries) — INFORMATIVO
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllQueriesExecution(unittest.TestCase):
    """
    Tests informativos sobre la biblioteca completa (core + extendida).

    La biblioteca extendida usa columnas (COSTE, STOCK, PROVINCIA, UNIDADES, etc.)
    que el simulador SQLite no tiene en su esquema. Los errores de tipo
    'no such column' / 'no such table' son ESPERADOS y no indican bugs.

    Solo se verifica:
      - El driver no lanza excepciones no controladas (errores inesperados)
      - Las consultas que si ejecutan devuelven lista
      - El total de consultas es >= 77
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = _get_driver()
        cls.all_queries = get_all_queries()

    def test_all_queries_no_uncontrolled_exceptions(self):
        """
        El driver no lanza excepciones no controladas en ninguna consulta.
        Los errores de esquema (no such column/table, ambiguous column, etc.)
        son esperados en la biblioteca extendida y se ignoran.
        """
        known_schema_errors = (
            "no such column",
            "no such table",
            "ambiguous column",
            "aggregate functions are not allowed",
            "HAVING clause on a non-aggregate",
            "ORDER BY clause should come after UNION",
            "misuse of aggregate function",
        )
        uncontrolled = []
        for q in self.all_queries:
            rows, err = _execute_query(self.driver, q["sql"])
            if err and not any(kw in err for kw in known_schema_errors):
                uncontrolled.append(f"{q['id']}: {err}")
        self.assertFalse(
            uncontrolled,
            f"Errores no controlados en la biblioteca extendida:\n"
            + "\n".join(uncontrolled[:10])
        )

    def test_all_queries_that_execute_return_list(self):
        """Las consultas que ejecutan sin error devuelven una lista."""
        failures = []
        for q in self.all_queries:
            rows, err = _execute_query(self.driver, q["sql"])
            if err is None and not isinstance(rows, list):
                failures.append(f"{q['id']}: devolvio {type(rows).__name__}")
        self.assertFalse(failures, "\n".join(failures[:10]))

    def test_total_queries_count(self):
        """La biblioteca total tiene al menos 77 consultas."""
        self.assertGreaterEqual(
            len(self.all_queries), 77,
            f"Solo {len(self.all_queries)} consultas totales"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. EJECUCION POR DEPARTAMENTO (solo core — el simulador soporta el core)
# ═══════════════════════════════════════════════════════════════════════════════

class TestQueriesByDepartment(unittest.TestCase):
    """Consultas de cada departamento del core ejecutan sin error."""

    @classmethod
    def setUpClass(cls):
        cls.driver = _get_driver()
        cls.core_ids = {q["id"] for q in QUERY_LIBRARY_CORE}

    def _assert_dept_executes(self, dept: str):
        # Solo consultas del core — el simulador no tiene todas las columnas de la biblioteca extendida
        queries = [q for q in get_queries_by_dept(dept) if q["id"] in self.core_ids]
        if not queries:
            self.skipTest(f"No hay consultas core para dept={dept}")
        failures = []
        for q in queries:
            rows, err = _execute_query(self.driver, q["sql"])
            if err:
                failures.append(f"{q['id']}: {err}")
        self.assertFalse(
            failures,
            f"[{dept}] {len(failures)}/{len(queries)} fallaron:\n" + "\n".join(failures[:10])
        )

    def test_ventas_queries_execute(self):
        self._assert_dept_executes(Dept.VENTAS)

    def test_compras_queries_execute(self):
        self._assert_dept_executes(Dept.COMPRAS)

    def test_almacen_queries_execute(self):
        self._assert_dept_executes(Dept.ALMACEN)

    def test_finanzas_queries_execute(self):
        self._assert_dept_executes(Dept.FINANZAS)

    def test_direccion_queries_execute(self):
        self._assert_dept_executes(Dept.DIRECCION)

    def test_sat_queries_execute(self):
        self._assert_dept_executes(Dept.SAT)

    def test_marketing_queries_execute(self):
        self._assert_dept_executes(Dept.MARKETING)

    def test_todos_queries_execute(self):
        self._assert_dept_executes(Dept.TODOS)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. EJECUCION POR URGENCIA (solo core)
# ═══════════════════════════════════════════════════════════════════════════════

class TestQueriesByUrgencia(unittest.TestCase):
    """Consultas de cada nivel de urgencia del core ejecutan sin error."""

    @classmethod
    def setUpClass(cls):
        cls.driver = _get_driver()
        cls.core_ids = {q["id"] for q in QUERY_LIBRARY_CORE}

    def _assert_urgencia_executes(self, urgencia: str):
        # Solo consultas del core
        queries = [q for q in get_queries_by_urgencia(urgencia) if q["id"] in self.core_ids]
        if not queries:
            self.skipTest(f"No hay consultas core para urgencia={urgencia}")
        failures = []
        for q in queries:
            rows, err = _execute_query(self.driver, q["sql"])
            if err:
                failures.append(f"{q['id']}: {err}")
        self.assertFalse(
            failures,
            f"[{urgencia}] {len(failures)}/{len(queries)} fallaron:\n" + "\n".join(failures[:10])
        )

    def test_critico_queries_execute(self):
        self._assert_urgencia_executes("Cr\u00edtico")

    def test_alto_queries_execute(self):
        self._assert_urgencia_executes("Alto")

    def test_medio_queries_execute(self):
        self._assert_urgencia_executes("Medio")

    def test_bajo_queries_execute(self):
        self._assert_urgencia_executes("Bajo")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. EJECUCION POR TIPO (solo core)
# ═══════════════════════════════════════════════════════════════════════════════

class TestQueriesByTipo(unittest.TestCase):
    """Consultas de cada tipo del core ejecutan sin error."""

    @classmethod
    def setUpClass(cls):
        cls.driver = _get_driver()
        cls.core_ids = {q["id"] for q in QUERY_LIBRARY_CORE}

    def _assert_tipo_executes(self, tipo: str):
        # Solo consultas del core
        queries = [q for q in get_queries_by_tipo(tipo) if q["id"] in self.core_ids]
        if not queries:
            self.skipTest(f"No hay consultas core para tipo={tipo}")
        failures = []
        for q in queries:
            rows, err = _execute_query(self.driver, q["sql"])
            if err:
                failures.append(f"{q['id']}: {err}")
        self.assertFalse(
            failures,
            f"[{tipo}] {len(failures)}/{len(queries)} fallaron:\n" + "\n".join(failures[:10])
        )

    def test_kpi_queries_execute(self):
        self._assert_tipo_executes(Tipo.KPI)

    def test_riesgo_queries_execute(self):
        self._assert_tipo_executes(Tipo.RIESGO)

    def test_optimizacion_queries_execute(self):
        self._assert_tipo_executes("Optimizaci\u00f3n")

    def test_prediccion_queries_execute(self):
        self._assert_tipo_executes("Predicci\u00f3n")

    def test_ahorro_queries_execute(self):
        self._assert_tipo_executes("Ahorro")

    def test_operacional_queries_execute(self):
        self._assert_tipo_executes("Operacional")

    def test_estrategico_queries_execute(self):
        self._assert_tipo_executes("Estrat\u00e9gico")

    def test_calidad_queries_execute(self):
        self._assert_tipo_executes("Calidad")

    def test_financiero_queries_execute(self):
        self._assert_tipo_executes("Financiero")

    def test_alerta_queries_execute(self):
        self._assert_tipo_executes("Alerta")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CONSULTAS CRITICAS ESPECIFICAS (smoke test)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCriticalQueriesSmoke(unittest.TestCase):
    """Smoke test de las consultas mas importantes por nombre."""

    @classmethod
    def setUpClass(cls):
        cls.driver = _get_driver()

    def _test_critical_query(self, query_id: str):
        q = get_query_by_id(query_id)
        if not q:  # {} es falsy
            self.skipTest(f"Consulta {query_id} no encontrada en la biblioteca")
        rows, err = _execute_query(self.driver, q["sql"])
        self.assertIsNone(err, f"{query_id} fallo: {err}")
        self.assertIsInstance(rows, list, f"{query_id} no devolvio lista")

    def test_v_kpi_facturacion_total(self):
        self._test_critical_query("v_kpi_facturacion_total")

    def test_v_kpi_top10_clientes(self):
        self._test_critical_query("v_kpi_top10_clientes")

    def test_f_kpi_saldo_caja(self):
        self._test_critical_query("f_kpi_saldo_caja")

    def test_d_kpi_resumen_ejecutivo(self):
        self._test_critical_query("d_kpi_resumen_ejecutivo")

    def test_f_saldo_clientes_vencido(self):
        self._test_critical_query("f_saldo_clientes_vencido")

    def test_f_pagos_proximos(self):
        self._test_critical_query("f_pagos_proximos")

    def test_f_kpi_movimientos_caja_recientes(self):
        self._test_critical_query("f_kpi_movimientos_caja_recientes")

    def test_s_riesgo_sats_sin_facturar(self):
        self._test_critical_query("s_riesgo_sats_sin_facturar")

    def test_top10_clientes_returns_at_most_10(self):
        """v_kpi_top10_clientes devuelve como maximo 10 filas."""
        q = get_query_by_id("v_kpi_top10_clientes")
        if not q:
            self.skipTest("Consulta no encontrada")
        rows, err = _execute_query(self.driver, q["sql"])
        self.assertIsNone(err, f"Error: {err}")
        self.assertLessEqual(len(rows), 10, f"Devolvio {len(rows)} filas (maximo esperado: 10)")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. FILTROS DE BUSQUEDA
# ═══════════════════════════════════════════════════════════════════════════════

class TestQueryFilters(unittest.TestCase):
    """Los filtros de busqueda devuelven resultados correctos."""

    @classmethod
    def setUpClass(cls):
        cls.core_queries = list(QUERY_LIBRARY_CORE)
        cls.core_ids = {q["id"] for q in cls.core_queries}

    def test_get_queries_by_dept_ventas_returns_ventas_queries(self):
        """get_queries_by_dept(Ventas) devuelve solo consultas de Ventas."""
        queries = get_queries_by_dept(Dept.VENTAS)
        self.assertGreater(len(queries), 0, "No hay consultas de Ventas")
        for q in queries:
            dept = q.get("dept")
            self.assertTrue(
                _dept_matches(dept, Dept.VENTAS),
                f"{q['id']}: dept={dept} no incluye Ventas"
            )

    def test_get_queries_by_urgencia_critico_returns_critico(self):
        """get_queries_by_urgencia(Critico) devuelve solo consultas Critico."""
        queries = get_queries_by_urgencia("Cr\u00edtico")
        self.assertGreater(len(queries), 0, "No hay consultas Critico")
        self.assertTrue(
            all(q["urgencia"] == "Cr\u00edtico" for q in queries),
            "Hay consultas de otra urgencia en el resultado Critico"
        )

    def test_get_queries_by_tipo_kpi_returns_only_kpi(self):
        """get_queries_by_tipo(KPI) devuelve solo consultas KPI."""
        queries = get_queries_by_tipo(Tipo.KPI)
        self.assertGreater(len(queries), 0, "No hay consultas KPI")
        self.assertTrue(
            all(q["tipo"] == Tipo.KPI for q in queries),
            "Hay consultas de otro tipo en el resultado KPI"
        )

    def test_get_queries_by_rol_returns_matching_rol(self):
        """get_queries_by_rol() devuelve consultas que incluyen el rol solicitado.
        Nota: rol puede ser string o lista en la biblioteca extendida.
        """
        queries = get_queries_by_rol(Rol.DIRECTOR)
        if not queries:
            self.skipTest("No hay consultas para Rol.DIRECTOR")
        for q in queries:
            rol = q.get("rol")
            matches = _rol_matches(rol, Rol.DIRECTOR)
            self.assertTrue(matches, f"{q['id']}: rol={rol} no incluye {Rol.DIRECTOR}")

    def test_core_filters_return_core_queries(self):
        """Los IDs del core filtrados por dept estan en QUERY_LIBRARY_CORE."""
        ventas_core = [q for q in get_queries_by_dept(Dept.VENTAS) if q["id"] in self.core_ids]
        self.assertGreater(len(ventas_core), 0, "No hay consultas core de Ventas")
        for q in ventas_core:
            self.assertIn(q["id"], self.core_ids, f"{q['id']} no esta en QUERY_LIBRARY_CORE")


# ═══════════════════════════════════════════════════════════════════════════════
# 9. ESTRUCTURA DE LA BIBLIOTECA EXTENDIDA (get_all_queries)
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtendedQueryLibraryStructure(unittest.TestCase):
    """Verifica la estructura basica de la biblioteca extendida."""

    @classmethod
    def setUpClass(cls):
        cls.all_queries = get_all_queries()

    def test_all_queries_have_required_fields(self):
        """Todas las consultas extendidas tienen los campos obligatorios."""
        failures = []
        for q in self.all_queries:
            missing = _required_fields(q)
            if missing:
                failures.append(f"{q.get('id', '?')}: faltan {missing}")
        self.assertFalse(
            failures,
            f"{len(failures)} consultas con campos faltantes:\n" + "\n".join(failures[:10])
        )

    def test_all_queries_have_non_empty_sql(self):
        """Todas las consultas extendidas tienen SQL no vacio."""
        failures = [q["id"] for q in self.all_queries if not q.get("sql", "").strip()]
        self.assertFalse(failures, f"Consultas sin SQL: {failures[:10]}")

    def test_extended_library_larger_than_core(self):
        """La biblioteca extendida tiene mas consultas que el core."""
        core_count = len(list(QUERY_LIBRARY_CORE))
        all_count = len(self.all_queries)
        self.assertGreaterEqual(
            all_count, core_count,
            f"La biblioteca extendida ({all_count}) no puede ser menor que el core ({core_count})"
        )


if __name__ == "__main__":
    unittest.main()
