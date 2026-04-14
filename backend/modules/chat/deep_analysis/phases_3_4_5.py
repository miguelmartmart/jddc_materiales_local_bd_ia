"""
phases_3_4_5.py — Re-exportador de compatibilidad.

Este fichero existía con 1413 líneas y fue dividido en:
  - phase3.py  → Phase3Mixin  (Fases 3 y 3b)
  - phase4.py  → Phase4Mixin  (Fases 4 y 4b)
  - phase5.py  → Phase5Mixin  (Fase 5)

Phases345Mixin hereda de los tres para mantener compatibilidad con
cualquier código que importe desde este módulo.
"""

from backend.modules.chat.deep_analysis.phase3 import Phase3Mixin
from backend.modules.chat.deep_analysis.phase4 import Phase4Mixin
from backend.modules.chat.deep_analysis.phase5 import Phase5Mixin

# Importaciones a nivel de módulo para permitir mocking en tests
try:
    from backend.modules.db_explorer.context_retriever import get_context_retriever
except ImportError:
    get_context_retriever = None  # type: ignore

try:
    from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
except ImportError:
    get_knowledge_store = None  # type: ignore


class Phases345Mixin(Phase3Mixin, Phase4Mixin, Phase5Mixin):
    """
    Mixin combinado con las fases 3, 3b, 4, 4b y 5.
    Hereda de Phase3Mixin, Phase4Mixin y Phase5Mixin.

    Compatibilidad: cualquier código que importe Phases345Mixin
    sigue funcionando sin cambios.
    """
    pass


__all__ = [
    "Phases345Mixin",
    "Phase3Mixin",
    "Phase4Mixin",
    "Phase5Mixin",
    "get_context_retriever",
    "get_knowledge_store",
]
