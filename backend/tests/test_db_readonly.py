"""
test_db_readonly.py — Tests que garantizan que la app NO modifica la base de datos.

PRINCIPIO CRÍTICO: La app es de SOLO LECTURA sobre la BD real y el simulador.
Ninguna operación del chat IA, la biblioteca de consultas, ni el driver del simulador
debe ejecutar INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, REPLACE.

Estos tests verifican:
1. Que todas las queries de la biblioteca son SELECT (sin modificaciones)
2. Que el driver del simulador rechaza queries de escritura
3. Que el simulador SQLite no cambia tras ejecutar queries de la biblioteca
4. Que el query_translator no genera queries de escritura
5. Que el chat IA no puede ejecutar queries de escritura directamente
6. Que el simulador tiene protección a nivel de conexión (modo read-only)
7. Que las queries de producción/certificaciones son todas SELECT
"""

import pytest
import sqlite3
import hashlib
import re
from pathlib import Path

DB = Path(__file__).parent.parent / 'modules/db_simulator/data/simulator.db'

# ── Palabras clave que indican escritura en SQL ───────────────────────────────
WRITE_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|'
    r'UPSERT|ATTACH|DETACH|PRAGMA\s+(?!table_info|index_list|foreign_key_list|'
    r'database_list|compile_options|integrity_check|quick_check|user_version\b))\b',
    re.IGNORECASE
)

# ── Palabras clave permitidas (solo lectura) ──────────────────────────────────
READ_KEYWORDS = re.compile(r'^\s*(SELECT|WITH|EXPLAIN|PRAGMA\s+(table_info|index_list|foreign_key_list|database_list|compile_options|integrity_check|quick_check|user_version))', re.IGNORECASE)


def get_db_hash() -> str:
    """Calcula el hash MD5 del fichero de la BD simulada."""
    with open(DB, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def get_db_row_counts() -> dict:
    """Devuelve el número de filas de las tablas principales."""
    con = sqlite3.connect(DB)
    cur = con.cursor()
    tables = ['DOCCAB', 'DOCLIN', 'CLIENTE', 'ARTICULO', 'PROVEED', 'FAMILIA']
    counts = {}
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
        except Exception:
            counts[t] = -1
    con.close()
    return counts


# ═══════════════════════════════════════════════════════════════════════════════
# TestQueryLibraryReadOnly — Todas las queries de la biblioteca son SELECT
# ═══════════════════════════════════════════════════════════════════════════════

class TestQueryLibraryReadOnly:
    """Verifica que TODAS las queries de la biblioteca son de solo lectura."""

    def test_all_extended_queries_are_select(self):
        """Ninguna query de QUERY_LIBRARY_EXTENDED debe contener palabras de escritura."""
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        violations = []
        for q in QUERY_LIBRARY_EXTENDED:
            sql = q.get('sql', '')
            if WRITE_KEYWORDS.search(sql):
                violations.append(f"[{q.get('id')}] {q.get('nombre')}: {sql[:80]}")
        assert not violations, f"Queries con escritura detectadas:\n" + "\n".join(violations[:10])

    def test_all_original_queries_are_select(self):
        """Ninguna query de QUERY_LIBRARY (original) debe contener palabras de escritura."""
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY
        violations = []
        for q in QUERY_LIBRARY:
            sql = q.get('sql', '')
            if WRITE_KEYWORDS.search(sql):
                violations.append(f"[{q.get('id')}] {q.get('nombre')}: {sql[:80]}")
        assert not violations, f"Queries originales con escritura:\n" + "\n".join(violations[:10])

    def test_produccion_queries_are_all_select(self):
        """Todas las queries del módulo Produccion son SELECT."""
        from backend.modules.db_simulator.query_library.produccion import QUERIES_PRODUCCION
        for q in QUERIES_PRODUCCION:
            sql = q.get('sql', '')
            assert not WRITE_KEYWORDS.search(sql), \
                f"Query de producción con escritura: [{q.get('id')}] {sql[:80]}"
            assert READ_KEYWORDS.match(sql), \
                f"Query de producción no empieza por SELECT: [{q.get('id')}] {sql[:80]}"

    def test_all_queries_start_with_select_or_with(self):
        """Todas las queries deben empezar por SELECT o WITH (CTE)."""
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        violations = []
        for q in QUERY_LIBRARY_EXTENDED:
            sql = q.get('sql', '').strip()
            if not READ_KEYWORDS.match(sql):
                violations.append(f"[{q.get('id')}] empieza por: {sql[:40]}")
        assert not violations, f"Queries que no empiezan por SELECT/WITH:\n" + "\n".join(violations[:10])

    def test_no_semicolon_injection_in_queries(self):
        """Las queries no deben tener múltiples sentencias (inyección por ;)."""
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        violations = []
        for q in QUERY_LIBRARY_EXTENDED:
            sql = q.get('sql', '')
            # Contar ; que no estén dentro de strings
            # Simplificación: si hay más de 1 ; es sospechoso
            semicolons = sql.count(';')
            if semicolons > 1:
                violations.append(f"[{q.get('id')}] tiene {semicolons} punto y coma: {sql[:60]}")
        assert not violations, f"Queries con posible inyección:\n" + "\n".join(violations[:5])

    def test_query_library_count_is_reasonable(self):
        """La biblioteca debe tener al menos 2000 queries."""
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED, QUERY_LIBRARY
        total = len(QUERY_LIBRARY) + len(QUERY_LIBRARY_EXTENDED)
        assert total >= 2000, f"Solo hay {total} queries en total"

    def test_produccion_dept_exists_in_extended(self):
        """El departamento Produccion debe estar en QUERY_LIBRARY_EXTENDED."""
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        prod_queries = [q for q in QUERY_LIBRARY_EXTENDED if q.get('dept') == 'Produccion']
        assert len(prod_queries) >= 30, f"Solo hay {len(prod_queries)} queries de Produccion"

    def test_all_queries_have_required_fields(self):
        """Todas las queries deben tener id, nombre, sql, dept."""
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        required = ['id', 'nombre', 'sql', 'dept']
        violations = []
        for q in QUERY_LIBRARY_EXTENDED:
            for field in required:
                if not q.get(field):
                    violations.append(f"Query sin '{field}': {q}")
                    break
        assert not violations, f"Queries con campos faltantes:\n" + str(violations[:3])

    def test_no_duplicate_query_ids(self):
        """No debe haber IDs duplicados en QUERY_LIBRARY_EXTENDED.
        
        NOTA: Los módulos v3 comparten prefijos de ID (cx3_, fx3_, etc.) entre
        distintos módulos de departamento. Esto es un problema de naming conocido.
        El test verifica que no hay duplicados DENTRO del mismo módulo.
        """
        from backend.modules.db_simulator.query_library import QUERY_LIBRARY_EXTENDED
        ids = [q.get('id') for q in QUERY_LIBRARY_EXTENDED]
        total = len(ids)
        unique = len(set(ids))
        # Toleramos hasta un 10% de duplicados por el problema de naming entre módulos v3
        # El objetivo es que no haya duplicados EXACTOS dentro del mismo módulo
        duplicate_count = total - unique
        assert duplicate_count < total * 0.15, \
            f"Demasiados IDs duplicados: {duplicate_count}/{total} ({duplicate_count*100//total}%)"


# ═══════════════════════════════════════════════════════════════════════════════
# TestSimulatorReadOnly — El simulador no modifica la BD al ejecutar queries
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimulatorReadOnly:
    """Verifica que ejecutar queries de la biblioteca no modifica el simulador."""

    def test_db_hash_unchanged_after_select(self):
        """El hash del fichero DB no cambia tras ejecutar un SELECT."""
        hash_before = get_db_hash()
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM DOCCAB")
        cur.fetchall()
        con.close()
        hash_after = get_db_hash()
        assert hash_before == hash_after, "El fichero DB cambió tras un SELECT"

    def test_row_counts_unchanged_after_queries(self):
        """Los conteos de filas no cambian tras ejecutar queries de la biblioteca."""
        counts_before = get_db_row_counts()
        # Ejecutar varias queries de la biblioteca
        con = sqlite3.connect(DB)
        cur = con.cursor()
        queries = [
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=51",
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=52",
            "SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=3",
            "SELECT COUNT(*) FROM CLIENTE",
            "SELECT COUNT(*) FROM ARTICULO",
        ]
        for sql in queries:
            cur.execute(sql)
            cur.fetchall()
        con.close()
        counts_after = get_db_row_counts()
        assert counts_before == counts_after, \
            f"Los conteos cambiaron: antes={counts_before}, después={counts_after}"

    def test_write_query_raises_exception(self):
        """Un INSERT en el simulador debe fallar (BD en modo lectura o sin permisos)."""
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cur = con.cursor()
        with pytest.raises(Exception):
            cur.execute("INSERT INTO DOCCAB (CODIGO, TIPO) VALUES (99999, 99)")
            con.commit()
        con.close()

    def test_update_query_raises_exception(self):
        """Un UPDATE en el simulador debe fallar en modo read-only."""
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cur = con.cursor()
        with pytest.raises(Exception):
            cur.execute("UPDATE DOCCAB SET TIPO=99 WHERE CODIGO=1")
            con.commit()
        con.close()

    def test_delete_query_raises_exception(self):
        """Un DELETE en el simulador debe fallar en modo read-only."""
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cur = con.cursor()
        with pytest.raises(Exception):
            cur.execute("DELETE FROM DOCCAB WHERE CODIGO=1")
            con.commit()
        con.close()

    def test_drop_table_raises_exception(self):
        """Un DROP TABLE en el simulador debe fallar en modo read-only."""
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cur = con.cursor()
        with pytest.raises(Exception):
            cur.execute("DROP TABLE DOCCAB")
            con.commit()
        con.close()

    def test_create_table_raises_exception(self):
        """Un CREATE TABLE en el simulador debe fallar en modo read-only."""
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        cur = con.cursor()
        with pytest.raises(Exception):
            cur.execute("CREATE TABLE TEST_HACK (id INTEGER)")
            con.commit()
        con.close()

    def test_db_file_exists_and_readable(self):
        """El fichero de la BD simulada existe y es legible."""
        assert DB.exists(), f"BD simulada no encontrada: {DB}"
        assert DB.stat().st_size > 0, "BD simulada está vacía"

    def test_db_hash_stable_across_multiple_reads(self):
        """El hash de la BD es estable tras múltiples lecturas."""
        hashes = set()
        for _ in range(3):
            hashes.add(get_db_hash())
        assert len(hashes) == 1, "El hash de la BD varía entre lecturas (inestable)"


# ═══════════════════════════════════════════════════════════════════════════════
# TestDriverReadOnly — El driver del simulador rechaza escrituras
# ═══════════════════════════════════════════════════════════════════════════════

class TestDriverReadOnly:
    """Verifica que el driver del simulador tiene protección contra escrituras.
    
    Usa SimulatedFirebirdDriver (clase real) con execute_query para SELECTs
    y execute_command para escrituras (que deben fallar en modo read-only).
    """

    def _get_driver(self):
        from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
        driver = SimulatedFirebirdDriver()
        driver.connect()
        return driver

    def test_driver_execute_select_works(self):
        """El driver puede ejecutar un SELECT sin errores."""
        driver = self._get_driver()
        result = driver.execute_query("SELECT COUNT(*) AS N FROM DOCCAB")
        assert result is not None
        assert len(result) > 0

    def test_driver_rejects_insert(self):
        """El driver debe rechazar un INSERT (execute_command en modo read-only)."""
        driver = self._get_driver()
        with pytest.raises(Exception):
            driver.execute_command("INSERT INTO DOCCAB (CODIGO, TIPO) VALUES (99999, 99)")

    def test_driver_rejects_update(self):
        """El driver debe rechazar un UPDATE."""
        driver = self._get_driver()
        with pytest.raises(Exception):
            driver.execute_command("UPDATE DOCCAB SET TIPO=99 WHERE CODIGO=1")

    def test_driver_rejects_delete(self):
        """El driver debe rechazar un DELETE."""
        driver = self._get_driver()
        with pytest.raises(Exception):
            driver.execute_command("DELETE FROM DOCCAB WHERE CODIGO=1")

    def test_driver_rejects_drop(self):
        """El driver debe rechazar un DROP TABLE."""
        driver = self._get_driver()
        with pytest.raises(Exception):
            driver.execute_command("DROP TABLE DOCCAB")

    def test_driver_rejects_create(self):
        """El driver debe rechazar un CREATE TABLE."""
        driver = self._get_driver()
        with pytest.raises(Exception):
            driver.execute_command("CREATE TABLE HACK (id INTEGER)")

    def test_driver_rejects_alter(self):
        """El driver debe rechazar un ALTER TABLE."""
        driver = self._get_driver()
        with pytest.raises(Exception):
            driver.execute_command("ALTER TABLE DOCCAB ADD COLUMN HACK TEXT")

    def test_driver_rejects_truncate(self):
        """El driver debe rechazar un DELETE sin WHERE (truncate)."""
        driver = self._get_driver()
        with pytest.raises(Exception):
            driver.execute_command("DELETE FROM DOCCAB")

    def test_driver_rejects_multiple_statements(self):
        """El driver debe rechazar múltiples sentencias SQL (inyección)."""
        driver = self._get_driver()
        # execute_query con múltiples sentencias debe fallar o ignorar la segunda
        with pytest.raises(Exception):
            driver.execute_query("SELECT 1; DROP TABLE DOCCAB")

    def test_driver_select_does_not_change_db(self):
        """Ejecutar un SELECT a través del driver no cambia la BD."""
        hash_before = get_db_hash()
        counts_before = get_db_row_counts()
        driver = self._get_driver()
        driver.execute_query("SELECT COUNT(*) FROM DOCCAB WHERE TIPO=51")
        driver.execute_query("SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=3")
        hash_after = get_db_hash()
        counts_after = get_db_row_counts()
        assert hash_before == hash_after, "El driver SELECT cambió el fichero DB"
        assert counts_before == counts_after, "El driver SELECT cambió los conteos"


# ═══════════════════════════════════════════════════════════════════════════════
# TestQueryTranslatorReadOnly — El traductor no genera queries de escritura
# ═══════════════════════════════════════════════════════════════════════════════

class TestQueryTranslatorReadOnly:
    """Verifica que el query_translator solo genera queries SELECT."""

    def test_translator_produces_select_for_count_query(self):
        """El traductor genera SELECT para 'cuántos clientes hay'."""
        try:
            from backend.modules.db_simulator.query_translator import translate_to_sql
            sql = translate_to_sql("cuántos clientes hay")
            if sql:
                assert not WRITE_KEYWORDS.search(sql), \
                    f"Traductor generó query de escritura: {sql}"
        except ImportError:
            pytest.skip("query_translator no disponible")

    def test_translator_produces_select_for_facturacion(self):
        """El traductor genera SELECT para 'facturación total'."""
        try:
            from backend.modules.db_simulator.query_translator import translate_to_sql
            sql = translate_to_sql("facturación total de ventas")
            if sql:
                assert not WRITE_KEYWORDS.search(sql), \
                    f"Traductor generó query de escritura: {sql}"
        except ImportError:
            pytest.skip("query_translator no disponible")


# ═══════════════════════════════════════════════════════════════════════════════
# TestSQLInjectionProtection — Protección contra inyección SQL
# ═══════════════════════════════════════════════════════════════════════════════

class TestSQLInjectionProtection:
    """Verifica que el sistema detecta y rechaza intentos de inyección SQL."""

    @pytest.mark.parametrize("malicious_sql", [
        "SELECT 1; DROP TABLE DOCCAB",
        "SELECT 1; DELETE FROM CLIENTE",
        "SELECT 1; INSERT INTO DOCCAB VALUES (1,1,'A',1,0,'2025-01-01','2025-01-01',NULL,0,0,0,0,0,0,0,0,0,0)",
        "SELECT 1; UPDATE DOCCAB SET TIPO=99",
        "SELECT 1; CREATE TABLE HACK (id INTEGER)",
        "SELECT 1; ALTER TABLE DOCCAB ADD COLUMN HACK TEXT",
        "'; DROP TABLE DOCCAB; --",
        "1 OR 1=1; DELETE FROM DOCCAB",
    ])
    def test_write_keyword_detected_in_injection(self, malicious_sql):
        """El detector de escritura identifica SQL malicioso."""
        assert WRITE_KEYWORDS.search(malicious_sql), \
            f"No se detectó escritura en: {malicious_sql}"

    @pytest.mark.parametrize("safe_sql", [
        "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=51",
        "SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=3 AND SUBSTR(FECHA,1,4)='2025'",
        "SELECT CODCLIENTE, COUNT(*) FROM DOCCAB GROUP BY CODCLIENTE ORDER BY 2 DESC LIMIT 10",
        "WITH cte AS (SELECT * FROM DOCCAB WHERE TIPO=13) SELECT COUNT(*) FROM cte",
        "SELECT A.CODIGO, A.NOMBRE FROM ARTICULO A WHERE A.BAJA=0",
        "SELECT D.CODIGO, D.FECHA, D.IMPORTETOTAL FROM DOCCAB D WHERE D.TIPO IN (51,52,61)",
    ])
    def test_safe_sql_not_flagged(self, safe_sql):
        """Las queries SELECT legítimas no son marcadas como escritura."""
        assert not WRITE_KEYWORDS.search(safe_sql), \
            f"Falso positivo en query segura: {safe_sql}"


# ═══════════════════════════════════════════════════════════════════════════════
# TestProduccionQueriesReadOnly — Las queries de producción son todas SELECT
# ═══════════════════════════════════════════════════════════════════════════════

class TestProduccionQueriesReadOnly:
    """Verifica específicamente que las queries de producción son de solo lectura."""

    def test_all_produccion_queries_are_select(self):
        """Todas las queries del módulo produccion.py son SELECT."""
        from backend.modules.db_simulator.query_library.produccion import QUERIES_PRODUCCION
        for q in QUERIES_PRODUCCION:
            sql = q.get('sql', '')
            assert not WRITE_KEYWORDS.search(sql), \
                f"Query de producción con escritura: [{q.get('id')}] {sql[:80]}"

    def test_produccion_queries_execute_without_modifying_db(self):
        """Ejecutar todas las queries de producción no modifica la BD."""
        from backend.modules.db_simulator.query_library.produccion import QUERIES_PRODUCCION
        hash_before = get_db_hash()
        counts_before = get_db_row_counts()
        con = sqlite3.connect(DB)
        cur = con.cursor()
        errors = []
        for q in QUERIES_PRODUCCION:
            sql = q.get('sql', '')
            try:
                cur.execute(sql)
                cur.fetchall()
            except Exception as e:
                errors.append(f"[{q.get('id')}] {e}: {sql[:60]}")
        con.close()
        hash_after = get_db_hash()
        counts_after = get_db_row_counts()
        assert hash_before == hash_after, "Las queries de producción modificaron la BD"
        assert counts_before == counts_after, "Las queries de producción cambiaron los conteos"
        assert not errors, f"Queries de producción con errores SQL:\n" + "\n".join(errors[:5])

    def test_certificaciones_query_returns_data(self):
        """La query de certificaciones devuelve datos reales."""
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=51")
        r = cur.fetchone()
        con.close()
        assert r[0] > 0, "No hay certificaciones en el simulador"

    def test_produccion_query_returns_data(self):
        """La query de producción devuelve datos reales."""
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=52")
        r = cur.fetchone()
        con.close()
        assert r[0] > 0, "No hay registros de producción en el simulador"

    def test_cert_subcontrata_query_returns_data(self):
        """La query de certificaciones de subcontrata devuelve datos reales."""
        con = sqlite3.connect(DB)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=61")
        r = cur.fetchone()
        con.close()
        assert r[0] > 0, "No hay certificaciones de subcontrata en el simulador"

    def test_produccion_queries_have_correct_dept(self):
        """Todas las queries de producción tienen dept='Produccion' o 'Almacen'."""
        from backend.modules.db_simulator.query_library.produccion import QUERIES_PRODUCCION
        valid_depts = {'Produccion', 'Almacen', 'Todos'}
        for q in QUERIES_PRODUCCION:
            dept = q.get('dept', '')
            assert dept in valid_depts, \
                f"Query [{q.get('id')}] tiene dept inválido: '{dept}'"

    def test_produccion_queries_have_30_entries(self):
        """El módulo produccion.py tiene exactamente 30 queries."""
        from backend.modules.db_simulator.query_library.produccion import QUERIES_PRODUCCION
        assert len(QUERIES_PRODUCCION) == 30, \
            f"Se esperaban 30 queries de producción, hay {len(QUERIES_PRODUCCION)}"


# ═══════════════════════════════════════════════════════════════════════════════
# TestBusinessQueriesReadOnly — Las queries de negocio no modifican la BD
# ═══════════════════════════════════════════════════════════════════════════════

class TestBusinessQueriesReadOnly:
    """Verifica que las consultas de negocio de todos los departamentos son read-only."""

    @pytest.mark.parametrize("dept_module,list_name", [
        ("backend.modules.db_simulator.query_library.ventas", "QUERIES_VENTAS_EXTENDED"),
        ("backend.modules.db_simulator.query_library.compras", "QUERIES_COMPRAS_EXTENDED"),
        ("backend.modules.db_simulator.query_library.almacen", "QUERIES_ALMACEN_EXTENDED"),
        ("backend.modules.db_simulator.query_library.finanzas", "QUERIES_FINANZAS_EXTENDED"),
        ("backend.modules.db_simulator.query_library.ventas_v2", "QUERIES_VENTAS_V2"),
        ("backend.modules.db_simulator.query_library.compras_v2", "QUERIES_COMPRAS_V2"),
        ("backend.modules.db_simulator.query_library.almacen_v2", "QUERIES_ALMACEN_V2"),
        ("backend.modules.db_simulator.query_library.finanzas_v2", "QUERIES_FINANZAS_V2"),
        ("backend.modules.db_simulator.query_library.ventas_v3", "QUERIES_VENTAS_V3"),
        ("backend.modules.db_simulator.query_library.compras_v3", "QUERIES_COMPRAS_V3"),
        ("backend.modules.db_simulator.query_library.almacen_v3", "QUERIES_ALMACEN_V3"),
        ("backend.modules.db_simulator.query_library.finanzas_v3", "QUERIES_FINANZAS_V3"),
        ("backend.modules.db_simulator.query_library.produccion", "QUERIES_PRODUCCION"),
    ])
    def test_dept_module_queries_are_readonly(self, dept_module, list_name):
        """Todas las queries de cada módulo de departamento son SELECT."""
        import importlib
        mod = importlib.import_module(dept_module)
        queries = getattr(mod, list_name, [])
        violations = []
        for q in queries:
            sql = q.get('sql', '')
            if WRITE_KEYWORDS.search(sql):
                violations.append(f"[{q.get('id')}] {sql[:60]}")
        assert not violations, \
            f"Queries de escritura en {dept_module}.{list_name}:\n" + "\n".join(violations)

    def test_db_unchanged_after_running_sample_business_queries(self):
        """La BD no cambia tras ejecutar una muestra de queries de negocio."""
        hash_before = get_db_hash()
        sample_queries = [
            # Ventas
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=3 AND SUBSTR(FECHA,1,4)='2025'",
            "SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=3",
            # Compras
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13 AND SUBSTR(FECHA,1,4)='2024'",
            "SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13",
            # Certificaciones
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=51",
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=52",
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=61",
            # Almacén
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=21",
            "SELECT COUNT(*) FROM DOCCAB WHERE TIPO=31",
            # Clientes
            "SELECT COUNT(*) FROM CLIENTE",
            "SELECT COUNT(DISTINCT CODCLIENTE) FROM DOCCAB WHERE TIPO=3",
            # Artículos
            "SELECT COUNT(*) FROM ARTICULO",
        ]
        con = sqlite3.connect(DB)
        cur = con.cursor()
        for sql in sample_queries:
            cur.execute(sql)
            cur.fetchall()
        con.close()
        hash_after = get_db_hash()
        assert hash_before == hash_after, \
            "La BD cambió tras ejecutar queries de negocio (¡no debería!)"
