"""finanzas_v2.py — 125 consultas adicionales de Finanzas (v2).

DEVIA: fichero < 500 líneas, módulo independiente, sin lógica de negocio.
"""
from backend.modules.db_simulator.query_library.builder import q

QUERIES_FINANZAS_V2: list = [
    q("fx2_001", "Saldo de caja por día", "Saldo diario de caja",
      "Suma de movimientos de caja agrupados por día para seguimiento de tesorería.",
      "SELECT SUBSTR(FECHA,1,10) AS DIA, SUM(IMPORTE) AS SALDO_DIA, COUNT(*) AS N_MOVIMIENTOS "
      "FROM CAJA WHERE FECHA IS NOT NULL GROUP BY DIA ORDER BY DIA DESC LIMIT 30",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_002", "Facturas de venta pendientes de cobro", "Facturas sin cobrar",
      "Facturas TIPO=13 con IMPORTEENTREGADO=0 que representan deuda pendiente de clientes.",
      "SELECT CODIGO, CODCLIENTE, IMPORTETOTAL, FECHA "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEENTREGADO=0 ORDER BY FECHA LIMIT 30",
      "Finanzas", "Finanzas", "Alerta", "Alto", "", ""),

    q("fx2_003", "Importe total pendiente de cobro", "Total deuda clientes",
      "Suma de IMPORTETOTAL de facturas TIPO=13 con IMPORTEENTREGADO=0.",
      "SELECT COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_PENDIENTE "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTEENTREGADO=0",
      "Finanzas", "Finanzas", "KPI", "Critico", "", ""),

    q("fx2_004", "Saldo acumulado de caja", "Saldo total caja",
      "Suma total de todos los movimientos de caja registrados.",
      "SELECT ROUND(SUM(IMPORTE),2) AS SALDO_TOTAL, COUNT(*) AS N_MOVIMIENTOS FROM CAJA",
      "Finanzas", "Finanzas", "KPI", "Critico", "", ""),

    q("fx2_005", "Movimientos de caja por mes", "Caja mensual",
      "Agrupa movimientos de caja por mes para ver la evolución de tesorería.",
      "SELECT SUBSTR(FECHA,1,7) AS MES, SUM(IMPORTE) AS TOTAL_MES, COUNT(*) AS N "
      "FROM CAJA WHERE FECHA IS NOT NULL GROUP BY MES ORDER BY MES DESC LIMIT 12",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_006", "Facturas cobradas vs pendientes", "Ratio cobro facturas",
      "Compara el número y volumen de facturas cobradas frente a pendientes.",
      "SELECT IMPORTEENTREGADO, COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY IMPORTEENTREGADO",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_007", "Facturas con importe superior a 10.000€", "Facturas de alto valor",
      "Facturas TIPO=13 con importe superior a 10.000€ para seguimiento de grandes operaciones.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL>10000 ORDER BY IMPORTETOTAL DESC LIMIT 20",
      "Finanzas", "Finanzas", "Operacional", "Medio", "", ""),

    q("fx2_008", "Importe medio por factura de venta", "Ticket medio factura",
      "Importe medio de las facturas TIPO=13 emitidas.",
      "SELECT ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO, "
      "ROUND(MIN(IMPORTETOTAL),2) AS MINIMO, ROUND(MAX(IMPORTETOTAL),2) AS MAXIMO "
      "FROM DOCCAB WHERE TIPO=13",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_009", "Facturas emitidas por trimestre", "Facturación trimestral",
      "Agrupa facturas TIPO=13 por trimestre para análisis de estacionalidad.",
      "SELECT SUBSTR(FECHA,1,4)||'-T'||((CAST(SUBSTR(FECHA,6,2) AS INT)-1)/3+1) AS TRIMESTRE, "
      "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY TRIMESTRE ORDER BY TRIMESTRE DESC LIMIT 8",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_010", "Facturas rectificativas emitidas", "Abonos y rectificativas",
      "Documentos TIPO=14 (facturas rectificativas) que reducen la facturación.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=14 ORDER BY FECHA DESC LIMIT 20",
      "Finanzas", "Finanzas", "Alerta", "Medio", "", ""),

    q("fx2_011", "Importe total de abonos emitidos", "Total abonos",
      "Suma de IMPORTETOTAL de documentos TIPO=14 (rectificativas/abonos).",
      "SELECT COUNT(*) AS N_ABONOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_ABONOS "
      "FROM DOCCAB WHERE TIPO=14",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_012", "Ratio abonos sobre facturación total", "Porcentaje abonos",
      "Porcentaje que representan los abonos sobre la facturación bruta.",
      "SELECT ROUND(SUM(CASE WHEN TIPO=14 THEN IMPORTETOTAL ELSE 0 END),2) AS TOTAL_ABONOS, "
      "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS TOTAL_FACTURAS, "
      "ROUND(100.0*SUM(CASE WHEN TIPO=14 THEN IMPORTETOTAL ELSE 0 END)/"
      "NULLIF(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),0),2) AS PCT_ABONOS "
      "FROM DOCCAB WHERE TIPO IN (13,14)",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_013", "Facturas con IMPORTEIVA desglosado", "Verificación IMPORTEIVA facturas",
      "Muestra IMPORTEBASE, IMPORTEIVA e IMPORTETOTAL para verificar coherencia fiscal.",
      "SELECT CODIGO, CODCLIENTE, IMPORTEBASE, "
      "ROUND(IMPORTETOTAL-IMPORTEBASE,2) AS IVA_CALCULADO, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 ORDER BY FECHA DESC LIMIT 20",
      "Finanzas", "Finanzas", "Operacional", "Medio", "", ""),

    q("fx2_014", "Suma de base imponible vs IMPORTEIVA total", "Totales fiscales",
      "Agrega base imponible e IMPORTEIVA de todas las facturas para cuadre fiscal.",
      "SELECT ROUND(SUM(IMPORTEBASE),2) AS TOTAL_BASE, "
      "ROUND(SUM(IMPORTETOTAL-IMPORTEBASE),2) AS TOTAL_IVA, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FINAL "
      "FROM DOCCAB WHERE TIPO=13",
      "Finanzas", "Finanzas", "KPI", "Critico", "", ""),

    q("fx2_015", "Facturas del mes actual", "Facturación mes en curso",
      "Facturas TIPO=13 emitidas en el mes actual.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7) "
      "ORDER BY FECHA DESC LIMIT 30",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_016", "Comparativa facturación mes actual vs mes anterior", "Variación mensual facturación",
      "Compara el total facturado del mes actual con el mes anterior.",
      "SELECT "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,7)=SUBSTR(DATE('now'),1,7) THEN IMPORTETOTAL ELSE 0 END),2) AS MES_ACTUAL, "
      "ROUND(SUM(CASE WHEN SUBSTR(FECHA,1,7)=SUBSTR(DATE('now','-1 month'),1,7) THEN IMPORTETOTAL ELSE 0 END),2) AS MES_ANTERIOR "
      "FROM DOCCAB WHERE TIPO=13",
      "Finanzas", "Finanzas", "KPI", "Critico", "", ""),

    q("fx2_017", "Movimientos de caja negativos (salidas)", "Salidas de caja",
      "Movimientos de caja con IMPORTE<0 que representan pagos o salidas de efectivo.",
      "SELECT SUBSTR(FECHA,1,10) AS DIA, COUNT(*) AS N, ROUND(SUM(IMPORTE),2) AS TOTAL_SALIDAS "
      "FROM CAJA WHERE IMPORTE<0 AND FECHA IS NOT NULL GROUP BY DIA ORDER BY DIA DESC LIMIT 20",
      "Finanzas", "Finanzas", "Operacional", "Medio", "", ""),

    q("fx2_018", "Movimientos de caja positivos (entradas)", "Entradas de caja",
      "Movimientos de caja con IMPORTE>0 que representan cobros o entradas de efectivo.",
      "SELECT SUBSTR(FECHA,1,10) AS DIA, COUNT(*) AS N, ROUND(SUM(IMPORTE),2) AS TOTAL_ENTRADAS "
      "FROM CAJA WHERE IMPORTE>0 AND FECHA IS NOT NULL GROUP BY DIA ORDER BY DIA DESC LIMIT 20",
      "Finanzas", "Finanzas", "Operacional", "Medio", "", ""),

    q("fx2_019", "Facturas con importe cero o negativo", "Facturas anómalas por importe",
      "Facturas TIPO=13 con IMPORTETOTAL<=0 que pueden indicar errores de registro.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND IMPORTETOTAL<=0 ORDER BY FECHA DESC LIMIT 20",
      "Finanzas", "Finanzas", "Alerta", "Alto", "", ""),

    q("fx2_020", "Facturación acumulada por año", "Facturación anual histórica",
      "Suma de facturación TIPO=13 agrupada por año para análisis histórico.",
      "SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N_FACTURAS, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
      "GROUP BY ANIO ORDER BY ANIO DESC",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_021", "Presupuestos convertidos a factura", "Conversión presupuesto-factura",
      "Presupuestos TIPO=0 que tienen una factura TIPO=13 asociada (mismo cliente, importe similar).",
      "SELECT P.CODIGO AS COD_PRESUPUESTO, P.CODCLIENTE, P.IMPORTETOTAL AS IMP_PRESUPUESTO, "
      "F.CODIGO AS COD_FACTURA, F.IMPORTETOTAL AS IMP_FACTURA "
      "FROM DOCCAB P JOIN DOCCAB F ON F.CODCLIENTE=P.CODCLIENTE "
      "AND ABS(F.IMPORTETOTAL-P.IMPORTETOTAL)<1 "
      "WHERE P.TIPO=0 AND F.TIPO=13 LIMIT 20",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_022", "Facturas por agente comercial", "Facturación por agente",
      "Suma de facturación TIPO=13 agrupada por CODAGENTE.",
      "SELECT CODAGENTE, COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=13 GROUP BY CODAGENTE ORDER BY TOTAL DESC",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),

    q("fx2_023", "Facturas sin agente asignado", "Facturas sin agente",
      "Facturas TIPO=13 con CODAGENTE nulo o cero que no tienen agente asignado.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND (CODAGENTE IS NULL OR CODAGENTE=0) "
      "ORDER BY FECHA DESC LIMIT 20",
      "Finanzas", "Finanzas", "Alerta", "Medio", "", ""),

    q("fx2_024", "Importe medio de presupuestos", "Ticket medio presupuesto",
      "Importe medio de los presupuestos TIPO=0 para comparar con el ticket medio de factura.",
      "SELECT COUNT(*) AS N_PRESUPUESTOS, ROUND(AVG(IMPORTETOTAL),2) AS IMPORTE_MEDIO, "
      "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
      "FROM DOCCAB WHERE TIPO=0",
      "Finanzas", "Finanzas", "KPI", "Medio", "", ""),

    q("fx2_025", "Facturas emitidas en los últimos 7 días", "Facturación última semana",
      "Facturas TIPO=13 emitidas en los últimos 7 días para seguimiento inmediato.",
      "SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
      "FROM DOCCAB WHERE TIPO=13 AND FECHA >= DATE('now','-7 days') "
      "ORDER BY FECHA DESC LIMIT 30",
      "Finanzas", "Finanzas", "KPI", "Alto", "", ""),
]
