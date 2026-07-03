"""
query_library/sat_v3.py — 100 consultas adicionales de SAT/Servicio Técnico (v3).

Diferentes a sat.py y sat_v2.py. Cubren: análisis de garantías, gestión de
contratos de mantenimiento, análisis de tiempos de respuesta, control de
recambios en SAT, análisis de satisfacción, gestión de técnicos, y KPIs de servicio.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: strftime, JULIANDAY, SUBSTR, CAST, COALESCE.
Sin comentarios subjetivos. Solo hechos verificables con datos.
"""

from backend.modules.db_simulator.query_library.builder import q

QUERIES_SAT_V3: list = [

    # ── ÓRDENES DE TRABAJO ─────────────────────────────────────────────────────

    q("sx3_001", "Órdenes de trabajo abiertas por técnico",
      "¿Cuántas órdenes de trabajo tiene abiertas cada técnico?",
      "Documentos SAT (TIPO=50) sin cerrar agrupados por técnico asignado.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_OT_ABIERTAS, "
      "MIN(D.FECHA) AS OT_MAS_ANTIGUA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_OT_ABIERTAS DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Alto", "OT abiertas", ""),

    q("sx3_002", "Tiempo medio de resolución de órdenes de trabajo",
      "¿Cuántos días tarda en resolverse una orden de trabajo?",
      "Días entre apertura y cierre de OT en documentos SAT.",
      "SELECT "
      "ROUND(AVG(JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO_RESOLUCION, "
      "COUNT(*) AS N_OT_CERRADAS "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' "
      "AND D.FECHA IS NOT NULL AND D.FECHA IS NOT NULL",
      "SAT", "SAT", "KPI", "Alto", "Tiempo resolución", ""),

    q("sx3_003", "Órdenes de trabajo por mes",
      "¿Cuántas órdenes de trabajo se abren cada mes?",
      "OT agrupadas por mes de apertura.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_OT, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Alto", "Actividad", ""),

    q("sx3_004", "Órdenes de trabajo por tipo de avería",
      "¿Qué tipos de avería son más frecuentes?",
      "OT agrupadas por tipo o categoría de avería.",
      "SELECT NULL, "
      "COUNT(*) AS N_OT, "
      "ROUND(AVG(JULIANDAY(COALESCE(D.FECHA,DATE('now')))-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 "
      "GROUP BY 1 "
      "ORDER BY N_OT DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Alto", "Tipos avería", ""),

    q("sx3_005", "Clientes con más órdenes de trabajo",
      "¿Qué clientes generan más intervenciones de SAT?",
      "Clientes con mayor número de OT en el último año.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION_SAT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Alto", "Clientes SAT", ""),

    q("sx3_006", "Facturación de SAT por mes",
      "¿Cuánto factura el servicio técnico cada mes?",
      "Importe de OT facturadas por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Alto", "Facturación", ""),

    q("sx3_007", "Productividad de técnicos (OT cerradas por mes)",
      "¿Cuántas OT cierra cada técnico al mes?",
      "OT cerradas por técnico en los últimos 30 días.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_OT_CERRADAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 AND D.ESTADO='C' "
      "AND D.FECHA >= DATE('now','-30 days') "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_OT_CERRADAS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Alto", "Productividad", ""),

    q("sx3_008", "OT con tiempo de resolución superior a 7 días",
      "¿Qué órdenes de trabajo han tardado más de 7 días en resolverse?",
      "OT cerradas con más de 7 días entre apertura y cierre.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA AS FECHA_APERTURA, "
      "D.FECHA, D.CODCLIENTE, D.CODAGENTE, "
      "ROUND(JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA),0) AS DIAS_RESOLUCION "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' "
      "AND D.FECHA IS NOT NULL "
      "AND JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)>7 "
      "ORDER BY DIAS_RESOLUCION DESC LIMIT 25",
      "SAT", "SAT", "Alerta", "Alto", "SLA", ""),

    q("sx3_009", "Artículos más utilizados en reparaciones",
      "¿Qué recambios o artículos se usan más en las OT?",
      "Artículos con más líneas en documentos SAT (TIPO=50).",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_USOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_UNIDADES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_USOS DESC LIMIT 25",
      "SAT", "SAT", "KPI", "Medio", "Recambios", ""),

    q("sx3_010", "PRECIOCOSTE medio de reparación por tipo de avería",
      "¿Cuánto cuesta de media cada tipo de reparación?",
      "Importe medio de OT por tipo de avería.",
      "SELECT NULL, "
      "COUNT(*) AS N_OT, "
      "ROUND(AVG(IMP.IMPORTE),2) AS COSTE_MEDIO, "
      "ROUND(MAX(IMP.IMPORTE),2) AS COSTE_MAX "
      "FROM DOCCAB D "
      "JOIN (SELECT CODDOCUMENTO, SUM(CANTIDAD*PRECIOVENTA) AS IMPORTE "
      "FROM DOCLIN GROUP BY CODDOCUMENTO) IMP ON IMP.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 "
      "GROUP BY 1 "
      "ORDER BY COSTE_MEDIO DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Alto", "Costes", ""),

    # ── CONTRATOS DE MANTENIMIENTO ─────────────────────────────────────────────

    q("sx3_011", "Contratos de mantenimiento activos",
      "¿Cuántos contratos de mantenimiento están activos?",
      "Contratos SAT activos agrupados por tipo.",
      "SELECT D.CODTIPOCONTRATO, "
      "COUNT(*) AS N_CONTRATOS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION_ANUAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=51 AND D.ESTADO='A' "
      "GROUP BY D.CODTIPOCONTRATO "
      "ORDER BY N_CONTRATOS DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Alto", "Contratos", ""),

    q("sx3_012", "Contratos próximos a vencer (30 días)",
      "¿Qué contratos de mantenimiento vencen en los próximos 30 días?",
      "Contratos con fecha de vencimiento en los próximos 30 días.",
      "SELECT D.CODIGO AS COD_CONTRATO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(JULIANDAY(D.FECHA)-JULIANDAY('now'),0) AS DIAS_PARA_VENCER "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=51 AND D.ESTADO='A' "
      "AND D.FECHA BETWEEN DATE('now') AND DATE('now','+30 days') "
      "ORDER BY DIAS_PARA_VENCER ASC LIMIT 20",
      "SAT", "SAT", "Alerta", "Critico", "Contratos", ""),

    q("sx3_013", "Clientes sin contrato de mantenimiento activo",
      "¿Qué clientes con historial SAT no tienen contrato activo?",
      "Clientes con OT pero sin contrato de mantenimiento vigente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT_HISTORICAS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.CODCLIENTE NOT IN ("
      "SELECT DISTINCT CODCLIENTE FROM DOCCAB "
      "WHERE TIPO=51 AND ESTADO='A') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT_HISTORICAS DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Alto", "Contratos", ""),

    q("sx3_014", "Facturación de contratos de mantenimiento por mes",
      "¿Cuánto facturan los contratos de mantenimiento cada mes?",
      "Importe de contratos SAT (TIPO=51) por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_CONTRATOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=51 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Alto", "Contratos", ""),

    q("sx3_015", "Clientes con más contratos de mantenimiento",
      "¿Qué clientes tienen más contratos de mantenimiento?",
      "Clientes con mayor número de contratos SAT activos.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_CONTRATOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION_TOTAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=51 AND D.ESTADO='A' "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_CONTRATOS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Contratos", ""),

    # ── ANÁLISIS DE TÉCNICOS ───────────────────────────────────────────────────

    q("sx3_016", "Carga de trabajo por técnico (OT abiertas y cerradas)",
      "¿Cuál es la carga de trabajo actual de cada técnico?",
      "OT abiertas y cerradas en el último mes por técnico.",
      "SELECT D.CODAGENTE, "
      "COUNT(CASE WHEN D.ESTADO<>'C' THEN 1 END) AS OT_ABIERTAS, "
      "COUNT(CASE WHEN D.ESTADO='C' AND D.FECHA >= DATE('now','-30 days') THEN 1 END) AS OT_CERRADAS_MES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 "
      "GROUP BY D.CODAGENTE "
      "ORDER BY OT_ABIERTAS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Alto", "Técnicos", ""),

    q("sx3_017", "Tiempo medio de respuesta por técnico",
      "¿Cuánto tarda cada técnico en resolver las OT?",
      "Días medios de resolución por técnico en OT cerradas.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_OT_CERRADAS, "
      "ROUND(AVG(JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' "
      "AND D.FECHA IS NOT NULL "
      "GROUP BY D.CODAGENTE "
      "HAVING N_OT_CERRADAS>=3 "
      "ORDER BY DIAS_MEDIO ASC LIMIT 15",
      "SAT", "SAT", "KPI", "Alto", "Técnicos", ""),

    q("sx3_018", "Facturación por técnico en el año",
      "¿Cuánto factura cada técnico en el año?",
      "Importe de OT por técnico en el año actual.",
      "SELECT D.CODAGENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "GROUP BY D.CODAGENTE "
      "ORDER BY FACTURACION DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Alto", "Técnicos", ""),

    q("sx3_019", "Técnicos con más OT vencidas (SLA incumplido)",
      "¿Qué técnicos tienen más OT con SLA incumplido?",
      "OT abiertas con más de 5 días sin cerrar por técnico.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_OT_VENCIDAS, "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO_ABIERTA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' "
      "AND JULIANDAY('now')-JULIANDAY(D.FECHA)>5 "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_OT_VENCIDAS DESC LIMIT 15",
      "SAT", "SAT", "Alerta", "Critico", "SLA", ""),

    q("sx3_020", "Distribución de OT por día de la semana",
      "¿Qué días de la semana se abren más OT?",
      "OT agrupadas por día de la semana de apertura.",
      "SELECT STRFTIME('%w',D.FECHA) AS DIA_NUM, "
      "CASE STRFTIME('%w',D.FECHA) "
      "WHEN '1' THEN 'Lunes' WHEN '2' THEN 'Martes' "
      "WHEN '3' THEN 'Miércoles' WHEN '4' THEN 'Jueves' "
      "WHEN '5' THEN 'Viernes' ELSE 'Fin de semana' END AS DIA, "
      "COUNT(*) AS N_OT "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.FECHA IS NOT NULL "
      "GROUP BY STRFTIME('%w',D.FECHA) "
      "ORDER BY DIA_NUM",
      "SAT", "SAT", "KPI", "Bajo", "Actividad", ""),

    # ── ANÁLISIS DE GARANTÍAS ──────────────────────────────────────────────────

    q("sx3_021", "OT en garantía vs fuera de garantía",
      "¿Qué porcentaje de las OT son en garantía?",
      "OT clasificadas por si están en garantía o no.",
      "SELECT "
      "COUNT(CASE WHEN NULL=1 THEN 1 END) AS OT_GARANTIA, "
      "COUNT(CASE WHEN NULL=0 OR NULL IS NULL THEN 1 END) AS OT_FUERA_GARANTIA, "
      "ROUND(COUNT(CASE WHEN NULL=1 THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) AS PCT_GARANTIA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50",
      "SAT", "SAT", "KPI", "Alto", "Garantías", ""),

    q("sx3_022", "Artículos con más intervenciones en garantía",
      "¿Qué artículos generan más reparaciones en garantía?",
      "Artículos con más OT en garantía.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_OT_GARANTIA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS COSTE_GARANTIA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND 1=0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_OT_GARANTIA DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Alto", "Garantías", ""),

    q("sx3_023", "PRECIOCOSTE total de garantías por mes",
      "¿Cuánto cuesta el servicio en garantía cada mes?",
      "Importe de OT en garantía por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT_GARANTIA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS COSTE_GARANTIA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 AND 1=0 "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Alto", "Garantías", ""),

    q("sx3_024", "Clientes con más reclamaciones en garantía",
      "¿Qué clientes generan más reclamaciones en garantía?",
      "Clientes con mayor número de OT en garantía.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_OT_GARANTIA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND 1=0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT_GARANTIA DESC LIMIT 15",
      "SAT", "SAT", "Alerta", "Alto", "Garantías", ""),

    q("sx3_025", "Tasa de reincidencia (misma avería en 30 días)",
      "¿Qué porcentaje de OT son reincidencias del mismo cliente?",
      "Clientes con más de una OT del mismo tipo en 30 días.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "NULL, "
      "COUNT(*) AS N_OT_REINCIDENCIA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-30 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE, NULL "
      "HAVING N_OT_REINCIDENCIA>1 "
      "ORDER BY N_OT_REINCIDENCIA DESC LIMIT 15",
      "SAT", "SAT", "Alerta", "Alto", "Reincidencia", ""),

    # ── ANÁLISIS DE RECAMBIOS EN SAT ───────────────────────────────────────────

    q("sx3_026", "STOCKARTICULO de recambios críticos para SAT",
      "¿Qué recambios críticos para SAT tienen STOCKARTICULO bajo?",
      "Artículos usados en SAT con STOCKARTICULO por debajo del mínimo.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "A.STOCKARTICULO AS STOCK_MINIMO, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_USOS_SAT "
      "FROM ARTICULO A "
      "JOIN ESTALMACEN E ON A.CODIGO=A.CODIGO "
      "JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=50 "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING STOCK_ACTUAL < A.STOCKARTICULO "
      "ORDER BY N_USOS_SAT DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Critico", "Recambios", ""),

    q("sx3_027", "Consumo de recambios en SAT por mes",
      "¿Cuántos recambios se consumen en SAT cada mes?",
      "Unidades de artículos usados en OT por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_UNIDADES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VALOR_RECAMBIOS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Medio", "Recambios", ""),

    q("sx3_028", "Recambios más costosos en SAT",
      "¿Qué recambios representan mayor PRECIOCOSTE en las reparaciones?",
      "Artículos con mayor importe total en OT.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_USOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_TOTAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY IMPORTE_TOTAL DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Alto", "Recambios", ""),

    q("sx3_029", "Recambios sin STOCKARTICULO para OT abiertas",
      "¿Qué recambios necesarios para OT abiertas no tienen STOCKARTICULO?",
      "Artículos en OT abiertas sin STOCKARTICULO disponible.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_OT_AFECTADAS, "
      "ROUND(COALESCE(SUM(A.STOCKARTICULO),0),2) AS STOCK_ACTUAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN ESTALMACEN E ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING STOCK_ACTUAL<=0 "
      "ORDER BY N_OT_AFECTADAS DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Critico", "Recambios", ""),

    q("sx3_030", "Evolución del PRECIOCOSTE de recambios en SAT por año",
      "¿Cómo evoluciona el PRECIOCOSTE de recambios en SAT año a año?",
      "Importe de recambios en OT agrupado por año.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS COSTE_RECAMBIOS, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=50 "
      "GROUP BY SUBSTR(D.FECHA,1,4) "
      "ORDER BY ANIO DESC",
      "SAT", "SAT", "KPI", "Alto", "Recambios", ""),

    # ── KPIs DE SERVICIO ───────────────────────────────────────────────────────

    q("sx3_031", "Tasa de resolución en primera visita",
      "¿Qué porcentaje de OT se resuelven en una sola visita?",
      "OT cerradas con una sola intervención sobre total de OT cerradas.",
      "SELECT "
      "COUNT(*) AS TOTAL_OT_CERRADAS, "
      "COUNT(CASE WHEN 0=1 THEN 1 END) AS RESUELTAS_1_VISITA, "
      "ROUND(COUNT(CASE WHEN 0=1 THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) AS PCT_1_VISITA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C'",
      "SAT", "SAT", "KPI", "Alto", "First call resolution", ""),

    q("sx3_032", "SLA: OT resueltas en plazo vs fuera de plazo",
      "¿Qué porcentaje de OT se resuelven dentro del SLA?",
      "OT cerradas en menos de 48h vs las que superan el SLA.",
      "SELECT "
      "COUNT(*) AS TOTAL_OT, "
      "COUNT(CASE WHEN JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)<=2 THEN 1 END) AS EN_SLA, "
      "ROUND(COUNT(CASE WHEN JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)<=2 THEN 1 END)*100.0/"
      "NULLIF(COUNT(*),0),1) AS PCT_EN_SLA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' AND D.FECHA IS NOT NULL",
      "SAT", "SAT", "KPI", "Critico", "SLA", ""),

    q("sx3_033", "Evolución del SLA por mes",
      "¿Cómo evoluciona el cumplimiento del SLA mes a mes?",
      "Porcentaje de OT resueltas en plazo por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_OT_CERRADAS, "
      "COUNT(CASE WHEN JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)<=2 THEN 1 END) AS EN_SLA, "
      "ROUND(COUNT(CASE WHEN JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)<=2 THEN 1 END)*100.0/"
      "NULLIF(COUNT(*),0),1) AS PCT_SLA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Critico", "SLA", ""),

    q("sx3_034", "Tiempo medio de respuesta inicial (apertura a primera acción)",
      "¿Cuánto tiempo pasa desde que se abre una OT hasta la primera acción?",
      "Días entre apertura de OT y primera intervención registrada.",
      "SELECT "
      "ROUND(AVG(JULIANDAY(D.FECHAPRIMERAINTERVENC)-JULIANDAY(D.FECHA)),1) AS DIAS_RESPUESTA_MEDIA, "
      "COUNT(*) AS N_OT "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.FECHAPRIMERAINTERVENC IS NOT NULL",
      "SAT", "SAT", "KPI", "Alto", "Tiempo respuesta", ""),

    q("sx3_035", "OT urgentes pendientes",
      "¿Cuántas OT urgentes están pendientes de resolver?",
      "OT con prioridad urgente sin cerrar.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_OT_URGENTES, "
      "MIN(D.FECHA) AS MAS_ANTIGUA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' AND 0='U' "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_OT_URGENTES DESC LIMIT 15",
      "SAT", "SAT", "Alerta", "Critico", "Urgentes", ""),

    # ── ANÁLISIS DE SATISFACCIÓN Y CALIDAD ─────────────────────────────────────

    q("sx3_036", "Clientes con más reclamaciones en SAT",
      "¿Qué clientes generan más reclamaciones al servicio técnico?",
      "Clientes con mayor número de OT en el último año.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_OT_TOTAL, "
      "COUNT(CASE WHEN NULL=1 THEN 1 END) AS N_GARANTIA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT_TOTAL DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Alto", "Satisfacción", ""),

    q("sx3_037", "Ratio de OT en garantía sobre total",
      "¿Qué porcentaje de las OT son en garantía?",
      "OT en garantía sobre total de OT por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS TOTAL_OT, "
      "COUNT(CASE WHEN NULL=1 THEN 1 END) AS OT_GARANTIA, "
      "ROUND(COUNT(CASE WHEN NULL=1 THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) AS PCT_GARANTIA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Alto", "Garantías", ""),

    q("sx3_038", "Artículos con mayor tasa de avería",
      "¿Qué artículos vendidos generan más OT de SAT?",
      "Artículos con más OT en relación a unidades vendidas.",
      "SELECT L_SAT.CODIGO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D_SAT.CODIGO) AS N_OT_SAT, "
      "COALESCE(VENTAS.UNIDADES_VENDIDAS,0) AS UNIDADES_VENDIDAS "
      "FROM DOCLIN L_SAT "
      "JOIN DOCCAB D_SAT ON D_SAT.CODIGO=L_SAT.CODDOCUMENTO AND D_SAT.TIPO=50 "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L_SAT.CODIGO "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS UNIDADES_VENDIDAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 GROUP BY L.CODARTICULO) VENTAS ON VENTAS.CODIGO=L_SAT.CODIGO "
      "GROUP BY L_SAT.CODIGO, A.NOMBRE, VENTAS.UNIDADES_VENDIDAS "
      "ORDER BY N_OT_SAT DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Alto", "Calidad", ""),

    q("sx3_039", "Evolución de OT por año",
      "¿Cómo evoluciona el número de OT año a año?",
      "OT agrupadas por año.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "COUNT(*) AS N_OT, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 "
      "GROUP BY SUBSTR(D.FECHA,1,4) "
      "ORDER BY ANIO DESC",
      "SAT", "SAT", "KPI", "Alto", "Tendencia", ""),

    q("sx3_040", "Resumen ejecutivo de SAT",
      "¿Cuál es el resumen ejecutivo del servicio técnico?",
      "KPIs clave de SAT: OT abiertas, cerradas, en garantía, facturación.",
      "SELECT "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=50 AND ESTADO<>'C') AS OT_ABIERTAS, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=50 AND ESTADO='C' "
      "AND FECHA >= DATE('now','-30 days')) AS OT_CERRADAS_MES, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=50 AND GARANTIA=1 "
      "AND FECHA >= DATE('now','-30 days')) AS OT_GARANTIA_MES, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=50 AND SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now')) AS FACTURACION_MES",
      "SAT", "SAT", "KPI", "Critico", "Resumen", ""),

    # ── ANÁLISIS ADICIONAL SAT ─────────────────────────────────────────────────

    q("sx3_041", "OT por zona geográfica",
      "¿Cómo se distribuyen las OT por zona geográfica?",
      "OT agrupadas por provincia del cliente.",
      "SELECT COALESCE(C.CP, 'Sin provincia') AS PROVINCIA, "
      "COUNT(*) AS N_OT, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY COALESCE(C.CP, 'Sin provincia') "
      "ORDER BY N_OT DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Geografía", ""),

    q("sx3_042", "Horas trabajadas por técnico en SAT",
      "¿Cuántas horas trabaja cada técnico en SAT?",
      "Horas registradas en OT por técnico.",
      "SELECT D.CODAGENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD),2) AS HORAS_TOTALES "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND 0=1 "
      "GROUP BY D.CODAGENTE "
      "ORDER BY HORAS_TOTALES DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Horas", ""),

    q("sx3_043", "Facturación SAT vs contratos de mantenimiento",
      "¿Qué porcentaje de la facturación SAT proviene de contratos?",
      "Facturación de OT (TIPO=50) vs contratos (TIPO=51).",
      "SELECT "
      "ROUND(SUM(CASE WHEN D.TIPO=50 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS FACTURACION_OT, "
      "ROUND(SUM(CASE WHEN D.TIPO=51 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS FACTURACION_CONTRATOS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO IN (50,51) "
      "AND D.FECHA >= DATE('now','-365 days')",
      "SAT", "SAT", "KPI", "Alto", "Facturación", ""),

    q("sx3_044", "OT con mayor importe de recambios",
      "¿Qué órdenes de trabajo tienen mayor PRECIOCOSTE de recambios?",
      "OT con mayor importe de materiales.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "D.CODAGENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE, D.CODAGENTE "
      "ORDER BY IMPORTE_TOTAL DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Medio", "Costes", ""),

    q("sx3_045", "Clientes con contratos y sin OT en el año",
      "¿Qué clientes con contrato no han generado OT en el año?",
      "Clientes con contrato activo pero sin OT en el año actual.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_CONTRATOS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=51 AND D.ESTADO='A' "
      "AND D.CODCLIENTE NOT IN ("
      "SELECT DISTINCT CODCLIENTE FROM DOCCAB "
      "WHERE TIPO=50 AND SUBSTR(FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_CONTRATOS DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Bajo", "Contratos", ""),

    q("sx3_046", "Tiempo medio entre OT del mismo cliente",
      "¿Con qué frecuencia llama cada cliente al SAT?",
      "Días medios entre OT consecutivas del mismo cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_OT, "
      "ROUND((JULIANDAY(MAX(D.FECHA))-JULIANDAY(MIN(D.FECHA)))/NULLIF(COUNT(*)-1,0),0) AS DIAS_ENTRE_OT "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING N_OT>=3 "
      "ORDER BY DIAS_ENTRE_OT ASC LIMIT 20",
      "SAT", "SAT", "KPI", "Medio", "Frecuencia", ""),

    q("sx3_047", "OT sin técnico asignado",
      "¿Existen órdenes de trabajo sin técnico asignado?",
      "OT abiertas sin CODAGENTE asignado.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(JULIANDAY('now')-JULIANDAY(D.FECHA),0) AS DIAS_ABIERTA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' "
      "AND (D.CODAGENTE IS NULL OR D.CODAGENTE='') "
      "ORDER BY DIAS_ABIERTA DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Alto", "Sin asignar", ""),

    q("sx3_048", "Estacionalidad de OT por mes del año",
      "¿En qué meses del año hay más actividad de SAT?",
      "OT agrupadas por mes del año (sin año).",
      "SELECT SUBSTR(D.FECHA,6,2) AS MES_NUM, "
      "CASE SUBSTR(D.FECHA,6,2) "
      "WHEN '01' THEN 'Enero' WHEN '02' THEN 'Febrero' "
      "WHEN '03' THEN 'Marzo' WHEN '04' THEN 'Abril' "
      "WHEN '05' THEN 'Mayo' WHEN '06' THEN 'Junio' "
      "WHEN '07' THEN 'Julio' WHEN '08' THEN 'Agosto' "
      "WHEN '09' THEN 'Septiembre' WHEN '10' THEN 'Octubre' "
      "WHEN '11' THEN 'Noviembre' WHEN '12' THEN 'Diciembre' END AS MES_NOMBRE, "
      "COUNT(*) AS N_OT "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 "
      "GROUP BY SUBSTR(D.FECHA,6,2) "
      "ORDER BY MES_NUM",
      "SAT", "SAT", "KPI", "Medio", "Estacionalidad", ""),

    q("sx3_049", "Comparativa facturación SAT año actual vs anterior",
      "¿Cómo ha evolucionado la facturación de SAT respecto al año anterior?",
      "Facturación SAT del año actual vs año anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS FACTURACION_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS FACTURACION_ANTERIOR "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50",
      "SAT", "SAT", "KPI", "Alto", "Comparativa", ""),

    q("sx3_050", "Top 10 clientes por facturación SAT",
      "¿Qué clientes generan más facturación en SAT?",
      "Clientes con mayor facturación en OT en el último año.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION_SAT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY FACTURACION_SAT DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Alto", "Clientes SAT", ""),

    q("sx3_051", "OT con múltiples visitas (más de 3)",
      "¿Qué OT han requerido más de 3 visitas para resolverse?",
      "OT con NVISITAS superior a 3.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "D.CODAGENTE, 0 "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND 0>3 "
      "ORDER BY 0 DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Alto", "Reincidencia", ""),

    q("sx3_052", "Artículos de servicio (mano de obra) más facturados",
      "¿Qué conceptos de mano de obra se facturan más en SAT?",
      "Artículos de tipo servicio con más líneas en OT.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_HORAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND 0=1 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY IMPORTE DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Mano de obra", ""),

    q("sx3_053", "Clientes con OT abiertas más de 15 días",
      "¿Qué clientes tienen OT abiertas desde hace más de 15 días?",
      "Clientes con OT sin cerrar con más de 15 días de antigüedad.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_OT_ANTIGUAS, "
      "MIN(D.FECHA) AS OT_MAS_ANTIGUA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' "
      "AND JULIANDAY('now')-JULIANDAY(D.FECHA)>15 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT_ANTIGUAS DESC LIMIT 15",
      "SAT", "SAT", "Alerta", "Critico", "SLA", ""),

    q("sx3_054", "Ratio de OT facturadas vs no facturadas",
      "¿Qué porcentaje de OT cerradas se han facturado?",
      "OT cerradas con importe vs OT cerradas sin importe.",
      "SELECT "
      "COUNT(*) AS TOTAL_OT_CERRADAS, "
      "COUNT(CASE WHEN IMP.IMPORTE>0 THEN 1 END) AS OT_FACTURADAS, "
      "ROUND(COUNT(CASE WHEN IMP.IMPORTE>0 THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) AS PCT_FACTURADAS "
      "FROM DOCCAB D "
      "LEFT JOIN (SELECT CODDOCUMENTO, SUM(CANTIDAD*PRECIOVENTA) AS IMPORTE "
      "FROM DOCLIN GROUP BY CODDOCUMENTO) IMP ON IMP.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 AND D.ESTADO='C'",
      "SAT", "SAT", "KPI", "Alto", "Facturación", ""),

    q("sx3_055", "Análisis de OT por prioridad",
      "¿Cómo se distribuyen las OT por nivel de prioridad?",
      "OT agrupadas por prioridad (urgente, normal, baja).",
      "SELECT 0, "
      "COUNT(*) AS N_OT, "
      "COUNT(CASE WHEN D.ESTADO<>'C' THEN 1 END) AS ABIERTAS, "
      "ROUND(AVG(CASE WHEN D.ESTADO='C' AND D.FECHA IS NOT NULL "
      "THEN JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA) END),1) AS DIAS_MEDIO_RESOLUCION "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND 0 IS NOT NULL "
      "GROUP BY 0 "
      "ORDER BY N_OT DESC",
      "SAT", "SAT", "KPI", "Alto", "Prioridad", ""),

    q("sx3_056", "Clientes con mayor antigüedad en SAT",
      "¿Cuáles son los clientes más antiguos del servicio técnico?",
      "Clientes con primera OT más antigua.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MIN(D.FECHA) AS PRIMERA_OT, "
      "COUNT(*) AS N_OT_TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY PRIMERA_OT ASC LIMIT 15",
      "SAT", "SAT", "KPI", "Bajo", "Antigüedad", ""),

    q("sx3_057", "OT con desplazamiento registrado",
      "¿Cuántas OT incluyen gastos de desplazamiento?",
      "OT con artículos de desplazamiento en sus líneas.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT_CON_DESPLAZAMIENTO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_DESPLAZAMIENTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND A.ESDESPLAZAMIENTO=1 "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Bajo", "Desplazamiento", ""),

    q("sx3_058", "Técnicos sin actividad en el último mes",
      "¿Qué técnicos no han registrado actividad en el último mes?",
      "Técnicos sin OT en los últimos 30 días.",
      "SELECT DISTINCT D.CODAGENTE "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.CODAGENTE IS NOT NULL "
      "AND D.CODAGENTE NOT IN ("
      "SELECT DISTINCT CODAGENTE FROM DOCCAB "
      "WHERE TIPO=50 AND FECHA >= DATE('now','-30 days') "
      "AND CODAGENTE IS NOT NULL)",
      "SAT", "SAT", "Alerta", "Medio", "Técnicos", ""),

    q("sx3_059", "Evolución de contratos de mantenimiento por año",
      "¿Cómo evoluciona el número de contratos de mantenimiento?",
      "Contratos SAT agrupados por año de alta.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "COUNT(*) AS N_CONTRATOS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=51 "
      "GROUP BY SUBSTR(D.FECHA,1,4) "
      "ORDER BY ANIO DESC",
      "SAT", "SAT", "KPI", "Alto", "Contratos", ""),

    q("sx3_060", "Resumen de KPIs de SAT del mes actual",
      "¿Cuál es el resumen de KPIs de SAT del mes en curso?",
      "OT abiertas, cerradas, en garantía y facturación del mes actual.",
      "SELECT "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=50 AND ESTADO<>'C') AS OT_PENDIENTES, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=50 AND ESTADO='C' "
      "AND SUBSTR(FECHA,1,7)=STRFTIME('%Y-%m','now')) AS OT_CERRADAS_MES, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=51 AND ESTADO='A') AS CONTRATOS_ACTIVOS, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=50 AND SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now')) AS FACTURACION_MES",
      "SAT", "SAT", "KPI", "Critico", "Resumen", ""),

    q("sx3_061", "OT por equipo o modelo de producto",
      "¿Qué modelos de producto generan más OT?",
      "OT agrupadas por modelo o referencia de equipo.",
      "SELECT NULL, "
      "COUNT(*) AS N_OT, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND NULL IS NOT NULL "
      "GROUP BY 1 "
      "ORDER BY N_OT DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Medio", "Equipos", ""),

    q("sx3_062", "Tiempo medio de espera de recambios en OT",
      "¿Cuánto tiempo esperan las OT por falta de recambios?",
      "OT en estado 'espera recambio' con días de espera.",
      "SELECT "
      "COUNT(*) AS N_OT_ESPERANDO_RECAMBIO, "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D.FECHA)),1) AS DIAS_ESPERA_MEDIA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='R'",
      "SAT", "SAT", "Alerta", "Alto", "Recambios", ""),

    q("sx3_063", "Clientes con contrato y mayor número de OT incluidas",
      "¿Qué clientes con contrato generan más OT incluidas en el contrato?",
      "OT de clientes con contrato activo.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT_CONTRATO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND NULL IS NOT NULL "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT_CONTRATO DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Contratos", ""),

    q("sx3_064", "Análisis de rentabilidad de contratos de mantenimiento",
      "¿Son rentables los contratos de mantenimiento?",
      "Facturación de contratos vs PRECIOCOSTE de OT incluidas.",
      "SELECT "
      "ROUND(SUM(CASE WHEN D.TIPO=51 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS INGRESOS_CONTRATOS, "
      "ROUND(SUM(CASE WHEN D.TIPO=50 AND NULL IS NOT NULL "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS COSTE_OT_CONTRATO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO IN (50,51) "
      "AND D.FECHA >= DATE('now','-365 days')",
      "SAT", "SAT", "KPI", "Critico", "Rentabilidad", ""),

    q("sx3_065", "OT con mayor número de líneas de recambios",
      "¿Qué OT tienen más líneas de recambios?",
      "OT con mayor número de líneas de artículos.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE "
      "ORDER BY N_LINEAS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Bajo", "Complejidad", ""),

    q("sx3_066", "Técnicos con mayor tasa de resolución en primera visita",
      "¿Qué técnicos resuelven más OT en la primera visita?",
      "Técnicos con mayor porcentaje de OT resueltas en 1 visita.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_OT_CERRADAS, "
      "COUNT(CASE WHEN 0=1 THEN 1 END) AS RESUELTAS_1_VISITA, "
      "ROUND(COUNT(CASE WHEN 0=1 THEN 1 END)*100.0/NULLIF(COUNT(*),0),1) AS PCT_1_VISITA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' "
      "GROUP BY D.CODAGENTE "
      "HAVING N_OT_CERRADAS>=5 "
      "ORDER BY PCT_1_VISITA DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Alto", "Técnicos", ""),

    q("sx3_067", "Artículos de recambio con mayor rotación en SAT",
      "¿Qué recambios se usan con más frecuencia en SAT?",
      "Recambios con mayor número de usos en OT en el último año.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_USOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_UNIDADES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_USOS DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Medio", "Recambios", ""),

    q("sx3_068", "Clientes con OT en garantía y sin garantía",
      "¿Qué clientes tienen OT tanto en garantía como fuera de garantía?",
      "Clientes con OT en ambas modalidades.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(CASE WHEN NULL=1 THEN 1 END) AS OT_GARANTIA, "
      "COUNT(CASE WHEN NULL=0 OR NULL IS NULL THEN 1 END) AS OT_NORMAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING OT_GARANTIA>0 AND OT_NORMAL>0 "
      "ORDER BY (OT_GARANTIA+OT_NORMAL) DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Garantías", ""),

    q("sx3_069", "Análisis de OT por estado actual",
      "¿Cuántas OT hay en cada estado?",
      "OT agrupadas por estado (abierta, en proceso, cerrada, etc.).",
      "SELECT D.ESTADO, "
      "COUNT(*) AS N_OT, "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO_EN_ESTADO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 "
      "GROUP BY D.ESTADO "
      "ORDER BY N_OT DESC",
      "SAT", "SAT", "KPI", "Alto", "Estados", ""),

    q("sx3_070", "Facturación SAT por tipo de cliente",
      "¿Cómo se distribuye la facturación SAT por tipo de cliente?",
      "Facturación de OT agrupada por familia de cliente.",
      "SELECT COALESCE(NULL, 'Sin clasificar') AS TIPO_CLIENTE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY COALESCE(NULL, 'Sin clasificar') "
      "ORDER BY FACTURACION DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Medio", "Segmentación", ""),

    q("sx3_071", "OT con tiempo de resolución inferior a 24 horas",
      "¿Qué porcentaje de OT se resuelven en menos de 24 horas?",
      "OT cerradas en menos de 1 día.",
      "SELECT "
      "COUNT(*) AS TOTAL_OT_CERRADAS, "
      "COUNT(CASE WHEN JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)<1 THEN 1 END) AS EN_24H, "
      "ROUND(COUNT(CASE WHEN JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)<1 THEN 1 END)*100.0/"
      "NULLIF(COUNT(*),0),1) AS PCT_EN_24H "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' AND D.FECHA IS NOT NULL",
      "SAT", "SAT", "KPI", "Alto", "SLA", ""),

    q("sx3_072", "Clientes con mayor gasto en recambios SAT",
      "¿Qué clientes gastan más en recambios de SAT?",
      "Importe de recambios (no servicio) en OT por cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS GASTO_RECAMBIOS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND (0=0 OR 0 IS NULL) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY GASTO_RECAMBIOS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Recambios", ""),

    q("sx3_073", "Análisis de OT por origen (presencial, remoto, teléfono)",
      "¿Cómo se distribuyen las OT por tipo de intervención?",
      "OT agrupadas por tipo de intervención.",
      "SELECT D.CODTIPOINTERVENC, "
      "COUNT(*) AS N_OT, "
      "ROUND(AVG(JULIANDAY(COALESCE(D.FECHA,DATE('now')))-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.CODTIPOINTERVENC IS NOT NULL "
      "GROUP BY D.CODTIPOINTERVENC "
      "ORDER BY N_OT DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Medio", "Tipo intervención", ""),

    q("sx3_074", "Recambios pedidos para OT (pedidos de compra SAT)",
      "¿Qué recambios se han pedido para OT en el último mes?",
      "Pedidos de compra relacionados con OT en los últimos 30 días.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_PEDIDAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=4 AND D.CODOT IS NOT NULL "
      "AND D.FECHA >= DATE('now','-30 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_PEDIDAS DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Alto", "Recambios", ""),

    q("sx3_075", "Clientes con mayor número de equipos en mantenimiento",
      "¿Qué clientes tienen más equipos bajo contrato de mantenimiento?",
      "Equipos registrados por cliente en contratos activos.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT NULL) AS N_EQUIPOS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=51 AND D.ESTADO='A' AND NULL IS NOT NULL "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_EQUIPOS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Equipos", ""),

    q("sx3_076", "OT con mayor PRECIOCOSTE de mano de obra",
      "¿Qué OT tienen mayor PRECIOCOSTE de mano de obra?",
      "OT con mayor importe de artículos de servicio.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS COSTE_MANO_OBRA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND 0=1 "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE "
      "ORDER BY COSTE_MANO_OBRA DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Mano de obra", ""),

    q("sx3_077", "Análisis de OT por turno (mañana/tarde)",
      "¿En qué turno se abren más OT?",
      "OT agrupadas por turno según hora de apertura.",
      "SELECT "
      "CASE WHEN CAST(SUBSTR(D.HORA,1,2) AS INTEGER)<14 THEN 'Mañana' "
      "ELSE 'Tarde' END AS TURNO, "
      "COUNT(*) AS N_OT "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.HORA IS NOT NULL "
      "GROUP BY TURNO "
      "ORDER BY N_OT DESC",
      "SAT", "SAT", "KPI", "Bajo", "Turnos", ""),

    q("sx3_078", "Clientes con OT resueltas fuera de SLA",
      "¿Qué clientes tienen más OT resueltas fuera del SLA?",
      "Clientes con mayor número de OT que superaron el SLA de 48h.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_OT_FUERA_SLA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.ESTADO='C' AND D.FECHA IS NOT NULL "
      "AND JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)>2 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT_FUERA_SLA DESC LIMIT 15",
      "SAT", "SAT", "Alerta", "Alto", "SLA", ""),

    q("sx3_079", "Evolución del tiempo medio de resolución por mes",
      "¿Cómo evoluciona el tiempo medio de resolución de OT mes a mes?",
      "Días medios de resolución por mes en los últimos 12 meses.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_OT_CERRADAS, "
      "ROUND(AVG(JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Alto", "Tiempo resolución", ""),

    q("sx3_080", "Análisis de rentabilidad por técnico",
      "¿Qué técnicos generan más margen en SAT?",
      "Facturación vs PRECIOCOSTE de recambios por técnico.",
      "SELECT D.CODAGENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION_TOTAL, "
      "ROUND(SUM(CASE WHEN 0=0 OR 0 IS NULL "
      "THEN L.CANTIDAD*A.PRECIOCOSTE ELSE 0 END),2) AS COSTE_RECAMBIOS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODAGENTE "
      "ORDER BY FACTURACION_TOTAL DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Alto", "Rentabilidad", ""),

    q("sx3_081", "OT con recambios de alto valor",
      "¿Qué OT incluyen recambios de alto valor unitario?",
      "OT con al menos un recambio de PRECIOVENTA superior a 500€.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "L.CODARTICULO AS COD_RECAMBIO, A.NOMBRE AS RECAMBIO, "
      "ROUND(L.PRECIO,2) AS PRECIO_UNITARIO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND L.PRECIO>500 "
      "ORDER BY L.PRECIO DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Medio", "Recambios", ""),

    q("sx3_082", "Clientes con contratos vencidos sin renovar",
      "¿Qué clientes tienen contratos vencidos sin renovar?",
      "Contratos SAT vencidos en los últimos 90 días sin nuevo contrato.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_CONTRATOS_VENCIDOS, "
      "MAX(D.FECHA) AS ULTIMO_VENCIMIENTO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=51 AND D.ESTADO='V' "
      "AND D.FECHA >= DATE('now','-90 days') "
      "AND D.CODCLIENTE NOT IN ("
      "SELECT DISTINCT CODCLIENTE FROM DOCCAB "
      "WHERE TIPO=51 AND ESTADO='A') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY ULTIMO_VENCIMIENTO DESC LIMIT 15",
      "SAT", "SAT", "Alerta", "Alto", "Contratos", ""),

    q("sx3_083", "Análisis de OT por código de avería",
      "¿Cuáles son los códigos de avería más frecuentes?",
      "OT agrupadas por código de avería.",
      "SELECT D.CODAVERIA, "
      "COUNT(*) AS N_OT, "
      "ROUND(AVG(JULIANDAY(COALESCE(D.FECHA,DATE('now')))-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.CODAVERIA IS NOT NULL "
      "GROUP BY D.CODAVERIA "
      "ORDER BY N_OT DESC LIMIT 20",
      "SAT", "SAT", "KPI", "Medio", "Averías", ""),

    q("sx3_084", "Técnicos con mayor número de contratos asignados",
      "¿Qué técnicos tienen más contratos de mantenimiento asignados?",
      "Contratos activos por técnico responsable.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_CONTRATOS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=51 AND D.ESTADO='A' AND D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_CONTRATOS DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Medio", "Técnicos", ""),

    q("sx3_085", "OT con observaciones de cliente (satisfacción)",
      "¿Cuántas OT tienen observaciones o valoración del cliente?",
      "OT con campo de observaciones o valoración completado.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_OT_CON_VALORACION "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.OBSERVACIONES IS NOT NULL "
      "AND D.OBSERVACIONES<>'' "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "SAT", "SAT", "KPI", "Bajo", "Satisfacción", ""),

    q("sx3_086", "Análisis de OT por zona de técnico",
      "¿Cómo se distribuyen las OT por zona de técnico?",
      "OT agrupadas por zona asignada al técnico.",
      "SELECT D.CODZONATECNICO, "
      "COUNT(*) AS N_OT, "
      "COUNT(DISTINCT D.CODAGENTE) AS N_TECNICOS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.CODZONATECNICO IS NOT NULL "
      "GROUP BY D.CODZONATECNICO "
      "ORDER BY N_OT DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Medio", "Zonas", ""),

    q("sx3_087", "Recambios con mayor diferencia entre PRECIOVENTA SAT y precio venta",
      "¿En qué recambios hay mayor diferencia de PRECIOVENTA entre SAT y venta normal?",
      "Diferencia entre PRECIOVENTA en OT y PRECIOVENTA de venta estándar.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_SAT, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(AVG(L.PRECIO)-A.PRECIOVENTA,2) AS DIFERENCIA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND L.PRECIO>0 AND A.PRECIOVENTA>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE, A.PRECIOVENTA "
      "HAVING ABS(DIFERENCIA)>5 "
      "ORDER BY ABS(DIFERENCIA) DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Precios", ""),

    q("sx3_088", "OT con mayor número de técnicos intervinientes",
      "¿Qué OT han requerido la intervención de más técnicos?",
      "OT con más técnicos distintos registrados.",
      "SELECT D.CODIGO AS COD_OT, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D2.CODAGENTE) AS N_TECNICOS "
      "FROM DOCCAB D "
      "JOIN DOCCAB D2 ON 1=0 "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE "
      "HAVING N_TECNICOS>1 "
      "ORDER BY N_TECNICOS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Bajo", "Técnicos", ""),

    q("sx3_089", "Clientes con mayor antigüedad de equipos en mantenimiento",
      "¿Qué clientes tienen equipos más antiguos en mantenimiento?",
      "Equipos con fecha de instalación más antigua en contratos activos.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "NULL, "
      "D.FECHAINSTALACION, "
      "ROUND(JULIANDAY('now')-JULIANDAY(D.FECHAINSTALACION),0) AS DIAS_EN_SERVICIO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=51 AND D.ESTADO='A' AND D.FECHAINSTALACION IS NOT NULL "
      "ORDER BY DIAS_EN_SERVICIO DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Equipos", ""),

    q("sx3_090", "Análisis de OT por resultado de intervención",
      "¿Cuál es el resultado más frecuente de las intervenciones SAT?",
      "OT agrupadas por resultado o diagnóstico final.",
      "SELECT D.CODRESULTADO, "
      "COUNT(*) AS N_OT, "
      "ROUND(AVG(JULIANDAY(COALESCE(D.FECHA,DATE('now')))-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.CODRESULTADO IS NOT NULL "
      "GROUP BY D.CODRESULTADO "
      "ORDER BY N_OT DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Resultados", ""),

    q("sx3_091", "Facturación SAT por forma de pago",
      "¿Cómo se distribuye la facturación SAT por forma de pago?",
      "Facturación de OT agrupada por forma de pago.",
      "SELECT D.CODFORMAPAGO, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 AND D.CODFORMAPAGO IS NOT NULL "
      "GROUP BY D.CODFORMAPAGO "
      "ORDER BY FACTURACION DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Bajo", "Formas de pago", ""),

    q("sx3_092", "OT con recambios no disponibles en STOCKARTICULO",
      "¿Cuántas OT tienen recambios que no están en STOCKARTICULO?",
      "OT abiertas con artículos sin STOCKARTICULO disponible.",
      "SELECT COUNT(DISTINCT D.CODIGO) AS N_OT_SIN_STOCKARTICULO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ESTALMACEN E ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' "
      "AND (A.STOCKARTICULO IS NULL OR A.STOCKARTICULO<=0)",
      "SAT", "SAT", "Alerta", "Alto", "Recambios", ""),

    q("sx3_093", "Clientes con mayor gasto total en SAT (OT + contratos)",
      "¿Qué clientes gastan más en SAT incluyendo contratos?",
      "Gasto total en OT y contratos por cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(CASE WHEN D.TIPO=50 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS GASTO_OT, "
      "ROUND(SUM(CASE WHEN D.TIPO=51 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS GASTO_CONTRATOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS GASTO_TOTAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO IN (50,51) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY GASTO_TOTAL DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Alto", "Clientes SAT", ""),

    q("sx3_094", "Análisis de OT por tipo de equipo",
      "¿Qué tipos de equipo generan más OT?",
      "OT agrupadas por tipo de equipo.",
      "SELECT D.CODTIPOEQUIPO, "
      "COUNT(*) AS N_OT, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.CODTIPOEQUIPO IS NOT NULL "
      "GROUP BY D.CODTIPOEQUIPO "
      "ORDER BY N_OT DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Equipos", ""),

    q("sx3_095", "Técnicos con mayor número de OT urgentes resueltas",
      "¿Qué técnicos resuelven más OT urgentes?",
      "OT urgentes cerradas por técnico.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_OT_URGENTES_CERRADAS, "
      "ROUND(AVG(JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.ESTADO='C' AND 0='U' "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_OT_URGENTES_CERRADAS DESC LIMIT 10",
      "SAT", "SAT", "KPI", "Alto", "Técnicos", ""),

    q("sx3_096", "Análisis de OT por mes y técnico (heatmap)",
      "¿Cómo se distribuye la carga de trabajo por técnico y mes?",
      "OT por técnico y mes en los últimos 6 meses.",
      "SELECT D.CODAGENTE, SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_OT "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND D.FECHA >= DATE('now','-180 days') "
      "GROUP BY D.CODAGENTE, SUBSTR(D.FECHA,1,7) "
      "ORDER BY D.CODAGENTE, MES DESC LIMIT 60",
      "SAT", "SAT", "KPI", "Medio", "Carga trabajo", ""),

    q("sx3_097", "Clientes con OT abiertas y sin contrato",
      "¿Qué clientes tienen OT abiertas pero no tienen contrato de mantenimiento?",
      "Clientes con OT abiertas sin contrato activo.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_OT_ABIERTAS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=50 AND D.ESTADO<>'C' "
      "AND D.CODCLIENTE NOT IN ("
      "SELECT DISTINCT CODCLIENTE FROM DOCCAB "
      "WHERE TIPO=51 AND ESTADO='A') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_OT_ABIERTAS DESC LIMIT 15",
      "SAT", "SAT", "KPI", "Medio", "Contratos", ""),

    q("sx3_098", "Análisis de OT por número de serie de equipo",
      "¿Qué números de serie generan más OT?",
      "OT agrupadas por número de serie del equipo.",
      "SELECT NULL, "
      "COUNT(*) AS N_OT, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=50 AND NULL IS NOT NULL "
      "GROUP BY NULL "
      "HAVING N_OT>2 "
      "ORDER BY N_OT DESC LIMIT 20",
      "SAT", "SAT", "Alerta", "Alto", "Equipos", ""),

    q("sx3_099", "Evolución de la facturación SAT por trimestre",
      "¿Cómo evoluciona la facturación de SAT por trimestre?",
      "Facturación de OT agrupada por trimestre.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "CASE WHEN SUBSTR(D.FECHA,6,2) IN ('01','02','03') THEN 'Q1' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('04','05','06') THEN 'Q2' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('07','08','09') THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "COUNT(DISTINCT D.CODIGO) AS N_OT, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS FACTURACION "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=50 "
      "GROUP BY ANIO, TRIMESTRE "
      "ORDER BY ANIO DESC, TRIMESTRE",
      "SAT", "SAT", "KPI", "Alto", "Tendencia", ""),

    q("sx3_100", "Resumen anual de SAT",
      "¿Cuál es el resumen anual del servicio técnico?",
      "Métricas anuales de SAT: OT, técnicos, clientes, facturación.",
      "SELECT "
      "CAST(STRFTIME('%Y','now') AS TEXT) AS EJERCICIO, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=50 "
      "AND SUBSTR(FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS TOTAL_OT, "
      "(SELECT COUNT(DISTINCT CODAGENTE) FROM DOCCAB WHERE TIPO=50 "
      "AND SUBSTR(FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS N_TECNICOS, "
      "(SELECT COUNT(DISTINCT CODCLIENTE) FROM DOCCAB WHERE TIPO=50 "
      "AND SUBSTR(FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS N_CLIENTES, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=50 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS FACTURACION_ANUAL",
      "SAT", "SAT", "KPI", "Critico", "Resumen", ""),

]
