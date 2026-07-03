"""
query_library/__init__.py — Punto de acceso único a la biblioteca de consultas SQL.

Re-exporta todo desde query_library_core.py (consultas originales + funciones de acceso)
y añade QUERY_LIBRARY_EXTENDED (consultas nuevas de los submódulos v1, v2, v3).

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

# ─── Importar consultas originales y funciones de acceso ─────────────────────
from backend.modules.db_simulator.query_library_core import (
    QUERY_LIBRARY,
    Dept,
    Rol,
    Tipo,
    Urgencia,
    get_all_queries,
    get_queries_by_dept,
    get_queries_by_tipo,
    get_queries_by_urgencia,
    get_query_by_id,
    search_queries,
    get_catalog_summary,
    get_queries_by_rol,
)

# ─── Importar consultas extendidas v1 ────────────────────────────────────────
from backend.modules.db_simulator.query_library.ventas import QUERIES_VENTAS_EXTENDED
from backend.modules.db_simulator.query_library.compras import QUERIES_COMPRAS_EXTENDED
from backend.modules.db_simulator.query_library.almacen import QUERIES_ALMACEN_EXTENDED
from backend.modules.db_simulator.query_library.finanzas import QUERIES_FINANZAS_EXTENDED
from backend.modules.db_simulator.query_library.sat import QUERIES_SAT_EXTENDED
from backend.modules.db_simulator.query_library.direccion import QUERIES_DIRECCION_EXTENDED
from backend.modules.db_simulator.query_library.marketing import QUERIES_MARKETING_EXTENDED
from backend.modules.db_simulator.query_library.calidad import QUERIES_CALIDAD_EXTENDED

# ─── Importar consultas extendidas v2 ────────────────────────────────────────
from backend.modules.db_simulator.query_library.ventas_v2 import QUERIES_VENTAS_V2
from backend.modules.db_simulator.query_library.compras_v2 import QUERIES_COMPRAS_V2
from backend.modules.db_simulator.query_library.almacen_v2 import QUERIES_ALMACEN_V2
from backend.modules.db_simulator.query_library.finanzas_v2 import QUERIES_FINANZAS_V2
from backend.modules.db_simulator.query_library.sat_v2 import QUERIES_SAT_V2
from backend.modules.db_simulator.query_library.direccion_v2 import QUERIES_DIRECCION_V2
from backend.modules.db_simulator.query_library.marketing_v2 import QUERIES_MARKETING_V2
from backend.modules.db_simulator.query_library.calidad_v2 import QUERIES_CALIDAD_V2

# ─── Importar consultas de Producción y Certificaciones ──────────────────────
from backend.modules.db_simulator.query_library.produccion import QUERIES_PRODUCCION

# ─── Importar consultas extendidas v3 ────────────────────────────────────────
from backend.modules.db_simulator.query_library.ventas_v3 import QUERIES_VENTAS_V3
from backend.modules.db_simulator.query_library.finanzas_v3 import QUERIES_FINANZAS_V3
from backend.modules.db_simulator.query_library.compras_v3 import QUERIES_COMPRAS_V3
from backend.modules.db_simulator.query_library.almacen_v3 import QUERIES_ALMACEN_V3
from backend.modules.db_simulator.query_library.direccion_v3 import QUERIES_DIRECCION_V3
from backend.modules.db_simulator.query_library.sat_v3 import QUERIES_SAT_V3
from backend.modules.db_simulator.query_library.marketing_v3 import QUERIES_MARKETING_V3
from backend.modules.db_simulator.query_library.calidad_v3 import QUERIES_CALIDAD_V3

# ─── Biblioteca extendida completa ───────────────────────────────────────────
QUERY_LIBRARY_EXTENDED: list = (
    # v1
    QUERIES_VENTAS_EXTENDED
    + QUERIES_COMPRAS_EXTENDED
    + QUERIES_ALMACEN_EXTENDED
    + QUERIES_FINANZAS_EXTENDED
    + QUERIES_SAT_EXTENDED
    + QUERIES_DIRECCION_EXTENDED
    + QUERIES_MARKETING_EXTENDED
    + QUERIES_CALIDAD_EXTENDED
    # v2
    + QUERIES_VENTAS_V2
    + QUERIES_COMPRAS_V2
    + QUERIES_ALMACEN_V2
    + QUERIES_FINANZAS_V2
    + QUERIES_SAT_V2
    + QUERIES_DIRECCION_V2
    + QUERIES_MARKETING_V2
    + QUERIES_CALIDAD_V2
    # v3
    + QUERIES_VENTAS_V3
    + QUERIES_FINANZAS_V3
    + QUERIES_COMPRAS_V3
    + QUERIES_ALMACEN_V3
    + QUERIES_DIRECCION_V3
    + QUERIES_SAT_V3
    + QUERIES_MARKETING_V3
    + QUERIES_CALIDAD_V3
    # Producción y Certificaciones
    + QUERIES_PRODUCCION
)

__all__ = [
    # Datos
    "QUERY_LIBRARY",
    "QUERY_LIBRARY_EXTENDED",
    # Constantes de clasificación
    "Dept",
    "Rol",
    "Tipo",
    "Urgencia",
    # Funciones de acceso
    "get_all_queries",
    "get_queries_by_dept",
    "get_queries_by_tipo",
    "get_queries_by_urgencia",
    "get_query_by_id",
    "search_queries",
    "get_catalog_summary",
    "get_queries_by_rol",
]
