"""
justification/registry.py — Registro central de verificaciones por query_id.

PRINCIPIO: Exactamente 10 paneles por consulta (STANDARD_PANEL_COUNT).
           Sin comentarios subjetivos. Solo hechos verificables con datos.
           Las afirmaciones técnicas tienen panel de evidencia asociado.

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from typing import Any, Dict, List

from backend.modules.db_simulator.justification.panels import (
    panel_desglose_tipos,
    panel_sin_duplicados,
    panel_evolucion_mensual,
    panel_comparativa_anual,
    panel_importes_anomalos,
    panel_ultimos_documentos,
    panel_documentos_sin_fecha,
    panel_documentos_sin_cliente,
    panel_antiguedad_documentos,
    panel_clientes_por_facturacion,
    panel_clientes_sin_nombre,
    panel_clientes_activos,
    panel_concentracion_top5,
    panel_iva_desglose,
    panel_iva_por_documento,
    panel_caja_resumen,
    panel_caja_por_mes,
    panel_articulos_mas_vendidos,
    panel_stock_articulos,
    panel_articulos_sin_stock,
    panel_articulos_baja,
    panel_articulos_sin_proveedor,
    panel_precio_vs_coste,
    panel_familias_productos,
    panel_proveedores_activos,
    panel_agentes_ventas,
    panel_formas_pago,
    panel_lineas_sin_articulo,
    panel_lineas_por_documento,
    panel_sats_por_estado,
    panel_presupuestos_por_estado,
    panel_albaranes_vs_facturas,
    panel_ventas_vs_compras_mensual,
    panel_descuentos_aplicados,
)

# Número estándar de paneles por consulta
STANDARD_PANEL_COUNT = 10

# ─── Helpers SQL locales ──────────────────────────────────────────────────────

_CLIENTE_NOMBRE = "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, CAST(D.CODCLIENTE AS TEXT))"


def _p(panel_dict: Dict[str, Any], unique_id: str) -> Dict[str, Any]:
    """Clona un panel y le asigna un id único para evitar colisiones en la misma consulta."""
    result = dict(panel_dict)
    result["id"] = unique_id
    return result


# ─── Registro de verificaciones ───────────────────────────────────────────────

_REGISTRY: Dict[str, List[Dict[str, Any]]] = {

    # ══════════════════════════════════════════════════════════════════════════
    # VENTAS — KPI PRINCIPALES
    # ══════════════════════════════════════════════════════════════════════════

    "v_kpi_facturacion_total": [
        _p(panel_desglose_tipos(), "v_ft_01"),
        _p(panel_sin_duplicados(13), "v_ft_02"),
        _p(panel_clientes_por_facturacion(13), "v_ft_03"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_ft_04"),
        _p(panel_comparativa_anual(13), "v_ft_05"),
        _p(panel_importes_anomalos(13), "v_ft_06"),
        _p(panel_ultimos_documentos(13, "facturas", 30), "v_ft_07"),
        _p(panel_iva_desglose(13), "v_ft_08"),
        _p(panel_iva_por_documento(13), "v_ft_09"),
        _p(panel_agentes_ventas(), "v_ft_10"),
    ],

    "v_kpi_ticket_medio": [
        {
            "id": "v_tm_01",
            "label": "Distribución de importes por rango",
            "justificacion": (
                "Agrupa las facturas por rangos de importe para ver si el ticket medio es representativo "
                "o está distorsionado por outliers (facturas muy grandes o muy pequeñas)."
            ),
            # Subquery wrapper: Firebird 2.5 no permite GROUP BY alias de CASE.
            # Sin simbolo euro para compatibilidad con charset latin-1 de Firebird.
            "sql": (
                "SELECT RANGO, COUNT(*) AS N_FACTURAS, ROUND(AVG(IMPORTE),2) AS MEDIA_RANGO "
                "FROM ("
                "SELECT IMPORTETOTAL AS IMPORTE, "
                "CASE WHEN IMPORTETOTAL < 100 THEN 'menos 100' "
                "     WHEN IMPORTETOTAL < 500 THEN '100-500' "
                "     WHEN IMPORTETOTAL < 1000 THEN '500-1000' "
                "     WHEN IMPORTETOTAL < 5000 THEN '1000-5000' "
                "     ELSE 'mas 5000' END AS RANGO "
                "FROM DOCCAB WHERE TIPO=13"
                ") GROUP BY RANGO ORDER BY MIN(IMPORTE)"
            ),
            "icono": "📊",
            "tipo": "tabla",
            "max_rows": 10,
        },
        {
            "id": "v_tm_02",
            "label": "Ticket medio por cliente (top 20)",
            "justificacion": (
                "El ticket medio global puede ocultar diferencias entre clientes. "
                "Este panel muestra el ticket medio de cada cliente para identificar "
                "quiénes generan trabajos de mayor valor."
            ),
            # GROUP BY incluye D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL
            # para compatibilidad con Firebird (no permite columnas no agregadas fuera del GROUP BY)
            "sql": (
                f"SELECT {_CLIENTE_NOMBRE} AS CLIENTE, "
                "COUNT(*) AS N_FACTURAS, ROUND(AVG(D.IMPORTETOTAL),2) AS TICKET_MEDIO, "
                "ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
                "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
                "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
                "ORDER BY TICKET_MEDIO DESC LIMIT 20"
            ),
            "icono": "👤",
            "tipo": "tabla",
            "max_rows": 20,
        },
        {
            "id": "v_tm_03",
            "label": "Evolución del ticket medio mensual",
            "justificacion": (
                "Si el ticket medio varía mucho mes a mes, puede indicar cambios en el mix de trabajos "
                "o en la política de precios."
            ),
            "sql": (
                "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_FACTURAS, "
                "ROUND(AVG(IMPORTETOTAL),2) AS TICKET_MEDIO "
                "FROM DOCCAB WHERE TIPO=13 AND FECHA IS NOT NULL "
                "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 12"
            ),
            "icono": "📈",
            "tipo": "tabla",
            "max_rows": 12,
        },
        _p(panel_importes_anomalos(13), "v_tm_04"),
        _p(panel_sin_duplicados(13), "v_tm_05"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_tm_06"),
        _p(panel_comparativa_anual(13), "v_tm_07"),
        _p(panel_clientes_activos(13), "v_tm_08"),
        _p(panel_iva_desglose(13), "v_tm_09"),
        _p(panel_iva_por_documento(13), "v_tm_10"),
    ],

    "v_kpi_top10_clientes": [
        _p(panel_clientes_activos(13), "v_tc_01"),
        _p(panel_concentracion_top5(13), "v_tc_02"),
        _p(panel_clientes_sin_nombre(), "v_tc_03"),
        {
            "id": "v_tc_04",
            "label": "Todos los clientes con facturación (orden alfabético)",
            "justificacion": (
                "Lista completa de clientes con facturación, ordenada alfabéticamente. "
                "Permite verificar que no hay clientes duplicados con nombres similares."
            ),
            # GROUP BY incluye D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL
            # para compatibilidad con Firebird (no permite columnas no agregadas fuera del GROUP BY)
            "sql": (
                f"SELECT {_CLIENTE_NOMBRE} AS CLIENTE, "
                "COUNT(D.CODIGO) AS N_FACTURAS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
                "FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
                "WHERE D.TIPO=13 GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
                "ORDER BY CLIENTE ASC LIMIT 50"
            ),
            "icono": "🔤",
            "tipo": "tabla",
            "max_rows": 50,
        },
        _p(panel_evolucion_mensual(13, "facturas"), "v_tc_05"),
        _p(panel_importes_anomalos(13), "v_tc_06"),
        _p(panel_sin_duplicados(13), "v_tc_07"),
        _p(panel_iva_desglose(13), "v_tc_08"),
        _p(panel_iva_por_documento(13), "v_tc_09"),
        _p(panel_agentes_ventas(), "v_tc_10"),
    ],

    "v_kpi_n_clientes_activos": [
        _p(panel_clientes_activos(13), "v_ca_01"),
        _p(panel_clientes_sin_nombre(), "v_ca_02"),
        {
            "id": "v_ca_03",
            "label": "Clientes nuevos vs recurrentes",
            "justificacion": (
                "Un cliente es 'nuevo' si tiene solo 1 factura. "
                "Un cliente 'recurrente' tiene 2 o más. "
                "La proporción indica la fidelización de la cartera."
            ),
            "sql": (
                "SELECT "
                "CASE WHEN N_FACTURAS=1 THEN 'Nuevo (1 factura)' "
                "     WHEN N_FACTURAS<=3 THEN 'Ocasional (2-3)' "
                "     WHEN N_FACTURAS<=10 THEN 'Regular (4-10)' "
                "     ELSE 'Fiel (>10)' END AS TIPO_CLIENTE, "
                "COUNT(*) AS N_CLIENTES "
                "FROM (SELECT CODCLIENTE, COUNT(*) AS N_FACTURAS FROM DOCCAB WHERE TIPO=13 GROUP BY CODCLIENTE) "
                "GROUP BY TIPO_CLIENTE ORDER BY MIN(N_FACTURAS)"
            ),
            "icono": "🔄",
            "tipo": "tabla",
            "max_rows": 10,
        },
        _p(panel_concentracion_top5(13), "v_ca_04"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_ca_05"),
        _p(panel_importes_anomalos(13), "v_ca_06"),
        _p(panel_sin_duplicados(13), "v_ca_07"),
        _p(panel_agentes_ventas(), "v_ca_08"),
        _p(panel_formas_pago(), "v_ca_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_ca_10"),
    ],

    "v_kpi_conversion_presupuestos": [
        _p(panel_presupuestos_por_estado(), "v_cp_01"),
        {
            "id": "v_cp_02",
            "label": "Presupuestos con documento de origen en facturas",
            "justificacion": (
                "Presupuestos (TIPO=0) que tienen un documento relacionado de TIPO=13. "
                "La tasa de conversión = presupuestos convertidos / total presupuestos."
            ),
            "sql": (
                "SELECT COUNT(DISTINCT D.CODIGO) AS TOTAL_PRESUPUESTOS, "
                "COUNT(DISTINCT L.CODDOCUMENTOORIGEN) AS CONVERTIDOS "
                "FROM DOCCAB D "
                "LEFT JOIN DOCLIN L ON L.CODDOCUMENTOORIGEN=D.CODIGO "
                "WHERE D.TIPO=0"
            ),
            "icono": "✅",
            "tipo": "resumen",
            "max_rows": 5,
        },
        _p(panel_evolucion_mensual(0, "presupuestos"), "v_cp_03"),
        _p(panel_comparativa_anual(0), "v_cp_04"),
        _p(panel_importes_anomalos(0), "v_cp_05"),
        _p(panel_sin_duplicados(0), "v_cp_06"),
        _p(panel_clientes_por_facturacion(0), "v_cp_07"),
        _p(panel_documentos_sin_fecha(0), "v_cp_08"),
        _p(panel_antiguedad_documentos(0, "presupuestos"), "v_cp_09"),
        _p(panel_ultimos_documentos(0, "presupuestos", 20), "v_cp_10"),
    ],

    "v_kpi_presupuestos_pendientes_importe": [
        _p(panel_presupuestos_por_estado(), "v_pp_01"),
        {
            "id": "v_pp_02",
            "label": "Presupuestos con más de 90 días sin respuesta",
            "justificacion": (
                "Presupuestos muy antiguos sin convertir en factura. "
                "Incluirlos en el pipeline activo distorsiona las previsiones de ventas."
            ),
            "sql": (
                "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE, "
                "CAST(JULIANDAY('now') - JULIANDAY(FECHA) AS INTEGER) AS DIAS_PENDIENTE "
                "FROM DOCCAB WHERE TIPO=0 AND FECHA IS NOT NULL "
                "AND JULIANDAY('now') - JULIANDAY(FECHA) > 90 "
                "ORDER BY DIAS_PENDIENTE DESC LIMIT 20"
            ),
            "icono": "⏰",
            "tipo": "tabla",
            "max_rows": 20,
        },
        _p(panel_clientes_por_facturacion(0), "v_pp_03"),
        _p(panel_evolucion_mensual(0, "presupuestos"), "v_pp_04"),
        _p(panel_comparativa_anual(0), "v_pp_05"),
        _p(panel_importes_anomalos(0), "v_pp_06"),
        _p(panel_sin_duplicados(0), "v_pp_07"),
        _p(panel_documentos_sin_fecha(0), "v_pp_08"),
        _p(panel_antiguedad_documentos(0, "presupuestos"), "v_pp_09"),
        _p(panel_ultimos_documentos(0, "presupuestos", 20), "v_pp_10"),
    ],

    "v_presupuestos_antiguos_sin_respuesta": [
        _p(panel_presupuestos_por_estado(), "v_pa_01"),
        _p(panel_evolucion_mensual(0, "presupuestos"), "v_pa_02"),
        _p(panel_comparativa_anual(0), "v_pa_03"),
        _p(panel_clientes_por_facturacion(0), "v_pa_04"),
        _p(panel_importes_anomalos(0), "v_pa_05"),
        _p(panel_sin_duplicados(0), "v_pa_06"),
        _p(panel_documentos_sin_fecha(0), "v_pa_07"),
        _p(panel_antiguedad_documentos(0, "presupuestos"), "v_pa_08"),
        _p(panel_concentracion_top5(0), "v_pa_09"),
        _p(panel_ultimos_documentos(0, "presupuestos", 20), "v_pa_10"),
    ],

    "v_kpi_facturacion_mensual": [
        _p(panel_evolucion_mensual(13, "facturas"), "v_fm_01"),
        _p(panel_comparativa_anual(13), "v_fm_02"),
        _p(panel_documentos_sin_fecha(13), "v_fm_03"),
        _p(panel_sin_duplicados(13), "v_fm_04"),
        _p(panel_importes_anomalos(13), "v_fm_05"),
        _p(panel_clientes_por_facturacion(13), "v_fm_06"),
        _p(panel_agentes_ventas(), "v_fm_07"),
        _p(panel_formas_pago(), "v_fm_08"),
        _p(panel_iva_desglose(13), "v_fm_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_fm_10"),
    ],

    "v_kpi_ventas_acumuladas_anio": [
        _p(panel_comparativa_anual(13), "v_va_01"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_va_02"),
        _p(panel_documentos_sin_fecha(13), "v_va_03"),
        _p(panel_sin_duplicados(13), "v_va_04"),
        _p(panel_importes_anomalos(13), "v_va_05"),
        _p(panel_clientes_por_facturacion(13), "v_va_06"),
        _p(panel_agentes_ventas(), "v_va_07"),
        _p(panel_formas_pago(), "v_va_08"),
        _p(panel_iva_desglose(13), "v_va_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_va_10"),
    ],

    "v_kpi_albaranes_sin_facturar": [
        _p(panel_albaranes_vs_facturas(), "v_af_01"),
        {
            "id": "v_af_02",
            "label": "Albaranes con más de 30 días sin facturar",
            "justificacion": (
                "Albaranes muy antiguos sin facturar representan ingresos no cobrados. "
                "Deben revisarse para facturarlos o justificar por qué siguen pendientes."
            ),
            "sql": (
                "SELECT CODIGO, CODCLIENTE, FECHA, ROUND(IMPORTETOTAL,2) AS IMPORTE, "
                "CAST(JULIANDAY('now') - JULIANDAY(FECHA) AS INTEGER) AS DIAS_PENDIENTE "
                "FROM DOCCAB WHERE TIPO=11 AND FECHA IS NOT NULL "
                "AND JULIANDAY('now') - JULIANDAY(FECHA) > 30 "
                "ORDER BY DIAS_PENDIENTE DESC LIMIT 20"
            ),
            "icono": "⏰",
            "tipo": "tabla",
            "max_rows": 20,
        },
        _p(panel_evolucion_mensual(11, "albaranes"), "v_af_03"),
        _p(panel_comparativa_anual(11), "v_af_04"),
        _p(panel_importes_anomalos(11), "v_af_05"),
        _p(panel_sin_duplicados(11), "v_af_06"),
        _p(panel_clientes_por_facturacion(11), "v_af_07"),
        _p(panel_documentos_sin_fecha(11), "v_af_08"),
        _p(panel_antiguedad_documentos(11, "albaranes"), "v_af_09"),
        _p(panel_ultimos_documentos(11, "albaranes", 20), "v_af_10"),
    ],

    "v_ventas_por_forma_pago": [
        _p(panel_formas_pago(), "v_vfp_01"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_vfp_02"),
        _p(panel_comparativa_anual(13), "v_vfp_03"),
        _p(panel_clientes_por_facturacion(13), "v_vfp_04"),
        _p(panel_importes_anomalos(13), "v_vfp_05"),
        _p(panel_sin_duplicados(13), "v_vfp_06"),
        _p(panel_iva_desglose(13), "v_vfp_07"),
        _p(panel_iva_por_documento(13), "v_vfp_08"),
        _p(panel_agentes_ventas(), "v_vfp_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_vfp_10"),
    ],

    "v_clientes_sin_compra_reciente": [
        _p(panel_clientes_activos(13), "v_csr_01"),
        _p(panel_clientes_sin_nombre(), "v_csr_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_csr_03"),
        _p(panel_comparativa_anual(13), "v_csr_04"),
        _p(panel_concentracion_top5(13), "v_csr_05"),
        _p(panel_importes_anomalos(13), "v_csr_06"),
        _p(panel_sin_duplicados(13), "v_csr_07"),
        _p(panel_agentes_ventas(), "v_csr_08"),
        _p(panel_formas_pago(), "v_csr_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_csr_10"),
    ],

    "v_clientes_nuevos_mes": [
        _p(panel_clientes_activos(13), "v_cnm_01"),
        _p(panel_clientes_sin_nombre(), "v_cnm_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_cnm_03"),
        _p(panel_comparativa_anual(13), "v_cnm_04"),
        _p(panel_concentracion_top5(13), "v_cnm_05"),
        _p(panel_importes_anomalos(13), "v_cnm_06"),
        _p(panel_sin_duplicados(13), "v_cnm_07"),
        _p(panel_agentes_ventas(), "v_cnm_08"),
        _p(panel_formas_pago(), "v_cnm_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_cnm_10"),
    ],

    "v_distribucion_documentos_tipo": [
        _p(panel_desglose_tipos(), "v_ddt_01"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_ddt_02"),
        _p(panel_evolucion_mensual(0, "presupuestos"), "v_ddt_03"),
        _p(panel_albaranes_vs_facturas(), "v_ddt_04"),
        _p(panel_importes_anomalos(13), "v_ddt_05"),
        _p(panel_sin_duplicados(13), "v_ddt_06"),
        _p(panel_documentos_sin_fecha(13), "v_ddt_07"),
        _p(panel_clientes_activos(13), "v_ddt_08"),
        _p(panel_iva_desglose(13), "v_ddt_09"),
        _p(panel_comparativa_anual(13), "v_ddt_10"),
    ],

    "v_ventas_por_provincia": [
        _p(panel_clientes_activos(13), "v_vpp_01"),
        _p(panel_clientes_sin_nombre(), "v_vpp_02"),
        _p(panel_concentracion_top5(13), "v_vpp_03"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_vpp_04"),
        _p(panel_comparativa_anual(13), "v_vpp_05"),
        _p(panel_importes_anomalos(13), "v_vpp_06"),
        _p(panel_sin_duplicados(13), "v_vpp_07"),
        _p(panel_agentes_ventas(), "v_vpp_08"),
        _p(panel_formas_pago(), "v_vpp_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_vpp_10"),
    ],

    "v_ranking_comerciales": [
        _p(panel_agentes_ventas(), "v_rc_01"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_rc_02"),
        _p(panel_comparativa_anual(13), "v_rc_03"),
        _p(panel_clientes_por_facturacion(13), "v_rc_04"),
        _p(panel_importes_anomalos(13), "v_rc_05"),
        _p(panel_sin_duplicados(13), "v_rc_06"),
        _p(panel_concentracion_top5(13), "v_rc_07"),
        _p(panel_iva_desglose(13), "v_rc_08"),
        _p(panel_formas_pago(), "v_rc_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_rc_10"),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # VENTAS — RIESGO Y ALERTAS
    # ══════════════════════════════════════════════════════════════════════════

    "v_riesgo_concentracion_clientes": [
        _p(panel_concentracion_top5(13), "v_rcc_01"),
        _p(panel_clientes_activos(13), "v_rcc_02"),
        _p(panel_clientes_por_facturacion(13), "v_rcc_03"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_rcc_04"),
        _p(panel_comparativa_anual(13), "v_rcc_05"),
        _p(panel_importes_anomalos(13), "v_rcc_06"),
        _p(panel_sin_duplicados(13), "v_rcc_07"),
        _p(panel_agentes_ventas(), "v_rcc_08"),
        _p(panel_formas_pago(), "v_rcc_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_rcc_10"),
    ],

    "v_riesgo_facturas_importe_alto": [
        _p(panel_clientes_por_facturacion(13), "v_rfia_01"),
        _p(panel_concentracion_top5(13), "v_rfia_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_rfia_03"),
        _p(panel_comparativa_anual(13), "v_rfia_04"),
        _p(panel_importes_anomalos(13), "v_rfia_05"),
        _p(panel_sin_duplicados(13), "v_rfia_06"),
        _p(panel_iva_desglose(13), "v_rfia_07"),
        _p(panel_iva_por_documento(13), "v_rfia_08"),
        _p(panel_agentes_ventas(), "v_rfia_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_rfia_10"),
    ],

    "v_riesgo_clientes_un_solo_producto": [
        _p(panel_clientes_activos(13), "v_rcusp_01"),
        _p(panel_articulos_mas_vendidos(), "v_rcusp_02"),
        _p(panel_lineas_sin_articulo(), "v_rcusp_03"),
        _p(panel_lineas_por_documento(13), "v_rcusp_04"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_rcusp_05"),
        _p(panel_comparativa_anual(13), "v_rcusp_06"),
        _p(panel_importes_anomalos(13), "v_rcusp_07"),
        _p(panel_sin_duplicados(13), "v_rcusp_08"),
        _p(panel_familias_productos(), "v_rcusp_09"),
        _p(panel_precio_vs_coste(), "v_rcusp_10"),
    ],

    "v_riesgo_presupuestos_caducados": [
        _p(panel_presupuestos_por_estado(), "v_rpc_01"),
        _p(panel_evolucion_mensual(0, "presupuestos"), "v_rpc_02"),
        _p(panel_comparativa_anual(0), "v_rpc_03"),
        _p(panel_clientes_por_facturacion(0), "v_rpc_04"),
        _p(panel_importes_anomalos(0), "v_rpc_05"),
        _p(panel_sin_duplicados(0), "v_rpc_06"),
        _p(panel_documentos_sin_fecha(0), "v_rpc_07"),
        _p(panel_antiguedad_documentos(0, "presupuestos"), "v_rpc_08"),
        _p(panel_concentracion_top5(0), "v_rpc_09"),
        _p(panel_ultimos_documentos(0, "presupuestos", 20), "v_rpc_10"),
    ],

    "v_riesgo_clientes_deuda_alta": [
        _p(panel_clientes_por_facturacion(13), "v_rcda_01"),
        _p(panel_concentracion_top5(13), "v_rcda_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_rcda_03"),
        _p(panel_comparativa_anual(13), "v_rcda_04"),
        _p(panel_importes_anomalos(13), "v_rcda_05"),
        _p(panel_sin_duplicados(13), "v_rcda_06"),
        _p(panel_antiguedad_documentos(13, "facturas"), "v_rcda_07"),
        _p(panel_iva_desglose(13), "v_rcda_08"),
        _p(panel_agentes_ventas(), "v_rcda_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_rcda_10"),
    ],

    "v_riesgo_sin_ventas_ultima_semana": [
        _p(panel_evolucion_mensual(13, "facturas"), "v_rsvus_01"),
        _p(panel_comparativa_anual(13), "v_rsvus_02"),
        _p(panel_documentos_sin_fecha(13), "v_rsvus_03"),
        _p(panel_sin_duplicados(13), "v_rsvus_04"),
        _p(panel_importes_anomalos(13), "v_rsvus_05"),
        _p(panel_clientes_activos(13), "v_rsvus_06"),
        _p(panel_agentes_ventas(), "v_rsvus_07"),
        _p(panel_formas_pago(), "v_rsvus_08"),
        _p(panel_iva_desglose(13), "v_rsvus_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_rsvus_10"),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # VENTAS — OPTIMIZACIÓN Y PREDICCIÓN
    # ══════════════════════════════════════════════════════════════════════════

    "v_opt_mejor_dia_semana_ventas": [
        _p(panel_evolucion_mensual(13, "facturas"), "v_omdsv_01"),
        _p(panel_comparativa_anual(13), "v_omdsv_02"),
        _p(panel_documentos_sin_fecha(13), "v_omdsv_03"),
        _p(panel_sin_duplicados(13), "v_omdsv_04"),
        _p(panel_importes_anomalos(13), "v_omdsv_05"),
        _p(panel_clientes_activos(13), "v_omdsv_06"),
        _p(panel_agentes_ventas(), "v_omdsv_07"),
        _p(panel_formas_pago(), "v_omdsv_08"),
        _p(panel_iva_desglose(13), "v_omdsv_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_omdsv_10"),
    ],

    "v_opt_estacionalidad_trimestral": [
        _p(panel_evolucion_mensual(13, "facturas"), "v_oet_01"),
        _p(panel_comparativa_anual(13), "v_oet_02"),
        _p(panel_documentos_sin_fecha(13), "v_oet_03"),
        _p(panel_sin_duplicados(13), "v_oet_04"),
        _p(panel_importes_anomalos(13), "v_oet_05"),
        _p(panel_clientes_activos(13), "v_oet_06"),
        _p(panel_agentes_ventas(), "v_oet_07"),
        _p(panel_formas_pago(), "v_oet_08"),
        _p(panel_iva_desglose(13), "v_oet_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_oet_10"),
    ],

    "v_pred_clientes_alto_valor": [
        _p(panel_clientes_activos(13), "v_pcav_01"),
        _p(panel_concentracion_top5(13), "v_pcav_02"),
        _p(panel_clientes_por_facturacion(13), "v_pcav_03"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_pcav_04"),
        _p(panel_comparativa_anual(13), "v_pcav_05"),
        _p(panel_importes_anomalos(13), "v_pcav_06"),
        _p(panel_sin_duplicados(13), "v_pcav_07"),
        _p(panel_agentes_ventas(), "v_pcav_08"),
        _p(panel_formas_pago(), "v_pcav_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_pcav_10"),
    ],

    "v_pred_productos_tendencia_creciente": [
        _p(panel_articulos_mas_vendidos(), "v_pptc_01"),
        _p(panel_lineas_sin_articulo(), "v_pptc_02"),
        _p(panel_lineas_por_documento(13), "v_pptc_03"),
        _p(panel_familias_productos(), "v_pptc_04"),
        _p(panel_precio_vs_coste(), "v_pptc_05"),
        _p(panel_stock_articulos(), "v_pptc_06"),
        _p(panel_articulos_sin_stock(), "v_pptc_07"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_pptc_08"),
        _p(panel_comparativa_anual(13), "v_pptc_09"),
        _p(panel_importes_anomalos(13), "v_pptc_10"),
    ],

    "v_pred_clientes_riesgo_fuga": [
        _p(panel_clientes_activos(13), "v_pcrf_01"),
        _p(panel_clientes_sin_nombre(), "v_pcrf_02"),
        _p(panel_concentracion_top5(13), "v_pcrf_03"),
        _p(panel_evolucion_mensual(13, "facturas"), "v_pcrf_04"),
        _p(panel_comparativa_anual(13), "v_pcrf_05"),
        _p(panel_importes_anomalos(13), "v_pcrf_06"),
        _p(panel_sin_duplicados(13), "v_pcrf_07"),
        _p(panel_agentes_ventas(), "v_pcrf_08"),
        _p(panel_formas_pago(), "v_pcrf_09"),
        _p(panel_ultimos_documentos(13, "facturas", 20), "v_pcrf_10"),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # COMPRAS — KPI Y PROVEEDORES
    # ══════════════════════════════════════════════════════════════════════════

    "c_kpi_top10_proveedores": [
        _p(panel_proveedores_activos(), "c_tp_01"),
        _p(panel_articulos_sin_proveedor(), "c_tp_02"),
        _p(panel_familias_productos(), "c_tp_03"),
        _p(panel_precio_vs_coste(), "c_tp_04"),
        _p(panel_stock_articulos(), "c_tp_05"),
        _p(panel_articulos_sin_stock(), "c_tp_06"),
        _p(panel_articulos_baja(), "c_tp_07"),
        _p(panel_lineas_sin_articulo(), "c_tp_08"),
        _p(panel_evolucion_mensual(13, "facturas"), "c_tp_09"),
        _p(panel_comparativa_anual(13), "c_tp_10"),
    ],

    "c_kpi_articulos_sin_proveedor": [
        _p(panel_articulos_sin_proveedor(), "c_asp_01"),
        _p(panel_proveedores_activos(), "c_asp_02"),
        _p(panel_familias_productos(), "c_asp_03"),
        _p(panel_precio_vs_coste(), "c_asp_04"),
        _p(panel_stock_articulos(), "c_asp_05"),
        _p(panel_articulos_sin_stock(), "c_asp_06"),
        _p(panel_articulos_baja(), "c_asp_07"),
        _p(panel_lineas_sin_articulo(), "c_asp_08"),
        _p(panel_articulos_mas_vendidos(), "c_asp_09"),
        _p(panel_lineas_por_documento(13), "c_asp_10"),
    ],

    "c_kpi_catalogo_por_proveedor": [
        _p(panel_proveedores_activos(), "c_cpp_01"),
        _p(panel_articulos_sin_proveedor(), "c_cpp_02"),
        _p(panel_familias_productos(), "c_cpp_03"),
        _p(panel_precio_vs_coste(), "c_cpp_04"),
        _p(panel_stock_articulos(), "c_cpp_05"),
        _p(panel_articulos_sin_stock(), "c_cpp_06"),
        _p(panel_articulos_baja(), "c_cpp_07"),
        _p(panel_lineas_sin_articulo(), "c_cpp_08"),
        _p(panel_articulos_mas_vendidos(), "c_cpp_09"),
        _p(panel_lineas_por_documento(13), "c_cpp_10"),
    ],

    "c_riesgo_proveedor_unico": [
        _p(panel_proveedores_activos(), "c_rpu_01"),
        _p(panel_articulos_sin_proveedor(), "c_rpu_02"),
        _p(panel_stock_articulos(), "c_rpu_03"),
        _p(panel_articulos_sin_stock(), "c_rpu_04"),
        _p(panel_familias_productos(), "c_rpu_05"),
        _p(panel_precio_vs_coste(), "c_rpu_06"),
        _p(panel_articulos_baja(), "c_rpu_07"),
        _p(panel_lineas_sin_articulo(), "c_rpu_08"),
        _p(panel_articulos_mas_vendidos(), "c_rpu_09"),
        _p(panel_lineas_por_documento(13), "c_rpu_10"),
    ],

    "c_opt_negociacion_volumen": [
        _p(panel_articulos_mas_vendidos(), "c_onv_01"),
        _p(panel_proveedores_activos(), "c_onv_02"),
        _p(panel_precio_vs_coste(), "c_onv_03"),
        _p(panel_stock_articulos(), "c_onv_04"),
        _p(panel_articulos_sin_stock(), "c_onv_05"),
        _p(panel_familias_productos(), "c_onv_06"),
        _p(panel_lineas_sin_articulo(), "c_onv_07"),
        _p(panel_lineas_por_documento(13), "c_onv_08"),
        _p(panel_evolucion_mensual(13, "facturas"), "c_onv_09"),
        _p(panel_comparativa_anual(13), "c_onv_10"),
    ],

    "c_kpi_proveedores_activos": [
        _p(panel_proveedores_activos(), "c_pa_01"),
        _p(panel_articulos_sin_proveedor(), "c_pa_02"),
        _p(panel_familias_productos(), "c_pa_03"),
        _p(panel_precio_vs_coste(), "c_pa_04"),
        _p(panel_stock_articulos(), "c_pa_05"),
        _p(panel_articulos_sin_stock(), "c_pa_06"),
        _p(panel_articulos_baja(), "c_pa_07"),
        _p(panel_lineas_sin_articulo(), "c_pa_08"),
        _p(panel_articulos_mas_vendidos(), "c_pa_09"),
        _p(panel_lineas_por_documento(13), "c_pa_10"),
    ],

    "c_kpi_articulos_precio_alto": [
        _p(panel_precio_vs_coste(), "c_apa_01"),
        _p(panel_proveedores_activos(), "c_apa_02"),
        _p(panel_familias_productos(), "c_apa_03"),
        _p(panel_stock_articulos(), "c_apa_04"),
        _p(panel_articulos_sin_stock(), "c_apa_05"),
        _p(panel_articulos_baja(), "c_apa_06"),
        _p(panel_articulos_sin_proveedor(), "c_apa_07"),
        _p(panel_lineas_sin_articulo(), "c_apa_08"),
        _p(panel_articulos_mas_vendidos(), "c_apa_09"),
        _p(panel_lineas_por_documento(13), "c_apa_10"),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # ALMACÉN — KPI Y STOCK
    # ══════════════════════════════════════════════════════════════════════════

    "a_kpi_valor_stock_total": [
        _p(panel_stock_articulos(), "a_vst_01"),
        _p(panel_articulos_sin_stock(), "a_vst_02"),
        _p(panel_familias_productos(), "a_vst_03"),
        _p(panel_precio_vs_coste(), "a_vst_04"),
        _p(panel_proveedores_activos(), "a_vst_05"),
        _p(panel_articulos_sin_proveedor(), "a_vst_06"),
        _p(panel_articulos_baja(), "a_vst_07"),
        _p(panel_lineas_sin_articulo(), "a_vst_08"),
        _p(panel_articulos_mas_vendidos(), "a_vst_09"),
        _p(panel_lineas_por_documento(13), "a_vst_10"),
    ],

    "a_kpi_articulos_sin_stock": [
        _p(panel_articulos_sin_stock(), "a_ass_01"),
        _p(panel_stock_articulos(), "a_ass_02"),
        _p(panel_familias_productos(), "a_ass_03"),
        _p(panel_precio_vs_coste(), "a_ass_04"),
        _p(panel_proveedores_activos(), "a_ass_05"),
        _p(panel_articulos_sin_proveedor(), "a_ass_06"),
        _p(panel_articulos_baja(), "a_ass_07"),
        _p(panel_lineas_sin_articulo(), "a_ass_08"),
        _p(panel_articulos_mas_vendidos(), "a_ass_09"),
        _p(panel_lineas_por_documento(13), "a_ass_10"),
    ],

    "a_kpi_stock_bajo_minimo": [
        _p(panel_stock_articulos(), "a_sbm_01"),
        _p(panel_articulos_sin_stock(), "a_sbm_02"),
        _p(panel_familias_productos(), "a_sbm_03"),
        _p(panel_precio_vs_coste(), "a_sbm_04"),
        _p(panel_proveedores_activos(), "a_sbm_05"),
        _p(panel_articulos_sin_proveedor(), "a_sbm_06"),
        _p(panel_articulos_baja(), "a_sbm_07"),
        _p(panel_lineas_sin_articulo(), "a_sbm_08"),
        _p(panel_articulos_mas_vendidos(), "a_sbm_09"),
        _p(panel_lineas_por_documento(13), "a_sbm_10"),
    ],

    "a_kpi_stock_por_familia": [
        _p(panel_familias_productos(), "a_spf_01"),
        _p(panel_stock_articulos(), "a_spf_02"),
        _p(panel_articulos_sin_stock(), "a_spf_03"),
        _p(panel_precio_vs_coste(), "a_spf_04"),
        _p(panel_proveedores_activos(), "a_spf_05"),
        _p(panel_articulos_sin_proveedor(), "a_spf_06"),
        _p(panel_articulos_baja(), "a_spf_07"),
        _p(panel_lineas_sin_articulo(), "a_spf_08"),
        _p(panel_articulos_mas_vendidos(), "a_spf_09"),
        _p(panel_lineas_por_documento(13), "a_spf_10"),
    ],

    "a_kpi_rotacion_stock": [
        _p(panel_articulos_mas_vendidos(), "a_rs_01"),
        _p(panel_stock_articulos(), "a_rs_02"),
        _p(panel_articulos_sin_stock(), "a_rs_03"),
        _p(panel_familias_productos(), "a_rs_04"),
        _p(panel_precio_vs_coste(), "a_rs_05"),
        _p(panel_proveedores_activos(), "a_rs_06"),
        _p(panel_articulos_sin_proveedor(), "a_rs_07"),
        _p(panel_articulos_baja(), "a_rs_08"),
        _p(panel_lineas_sin_articulo(), "a_rs_09"),
        _p(panel_lineas_por_documento(13), "a_rs_10"),
    ],

    "a_riesgo_stock_muerto": [
        _p(panel_stock_articulos(), "a_rsm_01"),
        _p(panel_articulos_sin_stock(), "a_rsm_02"),
        _p(panel_familias_productos(), "a_rsm_03"),
        _p(panel_precio_vs_coste(), "a_rsm_04"),
        _p(panel_proveedores_activos(), "a_rsm_05"),
        _p(panel_articulos_sin_proveedor(), "a_rsm_06"),
        _p(panel_articulos_baja(), "a_rsm_07"),
        _p(panel_lineas_sin_articulo(), "a_rsm_08"),
        _p(panel_articulos_mas_vendidos(), "a_rsm_09"),
        _p(panel_lineas_por_documento(13), "a_rsm_10"),
    ],

    "a_ahorro_reduccion_sobrestock": [
        _p(panel_stock_articulos(), "a_ars_01"),
        _p(panel_articulos_sin_stock(), "a_ars_02"),
        _p(panel_familias_productos(), "a_ars_03"),
        _p(panel_precio_vs_coste(), "a_ars_04"),
        _p(panel_proveedores_activos(), "a_ars_05"),
        _p(panel_articulos_sin_proveedor(), "a_ars_06"),
        _p(panel_articulos_baja(), "a_ars_07"),
        _p(panel_lineas_sin_articulo(), "a_ars_08"),
        _p(panel_articulos_mas_vendidos(), "a_ars_09"),
        _p(panel_lineas_por_documento(13), "a_ars_10"),
    ],

    "a_movimientos_stock_recientes": [
        _p(panel_stock_articulos(), "a_msr_01"),
        _p(panel_articulos_sin_stock(), "a_msr_02"),
        _p(panel_familias_productos(), "a_msr_03"),
        _p(panel_precio_vs_coste(), "a_msr_04"),
        _p(panel_proveedores_activos(), "a_msr_05"),
        _p(panel_articulos_sin_proveedor(), "a_msr_06"),
        _p(panel_articulos_baja(), "a_msr_07"),
        _p(panel_lineas_sin_articulo(), "a_msr_08"),
        _p(panel_articulos_mas_vendidos(), "a_msr_09"),
        _p(panel_lineas_por_documento(13), "a_msr_10"),
    ],

    "a_kpi_articulos_mas_vendidos": [
        _p(panel_articulos_mas_vendidos(), "a_amv_01"),
        _p(panel_stock_articulos(), "a_amv_02"),
        _p(panel_articulos_sin_stock(), "a_amv_03"),
        _p(panel_familias_productos(), "a_amv_04"),
        _p(panel_precio_vs_coste(), "a_amv_05"),
        _p(panel_proveedores_activos(), "a_amv_06"),
        _p(panel_articulos_sin_proveedor(), "a_amv_07"),
        _p(panel_articulos_baja(), "a_amv_08"),
        _p(panel_lineas_sin_articulo(), "a_amv_09"),
        _p(panel_lineas_por_documento(13), "a_amv_10"),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # FINANZAS — KPI Y TESORERÍA
    # ══════════════════════════════════════════════════════════════════════════

    "f_kpi_saldo_caja": [
        _p(panel_caja_resumen(), "f_sc_01"),
        _p(panel_caja_por_mes(), "f_sc_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_sc_03"),
        _p(panel_comparativa_anual(13), "f_sc_04"),
        _p(panel_iva_desglose(13), "f_sc_05"),
        _p(panel_iva_por_documento(13), "f_sc_06"),
        _p(panel_importes_anomalos(13), "f_sc_07"),
        _p(panel_sin_duplicados(13), "f_sc_08"),
        _p(panel_formas_pago(), "f_sc_09"),
        _p(panel_ventas_vs_compras_mensual(), "f_sc_10"),
    ],

    "f_kpi_cobros_mes": [
        _p(panel_caja_resumen(), "f_cm_01"),
        _p(panel_caja_por_mes(), "f_cm_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_cm_03"),
        _p(panel_comparativa_anual(13), "f_cm_04"),
        _p(panel_iva_desglose(13), "f_cm_05"),
        _p(panel_iva_por_documento(13), "f_cm_06"),
        _p(panel_importes_anomalos(13), "f_cm_07"),
        _p(panel_sin_duplicados(13), "f_cm_08"),
        _p(panel_formas_pago(), "f_cm_09"),
        _p(panel_ventas_vs_compras_mensual(), "f_cm_10"),
    ],

    "f_kpi_pagos_mes": [
        _p(panel_caja_resumen(), "f_pm_01"),
        _p(panel_caja_por_mes(), "f_pm_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_pm_03"),
        _p(panel_comparativa_anual(13), "f_pm_04"),
        _p(panel_iva_desglose(13), "f_pm_05"),
        _p(panel_iva_por_documento(13), "f_pm_06"),
        _p(panel_importes_anomalos(13), "f_pm_07"),
        _p(panel_sin_duplicados(13), "f_pm_08"),
        _p(panel_formas_pago(), "f_pm_09"),
        _p(panel_ventas_vs_compras_mensual(), "f_pm_10"),
    ],

    "f_kpi_margen_bruto_estimado": [
        _p(panel_precio_vs_coste(), "f_mbe_01"),
        _p(panel_articulos_mas_vendidos(), "f_mbe_02"),
        _p(panel_familias_productos(), "f_mbe_03"),
        _p(panel_stock_articulos(), "f_mbe_04"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_mbe_05"),
        _p(panel_comparativa_anual(13), "f_mbe_06"),
        _p(panel_iva_desglose(13), "f_mbe_07"),
        _p(panel_iva_por_documento(13), "f_mbe_08"),
        _p(panel_importes_anomalos(13), "f_mbe_09"),
        _p(panel_ventas_vs_compras_mensual(), "f_mbe_10"),
    ],

    "f_kpi_evolucion_caja_mensual": [
        _p(panel_caja_por_mes(), "f_ecm_01"),
        _p(panel_caja_resumen(), "f_ecm_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_ecm_03"),
        _p(panel_comparativa_anual(13), "f_ecm_04"),
        _p(panel_iva_desglose(13), "f_ecm_05"),
        _p(panel_iva_por_documento(13), "f_ecm_06"),
        _p(panel_importes_anomalos(13), "f_ecm_07"),
        _p(panel_sin_duplicados(13), "f_ecm_08"),
        _p(panel_formas_pago(), "f_ecm_09"),
        _p(panel_ventas_vs_compras_mensual(), "f_ecm_10"),
    ],

    "f_riesgo_facturas_alto_importe_sin_cobrar": [
        _p(panel_clientes_por_facturacion(13), "f_rfaisc_01"),
        _p(panel_concentracion_top5(13), "f_rfaisc_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_rfaisc_03"),
        _p(panel_comparativa_anual(13), "f_rfaisc_04"),
        _p(panel_importes_anomalos(13), "f_rfaisc_05"),
        _p(panel_sin_duplicados(13), "f_rfaisc_06"),
        _p(panel_antiguedad_documentos(13, "facturas"), "f_rfaisc_07"),
        _p(panel_iva_desglose(13), "f_rfaisc_08"),
        _p(panel_iva_por_documento(13), "f_rfaisc_09"),
        _p(panel_caja_resumen(), "f_rfaisc_10"),
    ],

    "f_ahorro_descuentos_excesivos": [
        _p(panel_descuentos_aplicados(13), "f_ade_01"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_ade_02"),
        _p(panel_comparativa_anual(13), "f_ade_03"),
        _p(panel_clientes_por_facturacion(13), "f_ade_04"),
        _p(panel_importes_anomalos(13), "f_ade_05"),
        _p(panel_sin_duplicados(13), "f_ade_06"),
        _p(panel_agentes_ventas(), "f_ade_07"),
        _p(panel_precio_vs_coste(), "f_ade_08"),
        _p(panel_iva_desglose(13), "f_ade_09"),
        _p(panel_iva_por_documento(13), "f_ade_10"),
    ],

    "f_kpi_ratio_cobros_pagos": [
        _p(panel_caja_resumen(), "f_rcp_01"),
        _p(panel_caja_por_mes(), "f_rcp_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_rcp_03"),
        _p(panel_comparativa_anual(13), "f_rcp_04"),
        _p(panel_iva_desglose(13), "f_rcp_05"),
        _p(panel_iva_por_documento(13), "f_rcp_06"),
        _p(panel_importes_anomalos(13), "f_rcp_07"),
        _p(panel_sin_duplicados(13), "f_rcp_08"),
        _p(panel_formas_pago(), "f_rcp_09"),
        _p(panel_ventas_vs_compras_mensual(), "f_rcp_10"),
    ],

    "f_kpi_movimientos_caja_recientes": [
        _p(panel_caja_resumen(), "f_mcr_01"),
        _p(panel_caja_por_mes(), "f_mcr_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "f_mcr_03"),
        _p(panel_comparativa_anual(13), "f_mcr_04"),
        _p(panel_iva_desglose(13), "f_mcr_05"),
        _p(panel_iva_por_documento(13), "f_mcr_06"),
        _p(panel_importes_anomalos(13), "f_mcr_07"),
        _p(panel_sin_duplicados(13), "f_mcr_08"),
        _p(panel_formas_pago(), "f_mcr_09"),
        _p(panel_ventas_vs_compras_mensual(), "f_mcr_10"),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # SAT — SERVICIO TÉCNICO
    # ══════════════════════════════════════════════════════════════════════════

    "s_kpi_sats_mes": [
        _p(panel_sats_por_estado(), "s_sm_01"),
        _p(panel_evolucion_mensual(2, "SATs"), "s_sm_02"),
        _p(panel_comparativa_anual(2), "s_sm_03"),
        _p(panel_clientes_por_facturacion(2), "s_sm_04"),
        _p(panel_importes_anomalos(2), "s_sm_05"),
        _p(panel_sin_duplicados(2), "s_sm_06"),
        _p(panel_documentos_sin_fecha(2), "s_sm_07"),
        _p(panel_antiguedad_documentos(2, "SATs"), "s_sm_08"),
        _p(panel_desglose_tipos(), "s_sm_09"),
        _p(panel_ultimos_documentos(2, "SATs", 20), "s_sm_10"),
    ],

    "s_kpi_clientes_con_mas_sats": [
        _p(panel_clientes_por_facturacion(2), "s_scms_01"),
        _p(panel_sats_por_estado(), "s_scms_02"),
        _p(panel_evolucion_mensual(2, "SATs"), "s_scms_03"),
        _p(panel_comparativa_anual(2), "s_scms_04"),
        _p(panel_importes_anomalos(2), "s_scms_05"),
        _p(panel_sin_duplicados(2), "s_scms_06"),
        _p(panel_documentos_sin_fecha(2), "s_scms_07"),
        _p(panel_antiguedad_documentos(2, "SATs"), "s_scms_08"),
        _p(panel_desglose_tipos(), "s_scms_09"),
        _p(panel_ultimos_documentos(2, "SATs", 20), "s_scms_10"),
    ],

    "s_kpi_sats_por_mes": [
        _p(panel_evolucion_mensual(2, "SATs"), "s_spm_01"),
        _p(panel_comparativa_anual(2), "s_spm_02"),
        _p(panel_sats_por_estado(), "s_spm_03"),
        _p(panel_clientes_por_facturacion(2), "s_spm_04"),
        _p(panel_importes_anomalos(2), "s_spm_05"),
        _p(panel_sin_duplicados(2), "s_spm_06"),
        _p(panel_documentos_sin_fecha(2), "s_spm_07"),
        _p(panel_antiguedad_documentos(2, "SATs"), "s_spm_08"),
        _p(panel_desglose_tipos(), "s_spm_09"),
        _p(panel_ultimos_documentos(2, "SATs", 20), "s_spm_10"),
    ],

    "s_riesgo_sats_sin_facturar": [
        _p(panel_sats_por_estado(), "s_rssf_01"),
        _p(panel_evolucion_mensual(2, "SATs"), "s_rssf_02"),
        _p(panel_comparativa_anual(2), "s_rssf_03"),
        _p(panel_clientes_por_facturacion(2), "s_rssf_04"),
        _p(panel_importes_anomalos(2), "s_rssf_05"),
        _p(panel_sin_duplicados(2), "s_rssf_06"),
        _p(panel_documentos_sin_fecha(2), "s_rssf_07"),
        _p(panel_antiguedad_documentos(2, "SATs"), "s_rssf_08"),
        _p(panel_desglose_tipos(), "s_rssf_09"),
        _p(panel_ultimos_documentos(2, "SATs", 20), "s_rssf_10"),
    ],

    "s_opt_productos_mas_usados_en_sat": [
        _p(panel_articulos_mas_vendidos(), "s_opmus_01"),
        _p(panel_stock_articulos(), "s_opmus_02"),
        _p(panel_articulos_sin_stock(), "s_opmus_03"),
        _p(panel_familias_productos(), "s_opmus_04"),
        _p(panel_precio_vs_coste(), "s_opmus_05"),
        _p(panel_proveedores_activos(), "s_opmus_06"),
        _p(panel_articulos_sin_proveedor(), "s_opmus_07"),
        _p(panel_lineas_sin_articulo(), "s_opmus_08"),
        _p(panel_sats_por_estado(), "s_opmus_09"),
        _p(panel_evolucion_mensual(2, "SATs"), "s_opmus_10"),
    ],

    "s_kpi_sats_abiertos_antiguos": [
        _p(panel_sats_por_estado(), "s_saa_01"),
        _p(panel_evolucion_mensual(2, "SATs"), "s_saa_02"),
        _p(panel_comparativa_anual(2), "s_saa_03"),
        _p(panel_clientes_por_facturacion(2), "s_saa_04"),
        _p(panel_importes_anomalos(2), "s_saa_05"),
        _p(panel_sin_duplicados(2), "s_saa_06"),
        _p(panel_documentos_sin_fecha(2), "s_saa_07"),
        _p(panel_antiguedad_documentos(2, "SATs"), "s_saa_08"),
        _p(panel_desglose_tipos(), "s_saa_09"),
        _p(panel_ultimos_documentos(2, "SATs", 20), "s_saa_10"),
    ],

    "s_kpi_facturacion_sat_vs_instalacion": [
        _p(panel_desglose_tipos(), "s_sfvsi_01"),
        _p(panel_evolucion_mensual(2, "SATs"), "s_sfvsi_02"),
        _p(panel_evolucion_mensual(13, "facturas"), "s_sfvsi_03"),
        _p(panel_comparativa_anual(13), "s_sfvsi_04"),
        _p(panel_importes_anomalos(13), "s_sfvsi_05"),
        _p(panel_sin_duplicados(13), "s_sfvsi_06"),
        _p(panel_iva_desglose(13), "s_sfvsi_07"),
        _p(panel_iva_por_documento(13), "s_sfvsi_08"),
        _p(panel_agentes_ventas(), "s_sfvsi_09"),
        _p(panel_ventas_vs_compras_mensual(), "s_sfvsi_10"),
    ],
}


def get_verifications_for_query(query_id: str) -> List[Dict[str, Any]]:
    """
    Devuelve la lista de paneles de verificación para una consulta.

    Prioridad:
    1. Paneles específicos del registro (_REGISTRY) — máxima precisión.
    2. Paneles auto-generados basados en los metadatos de la consulta.
    3. Lista vacía si no se puede obtener la consulta.

    Garantiza exactamente STANDARD_PANEL_COUNT paneles.
    """
    # 1. Paneles específicos del registro
    if query_id in _REGISTRY:
        return _REGISTRY[query_id][:STANDARD_PANEL_COUNT]

    # 2. Auto-generación basada en metadatos de la consulta
    try:
        from backend.modules.db_simulator.query_library import get_query_by_id
        from backend.modules.db_simulator.justification.auto_panels import generate_auto_panels
        query = get_query_by_id(query_id)
        if query:
            return generate_auto_panels(query)[:STANDARD_PANEL_COUNT]
    except Exception:
        pass

    # 3. Sin paneles disponibles
    return []
