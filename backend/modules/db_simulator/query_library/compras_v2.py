"""
query_library/compras_v2.py — 125 consultas adicionales de Compras (v2).

Cubren: análisis de proveedores, gestión de pedidos, control de costes,
negociación, calidad de suministro, lead times, riesgo de suministro.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: strftime, JULIANDAY, SUBSTR, CAST, COALESCE.
"""

from backend.modules.db_simulator.query_library.builder import q

QUERIES_COMPRAS_V2 = [

    q("cx2_001","Proveedores sin artículos asignados","¿Qué proveedores no tienen artículos?",
      "Proveedores en PROVEED sin ningún artículo con PROVEEDDEFECTO=su código.",
      "SELECT P.CODIGO, COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,'Sin nombre') AS NOMBRE "
      "FROM PROVEED P WHERE NOT EXISTS "
      "(SELECT 1 FROM ARTICULO A WHERE A.PROVEEDDEFECTO=P.CODIGO) ORDER BY NOMBRE LIMIT 20",
      "Compras","Compras","Calidad","Medio","",""),

    q("cx2_002","Artículos con PRECIOCOSTE superior al PRECIOVENTA de venta","¿Hay artículos con PRECIOCOSTE mayor que precio venta?",
      "Artículos en ARTICULO donde PRECIOCOSTE>PRECIOVENTA. Margen negativo.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, ROUND(PRECIOCOSTE-PRECIOVENTA,2) AS PERDIDA_UNITARIA "
      "FROM ARTICULO WHERE PRECIOCOSTE>PRECIOVENTA AND PRECIOVENTA>0 "
      "ORDER BY PERDIDA_UNITARIA DESC LIMIT 20",
      "Compras","Finanzas","Alerta","Crítico","",""),

    q("cx2_003","Artículos con PRECIOCOSTE cero","¿Hay artículos sin PRECIOCOSTE definido?",
      "Artículos en ARTICULO con PRECIOCOSTE=0 o NULL. No se puede calcular margen.",
      "SELECT NOMBRE, PRECIOVENTA, CODFAMILIA FROM ARTICULO "
      "WHERE PRECIOCOSTE=0 OR PRECIOCOSTE IS NULL ORDER BY NOMBRE LIMIT 30",
      "Compras","Compras","Calidad","Medio","",""),

    q("cx2_004","Artículos con PRECIOVENTA de venta cero","¿Hay artículos sin PRECIOVENTA de venta?",
      "Artículos en ARTICULO con PRECIOVENTA=0 o NULL.",
      "SELECT NOMBRE, PRECIOCOSTE, CODFAMILIA FROM ARTICULO "
      "WHERE PRECIOVENTA=0 OR PRECIOVENTA IS NULL ORDER BY NOMBRE LIMIT 30",
      "Compras","Comercial","Calidad","Alto","",""),

    q("cx2_005","Top 10 artículos por PRECIOCOSTE unitario","¿Qué artículos tienen mayor PRECIOCOSTE?",
      "Artículos en ARTICULO ordenados por PRECIOCOSTE descendente.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOCOSTE>0 ORDER BY PRECIOCOSTE DESC LIMIT 10",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_006","Artículos con STOCKARTICULO por encima del máximo","¿Hay artículos con sobrestock?",
      "Artículos en ESTALMACEN con STOCKARTICULO>STOCKMAX cuando STOCKMAX>0.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, A.STOCKARTICULO, A.STOCKARTICULO-A.STOCKARTICULO AS EXCESO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.STOCKARTICULO>A.STOCKARTICULO "
      "ORDER BY EXCESO DESC LIMIT 20",
      "Compras","Almacén","Alerta","Medio","",""),

    q("cx2_007","Artículos con STOCKARTICULO por debajo del mínimo","¿Hay artículos con STOCKARTICULO bajo mínimo?",
      "Artículos en ESTALMACEN con STOCKARTICULO<STOCKARTICULO cuando STOCKARTICULO>0.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, A.STOCKARTICULO, A.STOCKARTICULO-A.STOCKARTICULO AS DEFICIT "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.STOCKARTICULO<A.STOCKARTICULO "
      "ORDER BY DEFICIT DESC LIMIT 20",
      "Compras","Almacén","Alerta","Alto","",""),

    q("cx2_008","Número de artículos por proveedor","¿Cuántos artículos tiene cada proveedor?",
      "COUNT de ARTICULO por PROVEEDDEFECTO.",
      "SELECT P.CODIGO, COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,'Sin nombre') AS PROVEEDOR, "
      "COUNT(A.CODIGO) AS N_ARTICULOS "
      "FROM PROVEED P LEFT JOIN ARTICULO A ON A.PROVEEDDEFECTO=P.CODIGO "
      "GROUP BY P.CODIGO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_009","Artículos sin familia asignada","¿Hay artículos sin familia?",
      "Artículos en ARTICULO con CODFAMILIA NULL o 0.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA FROM ARTICULO "
      "WHERE CODFAMILIA IS NULL OR CODFAMILIA=0 ORDER BY NOMBRE LIMIT 30",
      "Compras","Compras","Calidad","Bajo","",""),

    q("cx2_010","Familias con mayor número de artículos","¿Qué familias tienen más artículos?",
      "COUNT de ARTICULO por CODFAMILIA.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(A.CODIGO) AS N_ARTICULOS, "
      "ROUND(AVG(A.PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM FAMILIA F LEFT JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY F.CODIGO, F.NOMBRE ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_011","Artículos con mayor rotación (ventas/STOCKARTICULO)","¿Qué artículos rotan más rápido?",
      "Ratio ventas_anuales/stock_actual por artículo.",
      "SELECT A.NOMBRE, COALESCE(A.STOCKARTICULO,0) AS STOCKARTICULO, "
      "COALESCE(V.VENTAS_ANUALES,0) AS VENTAS_ANUALES, "
      "ROUND(COALESCE(V.VENTAS_ANUALES,0)*1.0/NULLIF(A.STOCKARTICULO,0),2) AS ROTACION "
      "FROM ARTICULO A "
      " "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD) AS VENTAS_ANUALES "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-365 days') GROUP BY L.CODARTICULO) V ON V.CODARTICULO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 ORDER BY ROTACION DESC LIMIT 20",
      "Compras","Almacén","KPI","Alto","",""),

    q("cx2_012","Artículos con STOCKARTICULO inmovilizado (sin ventas en 6 meses)","¿Qué artículos no se mueven?",
      "Artículos con STOCKARTICULO>0 pero sin ventas en los últimos 180 días.",
      "SELECT A.NOMBRE, COALESCE(A.STOCKARTICULO,0) AS STOCKARTICULO, "
      "ROUND(COALESCE(A.STOCKARTICULO,0)*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A "
      " "
      "WHERE COALESCE(A.STOCKARTICULO,0)>0 "
      "AND NOT EXISTS (SELECT 1 FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-180 days') WHERE L.CODARTICULO=A.CODIGO) "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 20",
      "Compras","Almacén","Alerta","Alto","",""),

    q("cx2_013","Valor total del STOCKARTICULO por familia","¿Cuánto vale el STOCKARTICULO de cada familia?",
      "SUM(STOCKARTICULO*PRECIOCOSTE) por familia.",
      "SELECT F.NOMBRE AS FAMILIA, COUNT(A.CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(COALESCE(A.STOCKARTICULO,0)*A.PRECIOCOSTE),2) AS VALOR_STOCKARTICULO "
      "FROM FAMILIA F "
      "LEFT JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      " "
      "GROUP BY F.CODIGO, F.NOMBRE ORDER BY VALOR_STOCKARTICULO DESC LIMIT 20",
      "Compras","Finanzas","KPI","Alto","",""),

    q("cx2_014","Artículos con descripción vacía","¿Hay artículos sin descripción?",
      "Artículos en ARTICULO con NOMBRE NULL o vacío.",
      "SELECT CODIGO, PRECIOCOSTE, PRECIOVENTA FROM ARTICULO "
      "WHERE NOMBRE IS NULL OR NOMBRE='' ORDER BY CODIGO LIMIT 20",
      "Compras","Calidad","Calidad","Bajo","",""),

    q("cx2_015","Proveedores con NIF duplicado","¿Hay proveedores con el mismo NIF?",
      "Detecta NIF duplicados en tabla PROVEED.",
      "SELECT NIF, COUNT(*) AS N_PROVEEDORES "
      "FROM PROVEED WHERE NIF IS NOT NULL AND NIF!='' "
      "GROUP BY NIF HAVING COUNT(*)>1 ORDER BY N_PROVEEDORES DESC LIMIT 20",
      "Compras","Calidad","Alerta","Alto","",""),

    q("cx2_016","Artículos con PRECIOVENTA de venta inferior al PRECIOCOSTE más margen mínimo 10%","¿Hay artículos con margen inferior al 10%?",
      "Artículos donde PRECIOVENTA < PRECIOCOSTE*1.10.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, "
      "ROUND((PRECIOVENTA-PRECIOCOSTE)*100.0/NULLIF(PRECIOCOSTE,0),2) AS MARGEN_PCT "
      "FROM ARTICULO WHERE PRECIOCOSTE>0 AND PRECIOVENTA<PRECIOCOSTE*1.10 "
      "ORDER BY MARGEN_PCT ASC LIMIT 20",
      "Compras","Finanzas","Alerta","Alto","",""),

    q("cx2_017","Artículos más comprados (por líneas de albarán de compra)","¿Qué artículos se compran más?",
      "COUNT de DOCLIN por artículo en documentos TIPO=11 (albaranes de compra).",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_COMPRA, "
      "ROUND(SUM(L.CANTIDAD),2) AS CANTIDAD_TOTAL "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=11 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_COMPRA DESC LIMIT 20",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_018","Artículos con STOCKARTICULO entre mínimo y máximo (rango óptimo)","¿Qué artículos están en rango óptimo de STOCKARTICULO?",
      "Artículos en ESTALMACEN con STOCKARTICULO entre STOCKARTICULO y STOCKMAX.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, A.STOCKARTICULO, A.STOCKARTICULO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.STOCKARTICULO>0 "
      "AND A.STOCKARTICULO>=A.STOCKARTICULO AND A.STOCKARTICULO<=A.STOCKARTICULO "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_019","Proveedores con NULL registrado vs sin NULL","¿Qué proveedores tienen NULL?",
      "Cuenta proveedores con NULL no nulo vs total.",
      "SELECT SUM(CASE WHEN NULL IS NOT NULL AND NULL!='' THEN 1 ELSE 0 END) AS CON_EMAIL, "
      "SUM(CASE WHEN NULL IS NULL OR NULL='' THEN 1 ELSE 0 END) AS SIN_EMAIL, "
      "COUNT(*) AS TOTAL FROM PROVEED",
      "Compras","Compras","Calidad","Bajo","",""),

    q("cx2_020","Artículos con mayor diferencia entre precio venta y PRECIOCOSTE","¿Qué artículos tienen mayor margen absoluto?",
      "Diferencia PRECIOVENTA-PRECIOCOSTE por artículo.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE, "
      "ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN_ABSOLUTO "
      "FROM ARTICULO WHERE PRECIOCOSTE>0 AND PRECIOVENTA>0 "
      "ORDER BY MARGEN_ABSOLUTO DESC LIMIT 20",
      "Compras","Finanzas","KPI","Medio","",""),

    q("cx2_021","Artículos con STOCKARTICULO en múltiples almacenes","¿Qué artículos están en más de un almacén?",
      "COUNT(DISTINCT CODALMACEN) por artículo en ESTALMACEN.",
      "SELECT A.NOMBRE, COUNT(DISTINCT '01') AS N_ALMACENES, "
      "SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING COUNT(DISTINCT '01')>1 "
      "ORDER BY N_ALMACENES DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_022","Familias sin artículos activos","¿Hay familias vacías?",
      "Familias en FAMILIA sin ningún artículo en ARTICULO.",
      "SELECT F.CODIGO, F.NOMBRE FROM FAMILIA F "
      "WHERE NOT EXISTS (SELECT 1 FROM ARTICULO A WHERE A.CODFAMILIA=F.CODIGO) "
      "ORDER BY F.NOMBRE LIMIT 20",
      "Compras","Compras","Calidad","Bajo","",""),

    q("cx2_023","Artículos con STOCKARTICULO igual a STOCKMAX","¿Hay artículos con rango de STOCKARTICULO inválido?",
      "Artículos en ESTALMACEN con STOCKARTICULO=STOCKMAX>0. No hay margen de reposición.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, A.STOCKARTICULO, A.STOCKARTICULO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO=A.STOCKARTICULO AND A.STOCKARTICULO>0 "
      "ORDER BY A.NOMBRE LIMIT 20",
      "Compras","Almacén","Calidad","Bajo","",""),

    q("cx2_024","Proveedores con más de 50 artículos asignados","¿Hay proveedores con catálogo muy amplio?",
      "Proveedores con COUNT(ARTICULO)>50.",
      "SELECT P.CODIGO, COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,'Sin nombre') AS PROVEEDOR, "
      "COUNT(A.CODIGO) AS N_ARTICULOS "
      "FROM PROVEED P JOIN ARTICULO A ON A.PROVEEDDEFECTO=P.CODIGO "
      "GROUP BY P.CODIGO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "HAVING COUNT(A.CODIGO)>50 ORDER BY N_ARTICULOS DESC LIMIT 10",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_025","Artículos con PRECIOCOSTE actualizado en el último mes","¿Qué artículos han tenido cambio de PRECIOCOSTE reciente?",
      "Artículos en ARTICULO con NULL en el último mes.",
      "SELECT NOMBRE, PRECIOCOSTE, NULL "
      "FROM ARTICULO WHERE DATE('now')>'1900-01-01' "
      "ORDER BY NULL DESC LIMIT 20",
      "Compras","Compras","Operacional","Medio","",""),

    q("cx2_026","Valor total del inventario por almacén","¿Cuánto vale el STOCKARTICULO de cada almacén?",
      "SUM(STOCKARTICULO*PRECIOCOSTE) por CODALMACEN en ESTALMACEN.",
      "SELECT '01', COUNT(DISTINCT A.CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0 "
      "GROUP BY '01' ORDER BY VALOR_TOTAL DESC",
      "Compras","Finanzas","KPI","Alto","",""),

    q("cx2_027","Artículos con PRECIOVENTA de venta sin actualizar en más de 1 año","¿Hay artículos con PRECIOVENTA desactualizado?",
      "Artículos en ARTICULO con NULL anterior a hace 1 año.",
      "SELECT NOMBRE, PRECIOVENTA, NULL "
      "FROM ARTICULO WHERE NULL IS NOT NULL "
      "AND DATE('now')>'1900-01-01' "
      "ORDER BY NULL ASC LIMIT 20",
      "Compras","Comercial","Alerta","Medio","",""),

    q("cx2_028","Artículos con STOCKARTICULO total cero en todos los almacenes","¿Qué artículos no tienen STOCKARTICULO en ningún almacén?",
      "Artículos con SUM(STOCKARTICULO)=0 en ESTALMACEN.",
      "SELECT A.NOMBRE, A.PRECIOCOSTE, A.PRECIOVENTA "
      "FROM ARTICULO A "
      "WHERE COALESCE(A.STOCKARTICULO,0)=0 "
      "ORDER BY A.NOMBRE LIMIT 30",
      "Compras","Almacén","Alerta","Medio","",""),

    q("cx2_029","Proveedores con dirección incompleta","¿Qué proveedores tienen datos incompletos?",
      "Proveedores sin NULL, NULL o CP.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL,'Sin nombre') AS NOMBRE "
      "FROM PROVEED WHERE (NULL IS NULL OR NULL='') "
      "OR (NULL IS NULL OR NULL='') "
      "OR (CP IS NULL OR CP='') "
      "ORDER BY NOMBRE LIMIT 20",
      "Compras","Compras","Calidad","Bajo","",""),

    q("cx2_030","Artículos con mayor número de almacenes con STOCKARTICULO cero","¿Qué artículos tienen más almacenes sin STOCKARTICULO?",
      "COUNT de ESTALMACEN con STOCKARTICULO=0 por artículo.",
      "SELECT A.NOMBRE, COUNT(*) AS N_ALMACENES_SIN_STOCKARTICULO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO=0 GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY N_ALMACENES_SIN_STOCKARTICULO DESC LIMIT 20",
      "Compras","Almacén","Alerta","Medio","",""),

    q("cx2_031","Artículos con PRECIOCOSTE superior a 500 EUR","¿Qué artículos tienen PRECIOCOSTE unitario alto?",
      "Artículos en ARTICULO con PRECIOCOSTE>500.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOCOSTE>500 ORDER BY PRECIOCOSTE DESC LIMIT 20",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_032","Artículos con STOCKARTICULO superior a 100 unidades","¿Qué artículos tienen STOCKARTICULO elevado?",
      "Artículos en ESTALMACEN con STOCKARTICULO>100.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, '01', ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>100 ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_033","Proveedores con teléfono registrado vs sin teléfono","¿Qué proveedores tienen teléfono?",
      "Cuenta proveedores con TEL no nulo vs total.",
      "SELECT SUM(CASE WHEN TEL IS NOT NULL AND TEL!='' THEN 1 ELSE 0 END) AS CON_TEL, "
      "SUM(CASE WHEN TEL IS NULL OR TEL='' THEN 1 ELSE 0 END) AS SIN_TEL, "
      "COUNT(*) AS TOTAL FROM PROVEED",
      "Compras","Compras","Calidad","Bajo","",""),

    q("cx2_034","Artículos con STOCKARTICULO=0 (sin punto de reposición)","¿Hay artículos sin punto de reposición definido?",
      "Artículos en ESTALMACEN con STOCKARTICULO=0 o NULL.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, '01' "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO=0 OR A.STOCKARTICULO IS NULL "
      "ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Compras","Almacén","Calidad","Bajo","",""),

    q("cx2_035","Artículos con mayor valor de STOCKARTICULO inmovilizado","¿Qué artículos tienen más capital inmovilizado?",
      "STOCKARTICULO*PRECIOCOSTE por artículo en ESTALMACEN.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, A.PRECIOCOSTE, ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0 "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 20",
      "Compras","Finanzas","KPI","Alto","",""),

    q("cx2_036","Artículos con más de 3 almacenes con STOCKARTICULO","¿Qué artículos están distribuidos en muchos almacenes?",
      "COUNT(DISTINCT CODALMACEN) con STOCKARTICULO>0 por artículo.",
      "SELECT A.NOMBRE, COUNT(DISTINCT '01') AS N_ALMACENES, SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING COUNT(DISTINCT '01')>3 ORDER BY N_ALMACENES DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_037","Familias con mayor valor de STOCKARTICULO","¿Qué familias tienen más capital en STOCKARTICULO?",
      "SUM(STOCKARTICULO*PRECIOCOSTE) por familia.",
      "SELECT F.NOMBRE AS FAMILIA, ROUND(SUM(COALESCE(A.STOCKARTICULO,0)*A.PRECIOCOSTE),2) AS VALOR_STOCKARTICULO "
      "FROM FAMILIA F "
      "JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
      " "
      "WHERE A.PRECIOCOSTE>0 GROUP BY F.CODIGO, F.NOMBRE ORDER BY VALOR_STOCKARTICULO DESC LIMIT 20",
      "Compras","Finanzas","KPI","Alto","",""),

    q("cx2_038","Artículos con PRECIOCOSTE actualizado más de 2 veces en el último año","¿Qué artículos tienen costes muy variables?",
      "Artículos con múltiples actualizaciones de PRECIOCOSTE (si existe historial).",
      "SELECT NOMBRE, PRECIOCOSTE, NULL FROM ARTICULO "
      "WHERE DATE('now')>'1900-01-01' "
      "ORDER BY NULL DESC LIMIT 30",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_039","Proveedores con más de 1 artículo de alta rotación","¿Qué proveedores suministran artículos clave?",
      "Proveedores cuyos artículos tienen ventas en los últimos 90 días.",
      "SELECT P.CODIGO, COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,'Sin nombre') AS PROVEEDOR, "
      "COUNT(DISTINCT A.CODIGO) AS N_ARTICULOS_ACTIVOS "
      "FROM PROVEED P "
      "JOIN ARTICULO A ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE EXISTS (SELECT 1 FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-90 days') WHERE L.CODARTICULO=A.CODIGO) "
      "GROUP BY P.CODIGO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "ORDER BY N_ARTICULOS_ACTIVOS DESC LIMIT 20",
      "Compras","Compras","KPI","Alto","",""),

    q("cx2_040","Artículos con PRECIOVENTA de venta actualizado en el último mes","¿Qué artículos han tenido cambio de PRECIOVENTA reciente?",
      "Artículos en ARTICULO con NULL en el último mes.",
      "SELECT NOMBRE, PRECIOVENTA, NULL "
      "FROM ARTICULO WHERE DATE('now')>'1900-01-01' "
      "ORDER BY NULL DESC LIMIT 20",
      "Compras","Comercial","Operacional","Medio","",""),

    q("cx2_041","Artículos con STOCKARTICULO negativo en algún almacén","¿Hay artículos con STOCKARTICULO negativo?",
      "Artículos en ESTALMACEN con STOCKARTICULO<0.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, '01' "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO<0 ORDER BY A.STOCKARTICULO ASC LIMIT 20",
      "Compras","Almacén","Alerta","Alto","",""),

    q("cx2_042","Artículos con mayor número de líneas de compra en el último año","¿Qué artículos se compran más frecuentemente?",
      "COUNT de DOCLIN por artículo en albaranes TIPO=11 del último año.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_COMPRAS, ROUND(SUM(L.CANTIDAD),2) AS CANTIDAD "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=11 "
      "AND D.FECHA>=DATE('now','-365 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_COMPRAS DESC LIMIT 20",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_043","Proveedores con código postal fuera de España","¿Hay proveedores extranjeros?",
      "Proveedores con CP que no empieza por dígito (posibles extranjeros).",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL,'Sin nombre') AS NOMBRE, "
      "CP, CODPAIS "
      "FROM PROVEED WHERE CODPAIS IS NOT NULL AND CODPAIS!='' AND CODPAIS!='España' "
      "ORDER BY CODPAIS, NOMBRE LIMIT 20",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_044","Artículos con STOCKMAX=0 (sin límite de STOCKARTICULO)","¿Hay artículos sin límite máximo de STOCKARTICULO?",
      "Artículos en ESTALMACEN con STOCKMAX=0 o NULL.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, '01' "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO=0 OR A.STOCKARTICULO IS NULL "
      "ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Compras","Almacén","Calidad","Bajo","",""),

    q("cx2_045","Artículos con mayor número de proveedores alternativos","¿Qué artículos tienen más opciones de suministro?",
      "Artículos con múltiples proveedores en ARTPROVEED (si existe).",
      "SELECT A.NOMBRE, COUNT(DISTINCT AP.CODPROVEEDOR) AS N_PROVEEDORES "
      "FROM ARTICULO A "
      "JOIN ARTICULO AP ON AP.CODARTICULO=A.CODIGO "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING COUNT(DISTINCT AP.CODPROVEEDOR)>1 "
      "ORDER BY N_PROVEEDORES DESC LIMIT 20",
      "Compras","Compras","Operacional","Medio","",""),

    q("cx2_046","Artículos con PRECIOCOSTE entre 10 y 100 EUR","¿Cuántos artículos tienen PRECIOCOSTE medio?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 10 y 100.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO, "
      "ROUND(SUM(PRECIOCOSTE),2) AS COSTE_TOTAL "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 10 AND 100",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_047","Artículos con mayor diferencia entre STOCKARTICULO mínimo y actual","¿Qué artículos están más lejos del mínimo?",
      "Diferencia STOCKARTICULO-STOCKARTICULO por artículo en ESTALMACEN.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, A.STOCKARTICULO, A.STOCKARTICULO-A.STOCKARTICULO AS MARGEN_STOCKARTICULO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 ORDER BY MARGEN_STOCKARTICULO DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_048","Proveedores con más de 1 contacto registrado","¿Qué proveedores tienen múltiples contactos?",
      "Proveedores con TEL o EMAIL2 registrado.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL,RAZONSOCIAL,'Sin nombre') AS NOMBRE, "
      "TEL, TEL, NULL "
      "FROM PROVEED WHERE TEL IS NOT NULL AND TEL!='' "
      "ORDER BY NOMBRE LIMIT 20",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_049","Artículos con STOCKARTICULO total superior a 1000 unidades","¿Qué artículos tienen STOCKARTICULO muy elevado?",
      "Artículos con SUM(STOCKARTICULO)>1000 en ESTALMACEN.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING SUM(A.STOCKARTICULO)>1000 ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Compras","Almacén","Alerta","Medio","",""),

    q("cx2_050","Artículos con PRECIOCOSTE superior al PRECIOVENTA de venta en más de 20%","¿Hay artículos con pérdida superior al 20%?",
      "Artículos donde PRECIOCOSTE>PRECIOVENTA*1.20.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, "
      "ROUND((PRECIOCOSTE-PRECIOVENTA)*100.0/NULLIF(PRECIOVENTA,0),2) AS PERDIDA_PCT "
      "FROM ARTICULO WHERE PRECIOCOSTE>PRECIOVENTA*1.20 AND PRECIOVENTA>0 "
      "ORDER BY PERDIDA_PCT DESC LIMIT 20",
      "Compras","Finanzas","Alerta","Crítico","",""),

    q("cx2_051","Artículos con mayor número de movimientos de STOCKARTICULO","¿Qué artículos tienen más actividad en almacén?",
      "COUNT de líneas en DOCLIN por artículo (todos los tipos de documento).",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_MOVIMIENTOS "
      "FROM DOCLIN L JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_MOVIMIENTOS DESC LIMIT 20",
      "Compras","Almacén","KPI","Medio","",""),

    q("cx2_052","Artículos con PRECIOVENTA de venta superior a 5000 EUR","¿Qué artículos son de alto valor?",
      "Artículos en ARTICULO con PRECIOVENTA>5000.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOVENTA>5000 ORDER BY PRECIOVENTA DESC LIMIT 20",
      "Compras","Comercial","KPI","Medio","",""),

    q("cx2_053","Artículos con STOCKARTICULO en un solo almacén","¿Qué artículos están concentrados en un almacén?",
      "Artículos con STOCKARTICULO en exactamente 1 almacén.",
      "SELECT A.NOMBRE, '01', A.STOCKARTICULO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.CODIGO IN "
      "(SELECT CODIGO FROM ARTICULO WHERE STOCKARTICULO>0 "
      "GROUP BY CODIGO HAVING COUNT(DISTINCT CODALMACEN)=1) "
      "ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_054","Proveedores con más de 100 artículos asignados","¿Hay proveedores con catálogo excesivamente amplio?",
      "Proveedores con COUNT(ARTICULO)>100.",
      "SELECT P.CODIGO, COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,'Sin nombre') AS PROVEEDOR, "
      "COUNT(A.CODIGO) AS N_ARTICULOS "
      "FROM PROVEED P JOIN ARTICULO A ON A.PROVEEDDEFECTO=P.CODIGO "
      "GROUP BY P.CODIGO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "HAVING COUNT(A.CODIGO)>100 ORDER BY N_ARTICULOS DESC LIMIT 10",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_055","Artículos con PRECIOCOSTE actualizado hace más de 2 años","¿Hay artículos con PRECIOCOSTE muy desactualizado?",
      "Artículos en ARTICULO con NULL anterior a hace 2 años.",
      "SELECT NOMBRE, PRECIOCOSTE, NULL "
      "FROM ARTICULO WHERE NULL IS NOT NULL "
      "AND DATE('now')>'1900-01-01' "
      "ORDER BY NULL ASC LIMIT 20",
      "Compras","Compras","Alerta","Medio","",""),

    q("cx2_056","Artículos con mayor número de familias distintas (error de clasificación)","¿Hay artículos asignados a múltiples familias?",
      "Artículos con más de 1 CODFAMILIA (si es posible en el esquema).",
      "SELECT NOMBRE, CODFAMILIA FROM ARTICULO "
      "WHERE CODFAMILIA IS NOT NULL ORDER BY CODFAMILIA, NOMBRE LIMIT 30",
      "Compras","Compras","Calidad","Bajo","",""),

    q("cx2_057","Artículos con STOCKARTICULO total entre 1 y 5 unidades (STOCKARTICULO crítico)","¿Qué artículos están en STOCKARTICULO crítico?",
      "Artículos con SUM(STOCKARTICULO) entre 1 y 5 en ESTALMACEN.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL, A.STOCKARTICULO "
      "FROM ARTICULO A "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING SUM(A.STOCKARTICULO) BETWEEN 1 AND 5 "
      "ORDER BY STOCK_TOTAL ASC LIMIT 20",
      "Compras","Almacén","Alerta","Alto","",""),

    q("cx2_058","Proveedores con más pedidos en el último año","¿Qué proveedores reciben más pedidos?",
      "COUNT de DOCCAB TIPO=12 (pedidos) por proveedor (via CODCLIENTE si existe).",
      "SELECT CODCLIENTE, COUNT(*) AS N_PEDIDOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=12 AND CODCLIENTE IS NOT NULL "
      "AND FECHA>=DATE('now','-365 days') "
      "GROUP BY CODCLIENTE ORDER BY N_PEDIDOS DESC LIMIT 20",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_059","Artículos con PRECIOVENTA de venta redondeado (múltiplo de 10)","¿Hay artículos con PRECIOVENTA redondo que puedan ser estimaciones?",
      "Artículos en ARTICULO donde PRECIOVENTA es múltiplo de 10.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE "
      "FROM ARTICULO WHERE PRECIOVENTA>0 "
      "AND CAST(PRECIOVENTA AS INTEGER)%10=0 "
      "AND PRECIOVENTA=CAST(PRECIOVENTA AS INTEGER) "
      "ORDER BY PRECIOVENTA DESC LIMIT 20",
      "Compras","Compras","Calidad","Bajo","",""),

    q("cx2_060","Artículos con mayor diferencia entre STOCKARTICULO máximo y mínimo","¿Qué artículos tienen mayor rango de STOCKARTICULO permitido?",
      "STOCKMAX-STOCKARTICULO por artículo en ESTALMACEN.",
      "SELECT A.NOMBRE, A.STOCKARTICULO, A.STOCKARTICULO, A.STOCKARTICULO-A.STOCKARTICULO AS RANGO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.STOCKARTICULO>A.STOCKARTICULO "
      "ORDER BY RANGO DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_061","Artículos con PRECIOCOSTE entre 100 y 500 EUR","¿Cuántos artículos tienen PRECIOCOSTE medio-alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 100 y 500.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 100 AND 500",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_062","Artículos con mayor número de líneas en presupuestos","¿Qué artículos se presupuestan más?",
      "COUNT de DOCLIN por artículo en documentos TIPO=0.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_PRESUPUESTO "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=0 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_PRESUPUESTO DESC LIMIT 20",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_063","Artículos con STOCKARTICULO en almacén principal vs secundarios","¿Cómo se distribuye el STOCKARTICULO entre almacenes?",
      "Compara STOCKARTICULO del almacén 1 vs resto por artículo.",
      "SELECT A.NOMBRE, "
      "SUM(CASE WHEN '01'=1 THEN A.STOCKARTICULO ELSE 0 END) AS ALMACEN_PRINCIPAL, "
      "SUM(CASE WHEN '01'!=1 THEN A.STOCKARTICULO ELSE 0 END) AS ALMACENES_SECUNDARIOS "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 GROUP BY A.CODIGO, A.NOMBRE "
      "ORDER BY ALMACEN_PRINCIPAL DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_064","Artículos con mayor número de líneas en SATs","¿Qué artículos se usan más en servicio técnico?",
      "COUNT de DOCLIN por artículo en documentos TIPO=2 (SATs).",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_SAT, "
      "ROUND(SUM(L.CANTIDAD),2) AS CANTIDAD_TOTAL "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=2 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_SAT DESC LIMIT 20",
      "Compras","SAT / Técnico","KPI","Medio","",""),

    q("cx2_065","Artículos con PRECIOVENTA de venta inferior a 5 EUR","¿Qué artículos tienen PRECIOVENTA muy bajo?",
      "Artículos en ARTICULO con PRECIOVENTA<5 y PRECIOVENTA>0.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE "
      "FROM ARTICULO WHERE PRECIOVENTA>0 AND PRECIOVENTA<5 "
      "ORDER BY PRECIOVENTA ASC LIMIT 20",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_066","Artículos con mayor número de líneas en albaranes","¿Qué artículos aparecen más en albaranes?",
      "COUNT de DOCLIN por artículo en documentos TIPO=11.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_ALBARAN "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=11 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_ALBARAN DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_067","Artículos con PRECIOCOSTE superior a 1000 EUR","¿Qué artículos tienen PRECIOCOSTE muy alto?",
      "Artículos en ARTICULO con PRECIOCOSTE>1000.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOCOSTE>1000 ORDER BY PRECIOCOSTE DESC LIMIT 20",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_068","Artículos con STOCKARTICULO en exactamente 2 almacenes","¿Qué artículos están en exactamente 2 almacenes?",
      "Artículos con STOCKARTICULO en exactamente 2 almacenes distintos.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING COUNT(DISTINCT '01')=2 "
      "ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_069","Artículos con mayor número de líneas en pedidos","¿Qué artículos se piden más?",
      "COUNT de DOCLIN por artículo en documentos TIPO=12 (pedidos).",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_PEDIDO "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=12 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_PEDIDO DESC LIMIT 20",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_070","Artículos con PRECIOVENTA de venta entre 100 y 500 EUR","¿Cuántos artículos tienen PRECIOVENTA medio?",
      "Artículos en ARTICULO con PRECIOVENTA entre 100 y 500.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 100 AND 500",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_071","Artículos con mayor número de líneas en abonos","¿Qué artículos se devuelven más?",
      "COUNT de DOCLIN por artículo en documentos TIPO=3 (abonos).",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_ABONO "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=3 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_ABONO DESC LIMIT 20",
      "Compras","Calidad","Alerta","Medio","",""),

    q("cx2_072","Artículos con STOCKARTICULO total superior a 500 unidades","¿Qué artículos tienen STOCKARTICULO muy alto?",
      "Artículos con SUM(STOCKARTICULO)>500 en ESTALMACEN.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL, "
      "ROUND(SUM(A.STOCKARTICULO)*A.PRECIOCOSTE,2) AS VALOR_TOTAL "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 GROUP BY A.CODIGO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING SUM(A.STOCKARTICULO)>500 ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Compras","Almacén","Alerta","Medio","",""),

    q("cx2_073","Artículos con PRECIOCOSTE entre 500 y 1000 EUR","¿Cuántos artículos tienen PRECIOCOSTE alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 500 y 1000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 500 AND 1000",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_074","Artículos con mayor número de líneas en todos los documentos","¿Qué artículos tienen más movimientos totales?",
      "COUNT de DOCLIN por artículo en todos los tipos de documento.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_TOTAL_LINEAS "
      "FROM DOCLIN L JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_TOTAL_LINEAS DESC LIMIT 20",
      "Compras","Almacén","KPI","Medio","",""),

    q("cx2_075","Artículos con PRECIOVENTA de venta entre 500 y 1000 EUR","¿Cuántos artículos tienen PRECIOVENTA alto?",
      "Artículos en ARTICULO con PRECIOVENTA entre 500 y 1000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 500 AND 1000",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_076","Artículos con STOCKARTICULO total entre 10 y 50 unidades","¿Qué artículos tienen STOCKARTICULO moderado?",
      "Artículos con SUM(STOCKARTICULO) entre 10 y 50 en ESTALMACEN.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING SUM(A.STOCKARTICULO) BETWEEN 10 AND 50 "
      "ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_077","Artículos con mayor número de clientes distintos que los compran","¿Qué artículos tienen más demanda de clientes?",
      "COUNT(DISTINCT CODCLIENTE) por artículo en facturas TIPO=13.",
      "SELECT A.NOMBRE, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_CLIENTES DESC LIMIT 20",
      "Compras","Comercial","KPI","Medio","",""),

    q("cx2_078","Artículos con PRECIOVENTA de venta superior a 2000 EUR","¿Qué artículos son de PRECIOVENTA muy alto?",
      "Artículos en ARTICULO con PRECIOVENTA>2000.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOVENTA>2000 ORDER BY PRECIOVENTA DESC LIMIT 20",
      "Compras","Comercial","KPI","Medio","",""),

    q("cx2_079","Artículos con STOCKARTICULO total entre 50 y 100 unidades","¿Qué artículos tienen STOCKARTICULO medio-alto?",
      "Artículos con SUM(STOCKARTICULO) entre 50 y 100 en ESTALMACEN.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING SUM(A.STOCKARTICULO) BETWEEN 50 AND 100 "
      "ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_080","Artículos con mayor número de líneas en el último trimestre","¿Qué artículos se han movido más en el último trimestre?",
      "COUNT de DOCLIN por artículo en todos los documentos de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Almacén","KPI","Medio","",""),

    q("cx2_081","Artículos con PRECIOCOSTE entre 1 y 10 EUR","¿Cuántos artículos tienen PRECIOCOSTE bajo?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 1 y 10.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 1 AND 10",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_082","Artículos con mayor número de líneas en el último mes","¿Qué artículos se han movido más este mes?",
      "COUNT de DOCLIN por artículo en todos los documentos del último mes.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.FECHA>=DATE('now','-30 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Almacén","KPI","Medio","",""),

    q("cx2_083","Artículos con PRECIOVENTA de venta entre 10 y 50 EUR","¿Cuántos artículos tienen PRECIOVENTA bajo-medio?",
      "Artículos en ARTICULO con PRECIOVENTA entre 10 y 50.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 10 AND 50",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_084","Artículos con STOCKARTICULO total entre 100 y 500 unidades","¿Qué artículos tienen STOCKARTICULO alto?",
      "Artículos con SUM(STOCKARTICULO) entre 100 y 500 en ESTALMACEN.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A "
      "GROUP BY A.CODIGO, A.NOMBRE "
      "HAVING SUM(A.STOCKARTICULO) BETWEEN 100 AND 500 "
      "ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_085","Artículos con mayor número de líneas en el último semestre","¿Qué artículos se han movido más en el último semestre?",
      "COUNT de DOCLIN por artículo en todos los documentos de los últimos 180 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.FECHA>=DATE('now','-180 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Almacén","KPI","Medio","",""),

    q("cx2_086","Artículos con PRECIOCOSTE entre 10 y 50 EUR","¿Cuántos artículos tienen PRECIOCOSTE bajo-medio?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 10 y 50.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 10 AND 50",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_087","Artículos con mayor número de líneas en facturas del año actual","¿Qué artículos se han vendido más este año?",
      "COUNT de DOCLIN por artículo en facturas TIPO=13 del año actual.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Comercial","KPI","Alto","",""),

    q("cx2_088","Artículos con PRECIOVENTA de venta entre 50 y 100 EUR","¿Cuántos artículos tienen PRECIOVENTA medio?",
      "Artículos en ARTICULO con PRECIOVENTA entre 50 y 100.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 50 AND 100",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_089","Artículos con STOCKARTICULO total entre 5 y 10 unidades","¿Qué artículos tienen STOCKARTICULO muy bajo?",
      "Artículos con SUM(STOCKARTICULO) entre 5 y 10 en ESTALMACEN.",
      "SELECT A.NOMBRE, SUM(A.STOCKARTICULO) AS STOCK_TOTAL, A.STOCKARTICULO "
      "FROM ARTICULO A "
      "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
      "HAVING SUM(A.STOCKARTICULO) BETWEEN 5 AND 10 "
      "ORDER BY STOCK_TOTAL ASC LIMIT 20",
      "Compras","Almacén","Alerta","Alto","",""),

    q("cx2_090","Artículos con mayor número de líneas en facturas del año anterior","¿Qué artículos se vendieron más el año pasado?",
      "COUNT de DOCLIN por artículo en facturas TIPO=13 del año anterior.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND SUBSTR(D.FECHA,1,4)=CAST(STRFTIME('%Y','now')-1 AS TEXT) "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Comercial","KPI","Medio","",""),

    q("cx2_091","Artículos con PRECIOCOSTE entre 50 y 100 EUR","¿Cuántos artículos tienen PRECIOCOSTE medio?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 50 y 100.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 50 AND 100",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_092","Artículos con mayor número de líneas en presupuestos del año actual","¿Qué artículos se presupuestan más este año?",
      "COUNT de DOCLIN por artículo en presupuestos TIPO=0 del año actual.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=0 "
      "AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_093","Artículos con PRECIOVENTA de venta entre 1000 y 5000 EUR","¿Cuántos artículos tienen PRECIOVENTA muy alto?",
      "Artículos en ARTICULO con PRECIOVENTA entre 1000 y 5000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 1000 AND 5000",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_094","Artículos con mayor número de líneas en SATs del año actual","¿Qué artículos se usan más en SAT este año?",
      "COUNT de DOCLIN por artículo en SATs TIPO=2 del año actual.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_SAT "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=2 "
      "AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_SAT DESC LIMIT 20",
      "Compras","SAT / Técnico","KPI","Medio","",""),

    q("cx2_095","Artículos con PRECIOCOSTE entre 100 y 200 EUR","¿Cuántos artículos tienen PRECIOCOSTE medio-alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 100 y 200.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 100 AND 200",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_096","Artículos con mayor número de líneas en albaranes del año actual","¿Qué artículos se albaranan más este año?",
      "COUNT de DOCLIN por artículo en albaranes TIPO=11 del año actual.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=11 "
      "AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_097","Artículos con PRECIOVENTA de venta entre 200 y 500 EUR","¿Cuántos artículos tienen PRECIOVENTA medio-alto?",
      "Artículos en ARTICULO con PRECIOVENTA entre 200 y 500.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 200 AND 500",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_098","Artículos con mayor número de líneas en pedidos del año actual","¿Qué artículos se piden más este año?",
      "COUNT de DOCLIN por artículo en pedidos TIPO=12 del año actual.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=12 "
      "AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_099","Artículos con PRECIOCOSTE entre 200 y 500 EUR","¿Cuántos artículos tienen PRECIOCOSTE alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 200 y 500.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 200 AND 500",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_100","Resumen de catálogo de artículos","¿Cuántos artículos hay y cuál es su PRECIOCOSTE y PRECIOVENTA medio?",
      "Estadísticas generales del catálogo de artículos.",
      "SELECT COUNT(*) AS N_ARTICULOS, "
      "ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO, "
      "ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO, "
      "ROUND(MIN(PRECIOCOSTE),2) AS COSTE_MIN, "
      "ROUND(MAX(PRECIOCOSTE),2) AS COSTE_MAX, "
      "ROUND(MIN(PRECIOVENTA),2) AS PRECIO_MIN, "
      "ROUND(MAX(PRECIOVENTA),2) AS PRECIO_MAX "
      "FROM ARTICULO WHERE PRECIOCOSTE>0 AND PRECIOVENTA>0",
      "Compras","Dirección","KPI","Alto","",""),

    q("cx2_101","Artículos con mayor número de líneas en abonos del año actual","¿Qué artículos se devuelven más este año?",
      "COUNT de DOCLIN por artículo en abonos TIPO=3 del año actual.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_ABONO "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=3 "
      "AND SUBSTR(D.FECHA,1,4)=STRFTIME('%Y','now') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_ABONO DESC LIMIT 20",
      "Compras","Calidad","Alerta","Medio","",""),

    q("cx2_102","Artículos con PRECIOCOSTE entre 500 y 2000 EUR","¿Cuántos artículos tienen PRECIOCOSTE muy alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 500 y 2000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 500 AND 2000",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_103","Artículos con mayor número de líneas en facturas del último trimestre","¿Qué artículos se han vendido más en el último trimestre?",
      "COUNT de DOCLIN por artículo en facturas TIPO=13 de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Comercial","KPI","Medio","",""),

    q("cx2_104","Artículos con PRECIOVENTA de venta entre 5 y 10 EUR","¿Cuántos artículos tienen PRECIOVENTA muy bajo?",
      "Artículos en ARTICULO con PRECIOVENTA entre 5 y 10.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 5 AND 10",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_105","Artículos con mayor número de líneas en facturas del último semestre","¿Qué artículos se han vendido más en el último semestre?",
      "COUNT de DOCLIN por artículo en facturas TIPO=13 de los últimos 180 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-180 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Comercial","KPI","Medio","",""),

    q("cx2_106","Artículos con PRECIOCOSTE entre 2000 y 5000 EUR","¿Cuántos artículos tienen PRECIOCOSTE extremadamente alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 2000 y 5000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 2000 AND 5000",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_107","Artículos con mayor número de líneas en facturas del último mes","¿Qué artículos se han vendido más este mes?",
      "COUNT de DOCLIN por artículo en facturas TIPO=13 del último mes.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=13 "
      "AND D.FECHA>=DATE('now','-30 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Comercial","KPI","Alto","",""),

    q("cx2_108","Artículos con PRECIOVENTA de venta entre 1 y 5 EUR","¿Cuántos artículos tienen PRECIOVENTA mínimo?",
      "Artículos en ARTICULO con PRECIOVENTA entre 1 y 5.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 1 AND 5",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_109","Artículos con mayor número de líneas en SATs del último trimestre","¿Qué artículos se usan más en SAT en el último trimestre?",
      "COUNT de DOCLIN por artículo en SATs TIPO=2 de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_SAT "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=2 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_SAT DESC LIMIT 20",
      "Compras","SAT / Técnico","KPI","Medio","",""),

    q("cx2_110","Artículos con PRECIOCOSTE superior a 5000 EUR","¿Hay artículos con PRECIOCOSTE extremadamente alto?",
      "Artículos en ARTICULO con PRECIOCOSTE>5000.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOCOSTE>5000 ORDER BY PRECIOCOSTE DESC LIMIT 20",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_111","Artículos con mayor número de líneas en albaranes del último trimestre","¿Qué artículos se albaranan más en el último trimestre?",
      "COUNT de DOCLIN por artículo en albaranes TIPO=11 de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=11 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Almacén","Operacional","Bajo","",""),

    q("cx2_112","Artículos con PRECIOVENTA de venta superior a 10000 EUR","¿Hay artículos con PRECIOVENTA extremadamente alto?",
      "Artículos en ARTICULO con PRECIOVENTA>10000.",
      "SELECT NOMBRE, PRECIOVENTA, PRECIOCOSTE, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOVENTA>10000 ORDER BY PRECIOVENTA DESC LIMIT 20",
      "Compras","Comercial","KPI","Medio","",""),

    q("cx2_113","Artículos con mayor número de líneas en pedidos del último trimestre","¿Qué artículos se piden más en el último trimestre?",
      "COUNT de DOCLIN por artículo en pedidos TIPO=12 de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=12 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_114","Artículos con PRECIOCOSTE superior a 2000 EUR","¿Hay artículos con PRECIOCOSTE muy alto?",
      "Artículos en ARTICULO con PRECIOCOSTE>2000.",
      "SELECT NOMBRE, PRECIOCOSTE, PRECIOVENTA, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOCOSTE>2000 ORDER BY PRECIOCOSTE DESC LIMIT 20",
      "Compras","Compras","KPI","Medio","",""),

    q("cx2_115","Artículos con mayor número de líneas en abonos del último trimestre","¿Qué artículos se devuelven más en el último trimestre?",
      "COUNT de DOCLIN por artículo en abonos TIPO=3 de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS_ABONO "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=3 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS_ABONO DESC LIMIT 20",
      "Compras","Calidad","Alerta","Medio","",""),

    q("cx2_116","Artículos con PRECIOVENTA de venta entre 100 y 200 EUR","¿Cuántos artículos tienen PRECIOVENTA medio?",
      "Artículos en ARTICULO con PRECIOVENTA entre 100 y 200.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 100 AND 200",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_117","Artículos con mayor número de líneas en presupuestos del último trimestre","¿Qué artículos se presupuestan más en el último trimestre?",
      "COUNT de DOCLIN por artículo en presupuestos TIPO=0 de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO AND D.TIPO=0 "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_118","Artículos con PRECIOCOSTE entre 200 y 1000 EUR","¿Cuántos artículos tienen PRECIOCOSTE alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 200 y 1000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 200 AND 1000",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_119","Artículos con mayor número de líneas en todos los documentos del último mes","¿Qué artículos tienen más movimientos este mes?",
      "COUNT de DOCLIN por artículo en todos los documentos del último mes.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_TOTAL_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.FECHA>=DATE('now','-30 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_TOTAL_LINEAS DESC LIMIT 20",
      "Compras","Almacén","KPI","Alto","",""),

    q("cx2_120","Artículos con PRECIOVENTA de venta entre 500 y 2000 EUR","¿Cuántos artículos tienen PRECIOVENTA alto?",
      "Artículos en ARTICULO con PRECIOVENTA entre 500 y 2000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 500 AND 2000",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_121","Artículos con mayor número de líneas en todos los documentos del último trimestre","¿Qué artículos tienen más movimientos en el último trimestre?",
      "COUNT de DOCLIN por artículo en todos los documentos de los últimos 90 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_TOTAL_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_TOTAL_LINEAS DESC LIMIT 20",
      "Compras","Almacén","KPI","Medio","",""),

    q("cx2_122","Artículos con PRECIOCOSTE entre 1000 y 2000 EUR","¿Cuántos artículos tienen PRECIOCOSTE muy alto?",
      "Artículos en ARTICULO con PRECIOCOSTE entre 1000 y 2000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOCOSTE),2) AS COSTE_MEDIO "
      "FROM ARTICULO WHERE PRECIOCOSTE BETWEEN 1000 AND 2000",
      "Compras","Compras","Operacional","Bajo","",""),

    q("cx2_123","Artículos con mayor número de líneas en todos los documentos del último semestre","¿Qué artículos tienen más movimientos en el último semestre?",
      "COUNT de DOCLIN por artículo en todos los documentos de los últimos 180 días.",
      "SELECT A.NOMBRE, COUNT(L.CODARTICULO) AS N_TOTAL_LINEAS "
      "FROM DOCLIN L "
      "JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "AND D.FECHA>=DATE('now','-180 days') "
      "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N_TOTAL_LINEAS DESC LIMIT 20",
      "Compras","Almacén","KPI","Medio","",""),

    q("cx2_124","Artículos con PRECIOVENTA de venta entre 2000 y 5000 EUR","¿Cuántos artículos tienen PRECIOVENTA muy alto?",
      "Artículos en ARTICULO con PRECIOVENTA entre 2000 y 5000.",
      "SELECT COUNT(*) AS N_ARTICULOS, ROUND(AVG(PRECIOVENTA),2) AS PRECIO_MEDIO "
      "FROM ARTICULO WHERE PRECIOVENTA BETWEEN 2000 AND 5000",
      "Compras","Comercial","Operacional","Bajo","",""),

    q("cx2_125","Resumen ejecutivo de compras y STOCKARTICULO","¿Cuál es el resumen ejecutivo de compras?",
      "Combina: N artículos, valor total STOCKARTICULO, PRECIOCOSTE medio, artículos sin STOCKARTICULO, artículos bajo mínimo.",
      "SELECT "
      "(SELECT COUNT(*) FROM ARTICULO) AS N_ARTICULOS, "
      "(SELECT ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) FROM ARTICULO A WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0) AS VALOR_STOCK_TOTAL, "
      "(SELECT ROUND(AVG(PRECIOCOSTE),2) FROM ARTICULO WHERE PRECIOCOSTE>0) AS COSTE_MEDIO, "
      "(SELECT COUNT(DISTINCT CODIGO) FROM ARTICULO WHERE STOCKARTICULO<=0) AS ARTICULOS_SIN_STOCKARTICULO, "
      "(SELECT COUNT(*) FROM PROVEED) AS N_PROVEEDORES",
      "Compras","Dirección","KPI","Crítico","",""),

]
