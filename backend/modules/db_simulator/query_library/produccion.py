"""produccion.py — Consultas de Certificaciones, Producción y documentos de obra.

Tipos de documento cubiertos:
  51 = certificación
  52 = producción
  61 = certificación de subcontrata

Clasificación:
  - tipo="Certificaciones" → consultas sobre TIPO 51, 61, o mixtas 51+52+61
  - tipo="KPI"             → KPIs genéricos de producción
  - tipo="Financiero"      → análisis de importes
  - tipo="Operacional"     → listados y consultas puntuales

NOTAS DE COMPATIBILIDAD:
  - Las queries usan SQLite. El query_translator las convierte a Firebird automáticamente.
  - SUBSTR(FECHA,1,4) → SUBSTRING(FECHA FROM 1 FOR 4) en Firebird
  - STRFTIME('%Y','now') → EXTRACT(YEAR FROM CURRENT_DATE) en Firebird
  - DATE('now','-N months') → DATEADD(-N MONTH TO CURRENT_DATE) en Firebird
  - El simulador tiene datos de 2024; la BD real (Firebird) tiene datos actuales.

DATOS DEL SIMULADOR (verificados 2024-06-24):
  TIPO 51 (Certificación):       20 docs, importe ~1.324.362 €
  TIPO 52 (Producción):          15 docs, importe ~434.712 €
  TIPO 61 (Cert. Subcontrata):   10 docs, importe ~352.315 €
  Rango de fechas: 2024-01-xx a 2024-12-xx
"""
from backend.modules.db_simulator.query_library.builder import q

QUERIES_PRODUCCION: list = [

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE A: CERTIFICACIONES (TIPO=51) — tipo="Certificaciones"
    # ══════════════════════════════════════════════════════════════════════════

    q("prod_001",
      "Total de certificaciones",
      "¿Cuántas certificaciones hay en total?",
      "Cuenta todos los documentos de tipo 51 (certificación). "
      "Devuelve un único número para verificar rápidamente la actividad.",
      "SELECT COUNT(*) AS TOTAL_CERTIFICACIONES FROM DOCCAB WHERE TIPO=51",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Total Certificaciones",
      "KPI de un vistazo: volumen total de certificaciones en la BD."),

    q("prod_002",
      "Certificaciones por año",
      "¿Cuántas certificaciones se han hecho cada año?",
      "Agrupa certificaciones (TIPO=51) por año para ver la evolución anual.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=51 "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Certificaciones por Año",
      "Compara la actividad de certificaciones año a año."),

    q("prod_003",
      "Certificaciones por mes (año más reciente con datos)",
      "¿Cuántas certificaciones hubo cada mes en el año con más actividad?",
      "Agrupa certificaciones (TIPO=51) por mes del año con más documentos.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=51 "
      "AND SUBSTR(FECHA,1,4) = ("
      "  SELECT SUBSTR(FECHA,1,4) FROM DOCCAB WHERE TIPO=51 "
      "  GROUP BY SUBSTR(FECHA,1,4) ORDER BY COUNT(*) DESC LIMIT 1"
      ") "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Certificaciones Mensuales",
      "Identifica los meses con más actividad de certificación."),

    q("prod_004",
      "Certificaciones en 2024",
      "¿Cuántas certificaciones se hicieron en 2024?",
      "Cuenta y suma certificaciones (TIPO=51) del año 2024. "
      "Devuelve tres datos: número, importe total e importe medio.",
      "SELECT COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO "
      "FROM DOCCAB WHERE TIPO=51 AND SUBSTR(FECHA,1,4)='2024'",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Certificaciones 2024",
      "Consulta directa de certificaciones en 2024."),

    q("prod_004b",
      "Certificaciones en abril 2025",
      "¿Cuántas certificaciones se hicieron en abril de 2025?",
      "Cuenta certificaciones (TIPO=51) con fecha en abril de 2025. "
      "En la BD real devuelve datos reales; en el simulador puede devolver 0 (datos solo hasta 2024).",
      "SELECT COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO "
      "FROM DOCCAB WHERE TIPO=51 AND SUBSTR(FECHA,1,7)='2025-04'",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Certificaciones Abril 2025",
      "Consulta puntual de certificaciones en abril 2025."),

    q("prod_005",
      "Certificaciones por mes en 2024",
      "¿Cuántas certificaciones hubo cada mes en 2024?",
      "Desglose mensual de certificaciones (TIPO=51) durante 2024.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=51 AND SUBSTR(FECHA,1,4)='2024' "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Certificaciones 2024 por Mes",
      "Analiza la distribución mensual de certificaciones en 2024."),

    q("prod_006",
      "Importe total de certificaciones por año",
      "¿Cuál es el importe total de certificaciones por año?",
      "Suma IMPORTETOTAL de certificaciones (TIPO=51) agrupado por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO, "
      "ROUND(MAX(IMPORTETOTAL),2) AS IMPORTE_MAXIMO "
      "FROM DOCCAB WHERE TIPO=51 "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Importe Certificaciones por Año",
      "Evalúa el valor económico de las certificaciones."),

    q("prod_007",
      "Certificaciones por cliente",
      "¿Cuántas certificaciones tiene cada cliente?",
      "Agrupa certificaciones (TIPO=51) por CODCLIENTE.",
      "SELECT CODCLIENTE, COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=51 AND CODCLIENTE IS NOT NULL "
      "GROUP BY CODCLIENTE ORDER BY N_CERTIFICACIONES DESC LIMIT 20",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Certificaciones por Cliente",
      "Identifica los clientes con más certificaciones."),

    q("prod_008",
      "Últimas 20 certificaciones",
      "¿Cuáles son las certificaciones más recientes?",
      "Lista las 20 certificaciones (TIPO=51) más recientes con su importe.",
      "SELECT CODIGO, SERIE, NUMERO, FECHA, CODCLIENTE, "
      "ROUND(IMPORTEBASE,2) AS BASE, ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=51 ORDER BY FECHA DESC, CODIGO DESC LIMIT 20",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Últimas Certificaciones",
      "Revisa las certificaciones más recientes."),

    q("prod_009",
      "Comparativa certificaciones: dos años consecutivos",
      "¿Cómo han evolucionado las certificaciones entre los dos últimos años con datos?",
      "Compara número e importe de certificaciones (TIPO=51) entre los dos años más recientes.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=51 "
      "AND SUBSTR(FECHA,1,4) IN ("
      "  SELECT DISTINCT SUBSTR(FECHA,1,4) FROM DOCCAB WHERE TIPO=51 "
      "  ORDER BY SUBSTR(FECHA,1,4) DESC LIMIT 2"
      ") "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Evolución Certificaciones",
      "Evalúa el crecimiento o caída de certificaciones entre los últimos años."),

    # ── KPI de un número: Certificaciones (TIPO=51) ───────────────────────────

    q("prod_009b",
      "Solo el número: cuántas certificaciones en total",
      "Dame solo el número de certificaciones que hay",
      "Un único valor: total de certificaciones (TIPO=51) en la BD.",
      "SELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO=51",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Número Certificaciones",
      "Responde directamente a '¿cuántas certificaciones hay?'"),

    q("prod_009c",
      "Número de certificaciones en 2024 (KPI simple)",
      "¿Cuántas certificaciones se emitieron en 2024? Dame solo el número.",
      "Un único número: certificaciones (TIPO=51) con fecha en 2024.",
      "SELECT COUNT(*) AS CERT_2024 FROM DOCCAB WHERE TIPO=51 AND SUBSTR(FECHA,1,4)='2024'",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Certificaciones 2024 (n)",
      "KPI mínimo: número de certificaciones en 2024."),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE B: PRODUCCIÓN (TIPO=52) — tipo="Certificaciones" (mismo dominio)
    # ══════════════════════════════════════════════════════════════════════════

    q("prod_010",
      "Total de registros de producción",
      "¿Cuántos registros de producción hay en total?",
      "Cuenta todos los documentos de tipo 52 (producción) en DOCCAB.",
      "SELECT COUNT(*) AS TOTAL_PRODUCCION FROM DOCCAB WHERE TIPO=52",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Total Producción",
      "Revisa el volumen total de registros de producción."),

    q("prod_011",
      "Producción por año",
      "¿Cuántos registros de producción hay por año?",
      "Agrupa registros de producción (TIPO=52) por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_PRODUCCION, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=52 "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Producción por Año",
      "Analiza la evolución anual de la producción."),

    q("prod_012",
      "Producción por mes en 2024",
      "¿Cuántos registros de producción hubo por mes en 2024?",
      "Desglose mensual de producción (TIPO=52) durante 2024.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_PRODUCCION, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=52 AND SUBSTR(FECHA,1,4)='2024' "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Producción 2024 por Mes",
      "Identifica los meses con más actividad productiva en 2024."),

    q("prod_013",
      "Producción en 2024 (KPI simple)",
      "¿Cuántos registros de producción hubo en 2024? Dame el número.",
      "Cuenta registros de producción (TIPO=52) con fecha en 2024. "
      "Devuelve: count, importe total, importe medio.",
      "SELECT COUNT(*) AS N_PRODUCCION, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO "
      "FROM DOCCAB WHERE TIPO=52 AND SUBSTR(FECHA,1,4)='2024'",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Producción 2024 (n)",
      "KPI mínimo: registros de producción en 2024."),

    q("prod_014",
      "Últimas 20 órdenes de producción",
      "¿Cuáles son las órdenes de producción más recientes?",
      "Lista los 20 registros de producción (TIPO=52) más recientes.",
      "SELECT CODIGO, SERIE, NUMERO, FECHA, CODCLIENTE, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=52 ORDER BY FECHA DESC, CODIGO DESC LIMIT 20",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Últimas Órdenes Producción",
      "Revisa las órdenes de producción más recientes."),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE C: CERTIFICACIONES DE SUBCONTRATA (TIPO=61)
    # ══════════════════════════════════════════════════════════════════════════

    q("prod_016",
      "Total de certificaciones de subcontrata",
      "¿Cuántas certificaciones de subcontrata hay en total?",
      "Cuenta todos los documentos de tipo 61 (certificación de subcontrata).",
      "SELECT COUNT(*) AS TOTAL_CERT_SUBCONTRATA FROM DOCCAB WHERE TIPO=61",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Total Cert. Subcontrata",
      "Revisa el volumen de certificaciones de subcontrata."),

    q("prod_017",
      "Certificaciones de subcontrata por año",
      "¿Cuántas certificaciones de subcontrata hay por año?",
      "Agrupa certificaciones de subcontrata (TIPO=61) por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_CERT_SUBCONTRATA, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=61 "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Cert. Subcontrata por Año",
      "Analiza la evolución anual de certificaciones de subcontrata."),

    q("prod_018",
      "Certificaciones de subcontrata por mes en 2024",
      "¿Cuántas certificaciones de subcontrata hubo por mes en 2024?",
      "Desglose mensual de certificaciones de subcontrata (TIPO=61) durante 2024.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=61 AND SUBSTR(FECHA,1,4)='2024' "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Cert. Subcontrata 2024 por Mes",
      "Identifica los meses con más actividad de subcontrata en 2024."),

    q("prod_019",
      "Importe total de certificaciones de subcontrata por año",
      "¿Cuál es el gasto en subcontrata por año?",
      "Suma IMPORTETOTAL de certificaciones de subcontrata (TIPO=61) por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS MEDIA "
      "FROM DOCCAB WHERE TIPO=61 "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Gasto Subcontrata por Año",
      "Controla el gasto en subcontrata."),

    q("prod_020",
      "Últimas 20 certificaciones de subcontrata",
      "¿Cuáles son las certificaciones de subcontrata más recientes?",
      "Lista las 20 certificaciones de subcontrata (TIPO=61) más recientes.",
      "SELECT CODIGO, SERIE, NUMERO, FECHA, CODCLIENTE, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=61 ORDER BY FECHA DESC, CODIGO DESC LIMIT 20",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Últimas Cert. Subcontrata",
      "Revisa las certificaciones de subcontrata más recientes."),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE D: RESUMEN GLOBAL (51 + 52 + 61)
    # ══════════════════════════════════════════════════════════════════════════

    q("prod_021",
      "Resumen global: certificaciones y producción",
      "¿Cuántos documentos de producción y certificaciones hay por tipo y año?",
      "Cuenta documentos de tipos 51, 52 y 61 agrupados por tipo y año.",
      "SELECT TIPO, "
      "CASE TIPO WHEN 51 THEN 'Certificacion' "
      "WHEN 52 THEN 'Produccion' "
      "WHEN 61 THEN 'Cert. Subcontrata' END AS DESCRIPCION, "
      "SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO IN (51,52,61) "
      "GROUP BY TIPO, SUBSTR(FECHA,1,4) ORDER BY TIPO, ANIO DESC",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Resumen Produccion y Certificaciones",
      "Vista global de toda la actividad de produccion y certificaciones."),

    q("prod_022",
      "Actividad de producción por mes (todos los tipos)",
      "¿Cuántos documentos de producción/certificaciones hay por mes?",
      "Agrupa tipos 51, 52 y 61 por mes para ver la actividad productiva mensual.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "SUM(CASE WHEN TIPO=51 THEN 1 ELSE 0 END) AS CERTIFICACIONES, "
      "SUM(CASE WHEN TIPO=52 THEN 1 ELSE 0 END) AS PRODUCCION, "
      "SUM(CASE WHEN TIPO=61 THEN 1 ELSE 0 END) AS CERT_SUBCONTRATA, "
      "COUNT(*) AS TOTAL "
      "FROM DOCCAB WHERE TIPO IN (51,52,61) "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Actividad Productiva Mensual",
      "Monitoriza la actividad mensual de produccion y certificaciones."),

    q("prod_023",
      "Importe total de producción y certificaciones por año",
      "¿Cuál es el importe total de producción y certificaciones por año?",
      "Suma importes de tipos 51, 52 y 61 agrupados por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "ROUND(SUM(CASE WHEN TIPO=51 THEN IMPORTETOTAL ELSE 0 END),2) AS IMPORTE_CERTIFICACIONES, "
      "ROUND(SUM(CASE WHEN TIPO=52 THEN IMPORTETOTAL ELSE 0 END),2) AS IMPORTE_PRODUCCION, "
      "ROUND(SUM(CASE WHEN TIPO=61 THEN IMPORTETOTAL ELSE 0 END),2) AS IMPORTE_SUBCONTRATA, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO IN (51,52,61) "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Importe Produccion y Certificaciones",
      "Evalua el valor economico de toda la actividad productiva."),

    q("prod_024",
      "Documentos de producción en un mes específico (2024-04)",
      "¿Cuántos documentos de producción/certificaciones hubo en abril 2024?",
      "Cuenta tipos 51, 52 y 61 en abril de 2024 con desglose por tipo.",
      "SELECT TIPO, "
      "CASE TIPO WHEN 51 THEN 'Certificacion' "
      "WHEN 52 THEN 'Produccion' "
      "WHEN 61 THEN 'Cert. Subcontrata' END AS DESCRIPCION, "
      "COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO IN (51,52,61) AND SUBSTR(FECHA,1,7)='2024-04' "
      "GROUP BY TIPO ORDER BY TIPO",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Produccion Abril 2024",
      "Consulta puntual de toda la actividad productiva en abril 2024."),

    q("prod_025",
      "Tendencia mensual de certificaciones (todos los datos)",
      "¿Cómo han evolucionado las certificaciones mes a mes?",
      "Muestra la tendencia mensual de certificaciones (TIPO=51) ordenada cronológicamente.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=51 "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Tendencia Certificaciones",
      "Identifica tendencias en la actividad de certificaciones."),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE E: TODOS LOS TIPOS DE DOCUMENTOS
    # ══════════════════════════════════════════════════════════════════════════

    q("prod_026",
      "Resumen de todos los tipos de documentos por año",
      "¿Cuántos documentos de cada tipo hay por año?",
      "Muestra el conteo de todos los tipos de documentos por año.",
      "SELECT TIPO, "
      "CASE TIPO "
      "WHEN 0 THEN 'Presupuesto cliente' "
      "WHEN 1 THEN 'Pedido cliente' "
      "WHEN 2 THEN 'Albaran cliente' "
      "WHEN 3 THEN 'Factura venta' "
      "WHEN 10 THEN 'Presupuesto proveedor' "
      "WHEN 11 THEN 'Pedido proveedor' "
      "WHEN 12 THEN 'Albaran proveedor' "
      "WHEN 13 THEN 'Factura compra' "
      "WHEN 21 THEN 'Movimiento almacen' "
      "WHEN 31 THEN 'Recuento almacen' "
      "WHEN 51 THEN 'Certificacion' "
      "WHEN 52 THEN 'Produccion' "
      "WHEN 61 THEN 'Cert. subcontrata' "
      "ELSE 'Otro' END AS DESCRIPCION, "
      "SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N "
      "FROM DOCCAB "
      "GROUP BY TIPO, SUBSTR(FECHA,1,4) ORDER BY ANIO DESC, TIPO",
      "Produccion", "Todos", "KPI", "Alto",
      "Todos los Tipos por Año",
      "Vista completa de la actividad documental por tipo y año."),

    q("prod_027",
      "Movimientos de almacén por año",
      "¿Cuántos movimientos de almacén hubo por año?",
      "Agrupa movimientos de almacén (TIPO=21) por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_MOVIMIENTOS "
      "FROM DOCCAB WHERE TIPO=21 "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Almacen", "Operacional", "Medio",
      "Movimientos Almacen por Año",
      "Analiza la actividad de almacen año a año."),

    q("prod_028",
      "Recuentos de almacén por año",
      "¿Cuántos recuentos de almacén se hicieron por año?",
      "Agrupa recuentos de almacén (TIPO=31) por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_RECUENTOS "
      "FROM DOCCAB WHERE TIPO=31 "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Produccion", "Almacen", "Operacional", "Bajo",
      "Recuentos Almacen por Año",
      "Verifica la frecuencia de recuentos de inventario."),

    q("prod_029",
      "Actividad total por tipo de documento (todos los años)",
      "¿Cuántos documentos hay de cada tipo en total?",
      "Cuenta todos los documentos agrupados por tipo con descripción y suma de importes.",
      "SELECT TIPO, "
      "CASE TIPO "
      "WHEN 0 THEN 'Presupuesto cliente' "
      "WHEN 1 THEN 'Pedido cliente' "
      "WHEN 2 THEN 'Albaran cliente' "
      "WHEN 3 THEN 'Factura venta' "
      "WHEN 10 THEN 'Presupuesto proveedor' "
      "WHEN 11 THEN 'Pedido proveedor' "
      "WHEN 12 THEN 'Albaran proveedor' "
      "WHEN 13 THEN 'Factura compra' "
      "WHEN 21 THEN 'Movimiento almacen' "
      "WHEN 31 THEN 'Recuento almacen' "
      "WHEN 51 THEN 'Certificacion' "
      "WHEN 52 THEN 'Produccion' "
      "WHEN 61 THEN 'Cert. subcontrata' "
      "ELSE 'Otro' END AS DESCRIPCION, "
      "COUNT(*) AS TOTAL, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB GROUP BY TIPO ORDER BY TIPO",
      "Produccion", "Todos", "KPI", "Alto",
      "Actividad por Tipo de Documento",
      "Resumen global de todos los tipos de documentos."),

    q("prod_030",
      "Documentos de producción en 2024 (desglose)",
      "¿Cuántos documentos de producción y certificaciones hubo en 2024?",
      "Cuenta tipos 51, 52 y 61 en 2024 con desglose por tipo.",
      "SELECT TIPO, "
      "CASE TIPO WHEN 51 THEN 'Certificacion' "
      "WHEN 52 THEN 'Produccion' "
      "WHEN 61 THEN 'Cert. Subcontrata' END AS DESCRIPCION, "
      "COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO IN (51,52,61) AND SUBSTR(FECHA,1,4)='2024' "
      "GROUP BY TIPO ORDER BY TIPO",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Produccion 2024 desglose",
      "Consulta de toda la actividad productiva en 2024."),

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE F: KPIs SIMPLES DE UN NÚMERO (respuesta inmediata)
    # ══════════════════════════════════════════════════════════════════════════

    q("prod_031",
      "KPI: total certificaciones + subcontrata",
      "¿Cuántas certificaciones (propias y de subcontrata) hay en total?",
      "Suma total de TIPO=51 y TIPO=61. Un único número.",
      "SELECT COUNT(*) AS TOTAL_CERTS FROM DOCCAB WHERE TIPO IN (51,61)",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Total Certs (51+61)",
      "KPI de un vistazo: certificaciones propias más subcontrata."),

    q("prod_032",
      "KPI: importe total certificaciones (TIPO=51)",
      "¿Cuál es el importe total de todas las certificaciones?",
      "Suma IMPORTETOTAL de todas las certificaciones (TIPO=51). Un único valor.",
      "SELECT ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL_CERTIFICACIONES "
      "FROM DOCCAB WHERE TIPO=51",
      "Produccion", "Todos", "Certificaciones", "Alto",
      "Importe Total Certs",
      "KPI financiero: importe total acumulado de certificaciones."),

    q("prod_033",
      "KPI: importe medio por certificación",
      "¿Cuál es el importe medio de una certificación?",
      "AVG de IMPORTETOTAL en TIPO=51. Útil para benchmark.",
      "SELECT ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO_CERT, "
      "COUNT(*) AS N_CERTIFICACIONES "
      "FROM DOCCAB WHERE TIPO=51 AND IMPORTETOTAL > 0",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Importe Medio Certificacion",
      "Benchmark: PRECIOVENTA medio de una certificacion."),

    q("prod_034",
      "Certificaciones en 2024 por trimestre",
      "¿Cuántas certificaciones hubo en 2024 por trimestre?",
      "Agrupa certificaciones (TIPO=51) de 2024 por trimestre.",
      "SELECT "
      "CASE "
      "  WHEN SUBSTR(FECHA,6,2) IN ('01','02','03') THEN 'Q1 2024' "
      "  WHEN SUBSTR(FECHA,6,2) IN ('04','05','06') THEN 'Q2 2024' "
      "  WHEN SUBSTR(FECHA,6,2) IN ('07','08','09') THEN 'Q3 2024' "
      "  ELSE 'Q4 2024' "
      "END AS TRIMESTRE, "
      "COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=51 AND SUBSTR(FECHA,1,4)='2024' "
      "GROUP BY TRIMESTRE ORDER BY TRIMESTRE",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Certificaciones 2024 por Trimestre",
      "Analiza si la actividad de certificaciones es estacional."),

    q("prod_035",
      "Facturas de compra en 2024 (KPI simple)",
      "¿Cuántas facturas de compra llegaron en 2024?",
      "Cuenta facturas de proveedor (TIPO=13) con fecha en 2024. Un número.",
      "SELECT COUNT(*) AS FACTURAS_COMPRA_2024 "
      "FROM DOCCAB WHERE TIPO=13 AND SUBSTR(FECHA,1,4)='2024'",
      "Produccion", "Todos", "KPI", "Bajo",
      "Facturas Compra 2024 (n)",
      "KPI cruzado: facturas de proveedor recibidas en 2024."),

    q("prod_036",
      "Facturas de compra en 2024 por mes",
      "¿Cuántas facturas de compra llegaron cada mes en 2024?",
      "Desglose mensual de facturas de proveedor (TIPO=13) en 2024.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND SUBSTR(FECHA,1,4)='2024' "
      "GROUP BY MES ORDER BY MES",
      "Produccion", "Todos", "KPI", "Bajo",
      "Facturas Compra 2024 por Mes",
      "Verifica la regularidad de llegada de facturas de proveedor."),

    q("prod_037",
      "Todos los tipos de docs en 2024: resumen ejecutivo",
      "¿Cuántos documentos de cada tipo hubo en 2024?",
      "Vista rápida de actividad 2024 por tipo de documento con nombre legible.",
      "SELECT "
      "CASE TIPO "
      "WHEN 0 THEN 'Presupuesto cliente' "
      "WHEN 1 THEN 'Pedido cliente' "
      "WHEN 2 THEN 'Albaran cliente' "
      "WHEN 3 THEN 'Factura venta' "
      "WHEN 10 THEN 'Presupuesto proveedor' "
      "WHEN 11 THEN 'Pedido proveedor' "
      "WHEN 12 THEN 'Albaran proveedor' "
      "WHEN 13 THEN 'Factura compra' "
      "WHEN 21 THEN 'Movimiento almacen' "
      "WHEN 31 THEN 'Recuento almacen' "
      "WHEN 51 THEN 'Certificacion' "
      "WHEN 52 THEN 'Produccion' "
      "WHEN 61 THEN 'Cert. subcontrata' "
      "ELSE 'Otro' END AS TIPO_DOC, "
      "COUNT(*) AS N "
      "FROM DOCCAB WHERE SUBSTR(FECHA,1,4)='2024' "
      "GROUP BY TIPO ORDER BY TIPO",
      "Produccion", "Todos", "KPI", "Alto",
      "Actividad 2024 por Tipo",
      "Resumen ejecutivo de toda la actividad documental en 2024."),

    q("prod_038",
      "Cert. subcontrata en 2024 (KPI simple)",
      "¿Cuántas certificaciones de subcontrata hubo en 2024?",
      "Un único número: certificaciones de subcontrata (TIPO=61) en 2024.",
      "SELECT COUNT(*) AS CERT_SUBCONTRATA_2024 "
      "FROM DOCCAB WHERE TIPO=61 AND SUBSTR(FECHA,1,4)='2024'",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Cert. Subcontrata 2024 (n)",
      "KPI minimo: certificaciones de subcontrata en 2024."),

    q("prod_039",
      "Total produccion + cert + subcontrata en 2024",
      "¿Cuántos documentos de producción y certificaciones hubo en 2024 en total?",
      "Un único número: suma de TIPO 51+52+61 en 2024.",
      "SELECT COUNT(*) AS TOTAL_ACTIVIDAD_PRODUCTIVA_2024 "
      "FROM DOCCAB WHERE TIPO IN (51,52,61) AND SUBSTR(FECHA,1,4)='2024'",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Total Actividad Productiva 2024",
      "KPI global de toda la actividad productiva en 2024."),

    q("prod_040",
      "Certificacion con mayor importe",
      "¿Cuál es la certificación de mayor importe?",
      "Busca la certificación (TIPO=51) con el IMPORTETOTAL más alto.",
      "SELECT CODIGO, SERIE, NUMERO, FECHA, CODCLIENTE, "
      "ROUND(IMPORTETOTAL,2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=51 "
      "ORDER BY IMPORTETOTAL DESC LIMIT 1",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Mayor Certificacion",
      "Identifica la certificacion de mayor valor economico."),

    q("prod_041",
      "Certificacion con menor importe",
      "¿Cuál es la certificación de menor importe?",
      "Busca la certificación (TIPO=51) con el IMPORTETOTAL más bajo (mayor que 0).",
      "SELECT CODIGO, SERIE, NUMERO, FECHA, CODCLIENTE, "
      "ROUND(IMPORTETOTAL,2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=51 AND IMPORTETOTAL > 0 "
      "ORDER BY IMPORTETOTAL ASC LIMIT 1",
      "Produccion", "Todos", "Certificaciones", "Medio",
      "Menor Certificacion",
      "Identifica la certificacion de menor valor economico."),

    q("prod_042",
      "Cadencia de certificaciones (primera y ultima fecha)",
      "¿Cuándo fue la primera y la última certificación emitida?",
      "Devuelve la primera y la última certificación (TIPO=51), el total "
      "y el periodo cubierto en días (compatible SQLite y Firebird).",
      "SELECT COUNT(*) AS N_CERTIFICACIONES, "
      "MIN(FECHA) AS PRIMERA_CERT, MAX(FECHA) AS ULTIMA_CERT, "
      "MIN(SUBSTR(FECHA,1,4)) AS ANIO_INICIO, MAX(SUBSTR(FECHA,1,4)) AS ANIO_FIN "
      "FROM DOCCAB WHERE TIPO=51",
      "Produccion", "Todos", "Certificaciones", "Bajo",
      "Cadencia Certificaciones",
      "Mide el periodo de actividad de certificaciones."),
]
