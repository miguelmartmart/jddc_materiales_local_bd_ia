"""
deep_analysis_agent.py — Shim de compatibilidad hacia el paquete deep_analysis/.

DEPRECADO: Este fichero existe solo para compatibilidad con imports anteriores.
           Usar directamente: from backend.modules.chat.deep_analysis import DeepAnalysisAgent

El código real está en:
  backend/modules/chat/deep_analysis/
    __init__.py      — Exportaciones públicas
    models.py        — Dataclasses, Enums, TokenBudget, detect_depth
    phases_1_2.py    — Fases 0, 1, 2 (comprensión + exploración)
    phases_3_4_5.py  — Fases 3, 4, 5 (investigación + análisis + síntesis)
    agent.py         — DeepAnalysisAgent (orquestador)
"""

# Re-exportar todo desde el paquete real
from backend.modules.chat.deep_analysis import DeepAnalysisAgent, detect_depth, AnalysisDepth
from backend.modules.chat.deep_analysis.models import (
    DEPTH_CONFIG, EpicAnalysisResult, PhaseResult, SubPhaseResult, TokenBudget,
)

__all__ = [
    "DeepAnalysisAgent",
    "detect_depth",
    "AnalysisDepth",
    "DEPTH_CONFIG",
    "EpicAnalysisResult",
    "PhaseResult",
    "SubPhaseResult",
    "TokenBudget",
]
