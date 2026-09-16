"""Router FastAPI del módulo BD Clone — DEVIA.

Prefix: /api/bd-clone
Tags:   BD Clone — SQL Directo Firebird
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from backend.modules.bd_clone.service import get_service

router = APIRouter()


# ── Modelos de petición ───────────────────────────────────────────────────────

class EjecutarSQLRequest(BaseModel):
    sql: str

class EjecutarPredefinidaRequest(BaseModel):
    query_id: str
    params: Dict[str, Any] = Field(default_factory=dict)

class TablaDetalleRequest(BaseModel):
    tabla: str

class EscrituraRequest(BaseModel):
    activar: bool
    confirmacion: str = ""

class CatalogRequest(BaseModel):
    force_refresh: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """Estado de la conexión Firebird y configuración del módulo."""
    return get_service().get_status()


@router.get("/probar-conexion")
async def probar_conexion():
    """
    Prueba la conexión real a Firebird.
    Hace SELECT COUNT(*) sobre RDB$RELATIONS y devuelve n_tablas y ms.
    No devuelve datos de negocio.
    """
    return get_service().probar_conexion()


@router.post("/catalogo")
async def get_catalogo(request: CatalogRequest):
    """
    Lista todas las tablas de usuario de la BD Firebird.
    Incluye n_columnas. n_registros es null (se obtiene bajo demanda con /tabla-detalle).
    Caché de 1 hora — usa force_refresh=true para forzar actualización.
    """
    try:
        return get_service().get_catalog(force_refresh=request.force_refresh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/tabla-detalle")
async def get_tabla_detalle(request: TablaDetalleRequest):
    """
    Detalle de una tabla: columnas (campo, tipo, posición) + conteo + primeras 5 filas.
    Solo lectura.
    """
    try:
        return get_service().get_tabla_detalle(request.tabla)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ejecutar-sql")
async def ejecutar_sql(request: EjecutarSQLRequest):
    """
    Ejecuta un SQL SELECT libre contra Firebird real.
    - Solo permite SELECT salvo que modo_escritura esté activo.
    - Limita el resultado a 500 filas (MAX_ROWS_SELECT).
    - Inyecta FIRST 500 automáticamente si no hay FIRST/SKIP ya.
    - Registra en historial (sql_preview, ms, n_filas).
    """
    try:
        return get_service().ejecutar_sql(request.sql)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/consultas-predefinidas")
async def get_consultas_predefinidas():
    """
    Lista las consultas de la query_library del proyecto compatibles con Firebird real.
    Son las mismas que usa el Chat IA. Excluye consultas SQLite-only.
    """
    try:
        consultas = get_service().get_consultas_predefinidas()
        return {
            "consultas": consultas,
            "total": len(consultas),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ejecutar-predefinida")
async def ejecutar_predefinida(request: EjecutarPredefinidaRequest):
    """
    Ejecuta una consulta predefinida de la query_library con los parámetros indicados.
    Los parámetros sustituyen {{param}} o :param en el SQL.
    """
    try:
        return get_service().ejecutar_predefinida(request.query_id, request.params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/diagnostico")
async def diagnostico():
    """
    Diagnóstico completo: conexión Firebird + conteo de 12 tablas clave.
    Sin devolver valores de negocio — solo estados y conteos.
    """
    try:
        return get_service().diagnostico()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/historial")
async def get_historial(limit: int = 50):
    """Historial de las últimas N consultas ejecutadas (máx. 200)."""
    return {
        "historial": get_service().get_history(limit),
        "total": len(get_service().get_history(200)),
    }


@router.delete("/historial")
async def clear_historial():
    """Limpiar el historial de consultas."""
    get_service().clear_history()
    return {"ok": True, "mensaje": "Historial limpiado correctamente."}


@router.post("/escritura")
async def control_escritura(request: EscrituraRequest):
    """
    Activa/desactiva el modo escritura.
    Para ACTIVAR se requiere confirmacion='ACTIVAR ESCRITURA BD'.
    En modo escritura se permiten INSERT/UPDATE/DELETE además de SELECT.
    """
    svc = get_service()
    if request.activar:
        return svc.activar_escritura(request.confirmacion)
    else:
        return svc.desactivar_escritura()
