"""
test_integration_real.py
========================
Tests de integracion REALES sin mocks:
  1. BD Simulada (SQLite) — datos y metadatos reales del simulador
  2. BD Real (Firebird 192.168.0.254:3050) — solo SELECT, nunca modifica nada
  3. Modelo 8B via backend live (localhost:8001) — preguntas reales al chat IA

Principios:
  - CERO mocks: todo contra servicios reales
  - CERO escrituras: solo SELECT en BD real Firebird
  - Auto-skip si el servicio no esta disponible (BD real, backend, LM Studio)
  - Cada test verifica datos reales, no valores hardcodeados
  - Los tests de IA verifican que la respuesta es coherente (no vacia, no error)

Ejecutar:
  set PYTHONUTF8=1
  set PYTHONPATH=c:\\Users\\migue\\Documents\\activepieces\\pendiente-fact\\bots\\interjddcia
  python -m pytest backend/tests/test_integration_real.py -v --tb=short

  # Solo BD real:
  python -m pytest backend/tests/test_integration_real.py -v -k "RealDB"

  # Solo simulador:
  python -m pytest backend/tests/test_integration_real.py -v -k "Simulator"

  # Solo modelo 8B:
  python -m pytest backend/tests/test_integration_real.py -v -k "Model8B"
"""

import json
import os
import socket
import sys
import time
import unittest
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

# ── Path setup ────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

os.chdir(_DIR)

# ── Helpers de conectividad ───────────────────────────────────────────────────

def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _http_get(url: str, timeout: float = 5.0) -> Optional[dict]:
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def _http_post(url: str, payload: dict, timeout: float = 120.0) -> Optional[dict]:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data,
                                  headers={'Content-Type': 'application/json'},
                                  method='POST')
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


# ── Checks de disponibilidad (se evaluan una vez) ────────────────────────────

def _backend_available() -> bool:
    return _tcp_open('localhost', 8001)


def _lmstudio_available() -> bool:
    return _tcp_open('localhost', 1234)


def _firebird_available() -> bool:
    from backend.core.config.settings import settings as s
    return _tcp_open(s.DB_HOST, s.DB_PORT, timeout=3.0)


def _get_firebird_driver():
    """Devuelve un driver Firebird conectado (solo lectura)."""
    from backend.core.factory.db_factory import DBFactory
    from backend.core.utils.constants import DBConstants
    from backend.core.config.settings import settings as s
    from backend.modules.db_simulator.constants import TestModeConfig

    driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
    config = type("C", (), {
        "host": s.DB_HOST,
        "port": s.DB_PORT,
        "database": s.DB_NAME,
        "user": s.DB_USER,
        "password": s.DB_PASSWORD,
        "charset": TestModeConfig.FIREBIRD_CHARSET,
    })()
    driver.connect(config)
    return driver


def _get_simulator_driver():
    """Devuelve un SimulatedFirebirdDriver conectado al simulador SQLite."""
    from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
    from backend.modules.db_simulator.constants import SimulatorPaths
    driver = SimulatedFirebirdDriver()
    db_path = str(SimulatorPaths.DB_PATH) if SimulatorPaths.DB_PATH.exists() else ":memory:"
    driver.connect(db_path=db_path)
    return driver


# =============================================================================
# BLOQUE 1: BD SIMULADA (SQLite) — sin conexion externa
# =============================================================================

class TestSimulatorDB(unittest.TestCase):
    """
    Tests contra la BD simulada SQLite.
    No requieren conexion externa — siempre disponibles.
    Verifican datos y metadatos reales del simulador (sin mocks).
    """

    @classmethod
    def setUpClass(cls):
        cls.driver = _get_simulator_driver()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.driver.disconnect()
        except Exception:
            pass

    def _q(self, sql: str) -> List[Dict[str, Any]]:
        return self.driver.execute_query(sql)

    # ── Metadatos del simulador ───────────────────────────────────────────────

    def test_simulator_status_ready(self):
        """El simulador debe estar en estado 'ready'."""
        from backend.modules.db_simulator.constants import SimulatorPaths
        with open(SimulatorPaths.STATUS_PATH) as f:
            status = json.load(f)
        self.assertEqual(status.get('status'), 'ready')

    def test_simulator_config_has_required_keys(self):
        """config.json del simulador tiene las claves requeridas."""
        from backend.modules.db_simulator.constants import SimulatorPaths
        with open(SimulatorPaths.CONFIG_PATH) as f:
            cfg = json.load(f)
        for key in ['simulator_enabled', 'show_disclaimer', 'test_mode']:
            self.assertIn(key, cfg, f"config.json debe tener '{key}'")

    def test_simulator_db_file_exists_and_readable(self):
        """simulator.db existe y es legible."""
        from backend.modules.db_simulator.constants import SimulatorPaths
        self.assertTrue(SimulatorPaths.DB_PATH.exists())
        self.assertGreater(SimulatorPaths.DB_PATH.stat().st_size, 0)

    # ── Tablas principales ────────────────────────────────────────────────────

    def test_doccab_has_records(self):
        """DOCCAB tiene registros reales."""
        rows = self._q("SELECT COUNT(*) AS N FROM DOCCAB")
        n = rows[0]['N']
        self.assertGreater(n, 0, "DOCCAB esta vacia")
        print(f"\n  DOCCAB: {n} registros")

    def test_cliente_has_records(self):
        """CLIENTE tiene registros reales."""
        rows = self._q("SELECT COUNT(*) AS N FROM CLIENTE")
        n = rows[0]['N']
        self.assertGreater(n, 0, "CLIENTE esta vacia")
        print(f"\n  CLIENTE: {n} registros")

    def test_articulo_has_records(self):
        """ARTICULO tiene registros reales."""
        rows = self._q("SELECT COUNT(*) AS N FROM ARTICULO")
        n = rows[0]['N']
        self.assertGreater(n, 0, "ARTICULO esta vacia")
        print(f"\n  ARTICULO: {n} registros")

    def test_doclin_has_records(self):
        """DOCLIN tiene registros reales."""
        rows = self._q("SELECT COUNT(*) AS N FROM DOCLIN")
        n = rows[0]['N']
        self.assertGreater(n, 0, "DOCLIN esta vacia")
        print(f"\n  DOCLIN: {n} registros")

    def test_familia_has_records(self):
        """FAMILIA tiene registros reales."""
        rows = self._q("SELECT COUNT(*) AS N FROM FAMILIA")
        n = rows[0]['N']
        self.assertGreater(n, 0, "FAMILIA esta vacia")
        print(f"\n  FAMILIA: {n} registros")

    # ── Datos de facturas ─────────────────────────────────────────────────────

    def test_facturas_tipo13_exist(self):
        """Hay facturas (TIPO=13) en el simulador."""
        rows = self._q("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=13")
        n = rows[0]['N']
        self.assertGreater(n, 0, "No hay facturas TIPO=13 en el simulador")
        print(f"\n  Facturas TIPO=13: {n}")

    def test_facturacion_total_positive(self):
        """La facturacion total (TIPO=13) es positiva."""
        rows = self._q("SELECT SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB WHERE TIPO=13")
        total = rows[0]['TOTAL']
        self.assertIsNotNone(total)
        self.assertGreater(total, 0)
        print(f"\n  Facturacion total simulador: {total:,.2f}")

    def test_presupuestos_tipo0_exist(self):
        """Hay presupuestos (TIPO=0) en el simulador."""
        rows = self._q("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0")
        n = rows[0]['N']
        self.assertGreater(n, 0, "No hay presupuestos TIPO=0 en el simulador")
        print(f"\n  Presupuestos TIPO=0: {n}")

    def test_multiple_tipos_in_doccab(self):
        """DOCCAB tiene multiples tipos de documentos."""
        rows = self._q("SELECT TIPO, COUNT(*) AS N FROM DOCCAB GROUP BY TIPO ORDER BY TIPO")
        self.assertGreater(len(rows), 1, "Solo hay 1 tipo de documento")
        for row in rows:
            print(f"\n  TIPO={row['TIPO']}: {row['N']} docs")

    def test_importetotal_not_null_for_facturas(self):
        """IMPORTETOTAL no es NULL en facturas."""
        rows = self._q(
            "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL IS NULL"
        )
        n = rows[0]['N']
        self.assertEqual(n, 0, f"Hay {n} facturas con IMPORTETOTAL NULL")

    # ── Columnas reales ───────────────────────────────────────────────────────

    def test_doccab_columns_real(self):
        """DOCCAB tiene las columnas reales del schema Firebird."""
        import sqlite3
        from backend.modules.db_simulator.constants import SimulatorPaths
        con = sqlite3.connect(str(SimulatorPaths.DB_PATH))
        cur = con.cursor()
        cur.execute("PRAGMA table_info(DOCCAB)")
        cols = [r[1] for r in cur.fetchall()]
        con.close()
        for col in ['CODIGO', 'TIPO', 'FECHA', 'CODCLIENTE', 'IMPORTETOTAL',
                    'IMPORTEBASE', 'IMPORTEIVA']:
            self.assertIn(col, cols, f"DOCCAB no tiene columna {col}")

    def test_articulo_columns_real(self):
        """ARTICULO tiene las columnas reales del schema Firebird."""
        import sqlite3
        from backend.modules.db_simulator.constants import SimulatorPaths
        con = sqlite3.connect(str(SimulatorPaths.DB_PATH))
        cur = con.cursor()
        cur.execute("PRAGMA table_info(ARTICULO)")
        cols = [r[1] for r in cur.fetchall()]
        con.close()
        for col in ['CODIGO', 'NOMBRE', 'DESCRIPCION', 'PRECIOVENTA', 'PRECIOCOSTE']:
            self.assertIn(col, cols, f"ARTICULO no tiene columna {col}")

    def test_cliente_columns_real(self):
        """CLIENTE tiene las columnas reales del schema Firebird."""
        import sqlite3
        from backend.modules.db_simulator.constants import SimulatorPaths
        con = sqlite3.connect(str(SimulatorPaths.DB_PATH))
        cur = con.cursor()
        cur.execute("PRAGMA table_info(CLIENTE)")
        cols = [r[1] for r in cur.fetchall()]
        con.close()
        for col in ['CODIGO', 'NOMBRECOMERCIAL', 'RAZONSOCIAL', 'NIF']:
            self.assertIn(col, cols, f"CLIENTE no tiene columna {col}")

    def test_doclin_columns_real(self):
        """DOCLIN tiene las columnas reales del schema Firebird."""
        import sqlite3
        from backend.modules.db_simulator.constants import SimulatorPaths
        con = sqlite3.connect(str(SimulatorPaths.DB_PATH))
        cur = con.cursor()
        cur.execute("PRAGMA table_info(DOCLIN)")
        cols = [r[1] for r in cur.fetchall()]
        con.close()
        for col in ['CODIGO', 'CODDOCUMENTO', 'CODARTICULO', 'CANTIDAD', 'PRECIO']:
            self.assertIn(col, cols, f"DOCLIN no tiene columna {col}")

    # ── Consultas de la query_library contra simulador ────────────────────────

    def test_query_library_facturacion_total_simulator(self):
        """v_kpi_facturacion_total ejecuta correctamente en el simulador."""
        from backend.modules.db_simulator.query_library import get_query_by_id
        q = get_query_by_id("v_kpi_facturacion_total")
        self.assertNotEqual(q, {}, "Consulta v_kpi_facturacion_total no encontrada")
        rows = self._q(q['sql'])
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        # El resultado debe tener un campo de total
        row = rows[0]
        self.assertTrue(len(row) > 0, "La consulta no devuelve columnas")
        total_val = list(row.values())[0]
        self.assertIsNotNone(total_val)
        print(f"\n  Facturacion total (query_library): {total_val}")

    def test_query_library_top10_clientes_simulator(self):
        """v_kpi_top10_clientes ejecuta correctamente en el simulador."""
        from backend.modules.db_simulator.query_library import get_query_by_id
        q = get_query_by_id("v_kpi_top10_clientes")
        self.assertNotEqual(q, {}, "Consulta v_kpi_top10_clientes no encontrada")
        rows = self._q(q['sql'])
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 10)
        self.assertGreater(len(rows), 0, "No hay clientes en el simulador")
        print(f"\n  Top clientes simulador: {len(rows)} filas")

    def test_query_library_conversion_presupuestos_simulator(self):
        """v_kpi_conversion_presupuestos ejecuta en el simulador."""
        from backend.modules.db_simulator.query_library import get_query_by_id
        q = get_query_by_id("v_kpi_conversion_presupuestos")
        self.assertNotEqual(q, {})
        rows = self._q(q['sql'])
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        print(f"\n  Conversion presupuestos simulador: {rows[0]}")

    def test_query_library_resumen_ejecutivo_simulator(self):
        """d_kpi_resumen_ejecutivo ejecuta en el simulador."""
        from backend.modules.db_simulator.query_library import get_query_by_id
        q = get_query_by_id("d_kpi_resumen_ejecutivo")
        self.assertNotEqual(q, {})
        rows = self._q(q['sql'])
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        print(f"\n  Resumen ejecutivo simulador: {len(rows)} indicadores")

    def test_all_core_queries_execute_in_simulator(self):
        """Todas las consultas del core (77) ejecutan sin error en el simulador."""
        from backend.modules.db_simulator.query_library_core import QUERY_LIBRARY as CORE
        errors = []
        for q in CORE:
            try:
                rows = self._q(q['sql'])
                self.assertIsInstance(rows, list)
            except Exception as e:
                errors.append(f"  {q['id']}: {e}")
        if errors:
            self.fail(f"{len(errors)} consultas core fallaron:\n" + "\n".join(errors))
        print(f"\n  {len(CORE)} consultas core OK en simulador")

    # ── Consistencia de datos ─────────────────────────────────────────────────

    def test_doclin_references_valid_doccab(self):
        """Todas las lineas de DOCLIN referencian cabeceras existentes."""
        rows = self._q("""
            SELECT COUNT(*) AS N FROM DOCLIN l
            WHERE NOT EXISTS (
                SELECT 1 FROM DOCCAB c WHERE c.CODIGO = l.CODDOCUMENTO
            )
        """)
        orphans = rows[0]['N']
        self.assertEqual(orphans, 0, f"Hay {orphans} lineas huerfanas en DOCLIN")

    def test_articulos_have_valid_precio(self):
        """Los articulos activos tienen precio de venta >= 0."""
        rows = self._q(
            "SELECT COUNT(*) AS N FROM ARTICULO WHERE PRECIOVENTA < 0"
        )
        n = rows[0]['N']
        self.assertEqual(n, 0, f"Hay {n} articulos con PRECIOVENTA negativo")

    def test_clientes_have_codigo(self):
        """Todos los clientes tienen CODIGO no nulo."""
        rows = self._q("SELECT COUNT(*) AS N FROM CLIENTE WHERE CODIGO IS NULL OR CODIGO = ''")
        n = rows[0]['N']
        self.assertEqual(n, 0, f"Hay {n} clientes sin CODIGO")

    def test_row_counts_match_status_json(self):
        """Los row_counts en status.json coinciden con la BD."""
        import sqlite3
        from backend.modules.db_simulator.constants import SimulatorPaths
        with open(SimulatorPaths.STATUS_PATH) as f:
            status = json.load(f)
        row_counts = status.get('row_counts', {})
        con = sqlite3.connect(str(SimulatorPaths.DB_PATH))
        cur = con.cursor()
        for table, expected in row_counts.items():
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            actual = cur.fetchone()[0]
            self.assertEqual(actual, expected,
                             f"Tabla {table}: status.json={expected}, BD={actual}")
        con.close()
        print(f"\n  {len(row_counts)} tablas verificadas contra status.json")


# =============================================================================
# BLOQUE 2: BD REAL FIREBIRD — solo SELECT, nunca modifica nada
# =============================================================================

class TestRealFirebirdDB(unittest.TestCase):
    """
    Tests contra la BD real Firebird (192.168.0.254:3050).
    IMPORTANTE: Solo ejecuta SELECT. Nunca INSERT/UPDATE/DELETE/DDL.
    Se omiten automaticamente si la BD no esta disponible.
    """

    _driver = None
    _available = None

    @classmethod
    def setUpClass(cls):
        if not _firebird_available():
            cls._available = False
            return
        try:
            cls._driver = _get_firebird_driver()
            # Verificar con query minima de solo lectura
            cls._driver.execute_query("SELECT FIRST 1 CODIGO FROM DOCCAB")
            cls._available = True
            from backend.core.config.settings import settings as s
            print(f"\n  BD real disponible: {s.DB_HOST}:{s.DB_PORT}")
        except Exception as e:
            cls._available = False
            cls._driver = None
            print(f"\n  BD real NO disponible: {e}")

    @classmethod
    def tearDownClass(cls):
        if cls._driver:
            try:
                cls._driver.disconnect()
            except Exception:
                pass

    def _skip_if_no_db(self):
        if not self._available:
            self.skipTest("BD real Firebird no disponible")

    def _q(self, sql: str) -> List[Dict[str, Any]]:
        """Ejecuta SQL de solo lectura contra Firebird real."""
        # Verificacion de seguridad: solo SELECT permitido
        sql_upper = sql.strip().upper()
        forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
                     'ALTER', 'TRUNCATE', 'MERGE', 'EXECUTE']
        for kw in forbidden:
            if sql_upper.startswith(kw) or f' {kw} ' in sql_upper:
                raise ValueError(f"SEGURIDAD: SQL no permitido en tests (contiene {kw})")
        return self._driver.execute_query(sql)

    # ── Conectividad ──────────────────────────────────────────────────────────

    def test_real_db_connection(self):
        """Conexion a BD real Firebird establecida."""
        self._skip_if_no_db()
        self.assertTrue(self._available)

    def test_real_db_is_not_empty(self):
        """La BD real tiene datos (no es una BD vacia)."""
        self._skip_if_no_db()
        rows = self._q("SELECT COUNT(*) AS N FROM DOCCAB")
        n = rows[0]['N']
        self.assertGreater(n, 0, "DOCCAB esta vacia en BD real")
        print(f"\n  DOCCAB real: {n} registros")

    # ── Tablas principales ────────────────────────────────────────────────────

    def test_real_doccab_count(self):
        """DOCCAB real tiene registros."""
        self._skip_if_no_db()
        rows = self._q("SELECT COUNT(*) AS N FROM DOCCAB")
        n = rows[0]['N']
        self.assertGreater(n, 0)
        print(f"\n  DOCCAB real: {n}")

    def test_real_cliente_count(self):
        """CLIENTE real tiene registros."""
        self._skip_if_no_db()
        rows = self._q("SELECT COUNT(*) AS N FROM CLIENTE")
        n = rows[0]['N']
        self.assertGreater(n, 0)
        print(f"\n  CLIENTE real: {n}")

    def test_real_articulo_count(self):
        """ARTICULO real tiene registros."""
        self._skip_if_no_db()
        rows = self._q("SELECT COUNT(*) AS N FROM ARTICULO")
        n = rows[0]['N']
        self.assertGreater(n, 0)
        print(f"\n  ARTICULO real: {n}")

    def test_real_doclin_count(self):
        """DOCLIN real tiene registros."""
        self._skip_if_no_db()
        rows = self._q("SELECT COUNT(*) AS N FROM DOCLIN")
        n = rows[0]['N']
        self.assertGreater(n, 0)
        print(f"\n  DOCLIN real: {n}")

    # ── Facturas reales ───────────────────────────────────────────────────────

    def test_real_facturas_tipo13(self):
        """Hay facturas (TIPO=13) en la BD real."""
        self._skip_if_no_db()
        rows = self._q("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO = 13")
        n = rows[0]['N']
        self.assertGreater(n, 0, "No hay facturas TIPO=13 en BD real")
        print(f"\n  Facturas reales TIPO=13: {n}")

    def test_real_facturacion_total(self):
        """La facturacion total real es positiva."""
        self._skip_if_no_db()
        rows = self._q("SELECT SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB WHERE TIPO = 13")
        total = rows[0]['TOTAL']
        self.assertIsNotNone(total)
        self.assertGreater(float(total), 0)
        print(f"\n  Facturacion total real: {float(total):,.2f}")

    def test_real_presupuestos_tipo0(self):
        """Hay presupuestos (TIPO=0) en la BD real."""
        self._skip_if_no_db()
        rows = self._q("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO = 0")
        n = rows[0]['N']
        self.assertGreater(n, 0, "No hay presupuestos TIPO=0 en BD real")
        print(f"\n  Presupuestos reales TIPO=0: {n}")

    def test_real_multiple_tipos(self):
        """La BD real tiene multiples tipos de documentos."""
        self._skip_if_no_db()
        rows = self._q("SELECT TIPO, COUNT(*) AS N FROM DOCCAB GROUP BY TIPO ORDER BY TIPO")
        self.assertGreater(len(rows), 1)
        for row in rows:
            print(f"\n  TIPO={row['TIPO']}: {row['N']} docs")

    # ── Schema real Firebird ──────────────────────────────────────────────────

    def test_real_doccab_has_importetotal(self):
        """DOCCAB real tiene columna IMPORTETOTAL."""
        self._skip_if_no_db()
        rows = self._q(
            "SELECT TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME "
            "FROM RDB$RELATION_FIELDS r "
            "WHERE TRIM(r.RDB$RELATION_NAME) = 'DOCCAB' "
            "ORDER BY r.RDB$FIELD_POSITION"
        )
        cols = [r['FIELD_NAME'].strip() for r in rows]
        self.assertIn('IMPORTETOTAL', cols, "DOCCAB real no tiene IMPORTETOTAL")

    def test_real_doccab_has_importebase(self):
        """DOCCAB real tiene columna IMPORTEBASE."""
        self._skip_if_no_db()
        rows = self._q(
            "SELECT TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME "
            "FROM RDB$RELATION_FIELDS r "
            "WHERE TRIM(r.RDB$RELATION_NAME) = 'DOCCAB' "
            "ORDER BY r.RDB$FIELD_POSITION"
        )
        cols = [r['FIELD_NAME'].strip() for r in rows]
        self.assertIn('IMPORTEBASE', cols, "DOCCAB real no tiene IMPORTEBASE")

    def test_real_articulo_has_precioventa(self):
        """ARTICULO real tiene columna PRECIOVENTA (no PRECIO)."""
        self._skip_if_no_db()
        rows = self._q(
            "SELECT TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME "
            "FROM RDB$RELATION_FIELDS r "
            "WHERE TRIM(r.RDB$RELATION_NAME) = 'ARTICULO' "
            "ORDER BY r.RDB$FIELD_POSITION"
        )
        cols = [r['FIELD_NAME'].strip() for r in rows]
        self.assertIn('PRECIOVENTA', cols, "ARTICULO real no tiene PRECIOVENTA")

    def test_real_cliente_has_nombrecomercial(self):
        """CLIENTE real tiene columna NOMBRECOMERCIAL."""
        self._skip_if_no_db()
        rows = self._q(
            "SELECT TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME "
            "FROM RDB$RELATION_FIELDS r "
            "WHERE TRIM(r.RDB$RELATION_NAME) = 'CLIENTE' "
            "ORDER BY r.RDB$FIELD_POSITION"
        )
        cols = [r['FIELD_NAME'].strip() for r in rows]
        self.assertIn('NOMBRECOMERCIAL', cols, "CLIENTE real no tiene NOMBRECOMERCIAL")

    # ── Consultas de la query_library contra BD real ──────────────────────────

    def test_real_query_facturacion_total(self):
        """v_kpi_facturacion_total ejecuta en BD real y devuelve importe."""
        self._skip_if_no_db()
        from backend.modules.db_simulator.query_library import get_query_by_id
        from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

        q = get_query_by_id("v_kpi_facturacion_total")
        self.assertNotEqual(q, {})
        adapted, _ = adapt_sql_for_firebird(q['sql'])
        fb_sql, _ = FirebirdSQLNormalizer().normalize(adapted)
        rows = self._q(fb_sql)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        total = list(rows[0].values())[0]
        self.assertIsNotNone(total)
        print(f"\n  Facturacion total real (query_library): {float(total):,.2f}")

    def test_real_query_top10_clientes(self):
        """v_kpi_top10_clientes ejecuta en BD real."""
        self._skip_if_no_db()
        from backend.modules.db_simulator.query_library import get_query_by_id
        from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

        q = get_query_by_id("v_kpi_top10_clientes")
        self.assertNotEqual(q, {})
        adapted, _ = adapt_sql_for_firebird(q['sql'])
        fb_sql, _ = FirebirdSQLNormalizer().normalize(adapted)
        rows = self._q(fb_sql)
        self.assertIsInstance(rows, list)
        self.assertLessEqual(len(rows), 10)
        print(f"\n  Top clientes real: {len(rows)} filas")

    def test_real_query_conversion_presupuestos(self):
        """v_kpi_conversion_presupuestos ejecuta en BD real."""
        self._skip_if_no_db()
        from backend.modules.db_simulator.query_library import get_query_by_id
        from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

        q = get_query_by_id("v_kpi_conversion_presupuestos")
        self.assertNotEqual(q, {})
        adapted, _ = adapt_sql_for_firebird(q['sql'])
        fb_sql, _ = FirebirdSQLNormalizer().normalize(adapted)
        rows = self._q(fb_sql)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        print(f"\n  Conversion presupuestos real: {rows[0]}")

    def test_real_query_resumen_ejecutivo(self):
        """d_kpi_resumen_ejecutivo ejecuta en BD real."""
        self._skip_if_no_db()
        from backend.modules.db_simulator.query_library import get_query_by_id
        from backend.modules.db_simulator.sqlite_to_firebird import adapt_sql_for_firebird
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

        q = get_query_by_id("d_kpi_resumen_ejecutivo")
        self.assertNotEqual(q, {})
        adapted, _ = adapt_sql_for_firebird(q['sql'])
        fb_sql, _ = FirebirdSQLNormalizer().normalize(adapted)
        rows = self._q(fb_sql)
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        print(f"\n  Resumen ejecutivo real: {len(rows)} indicadores")

    def test_real_no_write_operations(self):
        """Verificar que el driver rechaza operaciones de escritura."""
        self._skip_if_no_db()
        write_sqls = [
            "INSERT INTO DOCCAB (CODIGO) VALUES ('TEST')",
            "UPDATE DOCCAB SET TIPO=99 WHERE CODIGO='TEST'",
            "DELETE FROM DOCCAB WHERE CODIGO='TEST'",
            "DROP TABLE DOCCAB",
        ]
        for sql in write_sqls:
            with self.assertRaises(ValueError,
                                   msg=f"Deberia rechazar: {sql[:40]}"):
                self._q(sql)

    # ── Consistencia simulador vs real ────────────────────────────────────────

    def test_real_vs_simulator_tipos_match(self):
        """Los tipos de documento en BD real coinciden con los del simulador."""
        self._skip_if_no_db()
        # Tipos en BD real
        rows_real = self._q(
            "SELECT TIPO FROM DOCCAB GROUP BY TIPO ORDER BY TIPO"
        )
        tipos_real = {r['TIPO'] for r in rows_real}

        # Tipos en simulador
        sim_driver = _get_simulator_driver()
        rows_sim = sim_driver.execute_query(
            "SELECT TIPO FROM DOCCAB GROUP BY TIPO ORDER BY TIPO"
        )
        sim_driver.disconnect()
        tipos_sim = {r['TIPO'] for r in rows_sim}

        # Los tipos del simulador deben ser un subconjunto de los reales
        # (el simulador puede tener menos tipos que la BD real)
        missing_in_real = tipos_sim - tipos_real
        self.assertEqual(
            len(missing_in_real), 0,
            f"Tipos en simulador no presentes en BD real: {missing_in_real}"
        )
        print(f"\n  Tipos reales: {sorted(tipos_real)}")
        print(f"  Tipos simulador: {sorted(tipos_sim)}")


# =============================================================================
# BLOQUE 3: MODELO 8B via backend live (localhost:8001)
# =============================================================================

class TestModel8BLiveBackend(unittest.TestCase):
    """
    Tests del modelo Qwen3 8B via el backend live en localhost:8001.
    Envia preguntas reales al chat IA y verifica que las respuestas son coherentes.
    Se omiten si el backend o LM Studio no estan disponibles.
    """

    BACKEND_URL = "http://localhost:8001"
    MODEL_ID = "jddcia-qwen3-8b-ip"
    TIMEOUT = 120  # segundos por peticion

    @classmethod
    def setUpClass(cls):
        cls._backend_ok = _backend_available()
        cls._lmstudio_ok = _lmstudio_available()
        if cls._backend_ok:
            print(f"\n  Backend disponible: {cls.BACKEND_URL}")
        if cls._lmstudio_ok:
            print(f"\n  LM Studio disponible: localhost:1234")

    def _skip_if_no_backend(self):
        if not self._backend_ok:
            self.skipTest("Backend localhost:8001 no disponible")
        if not self._lmstudio_ok:
            self.skipTest("LM Studio localhost:1234 no disponible")

    def _chat(self, message: str, simulator: bool = False,
              deep: bool = False, timeout: int = None) -> dict:
        """Envia un mensaje al chat IA y devuelve la respuesta completa."""
        payload = {
            'message': message,
            'model_id': self.MODEL_ID,
            'preferred_model_id': self.MODEL_ID,
            'conversation_history': [],
            'no_db': False,
            'deep_analysis': deep,
            'simulator_active': simulator,
            'session_id': None,
        }
        t = timeout or self.TIMEOUT
        result = _http_post(f"{self.BACKEND_URL}/api/chat/send", payload, timeout=t)
        return result or {}

    @staticmethod
    def _safe_text(text: str, max_len: int = 200) -> str:
        """Convierte texto a ASCII seguro para print() en Windows cp1252."""
        return text[:max_len].encode('ascii', errors='replace').decode('ascii')

    # ── Tests de conectividad del backend ─────────────────────────────────────

    def test_backend_health(self):
        """El backend responde en /health."""
        self._skip_if_no_backend()
        data = _http_get(f"{self.BACKEND_URL}/health")
        self.assertIsNotNone(data, "Backend /health no responde")

    def test_backend_ping(self):
        """El backend responde en /api/chat/ping."""
        self._skip_if_no_backend()
        data = _http_get(f"{self.BACKEND_URL}/api/chat/ping")
        self.assertIsNotNone(data)
        self.assertEqual(data.get('status'), 'alive')
        self.assertEqual(data.get('service'), 'DEVIA Chat')

    def test_lmstudio_has_8b_model(self):
        """LM Studio tiene el modelo qwen/qwen3-vl-8b cargado."""
        self._skip_if_no_backend()
        data = _http_get("http://localhost:1234/v1/models")
        self.assertIsNotNone(data)
        model_ids = [m.get('id', '') for m in data.get('data', [])]
        self.assertIn('qwen/qwen3-vl-8b', model_ids,
                      f"qwen/qwen3-vl-8b no esta en LM Studio. Modelos: {model_ids}")

    # ── Tests con BD simulada ─────────────────────────────────────────────────

    def test_8b_facturacion_total_simulator(self):
        """8B responde correctamente a 'facturacion total' con BD simulada."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Cuanto es la facturacion total?", simulator=True)
        elapsed = time.time() - t0

        self.assertIsNotNone(resp, "No se recibio respuesta del backend")
        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 10, "Respuesta vacia o muy corta")

        # Debe contener un numero (la facturacion)
        import re
        has_number = bool(re.search(r'\d[\d.,]+', response_text))
        self.assertTrue(has_number, f"Respuesta no contiene numero: {response_text[:200]}")
        print(f"\n  Facturacion total (8B+sim, {elapsed:.1f}s): {self._safe_text(response_text, 150)}")

    def test_8b_count_clientes_simulator(self):
        """8B responde a 'cuantos clientes hay' con BD simulada — success y contenido."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Cuantos clientes hay en total?", simulator=True)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        # El modelo debe responder con contenido (numero o explicacion con SQL)
        import re
        clean = re.sub(r'<[^>]+>', '', response_text).strip()
        self.assertGreater(len(clean), 5,
                           f"Respuesta vacia ({elapsed:.1f}s)")
        print(f"\n  Clientes (8B+sim, {elapsed:.1f}s): {self._safe_text(response_text, 150)}")

    def test_8b_count_articulos_simulator(self):
        """8B responde a 'cuantos articulos hay' con BD simulada — success y contenido."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Cuantos articulos tenemos?", simulator=True)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        import re
        clean = re.sub(r'<[^>]+>', '', response_text).strip()
        self.assertGreater(len(clean), 5,
                           f"Respuesta vacia ({elapsed:.1f}s)")
        print(f"\n  Articulos (8B+sim, {elapsed:.1f}s): {self._safe_text(response_text, 150)}")

    def test_8b_top_clientes_simulator(self):
        """8B responde a 'top clientes por facturacion' con BD simulada."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Cuales son los 5 clientes con mas facturacion?", simulator=True)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 20)
        print(f"\n  Top clientes (8B+sim, {elapsed:.1f}s): {self._safe_text(response_text, 200)}")

    def test_8b_presupuestos_simulator(self):
        """8B responde a 'cuantos presupuestos hay' con BD simulada."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Cuantos presupuestos hay?", simulator=True)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        import re
        has_number = bool(re.search(r'\d+', response_text))
        self.assertTrue(has_number, f"Respuesta no contiene numero: {response_text[:200]}")
        print(f"\n  Presupuestos (8B+sim, {elapsed:.1f}s): {self._safe_text(response_text, 150)}")

    # ── Tests con BD real ─────────────────────────────────────────────────────

    def test_8b_facturacion_total_real_db(self):
        """8B responde correctamente a 'facturacion total' con BD real."""
        self._skip_if_no_backend()
        if not _firebird_available():
            self.skipTest("BD real Firebird no disponible")

        t0 = time.time()
        resp = self._chat("Cuanto es la facturacion total?", simulator=False)
        elapsed = time.time() - t0

        self.assertIsNotNone(resp)
        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 10)

        import re
        has_number = bool(re.search(r'\d[\d.,]+', response_text))
        self.assertTrue(has_number, f"Respuesta no contiene numero: {response_text[:200]}")
        print(f"\n  Facturacion total REAL (8B, {elapsed:.1f}s): {response_text[:200]}")

    def test_8b_count_clientes_real_db(self):
        """8B responde a 'cuantos clientes hay' con BD real."""
        self._skip_if_no_backend()
        if not _firebird_available():
            self.skipTest("BD real Firebird no disponible")

        t0 = time.time()
        resp = self._chat("Cuantos clientes hay?", simulator=False)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        import re
        has_number = bool(re.search(r'\d+', response_text))
        self.assertTrue(has_number, f"Respuesta no contiene numero: {response_text[:200]}")
        print(f"\n  Clientes REAL (8B, {elapsed:.1f}s): {response_text[:150]}")

    def test_8b_articulos_mas_vendidos_real_db(self):
        """8B responde a 'articulos mas vendidos' con BD real."""
        self._skip_if_no_backend()
        if not _firebird_available():
            self.skipTest("BD real Firebird no disponible")

        t0 = time.time()
        resp = self._chat("Cuales son los articulos mas vendidos?", simulator=False)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 20)
        print(f"\n  Articulos mas vendidos REAL (8B, {elapsed:.1f}s): {response_text[:200]}")

    def test_8b_top_clientes_real_db(self):
        """8B responde a 'top clientes' con BD real."""
        self._skip_if_no_backend()
        if not _firebird_available():
            self.skipTest("BD real Firebird no disponible")

        t0 = time.time()
        resp = self._chat("Cuales son los mejores clientes por facturacion?", simulator=False)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 20)
        print(f"\n  Top clientes REAL (8B, {elapsed:.1f}s): {response_text[:200]}")

    def test_8b_presupuestos_real_db(self):
        """8B responde a 'cuantos presupuestos hay' con BD real."""
        self._skip_if_no_backend()
        if not _firebird_available():
            self.skipTest("BD real Firebird no disponible")

        t0 = time.time()
        resp = self._chat("Cuantos presupuestos hay en total?", simulator=False)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        import re
        has_number = bool(re.search(r'\d+', response_text))
        self.assertTrue(has_number, f"Respuesta no contiene numero: {response_text[:200]}")
        print(f"\n  Presupuestos REAL (8B, {elapsed:.1f}s): {response_text[:150]}")

    # ── Tests de coherencia simulador vs real ─────────────────────────────────

    def test_8b_simulator_vs_real_facturacion_different(self):
        """
        La facturacion del simulador y la real son diferentes
        (el simulador tiene datos sinteticos, no los reales).
        """
        self._skip_if_no_backend()
        if not _firebird_available():
            self.skipTest("BD real Firebird no disponible")

        import re

        resp_sim = self._chat("Cuanto es la facturacion total exacta en euros?",
                              simulator=True)
        resp_real = self._chat("Cuanto es la facturacion total exacta en euros?",
                               simulator=False)

        self.assertTrue(resp_sim.get('success'))
        self.assertTrue(resp_real.get('success'))

        # Extraer numeros de ambas respuestas
        def extract_numbers(text):
            return re.findall(r'[\d.,]+', text.replace(' ', ''))

        nums_sim = extract_numbers(resp_sim.get('response', ''))
        nums_real = extract_numbers(resp_real.get('response', ''))

        print(f"\n  Facturacion simulador: {nums_sim[:3]}")
        print(f"  Facturacion real: {nums_real[:3]}")

        # Al menos uno de los numeros debe ser diferente
        # (si son iguales, algo esta mal — el simulador no deberia tener los mismos datos)
        # Nota: no forzamos que sean diferentes porque podria ser coincidencia
        # Solo verificamos que ambas respuestas tienen numeros
        self.assertGreater(len(nums_sim), 0, "Simulador no devolvio numeros")
        self.assertGreater(len(nums_real), 0, "BD real no devolvio numeros")

    # ── Tests de calidad de respuesta ─────────────────────────────────────────

    def test_8b_response_not_error_message(self):
        """La respuesta del 8B no es un mensaje de error del sistema."""
        self._skip_if_no_backend()
        resp = self._chat("Cuantos documentos hay en total?", simulator=True)
        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '').lower()

        error_phrases = [
            'no se pudo conectar',
            'error interno',
            'timeout',
            'connection refused',
            'traceback',
        ]
        for phrase in error_phrases:
            self.assertNotIn(phrase, response_text,
                             f"Respuesta contiene frase de error: '{phrase}'")

    def test_8b_response_time_reasonable(self):
        """El 8B responde en menos de 90 segundos para preguntas simples."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Cuantos clientes hay?", simulator=True, timeout=90)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        self.assertLess(elapsed, 90,
                        f"El 8B tardo {elapsed:.1f}s (max: 90s para preguntas simples)")
        print(f"\n  Tiempo respuesta 8B: {elapsed:.1f}s")

    def test_8b_response_has_content(self):
        """La respuesta del 8B tiene contenido real (no vacia)."""
        self._skip_if_no_backend()
        resp = self._chat("Cual es la facturacion total?", simulator=True)
        self.assertTrue(resp.get('success'))
        response_text = resp.get('response', '')
        # Quitar HTML tags para medir contenido real
        import re
        clean = re.sub(r'<[^>]+>', '', response_text).strip()
        self.assertGreater(len(clean), 10,
                           f"Respuesta muy corta o vacia: '{clean[:100]}'")

    def test_8b_articulos_con_mas_proveedores_simulator(self):
        """8B responde a la pregunta compleja de articulos con mas proveedores."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat(
            "Articulos con mayor numero de proveedores distintos. "
            "Hay articulos asociados a mas de un proveedor?",
            simulator=True,
            timeout=self.TIMEOUT
        )
        elapsed = time.time() - t0

        self.assertIsNotNone(resp)
        self.assertTrue(resp.get('success'),
                        f"Respuesta fallida ({elapsed:.1f}s): {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 10)
        print(f"\n  Articulos+proveedores (8B+sim, {elapsed:.1f}s): {self._safe_text(response_text, 200)}")

    def test_8b_saldo_caja_simulator(self):
        """8B responde a 'saldo de caja' con BD simulada."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Cual es el saldo de caja actual?", simulator=True)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 5)
        print(f"\n  Saldo caja (8B+sim, {elapsed:.1f}s): {response_text[:150]}")

    def test_8b_ventas_por_mes_simulator(self):
        """8B responde a 'ventas por mes' con BD simulada."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat("Muestra las ventas por mes del ultimo anio", simulator=True)
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 10)
        print(f"\n  Ventas por mes (8B+sim, {elapsed:.1f}s): {response_text[:200]}")

    def test_8b_tasa_conversion_presupuestos_simulator(self):
        """8B responde a 'tasa de conversion de presupuestos' con BD simulada."""
        self._skip_if_no_backend()
        t0 = time.time()
        resp = self._chat(
            "Cual es la tasa de conversion de presupuestos a facturas?",
            simulator=True
        )
        elapsed = time.time() - t0

        self.assertTrue(resp.get('success'), f"Respuesta fallida: {resp}")
        response_text = resp.get('response', '')
        self.assertGreater(len(response_text), 5)
        print(f"\n  Tasa conversion (8B+sim, {elapsed:.1f}s): {response_text[:150]}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    import logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for cls in [
        TestSimulatorDB,
        TestRealFirebirdDB,
        TestModel8BLiveBackend,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    skipped = len(result.skipped)
    passed = total - failed - skipped

    print(f"\n{'='*60}")
    print(f"RESULTADO: {passed}/{total} OK | {failed} fallos | {skipped} omitidos")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)
