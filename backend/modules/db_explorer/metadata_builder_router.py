"""
Router del módulo Metadata Builder.

INDEPENDENCIA: Este router es completamente independiente del router existente
(db_explorer/router.py). No modifica ni interfiere con ningún endpoint existente.

Se registra en main.py con prefix="/api/metadata-builder".

ENDPOINTS:
  GET  /status          → Estado de la IA local y resumen de metadatos actuales
  GET  /tables          → Lista de tablas de la BD con estado de metadatos
  GET  /tables/{name}   → Estructura real de una tabla (columnas, PKs, FKs, conteo)
  POST /tables/{name}/analyze  → Analiza tabla con IA local → genera metadatos JSON
  POST /tables/{name}/save     → Guarda metadatos aprobados en el JSON
  GET  /tables/{name}/metadata → Metadatos actuales de una tabla
  DELETE /tables/{name}/metadata → Elimina metadatos de una tabla
"""

import logging
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService

logger = logging.getLogger(__name__)

router = APIRouter()

# Instancia única del servicio (stateless — seguro para FastAPI)
_service = MetadataBuilderService()


# ─── Schemas de request/response ─────────────────────────────────────────────

class SaveMetadataRequest(BaseModel):
    """Payload para guardar metadatos aprobados por el usuario."""
    metadata: Dict[str, Any] = Field(
        ...,
        description="Objeto de metadatos generado por la IA (o editado manualmente)."
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    summary="Estado del módulo",
    description=(
        "Verifica disponibilidad de la IA local LAN y devuelve resumen de metadatos actuales. "
        "SEGURIDAD: Si la IA local no está disponible, el módulo está bloqueado."
    ),
)
async def get_status():
    """
    EMISOR: Frontend  RECEPTOR: MetadataBuilderService → Qwen3 LAN
    """
    try:
        ai_status = await _service.check_local_ai()
        summary   = _service.get_metadata_summary()
        return {
            "success":  True,
            "ai":       ai_status,
            "metadata": summary,
        }
    except Exception as exc:
        logger.error(f"[METADATA_BUILDER][STATUS] ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/tables",
    summary="Listar tablas de la BD",
    description="Lista todas las tablas de usuario de Firebird con su estado de metadatos.",
)
def get_tables():
    """
    EMISOR: Frontend  RECEPTOR: MetadataBuilderService → Firebird
    No requiere IA — solo consulta la BD.
    """
    try:
        result = _service.get_all_tables()
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[METADATA_BUILDER][GET_TABLES] ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/tables/{table_name}",
    summary="Estructura de una tabla",
    description=(
        "Obtiene columnas, tipos, PKs, FKs, conteo de registros y muestra de datos "
        "(sin columnas sensibles). No requiere IA."
    ),
)
def get_table_structure(
    table_name: str = Path(..., description="Nombre de la tabla Firebird", examples=["DOCLIN"])
):
    """
    EMISOR: Frontend  RECEPTOR: MetadataBuilderService → Firebird
    """
    try:
        result = _service.get_table_structure(table_name)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[METADATA_BUILDER][GET_STRUCTURE] {table_name} ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/tables/{table_name}/analyze",
    summary="Analizar tabla con IA local",
    description=(
        "Consulta la estructura de la tabla en Firebird y la envía a la IA local LAN "
        "para generar metadatos semánticos JSON. "
        "SEGURIDAD: Los datos NUNCA salen a internet. "
        "Si la IA local no está disponible, devuelve error 503."
    ),
)
async def analyze_table(
    table_name: str = Path(..., description="Nombre de la tabla a analizar", examples=["DOCLIN"])
):
    """
    EMISOR: Frontend  RECEPTOR: MetadataBuilderService → Firebird → Qwen3 LAN
    """
    try:
        result = await _service.analyze_table(table_name)
        if not result["success"]:
            # 503 si la IA no está disponible, 500 para otros errores
            status = 503 if "IA local" in result.get("error", "") else 500
            raise HTTPException(status_code=status, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[METADATA_BUILDER][ANALYZE] {table_name} ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/tables/{table_name}/save",
    summary="Guardar metadatos aprobados",
    description=(
        "Persiste los metadatos (generados por IA o editados manualmente) "
        "en db_metadata_optimized.json. El cambio es inmediato — no requiere reiniciar el servidor."
    ),
)
def save_table_metadata(
    table_name: str = Path(..., description="Nombre de la tabla", examples=["DOCLIN"]),
    body: SaveMetadataRequest = ...,
):
    """
    EMISOR: Frontend (tras aprobación del usuario)
    RECEPTOR: MetadataBuilderService → db_metadata_optimized.json
    """
    try:
        result = _service.save_table_metadata(table_name, body.metadata)
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[METADATA_BUILDER][SAVE] {table_name} ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/tables/{table_name}/metadata",
    summary="Metadatos actuales de una tabla",
    description="Devuelve los metadatos actualmente registrados para una tabla.",
)
def get_table_metadata(
    table_name: str = Path(..., description="Nombre de la tabla", examples=["ARTICULO"])
):
    try:
        result = _service.get_table_metadata(table_name)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[METADATA_BUILDER][GET_META] {table_name} ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/tables/{table_name}/metadata",
    summary="Eliminar metadatos de una tabla",
    description="Elimina los metadatos de una tabla del JSON. La tabla sigue existiendo en la BD.",
)
def delete_table_metadata(
    table_name: str = Path(..., description="Nombre de la tabla", examples=["ARTICULO"])
):
    try:
        result = _service.delete_table_metadata(table_name)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[METADATA_BUILDER][DELETE] {table_name} ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
