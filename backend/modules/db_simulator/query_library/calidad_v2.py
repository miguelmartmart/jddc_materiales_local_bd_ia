"""calidad_v2.py — 25 consultas adicionales de Calidad / Integridad de datos (v2).

DEVIA: fichero < 500 líneas, módulo independiente, sin lógica de negocio.
"""
from backend.modules.db_simulator.query_library.builder import q

QUERIES_CALIDAD_V2: list = [
    q("cv2_001", "Documentos sin cliente asignado", "Docs sin cliente",
      "Documentos DOCCAB con CODCLIENTE nulo o cero que no tienen cliente asignado.",
      "SELECT CODIGO, TIPO, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE CODCLIENTE IS NULL OR CODCLIENTE=0 ORDER BY FECHA DESC LIMIT 20",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_002", "Artículos sin PRECIOVENTA de venta", "Artículos con PRECIOVENTA cero",
      "Artículos con PRECIOVENTA=0 o nulo que no pueden facturarse correctamente.",
      "SELECT CODIGO, NOMBRE, PRECIOCOSTE FROM ARTICULO "
      "WHERE PRECIOVENTA=0 OR PRECIOVENTA IS NULL ORDER BY NOMBRE LIMIT 30",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_003", "Líneas de documento sin artículo asignado", "Líneas sin artículo",
      "Líneas DOCLIN con CODIGO nulo o cero que no tienen artículo asignado.",
      "SELECT L.CODARTICULO, L.CODDOCUMENTO, L.CANTIDAD, L.PRECIO "
      "FROM DOCLIN L WHERE L.CODARTICULO IS NULL OR L.CODARTICULO=0 LIMIT 20",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_004", "Documentos con fecha futura", "Fechas futuras en documentos",
      "Documentos DOCCAB con FECHA superior a la fecha actual, posibles errores de entrada.",
      "SELECT CODIGO, TIPO, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE FECHA > DATE('now') ORDER BY FECHA ASC LIMIT 20",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_005", "Documentos con fecha anterior a 2000", "Fechas históricas anómalas",
      "Documentos con FECHA anterior a 2000 que pueden ser errores de entrada.",
      "SELECT CODIGO, TIPO, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE FECHA < '2000-01-01' ORDER BY FECHA ASC LIMIT 20",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_006", "Artículos duplicados por nombre", "Posibles duplicados en catálogo",
      "Artículos con el mismo NOMBRE que pueden ser duplicados en el catálogo.",
      "SELECT NOMBRE, COUNT(*) AS N_DUPLICADOS FROM ARTICULO "
      "GROUP BY NOMBRE HAVING N_DUPLICADOS>1 ORDER BY N_DUPLICADOS DESC LIMIT 20",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_007", "Líneas de documento con cantidad cero o negativa", "Cantidades anómalas",
      "Líneas DOCLIN con CANTIDAD<=0 que pueden indicar errores de registro.",
      "SELECT L.CODARTICULO, L.CODDOCUMENTO, L.CODARTICULO, L.CANTIDAD, L.PRECIO "
      "FROM DOCLIN L WHERE L.CANTIDAD<=0 ORDER BY L.CANTIDAD ASC LIMIT 20",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_008", "Líneas de documento con PRECIOVENTA negativo", "Precios negativos en líneas",
      "Líneas DOCLIN con PRECIOVENTA<0 que pueden indicar errores o abonos no registrados correctamente.",
      "SELECT L.CODARTICULO, L.CODDOCUMENTO, L.CODARTICULO, L.CANTIDAD, L.PRECIO "
      "FROM DOCLIN L WHERE L.PRECIO<0 ORDER BY L.PRECIO ASC LIMIT 20",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_009", "Documentos sin líneas de detalle", "Documentos vacíos",
      "Documentos DOCCAB que no tienen ninguna línea en DOCLIN.",
      "SELECT D.CODIGO, D.TIPO, D.FECHA, D.IMPORTETOTAL "
      "FROM DOCCAB D WHERE NOT EXISTS ("
      "SELECT 1 FROM DOCLIN L WHERE L.CODDOCUMENTO=D.CODIGO) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_010", "Artículos con PRECIOCOSTE superior al PRECIOVENTA de venta", "Margen negativo",
      "Artículos donde PRECIOCOSTE>PRECIOVENTA generan pérdida en cada venta.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE, ROUND(PRECIOVENTA-PRECIOCOSTE,2) AS MARGEN "
      "FROM ARTICULO WHERE PRECIOVENTA>0 AND PRECIOCOSTE>PRECIOVENTA ORDER BY MARGEN ASC LIMIT 20",
      "Todos", "Todos", "Alerta", "Critico", "", ""),

    q("cv2_011", "Documentos con IMPORTETOTAL diferente a la suma de líneas", "Descuadre cabecera-líneas",
      "Documentos donde IMPORTETOTAL no coincide con la suma de CANTIDAD*PRECIOVENTA de sus líneas.",
      "SELECT D.CODIGO, D.TIPO, D.IMPORTETOTAL, "
      "ROUND(SUM(L.CANTIDAD*L.PRECIO),2) AS SUMA_LINEAS, "
      "ROUND(D.IMPORTETOTAL-SUM(L.CANTIDAD*L.PRECIO),2) AS DIFERENCIA "
      "FROM DOCCAB D JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
      "GROUP BY D.CODIGO, D.TIPO, D.IMPORTETOTAL "
      "HAVING ABS(DIFERENCIA)>0.01 ORDER BY ABS(DIFERENCIA) DESC LIMIT 20",
      "Todos", "Todos", "Alerta", "Critico", "", ""),

    q("cv2_012", "Artículos sin código de familia", "Artículos sin clasificar",
      "Artículos con CODFAMILIA nulo o cero que no están clasificados.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE "
      "FROM ARTICULO WHERE CODFAMILIA IS NULL OR CODFAMILIA=0 ORDER BY NOMBRE LIMIT 30",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_013", "Clientes sin ningún documento asociado", "Clientes sin actividad",
      "Clientes registrados en el sistema que no tienen ningún documento en DOCCAB.",
      "SELECT C.CODIGO, COALESCE(C.NOMBRECOMERCIAL,C.RAZONSOCIAL) FROM CLIENTE C "
      "WHERE NOT EXISTS (SELECT 1 FROM DOCCAB D WHERE D.CODCLIENTE=C.CODIGO) "
      "ORDER BY COALESCE(C.NOMBRECOMERCIAL,C.RAZONSOCIAL) LIMIT 30",
      "Todos", "Todos", "Alerta", "Bajo", "", ""),

    q("cv2_014", "Documentos con IMPORTEBASE mayor que IMPORTETOTAL", "IMPORTEIVA negativo implícito",
      "Documentos donde IMPORTEBASE>IMPORTETOTAL, lo que implicaría IMPORTEIVA negativo.",
      "SELECT CODIGO, TIPO, IMPORTEBASE, IMPORTETOTAL, "
      "ROUND(IMPORTETOTAL-IMPORTEBASE,2) AS IVA_CALCULADO "
      "FROM DOCCAB WHERE IMPORTEBASE>IMPORTETOTAL AND IMPORTETOTAL>0 "
      "ORDER BY IVA_CALCULADO ASC LIMIT 20",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_015", "Líneas con artículo no existente en catálogo", "Referencias huérfanas",
      "Líneas DOCLIN con CODIGO que no existe en la tabla ARTICULO.",
      "SELECT L.CODARTICULO, L.CODDOCUMENTO, L.CODARTICULO, L.CANTIDAD, L.PRECIO "
      "FROM DOCLIN L WHERE NOT EXISTS ("
      "SELECT 1 FROM ARTICULO A WHERE A.CODIGO=L.CODARTICULO) "
      "AND L.CODARTICULO IS NOT NULL AND L.CODARTICULO!=0 LIMIT 20",
      "Todos", "Todos", "Alerta", "Critico", "", ""),

    q("cv2_016", "Documentos con cliente no existente en tabla CLIENTE", "Clientes huérfanos",
      "Documentos DOCCAB con CODCLIENTE que no existe en la tabla CLIENTE.",
      "SELECT D.CODIGO, D.TIPO, D.CODCLIENTE, D.FECHA, D.IMPORTETOTAL "
      "FROM DOCCAB D WHERE NOT EXISTS ("
      "SELECT 1 FROM CLIENTE C WHERE C.CODIGO=D.CODCLIENTE) "
      "AND D.CODCLIENTE IS NOT NULL AND D.CODCLIENTE!=0 LIMIT 20",
      "Todos", "Todos", "Alerta", "Critico", "", ""),

    q("cv2_017", "Artículos con PRECIOVENTA igual al PRECIOCOSTE (margen cero)", "Artículos sin margen",
      "Artículos donde PRECIOVENTA=PRECIOCOSTE, lo que implica margen cero en su venta.",
      "SELECT CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE "
      "FROM ARTICULO WHERE PRECIOVENTA>0 AND PRECIOCOSTE>0 AND ABS(PRECIOVENTA-PRECIOCOSTE)<0.01 "
      "ORDER BY NOMBRE LIMIT 20",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_018", "Movimientos de caja sin fecha", "Caja sin fecha",
      "Movimientos de caja con FECHA nula que no pueden ordenarse cronológicamente.",
      "SELECT CODIGO, IMPORTE FROM CAJA WHERE FECHA IS NULL LIMIT 20",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_019", "Documentos con agente no válido", "Facturas con agente cero",
      "Facturas TIPO=13 con CODAGENTE=0 o nulo que no tienen agente asignado.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND (CODAGENTE IS NULL OR CODAGENTE=0) "
      "ORDER BY FECHA DESC LIMIT 20",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_020", "Resumen de integridad: conteo de anomalías por tipo", "Dashboard de calidad de datos",
      "Cuenta el número de anomalías detectadas en cada categoría de integridad.",
      "SELECT 'Docs sin cliente' AS ANOMALIA, COUNT(*) AS N FROM DOCCAB WHERE CODCLIENTE IS NULL OR CODCLIENTE=0 "
      "UNION ALL SELECT 'Articulos sin PRECIOVENTA', COUNT(*) FROM ARTICULO WHERE PRECIOVENTA=0 OR PRECIOVENTA IS NULL "
      "UNION ALL SELECT 'Lineas sin articulo', COUNT(*) FROM DOCLIN WHERE CODIGO IS NULL OR CODARTICULO=0 "
      "UNION ALL SELECT 'Docs sin lineas', COUNT(*) FROM DOCCAB D WHERE NOT EXISTS (SELECT 1 FROM DOCLIN L WHERE L.CODDOCUMENTO=CODIGO) "
      "UNION ALL SELECT 'Articulos margen negativo', COUNT(*) FROM ARTICULO WHERE PRECIOVENTA>0 AND PRECIOCOSTE>PRECIOVENTA "
      "ORDER BY N DESC",
      "Todos", "Todos", "KPI", "Critico", "", ""),

    q("cv2_021", "Familias sin artículos asignados", "Familias vacías",
      "Familias que no tienen ningún artículo asignado en el catálogo.",
      "SELECT F.CODIGO, F.NOMBRE FROM FAMILIA F "
      "WHERE NOT EXISTS (SELECT 1 FROM ARTICULO A WHERE A.CODFAMILIA=F.CODIGO) "
      "ORDER BY F.NOMBRE",
      "Todos", "Todos", "Alerta", "Bajo", "", ""),

    q("cv2_022", "Documentos con TIPO no reconocido", "Tipos de documento desconocidos",
      "Documentos con TIPO que no corresponde a ningún tipo conocido del sistema.",
      "SELECT TIPO, COUNT(*) AS N_DOCS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO NOT IN (0,2,11,12,13,14,20,21) "
      "GROUP BY TIPO ORDER BY N_DOCS DESC LIMIT 10",
      "Todos", "Todos", "Alerta", "Medio", "", ""),

    q("cv2_023", "Artículos con nombre vacío o nulo", "Artículos sin nombre",
      "Artículos con NOMBRE nulo o vacío que no pueden identificarse correctamente.",
      "SELECT CODIGO, PRECIOVENTA, PRECIOCOSTE FROM ARTICULO "
      "WHERE NOMBRE IS NULL OR TRIM(NOMBRE)='' ORDER BY CODIGO LIMIT 20",
      "Todos", "Todos", "Alerta", "Alto", "", ""),

    q("cv2_024", "Líneas de documento con documento cabecera inexistente", "Líneas huérfanas",
      "Líneas DOCLIN cuyo CODDOCUMENTO no existe en DOCCAB.",
      "SELECT L.CODARTICULO, L.CODDOCUMENTO, L.CODARTICULO, L.CANTIDAD "
      "FROM DOCLIN L WHERE NOT EXISTS ("
      "SELECT 1 FROM DOCCAB D WHERE CODIGO=L.CODDOCUMENTO) LIMIT 20",
      "Todos", "Todos", "Alerta", "Critico", "", ""),

    q("cv2_025", "Porcentaje de documentos con datos completos", "Completitud de datos",
      "Porcentaje de documentos DOCCAB que tienen cliente, fecha e importe válidos.",
      "SELECT COUNT(*) AS TOTAL_DOCS, "
      "SUM(CASE WHEN CODCLIENTE>0 AND FECHA IS NOT NULL AND IMPORTETOTAL>0 THEN 1 ELSE 0 END) AS COMPLETOS, "
      "ROUND(100.0*SUM(CASE WHEN CODCLIENTE>0 AND FECHA IS NOT NULL AND IMPORTETOTAL>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS PCT_COMPLETOS "
      "FROM DOCCAB",
      "Todos", "Todos", "KPI", "Alto", "", ""),
]
