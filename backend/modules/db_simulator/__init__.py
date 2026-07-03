"""
db_simulator — Simulador de BD Firebird basado en SQLite.

Exporta la interfaz mínima necesaria para integrar el módulo
en el resto del sistema DEVIA sin exponer detalles internos.

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from backend.modules.db_simulator.driver  import SimulatedFirebirdDriver
from backend.modules.db_simulator.manager import simulator_manager

__all__ = ["SimulatedFirebirdDriver", "simulator_manager"]
