"""
deep_analysis/ — Paquete del Agente de Análisis Profundo Multi-Fase ÉPICO v2.0

Módulos:
  models.py         — Dataclasses, Enums, TokenBudget, constantes
  phases_1_2.py     — Fase 0 (presupuesto), Fase 1 (comprensión), Fase 2 (exploración)
  phases_3_4_5.py   — Fase 3 (investigación), Fase 4 (análisis), Fase 4b (aprendizaje), Fase 5 (síntesis)
  agent.py          — DeepAnalysisAgent (orquestador principal)
  knowledge_store.py — KnowledgeStore: almacén de conocimiento persistente (LAN_ONLY)

Estructura de conocimiento persistente (core/config/knowledge/):
  tables/TABLA.json    ← metadatos ricos por tabla (columnas reales, conteos, distribuciones)
  index.json           ← índice global de tablas conocidas
  business_rules.json  ← reglas de negocio descubiertas
  query_patterns.json  ← patrones SQL exitosos por intención
  discoveries_log.jsonl ← log append-only de descubrimientos

Importación pública:
  from backend.modules.chat.deep_analysis import DeepAnalysisAgent, detect_depth
  from backend.modules.chat.deep_analysis import get_knowledge_store, KnowledgeStore
"""

from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
from backend.modules.chat.deep_analysis.models import detect_depth, AnalysisDepth
from backend.modules.chat.deep_analysis.knowledge_store import KnowledgeStore, get_knowledge_store

__all__ = [
    "DeepAnalysisAgent",
    "detect_depth",
    "AnalysisDepth",
    "KnowledgeStore",
    "get_knowledge_store",
]
