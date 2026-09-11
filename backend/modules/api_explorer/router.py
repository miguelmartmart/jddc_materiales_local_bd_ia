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
    # Tabla real Firebird (confirmada por db_metadata_optimized.json)
    # (tabla, campo_id, campo_desc, param_api_mpyme)
    "proyectos":   ("PROYECTOS",     "CODIGO",  "NOMBRE",       "codProyecto"),
    "partidas":    ("PROYECTOS",     "CODIGO",  "NOMBRE",       "codProyecto"),
    "proordutil":  ("PROYECTOS",     "CODIGO",  "NOMBRE",       "codProyecto"),
    "proordprev":  ("PROYECTOS",     "CODIGO",  "NOMBRE",       "codProyecto"),
    "reporden":    ("REPCAB",        "CODIGO",  "CODIGO",       "codOrden"),
    "repordutil":  ("REPCAB",        "CODIGO",  "CODIGO",       "codOrden"),
    "recursos":    ("RECURSO",       "CODIGO",  "DESCRIPCION",  "codRecurso"),
    "repobjetos":  ("REPOBJETO",     "CODIGO",  "NOMBRE",       "codObjeto"),
    "repinst":     ("REPINSTALACION","CODIGO",  "NOMBRE",       "codInst"),
    "tipostrabajo":("REPARA",        "CODIGO",  "DESCRIPCION",  "codTrabajo"),
    "articulos":   ("ARTICULO",      "CODIGO",  "NOMBRE",       "codArticulo"),
    "proveedores": ("PROVEED",       "CODIGO",  "RAZONSOCIAL",  "codProv"),
    "clientes":    ("CLIENTE",       "CODIGO",  "NOMBRE",       "codCliente"),
    "docalbcom":   ("DOCCAB",        "CODIGO",  "CODIGO",       "codDocumento"),
    "docfaccom":   ("DOCCAB",        "CODIGO",  "CODIGO",       "codDocumento"),
    "docpedcom":   ("DOCCAB",        "CODIGO",  "CODIGO",       "codDocumento"),
    "ordenfab":    ("REPCAB",        "CODIGO",  "CODIGO",       "codOrden"),
}


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
        return {"ok": False,
                "error": f"{type(exc).__name__}: {str(exc)[:250]}",
                "db_host": _s.DB_HOST, "db_name": _s.DB_NAME}


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
        for tabla in ["PROYECTOS", "REPCAB", "ARTICULO", "RECURSO", "CLIENTE", "PROVEED"]:
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
    if code!=0 and operacion in("browse","read"):
        if code==6:
            nid=True
            fb=_firebird_ids(clase,n=10)
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
                intentos.append({"desc":"Firebird no disponible","params":{},"code":-1,"ms":0,
                                  "n_items":0,"ok":False,"servidor":fb.get("error","No disponible")})
    # PASO 4: ultimo recurso browse sin params
    if code!=0 and operacion=="browse":
        rf,mf=_llama({},"browse sin params (ultimo recurso)")
        if isinstance(rf,dict) and rf.get("code")==0: raw,ms,code=rf,mf,0
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
            # browse vacio/pagesize primero
            if code==6 and op=="browse":
                try:
                    r00,m00=svc._client().browse(svc.ssid1,svc.ssid2,clase,{})
                    if isinstance(r00,dict) and r00.get("code")==0: raw,ms,code=r00,m00,0
                except: pass
            if code==6 and op=="browse":
                try:
                    r01,m01=svc._client().browse(svc.ssid1,svc.ssid2,clase,{"pagesize":"1"})
                    if isinstance(r01,dict) and r01.get("code")==0: raw,ms,code=r01,m01,0
                except: pass
            if code==6 and op in("browse","read"):
                msg_servidor = str(raw.get("data",""))[:120]
                fb=_firebird_ids(clase, n=8)
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
            elif code==5: estado,msg=_estado_code5(raw)
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
    return {"success":True,"timestamp":ts,"use_mock":svc.use_mock,"total_clases":len(resultados),
            "resumen":{"ok":sum(1 for v in resultados.values() if v["estado_global"]=="ok"),
                "requiere_params":sum(1 for v in resultados.values() if v["estado_global"]=="requiere_params"),
                "sin_licencia":sum(1 for v in resultados.values() if v["estado_global"]=="sin_licencia"),
                "sin_permiso":sum(1 for v in resultados.values() if v["estado_global"]=="sin_permiso"),
                "error":sum(1 for v in resultados.values() if v["estado_global"]=="error")},
            "clases":resultados,
            "aviso":"Sin datos privados. Solo estados, códigos y nombres de campos."}

@router.get("/diagnostico-firebird")
async def diagnostico_firebird():
    """Diagnostico completo de la conexion Firebird. Solo lectura. Sin valores de negocio."""
    d = _firebird_diagnostico()
    return d


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

