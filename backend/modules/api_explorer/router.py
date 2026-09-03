"""Router FastAPI del modulo API Explorer — DEVIA."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from backend.modules.api_explorer.service import get_service, CLASES_POR_MODULO, ALL_OBJECT_CLASSES

router = APIRouter()


class LoginRequest(BaseModel):
    empresa: str = ""
    usuario: str = ""
    password: str = ""

class EjecutarRequest(BaseModel):
    clase: str
    operacion: str
    params: Dict[str, Any] = Field(default_factory=dict)

class ModoRequest(BaseModel):
    use_mock: bool

class EscrituraRequest(BaseModel):
    activar: bool
    confirmacion: str = ""  # Debe ser "ACTIVAR ESCRITURA" para activar

class DiscoverRequest(BaseModel):
    host: str = ""  # Host extra a probar (ademas del DB_HOST del .env)


@router.get("/status")
async def get_status():
    """Estado actual de la sesion y configuracion."""
    return get_service().get_status()

@router.get("/config")
async def get_config():
    """Configuracion de variables de entorno (sin datos sensibles)."""
    return get_service().get_config_env()

@router.get("/catalogue")
async def get_catalogue():
    """Catalogo completo de modulos, clases y operaciones documentadas."""
    return {"catalogue": CLASES_POR_MODULO, "all_classes": ALL_OBJECT_CLASSES}

@router.post("/login")
async def login(request: LoginRequest):
    """Iniciar sesion con la API Distrito K (real o mock)."""
    try:
        result = get_service().login(request.empresa, request.usuario, request.password)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout():
    """Cerrar sesion y liberar el slot de conexion."""
    try:
        return get_service().logout()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ejecutar")
async def ejecutar(request: EjecutarRequest):
    """
    Ejecutar cualquier operacion de la API (browse, read, permiso, info, new, write, cancel, imputaPro).
    Las operaciones de escritura estan bloqueadas si modo_escritura=False.
    """
    try:
        return get_service().ejecutar(request.clase, request.operacion, request.params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/modo")
async def cambiar_modo(request: ModoRequest):
    """Cambiar entre BD Simulada (mock) y API Real."""
    svc = get_service()
    svc.use_mock = request.use_mock
    if svc.session_active:
        svc.session_active = False; svc.ssid1 = ""; svc.ssid2 = ""
    return {"use_mock": svc.use_mock, "session_reset": True}

@router.post("/escritura")
async def control_escritura(request: EscrituraRequest):
    """
    Activar/desactivar modo escritura.
    Para ACTIVAR se requiere confirmacion='ACTIVAR ESCRITURA'.
    """
    svc = get_service()
    if request.activar:
        if request.confirmacion != "ACTIVAR ESCRITURA":
            raise HTTPException(status_code=400, detail="Confirmacion incorrecta. Escribe exactamente: ACTIVAR ESCRITURA")
        svc.modo_escritura = True
        return {"modo_escritura": True, "mensaje": "Modo escritura ACTIVADO. Proceder con maxima cautela."}
    else:
        svc.modo_escritura = False
        return {"modo_escritura": False, "mensaje": "Modo escritura DESACTIVADO. Solo lectura activa."}

@router.get("/history")
async def get_history(limit: int = 50):
    """Historial de las ultimas N operaciones realizadas."""
    return {"history": get_service().get_history(limit), "resumen": get_service().resumen_historial()}

@router.delete("/history")
async def clear_history():
    """Limpiar el historial de operaciones."""
    get_service().clear_history()
    return {"mensaje": "Historial limpiado correctamente."}

@router.get("/matrix")
async def get_matrix():
    """Matriz de capacidades: resultado de todas las pruebas realizadas."""
    return {"matrix": get_service().get_matrix(), "catalogue": CLASES_POR_MODULO}

@router.post("/discover")
async def discover_url(request: DiscoverRequest):
    """
    Descubrimiento automatico de la URL de la API mPYME.
    Prueba puertos tipicos (8081 principal segun doc v1.2, mas 8080, 80, 443...)
    en el servidor Firebird (DB_HOST del .env) y en el host indicado.
    No requiere sesion activa. Solo lectura, sin riesgo.
    """
    try:
        return get_service().discover_url(extra_host=request.host)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/discover-db")
async def discover_from_db():
    """
    Autodescubrimiento seguro desde Firebird.
    Lee usuarios del motor (RDB$USERS) y de SQL Obras (USDLOGIN, USUARIS, etc.)
    mediante SELECT de solo lectura.
    Sin escrituras. Sin ataques de fuerza bruta.
    La password no puede descubrirse automaticamente.
    Requiere que DB_HOST, DB_NAME, DB_USER y DB_PASSWORD esten configurados en .env.
    """
    try:
        return get_service().discover_from_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
