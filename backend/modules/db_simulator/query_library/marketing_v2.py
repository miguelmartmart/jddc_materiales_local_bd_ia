"""marketing_v2.py — 25 consultas adicionales de Marketing (v2).

DEVIA: fichero < 500 líneas, módulo independiente, sin lógica de negocio.
"""
from backend.modules.db_simulator.query_library.builder import q

QUERIES_MARKETING_V2: list = [
    q("mv2_001", "Top 10 clientes por facturación total", "Ranking clientes por volumen",
      "Clientes con mayor importe total en facturas TIPO=13.",
      "SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE ORDER BY TOTAL DESC LIMIT 10",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_002", "Familias de artículos más vendidas por importe", "Familias top ventas",
      "Familias con mayor importe total en líneas de facturas TIPO=13.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS TOTAL_IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 GROUP BY F.NOMBRE ORDER BY TOTAL_IMPORTE DESC LIMIT 10",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_003", "Clientes con un solo documento (potencial de fidelización)", "Clientes de una sola compra",
      "Clientes que solo tienen un documento TIPO=13, candidatos a acciones de fidelización.",
      "SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE HAVING N_FACTURAS=1 "
      "ORDER BY TOTAL DESC LIMIT 20",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_004", "Artículos nunca vendidos (oportunidad o descatalogación)", "Artículos sin ventas",
      "Artículos del catálogo que no aparecen en ninguna línea de factura TIPO=13.",
      "SELECT A.CODIGO, A.NOMBRE, A.PRECIOVENTA, A.PRECIOCOSTE "
      "FROM ARTICULO A WHERE A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13) ORDER BY A.NOMBRE LIMIT 20",
      "Marketing", "Marketing", "Alerta", "Medio", "", ""),

    q("mv2_005", "Distribución de clientes por número de facturas", "Segmentación por frecuencia",
      "Agrupa clientes según el número de facturas para segmentar por frecuencia de compra.",
      "SELECT CASE WHEN N_FACTURAS=1 THEN '1 factura' "
      "WHEN N_FACTURAS BETWEEN 2 AND 5 THEN '2-5 facturas' "
      "WHEN N_FACTURAS BETWEEN 6 AND 10 THEN '6-10 facturas' "
      "ELSE 'Más de 10' END AS SEGMENTO, COUNT(*) AS N_CLIENTES "
      "FROM (SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) "
      "GROUP BY SEGMENTO ORDER BY N_CLIENTES DESC",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_006", "Artículos con mayor número de clientes distintos", "Artículos más demandados",
      "Artículos que han sido comprados por el mayor número de clientes distintos.",
      "SELECT L.CODARTICULO, A.NOMBRE, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY N_CLIENTES DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_007", "Clientes con mayor importe medio por factura", "Clientes de alto valor unitario",
      "Clientes con mayor importe medio por factura, indicativo de compras de alto valor.",
      "SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE "
      "HAVING N_FACTURAS>=2 ORDER BY IMPORTE_MEDIO DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_008", "Presupuestos por cliente (pipeline)", "Pipeline por cliente",
      "Clientes con presupuestos TIPO=0 activos para priorizar seguimiento comercial.",
      "SELECT CODCLIENTE, COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_PIPELINE "
      "FROM DOCCAB WHERE TIPO=0 GROUP BY CODCLIENTE ORDER BY TOTAL_PIPELINE DESC LIMIT 20",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_009", "Artículos vendidos solo una vez", "Artículos de baja rotación",
      "Artículos que solo aparecen en una línea de factura TIPO=13.",
      "SELECT L.CODARTICULO, A.NOMBRE, COUNT(L.CODARTICULO) AS N_VENTAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 GROUP BY L.CODARTICULO, A.NOMBRE HAVING N_VENTAS=1 "
      "ORDER BY A.NOMBRE LIMIT 20",
      "Marketing", "Marketing", "Alerta", "Medio", "", ""),

    q("mv2_010", "Clientes con presupuesto pero sin factura", "Presupuestos no convertidos",
      "Clientes que tienen presupuestos TIPO=0 pero ninguna factura TIPO=13.",
      "SELECT DISTINCT P.CODCLIENTE, COUNT(P.CODIGO) AS N_PRESUPUESTOS, "
      "ROUND(SUM(P.IMPORTETOTAL),2) AS TOTAL_PRESUPUESTADO "
      "FROM DOCCAB P WHERE P.TIPO=0 "
      "AND P.CODCLIENTE NOT IN (SELECT DISTINCT CODCLIENTE FROM DOCCAB WHERE TIPO=13) "
      "GROUP BY P.CODCLIENTE ORDER BY TOTAL_PRESUPUESTADO DESC LIMIT 20",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_011", "Ventas por mes y familia", "Estacionalidad por familia",
      "Importe de ventas por mes y familia para detectar estacionalidad por categoría.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, F.NOMBRE AS FAMILIA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS TOTAL "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY MES, F.NOMBRE ORDER BY MES DESC, TOTAL DESC LIMIT 30",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_012", "Clientes con mayor crecimiento interanual", "Clientes con más crecimiento",
      "Clientes cuya facturación del año actual supera la del año anterior.",
      "SELECT CODCLIENTE, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) THEN IMPORTETOTAL ELSE 0 END),2) AS ANIO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INT)-1 AS TEXT) THEN IMPORTETOTAL ELSE 0 END),2) AS ANIO_ANTERIOR "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE "
      "HAVING ANIO_ACTUAL>0 AND ANIO_ANTERIOR>0 "
      "ORDER BY (ANIO_ACTUAL-ANIO_ANTERIOR) DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_013", "Número de clientes nuevos por trimestre", "Captación trimestral",
      "Clientes que generaron su primera factura en cada trimestre.",
      "SELECT SUBSTR(PRIMERA_FECHA,1,4)||'-T'||((CAST(SUBSTR(PRIMERA_FECHA,6,2) AS INT)-1)/3+1) AS TRIMESTRE, "
      "COUNT(*) AS NUEVOS_CLIENTES "
      "FROM (SELECT CODCLIENTE, MIN(FECHA) AS PRIMERA_FECHA FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) "
      "GROUP BY TRIMESTRE ORDER BY TRIMESTRE DESC LIMIT 8",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_014", "Artículos con PRECIOVENTA superior a 1.000€", "Artículos de alto valor",
      "Artículos con PRECIOVENTA>1000 que representan el segmento premium del catálogo.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOVENTA>1000 ORDER BY PRECIOVENTA DESC LIMIT 20",
      "Marketing", "Marketing", "KPI", "Medio", "", ""),

    q("mv2_015", "Clientes con facturas en todos los meses del año actual", "Clientes recurrentes",
      "Clientes que han generado facturas en todos los meses del año actual.",
      "SELECT CODCLIENTE, COUNT(DISTINCT SUBSTR(FECHA,1,7)) AS MESES_CON_FACTURA "
      "FROM DOCCAB WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY CODCLIENTE "
      "HAVING MESES_CON_FACTURA=MAX(CAST(SUBSTR(DATE('now'),6,2) AS INT)) "
      "ORDER BY MESES_CON_FACTURA DESC LIMIT 20",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_016", "Importe medio de presupuesto vs factura por cliente", "Conversión valor presupuesto",
      "Compara el importe medio de presupuestos con el de facturas por cliente.",
      "SELECT P.CODCLIENTE, "
      "ROUND(AVG(P.IMPORTETOTAL),2) AS MEDIA_PRESUPUESTO, "
      "ROUND(AVG(F.IMPORTETOTAL),2) AS MEDIA_FACTURA "
      "FROM DOCCAB P JOIN DOCCAB F ON F.CODCLIENTE=P.CODCLIENTE AND F.TIPO=13 "
      "WHERE P.TIPO=0 GROUP BY P.CODCLIENTE ORDER BY MEDIA_FACTURA DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Medio", "", ""),

    q("mv2_017", "Artículos más vendidos en el último mes", "Top ventas último mes",
      "Artículos con más unidades vendidas en el último mes.",
      "SELECT L.CODARTICULO, A.NOMBRE, SUM(L.CANTIDAD) AS CANTIDAD, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-30 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY CANTIDAD DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_018", "Clientes con mayor número de artículos distintos comprados", "Amplitud de compra",
      "Clientes que han comprado el mayor número de artículos distintos.",
      "SELECT D.CODCLIENTE, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE ORDER BY N_ARTICULOS_DISTINTOS DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_019", "Familias sin ventas en el último trimestre", "Familias sin demanda reciente",
      "Familias de artículos que no han generado ninguna venta en los últimos 90 días.",
      "SELECT F.NOMBRE AS FAMILIA FROM FAMILIA F "
      "WHERE F.CODIGO NOT IN ("
      "SELECT DISTINCT A.CODFAMILIA FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-90 days')) "
      "ORDER BY F.NOMBRE",
      "Marketing", "Marketing", "Alerta", "Medio", "", ""),

    q("mv2_020", "Clientes con mayor variedad de familias compradas", "Diversificación de compra",
      "Clientes que han comprado artículos de más familias distintas.",
      "SELECT D.CODCLIENTE, COUNT(DISTINCT A.CODFAMILIA) AS N_FAMILIAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE ORDER BY N_FAMILIAS DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Medio", "", ""),

    q("mv2_021", "Artículos con descuento aplicado en facturas", "Artículos con descuento",
      "Artículos en líneas de factura donde el PRECIOVENTA de línea es inferior al PRECIOVENTA de catálogo.",
      "SELECT L.CODARTICULO, A.NOMBRE, A.PRECIOVENTA AS PRECIO_CATALOGO, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO_FACTURADO, "
      "ROUND(AVG(A.PRECIOVENTA-L.PRECIO),2) AS DESCUENTO_MEDIO "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND L.PRECIO<A.PRECIOVENTA AND A.PRECIOVENTA>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY DESCUENTO_MEDIO DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_022", "Número de presupuestos por agente", "Pipeline por agente",
      "Presupuestos TIPO=0 agrupados por agente para ver el pipeline comercial de cada uno.",
      "SELECT CODAGENTE, COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_PIPELINE "
      "FROM DOCCAB WHERE TIPO=0 GROUP BY CODAGENTE ORDER BY TOTAL_PIPELINE DESC",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_023", "Clientes con presupuesto y factura en el mismo mes", "Conversión rápida",
      "Clientes que convirtieron un presupuesto en factura dentro del mismo mes.",
      "SELECT P.CODCLIENTE, SUBSTR(P.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT P.CODIGO) AS N_PRESUPUESTOS, COUNT(DISTINCT F.CODIGO) AS N_FACTURAS "
      "FROM DOCCAB P JOIN DOCCAB F ON F.CODCLIENTE=P.CODCLIENTE "
      "AND SUBSTR(F.FECHA,1,7)=SUBSTR(P.FECHA,1,7) AND F.TIPO=13 "
      "WHERE P.TIPO=0 GROUP BY P.CODCLIENTE, MES ORDER BY N_FACTURAS DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Medio", "", ""),

    q("mv2_024", "Artículos con mayor margen porcentual", "Artículos más rentables por margen",
      "Artículos con mayor porcentaje de margen (PRECIOVENTA-PRECIOCOSTE)/PRECIOVENTA.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE, "
      "ROUND((PRECIOVENTA-PRECIOCOSTE)/PRECIOVENTA*100,1) AS PCT_MARGEN "
      "FROM ARTICULO WHERE PRECIOVENTA>0 AND PRECIOCOSTE>0 AND PRECIOVENTA>PRECIOCOSTE "
      "ORDER BY PCT_MARGEN DESC LIMIT 15",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),

    q("mv2_025", "Clientes con facturas en el último mes", "Clientes activos último mes",
      "Clientes que han generado al menos una factura TIPO=13 en los últimos 30 días.",
      "SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA >= DATE('now','-30 days') "
      "GROUP BY CODCLIENTE ORDER BY TOTAL DESC LIMIT 20",
      "Marketing", "Marketing", "KPI", "Alto", "", ""),
]
