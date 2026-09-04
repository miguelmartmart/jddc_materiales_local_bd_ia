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


@router.post("/sonda-rapida")
async def sonda_rapida(body: dict):
    """
    Versión ligera de sonda para el Plan de pruebas:
    lanza browse(params) directamente y devuelve código, datos y causa.
    Solo lectura. Sin modal — resultado inline en el Plan.
    """
    try:
        svc = get_service()
        if not svc.session_active:
            return {"success": False, "error": "Sin sesión activa. Haz login primero."}
        clase = (body.get("clase") or "").strip()
        op    = (body.get("op") or "browse").strip()
        params = body.get("params") or {}
        if not clase:
            return {"success": False, "error": "Parámetro 'clase' requerido."}
        if op != "browse":
            return {"success": False, "error": f"sonda-rapida solo admite 'browse' (op={op})."}
        # Filtrar params con "?" — no ejecutar con valores placeholder
        params_limpios = {k: v for k, v in params.items() if v != "?"}
        raw, ms = svc._client().browse(svc.ssid1, svc.ssid2, clase, params_limpios)
        code = raw.get("code")
        data = raw.get("data") or raw.get("items") or []
        items = data if isinstance(data, list) else []
        from backend.modules.api_explorer.service import _clasificar_causa, _explicar_causa
        entry = {
            "permiso_code": None,
            "browse_code": code,
            "browse_raw": {"data": str(raw.get("data", ""))[:200]},
            "info_code": None,
            "muestra": items[:5],
            "campos_reales": [],
        }
        causa = _clasificar_causa(entry)
        expl  = _explicar_causa(entry, svc.use_mock)
        return {
            "success": True,
            "clase": clase,
            "params_enviados": params_limpios,
            "code": code,
            "duracion_ms": round(ms, 1),
            "n_items": len(items),
            "datos": items[:10],
            "causa": causa,
            "explicacion": expl,
            "raw_data": str(raw.get("data", ""))[:300],
            "modo": "mock" if svc.use_mock else "real",
        }
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


@router.get("/plan-pruebas")
async def get_plan_pruebas():
    """
    Plan de pruebas pendientes basado en el discover actual.
    Indica qué falta probar, con qué params y por qué.
    """
    svc = get_service()
    svc._cargar_discover_cache()
    dr = getattr(svc, '_last_discover', None)

    obs_fijas = [
        {"icono":"⚠️","titulo":"permiso.data='Ok' siempre (string, sin flags de operaciones)",
         "detalle":"En esta instalación permiso no devuelve browse:true/write:true. Los permisos de operación solo se conocen probando empiricamente cada una.",
         "accion":"Probar browse, read, new+cancel en cada clase accesible."},
        {"icono":"⚠️","titulo":"info devuelve data=true (booleano) — sin metadatos de campos",
         "detalle":"info no devuelve metadatos en esta instalación. Los campos reales solo se ven en la respuesta de browse con datos.",
         "accion":"Cuando browse devuelva datos, analizar las claves del primer registro."},
        {"icono":"🚫","titulo":"Módulo 'Documentos' no contratado (5 clases bloqueadas)",
         "detalle":"docalbcom, docfaccom, docpedcom, articulos, proveedores. Mensaje: 'No dispone de licencia para el módulo Documentos'. Bloquea también imputaPro.",
         "accion":"Preguntar precio del módulo Documentos a Distrito K. Sin él no se puede vincular compras a obras."},
        {"icono":"✅","titulo":"Módulos Reparaciones y Proyectos confirmados con licencia",
         "detalle":"reporden, repobjetos, repinst, tipostrabajo, repordutil + proyectos, partidas, proordutil, proordprev + clientes, ordenfab, recursos.",
         "accion":"Construir sobre estos módulos."},
    ]

    if not dr:
        return {"discover_disponible":False,"observaciones_fijas":obs_fijas,"pruebas_pendientes":[],"pruebas_completadas":[]}

    clases = dr.get("clases", {})
    sondas_hechas = {s["clase"] for s in svc._sondas if s.get("datos_reales")}

    PRUEBAS = [
        ("proyectos","browse",{"num":20},"Listar obras/proyectos","🔴","Necesario para obtener códigos reales de obra"),
        ("proyectos","browse",{"estado":"activo"},"Listar solo obras activas","🔴","Filtro más útil en operación real"),
        ("reporden","browse",{"num":20},"Listar órdenes de reparación","🔴","Dato base módulo mantenimiento"),
        ("reporden","browse",{"estado":"abierta"},"Listar reparaciones abiertas","🔴","Filtro operacional"),
        ("recursos","browse",{"num":50},"Listar recursos (operarios/maquinaria)","🔴","Necesario para imputar horas — conocer codRecurso"),
        ("clientes","browse",{"num":50},"Listar clientes","🟡","Los proyectos tienen cliente — filtros"),
        ("tipostrabajo","browse",{"num":100},"Listar tipos de trabajo","🟡","Tabla maestra para desplegable en app"),
        ("repobjetos","browse",{"num":50},"Listar equipos reparables","🟡","Crear órdenes reparación"),
        ("repinst","browse",{"num":50},"Listar instalaciones","🟡","Jerarquía instalación>equipo>orden"),
        ("partidas","browse",{"codProyecto":"?"},"Listar partidas de obra (con codProyecto real)","🟡","Necesita codProyecto de browse proyectos"),
        ("proordutil","browse",{"codProyecto":"?"},"Listar costes imputados a una obra","🟡","Ver utilizados — necesita codProyecto real"),
        ("proordprev","browse",{"codProyecto":"?"},"Listar previstos de una obra","🟡","Comparar previsto vs real"),
        ("repordutil","browse",{"codOrden":"?"},"Listar utilizados de una reparación","🟠","Necesita codOrden de browse reporden"),
        ("proyectos","read",{"objectid":"?"},"Leer detalle de una obra","🟠","read individual — más detalle"),
        ("reporden","read",{"objectid":"?"},"Leer detalle de una orden","🟠","read individual"),
        ("reporden","new",{},"Crear orden temporal (new + cancel)","🟠","Verifica si podemos crear — cancel descarta sin persistir"),
        ("proordutil","new",{"codProyecto":"?","codPartida":"?","tipo":"M"},"Crear utilizado temporal (new + cancel)","🟠","Verifica si write disponible"),
        ("ordenfab","browse",{"num":20},"Listar órdenes de fabricación","⚪","permiso=0 confirmado — solo falta browse con params"),
    ]

    pendientes, completadas = [], []
    for (clase,op,params,desc,prio,por_que) in PRUEBAS:
        drC = clases.get(clase, {})
        tiene_datos = bool(drC.get("muestra") or drC.get("browse_params_exitosos"))
        tiene_sonda = clase in sondas_hechas
        completada = (op=="browse" and tiene_datos and "?" not in str(params)) or (op=="browse" and tiene_sonda)
        e = {"clase":clase,"operacion":op,"params_sugeridos":params,"descripcion":desc,"prioridad":prio,"por_que":por_que,"causa_actual":drC.get("causa_real",""),"tiene_datos":tiene_datos,"tiene_sonda":tiene_sonda,"nota_params":"Sustituir '?' por valor real de browse previo" if "?" in str(params) else ""}
        (completadas if completada else pendientes).append(e)

    return {"discover_disponible":True,"discover_timestamp":dr.get("timestamp","")[:19],"empresa":dr.get("sesion",{}).get("empresa",""),"total_pruebas":len(PRUEBAS),"pendientes":len(pendientes),"completadas":len(completadas),"observaciones_fijas":obs_fijas,"pruebas_pendientes":pendientes,"pruebas_completadas":completadas}


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
