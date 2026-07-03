"""
query_library/ventas_v2.py — 125 consultas adicionales de Ventas (v2).

Diferentes a ventas.py. Cubren: análisis de cartera, ciclo de vida cliente,
rentabilidad por segmento, análisis de descuentos, pipeline comercial,
estacionalidad avanzada, análisis de devoluciones y abonos.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: strftime, JULIANDAY, SUBSTR, CAST, COALESCE.
"""

from backend.modules.db_simulator.query_library.builder import q

_C = "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, CAST(D.CODCLIENTE AS TEXT))"

QUERIES_VENTAS_V2 = [

    q("vx2_001", "Clientes sin factura en los últimos 6 meses",
      "¿Qué clientes activos no han comprado en los últimos 6 meses?",
      "Clientes con al menos 1 factura histórica pero sin ninguna en los últimos 180 días.",
      f"SELECT {_C} AS CLIENTE, MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "COUNT(*) AS TOTAL_FACTURAS_HISTORICAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING MAX(D.FECHA) < DATE('now','-180 days') "
      "ORDER BY ULTIMA_COMPRA DESC LIMIT 30",
      "Ventas","Comercial","Cliente","Alto","Clientes inactivos",""),

    q("vx2_002", "Tasa de recompra por cliente",
      "¿Qué porcentaje de clientes han comprado más de una vez?",
      "Agrupa clientes por número de facturas. Clientes con N=1 son de compra única.",
      "SELECT CASE WHEN N_FACTURAS=1 THEN 'Una sola compra' "
      "WHEN N_FACTURAS BETWEEN 2 AND 5 THEN '2-5 compras' "
      "WHEN N_FACTURAS BETWEEN 6 AND 10 THEN '6-10 compras' "
      "ELSE 'Más de 10 compras' END AS SEGMENTO, "
      "COUNT(*) AS N_CLIENTES, ROUND(AVG(TOTAL_EUR),2) AS MEDIA_GASTO "
      "FROM (SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS, SUM(IMPORTETOTAL) AS TOTAL_EUR "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) "
      "GROUP BY SEGMENTO ORDER BY MIN(N_FACTURAS)",
      "Ventas","Comercial","Cliente","Medio","Fidelización",""),

    q("vx2_003", "Valor de vida del cliente (LTV estimado)",
      "¿Cuál es el gasto total acumulado por cliente?",
      "Suma total de IMPORTETOTAL por cliente en facturas TIPO=13. Ordenado por LTV descendente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS LTV_TOTAL, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "MIN(D.FECHA) AS PRIMERA_COMPRA, MAX(D.FECHA) AS ULTIMA_COMPRA "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY LTV_TOTAL DESC LIMIT 30",
      "Ventas","Dirección","Cliente","Alto","LTV",""),

    q("vx2_004", "Abonos y devoluciones (TIPO=3)",
      "¿Cuántos abonos se han emitido y por qué importe?",
      "Documentos TIPO=3 (abonos/rectificativas). Importes negativos reducen la facturación neta.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_ABONOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_ABONOS "
      "FROM DOCCAB WHERE TIPO=3 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas","Finanzas","Operacional","Alto","Abonos",""),

    q("vx2_005", "Ratio abonos / facturas por mes",
      "¿Qué porcentaje de la facturación se devuelve cada mes?",
      "Compara importe de abonos (TIPO=3) vs facturas (TIPO=13) por mes.",
      "SELECT F.MES, F.TOTAL_FACTURAS, COALESCE(A.TOTAL_ABONOS,0) AS TOTAL_ABONOS, "
      "ROUND(COALESCE(A.TOTAL_ABONOS,0)*100.0/NULLIF(F.TOTAL_FACTURAS,0),2) AS RATIO_PCT "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) F "
      "LEFT JOIN (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(ABS(SUM(IMPORTETOTAL)),2) AS TOTAL_ABONOS "
      "FROM DOCCAB WHERE TIPO=3 AND FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) A "
      "ON F.MES=A.MES ORDER BY F.MES DESC LIMIT 12",
      "Ventas","Finanzas","KPI","Alto","Devoluciones",""),

    q("vx2_006", "Clientes con mayor número de abonos",
      "¿Qué clientes generan más devoluciones?",
      "Clientes con más documentos TIPO=3. Alta frecuencia puede indicar problemas de calidad.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_ABONOS, "
      "ROUND(SUM(ABS(D.IMPORTETOTAL)),2) AS TOTAL_DEVUELTO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=3 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_ABONOS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Devoluciones",""),

    q("vx2_007", "Facturación neta (facturas menos abonos)",
      "¿Cuál es la facturación real descontando devoluciones?",
      "Suma TIPO=13 menos valor absoluto de TIPO=3 por mes.",
      "SELECT MES, ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL "
      "WHEN TIPO=3 THEN -ABS(IMPORTETOTAL) ELSE 0 END),2) AS FACTURACION_NETA, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS BRUTA, "
      "ROUND(SUM(CASE WHEN TIPO=3 THEN ABS(IMPORTETOTAL) ELSE 0 END),2) AS ABONOS "
      "FROM (SELECT TIPO, IMPORTETOTAL, SUBSTR(FECHA,1,7) AS MES FROM DOCCAB "
      "WHERE TIPO IN (13,3) AND FECHA IS NOT NULL) "
      "GROUP BY MES ORDER BY MES DESC LIMIT 12",
      "Ventas","Finanzas","KPI","Crítico","Facturación neta",""),

    q("vx2_008", "Descuentos aplicados en facturas",
      "¿Qué descuentos se aplican en las líneas de factura?",
      "Analiza DESCUENTOS en DOCLIN para facturas TIPO=13. Detecta si hay descuentos excesivos.",
      "SELECT CASE WHEN L.DESCUENTOS=0 THEN 'Sin descuento' "
      "WHEN L.DESCUENTOS<=5 THEN '1-5%' "
      "WHEN L.DESCUENTOS<=10 THEN '6-10%' "
      "WHEN L.DESCUENTOS<=20 THEN '11-20%' "
      "ELSE 'Más de 20%' END AS RANGO_DESCUENTO, "
      "COUNT(*) AS N_LINEAS, ROUND(AVG(L.DESCUENTOS),2) AS MEDIA_DESC "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "WHERE L.DESCUENTOS IS NOT NULL "
      "GROUP BY RANGO_DESCUENTO ORDER BY MIN(L.DESCUENTOS)",
      "Ventas","Comercial","Operacional","Medio","Descuentos",""),

    q("vx2_009", "Agente con mayor descuento medio aplicado",
      "¿Qué agente aplica más descuentos en sus ventas?",
      "Promedio de DESCUENTOS en DOCLIN agrupado por CODAGENTE de DOCCAB.",
      "SELECT D.CODAGENTE, COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(AVG(L.DESCUENTOS),2) AS DESCUENTO_MEDIO, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_FACTURADO "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS IS NOT NULL "
      "GROUP BY D.CODAGENTE ORDER BY DESCUENTO_MEDIO DESC LIMIT 10",
      "Ventas","Comercial","Agente","Medio","Descuentos por agente",""),

    q("vx2_010", "Facturas con descuento superior al 30%",
      "¿Qué facturas tienen líneas con descuento mayor al 30%?",
      "Líneas de DOCLIN con DESCUENTOS>30 en facturas TIPO=13. Pueden indicar errores o excepciones.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, MAX(L.DESCUENTOS) AS MAX_DESCUENTO "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>30 "
      "GROUP BY D.CODIGO, D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.FECHA, D.IMPORTETOTAL "
      "ORDER BY MAX_DESCUENTO DESC LIMIT 20",
      "Ventas","Comercial","Alerta","Alto","Descuentos excesivos",""),

    q("vx2_011", "Evolución trimestral de ventas",
      "¿Cómo evolucionan las ventas por trimestre?",
      "Agrupa DOCCAB TIPO=13 por año y trimestre (Q1-Q4).",
      "SELECT SUBSTR(FECHA,1,4) AS ANO, "
      "CASE WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANO, TRIMESTRE ORDER BY ANO DESC, TRIMESTRE",
      "Ventas","Dirección","KPI","Alto","Estacionalidad",""),

    q("vx2_012", "Comparativa mismo mes año anterior vs actual",
      "¿Cómo se compara el mes actual con el mismo mes del año pasado?",
      "Compara IMPORTETOTAL del mes actual vs mismo mes del año anterior.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "AND (SUBSTR(FECHA,1,7)=STRFTIME('%Y-%m','now') "
      "OR SUBSTR(FECHA,1,7)=STRFTIME('%Y-%m','now','-1 year')) "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES",
      "Ventas","Dirección","KPI","Alto","Comparativa YoY",""),

    q("vx2_013", "Clientes con primera compra este año",
      "¿Qué clientes han comprado por primera vez este año?",
      "Clientes cuya primera factura (MIN FECHA) es del año en curso.",
      f"SELECT {_C} AS CLIENTE, MIN(D.FECHA) AS PRIMERA_COMPRA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING MIN(D.FECHA) >= DATE('now','start of year') "
      "ORDER BY PRIMERA_COMPRA DESC LIMIT 30",
      "Ventas","Comercial","Cliente","Medio","Nuevos clientes",""),

    q("vx2_014", "Facturas sin líneas de detalle",
      "¿Hay facturas sin ninguna línea en DOCLIN?",
      "Facturas TIPO=13 sin registros en DOCLIN. Pueden indicar errores de importación.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D WHERE D.TIPO=13 "
      "AND NOT EXISTS (SELECT 1 FROM DOCLIN L WHERE L.CODDOCUMENTO=D.CODIGO) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Integridad datos",""),

    q("vx2_015", "Número medio de líneas por factura",
      "¿Cuántos artículos distintos se incluyen de media en cada factura?",
      "COUNT de DOCLIN por CODDOCUMENTO para facturas TIPO=13.",
      "SELECT ROUND(AVG(N_LINEAS),2) AS MEDIA_LINEAS, "
      "MIN(N_LINEAS) AS MIN_LINEAS, MAX(N_LINEAS) AS MAX_LINEAS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM (SELECT L.CODDOCUMENTO, COUNT(*) AS N_LINEAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY L.CODDOCUMENTO)",
      "Ventas","Comercial","Operacional","Bajo","Complejidad factura",""),

    q("vx2_016", "Top 10 facturas de mayor importe",
      "¿Cuáles son las 10 facturas de mayor importe?",
      "Las 10 facturas TIPO=13 con mayor IMPORTETOTAL.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, D.CODAGENTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 ORDER BY D.IMPORTETOTAL DESC LIMIT 10",
      "Ventas","Dirección","KPI","Alto","Top facturas",""),

    q("vx2_017", "Facturas emitidas en fin de semana",
      "¿Hay facturas emitidas en sábado o domingo?",
      "Facturas TIPO=13 con strftime('%w')=0 (domingo) o 6 (sábado).",
      "SELECT CASE CAST(strftime('%w',FECHA) AS INTEGER) "
      "WHEN 0 THEN 'Domingo' ELSE 'Sábado' END AS DIA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "AND CAST(strftime('%w',FECHA) AS INTEGER) IN (0,6) "
      "GROUP BY DIA",
      "Ventas","Calidad","Operacional","Bajo","Anomalías fecha",""),

    q("vx2_018", "Clientes con facturas en todos los meses del año",
      "¿Qué clientes compran de forma constante todos los meses?",
      "Clientes con facturas en 12 meses distintos del año actual.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_CON_COMPRA, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7))>=10 "
      "ORDER BY MESES_CON_COMPRA DESC",
      "Ventas","Comercial","Cliente","Medio","Fidelización",""),

    q("vx2_019", "Distribución de facturas por rango de días desde emisión",
      "¿Cuántos días de antigüedad tienen las facturas pendientes?",
      "Agrupa facturas TIPO=13 por antigüedad en días.",
      "SELECT CASE WHEN DIAS<=7 THEN '0-7 días' "
      "WHEN DIAS<=30 THEN '8-30 días' "
      "WHEN DIAS<=90 THEN '31-90 días' "
      "WHEN DIAS<=180 THEN '91-180 días' "
      "ELSE 'Más de 180 días' END AS RANGO, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTE),2) AS TOTAL "
      "FROM (SELECT IMPORTETOTAL AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(FECHA) AS INTEGER) AS DIAS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL) "
      "GROUP BY RANGO ORDER BY MIN(DIAS)",
      "Ventas","Finanzas","Operacional","Medio","Antigüedad facturas",""),

    q("vx2_020", "Ventas por código postal del cliente",
      "¿Qué zonas geográficas generan más ventas?",
      "Agrupa por CP de CLIENTE para ver distribución geográfica.",
      "SELECT C.CP, COUNT(D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND C.CP IS NOT NULL AND C.CP!='' "
      "GROUP BY C.CP ORDER BY TOTAL DESC LIMIT 20",
      "Ventas","Marketing","Geográfico","Medio","Distribución geográfica",""),

    q("vx2_021", "Facturas con importe exactamente igual a otra del mismo cliente",
      "¿Hay facturas duplicadas por importe y cliente?",
      "Detecta pares de facturas del mismo cliente con el mismo importe exacto.",
      "SELECT CODCLIENTE, ROUND(IMPORTETOTAL,2) AS IMPORTE, COUNT(*) AS N_REPETICIONES "
      "FROM DOCCAB WHERE TIPO=13 "
      "GROUP BY CODCLIENTE, ROUND(IMPORTETOTAL,2) "
      "HAVING COUNT(*)>1 ORDER BY N_REPETICIONES DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Duplicados potenciales",""),

    q("vx2_022", "Clientes con mayor crecimiento interanual",
      "¿Qué clientes han aumentado más su compra respecto al año anterior?",
      "Compara facturación por cliente entre año actual y año anterior.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANO_ANTERIOR "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING ANO_ANTERIOR>0 AND ANO_ACTUAL>ANO_ANTERIOR "
      "ORDER BY (ANO_ACTUAL-ANO_ANTERIOR) DESC LIMIT 20",
      "Ventas","Dirección","Cliente","Alto","Crecimiento clientes",""),

    q("vx2_023", "Clientes con mayor caída interanual",
      "¿Qué clientes han reducido más su compra respecto al año anterior?",
      "Compara facturación por cliente entre año actual y año anterior. Caída = riesgo de fuga.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANO_ANTERIOR "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING ANO_ANTERIOR>0 AND ANO_ACTUAL<ANO_ANTERIOR "
      "ORDER BY (ANO_ANTERIOR-ANO_ACTUAL) DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Alto","Riesgo fuga",""),

    q("vx2_024", "Facturas con IMPORTEIVA cero o nulo",
      "¿Hay facturas sin IMPORTEIVA aplicado?",
      "Facturas TIPO=13 con IMPORTEIVA=0 o NULL. Pueden ser exportaciones o errores.",
      "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE, "
      "COALESCE(IMPORTEIVA,0) AS IMPORTEIVA "
      "FROM DOCCAB WHERE TIPO=13 AND (IMPORTEIVA=0 OR IMPORTEIVA IS NULL) "
      "ORDER BY FECHA DESC LIMIT 20",
      "Ventas","Finanzas","Alerta","Alto","IMPORTEIVA cero",""),

    q("vx2_025", "Distribución de tipos de IMPORTEIVA en líneas de factura",
      "¿Qué tipos de IMPORTEIVA se aplican en las líneas de venta?",
      "Agrupa DOCLIN por TIPOIVA para facturas TIPO=13.",
      "SELECT L.TIPOIVA, COUNT(*) AS N_LINEAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_BASE "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "WHERE L.TIPOIVA IS NOT NULL "
      "GROUP BY L.TIPOIVA ORDER BY N_LINEAS DESC",
      "Ventas","Finanzas","Operacional","Medio","Tipos IMPORTEIVA",""),

    q("vx2_026", "Agentes sin ventas en el último mes",
      "¿Qué agentes no han generado ninguna factura en el último mes?",
      "Agentes con CODAGENTE en DOCCAB pero sin facturas TIPO=13 en los últimos 30 días.",
      "SELECT DISTINCT D.CODAGENTE "
      "FROM DOCCAB D WHERE D.TIPO=13 "
      "AND D.CODAGENTE NOT IN ("
      "SELECT CODAGENTE FROM DOCCAB WHERE TIPO=13 AND FECHA>=DATE('now','-30 days') "
      "AND CODAGENTE IS NOT NULL) "
      "AND D.CODAGENTE IS NOT NULL",
      "Ventas","RRHH","Alerta","Alto","Agentes inactivos",""),

    q("vx2_027", "Facturación por agente y mes (últimos 6 meses)",
      "¿Cómo evoluciona la facturación de cada agente mes a mes?",
      "Agrupa DOCCAB TIPO=13 por CODAGENTE y mes para los últimos 6 meses.",
      "SELECT CODAGENTE, SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA>=DATE('now','-180 days') "
      "GROUP BY CODAGENTE, SUBSTR(FECHA,1,7) "
      "ORDER BY CODAGENTE, MES DESC",
      "Ventas","Comercial","Agente","Medio","Evolución por agente",""),

    q("vx2_028", "Clientes con forma de pago no asignada",
      "¿Qué clientes no tienen forma de pago definida?",
      "Clientes en CLIENTE con FORMASPAGO NULL o vacío.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL,'Sin nombre') AS NOMBRE, "
      "FORMASPAGO "
      "FROM CLIENTE WHERE FORMASPAGO IS NULL OR FORMASPAGO='' "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas","Finanzas","Calidad","Medio","Datos maestros",""),

    q("vx2_029", "Facturas con fecha futura (error de fecha)",
      "¿Hay facturas con fecha posterior a hoy?",
      "Facturas TIPO=13 con FECHA > DATE('now'). Indican errores de entrada de datos.",
      "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA > DATE('now') "
      "ORDER BY FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Crítico","Errores fecha",""),

    q("vx2_030", "Facturas con fecha anterior a 2010 (posible error)",
      "¿Hay facturas con fecha muy antigua que puedan ser errores?",
      "Facturas TIPO=13 con FECHA < '2010-01-01'. Pueden ser migraciones o errores.",
      "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA < '2010-01-01' "
      "ORDER BY FECHA ASC LIMIT 20",
      "Ventas","Calidad","Alerta","Medio","Fechas antiguas",""),

    q("vx2_031", "Concentración de ventas: % del top 3 clientes",
      "¿Qué porcentaje de las ventas totales representan los 3 mejores clientes?",
      "Calcula el peso de los 3 clientes con mayor facturación sobre el total.",
      "SELECT ROUND(SUM(TOTAL_CLIENTE)*100.0/SUM(SUM(TOTAL_CLIENTE)) OVER(),2) AS PCT_TOP3 "
      "FROM (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL_CLIENTE "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE "
      "ORDER BY TOTAL_CLIENTE DESC LIMIT 3)",
      "Ventas","Dirección","KPI","Alto","Concentración",""),

    q("vx2_032", "Facturas con CODCLIENTE nulo",
      "¿Hay facturas sin cliente asignado?",
      "Facturas TIPO=13 con CODCLIENTE NULL. No se pueden atribuir a ningún cliente.",
      "SELECT COUNT(*) AS N_SIN_CLIENTE, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND CODCLIENTE IS NULL",
      "Ventas","Calidad","Alerta","Alto","Integridad datos",""),

    q("vx2_033", "Ventas por familia de artículo",
      "¿Qué familias de artículos generan más ventas?",
      "JOIN DOCLIN → ARTICULO → FAMILIA para facturas TIPO=13.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_TOTAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "GROUP BY F.CODIGO, F.NOMBRE ORDER BY IMPORTE_TOTAL DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","Ventas por familia",""),

    q("vx2_034", "Artículos vendidos solo una vez",
      "¿Qué artículos aparecen en una sola línea de factura?",
      "Artículos con COUNT(DOCLIN)=1 en facturas TIPO=13. Pueden ser artículos obsoletos.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_VENTAS "
      "FROM ARTICULO A JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY A.CODIGO, A.NOMBRE HAVING COUNT(L.CODARTICULO)=1 "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Ventas","Almacén","Producto","Bajo","Artículos poco vendidos",""),

    q("vx2_035", "PRECIOVENTA medio de venta por artículo",
      "¿A qué PRECIOVENTA medio se vende cada artículo?",
      "AVG(PRECIOVENTA) en DOCLIN para facturas TIPO=13 por artículo.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_VENTAS, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO, "
      "ROUND(MIN(L.PRECIO),2) AS PRECIO_MIN, "
      "ROUND(MAX(L.PRECIO),2) AS PRECIO_MAX "
      "FROM ARTICULO A JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_VENTAS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","Precios de venta",""),

    q("vx2_036", "Variabilidad de PRECIOVENTA por artículo (PRECIOVENTA máx vs mín)",
      "¿Qué artículos tienen mayor variación de PRECIOVENTA entre ventas?",
      "Diferencia entre MAX y MIN de PRECIOVENTA en DOCLIN por artículo.",
      "SELECT A.NOMBRE, ROUND(MAX(L.PRECIO)-MIN(L.PRECIO),2) AS VARIACION_PRECIO, "
      "ROUND(MIN(L.PRECIO),2) AS MIN_PRECIO, ROUND(MAX(L.PRECIO),2) AS MAX_PRECIO, "
      "COUNT(*) AS N_VENTAS "
      "FROM ARTICULO A JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY A.CODIGO, A.NOMBRE HAVING COUNT(*)>2 "
      "ORDER BY VARIACION_PRECIO DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","Variabilidad precios",""),

    q("vx2_037", "Clientes que solo compran en un mes del año",
      "¿Hay clientes con compras concentradas en un solo mes?",
      "Clientes con facturas en un único mes del año. Pueden ser estacionales.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_DISTINTOS, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7))=1 AND COUNT(*)>1 "
      "ORDER BY TOTAL DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Estacionalidad clientes",""),

    q("vx2_038", "Facturas con importe inferior a 50 EUR",
      "¿Cuántas facturas son de importe muy bajo (menos de 50 EUR)?",
      "Facturas TIPO=13 con IMPORTETOTAL<50. Pueden indicar trabajos menores o errores.",
      "SELECT COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS MEDIA "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL<50 AND IMPORTETOTAL>0",
      "Ventas","Finanzas","Operacional","Bajo","Facturas pequeñas",""),

    q("vx2_039", "Facturas con importe superior a 10.000 EUR",
      "¿Cuántas facturas superan los 10.000 EUR?",
      "Facturas TIPO=13 con IMPORTETOTAL>10000. Son las de mayor impacto en la facturación.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL>10000 "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 30",
      "Ventas","Dirección","KPI","Alto","Facturas grandes",""),

    q("vx2_040", "Número de clientes únicos por agente",
      "¿Cuántos clientes distintos gestiona cada agente?",
      "COUNT(DISTINCT CODCLIENTE) por CODAGENTE en facturas TIPO=13.",
      "SELECT CODAGENTE, COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE IS NOT NULL "
      "GROUP BY CODAGENTE ORDER BY N_CLIENTES DESC",
      "Ventas","Comercial","Agente","Medio","Cartera por agente",""),

    q("vx2_041", "Facturas con el mismo número de líneas que otra del mismo cliente",
      "¿Hay facturas con estructura idéntica (mismo cliente, mismas líneas)?",
      "Detecta facturas con igual CODCLIENTE y N_LINEAS. Posibles duplicados.",
      "SELECT CODCLIENTE, N_LINEAS, COUNT(*) AS N_FACTURAS_IGUALES "
      "FROM (SELECT D.CODCLIENTE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODIGO, D.CODCLIENTE) "
      "GROUP BY CODCLIENTE, N_LINEAS HAVING COUNT(*)>2 "
      "ORDER BY N_FACTURAS_IGUALES DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Medio","Duplicados estructura",""),

    q("vx2_042", "Evolución del número de clientes activos por mes",
      "¿Cómo varía el número de clientes que compran cada mes?",
      "COUNT(DISTINCT CODCLIENTE) por mes en facturas TIPO=13.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(DISTINCT CODCLIENTE) AS CLIENTES_ACTIVOS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas","Comercial","KPI","Alto","Clientes activos por mes",""),

    q("vx2_043", "Artículos con PRECIOVENTA de venta inferior al PRECIOCOSTE",
      "¿Se venden artículos por debajo del PRECIOCOSTE?",
      "Líneas de DOCLIN donde PRECIOVENTA < PRECIOCOSTE del artículo. Indica pérdida en esa venta.",
      "SELECT A.NOMBRE, L.PRECIO AS PRECIO_VENTA, A.PRECIOCOSTE, "
      "ROUND(L.PRECIO-A.PRECIOCOSTE,2) AS MARGEN, D.FECHA "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "WHERE L.PRECIO<A.PRECIOCOSTE AND A.PRECIOCOSTE>0 "
      "ORDER BY MARGEN ASC LIMIT 20",
      "Ventas","Finanzas","Alerta","Crítico","Ventas bajo PRECIOCOSTE",""),

    q("vx2_044", "Clientes con NULL registrado vs sin NULL",
      "¿Qué porcentaje de clientes tienen NULL registrado?",
      "Cuenta clientes con NULL no nulo vs total en tabla CLIENTE.",
      "SELECT "
      "SUM(CASE WHEN NULL IS NOT NULL AND NULL!='' THEN 1 ELSE 0 END) AS CON_EMAIL, "
      "SUM(CASE WHEN NULL IS NULL OR NULL='' THEN 1 ELSE 0 END) AS SIN_EMAIL, "
      "COUNT(*) AS TOTAL "
      "FROM CLIENTE",
      "Ventas","Marketing","Calidad","Bajo","Datos maestros",""),

    q("vx2_045", "Facturas con CODAGENTE nulo",
      "¿Hay facturas sin agente asignado?",
      "Facturas TIPO=13 con CODAGENTE NULL. No se pueden atribuir a ningún comercial.",
      "SELECT COUNT(*) AS N_SIN_AGENTE, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE IS NULL",
      "Ventas","Comercial","Calidad","Medio","Datos maestros",""),

    q("vx2_046", "Ranking de artículos por margen bruto estimado",
      "¿Qué artículos generan más margen bruto?",
      "Margen = (PRECIOVENTA - PRECIOCOSTE) * CANTIDAD por artículo en facturas TIPO=13.",
      "SELECT A.NOMBRE, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN_TOTAL, "
      "ROUND(AVG(L.PRECIO-A.PRECIOCOSTE),2) AS MARGEN_UNITARIO, "
      "COUNT(*) AS N_VENTAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "WHERE A.PRECIOCOSTE>0 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY MARGEN_TOTAL DESC LIMIT 20",
      "Ventas","Finanzas","Producto","Alto","Margen por artículo",""),

    q("vx2_047", "Clientes con teléfono registrado vs sin teléfono",
      "¿Qué porcentaje de clientes tienen teléfono registrado?",
      "Cuenta clientes con TEL no nulo vs total.",
      "SELECT "
      "SUM(CASE WHEN TEL IS NOT NULL AND TEL!='' THEN 1 ELSE 0 END) AS CON_TELEFONO, "
      "SUM(CASE WHEN TEL IS NULL OR TEL='' THEN 1 ELSE 0 END) AS SIN_TELEFONO, "
      "COUNT(*) AS TOTAL FROM CLIENTE",
      "Ventas","Marketing","Calidad","Bajo","Datos maestros",""),

    q("vx2_048", "Facturas con más de 20 líneas",
      "¿Qué facturas tienen más de 20 líneas de detalle?",
      "Facturas TIPO=13 con COUNT(DOCLIN)>20. Son las más complejas.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODIGO, D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.FECHA, D.IMPORTETOTAL "
      "HAVING COUNT(L.CODARTICULO)>20 ORDER BY N_LINEAS DESC LIMIT 20",
      "Ventas","Operaciones","Operacional","Bajo","Facturas complejas",""),

    q("vx2_049", "Ventas acumuladas año actual vs objetivo (si existe tabla objetivo)",
      "¿Cuánto se ha facturado en el año actual?",
      "Suma IMPORTETOTAL de facturas TIPO=13 del año en curso.",
      "SELECT STRFTIME('%Y','now') AS ANO, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_ACUMULADO "
      "FROM DOCCAB WHERE TIPO=13 "
      "AND SUBSTR(FECHA,1,4)=STRFTIME('%Y','now')",
      "Ventas","Dirección","KPI","Crítico","Acumulado anual",""),

    q("vx2_050", "Clientes con NIF duplicado",
      "¿Hay clientes con el mismo NIF registrado más de una vez?",
      "Detecta NIF duplicados en tabla CLIENTE. Pueden causar problemas fiscales.",
      "SELECT NIF, COUNT(*) AS N_CLIENTES "
      "FROM CLIENTE WHERE NIF IS NOT NULL AND NIF!='' "
      "GROUP BY NIF HAVING COUNT(*)>1 ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Duplicados NIF",""),

    q("vx2_051", "Facturas por serie documental",
      "¿Cuántas facturas hay por cada serie?",
      "Agrupa DOCCAB TIPO=13 por SERIE para ver distribución de series documentales.",
      "SELECT SERIE, COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 "
      "GROUP BY SERIE ORDER BY N_FACTURAS DESC",
      "Ventas","Finanzas","Operacional","Bajo","Series documentales",""),

    q("vx2_052", "Clientes con más de 5 agentes distintos asignados",
      "¿Hay clientes atendidos por demasiados agentes distintos?",
      "COUNT(DISTINCT CODAGENTE) por cliente en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT D.CODAGENTE) AS N_AGENTES, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT D.CODAGENTE)>2 "
      "ORDER BY N_AGENTES DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Asignación agentes",""),

    q("vx2_053", "Artículos sin ventas en el último año",
      "¿Qué artículos no se han vendido en los últimos 12 meses?",
      "Artículos en ARTICULO sin ninguna línea en DOCLIN de facturas TIPO=13 en el último año.",
      "SELECT A.CODIGO, A.NOMBRE "
      "FROM ARTICULO A "
      "WHERE NOT EXISTS ("
      "SELECT 1 FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "WHERE L.CODARTICULO=A.CODIGO AND D.FECHA>=DATE('now','-365 days')) "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Ventas","Almacén","Producto","Medio","Artículos sin movimiento",""),

    q("vx2_054", "Facturas con IMPORTEBASE inconsistente con IMPORTETOTAL",
      "¿Hay facturas donde la base imponible más IMPORTEIVA no cuadra con el total?",
      "Verifica que IMPORTEBASE + IMPORTEIVA ≈ IMPORTETOTAL en facturas TIPO=13.",
      "SELECT CODIGO, ROUND(IMPORTEBASE,2) AS BASE, ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL, "
      "ROUND(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL,2) AS DIFERENCIA "
      "FROM DOCCAB WHERE TIPO=13 "
      "AND ABS(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL)>0.05 "
      "ORDER BY ABS(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL) DESC LIMIT 20",
      "Ventas","Finanzas","Alerta","Alto","Coherencia IMPORTEIVA",""),

    q("vx2_055", "Clientes con dirección de facturación incompleta",
      "¿Qué clientes tienen datos de dirección incompletos?",
      "Clientes sin NULL, NULL o CP en tabla CLIENTE.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL,'Sin nombre') AS NOMBRE, "
      "CASE WHEN NULL IS NULL OR NULL='' THEN 'Sin dirección' ELSE 'OK' END AS DIR, "
      "CASE WHEN NULL IS NULL OR NULL='' THEN 'Sin población' ELSE 'OK' END AS POB, "
      "CASE WHEN CP IS NULL OR CP='' THEN 'Sin CP' ELSE 'OK' END AS CP "
      "FROM CLIENTE WHERE (NULL IS NULL OR NULL='') "
      "OR (NULL IS NULL OR NULL='') "
      "OR (CP IS NULL OR CP='') "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas","Calidad","Calidad","Bajo","Datos maestros",""),

    q("vx2_056", "Ventas por día del mes (1-31)",
      "¿Qué días del mes concentran más ventas?",
      "Agrupa DOCCAB TIPO=13 por día del mes (1-31).",
      "SELECT CAST(SUBSTR(FECHA,9,2) AS INTEGER) AS DIA_MES, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY DIA_MES ORDER BY DIA_MES",
      "Ventas","Comercial","Operacional","Bajo","Distribución diaria",""),

    q("vx2_057", "Facturas con CODCLIENTE que no existe en tabla CLIENTE",
      "¿Hay facturas con clientes huérfanos (no en tabla CLIENTE)?",
      "Facturas TIPO=13 con CODCLIENTE que no tiene registro en CLIENTE.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D WHERE D.TIPO=13 AND D.CODCLIENTE IS NOT NULL "
      "AND NOT EXISTS (SELECT 1 FROM CLIENTE C WHERE C.CODIGO=D.CODCLIENTE) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Integridad referencial",""),

    q("vx2_058", "Artículos con PRECIOVENTA de venta cero",
      "¿Hay artículos con PRECIOVENTA de venta igual a cero?",
      "Líneas de DOCLIN con PRECIOVENTA=0 en facturas TIPO=13.",
      "SELECT A.NOMBRE, COUNT(*) AS N_LINEAS, D.FECHA "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "WHERE L.PRECIO=0 OR L.PRECIO IS NULL "
      "GROUP BY A.CODIGO, A.NOMBRE, D.FECHA "
      "ORDER BY N_LINEAS DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Precios cero",""),

    q("vx2_059", "Clientes con mayor número de facturas rectificativas",
      "¿Qué clientes tienen más abonos o rectificativas?",
      "COUNT de TIPO=3 por cliente. Alta frecuencia puede indicar problemas recurrentes.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_ABONOS, "
      "ROUND(SUM(ABS(D.IMPORTETOTAL)),2) AS TOTAL_ABONADO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=3 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_ABONOS DESC LIMIT 20",
      "Ventas","Calidad","Cliente","Medio","Rectificativas por cliente",""),

    q("vx2_060", "Facturas con cantidad negativa en líneas",
      "¿Hay líneas de factura con cantidad negativa?",
      "DOCLIN con CANTIDAD<0 en facturas TIPO=13. Pueden ser devoluciones parciales.",
      "SELECT D.CODIGO, A.NOMBRE AS ARTICULO, L.CANTIDAD, L.PRECIO, D.FECHA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE L.CANTIDAD<0 ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Cantidades negativas",""),

    q("vx2_061", "Evolución del ticket medio por trimestre",
      "¿Cómo evoluciona el ticket medio trimestre a trimestre?",
      "AVG(IMPORTETOTAL) por trimestre en facturas TIPO=13.",
      "SELECT SUBSTR(FECHA,1,4) AS ANO, "
      "CASE WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER)<=3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER)<=6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER)<=9 THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "COUNT(*) AS N_FACTURAS, ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANO, TRIMESTRE ORDER BY ANO DESC, TRIMESTRE",
      "Ventas","Dirección","KPI","Medio","Ticket medio trimestral",""),

    q("vx2_062", "Clientes con mayor variación de ticket entre compras",
      "¿Qué clientes tienen mayor variabilidad en sus importes de compra?",
      "MAX-MIN de IMPORTETOTAL por cliente en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(MAX(D.IMPORTETOTAL)-MIN(D.IMPORTETOTAL),2) AS VARIACION, "
      "ROUND(MIN(D.IMPORTETOTAL),2) AS MIN_TICKET, "
      "ROUND(MAX(D.IMPORTETOTAL),2) AS MAX_TICKET, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(*)>2 ORDER BY VARIACION DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Variabilidad compras",""),

    q("vx2_063", "Facturas con SERIE vacía o nula",
      "¿Hay facturas sin serie documental asignada?",
      "Facturas TIPO=13 con SERIE NULL o vacío.",
      "SELECT COUNT(*) AS N_SIN_SERIE, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND (SERIE IS NULL OR SERIE='')",
      "Ventas","Calidad","Alerta","Medio","Datos maestros",""),

    q("vx2_064", "Artículos más vendidos por familia",
      "¿Cuál es el artículo más vendido de cada familia?",
      "TOP 1 artículo por importe en cada familia para facturas TIPO=13.",
      "SELECT F.NOMBRE AS FAMILIA, A.NOMBRE AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_TOTAL "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY F.CODIGO, F.NOMBRE, A.CODIGO, A.NOMBRE "
      "ORDER BY F.NOMBRE, IMPORTE_TOTAL DESC LIMIT 30",
      "Ventas","Comercial","Producto","Medio","Top por familia",""),

    q("vx2_065", "Clientes con compras solo en un agente",
      "¿Qué clientes han comprado siempre con el mismo agente?",
      "Clientes con COUNT(DISTINCT CODAGENTE)=1 en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, MAX(D.CODAGENTE) AS AGENTE_UNICO, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT D.CODAGENTE)=1 "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Fidelidad agente",""),

    q("vx2_066", "Facturas con importe redondeado (múltiplo de 100)",
      "¿Hay facturas con importes exactamente redondos que puedan ser estimaciones?",
      "Facturas TIPO=13 donde IMPORTETOTAL es múltiplo exacto de 100.",
      "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>0 "
      "AND CAST(IMPORTETOTAL AS INTEGER) % 100 = 0 "
      "AND IMPORTETOTAL = CAST(IMPORTETOTAL AS INTEGER) "
      "ORDER BY IMPORTETOTAL DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Bajo","Importes redondos",""),

    q("vx2_067", "Distribución de clientes por número de artículos distintos comprados",
      "¿Cuántos artículos distintos compra cada cliente?",
      "COUNT(DISTINCT CODIGO) por cliente en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_ARTICULOS_DISTINTOS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Diversidad compras",""),

    q("vx2_068", "Facturas emitidas el último día del mes",
      "¿Hay concentración de facturas en el último día del mes?",
      "Facturas TIPO=13 donde el día es el último del mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_FACTURAS_ULTIMO_DIA, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "AND FECHA=DATE(FECHA,'start of month','+1 month','-1 day') "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 12",
      "Ventas","Finanzas","Operacional","Bajo","Concentración fin de mes",""),

    q("vx2_069", "Clientes con dirección de NULL duplicada",
      "¿Hay clientes distintos con el mismo NULL?",
      "Detecta emails duplicados en tabla CLIENTE.",
      "SELECT NULL, COUNT(*) AS N_CLIENTES "
      "FROM CLIENTE WHERE NULL IS NOT NULL AND NULL!='' "
      "GROUP BY 1 HAVING COUNT(*)>1 ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Medio","Duplicados NULL",""),

    q("vx2_070", "Ventas por provincia (PROVINCIA de CLIENTE)",
      "¿Qué provincias generan más ventas?",
      "Agrupa por PROVINCIA de CLIENTE para facturas TIPO=13.",
      "SELECT C.CP, COUNT(D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND C.CP IS NOT NULL AND C.CP!='' "
      "GROUP BY C.CP ORDER BY TOTAL DESC LIMIT 20",
      "Ventas","Marketing","Geográfico","Medio","Ventas por provincia",""),

    q("vx2_071", "Artículos con STOCKARTICULO cero pero con ventas recientes",
      "¿Hay artículos sin STOCKARTICULO que se han vendido recientemente?",
      "Artículos con STOCKARTICULO=0 en ESTALMACEN pero con ventas en los últimos 90 días.",
      "SELECT A.NOMBRE, COALESCE(A.STOCKARTICULO,0) AS STOCK_ACTUAL, "
      "COUNT(L.CODARTICULO) AS VENTAS_RECIENTES "
      "FROM ARTICULO A "
      " "
      "JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "WHERE COALESCE(A.STOCKARTICULO,0)<=0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "ORDER BY VENTAS_RECIENTES DESC LIMIT 20",
      "Ventas","Almacén","Alerta","Alto","Rotura de STOCKARTICULO",""),

    q("vx2_072", "Facturas con CODAGENTE diferente al agente habitual del cliente",
      "¿Hay facturas donde el agente no es el habitual del cliente?",
      "Compara CODAGENTE de la factura con el agente más frecuente del cliente.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.CODAGENTE AS AGENTE_FACTURA, "
      "H.AGENTE_HABITUAL, D.FECHA "
      "FROM DOCCAB D "
      "JOIN (SELECT CODCLIENTE, CODAGENTE AS AGENTE_HABITUAL "
      "FROM (SELECT CODCLIENTE, CODAGENTE, COUNT(*) AS N "
      "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE IS NOT NULL "
      "GROUP BY CODCLIENTE, CODAGENTE) "
      "GROUP BY CODCLIENTE HAVING MAX(N)) H ON H.CODCLIENTE=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.CODAGENTE!=H.AGENTE_HABITUAL "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas","Comercial","Operacional","Bajo","Cambio de agente",""),

    q("vx2_073", "Clientes con más de 1 NIF registrado",
      "¿Hay clientes con múltiples NIFs?",
      "Clientes en CLIENTE con más de un NIF distinto (posibles duplicados de cliente).",
      "SELECT COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL,'Sin nombre') AS NOMBRE, "
      "COUNT(DISTINCT NIF) AS N_NIFS "
      "FROM CLIENTE WHERE NIF IS NOT NULL AND NIF!='' "
      "GROUP BY CODIGO, NOMBRECOMERCIAL, RAZONSOCIAL "
      "HAVING COUNT(DISTINCT NIF)>1 ORDER BY N_NIFS DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Duplicados cliente",""),

    q("vx2_074", "Facturas con IMPORTETOTAL negativo",
      "¿Hay facturas con importe total negativo?",
      "Facturas TIPO=13 con IMPORTETOTAL<0. Pueden ser abonos mal clasificados.",
      "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL<0 "
      "ORDER BY IMPORTETOTAL ASC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Importes negativos",""),

    q("vx2_075", "Distribución de ventas por hora del día (últimos 30 días)",
      "¿A qué horas se emiten más facturas en el último mes?",
      "Agrupa por hora de FECHA en facturas TIPO=13 de los últimos 30 días.",
      "SELECT CAST(SUBSTR(FECHA,12,2) AS INTEGER) AS HORA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA>=DATE('now','-30 days') "
      "AND LENGTH(FECHA)>10 "
      "GROUP BY HORA ORDER BY HORA",
      "Ventas","Operaciones","Operacional","Bajo","Distribución horaria",""),

    q("vx2_076", "Clientes con compras en más de 3 series distintas",
      "¿Hay clientes con facturas en múltiples series documentales?",
      "COUNT(DISTINCT SERIE) por cliente en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT D.SERIE) AS N_SERIES, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.SERIE IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT D.SERIE)>1 "
      "ORDER BY N_SERIES DESC LIMIT 20",
      "Ventas","Finanzas","Operacional","Bajo","Series por cliente",""),

    q("vx2_077", "Artículos con mayor número de devoluciones",
      "¿Qué artículos aparecen más en abonos (TIPO=3)?",
      "COUNT de DOCLIN por artículo en documentos TIPO=3.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_DEVOLUCIONES, "
      "ROUND(SUM(ABS(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL))),2) AS IMPORTE_DEVUELTO "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=3 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_DEVOLUCIONES DESC LIMIT 20",
      "Ventas","Calidad","Producto","Medio","Devoluciones por artículo",""),

    q("vx2_078", "Facturas con IMPORTEBASE igual a IMPORTETOTAL (sin IVA)",
      "¿Hay facturas donde la base imponible es igual al total (IMPORTEIVA=0)?",
      "Facturas TIPO=13 donde IMPORTEBASE=IMPORTETOTAL. Pueden ser exentas de IMPORTEIVA.",
      "SELECT COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 "
      "AND ABS(IMPORTEBASE-IMPORTETOTAL)<0.01 AND IMPORTETOTAL>0",
      "Ventas","Finanzas","Operacional","Medio","Facturas exentas IMPORTEIVA",""),

    q("vx2_079", "Clientes con mayor tiempo entre primera y última compra",
      "¿Qué clientes llevan más tiempo siendo clientes?",
      "Diferencia en días entre MIN y MAX de FECHA por cliente en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "MIN(D.FECHA) AS PRIMERA_COMPRA, MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "CAST(JULIANDAY(MAX(D.FECHA))-JULIANDAY(MIN(D.FECHA)) AS INTEGER) AS DIAS_CLIENTE, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(*)>1 ORDER BY DIAS_CLIENTE DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Antigüedad clientes",""),

    q("vx2_080", "Facturas con CODCLIENTE igual a 0 o negativo",
      "¿Hay facturas con código de cliente inválido?",
      "Facturas TIPO=13 con CODCLIENTE<=0. Indican errores de datos.",
      "SELECT COUNT(*) AS N_INVALIDOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND (CODCLIENTE<=0 OR CODCLIENTE IS NULL)",
      "Ventas","Calidad","Alerta","Alto","Clientes inválidos",""),

    q("vx2_081", "Ventas por tipo de cliente (si existe campo TIPOCLIENTE)",
      "¿Cómo se distribuyen las ventas por tipo de cliente?",
      "Agrupa por TIPOCLIENTE de CLIENTE para facturas TIPO=13.",
      "SELECT NULL, COUNT(D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND NULL IS NOT NULL "
      "GROUP BY NULL ORDER BY TOTAL DESC",
      "Ventas","Comercial","Segmentación","Medio","Segmentación clientes",""),

    q("vx2_082", "Artículos con PRECIOVENTA de catálogo vs PRECIOVENTA de venta real",
      "¿Se venden los artículos al PRECIOVENTA de catálogo o con variaciones?",
      "Compara PRECIOVENTA de ARTICULO con AVG(PRECIOVENTA) en DOCLIN.",
      "SELECT A.NOMBRE, A.PRECIOVENTA AS PRECIO_CATALOGO, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_VENTA_REAL, "
      "ROUND(AVG(L.PRECIO)-A.PRECIOVENTA,2) AS DIFERENCIA "
      "FROM ARTICULO A JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "WHERE A.PRECIOVENTA>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOVENTA "
      "ORDER BY ABS(AVG(L.PRECIO)-A.PRECIOVENTA) DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","Desviación PRECIOVENTA catálogo",""),

    q("vx2_083", "Facturas con más de 1 agente en sus líneas",
      "¿Hay facturas donde las líneas tienen agentes distintos?",
      "Detecta inconsistencias de agente dentro de una misma factura.",
      "SELECT D.CODIGO, COUNT(DISTINCT D.CODAGENTE) AS N_AGENTES, D.FECHA "
      "FROM DOCCAB D WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODIGO, D.FECHA HAVING COUNT(DISTINCT D.CODAGENTE)>1 "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Bajo","Inconsistencia agente",""),

    q("vx2_084", "Clientes con compras en el mismo día que un abono",
      "¿Hay clientes que el mismo día tienen una factura y un abono?",
      "Detecta pares factura+abono del mismo cliente en la misma fecha.",
      "SELECT F.CODCLIENTE, F.FECHA, "
      "ROUND(F.IMPORTE_FACTURA,2) AS FACTURA, "
      "ROUND(A.IMPORTE_ABONO,2) AS ABONO "
      "FROM (SELECT CODCLIENTE, FECHA, SUM(IMPORTETOTAL) AS IMPORTE_FACTURA "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE, FECHA) F "
      "JOIN (SELECT CODCLIENTE, FECHA, SUM(ABS(IMPORTETOTAL)) AS IMPORTE_ABONO "
      "FROM DOCCAB WHERE TIPO=3 GROUP BY CODCLIENTE, FECHA) A "
      "ON F.CODCLIENTE=A.CODCLIENTE AND F.FECHA=A.FECHA "
      "ORDER BY F.FECHA DESC LIMIT 20",
      "Ventas","Finanzas","Alerta","Medio","Factura+abono mismo día",""),

    q("vx2_085", "Evolución del número de artículos distintos vendidos por mes",
      "¿Cómo varía la diversidad de productos vendidos cada mes?",
      "COUNT(DISTINCT CODIGO) por mes en facturas TIPO=13.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas","Comercial","Producto","Bajo","Diversidad productos",""),

    q("vx2_086", "Clientes con mayor número de artículos distintos comprados",
      "¿Qué clientes tienen la cartera de compras más diversa?",
      "COUNT(DISTINCT CODIGO) por cliente en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Diversidad compras",""),

    q("vx2_087", "Facturas con IMPORTETOTAL igual a IMPORTEBASE (sin IMPORTEIVA aplicado)",
      "¿Hay facturas donde no se ha aplicado IMPORTEIVA?",
      "Facturas TIPO=13 donde IMPORTETOTAL=IMPORTEBASE. Pueden ser exentas o errores.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>0 "
      "AND ABS(IMPORTETOTAL-IMPORTEBASE)<0.01 "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 12",
      "Ventas","Finanzas","Operacional","Medio","Facturas sin IMPORTEIVA",""),

    q("vx2_088", "Clientes con compras en más de 2 años distintos",
      "¿Qué clientes llevan comprando más de 2 años?",
      "COUNT(DISTINCT SUBSTR(FECHA,1,4)) por cliente en facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT SUBSTR(D.FECHA,1,4)) AS N_ANOS, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,4))>2 "
      "ORDER BY N_ANOS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Clientes longevos",""),

    q("vx2_089", "Artículos con mayor variación de cantidad vendida por mes",
      "¿Qué artículos tienen ventas más irregulares mes a mes?",
      "Desviación estándar de CANTIDAD por artículo en facturas TIPO=13.",
      "SELECT A.NOMBRE, COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_CON_VENTA, "
      "ROUND(SUM(L.CANTIDAD),2) AS CANTIDAD_TOTAL, "
      "ROUND(AVG(L.CANTIDAD),2) AS MEDIA_MENSUAL "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7))>3 "
      "ORDER BY CANTIDAD_TOTAL DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","Irregularidad ventas",""),

    q("vx2_090", "Facturas con CODAGENTE igual a CODCLIENTE (posible error)",
      "¿Hay facturas donde el código de agente coincide con el de cliente?",
      "Detecta posibles errores de entrada donde CODAGENTE=CODCLIENTE.",
      "SELECT CODIGO, CODCLIENTE, CODAGENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE=CODCLIENTE "
      "ORDER BY FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Medio","Error agente=cliente",""),

    q("vx2_091", "Ventas por NULL (si existe campo NULL en DOCCAB)",
      "¿Cómo se distribuyen las ventas por NULL?",
      "Agrupa por NULL de DOCCAB para facturas TIPO=13.",
      "SELECT COALESCE(NULL,'Sin NULL') AS NULL, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 "
      "GROUP BY NULL ORDER BY TOTAL DESC",
      "Ventas","Marketing","Segmentación","Medio","Ventas por NULL",""),

    q("vx2_092", "Clientes con compras en el mismo mes que su primera compra (aniversario)",
      "¿Qué clientes compran en el mismo mes de su aniversario?",
      "Clientes cuya primera compra fue en el mismo mes que el mes actual.",
      f"SELECT {_C} AS CLIENTE, MIN(D.FECHA) AS PRIMERA_COMPRA, "
      "COUNT(*) AS N_FACTURAS_ESTE_MES "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,6,2)=STRFTIME('%m','now') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING MIN(D.FECHA)<DATE('now','start of year') "
      "ORDER BY PRIMERA_COMPRA ASC LIMIT 20",
      "Ventas","Marketing","Cliente","Bajo","Aniversario clientes",""),

    q("vx2_093", "Artículos con PRECIOVENTA de venta superior a 1000 EUR",
      "¿Qué artículos tienen PRECIOVENTA unitario superior a 1000 EUR?",
      "Artículos en ARTICULO con PRECIOVENTA>1000.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE, "
      "ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN_UNITARIO "
      "FROM ARTICULO WHERE PRECIOVENTA>1000 "
      "ORDER BY PRECIOVENTA DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","Artículos premium",""),

    q("vx2_094", "Facturas con IMPORTETOTAL superior a la media más 3 desviaciones",
      "¿Hay facturas estadísticamente anómalas por importe?",
      "Facturas TIPO=13 con importe > media + 3*desviación estándar.",
      "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL > ("
      "SELECT AVG(IMPORTETOTAL)+3*(AVG(IMPORTETOTAL*IMPORTETOTAL)-AVG(IMPORTETOTAL)*AVG(IMPORTETOTAL)) "
      "FROM DOCCAB WHERE TIPO=13) "
      "ORDER BY IMPORTETOTAL DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Outliers importe",""),

    q("vx2_095", "Clientes con compras en todos los trimestres del año",
      "¿Qué clientes compran en los 4 trimestres del año?",
      "Clientes con facturas en Q1, Q2, Q3 y Q4 del año actual.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT "
      "CASE WHEN CAST(SUBSTR(D.FECHA,6,2) AS INTEGER)<=3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(D.FECHA,6,2) AS INTEGER)<=6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(D.FECHA,6,2) AS INTEGER)<=9 THEN 'Q3' "
      "ELSE 'Q4' END) AS N_TRIMESTRES "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT CASE WHEN CAST(SUBSTR(D.FECHA,6,2) AS INTEGER)<=3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(D.FECHA,6,2) AS INTEGER)<=6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(D.FECHA,6,2) AS INTEGER)<=9 THEN 'Q3' "
      "ELSE 'Q4' END)=4 "
      "ORDER BY N_TRIMESTRES DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Clientes constantes",""),

    q("vx2_096", "Facturas con líneas de artículos de familias distintas",
      "¿Qué facturas incluyen artículos de más de 3 familias distintas?",
      "Facturas TIPO=13 con COUNT(DISTINCT CODFAMILIA)>3 en sus líneas.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "COUNT(DISTINCT A.CODFAMILIA) AS N_FAMILIAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODIGO, D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.FECHA "
      "HAVING COUNT(DISTINCT A.CODFAMILIA)>3 "
      "ORDER BY N_FAMILIAS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","Facturas multifamilia",""),

    q("vx2_097", "Clientes con mayor ratio abonos/facturas",
      "¿Qué clientes tienen más devoluciones en proporción a sus compras?",
      "Ratio N_ABONOS/N_FACTURAS por cliente.",
      f"SELECT {_C} AS CLIENTE, "
      "COALESCE(A.N_ABONOS,0) AS N_ABONOS, F.N_FACTURAS, "
      "ROUND(COALESCE(A.N_ABONOS,0)*100.0/NULLIF(F.N_FACTURAS,0),2) AS RATIO_PCT "
      "FROM (SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) F "
      "LEFT JOIN (SELECT CODCLIENTE, COUNT(*) AS N_ABONOS FROM DOCCAB WHERE TIPO=3 GROUP BY CODCLIENTE) A "
      "ON F.CODCLIENTE=A.CODCLIENTE "
      "LEFT JOIN CLIENTE C ON F.CODCLIENTE=C.CODIGO "
      "WHERE F.N_FACTURAS>2 ORDER BY RATIO_PCT DESC LIMIT 20",
      "Ventas","Calidad","Cliente","Medio","Ratio devoluciones",""),

    q("vx2_098", "Artículos con mayor número de clientes distintos que los compran",
      "¿Qué artículos tienen la base de clientes más amplia?",
      "COUNT(DISTINCT CODCLIENTE) por artículo en facturas TIPO=13.",
      "SELECT A.NOMBRE, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES_DISTINTOS, "
      "COUNT(*) AS N_VENTAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_CLIENTES_DISTINTOS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","Alcance por artículo",""),

    q("vx2_099", "Facturas con IMPORTETOTAL igual a 0",
      "¿Hay facturas con importe total cero?",
      "Facturas TIPO=13 con IMPORTETOTAL=0. Pueden ser errores o servicios gratuitos.",
      "SELECT CODIGO, CODCLIENTE, FECHA, CODAGENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL=0 "
      "ORDER BY FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Alto","Facturas cero",""),

    q("vx2_100", "Clientes con mayor número de facturas en el último trimestre",
      "¿Qué clientes han sido más activos en el último trimestre?",
      "COUNT de facturas TIPO=13 por cliente en los últimos 90 días.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Clientes activos trimestre",""),

    q("vx2_101", "Artículos con mayor margen porcentual",
      "¿Qué artículos tienen mayor margen porcentual sobre el PRECIOCOSTE?",
      "Margen% = (PRECIOVENTA-PRECIOCOSTE)/PRECIOCOSTE*100 en ARTICULO.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE, "
      "ROUND((PRECIOVENTA-PRECIOCOSTE)*100.0/NULLIF(PRECIOCOSTE,0),2) AS MARGEN_PCT "
      "FROM ARTICULO WHERE PRECIOCOSTE>0 AND PRECIOVENTA>0 "
      "ORDER BY MARGEN_PCT DESC LIMIT 20",
      "Ventas","Finanzas","Producto","Medio","Margen porcentual",""),

    q("vx2_102", "Facturas con CODAGENTE que no existe en tabla de agentes",
      "¿Hay facturas con agentes huérfanos?",
      "Facturas TIPO=13 con CODAGENTE que no tiene registro en la tabla de agentes.",
      "SELECT D.CODIGO, D.CODAGENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL "
      "AND NOT EXISTS (SELECT 1 FROM AGENTES A WHERE A.CODIGO=D.CODAGENTE) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas","Calidad","Alerta","Medio","Agentes huérfanos",""),

    q("vx2_103", "Clientes con compras en el mes de diciembre (estacionalidad navideña)",
      "¿Qué clientes compran en diciembre?",
      "Clientes con facturas TIPO=13 en mes 12.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS_DICIEMBRE, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND CAST(SUBSTR(D.FECHA,6,2) AS INTEGER)=12 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY TOTAL DESC LIMIT 20",
      "Ventas","Comercial","Estacionalidad","Bajo","Ventas diciembre",""),

    q("vx2_104", "Artículos con STOCKARTICULO negativo",
      "¿Hay artículos con STOCKARTICULO negativo en almacén?",
      "Artículos en ESTALMACEN con STOCKARTICULO<0.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, '01' "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO<0 ORDER BY A.STOCKARTICULO ASC LIMIT 20",
      "Ventas","Almacén","Alerta","Alto","STOCKARTICULO negativo",""),

    q("vx2_105", "Facturas con IMPORTEIVA superior al 21% de IMPORTEBASE",
      "¿Hay facturas con IMPORTEIVA superior al tipo máximo legal (21%)?",
      "Facturas TIPO=13 donde IMPORTEIVA/IMPORTEBASE>0.21.",
      "SELECT CODIGO, ROUND(IMPORTEBASE,2) AS BASE, ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTEIVA*100.0/NULLIF(IMPORTEBASE,0),2) AS TIPO_IVA_REAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEBASE>0 AND IMPORTEIVA>0 "
      "AND IMPORTEIVA/IMPORTEBASE>0.21 "
      "ORDER BY TIPO_IVA_REAL DESC LIMIT 20",
      "Ventas","Finanzas","Alerta","Alto","IMPORTEIVA excesivo",""),

    q("vx2_106", "Clientes con mayor número de artículos distintos en una sola factura",
      "¿Qué facturas tienen más artículos distintos?",
      "MAX(COUNT(DISTINCT CODIGO)) por factura por cliente.",
      f"SELECT {_C} AS CLIENTE, D.CODIGO, D.FECHA, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODIGO, D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.FECHA "
      "ORDER BY N_ARTICULOS_DISTINTOS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","Diversidad por factura",""),

    q("vx2_107", "Evolución de clientes nuevos vs recurrentes por mes",
      "¿Cuántos clientes nuevos y recurrentes hay cada mes?",
      "Clasifica clientes por si es su primera factura del mes o ya tenían facturas anteriores.",
      "SELECT MES, "
      "SUM(CASE WHEN ES_NUEVO=1 THEN 1 ELSE 0 END) AS CLIENTES_NUEVOS, "
      "SUM(CASE WHEN ES_NUEVO=0 THEN 1 ELSE 0 END) AS CLIENTES_RECURRENTES "
      "FROM (SELECT CODCLIENTE, SUBSTR(FECHA,1,7) AS MES, "
      "CASE WHEN FECHA=MIN(FECHA) OVER (PARTITION BY CODCLIENTE) THEN 1 ELSE 0 END AS ES_NUEVO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL) "
      "GROUP BY MES ORDER BY MES DESC LIMIT 12",
      "Ventas","Comercial","KPI","Alto","Nuevos vs recurrentes",""),

    q("vx2_108", "Artículos con mayor número de proveedores distintos",
      "¿Qué artículos tienen más de un proveedor posible?",
      "COUNT(DISTINCT PROVEEDDEFECTO) por artículo en ARTICULO.",
      "SELECT NOMBRE, PROVEEDDEFECTO AS PROVEEDOR_DEFECTO "
      "FROM ARTICULO WHERE PROVEEDDEFECTO IS NOT NULL "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas","Compras","Producto","Bajo","Proveedores por artículo",""),

    q("vx2_109", "Facturas con CODCLIENTE repetido en el mismo día",
      "¿Hay clientes con más de una factura en el mismo día?",
      "Detecta clientes con múltiples facturas TIPO=13 en la misma fecha.",
      "SELECT CODCLIENTE, FECHA, COUNT(*) AS N_FACTURAS_DIA, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_DIA "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY CODCLIENTE, FECHA HAVING COUNT(*)>1 "
      "ORDER BY N_FACTURAS_DIA DESC LIMIT 20",
      "Ventas","Calidad","Operacional","Bajo","Múltiples facturas mismo día",""),

    q("vx2_110", "Clientes con mayor porcentaje de descuento medio",
      "¿A qué clientes se les aplica más descuento de media?",
      "AVG(DESCUENTOS) en DOCLIN por cliente para facturas TIPO=13.",
      f"SELECT {_C} AS CLIENTE, ROUND(AVG(L.DESCUENTOS),2) AS DESCUENTO_MEDIO, "
      "COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS IS NOT NULL AND L.DESCUENTOS>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY DESCUENTO_MEDIO DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Descuentos por cliente",""),

    q("vx2_111", "Artículos con mayor número de líneas en abonos",
      "¿Qué artículos se devuelven más frecuentemente?",
      "COUNT de DOCLIN por artículo en documentos TIPO=3 (abonos).",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_ABONO "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=3 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_ABONO DESC LIMIT 20",
      "Ventas","Calidad","Producto","Medio","Artículos más devueltos",""),

    q("vx2_112", "Facturas con IMPORTETOTAL superior al doble de la media",
      "¿Hay facturas con importe más del doble de la media?",
      "Facturas TIPO=13 con IMPORTETOTAL > 2 * AVG(IMPORTETOTAL).",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL > "
      "(SELECT 2*AVG(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13) "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 20",
      "Ventas","Finanzas","Alerta","Medio","Facturas sobre media",""),

    q("vx2_113", "Clientes con compras solo en un agente en el último año",
      "¿Qué clientes han comprado exclusivamente con un agente en el último año?",
      "COUNT(DISTINCT CODAGENTE)=1 por cliente en facturas TIPO=13 del último año.",
      f"SELECT {_C} AS CLIENTE, MAX(D.CODAGENTE) AS AGENTE, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-365 days') "
      "AND D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT D.CODAGENTE)=1 "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Fidelidad agente anual",""),

    q("vx2_114", "Artículos con PRECIOVENTA de venta igual al PRECIOCOSTE (margen cero)",
      "¿Hay artículos que se venden sin margen?",
      "Artículos en ARTICULO donde PRECIOVENTA=PRECIOCOSTE.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE "
      "FROM ARTICULO WHERE PRECIOCOSTE>0 AND ABS(PRECIOVENTA-PRECIOCOSTE)<0.01 "
      "ORDER BY NOMBRE LIMIT 20",
      "Ventas","Finanzas","Alerta","Alto","Margen cero",""),

    q("vx2_115", "Facturas con CODAGENTE igual a 0 o negativo",
      "¿Hay facturas con código de agente inválido?",
      "Facturas TIPO=13 con CODAGENTE<=0.",
      "SELECT COUNT(*) AS N_INVALIDOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE IS NOT NULL AND CODAGENTE<=0",
      "Ventas","Calidad","Alerta","Medio","Agentes inválidos",""),

    q("vx2_116", "Clientes con mayor número de facturas en el mes actual",
      "¿Qué clientes han comprado más veces este mes?",
      "COUNT de facturas TIPO=13 por cliente en el mes actual.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","Clientes activos mes actual",""),

    q("vx2_117", "Artículos con mayor número de facturas distintas en las que aparecen",
      "¿En cuántas facturas distintas aparece cada artículo?",
      "COUNT(DISTINCT CODDOCUMENTO) por artículo en facturas TIPO=13.",
      "SELECT A.NOMBRE, COUNT(DISTINCT L.CODDOCUMENTO) AS N_FACTURAS_DISTINTAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_TOTAL "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_FACTURAS_DISTINTAS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","Presencia por artículo",""),

    q("vx2_118", "Facturas con IMPORTETOTAL inferior a la media menos 2 desviaciones",
      "¿Hay facturas estadísticamente anómalas por importe bajo?",
      "Facturas TIPO=13 con importe < media - 2*desviación estándar.",
      "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL > 0 AND IMPORTETOTAL < ("
      "SELECT AVG(IMPORTETOTAL)-2*(AVG(IMPORTETOTAL*IMPORTETOTAL)-AVG(IMPORTETOTAL)*AVG(IMPORTETOTAL)) "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>0) "
      "ORDER BY IMPORTETOTAL ASC LIMIT 20",
      "Ventas","Calidad","Alerta","Bajo","Outliers importe bajo",""),

    q("vx2_119", "Clientes con mayor número de artículos distintos en el último mes",
      "¿Qué clientes han comprado más variedad de artículos este mes?",
      "COUNT(DISTINCT CODIGO) por cliente en facturas TIPO=13 del último mes.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-30 days') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Diversidad compras recientes",""),

    q("vx2_120", "Artículos con mayor número de clientes distintos en el último trimestre",
      "¿Qué artículos tienen más demanda en el último trimestre?",
      "COUNT(DISTINCT CODCLIENTE) por artículo en facturas TIPO=13 de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "COUNT(*) AS N_VENTAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","Demanda reciente",""),

    q("vx2_121", "Facturas con IMPORTETOTAL entre 100 y 500 EUR (rango más frecuente)",
      "¿Cuántas facturas están en el rango de 100-500 EUR?",
      "Facturas TIPO=13 con IMPORTETOTAL entre 100 y 500.",
      "SELECT COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS MEDIA "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL BETWEEN 100 AND 500",
      "Ventas","Comercial","Operacional","Bajo","Rango medio facturas",""),

    q("vx2_122", "Clientes con mayor número de facturas en el año anterior",
      "¿Qué clientes fueron más activos el año pasado?",
      "COUNT de facturas TIPO=13 por cliente en el año anterior.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","Clientes activos año anterior",""),

    q("vx2_123", "Artículos con mayor número de líneas en el último mes",
      "¿Qué artículos se han vendido más veces este mes?",
      "COUNT de DOCLIN por artículo en facturas TIPO=13 del último mes.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-30 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","Artículos más vendidos mes",""),

    q("vx2_124", "Facturas con IMPORTETOTAL superior a 5000 EUR emitidas en el último mes",
      "¿Qué facturas grandes se han emitido este mes?",
      "Facturas TIPO=13 con IMPORTETOTAL>5000 en los últimos 30 días.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL>5000 AND D.FECHA>=DATE('now','-30 days') "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 20",
      "Ventas","Dirección","KPI","Alto","Facturas grandes recientes",""),

    q("vx2_125", "Resumen ejecutivo de ventas: KPIs principales en una sola consulta",
      "¿Cuál es el resumen ejecutivo de ventas?",
      "Combina en una sola consulta: total facturado, N facturas, ticket medio, "
      "N clientes activos, N artículos vendidos del año actual.",
      "SELECT "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURADO, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES_ACTIVOS, "
      "ROUND(MAX(IMPORTETOTAL),2) AS FACTURA_MAX "
      "FROM DOCCAB WHERE TIPO=13 "
      "AND SUBSTR(FECHA,1,4)=STRFTIME('%Y','now')",
      "Ventas","Dirección","KPI","Crítico","Resumen ejecutivo",""),

]
