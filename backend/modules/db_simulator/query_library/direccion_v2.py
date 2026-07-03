"""direccion_v2.py — 25 consultas adicionales de Dirección (v2).

DEVIA: fichero < 500 líneas, módulo independiente, sin lógica de negocio.
"""
from backend.modules.db_simulator.query_library.builder import q

QUERIES_DIRECCION_V2: list = [
    q("dv2_001", "Margen bruto por familia de artículo", "Margen por familia",
      "Diferencia media entre PRECIOVENTA de venta y PRECIOCOSTE por familia de artículo.",
      "SELECT F.NOMBRE AS FAMILIA, ROUND(AVG(A.PRECIOVENTA-A.PRECIOCOSTE),2) AS MARGEN_MEDIO, "
      "ROUND(AVG(CASE WHEN A.PRECIOVENTA>0 THEN (A.PRECIOVENTA-A.PRECIOCOSTE)/A.PRECIOVENTA*100 ELSE NULL END),1) AS PCT_MARGEN "
      "FROM ARTICULO A JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE A.PRECIOVENTA>0 AND A.PRECIOCOSTE>0 GROUP BY F.NOMBRE ORDER BY MARGEN_MEDIO DESC",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_002", "Clientes con primera factura por mes", "Nuevos clientes por mes",
      "Mes en que cada cliente emitió su primera factura, agrupado para ver captación mensual.",
      "SELECT SUBSTR(MIN(D.FECHA),1,7) AS MES_PRIMERA_FACTURA, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY MES_PRIMERA_FACTURA ORDER BY MES_PRIMERA_FACTURA DESC LIMIT 12",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_003", "Facturación total por departamento (tipo documento)", "Facturación por tipo",
      "Suma de IMPORTETOTAL agrupada por TIPO de documento para visión global.",
      "SELECT TIPO, COUNT(*) AS N_DOCS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB GROUP BY TIPO ORDER BY TOTAL DESC",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_004", "Concentración de ventas en top 5 clientes", "Concentración cartera clientes",
      "Porcentaje de la facturación total que representan los 5 clientes con más volumen.",
      "SELECT ROUND(100.0*SUM(TOP5.TOTAL)/(SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13),2) AS PCT_TOP5 "
      "FROM (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB WHERE TIPO=13 "
      "GROUP BY CODCLIENTE ORDER BY TOTAL DESC LIMIT 5) TOP5",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_005", "Evolución de presupuestos vs facturas por mes", "Conversión presupuesto a factura",
      "Compara el número de presupuestos TIPO=0 con facturas TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "SUM(CASE WHEN TIPO=0 THEN 1 ELSE 0 END) AS N_PRESUPUESTOS, "
      "SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END) AS N_FACTURAS "
      "FROM DOCCAB WHERE TIPO IN (0,13) AND FECHA IS NOT NULL "
      "GROUP BY MES ORDER BY MES DESC LIMIT 12",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_006", "Número de clientes activos (con factura en últimos 12 meses)", "Clientes activos",
      "Clientes que han generado al menos una factura TIPO=13 en los últimos 12 meses.",
      "SELECT COUNT(DISTINCT CODCLIENTE) AS CLIENTES_ACTIVOS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA >= DATE('now','-365 days')",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_007", "Número de clientes inactivos (sin factura en 12 meses)", "Clientes inactivos",
      "Clientes que tuvieron facturas pero no han generado ninguna en los últimos 12 meses.",
      "SELECT COUNT(DISTINCT CODCLIENTE) AS CLIENTES_INACTIVOS "
      "FROM DOCCAB WHERE TIPO=13 "
      "AND CODCLIENTE NOT IN (SELECT DISTINCT CODCLIENTE FROM DOCCAB "
      "WHERE TIPO=13 AND FECHA >= DATE('now','-365 days'))",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_008", "Facturación media mensual del año actual", "Media mensual facturación",
      "Divide la facturación total del año actual entre los meses transcurridos.",
      "SELECT ROUND(SUM(IMPORTETOTAL)/MAX(CAST(SUBSTR(FECHA,6,2) AS INT)),2) AS MEDIA_MENSUAL, "
      "SUM(IMPORTETOTAL) AS TOTAL_ANIO, MAX(CAST(SUBSTR(FECHA,6,2) AS INT)) AS MESES "
      "FROM DOCCAB WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4)",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_009", "Número de proveedores activos", "Proveedores con compras recientes",
      "Proveedores que han generado al menos un pedido en los últimos 12 meses.",
      "SELECT COUNT(DISTINCT CODCLIENTE) AS PROVEEDORES_ACTIVOS "
      "FROM DOCCAB WHERE TIPO IN (20,21) AND FECHA >= DATE('now','-365 days')",
      "NULL", "NULL", "KPI", "Medio", "", ""),

    q("dv2_010", "Ratio facturación SAT sobre facturación total", "Peso del SAT en facturación",
      "Porcentaje que representa la facturación de SATs sobre el total facturado.",
      "SELECT ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTETOTAL ELSE 0 END),2) AS TOTAL_SAT, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS TOTAL_VENTAS, "
      "ROUND(100.0*SUM(CASE WHEN TIPO=2 THEN IMPORTETOTAL ELSE 0 END)/"
      "NULLIF(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),0),2) AS PCT_SAT "
      "FROM DOCCAB WHERE TIPO IN (2,13)",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_011", "Top 10 artículos por importe total vendido", "Artículos más rentables",
      "Artículos con mayor importe total en líneas de facturas TIPO=13.",
      "SELECT L.CODARTICULO, A.NOMBRE, ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS TOTAL_VENDIDO "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY TOTAL_VENDIDO DESC LIMIT 10",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_012", "Número total de documentos por tipo", "Volumen documental por tipo",
      "Cuenta todos los documentos del sistema agrupados por TIPO.",
      "SELECT TIPO, COUNT(*) AS N_DOCUMENTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_IMPORTE "
      "FROM DOCCAB GROUP BY TIPO ORDER BY N_DOCUMENTOS DESC",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_013", "Crecimiento interanual de facturación", "Variación año a año",
      "Compara la facturación del año actual con el año anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) THEN IMPORTETOTAL ELSE 0 END),2) AS ANIO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INT)-1 AS TEXT) THEN IMPORTETOTAL ELSE 0 END),2) AS ANIO_ANTERIOR "
      "FROM DOCCAB WHERE TIPO=13",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_014", "Número de familias de artículos activas", "Familias con ventas",
      "Familias que tienen al menos un artículo vendido en facturas TIPO=13.",
      "SELECT COUNT(DISTINCT A.CODFAMILIA) AS FAMILIAS_ACTIVAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO WHERE D.TIPO=13",
      "NULL", "NULL", "KPI", "Medio", "", ""),

    q("dv2_015", "Facturación por agente y mes", "Rendimiento agentes por mes",
      "Facturación TIPO=13 desglosada por agente y mes para seguimiento de rendimiento.",
      "SELECT CODAGENTE, SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY CODAGENTE, MES ORDER BY MES DESC, TOTAL DESC LIMIT 30",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_016", "Clientes con mayor número de documentos", "Clientes más activos",
      "Clientes con más documentos de cualquier tipo registrados en el sistema.",
      "SELECT CODCLIENTE, COUNT(*) AS N_DOCUMENTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB GROUP BY CODCLIENTE ORDER BY N_DOCUMENTOS DESC LIMIT 20",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_017", "Valor total de presupuestos pendientes", "Pipeline comercial",
      "Suma de IMPORTETOTAL de presupuestos TIPO=0 que no tienen factura asociada.",
      "SELECT COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_PIPELINE "
      "FROM DOCCAB WHERE TIPO=0",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_018", "Número de artículos vendidos vs catálogo total", "Cobertura de catálogo",
      "Porcentaje de artículos del catálogo que han sido vendidos al menos una vez.",
      "SELECT (SELECT COUNT(*) FROM ARTICULO) AS TOTAL_CATALOGO, "
      "COUNT(DISTINCT L.CODARTICULO) AS ARTICULOS_VENDIDOS, "
      "ROUND(100.0*COUNT(DISTINCT L.CODARTICULO)/(SELECT COUNT(*) FROM ARTICULO),1) AS PCT_COBERTURA "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO WHERE D.TIPO=13",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_019", "Facturación por trimestre y año", "Estacionalidad trimestral",
      "Facturación TIPO=13 agrupada por año y trimestre para análisis de estacionalidad.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "((CAST(SUBSTR(FECHA,6,2) AS INT)-1)/3+1) AS TRIMESTRE, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO, TRIMESTRE ORDER BY ANIO DESC, TRIMESTRE",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_020", "Número de líneas de venta por artículo y familia", "Detalle ventas por familia",
      "Número de líneas de factura por artículo agrupado por familia.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS TOTAL_IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 GROUP BY F.NOMBRE ORDER BY TOTAL_IMPORTE DESC",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_021", "Clientes sin actividad en los últimos 6 meses", "Clientes en riesgo de abandono",
      "Clientes que tuvieron facturas pero no han generado ninguna en los últimos 6 meses.",
      "SELECT DISTINCT CODCLIENTE, MAX(FECHA) AS ULTIMA_FACTURA "
      "FROM DOCCAB WHERE TIPO=13 "
      "GROUP BY CODCLIENTE HAVING MAX(FECHA) < DATE('now','-180 days') "
      "ORDER BY ULTIMA_FACTURA ASC LIMIT 20",
      "NULL", "NULL", "Alerta", "Alto", "", ""),

    q("dv2_022", "Importe total de compras vs ventas", "Balance compras-ventas",
      "Compara el total de compras (TIPO=20) con el total de ventas (TIPO=13).",
      "SELECT ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS TOTAL_VENTAS, "
      "ROUND(SUM(CASE WHEN TIPO=20 THEN IMPORTETOTAL ELSE 0 END),2) AS TOTAL_COMPRAS, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END)-"
      "SUM(CASE WHEN TIPO=20 THEN IMPORTETOTAL ELSE 0 END),2) AS DIFERENCIA "
      "FROM DOCCAB WHERE TIPO IN (13,20)",
      "NULL", "NULL", "KPI", "Critico", "", ""),

    q("dv2_023", "Número de agentes comerciales activos", "Agentes con ventas",
      "Agentes que han generado al menos una factura TIPO=13 en los últimos 12 meses.",
      "SELECT COUNT(DISTINCT CODAGENTE) AS AGENTES_ACTIVOS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA >= DATE('now','-365 days') "
      "AND CODAGENTE IS NOT NULL AND CODAGENTE>0",
      "NULL", "NULL", "KPI", "Medio", "", ""),

    q("dv2_024", "Facturación por cliente y año", "Histórico facturación por cliente",
      "Facturación TIPO=13 por cliente y año para ver la evolución de cada cuenta.",
      "SELECT CODCLIENTE, SUBSTR(FECHA,1,4) AS ANIO, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY CODCLIENTE, ANIO ORDER BY TOTAL DESC LIMIT 30",
      "NULL", "NULL", "KPI", "Alto", "", ""),

    q("dv2_025", "Resumen ejecutivo: KPIs principales del negocio", "Dashboard ejecutivo",
      "Resumen de los KPIs más importantes: facturas, clientes, SATs, presupuestos y caja.",
      "SELECT "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13) AS N_FACTURAS, "
      "(SELECT ROUND(SUM(IMPORTETOTAL),2) FROM DOCCAB WHERE TIPO=13) AS TOTAL_FACTURADO, "
      "(SELECT COUNT(DISTINCT CODCLIENTE) FROM DOCCAB WHERE TIPO=13) AS N_CLIENTES, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=2) AS N_SATS, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=0) AS N_PRESUPUESTOS, "
      "(SELECT ROUND(SUM(IMPORTE),2) FROM CAJA) AS SALDO_CAJA",
      "NULL", "NULL", "KPI", "Critico", "", ""),
]
