"""
query_library/compras.py — 125 consultas extendidas de Compras y Proveedores.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: ver reglas en DEVIA.md
NOTA: DOCCAB no tiene PROVEEDDEFECTO directo -> acceder via DOCLIN->ARTICULO->PROVEED
"""

from backend.modules.db_simulator.query_library.builder import q

_P = "COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL, CAST(P.CODIGO AS TEXT))"
_PA = "COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL, CAST(A.PROVEEDDEFECTO AS TEXT))"
_A = "COALESCE(A.NOMBRE, A.DESCRIPCION, A.CODIGO)"

QUERIES_COMPRAS_EXTENDED = [

    q("cx_001", "Catalogo completo de proveedores",
      "Que proveedores estan registrados en el sistema?",
      "Lista todos los registros de PROVEED con nombre, TEL y numero de articulos asociados.",
      "SELECT " + _P + " AS PROVEEDOR, P.TEL, COUNT(A.CODIGO) AS N_ARTICULOS "
      "FROM PROVEED P LEFT JOIN ARTICULO A ON A.PROVEEDDEFECTO=P.CODIGO "
      "GROUP BY P.CODIGO ORDER BY N_ARTICULOS DESC LIMIT 30",
      "Compras", "Administrativo", "Proveedor", "Bajo", "", ""),

    q("cx_002", "Proveedores sin articulos asociados",
      "Que proveedores no tienen ningun articulo en el catalogo?",
      "PROVEED sin registros en ARTICULO con PROVEEDDEFECTO coincidente.",
      "SELECT " + _P + " AS PROVEEDOR, P.TEL "
      "FROM PROVEED P WHERE P.CODIGO NOT IN "
      "(SELECT DISTINCT PROVEEDDEFECTO FROM ARTICULO WHERE PROVEEDDEFECTO IS NOT NULL AND PROVEEDDEFECTO!='') "
      "LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Medio", "", ""),

    q("cx_003", "Articulos por proveedor con STOCKARTICULO actual",
      "Cuantos articulos y que STOCKARTICULO tiene cada proveedor?",
      "Agrupa ARTICULO por PROVEEDDEFECTO con SUM(STOCKARTICULO) y valor a PRECIOCOSTE.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS, "
      "SUM(A.STOCKARTICULO) AS STOCK_TOTAL, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_STOCK_COSTE "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY (STOCKARTICULO*PRECIOCOSTE) DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_004", "Articulos con STOCKARTICULO bajo por proveedor",
      "Que proveedores tienen articulos con STOCKARTICULO bajo (3 o menos unidades)?",
      "ARTICULO con STOCKARTICULO <= 3 agrupado por PROVEEDDEFECTO.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS_STOCK_BAJO, "
      "SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.STOCKARTICULO <= 3 AND A.STOCKARTICULO >= 0 "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY N_ARTICULOS_STOCK_BAJO DESC LIMIT 20",
      "Compras", "Almacenero", "Riesgo", "Alto", "", ""),

    q("cx_005", "Articulos sin STOCKARTICULO por proveedor",
      "Que proveedores tienen articulos sin STOCKARTICULO?",
      "ARTICULO con STOCKARTICULO = 0 agrupado por PROVEEDDEFECTO.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS_SIN_STOCKARTICULO "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.STOCKARTICULO = 0 "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY N_ARTICULOS_SIN_STOCKARTICULO DESC LIMIT 20",
      "Compras", "Almacenero", "Riesgo", "Critico", "", ""),

    q("cx_006", "Valor del catalogo por proveedor a PRECIOVENTA de venta",
      "Cuanto vale el catalogo de cada proveedor a PRECIOVENTA de venta?",
      "SUM(PRECIOVENTA*STOCKARTICULO) por PROVEEDDEFECTO en ARTICULO.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(A.PRECIOVENTA*A.STOCKARTICULO),2) AS VALOR_CATALOGO_VENTA "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY VALOR_CATALOGO_VENTA DESC LIMIT 20",
      "Compras", "Director", "Financiero", "Medio", "", ""),

    q("cx_007", "Margen medio por proveedor",
      "Que proveedores ofrecen mayor margen en sus articulos?",
      "AVG((PRECIOVENTA-PRECIOCOSTE)/PRECIOVENTA*100) por PROVEEDDEFECTO en ARTICULO.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS, "
      "ROUND(AVG(CASE WHEN A.PRECIOVENTA>0 THEN 100.0*(A.PRECIOVENTA-A.PRECIOCOSTE)/A.PRECIOVENTA ELSE NULL END),1) AS MARGEN_MEDIO_PCT "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' AND A.PRECIOVENTA > 0 "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY MARGEN_MEDIO_PCT DESC LIMIT 20",
      "Compras", "Director", "Financiero", "Alto", "", ""),

    q("cx_008", "Articulos con margen negativo por proveedor",
      "Que proveedores tienen articulos con PRECIOVENTA de venta inferior al PRECIOCOSTE?",
      "ARTICULO con PRECIOVENTA < PRECIOCOSTE agrupado por PROVEEDDEFECTO.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS_MARGEN_NEG "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PRECIOVENTA < A.PRECIOCOSTE AND A.PRECIOCOSTE > 0 "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY N_ARTICULOS_MARGEN_NEG DESC LIMIT 20",
      "Compras", "Director", "Riesgo", "Critico", "", ""),

    q("cx_009", "Articulos mas vendidos por proveedor",
      "Que articulos de cada proveedor generan mas ventas?",
      "JOIN DOCLIN->DOCCAB TIPO=13->ARTICULO->PROVEED. Agrupa por proveedor y articulo.",
      "SELECT " + _PA + " AS PROVEEDOR, " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_VENTAS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO, L.CODARTICULO ORDER BY IMPORTE_VENTAS DESC LIMIT 40",
      "Compras", "Comercial", "Proveedor", "Alto", "", ""),

    q("cx_010", "Ventas totales por proveedor",
      "Cuanto se ha vendido de articulos de cada proveedor?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=13 JOIN ARTICULO por PROVEEDDEFECTO.",
      "SELECT " + _PA + " AS PROVEEDOR, "
      "COUNT(DISTINCT L.CODDOCUMENTO) AS N_FACTURAS, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS VENTAS_TOTAL "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY VENTAS_TOTAL DESC LIMIT 20",
      "Compras", "Director", "Proveedor", "Alto", "", ""),

    q("cx_011", "Ventas por proveedor y mes",
      "Como evolucionan las ventas de cada proveedor mes a mes?",
      "Cruza PROVEEDDEFECTO con SUBSTR(FECHA,1,7) en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT " + _PA + " AS PROVEEDOR, SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS VENTAS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' AND D.FECHA IS NOT NULL "
      "GROUP BY A.PROVEEDDEFECTO, SUBSTR(D.FECHA,1,7) ORDER BY MES DESC, VENTAS DESC LIMIT 60",
      "Compras", "Director", "Proveedor", "Medio", "", ""),

    q("cx_012", "Proveedor con mayor numero de articulos en catalogo",
      "Que proveedor tiene mas articulos en el catalogo?",
      "COUNT(ARTICULO) por PROVEEDDEFECTO.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY N_ARTICULOS DESC LIMIT 20",
      "Compras", "Administrativo", "Proveedor", "Bajo", "", ""),

    q("cx_013", "Articulos de un solo proveedor (dependencia exclusiva)",
      "Que articulos solo tienen un proveedor posible?",
      "Todos los articulos tienen un solo PROVEEDDEFECTO en el modelo actual. "
      "Esta consulta lista articulos con proveedor asignado para identificar dependencias.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS_EXCLUSIVOS "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO HAVING COUNT(A.CODIGO) >= 5 "
      "ORDER BY N_ARTICULOS_EXCLUSIVOS DESC LIMIT 20",
      "Compras", "Director", "Riesgo", "Alto", "", ""),

    q("cx_014", "Articulos con PRECIOVENTA de PRECIOCOSTE superior a PRECIOVENTA de venta",
      "Que articulos tienen PRECIOCOSTE mayor que PRECIOVENTA de venta?",
      "ARTICULO con PRECIOCOSTE > PRECIOVENTA. Vender estos articulos genera perdida.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.PRECIOCOSTE-A.PRECIOVENTA,2) AS PERDIDA_UNITARIA "
      "FROM ARTICULO A WHERE A.PRECIOCOSTE > A.PRECIOVENTA AND A.PRECIOVENTA > 0 "
      "ORDER BY PERDIDA_UNITARIA DESC LIMIT 20",
      "Compras", "Director", "Riesgo", "Critico", "", ""),

    q("cx_015", "Articulos con PRECIOVENTA de PRECIOCOSTE igual a PRECIOVENTA de venta",
      "Que articulos tienen margen cero?",
      "ARTICULO con PRECIOCOSTE = PRECIOVENTA. Margen bruto = 0.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A WHERE A.PRECIOCOSTE = A.PRECIOVENTA AND A.PRECIOVENTA > 0 LIMIT 20",
      "Compras", "Director", "Riesgo", "Alto", "", ""),

    q("cx_016", "Articulos con mayor diferencia entre PRECIOCOSTE y PRECIOVENTA de venta",
      "Que articulos tienen mayor margen absoluto?",
      "MAX(PRECIOVENTA-PRECIOCOSTE) por articulo en ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.PRECIOVENTA-A.PRECIOCOSTE,2) AS MARGEN_ABSOLUTO "
      "FROM ARTICULO A WHERE A.PRECIOVENTA > 0 AND A.PRECIOCOSTE > 0 "
      "ORDER BY MARGEN_ABSOLUTO DESC LIMIT 20",
      "Compras", "Director", "Financiero", "Medio", "", ""),

    q("cx_017", "Articulos con mayor porcentaje de margen",
      "Que articulos tienen mayor porcentaje de margen bruto?",
      "100*(PRECIOVENTA-PRECIOCOSTE)/PRECIOVENTA por articulo en ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(100.0*(A.PRECIOVENTA-A.PRECIOCOSTE)/A.PRECIOVENTA,1) AS MARGEN_PCT "
      "FROM ARTICULO A WHERE A.PRECIOVENTA > 0 AND A.PRECIOCOSTE > 0 "
      "ORDER BY MARGEN_PCT DESC LIMIT 20",
      "Compras", "Director", "Financiero", "Alto", "", ""),

    q("cx_018", "Articulos con menor porcentaje de margen (positivo)",
      "Que articulos tienen el margen mas ajustado?",
      "MIN(100*(PRECIOVENTA-PRECIOCOSTE)/PRECIOVENTA) > 0 por articulo en ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(100.0*(A.PRECIOVENTA-A.PRECIOCOSTE)/A.PRECIOVENTA,1) AS MARGEN_PCT "
      "FROM ARTICULO A WHERE A.PRECIOVENTA > 0 AND A.PRECIOCOSTE > 0 "
      "AND A.PRECIOVENTA > A.PRECIOCOSTE "
      "ORDER BY MARGEN_PCT ASC LIMIT 20",
      "Compras", "Director", "Riesgo", "Alto", "", ""),

    q("cx_019", "Articulos dados de baja con STOCKARTICULO positivo",
      "Hay articulos dados de baja que aun tienen STOCKARTICULO?",
      "ARTICULO con BAJA=1 y STOCKARTICULO > 0. STOCKARTICULO inmovilizado de articulos inactivos.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_UNITARIO, "
      "ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_STOCKARTICULO "
      "FROM ARTICULO A WHERE A.BAJA=1 AND A.STOCKARTICULO > 0 "
      "ORDER BY VALOR_STOCKARTICULO DESC LIMIT 20",
      "Compras", "Almacenero", "Riesgo", "Alto", "", ""),

    q("cx_020", "Articulos sin familia asignada",
      "Que articulos no tienen familia de producto asignada?",
      "ARTICULO con CODFAMILIA NULL o vacio.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A WHERE A.CODFAMILIA IS NULL OR A.CODFAMILIA='' "
      "ORDER BY A.STOCKARTICULO DESC LIMIT 30",
      "Compras", "Administrativo", "Calidad", "Medio", "", ""),

    q("cx_021", "Articulos sin descripcion ni nombre",
      "Hay articulos sin nombre ni descripcion?",
      "ARTICULO con NOMBRE y DESCRIPCION vacios o nulos.",
      "SELECT A.CODIGO, A.STOCKARTICULO AS STOCKARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A WHERE (A.NOMBRE IS NULL OR A.NOMBRE='') "
      "AND (A.DESCRIPCION IS NULL OR A.DESCRIPCION='') LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Medio", "", ""),

    q("cx_022", "Articulos con PRECIOVENTA de venta cero y STOCKARTICULO positivo",
      "Hay articulos con PRECIOVENTA cero pero con STOCKARTICULO?",
      "ARTICULO con PRECIOVENTA=0 y STOCKARTICULO > 0. No se pueden vender correctamente.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE (A.PRECIOVENTA=0 OR A.PRECIOVENTA IS NULL) AND A.STOCKARTICULO > 0 "
      "ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Alto", "", ""),

    q("cx_023", "Articulos con PRECIOVENTA de PRECIOCOSTE cero y STOCKARTICULO positivo",
      "Hay articulos con PRECIOCOSTE cero pero con STOCKARTICULO?",
      "ARTICULO con PRECIOCOSTE=0 y STOCKARTICULO > 0. El margen no se puede calcular.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A WHERE (A.PRECIOCOSTE=0 OR A.PRECIOCOSTE IS NULL) AND A.STOCKARTICULO > 0 "
      "ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Medio", "", ""),

    q("cx_024", "Articulos con STOCKARTICULO negativo",
      "Hay articulos con STOCKARTICULO negativo?",
      "ARTICULO con STOCKARTICULO < 0. Indica error de registro de movimientos.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A WHERE A.STOCKARTICULO < 0 "
      "ORDER BY A.STOCKARTICULO ASC LIMIT 20",
      "Compras", "Almacenero", "Calidad", "Critico", "", ""),

    q("cx_025", "Valor total del inventario a PRECIOVENTA de PRECIOCOSTE",
      "Cual es el valor total del inventario a PRECIOVENTA de PRECIOCOSTE?",
      "SUM(STOCKARTICULO*PRECIOCOSTE) en ARTICULO con STOCKARTICULO > 0.",
      "SELECT COUNT(*) AS N_ARTICULOS_CON_STOCKARTICULO, "
      "SUM(A.STOCKARTICULO) AS UNIDADES_TOTALES, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_INVENTARIO_COSTE "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.PRECIOCOSTE > 0",
      "Compras", "Director", "Financiero", "Critico", "Valor inventario", ""),

    q("cx_026", "Valor total del inventario a PRECIOVENTA de venta",
      "Cual es el valor total del inventario a PRECIOVENTA de venta?",
      "SUM(STOCKARTICULO*PRECIOVENTA) en ARTICULO con STOCKARTICULO > 0.",
      "SELECT COUNT(*) AS N_ARTICULOS_CON_STOCKARTICULO, "
      "SUM(A.STOCKARTICULO) AS UNIDADES_TOTALES, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOVENTA),2) AS VALOR_INVENTARIO_VENTA "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.PRECIOVENTA > 0",
      "Compras", "Director", "Financiero", "Critico", "Valor inventario venta", ""),

    q("cx_027", "Diferencia entre valor inventario PRECIOCOSTE y venta",
      "Cual es el margen potencial del inventario actual?",
      "Diferencia entre SUM(PRECIOVENTA*STOCKARTICULO) y SUM(PRECIOCOSTE*STOCKARTICULO).",
      "SELECT "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOVENTA),2) AS VALOR_VENTA, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_COSTE, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOVENTA)-SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS MARGEN_POTENCIAL "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.PRECIOVENTA > 0 AND A.PRECIOCOSTE > 0",
      "Compras", "Director", "Financiero", "Alto", "", ""),

    q("cx_028", "Articulos con mayor valor de STOCKARTICULO a PRECIOCOSTE",
      "Que articulos tienen mayor valor inmovilizado en STOCKARTICULO?",
      "STOCKARTICULO*PRECIOCOSTE por articulo en ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE_UNITARIO, "
      "ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_STOCKARTICULO "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.PRECIOCOSTE > 0 "
      "ORDER BY VALOR_STOCKARTICULO DESC LIMIT 20",
      "Compras", "Almacenero", "Financiero", "Alto", "", ""),

    q("cx_029", "Articulos con mayor valor de STOCKARTICULO a PRECIOVENTA de venta",
      "Que articulos tienen mayor valor potencial de venta en STOCKARTICULO?",
      "STOCKARTICULO*PRECIOVENTA por articulo en ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.STOCKARTICULO*A.PRECIOVENTA,2) AS VALOR_POTENCIAL "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.PRECIOVENTA > 0 "
      "ORDER BY VALOR_POTENCIAL DESC LIMIT 20",
      "Compras", "Almacenero", "Financiero", "Medio", "", ""),

    q("cx_030", "Articulos con STOCKARTICULO superior a 50 unidades",
      "Que articulos tienen mas de 50 unidades en STOCKARTICULO?",
      "ARTICULO con STOCKARTICULO > 50.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO, ROUND(A.PRECIOCOSTE,2) AS COSTE "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 50 "
      "ORDER BY A.STOCKARTICULO DESC LIMIT 20",
      "Compras", "Almacenero", "Operacional", "Medio", "", ""),

    q("cx_031", "Articulos con STOCKARTICULO entre 1 y 3 unidades (critico)",
      "Que articulos tienen STOCKARTICULO critico (1-3 unidades)?",
      "ARTICULO con STOCKARTICULO BETWEEN 1 AND 3.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO, "
      "COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,'Sin proveedor') AS PROVEEDOR "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.STOCKARTICULO BETWEEN 1 AND 3 "
      "ORDER BY A.STOCKARTICULO ASC LIMIT 30",
      "Compras", "Almacenero", "Riesgo", "Alto", "", ""),

    q("cx_032", "Articulos con STOCKARTICULO entre 4 y 10 unidades (bajo)",
      "Que articulos tienen STOCKARTICULO bajo (4-10 unidades)?",
      "ARTICULO con STOCKARTICULO BETWEEN 4 AND 10.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO "
      "FROM ARTICULO A WHERE A.STOCKARTICULO BETWEEN 4 AND 10 "
      "ORDER BY A.STOCKARTICULO ASC LIMIT 30",
      "Compras", "Almacenero", "Riesgo", "Medio", "", ""),

    q("cx_033", "Familias con mayor valor de STOCKARTICULO",
      "Que familias de producto tienen mayor valor de inventario?",
      "SUM(STOCKARTICULO*PRECIOCOSTE) por CODFAMILIA en ARTICULO JOIN FAMILIA.",
      "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
      "COUNT(A.CODIGO) AS N_ARTICULOS, "
      "SUM(A.STOCKARTICULO) AS STOCK_TOTAL, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_COSTE "
      "FROM ARTICULO A LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY A.CODFAMILIA ORDER BY VALOR_PRECIOCOSTE DESC LIMIT 20",
      "Compras", "Almacenero", "Financiero", "Alto", "", ""),

    q("cx_034", "Familias con mayor numero de articulos sin STOCKARTICULO",
      "Que familias tienen mas articulos sin STOCKARTICULO?",
      "COUNT(ARTICULO con STOCKARTICULO=0) por CODFAMILIA.",
      "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
      "COUNT(A.CODIGO) AS N_SIN_STOCKARTICULO "
      "FROM ARTICULO A LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "WHERE A.STOCKARTICULO = 0 "
      "GROUP BY A.CODFAMILIA ORDER BY N_SIN_STOCKARTICULO DESC LIMIT 20",
      "Compras", "Almacenero", "Riesgo", "Alto", "", ""),

    q("cx_035", "Articulos con mayor rotacion (ventas/STOCKARTICULO)",
      "Que articulos tienen mayor rotacion de inventario?",
      "Ratio SUM(CANTIDAD vendida) / STOCKARTICULO por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_VENDIDAS, "
      "A.STOCKARTICULO AS STOCK_ACTUAL, "
      "CASE WHEN A.STOCKARTICULO > 0 "
      "THEN ROUND(SUM(CAST(L.CANTIDAD AS REAL))/A.STOCKARTICULO,2) ELSE NULL END AS ROTACION "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.STOCKARTICULO > 0 GROUP BY L.CODARTICULO "
      "ORDER BY ROTACION DESC LIMIT 20",
      "Compras", "Almacenero", "Optimizacion", "Alto", "", ""),

    q("cx_036", "Articulos con menor rotacion (posible sobrestock)",
      "Que articulos tienen menor rotacion de inventario?",
      "Ratio SUM(CANTIDAD vendida) / STOCKARTICULO por articulo. Menor = mas sobrestock.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_VENDIDAS, "
      "A.STOCKARTICULO AS STOCK_ACTUAL, "
      "CASE WHEN A.STOCKARTICULO > 0 "
      "THEN ROUND(SUM(CAST(L.CANTIDAD AS REAL))/A.STOCKARTICULO,2) ELSE NULL END AS ROTACION "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.STOCKARTICULO > 0 GROUP BY L.CODARTICULO "
      "ORDER BY ROTACION ASC LIMIT 20",
      "Compras", "Almacenero", "Riesgo", "Alto", "", ""),

    q("cx_037", "Articulos con STOCKARTICULO pero sin ventas en 90 dias",
      "Que articulos tienen STOCKARTICULO pero no se han vendido en 3 meses?",
      "ARTICULO con STOCKARTICULO > 0 que no aparece en DOCLIN JOIN DOCCAB TIPO=13 "
      "con FECHA >= date('now','-90 days').",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "WHERE D.FECHA >= date('now','-90 days') AND L.CODARTICULO IS NOT NULL) "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 30",
      "Compras", "Almacenero", "Riesgo", "Alto", "", ""),

    q("cx_038", "Articulos con STOCKARTICULO pero sin ventas en 180 dias",
      "Que articulos tienen STOCKARTICULO pero no se han vendido en 6 meses?",
      "ARTICULO con STOCKARTICULO > 0 sin ventas en los ultimos 180 dias.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "WHERE D.FECHA >= date('now','-180 days') AND L.CODARTICULO IS NOT NULL) "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 30",
      "Compras", "Almacenero", "Riesgo", "Critico", "", ""),

    q("cx_039", "Articulos con STOCKARTICULO pero sin ventas nunca",
      "Que articulos tienen STOCKARTICULO pero nunca se han vendido?",
      "ARTICULO con STOCKARTICULO > 0 que no aparece en ninguna DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.STOCKARTICULO*A.PRECIOCOSTE,2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "WHERE L.CODARTICULO IS NOT NULL) "
      "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 30",
      "Compras", "Almacenero", "Riesgo", "Critico", "", ""),

    q("cx_040", "Proveedor con mayor valor de STOCKARTICULO inmovilizado",
      "Que proveedor tiene mas valor de STOCKARTICULO sin vender?",
      "SUM(STOCKARTICULO*PRECIOCOSTE) para articulos sin ventas en 90 dias por proveedor.",
      "SELECT " + _PA + " AS PROVEEDOR, COUNT(A.CODIGO) AS N_ARTICULOS, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.STOCKARTICULO > 0 AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "WHERE D.FECHA >= date('now','-90 days') AND L.CODARTICULO IS NOT NULL) "
      "GROUP BY A.PROVEEDDEFECTO ORDER BY VALOR_INMOVILIZADO DESC LIMIT 20",
      "Compras", "Director", "Riesgo", "Alto", "", ""),

    q("cx_041", "Articulos con mayor numero de unidades vendidas por proveedor",
      "Que articulos de cada proveedor se venden en mas unidades?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=13 por articulo y proveedor.",
      "SELECT " + _PA + " AS PROVEEDOR, " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_VENDIDAS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO, L.CODARTICULO ORDER BY UNIDADES_VENDIDAS DESC LIMIT 40",
      "Compras", "Almacenero", "Proveedor", "Medio", "", ""),

    q("cx_042", "Articulos con PRECIOVENTA actualizado recientemente",
      "Que articulos tienen PRECIOVENTA diferente al PRECIOVENTA medio de venta historico?",
      "Compara PRECIOVENTA en ARTICULO con AVG(PRECIOVENTA en DOCLIN). "
      "Diferencias grandes indican actualizacion de precios reciente.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO_CATALOGO, "
      "ROUND(AVG(CAST(L.PRECIO AS REAL)),2) AS PRECIO_MEDIO_HISTORICO, "
      "ROUND(A.PRECIOVENTA - AVG(CAST(L.PRECIO AS REAL)),2) AS DIFERENCIA "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE A.PRECIOVENTA > 0 GROUP BY L.CODARTICULO "
      "HAVING ABS(A.PRECIOVENTA - AVG(CAST(L.PRECIO AS REAL))) > 10 "
      "ORDER BY ABS(DIFERENCIA) DESC LIMIT 20",
      "Compras", "Comercial", "Calidad", "Medio", "", ""),

    q("cx_043", "Articulos con mayor numero de lineas en documentos",
      "Que articulos aparecen en mas lineas de documentos (todos los tipos)?",
      "COUNT(DOCLIN) por CODIGO sin filtro de tipo.",
      "SELECT " + _A + " AS ARTICULO, COUNT(L.CODARTICULO) AS N_LINEAS_TOTAL "
      "FROM DOCLIN L LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_LINEAS_TOTAL DESC LIMIT 20",
      "Compras", "Almacenero", "Operacional", "Bajo", "", ""),

    q("cx_044", "Articulos con codigo duplicado en DOCLIN",
      "Hay lineas de documento con el mismo articulo repetido en la misma factura?",
      "Detecta DOCLIN con mismo CODDOCUMENTO y CODIGO mas de una vez.",
      "SELECT CODDOCUMENTO, CODIGO, COUNT(*) AS N_LINEAS "
      "FROM DOCLIN WHERE CODIGO IS NOT NULL AND CODIGO!='' "
      "GROUP BY CODDOCUMENTO, L.CODIGO HAVING COUNT(*) > 1 "
      "ORDER BY N_LINEAS DESC LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Medio", "", ""),

    q("cx_045", "Articulos con cantidad cero en lineas de venta",
      "Hay lineas de venta con cantidad cero?",
      "DOCLIN JOIN DOCCAB TIPO=13 con CANTIDAD=0 o NULL.",
      "SELECT L.CODDOCUMENTO, " + _A + " AS ARTICULO, "
      "CAST(L.CANTIDAD AS REAL) AS CANTIDAD, CAST(L.PRECIO AS REAL) AS PRECIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE CAST(L.CANTIDAD AS REAL) = 0 OR L.CANTIDAD IS NULL LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Medio", "", ""),

    q("cx_046", "Articulos con PRECIOVENTA cero en lineas de venta",
      "Hay lineas de venta con PRECIOVENTA cero?",
      "DOCLIN JOIN DOCCAB TIPO=13 con PRECIOVENTA=0 o NULL.",
      "SELECT L.CODDOCUMENTO, " + _A + " AS ARTICULO, "
      "CAST(L.CANTIDAD AS REAL) AS CANTIDAD "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE CAST(L.PRECIO AS REAL) = 0 OR L.PRECIO IS NULL LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Alto", "", ""),

    q("cx_047", "Articulos con cantidad negativa en lineas de venta",
      "Hay lineas de venta con cantidad negativa?",
      "DOCLIN JOIN DOCCAB TIPO=13 con CANTIDAD < 0. Pueden ser devoluciones.",
      "SELECT L.CODDOCUMENTO, " + _A + " AS ARTICULO, "
      "CAST(L.CANTIDAD AS REAL) AS CANTIDAD, CAST(L.PRECIO AS REAL) AS PRECIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE CAST(L.CANTIDAD AS REAL) < 0 LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Alto", "", ""),

    q("cx_048", "Articulos con PRECIOVENTA negativo en lineas de venta",
      "Hay lineas de venta con PRECIOVENTA negativo?",
      "DOCLIN JOIN DOCCAB TIPO=13 con PRECIOVENTA < 0. Son errores de datos.",
      "SELECT L.CODDOCUMENTO, " + _A + " AS ARTICULO, "
      "CAST(L.CANTIDAD AS REAL) AS CANTIDAD, CAST(L.PRECIO AS REAL) AS PRECIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE CAST(L.PRECIO AS REAL) < 0 LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Critico", "", ""),

    q("cx_049", "Resumen de articulos por estado (baja/activo)",
      "Cuantos articulos estan activos y cuantos dados de baja?",
      "COUNT de ARTICULO agrupado por BAJA.",
      "SELECT CASE WHEN BAJA=1 THEN 'Dado de baja' ELSE 'Activo' END AS ESTADO, "
      "COUNT(*) AS N_ARTICULOS "
      "FROM ARTICULO GROUP BY BAJA",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_050", "Articulos activos con STOCKARTICULO cero",
      "Cuantos articulos activos no tienen STOCKARTICULO?",
      "ARTICULO con BAJA!=1 y STOCKARTICULO=0.",
      "SELECT COUNT(*) AS N_ACTIVOS_SIN_STOCKARTICULO "
      "FROM ARTICULO WHERE (BAJA IS NULL OR BAJA!=1) AND STOCKARTICULO=0",
      "Compras", "Almacenero", "Operacional", "Medio", "", ""),

    q("cx_051", "Articulos con mayor numero de SATs asociados",
      "Que articulos aparecen mas en SATs?",
      "COUNT(DOCLIN JOIN DOCCAB TIPO=2) por CODIGO.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_SATS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=2 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_SATS DESC LIMIT 20",
      "Compras", "Tecnico", "Proveedor", "Medio", "", ""),

    q("cx_052", "Articulos con mayor PRECIOCOSTE unitario",
      "Que articulos tienen mayor PRECIOVENTA de PRECIOCOSTE?",
      "MAX(PRECIOCOSTE) en ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE A.PRECIOCOSTE > 0 "
      "ORDER BY A.PRECIOCOSTE DESC LIMIT 20",
      "Compras", "Director", "Financiero", "Medio", "", ""),

    q("cx_053", "Articulos con mayor PRECIOVENTA de venta",
      "Que articulos tienen mayor PRECIOVENTA de venta en catalogo?",
      "MAX(PRECIOVENTA) en ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE A.PRECIOVENTA > 0 "
      "ORDER BY A.PRECIOVENTA DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Bajo", "", ""),

    q("cx_054", "Articulos con PRECIOVENTA de venta entre 100 y 500 euros",
      "Que articulos tienen PRECIOVENTA de venta en el rango 100-500 euros?",
      "ARTICULO con PRECIOVENTA BETWEEN 100 AND 500.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO, "
      "A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE A.PRECIOVENTA BETWEEN 100 AND 500 "
      "ORDER BY A.PRECIOVENTA DESC LIMIT 30",
      "Compras", "Comercial", "Producto", "Bajo", "", ""),

    q("cx_055", "Articulos con PRECIOVENTA de venta superior a 1000 euros",
      "Que articulos tienen PRECIOVENTA de venta superior a 1000 euros?",
      "ARTICULO con PRECIOVENTA > 1000.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE A.PRECIOVENTA > 1000 "
      "ORDER BY A.PRECIOVENTA DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Medio", "", ""),

    q("cx_056", "Articulos con PRECIOVENTA de venta inferior a 10 euros",
      "Que articulos tienen PRECIOVENTA de venta inferior a 10 euros?",
      "ARTICULO con PRECIOVENTA < 10 y PRECIOVENTA > 0.",
      "SELECT " + _A + " AS ARTICULO, ROUND(A.PRECIOVENTA,2) AS PRECIO, "
      "A.STOCKARTICULO AS STOCKARTICULO "
      "FROM ARTICULO A WHERE A.PRECIOVENTA < 10 AND A.PRECIOVENTA > 0 "
      "ORDER BY A.PRECIOVENTA ASC LIMIT 30",
      "Compras", "Comercial", "Producto", "Bajo", "", ""),

    q("cx_057", "Proveedores con TEL registrado",
      "Que porcentaje de proveedores tienen TEL registrado?",
      "COUNT de PROVEED con TEL no nulo vs total.",
      "SELECT COUNT(*) AS TOTAL_PROVEEDORES, "
      "SUM(CASE WHEN TEL IS NOT NULL AND TEL!='' THEN 1 ELSE 0 END) AS CON_TELEFONO, "
      "ROUND(100.0*SUM(CASE WHEN TEL IS NOT NULL AND TEL!='' THEN 1 ELSE 0 END)/COUNT(*),1) AS PCT "
      "FROM PROVEED",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_058", "Proveedores con nombre comercial y razon social distintos",
      "Que proveedores tienen nombre comercial diferente a razon social?",
      "PROVEED con NOMBRECOMERCIAL != RAZONSOCIAL.",
      "SELECT P.CODIGO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "FROM PROVEED P WHERE P.NOMBRECOMERCIAL IS NOT NULL AND P.RAZONSOCIAL IS NOT NULL "
      "AND P.NOMBRECOMERCIAL != P.RAZONSOCIAL LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_059", "Articulos con descripcion diferente al nombre",
      "Que articulos tienen descripcion diferente al nombre?",
      "ARTICULO con NOMBRE != DESCRIPCION. Puede indicar datos duplicados o inconsistentes.",
      "SELECT A.CODIGO, A.NOMBRE, A.DESCRIPCION "
      "FROM ARTICULO A WHERE A.NOMBRE IS NOT NULL AND A.DESCRIPCION IS NOT NULL "
      "AND A.NOMBRE != A.DESCRIPCION LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_060", "Articulos con codigo alfanumerico (no numerico)",
      "Hay articulos con codigo no numerico?",
      "ARTICULO con CODIGO que no es un numero puro. "
      "Puede causar problemas en JOINs con DOCLIN.CODIGO.",
      "SELECT A.CODIGO, " + _A + " AS NOMBRE "
      "FROM ARTICULO A WHERE CAST(A.CODIGO AS INTEGER) = 0 AND A.CODIGO != '0' LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Medio", "", ""),

    q("cx_061", "Articulos con ventas en SATs pero sin ventas en facturas",
      "Que articulos solo aparecen en SATs pero no en facturas?",
      "Articulos en DOCLIN JOIN DOCCAB TIPO=2 que no aparecen en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_SATS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=2 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE L.CODARTICULO NOT IN ("
      "SELECT DISTINCT L2.CODIGO FROM DOCLIN L2 "
      "JOIN DOCCAB D2 ON L2.CODDOCUMENTO=D2.CODIGO AND D2.TIPO=13 "
      "WHERE L2.CODIGO IS NOT NULL) "
      "GROUP BY L.CODARTICULO ORDER BY N_SATS DESC LIMIT 20",
      "Compras", "Tecnico", "Producto", "Medio", "", ""),

    q("cx_062", "Articulos con ventas en albaranes pero no en facturas",
      "Que articulos aparecen en albaranes pero no en facturas?",
      "Articulos en DOCLIN JOIN DOCCAB TIPO=11 que no aparecen en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_ALBARANES "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=11 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE L.CODARTICULO NOT IN ("
      "SELECT DISTINCT L2.CODIGO FROM DOCLIN L2 "
      "JOIN DOCCAB D2 ON L2.CODDOCUMENTO=D2.CODIGO AND D2.TIPO=13 "
      "WHERE L2.CODIGO IS NOT NULL) "
      "GROUP BY L.CODARTICULO ORDER BY N_ALBARANES DESC LIMIT 20",
      "Compras", "Almacenero", "Calidad", "Medio", "", ""),

    q("cx_063", "Articulos con ventas en presupuestos pero no en facturas",
      "Que articulos aparecen en presupuestos pero no en facturas?",
      "Articulos en DOCLIN JOIN DOCCAB TIPO=0 que no aparecen en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_PRESUPUESTOS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=0 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE L.CODARTICULO NOT IN ("
      "SELECT DISTINCT L2.CODIGO FROM DOCLIN L2 "
      "JOIN DOCCAB D2 ON L2.CODDOCUMENTO=D2.CODIGO AND D2.TIPO=13 "
      "WHERE L2.CODIGO IS NOT NULL) "
      "GROUP BY L.CODARTICULO ORDER BY N_PRESUPUESTOS DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Medio", "", ""),

    q("cx_064", "Articulos con mayor importe en presupuestos",
      "Que articulos tienen mayor importe en presupuestos?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=0 por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PRESUPUESTADO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=0 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PRESUPUESTADO DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Medio", "", ""),

    q("cx_065", "Articulos con mayor diferencia entre presupuestado y facturado",
      "Que articulos tienen mayor diferencia entre lo presupuestado y lo facturado?",
      "Compara SUM(CANTIDAD*PRECIOVENTA) en TIPO=0 vs TIPO=13 por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CASE WHEN D.TIPO=0 THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS PRESUPUESTADO, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS FACTURADO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO IN (0,13) "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO "
      "HAVING PRESUPUESTADO > 0 AND FACTURADO > 0 "
      "ORDER BY ABS(PRESUPUESTADO-FACTURADO) DESC LIMIT 20",
      "Compras", "Director", "Calidad", "Medio", "", ""),

    q("cx_066", "Articulos con mayor numero de clientes distintos que los compran",
      "Que articulos se venden a mas clientes distintos?",
      "COUNT(DISTINCT CODCLIENTE) por articulo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_CLIENTES DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Medio", "", ""),

    q("cx_067", "Articulos con mayor numero de agentes que los venden",
      "Que articulos son vendidos por mas agentes distintos?",
      "COUNT(DISTINCT CODAGENTE) por articulo en DOCLIN JOIN DOCCAB TIPO=13.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT D.CODAGENTE) AS N_AGENTES "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.CODAGENTE > 0 "
      "GROUP BY L.CODARTICULO ORDER BY N_AGENTES DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Bajo", "", ""),

    q("cx_068", "Articulos con mayor importe en SATs",
      "Que articulos generan mas importe en SATs?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=2 por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_SAT "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=2 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_SAT DESC LIMIT 20",
      "Compras", "Tecnico", "Producto", "Medio", "", ""),

    q("cx_069", "Articulos con mayor importe en albaranes",
      "Que articulos generan mas importe en albaranes?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=11 por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_ALBARAN "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=11 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_ALBARAN DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),

    q("cx_070", "Resumen de articulos por familia y proveedor",
      "Cuantos articulos hay por familia y proveedor?",
      "Cruza CODFAMILIA con PROVEEDDEFECTO en ARTICULO.",
      "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
      "COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL,'Sin proveedor') AS PROVEEDOR, "
      "COUNT(A.CODIGO) AS N_ARTICULOS "
      "FROM ARTICULO A LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "GROUP BY A.CODFAMILIA, A.PROVEEDDEFECTO ORDER BY N_ARTICULOS DESC LIMIT 30",
      "Compras", "Almacenero", "Proveedor", "Bajo", "", ""),

    q("cx_071", "Articulos con mayor importe total (ventas + SATs + albaranes)",
      "Que articulos generan mas importe en todos los tipos de documento?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB (todos los tipos) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_TOTAL "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_TOTAL DESC LIMIT 20",
      "Compras", "Director", "Producto", "Alto", "", ""),

    q("cx_072", "Articulos con mayor numero de documentos distintos",
      "En cuantos documentos distintos aparece cada articulo?",
      "COUNT(DISTINCT CODDOCUMENTO) por articulo en DOCLIN (todos los tipos).",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS "
      "FROM DOCLIN L LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_DOCUMENTOS DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),

    q("cx_073", "Articulos con mayor numero de lineas en presupuestos",
      "Que articulos aparecen mas en presupuestos?",
      "COUNT(DOCLIN JOIN DOCCAB TIPO=0) por CODIGO.",
      "SELECT " + _A + " AS ARTICULO, COUNT(L.CODARTICULO) AS N_LINEAS_PRESUPUESTO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=0 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_LINEAS_PRESUPUESTO DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Bajo", "", ""),

    q("cx_074", "Articulos con mayor numero de lineas en albaranes",
      "Que articulos aparecen mas en albaranes?",
      "COUNT(DOCLIN JOIN DOCCAB TIPO=11) por CODIGO.",
      "SELECT " + _A + " AS ARTICULO, COUNT(L.CODARTICULO) AS N_LINEAS_ALBARAN "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=11 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_LINEAS_ALBARAN DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),

    q("cx_075", "Articulos con mayor numero de lineas en SATs",
      "Que articulos aparecen mas en SATs?",
      "COUNT(DOCLIN JOIN DOCCAB TIPO=2) por CODIGO.",
      "SELECT " + _A + " AS ARTICULO, COUNT(L.CODARTICULO) AS N_LINEAS_SAT "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=2 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_LINEAS_SAT DESC LIMIT 20",
      "Compras", "Tecnico", "Producto", "Bajo", "", ""),

    q("cx_076", "Articulos con mayor importe en el ultimo mes",
      "Que articulos se han vendido mas en el ultimo mes?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=13 del mes actual.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_MES "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_MES DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Alto", "", ""),

    q("cx_077", "Articulos con mayor importe en el ultimo trimestre",
      "Que articulos se han vendido mas en los ultimos 3 meses?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=13 con FECHA >= date('now','-90 days').",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_90D "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.FECHA >= date('now','-90 days') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_90D DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Alto", "", ""),

    q("cx_078", "Articulos con mayor importe en el ultimo anio",
      "Que articulos se han vendido mas en el ultimo anio?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=13 del anio actual.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_ANIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_ANIO DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Alto", "", ""),

    q("cx_079", "Articulos con ventas crecientes por proveedor",
      "Que proveedores tienen articulos con ventas crecientes?",
      "Compara ventas del mes actual vs mes anterior por proveedor.",
      "SELECT " + _PA + " AS PROVEEDOR, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now','-1 month') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ANTERIOR "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO HAVING MES_ACTUAL > MES_ANTERIOR AND MES_ANTERIOR > 0 "
      "ORDER BY (MES_ACTUAL-MES_ANTERIOR) DESC LIMIT 20",
      "Compras", "Director", "Prediccion", "Medio", "", ""),

    q("cx_080", "Articulos con ventas decrecientes por proveedor",
      "Que proveedores tienen articulos con ventas decrecientes?",
      "Compara ventas del mes actual vs mes anterior por proveedor.",
      "SELECT " + _PA + " AS PROVEEDOR, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now','-1 month') THEN CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL) ELSE 0 END),2) AS MES_ANTERIOR "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN PROVEED P ON A.PROVEEDDEFECTO=P.CODIGO "
      "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO!='' "
      "GROUP BY A.PROVEEDDEFECTO HAVING MES_ACTUAL < MES_ANTERIOR AND MES_ACTUAL > 0 "
      "ORDER BY (MES_ANTERIOR-MES_ACTUAL) DESC LIMIT 20",
      "Compras", "Director", "Riesgo", "Medio", "", ""),

    q("cx_081", "Articulos con mayor numero de unidades en STOCKARTICULO por familia",
      "Que familias tienen mas unidades en STOCKARTICULO?",
      "SUM(STOCKARTICULO) por CODFAMILIA en ARTICULO.",
      "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
      "COUNT(A.CODIGO) AS N_ARTICULOS, SUM(A.STOCKARTICULO) AS STOCK_TOTAL "
      "FROM ARTICULO A LEFT JOIN FAMILIA F ON A.CODFAMILIA=F.CODIGO "
      "GROUP BY A.CODFAMILIA ORDER BY STOCK_TOTAL DESC LIMIT 20",
      "Compras", "Almacenero", "Operacional", "Medio", "", ""),

    q("cx_082", "Articulos con mayor numero de unidades vendidas en el anio",
      "Que articulos se han vendido en mas unidades este anio?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=13 del anio actual.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_ANIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_ANIO DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Alto", "", ""),

    q("cx_083", "Articulos con mayor numero de unidades vendidas en el mes",
      "Que articulos se han vendido en mas unidades este mes?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=13 del mes actual.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_MES "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_MES DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Alto", "", ""),

    q("cx_084", "Articulos con mayor diferencia entre STOCKARTICULO y ventas mensuales",
      "Que articulos tienen STOCKARTICULO muy superior a sus ventas mensuales?",
      "Compara STOCKARTICULO con SUM(CANTIDAD) del ultimo mes.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0),2) AS VENTAS_MES, "
      "ROUND(A.STOCKARTICULO - COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0),2) AS EXCESO "
      "FROM ARTICULO A LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "AND SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "WHERE A.STOCKARTICULO > 0 GROUP BY A.CODIGO "
      "ORDER BY EXCESO DESC LIMIT 20",
      "Compras", "Almacenero", "Optimizacion", "Alto", "", ""),

    q("cx_085", "Articulos con STOCKARTICULO suficiente para mas de 6 meses",
      "Que articulos tienen STOCKARTICULO para mas de 6 meses de ventas?",
      "Compara STOCKARTICULO con SUM(CANTIDAD) de los ultimos 6 meses / 6.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0)/6,2) AS VENTAS_MEDIA_MENSUAL, "
      "CASE WHEN COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0) > 0 "
      "THEN ROUND(A.STOCKARTICULO/(COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0)/6),1) "
      "ELSE NULL END AS MESES_STOCKARTICULO "
      "FROM ARTICULO A LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "AND D.FECHA >= date('now','-180 days') "
      "WHERE A.STOCKARTICULO > 0 GROUP BY A.CODIGO "
      "HAVING MESES_STOCKARTICULO > 6 ORDER BY MESES_STOCKARTICULO DESC LIMIT 20",
      "Compras", "Almacenero", "Riesgo", "Alto", "", ""),

    q("cx_086", "Articulos con STOCKARTICULO insuficiente para 1 mes de ventas",
      "Que articulos tienen STOCKARTICULO para menos de 1 mes de ventas?",
      "Compara STOCKARTICULO con SUM(CANTIDAD) de los ultimos 30 dias.",
      "SELECT " + _A + " AS ARTICULO, A.STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0),2) AS VENTAS_30D, "
      "CASE WHEN COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0) > 0 "
      "THEN ROUND(A.STOCKARTICULO/COALESCE(SUM(CAST(L.CANTIDAD AS REAL)),0)*30,1) "
      "ELSE NULL END AS DIAS_STOCKARTICULO "
      "FROM ARTICULO A LEFT JOIN DOCLIN L ON L.CODARTICULO=A.CODIGO "
      "LEFT JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "AND D.FECHA >= date('now','-30 days') "
      "WHERE A.STOCKARTICULO > 0 GROUP BY A.CODIGO "
      "HAVING DIAS_STOCKARTICULO < 30 AND VENTAS_30D > 0 ORDER BY DIAS_STOCKARTICULO ASC LIMIT 20",
      "Compras", "Almacenero", "Riesgo", "Critico", "", ""),

    q("cx_087", "Articulos con mayor numero de familias distintas en ventas",
      "Hay articulos que aparecen en familias distintas en diferentes documentos?",
      "Detecta inconsistencias de clasificacion en DOCLIN JOIN ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT A.CODFAMILIA) AS N_FAMILIAS "
      "FROM DOCLIN L LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING COUNT(DISTINCT A.CODFAMILIA) > 1 LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_088", "Articulos con mayor importe en documentos de pedido proveedor",
      "Que articulos aparecen mas en pedidos a proveedor (TIPO=12)?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=12 por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PEDIDO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PEDIDO DESC LIMIT 20",
      "Compras", "Administrativo", "Proveedor", "Medio", "", ""),

    q("cx_089", "Pedidos a proveedor por mes (TIPO=12)",
      "Cuantos pedidos a proveedor se emiten cada mes?",
      "COUNT y SUM de DOCCAB TIPO=12 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_PEDIDOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=12 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Compras", "Administrativo", "Proveedor", "Medio", "", ""),

    q("cx_090", "Pedidos a proveedor por anio",
      "Cuantos pedidos a proveedor se emiten cada anio?",
      "COUNT y SUM de DOCCAB TIPO=12 por anio.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_PEDIDOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=12 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Compras", "Director", "Proveedor", "Medio", "", ""),

    q("cx_091", "Pedidos a proveedor con mayor importe",
      "Cuales son los pedidos a proveedor de mayor importe?",
      "DOCCAB TIPO=12 ordenado por IMPORTETOTAL DESC.",
      "SELECT CODIGO, CODCLIENTE AS PROVEEDDEFECTO, FECHA, "
      "ROUND(IMPORTETOTAL,2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=12 ORDER BY IMPORTETOTAL DESC LIMIT 20",
      "Compras", "Director", "Proveedor", "Alto", "", ""),

    q("cx_092", "Articulos con mayor importe en pedidos a proveedor",
      "Que articulos se piden mas a proveedor?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=12 por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PEDIDO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_PEDIDAS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PEDIDO DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_093", "Articulos con mayor diferencia entre pedido y venta",
      "Que articulos se piden mas de lo que se venden?",
      "Compara SUM(CANTIDAD en TIPO=12) vs SUM(CANTIDAD en TIPO=13) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CASE WHEN D.TIPO=12 THEN CAST(L.CANTIDAD AS REAL) ELSE 0 END),2) AS PEDIDO, "
      "ROUND(SUM(CASE WHEN D.TIPO=13 THEN CAST(L.CANTIDAD AS REAL) ELSE 0 END),2) AS VENDIDO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO IN (12,13) "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING PEDIDO > 0 AND VENDIDO > 0 "
      "ORDER BY (PEDIDO-VENDIDO) DESC LIMIT 20",
      "Compras", "Almacenero", "Optimizacion", "Medio", "", ""),

    q("cx_094", "Articulos con mayor numero de pedidos a proveedor",
      "Que articulos se piden mas veces a proveedor?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB TIPO=12 por articulo.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_PEDIDOS DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Medio", "", ""),

    q("cx_095", "Articulos con mayor numero de pedidos a proveedor en el anio",
      "Que articulos se han pedido mas veces a proveedor este anio?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB TIPO=12 del anio actual.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY L.CODARTICULO ORDER BY N_PEDIDOS DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Medio", "", ""),

    q("cx_096", "Articulos con mayor numero de pedidos a proveedor en el mes",
      "Que articulos se han pedido mas veces a proveedor este mes?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB TIPO=12 del mes actual.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_PEDIDOS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY L.CODARTICULO ORDER BY N_PEDIDOS DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_097", "Articulos con mayor importe en pedidos a proveedor en el anio",
      "Que articulos se han pedido por mayor importe a proveedor este anio?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=12 del anio actual.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PEDIDO_ANIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PEDIDO_ANIO DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_098", "Articulos con mayor importe en pedidos a proveedor en el mes",
      "Que articulos se han pedido por mayor importe a proveedor este mes?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=12 del mes actual.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PEDIDO_MES "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PEDIDO_MES DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_099", "Articulos con mayor importe en pedidos a proveedor en el trimestre",
      "Que articulos se han pedido por mayor importe a proveedor en los ultimos 3 meses?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=12 con FECHA >= date('now','-90 days').",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PEDIDO_90D "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.FECHA >= date('now','-90 days') "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PEDIDO_90D DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_100", "Resumen ejecutivo de compras y STOCKARTICULO",
      "Cual es el resumen de los KPIs de compras y STOCKARTICULO mas importantes?",
      "Combina en una sola consulta: total articulos, con STOCKARTICULO, sin STOCKARTICULO, valor inventario.",
      "SELECT "
      "COUNT(*) AS TOTAL_ARTICULOS, "
      "SUM(CASE WHEN STOCKARTICULO > 0 THEN 1 ELSE 0 END) AS CON_STOCKARTICULO, "
      "SUM(CASE WHEN STOCKARTICULO = 0 THEN 1 ELSE 0 END) AS SIN_STOCKARTICULO, "
      "SUM(CASE WHEN STOCKARTICULO < 0 THEN 1 ELSE 0 END) AS STOCK_NEGATIVO, "
      "ROUND(SUM(STOCKARTICULO*PRECIOCOSTE),2) AS VALOR_INVENTARIO_COSTE, "
      "ROUND(SUM(STOCKARTICULO*PRECIOVENTA),2) AS VALOR_INVENTARIO_VENTA "
      "FROM ARTICULO WHERE BAJA IS NULL OR BAJA!=1",
      "Compras", "Director", "KPI", "Critico", "Resumen compras", ""),

    q("cx_101", "Articulos con mayor numero de proveedores distintos en ventas",
      "Hay articulos que se venden con distintos proveedores en diferentes documentos?",
      "Detecta inconsistencias de proveedor en DOCLIN JOIN ARTICULO.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT A.PROVEEDDEFECTO) AS N_PROVEEDORES "
      "FROM DOCLIN L LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING COUNT(DISTINCT A.PROVEEDDEFECTO) > 1 LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_102", "Articulos con mayor importe en documentos de todos los tipos",
      "Que articulos generan mas importe en todos los tipos de documento combinados?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB (todos los tipos) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_TOTAL_TODOS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_TOTAL_TODOS DESC LIMIT 20",
      "Compras", "Director", "Producto", "Alto", "", ""),

    q("cx_103", "Articulos con mayor numero de documentos distintos en el anio",
      "En cuantos documentos distintos aparece cada articulo este anio?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB del anio actual.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS_ANIO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,4)=strftime('%Y','now') "
      "GROUP BY L.CODARTICULO ORDER BY N_DOCUMENTOS_ANIO DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Medio", "", ""),

    q("cx_104", "Articulos con mayor numero de documentos distintos en el mes",
      "En cuantos documentos distintos aparece cada articulo este mes?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB del mes actual.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS_MES "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE SUBSTR(D.FECHA,1,7)=strftime('%Y-%m','now') "
      "GROUP BY L.CODARTICULO ORDER BY N_DOCUMENTOS_MES DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Alto", "", ""),

    q("cx_105", "Articulos con mayor numero de documentos distintos en el trimestre",
      "En cuantos documentos distintos aparece cada articulo en los ultimos 3 meses?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB con FECHA >= date('now','-90 days').",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS_90D "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.FECHA >= date('now','-90 days') "
      "GROUP BY L.CODARTICULO ORDER BY N_DOCUMENTOS_90D DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Alto", "", ""),

    q("cx_106", "Articulos con mayor numero de documentos distintos en los ultimos 6 meses",
      "En cuantos documentos distintos aparece cada articulo en los ultimos 6 meses?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB con FECHA >= date('now','-180 days').",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS_180D "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.FECHA >= date('now','-180 days') "
      "GROUP BY L.CODARTICULO ORDER BY N_DOCUMENTOS_180D DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Medio", "", ""),

    q("cx_107", "Articulos con mayor numero de documentos distintos en el ultimo anio",
      "En cuantos documentos distintos aparece cada articulo en el ultimo anio?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN JOIN DOCCAB con FECHA >= date('now','-365 days').",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS_365D "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.FECHA >= date('now','-365 days') "
      "GROUP BY L.CODARTICULO ORDER BY N_DOCUMENTOS_365D DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Medio", "", ""),

    q("cx_108", "Articulos con mayor numero de documentos distintos en toda la historia",
      "En cuantos documentos distintos aparece cada articulo en toda la historia?",
      "COUNT(DISTINCT CODDOCUMENTO) en DOCLIN (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS_HISTORICO "
      "FROM DOCLIN L LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_DOCUMENTOS_HISTORICO DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),

    q("cx_109", "Articulos con mayor importe en toda la historia",
      "Que articulos han generado mas importe en toda la historia de documentos?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB (todos los tipos, sin filtro) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_HISTORICO DESC LIMIT 20",
      "Compras", "Director", "Producto", "Alto", "", ""),

    q("cx_110", "Articulos con mayor importe en ventas en toda la historia",
      "Que articulos han generado mas importe en ventas en toda la historia?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=13 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_VENTAS_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_VENTAS_HISTORICO DESC LIMIT 20",
      "Compras", "Director", "Producto", "Alto", "", ""),

    q("cx_111", "Articulos con mayor importe en SATs en toda la historia",
      "Que articulos han generado mas importe en SATs en toda la historia?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=2 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_SAT_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=2 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_SAT_HISTORICO DESC LIMIT 20",
      "Compras", "Tecnico", "Producto", "Medio", "", ""),

    q("cx_112", "Articulos con mayor importe en albaranes en toda la historia",
      "Que articulos han generado mas importe en albaranes en toda la historia?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=11 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_ALBARAN_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=11 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_ALBARAN_HISTORICO DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),

    q("cx_113", "Articulos con mayor importe en presupuestos en toda la historia",
      "Que articulos han generado mas importe en presupuestos en toda la historia?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=0 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PRESUPUESTO_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=0 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PRESUPUESTO_HISTORICO DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Medio", "", ""),

    q("cx_114", "Articulos con mayor importe en pedidos a proveedor en toda la historia",
      "Que articulos han generado mas importe en pedidos a proveedor en toda la historia?",
      "SUM(CANTIDAD*PRECIOVENTA) en DOCLIN JOIN DOCCAB TIPO=12 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) AS IMPORTE_PEDIDO_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY IMPORTE_PEDIDO_HISTORICO DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_115", "Articulos con mayor numero de unidades en toda la historia",
      "Que articulos han tenido mas unidades vendidas en toda la historia?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=13 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_HISTORICO DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Alto", "", ""),

    q("cx_116", "Articulos con mayor numero de unidades en SATs en toda la historia",
      "Que articulos han tenido mas unidades en SATs en toda la historia?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=2 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_SAT_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=2 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_SAT_HISTORICO DESC LIMIT 20",
      "Compras", "Tecnico", "Producto", "Medio", "", ""),

    q("cx_117", "Articulos con mayor numero de unidades en albaranes en toda la historia",
      "Que articulos han tenido mas unidades en albaranes en toda la historia?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=11 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_ALBARAN_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=11 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_ALBARAN_HISTORICO DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),

    q("cx_118", "Articulos con mayor numero de unidades en presupuestos en toda la historia",
      "Que articulos han tenido mas unidades en presupuestos en toda la historia?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=0 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_PRESUPUESTO_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=0 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_PRESUPUESTO_HISTORICO DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Bajo", "", ""),

    q("cx_119", "Articulos con mayor numero de unidades en pedidos a proveedor en toda la historia",
      "Que articulos han tenido mas unidades en pedidos a proveedor en toda la historia?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB TIPO=12 (sin filtro de fecha) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_PEDIDO_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=12 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_PEDIDO_HISTORICO DESC LIMIT 20",
      "Compras", "Almacenero", "Proveedor", "Alto", "", ""),

    q("cx_120", "Articulos con mayor numero de unidades en todos los documentos en toda la historia",
      "Que articulos han tenido mas unidades en todos los documentos en toda la historia?",
      "SUM(CANTIDAD) en DOCLIN JOIN DOCCAB (todos los tipos, sin filtro) por articulo.",
      "SELECT " + _A + " AS ARTICULO, "
      "ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) AS UNIDADES_TOTAL_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY UNIDADES_TOTAL_HISTORICO DESC LIMIT 20",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),

    q("cx_121", "Articulos con mayor numero de clientes distintos en toda la historia",
      "A cuantos clientes distintos se ha vendido cada articulo en toda la historia?",
      "COUNT(DISTINCT CODCLIENTE) en DOCLIN JOIN DOCCAB TIPO=13 (sin filtro) por articulo.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT D.CODCLIENTE) AS N_CLIENTES_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO ORDER BY N_CLIENTES_HISTORICO DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Medio", "", ""),

    q("cx_122", "Articulos con mayor numero de agentes distintos en toda la historia",
      "Cuantos agentes distintos han vendido cada articulo en toda la historia?",
      "COUNT(DISTINCT CODAGENTE) en DOCLIN JOIN DOCCAB TIPO=13 (sin filtro) por articulo.",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT D.CODAGENTE) AS N_AGENTES_HISTORICO "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO AND D.TIPO=13 "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "WHERE D.CODAGENTE > 0 "
      "GROUP BY L.CODARTICULO ORDER BY N_AGENTES_HISTORICO DESC LIMIT 20",
      "Compras", "Comercial", "Producto", "Bajo", "", ""),

    q("cx_123", "Articulos con mayor numero de familias distintas en toda la historia",
      "Hay articulos que aparecen en familias distintas en diferentes documentos historicos?",
      "Detecta inconsistencias de clasificacion en DOCLIN JOIN ARTICULO (sin filtro).",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT A.CODFAMILIA) AS N_FAMILIAS_HISTORICO "
      "FROM DOCLIN L LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING COUNT(DISTINCT A.CODFAMILIA) > 1 LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_124", "Articulos con mayor numero de proveedores distintos en toda la historia",
      "Hay articulos que aparecen con proveedores distintos en diferentes documentos historicos?",
      "Detecta inconsistencias de proveedor en DOCLIN JOIN ARTICULO (sin filtro).",
      "SELECT " + _A + " AS ARTICULO, COUNT(DISTINCT A.PROVEEDDEFECTO) AS N_PROVEEDORES_HISTORICO "
      "FROM DOCLIN L LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO HAVING COUNT(DISTINCT A.PROVEEDDEFECTO) > 1 LIMIT 20",
      "Compras", "Administrativo", "Calidad", "Bajo", "", ""),

    q("cx_125", "Articulos con mayor numero de documentos distintos en toda la historia por tipo",
      "En cuantos documentos de cada tipo aparece cada articulo en toda la historia?",
      "COUNT(DISTINCT CODDOCUMENTO) por articulo y tipo en DOCLIN JOIN DOCCAB (sin filtro).",
      "SELECT " + _A + " AS ARTICULO, D.TIPO, COUNT(DISTINCT L.CODDOCUMENTO) AS N_DOCUMENTOS "
      "FROM DOCLIN L JOIN DOCCAB D ON L.CODDOCUMENTO=D.CODIGO "
      "LEFT JOIN ARTICULO A ON L.CODARTICULO=A.CODIGO "
      "GROUP BY L.CODARTICULO, D.TIPO ORDER BY N_DOCUMENTOS DESC LIMIT 40",
      "Compras", "Almacenero", "Producto", "Bajo", "", ""),
]
