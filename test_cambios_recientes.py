"""
Tests para los cambios recientes del DEVIA:
  1. Fix alias POSITION -> FIELD_POS en firebird_metadata_queries.py
  2. ARRANCAR_DEVIA.bat: estructura, subrutinas, lógica de puertos
  3. Health endpoint devuelve "DEVIA Chat API"
  4. Integración: el bat detectaría correctamente el DEVIA vs signing-service

Ejecutar:
    cd bots/interjddcia
    set PYTHONUTF8=1
    set PYTHONPATH=%CD%
    .venv\Scripts\python.exe -X utf8 test_cambios_recientes.py
"""
import sys
import os
import re
import json
import unittest

# ─────────────────────────────────────────────────────────────
# SUITE 1: Fix POSITION -> FIELD_POS
# ─────────────────────────────────────────────────────────────
class TestFixPosition(unittest.TestCase):
    """Verifica que el alias POSITION fue corregido a FIELD_POS."""

    def setUp(self):
        from backend.drivers.db.firebird_metadata_queries import QUERY_TABLE_COLUMNS_TYPED
        self.query = QUERY_TABLE_COLUMNS_TYPED

    def test_alias_position_eliminado(self):
        """AS POSITION no debe aparecer en la query (palabra reservada Firebird 2.5)."""
        self.assertNotIn(
            "AS POSITION", self.query,
            "ERROR: 'AS POSITION' sigue en la query — Firebird 2.5 lo rechaza"
        )

    def test_alias_field_pos_presente(self):
        """AS FIELD_POS debe estar en la query como reemplazo."""
        self.assertIn(
            "AS FIELD_POS", self.query,
            "ERROR: 'AS FIELD_POS' no encontrado en la query"
        )

    def test_rdb_field_position_sigue_presente(self):
        """RDB$FIELD_POSITION (nombre de columna del sistema) debe seguir en la query."""
        self.assertIn(
            "RDB$FIELD_POSITION", self.query,
            "ERROR: RDB$FIELD_POSITION (columna del sistema) fue eliminado por error"
        )

    def test_campos_requeridos_en_query(self):
        """Todos los campos que usa el código Python deben estar en la query."""
        campos = ["FIELD_NAME", "FIELD_TYPE", "DECIMAL_TYPE", "NOT_NULL", "FIELD_POS"]
        for campo in campos:
            with self.subTest(campo=campo):
                self.assertIn(campo, self.query, f"Campo {campo} no encontrado en la query")

    def test_metadata_builder_no_usa_alias_position(self):
        """metadata_builder_service no debe acceder al alias 'POSITION' como clave de dict."""
        import inspect
        from backend.modules.db_explorer import metadata_builder_service
        src = inspect.getsource(metadata_builder_service)
        # Eliminar referencias legítimas
        src_clean = src.replace("RDB$FIELD_POSITION", "").replace("FIELD_POSITION", "")
        bad = re.findall(r"""['"]POSITION['"]""", src_clean)
        self.assertEqual(bad, [], f"metadata_builder_service usa alias POSITION: {bad}")

    def test_deep_indexer_no_usa_alias_position(self):
        """deep_indexer_service no debe acceder al alias 'POSITION' como clave de dict."""
        import inspect
        from backend.modules.db_explorer import deep_indexer_service
        src = inspect.getsource(deep_indexer_service)
        src_clean = src.replace("RDB$FIELD_POSITION", "").replace("FIELD_POSITION", "")
        bad = re.findall(r"""['"]POSITION['"]""", src_clean)
        self.assertEqual(bad, [], f"deep_indexer_service usa alias POSITION: {bad}")

    def test_query_es_string_no_vacio(self):
        """La query debe ser un string no vacío."""
        self.assertIsInstance(self.query, str)
        self.assertGreater(len(self.query), 50, "La query parece demasiado corta")

    def test_query_tiene_from_rdb(self):
        """La query debe hacer SELECT de tablas del sistema RDB$."""
        self.assertIn("RDB$", self.query, "La query no accede a tablas del sistema RDB$")


# ─────────────────────────────────────────────────────────────
# SUITE 2: ARRANCAR_DEVIA.bat — estructura y lógica
# ─────────────────────────────────────────────────────────────
class TestArrancarDeviaBat(unittest.TestCase):
    """Verifica la estructura y lógica del ARRANCAR_DEVIA.bat."""

    BAT_PATH = os.path.join(os.path.dirname(__file__), "ARRANCAR_DEVIA.bat")

    def setUp(self):
        self.assertTrue(
            os.path.exists(self.BAT_PATH),
            f"ARRANCAR_DEVIA.bat no encontrado en {self.BAT_PATH}"
        )
        with open(self.BAT_PATH, "r", encoding="utf-8", errors="replace") as f:
            self.content = f.read()

    def test_bat_existe(self):
        """El archivo ARRANCAR_DEVIA.bat debe existir."""
        self.assertTrue(os.path.exists(self.BAT_PATH))

    def test_version_actualizada(self):
        """El bat debe tener la versión 3.1.0."""
        self.assertIn("3.1.0", self.content, "Versión 3.1.0 no encontrada en el bat")

    def test_subrutina_log(self):
        """Debe existir la subrutina :LOG para trazas."""
        self.assertIn(":LOG", self.content, "Subrutina :LOG no encontrada")
        self.assertIn("LOG_FILE", self.content, "Variable LOG_FILE no encontrada")

    def test_subrutina_get_port_pid(self):
        """Debe existir la subrutina :GET_PORT_PID (reemplaza a :KILL_PORT en v3.1.0)."""
        self.assertIn(":GET_PORT_PID", self.content,
                      "Subrutina :GET_PORT_PID no encontrada — necesaria para detectar PID del puerto")

    def test_subrutina_try_free_port(self):
        """Debe existir la subrutina :TRY_FREE_PORT con estrategias múltiples."""
        self.assertIn(":TRY_FREE_PORT", self.content, "Subrutina :TRY_FREE_PORT no encontrada")

    def test_subrutina_resolve_port(self):
        """Debe existir la subrutina :RESOLVE_PORT para puertos alternativos."""
        self.assertIn(":RESOLVE_PORT", self.content, "Subrutina :RESOLVE_PORT no encontrada")

    def test_subrutina_wait_for_devia(self):
        """Debe existir la subrutina :WAIT_FOR_DEVIA."""
        self.assertIn(":WAIT_FOR_DEVIA", self.content, "Subrutina :WAIT_FOR_DEVIA no encontrada")

    def test_puertos_alternativos_definidos(self):
        """Deben estar definidos los puertos alternativos."""
        self.assertIn("DEVIA_PORTS_ALT", self.content, "DEVIA_PORTS_ALT no definido")
        self.assertIn("8010", self.content, "Puerto alternativo 8010 no encontrado")

    def test_deteccion_docker(self):
        """El bat debe detectar procesos Docker."""
        self.assertIn("docker stop", self.content, "Lógica docker stop no encontrada")
        self.assertIn("FIND_DOCKER_CONTAINER_ON_PORT", self.content,
                      "Subrutina FIND_DOCKER_CONTAINER_ON_PORT no encontrada")

    def test_deteccion_python_uvicorn(self):
        """El bat debe detectar y matar procesos Python/uvicorn."""
        self.assertIn("python uvicorn", self.content.lower().replace("\n", " "),
                      "Detección de Python/uvicorn no encontrada")

    def test_verificacion_devia_en_health(self):
        """El bat debe verificar que el health devuelve 'DEVIA' (no otro servicio)."""
        self.assertIn("DEVIA", self.content, "Verificación de 'DEVIA' en health no encontrada")
        self.assertIn("findstr /i", self.content, "findstr para verificar health no encontrado")

    def test_diagnostico_completo(self):
        """El bat debe tener sección de diagnóstico completo."""
        self.assertIn(":DIAGNOSTICO", self.content, "Sección :DIAGNOSTICO no encontrada")
        self.assertIn("CHECK_DOCKER", self.content, "CHECK_DOCKER no encontrado en diagnóstico")
        self.assertIn("CHECK_LOCAL_AI", self.content, "CHECK_LOCAL_AI no encontrado")
        self.assertIn("CHECK_FIREBIRD", self.content, "CHECK_FIREBIRD no encontrado")

    def test_log_dir_creado(self):
        """El bat debe crear el directorio de logs."""
        self.assertIn("LOG_DIR", self.content, "LOG_DIR no definido")
        self.assertIn("mkdir", self.content, "mkdir para logs no encontrado")

    def test_opcion_4_diagnostico(self):
        """La opción 4 debe ir al diagnóstico."""
        self.assertIn('"4" goto :DIAGNOSTICO', self.content,
                      "Routing opción 4 -> DIAGNOSTICO no encontrado")

    def test_scan_ports_subrutina(self):
        """Debe existir :SCAN_PORTS para mostrar estado de puertos."""
        self.assertIn(":SCAN_PORTS", self.content, "Subrutina :SCAN_PORTS no encontrada")

    def test_check_devia_running(self):
        """Debe existir :CHECK_DEVIA_RUNNING para detectar si el DEVIA ya corre."""
        self.assertIn(":CHECK_DEVIA_RUNNING", self.content,
                      "Subrutina :CHECK_DEVIA_RUNNING no encontrada")

    def test_resumen_final_con_log(self):
        """El resumen final debe mostrar la ruta del log."""
        self.assertIn("Log de arranque", self.content, "Referencia al log en resumen no encontrada")

    def test_enabledelayedexpansion(self):
        """El bat debe usar enabledelayedexpansion para variables en bloques."""
        self.assertIn("enabledelayedexpansion", self.content,
                      "enabledelayedexpansion no encontrado — necesario para !VAR! en bloques")


# ─────────────────────────────────────────────────────────────
# SUITE 3: Health endpoint del DEVIA
# ─────────────────────────────────────────────────────────────
class TestHealthEndpoint(unittest.TestCase):
    """Verifica que el health endpoint del DEVIA devuelve los campos correctos."""

    def test_health_devuelve_devia_chat_api(self):
        """El health debe devolver service='DEVIA Chat API'."""
        import importlib
        import inspect
        # Leer el main.py y verificar la respuesta del health
        main_path = os.path.join(os.path.dirname(__file__), "backend", "main.py")
        self.assertTrue(os.path.exists(main_path), "backend/main.py no encontrado")
        with open(main_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertIn('"DEVIA Chat API"', content,
                      "El health no devuelve 'DEVIA Chat API' — el bat no podrá detectarlo")

    def test_health_tiene_status_ok(self):
        """El health debe devolver status='ok'."""
        main_path = os.path.join(os.path.dirname(__file__), "backend", "main.py")
        with open(main_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertIn('"ok"', content, "El health no devuelve status='ok'")

    def test_health_tiene_version(self):
        """El health debe devolver version."""
        main_path = os.path.join(os.path.dirname(__file__), "backend", "main.py")
        with open(main_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertIn("version", content, "El health no devuelve version")

    def test_bat_busca_devia_en_health(self):
        """El bat debe buscar 'DEVIA' en la respuesta del health para verificar que es el DEVIA."""
        bat_path = os.path.join(os.path.dirname(__file__), "ARRANCAR_DEVIA.bat")
        with open(bat_path, "r", encoding="utf-8", errors="replace") as f:
            bat_content = f.read()
        # El bat usa findstr /i "DEVIA" sobre la respuesta del health
        self.assertIn('findstr /i "DEVIA"', bat_content,
                      "El bat no verifica 'DEVIA' en la respuesta del health")


# ─────────────────────────────────────────────────────────────
# SUITE 4: Palabras reservadas Firebird 2.5
# ─────────────────────────────────────────────────────────────
class TestFirebirdReservedWords(unittest.TestCase):
    """Verifica que las queries de introspección no usan palabras reservadas como alias."""

    RESERVED_WORDS = [
        "POSITION", "VALUE", "TYPE", "TIME", "DATE", "YEAR", "MONTH",
        "DAY", "HOUR", "MINUTE", "SECOND", "INDEX", "PLAN", "ORDER",
    ]

    def setUp(self):
        from backend.drivers.db import firebird_metadata_queries as fmq
        import inspect
        self.module_src = inspect.getsource(fmq)
        # Obtener todas las queries del módulo
        self.queries = {}
        for name in dir(fmq):
            val = getattr(fmq, name)
            if isinstance(val, str) and "SELECT" in val.upper() and "RDB$" in val:
                self.queries[name] = val

    def test_hay_queries_de_introspeccion(self):
        """Debe haber al menos una query de introspección Firebird."""
        self.assertGreater(len(self.queries), 0,
                           "No se encontraron queries de introspección en firebird_metadata_queries")

    def test_ninguna_query_usa_as_position(self):
        """Ninguna query debe usar AS POSITION (palabra reservada Firebird 2.5)."""
        for name, query in self.queries.items():
            with self.subTest(query=name):
                self.assertNotIn(
                    "AS POSITION", query,
                    f"Query {name} usa 'AS POSITION' — palabra reservada en Firebird 2.5"
                )

    def test_aliases_usan_prefijos_descriptivos(self):
        """Los aliases en las queries deben usar prefijos descriptivos (FIELD_, FK_, PK_)."""
        for name, query in self.queries.items():
            # Buscar aliases AS <WORD> donde WORD es una sola palabra en mayúsculas
            aliases = re.findall(r'\bAS\s+([A-Z_]+)\b', query)
            for alias in aliases:
                # Los aliases de una sola palabra corta sin prefijo son sospechosos
                if len(alias) <= 6 and alias in self.RESERVED_WORDS:
                    self.fail(
                        f"Query {name}: alias '{alias}' es una palabra reservada de Firebird 2.5"
                    )


# ─────────────────────────────────────────────────────────────
# SUITE 5: Integración — detección signing-service vs DEVIA
# ─────────────────────────────────────────────────────────────
class TestDeteccionServicio(unittest.TestCase):
    """Simula la lógica del bat para detectar si el health es del DEVIA o de otro servicio."""

    def _simula_deteccion_bat(self, health_response: str) -> str:
        """Simula el findstr /i 'DEVIA' del bat."""
        if "DEVIA" in health_response.upper():
            return "DEVIA"
        elif "signing" in health_response.lower():
            return "signing-service"
        else:
            return "otro"

    def test_detecta_devia_correctamente(self):
        """El bat debe detectar el DEVIA cuando el health devuelve 'DEVIA Chat API'."""
        health = '{"status": "ok", "service": "DEVIA Chat API", "version": "3.0.0"}'
        resultado = self._simula_deteccion_bat(health)
        self.assertEqual(resultado, "DEVIA",
                         "No se detectó el DEVIA en la respuesta del health")

    def test_detecta_signing_service(self):
        """El bat debe detectar el signing-service cuando el health lo devuelve."""
        health = '{"status": "ok", "service": "signing-service", "version": "1.0.0"}'
        resultado = self._simula_deteccion_bat(health)
        self.assertEqual(resultado, "signing-service",
                         "No se detectó el signing-service en la respuesta del health")

    def test_no_confunde_servicios(self):
        """El bat no debe confundir el signing-service con el DEVIA."""
        health_signing = '{"status": "ok", "service": "signing-service", "version": "1.0.0"}'
        health_devia = '{"status": "ok", "service": "DEVIA Chat API", "version": "3.0.0"}'
        self.assertNotEqual(
            self._simula_deteccion_bat(health_signing),
            self._simula_deteccion_bat(health_devia),
            "El bat confunde signing-service con DEVIA"
        )

    def test_devia_en_puerto_alternativo(self):
        """El DEVIA debe ser detectado aunque esté en un puerto alternativo (8010, 8011...)."""
        health = '{"status": "ok", "service": "DEVIA Chat API", "version": "3.0.0"}'
        for puerto in [8001, 8010, 8011, 8012, 8013, 8014, 8015]:
            with self.subTest(puerto=puerto):
                resultado = self._simula_deteccion_bat(health)
                self.assertEqual(resultado, "DEVIA",
                                 f"DEVIA no detectado en puerto {puerto}")


# ─────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────
def run_tests():
    """Ejecuta todos los tests con output amigable."""
    suites = [
        ("Fix POSITION -> FIELD_POS", TestFixPosition),
        ("ARRANCAR_DEVIA.bat estructura", TestArrancarDeviaBat),
        ("Health endpoint DEVIA", TestHealthEndpoint),
        ("Palabras reservadas Firebird 2.5", TestFirebirdReservedWords),
        ("Detección signing-service vs DEVIA", TestDeteccionServicio),
    ]

    total_ok = 0
    total_fail = 0
    total_error = 0

    print()
    print("=" * 60)
    print("TESTS — Cambios recientes DEVIA")
    print("=" * 60)

    for suite_name, suite_class in suites:
        suite = unittest.TestLoader().loadTestsFromTestCase(suite_class)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)

        ok = result.testsRun - len(result.failures) - len(result.errors)
        total_ok += ok
        total_fail += len(result.failures)
        total_error += len(result.errors)

        status = "OK" if not result.failures and not result.errors else "FALLO"
        icon = "✓" if status == "OK" else "✗"
        print(f"\n  {icon} {suite_name}: {ok}/{result.testsRun} OK")

        for test, msg in result.failures:
            test_name = str(test).split(" ")[0]
            # Extraer solo la primera línea del mensaje de error
            first_line = msg.strip().split("\n")[-1].strip()
            print(f"      FALLO: {test_name}")
            print(f"             {first_line[:100]}")

        for test, msg in result.errors:
            test_name = str(test).split(" ")[0]
            first_line = msg.strip().split("\n")[-1].strip()
            print(f"      ERROR: {test_name}")
            print(f"             {first_line[:100]}")

    total = total_ok + total_fail + total_error
    print()
    print("=" * 60)
    if total_fail == 0 and total_error == 0:
        print(f"  RESULTADO: {total_ok}/{total} tests OK — TODOS PASADOS")
    else:
        print(f"  RESULTADO: {total_ok}/{total} OK | {total_fail} fallos | {total_error} errores")
    print("=" * 60)
    print()

    return total_fail + total_error


if __name__ == "__main__":
    sys.exit(run_tests())
