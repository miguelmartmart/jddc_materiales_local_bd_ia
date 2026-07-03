"""
query_library/builder.py — Helper para construir entradas de consulta estándar.

PRINCIPIO: Centraliza la estructura de cada consulta. Sin literales dispersos.
DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from typing import Any, Dict, List, Optional


def q(
    id: str,
    nombre: str,
    desc_simple: str,
    desc_tecnica: str,
    sql: str,
    dept: str,
    rol: str,
    tipo: str,
    urgencia: str,
    kpi: str = "",
    accion: str = "",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Construye un dict de consulta con la estructura estándar.
    Todos los campos son obligatorios excepto kpi, accion y tags.

    Nota: 'title' es alias de 'nombre' para compatibilidad con el sistema legacy
    que usa query_library.py (QUERY_LIBRARY original).
    """
    return {
        "id": id,
        "title": nombre,   # alias para compatibilidad con QUERY_LIBRARY original
        "nombre": nombre,
        "desc": desc_simple,  # alias legacy
        "desc_simple": desc_simple,
        "desc_tecnica": desc_tecnica,
        "sql": sql,
        "dept": dept,
        "rol": rol,
        "tipo": tipo,
        "urgencia": urgencia,
        "kpi": kpi,
        "accion": accion,
        "tags": tags or [],
    }
