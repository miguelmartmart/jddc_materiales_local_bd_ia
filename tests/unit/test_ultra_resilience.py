"""
tests/unit/test_ultra_resilience.py
Tests ultra-resilientes: flujo completo de la pantalla "Probar ContextRetriever"
con tablas no indexadas, fallos SQL reales y auto-corrección.

Cubre:
  1. Normalizer paso 20: DOCLIN.FECHA → JOIN DOCCAB
  2. fix_after_error con column_unknown FECHA en DOCLIN
  3. SQLCorrector._extract_tables_from_sql con queries complejas
  4. SQLCorrector._find_date_columns detecta columnas de fecha
  5. execute_with_correction: flujo completo con mock de BD que falla y luego corrige
  6. Tablas no indexadas: el corrector consulta metadatos reales y aprende
  7. Tablas con pocos registros: advertencia LOW_RECORD_TABLES
  8. Corrección encadenada: falla 1 → determinista → falla 2 → IA → éxito

Ejecutar desde bots/interjddcia/:
    python -m pytest tests/unit/test_ultra_resilience.py -v
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import List, Dict, Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.chat.sql_corrector import SQLCorrector
from backend.modules.chat.firebird_sql_constants import LOW_RECORD_TABLES, TABLE_DATE_COLUMNS


# ─── Helpers ──────────────────────────────────────────────────────────────────

def run_async(coro):
    """Ejecuta una coroutine en un event loop para tests síncronos."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── Tests: Paso 20 — DOCLIN.FECHA → JOIN DOCCAB ─────────────────────────────

class TestDoclinFechaJoinDoccab(unittest.TestCase):
    """Paso 20 del normalizer: DOCLIN no tiene FECHA, la fecha está en DOCCAB."""

    def setUp(self):
        self.n = FirebirdSQLNormalizer()

    def _norm(self, sql):
        result, changes = self.n.normalize(sql)
        return result, changes

    def test_l_fecha_en_doclin_añade_join_doccab(self):
        """L.FECHA en query con DOCLIN → añade JOIN DOCCAB C y sustituye L.FECHA por C.FECHA."""
        sql = (
            "SELECT FIRST 5 A.CODIGO, A.NOMBRE, COUNT(*) AS NCOMPRAS "
            "FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO = A.CODIGO "
            "WHERE EXTRACT(MONTH FROM L.FECHA) = EXTRACT(MONTH FROM CURRENT_DATE) "
            "AND EXTRACT(YEAR FROM L.FECHA) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY NCOMPRAS DESC"
        )
        out, changes = self._norm(sql)
        out_up = out.upper()
        # Debe añadir JOIN DOCCAB
        self.assertIn("DOCCAB", out_up, "Debe añadir JOIN DOCCAB")
        # L.FECHA debe sustituirse por C.FECHA
        self.assertNotIn("L.FECHA", out_up, "L.FECHA debe desaparecer")
        self.assertIn("C.FECHA", out_up, "C.FECHA debe aparecer")
        # Debe reportar el cambio
        self.assertTrue(
            any("DOCCAB" in c.upper() or "FECHA" in c.upper() for c in changes),
            f"Debe reportar cambio de FECHA. Cambios: {changes}"
        )

    def test_doclin_fecha_explicito_sustituido(self):
        """DOCLIN.FECHA explícito → C.FECHA."""
        sql = (
            "SELECT FIRST 10 CODDOCUMENTO, CODIGO "
            "FROM DOCLIN WHERE DOCLIN.FECHA >= '2026-01-01'"
        )
        out, changes = self._norm(sql)
        out_up = out.upper()
        self.assertNotIn("DOCLIN.FECHA", out_up)
        self.assertIn("C.FECHA", out_up)

    def test_sin_doclin_no_modifica(self):
        """Sin DOCLIN en la query, no se aplica el paso 20."""
        sql = (
            "SELECT FIRST 10 CODIGO, FECHA FROM DOCCAB "
            "WHERE EXTRACT(MONTH FROM FECHA) = EXTRACT(MONTH FROM CURRENT_DATE)"
        )
        out, changes = self._norm(sql)
        # No debe añadir JOIN DOCCAB extra (ya está en DOCCAB)
        self.assertNotIn("JOIN DOCCAB", out.upper())

    def test_fix_after_error_column_unknown_fecha_doclin(self):
        """fix_after_error con 'Column unknown FECHA' en query con DOCLIN → JOIN DOCCAB."""
        sql = (
            "SELECT FIRST 5 A.CODIGO, A.NOMBRE, COUNT(*) AS NCOMPRAS "
            "FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO = A.CODIGO "
            "WHERE EXTRACT(MONTH FROM L.FECHA) = EXTRACT(MONTH FROM CURRENT_DATE) "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY NCOMPRAS DESC"
        )
        error = (
            "Dynamic SQL Error\nSQL error code = -206\n"
            "Column unknown\nL.FECHA\nAt line 4, column 28"
        )
        out, changes = self.n.fix_after_error(sql, error)
        out_up = out.upper()
        self.assertIn("DOCCAB", out_up, "Debe añadir JOIN DOCCAB tras error column_unknown FECHA")
        self.assertNotIn("L.FECHA", out_up, "L.FECHA debe desaparecer")
        self.assertTrue(len(changes) > 0, "Debe reportar cambios")

    def test_query_exacta_del_error_reportado(self):
        """
        Reproduce exactamente el error reportado por el usuario:
        'artículos con más compras, este mes' → L.FECHA no existe en DOCLIN.
        """
        # Esta es la query exacta que generó la IA y falló
        sql = (
            "SELECT FIRST 5 A.CODIGO, A.NOMBRE, COUNT(*) AS NCOMPRAS "
            "FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO = A.CODIGO "
            "WHERE EXTRACT(MONTH FROM L.FECHA) = EXTRACT(MONTH FROM CURRENT_DATE) "
            "AND EXTRACT(YEAR FROM L.FECHA) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY NCOMPRAS DESC"
        )
        # El normalizer debe corregirla ANTES de ejecutar (paso 20)
        out, changes = self.n.normalize(sql)
        out_up = out.upper()

        # Verificaciones clave
        self.assertIn("DOCCAB", out_up, "JOIN DOCCAB debe añadirse")
        self.assertNotIn("L.FECHA", out_up, "L.FECHA no debe existir en la query corregida")
        self.assertIn("C.FECHA", out_up, "C.FECHA debe usarse para el filtro de fecha")
        # La query debe seguir siendo válida (tiene GROUP BY, ORDER BY, FIRST 5)
        self.assertIn("GROUP BY", out_up)
        self.assertIn("ORDER BY", out_up)
        self.assertIn("FIRST 5", out_up)


# ─── Tests: SQLCorrector — extracción de tablas y columnas de fecha ───────────

class TestSQLCorrectorMetadata(unittest.TestCase):
    """Tests de los métodos de metadatos del SQLCorrector."""

    def setUp(self):
        self.corrector = SQLCorrector()

    def test_extract_tables_simple(self):
        """Extrae tablas de un SELECT simple."""
        sql = "SELECT FIRST 10 CODIGO FROM ARTICULO"
        tables = self.corrector._extract_tables_from_sql(sql)
        self.assertIn("ARTICULO", tables)

    def test_extract_tables_con_joins(self):
        """Extrae todas las tablas de un SELECT con múltiples JOINs."""
        sql = (
            "SELECT FIRST 5 A.CODIGO, A.NOMBRE, COUNT(*) AS N "
            "FROM ARTICULO A "
            "JOIN DOCLIN L ON L.CODIGO = A.CODIGO "
            "JOIN DOCCAB C ON C.CODIGO = L.CODDOCUMENTO "
            "WHERE C.TIPO = 13 "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N DESC"
        )
        tables = self.corrector._extract_tables_from_sql(sql)
        self.assertIn("ARTICULO", tables)
        self.assertIn("DOCLIN", tables)
        self.assertIn("DOCCAB", tables)

    def test_extract_tables_no_duplicados(self):
        """No devuelve tablas duplicadas."""
        sql = "SELECT FIRST 5 * FROM ARTICULO A JOIN ARTICULO B ON A.CODIGO = B.CODIGO"
        tables = self.corrector._extract_tables_from_sql(sql)
        self.assertEqual(tables.count("ARTICULO"), 1)

    def test_find_date_columns_detecta_fecha(self):
        """Detecta columnas de fecha por nombre."""
        cols = ["CODIGO", "NOMBRE", "FECHA", "FECHAENTREGA", "STOCKARTICULO"]
        date_cols = self.corrector._find_date_columns(cols)
        self.assertIn("FECHA", date_cols)
        self.assertIn("FECHAENTREGA", date_cols)
        self.assertNotIn("CODIGO", date_cols)
        self.assertNotIn("STOCKARTICULO", date_cols)

    def test_find_date_columns_sin_fecha(self):
        """Tabla sin columnas de fecha devuelve lista vacía."""
        cols = ["CODDOCUMENTO", "CODIGO", "DESCRIPCION", "IMPORTEDESCUENTO"]
        date_cols = self.corrector._find_date_columns(cols)
        self.assertEqual(date_cols, [])

    def test_doclin_no_tiene_fecha_en_constants(self):
        """TABLE_DATE_COLUMNS confirma que DOCLIN no tiene fecha propia."""
        self.assertIn("DOCLIN", TABLE_DATE_COLUMNS)
        self.assertFalse(TABLE_DATE_COLUMNS["DOCLIN"]["has_date"])
        self.assertIsNone(TABLE_DATE_COLUMNS["DOCLIN"]["date_col"])
        join_info = TABLE_DATE_COLUMNS["DOCLIN"]["date_via_join"]
        self.assertEqual(join_info["join_table"], "DOCCAB")
        self.assertEqual(join_info["date_col"], "DOCCAB.FECHA")

    def test_low_record_tables_contiene_doccab(self):
        """LOW_RECORD_TABLES contiene DOCCAB con advertencia."""
        self.assertIn("DOCCAB", LOW_RECORD_TABLES)
        self.assertIn("warning", LOW_RECORD_TABLES["DOCCAB"])
        self.assertIn("3", LOW_RECORD_TABLES["DOCCAB"]["warning"])


# ─── Tests: SQLCorrector — consulta metadatos reales (mock BD) ────────────────

class TestSQLCorrectorRealMetadata(unittest.TestCase):
    """Tests del corrector consultando metadatos reales (BD mockeada)."""

    def setUp(self):
        self.corrector = SQLCorrector()

    def _make_execute_func(self, columns_by_table: Dict[str, List[str]], sample_by_table: Dict[str, List[Dict]] = None):
        """
        Crea un execute_func mock que:
        - Para RDB$RELATION_FIELDS → devuelve columnas de la tabla
        - Para SELECT FIRST N * FROM tabla → devuelve muestra
        - Para cualquier otra query → lanza error de columna desconocida
        """
        sample_by_table = sample_by_table or {}

        def execute_func(query: str) -> List[Dict]:
            q_up = query.upper()

            # Consulta de metadatos RDB$
            if "RDB$RELATION_FIELDS" in q_up:
                # Extraer nombre de tabla del WHERE
                import re
                m = re.search(r"TRIM\(RDB\$RELATION_NAME\)\s*=\s*'([^']+)'", query, re.IGNORECASE)
                if m:
                    tbl = m.group(1).upper()
                    cols = columns_by_table.get(tbl, [])
                    return [{"FIELD_NAME": c} for c in cols]
                return []

            # Muestra de datos
            import re
            m = re.search(r"SELECT FIRST \d+ \* FROM (\w+)", query, re.IGNORECASE)
            if m:
                tbl = m.group(1).upper()
                return sample_by_table.get(tbl, [])

            # Query principal — falla con column_unknown
            raise Exception("Dynamic SQL Error\nSQL error code = -206\nColumn unknown\nFECHA\nAt line 1")

        return execute_func

    def test_get_real_table_columns_doclin(self):
        """_get_real_table_columns devuelve columnas reales de DOCLIN."""
        cols_mock = ["CODDOCUMENTO", "CODIGO", "DESCRIPCION", "FECHAENTREGA", "IMPORTEDESCUENTO"]
        execute_func = self._make_execute_func({"DOCLIN": cols_mock})

        result = self.corrector._get_real_table_columns("DOCLIN", execute_func)
        self.assertEqual(result, cols_mock)

    def test_get_real_table_columns_tabla_no_indexada(self):
        """
        Tabla no indexada (no en db_metadata_optimized.json):
        _get_real_table_columns la descubre consultando RDB$RELATION_FIELDS.
        """
        # HISTORICOPRECIOS es una tabla que puede no estar bien indexada
        cols_mock = ["CODARTICULO", "CODPROVEEDOR", "PRECIO", "FECHAMODIFICACION", "CANTIDAD"]
        execute_func = self._make_execute_func({"HISTORICOPRECIOS": cols_mock})

        result = self.corrector._get_real_table_columns("HISTORICOPRECIOS", execute_func)
        self.assertEqual(result, cols_mock)
        # Detectar columnas de fecha
        date_cols = self.corrector._find_date_columns(result)
        self.assertIn("FECHAMODIFICACION", date_cols)

    def test_get_real_table_sample(self):
        """_get_real_table_sample devuelve muestra de datos reales."""
        sample = [
            {"CODDOCUMENTO": 1001, "CODIGO": "ART001", "DESCRIPCION": "Filtro aire"},
            {"CODDOCUMENTO": 1002, "CODIGO": "ART002", "DESCRIPCION": "Compresor"},
        ]
        execute_func = self._make_execute_func({}, {"DOCLIN": sample})
        result = self.corrector._get_real_table_sample("DOCLIN", execute_func, limit=3)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["CODIGO"], "ART001")

    def test_get_real_table_columns_error_graceful(self):
        """Si la BD falla al consultar metadatos, devuelve lista vacía (no lanza excepción)."""
        def bad_execute(query):
            raise Exception("Connection refused")

        result = self.corrector._get_real_table_columns("CUALQUIER_TABLA", bad_execute)
        self.assertEqual(result, [])


# ─── Tests: execute_with_correction — flujo completo ultra-resiliente ─────────

class TestExecuteWithCorrectionUltraResilient(unittest.TestCase):
    """
    Tests del flujo completo de corrección automática.
    Simula el flujo real de la pantalla 'Probar ContextRetriever'.
    """

    def setUp(self):
        self.corrector = SQLCorrector()

    def _make_ai_provider(self, corrected_sql: str) -> MagicMock:
        """Mock de AI provider que devuelve el SQL corregido."""
        provider = MagicMock()
        provider.generate_text = AsyncMock(
            return_value=f"```sql\n{corrected_sql}\n```"
        )
        return provider

    def test_flujo_doclin_fecha_corregido_deterministicamente(self):
        """
        Flujo completo: query con L.FECHA en DOCLIN.
        El normalizer (paso 20) la corrige ANTES de ejecutar → no llega a fallar.
        """
        # Query que generaría la IA (con L.FECHA incorrecto)
        bad_sql = (
            "SELECT FIRST 5 A.CODIGO, A.NOMBRE, COUNT(*) AS NCOMPRAS "
            "FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO = A.CODIGO "
            "WHERE EXTRACT(MONTH FROM L.FECHA) = EXTRACT(MONTH FROM CURRENT_DATE) "
            "AND EXTRACT(YEAR FROM L.FECHA) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY NCOMPRAS DESC"
        )

        # El execute_func solo acepta queries con C.FECHA (corregidas)
        call_log = []
        def execute_func(query: str):
            call_log.append(query)
            if "L.FECHA" in query.upper():
                raise Exception("Column unknown\nL.FECHA")
            # Query corregida con C.FECHA → éxito
            return [
                {"CODIGO": "ART001", "NOMBRE": "Filtro aire", "NCOMPRAS": 150},
                {"CODIGO": "ART002", "NOMBRE": "Compresor", "NCOMPRAS": 89},
            ]

        provider = self._make_ai_provider("")
        result = run_async(self.corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="artículos con más compras este mes",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=execute_func,
            max_retries=3,
        ))

        # Debe devolver resultados
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        # La primera query ejecutada debe tener C.FECHA (corregida por normalizer)
        first_query = call_log[0].upper()
        self.assertNotIn("L.FECHA", first_query, "El normalizer debe haber corregido L.FECHA antes de ejecutar")

    def test_flujo_tabla_no_indexada_con_columna_desconocida(self):
        """
        Tabla no indexada (ESTPROVEED) con columna desconocida.
        El corrector consulta metadatos reales, descubre las columnas y pide corrección a la IA.
        """
        bad_sql = "SELECT FIRST 10 CODPROVEEDOR, NOMBRE, SALDO_PENDIENTE FROM ESTPROVEED"

        # Columnas reales de ESTPROVEED (sin SALDO_PENDIENTE, tiene SALDO)
        real_cols_estproveed = [
            "CODPROVEEDOR", "NOMBRE", "SALDO", "TOTALCOMPRAS",
            "ULTIMACOMPRA", "FECHAALTA"
        ]

        call_count = {"n": 0}

        def execute_func(query: str):
            q_up = query.upper()
            # Consulta de metadatos RDB$
            if "RDB$RELATION_FIELDS" in q_up:
                import re
                m = re.search(r"TRIM\(RDB\$RELATION_NAME\)\s*=\s*'([^']+)'", query, re.IGNORECASE)
                if m and m.group(1).upper() == "ESTPROVEED":
                    return [{"FIELD_NAME": c} for c in real_cols_estproveed]
                return []
            # Muestra de datos
            if "SELECT FIRST" in q_up and "* FROM ESTPROVEED" in q_up:
                return [{"CODPROVEEDOR": 1, "NOMBRE": "Proveedor Test", "SALDO": 1500.0}]
            # Query principal
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Primera ejecución: falla con column_unknown
                raise Exception("Dynamic SQL Error\nSQL error code = -206\nColumn unknown\nSALDO_PENDIENTE")
            # Segunda ejecución (corregida por IA): éxito
            return [
                {"CODPROVEEDOR": 1, "NOMBRE": "Proveedor Test", "SALDO": 1500.0},
                {"CODPROVEEDOR": 2, "NOMBRE": "Otro Proveedor", "SALDO": 3200.0},
            ]

        # La IA corrige SALDO_PENDIENTE → SALDO
        corrected = "SELECT FIRST 10 CODPROVEEDOR, NOMBRE, SALDO FROM ESTPROVEED"
        provider = self._make_ai_provider(corrected)

        result = run_async(self.corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="proveedores con saldo pendiente",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=execute_func,
            max_retries=3,
        ))

        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        # La IA debe haber sido llamada con contexto enriquecido
        self.assertTrue(provider.generate_text.called)
        # El prompt debe incluir las columnas reales
        call_args = provider.generate_text.call_args[0][0]
        self.assertIn("SALDO", call_args, "El prompt debe incluir columnas reales de ESTPROVEED")

    def test_flujo_tabla_con_pocos_registros_advertencia(self):
        """
        Tabla con pocos registros (DOCCAB con 3 registros).
        El corrector debe incluir advertencia en el prompt de corrección.
        """
        bad_sql = "SELECT FIRST 10 CODIGO, FECHA, TIPO FROM DOCCAB WHERE COLUMNA_INEXISTENTE = 1"

        real_cols_doccab = ["CODIGO", "TIPO", "SERIE", "NUMERO", "FECHA", "FECHAEMISION", "CODCLIENTE"]

        call_count = {"n": 0}

        def execute_func(query: str):
            q_up = query.upper()
            if "RDB$RELATION_FIELDS" in q_up:
                import re
                m = re.search(r"TRIM\(RDB\$RELATION_NAME\)\s*=\s*'([^']+)'", query, re.IGNORECASE)
                if m and m.group(1).upper() == "DOCCAB":
                    return [{"FIELD_NAME": c} for c in real_cols_doccab]
                return []
            if "SELECT FIRST" in q_up and "* FROM DOCCAB" in q_up:
                return [{"CODIGO": 1, "TIPO": 13, "FECHA": "2026-03-01"}]
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Dynamic SQL Error\nColumn unknown\nCOLUMNA_INEXISTENTE")
            return [{"CODIGO": 1, "TIPO": 13, "FECHA": "2026-03-01"}]

        corrected = "SELECT FIRST 10 CODIGO, FECHA, TIPO FROM DOCCAB"
        provider = self._make_ai_provider(corrected)

        result = run_async(self.corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="documentos recientes",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=execute_func,
            max_retries=3,
        ))

        self.assertIsNotNone(result)
        # El prompt de corrección debe incluir advertencia de pocos registros
        call_args = provider.generate_text.call_args[0][0]
        self.assertIn("DOCCAB", call_args.upper())
        # Debe mencionar los pocos registros
        self.assertTrue(
            "pocos registros" in call_args.lower() or "3 registros" in call_args.lower(),
            f"El prompt debe advertir sobre pocos registros. Prompt: {call_args[:500]}"
        )

    def test_flujo_correccion_encadenada_dos_errores(self):
        """
        Flujo con dos errores encadenados:
        1. Error 1: LIMIT → corregido deterministicamente a FIRST N
        2. Error 2: column_unknown → corregido por IA con metadatos reales
        """
        # Query con LIMIT (error 1) y columna inexistente (error 2)
        bad_sql = "SELECT CODIGO, NOMBRE_ARTICULO FROM ARTICULO LIMIT 5"

        real_cols_articulo = [
            "CODIGO", "NOMBRE", "DESCRIPCIONCORTA", "STOCKARTICULO",
            "PRECIOVENTA", "BAJA", "FAMILIA"
        ]

        call_count = {"n": 0}

        def execute_func(query: str):
            q_up = query.upper()
            if "RDB$RELATION_FIELDS" in q_up:
                import re
                m = re.search(r"TRIM\(RDB\$RELATION_NAME\)\s*=\s*'([^']+)'", query, re.IGNORECASE)
                if m and m.group(1).upper() == "ARTICULO":
                    return [{"FIELD_NAME": c} for c in real_cols_articulo]
                return []
            if "SELECT FIRST" in q_up and "* FROM ARTICULO" in q_up:
                return [{"CODIGO": "ART001", "NOMBRE": "Filtro"}]
            call_count["n"] += 1
            if call_count["n"] == 1:
                # El normalizer ya corrige LIMIT → FIRST, pero NOMBRE_ARTICULO no existe
                raise Exception("Dynamic SQL Error\nColumn unknown\nNOMBRE_ARTICULO")
            # Corregido: NOMBRE_ARTICULO → NOMBRE
            return [
                {"CODIGO": "ART001", "NOMBRE": "Filtro aire"},
                {"CODIGO": "ART002", "NOMBRE": "Compresor"},
            ]

        corrected = "SELECT FIRST 5 CODIGO, NOMBRE FROM ARTICULO"
        provider = self._make_ai_provider(corrected)

        result = run_async(self.corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="dame 5 artículos",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=execute_func,
            max_retries=3,
        ))

        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        # El prompt de IA debe incluir las columnas reales de ARTICULO
        call_args = provider.generate_text.call_args[0][0]
        self.assertIn("NOMBRE", call_args, "El prompt debe incluir columna NOMBRE de ARTICULO")

    def test_flujo_tabla_completamente_desconocida(self):
        """
        Tabla completamente desconocida (no en índices SIUO, no en metadatos).
        El corrector la descubre consultando RDB$RELATION_FIELDS y aprende.
        """
        # FOTOGRAF es una tabla que puede no estar bien indexada
        bad_sql = "SELECT FIRST 5 CODARTICULO, RUTA_IMAGEN, ORDEN FROM FOTOGRAF"

        # Columnas reales de FOTOGRAF
        real_cols = ["CODARTICULO", "RUTA", "ORDEN", "TIPO", "DESCRIPCION"]

        call_count = {"n": 0}

        def execute_func(query: str):
            q_up = query.upper()
            if "RDB$RELATION_FIELDS" in q_up:
                import re
                m = re.search(r"TRIM\(RDB\$RELATION_NAME\)\s*=\s*'([^']+)'", query, re.IGNORECASE)
                if m and m.group(1).upper() == "FOTOGRAF":
                    return [{"FIELD_NAME": c} for c in real_cols]
                return []
            if "SELECT FIRST" in q_up and "* FROM FOTOGRAF" in q_up:
                return [{"CODARTICULO": "ART001", "RUTA": "/img/art001.jpg", "ORDEN": 1}]
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Dynamic SQL Error\nColumn unknown\nRUTA_IMAGEN")
            return [
                {"CODARTICULO": "ART001", "RUTA": "/img/art001.jpg", "ORDEN": 1},
            ]

        # La IA corrige RUTA_IMAGEN → RUTA
        corrected = "SELECT FIRST 5 CODARTICULO, RUTA, ORDEN FROM FOTOGRAF"
        provider = self._make_ai_provider(corrected)

        result = run_async(self.corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="fotos de artículos",
            db_context="contexto de prueba",
            ai_provider=provider,
            execute_func=execute_func,
            max_retries=3,
        ))

        self.assertIsNotNone(result)
        # El prompt debe incluir las columnas reales descubiertas
        call_args = provider.generate_text.call_args[0][0]
        self.assertIn("RUTA", call_args, "El prompt debe incluir columna RUTA real de FOTOGRAF")
        self.assertIn("FOTOGRAF", call_args.upper())

    def test_max_retries_lanza_excepcion(self):
        """Si se agotan los reintentos, se lanza excepción con mensaje descriptivo."""
        bad_sql = "SELECT FIRST 5 COLUMNA_INEXISTENTE FROM TABLA_INEXISTENTE"

        def always_fails(query: str):
            if "RDB$" in query.upper():
                return []  # Sin metadatos
            raise Exception("Dynamic SQL Error\nColumn unknown\nCOLUMNA_INEXISTENTE")

        provider = MagicMock()
        provider.generate_text = AsyncMock(return_value="```sql\nSELECT FIRST 5 COLUMNA_INEXISTENTE FROM TABLA_INEXISTENTE\n```")

        with self.assertRaises(Exception) as ctx:
            run_async(self.corrector.execute_with_correction(
                sql_query=bad_sql,
                original_question="consulta imposible",
                db_context="contexto de prueba",
                ai_provider=provider,
                execute_func=always_fails,
                max_retries=2,
            ))

        # El mensaje de error debe ser descriptivo
        self.assertIn("intentos", str(ctx.exception).lower())


# ─── Tests: Integración normalizer + corrector ────────────────────────────────

class TestIntegracionNormalizerCorrector(unittest.TestCase):
    """Tests de integración entre normalizer y corrector."""

    def setUp(self):
        self.n = FirebirdSQLNormalizer()
        self.c = SQLCorrector()

    def test_pipeline_completo_articulos_mes_actual(self):
        """
        Pipeline completo para 'artículos con más compras este mes':
        1. Normalizer paso 19: añade JOIN DOCLIN
        2. Normalizer paso 20: añade JOIN DOCCAB para FECHA
        La query resultante debe ser válida para Firebird.
        """
        # Query que generaría la IA sin conocer la estructura real
        sql_ia = (
            "SELECT FIRST 5 CODIGO, NOMBRE, COUNT(*) AS NCOMPRAS "
            "FROM ARTICULO "
            "GROUP BY CODIGO, NOMBRE "
            "ORDER BY COUNT(*) DESC"
        )
        # Paso 1: normalizer añade JOIN DOCLIN (paso 19)
        out1, changes1 = self.n.normalize(sql_ia)
        self.assertIn("JOIN DOCLIN", out1.upper(), "Paso 19: debe añadir JOIN DOCLIN")

        # Ahora la IA añade filtro de fecha (con L.FECHA incorrecto)
        sql_con_fecha = out1.replace(
            "GROUP BY",
            "WHERE EXTRACT(MONTH FROM L.FECHA) = EXTRACT(MONTH FROM CURRENT_DATE) GROUP BY"
        )
        # Paso 2: normalizer corrige L.FECHA → JOIN DOCCAB + C.FECHA (paso 20)
        out2, changes2 = self.n.normalize(sql_con_fecha)
        out2_up = out2.upper()
        self.assertIn("DOCCAB", out2_up, "Paso 20: debe añadir JOIN DOCCAB")
        self.assertNotIn("L.FECHA", out2_up, "L.FECHA debe desaparecer")
        self.assertIn("C.FECHA", out2_up, "C.FECHA debe aparecer")

    def test_detect_error_type_column_unknown(self):
        """detect_error_type identifica correctamente column_unknown con nombre de columna."""
        error = (
            "Dynamic SQL Error\nSQL error code = -206\n"
            "Column unknown\nL.FECHA\nAt line 4, column 28"
        )
        info = self.c.detect_error_type(error)
        self.assertEqual(info["type"], "column_unknown")
        # La columna extraída puede ser L.FECHA o FECHA según el parser
        self.assertIn(info.get("column", "").upper(), ["L.FECHA", "FECHA", "L"])

    def test_detect_error_type_table_unknown(self):
        """detect_error_type identifica table_unknown."""
        error = "Dynamic SQL Error\nSQL error code = -204\nTable unknown TABLA_INEXISTENTE"
        info = self.c.detect_error_type(error)
        self.assertEqual(info["type"], "table_unknown")

    def test_detect_error_type_blob(self):
        """detect_error_type identifica blob_in_groupby."""
        error = "conversion error from string BLOB"
        info = self.c.detect_error_type(error)
        self.assertEqual(info["type"], "blob_in_groupby")

    def test_detect_error_type_limit(self):
        """detect_error_type identifica invalid_keyword para LIMIT."""
        error = "Dynamic SQL Error\nToken unknown - line 1, column 50\nLIMIT"
        info = self.c.detect_error_type(error)
        self.assertEqual(info["type"], "invalid_keyword")
        self.assertEqual(info["token"].upper(), "LIMIT")


# ─── Tests: Constantes y configuración ───────────────────────────────────────

class TestConstantesConfiguracion(unittest.TestCase):
    """Verifica que las constantes están correctamente configuradas."""

    def test_table_date_columns_completo(self):
        """TABLE_DATE_COLUMNS tiene entradas para las tablas principales."""
        self.assertIn("DOCLIN", TABLE_DATE_COLUMNS)
        self.assertIn("DOCCAB", TABLE_DATE_COLUMNS)
        self.assertIn("ARTICULO", TABLE_DATE_COLUMNS)

    def test_doclin_join_info_completo(self):
        """La info de JOIN para DOCLIN está completa."""
        join_info = TABLE_DATE_COLUMNS["DOCLIN"]["date_via_join"]
        self.assertIn("join_table", join_info)
        self.assertIn("join_on", join_info)
        self.assertIn("date_col", join_info)
        self.assertEqual(join_info["join_table"], "DOCCAB")
        self.assertIn("CODDOCUMENTO", join_info["join_on"])

    def test_low_record_tables_tiene_warning(self):
        """Todas las entradas de LOW_RECORD_TABLES tienen 'warning'."""
        for table, info in LOW_RECORD_TABLES.items():
            self.assertIn("warning", info, f"{table} debe tener 'warning'")
            self.assertIn("record_count", info, f"{table} debe tener 'record_count'")
            self.assertGreater(len(info["warning"]), 10, f"Warning de {table} debe ser descriptivo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
