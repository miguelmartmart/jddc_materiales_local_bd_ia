"""
Router FastAPI del modulo API Clone. Prefix: /api/api-clone

Sistema de proteccion de escritura (3 niveles, segun doc mPYME v1.2):
  Nivel 0 — lectura: browse/read/permiso/info/cancel → siempre disponible
  Nivel 1 — temporal: new/edit → requiere Paso 1 (ACTIVAR ESCRITURA)
  Nivel 2 — ESCRITURA REAL: write/imputaPro/imputaRep → requiere Paso 1 + Paso 2 (CONFIRMAR ESCRITURA)
                              + confirmacion en body de cada peticion
  Nivel 3 — DESTRUCTIVO: delete → requiere confirmacion='CONFIRMAR BORRADO DEFINITIVO'
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from backend.modules.api_clone.service import get_service

router = APIRouter()


# ── Modelos de peticion ───────────────────────────────────────────────────────

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


class NewRequest(BaseModel):
    clase: str


class EditRequest(BaseModel):
    clase: str
    objectid: str
    data: Dict[str, Any] = Field(default_factory=dict)


class CancelRequest(BaseModel):
    clase: str
    objectid: str


class WriteRequest(BaseModel):
    clase: str
    objectid: str
    data: Dict[str, Any] = Field(default_factory=dict)
    confirmacion: str = ""   # Debe ser exactamente 'CONFIRMAR ESCRITURA'


class ImputaRequest(BaseModel):
    clase: str
    objectid: str
    accion: str              # 'imputaPro' | 'imputaRep' | 'imputaFab'
    cod_maestro: str
    cod_detalle: str = ""
    subcontrata: str = "F"
    confirmacion: str = ""   # Debe ser exactamente 'CONFIRMAR ESCRITURA'


class EscrituraP1Request(BaseModel):
    confirmacion: str = ""   # Debe ser 'ACTIVAR ESCRITURA'


class EscrituraP2Request(BaseModel):
    confirmacion: str = ""   # Debe ser 'CONFIRMAR ESCRITURA'


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


class ValoresCampoRequest(BaseModel):
    campo: str     # nombre del parametro API: codProyecto, codOrden, etc.
    limit: int = 15


@router.post("/valores-campo")
async def valores_campo(request: ValoresCampoRequest):
    """
    Devuelve valores reales de la BD para autocompletar un campo en el Probador Manual.
    Usa el LOOKUP_CAMPO del queries.py para saber que tabla y columnas consultar.
    - campo='codProyecto' → SELECT FIRST N CODIGO, NOMBRE FROM PROYECTOS
    - campo='codOrden'    → SELECT FIRST N CODIGO, DESCRIPCION FROM REPARA
    - etc.

    Solo lectura. Sin modificar datos.
    Devuelve lista de {id, desc} con valores reales de produccion.
    """
    try:
        return get_service().valores_campo(request.campo, request.limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/fiabilidad/{clase}")
async def get_fiabilidad(clase: str):
    """
    Devuelve la explicacion de fiabilidad de los resultados para una clase:
    - nivel (ULTRA/ALTO/MEDIO)
    - por que son fiables (PK directa, FK que garantiza aislamiento...)
    - SQL de ejemplo ejecutado
    - detalle de claves usadas
    """
    from backend.modules.api_clone.queries import FIABILIDAD_CLASE
    f = FIABILIDAD_CLASE.get(clase)
    if not f:
        raise HTTPException(status_code=404, detail=f"Clase '{clase}' sin datos de fiabilidad")
    return {"clase": clase, **f}


@router.get("/campos/{clase}")
async def get_campos_clase(clase: str):
    """
    Devuelve los campos/parametros de una clase con:
    - descripcion en texto natural
    - tipo de dato
    - si es obligatorio
    - ejemplo de valor
    - tabla FK donde buscar valores reales (para el boton 'Buscar en BD')
    """
    from backend.modules.api_clone.queries import CAMPOS_CLASE
    campos = CAMPOS_CLASE.get(clase)
    if campos is None:
        raise HTTPException(status_code=404, detail=f"Clase '{clase}' sin metadatos de campos")
    return {"clase": clase, "campos": campos}


# ── ENDPOINTS DE ESCRITURA (protegidos por 2 niveles de confirmacion) ─────────

@router.post("/new")
async def new(request: NewRequest):
    """
    RIESGO 1 — Crea objeto TEMPORAL en sesion (NO persiste hasta write).
    Requiere: modo_escritura=True (Paso 1).
    Semantica identica a new() de mPYME v1.2.
    El objeto es temporal — usa cancel() para descartarlo o write() para persistirlo.
    """
    try:
        return get_service().new(request.clase)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/edit")
async def edit(request: EditRequest):
    """
    RIESGO 1 — Modifica datos del objeto temporal en memoria (NO persiste hasta write).
    Requiere: modo_escritura=True (Paso 1) + objectid valido de un new() previo.
    """
    try:
        return get_service().edit(request.clase, request.objectid, request.data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cancel")
async def cancel(request: CancelRequest):
    """
    RIESGO 0 — Descarta objeto temporal. Seguro, no persiste nada.
    Usar siempre cuando se hace new/edit y no se quiere persistir.
    """
    try:
        return get_service().cancel(request.clase, request.objectid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/write")
async def write(request: WriteRequest):
    """
    RIESGO 2 — ESCRITURA REAL IRREVERSIBLE. Persiste en Firebird via INSERT.

    REQUISITOS (los 3 deben cumplirse):
      1. Paso 1 activo: POST /escritura/activar-paso1 con confirmacion='ACTIVAR ESCRITURA'
      2. Paso 2 activo: POST /escritura/activar-paso2 con confirmacion='CONFIRMAR ESCRITURA'
      3. Este body: { confirmacion: 'CONFIRMAR ESCRITURA' }

    Flujo correcto:
      1. POST /new { clase: 'proyectos' }                    → objectid=TMP_PROYECTOS_XXXXXXXX
      2. POST /edit { clase, objectid, data: { nombre: ... } } → datos en memoria
      3. POST /write { clase, objectid, data, confirmacion: 'CONFIRMAR ESCRITURA' } → INSERT en BD

    IMPORTANTE: Operacion IRREVERSIBLE. Modifica la BD de produccion definitivamente.
    """
    try:
        return get_service().write(request.clase, request.objectid, request.data, request.confirmacion)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/imputa")
async def imputa(request: ImputaRequest):
    """
    RIESGO 2 — ESCRITURA REAL IRREVERSIBLE. Imputa linea de compra a Proyecto/Reparacion.

    Segun documentacion oficial mPYME v1.2 pag.26-27:
      imputaPro: vincula linea de docalbcom/docfaccom a un proyecto (codMaestro=codProyecto, codDetalle=codPartida)
      imputaRep: vincula linea a una orden de reparacion (codMaestro=codOrden, codDetalle=codFase)
      imputaFab: vincula linea a una orden de fabricacion

    REQUISITOS: Paso 1 + Paso 2 activos + confirmacion='CONFIRMAR ESCRITURA' en body.
    IMPORTANTE: Operacion IRREVERSIBLE. Inserta en DOCLINIMPUTACION de produccion.
    """
    try:
        return get_service().imputa(
            request.clase, request.objectid, request.accion,
            request.cod_maestro, request.cod_detalle,
            request.subcontrata, request.confirmacion
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/objetos-temporales")
async def get_objetos_temporales():
    """Lista objetos en sesion temporal (new pero sin write todavia)."""
    return get_service().get_objetos_temporales()


# ── CONTROL DE ESCRITURA (activacion por pasos) ────────────────────────────────

@router.post("/escritura/activar-paso1")
async def activar_escritura_paso1(request: EscrituraP1Request):
    """
    PASO 1/2 — Activa new/edit (operaciones temporales, riesgo 1).
    Requiere body: { confirmacion: 'ACTIVAR ESCRITURA' }
    Este paso NO habilita write ni imputaPro — esos requieren el Paso 2.
    """
    return get_service().activar_modo_escritura(request.confirmacion)


@router.post("/escritura/activar-paso2")
async def activar_escritura_paso2(request: EscrituraP2Request):
    """
    PASO 2/2 — Activa write/imputaPro (ESCRITURA REAL IRREVERSIBLE, riesgo 2).
    Requiere: Paso 1 activo + body: { confirmacion: 'CONFIRMAR ESCRITURA' }

    ADVERTENCIA: Tras activar este paso, write/imputaPro modifican la BD de produccion.
    Cada peticion de write/imputaPro requiere ADEMAS confirmacion='CONFIRMAR ESCRITURA' en su body.
    """
    return get_service().activar_session_escritura(request.confirmacion)


@router.post("/escritura/desactivar")
async def desactivar_escritura():
    """
    Desactiva AMBOS niveles de escritura.
    Descarta todos los objetos temporales pendientes.
    """
    return get_service().desactivar_escritura()


@router.get("/escritura/estado")
async def estado_escritura():
    """Estado actual de los niveles de escritura y objetos temporales."""
    svc = get_service()
    return {
        "modo_escritura": svc.modo_escritura,
        "session_escritura": svc.session_escritura,
        "objetos_temporales": len(svc._objetos_temporales),
        "guia": {
            "paso_1": "POST /escritura/activar-paso1 con confirmacion='ACTIVAR ESCRITURA' → habilita new/edit",
            "paso_2": "POST /escritura/activar-paso2 con confirmacion='CONFIRMAR ESCRITURA' → habilita write/imputaPro",
            "cada_write": "Cada peticion de /write o /imputa requiere ademas confirmacion='CONFIRMAR ESCRITURA'",
            "desactivar": "POST /escritura/desactivar → vuelve a solo lectura",
        }
    }
