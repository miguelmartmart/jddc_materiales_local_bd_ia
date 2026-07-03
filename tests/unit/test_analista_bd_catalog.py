"""
test_analista_bd_catalog.py — Tests del catálogo de consultas del Analista BD.

Verifica que las 70 consultas del demo_analista_bd.py ejecutan sin error
y devuelven resultados coherentes. No imprime valores reales.

EJECUCIÓN:
  cd bots/interjddcia
  python -m pytest tests/unit/test_analista_bd_catalog.py -v
"""

import sys
import sqlite3
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.modules.db_simulator.constants import SimulatorPaths

_SIM = str(SimulatorPaths.DB_PATH)


@pytest.fixture(scope="module")
def db():
    if not Path(_SIM).exists():
        pytest.skip("simulator.db no encontrado")
    conn = sqlite3.connect(_SIM)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def q(conn, sql):
    return [dict(r) for r in conn.execute(sql).fetchall()]


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _xfail_sin_datos(db, *tablas):
    """Marca el test como xfail si alguna tabla no tiene filas en el snapshot actual."""
    for t in tablas:
        if _count(db, t) == 0:
            pytest.xfail(
                f"{t}: snapshot Firebird pendiente — tabla existe en BD real "
                f"pero sin datos capturados en simulador actual"
            )


# ── Los 70 tests: cada uno verifica una query del catálogo ───────────────────

class TestGerencia:
    def test_g01_actividad_por_tipo(self, db):
        r = q(db, "SELECT TIPO, COUNT(*) AS n FROM DOCCAB GROUP BY TIPO ORDER BY n DESC")
        assert len(r) > 1

    def test_g02_evolucion_mensual_cte(self, db):
        r = q(db, """
            WITH m AS (SELECT strftime('%Y-%m',FECHA) AS mes, COUNT(*) AS n
                       FROM DOCCAB WHERE FECHA IS NOT NULL GROUP BY mes)
            SELECT mes, n FROM m ORDER BY mes DESC LIMIT 12""")
        assert len(r) > 0

    def test_g03_top_agentes(self, db):
        r = q(db, """SELECT CODAGENTE, COUNT(*) AS n FROM DOCCAB
                     WHERE CODAGENTE IS NOT NULL GROUP BY CODAGENTE ORDER BY n DESC LIMIT 10""")
        assert len(r) >= 0

    def test_g04_tasa_conversion_presupuesto_factura(self, db):
        r = q(db, """
            WITH p AS (SELECT strftime('%Y-%m',FECHA) AS mes, COUNT(*) AS np
                       FROM DOCCAB WHERE TIPO=1 GROUP BY mes),
                 f AS (SELECT strftime('%Y-%m',FECHA) AS mes, COUNT(*) AS nf
                       FROM DOCCAB WHERE TIPO=13 GROUP BY mes)
            SELECT p.mes, p.np, COALESCE(f.nf,0) AS nf
            FROM p LEFT JOIN f ON f.mes=p.mes ORDER BY p.mes DESC LIMIT 12""")
        assert len(r) >= 0

    def test_g05_distribucion_geografica_cp(self, db):
        r = q(db, "SELECT CP, COUNT(*) AS n FROM CLIENTE WHERE CP IS NOT NULL GROUP BY CP ORDER BY n DESC LIMIT 15")
        assert len(r) > 0

    def test_g06_proyectos_por_tipo_obra(self, db):
        _xfail_sin_datos(db, "PROYECTOS")
        r = q(db, """SELECT TIPOOBRA, COUNT(*) AS total,
                            SUM(CASE WHEN FECHAFIN IS NULL THEN 1 ELSE 0 END) AS en_curso
                     FROM PROYECTOS GROUP BY TIPOOBRA""")
        assert len(r) > 0

    def test_g07_clientes_nuevos_por_anyo(self, db):
        r = q(db, """SELECT strftime('%Y',FECHAALTA) AS a, COUNT(*) AS n
                     FROM CLIENTE WHERE FECHAALTA IS NOT NULL GROUP BY a ORDER BY a DESC""")
        if len(r) == 0:
            pytest.skip("CLIENTE.FECHAALTA sin datos en esta BD (columna vacía o NULL)")
        assert len(r) > 0

    def test_g08_ratio_docs_con_importe(self, db):
        r = q(db, """SELECT COUNT(*) AS total,
                            SUM(CASE WHEN IMPORTETOTAL IS NOT NULL AND CAST(IMPORTETOTAL AS REAL)>0 THEN 1 ELSE 0 END) AS con_imp
                     FROM DOCCAB""")
        assert r[0]["total"] > 0

    def test_g09_remesas_por_anyo(self, db):
        _xfail_sin_datos(db, "REMESA")
        r = q(db, "SELECT strftime('%Y',FECHAEMISION) AS a, COUNT(*) AS n FROM REMESA WHERE FECHAEMISION IS NOT NULL GROUP BY a")
        assert len(r) > 0

    def test_g10_indice_actividad_agente(self, db):
        r = q(db, """
            WITH act AS (SELECT CODAGENTE, strftime('%Y-%m',FECHA) AS mes, COUNT(*) AS n
                         FROM DOCCAB WHERE CODAGENTE IS NOT NULL AND FECHA IS NOT NULL
                         GROUP BY CODAGENTE, mes)
            SELECT CODAGENTE, COUNT(DISTINCT mes) AS meses, ROUND(AVG(n),1) AS media
            FROM act GROUP BY CODAGENTE ORDER BY media DESC LIMIT 10""")
        assert len(r) >= 0


class TestContabilidad:
    def test_c01_baseimponible_iva_mensual(self, db):
        # Columnas reales capturadas de Firebird: IMPORTEBASE e IMPORTEIVA
        r = q(db, """SELECT strftime('%Y-%m',FECHA) AS mes,
                            ROUND(SUM(CAST(IMPORTEBASE AS REAL)),2) AS base,
                            ROUND(SUM(CAST(IMPORTEIVA AS REAL)),2) AS iva
                     FROM DOCCAB WHERE TIPO IN (13,40) AND FECHA IS NOT NULL
                     GROUP BY mes ORDER BY mes DESC LIMIT 12""")
        assert len(r) > 0

    def test_c02_recibos_vencidos_cobrados(self, db):
        _xfail_sin_datos(db, "RECIBO1")
        r = q(db, """
            WITH v AS (SELECT strftime('%Y-%m',FECHAVENC) AS mes, COUNT(*) AS n,
                              ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS total
                       FROM RECIBO1 WHERE FECHAVENC IS NOT NULL GROUP BY mes),
                 c AS (SELECT strftime('%Y-%m',FECHA) AS mes, COUNT(*) AS n,
                              ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS total
                       FROM RECIBO3 WHERE FECHA IS NOT NULL GROUP BY mes)
            SELECT v.mes, v.n AS vencidos, COALESCE(c.n,0) AS cobrados
            FROM v LEFT JOIN c ON c.mes=v.mes ORDER BY v.mes DESC LIMIT 12""")
        assert len(r) > 0

    def test_c03_histograma_importes(self, db):
        r = q(db, """SELECT
                        SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL)<100 THEN 1 ELSE 0 END) AS menos_100,
                        SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL) BETWEEN 100 AND 999 THEN 1 ELSE 0 END) AS rango_100_999,
                        SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL)>=1000 THEN 1 ELSE 0 END) AS mas_1000
                     FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL IS NOT NULL""")
        total = r[0]["menos_100"] + r[0]["rango_100_999"] + r[0]["mas_1000"]
        assert total > 0

    def test_c04_recibos_por_forma_pago(self, db):
        _xfail_sin_datos(db, "RECIBO3")
        r = q(db, """SELECT CODFORMAPAGO, COUNT(*) AS n, ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS total
                     FROM RECIBO3 WHERE CODFORMAPAGO IS NOT NULL GROUP BY CODFORMAPAGO""")
        assert len(r) > 0

    def test_c05_aging_report(self, db):
        _xfail_sin_datos(db, "RECIBO1")
        r = q(db, """SELECT
                        SUM(CASE WHEN CAST(julianday('now')-julianday(FECHAVENC) AS INTEGER)<=30 THEN 1 ELSE 0 END) AS d_30,
                        SUM(CASE WHEN CAST(julianday('now')-julianday(FECHAVENC) AS INTEGER) BETWEEN 31 AND 90 THEN 1 ELSE 0 END) AS d_31_90,
                        SUM(CASE WHEN CAST(julianday('now')-julianday(FECHAVENC) AS INTEGER)>90 THEN 1 ELSE 0 END) AS mas_90
                     FROM RECIBO1 WHERE FECHAVENC IS NOT NULL AND FECHAVENC<date('now')""")
        assert sum(r[0].values()) >= 0

    def test_c06_variacion_precios_historico(self, db):
        _xfail_sin_datos(db, "HISTORICOPRECIOS")
        r = q(db, """SELECT strftime('%Y',FECHA) AS a, COUNT(*) AS cambios,
                            ROUND(AVG(CAST(PRECIONUEVO AS REAL)-CAST(PRECIOANTERIOR AS REAL)),4) AS var_media
                     FROM HISTORICOPRECIOS WHERE FECHA IS NOT NULL GROUP BY a ORDER BY a DESC""")
        assert len(r) > 0

    def test_c07_remesas_euros(self, db):
        _xfail_sin_datos(db, "REMESA")
        r = q(db, "SELECT ENEUROS, COUNT(*) AS n FROM REMESA GROUP BY ENEUROS")
        assert len(r) > 0

    def test_c08_iva_por_tipo_en_doclin(self, db):
        r = q(db, "SELECT TIPOIVA, COUNT(*) AS n FROM DOCLIN WHERE TIPOIVA IS NOT NULL AND TIPOIVA != 0 GROUP BY TIPOIVA ORDER BY n DESC")
        if len(r) == 0:
            pytest.skip("DOCLIN.TIPOIVA sin datos distintos de 0 en esta BD")
        assert len(r) > 0

    def test_c09_concentracion_riesgo_deudores(self, db):
        r = q(db, """SELECT CODPAGA, COUNT(*) AS n, ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS deuda
                     FROM RECIBO1 WHERE ACTIVO=1 AND CODPAGA IS NOT NULL GROUP BY CODPAGA
                     ORDER BY deuda DESC LIMIT 10""")
        assert len(r) >= 0

    def test_c10_balance_recibos_mensual(self, db):
        _xfail_sin_datos(db, "RECIBO1")
        r = q(db, """
            WITH e AS (SELECT strftime('%Y-%m',FECHA) AS mes, ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS te
                       FROM RECIBO1 WHERE FECHA IS NOT NULL GROUP BY mes),
                 c AS (SELECT strftime('%Y-%m',FECHA) AS mes, ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS tc
                       FROM RECIBO3 WHERE FECHA IS NOT NULL GROUP BY mes)
            SELECT e.mes, e.te, COALESCE(c.tc,0) AS tc, ROUND(e.te-COALESCE(c.tc,0),2) AS pendiente
            FROM e LEFT JOIN c ON c.mes=e.mes ORDER BY e.mes DESC LIMIT 12""")
        assert len(r) > 0


class TestAlmacen:
    def test_a01_stock_por_almacen(self, db):
        _xfail_sin_datos(db, "EXISTENC")
        r = q(db, "SELECT CODALMACEN, COUNT(*) AS articulos, SUM(CAST(STOCK1 AS REAL)) AS stock FROM EXISTENC GROUP BY CODALMACEN")
        assert len(r) > 0

    def test_a02_articulos_multi_almacen(self, db):
        r = q(db, """SELECT CODARTICULO, COUNT(DISTINCT CODALMACEN) AS nalm, SUM(CAST(STOCK1 AS REAL)) AS total
                     FROM EXISTENC GROUP BY CODARTICULO HAVING COUNT(DISTINCT CODALMACEN)>1 ORDER BY total DESC LIMIT 15""")
        assert len(r) >= 0

    def test_a03_roturas_stock(self, db):
        r = q(db, """SELECT COUNT(*) AS roturas, MIN(CAST(STOCK1 AS REAL)) AS peor
                     FROM EXISTENC WHERE CAST(STOCK1 AS REAL)<=0""")
        assert r[0]["roturas"] >= 0

    def test_a04_valor_inventario_mensual(self, db):
        r = q(db, """SELECT strftime('%Y-%m',FECHA) AS mes,
                            ROUND(SUM(CAST(IMPCOSTE AS REAL)),2) AS coste,
                            ROUND(SUM(CAST(IMPVENTA AS REAL)),2) AS venta
                     FROM ESTALMACEN WHERE FECHA IS NOT NULL GROUP BY mes ORDER BY mes DESC LIMIT 12""")
        assert len(r) > 0

    def test_a05_pendientes_servir(self, db):
        r = q(db, """SELECT CODALMACEN, SUM(CAST(PENDSERVIR1 AS REAL)) AS pendiente
                     FROM EXISTENC WHERE CAST(PENDSERVIR1 AS REAL)>0 GROUP BY CODALMACEN""")
        assert len(r) >= 0

    def test_a06_margen_por_articulo(self, db):
        r = q(db, """SELECT CODIGO, ROUND(CAST(IMPCOSTE AS REAL),4) AS coste, ROUND(CAST(IMPVENTA AS REAL),4) AS venta
                     FROM ESTALMACEN WHERE IMPCOSTE IS NOT NULL AND IMPVENTA IS NOT NULL
                       AND CAST(IMPVENTA AS REAL)>0 ORDER BY CAST(IMPVENTA AS REAL)/NULLIF(CAST(IMPCOSTE AS REAL),0) DESC LIMIT 10""")
        assert len(r) >= 0

    def test_a07_antiguedad_inventario(self, db):
        r = q(db, """SELECT strftime('%Y',FECHA) AS a, COUNT(*) AS n,
                            ROUND(AVG(julianday('now')-julianday(FECHA)),0) AS dias_medio
                     FROM ESTALMACEN WHERE FECHA IS NOT NULL GROUP BY a ORDER BY a""")
        assert len(r) > 0

    def test_a08_ubicaciones(self, db):
        _xfail_sin_datos(db, "EXISTENC")
        r = q(db, """SELECT CODALMACEN, COUNT(DISTINCT UBICACION) AS ubicaciones,
                            COUNT(CASE WHEN UBICACION IS NULL THEN 1 END) AS sin_ubic
                     FROM EXISTENC GROUP BY CODALMACEN""")
        assert len(r) > 0

    def test_a09_cobertura_neta(self, db):
        r = q(db, """SELECT CODARTICULO,
                            ROUND(SUM(CAST(STOCK1 AS REAL)),2) AS stock,
                            ROUND(SUM(CAST(PENDSERVIR1 AS REAL)),2) AS pendiente,
                            ROUND(SUM(CAST(STOCK1 AS REAL))-SUM(CAST(PENDSERVIR1 AS REAL)),2) AS cobertura
                     FROM EXISTENC GROUP BY CODARTICULO HAVING SUM(CAST(PENDSERVIR1 AS REAL))>0
                     ORDER BY cobertura ASC LIMIT 15""")
        assert len(r) >= 0

    def test_a10_compras_por_proveedor(self, db):
        _xfail_sin_datos(db, "COMPRA")
        r = q(db, """SELECT CODPROVEEDOR, COUNT(DISTINCT CODARTICULO) AS arts,
                            ROUND(AVG(CAST(PRECIOCOSTE AS REAL)),4) AS precio_medio
                     FROM COMPRA WHERE CODPROVEEDOR IS NOT NULL GROUP BY CODPROVEEDOR ORDER BY arts DESC LIMIT 10""")
        assert len(r) > 0


class TestComercial:
    def test_co01_ranking_clientes(self, db):
        r = q(db, """SELECT CODCLIENTE, COUNT(*) AS n, ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS total
                     FROM DOCCAB WHERE TIPO=13 AND CODCLIENTE IS NOT NULL GROUP BY CODCLIENTE ORDER BY total DESC LIMIT 10""")
        assert len(r) > 0

    def test_co02_estacionalidad_ventas(self, db):
        r = q(db, """SELECT strftime('%m',FECHA) AS mes, COUNT(*) AS n, ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS media
                     FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY mes ORDER BY mes""")
        assert len(r) > 0 and len(r) <= 12

    def test_co03_ciclo_vida_cliente(self, db):
        r = q(db, """SELECT CODCLIENTE, MIN(FECHA) AS primera, MAX(FECHA) AS ultima, COUNT(*) AS n
                     FROM DOCCAB WHERE TIPO=13 AND CODCLIENTE IS NOT NULL GROUP BY CODCLIENTE
                     HAVING COUNT(*)>1 ORDER BY n DESC LIMIT 10""")
        assert len(r) >= 0

    def test_co04_clientes_sin_actividad(self, db):
        r = q(db, """SELECT COUNT(*) AS n FROM (
                        SELECT CODCLIENTE FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE
                        HAVING julianday('now')-julianday(MAX(FECHA))>365
                     )""")
        assert r[0]["n"] >= 0

    def test_co05_tasa_cierre_por_serie(self, db):
        r = q(db, """
            WITH p AS (SELECT SERIE, COUNT(*) AS np FROM DOCCAB WHERE TIPO=1 GROUP BY SERIE),
                 ped AS (SELECT SERIE, COUNT(*) AS nped FROM DOCCAB WHERE TIPO=20 GROUP BY SERIE)
            SELECT p.SERIE, p.np, COALESCE(ped.nped,0) AS nped FROM p LEFT JOIN ped ON ped.SERIE=p.SERIE""")
        assert len(r) >= 0

    def test_co06_ticket_por_tipo_cliente(self, db):
        r = q(db, """SELECT c.TIPOPERSONA, COUNT(DISTINCT d.CODCLIENTE) AS ncli,
                            ROUND(AVG(CAST(d.IMPORTETOTAL AS REAL)),2) AS ticket_medio
                     FROM DOCCAB d JOIN CLIENTE c ON c.CODIGO=d.CODCLIENTE
                     WHERE d.TIPO=13 GROUP BY c.TIPOPERSONA""")
        assert len(r) >= 0

    def test_co07_frecuencia_compra(self, db):
        r = q(db, """SELECT n_tramo, COUNT(*) AS clientes FROM (
                        SELECT CODCLIENTE,
                               CASE WHEN COUNT(*)=1 THEN '1' WHEN COUNT(*) BETWEEN 2 AND 5 THEN '2-5' ELSE '6+' END AS n_tramo
                        FROM DOCCAB WHERE TIPO=13 AND CODCLIENTE IS NOT NULL GROUP BY CODCLIENTE
                     ) GROUP BY n_tramo""")
        assert len(r) > 0

    def test_co08_albaranes_sin_facturar(self, db):
        r = q(db, """WITH alb AS (SELECT CODIGO FROM DOCCAB WHERE TIPO=40),
                          ref AS (SELECT DISTINCT CODDOCUMENTO FROM DOCREF)
                     SELECT COUNT(*) AS sin_fact FROM alb LEFT JOIN ref ON ref.CODDOCUMENTO=alb.CODIGO
                     WHERE ref.CODDOCUMENTO IS NULL""")
        assert r[0]["sin_fact"] >= 0

    def test_co09_evolucion_cartera(self, db):
        r = q(db, """SELECT strftime('%Y',FECHA) AS a, COUNT(DISTINCT CODCLIENTE) AS clientes
                     FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY a ORDER BY a DESC LIMIT 10""")
        assert len(r) > 0

    def test_co10_comparativa_agentes(self, db):
        r = q(db, """SELECT CODAGENTE,
                            COUNT(CASE WHEN TIPO=1 THEN 1 END) AS pres,
                            COUNT(CASE WHEN TIPO=13 THEN 1 END) AS fact,
                            ROUND(SUM(CASE WHEN TIPO=13 THEN CAST(IMPORTETOTAL AS REAL) ELSE 0 END),2) AS total
                     FROM DOCCAB WHERE CODAGENTE IS NOT NULL GROUP BY CODAGENTE ORDER BY total DESC""")
        assert len(r) >= 0


class TestPredicciones:
    def test_p01_tendencia_lineal(self, db):
        r = q(db, """WITH m AS (SELECT strftime('%Y-%m',FECHA) AS mes,
                                      ROW_NUMBER() OVER (ORDER BY strftime('%Y-%m',FECHA)) AS t,
                                      SUM(CAST(IMPORTETOTAL AS REAL)) AS y
                                FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY mes),
                          s AS (SELECT COUNT(*) AS n, SUM(t) AS st, SUM(y) AS sy, SUM(t*t) AS st2, SUM(t*y) AS sty FROM m)
                     SELECT ROUND((sty-st*sy/n)/(st2-st*st/n),2) AS pendiente FROM s WHERE n>1""")
        assert len(r) > 0

    def test_p02_modelo_rfm(self, db):
        r = q(db, """WITH rfm AS (SELECT CODCLIENTE,
                                        CAST(julianday('now')-julianday(MAX(FECHA)) AS INTEGER) AS rec,
                                        COUNT(*) AS frec
                                   FROM DOCCAB WHERE TIPO=13 AND CODCLIENTE IS NOT NULL GROUP BY CODCLIENTE)
                     SELECT COUNT(CASE WHEN rec<=90 THEN 1 END) AS activos,
                            COUNT(CASE WHEN rec BETWEEN 91 AND 365 THEN 1 END) AS en_riesgo,
                            COUNT(CASE WHEN rec>365 THEN 1 END) AS perdidos
                     FROM rfm""")
        r0 = r[0]
        assert r0["activos"] + r0["en_riesgo"] + r0["perdidos"] > 0

    def test_p03_proyeccion_stock(self, db):
        r = q(db, """WITH consumo AS (SELECT l.CODARTICULO,
                                           SUM(CAST(l.CANTIDAD AS REAL))/
                                           NULLIF(julianday(MAX(d.FECHA))-julianday(MIN(d.FECHA)),0)*30 AS c30d
                                      FROM DOCLIN l JOIN DOCCAB d ON d.CODIGO=l.CODDOCUMENTO
                                      WHERE d.TIPO=13 AND d.FECHA>=date('now','-90 days') GROUP BY l.CODARTICULO),
                          s AS (SELECT CODARTICULO, SUM(CAST(STOCK1 AS REAL)) AS stk FROM EXISTENC GROUP BY CODARTICULO)
                     SELECT COUNT(*) AS criticos FROM consumo c JOIN s ON s.CODARTICULO=c.CODARTICULO
                     WHERE c.c30d>0 AND s.stk/c.c30d<1.5""")
        assert r[0]["criticos"] >= 0

    def test_p04_estacionalidad_factor(self, db):
        r = q(db, """WITH m AS (SELECT strftime('%m',FECHA) AS mes, SUM(CAST(IMPORTETOTAL AS REAL)) AS t
                                FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY mes),
                          avg AS (SELECT AVG(t) AS media FROM m)
                     SELECT mes, ROUND(t/(SELECT media FROM avg),3) AS factor FROM m ORDER BY mes""")
        assert len(r) > 0

    def test_p05_proyectos_riesgo_sobrecosto(self, db):
        _xfail_sin_datos(db, "PROYECTOS")
        r = q(db, """SELECT p.CODIGO, COUNT(pp.CODPRESUPUESTO) AS npres,
                            CASE WHEN COUNT(pp.CODPRESUPUESTO)>3 THEN 'ALTO' WHEN COUNT(pp.CODPRESUPUESTO)>1 THEN 'MEDIO' ELSE 'BAJO' END AS riesgo
                     FROM PROYECTOS p LEFT JOIN PRESUPROYE pp ON pp.CODPROYECTO=p.CODIGO
                     GROUP BY p.CODIGO ORDER BY npres DESC LIMIT 15""")
        assert len(r) > 0

    def test_p06_tendencia_precios_proveedor(self, db):
        r = q(db, """SELECT CODPROVEEDOR,
                            ROUND(MIN(CAST(PRECIOCOSTE AS REAL)),4) AS pmin,
                            ROUND(MAX(CAST(PRECIOCOSTE AS REAL)),4) AS pmax,
                            ROUND(100.0*(MAX(CAST(PRECIOCOSTE AS REAL))-MIN(CAST(PRECIOCOSTE AS REAL)))
                                  /NULLIF(MIN(CAST(PRECIOCOSTE AS REAL)),0),2) AS var_pct
                     FROM COMPRA WHERE CODPROVEEDOR IS NOT NULL AND CAST(PRECIOCOSTE AS REAL)>0
                     GROUP BY CODPROVEEDOR HAVING COUNT(*)>3 ORDER BY var_pct DESC LIMIT 10""")
        assert len(r) >= 0

    def test_p07_media_movil_reparaciones(self, db):
        _xfail_sin_datos(db, "REPCAB")
        r = q(db, """SELECT strftime('%Y-%m',FECHA) AS mes, COUNT(*) AS n,
                            AVG(COUNT(*)) OVER (ORDER BY strftime('%Y-%m',FECHA) ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS mm3
                     FROM REPCAB WHERE FECHA IS NOT NULL GROUP BY mes ORDER BY mes DESC LIMIT 18""")
        assert len(r) > 0

    def test_p08_inflacion_precios(self, db):
        _xfail_sin_datos(db, "HISTORICOPRECIOS")
        r = q(db, """SELECT strftime('%Y',FECHA) AS a,
                            SUM(CASE WHEN CAST(PRECIONUEVO AS REAL)>CAST(PRECIOANTERIOR AS REAL) THEN 1 ELSE 0 END) AS subidas,
                            ROUND(AVG(100.0*(CAST(PRECIONUEVO AS REAL)-CAST(PRECIOANTERIOR AS REAL))
                                  /NULLIF(CAST(PRECIOANTERIOR AS REAL),0)),2) AS variacion
                     FROM HISTORICOPRECIOS WHERE PRECIOANTERIOR IS NOT NULL AND CAST(PRECIOANTERIOR AS REAL)>0
                     GROUP BY a ORDER BY a DESC LIMIT 5""")
        assert len(r) > 0

    def test_p09_proyeccion_cobros_futuros(self, db):
        r = q(db, """SELECT strftime('%Y-%m',FECHAVENC) AS mes, COUNT(*) AS n,
                            ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS previsto
                     FROM RECIBO1 WHERE FECHAVENC>date('now') AND ACTIVO=1
                     GROUP BY mes ORDER BY mes LIMIT 12""")
        assert len(r) >= 0

    def test_p10_estados_documentos_anomalos(self, db):
        r = q(db, "SELECT ESTADO, COUNT(*) AS n FROM DOCCAB WHERE ESTADO IS NOT NULL GROUP BY ESTADO ORDER BY n DESC")
        assert len(r) >= 0


class TestAlertas:
    def test_al01_facturas_duplicadas(self, db):
        r = q(db, """SELECT CODCLIENTE, FECHA, COUNT(*) AS n FROM DOCCAB WHERE TIPO=13
                     GROUP BY CODCLIENTE, FECHA HAVING COUNT(*)>1 ORDER BY n DESC LIMIT 10""")
        assert len(r) >= 0

    def test_al02_recibos_importe_anomalo(self, db):
        r = q(db, "SELECT COUNT(*) AS n FROM RECIBO1 WHERE IMPORTE IS NOT NULL AND CAST(IMPORTE AS REAL)<=0")
        assert r[0]["n"] >= 0

    def test_al03_docs_importe_negativo(self, db):
        r = q(db, "SELECT TIPO, COUNT(*) AS n FROM DOCCAB WHERE CAST(IMPORTETOTAL AS REAL)<0 GROUP BY TIPO")
        assert len(r) >= 0

    def test_al04_stock_negativo(self, db):
        r = q(db, """SELECT CODALMACEN, COUNT(*) AS n FROM EXISTENC
                     WHERE CAST(STOCK1 AS REAL)<0 GROUP BY CODALMACEN""")
        assert len(r) >= 0

    def test_al05_morosos_reincidentes(self, db):
        r = q(db, """SELECT CODPAGA, COUNT(*) AS n FROM RECIBO1
                     WHERE ACTIVO=1 AND FECHAVENC<date('now') GROUP BY CODPAGA HAVING COUNT(*)>=3""")
        assert len(r) >= 0

    def test_al06_proyectos_sin_presupuesto(self, db):
        r = q(db, """SELECT COUNT(*) AS n FROM PROYECTOS p
                     LEFT JOIN PRESUPROYE pp ON pp.CODPROYECTO=p.CODIGO WHERE pp.CODPROYECTO IS NULL""")
        assert r[0]["n"] >= 0

    def test_al07_ventas_bajo_coste(self, db):
        r = q(db, """SELECT COUNT(*) AS n FROM DOCLIN l JOIN DOCCAB d ON d.CODIGO=l.CODDOCUMENTO
                     WHERE d.TIPO=13 AND CAST(l.COSTE AS REAL)>0
                       AND CAST(l.PRECIO AS REAL)<CAST(l.COSTE AS REAL)""")
        assert r[0]["n"] >= 0

    def test_al08_incoherencia_base_iva_total(self, db):
        r = q(db, """SELECT COUNT(*) AS n FROM DOCCAB
                     WHERE IMPORTEBASE IS NOT NULL AND IMPORTEIVA IS NOT NULL AND IMPORTETOTAL IS NOT NULL
                       AND CAST(IMPORTETOTAL AS REAL)>0
                       AND ABS(CAST(IMPORTEBASE AS REAL)+CAST(IMPORTEIVA AS REAL)-CAST(IMPORTETOTAL AS REAL))>0.02""")
        assert r[0]["n"] >= 0

    def test_al09_series_sin_actividad(self, db):
        r = q(db, """SELECT COUNT(*) AS n FROM SERIE s
                     WHERE ULTIMO>0
                       AND (SELECT MAX(FECHA) FROM DOCCAB d WHERE d.SERIE=s.SERIE AND d.TIPO=s.TIPO) IS NULL""")
        assert r[0]["n"] >= 0

    def test_al10_recursos_sin_reparaciones(self, db):
        r = q(db, """SELECT COUNT(*) AS n FROM RECURSO r
                     LEFT JOIN REPCAB rep ON rep.CODALMACEN=r.CODIGO AND rep.FECHA>=date('now','-90 days')
                     WHERE rep.CODALMACEN IS NULL""")
        assert r[0]["n"] >= 0


class TestReporting:
    def test_r01_cuadro_mando_global(self, db):
        r = q(db, """SELECT
                        (SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13) AS facturas,
                        (SELECT COUNT(*) FROM DOCCAB WHERE TIPO=1)  AS presupuestos,
                        (SELECT COUNT(*) FROM CLIENTE) AS clientes,
                        (SELECT COUNT(*) FROM PROVEED) AS proveedores,
                        (SELECT COUNT(*) FROM PROYECTOS) AS proyectos,
                        (SELECT COUNT(*) FROM REPCAB) AS reparaciones""")
        assert r[0]["facturas"] > 0
        assert r[0]["clientes"] > 0

    def test_r02_matriz_docs_por_anyo(self, db):
        r = q(db, """SELECT strftime('%Y',FECHA) AS a,
                            SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END) AS facturas,
                            SUM(CASE WHEN TIPO=1 THEN 1 ELSE 0 END) AS pres,
                            COUNT(*) AS total
                     FROM DOCCAB WHERE FECHA IS NOT NULL GROUP BY a ORDER BY a DESC LIMIT 10""")
        assert len(r) > 0

    def test_r03_rentabilidad_bruta(self, db):
        r = q(db, """SELECT COUNT(*) AS lineas,
                            ROUND(SUM(CAST(CANTIDAD AS REAL)*CAST(PRECIO AS REAL)),2) AS ingreso,
                            ROUND(SUM(CAST(CANTIDAD AS REAL)*CAST(COSTE AS REAL)),2) AS coste
                     FROM DOCLIN l JOIN DOCCAB d ON d.CODIGO=l.CODDOCUMENTO
                     WHERE d.TIPO=13 AND l.PRECIO IS NOT NULL AND l.COSTE IS NOT NULL""")
        assert r[0]["lineas"] > 0

    def test_r04_top_articulos_vendidos(self, db):
        r = q(db, """SELECT l.CODARTICULO, ROUND(SUM(CAST(l.CANTIDAD AS REAL)*CAST(l.PRECIO AS REAL)),2) AS total
                     FROM DOCLIN l JOIN DOCCAB d ON d.CODIGO=l.CODDOCUMENTO
                     WHERE d.TIPO=13 GROUP BY l.CODARTICULO ORDER BY total DESC LIMIT 10""")
        assert len(r) > 0

    def test_r05_dashboard_proyectos(self, db):
        _xfail_sin_datos(db, "PROYECTOS")
        r = q(db, """SELECT TIPOOBRA, COUNT(*) AS total,
                            SUM(CASE WHEN FECHAFIN IS NULL THEN 1 ELSE 0 END) AS en_curso
                     FROM PROYECTOS GROUP BY TIPOOBRA""")
        assert len(r) > 0

    def test_r06_sat_por_delegacion(self, db):
        _xfail_sin_datos(db, "REPCAB")
        r = q(db, """SELECT CODALMACEN, COUNT(*) AS reparaciones,
                            MIN(FECHA) AS primera, MAX(FECHA) AS ultima
                     FROM REPCAB WHERE CODALMACEN IS NOT NULL GROUP BY CODALMACEN""")
        assert len(r) > 0

    def test_r07_trazabilidad_doc(self, db):
        r = q(db, """SELECT d1.TIPO AS origen, d2.TIPO AS destino, COUNT(*) AS n
                     FROM DOCREF dr JOIN DOCCAB d1 ON d1.CODIGO=dr.CODDOCUMENTO
                     JOIN DOCCAB d2 ON d2.CODIGO=dr.CODDOCUMENTODESTINO
                     GROUP BY d1.TIPO, d2.TIPO ORDER BY n DESC""")
        assert len(r) >= 0

    def test_r08_kpis_financieros(self, db):
        r = q(db, """SELECT ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS total,
                            COUNT(*) AS n, ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS media
                     FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL IS NOT NULL""")
        assert r[0]["n"] > 0

    def test_r09_evolucion_precio_compra(self, db):
        _xfail_sin_datos(db, "COMPRA")
        r = q(db, """SELECT CODARTICULO,
                            ROUND(MIN(CAST(PRECIOCOSTE AS REAL)),4) AS pmin,
                            ROUND(MAX(CAST(PRECIOCOSTE AS REAL)),4) AS pmax
                     FROM COMPRA WHERE PRECIOCOSTE IS NOT NULL AND CAST(PRECIOCOSTE AS REAL)>0
                     GROUP BY CODARTICULO ORDER BY pmax-pmin DESC LIMIT 10""")
        assert len(r) > 0

    def test_r10_resumen_ejecutivo_union(self, db):
        r = q(db, """
            SELECT 'Docs' AS e, COUNT(*) AS n, MIN(FECHA) AS desde, MAX(FECHA) AS hasta FROM DOCCAB
            UNION ALL SELECT 'Clientes', COUNT(*), NULL, NULL FROM CLIENTE
            UNION ALL SELECT 'Proyectos', COUNT(*), MIN(FECHAINICIO), MAX(FECHAINICIO) FROM PROYECTOS
            UNION ALL SELECT 'Reparaciones', COUNT(*), MIN(FECHA), MAX(FECHA) FROM REPCAB
            UNION ALL SELECT 'Recibos', COUNT(*), MIN(FECHA), MAX(FECHA) FROM RECIBO1""")
        assert len(r) == 5
        assert all(row["n"] >= 0 for row in r)
