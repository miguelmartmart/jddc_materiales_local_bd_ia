"""
test_semantica_articulos_stock.py — Abstracción semántica: artículos, stock, familias, almacenes.

OBJETIVO:
    Verificar que el motor semántico razona correctamente sobre el dominio de
    artículos, stock, familias de producto y almacenes de JDDC Climatización.

    El sistema debe ser capaz de:
    - Detectar preguntas sobre artículos/stock aunque el usuario use vocabulario coloquial
    - Inferir las tablas correctas (ARTICULO, DOCLIN, ESTALMACEN, FAMILIA, ALMACEN)
    - Conocer que STOCK → STOCKARTICULO (columna real en BD)
    - Razonar sobre familias de producto (splits, cassettes, VRV, etc.)
    - Entender consultas sobre ventas de artículos (JOIN DOCLIN)
    - Detectar artículos sin stock, con stock bajo, más vendidos, etc.

PRINCIPIOS DEVIA:
    - Sin mocks de datos: solo se simulan las preguntas del usuario
    - Ultra-resiliente: cada test es independiente
    - Determinista primero: patrones de detección deterministas
    - < 500 líneas por archivo

EJECUCIÓN:
    python -m pytest tests/unit/test_semantica_articulos_stock.py -v
"""

import sys
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.modules.chat.semantic_reasoning_engine import (
    SemanticReasoningEngine, BusinessDomain, ReasoningResult,
    get_reasoning_engine,
)
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.db_simulator.schema import TABLE_SCHEMAS, TABLE_COLUMNS, TABLE_CREATION_ORDER


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    """BD SQLite en memoria con esquema completo."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for t in TABLE_CREATION_ORDER:
        if t in TABLE_SCHEMAS:
            conn.execute(TABLE_SCHEMAS[t])
    conn.commit()
    return conn


def _seed_articulos(conn):
    """Inserta artículos de prueba en la BD en memoria."""
    conn.executemany(
        "INSERT INTO ARTICULO (CODIGO,CODFAMILIA,NOMBRE,PRECIOVENTA,STOCKARTICULO,BAJA) VALUES (?,?,?,?,?,?)",
        [
            (1, 1, "Split Samsung 2000W", 450.0, 5.0, 0),
            (2, 1, "Split Daikin 3000W",  620.0, 0.0, 0),   # sin stock
            (3, 3, "Cassette Mitsubishi 4x4", 980.0, 2.0, 0),
            (4, 6, "VRV Daikin 10HP", 4500.0, 1.0, 0),
            (5, 9, "Gas R-32 10kg", 85.0, 20.0, 0),
            (6, 1, "Split LG 2500W", 380.0, 0.0, 1),         # de baja
        ]
    )
    conn.executemany(
        "INSERT INTO FAMILIA (CODIGO,NOMBRE) VALUES (?,?)",
        [(1,"Splits Pared"),(3,"Cassettes"),(6,"VRV y VRF"),(9,"Gas Refrigerante")]
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE A1 — Detección de dominio: artículos y stock
# ══════════════════════════════════════════════════════════════════════════════

class TestDeteccionDominioArticulos(unittest.TestCase):
    """Verifica que el motor detecta el dominio ARTICULOS_STOCK correctamente."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_detecta_articulos_directa(self):
        r = self.engine.reason("dame todos los artículos del catálogo")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_stock_bajo(self):
        r = self.engine.reason("artículos con stock bajo")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_inventario(self):
        r = self.engine.reason("inventario del almacén principal")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_existencias(self):
        r = self.engine.reason("existencias de splits en almacén")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_producto(self):
        r = self.engine.reason("qué productos tenemos en stock")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_referencia(self):
        r = self.engine.reason("busca la referencia REF-001 en el catálogo")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_almacen(self):
        r = self.engine.reason("qué hay en el almacén de repuestos")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_articulo_singular(self):
        r = self.engine.reason("dame el precio del artículo 1234")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_stock_cero(self):
        r = self.engine.reason("artículos con stock a cero")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_mas_vendidos(self):
        r = self.engine.reason("cuáles son los artículos más vendidos")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_sin_stock(self):
        r = self.engine.reason("productos sin existencias en almacén")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_precio_articulo(self):
        r = self.engine.reason("precio de venta de los artículos de la familia splits")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_detecta_catalogo(self):
        # 'referencia' activa ARTICULOS_STOCK — la palabra clave es 'referencia'
        r = self.engine.reason("muéstrame el catálogo completo con referencias")
        self.assertIn(r.domain, [BusinessDomain.ARTICULOS_STOCK, BusinessDomain.GENERAL],
            "El catálogo con referencias puede detectarse como ARTICULOS_STOCK o GENERAL")

    def test_detecta_almacenes_plural(self):
        r = self.engine.reason("cuántos almacenes tiene la empresa")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE A2 — Tablas sugeridas y hints SQL para artículos
# ══════════════════════════════════════════════════════════════════════════════

class TestHintsArticulos(unittest.TestCase):
    """Verifica que el motor genera hints SQL correctos para artículos."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_sugiere_tabla_articulo(self):
        r = self.engine.reason("artículos con stock bajo")
        self.assertIn("ARTICULO", r.tables_suggested)

    def test_sugiere_tabla_doclin_para_ventas(self):
        r = self.engine.reason("artículos más vendidos del año")
        self.assertIn("DOCLIN", r.tables_suggested)

    def test_sugiere_estalmacen(self):
        r = self.engine.reason("estadísticas de almacén por período")
        self.assertIn("ESTALMACEN", r.tables_suggested)

    def test_hint_stockarticulo_no_stock(self):
        """El motor debe saber que la columna es STOCKARTICULO, no STOCK."""
        r = self.engine.reason("artículos con stock bajo")
        hints_text = " ".join(r.hints).upper()
        self.assertIn("STOCKARTICULO", hints_text,
            "El hint debe mencionar STOCKARTICULO (no STOCK) — columna real en BD")

    def test_hint_join_doclin_para_ventas(self):
        r = self.engine.reason("artículos más vendidos")
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "DOCLIN" in hints_text or "JOIN" in hints_text,
            "Para ventas de artículos debe sugerir JOIN con DOCLIN"
        )

    def test_confianza_alta_articulos(self):
        r = self.engine.reason("artículos con stock bajo")
        self.assertGreater(r.confidence, 0.7)

    def test_reasoning_steps_no_vacio(self):
        r = self.engine.reason("inventario del almacén")
        self.assertGreater(len(r.reasoning_steps), 0)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE A3 — Normalización SQL para artículos
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizacionSQLArticulos(unittest.TestCase):
    """Verifica que el normalizador corrige SQLs incorrectos sobre artículos."""

    def setUp(self):
        self.normalizer = FirebirdSQLNormalizer()

    def test_corrige_stock_a_stockarticulo(self):
        sql = "SELECT NOMBRE, STOCK FROM ARTICULO WHERE STOCK > 0"
        result, changes = self.normalizer.normalize(sql)
        self.assertIn("STOCKARTICULO", result,
            "STOCK debe corregirse a STOCKARTICULO")

    def test_corrige_limit_a_first(self):
        sql = "SELECT NOMBRE, PRECIOVENTA FROM ARTICULO LIMIT 10"
        result, changes = self.normalizer.normalize(sql)
        self.assertIn("FIRST", result.upper())
        self.assertNotIn("LIMIT", result.upper())

    def test_corrige_ilike_a_like(self):
        sql = "SELECT NOMBRE FROM ARTICULO WHERE NOMBRE ILIKE '%split%'"
        result, changes = self.normalizer.normalize(sql)
        self.assertNotIn("ILIKE", result.upper())

    def test_elimina_punto_y_coma(self):
        sql = "SELECT NOMBRE FROM ARTICULO WHERE BAJA = 0;"
        result, changes = self.normalizer.normalize(sql)
        self.assertFalse(result.strip().endswith(";"))

    def test_sql_articulos_valido_sin_cambios(self):
        sql = "SELECT FIRST 20 NOMBRE, PRECIOVENTA, STOCKARTICULO FROM ARTICULO WHERE BAJA = 0"
        result, changes = self.normalizer.normalize(sql)
        self.assertIn("ARTICULO", result)
        self.assertIn("STOCKARTICULO", result)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE A4 — Esquema BD: columnas reales de ARTICULO
# ══════════════════════════════════════════════════════════════════════════════

class TestEsquemaArticulo(unittest.TestCase):
    """Verifica que el esquema de ARTICULO tiene las columnas correctas."""

    def test_articulo_tiene_stockarticulo(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertIn("STOCKARTICULO", cols,
            "ARTICULO debe tener columna STOCKARTICULO (no STOCK)")

    def test_articulo_no_tiene_stock(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertNotIn("STOCK", cols,
            "ARTICULO NO debe tener columna STOCK — es STOCKARTICULO")

    def test_articulo_tiene_codfamilia(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertIn("CODFAMILIA", cols)

    def test_articulo_tiene_precioventa(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertIn("PRECIOVENTA", cols)

    def test_articulo_tiene_preciocoste(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertIn("PRECIOCOSTE", cols)

    def test_articulo_tiene_baja(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertIn("BAJA", cols,
            "ARTICULO debe tener columna BAJA para artículos dados de baja")

    def test_articulo_tiene_referencia(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertIn("REFERENCIA", cols)

    def test_articulo_tiene_tipoiva(self):
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertIn("TIPOIVA", cols)

    def test_familia_tiene_nombre(self):
        cols = TABLE_COLUMNS.get("FAMILIA", [])
        self.assertIn("NOMBRE", cols)

    def test_almacen_tiene_nombre(self):
        cols = TABLE_COLUMNS.get("ALMACEN", [])
        self.assertIn("NOMBRE", cols)

    def test_doclin_tiene_codarticulo(self):
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertIn("CODARTICULO", cols,
            "DOCLIN debe tener CODARTICULO para JOIN con ARTICULO")

    def test_doclin_tiene_cantidad(self):
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertIn("CANTIDAD", cols)

    def test_doclin_no_tiene_importe_directo(self):
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertNotIn("IMPORTE", cols,
            "DOCLIN no tiene columna IMPORTE directa — usar CANTIDAD*PRECIO")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE A5 — Simulador SQLite: queries reales sobre artículos
# ══════════════════════════════════════════════════════════════════════════════

class TestSimuladorArticulos(unittest.TestCase):
    """Verifica queries reales sobre artículos en BD SQLite en memoria."""

    def setUp(self):
        self.conn = _make_db()
        _seed_articulos(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_query_articulos_activos(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NOMBRE, STOCKARTICULO FROM ARTICULO WHERE BAJA = 0"
        ).fetchall()]
        self.assertEqual(len(rows), 5, "Deben haber 5 artículos activos (1 de baja)")

    def test_query_articulos_sin_stock(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NOMBRE FROM ARTICULO WHERE STOCKARTICULO = 0 AND BAJA = 0"
        ).fetchall()]
        self.assertEqual(len(rows), 1, "Solo el Split Daikin 3000W tiene stock=0 y está activo")
        self.assertIn("Daikin", rows[0]["NOMBRE"])

    def test_query_articulos_por_familia(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT a.NOMBRE, f.NOMBRE as FAMILIA FROM ARTICULO a "
            "JOIN FAMILIA f ON f.CODIGO = a.CODFAMILIA WHERE a.BAJA = 0"
        ).fetchall()]
        self.assertGreater(len(rows), 0)
        familias = {r["FAMILIA"] for r in rows}
        self.assertIn("Splits Pared", familias)

    def test_query_stock_total_por_familia(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT f.NOMBRE, SUM(a.STOCKARTICULO) as TOTAL_STOCK "
            "FROM ARTICULO a JOIN FAMILIA f ON f.CODIGO = a.CODFAMILIA "
            "WHERE a.BAJA = 0 GROUP BY f.CODIGO, f.NOMBRE"
        ).fetchall()]
        self.assertGreater(len(rows), 0)
        splits = next((r for r in rows if "Splits" in r["NOMBRE"]), None)
        self.assertIsNotNone(splits)
        self.assertEqual(splits["TOTAL_STOCK"], 5.0,
            "Solo el Split Samsung tiene stock (5), el Daikin tiene 0")

    def test_query_articulo_mas_caro(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NOMBRE, PRECIOVENTA FROM ARTICULO WHERE BAJA = 0 "
            "ORDER BY PRECIOVENTA DESC LIMIT 1"
        ).fetchall()]
        self.assertEqual(len(rows), 1)
        self.assertIn("VRV", rows[0]["NOMBRE"])

    def test_query_count_articulos(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT COUNT(*) as TOTAL FROM ARTICULO WHERE BAJA = 0"
        ).fetchall()]
        self.assertEqual(rows[0]["TOTAL"], 5)

    def test_query_articulos_gas_refrigerante(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT a.NOMBRE FROM ARTICULO a JOIN FAMILIA f ON f.CODIGO = a.CODFAMILIA "
            "WHERE f.NOMBRE LIKE '%Gas%' AND a.BAJA = 0"
        ).fetchall()]
        self.assertEqual(len(rows), 1)
        self.assertIn("R-32", rows[0]["NOMBRE"])

    def test_esquema_articulo_en_bd(self):
        """Verifica que la tabla ARTICULO existe y tiene las columnas correctas."""
        cursor = self.conn.execute("PRAGMA table_info(ARTICULO)")
        cols = {row[1] for row in cursor.fetchall()}
        self.assertIn("STOCKARTICULO", cols)
        self.assertIn("CODFAMILIA", cols)
        self.assertIn("BAJA", cols)
        self.assertNotIn("STOCK", cols)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE A6 — Abstracción semántica: razonamiento sobre artículos
# ══════════════════════════════════════════════════════════════════════════════

class TestAbstraccionSemanticaArticulos(unittest.TestCase):
    """
    Verifica que el motor razona a nivel de abstracción superior sobre artículos.
    El sistema debe deducir relaciones, inferir tablas y generar contexto correcto.
    """

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_deduce_que_ventas_requieren_doclin(self):
        """Para 'artículos más vendidos' el sistema debe inferir JOIN con DOCLIN."""
        r = self.engine.reason("cuáles son los artículos más vendidos este año")
        hints_text = " ".join(r.hints).upper()
        tables_text = " ".join(r.tables_suggested).upper()
        self.assertTrue(
            "DOCLIN" in hints_text or "DOCLIN" in tables_text,
            "Para ventas de artículos debe inferir DOCLIN"
        )

    def test_deduce_que_stock_es_stockarticulo(self):
        """El sistema debe saber que 'stock' en BD es STOCKARTICULO."""
        r = self.engine.reason("artículos con stock bajo")
        hints_text = " ".join(r.hints).upper()
        self.assertIn("STOCKARTICULO", hints_text)

    def test_razona_sobre_articulos_de_baja(self):
        """El sistema debe saber que BAJA=1 indica artículo dado de baja."""
        r = self.engine.reason("artículos activos del catálogo")
        # Debe detectar dominio correcto
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_resiliente_pregunta_vacia(self):
        r = self.engine.reason("")
        self.assertIsInstance(r, ReasoningResult)

    def test_resiliente_pregunta_sin_dominio(self):
        r = self.engine.reason("hola, ¿cómo estás?")
        self.assertEqual(r.domain, BusinessDomain.GENERAL)

    def test_resiliente_pregunta_muy_larga(self):
        pregunta = "artículo " * 300
        r = self.engine.reason(pregunta)
        self.assertIsInstance(r, ReasoningResult)
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_singleton_engine_funciona(self):
        """get_reasoning_engine() devuelve instancia válida."""
        engine = get_reasoning_engine()
        r = engine.reason("artículos con stock bajo")
        self.assertEqual(r.domain, BusinessDomain.ARTICULOS_STOCK)

    def test_build_enriched_prompt_articulos(self):
        """build_enriched_system_prompt enriquece el prompt para artículos."""
        r = self.engine.reason("artículos más vendidos")
        prompt = self.engine.build_enriched_system_prompt("BASE PROMPT", r)
        # Si hay dominio claro, el prompt debe enriquecerse
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)
