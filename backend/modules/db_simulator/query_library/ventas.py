"""
query_library/ventas.py — 125 consultas extendidas de Ventas.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: ver reglas en DEVIA.md sección "Reglas de compatibilidad SQLite"
"""

from backend.modules.db_simulator.query_library.builder import q

_C = "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, CAST(D.CODCLIENTE AS TEXT))"

QUERIES_VENTAS_EXTENDED = [

    q("vx_001", "Facturación por día de la semana",
      "¿Qué días de la semana se emiten más facturas y por qué importe?",
      "Agrupa DOCCAB TIPO=13 por día de la semana (strftime('%w')). "
      "0=domingo, 1=lunes … 6=sábado. Permite detectar patrones de emisión.",
      "SELECT CASE CAST(strftime('%w',FECHA) AS INTEGER) "
      "WHEN 0 THEN 'Domingo' WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes' "
      "WHEN 3 THEN 'Miércoles' WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes' "
      "ELSE 'Sábado' END AS DIA, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY strftime('%w',FECHA) ORDER BY N_FACTURAS DESC",
      "Ventas","Comercial","KPI","Medio","Facturas por día",""),

    q("vx_002", "Facturación por hora del día",
      "¿A qué horas se emiten más facturas?",
      "Agrupa por hora de FECHA en DOCCAB TIPO=13. "
      "Útil para detectar si hay concentración de emisión en horarios concretos.",
      "SELECT CAST(strftime('%H',FECHA) AS INTEGER) AS HORA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY HORA ORDER BY HORA",
      "Ventas","Comercial","Operacional","Bajo","",""),

    q("vx_003", "Clientes con exactamente 1 factura (sin repetición)",
      "¿Qué clientes han comprado solo una vez?",
      "Clientes con COUNT(TIPO=13)=1. Son candidatos a acciones de fidelización "
      "o indican trabajos puntuales sin continuidad.",
      f"SELECT {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.CODCLIENTE IN "
      "(SELECT CODCLIENTE FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE HAVING COUNT(*)=1) "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 30",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_004", "Clientes con más de 10 facturas",
      "¿Qué clientes tienen más de 10 facturas emitidas?",
      "Clientes con alta frecuencia de compra. COUNT(TIPO=13)>10.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL, ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE HAVING COUNT(*)>10 "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Alto","",""),

    q("vx_005", "Facturación últimos 7 días",
      "¿Cuánto se ha facturado en los últimos 7 días?",
      "Suma IMPORTETOTAL de DOCCAB TIPO=13 con FECHA >= date('now','-7 days').",
      "SELECT COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_7D "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA >= date('now','-7 days')",
      "Ventas","Director","KPI","Crítico","Facturación 7d",""),

    q("vx_006", "Facturación últimos 30 días",
      "¿Cuánto se ha facturado en los últimos 30 días?",
      "Suma IMPORTETOTAL de DOCCAB TIPO=13 con FECHA >= date('now','-30 days').",
      "SELECT COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_30D "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA >= date('now','-30 days')",
      "Ventas","Director","KPI","Crítico","Facturación 30d",""),

    q("vx_007", "Facturación últimos 90 días",
      "¿Cuánto se ha facturado en los últimos 90 días?",
      "Suma IMPORTETOTAL de DOCCAB TIPO=13 con FECHA >= date('now','-90 days').",
      "SELECT COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_90D "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA >= date('now','-90 days')",
      "Ventas","Director","KPI","Alto","Facturación 90d",""),

    q("vx_008", "Comparativa mes actual vs mes anterior",
      "¿Cómo se compara la facturación del mes actual con el mes anterior?",
      "Compara SUM(IMPORTETOTAL) del mes actual (strftime('%Y-%m','now')) "
      "con el mes anterior (strftime('%Y-%m','now','-1 month')).",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,7)=strftime('%Y-%m','now') THEN IMPORTETOTAL ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,7)=strftime('%Y-%m','now','-1 month') THEN IMPORTETOTAL ELSE 0 END),2) AS MES_ANTERIOR "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas","Director","KPI","Crítico","Comparativa mensual",""),

    q("vx_009", "Comparativa trimestre actual vs trimestre anterior",
      "¿Cómo se compara la facturación del trimestre actual con el anterior?",
      "Agrupa por trimestre usando CAST(strftime('%m',FECHA) AS INTEGER). "
      "Trimestre = (mes-1)/3 + 1.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "((CAST(SUBSTR(FECHA,6,2) AS INTEGER)-1)/3+1) AS TRIMESTRE, "
      "COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO, TRIMESTRE ORDER BY ANIO DESC, TRIMESTRE DESC LIMIT 8",
      "Ventas","Director","KPI","Alto","Comparativa trimestral",""),

    q("vx_010", "Facturación por agente y mes",
      "¿Cuánto factura cada comercial cada mes?",
      "Cruza CODAGENTE con SUBSTR(FECHA,1,7) en DOCCAB TIPO=13. "
      "CODAGENTE=0 significa sin agente asignado.",
      "SELECT COALESCE(CAST(CODAGENTE AS TEXT),'Sin agente') AS AGENTE, "
      "SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL AND CODAGENTE > 0 "
      "GROUP BY CODAGENTE, SUBSTR(FECHA,1,7) ORDER BY MES DESC, TOTAL DESC LIMIT 50",
      "Ventas","Director","KPI","Alto","Facturación por agente",""),

    q("vx_011", "Clientes sin factura en los últimos 180 días",
      "¿Qué clientes no han comprado en los últimos 6 meses?",
      "Clientes con MAX(FECHA) < date('now','-180 days') en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "CAST(JULIANDAY('now')-JULIANDAY(MAX(D.FECHA)) AS INTEGER) AS DIAS_SIN_COMPRA "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING MAX(D.FECHA) < date('now','-180 days') "
      "ORDER BY DIAS_SIN_COMPRA DESC LIMIT 30",
      "Ventas","Comercial","Riesgo","Alto","",""),

    q("vx_012", "Clientes sin factura en los últimos 365 días",
      "¿Qué clientes no han comprado en el último año?",
      "Clientes con MAX(FECHA) < date('now','-365 days') en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "CAST(JULIANDAY('now')-JULIANDAY(MAX(D.FECHA)) AS INTEGER) AS DIAS_SIN_COMPRA "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING MAX(D.FECHA) < date('now','-365 days') "
      "ORDER BY DIAS_SIN_COMPRA DESC LIMIT 30",
      "Ventas","Comercial","Riesgo","Crítico","",""),

    q("vx_013", "Clientes con primera compra este mes",
      "¿Qué clientes han comprado por primera vez este mes?",
      "Clientes cuya MIN(FECHA) en DOCCAB TIPO=13 es del mes actual.",
      f"SELECT {_C} AS CLIENTE, "
      "MIN(D.FECHA) AS PRIMERA_COMPRA, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING SUBSTR(MIN(D.FECHA),1,7)=strftime('%Y-%m','now') "
      "ORDER BY PRIMERA_COMPRA DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_014", "Clientes con primera compra este año",
      "¿Qué clientes han comprado por primera vez este año?",
      "Clientes cuya MIN(FECHA) en DOCCAB TIPO=13 es del año actual.",
      f"SELECT {_C} AS CLIENTE, "
      "MIN(D.FECHA) AS PRIMERA_COMPRA, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING SUBSTR(MIN(D.FECHA),1,4)=strftime('%Y','now') "
      "ORDER BY PRIMERA_COMPRA DESC LIMIT 30",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_015", "Importe máximo facturado en un solo documento",
      "¿Cuál es la factura de mayor importe?",
      "MAX(IMPORTETOTAL) en DOCCAB TIPO=13. Identifica el trabajo de mayor valor.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 ORDER BY D.IMPORTETOTAL DESC LIMIT 10",
      "Ventas","Director","KPI","Medio","Factura máxima",""),

    q("vx_016", "Importe mínimo facturado en un solo documento",
      "¿Cuál es la factura de menor importe (excluyendo cero)?",
      "MIN(IMPORTETOTAL) > 0 en DOCCAB TIPO=13. Identifica trabajos de muy bajo valor.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL > 0 ORDER BY D.IMPORTETOTAL ASC LIMIT 10",
      "Ventas","Comercial","Operacional","Bajo","",""),

    q("vx_017", "Distribución de facturas por rango de importe",
      "¿Cómo se distribuyen las facturas por tamaño?",
      "Agrupa DOCCAB TIPO=13 en rangos de importe. "
      "Permite ver si el negocio depende de trabajos grandes o pequeños.",
      "SELECT CASE WHEN IMPORTETOTAL<100 THEN '<100€' "
      "WHEN IMPORTETOTAL<500 THEN '100-500€' "
      "WHEN IMPORTETOTAL<1000 THEN '500-1k€' "
      "WHEN IMPORTETOTAL<5000 THEN '1k-5k€' "
      "WHEN IMPORTETOTAL<10000 THEN '5k-10k€' "
      "ELSE '>10k€' END AS RANGO, "
      "COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY RANGO ORDER BY MIN(IMPORTETOTAL)",
      "Ventas","Director","KPI","Medio","",""),

    q("vx_018", "Facturas con importe superior a 10.000€",
      "¿Qué facturas superan los 10.000€?",
      "DOCCAB TIPO=13 con IMPORTETOTAL > 10000. Son los trabajos de mayor envergadura.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL > 10000 ORDER BY D.IMPORTETOTAL DESC LIMIT 30",
      "Ventas","Director","KPI","Alto","",""),

    q("vx_019", "Facturas con importe inferior a 100€",
      "¿Qué facturas tienen importe inferior a 100€?",
      "DOCCAB TIPO=13 con IMPORTETOTAL < 100 y > 0. "
      "Facturas de muy bajo importe pueden tener PRECIOCOSTE administrativo superior al beneficio.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL < 100 AND D.IMPORTETOTAL > 0 "
      "ORDER BY D.IMPORTETOTAL ASC LIMIT 30",
      "Ventas","Administrativo","Operacional","Bajo","",""),

    q("vx_020", "Número de facturas por cliente (histograma)",
      "¿Cuántas facturas tiene cada cliente en total?",
      "Histograma de frecuencia de compra por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE ORDER BY N_FACTURAS DESC LIMIT 40",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_021", "Clientes con mayor crecimiento interanual",
      "¿Qué clientes han aumentado más su facturación respecto al año anterior?",
      "Compara SUM(IMPORTETOTAL) del año actual vs año anterior por cliente. "
      "Solo incluye clientes con datos en ambos años.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=strftime('%Y','now') THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANIO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(CAST(strftime('%Y','now') AS INTEGER)-1 AS TEXT) THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANIO_ANTERIOR "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING ANIO_ACTUAL > 0 AND ANIO_ANTERIOR > 0 "
      "ORDER BY (ANIO_ACTUAL - ANIO_ANTERIOR) DESC LIMIT 20",
      "Ventas","Director","Predicción","Alto","",""),

    q("vx_022", "Clientes con mayor caída interanual",
      "¿Qué clientes han reducido más su facturación respecto al año anterior?",
      "Compara SUM(IMPORTETOTAL) del año actual vs año anterior. "
      "Solo incluye clientes con datos en ambos años.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=strftime('%Y','now') THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANIO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(CAST(strftime('%Y','now') AS INTEGER)-1 AS TEXT) THEN D.IMPORTETOTAL ELSE 0 END),2) AS ANIO_ANTERIOR "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING ANIO_ACTUAL > 0 AND ANIO_ANTERIOR > 0 "
      "ORDER BY (ANIO_ACTUAL - ANIO_ANTERIOR) ASC LIMIT 20",
      "Ventas","Director","Riesgo","Alto","",""),

    q("vx_023", "Presupuestos emitidos este mes",
      "¿Cuántos presupuestos se han emitido este mes?",
      "COUNT y SUM de DOCCAB TIPO=0 con FECHA del mes actual.",
      "SELECT COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=0 AND SUBSTR(FECHA,1,7)=strftime('%Y-%m','now')",
      "Ventas","Comercial","KPI","Medio","Presupuestos mes",""),

    q("vx_024", "Presupuestos emitidos este año",
      "¿Cuántos presupuestos se han emitido este año?",
      "COUNT y SUM de DOCCAB TIPO=0 con FECHA del año actual.",
      "SELECT COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=0 AND SUBSTR(FECHA,1,4)=strftime('%Y','now')",
      "Ventas","Comercial","KPI","Medio","Presupuestos año",""),

    q("vx_025", "Ratio presupuestos/facturas por mes",
      "¿Cuántos presupuestos se emiten por cada factura?",
      "Compara COUNT de TIPO=0 vs TIPO=13 por mes. "
      "Un ratio alto indica muchos presupuestos sin convertir.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "SUM(CASE WHEN TIPO=0 THEN 1 ELSE 0 END) AS N_PRESUPUESTOS, "
      "SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END) AS N_FACTURAS, "
      "CASE WHEN SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END)>0 "
      "THEN ROUND(CAST(SUM(CASE WHEN TIPO=0 THEN 1 ELSE 0 END) AS REAL)/"
      "SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END),2) ELSE NULL END AS RATIO "
      "FROM DOCCAB WHERE TIPO IN (0,13) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 12",
      "Ventas","Director","KPI","Alto","Ratio presupuestos",""),

    q("vx_026", "Presupuestos con importe superior a 5.000€",
      "¿Qué presupuestos superan los 5.000€?",
      "DOCCAB TIPO=0 con IMPORTETOTAL > 5000. Son los proyectos de mayor envergadura en pipeline.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_PENDIENTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=0 AND D.IMPORTETOTAL > 5000 ORDER BY D.IMPORTETOTAL DESC LIMIT 20",
      "Ventas","Director","KPI","Alto","",""),

    q("vx_027", "Presupuestos convertidos en factura (últimos 90 días)",
      "¿Qué presupuestos recientes se han convertido en factura?",
      "Presupuestos TIPO=0 de los últimos 90 días que tienen líneas con CODDOCUMENTOORIGEN.",
      "SELECT COUNT(DISTINCT D.CODIGO) AS TOTAL_PRESUPUESTOS, "
      "COUNT(DISTINCT L.CODDOCUMENTOORIGEN) AS CONVERTIDOS, "
      "ROUND(100.0*COUNT(DISTINCT L.CODDOCUMENTOORIGEN)/COUNT(DISTINCT D.CODIGO),1) AS PCT_CONVERSION "
      "FROM DOCCAB D LEFT JOIN DOCLIN L ON L.CODDOCUMENTOORIGEN=D.CODIGO "
      "WHERE D.TIPO=0 AND D.FECHA >= date('now','-90 days')",
      "Ventas","Director","KPI","Alto","Tasa conversión",""),

    q("vx_028", "Albaranes emitidos este mes",
      "¿Cuántos albaranes se han emitido este mes?",
      "COUNT y SUM de DOCCAB TIPO=11 con FECHA del mes actual.",
      "SELECT COUNT(*) AS N_ALBARANES, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=11 AND SUBSTR(FECHA,1,7)=strftime('%Y-%m','now')",
      "Ventas","Administrativo","Operacional","Medio","",""),

    q("vx_029", "Albaranes sin facturar con más de 15 días",
      "¿Qué albaranes llevan más de 15 días sin facturar?",
      "DOCCAB TIPO=11 con FECHA < date('now','-15 days'). "
      "Representan trabajo entregado pendiente de facturación.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=11 AND D.FECHA < date('now','-15 days') "
      "ORDER BY DIAS DESC LIMIT 30",
      "Ventas","Administrativo","Riesgo","Alto","",""),

    q("vx_030", "Líneas de venta por artículo y mes",
      "¿Cuántas unidades de cada artículo se venden cada mes?",
      "Agrupa DOCLIN (JOIN DOCCAB TIPO=13) por CODIGO y mes. "
      "Permite detectar artículos con ventas estacionales.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS CANTIDAD, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.FECHA IS NOT NULL "
      "GROUP BY L.CODARTICULO, SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC, IMPORTE DESC LIMIT 50",
      "Ventas","Comercial","Producto","Medio","",""),

    q("vx_031", "Top 10 artículos más vendidos este mes",
      "¿Qué artículos se han vendido más este mes?",
      "Ranking de artículos por importe en DOCLIN JOIN DOCCAB TIPO=13 del mes actual.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS CANTIDAD, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE DESC LIMIT 10",
      "Ventas","Comercial","Producto","Alto","",""),

    q("vx_032", "Top 10 artículos más vendidos este año",
      "¿Qué artículos se han vendido más este año?",
      "Ranking de artículos por importe en DOCLIN JOIN DOCCAB TIPO=13 del año actual.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS CANTIDAD, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE DESC LIMIT 10",
      "Ventas","Comercial","Producto","Alto","",""),

    q("vx_033", "Artículos vendidos solo una vez",
      "¿Qué artículos se han vendido en una sola factura?",
      "Artículos con COUNT(DISTINCT CODDOCUMENTO)=1 en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING COUNT(DISTINCT L.CODDOCUMENTO)=1 "
      "ORDER BY IMPORTE DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","",""),

    q("vx_034", "Artículos sin ventas en los últimos 90 días",
      "¿Qué artículos no se han vendido en los últimos 3 meses?",
      "Artículos en ARTICULO que no aparecen en DOCLIN JOIN DOCCAB TIPO=13 "
      "con FECHA >= date('now','-90 days').",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,A.CODIGO) AS ARTICULO, "
      "A.STOCKARTICULO AS STOCKARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A WHERE A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "WHERE D.FECHA >= date('now','-90 days') AND L.CODARTICULO IS NOT NULL) "
      "AND A.STOCKARTICULO > 0 ORDER BY A.STOCKARTICULO DESC LIMIT 30",
      "Ventas","Almacenero","Riesgo","Alto","",""),

    q("vx_035", "Ventas por familia de producto",
      "¿Qué familias de producto generan más ventas?",
      "Agrupa DOCLIN JOIN DOCCAB TIPO=13 JOIN ARTICULO por CODFAMILIA.",
      "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY A.CODFAMILIA ORDER BY IMPORTE DESC LIMIT 20",
      "Ventas","Director","Producto","Alto","",""),

    q("vx_036", "Ventas por familia y mes",
      "¿Cómo evolucionan las ventas de cada familia mes a mes?",
      "Cruza CODFAMILIA con SUBSTR(FECHA,1,7) en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
      "SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "WHERE D.FECHA IS NOT NULL "
      "GROUP BY A.CODFAMILIA, SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC, IMPORTE DESC LIMIT 60",
      "Ventas","Director","Producto","Medio","",""),

    q("vx_037", "Clientes con compras en todas las familias",
      "¿Qué clientes compran artículos de todas las familias disponibles?",
      "Clientes con COUNT(DISTINCT CODFAMILIA) = total familias en ARTICULO.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT A.CODFAMILIA) AS N_FAMILIAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "ORDER BY N_FAMILIAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_038", "Clientes que solo compran una familia",
      "¿Qué clientes compran artículos de una sola familia?",
      "Clientes con COUNT(DISTINCT CODFAMILIA)=1 en DOCLIN JOIN DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA_UNICA, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT A.CODFAMILIA)=1 "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_039", "PRECIOVENTA medio de venta por artículo",
      "¿A qué PRECIOVENTA medio se vende cada artículo?",
      "AVG(PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=13 por artículo. "
      "Compara con PRECIOVENTA en ARTICULO para detectar desviaciones.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MEDIO_VENTA, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_CATALOGO, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL))-A.PRECIOVENTA,2) AS DIFERENCIA "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.PRECIOVENTA > 0 GROUP BY L.CODARTICULO "
      "ORDER BY ABS(DIFERENCIA) DESC LIMIT 20",
      "Ventas","Comercial","Calidad","Medio","",""),

    q("vx_040", "Artículos vendidos por debajo del PRECIOVENTA de catálogo",
      "¿Qué artículos se venden habitualmente por debajo de su PRECIOVENTA de catálogo?",
      "Artículos donde AVG(PRECIOVENTA en DOCLIN) < PRECIOVENTA en ARTICULO.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MEDIO_VENTA, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_CATALOGO, "
      "ROUND(100.0*(A.PRECIOVENTA-AVG(CAST(L.PRECIO AS REAL)))/A.PRECIOVENTA,1) AS PCT_DESCUENTO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.PRECIOVENTA > 0 GROUP BY L.CODARTICULO "
      "HAVING AVG(CAST(L.PRECIO AS REAL)) < A.PRECIOVENTA "
      "ORDER BY PCT_DESCUENTO DESC LIMIT 20",
      "Ventas","Director","Ahorro","Alto","",""),

    q("vx_041", "Artículos vendidos por encima del PRECIOVENTA de catálogo",
      "¿Qué artículos se venden por encima de su PRECIOVENTA de catálogo?",
      "Artículos donde AVG(PRECIOVENTA en DOCLIN) > PRECIOVENTA en ARTICULO.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MEDIO_VENTA, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_CATALOGO, "
      "ROUND(100.0*(AVG(CAST(L.PRECIO AS REAL))-A.PRECIOVENTA)/A.PRECIOVENTA,1) AS PCT_SOBRE_PRECIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.PRECIOVENTA > 0 GROUP BY L.CODARTICULO "
      "HAVING AVG(CAST(L.PRECIO AS REAL)) > A.PRECIOVENTA "
      "ORDER BY PCT_SOBRE_PRECIO DESC LIMIT 20",
      "Ventas","Director","Calidad","Medio","",""),

    q("vx_042", "Descuentos aplicados por agente",
      "¿Qué agentes aplican más descuentos?",
      "AVG(DESCUENTOS) en DOCCAB TIPO=13 por CODAGENTE. "
      "CODAGENTE=0 excluido (sin agente).",
      "SELECT COALESCE(CAST(CODAGENTE AS TEXT),'Sin agente') AS AGENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(COALESCE(DESCUENTOS,0)),2) AS DESCUENTO_MEDIO, "
      "ROUND(MAX(COALESCE(DESCUENTOS,0)),2) AS DESCUENTO_MAX "
      "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE > 0 "
      "GROUP BY CODAGENTE ORDER BY DESCUENTO_MEDIO DESC LIMIT 20",
      "Ventas","Director","Ahorro","Alto","",""),

    q("vx_043", "Facturas con descuento superior al 30%",
      "¿Qué facturas tienen un descuento superior al 30%?",
      "DOCCAB TIPO=13 con DESCUENTOS > 30.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, D.DESCUENTOS AS DESCUENTO_PCT "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.DESCUENTOS > 30 "
      "ORDER BY D.DESCUENTOS DESC LIMIT 30",
      "Ventas","Director","Riesgo","Alto","",""),

    q("vx_044", "Facturas sin descuento aplicado",
      "¿Qué porcentaje de facturas no tienen descuento?",
      "COUNT de DOCCAB TIPO=13 con DESCUENTOS=0 o NULL vs total.",
      "SELECT "
      "SUM(CASE WHEN COALESCE(DESCUENTOS,0)=0 THEN 1 ELSE 0 END) AS SIN_DESCUENTO, "
      "SUM(CASE WHEN COALESCE(DESCUENTOS,0)>0 THEN 1 ELSE 0 END) AS CON_DESCUENTO, "
      "COUNT(*) AS TOTAL, "
      "ROUND(100.0*SUM(CASE WHEN COALESCE(DESCUENTOS,0)=0 THEN 1 ELSE 0 END)/COUNT(*),1) AS PCT_SIN_DESCUENTO "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas","Comercial","Calidad","Bajo","",""),

    q("vx_045", "Clientes con mayor descuento medio recibido",
      "¿Qué clientes reciben los mayores descuentos en sus facturas?",
      "AVG(DESCUENTOS) en DOCCAB TIPO=13 por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(COALESCE(D.DESCUENTOS,0)),2) AS DESCUENTO_MEDIO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "ORDER BY DESCUENTO_MEDIO DESC LIMIT 20",
      "Ventas","Director","Ahorro","Alto","",""),

    q("vx_046", "Número de líneas por factura (media y distribución)",
      "¿Cuántas líneas tiene de media cada factura?",
      "AVG(COUNT(DOCLIN)) por DOCCAB TIPO=13. "
      "Facturas con pocas líneas pueden ser servicios; con muchas, instalaciones.",
      "SELECT ROUND(AVG(N_LINEAS),2) AS MEDIA_LINEAS, "
      "MIN(N_LINEAS) AS MIN_LINEAS, MAX(N_LINEAS) AS MAX_LINEAS "
      "FROM (SELECT D.CODIGO, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCCAB D LEFT JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODIGO)",
      "Ventas","Comercial","Operacional","Bajo","",""),

    q("vx_047", "Facturas con más de 10 líneas",
      "¿Qué facturas tienen más de 10 líneas de detalle?",
      "DOCCAB TIPO=13 con COUNT(DOCLIN) > 10. Son instalaciones o proyectos complejos.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "LEFT JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODIGO "
      "HAVING COUNT(L.CODARTICULO) > 10 ORDER BY N_LINEAS DESC LIMIT 20",
      "Ventas","Comercial","Operacional","Bajo","",""),

    q("vx_048", "Facturas sin líneas de detalle",
      "¿Qué facturas no tienen ninguna línea de detalle?",
      "DOCCAB TIPO=13 sin registros en DOCLIN. Son cabeceras huérfanas.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.CODIGO NOT IN (SELECT DISTINCT CODDOCUMENTO FROM DOCLIN) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas","Administrativo","Calidad","Alto","",""),

    q("vx_049", "Clientes con facturas en todos los meses del año actual",
      "¿Qué clientes han comprado en todos los meses del año actual?",
      "Clientes con COUNT(DISTINCT SUBSTR(FECHA,1,7)) = número de meses transcurridos.",
      f"SELECT {_C} AS CLIENTE, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_CON_COMPRA, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) >= CAST(strftime('%m','now') AS INTEGER) "
      "ORDER BY TOTAL DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_050", "Clientes con compras solo en un mes del año",
      "¿Qué clientes solo han comprado en un mes del año actual?",
      "Clientes con COUNT(DISTINCT SUBSTR(FECHA,1,7))=1 en DOCCAB TIPO=13 del año actual.",
      f"SELECT {_C} AS CLIENTE, "
      "MIN(SUBSTR(D.FECHA,1,7)) AS MES_COMPRA, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7))=1 "
      "ORDER BY TOTAL DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","",""),

    q("vx_051", "Facturación acumulada por semana del año",
      "¿Cómo evoluciona la facturación semana a semana?",
      "Agrupa DOCCAB TIPO=13 por semana del año (strftime('%W')).",
      "SELECT strftime('%Y',FECHA) AS ANIO, "
      "CAST(strftime('%W',FECHA) AS INTEGER) AS SEMANA, "
      "COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO, SEMANA ORDER BY ANIO DESC, SEMANA DESC LIMIT 52",
      "Ventas","Director","KPI","Medio","",""),

    q("vx_052", "Clientes con mayor número de presupuestos sin convertir",
      "¿Qué clientes tienen más presupuestos pendientes de convertir?",
      "Clientes con más DOCCAB TIPO=0 sin correspondencia en TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(D.CODIGO) AS N_PRESUPUESTOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_PIPELINE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=0 GROUP BY D.CODCLIENTE "
      "ORDER BY N_PRESUPUESTOS DESC LIMIT 20",
      "Ventas","Comercial","Riesgo","Alto","",""),

    q("vx_053", "Importe total en pipeline (presupuestos activos)",
      "¿Cuánto dinero hay en presupuestos pendientes de convertir?",
      "SUM(IMPORTETOTAL) de DOCCAB TIPO=0 con FECHA >= date('now','-60 days').",
      "SELECT COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS PIPELINE_TOTAL "
      "FROM DOCCAB WHERE TIPO=0 AND FECHA >= date('now','-60 days')",
      "Ventas","Director","KPI","Crítico","Pipeline",""),

    q("vx_054", "Clientes con mayor pipeline (presupuestos recientes)",
      "¿Qué clientes tienen más importe en presupuestos recientes?",
      "SUM(IMPORTETOTAL) de DOCCAB TIPO=0 con FECHA >= date('now','-60 days') por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(D.CODIGO) AS N_PRESUPUESTOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS PIPELINE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=0 AND D.FECHA >= date('now','-60 days') "
      "GROUP BY D.CODCLIENTE ORDER BY PIPELINE DESC LIMIT 20",
      "Ventas","Comercial","KPI","Alto","",""),

    q("vx_055", "Facturas emitidas en fin de semana",
      "¿Cuántas facturas se emiten en sábado o domingo?",
      "DOCCAB TIPO=13 con strftime('%w',FECHA) IN ('0','6').",
      "SELECT COUNT(*) AS N_FACTURAS_FDS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FDS "
      "FROM DOCCAB WHERE TIPO=13 AND strftime('%w',FECHA) IN ('0','6')",
      "Ventas","Administrativo","Calidad","Bajo","",""),

    q("vx_056", "Facturas con fecha futura (error de datos)",
      "¿Hay facturas con fecha posterior a hoy?",
      "DOCCAB TIPO=13 con FECHA > date('now'). Son errores de entrada de datos.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA > date('now') ORDER BY D.FECHA ASC LIMIT 20",
      "Ventas","Administrativo","Calidad","Crítico","",""),

    q("vx_057", "Facturas con fecha anterior a 2020 (posible error)",
      "¿Hay facturas con fecha anterior a 2020?",
      "DOCCAB TIPO=13 con FECHA < '2020-01-01'. Pueden ser errores de importación.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA < '2020-01-01' ORDER BY D.FECHA ASC LIMIT 20",
      "Ventas","Administrativo","Calidad","Medio","",""),

    q("vx_058", "Clientes con facturas en más de 3 años distintos",
      "¿Qué clientes llevan más de 3 años comprando?",
      "Clientes con COUNT(DISTINCT SUBSTR(FECHA,1,4)) > 3 en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,4)) AS ANIOS_ACTIVO, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_HISTORICO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,4)) > 3 "
      "ORDER BY ANIOS_ACTIVO DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_059", "Clientes con facturas en un solo año",
      "¿Qué clientes solo han comprado en un año?",
      "Clientes con COUNT(DISTINCT SUBSTR(FECHA,1,4))=1 en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "MIN(SUBSTR(D.FECHA,1,4)) AS ANIO_COMPRA, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,4))=1 "
      "ORDER BY TOTAL DESC LIMIT 30",
      "Ventas","Comercial","Cliente","Bajo","",""),

    q("vx_060", "Facturación por código postal del cliente",
      "¿Qué zonas geográficas generan más facturación?",
      "Agrupa por CP de CLIENTE JOIN DOCCAB TIPO=13.",
      f"SELECT COALESCE(C.CP,'Sin CP') AS CP, "
      "COUNT(D.CODIGO) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY C.CP ORDER BY TOTAL DESC LIMIT 20",
      "Ventas","Director","Estratégico","Medio","",""),

    q("vx_061", "Clientes con teléfono registrado",
      "¿Qué porcentaje de clientes tienen teléfono registrado?",
      "COUNT de CLIENTE con TEL no nulo vs total.",
      "SELECT COUNT(*) AS TOTAL_CLIENTES, "
      "SUM(CASE WHEN TEL IS NOT NULL AND TEL!='' THEN 1 ELSE 0 END) AS CON_TELEFONO, "
      "ROUND(100.0*SUM(CASE WHEN TEL IS NOT NULL AND TEL!='' THEN 1 ELSE 0 END)/COUNT(*),1) AS PCT "
      "FROM CLIENTE",
      "Ventas","Comercial","Calidad","Bajo","",""),

    q("vx_062", "Clientes dados de baja con facturas recientes",
      "¿Hay clientes dados de baja que tienen facturas recientes?",
      "CLIENTE con BAJA=1 que aparecen en DOCCAB TIPO=13 con FECHA reciente.",
      f"SELECT {_C} AS CLIENTE, MAX(D.FECHA) AS ULTIMA_FACTURA, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND C.BAJA=1 "
      "GROUP BY D.CODCLIENTE ORDER BY ULTIMA_FACTURA DESC LIMIT 20",
      "Ventas","Administrativo","Calidad","Alto","",""),

    q("vx_063", "Clientes sin ninguna factura emitida",
      "¿Qué clientes del maestro no tienen ninguna factura?",
      "CLIENTE que no aparecen en DOCCAB TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL,C.RAZONSOCIAL,CAST(C.CODIGO AS TEXT)) AS CLIENTE "
      "FROM CLIENTE C WHERE C.CODIGO NOT IN "
      "(SELECT DISTINCT CODCLIENTE FROM DOCCAB WHERE TIPO=13 AND CODCLIENTE IS NOT NULL) "
      "AND (C.BAJA IS NULL OR C.BAJA!=1) LIMIT 30",
      "Ventas","Comercial","Calidad","Medio","",""),

    q("vx_064", "Facturas con CODAGENTE=0 (sin agente asignado)",
      "¿Cuántas facturas no tienen agente asignado?",
      "DOCCAB TIPO=13 con CODAGENTE=0 o NULL. "
      "Estas facturas no se atribuyen a ningún comercial.",
      "SELECT COUNT(*) AS N_SIN_AGENTE, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_SIN_AGENTE "
      "FROM DOCCAB WHERE TIPO=13 AND (CODAGENTE=0 OR CODAGENTE IS NULL)",
      "Ventas","Director","Calidad","Alto","",""),

    q("vx_065", "Facturas con CODFORMAPAGO vacío",
      "¿Cuántas facturas no tienen forma de pago asignada?",
      "DOCCAB TIPO=13 con CODFORMAPAGO NULL o vacío.",
      "SELECT COUNT(*) AS N_SIN_FORMAPAGO, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND (CODFORMAPAGO IS NULL OR CODFORMAPAGO='')",
      "Ventas","Administrativo","Calidad","Medio","",""),

    q("vx_066", "Distribución de facturas por forma de pago y mes",
      "¿Cómo evoluciona el uso de cada forma de pago mes a mes?",
      "Cruza CODFORMAPAGO con SUBSTR(FECHA,1,7) en DOCCAB TIPO=13.",
      "SELECT COALESCE(CODFORMAPAGO,'Sin forma pago') AS FORMA_PAGO, "
      "SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY CODFORMAPAGO, SUBSTR(FECHA,1,7) ORDER BY MES DESC, TOTAL DESC LIMIT 50",
      "Ventas","Administrativo","Financiero","Medio","",""),

    q("vx_067", "Clientes con mayor número de albaranes",
      "¿Qué clientes tienen más albaranes emitidos?",
      "COUNT de DOCCAB TIPO=11 por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_ALBARANES, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=11 GROUP BY D.CODCLIENTE ORDER BY N_ALBARANES DESC LIMIT 20",
      "Ventas","Comercial","Operacional","Bajo","",""),

    q("vx_068", "Clientes con albaranes pero sin facturas",
      "¿Qué clientes tienen albaranes pero ninguna factura?",
      "Clientes en DOCCAB TIPO=11 que no aparecen en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(D.CODIGO) AS N_ALBARANES, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_ALBARANES "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=11 AND D.CODCLIENTE NOT IN "
      "(SELECT DISTINCT CODCLIENTE FROM DOCCAB WHERE TIPO=13) "
      "GROUP BY D.CODCLIENTE ORDER BY TOTAL_ALBARANES DESC LIMIT 20",
      "Ventas","Administrativo","Riesgo","Alto","",""),

    q("vx_069", "Importe medio de presupuesto por cliente",
      "¿Cuál es el importe medio de los presupuestos de cada cliente?",
      "AVG(IMPORTETOTAL) de DOCCAB TIPO=0 por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_PRESUPUESTOS, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS IMPORTE_MEDIO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=0 GROUP BY D.CODCLIENTE ORDER BY IMPORTE_MEDIO DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_070", "Clientes con presupuesto pero sin factura nunca",
      "¿Qué clientes tienen presupuestos pero nunca han comprado?",
      "Clientes en DOCCAB TIPO=0 que no aparecen en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(D.CODIGO) AS N_PRESUPUESTOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_PRESUPUESTADO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=0 AND D.CODCLIENTE NOT IN "
      "(SELECT DISTINCT CODCLIENTE FROM DOCCAB WHERE TIPO=13) "
      "GROUP BY D.CODCLIENTE ORDER BY TOTAL_PRESUPUESTADO DESC LIMIT 20",
      "Ventas","Comercial","Riesgo","Alto","",""),

    q("vx_071", "Artículos con mayor margen de contribución",
      "¿Qué artículos generan más margen bruto en ventas?",
      "Calcula (PRECIOVENTA-PRECIOCOSTE)*CANTIDAD por artículo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*(CAST(L.PRECIO AS REAL)-A.PRECIOCOSTE)),2) AS MARGEN_TOTAL, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS VENTAS_TOTAL "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.PRECIOCOSTE > 0 GROUP BY L.CODARTICULO "
      "ORDER BY MARGEN_TOTAL DESC LIMIT 20",
      "Ventas","Director","Financiero","Alto","",""),

    q("vx_072", "Artículos con margen negativo en ventas",
      "¿Qué artículos se venden por debajo de su PRECIOCOSTE?",
      "Artículos donde AVG(PRECIOVENTA en DOCLIN) < PRECIOCOSTE en ARTICULO.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL)),2) AS PRECIO_VENTA_MEDIO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL))-A.PRECIOCOSTE,2) AS MARGEN "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.PRECIOCOSTE > 0 GROUP BY L.CODARTICULO "
      "HAVING AVG(CAST(L.PRECIO AS REAL)) < A.PRECIOCOSTE "
      "ORDER BY MARGEN ASC LIMIT 20",
      "Ventas","Director","Riesgo","Crítico","",""),

    q("vx_073", "Clientes con mayor margen generado",
      "¿Qué clientes generan más margen bruto?",
      "Suma (PRECIOVENTA-PRECIOCOSTE)*CANTIDAD por cliente en DOCLIN JOIN DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*(CAST(L.PRECIO AS REAL)-A.PRECIOCOSTE)),2) AS MARGEN_TOTAL, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS VENTAS_TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE > 0 GROUP BY D.CODCLIENTE "
      "ORDER BY MARGEN_TOTAL DESC LIMIT 20",
      "Ventas","Director","Financiero","Alto","",""),

    q("vx_074", "Ventas de servicios vs productos físicos",
      "¿Qué porcentaje de las ventas son servicios vs productos físicos?",
      "Distingue artículos de servicio (STOCKARTICULO=0 y sin movimiento de STOCKARTICULO) "
      "de productos físicos.",
      "SELECT "
      "CASE WHEN A.STOCKARTICULO=0 THEN 'Servicio/Sin STOCKARTICULO' ELSE 'Producto físico' END AS TIPO_ARTICULO, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY TIPO_ARTICULO ORDER BY IMPORTE DESC",
      "Ventas","Director","Estratégico","Medio","",""),

    q("vx_075", "Clientes con compras en el último mes y en el mismo mes del año anterior",
      "¿Qué clientes compraron este mes y también en el mismo mes del año pasado?",
      "Clientes con facturas en SUBSTR(FECHA,1,7)=mes_actual Y en mismo mes año anterior.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') THEN D.IMPORTETOTAL ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y','now','-1 year')||SUBSTR(strftime('%Y-%m','now'),5) THEN D.IMPORTETOTAL ELSE 0 END),2) AS MISMO_MES_ANIO_ANTERIOR "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING MES_ACTUAL > 0 AND MISMO_MES_ANIO_ANTERIOR > 0 "
      "ORDER BY MES_ACTUAL DESC LIMIT 20",
      "Ventas","Director","Predicción","Medio","",""),

    q("vx_076", "Número de clientes únicos por mes",
      "¿Cuántos clientes distintos compran cada mes?",
      "COUNT(DISTINCT CODCLIENTE) en DOCCAB TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(DISTINCT CODCLIENTE) AS CLIENTES_UNICOS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas","Director","KPI","Alto","",""),

    q("vx_077", "Clientes con mayor frecuencia de compra (días entre compras)",
      "¿Qué clientes compran con más frecuencia?",
      "Calcula el intervalo medio entre compras por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND((JULIANDAY(MAX(D.FECHA))-JULIANDAY(MIN(D.FECHA)))/NULLIF(COUNT(*)-1,0),1) AS DIAS_ENTRE_COMPRAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE HAVING COUNT(*) > 2 "
      "ORDER BY DIAS_ENTRE_COMPRAS ASC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_078", "Clientes con mayor tiempo entre primera y última compra",
      "¿Qué clientes llevan más tiempo siendo clientes activos?",
      "Calcula JULIANDAY(MAX(FECHA))-JULIANDAY(MIN(FECHA)) por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, "
      "MIN(D.FECHA) AS PRIMERA_COMPRA, MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "CAST(JULIANDAY(MAX(D.FECHA))-JULIANDAY(MIN(D.FECHA)) AS INTEGER) AS DIAS_ACTIVO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "ORDER BY DIAS_ACTIVO DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","",""),

    q("vx_079", "Artículos con mayor número de clientes distintos",
      "¿Qué artículos se venden a más clientes distintos?",
      "COUNT(DISTINCT CODCLIENTE) por artículo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","",""),

    q("vx_080", "Artículos vendidos a un solo cliente",
      "¿Qué artículos solo se han vendido a un cliente?",
      "Artículos con COUNT(DISTINCT CODCLIENTE)=1 en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      f"{_C} AS CLIENTE_UNICO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "GROUP BY L.CODARTICULO HAVING COUNT(DISTINCT D.CODCLIENTE)=1 "
      "ORDER BY IMPORTE DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","",""),

    q("vx_081", "Facturas con IMPORTEIVA=0 (posibles exentas)",
      "¿Hay facturas con IMPORTEIVA igual a cero?",
      "DOCCAB TIPO=13 con IMPORTEIVA=0 o NULL. Pueden ser operaciones exentas o errores.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, ROUND(D.IMPORTEIVA,2) AS IMPORTEIVA "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND (D.IMPORTEIVA=0 OR D.IMPORTEIVA IS NULL) "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 20",
      "Ventas","Administrativo","Calidad","Alto","",""),

    q("vx_082", "Distribución de tipos de IMPORTEIVA aplicados",
      "¿Qué tipos de IMPORTEIVA se aplican en las facturas?",
      "Agrupa por porcentaje de IMPORTEIVA calculado (IMPORTEIVA/IMPORTEBASE*100) en DOCCAB TIPO=13.",
      "SELECT ROUND(100.0*IMPORTEIVA/NULLIF(IMPORTEBASE,0),0) AS PCT_IVA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEBASE > 0 "
      "GROUP BY PCT_IMPORTEIVA ORDER BY N_FACTURAS DESC LIMIT 10",
      "Ventas","Administrativo","Financiero","Medio","",""),

    q("vx_083", "Clientes con mayor variabilidad en importes de factura",
      "¿Qué clientes tienen mayor variación en el importe de sus facturas?",
      "Calcula MAX-MIN de IMPORTETOTAL por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(MIN(D.IMPORTETOTAL),2) AS MIN_FACTURA, "
      "ROUND(MAX(D.IMPORTETOTAL),2) AS MAX_FACTURA, "
      "ROUND(MAX(D.IMPORTETOTAL)-MIN(D.IMPORTETOTAL),2) AS RANGO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE HAVING COUNT(*) > 2 "
      "ORDER BY RANGO DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","",""),

    q("vx_084", "Facturas agrupadas por agente y forma de pago",
      "¿Qué formas de pago usa cada agente?",
      "Cruza CODAGENTE con CODFORMAPAGO en DOCCAB TIPO=13.",
      "SELECT COALESCE(CAST(CODAGENTE AS TEXT),'Sin agente') AS AGENTE, "
      "COALESCE(CODFORMAPAGO,'Sin forma pago') AS FORMA_PAGO, "
      "COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE > 0 "
      "GROUP BY CODAGENTE, CODFORMAPAGO ORDER BY AGENTE, TOTAL DESC LIMIT 40",
      "Ventas","Director","Operacional","Bajo","",""),

    q("vx_085", "Clientes con facturas en más de 2 agentes distintos",
      "¿Qué clientes han sido atendidos por más de 2 agentes distintos?",
      "COUNT(DISTINCT CODAGENTE) > 2 por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT D.CODAGENTE) AS N_AGENTES, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.CODAGENTE > 0 GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT D.CODAGENTE) > 2 ORDER BY N_AGENTES DESC LIMIT 20",
      "Ventas","Director","Calidad","Medio","",""),

    q("vx_086", "Artículos con PRECIOVENTA de venta igual a cero",
      "¿Hay artículos con PRECIOVENTA de venta cero en el catálogo?",
      "ARTICULO con PRECIOVENTA=0 o NULL. Pueden ser artículos de servicio o errores.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,A.CODIGO) AS ARTICULO, "
      "A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE A.PRECIOVENTA=0 OR A.PRECIOVENTA IS NULL LIMIT 20",
      "Ventas","Administrativo","Calidad","Medio","",""),

    q("vx_087", "Artículos con PRECIOVENTA de PRECIOCOSTE igual a cero",
      "¿Hay artículos con PRECIOVENTA de PRECIOCOSTE cero?",
      "ARTICULO con PRECIOCOSTE=0 o NULL. El margen no se puede calcular para estos.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,A.CODIGO) AS ARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE A.PRECIOCOSTE=0 OR A.PRECIOCOSTE IS NULL LIMIT 20",
      "Ventas","Administrativo","Calidad","Medio","",""),

    q("vx_088", "Clientes con mayor número de artículos distintos comprados",
      "¿Qué clientes compran más variedad de artículos?",
      "COUNT(DISTINCT CODIGO) por cliente en DOCLIN JOIN DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "ORDER BY N_ARTICULOS_DISTINTOS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_089", "Artículos más vendidos por familia",
      "¿Cuál es el artículo más vendido de cada familia?",
      "Ranking de artículos por importe dentro de cada familia en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
      "COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY A.CODFAMILIA, L.CODARTICULO "
      "ORDER BY A.CODFAMILIA, IMPORTE DESC LIMIT 40",
      "Ventas","Comercial","Producto","Medio","",""),

    q("vx_090", "Clientes con mayor número de presupuestos aceptados",
      "¿Qué clientes aceptan más presupuestos?",
      "Clientes con más DOCCAB TIPO=0 que tienen correspondencia en TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT D.CODIGO) AS N_PRESUPUESTOS_ACEPTADOS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "JOIN DOCLIN L ON L.CODDOCUMENTOORIGEN=D.CODIGO "
      "WHERE D.TIPO=0 GROUP BY D.CODCLIENTE "
      "ORDER BY N_PRESUPUESTOS_ACEPTADOS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_091", "Facturas con IMPORTEBASE mayor que IMPORTETOTAL",
      "¿Hay facturas donde la base imponible supera el importe total?",
      "DOCCAB TIPO=13 con IMPORTEBASE > IMPORTETOTAL. Es un error de datos.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTEBASE,2) AS BASE, ROUND(D.IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTEBASE > D.IMPORTETOTAL LIMIT 20",
      "Ventas","Administrativo","Calidad","Crítico","",""),

    q("vx_092", "Facturas con IMPORTEIVA mayor que IMPORTEBASE",
      "¿Hay facturas donde el IMPORTEIVA supera la base imponible?",
      "DOCCAB TIPO=13 con IMPORTEIVA > IMPORTEBASE. Es un error de datos.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTEBASE,2) AS BASE, ROUND(D.IMPORTEIVA,2) AS IMPORTEIVA "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTEIVA > D.IMPORTEBASE LIMIT 20",
      "Ventas","Administrativo","Calidad","Crítico","",""),

    q("vx_093", "Clientes con mayor importe en un solo pedido",
      "¿Qué clientes han realizado el pedido de mayor importe?",
      "MAX(IMPORTETOTAL) por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, ROUND(MAX(D.IMPORTETOTAL),2) AS MAX_FACTURA, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS MEDIA_FACTURA "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE ORDER BY MAX_FACTURA DESC LIMIT 20",
      "Ventas","Director","KPI","Medio","",""),

    q("vx_094", "Artículos con mayor número de unidades vendidas",
      "¿Qué artículos se venden en mayor cantidad de unidades?",
      "SUM(CANTIDAD) por artículo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_VENDIDAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_VENDIDAS DESC LIMIT 20",
      "Ventas","Almacenero","Producto","Medio","",""),

    q("vx_095", "Artículos con mayor PRECIOVENTA unitario vendido",
      "¿Qué artículos tienen el PRECIOVENTA unitario más alto en ventas?",
      "MAX(PRECIOVENTA) por artículo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(MAX(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MAX, "
      "ROUND(MIN(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MIN, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MEDIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY PRECIO_MAX DESC LIMIT 20",
      "Ventas","Comercial","Producto","Bajo","",""),

    q("vx_096", "Clientes con facturas en el mismo día del mes",
      "¿Hay clientes que siempre facturan el mismo día del mes?",
      "Detecta clientes con COUNT(DISTINCT CAST(strftime('%d',FECHA) AS INTEGER))=1.",
      f"SELECT {_C} AS CLIENTE, "
      "CAST(strftime('%d',MIN(D.FECHA)) AS INTEGER) AS DIA_MES, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT CAST(strftime('%d',D.FECHA) AS INTEGER))=1 AND COUNT(*)>2 "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","",""),

    q("vx_097", "Facturas con CODCLIENTE no existente en maestro",
      "¿Hay facturas con un código de cliente que no existe en el maestro?",
      "DOCCAB TIPO=13 con CODCLIENTE no presente en CLIENTE.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D WHERE D.TIPO=13 AND D.CODCLIENTE NOT IN "
      "(SELECT CODIGO FROM CLIENTE) LIMIT 20",
      "Ventas","Administrativo","Calidad","Alto","",""),

    q("vx_098", "Artículos con CODFAMILIA no existente en maestro",
      "¿Hay artículos con familia que no existe en el maestro?",
      "ARTICULO con CODFAMILIA no presente en FAMILIA.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,A.CODIGO) AS ARTICULO, A.CODFAMILIA "
      "FROM ARTICULO A WHERE A.CODFAMILIA IS NOT NULL AND A.CODFAMILIA!='' "
      "AND A.CODFAMILIA NOT IN (SELECT CODIGO FROM FAMILIA) LIMIT 20",
      "Ventas","Administrativo","Calidad","Medio","",""),

    q("vx_099", "Clientes con mayor número de artículos distintos en una sola factura",
      "¿Qué facturas tienen más variedad de artículos?",
      "MAX(COUNT(DISTINCT CODIGO)) por factura en DOCLIN JOIN DOCCAB TIPO=13.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODIGO "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Ventas","Comercial","Operacional","Bajo","",""),

    q("vx_100", "Resumen ejecutivo de ventas (KPIs principales en una consulta)",
      "¿Cuál es el resumen de los KPIs de ventas más importantes?",
      "Combina en una sola consulta: total facturado, n facturas, ticket medio, "
      "n clientes activos, n artículos vendidos.",
      "SELECT "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURACION_TOTAL, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES_ACTIVOS, "
      "ROUND(MAX(IMPORTETOTAL),2) AS FACTURA_MAXIMA, "
      "ROUND(MIN(CASE WHEN IMPORTETOTAL>0 THEN IMPORTETOTAL END),2) AS FACTURA_MINIMA "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas","Director","KPI","Crítico","Resumen ventas",""),

    q("vx_101", "Clientes con compras en el último trimestre",
      "¿Qué clientes han comprado en los últimos 3 meses?",
      "Clientes con MAX(FECHA) >= date('now','-90 days') en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= date('now','-90 days') "
      "GROUP BY D.CODCLIENTE ORDER BY TOTAL DESC LIMIT 30",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_102", "Artículos con ventas crecientes (último mes vs mes anterior)",
      "¿Qué artículos han aumentado sus ventas respecto al mes anterior?",
      "Compara SUM(CANTIDAD*PRECIOVENTA) del mes actual vs mes anterior por artículo.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now','-1 month') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ANTERIOR "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING MES_ACTUAL > MES_ANTERIOR AND MES_ANTERIOR > 0 "
      "ORDER BY (MES_ACTUAL-MES_ANTERIOR) DESC LIMIT 20",
      "Ventas","Comercial","Predicción","Medio","",""),

    q("vx_103", "Artículos con ventas decrecientes (último mes vs mes anterior)",
      "¿Qué artículos han reducido sus ventas respecto al mes anterior?",
      "Compara SUM(CANTIDAD*PRECIOVENTA) del mes actual vs mes anterior por artículo.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now','-1 month') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ANTERIOR "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING MES_ACTUAL < MES_ANTERIOR AND MES_ACTUAL > 0 "
      "ORDER BY (MES_ANTERIOR-MES_ACTUAL) DESC LIMIT 20",
      "Ventas","Comercial","Riesgo","Medio","",""),

    q("vx_104", "Clientes con mayor número de líneas de detalle acumuladas",
      "¿Qué clientes tienen más líneas de detalle en sus facturas?",
      "SUM(COUNT(DOCLIN)) por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(L.CODARTICULO) AS N_LINEAS_TOTAL, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE ORDER BY N_LINEAS_TOTAL DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","",""),

    q("vx_105", "Facturas con CODCLIENTE igual a CODAGENTE (posible error)",
      "¿Hay facturas donde el cliente y el agente tienen el mismo código?",
      "DOCCAB TIPO=13 con CODCLIENTE=CODAGENTE. Puede ser un error de entrada.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.CODAGENTE, D.FECHA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.CODCLIENTE=D.CODAGENTE LIMIT 20",
      "Ventas","Administrativo","Calidad","Medio","",""),

    q("vx_106", "Clientes con mayor importe en presupuestos rechazados",
      "¿Qué clientes tienen más importe en presupuestos que no se convirtieron?",
      "Presupuestos TIPO=0 sin correspondencia en TIPO=13 por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(D.CODIGO) AS N_PRESUPUESTOS_NO_CONVERTIDOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS IMPORTE_NO_CONVERTIDO "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=0 AND D.CODIGO NOT IN "
      "(SELECT DISTINCT CODDOCUMENTOORIGEN FROM DOCLIN WHERE CODDOCUMENTOORIGEN IS NOT NULL) "
      "GROUP BY D.CODCLIENTE ORDER BY IMPORTE_NO_CONVERTIDO DESC LIMIT 20",
      "Ventas","Comercial","Riesgo","Alto","",""),

    q("vx_107", "Artículos con mayor variación de PRECIOVENTA en ventas",
      "¿Qué artículos tienen mayor variación de PRECIOVENTA entre ventas?",
      "MAX(PRECIOVENTA)-MIN(PRECIOVENTA) por artículo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(MIN(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MIN, "
      "ROUND(MAX(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MAX, "
      "ROUND(MAX(CAST(L.PRECIO AS REAL))-MIN(CAST(L.PRECIO AS REAL)),2) AS VARIACION "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING COUNT(*) > 2 "
      "ORDER BY VARIACION DESC LIMIT 20",
      "Ventas","Comercial","Calidad","Medio","",""),

    q("vx_108", "Clientes con facturas en más de 5 agentes distintos",
      "¿Qué clientes han sido atendidos por más de 5 agentes distintos?",
      "COUNT(DISTINCT CODAGENTE) > 5 por cliente en DOCCAB TIPO=13.",
      f"SELECT {_C} AS CLIENTE, COUNT(DISTINCT D.CODAGENTE) AS N_AGENTES, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.CODAGENTE > 0 GROUP BY D.CODCLIENTE "
      "HAVING COUNT(DISTINCT D.CODAGENTE) > 5 ORDER BY N_AGENTES DESC LIMIT 20",
      "Ventas","Director","Calidad","Medio","",""),

    q("vx_109", "Facturas con importe redondeado (posible estimación)",
      "¿Hay facturas con importe exactamente redondo (múltiplo de 100)?",
      "DOCCAB TIPO=13 con IMPORTETOTAL % 100 = 0. Pueden ser estimaciones.",
      f"SELECT D.CODIGO, {_C} AS CLIENTE, D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND CAST(D.IMPORTETOTAL AS INTEGER) % 100 = 0 "
      "AND D.IMPORTETOTAL > 0 ORDER BY D.IMPORTETOTAL DESC LIMIT 20",
      "Ventas","Administrativo","Calidad","Bajo","",""),

    q("vx_110", "Clientes con mayor número de artículos distintos por factura",
      "¿Qué clientes piden más variedad de artículos en cada factura?",
      "AVG(COUNT(DISTINCT CODIGO)) por factura por cliente.",
      f"SELECT {_C} AS CLIENTE, "
      "ROUND(AVG(N_ARTICULOS),2) AS MEDIA_ARTICULOS_POR_FACTURA, "
      "COUNT(*) AS N_FACTURAS "
      "FROM (SELECT D.CODCLIENTE, D.CODIGO, COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS "
      "      FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO WHERE D.TIPO=13 "
      "      GROUP BY D.CODIGO) "
      "LEFT JOIN CLIENTE C ON CODCLIENTE=C.CODIGO "
      "GROUP BY CODCLIENTE ORDER BY MEDIA_ARTICULOS_POR_FACTURA DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Bajo","",""),

    q("vx_111", "Facturas con ESTADO distinto de 0 y 1",
      "¿Hay facturas con estados no estándar?",
      "DOCCAB TIPO=13 con ESTADO no en (0,1). Pueden ser estados personalizados.",
      f"SELECT D.ESTADOPEND, COUNT(*) AS N, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D WHERE D.TIPO=13 AND D.ESTADOPEND NOT IN (0,1) "
      "GROUP BY D.ESTADOPEND ORDER BY N DESC LIMIT 10",
      "Ventas","Administrativo","Calidad","Bajo","",""),

    q("vx_112", "Clientes con mayor número de facturas en el último mes",
      "¿Qué clientes han recibido más facturas en el último mes?",
      "COUNT de DOCCAB TIPO=13 del mes actual por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY D.CODCLIENTE ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","KPI","Medio","",""),

    q("vx_113", "Artículos con mayor número de facturas distintas",
      "¿En cuántas facturas distintas aparece cada artículo?",
      "COUNT(DISTINCT CODDOCUMENTO) por artículo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_FACTURAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_FACTURAS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","",""),

    q("vx_114", "Clientes con mayor importe en el último trimestre",
      "¿Qué clientes han facturado más en los últimos 3 meses?",
      "SUM(IMPORTETOTAL) de DOCCAB TIPO=13 con FECHA >= date('now','-90 days') por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_90D "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= date('now','-90 days') "
      "GROUP BY D.CODCLIENTE ORDER BY TOTAL_90D DESC LIMIT 20",
      "Ventas","Director","KPI","Alto","",""),

    q("vx_115", "Artículos con mayor importe en el último trimestre",
      "¿Qué artículos se han vendido más en los últimos 3 meses?",
      "SUM(CANTIDAD*PRECIOVENTA) de DOCLIN JOIN DOCCAB TIPO=13 con FECHA >= date('now','-90 days').",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_90D "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.FECHA >= date('now','-90 days') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_90D DESC LIMIT 20",
      "Ventas","Comercial","Producto","Alto","",""),

    q("vx_116", "Clientes con mayor número de presupuestos en el último mes",
      "¿Qué clientes han recibido más presupuestos en el último mes?",
      "COUNT de DOCCAB TIPO=0 del mes actual por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_PRESUPUESTOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=0 AND SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY D.CODCLIENTE ORDER BY N_PRESUPUESTOS DESC LIMIT 20",
      "Ventas","Comercial","KPI","Medio","",""),

    q("vx_117", "Facturas con CODCLIENTE vacío o nulo",
      "¿Hay facturas sin cliente asignado?",
      "DOCCAB TIPO=13 con CODCLIENTE NULL o vacío.",
      "SELECT COUNT(*) AS N_SIN_CLIENTE, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND (CODCLIENTE IS NULL OR CODCLIENTE='')",
      "Ventas","Administrativo","Calidad","Alto","",""),

    q("vx_118", "Artículos con mayor número de proveedores distintos",
      "¿Hay artículos asociados a más de un proveedor?",
      "En el modelo actual, ARTICULO tiene un solo PROVEEDDEFECTO. "
      "Esta consulta verifica si hay inconsistencias.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,A.CODIGO) AS ARTICULO, "
      "COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,CAST(A.PROVEEDDEFECTO AS TEXT)) AS PROVEEDOR "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "ORDER BY ARTICULO LIMIT 30",
      "Ventas","Administrativo","Calidad","Bajo","",""),

    q("vx_119", "Clientes con mayor número de albaranes sin facturar",
      "¿Qué clientes tienen más albaranes pendientes de facturar?",
      "COUNT de DOCCAB TIPO=11 por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_ALBARANES, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_PENDIENTE "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=11 GROUP BY D.CODCLIENTE ORDER BY N_ALBARANES DESC LIMIT 20",
      "Ventas","Administrativo","Riesgo","Alto","",""),

    q("vx_120", "Artículos con mayor número de albaranes",
      "¿Qué artículos aparecen más en albaranes?",
      "COUNT(DISTINCT CODDOCUMENTO) por artículo en DOCLIN JOIN DOCCAB TIPO=11.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_ALBARANES, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=11 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_ALBARANES DESC LIMIT 20",
      "Ventas","Almacenero","Producto","Bajo","",""),

    q("vx_121", "Clientes con mayor número de SATs",
      "¿Qué clientes tienen más SATs registrados?",
      "COUNT de DOCCAB TIPO=2 por cliente.",
      f"SELECT {_C} AS CLIENTE, COUNT(*) AS N_SATS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=2 GROUP BY D.CODCLIENTE ORDER BY N_SATS DESC LIMIT 20",
      "Ventas","Comercial","Cliente","Medio","",""),

    q("vx_122", "Clientes con SATs y sin facturas recientes",
      "¿Qué clientes tienen SATs pero no han comprado en los últimos 6 meses?",
      "Clientes con DOCCAB TIPO=2 y sin DOCCAB TIPO=13 en los últimos 180 días.",
      f"SELECT {_C} AS CLIENTE, COUNT(D.CODIGO) AS N_SATS "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO=2 AND D.CODCLIENTE NOT IN "
      "(SELECT DISTINCT CODCLIENTE FROM DOCCAB WHERE TIPO=13 "
      "AND FECHA >= date('now','-180 days')) "
      "GROUP BY D.CODCLIENTE ORDER BY N_SATS DESC LIMIT 20",
      "Ventas","Comercial","Riesgo","Alto","",""),

    q("vx_123", "Artículos con mayor número de SATs",
      "¿Qué artículos aparecen más en SATs?",
      "COUNT(DISTINCT CODDOCUMENTO) por artículo en DOCLIN JOIN DOCCAB TIPO=2.",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_SATS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=2 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_SATS DESC LIMIT 20",
      "Ventas","Comercial","Producto","Medio","",""),

    q("vx_124", "Clientes con mayor ratio SAT/Factura",
      "¿Qué clientes tienen más SATs por cada factura?",
      "Ratio COUNT(TIPO=2)/COUNT(TIPO=13) por cliente.",
      f"SELECT {_C} AS CLIENTE, "
      "SUM(CASE WHEN D.TIPO=2 THEN 1 ELSE 0 END) AS N_SATS, "
      "SUM(CASE WHEN D.TIPO=13 THEN 1 ELSE 0 END) AS N_FACTURAS, "
      "CASE WHEN SUM(CASE WHEN D.TIPO=13 THEN 1 ELSE 0 END)>0 "
      "THEN ROUND(CAST(SUM(CASE WHEN D.TIPO=2 THEN 1 ELSE 0 END) AS REAL)/"
      "SUM(CASE WHEN D.TIPO=13 THEN 1 ELSE 0 END),2) ELSE NULL END AS RATIO_SAT_FACTURA "
      "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
      "WHERE D.TIPO IN (2,13) GROUP BY D.CODCLIENTE "
      "HAVING N_SATS > 0 AND N_FACTURAS > 0 "
      "ORDER BY RATIO_SAT_FACTURA DESC LIMIT 20",
      "Ventas","Director","Calidad","Alto","",""),

    q("vx_125", "Artículos con mayor importe total en toda la historia",
      "¿Qué artículos han generado más importe en toda la historia de ventas?",
      "SUM(CANTIDAD*PRECIOVENTA) por artículo en DOCLIN JOIN DOCCAB TIPO=13 (sin filtro de fecha).",
      "SELECT COALESCE(A.NOMBRE,A.DESCRIPCION,L.CODARTICULO) AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_HISTORICO, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_FACTURAS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_HISTORICO DESC LIMIT 20",
      "Ventas","Director","KPI","Alto","",""),
]
