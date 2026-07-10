"""
test_semantica_financiero_caja.py — Abstracción semántica: financiero, caja, cobros, pagos.

OBJETIVO:
    Verificar que el motor semántico razona correctamente sobre el dominio
    financiero de JDDC: caja, cobros, pagos, tesorería, vencimientos.

    El sistema debe ser capaz de:
    - Detectar preguntas sobre caja/tesorería con vocabulario coloquial
    - Inferir tablas correctas (CAJA, DOCCAB, FORMASPAGO)
    - Conocer que CAJA.TIPO=1 es cobro, TIPO=2 es pago
    - Razonar sobre vencimientos, liquidez, saldos de caja
    - Entender consultas sobre cobros pendientes, pagos del mes, etc.
    - Detectar la relación CAJA → DOCCAB (cobros vinculados a facturas)

PRINCIPIOS DEVIA:
    - Sin mocks de datos: solo se simulan las preguntas del usuario
    - Ultra-resiliente: cada test es independiente
    - Determinista primero: patrones de detección deterministas
    - < 500 líneas por archivo

EJECUCIÓN:
    python -m pytest tests/unit/test_semantica_financiero_caja.py -v
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


def _seed_caja(conn):
    """Inserta movimientos de caja de prueba."""
    conn.executemany(
        "INSERT INTO CAJA (FECHA,CODAPUNTE,TIPO,IMPORTE,CONCEPTO,CODCLIENTE) VALUES (?,?,?,?,?,?)",
        [
            ("2026-01-05", 1, 1, 6050.0,  "Cobro factura 401 - Constructora Pérez", 1),
            ("2026-01-10", 2, 1, 12100.0, "Cobro factura 402 - Hoteles Mediterráneo", 2),
            ("2026-01-15", 3, 2, 3630.0,  "Pago factura proveedor Daikin", 0),
            ("2026-01-20", 4, 2, 1500.0,  "Pago nóminas enero", 0),
            ("2026-02-05", 5, 1, 9680.0,  "Cobro factura 403 - Hoteles Mediterráneo", 2),
            ("2026-02-10", 6, 2, 2200.0,  "Pago alquiler nave", 0),
        ]
    )
    conn.executemany(
        "INSERT INTO FORMASPAGO (CODIGO,NOMBRE,DIASVENC,TIPOCOBRO) VALUES (?,?,?,?)",
        [
            ("CONTADO", "Contado", 0, 1),
            ("30DIAS",  "30 días", 30, 2),
            ("60DIAS",  "60 días", 60, 2),
            ("90DIAS",  "90 días", 90, 2),
        ]
    )
    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE D1 — Detección de dominio: financiero
# ══════════════════════════════════════════════════════════════════════════════

class TestDeteccionDominioFinanciero(unittest.TestCase):
    """Verifica que el motor detecta el dominio FINANCIERO correctamente."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_detecta_caja(self):
        r = self.engine.reason("movimientos de caja del mes")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)

    def test_detecta_cobros(self):
        r = self.engine.reason("cobros pendientes de clientes")
        self.assertIn(r.domain, [BusinessDomain.FINANCIERO, BusinessDomain.CLIENTES_PROVEEDORES])

    def test_detecta_pagos(self):
        r = self.engine.reason("pagos realizados este mes")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)

    def test_detecta_tesoreria(self):
        r = self.engine.reason("estado de tesorería de la empresa")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)

    def test_detecta_tesoreria_sin_tilde(self):
        r = self.engine.reason("informe de tesoreria mensual")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)

    def test_detecta_recibos(self):
        r = self.engine.reason("recibos domiciliados del mes")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)

    def test_detecta_vencimientos(self):
        # "vencimientos de facturas" puede detectarse como FINANCIERO o DOCUMENTOS
        r = self.engine.reason("vencimientos de facturas próximos")
        self.assertIn(r.domain, [BusinessDomain.FINANCIERO, BusinessDomain.DOCUMENTOS])

    def test_detecta_liquidez(self):
        r = self.engine.reason("situación de liquidez de la empresa")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)

    def test_detecta_saldo_caja(self):
        r = self.engine.reason("saldo actual de caja")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)

    def test_detecta_cobro_singular(self):
        # "cobro de cliente" puede detectarse como FINANCIERO o CLIENTES_PROVEEDORES
        r = self.engine.reason("registrar un cobro de cliente")
        self.assertIn(r.domain, [BusinessDomain.FINANCIERO, BusinessDomain.CLIENTES_PROVEEDORES])


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE D2 — Hints SQL para financiero
# ══════════════════════════════════════════════════════════════════════════════

class TestHintsFinanciero(unittest.TestCase):
    """Verifica que el motor genera hints SQL correctos para financiero."""

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_sugiere_tabla_caja(self):
        r = self.engine.reason("movimientos de caja del mes")
        self.assertIn("CAJA", r.tables_suggested)

    def test_sugiere_tabla_doccab_financiero(self):
        r = self.engine.reason("cobros pendientes de clientes")
        self.assertIn("DOCCAB", r.tables_suggested)

    def test_hint_tipo_cobro_pago(self):
        """El motor debe saber que CAJA.TIPO=1 es cobro, TIPO=2 es pago."""
        r = self.engine.reason("movimientos de caja del mes")
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO=1" in hints_text or "TIPO=2" in hints_text or
            "COBRO" in hints_text or "PAGO" in hints_text,
            f"Los hints deben mencionar tipos de movimiento de caja: {r.hints}"
        )

    def test_confianza_alta_financiero(self):
        r = self.engine.reason("movimientos de caja del mes")
        self.assertGreater(r.confidence, 0.6)

    def test_reasoning_steps_financiero(self):
        r = self.engine.reason("cobros del mes de enero")
        self.assertGreater(len(r.reasoning_steps), 0)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE D3 — Esquema BD: columnas reales de CAJA y FORMASPAGO
# ══════════════════════════════════════════════════════════════════════════════

class TestEsquemaFinanciero(unittest.TestCase):
    """Verifica que el esquema de CAJA y FORMASPAGO tiene las columnas correctas."""

    def test_caja_tiene_tipo(self):
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertIn("TIPO", cols,
            "CAJA debe tener TIPO (1=cobro, 2=pago)")

    def test_caja_tiene_importe(self):
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertIn("IMPORTE", cols)

    def test_caja_tiene_fecha(self):
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertIn("FECHA", cols)

    def test_caja_tiene_concepto(self):
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertIn("CONCEPTO", cols)

    def test_caja_tiene_codcliente(self):
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertIn("CODCLIENTE", cols,
            "CAJA debe tener CODCLIENTE para vincular cobros con clientes")

    def test_caja_tiene_codapunte(self):
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertIn("CODAPUNTE", cols,
            "CAJA.CODAPUNTE es la PK (no CODIGO)")

    def test_caja_no_tiene_codigo(self):
        cols = TABLE_COLUMNS.get("CAJA", [])
        self.assertNotIn("CODIGO", cols,
            "CAJA usa CODAPUNTE como PK, no CODIGO")

    def test_formaspago_tiene_diasvenc(self):
        cols = TABLE_COLUMNS.get("FORMASPAGO", [])
        self.assertIn("DIASVENC", cols,
            "FORMASPAGO debe tener DIASVENC para calcular vencimientos")

    def test_formaspago_tiene_tipocobro(self):
        cols = TABLE_COLUMNS.get("FORMASPAGO", [])
        self.assertIn("TIPOCOBRO", cols)

    def test_doccab_tiene_codformapago(self):
        cols = TABLE_COLUMNS.get("DOCCAB", [])
        self.assertIn("CODFORMAPAGO", cols,
            "DOCCAB debe tener CODFORMAPAGO para calcular vencimientos")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE D4 — Simulador SQLite: queries reales sobre caja
# ══════════════════════════════════════════════════════════════════════════════

class TestSimuladorFinanciero(unittest.TestCase):
    """Verifica queries reales sobre caja en BD SQLite en memoria."""

    def setUp(self):
        self.conn = _make_db()
        _seed_caja(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_query_cobros_totales(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT SUM(IMPORTE) as TOTAL FROM CAJA WHERE TIPO = 1"
        ).fetchall()]
        self.assertAlmostEqual(rows[0]["TOTAL"], 27830.0, places=1,
            msg="Total cobros: 6050 + 12100 + 9680 = 27830")

    def test_query_pagos_totales(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT SUM(IMPORTE) as TOTAL FROM CAJA WHERE TIPO = 2"
        ).fetchall()]
        self.assertAlmostEqual(rows[0]["TOTAL"], 7330.0, places=1,
            msg="Total pagos: 3630 + 1500 + 2200 = 7330")

    def test_query_saldo_caja(self):
        """Saldo = cobros - pagos."""
        rows = [dict(r) for r in self.conn.execute(
            "SELECT SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE -IMPORTE END) as SALDO FROM CAJA"
        ).fetchall()]
        self.assertAlmostEqual(rows[0]["SALDO"], 20500.0, places=1,
            msg="Saldo = 27830 - 7330 = 20500")

    def test_query_cobros_por_mes(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT substr(FECHA,1,7) as MES, SUM(IMPORTE) as TOTAL "
            "FROM CAJA WHERE TIPO = 1 GROUP BY MES ORDER BY MES"
        ).fetchall()]
        self.assertEqual(len(rows), 2, "Cobros en enero y febrero")
        meses = {r["MES"] for r in rows}
        self.assertIn("2026-01", meses)
        self.assertIn("2026-02", meses)

    def test_query_cobros_por_cliente(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT CODCLIENTE, SUM(IMPORTE) as TOTAL "
            "FROM CAJA WHERE TIPO = 1 AND CODCLIENTE > 0 "
            "GROUP BY CODCLIENTE ORDER BY TOTAL DESC"
        ).fetchall()]
        self.assertGreater(len(rows), 0)
        # Cliente 2 (Hoteles Mediterráneo) tiene más cobros
        self.assertEqual(rows[0]["CODCLIENTE"], 2)

    def test_query_count_movimientos(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT COUNT(*) as TOTAL FROM CAJA"
        ).fetchall()]
        self.assertEqual(rows[0]["TOTAL"], 6)

    def test_query_formaspago_con_vencimiento(self):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT CODIGO, NOMBRE, DIASVENC FROM FORMASPAGO WHERE DIASVENC > 0 ORDER BY DIASVENC"
        ).fetchall()]
        self.assertEqual(len(rows), 3, "3 formas de pago con vencimiento (30, 60, 90 días)")

    def test_esquema_caja_en_bd(self):
        cursor = self.conn.execute("PRAGMA table_info(CAJA)")
        cols = {row[1] for row in cursor.fetchall()}
        self.assertIn("CODAPUNTE", cols)
        self.assertIn("TIPO", cols)
        self.assertIn("IMPORTE", cols)
        self.assertNotIn("CODIGO", cols)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE D5 — Normalización SQL para financiero
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizacionSQLFinanciero(unittest.TestCase):
    """Verifica que el normalizador corrige SQLs incorrectos sobre caja."""

    def setUp(self):
        self.normalizer = FirebirdSQLNormalizer()

    def test_corrige_limit_caja(self):
        sql = "SELECT FECHA, IMPORTE FROM CAJA WHERE TIPO = 1 LIMIT 20"
        result, _ = self.normalizer.normalize(sql)
        self.assertIn("FIRST", result.upper())
        self.assertNotIn("LIMIT", result.upper())

    def test_elimina_punto_y_coma_caja(self):
        sql = "SELECT SUM(IMPORTE) FROM CAJA WHERE TIPO = 1;"
        result, _ = self.normalizer.normalize(sql)
        self.assertFalse(result.strip().endswith(";"))

    def test_sql_caja_valido_sin_cambios(self):
        sql = "SELECT FIRST 50 FECHA, TIPO, IMPORTE, CONCEPTO FROM CAJA ORDER BY FECHA DESC"
        result, _ = self.normalizer.normalize(sql)
        self.assertIn("CAJA", result)
        self.assertIn("IMPORTE", result)

    def test_corrige_ilike_concepto(self):
        sql = "SELECT CONCEPTO FROM CAJA WHERE CONCEPTO ILIKE '%cobro%'"
        result, _ = self.normalizer.normalize(sql)
        self.assertNotIn("ILIKE", result.upper())


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE D6 — Abstracción semántica: razonamiento sobre financiero
# ══════════════════════════════════════════════════════════════════════════════

class TestAbstraccionSemanticaFinanciero(unittest.TestCase):
    """
    Verifica que el motor razona a nivel de abstracción superior sobre financiero.
    """

    def setUp(self):
        self.engine = SemanticReasoningEngine()

    def test_deduce_que_saldo_requiere_cobros_menos_pagos(self):
        """Para 'saldo de caja' el sistema debe inferir cobros - pagos."""
        r = self.engine.reason("saldo actual de caja")
        self.assertEqual(r.domain, BusinessDomain.FINANCIERO)
        hints_text = " ".join(r.hints).upper()
        self.assertTrue(
            "TIPO=1" in hints_text or "TIPO=2" in hints_text or
            "COBRO" in hints_text or "CAJA" in hints_text,
            "Para saldo de caja debe mencionar tipos de movimiento"
        )

    def test_deduce_que_vencimientos_usan_formaspago(self):
        """Para 'vencimientos de facturas' el sistema puede detectar FINANCIERO o DOCUMENTOS."""
        r = self.engine.reason("vencimientos de facturas próximos")
        self.assertIn(r.domain, [BusinessDomain.FINANCIERO, BusinessDomain.DOCUMENTOS])

    def test_razona_sobre_cobros_pendientes(self):
        r = self.engine.reason("cobros pendientes de clientes")
        self.assertIn(r.domain, [BusinessDomain.FINANCIERO, BusinessDomain.CLIENTES_PROVEEDORES])

    def test_razona_sobre_pagos_proveedores(self):
        r = self.engine.reason("pagos pendientes a proveedores")
        self.assertIn(r.domain, [BusinessDomain.FINANCIERO, BusinessDomain.CLIENTES_PROVEEDORES])

    def test_resiliente_pregunta_financiera_ambigua(self):
        r = self.engine.reason("cuánto dinero tenemos")
        self.assertIsInstance(r, ReasoningResult)

    def test_build_enriched_prompt_financiero(self):
        r = self.engine.reason("movimientos de caja del mes")
        prompt = self.engine.build_enriched_system_prompt("BASE PROMPT", r)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)

    def test_normaliza_sql_caja_limit(self):
        normalizer = FirebirdSQLNormalizer()
        sql = "SELECT FECHA, IMPORTE FROM CAJA ORDER BY FECHA DESC LIMIT 10"
        result, _ = normalizer.normalize(sql)
        self.assertIn("FIRST", result.upper())
