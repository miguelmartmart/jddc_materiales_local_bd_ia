"""
justification/__init__.py — Módulo de justificación y evidencias para la biblioteca de consultas.

Exporta:
  - get_verifications_for_query(query_id) → List[Dict]
  - STANDARD_PANEL_COUNT: número estándar de paneles por consulta (10)

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from backend.modules.db_simulator.justification.registry import (
    get_verifications_for_query,
    STANDARD_PANEL_COUNT,
)

__all__ = ["get_verifications_for_query", "STANDARD_PANEL_COUNT"]
