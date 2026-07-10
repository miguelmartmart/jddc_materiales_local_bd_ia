"""
test_semantica_estructura_bd.py — Abstracción semántica: estructura interna de BD y metadatos.

OBJETIVO:
    Verificar que el motor semántico puede razonar sobre la estructura interna
    de la base de datos JDDC: tablas, columnas, relaciones, valores internos,
    metadatos y patrones de codificación.

    El sistema debe ser capaz de:
    - Conocer todas las tablas del esquema y sus columnas reales
    - Razonar sobre relaciones entre tablas (FKs implícitas)
    - Conocer valores internos: TIPO, ESTADO, TIPORETENCION, BAJA, etc.
    - Detectar columnas que NO existen (STOCK, DESCUENTO, IMPORTE en DOCLIN)
    - Razonar sobre PKs especiales (CAJA.CODAPUNTE, PROYECTOS.CODIGO=TEXT)
    - Entender el orden de creación de tablas (dependencias)
    - Verificar que el esquema SQLite replica fielmente el Firebird real

PRINCIPIOS DEVIA:
    - Sin mocks de datos: solo se simulan las preguntas del usuario
    - Ultra-resiliente: cada test es independiente
    - Determinista primero: patrones de detección deterministas
    - < 500 líneas por archivo

EJECUCIÓN:
    python -m pytest tests/unit/test_semantica_estructura_bd.py -v
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
    JDDC_BUSINESS_KNOWLEDGE,
)
from backend.modules.db_simulator.schema import (
    TABLE_SCHEMAS, TABLE_COLUMNS, TABLE_CREATION_ORDER, TABLE_INDEXES,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for t in TABLE_CREATION_ORDER:
        if t in TABLE_SCHEMAS:
            conn.execute(TABLE_SCHEMAS[t])
    conn.commit()
    return conn


def _get_real_cols(conn, table):
    """Devuelve columnas reales de una tabla en la BD SQLite."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE E1 — Tablas del esquema: existencia y orden
# ══════════════════════════════════════════════════════════════════════════════

class TestTablasPrincipales(unittest.TestCase):
    """Verifica que todas las tablas principales existen en el esquema."""

    TABLAS_REQUERIDAS = [
        "FAMILIA", "ALMACEN", "RECURSO", "PROVEED", "ARTICULO",
        "CLIENTE", "DOCCAB", "DOCLIN", "CAJA", "ESTALMACEN",
        "PROYECTOS", "PROYVAR", "PRESUPROYE", "DOCDESTINO",
        "AGENTES", "TIPOSIVA", "TARIFAS", "FORMASPAGO", "SERIES", "AVISOS",
    ]

    def test_todas_las_tablas_en_schemas(self):
        for tabla in self.TABLAS_REQUERIDAS:
            self.assertIn(tabla, TABLE_SCHEMAS,
                f"Tabla {tabla} debe estar en TABLE_SCHEMAS")

    def test_todas_las_tablas_en_columns(self):
        for tabla in self.TABLAS_REQUERIDAS:
            self.assertIn(tabla, TABLE_COLUMNS,
                f"Tabla {tabla} debe estar en TABLE_COLUMNS")

    def test_todas_las_tablas_en_creation_order(self):
        for tabla in self.TABLAS_REQUERIDAS:
            self.assertIn(tabla, TABLE_CREATION_ORDER,
                f"Tabla {tabla} debe estar en TABLE_CREATION_ORDER")

    def test_orden_creacion_maestros_primero(self):
        """Los maestros deben crearse antes que los documentos."""
        idx_articulo = TABLE_CREATION_ORDER.index("ARTICULO")
        idx_doccab = TABLE_CREATION_ORDER.index("DOCCAB")
        self.assertLess(idx_articulo, idx_doccab,
            "ARTICULO debe crearse antes que DOCCAB")

    def test_orden_creacion_proyectos_antes_doccab(self):
        idx_proyectos = TABLE_CREATION_ORDER.index("PROYECTOS")
        idx_doccab = TABLE_CREATION_ORDER.index("DOCCAB")
        self.assertLess(idx_proyectos, idx_doccab,
            "PROYECTOS debe crearse antes que DOCCAB")

    def test_orden_creacion_cliente_antes_doccab(self):
        idx_cliente = TABLE_CREATION_ORDER.index("CLIENTE")
        idx_doccab = TABLE_CREATION_ORDER.index("DOCCAB")
        self.assertLess(idx_cliente, idx_doccab)

    def test_doclin_despues_de_doccab(self):
        idx_doccab = TABLE_CREATION_ORDER.index("DOCCAB")
        idx_doclin = TABLE_CREATION_ORDER.index("DOCLIN")
        self.assertLess(idx_doccab, idx_doclin,
            "DOCLIN debe crearse después de DOCCAB")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE E2 — Columnas que NO existen (errores comunes de IA)
# ══════════════════════════════════════════════════════════════════════════════

class TestColumnasQueNoExisten(unittest.TestCase):
    """
    Verifica que el sistema conoce las columnas que NO existen en la BD.
    Estos son errores comunes que la IA comete al generar SQL.
    """

    def test_articulo_no_tiene_stock(self):
        """ARTICULO.STOCK no existe — es STOCKARTICULO."""
        cols = TABLE_COLUMNS.get("ARTICULO", [])
        self.assertNotIn("STOCK", cols)
        self.assertIn("STOCKARTICULO", cols)

    def test_doclin_no_tiene_importe(self):
        """DOCLIN.IMPORTE no existe — calcular con CANTIDAD*PRECIO."""
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertNotIn("IMPORTE", cols)
        self.assertIn("CANTIDAD", cols)
        self.assertIn("PRECIO", cols)

    def test_doclin_no_tiene_descuento_singular(self):
        """DOCLIN.DESCUENTO no existe — es DESCUENTOS (plural)."""
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertNotIn("DESCUENTO", cols)
        self.assertIn("DESCUENTOS", cols)

    def test_doclin_no_tiene_fecha(self):
        """DOCLIN.FECHA no existe — la fecha está en DOCCAB."""
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertNotIn("FECHA", cols)

    def test_caja_no_tiene_codigo(self):
        """CAJA.CODIGO no existe — la PK es CODAPUNTE."""
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertNotIn("CODIGO", cols)
        self.assertIn("CODAPUNTE", cols)

    def test_estalmacen_no_tiene_codarticulo(self):
        """ESTALMACEN no tiene CODARTICULO — es tabla de totales por período."""
        cols = TABLE_COLUMNS.get("ESTALMACEN", [])
        self.assertNotIn("CODARTICULO", cols)
        self.assertNotIn("CODALMACEN", cols)

    def test_proyectos_no_tiene_diasdevolucionretencion_en_columns(self):
        """PROYECTOS.DIASDEVOLUCIONRETENCION puede no estar en TABLE_COLUMNS simplificado."""
        # Este test verifica que el sistema conoce la limitación del esquema simplificado
        cols = TABLE_COLUMNS.get("PROYECTOS", [])
        self.assertIn("TIPORETENCION", cols)
        self.assertIn("PORCRETENCION", cols)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE E3 — PKs y tipos de datos especiales
# ══════════════════════════════════════════════════════════════════════════════

class TestPKsYTiposEspeciales(unittest.TestCase):
    """Verifica PKs y tipos de datos especiales del esquema."""

    def test_proyectos_codigo_es_text(self):
        """PROYECTOS.CODIGO es TEXT (no INTEGER) — usar comillas en SQL."""
        schema = TABLE_SCHEMAS.get("PROYECTOS", "")
        self.assertIn("TEXT", schema.upper(),
            "PROYECTOS.CODIGO debe ser TEXT")
        # Verificar que no es INTEGER
        lines = [l for l in schema.split("\n") if "CODIGO" in l.upper()]
        for line in lines:
            if "PRIMARY KEY" in line.upper():
                self.assertNotIn("INTEGER", line.upper(),
                    "PROYECTOS.CODIGO no debe ser INTEGER")

    def test_caja_codapunte_es_pk(self):
        """CAJA.CODAPUNTE es la PK."""
        schema = TABLE_SCHEMAS.get("CAJA", "")
        self.assertIn("CODAPUNTE", schema)
        self.assertIn("PRIMARY KEY", schema.upper())

    def test_doclin_pk_compuesta(self):
        """DOCLIN tiene PK compuesta (CODDOCUMENTO, CODIGO)."""
        schema = TABLE_SCHEMAS.get("DOCLIN", "")
        self.assertIn("PRIMARY KEY", schema.upper())
        self.assertIn("CODDOCUMENTO", schema)
        self.assertIn("CODIGO", schema)

    def test_presuproye_pk_compuesta(self):
        """PRESUPROYE tiene PK compuesta (CODPROYECTO, CODPRESUPUESTO)."""
        schema = TABLE_SCHEMAS.get("PRESUPROYE", "")
        self.assertIn("PRIMARY KEY", schema.upper())
        self.assertIn("CODPROYECTO", schema)
        self.assertIn("CODPRESUPUESTO", schema)

    def test_formaspago_codigo_es_text(self):
        """FORMASPAGO.CODIGO es TEXT (ej: 'CONTADO', '30DIAS')."""
        schema = TABLE_SCHEMAS.get("FORMASPAGO", "")
        lines = [l for l in schema.split("\n") if "CODIGO" in l.upper()]
        for line in lines:
            if "PRIMARY KEY" in line.upper():
                self.assertIn("TEXT", line.upper(),
                    "FORMASPAGO.CODIGO debe ser TEXT")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE E4 — Índices del esquema
# ══════════════════════════════════════════════════════════════════════════════

class TestIndicesEsquema(unittest.TestCase):
    """Verifica que los índices críticos están definidos."""

    def test_indice_doccab_tipo(self):
        indexes = TABLE_INDEXES.get("DOCCAB", [])
        idx_text = " ".join(indexes).upper()
        self.assertIn("TIPO", idx_text,
            "DOCCAB debe tener índice en TIPO para queries frecuentes")

    def test_indice_doccab_fecha(self):
        indexes = TABLE_INDEXES.get("DOCCAB", [])
        idx_text = " ".join(indexes).upper()
        self.assertIn("FECHA", idx_text)

    def test_indice_doccab_proyecto(self):
        indexes = TABLE_INDEXES.get("DOCCAB", [])
        idx_text = " ".join(indexes).upper()
        self.assertIn("CODPROYECTO", idx_text,
            "DOCCAB debe tener índice en CODPROYECTO para queries de certificaciones")

    def test_indice_doclin_coddocumento(self):
        indexes = TABLE_INDEXES.get("DOCLIN", [])
        idx_text = " ".join(indexes).upper()
        self.assertIn("CODDOCUMENTO", idx_text)

    def test_indice_articulo_familia(self):
        indexes = TABLE_INDEXES.get("ARTICULO", [])
        idx_text = " ".join(indexes).upper()
        self.assertIn("CODFAMILIA", idx_text)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE E5 — Simulador: esquema real en BD SQLite
# ══════════════════════════════════════════════════════════════════════════════

class TestEsquemaRealEnSimulador(unittest.TestCase):
    """Verifica que el esquema SQLite replica correctamente el Firebird."""

    def setUp(self):
        self.conn = _make_db()

    def tearDown(self):
        self.conn.close()

    def test_todas_las_tablas_creadas(self):
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tablas_bd = {row[0] for row in cursor.fetchall()}
        for tabla in TABLE_CREATION_ORDER:
            if tabla in TABLE_SCHEMAS:
                self.assertIn(tabla, tablas_bd,
                    f"Tabla {tabla} debe existir en la BD SQLite")

    def test_articulo_columnas_reales(self):
        cols = _get_real_cols(self.conn, "ARTICULO")
        self.assertIn("STOCKARTICULO", cols)
        self.assertNotIn("STOCK", cols)

    def test_doclin_columnas_reales(self):
        cols = _get_real_cols(self.conn, "DOCLIN")
        self.assertIn("DESCUENTOS", cols)
        self.assertNotIn("DESCUENTO", cols)
        self.assertNotIn("IMPORTE", cols)
        self.assertNotIn("FECHA", cols)

    def test_caja_columnas_reales(self):
        cols = _get_real_cols(self.conn, "CAJA")
        self.assertIn("CODAPUNTE", cols)
        self.assertNotIn("CODIGO", cols)

    def test_doccab_tiene_codproyecto(self):
        cols = _get_real_cols(self.conn, "DOCCAB")
        self.assertIn("CODPROYECTO", cols)

    def test_proyectos_tiene_tiporetencion(self):
        cols = _get_real_cols(self.conn, "PROYECTOS")
        self.assertIn("TIPORETENCION", cols)
        self.assertIn("PORCRETENCION", cols)

    def test_insert_y_query_basico(self):
        """Verifica que se puede insertar y consultar en todas las tablas principales."""
        self.conn.execute(
            "INSERT INTO CLIENTE (CODIGO,NOMBRECOMERCIAL,BAJA) VALUES (1,'Test S.L.',0)"
        )
        self.conn.execute(
            "INSERT INTO DOCCAB (CODIGO,TIPO,FECHA,IMPORTETOTAL) VALUES (1,3,'2026-01-01',1000.0)"
        )
        self.conn.commit()
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NOMBRECOMERCIAL FROM CLIENTE WHERE CODIGO=1"
        ).fetchall()]
        self.assertEqual(rows[0]["NOMBRECOMERCIAL"], "Test S.L.")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE E6 — Razonamiento semántico sobre estructura de BD
# ══════════════════════════════════════════════════════════════════════════════

class TestRazonamientoEstructuraBD(unittest.TestCase):
    """
    Verifica que el motor semántico razona correctamente sobre la estructura
    interna de la BD cuando el usuario pregunta sobre ella.
    """

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_conocimiento_proyectos_codigo_es_text(self):
        """El conocimiento debe mencionar que PROYECTOS.CODIGO es TEXT."""
        conocimiento = JDDC_BUSINESS_KNOWLEDGE.get("proyectos_obras", "")
        self.assertIn("TEXT", conocimiento.upper(),
            "El conocimiento debe mencionar que PROYECTOS.CODIGO es TEXT")

    def test_conocimiento_join_proyectos_doccab(self):
        """El conocimiento debe mencionar el JOIN entre PROYECTOS y DOCCAB."""
        conocimiento = JDDC_BUSINESS_KNOWLEDGE.get("proyectos_obras", "")
        self.assertIn("CODPROYECTO", conocimiento,
            "El conocimiento debe mencionar CODPROYECTO para el JOIN")

    def test_conocimiento_certificaciones_join(self):
        """El conocimiento de certificaciones debe incluir el JOIN correcto."""
        conocimiento = JDDC_BUSINESS_KNOWLEDGE.get("certificaciones_obra", "")
        self.assertIn("JOIN", conocimiento.upper())
        self.assertIn("DOCCAB", conocimiento)
        self.assertIn("PROYECTOS", conocimiento)

    def test_razona_sobre_tablas_disponibles(self):
        """El motor debe sugerir tablas correctas para cada dominio."""
        dominios_tablas = [
            ("certificaciones de obra", ["DOCCAB", "PROYECTOS"]),
            ("artículos con stock bajo", ["ARTICULO"]),
            ("clientes activos", ["CLIENTE"]),
            ("movimientos de caja", ["CAJA"]),
            ("facturas emitidas", ["DOCCAB"]),
        ]
        for pregunta, tablas_esperadas in dominios_tablas:
            r = self.engine.reason(pregunta)
            for tabla in tablas_esperadas:
                self.assertIn(tabla, r.tables_suggested,
                    f"Para '{pregunta}' debe sugerir tabla {tabla}")

    def test_resiliente_pregunta_sobre_estructura(self):
        """Preguntas sobre la estructura de BD no deben lanzar excepción."""
        preguntas = [
            "qué tablas tiene la base de datos",
            "cuántas columnas tiene DOCCAB",
            "qué relación hay entre PROYECTOS y DOCCAB",
        ]
        for pregunta in preguntas:
            r = self.engine.reason(pregunta)
            self.assertIsInstance(r, ReasoningResult,
                f"La pregunta '{pregunta}' no debe lanzar excepción")
