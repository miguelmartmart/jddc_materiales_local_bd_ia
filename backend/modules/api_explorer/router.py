"""Router FastAPI del modulo API Explorer — DEVIA."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from backend.modules.api_explorer.service import (
    get_service, CLASES_POR_MODULO, ALL_OBJECT_CLASSES,
    _clasificar_causa, _explicar_causa
)

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

class DiscoverCredentialsRequest(BaseModel):
    empresa: str = ""       # Codigo de empresa a probar (puede ser vacio)
    url: str = ""           # URL del servidor mPYME (obtenida del autodescubrimiento)
    confirmacion: str = ""  # Debe ser "PROBAR CREDENCIALES" para ejecutar


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

@router.post("/discover-credentials")
async def discover_credentials(request: DiscoverCredentialsRequest):
    """
    Prueba credenciales por defecto conocidas contra la API mPYME.
    SEGURIDAD:
    - Requiere confirmacion='PROBAR CREDENCIALES' para ejecutar.
    - Maximo 10 intentos con 1s de delay entre cada uno.
    - Solo credenciales predeterminadas documentadas (NO diccionario de ataque).
    - Para al primer exito.
    - Registra todo en el log del servidor.
    """
    if request.confirmacion != "PROBAR CREDENCIALES":
        raise HTTPException(
            status_code=400,
            detail="Confirmacion requerida. Envia confirmacion='PROBAR CREDENCIALES' para ejecutar."
        )
    try:
        return get_service().discover_credentials(request.empresa, request.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/catalogue-full")
async def get_catalogue_full():
    """
    Catalogo completo documentado: modulos, clases, operaciones globales, campos y codigos de respuesta.
    Fuente: documentacion oficial mPYME v1.2 de Distrito K.
    """
    try:
        from backend.modules.api_explorer.api_catalogue_full import (
            get_catalogue, get_campos_clase, get_operaciones_globales, RIESGO, CODIGOS_RESPUESTA
        )
        return {
            "catalogue": get_catalogue(),
            "campos_clase": get_campos_clase(),
            "operaciones_globales": get_operaciones_globales(),
            "riesgo": {str(k): v for k, v in RIESGO.items()},
            "codigos_respuesta": {str(k): v for k, v in CODIGOS_RESPUESTA.items()},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/discover-all")
async def discover_all():
    """
    Descubrimiento COMPLETO de la API.
    Ejecuta permiso + info + browse en TODAS las clases documentadas.
    Requiere sesion activa (login previo).
    Solo lectura — no modifica ningun dato.
    Devuelve: permisos reales, campos reales del servidor, muestra de datos reales.
    """
    try:
        svc = get_service()
        result = svc.discover_all()
        svc.guardar_discover(result)  # guarda para generar_informe posterior
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/informe")
async def get_informe():
    """
    Genera informe completo multi-nivel (todos los perfiles y niveles combinados).
    Requiere discover-all previo.
    """
    try:
        return get_service().generar_informe()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class InformePerfilRequest(BaseModel):
    perfil: str = "gerente"   # gerente|ingeniero|sas|almacen|operario|mantenimiento|desarrollador
    nivel: str  = "normal"    # principiante|normal|avanzado|tecnico|raw


@router.post("/informe-perfil")
async def get_informe_perfil(request: InformePerfilRequest):
    """
    Genera informe filtrado por perfil de usuario y nivel de detalle.
    - perfil: qué clases/módulos son relevantes para ese rol
    - nivel: profundidad del lenguaje y detalle técnico
    Requiere discover-all previo. Nunca inventa datos.
    """
    try:
        return get_service().generar_informe_perfil(request.perfil, request.nivel)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SondaRequest(BaseModel):
    clase: str
    params_extra: Dict[str, Any] = Field(default_factory=dict)


@router.post("/sonda-clase")
async def sonda_clase(request: SondaRequest):
    """
    Prueba exhaustiva solo lectura de UNA clase:
    permiso + info + browse con múltiples estrategias de parámetros.
    NUNCA ejecuta new/write/edit/delete.
    Para clases code=6 (requiere_parametros), prueba variantes documentadas.
    """
    try:
        return get_service().sonda_clase(
            request.clase,
            params_extra=request.params_extra if request.params_extra else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discover-cache")
async def get_discover_cache():
    """
    Devuelve el último discover guardado (en memoria o desde disco).
    Permite al frontend mostrar datos anteriores sin volver a ejecutar discover-all.
    """
    try:
        svc = get_service()
        svc._cargar_discover_cache()
        dr = getattr(svc, '_last_discover', None)
        if not dr:
            return {"cached": False, "mensaje": "Sin discover previo. Ejecuta 'Descubrir todo' primero."}
        ts = dr.get("timestamp", "")[:19]
        empresa = dr.get("sesion", {}).get("empresa", "?")
        usuario = dr.get("sesion", {}).get("usuario", "?")
        modo = "mock" if dr.get("use_mock") else "real"
        resumen = dr.get("resumen", {})
        # Recalcular causa_real con la lógica actual (puede haber mejorado)
        clases_recalc = {}
        for cls, d in dr.get("clases", {}).items():
            d2 = dict(d)
            d2["causa_real"] = _clasificar_causa(d2)
            d2["causa_explicacion"] = _explicar_causa(d2, dr.get("use_mock", True))
            clases_recalc[cls] = d2
        return {
            "cached": True,
            "timestamp": ts,
            "empresa": empresa,
            "usuario": usuario,
            "modo": modo,
            "resumen": resumen,
            "clases": clases_recalc,
            "catalogue": dr.get("catalogue", {}),
            "use_mock": dr.get("use_mock", True),
            "success": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sondas")
async def get_sondas(limit: int = 100):
    """Historial completo de sondas ejecutadas (persiste entre reinicios)."""
    try:
        svc = get_service()
        return {
            "sondas": svc.get_sondas(limit),
            "total": len(svc._sondas),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exportar-todo")
async def exportar_todo():
    """
    Exporta TODO el conocimiento acumulado en un solo JSON:
    - Último discover (con causa_real recalculada)
    - Historial completo de llamadas
    - Historial de sondas
    - Matriz de capacidades
    - Metadatos de sesión y configuración
    Ideal para enviar como evidencia o para análisis posterior.
    """
    try:
        svc = get_service()
        svc._cargar_discover_cache()
        dr = getattr(svc, '_last_discover', None)

        # Recalcular causa_real en el discover con la lógica actual
        clases_recalc = {}
        if dr:
            for cls, d in dr.get("clases", {}).items():
                d2 = dict(d)
                d2["causa_real"] = _clasificar_causa(d2)
                d2["causa_explicacion"] = _explicar_causa(d2, dr.get("use_mock", True))
                clases_recalc[cls] = d2

        from datetime import datetime as _dt
        return {
            "exportado_en": _dt.now().isoformat(),
            "version_exportacion": "1.0",
            "descripcion": "Exportacion completa del modulo API Explorer DEVIA — JDDC",
            "discover": {
                "disponible": bool(dr),
                "timestamp": dr.get("timestamp", "") if dr else "",
                "empresa": dr.get("sesion", {}).get("empresa", "") if dr else "",
                "usuario": dr.get("sesion", {}).get("usuario", "") if dr else "",
                "modo": "mock" if (dr or {}).get("use_mock") else "real",
                "resumen": dr.get("resumen", {}) if dr else {},
                "clases": clases_recalc,
                "catalogue": dr.get("catalogue", {}) if dr else {},
            },
            "historial": {
                "total": len(svc._history),
                "llamadas": svc.get_history(500),
                "resumen": svc.resumen_historial(),
            },
            "sondas": {
                "total": len(svc._sondas),
                "resultados": svc.get_sondas(200),
            },
            "matriz": svc.get_matrix(),
            "config": {
                "api_url": svc.get_config_env().get("api_url", ""),
                "empresa_env": svc.get_config_env().get("empresa", ""),
                "usuario_env": svc.get_config_env().get("usuario", ""),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/perfiles-niveles")
async def get_perfiles_niveles():
    """Devuelve los perfiles y niveles disponibles para el selector de la UI."""
    svc = get_service()
    return {
        "perfiles": {k: {"label": v["label"], "emoji": v["emoji"], "desc": v["desc"]}
                     for k, v in svc.PERFILES.items()},
        "niveles":  {k: {"label": v["label"], "emoji": v["emoji"], "desc": v["desc"]}
                     for k, v in svc.NIVELES.items()},
    }

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
