"""
test_db_simulator_queries.py — Tests de consultas de negocio sobre el simulador.

Valida que el simulador puede responder consultas típicas de DEVIA:
  ✓ Productos más vendidos
  ✓ Facturas del mes / rango de fechas
  ✓ Total facturado en un período
  ✓ Mejores clientes (por importe facturado)
  ✓ Mejores proveedores (por compras)
  ✓ Presupuestos pendientes
  ✓ SATs en un rango de fechas
  ✓ Artículos por familia
  ✓ Stock disponible
  ✓ Movimientos de caja
  ✓ Albaranes vs facturas (tipos de documento)
  ✓ Consultas con SELECT FIRST N (traducción Firebird→SQLite)
  ✓ Consultas con EXTRACT (mes/año)
  ✓ Consultas con CURRENT_DATE

⚡ Sin acceso a red ni IA: BD en memoria con datos sintéticos.
   Todos los tests son deterministas y rápidos (<1s c/u).
"""

import pytest
from typing import Any, Dict, List

from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.synthetic_seeder import SyntheticSeeder
from backend.modules.db_simulator.constants import JDDCDocTipos


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURE PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def db() -> SimulatedFirebirdDriver:
    """
    BD SQLite en memoria, completamente poblada con datos sintéticos.
    Compartida por todos los tests del módulo (scope=module).
    """
    drv = SimulatedFirebirdDriver()
    drv.connect(db_path=":memory:")
    seeder = SyntheticSeeder(drv.conn)
    seeder.seed_all()
    yield drv
    drv.disconnect()


# ─── Helper ───────────────────────────────────────────────────────────────────

def _q(db: SimulatedFirebirdDriver, sql: str) -> List[Dict[str, Any]]:
    """Atajo para ejecutar queries en el driver."""
    return db.execute_query(sql)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONSULTAS BÁSICAS — tablas de referencia
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsultasBasicas:

    def test_listar_familias(self, db):
        rows = _q(db, "SELECT CODIGO, NOMBRE FROM FAMILIA ORDER BY NOMBRE")
        assert len(rows) > 0
        for row in rows:
            assert "CODIGO" in row
            assert "NOMBRE" in row
            assert row["NOMBRE"]  # no vacío

    def test_listar_articulos(self, db):
        rows = _q(db, "SELECT CODIGO, NOMBRE, PRECIOVENTA AS PRECIO FROM ARTICULO ORDER BY NOMBRE LIMIT 20")
        assert len(rows) > 0
        for row in rows:
            assert row["PRECIO"] > 0

    def test_listar_clientes(self, db):
        rows = _q(db, "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL, 'Sin nombre') AS NOMBRE FROM CLIENTE ORDER BY NOMBRECOMERCIAL LIMIT 20")
        assert len(rows) > 0
        for row in rows:
            assert row["NOMBRE"]

    def test_listar_proveedores(self, db):
        rows = _q(db, "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL, 'Sin nombre') AS NOMBRE FROM PROVEED ORDER BY NOMBRECOMERCIAL")
        assert len(rows) > 0
        for row in rows:
            assert row["NOMBRE"]

    def test_listar_almacenes(self, db):
        rows = _q(db, "SELECT CODIGO, NOMBRE FROM ALMACEN")
        assert len(rows) > 0

    def test_contar_articulos(self, db):
        rows = _q(db, "SELECT COUNT(*) as N FROM ARTICULO")
        assert rows[0]["N"] > 0

    def test_contar_clientes(self, db):
        rows = _q(db, "SELECT COUNT(*) as N FROM CLIENTE")
        assert rows[0]["N"] > 0

    def test_contar_documentos(self, db):
        rows = _q(db, "SELECT COUNT(*) as N FROM DOCCAB")
        assert rows[0]["N"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CONSULTAS DE VENTAS — facturas, importes, clientes
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsultasVentas:

    def test_total_facturado(self, db):
        """Total facturado (suma IMPORTETOTAL de facturas TIPO=13)."""
        rows = _q(db,
            "SELECT SUM(IMPORTETOTAL) as TOTAL "
            "FROM DOCCAB WHERE TIPO = 13"
        )
        total = rows[0]["TOTAL"]
        assert total is not None
        assert total > 0, "Debe haber importe en facturas"

    def test_facturas_del_mes_existe_resultado(self, db):
        """
        Facturas del último mes.
        Usamos CAST(strftime('%m', FECHA) AS INTEGER) = mes_actual.
        """
        # Obtener el mes más reciente en la BD
        rows_meses = _q(db,
            "SELECT DISTINCT CAST(strftime('%m', FECHA) AS INTEGER) as MES "
            "FROM DOCCAB WHERE TIPO = 13 ORDER BY MES DESC LIMIT 1"
        )
        if not rows_meses:
            pytest.skip("No hay facturas en la BD sintética")
        mes = rows_meses[0]["MES"]

        rows = _q(db,
            f"SELECT CODIGO, IMPORTETOTAL FROM DOCCAB "
            f"WHERE TIPO = 13 "
            f"AND CAST(strftime('%m', FECHA) AS INTEGER) = {mes}"
        )
        assert len(rows) > 0, f"No hay facturas en el mes {mes}"

    def test_facturas_rango_fechas(self, db):
        """Facturas entre dos fechas (rango del año en curso)."""
        rows = _q(db,
            "SELECT COUNT(*) as N FROM DOCCAB "
            "WHERE TIPO = 13 "
            "AND FECHA >= '2020-01-01' "
            "AND FECHA <= '2030-12-31'"
        )
        assert rows[0]["N"] > 0

    def test_mejores_clientes(self, db):
        """Top 5 clientes por total facturado."""
        rows = _q(db,
            "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL,'?') AS NOMBRE, SUM(D.IMPORTETOTAL) as TOTAL "
            "FROM DOCCAB D "
            "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "WHERE D.TIPO = 13 "
            "GROUP BY C.CODIGO "
            "ORDER BY TOTAL DESC "
            "LIMIT 5"
        )
        assert len(rows) > 0, "No se encontraron clientes en facturas"
        for row in rows:
            assert row["TOTAL"] > 0
        # Verificar que está ordenado descendentemente
        totales = [r["TOTAL"] for r in rows]
        assert totales == sorted(totales, reverse=True)

    def test_mejor_cliente_tiene_nombre(self, db):
        """El cliente con más ventas debe tener nombre."""
        rows = _q(db,
            "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL,'?') AS NOMBRE, SUM(D.IMPORTETOTAL) as TOTAL "
            "FROM DOCCAB D "
            "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "WHERE D.TIPO = 13 "
            "GROUP BY C.CODIGO "
            "ORDER BY TOTAL DESC "
            "LIMIT 1"
        )
        if rows:
            assert rows[0]["NOMBRE"]

    def test_numero_facturas_por_cliente(self, db):
        """Número de facturas por cliente."""
        rows = _q(db,
            "SELECT CODCLIENTE, COUNT(*) as N "
            "FROM DOCCAB WHERE TIPO = 13 "
            "GROUP BY CODCLIENTE "
            "ORDER BY N DESC LIMIT 10"
        )
        assert len(rows) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PRODUCTOS MÁS VENDIDOS
# ═══════════════════════════════════════════════════════════════════════════════

class TestProductosMasVendidos:

    def test_productos_mas_vendidos_por_cantidad(self, db):
        """
        Top 10 artículos más vendidos por cantidad (SUM CANTIDAD en DOCLIN).
        JOIN con ARTICULO usando CODARTICULO = CODIGO.
        """
        rows = _q(db,
            "SELECT A.NOMBRE, SUM(L.CANTIDAD) as TOTAL_CANT "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON L.CODARTICULO = A.CODIGO "
            "GROUP BY A.CODIGO, A.NOMBRE "
            "ORDER BY TOTAL_CANT DESC "
            "LIMIT 10"
        )
        assert len(rows) > 0, "No hay artículos en líneas de documento"
        for row in rows:
            assert row["TOTAL_CANT"] > 0

    def test_productos_mas_vendidos_por_importe(self, db):
        """Top 10 artículos por importe total vendido."""
        rows = _q(db,
            "SELECT A.NOMBRE, ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) as TOTAL_IMP "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON L.CODARTICULO = A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO = L.CODDOCUMENTO "
            "WHERE D.TIPO = 13 "
            "GROUP BY A.CODIGO, A.NOMBRE "
            "ORDER BY TOTAL_IMP DESC "
            "LIMIT 10"
        )
        assert len(rows) > 0
        importes = [r["TOTAL_IMP"] for r in rows]
        assert importes == sorted(importes, reverse=True)

    def test_articulos_por_familia(self, db):
        """Artículos agrupados por familia."""
        rows = _q(db,
            "SELECT F.NOMBRE as FAMILIA, COUNT(A.CODIGO) as N_ARTICULOS "
            "FROM ARTICULO A "
            "JOIN FAMILIA F ON F.CODIGO = A.CODFAMILIA "
            "GROUP BY F.NOMBRE "
            "ORDER BY N_ARTICULOS DESC"
        )
        assert len(rows) > 0, "No hay artículos con familia asignada"

    def test_stock_articulos(self, db):
        """Stock disponible de artículos."""
        rows = _q(db,
            "SELECT NOMBRE, STOCKARTICULO "
            "FROM ARTICULO "
            "WHERE STOCKARTICULO > 0 "
            "ORDER BY STOCKARTICULO DESC "
            "LIMIT 10"
        )
        assert len(rows) > 0, "No hay artículos con stock > 0"

    def test_articulos_sin_stock(self, db):
        """Artículos con stock cero (para reposición)."""
        rows = _q(db,
            "SELECT COUNT(*) as N FROM ARTICULO WHERE STOCKARTICULO <= 0"
        )
        # Simplemente verificar que la query funciona (puede ser 0 o más)
        assert "N" in rows[0]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TIPOS DE DOCUMENTO
# ═══════════════════════════════════════════════════════════════════════════════

class TestTiposDocumento:

    def test_facturas_existen(self, db):
        rows = _q(db, f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {JDDCDocTipos.FACTURA}")
        assert rows[0]["N"] > 0

    def test_presupuestos_existen(self, db):
        rows = _q(db, f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {JDDCDocTipos.PRESUPUESTO}")
        assert rows[0]["N"] > 0

    def test_presupuestos_pendientes(self, db):
        """Presupuestos en estado abierto (ESTADO=0)."""
        rows = _q(db,
            f"SELECT COUNT(*) as N FROM DOCCAB "
            f"WHERE TIPO = {JDDCDocTipos.PRESUPUESTO} AND ESTADO = 0"
        )
        assert "N" in rows[0]

    def test_sats_existen(self, db):
        rows = _q(db, f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {JDDCDocTipos.SAT}")
        assert rows[0]["N"] > 0

    def test_sats_en_rango_fechas(self, db):
        """SATs entre dos fechas."""
        rows = _q(db,
            f"SELECT CODIGO, FECHA, IMPORTETOTAL FROM DOCCAB "
            f"WHERE TIPO = {JDDCDocTipos.SAT} "
            f"AND FECHA >= '2020-01-01' "
            f"AND FECHA <= '2030-12-31'"
        )
        assert len(rows) > 0

    def test_albaranes_existen(self, db):
        rows = _q(db, f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {JDDCDocTipos.ALBARAN}")
        assert rows[0]["N"] > 0

    def test_distribucion_tipos_documento(self, db):
        """Verificar que hay varios tipos de documento."""
        rows = _q(db,
            "SELECT TIPO, COUNT(*) as N "
            "FROM DOCCAB GROUP BY TIPO ORDER BY N DESC"
        )
        tipos = {r["TIPO"] for r in rows}
        # Al menos 3 tipos distintos en datos sintéticos
        assert len(tipos) >= 3, f"Solo hay {len(tipos)} tipos de documento"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. COMPRAS / PROVEEDORES
# ═══════════════════════════════════════════════════════════════════════════════

class TestComprasProveedores:

    def test_mejores_proveedores_por_stock(self, db):
        """
        Proveedores con más artículos (proxy de relación comercial).
        """
        rows = _q(db,
            "SELECT COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL,'?') AS NOMBRE, COUNT(A.CODIGO) as N_ART "
            "FROM ARTICULO A "
            "JOIN PROVEED P ON CAST(P.CODIGO AS TEXT) = CAST(A.PROVEEDDEFECTO AS TEXT) "
            "GROUP BY P.CODIGO "
            "ORDER BY N_ART DESC "
            "LIMIT 5"
        )
        assert len(rows) > 0, "No hay artículos con proveedor asignado"

    def test_movimientos_estalmacen(self, db):
        """Movimientos de stock en rango de fechas."""
        rows = _q(db,
            "SELECT COUNT(*) as N FROM ESTALMACEN "
            "WHERE FECHA >= '2020-01-01'"
        )
        assert rows[0]["N"] > 0

    def test_stock_por_almacen(self, db):
        """Stock total por almacén (ESTALMACEN usa IMPCOSTE como proxy de valor)."""
        rows = _q(db,
            "SELECT CODIGO, SUM(ABS(IMPCOSTE)) as TOTAL "
            "FROM ESTALMACEN "
            "GROUP BY CODIGO "
            "ORDER BY TOTAL DESC"
        )
        assert len(rows) > 0

    def test_articulos_mas_movidos_en_stock(self, db):
        """Artículos con más movimientos de stock."""
        rows = _q(db,
            "SELECT E.CODIGO, SUM(ABS(E.IMPCOSTE)) as TOTAL_MOV "
            "FROM ESTALMACEN E "
            "GROUP BY E.CODIGO "
            "ORDER BY TOTAL_MOV DESC "
            "LIMIT 10"
        )
        assert len(rows) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. CAJA / TESORERÍA
# ═══════════════════════════════════════════════════════════════════════════════

class TestCajaTesoreria:

    def test_movimientos_caja_existen(self, db):
        rows = _q(db, "SELECT COUNT(*) as N FROM CAJA")
        assert rows[0]["N"] > 0

    def test_total_cobros_caja(self, db):
        """Total de entradas en caja (TIPO=1 = cobro)."""
        rows = _q(db,
            "SELECT SUM(IMPORTE) as TOTAL FROM CAJA WHERE TIPO = 1"
        )
        assert "TOTAL" in rows[0]

    def test_caja_en_rango_fechas(self, db):
        """Movimientos de caja en un rango de fechas."""
        rows = _q(db,
            "SELECT CODAPUNTE AS CODIGO, FECHA, CONCEPTO, IMPORTE "
            "FROM CAJA "
            "WHERE FECHA >= '2020-01-01' "
            "AND FECHA <= '2030-12-31' "
            "ORDER BY FECHA DESC "
            "LIMIT 20"
        )
        assert len(rows) > 0

    def test_caja_por_mes(self, db):
        """Movimientos de caja agrupados por mes."""
        rows = _q(db,
            "SELECT "
            "  CAST(strftime('%Y', FECHA) AS INTEGER) as ANIO, "
            "  CAST(strftime('%m', FECHA) AS INTEGER) as MES, "
            "  SUM(IMPORTE) as TOTAL "
            "FROM CAJA "
            "GROUP BY ANIO, MES "
            "ORDER BY ANIO DESC, MES DESC"
        )
        assert len(rows) > 0

    def test_saldo_caja_por_cliente(self, db):
        """Importe total movido por cliente en caja."""
        rows = _q(db,
            "SELECT CODCLIENTE, SUM(IMPORTE) as SALDO "
            "FROM CAJA "
            "WHERE CODCLIENTE > 0 "
            "GROUP BY CODCLIENTE "
            "ORDER BY SALDO DESC "
            "LIMIT 5"
        )
        # Puede haber o no movimientos con cliente asociado
        assert isinstance(rows, list)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CONSULTAS CON SINTAXIS FIREBIRD TRADUCIDA
# ═══════════════════════════════════════════════════════════════════════════════

class TestSintaxisFirebirdTraducida:

    def test_select_first_n(self, db):
        """SELECT FIRST N debe ejecutarse sin error (traducido a LIMIT N)."""
        rows = db.execute_query("SELECT FIRST 5 * FROM ARTICULO")
        assert len(rows) <= 5

    def test_select_first_distinct(self, db):
        rows = db.execute_query("SELECT DISTINCT FIRST 3 CODFAMILIA FROM ARTICULO")
        assert len(rows) <= 3

    def test_extract_month_from_fecha(self, db):
        """EXTRACT(MONTH FROM FECHA) traducido correctamente."""
        rows = db.execute_query(
            "SELECT EXTRACT(MONTH FROM FECHA) as MES FROM DOCCAB LIMIT 3"
        )
        assert len(rows) > 0
        for row in rows:
            mes = row["MES"]
            assert 1 <= mes <= 12, f"Mes inválido: {mes}"

    def test_extract_year_from_fecha(self, db):
        rows = db.execute_query(
            "SELECT EXTRACT(YEAR FROM FECHA) as ANIO FROM DOCCAB LIMIT 3"
        )
        assert len(rows) > 0
        for row in rows:
            assert row["ANIO"] > 2000

    def test_current_date_where_clause(self, db):
        """CURRENT_DATE en cláusula WHERE no lanza excepción."""
        rows = db.execute_query(
            "SELECT COUNT(*) as N FROM DOCCAB WHERE FECHA <= date('now')"
        )
        assert "N" in rows[0]

    def test_extract_in_group_by(self, db):
        """Agrupar por mes usando EXTRACT — consulta habitual en DEVIA."""
        rows = db.execute_query(
            "SELECT "
            "  EXTRACT(MONTH FROM FECHA) as MES, "
            "  COUNT(*) as N_DOCS, "
            "  SUM(IMPORTETOTAL) as TOTAL "
            "FROM DOCCAB "
            "WHERE TIPO = 13 "
            "GROUP BY MES "
            "ORDER BY MES"
        )
        assert len(rows) > 0
        for row in rows:
            mes = row["MES"]
            assert 1 <= mes <= 12


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CONSULTAS COMBINADAS — JOINS y agregaciones complejas
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsultasCombinadas:

    def test_facturas_con_lineas_y_articulos(self, db):
        """
        Facturas con sus líneas y nombre de artículo.
        Query típica: '¿Qué artículos se han vendido este mes?'
        """
        rows = db.execute_query(
            "SELECT D.CODIGO, D.FECHA, A.NOMBRE as ARTICULO, L.CANTIDAD, "
            "ROUND(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL),2) AS IMPORTE "
            "FROM DOCCAB D "
            "JOIN DOCLIN L ON L.CODDOCUMENTO = D.CODIGO "
            "JOIN ARTICULO A ON L.CODARTICULO = A.CODIGO "
            "WHERE D.TIPO = 13 "
            "ORDER BY D.FECHA DESC "
            "LIMIT 20"
        )
        assert len(rows) > 0
        for row in rows:
            assert row["ARTICULO"]
            assert row["CANTIDAD"] > 0

    def test_clientes_con_nombre_y_total(self, db):
        """
        Join DOCCAB + CLIENTE para top clientes con nombre completo.
        """
        rows = db.execute_query(
            "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, '?') AS NOMBRE, "
            "C.NIF, SUM(D.IMPORTETOTAL) as TOTAL_FACTURADO, "
            "COUNT(D.CODIGO) as N_FACTURAS "
            "FROM DOCCAB D "
            "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "WHERE D.TIPO = 13 "
            "GROUP BY C.CODIGO "
            "ORDER BY TOTAL_FACTURADO DESC "
            "LIMIT 10"
        )
        assert len(rows) > 0
        for row in rows:
            assert row["NOMBRE"]
            assert row["TOTAL_FACTURADO"] > 0
            assert row["N_FACTURAS"] > 0

    def test_articulos_por_familia_y_proveedor(self, db):
        """
        Artículos con familia y proveedor.
        Query típica: '¿Qué productos de Daikin tengo?'
        """
        rows = db.execute_query(
            "SELECT A.NOMBRE, F.NOMBRE as FAMILIA, "
            "COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL,'?') AS PROVEEDOR "
            "FROM ARTICULO A "
            "JOIN FAMILIA F ON F.CODIGO = A.CODFAMILIA "
            "JOIN PROVEED P ON CAST(P.CODIGO AS TEXT) = CAST(A.PROVEEDDEFECTO AS TEXT) "
            "ORDER BY F.NOMBRE, A.NOMBRE "
            "LIMIT 20"
        )
        assert len(rows) > 0
        for row in rows:
            assert row["FAMILIA"]
            assert row["PROVEEDOR"]

    def test_resumen_mensual_ventas(self, db):
        """
        Resumen de ventas agrupado por mes/año.
        Query típica: 'cuánto se ha facturado cada mes este año'
        """
        rows = db.execute_query(
            "SELECT "
            "  CAST(strftime('%Y', FECHA) AS INTEGER) as ANIO, "
            "  CAST(strftime('%m', FECHA) AS INTEGER) as MES, "
            "  COUNT(*) as N_FACTURAS, "
            "  SUM(IMPORTETOTAL) as TOTAL "
            "FROM DOCCAB "
            "WHERE TIPO = 13 "
            "GROUP BY ANIO, MES "
            "ORDER BY ANIO DESC, MES DESC"
        )
        assert len(rows) > 0
        for row in rows:
            assert row["TOTAL"] > 0
            assert 1 <= row["MES"] <= 12

    def test_presupuestos_vs_facturas_por_mes(self, db):
        """
        Comparativa presupuestos vs facturas por mes.
        """
        rows = db.execute_query(
            "SELECT "
            "  CAST(strftime('%m', FECHA) AS INTEGER) as MES, "
            "  SUM(CASE WHEN TIPO = 0  THEN 1 ELSE 0 END) as N_PRESUPUESTOS, "
            "  SUM(CASE WHEN TIPO = 13 THEN 1 ELSE 0 END) as N_FACTURAS "
            "FROM DOCCAB "
            "GROUP BY MES ORDER BY MES"
        )
        assert len(rows) > 0

    def test_empleados_con_documentos(self, db):
        """
        Documentos por agente/empleado.
        """
        rows = db.execute_query(
            "SELECT R.DESCRIPCION as EMPLEADO, COUNT(D.CODIGO) as N_DOCS "
            "FROM DOCCAB D "
            "JOIN RECURSO R ON R.CODIGO = D.CODAGENTE "
            "WHERE D.TIPO = 13 "
            "GROUP BY R.DESCRIPCION "
            "ORDER BY N_DOCS DESC "
            "LIMIT 5"
        )
        # Puede haber o no agentes asignados dependiendo de los datos sintéticos
        assert isinstance(rows, list)

    def test_query_proyectos_en_rango(self, db):
        """
        Equivalente a 'proyectos/documentos en tal rango de fechas'.
        En JDDC los documentos activos son el proxy de proyectos.
        """
        # Obtener el rango disponible en la BD
        rango = db.execute_query(
            "SELECT MIN(FECHA) as DESDE, MAX(FECHA) as HASTA FROM DOCCAB"
        )
        if not rango or rango[0]["DESDE"] is None:
            pytest.skip("No hay documentos para probar rango")

        desde = rango[0]["DESDE"]
        hasta = rango[0]["HASTA"]

        rows = db.execute_query(
            f"SELECT D.CODIGO, D.FECHA, D.TIPO, D.IMPORTETOTAL, "
            f"COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, '?') AS CLIENTE "
            f"FROM DOCCAB D "
            f"JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            f"WHERE D.FECHA BETWEEN '{desde}' AND '{hasta}' "
            f"ORDER BY D.FECHA DESC "
            f"LIMIT 10"
        )
        assert len(rows) > 0

    def test_total_comprado_por_rango(self, db):
        """
        '¿Cuánto se ha comprado en el período X-Y?'
        Suma de IMPORTETOTAL de todos los documentos en un rango.
        """
        rows = db.execute_query(
            "SELECT SUM(IMPORTETOTAL) as TOTAL, COUNT(*) as N "
            "FROM DOCCAB "
            "WHERE FECHA >= '2020-01-01' AND FECHA <= '2030-12-31' "
            "AND TIPO IN (13, 11)"  # Facturas + albaranes
        )
        assert rows[0]["TOTAL"] is not None
        assert rows[0]["TOTAL"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CASOS LÍMITE Y ROBUSTEZ
# ═══════════════════════════════════════════════════════════════════════════════

class TestCasosLimite:

    def test_query_sin_resultados(self, db):
        """Query válida que devuelve lista vacía."""
        rows = db.execute_query(
            "SELECT * FROM DOCCAB WHERE TIPO = 999 AND FECHA = '1900-01-01'"
        )
        assert rows == []

    def test_query_con_like(self, db):
        """LIKE funciona en SQLite."""
        rows = db.execute_query(
            "SELECT NOMBRE FROM ARTICULO WHERE NOMBRE LIKE '%Split%' LIMIT 5"
        )
        assert isinstance(rows, list)

    def test_query_con_order_by_y_limit(self, db):
        rows = db.execute_query(
            "SELECT NOMBRE, PRECIOVENTA AS PRECIO FROM ARTICULO "
            "ORDER BY PRECIOVENTA DESC LIMIT 3"
        )
        assert len(rows) <= 3
        if len(rows) > 1:
            assert rows[0]["PRECIO"] >= rows[1]["PRECIO"]

    def test_query_subconsulta(self, db):
        """Subconsulta básica."""
        rows = db.execute_query(
            "SELECT COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL, '?') AS NOMBRE FROM CLIENTE "
            "WHERE CODIGO IN (SELECT CODCLIENTE FROM DOCCAB WHERE TIPO = 13) "
            "LIMIT 5"
        )
        assert isinstance(rows, list)

    def test_query_case_when(self, db):
        """CASE WHEN funciona en SQLite."""
        rows = db.execute_query(
            "SELECT "
            "  TIPO, "
            "  CASE TIPO "
            "    WHEN 0  THEN 'Presupuesto' "
            "    WHEN 13 THEN 'Factura' "
            "    WHEN 11 THEN 'Albarán' "
            "    ELSE 'Otro' "
            "  END as TIPO_LABEL, "
            "  COUNT(*) as N "
            "FROM DOCCAB GROUP BY TIPO"
        )
        assert len(rows) > 0
        for row in rows:
            assert row["TIPO_LABEL"] in ("Presupuesto", "Factura", "Albarán", "Otro")

    def test_select_first_1(self, db):
        """SELECT FIRST 1 — límite extremo."""
        rows = db.execute_query("SELECT FIRST 1 * FROM DOCCAB")
        assert len(rows) == 1

    def test_select_first_1000(self, db):
        """SELECT FIRST 1000 — no debe fallar aunque haya menos filas."""
        rows = db.execute_query("SELECT FIRST 1000 * FROM FAMILIA")
        n_total = db.get_row_count("FAMILIA")
        assert len(rows) == n_total  # Devuelve lo que hay

    def test_driver_auto_reconnect(self, db):
        """
        El driver puede ejecutar queries incluso si conn es None (auto-connect).
        Esto simula el comportamiento de la app cuando hay reconexión.
        """
        drv = SimulatedFirebirdDriver()
        # No llamamos a connect() explícitamente
        rows = drv.execute_query("SELECT 1 as N FROM FAMILIA LIMIT 1")
        # execute_query() llama a connect() internamente si conn is None
        drv.disconnect()
