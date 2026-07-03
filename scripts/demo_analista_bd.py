"""
demo_analista_bd.py — Catálogo de 150 consultas ultra-complejas sobre el simulador.

PRIVACIDAD: Solo se imprimen conteos, fechas, promedios y porcentajes.
Nunca se imprimen nombres, NIFs, IBANs, teléfonos, emails ni direcciones.

EJECUCIÓN:
  cd bots/interjddcia
  python -X utf8 scripts/demo_analista_bd.py [categoria]

Categorías disponibles: gerencia, contabilidad, facturacion, almacen,
  logistica, comercial, compras, proyectos, sat, rrhh,
  marketing, predicciones, alertas, financiero, reporting
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.modules.db_simulator.constants import SimulatorPaths

DB_PATH = str(SimulatorPaths.DB_PATH)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(sql: str, params=()) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

def safe_repr(rows: List[Dict]) -> str:
    """Muestra filas sin valores de columnas sensibles."""
    SENSITIVE = {"NIF","IBAN","IBANPAGADOR","TEL","TELEFONO","EMAIL","NOMBRECOMERCIAL",
                 "RAZONSOCIAL","NOMBRE","DIR","NSS","NIF","TITULAR","BICPAGADOR"}
    if not rows:
        return "  (sin resultados)"
    out = []
    for row in rows[:5]:
        safe = {k: v for k, v in row.items() if k.upper() not in SENSITIVE}
        out.append("  " + str(safe))
    if len(rows) > 5:
        out.append(f"  ... y {len(rows)-5} filas más")
    return "\n".join(out)

def print_query(num: int, titulo: str, sql: str, justificacion: str,
                params=(), show_rows: bool = True):
    print(f"\n  [{num:02d}] {titulo}")
    print(f"  {'─'*72}")
    try:
        rows = run_query(sql, params)
        n = len(rows)
        print(f"  Resultado: {n} filas")
        if show_rows and rows:
            print(safe_repr(rows))
        print(f"\n  Justificación: {justificacion}")
    except Exception as e:
        print(f"  ERROR: {e}")
        print(f"  Justificación: {justificacion}")

def section(nombre: str, emoji: str = "📊"):
    print(f"\n{'═'*76}")
    print(f"  {emoji}  {nombre.upper()}")
    print(f"{'═'*76}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GERENCIA — KPIs estratégicos
# ═══════════════════════════════════════════════════════════════════════════════

def demo_gerencia():
    section("GERENCIA — KPIs estratégicos de dirección", "🏢")

    print_query(1, "Actividad total por tipo de documento",
        """SELECT TIPO,
                  COUNT(*) AS total_docs,
                  COUNT(DISTINCT CODCLIENTE) AS clientes_distintos,
                  ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS importe_medio,
                  MIN(FECHA) AS primera_fecha,
                  MAX(FECHA) AS ultima_fecha
           FROM DOCCAB
           WHERE TIPO IS NOT NULL
           GROUP BY TIPO
           ORDER BY total_docs DESC""",
        "Permite a dirección ver la distribución de actividad por tipo de documento "
        "(facturas=13, albaranes=40, pedidos=20, presupuestos=1). El importe medio "
        "revela el ticket promedio por tipo sin exponer facturas individuales.")

    print_query(2, "Evolución mensual de documentos (últimos 24 meses)",
        """WITH meses AS (
               SELECT strftime('%Y-%m', FECHA) AS mes,
                      TIPO,
                      COUNT(*) AS ndocs,
                      SUM(CAST(IMPORTETOTAL AS REAL)) AS importe_total
               FROM DOCCAB
               WHERE FECHA IS NOT NULL AND FECHA >= date('now','-24 months')
               GROUP BY mes, TIPO
           )
           SELECT mes, TIPO, ndocs, ROUND(importe_total,2) AS importe_total
           FROM meses
           ORDER BY mes DESC, ndocs DESC
           LIMIT 30""",
        "La CTE agrupa por mes y tipo mostrando tendencias. Sin ver facturas "
        "individuales, gerencia detecta estacionalidad y caídas de actividad.")

    print_query(3, "Top agentes por volumen de documentos",
        """SELECT CODAGENTE,
                  COUNT(*) AS total_docs,
                  COUNT(DISTINCT CODCLIENTE) AS clientes_gestionados,
                  ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS ticket_medio,
                  MIN(FECHA) AS desde, MAX(FECHA) AS hasta
           FROM DOCCAB
           WHERE CODAGENTE IS NOT NULL AND CODAGENTE != ''
           GROUP BY CODAGENTE
           ORDER BY total_docs DESC
           LIMIT 10""",
        "Ranking de agentes comerciales por volumen. Gerencia identifica quiénes "
        "generan más actividad sin necesitar nombres (usa CODAGENTE como ID).")

    print_query(4, "Tasa de conversión presupuesto → factura por período",
        """WITH pres AS (
               SELECT strftime('%Y-%m', FECHA) AS mes, COUNT(*) AS n_pres
               FROM DOCCAB WHERE TIPO = 1 AND FECHA IS NOT NULL
               GROUP BY mes
           ),
           fact AS (
               SELECT strftime('%Y-%m', FECHA) AS mes, COUNT(*) AS n_fact
               FROM DOCCAB WHERE TIPO = 13 AND FECHA IS NOT NULL
               GROUP BY mes
           )
           SELECT p.mes,
                  p.n_pres AS presupuestos,
                  COALESCE(f.n_fact, 0) AS facturas,
                  CASE WHEN p.n_pres > 0
                       THEN ROUND(100.0*COALESCE(f.n_fact,0)/p.n_pres,1)
                       ELSE 0 END AS tasa_conversion_pct
           FROM pres p LEFT JOIN fact f ON f.mes = p.mes
           ORDER BY p.mes DESC LIMIT 24""",
        "KPI clave de ventas. Compara presupuestos emitidos vs facturas generadas "
        "para calcular la tasa de cierre mensual. Una caída indica problemas comerciales.")

    print_query(5, "Distribución de clientes por origen geográfico (CP)",
        """SELECT CP,
                  COUNT(*) AS total_clientes,
                  ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS pct_cartera
           FROM CLIENTE
           WHERE CP IS NOT NULL AND CP != ''
           GROUP BY CP
           ORDER BY total_clientes DESC
           LIMIT 15""",
        "Mapeo geográfico de cartera de clientes por código postal. "
        "Permite a gerencia identificar zonas de concentración de negocio "
        "sin exponer nombres o direcciones individuales.")

    print_query(6, "Análisis de proyectos por estado y duración",
        """SELECT TIPOOBRA,
                  COUNT(*) AS total,
                  SUM(CASE WHEN FECHAFIN IS NOT NULL THEN 1 ELSE 0 END) AS finalizados,
                  SUM(CASE WHEN FECHAFIN IS NULL THEN 1 ELSE 0 END) AS en_curso,
                  ROUND(AVG(CASE WHEN FECHAFIN IS NOT NULL AND FECHAINICIO IS NOT NULL
                       THEN CAST(julianday(FECHAFIN)-julianday(FECHAINICIO) AS REAL)
                       ELSE NULL END),1) AS duracion_media_dias
           FROM PROYECTOS
           WHERE TIPOOBRA IS NOT NULL
           GROUP BY TIPOOBRA
           ORDER BY total DESC""",
        "Dashboard de proyectos por tipo de obra. La duración media en días permite "
        "a dirección evaluar la eficiencia de ejecución y detectar proyectos estancados.")

    print_query(7, "Evolución anual del número de clientes nuevos",
        """SELECT strftime('%Y', FECHAALTA) AS anyo,
                  COUNT(*) AS clientes_nuevos,
                  SUM(COUNT(*)) OVER (ORDER BY strftime('%Y', FECHAALTA)) AS acumulado
           FROM CLIENTE
           WHERE FECHAALTA IS NOT NULL AND FECHAALTA != ''
           GROUP BY anyo
           ORDER BY anyo DESC
           LIMIT 10""",
        "Crecimiento de cartera por año con acumulado mediante window function. "
        "Permite ver si el negocio crece, se estanca o pierde clientes.",
        show_rows=True)

    print_query(8, "Ratio documentos con/sin importe registrado",
        """SELECT
               SUM(CASE WHEN IMPORTETOTAL IS NOT NULL
                        AND CAST(IMPORTETOTAL AS REAL) > 0 THEN 1 ELSE 0 END) AS con_importe,
               SUM(CASE WHEN IMPORTETOTAL IS NULL
                        OR CAST(IMPORTETOTAL AS REAL) = 0 THEN 1 ELSE 0 END) AS sin_importe,
               COUNT(*) AS total,
               ROUND(100.0*SUM(CASE WHEN IMPORTETOTAL IS NOT NULL
                   AND CAST(IMPORTETOTAL AS REAL)>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS pct_completos
           FROM DOCCAB""",
        "Calidad de datos: qué % de documentos tienen importe registrado. "
        "Un % bajo indica problemas de captura de datos en el ERP.")

    print_query(9, "Análisis de remesas bancarias por período",
        """SELECT strftime('%Y', FECHAEMISION) AS anyo,
                  COUNT(*) AS remesas,
                  SUM(NUMRECIBOS) AS total_recibos,
                  ROUND(SUM(CAST(SUMRECIBOS AS REAL)),2) AS importe_total_remesas
           FROM REMESA
           WHERE FECHAEMISION IS NOT NULL
           GROUP BY anyo
           ORDER BY anyo DESC""",
        "Las remesas consolidan cobros bancarios. Ver el número e importe total "
        "por año permite a gerencia y tesorería validar la actividad de cobro.")

    print_query(10, "Índice de actividad: documentos por agente por mes",
        """WITH actividad AS (
               SELECT CODAGENTE,
                      strftime('%Y-%m', FECHA) AS mes,
                      COUNT(*) AS docs_mes
               FROM DOCCAB
               WHERE CODAGENTE IS NOT NULL AND FECHA IS NOT NULL
               GROUP BY CODAGENTE, mes
           )
           SELECT CODAGENTE,
                  COUNT(DISTINCT mes) AS meses_activos,
                  ROUND(AVG(docs_mes),1) AS media_docs_mes,
                  MAX(docs_mes) AS maximo_docs_mes,
                  MIN(docs_mes) AS minimo_docs_mes
           FROM actividad
           GROUP BY CODAGENTE
           ORDER BY media_docs_mes DESC
           LIMIT 10""",
        "Productividad de agentes: media de documentos generados por mes activo. "
        "Identifica agentes consistentes vs irregulares sin ver datos personales.")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CONTABILIDAD — Análisis económico
# ═══════════════════════════════════════════════════════════════════════════════

def demo_contabilidad():
    section("CONTABILIDAD — Análisis económico y financiero", "💰")

    print_query(1, "Evolución mensual de baseimponible e IVA facturado",
        """SELECT strftime('%Y-%m', FECHA) AS mes,
                  TIPO,
                  COUNT(*) AS ndocs,
                  ROUND(SUM(CAST(BASEIMPONIBLE AS REAL)),2) AS base_total,
                  ROUND(SUM(CAST(IVA AS REAL)),2) AS iva_total,
                  ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS total_con_iva
           FROM DOCCAB
           WHERE FECHA IS NOT NULL AND TIPO IN (13, 40)
           GROUP BY mes, TIPO
           ORDER BY mes DESC LIMIT 24""",
        "Liquidaciones de IVA mensuales para modelos 303. La base imponible + IVA "
        "deben cuadrar con el total. Imprescindible para contabilidad y Hacienda.")

    print_query(2, "Análisis de recibos vencidos vs cobrados",
        """WITH vencidos AS (
               SELECT strftime('%Y-%m', FECHAVENC) AS mes_venc,
                      COUNT(*) AS total_vencidos,
                      ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS importe_vencido
               FROM RECIBO1
               WHERE FECHAVENC IS NOT NULL AND FECHAVENC <= date('now')
               GROUP BY mes_venc
           ),
           cobrados AS (
               SELECT strftime('%Y-%m', FECHA) AS mes_cobro,
                      COUNT(*) AS total_cobrados,
                      ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS importe_cobrado
               FROM RECIBO3
               WHERE FECHA IS NOT NULL
               GROUP BY mes_cobro
           )
           SELECT v.mes_venc, v.total_vencidos, v.importe_vencido,
                  COALESCE(c.total_cobrados,0) AS cobrados,
                  COALESCE(c.importe_cobrado,0) AS importe_cobrado
           FROM vencidos v LEFT JOIN cobrados c ON c.mes_cobro = v.mes_venc
           ORDER BY v.mes_venc DESC LIMIT 12""",
        "Cartera de cobro: recibos vencidos vs efectivamente cobrados. "
        "La diferencia es el riesgo de crédito pendiente de recuperación.")

    print_query(3, "Distribución de importes de facturas por rangos",
        """SELECT
               SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL) < 100    THEN 1 ELSE 0 END) AS menos_100,
               SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL) BETWEEN 100 AND 999 THEN 1 ELSE 0 END) AS entre_100_999,
               SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL) BETWEEN 1000 AND 4999 THEN 1 ELSE 0 END) AS entre_1k_5k,
               SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL) BETWEEN 5000 AND 19999 THEN 1 ELSE 0 END) AS entre_5k_20k,
               SUM(CASE WHEN CAST(IMPORTETOTAL AS REAL) >= 20000 THEN 1 ELSE 0 END) AS mas_20k,
               ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS importe_medio,
               ROUND(MIN(CAST(IMPORTETOTAL AS REAL)),2) AS minimo,
               ROUND(MAX(CAST(IMPORTETOTAL AS REAL)),2) AS maximo
           FROM DOCCAB
           WHERE TIPO = 13 AND IMPORTETOTAL IS NOT NULL""",
        "Histograma de importes de facturas. Permite a contabilidad identificar "
        "la concentración del riesgo: si muchas facturas son de importes altos, "
        "el riesgo de impago es mayor.")

    print_query(4, "Recibos agrupados por forma de pago",
        """SELECT r.TIPOFORMAPAGO,
                  COUNT(*) AS num_recibos,
                  ROUND(SUM(CAST(r.IMPORTE AS REAL)),2) AS importe_total,
                  ROUND(AVG(CAST(r.IMPORTE AS REAL)),2) AS importe_medio,
                  MIN(r.FECHA) AS primera_fecha,
                  MAX(r.FECHA) AS ultima_fecha
           FROM RECIBO3 r
           WHERE r.TIPOFORMAPAGO IS NOT NULL
           GROUP BY r.TIPOFORMAPAGO
           ORDER BY importe_total DESC""",
        "Distribución de cobros por forma de pago. Contabilidad necesita saber "
        "qué % se cobra por transferencia, domiciliación, efectivo, etc., "
        "para cuadrar con los extractos bancarios por cuenta.")

    print_query(5, "Antigüedad de saldos vencidos (aging report)",
        """SELECT
               SUM(CASE WHEN CAST(julianday('now')-julianday(FECHAVENC) AS INTEGER) <= 30
                   THEN 1 ELSE 0 END) AS vencido_0_30d,
               SUM(CASE WHEN CAST(julianday('now')-julianday(FECHAVENC) AS INTEGER) BETWEEN 31 AND 60
                   THEN 1 ELSE 0 END) AS vencido_31_60d,
               SUM(CASE WHEN CAST(julianday('now')-julianday(FECHAVENC) AS INTEGER) BETWEEN 61 AND 90
                   THEN 1 ELSE 0 END) AS vencido_61_90d,
               SUM(CASE WHEN CAST(julianday('now')-julianday(FECHAVENC) AS INTEGER) > 90
                   THEN 1 ELSE 0 END) AS vencido_mas_90d,
               ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS total_pendiente
           FROM RECIBO1
           WHERE FECHAVENC IS NOT NULL AND FECHAVENC < date('now') AND ACTIVO = 1""",
        "Aging report estándar de deuda: clasifica los impagados por antigüedad. "
        "Los recibos >90 días son candidatos a provisión por insolvencia.")

    print_query(6, "Histórico de variaciones de precio por período",
        """SELECT strftime('%Y-%m', FECHA) AS mes,
                  COUNT(*) AS cambios_precio,
                  COUNT(DISTINCT CODARTICULO) AS articulos_con_cambio,
                  ROUND(AVG(CAST(PRECIONUEVO AS REAL) - CAST(PRECIOANTERIOR AS REAL)),4) AS variacion_media,
                  SUM(CASE WHEN CAST(PRECIONUEVO AS REAL) > CAST(PRECIOANTERIOR AS REAL)
                      THEN 1 ELSE 0 END) AS subidas,
                  SUM(CASE WHEN CAST(PRECIONUEVO AS REAL) < CAST(PRECIOANTERIOR AS REAL)
                      THEN 1 ELSE 0 END) AS bajadas
           FROM HISTORICOPRECIOS
           WHERE FECHA IS NOT NULL AND PRECIOANTERIOR IS NOT NULL AND PRECIONUEVO IS NOT NULL
           GROUP BY mes
           ORDER BY mes DESC LIMIT 12""",
        "Análisis de variación de precios de venta. Permite contabilidad detectar "
        "inflación en costes y ajustes de margen. Subidas > bajadas indica "
        "política de aumento de precios.")

    print_query(7, "Remesas por estado activo/inactivo y período",
        """SELECT strftime('%Y', FECHAEMISION) AS anyo,
                  ENEUROS,
                  COUNT(*) AS total_remesas,
                  SUM(NUMRECIBOS) AS recibos_agrupados,
                  ROUND(SUM(CAST(SUMRECIBOS AS REAL)),2) AS total_remesado
           FROM REMESA
           WHERE FECHAEMISION IS NOT NULL
           GROUP BY anyo, ENEUROS
           ORDER BY anyo DESC""",
        "Las remesas bancarias agrupan cobros. Saber si son en euros (ENEUROS=1) "
        "es clave para la contabilidad en divisas y conciliación bancaria.")

    print_query(8, "Análisis de IVA por tipo en líneas de documento",
        """SELECT TIPOIVA,
                  COUNT(*) AS lineas,
                  COUNT(DISTINCT CODDOCUMENTO) AS documentos,
                  ROUND(AVG(CAST(TRIBUTACIONIVA AS REAL)),2) AS tributacion_media,
                  ROUND(SUM(CAST(CANTIDAD AS REAL) * CAST(PRECIO AS REAL)),2) AS base_total_calculada
           FROM DOCLIN
           WHERE TIPOIVA IS NOT NULL
           GROUP BY TIPOIVA
           ORDER BY lineas DESC""",
        "Desglose de IVA por tipo en líneas de documento. Fundamental para "
        "cuadrar el modelo 303 y verificar que cada tipo de IVA se aplica "
        "correctamente según el tipo de producto o servicio.")

    print_query(9, "Concentración del riesgo: clientes con más recibos activos",
        """SELECT CODPAGADOR,
                  COUNT(*) AS num_recibos,
                  ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS deuda_total,
                  MIN(FECHAVENC) AS vence_antes,
                  MAX(FECHAVENC) AS vence_despues,
                  ROUND(AVG(CAST(IMPORTE AS REAL)),2) AS recibo_medio
           FROM RECIBO1
           WHERE ACTIVO = 1 AND CODPAGADOR IS NOT NULL
           GROUP BY CODPAGADOR
           ORDER BY deuda_total DESC
           LIMIT 10""",
        "Top 10 deudores por importe pendiente usando CODPAGADOR (no nombre). "
        "Contabilidad evalúa la concentración del riesgo crediticio sin exponer "
        "datos personales en el informe.")

    print_query(10, "Balance de recibos emitidos vs cobrados por mes",
        """WITH emitidos AS (
               SELECT strftime('%Y-%m', FECHAEMISION) AS mes,
                      COUNT(*) AS n, ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS total
               FROM RECIBO1 WHERE FECHAEMISION IS NOT NULL GROUP BY mes
           ),
           cobrados AS (
               SELECT strftime('%Y-%m', FECHAEMISION) AS mes,
                      COUNT(*) AS n, ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS total
               FROM RECIBO3 WHERE FECHAEMISION IS NOT NULL GROUP BY mes
           )
           SELECT e.mes,
                  e.n AS emitidos, e.total AS total_emitido,
                  COALESCE(c.n,0) AS cobrados, COALESCE(c.total,0) AS total_cobrado,
                  ROUND(e.total - COALESCE(c.total,0),2) AS pendiente
           FROM emitidos e LEFT JOIN cobrados c ON c.mes = e.mes
           ORDER BY e.mes DESC LIMIT 12""",
        "Balance mensual de cobros: emitidos vs cobrados = pendiente de cobro. "
        "Permite al departamento financiero monitorizar el cash flow esperado.")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ALMACÉN — Stock y movimientos
# ═══════════════════════════════════════════════════════════════════════════════

def demo_almacen():
    section("ALMACÉN — Stock, existencias y movimientos", "🏭")

    print_query(1, "Estado actual del stock por almacén",
        """SELECT CODALMACEN,
                  COUNT(DISTINCT CODARTICULO) AS articulos,
                  SUM(CAST(STOCK1 AS REAL)) AS stock_almacen_1,
                  SUM(CAST(STOCK2 AS REAL)) AS stock_almacen_2,
                  SUM(CASE WHEN CAST(STOCK1 AS REAL) <= 0 THEN 1 ELSE 0 END) AS articulos_sin_stock,
                  SUM(CASE WHEN CAST(STOCK1 AS REAL) > 0 THEN 1 ELSE 0 END) AS articulos_con_stock
           FROM EXISTENC
           WHERE CODALMACEN IS NOT NULL
           GROUP BY CODALMACEN
           ORDER BY stock_almacen_1 DESC""",
        "Cuadro de mando de stock por almacén. Permite al jefe de almacén "
        "ver qué almacenes tienen más/menos existencias y cuántos artículos "
        "están en rotura (stock ≤ 0) sin ver precios ni referencias.")

    print_query(2, "Artículos con stock en múltiples almacenes",
        """SELECT CODARTICULO,
                  COUNT(DISTINCT CODALMACEN) AS num_almacenes,
                  SUM(CAST(STOCK1 AS REAL)) AS stock_total,
                  MIN(CAST(STOCK1 AS REAL)) AS stock_minimo,
                  MAX(CAST(STOCK1 AS REAL)) AS stock_maximo,
                  AVG(CAST(STOCK1 AS REAL)) AS stock_medio
           FROM EXISTENC
           WHERE STOCK1 IS NOT NULL
           GROUP BY CODARTICULO
           HAVING COUNT(DISTINCT CODALMACEN) > 1
           ORDER BY stock_total DESC
           LIMIT 15""",
        "Artículos con presencia en más de un almacén. Permite planificar "
        "trasvases entre almacenes y optimizar el stock distribuido.")

    print_query(3, "Artículos en rotura de stock (STOCK1 ≤ 0)",
        """SELECT COUNT(*) AS total_roturas,
                  COUNT(DISTINCT CODARTICULO) AS articulos_en_rotura,
                  COUNT(DISTINCT CODALMACEN) AS almacenes_afectados,
                  ROUND(AVG(CAST(STOCK1 AS REAL)),2) AS stock_medio_rotura,
                  MIN(CAST(STOCK1 AS REAL)) AS peor_rotura
           FROM EXISTENC
           WHERE CAST(STOCK1 AS REAL) <= 0""",
        "Alerta de rotura: artículos con stock 0 o negativo. "
        "Stock negativo indica reservas comprometidas sin cobertura; "
        "es una alerta crítica para el departamento de compras.")

    print_query(4, "Evolución del valor de inventario por mes (ESTALMACEN)",
        """SELECT strftime('%Y-%m', FECHA) AS mes,
                  COUNT(DISTINCT CODIGO) AS articulos,
                  ROUND(SUM(CAST(IMPCOSTE AS REAL)),2) AS valor_coste,
                  ROUND(SUM(CAST(IMPVENTA AS REAL)),2) AS valor_venta,
                  ROUND(SUM(CAST(IMPVENTA AS REAL)) - SUM(CAST(IMPCOSTE AS REAL)),2) AS margen_bruto
           FROM ESTALMACEN
           WHERE FECHA IS NOT NULL
           GROUP BY mes
           ORDER BY mes DESC
           LIMIT 12""",
        "Evolución mensual del valor del inventario a precio de coste y venta. "
        "La diferencia es el margen bruto potencial del stock. Tendencia "
        "decreciente indica consumo sin reposición.")

    print_query(5, "Pedidos pendientes de servir (PENDSERVIR en EXISTENC)",
        """SELECT CODALMACEN,
                  COUNT(DISTINCT CODARTICULO) AS articulos_con_pendiente,
                  SUM(CAST(PENDSERVIR1 AS REAL)) AS total_pendiente,
                  SUM(CASE WHEN CAST(PENDSERVIR1 AS REAL) > CAST(STOCK1 AS REAL)
                      THEN 1 ELSE 0 END) AS sin_cobertura
           FROM EXISTENC
           WHERE PENDSERVIR1 IS NOT NULL AND CAST(PENDSERVIR1 AS REAL) > 0
           GROUP BY CODALMACEN
           ORDER BY total_pendiente DESC""",
        "Pedidos comprometidos sin stock suficiente. Indica riesgo de retraso "
        "en entregas. SIN_COBERTURA son artículos donde la demanda supera "
        "el stock disponible.")

    print_query(6, "Coste vs precio venta en ESTALMACEN (margen por artículo)",
        """SELECT CODIGO,
                  ROUND(CAST(IMPCOSTE AS REAL),4) AS coste,
                  ROUND(CAST(IMPVENTA AS REAL),4) AS precio_venta,
                  CASE WHEN CAST(IMPVENTA AS REAL) > 0
                       THEN ROUND(100.0*(CAST(IMPVENTA AS REAL)-CAST(IMPCOSTE AS REAL))
                                  /CAST(IMPVENTA AS REAL),2)
                       ELSE NULL END AS margen_pct,
                  FECHA
           FROM ESTALMACEN
           WHERE IMPCOSTE IS NOT NULL AND IMPVENTA IS NOT NULL
             AND CAST(IMPVENTA AS REAL) > 0
           ORDER BY margen_pct DESC
           LIMIT 10""",
        "Top 10 artículos por margen porcentual (sin nombres). Permite "
        "al gerente de almacén identificar los artículos más rentables "
        "para potenciar su rotación.")

    print_query(7, "Antigüedad del inventario (días desde último movimiento)",
        """SELECT strftime('%Y', FECHA) AS anyo_ultimo_mov,
                  COUNT(DISTINCT CODIGO) AS articulos,
                  ROUND(AVG(julianday('now') - julianday(FECHA)),0) AS dias_media_sin_mov,
                  MIN(FECHA) AS movimiento_mas_antiguo
           FROM ESTALMACEN
           WHERE FECHA IS NOT NULL
           GROUP BY anyo_ultimo_mov
           ORDER BY anyo_ultimo_mov""",
        "Clasificación del inventario por antigüedad del último movimiento. "
        "Artículos sin movimiento >365 días son stock obsoleto candidato "
        "a provisión o liquidación.")

    print_query(8, "Ubicaciones de almacén utilizadas",
        """SELECT CODALMACEN,
                  COUNT(DISTINCT UBICACION) AS ubicaciones_distintas,
                  COUNT(CASE WHEN UBICACION IS NULL OR UBICACION='' THEN 1 END) AS sin_ubicacion,
                  COUNT(CASE WHEN UBICACION IS NOT NULL AND UBICACION!='' THEN 1 END) AS con_ubicacion,
                  COUNT(*) AS total_lineas_stock
           FROM EXISTENC
           GROUP BY CODALMACEN
           ORDER BY ubicaciones_distintas DESC""",
        "Estructura del almacén por ubicaciones. Permite saber qué % del stock "
        "tiene ubicación asignada (necesario para picking eficiente) vs stock "
        "sin ubicar (dificulta la localización).")

    print_query(9, "Stock total vs pedido pendiente por artículo (cobertura)",
        """SELECT e.CODARTICULO,
                  ROUND(SUM(CAST(e.STOCK1 AS REAL)),2) AS stock_disponible,
                  ROUND(SUM(CAST(e.PENDSERVIR1 AS REAL)),2) AS pendiente_servir,
                  ROUND(SUM(CAST(e.STOCK1 AS REAL)) - SUM(CAST(e.PENDSERVIR1 AS REAL)),2) AS cobertura_neta
           FROM EXISTENC e
           GROUP BY e.CODARTICULO
           HAVING SUM(CAST(e.PENDSERVIR1 AS REAL)) > 0
           ORDER BY cobertura_neta ASC
           LIMIT 15""",
        "Cobertura neta = stock - pendiente. Los artículos con cobertura "
        "negativa tienen demanda comprometida superior al stock: alerta "
        "de reposición urgente para el departamento de compras.")

    print_query(10, "Análisis de compras por proveedor y artículo (rotación)",
        """SELECT CODPROVEEDOR,
                  COUNT(DISTINCT CODARTICULO) AS articulos_suministrados,
                  COUNT(*) AS lineas_compra,
                  ROUND(AVG(CAST(PRECIOCOSTE AS REAL)),4) AS precio_coste_medio,
                  ROUND(MIN(CAST(PRECIOCOSTE AS REAL)),4) AS precio_minimo,
                  ROUND(MAX(CAST(PRECIOCOSTE AS REAL)),4) AS precio_maximo
           FROM COMPRA
           WHERE CODPROVEEDOR IS NOT NULL AND PRECIOCOSTE IS NOT NULL
           GROUP BY CODPROVEEDOR
           ORDER BY articulos_suministrados DESC
           LIMIT 10""",
        "Análisis de proveedores por diversidad de artículos suministrados "
        "y rango de precios. Permite negociar mejores condiciones con "
        "proveedores que suministran más artículos.")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. COMERCIAL — Ventas y clientes
# ═══════════════════════════════════════════════════════════════════════════════

def demo_comercial():
    section("COMERCIAL — Ventas, clientes y oportunidades", "📈")

    print_query(1, "Ranking de clientes por volumen de documentos",
        """SELECT CODCLIENTE,
                  COUNT(*) AS total_docs,
                  COUNT(CASE WHEN TIPO=13 THEN 1 END) AS facturas,
                  COUNT(CASE WHEN TIPO=1  THEN 1 END) AS presupuestos,
                  COUNT(CASE WHEN TIPO=20 THEN 1 END) AS pedidos,
                  ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS facturado_total,
                  MAX(FECHA) AS ultima_actividad
           FROM DOCCAB
           WHERE CODCLIENTE IS NOT NULL
           GROUP BY CODCLIENTE
           ORDER BY facturado_total DESC
           LIMIT 10""",
        "Top 10 clientes por importe facturado (usando código, no nombre). "
        "Muestra actividad multi-tipo: facturas, presupuestos y pedidos. "
        "La última actividad indica si el cliente sigue activo.")

    print_query(2, "Análisis de estacionalidad de ventas",
        """SELECT strftime('%m', FECHA) AS mes_num,
                  CASE strftime('%m', FECHA)
                      WHEN '01' THEN 'Enero' WHEN '02' THEN 'Febrero'
                      WHEN '03' THEN 'Marzo' WHEN '04' THEN 'Abril'
                      WHEN '05' THEN 'Mayo' WHEN '06' THEN 'Junio'
                      WHEN '07' THEN 'Julio' WHEN '08' THEN 'Agosto'
                      WHEN '09' THEN 'Septiembre' WHEN '10' THEN 'Octubre'
                      WHEN '11' THEN 'Noviembre' WHEN '12' THEN 'Diciembre'
                      ELSE '?' END AS mes_nombre,
                  COUNT(*) AS documentos,
                  ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS importe_medio,
                  ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS total_acumulado
           FROM DOCCAB
           WHERE TIPO=13 AND FECHA IS NOT NULL
           GROUP BY mes_num
           ORDER BY mes_num""",
        "Patrón estacional de facturación por mes. Los meses de mayor "
        "importe indican temporada alta. Permite planificar stock, "
        "personal y acciones comerciales con antelación.")

    print_query(3, "Ciclo de vida del cliente: tiempo entre primer y último doc",
        """SELECT CODCLIENTE,
                  MIN(FECHA) AS primera_compra,
                  MAX(FECHA) AS ultima_compra,
                  COUNT(*) AS total_compras,
                  ROUND(julianday(MAX(FECHA)) - julianday(MIN(FECHA)),0) AS dias_relacion,
                  ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS ltv_acumulado
           FROM DOCCAB
           WHERE CODCLIENTE IS NOT NULL AND TIPO=13 AND FECHA IS NOT NULL
           GROUP BY CODCLIENTE
           HAVING COUNT(*) > 1
           ORDER BY ltv_acumulado DESC
           LIMIT 10""",
        "LTV (Lifetime Value) por cliente: cuánto ha facturado y durante "
        "cuánto tiempo. Clientes con alta LTV y muchos años de relación "
        "son los más valiosos para retener.")

    print_query(4, "Clientes sin actividad reciente (posible fuga)",
        """SELECT COUNT(*) AS clientes_sin_actividad_1_anyo,
                  SUM(CASE WHEN dias_inactivo > 730 THEN 1 ELSE 0 END) AS sin_actividad_2_anyos,
                  ROUND(AVG(dias_inactivo),0) AS media_dias_inactividad
           FROM (
               SELECT CODCLIENTE,
                      CAST(julianday('now') - julianday(MAX(FECHA)) AS INTEGER) AS dias_inactivo
               FROM DOCCAB
               WHERE CODCLIENTE IS NOT NULL AND TIPO=13 AND FECHA IS NOT NULL
               GROUP BY CODCLIENTE
               HAVING julianday('now') - julianday(MAX(FECHA)) > 365
           )""",
        "Alerta de churn (fuga de clientes): cuántos clientes llevan "
        ">1 año sin comprar. Permite al comercial lanzar campañas de "
        "re-activación antes de que la relación se rompa definitivamente.")

    print_query(5, "Ratio de cierre: presupuestos aceptados por serie",
        """WITH pres AS (
               SELECT SERIE, strftime('%Y', FECHA) AS anyo, COUNT(*) AS n_pres
               FROM DOCCAB WHERE TIPO=1 GROUP BY SERIE, anyo
           ),
           ped AS (
               SELECT SERIE, strftime('%Y', FECHA) AS anyo, COUNT(*) AS n_ped
               FROM DOCCAB WHERE TIPO=20 GROUP BY SERIE, anyo
           )
           SELECT p.SERIE, p.anyo, p.n_pres AS presupuestos,
                  COALESCE(ped.n_ped,0) AS pedidos,
                  ROUND(100.0*COALESCE(ped.n_ped,0)/p.n_pres,1) AS tasa_cierre_pct
           FROM pres p LEFT JOIN ped ON ped.SERIE=p.SERIE AND ped.anyo=p.anyo
           ORDER BY p.anyo DESC, p.SERIE""",
        "Tasa de conversión presupuesto→pedido por serie de documento. "
        "Series diferentes pueden corresponder a diferentes comerciales "
        "o delegaciones. Permite comparar su efectividad.")

    print_query(6, "Análisis de ticket medio por tipo de cliente",
        """SELECT c.TIPOPERSONA,
                  c.TIPORESIDENCIA,
                  COUNT(DISTINCT d.CODCLIENTE) AS clientes,
                  COUNT(d.CODIGO) AS facturas,
                  ROUND(AVG(CAST(d.IMPORTETOTAL AS REAL)),2) AS ticket_medio,
                  ROUND(SUM(CAST(d.IMPORTETOTAL AS REAL)),2) AS facturado_total
           FROM DOCCAB d
           JOIN CLIENTE c ON c.CODIGO = d.CODCLIENTE
           WHERE d.TIPO = 13 AND d.IMPORTETOTAL IS NOT NULL
           GROUP BY c.TIPOPERSONA, c.TIPORESIDENCIA
           ORDER BY facturado_total DESC""",
        "Ticket medio segmentado por tipo de persona (física/jurídica) "
        "y residencia (nacional/extranjero). Permite ajustar la estrategia "
        "de precios según el segmento de cliente.")

    print_query(7, "Frecuencia de compra: distribución de clientes por recurrencia",
        """SELECT num_compras_tramo,
                  COUNT(*) AS clientes,
                  ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),1) AS pct
           FROM (
               SELECT CODCLIENTE,
                      CASE
                          WHEN COUNT(*) = 1 THEN '1 compra'
                          WHEN COUNT(*) BETWEEN 2 AND 5 THEN '2-5 compras'
                          WHEN COUNT(*) BETWEEN 6 AND 20 THEN '6-20 compras'
                          ELSE 'más de 20'
                      END AS num_compras_tramo
               FROM DOCCAB
               WHERE TIPO=13 AND CODCLIENTE IS NOT NULL
               GROUP BY CODCLIENTE
           )
           GROUP BY num_compras_tramo
           ORDER BY clientes DESC""",
        "Segmentación por frecuencia de compra. El 80% de los ingresos "
        "suele venir del 20% de clientes más recurrentes (Pareto). "
        "Clientes de '1 compra' son candidatos a campañas de fidelización.")

    print_query(8, "Análisis de albaranes sin facturar (pendiente de facturar)",
        """WITH albaranes AS (
               SELECT CODIGO AS cod_alb, CODCLIENTE, FECHA, IMPORTETOTAL
               FROM DOCCAB WHERE TIPO=40
           ),
           facturados AS (
               SELECT DISTINCT CODDOCUMENTO FROM DOCREF
           )
           SELECT COUNT(*) AS albaranes_sin_factura,
                  COUNT(DISTINCT a.CODCLIENTE) AS clientes_afectados,
                  ROUND(SUM(CAST(a.IMPORTETOTAL AS REAL)),2) AS importe_pendiente,
                  MIN(a.FECHA) AS alb_mas_antiguo
           FROM albaranes a
           LEFT JOIN facturados f ON f.CODDOCUMENTO = a.cod_alb
           WHERE f.CODDOCUMENTO IS NULL""",
        "Albaranes entregados sin facturar = ingresos no registrados contablemente. "
        "Este importe pendiente debe facturarse urgentemente para el cierre del período.")

    print_query(9, "Evolución de la cartera activa de clientes por año",
        """SELECT strftime('%Y', FECHA) AS anyo,
                  COUNT(DISTINCT CODCLIENTE) AS clientes_activos,
                  COUNT(*) AS facturas_emitidas,
                  ROUND(SUM(CAST(IMPORTETOTAL AS REAL))/COUNT(DISTINCT CODCLIENTE),2) AS facturado_por_cliente
           FROM DOCCAB
           WHERE TIPO=13 AND CODCLIENTE IS NOT NULL AND FECHA IS NOT NULL
           GROUP BY anyo
           ORDER BY anyo DESC
           LIMIT 10""",
        "Tamaño de la cartera activa anual y productividad por cliente. "
        "Cartera activa decreciente con importe por cliente creciente "
        "indica concentración del negocio en menos pero mejores clientes.")

    print_query(10, "Comparativa agentes: conversión y ticket medio",
        """WITH agente_stats AS (
               SELECT CODAGENTE,
                      COUNT(CASE WHEN TIPO=1 THEN 1 END) AS presupuestos,
                      COUNT(CASE WHEN TIPO=13 THEN 1 END) AS facturas,
                      ROUND(AVG(CASE WHEN TIPO=13 THEN CAST(IMPORTETOTAL AS REAL) END),2) AS ticket_medio_factura,
                      ROUND(SUM(CASE WHEN TIPO=13 THEN CAST(IMPORTETOTAL AS REAL) ELSE 0 END),2) AS total_facturado
               FROM DOCCAB WHERE CODAGENTE IS NOT NULL
               GROUP BY CODAGENTE
           )
           SELECT CODAGENTE, presupuestos, facturas,
                  CASE WHEN presupuestos>0 THEN ROUND(100.0*facturas/presupuestos,1) ELSE 0 END AS tasa_conversion,
                  ticket_medio_factura, total_facturado
           FROM agente_stats
           ORDER BY total_facturado DESC""",
        "Cuadro de mandos de agentes: presupuestos emitidos, facturas cerradas, "
        "tasa de conversión y ticket medio. Permite al director comercial "
        "identificar agentes de alto rendimiento vs bajo rendimiento.")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PREDICCIONES — Machine learning sin AI (tendencias estadísticas)
# ═══════════════════════════════════════════════════════════════════════════════

def demo_predicciones():
    section("PREDICCIONES — Tendencias y proyecciones estadísticas", "🔮")

    print_query(1, "Tendencia lineal de facturación (regresión simple en SQL)",
        """WITH mensual AS (
               SELECT strftime('%Y-%m', FECHA) AS mes,
                      ROW_NUMBER() OVER (ORDER BY strftime('%Y-%m', FECHA)) AS t,
                      COUNT(*) AS ndocs,
                      ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS total
               FROM DOCCAB
               WHERE TIPO=13 AND FECHA IS NOT NULL
               GROUP BY mes
           ),
           stats AS (
               SELECT COUNT(*) AS n,
                      SUM(t) AS sum_t, SUM(total) AS sum_y,
                      SUM(t*t) AS sum_t2, SUM(t*total) AS sum_ty
               FROM mensual
           )
           SELECT ROUND((sum_ty - sum_t*sum_y/n) / (sum_t2 - sum_t*sum_t/n),2) AS pendiente_mensual,
                  ROUND(sum_y/n,2) AS media_mensual,
                  CASE WHEN (sum_ty - sum_t*sum_y/n) > 0 THEN 'CRECIENTE' ELSE 'DECRECIENTE' END AS tendencia
           FROM stats""",
        "Regresión lineal en SQL puro: la pendiente mensual indica si la "
        "facturación crece o decrece. Una pendiente positiva = negocio en "
        "expansión. Se puede extrapolar para proyectar facturación futura.")

    print_query(2, "Predicción de clientes en riesgo de fuga (modelo RFM simplificado)",
        """WITH rfm AS (
               SELECT CODCLIENTE,
                      CAST(julianday('now') - julianday(MAX(FECHA)) AS INTEGER) AS recencia,
                      COUNT(*) AS frecuencia,
                      ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS valor_monetario
               FROM DOCCAB
               WHERE TIPO=13 AND CODCLIENTE IS NOT NULL AND FECHA IS NOT NULL
               GROUP BY CODCLIENTE
           )
           SELECT
               COUNT(CASE WHEN recencia <= 90 AND frecuencia >= 5 THEN 1 END) AS campeones,
               COUNT(CASE WHEN recencia <= 180 AND frecuencia >= 3 THEN 1 END) AS leales,
               COUNT(CASE WHEN recencia BETWEEN 180 AND 365 THEN 1 END) AS en_riesgo,
               COUNT(CASE WHEN recencia > 365 THEN 1 END) AS perdidos,
               COUNT(*) AS total_clientes
           FROM rfm""",
        "Modelo RFM (Recencia, Frecuencia, Valor) sin IA: clasifica clientes "
        "por comportamiento de compra. 'En riesgo' son clientes que compraban "
        "regularmente pero llevan 6-12 meses sin comprar: targets prioritarios.")

    print_query(3, "Proyección de stock: artículos que se agotarán en 30 días",
        """WITH consumo AS (
               SELECT l.CODARTICULO,
                      SUM(CAST(l.CANTIDAD AS REAL)) AS unidades_vendidas,
                      COUNT(DISTINCT d.FECHA) AS dias_con_venta,
                      ROUND(SUM(CAST(l.CANTIDAD AS REAL)) /
                            NULLIF(julianday(MAX(d.FECHA))-julianday(MIN(d.FECHA)),0) * 30, 2) AS consumo_30d
               FROM DOCLIN l
               JOIN DOCCAB d ON d.CODIGO = l.CODDOCUMENTO
               WHERE d.TIPO=13 AND d.FECHA >= date('now','-90 days')
               GROUP BY l.CODARTICULO
           ),
           stock AS (
               SELECT CODARTICULO, SUM(CAST(STOCK1 AS REAL)) AS stock_total
               FROM EXISTENC GROUP BY CODARTICULO
           )
           SELECT c.CODARTICULO,
                  s.stock_total,
                  c.consumo_30d AS consumo_mensual_estimado,
                  ROUND(s.stock_total / NULLIF(c.consumo_30d,0), 1) AS meses_cobertura
           FROM consumo c JOIN stock s ON s.CODARTICULO = c.CODARTICULO
           WHERE s.stock_total > 0 AND c.consumo_30d > 0
             AND s.stock_total / c.consumo_30d < 1.5
           ORDER BY meses_cobertura ASC
           LIMIT 15""",
        "Artículos con menos de 1.5 meses de cobertura al ritmo actual de ventas. "
        "Prioridad de compra para evitar rotura. El consumo se calcula sobre "
        "los últimos 90 días de ventas reales.")

    print_query(4, "Estacionalidad: factor de variación mensual respecto a la media",
        """WITH mensual AS (
               SELECT strftime('%m', FECHA) AS mes,
                      SUM(CAST(IMPORTETOTAL AS REAL)) AS total_mes
               FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL
               GROUP BY mes
           ),
           media_global AS (
               SELECT AVG(total_mes) AS media FROM mensual
           )
           SELECT mes,
                  ROUND(total_mes,2) AS total,
                  ROUND(total_mes / (SELECT media FROM media_global),3) AS factor_estacional
           FROM mensual
           ORDER BY mes""",
        "Índice estacional: factor > 1 indica mes por encima de la media "
        "histórica. Permite dimensionar compras, personal y producción "
        "aplicando el factor al presupuesto anual planificado.")

    print_query(5, "Predicción de proyectos que superarán el presupuesto",
        """SELECT p.CODIGO AS cod_proyecto,
                  p.TIPOOBRA,
                  p.FECHAINICIO,
                  p.FECHAFIN,
                  COUNT(pp.CODPRESUPUESTO) AS num_presupuestos,
                  CASE
                      WHEN COUNT(pp.CODPRESUPUESTO) > 3 THEN 'RIESGO ALTO de sobrecosto'
                      WHEN COUNT(pp.CODPRESUPUESTO) > 1 THEN 'RIESGO MEDIO'
                      ELSE 'BAJO RIESGO'
                  END AS prediccion_riesgo
           FROM PROYECTOS p
           LEFT JOIN PRESUPROYE pp ON pp.CODPROYECTO = p.CODIGO
           GROUP BY p.CODIGO, p.TIPOOBRA, p.FECHAINICIO, p.FECHAFIN
           ORDER BY num_presupuestos DESC
           LIMIT 15""",
        "Proyectos con múltiples presupuestos asociados suelen indicar "
        "revisiones por variaciones. Más de 3 presupuestos = alta probabilidad "
        "de desviación del coste inicial.")

    print_query(6, "Tendencia de precios de compra por proveedor",
        """SELECT CODPROVEEDOR,
                  COUNT(*) AS revisiones_precio,
                  ROUND(MIN(CAST(PRECIOCOSTE AS REAL)),4) AS precio_minimo,
                  ROUND(MAX(CAST(PRECIOCOSTE AS REAL)),4) AS precio_maximo,
                  ROUND(AVG(CAST(PRECIOCOSTE AS REAL)),4) AS precio_medio,
                  ROUND(100.0*(MAX(CAST(PRECIOCOSTE AS REAL))-MIN(CAST(PRECIOCOSTE AS REAL)))
                        /NULLIF(MIN(CAST(PRECIOCOSTE AS REAL)),0),2) AS variacion_pct
           FROM COMPRA
           WHERE CODPROVEEDOR IS NOT NULL AND PRECIOCOSTE IS NOT NULL
           GROUP BY CODPROVEEDOR
           HAVING COUNT(*) > 3
           ORDER BY variacion_pct DESC
           LIMIT 10""",
        "Proveedores con mayor variación de precios son los de mayor riesgo "
        "para el margen. Una variación >20% indica necesidad de renegociar "
        "contratos o diversificar proveedores.")

    print_query(7, "Predicción de reparaciones SAT por período histórico",
        """SELECT strftime('%Y-%m', FECHA) AS mes,
                  COUNT(*) AS reparaciones,
                  AVG(COUNT(*)) OVER (ORDER BY strftime('%Y-%m', FECHA)
                      ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS media_movil_3m
           FROM REPCAB
           WHERE FECHA IS NOT NULL
           GROUP BY mes
           ORDER BY mes DESC
           LIMIT 18""",
        "Media móvil de 3 meses sobre reparaciones SAT. Suaviza la variabilidad "
        "mensual y revela la tendencia real. Un aumento sostenido indica "
        "mayor volumen de servicio técnico a gestionar.")

    print_query(8, "Análisis de variación de precios en histórico (inflación)",
        """SELECT strftime('%Y', FECHA) AS anyo,
                  COUNT(*) AS cambios,
                  SUM(CASE WHEN CAST(PRECIONUEVO AS REAL) > CAST(PRECIOANTERIOR AS REAL) THEN 1 ELSE 0 END) AS subidas,
                  SUM(CASE WHEN CAST(PRECIONUEVO AS REAL) < CAST(PRECIOANTERIOR AS REAL) THEN 1 ELSE 0 END) AS bajadas,
                  ROUND(AVG(100.0*(CAST(PRECIONUEVO AS REAL)-CAST(PRECIOANTERIOR AS REAL))
                            /NULLIF(CAST(PRECIOANTERIOR AS REAL),0)),2) AS pct_variacion_media
           FROM HISTORICOPRECIOS
           WHERE PRECIOANTERIOR IS NOT NULL AND PRECIONUEVO IS NOT NULL
             AND CAST(PRECIOANTERIOR AS REAL) > 0
           GROUP BY anyo
           ORDER BY anyo DESC
           LIMIT 5""",
        "Tasa de variación media de precios por año. Un valor positivo alto "
        "indica presión inflacionaria en la lista de precios. Permite ajustar "
        "la política de precios de venta para mantener el margen.")

    print_query(9, "Proyección de cobros futuros (recibos con vencimiento futuro)",
        """SELECT strftime('%Y-%m', FECHAVENC) AS mes_cobro,
                  COUNT(*) AS num_recibos,
                  ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS importe_previsto,
                  ROUND(SUM(CAST(GASTOS AS REAL)),2) AS gastos_bancarios
           FROM RECIBO1
           WHERE FECHAVENC > date('now') AND ACTIVO = 1
           GROUP BY mes_cobro
           ORDER BY mes_cobro
           LIMIT 12""",
        "Flujo de caja futuro basado en recibos activos con vencimiento pendiente. "
        "Permite a tesorería planificar disponibilidad de fondos y necesidades "
        "de financiación para los próximos 12 meses.")

    print_query(10, "Alerta temprana: documentos sin completar (ESTADO anómalo)",
        """SELECT ESTADO,
                  COUNT(*) AS total,
                  ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS pct,
                  MIN(FECHA) AS mas_antiguo,
                  MAX(FECHA) AS mas_reciente
           FROM DOCCAB
           WHERE ESTADO IS NOT NULL
           GROUP BY ESTADO
           ORDER BY total DESC""",
        "Distribución de estados de documentos. Estados distintos del normal "
        "indican facturas pendientes de cobro, bloqueadas o anuladas. "
        "Monitorizar la evolución de estados anómalos es una alerta preventiva.")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ALERTAS — Detección automática de anomalías
# ═══════════════════════════════════════════════════════════════════════════════

def demo_alertas():
    section("ALERTAS — Detección automática de anomalías y riesgos", "🚨")

    print_query(1, "Alerta: facturas duplicadas (mismo cliente, importe y fecha)",
        """SELECT CODCLIENTE, FECHA, IMPORTETOTAL, COUNT(*) AS duplicados
           FROM DOCCAB
           WHERE TIPO=13 AND CODCLIENTE IS NOT NULL
             AND IMPORTETOTAL IS NOT NULL
           GROUP BY CODCLIENTE, FECHA, IMPORTETOTAL
           HAVING COUNT(*) > 1
           ORDER BY duplicados DESC
           LIMIT 10""",
        "Facturas con idéntico cliente, fecha e importe son sospechosas de "
        "duplicación. Pueden ser errores de importación o facturación doble "
        "que generarían problemas contables y con el cliente.")

    print_query(2, "Alerta: recibos con importe 0 o negativo",
        """SELECT COUNT(*) AS recibos_anomalos,
                  SUM(CASE WHEN CAST(IMPORTE AS REAL) = 0 THEN 1 ELSE 0 END) AS importe_cero,
                  SUM(CASE WHEN CAST(IMPORTE AS REAL) < 0 THEN 1 ELSE 0 END) AS importe_negativo,
                  MIN(FECHAEMISION) AS desde, MAX(FECHAEMISION) AS hasta
           FROM RECIBO1
           WHERE IMPORTE IS NOT NULL AND CAST(IMPORTE AS REAL) <= 0""",
        "Recibos con importe 0 o negativo son registros erróneos o abonos "
        "sin documentación adecuada. Requieren revisión urgente por contabilidad.")

    print_query(3, "Alerta: documentos con IMPORTETOTAL incongruente (negativo)",
        """SELECT TIPO,
                  COUNT(*) AS docs_con_importe_negativo,
                  ROUND(MIN(CAST(IMPORTETOTAL AS REAL)),2) AS importe_mas_negativo,
                  ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS media_importe_negativo
           FROM DOCCAB
           WHERE IMPORTETOTAL IS NOT NULL AND CAST(IMPORTETOTAL AS REAL) < 0
           GROUP BY TIPO
           ORDER BY docs_con_importe_negativo DESC""",
        "Documentos con importe negativo pueden ser abonos (normal) o errores "
        "de entrada (anormal). Si el TIPO no es un abono, es una alerta crítica "
        "que debe revisarse con el departamento financiero.")

    print_query(4, "Alerta: artículos con stock negativo por almacén",
        """SELECT CODALMACEN,
                  COUNT(CASE WHEN CAST(STOCK1 AS REAL) < 0 THEN 1 END) AS articulos_stock_neg,
                  ROUND(SUM(CASE WHEN CAST(STOCK1 AS REAL) < 0 THEN CAST(STOCK1 AS REAL) ELSE 0 END),2) AS total_deficit,
                  MIN(CAST(STOCK1 AS REAL)) AS peor_deficit
           FROM EXISTENC
           GROUP BY CODALMACEN
           HAVING articulos_stock_neg > 0
           ORDER BY articulos_stock_neg DESC""",
        "Stock negativo = pedidos servidos sin stock disponible. Indica "
        "posibles errores de inventario, mercancía no registrada en entrada "
        "o servicio de pedidos sin verificación de stock.")

    print_query(5, "Alerta: clientes con más de X recibos impagados vencidos",
        """SELECT CODPAGADOR,
                  COUNT(*) AS recibos_vencidos,
                  ROUND(SUM(CAST(IMPORTE AS REAL)),2) AS deuda_total,
                  MIN(FECHAVENC) AS primer_vencimiento,
                  CAST(julianday('now')-julianday(MIN(FECHAVENC)) AS INTEGER) AS dias_impago_maximo
           FROM RECIBO1
           WHERE ACTIVO=1 AND FECHAVENC < date('now') AND CODPAGADOR IS NOT NULL
           GROUP BY CODPAGADOR
           HAVING COUNT(*) >= 3
           ORDER BY deuda_total DESC
           LIMIT 10""",
        "Clientes con 3 o más recibos vencidos impagados son morosos reincidentes. "
        "Alerta de crédito: revisar si deben bloquearse nuevos pedidos hasta "
        "regularizar la deuda.")

    print_query(6, "Alerta: proyectos sin presupuesto asignado",
        """SELECT COUNT(*) AS proyectos_sin_presupuesto,
                  (SELECT COUNT(*) FROM PROYECTOS) AS total_proyectos,
                  ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM PROYECTOS),1) AS pct_sin_presupuesto
           FROM PROYECTOS p
           LEFT JOIN PRESUPROYE pp ON pp.CODPROYECTO = p.CODIGO
           WHERE pp.CODPROYECTO IS NULL""",
        "Proyectos sin presupuesto vinculado no pueden controlarse económicamente. "
        "Si >20% de proyectos no tienen presupuesto, hay un problema de proceso "
        "en la aprobación de proyectos.")

    print_query(7, "Alerta: precios de venta inferiores al precio de coste",
        """SELECT COUNT(*) AS lineas_venta_bajo_coste,
                  ROUND(AVG(CAST(l.PRECIO AS REAL) - CAST(l.COSTE AS REAL)),4) AS margen_medio,
                  MIN(CAST(l.PRECIO AS REAL) - CAST(l.COSTE AS REAL)) AS peor_margen
           FROM DOCLIN l
           JOIN DOCCAB d ON d.CODIGO = l.CODDOCUMENTO
           WHERE d.TIPO=13
             AND l.PRECIO IS NOT NULL AND l.COSTE IS NOT NULL
             AND CAST(l.COSTE AS REAL) > 0
             AND CAST(l.PRECIO AS REAL) < CAST(l.COSTE AS REAL)""",
        "Líneas de factura vendidas por debajo del coste = pérdida directa. "
        "Puede ser por descuentos excesivos, errores de tarifa o "
        "productos obsoletos liquidados. Requiere revisión de política de precios.")

    print_query(8, "Alerta: documentos con BASEIMPONIBLE e IVA incongruentes",
        """SELECT COUNT(*) AS docs_incoherentes,
                  ROUND(AVG(ABS(CAST(BASEIMPONIBLE AS REAL) + CAST(IVA AS REAL)
                               - CAST(IMPORTETOTAL AS REAL))),4) AS desvio_medio_euros
           FROM DOCCAB
           WHERE BASEIMPONIBLE IS NOT NULL AND IVA IS NOT NULL AND IMPORTETOTAL IS NOT NULL
             AND CAST(IMPORTETOTAL AS REAL) > 0
             AND ABS(CAST(BASEIMPONIBLE AS REAL) + CAST(IVA AS REAL)
                     - CAST(IMPORTETOTAL AS REAL)) > 0.02""",
        "Documentos donde BASE + IVA ≠ TOTAL indican errores de cuadre contable. "
        "Una desviación de más de 2 céntimos no puede explicarse por redondeo "
        "y debe investigarse.")

    print_query(9, "Alerta: series de documentos sin actividad reciente",
        """SELECT SERIE, TIPO, ULTIMO,
                  CAST(julianday('now') - julianday(
                       (SELECT MAX(FECHA) FROM DOCCAB d WHERE d.SERIE=s.SERIE AND d.TIPO=s.TIPO)
                  ) AS INTEGER) AS dias_sin_actividad
           FROM SERIE s
           WHERE ULTIMO > 0
             AND (julianday('now') - julianday(
                  (SELECT MAX(FECHA) FROM DOCCAB d WHERE d.SERIE=s.SERIE AND d.TIPO=s.TIPO)
                  ) > 180
                  OR (SELECT MAX(FECHA) FROM DOCCAB d WHERE d.SERIE=s.SERIE AND d.TIPO=s.TIPO) IS NULL)
           ORDER BY dias_sin_actividad DESC""",
        "Series de documentos sin uso en 6+ meses pueden indicar "
        "delegaciones o ejercicios cerrados que siguen activos en el sistema. "
        "Deben revisarse para limpiar la configuración del ERP.")

    print_query(10, "Alerta: recursos (empleados) sin actividad en reparaciones",
        """SELECT COUNT(*) AS tecnicos_sin_reparacion_90d
           FROM RECURSO r
           LEFT JOIN REPCAB rep ON rep.CODALMACEN = r.CODIGO
               AND rep.FECHA >= date('now','-90 days')
           WHERE r.CODIGO IS NOT NULL
             AND rep.CODALMACEN IS NULL""",
        "Técnicos sin ninguna reparación asignada en los últimos 90 días "
        "pueden estar en baja, sin actividad, o el SAT está subasignando. "
        "Permite al responsable del SAT detectar desequilibrios de carga.")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. REPORTING EJECUTIVO — Dashboards multi-dimensionales
# ═══════════════════════════════════════════════════════════════════════════════

def demo_reporting():
    section("REPORTING EJECUTIVO — Dashboards y KPIs multi-dimensionales", "📋")

    print_query(1, "Cuadro de mando anual: todas las métricas clave",
        """SELECT
               (SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13) AS total_facturas,
               (SELECT COUNT(*) FROM DOCCAB WHERE TIPO=1)  AS total_presupuestos,
               (SELECT COUNT(*) FROM DOCCAB WHERE TIPO=20) AS total_pedidos,
               (SELECT COUNT(*) FROM DOCCAB WHERE TIPO=40) AS total_albaranes,
               (SELECT COUNT(DISTINCT CODCLIENTE) FROM DOCCAB WHERE TIPO=13) AS clientes_facturados,
               (SELECT COUNT(*) FROM CLIENTE) AS total_clientes,
               (SELECT COUNT(*) FROM PROVEED) AS total_proveedores,
               (SELECT COUNT(*) FROM PROYECTOS) AS total_proyectos,
               (SELECT COUNT(*) FROM REPCAB) AS total_reparaciones,
               (SELECT COUNT(*) FROM RECIBO1 WHERE ACTIVO=1) AS recibos_pendientes""",
        "Panel ejecutivo completo: una sola query con todos los KPIs en "
        "una fila. Permite crear dashboards de un vistazo para la dirección "
        "sin necesidad de múltiples informes.")

    print_query(2, "Matriz de actividad: documentos × año × tipo",
        """SELECT strftime('%Y', FECHA) AS anyo,
                  SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END) AS facturas,
                  SUM(CASE WHEN TIPO=1  THEN 1 ELSE 0 END) AS presupuestos,
                  SUM(CASE WHEN TIPO=20 THEN 1 ELSE 0 END) AS pedidos,
                  SUM(CASE WHEN TIPO=40 THEN 1 ELSE 0 END) AS albaranes,
                  COUNT(*) AS total_documentos
           FROM DOCCAB
           WHERE FECHA IS NOT NULL
           GROUP BY anyo
           ORDER BY anyo DESC
           LIMIT 10""",
        "Matriz pivotada de actividad por año. Permite identificar en qué "
        "años el negocio fue más activo y si la tendencia es creciente. "
        "Base para el informe anual comparativo.")

    print_query(3, "Análisis de rentabilidad bruta en líneas de venta",
        """SELECT COUNT(*) AS total_lineas,
                  ROUND(SUM(CAST(CANTIDAD AS REAL) * CAST(PRECIO AS REAL)),2) AS ingreso_bruto,
                  ROUND(SUM(CAST(CANTIDAD AS REAL) * CAST(COSTE AS REAL)),2) AS coste_bruto,
                  ROUND(SUM(CAST(CANTIDAD AS REAL) * (CAST(PRECIO AS REAL)-CAST(COSTE AS REAL))),2) AS margen_bruto,
                  ROUND(100.0*SUM(CAST(CANTIDAD AS REAL)*(CAST(PRECIO AS REAL)-CAST(COSTE AS REAL)))
                        /NULLIF(SUM(CAST(CANTIDAD AS REAL)*CAST(PRECIO AS REAL)),0),2) AS margen_pct
           FROM DOCLIN l
           JOIN DOCCAB d ON d.CODIGO = l.CODDOCUMENTO
           WHERE d.TIPO=13 AND l.PRECIO IS NOT NULL AND l.COSTE IS NOT NULL
             AND l.CANTIDAD IS NOT NULL""",
        "P&L básico de ventas: ingresos - costes = margen bruto. "
        "El porcentaje de margen es el KPI fundamental de rentabilidad comercial. "
        "Permite comparar el margen real vs el objetivo presupuestado.")

    print_query(4, "Ranking de artículos más vendidos (por cantidad y por importe)",
        """SELECT l.CODARTICULO,
                  ROUND(SUM(CAST(l.CANTIDAD AS REAL)),2) AS unidades_vendidas,
                  ROUND(SUM(CAST(l.CANTIDAD AS REAL)*CAST(l.PRECIO AS REAL)),2) AS importe_vendido,
                  COUNT(DISTINCT d.CODCLIENTE) AS clientes_distintos,
                  COUNT(DISTINCT l.CODDOCUMENTO) AS num_facturas
           FROM DOCLIN l
           JOIN DOCCAB d ON d.CODIGO = l.CODDOCUMENTO
           WHERE d.TIPO=13 AND l.CODARTICULO IS NOT NULL AND l.CANTIDAD IS NOT NULL
           GROUP BY l.CODARTICULO
           ORDER BY importe_vendido DESC
           LIMIT 10""",
        "Top 10 artículos por importe vendido (análisis ABC). Los 10 primeros "
        "artículos suelen representar el 70-80% de la facturación. "
        "Permite priorizar el stock y las negociaciones con proveedores.")

    print_query(5, "Dashboard de proyectos: estado, duración y cobertura presupuestaria",
        """SELECT p.TIPOOBRA,
                  COUNT(*) AS total,
                  SUM(CASE WHEN p.FECHAFIN IS NULL THEN 1 ELSE 0 END) AS en_curso,
                  SUM(CASE WHEN p.FECHAFIN IS NOT NULL THEN 1 ELSE 0 END) AS terminados,
                  COUNT(DISTINCT pp.CODPRESUPUESTO) AS presupuestos_vinculados,
                  ROUND(COUNT(DISTINCT pp.CODPRESUPUESTO) * 1.0 / COUNT(*),2) AS presupuestos_por_proyecto,
                  ROUND(AVG(CASE WHEN p.FECHAFIN IS NOT NULL
                       THEN julianday(p.FECHAFIN)-julianday(p.FECHAINICIO) END),0) AS duracion_media_dias
           FROM PROYECTOS p
           LEFT JOIN PRESUPROYE pp ON pp.CODPROYECTO = p.CODIGO
           GROUP BY p.TIPOOBRA
           ORDER BY total DESC""",
        "Dashboard de proyectos agrupado por tipo de obra. Muestra la "
        "cobertura presupuestaria (presupuestos por proyecto) y la duración "
        "media de ejecución para planificación de recursos.")

    print_query(6, "Análisis de SAT: tiempo medio entre reparaciones por código de obra",
        """SELECT CODALMACEN AS delegacion,
                  COUNT(*) AS reparaciones,
                  MIN(FECHA) AS primera_rep,
                  MAX(FECHA) AS ultima_rep,
                  ROUND((julianday(MAX(FECHA))-julianday(MIN(FECHA)))/NULLIF(COUNT(*)-1,0),1) AS dias_entre_reparaciones
           FROM REPCAB
           WHERE FECHA IS NOT NULL AND CODALMACEN IS NOT NULL
           GROUP BY CODALMACEN
           ORDER BY reparaciones DESC""",
        "Cadencia de reparaciones por delegación/almacén. El tiempo medio "
        "entre reparaciones indica la frecuencia de servicio. Aumenta si "
        "el parque instalado crece o los equipos envejecen.")

    print_query(7, "Trazabilidad completa: de pedido a albarán a factura",
        """SELECT
               d1.TIPO AS tipo_origen,
               COUNT(DISTINCT d1.CODIGO) AS docs_origen,
               COUNT(DISTINCT dr.CODDOCUMENTODESTINO) AS docs_destino,
               d2.TIPO AS tipo_destino,
               ROUND(100.0*COUNT(DISTINCT dr.CODDOCUMENTODESTINO)
                     /NULLIF(COUNT(DISTINCT d1.CODIGO),0),1) AS pct_convertidos
           FROM DOCCAB d1
           JOIN DOCREF dr ON dr.CODDOCUMENTO = d1.CODIGO
           JOIN DOCCAB d2 ON d2.CODIGO = dr.CODDOCUMENTODESTINO
           WHERE d1.TIPO IN (1,20,40)
           GROUP BY d1.TIPO, d2.TIPO
           ORDER BY docs_origen DESC""",
        "Flujo de documentos: qué % de presupuestos se convierten en pedidos, "
        "qué % de pedidos en albaranes, etc. La trazabilidad completa permite "
        "detectar cuellos de botella en el proceso comercial.")

    print_query(8, "KPIs financieros globales consolidados",
        """SELECT
               ROUND(SUM(CAST(BASEIMPONIBLE AS REAL)),2) AS base_total_facturas,
               ROUND(SUM(CAST(IVA AS REAL)),2) AS iva_total_facturas,
               ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2) AS facturado_total,
               COUNT(*) AS num_facturas,
               ROUND(AVG(CAST(IMPORTETOTAL AS REAL)),2) AS ticket_medio,
               COUNT(DISTINCT CODCLIENTE) AS clientes_facturados,
               ROUND(SUM(CAST(IMPORTETOTAL AS REAL))/NULLIF(COUNT(DISTINCT CODCLIENTE),0),2) AS facturado_por_cliente
           FROM DOCCAB
           WHERE TIPO=13 AND IMPORTETOTAL IS NOT NULL""",
        "KPIs financieros en una sola fila: base imponible, IVA, total, "
        "ticket medio y facturado por cliente activo. Referencia rápida "
        "para el controller financiero.")

    print_query(9, "Análisis de compras: evolución del precio unitario por artículo",
        """WITH precios AS (
               SELECT CODARTICULO,
                      ROUND(MIN(CAST(PRECIOCOSTE AS REAL)),4) AS precio_minimo,
                      ROUND(MAX(CAST(PRECIOCOSTE AS REAL)),4) AS precio_maximo,
                      ROUND(AVG(CAST(PRECIOCOSTE AS REAL)),4) AS precio_medio,
                      COUNT(*) AS num_registros,
                      ROUND(100.0*(MAX(CAST(PRECIOCOSTE AS REAL))-MIN(CAST(PRECIOCOSTE AS REAL)))
                            /NULLIF(MIN(CAST(PRECIOCOSTE AS REAL)),0),2) AS variacion_pct
               FROM COMPRA
               WHERE PRECIOCOSTE IS NOT NULL AND CAST(PRECIOCOSTE AS REAL) > 0
               GROUP BY CODARTICULO
           )
           SELECT CODARTICULO, precio_minimo, precio_maximo, precio_medio,
                  num_registros, variacion_pct
           FROM precios
           ORDER BY variacion_pct DESC
           LIMIT 10""",
        "Top 10 artículos con mayor variación de precio de compra. "
        "Artículos con >50% de variación entre el mínimo y máximo precio "
        "pagado indican ineficiencia en compras o alta volatilidad del mercado.")

    print_query(10, "Informe de gestión: resumen ejecutivo de todas las entidades",
        """SELECT 'Documentos' AS entidad, COUNT(*) AS total,
                  MIN(FECHA) AS desde, MAX(FECHA) AS hasta FROM DOCCAB
           UNION ALL
           SELECT 'Líneas doc', COUNT(*), NULL, NULL FROM DOCLIN
           UNION ALL
           SELECT 'Clientes', COUNT(*), MIN(FECHAALTA), MAX(FECHAALTA) FROM CLIENTE
              WHERE FECHAALTA IS NOT NULL
           UNION ALL
           SELECT 'Proveedores', COUNT(*), MIN(FECHAALTA), MAX(FECHAALTA) FROM PROVEED
              WHERE FECHAALTA IS NOT NULL
           UNION ALL
           SELECT 'Proyectos', COUNT(*), MIN(FECHAINICIO), MAX(FECHAINICIO) FROM PROYECTOS
           UNION ALL
           SELECT 'Reparaciones', COUNT(*), MIN(FECHA), MAX(FECHA) FROM REPCAB
           UNION ALL
           SELECT 'Recibos emitidos', COUNT(*), MIN(FECHAEMISION), MAX(FECHAEMISION) FROM RECIBO1
           UNION ALL
           SELECT 'Recibos cobrados', COUNT(*), MIN(FECHAEMISION), MAX(FECHAEMISION) FROM RECIBO3""",
        "Resumen ejecutivo de todas las entidades en un solo resultado. "
        "Permite a la dirección ver de un vistazo la cobertura temporal "
        "de cada módulo del ERP en la muestra del simulador.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

CATEGORIAS = {
    "gerencia":       (demo_gerencia,       "Gerencia"),
    "contabilidad":   (demo_contabilidad,   "Contabilidad"),
    "almacen":        (demo_almacen,        "Almacén"),
    "comercial":      (demo_comercial,      "Comercial"),
    "predicciones":   (demo_predicciones,   "Predicciones"),
    "alertas":        (demo_alertas,        "Alertas"),
    "reporting":      (demo_reporting,      "Reporting"),
}

if __name__ == "__main__":
    cat = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print(f"\n{'═'*76}")
    print(f"  DEMO ANALISTA BD — Consultas sobre simulador con datos reales")
    print(f"  BD: {DB_PATH}")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Privacidad: solo conteos, fechas, promedios — sin datos personales")
    print(f"{'═'*76}")

    if cat == "all":
        for fn, nombre in CATEGORIAS.values():
            fn()
    elif cat in CATEGORIAS:
        fn, nombre = CATEGORIAS[cat]
        fn()
    else:
        print(f"Categoría '{cat}' no encontrada. Disponibles: {', '.join(CATEGORIAS)}")
        sys.exit(1)

    print(f"\n{'═'*76}")
    print("  FIN DEL DEMO")
    print(f"{'═'*76}\n")
