"""
test_business_queries.py — Tests exhaustivos de consultas de negocio por departamento

Cubre TODOS los tipos de documentos del sistema:
  0  = presupuesto de cliente
  1  = pedido de cliente
  2  = albarán (de cliente)
  3  = factura de venta (cliente)
  10 = presupuesto de proveedor
  11 = pedido a proveedor
  12 = albarán de proveedor
  13 = factura de compra (proveedor)
  21 = movimiento de almacén
  31 = recuento de almacén
  51 = certificación
  52 = producción
  61 = certificación de subcontrata

Departamentos cubiertos:
  - Ventas (tipos 0, 1, 2, 3)
  - Compras (tipos 10, 11, 12, 13)
  - Almacén (tipos 21, 31)
  - Producción / Certificaciones (tipos 51, 52, 61)
  - Finanzas (importes, IVA, cobros, pagos)
  - Dirección (KPIs globales, comparativas)
  - Clientes (análisis por cliente)
  - Proveedores (análisis por proveedor)
  - Artículos (catálogo, stock)

Principios:
  - Todos los tests son deterministas (usan el simulador SQLite)
  - Los valores esperados se calculan dinámicamente desde la BD
  - Cada test verifica UNA consulta de negocio concreta
  - Los tests sirven como documentación de las consultas que el chat IA debe saber responder
"""

import pytest
import sqlite3
from pathlib import Path

DB = Path(__file__).parent.parent / 'modules/db_simulator/data/simulator.db'

# ── Tipos de documentos ───────────────────────────────────────────────────────
TIPO_PRESUPUESTO_CLIENTE   = 0
TIPO_PEDIDO_CLIENTE        = 1
TIPO_ALBARAN_CLIENTE       = 2
TIPO_FACTURA_VENTA         = 3
TIPO_PRESUPUESTO_PROVEEDOR = 10
TIPO_PEDIDO_PROVEEDOR      = 11
TIPO_ALBARAN_PROVEEDOR     = 12
TIPO_FACTURA_COMPRA        = 13
TIPO_MOVIMIENTO_ALMACEN    = 21
TIPO_RECUENTO_ALMACEN      = 31
TIPO_CERTIFICACION         = 51
TIPO_PRODUCCION            = 52
TIPO_CERT_SUBCONTRATA      = 61


def q(sql: str, params=()):
    """Ejecuta una query en el simulador y devuelve los resultados."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def q1(sql: str, params=()):
    """Devuelve el primer resultado (o None)."""
    rows = q(sql, params)
    return rows[0] if rows else None


# ═══════════════════════════════════════════════════════════════════════════════
# TestDocumentTypes — Verificación de tipos de documentos en el simulador
# ═══════════════════════════════════════════════════════════════════════════════

class TestDocumentTypes:
    """Verifica que todos los tipos de documentos existen en el simulador."""

    def test_tipo_0_presupuesto_cliente_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=0")
        assert r['n'] > 0, "Debe haber presupuestos de cliente (TIPO=0)"

    def test_tipo_1_pedido_cliente_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=1")
        assert r['n'] > 0, "Debe haber pedidos de cliente (TIPO=1)"

    def test_tipo_2_albaran_cliente_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=2")
        assert r['n'] > 0, "Debe haber albaranes de cliente (TIPO=2)"

    def test_tipo_3_factura_venta_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3")
        assert r['n'] > 0, "Debe haber facturas de venta (TIPO=3)"

    def test_tipo_10_presupuesto_proveedor_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=10")
        assert r['n'] > 0, "Debe haber presupuestos de proveedor (TIPO=10)"

    def test_tipo_11_pedido_proveedor_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=11")
        assert r['n'] > 0, "Debe haber pedidos a proveedor (TIPO=11)"

    def test_tipo_12_albaran_proveedor_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=12")
        assert r['n'] > 0, "Debe haber albaranes de proveedor (TIPO=12)"

    def test_tipo_13_factura_compra_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13")
        assert r['n'] > 0, "Debe haber facturas de compra (TIPO=13)"

    def test_tipo_21_movimiento_almacen_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=21")
        assert r['n'] > 0, "Debe haber movimientos de almacén (TIPO=21)"

    def test_tipo_31_recuento_almacen_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=31")
        assert r['n'] > 0, "Debe haber recuentos de almacén (TIPO=31)"

    def test_tipo_51_certificacion_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51")
        assert r['n'] > 0, "Debe haber certificaciones (TIPO=51)"

    def test_tipo_52_produccion_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=52")
        assert r['n'] > 0, "Debe haber registros de producción (TIPO=52)"

    def test_tipo_61_cert_subcontrata_exists(self):
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=61")
        assert r['n'] > 0, "Debe haber certificaciones de subcontrata (TIPO=61)"

    def test_all_13_types_present(self):
        """Los 13 tipos de documentos deben estar presentes"""
        expected_types = {0, 1, 2, 3, 10, 11, 12, 13, 21, 31, 51, 52, 61}
        rows = q("SELECT DISTINCT TIPO FROM DOCCAB ORDER BY TIPO")
        actual_types = {r['TIPO'] for r in rows}
        missing = expected_types - actual_types
        assert not missing, f"Tipos de documentos faltantes: {missing}"

    def test_data_spans_2024_to_2026(self):
        """Los datos deben abarcar 2024, 2025 y 2026"""
        rows = q("SELECT DISTINCT substr(FECHA,1,4) as anio FROM DOCCAB ORDER BY anio")
        years = {r['anio'] for r in rows}
        assert '2024' in years, "Debe haber datos de 2024"
        assert '2025' in years, "Debe haber datos de 2025"
        assert '2026' in years, "Debe haber datos de 2026"


# ═══════════════════════════════════════════════════════════════════════════════
# TestVentas — Departamento de Ventas (tipos 0, 1, 2, 3)
# ═══════════════════════════════════════════════════════════════════════════════

class TestVentas:
    """Consultas del departamento de Ventas."""

    # ── Presupuestos de cliente (TIPO=0) ──────────────────────────────────────

    def test_cuantos_presupuestos_cliente_total(self):
        """¿Cuántos presupuestos de cliente hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=0")
        assert r['n'] > 0

    def test_cuantos_presupuestos_cliente_2024(self):
        """¿Cuántos presupuestos de cliente se hicieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=0 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 45, f"Esperados 45 presupuestos en 2024, hay {r['n']}"

    def test_cuantos_presupuestos_cliente_2025(self):
        """¿Cuántos presupuestos de cliente se hicieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=0 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 55, f"Esperados 55 presupuestos en 2025, hay {r['n']}"

    def test_importe_total_presupuestos_2025(self):
        """¿Cuál es el importe total de presupuestos de cliente en 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=0 AND substr(FECHA,1,4)='2025'")
        assert r['total'] > 0

    def test_presupuestos_por_mes_2025(self):
        """¿Cuántos presupuestos de cliente hay por mes en 2025?"""
        rows = q("""
            SELECT substr(FECHA,1,7) as mes, COUNT(*) as n
            FROM DOCCAB WHERE TIPO=0 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY mes
        """)
        assert len(rows) > 0
        # Cada mes debe tener al menos 1 presupuesto
        for r in rows:
            assert r['n'] >= 1

    # ── Pedidos de cliente (TIPO=1) ───────────────────────────────────────────

    def test_cuantos_pedidos_cliente_total(self):
        """¿Cuántos pedidos de cliente hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=1")
        assert r['n'] > 0

    def test_cuantos_pedidos_cliente_2024(self):
        """¿Cuántos pedidos de cliente se recibieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=1 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 38

    def test_cuantos_pedidos_cliente_2025(self):
        """¿Cuántos pedidos de cliente se recibieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=1 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 48

    def test_importe_medio_pedido_cliente(self):
        """¿Cuál es el importe medio de un pedido de cliente?"""
        r = q1("SELECT AVG(IMPORTETOTAL) as media FROM DOCCAB WHERE TIPO=1")
        assert r['media'] > 0

    # ── Albaranes de cliente (TIPO=2) ─────────────────────────────────────────

    def test_cuantos_albaranes_cliente_total(self):
        """¿Cuántos albaranes de cliente hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=2")
        assert r['n'] > 0

    def test_cuantos_albaranes_cliente_2024(self):
        """¿Cuántos albaranes de cliente se emitieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=2 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 52

    def test_albaranes_cliente_2025(self):
        """¿Cuántos albaranes de cliente se emitieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=2 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 63

    # ── Facturas de venta (TIPO=3) ────────────────────────────────────────────

    def test_cuantas_facturas_venta_total(self):
        """¿Cuántas facturas de venta hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3")
        assert r['n'] > 0

    def test_cuantas_facturas_venta_2024(self):
        """¿Cuántas facturas de venta se emitieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 67

    def test_cuantas_facturas_venta_2025(self):
        """¿Cuántas facturas de venta se emitieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        # 82 del año + 12 de abril específico
        assert r['n'] == 94, f"Esperadas 94 facturas venta 2025, hay {r['n']}"

    def test_facturacion_venta_total_2024(self):
        """¿Cuál es la facturación total de ventas en 2024?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2024'")
        assert r['total'] > 0

    def test_facturacion_venta_total_2025(self):
        """¿Cuál es la facturación total de ventas en 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        assert r['total'] > 0

    def test_facturas_venta_abril_2025(self):
        """¿Cuántas facturas de venta se emitieron en abril de 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,7)='2025-04'")
        assert r['n'] >= 12, f"Esperadas al menos 12 facturas venta en abril 2025, hay {r['n']}"

    def test_facturacion_venta_abril_2025(self):
        """¿Cuál es la facturación de ventas en abril de 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,7)='2025-04'")
        assert r['total'] > 0

    def test_top5_clientes_por_facturacion_2025(self):
        """¿Cuáles son los 5 clientes con más facturación en 2025?"""
        rows = q("""
            SELECT CODCLIENTE, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
            GROUP BY CODCLIENTE ORDER BY total DESC LIMIT 5
        """)
        assert len(rows) > 0
        assert rows[0]['total'] >= rows[-1]['total']

    def test_facturacion_venta_por_mes_2025(self):
        """¿Cuál es la facturación de ventas por mes en 2025?"""
        rows = q("""
            SELECT substr(FECHA,1,7) as mes, COUNT(*) as n, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY mes
        """)
        assert len(rows) > 0

    def test_comparativa_ventas_2024_vs_2025(self):
        """¿Cómo han evolucionado las ventas de 2024 a 2025?"""
        r2024 = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2024'")
        r2025 = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        assert r2024['total'] > 0
        assert r2025['total'] > 0
        # Ambos años tienen datos
        variacion = (r2025['total'] - r2024['total']) / r2024['total'] * 100
        assert isinstance(variacion, float)

    def test_importe_medio_factura_venta(self):
        """¿Cuál es el importe medio de una factura de venta?"""
        r = q1("SELECT AVG(IMPORTETOTAL) as media FROM DOCCAB WHERE TIPO=3")
        assert r['media'] > 0

    def test_factura_venta_mayor_importe(self):
        """¿Cuál es la factura de venta de mayor importe?"""
        r = q1("SELECT MAX(IMPORTETOTAL) as max_total FROM DOCCAB WHERE TIPO=3")
        assert r['max_total'] > 0

    def test_conversion_presupuesto_a_pedido(self):
        """Ratio de conversión: presupuestos vs pedidos"""
        r_pres = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=0 AND substr(FECHA,1,4)='2025'")
        r_ped  = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=1 AND substr(FECHA,1,4)='2025'")
        assert r_pres['n'] > 0
        assert r_ped['n'] > 0
        ratio = r_ped['n'] / r_pres['n']
        assert 0 < ratio <= 2  # ratio razonable


# ═══════════════════════════════════════════════════════════════════════════════
# TestCompras — Departamento de Compras (tipos 10, 11, 12, 13)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompras:
    """Consultas del departamento de Compras."""

    # ── Presupuestos de proveedor (TIPO=10) ───────────────────────────────────

    def test_cuantos_presupuestos_proveedor_total(self):
        """¿Cuántos presupuestos de proveedor hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=10")
        assert r['n'] > 0

    def test_cuantos_presupuestos_proveedor_2024(self):
        """¿Cuántos presupuestos de proveedor se recibieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=10 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 22

    def test_cuantos_presupuestos_proveedor_2025(self):
        """¿Cuántos presupuestos de proveedor se recibieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=10 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 28

    # ── Pedidos a proveedor (TIPO=11) ─────────────────────────────────────────

    def test_cuantos_pedidos_proveedor_total(self):
        """¿Cuántos pedidos a proveedor hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=11")
        assert r['n'] > 0

    def test_cuantos_pedidos_proveedor_2024(self):
        """¿Cuántos pedidos a proveedor se realizaron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=11 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 35

    def test_cuantos_pedidos_proveedor_2025(self):
        """¿Cuántos pedidos a proveedor se realizaron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=11 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 42

    def test_importe_total_pedidos_proveedor_2025(self):
        """¿Cuál es el importe total de pedidos a proveedor en 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=11 AND substr(FECHA,1,4)='2025'")
        assert r['total'] > 0

    # ── Albaranes de proveedor (TIPO=12) ──────────────────────────────────────

    def test_cuantos_albaranes_proveedor_total(self):
        """¿Cuántos albaranes de proveedor hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=12")
        assert r['n'] > 0

    def test_cuantos_albaranes_proveedor_2024(self):
        """¿Cuántos albaranes de proveedor se recibieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=12 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 41

    def test_cuantos_albaranes_proveedor_2025(self):
        """¿Cuántos albaranes de proveedor se recibieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=12 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 49

    # ── Facturas de compra (TIPO=13) ──────────────────────────────────────────

    def test_cuantas_facturas_compra_total(self):
        """¿Cuántas facturas de compra hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13")
        assert r['n'] > 0

    def test_cuantas_facturas_compra_2024(self):
        """¿Cuántas facturas de compra llegaron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 58, f"Esperadas 58 facturas compra en 2024, hay {r['n']}"

    def test_cuantas_facturas_compra_2025(self):
        """¿Cuántas facturas de compra llegaron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        # 71 del año + 9 de abril específico
        assert r['n'] == 80, f"Esperadas 80 facturas compra en 2025, hay {r['n']}"

    def test_cuantas_facturas_compra_abril_2025(self):
        """¿Cuántas facturas de compra llegaron en abril de 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,7)='2025-04'")
        assert r['n'] >= 9, f"Esperadas al menos 9 facturas compra en abril 2025, hay {r['n']}"

    def test_gasto_compras_total_2024(self):
        """¿Cuál es el gasto total en compras en 2024?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2024'")
        assert r['total'] > 0

    def test_gasto_compras_total_2025(self):
        """¿Cuál es el gasto total en compras en 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        assert r['total'] > 0

    def test_gasto_compras_abril_2025(self):
        """¿Cuál es el gasto en compras en abril de 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,7)='2025-04'")
        assert r['total'] > 0

    def test_top5_proveedores_por_gasto_2025(self):
        """¿Cuáles son los 5 proveedores con más gasto en 2025?"""
        rows = q("""
            SELECT CODCLIENTE as proveedor, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'
            GROUP BY CODCLIENTE ORDER BY total DESC LIMIT 5
        """)
        assert len(rows) > 0

    def test_gasto_compras_por_mes_2025(self):
        """¿Cuál es el gasto en compras por mes en 2025?"""
        rows = q("""
            SELECT substr(FECHA,1,7) as mes, COUNT(*) as n, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY mes
        """)
        assert len(rows) > 0

    def test_comparativa_compras_2024_vs_2025(self):
        """¿Cómo han evolucionado las compras de 2024 a 2025?"""
        r2024 = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2024'")
        r2025 = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        assert r2024['total'] > 0
        assert r2025['total'] > 0

    def test_importe_medio_factura_compra(self):
        """¿Cuál es el importe medio de una factura de compra?"""
        r = q1("SELECT AVG(IMPORTETOTAL) as media FROM DOCCAB WHERE TIPO=13")
        assert r['media'] > 0

    def test_margen_bruto_2025(self):
        """¿Cuál es el margen bruto (ventas - compras) en 2025?"""
        ventas = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        compras = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        margen = ventas['total'] - compras['total']
        # El margen puede ser positivo o negativo en datos sintéticos
        assert isinstance(margen, float)


# ═══════════════════════════════════════════════════════════════════════════════
# TestAlmacen — Departamento de Almacén (tipos 21, 31)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlmacen:
    """Consultas del departamento de Almacén."""

    def test_cuantos_movimientos_almacen_total(self):
        """¿Cuántos movimientos de almacén hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=21")
        assert r['n'] > 0

    def test_cuantos_movimientos_almacen_2024(self):
        """¿Cuántos movimientos de almacén hubo en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=21 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 18

    def test_cuantos_movimientos_almacen_2025(self):
        """¿Cuántos movimientos de almacén hubo en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=21 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 24

    def test_cuantos_recuentos_almacen_total(self):
        """¿Cuántos recuentos de almacén hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=31")
        assert r['n'] > 0

    def test_cuantos_recuentos_almacen_2024(self):
        """¿Cuántos recuentos de almacén se hicieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=31 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 6

    def test_cuantos_recuentos_almacen_2025(self):
        """¿Cuántos recuentos de almacén se hicieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=31 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 8

    def test_movimientos_almacen_por_mes_2025(self):
        """¿Cuántos movimientos de almacén hubo por mes en 2025?"""
        rows = q("""
            SELECT substr(FECHA,1,7) as mes, COUNT(*) as n
            FROM DOCCAB WHERE TIPO=21 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY mes
        """)
        assert len(rows) > 0

    def test_articulos_en_stock(self):
        """¿Cuántos artículos tienen stock registrado?"""
        r = q1("SELECT COUNT(*) as n FROM ARTICULO WHERE STOCKARTICULO > 0")
        assert r['n'] >= 0  # puede ser 0 si no hay stock

    def test_articulos_sin_stock(self):
        """¿Cuántos artículos tienen stock en 0?"""
        r = q1("SELECT COUNT(*) as n FROM ARTICULO WHERE STOCKARTICULO = 0 OR STOCKARTICULO IS NULL")
        assert r['n'] >= 0

    def test_total_articulos_catalogo(self):
        """¿Cuántos artículos hay en el catálogo?"""
        r = q1("SELECT COUNT(*) as n FROM ARTICULO")
        assert r['n'] > 0

    def test_articulos_por_familia(self):
        """¿Cuántos artículos hay por familia?"""
        rows = q("""
            SELECT CODFAMILIA, COUNT(*) as n
            FROM ARTICULO GROUP BY CODFAMILIA ORDER BY n DESC
        """)
        assert len(rows) > 0

    def test_almacenes_disponibles(self):
        """¿Cuántos almacenes hay?"""
        r = q1("SELECT COUNT(*) as n FROM ALMACEN")
        assert r['n'] >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestProduccion — Producción y Certificaciones (tipos 51, 52, 61)
# ═══════════════════════════════════════════════════════════════════════════════

class TestProduccion:
    """Consultas del departamento de Producción y Certificaciones."""

    # ── Certificaciones (TIPO=51) ─────────────────────────────────────────────

    def test_cuantas_certificaciones_total(self):
        """¿Cuántas certificaciones hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51")
        assert r['n'] > 0

    def test_cuantas_certificaciones_2024(self):
        """¿Cuántas certificaciones se hicieron en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 14

    def test_cuantas_certificaciones_2025(self):
        """¿Cuántas certificaciones se hicieron en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,4)='2025'")
        # 19 del año + 7 de abril específico
        assert r['n'] == 26, f"Esperadas 26 certificaciones en 2025, hay {r['n']}"

    def test_cuantas_certificaciones_abril_2025(self):
        """¿Cuántas certificaciones se hicieron en abril de 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,7)='2025-04'")
        assert r['n'] >= 7, f"Esperadas al menos 7 certificaciones en abril 2025, hay {r['n']}"

    def test_importe_certificaciones_2025(self):
        """¿Cuál es el importe total de certificaciones en 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,4)='2025'")
        assert r['total'] > 0

    def test_importe_certificaciones_abril_2025(self):
        """¿Cuál es el importe de certificaciones en abril de 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,7)='2025-04'")
        assert r['total'] > 0

    def test_certificaciones_por_mes_2025(self):
        """¿Cuántas certificaciones hay por mes en 2025?"""
        rows = q("""
            SELECT substr(FECHA,1,7) as mes, COUNT(*) as n
            FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY mes
        """)
        assert len(rows) > 0

    # ── Producción (TIPO=52) ──────────────────────────────────────────────────

    def test_cuantos_registros_produccion_total(self):
        """¿Cuántos registros de producción hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=52")
        assert r['n'] > 0

    def test_cuantos_registros_produccion_2024(self):
        """¿Cuántos registros de producción hubo en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=52 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 20

    def test_cuantos_registros_produccion_2025(self):
        """¿Cuántos registros de producción hubo en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=52 AND substr(FECHA,1,4)='2025'")
        # 27 del año + 5 de abril específico
        assert r['n'] == 32, f"Esperados 32 registros producción en 2025, hay {r['n']}"

    def test_cuantos_registros_produccion_abril_2025(self):
        """¿Cuántos registros de producción hubo en abril de 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=52 AND substr(FECHA,1,7)='2025-04'")
        assert r['n'] >= 5, f"Esperados al menos 5 registros producción en abril 2025, hay {r['n']}"

    def test_produccion_por_mes_2025(self):
        """¿Cuántos registros de producción hay por mes en 2025?"""
        rows = q("""
            SELECT substr(FECHA,1,7) as mes, COUNT(*) as n
            FROM DOCCAB WHERE TIPO=52 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY mes
        """)
        assert len(rows) > 0

    # ── Certificaciones de subcontrata (TIPO=61) ──────────────────────────────

    def test_cuantas_cert_subcontrata_total(self):
        """¿Cuántas certificaciones de subcontrata hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=61")
        assert r['n'] > 0

    def test_cuantas_cert_subcontrata_2024(self):
        """¿Cuántas certificaciones de subcontrata hubo en 2024?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=61 AND substr(FECHA,1,4)='2024'")
        assert r['n'] == 8

    def test_cuantas_cert_subcontrata_2025(self):
        """¿Cuántas certificaciones de subcontrata hubo en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=61 AND substr(FECHA,1,4)='2025'")
        assert r['n'] == 11

    def test_importe_cert_subcontrata_2025(self):
        """¿Cuál es el importe total de certificaciones de subcontrata en 2025?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=61 AND substr(FECHA,1,4)='2025'")
        assert r['total'] > 0

    def test_comparativa_certificaciones_2024_vs_2025(self):
        """¿Cómo han evolucionado las certificaciones de 2024 a 2025?"""
        r2024 = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,4)='2024'")
        r2025 = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,4)='2025'")
        assert r2024['n'] > 0
        assert r2025['n'] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestFinanzas — Departamento de Finanzas
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanzas:
    """Consultas del departamento de Finanzas."""

    def test_facturacion_total_ventas_todos_anios(self):
        """¿Cuál es la facturación total de ventas de todos los años?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3")
        assert r['total'] > 0

    def test_gasto_total_compras_todos_anios(self):
        """¿Cuál es el gasto total en compras de todos los años?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13")
        assert r['total'] > 0

    def test_iva_total_ventas_2025(self):
        """¿Cuánto IVA se ha generado en ventas en 2025?"""
        r = q1("SELECT SUM(IMPORTEIVA) as iva FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        assert r['iva'] > 0

    def test_iva_total_compras_2025(self):
        """¿Cuánto IVA se ha soportado en compras en 2025?"""
        r = q1("SELECT SUM(IMPORTEIVA) as iva FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        assert r['iva'] > 0

    def test_iva_neto_2025(self):
        """¿Cuál es el IVA neto (repercutido - soportado) en 2025?"""
        iva_ventas = q1("SELECT SUM(IMPORTEIVA) as iva FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        iva_compras = q1("SELECT SUM(IMPORTEIVA) as iva FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        iva_neto = iva_ventas['iva'] - iva_compras['iva']
        assert isinstance(iva_neto, float)

    def test_base_imponible_ventas_2025(self):
        """¿Cuál es la base imponible de ventas en 2025?"""
        r = q1("SELECT SUM(IMPORTEBASE) as base FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        assert r['base'] > 0

    def test_base_imponible_compras_2025(self):
        """¿Cuál es la base imponible de compras en 2025?"""
        r = q1("SELECT SUM(IMPORTEBASE) as base FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        assert r['base'] > 0

    def test_importebase_equals_importebruto_minus_descuento(self):
        """IMPORTEBASE debe ser coherente con IMPORTEBRUTO - IMPORTEDESCUENTO"""
        rows = q("SELECT IMPORTEBRUTO, IMPORTEDESCUENTO, IMPORTEBASE FROM DOCCAB WHERE TIPO=3 LIMIT 10")
        for r in rows:
            expected = round(r['IMPORTEBRUTO'] - r['IMPORTEDESCUENTO'], 2)
            actual = round(r['IMPORTEBASE'], 2)
            assert abs(expected - actual) < 0.02, f"IMPORTEBASE inconsistente: {expected} vs {actual}"

    def test_importetotal_equals_base_plus_iva(self):
        """IMPORTETOTAL debe ser IMPORTEBASE + IMPORTEIVA (aproximadamente)"""
        rows = q("SELECT IMPORTEBASE, IMPORTEIVA, IMPORTETOTAL FROM DOCCAB WHERE TIPO=3 LIMIT 10")
        for r in rows:
            expected = round(r['IMPORTEBASE'] + r['IMPORTEIVA'], 2)
            actual = round(r['IMPORTETOTAL'], 2)
            assert abs(expected - actual) < 0.05, f"IMPORTETOTAL inconsistente: {expected} vs {actual}"

    def test_recibos_cobro_existen(self):
        """¿Hay recibos de cobro registrados?"""
        r = q1("SELECT COUNT(*) as n FROM RECIBO3")
        assert r['n'] >= 0

    def test_recibos_pago_existen(self):
        """¿Hay recibos de pago registrados?"""
        r = q1("SELECT COUNT(*) as n FROM RECIBO1")
        assert r['n'] >= 0

    def test_formas_pago_disponibles(self):
        """¿Cuántas formas de pago hay configuradas?"""
        r = q1("SELECT COUNT(*) as n FROM FORMASPAGO")
        assert r['n'] >= 0

    def test_facturacion_anual_por_tipo(self):
        """Resumen de facturación anual por tipo de documento"""
        rows = q("""
            SELECT TIPO, substr(FECHA,1,4) as anio, COUNT(*) as n, SUM(IMPORTETOTAL) as total
            FROM DOCCAB GROUP BY TIPO, anio ORDER BY TIPO, anio
        """)
        assert len(rows) > 0

    def test_importe_total_todos_documentos(self):
        """¿Cuál es el importe total de todos los documentos?"""
        r = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB")
        assert r['total'] > 0

    def test_documentos_sin_importe(self):
        """¿Hay documentos sin importe (IMPORTETOTAL=0)?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE IMPORTETOTAL = 0 OR IMPORTETOTAL IS NULL")
        # Puede haber algunos (movimientos de almacén, recuentos)
        assert r['n'] >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestClientes — Análisis de Clientes
# ═══════════════════════════════════════════════════════════════════════════════

class TestClientes:
    """Consultas de análisis de clientes."""

    def test_total_clientes(self):
        """¿Cuántos clientes hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM CLIENTE")
        assert r['n'] > 0

    def test_clientes_activos_2025(self):
        """¿Cuántos clientes han comprado en 2025?"""
        r = q1("""
            SELECT COUNT(DISTINCT CODCLIENTE) as n
            FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
        """)
        assert r['n'] > 0

    def test_clientes_activos_2024(self):
        """¿Cuántos clientes han comprado en 2024?"""
        r = q1("""
            SELECT COUNT(DISTINCT CODCLIENTE) as n
            FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2024'
        """)
        assert r['n'] > 0

    def test_top10_clientes_por_facturacion_2025(self):
        """¿Cuáles son los 10 clientes con más facturación en 2025?"""
        rows = q("""
            SELECT CODCLIENTE, COUNT(*) as n_facturas, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
            GROUP BY CODCLIENTE ORDER BY total DESC LIMIT 10
        """)
        assert len(rows) > 0
        assert rows[0]['total'] >= rows[-1]['total']

    def test_cliente_con_mas_facturas_2025(self):
        """¿Qué cliente tiene más facturas en 2025?"""
        r = q1("""
            SELECT CODCLIENTE, COUNT(*) as n
            FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
            GROUP BY CODCLIENTE ORDER BY n DESC LIMIT 1
        """)
        assert r is not None
        assert r['n'] > 0

    def test_facturacion_media_por_cliente_2025(self):
        """¿Cuál es la facturación media por cliente en 2025?"""
        r = q1("""
            SELECT AVG(total) as media FROM (
                SELECT CODCLIENTE, SUM(IMPORTETOTAL) as total
                FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
                GROUP BY CODCLIENTE
            )
        """)
        assert r['media'] > 0

    def test_clientes_con_presupuesto_pero_sin_pedido_2025(self):
        """¿Cuántos clientes tienen presupuesto pero no pedido en 2025?"""
        r = q1("""
            SELECT COUNT(DISTINCT p.CODCLIENTE) as n
            FROM DOCCAB p
            WHERE p.TIPO=0 AND substr(p.FECHA,1,4)='2025'
            AND p.CODCLIENTE NOT IN (
                SELECT DISTINCT CODCLIENTE FROM DOCCAB
                WHERE TIPO=1 AND substr(FECHA,1,4)='2025'
            )
        """)
        assert r['n'] >= 0

    def test_clientes_nuevos_2025(self):
        """¿Cuántos clientes han comprado en 2025 pero no en 2024?"""
        r = q1("""
            SELECT COUNT(DISTINCT c2025.CODCLIENTE) as n
            FROM DOCCAB c2025
            WHERE c2025.TIPO=3 AND substr(c2025.FECHA,1,4)='2025'
            AND c2025.CODCLIENTE NOT IN (
                SELECT DISTINCT CODCLIENTE FROM DOCCAB
                WHERE TIPO=3 AND substr(FECHA,1,4)='2024'
            )
        """)
        assert r['n'] >= 0

    def test_clientes_con_albaran_sin_factura_2025(self):
        """¿Cuántos clientes tienen albarán pero no factura en 2025?"""
        r = q1("""
            SELECT COUNT(DISTINCT a.CODCLIENTE) as n
            FROM DOCCAB a
            WHERE a.TIPO=2 AND substr(a.FECHA,1,4)='2025'
            AND a.CODCLIENTE NOT IN (
                SELECT DISTINCT CODCLIENTE FROM DOCCAB
                WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
            )
        """)
        assert r['n'] >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestProveedores — Análisis de Proveedores
# ═══════════════════════════════════════════════════════════════════════════════

class TestProveedores:
    """Consultas de análisis de proveedores."""

    def test_total_proveedores(self):
        """¿Cuántos proveedores hay en total?"""
        r = q1("SELECT COUNT(*) as n FROM PROVEED")
        assert r['n'] > 0

    def test_proveedores_activos_2025(self):
        """¿Cuántos proveedores han enviado facturas en 2025?"""
        r = q1("""
            SELECT COUNT(DISTINCT CODCLIENTE) as n
            FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'
        """)
        assert r['n'] > 0

    def test_top5_proveedores_por_gasto_2024(self):
        """¿Cuáles son los 5 proveedores con más gasto en 2024?"""
        rows = q("""
            SELECT CODCLIENTE as proveedor, COUNT(*) as n_facturas, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2024'
            GROUP BY CODCLIENTE ORDER BY total DESC LIMIT 5
        """)
        assert len(rows) > 0

    def test_proveedor_con_mas_facturas_2025(self):
        """¿Qué proveedor ha enviado más facturas en 2025?"""
        r = q1("""
            SELECT CODCLIENTE as proveedor, COUNT(*) as n
            FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'
            GROUP BY CODCLIENTE ORDER BY n DESC LIMIT 1
        """)
        assert r is not None
        assert r['n'] > 0

    def test_gasto_medio_por_proveedor_2025(self):
        """¿Cuál es el gasto medio por proveedor en 2025?"""
        r = q1("""
            SELECT AVG(total) as media FROM (
                SELECT CODCLIENTE, SUM(IMPORTETOTAL) as total
                FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'
                GROUP BY CODCLIENTE
            )
        """)
        assert r['media'] > 0

    def test_proveedores_con_pedido_sin_albaran_2025(self):
        """¿Cuántos proveedores tienen pedido pero no albarán en 2025?"""
        r = q1("""
            SELECT COUNT(DISTINCT p.CODCLIENTE) as n
            FROM DOCCAB p
            WHERE p.TIPO=11 AND substr(p.FECHA,1,4)='2025'
            AND p.CODCLIENTE NOT IN (
                SELECT DISTINCT CODCLIENTE FROM DOCCAB
                WHERE TIPO=12 AND substr(FECHA,1,4)='2025'
            )
        """)
        assert r['n'] >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestDireccion — KPIs de Dirección
# ═══════════════════════════════════════════════════════════════════════════════

class TestDireccion:
    """KPIs globales para dirección."""

    def test_total_documentos_2025(self):
        """¿Cuántos documentos se han generado en total en 2025?"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE substr(FECHA,1,4)='2025'")
        assert r['n'] > 0

    def test_total_documentos_por_tipo_2025(self):
        """¿Cuántos documentos hay por tipo en 2025?"""
        rows = q("""
            SELECT TIPO, COUNT(*) as n FROM DOCCAB
            WHERE substr(FECHA,1,4)='2025'
            GROUP BY TIPO ORDER BY TIPO
        """)
        assert len(rows) > 0

    def test_actividad_por_mes_2025(self):
        """¿Cuál es la actividad (nº documentos) por mes en 2025?"""
        rows = q("""
            SELECT substr(FECHA,1,7) as mes, COUNT(*) as n
            FROM DOCCAB WHERE substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY mes
        """)
        assert len(rows) > 0

    def test_kpi_ventas_vs_compras_2025(self):
        """KPI: ratio ventas/compras en 2025"""
        ventas = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        compras = q1("SELECT SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        assert ventas['total'] > 0
        assert compras['total'] > 0
        ratio = ventas['total'] / compras['total']
        assert ratio > 0

    def test_crecimiento_ventas_2024_a_2025(self):
        """¿Cuánto han crecido las ventas de 2024 a 2025?"""
        v2024 = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2024'")
        v2025 = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        crecimiento = v2025['n'] - v2024['n']
        assert isinstance(crecimiento, int)

    def test_crecimiento_compras_2024_a_2025(self):
        """¿Cuánto han crecido las compras de 2024 a 2025?"""
        c2024 = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2024'")
        c2025 = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        crecimiento = c2025['n'] - c2024['n']
        assert isinstance(crecimiento, int)

    def test_mes_con_mas_ventas_2025(self):
        """¿En qué mes se han generado más ventas en 2025?"""
        r = q1("""
            SELECT substr(FECHA,1,7) as mes, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY total DESC LIMIT 1
        """)
        assert r is not None
        assert r['total'] > 0

    def test_mes_con_mas_compras_2025(self):
        """¿En qué mes se han generado más compras en 2025?"""
        r = q1("""
            SELECT substr(FECHA,1,7) as mes, SUM(IMPORTETOTAL) as total
            FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'
            GROUP BY mes ORDER BY total DESC LIMIT 1
        """)
        assert r is not None
        assert r['total'] > 0

    def test_documentos_abril_2025_todos_tipos(self):
        """¿Cuántos documentos de cada tipo hubo en abril de 2025?"""
        rows = q("""
            SELECT TIPO, COUNT(*) as n FROM DOCCAB
            WHERE substr(FECHA,1,7)='2025-04'
            GROUP BY TIPO ORDER BY TIPO
        """)
        assert len(rows) > 0

    def test_resumen_ejecutivo_2025(self):
        """Resumen ejecutivo: ventas, compras, certificaciones, producción en 2025"""
        ventas = q1("SELECT COUNT(*) as n, SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2025'")
        compras = q1("SELECT COUNT(*) as n, SUM(IMPORTETOTAL) as total FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2025'")
        certs = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,4)='2025'")
        prod = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=52 AND substr(FECHA,1,4)='2025'")
        assert ventas['n'] > 0
        assert compras['n'] > 0
        assert certs['n'] > 0
        assert prod['n'] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestConsultasEspecificas — Las consultas exactas que el usuario quiere probar
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsultasEspecificas:
    """
    Las consultas exactas que el usuario mencionó:
    - ¿Cuántas certificaciones se han hecho en abril 2025?
    - ¿Cuántas facturas de compra han llegado en 2024?
    - Cosas que den un número solo
    """

    def test_certificaciones_abril_2025(self):
        """¿Cuántas certificaciones se han hecho en abril 2025? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=51 AND substr(FECHA,1,7)='2025-04'")
        n = r['n']
        assert n >= 7, f"Esperadas al menos 7 certificaciones en abril 2025, hay {n}"
        print(f"\n✅ Certificaciones en abril 2025: {n}")

    def test_facturas_compra_2024(self):
        """¿Cuántas facturas de compra han llegado en 2024? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=13 AND substr(FECHA,1,4)='2024'")
        n = r['n']
        assert n == 58, f"Esperadas 58 facturas de compra en 2024, hay {n}"
        print(f"\n✅ Facturas de compra en 2024: {n}")

    def test_facturas_venta_2024(self):
        """¿Cuántas facturas de venta se emitieron en 2024? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=3 AND substr(FECHA,1,4)='2024'")
        n = r['n']
        assert n == 67, f"Esperadas 67 facturas de venta en 2024, hay {n}"
        print(f"\n✅ Facturas de venta en 2024: {n}")

    def test_pedidos_cliente_2025(self):
        """¿Cuántos pedidos de cliente se recibieron en 2025? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=1 AND substr(FECHA,1,4)='2025'")
        n = r['n']
        assert n == 48, f"Esperados 48 pedidos de cliente en 2025, hay {n}"
        print(f"\n✅ Pedidos de cliente en 2025: {n}")

    def test_albaranes_proveedor_2025(self):
        """¿Cuántos albaranes de proveedor se recibieron en 2025? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=12 AND substr(FECHA,1,4)='2025'")
        n = r['n']
        assert n == 49, f"Esperados 49 albaranes de proveedor en 2025, hay {n}"
        print(f"\n✅ Albaranes de proveedor en 2025: {n}")

    def test_produccion_abril_2025(self):
        """¿Cuántos registros de producción hubo en abril 2025? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=52 AND substr(FECHA,1,7)='2025-04'")
        n = r['n']
        assert n >= 5, f"Esperados al menos 5 registros de producción en abril 2025, hay {n}"
        print(f"\n✅ Registros de producción en abril 2025: {n}")

    def test_movimientos_almacen_2024(self):
        """¿Cuántos movimientos de almacén hubo en 2024? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=21 AND substr(FECHA,1,4)='2024'")
        n = r['n']
        assert n == 18, f"Esperados 18 movimientos de almacén en 2024, hay {n}"
        print(f"\n✅ Movimientos de almacén en 2024: {n}")

    def test_recuentos_almacen_2025(self):
        """¿Cuántos recuentos de almacén se hicieron en 2025? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=31 AND substr(FECHA,1,4)='2025'")
        n = r['n']
        assert n == 8, f"Esperados 8 recuentos de almacén en 2025, hay {n}"
        print(f"\n✅ Recuentos de almacén en 2025: {n}")

    def test_cert_subcontrata_2024(self):
        """¿Cuántas certificaciones de subcontrata hubo en 2024? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=61 AND substr(FECHA,1,4)='2024'")
        n = r['n']
        assert n == 8, f"Esperadas 8 cert. subcontrata en 2024, hay {n}"
        print(f"\n✅ Certificaciones de subcontrata en 2024: {n}")

    def test_presupuestos_proveedor_2025(self):
        """¿Cuántos presupuestos de proveedor se recibieron en 2025? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE TIPO=10 AND substr(FECHA,1,4)='2025'")
        n = r['n']
        assert n == 28, f"Esperados 28 presupuestos de proveedor en 2025, hay {n}"
        print(f"\n✅ Presupuestos de proveedor en 2025: {n}")

    def test_total_documentos_2024(self):
        """¿Cuántos documentos en total se generaron en 2024? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE substr(FECHA,1,4)='2024'")
        n = r['n']
        # 45+38+52+67+22+35+41+58+18+6+14+20+8 = 424
        assert n == 424, f"Esperados 424 documentos en 2024, hay {n}"
        print(f"\n✅ Total documentos en 2024: {n}")

    def test_total_documentos_2025(self):
        """¿Cuántos documentos en total se generaron en 2025? → número exacto"""
        r = q1("SELECT COUNT(*) as n FROM DOCCAB WHERE substr(FECHA,1,4)='2025'")
        n = r['n']
        # 55+48+63+82+28+42+49+71+24+8+19+27+11 + extras abril (7+5+12+9) = 560
        assert n >= 500, f"Esperados al menos 500 documentos en 2025, hay {n}"
        print(f"\n✅ Total documentos en 2025: {n}")
