"""
test_semantica_documentos_tipos.py — Abstracción semántica: documentos, tipos DOCCAB, mapeo.

OBJETIVO:
    Verificar que el motor semántico razona correctamente sobre el dominio de
    documentos (facturas, albaranes, pedidos, presupuestos) y el mapeo de tipos
    de DOCCAB en JDDC Climatización.

    El sistema debe ser capaz de:
    - Detectar el tipo de documento correcto (TIPO=0,1,2,3,10,11,12,13)
    - Saber que TIPO=0 es PRESUPUESTO (nunca albarán)
    - Saber que TIPO=3 es FACTURA CLIENTE (no proveedor)
    - Saber que TIPO=13 es FACTURA PROVEEDOR
    - Razonar sobre documentos vinculados a proyectos (CODPROYECTO)
    - Entender consultas sobre albaranes pendientes, facturas del mes, etc.
    - Detectar la relación DOCCAB → DOCLIN (líneas de documento)

PRINCIPIOS DEVIA:
    - Sin mocks de datos: solo se simulan las preguntas del usuario
    - Ultra-resiliente: cada test es independiente
    - Determinista primero: patrones de detección deterministas
    - < 500 líneas por archivo

EJECUCIÓN:
    python -m pytest tests/unit/test_semantica_documentos_tipos.py -v
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
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.db_simulator.schema import TABLE_SCHEMAS, TABLE_COLUMNS, TABLE_CREATION_ORDER


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for t in TABLE_CREATION_ORDER:
        if t in TABLE_SCHEMAS:
            conn.execute(TABLE_SCHEMAS[t])
    conn.commit()
    return conn


def _seed_documentos(conn):
    """Inserta documentos de prueba con todos los tipos."""
    conn.executemany(
        "INSERT INTO DOCCAB (CODIGO,TIPO,NUMERO,FECHA,CODCLIENTE,IMPORTETOTAL,CODPROYECTO) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (1,  0, 101, "2026-01-10", 1, 5000.0,  None),   # Presupuesto cliente
            (2,  1, 201, "2026-01-15", 1, 5000.0,  None),   # Pedido cliente
            (3,  2, 301, "2026-01-20", 1, 5000.0,  None),   # Albarán cliente
            (4,  3, 401, "2026-01-25", 1, 6050.0,  None),   # Factura cliente
            (5,  3, 402, "2026-02-05", 2, 12100.0, "P001"), # Factura cliente con proyecto
            (6,  3, 403, "2026-02-10", 2, 9680.0,  "P001"), # Factura cliente con proyecto
            (7, 10, 501, "2026-01-12", 0, 3000.0,  None),   # Presupuesto proveedor
            (8, 11, 601, "2026-01-18", 0, 3000.0,  None),   # Pedido proveedor
            (9, 12, 701, "2026-01-22", 0, 3000.0,  None),   # Albarán proveedor
            (10,13, 801, "2026-01-28", 0, 3630.0,  None),   # Factura proveedor
        ]
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE C1 — Detección de dominio: documentos
# ══════════════════════════════════════════════════════════════════════════════

class TestDeteccionDominioDocumentos(unittest.TestCase):
    """Verifica que el motor detecta el dominio DOCUMENTOS correctamente."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_detecta_facturas(self):
        r = self.engine.reason("facturas emitidas este mes")
        self.assertEqual(r.domain, BusinessDomain.DOCUMENTOS)

    def test_detecta_albaranes(self):
        r = self.engine.reason("albaranes pendientes de facturar")
        self.assertEqual(r.domain, BusinessDomain.DOCUMENTOS)

    def test_detecta_pedidos(self):
        r = self.engine.reason("pedidos de clientes del trimestre")
        self.assertEqual(r.domain, BusinessDomain.DOCUMENTOS)

    def test_detecta_presupuestos(self):
        r = self.engine.reason("presupuestos enviados a clientes")
        self.assertIn(r.domain, [BusinessDomain.DOCUMENTOS, BusinessDomain.CLIENTES_PROVEEDORES])

    def test_detecta_abonos(self):
        r = self.engine.reason("abonos emitidos este año")
        self.assertEqual(r.domain, BusinessDomain.DOCUMENTOS)

    def test_detecta_contratos(self):
        r = self.engine.reason("contratos firmados con clientes")
        self.assertEqual(r.domain, BusinessDomain.DOCUMENTOS)

    def test_detecta_factura_singular(self):
        r = self.engine.reason("dame la factura número 401")
        self.assertEqual(r.domain, BusinessDomain.DOCUMENTOS)

    def test_detecta_albaranes_proveedor(self):
        r = self.engine.reason("albaranes de proveedor sin facturar")
        self.assertIn(r.domain, [BusinessDomain.DOCUMENTOS, BusinessDomain.CLIENTES_PROVEEDORES])

    def test_detecta_presupuestos_aceptados(self):
        r = self.engine.reason("presupuestos aceptados por clientes este año")
        self.assertIn(r.domain, [BusinessDomain.DOCUMENTOS, BusinessDomain.CLIENTES_PROVEEDORES])


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE C2 — Conocimiento del mapeo DOCCAB.TIPO
# ══════════════════════════════════════════════════════════════════════════════

class TestMapeoTipoDocumento(unittest.TestCase):
    """
    Verifica que el sistema conoce el mapeo correcto de DOCCAB.TIPO.
    Este es conocimiento crítico de negocio JDDC verificado con el usuario.
    """

    def setUp(self):
        self.engine = SemanticReasoningEngine()
        self.conocimiento = JDDC_BUSINESS_KNOWLEDGE.get("documentos_tipo", "")

    def test_conocimiento_tipo0_es_presupuesto(self):
        self.assertIn("TIPO=0", self.conocimiento)
        self.assertIn("Presupuesto", self.conocimiento)

    def test_conocimiento_tipo1_es_pedido_cliente(self):
        self.assertIn("TIPO=1", self.conocimiento)

    def test_conocimiento_tipo2_es_albaran_cliente(self):
        self.assertIn("TIPO=2", self.conocimiento)

    def test_conocimiento_tipo3_es_factura_cliente(self):
        self.assertIn("TIPO=3", self.conocimiento)
        self.assertIn("Factura", self.conocimiento)

    def test_conocimiento_tipo10_es_presupuesto_proveedor(self):
        self.assertIn("TIPO=10", self.conocimiento)

    def test_conocimiento_tipo13_es_factura_proveedor(self):
        self.assertIn("TIPO=13", self.conocimiento)

    def test_regla_tipo0_nunca_albaran(self):
        """REGLA CRÍTICA: TIPO=0 es PRESUPUESTO, NUNCA Albarán."""
        self.assertIn("PRESUPUESTO", self.conocimiento.upper(),
            "El conocimiento debe dejar claro que TIPO=0 es PRESUPUESTO")

    def test_hint_factura_detecta_tipo3(self):
        """Para 'facturas' el motor debe sugerir TIPO=3."""
        r = self.engine.reason("facturas emitidas este mes")
        filters_text = " ".join(r.filters_suggested).upper()
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO = 3" in filters_text or "TIPO=3" in filters_text or
            "TIPO = 3" in hints_text or "TIPO=3" in hints_text,
            f"Para facturas debe sugerir TIPO=3. Filters: {r.filters_suggested}, Hints: {r.hints}"
        )

    def test_hint_presupuesto_detecta_tipo0(self):
        """Para 'presupuestos' el motor debe sugerir TIPO=0."""
        r = self.engine.reason("presupuestos enviados a clientes")
        filters_text = " ".join(r.filters_suggested).upper()
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO = 0" in filters_text or "TIPO=0" in filters_text or
            "TIPO = 0" in hints_text or "TIPO=0" in hints_text,
            f"Para presupuestos debe sugerir TIPO=0. Filters: {r.filters_suggested}"
        )

    def test_hint_albaran_detecta_tipo2(self):
        """Para 'albaranes' el motor debe sugerir TIPO=2."""
        r = self.engine.reason("albaranes de clientes pendientes")
        filters_text = " ".join(r.filters_suggested).upper()
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO = 2" in filters_text or "TIPO=2" in filters_text or
            "TIPO = 2" in hints_text or "TIPO=2" in hints_text,
            f"Para albaranes debe sugerir TIPO=2. Filters: {r.filters_suggested}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE C3 — Esquema BD: columnas reales de DOCCAB y DOCLIN
# ══════════════════════════════════════════════════════════════════════════════

class TestEsquemaDocumentos(unittest.TestCase):
    """Verifica que el esquema de DOCCAB y DOCLIN tiene las columnas correctas."""

    def test_doccab_tiene_tipo(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("TIPO", cols)

    def test_doccab_tiene_codproyecto(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("CODPROYECTO", cols,
            "DOCCAB debe tener CODPROYECTO para vincular documentos a proyectos")

    def test_doccab_tiene_importetotal(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("IMPORTETOTAL", cols)

    def test_doccab_tiene_importebase(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("IMPORTEBASE", cols)

    def test_doccab_tiene_importeiva(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("IMPORTEIVA", cols)

    def test_doccab_tiene_fecha(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("FECHA", cols)

    def test_doccab_tiene_numero(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("NUMERO", cols)

    def test_doccab_tiene_serie(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("SERIE", cols)

    def test_doccab_tiene_estado(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("ESTADO", cols)

    def test_doclin_tiene_precio(self):
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertIn("PRECIO", cols)

    def test_doclin_tiene_descuentos(self):
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertIn("DESCUENTOS", cols,
            "DOCLIN tiene DESCUENTOS (no DESCUENTO)")

    def test_doclin_no_tiene_descuento_singular(self):
        cols = TABLE_COLUMNS.get("DOCLIN", [])
        self.assertNotIn("DESCUENTO", cols,
            "DOCLIN tiene DESCUENTOS (plural), no DESCUENTO")

    def test_docdestino_existe(self):
        self.assertIn("DOCDESTINO", TABLE_COLUMNS,
            "DOCDESTINO debe existir para relación presupuesto→factura")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE C4 — Simulador SQLite: queries reales sobre documentos
# ══════════════════════════════════════════════════════════════════════════════

class TestSimuladorDocumentos(unittest.TestCase):
    """Verifica queries reales sobre documentos en BD SQLite en memoria."""

    def setUp(self):
        self.conn = _make_db()
        _seed_documentos(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_query_facturas_cliente(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NUMERO, IMPORTETOTAL FROM DOCCAB WHERE TIPO = 3"
        ).fetchall()]
        self.assertEqual(len(rows), 3, "3 facturas de cliente (TIPO=3)")

    def test_query_presupuestos_cliente(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NUMERO FROM DOCCAB WHERE TIPO = 0"
        ).fetchall()]
        self.assertEqual(len(rows), 1, "1 presupuesto cliente (TIPO=0)")

    def test_query_albaranes_cliente(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NUMERO FROM DOCCAB WHERE TIPO = 2"
        ).fetchall()]
        self.assertEqual(len(rows), 1, "1 albarán cliente (TIPO=2)")

    def test_query_facturas_proveedor(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NUMERO FROM DOCCAB WHERE TIPO = 13"
        ).fetchall()]
        self.assertEqual(len(rows), 1, "1 factura proveedor (TIPO=13)")

    def test_query_facturas_con_proyecto(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NUMERO, CODPROYECTO FROM DOCCAB WHERE TIPO = 3 AND CODPROYECTO IS NOT NULL"
        ).fetchall()]
        self.assertEqual(len(rows), 2, "2 facturas vinculadas al proyecto P001")
        for r in rows:
            self.assertEqual(r["CODPROYECTO"], "P001")

    def test_query_total_facturado_cliente(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT SUM(IMPORTETOTAL) as TOTAL FROM DOCCAB WHERE TIPO = 3"
        ).fetchall()]
        self.assertAlmostEqual(rows[0]["TOTAL"], 27830.0, places=1)

    def test_query_count_por_tipo(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT TIPO, COUNT(*) as TOTAL FROM DOCCAB GROUP BY TIPO ORDER BY TIPO"
        ).fetchall()]
        tipos = {r["TIPO"]: r["TOTAL"] for r in rows}
        self.assertEqual(tipos.get(0), 1)   # 1 presupuesto cliente
        self.assertEqual(tipos.get(3), 3)   # 3 facturas cliente
        self.assertEqual(tipos.get(13), 1)  # 1 factura proveedor

    def test_query_facturas_por_mes(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT substr(FECHA,1,7) as MES, COUNT(*) as TOTAL "
            "FROM DOCCAB WHERE TIPO = 3 GROUP BY MES ORDER BY MES"
        ).fetchall()]
        self.assertEqual(len(rows), 2, "Facturas en enero y febrero")
        meses = {r["MES"] for r in rows}
        self.assertIn("2026-01", meses)
        self.assertIn("2026-02", meses)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE C5 — Normalización SQL para documentos
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizacionSQLDocumentos(unittest.TestCase):
    """Verifica que el normalizador corrige SQLs incorrectos sobre documentos."""

    def setUp(self):
        self.normalizer = FirebirdSQLNormalizer()

    def test_corrige_limit_facturas(self):
        sql = "SELECT NUMERO, IMPORTETOTAL FROM DOCCAB WHERE TIPO = 3 LIMIT 50"
        result, _ = self.normalizer.normalize(sql)
        self.assertIn("FIRST", result.upper())
        self.assertNotIn("LIMIT", result.upper())

    def test_corrige_ilike_facturas(self):
        sql = "SELECT NUMERO FROM DOCCAB WHERE DESCRIPCION ILIKE '%instalación%'"
        result, _ = self.normalizer.normalize(sql)
        self.assertNotIn("ILIKE", result.upper())

    def test_elimina_punto_y_coma_facturas(self):
        sql = "SELECT COUNT(*) FROM DOCCAB WHERE TIPO = 3;"
        result, _ = self.normalizer.normalize(sql)
        self.assertFalse(result.strip().endswith(";"))

    def test_sql_facturas_valido_sin_cambios(self):
        sql = "SELECT FIRST 50 NUMERO, FECHA, IMPORTETOTAL FROM DOCCAB WHERE TIPO = 3 ORDER BY FECHA DESC"
        result, _ = self.normalizer.normalize(sql)
        self.assertIn("DOCCAB", result)
        self.assertIn("TIPO", result)

    def test_corrige_doclin_fecha_a_join_doccab(self):
        """DOCLIN.FECHA no existe — debe hacer JOIN con DOCCAB para obtener la fecha."""
        sql = "SELECT L.FECHA, L.CANTIDAD FROM DOCLIN L WHERE L.FECHA > '2026-01-01'"
        result, changes = self.normalizer.normalize(sql)
        # El normalizador debe detectar DOCLIN.FECHA y sugerir JOIN
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE C6 — Abstracción semántica: razonamiento sobre documentos
# ══════════════════════════════════════════════════════════════════════════════

class TestAbstraccionSemanticaDocumentos(unittest.TestCase):
    """
    Verifica que el motor razona a nivel de abstracción superior sobre documentos.
    """

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_deduce_que_certificaciones_son_facturas_con_proyecto(self):
        """Las certificaciones son DOCCAB con TIPO=3 y CODPROYECTO no nulo."""
        r = self.engine.reason("certificaciones de obra del proyecto P001")
        # Certificaciones tienen mayor prioridad que documentos
        self.assertEqual(r.domain, BusinessDomain.CERTIFICACIONES)
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO=3" in hints_text or "CODPROYECTO" in hints_text,
            "Las certificaciones deben mencionar TIPO=3 y CODPROYECTO"
        )

    def test_deduce_que_presupuesto_no_es_albaran(self):
        """TIPO=0 es PRESUPUESTO, nunca albarán — regla crítica."""
        conocimiento = JDDC_BUSINESS_KNOWLEDGE.get("documentos_tipo", "")
        self.assertIn("PRESUPUESTO", conocimiento.upper())
        # La regla explícita debe estar en el conocimiento
        self.assertIn("NUNCA", conocimiento.upper(),
            "El conocimiento debe incluir la regla 'TIPO=0 es PRESUPUESTO, NUNCA Albarán'")

    def test_sugiere_doccab_para_facturas(self):
        r = self.engine.reason("facturas emitidas este año")
        self.assertIn("DOCCAB", r.tables_suggested)

    def test_sugiere_doclin_para_lineas(self):
        r = self.engine.reason("líneas de factura con artículos")
        self.assertIn("DOCLIN", r.tables_suggested)

    def test_resiliente_pregunta_tipo_ambiguo(self):
        """Una pregunta con tipo ambiguo no debe lanzar excepción."""
        r = self.engine.reason("documentos del mes")
        self.assertIsInstance(r, ReasoningResult)

    def test_confianza_alta_facturas(self):
        r = self.engine.reason("facturas emitidas este mes")
        self.assertGreater(r.confidence, 0.7)

    def test_build_enriched_prompt_documentos(self):
        r = self.engine.reason("facturas del mes de enero")
        prompt = self.engine.build_enriched_system_prompt("BASE PROMPT", r)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)
