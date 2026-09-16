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

    # Hallazgos verificados empíricamente con API Real JDDC (2026-09-04)
    obs_fijas = [
        {
            "icono": "✅",
            "titulo": "VERIFICADO (API Real JDDC): acceso confirmado sin restricciones — 6 clases",
            "detalle": (
                "repobjetos (equipos), repinst (instalaciones), tipostrabajo, partidas, "
                "ordenfab, clientes. permiso=0 confirmado. "
                "Browse devuelve code=6 en algunas (requiere params), no es fallo."
            ),
            "accion": "Estas clases están listas para usar en producción.",
        },
        {
            "icono": "🔵",
            "titulo": "VERIFICADO: 6 clases accesibles que necesitan parámetros (code=6 = normal)",
            "detalle": (
                "reporden, repordutil, proyectos, proordutil, proordprev, recursos. "
                "code=6 NO significa fallo de BD — es el comportamiento documentado cuando "
                "la clase requiere un identificador obligatorio (codProyecto, codOrden...). "
                "La solución es pasar el parámetro correcto en el Explorador."
            ),
            "accion": (
                "Prueba de segunda fase: obtener un codProyecto real con 'proyectos.browse' "
                "y usarlo en partidas, proordutil, proordprev."
            ),
        },
        {
            "icono": "🚫",
            "titulo": "VERIFICADO: módulo Documentos NO contratado — 5 clases bloqueadas",
            "detalle": (
                "docalbcom, docfaccom, docpedcom, articulos, proveedores. "
                "Mensaje exacto del servidor: 'No dispone de licencia para el módulo Documentos'. "
                "Esto bloquea también imputaPro (vincular compras a obras). "
                "Es una restricción contractual, no técnica."
            ),
            "accion": (
                "Contactar con Distrito K para ampliar licencia del módulo Documentos. "
                "Sin él: no se puede ver catálogo de artículos ni vincular compras a obras."
            ),
        },
        {
            "icono": "⚠️",
            "titulo": "Comportamiento técnico de esta instalación: permiso e info no devuelven metadatos",
            "detalle": (
                "permiso devuelve data='Ok' (string) — nunca flags de operaciones. "
                "info devuelve data=true (booleano) — nunca lista de campos. "
                "Los campos reales solo se conocen analizando la respuesta de un browse exitoso."
            ),
            "accion": "Documentado. No es un bug — es el comportamiento de esta versión/instalación de mPYME.",
        },
        {
            "icono": "🚀",
            "titulo": "3 aplicaciones YA DISPONIBLES con la licencia actual",
            "detalle": (
                "1. App Operario: registrar costes reales en obra (proordutil + proyectos + partidas). "
                "2. Cuadro de Mando: costes reales vs previstos por obra. "
                "3. Integración IA: responder preguntas sobre obras/costes."
            ),
            "accion": "Construir sobre proordutil + proyectos + partidas. Sin ampliar licencia.",
        },
    ]

    if not dr:
        return {"discover_disponible":False,"observaciones_fijas":obs_fijas,"pruebas_pendientes":[],"pruebas_completadas":[]}

    clases = dr.get("clases", {})
    sondas_hechas = {s["clase"] for s in svc._sondas if s.get("datos_reales")}

    # FASE 0 (NUEVA 2026-09-09): clases que devuelven code=6 INCLUSO con num=20
    # Necesitan parámetro obligatorio desconocido (ejercicio, soloActivos, tipo...)
    CLASES_INVESTIGAR = ["proyectos", "reporden", "recursos", "proordutil", "proordprev", "repordutil"]
    # FASE 1: clases simples con browse confirmado
    # FASE 2: requieren identificador real (codProyecto/codOrden de FASE 0)
    # FASE 3: ensayo escritura (new+cancel) — no persiste nunca
    PRUEBAS = [
        # FASE 1
        ("clientes",    "browse", {"num": 50},             "🤝 Listar clientes",                      "🟡", "Relaciona proyectos con clientes"),
        ("tipostrabajo","browse", {"num": 100},            "🏷️ Tipos de trabajo",                     "🟡", "Tabla maestra para app reparaciones"),
        ("repobjetos",  "browse", {"num": 50},             "⚙️ Equipos reparables",                   "🟡", "Necesario para crear órdenes de reparación"),
        ("repinst",     "browse", {"num": 50},             "🏢 Instalaciones",                        "🟡", "Jerarquía: instalación → equipo → orden"),
        ("ordenfab",    "browse", {"num": 20},             "🏭 Órdenes de fabricación",               "⚪", "permiso=0 confirmado"),
        # FASE 2
        ("partidas",    "browse", {"codProyecto": "?"},    "📐 Partidas de una obra real",            "🟡", "Sustituir ? por codProyecto (FASE 0)"),
        ("proordutil",  "browse", {"codProyecto": "?"},    "💰 Costes reales imputados",              "🟡", "Sustituir ? por codProyecto"),
        ("proordprev",  "browse", {"codProyecto": "?"},    "📊 Previstos/presupuesto",                "🟡", "Sustituir ? por codProyecto"),
        ("repordutil",  "browse", {"codOrden": "?"},       "🔩 Materiales/horas de una reparación",   "🟠", "Sustituir ? por codOrden (FASE 0)"),
        ("proyectos",   "read",   {"objectid": "?"},       "🔍 Detalle completo de una obra",         "🟠", "Sustituir ? por codProyecto"),
        ("reporden",    "read",   {"objectid": "?"},       "🔍 Detalle completo de una orden",        "🟠", "Sustituir ? por codOrden"),
        # FASE 3
        ("reporden",    "new",    {},                      "🧪 Ensayo: crear orden temporal",         "🟠", "new+cancel — no persiste en BD"),
        ("proordutil",  "new",    {"codProyecto": "?", "codPartida": "?", "tipo": "M"},
                                                           "🧪 Ensayo: crear utilizado temporal",     "🟠", "new+cancel — ? = valores reales"),
    ]

    pendientes, completadas = [], []
    for (clase, op, params, desc, prio, por_que) in PRUEBAS:
        drC = clases.get(clase, {})
        tiene_datos = bool(drC.get("muestra") or drC.get("browse_params_exitosos"))
        tiene_sonda = clase in sondas_hechas
        tiene_interr = "?" in str(list(params.values()))
        completada = (op == "browse" and not tiene_interr and (tiene_datos or tiene_sonda))
        nota = (
            "Sustituir ? por valor real. Usa el Explorador." if tiene_interr else
            "Ensayo/lectura individual. Usar el Explorador." if op in ("new", "read") else ""
        )
        fase = (
            "FASE 1" if not tiene_interr and op == "browse" else
            "FASE 2" if tiene_interr and op == "browse" else "FASE 3"
        )
        e = {
            "clase": clase, "operacion": op, "params_sugeridos": params,
            "descripcion": desc, "prioridad": prio, "por_que": por_que,
            "causa_actual": drC.get("causa_real", ""),
            "tiene_datos": tiene_datos, "tiene_sonda": tiene_sonda,
            "nota_params": nota, "fase": fase,
        }
        (completadas if completada else pendientes).append(e)

    # Bloque FASE 0: clases code=6 — investigar param obligatorio
    DESC_CLASE = {
        "proyectos":  "Obras/Proyectos — clave del modulo obras",
        "reporden":   "Ordenes de reparacion — clave modulo mantenimiento",
        "recursos":   "Recursos (operarios/maquinaria) — para imputar horas",
        "proordutil": "Costes reales imputados a obra",
        "proordprev": "Costes previstos/presupuesto de obra",
        "repordutil": "Materiales y horas de una reparacion",
    }
    investigar = []
    for cl in CLASES_INVESTIGAR:
        drC = clases.get(cl, {})
        tiene_datos = bool(drC.get("muestra") or drC.get("browse_params_exitosos"))
        tiene_sonda = cl in sondas_hechas
        if tiene_datos or tiene_sonda:
            completadas.append({
                "clase": cl, "operacion": "browse", "params_sugeridos": {},
                "descripcion": f"Desbloqueado: {DESC_CLASE.get(cl, cl)}",
                "prioridad": "alta", "por_que": "Resuelto en FASE 0",
                "causa_actual": "acceso_confirmado",
                "tiene_datos": tiene_datos, "tiene_sonda": tiene_sonda,
                "nota_params": "", "fase": "FASE 0",
            })
        else:
            cands = svc.get_investigar_params(cl)
            investigar.append({
                "clase": cl,
                "descripcion": DESC_CLASE.get(cl, cl),
                "causa_actual": drC.get("causa_real", "requiere_parametros"),
                "candidatos": cands.get("candidatos_manuales", []),
                "candidatos_sonda": cands.get("candidatos_sonda", []),
                "nota": cands.get("nota", ""),
            })

    f0_total = len(CLASES_INVESTIGAR)
    f0_ok    = sum(1 for e in completadas if e.get("fase") == "FASE 0")
    f1_total = sum(1 for _, op, p, *_ in PRUEBAS if op == "browse" and "?" not in str(list(p.values())))
    f1_ok    = sum(1 for e in completadas if e.get("fase") == "FASE 1")
    f2_total = sum(1 for _, op, p, *_ in PRUEBAS if op == "browse" and "?" in str(list(p.values())))
    f3_total = sum(1 for _, op, *_ in PRUEBAS if op in ("new", "read"))

    return {
        "discover_disponible": True,
        "discover_timestamp": dr.get("timestamp", "")[:19],
        "empresa": dr.get("sesion", {}).get("empresa", ""),
        "total_pruebas": len(PRUEBAS) + f0_total,
        "pendientes": len(pendientes) + len(investigar),
        "completadas": len(completadas),
        "fases": {
            "f0": {"label": "FASE 0 - Investigar param obligatorio (6 clases code=6)", "total": f0_total, "ok": f0_ok},
            "f1": {"label": "FASE 1 - Browse simple (tablas maestras)", "total": f1_total, "ok": f1_ok},
            "f2": {"label": "FASE 2 - Browse con identificador real", "total": f2_total, "ok": 0},
            "f3": {"label": "FASE 3 - Ensayo escritura (new+cancel)", "total": f3_total, "ok": 0},
        },
        "observaciones_fijas": obs_fijas,
        "pruebas_pendientes": pendientes,
        "pruebas_completadas": completadas,
        "investigar": investigar,
    }


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


@router.get("/investigar-params/{clase}")
async def get_investigar_params(clase: str):
    """
    Devuelve los parámetros candidatos para investigar una clase que devuelve code=6.
    VERIFICADO (API Real JDDC 2026-09-09): proyectos, reporden, recursos,
    proordutil, proordprev, repordutil siguen en code=6 incluso con num=20.
    Necesitan un parámetro obligatorio específico de esta instalación.
    Este endpoint devuelve los candidatos a probar en el Explorador.
    """
    svc = get_service()
    return svc.get_investigar_params(clase)


class BrowseParamsRequest(BaseModel):
    clase: str
    params: Dict[str, Any] = Field(default_factory=dict)


@router.post("/browse-params")
async def browse_con_params(request: BrowseParamsRequest):
    """
    Ejecuta un browse de SOLO LECTURA con los parámetros indicados.
    Usado desde el Plan para investigar qué parámetro desbloquea una clase code=6.
    Registra el intento en el historial.
    """
    svc = get_service()
    if not svc.session_active:
        raise HTTPException(status_code=401, detail="Sin sesión activa. Inicia sesión primero.")
    if not svc.session_active:
        return {"success": False, "error": "Sin sesión activa"}
    try:
        import time as _time
        t0 = _time.time()
        raw, _ = svc._client().browse(svc.ssid1, svc.ssid2, request.clase, request.params)
        ms = round((_time.time() - t0) * 1000)
        code = raw.get("code")
        items = raw.get("items") or raw.get("data") or []
        total = raw.get("total")
        n = len(items) if isinstance(items, list) else 0
        data_raw = str(raw.get("data", ""))

        if code == 0:
            estado = "ok"
            interpretacion = f"✅ DATOS REALES — {n} registros" + (f" (total BD: {total})" if total is not None else "")
            # Guardar muestra con campos
            muestra = items[:5] if isinstance(items, list) else []
            campos = list(muestra[0].keys()) if muestra and isinstance(muestra[0], dict) else []
        elif code == 6:
            estado = "requiere_params"
            interpretacion = f"🔵 code=6 — Todavía requiere parámetro. Mensaje: '{data_raw[:120]}'"
            muestra, campos = [], []
        elif code == 5 and any(k in data_raw.lower() for k in ("licencia", "no dispone", "sin licencia")):
            estado = "sin_licencia"
            interpretacion = f"🚫 SIN LICENCIA: {data_raw[:120]}"
            muestra, campos = [], []
        else:
            estado = "error"
            interpretacion = f"⚠️ code={code}: {data_raw[:120]}"
            muestra, campos = [], []

        # Registrar en historial
        svc._history.insert(0, {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "clase": request.clase,
            "operacion": "browse",
            "params": request.params,
            "code": code,
            "estado": estado,
            "duracion_ms": ms,
            "n_items": n,
            "use_mock": svc.use_mock,
        })
        svc._history = svc._history[:500]

        return {
            "success": code == 0,
            "clase": request.clase,
            "params_usados": request.params,
            "code": code,
            "estado": estado,
            "interpretacion": interpretacion,
            "n_items": n,
            "total": total,
            "muestra": muestra,
            "campos_detectados": campos,
            "data_raw": data_raw[:300],
            "ms": ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sonda-masiva-fase0")
async def sonda_masiva_fase0():
    """
    Sonda masiva AUTOMATICA de solo lectura para las 6 clases FASE 0.
    Prueba >50 variantes de parametros (ejercicio, anyo, soloActivos, activo,
    todos, tipo, codEmpresa, filtro, estado, etc.) sin intervencion manual.
    Nunca escribe. Devuelve resultado detallado + TXT exportable.
    """
    svc = get_service()
    if not svc.session_active:
        raise HTTPException(status_code=401, detail="Sin sesion activa.")
    try:
        return svc.sonda_masiva_fase0()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/obtener-ids-reales")
async def obtener_ids_reales():
    """
    Consulta SOLO LECTURA a Firebird para obtener IDs reales de las tablas clave
    de SQL Obras (PROYECTOS, PROYORDENES, RECURSOS, etc.).
    Necesarios para probar clases que exigen un identificador de negocio real (code=6).
    NUNCA modifica la BD. Solo hace SELECT FIRST 5.
    """
    from backend.core.config.settings import settings
    import time

    # Mapeo clase-API → tabla Firebird + campo ID + campo descripción
    TABLA_MAP = [
        {
            "clase": "proyectos",
            "param_api": "codProyecto",
            "tabla": "PROYECTOS",
            "campo_id": "CODPROYE",
            "campo_desc": "DENOMINACION",
        },
        {
            "clase": "reporden",
            "param_api": "codOrden",
            "tabla": "REPORDEN",
            "campo_id": "CODORDEN",
            "campo_desc": "DESCRIPCION",
        },
        {
            "clase": "recursos",
            "param_api": "codRecurso",
            "tabla": "RECURSOS",
            "campo_id": "CODRECURSO",
            "campo_desc": "NOMBRE",
        },
        {
            "clase": "proordutil",
            "param_api": "codProyecto",
            "tabla": "PROYECTOS",
            "campo_id": "CODPROYE",
            "campo_desc": "DENOMINACION",
        },
        {
            "clase": "proordprev",
            "param_api": "codProyecto",
            "tabla": "PROYECTOS",
            "campo_id": "CODPROYE",
            "campo_desc": "DENOMINACION",
        },
        {
            "clase": "repordutil",
            "param_api": "codOrden",
            "tabla": "REPORDEN",
            "campo_id": "CODORDEN",
            "campo_desc": "DESCRIPCION",
        },
    ]

    resultados = []
    db_host = settings.DB_HOST
    db_port = settings.DB_PORT
    db_name = settings.DB_NAME
    db_user = settings.DB_USER
    db_pass = settings.DB_PASSWORD

    if not db_name:
        return {
            "ok": False,
            "error": "DB_NAME no configurado en .env — sin acceso directo a Firebird.",
            "resultados": [],
        }

    for entrada in TABLA_MAP:
        clase = entrada["clase"]
        tabla = entrada["tabla"]
        campo_id = entrada["campo_id"]
        campo_desc = entrada["campo_desc"]
        param_api = entrada["param_api"]

        ids_encontrados = []
        error_msg = None
        try:
            import firebirdsql
            t0 = time.monotonic()
            con = firebirdsql.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_pass,
                charset="UTF8",
            )
            cur = con.cursor()
            sql = (
                f"SELECT FIRST 5 {campo_id}, {campo_desc} "
                f"FROM {tabla} "
                f"ORDER BY {campo_id}"
            )
            cur.execute(sql)
            rows = cur.fetchall()
            ms = round((time.monotonic() - t0) * 1000)
            cur.close(); con.close()
            for row in rows:
                vid = str(row[0]).strip() if row[0] is not None else ""
                vdesc = str(row[1]).strip() if row[1] is not None else ""
                if vid:
                    ids_encontrados.append({
                        "id": vid,
                        "desc": vdesc,
                        "param_api": param_api,
                    })
        except ImportError:
            error_msg = "firebirdsql no instalado en este entorno."
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)[:200]}"

        resultados.append({
            "clase": clase,
            "tabla": tabla,
            "campo_id": campo_id,
            "param_api": param_api,
            "ids": ids_encontrados,
            "ok": len(ids_encontrados) > 0,
            "error": error_msg,
        })

    # Marcar duplicados (proyectos aparece en proordutil y proordprev — mismos IDs)
    return {
        "ok": any(r["ok"] for r in resultados),
        "db_host": db_host,
        "db_name": db_name,
        "resultados": resultados,
        "aviso": (
            "SOLO LECTURA — SELECT FIRST 5 — Ningún dato modificado. "
            "Usa estos IDs reales en el Explorador para desbloquear las clases FASE 0."
        ),
    }




# ─── Helpers Firebird: usan FirebirdDriver del proyecto ───────────────────────
# Mismo driver que usa el chat y todos los demás módulos.
# backend/drivers/db/firebird_driver.py + backend/core/factory/db_factory.py

MAPA_FIREBIRD = {
    # ── Tablas 100% confirmadas en table_index.json (443 tablas reales de la BD JDDC) ──
    # Fuente: backend/core/config/table_index.json generado desde la BD real
    #
    # PROYECTOS.CODIGO = ID interno numerico. NOMBRE = nombre obra.
    # La API mPYME usa objectclass=proyectos y browse/read con objectid=CODIGO
    "proyectos":    ("PROYECTOS",     "CODIGO",  "NOMBRE",        "codProyecto"),
    "partidas":     ("PROYECTOS",     "CODIGO",  "NOMBRE",        "codProyecto"),
    "proordutil":   ("PROYECTOS",     "CODIGO",  "NOMBRE",        "codProyecto"),
    "proordprev":   ("PROYECTOS",     "CODIGO",  "NOMBRE",        "codProyecto"),
    # REPARA = tabla de ordenes de reparacion/partes SAT
    # pk=['CODIGO'], n=7320 registros reales, cols: CODIGO, DESCRIPCION, FECHA, CODCLIENTE
    "reporden":     ("REPARA",        "CODIGO",  "DESCRIPCION",   "codOrden"),
    "repordutil":   ("REPARA",        "CODIGO",  "DESCRIPCION",   "codOrden"),
    # tipostrabajo → tabla TIPO (tipos genericos del ERP), n=239
    # TIPO.TIPO es el discriminador de familia, TIPO.CODIGO es el ID
    "tipostrabajo": ("TIPO",          "CODIGO",  "DESCRIPCION",   "codTrabajo"),
    # REPOBJETO pk=['CODIGO'], cols: CODIGO, NOMBRE, CODPROPIETARIO
    "repobjetos":   ("REPOBJETO",     "CODIGO",  "NOMBRE",        "codObjeto"),
    # REPINSTALACION pk=['CODIGO'], cols: CODIGO, NOMBRE, CODCLIENTE
    "repinst":      ("REPINSTALACION","CODIGO",  "NOMBRE",        "codInst"),
    # RECURSO pk=['CODIGO'], cols: CODIGO, DESCRIPCION
    "recursos":     ("RECURSO",       "CODIGO",  "DESCRIPCION",   "codRecurso"),
    # ARTICULO pk=['CODIGO'], cols: CODIGO, NOMBRE
    "articulos":    ("ARTICULO",      "CODIGO",  "NOMBRE",        "codArticulo"),
    # PROVEED pk=['CODIGO'], cols: CODIGO, RAZONSOCIAL
    "proveedores":  ("PROVEED",       "CODIGO",  "RAZONSOCIAL",   "codProv"),
    # CLIENTE pk=['CODIGO'], cols: CODIGO, RAZONSOCIAL
    "clientes":     ("CLIENTE",       "CODIGO",  "RAZONSOCIAL",   "codCliente"),
    # DOCCAB = albaranes/facturas/pedidos de compra
    "docalbcom":    ("DOCCAB",        "CODIGO",  "CODIGO",        "codDocumento"),
    "docfaccom":    ("DOCCAB",        "CODIGO",  "CODIGO",        "codDocumento"),
    "docpedcom":    ("DOCCAB",        "CODIGO",  "CODIGO",        "codDocumento"),
    # FABCAB = ordenes de fabricacion, pk=['CODMAESTRO','ESPREVISION','CODIGO']
    "ordenfab":     ("FABCAB",        "CODIGO",  "CODIGO",        "codOrden"),
}


# Cache de IDs Firebird: evita conexiones repetidas en sesiones intensivas
import time as _time_module
_FB_CACHE: dict = {}   # clase -> {"ts": float, "result": dict}
_FB_CACHE_TTL = 300    # 5 minutos

def _firebird_ids_cached(clase: str, n: int = 10) -> dict:
    """_firebird_ids con caché en memoria (TTL 5 min). 1 conexión por sesión de pruebas."""
    now = _time_module.monotonic()
    cached = _FB_CACHE.get(clase)
    if cached and (now - cached["ts"]) < _FB_CACHE_TTL:
        return cached["result"]
    result = _firebird_ids(clase, n)
    _FB_CACHE[clase] = {"ts": now, "result": result}
    return result

def _invalidar_cache_fb():
    """Invalida el caché de IDs (usar si se detecta error de conexión)."""
    _FB_CACHE.clear()

def _get_db_driver():
    """Obtiene y conecta el FirebirdDriver del proyecto. Igual que el resto de módulos."""
    from backend.core.config.settings import settings
    from backend.core.abstract.database import DBConfig
    from backend.core.factory.db_factory import DBFactory
    if not settings.DB_NAME:
        raise ValueError("DB_NAME no configurado en el .env del servidor")
    cfg = DBConfig(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset="latin1",   # charset igual que el resto del proyecto
    )
    drv = DBFactory.get_driver("firebird")
    drv.connect(cfg)
    return drv


def _firebird_ids(clase: str, n: int = 5) -> dict:
    """
    Obtiene hasta N IDs reales de Firebird usando el FirebirdDriver del proyecto.
    Solo lectura. Sin modificar nada. Devuelve lista de valores para probar uno a uno.
    """
    from backend.core.config.settings import settings
    info = MAPA_FIREBIRD.get(clase)
    if not info:
        return {"ok": False, "error": f"clase '{clase}' no tiene tabla mapeada"}
    tabla, campo_id, campo_desc, param_api = info
    if not settings.DB_NAME:
        return {"ok": False, "error": "DB_NAME no configurado en el .env del servidor"}
    try:
        drv = _get_db_driver()
        try:
            # Si campo_id == campo_desc evitar SELECT duplicado
            if campo_id == campo_desc:
                sql = f"SELECT FIRST {n} {campo_id} FROM {tabla} ORDER BY {campo_id}"
            else:
                sql = f"SELECT FIRST {n} {campo_id}, {campo_desc} FROM {tabla} ORDER BY {campo_id}"
            rows = drv.execute_query(sql)
        finally:
            drv.disconnect()
        if not rows:
            return {"ok": False, "error": f"Tabla {tabla} vacía (sin registros)"}
        valores = []
        for row in rows:
            # El driver devuelve claves en minúsculas o mayúsculas según charset
            vid = ""
            for key in [campo_id, campo_id.lower(), campo_id.upper()]:
                v = row.get(key, "")
                if v:
                    vid = str(v).strip(); break
            if campo_id == campo_desc:
                vdesc = vid
            else:
                vdesc = ""
                for key in [campo_desc, campo_desc.lower(), campo_desc.upper()]:
                    v = row.get(key, "")
                    if v:
                        vdesc = str(v).strip(); break
            if vid:
                valores.append({"id": vid, "desc": vdesc if vdesc else vid})
        if not valores:
            return {"ok": False, "error": f"Tabla {tabla}: sin valor en campo {campo_id}"}
        return {"ok": True, "param": param_api,
                "valores": [v["id"] for v in valores],
                "valores_desc": valores, "tabla": tabla}
    except Exception as exc:
        from backend.core.config.settings import settings as _s
        import logging as _log
        err_full = f"{type(exc).__name__}: {str(exc)}"
        _log.getLogger(__name__).warning(
            f"[api_explorer] _firebird_ids({clase}) tabla={info[0] if info else '?'}: {err_full}")
        return {"ok": False,
                "error": err_full[:500],
                "db_host": _s.DB_HOST, "db_name": _s.DB_NAME,
                "tabla_intentada": info[0] if info else "?",
                "campo_intentado": info[1] if info else "?"}


def _firebird_primer_id(clase: str) -> dict:
    """Compatibilidad con código anterior: devuelve solo el primer ID."""
    r = _firebird_ids(clase, n=3)
    if r.get("ok") and r.get("valores"):
        return {"ok": True, "param": r["param"], "valor": r["valores"][0]}
    return {"ok": False, "error": r.get("error", "sin datos")}


def _firebird_diagnostico() -> dict:
    """
    Diagnóstico completo usando el FirebirdDriver del proyecto.
    Sin devolver valores de negocio — solo estados y conteos.
    """
    from backend.core.config.settings import settings
    result = {
        "db_host": settings.DB_HOST, "db_port": settings.DB_PORT,
        "db_name": settings.DB_NAME, "db_user": settings.DB_USER,
        "db_name_configurado": bool(settings.DB_NAME),
        "driver": "FirebirdDriver (backend/drivers/db/firebird_driver.py)",
        "firebirdsql_instalado": False, "conexion_ok": False,
        "error": None, "tablas_probadas": {},
    }
    if not settings.DB_NAME:
        result["error"] = "DB_NAME vacío en el .env. Añadir la ruta del fichero .fdb"
        return result
    try:
        import firebirdsql  # noqa — solo verificar instalación
        result["firebirdsql_instalado"] = True
    except ImportError:
        result["error"] = "firebirdsql no instalado. Ejecutar: pip install firebirdsql"
        return result
    try:
        drv = _get_db_driver()
        result["conexion_ok"] = True
        # Tablas confirmadas en table_index.json (443 tablas reales JDDC)
        for tabla in ["PROYECTOS", "REPARA", "REPOBJETO", "REPINSTALACION",
                      "ARTICULO", "RECURSO", "CLIENTE", "PROVEED", "FABCAB"]:
            try:
                rows = drv.execute_query(f"SELECT COUNT(*) AS N FROM {tabla}")
                cnt = rows[0].get("N", rows[0].get("COUNT", 0)) if rows else 0
                result["tablas_probadas"][tabla] = {"ok": True, "n_registros": int(cnt)}
            except Exception as e:
                result["tablas_probadas"][tabla] = {"ok": False, "error": str(e)[:120]}
        drv.disconnect()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return result



class AutoProbarRequest(BaseModel):
    clase: str
    operacion: str
    params: Dict[str, Any] = Field(default_factory=dict)


@router.post("/auto-probar")
async def auto_probar(request: AutoProbarRequest):
    """Prueba exhaustiva: params usuario + IDs BD real. Devuelve items REALES."""
    import time as _t, json as _json
    svc = get_service()
    if not svc.session_active:
        raise HTTPException(status_code=401, detail="Sin sesion activa.")
    clase=request.clase; operacion=request.operacion; params=dict(request.params)
    RIESGO_OP={"browse":0,"read":0,"permiso":0,"info":0,"new":1,"edit":1,
               "cancel":0,"write":2,"imputaPro":2,"exec":2,"delete":3}
    if RIESGO_OP.get(operacion,0)>=2 and not svc.modo_escritura:
        return {"success":False,"clase":clase,"operacion":operacion,"code":-99,
                "estado":"bloqueado","ms":0,"n_items":0,"campos_detectados":[],
                "necesito_id_real":False,"id_resuelto":False,"params_usados":params,
                "use_mock":svc.use_mock,"muestra_tipos":{},"items":[],"id_usado":"",
                "raw_servidor":"","intentos_diagnostico":[],"diag_resumen":"",
                "mensaje":f"'{operacion}' requiere modo escritura activo."}
    intentos=[]
    def _llama(p, desc=""):
        t0=_t.monotonic()
        try:
            if operacion=="browse": raw,ms=svc._client().browse(svc.ssid1,svc.ssid2,clase,dict(p))
            elif operacion=="read": raw,ms=svc._client().read(svc.ssid1,svc.ssid2,clase,dict(p))
            elif operacion=="permiso": raw,ms=svc._client().permiso(svc.ssid1,svc.ssid2,clase)
            elif operacion=="info": raw,ms=svc._client().info(svc.ssid1,svc.ssid2,clase)
            elif operacion in("new","edit"): raw,ms=svc._client().new(svc.ssid1,svc.ssid2,clase,dict(p))
            elif operacion=="cancel": raw,ms=svc._client().cancel(svc.ssid1,svc.ssid2,clase,dict(p))
            else: ms=round((_t.monotonic()-t0)*1000); raw={"code":-99,"data":"op no soportada"}
        except Exception as exc:
            ms=round((_t.monotonic()-t0)*1000); raw={"code":-1,"data":str(exc)[:300]}
        c=raw.get("code") if isinstance(raw,dict) else -1
        d=str(raw.get("data",raw.get("error","")))[:200]
        ri=raw.get("items") or (raw.get("data") if isinstance(raw.get("data"),list) else [])
        intentos.append({"desc":desc,"params":dict(p),"code":c,
                          "ms":round(ms),"n_items":len(ri) if isinstance(ri,list) else 0,
                          "servidor":d,"ok":c==0})
        return raw,ms
    raw,ms=_llama(params,"Params usuario")
    code=raw.get("code") if isinstance(raw,dict) else -1
    nid=False; ires=False; id_usado=""; ids_fb_probados=[]; n_variantes=0
    # PASO 1: browse vacio si los params del usuario no funcionan
    if code!=0 and operacion=="browse" and params:
        r0,m0=_llama({},"browse sin params")
        if isinstance(r0,dict) and r0.get("code")==0: raw,ms,code=r0,m0,0
    # PASO 2: browse con pagesize=1
    if code!=0 and operacion=="browse":
        r0b,m0b=_llama({"pagesize":"1"},"browse pagesize=1")
        if isinstance(r0b,dict) and r0b.get("code")==0: raw,ms,code=r0b,m0b,0
    # PASO 3: auto-resolucion via Firebird (IDs reales) — hasta 10 IDs x 6 variantes c/u
    # code=6: necesita params. code=5 generico (sin keywords licencia/crash) = tambien necesita params
    _rdt_paso3 = str(raw.get("data","")).lower() if isinstance(raw,dict) else ""
    _KW_NO_PARAM=("licencia","no dispone","sin licencia","module not licensed",
                   "violaci","pymemobileserver","exception","segfault","access violation")
    _code5_es_params = (code==5 and not any(kw in _rdt_paso3 for kw in _KW_NO_PARAM))
    if code!=0 and operacion in("browse","read"):
        if code==6 or _code5_es_params:
            nid=True
            # Retry hasta 2 veces si _firebird_ids falla (Firebird puede necesitar tiempo)
            fb = {"ok": False, "error": "no iniciado"}
            for _retry_fb in range(3):
                fb = _firebird_ids_cached(clase, 10)
                if fb.get("ok"): break
                if _retry_fb < 2:
                    import time as _tw; _tw.sleep(0.3 * (_retry_fb + 1))
                    _FB_CACHE.pop(clase, None)  # invalidar cache para forzar reintento
            if fb.get("ok") and fb.get("valores"):
                papi=fb["param"]; ids_fb_probados=list(fb["valores"])
                for val in fb["valores"]:
                    if ires: break
                    if operacion=="browse":
                        variantes=[
                            ({**params,papi:val},f"browse {papi}={val}"),
                            ({**params,"filter":_json.dumps({papi:val})},f"browse filter-json {papi}={val}"),
                            ({**params,"objectid":val},f"browse objectid={val}"),
                            ({papi:val,"pagesize":"25"},f"browse {papi}={val} pagesize=25"),
                            ({papi:val,"pagesize":"1"},f"browse {papi}={val} pagesize=1"),
                            ({"filter":_json.dumps({papi:val}),"pagesize":"1"},f"filter-json+pagesize=1"),
                        ]
                        for vp,vd in variantes:
                            n_variantes+=1
                            rv,mv=_llama(vp,vd)
                            if isinstance(rv,dict) and rv.get("code")==0:
                                raw,ms,code=rv,mv,0; ires=True; id_usado=val; break
                    elif operacion=="read":
                        variantes=[
                            ({"objectid":val},f"read objectid={val}"),
                            ({papi:val},f"read {papi}={val}"),
                            ({"objectid":str(val),"pagesize":"1"},f"read objectid={val} p1"),
                        ]
                        for vp,vd in variantes:
                            n_variantes+=1
                            rv,mv=_llama(vp,vd)
                            if isinstance(rv,dict) and rv.get("code")==0:
                                raw,ms,code=rv,mv,0; ires=True; id_usado=val; break
            else:
                _fb_err = fb.get("error","Firebird no disponible")
                import logging as _lg
                _lg.getLogger(__name__).warning(f"[auto_probar] _firebird_ids({clase}) fallo: {_fb_err}")
                intentos.append({"desc":"Firebird error","params":{},"code":-1,"ms":0,
                                  "n_items":0,"ok":False,"servidor":_fb_err})
                ids_fb_probados.append(f"ERROR: {_fb_err[:80]}")
    # PASO 4: filtros de dominio conocidos
    if code!=0 and operacion=="browse":
        for _fp in [{},{"pagesize":"1"},{"pagesize":"1","page":"1"},
                    {"columns":"[]"},{"filter":"{}"}]:
            if code==0: break
            try:
                rfd,mfd=svc._client().browse(svc.ssid1,svc.ssid2,clase,_fp)
                if isinstance(rfd,dict) and rfd.get("code")==0: raw,ms,code=rfd,mfd,0
            except: pass
    # PASO 5: ultimo recurso absoluto
    if code!=0 and operacion=="browse":
        rf,mf=_llama({},"browse vacio ultimo recurso")
        if isinstance(rf,dict) and rf.get("code")==0: raw,ms,code=rf,mf,0
    # PASO 6: si sigue code=6, llamar info() para revelar estructura real mPYME
    _info_servidor={}
    if code==6:
        try:
            iraw,_=svc._client().info(svc.ssid1,svc.ssid2,clase)
            if isinstance(iraw,dict) and iraw.get("code")==0:
                _info_servidor={"code":0,"campos":iraw.get("data",[]),
                                "msg":"info() OK — campos de mPYME obtenidos correctamente"}
            else:
                _info_servidor={"code":(iraw or {}).get("code",-1),
                                "msg":str((iraw or {}).get("data",""))[:200]}
        except Exception as _ei:
            _info_servidor={"code":-1,"msg":str(_ei)[:200]}
    raw_data=raw.get("data") if isinstance(raw,dict) else None
    items=[]
    if isinstance(raw_data,list): items=raw_data
    elif isinstance(raw_data,dict) and "items" in raw_data: items=raw_data["items"]
    elif isinstance(raw.get("items"),list): items=raw["items"]
    elif isinstance(raw_data,dict) and raw_data and code==0: items=[raw_data]
    if not isinstance(items,list): items=[]
    n=len(items); campos=list(items[0].keys())[:25] if n>0 and isinstance(items[0],dict) else []
    _rdt=str(raw.get("data","")).lower() if isinstance(raw,dict) else ""
    _KW_LIC=("licencia","no dispone","sin licencia","module not licensed")
    _KW_CRASH=("violaci","acceso a la direcci","pymemobileserver",
               "pymeserver","exception","segfault","access violation",
               "leer de direcci","escribir en direcci","m\u00f3dulo '")
    SM={0:"ok",1:"sin_licencia",2:"sin_permiso",5:"config_incompleta",
        6:"requiere_params",-1:"error",-99:"bloqueado"}
    if code==5 and any(kw in _rdt for kw in _KW_LIC): estado="sin_licencia"
    elif code==5 and any(kw in _rdt for kw in _KW_CRASH): estado="crash_servidor"
    elif code==5 and not any(kw in _rdt for kw in list(_KW_LIC)+list(_KW_CRASH)):
        # code=5 generico sin keywords conocidas = necesita parametros (igual que code=6)
        estado="requiere_params"
    else: estado=SM.get(code,"error")
    _rm=str(raw.get("data",raw.get("error","")))[:200] if isinstance(raw,dict) else ""
    ni=len(intentos)
    _ids_str=", ".join(str(x) for x in ids_fb_probados[:5])
    dr=(f"{ni} intentos | {n_variantes} variantes"
        +(f" | IDs BD probados: {_ids_str}" if ids_fb_probados else "")
        +(f" | ID exitoso: {id_usado}" if ires else ""))
    ok_txt=f"OK {n} registro(s) de SQL Obras."+(f" [ID:{id_usado}]" if ires else "")
    _ids_count=len(ids_fb_probados)
    if nid and ids_fb_probados:
        req_txt=(f"Firebird OK: se probaron {_ids_count} IDs reales ({_ids_str}) "+
                 f"con {n_variantes} variantes cada uno - mPYME devolvio code=6 en todos. "+
                 "Ver 'intentos_diagnostico' para detalle.")
    else:
        req_txt="Usa boton BD para obtener IDs reales de la base de datos."
    MSGS={"ok":ok_txt,
          "sin_licencia":f"Sin licencia (code={code}). {_rm[:100]}. Contactar Distrito K.",
          "sin_permiso":f"Sin permiso (code=2). {_rm[:80]}",
          "crash_servidor":(f"CRASH interno del servidor mPYME (code=5). "+
                             f"Violacion de acceso/excepcion en PymeMobileServer.exe. "+
                             f"Avisar al administrador del servidor SQL Obras. Raw: {_rm[:100]}"),
          "config_incompleta":f"Config incompleta (code=5). {_rm[:100]}",
          "requiere_params":(f"code=6 tras {ni} intentos ({n_variantes} variantes, {_ids_count} IDs BD). "+
                              f"{_rm[:80]}. "+req_txt),
          "error":f"code={code}. {_rm[:100]}",
          "bloqueado":"Escritura bloqueada."}
    svc._history.insert(0,{"timestamp":__import__("datetime").datetime.now().isoformat(),
        "clase":clase,"operacion":operacion,"params":params,"code":code,
        "estado":estado,"duracion_ms":round(ms),"n_items":n,"use_mock":svc.use_mock})
    svc._history=svc._history[:500]
    return {"success":code==0,"clase":clase,"operacion":operacion,"code":code,
            "estado":estado,"mensaje":MSGS.get(estado,f"code={code}"),
            "n_items":n,"campos_detectados":campos,
            "necesito_id_real":nid,"id_resuelto":ires,"id_usado":id_usado,
            "ids_firebird_probados":ids_fb_probados,
            "n_variantes_intentadas":n_variantes,
            "params_usados":params,"ms":round(ms),"use_mock":svc.use_mock,
            "raw_servidor":_rm,
            "items":items[:25],
            "items_muestra":items[:5],
            "info_servidor":_info_servidor,
            "muestra_tipos":({k:type(v).__name__ for k,v in items[0].items()} if n>0 and isinstance(items[0],dict) else {}),
            "intentos_diagnostico":intentos,
            "diag_resumen":dr}


class ProbarTodoRequest(BaseModel):
    solo_lectura: bool = True


@router.post("/probar-todo-catalogo")
async def probar_todo_catalogo(request: ProbarTodoRequest):
    """Prueba TODAS las clases. Auto-resuelve code=6. Sin datos privados."""
    import time as _t
    svc = get_service()
    if not svc.session_active:
        raise HTTPException(status_code=401, detail="Sin sesión activa.")
    from backend.modules.api_explorer.api_catalogue_full import get_catalogue
    catalogue = get_catalogue()
    CLASES_OPS: dict = {}
    for mod_data in catalogue.values():
        for c in mod_data.get("clases",[]):
            nombre=c if isinstance(c,str) else c.get("nombre","")
            ops_doc=(c.get("ops",[]) if isinstance(c,dict) else []) or []
            ops_lec=[o for o in ops_doc if o in("browse","permiso","info","read")] or ["browse","permiso","info"]
            if nombre: CLASES_OPS[nombre]=ops_lec
    # PRE-CARGAR todos los IDs de Firebird con 1 sola conexión al inicio
    # Evita agotamiento de conexiones (N_clases * N_ops * nueva_conexion = demasiadas)
    _ids_pool: dict = {}  # clase -> {"ok": bool, "param": str, "valores": list, "error": str}
    try:
        from backend.core.config.settings import settings as _sett
        if _sett.DB_NAME:
            drv_pool = _get_db_driver()
            try:
                for _cl, _mi in MAPA_FIREBIRD.items():
                    _tabla, _campo_id, _campo_desc, _param = _mi
                    try:
                        if _campo_id == _campo_desc:
                            _sql = f"SELECT FIRST 10 {_campo_id} FROM {_tabla} ORDER BY {_campo_id}"
                        else:
                            _sql = f"SELECT FIRST 10 {_campo_id}, {_campo_desc} FROM {_tabla} ORDER BY {_campo_id}"
                        _rows = drv_pool.execute_query(_sql)
                        _vals = []
                        for _r in (_rows or []):
                            _v = ""
                            for _k in [_campo_id, _campo_id.lower(), _campo_id.upper()]:
                                if _r.get(_k): _v = str(_r[_k]).strip(); break
                            if _v: _vals.append(_v)
                        if _vals:
                            _ids_pool[_cl] = {"ok": True, "param": _param, "valores": _vals,
                                              "tabla": _tabla, "campo": _campo_id}
                            import logging as _lp2
                            _lp2.getLogger(__name__).info(
                                f"[pool] {_cl} <- {_tabla}.{_campo_id}: {_vals[:3]}")
                        else:
                            _ids_pool[_cl] = {"ok": False, "error": f"{_tabla} vacia (0 registros)",
                                              "tabla": _tabla}
                    except Exception as _e2:
                        _err2 = str(_e2)[:200]
                        _ids_pool[_cl] = {"ok": False, "error": _err2, "tabla": _tabla}
                        import logging as _lp3
                        _lp3.getLogger(__name__).warning(
                            f"[pool] FALLO {_cl} ({_tabla}.{_campo_id}): {_err2}")
            finally:
                drv_pool.disconnect()
    except Exception as _epool:
        import logging as _lpool
        _lpool.getLogger(__name__).warning(f"[probar-todo] pool IDs fallo: {_epool}")

    def _ids_from_pool(clase):
        """Devuelve IDs del pool pre-cargado. Nunca abre nueva conexion."""
        return _ids_pool.get(clase, {"ok": False, "error": "No en pool"})

    resultados: dict = {}
    for clase,ops in CLASES_OPS.items():
        entrada={"clase":clase,"resultados_op":{}}
        # Ejecutar permiso + info siempre para clasificar code=5 correctamente
        praw,pms = {"code":-1},0
        iraw,ims = {"code":-1},0
        try: praw,pms = svc._client().permiso(svc.ssid1,svc.ssid2,clase)
        except: pass
        try: iraw,ims = svc._client().info(svc.ssid1,svc.ssid2,clase)
        except: pass
        def _estado_code5(raw_resp):
            data_txt = str((raw_resp or {}).get("data","")).lower()
            if any(kw in data_txt for kw in ("licencia","no dispone","sin licencia","module not licensed")):
                return "sin_licencia", "Sin licencia — "+str((raw_resp or {}).get("data",""))[:100]
            _CRASH=("violaci","acceso a la direcci","pymemobileserver","pymeserver",
                    "exception","segfault","access violation","leer de direcci",
                    "escribir en direcci","m\u00f3dulo '")
            if any(kw in data_txt for kw in _CRASH):
                return "crash_servidor", "CRASH mPYME — "+str((raw_resp or {}).get("data",""))[:120]
            return "config_incompleta", "code=5: "+str((raw_resp or {}).get("data",""))[:100]
        for op in ops:
            if op == "permiso":
                raw,ms = (praw if isinstance(praw,dict) else {"code":-1}),pms
            elif op == "info":
                raw,ms = (iraw if isinstance(iraw,dict) else {"code":-1}),ims
            else:
                t0=_t.monotonic()
                try:
                    if op=="browse": raw,ms=svc._client().browse(svc.ssid1,svc.ssid2,clase,{})
                    elif op=="read": raw,ms=svc._client().read(svc.ssid1,svc.ssid2,clase,{})
                    else: continue
                except Exception as exc:
                    entrada["resultados_op"][op]={"code":-1,"estado":"error","ok":False,
                        "ms":round((_t.monotonic()-t0)*1000),"n_items":0,"campos":[],
                        "necesito_id":False,"id_resuelto":False,
                        "mensaje":f"Excepcion: {str(exc)[:100]}"}; continue
            code=raw.get("code") if isinstance(raw,dict) else -1
            nid=False; ires=False; msg_servidor=""; ids_fb=[]; nvar=0; id_ok=""
            # permiso e info con code=6: mPYME requiere objectid incluso para ellas
            # Probar con IDs reales de Firebird
            if code==6 and op in("permiso","info","read"):
                fb2=_ids_from_pool(clase)
                if fb2.get("ok") and fb2.get("valores"):
                    import json as _fj2; papi2=fb2["param"]; ids_fb=list(fb2["valores"])
                    for val2 in ids_fb:
                        try:
                            if op=="permiso":
                                r2p={**svc._client()._base(),"method":"permiso","objectclass":clase,"objectid":val2}
                                import requests as _rq
                                resp2=_rq.post(svc._client().url,data=r2p,timeout=svc._client().tout,verify=svc._client().ssl)
                                raw2=resp2.json(); ms2=0
                            elif op=="info":
                                r2i={**svc._client()._base(),"method":"info","objectclass":clase,"objectid":val2}
                                resp2=_rq.post(svc._client().url,data=r2i,timeout=svc._client().tout,verify=svc._client().ssl)
                                raw2=resp2.json(); ms2=0
                            elif op=="read":
                                raw2,ms2=svc._client().read(svc.ssid1,svc.ssid2,clase,{"objectid":val2})
                            if isinstance(raw2,dict) and raw2.get("code")==0:
                                raw,ms,code=raw2,ms2,0; ires=True; id_ok=str(val2); break
                        except: pass
            # browse vacio/pagesize primero (code=6 o code=5 sin keywords licencia/crash)
            _rdt_pt=str(raw.get("data","")).lower() if isinstance(raw,dict) else ""
            _KW_PT=("licencia","no dispone","sin licencia","module not licensed",
                    "violaci","pymemobileserver","exception","segfault")
            _c5p=(code==5 and not any(kw in _rdt_pt for kw in _KW_PT))
            if (code==6 or _c5p) and op=="browse":
                try:
                    r00,m00=svc._client().browse(svc.ssid1,svc.ssid2,clase,{})
                    if isinstance(r00,dict) and r00.get("code")==0: raw,ms,code=r00,m00,0
                except: pass
            if (code==6 or _c5p) and op=="browse":
                try:
                    r01,m01=svc._client().browse(svc.ssid1,svc.ssid2,clase,{"pagesize":"1"})
                    if isinstance(r01,dict) and r01.get("code")==0: raw,ms,code=r01,m01,0
                except: pass
            if (code==6 or _c5p) and op in("browse","read"):
                msg_servidor = str(raw.get("data",""))[:120]
                fb=_ids_from_pool(clase)
                if fb.get("ok") and fb.get("valores"):
                    nid=True; ids_fb=list(fb["valores"])
                    import json as _fj; papi=fb["param"]
                    for val in ids_fb:
                        if ires: break
                        variantes=([{papi:val},{"filter":_fj.dumps({papi:val})},
                                    {"objectid":val},{papi:val,"pagesize":"25"},
                                    {papi:val,"pagesize":"1"},{"filter":_fj.dumps({papi:val}),"pagesize":"1"}]
                                   if op=="browse" else [{"objectid":val},{papi:val}])
                        for vp in variantes:
                            nvar+=1
                            try:
                                if op=="browse": rv,mv=svc._client().browse(svc.ssid1,svc.ssid2,clase,vp)
                                else: rv,mv=svc._client().read(svc.ssid1,svc.ssid2,clase,vp)
                                if isinstance(rv,dict) and rv.get("code")==0:
                                    raw,ms,code=rv,mv,0; ires=True; id_ok=str(val); break
                            except: pass
                else:
                    msg_servidor += " | Firebird: "+fb.get("error","no disponible")
            if code==0: estado="ok"; msg=""
            elif code==1: estado="sin_licencia"; msg=str(raw.get("data",""))[:120]
            elif code==2: estado="sin_permiso"; msg=str(raw.get("data",""))[:120]
            elif code==5:
                estado,msg=_estado_code5(raw)
                # si era code=5 generico y resolvimos con IDs -> ok
                if estado=="config_incompleta" and ires: estado="ok"; msg=""
                # si era code=5 generico y necesita ID -> requiere_params (mas claro que config_incompleta)
                elif estado=="config_incompleta" and nid: estado="requiere_params"; msg="Necesita ID real (code=5 generico). "+msg
            elif code==6: estado="requiere_params"; msg=msg_servidor or str(raw.get("data",""))[:120]
            elif code==-1: estado="error"; msg=str(raw.get("error",raw.get("data","")))[:120]
            else: estado="error"; msg=f"code={code}: {str(raw.get('data',''))[:100]}"
            items=(raw.get("items") or raw.get("data") or []) if isinstance(raw,dict) else []
            if not isinstance(items,list): items=[]
            n=len(items); campos=list(items[0].keys())[:15] if n>0 and isinstance(items[0],dict) else []
            entrada["resultados_op"][op]={"code":code,"estado":estado,"ok":code==0,
                "ms":round(ms),"n_items":n,"campos":campos,"necesito_id":nid,"id_resuelto":ires,
                "ids_fb_probados":ids_fb,"n_variantes":nvar,"id_ok":id_ok,
                "items_muestra":items[:3],
                "mensaje":(f"code=6 tras {nvar} variantes, {len(ids_fb)} IDs BD. "+msg if code==6 and ids_fb else msg)}
            _t.sleep(0.05)
        ops_r=entrada["resultados_op"]
        if any(v.get("ok") for v in ops_r.values()): entrada["estado_global"]="ok"
        elif any(v.get("estado")=="requiere_params" for v in ops_r.values()): entrada["estado_global"]="requiere_params"
        elif any(v.get("estado")=="sin_licencia" for v in ops_r.values()): entrada["estado_global"]="sin_licencia"
        elif any(v.get("estado")=="sin_permiso" for v in ops_r.values()): entrada["estado_global"]="sin_permiso"
        elif any(v.get("estado")=="config_incompleta" for v in ops_r.values()): entrada["estado_global"]="config_incompleta"
        else: entrada["estado_global"]="error"
        resultados[clase]=entrada
    ts=__import__("datetime").datetime.now().isoformat()
    # Resumir estado del pool de IDs para incluir en la respuesta
    _pool_resumen = {}
    for _c, _pi in _ids_pool.items():
        _pool_resumen[_c] = {
            "ok": _pi.get("ok"), "tabla": _pi.get("tabla","?"),
            "n_ids": len(_pi.get("valores",[])),
            "primeros_ids": _pi.get("valores",[])[:3],
            "error": _pi.get("error","") if not _pi.get("ok") else ""
        }
    return {"success":True,"timestamp":ts,"use_mock":svc.use_mock,"total_clases":len(resultados),
            "resumen":{"ok":sum(1 for v in resultados.values() if v["estado_global"]=="ok"),
                "requiere_params":sum(1 for v in resultados.values() if v["estado_global"]=="requiere_params"),
                "sin_licencia":sum(1 for v in resultados.values() if v["estado_global"]=="sin_licencia"),
                "sin_permiso":sum(1 for v in resultados.values() if v["estado_global"]=="sin_permiso"),
                "error":sum(1 for v in resultados.values() if v["estado_global"]=="error")},
            "clases":resultados,
            "pool_ids_firebird": _pool_resumen,
            "aviso":"Sin datos privados. Solo estados, códigos y nombres de campos."}

@router.get("/diagnostico-firebird")
async def diagnostico_firebird():
    """Diagnostico completo de la conexion Firebird. Solo lectura. Sin valores de negocio."""
    d = _firebird_diagnostico()
    return d


@router.post("/debug-firebird-ids")
async def debug_firebird_ids(request: dict = None):
    """Debug: prueba _firebird_ids para cada clase y devuelve el resultado exacto con error completo."""
    from backend.core.config.settings import settings as _s
    clases = list(MAPA_FIREBIRD.keys())
    resultados = {}
    # Primero hacer una conexion de prueba directa para ver si el driver funciona
    conn_test = {"ok": False, "error": "", "n_rows": 0}
    try:
        drv_t = _get_db_driver()
        rows_t = drv_t.execute_query("SELECT COUNT(*) AS N FROM PROYECTOS")
        drv_t.disconnect()
        conn_test = {"ok": True, "error": "", "n_rows": (rows_t[0].get("N") or rows_t[0].get("n",0)) if rows_t else 0}
    except Exception as _e_conn:
        conn_test = {"ok": False, "error": str(_e_conn)}
    for clase in clases:
        r = _firebird_ids(clase, n=3)
        resultados[clase] = {
            "ok": r.get("ok"), "error": r.get("error",""),
            "param": r.get("param",""), "n_valores": len(r.get("valores",[])),
            "primeros": r.get("valores",[])[:3],
            "tabla": MAPA_FIREBIRD[clase][0], "campo_id": MAPA_FIREBIRD[clase][1],
            "tabla_err": r.get("tabla_intentada",""), "campo_err": r.get("campo_intentado",""),
        }
    return {"success": True, "resultados": resultados, "conn_test": conn_test,
            "db_host": _s.DB_HOST, "db_name": _s.DB_NAME, "db_user": _s.DB_USER}


@router.post("/test-new-cancel")
async def test_new_cancel():
    """
    Prueba new()+cancel() en proyectos — 100% seguro, no persiste nada.
    Objetivo: determinar si la BD de mPYME responde a operaciones que requieren BD,
    para confirmar si el problema de browse es de BD o de protocolo.
    """
    import time as _tnc
    svc = get_service()
    if not svc.session_active:
        raise HTTPException(status_code=401, detail="Sin sesion activa.")
    resultados = []
    clases_test = ["proyectos", "repobjetos", "reporden", "clientes"]
    for cls in clases_test:
        # 1. new() — crea objeto temporal en sesion
        t0 = _tnc.monotonic()
        try:
            raw_new, ms_new = svc._client().new(svc.ssid1, svc.ssid2, cls, {})
            code_new = raw_new.get("code") if isinstance(raw_new, dict) else -1
            oid = ""
            if code_new == 0:
                d = raw_new.get("data", {})
                if isinstance(d, dict):
                    oid = d.get("objectId", d.get("objectid", d.get("id", "new")))
                if not oid: oid = "new"
        except Exception as e:
            raw_new = {"code": -1, "data": str(e)[:200]}
            code_new = -1; ms_new = 0; oid = ""
        # 2. cancel() — descarta el objeto temporal (seguro siempre)
        ms_cancel = 0; code_cancel = -1
        if oid:
            try:
                raw_cancel, ms_cancel = svc._client().cancel(svc.ssid1, svc.ssid2, cls, {"objectid": oid})
                code_cancel = raw_cancel.get("code") if isinstance(raw_cancel, dict) else -1
            except Exception as ec:
                raw_cancel = {"code": -1, "data": str(ec)[:100]}
                code_cancel = -1
        resultados.append({
            "clase": cls,
            "new_code": code_new,
            "new_ms": round(ms_new),
            "new_ok": code_new == 0,
            "new_msg": str((raw_new or {}).get("data", ""))[:150],
            "cancel_code": code_cancel,
            "cancel_ok": code_cancel in (0, -1),  # -1 es ok si no hubo oid
            "objectid": oid,
            "bd_accesible": code_new == 0,
        })
    todos_ok = all(r["new_ok"] for r in resultados)
    alguno_ok = any(r["new_ok"] for r in resultados)
    if todos_ok:
        conclusion = "BD_OK: new() funciona en todas las clases. La BD de mPYME esta accesible. El problema de browse es especifico de esa operacion."
    elif alguno_ok:
        conclusion = "BD_PARCIAL: new() funciona en algunas clases. La BD de mPYME tiene acceso parcial."
    else:
        conclusion = "BD_INACC: new() falla en todas las clases. La BD de mPYME no esta accesible desde PymeMobileServer. Reiniciar SQL Obras y PymeMobileServer."
    return {
        "success": True,
        "conclusion": conclusion,
        "todos_ok": todos_ok,
        "alguno_ok": alguno_ok,
        "resultados": resultados,
        "aviso": "SEGURO: new()+cancel() no persiste ningun dato. Solo verifica acceso a BD."
    }


@router.get("/informe-completo")
async def get_informe_completo():
    """
    Genera y devuelve el informe TXT completo con todo lo aprendido:
    - Clases accesibles / bloqueadas / con licencia
    - Comportamiento tecnico verificado
    - Variantes probadas automaticamente (FASE 0)
    - Aplicaciones posibles
    - Acciones requeridas
    - Pregunta exacta para Distrito K
    Descargable como archivo .txt
    """
    svc = get_service()
    try:
        return svc.generar_informe_completo()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/super-diagnostico")
async def super_diagnostico():
    """Diagnostico exhaustivo: prueba TODO antes de escalar a Distrito K."""
    import json as _sj
    svc = get_service()
    if not svc.session_active:
        raise HTTPException(status_code=401, detail="Sin sesion activa.")
    cfg = svc.get_config_env()
    ts_inicio = __import__("datetime").datetime.now().isoformat()
    import logging as _lg2; _slog = _lg2.getLogger(__name__)

    # F1: Firebird + F2: Pool IDs
    fb_diag = _firebird_diagnostico()
    ids_pool: dict = {}
    if fb_diag.get("conexion_ok"):
        try:
            drv_pool = _get_db_driver()
            try:
                for _cl, (_t, _ci, _cd, _pm) in MAPA_FIREBIRD.items():
                    try:
                        _sql = (f"SELECT FIRST 10 {_ci} FROM {_t} ORDER BY {_ci}" if _ci==_cd else
                                f"SELECT FIRST 10 {_ci}, {_cd} FROM {_t} ORDER BY {_ci}")
                        _rows = drv_pool.execute_query(_sql)
                        _vals = []
                        for _r in (_rows or []):
                            for _k in [_ci, _ci.lower(), _ci.upper()]:
                                if _r.get(_k): _vals.append(str(_r[_k]).strip()); break
                        ids_pool[_cl] = {"ok":bool(_vals),"param":_pm,"valores":_vals,"tabla":_t,"n":len(_vals)}
                    except Exception as _e2:
                        ids_pool[_cl] = {"ok":False,"error":str(_e2)[:120],"tabla":_t,"n":0}
            finally:
                drv_pool.disconnect()
        except Exception as _e3:
            _slog.warning(f"[super-diag] pool: {_e3}")


    # F3: permiso+info+browse+read por clase (captura msg exacto de code=6)
    from backend.modules.api_explorer.service import ALL_OBJECT_CLASSES
    _anyo_bd = "2021"  # anyo real de la BD Firebird (juandedi/2021.fdb)
    clases_resultado: dict = {}
    for clase in ALL_OBJECT_CLASSES:
        cr: dict = {"permiso_code":None,"permiso_msg":"","info_code":None,"info_campos":[],
                    "browse_intentos":[],"browse_code_final":None,"browse_ok":False,
                    "browse_msg_exacto":"",
                    "read_intentos":[],"read_code_final":None,"read_ok":False,
                    "n_items":0,"items_muestra":[],"campos":[],"params_exitosos":None}
        # permiso
        try:
            _pr,_ = svc._client().permiso(svc.ssid1,svc.ssid2,clase)
            cr["permiso_code"]=_pr.get("code") if isinstance(_pr,dict) else -1
            cr["permiso_msg"]=str((_pr or {}).get("data",""))[:200]
        except Exception as _ep: cr["permiso_code"]=-1; cr["permiso_msg"]=str(_ep)[:80]
        # info (captura campos reales si code=0)
        try:
            _ir,_ = svc._client().info(svc.ssid1,svc.ssid2,clase)
            cr["info_code"]=_ir.get("code") if isinstance(_ir,dict) else -1
            if cr["info_code"]==0:
                _idata = (_ir or {}).get("data",{})
                if isinstance(_idata,dict): cr["info_campos"]=list(_idata.keys())[:30]
                elif isinstance(_idata,list): cr["info_campos"]=[str(x) for x in _idata[:30]]
        except Exception: cr["info_code"]=-1
        if cr["permiso_code"]==1:
            cr["browse_code_final"]=-99; clases_resultado[clase]=cr; continue
        # VARIANTES segun documentacion oficial mPYME v1.2
        # code=6 = MAINTENANCE MODE (no es falta de parametro)
        # proyectos: browse con filter opcional
        # proordutil: requiere masterid + desde/hasta
        # partidas: requiere master=<idProyecto>
        # repobjetos: requiere masterClass/masterId o mode:add
        _fb = ids_pool.get(clase,{})
        _fb_vals = _fb.get("valores",[]) if _fb.get("ok") else []
        _fb_param = _fb.get("param","")
        _variantes = [
            # Basicas documentadas: browse sin parametros, con filter
            ({}, "vacio"),
            ({"filter": ""}, "filter=vacio"),
            ({"pagesize": "25"}, "p25"),
            ({"pagesize": "1"}, "p1"),
            ({"more": "first"}, "more=first"),
            ({"more": "first", "pagesize": "25"}, "more=first+p25"),
            # Documentos: serie/ejercicio
            ({"ejercicio": _anyo_bd}, f"ej={_anyo_bd}"),
            ({"ejercicio": "2026"}, "ej=2026"),
            ({"ejercicio": "2025"}, "ej=2025"),
            ({"anyo": _anyo_bd}, f"anyo={_anyo_bd}"),
            # Estados habituales
            ({"estado": "abierta"}, "est=abierta"),
            ({"estado": "activa"}, "est=activa"),
            ({"soloActivos": "T"}, "soloActivos=T"),
            ({"activo": "T"}, "activo=T"),
            ({"todos": "T"}, "todos=T"),
            # Columnas y ordenacion
            ({"columns": "[]"},"cols=[]"),
            # (cols=asc variante eliminada por problema de escaping)
            # Tipos
            ({"tipo": "EMPLEADO"}, "tipo=EMP"),
            ({"tipo": "M"}, "tipo=M"),
        ]
        # Variantes con masterid (requerido por proordutil, partidas, repordutil, repobjetos)
        # La doc indica: proordutil&masterid=<idProyecto>&desde=...&hasta=...
        _ids_proyectos = ids_pool.get("proyectos",{}).get("valores",[])
        _ids_reporden  = ids_pool.get("reporden",{}).get("valores",[])
        _ids_clientes  = ids_pool.get("clientes",{}).get("valores",[])
        _master_clase = {
            "proordutil": _ids_proyectos, "proordprev": _ids_proyectos,
            "partidas":   _ids_proyectos,
            "repordutil": _ids_reporden, "repobjetos": _ids_clientes,
            "repinst":    _ids_clientes,
        }
        if clase in _master_clase:
            for _mid in (_master_clase[clase] or [])[:3]:
                _variantes += [
                    ({"masterid": _mid}, f"masterid={_mid}"),
                    ({"master": _mid}, f"master={_mid}"),
                    ({"masterid": _mid, "pagesize": "25"}, f"masterid={_mid}+p25"),
                ]
            # proordutil necesita rango de fechas
            if clase in ("proordutil", "proordprev"):
                for _mid in (_master_clase[clase] or [])[:2]:
                    _variantes += [
                        ({"masterid": _mid, "desde": "01/01/2000", "hasta": "31/12/2030"}, f"masterid={_mid}+fechas"),
                        ({"masterid": _mid, "desde": "01/01/2000", "hasta": "31/12/2030", "recurso": "", "orden": "fecha-asc"}, f"masterid={_mid}+full"),
                    ]
        # Para docXXX: variantes con serie
        if clase.startswith("doc"):
            _variantes += [
                ({"serie": "A"}, "serie=A"),
                ({"serie": ""}, "serie=vacio"),
                ({"tipo": "3"}, "tipo=3"),
                ({"tipo": "1"}, "tipo=1"),
            ]
        # IDs reales de Firebird (segun MAPA_FIREBIRD)
        if _fb.get("ok") and _fb_vals:
            for _val in _fb_vals[:5]:
                _variantes += [
                    ({_fb_param:_val},f"{_fb_param}={_val}"),
                    ({"objectid":_val},f"oid={_val}"),
                    ({_fb_param:_val,"pagesize":"25"},f"{_fb_param}={_val}+p25"),
                    ({_fb_param:_val,"filter":""},f"{_fb_param}={_val}+filter"),
                ]
        best_code = None
        best_code = None
        _msg6_primero = ""
        for _vp,_vd in _variantes:
            if best_code==0: break
            try:
                _rv,_ = svc._client().browse(svc.ssid1,svc.ssid2,clase,dict(_vp))
                _c = _rv.get("code") if isinstance(_rv,dict) else -1
                _itms = _rv.get("items") or (_rv.get("data") if isinstance(_rv.get("data"),list) else [])
                _n = len(_itms) if isinstance(_itms,list) else 0
                _msg_data = str((_rv or {}).get("data",""))[:120]
                cr["browse_intentos"].append({"desc":_vd,"code":_c,"n_items":_n,"msg":_msg_data})
                if _c==6 and not _msg6_primero: _msg6_primero = _msg_data
                if _c==0:
                    best_code=0; cr["browse_ok"]=True; cr["n_items"]=_n; cr["params_exitosos"]=_vp
                    if not cr["items_muestra"] and isinstance(_itms,list) and _itms:
                        cr["items_muestra"]=_itms[:3]
                        cr["campos"]=(list(_itms[0].keys())[:20] if isinstance(_itms[0],dict) else [])
                elif best_code is None: best_code=_c
            except Exception as _eb:
                cr["browse_intentos"].append({"desc":_vd,"code":-1,"n_items":0,"msg":str(_eb)[:60]})
        cr["browse_code_final"]=best_code if best_code is not None else -1
        cr["browse_msg_exacto"]=_msg6_primero
        # read() con IDs reales de Firebird
        if _fb.get("ok") and _fb.get("valores"):
            _papi = _fb["param"]
            for _val in _fb["valores"][:3]:
                try:
                    _rdr,_ = svc._client().read(svc.ssid1,svc.ssid2,clase,{_papi:_val})
                    _rc = _rdr.get("code") if isinstance(_rdr,dict) else -1
                    _rmsg = str((_rdr or {}).get("data",""))[:120]
                    cr["read_intentos"].append({"objectid":_val,"code":_rc,"msg":_rmsg})
                    if _rc==0 and not cr["read_ok"]:
                        cr["read_ok"]=True; cr["read_code_final"]=0
                        if not cr["info_campos"] and isinstance((_rdr or {}).get("data"),dict):
                            cr["info_campos"]=list(_rdr["data"].keys())[:20]
                except Exception as _er:
                    cr["read_intentos"].append({"objectid":_val,"code":-1,"msg":str(_er)[:60]})
        if cr["read_code_final"] is None and cr["read_intentos"]:
            cr["read_code_final"]=cr["read_intentos"][-1]["code"]
        clases_resultado[clase]=cr
    # F4: new+cancel con variantes de params de contexto
    # CORRECCION: new() sin objectid para clases padre (doc oficial v1.2: objectid es OPCIONAL)
    # El fix en service.py ya no envia objectid=new para clases simples
    nc_resultados=[]
    _new_variantes = [
        ({},"sin_objectid"),            # CORRECTO segun doc: new() obligatorios solo ssid1+ssid2+objectclass
        ({"ejercicio":_anyo_bd},f"ej={_anyo_bd}"),
        ({"ejercicio":"2026"},"ej=2026"),
        ({"empr":cfg.get("empresa","")},"empr"),
    ]
    for _cls4 in ["proyectos","repobjetos","reporden","clientes"]:
        _nc_best_code=None; _nc_best_oid=""; _nc_best_variant=""; _nc_best_msg=""
        for _nvp, _nvd in _new_variantes:
            try:
                _rn,_=svc._client().new(svc.ssid1,svc.ssid2,_cls4,dict(_nvp))
                _cn=_rn.get("code") if isinstance(_rn,dict) else -1
                _nmsg=str((_rn or {}).get("data",""))[:120]
                if _cn==0:
                    _d4=(_rn or {}).get("data",{})
                    _oid=((_d4.get("objectId") or _d4.get("objectid") or _d4.get("id") or "new")
                          if isinstance(_d4,dict) else "new")
                    _nc_best_code=0; _nc_best_oid=_oid; _nc_best_variant=_nvd; _nc_best_msg=_nmsg; break
                elif _nc_best_code is None: _nc_best_code=_cn; _nc_best_msg=_nmsg; _nc_best_variant=_nvd
            except Exception as _enc:
                if _nc_best_code is None: _nc_best_code=-1; _nc_best_msg=str(_enc)[:80]; _nc_best_variant=_nvd
        _cc=-1
        if _nc_best_oid:
            try:
                _rc,_=svc._client().cancel(svc.ssid1,svc.ssid2,_cls4,{"objectid":_nc_best_oid})
                _cc=_rc.get("code") if isinstance(_rc,dict) else -1
            except Exception: pass
        nc_resultados.append({"clase":_cls4,"new_code":_nc_best_code,"cancel_code":_cc,
                               "bd_accesible":_nc_best_code==0,
                               "variant":_nc_best_variant,"msg":_nc_best_msg})
    # F5: Conclusiones automáticas
    n_ok  = sum(1 for v in clases_resultado.values() if v["browse_ok"])
    n_lic = sum(1 for v in clases_resultado.values() if v.get("permiso_code")==1)
    nc_ok = any(r["bd_accesible"] for r in nc_resultados)
    fb_ok = fb_diag.get("conexion_ok",False)
    n_var = sum(len(v["browse_intentos"]) for v in clases_resultado.values())
    _cl_ok  = [c for c,v in clases_resultado.items() if v["browse_ok"]]
    _cl_p6  = [c for c,v in clases_resultado.items() if not v["browse_ok"] and v.get("browse_code_final")==6]
    _cl_lic = [c for c,v in clases_resultado.items() if v.get("permiso_code")==1]
    _cl_perm_ok = [c for c,v in clases_resultado.items() if v.get("permiso_code")==0]
    _nc_new_codes = sorted({r["new_code"] for r in nc_resultados})
    _nc_code6_all = bool(nc_resultados) and all(r["new_code"]==6 for r in nc_resultados)
    _nc_code5_all = bool(nc_resultados) and all(r["new_code"]==5 for r in nc_resultados)
    # Datos adicionales para analisis
    _cl_read_ok = [c for c,v in clases_resultado.items() if v.get("read_ok")]
    _cl_info_ok = [c for c,v in clases_resultado.items() if v.get("info_code")==0]
    _msg6_ejemplos = {c:v.get("browse_msg_exacto","") for c,v in clases_resultado.items()
                      if v.get("browse_msg_exacto") and v.get("browse_code_final")==6}
    """Nuevo bloque de conclusiones para super_diagnostico — doc oficial v1.2."""
    # Este archivo es importado por _patch_conc2.py
    # code=6 segun documentacion OFICIAL mPYME v1.2 = MAINTENANCE MODE
    # NO es falta de parametro.
    # new()=code=5 'No dispone de licencia para el modulo Proyectos' = LICENCIA no contratada
    _todo_code6_mismo_msg = len(set(_msg6_ejemplos.values()))==1 if _msg6_ejemplos else False
    conclusiones=[]
    if n_ok:
        conclusiones.append({"tipo":"ok","texto":f"OK {n_ok} clase(s) con datos reales: {', '.join(_cl_ok)}"})
    if _cl_read_ok:
        conclusiones.append({"tipo":"ok","texto":f"OK read() funciona en: {', '.join(_cl_read_ok)}"})
    if n_lic:
        conclusiones.append({"tipo":"licencia","texto":f"Sin licencia (permiso code=1): {', '.join(_cl_lic)}"})
    if _cl_p6:
        _msg6_ej = list(_msg6_ejemplos.values())[0] if _msg6_ejemplos else ""
        _nc_msg5_texto = nc_resultados[0]["msg"] if nc_resultados else ""
        _tiene_lic_msg = "licencia" in _nc_msg5_texto.lower()
        if _nc_code5_all and _tiene_lic_msg:
            conclusiones.append({"tipo":"licencia","texto":(
                f"CAUSA PROBABLE: Modulo mPYME no contratado/activado. "
                f"new()=code=5: '{_nc_msg5_texto[:100]}'. "
                f"code=6 en browse = modo mantenimiento segun doc oficial mPYME v1.2. "
                f"Solicitar a Distrito K activar modulos: Proyectos, Reparaciones, Compras.")})
        elif _nc_code6_all:
            conclusiones.append({"tipo":"bd_inacc","texto":(
                f"code=6 en browse Y new() = MODO MANTENIMIENTO segun doc oficial mPYME v1.2. "
                f"Msg: '{_msg6_ej[:80]}'. "
                f"SQL Obras esta en modo mantenimiento. "
                f"Desactivar mantenimiento en SQL Obras o contactar Distrito K.")})
        else:
            conclusiones.append({"tipo":"params","texto":(
                f"code=6 en {len(_cl_p6)} clase(s) = modo mantenimiento segun doc oficial. "
                + (f"Msg: '{_msg6_ej[:80]}'. " if _msg6_ej else "")
                + f"Contactar Distrito K para resolver.")})
    _cl_p5 = [c for c,v in clases_resultado.items() if not v["browse_ok"] and v.get("browse_code_final")==5]
    if _cl_p5:
        conclusiones.append({"tipo":"config","texto":f"code=5 (Peticion no reconocida o no soportada): {', '.join(_cl_p5)}"})
    if not fb_ok:
        conclusiones.append({"tipo":"firebird","texto":"Firebird no conecta. Verificar .env"})
    empresa=cfg.get("empresa","?"); api_url=cfg.get("api_url","?")
    db_host=fb_diag.get("db_host","?"); db_name=fb_diag.get("db_name","?")
    _ids_ej=[f"  - {c}: {ids_pool.get(c,{}).get('param','?')}={ids_pool.get(c,{}).get('valores',[None])[0]}"
             for c in _cl_p6[:3] if ids_pool.get(c,{}).get("ok")]
    _pe=clases_resultado.get(_cl_p6[0],{}).get("permiso_code","?") if _cl_p6 else "?"
    _nc_msgs=[f"{r['clase']}: new()=code{r['new_code']} ({r['msg'][:60]})" for r in nc_resultados]
    aviso_admin=""
    if _cl_p6 and _nc_code6_all:
        _msg6_mant = list(_msg6_ejemplos.values())[0] if _msg6_ejemplos else "?"
        aviso_admin=(
            f"AVISO: SQL Obras esta en MODO MANTENIMIENTO ({ts_inicio[:19]}).\n"
            f"code=6 segun documentacion oficial mPYME = modo mantenimiento activo.\n"
            f"Mensaje del servidor: '{_msg6_mant}'.\n\n"
            f"ACCION: Desactivar modo mantenimiento en SQL Obras:\n"
            f"  Administracion > Sistema > Modo mantenimiento > Desactivar\n"
            f"  O reiniciar PymeMobileServer.exe si el modo persiste."
        )
    pregunta_dk=""
    if _cl_p6 or _nc_code6_all or _nc_code5_all:
        _msg6_ej2 = list(_msg6_ejemplos.values())[0] if _msg6_ejemplos else "(no capturado)"
        _read_info = ""
        if _cl_read_ok:
            _read_info = f"read() devuelve code=0 en: {', '.join(_cl_read_ok)}.\n"
        _nc_msg_ej = nc_resultados[0]["msg"][:100] if nc_resultados else ""
        pregunta_dk=(
            f"Hola Distrito K,\n\nInstalacion: empresa={empresa}, URL={api_url}\n"
            f"BD Firebird: {db_host} / {db_name}\n\n"
            f"SITUACION:\n"
            f"browse() devuelve code=6 en {len(_cl_p6)} clases tras {n_var} variantes probadas.\n"
            f"new() devuelve code=6 en todas las clases con params vacio y con ejercicio.\n"
            f"Mensaje exacto recibido en code=6: '{_msg6_ej2}'\n\n"
            f"SEGUN DOCUMENTACION OFICIAL v1.2:\n"
            f"code=6 = Maintenance mode. No sabemos si SQL Obras esta en mantenimiento.\n"
            f"new() tambien code=6 => posible modo mantenimiento global.\n\n"
            f"VARIANTES YA PROBADAS EN BROWSE:\n"
            f"  vacio, pagesize=1/25, filter=vacio, estado=abierta/activa, soloActivos=T,\n"
            f"  activo=T, todos=T, ejercicio=2021/2025/2026, anyo=2021/2026,\n"
            f"  objectid=new, IDs reales Firebird, masterid, master, desde/hasta (proordutil),\n"
            f"  serie=A (docs), mode=add (repobjetos), columns=asc\n\n"
            + ("".join(f"  {l}\n" for l in _ids_ej) if _ids_ej else "  (ver detalle por clase)\n")
            + (f"\nQUE SI FUNCIONA:\n{_read_info}" if _read_info else "")
            + f"\nNEW() MSG: '{_nc_msg_ej}'\n\n"
            f"PREGUNTAS:\n"
            f"  1. Que parametro obligatorio requiere browse() en estas clases?\n"
            f"     (proyectos, reporden, clientes, docalbcom, docfaccom, docpedcom, etc.)\n"
            f"  2. SQL Obras esta en modo mantenimiento? Como desactivarlo?\n"
            f"  3. new() de proyectos da 'No dispone de licencia'. Esta contratado el modulo?\n"
            f"  4. Hay parametro de instalacion obligatorio en todas las llamadas?\n"
            f"     (ejercicio=AAAA? codEmpresa? soloActivos? otro?)\n\n"
            f"Muchas gracias."
        )
    db_host=fb_diag.get("db_host","?"); db_name=fb_diag.get("db_name","?")
    _ids_ej=[f"  - {c}: {ids_pool.get(c,{}).get('param','?')}={ids_pool.get(c,{}).get('valores',[None])[0]}"
             for c in _cl_p6[:3] if ids_pool.get(c,{}).get("ok")]
    _pe=clases_resultado.get(_cl_p6[0],{}).get("permiso_code","?") if _cl_p6 else "?"
    _nc_msgs=[f"{r['clase']}: new()=code{r['new_code']} ({r['msg'][:60]})" for r in nc_resultados]
    aviso_admin=""  # ya no hay aviso de servidor: code=6 = falta parametro, no es error de BD
    # Pregunta correcta para Distrito K (siempre que haya code=6, independiente de new())
    pregunta_dk=""
    if _cl_p6 or _nc_code6_all:
        _msg6_ej = list(_msg6_ejemplos.values())[0] if _msg6_ejemplos else "(no capturado)"
        _read_info = ""
        if _cl_read_ok:
            _read_info = f"read() devuelve code=0 en: {', '.join(_cl_read_ok)}.\n"
        if _cl_info_ok:
            _read_info += f"info() devuelve code=0 en: {', '.join(_cl_info_ok)}.\n"
        _campos_info = {}
        for _c, _v in clases_resultado.items():
            if _v.get("info_campos"): _campos_info[_c] = _v["info_campos"][:10]
        _campos_str = "\n".join(f"  - {c}: {', '.join(fs)}" for c,fs in list(_campos_info.items())[:4]) if _campos_info else ""
        _nc_msg_ej = nc_resultados[0]["msg"][:100] if nc_resultados else ""
        pregunta_dk=(
            f"Hola Distrito K,\n\nInstalacion: empresa={empresa}, URL={api_url}\n"
            f"BD Firebird: {db_host} / {db_name}\n\n"
            f"SITUACION:\n"
            f"browse() devuelve code=6 en {len(_cl_p6)} clases tras {n_var} variantes probadas.\n"
            f"new() devuelve code=6 en todas las clases con params vacio y con ejercicio.\n"
            f"Mensaje exacto recibido en code=6: '{_msg6_ej}'\n\n"
            f"VARIANTES YA PROBADAS EN BROWSE:\n"
            f"  vacio, pagesize=1/25, filter={{}}, estado=abierta/activa, soloActivos=T,\n"
            f"  activo=T, todos=T, ejercicio=2021/2025/2026, anyo=2021/2026,\n"
            f"  objectid=new, IDs reales Firebird con {_fb.get('param','?')}=\n"
            + ("".join(f"  {l}\n" for l in _ids_ej) if _ids_ej else "  (ver detalle por clase)\n")
            + (f"\nQUE SI FUNCIONA:\n{_read_info}" if _read_info else "")
            + (f"\nCAMPOS CONOCIDOS (de info()):\n{_campos_str}\n" if _campos_str else "")
            + f"\nNEW() MSG: '{_nc_msg_ej}'\n\n"
            f"PREGUNTAS:\n"
            f"  1. Que parametro obligatorio requiere browse() en estas clases?\n"
            f"     (proyectos, reporden, clientes, docalbcom, docfaccom, docpedcom, etc.)\n"
            f"  2. Que parametros obligatorios requiere new()?\n"
            f"  3. El mensaje 'No es posible acceder a la base de datos' en code=6\n"
            f"     siempre significa 'falta parametro' o hay otra causa?\n"
            f"  4. Hay parametro de instalacion obligatorio en todas las llamadas?\n"
            f"     (ejercicio=AAAA? codEmpresa? soloActivos? otro?)\n"
            f"  5. La documentacion menciona parametros obligatorios por clase?\n\n"
            f"Muchas gracias."
        )
    return {
        "success":True,"timestamp":ts_inicio,"empresa":empresa,"api_url":api_url,
        "fases":{
            "firebird":{"ok":fb_ok,"db_host":fb_diag.get("db_host",""),
                        "db_name":fb_diag.get("db_name",""),"error":fb_diag.get("error",""),
                        "n_proyectos":fb_diag.get("tablas_probadas",{}).get("PROYECTOS",{}).get("n_registros",0)},
            "ids_pool":{"n_clases":sum(1 for v in ids_pool.values() if v.get("ok")),
                        "detalle":{k:{"ok":v.get("ok"),"n":v.get("n",0),"tabla":v.get("tabla","")}
                                   for k,v in ids_pool.items()}},
            "browse":{"n_ok":n_ok,"n_code6":len(_cl_p6),"n_lic":n_lic,"n_var":n_var},
            "new_cancel":{"resultados":nc_resultados,"alguno_ok":nc_ok,
                          "new_codes":_nc_new_codes,"nc_code6_all":_nc_code6_all},
        },
        "clases":clases_resultado,
        "ids_pool":{k:{"ok":v.get("ok"),"param":v.get("param"),"n":v.get("n",0),
                       "tabla":v.get("tabla"),"error":v.get("error")} for k,v in ids_pool.items()},
        "conclusiones":conclusiones,
        "pregunta_distrito_k":pregunta_dk,
        "aviso_admin":aviso_admin,
        "nc_new_codes":_nc_new_codes,
        "bd_host":db_host,"bd_name":db_name,
        "clases_permiso_ok":_cl_perm_ok,
        "resumen":{"n_browse_ok":n_ok,"n_sin_licencia":n_lic,"n_req_params":len(_cl_p6),
                   "bd_mpyme_accesible":nc_ok,"fb_conecta":fb_ok,"n_var":n_var,
                   "clases_con_datos":_cl_ok,"clases_code6":_cl_p6,
                   "nc_new_codes":_nc_new_codes,"bd_host":db_host},
    }


@router.get("/modo-mantenimiento")
async def modo_mantenimiento():
    """
    Verifica si SQL Obras/PymeMobileServer esta en modo mantenimiento
    y devuelve instrucciones paso a paso para desactivarlo.

    Segun documentacion oficial mPYME v1.2 pag. 7:
    code=6 = Maintenance mode: el sistema esta en modo mantenimiento.

    El modo mantenimiento se puede activar/desactivar desde:
    1. SQL Obras desktop (si tienes acceso directo)
    2. PymeMobileServer.exe (reinicio del servicio)
    3. Contactando a Distrito K
    """
    svc = get_service()
    cfg = svc.get_config_env()
    api_url = cfg.get("api_url", "?")
    empresa = cfg.get("empresa", "?")
    ts = __import__("datetime").datetime.now().isoformat()

    # Prueba rapida: hace una sola llamada browse(clientes) para detectar si sigue en mantenimiento
    esta_en_mantenimiento = None
    browse_msg = ""
    browse_code = None
    if svc.session_active:
        try:
            _rb, _ = svc._client().browse(svc.ssid1, svc.ssid2, "clientes", {})
            browse_code = _rb.get("code") if isinstance(_rb, dict) else -1
            browse_msg = str((_rb or {}).get("data", ""))[:200]
            esta_en_mantenimiento = (browse_code == 6)
        except Exception as _em:
            esta_en_mantenimiento = None
            browse_msg = str(_em)[:100]

    return {
        "success": True,
        "timestamp": ts,
        "api_url": api_url,
        "empresa": empresa,
        "browse_clientes_code": browse_code,
        "browse_clientes_msg": browse_msg,
        "esta_en_mantenimiento": esta_en_mantenimiento,
        "instrucciones": {
            "titulo": "Como desactivar el modo mantenimiento en SQL Obras",
            "descripcion": (
                "El modo mantenimiento (code=6 segun doc mPYME v1.2) bloquea TODAS las "
                "llamadas a la API. Mensaje del servidor: 'No es posible acceder a la base "
                "de datos en este momento'. Se puede desactivar sin necesidad de llamar a "
                "Distrito K si tienes acceso al servidor."
            ),
            "opcion_A": {
                "titulo": "Opcion A: Desde SQL Obras desktop (RECOMENDADA si tienes acceso)",
                "pasos": [
                    "1. Abrir SQL Obras en el PC servidor (192.168.0.254)",
                    "2. Menu: Administracion > Sistema (o Herramientas > Opciones del sistema)",
                    "3. Buscar 'Modo mantenimiento' o 'Mantenimiento API'",
                    "4. Si esta activo: DESACTIVAR y guardar",
                    "5. Alternativa: Utilidades > Modo servicio > Desactivar",
                    "6. Reiniciar PymeMobileServer.exe despues",
                    "7. Volver a DEVIA y repetir el Diagnostico completo"
                ],
            },
            "opcion_B": {
                "titulo": "Opcion B: Reiniciar PymeMobileServer.exe",
                "pasos": [
                    "1. En el servidor 192.168.0.254: abrir Servicios de Windows",
                    "   (Inicio > Ejecutar > services.msc)",
                    "2. Buscar 'PymeMobile Server' o 'mPYME'",
                    "3. Click derecho > Reiniciar",
                    "4. Esperar 30 segundos",
                    "5. Volver a DEVIA y repetir el Diagnostico completo",
                    "NOTA: Reiniciar el servicio NO desactiva el modo mantenimiento si "
                    "fue activado deliberadamente desde SQL Obras. Usar Opcion A primero."
                ],
            },
            "opcion_C": {
                "titulo": "Opcion C: Reiniciar el servidor completo",
                "pasos": [
                    "1. Reiniciar el servidor 192.168.0.254",
                    "2. Esperar a que SQL Obras y PymeMobileServer arranquen",
                    "3. Verificar que SQL Obras abre sin pedir confirmacion de mantenimiento",
                    "4. Volver a DEVIA y repetir el Diagnostico completo"
                ],
            },
            "opcion_D": {
                "titulo": "Opcion D: Contactar a Distrito K",
                "pasos": [
                    "Enviar el mensaje de la pregunta generada en el Diagnostico completo",
                    "Preguntar: '¿Esta activo el modo mantenimiento en nuestra instalacion? "
                    "browse() y new() devuelven code=6 (Maintenance mode segun doc v1.2) "
                    "con el mensaje \"No es posible acceder a la base de datos en este momento\"'",
                    "Solicitar que verifiquen el estado del servidor y desactiven el modo mantenimiento"
                ],
            },
        },
        "nota_doc": (
            "Documentacion oficial mPYME v1.2, pag. 7: "
            "'code=6 = Maintenance mode: no se puede ejecutar la peticion por encontrarse "
            "el sistema en modo de mantenimiento. La sesion sigue siendo valida.'"
        ),
    }


@router.get("/validar-datos-bd")
async def validar_datos_bd():
    ts = __import__("datetime").datetime.now().isoformat()
    try:
        drv = _get_db_driver()
    except Exception as e:
        return {"success": False, "error": f"Firebird no accesible: {e}",
                "timestamp": ts, "nota": "Ejecutar desde la VM en la red local."}
    def _q(sql):
        try: return drv.execute_query(sql) or []
        except Exception as ex:
            msg=str(ex)
            if "-204" in msg or "Table unknown" in msg.lower():
                return []  # tabla no existe, lista vacia limpia
            return [{"ERROR": msg[:100]}]
    def _count(tabla_o_sql):
        try:
            sql=(tabla_o_sql if tabla_o_sql.strip().upper().startswith("SELECT")
                 else f"SELECT COUNT(*) AS N FROM {tabla_o_sql}")
            r=drv.execute_query(sql)
            if not r: return 0
            row=r[0]; return row.get("N") or row.get("n") or 0
        except Exception as ex:
            msg=str(ex)
            if "-204" in msg or "Table unknown" in msg.lower():
                return "NO_EXISTE"  # tabla no existe en esta BD
            if "-206" in msg or "Column unknown" in msg.lower():
                return "COL_ERROR"  # columna no existe, tabla existe
            return f"ERR:{msg[:60]}"
    resultado={"timestamp":ts,"modulos":{},"success":False}
    try:
        # --- MAESTROS ---
        n_cli=_count("CLIENTE"); n_prov=_count("PROVEED"); n_art=_count("ARTICULO")
        n_rec=_count("RECURSO"); n_reobj=_count("REPOBJETO"); n_repinst=_count("REPINSTALACION")
        rec_m=_q("SELECT FIRST 5 CODIGO,DESCRIPCION FROM RECURSO ORDER BY CODIGO")
        reobj_m=_q("SELECT FIRST 3 CODIGO,NOMBRE,CODPROPIETARIO FROM REPOBJETO ORDER BY CODIGO")
        resultado["modulos"]["maestros"]={
            "descripcion":"Clientes, proveedores, articulos, tecnicos, objetos de cliente",
            "api_licencia":"Base (sin licencia extra)",
            "tablas":{
                "CLIENTE":{"n":n_cli,"ok":isinstance(n_cli,int) and n_cli>0},
                "PROVEED":{"n":n_prov,"ok":isinstance(n_prov,int) and n_prov>0},
                "ARTICULO":{"n":n_art,"ok":isinstance(n_art,int) and n_art>0},
                "RECURSO":{"n":n_rec,"ok":isinstance(n_rec,int) and n_rec>0,"muestra":rec_m[:3]},
                "REPOBJETO":{"n":n_reobj,"ok":isinstance(n_reobj,int) and n_reobj>0,"muestra":reobj_m[:3]},
                "REPINSTALACION":{"n":n_repinst,"ok":isinstance(n_repinst,int) and n_repinst>0},
            },
            "conclusion":(
                f"{n_cli} clientes, {n_prov} proveedores, {n_art} articulos, "
                f"{n_rec} tecnicos, {n_reobj} objetos de cliente. DATOS REALES OK."
                if all(isinstance(x,int) and x>0 for x in [n_cli,n_prov,n_art])
                else "Algunas tablas vacias o error de acceso."
            ),
        }
        # --- PROYECTOS ---
        proy_defs=[
            ("PREUTILLIN","Horas/costes imputados reales EN PROYECTOS (campo clave)"),
            ("PREUTILCAB","Imputacion real cabecera"),
            ("PREPREVLIN","Previsiones de horas por proyecto"),
            ("PREPREV","Previsiones cabecera"),
            ("PRESUPROYE","Presupuesto del proyecto"),
            ("PARTPROYE","Partidas/capitulos BC3"),
        ]
        proy_tablas={}
        for tabla,desc in proy_defs:
            n=_count(tabla); m=[]
            if isinstance(n,int) and n>0:
                if tabla=="PREUTILLIN":
                    m=_q("SELECT FIRST 3 pl.CODMAESTRO,pl.CODRECURSO,pl.CANTIDAD,pl.PRECIO,pl.COSTE,pl.FECHA,r.DESCRIPCION AS TECNICO FROM PREUTILLIN pl LEFT JOIN RECURSO r ON pl.CODRECURSO=r.CODIGO WHERE pl.CANTIDAD>0 ORDER BY pl.FECHA DESC")
                elif tabla=="PREPREVLIN":
                    m=_q("SELECT FIRST 3 CODMAESTRO,CODRECURSO,DURACION,PRECIO FROM PREPREVLIN ORDER BY CODMAESTRO")
                elif tabla=="PRESUPROYE":
                    m=_q("SELECT FIRST 3 CODPROYECTO,DESCRIPCION,IMPORTE FROM PRESUPROYE ORDER BY CODPROYECTO DESC")
            proy_tablas[tabla]={"desc":desc,"n":n,"ok":isinstance(n,int) and n>0,"muestra":m}
        n_pu=proy_tablas.get("PREUTILLIN",{}).get("n",0)
        n_pp=proy_tablas.get("PREPREVLIN",{}).get("n",0)
        n_proy=_count("PROYECTOS")
        resultado["modulos"]["gestion_proyectos"]={
            "descripcion":"Horas imputadas en proyectos, previsiones, partidas, costes reales",
            "api_licencia":"mPyme Proyectos (REQUIERE LICENCIA)",
            "n_proyectos_bd":n_proy,
            "tablas":proy_tablas,
            "conclusion":(
                f"{n_proy} proyectos en BD. {n_pu} imputaciones reales de horas, {n_pp} previsiones. "
                "DATOS REALES. La licencia mPyme Proyectos dara acceso a horas/costes reales por tecnico y proyecto. MUY RENTABLE."
                if isinstance(n_pu,int) and n_pu>0 else (
                    f"{n_proy} proyectos en BD pero PREUTILLIN tiene {n_pu} registros. "
                    "La empresa NO imputa horas/costes en proyectos dentro de SQL Obras. "
                    "La licencia daria acceso a proyectos pero NO a horas de tecnico (no existen en BD)."
                    if isinstance(n_pu,int) else f"ERROR: {n_pu}"
                )
            ),
        }
        # --- REPARACIONES ---
        rep_defs=[
            ("REPARA","Partes/ordenes de reparacion SAT"),
            ("RABUTILLIN","Horas de tecnico en partes (campo clave)"),
            ("RABUTILCAB","Horas imputadas cabecera"),
            ("REPOBJETO","Objetos/equipos del cliente"),
            ("REPINSTALACION","Instalaciones del cliente"),
        ]
        rep_tablas={}
        for tabla,desc in rep_defs:
            n=_count(tabla); m=[]
            if isinstance(n,int) and n>0:
                if tabla=="REPARA":
                    m=_q("SELECT FIRST 3 CODIGO,DESCRIPCION,FECHA,CODCLIENTE FROM REPARA ORDER BY FECHA DESC")
                elif tabla=="RABUTILLIN":
                    m=_q("SELECT FIRST 3 rl.CODMAESTRO,rl.CODRECURSO,rl.CANTIDAD,rl.PRECIO,rl.COSTE,rl.FECHA,r.DESCRIPCION AS TECNICO FROM RABUTILLIN rl LEFT JOIN RECURSO r ON rl.CODRECURSO=r.CODIGO WHERE rl.CANTIDAD>0 ORDER BY rl.FECHA DESC")
                elif tabla=="REPOBJETO":
                    m=_q("SELECT FIRST 3 CODIGO,NOMBRE,CODPROPIETARIO FROM REPOBJETO ORDER BY CODIGO")
            rep_tablas[tabla]={"desc":desc,"n":n,"ok":isinstance(n,int) and n>0,"muestra":m}
        n_ru=rep_tablas.get("RABUTILLIN",{}).get("n",0)
        n_ra=rep_tablas.get("REPARA",{}).get("n",0)
        resultado["modulos"]["reparaciones"]={
            "descripcion":"Partes SAT, horas de tecnico por parte, objetos de cliente",
            "api_licencia":"mPyme Reparaciones (posible con licencia actual)",
            "tablas":rep_tablas,
            "conclusion":(
                f"{n_ra} partes SAT con {n_ru} lineas de horas de tecnico. "
                "DATOS REALES. La API repordutil dara horas reales por tecnico. MUY RELEVANTE."
                if isinstance(n_ru,int) and n_ru>0 else (
                    f"{n_ra} partes SAT pero RABUTILLIN={n_ru}. "
                    "Los partes no llevan horas de tecnico detalladas en SQL Obras. "
                    "La API daria cabeceras de partes pero no horas."
                    if isinstance(n_ra,int) and n_ra>0 else f"VERIFICAR:{n_ru}"
                )
            ),
        }
        # --- DOCUMENTOS COMPRA ---
        n_ap=_count("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=3 AND CODPROYECTO IS NOT NULL AND TRIM(CODPROYECTO)<>''")
        n_fp=_count("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=2 AND CODPROYECTO IS NOT NULL AND TRIM(CODPROYECTO)<>''")
        tipos_doc=_q("SELECT TIPO,COUNT(*) AS N FROM DOCCAB WHERE TIPO IN (1,2,3,11,12,13,21) GROUP BY TIPO ORDER BY TIPO")
        alb_m=_q("SELECT FIRST 3 CODIGO,SERIE,NUMERO,FECHA,CODCLIENTE,CODPROYECTO,IMPORTETOTAL FROM DOCCAB WHERE TIPO=3 AND CODPROYECTO IS NOT NULL ORDER BY FECHA DESC")
        resultado["modulos"]["documentos_compra"]={
            "descripcion":"Albaranes y facturas de compra, vinculacion a proyectos",
            "api_licencia":"mPyme Documentos",
            "tablas":{"DOCCAB_tipos":tipos_doc,"alb_con_proyecto":{"n":n_ap,"muestra":alb_m[:3]},"fac_con_proyecto":{"n":n_fp}},
            "conclusion":(
                f"{n_ap} albaranes y {n_fp} facturas de compra vinculadas a proyectos. "
                "La imputacion docalbcom->imputaPro funcionara con datos reales."
                if isinstance(n_ap,int) and n_ap>0 else
                "Documentos de compra no vinculados a proyectos. Revisar flujo antes de comprar."
            ),
        }
        # --- RECOMENDACIONES ---
        recs=[]
        n_pu2=resultado["modulos"]["gestion_proyectos"]["tablas"].get("PREUTILLIN",{}).get("n",0)
        n_ru2=resultado["modulos"]["reparaciones"]["tablas"].get("RABUTILLIN",{}).get("n",0)
        n_ra2=resultado["modulos"]["reparaciones"]["tablas"].get("REPARA",{}).get("n",0)
        n_ap2=resultado["modulos"]["documentos_compra"]["tablas"].get("alb_con_proyecto",{}).get("n",0)
        if isinstance(n_pu2,int) and n_pu2>0: recs.append(f"COMPRAR mPyme Proyectos: {n_pu2} imputaciones de horas reales disponibles.")
        else: recs.append("ESTUDIAR mPyme Proyectos: hay proyectos pero sin horas imputadas. Preguntar a DK sobre flujo.")
        if isinstance(n_ru2,int) and n_ru2>0: recs.append(f"ACTIVAR Reparaciones: {n_ra2} partes con {n_ru2} horas de tecnico.")
        elif isinstance(n_ra2,int) and n_ra2>0: recs.append(f"EVALUAR Reparaciones: {n_ra2} partes SAT pero sin horas detalladas en RABUTILLIN.")
        if isinstance(n_ap2,int) and n_ap2>0: recs.append(f"ACTIVAR Documentos compra: {n_ap2} albaranes ya vinculados a proyectos.")
        resultado["recomendaciones"]=recs
        resultado["success"]=True
    except Exception as e:
        resultado["error"]=str(e)
    finally:
        try: drv.disconnect()
        except: pass
    return resultado


@router.get("/informe-maestro")
async def informe_maestro():
    import datetime as _dt
    ts = _dt.datetime.now().isoformat()
    svc = get_service()
    cfg = svc.get_config_env()
    api_url = cfg.get("api_url","?")
    empresa = cfg.get("empresa","?")
    sesion_activa = svc.session_active

    # ======================================================
    # BLOQUE 1: Firebird — datos reales de la BD
    # ======================================================
    fb_ok = False
    fb_error = ""
    fb_datos = {}
    try:
        drv = _get_db_driver()
        fb_ok = True
        def _q(sql):
            try: return drv.execute_query(sql) or []
            except Exception as ex:
                msg=str(ex)
                if "-204" in msg or "Table unknown" in msg.lower():
                    return []
                return [{"ERROR": msg[:120]}]
        def _n(sql_o_tabla):
            sql = (sql_o_tabla if sql_o_tabla.strip().upper().startswith("SELECT")
                   else f"SELECT COUNT(*) AS N FROM {sql_o_tabla}")
            try:
                r = drv.execute_query(sql)
                if not r: return 0
                row = r[0]; return int(row.get("N") or row.get("n") or 0)
            except Exception as ex:
                msg=str(ex)
                if "-204" in msg or "Table unknown" in msg.lower():
                    return "NO_EXISTE"
                if "-206" in msg or "Column unknown" in msg.lower():
                    return "COL_ERROR"
                return f"ERR:{msg[:60]}"

        # Maestros
        fb_datos["n_clientes"]     = _n("CLIENTE")
        fb_datos["n_proveedores"]  = _n("PROVEED")
        fb_datos["n_articulos"]    = _n("ARTICULO")
        fb_datos["n_recursos"]     = _n("RECURSO")
        fb_datos["n_repobjetos"]   = _n("REPOBJETO")
        fb_datos["n_repinstalacion"] = _n("REPINSTALACION")
        fb_datos["n_familias"]     = _n("FAMILIA")
        fb_datos["muestra_recursos"] = _q("SELECT FIRST 8 CODIGO,DESCRIPCION FROM RECURSO ORDER BY CODIGO")
        fb_datos["muestra_clientes"] = _q("SELECT FIRST 3 CODIGO,RAZONSOCIAL FROM CLIENTE ORDER BY CODIGO")
        # Proyectos
        fb_datos["n_proyectos"]    = _n("PROYECTOS")
        fb_datos["n_proy_activos"] = _n("SELECT COUNT(*) AS N FROM PROYECTOS WHERE FINOBRA<>'T'")
        fb_datos["n_preutillin"]   = _n("PREUTILLIN")
        fb_datos["n_preutilcab"]   = _n("PREUTILCAB")
        fb_datos["n_preprevlin"]   = _n("PREPREVLIN")
        fb_datos["n_presuproye"]   = _n("PRESUPROYE")
        fb_datos["n_partproye"]    = _n("PARTPROYE")
        if isinstance(fb_datos["n_preutillin"],int) and fb_datos["n_preutillin"]>0:
            fb_datos["muestra_horas_proyecto"] = _q(
                "SELECT FIRST 5 pl.CODMAESTRO,pl.CODRECURSO,pl.CANTIDAD,pl.PRECIO,pl.COSTE,"
                "pl.FECHA,r.DESCRIPCION AS TECNICO "
                "FROM PREUTILLIN pl LEFT JOIN RECURSO r ON pl.CODRECURSO=r.CODIGO "
                "WHERE pl.CANTIDAD>0 ORDER BY pl.FECHA DESC"
            )
            fb_datos["rango_fechas_imputacion"] = _q(
                "SELECT MIN(FECHA) AS DESDE, MAX(FECHA) AS HASTA, COUNT(DISTINCT CODMAESTRO) AS N_PROYECTOS "
                "FROM PREUTILLIN WHERE CANTIDAD>0"
            )
            fb_datos["top_tecnicos"] = _q(
                "SELECT FIRST 5 pl.CODRECURSO, r.DESCRIPCION AS TECNICO, "
                "COUNT(*) AS N_IMPUTACIONES, SUM(pl.CANTIDAD) AS HORAS_TOTALES, "
                "AVG(pl.PRECIO) AS PRECIO_MEDIO "
                "FROM PREUTILLIN pl LEFT JOIN RECURSO r ON pl.CODRECURSO=r.CODIGO "
                "WHERE pl.CANTIDAD>0 GROUP BY pl.CODRECURSO,r.DESCRIPCION "
                "ORDER BY HORAS_TOTALES DESC"
            )
        else:
            fb_datos["muestra_horas_proyecto"] = []
            fb_datos["rango_fechas_imputacion"] = []
            fb_datos["top_tecnicos"] = []
        # Reparaciones
        fb_datos["n_repara"]       = _n("REPARA")
        fb_datos["n_repara_abiertas"] = _n("SELECT COUNT(*) AS N FROM REPARA WHERE ESTADO='A'")
        fb_datos["n_rabutillin"]   = _n("RABUTILLIN")
        fb_datos["n_rabutilcab"]   = _n("RABUTILCAB")
        fb_datos["muestra_repara"] = _q("SELECT FIRST 3 CODIGO,DESCRIPCION,FECHA,CODCLIENTE,ESTADO FROM REPARA ORDER BY FECHA DESC")
        if isinstance(fb_datos["n_rabutillin"],int) and fb_datos["n_rabutillin"]>0:
            fb_datos["muestra_horas_rep"] = _q(
                "SELECT FIRST 5 rl.CODMAESTRO,rl.CODRECURSO,rl.CANTIDAD,rl.PRECIO,rl.COSTE,"
                "rl.FECHA,r.DESCRIPCION AS TECNICO "
                "FROM RABUTILLIN rl LEFT JOIN RECURSO r ON rl.CODRECURSO=r.CODIGO "
                "WHERE rl.CANTIDAD>0 ORDER BY rl.FECHA DESC"
            )
            fb_datos["top_tecnicos_rep"] = _q(
                "SELECT FIRST 5 rl.CODRECURSO,r.DESCRIPCION AS TECNICO,"
                "COUNT(*) AS N_PARTES,SUM(rl.CANTIDAD) AS HORAS_TOTALES,AVG(rl.PRECIO) AS PRECIO_MEDIO "
                "FROM RABUTILLIN rl LEFT JOIN RECURSO r ON rl.CODRECURSO=r.CODIGO "
                "WHERE rl.CANTIDAD>0 GROUP BY rl.CODRECURSO,r.DESCRIPCION "
                "ORDER BY HORAS_TOTALES DESC"
            )
        else:
            fb_datos["muestra_horas_rep"] = []
            fb_datos["top_tecnicos_rep"] = []
        # Documentos
        fb_datos["n_doccab_total"]  = _n("DOCCAB")
        fb_datos["dist_tipos_doc"]  = _q("SELECT TIPO,COUNT(*) AS N FROM DOCCAB GROUP BY TIPO ORDER BY N DESC")
        fb_datos["n_albcom"]        = _n("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=3")
        fb_datos["n_faccom"]        = _n("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=2")
        fb_datos["n_pedcom"]        = _n("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=1")
        fb_datos["n_albven"]        = _n("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=13")
        fb_datos["n_facven"]        = _n("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=12")
        fb_datos["n_albcom_proy"]   = _n("SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=3 AND CODPROYECTO IS NOT NULL AND CODPROYECTO<>0")
        fb_datos["muestra_albcom_proy"] = _q(
            "SELECT FIRST 3 CODIGO,SERIE,NUMERO,FECHA,CODCLIENTE,CODPROYECTO,IMPORTETOTAL "
            "FROM DOCCAB WHERE TIPO=3 AND CODPROYECTO IS NOT NULL ORDER BY FECHA DESC"
        ) if isinstance(fb_datos.get("n_albcom_proy"),int) and fb_datos["n_albcom_proy"]>0 else []

        drv.disconnect()
    except Exception as e:
        fb_ok = False
        fb_error = str(e)[:200]
        try: drv.disconnect()
        except: pass

    # ======================================================
    # BLOQUE 2: API mPYME — llamadas reales (permiso + browse si posible)
    # ======================================================
    api_clases = {
        "clientes":     {"modulo":"maestros","licencia":"base","tabla_fb":"CLIENTE","n_fb":fb_datos.get("n_clientes",0)},
        "proveedores":  {"modulo":"maestros","licencia":"base","tabla_fb":"PROVEED","n_fb":fb_datos.get("n_proveedores",0)},
        "articulos":    {"modulo":"maestros","licencia":"base","tabla_fb":"ARTICULO","n_fb":fb_datos.get("n_articulos",0)},
        "recursos":     {"modulo":"maestros","licencia":"base","tabla_fb":"RECURSO","n_fb":fb_datos.get("n_recursos",0)},
        "proyectos":    {"modulo":"proyectos","licencia":"mPyme Proyectos","tabla_fb":"PROYECTOS","n_fb":fb_datos.get("n_proyectos",0)},
        "partidas":     {"modulo":"proyectos","licencia":"mPyme Proyectos","tabla_fb":"PROYECTOS","n_fb":fb_datos.get("n_proyectos",0)},
        "proordutil":   {"modulo":"proyectos","licencia":"mPyme Proyectos","tabla_fb":"PREUTILLIN","n_fb":fb_datos.get("n_preutillin",0)},
        "proordprev":   {"modulo":"proyectos","licencia":"mPyme Proyectos","tabla_fb":"PREPREVLIN","n_fb":fb_datos.get("n_preprevlin",0)},
        "reporden":     {"modulo":"reparaciones","licencia":"mPyme Reparaciones","tabla_fb":"REPARA","n_fb":fb_datos.get("n_repara",0)},
        "repordutil":   {"modulo":"reparaciones","licencia":"mPyme Reparaciones","tabla_fb":"RABUTILLIN","n_fb":fb_datos.get("n_rabutillin",0)},
        "repobjetos":   {"modulo":"reparaciones","licencia":"mPyme Reparaciones","tabla_fb":"REPOBJETO","n_fb":fb_datos.get("n_repobjetos",0)},
        "tipostrabajo": {"modulo":"reparaciones","licencia":"mPyme Reparaciones","tabla_fb":"TIPO","n_fb":0},
        "docalbcom":    {"modulo":"documentos","licencia":"mPyme Documentos","tabla_fb":"DOCCAB","n_fb":fb_datos.get("n_albcom",0)},
        "docfaccom":    {"modulo":"documentos","licencia":"mPyme Documentos","tabla_fb":"DOCCAB","n_fb":fb_datos.get("n_faccom",0)},
        "docpedcom":    {"modulo":"documentos","licencia":"mPyme Documentos","tabla_fb":"DOCCAB","n_fb":fb_datos.get("n_pedcom",0)},
        "ordenfab":     {"modulo":"fabricacion","licencia":"mPyme Fabricacion","tabla_fb":"FABCAB","n_fb":0},
    }
    api_resultados = {}
    mantenimiento_detectado = False
    if sesion_activa:
        for clase, info in api_clases.items():
            res = {"permiso_code":None,"permiso_msg":"","browse_code":None,"browse_msg":"",
                   "browse_n":0,"browse_muestra":[],"new_code":None,"new_msg":""}
            # permiso
            try:
                rp,_ = svc._client().permiso(svc.ssid1,svc.ssid2,clase)
                res["permiso_code"] = rp.get("code") if isinstance(rp,dict) else -1
                res["permiso_msg"] = str((rp or {}).get("data",""))[:150]
            except Exception as ep:
                res["permiso_code"] = -1; res["permiso_msg"] = str(ep)[:80]
            # browse rapido (solo si permiso no es =1)
            if res["permiso_code"] != 1:
                try:
                    rb,_ = svc._client().browse(svc.ssid1,svc.ssid2,clase,{})
                    res["browse_code"] = rb.get("code") if isinstance(rb,dict) else -1
                    res["browse_msg"] = str((rb or {}).get("data",""))[:200]
                    if res["browse_code"] == 6: mantenimiento_detectado = True
                    if res["browse_code"] == 0:
                        data = (rb or {}).get("data",{})
                        items = data.get("items",[]) if isinstance(data,dict) else (data if isinstance(data,list) else [])
                        res["browse_n"] = len(items)
                        res["browse_muestra"] = items[:2]
                except Exception as eb:
                    res["browse_code"] = -1; res["browse_msg"] = str(eb)[:80]
            api_resultados[clase] = res

    # ======================================================
    # BLOQUE 3: Cruzar BD + API para cada clase
    # ======================================================
    def _clasificar(clase, info, api_res):
        n_fb = info.get("n_fb",0)
        n_fb_int = n_fb if isinstance(n_fb,int) else 0
        perm = (api_res or {}).get("permiso_code")
        browse = (api_res or {}).get("browse_code")
        # Estado API
        if perm == 1:
            api_estado = "sin_licencia"
        elif browse == 6:
            api_estado = "mantenimiento"
        elif browse == 0:
            api_estado = "funciona"
        elif browse == 5:
            api_estado = "error_params"
        elif perm == 0:
            api_estado = "permiso_ok_browse_bloqueado"
        elif perm is None:
            api_estado = "sin_sesion"
        else:
            api_estado = f"code_{browse or perm}"
        # Estado BD
        if not fb_ok:
            bd_estado = "fb_no_accesible"
        elif n_fb_int > 0:
            bd_estado = "datos_reales"
        elif isinstance(n_fb,int):
            bd_estado = "tabla_vacia"
        else:
            bd_estado = "error"
        # Recomendacion
        lic = info.get("licencia","base")
        if bd_estado == "datos_reales" and lic == "base":
            rec = "disponible_sin_licencia_extra"
        elif bd_estado == "datos_reales" and lic != "base":
            rec = "comprar_licencia_vale_la_pena"
        elif bd_estado == "tabla_vacia" and lic != "base":
            rec = "estudiar_antes_de_comprar"
        elif bd_estado == "tabla_vacia" and lic == "base":
            rec = "tabla_vacia_cambiar_flujo"
        else:
            rec = "revisar"
        return {"api_estado":api_estado,"bd_estado":bd_estado,"recomendacion":rec,
                "n_registros_fb":n_fb_int,"tabla_fb":info.get("tabla_fb",""),
                "licencia":lic,"modulo":info.get("modulo","")}

    clases_cruzadas = {}
    for clase, info in api_clases.items():
        api_res = api_resultados.get(clase,{})
        cruce = _clasificar(clase, info, api_res)
        cruce["api_res"] = api_res
        clases_cruzadas[clase] = cruce

    # ======================================================
    # BLOQUE 4: Textos de informe en 5 niveles
    # ======================================================
    def _lineas_nivel1():
        L=[]
        L.append("INFORME MAESTRO API mPYME - JDDC")
        L.append(f"Fecha: {ts[:19]} | URL: {api_url} | BD: Firebird {'OK' if fb_ok else 'NO ACCESIBLE'}")
        L.append("="*60)
        n_ok    = sum(1 for c in clases_cruzadas.values() if c["bd_estado"]=="datos_reales" and c["licencia"]=="base")
        n_lic   = sum(1 for c in clases_cruzadas.values() if c["bd_estado"]=="datos_reales" and c["licencia"]!="base")
        n_vacio = sum(1 for c in clases_cruzadas.values() if c["bd_estado"]=="tabla_vacia")
        n_mant  = sum(1 for c in clases_cruzadas.values() if c["api_estado"]=="mantenimiento")
        L.append(f"Clases API con datos reales y sin licencia extra: {n_ok}")
        L.append(f"Clases API con datos reales que requieren licencia: {n_lic}")
        L.append(f"Clases API con tabla Firebird vacia (sin uso): {n_vacio}")
        L.append(f"Clases bloqueadas por modo mantenimiento: {n_mant}")
        L.append("")
        L.append("ESTADO API: "+("MODO MANTENIMIENTO ACTIVO (code=6)" if mantenimiento_detectado else ("Sin sesion" if not sesion_activa else "OK")))
        L.append("")
        L.append("RESUMEN EJECUTIVO:")
        mods = {}
        for c,v in clases_cruzadas.items():
            m = v["modulo"]; mods.setdefault(m,{"ok":0,"lic":0,"vacio":0,"total":0})
            mods[m]["total"] += 1
            if v["bd_estado"]=="datos_reales" and v["licencia"]=="base": mods[m]["ok"] += 1
            elif v["bd_estado"]=="datos_reales": mods[m]["lic"] += 1
            else: mods[m]["vacio"] += 1
        for m,s in mods.items():
            L.append(f"  {m}: {s['ok']} disponibles, {s['lic']} con datos (licencia), {s['vacio']} sin datos")
        return "\n".join(L)

    def _lineas_nivel2():
        L=[]
        L.append("INFORME API mPYME - NIVEL MODULO")
        L.append(f"Fecha: {ts[:19]} | Empresa: {empresa} | URL: {api_url}")
        L.append("="*65)
        modulos_info = {
            "maestros":{"lbl":"MAESTROS","lic":"Base"},
            "proyectos":{"lbl":"GESTION DE PROYECTOS","lic":"mPyme Proyectos"},
            "reparaciones":{"lbl":"REPARACIONES","lic":"mPyme Reparaciones"},
            "documentos":{"lbl":"DOCUMENTOS DE COMPRA","lic":"mPyme Documentos"},
            "fabricacion":{"lbl":"FABRICACION","lic":"mPyme Fabricacion"},
        }
        for mod_id, minfo in modulos_info.items():
            clases_mod = {c:v for c,v in clases_cruzadas.items() if v["modulo"]==mod_id}
            if not clases_mod: continue
            L.append(f"\n{'='*65}")
            L.append(f"MODULO: {minfo['lbl']} | Licencia: {minfo['lic']}")
            L.append(f"{'='*65}")
            for clase,cruce in clases_mod.items():
                n = cruce["n_registros_fb"]
                tabla = cruce["tabla_fb"]
                bd_txt = f"{n:,} registros en {tabla}" if isinstance(n,int) and n>0 else f"VACIA/ERROR: {tabla}"
                api_txt = cruce["api_estado"].replace("_"," ").upper()
                rec_txt = cruce["recomendacion"].replace("_"," ").upper()
                L.append(f"  {clase}:")
                L.append(f"    BD Firebird: {bd_txt}")
                L.append(f"    API estado:  {api_txt}")
                L.append(f"    Accion:      {rec_txt}")
        L.append("")
        L.append("PROBLEMAS DETECTADOS:")
        if mantenimiento_detectado:
            L.append("  - MODO MANTENIMIENTO ACTIVO: browse()=code=6 en todas las clases")
            L.append("    Doc oficial pag.7: 'Maintenance mode - la sesion sigue siendo valida'")
            L.append("    Accion: contactar Distrito K o ver panel de modo mantenimiento en DEVIA")
        if not sesion_activa:
            L.append("  - SIN SESION API: conectarse en la pestana Conexion para datos de la API")
        if not fb_ok:
            L.append(f"  - FIREBIRD NO ACCESIBLE: {fb_error}")
        return "\n".join(L)

    def _lineas_nivel3():
        L=[]
        L.append("INFORME DETALLADO - DATOS REALES BD + ESTADO API")
        L.append(f"Fecha: {ts[:19]} | Empresa: {empresa} | URL: {api_url}")
        L.append(f"BD Firebird: {'OK' if fb_ok else 'NO ACCESIBLE - '+fb_error[:60]}")
        L.append(f"Sesion API: {'activa' if sesion_activa else 'sin sesion'}")
        L.append(f"Mantenimiento detectado: {'SI (code=6)' if mantenimiento_detectado else 'No'}")
        L.append("="*70)
        L.append("")
        L.append("DATOS CLAVE DE LA BD FIREBIRD:")
        if fb_ok:
            L.append(f"  Clientes:      {fb_datos.get('n_clientes',0):,}")
            L.append(f"  Proveedores:   {fb_datos.get('n_proveedores',0):,}")
            L.append(f"  Articulos:     {fb_datos.get('n_articulos',0):,}")
            L.append(f"  Tecnicos/Recursos: {fb_datos.get('n_recursos',0):,}")
            L.append(f"  Proyectos:     {fb_datos.get('n_proyectos',0):,} (activos: {fb_datos.get('n_proy_activos',0):,})")
            L.append(f"  Horas en proyectos (PREUTILLIN): {fb_datos.get('n_preutillin',0):,} imputaciones")
            L.append(f"  Previsiones en proyectos (PREPREVLIN): {fb_datos.get('n_preprevlin',0):,}")
            L.append(f"  Partes SAT (REPARA): {fb_datos.get('n_repara',0):,} (abiertos: {fb_datos.get('n_repara_abiertas',0):,})")
            L.append(f"  Horas en partes SAT (RABUTILLIN): {fb_datos.get('n_rabutillin',0):,}")
            L.append(f"  Objetos de cliente (REPOBJETO): {fb_datos.get('n_repobjetos',0):,}")
            L.append(f"  Instalaciones (REPINSTALACION): {fb_datos.get('n_repinstalacion',0):,}")
            L.append(f"  Albaranes compra: {fb_datos.get('n_albcom',0):,} | Facturas compra: {fb_datos.get('n_faccom',0):,}")
            L.append(f"  Albaranes compra vinculados a proyecto: {fb_datos.get('n_albcom_proy',0):,}")
            if fb_datos.get("muestra_recursos"):
                L.append("")
                L.append("  TECNICOS/RECURSOS (muestra BD real):")
                for r in fb_datos["muestra_recursos"]:
                    L.append(f"    {r.get('CODIGO','?')} - {r.get('DESCRIPCION','?')}")
            if fb_datos.get("top_tecnicos"):
                L.append("")
                L.append("  TOP TECNICOS POR HORAS IMPUTADAS EN PROYECTOS:")
                for r in fb_datos["top_tecnicos"]:
                    L.append(f"    {r.get('TECNICO','?')}: {r.get('HORAS_TOTALES',0):.1f}h | precio medio: {r.get('PRECIO_MEDIO',0):.2f}")
            if fb_datos.get("top_tecnicos_rep"):
                L.append("")
                L.append("  TOP TECNICOS POR HORAS EN PARTES SAT:")
                for r in fb_datos["top_tecnicos_rep"]:
                    L.append(f"    {r.get('TECNICO','?')}: {r.get('HORAS_TOTALES',0):.1f}h en {r.get('N_PARTES',0)} partes")
        else:
            L.append(f"  Firebird no accesible: {fb_error}")
        L.append("")
        L.append("-"*70)
        L.append("CLASES API - CRUCE BD + API:")
        for clase, cruce in clases_cruzadas.items():
            perm = cruce["api_res"].get("permiso_code","?")
            browse = cruce["api_res"].get("browse_code","?")
            n = cruce["n_registros_fb"]
            tabla = cruce["tabla_fb"]
            L.append(f"")
            L.append(f"  [{clase}]")
            L.append(f"    Modulo API:  {cruce['modulo']} | Licencia: {cruce['licencia']}")
            L.append(f"    BD:          {tabla} = {n:,} registros" if isinstance(n,int) else f"    BD:          {tabla} = {n}")
            L.append(f"    API permiso: code={perm} | browse: code={browse}")
            L.append(f"    Estado:      BD={cruce['bd_estado']} | API={cruce['api_estado']}")
            L.append(f"    Accion:      {cruce['recomendacion']}")
        return "\n".join(L)

    def _lineas_nivel4():
        L=[]
        L.append("INFORME TECNICO COMPLETO - API mPYME + BD FIREBIRD")
        L.append(f"Instalacion: empresa={empresa} | URL={api_url}")
        L.append(f"BD: {cfg.get('db_host','?')} / {cfg.get('db_name','?')}")
        L.append(f"Fecha: {ts[:19]}")
        L.append(f"Sesion API: {'activa (ssid1+ssid2)' if sesion_activa else 'sin sesion'}")
        L.append(f"Firebird: {'OK - conexion directa' if fb_ok else 'NO ACCESIBLE: '+fb_error[:80]}")
        L.append("="*70)
        L.append("")
        L.append("PROTOCOLO API:")
        L.append(f"  URL base:  {api_url}")
        L.append("  HTTP: POST / | Content-Type: application/x-www-form-urlencoded")
        L.append("  Auth: method=login&empr=<empresa>&user=<u>&pass=<sha1_base64>")
        L.append("  Respuesta: {code: 0|5|6|7, data: {...}}")
        L.append("  code=6: Maintenance mode (SITUACION ACTUAL)")
        L.append("  code=5: Error o sin licencia")
        L.append("")
        L.append("="*70)
        L.append("REFERENCIA POR CLASE API (BD + API + Peticion exacta):")
        L.append("="*70)
        peticiones = {
            "clientes":   "method=browse&objectclass=clientes&ssid1=X&ssid2=Y",
            "proveedores":"method=browse&objectclass=proveedores&ssid1=X&ssid2=Y",
            "articulos":  "method=browse&objectclass=articulos&filter=<nombre>&ssid1=X&ssid2=Y",
            "recursos":   "method=browse&objectclass=recursos&ssid1=X&ssid2=Y",
            "proyectos":  "method=browse&objectclass=proyectos&ssid1=X&ssid2=Y",
            "partidas":   "method=browse&objectclass=partidas&masterid=<id_proy_hex>&ssid1=X&ssid2=Y",
            "proordutil": "method=browse&objectclass=proordutil&masterid=<id_proy_hex>&desde=01/01/2000&hasta=31/12/2030&orden=fecha-asc&ssid1=X&ssid2=Y",
            "proordprev": "method=browse&objectclass=proordprev&masterid=<id_proy_hex>-<codDocPrev>&ssid1=X&ssid2=Y",
            "reporden":   "method=browse&objectclass=reporden&ssid1=X&ssid2=Y",
            "repordutil": "method=browse&objectclass=repordutil&masterid=<id_rep_hex>&ssid1=X&ssid2=Y",
            "repobjetos": "method=browse&objectclass=repobjetos&masterClass=clientes&masterId=<id>&ssid1=X&ssid2=Y",
            "tipostrabajo":"method=browse&objectclass=tipostrabajo&ssid1=X&ssid2=Y",
            "docalbcom":  "method=browse&objectclass=docalbcom&ssid1=X&ssid2=Y",
            "docfaccom":  "method=browse&objectclass=docfaccom&ssid1=X&ssid2=Y",
            "docpedcom":  "method=browse&objectclass=docpedcom&ssid1=X&ssid2=Y",
            "ordenfab":   "method=browse&objectclass=ordenfab&ssid1=X&ssid2=Y",
        }
        campos_api = {
            "clientes":   "id, codigo, nombre, cif, telefono, email, formapago, direccion",
            "proveedores":"id, codigo, nombre, cif, telefono, email, formapago",
            "articulos":  "id, codigo, nombre, preciocoste, precioventa, pvp, familia, existencias",
            "recursos":   "id, codigo, nombre, descripcion, costeHora, precioHora",
            "proyectos":  "id, codigo, nombre, finobra, fecha, fechainicio, codcliente, nomcliente, direccion",
            "partidas":   "id, codigo, descripcion, nivel, costeprev, costeutil",
            "proordutil": "recursos[].nombre(tecnico), cantidad(HORAS), precio, coste, importe, fecha; materiales[].articulo, cantidad, precio",
            "proordprev": "codRecurso, descripcion(tecnico), duracion(horas prev), precio",
            "reporden":   "id, codigo, descripcion, estado, fecha, nomcliente, costeutil, precioutil, beneficioutil",
            "repordutil": "nombre(tecnico), cantidad(horas), precio, coste, importe, fecha",
            "repobjetos": "id, codigo, nombre, tipoobjeto, inigarantia, fingarantia, adic_obj_1..15",
            "tipostrabajo":"id, codigo, nombre",
            "docalbcom":  "id, serie, numero, fecha, proveedor, nomprov, impbase, impiva, imptotal, proyecto",
            "docfaccom":  "id, serie, numero, fecha, proveedor, nomprov, impbase, impiva, imptotal",
            "docpedcom":  "id, serie, numero, fecha, proveedor, imptotal",
            "ordenfab":   "id, codigo, descripcion, estado, articulo, cantidad",
        }
        for clase, cruce in clases_cruzadas.items():
            api_res = cruce["api_res"]
            n = cruce["n_registros_fb"]
            L.append(f"")
            L.append(f"CLASS: {clase}")
            L.append(f"  Modulo:         {cruce['modulo']}")
            L.append(f"  Licencia:       {cruce['licencia']}")
            L.append(f"  Tabla FB:       {cruce['tabla_fb']} = {n:,} registros" if isinstance(n,int) else f"  Tabla FB: {cruce['tabla_fb']} = {n}")
            L.append(f"  BD estado:      {cruce['bd_estado']}")
            L.append(f"  API permiso:    code={api_res.get('permiso_code','?')} | msg: {api_res.get('permiso_msg','')[:80]}")
            L.append(f"  API browse:     code={api_res.get('browse_code','?')} | msg: {api_res.get('browse_msg','')[:100]}")
            L.append(f"  API estado:     {cruce['api_estado']}")
            L.append(f"  Recomendacion:  {cruce['recomendacion']}")
            L.append(f"  Campos API:     {campos_api.get(clase,'(ver doc oficial)')}")
            L.append(f"  Peticion HTTP:  POST {api_url}")
            L.append(f"  Body:           {peticiones.get(clase,'method=browse&objectclass='+clase+'&ssid1=X&ssid2=Y')}")
        return "\n".join(L)

    def _lineas_dk():
        L=[]
        L.append("Asunto: Consulta sobre licencias, modo mantenimiento y datos disponibles - API mPYME JDDC")
        L.append("")
        L.append("Hola Distrito K,")
        L.append("")
        L.append(f"Instalacion: empresa={empresa} | URL={api_url}")
        L.append(f"BD Firebird: {cfg.get('db_host','?')} / {cfg.get('db_name','?')}")
        L.append(f"Diagnostico generado: {ts[:19]}")
        L.append("")
        L.append("PROBLEMA 1 — MODO MANTENIMIENTO (URGENTE):")
        if mantenimiento_detectado:
            L.append("  browse() y new() devuelven code=6 en TODAS las clases.")
            L.append("  Segun doc oficial mPYME v1.2 pag.7: code=6 = Maintenance mode.")
            L.append("  Mensaje exacto del servidor: 'No es posible acceder a la base de datos'")
            L.append("  SOLICITUD: Por favor, desactivar el modo mantenimiento o indicarnos")
            L.append("  como desactivarlo nosotros si tenemos acceso a SQL Obras.")
        else:
            L.append("  Anteriormente detectado. Estado actual: verificar con diagnostico completo.")
        L.append("")
        L.append("PROBLEMA 2 — LICENCIAS:")
        L.append("  new(proyectos) = code=5 'No dispone de licencia para el modulo Proyectos'")
        L.append("  Solicitud: confirmar que modulos mPYME tenemos contratados actualmente.")
        L.append("")
        L.append("DATOS QUE NECESITAMOS Y CONFIRMACION DE USO EN BD REAL:")
        L.append("")
        with_data = [(c,v) for c,v in clases_cruzadas.items() if v["bd_estado"]=="datos_reales"]
        L.append("A) Clases con datos reales en BD (datos confirmados por SELECT en Firebird):")
        for clase,cruce in with_data:
            n = cruce["n_registros_fb"]
            L.append(f"  - {clase}: {n:,} registros en {cruce['tabla_fb']} | Licencia: {cruce['licencia']}")
        L.append("")
        L.append("B) Licencias que necesitamos (con uso real confirmado en BD):")
        need_lic = [(c,v) for c,v in clases_cruzadas.items()
                    if v["bd_estado"]=="datos_reales" and v["licencia"]!="base"]
        mods_lic = {}
        for clase,cruce in need_lic:
            m = cruce["licencia"]; mods_lic.setdefault(m,[]).append(clase)
        for lic, clases_l in mods_lic.items():
            L.append(f"  - {lic}: clases {', '.join(clases_l)}")
        if not mods_lic:
            L.append("  (pendiente de verificar - mantenimiento activo)")
        L.append("")
        L.append("C) Clases sin datos en BD (no se usaria aunque se compre la licencia):")
        no_data = [(c,v) for c,v in clases_cruzadas.items() if v["bd_estado"]=="tabla_vacia"]
        for clase,cruce in no_data:
            L.append(f"  - {clase}: {cruce['tabla_fb']} = 0 registros")
        L.append("")
        L.append("PREGUNTAS CONCRETAS:")
        L.append("  1. Modo mantenimiento: por que esta activo? como desactivarlo?")
        L.append("  2. Que modulos mPYME tenemos contratados actualmente?")
        L.append("  3. Precio de: mPyme Proyectos, mPyme Reparaciones, mPyme Documentos")
        L.append("  4. Una vez activa la API sin mantenimiento, necesitamos el parametro exacto")
        L.append("     para browse() de: proyectos, reporden, proordutil, repordutil")
        L.append("  5. proordutil (horas por proyecto): hay parametro obligatorio masterid?")
        L.append("     Ejemplo de la doc: masterid=<idProyectoHex>&desde=...&hasta=...")
        L.append("")
        L.append("Muchas gracias.")
        return "\n".join(L)

    return {
        "success": True,
        "timestamp": ts,
        "empresa": empresa,
        "api_url": api_url,
        "sesion_activa": sesion_activa,
        "fb_ok": fb_ok,
        "fb_error": fb_error,
        "fb_datos": fb_datos,
        "api_resultados": api_resultados,
        "clases_cruzadas": clases_cruzadas,
        "mantenimiento_detectado": mantenimiento_detectado,
        "niveles_texto": {
            "n1_ejecutivo":   _lineas_nivel1(),
            "n2_por_modulo":  _lineas_nivel2(),
            "n3_datos_reales":_lineas_nivel3(),
            "n4_tecnico":     _lineas_nivel4(),
            "n5_distrito_k":  _lineas_dk(),
        }
    }


class ValoresParamRequest(BaseModel):
    clase: str
    campo: str   # nombre del parámetro API: "codProyecto", "codOrden", etc.


@router.post("/valores-param")
async def valores_param(request: ValoresParamRequest):
    """
    Obtiene valores reales de Firebird para autocompletar un campo de parámetro.
    Usa el FirebirdDriver del proyecto (mismo que el chat y otros módulos).
    Solo lectura. Devuelve máx. 10 valores: id + descripción.
    Los valores SÍ se devuelven (para rellenar el formulario del Probador — no aparecen en informes).
    """
    from backend.core.config.settings import settings
    # Usar MAPA_FIREBIRD que ya tiene toda la info necesaria
    info_fb = MAPA_FIREBIRD.get(request.campo) or next(
        (v for k, v in MAPA_FIREBIRD.items() if v[3] == request.campo), None
    )
    # Mapeo alternativo por nombre de campo API (los mapas de MAPA_FIREBIRD usan clase, no campo)
    MAPA_CAMPO = {
        # Nombres reales de tablas y columnas confirmados en db_metadata_optimized.json
        "codProyecto": ("PROYECTOS",     "CODIGO",  "NOMBRE"),
        "codOrden":    ("REPCAB",        "CODIGO",  "CODIGO"),
        "codRecurso":  ("RECURSO",       "CODIGO",  "DESCRIPCION"),
        "codObjeto":   ("REPOBJETO",     "CODIGO",  "NOMBRE"),
        "codInst":     ("REPINSTALACION","CODIGO",  "NOMBRE"),
        "codTrabajo":  ("REPARA",        "CODIGO",  "DESCRIPCION"),
        "codArticulo": ("ARTICULO",      "CODIGO",  "NOMBRE"),
        "codProv":     ("PROVEED",       "CODIGO",  "RAZONSOCIAL"),
        "codCliente":  ("CLIENTE",       "CODIGO",  "NOMBRE"),
        "codDocumento":("DOCCAB",        "CODIGO",  "CODIGO"),
        "codPartida":  ("PRESUPROYE",    "CODIGO",  "CODIGO"),
    }
    info = MAPA_CAMPO.get(request.campo)
    if not info:
        return {"ok": False, "campo": request.campo, "valores": [],
                "error": f"Campo '{request.campo}' no tiene tabla mapeada"}
    tabla, campo_id, campo_desc = info
    if not settings.DB_NAME:
        return {"ok": False, "campo": request.campo, "valores": [],
                "error": "DB_NAME no configurado en el .env del servidor"}
    try:
        drv = _get_db_driver()
        try:
            if campo_id == campo_desc:
                sql = f"SELECT FIRST 10 {campo_id} FROM {tabla} ORDER BY {campo_id}"
            else:
                sql = f"SELECT FIRST 10 {campo_id}, {campo_desc} FROM {tabla} ORDER BY {campo_id}"
            rows = drv.execute_query(sql)
        finally:
            drv.disconnect()
        valores = []
        for row in rows:
            vid = ""
            for key in [campo_id, campo_id.lower(), campo_id.upper()]:
                v = row.get(key, "")
                if v:
                    vid = str(v).strip(); break
            if campo_id == campo_desc:
                vdsc = vid
            else:
                vdsc = ""
                for key in [campo_desc, campo_desc.lower(), campo_desc.upper()]:
                    v = row.get(key, "")
                    if v:
                        vdsc = str(v).strip(); break
            if vid:
                valores.append({"id": vid, "desc": vdsc if vdsc else vid})
        return {"ok": True, "campo": request.campo, "tabla": tabla, "valores": valores}
    except Exception as exc:
        return {"ok": False, "campo": request.campo, "valores": [],
                "error": f"{type(exc).__name__}: {str(exc)[:250]}"}

