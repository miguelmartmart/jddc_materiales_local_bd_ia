"""
backend/core/context — Gestión inteligente de contexto para modelos LLM.

Módulos:
  context_manager.py — ContextManager: comprime contexto con IA cuando supera el límite
"""
from backend.core.context.context_manager import ContextManager, ContextManagerConfig

__all__ = ["ContextManager", "ContextManagerConfig"]
