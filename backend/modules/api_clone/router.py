"""Router FastAPI del modulo API Clone. Prefix: /api/api-clone"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from backend.modules.api_clone.service import get_service

router = APIRouter()


class BrowseRequest(BaseModel):
    clase: str
    params: Dict[str, Any] = Field(default_factory=dict)
    num: int = 50


class ReadRequest(BaseModel):
    clase: str
    objectid: str


class PermisoRequest(BaseModel):
    clase: str


class InfoRequest(BaseModel):
    clase: str


class DiscoverRequest(BaseModel):
    num_por_clase: int = 5


@router.get("/status")
async def get_status():
    """Estado del modulo: conexion BD, clases disponibles."""
    return get_service().get_status()


@router.get("/catalogue")
async def get_catalogue():
    """Catalogo de clases y operaciones disponibles (igual que API Explorer)."""
    return get_service().get_catalogue()


@router.post("/permiso")
async def permiso(request: PermisoRequest):
    """
    Simula permiso() del API Explorer.
    En lugar de llamar a mPYME, cuenta los registros reales en Firebird.
    Devuelve n_registros real, modulo, licencia y operaciones disponibles.
    """
    try:
        return get_service().permiso(request.clase)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/info")
async def info(request: InfoRequest):
    """
    Simula info() del API Explorer.
    Devuelve columnas reales de la tabla via RDB$RELATION_FIELDS.
    100% datos reales de Firebird.
    """
    try:
        return get_service().info(request.clase)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/browse")
async def browse(request: BrowseRequest):
    """
    Simula browse() del API Explorer con datos REALES de Firebird.
    - SELECT FIRST {num} cols FROM tabla WHERE filtros ORDER BY pk
    - Devuelve items + total real
    - Si la clase requiere parametro (codProyecto, codOrden...) y no se pasa,
      devuelve aviso en lugar de error (igual que code=6 en mPYME)
    """
    try:
        return get_service().browse(request.clase, request.params, request.num)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/read")
async def read(request: ReadRequest):
    """
    Simula read() del API Explorer con datos REALES de Firebird.
    SELECT por clave primaria — devuelve el registro completo.
    """
    try:
        return get_service().read(request.clase, request.objectid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/discover-all")
async def discover_all(request: DiscoverRequest):
    """
    Simula discover-all del API Explorer.
    Ejecuta permiso (conteo real) + browse (muestra real) en TODAS las clases.
    Devuelve resumen con n_registros real y muestra de cada clase.
    100% datos reales de Firebird — sin llamar a la API mPYME.
    """
    try:
        return get_service().discover_all(request.num_por_clase)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history")
async def get_history(limit: int = 100):
    """Historial de operaciones ejecutadas."""
    svc = get_service()
    return {"history": svc.get_history(limit), "total": len(svc.get_history(200))}


@router.delete("/history")
async def clear_history():
    """Limpiar historial."""
    get_service().clear_history()
    return {"ok": True, "mensaje": "Historial limpiado."}


@router.get("/matrix")
async def get_matrix():
    """Matriz de estados: que clases/operaciones se han probado."""
    return {"matrix": get_service().get_matrix(), "catalogue": get_service().get_catalogue()}
