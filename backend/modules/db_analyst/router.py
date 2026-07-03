"""
router.py — Endpoints FastAPI del módulo Analista BD.

Todos los endpoints devuelven procedencia completa (Provenance) para que el
usuario pueda auditar de dónde vienen los datos y verificar la fiabilidad
de cada respuesta.

Endpoints:
  POST /api/db-analyst/chat           → Enviar pregunta, recibir respuesta + Provenance
  POST /api/db-analyst/chat/justify   → Justificar la respuesta anterior de una sesión
  POST /api/db-analyst/session/new    → Crear nueva sesión
  GET  /api/db-analyst/sessions       → Listar sesiones recientes
  GET  /api/db-analyst/session/{id}   → Mensajes de una sesión
  DELETE /api/db-analyst/session/{id} → Eliminar sesión
  GET  /api/db-analyst/status         → Estado del módulo (SIUO, simulador, fuente de datos)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.modules.db_analyst.models import (
    AnalystChatRequest,
    AnalystChatResponse,
    NewSessionResponse,
    Provenance,
    SessionInfo,
    SessionMessage,
    StatusResponse,
)
from backend.modules.db_analyst.service import AnalystService
from backend.modules.db_analyst.session_store import AnalystSessionStore

router = APIRouter()
logger = logging.getLogger(__name__)

# Singletons del módulo
_service = AnalystService()
_store = AnalystSessionStore()


# ─── Request extra ────────────────────────────────────────────────────────────

class JustifyRequest(BaseModel):
    session_id: str
    followup: Optional[str] = Field(default="", description="Pregunta de seguimiento opcional")
    model_id: Optional[str] = "jddcia-qwen3-30b"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Estado del módulo: fuente de datos activa, índices SIUO y simulador."""
    try:
        from backend.modules.db_simulator.manager import simulator_manager
        sim_enabled = simulator_manager.is_enabled()
        sim_status = simulator_manager.get_status().get("status", "unknown") if sim_enabled else None
    except Exception:
        sim_enabled = False
        sim_status = None

    data_source = "simulator" if sim_enabled else "firebird"

    # SIUO readiness
    siuo_ready = False
    siuo_tables = 0
    try:
        from backend.modules.db_explorer.deep_indexer_service import TABLE_INDEX_PATH, _load_json
        idx = _load_json(TABLE_INDEX_PATH)
        if idx:
            siuo_ready = True
            siuo_tables = len(idx)
    except Exception:
        pass

    return StatusResponse(
        data_source=data_source,
        siuo_ready=siuo_ready,
        siuo_tables_indexed=siuo_tables,
        simulator_enabled=sim_enabled,
        simulator_status=sim_status,
    )


@router.post("/session/new", response_model=NewSessionResponse)
async def new_session(model_id: Optional[str] = "jddcia-qwen3-30b"):
    """Crea una nueva sesión de conversación analítica."""
    session_id = _store.create_session(model_id=model_id or "jddcia-qwen3-30b")
    return NewSessionResponse(session_id=session_id, title="Nueva conversación")


@router.get("/sessions")
async def list_sessions(limit: int = 50):
    """Lista las sesiones más recientes."""
    return _store.list_sessions(limit=limit)


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Devuelve todos los mensajes de una sesión con su procedencia."""
    messages = _store.get_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Elimina una sesión y todos sus mensajes."""
    _store.delete_session(session_id)
    return {"success": True}


@router.post("/chat", response_model=AnalystChatResponse)
async def chat(request: AnalystChatRequest):
    """
    Envía una pregunta al Analista BD.

    Proceso:
      1. Recupera contexto SIUO para la pregunta
      2. Genera SQL con Qwen3 LAN
      3. Ejecuta SQL contra la BD (simulador o real)
      4. Interpreta resultados con justificación en <details>
      5. Guarda el mensaje con procedencia completa en la sesión
      6. Devuelve respuesta + Provenance
    """
    # Sesión: crear si no se proporcionó
    session_id = request.session_id
    if not session_id:
        session_id = _store.create_session(model_id=request.model_id or "jddcia-qwen3-30b")

    # Historial de conversación para contexto
    history_msgs = _store.get_messages(session_id)
    history = [{"role": m.role, "content": m.content} for m in history_msgs]

    # Procesar
    try:
        response_text, prov = await _service.process(
            message=request.message,
            history=history,
            model_id=request.model_id,
        )
    except Exception as e:
        logger.error(f"[ANALYST ROUTER] Error procesando mensaje: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    # Actualizar título de sesión con el primer mensaje del usuario
    if len(history) == 0:
        title = request.message[:60] + ("…" if len(request.message) > 60 else "")
        _store.update_title(session_id, title)

    # Guardar mensajes
    _store.add_message(session_id, "user", request.message)
    msg_id = _store.add_message(session_id, "assistant", response_text, provenance=prov)

    return AnalystChatResponse(
        message_id=msg_id,
        session_id=session_id,
        response=response_text,
        provenance=prov,
    )


@router.post("/chat/justify")
async def justify(request: JustifyRequest):
    """
    Justifica la última respuesta del asistente en una sesión.

    Recupera la procedencia guardada (SQL, datos brutos, tablas SIUO)
    y pide al modelo que explique detalladamente de dónde vienen los datos,
    cómo verificarlos y si se puede confiar al 100% en la respuesta.
    """
    # Obtener último mensaje del asistente
    last = _store.get_last_assistant_message(request.session_id)
    if not last:
        raise HTTPException(status_code=404, detail="No hay mensaje previo en esta sesión")

    # Recuperar la pregunta original (mensaje de usuario anterior)
    messages = _store.get_messages(request.session_id)
    original_question = ""
    for m in reversed(messages):
        if m.role == "user":
            original_question = m.content
            break

    if not last.provenance:
        return {"justification": "No hay procedencia almacenada para este mensaje."}

    try:
        justification = await _service.justify(
            original_question=original_question,
            provenance=last.provenance,
            followup=request.followup or "",
            model_id=request.model_id,
        )
    except Exception as e:
        logger.error(f"[ANALYST ROUTER] Error justificando: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    # Guardar la justificación como mensaje del asistente (sin procedencia propia)
    _store.add_message(request.session_id, "assistant", justification)

    return {"justification": justification, "session_id": request.session_id}
