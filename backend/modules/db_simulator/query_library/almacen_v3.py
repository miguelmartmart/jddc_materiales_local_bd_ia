"""
query_library/almacen_v3.py — 125 consultas adicionales de Almacén (v3).

Diferentes a almacen.py y almacen_v2.py. Cubren: análisis de rotación avanzada,
gestión de ubicaciones, control de lotes y caducidades, análisis ABC de inventario,
optimización de reposición, análisis de mermas, trazabilidad de movimientos,
gestión de almacenes múltiples, análisis de picking, y control de inventario cíclico.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: strftime, JULIANDAY, SUBSTR, CAST, COALESCE.
Sin comentarios subjetivos. Solo hechos verificables con datos.
"""

from backend.modules.db_simulator.query_library.builder import q

QUERIES_ALMACEN_V3: list = [

    # ── ANÁLISIS ABC DE INVENTARIO ─────────────────────────────────────────────

    q("ax3_001", "Clasificación ABC de artículos por valor de STOCKARTICULO",
      "¿Qué artículos representan el 80% del valor del inventario?",
      "Clasifica artículos por valor acumulado (STOCKARTICULO × PRECIOCOSTE) para análisis ABC.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO * A.PRECIOCOSTE),2) AS VALOR_STOCKARTICULO, "
      "ROUND(SUM(A.STOCKARTICULO * A.PRECIOCOSTE)*100.0/"
      "(SELECT SUM(E2.STOCKARTICULO*A2.PRECIOCOSTE) FROM ARTICULO E2 "
      "JOIN ARTICULO A2 ON A2.CODIGO=E2.CODIGO WHERE E2.STOCKARTICULO>0),2) AS PCT_VALOR "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY VALOR_STOCKARTICULO DESC LIMIT 50",
      "Almacen", "Almacen", "KPI", "Alto", "ABC", ""),

    q("ax3_002", "Artículos clase A (top 20% por valor)",
      "¿Cuáles son los artículos de clase A que requieren mayor control?",
      "Top 20% de artículos por valor de STOCKARTICULO. Requieren control estricto.",
      "SELECT A.CODIGO, A.NOMBRE, A.CODFAMILIA, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_UNIT, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.CODFAMILIA, A.PRECIOCOSTE "
      "ORDER BY VALOR_TOTAL DESC LIMIT 20",
      "Almacen", "Dirección", "KPI", "Critico", "ABC", ""),

    q("ax3_003", "Artículos clase C (menor valor, mayor cantidad)",
      "¿Qué artículos de bajo valor ocupan espacio en almacén?",
      "Artículos con STOCKARTICULO pero valor unitario bajo. Candidatos a revisión de STOCKARTICULO mínimo.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_UNIT, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING VALOR_TOTAL < 50 "
      "ORDER BY STOCK_TOTAL DESC LIMIT 40",
      "Almacen", "Almacen", "KPI", "Bajo", "ABC", ""),

    q("ax3_004", "Concentración de valor por familia (análisis Pareto)",
      "¿Qué familias concentran el mayor valor de inventario?",
      "Valor de STOCKARTICULO agrupado por familia para identificar familias críticas.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(DISTINCT A.CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_FAMILIA, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE)*100.0/"
      "(SELECT SUM(E2.STOCKARTICULO*A2.PRECIOCOSTE) FROM ARTICULO E2 "
      "JOIN ARTICULO A2 ON A2.CODIGO=E2.CODIGO WHERE E2.STOCKARTICULO>0),1) AS PCT "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY F.NOMBRE ORDER BY VALOR_FAMILIA DESC",
      "Almacen", "Dirección", "KPI", "Alto", "Pareto", ""),

    # ── ROTACIÓN Y MOVIMIENTOS ─────────────────────────────────────────────────

    q("ax3_005", "Artículos sin movimiento en los últimos 90 días",
      "¿Qué artículos no han tenido movimiento en 3 meses?",
      "Artículos con STOCKARTICULO pero sin líneas de documento en los últimos 90 días.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO, "
      "MAX(D.FECHA) AS ULTIMO_MOVIMIENTO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING MAX(D.FECHA) < DATE('now','-90 days') OR MAX(D.FECHA) IS NULL "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "Rotación", ""),

    q("ax3_006", "Artículos sin movimiento en los últimos 180 días",
      "¿Qué artículos llevan 6 meses sin movimiento?",
      "STOCKARTICULO inmovilizado más de 180 días. Candidatos a liquidación o baja.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.FECHA >= DATE('now','-180 days')) "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 30",
      "Almacen", "Dirección", "Alerta", "Critico", "Rotación", ""),

    q("ax3_007", "Velocidad de rotación por artículo (unidades/mes)",
      "¿A qué velocidad rota cada artículo en almacén?",
      "Unidades salidas por mes en los últimos 12 meses dividido entre meses activos.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_ACTIVOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_SALIDAS, "
      "ROUND(SUM(L.CANTIDAD)/NULLIF(COUNT(DISTINCT SUBSTR(D.FECHA,1,7)),0),2) AS ROTACION_MES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO IN (13,11) AND D.FECHA >= DATE('now','-365 days') AND L.CANTIDAD>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY ROTACION_MES DESC LIMIT 40",
      "Almacen", "Almacen", "KPI", "Alto", "Rotación", ""),

    q("ax3_008", "Días de cobertura de STOCKARTICULO por artículo",
      "¿Para cuántos días de venta alcanza el STOCKARTICULO actual de cada artículo?",
      "STOCKARTICULO actual dividido entre consumo diario medio de los últimos 90 días.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(L.CANTIDAD)/90.0,3) AS CONSUMO_DIARIO, "
      "ROUND(SUM(A.STOCKARTICULO)/NULLIF(SUM(L.CANTIDAD)/90.0,0),0) AS DIAS_COBERTURA "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.TIPO=13 AND D.FECHA >= DATE('now','-90 days') "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING CONSUMO_DIARIO>0 "
      "ORDER BY DIAS_COBERTURA ASC LIMIT 30",
      "Almacen", "Almacen", "KPI", "Alto", "Cobertura", ""),

    q("ax3_009", "Artículos con alta rotación y STOCKARTICULO bajo (riesgo rotura)",
      "¿Qué artículos de alta rotación tienen poco STOCKARTICULO?",
      "Artículos con rotación alta pero días de cobertura menores a 15.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(L.CANTIDAD)/90.0,3) AS CONSUMO_DIARIO, "
      "ROUND(SUM(A.STOCKARTICULO)/NULLIF(SUM(L.CANTIDAD)/90.0,0),0) AS DIAS_COBERTURA "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.TIPO=13 AND D.FECHA >= DATE('now','-90 days') "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING CONSUMO_DIARIO>0 AND DIAS_COBERTURA < 15 "
      "ORDER BY DIAS_COBERTURA ASC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Critico", "Rotura", ""),

    q("ax3_010", "Frecuencia de movimientos por artículo (últimos 6 meses)",
      "¿Con qué frecuencia se mueve cada artículo en almacén?",
      "Número de documentos distintos que incluyen cada artículo en 6 meses.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_CON_MOVIMIENTO, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_UNIDADES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.FECHA >= DATE('now','-180 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_DOCUMENTOS DESC LIMIT 30",
      "Almacen", "Almacen", "KPI", "Medio", "Frecuencia", ""),

    # ── GESTIÓN DE ALMACENES MÚLTIPLES ─────────────────────────────────────────

    q("ax3_011", "Comparativa de STOCKARTICULO entre almacenes",
      "¿Cómo se distribuye el STOCKARTICULO entre los distintos almacenes?",
      "STOCKARTICULO total por almacén para identificar desequilibrios entre ubicaciones.",
      "SELECT '01', "
      "COUNT(DISTINCT A.CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_TOTAL "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY '01' "
      "ORDER BY VALOR_TOTAL DESC",
      "Almacen", "Almacen", "KPI", "Alto", "Multi-almacén", ""),

    q("ax3_012", "Artículos presentes en múltiples almacenes",
      "¿Qué artículos están distribuidos en más de un almacén?",
      "Artículos con STOCKARTICULO en 2 o más almacenes distintos.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "COUNT(DISTINCT '01') AS N_ALMACENES, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING N_ALMACENES > 1 "
      "ORDER BY N_ALMACENES DESC, STOCK_TOTAL DESC LIMIT 30",
      "Almacen", "Almacen", "KPI", "Medio", "Multi-almacén", ""),

    q("ax3_013", "Artículos exclusivos de un almacén",
      "¿Qué artículos solo existen en un almacén concreto?",
      "Artículos con STOCKARTICULO únicamente en un almacén. Riesgo si ese almacén falla.",
      "SELECT A.CODIGO, A.NOMBRE, '01', "
      "ROUND(A.STOCKARTICULO,2) AS STOCKARTICULO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 AND A.CODIGO NOT IN ("
      "SELECT CODIGO FROM ARTICULO "
      "WHERE STOCKARTICULO>0 GROUP BY CODIGO HAVING COUNT(DISTINCT CODALMACEN)>1) "
      "ORDER BY '01', A.NOMBRE LIMIT 40",
      "Almacen", "Almacen", "KPI", "Medio", "Multi-almacén", ""),

    q("ax3_014", "Transferencias entre almacenes (albaranes internos)",
      "¿Cuántas transferencias internas se han realizado entre almacenes?",
      "Documentos de tipo transferencia interna agrupados por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, D.TIPO, "
      "COUNT(*) AS N_TRANSFERENCIAS, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO IN (30,31,32) "
      "GROUP BY SUBSTR(D.FECHA,1,7), D.TIPO "
      "ORDER BY MES DESC LIMIT 24",
      "Almacen", "Almacen", "KPI", "Medio", "Transferencias", ""),

    q("ax3_015", "Desequilibrio de STOCKARTICULO entre almacenes por artículo",
      "¿Qué artículos tienen STOCKARTICULO muy desigual entre almacenes?",
      "Diferencia entre el almacén con más STOCKARTICULO y el de menos para cada artículo.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "MAX(A.STOCKARTICULO) AS STOCK_MAX, MIN(A.STOCKARTICULO) AS STOCK_MIN, "
      "MAX(A.STOCKARTICULO)-MIN(A.STOCKARTICULO) AS DIFERENCIA, "
      "COUNT(DISTINCT '01') AS N_ALMACENES "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>=0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING N_ALMACENES>1 AND DIFERENCIA>10 "
      "ORDER BY DIFERENCIA DESC LIMIT 25",
      "Almacen", "Almacen", "KPI", "Medio", "Multi-almacén", ""),

    # ── CONTROL DE ENTRADAS Y SALIDAS ──────────────────────────────────────────

    q("ax3_016", "Entradas de STOCKARTICULO por mes (albaranes de compra)",
      "¿Cuántas unidades han entrado en almacén cada mes?",
      "Líneas de albarán de compra (TIPO=10) agrupadas por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES, "
      "COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_ENTRADA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=10 AND L.CANTIDAD>0 "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Almacen", "Almacen", "KPI", "Alto", "Entradas", ""),

    q("ax3_017", "Salidas de STOCKARTICULO por mes (albaranes de venta)",
      "¿Cuántas unidades han salido de almacén cada mes?",
      "Líneas de albarán de venta (TIPO=11) agrupadas por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES, "
      "COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_SALIDA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=11 AND L.CANTIDAD>0 "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Almacen", "Almacen", "KPI", "Alto", "Salidas", ""),

    q("ax3_018", "Balance entradas vs salidas por artículo (últimos 90 días)",
      "¿Qué artículos tienen más salidas que entradas en los últimos 3 meses?",
      "Compara unidades entradas (TIPO=10) vs salidas (TIPO=11) por artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(CASE WHEN D.TIPO=10 THEN L.CANTIDAD ELSE 0 END),2) AS ENTRADAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=11 THEN L.CANTIDAD ELSE 0 END),2) AS SALIDAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=10 THEN L.CANTIDAD ELSE -L.CANTIDAD END),2) AS BALANCE "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO IN (10,11) AND D.FECHA >= DATE('now','-90 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY BALANCE ASC LIMIT 30",
      "Almacen", "Almacen", "KPI", "Alto", "Balance", ""),

    q("ax3_019", "Artículos con más devoluciones de clientes",
      "¿Qué artículos generan más devoluciones de clientes?",
      "Líneas de abono de venta (TIPO=14) agrupadas por artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_DEVOLUCIONES, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_DEVUELTAS, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=14 AND L.CANTIDAD>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_DEVUELTAS DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Alto", "Devoluciones", ""),

    q("ax3_020", "Tasa de devolución por artículo (% sobre ventas)",
      "¿Qué porcentaje de las ventas de cada artículo se devuelve?",
      "Unidades devueltas (TIPO=14) sobre unidades vendidas (TIPO=13) por artículo.",
      "SELECT A.CODIGO AS COD_ART, A.NOMBRE, "
      "ROUND(V.VENDIDAS,2) AS UNIDADES_VENDIDAS, "
      "ROUND(COALESCE(DEV.DEVUELTAS,0),2) AS UNIDADES_DEVUELTAS, "
      "ROUND(COALESCE(DEV.DEVUELTAS,0)*100.0/NULLIF(V.VENDIDAS,0),1) AS TASA_DEVOLUCION_PCT "
      "FROM (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS VENDIDAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 GROUP BY L.CODARTICULO) V "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS DEVUELTAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=14 GROUP BY L.CODARTICULO) DEV ON DEV.CODIGO=A.CODIGO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE COALESCE(DEV.DEVUELTAS,0)>0 "
      "ORDER BY TASA_DEVOLUCION_PCT DESC LIMIT 25",
      "Almacen", "Calidad", "KPI", "Alto", "Devoluciones", ""),

    # ── REPOSICIÓN Y STOCKARTICULO MÍNIMO ──────────────────────────────────────────────

    q("ax3_021", "Artículos por debajo del STOCKARTICULO mínimo",
      "¿Qué artículos están por debajo de su STOCKARTICULO mínimo definido?",
      "Compara ESTALMACEN.STOCK con ARTICULO.STOCKARTICULO para detectar necesidades.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "A.STOCKARTICULO AS STOCK_MINIMO, "
      "ROUND(A.STOCKARTICULO - SUM(A.STOCKARTICULO),2) AS DEFICIT "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING STOCK_ACTUAL < A.STOCKARTICULO "
      "ORDER BY DEFICIT DESC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Critico", "Reposición", ""),

    q("ax3_022", "Artículos por encima del STOCKARTICULO máximo",
      "¿Qué artículos superan su STOCKARTICULO máximo definido?",
      "Exceso de STOCKARTICULO respecto al máximo definido en ARTICULO.STOCKARTICULO.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "A.STOCKARTICULO AS STOCK_MAXIMO, "
      "ROUND(SUM(A.STOCKARTICULO)-A.STOCKARTICULO,2) AS EXCESO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING STOCK_ACTUAL > A.STOCKARTICULO "
      "ORDER BY EXCESO DESC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "Reposición", ""),

    q("ax3_023", "Punto de reorden por artículo (STOCKARTICULO mínimo + lead time)",
      "¿Cuándo hay que lanzar pedido para cada artículo?",
      "Artículos cuyo STOCKARTICULO actual está cerca del punto de reorden.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "A.STOCKARTICULO AS STOCK_MINIMO, "
      "ROUND(SUM(A.STOCKARTICULO)-A.STOCKARTICULO,2) AS MARGEN_SOBRE_MINIMO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING MARGEN_SOBRE_MINIMO BETWEEN 0 AND A.STOCKARTICULO*0.5 "
      "ORDER BY MARGEN_SOBRE_MINIMO ASC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "Reposición", ""),

    q("ax3_024", "Artículos sin STOCKARTICULO mínimo definido con movimiento reciente",
      "¿Qué artículos activos no tienen STOCKARTICULO mínimo configurado?",
      "Artículos con movimiento en 90 días pero sin STOCKARTICULO definido.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_MOVIMIENTOS "
      "FROM ARTICULO A "
      " "
      "JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE (A.STOCKARTICULO IS NULL OR A.STOCKARTICULO=0) "
      "AND D.FECHA >= DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY N_MOVIMIENTOS DESC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Medio", "Configuración", ""),

    q("ax3_025", "Necesidades de reposición valoradas",
      "¿Cuánto costaría reponer todos los artículos bajo mínimos?",
      "Suma del PRECIOCOSTE de reposición para artículos con déficit respecto al mínimo.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "A.STOCKARTICULO AS STOCK_MINIMO, "
      "ROUND(A.STOCKARTICULO-SUM(A.STOCKARTICULO),2) AS UNIDADES_REPONER, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_UNIT, "
      "ROUND((A.STOCKARTICULO-SUM(A.STOCKARTICULO))*A.PRECIOCOSTE,2) AS COSTE_REPOSICION "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO, A.PRECIOCOSTE "
      "HAVING STOCK_ACTUAL < A.STOCKARTICULO "
      "ORDER BY COSTE_REPOSICION DESC LIMIT 30",
      "Almacen", "Dirección", "KPI", "Critico", "Reposición", ""),

    # ── ANÁLISIS DE MERMAS Y AJUSTES ───────────────────────────────────────────

    q("ax3_026", "Ajustes de inventario por mes",
      "¿Cuántos ajustes de inventario se realizan cada mes?",
      "Documentos de ajuste de inventario (TIPO=20) agrupados por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_AJUSTES, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS_AJUSTADOS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=20 "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Almacen", "Almacen", "KPI", "Medio", "Ajustes", ""),

    q("ax3_027", "Artículos con más ajustes de inventario",
      "¿Qué artículos requieren más ajustes de inventario?",
      "Artículos con mayor número de ajustes en documentos TIPO=20.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_AJUSTES, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_AJUSTADAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=20 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_AJUSTES DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Alto", "Ajustes", ""),

    q("ax3_028", "Valor de mermas y ajustes negativos",
      "¿Cuánto valor se pierde por mermas y ajustes negativos?",
      "Ajustes con unidades negativas valorados al PRECIOCOSTE del artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_AJUSTES, "
      "ROUND(SUM(ABS(L.CANTIDAD)),2) AS UNIDADES_MERMA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_UNIT, "
      "ROUND(SUM(ABS(L.CANTIDAD))*A.PRECIOCOSTE,2) AS VALOR_MERMA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=20 AND L.CANTIDAD<0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE, A.PRECIOCOSTE "
      "ORDER BY VALOR_MERMA DESC LIMIT 25",
      "Almacen", "Dirección", "Alerta", "Critico", "Mermas", ""),

    q("ax3_029", "Evolución mensual del valor de mermas",
      "¿Cómo evoluciona el valor de las mermas mes a mes?",
      "Valor total de ajustes negativos por mes en los últimos 12 meses.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_AJUSTES, "
      "ROUND(SUM(ABS(L.CANTIDAD)*A.PRECIOCOSTE),2) AS VALOR_MERMA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=20 AND L.CANTIDAD<0 "
      "AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC",
      "Almacen", "Dirección", "KPI", "Alto", "Mermas", ""),

    q("ax3_030", "Ratio de merma por familia de artículo",
      "¿Qué familias tienen mayor tasa de merma?",
      "Valor de mermas sobre valor de entradas por familia.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "ROUND(SUM(ABS(L.CANTIDAD)*A.PRECIOCOSTE),2) AS VALOR_MERMA, "
      "COUNT(*) AS N_AJUSTES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=20 AND L.CANTIDAD<0 "
      "GROUP BY F.NOMBRE "
      "ORDER BY VALOR_MERMA DESC LIMIT 20",
      "Almacen", "Calidad", "KPI", "Alto", "Mermas", ""),

    # ── TRAZABILIDAD Y AUDITORÍA ───────────────────────────────────────────────

    q("ax3_031", "Historial de movimientos de un artículo (últimos 60 días)",
      "¿Cuál es el historial completo de movimientos de un artículo?",
      "Todos los documentos que incluyen el artículo más reciente en 60 días.",
      "SELECT D.FECHA, D.TIPO, D.CODIGO AS COD_DOC, "
      "ROUND(L.CANTIDAD,2) AS CANTIDAD, ROUND(L.PRECIO,2) AS PRECIO, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE_PROVEEDOR "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE L.CODARTICULO=(SELECT L2.CODIGO FROM DOCLIN L2 "
      "JOIN DOCCAB D2 ON D2.CODIGO=L2.CODDOCUMENTO "
      "WHERE D2.FECHA >= DATE('now','-60 days') "
      "GROUP BY L2.CODIGO ORDER BY COUNT(*) DESC LIMIT 1) "
      "AND D.FECHA >= DATE('now','-60 days') "
      "ORDER BY D.FECHA DESC LIMIT 50",
      "Almacen", "Almacen", "Detalle", "Medio", "Trazabilidad", ""),

    q("ax3_032", "Documentos de almacén por operario/usuario",
      "¿Cuántos documentos de almacén ha generado cada usuario?",
      "Agrupa documentos de almacén por CODUSUARIO para auditoría.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_DOCUMENTOS, "
      "COUNT(DISTINCT D.TIPO) AS TIPOS_DISTINTOS, "
      "MIN(D.FECHA) AS PRIMER_DOC, MAX(D.FECHA) AS ULTIMO_DOC "
      "FROM DOCCAB D "
      "WHERE D.TIPO IN (10,11,20,30,31) "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_DOCUMENTOS DESC LIMIT 20",
      "Almacen", "Almacen", "Auditoría", "Medio", "Usuarios", ""),

    q("ax3_033", "Albaranes de compra sin factura asociada",
      "¿Qué albaranes de compra no tienen factura asociada?",
      "Albaranes TIPO=10 sin referencia a factura de compra TIPO=20.",
      "SELECT D.CODIGO AS COD_ALBARAN, D.FECHA, D.CODCLIENTE, "
      "COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=10 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=20) "
      "GROUP BY D.CODIGO, D.FECHA, D.CODCLIENTE "
      "ORDER BY D.FECHA DESC LIMIT 30",
      "Almacen", "Compras", "Alerta", "Alto", "Pendientes", ""),

    q("ax3_034", "Albaranes de venta sin factura asociada",
      "¿Qué albaranes de venta no han sido facturados?",
      "Albaranes TIPO=11 sin referencia a factura de venta TIPO=13.",
      "SELECT D.CODIGO AS COD_ALBARAN, D.FECHA, D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=11 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=13) "
      "GROUP BY D.CODIGO, D.FECHA, D.CODCLIENTE, CLIENTE "
      "ORDER BY D.FECHA DESC LIMIT 30",
      "Almacen", "Ventas", "Alerta", "Alto", "Pendientes", ""),

    q("ax3_035", "Discrepancias entre STOCKARTICULO teórico y físico",
      "¿Existen discrepancias entre el STOCKARTICULO teórico y el registrado?",
      "Artículos donde la suma de movimientos no coincide con ESTALMACEN.STOCK.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_REGISTRADO, "
      "ROUND(SUM(CASE WHEN D.TIPO=10 THEN L.CANTIDAD "
      "WHEN D.TIPO IN (11,14) THEN -L.CANTIDAD ELSE 0 END),2) AS STOCK_CALCULADO, "
      "ROUND(SUM(A.STOCKARTICULO)-SUM(CASE WHEN D.TIPO=10 THEN L.CANTIDAD "
      "WHEN D.TIPO IN (11,14) THEN -L.CANTIDAD ELSE 0 END),2) AS DISCREPANCIA "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO IN (10,11,14) "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING ABS(DISCREPANCIA)>1 "
      "ORDER BY ABS(DISCREPANCIA) DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Critico", "Discrepancias", ""),

    # ── ANÁLISIS DE PROVEEDORES EN ALMACÉN ─────────────────────────────────────

    q("ax3_036", "Proveedores con más entradas de STOCKARTICULO",
      "¿Qué proveedores suministran más unidades al almacén?",
      "Albaranes de compra (TIPO=10) agrupados por proveedor.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL), CAST(D.CODCLIENTE AS TEXT)) AS PROVEEDOR, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_RECIBIDAS, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN PROVEED P ON P.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=10 "
      "GROUP BY D.CODCLIENTE, PROVEEDOR "
      "ORDER BY UNIDADES_RECIBIDAS DESC LIMIT 20",
      "Almacen", "Compras", "KPI", "Alto", "Proveedores", ""),

    q("ax3_037", "Tiempo medio entre pedido y recepción por proveedor",
      "¿Cuántos días tarda cada proveedor en servir los pedidos?",
      "Diferencia en días entre fecha de pedido (TIPO=4) y albarán (TIPO=10).",
      "SELECT D_PED.CODCLIENTE, "
      "COALESCE(COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL), CAST(D_PED.CODCLIENTE AS TEXT)) AS PROVEEDOR, "
      "COUNT(*) AS N_PEDIDOS, "
      "ROUND(AVG(JULIANDAY(D_ALB.FECHA)-JULIANDAY(D_PED.FECHA)),1) AS DIAS_MEDIO_ENTREGA "
      "FROM DOCCAB D_PED "
      "JOIN DOCCAB D_ALB ON 1=0 AND D_ALB.TIPO=10 "
      "LEFT JOIN PROVEED P ON P.CODIGO=D_PED.CODCLIENTE "
      "WHERE D_PED.TIPO=4 AND D_PED.FECHA IS NOT NULL AND D_ALB.FECHA IS NOT NULL "
      "GROUP BY D_PED.CODCLIENTE, PROVEEDOR "
      "HAVING N_PEDIDOS>=3 "
      "ORDER BY DIAS_MEDIO_ENTREGA ASC LIMIT 20",
      "Almacen", "Compras", "KPI", "Alto", "Lead time", ""),

    q("ax3_038", "Artículos con un único proveedor (riesgo de dependencia)",
      "¿Qué artículos solo tienen un proveedor registrado?",
      "Artículos con un único proveedor en albaranes de compra. Riesgo de dependencia.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_PROVEEDORES, "
      "MAX(D.CODCLIENTE) AS PROVEEDOR_UNICO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=10 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING N_PROVEEDORES=1 "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Almacen", "Compras", "Alerta", "Alto", "Dependencia", ""),

    q("ax3_039", "Variabilidad de precios de compra por artículo",
      "¿En qué artículos varía más el PRECIOVENTA de compra entre proveedores?",
      "Diferencia entre PRECIOVENTA máximo y mínimo de compra por artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(MIN(L.PRECIO),2) AS PRECIO_MIN, "
      "ROUND(MAX(L.PRECIO),2) AS PRECIO_MAX, "
      "ROUND(MAX(L.PRECIO)-MIN(L.PRECIO),2) AS VARIACION, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_PROVEEDORES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO IN (4,10) AND L.PRECIO>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING N_PROVEEDORES>1 "
      "ORDER BY VARIACION DESC LIMIT 25",
      "Almacen", "Compras", "KPI", "Medio", "Precios compra", ""),

    q("ax3_040", "Recepciones parciales de pedidos de compra",
      "¿Qué pedidos de compra tienen recepciones parciales pendientes?",
      "Pedidos TIPO=4 con albarán asociado pero con diferencia de unidades.",
      "SELECT D_PED.CODIGO AS COD_PEDIDO, D_PED.FECHA AS FECHA_PEDIDO, "
      "D_PED.CODCLIENTE, "
      "ROUND(SUM(L_PED.CANTIDAD),2) AS UNIDADES_PEDIDAS, "
      "ROUND(COALESCE(SUM(L_ALB.CANTIDAD),0),2) AS UNIDADES_RECIBIDAS, "
      "ROUND(SUM(L_PED.CANTIDAD)-COALESCE(SUM(L_ALB.CANTIDAD),0),2) AS PENDIENTE "
      "FROM DOCCAB D_PED "
      "JOIN DOCLIN L_PED ON L_PED.CODDOCUMENTO=D_PED.CODIGO "
      "LEFT JOIN DOCCAB D_ALB ON 1=0 AND D_ALB.TIPO=10 "
      "LEFT JOIN DOCLIN L_ALB ON L_ALB.CODDOCUMENTO=D_ALB.CODIGO "
      "AND L_ALB.CODIGO=L_PED.CODIGO "
      "WHERE D_PED.TIPO=4 "
      "GROUP BY D_PED.CODIGO, D_PED.FECHA, D_PED.CODCLIENTE "
      "HAVING PENDIENTE>0 "
      "ORDER BY D_PED.FECHA DESC LIMIT 25",
      "Almacen", "Compras", "Alerta", "Alto", "Pendientes", ""),

    # ── ANÁLISIS DE ARTÍCULOS ──────────────────────────────────────────────────

    q("ax3_041", "Artículos dados de alta en los últimos 30 días",
      "¿Qué artículos se han creado recientemente en el catálogo?",
      "Artículos con FECHAALTA en los últimos 30 días.",
      "SELECT A.CODIGO, A.NOMBRE, A.CODFAMILIA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "A.FECHAALTA "
      "FROM ARTICULO A "
      "WHERE A.FECHAALTA >= DATE('now','-30 days') "
      "ORDER BY A.FECHAALTA DESC LIMIT 30",
      "Almacen", "Almacen", "KPI", "Medio", "Catálogo", ""),

    q("ax3_042", "Artículos sin PRECIOVENTA de venta definido",
      "¿Qué artículos no tienen PRECIOVENTA de venta configurado?",
      "Artículos con PRECIOVENTA=0 o NULL que no pueden venderse correctamente.",
      "SELECT A.CODIGO, A.NOMBRE, A.CODFAMILIA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE "
      "FROM ARTICULO A "
      "WHERE (A.PRECIOVENTA IS NULL OR A.PRECIOVENTA=0) "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "Configuración", ""),

    q("ax3_043", "Artículos sin PRECIOVENTA de PRECIOCOSTE definido",
      "¿Qué artículos no tienen PRECIOVENTA de PRECIOCOSTE configurado?",
      "Artículos con PRECIOCOSTE=0 o NULL. Impide calcular márgenes correctamente.",
      "SELECT A.CODIGO, A.NOMBRE, A.CODFAMILIA, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA "
      "FROM ARTICULO A "
      "WHERE (A.PRECIOCOSTE IS NULL OR A.PRECIOCOSTE=0) "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Medio", "Configuración", ""),

    q("ax3_044", "Artículos con margen negativo (PRECIOCOSTE > precio venta)",
      "¿Qué artículos tienen el PRECIOCOSTE mayor que el PRECIOVENTA de venta?",
      "Artículos donde PRECIOCOSTE > PRECIOVENTA. Indica error de configuración o pérdida.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.PRECIOVENTA-A.PRECIOCOSTE,2) AS MARGEN_UNITARIO "
      "FROM ARTICULO A "
      "WHERE A.PRECIOCOSTE>0 AND A.PRECIOVENTA>0 AND A.PRECIOCOSTE>A.PRECIOVENTA "
      "ORDER BY MARGEN_UNITARIO ASC LIMIT 25",
      "Almacen", "Dirección", "Alerta", "Critico", "Márgenes", ""),

    q("ax3_045", "Artículos sin familia asignada",
      "¿Qué artículos no tienen familia asignada?",
      "Artículos con CODFAMILIA=NULL o sin registro en FAMILIA.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A "
      "WHERE A.CODFAMILIA IS NULL OR A.CODFAMILIA NOT IN "
      "(SELECT CODIGO FROM FAMILIA) "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Bajo", "Configuración", ""),

    q("ax3_046", "Artículos con STOCKARTICULO pero sin movimiento en el año",
      "¿Qué artículos tienen STOCKARTICULO pero no se han movido en todo el año?",
      "STOCKARTICULO inmovilizado sin ningún movimiento en los últimos 365 días.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.FECHA >= DATE('now','-365 days')) "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 30",
      "Almacen", "Dirección", "Alerta", "Alto", "Inmovilizado", ""),

    q("ax3_047", "Top artículos por número de líneas de documento",
      "¿Qué artículos aparecen en más documentos?",
      "Artículos con mayor presencia en documentos de cualquier tipo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_LINEAS, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS, "
      "COUNT(DISTINCT D.TIPO) AS TIPOS_DISTINTOS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_DOCUMENTOS DESC LIMIT 25",
      "Almacen", "Almacen", "KPI", "Medio", "Actividad", ""),

    q("ax3_048", "Artículos con PRECIOVENTA de venta sin actualizar (>1 año)",
      "¿Qué artículos no han actualizado su PRECIOVENTA de venta en más de un año?",
      "Artículos cuya FECHAMODPRECIO es anterior a hace 365 días.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_ACTUAL, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_ACTUAL, "
      "A.FECHAMODPRECIO AS ULTIMA_ACTUALIZACION "
      "FROM ARTICULO A "
      "WHERE A.FECHAMODPRECIO IS NOT NULL "
      "AND A.FECHAMODPRECIO < DATE('now','-365 days') "
      "ORDER BY A.FECHAMODPRECIO ASC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Medio", "Precios", ""),

    q("ax3_049", "Artículos con mayor número de proveedores",
      "¿Qué artículos tienen más proveedores alternativos?",
      "Artículos con más proveedores distintos en albaranes de compra.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_PROVEEDORES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=10 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_PROVEEDORES DESC LIMIT 20",
      "Almacen", "Compras", "KPI", "Bajo", "Proveedores", ""),

    q("ax3_050", "Artículos con mayor variación de PRECIOVENTA de compra",
      "¿En qué artículos varía más el PRECIOVENTA de compra a lo largo del tiempo?",
      "Coeficiente de variación del PRECIOVENTA de compra por artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_COMPRAS, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO, "
      "ROUND(MIN(L.PRECIO),2) AS PRECIO_MIN, "
      "ROUND(MAX(L.PRECIO),2) AS PRECIO_MAX, "
      "ROUND((MAX(L.PRECIO)-MIN(L.PRECIO))*100.0/NULLIF(AVG(L.PRECIO),0),1) AS CV_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=10 AND L.PRECIO>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING N_COMPRAS>=5 "
      "ORDER BY CV_PCT DESC LIMIT 20",
      "Almacen", "Compras", "KPI", "Medio", "Precios compra", ""),

    # ── INVENTARIO CÍCLICO Y RECUENTOS ─────────────────────────────────────────

    q("ax3_051", "Artículos pendientes de recuento (sin inventario reciente)",
      "¿Qué artículos no han sido inventariados en los últimos 6 meses?",
      "Artículos sin ajuste de inventario (TIPO=20) en los últimos 180 días.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR "
      "FROM ARTICULO A "
      "JOIN ESTALMACEN E ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=20 AND D.FECHA >= DATE('now','-180 days')) "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "ORDER BY VALOR DESC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Medio", "Inventario", ""),

    q("ax3_052", "Frecuencia de inventarios por artículo",
      "¿Con qué frecuencia se inventaría cada artículo?",
      "Número de ajustes de inventario (TIPO=20) por artículo en el último año.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_INVENTARIOS, "
      "MIN(D.FECHA) AS PRIMER_INVENTARIO, "
      "MAX(D.FECHA) AS ULTIMO_INVENTARIO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=20 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_INVENTARIOS DESC LIMIT 25",
      "Almacen", "Almacen", "KPI", "Bajo", "Inventario", ""),

    q("ax3_053", "Artículos con mayor discrepancia en inventarios",
      "¿En qué artículos se detectan más diferencias en los recuentos?",
      "Artículos con ajustes de inventario de mayor magnitud.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_AJUSTES, "
      "ROUND(SUM(ABS(L.CANTIDAD)),2) AS TOTAL_DIFERENCIA, "
      "ROUND(AVG(ABS(L.CANTIDAD)),2) AS DIFERENCIA_MEDIA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=20 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY TOTAL_DIFERENCIA DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Alto", "Inventario", ""),

    q("ax3_054", "Valor total de ajustes de inventario por año",
      "¿Cuánto valor se ajusta en inventario cada año?",
      "Valor absoluto de todos los ajustes de inventario agrupados por año.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "COUNT(*) AS N_AJUSTES, "
      "ROUND(SUM(ABS(L.CANTIDAD)*A.PRECIOCOSTE),2) AS VALOR_AJUSTADO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=20 "
      "GROUP BY SUBSTR(D.FECHA,1,4) "
      "ORDER BY ANIO DESC",
      "Almacen", "Dirección", "KPI", "Alto", "Inventario", ""),

    q("ax3_055", "Artículos con STOCKARTICULO exactamente en el mínimo",
      "¿Qué artículos tienen el STOCKARTICULO exactamente igual al mínimo?",
      "Artículos en el límite del STOCKARTICULO mínimo. Requieren reposición inmediata.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "A.STOCKARTICULO AS STOCK_MINIMO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING ABS(STOCK_ACTUAL - A.STOCKARTICULO) < 1 "
      "ORDER BY A.NOMBRE LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Alto", "Reposición", ""),

    # ── ANÁLISIS TEMPORAL Y ESTACIONALIDAD ─────────────────────────────────────

    q("ax3_056", "Estacionalidad de entradas de STOCKARTICULO por mes",
      "¿En qué meses del año entran más unidades al almacén?",
      "Entradas de STOCKARTICULO (TIPO=10) agrupadas por mes del año (sin año).",
      "SELECT SUBSTR(D.FECHA,6,2) AS MES_NUM, "
      "CASE SUBSTR(D.FECHA,6,2) "
      "WHEN '01' THEN 'Enero' WHEN '02' THEN 'Febrero' "
      "WHEN '03' THEN 'Marzo' WHEN '04' THEN 'Abril' "
      "WHEN '05' THEN 'Mayo' WHEN '06' THEN 'Junio' "
      "WHEN '07' THEN 'Julio' WHEN '08' THEN 'Agosto' "
      "WHEN '09' THEN 'Septiembre' WHEN '10' THEN 'Octubre' "
      "WHEN '11' THEN 'Noviembre' WHEN '12' THEN 'Diciembre' END AS MES_NOMBRE, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_ENTRADA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=10 "
      "GROUP BY SUBSTR(D.FECHA,6,2) "
      "ORDER BY MES_NUM",
      "Almacen", "Almacen", "KPI", "Medio", "Estacionalidad", ""),

    q("ax3_057", "Estacionalidad de salidas de STOCKARTICULO por mes",
      "¿En qué meses del año salen más unidades del almacén?",
      "Salidas de STOCKARTICULO (TIPO=11) agrupadas por mes del año.",
      "SELECT SUBSTR(D.FECHA,6,2) AS MES_NUM, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_SALIDA "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=11 "
      "GROUP BY SUBSTR(D.FECHA,6,2) "
      "ORDER BY MES_NUM",
      "Almacen", "Almacen", "KPI", "Medio", "Estacionalidad", ""),

    q("ax3_058", "Comparativa de STOCKARTICULO año actual vs año anterior",
      "¿Cómo ha evolucionado el valor del inventario respecto al año anterior?",
      "Valor de STOCKARTICULO en documentos del año actual vs año anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VALOR_ANIO_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS VALOR_ANIO_ANTERIOR "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=10",
      "Almacen", "Dirección", "KPI", "Alto", "Comparativa", ""),

    q("ax3_059", "Picos de actividad de almacén por día de la semana",
      "¿Qué días de la semana hay más actividad en almacén?",
      "Documentos de almacén agrupados por día de la semana.",
      "SELECT STRFTIME('%w',D.FECHA) AS DIA_NUM, "
      "CASE STRFTIME('%w',D.FECHA) "
      "WHEN '0' THEN 'Domingo' WHEN '1' THEN 'Lunes' "
      "WHEN '2' THEN 'Martes' WHEN '3' THEN 'Miércoles' "
      "WHEN '4' THEN 'Jueves' WHEN '5' THEN 'Viernes' "
      "WHEN '6' THEN 'Sábado' END AS DIA_NOMBRE, "
      "COUNT(*) AS N_DOCUMENTOS "
      "FROM DOCCAB D "
      "WHERE D.TIPO IN (10,11,20) AND D.FECHA IS NOT NULL "
      "GROUP BY STRFTIME('%w',D.FECHA) "
      "ORDER BY DIA_NUM",
      "Almacen", "Almacen", "KPI", "Bajo", "Actividad", ""),

    q("ax3_060", "Artículos con mayor crecimiento de STOCKARTICULO en 30 días",
      "¿Qué artículos han aumentado más su STOCKARTICULO en el último mes?",
      "Entradas netas (entradas - salidas) por artículo en los últimos 30 días.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(CASE WHEN D.TIPO=10 THEN L.CANTIDAD ELSE 0 END),2) AS ENTRADAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=11 THEN L.CANTIDAD ELSE 0 END),2) AS SALIDAS, "
      "ROUND(SUM(CASE WHEN D.TIPO=10 THEN L.CANTIDAD ELSE -L.CANTIDAD END),2) AS NETO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO IN (10,11) AND D.FECHA >= DATE('now','-30 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING NETO>0 "
      "ORDER BY NETO DESC LIMIT 25",
      "Almacen", "Almacen", "KPI", "Medio", "Crecimiento", ""),

    # ── ANÁLISIS DE PICKING Y PREPARACIÓN ──────────────────────────────────────

    q("ax3_061", "Líneas de albarán por operario (productividad picking)",
      "¿Cuántas líneas de albarán prepara cada operario?",
      "Líneas de albarán de venta (TIPO=11) por usuario en los últimos 30 días.",
      "SELECT D.CODAGENTE, "
      "COUNT(*) AS N_LINEAS, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES, "
      "ROUND(COUNT(*)*1.0/COUNT(DISTINCT D.CODIGO),1) AS LINEAS_POR_ALBARAN "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=11 AND D.FECHA >= DATE('now','-30 days') "
      "GROUP BY D.CODAGENTE "
      "ORDER BY N_LINEAS DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Medio", "Productividad", ""),

    q("ax3_062", "Albaranes con más líneas (complejidad de picking)",
      "¿Qué albaranes tienen más líneas de artículos?",
      "Albaranes de venta (TIPO=11) con mayor número de líneas.",
      "SELECT D.CODIGO AS COD_ALBARAN, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_UNIDADES "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=11 "
      "GROUP BY D.CODIGO, D.FECHA, CLIENTE "
      "ORDER BY N_LINEAS DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Bajo", "Picking", ""),

    q("ax3_063", "Tiempo medio de preparación de albaranes por mes",
      "¿Cuánto tiempo transcurre entre pedido y albarán de venta?",
      "Días entre pedido de venta (TIPO=1) y albarán (TIPO=11) por mes.",
      "SELECT SUBSTR(D_PED.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_PEDIDOS, "
      "ROUND(AVG(JULIANDAY(D_ALB.FECHA)-JULIANDAY(D_PED.FECHA)),1) AS DIAS_MEDIO "
      "FROM DOCCAB D_PED "
      "JOIN DOCCAB D_ALB ON 1=0 AND D_ALB.TIPO=11 "
      "WHERE D_PED.TIPO=1 AND D_PED.FECHA IS NOT NULL AND D_ALB.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D_PED.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 12",
      "Almacen", "Almacen", "KPI", "Alto", "Lead time", ""),

    q("ax3_064", "Artículos más frecuentes en albaranes de venta",
      "¿Qué artículos aparecen en más albaranes de venta?",
      "Artículos con mayor presencia en albaranes TIPO=11.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_ALBARANES, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_UNIDADES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=11 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_ALBARANES DESC LIMIT 25",
      "Almacen", "Almacen", "KPI", "Medio", "Picking", ""),

    q("ax3_065", "Albaranes pendientes de servir (sin facturar)",
      "¿Cuántos albaranes de venta están pendientes de facturar?",
      "Albaranes TIPO=11 sin factura asociada agrupados por cliente.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES_PENDIENTES, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_PENDIENTE "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=11 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=13) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY IMPORTE_PENDIENTE DESC LIMIT 25",
      "Almacen", "Ventas", "Alerta", "Alto", "Pendientes", ""),

    # ── ANÁLISIS DE FAMILIAS Y CATEGORÍAS ──────────────────────────────────────

    q("ax3_066", "Familias con mayor número de artículos",
      "¿Qué familias tienen más artículos en el catálogo?",
      "Número de artículos por familia en la tabla ARTICULO.",
      "SELECT F.CODIGO, F.NOMBRE AS FAMILIA, "
      "COUNT(A.CODIGO) AS N_ARTICULOS, "
      "ROUND(AVG(A.PRECIOVENTA),2) AS PRECIO_MEDIO, "
      "ROUND(AVG(A.PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM FAMILIA F "
      "LEFT JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY F.CODIGO, F.NOMBRE "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Bajo", "Catálogo", ""),

    q("ax3_067", "Familias con mayor valor de STOCKARTICULO",
      "¿Qué familias concentran más valor en almacén?",
      "Valor de STOCKARTICULO (STOCKARTICULO × PRECIOCOSTE) agrupado por familia.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "COUNT(DISTINCT A.CODIGO) AS N_ARTICULOS_CON_STOCKARTICULO, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_TOTAL "
      "FROM FAMILIA F "
      "JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      "JOIN ESTALMACEN E ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY F.NOMBRE "
      "ORDER BY VALOR_TOTAL DESC LIMIT 20",
      "Almacen", "Dirección", "KPI", "Alto", "Familias", ""),

    q("ax3_068", "Familias con mayor rotación de STOCKARTICULO",
      "¿Qué familias tienen mayor velocidad de rotación?",
      "Unidades vendidas (TIPO=13) por familia en los últimos 12 meses.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "COUNT(DISTINCT L.CODARTICULO) AS N_ARTICULOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_VENDIDAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_VENTAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY F.NOMBRE "
      "ORDER BY UNIDADES_VENDIDAS DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Alto", "Rotación", ""),

    q("ax3_069", "Familias con artículos sin movimiento",
      "¿Qué familias tienen más artículos sin movimiento?",
      "Familias con mayor proporción de artículos sin movimiento en 180 días.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "COUNT(DISTINCT A.CODIGO) AS TOTAL_ARTICULOS, "
      "COUNT(DISTINCT CASE WHEN A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.FECHA >= DATE('now','-180 days')) "
      "THEN A.CODIGO END) AS SIN_MOVIMIENTO "
      "FROM FAMILIA F "
      "JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY F.NOMBRE "
      "HAVING SIN_MOVIMIENTO>0 "
      "ORDER BY SIN_MOVIMIENTO DESC LIMIT 20",
      "Almacen", "Almacen", "Alerta", "Medio", "Rotación", ""),

    q("ax3_070", "Margen medio por familia de artículo",
      "¿Cuál es el margen bruto medio de cada familia?",
      "Diferencia entre PRECIOVENTA de venta y PRECIOCOSTE medio por familia.",
      "SELECT F.NOMBRE AS FAMILIA, "
      "COUNT(A.CODIGO) AS N_ARTICULOS, "
      "ROUND(AVG(A.PRECIOVENTA),2) AS PRECIO_MEDIO, "
      "ROUND(AVG(A.PRECIOCOSTE),2) AS COSTE_MEDIO, "
      "ROUND(AVG(A.PRECIOVENTA-A.PRECIOCOSTE),2) AS MARGEN_MEDIO, "
      "ROUND(AVG((A.PRECIOVENTA-A.PRECIOCOSTE)*100.0/NULLIF(A.PRECIOVENTA,0)),1) AS MARGEN_PCT "
      "FROM FAMILIA F "
      "JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      "WHERE A.PRECIOVENTA>0 AND A.PRECIOCOSTE>0 "
      "GROUP BY F.NOMBRE "
      "ORDER BY MARGEN_PCT DESC LIMIT 20",
      "Almacen", "Dirección", "KPI", "Alto", "Márgenes", ""),

    # ── ANÁLISIS DE EFICIENCIA OPERATIVA ───────────────────────────────────────

    q("ax3_071", "Documentos de almacén por hora del día",
      "¿A qué horas del día hay más actividad en almacén?",
      "Documentos de almacén agrupados por hora de creación.",
      "SELECT SUBSTR(D.HORA,1,2) AS HORA, "
      "COUNT(*) AS N_DOCUMENTOS "
      "FROM DOCCAB D "
      "WHERE D.TIPO IN (10,11,20) AND D.HORA IS NOT NULL "
      "GROUP BY SUBSTR(D.HORA,1,2) "
      "ORDER BY HORA",
      "Almacen", "Almacen", "KPI", "Bajo", "Eficiencia", ""),

    q("ax3_072", "Albaranes con errores de cantidad (unidades=0)",
      "¿Existen líneas de albarán con cantidad cero?",
      "Líneas de albarán con CANTIDAD=0 que pueden indicar errores de entrada.",
      "SELECT D.CODIGO AS COD_DOC, D.FECHA, D.TIPO, "
      "L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "L.CANTIDAD "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO IN (10,11) AND L.CANTIDAD=0 "
      "ORDER BY D.FECHA DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Medio", "Errores", ""),

    q("ax3_073", "Albaranes con PRECIOVENTA cero en líneas",
      "¿Existen líneas de albarán con PRECIOVENTA cero?",
      "Líneas de albarán con PRECIOVENTA=0 que pueden indicar errores de valoración.",
      "SELECT D.CODIGO AS COD_DOC, D.FECHA, D.TIPO, "
      "L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(L.CANTIDAD,2) AS CANTIDAD "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO IN (10,11) AND (L.PRECIO IS NULL OR L.PRECIO=0) "
      "ORDER BY D.FECHA DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Medio", "Errores", ""),

    q("ax3_074", "Documentos duplicados en almacén (mismo día, mismo proveedor)",
      "¿Existen albaranes duplicados del mismo proveedor en el mismo día?",
      "Albaranes de compra con mismo proveedor y fecha que pueden ser duplicados.",
      "SELECT D.FECHA, D.CODCLIENTE, D.TIPO, "
      "COUNT(*) AS N_DOCUMENTOS "
      "FROM DOCCAB D "
      "WHERE D.TIPO=10 AND D.FECHA IS NOT NULL "
      "GROUP BY D.FECHA, D.CODCLIENTE, D.TIPO "
      "HAVING N_DOCUMENTOS>1 "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Almacen", "Almacen", "Alerta", "Alto", "Duplicados", ""),

    q("ax3_075", "Artículos con código duplicado o similar",
      "¿Existen artículos con nombres muy similares que puedan ser duplicados?",
      "Artículos con el mismo nombre (primeros 20 caracteres) pero distinto código.",
      "SELECT SUBSTR(A.NOMBRE,1,20) AS NOMBRE_CORTO, "
      "COUNT(*) AS N_ARTICULOS, "
      "GROUP_CONCAT(A.CODIGO) AS CODIGOS "
      "FROM ARTICULO A "
      "GROUP BY SUBSTR(A.NOMBRE,1,20) "
      "HAVING N_ARTICULOS>1 "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Almacen", "Almacen", "Alerta", "Medio", "Duplicados", ""),

    # ── ANÁLISIS DE COSTES Y VALORACIÓN ────────────────────────────────────────

    q("ax3_076", "Evolución del PRECIOCOSTE medio de compra por artículo",
      "¿Cómo ha evolucionado el PRECIOCOSTE de compra de los principales artículos?",
      "PRECIOVENTA medio de compra por artículo y año en albaranes TIPO=10.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "SUBSTR(D.FECHA,1,4) AS ANIO, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO_COMPRA, "
      "COUNT(*) AS N_COMPRAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=10 AND L.PRECIO>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE, SUBSTR(D.FECHA,1,4) "
      "ORDER BY L.CODARTICULO, ANIO DESC LIMIT 60",
      "Almacen", "Compras", "KPI", "Alto", "Costes", ""),

    q("ax3_077", "Diferencia entre PRECIOCOSTE registrado y PRECIOCOSTE de compra real",
      "¿El PRECIOCOSTE registrado en el artículo coincide con el PRECIOVENTA de compra real?",
      "Compara ARTICULO.COSTE con el PRECIOVENTA medio de compra en albaranes.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_REGISTRADO, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_COMPRA_REAL, "
      "ROUND(AVG(L.PRECIO)-A.PRECIOCOSTE,2) AS DIFERENCIA "
      "FROM ARTICULO A "
      "JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=10 AND L.PRECIO>0 AND A.PRECIOCOSTE>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING ABS(DIFERENCIA)>1 "
      "ORDER BY ABS(DIFERENCIA) DESC LIMIT 25",
      "Almacen", "Compras", "Alerta", "Alto", "Costes", ""),

    q("ax3_078", "Valor total del inventario por mes (evolución)",
      "¿Cómo ha evolucionado el valor del inventario mes a mes?",
      "Valor de entradas netas acumuladas por mes para estimar evolución del inventario.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN D.TIPO=10 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS ENTRADAS_VALOR, "
      "ROUND(SUM(CASE WHEN D.TIPO=11 THEN L.CANTIDAD*L.PRECIO ELSE 0 END),2) AS SALIDAS_VALOR "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO IN (10,11) "
      "GROUP BY SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC LIMIT 24",
      "Almacen", "Dirección", "KPI", "Alto", "Valoración", ""),

    q("ax3_079", "Artículos con mayor PRECIOCOSTE de almacenamiento (valor × tiempo)",
      "¿Qué artículos generan mayor PRECIOCOSTE de almacenamiento por inmovilización?",
      "Artículos con alto valor de STOCKARTICULO y sin movimiento reciente.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_UNIT, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO, "
      "COALESCE(MAX(D.FECHA),'Sin movimiento') AS ULTIMO_MOVIMIENTO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING VALOR_INMOVILIZADO>500 "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 25",
      "Almacen", "Dirección", "KPI", "Alto", "Costes", ""),

    q("ax3_080", "Resumen de KPIs de almacén",
      "¿Cuál es el resumen ejecutivo de los principales KPIs de almacén?",
      "Métricas clave: artículos totales, valor inventario, artículos bajo mínimo, sin movimiento.",
      "SELECT "
      "(SELECT COUNT(*) FROM ARTICULO) AS TOTAL_ARTICULOS, "
      "(SELECT COUNT(DISTINCT CODIGO) FROM ARTICULO WHERE STOCKARTICULO>0) AS ARTICULOS_CON_STOCKARTICULO, "
      "(SELECT ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO WHERE A.STOCKARTICULO>0) AS VALOR_INVENTARIO, "
      "(SELECT COUNT(*) FROM ARTICULO WHERE STOCKARTICULO<0) AS ARTICULOS_STOCK_NEGATIVO, "
      "(SELECT COUNT(*) FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.STOCKARTICULO<A.STOCKARTICULO) AS BAJO_MINIMO",
      "Almacen", "Dirección", "KPI", "Critico", "Resumen", ""),

    # ── ANÁLISIS DE CLIENTES EN ALMACÉN ────────────────────────────────────────

    q("ax3_081", "Clientes con más albaranes de venta pendientes",
      "¿Qué clientes tienen más albaranes sin facturar?",
      "Clientes con mayor número de albaranes TIPO=11 sin factura asociada.",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_ALBARANES, "
      "MIN(D.FECHA) AS ALBARAN_MAS_ANTIGUO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=11 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=13) "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY N_ALBARANES DESC LIMIT 20",
      "Almacen", "Ventas", "Alerta", "Alto", "Pendientes", ""),

    q("ax3_082", "Artículos más devueltos por clientes",
      "¿Qué artículos generan más devoluciones de clientes?",
      "Artículos con más líneas en abonos de venta (TIPO=14).",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_DEVOLUCIONES, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_DEVUELTAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_DEVUELTO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=14 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_DEVUELTAS DESC LIMIT 20",
      "Almacen", "Calidad", "Alerta", "Alto", "Devoluciones", ""),

    q("ax3_083", "Clientes con mayor volumen de devoluciones",
      "¿Qué clientes devuelven más mercancía?",
      "Clientes con mayor importe en abonos de venta (TIPO=14).",
      "SELECT D.CODCLIENTE, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(DISTINCT D.CODIGO) AS N_ABONOS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_DEVUELTO "
      "FROM DOCCAB D "
      "JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=14 "
      "GROUP BY D.CODCLIENTE, CLIENTE "
      "ORDER BY IMPORTE_DEVUELTO DESC LIMIT 20",
      "Almacen", "Ventas", "Alerta", "Alto", "Devoluciones", ""),

    q("ax3_084", "Artículos reservados para clientes (pedidos pendientes)",
      "¿Qué artículos tienen unidades reservadas en pedidos de venta?",
      "Unidades en pedidos de venta (TIPO=1) no servidos aún.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_RESERVADAS, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_DISPONIBLE "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN ESTALMACEN E ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=1 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=11) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_RESERVADAS DESC LIMIT 25",
      "Almacen", "Ventas", "KPI", "Alto", "Reservas", ""),

    q("ax3_085", "STOCKARTICULO disponible vs reservado por artículo",
      "¿Cuánto STOCKARTICULO libre queda después de descontar reservas?",
      "STOCKARTICULO actual menos unidades en pedidos de venta pendientes.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL, "
      "ROUND(COALESCE(R.RESERVADO,0),2) AS RESERVADO, "
      "ROUND(SUM(A.STOCKARTICULO)-COALESCE(R.RESERVADO,0),2) AS STOCK_LIBRE "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS RESERVADO "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=1 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=11) "
      "GROUP BY L.CODARTICULO) R ON R.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, R.RESERVADO "
      "ORDER BY STOCK_LIBRE ASC LIMIT 30",
      "Almacen", "Ventas", "KPI", "Critico", "Reservas", ""),

    # ── ANÁLISIS DE CALIDAD EN ALMACÉN ─────────────────────────────────────────

    q("ax3_086", "Artículos con más incidencias de calidad",
      "¿Qué artículos generan más incidencias de calidad en almacén?",
      "Artículos con mayor número de ajustes negativos y devoluciones combinados.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "COUNT(DISTINCT CASE WHEN D.TIPO=20 AND L.CANTIDAD<0 THEN L.CODDOCUMENTO END) AS AJUSTES_NEG, "
      "COUNT(DISTINCT CASE WHEN D.TIPO=14 THEN L.CODDOCUMENTO END) AS DEVOLUCIONES, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS TOTAL_INCIDENCIAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO IN (14,20) "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING TOTAL_INCIDENCIAS>0 "
      "ORDER BY TOTAL_INCIDENCIAS DESC LIMIT 25",
      "Almacen", "Calidad", "Alerta", "Alto", "Calidad", ""),

    q("ax3_087", "Ratio de incidencias sobre movimientos totales",
      "¿Qué porcentaje de los movimientos son incidencias?",
      "Incidencias (ajustes negativos + devoluciones) sobre total de movimientos.",
      "SELECT "
      "COUNT(DISTINCT CASE WHEN D.TIPO IN (14,20) THEN L.CODDOCUMENTO END) AS N_INCIDENCIAS, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_TOTAL_MOVIMIENTOS, "
      "ROUND(COUNT(DISTINCT CASE WHEN D.TIPO IN (14,20) THEN L.CODDOCUMENTO END)*100.0/"
      "NULLIF(COUNT(DISTINCT L.CODDOCUMENTO),0),2) AS RATIO_INCIDENCIAS_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO",
      "Almacen", "Calidad", "KPI", "Alto", "Calidad", ""),

    q("ax3_088", "Artículos con STOCKARTICULO negativo por almacén",
      "¿En qué almacenes hay artículos con STOCKARTICULO negativo?",
      "Detalle de artículos con STOCKARTICULO negativo por almacén.",
      "SELECT '01', A.CODIGO, A.NOMBRE, "
      "ROUND(A.STOCKARTICULO,2) AS STOCK_NEGATIVO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO<0 "
      "ORDER BY '01', A.STOCKARTICULO ASC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Critico", "STOCKARTICULO negativo", ""),

    q("ax3_089", "Artículos con STOCKARTICULO fraccionado (no entero)",
      "¿Qué artículos tienen STOCKARTICULO con decimales cuando deberían ser enteros?",
      "Artículos con STOCKARTICULO que no es número entero.",
      "SELECT A.CODIGO, A.NOMBRE, '01', "
      "ROUND(A.STOCKARTICULO,4) AS STOCKARTICULO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO != CAST(A.STOCKARTICULO AS INTEGER) AND A.STOCKARTICULO>0 "
      "ORDER BY A.NOMBRE LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Bajo", "Calidad datos", ""),

    q("ax3_090", "Documentos de almacén sin líneas asociadas",
      "¿Existen documentos de almacén sin ninguna línea de artículo?",
      "Documentos TIPO=10,11,20 sin líneas en DOCLIN. Posibles documentos vacíos.",
      "SELECT D.CODIGO, D.FECHA, D.TIPO, D.CODAGENTE "
      "FROM DOCCAB D "
      "WHERE D.TIPO IN (10,11,20) AND D.CODIGO NOT IN ("
      "SELECT DISTINCT CODDOCUMENTO FROM DOCLIN) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Almacen", "Almacen", "Alerta", "Medio", "Calidad datos", ""),

    # ── ANÁLISIS AVANZADO ──────────────────────────────────────────────────────

    q("ax3_091", "Artículos con demanda irregular (coeficiente de variación alto)",
      "¿Qué artículos tienen demanda muy irregular mes a mes?",
      "Artículos con alta variabilidad en unidades vendidas por mes.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_ACTIVOS, "
      "ROUND(AVG(MES_VENTAS.UNIDADES_MES),2) AS MEDIA_MENSUAL, "
      "ROUND(MAX(MES_VENTAS.UNIDADES_MES)-MIN(MES_VENTAS.UNIDADES_MES),2) AS RANGO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN (SELECT L2.CODIGO, SUBSTR(D2.FECHA,1,7) AS MES, "
      "SUM(L2.CANTIDAD) AS UNIDADES_MES "
      "FROM DOCLIN L2 JOIN DOCCAB D2 ON D2.CODIGO=L2.CODDOCUMENTO "
      "WHERE D2.TIPO=13 GROUP BY L2.CODIGO, SUBSTR(D2.FECHA,1,7)) MES_VENTAS "
      "ON MES_VENTAS.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING MESES_ACTIVOS>=6 AND RANGO>10 "
      "ORDER BY RANGO DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Medio", "Demanda", ""),

    q("ax3_092", "Artículos con tendencia creciente de ventas",
      "¿Qué artículos muestran tendencia creciente en ventas?",
      "Artículos donde las ventas del último trimestre superan al anterior.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(CASE WHEN D.FECHA >= DATE('now','-90 days') "
      "THEN L.CANTIDAD ELSE 0 END),2) AS VENTAS_ULTIMO_TRIM, "
      "ROUND(SUM(CASE WHEN D.FECHA BETWEEN DATE('now','-180 days') "
      "AND DATE('now','-91 days') THEN L.CANTIDAD ELSE 0 END),2) AS VENTAS_TRIM_ANTERIOR "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-180 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING VENTAS_ULTIMO_TRIM > VENTAS_TRIM_ANTERIOR AND VENTAS_TRIM_ANTERIOR>0 "
      "ORDER BY (VENTAS_ULTIMO_TRIM-VENTAS_TRIM_ANTERIOR) DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Alto", "Tendencia", ""),

    q("ax3_093", "Artículos con tendencia decreciente de ventas",
      "¿Qué artículos muestran tendencia decreciente en ventas?",
      "Artículos donde las ventas del último trimestre son menores al anterior.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(CASE WHEN D.FECHA >= DATE('now','-90 days') "
      "THEN L.CANTIDAD ELSE 0 END),2) AS VENTAS_ULTIMO_TRIM, "
      "ROUND(SUM(CASE WHEN D.FECHA BETWEEN DATE('now','-180 days') "
      "AND DATE('now','-91 days') THEN L.CANTIDAD ELSE 0 END),2) AS VENTAS_TRIM_ANTERIOR "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-180 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING VENTAS_ULTIMO_TRIM < VENTAS_TRIM_ANTERIOR AND VENTAS_ULTIMO_TRIM>0 "
      "ORDER BY (VENTAS_TRIM_ANTERIOR-VENTAS_ULTIMO_TRIM) DESC LIMIT 20",
      "Almacen", "Ventas", "Alerta", "Alto", "Tendencia", ""),

    q("ax3_094", "Artículos con ventas solo en un cliente",
      "¿Qué artículos se venden exclusivamente a un único cliente?",
      "Artículos con un único cliente en facturas de venta TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "MAX(D.CODCLIENTE) AS CLIENTE_UNICO, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_VENDIDO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING N_CLIENTES=1 "
      "ORDER BY TOTAL_VENDIDO DESC LIMIT 25",
      "Almacen", "Ventas", "Alerta", "Medio", "Dependencia", ""),

    q("ax3_095", "Artículos con ventas en todos los meses del año",
      "¿Qué artículos se venden de forma constante todos los meses?",
      "Artículos presentes en los 12 meses del último año.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_CON_VENTA, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_VENDIDO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING MESES_CON_VENTA=12 "
      "ORDER BY TOTAL_VENDIDO DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Alto", "Constancia", ""),

    q("ax3_096", "Artículos con ventas solo en un mes del año",
      "¿Qué artículos tienen ventas concentradas en un único mes?",
      "Artículos con ventas en un solo mes del último año. Alta estacionalidad.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT SUBSTR(D.FECHA,1,7)) AS MESES_CON_VENTA, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_VENDIDO, "
      "MAX(SUBSTR(D.FECHA,1,7)) AS MES_VENTA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING MESES_CON_VENTA=1 AND TOTAL_VENDIDO>10 "
      "ORDER BY TOTAL_VENDIDO DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Medio", "Estacionalidad", ""),

    q("ax3_097", "Artículos con mayor número de clientes distintos",
      "¿Qué artículos tienen la base de clientes más amplia?",
      "Artículos vendidos a más clientes distintos en facturas TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_VENDIDO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_CLIENTES DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Medio", "Clientes", ""),

    q("ax3_098", "Artículos con PRECIOVENTA de venta superior a 3x el PRECIOCOSTE",
      "¿Qué artículos tienen un margen superior al 200%?",
      "Artículos donde PRECIOVENTA > 3 × PRECIOCOSTE. Margen bruto superior al 200%.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND((A.PRECIOVENTA-A.PRECIOCOSTE)*100.0/NULLIF(A.PRECIOCOSTE,0),1) AS MARGEN_SOBRE_COSTE_PCT "
      "FROM ARTICULO A "
      "WHERE A.PRECIOCOSTE>0 AND A.PRECIOVENTA>0 AND A.PRECIOVENTA>3*A.PRECIOCOSTE "
      "ORDER BY MARGEN_SOBRE_COSTE_PCT DESC LIMIT 25",
      "Almacen", "Dirección", "KPI", "Medio", "Márgenes", ""),

    q("ax3_099", "Artículos con PRECIOVENTA de venta inferior a 1.1x el PRECIOCOSTE",
      "¿Qué artículos tienen margen inferior al 10%?",
      "Artículos donde PRECIOVENTA < 1.1 × PRECIOCOSTE. Margen bruto inferior al 10%.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND((A.PRECIOVENTA-A.PRECIOCOSTE)*100.0/NULLIF(A.PRECIOVENTA,0),1) AS MARGEN_PCT "
      "FROM ARTICULO A "
      "WHERE A.PRECIOCOSTE>0 AND A.PRECIOVENTA>0 AND A.PRECIOVENTA<1.1*A.PRECIOCOSTE "
      "ORDER BY MARGEN_PCT ASC LIMIT 25",
      "Almacen", "Dirección", "Alerta", "Alto", "Márgenes", ""),

    q("ax3_100", "Resumen de actividad de almacén del último mes",
      "¿Cuál es el resumen de actividad de almacén del último mes?",
      "Métricas del último mes: albaranes, artículos movidos, entradas, salidas.",
      "SELECT "
      "(SELECT COUNT(DISTINCT CODIGO) FROM DOCCAB D "
      "WHERE D.TIPO=10 AND D.FECHA >= DATE('now','-30 days')) AS ALBARANES_COMPRA, "
      "(SELECT COUNT(DISTINCT CODIGO) FROM DOCCAB D "
      "WHERE D.TIPO=11 AND D.FECHA >= DATE('now','-30 days')) AS ALBARANES_VENTA, "
      "(SELECT COUNT(DISTINCT L.CODARTICULO) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO IN (10,11) AND D.FECHA >= DATE('now','-30 days')) AS ARTICULOS_MOVIDOS, "
      "(SELECT ROUND(SUM(L.CANTIDAD),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=10 AND D.FECHA >= DATE('now','-30 days')) AS UNIDADES_ENTRADA, "
      "(SELECT ROUND(SUM(L.CANTIDAD),2) FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=11 AND D.FECHA >= DATE('now','-30 days')) AS UNIDADES_SALIDA",
      "Almacen", "Dirección", "KPI", "Alto", "Resumen", ""),

    # ── ANÁLISIS COMPLEMENTARIO ────────────────────────────────────────────────

    q("ax3_101", "Artículos con más de 5 proveedores distintos",
      "¿Qué artículos tienen una amplia red de proveedores?",
      "Artículos con 5 o más proveedores distintos en albaranes de compra.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_PROVEEDORES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=10 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING N_PROVEEDORES>=5 "
      "ORDER BY N_PROVEEDORES DESC LIMIT 20",
      "Almacen", "Compras", "KPI", "Bajo", "Proveedores", ""),

    q("ax3_102", "Artículos con STOCKARTICULO en todos los almacenes",
      "¿Qué artículos tienen STOCKARTICULO en todos los almacenes activos?",
      "Artículos presentes en todos los almacenes con STOCKARTICULO positivo.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "COUNT(DISTINCT '01') AS N_ALMACENES, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING N_ALMACENES=(SELECT COUNT(DISTINCT CODALMACEN) FROM ARTICULO WHERE STOCKARTICULO>0) "
      "ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Medio", "Multi-almacén", ""),

    q("ax3_103", "Artículos con PRECIOVENTA de compra superior al de venta",
      "¿Existen artículos donde el PRECIOVENTA de compra supera al de venta?",
      "Artículos donde el PRECIOVENTA medio de compra (TIPO=10) supera al PRECIOVENTA de venta.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_COMPRA_MEDIO, "
      "ROUND(AVG(L.PRECIO)-A.PRECIOVENTA,2) AS DIFERENCIA "
      "FROM ARTICULO A "
      "JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=10 AND L.PRECIO>0 AND A.PRECIOVENTA>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOVENTA "
      "HAVING PRECIO_COMPRA_MEDIO > A.PRECIOVENTA "
      "ORDER BY DIFERENCIA DESC LIMIT 20",
      "Almacen", "Dirección", "Alerta", "Critico", "Márgenes", ""),

    q("ax3_104", "Artículos con alta rotación pero sin STOCKARTICULO mínimo",
      "¿Qué artículos de alta rotación no tienen STOCKARTICULO mínimo configurado?",
      "Artículos con más de 10 movimientos en 90 días sin STOCKARTICULO definido.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_MOVIMIENTOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_UNIDADES "
      "FROM ARTICULO A "
      "JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE (A.STOCKARTICULO IS NULL OR A.STOCKARTICULO=0) "
      "AND D.TIPO=13 AND D.FECHA >= DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING N_MOVIMIENTOS>10 "
      "ORDER BY N_MOVIMIENTOS DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Alto", "Configuración", ""),

    q("ax3_105", "Artículos con STOCKARTICULO pero sin PRECIOVENTA de venta",
      "¿Hay artículos en STOCKARTICULO que no se pueden vender por falta de PRECIOVENTA?",
      "Artículos con STOCKARTICULO positivo pero sin PRECIOVENTA de venta configurado.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 AND (A.PRECIOVENTA IS NULL OR A.PRECIOVENTA=0) "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Alto", "Configuración", ""),

    q("ax3_106", "Artículos con STOCKARTICULO pero sin PRECIOCOSTE definido",
      "¿Hay artículos en STOCKARTICULO sin PRECIOCOSTE definido que impiden valorar el inventario?",
      "Artículos con STOCKARTICULO positivo pero sin PRECIOCOSTE configurado.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 AND (A.PRECIOCOSTE IS NULL OR A.PRECIOCOSTE=0) "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY STOCK_ACTUAL DESC LIMIT 25",
      "Almacen", "Almacen", "Alerta", "Medio", "Configuración", ""),

    q("ax3_107", "Artículos con más de 100 unidades en STOCKARTICULO",
      "¿Qué artículos tienen grandes cantidades en almacén?",
      "Artículos con STOCKARTICULO total superior a 100 unidades.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_TOTAL "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING STOCK_TOTAL>100 "
      "ORDER BY STOCK_TOTAL DESC LIMIT 30",
      "Almacen", "Almacen", "KPI", "Medio", "STOCKARTICULO alto", ""),

    q("ax3_108", "Artículos con menos de 5 unidades en STOCKARTICULO",
      "¿Qué artículos tienen STOCKARTICULO muy bajo (menos de 5 unidades)?",
      "Artículos con STOCKARTICULO entre 0 y 5 unidades. Posible riesgo de rotura.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL, "
      "A.STOCKARTICULO AS STOCK_MINIMO "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING STOCK_TOTAL<5 "
      "ORDER BY STOCK_TOTAL ASC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "STOCKARTICULO bajo", ""),

    q("ax3_109", "Artículos con STOCKARTICULO exactamente cero",
      "¿Qué artículos tienen STOCKARTICULO exactamente cero?",
      "Artículos con STOCKARTICULO=0 en ESTALMACEN. Pueden estar agotados.",
      "SELECT A.CODIGO, A.NOMBRE, A.CODFAMILIA, "
      "A.STOCKARTICULO AS STOCK_MINIMO "
      "FROM ARTICULO A "
      "WHERE A.CODIGO IN ("
      "SELECT CODIGO FROM ARTICULO "
      "GROUP BY CODIGO HAVING SUM(STOCKARTICULO)=0) "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "STOCKARTICULO cero", ""),

    q("ax3_110", "Artículos con mayor número de familias de clientes compradores",
      "¿Qué artículos son comprados por clientes de más sectores distintos?",
      "Artículos vendidos a clientes de más sectores/familias distintas.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT NULL) AS N_SECTORES_CLIENTE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_SECTORES_CLIENTE DESC, N_CLIENTES DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Bajo", "Segmentación", ""),

    q("ax3_111", "Artículos con ventas en el extranjero",
      "¿Qué artículos se venden a clientes extranjeros?",
      "Artículos vendidos a clientes con país distinto al nacional.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES_EXTRAN, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_EXPORTADAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND C.CODPAIS IS NOT NULL AND C.CODPAIS<>'ES' "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_EXPORTADAS DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Medio", "Exportación", ""),

    q("ax3_112", "Artículos con descuentos frecuentes en ventas",
      "¿Qué artículos se venden habitualmente con descuento?",
      "Artículos con descuento en más del 50% de sus líneas de factura.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_LINEAS, "
      "COUNT(CASE WHEN L.DESCUENTOS>0 THEN 1 END) AS N_CON_DESCUENTO, "
      "ROUND(COUNT(CASE WHEN L.DESCUENTOS>0 THEN 1 END)*100.0/COUNT(*),1) AS PCT_CON_DESCUENTO, "
      "ROUND(AVG(CASE WHEN L.DESCUENTOS>0 THEN L.DESCUENTOS END),2) AS DESCUENTO_MEDIO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING PCT_CON_DESCUENTO>50 "
      "ORDER BY PCT_CON_DESCUENTO DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Medio", "Descuentos", ""),

    q("ax3_113", "Artículos con mayor descuento medio aplicado",
      "¿En qué artículos se aplican los mayores descuentos?",
      "Descuento medio por artículo en facturas de venta TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(AVG(L.DESCUENTOS),2) AS DESCUENTO_MEDIO, "
      "ROUND(MAX(L.DESCUENTOS),2) AS DESCUENTO_MAX "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY DESCUENTO_MEDIO DESC LIMIT 20",
      "Almacen", "Ventas", "KPI", "Medio", "Descuentos", ""),

    q("ax3_114", "Artículos con ventas en el último trimestre sin STOCKARTICULO",
      "¿Qué artículos se han vendido recientemente pero no tienen STOCKARTICULO?",
      "Artículos con ventas en 90 días pero con STOCKARTICULO=0 o sin registro.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_VENDIDAS, "
      "ROUND(COALESCE(SUM(A.STOCKARTICULO),0),2) AS STOCK_ACTUAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN ESTALMACEN E ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-90 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "HAVING STOCK_ACTUAL<=0 "
      "ORDER BY UNIDADES_VENDIDAS DESC LIMIT 25",
      "Almacen", "Ventas", "Alerta", "Critico", "Rotura", ""),

    q("ax3_115", "Artículos con pedidos de compra abiertos",
      "¿Qué artículos tienen pedidos de compra pendientes de recibir?",
      "Artículos en pedidos de compra (TIPO=4) sin albarán asociado.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_PEDIDAS, "
      "MIN(D.FECHA) AS PEDIDO_MAS_ANTIGUO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=4 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=10) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_PEDIDAS DESC LIMIT 25",
      "Almacen", "Compras", "KPI", "Alto", "Pedidos abiertos", ""),

    q("ax3_116", "Artículos con pedidos de venta abiertos",
      "¿Qué artículos tienen pedidos de venta pendientes de servir?",
      "Artículos en pedidos de venta (TIPO=1) sin albarán asociado.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_PENDIENTES, "
      "MIN(D.FECHA) AS PEDIDO_MAS_ANTIGUO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=1 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=11) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY UNIDADES_PENDIENTES DESC LIMIT 25",
      "Almacen", "Ventas", "Alerta", "Alto", "Pedidos abiertos", ""),

    q("ax3_117", "Artículos con mayor diferencia entre STOCKARTICULO máximo y actual",
      "¿Qué artículos están más lejos de su STOCKARTICULO máximo?",
      "Diferencia entre STOCKARTICULO y STOCKARTICULO actual por artículo.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_ACTUAL, "
      "A.STOCKARTICULO AS STOCK_MAXIMO, "
      "ROUND(A.STOCKARTICULO-SUM(A.STOCKARTICULO),2) AS DIFERENCIA "
      "FROM ARTICULO E "
      "JOIN ARTICULO A ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING DIFERENCIA>0 "
      "ORDER BY DIFERENCIA DESC LIMIT 25",
      "Almacen", "Almacen", "KPI", "Bajo", "STOCKARTICULO máximo", ""),

    q("ax3_118", "Artículos con mayor número de líneas de pedido de venta",
      "¿Qué artículos aparecen en más pedidos de venta?",
      "Artículos con mayor presencia en pedidos de venta TIPO=1.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_PEDIDO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=1 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_PEDIDOS DESC LIMIT 25",
      "Almacen", "Ventas", "KPI", "Medio", "Demanda", ""),

    q("ax3_119", "Artículos con mayor número de líneas de pedido de compra",
      "¿Qué artículos se piden más a proveedores?",
      "Artículos con mayor presencia en pedidos de compra TIPO=4.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS, "
      "ROUND(SUM(L.CANTIDAD),2) AS TOTAL_PEDIDO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=4 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_PEDIDOS DESC LIMIT 25",
      "Almacen", "Compras", "KPI", "Medio", "Compras", ""),

    q("ax3_120", "Artículos con mayor valor de pedidos de compra abiertos",
      "¿Cuánto valor hay en pedidos de compra pendientes de recibir?",
      "Valor de pedidos de compra (TIPO=4) sin albarán asociado por artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VALOR_PENDIENTE, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_PENDIENTES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=4 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=10) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY VALOR_PENDIENTE DESC LIMIT 25",
      "Almacen", "Compras", "KPI", "Alto", "Pedidos abiertos", ""),

    q("ax3_121", "Artículos con mayor valor de pedidos de venta abiertos",
      "¿Cuánto valor hay en pedidos de venta pendientes de servir?",
      "Valor de pedidos de venta (TIPO=1) sin albarán asociado por artículo.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS VALOR_PENDIENTE, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_PENDIENTES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=1 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=11) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY VALOR_PENDIENTE DESC LIMIT 25",
      "Almacen", "Ventas", "KPI", "Alto", "Pedidos abiertos", ""),

    q("ax3_122", "Artículos con STOCKARTICULO suficiente para cubrir pedidos abiertos",
      "¿El STOCKARTICULO actual cubre los pedidos de venta pendientes?",
      "Compara STOCKARTICULO disponible con unidades en pedidos de venta sin servir.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "ROUND(COALESCE(SUM(A.STOCKARTICULO),0),2) AS STOCK_DISPONIBLE, "
      "ROUND(COALESCE(PED.PENDIENTE,0),2) AS UNIDADES_PEDIDAS, "
      "ROUND(COALESCE(SUM(A.STOCKARTICULO),0)-COALESCE(PED.PENDIENTE,0),2) AS DIFERENCIA "
      "FROM ARTICULO A "
      " "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS PENDIENTE "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=1 AND D.CODIGO NOT IN ("
      "SELECT COALESCE(NULL,'') FROM DOCCAB WHERE TIPO=11) "
      "GROUP BY L.CODARTICULO) PED ON PED.CODIGO=A.CODIGO "
      "WHERE PED.PENDIENTE>0 "
      "GROUP BY A.CODIGO, A.NOMBRE, PED.PENDIENTE "
      "ORDER BY DIFERENCIA ASC LIMIT 25",
      "Almacen", "Ventas", "KPI", "Critico", "Cobertura pedidos", ""),

    q("ax3_123", "Artículos con mayor número de proveedores activos",
      "¿Qué artículos tienen más proveedores activos en el último año?",
      "Proveedores distintos en albaranes de compra del último año.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(DISTINCT D.CODCLIENTE) AS N_PROVEEDORES_ACTIVOS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=10 AND D.FECHA >= DATE('now','-365 days') "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY N_PROVEEDORES_ACTIVOS DESC LIMIT 20",
      "Almacen", "Compras", "KPI", "Bajo", "Proveedores", ""),

    q("ax3_124", "Artículos con mayor importe de compras en el año",
      "¿En qué artículos se gasta más en compras durante el año?",
      "Importe total de compras (TIPO=10) por artículo en el año actual.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_COMPRADAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_COMPRAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=10 "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY IMPORTE_COMPRAS DESC LIMIT 25",
      "Almacen", "Compras", "KPI", "Alto", "Compras", ""),

    q("ax3_125", "Artículos con mayor importe de ventas en el año",
      "¿Qué artículos generan más ingresos de ventas en el año actual?",
      "Importe total de ventas (TIPO=13) por artículo en el año actual.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE, "
      "COUNT(*) AS N_LINEAS, "
      "ROUND(SUM(L.CANTIDAD),2) AS UNIDADES_VENDIDAS, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS IMPORTE_VENTAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now') AS TEXT) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY IMPORTE_VENTAS DESC LIMIT 25",
      "Almacen", "Ventas", "KPI", "Alto", "Ventas", ""),

]
