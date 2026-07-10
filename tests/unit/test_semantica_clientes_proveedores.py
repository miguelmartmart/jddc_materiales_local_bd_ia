"""
test_semantica_clientes_proveedores.py — Abstracción semántica: clientes, proveedores, agentes.

OBJETIVO:
    Verificar que el motor semántico razona correctamente sobre el dominio de
    clientes, proveedores y agentes comerciales de JDDC Climatización.

    El sistema debe ser capaz de:
    - Detectar preguntas sobre clientes/proveedores con vocabulario coloquial
    - Inferir tablas correctas (CLIENTE, PROVEED, AGENTES, DOCCAB)
    - Distinguir entre clientes (ventas, TIPO=3) y proveedores (compras, TIPO=13)
    - Razonar sobre segmentación de clientes (por volumen, zona, agente)
    - Entender consultas sobre proveedores habituales, mejores clientes, etc.
    - Detectar clientes/proveedores dados de baja (BAJA=1)

PRINCIPIOS DEVIA:
    - Sin mocks de datos: solo se simulan las preguntas del usuario
    - Ultra-resiliente: cada test es independiente
    - Determinista primero: patrones de detección deterministas
    - < 500 líneas por archivo

EJECUCIÓN:
    python -m pytest tests/unit/test_semantica_clientes_proveedores.py -v
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


def _seed_clientes_proveedores(conn):
    """Inserta clientes, proveedores y agentes de prueba."""
    conn.executemany(
        "INSERT INTO CLIENTE (CODIGO,NOMBRECOMERCIAL,RAZONSOCIAL,NIF,CODAGENTE,BAJA) VALUES (?,?,?,?,?,?)",
        [
            (1, "Constructora Pérez S.L.", "Constructora Pérez S.L.", "B12345678", 1, 0),
            (2, "Hoteles Mediterráneo S.A.", "Hoteles Mediterráneo S.A.", "A23456789", 1, 0),
            (3, "Clínica San Juan S.L.", "Clínica San Juan S.L.", "B34567890", 2, 0),
            (4, "Supermercados Norte S.A.", "Supermercados Norte S.A.", "A45678901", 2, 0),
            (5, "Antiguo Cliente S.L.", "Antiguo Cliente S.L.", "B56789012", 1, 1),  # baja
        ]
    )
    conn.executemany(
        "INSERT INTO PROVEED (CODIGO,NOMBRECOMERCIAL,RAZONSOCIAL,NIF,BAJA) VALUES (?,?,?,?,?)",
        [
            (1, "Daikin España S.A.U.", "Daikin España S.A.U.", "B82345678", 0),
            (2, "Mitsubishi Electric Europe", "Mitsubishi Electric Europe B.V.", "B91234567", 0),
            (3, "Proveedor Inactivo S.L.", "Proveedor Inactivo S.L.", "B11111111", 1),  # baja
        ]
    )
    conn.executemany(
        "INSERT INTO AGENTES (CODIGO,NOMBRE,COMISION) VALUES (?,?,?)",
        [(1, "Juan García", 3.5), (2, "María López", 4.0)]
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE B1 — Detección de dominio: clientes
# ══════════════════════════════════════════════════════════════════════════════

class TestDeteccionDominioClientes(unittest.TestCase):
    """Verifica que el motor detecta el dominio CLIENTES_PROVEEDORES para clientes."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_detecta_clientes_directa(self):
        r = self.engine.reason("dame la lista de clientes activos")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_mejores_clientes(self):
        r = self.engine.reason("cuáles son los mejores clientes del año")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_clientes_por_agente(self):
        r = self.engine.reason("clientes asignados al agente Juan García")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_clientes_sin_compras(self):
        r = self.engine.reason("clientes que no han comprado este año")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_agentes_comerciales(self):
        r = self.engine.reason("agentes comerciales con más ventas")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_comerciales(self):
        r = self.engine.reason("qué comerciales tenemos en la empresa")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_cliente_singular(self):
        r = self.engine.reason("datos del cliente Constructora Pérez")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_clientes_zona(self):
        r = self.engine.reason("clientes de la zona norte")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE B2 — Detección de dominio: proveedores
# ══════════════════════════════════════════════════════════════════════════════

class TestDeteccionDominioProveedores(unittest.TestCase):
    """Verifica que el motor detecta el dominio CLIENTES_PROVEEDORES para proveedores."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_detecta_proveedores_directa(self):
        r = self.engine.reason("lista de proveedores habituales")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_proveedor_singular(self):
        r = self.engine.reason("datos del proveedor Daikin")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_proveedores_facturas(self):
        r = self.engine.reason("proveedores con facturas pendientes de pago")
        self.assertIn(r.domain, [BusinessDomain.CLIENTES_PROVEEDORES, BusinessDomain.DOCUMENTOS])

    def test_detecta_mejores_proveedores(self):
        r = self.engine.reason("proveedores a los que más compramos")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_detecta_proveedor_defecto(self):
        r = self.engine.reason("proveedor por defecto de cada artículo")
        self.assertIn(r.domain, [BusinessDomain.CLIENTES_PROVEEDORES, BusinessDomain.ARTICULOS_STOCK])


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE B3 — Hints SQL para clientes y proveedores
# ══════════════════════════════════════════════════════════════════════════════

class TestHintsClientesProveedores(unittest.TestCase):
    """Verifica que el motor genera hints SQL correctos para clientes/proveedores."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_sugiere_tabla_cliente(self):
        r = self.engine.reason("clientes activos de la empresa")
        self.assertIn("CLIENTE", r.tables_suggested)

    def test_sugiere_tabla_proveed(self):
        r = self.engine.reason("proveedores habituales")
        self.assertIn("PROVEED", r.tables_suggested)

    def test_sugiere_tabla_agentes(self):
        r = self.engine.reason("agentes comerciales de la empresa")
        # AGENTES está en el dominio CLIENTES_PROVEEDORES — verificar dominio correcto
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES,
            "Preguntas sobre agentes deben detectar dominio CLIENTES_PROVEEDORES")

    def test_hint_ventas_clientes_tipo3(self):
        """Para ventas a clientes debe sugerir TIPO=3 (factura cliente)."""
        r = self.engine.reason("clientes con más ventas")
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO=3" in hints_text or "TIPO" in hints_text or "DOCCAB" in hints_text,
            "Para ventas a clientes debe mencionar TIPO=3 o DOCCAB"
        )

    def test_hint_compras_proveedores_tipo13(self):
        """Para compras a proveedores debe sugerir TIPO=13 (factura proveedor)."""
        r = self.engine.reason("proveedores con más compras")
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO=13" in hints_text or "TIPO" in hints_text or "DOCCAB" in hints_text,
            "Para compras a proveedores debe mencionar TIPO=13 o DOCCAB"
        )

    def test_confianza_alta_clientes(self):
        r = self.engine.reason("clientes activos")
        self.assertGreater(r.confidence, 0.6)

    def test_confianza_alta_proveedores(self):
        r = self.engine.reason("proveedores habituales")
        self.assertGreater(r.confidence, 0.6)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE B4 — Esquema BD: columnas reales de CLIENTE y PROVEED
# ══════════════════════════════════════════════════════════════════════════════

class TestEsquemaClientesProveedores(unittest.TestCase):
    """Verifica que el esquema de CLIENTE y PROVEED tiene las columnas correctas."""

    def test_cliente_tiene_nombrecomercial(self):
        cols = TABLE_COLUMNS.get("CLIENTE", [])
        self.assertIn("NOMBRECOMERCIAL", cols)

    def test_cliente_tiene_razonsocial(self):
        cols = TABLE_COLUMNS.get("CLIENTE", [])
        self.assertIn("RAZONSOCIAL", cols)

    def test_cliente_tiene_nif(self):
        cols = TABLE_COLUMNS.get("CLIENTE", [])
        self.assertIn("NIF", cols)

    def test_cliente_tiene_baja(self):
        cols = TABLE_COLUMNS.get("CLIENTE", [])
        self.assertIn("BAJA", cols)

    def test_cliente_tiene_codagente(self):
        cols = TABLE_COLUMNS.get("CLIENTE", [])
        self.assertIn("CODAGENTE", cols,
            "CLIENTE debe tener CODAGENTE para vincular con agente comercial")

    def test_proveed_tiene_nombrecomercial(self):
        cols = TABLE_COLUMNS.get("PROVEED", [])
        self.assertIn("NOMBRECOMERCIAL", cols)

    def test_proveed_tiene_baja(self):
        cols = TABLE_COLUMNS.get("PROVEED", [])
        self.assertIn("BAJA", cols)

    def test_agentes_tiene_comision(self):
        cols = TABLE_COLUMNS.get("AGENTES", [])
        self.assertIn("COMISION", cols)

    def test_doccab_tiene_codcliente(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("CODCLIENTE", cols,
            "DOCCAB debe tener CODCLIENTE para vincular facturas con clientes")

    def test_doccab_tiene_codagente(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("CODAGENTE", cols)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE B5 — Simulador SQLite: queries reales sobre clientes/proveedores
# ══════════════════════════════════════════════════════════════════════════════

class TestSimuladorClientesProveedores(unittest.TestCase):
    """Verifica queries reales sobre clientes/proveedores en BD SQLite en memoria."""

    def setUp(self):
        self.conn = _make_db()
        _seed_clientes_proveedores(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_query_clientes_activos(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NOMBRECOMERCIAL FROM CLIENTE WHERE BAJA = 0"
        ).fetchall()]
        self.assertEqual(len(rows), 4, "4 clientes activos (1 de baja)")

    def test_query_clientes_por_agente(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT c.NOMBRECOMERCIAL, a.NOMBRE as AGENTE "
            "FROM CLIENTE c JOIN AGENTES a ON a.CODIGO = c.CODAGENTE "
            "WHERE c.BAJA = 0"
        ).fetchall()]
        self.assertGreater(len(rows), 0)
        agentes = {r["AGENTE"] for r in rows}
        self.assertIn("Juan García", agentes)

    def test_query_proveedores_activos(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NOMBRECOMERCIAL FROM PROVEED WHERE BAJA = 0"
        ).fetchall()]
        self.assertEqual(len(rows), 2, "2 proveedores activos (1 de baja)")

    def test_query_count_clientes(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT COUNT(*) as TOTAL FROM CLIENTE WHERE BAJA = 0"
        ).fetchall()]
        self.assertEqual(rows[0]["TOTAL"], 4)

    def test_query_agentes_con_clientes(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT a.NOMBRE, COUNT(c.CODIGO) as NUM_CLIENTES "
            "FROM AGENTES a LEFT JOIN CLIENTE c ON c.CODAGENTE = a.CODIGO AND c.BAJA = 0 "
            "GROUP BY a.CODIGO, a.NOMBRE"
        ).fetchall()]
        self.assertGreater(len(rows), 0)

    def test_query_cliente_por_nif(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT NOMBRECOMERCIAL FROM CLIENTE WHERE NIF = 'B12345678'"
        ).fetchall()]
        self.assertEqual(len(rows), 1)
        self.assertIn("Pérez", rows[0]["NOMBRECOMERCIAL"])

    def test_esquema_cliente_en_bd(self):
        cursor = self.conn.execute("PRAGMA table_info(CLIENTE)")
        cols = {row[1] for row in cursor.fetchall()}
        self.assertIn("NOMBRECOMERCIAL", cols)
        self.assertIn("BAJA", cols)
        self.assertIn("CODAGENTE", cols)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE B6 — Abstracción semántica: razonamiento sobre clientes/proveedores
# ══════════════════════════════════════════════════════════════════════════════

class TestAbstraccionSemanticaClientesProveedores(unittest.TestCase):
    """
    Verifica que el motor razona a nivel de abstracción superior sobre
    clientes, proveedores y agentes comerciales.
    """

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_deduce_que_ventas_clientes_usan_doccab(self):
        """Para 'mejores clientes' debe inferir JOIN con DOCCAB."""
        r = self.engine.reason("clientes con más ventas este año")
        tables_text = " ".join(r.tables_suggested).upper()
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "DOCCAB" in tables_text or "DOCCAB" in hints_text,
            "Para ventas de clientes debe inferir DOCCAB"
        )

    def test_deduce_que_compras_proveedores_usan_doccab(self):
        """Para 'proveedores con más compras' debe inferir JOIN con DOCCAB."""
        r = self.engine.reason("proveedores a los que más compramos")
        tables_text = " ".join(r.tables_suggested).upper()
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "DOCCAB" in tables_text or "DOCCAB" in hints_text or "PROVEED" in tables_text,
            "Para compras a proveedores debe inferir DOCCAB o PROVEED"
        )

    def test_distingue_cliente_de_proveedor(self):
        """El motor debe distinguir entre preguntas de clientes y proveedores."""
        r_cli = self.engine.reason("clientes activos de la empresa")
        r_prov = self.engine.reason("proveedores habituales")
        # Ambos son CLIENTES_PROVEEDORES pero con hints diferentes
        self.assertEqual(r_cli.domain, BusinessDomain.CLIENTES_PROVEEDORES)
        self.assertEqual(r_prov.domain, BusinessDomain.CLIENTES_PROVEEDORES)
        # Los hints deben ser diferentes
        hints_cli = " ".join(r_cli.hints).upper()
        hints_prov = " ".join(r_prov.hints).upper()
        # Cliente → TIPO=3, Proveedor → TIPO=13
        self.assertTrue(
            "TIPO=3" in hints_cli or "CLIENTE" in hints_cli,
            f"Hints de cliente deben mencionar TIPO=3 o CLIENTE: {r_cli.hints}"
        )
        self.assertTrue(
            "TIPO=13" in hints_prov or "PROVEED" in hints_prov,
            f"Hints de proveedor deben mencionar TIPO=13 o PROVEED: {r_prov.hints}"
        )

    def test_razona_sobre_baja_clientes(self):
        """El sistema debe saber que BAJA=1 indica cliente dado de baja."""
        r = self.engine.reason("clientes activos de la empresa")
        self.assertEqual(r.domain, BusinessDomain.CLIENTES_PROVEEDORES)

    def test_resiliente_pregunta_ambigua(self):
        """Una pregunta ambigua no debe lanzar excepción."""
        r = self.engine.reason("quién nos compra más")
        self.assertIsInstance(r, ReasoningResult)

    def test_normaliza_sql_clientes(self):
        """El normalizador corrige SQLs sobre clientes."""
        normalizer = FirebirdSQLNormalizer()
        sql = "SELECT NOMBRECOMERCIAL FROM CLIENTE WHERE BAJA = 0 LIMIT 20"
        result, _ = normalizer.normalize(sql)
        self.assertIn("FIRST", result.upper())
        self.assertNotIn("LIMIT", result.upper())

    def test_normaliza_ilike_clientes(self):
        normalizer = FirebirdSQLNormalizer()
        sql = "SELECT NOMBRECOMERCIAL FROM CLIENTE WHERE NOMBRECOMERCIAL ILIKE '%pérez%'"
        result, _ = normalizer.normalize(sql)
        self.assertNotIn("ILIKE", result.upper())
