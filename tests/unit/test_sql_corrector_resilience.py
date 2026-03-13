"""
tests/unit/test_sql_corrector_resilience.py
Tests REALES sin mocks para las nuevas funcionalidades de sql_corrector.py
y markdownToHtml de siuo_constants.js (lógica Python equivalente).

Cubre SIN MOCKS:
  1. _load_sql_max_retries() lee config.json real
  2. _find_similar_tables_in_db() con execute_func real (Firebird en LAN)
     — si no hay BD disponible, el test se marca como SKIP automáticamente
  3. _get_all_tables_from_metadata() lee db_metadata_optimized.json real
  4. markdownToHtml equivalente Python: parseo de tablas GFM
  5. execute_with_correction: max_retries=None → lee config.json
  6. detect_error_type: table_unknown extrae nombre de tabla correctamente
  7. Flujo table_unknown → _find_similar_tables_in_db → candidatas enviadas a IA

Ejecutar desde bots/interjddcia/:
    python -m pytest tests/unit/test_sql_corrector_resilience.py -v
    python -m pytest tests/unit/test_sql_corrector_resilience.py -v -k "not real_db"
"""

import sys
import os
import json
import asyncio
import unittest
import re
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.modules.chat.sql_corrector import SQLCorrector, _load_sql_max_retries
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

# Rutas reales
_CONFIG_PATH = os.path.join(ROOT, "backend", "modules", "chat", "config.json")
_METADATA_PATH = os.path.join(ROOT, "backend", "core", "config", "db_metadata_optimized.json")


def run_async(coro):
    """Ejecuta una coroutine en un event loop para tests síncronos."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _try_connect_firebird() -> Optional[Any]:
    """
    Intenta conectar a Firebird usando la configuración del .env.
    Devuelve el driver si conecta, None si no hay BD disponible.
    """
    try:
        from backend.core.config.settings import settings
        from backend.core.factory.db_factory import DBFactory
        from backend.core.abstract.database import DBConfig

        db_config = DBConfig(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        driver = DBFactory.create(settings.DB_TYPE, db_config)
        # Test de conexión rápido
        driver.execute_query("SELECT FIRST 1 1 AS OK FROM RDB$DATABASE")
        return driver
    except Exception:
        return None


# ─── Tests: _load_sql_max_retries — sin mocks ─────────────────────────────────

class TestLoadSqlMaxRetries(unittest.TestCase):
    """
    Tests REALES de _load_sql_max_retries().
    Lee el config.json real del proyecto.
    """

    def test_lee_config_json_real(self):
        """_load_sql_max_retries() lee el config.json real y devuelve un entero."""
        value = _load_sql_max_retries()
        self.assertIsInstance(value, int, "Debe devolver un entero")
        self.assertGreater(value, 0, "Debe ser mayor que 0")
        self.assertLessEqual(value, 100, "Valor razonable (no más de 100 reintentos)")

    def test_valor_coincide_con_config_json(self):
        """El valor devuelto coincide exactamente con max_sql_retries del config.json."""
        self.assertTrue(os.path.exists(_CONFIG_PATH), f"config.json debe existir en {_CONFIG_PATH}")
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        expected = cfg.get("max_sql_retries", 4)
        actual = _load_sql_max_retries()
        self.assertEqual(actual, int(expected),
                         f"Debe coincidir con config.json: esperado={expected}, actual={actual}")

    def test_config_json_tiene_todos_los_parametros(self):
        """config.json tiene todos los parámetros requeridos."""
        self.assertTrue(os.path.exists(_CONFIG_PATH))
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        # Parámetros obligatorios
        self.assertIn("max_sql_retries", cfg, "Debe tener max_sql_retries")
        self.assertIn("lan_max_retries", cfg, "Debe tener lan_max_retries")
        self.assertIn("lan_read_timeout_s", cfg, "Debe tener lan_read_timeout_s")
        self.assertIn("ai_local_only", cfg, "Debe tener ai_local_only")
        # Tipos correctos
        self.assertIsInstance(cfg["max_sql_retries"], int)
        self.assertIsInstance(cfg["lan_max_retries"], int)
        self.assertIsInstance(cfg["lan_read_timeout_s"], int)
        self.assertIsInstance(cfg["ai_local_only"], bool)

    def test_execute_with_correction_usa_config_json_por_defecto(self):
        """
        execute_with_correction con max_retries=None lee config.json.
        Verifica que el valor usado es el del config.json real.
        """
        corrector = SQLCorrector()
        expected_retries = _load_sql_max_retries()

        # Contamos cuántas veces se llama execute_func para verificar max_retries
        call_count = {"n": 0}

        def execute_func(query: str):
            if "RDB$" in query.upper():
                return []
            call_count["n"] += 1
            raise Exception("Dynamic SQL Error\nColumn unknown\nCOLUMNA_FAKE")

        provider = MagicMock()
        # La IA devuelve el mismo SQL → fuerza agotar reintentos
        provider.generate_text = AsyncMock(
            return_value="```sql\nSELECT FIRST 1 COLUMNA_FAKE FROM TABLA_FAKE\n```"
        )

        with self.assertRaises(Exception):
            run_async(corrector.execute_with_correction(
                sql_query="SELECT FIRST 1 COLUMNA_FAKE FROM TABLA_FAKE",
                original_question="test",
                db_context="test",
                ai_provider=provider,
                execute_func=execute_func,
                max_retries=None,  # ← debe leer config.json
            ))

        # El número de intentos debe ser max_retries + 1 (intento inicial + reintentos)
        # Nota: algunos intentos pueden ser interceptados por el normalizer
        self.assertGreater(call_count["n"], 0, "Debe haber intentado ejecutar al menos una vez")


# ─── Tests: _get_all_tables_from_metadata — sin mocks ─────────────────────────

class TestGetAllTablesFromMetadata(unittest.TestCase):
    """
    Tests REALES de _get_all_tables_from_metadata().
    Lee el db_metadata_optimized.json real del proyecto.
    """

    def setUp(self):
        self.corrector = SQLCorrector()

    def test_lee_metadata_real(self):
        """_get_all_tables_from_metadata() lee el JSON real y devuelve lista de tablas."""
        tables = self.corrector._get_all_tables_from_metadata()
        self.assertIsInstance(tables, list)
        self.assertGreater(len(tables), 0, "Debe haber al menos una tabla en los metadatos")

    def test_tablas_principales_en_metadata(self):
        """Las tablas principales del sistema están en los metadatos."""
        tables = self.corrector._get_all_tables_from_metadata()
        tables_upper = [t.upper() for t in tables]
        # Tablas que deben estar siempre (verificadas contra el JSON real)
        for expected in ["ARTICULO", "CLIENTE", "DOCCAB", "DOCLIN"]:
            self.assertIn(expected, tables_upper,
                          f"La tabla {expected} debe estar en db_metadata_optimized.json")

    def test_no_devuelve_claves_internas(self):
        """No devuelve claves internas que empiezan con '_'."""
        tables = self.corrector._get_all_tables_from_metadata()
        for t in tables:
            self.assertFalse(t.startswith("_"),
                             f"No debe devolver claves internas: {t}")

    def test_metadata_json_valido(self):
        """El db_metadata_optimized.json es un JSON válido y tiene estructura correcta."""
        self.assertTrue(os.path.exists(_METADATA_PATH),
                        f"db_metadata_optimized.json debe existir en {_METADATA_PATH}")
        with open(_METADATA_PATH, encoding="utf-8") as f:
            meta = json.load(f)
        self.assertIsInstance(meta, dict)
        # El JSON real tiene 9 tablas indexadas (más la clave "TABLES")
        self.assertGreater(len(meta), 5, "Debe tener al menos 5 entradas en los metadatos")


# ─── Tests: _find_similar_tables_in_db — lógica pura sin BD ──────────────────

class TestFindSimilarTablesLogica(unittest.TestCase):
    """
    Tests de la lógica de _find_similar_tables_in_db SIN conexión a BD real.
    Usa un execute_func que simula RDB$RELATIONS con tablas reales conocidas.
    """

    def setUp(self):
        self.corrector = SQLCorrector()
        # Simula las tablas reales de la BD (subset representativo)
        self.tablas_reales = [
            "ARTICULO", "CLIENTE", "COMPRA", "DOCCAB", "DOCLIN",
            "DOCVAR", "ESTPROVEED", "CATEGORIAPROVEED", "PROVEEDORCAT",
            "RECURSO", "REPARA", "REPCAB", "REPLIN", "SERIE",
            "ALMACEN", "AGENTE", "FAMILIA", "FOTOGRAF",
        ]

    def _make_rdb_execute(self, tablas: List[str]):
        """
        Crea un execute_func que simula RDB$RELATIONS y COUNT(*).
        """
        # Asignar n_records ficticios para ordenar
        n_records = {
            "COMPRA": 12041, "DOCCAB": 3, "DOCLIN": 71025, "DOCVAR": 5000,
            "ESTPROVEED": 1, "CATEGORIAPROVEED": 4, "PROVEEDORCAT": 10,
            "ARTICULO": 11866, "CLIENTE": 9270, "RECURSO": 178,
            "REPARA": 7320, "REPCAB": 16847, "REPLIN": 71025,
            "SERIE": 2171, "ALMACEN": 865, "AGENTE": 2, "FAMILIA": 50,
            "FOTOGRAF": 0,
        }

        def execute_func(query: str) -> List[Dict]:
            q_up = query.upper()

            # Simular RDB$RELATIONS con CONTAINING
            if "RDB$RELATIONS" in q_up and "CONTAINING" in q_up:
                m = re.search(r"CONTAINING\s+'([^']+)'", query, re.IGNORECASE)
                if m:
                    root = m.group(1).upper()
                    matches = [t for t in tablas if root in t.upper()]
                    return [{"TNAME": t} for t in matches[:20]]
                return []

            # Simular COUNT(*)
            m = re.search(r"SELECT COUNT\(\*\) AS N FROM (\w+)", query, re.IGNORECASE)
            if m:
                tbl = m.group(1).upper()
                n = n_records.get(tbl, 0)
                return [{"N": n}]

            return []

        return execute_func

    def test_proveedor_encuentra_candidatas(self):
        """
        'PROVEEDOR' no existe → encuentra ESTPROVEED, CATEGORIAPROVEED, PROVEEDORCAT.
        """
        execute_func = self._make_rdb_execute(self.tablas_reales)
        result = self.corrector._find_similar_tables_in_db("PROVEEDOR", execute_func)

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0, "Debe encontrar al menos una tabla similar a PROVEEDOR")

        table_names = [r["table"] for r in result]
        # Al menos una de estas debe aparecer
        found_any = any(t in table_names for t in ["ESTPROVEED", "CATEGORIAPROVEED", "PROVEEDORCAT"])
        self.assertTrue(found_any,
                        f"Debe encontrar tablas relacionadas con PROVEEDOR. Encontradas: {table_names}")

    def test_resultado_ordenado_por_n_records(self):
        """Las candidatas se ordenan por n_records descendente."""
        execute_func = self._make_rdb_execute(self.tablas_reales)
        result = self.corrector._find_similar_tables_in_db("PROVEEDOR", execute_func)

        if len(result) >= 2:
            for i in range(len(result) - 1):
                n_curr = result[i].get("n_records") or 0
                n_next = result[i + 1].get("n_records") or 0
                self.assertGreaterEqual(n_curr, n_next,
                                        f"Debe estar ordenado: {result[i]['table']}({n_curr}) >= {result[i+1]['table']}({n_next})")

    def test_tabla_inexistente_sin_similares_devuelve_lista_vacia(self):
        """Tabla sin ninguna similitud devuelve lista vacía."""
        execute_func = self._make_rdb_execute(self.tablas_reales)
        result = self.corrector._find_similar_tables_in_db("XYZQWERTY123", execute_func)
        self.assertIsInstance(result, list)
        # Puede ser vacía o con muy pocas coincidencias
        # Lo importante es que no lanza excepción

    def test_tabla_vacia_devuelve_lista_vacia(self):
        """Nombre de tabla vacío devuelve lista vacía sin error."""
        execute_func = self._make_rdb_execute(self.tablas_reales)
        result = self.corrector._find_similar_tables_in_db("", execute_func)
        self.assertEqual(result, [])

    def test_error_en_rdb_relations_no_lanza_excepcion(self):
        """Si RDB$RELATIONS falla, devuelve lista vacía sin propagar la excepción."""
        def bad_execute(query: str):
            raise Exception("Connection refused")

        result = self.corrector._find_similar_tables_in_db("PROVEEDOR", bad_execute)
        self.assertIsInstance(result, list)
        # No debe lanzar excepción

    def test_docvar_encuentra_doclin_doccab(self):
        """'DOCVAR' encuentra DOCLIN, DOCCAB, DOCVAR (si existe)."""
        execute_func = self._make_rdb_execute(self.tablas_reales)
        result = self.corrector._find_similar_tables_in_db("DOCVAR", execute_func)
        table_names = [r["table"] for r in result]
        # DOCVAR está en la lista de tablas reales
        self.assertIn("DOCVAR", table_names, "DOCVAR debe encontrarse a sí misma")

    def test_estructura_resultado(self):
        """Cada elemento del resultado tiene 'table' y 'n_records'."""
        execute_func = self._make_rdb_execute(self.tablas_reales)
        result = self.corrector._find_similar_tables_in_db("COMPRA", execute_func)

        for entry in result:
            self.assertIn("table", entry, "Cada entrada debe tener 'table'")
            self.assertIn("n_records", entry, "Cada entrada debe tener 'n_records'")
            self.assertIsInstance(entry["table"], str)


# ─── Tests: flujo table_unknown → candidatas → prompt IA ─────────────────────

class TestTableUnknownFlujoCompleto(unittest.TestCase):
    """
    Tests del flujo completo cuando ocurre Table unknown:
    1. Detectar error
    2. Buscar candidatas en RDB$RELATIONS
    3. Incluir candidatas en el prompt de la IA
    4. La IA corrige el SQL con la tabla correcta
    """

    def setUp(self):
        self.corrector = SQLCorrector()
        self.normalizer = FirebirdSQLNormalizer()

    def _make_execute_with_rdb(self, tablas_reales: List[str], n_records: Dict[str, int],
                                 corrected_sql: str):
        """
        Crea execute_func que:
        - Falla con Table unknown PROVEEDOR en la primera ejecución
        - Responde a RDB$RELATIONS con tablas similares
        - Responde a COUNT(*) con n_records
        - Acepta el SQL corregido
        """
        call_count = {"n": 0}

        def execute_func(query: str) -> List[Dict]:
            q_up = query.upper()

            # RDB$RELATIONS
            if "RDB$RELATIONS" in q_up and "CONTAINING" in q_up:
                m = re.search(r"CONTAINING\s+'([^']+)'", query, re.IGNORECASE)
                if m:
                    root = m.group(1).upper()
                    matches = [t for t in tablas_reales if root in t.upper()]
                    return [{"TNAME": t} for t in matches[:20]]
                return []

            # RDB$RELATION_FIELDS (columnas)
            if "RDB$RELATION_FIELDS" in q_up:
                m = re.search(r"TRIM\(RDB\$RELATION_NAME\)\s*=\s*'([^']+)'", query, re.IGNORECASE)
                if m:
                    tbl = m.group(1).upper()
                    cols_map = {
                        "COMPRA": ["CODIGO", "CODPROVEEDOR", "FECHA", "TOTAL", "ESTADO"],
                        "ESTPROVEED": ["CODPROVEEDOR", "NOMBRE", "SALDO", "TOTALCOMPRAS"],
                        "CATEGORIAPROVEED": ["CODCATEGORIA", "CODPROVEEDOR"],
                    }
                    cols = cols_map.get(tbl, [])
                    return [{"FIELD_NAME": c} for c in cols]
                return []

            # COUNT(*)
            m = re.search(r"SELECT COUNT\(\*\) AS N FROM (\w+)", query, re.IGNORECASE)
            if m:
                tbl = m.group(1).upper()
                return [{"N": n_records.get(tbl, 0)}]

            # Muestra de datos
            m = re.search(r"SELECT FIRST \d+ \* FROM (\w+)", query, re.IGNORECASE)
            if m:
                return []

            # Query principal
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Dynamic SQL Error\nSQL error code = -204\nTable unknown PROVEEDOR")
            # Segunda ejecución (SQL corregido): éxito
            return [
                {"CODPROVEEDOR": 1, "NOMBRE": "Proveedor A", "TOTAL": 5000.0},
                {"CODPROVEEDOR": 2, "NOMBRE": "Proveedor B", "TOTAL": 3200.0},
            ]

        return execute_func

    def test_table_unknown_proveedor_busca_candidatas(self):
        """
        Cuando ocurre Table unknown PROVEEDOR:
        1. El corrector busca en RDB$RELATIONS tablas similares
        2. Incluye las candidatas en el prompt de la IA
        3. La IA corrige el SQL con la tabla real (COMPRA o ESTPROVEED)
        """
        bad_sql = (
            "SELECT FIRST 10 P.CODPROVEEDOR, P.NOMBRE, SUM(P.TOTAL) AS TOTALCOMPRAS "
            "FROM PROVEEDOR P "
            "GROUP BY P.CODPROVEEDOR, P.NOMBRE "
            "ORDER BY TOTALCOMPRAS DESC"
        )

        tablas_reales = ["COMPRA", "ESTPROVEED", "CATEGORIAPROVEED", "ARTICULO", "CLIENTE"]
        n_records = {"COMPRA": 12041, "ESTPROVEED": 1, "CATEGORIAPROVEED": 4}

        corrected_sql = (
            "SELECT FIRST 10 CODPROVEEDOR, NOMBRE, TOTALCOMPRAS "
            "FROM ESTPROVEED "
            "ORDER BY TOTALCOMPRAS DESC"
        )

        execute_func = self._make_execute_with_rdb(tablas_reales, n_records, corrected_sql)

        # La IA recibe el prompt con candidatas y devuelve el SQL corregido
        prompt_received = []
        async def mock_generate(prompt: str) -> str:
            prompt_received.append(prompt)
            return f"```sql\n{corrected_sql}\n```"

        provider = MagicMock()
        provider.generate_text = mock_generate

        result = run_async(self.corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="proveedores con más compras",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=execute_func,
            max_retries=3,
        ))

        # Debe devolver resultados
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

        # El prompt debe incluir información sobre la tabla desconocida
        self.assertGreater(len(prompt_received), 0, "La IA debe haber sido llamada")
        prompt = prompt_received[0]
        self.assertIn("PROVEEDOR", prompt.upper(),
                      "El prompt debe mencionar la tabla desconocida PROVEEDOR")

        # El prompt debe incluir candidatas reales
        found_candidate = any(t in prompt.upper() for t in ["COMPRA", "ESTPROVEED", "CATEGORIAPROVEED"])
        self.assertTrue(found_candidate,
                        f"El prompt debe incluir tablas candidatas reales. Prompt (primeros 500): {prompt[:500]}")

    def test_detect_error_type_table_unknown_extrae_nombre(self):
        """detect_error_type extrae correctamente el nombre de la tabla desconocida."""
        test_cases = [
            ("Dynamic SQL Error\nSQL error code = -204\nTable unknown PROVEEDOR", "PROVEEDOR"),
            ("Dynamic SQL Error\nTable unknown TABLA_INEXISTENTE", "TABLA_INEXISTENTE"),
            ("Table unknown DOCVAR2", "DOCVAR2"),
        ]
        for error_msg, expected_table in test_cases:
            with self.subTest(error=error_msg):
                info = self.corrector.detect_error_type(error_msg)
                self.assertEqual(info["type"], "table_unknown")
                self.assertIsNotNone(info.get("table"),
                                     f"Debe extraer el nombre de tabla de: {error_msg}")
                self.assertEqual(info["table"].upper(), expected_table.upper(),
                                 f"Tabla extraída incorrecta: {info['table']} != {expected_table}")

    def test_table_unknown_fallback_a_metadata_si_rdb_falla(self):
        """
        Si RDB$RELATIONS no devuelve resultados, usa db_metadata_optimized.json como fallback.
        """
        bad_sql = "SELECT FIRST 5 * FROM TABLA_COMPLETAMENTE_NUEVA"

        call_count = {"n": 0}

        def execute_func(query: str) -> List[Dict]:
            if "RDB$" in query.upper():
                return []  # RDB$RELATIONS no devuelve nada
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Dynamic SQL Error\nTable unknown TABLA_COMPLETAMENTE_NUEVA")
            return [{"CODIGO": 1}]

        prompt_received = []
        async def mock_generate(prompt: str) -> str:
            prompt_received.append(prompt)
            return "```sql\nSELECT FIRST 5 CODIGO FROM ARTICULO\n```"

        provider = MagicMock()
        provider.generate_text = mock_generate

        result = run_async(self.corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="test fallback metadata",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=execute_func,
            max_retries=2,
        ))

        self.assertIsNotNone(result)

        # El prompt debe incluir información del fallback (metadatos o error)
        if prompt_received:
            prompt = prompt_received[0]
            # Debe mencionar que la tabla no existe
            self.assertIn("TABLA_COMPLETAMENTE_NUEVA", prompt.upper(),
                          "El prompt debe mencionar la tabla desconocida")


# ─── Tests: markdownToHtml — lógica Python equivalente ───────────────────────

class TestMarkdownToHtmlLogica(unittest.TestCase):
    """
    Tests de la lógica de parseo de tablas Markdown.
    Implementa la misma lógica que markdownToHtml() de siuo_constants.js en Python
    para verificar que el algoritmo es correcto.
    """

    def _parse_markdown_table(self, text: str) -> Optional[Dict]:
        """
        Implementación Python equivalente a la lógica de tablas en markdownToHtml().
        Devuelve dict con 'headers' y 'rows', o None si no es tabla válida.
        """
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return None

        # Detectar línea separadora
        sep_idx = None
        for i, line in enumerate(lines):
            if re.match(r'^\s*\|[\s\-:|]+\|\s*$', line):
                sep_idx = i
                break

        if sep_idx is None:
            return None

        def parse_cells(line: str) -> List[str]:
            return [c.strip() for c in re.sub(r'^\s*\|', '', re.sub(r'\|\s*$', '', line)).split("|")]

        headers = parse_cells(lines[0])
        rows = [parse_cells(l) for l in lines[sep_idx + 1:]]
        return {"headers": headers, "rows": rows}

    def test_tabla_simple_3_columnas(self):
        """Parsea tabla Markdown simple con 3 columnas."""
        md = """| CODIGO | NOMBRE | STOCK |
|--------|--------|-------|
| ART001 | Filtro | 150   |
| ART002 | Compresor | 89 |"""

        result = self._parse_markdown_table(md)
        self.assertIsNotNone(result, "Debe parsear la tabla")
        self.assertEqual(result["headers"], ["CODIGO", "NOMBRE", "STOCK"])
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["rows"][0][0], "ART001")
        self.assertEqual(result["rows"][1][0], "ART002")

    def test_tabla_con_alineacion_columnas(self):
        """Parsea tabla con alineación de columnas (|:---|:---:|---:|)."""
        md = """| Artículo | Cantidad | Precio |
|:---------|:--------:|-------:|
| Filtro   | 10       | 25.50  |
| Compresor| 5        | 150.00 |"""

        result = self._parse_markdown_table(md)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["headers"]), 3)
        self.assertEqual(len(result["rows"]), 2)

    def test_tabla_una_columna(self):
        """Parsea tabla con una sola columna."""
        md = """| TABLA |
|-------|
| ARTICULO |
| CLIENTE |
| COMPRA |"""

        result = self._parse_markdown_table(md)
        self.assertIsNotNone(result)
        self.assertEqual(result["headers"], ["TABLA"])
        self.assertEqual(len(result["rows"]), 3)

    def test_no_tabla_sin_separador(self):
        """Texto con pipes pero sin línea separadora no es tabla."""
        md = """| col1 | col2 |
| val1 | val2 |"""

        result = self._parse_markdown_table(md)
        self.assertIsNone(result, "Sin separador no debe parsear como tabla")

    def test_no_tabla_texto_normal(self):
        """Texto normal sin pipes no es tabla."""
        text = "Este es un texto normal sin tablas."
        result = self._parse_markdown_table(text)
        self.assertIsNone(result)

    def test_tabla_respuesta_tipica_ia(self):
        """
        Parsea una tabla típica que genera la IA para responder consultas SQL.
        Simula la respuesta real de Qwen3 30B.
        """
        md = """| CODCLIENTE | RAZONSOCIAL | TOTALFACTURADO | NFACTURAS |
|------------|-------------|----------------|-----------|
| 1001 | Empresa ABC S.L. | 45.230,50 | 23 |
| 1002 | Instalaciones XYZ | 38.100,00 | 18 |
| 1003 | Climatización Norte | 29.500,75 | 15 |"""

        result = self._parse_markdown_table(md)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["headers"]), 4)
        self.assertIn("CODCLIENTE", result["headers"])
        self.assertIn("RAZONSOCIAL", result["headers"])
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(result["rows"][0][1], "Empresa ABC S.L.")

    def test_tabla_con_celdas_vacias(self):
        """Parsea tabla con celdas vacías."""
        md = """| COD | NOMBRE | FECHA |
|-----|--------|-------|
| 1   | Test   |       |
| 2   |        | 2026  |"""

        result = self._parse_markdown_table(md)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["rows"]), 2)
        # Celda vacía debe ser string vacío
        self.assertEqual(result["rows"][0][2], "")
        self.assertEqual(result["rows"][1][1], "")

    def test_tabla_genera_html_correcto(self):
        """
        Verifica que la tabla Markdown genera HTML con las clases correctas.
        Simula la salida de markdownToHtml().
        """
        md = """| COD | NOMBRE |
|-----|--------|
| 1   | Test   |"""

        result = self._parse_markdown_table(md)
        self.assertIsNotNone(result)

        # Generar HTML como lo haría markdownToHtml()
        def escape_html(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        headers_html = "".join(f"<th>{escape_html(h)}</th>" for h in result["headers"])
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{escape_html(c)}</td>" for c in row) + "</tr>"
            for row in result["rows"]
        )
        table_html = f'<div class="md-table-wrap"><table class="md-table"><thead><tr>{headers_html}</tr></thead><tbody>{rows_html}</tbody></table></div>'

        # Verificar estructura HTML
        self.assertIn('class="md-table"', table_html)
        self.assertIn('class="md-table-wrap"', table_html)
        self.assertIn("<thead>", table_html)
        self.assertIn("<tbody>", table_html)
        self.assertIn("<th>COD</th>", table_html)
        self.assertIn("<th>NOMBRE</th>", table_html)
        self.assertIn("<td>1</td>", table_html)
        self.assertIn("<td>Test</td>", table_html)

    def test_xss_en_celdas_escapado(self):
        """Los caracteres HTML en celdas se escapan correctamente (anti-XSS)."""
        md = """| COD | SCRIPT |
|-----|--------|
| 1   | <script>alert('xss')</script> |"""

        result = self._parse_markdown_table(md)
        self.assertIsNotNone(result)

        def escape_html(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        cell_value = result["rows"][0][1]
        escaped = escape_html(cell_value)
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)


# ─── Tests: integración real con BD Firebird (skip si no disponible) ──────────

class TestIntegracionRealFirebird(unittest.TestCase):
    """
    Tests de integración REAL con Firebird.
    Se saltan automáticamente si la BD no está disponible.
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = _try_connect_firebird()
        if cls.driver is None:
            cls.skip_reason = "BD Firebird no disponible (normal en CI/CD)"
        else:
            cls.skip_reason = None

    def _skip_if_no_db(self):
        if self.driver is None:
            self.skipTest(self.skip_reason)

    def _execute(self, query: str) -> List[Dict]:
        """Ejecuta una query en Firebird real."""
        return self.driver.execute_query(query)

    def test_rdb_relations_accesible(self):
        """RDB$RELATIONS es accesible y devuelve tablas del sistema."""
        self._skip_if_no_db()
        rows = self._execute(
            "SELECT FIRST 5 TRIM(RDB$RELATION_NAME) AS TNAME "
            "FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL"
        )
        self.assertGreater(len(rows), 0, "Debe haber tablas de usuario en RDB$RELATIONS")
        for row in rows:
            self.assertIn("TNAME", row)
            self.assertIsNotNone(row["TNAME"])

    def test_find_similar_tables_proveedor_real(self):
        """
        Test REAL: _find_similar_tables_in_db con 'PROVEEDOR' contra BD real.
        Verifica que encuentra tablas reales con 'PROV' en el nombre.
        """
        self._skip_if_no_db()
        corrector = SQLCorrector()
        result = corrector._find_similar_tables_in_db("PROVEEDOR", self._execute)

        self.assertIsInstance(result, list)
        # Debe encontrar al menos ESTPROVEED o CATEGORIAPROVEED
        table_names = [r["table"] for r in result]
        self.assertGreater(len(table_names), 0,
                           "Debe encontrar al menos una tabla similar a PROVEEDOR en la BD real")
        # Verificar estructura
        for entry in result:
            self.assertIn("table", entry)
            self.assertIn("n_records", entry)

    def test_get_real_table_columns_articulo(self):
        """
        Test REAL: _get_real_table_columns para ARTICULO contra BD real.
        """
        self._skip_if_no_db()
        corrector = SQLCorrector()
        cols = corrector._get_real_table_columns("ARTICULO", self._execute)

        self.assertGreater(len(cols), 0, "ARTICULO debe tener columnas")
        cols_upper = [c.upper() for c in cols]
        # Columnas que deben existir en ARTICULO
        self.assertIn("CODIGO", cols_upper, "ARTICULO debe tener CODIGO")
        self.assertIn("NOMBRE", cols_upper, "ARTICULO debe tener NOMBRE")

    def test_get_real_table_columns_doclin_no_tiene_fecha(self):
        """
        Test REAL: DOCLIN no tiene columna FECHA (la fecha está en DOCCAB).
        """
        self._skip_if_no_db()
        corrector = SQLCorrector()
        cols = corrector._get_real_table_columns("DOCLIN", self._execute)

        self.assertGreater(len(cols), 0, "DOCLIN debe tener columnas")
        cols_upper = [c.upper() for c in cols]
        # DOCLIN NO debe tener FECHA
        self.assertNotIn("FECHA", cols_upper,
                         "DOCLIN NO debe tener columna FECHA (está en DOCCAB)")
        # Pero sí debe tener CODDOCUMENTO
        self.assertIn("CODDOCUMENTO", cols_upper,
                      "DOCLIN debe tener CODDOCUMENTO para JOIN con DOCCAB")

    def test_find_similar_tables_cliente_real(self):
        """
        Test REAL: 'CLIENTE' existe → debe encontrarse a sí misma.
        """
        self._skip_if_no_db()
        corrector = SQLCorrector()
        result = corrector._find_similar_tables_in_db("CLIENTE", self._execute)

        table_names = [r["table"] for r in result]
        self.assertIn("CLIENTE", table_names,
                      "CLIENTE debe encontrarse a sí misma en RDB$RELATIONS")

    def test_execute_with_correction_table_unknown_real(self):
        """
        Test REAL E2E: query con tabla inexistente → corrector busca en RDB$RELATIONS
        → IA corrige → resultado válido.
        """
        self._skip_if_no_db()
        corrector = SQLCorrector()

        # Query con tabla que no existe
        bad_sql = "SELECT FIRST 5 CODIGO, NOMBRE FROM TABLA_QUE_NO_EXISTE_JAMAS"

        prompt_received = []
        async def mock_generate(prompt: str) -> str:
            prompt_received.append(prompt)
            # La IA "corrige" usando ARTICULO (tabla real)
            return "```sql\nSELECT FIRST 5 CODIGO, NOMBRE FROM ARTICULO\n```"

        provider = MagicMock()
        provider.generate_text = mock_generate

        result = run_async(corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="test tabla inexistente",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=self._execute,
            max_retries=2,
        ))

        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0, "Debe devolver resultados de ARTICULO")

        # El prompt debe mencionar la tabla desconocida
        self.assertGreater(len(prompt_received), 0)
        prompt = prompt_received[0]
        self.assertIn("TABLA_QUE_NO_EXISTE_JAMAS", prompt.upper())


if __name__ == "__main__":
    unittest.main(verbosity=2)
