"""
demo_queries.py — Consultas de demostración predefinidas del simulador.

Adaptadas al esquema real de Firebird capturado en simulator.db:
  - CLIENTE: NOMBRECOMERCIAL / RAZONSOCIAL (no NOMBRE), TEL (no TELEFONO)
  - PROVEED:  NOMBRECOMERCIAL / RAZONSOCIAL
  - DOCLIN:   CODDOCUMENTO (FK→DOCCAB.CODIGO), CODARTICULO (no CODART),
              PRECIOVENTA*CANTIDAD (no columna IMPORTE directa)
  - ARTICULO: esquema sintético con NOMBRE, PRECIOVENTA, STOCKARTICULO

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
from typing import Any, Dict, List

from backend.modules.db_simulator.constants import JDDCDocTipos, SimulatorLog
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver

logger = logging.getLogger(__name__)

# ─── Helper de nombre de cliente/proveedor ───────────────────────────────────
_CLI_NOMBRE = "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, 'Sin nombre')"
_PRO_NOMBRE = "COALESCE(P.NOMBRECOMERCIAL, P.RAZONSOCIAL, 'Sin nombre')"

DEMO_SQL_QUERIES = [
    {
        "id": "top_clientes",
        "title": "Top 10 Mejores Clientes",
        "sql": (
            "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, 'Sin nombre') AS NOMBRE, "
            "COUNT(D.CODIGO) AS N_FACTURAS, "
            "ROUND(SUM(CAST(D.IMPORTETOTAL AS REAL)), 2) AS TOTAL "
            "FROM DOCCAB D "
            "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "WHERE D.TIPO = 13 "
            "GROUP BY C.CODIGO "
            "ORDER BY TOTAL DESC "
            "LIMIT 10"
        ),
    },
    {
        "id": "top_productos",
        "title": "Productos Más Vendidos",
        "sql": (
            "SELECT L.CODARTICULO AS ARTICULO, "
            "ROUND(SUM(CAST(L.CANTIDAD AS REAL)), 2) AS TOTAL_CANT, "
            "ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)), 2) AS TOTAL_IMP "
            "FROM DOCLIN L "
            "JOIN DOCCAB D ON D.CODIGO = L.CODDOCUMENTO "
            "WHERE D.TIPO = 13 AND L.CODARTICULO IS NOT NULL "
            "GROUP BY L.CODARTICULO "
            "ORDER BY TOTAL_IMP DESC "
            "LIMIT 10"
        ),
    },
    {
        "id": "ultimas_facturas",
        "title": "Últimas Facturas",
        "sql": (
            "SELECT D.FECHA, D.NUMERO, D.SERIE, "
            "COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, D.CODCLIENTE) AS CLIENTE, "
            "ROUND(CAST(D.IMPORTETOTAL AS REAL), 2) AS IMPORTE "
            "FROM DOCCAB D "
            "LEFT JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
            "WHERE D.TIPO = 13 "
            "ORDER BY D.FECHA DESC, D.CODIGO DESC LIMIT 20"
        ),
    },
    {
        "id": "clientes_activos",
        "title": "Clientes con Documentos",
        "sql": (
            "SELECT COALESCE(C.NOMBRECOMERCIAL, C.RAZONSOCIAL, 'Sin nombre') AS NOMBRE, "
            "COUNT(D.CODIGO) AS DOCUMENTOS, "
            "ROUND(SUM(CAST(D.IMPORTETOTAL AS REAL)), 2) AS TOTAL "
            "FROM CLIENTE C "
            "JOIN DOCCAB D ON D.CODCLIENTE = C.CODIGO "
            "GROUP BY C.CODIGO "
            "ORDER BY DOCUMENTOS DESC "
            "LIMIT 15"
        ),
    },
    {
        "id": "stock_disponible",
        "title": "Stock Disponible",
        "sql": (
            "SELECT A.NOMBRE, A.STOCKARTICULO AS STOCK, "
            "ROUND(CAST(A.PRECIOVENTA AS REAL), 2) AS PRECIOVENTA "
            "FROM ARTICULO A WHERE A.STOCKARTICULO > 0 "
            "ORDER BY A.STOCKARTICULO DESC LIMIT 20"
        ),
    },
    {
        "id": "resumen_general",
        "title": "Resumen General de Documentos",
        "sql": (
            "SELECT COUNT(*) AS TOTAL_DOCUMENTOS, "
            "ROUND(SUM(CAST(IMPORTETOTAL AS REAL)), 2) AS SUMA_TOTAL "
            "FROM DOCCAB"
        ),
    },
    {
        "id": "catalogo_articulos",
        "title": "Catálogo de Artículos",
        "sql": (
            "SELECT CODIGO, NOMBRE, STOCKARTICULO AS STOCK, "
            "ROUND(CAST(PRECIOVENTA AS REAL), 2) AS PRECIOVENTA "
            "FROM ARTICULO ORDER BY NOMBRE ASC LIMIT 40"
        ),
    },
]


def get_demo_sql_queries() -> list:
    """Devuelve la lista de consultas SQL predefinidas para el dashboard."""
    return DEMO_SQL_QUERIES


# ─── Etiquetas de tipos de documento ─────────────────────────────────────────

_TIPO_LABELS = {
    0: "Presupuesto", 1: "Presupuesto", 2: "SAT", 3: "Abono",
    10: "Contrato", 11: "Albarán", 12: "Pedido", 13: "Factura",
    20: "Pedido", 21: "Pedido Compra", 40: "Albarán",
    51: "Certificación", 61: "Recibo",
}


# ─── Runner principal ─────────────────────────────────────────────────────────

def run_demo_queries() -> Dict[str, Any]:
    drv = SimulatedFirebirdDriver()
    drv.connect()
    try:
        return {
            "resumen_general":         _resumen_general(drv),
            "top_productos":           _top_productos(drv),
            "top_clientes":            _top_clientes(drv),
            "ventas_por_mes":          _ventas_por_mes(drv),
            "documentos_por_tipo":     _documentos_por_tipo(drv),
            "top_proveedores":         _top_proveedores(drv),
            "stock_disponible":        _stock_disponible(drv),
            "ultimas_facturas":        _ultimas_facturas(drv),
            "presupuestos_pendientes": _presupuestos_pendientes(drv),
            "sats_recientes":          _sats_recientes(drv),
        }
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en demo_queries: {e}", exc_info=True)
        raise
    finally:
        drv.disconnect()


# ─── Consultas individuales ───────────────────────────────────────────────────

def _resumen_general(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    n_facturas = drv.execute_query(
        f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {JDDCDocTipos.FACTURA}"
    )[0]["N"]
    total_fact = drv.execute_query(
        f"SELECT COALESCE(ROUND(SUM(CAST(IMPORTETOTAL AS REAL)),2),0) as T "
        f"FROM DOCCAB WHERE TIPO = {JDDCDocTipos.FACTURA}"
    )[0]["T"] or 0
    n_clientes  = drv.execute_query("SELECT COUNT(*) as N FROM CLIENTE")[0]["N"]
    n_articulos = drv.execute_query("SELECT COUNT(*) as N FROM ARTICULO")[0]["N"]
    n_docs      = drv.execute_query("SELECT COUNT(*) as N FROM DOCCAB")[0]["N"]
    n_presupuestos = drv.execute_query(
        f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {JDDCDocTipos.PRESUPUESTO}"
    )[0]["N"]
    return {
        "titulo": "Resumen General",
        "icono": "📊",
        "tipo": "stats",
        "datos": [
            {"label": "Facturas",       "valor": n_facturas,          "formato": "int"},
            {"label": "Total Facturado","valor": round(total_fact, 2), "formato": "money"},
            {"label": "Clientes",       "valor": n_clientes,          "formato": "int"},
            {"label": "Artículos",      "valor": n_articulos,         "formato": "int"},
            {"label": "Documentos",     "valor": n_docs,              "formato": "int"},
            {"label": "Presupuestos",   "valor": n_presupuestos,      "formato": "int"},
        ],
    }


def _top_productos(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    # DOCLIN.CODARTICULO coincide 100% con ARTICULO.CODIGO en la BD real.
    # LEFT JOIN para obtener el nombre real del artículo (Mitsubishi, Daikin, etc.)
    rows = drv.execute_query(
        "SELECT COALESCE(A.NOMBRE, CAST(L.CODARTICULO AS TEXT)) AS NOMBRE, "
        "  ROUND(SUM(CAST(L.CANTIDAD AS REAL)),2) as TOTAL_CANT, "
        "  ROUND(SUM(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL)),2) as TOTAL_IMP "
        "FROM DOCLIN L "
        "JOIN DOCCAB D ON D.CODIGO = L.CODDOCUMENTO "
        "LEFT JOIN ARTICULO A ON A.CODIGO = L.CODARTICULO "
        f"WHERE D.TIPO = {JDDCDocTipos.FACTURA} AND L.CODARTICULO IS NOT NULL "
        "GROUP BY L.CODARTICULO "
        "ORDER BY TOTAL_IMP DESC "
        "LIMIT 10"
    )
    return {
        "titulo": "Productos Más Vendidos",
        "icono": "🏆",
        "tipo": "tabla",
        "columnas": [
            {"key": "NOMBRE",     "label": "Producto",   "formato": "text"},
            {"key": "TOTAL_CANT", "label": "Uds.",        "formato": "dec"},
            {"key": "TOTAL_IMP",  "label": "Importe (€)", "formato": "money"},
        ],
        "datos": rows,
    }


def _top_clientes(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    rows = drv.execute_query(
        f"SELECT {_CLI_NOMBRE} AS NOMBRE, "
        "  COUNT(D.CODIGO) as N_FACTURAS, "
        "  ROUND(SUM(CAST(D.IMPORTETOTAL AS REAL)), 2) as TOTAL "
        "FROM DOCCAB D "
        "JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
        f"WHERE D.TIPO = {JDDCDocTipos.FACTURA} "
        "GROUP BY C.CODIGO "
        "ORDER BY TOTAL DESC "
        "LIMIT 10"
    )
    return {
        "titulo": "Mejores Clientes",
        "icono": "👥",
        "tipo": "tabla",
        "columnas": [
            {"key": "NOMBRE",     "label": "Cliente",   "formato": "text"},
            {"key": "N_FACTURAS", "label": "Facturas",  "formato": "int"},
            {"key": "TOTAL",      "label": "Total (€)", "formato": "money"},
        ],
        "datos": rows,
    }


def _ventas_por_mes(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    rows = drv.execute_query(
        "SELECT "
        "  CAST(strftime('%Y', FECHA) AS INTEGER) as ANIO, "
        "  CAST(strftime('%m', FECHA) AS INTEGER) as MES, "
        "  COUNT(*) as N_FACTURAS, "
        "  ROUND(SUM(CAST(IMPORTETOTAL AS REAL)), 2) as TOTAL "
        "FROM DOCCAB "
        f"WHERE TIPO = {JDDCDocTipos.FACTURA} AND FECHA IS NOT NULL "
        "GROUP BY ANIO, MES "
        "ORDER BY ANIO DESC, MES DESC "
        "LIMIT 12"
    )
    _MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
    for r in rows:
        m = r.get("MES", 1)
        a = r.get("ANIO", "")
        r["PERIODO"] = f"{_MESES[m-1]} {a}"
    return {
        "titulo": "Facturación Mensual",
        "icono": "📅",
        "tipo": "tabla",
        "columnas": [
            {"key": "PERIODO",    "label": "Período",   "formato": "text"},
            {"key": "N_FACTURAS", "label": "Facturas",  "formato": "int"},
            {"key": "TOTAL",      "label": "Total (€)", "formato": "money"},
        ],
        "datos": rows,
    }


def _documentos_por_tipo(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    rows = drv.execute_query(
        "SELECT TIPO, COUNT(*) as N, "
        "  ROUND(COALESCE(SUM(CAST(IMPORTETOTAL AS REAL)), 0), 2) as TOTAL "
        "FROM DOCCAB "
        "GROUP BY TIPO "
        "ORDER BY N DESC"
    )
    total_docs = sum(r["N"] for r in rows) or 1
    for r in rows:
        r["TIPO_LABEL"] = _TIPO_LABELS.get(r["TIPO"], f"Tipo {r['TIPO']}")
        r["PCT"] = round(r["N"] / total_docs * 100, 1)
    return {
        "titulo": "Documentos por Tipo",
        "icono": "📄",
        "tipo": "tabla",
        "columnas": [
            {"key": "TIPO_LABEL", "label": "Tipo",        "formato": "text"},
            {"key": "N",          "label": "Cantidad",    "formato": "int"},
            {"key": "PCT",        "label": "%",           "formato": "pct"},
            {"key": "TOTAL",      "label": "Importe (€)", "formato": "money"},
        ],
        "datos": rows,
    }


def _top_proveedores(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    """Top proveedores por artículos del catálogo que suministran.

    NOTA: La BD JDDC no tiene tabla COMPRA ni columna DOCCAB.CODPROVEEDOR.
    El vínculo proveedor→artículo está en ARTICULO.PROVEEDDEFECTO (FK→PROVEED.CODIGO).
    Se cuenta cuántos artículos distintos suministra cada proveedor y el precio
    medio de coste de esos artículos — datos reales del catálogo.
    """
    rows = drv.execute_query(
        f"SELECT {_PRO_NOMBRE} AS NOMBRE, "
        "  COUNT(A.CODIGO) AS N_ART, "
        "  ROUND(AVG(CAST(A.PRECIOCOSTE AS REAL)), 2) AS PRECIO_MEDIO "
        "FROM ARTICULO A "
        "JOIN PROVEED P ON CAST(P.CODIGO AS TEXT) = CAST(A.PROVEEDDEFECTO AS TEXT) "
        "WHERE A.PROVEEDDEFECTO IS NOT NULL AND A.PROVEEDDEFECTO != 0 "
        "GROUP BY A.PROVEEDDEFECTO "
        "ORDER BY N_ART DESC "
        "LIMIT 10"
    )
    return {
        "titulo": "Principales Proveedores",
        "icono": "🏭",
        "tipo": "tabla",
        "columnas": [
            {"key": "NOMBRE",      "label": "Proveedor",      "formato": "text"},
            {"key": "N_ART",       "label": "Artículos",      "formato": "int"},
            {"key": "PRECIO_MEDIO","label": "Precio Medio (€)","formato": "money"},
        ],
        "datos": rows,
    }


def _stock_disponible(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    """Artículos con stock disponible (datos sintéticos ARTICULO + FAMILIA)."""
    rows = drv.execute_query(
        "SELECT A.NOMBRE, COALESCE(F.NOMBRE,'Sin familia') as FAMILIA, "
        "  A.STOCKARTICULO as STOCK, ROUND(CAST(A.PRECIOVENTA AS REAL),2) as PRECIOVENTA "
        "FROM ARTICULO A "
        "LEFT JOIN FAMILIA F ON F.CODIGO = A.CODFAMILIA "
        "WHERE A.STOCKARTICULO > 0 "
        "ORDER BY A.STOCKARTICULO DESC "
        "LIMIT 15"
    )
    return {
        "titulo": "Stock Disponible",
        "icono": "📦",
        "tipo": "tabla",
        "columnas": [
            {"key": "NOMBRE",  "label": "Artículo",  "formato": "text"},
            {"key": "FAMILIA", "label": "Familia",   "formato": "text"},
            {"key": "STOCK",   "label": "Stock",     "formato": "dec"},
            {"key": "PRECIOVENTA",  "label": "Precio (€)","formato": "money"},
        ],
        "datos": rows,
    }


def _ultimas_facturas(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    rows = drv.execute_query(
        f"SELECT D.FECHA, D.NUMERO, D.SERIE, "
        f"  {_CLI_NOMBRE} AS CLIENTE, "
        "  ROUND(CAST(D.IMPORTETOTAL AS REAL), 2) as IMPORTE "
        "FROM DOCCAB D "
        "LEFT JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
        f"WHERE D.TIPO = {JDDCDocTipos.FACTURA} AND D.FECHA IS NOT NULL "
        "ORDER BY D.FECHA DESC, D.CODIGO DESC "
        "LIMIT 10"
    )
    return {
        "titulo": "Últimas Facturas",
        "icono": "🧾",
        "tipo": "tabla",
        "columnas": [
            {"key": "FECHA",   "label": "Fecha",     "formato": "text"},
            {"key": "SERIE",   "label": "Serie",     "formato": "text"},
            {"key": "NUMERO",  "label": "Nº",        "formato": "int"},
            {"key": "CLIENTE", "label": "Cliente",   "formato": "text"},
            {"key": "IMPORTE", "label": "Importe (€)","formato": "money"},
        ],
        "datos": rows,
    }


def _presupuestos_pendientes(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    rows = drv.execute_query(
        f"SELECT D.FECHA, D.SERIE, D.NUMERO, "
        f"  {_CLI_NOMBRE} AS CLIENTE, "
        "  ROUND(CAST(D.IMPORTETOTAL AS REAL), 2) as IMPORTE "
        "FROM DOCCAB D "
        "LEFT JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
        f"WHERE D.TIPO = {JDDCDocTipos.PRESUPUESTO} AND D.ESTADOPEND = 0 "
        "  AND D.FECHA IS NOT NULL "
        "ORDER BY CAST(D.IMPORTETOTAL AS REAL) DESC "
        "LIMIT 10"
    )
    return {
        "titulo": "Presupuestos Pendientes",
        "icono": "📋",
        "tipo": "tabla",
        "columnas": [
            {"key": "FECHA",   "label": "Fecha",     "formato": "text"},
            {"key": "SERIE",   "label": "Serie",     "formato": "text"},
            {"key": "NUMERO",  "label": "Nº",        "formato": "int"},
            {"key": "CLIENTE", "label": "Cliente",   "formato": "text"},
            {"key": "IMPORTE", "label": "Importe (€)","formato": "money"},
        ],
        "datos": rows,
    }


def _sats_recientes(drv: SimulatedFirebirdDriver) -> Dict[str, Any]:
    """SATs recientes — DOCCAB TIPO=2 con JOIN a CLIENTE.

    NOTA: No existe tabla REPCAB en la BD real. Los SATs son documentos
    de tipo 2 en DOCCAB, con CODCLIENTE como referencia al cliente.
    """
    rows = drv.execute_query(
        f"SELECT D.FECHA, D.SERIE, D.NUMERO, "
        f"  {_CLI_NOMBRE} AS CLIENTE, "
        "  ROUND(CAST(D.IMPORTETOTAL AS REAL), 2) as IMPORTE "
        "FROM DOCCAB D "
        "LEFT JOIN CLIENTE C ON C.CODIGO = D.CODCLIENTE "
        f"WHERE D.TIPO = {JDDCDocTipos.SAT} AND D.FECHA IS NOT NULL "
        "ORDER BY D.FECHA DESC, D.CODIGO DESC "
        "LIMIT 10"
    )
    return {
        "titulo": "SATs Recientes",
        "icono": "🔧",
        "tipo": "tabla",
        "columnas": [
            {"key": "FECHA",   "label": "Fecha",      "formato": "text"},
            {"key": "SERIE",   "label": "Serie",      "formato": "text"},
            {"key": "NUMERO",  "label": "Nº",         "formato": "int"},
            {"key": "CLIENTE", "label": "Cliente",    "formato": "text"},
            {"key": "IMPORTE", "label": "Importe (€)","formato": "money"},
        ],
        "datos": rows,
    }
