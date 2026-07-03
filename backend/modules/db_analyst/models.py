"""
Modelos Pydantic del módulo Analista BD.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class AnalystChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None          # None → crear nueva sesión
    model_id: Optional[str] = "jddcia-qwen3-30b"


class Provenance(BaseModel):
    """Procedencia completa de una respuesta: dónde vienen los datos."""
    sql_generated: Optional[str] = None       # SQL tal como lo generó la IA
    sql_executed: Optional[str] = None        # SQL tras normalización
    raw_results: Optional[List[Dict[str, Any]]] = None  # Datos brutos (max 50 filas)
    tables_used: List[str] = []               # Tablas del índice SIUO usadas
    siuo_keywords: List[str] = []            # Keywords que dispararon el índice
    siuo_source: str = "unknown"             # Fuente del contexto (concept_index, fallback…)
    context_tokens: int = 0                  # Tokens estimados del contexto SIUO
    data_source: str = "simulator"           # "simulator" o "firebird"
    model_used: Optional[str] = None         # Modelo que generó la respuesta
    execution_time_ms: int = 0               # Tiempo total de procesamiento
    requires_db: bool = True                 # False si fue respuesta conversacional


class AnalystChatResponse(BaseModel):
    message_id: int
    session_id: str
    response: str
    provenance: Provenance


class NewSessionResponse(BaseModel):
    session_id: str
    title: str


class SessionInfo(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class SessionMessage(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    provenance: Optional[Provenance] = None
    created_at: str


class StatusResponse(BaseModel):
    data_source: str                 # "simulator" | "firebird"
    siuo_ready: bool                 # ¿Existen los índices SIUO?
    siuo_tables_indexed: int         # Número de tablas indexadas
    simulator_enabled: bool
    simulator_status: Optional[str] = None
