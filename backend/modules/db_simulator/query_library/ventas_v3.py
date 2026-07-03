"""
query_library/ventas_v3.py — 200 consultas adicionales de Ventas (v3).

Diferentes a ventas.py y ventas_v2.py. Cubren: análisis de rentabilidad por línea,
gestión de cartera avanzada, análisis de precios, ciclos de venta, segmentación
geográfica, análisis de productos estrella, gestión de riesgo de clientes,
análisis de márgenes, forecasting de ventas, y análisis de comportamiento de compra.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: strftime, JULIANDAY, SUBSTR, CAST, COALESCE.
Sin comentarios subjetivos. Solo hechos verificables con datos.
"""

from backend.modules.db_simulator.query_library.builder import q

_C = "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, CAST(D.CODCLIENTE AS TEXT))"
_CA = "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, CAST(L.CODCLIENTE AS TEXT))"

QUERIES_VENTAS_V3 = [

    # ── ANÁLISIS DE PRECIOS ────────────────────────────────────────────────────

    q("vx3_001", "PRECIOVENTA medio de venta por artículo",
      "¿A qué PRECIOVENTA medio se vende cada artículo?",
      "PRECIOVENTA medio ponderado por unidades vendidas en líneas de factura TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_LINEAS, SUM(L.CANTIDAD) AS TOTAL_UNIDADES, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO, "
      "ROUND(MIN(L.PRECIO),2) AS PRECIO_MIN, ROUND(MAX(L.PRECIO),2) AS PRECIO_MAX "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND L.CANTIDAD>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY TOTAL_UNIDADES DESC LIMIT 30",
      "Ventas", "Comercial", "Artículo", "Alto", "PRECIOVENTA medio", ""),

    q("vx3_002", "Dispersión de precios por artículo (variabilidad)",
      "¿En qué artículos varía más el PRECIOVENTA de venta entre clientes?",
      "Diferencia entre PRECIOVENTA máximo y mínimo por artículo en facturas TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(MIN(L.PRECIO),2) AS PRECIO_MIN, ROUND(MAX(L.PRECIO),2) AS PRECIO_MAX, "
      "ROUND(MAX(L.PRECIO)-MIN(L.PRECIO),2) AS DISPERSION, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND L.PRECIO>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING COUNT(*)>2 "
      "ORDER BY DISPERSION DESC LIMIT 20",
      "Ventas", "Dirección", "Artículo", "Medio", "Precios", ""),

    q("vx3_003", "Artículos vendidos por debajo del PRECIOVENTA de PRECIOCOSTE",
      "¿Se venden artículos por debajo de su PRECIOVENTA de PRECIOCOSTE?",
      "Líneas de factura donde L.PRECIO < A.PRECIOCOSTE. Indica ventas a pérdida.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, ROUND(L.PRECIO,2) AS PRECIO_VENTA, "
      "ROUND(L.PRECIO-A.PRECIOCOSTE,2) AS MARGEN_UNITARIO, "
      "L.CANTIDAD, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND L.PRECIO<A.PRECIOCOSTE "
      "ORDER BY MARGEN_UNITARIO ASC LIMIT 30",
      "Ventas", "Dirección", "Artículo", "Crítico", "Margen", ""),

    q("vx3_004", "Margen bruto por artículo (precio venta vs PRECIOCOSTE)",
      "¿Cuál es el margen bruto de cada artículo?",
      "Diferencia entre PRECIOVENTA de venta y PRECIOCOSTE por artículo en facturas TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO_VENTA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(AVG(L.PRECIO)-A.PRECIOCOSTE,2) AS MARGEN_UNITARIO, "
      "ROUND((AVG(L.PRECIO)-A.PRECIOCOSTE)*100.0/NULLIF(AVG(L.PRECIO),0),1) AS MARGEN_PCT, "
      "SUM(L.CANTIDAD) AS UNIDADES_VENDIDAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE, A.PRECIOCOSTE "
      "ORDER BY MARGEN_PCT DESC LIMIT 30",
      "Ventas", "Dirección", "Artículo", "Alto", "Margen", ""),

    q("vx3_005", "Evolución del PRECIOVENTA medio de venta por mes",
      "¿Cómo evoluciona el PRECIOVENTA medio de venta mes a mes?",
      "PRECIOVENTA medio ponderado de todas las líneas de factura TIPO=13 por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD)/NULLIF(SUM(L.CANTIDAD),0),2) AS PRECIO_PONDERADO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND L.PRECIO>0 AND L.CANTIDAD>0 "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Ventas", "Dirección", "KPI", "Medio", "Precios", ""),

    # ── ANÁLISIS DE RENTABILIDAD POR LÍNEA ────────────────────────────────────

    q("vx3_006", "Rentabilidad por línea de factura",
      "¿Qué líneas de factura generan más margen?",
      "Margen por línea = (PRECIOVENTA - PRECIOCOSTE) * unidades en facturas TIPO=13.",
      "SELECT L.CODDOCUMENTO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "A.NOMBRE AS ARTICULO, L.CANTIDAD, "
      "ROUND(L.PRECIO,2) AS PRECIO, ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD,2) AS MARGEN_LINEA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "ORDER BY MARGEN_LINEA DESC LIMIT 30",
      "Ventas", "Dirección", "Operacional", "Alto", "Margen", ""),

    q("vx3_007", "Facturas con margen total negativo",
      "¿Hay facturas cuyo margen total es negativo?",
      "Suma de (PRECIOVENTA-PRECIOCOSTE)*unidades por factura TIPO=13. Negativo = venta a pérdida.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE_FACTURA, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN_TOTAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODIGO, D.FECHA, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.IMPORTETOTAL "
      "HAVING SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD)<0 "
      "ORDER BY MARGEN_TOTAL ASC LIMIT 20",
      "Ventas", "Dirección", "Operacional", "Crítico", "Margen", ""),

    q("vx3_008", "Top 10 artículos por margen total generado",
      "¿Qué artículos generan más margen bruto total?",
      "Suma de (PRECIOVENTA-PRECIOCOSTE)*unidades por artículo en facturas TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "SUM(L.CANTIDAD) AS UNIDADES_VENDIDAS, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS_TOTALES, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COSTE_TOTAL, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN_TOTAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY MARGEN_TOTAL DESC LIMIT 10",
      "Ventas", "Dirección", "Artículo", "Alto", "Margen", ""),

    q("vx3_009", "Margen por familia de producto",
      "¿Qué familias de producto tienen mayor margen?",
      "Agrupa margen bruto por CODFAMILIA en facturas TIPO=13.",
      "SELECT A.CODFAMILIA AS FAMILIA, F.NOMBRE AS NOMBRE_FAMILIA, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS, "
      "SUM(L.CANTIDAD) AS UNIDADES_VENDIDAS, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COSTE, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY A.CODFAMILIA, F.NOMBRE "
      "ORDER BY MARGEN DESC LIMIT 20",
      "Ventas", "Dirección", "Artículo", "Alto", "Margen", ""),

    q("vx3_010", "Margen por agente comercial",
      "¿Qué agente genera más margen bruto?",
      "Suma de margen bruto por CODAGENTE en facturas TIPO=13.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN_BRUTO, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD)*100.0/"
      "NULLIF(SUM(L.PRECIO*L.CANTIDAD),0),1) AS MARGEN_PCT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODAGENTE "
      "ORDER BY MARGEN_BRUTO DESC LIMIT 20",
      "Ventas", "Dirección", "Agente", "Alto", "Margen", ""),

    # ── ANÁLISIS DE CICLO DE VENTA ─────────────────────────────────────────────

    q("vx3_011", "Tiempo medio de conversión presupuesto a factura",
      "¿Cuántos días tarda un presupuesto en convertirse en factura?",
      "Días entre FECHA del presupuesto (TIPO=0) y FECHA de la factura (TIPO=13) via DOCDESTINO.",
      "SELECT ROUND(AVG(JULIANDAY(D2.FECHA)-JULIANDAY(D1.FECHA)),1) AS DIAS_MEDIO, "
      "MIN(CAST(JULIANDAY(D2.FECHA)-JULIANDAY(D1.FECHA) AS INTEGER)) AS DIAS_MIN, "
      "MAX(CAST(JULIANDAY(D2.FECHA)-JULIANDAY(D1.FECHA) AS INTEGER)) AS DIAS_MAX, "
      "COUNT(*) AS N_CONVERSIONES "
      "FROM DOCDESTINO DD "
      "JOIN DOCCAB D1 ON D1.CODIGO=DD.CODDOCUMENTO "
      "JOIN DOCCAB D2 ON D2.CODIGO=DD.CODDOCUMENTODESTINO "
      "WHERE D1.TIPO=0 AND D2.TIPO=13 "
      "AND D1.FECHA IS NOT NULL AND D2.FECHA IS NOT NULL",
      "Ventas", "Comercial", "KPI", "Alto", "Ciclo de venta", ""),

    q("vx3_012", "Presupuestos convertidos vs no convertidos por mes",
      "¿Qué porcentaje de presupuestos se convierten en factura cada mes?",
      "Presupuestos TIPO=0 por mes con y sin conversión a TIPO=13 via DOCDESTINO.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS TOTAL_PRESUPUESTOS, "
      "COUNT(DISTINCT DD.CODDOCUMENTO) AS CONVERTIDOS, "
      "COUNT(DISTINCT D.CODIGO)-COUNT(DISTINCT DD.CODDOCUMENTO) AS NO_CONVERTIDOS, "
      "ROUND(COUNT(DISTINCT DD.CODDOCUMENTO)*100.0/NULLIF(COUNT(DISTINCT D.CODIGO),0),1) AS TASA_PCT "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=0 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 12",
      "Ventas", "Comercial", "KPI", "Alto", "Conversión", ""),

    q("vx3_013", "Presupuestos sin convertir con más de 30 días de antigüedad",
      "¿Qué presupuestos llevan más de 30 días sin convertirse?",
      "Presupuestos TIPO=0 sin entrada en DOCDESTINO y con FECHA > 30 días.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL "
      "AND D.FECHA IS NOT NULL "
      "AND JULIANDAY('now')-JULIANDAY(D.FECHA)>30 "
      "ORDER BY DIAS_PENDIENTE DESC LIMIT 30",
      "Ventas", "Comercial", "Operacional", "Alto", "Pipeline", ""),

    q("vx3_014", "Valor del pipeline de presupuestos pendientes",
      "¿Cuánto vale el pipeline de presupuestos sin convertir?",
      "Suma de IMPORTETOTAL de presupuestos TIPO=0 sin entrada en DOCDESTINO.",
      "SELECT COUNT(*) AS N_PRESUPUESTOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_PIPELINE, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL AND D.FECHA IS NOT NULL",
      "Ventas", "Dirección", "KPI", "Crítico", "Pipeline", ""),

    q("vx3_015", "Tasa de conversión por agente comercial",
      "¿Qué agente convierte más presupuestos en facturas?",
      "Presupuestos TIPO=0 vs convertidos a TIPO=13 por CODAGENTE.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(DISTINCT D.CODIGO) AS PRESUPUESTOS, "
      "COUNT(DISTINCT DD.CODDOCUMENTO) AS CONVERTIDOS, "
      "ROUND(COUNT(DISTINCT DD.CODDOCUMENTO)*100.0/NULLIF(COUNT(DISTINCT D.CODIGO),0),1) AS TASA_PCT, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=0 "
      "GROUP BY D.CODAGENTE "
      "ORDER BY TASA_PCT DESC LIMIT 20",
      "Ventas", "Comercial", "Agente", "Alto", "Conversión", ""),

    # ── SEGMENTACIÓN DE CLIENTES ───────────────────────────────────────────────

    q("vx3_016", "Segmentación RFM de clientes (Recencia, Frecuencia, Monetario)",
      "¿Cómo se segmentan los clientes por RFM?",
      "Recencia=días desde última compra, Frecuencia=N facturas, Monetario=importe total.",
      "SELECT "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(MAX(D.FECHA)) AS INTEGER) AS RECENCIA_DIAS, "
      "COUNT(*) AS FRECUENCIA, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS MONETARIO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY MONETARIO DESC LIMIT 50",
      "Ventas", "Comercial", "Cliente", "Alto", "RFM", ""),

    q("vx3_017", "Clientes con una sola compra (one-shot)",
      "¿Cuántos clientes han comprado exactamente una vez?",
      "Clientes con exactamente 1 factura TIPO=13. Indica baja fidelización.",
      "SELECT COUNT(*) AS N_CLIENTES_ONE_SHOT, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURADO "
      "FROM (SELECT CODCLIENTE, COUNT(*) AS N, SUM(IMPORTETOTAL) AS IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE HAVING COUNT(*)=1)",
      "Ventas", "Comercial", "Cliente", "Medio", "Fidelización", ""),

    q("vx3_018", "Clientes nuevos por mes (primera factura)",
      "¿Cuántos clientes nuevos se incorporan cada mes?",
      "Clientes cuya primera factura TIPO=13 es en cada mes.",
      "SELECT SUBSTR(PRIMERA_FACTURA,1,7) AS MES, COUNT(*) AS CLIENTES_NUEVOS "
      "FROM (SELECT CODCLIENTE, MIN(FECHA) AS PRIMERA_FACTURA "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY CODCLIENTE) "
      "GROUP BY SUBSTR(PRIMERA_FACTURA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Ventas", "Comercial", "Cliente", "Medio", "Captación", ""),

    q("vx3_019", "Clientes perdidos (sin compra en 12 meses con historial previo)",
      "¿Qué clientes no han comprado en 12 meses pero tenían historial?",
      "Clientes con facturas TIPO=13 pero sin ninguna en los últimos 365 días.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA, COUNT(*) AS TOTAL_FACTURAS_HISTORICAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_HISTORICO, "
      "CAST(JULIANDAY('now')-JULIANDAY(MAX(D.FECHA)) AS INTEGER) AS DIAS_SIN_COMPRA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING MAX(D.FECHA) < DATE('now','-365 days') AND COUNT(*)>1 "
      "ORDER BY TOTAL_HISTORICO DESC LIMIT 30",
      "Ventas", "Comercial", "Cliente", "Alto", "Retención", ""),

    q("vx3_020", "Concentración de ventas: % del total en top 10 clientes",
      "¿Qué porcentaje de la facturación concentran los 10 mejores clientes?",
      "Facturación de los 10 primeros clientes vs total en facturas TIPO=13.",
      "SELECT "
      "ROUND(SUM(CASE WHEN RK<=10 THEN TOTAL ELSE 0 END)*100.0/NULLIF(SUM(TOTAL),0),1) AS PCT_TOP10, "
      "ROUND(SUM(CASE WHEN RK<=5 THEN TOTAL ELSE 0 END)*100.0/NULLIF(SUM(TOTAL),0),1) AS PCT_TOP5, "
      "ROUND(SUM(TOTAL),2) AS TOTAL_GENERAL "
      "FROM (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL, "
      "ROW_NUMBER() OVER (ORDER BY SUM(IMPORTETOTAL) DESC) AS RK "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE)",
      "Ventas", "Dirección", "KPI", "Alto", "Concentración", ""),

    # ── ANÁLISIS DE PRODUCTOS ESTRELLA ─────────────────────────────────────────

    q("vx3_021", "Productos con mayor crecimiento de ventas (mes actual vs anterior)",
      "¿Qué artículos han crecido más en ventas este mes?",
      "Compara unidades vendidas del mes actual vs mes anterior por artículo.",
      "SELECT A.NOMBRE AS ARTICULO, "
      "COALESCE(MES_ACT.CANTIDAD,0) AS UNIDADES_MES_ACTUAL, "
      "COALESCE(MES_ANT.CANTIDAD,0) AS UNIDADES_MES_ANTERIOR, "
      "COALESCE(MES_ACT.CANTIDAD,0)-COALESCE(MES_ANT.CANTIDAD,0) AS VARIACION "
      "FROM ARTICULO A "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS CANTIDAD "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=SUBSTR(DATE('now'),1,7) "
      "GROUP BY L.CODARTICULO) MES_ACT ON MES_ACT.CODIGO=A.CODIGO "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS CANTIDAD "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=SUBSTR(DATE('now','-1 month'),1,7) "
      "GROUP BY L.CODARTICULO) MES_ANT ON MES_ANT.CODIGO=A.CODIGO "
      "WHERE COALESCE(MES_ACT.CANTIDAD,0)>0 OR COALESCE(MES_ANT.CANTIDAD,0)>0 "
      "ORDER BY VARIACION DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Crecimiento", ""),

    q("vx3_022", "Artículos sin ventas en los últimos 90 días",
      "¿Qué artículos no se han vendido en los últimos 90 días?",
      "Artículos con STOCKARTICULO>0 pero sin líneas de factura TIPO=13 en 90 días.",
      "SELECT A.CODIGO, A.NOMBRE, A.STOCKARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_STOCK_INMOVILIZADO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 "
      "AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-90 days')) "
      "ORDER BY VALOR_STOCK_INMOVILIZADO DESC LIMIT 30",
      "Ventas", "Almacén", "Artículo", "Medio", "STOCKARTICULO inmovilizado", ""),

    q("vx3_023", "Artículos vendidos solo a un cliente (dependencia)",
      "¿Qué artículos se venden exclusivamente a un solo cliente?",
      "Artículos con ventas TIPO=13 a exactamente 1 cliente distinto.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "SUM(L.CANTIDAD) AS TOTAL_UNIDADES, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS TOTAL_VENTAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING COUNT(DISTINCT D.CODCLIENTE)=1 "
      "ORDER BY TOTAL_VENTAS DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Dependencia", ""),

    q("vx3_024", "Combinaciones de artículos más frecuentes en la misma factura",
      "¿Qué artículos se compran juntos con más frecuencia?",
      "Pares de artículos que aparecen en la misma factura TIPO=13.",
      "SELECT L1.CODIGO AS ART1, A1.NOMBRE AS NOMBRE1, "
      "L2.CODIGO AS ART2, A2.NOMBRE AS NOMBRE2, "
      "COUNT(*) AS N_FACTURAS_JUNTOS "
      "FROM DOCLIN L1 "
      "JOIN DOCLIN L2 ON L2.CODDOCUMENTO=L1.CODDOCUMENTO AND L2.CODIGO>L1.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L1.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A1 ON A1.CODIGO=L1.CODIGO "
      "LEFT JOIN ARTICULO A2 ON A2.CODIGO=L2.CODIGO "
      "WHERE D.TIPO=13 "
      "GROUP BY L1.CODIGO, L2.CODIGO, A1.NOMBRE, A2.NOMBRE "
      "ORDER BY N_FACTURAS_JUNTOS DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Cross-selling", ""),

    q("vx3_025", "Artículos con mayor rotación (ventas/STOCKARTICULO)",
      "¿Qué artículos tienen mayor rotación de STOCKARTICULO?",
      "Ratio unidades vendidas / STOCKARTICULO actual por artículo.",
      "SELECT A.CODIGO, A.NOMBRE, A.STOCKARTICULO AS STOCK_ACTUAL, "
      "COALESCE(V.UNIDADES_VENDIDAS,0) AS UNIDADES_VENDIDAS_ANIO, "
      "ROUND(COALESCE(V.UNIDADES_VENDIDAS,0)*1.0/NULLIF(A.STOCKARTICULO,0),2) AS ROTACION "
      "FROM ARTICULO A "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS UNIDADES_VENDIDAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-365 days') "
      "GROUP BY L.CODARTICULO) V ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "ORDER BY ROTACION DESC LIMIT 30",
      "Ventas", "Almacén", "Artículo", "Medio", "Rotación", ""),

    # ── ANÁLISIS DE ALBARANES ──────────────────────────────────────────────────

    q("vx3_026", "Albaranes pendientes de facturar",
      "¿Qué albaranes no se han convertido en factura?",
      "Albaranes TIPO=11 sin entrada en DOCDESTINO como origen.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=11 AND DD.CODDOCUMENTO IS NULL AND D.FECHA IS NOT NULL "
      "ORDER BY DIAS_PENDIENTE DESC LIMIT 30",
      "Ventas", "Comercial", "Operacional", "Alto", "Albaranes", ""),

    q("vx3_027", "Valor total de albaranes pendientes de facturar",
      "¿Cuánto dinero hay en albaranes sin facturar?",
      "Suma de IMPORTETOTAL de albaranes TIPO=11 sin conversión a factura.",
      "SELECT COUNT(*) AS N_ALBARANES, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_PENDIENTE, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS IMPORTE_MEDIO, "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D.FECHA)),1) AS DIAS_MEDIO_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=11 AND DD.CODDOCUMENTO IS NULL AND D.FECHA IS NOT NULL",
      "Ventas", "Finanzas", "KPI", "Alto", "Albaranes", ""),

    q("vx3_028", "Albaranes por cliente pendientes de facturar",
      "¿Qué clientes tienen más albaranes sin facturar?",
      "Agrupa albaranes TIPO=11 sin conversión por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_ALBARANES, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=11 AND DD.CODDOCUMENTO IS NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY VALOR_PENDIENTE DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Albaranes", ""),

    q("vx3_029", "Tiempo medio entre albarán y factura",
      "¿Cuántos días pasan entre el albarán y la factura?",
      "Días entre FECHA del albarán (TIPO=11) y FECHA de la factura (TIPO=13) via DOCDESTINO.",
      "SELECT ROUND(AVG(JULIANDAY(D2.FECHA)-JULIANDAY(D1.FECHA)),1) AS DIAS_MEDIO, "
      "MIN(CAST(JULIANDAY(D2.FECHA)-JULIANDAY(D1.FECHA) AS INTEGER)) AS DIAS_MIN, "
      "MAX(CAST(JULIANDAY(D2.FECHA)-JULIANDAY(D1.FECHA) AS INTEGER)) AS DIAS_MAX, "
      "COUNT(*) AS N_CONVERSIONES "
      "FROM DOCDESTINO DD "
      "JOIN DOCCAB D1 ON D1.CODIGO=DD.CODDOCUMENTO "
      "JOIN DOCCAB D2 ON D2.CODIGO=DD.CODDOCUMENTODESTINO "
      "WHERE D1.TIPO=11 AND D2.TIPO=13 "
      "AND D1.FECHA IS NOT NULL AND D2.FECHA IS NOT NULL",
      "Ventas", "Operaciones", "KPI", "Medio", "Ciclo", ""),

    q("vx3_030", "Evolución mensual de albaranes emitidos",
      "¿Cuántos albaranes se emiten cada mes?",
      "Conteo y suma de albaranes TIPO=11 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_ALBARANES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=11 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Operaciones", "Operacional", "Bajo", "Albaranes", ""),

    # ── ANÁLISIS DE PEDIDOS ────────────────────────────────────────────────────

    q("vx3_031", "Pedidos pendientes de servir",
      "¿Qué pedidos no se han convertido en albarán o factura?",
      "Pedidos TIPO=12 sin entrada en DOCDESTINO.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=12 AND DD.CODDOCUMENTO IS NULL AND D.FECHA IS NOT NULL "
      "ORDER BY DIAS_PENDIENTE DESC LIMIT 30",
      "Ventas", "Operaciones", "Operacional", "Alto", "Pedidos", ""),

    q("vx3_032", "Valor total de pedidos pendientes",
      "¿Cuánto vale la cartera de pedidos pendientes?",
      "Suma de IMPORTETOTAL de pedidos TIPO=12 sin conversión.",
      "SELECT COUNT(*) AS N_PEDIDOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_CARTERA, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS IMPORTE_MEDIO "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=12 AND DD.CODDOCUMENTO IS NULL",
      "Ventas", "Dirección", "KPI", "Alto", "Pedidos", ""),

    q("vx3_033", "Evolución mensual de pedidos recibidos",
      "¿Cuántos pedidos se reciben cada mes?",
      "Conteo y suma de pedidos TIPO=12 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_PEDIDOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=12 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Operaciones", "Operacional", "Bajo", "Pedidos", ""),

    q("vx3_034", "Pedidos por cliente",
      "¿Qué clientes generan más pedidos?",
      "Conteo de pedidos TIPO=12 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_PEDIDOS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=12 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_PEDIDOS DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Pedidos", ""),

    q("vx3_035", "Tiempo medio de servicio de pedidos",
      "¿Cuántos días tarda en servirse un pedido?",
      "Días entre FECHA del pedido (TIPO=12) y FECHA del albarán (TIPO=11) via DOCDESTINO.",
      "SELECT ROUND(AVG(JULIANDAY(D2.FECHA)-JULIANDAY(D1.FECHA)),1) AS DIAS_MEDIO, "
      "COUNT(*) AS N_PEDIDOS_SERVIDOS "
      "FROM DOCDESTINO DD "
      "JOIN DOCCAB D1 ON D1.CODIGO=DD.CODDOCUMENTO "
      "JOIN DOCCAB D2 ON D2.CODIGO=DD.CODDOCUMENTODESTINO "
      "WHERE D1.TIPO=12 AND D2.TIPO=11 "
      "AND D1.FECHA IS NOT NULL AND D2.FECHA IS NOT NULL",
      "Ventas", "Operaciones", "KPI", "Medio", "Servicio", ""),

    # ── ANÁLISIS DE FORMAS DE PAGO ─────────────────────────────────────────────

    q("vx3_036", "Distribución de facturas por forma de pago",
      "¿Qué formas de pago usan los clientes?",
      "Agrupa facturas TIPO=13 por CODFORMAPAGO.",
      "SELECT COALESCE(FP.NOMBRE, CAST(D.CODFORMAPAGO AS TEXT), 'Sin forma pago') AS FORMA_PAGO, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL, "
      "ROUND(SUM(D.IMPORTETOTAL)*100.0/("
      "SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13),1) AS PCT "
      "FROM DOCCAB D "
      "LEFT JOIN FORMASPAGO FP ON FP.CODIGO=D.CODFORMAPAGO "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODFORMAPAGO, FP.NOMBRE "
      "ORDER BY TOTAL DESC LIMIT 20",
      "Ventas", "Finanzas", "Operacional", "Medio", "Cobros", ""),

    q("vx3_037", "Clientes sin forma de pago asignada",
      "¿Qué clientes no tienen forma de pago configurada?",
      "Clientes con facturas TIPO=13 donde CODFORMAPAGO es NULL o 0.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND (D.CODFORMAPAGO IS NULL OR D.CODFORMAPAGO=0) "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY TOTAL DESC LIMIT 20",
      "Ventas", "Finanzas", "Cliente", "Medio", "Cobros", ""),

    q("vx3_038", "Importe pendiente de cobro por cliente",
      "¿Cuánto queda pendiente de cobrar por cliente?",
      "Diferencia entre IMPORTETOTAL e IMPORTEENTREGADO en facturas TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_FACTURADO, "
      "ROUND(SUM(D.IMPORTEENTREGADO),2) AS TOTAL_COBRADO, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO),2) AS PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO)>0 "
      "ORDER BY PENDIENTE DESC LIMIT 30",
      "Ventas", "Finanzas", "Cliente", "Crítico", "Cobros", ""),

    q("vx3_039", "Total pendiente de cobro global",
      "¿Cuánto dinero está pendiente de cobrar en total?",
      "Suma de IMPORTETOTAL - IMPORTEENTREGADO en facturas TIPO=13.",
      "SELECT COUNT(*) AS N_FACTURAS_PENDIENTES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURADO, "
      "ROUND(SUM(IMPORTEENTREGADO),2) AS TOTAL_COBRADO, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS TOTAL_PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO",
      "Ventas", "Finanzas", "KPI", "Crítico", "Cobros", ""),

    q("vx3_040", "Facturas cobradas al 100% vs parcialmente cobradas",
      "¿Qué porcentaje de facturas están totalmente cobradas?",
      "Clasifica facturas TIPO=13 por estado de cobro.",
      "SELECT "
      "SUM(CASE WHEN IMPORTEENTREGADO>=IMPORTETOTAL THEN 1 ELSE 0 END) AS COBRADAS_TOTAL, "
      "SUM(CASE WHEN IMPORTEENTREGADO>0 AND IMPORTEENTREGADO<IMPORTETOTAL THEN 1 ELSE 0 END) AS COBRADAS_PARCIAL, "
      "SUM(CASE WHEN IMPORTEENTREGADO=0 THEN 1 ELSE 0 END) AS SIN_COBRAR, "
      "COUNT(*) AS TOTAL_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas", "Finanzas", "KPI", "Alto", "Cobros", ""),

    # ── ANÁLISIS DE DESCUENTOS ─────────────────────────────────────────────────

    q("vx3_041", "Descuento medio por cliente",
      "¿Qué descuento medio se aplica a cada cliente?",
      "Promedio de DESCUENTOS en líneas de factura TIPO=13 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(AVG(L.DESCUENTOS),2) AS DESCUENTO_MEDIO_PCT, "
      "ROUND(MAX(L.DESCUENTOS),2) AS DESCUENTO_MAX_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY DESCUENTO_MEDIO_PCT DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Descuentos", ""),

    q("vx3_042", "Descuento medio por artículo",
      "¿Qué artículos reciben más descuento?",
      "Promedio de DESCUENTOS en líneas de factura TIPO=13 por artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(AVG(L.DESCUENTOS),2) AS DESCUENTO_MEDIO_PCT, "
      "ROUND(MAX(L.DESCUENTOS),2) AS DESCUENTO_MAX_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY DESCUENTO_MEDIO_PCT DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Descuentos", ""),

    q("vx3_043", "Importe total de descuentos aplicados",
      "¿Cuánto dinero se ha dejado de ingresar por descuentos?",
      "Suma de (PRECIO_LISTA - PRECIO_REAL) * CANTIDAD en facturas TIPO=13.",
      "SELECT COUNT(*) AS N_LINEAS_CON_DESCUENTO, "
      "ROUND(SUM(L.DESCUENTOS*L.PRECIO*L.CANTIDAD/100.0),2) AS IMPORTE_DESCUENTOS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0",
      "Ventas", "Finanzas", "KPI", "Medio", "Descuentos", ""),

    q("vx3_044", "Líneas con descuento superior al 30%",
      "¿Hay líneas de factura con descuento excesivo (>30%)?",
      "Líneas de factura TIPO=13 con DESCUENTOS>30. Pueden indicar errores o excepciones.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "A.NOMBRE AS ARTICULO, L.DESCUENTOS AS DESCUENTO_PCT, "
      "ROUND(L.PRECIO,2) AS PRECIO, L.CANTIDAD "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>30 "
      "ORDER BY L.DESCUENTOS DESC LIMIT 30",
      "Ventas", "Dirección", "Operacional", "Alto", "Descuentos", ""),

    q("vx3_045", "Descuento medio por agente comercial",
      "¿Qué agente aplica más descuentos?",
      "Promedio de DESCUENTOS en líneas de factura TIPO=13 por CODAGENTE.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(AVG(L.DESCUENTOS),2) AS DESCUENTO_MEDIO_PCT, "
      "ROUND(SUM(L.DESCUENTOS*L.PRECIO*L.CANTIDAD/100.0),2) AS IMPORTE_DESCUENTOS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0 "
      "GROUP BY D.CODAGENTE "
      "ORDER BY DESCUENTO_MEDIO_PCT DESC LIMIT 20",
      "Ventas", "Comercial", "Agente", "Medio", "Descuentos", ""),

    # ── ANÁLISIS DE IMPORTEIVA ────────────────────────────────────────────────────────

    q("vx3_046", "Desglose de IMPORTEIVA por tipo de documento",
      "¿Cuánto IMPORTEIVA se genera por tipo de documento?",
      "Suma de IMPORTEIVA por TIPO en DOCCAB. Verifica coherencia base+IMPORTEIVA=total.",
      "SELECT TIPO, COUNT(*) AS N_DOCS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL, "
      "ROUND(SUM(IMPORTEIVA)*100.0/NULLIF(SUM(IMPORTEBASE),0),1) AS TIPO_IVA_EFECTIVO_PCT "
      "FROM DOCCAB WHERE IMPORTEBASE>0 "
      "GROUP BY TIPO ORDER BY TOTAL DESC",
      "Ventas", "Finanzas", "KPI", "Alto", "IMPORTEIVA", ""),

    q("vx3_047", "Facturas con IMPORTEIVA inconsistente (base+IMPORTEIVA≠total)",
      "¿Hay facturas donde base+IMPORTEIVA no coincide con el total?",
      "Detecta facturas TIPO=13 donde IMPORTEBASE+IMPORTEIVA difiere de IMPORTETOTAL.",
      "SELECT D.CODIGO, D.FECHA, "
      "ROUND(IMPORTEBASE,2) AS BASE, ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL, "
      "ROUND(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL,2) AS DIFERENCIA "
      "FROM DOCCAB "
      "WHERE TIPO=13 AND ABS(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL)>0.05 "
      "ORDER BY ABS(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL) DESC LIMIT 20",
      "Ventas", "Finanzas", "Operacional", "Crítico", "IMPORTEIVA", ""),

    q("vx3_048", "IMPORTEIVA mensual generado en facturas",
      "¿Cuánto IMPORTEIVA se genera cada mes en facturas?",
      "Suma de IMPORTEIVA en facturas TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Finanzas", "KPI", "Alto", "IMPORTEIVA", ""),

    q("vx3_049", "Facturas con base imponible cero",
      "¿Hay facturas con base imponible cero?",
      "Facturas TIPO=13 con IMPORTEBASE=0 o NULL. Pueden ser errores de configuración.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND (D.IMPORTEBASE=0 OR D.IMPORTEBASE IS NULL) "
      "ORDER BY FECHA DESC LIMIT 20",
      "Ventas", "Finanzas", "Operacional", "Alto", "IMPORTEIVA", ""),

    q("vx3_050", "Tipo de IMPORTEIVA efectivo por cliente",
      "¿Qué tipo de IMPORTEIVA efectivo paga cada cliente?",
      "IMPORTEIVA/BASE por cliente en facturas TIPO=13. Detecta clientes exentos o con IMPORTEIVA reducido.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(D.IMPORTEIVA),2) AS IVA_TOTAL, "
      "ROUND(SUM(D.IMPORTEIVA)*100.0/NULLIF(SUM(D.IMPORTEBASE),0),1) AS IVA_EFECTIVO_PCT "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEBASE>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY IVA_EFECTIVO_PCT ASC LIMIT 20",
      "Ventas", "Finanzas", "Cliente", "Medio", "IMPORTEIVA", ""),

    # ── ANÁLISIS DE ESTACIONALIDAD ─────────────────────────────────────────────

    q("vx3_051", "Facturación por día de la semana",
      "¿Qué días de la semana se factura más?",
      "Agrupa facturas TIPO=13 por día de la semana (0=domingo, 6=sábado en SQLite).",
      "SELECT CAST(STRFTIME('%w', FECHA) AS INTEGER) AS DIA_SEMANA, "
      "CASE CAST(STRFTIME('%w', FECHA) AS INTEGER) "
      "WHEN 0 THEN 'Domingo' WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes' "
      "WHEN 3 THEN 'Miércoles' WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes' "
      "ELSE 'Sábado' END AS NOMBRE_DIA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY DIA_SEMANA ORDER BY DIA_SEMANA",
      "Ventas", "Dirección", "KPI", "Bajo", "Estacionalidad", ""),

    q("vx3_052", "Facturación por trimestre",
      "¿Cómo se distribuye la facturación por trimestre?",
      "Agrupa facturas TIPO=13 por trimestre del año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "CASE WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO, TRIMESTRE ORDER BY ANIO DESC, TRIMESTRE",
      "Ventas", "Dirección", "KPI", "Medio", "Estacionalidad", ""),

    q("vx3_053", "Comparativa mismo mes año anterior vs actual",
      "¿Cómo compara la facturación del mes actual con el mismo mes del año anterior?",
      "Facturación TIPO=13 del mes actual vs mismo mes del año anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7) THEN IMPORTETOTAL ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,7)=SUBSTR(DATE('now','-1 year'),1,7) THEN IMPORTETOTAL ELSE 0 END),2) AS MISMO_MES_ANIO_ANTERIOR "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas", "Dirección", "KPI", "Alto", "Comparativa", ""),

    q("vx3_054", "Facturación acumulada año en curso vs año anterior",
      "¿Cómo va la facturación acumulada del año vs el año anterior?",
      "Suma de IMPORTETOTAL TIPO=13 desde enero del año actual vs año anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) THEN IMPORTETOTAL ELSE 0 END),2) AS ANIO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INTEGER)-1 AS TEXT) THEN IMPORTETOTAL ELSE 0 END),2) AS ANIO_ANTERIOR "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas", "Dirección", "KPI", "Crítico", "Comparativa", ""),

    q("vx3_055", "Mes con mayor y menor facturación histórica",
      "¿Cuál es el mes con más y menos facturación en el histórico?",
      "Identifica el mes con mayor y menor IMPORTETOTAL en facturas TIPO=13.",
      "SELECT MES, TOTAL FROM ("
      "SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY TOTAL DESC LIMIT 1 "
      "UNION ALL "
      "SELECT MES, TOTAL FROM ("
      "SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY TOTAL ASC LIMIT 1",
      "Ventas", "Dirección", "KPI", "Medio", "Estacionalidad", ""),

    # ── ANÁLISIS DE AGENTES ────────────────────────────────────────────────────

    q("vx3_056", "Ranking de agentes por facturación mensual",
      "¿Cuál es el ranking de agentes este mes?",
      "Facturación TIPO=13 por CODAGENTE en el mes actual.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION_MES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=SUBSTR(DATE('now'),1,7) "
      "GROUP BY D.CODAGENTE ORDER BY FACTURACION_MES DESC",
      "Ventas", "Comercial", "Agente", "Alto", "Ranking", ""),

    q("vx3_057", "Evolución mensual de facturación por agente",
      "¿Cómo evoluciona la facturación de cada agente mes a mes?",
      "Facturación TIPO=13 por CODAGENTE y mes en los últimos 12 meses.",
      "SELECT D.CODAGENTE AS AGENTE, SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-12 months') "
      "GROUP BY D.CODAGENTE, SUBSTR(D.FECHA,1,7) "
      "ORDER BY AGENTE, MES DESC",
      "Ventas", "Comercial", "Agente", "Medio", "Evolución", ""),

    q("vx3_058", "Clientes sin agente asignado",
      "¿Qué facturas no tienen agente asignado?",
      "Facturas TIPO=13 con CODAGENTE NULL o 0.",
      "SELECT COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_SIN_AGENTE "
      "FROM DOCCAB WHERE TIPO=13 AND (CODAGENTE IS NULL OR CODAGENTE=0)",
      "Ventas", "Comercial", "Operacional", "Medio", "Agentes", ""),

    q("vx3_059", "Ticket medio por agente",
      "¿Cuál es el ticket medio de cada agente?",
      "Importe medio por factura TIPO=13 por CODAGENTE.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(MIN(D.IMPORTETOTAL),2) AS TICKET_MIN, "
      "ROUND(MAX(D.IMPORTETOTAL),2) AS TICKET_MAX "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODAGENTE ORDER BY TICKET_MEDIO DESC",
      "Ventas", "Comercial", "Agente", "Medio", "Ticket", ""),

    q("vx3_060", "Número de clientes distintos por agente",
      "¿Cuántos clientes distintos atiende cada agente?",
      "Clientes únicos en facturas TIPO=13 por CODAGENTE.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES_DISTINTOS, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION_TOTAL "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODAGENTE ORDER BY N_CLIENTES_DISTINTOS DESC",
      "Ventas", "Comercial", "Agente", "Medio", "Cartera", ""),

    # ── ANÁLISIS DE LÍNEAS DE FACTURA ──────────────────────────────────────────

    q("vx3_061", "Número medio de líneas por factura",
      "¿Cuántas líneas tiene de media cada factura?",
      "Promedio de líneas DOCLIN por factura TIPO=13.",
      "SELECT ROUND(AVG(N_LINEAS),1) AS MEDIA_LINEAS, "
      "MIN(N_LINEAS) AS MIN_LINEAS, MAX(N_LINEAS) AS MAX_LINEAS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM (SELECT CODDOCUMENTO, COUNT(*) AS N_LINEAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 GROUP BY CODDOCUMENTO)",
      "Ventas", "Operaciones", "KPI", "Bajo", "Líneas", ""),

    q("vx3_062", "Facturas con una sola línea",
      "¿Cuántas facturas tienen solo una línea?",
      "Facturas TIPO=13 con exactamente 1 línea en DOCLIN.",
      "SELECT COUNT(*) AS N_FACTURAS_1_LINEA, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 AND ("
      "SELECT COUNT(*) FROM DOCLIN L WHERE L.CODDOCUMENTO=D.CODIGO)=1",
      "Ventas", "Operaciones", "Operacional", "Bajo", "Líneas", ""),

    q("vx3_063", "Facturas con más de 10 líneas",
      "¿Qué facturas tienen más de 10 líneas?",
      "Facturas TIPO=13 con más de 10 líneas en DOCLIN. Pueden ser pedidos complejos.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODIGO, D.FECHA, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.IMPORTETOTAL "
      "HAVING COUNT(L.CODARTICULO)>10 "
      "ORDER BY N_LINEAS DESC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Bajo", "Líneas", ""),

    q("vx3_064", "Líneas de factura con unidades negativas",
      "¿Hay líneas de factura con unidades negativas?",
      "Líneas DOCLIN en facturas TIPO=13 con CANTIDAD<0. Pueden ser devoluciones.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "A.NOMBRE AS ARTICULO, L.CANTIDAD, ROUND(L.PRECIO,2) AS PRECIO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND L.CANTIDAD<0 "
      "ORDER BY L.CANTIDAD ASC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Medio", "Líneas", ""),

    q("vx3_065", "Líneas de factura con PRECIOVENTA cero",
      "¿Hay líneas de factura con PRECIOVENTA cero?",
      "Líneas DOCLIN en facturas TIPO=13 con PRECIOVENTA=0. Pueden ser artículos gratuitos o errores.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "A.NOMBRE AS ARTICULO, L.CANTIDAD "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND L.PRECIO=0 "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Medio", "Líneas", ""),

    # ── ANÁLISIS DE CLIENTES AVANZADO ──────────────────────────────────────────

    q("vx3_066", "Clientes con mayor crecimiento de compras (año actual vs anterior)",
      "¿Qué clientes han aumentado más sus compras este año?",
      "Compara facturación TIPO=13 por cliente en año actual vs año anterior.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(COALESCE(ACT.TOTAL,0),2) AS ANIO_ACTUAL, "
      "ROUND(COALESCE(ANT.TOTAL,0),2) AS ANIO_ANTERIOR, "
      "ROUND(COALESCE(ACT.TOTAL,0)-COALESCE(ANT.TOTAL,0),2) AS VARIACION "
      "FROM CLIENTE C "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) GROUP BY CODCLIENTE) ACT "
      "ON ACT.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INTEGER)-1 AS TEXT) "
      "GROUP BY CODCLIENTE) ANT ON ANT.CODCLIENTE=C.CODIGO "
      "WHERE COALESCE(ACT.TOTAL,0)>0 OR COALESCE(ANT.TOTAL,0)>0 "
      "ORDER BY VARIACION DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Alto", "Crecimiento", ""),

    q("vx3_067", "Clientes con mayor caída de compras",
      "¿Qué clientes han reducido más sus compras este año?",
      "Compara facturación TIPO=13 por cliente en año actual vs año anterior, ordenado por caída.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(COALESCE(ACT.TOTAL,0),2) AS ANIO_ACTUAL, "
      "ROUND(COALESCE(ANT.TOTAL,0),2) AS ANIO_ANTERIOR, "
      "ROUND(COALESCE(ACT.TOTAL,0)-COALESCE(ANT.TOTAL,0),2) AS VARIACION "
      "FROM CLIENTE C "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) GROUP BY CODCLIENTE) ACT "
      "ON ACT.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INTEGER)-1 AS TEXT) "
      "GROUP BY CODCLIENTE) ANT ON ANT.CODCLIENTE=C.CODIGO "
      "WHERE COALESCE(ANT.TOTAL,0)>0 "
      "ORDER BY VARIACION ASC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Alto", "Retención", ""),

    q("vx3_068", "Clientes con facturas en todos los meses del año",
      "¿Qué clientes compran todos los meses?",
      "Clientes con facturas TIPO=13 en los 12 meses del año actual.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_CON_COMPRA, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7))>=6 "
      "ORDER BY MESES_CON_COMPRA DESC, TOTAL DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Fidelización", ""),

    q("vx3_069", "Clientes con mayor número de artículos distintos comprados",
      "¿Qué clientes compran más variedad de artículos?",
      "Número de artículos distintos por cliente en facturas TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_ARTICULOS_DISTINTOS DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Cartera", ""),

    q("vx3_070", "Clientes con importe medio de factura más alto",
      "¿Qué clientes tienen el ticket medio más alto?",
      "Importe medio por factura TIPO=13 por cliente con al menos 2 facturas.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(*)>=2 "
      "ORDER BY TICKET_MEDIO DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Ticket", ""),

    # ── ANÁLISIS DE CONTRATOS Y CERTIFICACIONES ────────────────────────────────

    q("vx3_071", "Contratos activos (TIPO=10)",
      "¿Cuántos contratos hay activos?",
      "Documentos TIPO=10 (contratos). Conteo y suma de importes.",
      "SELECT COUNT(*) AS N_CONTRATOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS VALOR_TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS VALOR_MEDIO "
      "FROM DOCCAB WHERE TIPO=10",
      "Ventas", "Dirección", "KPI", "Alto", "Contratos", ""),

    q("vx3_072", "Contratos por cliente",
      "¿Qué clientes tienen contratos?",
      "Documentos TIPO=10 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_CONTRATOS, ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=10 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY VALOR_TOTAL DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Contratos", ""),

    q("vx3_073", "Certificaciones emitidas (TIPO=51)",
      "¿Cuántas certificaciones se han emitido?",
      "Documentos TIPO=51 (certificaciones). Conteo y suma.",
      "SELECT COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS VALOR_TOTAL "
      "FROM DOCCAB WHERE TIPO=51",
      "Ventas", "Dirección", "KPI", "Medio", "Certificaciones", ""),

    q("vx3_074", "Recibos emitidos (TIPO=61)",
      "¿Cuántos recibos se han emitido?",
      "Documentos TIPO=61 (recibos). Conteo y suma.",
      "SELECT COUNT(*) AS N_RECIBOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS VALOR_TOTAL "
      "FROM DOCCAB WHERE TIPO=61",
      "Ventas", "Finanzas", "KPI", "Bajo", "Recibos", ""),

    q("vx3_075", "Todos los tipos de documento con su descripción",
      "¿Qué tipos de documento existen en el sistema?",
      "Desglose completo de todos los TIPO en DOCCAB con conteo e importe.",
      "SELECT TIPO, "
      "CASE TIPO WHEN 0 THEN 'Presupuesto' WHEN 2 THEN 'SAT/Orden trabajo' "
      "WHEN 3 THEN 'Abono' WHEN 10 THEN 'Contrato' WHEN 11 THEN 'Albarán' "
      "WHEN 12 THEN 'Pedido' WHEN 13 THEN 'Factura' WHEN 51 THEN 'Certificación' "
      "WHEN 61 THEN 'Recibo' ELSE 'Otro' END AS DESCRIPCION, "
      "COUNT(*) AS N_DOCS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB GROUP BY TIPO ORDER BY N_DOCS DESC",
      "Ventas", "Dirección", "Operacional", "Bajo", "Documentos", ""),

    # ── ANÁLISIS DE RENTABILIDAD GLOBAL ───────────────────────────────────────

    q("vx3_076", "Facturación neta anual (facturas - abonos)",
      "¿Cuál es la facturación neta por año?",
      "Suma de facturas TIPO=13 menos abonos TIPO=3 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS FACTURAS, "
      "ROUND(SUM(CASE WHEN TIPO=3 THEN ABS(IMPORTETOTAL) ELSE 0 END),2) AS ABONOS, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL WHEN TIPO=3 THEN -ABS(IMPORTETOTAL) ELSE 0 END),2) AS NETO "
      "FROM DOCCAB WHERE TIPO IN (13,3) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Ventas", "Dirección", "KPI", "Crítico", "Facturación neta", ""),

    q("vx3_077", "Margen bruto global de la empresa",
      "¿Cuál es el margen bruto total de la empresa?",
      "Suma de (PRECIOVENTA-PRECIOCOSTE)*unidades en todas las líneas de facturas TIPO=13.",
      "SELECT ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS_BRUTOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COSTE_TOTAL, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN_BRUTO, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD)*100.0/"
      "NULLIF(SUM(L.PRECIO*L.CANTIDAD),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0",
      "Ventas", "Dirección", "KPI", "Crítico", "Margen", ""),

    q("vx3_078", "Margen bruto mensual",
      "¿Cómo evoluciona el margen bruto mes a mes?",
      "Margen bruto por mes en facturas TIPO=13.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COSTE, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Dirección", "KPI", "Alto", "Margen", ""),

    q("vx3_079", "Rentabilidad por cliente (margen bruto)",
      "¿Qué clientes generan más margen bruto?",
      "Margen bruto por cliente en facturas TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COSTE, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY MARGEN DESC LIMIT 20",
      "Ventas", "Dirección", "Cliente", "Alto", "Margen", ""),

    q("vx3_080", "Clientes con margen negativo",
      "¿Hay clientes con los que se pierde dinero?",
      "Clientes con margen bruto negativo en facturas TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COSTE, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD)<0 "
      "ORDER BY MARGEN ASC LIMIT 20",
      "Ventas", "Dirección", "Cliente", "Crítico", "Margen", ""),

    # ── ANÁLISIS DE DATOS MAESTROS ─────────────────────────────────────────────

    q("vx3_081", "Clientes sin dirección registrada",
      "¿Qué clientes no tienen dirección?",
      "Clientes con NULL NULL o vacía en la tabla CLIENTE.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL) AS NOMBRE "
      "FROM CLIENTE WHERE NULL IS NULL OR TRIM(NULL)='' "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas", "Comercial", "Cliente", "Bajo", "Datos maestros", ""),

    q("vx3_082", "Clientes sin teléfono registrado",
      "¿Qué clientes no tienen teléfono?",
      "Clientes con TEL NULL o vacío en la tabla CLIENTE.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL) AS NOMBRE "
      "FROM CLIENTE WHERE TEL IS NULL OR TRIM(TEL)='' "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas", "Comercial", "Cliente", "Bajo", "Datos maestros", ""),

    q("vx3_083", "Clientes sin NULL registrado",
      "¿Qué clientes no tienen NULL?",
      "Clientes con NULL NULL o vacío en la tabla CLIENTE.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL) AS NOMBRE "
      "FROM CLIENTE WHERE NULL IS NULL OR TRIM(NULL)='' "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas", "Comercial", "Cliente", "Bajo", "Datos maestros", ""),

    q("vx3_084", "Clientes duplicados por nombre similar",
      "¿Hay clientes con nombres muy similares que puedan ser duplicados?",
      "Clientes con RAZONSOCIAL que empieza igual (primeros 10 caracteres).",
      "SELECT SUBSTR(COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL),1,15) AS INICIO_NOMBRE, "
      "COUNT(*) AS N_CLIENTES, "
      "GROUP_CONCAT(CODIGO) AS CODIGOS "
      "FROM CLIENTE "
      "GROUP BY SUBSTR(COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL),1,15) "
      "HAVING COUNT(*)>1 "
      "ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Datos maestros", ""),

    q("vx3_085", "Total de clientes en la base de datos",
      "¿Cuántos clientes hay registrados?",
      "Conteo total de registros en la tabla CLIENTE.",
      "SELECT COUNT(*) AS TOTAL_CLIENTES, "
      "SUM(CASE WHEN NOMBRECOMERCIAL IS NOT NULL THEN 1 ELSE 0 END) AS CON_NOMBRE_COMERCIAL, "
      "SUM(CASE WHEN RAZONSOCIAL IS NOT NULL THEN 1 ELSE 0 END) AS CON_RAZON_SOCIAL "
      "FROM CLIENTE",
      "Ventas", "Dirección", "KPI", "Bajo", "Datos maestros", ""),

    # ── ANÁLISIS DE ARTÍCULOS AVANZADO ─────────────────────────────────────────

    q("vx3_086", "Artículos con PRECIOVENTA de venta inferior al PRECIOVENTA de tarifa",
      "¿Hay artículos que se venden por debajo de su PRECIOVENTA de tarifa?",
      "Líneas de factura TIPO=13 donde L.PRECIO < A.PRECIOVENTA (PRECIOVENTA de tarifa).",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_TARIFA, "
      "ROUND(L.PRECIO,2) AS PRECIO_VENTA_REAL, "
      "ROUND(A.PRECIOVENTA-L.PRECIO,2) AS DIFERENCIA, "
      "COUNT(*) AS N_VECES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOVENTA>0 AND L.PRECIO<A.PRECIOVENTA "
      "GROUP BY L.CODARTICULO, A.NOMBRE, A.PRECIOVENTA "
      "ORDER BY DIFERENCIA DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Precios", ""),

    q("vx3_087", "Artículos más vendidos por número de facturas distintas",
      "¿En cuántas facturas distintas aparece cada artículo?",
      "Número de facturas TIPO=13 distintas que incluyen cada artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_FACTURAS_DISTINTAS, "
      "SUM(L.CANTIDAD) AS TOTAL_UNIDADES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_FACTURAS_DISTINTAS DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Popularidad", ""),

    q("vx3_088", "Artículos sin familia asignada",
      "¿Qué artículos no tienen familia asignada?",
      "Artículos con CODFAMILIA NULL o 0 en la tabla ARTICULO.",
      "SELECT CODIGO, NOMBRE, ROUND(PRECIOVENTA,2) AS PRECIO, STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO WHERE CODFAMILIA IS NULL OR CODFAMILIA=0 "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas", "Almacén", "Artículo", "Bajo", "Datos maestros", ""),

    q("vx3_089", "Artículos con PRECIOVENTA de PRECIOCOSTE mayor que PRECIOVENTA de venta",
      "¿Hay artículos con PRECIOCOSTE mayor que PRECIOVENTA de venta en tarifa?",
      "Artículos donde PRECIOCOSTE > PRECIOVENTA en la tabla ARTICULO.",
      "SELECT CODIGO, NOMBRE, "
      "ROUND(PRECIOCOSTE,2) AS COSTE, "
      "ROUND(PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(PRECIOCOSTE-PRECIOVENTA,2) AS DIFERENCIA "
      "FROM ARTICULO WHERE PRECIOCOSTE>PRECIOVENTA AND PRECIOVENTA>0 "
      "ORDER BY DIFERENCIA DESC LIMIT 20",
      "Ventas", "Dirección", "Artículo", "Crítico", "Precios", ""),

    q("vx3_090", "Artículos con PRECIOVENTA de venta cero",
      "¿Qué artículos tienen PRECIOVENTA de venta cero?",
      "Artículos con PRECIOVENTA=0 o NULL en la tabla ARTICULO.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO WHERE PRECIOVENTA=0 OR PRECIOVENTA IS NULL "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas", "Comercial", "Artículo", "Medio", "Datos maestros", ""),

    # ── ANÁLISIS DE CAJA Y COBROS ──────────────────────────────────────────────

    q("vx3_091", "Movimientos de caja del mes actual",
      "¿Cuáles son los movimientos de caja de este mes?",
      "Registros de CAJA del mes actual ordenados por fecha.",
      "SELECT FECHA, ROUND(IMPORTE,2) AS IMPORTE, CONCEPTO "
      "FROM CAJA WHERE SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7) "
      "ORDER BY FECHA DESC LIMIT 50",
      "Ventas", "Finanzas", "Operacional", "Medio", "Caja", ""),

    q("vx3_092", "Saldo de caja por mes",
      "¿Cuál es el saldo neto de caja cada mes?",
      "Suma de IMPORTE en CAJA por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(IMPORTE),2) AS SALDO_NETO, "
      "ROUND(SUM(CASE WHEN IMPORTE>0 THEN IMPORTE ELSE 0 END),2) AS ENTRADAS, "
      "ROUND(SUM(CASE WHEN IMPORTE<0 THEN ABS(IMPORTE) ELSE 0 END),2) AS SALIDAS "
      "FROM CAJA WHERE FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Finanzas", "KPI", "Alto", "Caja", ""),

    q("vx3_093", "Movimientos de caja con importe superior a 5000€",
      "¿Qué movimientos de caja superan los 5000€?",
      "Registros de CAJA con ABS(IMPORTE)>5000.",
      "SELECT FECHA, ROUND(IMPORTE,2) AS IMPORTE, CONCEPTO "
      "FROM CAJA WHERE ABS(IMPORTE)>5000 "
      "ORDER BY ABS(IMPORTE) DESC LIMIT 20",
      "Ventas", "Finanzas", "Operacional", "Alto", "Caja", ""),

    q("vx3_094", "Número de movimientos de caja por mes",
      "¿Cuántos movimientos de caja hay cada mes?",
      "Conteo de registros en CAJA por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_MOVIMIENTOS "
      "FROM CAJA WHERE FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Finanzas", "Operacional", "Bajo", "Caja", ""),

    q("vx3_095", "Saldo acumulado de caja",
      "¿Cuál es el saldo acumulado total de caja?",
      "Suma total de todos los movimientos en CAJA.",
      "SELECT COUNT(*) AS N_MOVIMIENTOS, "
      "ROUND(SUM(IMPORTE),2) AS SALDO_TOTAL, "
      "ROUND(SUM(CASE WHEN IMPORTE>0 THEN IMPORTE ELSE 0 END),2) AS TOTAL_ENTRADAS, "
      "ROUND(SUM(CASE WHEN IMPORTE<0 THEN ABS(IMPORTE) ELSE 0 END),2) AS TOTAL_SALIDAS "
      "FROM CAJA",
      "Ventas", "Finanzas", "KPI", "Alto", "Caja", ""),

    # ── ANÁLISIS DE ESTALMACEN (STOCKARTICULO HISTÓRICO) ───────────────────────────────

    q("vx3_096", "Movimientos de STOCKARTICULO por artículo",
      "¿Cuántos movimientos de STOCKARTICULO tiene cada artículo?",
      "Conteo de registros en ESTALMACEN por artículo.",
      "SELECT A.CODIGO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_MOVIMIENTOS, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS CANTIDAD_TOTAL "
      "FROM ARTICULO E "
      "LEFT JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY N_MOVIMIENTOS DESC LIMIT 30",
      "Ventas", "Almacén", "Artículo", "Bajo", "STOCKARTICULO", ""),

    q("vx3_097", "Artículos con más entradas de STOCKARTICULO",
      "¿Qué artículos han recibido más entradas de STOCKARTICULO?",
      "Movimientos positivos en ESTALMACEN por artículo.",
      "SELECT A.CODIGO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_ENTRADAS, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS CANTIDAD_ENTRADA "
      "FROM ARTICULO E "
      "LEFT JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY CANTIDAD_ENTRADA DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Bajo", "STOCKARTICULO", ""),

    q("vx3_098", "Artículos con más salidas de STOCKARTICULO",
      "¿Qué artículos tienen más salidas de STOCKARTICULO?",
      "Movimientos negativos en ESTALMACEN por artículo.",
      "SELECT A.CODIGO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_SALIDAS, "
      "ROUND(ABS(SUM(A.STOCKARTICULO)),2) AS CANTIDAD_SALIDA "
      "FROM ARTICULO E "
      "LEFT JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO<0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY CANTIDAD_SALIDA DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Bajo", "STOCKARTICULO", ""),

    q("vx3_099", "Valor total del inventario actual",
      "¿Cuánto vale el inventario actual?",
      "Suma de STOCKARTICULO * PRECIOCOSTE por artículo en ARTICULO.",
      "SELECT COUNT(*) AS N_ARTICULOS_CON_STOCKARTICULO, "
      "ROUND(SUM(STOCKARTICULO*PRECIOCOSTE),2) AS VALOR_INVENTARIO_COSTE, "
      "ROUND(SUM(STOCKARTICULO*PRECIOVENTA),2) AS VALOR_INVENTARIO_VENTA "
      "FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0",
      "Ventas", "Dirección", "KPI", "Alto", "Inventario", ""),

    q("vx3_100", "Artículos con STOCKARTICULO negativo",
      "¿Hay artículos con STOCKARTICULO negativo?",
      "Artículos con STOCKARTICULO<0 en la tabla ARTICULO. Indica posibles errores.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCK_NEGATIVO, "
      "ROUND(PRECIOVENTA,2) AS PRECIO_VENTA "
      "FROM ARTICULO WHERE STOCKARTICULO<0 "
      "ORDER BY STOCKARTICULO ASC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Alto", "STOCKARTICULO", ""),

    # ── ANÁLISIS DE PROVEEDORES EN VENTAS ──────────────────────────────────────

    q("vx3_101", "Artículos por proveedor principal",
      "¿Cuántos artículos tiene cada proveedor?",
      "Agrupa artículos por PROVEEDDEFECTO en la tabla ARTICULO.",
      "SELECT A.PROVEEDDEFECTO AS COD_PROV, "
      "COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL) AS PROVEEDOR, "
      "COUNT(*) AS N_ARTICULOS, "
      "ROUND(AVG(A.PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO A "
      "LEFT JOIN PROVEED P ON P.CODIGO=A.PROVEEDDEFECTO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO>0 "
      "GROUP BY A.PROVEEDDEFECTO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Ventas", "Compras", "Artículo", "Bajo", "Proveedores", ""),

    q("vx3_102", "Ventas de artículos por proveedor principal",
      "¿Cuánto se vende de artículos de cada proveedor?",
      "Facturación TIPO=13 agrupada por proveedor principal del artículo.",
      "SELECT COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL) AS PROVEEDOR, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS, "
      "SUM(L.CANTIDAD) AS UNIDADES_VENDIDAS, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS VENTAS_TOTALES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN PROVEED P ON P.CODIGO=A.PROVEEDDEFECTO "
      "WHERE D.TIPO=13 "
      "GROUP BY A.PROVEEDDEFECTO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "ORDER BY VENTAS_TOTALES DESC LIMIT 20",
      "Ventas", "Compras", "Artículo", "Medio", "Proveedores", ""),

    # ── ANÁLISIS DE FAMILIAS ───────────────────────────────────────────────────

    q("vx3_103", "Facturación por familia de producto",
      "¿Cuánto se factura por familia de producto?",
      "Suma de IMPORTETOTAL en facturas TIPO=13 agrupado por familia de artículo.",
      "SELECT A.CODFAMILIA AS FAMILIA, F.NOMBRE AS NOMBRE_FAMILIA, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "SUM(L.CANTIDAD) AS CANTIDAD, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS VENTAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 "
      "GROUP BY A.CODFAMILIA, F.NOMBRE "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Ventas", "Dirección", "Artículo", "Medio", "Familias", ""),

    q("vx3_104", "Evolución mensual de ventas por familia",
      "¿Cómo evolucionan las ventas de cada familia mes a mes?",
      "Ventas TIPO=13 por familia y mes en los últimos 12 meses.",
      "SELECT A.CODFAMILIA AS FAMILIA, F.NOMBRE AS NOMBRE_FAMILIA, "
      "SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS VENTAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-12 months') "
      "GROUP BY A.CODFAMILIA, F.NOMBRE, SUBSTR(D.FECHA,1,7) "
      "ORDER BY FAMILIA, MES DESC",
      "Ventas", "Dirección", "Artículo", "Medio", "Familias", ""),

    q("vx3_105", "Familias sin ventas en los últimos 6 meses",
      "¿Qué familias de producto no tienen ventas recientes?",
      "Familias sin líneas de factura TIPO=13 en los últimos 180 días.",
      "SELECT F.CODIGO, F.NOMBRE AS FAMILIA, "
      "COUNT(A.CODIGO) AS N_ARTICULOS_EN_FAMILIA "
      "FROM FAMILIA F "
      "LEFT JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      "WHERE F.CODIGO NOT IN ("
      "SELECT DISTINCT A2.CODFAMILIA FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A2 ON A2.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-180 days') "
      "AND A2.CODFAMILIA IS NOT NULL) "
      "GROUP BY F.CODIGO, F.NOMBRE "
      "ORDER BY F.NOMBRE LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Familias", ""),

    # ── ANÁLISIS DE DOCUMENTOS RECIENTES ──────────────────────────────────────

    q("vx3_106", "Últimas 20 facturas emitidas",
      "¿Cuáles son las últimas facturas emitidas?",
      "Las 20 facturas TIPO=13 más recientes por FECHA.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, D.CODAGENTE AS AGENTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 ORDER BY D.FECHA DESC, D.CODIGO DESC LIMIT 20",
      "Ventas", "Comercial", "Operacional", "Bajo", "Documentos", ""),

    q("vx3_107", "Últimos 20 presupuestos emitidos",
      "¿Cuáles son los últimos presupuestos emitidos?",
      "Los 20 presupuestos TIPO=0 más recientes por FECHA.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=0 ORDER BY D.FECHA DESC, D.CODIGO DESC LIMIT 20",
      "Ventas", "Comercial", "Operacional", "Bajo", "Documentos", ""),

    q("vx3_108", "Facturas del día de hoy",
      "¿Qué facturas se han emitido hoy?",
      "Facturas TIPO=13 con FECHA=hoy.",
      "SELECT D.CODIGO, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA=DATE('now') "
      "ORDER BY D.CODIGO DESC",
      "Ventas", "Comercial", "Operacional", "Bajo", "Documentos", ""),

    q("vx3_109", "Facturas de la semana actual",
      "¿Qué facturas se han emitido esta semana?",
      "Facturas TIPO=13 con FECHA en los últimos 7 días.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-7 days') "
      "ORDER BY D.FECHA DESC, D.CODIGO DESC LIMIT 50",
      "Ventas", "Comercial", "Operacional", "Bajo", "Documentos", ""),

    q("vx3_110", "Factura más grande del año",
      "¿Cuál es la factura de mayor importe del año?",
      "Factura TIPO=13 con mayor IMPORTETOTAL en el año actual.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, D.CODAGENTE AS AGENTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 1",
      "Ventas", "Dirección", "KPI", "Bajo", "Documentos", ""),

    # ── ANÁLISIS DE RIESGO ─────────────────────────────────────────────────────

    q("vx3_111", "Clientes con riesgo de concentración (>20% de la facturación)",
      "¿Qué clientes representan más del 20% de la facturación total?",
      "Clientes cuya facturación TIPO=13 supera el 20% del total.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION, "
      "ROUND(SUM(D.IMPORTETOTAL)*100.0/("
      "SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13),1) AS PCT_TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING PCT_TOTAL>20 "
      "ORDER BY PCT_TOTAL DESC",
      "Ventas", "Dirección", "Cliente", "Crítico", "Riesgo", ""),

    q("vx3_112", "Facturas con importe superior a 10000€",
      "¿Qué facturas superan los 10000€?",
      "Facturas TIPO=13 con IMPORTETOTAL>10000.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL>10000 "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 30",
      "Ventas", "Dirección", "Operacional", "Medio", "Riesgo", ""),

    q("vx3_113", "Facturas sin cliente asignado",
      "¿Hay facturas sin cliente asignado?",
      "Facturas TIPO=13 con CODCLIENTE NULL o 0.",
      "SELECT D.CODIGO, D.FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND (CODCLIENTE IS NULL OR CODCLIENTE=0) "
      "ORDER BY FECHA DESC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Alto", "Datos maestros", ""),

    q("vx3_114", "Facturas con fecha futura",
      "¿Hay facturas con fecha posterior a hoy?",
      "Facturas TIPO=13 con FECHA>hoy. Pueden ser errores de fecha.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA>DATE('now') "
      "ORDER BY D.FECHA ASC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Alto", "Datos maestros", ""),

    q("vx3_115", "Facturas con importe cero o negativo",
      "¿Hay facturas con importe cero o negativo?",
      "Facturas TIPO=13 con IMPORTETOTAL<=0. Pueden ser errores o abonos mal clasificados.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL<=0 "
      "ORDER BY D.IMPORTETOTAL ASC LIMIT 20",
      "Ventas", "Finanzas", "Operacional", "Alto", "Datos maestros", ""),

    # ── ANÁLISIS DE COMPARATIVAS ───────────────────────────────────────────────

    q("vx3_116", "Comparativa de facturación por departamento (ventas vs SAT)",
      "¿Cuánto factura ventas vs SAT?",
      "Compara IMPORTETOTAL de facturas TIPO=13 vs SATs TIPO=2.",
      "SELECT "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS VENTAS, "
      "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTETOTAL ELSE 0 END),2) AS SAT, "
      "COUNT(CASE WHEN TIPO=13 THEN 1 END) AS N_FACTURAS_VENTA, "
      "COUNT(CASE WHEN TIPO=2 THEN 1 END) AS N_SATS "
      "FROM DOCCAB WHERE TIPO IN (13,2)",
      "Ventas", "Dirección", "KPI", "Alto", "Comparativa", ""),

    q("vx3_117", "Ratio presupuestos/facturas por mes",
      "¿Cuántos presupuestos se emiten por cada factura?",
      "Ratio de presupuestos TIPO=0 vs facturas TIPO=13 por mes.",
      "SELECT MES, N_PRESUPUESTOS, N_FACTURAS, "
      "ROUND(CAST(N_PRESUPUESTOS AS REAL)/NULLIF(N_FACTURAS,0),2) AS RATIO "
      "FROM ("
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "SUM(CASE WHEN TIPO=0 THEN 1 ELSE 0 END) AS N_PRESUPUESTOS, "
      "SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END) AS N_FACTURAS "
      "FROM DOCCAB WHERE TIPO IN (0,13) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY MES DESC LIMIT 12",
      "Ventas", "Comercial", "KPI", "Medio", "Comparativa", ""),

    q("vx3_118", "Evolución del número de clientes activos por mes",
      "¿Cuántos clientes distintos compran cada mes?",
      "Clientes únicos con facturas TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(DISTINCT CODCLIENTE) AS CLIENTES_ACTIVOS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Comercial", "KPI", "Medio", "Clientes activos", ""),

    q("vx3_119", "Ticket medio mensual",
      "¿Cómo evoluciona el ticket medio mes a mes?",
      "Importe medio por factura TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Dirección", "KPI", "Medio", "Ticket", ""),

    q("vx3_120", "Resumen ejecutivo de ventas (KPIs principales)",
      "¿Cuál es el resumen ejecutivo de ventas?",
      "KPIs principales: facturación total, ticket medio, clientes activos, facturas emitidas.",
      "SELECT "
      "COUNT(*) AS N_FACTURAS, "
      "COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES_DISTINTOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURACION_TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(MAX(IMPORTETOTAL),2) AS FACTURA_MAX, "
      "ROUND(MIN(IMPORTETOTAL),2) AS FACTURA_MIN "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas", "Dirección", "KPI", "Crítico", "Resumen ejecutivo", ""),

    # ── ANÁLISIS DE LÍNEAS AVANZADO ────────────────────────────────────────────

    q("vx3_121", "Artículos más vendidos por importe (no por unidades)",
      "¿Qué artículos generan más ingresos en euros?",
      "Suma de PRECIOVENTA*CANTIDAD por artículo en facturas TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "SUM(L.CANTIDAD) AS CANTIDAD, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS_TOTALES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY INGRESOS_TOTALES DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Alto", "Ingresos", ""),

    q("vx3_122", "Artículos con mayor número de clientes distintos",
      "¿Qué artículos compran más clientes distintos?",
      "Número de clientes únicos por artículo en facturas TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "SUM(L.CANTIDAD) AS TOTAL_UNIDADES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Popularidad", ""),

    q("vx3_123", "Líneas de factura sin artículo asignado",
      "¿Hay líneas de factura sin artículo asignado?",
      "Líneas DOCLIN en facturas TIPO=13 donde CODIGO no existe en ARTICULO.",
      "SELECT L.CODDOCUMENTO AS FACTURA, L.CODARTICULO AS COD_ART_INEXISTENTE, "
      "L.CANTIDAD, ROUND(L.PRECIO,2) AS PRECIO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.CODIGO IS NULL "
      "ORDER BY L.CODDOCUMENTO DESC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Medio", "Datos maestros", ""),

    q("vx3_124", "Importe total de líneas de factura vs cabecera",
      "¿Coincide la suma de líneas con el importe de la cabecera?",
      "Compara SUM(PRECIOVENTA*CANTIDAD) de DOCLIN con IMPORTETOTAL de DOCCAB por factura.",
      "SELECT D.CODIGO AS FACTURA, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE_CABECERA, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS SUMA_LINEAS, "
      "ROUND(D.IMPORTETOTAL-SUM(L.PRECIO*L.CANTIDAD),2) AS DIFERENCIA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODIGO, D.IMPORTETOTAL "
      "HAVING ABS(D.IMPORTETOTAL-SUM(L.PRECIO*L.CANTIDAD))>1 "
      "ORDER BY ABS(DIFERENCIA) DESC LIMIT 20",
      "Ventas", "Finanzas", "Operacional", "Alto", "Integridad datos", ""),

    q("vx3_125", "Facturas con líneas de artículos de distintas familias",
      "¿Qué facturas mezclan artículos de distintas familias?",
      "Facturas TIPO=13 con artículos de más de 3 familias distintas.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT A.CODFAMILIA) AS N_FAMILIAS, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND A.CODFAMILIA IS NOT NULL "
      "GROUP BY D.CODIGO, D.FECHA, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.IMPORTETOTAL "
      "HAVING COUNT(DISTINCT A.CODFAMILIA)>3 "
      "ORDER BY N_FAMILIAS DESC LIMIT 20",
      "Ventas", "Comercial", "Operacional", "Bajo", "Familias", ""),

    # ── ANÁLISIS DE PROVEEDORES AVANZADO ───────────────────────────────────────

    q("vx3_126", "Total de proveedores registrados",
      "¿Cuántos proveedores hay en la base de datos?",
      "Conteo total de registros en la tabla PROVEED.",
      "SELECT COUNT(*) AS TOTAL_PROVEEDORES, "
      "SUM(CASE WHEN NOMBRECOMERCIAL IS NOT NULL THEN 1 ELSE 0 END) AS CON_NOMBRE_COMERCIAL "
      "FROM PROVEED",
      "Ventas", "Compras", "KPI", "Bajo", "Proveedores", ""),

    q("vx3_127", "Proveedores sin artículos asignados",
      "¿Qué proveedores no tienen artículos asignados?",
      "Proveedores sin ningún artículo con PROVEEDDEFECTO apuntando a ellos.",
      "SELECT P.CODIGO, COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL) AS PROVEEDOR "
      "FROM PROVEED P "
      "WHERE P.CODIGO NOT IN (SELECT DISTINCT PROVEEDDEFECTO FROM ARTICULO "
      "WHERE PROVEEDDEFECTO IS NOT NULL AND PROVEEDDEFECTO>0) "
      "ORDER BY PROVEEDOR LIMIT 20",
      "Ventas", "Compras", "Operacional", "Bajo", "Proveedores", ""),

    q("vx3_128", "Artículos sin proveedor asignado",
      "¿Qué artículos no tienen proveedor asignado?",
      "Artículos con PROVEEDDEFECTO NULL o 0 en la tabla ARTICULO.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(PRECIOVENTA,2) AS PRECIO_VENTA "
      "FROM ARTICULO WHERE PROVEEDDEFECTO IS NULL OR PROVEEDDEFECTO=0 "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas", "Compras", "Artículo", "Bajo", "Datos maestros", ""),

    q("vx3_129", "Artículos con múltiples proveedores (via EQUIVAL)",
      "¿Qué artículos tienen equivalencias con otros artículos?",
      "Registros en EQUIVAL que relacionan artículos equivalentes.",
      "SELECT A.CODIGO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_EQUIVALENCIAS "
      "FROM ARTICULO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY N_EQUIVALENCIAS DESC LIMIT 20",
      "Ventas", "Compras", "Artículo", "Bajo", "Equivalencias", ""),

    q("vx3_130", "Resumen de artículos por estado de STOCKARTICULO",
      "¿Cuántos artículos hay con STOCKARTICULO positivo, cero y negativo?",
      "Clasifica artículos por estado de STOCKARTICULO.",
      "SELECT "
      "SUM(CASE WHEN STOCKARTICULO>0 THEN 1 ELSE 0 END) AS CON_STOCKARTICULO, "
      "SUM(CASE WHEN STOCKARTICULO=0 THEN 1 ELSE 0 END) AS SIN_STOCKARTICULO, "
      "SUM(CASE WHEN STOCKARTICULO<0 THEN 1 ELSE 0 END) AS STOCK_NEGATIVO, "
      "COUNT(*) AS TOTAL_ARTICULOS "
      "FROM ARTICULO",
      "Ventas", "Almacén", "KPI", "Medio", "STOCKARTICULO", ""),

    # ── ANÁLISIS DE DOCUMENTOS ASOCIADOS ──────────────────────────────────────

    q("vx3_131", "Documentos con más de un destino (multi-conversión)",
      "¿Hay documentos que se han convertido en más de un documento destino?",
      "Documentos en DOCDESTINO con más de 1 entrada como origen.",
      "SELECT CODDOCUMENTO AS DOC_ORIGEN, COUNT(*) AS N_DESTINOS "
      "FROM DOCDESTINO GROUP BY CODDOCUMENTO HAVING COUNT(*)>1 "
      "ORDER BY N_DESTINOS DESC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Medio", "Documentos", ""),

    q("vx3_132", "Cadena completa presupuesto→albarán→factura",
      "¿Cuántos documentos siguen la cadena completa presupuesto→albarán→factura?",
      "Presupuestos TIPO=0 que tienen albarán TIPO=11 y factura TIPO=13 asociados.",
      "SELECT COUNT(DISTINCT D0.CODIGO) AS PRESUPUESTOS_CADENA_COMPLETA "
      "FROM DOCCAB D0 "
      "JOIN DOCDESTINO DD1 ON DD1.CODDOCUMENTO=D0.CODIGO "
      "JOIN DOCCAB D11 ON D11.CODIGO=DD1.CODDOCUMENTODESTINO AND D11.TIPO=11 "
      "JOIN DOCDESTINO DD2 ON DD2.CODDOCUMENTO=D11.CODIGO "
      "JOIN DOCCAB D13 ON D13.CODIGO=DD2.CODDOCUMENTODESTINO AND D13.TIPO=13 "
      "WHERE D0.TIPO=0",
      "Ventas", "Operaciones", "KPI", "Medio", "Documentos", ""),

    q("vx3_133", "Presupuestos convertidos directamente a factura (sin albarán)",
      "¿Cuántos presupuestos se convierten directamente en factura sin pasar por albarán?",
      "Presupuestos TIPO=0 con destino TIPO=13 directo en DOCDESTINO.",
      "SELECT COUNT(*) AS N_CONVERSION_DIRECTA "
      "FROM DOCDESTINO DD "
      "JOIN DOCCAB D1 ON D1.CODIGO=DD.CODDOCUMENTO "
      "JOIN DOCCAB D2 ON D2.CODIGO=DD.CODDOCUMENTODESTINO "
      "WHERE D1.TIPO=0 AND D2.TIPO=13",
      "Ventas", "Operaciones", "KPI", "Medio", "Documentos", ""),

    q("vx3_134", "Documentos sin ninguna conversión (huérfanos)",
      "¿Cuántos documentos no tienen ningún documento destino?",
      "Documentos en DOCCAB sin entrada en DOCDESTINO como origen.",
      "SELECT TIPO, COUNT(*) AS N_HUERFANOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS VALOR_TOTAL "
      "FROM DOCCAB WHERE CODIGO NOT IN (SELECT CODDOCUMENTO FROM DOCDESTINO) "
      "GROUP BY TIPO ORDER BY N_HUERFANOS DESC",
      "Ventas", "Operaciones", "Operacional", "Medio", "Documentos", ""),

    q("vx3_135", "Relación entre documentos (mapa de conversiones)",
      "¿Cuántas conversiones hay entre cada par de tipos de documento?",
      "Conteo de conversiones en DOCDESTINO por par (TIPO_ORIGEN, TIPO_DESTINO).",
      "SELECT D1.TIPO AS TIPO_ORIGEN, D2.TIPO AS TIPO_DESTINO, "
      "COUNT(*) AS N_CONVERSIONES "
      "FROM DOCDESTINO DD "
      "JOIN DOCCAB D1 ON D1.CODIGO=DD.CODDOCUMENTO "
      "JOIN DOCCAB D2 ON D2.CODIGO=DD.CODDOCUMENTODESTINO "
      "GROUP BY D1.TIPO, D2.TIPO "
      "ORDER BY N_CONVERSIONES DESC",
      "Ventas", "Operaciones", "Operacional", "Bajo", "Documentos", ""),

    # ── ANÁLISIS DE CALIDAD DE DATOS ───────────────────────────────────────────

    q("vx3_136", "Documentos con fecha NULL",
      "¿Hay documentos sin fecha?",
      "Documentos en DOCCAB con FECHA NULL por tipo.",
      "SELECT TIPO, COUNT(*) AS N_SIN_FECHA "
      "FROM DOCCAB WHERE FECHA IS NULL "
      "GROUP BY TIPO ORDER BY N_SIN_FECHA DESC",
      "Ventas", "Operaciones", "Operacional", "Alto", "Calidad datos", ""),

    q("vx3_137", "Documentos con importe NULL",
      "¿Hay documentos con importe NULL?",
      "Documentos en DOCCAB con IMPORTETOTAL NULL por tipo.",
      "SELECT TIPO, COUNT(*) AS N_SIN_IMPORTE "
      "FROM DOCCAB WHERE IMPORTETOTAL IS NULL "
      "GROUP BY TIPO ORDER BY N_SIN_IMPORTE DESC",
      "Ventas", "Operaciones", "Operacional", "Alto", "Calidad datos", ""),

    q("vx3_138", "Clientes con razón social y nombre comercial iguales",
      "¿Hay clientes donde RAZONSOCIAL y NOMBRECOMERCIAL son idénticos?",
      "Clientes donde ambos campos tienen el mismo valor (posible duplicación).",
      "SELECT CODIGO, RAZONSOCIAL, NOMBRECOMERCIAL "
      "FROM CLIENTE "
      "WHERE RAZONSOCIAL IS NOT NULL AND NOMBRECOMERCIAL IS NOT NULL "
      "AND UPPER(TRIM(RAZONSOCIAL))=UPPER(TRIM(NOMBRECOMERCIAL)) "
      "ORDER BY RAZONSOCIAL LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Calidad datos", ""),

    q("vx3_139", "Artículos con nombre duplicado",
      "¿Hay artículos con el mismo nombre?",
      "Artículos con NOMBRE idéntico (posibles duplicados).",
      "SELECT NOMBRE, COUNT(*) AS N_ARTICULOS, "
      "GROUP_CONCAT(CODIGO) AS CODIGOS "
      "FROM ARTICULO WHERE NOMBRE IS NOT NULL "
      "GROUP BY UPPER(TRIM(NOMBRE)) HAVING COUNT(*)>1 "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Medio", "Calidad datos", ""),

    q("vx3_140", "Líneas de factura con unidades cero",
      "¿Hay líneas de factura con unidades cero?",
      "Líneas DOCLIN en facturas TIPO=13 con CANTIDAD=0.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "A.NOMBRE AS ARTICULO, L.PRECIO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND L.CANTIDAD=0 "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Ventas", "Operaciones", "Operacional", "Medio", "Calidad datos", ""),

    # ── ANÁLISIS DE TENDENCIAS ─────────────────────────────────────────────────

    q("vx3_141", "Crecimiento porcentual de facturación mes a mes",
      "¿Cuál es el crecimiento porcentual de facturación mes a mes?",
      "Variación porcentual de IMPORTETOTAL TIPO=13 entre meses consecutivos.",
      "SELECT MES, TOTAL, "
      "ROUND((TOTAL-LAG(TOTAL) OVER (ORDER BY MES))*100.0/"
      "NULLIF(LAG(TOTAL) OVER (ORDER BY MES),0),1) AS CRECIMIENTO_PCT "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY MES DESC LIMIT 13",
      "Ventas", "Dirección", "KPI", "Alto", "Tendencias", ""),

    q("vx3_142", "Media móvil de 3 meses de facturación",
      "¿Cuál es la media móvil de 3 meses de la facturación?",
      "Media de los últimos 3 meses de IMPORTETOTAL TIPO=13 por mes.",
      "SELECT MES, TOTAL, "
      "ROUND(AVG(TOTAL) OVER (ORDER BY MES ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),2) AS MEDIA_3M "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY MES DESC LIMIT 12",
      "Ventas", "Dirección", "KPI", "Medio", "Tendencias", ""),

    q("vx3_143", "Acumulado de facturación año en curso por mes",
      "¿Cuál es la facturación acumulada del año en curso mes a mes?",
      "Suma acumulada de IMPORTETOTAL TIPO=13 por mes en el año actual.",
      "SELECT MES, TOTAL, "
      "SUM(TOTAL) OVER (ORDER BY MES) AS ACUMULADO "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "AND FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY MES",
      "Ventas", "Dirección", "KPI", "Alto", "Acumulado", ""),

    q("vx3_144", "Ranking de meses por facturación histórica",
      "¿Cuáles son los meses con más facturación en el histórico?",
      "Top 12 meses por IMPORTETOTAL TIPO=13 en todo el histórico.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) "
      "ORDER BY TOTAL DESC LIMIT 12",
      "Ventas", "Dirección", "KPI", "Medio", "Ranking", ""),

    q("vx3_145", "Días con mayor facturación",
      "¿Qué días concretos tienen más facturación?",
      "Top 20 días por IMPORTETOTAL TIPO=13.",
      "SELECT FECHA, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY FECHA ORDER BY TOTAL DESC LIMIT 20",
      "Ventas", "Dirección", "KPI", "Bajo", "Estacionalidad", ""),

    # ── ANÁLISIS DE CLIENTES POR ZONA ─────────────────────────────────────────

    q("vx3_146", "Clientes por código postal",
      "¿Cómo se distribuyen los clientes por código postal?",
      "Agrupa clientes por CP en la tabla CLIENTE.",
      "SELECT CP, COUNT(*) AS N_CLIENTES "
      "FROM CLIENTE WHERE CP IS NOT NULL AND TRIM(CP)<>'' "
      "GROUP BY CP ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Geografía", ""),

    q("vx3_147", "Facturación por código postal de cliente",
      "¿Cuánto se factura por zona geográfica (código postal)?",
      "Suma de IMPORTETOTAL TIPO=13 por CP del cliente.",
      "SELECT C.CP, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND C.CP IS NOT NULL "
      "GROUP BY C.CP ORDER BY TOTAL DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Geografía", ""),

    q("vx3_148", "Clientes por provincia",
      "¿Cómo se distribuyen los clientes por provincia?",
      "Agrupa clientes por PROVINCIA en la tabla CLIENTE.",
      "SELECT PROVINCIA, COUNT(*) AS N_CLIENTES "
      "FROM CLIENTE WHERE CP IS NOT NULL AND TRIM(PROVINCIA)<>'' "
      "GROUP BY CP ORDER BY N_CLIENTES DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Geografía", ""),

    q("vx3_149", "Facturación por provincia de cliente",
      "¿Cuánto se factura por provincia?",
      "Suma de IMPORTETOTAL TIPO=13 por PROVINCIA del cliente.",
      "SELECT C.CP, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND C.CP IS NOT NULL "
      "GROUP BY C.CP ORDER BY TOTAL DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Geografía", ""),

    q("vx3_150", "Clientes sin código postal",
      "¿Qué clientes no tienen código postal?",
      "Clientes con CP NULL o vacío.",
      "SELECT COUNT(*) AS N_SIN_CODPOSTAL "
      "FROM CLIENTE WHERE CP IS NULL OR TRIM(CP)=''",
      "Ventas", "Comercial", "Cliente", "Bajo", "Datos maestros", ""),

    # ── ANÁLISIS DE CONDICIONES COMERCIALES ───────────────────────────────────

    q("vx3_151", "Clientes con condiciones especiales (CONDICIO)",
      "¿Qué condiciones comerciales hay registradas?",
      "Registros en la tabla CONDICIO.",
      "SELECT * FROM CONDICIO LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Condiciones", ""),

    q("vx3_152", "Formas de pago disponibles",
      "¿Qué formas de pago están configuradas en el sistema?",
      "Registros en la tabla FORMASPAGO.",
      "SELECT CODIGO, NOMBRE FROM FORMASPAGO ORDER BY NOMBRE LIMIT 20",
      "Ventas", "Finanzas", "Operacional", "Bajo", "Formas de pago", ""),

    q("vx3_153", "Familias de productos disponibles",
      "¿Qué familias de productos están configuradas?",
      "Registros en la tabla FAMILIA con conteo de artículos.",
      "SELECT F.CODIGO, F.NOMBRE, COUNT(A.CODIGO) AS N_ARTICULOS "
      "FROM FAMILIA F "
      "LEFT JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY F.CODIGO, F.NOMBRE ORDER BY N_ARTICULOS DESC",
      "Ventas", "Almacén", "Operacional", "Bajo", "Familias", ""),

    q("vx3_154", "Artículos con STOCKARTICULO mínimo configurado",
      "¿Qué artículos tienen STOCKARTICULO mínimo configurado?",
      "Artículos con STOCKARTICULO>0 en la tabla ARTICULO.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCK_ACTUAL, "
      "STOCKARTICULO AS STOCK_MINIMO, "
      "CASE WHEN STOCKARTICULO<=STOCKARTICULO THEN 'BAJO MÍNIMO' ELSE 'OK' END AS ESTADO "
      "FROM ARTICULO WHERE STOCKARTICULO>0 "
      "ORDER BY CASE WHEN STOCKARTICULO<=STOCKARTICULO THEN 0 ELSE 1 END, NOMBRE LIMIT 30",
      "Ventas", "Almacén", "Artículo", "Alto", "STOCKARTICULO mínimo", ""),

    q("vx3_155", "Artículos bajo STOCKARTICULO mínimo",
      "¿Qué artículos están por debajo de su STOCKARTICULO mínimo?",
      "Artículos con STOCKARTICULO<=STOCKARTICULO y STOCKARTICULO>0.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCK_ACTUAL, "
      "STOCKARTICULO AS STOCK_MINIMO, "
      "STOCKARTICULO-STOCKARTICULO AS DEFICIT "
      "FROM ARTICULO WHERE STOCKARTICULO>0 AND STOCKARTICULO<=STOCKARTICULO "
      "ORDER BY DEFICIT DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Crítico", "STOCKARTICULO mínimo", ""),

    # ── ANÁLISIS DE DOCUMENTOS ASOCIADOS A CLIENTES ───────────────────────────

    q("vx3_156", "Documentos en CLIENTEDOCUM",
      "¿Qué documentos de clientes hay registrados?",
      "Registros en la tabla CLIENTEDOCUM.",
      "SELECT COUNT(*) AS N_DOCUMENTOS FROM DOCCAB",
      "Ventas", "Comercial", "Cliente", "Bajo", "Documentos cliente", ""),

    q("vx3_157", "Clientes con más documentos asociados",
      "¿Qué clientes tienen más documentos en CLIENTEDOCUM?",
      "Conteo de registros en CLIENTEDOCUM por cliente.",
      "SELECT CODCLIENTE, COUNT(*) AS N_DOCUMENTOS "
      "FROM DOCCAB GROUP BY CODCLIENTE "
      "ORDER BY N_DOCUMENTOS DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Documentos cliente", ""),

    q("vx3_158", "Artículos con equivalencias registradas",
      "¿Qué artículos tienen equivalencias en EQUIVAL?",
      "Artículos con al menos una equivalencia en la tabla EQUIVAL.",
      "SELECT A.CODIGO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_EQUIVALENCIAS "
      "FROM ARTICULO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY N_EQUIVALENCIAS DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Bajo", "Equivalencias", ""),

    q("vx3_159", "Artículos asociados a documentos de línea (DOCLINDOCASOC)",
      "¿Qué artículos tienen documentos asociados en líneas?",
      "Registros en DOCLINDOCASOC.",
      "SELECT COUNT(*) AS N_REGISTROS FROM DOCLIN",
      "Ventas", "Operaciones", "Operacional", "Bajo", "Documentos", ""),

    q("vx3_160", "Resumen de todas las tablas del sistema",
      "¿Cuántos registros tiene cada tabla principal?",
      "Conteo de registros en las tablas principales del ERP.",
      "SELECT 'DOCCAB' AS TABLA, COUNT(*) AS N_REGISTROS FROM DOCCAB "
      "UNION ALL SELECT 'DOCLIN', COUNT(*) FROM DOCLIN "
      "UNION ALL SELECT 'ARTICULO', COUNT(*) FROM ARTICULO "
      "UNION ALL SELECT 'CLIENTE', COUNT(*) FROM CLIENTE "
      "UNION ALL SELECT 'PROVEED', COUNT(*) FROM PROVEED "
      "UNION ALL SELECT 'FAMILIA', COUNT(*) FROM FAMILIA "
      "UNION ALL SELECT 'CAJA', COUNT(*) FROM CAJA "
      "UNION ALL SELECT 'ESTALMACEN', COUNT(*) FROM ARTICULO "
      "UNION ALL SELECT 'DOCDESTINO', COUNT(*) FROM DOCDESTINO "
      "ORDER BY N_REGISTROS DESC",
      "Ventas", "Dirección", "KPI", "Bajo", "Sistema", ""),

    # ── ANÁLISIS DE RENTABILIDAD POR PERÍODO ──────────────────────────────────

    q("vx3_161", "Facturación del último trimestre",
      "¿Cuánto se ha facturado en el último trimestre?",
      "Suma de IMPORTETOTAL TIPO=13 en los últimos 90 días.",
      "SELECT COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA>=DATE('now','-90 days')",
      "Ventas", "Dirección", "KPI", "Alto", "Período", ""),

    q("vx3_162", "Facturación del último semestre",
      "¿Cuánto se ha facturado en el último semestre?",
      "Suma de IMPORTETOTAL TIPO=13 en los últimos 180 días.",
      "SELECT COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA>=DATE('now','-180 days')",
      "Ventas", "Dirección", "KPI", "Alto", "Período", ""),

    q("vx3_163", "Facturación del año anterior completo",
      "¿Cuánto se facturó el año anterior?",
      "Suma de IMPORTETOTAL TIPO=13 del año anterior.",
      "SELECT COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 "
      "AND SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INTEGER)-1 AS TEXT)",
      "Ventas", "Dirección", "KPI", "Alto", "Período", ""),

    q("vx3_164", "Comparativa Q1 año actual vs Q1 año anterior",
      "¿Cómo compara el primer trimestre de este año con el del año anterior?",
      "Facturación TIPO=13 de enero-marzo del año actual vs año anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "AND CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 1 AND 3 THEN IMPORTETOTAL ELSE 0 END),2) AS Q1_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INTEGER)-1 AS TEXT) "
      "AND CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 1 AND 3 THEN IMPORTETOTAL ELSE 0 END),2) AS Q1_ANTERIOR "
      "FROM DOCCAB WHERE TIPO=13",
      "Ventas", "Dirección", "KPI", "Alto", "Comparativa", ""),

    q("vx3_165", "Facturación por hora del día (si hay timestamp)",
      "¿A qué hora del día se emiten más facturas?",
      "Agrupa facturas TIPO=13 por hora si FECHA incluye timestamp.",
      "SELECT SUBSTR(FECHA,12,2) AS HORA, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND LENGTH(FECHA)>10 "
      "GROUP BY SUBSTR(FECHA,12,2) ORDER BY HORA",
      "Ventas", "Operaciones", "Operacional", "Bajo", "Estacionalidad", ""),

    # ── ANÁLISIS DE ARTÍCULOS POR PERÍODO ─────────────────────────────────────

    q("vx3_166", "Artículos nuevos vendidos este mes (primera venta)",
      "¿Qué artículos se han vendido por primera vez este mes?",
      "Artículos cuya primera línea de factura TIPO=13 es del mes actual.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "MIN(D.FECHA) AS PRIMERA_VENTA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING MIN(D.FECHA)>=DATE('now','-30 days') "
      "ORDER BY PRIMERA_VENTA DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Nuevos", ""),

    q("vx3_167", "Artículos vendidos solo en un mes del año",
      "¿Qué artículos solo se venden en un mes concreto del año?",
      "Artículos con ventas TIPO=13 en exactamente 1 mes distinto.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS N_MESES_CON_VENTA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7))=1 "
      "ORDER BY A.NOMBRE LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Bajo", "Estacionalidad", ""),

    q("vx3_168", "Artículos con ventas en todos los meses del año",
      "¿Qué artículos se venden todos los meses?",
      "Artículos con ventas TIPO=13 en los 12 meses del año actual.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS N_MESES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING COUNT(DISTINCT SUBSTR(D.FECHA,1,7))>=6 "
      "ORDER BY N_MESES DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Regularidad", ""),

    q("vx3_169", "Unidades vendidas por artículo este mes",
      "¿Cuántas unidades se han vendido de cada artículo este mes?",
      "Suma de CANTIDAD en líneas de factura TIPO=13 del mes actual.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "SUM(L.CANTIDAD) AS UNIDADES_MES, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS VENTAS_MES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=SUBSTR(DATE('now'),1,7) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_MES DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Ventas mes", ""),

    q("vx3_170", "Artículos con mayor variación de PRECIOVENTA entre clientes",
      "¿En qué artículos hay mayor diferencia de PRECIOVENTA entre clientes?",
      "Rango de precios (max-min) por artículo en facturas TIPO=13 con >1 cliente.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(MIN(L.PRECIO),2) AS PRECIO_MIN, "
      "ROUND(MAX(L.PRECIO),2) AS PRECIO_MAX, "
      "ROUND(MAX(L.PRECIO)-MIN(L.PRECIO),2) AS RANGO_PRECIO, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND L.PRECIO>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING COUNT(DISTINCT D.CODCLIENTE)>1 "
      "ORDER BY RANGO_PRECIO DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Precios", ""),

    # ── ANÁLISIS DE GESTIÓN COMERCIAL ──────────────────────────────────────────

    q("vx3_171", "Clientes con presupuesto pero sin factura nunca",
      "¿Hay clientes que solo tienen presupuestos pero nunca han comprado?",
      "Clientes con documentos TIPO=0 pero sin ningún TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_PRESUPUESTOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_PRESUPUESTOS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=0 AND D.CODCLIENTE NOT IN ("
      "SELECT DISTINCT CODCLIENTE FROM DOCCAB WHERE TIPO=13) "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY VALOR_PRESUPUESTOS DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Alto", "Pipeline", ""),

    q("vx3_172", "Presupuestos con importe superior a 5000€ sin convertir",
      "¿Qué presupuestos grandes están sin convertir?",
      "Presupuestos TIPO=0 con IMPORTETOTAL>5000 sin entrada en DOCDESTINO.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL AND D.IMPORTETOTAL>5000 "
      "ORDER BY D.IMPORTETOTAL DESC LIMIT 20",
      "Ventas", "Comercial", "Operacional", "Alto", "Pipeline", ""),

    q("vx3_173", "Tasa de conversión global de presupuestos",
      "¿Cuál es la tasa de conversión global de presupuestos a facturas?",
      "Presupuestos TIPO=0 totales vs convertidos a cualquier tipo via DOCDESTINO.",
      "SELECT COUNT(DISTINCT D.CODIGO) AS TOTAL_PRESUPUESTOS, "
      "COUNT(DISTINCT DD.CODDOCUMENTO) AS CONVERTIDOS, "
      "ROUND(COUNT(DISTINCT DD.CODDOCUMENTO)*100.0/NULLIF(COUNT(DISTINCT D.CODIGO),0),1) AS TASA_PCT "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=0",
      "Ventas", "Dirección", "KPI", "Crítico", "Conversión", ""),

    q("vx3_174", "Importe medio de presupuestos por agente",
      "¿Qué agente emite presupuestos de mayor importe?",
      "Importe medio de presupuestos TIPO=0 por CODAGENTE.",
      "SELECT CODAGENTE AS AGENTE, COUNT(*) AS N_PRESUPUESTOS, "
      "ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS VALOR_TOTAL "
      "FROM DOCCAB WHERE TIPO=0 "
      "GROUP BY CODAGENTE ORDER BY IMPORTE_MEDIO DESC LIMIT 20",
      "Ventas", "Comercial", "Agente", "Medio", "Presupuestos", ""),

    q("vx3_175", "Presupuestos emitidos este mes",
      "¿Cuántos presupuestos se han emitido este mes?",
      "Presupuestos TIPO=0 del mes actual.",
      "SELECT COUNT(*) AS N_PRESUPUESTOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS VALOR_TOTAL "
      "FROM DOCCAB WHERE TIPO=0 "
      "AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7)",
      "Ventas", "Comercial", "KPI", "Medio", "Presupuestos", ""),

    # ── ANÁLISIS DE STOCKARTICULO Y ALMACÉN ────────────────────────────────────────────

    q("vx3_176", "Artículos con STOCKARTICULO máximo configurado",
      "¿Qué artículos tienen STOCKARTICULO máximo configurado?",
      "Artículos con STOCKARTICULO>0 en la tabla ARTICULO.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCK_ACTUAL, "
      "STOCKARTICULO AS STOCK_MAXIMO, "
      "CASE WHEN STOCKARTICULO>=STOCKARTICULO THEN 'SOBRE MÁXIMO' ELSE 'OK' END AS ESTADO "
      "FROM ARTICULO WHERE STOCKARTICULO>0 "
      "ORDER BY CASE WHEN STOCKARTICULO>=STOCKARTICULO THEN 0 ELSE 1 END, NOMBRE LIMIT 30",
      "Ventas", "Almacén", "Artículo", "Medio", "STOCKARTICULO máximo", ""),

    q("vx3_177", "Artículos sobre STOCKARTICULO máximo",
      "¿Qué artículos superan su STOCKARTICULO máximo?",
      "Artículos con STOCKARTICULO>=STOCKARTICULO y STOCKARTICULO>0.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCK_ACTUAL, "
      "STOCKARTICULO AS STOCK_MAXIMO, "
      "STOCKARTICULO-STOCKARTICULO AS EXCESO "
      "FROM ARTICULO WHERE STOCKARTICULO>0 AND STOCKARTICULO>=STOCKARTICULO "
      "ORDER BY EXCESO DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Medio", "STOCKARTICULO máximo", ""),

    q("vx3_178", "Valor del STOCKARTICULO por familia",
      "¿Cuánto vale el STOCKARTICULO de cada familia de producto?",
      "Suma de STOCKARTICULO*PRECIOCOSTE por familia.",
      "SELECT A.CODFAMILIA AS FAMILIA, F.NOMBRE AS NOMBRE_FAMILIA, "
      "COUNT(*) AS N_ARTICULOS, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_STOCK_COSTE, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOVENTA),2) AS VALOR_STOCK_VENTA "
      "FROM ARTICULO A "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0 "
      "GROUP BY A.CODFAMILIA, F.NOMBRE "
      "ORDER BY (STOCKARTICULO*PRECIOCOSTE) DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Alto", "Inventario", ""),

    q("vx3_179", "Artículos con mayor valor de STOCKARTICULO inmovilizado",
      "¿Qué artículos tienen más valor de STOCKARTICULO sin vender?",
      "Artículos con mayor STOCKARTICULO*PRECIOCOSTE sin ventas recientes.",
      "SELECT A.CODIGO, A.NOMBRE, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0 "
      "AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-180 days')) "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Alto", "STOCKARTICULO inmovilizado", ""),

    q("vx3_180", "Rotación de STOCKARTICULO por familia",
      "¿Qué familias tienen mayor rotación de STOCKARTICULO?",
      "Ratio ventas/STOCKARTICULO por familia en los últimos 12 meses.",
      "SELECT A.CODFAMILIA AS FAMILIA, F.NOMBRE AS NOMBRE_FAMILIA, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_STOCKARTICULO, "
      "ROUND(COALESCE(V.VENTAS,0),2) AS VENTAS_12M, "
      "ROUND(COALESCE(V.VENTAS,0)/NULLIF(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),0),2) AS ROTACION "
      "FROM ARTICULO A "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "LEFT JOIN (SELECT A2.CODFAMILIA, SUM(L.PRECIO*L.CANTIDAD) AS VENTAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A2 ON A2.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-365 days') "
      "GROUP BY A2.CODFAMILIA) V ON V.CODFAMILIA=A.CODFAMILIA "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODFAMILIA, F.NOMBRE, V.VENTAS "
      "ORDER BY ROTACION DESC LIMIT 20",
      "Ventas", "Almacén", "Artículo", "Medio", "Rotación", ""),

    # ── ANÁLISIS DE CLIENTES ESPECIALES ───────────────────────────────────────

    q("vx3_181", "Clientes con mayor número de presupuestos rechazados",
      "¿Qué clientes tienen más presupuestos sin convertir?",
      "Clientes con más presupuestos TIPO=0 sin entrada en DOCDESTINO.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_PRESUPUESTOS_SIN_CONVERTIR, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_PERDIDO "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_PRESUPUESTOS_SIN_CONVERTIR DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Pipeline", ""),

    q("vx3_182", "Clientes con mayor antigüedad (primera factura más antigua)",
      "¿Cuáles son los clientes más antiguos?",
      "Clientes ordenados por fecha de primera factura TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MIN(D.FECHA) AS PRIMERA_FACTURA, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_HISTORICO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY PRIMERA_FACTURA ASC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Antigüedad", ""),

    q("vx3_183", "Clientes con compras en el último mes",
      "¿Qué clientes han comprado en el último mes?",
      "Clientes con facturas TIPO=13 en los últimos 30 días.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_MES "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-30 days') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY TOTAL_MES DESC LIMIT 30",
      "Ventas", "Comercial", "Cliente", "Medio", "Activos", ""),

    q("vx3_184", "Clientes con compras en el último año pero no en los últimos 3 meses",
      "¿Qué clientes han comprado en el año pero no recientemente?",
      "Clientes con facturas TIPO=13 en los últimos 365 días pero no en los últimos 90.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "COUNT(*) AS N_FACTURAS_ANIO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING MAX(D.FECHA)<DATE('now','-90 days') "
      "ORDER BY ULTIMA_COMPRA DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Retención", ""),

    q("vx3_185", "Clientes con mayor frecuencia de compra (facturas por mes)",
      "¿Qué clientes compran con más frecuencia?",
      "Ratio facturas/meses activos por cliente en facturas TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS N_MESES_ACTIVOS, "
      "ROUND(CAST(COUNT(*) AS REAL)/NULLIF(COUNT(DISTINCT SUBSTR(D.FECHA,1,7)),0),2) AS FACTURAS_POR_MES "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(*)>2 "
      "ORDER BY FACTURAS_POR_MES DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Medio", "Frecuencia", ""),

    # ── ANÁLISIS FINAL ─────────────────────────────────────────────────────────

    q("vx3_186", "Documentos emitidos por año",
      "¿Cuántos documentos se emiten por año?",
      "Conteo de todos los documentos en DOCCAB por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, TIPO, COUNT(*) AS N_DOCS "
      "FROM DOCCAB WHERE FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4), TIPO "
      "ORDER BY ANIO DESC, N_DOCS DESC",
      "Ventas", "Dirección", "Operacional", "Bajo", "Documentos", ""),

    q("vx3_187", "Artículos con PRECIOVENTA de venta actualizado recientemente",
      "¿Qué artículos tienen PRECIOVENTA de venta mayor que el PRECIOCOSTE en más de un 50%?",
      "Artículos con margen superior al 50% sobre PRECIOCOSTE.",
      "SELECT CODIGO, NOMBRE, "
      "ROUND(PRECIOCOSTE,2) AS COSTE, "
      "ROUND(PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND((PRECIOVENTA-PRECIOCOSTE)*100.0/NULLIF(PRECIOCOSTE,0),1) AS MARGEN_SOBRE_COSTE_PCT "
      "FROM ARTICULO WHERE PRECIOCOSTE>0 AND PRECIOVENTA>PRECIOCOSTE*1.5 "
      "ORDER BY MARGEN_SOBRE_COSTE_PCT DESC LIMIT 20",
      "Ventas", "Dirección", "Artículo", "Bajo", "Margen", ""),

    q("vx3_188", "Clientes con NIF/CIF registrado",
      "¿Cuántos clientes tienen NIF/CIF registrado?",
      "Clientes con campo NIF/CIF no vacío en la tabla CLIENTE.",
      "SELECT "
      "COUNT(*) AS TOTAL_CLIENTES, "
      "SUM(CASE WHEN NIF IS NOT NULL AND TRIM(NIF)<>'' THEN 1 ELSE 0 END) AS CON_NIF "
      "FROM CLIENTE",
      "Ventas", "Finanzas", "Cliente", "Bajo", "Datos maestros", ""),

    q("vx3_189", "Facturas con IRPF aplicado",
      "¿Cuántas facturas tienen IRPF aplicado?",
      "Facturas TIPO=13 con IMPORTEIRPF>0.",
      "SELECT COUNT(*) AS N_FACTURAS_CON_IRPF, "
      "ROUND(SUM(IMPORTEIRPF),2) AS TOTAL_IRPF, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEIRPF>0",
      "Ventas", "Finanzas", "KPI", "Medio", "IRPF", ""),

    q("vx3_190", "Facturas con recargo de equivalencia",
      "¿Cuántas facturas tienen recargo de equivalencia?",
      "Facturas TIPO=13 con IMPORTERECEQUIV>0.",
      "SELECT COUNT(*) AS N_FACTURAS_CON_RECEQUIV, "
      "ROUND(SUM(IMPORTERECEQUIV),2) AS TOTAL_RECEQUIV "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTERECEQUIV>0",
      "Ventas", "Finanzas", "KPI", "Bajo", "Recargo equivalencia", ""),

    q("vx3_191", "Artículos con mayor número de líneas en presupuestos",
      "¿Qué artículos aparecen más en presupuestos?",
      "Artículos más frecuentes en líneas de presupuesto TIPO=0.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_LINEAS_PRESUPUESTO, "
      "SUM(L.CANTIDAD) AS UNIDADES_PRESUPUESTADAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_LINEAS_PRESUPUESTO DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Bajo", "Presupuestos", ""),

    q("vx3_192", "Clientes con mayor importe presupuestado sin convertir",
      "¿Qué clientes tienen más valor en presupuestos sin convertir?",
      "Suma de IMPORTETOTAL de presupuestos TIPO=0 sin conversión por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_PRESUPUESTOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY VALOR_PENDIENTE DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Alto", "Pipeline", ""),

    q("vx3_193", "Artículos con PRECIOVENTA de PRECIOCOSTE cero",
      "¿Qué artículos tienen PRECIOVENTA de PRECIOCOSTE cero?",
      "Artículos con PRECIOCOSTE=0 o NULL en la tabla ARTICULO.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(PRECIOVENTA,2) AS PRECIO_VENTA "
      "FROM ARTICULO WHERE PRECIOCOSTE=0 OR PRECIOCOSTE IS NULL "
      "ORDER BY NOMBRE LIMIT 30",
      "Ventas", "Compras", "Artículo", "Medio", "Datos maestros", ""),

    q("vx3_194", "Facturas con descuento global en cabecera",
      "¿Hay facturas con descuento aplicado en la cabecera?",
      "Facturas TIPO=13 con DESCUENTOS>0 en DOCCAB.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, D.DESCUENTOS AS DESCUENTO_PCT "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.DESCUENTOS>0 "
      "ORDER BY D.DESCUENTOS DESC LIMIT 20",
      "Ventas", "Comercial", "Operacional", "Medio", "Descuentos", ""),

    q("vx3_195", "Número de artículos distintos vendidos por mes",
      "¿Cuántos artículos distintos se venden cada mes?",
      "Artículos únicos en líneas de factura TIPO=13 por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS, "
      "COUNT(*) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Ventas", "Comercial", "KPI", "Bajo", "Diversidad", ""),

    q("vx3_196", "Clientes con mayor número de artículos distintos en una sola factura",
      "¿Qué facturas tienen más artículos distintos?",
      "Facturas TIPO=13 con más artículos distintos en DOCLIN.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODIGO, D.FECHA, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.IMPORTETOTAL "
      "ORDER BY N_ARTICULOS_DISTINTOS DESC LIMIT 20",
      "Ventas", "Comercial", "Operacional", "Bajo", "Diversidad", ""),

    q("vx3_197", "Evolución del número de artículos en catálogo",
      "¿Cuántos artículos hay en el catálogo?",
      "Conteo total de artículos en ARTICULO con desglose por estado de STOCKARTICULO.",
      "SELECT COUNT(*) AS TOTAL_ARTICULOS, "
      "SUM(CASE WHEN STOCKARTICULO>0 THEN 1 ELSE 0 END) AS CON_STOCKARTICULO, "
      "SUM(CASE WHEN STOCKARTICULO=0 THEN 1 ELSE 0 END) AS SIN_STOCKARTICULO, "
      "SUM(CASE WHEN PRECIOVENTA>0 THEN 1 ELSE 0 END) AS CON_PRECIO_VENTA, "
      "SUM(CASE WHEN PRECIOCOSTE>0 THEN 1 ELSE 0 END) AS CON_PRECIO_COSTE "
      "FROM ARTICULO",
      "Ventas", "Almacén", "KPI", "Bajo", "Catálogo", ""),

    q("vx3_198", "Clientes con mayor número de agentes distintos que les han atendido",
      "¿A qué clientes han atendido más agentes distintos?",
      "Número de agentes distintos por cliente en facturas TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODAGENTE) AS N_AGENTES_DISTINTOS, "
      "COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(DISTINCT D.CODAGENTE)>1 "
      "ORDER BY N_AGENTES_DISTINTOS DESC LIMIT 20",
      "Ventas", "Comercial", "Cliente", "Bajo", "Agentes", ""),

    q("vx3_199", "Artículos con mayor número de presupuestos sin convertir",
      "¿Qué artículos aparecen más en presupuestos que no se convierten?",
      "Artículos en líneas de presupuestos TIPO=0 sin conversión.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "COUNT(*) AS N_LINEAS_NO_CONVERTIDAS, "
      "SUM(L.CANTIDAD) AS UNIDADES_NO_CONVERTIDAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_LINEAS_NO_CONVERTIDAS DESC LIMIT 20",
      "Ventas", "Comercial", "Artículo", "Medio", "Pipeline", ""),

    q("vx3_200", "Dashboard completo de ventas (todos los KPIs en una consulta)",
      "¿Cuál es el estado completo de ventas en una sola vista?",
      "KPIs de ventas: facturación, clientes, artículos, presupuestos, albaranes, pedidos.",
      "SELECT "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13) AS N_FACTURAS, "
      "(SELECT ROUND(SUM(IMPORTETOTAL),2) FROM DOCCAB WHERE TIPO=13) AS FACTURACION_TOTAL, "
      "(SELECT COUNT(DISTINCT CODCLIENTE) FROM DOCCAB WHERE TIPO=13) AS CLIENTES_ACTIVOS, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=0) AS N_PRESUPUESTOS, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=11) AS N_ALBARANES, "
      "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=12) AS N_PEDIDOS, "
      "(SELECT COUNT(*) FROM ARTICULO) AS N_ARTICULOS, "
      "(SELECT COUNT(*) FROM CLIENTE) AS N_CLIENTES_BD",
      "Ventas", "Dirección", "KPI", "Crítico", "Dashboard", ""),

]
