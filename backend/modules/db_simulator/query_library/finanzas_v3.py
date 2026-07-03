"""
query_library/finanzas_v3.py — 150 consultas adicionales de Finanzas (v3).

Diferentes a finanzas.py y finanzas_v2.py. Cubren: análisis de tesorería,
gestión de cobros y pagos, análisis de IMPORTEIVA avanzado, control de gastos,
análisis de rentabilidad financiera, gestión de riesgo crediticio,
análisis de flujo de caja, y control presupuestario.

DEVIA: backend/modules/db_simulator/DEVIA.md
Compatibilidad SQLite: strftime, JULIANDAY, SUBSTR, CAST, COALESCE.
Sin comentarios subjetivos. Solo hechos verificables con datos.
"""

from backend.modules.db_simulator.query_library.builder import q

QUERIES_FINANZAS_V3 = [

    # ── ANÁLISIS DE COBROS ─────────────────────────────────────────────────────

    q("fx3_001", "Facturas pendientes de cobro por antigüedad",
      "¿Cuánto tiempo llevan pendientes de cobro las facturas?",
      "Clasifica facturas TIPO=13 con IMPORTETOTAL>IMPORTEENTREGADO por tramos de antigüedad.",
      "SELECT "
      "CASE WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=30 THEN '0-30 días' "
      "WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=60 THEN '31-60 días' "
      "WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=90 THEN '61-90 días' "
      "WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=180 THEN '91-180 días' "
      "ELSE 'Más de 180 días' END AS TRAMO, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO AND FECHA IS NOT NULL "
      "GROUP BY TRAMO ORDER BY MIN(JULIANDAY('now')-JULIANDAY(FECHA))",
      "Finanzas", "Dirección", "KPI", "Crítico", "Cobros", ""),

    q("fx3_002", "Clientes con deuda superior a 5000€",
      "¿Qué clientes tienen más de 5000€ pendientes de cobro?",
      "Suma de IMPORTETOTAL-IMPORTEENTREGADO por cliente en facturas TIPO=13.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS_PENDIENTES, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO),2) AS DEUDA_TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL>D.IMPORTEENTREGADO "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO)>5000 "
      "ORDER BY DEUDA_TOTAL DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Cobros", ""),

    q("fx3_003", "Ratio de cobro (IMPORTEENTREGADO/facturado) por mes",
      "¿Qué porcentaje de lo facturado se cobra cada mes?",
      "Ratio IMPORTEENTREGADO/IMPORTETOTAL en facturas TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO, "
      "ROUND(SUM(IMPORTEENTREGADO),2) AS IMPORTEENTREGADO, "
      "ROUND(SUM(IMPORTEENTREGADO)*100.0/NULLIF(SUM(IMPORTETOTAL),0),1) AS RATIO_COBRO_PCT "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Cobros", ""),

    q("fx3_004", "Facturas cobradas en el mes de emisión",
      "¿Qué porcentaje de facturas se cobran en el mismo mes de emisión?",
      "Facturas TIPO=13 donde IMPORTEENTREGADO>=IMPORTETOTAL en el mes de FECHA.",
      "SELECT COUNT(*) AS COBRADAS_MISMO_MES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_COBRADO_MISMO_MES "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEENTREGADO>=IMPORTETOTAL",
      "Finanzas", "Dirección", "KPI", "Medio", "Cobros", ""),

    q("fx3_005", "Evolución del saldo pendiente de cobro por mes",
      "¿Cómo evoluciona el saldo pendiente de cobro mes a mes?",
      "Suma de IMPORTETOTAL-IMPORTEENTREGADO en facturas TIPO=13 emitidas cada mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES_EMISION, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO, "
      "ROUND(SUM(IMPORTEENTREGADO),2) AS IMPORTEENTREGADO, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES_EMISION DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Cobros", ""),

    q("fx3_006", "Facturas con cobro parcial (entre 1% y 99%)",
      "¿Qué facturas tienen cobro parcial?",
      "Facturas TIPO=13 con IMPORTEENTREGADO>0 pero <IMPORTETOTAL.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS TOTAL, "
      "ROUND(D.IMPORTEENTREGADO,2) AS IMPORTEENTREGADO, "
      "ROUND(D.IMPORTETOTAL-D.IMPORTEENTREGADO,2) AS PENDIENTE, "
      "ROUND(D.IMPORTEENTREGADO*100.0/NULLIF(D.IMPORTETOTAL,0),1) AS PCT_COBRADO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO>0 AND D.IMPORTEENTREGADO<D.IMPORTETOTAL "
      "ORDER BY PENDIENTE DESC LIMIT 30",
      "Finanzas", "Dirección", "Operacional", "Alto", "Cobros", ""),

    q("fx3_007", "Días de cobro medio (DSO - Days Sales Outstanding)",
      "¿Cuántos días tarda de media en cobrarse una factura?",
      "Promedio de días entre FECHA de factura y cobro completo (IMPORTEENTREGADO>=IMPORTETOTAL).",
      "SELECT ROUND(AVG(JULIANDAY('now')-JULIANDAY(FECHA)),1) AS DSO_DIAS, "
      "COUNT(*) AS N_FACTURAS_COBRADAS "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEENTREGADO>=IMPORTETOTAL AND FECHA IS NOT NULL",
      "Finanzas", "Dirección", "KPI", "Alto", "Cobros", ""),

    q("fx3_008", "Clientes con mayor DSO (días de cobro)",
      "¿Qué clientes tardan más en pagar?",
      "Promedio de días entre FECHA y cobro completo por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(JULIANDAY('now')-JULIANDAY(D.FECHA)),1) AS DSO_MEDIO_DIAS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO>=D.IMPORTETOTAL AND D.FECHA IS NOT NULL "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(*)>=2 "
      "ORDER BY DSO_MEDIO_DIAS DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Cobros", ""),

    q("fx3_009", "Total IMPORTEENTREGADO vs facturado por año",
      "¿Cuánto se ha IMPORTEENTREGADO vs facturado por año?",
      "Suma de IMPORTETOTAL e IMPORTEENTREGADO en facturas TIPO=13 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO, "
      "ROUND(SUM(IMPORTEENTREGADO),2) AS IMPORTEENTREGADO, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Crítico", "Cobros", ""),

    q("fx3_010", "Facturas sin cobrar de más de 90 días",
      "¿Qué facturas llevan más de 90 días sin cobrar?",
      "Facturas TIPO=13 con IMPORTEENTREGADO=0 y FECHA>90 días.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_SIN_COBRAR "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "AND D.FECHA IS NOT NULL AND JULIANDAY('now')-JULIANDAY(D.FECHA)>90 "
      "ORDER BY DIAS_SIN_COBRAR DESC LIMIT 30",
      "Finanzas", "Dirección", "Operacional", "Crítico", "Cobros", ""),

    # ── ANÁLISIS DE PAGOS A PROVEEDORES ───────────────────────────────────────

    q("fx3_011", "Facturas de compra pendientes de pago (TIPO=13 en compras)",
      "¿Cuánto se debe a proveedores?",
      "Documentos de compra TIPO=13 con IMPORTETOTAL>IMPORTEENTREGADO.",
      "SELECT COUNT(*) AS N_FACTURAS_COMPRA_PENDIENTES, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS DEUDA_PROVEEDORES "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO",
      "Finanzas", "Compras", "KPI", "Alto", "Pagos", ""),

    q("fx3_012", "Movimientos de caja positivos (entradas) por mes",
      "¿Cuánto dinero entra en caja cada mes?",
      "Suma de IMPORTE>0 en CAJA por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(*) AS N_ENTRADAS, "
      "ROUND(SUM(IMPORTE),2) AS TOTAL_ENTRADAS "
      "FROM CAJA WHERE IMPORTE>0 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Caja", ""),

    q("fx3_013", "Movimientos de caja negativos (salidas) por mes",
      "¿Cuánto dinero sale de caja cada mes?",
      "Suma de IMPORTE<0 en CAJA por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "COUNT(*) AS N_SALIDAS, "
      "ROUND(ABS(SUM(IMPORTE)),2) AS TOTAL_SALIDAS "
      "FROM CAJA WHERE IMPORTE<0 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Caja", ""),

    q("fx3_014", "Flujo de caja neto mensual",
      "¿Cuál es el flujo de caja neto cada mes?",
      "Entradas menos salidas en CAJA por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN IMPORTE>0 THEN IMPORTE ELSE 0 END),2) AS ENTRADAS, "
      "ROUND(ABS(SUM(CASE WHEN IMPORTE<0 THEN IMPORTE ELSE 0 END)),2) AS SALIDAS, "
      "ROUND(SUM(IMPORTE),2) AS FLUJO_NETO "
      "FROM CAJA WHERE FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Crítico", "Caja", ""),

    q("fx3_015", "Saldo de caja acumulado por mes",
      "¿Cuál es el saldo acumulado de caja mes a mes?",
      "Suma acumulada de IMPORTE en CAJA por mes.",
      "SELECT MES, FLUJO_NETO, "
      "SUM(FLUJO_NETO) OVER (ORDER BY MES) AS SALDO_ACUMULADO "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTE),2) AS FLUJO_NETO "
      "FROM CAJA WHERE FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Caja", ""),

    # ── ANÁLISIS DE IMPORTEIVA AVANZADO ───────────────────────────────────────────────

    q("fx3_016", "IMPORTEIVA repercutido total (facturas emitidas)",
      "¿Cuánto IMPORTEIVA se ha repercutido en facturas emitidas?",
      "Suma de IMPORTEIVA en facturas TIPO=13 (IMPORTEIVA repercutido a clientes).",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_REPERCUTIDO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Crítico", "IMPORTEIVA", ""),

    q("fx3_017", "IMPORTEIVA soportado total (facturas recibidas de proveedores)",
      "¿Cuánto IMPORTEIVA se ha soportado en compras?",
      "Suma de IMPORTEIVA en documentos de compra (si existen en DOCCAB).",
      "SELECT COUNT(*) AS N_DOCS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_SOPORTADO "
      "FROM DOCCAB WHERE IMPORTEIVA>0 AND TIPO NOT IN (13)",
      "Finanzas", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("fx3_018", "Liquidación de IMPORTEIVA estimada por trimestre",
      "¿Cuál es la liquidación de IMPORTEIVA estimada por trimestre?",
      "IMPORTEIVA repercutido (TIPO=13) por trimestre.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "CASE WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_REPERCUTIDO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO, TRIMESTRE ORDER BY ANIO DESC, TRIMESTRE",
      "Finanzas", "Dirección", "KPI", "Crítico", "IMPORTEIVA", ""),

    q("fx3_019", "Facturas con tipo de IMPORTEIVA al 21%",
      "¿Cuántas facturas tienen IMPORTEIVA al 21%?",
      "Facturas TIPO=13 donde IMPORTEIVA/BASE ≈ 21%.",
      "SELECT COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEBASE>0 "
      "AND ROUND(IMPORTEIVA*100.0/NULLIF(IMPORTEBASE,0),0)=21",
      "Finanzas", "Dirección", "KPI", "Medio", "IMPORTEIVA", ""),

    q("fx3_020", "Facturas con tipo de IMPORTEIVA al 10%",
      "¿Cuántas facturas tienen IMPORTEIVA reducido al 10%?",
      "Facturas TIPO=13 donde IMPORTEIVA/BASE ≈ 10%.",
      "SELECT COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEBASE>0 "
      "AND ROUND(IMPORTEIVA*100.0/NULLIF(IMPORTEBASE,0),0)=10",
      "Finanzas", "Dirección", "KPI", "Medio", "IMPORTEIVA", ""),

    q("fx3_021", "Facturas exentas de IMPORTEIVA (IMPORTEIVA=0)",
      "¿Cuántas facturas están exentas de IMPORTEIVA?",
      "Facturas TIPO=13 con IMPORTEIVA=0 y IMPORTEBASE>0.",
      "SELECT COUNT(*) AS N_FACTURAS_EXENTAS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_EXENTA "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEIVA=0 AND IMPORTEBASE>0",
      "Finanzas", "Dirección", "KPI", "Medio", "IMPORTEIVA", ""),

    q("fx3_022", "Distribución de facturas por tipo de IMPORTEIVA efectivo",
      "¿Cómo se distribuyen las facturas por tipo de IMPORTEIVA?",
      "Agrupa facturas TIPO=13 por tipo de IMPORTEIVA efectivo (0%, 4%, 10%, 21%).",
      "SELECT "
      "CASE WHEN IMPORTEBASE=0 OR IMPORTEBASE IS NULL THEN 'Sin base' "
      "WHEN IMPORTEIVA=0 THEN '0% (Exento)' "
      "WHEN ROUND(IMPORTEIVA*100.0/NULLIF(IMPORTEBASE,0),0)=4 THEN '4% (Superreducido)' "
      "WHEN ROUND(IMPORTEIVA*100.0/NULLIF(IMPORTEBASE,0),0)=10 THEN '10% (Reducido)' "
      "WHEN ROUND(IMPORTEIVA*100.0/NULLIF(IMPORTEBASE,0),0)=21 THEN '21% (General)' "
      "ELSE 'Otro' END AS TIPO_IVA, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 "
      "GROUP BY TIPO_IMPORTEIVA ORDER BY N_FACTURAS DESC",
      "Finanzas", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("fx3_023", "IMPORTEIVA anual total generado",
      "¿Cuánto IMPORTEIVA se genera por año?",
      "Suma de IMPORTEIVA en facturas TIPO=13 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_TOTAL, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Crítico", "IMPORTEIVA", ""),

    q("fx3_024", "Recargo de equivalencia total",
      "¿Cuánto recargo de equivalencia se ha aplicado?",
      "Suma de IMPORTERECEQUIV en facturas TIPO=13.",
      "SELECT COUNT(*) AS N_FACTURAS_CON_RECEQUIV, "
      "ROUND(SUM(IMPORTERECEQUIV),2) AS TOTAL_RECEQUIV, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTERECEQUIV>0",
      "Finanzas", "Dirección", "KPI", "Bajo", "Recargo equivalencia", ""),

    q("fx3_025", "IRPF total retenido en facturas",
      "¿Cuánto IRPF se ha retenido en facturas?",
      "Suma de IMPORTEIRPF en facturas TIPO=13.",
      "SELECT COUNT(*) AS N_FACTURAS_CON_IRPF, "
      "ROUND(SUM(IMPORTEIRPF),2) AS TOTAL_IRPF, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(IMPORTEIRPF)*100.0/NULLIF(SUM(IMPORTEBASE),0),1) AS TIPO_IRPF_EFECTIVO_PCT "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEIRPF>0",
      "Finanzas", "Dirección", "KPI", "Medio", "IRPF", ""),

    # ── ANÁLISIS DE RENTABILIDAD FINANCIERA ───────────────────────────────────

    q("fx3_026", "Margen financiero bruto por mes",
      "¿Cuál es el margen financiero bruto mensual?",
      "Diferencia entre facturación TIPO=13 y abonos TIPO=3 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS INGRESOS, "
      "ROUND(SUM(CASE WHEN TIPO=3 THEN ABS(IMPORTETOTAL) ELSE 0 END),2) AS DEVOLUCIONES, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL WHEN TIPO=3 THEN -ABS(IMPORTETOTAL) ELSE 0 END),2) AS MARGEN_NETO "
      "FROM DOCCAB WHERE TIPO IN (13,3) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Crítico", "Margen", ""),

    q("fx3_027", "Ratio de devoluciones sobre facturación",
      "¿Qué porcentaje de la facturación se devuelve?",
      "Ratio de abonos TIPO=3 sobre facturas TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS FACTURAS, "
      "ROUND(SUM(CASE WHEN TIPO=3 THEN ABS(IMPORTETOTAL) ELSE 0 END),2) AS ABONOS, "
      "ROUND(SUM(CASE WHEN TIPO=3 THEN ABS(IMPORTETOTAL) ELSE 0 END)*100.0/"
      "NULLIF(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),0),2) AS RATIO_DEVOLUCION_PCT "
      "FROM DOCCAB WHERE TIPO IN (13,3) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 12",
      "Finanzas", "Dirección", "KPI", "Alto", "Devoluciones", ""),

    q("fx3_028", "Facturación base imponible vs IMPORTEIVA vs total por año",
      "¿Cuál es la estructura de la facturación (base, IVA, total) por año?",
      "Desglose de IMPORTEBASE, IMPORTEIVA e IMPORTETOTAL en facturas TIPO=13 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_IMPONIBLE, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL, "
      "ROUND(SUM(IMPORTEIVA)*100.0/NULLIF(SUM(IMPORTEBASE),0),1) AS TIPO_IVA_MEDIO_PCT "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Alto", "Estructura financiera", ""),

    q("fx3_029", "Ticket medio de factura por año",
      "¿Cómo evoluciona el ticket medio anual?",
      "Importe medio por factura TIPO=13 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Medio", "Ticket", ""),

    q("fx3_030", "Concentración de ingresos: curva de Pareto",
      "¿Qué porcentaje de clientes genera el 80% de los ingresos?",
      "Análisis de Pareto: clientes ordenados por facturación acumulada.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION, "
      "ROUND(SUM(D.IMPORTETOTAL)*100.0/("
      "SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13),1) AS PCT_INDIVIDUAL, "
      "ROUND(SUM(SUM(D.IMPORTETOTAL)) OVER (ORDER BY SUM(D.IMPORTETOTAL) DESC)*100.0/"
      "(SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13),1) AS PCT_ACUMULADO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY FACTURACION DESC LIMIT 30",
      "Finanzas", "Dirección", "KPI", "Alto", "Concentración", ""),

    # ── ANÁLISIS DE GASTOS Y COSTES ────────────────────────────────────────────

    q("fx3_031", "PRECIOCOSTE total de artículos vendidos (COGS)",
      "¿Cuál es el PRECIOCOSTE total de los artículos vendidos?",
      "Suma de PRECIOCOSTE*CANTIDAD en líneas de facturas TIPO=13.",
      "SELECT ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS_TOTAL, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS_TOTALES, "
      "ROUND((SUM(L.PRECIO*L.CANTIDAD)-SUM(A.PRECIOCOSTE*L.CANTIDAD))*100.0/"
      "NULLIF(SUM(L.PRECIO*L.CANTIDAD),0),1) AS MARGEN_BRUTO_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0",
      "Finanzas", "Dirección", "KPI", "Crítico", "COGS", ""),

    q("fx3_032", "COGS mensual",
      "¿Cómo evoluciona el PRECIOCOSTE de ventas mes a mes?",
      "Suma de PRECIOCOSTE*CANTIDAD en líneas de facturas TIPO=13 por mes.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD)-SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS MARGEN_BRUTO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "COGS", ""),

    q("fx3_033", "Valor del inventario a PRECIOVENTA de PRECIOCOSTE",
      "¿Cuánto vale el inventario a PRECIOVENTA de PRECIOCOSTE?",
      "Suma de STOCKARTICULO*PRECIOCOSTE en ARTICULO.",
      "SELECT COUNT(*) AS N_ARTICULOS_CON_STOCKARTICULO, "
      "ROUND(SUM(STOCKARTICULO*PRECIOCOSTE),2) AS VALOR_COSTE, "
      "ROUND(SUM(STOCKARTICULO*PRECIOVENTA),2) AS VALOR_VENTA, "
      "ROUND((SUM(STOCKARTICULO*PRECIOVENTA)-SUM(STOCKARTICULO*PRECIOCOSTE))*100.0/"
      "NULLIF(SUM(STOCKARTICULO*PRECIOVENTA),0),1) AS MARGEN_POTENCIAL_PCT "
      "FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0",
      "Finanzas", "Dirección", "KPI", "Alto", "Inventario", ""),

    q("fx3_034", "Artículos con mayor PRECIOCOSTE de inventario",
      "¿Qué artículos tienen mayor valor de inventario a PRECIOCOSTE?",
      "Artículos con mayor STOCKARTICULO*PRECIOCOSTE.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(PRECIOCOSTE,2) AS COSTE_UNITARIO, "
      "ROUND(STOCKARTICULO*PRECIOCOSTE,2) AS VALOR_INVENTARIO "
      "FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0 "
      "ORDER BY VALOR_INVENTARIO DESC LIMIT 20",
      "Finanzas", "Dirección", "Artículo", "Alto", "Inventario", ""),

    q("fx3_035", "Descuentos totales aplicados en el año",
      "¿Cuánto dinero se ha dejado de ingresar por descuentos en el año?",
      "Suma de descuentos en líneas de facturas TIPO=13 del año actual.",
      "SELECT ROUND(SUM(L.DESCUENTOS*L.PRECIO*L.CANTIDAD/100.0),2) AS DESCUENTOS_TOTALES, "
      "COUNT(*) AS N_LINEAS_CON_DESCUENTO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0 "
      "AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4)",
      "Finanzas", "Dirección", "KPI", "Medio", "Descuentos", ""),

    # ── ANÁLISIS DE RIESGO CREDITICIO ──────────────────────────────────────────

    q("fx3_036", "Clientes con deuda superior al 50% de su facturación histórica",
      "¿Qué clientes tienen una deuda desproporcionada respecto a su historial?",
      "Clientes donde pendiente/total_historico > 50%.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_HISTORICO, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO),2) AS PENDIENTE, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO)*100.0/NULLIF(SUM(D.IMPORTETOTAL),0),1) AS PCT_DEUDA "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING PCT_DEUDA>50 AND SUM(D.IMPORTETOTAL)>1000 "
      "ORDER BY PENDIENTE DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Riesgo crediticio", ""),

    q("fx3_037", "Clientes con facturas impagadas de más de 6 meses",
      "¿Qué clientes tienen facturas sin cobrar de más de 6 meses?",
      "Clientes con facturas TIPO=13 con IMPORTEENTREGADO=0 y FECHA>180 días.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS_IMPAGADAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS IMPORTE_IMPAGADO, "
      "MAX(CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER)) AS DIAS_MAX_IMPAGO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "AND D.FECHA IS NOT NULL AND JULIANDAY('now')-JULIANDAY(D.FECHA)>180 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY IMPORTE_IMPAGADO DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Riesgo crediticio", ""),

    q("fx3_038", "Exposición crediticia total por cliente",
      "¿Cuál es la exposición crediticia total por cliente?",
      "Suma de facturas pendientes + presupuestos sin convertir por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(COALESCE(PEND.PENDIENTE,0),2) AS FACTURAS_PENDIENTES, "
      "ROUND(COALESCE(PRESUP.VALOR,0),2) AS PRESUPUESTOS_PENDIENTES, "
      "ROUND(COALESCE(PEND.PENDIENTE,0)+COALESCE(PRESUP.VALOR,0),2) AS EXPOSICION_TOTAL "
      "FROM CLIENTE C "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL-IMPORTEENTREGADO) AS PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO GROUP BY CODCLIENTE) PEND "
      "ON PEND.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT D.CODCLIENTE, SUM(D.IMPORTETOTAL) AS VALOR "
      "FROM DOCCAB D LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL GROUP BY D.CODCLIENTE) PRESUP "
      "ON PRESUP.CODCLIENTE=C.CODIGO "
      "WHERE COALESCE(PEND.PENDIENTE,0)+COALESCE(PRESUP.VALOR,0)>0 "
      "ORDER BY EXPOSICION_TOTAL DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Riesgo crediticio", ""),

    q("fx3_039", "Número de clientes con alguna deuda pendiente",
      "¿Cuántos clientes tienen alguna deuda pendiente?",
      "Clientes con al menos 1 factura TIPO=13 con IMPORTETOTAL>IMPORTEENTREGADO.",
      "SELECT COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES_CON_DEUDA, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS DEUDA_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO",
      "Finanzas", "Dirección", "KPI", "Alto", "Riesgo crediticio", ""),

    q("fx3_040", "Clientes sin deuda pendiente (pagadores perfectos)",
      "¿Qué clientes siempre pagan al día?",
      "Clientes con facturas TIPO=13 donde IMPORTEENTREGADO>=IMPORTETOTAL en todas.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_FACTURADO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING MIN(D.IMPORTEENTREGADO)>=MIN(D.IMPORTETOTAL) "
      "AND COUNT(*)>=3 "
      "ORDER BY TOTAL_FACTURADO DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Bajo", "Riesgo crediticio", ""),

    # ── ANÁLISIS DE ABONOS Y RECTIFICATIVAS ───────────────────────────────────

    q("fx3_041", "Total de abonos emitidos por año",
      "¿Cuántos abonos se emiten por año?",
      "Conteo y suma de documentos TIPO=3 (abonos) por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "COUNT(*) AS N_ABONOS, "
      "ROUND(SUM(ABS(IMPORTETOTAL)),2) AS IMPORTE_TOTAL_ABONOS "
      "FROM DOCCAB WHERE TIPO=3 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Alto", "Abonos", ""),

    q("fx3_042", "Abonos por cliente",
      "¿Qué clientes generan más abonos?",
      "Conteo y suma de abonos TIPO=3 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_ABONOS, "
      "ROUND(SUM(ABS(D.IMPORTETOTAL)),2) AS IMPORTE_ABONADO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=3 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY IMPORTE_ABONADO DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Abonos", ""),

    q("fx3_043", "Ratio abonos/facturas por cliente",
      "¿Qué clientes tienen mayor ratio de devoluciones?",
      "Ratio de abonos TIPO=3 sobre facturas TIPO=13 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(COALESCE(F.TOTAL,0),2) AS FACTURADO, "
      "ROUND(COALESCE(A.ABONADO,0),2) AS ABONADO, "
      "ROUND(COALESCE(A.ABONADO,0)*100.0/NULLIF(COALESCE(F.TOTAL,0),0),1) AS RATIO_PCT "
      "FROM CLIENTE C "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 GROUP BY CODCLIENTE) F ON F.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(ABS(IMPORTETOTAL)) AS ABONADO FROM DOCCAB "
      "WHERE TIPO=3 GROUP BY CODCLIENTE) A ON A.CODCLIENTE=C.CODIGO "
      "WHERE COALESCE(F.TOTAL,0)>0 AND COALESCE(A.ABONADO,0)>0 "
      "ORDER BY RATIO_PCT DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Abonos", ""),

    q("fx3_044", "Abonos del mes actual",
      "¿Qué abonos se han emitido este mes?",
      "Documentos TIPO=3 del mes actual.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(ABS(D.IMPORTETOTAL),2) AS IMPORTE_ABONO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=3 AND SUBSTR(D.FECHA,1,7)=SUBSTR(DATE('now'),1,7) "
      "ORDER BY D.FECHA DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Medio", "Abonos", ""),

    q("fx3_045", "Importe total de abonos vs facturas por mes",
      "¿Cuánto representan los abonos sobre la facturación cada mes?",
      "Compara TIPO=13 vs TIPO=3 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS FACTURAS, "
      "ROUND(SUM(CASE WHEN TIPO=3 THEN ABS(IMPORTETOTAL) ELSE 0 END),2) AS ABONOS, "
      "ROUND(SUM(CASE WHEN TIPO=3 THEN ABS(IMPORTETOTAL) ELSE 0 END)*100.0/"
      "NULLIF(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),0),2) AS PCT_ABONOS "
      "FROM DOCCAB WHERE TIPO IN (13,3) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 12",
      "Finanzas", "Dirección", "KPI", "Alto", "Abonos", ""),

    # ── ANÁLISIS DE PRESUPUESTO Y CONTROL ─────────────────────────────────────

    q("fx3_046", "Facturación acumulada vs objetivo mensual",
      "¿Cuánto se ha facturado en el mes actual?",
      "Suma de IMPORTETOTAL TIPO=13 del mes actual para comparar con objetivo.",
      "SELECT SUBSTR(DATE('now'),1,7) AS MES_ACTUAL, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO_MES "
      "FROM DOCCAB WHERE TIPO=13 "
      "AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7)",
      "Finanzas", "Dirección", "KPI", "Crítico", "Control", ""),

    q("fx3_047", "Comparativa facturación mes actual vs media histórica mensual",
      "¿Está el mes actual por encima o por debajo de la media histórica?",
      "Compara facturación del mes actual con la media mensual histórica.",
      "SELECT "
      "ROUND((SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13 "
      "AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7)),2) AS MES_ACTUAL, "
      "ROUND((SELECT AVG(TOTAL) FROM (SELECT SUBSTR(FECHA,1,7) AS MES, "
      "SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7))),2) AS MEDIA_MENSUAL_HISTORICA",
      "Finanzas", "Dirección", "KPI", "Alto", "Control", ""),

    q("fx3_048", "Días de STOCKARTICULO disponible por artículo",
      "¿Cuántos días de STOCKARTICULO quedan de cada artículo?",
      "STOCKARTICULO actual / ventas diarias medias en los últimos 90 días.",
      "SELECT A.CODIGO, A.NOMBRE, A.STOCKARTICULO AS STOCK_ACTUAL, "
      "ROUND(COALESCE(V.UNIDADES_DIA,0),2) AS VENTAS_DIARIAS_MEDIA, "
      "CASE WHEN COALESCE(V.UNIDADES_DIA,0)=0 THEN 9999 "
      "ELSE CAST(A.STOCKARTICULO/V.UNIDADES_DIA AS INTEGER) END AS DIAS_STOCKARTICULO "
      "FROM ARTICULO A "
      "LEFT JOIN (SELECT L.CODARTICULO, SUM(L.CANTIDAD)*1.0/90 AS UNIDADES_DIA "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-90 days') "
      "GROUP BY L.CODARTICULO) V ON A.CODIGO=A.CODIGO "
      "WHERE A.STOCKARTICULO>0 "
      "ORDER BY DIAS_STOCKARTICULO ASC LIMIT 30",
      "Finanzas", "Almacén", "Artículo", "Alto", "STOCKARTICULO", ""),

    q("fx3_049", "Punto de equilibrio estimado (break-even)",
      "¿Cuánto hay que facturar para cubrir el PRECIOCOSTE de ventas?",
      "Relación entre ingresos y COGS para estimar el punto de equilibrio.",
      "SELECT ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS_TOTALES, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS_TOTAL, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD)-SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS MARGEN_BRUTO, "
      "ROUND((SUM(L.PRECIO*L.CANTIDAD)-SUM(A.PRECIOCOSTE*L.CANTIDAD))*100.0/"
      "NULLIF(SUM(L.PRECIO*L.CANTIDAD),0),1) AS MARGEN_BRUTO_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4)",
      "Finanzas", "Dirección", "KPI", "Crítico", "Break-even", ""),

    q("fx3_050", "Evolución del margen bruto porcentual por mes",
      "¿Cómo evoluciona el margen bruto porcentual mes a mes?",
      "Margen bruto % = (ingresos-COGS)/ingresos por mes en facturas TIPO=13.",
      "SELECT SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS, "
      "ROUND((SUM(L.PRECIO*L.CANTIDAD)-SUM(A.PRECIOCOSTE*L.CANTIDAD))*100.0/"
      "NULLIF(SUM(L.PRECIO*L.CANTIDAD),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Margen", ""),

    # ── ANÁLISIS DE CAJA AVANZADO ──────────────────────────────────────────────

    q("fx3_051", "Caja: mayor movimiento positivo histórico",
      "¿Cuál es el mayor ingreso registrado en caja?",
      "Registro de CAJA con mayor IMPORTE positivo.",
      "SELECT FECHA, ROUND(IMPORTE,2) AS IMPORTE, CONCEPTO "
      "FROM CAJA WHERE IMPORTE>0 ORDER BY IMPORTE DESC LIMIT 5",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    q("fx3_052", "Caja: mayor movimiento negativo histórico",
      "¿Cuál es el mayor pago registrado en caja?",
      "Registro de CAJA con mayor IMPORTE negativo (mayor salida).",
      "SELECT FECHA, ROUND(IMPORTE,2) AS IMPORTE, CONCEPTO "
      "FROM CAJA WHERE IMPORTE<0 ORDER BY IMPORTE ASC LIMIT 5",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    q("fx3_053", "Días sin movimientos de caja",
      "¿Cuántos días no hay movimientos de caja?",
      "Días laborables sin registros en CAJA.",
      "SELECT COUNT(DISTINCT FECHA) AS DIAS_CON_MOVIMIENTO, "
      "MIN(FECHA) AS PRIMER_MOVIMIENTO, MAX(FECHA) AS ULTIMO_MOVIMIENTO "
      "FROM CAJA WHERE FECHA IS NOT NULL",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    q("fx3_054", "Caja: media de movimientos por día",
      "¿Cuántos movimientos de caja hay de media por día?",
      "Promedio de registros en CAJA por día.",
      "SELECT ROUND(CAST(COUNT(*) AS REAL)/NULLIF(COUNT(DISTINCT FECHA),0),1) AS MEDIA_MOVIMIENTOS_DIA, "
      "COUNT(*) AS TOTAL_MOVIMIENTOS, "
      "COUNT(DISTINCT FECHA) AS DIAS_CON_MOVIMIENTO "
      "FROM CAJA WHERE FECHA IS NOT NULL",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    q("fx3_055", "Caja: importe medio por movimiento",
      "¿Cuál es el importe medio de cada movimiento de caja?",
      "Promedio de ABS(IMPORTE) en CAJA.",
      "SELECT ROUND(AVG(ABS(IMPORTE)),2) AS IMPORTE_MEDIO, "
      "ROUND(AVG(CASE WHEN IMPORTE>0 THEN IMPORTE END),2) AS MEDIA_ENTRADAS, "
      "ROUND(AVG(CASE WHEN IMPORTE<0 THEN ABS(IMPORTE) END),2) AS MEDIA_SALIDAS "
      "FROM CAJA",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    # ── ANÁLISIS DE FORMAS DE PAGO ─────────────────────────────────────────────

    q("fx3_056", "Facturación por forma de pago y mes",
      "¿Cómo evoluciona la facturación por forma de pago?",
      "Suma de IMPORTETOTAL TIPO=13 por CODFORMAPAGO y mes.",
      "SELECT COALESCE(FP.NOMBRE, 'Sin forma pago') AS FORMA_PAGO, "
      "SUBSTR(D.FECHA,1,7) AS MES, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN FORMASPAGO FP ON FP.CODIGO=D.CODFORMAPAGO "
      "WHERE D.TIPO=13 AND D.FECHA IS NOT NULL "
      "GROUP BY D.CODFORMAPAGO, FP.NOMBRE, SUBSTR(D.FECHA,1,7) "
      "ORDER BY MES DESC, TOTAL DESC LIMIT 30",
      "Finanzas", "Dirección", "Operacional", "Medio", "Formas de pago", ""),

    q("fx3_057", "Clientes que pagan al contado vs a crédito",
      "¿Qué clientes pagan al contado (IMPORTEENTREGADO=facturado)?",
      "Clientes con IMPORTEENTREGADO>=IMPORTETOTAL en todas sus facturas TIPO=13.",
      "SELECT "
      "SUM(CASE WHEN PAGO_CONTADO=1 THEN 1 ELSE 0 END) AS CLIENTES_CONTADO, "
      "SUM(CASE WHEN PAGO_CONTADO=0 THEN 1 ELSE 0 END) AS CLIENTES_CREDITO "
      "FROM (SELECT CODCLIENTE, "
      "CASE WHEN MIN(IMPORTEENTREGADO)>=MIN(IMPORTETOTAL) THEN 1 ELSE 0 END AS PAGO_CONTADO "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE)",
      "Finanzas", "Dirección", "KPI", "Medio", "Formas de pago", ""),

    q("fx3_058", "Importe medio de factura por forma de pago",
      "¿Varía el ticket medio según la forma de pago?",
      "Importe medio de facturas TIPO=13 por CODFORMAPAGO.",
      "SELECT COALESCE(FP.NOMBRE, 'Sin forma pago') AS FORMA_PAGO, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN FORMASPAGO FP ON FP.CODIGO=D.CODFORMAPAGO "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODFORMAPAGO, FP.NOMBRE "
      "ORDER BY TICKET_MEDIO DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Formas de pago", ""),

    q("fx3_059", "Facturas con forma de pago no configurada",
      "¿Cuántas facturas tienen forma de pago no configurada?",
      "Facturas TIPO=13 con CODFORMAPAGO que no existe en FORMASPAGO.",
      "SELECT COUNT(*) AS N_FACTURAS_FORMA_PAGO_INVALIDA "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 AND D.CODFORMAPAGO IS NOT NULL AND D.CODFORMAPAGO>0 "
      "AND D.CODFORMAPAGO NOT IN (SELECT CODIGO FROM FORMASPAGO)",
      "Finanzas", "Dirección", "Operacional", "Medio", "Formas de pago", ""),

    q("fx3_060", "Evolución de cobros por mes (IMPORTEENTREGADO)",
      "¿Cuánto se cobra cada mes?",
      "Suma de IMPORTEENTREGADO en facturas TIPO=13 por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(SUM(IMPORTEENTREGADO),2) AS IMPORTEENTREGADO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Cobros", ""),

    # ── ANÁLISIS DE DOCUMENTOS FINANCIEROS ────────────────────────────────────

    q("fx3_061", "Recibos emitidos por mes",
      "¿Cuántos recibos se emiten cada mes?",
      "Conteo de documentos TIPO=61 (recibos) por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_RECIBOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=61 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Recibos", ""),

    q("fx3_062", "Certificaciones emitidas por mes",
      "¿Cuántas certificaciones se emiten cada mes?",
      "Conteo de documentos TIPO=51 (certificaciones) por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_CERTIFICACIONES, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=51 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Certificaciones", ""),

    q("fx3_063", "Contratos por valor y cliente",
      "¿Cuánto valen los contratos por cliente?",
      "Documentos TIPO=10 (contratos) por cliente con suma de importes.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_CONTRATOS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_CONTRATOS "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=10 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY VALOR_CONTRATOS DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Contratos", ""),

    q("fx3_064", "Valor total de contratos activos",
      "¿Cuánto valen todos los contratos?",
      "Suma de IMPORTETOTAL de documentos TIPO=10.",
      "SELECT COUNT(*) AS N_CONTRATOS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS VALOR_TOTAL, "
      "ROUND(AVG(IMPORTETOTAL),2) AS VALOR_MEDIO "
      "FROM DOCCAB WHERE TIPO=10",
      "Finanzas", "Dirección", "KPI", "Alto", "Contratos", ""),

    q("fx3_065", "Documentos financieros por tipo y año",
      "¿Cuántos documentos de cada tipo financiero hay por año?",
      "Conteo de TIPO=10,51,61 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, TIPO, "
      "CASE TIPO WHEN 10 THEN 'Contrato' WHEN 51 THEN 'Certificación' "
      "WHEN 61 THEN 'Recibo' ELSE 'Otro' END AS DESCRIPCION, "
      "COUNT(*) AS N_DOCS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO IN (10,51,61) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4), TIPO ORDER BY ANIO DESC, N_DOCS DESC",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Documentos", ""),

    # ── ANÁLISIS DE INTEGRIDAD FINANCIERA ─────────────────────────────────────

    q("fx3_066", "Facturas con IMPORTEENTREGADO mayor que IMPORTETOTAL",
      "¿Hay facturas donde se ha IMPORTEENTREGADO más de lo facturado?",
      "Facturas TIPO=13 con IMPORTEENTREGADO>IMPORTETOTAL.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS FACTURADO, "
      "ROUND(D.IMPORTEENTREGADO,2) AS IMPORTEENTREGADO, "
      "ROUND(D.IMPORTEENTREGADO-D.IMPORTETOTAL,2) AS EXCESO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO>D.IMPORTETOTAL "
      "ORDER BY EXCESO DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Alto", "Integridad", ""),

    q("fx3_067", "Facturas con IMPORTEBASE negativa",
      "¿Hay facturas con base imponible negativa?",
      "Facturas TIPO=13 con IMPORTEBASE<0.",
      "SELECT D.CODIGO, D.FECHA, "
      "ROUND(IMPORTEBASE,2) AS BASE, ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEBASE<0 "
      "ORDER BY IMPORTEBASE ASC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Alto", "Integridad", ""),

    q("fx3_068", "Facturas con IMPORTEIVA negativo",
      "¿Hay facturas con IMPORTEIVA negativo?",
      "Facturas TIPO=13 con IMPORTEIVA<0.",
      "SELECT D.CODIGO, D.FECHA, "
      "ROUND(IMPORTEBASE,2) AS BASE, ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEIVA<0 "
      "ORDER BY IMPORTEIVA ASC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Alto", "Integridad", ""),

    q("fx3_069", "Coherencia entre IMPORTEBASE + IMPORTEIVA = IMPORTETOTAL",
      "¿Cuántas facturas tienen coherencia entre base, IMPORTEIVA y total?",
      "Verifica que IMPORTEBASE+IMPORTEIVA≈IMPORTETOTAL en facturas TIPO=13.",
      "SELECT "
      "COUNT(*) AS TOTAL_FACTURAS, "
      "SUM(CASE WHEN ABS(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL)<=0.05 THEN 1 ELSE 0 END) AS COHERENTES, "
      "SUM(CASE WHEN ABS(IMPORTEBASE+IMPORTEIVA-IMPORTETOTAL)>0.05 THEN 1 ELSE 0 END) AS INCOHERENTES "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEBASE IS NOT NULL",
      "Finanzas", "Dirección", "KPI", "Alto", "Integridad", ""),

    q("fx3_070", "Facturas con IMPORTETOTAL NULL",
      "¿Hay facturas sin importe total?",
      "Facturas TIPO=13 con IMPORTETOTAL NULL.",
      "SELECT COUNT(*) AS N_FACTURAS_SIN_IMPORTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL IS NULL",
      "Finanzas", "Dirección", "Operacional", "Crítico", "Integridad", ""),

    # ── ANÁLISIS DE RENTABILIDAD POR SEGMENTO ─────────────────────────────────

    q("fx3_071", "Rentabilidad por segmento de cliente (por importe de compra)",
      "¿Qué segmento de clientes es más rentable?",
      "Clasifica clientes por volumen de compra y calcula margen por segmento.",
      "SELECT "
      "CASE WHEN TOTAL<1000 THEN 'Pequeño (<1K)' "
      "WHEN TOTAL<5000 THEN 'Mediano (1K-5K)' "
      "WHEN TOTAL<20000 THEN 'Grande (5K-20K)' "
      "ELSE 'Muy grande (>20K)' END AS SEGMENTO, "
      "COUNT(*) AS N_CLIENTES, "
      "ROUND(SUM(TOTAL),2) AS FACTURACION_TOTAL, "
      "ROUND(AVG(TOTAL),2) AS MEDIA_POR_CLIENTE "
      "FROM (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) "
      "GROUP BY SEGMENTO ORDER BY FACTURACION_TOTAL DESC",
      "Finanzas", "Dirección", "KPI", "Alto", "Segmentación", ""),

    q("fx3_072", "Rentabilidad por número de facturas del cliente",
      "¿Los clientes con más facturas son más rentables?",
      "Clasifica clientes por frecuencia de compra y calcula facturación media.",
      "SELECT "
      "CASE WHEN N_FACTURAS=1 THEN '1 factura' "
      "WHEN N_FACTURAS BETWEEN 2 AND 5 THEN '2-5 facturas' "
      "WHEN N_FACTURAS BETWEEN 6 AND 10 THEN '6-10 facturas' "
      "ELSE 'Más de 10' END AS SEGMENTO_FRECUENCIA, "
      "COUNT(*) AS N_CLIENTES, "
      "ROUND(SUM(TOTAL),2) AS FACTURACION_TOTAL, "
      "ROUND(AVG(TOTAL),2) AS MEDIA_POR_CLIENTE "
      "FROM (SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS, SUM(IMPORTETOTAL) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) "
      "GROUP BY SEGMENTO_FRECUENCIA ORDER BY FACTURACION_TOTAL DESC",
      "Finanzas", "Dirección", "KPI", "Medio", "Segmentación", ""),

    q("fx3_073", "Top 5 clientes por facturación del año actual",
      "¿Cuáles son los 5 mejores clientes del año?",
      "Top 5 clientes por IMPORTETOTAL TIPO=13 en el año actual.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY FACTURACION DESC LIMIT 5",
      "Finanzas", "Dirección", "KPI", "Alto", "Ranking", ""),

    q("fx3_074", "Facturación de los últimos 30 días",
      "¿Cuánto se ha facturado en los últimos 30 días?",
      "Suma de IMPORTETOTAL TIPO=13 en los últimos 30 días.",
      "SELECT COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO_30D, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA>=DATE('now','-30 days')",
      "Finanzas", "Dirección", "KPI", "Alto", "Período", ""),

    q("fx3_075", "Comparativa facturación últimos 30 días vs 30 días anteriores",
      "¿Cómo compara la facturación de los últimos 30 días con los 30 anteriores?",
      "Compara IMPORTETOTAL TIPO=13 de los últimos 30 días vs los 30 anteriores.",
      "SELECT "
      "ROUND(SUM(CASE WHEN FECHA>=DATE('now','-30 days') THEN IMPORTETOTAL ELSE 0 END),2) AS ULTIMOS_30D, "
      "ROUND(SUM(CASE WHEN FECHA>=DATE('now','-60 days') AND FECHA<DATE('now','-30 days') THEN IMPORTETOTAL ELSE 0 END),2) AS ANTERIORES_30D "
      "FROM DOCCAB WHERE TIPO=13",
      "Finanzas", "Dirección", "KPI", "Alto", "Comparativa", ""),

    # ── ANÁLISIS DE STOCKARTICULO FINANCIERO ───────────────────────────────────────────

    q("fx3_076", "Rotación de inventario anual",
      "¿Cuántas veces rota el inventario al año?",
      "COGS anual / valor medio del inventario.",
      "SELECT ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS_ANUAL, "
      "ROUND((SELECT SUM(STOCKARTICULO*PRECIOCOSTE) FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0),2) AS VALOR_INVENTARIO, "
      "ROUND(SUM(A.PRECIOCOSTE*L.STOCKARTICULO)/(SELECT SUM(STOCKARTICULO*PRECIOCOSTE) FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0),2) AS ROTACION_INVENTARIO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4)",
      "Finanzas", "Dirección", "KPI", "Alto", "Inventario", ""),

    q("fx3_077", "Días de inventario (DIO)",
      "¿Cuántos días de ventas cubre el inventario actual?",
      "Valor inventario / (COGS diario).",
      "SELECT ROUND((SELECT SUM(STOCKARTICULO*PRECIOCOSTE) FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0),2) AS VALOR_INVENTARIO, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD)/365,2) AS COGS_DIARIO, "
      "ROUND((SELECT SUM(STOCKARTICULO*PRECIOCOSTE) FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0)/"
      "NULLIF(SUM(A.PRECIOCOSTE*L.CANTIDAD)/365,0),0) AS DIO_DIAS "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0",
      "Finanzas", "Dirección", "KPI", "Alto", "Inventario", ""),

    q("fx3_078", "Artículos con mayor impacto en el valor del inventario",
      "¿Qué artículos representan más del 80% del valor del inventario?",
      "Artículos ordenados por STOCKARTICULO*PRECIOCOSTE con % acumulado.",
      "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCKARTICULO, "
      "ROUND(PRECIOCOSTE,2) AS COSTE, "
      "ROUND(STOCKARTICULO*PRECIOCOSTE,2) AS VALOR, "
      "ROUND(STOCKARTICULO*PRECIOCOSTE*100.0/"
      "(SELECT SUM(STOCKARTICULO*PRECIOCOSTE) FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0),1) AS PCT "
      "FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0 "
      "ORDER BY VALOR DESC LIMIT 20",
      "Finanzas", "Dirección", "Artículo", "Alto", "Inventario", ""),

    q("fx3_079", "Valor del STOCKARTICULO inmovilizado (sin ventas en 6 meses)",
      "¿Cuánto vale el STOCKARTICULO que no se ha vendido en 6 meses?",
      "Suma de STOCKARTICULO*PRECIOCOSTE de artículos sin ventas en 180 días.",
      "SELECT COUNT(*) AS N_ARTICULOS_INMOVILIZADOS, "
      "ROUND(SUM(A.STOCKARTICULO*A.PRECIOCOSTE),2) AS VALOR_INMOVILIZADO "
      "FROM ARTICULO A "
      "WHERE A.STOCKARTICULO>0 AND A.PRECIOCOSTE>0 "
      "AND A.CODIGO NOT IN ("
      "SELECT DISTINCT L.CODARTICULO FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-180 days'))",
      "Finanzas", "Dirección", "KPI", "Alto", "Inventario", ""),

    q("fx3_080", "Margen potencial del inventario actual",
      "¿Cuánto margen se puede obtener vendiendo el inventario actual?",
      "Diferencia entre valor de venta y PRECIOCOSTE del inventario actual.",
      "SELECT ROUND(SUM(STOCKARTICULO*PRECIOCOSTE),2) AS VALOR_COSTE, "
      "ROUND(SUM(STOCKARTICULO*PRECIOVENTA),2) AS VALOR_VENTA, "
      "ROUND(SUM(STOCKARTICULO*PRECIOVENTA)-SUM(STOCKARTICULO*PRECIOCOSTE),2) AS MARGEN_POTENCIAL, "
      "ROUND((SUM(STOCKARTICULO*PRECIOVENTA)-SUM(STOCKARTICULO*PRECIOCOSTE))*100.0/"
      "NULLIF(SUM(STOCKARTICULO*PRECIOVENTA),0),1) AS MARGEN_PCT "
      "FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0 AND PRECIOVENTA>0",
      "Finanzas", "Dirección", "KPI", "Alto", "Inventario", ""),

    # ── ANÁLISIS DE TENDENCIAS FINANCIERAS ────────────────────────────────────

    q("fx3_081", "Crecimiento de facturación año a año",
      "¿Cuál es el crecimiento de facturación año a año?",
      "Variación porcentual de IMPORTETOTAL TIPO=13 entre años.",
      "SELECT ANIO, TOTAL, "
      "ROUND((TOTAL-LAG(TOTAL) OVER (ORDER BY ANIO))*100.0/"
      "NULLIF(LAG(TOTAL) OVER (ORDER BY ANIO),0),1) AS CRECIMIENTO_PCT "
      "FROM (SELECT SUBSTR(FECHA,1,4) AS ANIO, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4)) "
      "ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Crítico", "Tendencias", ""),

    q("fx3_082", "Tendencia de cobros: ratio IMPORTEENTREGADO/facturado por trimestre",
      "¿Mejora o empeora el ratio de cobro por trimestre?",
      "Ratio IMPORTEENTREGADO/IMPORTETOTAL en facturas TIPO=13 por trimestre.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "CASE WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO, "
      "ROUND(SUM(IMPORTEENTREGADO),2) AS IMPORTEENTREGADO, "
      "ROUND(SUM(IMPORTEENTREGADO)*100.0/NULLIF(SUM(IMPORTETOTAL),0),1) AS RATIO_COBRO_PCT "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO, TRIMESTRE ORDER BY ANIO DESC, TRIMESTRE",
      "Finanzas", "Dirección", "KPI", "Alto", "Tendencias", ""),

    q("fx3_083", "Evolución del número de facturas emitidas por año",
      "¿Cómo evoluciona el número de facturas emitidas?",
      "Conteo de facturas TIPO=13 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Medio", "Tendencias", ""),

    q("fx3_084", "Evolución del número de clientes activos por año",
      "¿Cómo evoluciona el número de clientes activos por año?",
      "Clientes únicos con facturas TIPO=13 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES_ACTIVOS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Medio", "Tendencias", ""),

    q("fx3_085", "Evolución del ticket medio por año",
      "¿Cómo evoluciona el ticket medio anual?",
      "Importe medio por factura TIPO=13 por año.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Medio", "Tendencias", ""),

    # ── ANÁLISIS DE DATOS FINANCIEROS MAESTROS ────────────────────────────────

    q("fx3_086", "Clientes con límite de crédito configurado",
      "¿Qué clientes tienen límite de crédito?",
      "Clientes con LIMITECREDITO>0 en la tabla CLIENTE.",
      "SELECT CODIGO, COALESCE(NOMBRECOMERCIAL, RAZONSOCIAL) AS NOMBRE, "
      "ROUND(LIMITECREDITO,2) AS LIMITE_CREDITO "
      "FROM CLIENTE WHERE LIMITECREDITO>0 "
      "ORDER BY LIMITECREDITO DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Crédito", ""),

    q("fx3_087", "Clientes que superan su límite de crédito",
      "¿Qué clientes tienen deuda superior a su límite de crédito?",
      "Clientes donde deuda pendiente > LIMITECREDITO.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(C.LIMITECREDITO,2) AS LIMITE_CREDITO, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO),2) AS DEUDA_ACTUAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL>D.IMPORTEENTREGADO "
      "AND C.LIMITECREDITO>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL, C.LIMITECREDITO "
      "HAVING SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO)>C.LIMITECREDITO "
      "ORDER BY DEUDA_ACTUAL DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Crédito", ""),

    q("fx3_088", "Clientes con riesgo de impago (deuda > 90 días)",
      "¿Qué clientes tienen deuda de más de 90 días?",
      "Clientes con facturas TIPO=13 sin cobrar de más de 90 días.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS_RIESGO, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO),2) AS DEUDA_RIESGO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL>D.IMPORTEENTREGADO "
      "AND D.FECHA IS NOT NULL AND JULIANDAY('now')-JULIANDAY(D.FECHA)>90 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY DEUDA_RIESGO DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Riesgo crediticio", ""),

    q("fx3_089", "Provisión estimada de insolvencias",
      "¿Cuánto habría que provisionar por insolvencias?",
      "Deuda pendiente por tramos de antigüedad con % de provisión estimado.",
      "SELECT TRAMO, N_FACTURAS, PENDIENTE, "
      "ROUND(PENDIENTE*PCT_PROVISION/100.0,2) AS PROVISION_ESTIMADA "
      "FROM ("
      "SELECT "
      "CASE WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=90 THEN '0-90 días (5%)' "
      "WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=180 THEN '91-180 días (25%)' "
      "WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=365 THEN '181-365 días (50%)' "
      "ELSE 'Más de 1 año (100%)' END AS TRAMO, "
      "CASE WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=90 THEN 5 "
      "WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=180 THEN 25 "
      "WHEN JULIANDAY('now')-JULIANDAY(FECHA)<=365 THEN 50 "
      "ELSE 100 END AS PCT_PROVISION, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO AND FECHA IS NOT NULL "
      "GROUP BY TRAMO, PCT_PROVISION) "
      "ORDER BY PCT_PROVISION",
      "Finanzas", "Dirección", "KPI", "Crítico", "Provisiones", ""),

    q("fx3_090", "Resumen financiero ejecutivo",
      "¿Cuál es el resumen financiero completo de la empresa?",
      "KPIs financieros: facturación, cobros, pendiente, IVA, margen.",
      "SELECT "
      "(SELECT ROUND(SUM(IMPORTETOTAL),2) FROM DOCCAB WHERE TIPO=13) AS FACTURACION_TOTAL, "
      "(SELECT ROUND(SUM(IMPORTEENTREGADO),2) FROM DOCCAB WHERE TIPO=13) AS TOTAL_COBRADO, "
      "(SELECT ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO) AS PENDIENTE_COBRO, "
      "(SELECT ROUND(SUM(IMPORTEIVA),2) FROM DOCCAB WHERE TIPO=13) AS IVA_REPERCUTIDO, "
      "(SELECT ROUND(SUM(ABS(IMPORTETOTAL)),2) FROM DOCCAB WHERE TIPO=3) AS TOTAL_ABONOS, "
      "(SELECT ROUND(SUM(IMPORTE),2) FROM CAJA) AS SALDO_CAJA",
      "Finanzas", "Dirección", "KPI", "Crítico", "Resumen ejecutivo", ""),

    # ── ANÁLISIS DE COMPRAS FINANCIERO ────────────────────────────────────────

    q("fx3_091", "Evolución de compras por mes (documentos de compra)",
      "¿Cuánto se compra cada mes?",
      "Suma de IMPORTETOTAL de documentos de compra por mes.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, TIPO, "
      "COUNT(*) AS N_DOCS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO NOT IN (13,3) AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7), TIPO "
      "ORDER BY MES DESC, TOTAL DESC LIMIT 30",
      "Finanzas", "Compras", "KPI", "Medio", "Compras", ""),

    q("fx3_092", "Ratio ventas/compras por mes",
      "¿Cuánto se vende por cada euro comprado?",
      "Ratio de IMPORTETOTAL TIPO=13 vs documentos de compra por mes.",
      "SELECT V.MES, V.VENTAS, COALESCE(C.COMPRAS,0) AS COMPRAS, "
      "ROUND(V.VENTAS/NULLIF(COALESCE(C.COMPRAS,0),0),2) AS RATIO_VENTAS_COMPRAS "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS VENTAS "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) V "
      "LEFT JOIN (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS COMPRAS "
      "FROM DOCCAB WHERE TIPO NOT IN (13,3) AND FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) C "
      "ON V.MES=C.MES "
      "ORDER BY V.MES DESC LIMIT 12",
      "Finanzas", "Dirección", "KPI", "Alto", "Compras", ""),

    q("fx3_093", "PRECIOCOSTE de compras por proveedor",
      "¿Cuánto se compra a cada proveedor?",
      "Suma de IMPORTETOTAL de documentos de compra por proveedor.",
      "SELECT COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL) AS PROVEEDOR, "
      "COUNT(*) AS N_DOCS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_COMPRAS "
      "FROM DOCCAB D "
      "LEFT JOIN PROVEED P ON P.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO NOT IN (13,3) AND D.CODCLIENTE IS NOT NULL "
      "GROUP BY D.CODCLIENTE, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
      "ORDER BY TOTAL_COMPRAS DESC LIMIT 20",
      "Finanzas", "Compras", "KPI", "Alto", "Compras", ""),

    q("fx3_094", "Concentración de compras en proveedores",
      "¿Qué porcentaje de las compras se concentra en los 5 principales proveedores?",
      "Facturación de los 5 primeros proveedores vs total de compras.",
      "SELECT ROUND(SUM(CASE WHEN RK<=5 THEN TOTAL ELSE 0 END)*100.0/NULLIF(SUM(TOTAL),0),1) AS PCT_TOP5, "
      "ROUND(SUM(TOTAL),2) AS TOTAL_COMPRAS "
      "FROM (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL, "
      "ROW_NUMBER() OVER (ORDER BY SUM(IMPORTETOTAL) DESC) AS RK "
      "FROM DOCCAB WHERE TIPO NOT IN (13,3) AND CODCLIENTE IS NOT NULL "
      "GROUP BY CODCLIENTE)",
      "Finanzas", "Compras", "KPI", "Alto", "Concentración", ""),

    q("fx3_095", "Artículos con mayor PRECIOCOSTE de compra en el año",
      "¿Qué artículos han supuesto mayor PRECIOCOSTE de compra?",
      "Suma de PRECIOCOSTE*CANTIDAD por artículo en el año actual.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "SUM(L.CANTIDAD) AS UNIDADES_COMPRADAS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COSTE_TOTAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY COSTE_TOTAL DESC LIMIT 20",
      "Finanzas", "Compras", "Artículo", "Alto", "Compras", ""),

    # ── ANÁLISIS DE EFICIENCIA FINANCIERA ─────────────────────────────────────

    q("fx3_096", "Eficiencia de cobro por agente",
      "¿Qué agente tiene mejor ratio de cobro?",
      "Ratio IMPORTEENTREGADO/IMPORTETOTAL por CODAGENTE en facturas TIPO=13.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURADO, "
      "ROUND(SUM(D.IMPORTEENTREGADO),2) AS IMPORTEENTREGADO, "
      "ROUND(SUM(D.IMPORTEENTREGADO)*100.0/NULLIF(SUM(D.IMPORTETOTAL),0),1) AS RATIO_COBRO_PCT "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODAGENTE ORDER BY RATIO_COBRO_PCT DESC",
      "Finanzas", "Comercial", "Agente", "Alto", "Cobros", ""),

    q("fx3_097", "Facturas con mayor importe pendiente de cobro",
      "¿Cuáles son las facturas con mayor deuda pendiente?",
      "Top 20 facturas TIPO=13 por IMPORTETOTAL-IMPORTEENTREGADO.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS TOTAL, "
      "ROUND(D.IMPORTEENTREGADO,2) AS IMPORTEENTREGADO, "
      "ROUND(D.IMPORTETOTAL-D.IMPORTEENTREGADO,2) AS PENDIENTE "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTETOTAL>D.IMPORTEENTREGADO "
      "ORDER BY PENDIENTE DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Crítico", "Cobros", ""),

    q("fx3_098", "Análisis de morosidad: clientes con múltiples facturas impagadas",
      "¿Qué clientes tienen más de 3 facturas sin cobrar?",
      "Clientes con más de 3 facturas TIPO=13 con IMPORTEENTREGADO=0.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS_IMPAGADAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS IMPORTE_TOTAL_IMPAGADO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING COUNT(*)>3 "
      "ORDER BY IMPORTE_TOTAL_IMPAGADO DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Morosidad", ""),

    q("fx3_099", "Importe medio de deuda por cliente moroso",
      "¿Cuál es la deuda media por cliente con impagos?",
      "Promedio de IMPORTETOTAL-IMPORTEENTREGADO por cliente con deuda.",
      "SELECT COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES_CON_DEUDA, "
      "ROUND(AVG(DEUDA_CLIENTE),2) AS DEUDA_MEDIA_POR_CLIENTE, "
      "ROUND(MAX(DEUDA_CLIENTE),2) AS DEUDA_MAX_CLIENTE "
      "FROM (SELECT CODCLIENTE, SUM(IMPORTETOTAL-IMPORTEENTREGADO) AS DEUDA_CLIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO "
      "GROUP BY CODCLIENTE)",
      "Finanzas", "Dirección", "KPI", "Alto", "Morosidad", ""),

    q("fx3_100", "Dashboard financiero completo",
      "¿Cuál es el estado financiero completo de la empresa?",
      "KPIs financieros clave en una sola consulta.",
      "SELECT "
      "(SELECT ROUND(SUM(IMPORTETOTAL),2) FROM DOCCAB WHERE TIPO=13) AS FACTURACION_TOTAL, "
      "(SELECT ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO) AS PENDIENTE_COBRO, "
      "(SELECT ROUND(SUM(IMPORTEIVA),2) FROM DOCCAB WHERE TIPO=13) AS IVA_REPERCUTIDO, "
      "(SELECT ROUND(SUM(ABS(IMPORTETOTAL)),2) FROM DOCCAB WHERE TIPO=3) AS ABONOS, "
      "(SELECT ROUND(SUM(IMPORTE),2) FROM CAJA) AS SALDO_CAJA, "
      "(SELECT ROUND(SUM(STOCKARTICULO*PRECIOCOSTE),2) FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0) AS VALOR_INVENTARIO",
      "Finanzas", "Dirección", "KPI", "Crítico", "Dashboard", ""),

    # ── ANÁLISIS DE GASTOS OPERATIVOS ──────────────────────────────────────────

    q("fx3_101", "Movimientos de caja por concepto",
      "¿Cuáles son los conceptos más frecuentes en caja?",
      "Agrupa movimientos de CAJA por CONCEPTO.",
      "SELECT CONCEPTO, COUNT(*) AS N_MOVIMIENTOS, "
      "ROUND(SUM(IMPORTE),2) AS IMPORTE_TOTAL "
      "FROM CAJA WHERE CONCEPTO IS NOT NULL AND TRIM(CONCEPTO)<>'' "
      "GROUP BY CONCEPTO ORDER BY ABS(IMPORTE_TOTAL) DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    q("fx3_102", "Caja: movimientos sin concepto",
      "¿Cuántos movimientos de caja no tienen concepto?",
      "Registros de CAJA con CONCEPTO NULL o vacío.",
      "SELECT COUNT(*) AS N_SIN_CONCEPTO, "
      "ROUND(SUM(ABS(IMPORTE)),2) AS IMPORTE_TOTAL "
      "FROM CAJA WHERE CONCEPTO IS NULL OR TRIM(CONCEPTO)=''",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    q("fx3_103", "Caja: distribución por importe (tramos)",
      "¿Cómo se distribuyen los movimientos de caja por importe?",
      "Clasifica movimientos de CAJA por tramos de importe.",
      "SELECT "
      "CASE WHEN ABS(IMPORTE)<100 THEN 'Menos de 100€' "
      "WHEN ABS(IMPORTE)<500 THEN '100-500€' "
      "WHEN ABS(IMPORTE)<1000 THEN '500-1000€' "
      "WHEN ABS(IMPORTE)<5000 THEN '1000-5000€' "
      "ELSE 'Más de 5000€' END AS TRAMO, "
      "COUNT(*) AS N_MOVIMIENTOS, "
      "ROUND(SUM(ABS(IMPORTE)),2) AS IMPORTE_TOTAL "
      "FROM CAJA "
      "GROUP BY TRAMO ORDER BY MIN(ABS(IMPORTE))",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Caja", ""),

    q("fx3_104", "Caja: saldo al final de cada mes",
      "¿Cuál es el saldo de caja al final de cada mes?",
      "Saldo acumulado de CAJA al final de cada mes.",
      "SELECT MES, ROUND(SUM(FLUJO) OVER (ORDER BY MES),2) AS SALDO_FINAL "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, SUM(IMPORTE) AS FLUJO "
      "FROM CAJA WHERE FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) "
      "ORDER BY MES DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Caja", ""),

    q("fx3_105", "Caja: meses con saldo negativo",
      "¿Hay meses donde el flujo de caja es negativo?",
      "Meses con SUM(IMPORTE)<0 en CAJA.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTE),2) AS FLUJO_NETO "
      "FROM CAJA WHERE FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) HAVING SUM(IMPORTE)<0 "
      "ORDER BY FLUJO_NETO ASC LIMIT 12",
      "Finanzas", "Dirección", "KPI", "Alto", "Caja", ""),

    # ── ANÁLISIS DE CLIENTES FINANCIERO ───────────────────────────────────────

    q("fx3_106", "Clientes con mayor facturación en el año actual",
      "¿Cuáles son los mejores clientes del año actual?",
      "Top 20 clientes por IMPORTETOTAL TIPO=13 en el año actual.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY FACTURACION DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Ranking", ""),

    q("fx3_107", "Clientes con mayor crecimiento de facturación",
      "¿Qué clientes han crecido más en facturación este año?",
      "Variación de facturación TIPO=13 por cliente entre año actual y anterior.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(COALESCE(ACT.TOTAL,0),2) AS ANIO_ACTUAL, "
      "ROUND(COALESCE(ANT.TOTAL,0),2) AS ANIO_ANTERIOR, "
      "ROUND(COALESCE(ACT.TOTAL,0)-COALESCE(ANT.TOTAL,0),2) AS VARIACION_ABS, "
      "ROUND((COALESCE(ACT.TOTAL,0)-COALESCE(ANT.TOTAL,0))*100.0/"
      "NULLIF(COALESCE(ANT.TOTAL,0),0),1) AS VARIACION_PCT "
      "FROM CLIENTE C "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=SUBSTR(DATE('now'),1,4) GROUP BY CODCLIENTE) ACT "
      "ON ACT.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,4)=CAST(CAST(SUBSTR(DATE('now'),1,4) AS INTEGER)-1 AS TEXT) "
      "GROUP BY CODCLIENTE) ANT ON ANT.CODCLIENTE=C.CODIGO "
      "WHERE COALESCE(ANT.TOTAL,0)>0 "
      "ORDER BY VARIACION_PCT DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Crecimiento", ""),

    q("fx3_108", "Clientes con mayor deuda relativa a su facturación",
      "¿Qué clientes tienen mayor deuda relativa?",
      "Ratio deuda/facturación total por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION_TOTAL, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO),2) AS DEUDA, "
      "ROUND(SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO)*100.0/NULLIF(SUM(D.IMPORTETOTAL),0),1) AS RATIO_DEUDA_PCT "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "HAVING SUM(D.IMPORTETOTAL-D.IMPORTEENTREGADO)>0 "
      "ORDER BY RATIO_DEUDA_PCT DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Crítico", "Riesgo crediticio", ""),

    q("fx3_109", "Clientes con facturación creciente 3 meses consecutivos",
      "¿Qué clientes llevan 3 meses consecutivos creciendo?",
      "Clientes con facturación TIPO=13 mayor cada mes en los últimos 3 meses.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(COALESCE(M1.TOTAL,0),2) AS MES_ACTUAL, "
      "ROUND(COALESCE(M2.TOTAL,0),2) AS MES_ANTERIOR, "
      "ROUND(COALESCE(M3.TOTAL,0),2) AS DOS_MESES_ATRAS "
      "FROM CLIENTE C "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7) GROUP BY CODCLIENTE) M1 "
      "ON M1.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now','-1 month'),1,7) GROUP BY CODCLIENTE) M2 "
      "ON M2.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now','-2 months'),1,7) GROUP BY CODCLIENTE) M3 "
      "ON M3.CODCLIENTE=C.CODIGO "
      "WHERE COALESCE(M1.TOTAL,0)>COALESCE(M2.TOTAL,0) "
      "AND COALESCE(M2.TOTAL,0)>COALESCE(M3.TOTAL,0) "
      "AND COALESCE(M3.TOTAL,0)>0 "
      "ORDER BY MES_ACTUAL DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Medio", "Tendencias", ""),

    q("fx3_110", "Clientes con facturación decreciente 3 meses consecutivos",
      "¿Qué clientes llevan 3 meses consecutivos decreciendo?",
      "Clientes con facturación TIPO=13 menor cada mes en los últimos 3 meses.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(COALESCE(M1.TOTAL,0),2) AS MES_ACTUAL, "
      "ROUND(COALESCE(M2.TOTAL,0),2) AS MES_ANTERIOR, "
      "ROUND(COALESCE(M3.TOTAL,0),2) AS DOS_MESES_ATRAS "
      "FROM CLIENTE C "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7) GROUP BY CODCLIENTE) M1 "
      "ON M1.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now','-1 month'),1,7) GROUP BY CODCLIENTE) M2 "
      "ON M2.CODCLIENTE=C.CODIGO "
      "LEFT JOIN (SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL FROM DOCCAB "
      "WHERE TIPO=13 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now','-2 months'),1,7) GROUP BY CODCLIENTE) M3 "
      "ON M3.CODCLIENTE=C.CODIGO "
      "WHERE COALESCE(M1.TOTAL,0)<COALESCE(M2.TOTAL,0) "
      "AND COALESCE(M2.TOTAL,0)<COALESCE(M3.TOTAL,0) "
      "AND COALESCE(M1.TOTAL,0)>0 "
      "ORDER BY MES_ACTUAL ASC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Alto", "Tendencias", ""),

    # ── ANÁLISIS DE ARTÍCULOS FINANCIERO ──────────────────────────────────────

    q("fx3_111", "Artículos con mayor contribución al margen bruto",
      "¿Qué artículos contribuyen más al margen bruto total?",
      "Suma de (PRECIOVENTA-PRECIOCOSTE)*unidades por artículo con % sobre margen total.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD)*100.0/"
      "(SELECT SUM((L2.PRECIO-A2.PRECIOCOSTE)*L2.CANTIDAD) "
      "FROM DOCLIN L2 JOIN DOCCAB D2 ON D2.CODIGO=L2.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A2 ON A2.CODIGO=L2.CODIGO "
      "WHERE D2.TIPO=13 AND A2.PRECIOCOSTE>0),1) AS PCT_MARGEN_TOTAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE "
      "ORDER BY MARGEN DESC LIMIT 20",
      "Finanzas", "Dirección", "Artículo", "Alto", "Margen", ""),

    q("fx3_112", "Artículos con margen negativo en el año actual",
      "¿Qué artículos se venden a pérdida en el año actual?",
      "Artículos con margen bruto negativo en facturas TIPO=13 del año actual.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN_TOTAL "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY L.CODARTICULO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD)<0 "
      "ORDER BY MARGEN_TOTAL ASC LIMIT 20",
      "Finanzas", "Dirección", "Artículo", "Crítico", "Margen", ""),

    q("fx3_113", "Evolución del margen por artículo mes a mes",
      "¿Cómo evoluciona el margen de los artículos más vendidos?",
      "Margen bruto por artículo y mes en los últimos 6 meses.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "AND D.FECHA>=DATE('now','-6 months') "
      "GROUP BY L.CODARTICULO, A.NOMBRE, SUBSTR(D.FECHA,1,7) "
      "ORDER BY L.CODARTICULO, MES DESC LIMIT 60",
      "Finanzas", "Dirección", "Artículo", "Medio", "Margen", ""),

    q("fx3_114", "Artículos con mayor variación de margen entre meses",
      "¿En qué artículos varía más el margen entre meses?",
      "Diferencia entre margen máximo y mínimo mensual por artículo.",
      "SELECT COD_ART, ARTICULO, "
      "ROUND(MAX(MARGEN_MES),2) AS MARGEN_MAX, "
      "ROUND(MIN(MARGEN_MES),2) AS MARGEN_MIN, "
      "ROUND(MAX(MARGEN_MES)-MIN(MARGEN_MES),2) AS VARIACION "
      "FROM (SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "SUBSTR(D.FECHA,1,7) AS MES, "
      "SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD) AS MARGEN_MES "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE, SUBSTR(D.FECHA,1,7)) "
      "GROUP BY COD_ART, ARTICULO "
      "HAVING COUNT(*)>2 "
      "ORDER BY VARIACION DESC LIMIT 20",
      "Finanzas", "Dirección", "Artículo", "Medio", "Margen", ""),

    q("fx3_115", "Artículos con margen superior al 50%",
      "¿Qué artículos tienen margen bruto superior al 50%?",
      "Artículos con (PRECIOVENTA-PRECIOCOSTE)/PRECIOVENTA > 50% en facturas TIPO=13.",
      "SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO, "
      "ROUND(A.PRECIOCOSTE,2) AS COSTE, "
      "ROUND((AVG(L.PRECIO)-A.PRECIOCOSTE)*100.0/NULLIF(AVG(L.PRECIO),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE, A.PRECIOCOSTE "
      "HAVING MARGEN_PCT>50 "
      "ORDER BY MARGEN_PCT DESC LIMIT 20",
      "Finanzas", "Dirección", "Artículo", "Medio", "Margen", ""),

    # ── ANÁLISIS DE PREVISIÓN ──────────────────────────────────────────────────

    q("fx3_116", "Previsión de cobros próximos 30 días",
      "¿Cuánto se espera cobrar en los próximos 30 días?",
      "Facturas TIPO=13 pendientes de cobro emitidas en los últimos 60 días.",
      "SELECT COUNT(*) AS N_FACTURAS_PENDIENTES, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS COBRO_ESPERADO "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO "
      "AND FECHA>=DATE('now','-60 days')",
      "Finanzas", "Dirección", "KPI", "Alto", "Previsión", ""),

    q("fx3_117", "Previsión de facturación basada en media histórica",
      "¿Cuánto se espera facturar el próximo mes basándose en el histórico?",
      "Media de facturación TIPO=13 de los últimos 6 meses como previsión.",
      "SELECT ROUND(AVG(TOTAL),2) AS PREVISION_PROXIMO_MES "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, SUM(IMPORTETOTAL) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "AND FECHA>=DATE('now','-6 months') "
      "GROUP BY SUBSTR(FECHA,1,7))",
      "Finanzas", "Dirección", "KPI", "Medio", "Previsión", ""),

    q("fx3_118", "Valor del pipeline de presupuestos como previsión de ingresos",
      "¿Cuánto podría ingresar si se convierten todos los presupuestos pendientes?",
      "Suma de IMPORTETOTAL de presupuestos TIPO=0 sin conversión.",
      "SELECT COUNT(*) AS N_PRESUPUESTOS_PENDIENTES, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS VALOR_PIPELINE "
      "FROM DOCCAB D "
      "LEFT JOIN DOCDESTINO DD ON DD.CODDOCUMENTO=D.CODIGO "
      "WHERE D.TIPO=0 AND DD.CODDOCUMENTO IS NULL",
      "Finanzas", "Dirección", "KPI", "Alto", "Previsión", ""),

    q("fx3_119", "Estacionalidad de facturación: índice por mes del año",
      "¿Qué meses del año tienen más facturación históricamente?",
      "Índice de estacionalidad por mes (1=enero, 12=diciembre).",
      "SELECT CAST(SUBSTR(FECHA,6,2) AS INTEGER) AS MES_NUM, "
      "CASE CAST(SUBSTR(FECHA,6,2) AS INTEGER) "
      "WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo' "
      "WHEN 4 THEN 'Abril' WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio' "
      "WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Septiembre' "
      "WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' ELSE 'Diciembre' END AS MES_NOMBRE, "
      "ROUND(AVG(TOTAL_MES),2) AS MEDIA_MENSUAL "
      "FROM (SELECT SUBSTR(FECHA,6,2) AS MES, SUBSTR(FECHA,1,4) AS ANIO, "
      "SUM(IMPORTETOTAL) AS TOTAL_MES "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,6,2), SUBSTR(FECHA,1,4)) "
      "GROUP BY MES_NUM ORDER BY MES_NUM",
      "Finanzas", "Dirección", "KPI", "Medio", "Estacionalidad", ""),

    q("fx3_120", "Análisis de Pareto de artículos por margen",
      "¿Qué artículos generan el 80% del margen bruto?",
      "Artículos ordenados por margen con % acumulado.",
      "SELECT COD_ART, ARTICULO, MARGEN, "
      "ROUND(SUM(MARGEN) OVER (ORDER BY MARGEN DESC)*100.0/"
      "(SELECT SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD) "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0),1) AS PCT_ACUMULADO "
      "FROM (SELECT L.CODARTICULO AS COD_ART, A.NOMBRE AS ARTICULO, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY L.CODARTICULO, A.NOMBRE) "
      "ORDER BY MARGEN DESC LIMIT 30",
      "Finanzas", "Dirección", "KPI", "Alto", "Pareto", ""),

    # ── ANÁLISIS ADICIONAL ─────────────────────────────────────────────────────

    q("fx3_121", "Facturas emitidas en festivos o fines de semana",
      "¿Hay facturas emitidas en sábado o domingo?",
      "Facturas TIPO=13 con FECHA en sábado (6) o domingo (0) según SQLite.",
      "SELECT CAST(STRFTIME('%w', FECHA) AS INTEGER) AS DIA_SEMANA, "
      "CASE CAST(STRFTIME('%w', FECHA) AS INTEGER) WHEN 0 THEN 'Domingo' ELSE 'Sábado' END AS DIA, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "AND CAST(STRFTIME('%w', FECHA) AS INTEGER) IN (0,6) "
      "GROUP BY DIA_SEMANA ORDER BY N_FACTURAS DESC",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Estacionalidad", ""),

    q("fx3_122", "Facturas con número de documento no secuencial",
      "¿Hay saltos en la numeración de facturas?",
      "Detecta gaps en la secuencia de CODIGO en facturas TIPO=13.",
      "SELECT CODIGO, CODIGO-LAG(CODIGO) OVER (ORDER BY CODIGO) AS SALTO "
      "FROM DOCCAB WHERE TIPO=13 "
      "HAVING SALTO>1 "
      "ORDER BY CODIGO LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Medio", "Integridad", ""),

    q("fx3_123", "Facturas con el mismo importe (posibles duplicados)",
      "¿Hay facturas con el mismo importe y cliente en el mismo mes?",
      "Facturas TIPO=13 con mismo CODCLIENTE, IMPORTETOTAL y mes.",
      "SELECT CODCLIENTE, SUBSTR(FECHA,1,7) AS MES, "
      "ROUND(IMPORTETOTAL,2) AS IMPORTE, COUNT(*) AS N_FACTURAS "
      "FROM DOCCAB WHERE TIPO=13 "
      "GROUP BY CODCLIENTE, SUBSTR(FECHA,1,7), ROUND(IMPORTETOTAL,2) "
      "HAVING COUNT(*)>1 "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Alto", "Integridad", ""),

    q("fx3_124", "Análisis de concentración de IMPORTEIVA por cliente",
      "¿Qué clientes generan más IMPORTEIVA?",
      "Suma de IMPORTEIVA en facturas TIPO=13 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(D.IMPORTEIVA),2) AS IVA_TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEIVA>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY IVA_TOTAL DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Medio", "IMPORTEIVA", ""),

    q("fx3_125", "Resumen de KPIs financieros por departamento",
      "¿Cuáles son los KPIs financieros por tipo de documento?",
      "Resumen de IMPORTETOTAL, IMPORTEBASE, IMPORTEIVA por TIPO.",
      "SELECT TIPO, "
      "CASE TIPO WHEN 0 THEN 'Presupuesto' WHEN 2 THEN 'SAT' WHEN 3 THEN 'Abono' "
      "WHEN 10 THEN 'Contrato' WHEN 11 THEN 'Albarán' WHEN 12 THEN 'Pedido' "
      "WHEN 13 THEN 'Factura' WHEN 51 THEN 'Certificación' WHEN 61 THEN 'Recibo' "
      "ELSE 'Otro' END AS DESCRIPCION, "
      "COUNT(*) AS N_DOCS, "
      "ROUND(SUM(IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_TOTAL, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB GROUP BY TIPO ORDER BY TOTAL DESC",
      "Finanzas", "Dirección", "KPI", "Crítico", "Resumen ejecutivo", ""),

    q("fx3_126", "Facturas con IRPF por agente",
      "¿Qué agentes emiten facturas con IRPF?",
      "Facturas TIPO=13 con IMPORTEIRPF>0 por CODAGENTE.",
      "SELECT CODAGENTE AS AGENTE, COUNT(*) AS N_FACTURAS_CON_IRPF, "
      "ROUND(SUM(IMPORTEIRPF),2) AS TOTAL_IRPF "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEIRPF>0 "
      "GROUP BY CODAGENTE ORDER BY TOTAL_IRPF DESC",
      "Finanzas", "Comercial", "Agente", "Bajo", "IRPF", ""),

    q("fx3_127", "Facturas con recargo de equivalencia por cliente",
      "¿Qué clientes tienen recargo de equivalencia?",
      "Facturas TIPO=13 con IMPORTERECEQUIV>0 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTERECEQUIV),2) AS TOTAL_RECEQUIV "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTERECEQUIV>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY TOTAL_RECEQUIV DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Bajo", "Recargo equivalencia", ""),

    q("fx3_128", "Análisis de rentabilidad por mes del año (histórico)",
      "¿Qué mes del año es históricamente más rentable?",
      "Margen bruto medio por mes del año en facturas TIPO=13.",
      "SELECT CAST(SUBSTR(D.FECHA,6,2) AS INTEGER) AS MES_NUM, "
      "ROUND(AVG(MARGEN_MES),2) AS MARGEN_MEDIO "
      "FROM (SELECT SUBSTR(D.FECHA,6,2) AS MES, SUBSTR(D.FECHA,1,4) AS ANIO, "
      "SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD) AS MARGEN_MES "
      "FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,6,2), SUBSTR(D.FECHA,1,4)) "
      "GROUP BY MES_NUM ORDER BY MES_NUM",
      "Finanzas", "Dirección", "KPI", "Medio", "Estacionalidad", ""),

    q("fx3_129", "Facturas con mayor diferencia entre base y total",
      "¿Qué facturas tienen mayor diferencia entre base imponible y total?",
      "Facturas TIPO=13 con mayor IMPORTETOTAL-IMPORTEBASE (IMPORTEIVA+recargos).",
      "SELECT D.CODIGO, D.FECHA, "
      "ROUND(IMPORTEBASE,2) AS BASE, "
      "ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL, "
      "ROUND(IMPORTETOTAL-IMPORTEBASE,2) AS DIFERENCIA "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEBASE>0 "
      "ORDER BY DIFERENCIA DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Bajo", "IMPORTEIVA", ""),

    q("fx3_130", "Análisis de flujo de caja vs facturación",
      "¿Cómo se relaciona el flujo de caja con la facturación?",
      "Compara SUM(CAJA.IMPORTE) vs SUM(DOCCAB.IMPORTETOTAL) por mes.",
      "SELECT V.MES, V.FACTURADO, COALESCE(C.FLUJO_CAJA,0) AS FLUJO_CAJA "
      "FROM (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) V "
      "LEFT JOIN (SELECT SUBSTR(FECHA,1,7) AS MES, ROUND(SUM(IMPORTE),2) AS FLUJO_CAJA "
      "FROM CAJA WHERE FECHA IS NOT NULL GROUP BY SUBSTR(FECHA,1,7)) C "
      "ON V.MES=C.MES "
      "ORDER BY V.MES DESC LIMIT 12",
      "Finanzas", "Dirección", "KPI", "Alto", "Caja", ""),

    q("fx3_131", "Clientes con mayor IMPORTEIVA pagado",
      "¿Qué clientes pagan más IMPORTEIVA?",
      "Suma de IMPORTEIVA en facturas TIPO=13 por cliente.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM(D.IMPORTEIVA),2) AS IVA_TOTAL, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURACION "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEIVA>0 "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY IVA_TOTAL DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Medio", "IMPORTEIVA", ""),

    q("fx3_132", "Facturas con mayor IMPORTEIVA individual",
      "¿Qué facturas tienen mayor importe de IMPORTEIVA?",
      "Top 20 facturas TIPO=13 por IMPORTEIVA.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTEBASE,2) AS BASE, "
      "ROUND(D.IMPORTEIVA,2) AS IVA, "
      "ROUND(D.IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEIVA>0 "
      "ORDER BY D.IMPORTEIVA DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Bajo", "IMPORTEIVA", ""),

    q("fx3_133", "Evolución del IMPORTEIVA repercutido por trimestre",
      "¿Cómo evoluciona el IMPORTEIVA repercutido por trimestre?",
      "Suma de IMPORTEIVA en facturas TIPO=13 por trimestre.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, "
      "CASE WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2' "
      "WHEN CAST(SUBSTR(FECHA,6,2) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3' "
      "ELSE 'Q4' END AS TRIMESTRE, "
      "ROUND(SUM(IMPORTEIVA),2) AS IVA_REPERCUTIDO "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO, TRIMESTRE ORDER BY ANIO DESC, TRIMESTRE",
      "Finanzas", "Dirección", "KPI", "Alto", "IMPORTEIVA", ""),

    q("fx3_134", "Facturas con IMPORTEENTREGADO NULL",
      "¿Hay facturas sin información de cobro?",
      "Facturas TIPO=13 con IMPORTEENTREGADO NULL.",
      "SELECT COUNT(*) AS N_FACTURAS_SIN_COBRO_INFO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEENTREGADO IS NULL",
      "Finanzas", "Dirección", "Operacional", "Alto", "Integridad", ""),

    q("fx3_135", "Análisis de rentabilidad por agente y mes",
      "¿Cuál es la rentabilidad de cada agente por mes?",
      "Margen bruto por CODAGENTE y mes en facturas TIPO=13.",
      "SELECT D.CODAGENTE AS AGENTE, SUBSTR(D.FECHA,1,7) AS MES, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND D.FECHA IS NOT NULL "
      "GROUP BY D.CODAGENTE, SUBSTR(D.FECHA,1,7) "
      "ORDER BY AGENTE, MES DESC LIMIT 60",
      "Finanzas", "Comercial", "Agente", "Alto", "Margen", ""),

    q("fx3_136", "Facturas con mayor antigüedad sin cobrar",
      "¿Cuáles son las facturas más antiguas sin cobrar?",
      "Top 20 facturas TIPO=13 más antiguas con IMPORTEENTREGADO=0.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_SIN_COBRAR "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO=0 AND D.FECHA IS NOT NULL "
      "ORDER BY D.FECHA ASC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Crítico", "Cobros", ""),

    q("fx3_137", "Importe total de facturas emitidas por semana",
      "¿Cuánto se factura por semana?",
      "Suma de IMPORTETOTAL TIPO=13 por semana del año.",
      "SELECT STRFTIME('%Y-W%W', FECHA) AS SEMANA, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SEMANA ORDER BY SEMANA DESC LIMIT 26",
      "Finanzas", "Dirección", "KPI", "Bajo", "Período", ""),

    q("fx3_138", "Análisis de cobros por forma de pago",
      "¿Qué forma de pago tiene mejor ratio de cobro?",
      "Ratio IMPORTEENTREGADO/IMPORTETOTAL por CODFORMAPAGO en facturas TIPO=13.",
      "SELECT COALESCE(FP.NOMBRE, 'Sin forma pago') AS FORMA_PAGO, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS FACTURADO, "
      "ROUND(SUM(D.IMPORTEENTREGADO),2) AS IMPORTEENTREGADO, "
      "ROUND(SUM(D.IMPORTEENTREGADO)*100.0/NULLIF(SUM(D.IMPORTETOTAL),0),1) AS RATIO_COBRO_PCT "
      "FROM DOCCAB D "
      "LEFT JOIN FORMASPAGO FP ON FP.CODIGO=D.CODFORMAPAGO "
      "WHERE D.TIPO=13 "
      "GROUP BY D.CODFORMAPAGO, FP.NOMBRE "
      "ORDER BY RATIO_COBRO_PCT DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Alto", "Cobros", ""),

    q("fx3_139", "Facturas con mayor importe de IMPORTEIVA relativo",
      "¿Qué facturas tienen mayor porcentaje de IMPORTEIVA sobre el total?",
      "Facturas TIPO=13 con mayor IMPORTEIVA/IMPORTETOTAL.",
      "SELECT D.CODIGO, D.FECHA, "
      "ROUND(IMPORTEBASE,2) AS BASE, "
      "ROUND(IMPORTEIVA,2) AS IVA, "
      "ROUND(IMPORTETOTAL,2) AS TOTAL, "
      "ROUND(IMPORTEIVA*100.0/NULLIF(IMPORTETOTAL,0),1) AS PCT_IVA_SOBRE_TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEIVA>0 AND IMPORTETOTAL>0 "
      "ORDER BY PCT_IVA_SOBRE_TOTAL DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Bajo", "IMPORTEIVA", ""),

    q("fx3_140", "Análisis de rentabilidad global anual",
      "¿Cuál es la rentabilidad global de la empresa por año?",
      "Ingresos, COGS, margen bruto y % por año en facturas TIPO=13.",
      "SELECT SUBSTR(D.FECHA,1,4) AS ANIO, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN_BRUTO, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD)*100.0/"
      "NULLIF(SUM(L.PRECIO*L.CANTIDAD),0),1) AS MARGEN_PCT "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 AND D.FECHA IS NOT NULL "
      "GROUP BY SUBSTR(D.FECHA,1,4) ORDER BY ANIO DESC",
      "Finanzas", "Dirección", "KPI", "Crítico", "Rentabilidad", ""),

    q("fx3_141", "Facturas con descuento y su impacto en el margen",
      "¿Cuánto margen se pierde por los descuentos aplicados?",
      "Suma de descuentos aplicados en líneas de facturas TIPO=13.",
      "SELECT COUNT(*) AS N_LINEAS_CON_DESCUENTO, "
      "ROUND(SUM(L.DESCUENTOS*L.PRECIO*L.CANTIDAD/100.0),2) AS DESCUENTO_TOTAL, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS_SIN_DESCUENTO, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD*(1-L.DESCUENTOS/100.0)),2) AS INGRESOS_CON_DESCUENTO "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "WHERE D.TIPO=13 AND L.DESCUENTOS>0",
      "Finanzas", "Dirección", "KPI", "Alto", "Descuentos", ""),

    q("fx3_142", "Evolución de la deuda pendiente por mes de emisión",
      "¿Cuánta deuda queda pendiente de las facturas emitidas cada mes?",
      "Deuda pendiente agrupada por mes de emisión de la factura.",
      "SELECT SUBSTR(FECHA,1,7) AS MES_EMISION, "
      "COUNT(*) AS N_FACTURAS_CON_DEUDA, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) AS DEUDA_PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES_EMISION DESC LIMIT 24",
      "Finanzas", "Dirección", "KPI", "Alto", "Cobros", ""),

    q("fx3_143", "Clientes con mayor número de facturas en el año",
      "¿Qué clientes tienen más facturas en el año actual?",
      "Conteo de facturas TIPO=13 por cliente en el año actual.",
      "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND SUBSTR(D.FECHA,1,4)=SUBSTR(DATE('now'),1,4) "
      "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY N_FACTURAS DESC LIMIT 20",
      "Finanzas", "Dirección", "Cliente", "Medio", "Frecuencia", ""),

    q("fx3_144", "Análisis de IMPORTEIVA por agente comercial",
      "¿Cuánto IMPORTEIVA genera cada agente?",
      "Suma de IMPORTEIVA en facturas TIPO=13 por CODAGENTE.",
      "SELECT D.CODAGENTE AS AGENTE, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(D.IMPORTEBASE),2) AS BASE_TOTAL, "
      "ROUND(SUM(D.IMPORTEIVA),2) AS IVA_TOTAL "
      "FROM DOCCAB D "
      "WHERE D.TIPO=13 AND D.IMPORTEIVA>0 "
      "GROUP BY D.CODAGENTE ORDER BY IVA_TOTAL DESC",
      "Finanzas", "Comercial", "Agente", "Bajo", "IMPORTEIVA", ""),

    q("fx3_145", "Facturas con mayor número de días entre emisión y cobro",
      "¿Qué facturas tardaron más en cobrarse?",
      "Facturas TIPO=13 cobradas (IMPORTEENTREGADO>=IMPORTETOTAL) con más días.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
      "CAST(JULIANDAY('now')-JULIANDAY(D.FECHA) AS INTEGER) AS DIAS_HASTA_COBRO "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTEENTREGADO>=D.IMPORTETOTAL AND D.FECHA IS NOT NULL "
      "ORDER BY DIAS_HASTA_COBRO DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Medio", "Cobros", ""),

    q("fx3_146", "Análisis de rentabilidad por forma de pago",
      "¿Varía el margen según la forma de pago del cliente?",
      "Margen bruto por CODFORMAPAGO en facturas TIPO=13.",
      "SELECT COALESCE(FP.NOMBRE, 'Sin forma pago') AS FORMA_PAGO, "
      "COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(L.PRECIO*L.CANTIDAD),2) AS INGRESOS, "
      "ROUND(SUM(A.PRECIOCOSTE*L.CANTIDAD),2) AS COGS, "
      "ROUND(SUM((L.PRECIO-A.PRECIOCOSTE)*L.CANTIDAD),2) AS MARGEN "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN FORMASPAGO FP ON FP.CODIGO=D.CODFORMAPAGO "
      "WHERE D.TIPO=13 AND A.PRECIOCOSTE>0 "
      "GROUP BY D.CODFORMAPAGO, FP.NOMBRE "
      "ORDER BY MARGEN DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Medio", "Margen", ""),

    q("fx3_147", "Facturas con mayor importe de recargo de equivalencia",
      "¿Qué facturas tienen mayor recargo de equivalencia?",
      "Top 20 facturas TIPO=13 por IMPORTERECEQUIV.",
      "SELECT D.CODIGO, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(D.IMPORTEBASE,2) AS BASE, "
      "ROUND(D.IMPORTERECEQUIV,2) AS RECEQUIV, "
      "ROUND(D.IMPORTETOTAL,2) AS TOTAL "
      "FROM DOCCAB D "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND D.IMPORTERECEQUIV>0 "
      "ORDER BY D.IMPORTERECEQUIV DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Bajo", "Recargo equivalencia", ""),

    q("fx3_148", "Análisis de cobros por mes del año (estacionalidad)",
      "¿En qué mes del año se cobra más?",
      "Suma de IMPORTEENTREGADO en facturas TIPO=13 por mes del año.",
      "SELECT CAST(SUBSTR(FECHA,6,2) AS INTEGER) AS MES_NUM, "
      "ROUND(AVG(COBRADO_MES),2) AS COBRO_MEDIO "
      "FROM (SELECT SUBSTR(FECHA,6,2) AS MES, SUBSTR(FECHA,1,4) AS ANIO, "
      "SUM(IMPORTEENTREGADO) AS COBRADO_MES "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY SUBSTR(FECHA,6,2), SUBSTR(FECHA,1,4)) "
      "GROUP BY MES_NUM ORDER BY MES_NUM",
      "Finanzas", "Dirección", "KPI", "Medio", "Estacionalidad", ""),

    q("fx3_149", "Facturas con mayor diferencia entre PRECIOVENTA de tarifa y PRECIOVENTA real",
      "¿En qué facturas se aplica mayor descuento respecto a tarifa?",
      "Facturas TIPO=13 con mayor diferencia entre PRECIOVENTA y PRECIOVENTA real.",
      "SELECT D.CODIGO AS FACTURA, D.FECHA, "
      "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL) AS CLIENTE, "
      "ROUND(SUM((A.PRECIOVENTA-L.PRECIO)*L.CANTIDAD),2) AS DESCUENTO_TOTAL_TARIFA "
      "FROM DOCLIN L "
      "JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO "
      "LEFT JOIN ARTICULO A ON A.CODIGO=L.CODARTICULO "
      "LEFT JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
      "WHERE D.TIPO=13 AND A.PRECIOVENTA>0 AND L.PRECIO<A.PRECIOVENTA "
      "GROUP BY D.CODIGO, D.FECHA, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
      "ORDER BY DESCUENTO_TOTAL_TARIFA DESC LIMIT 20",
      "Finanzas", "Dirección", "Operacional", "Alto", "Descuentos", ""),

    q("fx3_150", "Dashboard de riesgo financiero",
      "¿Cuál es el perfil de riesgo financiero de la empresa?",
      "KPIs de riesgo: deuda pendiente, morosidad, concentración, inventario inmovilizado.",
      "SELECT "
      "(SELECT ROUND(SUM(IMPORTETOTAL-IMPORTEENTREGADO),2) FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>IMPORTEENTREGADO) AS DEUDA_TOTAL, "
      "(SELECT COUNT(DISTINCT CODCLIENTE) FROM DOCCAB WHERE TIPO=13 AND IMPORTEENTREGADO=0 AND JULIANDAY('now')-JULIANDAY(FECHA)>90) AS CLIENTES_MOROSOS_90D, "
      "(SELECT ROUND(MAX(SUM(IMPORTETOTAL))*100.0/SUM(IMPORTETOTAL),1) FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) AS PCT_MAYOR_CLIENTE, "
      "(SELECT ROUND(SUM(STOCKARTICULO*PRECIOCOSTE),2) FROM ARTICULO WHERE STOCKARTICULO>0 AND PRECIOCOSTE>0 AND CODIGO NOT IN (SELECT DISTINCT L.CODARTICULO FROM DOCLIN L JOIN DOCCAB D ON D.CODIGO=L.CODDOCUMENTO WHERE D.TIPO=13 AND D.FECHA>=DATE('now','-180 days'))) AS STOCK_INMOVILIZADO",
      "Finanzas", "Dirección", "KPI", "Crítico", "Riesgo", ""),

]
