"""
SIUORouter — Endpoints del Sistema de Indices Ultra-Optimizado.

ENDPOINTS:
  POST /api/siuo/analyze/start          Inicia analisis completo (SSE streaming)
  GET  /api/siuo/analyze/progress       Estado actual del proceso
  GET  /api/siuo/stats                  Estadisticas de los indices
  GET  /api/siuo/learning/suggestions   Sugerencias de autoaprendizaje
  POST /api/siuo/learning/feedback      Registrar feedback de SQL
  POST /api/siuo/reload                 Recargar indices en memoria
  GET  /api/siuo/context/test           Probar recuperacion de contexto

SEGURIDAD:
  - Solo usa Qwen3 LAN. Ningun dato sale a internet.
  - Validacion de entrada en todos los endpoints.
  - Errores siempre devuelven JSON estructurado.

PATRONES:
  - SSE (Server-Sent Events) para progreso en tiempo real
  - Singleton para DeepIndexerService y ContextRetriever
  - Respuestas tipadas con modelos Pydantic
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.modules.db_explorer.deep_indexer_service import get_deep_indexer
from backend.modules.db_explorer.context_retriever import (
    get_context_retriever,
    reload_context_retriever,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Modelos Pydantic ─────────────────────────────────────────────────────────

class AnalyzeStartRequest(BaseModel):
    batch_size: int   = Field(default=5,    ge=1, le=20,  description="Tablas por batch")
    resume:     bool  = Field(default=True,               description="Reanudar desde donde se quedo")


class FeedbackRequest(BaseModel):
    question:    str  = Field(..., min_length=1, max_length=500)
    sql_used:    str  = Field(..., min_length=1, max_length=2000)
    was_correct: bool = Field(...)
    tables_used: list = Field(default_factory=list)


class ContextTestRequest(BaseModel):
    question:   str = Field(..., min_length=1, max_length=500)
    max_tokens: int = Field(default=2000, ge=100, le=8000)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze/start", summary="Iniciar analisis completo de BD con Qwen3 (SSE)")
async def start_analysis(req: AnalyzeStartRequest):
    """
    Inicia el analisis completo de todas las tablas de Firebird con Qwen3 LAN.
    Devuelve un stream SSE con eventos de progreso en tiempo real.

    Eventos SSE:
      data: {"type": "start",    "total": N, "pending": M, "message": "..."}
      data: {"type": "progress", "table": "X", "done": N, "total": M, "status": "ok"|"error"}
      data: {"type": "phase",    "phase": "graph"|"concepts"|"values", "message": "..."}
      data: {"type": "complete", "done": N, "failed": K, "message": "..."}
      data: {"type": "error",    "message": "..."}
    """
    indexer = get_deep_indexer()

    async def event_generator():
        try:
            async for event in indexer.analyze_all_tables_batch(
                batch_size=req.batch_size,
                resume=req.resume,
            ):
                # Formato SSE: "data: {json}\n\n"
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                # Tras completar, recargar indices en memoria
                if event.get("type") == "complete":
                    reload_context_retriever()
                    yield f"data: {json.dumps({'type': 'reload', 'message': 'Indices recargados en memoria'})}\n\n"

        except asyncio.CancelledError:
            logger.info("[SIUO Router] Cliente desconectado durante el analisis")
        except Exception as exc:
            logger.error(f"[SIUO Router] Error en SSE: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)[:300]})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analyze/progress", summary="Estado actual del proceso de indexacion")
async def get_progress():
    """Devuelve el estado actual del proceso de indexacion (sin iniciar nada)."""
    indexer = get_deep_indexer()
    return indexer.get_progress()


@router.get("/stats", summary="Estadisticas de los indices SIUO")
async def get_stats():
    """
    Devuelve estadisticas de los indices actuales:
    - Tablas indexadas
    - Nodos y aristas del grafo
    - Keywords en concept_index
    - Enumerados y rangos en value_index
    """
    indexer   = get_deep_indexer()
    retriever = get_context_retriever()

    return {
        "indexer":   indexer.get_index_stats(),
        "retriever": retriever.get_stats(),
    }


@router.get("/learning/suggestions", summary="Sugerencias de autoaprendizaje")
async def get_learning_suggestions():
    """
    Devuelve sugerencias basadas en el historial de consultas:
    - Keywords frecuentes sin mapear en concept_index
    - Tablas mas usadas
    - Total de consultas registradas
    """
    retriever = get_context_retriever()
    return retriever.get_learning_suggestions()


@router.post("/learning/feedback", summary="Registrar feedback de SQL")
async def register_feedback(req: FeedbackRequest):
    """
    Registra si el SQL generado fue correcto o no.
    Permite al sistema aprender de los errores para mejorar el concept_index.
    """
    retriever = get_context_retriever()
    retriever.register_feedback(
        question=req.question,
        sql_used=req.sql_used,
        was_correct=req.was_correct,
        tables_used=req.tables_used,
    )
    return {"success": True, "message": "Feedback registrado correctamente"}


@router.post("/reload", summary="Recargar indices en memoria")
async def reload_indices():
    """
    Fuerza la recarga de todos los indices desde disco.
    Util tras una nueva indexacion o modificacion manual de los ficheros JSON.
    """
    retriever = reload_context_retriever()
    stats     = retriever.get_stats()
    return {
        "success": True,
        "message": "Indices recargados correctamente",
        "stats":   stats,
    }


@router.post("/context/test", summary="Probar recuperacion de contexto para una pregunta")
async def test_context(req: ContextTestRequest):
    """
    Prueba el ContextRetriever con una pregunta de ejemplo.
    Devuelve el contexto que se enviaria a la IA + metadatos de trazabilidad.
    Util para depurar y validar el sistema de indices.
    """
    retriever = get_context_retriever()
    context, meta = retriever.get_context(
        question=req.question,
        max_tokens=req.max_tokens,
    )
    return {
        "question":        req.question,
        "context_preview": context[:1000] + ("..." if len(context) > 1000 else ""),
        "context_length":  len(context),
        "meta":            meta,
    }
