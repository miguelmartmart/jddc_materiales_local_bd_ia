"""
query_library/direccion_v3.py — 125 consultas adicionales de Dirección (v3).

Diferentes a NULL.py y direccion_v2.py. Cubren: análisis estratégico avanzado,
cuadro de mando integral, análisis de rentabilidad por segmento, gestión de riesgos,
análisis de tendencias macroeconómicas internas, benchmarking interno, análisis de
eficiencia operativa, gestión del capital circulante, y análisis de sostenibilidad.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: strftime, JULIANDAY, SUBSTR, CAST, COALESCE.
Sin comentarios subjetivos. Solo hechos verificables con datos.
"""

from backend.modules.db_simulator.query_library.builder import q

QUERIES_DIRECCION_V3: list = [

    # ── CUADRO DE MANDO EJECUTIVO ──────────────────────────────────────────────

    q("dx3_001", "KPIs ejecutivos del mes actual",
      "¿Cuáles son los indicadores clave del mes en curso?",
      "Ventas, cobros, pedidos y clientes activos del mes actual.",
      "SELECT "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now')) AS VENTAS_MES, "
      "(SELECT COUNT(DISTINCT D.CODCLIENTE) FROM DOCCAB D "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now')) AS CLIENTES_ACTIVOS, "
      "(SELECT COUNT(*) FROM DOCCAB D "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now')) AS N_FACTURAS, "
      "(SELECT COUNT(*) FROM DOCCAB D "
      "WHERE D.TIPO=1 AND SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now')) AS PEDIDOS_RECIBIDOS",
      "Dirección", "Dirección", "KPI", "Critico", "Dashboard", ""),

    q("dx3_002", "Comparativa mensual: mes actual vs mes anterior",
      "¿Cómo se compara el mes actual con el mes anterior?",
      "Ventas, facturas y clientes del mes actual vs mes anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m','now') "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=STRFTIME('%Y-%m',DATE('now','-1 month')) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_MES_ANTERIOR "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-60 days')",
      "Dirección", "Dirección", "KPI", "Critico", "Comparativa", ""),

    q("dx3_003", "Comparativa trimestral: trimestre actual vs anterior",
      "¿Cómo se compara el trimestre actual con el anterior?",
      "Ventas del trimestre actual vs trimestre anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN D.FECHA >= DATE('now','-90 days') "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_TRIM_ACTUAL, "
      "ROUND(SUM(CASE WHEN D.FECHA BETWEEN DATE('now','-180 days') "
      "AND DATE('now','-91 days') THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_TRIM_ANTERIOR "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-180 days')",
      "Dirección", "Dirección", "KPI", "Critico", "Comparativa", ""),

    q("dx3_004", "Evolución de ventas por año (últimos 5 años)",
      "¿Cuál es la tendencia de ventas en los últimos 5 años?",
      "Ventas totales agrupadas por año en los últimos 5 años.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_TOTALES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-5 years') "
      "GROUP BY SUBSTR(D.FECHA,1,4) "
      "ORDER BY ANIO DESC",
      "Dirección", "Dirección", "KPI", "Critico", "Tendencia", ""),

    q("dx3_005", "Tasa de crecimiento anual de ventas (CAGR)",
      "¿Cuál es la tasa de crecimiento compuesto de las ventas?",
      "Ventas del año actual vs año anterior para calcular crecimiento.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_ANIO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_ANIO_ANTERIOR, "
      "ROUND((SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END) - "
      "SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END))*100.0/"
      "NULLIF(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),0),1) AS CRECIMIENTO_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Critico", "Crecimiento", ""),

    q("dx3_006", "Distribución de ventas por departamento/área",
      "¿Cómo se distribuyen las ventas entre los distintos departamentos?",
      "Ventas agrupadas por departamento o zona de venta.",
      "SELECT D.CODALMACEN AS ZONA, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODALMACEN "
      "ORDER BY VENTAS DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Distribución", ""),

    q("dx3_007", "Top 10 clientes por contribución al margen",
      "¿Qué clientes contribuyen más al margen bruto?",
      "Margen bruto (ventas - PRECIOCOSTE) por cliente en facturas TIPO=13.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE_VENTAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO, "
      "ROUND((SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE))*100.0/"
      "NULLIF(SUM(L.CANTIDAD*L.PRECIO),0),1) AS MARGEN_PCT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY MARGEN_BRUTO DESC LIMIT 10",
      "Dirección", "Dirección", "KPI", "Critico", "Margen", ""),

    q("dx3_008", "Margen bruto total de la empresa",
      "¿Cuál es el margen bruto total de la empresa?",
      "Diferencia entre ventas totales y PRECIOCOSTE de ventas en facturas TIPO=13.",
      "SELECT "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_TOTALES, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE_VENTAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO, "
      "ROUND((SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE))*100.0/"
      "NULLIF(SUM(L.CANTIDAD*L.PRECIO),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0",
      "Dirección", "Dirección", "KPI", "Critico", "Margen", ""),

    q("dx3_009", "Evolución del margen bruto por mes",
      "¿Cómo evoluciona el margen bruto mes a mes?",
      "Margen bruto mensual en los últimos 12 meses.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO, "
      "ROUND((SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE))*100.0/"
      "NULLIF(SUM(L.CANTIDAD*L.PRECIO),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Critico", "Margen", ""),

    q("dx3_010", "Rentabilidad por línea de producto (familia)",
      "¿Qué familias de productos son más rentables?",
      "Margen bruto por familia de artículo en facturas de venta.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO, "
      "ROUND((SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE))*100.0/"
      "NULLIF(SUM(L.CANTIDAD*L.PRECIO),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY F.NOMBRE "
      "ORDER BY MARGEN_BRUTO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Critico", "Rentabilidad", ""),

    # ── ANÁLISIS DE CLIENTES ESTRATÉGICO ───────────────────────────────────────

    q("dx3_011", "Concentración de ventas en top clientes (riesgo Pareto)",
      "¿Qué porcentaje de las ventas depende de los 10 principales clientes?",
      "Ventas de los top 10 clientes sobre ventas totales.",
      "SELECT "
      "ROUND(SUM(TOP10.VENTAS_CLIENTE),2) AS VENTAS_TOP10, "
      "ROUND((SELECT SUM(L.CANTIDAD*L.PRECIO) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO WHERE D.TIPO=13),2) AS VENTAS_TOTALES, "
      "ROUND(SUM(TOP10.VENTAS_CLIENTE)*100.0/"
      "(SELECT SUM(L.CANTIDAD*L.PRECIO) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO WHERE D.TIPO=13),1) AS PCT_CONCENTRACION "
      "FROM (SELECT D.CODCLIENTE, SUM(L.CANTIDAD*L.PRECIO) AS VENTAS_CLIENTE "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE "
      "ORDER BY VENTAS_CLIENTE DESC LIMIT 10) TOP10",
      "Dirección", "Dirección", "KPI", "Critico", "Concentración", ""),

    q("dx3_012", "Clientes nuevos vs recurrentes por año",
      "¿Cuántos clientes nuevos se captan cada año?",
      "Clientes que facturan por primera vez en cada año.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "COUNT(DISTINCT D.CODCLIENTE) AS CLIENTES_TOTALES "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 "
      "GROUP BY SUBSTR(D.FECHA,1,4) "
      "ORDER BY ANIO DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Clientes", ""),

    q("dx3_013", "Tasa de retención de clientes (año actual vs anterior)",
      "¿Qué porcentaje de clientes del año anterior siguen comprando?",
      "Clientes que compraron el año anterior y también el actual.",
      "SELECT "
      "COUNT(DISTINCT CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "THEN D.CODCLIENTE END) AS CLIENTES_ANIO_ANTERIOR, "
      "COUNT(DISTINCT CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "AND D.CODCLIENTE IN ("
      "SELECT DISTINCT CODCLIENTE FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT)) "
      "THEN D.CODCLIENTE END) AS CLIENTES_RETENIDOS "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Critico", "Retención", ""),

    q("dx3_014", "Valor de vida del cliente (LTV estimado)",
      "¿Cuál es el valor histórico acumulado de cada cliente?",
      "Ventas totales históricas por cliente como proxy del LTV.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,4)) AS ANIOS_ACTIVO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS LTV_HISTORICO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)/NULLIF(COUNT(DISTINCT SUBSTR(D.FECHA,1,4)),0),2) AS LTV_ANUAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY LTV_HISTORICO DESC LIMIT 25",
      "Dirección", "Dirección", "KPI", "Critico", "LTV", ""),

    q("dx3_015", "Clientes con mayor potencial de crecimiento",
      "¿Qué clientes muestran tendencia creciente en sus compras?",
      "Clientes con mayor crecimiento entre el último trimestre y el anterior.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(CASE WHEN D.FECHA >= DATE('now','-90 days') "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_TRIM_ACTUAL, "
      "ROUND(SUM(CASE WHEN D.FECHA BETWEEN DATE('now','-180 days') "
      "AND DATE('now','-91 days') THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_TRIM_ANTERIOR "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-180 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING VENTAS_TRIM_ACTUAL > VENTAS_TRIM_ANTERIOR AND VENTAS_TRIM_ANTERIOR>0 "
      "ORDER BY (VENTAS_TRIM_ACTUAL-VENTAS_TRIM_ANTERIOR) DESC LIMIT 15",
      "Dirección", "Dirección", "KPI", "Alto", "Crecimiento", ""),

    q("dx3_016", "Clientes en riesgo de abandono (sin compra en 90 días)",
      "¿Qué clientes habituales no han comprado en los últimos 3 meses?",
      "Clientes con historial de compra pero sin factura en los últimos 90 días.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "ROUND(JULIANDAY('now')-JULIANDAY(MAX(D.FECHA)),0) AS DIAS_SIN_COMPRA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_HISTORICAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING MAX(D.FECHA) < DATE('now','-90 days') "
      "AND VENTAS_HISTORICAS > 1000 "
      "ORDER BY VENTAS_HISTORICAS DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Critico", "Churn", ""),

    q("dx3_017", "Segmentación de clientes por volumen de compra",
      "¿Cómo se distribuyen los clientes por volumen de compra?",
      "Clientes agrupados en segmentos por volumen anual de compra.",
      "SELECT "
      "CASE WHEN VENTAS_ANUALES >= 50000 THEN 'A: >50k' "
      "WHEN VENTAS_ANUALES >= 10000 THEN 'B: 10k-50k' "
      "WHEN VENTAS_ANUALES >= 1000 THEN 'C: 1k-10k' "
      "ELSE 'D: <1k' END AS SEGMENTO, "
      "COUNT(*) AS N_CLIENTES, "
      "ROUND(SUM(VENTAS_ANUALES),2) AS VENTAS_SEGMENTO "
      "FROM (SELECT D.CODCLIENTE, SUM(L.CANTIDAD*L.PRECIO) AS VENTAS_ANUALES "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE) CLIENTES "
      "GROUP BY SEGMENTO "
      "ORDER BY SEGMENTO",
      "Dirección", "Dirección", "KPI", "Alto", "Segmentación", ""),

    q("dx3_018", "Clientes con mayor número de facturas en el año",
      "¿Qué clientes compran con más frecuencia?",
      "Clientes con mayor número de facturas en el año actual.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_TOTALES, "
      "ROUND(AVG(L.CANTIDAD*L.PRECIO),2) AS TICKET_MEDIO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Frecuencia", ""),

    q("dx3_019", "Análisis RFM: Recencia, Frecuencia, Monetario",
      "¿Cuál es el perfil RFM de los principales clientes?",
      "Días desde última compra, número de facturas y ventas totales por cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(JULIANDAY('now')-JULIANDAY(MAX(D.FECHA)),0) AS RECENCIA_DIAS, "
      "COUNT(DISTINCT D.CODIGO) AS FRECUENCIA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS MONETARIO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY MONETARIO DESC LIMIT 30",
      "Dirección", "Dirección", "KPI", "Critico", "RFM", ""),

    q("dx3_020", "Clientes con mayor ticket medio por factura",
      "¿Qué clientes tienen el ticket medio más alto?",
      "Importe medio por factura por cliente en el último año.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_TOTALES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)/COUNT(DISTINCT D.CODIGO),2) AS TICKET_MEDIO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING N_FACTURAS>=3 "
      "ORDER BY TICKET_MEDIO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Ticket medio", ""),

    # ── ANÁLISIS FINANCIERO ESTRATÉGICO ────────────────────────────────────────

    q("dx3_021", "Saldo de clientes pendiente de cobro",
      "¿Cuánto dinero está pendiente de cobrar de clientes?",
      "Facturas de venta (TIPO=13) sin cobro registrado.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS_PENDIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_PENDIENTE, "
      "MIN(D.FECHA) AS FACTURA_MAS_ANTIGUA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY IMPORTE_PENDIENTE DESC LIMIT 25",
      "Dirección", "Dirección", "KPI", "Critico", "Cobros", ""),

    q("dx3_022", "Antigüedad de la deuda de clientes",
      "¿Cuál es la antigüedad de las facturas pendientes de cobro?",
      "Facturas pendientes agrupadas por tramos de antigüedad.",
      "SELECT "
      "CASE WHEN JULIANDAY('now')-JULIANDAY(D.FECHA) <= 30 THEN '0-30 días' "
      "WHEN JULIANDAY('now')-JULIANDAY(D.FECHA) <= 60 THEN '31-60 días' "
      "WHEN JULIANDAY('now')-JULIANDAY(D.FECHA) <= 90 THEN '61-90 días' "
      "WHEN JULIANDAY('now')-JULIANDAY(D.FECHA) <= 180 THEN '91-180 días' "
      "ELSE '>180 días' END AS TRAMO_ANTIGUEDAD, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY TRAMO_ANTIGUEDAD "
      "ORDER BY TRAMO_ANTIGUEDAD",
      "Dirección", "Dirección", "KPI", "Critico", "Cobros", ""),

    q("dx3_023", "Saldo pendiente de pago a proveedores",
      "¿Cuánto dinero está pendiente de pagar a proveedores?",
      "Facturas de compra (TIPO=20) sin pago registrado.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL), CAST(D.CODCLIENTE AS TEXT)) AS PROVEEDOR, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS_PENDIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_PENDIENTE, "
      "MIN(D.FECHA) AS FACTURA_MAS_ANTIGUA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN PROVEED P ON P.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=20 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODCLIENTE, PROVEEDOR "
      "ORDER BY IMPORTE_PENDIENTE DESC LIMIT 25",
      "Dirección", "Dirección", "KPI", "Critico", "Pagos", ""),

    q("dx3_024", "Ratio de morosidad (facturas vencidas sobre total)",
      "¿Qué porcentaje de las facturas están vencidas?",
      "Facturas con fecha de vencimiento superada sobre total de facturas.",
      "SELECT "
      "COUNT(DISTINCT D.CODIGO) AS TOTAL_FACTURAS, "
      "COUNT(DISTINCT CASE WHEN D.IMPORTEENTREGADO=0 THEN D.CODIGO END) AS FACTURAS_PENDIENTES, "
      "ROUND(COUNT(DISTINCT CASE WHEN D.IMPORTEENTREGADO=0 THEN D.CODIGO END)*100.0/"
      "NULLIF(COUNT(DISTINCT D.CODIGO),0),1) AS RATIO_PENDIENTE_PCT "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Critico", "Morosidad", ""),

    q("dx3_025", "Flujo de caja estimado (cobros vs pagos por mes)",
      "¿Cuál es el flujo de caja estimado mes a mes?",
      "Diferencia entre cobros de clientes y pagos a proveedores por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS COBROS_ESTIMADOS, "
      "ROUND(SUM(CASE WHEN D.TIPO=20 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS PAGOS_ESTIMADOS, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO "
      "ELSE -L.CANTIDAD*L.PRECIO END),2) AS FLUJO_NETO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO IN (13,20) AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Critico", "Flujo de caja", ""),

    q("dx3_026", "Periodo medio de cobro (PMC)",
      "¿Cuántos días tarda la empresa en cobrar sus facturas?",
      "Días medios entre fecha de factura y fecha de cobro.",
      "SELECT "
      "ROUND(AVG(JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)),1) AS PMC_DIAS, "
      "COUNT(*) AS N_FACTURAS_COBRADAS "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=1 "
      "AND D.FECHA IS NOT NULL AND D.FECHA IS NOT NULL",
      "Dirección", "Dirección", "KPI", "Critico", "PMC", ""),

    q("dx3_027", "Periodo medio de pago (PMP)",
      "¿Cuántos días tarda la empresa en pagar a sus proveedores?",
      "Días medios entre fecha de factura de compra y fecha de pago.",
      "SELECT "
      "ROUND(AVG(JULIANDAY(D.FECHA)-JULIANDAY(D.FECHA)),1) AS PMP_DIAS, "
      "COUNT(*) AS N_FACTURAS_PAGADAS "
      "FROM DOCCAB D "
      "WHERE D.TIPO=20 AND D.IMPORTEENTREGADO=1 "
      "AND D.FECHA IS NOT NULL AND D.FECHA IS NOT NULL",
      "Dirección", "Dirección", "KPI", "Critico", "PMP", ""),

    q("dx3_028", "Capital circulante (clientes + STOCKARTICULO - proveedores)",
      "¿Cuál es el capital circulante de la empresa?",
      "Suma de saldos de clientes y STOCKARTICULO menos saldo de proveedores.",
      "SELECT "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0) AS SALDO_CLIENTES, "
      "(SELECT ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO WHERE A.STOCKARTICULO>0) AS VALOR_STOCKARTICULO, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=20 AND D.IMPORTEENTREGADO=0) AS SALDO_PROVEEDORES",
      "Dirección", "Dirección", "KPI", "Critico", "Capital circulante", ""),

    q("dx3_029", "Facturas de alto importe pendientes de cobro",
      "¿Qué facturas de gran importe están pendientes de cobro?",
      "Facturas individuales de más de 5.000€ sin cobrar.",
      "SELECT D.CODIGO AS COD_FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE, "
      "ROUND(JULIANDAY('now')-JULIANDAY(D.FECHA),0) AS DIAS_PENDIENTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE "
      "HAVING IMPORTE>5000 "
      "ORDER BY IMPORTE DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Critico", "Cobros", ""),

    q("dx3_030", "Evolución de la deuda de clientes por mes",
      "¿Cómo evoluciona el saldo pendiente de cobro mes a mes?",
      "Importe de facturas emitidas sin cobrar agrupadas por mes de emisión.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_EMITIDO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Dirección", "Dirección", "KPI", "Critico", "Cobros", ""),

    # ── ANÁLISIS DE PROVEEDORES ESTRATÉGICO ────────────────────────────────────

    q("dx3_031", "Concentración de compras en top proveedores",
      "¿Qué porcentaje de las compras depende de los 5 principales proveedores?",
      "Compras de los top 5 proveedores sobre compras totales.",
      "SELECT "
      "ROUND(SUM(TOP5.COMPRAS_PROV),2) AS COMPRAS_TOP5, "
      "ROUND((SELECT SUM(L.CANTIDAD*L.PRECIO) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO WHERE D.TIPO=20),2) AS COMPRAS_TOTALES, "
      "ROUND(SUM(TOP5.COMPRAS_PROV)*100.0/"
      "(SELECT SUM(L.CANTIDAD*L.PRECIO) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO WHERE D.TIPO=20),1) AS PCT_CONCENTRACION "
      "FROM (SELECT D.CODCLIENTE, SUM(L.CANTIDAD*L.PRECIO) AS COMPRAS_PROV "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=20 GROUP BY D.CODCLIENTE "
      "ORDER BY COMPRAS_PROV DESC LIMIT 5) TOP5",
      "Dirección", "Dirección", "KPI", "Critico", "Concentración", ""),

    q("dx3_032", "Proveedores estratégicos (alto volumen y único artículo)",
      "¿Qué proveedores son estratégicos por volumen y exclusividad?",
      "Proveedores con alto volumen de compra y artículos exclusivos.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL), CAST(D.CODCLIENTE AS TEXT)) AS PROVEEDOR, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS COMPRAS_TOTALES "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN PROVEED P ON P.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=20 "
      "GROUP BY D.CODCLIENTE, PROVEEDOR "
      "ORDER BY COMPRAS_TOTALES DESC LIMIT 15",
      "Dirección", "Dirección", "KPI", "Alto", "Proveedores", ""),

    q("dx3_033", "Evolución de compras por año",
      "¿Cómo han evolucionado las compras a proveedores por año?",
      "Compras totales agrupadas por año.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_PROVEEDORES, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS COMPRAS_TOTALES "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=20 "
      "GROUP BY SUBSTR(D.FECHA,1,4) "
      "ORDER BY ANIO DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Compras", ""),

    q("dx3_034", "Ratio compras/ventas por mes",
      "¿Qué porcentaje de las ventas se destina a compras?",
      "Relación entre compras y ventas por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=20 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS COMPRAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=20 THEN L.CANTIDAD*L.PRECIO ELSE 0 END)*100.0/"
      "NULLIF(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),0),1) AS RATIO_PCT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO IN (13,20) AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Ratio", ""),

    q("dx3_035", "Proveedores con mayor crecimiento de compras",
      "¿A qué proveedores se les compra más que el año anterior?",
      "Proveedores con mayor incremento de compras año actual vs anterior.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL), CAST(D.CODCLIENTE AS TEXT)) AS PROVEEDOR, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS COMPRAS_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS COMPRAS_ANTERIOR "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN PROVEED P ON P.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=20 "
      "GROUP BY D.CODCLIENTE, PROVEEDOR "
      "HAVING COMPRAS_ACTUAL > COMPRAS_ANTERIOR AND COMPRAS_ANTERIOR>0 "
      "ORDER BY (COMPRAS_ACTUAL-COMPRAS_ANTERIOR) DESC LIMIT 15",
      "Dirección", "Dirección", "KPI", "Medio", "Proveedores", ""),

    # ── ANÁLISIS DE RECURSOS HUMANOS Y PRODUCTIVIDAD ───────────────────────────

    q("dx3_036", "Productividad por comercial (ventas por usuario)",
      "¿Cuánto vende cada comercial/usuario?",
      "Ventas totales por usuario en facturas TIPO=13.",
      "SELECT D.CODAGENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_TOTALES "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODAGENTE "
      "ORDER BY VENTAS_TOTALES DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Productividad", ""),

    q("dx3_037", "Evolución de productividad por comercial (trimestral)",
      "¿Cómo evoluciona la productividad de cada comercial por trimestre?",
      "Ventas por usuario y trimestre en los últimos 4 trimestres.",
      "SELECT D.CODAGENTE, "
      "SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODAGENTE, SUBSTR(D.FECHA,1,7) "
      "ORDER BY D.CODAGENTE, MES DESC LIMIT 60",
      "Dirección", "Dirección", "KPI", "Alto", "Productividad", ""),

    q("dx3_038", "Documentos procesados por usuario (actividad total)",
      "¿Cuántos documentos procesa cada usuario?",
      "Total de documentos de cualquier tipo por usuario.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_DOCUMENTOS, "
      "COUNT(DISTINCT D.TIPO) AS TIPOS_DISTINTOS, "
      "MIN(D.FECHA) AS PRIMER_DOC, MAX(D.FECHA) AS ULTIMO_DOC "
      "FROM DOCCAB D "
      "WHERE D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_DOCUMENTOS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Actividad", ""),

    q("dx3_039", "Usuarios más activos en el último mes",
      "¿Qué usuarios han generado más actividad en el último mes?",
      "Documentos generados por usuario en los últimos 30 días.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_DOCUMENTOS, "
      "COUNT(DISTINCT D.TIPO) AS TIPOS_DISTINTOS "
      "FROM DOCCAB D "
      "WHERE D.FECHA >= DATE('now','-30 days') "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_DOCUMENTOS DESC LIMIT 15",
      "Dirección", "Dirección", "KPI", "Medio", "Actividad", ""),

    q("dx3_040", "Ratio de conversión pedidos a facturas por comercial",
      "¿Qué porcentaje de pedidos convierte cada comercial en facturas?",
      "Pedidos (TIPO=1) vs facturas (TIPO=13) por usuario.",
      "SELECT D.CODAGENTE, "
      "COUNT(DISTINCT CASE WHEN D.TIPO=1 THEN D.CODIGO END) AS N_PEDIDOS, "
      "COUNT(DISTINCT CASE WHEN D.TIPO=13 THEN D.CODIGO END) AS N_FACTURAS, "
      "ROUND(COUNT(DISTINCT CASE WHEN D.TIPO=13 THEN D.CODIGO END)*100.0/"
      "NULLIF(COUNT(DISTINCT CASE WHEN D.TIPO=1 THEN D.CODIGO END),0),1) AS RATIO_CONVERSION_PCT "
      "FROM DOCCAB D "
      "WHERE D.TIPO IN (1,13) AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODAGENTE "
      "HAVING N_PEDIDOS>0 "
      "ORDER BY RATIO_CONVERSION_PCT DESC LIMIT 15",
      "Dirección", "Dirección", "KPI", "Alto", "Conversión", ""),

    # ── ANÁLISIS DE RIESGOS ────────────────────────────────────────────────────

    q("dx3_041", "Clientes con riesgo de crédito (deuda alta y reciente)",
      "¿Qué clientes tienen mayor riesgo de crédito?",
      "Clientes con deuda pendiente superior a 10.000€ y más de 60 días.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS DEUDA_TOTAL, "
      "MIN(D.FECHA) AS FACTURA_MAS_ANTIGUA, "
      "ROUND(JULIANDAY('now')-JULIANDAY(MIN(D.FECHA)),0) AS DIAS_DEUDA_MAX "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING DEUDA_TOTAL>10000 AND DIAS_DEUDA_MAX>60 "
      "ORDER BY DEUDA_TOTAL DESC LIMIT 15",
      "Dirección", "Dirección", "Alerta", "Critico", "Riesgo crédito", ""),

    q("dx3_042", "Proveedores con riesgo de dependencia crítica",
      "¿Qué proveedores representan un riesgo de dependencia crítica?",
      "Proveedores que suministran más del 30% de las compras totales.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL), CAST(D.CODCLIENTE AS TEXT)) AS PROVEEDOR, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS COMPRAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)*100.0/"
      "(SELECT SUM(L2.CANTIDAD*L2.PRECIO) FROM DOCLIN L2 "
      "JOIN DOCCAB D2 ON D2.CODIGO=L2.CODDOCUMENTO WHERE D2.TIPO=20),1) AS PCT_COMPRAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN PROVEED P ON P.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=20 "
      "GROUP BY D.CODCLIENTE, PROVEEDOR "
      "HAVING PCT_COMPRAS>30 "
      "ORDER BY PCT_COMPRAS DESC",
      "Dirección", "Dirección", "Alerta", "Critico", "Riesgo", ""),

    q("dx3_043", "Artículos con riesgo de rotura de STOCKARTICULO crítico",
      "¿Qué artículos tienen riesgo inminente de rotura de STOCKARTICULO?",
      "Artículos con STOCKARTICULO para menos de 7 días de venta.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(L.CANTIDAD)/30.0,3) AS CONSUMO_DIARIO, "
      "ROUND(SUM(A.STOCKARTICULO)/NULLIF(SUM(L.CANTIDAD)/30.0,0),0) AS DIAS_COBERTURA "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.TIPO=13 AND D.FECHA >= DATE('now','-30 days') "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING CONSUMO_DIARIO>0 AND DIAS_COBERTURA<7 "
      "ORDER BY DIAS_COBERTURA ASC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Critico", "Riesgo STOCKARTICULO", ""),

    q("dx3_044", "Facturas con errores o anomalías detectadas",
      "¿Existen facturas con anomalías en importes o datos?",
      "Facturas con importe cero, negativo o sin líneas.",
      "SELECT D.CODIGO, D.FECHA, D.TIPO, D.CODCLIENTE, "
      "COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(COALESCE(L.CANTIDAD*L.PRECIO,0)),2) AS IMPORTE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODIGO, D.FECHA, D.TIPO, D.CODCLIENTE "
      "HAVING N_LINEAS=0 OR IMPORTE<=0 "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Critico", "Anomalías", ""),

    q("dx3_045", "Clientes con historial de impagos",
      "¿Qué clientes tienen historial de facturas sin cobrar?",
      "Clientes con más de 2 facturas pendientes de cobro.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS_IMPAGADAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_IMPAGADO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING N_FACTURAS_IMPAGADAS>2 "
      "ORDER BY IMPORTE_IMPAGADO DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Critico", "Impagos", ""),

    # ── ANÁLISIS DE MERCADO Y COMPETITIVIDAD ───────────────────────────────────

    q("dx3_046", "Nuevos artículos vendidos en el último trimestre",
      "¿Qué artículos nuevos se han incorporado a las ventas?",
      "Artículos con primera venta en los últimos 90 días.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "MIN(D.FECHA) AS PRIMERA_VENTA, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING MIN(D.FECHA) >= DATE('now','-90 days') "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Innovación", ""),

    q("dx3_047", "Artículos descatalogados (sin venta en 1 año)",
      "¿Qué artículos no se han vendido en el último año?",
      "Artículos sin ninguna venta en los últimos 365 días.",
      "SELECT A.CODIGO, A.NOMBRE, A.CODFAMILIA, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A "
      " "
      "WHERE A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days')) "
      "GROUP BY A.CODIGO, A.NOMBRE, A.CODFAMILIA, A.PRECIOCOSTE "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 30",
      "Dirección", "Dirección", "Alerta", "Alto", "Catálogo", ""),

    q("dx3_048", "Penetración de mercado por zona geográfica",
      "¿Cómo se distribuyen las ventas por zona geográfica?",
      "Ventas agrupadas por provincia o código postal del cliente.",
      "SELECT COALESCE(C.CP, 'Sin provincia') AS PROVINCIA, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY COALESCE(C.CP, 'Sin provincia') "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Geografía", ""),

    q("dx3_049", "Ventas a clientes nuevos vs recurrentes",
      "¿Qué porcentaje de las ventas proviene de clientes nuevos?",
      "Ventas de clientes con primera compra en el año actual vs recurrentes.",
      "SELECT "
      "ROUND(SUM(CASE WHEN PRIMERA_COMPRA.PRIMER_ANIO=CAST(STRFTIME('%Y','now') AS TEXT) "
      "THEN VENTAS_CLIENTE ELSE 0 END),2) AS VENTAS_CLIENTES_NUEVOS, "
      "ROUND(SUM(CASE WHEN PRIMERA_COMPRA.PRIMER_ANIO<CAST(STRFTIME('%Y','now') AS TEXT) "
      "THEN VENTAS_CLIENTE ELSE 0 END),2) AS VENTAS_CLIENTES_RECURRENTES "
      "FROM (SELECT D.CODCLIENTE, "
      "MIN(SUBSTR(D.FECHA,1,4)) AS PRIMER_ANIO, "
      "SUM(L.CANTIDAD*L.PRECIO) AS VENTAS_CLIENTE "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "GROUP BY D.CODCLIENTE) PRIMERA_COMPRA",
      "Dirección", "Dirección", "KPI", "Alto", "Captación", ""),

    q("dx3_050", "Estacionalidad de ventas por mes del año",
      "¿En qué meses del año se vende más?",
      "Ventas agrupadas por mes del año (sin año) para ver estacionalidad.",
      "SELECT SUBSTR(D.FECHA,6,2) AS MES_NUM, "
      "CASE SUBSTR(D.FECHA,6,2) "
      "WHEN '01' THEN 'Enero' WHEN '02' THEN 'Febrero' "
      "WHEN '03' THEN 'Marzo' WHEN '04' THEN 'Abril' "
      "WHEN '05' THEN 'Mayo' WHEN '06' THEN 'Junio' "
      "WHEN '07' THEN 'Julio' WHEN '08' THEN 'Agosto' "
      "WHEN '09' THEN 'Septiembre' WHEN '10' THEN 'Octubre' "
      "WHEN '11' THEN 'Noviembre' WHEN '12' THEN 'Diciembre' END AS MES_NOMBRE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(AVG(VENTAS_MES.VENTAS),2) AS VENTAS_MEDIA "
      "FROM DOCCAB D "
      "JOIN (SELECT SUBSTR(D2.FECHA,6,2) AS MES2, "
      "SUM(L2.CANTIDAD*L2.PRECIO) AS VENTAS "
      "FROM DOCCAB D2 JOIN DOCLIN L2 ON L2.CODDOCUMENTO=D2.CODIGO "
      "WHERE D2.TIPO=13 GROUP BY SUBSTR(D2.FECHA,1,7)) VENTAS_MES "
      "ON VENTAS_MES.MES2=SUBSTR(D.FECHA,6,2) "
      "WHERE D.TIPO=13 "
      "GROUP BY SUBSTR(D.FECHA,6,2) "
      "ORDER BY MES_NUM",
      "Dirección", "Dirección", "KPI", "Alto", "Estacionalidad", ""),

    # ── ANÁLISIS OPERATIVO ESTRATÉGICO ─────────────────────────────────────────

    q("dx3_051", "Tiempo medio de ciclo de venta (pedido a factura)",
      "¿Cuántos días transcurren desde el pedido hasta la factura?",
      "Días entre pedido de venta (TIPO=1) y factura (TIPO=13).",
      "SELECT "
      "ROUND(AVG(JULIANDAY(D_FAC.FECHA)-JULIANDAY(D_PED.FECHA)),1) AS DIAS_CICLO_MEDIO, "
      "COUNT(*) AS N_CICLOS "
      "FROM DOCCAB D_PED "
      "JOIN DOCCAB D_FAC ON 1=0 AND D_FAC.TIPO=13 "
      "WHERE D_PED.TIPO=1 AND D_PED.FECHA IS NOT NULL AND D_FAC.FECHA IS NOT NULL",
      "Dirección", "Dirección", "KPI", "Alto", "Ciclo venta", ""),

    q("dx3_052", "Tiempo medio de ciclo de compra (pedido a factura)",
      "¿Cuántos días transcurren desde el pedido de compra hasta la factura?",
      "Días entre pedido de compra (TIPO=4) y factura de compra (TIPO=20).",
      "SELECT "
      "ROUND(AVG(JULIANDAY(D_FAC.FECHA)-JULIANDAY(D_PED.FECHA)),1) AS DIAS_CICLO_MEDIO, "
      "COUNT(*) AS N_CICLOS "
      "FROM DOCCAB D_PED "
      "JOIN DOCCAB D_FAC ON 1=0 AND D_FAC.TIPO=20 "
      "WHERE D_PED.TIPO=4 AND D_PED.FECHA IS NOT NULL AND D_FAC.FECHA IS NOT NULL",
      "Dirección", "Dirección", "KPI", "Alto", "Ciclo compra", ""),

    q("dx3_053", "Pedidos de venta pendientes de servir (backlog)",
      "¿Cuánto backlog de pedidos hay pendiente de servir?",
      "Pedidos de venta (TIPO=1) sin albarán ni factura asociada.",
      "SELECT "
      "COUNT(DISTINCT D.CODIGO) AS N_PEDIDOS_PENDIENTES, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES_ESPERANDO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VALOR_BACKLOG, "
      "MIN(D.FECHA) AS PEDIDO_MAS_ANTIGUO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=1 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO IN (11,13))",
      "Dirección", "Dirección", "KPI", "Critico", "Backlog", ""),

    q("dx3_054", "Tasa de cumplimiento de pedidos (on-time delivery)",
      "¿Qué porcentaje de pedidos se sirven en el plazo acordado?",
      "Pedidos con albarán en menos de 5 días sobre total de pedidos.",
      "SELECT "
      "COUNT(*) AS TOTAL_PEDIDOS, "
      "COUNT(CASE WHEN JULIANDAY(D_ALB.FECHA)-JULIANDAY(D_PED.FECHA)<=5 THEN 1 END) AS EN_PLAZO, "
      "ROUND(COUNT(CASE WHEN JULIANDAY(D_ALB.FECHA)-JULIANDAY(D_PED.FECHA)<=5 THEN 1 END)*100.0/"
      "NULLIF(COUNT(*),0),1) AS PCT_EN_PLAZO "
      "FROM DOCCAB D_PED "
      "JOIN DOCCAB D_ALB ON 1=0 AND D_ALB.TIPO=11 "
      "WHERE D_PED.TIPO=1 AND D_PED.FECHA IS NOT NULL AND D_ALB.FECHA IS NOT NULL",
      "Dirección", "Dirección", "KPI", "Critico", "OTD", ""),

    q("dx3_055", "Presupuestos convertidos en pedidos (tasa de conversión)",
      "¿Qué porcentaje de presupuestos se convierten en pedidos?",
      "Presupuestos (TIPO=2) con pedido asociado sobre total de presupuestos.",
      "SELECT "
      "COUNT(DISTINCT D_PRES.CODIGO) AS TOTAL_PRESUPUESTOS, "
      "COUNT(DISTINCT D_PED.CODIGO) AS CONVERTIDOS_EN_PEDIDO, "
      "ROUND(COUNT(DISTINCT D_PED.CODIGO)*100.0/"
      "NULLIF(COUNT(DISTINCT D_PRES.CODIGO),0),1) AS TASA_CONVERSION_PCT "
      "FROM DOCCAB D_PRES "
      "LEFT JOIN DOCCAB D_PED ON 1=0 AND D_PED.TIPO=1 "
      "WHERE D_PRES.TIPO=2",
      "Dirección", "Dirección", "KPI", "Alto", "Conversión", ""),

    # ── ANÁLISIS DE CALIDAD Y SATISFACCIÓN ─────────────────────────────────────

    q("dx3_056", "Tasa de devoluciones sobre ventas totales",
      "¿Qué porcentaje de las ventas se devuelve?",
      "Importe de abonos (TIPO=14) sobre ventas (TIPO=13).",
      "SELECT "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=14 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS DEVOLUCIONES, "
      "ROUND(SUM(CASE WHEN D.TIPO=14 THEN L.CANTIDAD*L.PRECIO ELSE 0 END)*100.0/"
      "NULLIF(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),0),2) AS TASA_DEVOLUCION_PCT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO IN (13,14)",
      "Dirección", "Dirección", "KPI", "Alto", "Calidad", ""),

    q("dx3_057", "Evolución de devoluciones por mes",
      "¿Cómo evoluciona la tasa de devoluciones mes a mes?",
      "Importe de devoluciones (TIPO=14) por mes en los últimos 12 meses.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_ABONOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_DEVUELTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=14 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Calidad", ""),

    q("dx3_058", "Clientes con mayor tasa de devolución",
      "¿Qué clientes devuelven más en proporción a sus compras?",
      "Ratio devoluciones/ventas por cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=14 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS DEVOLUCIONES, "
      "ROUND(SUM(CASE WHEN D.TIPO=14 THEN L.CANTIDAD*L.PRECIO ELSE 0 END)*100.0/"
      "NULLIF(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),0),1) AS TASA_PCT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO IN (13,14) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING DEVOLUCIONES>0 "
      "ORDER BY TASA_PCT DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Alto", "Calidad", ""),

    q("dx3_059", "Reclamaciones y abonos por familia de producto",
      "¿Qué familias generan más devoluciones?",
      "Importe de abonos (TIPO=14) por familia de artículo.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "COUNT(DISTINCT D.CODIGO) AS N_ABONOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_DEVUELTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=14 "
      "GROUP BY F.NOMBRE "
      "ORDER BY IMPORTE_DEVUELTO DESC LIMIT 15",
      "Dirección", "Dirección", "Alerta", "Alto", "Calidad", ""),

    q("dx3_060", "NPS proxy: clientes que repiten vs que no repiten",
      "¿Qué porcentaje de clientes repite compra?",
      "Clientes con más de una factura sobre total de clientes.",
      "SELECT "
      "COUNT(DISTINCT D.CODCLIENTE) AS TOTAL_CLIENTES, "
      "COUNT(DISTINCT CASE WHEN CNT.N_FACTURAS>1 THEN D.CODCLIENTE END) AS CLIENTES_REPITEN, "
      "ROUND(COUNT(DISTINCT CASE WHEN CNT.N_FACTURAS>1 THEN D.CODCLIENTE END)*100.0/"
      "NULLIF(COUNT(DISTINCT D.CODCLIENTE),0),1) AS PCT_REPITEN "
      "FROM DOCCAB D "
      "JOIN (SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS FROM DOCCAB "
      "WHERE TIPO=13 GROUP BY CODCLIENTE) CNT ON CNT.CODCLIENTE=D.CODCLIENTE "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Alto", "Fidelización", ""),

    # ── ANÁLISIS DE SOSTENIBILIDAD Y EFICIENCIA ────────────────────────────────

    q("dx3_061", "Artículos con mayor impacto en ventas (80/20)",
      "¿Qué artículos generan el 80% de las ventas?",
      "Top artículos por ventas que acumulan el 80% del total.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)*100.0/"
      "(SELECT SUM(L2.CANTIDAD*L2.PRECIO) FROM DOCLIN L2 "
      "JOIN DOCCAB D2 ON D2.CODIGO=L2.CODDOCUMENTO WHERE D2.TIPO=13),2) AS PCT_VENTAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Critico", "Pareto", ""),

    q("dx3_062", "Eficiencia de la cartera de productos",
      "¿Qué porcentaje de artículos genera el 80% de las ventas?",
      "Número de artículos necesarios para alcanzar el 80% de ventas.",
      "SELECT "
      "COUNT(DISTINCT L.CODARTICULO) AS TOTAL_ARTICULOS_VENDIDOS, "
      "(SELECT COUNT(*) FROM ("
      "SELECT L2.CODIGO, SUM(L2.CANTIDAD*L2.PRECIO) AS V "
      "FROM DOCLIN L2 JOIN DOCCAB D2 ON D2.CODIGO=L2.CODDOCUMENTO "
      "WHERE D2.TIPO=13 GROUP BY L2.CODIGO "
      "ORDER BY V DESC LIMIT 20) T) AS ARTICULOS_TOP20, "
      "ROUND((SELECT SUM(V) FROM ("
      "SELECT L2.CODIGO, SUM(L2.CANTIDAD*L2.PRECIO) AS V "
      "FROM DOCLIN L2 JOIN DOCCAB D2 ON D2.CODIGO=L2.CODDOCUMENTO "
      "WHERE D2.TIPO=13 GROUP BY L2.CODIGO "
      "ORDER BY V DESC LIMIT 20) T)*100.0/"
      "NULLIF(SUM(L.CANTIDAD*L.PRECIO),0),1) AS PCT_VENTAS_TOP20 "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Alto", "Eficiencia", ""),

    q("dx3_063", "Rotación del inventario (veces por año)",
      "¿Cuántas veces rota el inventario al año?",
      "PRECIOCOSTE de ventas dividido entre valor medio del inventario.",
      "SELECT "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE_VENTAS_ANUAL, "
      "(SELECT ROUND(SUM(A.STOCKARTICULO*A2.PRECIOCOSTE),2) FROM ARTICULO E "
      "JOIN ARTICULO A2 ON A2.CODIGO=A.CODIGO WHERE A.STOCKARTICULO>0) AS VALOR_INVENTARIO, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE)/"
      "NULLIF((SELECT SUM(A.STOCKARTICULO*A2.PRECIOCOSTE) FROM ARTICULO E "
      "JOIN ARTICULO A2 ON A2.CODIGO=A.CODIGO WHERE A.STOCKARTICULO>0),0),2) AS ROTACION_ANUAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "AND D.FECHA >= DATE('now','-365 days')",
      "Dirección", "Dirección", "KPI", "Critico", "Rotación", ""),

    q("dx3_064", "Días de inventario (DSI)",
      "¿Cuántos días de ventas representa el inventario actual?",
      "Valor del inventario dividido entre PRECIOCOSTE de ventas diario.",
      "SELECT "
      "(SELECT ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO WHERE A.STOCKARTICULO>0) AS VALOR_INVENTARIO, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE)/365.0,2) AS COSTE_VENTAS_DIARIO, "
      "ROUND((SELECT SUM(A.STOCKARTICULO*A2.PRECIOCOSTE) FROM ARTICULO E "
      "JOIN ARTICULO A2 ON A2.CODIGO=A.CODIGO WHERE A.STOCKARTICULO>0)/"
      "NULLIF(SUM(L.CANTIDAD*A.PRECIOCOSTE)/365.0,0),0) AS DSI_DIAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "AND D.FECHA >= DATE('now','-365 days')",
      "Dirección", "Dirección", "KPI", "Critico", "DSI", ""),

    q("dx3_065", "Ciclo de conversión de efectivo (CCE)",
      "¿Cuántos días tarda la empresa en convertir inversiones en efectivo?",
      "DSI + PMC - PMP como proxy del ciclo de conversión de efectivo.",
      "SELECT "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D_COBRO.FECHA)),0) AS PMC_ESTIMADO, "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D_PAGO.FECHA)),0) AS PMP_ESTIMADO "
      "FROM DOCCAB D_COBRO, DOCCAB D_PAGO "
      "WHERE D_COBRO.TIPO=13 AND D_COBRO.COBRADO=0 "
      "AND D_PAGO.TIPO=20 AND D_PAGO.COBRADO=0",
      "Dirección", "Dirección", "KPI", "Critico", "CCE", ""),

    # ── ANÁLISIS DE PRESUPUESTOS Y OBJETIVOS ───────────────────────────────────

    q("dx3_066", "Presupuestos emitidos por mes",
      "¿Cuántos presupuestos se emiten cada mes?",
      "Presupuestos (TIPO=2) agrupados por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_PRESUPUESTOS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=2 "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Dirección", "Dirección", "KPI", "Alto", "Presupuestos", ""),

    q("dx3_067", "Tasa de conversión de presupuestos por mes",
      "¿Qué porcentaje de presupuestos se convierten en pedidos cada mes?",
      "Presupuestos con pedido asociado sobre total por mes.",
      "SELECT SUBSTR(D_PRES.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D_PRES.CODIGO) AS N_PRESUPUESTOS, "
      "COUNT(DISTINCT D_PED.CODIGO) AS N_CONVERTIDOS, "
      "ROUND(COUNT(DISTINCT D_PED.CODIGO)*100.0/"
      "NULLIF(COUNT(DISTINCT D_PRES.CODIGO),0),1) AS TASA_CONVERSION_PCT "
      "FROM DOCCAB D_PRES "
      "LEFT JOIN DOCCAB D_PED ON 1=0 AND D_PED.TIPO=1 "
      "WHERE D_PRES.TIPO=2 "
      "GROUP BY SUBSTR(D_PRES.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 12",
      "Dirección", "Dirección", "KPI", "Alto", "Conversión", ""),

    q("dx3_068", "Importe medio de presupuesto por cliente",
      "¿Cuál es el importe medio de los presupuestos por cliente?",
      "Importe medio de presupuestos (TIPO=2) por cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_PRESUPUESTOS, "
      "ROUND(AVG(PRES.IMPORTE),2) AS IMPORTE_MEDIO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "JOIN (SELECT L.CODDOCUMENTO, SUM(L.CANTIDAD*L.PRECIO) AS IMPORTE "
      "FROM DOCLIN L GROUP BY L.CODDOCUMENTO) PRES ON PRES.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=2 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY IMPORTE_MEDIO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Presupuestos", ""),

    q("dx3_069", "Presupuestos sin respuesta (más de 30 días)",
      "¿Qué presupuestos llevan más de 30 días sin respuesta?",
      "Presupuestos (TIPO=2) sin pedido asociado emitidos hace más de 30 días.",
      "SELECT D.CODIGO AS COD_PRESUPUESTO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE, "
      "ROUND(JULIANDAY('now')-JULIANDAY(D.FECHA),0) AS DIAS_SIN_RESPUESTA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=2 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=1) "
      "AND D.FECHA < DATE('now','-30 days') "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE "
      "ORDER BY DIAS_SIN_RESPUESTA DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Alto", "Presupuestos", ""),

    q("dx3_070", "Valor total del pipeline de ventas (presupuestos activos)",
      "¿Cuánto vale el pipeline de ventas actual?",
      "Importe total de presupuestos activos sin convertir en pedido.",
      "SELECT "
      "COUNT(DISTINCT D.CODIGO) AS N_PRESUPUESTOS_ACTIVOS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES_EN_PIPELINE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VALOR_PIPELINE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=2 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=1) "
      "AND D.FECHA >= DATE('now','-90 days')",
      "Dirección", "Dirección", "KPI", "Critico", "Pipeline", ""),

    # ── ANÁLISIS COMPARATIVO Y BENCHMARKING ────────────────────────────────────

    q("dx3_071", "Comparativa de ventas por día de la semana",
      "¿Qué días de la semana se factura más?",
      "Ventas agrupadas por día de la semana.",
      "SELECT STRFTIME('%w',D.FECHA) AS DIA_NUM, "
      "CASE STRFTIME('%w',D.FECHA) "
      "WHEN '1' THEN 'Lunes' WHEN '2' THEN 'Martes' "
      "WHEN '3' THEN 'Miércoles' WHEN '4' THEN 'Jueves' "
      "WHEN '5' THEN 'Viernes' ELSE 'Fin de semana' END AS DIA, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY STRFTIME('%w',D.FECHA) "
      "ORDER BY DIA_NUM",
      "Dirección", "Dirección", "KPI", "Medio", "Actividad", ""),

    q("dx3_072", "Comparativa de ventas por hora del día",
      "¿A qué horas del día se factura más?",
      "Ventas agrupadas por hora de creación de la factura.",
      "SELECT SUBSTR(D.HORA,1,2) AS HORA, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.HORA IS NOT NULL "
      "GROUP BY SUBSTR(D.HORA,1,2) "
      "ORDER BY HORA",
      "Dirección", "Dirección", "KPI", "Bajo", "Actividad", ""),

    q("dx3_073", "Ticket medio de venta por mes",
      "¿Cómo evoluciona el ticket medio de venta mes a mes?",
      "Importe medio por factura de venta por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_TOTALES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)/COUNT(DISTINCT D.CODIGO),2) AS TICKET_MEDIO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Ticket medio", ""),

    q("dx3_074", "Número medio de líneas por factura",
      "¿Cuántas líneas tiene de media cada factura?",
      "Número medio de líneas por factura de venta.",
      "SELECT "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(L.CODARTICULO) AS TOTAL_LINEAS, "
      "ROUND(COUNT(L.CODARTICULO)*1.0/COUNT(DISTINCT D.CODIGO),1) AS LINEAS_MEDIA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Medio", "Eficiencia", ""),

    q("dx3_075", "Evolución del número de clientes activos por mes",
      "¿Cómo evoluciona la base de clientes activos mes a mes?",
      "Clientes distintos con factura en cada mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODCLIENTE) AS CLIENTES_ACTIVOS "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Clientes", ""),

    # ── ANÁLISIS DE GESTIÓN INTERNA ────────────────────────────────────────────

    q("dx3_076", "Documentos generados por tipo en el último mes",
      "¿Cuántos documentos de cada tipo se han generado en el último mes?",
      "Todos los tipos de documento agrupados por tipo en los últimos 30 días.",
      "SELECT D.TIPO, "
      "COUNT(*) AS N_DOCUMENTOS, "
      "COUNT(DISTINCT D.CODAGENTE) AS N_USUARIOS "
      "FROM DOCCAB D "
      "WHERE D.FECHA >= DATE('now','-30 days') "
      "GROUP BY D.TIPO "
      "ORDER BY N_DOCUMENTOS DESC",
      "Dirección", "Dirección", "KPI", "Medio", "Actividad", ""),

    q("dx3_077", "Actividad del sistema por mes (total documentos)",
      "¿Cómo evoluciona la actividad total del sistema mes a mes?",
      "Total de documentos de todos los tipos por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_DOCUMENTOS, "
      "COUNT(DISTINCT D.TIPO) AS TIPOS_DISTINTOS, "
      "COUNT(DISTINCT D.CODAGENTE) AS N_USUARIOS "
      "FROM DOCCAB D "
      "WHERE D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Bajo", "Actividad", ""),

    q("dx3_078", "Resumen ejecutivo anual",
      "¿Cuál es el resumen ejecutivo del año en curso?",
      "Métricas clave del año: ventas, clientes, facturas, margen.",
      "SELECT "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS VENTAS_ANIO, "
      "(SELECT COUNT(DISTINCT D.CODCLIENTE) FROM DOCCAB D "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS CLIENTES_ACTIVOS, "
      "(SELECT COUNT(*) FROM DOCCAB D "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS N_FACTURAS, "
      "(SELECT COUNT(*) FROM DOCCAB D "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0) AS FACTURAS_PENDIENTES_COBRO",
      "Dirección", "Dirección", "KPI", "Critico", "Resumen", ""),

    q("dx3_079", "Comparativa de ventas por trimestre (últimos 2 años)",
      "¿Cómo se comparan los trimestres de los últimos 2 años?",
      "Ventas por trimestre en los últimos 8 trimestres.",
      "SELECT "
      "SUBSTR(D.FECHA,1,4) AS ANIO, "
      "CASE WHEN SUBSTR(D.FECHA,6,2) IN ('01','02','03') THEN 'Q1' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('04','05','06') THEN 'Q2' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('07','08','09') THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-2 years') "
      "GROUP BY ANIO, TRIMESTRE "
      "ORDER BY ANIO DESC, TRIMESTRE",
      "Dirección", "Dirección", "KPI", "Critico", "Comparativa", ""),

    q("dx3_080", "Análisis de Pareto de clientes (80/20)",
      "¿Cuántos clientes generan el 80% de las ventas?",
      "Número de clientes necesarios para alcanzar el 80% de ventas.",
      "SELECT "
      "COUNT(DISTINCT D.CODCLIENTE) AS TOTAL_CLIENTES, "
      "(SELECT COUNT(*) FROM ("
      "SELECT CODCLIENTE, SUM(L2.CANTIDAD*L2.PRECIO) AS V "
      "FROM DOCCAB D2 JOIN DOCLIN L2 ON L2.CODDOCUMENTO=D2.CODIGO "
      "WHERE D2.TIPO=13 GROUP BY CODCLIENTE "
      "ORDER BY V DESC LIMIT 10) T) AS CLIENTES_TOP10, "
      "ROUND((SELECT SUM(V) FROM ("
      "SELECT CODCLIENTE, SUM(L2.CANTIDAD*L2.PRECIO) AS V "
      "FROM DOCCAB D2 JOIN DOCLIN L2 ON L2.CODDOCUMENTO=D2.CODIGO "
      "WHERE D2.TIPO=13 GROUP BY CODCLIENTE "
      "ORDER BY V DESC LIMIT 10) T)*100.0/"
      "NULLIF(SUM(L.CANTIDAD*L.PRECIO),0),1) AS PCT_VENTAS_TOP10 "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Critico", "Pareto", ""),

    # ── ANÁLISIS ADICIONAL ─────────────────────────────────────────────────────

    q("dx3_081", "Ventas por NULL (tipo de documento origen)",
      "¿Qué NULL de venta genera más facturación?",
      "Facturas agrupadas por tipo de documento origen (pedido, albarán, directo).",
      "SELECT "
      "CASE WHEN NULL IS NULL THEN 'Directo' "
      "WHEN EXISTS(SELECT 1 FROM DOCCAB D2 WHERE D2.CODIGO=NULL AND D2.TIPO=1) THEN 'Pedido' "
      "WHEN EXISTS(SELECT 1 FROM DOCCAB D2 WHERE D2.CODIGO=NULL AND D2.TIPO=11) THEN 'Albarán' "
      "ELSE 'Otro' END AS NULL, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 "
      "GROUP BY NULL "
      "ORDER BY VENTAS DESC",
      "Dirección", "Dirección", "KPI", "Alto", "NULL", ""),

    q("dx3_082", "Clientes sin actividad en el año actual",
      "¿Qué clientes no han comprado en el año actual?",
      "Clientes con historial pero sin factura en el año en curso.",
      "SELECT C.CODIGO, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA "
      "FROM CLIENTE C "
      "JOIN DOCCAB D ON D.CODCLIENTE=C.CODIGO AND D.TIPO=13 "
      "WHERE C.CODIGO NOT IN ("
      "SELECT DISTINCT CODCLIENTE FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) "
      "GROUP BY C.CODIGO, CLIENTE "
      "ORDER BY ULTIMA_COMPRA DESC LIMIT 25",
      "Dirección", "Dirección", "Alerta", "Alto", "Inactivos", ""),

    q("dx3_083", "Artículos con mayor contribución al margen total",
      "¿Qué artículos contribuyen más al margen bruto total?",
      "Margen bruto por artículo ordenado por contribución total.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY MARGEN_BRUTO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Critico", "Margen", ""),

    q("dx3_084", "Familias con mayor contribución al margen total",
      "¿Qué familias contribuyen más al margen bruto?",
      "Margen bruto por familia de artículo.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO, "
      "ROUND((SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE))*100.0/"
      "NULLIF(SUM(L.CANTIDAD*L.PRECIO),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY F.NOMBRE "
      "ORDER BY MARGEN_BRUTO DESC LIMIT 15",
      "Dirección", "Dirección", "KPI", "Critico", "Margen", ""),

    q("dx3_085", "Clientes con mayor margen bruto generado",
      "¿Qué clientes generan más margen bruto?",
      "Margen bruto por cliente en facturas de venta.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY MARGEN_BRUTO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Critico", "Margen", ""),

    q("dx3_086", "Ventas acumuladas en el año vs objetivo (si existe)",
      "¿Cuánto se ha vendido en el año actual acumulado?",
      "Ventas acumuladas mes a mes en el año actual.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_MES, "
      "ROUND(SUM(SUM(L.CANTIDAD*L.PRECIO)) OVER "
      "(ORDER BY SUBSTR(D.FECHA,1,7)),2) AS VENTAS_ACUMULADAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES",
      "Dirección", "Dirección", "KPI", "Critico", "Acumulado", ""),

    q("dx3_087", "Clientes con mayor número de artículos distintos comprados",
      "¿Qué clientes tienen la cartera de compras más diversificada?",
      "Clientes con mayor número de artículos distintos en sus facturas.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_DISTINTOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_TOTALES "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_ARTICULOS_DISTINTOS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Diversificación", ""),

    q("dx3_088", "Ventas por tipo de cliente (nacional vs exportación)",
      "¿Qué porcentaje de las ventas es exportación?",
      "Ventas a clientes nacionales vs extranjeros.",
      "SELECT "
      "CASE WHEN C.CODPAIS IS NULL OR C.CODPAIS='ES' THEN 'Nacional' "
      "ELSE 'Exportación' END AS MERCADO, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY MERCADO "
      "ORDER BY VENTAS DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Mercados", ""),

    q("dx3_089", "Análisis de descuentos concedidos por mes",
      "¿Cuánto descuento se concede en ventas cada mes?",
      "Importe de descuentos aplicados en facturas de venta por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(CASE WHEN L.DESCUENTOS>0 THEN 1 END) AS N_LINEAS_CON_DESCUENTO, "
      "ROUND(SUM(CASE WHEN L.DESCUENTOS>0 "
      "THEN L.CANTIDAD*L.PRECIO*L.DESCUENTOS/100.0 ELSE 0 END),2) AS IMPORTE_DESCUENTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Descuentos", ""),

    q("dx3_090", "Impacto de descuentos en el margen bruto",
      "¿Cuánto margen se pierde por los descuentos concedidos?",
      "Diferencia entre ventas sin descuento y ventas con descuento aplicado.",
      "SELECT "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_CON_DESCUENTO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*(1+COALESCE(L.DESCUENTOS,0)/100.0)),2) AS VENTAS_SIN_DESCUENTO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*(1+COALESCE(L.DESCUENTOS,0)/100.0))-"
      "SUM(L.CANTIDAD*L.PRECIO),2) AS IMPACTO_DESCUENTOS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0",
      "Dirección", "Dirección", "KPI", "Alto", "Descuentos", ""),

    q("dx3_091", "Clientes con descuentos superiores al 20%",
      "¿Qué clientes reciben descuentos superiores al 20%?",
      "Clientes con descuento medio superior al 20% en sus facturas.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(AVG(L.DESCUENTOS),1) AS DESCUENTO_MEDIO, "
      "COUNT(*) AS N_LINEAS_CON_DESCUENTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING DESCUENTO_MEDIO>20 "
      "ORDER BY DESCUENTO_MEDIO DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Alto", "Descuentos", ""),

    q("dx3_092", "Evolución de clientes nuevos por mes",
      "¿Cuántos clientes nuevos se captan cada mes?",
      "Clientes con primera factura en cada mes.",
      "SELECT SUBSTR(PRIMERA.PRIMERA_FECHA,1,7) AS MES, "
      "COUNT(*) AS CLIENTES_NUEVOS "
      "FROM (SELECT D.CODCLIENTE, MIN(D.FECHA) AS PRIMERA_FECHA "
      "FROM DOCCAB D WHERE D.TIPO=13 GROUP BY D.CODCLIENTE) PRIMERA "
      "WHERE PRIMERA.PRIMERA_FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(PRIMERA.PRIMERA_FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Captación", ""),

    q("dx3_093", "Clientes perdidos (compraron hace >1 año y no han vuelto)",
      "¿Qué clientes se han perdido en el último año?",
      "Clientes con última compra hace más de 365 días.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "ROUND(JULIANDAY('now')-JULIANDAY(MAX(D.FECHA)),0) AS DIAS_INACTIVO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_HISTORICAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING MAX(D.FECHA) < DATE('now','-365 days') "
      "ORDER BY VENTAS_HISTORICAS DESC LIMIT 20",
      "Dirección", "Dirección", "Alerta", "Alto", "Churn", ""),

    q("dx3_094", "Ventas por agente/representante",
      "¿Cuánto vende cada agente o representante?",
      "Ventas agrupadas por código de agente en facturas TIPO=13.",
      "SELECT D.CODAGENTE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL "
      "GROUP BY D.CODAGENTE "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Agentes", ""),

    q("dx3_095", "Comisiones estimadas por agente",
      "¿Cuánto se estima en comisiones por agente?",
      "Ventas por agente como base para cálculo de comisiones.",
      "SELECT D.CODAGENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_BASE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)*0.05,2) AS COMISION_ESTIMADA_5PCT "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY D.CODAGENTE "
      "ORDER BY VENTAS_BASE DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Comisiones", ""),

    q("dx3_096", "Análisis de rentabilidad por agente",
      "¿Qué agentes generan más margen bruto?",
      "Margen bruto por agente en facturas de venta.",
      "SELECT D.CODAGENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS, "
      "ROUND(SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS COSTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)-SUM(L.CANTIDAD*A.PRECIOCOSTE),2) AS MARGEN_BRUTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.CODAGENTE IS NOT NULL AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODAGENTE "
      "ORDER BY MARGEN_BRUTO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Agentes", ""),

    q("dx3_097", "Clientes con mayor número de artículos distintos en el año",
      "¿Qué clientes compran más variedad de artículos en el año?",
      "Artículos distintos por cliente en el año actual.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Diversificación", ""),

    q("dx3_098", "Ventas por forma de pago",
      "¿Cómo se distribuyen las ventas por forma de pago?",
      "Ventas agrupadas por forma de pago en facturas TIPO=13.",
      "SELECT D.CODFORMAPAGO, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.CODFORMAPAGO IS NOT NULL "
      "GROUP BY D.CODFORMAPAGO "
      "ORDER BY VENTAS DESC LIMIT 15",
      "Dirección", "Dirección", "KPI", "Medio", "Formas de pago", ""),

    q("dx3_099", "Clientes con cambio de forma de pago",
      "¿Qué clientes han cambiado su forma de pago habitual?",
      "Clientes con más de una forma de pago distinta en sus facturas.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODFORMAPAGO) AS N_FORMAS_PAGO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.CODFORMAPAGO IS NOT NULL "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "HAVING N_FORMAS_PAGO>1 "
      "ORDER BY N_FORMAS_PAGO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Bajo", "Formas de pago", ""),

    q("dx3_100", "Resumen de riesgos operativos clave",
      "¿Cuáles son los principales riesgos operativos actuales?",
      "Indicadores de riesgo: STOCKARTICULO bajo mínimo, deuda alta, pedidos atrasados.",
      "SELECT "
      "(SELECT COUNT(*) FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.STOCKARTICULO<A.STOCKARTICULO) AS ARTICULOS_BAJO_MINIMO, "
      "(SELECT COUNT(DISTINCT D.CODCLIENTE) FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODCLIENTE HAVING SUM(L.CANTIDAD*L.PRECIO)>10000) AS CLIENTES_DEUDA_ALTA, "
      "(SELECT COUNT(*) FROM DOCCAB D "
      "WHERE D.TIPO=1 AND D.FECHA < DATE('now','-15 days') "
      "AND CODIGO NOT IN (SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=11)) AS PEDIDOS_ATRASADOS",
      "Dirección", "Dirección", "KPI", "Critico", "Riesgos", ""),

    q("dx3_101", "Ventas por tarifa de PRECIOVENTA aplicada",
      "¿Qué tarifa de PRECIOVENTA se aplica más en las ventas?",
      "Ventas agrupadas por código de tarifa en facturas TIPO=13.",
      "SELECT NULL, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND NULL IS NOT NULL "
      "GROUP BY 1 "
      "ORDER BY VENTAS DESC LIMIT 10",
      "Dirección", "Dirección", "KPI", "Medio", "Tarifas", ""),

    q("dx3_102", "Clientes con tarifa especial (diferente a la estándar)",
      "¿Qué clientes tienen tarifa especial de precios?",
      "Clientes con tarifa distinta a la tarifa estándar (CODTARIFA=1).",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "NULL, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND NULL IS NOT NULL AND 1=0 "
      "GROUP BY D.CODCLIENTE, CLIENTE, NULL "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Tarifas", ""),

    q("dx3_103", "Análisis de ventas por serie de factura",
      "¿Cómo se distribuyen las ventas por serie de facturación?",
      "Ventas agrupadas por serie de factura.",
      "SELECT D.SERIE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13 AND D.SERIE IS NOT NULL "
      "GROUP BY D.SERIE "
      "ORDER BY VENTAS DESC LIMIT 10",
      "Dirección", "Dirección", "KPI", "Bajo", "Series", ""),

    q("dx3_104", "Clientes con mayor antigüedad (primera compra más antigua)",
      "¿Cuáles son los clientes más antiguos de la empresa?",
      "Clientes ordenados por fecha de primera factura.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "MIN(D.FECHA) AS PRIMERA_COMPRA, "
      "MAX(D.FECHA) AS ULTIMA_COMPRA, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS_HISTORICAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY PRIMERA_COMPRA ASC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Antigüedad", ""),

    q("dx3_105", "Análisis de ventas por código postal",
      "¿Cómo se distribuyen las ventas por código postal?",
      "Ventas agrupadas por código postal del cliente.",
      "SELECT COALESCE(C.CP, 'Sin CP') AS CODIGO_POSTAL, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY COALESCE(C.CP, 'Sin CP') "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Medio", "Geografía", ""),

    q("dx3_106", "Clientes con mayor número de presupuestos sin convertir",
      "¿Qué clientes tienen más presupuestos sin aceptar?",
      "Clientes con mayor número de presupuestos (TIPO=2) sin pedido asociado.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_PRESUPUESTOS_PENDIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VALOR_POTENCIAL "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=2 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=1) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY VALOR_POTENCIAL DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Pipeline", ""),

    q("dx3_107", "Análisis de ventas por tipo de IMPORTEIVA aplicado",
      "¿Cómo se distribuyen las ventas por tipo de IMPORTEIVA?",
      "Ventas agrupadas por tipo de IMPORTEIVA en líneas de factura.",
      "SELECT L.TIPOIVA, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,0)/100.0),2) AS CUOTA_IMPORTEIVA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 "
      "GROUP BY L.TIPOIVA "
      "ORDER BY BASE_IMPONIBLE DESC",
      "Dirección", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("dx3_108", "Resumen de IMPORTEIVA repercutido por mes",
      "¿Cuánto IMPORTEIVA se repercute cada mes en las ventas?",
      "Base imponible e IMPORTEIVA repercutido por mes en facturas de venta.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS IVA_REPERCUTIDO, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)+"
      "SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS TOTAL_FACTURADO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Critico", "IMPORTEIVA", ""),

    q("dx3_109", "Resumen de IMPORTEIVA soportado por mes (compras)",
      "¿Cuánto IMPORTEIVA se soporta cada mes en las compras?",
      "Base imponible e IMPORTEIVA soportado por mes en facturas de compra.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS IVA_SOPORTADO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=20 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Critico", "IMPORTEIVA", ""),

    q("dx3_110", "Liquidación estimada de IMPORTEIVA por trimestre",
      "¿Cuál es la liquidación estimada de IMPORTEIVA por trimestre?",
      "IMPORTEIVA repercutido menos IMPORTEIVA soportado por trimestre.",
      "SELECT "
      "SUBSTR(D.FECHA,1,4) AS ANIO, "
      "CASE WHEN SUBSTR(D.FECHA,6,2) IN ('01','02','03') THEN 'Q1' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('04','05','06') THEN 'Q2' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('07','08','09') THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END),2) AS IVA_REPERCUTIDO, "
      "ROUND(SUM(CASE WHEN D.TIPO=20 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END),2) AS IVA_SOPORTADO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO IN (13,20) "
      "GROUP BY ANIO, TRIMESTRE "
      "ORDER BY ANIO DESC, TRIMESTRE",
      "Dirección", "Dirección", "KPI", "Critico", "IMPORTEIVA", ""),

    q("dx3_111", "Clientes con mayor volumen de IMPORTEIVA repercutido",
      "¿Qué clientes generan más IMPORTEIVA repercutido?",
      "IMPORTEIVA repercutido por cliente en facturas de venta.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS IVA_REPERCUTIDO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY IVA_REPERCUTIDO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("dx3_112", "Proveedores con mayor IMPORTEIVA soportado",
      "¿Qué proveedores generan más IMPORTEIVA soportado?",
      "IMPORTEIVA soportado por proveedor en facturas de compra.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL), CAST(D.CODCLIENTE AS TEXT)) AS PROVEEDOR, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS IVA_SOPORTADO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN PROVEED P ON P.CODIGO=D.CODCLIENTE "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=20 "
      "GROUP BY D.CODCLIENTE, PROVEEDOR "
      "ORDER BY IVA_SOPORTADO DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("dx3_113", "Facturas con IMPORTEIVA exento o tipo reducido",
      "¿Qué facturas tienen IMPORTEIVA exento o tipo reducido?",
      "Facturas con tipo de IMPORTEIVA distinto al general (21%).",
      "SELECT D.CODIGO AS COD_FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "L.TIPOIVA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 AND (I.PORCENTAJE IS NULL OR I.PORCENTAJE<21) "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE, L.TIPOIVA "
      "ORDER BY D.FECHA DESC LIMIT 25",
      "Dirección", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("dx3_114", "Análisis de ventas con y sin IMPORTEIVA por mes",
      "¿Cuánto representan las ventas con IMPORTEIVA incluido cada mes?",
      "Base imponible, IMPORTEIVA y total con IMPORTEIVA por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS IVA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)+"
      "SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS TOTAL_CON_IMPORTEIVA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Critico", "IMPORTEIVA", ""),

    q("dx3_115", "Resumen fiscal anual (ventas, compras, IMPORTEIVA neto)",
      "¿Cuál es el resumen fiscal del año en curso?",
      "Ventas, compras, IMPORTEIVA repercutido, IMPORTEIVA soportado e IMPORTEIVA neto del año.",
      "SELECT "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_BASE, "
      "ROUND(SUM(CASE WHEN D.TIPO=20 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS COMPRAS_BASE, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END),2) AS IVA_REPERCUTIDO, "
      "ROUND(SUM(CASE WHEN D.TIPO=20 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END),2) AS IVA_SOPORTADO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO IN (13,20) "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)",
      "Dirección", "Dirección", "KPI", "Critico", "Fiscal", ""),

    q("dx3_116", "Clientes exentos de IMPORTEIVA",
      "¿Qué clientes tienen facturas con IMPORTEIVA exento?",
      "Clientes con facturas donde el IMPORTEIVA es 0% o exento.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_EXENTA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 AND (I.PORCENTAJE=0 OR I.PORCENTAJE IS NULL) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY BASE_EXENTA DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("dx3_117", "Evolución del IMPORTEIVA neto a pagar por trimestre",
      "¿Cuánto IMPORTEIVA neto hay que pagar cada trimestre?",
      "IMPORTEIVA repercutido menos IMPORTEIVA soportado por trimestre.",
      "SELECT "
      "SUBSTR(D.FECHA,1,4) AS ANIO, "
      "CASE WHEN SUBSTR(D.FECHA,6,2) IN ('01','02','03') THEN 'Q1' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('04','05','06') THEN 'Q2' "
      "WHEN SUBSTR(D.FECHA,6,2) IN ('07','08','09') THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END) - "
      "SUM(CASE WHEN D.TIPO=20 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END),2) AS IVA_NETO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO IN (13,20) "
      "GROUP BY ANIO, TRIMESTRE "
      "ORDER BY ANIO DESC, TRIMESTRE",
      "Dirección", "Dirección", "KPI", "Critico", "IMPORTEIVA", ""),

    q("dx3_118", "Facturas rectificativas emitidas por mes",
      "¿Cuántas facturas rectificativas se emiten cada mes?",
      "Abonos y rectificativas (TIPO=14) agrupados por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_RECTIFICATIVAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_RECTIFICADO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=14 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Alto", "Rectificativas", ""),

    q("dx3_119", "Análisis de ventas por tipo de documento (factura vs albarán)",
      "¿Qué proporción de ventas se factura directamente vs por albarán?",
      "Facturas con y sin albarán previo.",
      "SELECT "
      "COUNT(DISTINCT CASE WHEN NULL IS NOT NULL THEN D.CODIGO END) AS FACTURAS_CON_ALBARAN, "
      "COUNT(DISTINCT CASE WHEN NULL IS NULL THEN D.CODIGO END) AS FACTURAS_DIRECTAS, "
      "ROUND(SUM(CASE WHEN NULL IS NOT NULL THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_CON_ALBARAN, "
      "ROUND(SUM(CASE WHEN NULL IS NULL THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VENTAS_DIRECTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=13",
      "Dirección", "Dirección", "KPI", "Medio", "Proceso", ""),

    q("dx3_120", "Clientes con mayor importe de IMPORTEIVA en facturas pendientes",
      "¿Qué clientes tienen más IMPORTEIVA pendiente de cobro?",
      "IMPORTEIVA en facturas pendientes de cobro por cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_PENDIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS IVA_PENDIENTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY IVA_PENDIENTE DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Critico", "IMPORTEIVA", ""),

    q("dx3_121", "Análisis de ventas intracomunitarias",
      "¿Cuánto se vende a clientes de la UE (intracomunitario)?",
      "Ventas a clientes con país de la UE distinto a España.",
      "SELECT COALESCE(C.CODPAIS, 'Sin país') AS CODPAIS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VENTAS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND C.CODPAIS IS NOT NULL AND C.CODPAIS<>'ES' "
      "GROUP BY COALESCE(C.CODPAIS, 'Sin país') "
      "ORDER BY VENTAS DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "Intracomunitario", ""),

    q("dx3_122", "Facturas con base imponible y desglose de IMPORTEIVA",
      "¿Cuál es el desglose de base imponible e IMPORTEIVA de las últimas facturas?",
      "Últimas 20 facturas con base imponible, IMPORTEIVA y total.",
      "SELECT D.CODIGO AS COD_FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS CUOTA_IVA, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO)+"
      "SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) AS TOTAL_FACTURA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("dx3_123", "Comparativa IMPORTEIVA repercutido vs soportado por mes",
      "¿Cómo se compara el IMPORTEIVA repercutido con el soportado cada mes?",
      "IMPORTEIVA repercutido (ventas) vs IMPORTEIVA soportado (compras) por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END),2) AS IVA_REPERCUTIDO, "
      "ROUND(SUM(CASE WHEN D.TIPO=20 "
      "THEN L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0 ELSE 0 END),2) AS IVA_SOPORTADO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO IN (13,20) AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Dirección", "Dirección", "KPI", "Critico", "IMPORTEIVA", ""),

    q("dx3_124", "Artículos con tipo de IMPORTEIVA reducido en ventas",
      "¿Qué artículos se venden con IMPORTEIVA reducido?",
      "Artículos con tipo de IMPORTEIVA inferior al 21% en facturas de venta.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "L.TIPOIVA, "
      "COALESCE(I.PORCENTAJE,0) AS PCT_IVA, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS BASE_IMPONIBLE "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 AND COALESCE(I.PORCENTAJE,21)<21 "
      "GROUP BY L.CODARTICULO, A.NOMBRE, L.TIPOIVA, I.PORCENTAJE "
      "ORDER BY BASE_IMPONIBLE DESC LIMIT 20",
      "Dirección", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("dx3_125", "Resumen de indicadores fiscales clave",
      "¿Cuáles son los indicadores fiscales clave de la empresa?",
      "Resumen de ventas, compras, IMPORTEIVA repercutido, soportado y neto del año.",
      "SELECT "
      "CAST(STRFTIME('%Y','now') AS TEXT) AS EJERCICIO, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS VENTAS_BASE, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=20 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS COMPRAS_BASE, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS IVA_REPERCUTIDO, "
      "(SELECT ROUND(SUM(L.CANTIDAD*L.PRECIO*COALESCE(I.PORCENTAJE,21)/100.0),2) "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA "
      "WHERE D.TIPO=20 AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT)) AS IVA_SOPORTADO",
      "Dirección", "Dirección", "KPI", "Critico", "Fiscal", ""),

]
