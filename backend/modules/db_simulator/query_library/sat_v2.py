"""sat_v2.py — 25 consultas adicionales de SAT / Técnico (v2).

DEVIA: fichero < 500 líneas, módulo independiente, sin lógica de negocio.
"""
from backend.modules.db_simulator.query_library.builder import q

QUERIES_SAT_V2: list = [
    q("sv2_001", "SATs por técnico (agente)", "SATs agrupados por agente",
      "Cuenta SATs TIPO=2 por CODAGENTE para ver la carga de trabajo de cada técnico.",
      "SELECT CODAGENTE, COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURADO "
      "FROM DOCCAB WHERE TIPO=2 GROUP BY CODAGENTE ORDER BY N_SATS DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_002", "SATs sin fecha de emisión (pendientes)", "SATs pendientes de cerrar",
      "SATs TIPO=2 sin FECHAEMISION asignada que pueden estar abiertos o sin procesar.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=2 AND FECHAEMISION IS NULL ORDER BY FECHA LIMIT 30",
      "SAT / Tecnico", "SAT / Tecnico", "Alerta", "Alto", "", ""),

    q("sv2_003", "Importe total facturado por SAT", "Facturación total SAT",
      "Suma de IMPORTETOTAL de todos los documentos TIPO=2 (SATs).",
      "SELECT COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_SAT "
      "FROM DOCCAB WHERE TIPO=2",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Critico", "", ""),

    q("sv2_004", "SATs por cliente", "SATs agrupados por cliente",
      "Clientes con más SATs registrados, útil para detectar equipos con problemas recurrentes.",
      "SELECT CODCLIENTE, COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=2 GROUP BY CODCLIENTE ORDER BY N_SATS DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_005", "SATs por mes", "Evolución mensual de SATs",
      "Número de SATs TIPO=2 agrupados por mes para ver la evolución del servicio técnico.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=2 AND FECHA IS NOT NULL GROUP BY MES ORDER BY MES DESC LIMIT 12",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_006", "Importe medio por SAT", "Ticket medio SAT",
      "Importe medio de los SATs TIPO=2 para comparar con la factura media de venta.",
      "SELECT ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO, "
      "ROUND(MIN(IMPORTETOTAL),2) AS MINIMO, ROUND(MAX(IMPORTETOTAL),2) AS MAXIMO "
      "FROM DOCCAB WHERE TIPO=2",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Medio", "", ""),

    q("sv2_007", "SATs con importe superior a 1.000€", "SATs de alto PRECIOCOSTE",
      "SATs TIPO=2 con IMPORTETOTAL>1000 que representan intervenciones de mayor envergadura.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=2 AND IMPORTETOTAL>1000 ORDER BY IMPORTETOTAL DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "Operacional", "Medio", "", ""),

    q("sv2_008", "SATs del mes actual", "SATs mes en curso",
      "SATs TIPO=2 registrados en el mes actual.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=2 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7) "
      "ORDER BY FECHA DESC LIMIT 30",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_009", "Artículos más usados en SATs", "Repuestos más utilizados en SAT",
      "Artículos que aparecen con más frecuencia en líneas de documentos SAT TIPO=2.",
      "SELECT L.CODARTICULO, A.NOMBRE, COUNT(L.CODARTICULO) AS N_USOS, SUM(L.CANTIDAD) AS TOTAL_UNIADES "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=2 GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY N_USOS DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_010", "SATs con importe cero", "SATs sin facturación",
      "SATs TIPO=2 con IMPORTETOTAL=0 que pueden ser visitas de garantía o sin facturar.",
      "SELECT CODIGO, CODCLIENTE, FECHA FROM DOCCAB WHERE TIPO=2 AND IMPORTETOTAL=0 "
      "ORDER BY FECHA DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "Alerta", "Medio", "", ""),

    q("sv2_011", "Ratio SATs por factura de venta", "Proporción SAT vs ventas",
      "Compara el número de SATs con el número de facturas de venta para ver la proporción de postventa.",
      "SELECT "
      "SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END) AS N_FACTURAS_VENTA, "
      "SUM(CASE WHEN TIPO=2 THEN 1 ELSE 0 END) AS N_SATS, "
      "ROUND(100.0*SUM(CASE WHEN TIPO=2 THEN 1 ELSE 0 END)/"
      "NULLIF(SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END),0),1) AS PCT_SAT_VS_VENTA "
      "FROM DOCCAB WHERE TIPO IN (2,13)",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_012", "SATs por año", "Evolución anual de SATs",
      "Número de SATs TIPO=2 agrupados por año para análisis histórico.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=2 AND FECHA IS NOT NULL GROUP BY ANIO ORDER BY ANIO DESC",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_013", "Clientes con más de 3 SATs", "Clientes con alta incidencia técnica",
      "Clientes con más de 3 SATs registrados que pueden indicar problemas recurrentes.",
      "SELECT CODCLIENTE, COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=2 GROUP BY CODCLIENTE HAVING N_SATS>3 ORDER BY N_SATS DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "Alerta", "Alto", "", ""),

    q("sv2_014", "SATs sin cliente asignado", "SATs sin cliente",
      "SATs TIPO=2 con CODCLIENTE nulo o cero que no tienen cliente asignado.",
      "SELECT CODIGO, FECHA, IMPORTETOTAL FROM DOCCAB "
      "WHERE TIPO=2 AND (CODCLIENTE IS NULL OR CODCLIENTE=0) ORDER BY FECHA DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "Alerta", "Medio", "", ""),

    q("sv2_015", "Facturación SAT vs facturación venta por mes", "Comparativa SAT vs ventas mensual",
      "Compara la facturación mensual de SATs con la de ventas para ver la proporción.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS VENTAS, "
      "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTETOTAL ELSE 0 END),2) AS SAT "
      "FROM DOCCAB WHERE TIPO IN (2,13) AND FECHA IS NOT NULL "
      "GROUP BY MES ORDER BY MES DESC LIMIT 12",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_016", "Líneas de SAT por artículo y técnico", "Detalle repuestos por técnico",
      "Artículos usados en SATs desglosados por técnico (CODAGENTE).",
      "SELECT D.CODAGENTE, L.CODARTICULO, A.NOMBRE, COUNT(L.CODARTICULO) AS N_USOS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=2 GROUP BY D.CODAGENTE, L.CODARTICULO, A.NOMBRE "
      "ORDER BY D.CODAGENTE, N_USOS DESC LIMIT 30",
      "SAT / Tecnico", "SAT / Tecnico", "Operacional", "Medio", "", ""),

    q("sv2_017", "SATs con más de 5 líneas de detalle", "SATs complejos",
      "SATs con más de 5 líneas en DOCLIN que representan intervenciones complejas.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.FECHA, D.IMPORTETOTAL, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=2 GROUP BY D.CODIGO, D.CODCLIENTE, D.FECHA, D.IMPORTETOTAL "
      "HAVING N_LINEAS>5 ORDER BY N_LINEAS DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "Operacional", "Medio", "", ""),

    q("sv2_018", "Importe total SAT por familia de artículo", "SAT por familia",
      "Agrupa el importe de líneas de SAT por familia de artículo para ver qué equipos generan más servicio.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS TOTAL_IMPORTE "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=2 GROUP BY F.NOMBRE ORDER BY TOTAL_IMPORTE DESC LIMIT 15",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_019", "SATs emitidos en los últimos 30 días", "SATs recientes",
      "SATs TIPO=2 registrados en los últimos 30 días.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=2 AND FECHA >= DATE('now','-30 days') "
      "ORDER BY FECHA DESC LIMIT 30",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_020", "Técnico con mayor facturación SAT", "Top técnico por facturación",
      "Técnico (CODAGENTE) con mayor importe total facturado en SATs.",
      "SELECT CODAGENTE, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURADO, COUNT(*) AS N_SATS "
      "FROM DOCCAB WHERE TIPO=2 GROUP BY CODAGENTE ORDER BY TOTAL_FACTURADO DESC LIMIT 10",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_021", "SATs con fecha anterior a 2020", "SATs históricos antiguos",
      "SATs TIPO=2 con fecha anterior a 2020 para identificar registros históricos.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=2 AND FECHA < '2020-01-01' ORDER BY FECHA DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "Operacional", "Bajo", "", ""),

    q("sv2_022", "Distribución de SATs por día de la semana", "SATs por día semana",
      "Agrupa SATs por día de la semana para detectar patrones de demanda.",
      "SELECT STRFTIME('%w',FECHA) AS DIA_SEMANA, COUNT(*) AS N_SATS "
      "FROM DOCCAB WHERE TIPO=2 AND FECHA IS NOT NULL "
      "GROUP BY DIA_SEMANA ORDER BY DIA_SEMANA",
      "SAT / Tecnico", "SAT / Tecnico", "Operacional", "Bajo", "", ""),

    q("sv2_023", "SATs con artículos de familia climatización", "SATs de climatización",
      "SATs que incluyen artículos de la familia principal de climatización.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.FECHA, D.IMPORTETOTAL "
      "FROM DOCCAB D WHERE D.TIPO=2 AND EXISTS ("
      "SELECT 1 FROM DOCLIN L JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE L.CODDOCUMENTO=D.CODIGO AND F.NOMBRE LIKE '%CLIMA%') "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_024", "Tiempo medio entre SATs por cliente", "Frecuencia de SATs por cliente",
      "Calcula el número de días entre el primer y último SAT de cada cliente.",
      "SELECT CODCLIENTE, COUNT(*) AS N_SATS, "
      "MIN(FECHA) AS PRIMER_SAT, MAX(FECHA) AS ULTIMO_SAT, "
      "CAST(JULIANDAY(MAX(FECHA))-JULIANDAY(MIN(FECHA)) AS INT) AS DIAS_ENTRE_SATS "
      "FROM DOCCAB WHERE TIPO=2 AND FECHA IS NOT NULL "
      "GROUP BY CODCLIENTE HAVING N_SATS>1 ORDER BY DIAS_ENTRE_SATS ASC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "KPI", "Alto", "", ""),

    q("sv2_025", "SATs sin líneas de detalle", "SATs vacíos sin líneas",
      "SATs TIPO=2 que no tienen ninguna línea en DOCLIN, posibles registros incompletos.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.FECHA, D.IMPORTETOTAL "
      "FROM DOCCAB D WHERE D.TIPO=2 AND NOT EXISTS ("
      "SELECT 1 FROM DOCLIN L WHERE L.CODDOCUMENTO=D.CODIGO) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "SAT / Tecnico", "SAT / Tecnico", "Alerta", "Medio", "", ""),
]
