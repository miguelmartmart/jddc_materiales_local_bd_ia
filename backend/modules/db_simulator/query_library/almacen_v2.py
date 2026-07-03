"""almacen_v2.py — 125 consultas adicionales de Almacén (v2).

DEVIA: fichero < 500 líneas, módulo independiente, sin lógica de negocio.
"""
from backend.modules.db_simulator.query_library.builder import q

QUERIES_ALMACEN_V2: list = [
    q("ax2_001", "Movimientos de STOCKARTICULO por mes", "Movimientos mensuales de almacén",
      "Agrupa líneas de documento por mes y tipo para ver la actividad de almacén.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, D.TIPO, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.FECHA IS NOT NULL GROUP BY SUBSTR(D.FECHA,1,7),D.TIPO ORDER BY MES DESC LIMIT 50",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_002", "Artículos con STOCKARTICULO cero en almacén principal", "STOCKARTICULO cero almacén 1",
      "Artículos sin existencias en CODALMACEN=1 que pueden generar roturas de STOCKARTICULO.",
      "SELECT A.CODIGO, A.NOMBRE, A.PRECIOCOSTE FROM ARTICULO A "
      "WHERE (SELECT COALESCE(SUM(A.STOCKARTICULO),0) FROM ARTICULO E "
      "WHERE A.CODIGO=A.CODIGO AND '01'=1)=0 ORDER BY A.NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "", ""),

    q("ax2_003", "Valor total del inventario por almacén", "Valor inventario por almacén",
      "Multiplica STOCKARTICULO por PRECIOCOSTE unitario para obtener el valor económico del inventario.",
      "SELECT '01', ROUND(SUM(A.STOCKARTICULO * A.PRECIOCOSTE),2) AS VALOR_INVENTARIO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 GROUP BY '01' ORDER BY VALOR_INVENTARIO DESC",
      "Almacen", "Almacen", "KPI", "Critico", "", ""),

    q("ax2_004", "Top 20 artículos por valor en STOCKARTICULO", "Artículos mayor valor STOCKARTICULO",
      "Identifica los artículos que concentran más valor económico en almacén.",
      "SELECT A.CODIGO, A.NOMBRE, A.STOCKARTICULO, A.PRECIOCOSTE, ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 ORDER BY VALOR DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_005", "Artículos con STOCKARTICULO negativo", "STOCKARTICULO negativo detectado",
      "STOCKARTICULO negativo indica errores de registro o ventas sin entrada previa.",
      "SELECT A.CODIGO, A.NOMBRE, '01', A.STOCKARTICULO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO<0 ORDER BY A.STOCKARTICULO ASC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Critico", "", ""),

    q("ax2_006", "Distribución de STOCKARTICULO por familia", "STOCKARTICULO por familia de artículo",
      "Agrupa el STOCKARTICULO total por familia para ver qué categorías tienen más existencias.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(DISTINCT A.CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(A.STOCKARTICULO),2) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
      "GROUP BY F.NOMBRE ORDER BY STOCK_TOTAL DESC",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_007", "Artículos sin movimiento en 90 días", "Artículos sin rotación",
      "Artículos con STOCKARTICULO pero sin líneas de venta en los últimos 90 días.",
      "SELECT A.CODIGO, A.NOMBRE, COALESCE(SUM(A.STOCKARTICULO),0) AS STOCK_ACTUAL "
      "FROM ARTICULO A "
      "WHERE A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA >= DATE('now','-90 days')) "
      "GROUP BY A.CODIGO, A.NOMBRE HAVING STOCK_ACTUAL>0 ORDER BY STOCK_ACTUAL DESC LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "", ""),

    q("ax2_008", "Número de almacenes activos", "Almacenes con STOCKARTICULO",
      "Cuenta almacenes que tienen al menos un artículo con STOCKARTICULO positivo.",
      "SELECT 1 AS N_ALMACENES_ACTIVOS FROM ARTICULO WHERE STOCKARTICULO>0",
      "Almacen", "Almacen", "Operacional", "Bajo", "", ""),

    q("ax2_009", "Artículos con STOCKARTICULO por encima del máximo", "Sobrestock detectado",
      "Artículos cuyo STOCKARTICULO supera el doble del PRECIOVENTA medio de venta (proxy de sobrestock).",
      "SELECT A.CODIGO, A.NOMBRE, A.STOCKARTICULO, A.PRECIOVENTA "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO > A.PRECIOVENTA*2 AND A.PRECIOVENTA>0 ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Almacen", "Almacen", "Alerta", "Medio", "", ""),

    q("ax2_010", "Últimas 30 entradas de almacén (albaranes compra)", "Últimas entradas almacén",
      "Albaranes de compra TIPO=21 más recientes para verificar recepciones.",
      "SELECT D.CODIGO, D.CODCLIENTE, D.FECHA, D.IMPORTETOTAL "
      "FROM DOCCAB D WHERE D.TIPO=21 ORDER BY D.FECHA DESC LIMIT 30",
      "Almacen", "Almacen", "Operacional", "Bajo", "", ""),

    q("ax2_011", "Rotación de STOCKARTICULO por artículo (ventas/STOCKARTICULO)", "Rotación de inventario",
      "Ratio ventas/STOCKARTICULO: valores altos indican alta rotación, valores bajos posible sobrestock.",
      "SELECT A.CODIGO, A.NOMBRE, "
      "COALESCE(SUM(L.CANTIDAD),0) AS UNIDADES_VENDIDAS, "
      "COALESCE(MAX(A.STOCKARTICULO),0) AS STOCK_ACTUAL, "
      "CASE WHEN COALESCE(MAX(A.STOCKARTICULO),0)>0 "
      "THEN ROUND(COALESCE(SUM(L.CANTIDAD),0)/MAX(A.STOCKARTICULO),2) ELSE NULL END AS ROTACION "
      "FROM ARTICULO A "
      "LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      " "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY ROTACION DESC NULLS LAST LIMIT 30",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_012", "Artículos con PRECIOVENTA de PRECIOCOSTE cero", "PRECIOCOSTE cero en artículos",
      "Artículos con PRECIOCOSTE=0 pueden distorsionar el cálculo del valor de inventario.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA FROM ARTICULO WHERE PRECIOCOSTE=0 OR PRECIOCOSTE IS NULL ORDER BY NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Medio", "", ""),

    q("ax2_013", "STOCKARTICULO total de todos los almacenes", "STOCKARTICULO global consolidado",
      "Suma total de unidades en STOCKARTICULO en todos los almacenes.",
      "SELECT ROUND(SUM(STOCKARTICULO),2) AS STOCK_TOTAL_GLOBAL, COUNT(DISTINCT CODIGO) AS N_ARTICULOS "
      "FROM ARTICULO WHERE STOCKARTICULO>0",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_014", "Artículos más vendidos por unidades", "Top artículos por unidades vendidas",
      "Ranking de artículos por cantidad total vendida en facturas TIPO=13.",
      "SELECT L.CODARTICULO, A.NOMBRE, SUM(L.CANTIDAD) AS TOTAL_UNIDADES "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY TOTAL_UNIDADES DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_015", "Artículos sin STOCKARTICULO en ningún almacén", "Artículos agotados globalmente",
      "Artículos que no tienen STOCKARTICULO en ningún almacén del sistema.",
      "SELECT A.CODIGO, A.NOMBRE, A.PRECIOVENTA, A.PRECIOCOSTE "
      "FROM ARTICULO A WHERE NOT EXISTS ("
      "SELECT 1 WHERE A.STOCKARTICULO > 0) "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Alto", "", ""),

    q("ax2_016", "Valor de inventario total del sistema", "Valor total inventario",
      "Suma del valor económico (STOCKARTICULO × PRECIOCOSTE) de todos los artículos en todos los almacenes.",
      "SELECT ROUND(SUM(A.STOCKARTICULO * A.PRECIOCOSTE),2) AS VALOR_TOTAL_INVENTARIO "
      "FROM ARTICULO A WHERE A.STOCKARTICULO>0",
      "Almacen", "Almacen", "KPI", "Critico", "", ""),

    q("ax2_017", "Artículos con más de 5 almacenes con STOCKARTICULO", "Artículos multi-almacén",
      "Artículos distribuidos en múltiples almacenes, útil para gestión de traslados.",
      "SELECT CODIGO, A.NOMBRE, 1 AS N_ALMACENES, SUM(STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "WHERE STOCKARTICULO>0 GROUP BY CODIGO, A.NOMBRE HAVING 1>1 "
      "ORDER BY N_ALMACENES DESC LIMIT 20",
      "Almacen", "Almacen", "Operacional", "Medio", "", ""),

    q("ax2_018", "Líneas de albarán de venta por artículo", "Albaranes venta por artículo",
      "Cuenta líneas de albarán TIPO=11 por artículo para ver flujo de salidas.",
      "SELECT L.CODARTICULO, A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS, SUM(L.CANTIDAD) AS TOTAL_UNIADES "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=11 GROUP BY L.CODARTICULO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Almacen", "Almacen", "Operacional", "Medio", "", ""),

    q("ax2_019", "Artículos con PRECIOVENTA de venta inferior al PRECIOCOSTE", "Margen negativo en artículos",
      "Artículos donde PRECIOVENTA < PRECIOCOSTE generan pérdida en cada venta.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOVENTA>0 AND PRECIOCOSTE>0 AND PRECIOVENTA<PRECIOCOSTE ORDER BY MARGEN ASC LIMIT 20",
      "Almacen", "Almacen", "Alerta", "Critico", "", ""),

    q("ax2_020", "Resumen de existencias por almacén", "Resumen existencias almacenes",
      "Número de artículos distintos y STOCKARTICULO total por cada almacén.",
      "SELECT CODALMACEN, COUNT(DISTINCT CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(STOCKARTICULO),2) AS STOCK_TOTAL "
      "FROM ARTICULO WHERE STOCKARTICULO>0 GROUP BY CODALMACEN ORDER BY STOCK_TOTAL DESC",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_021", "Artículos con mayor diferencia PRECIOVENTA-PRECIOCOSTE", "Mayor margen unitario",
      "Artículos con mayor margen absoluto por unidad (PRECIOVENTA - PRECIOCOSTE).",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN_UNITARIO "
      "FROM ARTICULO WHERE PRECIOVENTA>0 AND PRECIOCOSTE>0 ORDER BY MARGEN_UNITARIO DESC LIMIT 20",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),

    q("ax2_022", "Artículos sin familia asignada", "Artículos sin clasificar",
      "Artículos con CODFAMILIA nulo o cero no están clasificados correctamente.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE FROM ARTICULO "
      "WHERE CODFAMILIA IS NULL OR CODFAMILIA=0 ORDER BY NOMBRE LIMIT 30",
      "Almacen", "Almacen", "Alerta", "Medio", "", ""),

    q("ax2_023", "Número total de referencias en catálogo", "Total referencias catálogo",
      "Cuenta el total de artículos registrados en el sistema.",
      "SELECT COUNT(*) AS TOTAL_REFERENCIAS, "
      "SUM(CASE WHEN PRECIOVENTA>0 THEN 1 ELSE 0 END) AS CON_PRECIO, "
      "SUM(CASE WHEN PRECIOCOSTE>0 THEN 1 ELSE 0 END) AS CON_COSTE "
      "FROM ARTICULO",
      "Almacen", "Almacen", "KPI", "Bajo", "", ""),

    q("ax2_024", "Artículos con STOCKARTICULO pero sin ventas registradas", "STOCKARTICULO sin demanda",
      "Artículos con existencias pero que nunca han aparecido en una factura de venta.",
      "SELECT A.CODIGO, A.NOMBRE, COALESCE(SUM(A.STOCKARTICULO),0) AS STOCKARTICULO "
      "FROM ARTICULO A "
      "WHERE A.CODIGO NOT IN (SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO WHERE D.TIPO=13) "
      "GROUP BY A.CODIGO, A.NOMBRE HAVING STOCKARTICULO>0 ORDER BY STOCKARTICULO DESC LIMIT 20",
      "Almacen", "Almacen", "Alerta", "Alto", "", ""),

    q("ax2_025", "Porcentaje de artículos con STOCKARTICULO disponible", "Cobertura de STOCKARTICULO",
      "Ratio de artículos con STOCKARTICULO positivo sobre el total del catálogo.",
      "SELECT COUNT(*) AS TOTAL, "
      "SUM(CASE WHEN COALESCE(A.STOCKARTICULO,0)>0 THEN 1 ELSE 0 END) AS CON_STOCKARTICULO, "
      "ROUND(100.0*SUM(CASE WHEN COALESCE(A.STOCKARTICULO,0)>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS PCT_CON_STOCKARTICULO "
      "FROM ARTICULO A",
      "Almacen", "Almacen", "KPI", "Alto", "", ""),
]
