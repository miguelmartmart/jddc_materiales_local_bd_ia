"""
deep_analysis/ — Paquete del Agente de Análisis Profundo Multi-Fase ÉPICO v2.0

Módulos:
  models.py       — Dataclasses, Enums, TokenBudget, constantes
  phases_1_2.py   — Fase 0 (presupuesto), Fase 1 (comprensión), Fase 2 (exploración)
  phases_3_4_5.py — Fase 3 (investigación), Fase 4 (análisis), Fase 5 (síntesis)
  agent.py        — DeepAnalysisAgent (orquestador principal)

Importación pública:
  from backend.modules.chat.deep_analysis import DeepAnalysisAgent, detect_depth
"""

from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
from backend.modules.chat.deep_analysis.models import detect_depth, AnalysisDepth

__all__ = ["DeepAnalysisAgent", "detect_depth", "AnalysisDepth"]
