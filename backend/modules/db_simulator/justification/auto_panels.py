"""
justification/auto_panels.py — Generador automático de 10 paneles de justificación.

Para consultas sin paneles específicos en el registro, genera automáticamente
10 paneles relevantes basados en los metadatos de la consulta (dept, tipo, sql).

PRINCIPIO: Sin comentarios subjetivos. Solo hechos verificables con datos.
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

# ─── Constantes ───────────────────────────────────────────────────────────────

STANDARD_PANEL_COUNT = 10

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _p(panel_dict: Dict[str, Any], unique_id: str) -> Dict[str, Any]:
    """Clona un panel y le asigna un id único."""
    result = dict(panel_dict)
    result["id"] = unique_id
    return result


def _detect_tipo_from_sql(sql: str) -> int:
    """Detecta el TIPO de documento predominante en el SQL."""
    sql_upper = sql.upper()
    if "TIPO=13" in sql_upper or "TIPO = 13" in sql_upper:
        return 13
    if "TIPO=0" in sql_upper or "TIPO = 0" in sql_upper:
        return 0
    if "TIPO=11" in sql_upper or "TIPO = 11" in sql_upper:
        return 11
    if "TIPO=2" in sql_upper or "TIPO = 2" in sql_upper:
        return 2
    if "TIPO=12" in sql_upper or "TIPO = 12" in sql_upper:
        return 12
    return 13  # default: facturas de venta


def _detect_uses_articulo(sql: str) -> bool:
    """Detecta si el SQL usa la tabla ARTICULO."""
    return "ARTICULO" in sql.upper()


def _detect_uses_caja(sql: str) -> bool:
    """Detecta si el SQL usa la tabla CAJA."""
    return "CAJA" in sql.upper()


def _detect_uses_cliente(sql: str) -> bool:
    """Detecta si el SQL usa la tabla CLIENTE."""
    return "CLIENTE" in sql.upper()


def _detect_uses_proveed(sql: str) -> bool:
    """Detecta si el SQL usa la tabla PROVEED."""
    return "PROVEED" in sql.upper()


# ─── Conjuntos de paneles por contexto ────────────────────────────────────────

def _panels_ventas(tipo: int, prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de ventas/facturación."""
    label = {13: "facturas", 0: "presupuestos", 11: "albaranes", 2: "SATs"}.get(tipo, "documentos")
    return [
        _p(panel_desglose_tipos(),                    f"{prefix}_01"),
        _p(panel_sin_duplicados(tipo),                f"{prefix}_02"),
        _p(panel_evolucion_mensual(tipo, label),      f"{prefix}_03"),
        _p(panel_comparativa_anual(tipo),             f"{prefix}_04"),
        _p(panel_importes_anomalos(tipo),             f"{prefix}_05"),
        _p(panel_clientes_por_facturacion(tipo),      f"{prefix}_06"),
        _p(panel_ultimos_documentos(tipo, label, 20), f"{prefix}_07"),
        _p(panel_iva_desglose(tipo),                  f"{prefix}_08"),
        _p(panel_agentes_ventas(),                    f"{prefix}_09"),
        _p(panel_formas_pago(),                       f"{prefix}_10"),
    ]


def _panels_clientes(tipo: int, prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas centradas en clientes."""
    label = {13: "facturas", 0: "presupuestos", 11: "albaranes", 2: "SATs"}.get(tipo, "documentos")
    return [
        _p(panel_clientes_activos(tipo),              f"{prefix}_01"),
        _p(panel_clientes_sin_nombre(),               f"{prefix}_02"),
        _p(panel_concentracion_top5(tipo),            f"{prefix}_03"),
        _p(panel_clientes_por_facturacion(tipo),      f"{prefix}_04"),
        _p(panel_evolucion_mensual(tipo, label),      f"{prefix}_05"),
        _p(panel_comparativa_anual(tipo),             f"{prefix}_06"),
        _p(panel_importes_anomalos(tipo),             f"{prefix}_07"),
        _p(panel_sin_duplicados(tipo),                f"{prefix}_08"),
        _p(panel_agentes_ventas(),                    f"{prefix}_09"),
        _p(panel_ultimos_documentos(tipo, label, 20), f"{prefix}_10"),
    ]


def _panels_articulos(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de artículos/stock."""
    return [
        _p(panel_articulos_mas_vendidos(),   f"{prefix}_01"),
        _p(panel_stock_articulos(),          f"{prefix}_02"),
        _p(panel_articulos_sin_stock(),      f"{prefix}_03"),
        _p(panel_familias_productos(),       f"{prefix}_04"),
        _p(panel_precio_vs_coste(),          f"{prefix}_05"),
        _p(panel_proveedores_activos(),      f"{prefix}_06"),
        _p(panel_articulos_sin_proveedor(),  f"{prefix}_07"),
        _p(panel_articulos_baja(),           f"{prefix}_08"),
        _p(panel_lineas_sin_articulo(),      f"{prefix}_09"),
        _p(panel_lineas_por_documento(13),   f"{prefix}_10"),
    ]


def _panels_caja(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de caja/tesorería."""
    return [
        _p(panel_caja_resumen(),                      f"{prefix}_01"),
        _p(panel_caja_por_mes(),                      f"{prefix}_02"),
        _p(panel_ventas_vs_compras_mensual(),         f"{prefix}_03"),
        _p(panel_evolucion_mensual(13, "facturas"),   f"{prefix}_04"),
        _p(panel_comparativa_anual(13),               f"{prefix}_05"),
        _p(panel_iva_desglose(13),                    f"{prefix}_06"),
        _p(panel_iva_por_documento(13),               f"{prefix}_07"),
        _p(panel_importes_anomalos(13),               f"{prefix}_08"),
        _p(panel_sin_duplicados(13),                  f"{prefix}_09"),
        _p(panel_formas_pago(),                       f"{prefix}_10"),
    ]


def _panels_proveedores(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de proveedores/compras."""
    return [
        _p(panel_proveedores_activos(),              f"{prefix}_01"),
        _p(panel_articulos_sin_proveedor(),          f"{prefix}_02"),
        _p(panel_familias_productos(),               f"{prefix}_03"),
        _p(panel_precio_vs_coste(),                  f"{prefix}_04"),
        _p(panel_stock_articulos(),                  f"{prefix}_05"),
        _p(panel_articulos_sin_stock(),              f"{prefix}_06"),
        _p(panel_articulos_baja(),                   f"{prefix}_07"),
        _p(panel_lineas_sin_articulo(),              f"{prefix}_08"),
        _p(panel_articulos_mas_vendidos(),           f"{prefix}_09"),
        _p(panel_lineas_por_documento(13),           f"{prefix}_10"),
    ]


def _panels_sat(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de SAT/servicio técnico."""
    return [
        _p(panel_sats_por_estado(),                  f"{prefix}_01"),
        _p(panel_evolucion_mensual(2, "SATs"),       f"{prefix}_02"),
        _p(panel_comparativa_anual(2),               f"{prefix}_03"),
        _p(panel_clientes_por_facturacion(2),        f"{prefix}_04"),
        _p(panel_importes_anomalos(2),               f"{prefix}_05"),
        _p(panel_sin_duplicados(2),                  f"{prefix}_06"),
        _p(panel_documentos_sin_fecha(2),            f"{prefix}_07"),
        _p(panel_antiguedad_documentos(2, "SATs"),   f"{prefix}_08"),
        _p(panel_desglose_tipos(),                   f"{prefix}_09"),
        _p(panel_ultimos_documentos(2, "SATs", 20), f"{prefix}_10"),
    ]


def _panels_presupuestos(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de presupuestos."""
    return [
        _p(panel_presupuestos_por_estado(),              f"{prefix}_01"),
        _p(panel_evolucion_mensual(0, "presupuestos"),   f"{prefix}_02"),
        _p(panel_comparativa_anual(0),                   f"{prefix}_03"),
        _p(panel_clientes_por_facturacion(0),            f"{prefix}_04"),
        _p(panel_importes_anomalos(0),                   f"{prefix}_05"),
        _p(panel_sin_duplicados(0),                      f"{prefix}_06"),
        _p(panel_documentos_sin_fecha(0),                f"{prefix}_07"),
        _p(panel_antiguedad_documentos(0, "presupuestos"), f"{prefix}_08"),
        _p(panel_concentracion_top5(0),                  f"{prefix}_09"),
        _p(panel_ultimos_documentos(0, "presupuestos", 20), f"{prefix}_10"),
    ]


def _panels_albaranes(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de albaranes."""
    return [
        _p(panel_albaranes_vs_facturas(),                f"{prefix}_01"),
        _p(panel_evolucion_mensual(11, "albaranes"),     f"{prefix}_02"),
        _p(panel_comparativa_anual(11),                  f"{prefix}_03"),
        _p(panel_clientes_por_facturacion(11),           f"{prefix}_04"),
        _p(panel_importes_anomalos(11),                  f"{prefix}_05"),
        _p(panel_sin_duplicados(11),                     f"{prefix}_06"),
        _p(panel_documentos_sin_fecha(11),               f"{prefix}_07"),
        _p(panel_antiguedad_documentos(11, "albaranes"), f"{prefix}_08"),
        _p(panel_desglose_tipos(),                       f"{prefix}_09"),
        _p(panel_ultimos_documentos(11, "albaranes", 20), f"{prefix}_10"),
    ]


def _panels_margen(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de margen/rentabilidad."""
    return [
        _p(panel_precio_vs_coste(),                  f"{prefix}_01"),
        _p(panel_articulos_mas_vendidos(),           f"{prefix}_02"),
        _p(panel_familias_productos(),               f"{prefix}_03"),
        _p(panel_descuentos_aplicados(13),           f"{prefix}_04"),
        _p(panel_evolucion_mensual(13, "facturas"),  f"{prefix}_05"),
        _p(panel_comparativa_anual(13),              f"{prefix}_06"),
        _p(panel_iva_desglose(13),                   f"{prefix}_07"),
        _p(panel_iva_por_documento(13),              f"{prefix}_08"),
        _p(panel_importes_anomalos(13),              f"{prefix}_09"),
        _p(panel_ventas_vs_compras_mensual(),        f"{prefix}_10"),
    ]


def _panels_calidad(prefix: str) -> List[Dict[str, Any]]:
    """10 paneles para consultas de calidad de datos."""
    return [
        _p(panel_desglose_tipos(),                   f"{prefix}_01"),
        _p(panel_documentos_sin_fecha(13),           f"{prefix}_02"),
        _p(panel_documentos_sin_cliente(13),         f"{prefix}_03"),
        _p(panel_sin_duplicados(13),                 f"{prefix}_04"),
        _p(panel_importes_anomalos(13),              f"{prefix}_05"),
        _p(panel_lineas_sin_articulo(),              f"{prefix}_06"),
        _p(panel_articulos_sin_proveedor(),          f"{prefix}_07"),
        _p(panel_articulos_baja(),                   f"{prefix}_08"),
        _p(panel_clientes_sin_nombre(),              f"{prefix}_09"),
        _p(panel_iva_desglose(13),                   f"{prefix}_10"),
    ]


def _panels_generic(tipo: int, prefix: str) -> List[Dict[str, Any]]:
    """10 paneles genéricos para cualquier consulta."""
    label = {13: "facturas", 0: "presupuestos", 11: "albaranes", 2: "SATs"}.get(tipo, "documentos")
    return [
        _p(panel_desglose_tipos(),                    f"{prefix}_01"),
        _p(panel_evolucion_mensual(tipo, label),      f"{prefix}_02"),
        _p(panel_comparativa_anual(tipo),             f"{prefix}_03"),
        _p(panel_sin_duplicados(tipo),                f"{prefix}_04"),
        _p(panel_importes_anomalos(tipo),             f"{prefix}_05"),
        _p(panel_clientes_por_facturacion(tipo),      f"{prefix}_06"),
        _p(panel_ultimos_documentos(tipo, label, 20), f"{prefix}_07"),
        _p(panel_iva_desglose(tipo),                  f"{prefix}_08"),
        _p(panel_agentes_ventas(),                    f"{prefix}_09"),
        _p(panel_formas_pago(),                       f"{prefix}_10"),
    ]


# ─── Función principal ────────────────────────────────────────────────────────

def generate_auto_panels(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Genera automáticamente 10 paneles de justificación para una consulta.

    Selecciona el conjunto de paneles más relevante según:
    1. El SQL de la consulta (detecta tablas y tipos usados)
    2. El departamento (dept)
    3. El tipo de análisis (tipo)

    Garantiza exactamente STANDARD_PANEL_COUNT paneles.
    """
    query_id = query.get("id", "unknown")
    sql = query.get("sql", "")
    dept = query.get("dept", "")
    tipo_analisis = query.get("tipo", "")

    # Prefijo único basado en el ID de la consulta (primeros 8 chars)
    prefix = f"auto_{query_id[:8].replace('-', '_')}"

    # Detectar contexto del SQL
    tipo_doc = _detect_tipo_from_sql(sql)
    uses_articulo = _detect_uses_articulo(sql)
    uses_caja = _detect_uses_caja(sql)
    uses_proveed = _detect_uses_proveed(sql)

    # Normalizar dept a string para comparación
    dept_str = dept if isinstance(dept, str) else (dept[0] if dept else "")

    # Seleccionar conjunto de paneles según contexto
    sql_upper = sql.upper()

    # Calidad de datos
    if tipo_analisis in ("Calidad",) or "qx_" in query_id:
        return _panels_calidad(prefix)[:STANDARD_PANEL_COUNT]

    # SAT / Servicio técnico
    if "SAT" in dept_str.upper() or tipo_doc == 2 or "TIPO=2" in sql_upper:
        return _panels_sat(prefix)[:STANDARD_PANEL_COUNT]

    # Presupuestos
    if "TIPO=0" in sql_upper and "TIPO=13" not in sql_upper:
        return _panels_presupuestos(prefix)[:STANDARD_PANEL_COUNT]

    # Albaranes
    if "TIPO=11" in sql_upper and "TIPO=13" not in sql_upper:
        return _panels_albaranes(prefix)[:STANDARD_PANEL_COUNT]

    # Caja / Tesorería / Finanzas
    if uses_caja or "FINANZ" in dept_str.upper() or "CAJA" in sql_upper:
        return _panels_caja(prefix)[:STANDARD_PANEL_COUNT]

    # Proveedores / Compras
    if uses_proveed or "COMPRAS" in dept_str.upper() or "PROVEED" in sql_upper:
        return _panels_proveedores(prefix)[:STANDARD_PANEL_COUNT]

    # Artículos / Stock / Almacén
    if uses_articulo and "ALMAC" in dept_str.upper():
        return _panels_articulos(prefix)[:STANDARD_PANEL_COUNT]

    # Margen / Rentabilidad
    if tipo_analisis in ("Ahorro",) or "MARGEN" in sql_upper or "DESCUENTO" in sql_upper:
        return _panels_margen(prefix)[:STANDARD_PANEL_COUNT]

    # Clientes
    if "CLIENTE" in sql_upper and tipo_doc == 13:
        return _panels_clientes(tipo_doc, prefix)[:STANDARD_PANEL_COUNT]

    # Artículos (sin almacén específico)
    if uses_articulo:
        return _panels_articulos(prefix)[:STANDARD_PANEL_COUNT]

    # Ventas (default para TIPO=13)
    if tipo_doc == 13:
        return _panels_ventas(tipo_doc, prefix)[:STANDARD_PANEL_COUNT]

    # Genérico
    return _panels_generic(tipo_doc, prefix)[:STANDARD_PANEL_COUNT]
