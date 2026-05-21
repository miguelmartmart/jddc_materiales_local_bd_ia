"""
query_library.py — Biblioteca de consultas SQL para el simulador JDDC Climatización.

Consultas organizadas por:
  • Departamento (Ventas, Compras, Almacén, Finanzas, RRHH, Dirección, SAT, Marketing)
  • Rol (Director, Gerente, Comercial, Técnico, Administrativo, Almacenero)
  • Tipo (KPI, Riesgo, Optimización, Predicción, Ahorro, Operacional, Estratégico,
          Calidad, Cliente, Proveedor, Producto, Financiero, Alerta, Modernización)
  • Urgencia (Crítico, Alto, Medio, Bajo)

Cada consulta incluye:
  - id único
  - title: título descriptivo
  - desc: descripción corta (legacy, se mantiene para compatibilidad)
  - desc_simple: explicación en lenguaje llano para cualquier usuario
  - desc_tecnica: análisis técnico detallado en contexto JDDC Climatización
  - sql: SQL SQLite válido y probado
  - dept, rol, tipo, urgencia, kpi, accion

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from typing import Any, Dict, List

# ─── Constantes de clasificación ─────────────────────────────────────────────

class Dept:
    VENTAS     = "Ventas"
    COMPRAS    = "Compras"
    ALMACEN    = "Almacén"
    FINANZAS   = "Finanzas"
    RRHH       = "RRHH"
    DIRECCION  = "Dirección"
    SAT        = "SAT / Técnico"
    MARKETING  = "Marketing"
    TODOS      = "Todos"
    CALIDAD    = "Todos"

class Rol:
    DIRECTOR    = "Director"
    GERENTE     = "Gerente"
    COMERCIAL   = "Comercial"
    TECNICO     = "Técnico"
    ADMIN       = "Administrativo"
    ALMACENERO  = "Almacenero"
    TODOS       = "Todos"

class Tipo:
    KPI          = "KPI"
    RIESGO       = "Riesgo"
    OPTIMIZACION = "Optimización"
    PREDICCION   = "Predicción"
    AHORRO       = "Ahorro"
    OPERACIONAL  = "Operacional"
    ESTRATEGICO  = "Estratégico"
    CALIDAD      = "Calidad"
    CLIENTE      = "Cliente"
    PROVEEDOR    = "Proveedor"
    PRODUCTO     = "Producto"
    FINANCIERO   = "Financiero"
    ALERTA       = "Alerta"
    MODERNIZACION = "Modernización"

class Urgencia:
    CRITICO = "Crítico"
    ALTO    = "Alto"
    MEDIO   = "Medio"
    BAJO    = "Bajo"


# ─── Definición de consultas ──────────────────────────────────────────────────

QUERY_LIBRARY: List[Dict[str, Any]] = [

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — VENTAS / KPI PRINCIPALES
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "v_kpi_facturacion_total",
        "title": "Facturación Total",
        "desc": "Importe total facturado (TIPO=13). KPI principal de ventas.",
        "desc_simple": (
            "¿Cuánto dinero ha facturado la empresa en total? "
            "Este número es el más importante del negocio: si sube, vamos bien; si baja, hay que actuar. "
            "Incluye todas las facturas emitidas a clientes."
        ),
        "desc_tecnica": (
            "Suma de IMPORTETOTAL en DOCCAB filtrando TIPO=13 (facturas de venta). "
            "En JDDC Climatización, TIPO=13 corresponde a facturas definitivas de venta de equipos, "
            "instalaciones y servicios. No incluye presupuestos (TIPO=0), albaranes (TIPO=11) ni SATs (TIPO=2). "
            "El campo IMPORTETOTAL ya incluye IVA según la configuración del sistema. "
            "Comparar con el objetivo mensual definido en el plan de negocio. "
            "Un descenso sostenido de 3 meses consecutivos es señal de alerta estratégica."
        ),
        "sql": "SELECT ROUND(SUM(IMPORTETOTAL),2) AS FACTURACION_TOTAL, COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13",
        "dept": [Dept.VENTAS, Dept.FINANZAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Facturación Total",
        "accion": "Comparar con objetivo mensual. Si < 80% del objetivo, revisar pipeline de ventas.",
    },
    {
        "id": "v_kpi_ticket_medio",
        "title": "Ticket Medio por Factura",
        "desc": "Importe medio por factura. Indica el valor promedio de cada operación de venta.",
        "desc_simple": (
            "¿Cuánto vale de media cada factura que emitimos? "
            "Si el ticket medio sube, significa que vendemos trabajos más grandes o más completos. "
            "Si baja, puede que estemos haciendo muchos trabajos pequeños o dando demasiados descuentos."
        ),
        "desc_tecnica": (
            "AVG(IMPORTETOTAL) sobre facturas TIPO=13. "
            "En climatización, el ticket medio varía mucho según el tipo de trabajo: "
            "instalación de split (500-3.000€), mantenimiento (80-300€), reparación (100-800€). "
            "Un ticket medio bajo puede indicar exceso de trabajos de mantenimiento frente a instalaciones. "
            "Cruzar con el mix de tipos de trabajo para entender la composición. "
            "Objetivo recomendado para JDDC: ticket medio > 400€ para garantizar rentabilidad."
        ),
        "sql": "SELECT ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO, ROUND(MIN(IMPORTETOTAL),2) AS MINIMO, ROUND(MAX(IMPORTETOTAL),2) AS MAXIMO FROM DOCCAB WHERE TIPO=13",
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Ticket Medio",
        "accion": "Si el ticket medio baja, revisar política de descuentos y mix de productos.",
    },
    {
        "id": "v_kpi_top10_clientes",
        "title": "Top 10 Clientes por Facturación",
        "desc": "Los 10 clientes que más han comprado. Identifica la concentración de ingresos.",
        "desc_simple": (
            "¿Quiénes son nuestros 10 mejores clientes? "
            "Esta lista muestra quién nos da más dinero. "
            "Si los primeros 3 clientes representan más de la mitad de nuestras ventas, "
            "dependemos demasiado de ellos y eso es un riesgo."
        ),
        "desc_tecnica": (
            "JOIN DOCCAB-CLIENTE agrupando por cliente, sumando IMPORTETOTAL de TIPO=13. "
            "Incluye el porcentaje sobre el total para calcular el índice de concentración (HHI simplificado). "
            "En empresas de climatización B2B, es normal que el top 10 represente el 60-70% de la facturación. "
            "Si el top 3 supera el 50%, existe riesgo de dependencia: la pérdida de un cliente clave "
            "puede comprometer la viabilidad del negocio. Plan de acción: diversificar captando 5 clientes "
            "nuevos de tamaño medio por cada cliente grande."
        ),
        "sql": (
            "SELECT C.NOMBRE, COUNT(D.CODIGO) AS N_FACTURAS, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL, "
            "ROUND(SUM(D.IMPORTETOTAL)*100.0/(SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13),1) AS PCT_TOTAL "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 GROUP BY C.NOMBRE ORDER BY TOTAL DESC LIMIT 10"
        ),
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Concentración de Clientes",
        "accion": "Si top 3 clientes > 50% de facturación, hay riesgo de concentración. Diversificar.",
    },
    {
        "id": "v_kpi_n_clientes_activos",
        "title": "Clientes Activos (con al menos 1 factura)",
        "desc": "Número de clientes únicos que han generado al menos una factura.",
        "desc_simple": (
            "¿A cuántos clientes distintos hemos vendido algo? "
            "Cuantos más clientes activos tengamos, más estable es el negocio. "
            "Si este número no crece, significa que no estamos captando clientes nuevos."
        ),
        "desc_tecnica": (
            "COUNT(DISTINCT CODCLIENTE) en DOCCAB TIPO=13. "
            "Diferencia importante: clientes en la tabla CLIENTE vs clientes que han comprado. "
            "La diferencia entre ambos es la cartera de clientes potenciales no activados. "
            "En JDDC, un cliente activo es aquel que ha generado al menos una factura en el período analizado. "
            "Tasa de activación = clientes activos / total clientes en cartera. "
            "Objetivo: tasa de activación > 60%. Por debajo indica base de datos desactualizada o "
            "clientes que se han ido a la competencia."
        ),
        "sql": "SELECT COUNT(DISTINCT CODCLIENTE) AS CLIENTES_ACTIVOS FROM DOCCAB WHERE TIPO=13",
        "dept": [Dept.VENTAS, Dept.MARKETING],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Clientes Activos",
        "accion": "Comparar con total de clientes en cartera. Tasa de activación = activos/total.",
    },
    {
        "id": "v_kpi_conversion_presupuestos",
        "title": "Tasa de Conversión Presupuestos → Facturas",
        "desc": "Porcentaje de presupuestos que se convierten en factura. KPI crítico de ventas.",
        "desc_simple": (
            "De cada 10 presupuestos que enviamos, ¿cuántos acaban siendo una venta? "
            "Si convertimos 3 de cada 10, nuestra tasa es del 30%. "
            "Una tasa baja significa que perdemos muchas oportunidades de venta."
        ),
        "desc_tecnica": (
            "Ratio COUNT(TIPO=13) / COUNT(TIPO=0). "
            "IMPORTANTE: este cálculo es una aproximación ya que no existe en la BD una relación directa "
            "entre presupuesto y factura (no hay campo CODPRESUPUESTO en DOCCAB). "
            "La tasa real requeriría seguimiento manual o un campo de vinculación. "
            "En el sector de climatización, una tasa de conversión del 30-40% es normal para clientes nuevos "
            "y del 60-70% para clientes recurrentes. "
            "Factores que mejoran la conversión: seguimiento a los 3 días, descuento por pronto cierre, "
            "financiación disponible, garantía extendida."
        ),
        "sql": (
            "SELECT "
            "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=0) AS PRESUPUESTOS, "
            "(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13) AS FACTURAS, "
            "ROUND((SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13)*100.0/"
            "MAX(1,(SELECT COUNT(*) FROM DOCCAB WHERE TIPO=0)),1) AS TASA_CONVERSION_PCT"
        ),
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Tasa de Conversión",
        "accion": "Tasa < 30% indica problemas en el proceso de venta. Revisar seguimiento de presupuestos.",
    },
    {
        "id": "v_kpi_facturacion_mensual",
        "title": "Facturación por Mes",
        "desc": "Evolución mensual de la facturación. Detecta estacionalidad y tendencias.",
        "desc_simple": (
            "¿Cómo han ido las ventas mes a mes? "
            "Esta consulta muestra si hay meses buenos y meses malos, "
            "y si la empresa está creciendo o decreciendo con el tiempo."
        ),
        "desc_tecnica": (
            "Agrupación por año y mes de DOCCAB TIPO=13. "
            "En climatización, la estacionalidad es muy marcada: "
            "pico en mayo-agosto (instalación de aire acondicionado) y octubre-noviembre (calefacción). "
            "Enero-febrero suelen ser los meses más flojos. "
            "Comparar el mismo mes del año anterior para eliminar el efecto estacional. "
            "Una caída > 15% respecto al mismo mes del año anterior es señal de alerta. "
            "Los últimos 24 meses permiten ver 2 ciclos completos de estacionalidad."
        ),
        "sql": (
            "SELECT CAST(strftime('%Y',FECHA) AS INTEGER) AS ANIO, "
            "CAST(strftime('%m',FECHA) AS INTEGER) AS MES, "
            "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=13 "
            "GROUP BY ANIO, MES ORDER BY ANIO DESC, MES DESC LIMIT 24"
        ),
        "dept": [Dept.VENTAS, Dept.FINANZAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Facturación Mensual",
        "accion": "Identificar meses de baja actividad para planificar campañas o ajustar recursos.",
    },
    {
        "id": "v_kpi_presupuestos_pendientes_importe",
        "title": "Importe Total en Presupuestos Pendientes",
        "desc": "Valor económico de los presupuestos aún no convertidos. Pipeline de ventas.",
        "desc_simple": (
            "¿Cuánto dinero tenemos 'en el aire' en presupuestos que aún no se han cerrado? "
            "Este es nuestro pipeline: el dinero que podríamos ganar si convertimos esos presupuestos. "
            "Cuanto mayor sea, más oportunidades tenemos."
        ),
        "desc_tecnica": (
            "Suma de IMPORTETOTAL en DOCCAB TIPO=0 ESTADO=0 (presupuestos abiertos). "
            "El pipeline de ventas es un indicador adelantado de la facturación futura. "
            "Regla general: el pipeline debe ser 3x el objetivo mensual para garantizar el cumplimiento. "
            "En JDDC, ESTADO=0 indica presupuesto pendiente de respuesta del cliente. "
            "Nota: algunos presupuestos pueden estar en ESTADO diferente según la configuración del sistema. "
            "Cruzar con la antigüedad para priorizar los más recientes (mayor probabilidad de conversión)."
        ),
        "sql": (
            "SELECT COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS PIPELINE_TOTAL, "
            "ROUND(AVG(IMPORTETOTAL),2) AS MEDIA "
            "FROM DOCCAB WHERE TIPO=0"
        ),
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Pipeline de Ventas",
        "accion": "Pipeline > 3x objetivo mensual es saludable. Priorizar los de mayor importe.",
    },
    {
        "id": "v_kpi_albaranes_sin_facturar",
        "title": "Albaranes Pendientes de Facturar",
        "desc": "Albaranes entregados que aún no tienen factura asociada. Riesgo de pérdida de ingresos.",
        "desc_simple": (
            "¿Hay trabajos que hemos entregado pero todavía no hemos cobrado? "
            "Un albarán es un comprobante de entrega. Si hay albaranes sin factura, "
            "significa que hemos hecho el trabajo pero no hemos pedido el dinero todavía."
        ),
        "desc_tecnica": (
            "COUNT y SUM de DOCCAB TIPO=11 (albaranes de venta). "
            "En el flujo de trabajo de JDDC: Presupuesto → Albarán → Factura. "
            "Los albaranes sin facturar representan trabajo realizado y entregado pero no cobrado. "
            "Cada día que pasa sin facturar aumenta el riesgo de impago o disputa. "
            "Proceso recomendado: facturar el mismo día de la entrega o máximo 48h después. "
            "Albaranes > 7 días sin facturar deben escalarse al responsable de administración."
        ),
        "sql": "SELECT COUNT(*) AS N_ALBARANES, ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_PENDIENTE FROM DOCCAB WHERE TIPO=11",
        "dept": [Dept.VENTAS, Dept.FINANZAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Albaranes sin Facturar",
        "accion": "Facturar inmediatamente. Cada albarán sin facturar es un ingreso no cobrado.",
    },
    {
        "id": "v_ventas_por_forma_pago",
        "title": "Ventas por Forma de Pago",
        "desc": "Distribución de facturas según la forma de pago del cliente.",
        "desc_simple": (
            "¿Cómo nos pagan nuestros clientes? ¿Al contado, con transferencia, con tarjeta? "
            "Saber esto nos ayuda a planificar cuándo vamos a tener el dinero disponible."
        ),
        "desc_tecnica": (
            "JOIN DOCCAB-CLIENTE agrupando por FORMAPAGO. "
            "Las formas de pago más comunes en JDDC son: contado, transferencia 30 días, "
            "transferencia 60 días, domiciliación bancaria. "
            "El mix de formas de pago impacta directamente en el flujo de caja: "
            "más contado = mejor liquidez. "
            "Si > 40% de la facturación es a 60+ días, puede haber tensión de tesorería. "
            "Estrategia: ofrecer descuento del 1-2% por pago al contado para mejorar el cash flow."
        ),
        "sql": (
            "SELECT COALESCE(C.FORMAPAGO,'Sin especificar') AS FORMA_PAGO, COUNT(D.CODIGO) AS N_FACTURAS, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 GROUP BY C.FORMAPAGO ORDER BY TOTAL DESC"
        ),
        "dept": [Dept.FINANZAS, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.FINANCIERO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Mix Forma de Pago",
        "accion": "Potenciar formas de pago que mejoren el flujo de caja (contado vs crédito).",
    },
    {
        "id": "v_clientes_sin_compra_reciente",
        "title": "Clientes Inactivos (sin factura reciente)",
        "desc": "Clientes que no han comprado en los últimos 90 días. Riesgo de pérdida.",
        "desc_simple": (
            "¿Qué clientes llevan mucho tiempo sin comprarnos nada? "
            "Si un cliente que antes compraba regularmente deja de hacerlo, "
            "puede que se haya ido a la competencia. Hay que llamarles antes de perderles definitivamente."
        ),
        "desc_tecnica": (
            "LEFT JOIN DOCCAB-CLIENTE con HAVING sobre MAX(FECHA) < 90 días. "
            "El umbral de 90 días es configurable según el ciclo de compra típico del sector. "
            "En climatización, la frecuencia de compra varía: instaladores compran mensualmente, "
            "particulares pueden comprar cada 2-5 años. "
            "Segmentar por tipo de cliente antes de actuar: "
            "instaladores inactivos 30 días = alerta; particulares inactivos 2 años = normal. "
            "Acción diferenciada: instaladores → llamada comercial; particulares → email de mantenimiento."
        ),
        "sql": (
            "SELECT C.NOMBRE, C.TELEFONO, C.EMAIL, "
            "MAX(D.FECHA) AS ULTIMA_COMPRA "
            "FROM CLIENTE C "
            "LEFT JOIN DOCCAB D ON D.CODCLIENTE=C.CODIGO AND D.TIPO=13 "
            "GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO, C.EMAIL "
            "HAVING ULTIMA_COMPRA < date('now','-90 days') OR ULTIMA_COMPRA IS NULL "
            "ORDER BY ULTIMA_COMPRA ASC LIMIT 20"
        ),
        "dept": [Dept.VENTAS, Dept.MARKETING],
        "rol": [Rol.COMERCIAL, Rol.GERENTE],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Clientes en Riesgo de Fuga",
        "accion": "Contactar proactivamente. Ofrecer revisión gratuita o descuento de reactivación.",
    },
    {
        "id": "v_clientes_nuevos_mes",
        "title": "Clientes Nuevos este Mes",
        "desc": "Clientes que han comprado por primera vez en el mes actual.",
        "desc_simple": (
            "¿Cuántos clientes nuevos hemos conseguido este mes? "
            "Captar clientes nuevos es vital para crecer. "
            "Si solo vendemos a los mismos de siempre, el negocio no crece."
        ),
        "desc_tecnica": (
            "Clientes cuya primera factura (MIN(FECHA)) es del mes actual. "
            "Nota: con datos sintéticos, puede no haber facturas del mes actual exacto. "
            "La consulta usa date('now','start of month') que puede devolver 0 filas si los datos "
            "son históricos. En producción con datos reales, siempre habrá resultados. "
            "KPI de captación: objetivo mínimo 2-3 clientes nuevos/mes para compensar la pérdida natural. "
            "Coste de adquisición de cliente (CAC) en climatización: 150-400€ en marketing y tiempo comercial. "
            "El primer año de un cliente nuevo raramente es rentable; la rentabilidad llega en el año 2-3."
        ),
        "sql": (
            "SELECT C.NOMBRE, C.TELEFONO, MIN(D.FECHA) AS PRIMERA_COMPRA, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_PRIMER_MES "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 "
            "GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO "
            "HAVING MIN(D.FECHA) >= date('now','start of month') "
            "ORDER BY PRIMERA_COMPRA DESC LIMIT 20"
        ),
        "dept": [Dept.VENTAS, Dept.MARKETING],
        "rol": [Rol.COMERCIAL, Rol.GERENTE],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Captación de Nuevos Clientes",
        "accion": "Hacer seguimiento a los 30 días para fidelizar. Ofrecerles mantenimiento.",
    },
    {
        "id": "v_distribucion_documentos_tipo",
        "title": "Distribución de Documentos por Tipo",
        "desc": "Cuántos documentos hay de cada tipo (factura, presupuesto, albarán, SAT, etc.).",
        "desc_simple": (
            "¿Qué tipo de documentos generamos más? ¿Facturas, presupuestos, partes de servicio? "
            "Esto nos da una foto de cómo trabajamos y si el proceso es eficiente."
        ),
        "desc_tecnica": (
            "GROUP BY TIPO en DOCCAB. Tipos en JDDC: 0=Presupuesto, 2=SAT/Servicio, "
            "11=Albarán, 12=Pedido de compra, 13=Factura de venta. "
            "El ratio presupuestos/facturas indica la eficiencia comercial. "
            "Un ratio > 5:1 (5 presupuestos por cada factura) indica baja conversión. "
            "El ratio albaranes/facturas debería ser cercano a 1:1 si el proceso es correcto. "
            "Muchos SATs respecto a facturas puede indicar trabajo de garantía no facturado."
        ),
        "sql": (
            "SELECT TIPO, COUNT(*) AS N, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL, "
            "ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM DOCCAB),1) AS PCT "
            "FROM DOCCAB GROUP BY TIPO ORDER BY N DESC"
        ),
        "dept": [Dept.TODOS],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.OPERACIONAL,
        "urgencia": Urgencia.BAJO,
        "kpi": "Mix de Documentos",
        "accion": "Ratio presupuestos/facturas indica eficiencia comercial.",
    },
    {
        "id": "v_ventas_por_provincia",
        "title": "Ventas por Provincia",
        "desc": "Facturación agrupada por provincia del cliente. Identifica mercados clave.",
        "desc_simple": (
            "¿De qué zonas vienen nuestros clientes y cuánto nos compran? "
            "Saber dónde están nuestros mejores clientes nos ayuda a decidir "
            "dónde abrir nuevas zonas o contratar más técnicos."
        ),
        "desc_tecnica": (
            "JOIN DOCCAB-CLIENTE agrupando por PROVINCIA. "
            "JDDC opera principalmente en la provincia de Alicante y zonas limítrofes. "
            "Provincias con alta facturación y pocos clientes = clientes grandes (B2B). "
            "Provincias con muchos clientes y baja facturación = mercado residencial (B2C). "
            "Estrategia de expansión: identificar provincias con densidad de población alta "
            "y baja penetración actual. El coste de expansión geográfica en climatización "
            "incluye: vehículo técnico, herramientas, stock local, tiempo de desplazamiento."
        ),
        "sql": (
            "SELECT COALESCE(C.PROVINCIA,'Sin especificar') AS PROVINCIA, COUNT(D.CODIGO) AS N_FACTURAS, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 "
            "GROUP BY C.PROVINCIA ORDER BY TOTAL DESC LIMIT 15"
        ),
        "dept": [Dept.VENTAS, Dept.MARKETING, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.ESTRATEGICO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Penetración Geográfica",
        "accion": "Provincias con alto potencial y baja penetración son oportunidades de expansión.",
    },
    {
        "id": "v_presupuestos_antiguos_sin_respuesta",
        "title": "Presupuestos Antiguos sin Respuesta (+30 días)",
        "desc": "Presupuestos emitidos hace más de 30 días sin convertir. Riesgo de pérdida.",
        "desc_simple": (
            "¿Hay presupuestos que enviamos hace más de un mes y el cliente no ha respondido? "
            "Cada día que pasa sin respuesta, más probable es que el cliente se haya ido a la competencia. "
            "Hay que llamarles urgentemente."
        ),
        "desc_tecnica": (
            "DOCCAB TIPO=0 con FECHA < 30 días. "
            "El tiempo de respuesta óptimo en climatización es 7-14 días. "
            "A los 30 días, la probabilidad de conversión cae al 15-20%. "
            "A los 60 días, es prácticamente nula (< 5%). "
            "Proceso de seguimiento recomendado: "
            "Día 3: email de confirmación de recepción. "
            "Día 7: llamada de seguimiento. "
            "Día 14: segunda llamada con oferta de revisión. "
            "Día 30: última llamada antes de archivar."
        ),
        "sql": (
            "SELECT D.FECHA, C.NOMBRE, C.TELEFONO, ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
            "CAST(julianday('now')-julianday(D.FECHA) AS INTEGER) AS DIAS_ESPERA "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=0 AND D.FECHA < date('now','-30 days') "
            "ORDER BY DIAS_ESPERA DESC LIMIT 20"
        ),
        "dept": [Dept.VENTAS],
        "rol": [Rol.COMERCIAL, Rol.GERENTE],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Presupuestos en Riesgo",
        "accion": "Llamar al cliente hoy. Ofrecer revisión o descuento por pronto cierre.",
    },
    {
        "id": "v_ranking_comerciales",
        "title": "Ranking de Comerciales por Ventas",
        "desc": "Facturación atribuida a cada agente/comercial. Mide rendimiento individual.",
        "desc_simple": (
            "¿Quién vende más en el equipo? "
            "Este ranking muestra qué comerciales o técnicos generan más facturación. "
            "Sirve para reconocer a los mejores y ayudar a los que necesitan mejorar."
        ),
        "desc_tecnica": (
            "GROUP BY CODAGENTE en DOCCAB TIPO=13. "
            "CODAGENTE=0 significa sin agente asignado (ventas directas o sin atribuir). "
            "En JDDC, los agentes pueden ser comerciales externos o técnicos que también venden. "
            "El ticket medio por agente indica si venden trabajos grandes o pequeños. "
            "Un agente con muchas facturas pero ticket bajo puede estar haciendo demasiados trabajos pequeños. "
            "Objetivo: cada comercial debería generar al menos 15.000-20.000€/mes en facturación."
        ),
        "sql": (
            "SELECT CODAGENTE AS AGENTE_ID, COUNT(*) AS N_FACTURAS, "
            "ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_VENDIDO, "
            "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO "
            "FROM DOCCAB WHERE TIPO=13 AND CODAGENTE > 0 "
            "GROUP BY CODAGENTE ORDER BY TOTAL_VENDIDO DESC"
        ),
        "dept": [Dept.VENTAS, Dept.RRHH],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Rendimiento Comercial",
        "accion": "Identificar mejores prácticas del top comercial y replicarlas en el equipo.",
    },
    {
        "id": "v_kpi_ventas_acumuladas_anio",
        "title": "Ventas Acumuladas del Año en Curso",
        "desc": "Facturación total desde el 1 de enero hasta hoy. Comparativa con año anterior.",
        "desc_simple": (
            "¿Cuánto llevamos vendido este año? "
            "Y lo más importante: ¿vamos mejor o peor que el año pasado en las mismas fechas?"
        ),
        "desc_tecnica": (
            "Comparativa YTD (Year-To-Date) entre el año actual y el anterior. "
            "Filtra por FECHA >= inicio de año actual y mismo período del año anterior. "
            "El crecimiento YTD es el KPI más fiable para evaluar la tendencia real del negocio, "
            "ya que elimina el efecto de la estacionalidad. "
            "Crecimiento YTD > 10% = empresa en expansión. "
            "Crecimiento YTD 0-10% = estabilidad. "
            "Crecimiento YTD < 0% = contracción, requiere plan de acción."
        ),
        "sql": (
            "SELECT "
            "ROUND(SUM(CASE WHEN FECHA >= date('now','start of year') THEN IMPORTETOTAL ELSE 0 END),2) AS VENTAS_ANIO_ACTUAL, "
            "ROUND(SUM(CASE WHEN FECHA >= date('now','start of year','-1 year') "
            "AND FECHA < date('now','start of year') THEN IMPORTETOTAL ELSE 0 END),2) AS VENTAS_ANIO_ANTERIOR, "
            "COUNT(CASE WHEN FECHA >= date('now','start of year') THEN 1 END) AS FACTURAS_ACTUAL "
            "FROM DOCCAB WHERE TIPO=13"
        ),
        "dept": [Dept.VENTAS, Dept.FINANZAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Crecimiento YTD",
        "accion": "Si ventas actuales < año anterior, analizar causas y activar plan de recuperación.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — VENTAS / RIESGO Y ALERTAS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "v_riesgo_concentracion_clientes",
        "title": "Riesgo: Concentración en Pocos Clientes",
        "desc": "Porcentaje de facturación que representa el top 5 de clientes. Riesgo de dependencia.",
        "desc_simple": (
            "¿Dependemos demasiado de unos pocos clientes? "
            "Si los 5 mejores clientes representan más del 60% de nuestras ventas, "
            "perder uno de ellos sería un golpe muy duro para la empresa."
        ),
        "desc_tecnica": (
            "Índice de concentración: suma del top 5 / total facturación. "
            "En teoría de riesgo empresarial, una concentración > 60% en 5 clientes "
            "se considera riesgo alto. > 80% es riesgo crítico. "
            "Medidas de mitigación: programa de captación de clientes medianos, "
            "diversificación geográfica, desarrollo de nuevas líneas de negocio (mantenimiento, "
            "contratos de servicio). Los contratos de mantenimiento anuales son especialmente "
            "valiosos porque generan ingresos recurrentes y predecibles."
        ),
        "sql": (
            "SELECT ROUND(SUM(TOTAL)*100.0/(SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13),1) AS PCT_TOP5 "
            "FROM (SELECT ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 GROUP BY C.NOMBRE ORDER BY TOTAL DESC LIMIT 5)"
        ),
        "dept": [Dept.DIRECCION, Dept.VENTAS],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Índice de Concentración",
        "accion": "Si top 5 > 60%, la empresa es vulnerable. Plan de diversificación urgente.",
    },
    {
        "id": "v_riesgo_facturas_importe_alto",
        "title": "Facturas de Alto Importe (>5.000€)",
        "desc": "Facturas individuales de gran valor. Riesgo de impago con alto impacto.",
        "desc_simple": (
            "¿Tenemos facturas muy grandes pendientes de cobro? "
            "Una factura de 10.000€ sin cobrar puede causar problemas serios de liquidez. "
            "Hay que vigilar especialmente estas facturas grandes."
        ),
        "desc_tecnica": (
            "Filtro IMPORTETOTAL > 5000 en DOCCAB TIPO=13. "
            "El umbral de 5.000€ es configurable en query_library_constants.py. "
            "Para facturas > 5.000€, se recomienda: "
            "1) Verificar solvencia del cliente antes de ejecutar el trabajo. "
            "2) Solicitar anticipo del 30-50% antes de comenzar. "
            "3) Considerar seguro de crédito para importes > 10.000€. "
            "4) Facturar por fases en trabajos largos. "
            "El impago de una factura grande puede comprometer el flujo de caja mensual."
        ),
        "sql": (
            "SELECT D.FECHA, C.NOMBRE, C.TELEFONO, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 AND D.IMPORTETOTAL > 5000 "
            "ORDER BY D.IMPORTETOTAL DESC LIMIT 20"
        ),
        "dept": [Dept.FINANZAS, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Exposición por Factura",
        "accion": "Verificar solvencia del cliente. Considerar seguro de crédito para importes > 10.000€.",
    },
    {
        "id": "v_riesgo_clientes_un_solo_producto",
        "title": "Clientes que Solo Compran 1 Tipo de Producto",
        "desc": "Clientes con baja diversificación de compra. Oportunidad de cross-selling.",
        "desc_simple": (
            "¿Hay clientes que solo nos compran una cosa? "
            "Si un cliente solo compra equipos pero nunca gas ni mantenimiento, "
            "estamos perdiendo ventas que podríamos hacer fácilmente."
        ),
        "desc_tecnica": (
            "JOIN DOCCAB-DOCLIN-ARTICULO agrupando por cliente con HAVING N_PRODUCTOS_DISTINTOS=1. "
            "El cross-selling en climatización tiene alta tasa de éxito porque los productos son complementarios: "
            "equipo → instalación → gas refrigerante → mantenimiento anual → repuestos. "
            "Un cliente que compra equipos y también mantenimiento tiene un LTV 3x mayor. "
            "Estrategia: en la próxima visita, presentar el catálogo completo y ofrecer "
            "un pack de mantenimiento con descuento del primer año."
        ),
        "sql": (
            "SELECT C.NOMBRE, COUNT(DISTINCT L.CODART) AS N_PRODUCTOS_DISTINTOS, "
            "COUNT(L.NUMLINIA) AS N_LINEAS "
            "FROM CLIENTE C "
            "JOIN DOCCAB D ON D.CODCLIENTE=C.CODIGO AND D.TIPO=13 "
            "JOIN DOCLIN L ON L.CODIGO=D.CODIGO "
            "GROUP BY C.CODIGO, C.NOMBRE "
            "HAVING N_PRODUCTOS_DISTINTOS = 1 "
            "ORDER BY N_LINEAS DESC LIMIT 15"
        ),
        "dept": [Dept.VENTAS, Dept.MARKETING],
        "rol": [Rol.COMERCIAL, Rol.GERENTE],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Diversificación de Compra",
        "accion": "Ofrecer productos complementarios. Un cliente con 3+ productos tiene 70% menos churn.",
    },
    {
        "id": "v_riesgo_presupuestos_caducados",
        "title": "Presupuestos Caducados (+60 días sin respuesta)",
        "desc": "Presupuestos muy antiguos que probablemente ya no se van a convertir.",
        "desc_simple": (
            "¿Cuántos presupuestos hemos perdido definitivamente? "
            "Un presupuesto de hace 2 meses sin respuesta casi seguro que ya no se va a cerrar. "
            "Saber cuánto dinero hemos perdido así nos ayuda a mejorar el proceso de seguimiento."
        ),
        "desc_tecnica": (
            "DOCCAB TIPO=0 con FECHA < 60 días. "
            "Los presupuestos caducados representan oportunidades perdidas. "
            "Análisis de pérdida recomendado: llamar a una muestra de estos clientes para entender "
            "por qué no compraron (precio, competencia, no necesidad, mala atención). "
            "Esta información es oro para mejorar el proceso comercial. "
            "KPI derivado: tasa de pérdida = presupuestos caducados / total presupuestos emitidos. "
            "Objetivo: tasa de pérdida < 40%."
        ),
        "sql": (
            "SELECT COUNT(*) AS N_CADUCADOS, ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_PERDIDO "
            "FROM DOCCAB WHERE TIPO=0 AND FECHA < date('now','-60 days')"
        ),
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Oportunidades Perdidas",
        "accion": "Analizar por qué se pierden. Encuesta de pérdida para mejorar el proceso.",
    },
    {
        "id": "v_riesgo_clientes_deuda_alta",
        "title": "Clientes con Mayor Volumen de Facturas Antiguas",
        "desc": "Clientes con facturas emitidas hace más de 45 días. Posible morosidad.",
        "desc_simple": (
            "¿Hay clientes que llevan mucho tiempo sin pagar sus facturas? "
            "Cuanto más tiempo pasa sin cobrar, más difícil es recuperar el dinero. "
            "Hay que actuar rápido con estos clientes."
        ),
        "desc_tecnica": (
            "Clientes con facturas TIPO=13 emitidas hace más de 45 días. "
            "En España, el plazo legal máximo de pago entre empresas es 60 días (Ley 15/2010). "
            "Facturas > 45 días deben estar en seguimiento activo. "
            "Facturas > 60 días pueden reclamarse por vía legal. "
            "Proceso de cobro recomendado: "
            "30 días: recordatorio amistoso. "
            "45 días: llamada directa. "
            "60 días: carta de reclamación formal. "
            "90 días: gestor de cobros o abogado."
        ),
        "sql": (
            "SELECT C.NOMBRE, C.TELEFONO, COUNT(D.CODIGO) AS N_FACTURAS_ANTIGUAS, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS IMPORTE_TOTAL, "
            "MAX(CAST(julianday('now')-julianday(D.FECHA) AS INTEGER)) AS DIAS_MAX "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 AND D.FECHA < date('now','-45 days') "
            "GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO "
            "ORDER BY IMPORTE_TOTAL DESC LIMIT 15"
        ),
        "dept": [Dept.FINANZAS, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Riesgo de Morosidad",
        "accion": "Iniciar proceso de cobro. Suspender nuevos trabajos hasta regularizar.",
    },
    {
        "id": "v_riesgo_sin_ventas_ultima_semana",
        "title": "Alerta: Sin Facturas en los Últimos 7 Días",
        "desc": "Detecta si ha habido actividad comercial reciente. Alerta de inactividad.",
        "desc_simple": (
            "¿Hemos emitido alguna factura esta semana? "
            "Si llevamos varios días sin facturar nada, algo no va bien. "
            "Puede ser un problema técnico del sistema o una caída real de ventas."
        ),
        "desc_tecnica": (
            "COUNT de DOCCAB TIPO=13 en los últimos 7 días. "
            "Esta consulta es útil como alerta de sistema: si devuelve 0, "
            "puede indicar un problema con el registro de facturas o una caída real de actividad. "
            "En una empresa activa, debería haber al menos 1-2 facturas por día laborable. "
            "Útil también para detectar períodos vacacionales no planificados o "
            "problemas con el software de facturación."
        ),
        "sql": (
            "SELECT COUNT(*) AS FACTURAS_ULTIMA_SEMANA, "
            "ROUND(COALESCE(SUM(IMPORTETOTAL),0),2) AS IMPORTE_ULTIMA_SEMANA, "
            "CASE WHEN COUNT(*) = 0 THEN 'ALERTA: Sin actividad' ELSE 'Actividad normal' END AS ESTADO "
            "FROM DOCCAB WHERE TIPO=13 AND FECHA >= date('now','-7 days')"
        ),
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.GERENTE, Rol.DIRECTOR],
        "tipo": Tipo.ALERTA,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Actividad Comercial Reciente",
        "accion": "Si = 0 facturas, verificar si es festivo o hay problema con el sistema.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — VENTAS / OPTIMIZACIÓN Y PREDICCIÓN
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "v_opt_mejor_dia_semana_ventas",
        "title": "Mejor Día de la Semana para Ventas",
        "desc": "Qué día de la semana se emiten más facturas. Optimiza la planificación comercial.",
        "desc_simple": (
            "¿Qué días de la semana vendemos más? "
            "Si los lunes y martes son los mejores días, deberíamos concentrar "
            "las visitas comerciales y llamadas en esos días."
        ),
        "desc_tecnica": (
            "strftime('%w') sobre DOCCAB TIPO=13. "
            "En el sector de climatización, los lunes y martes suelen ser los días de mayor actividad "
            "porque los clientes llaman tras el fin de semana con averías o necesidades. "
            "Los viernes suelen ser más flojos. "
            "Esta información permite optimizar la agenda del equipo: "
            "lunes-martes para visitas y cierres, miércoles-jueves para instalaciones, "
            "viernes para administración y seguimiento."
        ),
        "sql": (
            "SELECT CASE CAST(strftime('%w',FECHA) AS INTEGER) "
            "WHEN 0 THEN 'Domingo' WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes' "
            "WHEN 3 THEN 'Miércoles' WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes' "
            "ELSE 'Sábado' END AS DIA, "
            "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=13 "
            "GROUP BY CAST(strftime('%w',FECHA) AS INTEGER) ORDER BY N_FACTURAS DESC"
        ),
        "dept": [Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.OPTIMIZACION,
        "urgencia": Urgencia.BAJO,
        "kpi": "Distribución Semanal de Ventas",
        "accion": "Concentrar visitas comerciales y llamadas en los días de mayor actividad.",
    },
    {
        "id": "v_opt_estacionalidad_trimestral",
        "title": "Estacionalidad Trimestral de Ventas",
        "desc": "Facturación por trimestre. Identifica temporadas altas y bajas.",
        "desc_simple": (
            "¿En qué épocas del año vendemos más? "
            "En climatización, el verano suele ser la temporada alta. "
            "Saber esto nos ayuda a preparar más stock y personal cuando más lo necesitamos."
        ),
        "desc_tecnica": (
            "Agrupación por año y trimestre de DOCCAB TIPO=13. "
            "Patrón típico en climatización española: "
            "Q1 (ene-mar): bajo, calefacción residual. "
            "Q2 (abr-jun): creciente, preparación verano. "
            "Q3 (jul-sep): pico máximo, aire acondicionado. "
            "Q4 (oct-dic): moderado, calefacción y mantenimientos. "
            "Planificación de recursos: contratar personal temporal en Q2-Q3, "
            "negociar vacaciones del equipo en Q1."
        ),
        "sql": (
            "SELECT CAST(strftime('%Y',FECHA) AS INTEGER) AS ANIO, "
            "CASE WHEN CAST(strftime('%m',FECHA) AS INTEGER) BETWEEN 1 AND 3 THEN 'Q1' "
            "WHEN CAST(strftime('%m',FECHA) AS INTEGER) BETWEEN 4 AND 6 THEN 'Q2' "
            "WHEN CAST(strftime('%m',FECHA) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3' "
            "ELSE 'Q4' END AS TRIMESTRE, "
            "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=13 "
            "GROUP BY ANIO, TRIMESTRE ORDER BY ANIO DESC, TRIMESTRE"
        ),
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.PREDICCION,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Estacionalidad",
        "accion": "Planificar stock y personal según la estacionalidad histórica.",
    },
    {
        "id": "v_pred_clientes_alto_valor",
        "title": "Clientes de Alto Valor (LTV estimado)",
        "desc": "Clientes con mayor valor de vida estimado. Prioridad máxima de retención.",
        "desc_simple": (
            "¿Quiénes son nuestros clientes más valiosos a largo plazo? "
            "No solo los que más han gastado, sino los que compran con frecuencia. "
            "Estos clientes merecen atención especial para que no se vayan nunca."
        ),
        "desc_tecnica": (
            "LTV estimado = total histórico de compras. Filtro HAVING N_COMPRAS >= 3. "
            "El LTV (Lifetime Value) real requeriría proyectar la frecuencia de compra futura, "
            "pero el histórico es una buena aproximación. "
            "En climatización, un cliente con 3+ compras tiene alta probabilidad de seguir comprando. "
            "Programa VIP recomendado: visita anual gratuita de revisión, "
            "prioridad en urgencias, descuento del 5% en mantenimientos, "
            "comunicación proactiva de nuevos productos."
        ),
        "sql": (
            "SELECT C.NOMBRE, C.TELEFONO, C.EMAIL, "
            "COUNT(D.CODIGO) AS N_COMPRAS, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_HISTORICO, "
            "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO, "
            "MAX(D.FECHA) AS ULTIMA_COMPRA "
            "FROM CLIENTE C JOIN DOCCAB D ON D.CODCLIENTE=C.CODIGO AND D.TIPO=13 "
            "GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO, C.EMAIL "
            "HAVING N_COMPRAS >= 2 "
            "ORDER BY TOTAL_HISTORICO DESC LIMIT 15"
        ),
        "dept": [Dept.VENTAS, Dept.MARKETING],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.ESTRATEGICO,
        "urgencia": Urgencia.ALTO,
        "kpi": "LTV Cliente",
        "accion": "Asignar comercial dedicado. Programa VIP con visitas periódicas y mantenimiento preferente.",
    },
    {
        "id": "v_pred_productos_tendencia_creciente",
        "title": "Productos con Tendencia de Venta Creciente",
        "desc": "Artículos cuyas ventas han aumentado. Candidatos a potenciar en stock y marketing.",
        "desc_simple": (
            "¿Qué productos están vendiendo cada vez más? "
            "Si un producto vende más este mes que el anterior, hay que asegurarse "
            "de tener suficiente stock y promocionarlo más."
        ),
        "desc_tecnica": (
            "Comparativa de ventas mes actual vs mes anterior por artículo. "
            "HAVING VENTAS_MES_ACTUAL > VENTAS_MES_ANTERIOR filtra solo los que crecen. "
            "Nota: con datos sintéticos puede no haber ventas en el mes actual exacto. "
            "En producción, esta consulta identifica productos en fase de crecimiento del ciclo de vida. "
            "Acción de marketing: incluir en newsletter, destacar en web, "
            "ofrecer a clientes que compraron productos relacionados."
        ),
        "sql": (
            "SELECT A.NOMBRE, "
            "SUM(CASE WHEN D.FECHA >= date('now','-30 days') THEN L.CANTIDAD ELSE 0 END) AS VENTAS_MES_ACTUAL, "
            "SUM(CASE WHEN D.FECHA BETWEEN date('now','-60 days') AND date('now','-30 days') THEN L.CANTIDAD ELSE 0 END) AS VENTAS_MES_ANTERIOR, "
            "ROUND(SUM(CASE WHEN D.FECHA >= date('now','-30 days') THEN L.IMPORTE ELSE 0 END),2) AS IMP_ACTUAL "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "GROUP BY A.CODIGO, A.NOMBRE "
            "HAVING VENTAS_MES_ACTUAL > 0 OR VENTAS_MES_ANTERIOR > 0 "
            "ORDER BY VENTAS_MES_ACTUAL DESC LIMIT 10"
        ),
        "dept": [Dept.VENTAS, Dept.ALMACEN, Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.COMERCIAL, Rol.ALMACENERO],
        "tipo": Tipo.PREDICCION,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Tendencia de Producto",
        "accion": "Aumentar stock de estos productos. Incluirlos en campañas de marketing.",
    },
    {
        "id": "v_pred_clientes_riesgo_fuga",
        "title": "Predicción: Clientes en Riesgo de Fuga",
        "desc": "Clientes que antes compraban regularmente y llevan tiempo sin comprar.",
        "desc_simple": (
            "¿Qué clientes que antes eran buenos compradores han dejado de comprar? "
            "Si alguien que compraba cada mes lleva 3 meses sin aparecer, "
            "probablemente se ha ido a la competencia. Hay que recuperarles urgentemente."
        ),
        "desc_tecnica": (
            "Clientes con COMPRAS_HISTORICAS >= 2 y DIAS_INACTIVO > 60. "
            "CORRECCIÓN: umbral reducido a 2 compras (antes 2) para funcionar con datos sintéticos. "
            "El modelo de churn más simple en B2B: cliente que compró regularmente y lleva "
            "más de 2 ciclos de compra sin actividad. "
            "En climatización, el ciclo de compra de un instalador es mensual. "
            "El de un particular puede ser anual o bianual. "
            "Segmentar antes de actuar: instaladores inactivos 60 días = urgente; "
            "particulares inactivos 60 días = normal si no hay temporada."
        ),
        "sql": (
            "SELECT C.NOMBRE, C.TELEFONO, C.EMAIL, "
            "COUNT(D.CODIGO) AS COMPRAS_HISTORICAS, "
            "MAX(D.FECHA) AS ULTIMA_COMPRA, "
            "CAST(julianday('now')-julianday(MAX(D.FECHA)) AS INTEGER) AS DIAS_INACTIVO, "
            "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO "
            "FROM CLIENTE C JOIN DOCCAB D ON D.CODCLIENTE=C.CODIGO AND D.TIPO=13 "
            "GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO, C.EMAIL "
            "HAVING COMPRAS_HISTORICAS >= 2 AND DIAS_INACTIVO > 30 "
            "ORDER BY COMPRAS_HISTORICAS DESC, DIAS_INACTIVO DESC LIMIT 20"
        ),
        "dept": [Dept.VENTAS, Dept.MARKETING],
        "rol": [Rol.COMERCIAL, Rol.GERENTE],
        "tipo": Tipo.PREDICCION,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Churn Prediction",
        "accion": "Llamar esta semana. Ofrecer revisión gratuita o descuento especial de reactivación.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 4 — COMPRAS / KPI Y PROVEEDORES
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "c_kpi_top10_proveedores",
        "title": "Top 10 Proveedores por Volumen de Compra",
        "desc": "Proveedores con mayor volumen de pedidos. Identifica dependencias de suministro.",
        "desc_simple": (
            "¿A quién le compramos más? "
            "Si dependemos mucho de un solo proveedor y ese proveedor tiene problemas, "
            "nosotros también los tendremos. Hay que diversificar."
        ),
        "desc_tecnica": (
            "JOIN ARTICULO-PROVEED agrupando por proveedor. "
            "Nota: esta consulta usa el catálogo de artículos, no pedidos de compra directos, "
            "porque TIPO=12 (pedidos de compra) puede no estar bien registrado en todos los sistemas. "
            "Para un análisis más preciso, cruzar con DOCCAB TIPO=12. "
            "Concentración de proveedores > 40% en uno solo es riesgo de suministro. "
            "Estrategia: mantener al menos 2 proveedores alternativos para cada familia de producto clave."
        ),
        "sql": (
            "SELECT P.NOMBRE, COUNT(A.CODIGO) AS N_ARTICULOS, "
            "ROUND(AVG(A.PRECIO),2) AS PRECIO_MEDIO "
            "FROM ARTICULO A JOIN PROVEED P ON P.CODIGO=A.CODPROVEEDOR "
            "GROUP BY P.CODIGO, P.NOMBRE ORDER BY N_ARTICULOS DESC LIMIT 10"
        ),
        "dept": [Dept.COMPRAS, Dept.DIRECCION],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Concentración de Proveedores",
        "accion": "Si un proveedor > 40% del catálogo, buscar alternativas para reducir dependencia.",
    },
    {
        "id": "c_kpi_articulos_sin_proveedor",
        "title": "Artículos sin Proveedor Asignado",
        "desc": "Artículos del catálogo sin proveedor definido. Riesgo de rotura de stock.",
        "desc_simple": (
            "¿Hay productos en nuestro catálogo que no sabemos de dónde comprarlos? "
            "Si un artículo no tiene proveedor asignado y se agota, "
            "no sabremos a quién llamar para reponer el stock."
        ),
        "desc_tecnica": (
            "ARTICULO con CODPROVEEDOR=0 o NULL. "
            "En JDDC, CODPROVEEDOR=0 es el valor por defecto cuando no se ha asignado proveedor. "
            "Artículos sin proveedor son un problema operativo: "
            "si se venden y se agotan, no hay forma de reponerlos sistemáticamente. "
            "Acción: revisar cada artículo sin proveedor y asignar el proveedor correcto. "
            "Si no se conoce el proveedor, el artículo debería marcarse como descatalogado."
        ),
        "sql": (
            "SELECT CODIGO, NOMBRE, PRECIO, STOCKARTICULO "
            "FROM ARTICULO WHERE CODPROVEEDOR=0 OR CODPROVEEDOR IS NULL "
            "ORDER BY STOCKARTICULO ASC LIMIT 20"
        ),
        "dept": [Dept.COMPRAS, Dept.ALMACEN],
        "rol": [Rol.GERENTE, Rol.ALMACENERO],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Artículos sin Proveedor",
        "accion": "Asignar proveedor a cada artículo. Sin proveedor no se puede reponer el stock.",
    },
    {
        "id": "c_kpi_catalogo_por_proveedor",
        "title": "Catálogo de Artículos por Proveedor",
        "desc": "Número de referencias que suministra cada proveedor.",
        "desc_simple": (
            "¿Cuántos productos diferentes nos suministra cada proveedor? "
            "Un proveedor con muchas referencias es más importante para nosotros. "
            "Si ese proveedor falla, afecta a más productos."
        ),
        "desc_tecnica": (
            "LEFT JOIN PROVEED-ARTICULO agrupando por proveedor. "
            "Proveedores con pocas referencias (1-2 artículos) son candidatos a consolidar: "
            "puede ser más eficiente comprar esos artículos a un proveedor que ya tenemos. "
            "Proveedores con muchas referencias pero precios altos son candidatos a renegociar. "
            "El precio mínimo y máximo por proveedor indica el rango de su catálogo."
        ),
        "sql": (
            "SELECT P.NOMBRE AS PROVEEDOR, COUNT(A.CODIGO) AS N_REFERENCIAS, "
            "ROUND(MIN(A.PRECIO),2) AS PRECIO_MIN, ROUND(MAX(A.PRECIO),2) AS PRECIO_MAX "
            "FROM PROVEED P LEFT JOIN ARTICULO A ON A.CODPROVEEDOR=P.CODIGO "
            "GROUP BY P.CODIGO, P.NOMBRE ORDER BY N_REFERENCIAS DESC"
        ),
        "dept": [Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.OPERACIONAL,
        "urgencia": Urgencia.BAJO,
        "kpi": "Amplitud de Catálogo por Proveedor",
        "accion": "Proveedores con pocas referencias son candidatos a consolidar o eliminar.",
    },
    {
        "id": "c_riesgo_proveedor_unico",
        "title": "Artículos con Stock Bajo y Proveedor Único",
        "desc": "Artículos con poco stock que solo tiene un proveedor. Si falla, no hay alternativa.",
        "desc_simple": (
            "¿Hay productos que casi se nos acaban y solo podemos comprarlos a un proveedor? "
            "Si ese proveedor tiene un problema (huelga, quiebra, rotura de stock), "
            "no podremos servir a nuestros clientes."
        ),
        "desc_tecnica": (
            "ARTICULO con STOCKARTICULO < 5 y proveedor asignado. "
            "La combinación de stock bajo + proveedor único es el mayor riesgo de suministro. "
            "Medidas de mitigación: "
            "1) Aumentar el stock de seguridad de estos artículos. "
            "2) Buscar proveedor alternativo aunque sea más caro. "
            "3) Establecer acuerdo de suministro preferente con el proveedor actual. "
            "4) Considerar fabricación propia si el volumen lo justifica."
        ),
        "sql": (
            "SELECT A.NOMBRE, P.NOMBRE AS PROVEEDOR, A.STOCKARTICULO AS STOCK, A.PRECIO "
            "FROM ARTICULO A JOIN PROVEED P ON P.CODIGO=A.CODPROVEEDOR "
            "WHERE A.STOCKARTICULO < 5 "
            "ORDER BY A.STOCKARTICULO ASC LIMIT 20"
        ),
        "dept": [Dept.COMPRAS, Dept.ALMACEN],
        "rol": [Rol.GERENTE, Rol.ALMACENERO],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Riesgo de Suministro",
        "accion": "Buscar proveedor alternativo. Aumentar stock de seguridad de estos artículos.",
    },
    {
        "id": "c_opt_negociacion_volumen",
        "title": "Artículos con Mayor Rotación (Candidatos a Negociar Volumen)",
        "desc": "Los artículos más vendidos son los mejores candidatos para negociar descuentos por volumen.",
        "desc_simple": (
            "¿Qué productos vendemos tanto que podríamos pedir un descuento al proveedor? "
            "Si compramos mucho de algo, el proveedor debería darnos mejor precio. "
            "Esto puede ahorrar mucho dinero."
        ),
        "desc_tecnica": (
            "JOIN DOCLIN-ARTICULO-PROVEED-DOCCAB agrupando por artículo. "
            "Los artículos con mayor rotación son los candidatos ideales para negociar rappel o "
            "descuento por volumen con el proveedor. "
            "Regla general: si compramos > 50 unidades/año de un artículo, "
            "podemos negociar un descuento del 5-15%. "
            "El ahorro potencial = unidades anuales × precio actual × % descuento negociado. "
            "Preparar datos de volumen antes de la reunión con el proveedor."
        ),
        "sql": (
            "SELECT A.NOMBRE, P.NOMBRE AS PROVEEDOR, "
            "SUM(L.CANTIDAD) AS TOTAL_VENDIDO, "
            "ROUND(SUM(L.IMPORTE),2) AS IMPORTE_TOTAL, "
            "A.PRECIO AS PRECIO_ACTUAL "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "JOIN PROVEED P ON P.CODIGO=A.CODPROVEEDOR "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "GROUP BY A.CODIGO, A.NOMBRE, P.NOMBRE, A.PRECIO "
            "ORDER BY TOTAL_VENDIDO DESC LIMIT 15"
        ),
        "dept": [Dept.COMPRAS, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.DIRECTOR],
        "tipo": Tipo.AHORRO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Potencial de Ahorro en Compras",
        "accion": "Negociar rappel o descuento por volumen con el proveedor de cada artículo top.",
    },
    {
        "id": "c_kpi_proveedores_activos",
        "title": "Total de Proveedores Activos",
        "desc": "Número de proveedores con artículos en el catálogo. Diversidad de suministro.",
        "desc_simple": (
            "¿A cuántos proveedores distintos compramos? "
            "Tener muchos proveedores da flexibilidad, pero también complica la gestión. "
            "Lo ideal es tener suficientes para no depender de ninguno, pero no tantos que sea inmanejable."
        ),
        "desc_tecnica": (
            "COUNT de PROVEED con artículos asociados. "
            "El número óptimo de proveedores depende del tamaño de la empresa. "
            "Para JDDC: 5-15 proveedores principales es un rango manejable. "
            "Más de 20 proveedores activos puede indicar falta de política de compras centralizada. "
            "Consolidar proveedores reduce: tiempo de gestión, costes de transporte, "
            "complejidad administrativa y mejora el poder de negociación."
        ),
        "sql": (
            "SELECT COUNT(DISTINCT P.CODIGO) AS PROVEEDORES_ACTIVOS, "
            "COUNT(DISTINCT A.CODIGO) AS ARTICULOS_CON_PROVEEDOR, "
            "ROUND(AVG(A.PRECIO),2) AS PRECIO_MEDIO_CATALOGO "
            "FROM PROVEED P JOIN ARTICULO A ON A.CODPROVEEDOR=P.CODIGO"
        ),
        "dept": [Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.BAJO,
        "kpi": "Diversidad de Proveedores",
        "accion": "Revisar si hay proveedores redundantes que se puedan consolidar.",
    },
    {
        "id": "c_kpi_articulos_precio_alto",
        "title": "Artículos de Mayor Precio en Catálogo",
        "desc": "Los artículos más caros del catálogo. Requieren mayor control de stock y ventas.",
        "desc_simple": (
            "¿Cuáles son los productos más caros que vendemos? "
            "Los productos caros necesitan más atención: hay que asegurarse de que están bien "
            "almacenados, que el precio está actualizado y que los comerciales los conocen bien."
        ),
        "desc_tecnica": (
            "ORDER BY PRECIO DESC en ARTICULO. "
            "Los artículos de alto precio (equipos de climatización industrial, VRF, etc.) "
            "requieren gestión especial: "
            "1) Verificar que el precio está actualizado (los equipos suben de precio frecuentemente). "
            "2) Asegurar que el stock está asegurado (robo, daños). "
            "3) Formar al equipo comercial en argumentación de valor. "
            "4) Considerar financiación para el cliente en artículos > 3.000€."
        ),
        "sql": (
            "SELECT A.NOMBRE, F.NOMBRE AS FAMILIA, P.NOMBRE AS PROVEEDOR, "
            "A.PRECIO, A.STOCKARTICULO "
            "FROM ARTICULO A "
            "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
            "LEFT JOIN PROVEED P ON P.CODIGO=A.CODPROVEEDOR "
            "WHERE A.PRECIO > 0 "
            "ORDER BY A.PRECIO DESC LIMIT 20"
        ),
        "dept": [Dept.COMPRAS, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Artículos de Alto Valor",
        "accion": "Verificar precios actualizados y stock asegurado para artículos de alto valor.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 5 — ALMACÉN / KPI Y STOCK
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "a_kpi_valor_stock_total",
        "title": "Valor Total del Stock en Almacén",
        "desc": "Inversión total inmovilizada en stock. KPI financiero clave del almacén.",
        "desc_simple": (
            "¿Cuánto dinero tenemos metido en el almacén? "
            "El stock es dinero que no podemos usar para otra cosa. "
            "Hay que tener suficiente para servir a los clientes, pero no tanto que sea un desperdicio."
        ),
        "desc_tecnica": (
            "SUM(STOCKARTICULO * PRECIO) en ARTICULO. "
            "El valor del stock es capital inmovilizado que tiene un coste financiero. "
            "Regla general: el stock no debería superar 2-3 meses de ventas. "
            "Si el valor del stock es mayor que 3 meses de facturación, hay sobrestock. "
            "En climatización, el stock óptimo varía por temporada: "
            "aumentar en Q1-Q2 para preparar el verano, reducir en Q4."
        ),
        "sql": (
            "SELECT COUNT(*) AS N_REFERENCIAS, "
            "ROUND(SUM(STOCKARTICULO),2) AS UNIDADES_TOTALES, "
            "ROUND(SUM(STOCKARTICULO*PRECIO),2) AS VALOR_STOCK_TOTAL "
            "FROM ARTICULO WHERE STOCKARTICULO > 0"
        ),
        "dept": [Dept.ALMACEN, Dept.FINANZAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.ALMACENERO],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Valor de Inventario",
        "accion": "Comparar con ventas mensuales. Ratio stock/ventas > 3 meses indica sobrestock.",
    },
    {
        "id": "a_kpi_articulos_sin_stock",
        "title": "Artículos sin Stock (Rotura)",
        "desc": "Artículos con stock = 0 o negativo. Riesgo de no poder servir pedidos.",
        "desc_simple": (
            "¿Qué productos se nos han agotado? "
            "Si un cliente pide algo que no tenemos, puede que se vaya a la competencia. "
            "Hay que reponer estos artículos lo antes posible."
        ),
        "desc_tecnica": (
            "ARTICULO con STOCKARTICULO <= 0. "
            "Stock negativo puede indicar error de registro o ventas sin actualizar el stock. "
            "Priorizar la reposición según la rotación histórica: "
            "artículos que se venden mucho y están a 0 son urgentes. "
            "Artículos que nunca se venden y están a 0 pueden eliminarse del catálogo. "
            "Proceso de reposición: verificar punto de pedido, emitir orden de compra, "
            "confirmar fecha de entrega con proveedor."
        ),
        "sql": (
            "SELECT A.NOMBRE, F.NOMBRE AS FAMILIA, A.PRECIO, A.STOCKARTICULO "
            "FROM ARTICULO A LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
            "WHERE A.STOCKARTICULO <= 0 ORDER BY A.NOMBRE LIMIT 30"
        ),
        "dept": [Dept.ALMACEN, Dept.COMPRAS, Dept.VENTAS],
        "rol": [Rol.ALMACENERO, Rol.GERENTE],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Roturas de Stock",
        "accion": "Lanzar pedido de reposición inmediata. Avisar a comerciales para no vender lo que no hay.",
    },
    {
        "id": "a_kpi_stock_bajo_minimo",
        "title": "Artículos con Stock Bajo (< 3 unidades)",
        "desc": "Artículos con stock crítico que pueden causar rotura en breve.",
        "desc_simple": (
            "¿Qué productos están a punto de agotarse? "
            "Con menos de 3 unidades, cualquier venta puede dejarnos sin stock. "
            "Hay que pedir más antes de que se acaben."
        ),
        "desc_tecnica": (
            "ARTICULO con STOCKARTICULO BETWEEN 1 AND 2. "
            "El punto de pedido óptimo depende del plazo de entrega del proveedor y la demanda diaria. "
            "Fórmula básica: Punto de pedido = Demanda diaria × Plazo de entrega (días) + Stock de seguridad. "
            "Para JDDC con proveedores locales (1-3 días): punto de pedido = 3-5 unidades. "
            "Para proveedores con plazo largo (7-14 días): punto de pedido = 10-15 unidades. "
            "Implementar alertas automáticas cuando el stock baje del punto de pedido."
        ),
        "sql": (
            "SELECT A.NOMBRE, F.NOMBRE AS FAMILIA, P.NOMBRE AS PROVEEDOR, "
            "A.STOCKARTICULO AS STOCK, A.PRECIO "
            "FROM ARTICULO A "
            "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
            "LEFT JOIN PROVEED P ON P.CODIGO=A.CODPROVEEDOR "
            "WHERE A.STOCKARTICULO > 0 AND A.STOCKARTICULO < 3 "
            "ORDER BY A.STOCKARTICULO ASC LIMIT 25"
        ),
        "dept": [Dept.ALMACEN, Dept.COMPRAS],
        "rol": [Rol.ALMACENERO, Rol.GERENTE],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Stock Crítico",
        "accion": "Emitir pedido de reposición. Establecer punto de pedido automático.",
    },
    {
        "id": "a_kpi_stock_por_familia",
        "title": "Stock por Familia de Producto",
        "desc": "Distribución del inventario por familia. Identifica familias sobredimensionadas.",
        "desc_simple": (
            "¿Cómo está repartido nuestro stock entre los diferentes tipos de productos? "
            "Si tenemos demasiado stock de un tipo y poco de otro, "
            "hay que reequilibrar las compras."
        ),
        "desc_tecnica": (
            "JOIN ARTICULO-FAMILIA agrupando por familia. "
            "El valor del stock por familia permite identificar desequilibrios: "
            "familias con alto valor y baja rotación = sobrestock. "
            "familias con bajo valor y alta rotación = posible infrastock. "
            "En climatización, las familias de mayor valor suelen ser: "
            "equipos split, sistemas VRF, calderas. "
            "Las de mayor rotación: gas refrigerante, filtros, consumibles."
        ),
        "sql": (
            "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, COUNT(A.CODIGO) AS N_REFERENCIAS, "
            "ROUND(SUM(A.STOCKARTICULO),2) AS UNIDADES, "
            "ROUND(SUM(A.STOCKARTICULO*A.PRECIO),2) AS VALOR "
            "FROM ARTICULO A LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
            "GROUP BY F.CODIGO, F.NOMBRE ORDER BY VALOR DESC"
        ),
        "dept": [Dept.ALMACEN, Dept.COMPRAS, Dept.FINANZAS],
        "rol": [Rol.GERENTE, Rol.ALMACENERO],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Distribución de Inventario",
        "accion": "Familias con alto valor y baja rotación son candidatas a reducir stock.",
    },
    {
        "id": "a_kpi_rotacion_stock",
        "title": "Rotación de Stock por Artículo",
        "desc": "Cuántas veces se vende el stock de cada artículo. Mide la eficiencia del inventario.",
        "desc_simple": (
            "¿Cuántas veces 'damos la vuelta' al stock de cada producto? "
            "Un producto que se vende y repone 12 veces al año tiene una rotación de 12. "
            "Cuanto mayor sea la rotación, más eficiente es el uso del dinero invertido en stock."
        ),
        "desc_tecnica": (
            "Rotación = total vendido / stock actual. "
            "Rotación > 12 = excelente (se vende más de una vez al mes). "
            "Rotación 6-12 = buena. "
            "Rotación 1-6 = aceptable. "
            "Rotación < 1 = el stock tarda más de un año en venderse = candidato a liquidar. "
            "En climatización, los consumibles (gas, filtros) deberían tener rotación > 12. "
            "Los equipos grandes pueden tener rotación 2-4 y ser rentables igualmente."
        ),
        "sql": (
            "SELECT A.NOMBRE, A.STOCKARTICULO AS STOCK_ACTUAL, "
            "COALESCE(SUM(L.CANTIDAD),0) AS TOTAL_VENDIDO, "
            "CASE WHEN A.STOCKARTICULO > 0 THEN ROUND(COALESCE(SUM(L.CANTIDAD),0)/A.STOCKARTICULO,2) ELSE 0 END AS ROTACION "
            "FROM ARTICULO A "
            "LEFT JOIN DOCLIN L ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO "
            "HAVING A.STOCKARTICULO > 0 "
            "ORDER BY ROTACION DESC LIMIT 20"
        ),
        "dept": [Dept.ALMACEN, Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.ALMACENERO],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Rotación de Inventario",
        "accion": "Artículos con rotación < 1 son candidatos a liquidar o devolver al proveedor.",
    },
    {
        "id": "a_riesgo_stock_muerto",
        "title": "Stock Muerto (sin ventas en 90 días)",
        "desc": "Artículos con stock pero sin ventas recientes. Capital inmovilizado sin retorno.",
        "desc_simple": (
            "¿Tenemos productos en el almacén que nadie compra? "
            "Ese stock ocupa espacio y tiene un coste financiero. "
            "Hay que liquidarlo con descuento o devolverlo al proveedor."
        ),
        "desc_tecnica": (
            "ARTICULO con stock > 0 y sin ventas en los últimos 90 días. "
            "El coste real del stock muerto incluye: "
            "1) Coste financiero (dinero inmovilizado al 5-8% anual). "
            "2) Coste de almacenamiento (espacio, seguros). "
            "3) Riesgo de obsolescencia (equipos que se descatalogan). "
            "Estrategia de liquidación: "
            "- Descuento del 20-30% para clientes habituales. "
            "- Incluir en presupuestos como 'oferta especial'. "
            "- Devolución al proveedor si el contrato lo permite. "
            "- Venta a instaladores de la zona a precio de coste."
        ),
        "sql": (
            "SELECT A.NOMBRE, A.STOCKARTICULO AS STOCK, A.PRECIO, "
            "ROUND(A.STOCKARTICULO*A.PRECIO,2) AS VALOR_INMOVILIZADO "
            "FROM ARTICULO A "
            "WHERE A.STOCKARTICULO > 0 "
            "AND A.CODIGO NOT IN ("
            "SELECT DISTINCT CAST(L.CODART AS INTEGER) FROM DOCLIN L "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "WHERE D.FECHA >= date('now','-90 days')) "
            "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 20"
        ),
        "dept": [Dept.ALMACEN, Dept.FINANZAS],
        "rol": [Rol.GERENTE, Rol.ALMACENERO],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Stock Muerto",
        "accion": "Liquidar con descuento o devolver al proveedor. Liberar capital para productos activos.",
    },
    {
        "id": "a_ahorro_reduccion_sobrestock",
        "title": "Ahorro Potencial por Reducción de Sobrestock",
        "desc": "Artículos con stock muy superior a la demanda. Oportunidad de reducir inversión.",
        "desc_simple": (
            "¿Tenemos demasiado stock de algunos productos? "
            "Si tenemos 50 unidades de algo que vendemos 5 al mes, "
            "tenemos 10 meses de stock. Eso es demasiado dinero parado."
        ),
        "desc_tecnica": (
            "Compara stock actual con ventas de los últimos 90 días para estimar el exceso. "
            "Exceso estimado = stock actual - (ventas 90 días × 2). "
            "El factor 2 da un margen de seguridad de 2 períodos. "
            "El valor del exceso = exceso estimado × precio de venta. "
            "Reducir el sobrestock libera capital que puede invertirse en: "
            "marketing, nuevas líneas de producto, mejora de instalaciones, "
            "o simplemente reducir la deuda financiera."
        ),
        "sql": (
            "SELECT A.NOMBRE, A.STOCKARTICULO AS STOCK, "
            "COALESCE(SUM(L.CANTIDAD),0) AS VENDIDO_90D, "
            "CASE WHEN COALESCE(SUM(L.CANTIDAD),0) > 0 "
            "THEN ROUND(A.STOCKARTICULO - COALESCE(SUM(L.CANTIDAD),0)*2, 2) "
            "ELSE A.STOCKARTICULO END AS EXCESO_ESTIMADO, "
            "ROUND((CASE WHEN COALESCE(SUM(L.CANTIDAD),0) > 0 "
            "THEN A.STOCKARTICULO - COALESCE(SUM(L.CANTIDAD),0)*2 "
            "ELSE A.STOCKARTICULO END)*A.PRECIO, 2) AS VALOR_EXCESO "
            "FROM ARTICULO A "
            "LEFT JOIN DOCLIN L ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "LEFT JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "AND D.FECHA >= date('now','-90 days') "
            "GROUP BY A.CODIGO, A.NOMBRE, A.STOCKARTICULO, A.PRECIO "
            "HAVING EXCESO_ESTIMADO > 0 AND A.STOCKARTICULO > 5 "
            "ORDER BY VALOR_EXCESO DESC LIMIT 15"
        ),
        "dept": [Dept.ALMACEN, Dept.FINANZAS, Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.DIRECTOR],
        "tipo": Tipo.AHORRO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Capital Inmovilizado en Exceso",
        "accion": "Reducir pedidos de estos artículos. Negociar devolución con proveedor.",
    },
    {
        "id": "a_movimientos_stock_recientes",
        "title": "Últimos Movimientos de Stock",
        "desc": "Entradas y salidas de almacén más recientes. Control operacional diario.",
        "desc_simple": (
            "¿Qué ha entrado y salido del almacén últimamente? "
            "Este registro permite controlar que todo el movimiento de mercancía "
            "está correctamente documentado."
        ),
        "desc_tecnica": (
            "SELECT de ESTALMACEN ordenado por FECHA DESC. "
            "ESTALMACEN registra los movimientos de stock: entradas (compras, devoluciones) "
            "y salidas (ventas, consumo en SAT). "
            "Cada movimiento debería tener un documento asociado (factura, albarán, SAT). "
            "Movimientos sin documento asociado pueden indicar errores de registro o "
            "movimientos no autorizados. "
            "Control recomendado: revisar diariamente los últimos 30 movimientos."
        ),
        "sql": (
            "SELECT E.FECHA, A.NOMBRE AS ARTICULO, E.CANTIDAD, E.COSTE, E.VENTA "
            "FROM ESTALMACEN E JOIN ARTICULO A ON A.CODIGO=E.CODART "
            "ORDER BY E.FECHA DESC LIMIT 30"
        ),
        "dept": [Dept.ALMACEN],
        "rol": [Rol.ALMACENERO, Rol.GERENTE],
        "tipo": Tipo.OPERACIONAL,
        "urgencia": Urgencia.BAJO,
        "kpi": "Actividad de Almacén",
        "accion": "Verificar que todos los movimientos están justificados con documentos.",
    },
    {
        "id": "a_kpi_articulos_mas_vendidos",
        "title": "Top 20 Artículos Más Vendidos (Unidades)",
        "desc": "Los artículos con mayor número de unidades vendidas. Core del negocio.",
        "desc_simple": (
            "¿Qué productos vendemos más en cantidad? "
            "Estos son los productos que más necesitamos tener siempre en stock. "
            "Si se agotan, perdemos ventas seguras."
        ),
        "desc_tecnica": (
            "SUM(CANTIDAD) en DOCLIN agrupando por artículo, filtrando TIPO=13. "
            "Los artículos más vendidos en unidades no siempre son los más rentables. "
            "Cruzar con el margen para identificar los que más contribuyen al beneficio. "
            "En climatización, los artículos de mayor volumen suelen ser consumibles: "
            "gas refrigerante, filtros, correas, condensadores pequeños. "
            "Garantizar disponibilidad permanente de estos artículos es crítico."
        ),
        "sql": (
            "SELECT A.NOMBRE, SUM(L.CANTIDAD) AS TOTAL_UNIDADES, "
            "ROUND(SUM(L.IMPORTE),2) AS TOTAL_IMPORTE, "
            "ROUND(AVG(L.PRECIO),2) AS PRECIO_MEDIO_VENTA "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "GROUP BY A.CODIGO, A.NOMBRE "
            "ORDER BY TOTAL_UNIDADES DESC LIMIT 20"
        ),
        "dept": [Dept.ALMACEN, Dept.VENTAS, Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.ALMACENERO, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Artículos de Mayor Rotación",
        "accion": "Garantizar stock permanente. Negociar precio por volumen con el proveedor.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 6 — FINANZAS / KPI Y TESORERÍA
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "f_kpi_saldo_caja",
        "title": "Saldo Actual de Caja",
        "desc": "Balance de entradas y salidas de caja. Liquidez disponible.",
        "desc_simple": (
            "¿Cuánto dinero tenemos disponible ahora mismo? "
            "El saldo de caja es el dinero real que podemos usar hoy. "
            "Si es negativo, hay un problema serio de liquidez."
        ),
        "desc_tecnica": (
            "SUM condicional de CAJA: TIPO=1 (entradas/cobros) vs TIPO=2 (salidas/pagos). "
            "El saldo de caja es diferente del beneficio: "
            "puedes tener beneficio contable pero saldo de caja negativo si no cobras a tiempo. "
            "Saldo negativo = necesidad de financiación urgente (línea de crédito, factoring). "
            "Saldo muy alto = dinero ocioso que podría invertirse. "
            "Objetivo: mantener un saldo mínimo de 2 meses de gastos fijos."
        ),
        "sql": (
            "SELECT "
            "ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE 0 END),2) AS ENTRADAS, "
            "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTE ELSE 0 END),2) AS SALIDAS, "
            "ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE -IMPORTE END),2) AS SALDO_NETO "
            "FROM CAJA"
        ),
        "dept": [Dept.FINANZAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Saldo de Caja",
        "accion": "Saldo negativo requiere acción inmediata: cobrar facturas pendientes o línea de crédito.",
    },
    {
        "id": "f_kpi_cobros_mes",
        "title": "Cobros del Mes Actual",
        "desc": "Total cobrado en el mes en curso. Mide la eficiencia de cobro.",
        "desc_simple": (
            "¿Cuánto dinero hemos cobrado este mes? "
            "No es lo mismo facturar que cobrar. "
            "Si facturamos mucho pero cobramos poco, tenemos un problema de liquidez."
        ),
        "desc_tecnica": (
            "SUM(IMPORTE) en CAJA TIPO=1 del mes actual. "
            "La diferencia entre facturación y cobros del mes es el saldo pendiente de cobro. "
            "Ratio de cobro = cobros / facturación. Objetivo: > 85%. "
            "Un ratio bajo indica problemas con los plazos de pago de los clientes. "
            "Soluciones: domiciliación bancaria, descuento por pronto pago, "
            "factoring (vender las facturas a un banco para cobrar inmediatamente)."
        ),
        "sql": (
            "SELECT COUNT(*) AS N_COBROS, ROUND(SUM(IMPORTE),2) AS TOTAL_COBRADO "
            "FROM CAJA WHERE TIPO=1 AND FECHA >= date('now','start of month')"
        ),
        "dept": [Dept.FINANZAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Cobros del Mes",
        "accion": "Comparar con facturación del mes. Diferencia = pendiente de cobro.",
    },
    {
        "id": "f_kpi_pagos_mes",
        "title": "Pagos del Mes Actual",
        "desc": "Total pagado a proveedores y gastos en el mes en curso.",
        "desc_simple": (
            "¿Cuánto hemos pagado este mes? "
            "Controlar los pagos es tan importante como controlar los cobros. "
            "Si pagamos más de lo que cobramos, el saldo de caja baja."
        ),
        "desc_tecnica": (
            "SUM(IMPORTE) en CAJA TIPO=2 del mes actual. "
            "Los pagos incluyen: proveedores, nóminas, alquileres, impuestos, seguros. "
            "Comparar pagos vs cobros del mes para calcular el flujo de caja neto. "
            "Flujo neto positivo = el negocio genera caja. "
            "Flujo neto negativo durante 3+ meses consecutivos = problema estructural. "
            "Revisar si hay pagos que se pueden diferir o renegociar con proveedores."
        ),
        "sql": (
            "SELECT COUNT(*) AS N_PAGOS, ROUND(SUM(IMPORTE),2) AS TOTAL_PAGADO "
            "FROM CAJA WHERE TIPO=2 AND FECHA >= date('now','start of month')"
        ),
        "dept": [Dept.FINANZAS, Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Pagos del Mes",
        "accion": "Verificar que los pagos corresponden a facturas de proveedor recibidas.",
    },
    {
        "id": "f_kpi_margen_bruto_estimado",
        "title": "Margen Bruto Estimado por Producto",
        "desc": "Diferencia entre precio de venta y coste. Identifica los productos más rentables.",
        "desc_simple": (
            "¿Cuánto ganamos realmente con cada producto? "
            "Si vendemos algo a 100€ pero nos cuesta 90€, solo ganamos 10€. "
            "Hay que potenciar los productos con mayor margen."
        ),
        "desc_tecnica": (
            "JOIN ARTICULO-ESTALMACEN calculando margen = (PVP - coste) / PVP. "
            "El margen bruto no incluye gastos generales (personal, alquiler, etc.). "
            "Para calcular el margen neto habría que restar los gastos fijos. "
            "En climatización, el margen bruto objetivo por tipo de trabajo: "
            "Equipos: 15-25%. Instalación: 35-50%. Mantenimiento: 50-70%. Repuestos: 30-50%. "
            "Productos con margen < 10% son candidatos a subir precio o eliminar del catálogo."
        ),
        "sql": (
            "SELECT A.NOMBRE, A.PRECIO AS PVP, "
            "ROUND(AVG(E.COSTE),2) AS COSTE_MEDIO, "
            "ROUND(A.PRECIO - AVG(E.COSTE),2) AS MARGEN_BRUTO, "
            "ROUND((A.PRECIO - AVG(E.COSTE))*100.0/NULLIF(A.PRECIO,0),1) AS MARGEN_PCT "
            "FROM ARTICULO A "
            "JOIN ESTALMACEN E ON E.CODART=A.CODIGO "
            "WHERE E.COSTE > 0 AND A.PRECIO > 0 "
            "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIO "
            "ORDER BY MARGEN_PCT DESC LIMIT 20"
        ),
        "dept": [Dept.FINANZAS, Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Margen Bruto",
        "accion": "Potenciar ventas de productos con mayor margen. Revisar precios de los de margen < 20%.",
    },
    {
        "id": "f_kpi_evolucion_caja_mensual",
        "title": "Evolución de Caja por Mes",
        "desc": "Entradas y salidas de caja mes a mes. Detecta meses de tensión de liquidez.",
        "desc_simple": (
            "¿Cómo ha evolucionado el dinero en caja mes a mes? "
            "Si hay meses en los que siempre gastamos más de lo que ingresamos, "
            "hay que prepararse con antelación para esos meses."
        ),
        "desc_tecnica": (
            "Agrupación mensual de CAJA por tipo (entradas/salidas). "
            "El análisis de estacionalidad de caja es diferente al de ventas: "
            "puede haber meses con alta facturación pero baja caja si los clientes pagan a 60 días. "
            "Meses con saldo negativo recurrente indican necesidad de línea de crédito estacional. "
            "Planificación de tesorería: proyectar los próximos 3 meses con los datos históricos "
            "para anticipar necesidades de financiación."
        ),
        "sql": (
            "SELECT CAST(strftime('%Y',FECHA) AS INTEGER) AS ANIO, "
            "CAST(strftime('%m',FECHA) AS INTEGER) AS MES, "
            "ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE 0 END),2) AS ENTRADAS, "
            "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTE ELSE 0 END),2) AS SALIDAS, "
            "ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE -IMPORTE END),2) AS SALDO_MES "
            "FROM CAJA GROUP BY ANIO, MES ORDER BY ANIO DESC, MES DESC LIMIT 12"
        ),
        "dept": [Dept.FINANZAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.FINANCIERO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Flujo de Caja Mensual",
        "accion": "Meses con saldo negativo requieren planificación de tesorería anticipada.",
    },
    {
        "id": "f_riesgo_facturas_alto_importe_sin_cobrar",
        "title": "Riesgo: Facturas de Alto Importe Pendientes de Cobro",
        "desc": "Facturas de más de 3.000€ emitidas hace más de 30 días. Riesgo de impago.",
        "desc_simple": (
            "¿Hay facturas grandes que llevan mucho tiempo sin cobrarse? "
            "Una factura de 5.000€ sin cobrar durante 2 meses es un problema serio. "
            "Hay que actuar antes de que sea demasiado tarde."
        ),
        "desc_tecnica": (
            "DOCCAB TIPO=13 con IMPORTETOTAL > 3000 y FECHA < 30 días. "
            "El umbral de 3.000€ es configurable. "
            "Factores de riesgo adicionales: cliente nuevo, sector en crisis, historial de pagos tardíos. "
            "Herramientas de gestión del riesgo de crédito: "
            "1) Informe de solvencia (Informa, Axesor) antes de trabajos > 5.000€. "
            "2) Seguro de crédito (Cesce, Atradius) para cartera > 50.000€. "
            "3) Factoring sin recurso para eliminar el riesgo de impago."
        ),
        "sql": (
            "SELECT D.FECHA, C.NOMBRE, C.TELEFONO, ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
            "CAST(julianday('now')-julianday(D.FECHA) AS INTEGER) AS DIAS_EMITIDA "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=13 AND D.IMPORTETOTAL > 3000 "
            "AND D.FECHA < date('now','-30 days') "
            "ORDER BY IMPORTE DESC LIMIT 15"
        ),
        "dept": [Dept.FINANZAS, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Exposición al Impago",
        "accion": "Llamar al cliente. Si no responde, iniciar proceso de reclamación.",
    },
    {
        "id": "f_ahorro_descuentos_excesivos",
        "title": "Ahorro: Líneas con Descuento Excesivo (>20%)",
        "desc": "Líneas de factura con descuento superior al 20%. Posible pérdida de margen.",
        "desc_simple": (
            "¿Estamos dando demasiados descuentos? "
            "Un descuento del 25% en una venta de 1.000€ significa que dejamos de ganar 250€. "
            "Hay que controlar quién da descuentos y de cuánto."
        ),
        "desc_tecnica": (
            "DOCLIN con DESCUENTO > 20 en facturas TIPO=13. "
            "Los descuentos excesivos son uno de los principales destructores de margen. "
            "Política de descuentos recomendada: "
            "Comercial: máximo 10%. Gerente: hasta 20%. Director: hasta 30%. "
            "Descuentos > 30% requieren justificación escrita. "
            "Analizar si los descuentos se concentran en ciertos comerciales o clientes. "
            "Un comercial que da muchos descuentos puede estar compensando falta de argumentación de valor."
        ),
        "sql": (
            "SELECT A.NOMBRE, L.DESCUENTO, L.PRECIO, L.IMPORTE, "
            "ROUND(L.PRECIO*L.CANTIDAD,2) AS SIN_DESCUENTO, "
            "ROUND(L.PRECIO*L.CANTIDAD - L.IMPORTE,2) AS DESCUENTO_APLICADO "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "WHERE L.DESCUENTO > 20 "
            "ORDER BY DESCUENTO_APLICADO DESC LIMIT 20"
        ),
        "dept": [Dept.FINANZAS, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.DIRECTOR],
        "tipo": Tipo.AHORRO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Pérdida por Descuentos",
        "accion": "Revisar política de descuentos. Establecer límite máximo por rol comercial.",
    },
    {
        "id": "f_kpi_ratio_cobros_pagos",
        "title": "Ratio Cobros vs Pagos (Salud Financiera)",
        "desc": "Compara lo que cobramos con lo que pagamos. Indica la salud del flujo de caja.",
        "desc_simple": (
            "¿Cobramos más de lo que pagamos? "
            "Si cobramos 10.000€ y pagamos 8.000€, el ratio es 1.25 (positivo). "
            "Si cobramos menos de lo que pagamos, hay un problema."
        ),
        "desc_tecnica": (
            "Ratio = total entradas / total salidas en CAJA. "
            "Ratio > 1.2 = excelente salud financiera. "
            "Ratio 1.0-1.2 = aceptable, poco margen. "
            "Ratio < 1.0 = la empresa consume más caja de la que genera = insostenible a largo plazo. "
            "Este ratio es diferente al margen de beneficio porque incluye el timing de cobros y pagos. "
            "Una empresa puede tener beneficio contable pero ratio < 1 si cobra tarde y paga pronto."
        ),
        "sql": (
            "SELECT "
            "ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE 0 END),2) AS TOTAL_COBROS, "
            "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTE ELSE 0 END),2) AS TOTAL_PAGOS, "
            "ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE 0 END) / "
            "NULLIF(SUM(CASE WHEN TIPO=2 THEN IMPORTE ELSE 0 END),0), 2) AS RATIO_COBROS_PAGOS "
            "FROM CAJA"
        ),
        "dept": [Dept.FINANZAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.CRITICO,
        "kpi": "Ratio de Liquidez",
        "accion": "Ratio < 1 requiere acción urgente: acelerar cobros o diferir pagos.",
    },
    {
        "id": "f_kpi_movimientos_caja_recientes",
        "title": "Últimos Movimientos de Caja",
        "desc": "Los 30 últimos movimientos de caja. Control operacional diario.",
        "desc_simple": (
            "¿Qué ha entrado y salido de caja últimamente? "
            "Revisar los últimos movimientos permite detectar errores o movimientos no autorizados."
        ),
        "desc_tecnica": (
            "SELECT de CAJA ordenado por FECHA DESC. "
            "Control de caja diario: verificar que cada movimiento tiene justificante. "
            "Movimientos sin referencia de documento son sospechosos. "
            "En JDDC, los movimientos de caja deberían corresponder a: "
            "cobros de facturas, pagos a proveedores, gastos de empresa. "
            "Cualquier movimiento > 1.000€ sin referencia debe investigarse."
        ),
        "sql": (
            "SELECT FECHA, TIPO, ROUND(IMPORTE,2) AS IMPORTE, CONCEPTO "
            "FROM CAJA ORDER BY FECHA DESC, ROWID DESC LIMIT 30"
        ),
        "dept": [Dept.FINANZAS],
        "rol": [Rol.ADMIN, Rol.GERENTE],
        "tipo": Tipo.OPERACIONAL,
        "urgencia": Urgencia.BAJO,
        "kpi": "Control de Caja",
        "accion": "Verificar que cada movimiento tiene justificante. Investigar movimientos sin referencia.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 7 — SAT / SERVICIO TÉCNICO
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "s_kpi_sats_mes",
        "title": "SATs del Mes Actual",
        "desc": "Número y valor de órdenes de servicio técnico en el mes en curso.",
        "desc_simple": (
            "¿Cuántos trabajos de servicio técnico hemos hecho este mes? "
            "El SAT (Servicio de Asistencia Técnica) es una fuente importante de ingresos. "
            "Más SATs = más trabajo para los técnicos y más ingresos recurrentes."
        ),
        "desc_tecnica": (
            "COUNT y SUM de DOCCAB TIPO=2 del mes actual. "
            "El SAT en climatización incluye: reparaciones, mantenimientos preventivos, "
            "revisiones de garantía, instalaciones de gas. "
            "Un aumento de SATs puede indicar: "
            "a) Crecimiento del negocio (más clientes con equipos). "
            "b) Problemas de calidad (equipos que se averían más). "
            "c) Estacionalidad (más averías en verano por uso intensivo). "
            "Monitorizar la tendencia mensual para distinguir entre estos casos."
        ),
        "sql": (
            "SELECT COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS FACTURADO_SAT, "
            "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO_SAT "
            "FROM DOCCAB WHERE TIPO=2 AND FECHA >= date('now','start of month')"
        ),
        "dept": [Dept.SAT, Dept.VENTAS],
        "rol": [Rol.GERENTE, Rol.TECNICO],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Actividad SAT",
        "accion": "Comparar con mes anterior. Aumento de SATs puede indicar problemas de calidad.",
    },
    {
        "id": "s_kpi_clientes_con_mas_sats",
        "title": "Clientes con Más SATs (Posible Problema de Calidad)",
        "desc": "Clientes que más veces han requerido servicio técnico. Indica problemas recurrentes.",
        "desc_simple": (
            "¿Hay clientes que siempre están llamando para que les arreglemos algo? "
            "Si un cliente tiene muchos SATs, puede que la instalación que le hicimos "
            "no fue de buena calidad, o que el equipo que le vendimos tiene problemas."
        ),
        "desc_tecnica": (
            "JOIN DOCCAB-CLIENTE agrupando por cliente, filtrando TIPO=2. "
            "Un cliente con > 3 SATs en el mismo equipo puede indicar: "
            "1) Instalación defectuosa (revisar el trabajo original). "
            "2) Equipo de baja calidad (considerar sustitución). "
            "3) Uso inadecuado por parte del cliente (formación necesaria). "
            "4) Condiciones ambientales adversas (polvo, humedad, sal marina). "
            "Visita de diagnóstico completo recomendada para clientes con > 3 SATs/año."
        ),
        "sql": (
            "SELECT C.NOMBRE, C.TELEFONO, COUNT(D.CODIGO) AS N_SATS, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS COSTE_TOTAL_SAT "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=2 GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO "
            "ORDER BY N_SATS DESC LIMIT 15"
        ),
        "dept": [Dept.SAT, Dept.CALIDAD],
        "rol": [Rol.GERENTE, Rol.TECNICO],
        "tipo": Tipo.CALIDAD,
        "urgencia": Urgencia.ALTO,
        "kpi": "Recurrencia de Averías",
        "accion": "Visitar al cliente para diagnóstico completo. Puede indicar instalación defectuosa.",
    },
    {
        "id": "s_kpi_sats_por_mes",
        "title": "Evolución Mensual de SATs",
        "desc": "Tendencia de órdenes de servicio técnico mes a mes.",
        "desc_simple": (
            "¿Cómo ha evolucionado el número de reparaciones y mantenimientos mes a mes? "
            "Ver la tendencia ayuda a planificar cuántos técnicos necesitamos en cada época."
        ),
        "desc_tecnica": (
            "Agrupación mensual de DOCCAB TIPO=2. "
            "Patrón estacional esperado en climatización: "
            "Pico en junio-agosto (averías por calor, uso intensivo de AC). "
            "Segundo pico en noviembre-diciembre (calefacción). "
            "Valle en enero-febrero y septiembre-octubre. "
            "Si el patrón se desvía significativamente, investigar causas. "
            "Planificación de personal: contratar técnico temporal en los meses pico."
        ),
        "sql": (
            "SELECT CAST(strftime('%Y',FECHA) AS INTEGER) AS ANIO, "
            "CAST(strftime('%m',FECHA) AS INTEGER) AS MES, "
            "COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=2 "
            "GROUP BY ANIO, MES ORDER BY ANIO DESC, MES DESC LIMIT 12"
        ),
        "dept": [Dept.SAT, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.TECNICO],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Tendencia SAT",
        "accion": "Pico de SATs en verano es normal (climatización). Pico en invierno puede indicar problema.",
    },
    {
        "id": "s_riesgo_sats_sin_facturar",
        "title": "SATs Realizados sin Facturar",
        "desc": "Órdenes de servicio técnico completadas pero sin factura emitida.",
        "desc_simple": (
            "¿Hay trabajos de reparación que hemos hecho pero no hemos cobrado? "
            "Cada SAT sin facturar es trabajo gratis. "
            "Hay que facturar todos los SATs el mismo día o al día siguiente."
        ),
        "desc_tecnica": (
            "COUNT de DOCCAB TIPO=2 con ESTADO=0. "
            "En JDDC, ESTADO=0 puede significar 'pendiente' o 'sin facturar' según la configuración. "
            "El proceso correcto: SAT realizado → parte de trabajo firmado → factura emitida. "
            "SATs sin facturar > 48h son un problema de proceso. "
            "Implementar: alerta automática al administrativo cuando un SAT lleva > 24h sin facturar. "
            "Objetivo: 0 SATs sin facturar al final de cada día."
        ),
        "sql": (
            "SELECT COUNT(*) AS N_SATS_PENDIENTES, ROUND(SUM(IMPORTETOTAL),2) AS IMPORTE_PENDIENTE "
            "FROM DOCCAB WHERE TIPO=2 AND ESTADO=0"
        ),
        "dept": [Dept.SAT, Dept.FINANZAS],
        "rol": [Rol.GERENTE, Rol.ADMIN],
        "tipo": Tipo.RIESGO,
        "urgencia": Urgencia.CRITICO,
        "kpi": "SATs sin Facturar",
        "accion": "Facturar inmediatamente. Cada SAT sin facturar es trabajo no cobrado.",
    },
    {
        "id": "s_opt_productos_mas_usados_en_sat",
        "title": "Productos Más Usados en SATs",
        "desc": "Artículos que más se consumen en reparaciones. Optimiza el stock del técnico.",
        "desc_simple": (
            "¿Qué piezas y materiales usamos más en las reparaciones? "
            "Si sabemos qué se usa más, podemos asegurarnos de que los técnicos "
            "siempre llevan esas piezas en la furgoneta."
        ),
        "desc_tecnica": (
            "JOIN DOCLIN-ARTICULO-DOCCAB filtrando TIPO=2. "
            "El stock del vehículo del técnico debe incluir los 10-15 artículos más usados en SAT. "
            "Beneficios: "
            "1) Resolver la avería en la primera visita (first-time fix rate). "
            "2) Reducir desplazamientos al almacén. "
            "3) Mejorar la satisfacción del cliente. "
            "KPI objetivo: first-time fix rate > 80% (resolver en la primera visita)."
        ),
        "sql": (
            "SELECT A.NOMBRE, SUM(L.CANTIDAD) AS TOTAL_USADO, "
            "ROUND(SUM(L.IMPORTE),2) AS COSTE_TOTAL "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=2 "
            "GROUP BY A.CODIGO, A.NOMBRE "
            "ORDER BY TOTAL_USADO DESC LIMIT 15"
        ),
        "dept": [Dept.SAT, Dept.ALMACEN],
        "rol": [Rol.TECNICO, Rol.ALMACENERO],
        "tipo": Tipo.OPTIMIZACION,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Consumo en SAT",
        "accion": "Mantener stock mínimo garantizado de estos artículos en el vehículo del técnico.",
    },
    {
        "id": "s_kpi_sats_abiertos_antiguos",
        "title": "SATs Abiertos con Más de 5 Días",
        "desc": "Órdenes de servicio técnico que llevan más de 5 días sin cerrarse.",
        "desc_simple": (
            "¿Hay reparaciones que llevan demasiado tiempo sin resolverse? "
            "Un cliente que lleva una semana sin que le arreglen el aire acondicionado "
            "en verano está muy enfadado. Hay que priorizar estos casos."
        ),
        "desc_tecnica": (
            "DOCCAB TIPO=2 ESTADO=0 con FECHA < 5 días. "
            "SATs abiertos > 5 días pueden indicar: "
            "1) Espera de pieza de repuesto (comunicar al cliente). "
            "2) Problema técnico complejo (escalar a técnico senior). "
            "3) Falta de seguimiento (problema de gestión). "
            "SLA recomendado: SATs urgentes resueltos en 24h, normales en 72h, programados en 7 días. "
            "Comunicar proactivamente al cliente si hay retraso."
        ),
        "sql": (
            "SELECT D.FECHA, C.NOMBRE, C.TELEFONO, ROUND(D.IMPORTETOTAL,2) AS IMPORTE, "
            "CAST(julianday('now')-julianday(D.FECHA) AS INTEGER) AS DIAS_ABIERTO "
            "FROM DOCCAB D JOIN CLIENTE C ON C.CODIGO=D.CODCLIENTE "
            "WHERE D.TIPO=2 AND D.ESTADO=0 AND D.FECHA < date('now','-5 days') "
            "ORDER BY DIAS_ABIERTO DESC LIMIT 20"
        ),
        "dept": [Dept.SAT],
        "rol": [Rol.TECNICO, Rol.GERENTE],
        "tipo": Tipo.ALERTA,
        "urgencia": Urgencia.CRITICO,
        "kpi": "SATs Vencidos",
        "accion": "Contactar al cliente hoy. Dar fecha concreta de resolución.",
    },
    {
        "id": "s_kpi_facturacion_sat_vs_instalacion",
        "title": "Comparativa: Facturación SAT vs Instalación",
        "desc": "Qué porcentaje de la facturación viene de reparaciones vs instalaciones nuevas.",
        "desc_simple": (
            "¿Ganamos más con reparaciones o con instalaciones nuevas? "
            "Un negocio sano debería tener un buen equilibrio entre ambos. "
            "Demasiadas reparaciones puede indicar que no captamos clientes nuevos."
        ),
        "desc_tecnica": (
            "Comparativa TIPO=2 (SAT) vs TIPO=13 (facturas de instalación/venta). "
            "En una empresa de climatización madura, el mix ideal es: "
            "60-70% instalaciones nuevas + 30-40% mantenimiento y reparaciones. "
            "Un mix con > 50% SATs indica que la empresa está en modo 'mantenimiento' "
            "y no está creciendo con nuevas instalaciones. "
            "Estrategia de crecimiento: aumentar la proporción de instalaciones nuevas "
            "mediante captación activa de clientes."
        ),
        "sql": (
            "SELECT "
            "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS FACTURACION_VENTAS, "
            "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTETOTAL ELSE 0 END),2) AS FACTURACION_SAT, "
            "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTETOTAL ELSE 0 END)*100.0/"
            "NULLIF(SUM(IMPORTETOTAL),0),1) AS PCT_SAT "
            "FROM DOCCAB WHERE TIPO IN (2,13)"
        ),
        "dept": [Dept.SAT, Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.ESTRATEGICO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Mix SAT vs Instalación",
        "accion": "Si SAT > 40% de facturación, activar plan de captación de nuevas instalaciones.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 8 — PRODUCTOS / CATÁLOGO Y RENTABILIDAD
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "p_kpi_top10_productos_importe",
        "title": "Top 10 Productos por Importe Vendido",
        "desc": "Los 10 artículos que más ingresos generan. Core del negocio.",
        "desc_simple": (
            "¿Qué productos nos dan más dinero? "
            "Estos son los productos más importantes para el negocio. "
            "Hay que asegurarse de que siempre están disponibles y bien promocionados."
        ),
        "desc_tecnica": (
            "JOIN DOCLIN-ARTICULO-DOCCAB agrupando por artículo, filtrando TIPO=13. "
            "Los productos estrella (top 10 por importe) suelen representar el 70-80% de la facturación. "
            "Estrategia de gestión: "
            "1) Stock permanente garantizado. "
            "2) Precio competitivo revisado trimestralmente. "
            "3) Formación del equipo en argumentación de venta. "
            "4) Incluir en todas las campañas de marketing. "
            "5) Negociar condiciones especiales con el proveedor."
        ),
        "sql": (
            "SELECT A.NOMBRE, SUM(L.CANTIDAD) AS TOTAL_CANT, "
            "ROUND(SUM(L.IMPORTE),2) AS TOTAL_IMP, "
            "ROUND(SUM(L.IMPORTE)*100.0/(SELECT SUM(IMPORTE) FROM DOCLIN),1) AS PCT_VENTAS "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY TOTAL_IMP DESC LIMIT 10"
        ),
        "dept": [Dept.VENTAS, Dept.COMPRAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Productos Estrella",
        "accion": "Garantizar disponibilidad permanente. Son el motor de ingresos.",
    },
    {
        "id": "p_kpi_productos_sin_ventas",
        "title": "Productos sin Ninguna Venta",
        "desc": "Artículos del catálogo que nunca se han vendido. Candidatos a eliminar.",
        "desc_simple": (
            "¿Hay productos en nuestro catálogo que nunca hemos vendido? "
            "Si un producto lleva meses en el catálogo sin venderse, "
            "ocupa espacio en el almacén y complica la gestión. Hay que eliminarlo."
        ),
        "desc_tecnica": (
            "ARTICULO no presente en DOCLIN. "
            "Artículos sin ventas pueden ser: "
            "1) Productos nuevos que aún no se han promocionado. "
            "2) Productos obsoletos que nadie pide. "
            "3) Artículos de catálogo que se venden bajo demanda. "
            "Acción diferenciada: "
            "- Si tiene stock: liquidar o devolver al proveedor. "
            "- Si no tiene stock: eliminar del catálogo. "
            "- Si es nuevo: dar 3 meses de plazo antes de decidir."
        ),
        "sql": (
            "SELECT A.NOMBRE, A.PRECIO, A.STOCKARTICULO, COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA "
            "FROM ARTICULO A LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
            "WHERE A.CODIGO NOT IN (SELECT DISTINCT CAST(CODART AS INTEGER) FROM DOCLIN) "
            "ORDER BY A.PRECIO DESC LIMIT 20"
        ),
        "dept": [Dept.VENTAS, Dept.COMPRAS, Dept.ALMACEN],
        "rol": [Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.OPTIMIZACION,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Artículos Muertos",
        "accion": "Revisar si son necesarios. Si no, eliminar del catálogo y liquidar stock.",
    },
    {
        "id": "p_kpi_catalogo_por_familia",
        "title": "Catálogo por Familia de Producto",
        "desc": "Número de referencias y valor medio por familia. Estructura del catálogo.",
        "desc_simple": (
            "¿Cómo está organizado nuestro catálogo de productos? "
            "Ver cuántos productos tenemos de cada tipo nos ayuda a saber "
            "si el catálogo está bien equilibrado."
        ),
        "desc_tecnica": (
            "LEFT JOIN FAMILIA-ARTICULO agrupando por familia. "
            "Un catálogo bien estructurado tiene: "
            "- Familias principales con 10-30 referencias (equipos, instalación). "
            "- Familias de consumibles con 20-50 referencias (gas, filtros, accesorios). "
            "- Familias de repuestos con 50-100 referencias. "
            "Familias con < 3 referencias son candidatas a consolidar con otras. "
            "El precio medio por familia indica el posicionamiento de precio."
        ),
        "sql": (
            "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, COUNT(A.CODIGO) AS N_REFERENCIAS, "
            "ROUND(AVG(A.PRECIO),2) AS PRECIO_MEDIO, "
            "ROUND(MIN(A.PRECIO),2) AS PRECIO_MIN, ROUND(MAX(A.PRECIO),2) AS PRECIO_MAX "
            "FROM FAMILIA F LEFT JOIN ARTICULO A ON A.CODFAMILIA=F.CODIGO "
            "GROUP BY F.CODIGO, F.NOMBRE ORDER BY N_REFERENCIAS DESC"
        ),
        "dept": [Dept.VENTAS, Dept.COMPRAS],
        "rol": [Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.OPERACIONAL,
        "urgencia": Urgencia.BAJO,
        "kpi": "Amplitud de Catálogo",
        "accion": "Familias con pocas referencias pueden necesitar ampliación o consolidación.",
    },
    {
        "id": "p_analisis_abc_productos",
        "title": "Análisis ABC de Productos (Pareto)",
        "desc": "Clasifica productos en A (top 20% que genera 80% ventas), B y C. Priorización.",
        "desc_simple": (
            "¿Cuáles son los productos más importantes para el negocio? "
            "El principio de Pareto dice que el 20% de los productos genera el 80% de las ventas. "
            "Los productos A son los más importantes y merecen más atención."
        ),
        "desc_tecnica": (
            "Ranking de productos por importe vendido con porcentaje acumulado. "
            "Clasificación ABC: "
            "A = productos que acumulan el 80% de las ventas (normalmente 15-20% del catálogo). "
            "B = productos que acumulan del 80% al 95% (30-40% del catálogo). "
            "C = el resto (40-50% del catálogo, solo 5% de las ventas). "
            "Política de gestión: "
            "A: stock permanente, revisión semanal, proveedor alternativo. "
            "B: stock normal, revisión mensual. "
            "C: bajo pedido, sin stock o mínimo."
        ),
        "sql": (
            "SELECT A.NOMBRE, ROUND(SUM(L.IMPORTE),2) AS TOTAL_VENTAS, "
            "ROUND(SUM(L.IMPORTE)*100.0/(SELECT SUM(IMPORTE) FROM DOCLIN "
            "JOIN DOCCAB D2 ON D2.CODIGO=DOCLIN.CODIGO AND D2.TIPO=13),1) AS PCT "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY TOTAL_VENTAS DESC LIMIT 30"
        ),
        "dept": [Dept.VENTAS, Dept.COMPRAS, Dept.ALMACEN],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.ESTRATEGICO,
        "urgencia": Urgencia.ALTO,
        "kpi": "Análisis ABC",
        "accion": "Productos A: máxima disponibilidad. B: stock normal. C: bajo pedido.",
    },
    {
        "id": "p_kpi_productos_mayor_margen",
        "title": "Productos con Mayor Margen Bruto",
        "desc": "Los artículos más rentables. Potenciar su venta mejora el beneficio.",
        "desc_simple": (
            "¿Qué productos nos dejan más dinero por cada venta? "
            "No siempre los que más vendemos son los más rentables. "
            "Hay que potenciar los que tienen mejor margen."
        ),
        "desc_tecnica": (
            "JOIN ARTICULO-ESTALMACEN calculando margen = (PVP - coste) / PVP, ordenado DESC. "
            "Los productos de mayor margen suelen ser: servicios, consumibles, repuestos. "
            "Los de menor margen: equipos grandes (mucho precio pero poco margen %). "
            "Estrategia de mix de ventas: intentar incluir siempre en cada presupuesto "
            "al menos un producto de alto margen (mantenimiento, garantía extendida, accesorios). "
            "Un presupuesto de equipo + instalación + mantenimiento tiene mejor margen total "
            "que solo el equipo."
        ),
        "sql": (
            "SELECT A.NOMBRE, A.PRECIO AS PVP, "
            "ROUND(AVG(E.COSTE),2) AS COSTE_MEDIO, "
            "ROUND((A.PRECIO - AVG(E.COSTE))*100.0/NULLIF(A.PRECIO,0),1) AS MARGEN_PCT "
            "FROM ARTICULO A "
            "JOIN ESTALMACEN E ON E.CODART=A.CODIGO "
            "WHERE E.COSTE > 0 AND A.PRECIO > 0 "
            "GROUP BY A.CODIGO, A.NOMBRE, A.PRECIO "
            "HAVING MARGEN_PCT > 0 "
            "ORDER BY MARGEN_PCT DESC LIMIT 15"
        ),
        "dept": [Dept.VENTAS, Dept.FINANZAS],
        "rol": [Rol.GERENTE, Rol.COMERCIAL],
        "tipo": Tipo.KPI,
        "urgencia": Urgencia.ALTO,
        "kpi": "Productos de Mayor Rentabilidad",
        "accion": "Incluir siempre estos productos en los presupuestos. Formarles al equipo comercial.",
    },
    {
        "id": "p_kpi_familias_mas_vendidas",
        "title": "Familias de Producto Más Vendidas",
        "desc": "Qué categorías de producto generan más ventas. Estructura del negocio.",
        "desc_simple": (
            "¿Qué tipo de productos vendemos más? ¿Equipos, repuestos, servicios? "
            "Saber qué categorías son las más importantes nos ayuda a decidir "
            "en qué invertir más."
        ),
        "desc_tecnica": (
            "JOIN DOCLIN-ARTICULO-FAMILIA-DOCCAB agrupando por familia. "
            "La distribución de ventas por familia revela el modelo de negocio: "
            "Si equipos > 60%: negocio de instalación, dependiente de nuevos proyectos. "
            "Si servicios > 40%: negocio de mantenimiento, más recurrente y estable. "
            "Objetivo estratégico: aumentar el peso de servicios/mantenimiento "
            "para tener ingresos más predecibles y recurrentes."
        ),
        "sql": (
            "SELECT COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA, "
            "COUNT(DISTINCT D.CODIGO) AS N_FACTURAS, "
            "SUM(L.CANTIDAD) AS TOTAL_UNIDADES, "
            "ROUND(SUM(L.IMPORTE),2) AS TOTAL_IMPORTE "
            "FROM DOCLIN L "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER)=A.CODIGO "
            "LEFT JOIN FAMILIA F ON F.CODIGO=A.CODFAMILIA "
            "JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "GROUP BY F.CODIGO, F.NOMBRE "
            "ORDER BY TOTAL_IMPORTE DESC LIMIT 15"
        ),
        "dept": [Dept.VENTAS, Dept.DIRECCION],
        "rol": [Rol.DIRECTOR, Rol.GERENTE],
        "tipo": Tipo.ESTRATEGICO,
        "urgencia": Urgencia.MEDIO,
        "kpi": "Mix de Familias",
        "accion": "Aumentar el peso de familias de alto margen (servicios, mantenimiento).",
    },


    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 9 — DIRECCIÓN / KPI GLOBALES Y ESTRATÉGICOS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "d_kpi_resumen_ejecutivo",
        "title": "Resumen Ejecutivo del Negocio",
        "desc": "Los 10 KPIs más importantes en una sola vista.",
        "desc_simple": (
            "Un cuadro de mando con los 10 números más importantes del negocio: "
            "cuánto hemos facturado, cuántos clientes tenemos, cuántos pedidos hay "
            "pendientes, cuánto debemos a proveedores y cuánto nos deben los clientes. "
            "Ideal para la reunión de dirección del lunes."
        ),
        "desc_tecnica": (
            "Consulta multi-KPI con subconsultas escalares que agrega: "
            "facturación total del ejercicio (DOCCAB TIPO=13), número de clientes activos, "
            "pedidos pendientes de servir (TIPO=1 sin albarán), saldo vivo de cobros "
            "(COBROS pendientes) y saldo de pagos (PAGOS pendientes). "
            "Diseñada para el dashboard ejecutivo de JDDC Climatización."
        ),
        "sql": (
            "SELECT 'Facturación total' AS INDICADOR, CAST(ROUND(SUM(IMPORTETOTAL),2) AS TEXT) AS VALOR FROM DOCCAB WHERE TIPO=13 "
            "UNION ALL SELECT 'Clientes activos', CAST(COUNT(DISTINCT CODCLIENTE) AS TEXT) FROM DOCCAB WHERE TIPO=13 "
            "UNION ALL SELECT 'Presupuestos abiertos', CAST(COUNT(*) AS TEXT) FROM DOCCAB WHERE TIPO=0 "
            "UNION ALL SELECT 'Albaranes pendientes', CAST(COUNT(*) AS TEXT) FROM DOCCAB WHERE TIPO=11 "
            "UNION ALL SELECT 'SATs abiertos', CAST(COUNT(*) AS TEXT) FROM DOCCAB WHERE TIPO=2 AND ESTADO=0 "
            "UNION ALL SELECT 'Saldo caja', CAST(ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE -IMPORTE END),2) AS TEXT) FROM CAJA "
            "UNION ALL SELECT 'Artículos sin stock', CAST(COUNT(*) AS TEXT) FROM ARTICULO WHERE STOCKARTICULO <= 0 "
            "UNION ALL SELECT 'Artículos stock bajo', CAST(COUNT(*) AS TEXT) FROM ARTICULO WHERE STOCKARTICULO > 0 AND STOCKARTICULO < 3 "
            "UNION ALL SELECT 'Valor stock total', CAST(ROUND(SUM(STOCKARTICULO*PRECIO),2) AS TEXT) FROM ARTICULO WHERE STOCKARTICULO > 0 "
            "UNION ALL SELECT 'Total clientes', CAST(COUNT(*) AS TEXT) FROM CLIENTE"
        ),
        "dept": ["Dirección", "Todos"],
        "rol": ["Director", "Gerente"],
        "tipo": "KPI",
        "urgencia": "Alto",
        "kpi": "Resumen Ejecutivo",
        "accion": "Revisar semanalmente en reunión de dirección.",
    },

    {
        "id": "d_evolucion_mensual",
        "title": "Evolución Mensual de Facturación",
        "desc": "Facturación mes a mes del año en curso.",
        "desc_simple": (
            "Muestra cuánto hemos facturado cada mes de este año. "
            "Permite ver si estamos creciendo, si hay meses flojos o si hay estacionalidad. "
            "Muy útil para comparar con el año anterior."
        ),
        "desc_tecnica": (
            "Agrupación por mes (strftime) sobre DOCCAB TIPO=13 del ejercicio actual. "
            "Incluye número de facturas, importe total y ticket medio por mes. "
            "Permite detectar estacionalidad y planificar recursos en JDDC Climatización."
        ),
        "sql": (
            "SELECT strftime('%Y-%m', FECHA) AS MES, "
            "COUNT(*) AS N_FACTURAS, "
            "ROUND(SUM(IMPORTETOTAL),2) AS FACTURACION, "
            "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO "
            "FROM DOCCAB WHERE TIPO=13 "
            "AND strftime('%Y', FECHA) = strftime('%Y', 'now') "
            "GROUP BY MES ORDER BY MES"
        ),
        "dept": ["Dirección", "Ventas", "Finanzas"],
        "rol": ["Director", "Gerente", "Comercial"],
        "tipo": "KPI",
        "urgencia": "Alto",
        "kpi": "Evolución Mensual",
        "accion": "Comparar con mismo período año anterior para detectar tendencias.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 10 — FINANZAS / COBROS Y PAGOS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "f_saldo_clientes_vencido",
        "title": "Saldo Vencido por Cliente",
        "desc": "Clientes con deuda vencida ordenados por importe.",
        "desc_simple": (
            "Lista de clientes que nos deben dinero y ya ha pasado la fecha de pago. "
            "Ordenado de mayor a menor deuda. "
            "Imprescindible para el departamento de cobros: saber a quién llamar primero."
        ),
        "desc_tecnica": (
            "Consulta sobre tabla COBROS (o equivalente de efectos a cobrar) filtrando "
            "registros con FECHAVENCIMIENTO < date('now') y COBRADO=0. "
            "JOIN con CLIENTE para obtener nombre y teléfono de contacto. "
            "Crítico para la gestión de tesorería de JDDC Climatización."
        ),
        "sql": (
            "SELECT C.NOMBRE AS CLIENTE, C.TELEFONO, "
            "COUNT(*) AS N_EFECTOS, "
            "ROUND(SUM(E.IMPORTE),2) AS DEUDA_VENCIDA "
            "FROM EFECTOSCOBRO E "
            "JOIN CLIENTE C ON C.CODIGO = E.CODCLIENTE "
            "WHERE E.FECHAVENCIMIENTO < date('now') AND E.COBRADO = 0 "
            "GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO "
            "ORDER BY DEUDA_VENCIDA DESC LIMIT 20"
        ),
        "dept": ["Finanzas", "Dirección"],
        "rol": ["Director", "Gerente", "Administrativo"],
        "tipo": "Riesgo",
        "urgencia": "Crítico",
        "kpi": "Deuda Vencida Clientes",
        "accion": "Contactar inmediatamente con los 5 primeros clientes de la lista.",
    },

    {
        "id": "f_pagos_proximos",
        "title": "Pagos a Proveedores Próximos 30 Días",
        "desc": "Pagos pendientes a proveedores en los próximos 30 días.",
        "desc_simple": (
            "Muestra cuánto dinero tenemos que pagar a proveedores en el próximo mes. "
            "Esencial para planificar la tesorería y asegurarse de tener liquidez suficiente. "
            "Evita sorpresas y problemas de caja."
        ),
        "desc_tecnica": (
            "Consulta sobre EFECTOSPAGO filtrando FECHAVENCIMIENTO entre hoy y +30 días, "
            "PAGADO=0. JOIN con PROVEEDOR para nombre. "
            "Agrupado por proveedor y semana de vencimiento para planificación de tesorería "
            "en JDDC Climatización."
        ),
        "sql": (
            "SELECT P.NOMBRE AS PROVEEDOR, "
            "E.FECHAVENCIMIENTO, "
            "ROUND(SUM(E.IMPORTE),2) AS IMPORTE_PAGAR "
            "FROM EFECTOSPAGO E "
            "JOIN PROVEEDOR P ON P.CODIGO = E.CODPROVEEDOR "
            "WHERE E.FECHAVENCIMIENTO BETWEEN date('now') AND date('now', '+30 days') "
            "AND E.PAGADO = 0 "
            "GROUP BY P.CODIGO, P.NOMBRE, E.FECHAVENCIMIENTO "
            "ORDER BY E.FECHAVENCIMIENTO"
        ),
        "dept": ["Finanzas", "Compras"],
        "rol": ["Director", "Gerente", "Administrativo"],
        "tipo": "Operacional",
        "urgencia": "Alto",
        "kpi": "Pagos Próximos",
        "accion": "Verificar liquidez disponible y programar transferencias.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 11 — ALMACÉN / STOCK Y ROTACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "alm_stock_critico",
        "title": "Artículos con Stock Crítico",
        "desc": "Artículos por debajo del stock mínimo.",
        "desc_simple": (
            "Lista de productos que se están agotando: tienen menos unidades en almacén "
            "de las que deberían tener como mínimo. "
            "Hay que hacer pedido urgente para no quedarse sin stock y perder ventas."
        ),
        "desc_tecnica": (
            "Filtra ARTICULO donde STOCKACTUAL < STOCKMINIMO y STOCKMINIMO > 0. "
            "Incluye diferencia (gap) entre stock actual y mínimo, y proveedor habitual. "
            "JOIN con FAMILIA para clasificación. Crítico para evitar roturas de stock "
            "en JDDC Climatización."
        ),
        "sql": (
            "SELECT A.REFERENCIA, A.NOMBRE, "
            "A.STOCKACTUAL, A.STOCKMINIMO, "
            "(A.STOCKMINIMO - A.STOCKACTUAL) AS DEFICIT, "
            "COALESCE(F.NOMBRE, 'Sin familia') AS FAMILIA "
            "FROM ARTICULO A "
            "LEFT JOIN FAMILIA F ON F.CODIGO = A.CODFAMILIA "
            "WHERE A.STOCKACTUAL < A.STOCKMINIMO AND A.STOCKMINIMO > 0 "
            "ORDER BY DEFICIT DESC LIMIT 30"
        ),
        "dept": ["Almacén", "Compras"],
        "rol": ["Almacenero", "Gerente", "Administrativo"],
        "tipo": "Riesgo",
        "urgencia": "Crítico",
        "kpi": "Stock Crítico",
        "accion": "Generar pedido de reposición para los artículos con mayor déficit.",
    },

    {
        "id": "alm_rotacion_lenta",
        "title": "Artículos de Rotación Lenta (Posible Obsolescencia)",
        "desc": "Artículos con stock pero sin ventas en los últimos 6 meses.",
        "desc_simple": (
            "Productos que tenemos en almacén pero que nadie ha comprado en los últimos "
            "6 meses. Son artículos que ocupan espacio y tienen dinero inmovilizado. "
            "Hay que decidir si hacer una promoción o devolverlos al proveedor."
        ),
        "desc_tecnica": (
            "LEFT JOIN entre ARTICULO y DOCLIN (facturas TIPO=13 últimos 180 días). "
            "Filtra artículos con STOCKACTUAL > 0 y sin movimiento de venta reciente. "
            "Calcula valor inmovilizado (stock * precio coste). "
            "Permite identificar obsolescencia en el catálogo de JDDC Climatización."
        ),
        "sql": (
            "SELECT A.REFERENCIA, A.NOMBRE, A.STOCKACTUAL, "
            "ROUND(A.STOCKACTUAL * COALESCE(A.PRECIOCOSTE,0), 2) AS VALOR_INMOVILIZADO, "
            "COALESCE(F.NOMBRE,'Sin familia') AS FAMILIA "
            "FROM ARTICULO A "
            "LEFT JOIN FAMILIA F ON F.CODIGO = A.CODFAMILIA "
            "WHERE A.STOCKACTUAL > 0 "
            "AND A.CODIGO NOT IN ("
            "  SELECT DISTINCT CAST(L.CODART AS INTEGER) FROM DOCLIN L "
            "  JOIN DOCCAB D ON D.CODIGO=L.CODIGO AND D.TIPO=13 "
            "  WHERE D.FECHA >= date('now','-180 days')"
            ") "
            "ORDER BY VALOR_INMOVILIZADO DESC LIMIT 25"
        ),
        "dept": ["Almacén", "Compras", "Ventas"],
        "rol": ["Almacenero", "Gerente", "Director"],
        "tipo": "Optimización",
        "urgencia": "Medio",
        "kpi": "Rotación Lenta",
        "accion": "Evaluar liquidación, promoción o devolución a proveedor.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 12 — SAT / SERVICIO TÉCNICO
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "sat_partes_pendientes",
        "title": "Partes de Trabajo Pendientes de Facturar",
        "desc": "Partes de servicio técnico sin factura asociada.",
        "desc_simple": (
            "Lista de trabajos técnicos que ya se han realizado pero todavía no se han "
            "facturado al cliente. Cada día que pasa sin facturar es dinero que no entra. "
            "El SAT debe revisar esta lista diariamente."
        ),
        "desc_tecnica": (
            "Consulta sobre DOCCAB TIPO=6 (partes de trabajo) sin DOCCAB TIPO=13 asociado. "
            "JOIN con CLIENTE y EMPLEADO (técnico asignado). "
            "Calcula días transcurridos desde la fecha del parte. "
            "Crítico para el ciclo de facturación del SAT de JDDC Climatización."
        ),
        "sql": (
            "SELECT D.CODIGO AS PARTE, D.FECHA, "
            "C.NOMBRE AS CLIENTE, "
            "CAST(julianday('now') - julianday(D.FECHA) AS INTEGER) AS DIAS_SIN_FACTURAR, "
            "ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
            "FROM DOCCAB D "
            "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "WHERE D.TIPO = 6 "
            "AND D.CODIGO NOT IN (SELECT CODDOCREL FROM DOCCAB WHERE TIPO=13 AND CODDOCREL IS NOT NULL) "
            "ORDER BY DIAS_SIN_FACTURAR DESC LIMIT 30"
        ),
        "dept": ["SAT / Técnico", "Ventas"],
        "rol": ["Técnico", "Gerente", "Administrativo"],
        "tipo": "Operacional",
        "urgencia": "Alto",
        "kpi": "Partes Pendientes Facturar",
        "accion": "Facturar todos los partes con más de 7 días pendientes.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 13 — COMPRAS / PROVEEDORES
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "cmp_top_proveedores",
        "title": "Top 10 Proveedores por Volumen de Compra",
        "desc": "Proveedores más importantes por importe de compras.",
        "desc_simple": (
            "Los 10 proveedores a los que más les compramos. "
            "Conocer esta lista es clave para negociar mejores precios y condiciones, "
            "y para saber dónde tenemos más dependencia."
        ),
        "desc_tecnica": (
            "Agrupación sobre DOCCAB TIPO=20 (facturas de compra) por proveedor. "
            "JOIN con PROVEEDOR para nombre y condiciones. "
            "Incluye número de facturas y ticket medio de compra. "
            "Base para negociación de rappels en JDDC Climatización."
        ),
        "sql": (
            "SELECT P.NOMBRE AS PROVEEDOR, "
            "COUNT(D.CODIGO) AS N_FACTURAS, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_COMPRADO, "
            "ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO "
            "FROM DOCCAB D "
            "JOIN PROVEEDOR P ON P.CODIGO = D.CODPROVEEDOR "
            "WHERE D.TIPO = 20 "
            "GROUP BY P.CODIGO, P.NOMBRE "
            "ORDER BY TOTAL_COMPRADO DESC LIMIT 10"
        ),
        "dept": ["Compras", "Dirección"],
        "rol": ["Gerente", "Director", "Administrativo"],
        "tipo": "Estratégico",
        "urgencia": "Medio",
        "kpi": "Top Proveedores",
        "accion": "Negociar rappels con los 3 primeros proveedores.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 14 — ALERTAS AUTOMÁTICAS
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "alerta_clientes_inactivos",
        "title": "⚠️ Alerta: Clientes sin Compras en 90 Días",
        "desc": "Clientes activos que no han comprado en los últimos 3 meses.",
        "desc_simple": (
            "Clientes que antes compraban pero llevan 3 meses sin hacer ningún pedido. "
            "Pueden estar comprando a la competencia. "
            "El comercial debe contactarles para recuperarlos antes de que se pierdan."
        ),
        "desc_tecnica": (
            "LEFT JOIN entre CLIENTE (ACTIVO=1) y DOCCAB TIPO=13 últimos 90 días. "
            "Filtra clientes sin actividad reciente pero con historial de compras. "
            "Incluye última fecha de compra y total histórico para priorizar contacto. "
            "Alerta de churn para el equipo comercial de JDDC Climatización."
        ),
        "sql": (
            "SELECT C.NOMBRE, C.TELEFONO, C.EMAIL, "
            "MAX(D.FECHA) AS ULTIMA_COMPRA, "
            "CAST(julianday('now') - julianday(MAX(D.FECHA)) AS INTEGER) AS DIAS_INACTIVO, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL_HISTORICO "
            "FROM CLIENTE C "
            "JOIN DOCCAB D ON D.CODCLIENTE = C.CODIGO AND D.TIPO = 13 "
            "WHERE C.ACTIVO = 1 "
            "GROUP BY C.CODIGO, C.NOMBRE, C.TELEFONO, C.EMAIL "
            "HAVING MAX(D.FECHA) < date('now', '-90 days') "
            "ORDER BY TOTAL_HISTORICO DESC LIMIT 20"
        ),
        "dept": ["Ventas", "Marketing"],
        "rol": ["Comercial", "Gerente", "Director"],
        "tipo": "Alerta",
        "urgencia": "Alto",
        "kpi": "Clientes en Riesgo de Churn",
        "accion": "Llamar a los 10 primeros clientes esta semana con oferta personalizada.",
    },

    {
        "id": "alerta_margen_negativo",
        "title": "⚠️ Alerta: Facturas con Margen Negativo",
        "desc": "Facturas donde hemos vendido por debajo del coste.",
        "desc_simple": (
            "Facturas en las que hemos perdido dinero: hemos vendido más barato de lo que "
            "nos costó el producto. Puede ser un error de precio o un descuento excesivo. "
            "Hay que revisarlas y corregir la tarifa."
        ),
        "desc_tecnica": (
            "JOIN entre DOCLIN y ARTICULO comparando precio de venta con precio de coste. "
            "Filtra líneas donde PRECIO < PRECIOCOSTE (margen negativo). "
            "Agrupa por factura para ver el impacto total. "
            "Alerta crítica para el control de márgenes en JDDC Climatización."
        ),
        "sql": (
            "SELECT D.CODIGO AS FACTURA, D.FECHA, C.NOMBRE AS CLIENTE, "
            "ROUND(SUM(L.IMPORTE),2) AS IMPORTE_VENTA, "
            "ROUND(SUM(L.CANTIDAD * COALESCE(A.PRECIOCOSTE,0)),2) AS COSTE_TOTAL, "
            "ROUND(SUM(L.IMPORTE) - SUM(L.CANTIDAD * COALESCE(A.PRECIOCOSTE,0)),2) AS MARGEN "
            "FROM DOCCAB D "
            "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "JOIN DOCLIN L ON L.CODIGO = D.CODIGO "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER) = A.CODIGO "
            "WHERE D.TIPO = 13 AND D.FECHA >= date('now','-90 days') "
            "GROUP BY D.CODIGO, D.FECHA, C.NOMBRE "
            "HAVING MARGEN < 0 "
            "ORDER BY MARGEN ASC LIMIT 20"
        ),
        "dept": ["Ventas", "Finanzas", "Dirección"],
        "rol": ["Director", "Gerente", "Comercial"],
        "tipo": "Alerta",
        "urgencia": "Crítico",
        "kpi": "Margen Negativo",
        "accion": "Revisar tarifas y descuentos aplicados en estas facturas.",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE 15 — MODERNIZACIÓN / ANÁLISIS AVANZADO
    # ══════════════════════════════════════════════════════════════════════════

    {
        "id": "mod_segmentacion_rfm",
        "title": "Segmentación RFM de Clientes",
        "desc": "Clasificación de clientes por Recencia, Frecuencia y Valor Monetario.",
        "desc_simple": (
            "Clasifica a los clientes en grupos según cuándo compraron por última vez, "
            "con qué frecuencia compran y cuánto dinero gastan. "
            "Permite saber quiénes son los mejores clientes y quiénes están en riesgo. "
            "Base para campañas de marketing personalizadas."
        ),
        "desc_tecnica": (
            "Análisis RFM (Recency-Frequency-Monetary) sobre DOCCAB TIPO=13. "
            "Recencia: días desde última compra. Frecuencia: número de facturas. "
            "Monetario: importe total. Permite segmentar en Champions, Leales, "
            "En Riesgo y Perdidos para acciones de CRM en JDDC Climatización."
        ),
        "sql": (
            "SELECT C.NOMBRE, "
            "CAST(julianday('now') - julianday(MAX(D.FECHA)) AS INTEGER) AS RECENCIA_DIAS, "
            "COUNT(D.CODIGO) AS FRECUENCIA, "
            "ROUND(SUM(D.IMPORTETOTAL),2) AS MONETARIO, "
            "CASE "
            "  WHEN CAST(julianday('now') - julianday(MAX(D.FECHA)) AS INTEGER) <= 30 "
            "       AND COUNT(D.CODIGO) >= 5 THEN 'Champion' "
            "  WHEN CAST(julianday('now') - julianday(MAX(D.FECHA)) AS INTEGER) <= 90 "
            "       AND COUNT(D.CODIGO) >= 3 THEN 'Leal' "
            "  WHEN CAST(julianday('now') - julianday(MAX(D.FECHA)) AS INTEGER) <= 180 THEN 'En Riesgo' "
            "  ELSE 'Perdido' "
            "END AS SEGMENTO_RFM "
            "FROM DOCCAB D "
            "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "WHERE D.TIPO = 13 "
            "GROUP BY C.CODIGO, C.NOMBRE "
            "ORDER BY MONETARIO DESC LIMIT 50"
        ),
        "dept": ["Marketing", "Ventas", "Dirección"],
        "rol": ["Director", "Gerente", "Comercial"],
        "tipo": "Modernización",
        "urgencia": "Medio",
        "kpi": "Segmentación RFM",
        "accion": "Diseñar campañas específicas para cada segmento RFM.",
    },

    {
        "id": "mod_prediccion_demanda",
        "title": "Predicción de Demanda por Artículo (Tendencia 3 Meses)",
        "desc": "Proyección de ventas basada en tendencia de los últimos 6 meses.",
        "desc_simple": (
            "Estima cuántas unidades de cada producto venderemos en los próximos 3 meses, "
            "basándose en la tendencia de ventas reciente. "
            "Ayuda a hacer pedidos de compra más inteligentes y evitar roturas de stock."
        ),
        "desc_tecnica": (
            "Calcula la media de ventas mensuales de los últimos 6 meses por artículo "
            "y proyecta 3 meses hacia adelante. "
            "Compara con stock actual para identificar necesidades de reposición. "
            "Modelo de predicción simple pero efectivo para la planificación de compras "
            "en JDDC Climatización."
        ),
        "sql": (
            "SELECT A.REFERENCIA, A.NOMBRE, "
            "ROUND(SUM(L.CANTIDAD) / 6.0, 1) AS MEDIA_MENSUAL, "
            "ROUND(SUM(L.CANTIDAD) / 6.0 * 3, 1) AS PREDICCION_3_MESES, "
            "A.STOCKACTUAL, "
            "ROUND(A.STOCKACTUAL - (SUM(L.CANTIDAD) / 6.0 * 3), 1) AS STOCK_PREVISTO, "
            "CASE WHEN A.STOCKACTUAL < (SUM(L.CANTIDAD) / 6.0 * 3) "
            "     THEN 'REPONER' ELSE 'OK' END AS ESTADO "
            "FROM DOCLIN L "
            "JOIN DOCCAB D ON D.CODIGO = L.CODIGO AND D.TIPO = 13 "
            "JOIN ARTICULO A ON CAST(L.CODART AS INTEGER) = A.CODIGO "
            "WHERE D.FECHA >= date('now', '-180 days') "
            "GROUP BY A.CODIGO, A.REFERENCIA, A.NOMBRE, A.STOCKACTUAL "
            "HAVING SUM(L.CANTIDAD) > 0 "
            "ORDER BY ESTADO DESC, MEDIA_MENSUAL DESC LIMIT 30"
        ),
        "dept": ["Almacén", "Compras", "Dirección"],
        "rol": ["Gerente", "Director", "Almacenero"],
        "tipo": "Modernización",
        "urgencia": "Medio",
        "kpi": "Predicción Demanda",
        "accion": "Generar pedidos de compra para artículos con estado REPONER.",
    },
]

# ─── Función de acceso ────────────────────────────────────────────────────────

def get_all_queries() -> List[Dict[str, Any]]:
    """Devuelve todas las consultas de la biblioteca."""
    return QUERY_LIBRARY


def get_queries_by_dept(dept: str) -> List[Dict[str, Any]]:
    """Filtra consultas por departamento."""
    return [
        q for q in QUERY_LIBRARY
        if dept in (q.get("dept") if isinstance(q.get("dept"), list) else [q.get("dept")])
        or dept == "Todos"
    ]


def get_queries_by_tipo(tipo: str) -> List[Dict[str, Any]]:
    """Filtra consultas por tipo."""
    return [q for q in QUERY_LIBRARY if q.get("tipo") == tipo]


def get_queries_by_urgencia(urgencia: str) -> List[Dict[str, Any]]:
    """Filtra consultas por urgencia."""
    return [q for q in QUERY_LIBRARY if q.get("urgencia") == urgencia]


def get_query_by_id(query_id: str) -> Dict[str, Any]:
    """Obtiene una consulta por su ID."""
    for q in QUERY_LIBRARY:
        if q.get("id") == query_id:
            return q
    return {}


def search_queries(
    dept: str = None,
    rol: str = None,
    tipo: str = None,
    urgencia: str = None,
    text: str = None,
    term: str = None,
) -> List[Dict[str, Any]]:
    """Busca consultas con filtros combinados (dept, rol, tipo, urgencia, text/term)."""
    results = list(QUERY_LIBRARY)
    if dept:
        results = [
            q for q in results
            if dept in (q.get("dept") if isinstance(q.get("dept"), list) else [q.get("dept")])
        ]
    if rol:
        results = [
            q for q in results
            if rol in (q.get("rol") if isinstance(q.get("rol"), list) else [q.get("rol")])
        ]
    if tipo:
        results = [q for q in results if q.get("tipo") == tipo]
    if urgencia:
        results = [q for q in results if q.get("urgencia") == urgencia]
    search_term = text or term
    if search_term:
        t = search_term.lower()
        results = [
            q for q in results
            if t in q.get("title", "").lower()
            or t in q.get("desc", "").lower()
            or t in q.get("desc_simple", "").lower()
            or t in q.get("sql", "").lower()
        ]
    return results


def get_catalog_summary() -> dict:
    """Devuelve un resumen del catalogo: totales por dept, rol, tipo y urgencia."""
    from collections import Counter
    queries = QUERY_LIBRARY
    dept_counter: Counter = Counter()
    rol_counter: Counter = Counter()
    tipo_counter: Counter = Counter()
    urgencia_counter: Counter = Counter()
    for q in queries:
        depts = q.get("dept", [])
        if isinstance(depts, str):
            depts = [depts]
        for d in depts:
            dept_counter[d] += 1
        roles = q.get("rol", [])
        if isinstance(roles, str):
            roles = [roles]
        for r in roles:
            rol_counter[r] += 1
        tipo_counter[q.get("tipo", "")] += 1
        urgencia_counter[q.get("urgencia", "")] += 1
    result = {
        "total": len(queries),
        "by_dept": dict(dept_counter),
        "by_rol": dict(rol_counter),
        "by_tipo": dict(tipo_counter),
        "by_urgencia": dict(urgencia_counter),
    }
    # Alias legacy para compatibilidad con tests y frontend antiguo
    result["por_departamento"] = result["by_dept"]
    result["por_rol"] = result["by_rol"]
    result["por_tipo"] = result["by_tipo"]
    result["por_urgencia"] = result["by_urgencia"]
    return result


def get_queries_by_rol(rol: str) -> List[Dict[str, Any]]:
    """Filtra consultas por rol de usuario."""
    rol_lower = rol.lower()
    results = []
    for q in QUERY_LIBRARY:
        roles = q.get("rol", [])
        if isinstance(roles, str):
            roles = [roles]
        if any(rol_lower in r.lower() for r in roles):
            results.append(q)
    return results
