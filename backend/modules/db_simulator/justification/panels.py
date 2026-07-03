"""
justification/panels.py — Paneles de justificación reutilizables.

Cada función devuelve un dict con la estructura estándar de verificación:
  {id, label, justificacion, sql, icono, tipo, max_rows}

PRINCIPIO: Sin comentarios subjetivos. Solo hechos verificables con datos.
DEVIA: backend/modules/db_simulator/DEVIA.md

COMPATIBILIDAD FIREBIRD:
  - No usar CAST(x AS TEXT) — Firebird no tiene tipo TEXT. Usar VARCHAR(N).
  - No usar COALESCE(VARCHAR_col, BLOB_col) — tipos incompatibles en Firebird.
    ARTICULO.DESCRIPCION es BLOB — nunca mezclar con VARCHAR en COALESCE.
  - ARTICULO.PRECIO no existe en Firebird — usar PRECIOVENTA.
  - ARTICULO.CODPROVEEDOR no existe en Firebird — usar PROVEEDDEFECTO.
  - DOCCAB.IMPORTEBASE (no BASEIMPONIBLE), DOCCAB.IMPORTEIVA (no IVA).
  - DOCLIN.CODARTICULO es INTEGER en Firebird — no comparar con ''.
  - CODCLIENTE, CODAGENTE son INTEGER — no comparar con ''.
"""

from typing import Dict, Any

# ─── Helpers SQL ──────────────────────────────────────────────────────────────

# VARCHAR(20) para CAST de enteros — Firebird no tiene tipo TEXT.
# Solo NOMBRECOMERCIAL/RAZONSOCIAL (VARCHAR) — nunca DESCRIPCION (BLOB).
_CLIENTE_NOMBRE = (
    "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, CAST(D.CODCLIENTE AS VARCHAR(20)))"
)
_PROVEEDOR_NOMBRE = (
    "COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL, CAST(P.CODIGO AS VARCHAR(20)))"
)
# Solo A.NOMBRE (VARCHAR) — A.DESCRIPCION es BLOB en Firebird, incompatible con COALESCE
_ARTICULO_NOMBRE = "COALESCE(A.NOMBRE, CAST(A.CODIGO AS VARCHAR(50)))"


# ─── Paneles de documentos ────────────────────────────────────────────────────

def panel_desglose_tipos() -> Dict[str, Any]:
    """Desglose de todos los tipos de documento en DOCCAB."""
    return {
        "id": "px_tipos_documento",
        "label": "Desglose de todos los tipos de documento",
        "justificacion": (
            "Muestra cuántos documentos hay de cada TIPO en DOCCAB. "
            "Confirma que el filtro de la consulta principal es correcto "
            "y que no se mezclan facturas (13), albaranes (11), presupuestos (0) ni SATs (2)."
        ),
        "sql": (
            "SELECT TIPO, COUNT(*) AS N_DOCS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB GROUP BY TIPO ORDER BY N_DOCS DESC"
        ),
        "icono": "📋",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_sin_duplicados(tipo_num: int) -> Dict[str, Any]:
    """Verifica que no hay códigos duplicados para un tipo de documento."""
    return {
        "id": "px_sin_duplicados",
        "label": f"Sin duplicados de CODIGO (TIPO={tipo_num})",
        "justificacion": (
            f"Comprueba que no hay dos documentos TIPO={tipo_num} con el mismo CODIGO. "
            "Si aparece algún CODIGO con N>1, existe un duplicado que inflaría los totales. "
            "El resultado debe estar vacío."
        ),
        "sql": (
            f"SELECT CODIGO, COUNT(*) AS N FROM DOCCAB WHERE TIPO={tipo_num} "
            "GROUP BY CODIGO HAVING COUNT(*) > 1 ORDER BY N DESC LIMIT 20"
        ),
        "icono": "🔁",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_evolucion_mensual(tipo_num: int, label: str = "documentos") -> Dict[str, Any]:
    """Evolución mensual de documentos de un tipo."""
    return {
        "id": "px_evolucion_mensual",
        "label": f"Evolución mensual de {label} (últimos 24 meses)",
        "justificacion": (
            f"Distribución de {label} por mes. "
            "Permite detectar meses con importe 0 o muy bajo que merecen revisión."
        ),
        "sql": (
            f"SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N, "
            f"ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            f"FROM DOCCAB WHERE TIPO={tipo_num} AND FECHA IS NOT NULL "
            "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 24"
        ),
        "icono": "📅",
        "tipo": "tabla",
        "max_rows": 24,
    }


def panel_comparativa_anual(tipo_num: int) -> Dict[str, Any]:
    """Comparativa anual de documentos."""
    return {
        "id": "px_comparativa_anual",
        "label": "Comparativa anual (total por año)",
        "justificacion": (
            "Agrupa por año para ver la tendencia a largo plazo. "
            "Un año con cifra muy diferente a los demás puede indicar un error de importación."
        ),
        "sql": (
            f"SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N, "
            f"ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            f"FROM DOCCAB WHERE TIPO={tipo_num} AND FECHA IS NOT NULL "
            "GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC"
        ),
        "icono": "📆",
        "tipo": "tabla",
        "max_rows": 10,
    }


def panel_importes_anomalos(tipo_num: int) -> Dict[str, Any]:
    """Documentos con importe cero o negativo."""
    return {
        "id": "px_importes_anomalos",
        "label": "Documentos con importe ≤ 0",
        "justificacion": (
            "Documentos con IMPORTETOTAL <= 0 pueden ser abonos, errores "
            "o documentos rectificativos. Reducen el total y deben revisarse individualmente."
        ),
        "sql": (
            f"SELECT CODIGO, CODCLIENTE, FECHA, IMPORTETOTAL "
            f"FROM DOCCAB WHERE TIPO={tipo_num} AND IMPORTETOTAL <= 0 "
            "ORDER BY IMPORTETOTAL ASC LIMIT 20"
        ),
        "icono": "⚠️",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_ultimos_documentos(
    tipo_num: int, label: str = "documentos", n: int = 30
) -> Dict[str, Any]:
    """Últimos N documentos de un tipo."""
    return {
        "id": "px_ultimos_docs",
        "label": f"Últimos {n} {label} (más recientes)",
        "justificacion": (
            f"Los {n} {label} más recientes ordenados por fecha. "
            "Permite verificar que los documentos tienen cliente asignado, "
            "fecha válida e importe coherente."
        ),
        # _CLIENTE_NOMBRE usa VARCHAR(20) — compatible con Firebird
        "sql": (
            f"SELECT D.CODIGO, {_CLIENTE_NOMBRE} AS CLIENTE, "
            f"D.FECHA, ROUND(D.IMPORTETOTAL,2) AS IMPORTE "
            f"FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
            f"WHERE D.TIPO={tipo_num} ORDER BY D.FECHA DESC LIMIT {n}"
        ),
        "icono": "📋",
        "tipo": "tabla",
        "max_rows": n,
    }


def panel_documentos_sin_fecha(tipo_num: int) -> Dict[str, Any]:
    """Documentos sin fecha."""
    return {
        "id": "px_sin_fecha",
        "label": "Documentos sin fecha asignada",
        "justificacion": (
            "Documentos sin FECHA no aparecen en los análisis temporales. "
            "Si hay muchos, los gráficos mensuales y anuales están incompletos."
        ),
        # Solo IS NULL: en Firebird, FECHA es DATE y no puede ser ''
        "sql": (
            f"SELECT COUNT(*) AS DOCS_SIN_FECHA "
            f"FROM DOCCAB WHERE TIPO={tipo_num} AND FECHA IS NULL"
        ),
        "icono": "D",
        "tipo": "resumen",
        "max_rows": 5,
    }


def panel_documentos_sin_cliente(tipo_num: int) -> Dict[str, Any]:
    """Documentos sin cliente asignado."""
    return {
        "id": "px_sin_cliente",
        "label": "Documentos sin cliente asignado",
        "justificacion": (
            "Documentos sin CODCLIENTE no se pueden atribuir a ningún cliente. "
            "Si hay muchos, hay un problema de importación de datos."
        ),
        # CODCLIENTE es INTEGER en Firebird: comparar con 0 o IS NULL, no con ''
        "sql": (
            f"SELECT COUNT(*) AS DOCS_SIN_CLIENTE "
            f"FROM DOCCAB WHERE TIPO={tipo_num} AND (CODCLIENTE IS NULL OR CODCLIENTE=0)"
        ),
        "icono": "W",
        "tipo": "resumen",
        "max_rows": 5,
    }


def panel_antiguedad_documentos(
    tipo_num: int, label: str = "documentos"
) -> Dict[str, Any]:
    """Distribución de documentos por año (sin JULIANDAY — no disponible en Firebird 2.5)."""
    return {
        "id": "px_antiguedad",
        "label": f"Distribución de {label} por año",
        "justificacion": (
            f"Distribución de {label} por año de emisión. "
            "Permite detectar documentos de años muy anteriores que podrían ser errores de importación. "
            "Se agrupa por SUBSTR(FECHA,1,4) — compatible con Firebird 2.5 y SQLite."
        ),
        # Sin JULIANDAY: Firebird 2.5 no tiene esta función.
        "sql": (
            f"SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N, "
            f"ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            f"FROM DOCCAB WHERE TIPO={tipo_num} AND FECHA IS NOT NULL "
            f"GROUP BY SUBSTR(FECHA,1,4) ORDER BY ANIO DESC LIMIT 10"
        ),
        "icono": "T",
        "tipo": "tabla",
        "max_rows": 10,
    }


# ─── Paneles de clientes ──────────────────────────────────────────────────────

def panel_clientes_por_facturacion(tipo_num: int = 13) -> Dict[str, Any]:
    """Top clientes por facturación."""
    return {
        "id": "px_clientes_facturacion",
        "label": "Top 20 clientes por facturación",
        "justificacion": (
            "Desglose por cliente. Permite detectar si un cliente concentra demasiado volumen "
            "o si hay clientes con importes anómalos."
        ),
        # GROUP BY incluye D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL
        # para compatibilidad con Firebird (no permite columnas no agregadas fuera del GROUP BY)
        "sql": (
            f"SELECT {_CLIENTE_NOMBRE} AS CLIENTE, "
            f"COUNT(D.CODIGO) AS N_DOCS, ROUND(SUM(D.IMPORTETOTAL),2) AS TOTAL "
            f"FROM DOCCAB D LEFT JOIN CLIENTE C ON D.CODCLIENTE=C.CODIGO "
            f"WHERE D.TIPO={tipo_num} "
            "GROUP BY D.CODCLIENTE, C.NOMBRECOMERCIAL, C.RAZONSOCIAL "
            "ORDER BY TOTAL DESC LIMIT 20"
        ),
        "icono": "👥",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_clientes_sin_nombre() -> Dict[str, Any]:
    """Clientes sin nombre asignado."""
    return {
        "id": "px_clientes_sin_nombre",
        "label": "Clientes sin nombre asignado",
        "justificacion": (
            "Clientes con NOMBRECOMERCIAL y RAZONSOCIAL vacíos tienen identificación deficiente. "
            "Sus documentos están incluidos en los totales pero no se pueden identificar."
        ),
        "sql": (
            "SELECT C.CODIGO, COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, '') AS NOMBRE "
            "FROM CLIENTE C "
            "WHERE (C.NOMBRECOMERCIAL IS NULL OR C.NOMBRECOMERCIAL='') "
            "AND (C.RAZONSOCIAL IS NULL OR C.RAZONSOCIAL='') LIMIT 20"
        ),
        "icono": "❓",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_clientes_activos(tipo_num: int = 13) -> Dict[str, Any]:
    """Total de clientes con al menos un documento."""
    return {
        "id": "px_clientes_activos",
        "label": "Total de clientes con al menos un documento",
        "justificacion": (
            f"Solo se cuentan clientes que tienen al menos un documento TIPO={tipo_num}. "
            "Los clientes sin documentos no aparecen en los análisis."
        ),
        "sql": (
            f"SELECT COUNT(DISTINCT CODCLIENTE) AS CLIENTES_ACTIVOS "
            f"FROM DOCCAB WHERE TIPO={tipo_num}"
        ),
        "icono": "✅",
        "tipo": "resumen",
        "max_rows": 5,
    }


def panel_concentracion_top5(tipo_num: int = 13) -> Dict[str, Any]:
    """Top 5 clientes por facturación (sin CTE, sin subqueries correlacionadas)."""
    return {
        "id": "px_concentracion_top5",
        "label": "Top 5 clientes por facturación (concentración)",
        "justificacion": (
            "Muestra los 5 clientes con mayor facturación. "
            "Comparar el TOTAL de cada cliente con el total general de la consulta principal "
            "para calcular el porcentaje de concentración."
        ),
        # Firebird 2.5: FIRST n en lugar de LIMIT n
        "sql": (
            f"SELECT FIRST 5 CODCLIENTE, COUNT(*) AS N_DOCS, "
            f"ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            f"FROM DOCCAB WHERE TIPO={tipo_num} "
            f"GROUP BY CODCLIENTE ORDER BY TOTAL DESC"
        ),
        "icono": "!",
        "tipo": "tabla",
        "max_rows": 5,
    }


# ─── Paneles de IVA y finanzas ────────────────────────────────────────────────

def panel_iva_desglose(tipo_num: int = 13) -> Dict[str, Any]:
    """Desglose de IVA: evidencia de que IMPORTETOTAL incluye IVA."""
    return {
        "id": "px_iva_desglose",
        "label": "Desglose IVA: IMPORTEBASE + IMPORTEIVA vs IMPORTETOTAL",
        "justificacion": (
            "Verifica la relación IMPORTEBASE + IMPORTEIVA vs IMPORTETOTAL. "
            "Si DIFERENCIA ≈ 0, IMPORTETOTAL = IMPORTEBASE + IMPORTEIVA (IVA incluido). "
            "Si DIFERENCIA ≈ TOTAL_IVA, IMPORTETOTAL = IMPORTEBASE (IVA no incluido). "
            "Este panel proporciona la evidencia numérica de cómo está configurado el sistema."
        ),
        # Firebird real: IMPORTEBASE, IMPORTEIVA (columnas reales de DOCCAB)
        "sql": (
            f"SELECT COUNT(*) AS N_DOCS, "
            f"ROUND(SUM(IMPORTEBASE),2) AS TOTAL_BASE, "
            f"ROUND(SUM(IMPORTEIVA),2) AS TOTAL_IVA, "
            f"ROUND(SUM(IMPORTETOTAL),2) AS TOTAL_FINAL, "
            f"ROUND(SUM(IMPORTETOTAL)-SUM(IMPORTEBASE)-SUM(IMPORTEIVA),2) AS DIFERENCIA "
            f"FROM DOCCAB WHERE TIPO={tipo_num}"
        ),
        "icono": "🧾",
        "tipo": "resumen",
        "max_rows": 5,
    }


def panel_iva_por_documento(tipo_num: int = 13) -> Dict[str, Any]:
    """Muestra IMPORTEBASE, IMPORTEIVA e IMPORTETOTAL por documento."""
    return {
        "id": "px_iva_por_doc",
        "label": "IMPORTEBASE, IMPORTEIVA e IMPORTETOTAL por documento (muestra)",
        "justificacion": (
            "Muestra los campos IMPORTEBASE, IMPORTEIVA e IMPORTETOTAL de los últimos 10 documentos. "
            "Permite verificar visualmente si IMPORTETOTAL = IMPORTEBASE + IMPORTEIVA "
            "o si IMPORTETOTAL = IMPORTEBASE (sin IVA)."
        ),
        # Firebird real: IMPORTEBASE, IMPORTEIVA (no BASEIMPONIBLE, IVA)
        "sql": (
            f"SELECT CODIGO, ROUND(IMPORTEBASE,2) AS BASE, "
            f"ROUND(IMPORTEIVA,2) AS IVA_IMPORTE, "
            f"ROUND(IMPORTETOTAL,2) AS TOTAL, "
            f"ROUND(IMPORTETOTAL - IMPORTEBASE - IMPORTEIVA, 2) AS DIFERENCIA "
            f"FROM DOCCAB WHERE TIPO={tipo_num} AND IMPORTEBASE > 0 "
            f"ORDER BY FECHA DESC LIMIT 10"
        ),
        "icono": "🧾",
        "tipo": "tabla",
        "max_rows": 10,
    }


def panel_caja_resumen() -> Dict[str, Any]:
    """Resumen de movimientos de caja."""
    return {
        "id": "px_caja_resumen",
        "label": "Resumen de movimientos de caja (cobros vs pagos)",
        "justificacion": (
            "Muestra el total de cobros (TIPO=1) y pagos (TIPO=2) en CAJA. "
            "El saldo neto debe ser coherente con la facturación y las compras registradas."
        ),
        "sql": (
            "SELECT TIPO, COUNT(*) AS N_MOVIMIENTOS, ROUND(SUM(IMPORTE),2) AS TOTAL "
            "FROM CAJA GROUP BY TIPO ORDER BY TIPO"
        ),
        "icono": "💰",
        "tipo": "tabla",
        "max_rows": 10,
    }


def panel_caja_por_mes() -> Dict[str, Any]:
    """Movimientos de caja por mes."""
    return {
        "id": "px_caja_por_mes",
        "label": "Movimientos de caja por mes (últimos 12)",
        "justificacion": (
            "Evolución mensual de los movimientos de caja. "
            "Permite detectar meses con actividad anómala o sin movimientos."
        ),
        "sql": (
            "SELECT SUBSTR(FECHA,1,7) AS MES, COUNT(*) AS N_MOVIMIENTOS, "
            "ROUND(SUM(CASE WHEN TIPO=1 THEN IMPORTE ELSE 0 END),2) AS COBROS, "
            "ROUND(SUM(CASE WHEN TIPO=2 THEN IMPORTE ELSE 0 END),2) AS PAGOS "
            "FROM CAJA WHERE FECHA IS NOT NULL "
            "GROUP BY SUBSTR(FECHA,1,7) ORDER BY MES DESC LIMIT 12"
        ),
        "icono": "📊",
        "tipo": "tabla",
        "max_rows": 12,
    }


# ─── Paneles de artículos y stock ─────────────────────────────────────────────

def panel_articulos_mas_vendidos() -> Dict[str, Any]:
    """Top artículos más vendidos por importe (via DOCLIN)."""
    return {
        "id": "px_articulos_mas_vendidos",
        "label": "Top 20 artículos más vendidos (por importe en líneas de factura)",
        "justificacion": (
            "Ranking de artículos por importe total en líneas de factura (DOCLIN JOIN DOCCAB TIPO=13). "
            "Importe = SUM(CANTIDAD * PRECIO) en DOCLIN. "
            "Permite verificar que los artículos con más ventas son los esperados."
        ),
        # ART.DESCRIPCION es BLOB en Firebird — no compatible con COALESCE(VARCHAR, BLOB).
        # Solo ART.NOMBRE (VARCHAR) con fallback a CAST(CODIGO AS VARCHAR(50)).
        "sql": (
            "SELECT COALESCE(ART.NOMBRE, CAST(LIN.CODARTICULO AS VARCHAR(50))) AS ARTICULO, "
            "COUNT(LIN.CODDOCUMENTO) AS N_LINEAS, "
            "ROUND(SUM(CAST(LIN.CANTIDAD AS REAL)*CAST(LIN.PRECIO AS REAL)),2) AS TOTAL "
            "FROM DOCLIN LIN "
            "LEFT JOIN ARTICULO ART ON LIN.CODARTICULO=ART.CODIGO "
            "JOIN DOCCAB CAB ON LIN.CODDOCUMENTO=CAB.CODIGO AND CAB.TIPO=13 "
            "GROUP BY LIN.CODARTICULO, ART.NOMBRE ORDER BY TOTAL DESC LIMIT 20"
        ),
        "icono": "P",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_stock_articulos() -> Dict[str, Any]:
    """Stock actual por artículo."""
    return {
        "id": "px_stock_articulos",
        "label": "Stock actual por artículo (top 20 con más stock)",
        "justificacion": (
            "Muestra el stock actual (STOCKARTICULO) de los artículos con más unidades. "
            "Permite verificar que el stock es coherente con las ventas y compras registradas."
        ),
        # A.DESCRIPCION es BLOB en Firebird — incompatible con COALESCE(VARCHAR, BLOB).
        # Solo A.NOMBRE (VARCHAR) con fallback a CAST(A.CODIGO AS VARCHAR(50)).
        # A.PRECIOVENTA en Firebird (columna real — A.PRECIO no existe en ARTICULO).
        "sql": (
            "SELECT COALESCE(A.NOMBRE, CAST(A.CODIGO AS VARCHAR(50))) AS ARTICULO, "
            "A.STOCKARTICULO AS STOCK, ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA "
            "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 "
            "ORDER BY A.STOCKARTICULO DESC LIMIT 20"
        ),
        "icono": "P",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_articulos_sin_stock() -> Dict[str, Any]:
    """Artículos con stock cero o negativo."""
    return {
        "id": "px_articulos_sin_stock",
        "label": "Artículos con stock = 0 o negativo",
        "justificacion": (
            "Artículos con STOCKARTICULO <= 0. "
            "Stock negativo indica error de registro que debe corregirse."
        ),
        # A.DESCRIPCION es BLOB en Firebird — incompatible con COALESCE(VARCHAR, BLOB).
        # A.PRECIOVENTA en Firebird (columna real — A.PRECIO no existe en ARTICULO).
        "sql": (
            "SELECT COALESCE(A.NOMBRE, CAST(A.CODIGO AS VARCHAR(50))) AS ARTICULO, "
            "A.STOCKARTICULO AS STOCK, ROUND(A.PRECIOVENTA,2) AS PRECIO "
            "FROM ARTICULO A WHERE A.STOCKARTICULO <= 0 "
            "ORDER BY A.STOCKARTICULO ASC LIMIT 30"
        ),
        "icono": "W",
        "tipo": "tabla",
        "max_rows": 30,
    }


def panel_articulos_baja() -> Dict[str, Any]:
    """Artículos dados de baja."""
    return {
        "id": "px_articulos_baja",
        "label": "Artículos dados de baja (BAJA=1)",
        "justificacion": (
            "Artículos con BAJA=1 están inactivos. Si aparecen en ventas recientes, "
            "indica que se vendieron artículos descatalogados."
        ),
        # A.DESCRIPCION es BLOB en Firebird — incompatible con COALESCE(VARCHAR, BLOB).
        # A.PRECIOVENTA en Firebird (columna real — A.PRECIO no existe en ARTICULO).
        "sql": (
            "SELECT COALESCE(A.NOMBRE, CAST(A.CODIGO AS VARCHAR(50))) AS ARTICULO, "
            "A.STOCKARTICULO AS STOCK, ROUND(A.PRECIOVENTA,2) AS PRECIO "
            "FROM ARTICULO A WHERE A.BAJA=1 LIMIT 20"
        ),
        "icono": "X",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_articulos_sin_proveedor() -> Dict[str, Any]:
    """Artículos sin proveedor asignado."""
    return {
        "id": "px_articulos_sin_proveedor",
        "label": "Artículos sin proveedor asignado",
        "justificacion": (
            "Artículos con PROVEEDDEFECTO IS NULL o = 0 no tienen proveedor de referencia. "
            "Esto dificulta la reposición de stock y el análisis de compras."
        ),
        # PROVEEDDEFECTO en Firebird (no CODPROVEEDOR — esa columna no existe en ARTICULO).
        # PROVEEDDEFECTO es INTEGER en Firebird: comparar con 0 o IS NULL, no con ''.
        "sql": (
            "SELECT COALESCE(A.NOMBRE, CAST(A.CODIGO AS VARCHAR(50))) AS ARTICULO, "
            "A.STOCKARTICULO AS STOCK "
            "FROM ARTICULO A WHERE A.PROVEEDDEFECTO IS NULL OR A.PROVEEDDEFECTO=0 "
            "ORDER BY A.STOCKARTICULO DESC LIMIT 20"
        ),
        "icono": "?",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_precio_vs_coste() -> Dict[str, Any]:
    """Artículos con precio de venta vs coste."""
    return {
        "id": "px_precio_vs_coste",
        "label": "Artículos con precio de venta vs coste (margen)",
        "justificacion": (
            "Compara PRECIOVENTA con PRECIOCOSTE para cada artículo. "
            "Artículos con margen negativo o muy bajo deben revisarse en la política de precios."
        ),
        # A.PRECIOVENTA en Firebird (columna real — A.PRECIO no existe en ARTICULO).
        # A.DESCRIPCION es BLOB en Firebird — incompatible con COALESCE(VARCHAR, BLOB).
        "sql": (
            "SELECT COALESCE(A.NOMBRE, CAST(A.CODIGO AS VARCHAR(50))) AS ARTICULO, "
            "ROUND(A.PRECIOVENTA,2) AS PRECIO_VENTA, ROUND(A.PRECIOCOSTE,2) AS COSTE, "
            "ROUND(A.PRECIOVENTA - A.PRECIOCOSTE, 2) AS MARGEN, "
            "CASE WHEN A.PRECIOVENTA > 0 "
            "     THEN ROUND(100.0*(A.PRECIOVENTA-A.PRECIOCOSTE)/A.PRECIOVENTA,1) "
            "     ELSE 0 END AS PCT_MARGEN "
            "FROM ARTICULO A WHERE A.PRECIOVENTA > 0 ORDER BY PCT_MARGEN ASC LIMIT 20"
        ),
        "icono": "$",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_familias_productos() -> Dict[str, Any]:
    """Distribución de artículos por código de familia (CODFAMILIA)."""
    return {
        "id": "px_familias_productos",
        "label": "Distribución de artículos por familia (CODFAMILIA)",
        "justificacion": (
            "Muestra cuántos artículos hay en cada familia (CODFAMILIA). "
            "La tabla FAMILIA no existe en la BD real Firebird JDDC; "
            "se agrupa directamente por ARTICULO.CODFAMILIA. "
            "Permite verificar que los artículos están clasificados por familia."
        ),
        # La tabla FAMILIA no existe en Firebird real JDDC.
        # Se agrupa por CODFAMILIA directamente desde ARTICULO.
        # CODFAMILIA es INTEGER en Firebird — CAST a VARCHAR para COALESCE con string.
        "sql": (
            "SELECT COALESCE(CAST(A.CODFAMILIA AS VARCHAR(50)), 'Sin familia') AS CODFAMILIA, "
            "COUNT(A.CODIGO) AS N_ARTICULOS "
            "FROM ARTICULO A "
            "GROUP BY A.CODFAMILIA ORDER BY N_ARTICULOS DESC LIMIT 20"
        ),
        "icono": "F",
        "tipo": "tabla",
        "max_rows": 20,
    }


# ─── Paneles de proveedores ───────────────────────────────────────────────────

def panel_proveedores_activos() -> Dict[str, Any]:
    """Proveedores activos en el sistema."""
    return {
        "id": "px_proveedores_activos",
        "label": "Proveedores activos en el sistema",
        "justificacion": (
            "Lista de proveedores registrados con el número de artículos asociados. "
            "Permite verificar que los proveedores referenciados en artículos existen en el maestro."
        ),
        # GROUP BY incluye P.CODIGO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL para compatibilidad Firebird.
        # CAST(P.CODIGO AS VARCHAR(20)) — Firebird no tiene tipo TEXT.
        # PROVEEDDEFECTO en ARTICULO (no CODPROVEEDOR).
        "sql": (
            "SELECT COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL, "
            "CAST(P.CODIGO AS VARCHAR(20))) AS PROVEEDOR, "
            "COUNT(A.CODIGO) AS N_ARTICULOS "
            "FROM PROVEED P LEFT JOIN ARTICULO A ON A.PROVEEDDEFECTO=P.CODIGO "
            "GROUP BY P.CODIGO, P.NOMBRECOMERCIAL, P.RAZONSOCIAL "
            "ORDER BY N_ARTICULOS DESC LIMIT 20"
        ),
        "icono": "🏭",
        "tipo": "tabla",
        "max_rows": 20,
    }


# ─── Paneles de agentes y formas de pago ─────────────────────────────────────

def panel_agentes_ventas() -> Dict[str, Any]:
    """Ventas por agente/comercial."""
    return {
        "id": "px_agentes_ventas",
        "label": "Ventas por agente/comercial (CODAGENTE)",
        "justificacion": (
            "Distribución de facturas por agente. Permite verificar que todas las facturas "
            "tienen agente asignado y detectar desequilibrios en la cartera de clientes."
        ),
        # CODAGENTE es INTEGER en Firebird — CAST a VARCHAR(20), no TEXT.
        "sql": (
            "SELECT COALESCE(CAST(CODAGENTE AS VARCHAR(20)), 'Sin agente') AS AGENTE, "
            "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=13 GROUP BY CODAGENTE ORDER BY TOTAL DESC LIMIT 20"
        ),
        "icono": "👤",
        "tipo": "tabla",
        "max_rows": 20,
    }


def panel_formas_pago() -> Dict[str, Any]:
    """Distribución por forma de pago."""
    return {
        "id": "px_formas_pago",
        "label": "Distribución por forma de pago",
        "justificacion": (
            "Muestra cuántas facturas usan cada forma de pago. "
            "Permite detectar si hay facturas sin forma de pago asignada "
            "o si la distribución es coherente con la política comercial."
        ),
        # CODFORMAPAGO es VARCHAR en Firebird — COALESCE con string es válido.
        "sql": (
            "SELECT COALESCE(CODFORMAPAGO, 'Sin forma pago') AS FORMA_PAGO, "
            "COUNT(*) AS N_FACTURAS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=13 GROUP BY CODFORMAPAGO ORDER BY TOTAL DESC LIMIT 15"
        ),
        "icono": "💳",
        "tipo": "tabla",
        "max_rows": 15,
    }


# ─── Paneles de líneas de documento ──────────────────────────────────────────

def panel_lineas_sin_articulo() -> Dict[str, Any]:
    """Líneas sin artículo asignado."""
    return {
        "id": "px_lineas_sin_articulo",
        "label": "Líneas de venta sin artículo asignado",
        "justificacion": (
            "Líneas de DOCLIN sin CODARTICULO válido. Si hay muchas, el análisis de productos "
            "está incompleto. Estas líneas tienen importe pero no se pueden atribuir a ningún artículo."
        ),
        # CODARTICULO es INTEGER en Firebird — no comparar con ''.
        # Solo IS NULL o = 0 para detectar líneas sin artículo.
        "sql": (
            "SELECT COUNT(*) AS LINEAS_SIN_ARTICULO, "
            "ROUND(SUM(CAST(CANTIDAD AS REAL)*CAST(PRECIO AS REAL)),2) AS IMPORTE_SIN_ATRIBUIR "
            "FROM DOCLIN WHERE CODARTICULO IS NULL OR CODARTICULO=0"
        ),
        "icono": "⚠️",
        "tipo": "resumen",
        "max_rows": 5,
    }


def panel_lineas_por_documento(tipo_num: int = 13) -> Dict[str, Any]:
    """Número de líneas por documento (resumen simple)."""
    return {
        "id": "px_lineas_por_doc",
        "label": "Número de líneas por documento (resumen)",
        "justificacion": (
            "Muestra el total de líneas en DOCLIN para documentos de este tipo, "
            "el promedio de líneas por documento y el máximo. "
            "Documentos con 0 líneas son anómalos (cabecera sin detalle)."
        ),
        # Consulta simple sin triple subquery para evitar timeouts en BD grandes.
        "sql": (
            f"SELECT "
            f"COUNT(DISTINCT D.CODIGO) AS N_DOCS_TOTAL, "
            f"COUNT(L.CODIGO) AS N_LINEAS_TOTAL, "
            f"CASE WHEN COUNT(DISTINCT D.CODIGO) > 0 "
            f"     THEN ROUND(CAST(COUNT(L.CODIGO) AS REAL)/COUNT(DISTINCT D.CODIGO),1) "
            f"     ELSE 0 END AS MEDIA_LINEAS_POR_DOC "
            f"FROM DOCCAB D LEFT JOIN DOCLIN L ON L.CODDOCUMENTO=D.CODIGO "
            f"WHERE D.TIPO={tipo_num}"
        ),
        "icono": "L",
        "tipo": "resumen",
        "max_rows": 5,
    }


# ─── Paneles de SAT ───────────────────────────────────────────────────────────

def panel_sats_por_estado() -> Dict[str, Any]:
    """SATs: resumen de totales y distribución por agente."""
    return {
        "id": "px_sats_estado",
        "label": "SATs: resumen total y distribución por agente",
        "justificacion": (
            "Muestra el total de SATs (TIPO=2), su importe total y distribución por agente. "
            "La columna ESTADO no existe en DOCCAB de Firebird JDDC; "
            "se usa CODAGENTE como dimensión de agrupación alternativa."
        ),
        # CODAGENTE es INTEGER en Firebird — CAST a VARCHAR(20), no TEXT.
        "sql": (
            "SELECT COALESCE(CAST(CODAGENTE AS VARCHAR(20)), 'Sin agente') AS AGENTE, "
            "COUNT(*) AS N_SATS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=2 "
            "GROUP BY CODAGENTE ORDER BY N_SATS DESC LIMIT 15"
        ),
        "icono": "S",
        "tipo": "tabla",
        "max_rows": 15,
    }


def panel_presupuestos_por_estado() -> Dict[str, Any]:
    """Presupuestos: resumen total y distribución por agente."""
    return {
        "id": "px_presupuestos_estado",
        "label": "Presupuestos: resumen total y distribución por agente",
        "justificacion": (
            "Muestra el total de presupuestos (TIPO=0), su importe total y distribución por agente. "
            "La columna ESTADO no existe en DOCCAB de Firebird JDDC; "
            "se usa CODAGENTE como dimensión de agrupación alternativa."
        ),
        # CODAGENTE es INTEGER en Firebird — CAST a VARCHAR(20), no TEXT.
        "sql": (
            "SELECT COALESCE(CAST(CODAGENTE AS VARCHAR(20)), 'Sin agente') AS AGENTE, "
            "COUNT(*) AS N_PRESUPUESTOS, ROUND(SUM(IMPORTETOTAL),2) AS TOTAL "
            "FROM DOCCAB WHERE TIPO=0 "
            "GROUP BY CODAGENTE ORDER BY N_PRESUPUESTOS DESC LIMIT 15"
        ),
        "icono": "P",
        "tipo": "tabla",
        "max_rows": 15,
    }


def panel_albaranes_vs_facturas() -> Dict[str, Any]:
    """Comparativa albaranes vs facturas."""
    return {
        "id": "px_albaranes_vs_facturas",
        "label": "Albaranes vs facturas: comparativa",
        "justificacion": (
            "Compara el número de albaranes (TIPO=11) con facturas (TIPO=13). "
            "Si hay muchos más albaranes que facturas, hay trabajo entregado sin facturar."
        ),
        "sql": (
            "SELECT "
            "SUM(CASE WHEN TIPO=11 THEN 1 ELSE 0 END) AS N_ALBARANES, "
            "SUM(CASE WHEN TIPO=13 THEN 1 ELSE 0 END) AS N_FACTURAS, "
            "ROUND(SUM(CASE WHEN TIPO=11 THEN IMPORTETOTAL ELSE 0 END),2) AS IMPORTE_ALBARANES, "
            "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS IMPORTE_FACTURAS "
            "FROM DOCCAB WHERE TIPO IN (11,13)"
        ),
        "icono": "📊",
        "tipo": "resumen",
        "max_rows": 5,
    }


def panel_ventas_vs_compras_mensual() -> Dict[str, Any]:
    """Ventas vs compras por mes."""
    return {
        "id": "px_ventas_vs_compras",
        "label": "Ventas vs Compras por mes (últimos 12 meses)",
        "justificacion": (
            "Compara ventas (TIPO=13) y pedidos a proveedor (TIPO=12) mes a mes. "
            "Permite detectar meses con más compras que ventas."
        ),
        # Firebird 2.5: GROUP BY debe usar la expresión completa, no el alias.
        "sql": (
            "SELECT SUBSTR(FECHA,1,7) AS MES, "
            "ROUND(SUM(CASE WHEN TIPO=13 THEN IMPORTETOTAL ELSE 0 END),2) AS VENTAS, "
            "ROUND(SUM(CASE WHEN TIPO=12 THEN IMPORTETOTAL ELSE 0 END),2) AS COMPRAS "
            "FROM DOCCAB WHERE TIPO IN (13,12) AND FECHA IS NOT NULL "
            "GROUP BY SUBSTR(FECHA,1,7) ORDER BY SUBSTR(FECHA,1,7) DESC LIMIT 12"
        ),
        "icono": "C",
        "tipo": "tabla",
        "max_rows": 12,
    }


def panel_descuentos_aplicados(tipo_num: int = 13) -> Dict[str, Any]:
    """Distribución de líneas con descuento en DOCLIN."""
    return {
        "id": "px_descuentos",
        "label": "Líneas de venta con descuento aplicado (DOCLIN.DESCUENTOS)",
        "justificacion": (
            "Líneas de DOCLIN con DESCUENTOS > 0. "
            "Descuentos muy altos (>30%) pueden indicar errores o política de precios agresiva. "
            "La columna DESCUENTOS está en DOCLIN, no en DOCCAB."
        ),
        # Subquery wrapper para GROUP BY alias en Firebird 2.5.
        "sql": (
            f"SELECT RANGO_DESC, COUNT(*) AS N_LINEAS, "
            f"ROUND(SUM(IMPORTE_LINEA),2) AS TOTAL "
            f"FROM ("
            f"SELECT CAST(LIN.CANTIDAD AS REAL)*CAST(LIN.PRECIO AS REAL) AS IMPORTE_LINEA, "
            f"CASE WHEN LIN.DESCUENTOS IS NULL OR LIN.DESCUENTOS=0 THEN 'Sin descuento' "
            f"     WHEN LIN.DESCUENTOS<=10 THEN '1-10%' "
            f"     WHEN LIN.DESCUENTOS<=20 THEN '11-20%' "
            f"     WHEN LIN.DESCUENTOS<=30 THEN '21-30%' "
            f"     ELSE 'mas 30%' END AS RANGO_DESC, "
            f"COALESCE(LIN.DESCUENTOS,0) AS DESC_VAL "
            f"FROM DOCLIN LIN "
            f"JOIN DOCCAB CAB ON LIN.CODDOCUMENTO=CAB.CODIGO AND CAB.TIPO={tipo_num}"
            f") GROUP BY RANGO_DESC ORDER BY MIN(DESC_VAL)"
        ),
        "icono": "%",
        "tipo": "tabla",
        "max_rows": 10,
    }
