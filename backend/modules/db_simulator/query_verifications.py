"""
query_verifications.py — Compatibilidad: delega al módulo justification/.

Este fichero se mantiene por compatibilidad con imports existentes.
La lógica real está en backend/modules/db_simulator/justification/

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from typing import Dict, List, Any

from backend.modules.db_simulator.justification.registry import (
    get_verifications_for_query,
    STANDARD_PANEL_COUNT,
    _REGISTRY,
)

# Alias de compatibilidad con tests y código que usaban el dict directo
QUERY_VERIFICATIONS: Dict[str, List[Dict[str, Any]]] = _REGISTRY


def get_all_query_ids_with_verifications() -> List[str]:
    """Devuelve todos los IDs de consulta que tienen verificaciones definidas."""
    return list(_REGISTRY.keys())


__all__ = [
    "get_verifications_for_query",
    "STANDARD_PANEL_COUNT",
    "QUERY_VERIFICATIONS",
    "get_all_query_ids_with_verifications",
]
