"""Servicio del modulo API Explorer para DEVIA. Sesion stateful + mock/real."""
import logging, time, random, uuid, os, json, re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from backend.core.config.settings import settings

# ── Archivos de persistencia (todos en data/ — sobreviven reinicios) ──────────
_DATA_DIR            = Path(__file__).parent / "data"
_DISCOVER_CACHE_FILE = _DATA_DIR / "_discover_cache.json"
_HISTORY_FILE        = _DATA_DIR / "_history.json"
_MATRIX_FILE         = _DATA_DIR / "_matrix.json"
_SONDAS_FILE         = _DATA_DIR / "_sondas.json"


def _guardar_json(path: Path, data) -> None:
    """Escribe JSON a disco de forma segura (escritura atómica básica)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.warning(f"[api_explorer] No se pudo guardar {path.name}: {e}")


def _cargar_json(path: Path, default):
    """Carga JSON desde disco. Devuelve default si no existe o hay error."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[api_explorer] No se pudo cargar {path.name}: {e}")
    return default

logger = logging.getLogger(__name__)

CLASES_POR_MODULO = {
    "Gestion de Proyectos": {"proyectos":["browse","read"],"partidas":["browse","read"],"proordutil":["browse","read","new","edit","write","cancel"],"proordprev":["browse","read"]},
    "Reparaciones": {"reporden":["browse","read","new","write","cancel"],"repobjetos":["browse","read"],"repinst":["browse","read"],"tipostrabajo":["browse"],"repordutil":["browse","new","write","cancel"]},
    "Maestros": {"articulos":["browse","read"],"recursos":["browse","read"],"proveedores":["browse"],"clientes":["browse"]},
    "Documentos de Compra": {"docalbcom":["browse","read","imputaPro"],"docfaccom":["browse","read","imputaPro"],"docpedcom":["browse","imputaPro"]},
    "Fabricacion": {"ordenfab":["browse"]},
}
ALL_OBJECT_CLASSES = ["proyectos","partidas","proordutil","proordprev","reporden","repobjetos","repinst","tipostrabajo","repordutil","articulos","recursos","proveedores","clientes","docalbcom","docfaccom","docpedcom","ordenfab"]
RIESGO_ESCRITURA = 2
OPERACIONES_RIESGO = {"browse":0,"read":0,"permiso":0,"info":0,"new":1,"edit":1,"cancel":1,"write":2,"imputaPro":2,"exec":2,"delete":3}
NOTAS_DOC = {
    ("proordutil","write"):"Tras write el servidor asigna codDocumento definitivo.",
    ("proordutil","new"):"No persiste hasta write. Usar cancel para descartar.",
    ("docalbcom","imputaPro"):"Documentado explicitamente. Compra computa como material consumido.",
    ("docfaccom","imputaPro"):"Documentado para facturas de compra.",
    ("docpedcom","imputaPro"):"DOC NO CONCLUYENTE: usa 'previsiblemente'. Verificar empiricamente.",
    ("repordutil","write"):"Ejemplo documentado: codRecurso, horas, coste, precio, duracion.",
}
NOTAS_SEGURIDAD = {
    ("proordutil","write"):"ESCRITURA REAL: Modifica SQL Obras definitivamente.",
    ("repordutil","write"):"ESCRITURA REAL: Modifica SQL Obras definitivamente.",
    ("docalbcom","imputaPro"):"ESCRITURA REAL: Vincula compra como coste real del proyecto.",
    ("docfaccom","imputaPro"):"ESCRITURA REAL: Vincula factura como coste real.",
    ("reporden","cancel"):"Cancela/anula una orden de reparacion.",
    ("docpedcom","imputaPro"):"ESCRITURA REAL con documentacion no concluyente.",
}

class MockApiClient:
    PROYECTOS=[{"codProyecto":"25/184","descripcion":"Hospital Murcia","estado":"activo"},{"codProyecto":"25/185","descripcion":"Oficinas Murcia","estado":"activo"},{"codProyecto":"24/091","descripcion":"Nave Industrial","estado":"cerrado"}]
    PARTIDAS={"25/184":[{"codPartida":"01","descripcion":"Obra Civil"},{"codPartida":"03","descripcion":"Climatizacion"},{"codPartida":"03.02","descripcion":"Unidades interiores"}]}
    UTILIZADOS=[{"codDocumento":"U-001","codPartida":"03.02","codArticulo":"1#100142","descripcion":"Tubo cobre","cantidad":18.0,"coste":3.20,"precio":5.50},{"codDocumento":"U-002","codPartida":"03.01","codArticulo":"R-INST01","descripcion":"Instalador HVAC","cantidad":6.5,"coste":22.0,"precio":35.0}]
    PERMISOS={"proyectos":{"browse":True,"read":True,"new":False,"write":False},"partidas":{"browse":True,"read":True},"proordutil":{"browse":True,"read":True,"new":True,"edit":True,"write":True,"cancel":True,"delete":False},"proordprev":{"browse":True,"read":True},"reporden":{"browse":True,"read":True,"new":True,"write":True,"cancel":True},"repordutil":{"browse":True,"read":True,"new":True,"write":True,"cancel":True},"repobjetos":{"browse":True,"read":True},"repinst":{"browse":True,"read":True},"tipostrabajo":{"browse":True},"articulos":{"browse":True,"read":True},"recursos":{"browse":True,"read":True},"proveedores":{"browse":True,"read":True},"clientes":{"browse":True,"read":True},"docalbcom":{"browse":True,"read":True,"imputaPro":True},"docfaccom":{"browse":True,"read":True,"imputaPro":True},"docpedcom":{"browse":True,"imputaPro":False},"ordenfab":{"browse":False}}

    def __init__(self): self._objects:Dict[str,Any]={}
    def _ms(self)->float: ms=random.uniform(80,350); time.sleep(ms/1000); return ms
    def _ok(self,d)->Tuple[dict,float]: return {"code":0,**d}, self._ms()
    def login(self,e,u,p):
        if not(e and u and p): return {"code":5,"mensaje":"Params incompletos"},self._ms()
        return self._ok({"ssid1":f"MOCK_{uuid.uuid4().hex[:8].upper()}","ssid2":f"MOCK_{uuid.uuid4().hex[:8].upper()}"})
    def logout(self,s1,s2): return self._ok({"mensaje":"Sesion cerrada"})
    def permiso(self,s1,s2,cls): return self._ok({"objectClass":cls,**self.PERMISOS.get(cls,{"browse":False})})
    def info(self,s1,s2,cls): return self._ok({"objectClass":cls,"fields":[{"nombre":"id","tipo":"str"}]})

    def browse(self,s1,s2,cls,params):
        BROWSE_DATA={"proyectos":{"items":self.PROYECTOS,"total":3},"partidas":{"items":self.PARTIDAS.get(params.get("codProyecto",""),[]),"total":0},"proordutil":{"items":self.UTILIZADOS,"total":2},"proordprev":{"items":[],"total":0},"reporden":{"items":[{"codOrden":"REP-2026-001","descripcion":"Averia compresor","estado":"abierta"}],"total":1},"repobjetos":{"items":[{"codObjeto":"OBJ-001","descripcion":"UTA-A"}],"total":1},"repinst":{"items":[{"codInst":"INST-01","descripcion":"Planta 1"}],"total":1},"tipostrabajo":{"items":[{"codTipo":"MANT","descripcion":"Mantenimiento"},{"codTipo":"AVAR","descripcion":"Averia"}],"total":2},"repordutil":{"items":[],"total":0},"articulos":{"items":[{"codArticulo":"1#100142","descripcion":"Tubo cobre","precio":5.50}],"total":1},"recursos":{"items":[{"codRecurso":"R-INST01","descripcion":"Instalador HVAC"}],"total":1},"proveedores":{"items":[{"codProv":"DAIKIN","nombre":"Daikin Spain S.A."}],"total":1},"clientes":{"items":[{"codCliente":"CLI-001","nombre":"Hospital Reina Sofia"}],"total":1},"docalbcom":{"items":[{"codDocumento":"ALB-2026-0101","proveedor":"Daikin Spain S.A.","total":2500.0}],"total":1},"docfaccom":{"items":[],"total":0},"docpedcom":{"items":[],"total":0}}
        dm=BROWSE_DATA.get(cls)
        if dm is None: return {"code":1,"mensaje":"Sin licencia (mock)"},self._ms()
        return self._ok(dm)

    def read(self,s1,s2,cls,params):
        if cls=="proyectos":
            cod=params.get("codProyecto",""); item=next((p for p in self.PROYECTOS if p["codProyecto"]==cod),None)
            ms=self._ms(); return ({"code":0,**item} if item else {"code":10,"mensaje":f"No encontrado: {cod}"}),ms
        if cls=="proordutil":
            cod=params.get("codDocumento",""); item=next((u for u in self.UTILIZADOS if u["codDocumento"]==cod),None)
            ms=self._ms(); return ({"code":0,**item} if item else {"code":10,"mensaje":"No encontrado"}),ms
        return self._ok({"nota":f"read mock {cls}","params":params})

    def new(self,s1,s2,cls,params):
        oid=f"TMP_{cls.upper()}_{uuid.uuid4().hex[:6].upper()}"; self._objects[oid]={"class":cls,"params":params}
        return self._ok({"objectId":oid,"nota":"Objeto temporal. No persiste hasta write."})

    def write(self,s1,s2,cls,params):
        oid=params.get("objectId","")
        if oid not in self._objects: return {"code":20,"mensaje":f"objectId '{oid}' no encontrado."},self._ms()
        cod=f"DOC_{cls.upper()}_{uuid.uuid4().hex[:6].upper()}"; del self._objects[oid]
        return self._ok({"codDocumento":cod,"nota":"[MOCK] Persistido en BD simulada."})

    def cancel(self,s1,s2,cls,params):
        oid=params.get("objectId","")
        if oid in self._objects: del self._objects[oid]
        return self._ok({"nota":"Objeto temporal cancelado."})

    def imputa_pro(self,s1,s2,cls,params):
        return self._ok({"nota":f"[MOCK] Proyecto={params.get('codMaestro')} Partida={params.get('codDetalle')}","codMaestro":params.get("codMaestro"),"codDetalle":params.get("codDetalle")})


class RealApiClient:
    """
    Cliente HTTP real para la API mPYME de Distrito K.

    Protocolo segun documentacion oficial v1.2:
    - Todas las peticiones son POST a la URL base (no a sub-rutas)
    - Content-Type: application/x-www-form-urlencoded  (NO JSON)
    - Parametros como form fields: method=login&empr=1&user=admin&pass=HASH
    - Password: SHA1 del password en texto plano, codificado en Base64 (url-encoded)
    - Empresa: parametro "empr" (NO "empresa")
    - Clase: parametro "objectclass" (minusculas, NO "objectClass")
    - Sesion: ssid1 + ssid2 obtenidos del login
    """
    def __init__(self, url, emp, tout, ssl_verify):
        self.url = url.rstrip("/")
        self.emp = emp  # empresa — se incluye en _base() de todas las llamadas
        self.tout = tout
        self.ssl = ssl_verify
        self._s1 = ""
        self._s2 = ""

    @staticmethod
    def _hash_password(password: str) -> str:
        """SHA1 del password -> Base64. Formato exacto documentado por Distrito K."""
        import hashlib, base64
        sha1 = hashlib.sha1(password.encode("utf-8")).digest()
        return base64.b64encode(sha1).decode("ascii")

    def _post(self, fields: dict):
        """
        POST a la URL base con application/x-www-form-urlencoded.
        La API mPYME usa siempre la misma URL (raiz), distinguiendo por 'method'.
        """
        import requests
        t0 = time.monotonic()
        try:
            r = requests.post(
                self.url,
                data=fields,              # form-urlencoded, NO json=
                timeout=self.tout,
                verify=self.ssl,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                allow_redirects=True,     # maneja 302 automaticamente
            )
            ms = (time.monotonic() - t0) * 1000
            try:
                d = r.json()
            except Exception:
                d = {"raw": r.text[:500]}
            d["_http_status"] = r.status_code
            return d, ms
        except Exception as e:
            ms = (time.monotonic() - t0) * 1000
            return {"code": -1, "error": str(e), "_http_status": 0}, ms

    def _base(self) -> dict:
        """
        Campos comunes: ssid1, ssid2 y empr.
        IMPORTANTE: la API mPYME puede requerir 'empr' en CADA peticion,
        no solo en login. Incluirlo siempre evita code=5 por parametros incompletos.
        """
        base = {"ssid1": self._s1, "ssid2": self._s2}
        if self.emp:
            base["empr"] = self.emp
        return base

    def login(self, empresa, usuario, password):
        """
        Login segun doc: method=login&empr=<n>&user=<u>&pass=<sha1_base64>
        'empr' puede ser numero de empresa o codigo. Si es texto, se envia tal cual.
        Tras login exitoso guardamos emp para incluirlo en TODAS las llamadas
        posteriores (evita code=5 por empresa no enviada).
        """
        pw_hash = self._hash_password(password)
        fields = {
            "method": "login",
            "user": usuario,
            "pass": pw_hash,
        }
        # 'empr' es el numero/codigo de empresa — puede ser 1, "JDDC", etc.
        if empresa:
            fields["empr"] = empresa
        d, ms = self._post(fields)
        if d.get("code") == 0:
            data = d.get("data", {})
            self._s1 = data.get("ssid1", "")
            self._s2 = data.get("ssid2", "")
            # Guardar empresa para incluirla en _base() de todas las llamadas
            if empresa:
                self.emp = empresa
        return d, ms

    def logout(self, s1, s2):
        return self._post({**self._base(), "method": "logout"})

    def permiso(self, s1, s2, cls):
        return self._post({**self._base(), "method": "permiso", "objectclass": cls})

    def info(self, s1, s2, cls):
        return self._post({**self._base(), "method": "info", "objectclass": cls})

    def browse(self, s1, s2, cls, params):
        import json
        fields = {**self._base(), "method": "browse", "objectclass": cls}
        # Parametros adicionales como campos form individuales o como 'filter'/'columns'
        for k, v in params.items():
            fields[k] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        return self._post(fields)

    def read(self, s1, s2, cls, params):
        import json
        oid = params.pop("objectid", params.pop("id", ""))
        fields = {**self._base(), "method": "read", "objectclass": cls, "objectid": oid}
        for k, v in params.items():
            fields[k] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        return self._post(fields)

    def new(self, s1, s2, cls, params):
        import json
        oid = params.pop("objectid", "new")
        fields = {**self._base(), "method": "new", "objectclass": cls, "objectid": oid}
        for k, v in params.items():
            fields[k] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        return self._post(fields)

    def write(self, s1, s2, cls, params):
        import json
        oid = params.pop("objectid", "new")
        data = {k: v for k, v in params.items()}
        fields = {**self._base(), "method": "write", "objectclass": cls,
                  "objectid": oid, "data": json.dumps(data)}
        return self._post(fields)

    def cancel(self, s1, s2, cls, params):
        oid = params.get("objectid", "new")
        return self._post({**self._base(), "method": "cancel", "objectclass": cls, "objectid": oid})

    def imputa_pro(self, s1, s2, cls, params):
        import json
        oid = params.pop("objectid", "new")
        fields = {**self._base(), "method": "exec", "objectclass": cls,
                  "objectid": oid, "action": "imputaPro",
                  "params": json.dumps(params)}
        return self._post(fields)


def _clasificar_causa(entry: dict) -> str:
    """
    Clasifica la causa real del estado de una clase tras discover_all.
    Basada en los códigos reales que devuelve el servidor mPYME de Distrito K.

    IMPORTANTE — El servidor usa code=5 para DOS cosas distintas:
      - "No dispone de licencia para el módulo X" → sin_licencia real
      - "Petición no reconocida"                 → operación no soportada
    Hay que parsear el data para distinguirlas.

    IMPORTANTE — code=6 ("No es posible acceder a la base de datos en este momento")
    NO es un error de BD: es la forma en que el servidor indica que la operación
    necesita parámetros adicionales (ej: codProyecto para partidas).

    Prioridad:
      1. datos reales (browse=0 / muestra / campos_reales) → acceso_confirmado
      2. info OK (icode=0) → acceso_confirmado
      3. permiso=0 → acceso_confirmado (definitivo)
      4. permiso=1 → sin_licencia
      5. permiso=2 → sin_permiso_usuario
      6. permiso=5 con mensaje "licencia/No dispone" → sin_licencia
      7. permiso=6 → requiere_parametros (clase accesible, pide parámetros)
      8. browse=6 → requiere_parametros
      9. permiso=5 con mensaje neutro (Petición no reconocida) + permiso=0 previo → ya capturado
      10. bcode=5 con pcode=0 → acceso_confirmado (browse no soportado pero clase OK)
      11. cualquier 5 restante → config_incompleta (empresa no enviada, etc.)
      12. otro → respuesta_inesperada
    """
    pcode = entry.get("permiso_code")
    icode = entry.get("info_code")
    bcode = entry.get("browse_code")
    muestra = entry.get("muestra", [])
    campos_reales = entry.get("campos_reales", [])

    # Obtener los textos reales del servidor para distinguir code=5
    pdata = str((entry.get("permiso_raw") or {}).get("data", "")).lower()
    bdata = str((entry.get("browse_raw") or {}).get("data", "")).lower()

    # 1-3. Datos reales o permiso OK → confirmado sin ambigüedad
    if muestra or campos_reales:
        return "acceso_confirmado"
    if bcode == 0:
        return "acceso_confirmado"
    if icode == 0:
        return "acceso_confirmado"
    if pcode == 0:
        return "acceso_confirmado"

    # 4. Sin licencia contractual explícita
    if pcode == 1:
        return "sin_licencia"

    # 5. Sin permiso de usuario
    if pcode == 2:
        return "sin_permiso_usuario"

    # 6. permiso=5 con mensaje explícito de licencia del servidor
    #    Ej: "No dispone de licencia para el módulo Documentos. (Función \"docalbcom\")"
    _NO_LICENCIA_KEYWORDS = ("licencia", "no dispone", "sin licencia", "module not licensed")
    if pcode == 5 and any(kw in pdata for kw in _NO_LICENCIA_KEYWORDS):
        return "sin_licencia"

    # 7. permiso=6 → el servidor pide parámetros (clase accesible pero browse sin filtros falla)
    #    Mensaje habitual: "No es posible acceder a la base de datos en este momento"
    #    NO es un error de BD — es el modo en que mPYME indica parámetros obligatorios
    if pcode == 6:
        return "requiere_parametros"

    # 8. browse=6 con permiso distinto de 5 → requiere parámetros
    if bcode == 6 and pcode != 5:
        return "requiere_parametros"

    # 10. browse=5 ("Petición no reconocida") con permiso=0 o icode=0 ya capturado arriba.
    #     Si llegamos aquí con pcode=5 y bcode=5 sin mensaje de licencia → config incompleta
    if pcode == 5 or bcode == 5:
        return "config_incompleta"

    # 12. Cualquier otro código no documentado
    return "respuesta_inesperada"


def _explicar_causa(entry: dict, use_mock: bool) -> str:
    """
    Explicación en lenguaje natural de la causa real.
    Usa los textos reales que devuelve el servidor mPYME para dar información precisa.
    Sin ambigüedades. Indica exactamente qué ocurre y qué hacer.
    """
    causa = _clasificar_causa(entry)
    pcode = entry.get("permiso_code")
    bcode = entry.get("browse_code")
    icode = entry.get("info_code")
    modo = "BD Simulada" if use_mock else "API Real"

    # Textos reales del servidor (para incluirlos en las explicaciones)
    pdata = str((entry.get("permiso_raw") or {}).get("data", ""))
    bdata = str((entry.get("browse_raw") or {}).get("data", ""))
    idata = str((entry.get("info_raw") or {}).get("data", ""))

    if causa == "acceso_confirmado":
        n = len(entry.get("muestra", []))
        reg = entry.get("total_registros")
        if n > 0:
            base = f"Acceso CONFIRMADO ({modo}). Se han obtenido {n} registros reales"
            if reg is not None:
                base += f" (total en BD: {reg})"
            base += ". La clase funciona correctamente."
        elif entry.get("campos_reales"):
            base = (f"Acceso CONFIRMADO ({modo}). El servidor devuelve los metadatos de la clase "
                    f"(info→code=0). La tabla puede estar vacía o browse requiere parámetros.")
        elif icode == 0:
            base = (f"Acceso CONFIRMADO ({modo}). La operación 'info' respondió OK (code=0). "
                    f"La clase existe y es accesible.")
        else:
            base = f"Acceso CONFIRMADO ({modo}). permiso devolvió code=0 — licencia y permisos OK."
        nota = entry.get("nota_permiso", "")
        if nota:
            base += f" | {nota}"
        return base

    if causa == "sin_licencia":
        # Distinguir si fue code=1 o code=5 con mensaje de licencia
        if pcode == 1:
            msg_servidor = pdata[:120] if pdata else "code=1"
            return (
                f"SIN LICENCIA CONTRACTUAL (code=1). "
                f"Vuestra licencia NO incluye esta clase. "
                f"Para activarla contactad con Distrito K. "
                f"Mensaje del servidor: \"{msg_servidor}\""
            )
        else:
            # pcode=5 con mensaje de licencia
            msg_servidor = pdata[:180] if pdata else "No dispone de licencia"
            return (
                f"SIN LICENCIA (code=5, mensaje de licencia). "
                f"El servidor rechazó la petición indicando explícitamente falta de licencia. "
                f"Esto NO es un error de configuración — es una restricción contractual. "
                f"Contactad con Distrito K para ampliar. "
                f"Mensaje exacto del servidor: \"{msg_servidor}\""
            )

    if causa == "sin_permiso_usuario":
        clase_nombre = entry.get("clase", "?")
        usuario_api = entry.get("sesion_usuario", "API")
        return (
            f"SIN PERMISO DE USUARIO (code=2). La licencia puede incluir esta clase, "
            f"pero el usuario '{usuario_api}' no tiene acceso "
            f"a '{clase_nombre}' configurado en SQL Obras. "
            f"Solución: pedir al administrador de SQL Obras que asigne permisos al usuario API."
        )

    if causa == "requiere_parametros":
        # El mensaje "No es posible acceder a la base de datos en este momento" (code=6)
        # NO es un error de BD — es la forma de mPYME de indicar parámetros obligatorios
        msg_real = bdata[:100] if bdata and bdata != "none" else (pdata[:100] if pdata else "code=6")
        return (
            f"CLASE ACCESIBLE — requiere parámetros para browse (code=6). "
            f"El servidor responde code=6 a browse() sin filtros. "
            f"Esto NO significa que la BD esté caída: es el comportamiento documentado "
            f"para clases que necesitan un identificador obligatorio (ej: codProyecto para partidas, "
            f"codOrden para repordutil). "
            f"Para ver datos: usa el Explorador con los parámetros correctos. "
            f"Mensaje del servidor: \"{msg_real}\""
        )

    if causa == "config_incompleta":
        return (
            f"CONFIG INCOMPLETA (code=5, mensaje genérico). "
            f"El servidor respondió code=5 sin mensaje de licencia. "
            f"Causas posibles: (1) el campo 'empr' (empresa) no se envía o tiene valor incorrecto — "
            f"verifica SQLOB_EMPRESA en .env; (2) la operación no está soportada para esta clase "
            f"en vuestra instalación ('Petición no reconocida'). "
            f"Mensaje permiso: \"{pdata[:100]}\". Mensaje browse: \"{bdata[:100]}\""
        )

    # respuesta_inesperada
    return (
        f"RESPUESTA INESPERADA. permiso→code={pcode}, info→code={icode}, browse→code={bcode}. "
        f"El servidor devolvió un código no cubierto por los patrones conocidos de mPYME v1.2. "
        f"Respuesta permiso: \"{pdata[:100]}\". Respuesta browse: \"{bdata[:100]}\"."
    )


class ApiExplorerService:
    def __init__(self):
        self.ssid1=""; self.ssid2=""; self.session_active=False
        self.session_empresa=""; self.session_usuario=""; self.session_started=None
        self.use_mock=True; self.modo_escritura=False
        self._mock=MockApiClient(); self._real:Optional[RealApiClient]=None
        # Cargar historial, matriz y sondas desde disco al arrancar
        raw_hist = _cargar_json(_HISTORY_FILE, [])
        self._history: List[Dict] = raw_hist if isinstance(raw_hist, list) else []
        raw_mat = _cargar_json(_MATRIX_FILE, {})
        self._matrix: Dict[str, Dict] = raw_mat if isinstance(raw_mat, dict) else {}
        raw_sond = _cargar_json(_SONDAS_FILE, [])
        self._sondas: List[Dict] = raw_sond if isinstance(raw_sond, list) else []
        self._last_discover: Optional[Dict] = None  # se carga bajo demanda

    def _client(self):
        if self.use_mock: return self._mock
        if self._real is None:
            self._real = RealApiClient(
                settings.SQLOB_API_URL,
                settings.SQLOB_EMPRESA,
                settings.SQLOB_TIMEOUT,
                settings.SQLOB_VERIFY_SSL,
            )
        return self._real

    def _build(self,clase,op,params,raw,ms):
        hs=raw.pop("_http_status",200); code=raw.get("code")
        if raw.get("error") and code==-1: e="falla"; m=f"Error de conexion: {raw.get('error')}"
        elif hs==401: e="sin_permiso"; m="Sin autorizacion (401)"
        elif hs==403: e="sin_permiso"; m="Acceso denegado (403)"
        elif hs not in (200,201): e="falla"; m=f"HTTP {hs}"
        elif code==0: e="ok"; m="Operacion exitosa. code=0"
        elif code==1: e="sin_licencia"; m="Sin licencia para este modulo/clase (code=1). Vuestra licencia no incluye esta funcion."
        elif code==2: e="sin_permiso"; m="Sin permiso (code=2). El usuario API no tiene acceso a esta operacion."
        elif code==3: e="falla"; m="Error de validacion (code=3). Parametros enviados no son validos segun el servidor."
        elif code==5: e="falla"; m="Parametros incompletos (code=5). Faltan campos requeridos. Comprueba usuario, empresa y password."
        elif code==6: e="precisa_params"; m="Esta operacion requiere parametros adicionales (code=6). Proporciona el ID o clave del objeto."
        elif code==10: e="falla"; m="No encontrado (code=10). El objeto solicitado no existe en la BD."
        elif code is not None: e="falla"; m=f"Error servidor: code={code}. Consulta la tabla de codigos."
        else: e="ok"; m="HTTP 200 sin code interno (respuesta no estandar)."
        r={"id":str(uuid.uuid4())[:8],"timestamp":datetime.now().isoformat(),"clase":clase,"operacion":op,"params":params,"http_status":hs,"code":code,"json":raw,"duracion_ms":round(ms,1),"estado":e,"mensaje":m,"use_mock":self.use_mock,"nota_doc":NOTAS_DOC.get((clase,op),""),"nota_seguridad":NOTAS_SEGURIDAD.get((clase,op),"")}
        self._history.append(r)
        if len(self._history)>200: self._history=self._history[-200:]
        if clase not in self._matrix: self._matrix[clase]={}
        # Persistir a disco — sobrevive reinicios del servidor
        _guardar_json(_HISTORY_FILE, self._history)
        _guardar_json(_MATRIX_FILE, self._matrix)

        self._matrix[clase][op]={"estado":e,"ts":r["timestamp"]}
        return r

    def login(self,empresa,usuario,password):
        emp=empresa or settings.SQLOB_EMPRESA; usr=usuario or settings.SQLOB_USUARIO; pwd=password or settings.SQLOB_PASSWORD
        raw,ms=self._client().login(emp,usr,pwd)
        if raw.get("code")==0:
            self.ssid1=raw.get("ssid1",""); self.ssid2=raw.get("ssid2",""); self.session_active=True
            self.session_empresa=emp; self.session_usuario=usr; self.session_started=datetime.now().isoformat()
        return self._build("login","login",{},raw,ms)

    def logout(self):
        raw,ms=self._client().logout(self.ssid1,self.ssid2)
        self.ssid1=""; self.ssid2=""; self.session_active=False; self.session_started=None
        return self._build("logout","logout",{},raw,ms)

    def ejecutar(self,clase,op,params):
        if OPERACIONES_RIESGO.get(op,0)>=RIESGO_ESCRITURA and not self.modo_escritura:
            return {"id":str(uuid.uuid4())[:8],"timestamp":datetime.now().isoformat(),"clase":clase,"operacion":op,"params":params,"http_status":None,"code":None,"json":{},"duracion_ms":0,"estado":"bloqueado","mensaje":"BLOQUEADO: modo solo lectura activo. Activa escritura.","use_mock":self.use_mock,"nota_doc":NOTAS_DOC.get((clase,op),""),"nota_seguridad":NOTAS_SEGURIDAD.get((clase,op),"")}
        if not self.session_active:
            return {"id":str(uuid.uuid4())[:8],"timestamp":datetime.now().isoformat(),"clase":clase,"operacion":op,"params":params,"http_status":None,"code":None,"json":{},"duracion_ms":0,"estado":"falla","mensaje":"Sin sesion activa. Realiza login primero.","use_mock":self.use_mock,"nota_doc":"","nota_seguridad":""}
        c=self._client(); s1,s2=self.ssid1,self.ssid2
        fn={"permiso":lambda:c.permiso(s1,s2,clase),"info":lambda:c.info(s1,s2,clase),"browse":lambda:c.browse(s1,s2,clase,params),"read":lambda:c.read(s1,s2,clase,params),"new":lambda:c.new(s1,s2,clase,params),"write":lambda:c.write(s1,s2,clase,params),"cancel":lambda:c.cancel(s1,s2,clase,params),"imputaPro":lambda:c.imputa_pro(s1,s2,clase,params)}.get(op)
        raw,ms=fn() if fn else ({"code":-99,"error":f"'{op}' no implementada"},0.0)
        return self._build(clase,op,params,raw,ms)

    def get_status(self): return {"session_active":self.session_active,"empresa":self.session_empresa,"usuario":self.session_usuario,"session_started":self.session_started,"ssid1_masked":f"{self.ssid1[:6]}****" if self.ssid1 else "","ssid2_masked":f"{self.ssid2[:6]}****" if self.ssid2 else "","use_mock":self.use_mock,"modo_escritura":self.modo_escritura}
    def get_config_env(self):
        db_host = settings.DB_HOST or ""
        return {
            "api_url": settings.SQLOB_API_URL,
            "empresa": settings.SQLOB_EMPRESA,
            "usuario": settings.SQLOB_USUARIO,
            "password_set": bool(settings.SQLOB_PASSWORD),
            "timeout": settings.SQLOB_TIMEOUT,
            "verify_ssl": settings.SQLOB_VERIFY_SSL,
            # Pista: servidor Firebird, probablemente mismo host que mPYME
            "db_host_hint": db_host,
            "candidate_urls": self._build_candidate_urls(db_host),
        }

    def _build_candidate_urls(self, host: str) -> list:
        """Genera URLs candidatas segun documentacion mPYME v1.2 (puerto 8081 por defecto)."""
        if not host or host in ("localhost", "127.0.0.1"):
            hosts = ["localhost", "127.0.0.1"]
        else:
            hosts = [host, "localhost"]
        ports = [8081, 8080, 80, 443, 8443, 8000, 8001]
        candidates = []
        for h in hosts:
            for p in ports:
                proto = "https" if p in (443, 8443) else "http"
                candidates.append(f"{proto}://{h}:{p}/")
        return candidates[:12]

    def discover_url(self, extra_host: str = "") -> dict:
        """
        Prueba URLs candidatas segun documentacion mPYME v1.2.
        Envia method=login con credenciales vacias y observa la respuesta.
        - HTTP 200 + JSON con 'code' → servidor mPYME encontrado
        - HTTP 302 → redirige (probablemente HTTPS), seguir redireccion
        - Conexion rechazada/timeout → no hay servidor en ese puerto
        """
        import requests, hashlib, base64
        db_host = extra_host or settings.DB_HOST or "localhost"
        candidates = self._build_candidate_urls(db_host)
        results = []
        found = []

        for url in candidates:
            result = {"url": url, "estado": "no_responde", "detalle": "", "ms": 0}
            try:
                t0 = time.monotonic()
                # Peticion minima: login con usuario vacio — suficiente para ver si responde
                pw = base64.b64encode(hashlib.sha1(b"").digest()).decode()
                r = requests.post(
                    url,
                    data={"method": "login", "user": "", "pass": pw},
                    timeout=4,
                    verify=False,
                    allow_redirects=True,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                ms = round((time.monotonic() - t0) * 1000, 1)
                result["ms"] = ms
                result["http"] = r.status_code

                if r.status_code == 200:
                    try:
                        j = r.json()
                        if "code" in j:
                            result["estado"] = "mpyme_encontrado"
                            result["detalle"] = f"✅ Servidor mPYME confirmado — responde con code={j.get('code')}"
                            result["json_muestra"] = str(j)[:200]
                            found.append(url)
                        else:
                            result["estado"] = "http_ok_no_mpyme"
                            result["detalle"] = f"HTTP 200 pero no parece mPYME (sin campo 'code')"
                    except Exception:
                        result["estado"] = "http_ok_no_json"
                        result["detalle"] = f"HTTP 200 pero respuesta no es JSON: {r.text[:100]}"
                elif r.status_code in (401, 403, 500):
                    result["estado"] = "mpyme_posible"
                    result["detalle"] = f"HTTP {r.status_code} — puede ser mPYME con autenticacion"
                    found.append(url)
                elif r.status_code == 302:
                    result["estado"] = "redirige"
                    result["detalle"] = f"Redirige a: {r.headers.get('Location','?')}"
                else:
                    result["estado"] = "http_otro"
                    result["detalle"] = f"HTTP {r.status_code}"
            except requests.exceptions.ConnectTimeout:
                result["detalle"] = "Timeout de conexion (>4s)"
            except requests.exceptions.ConnectionError as e:
                result["detalle"] = f"Sin conexion: {str(e)[:80]}"
            except Exception as e:
                result["detalle"] = f"Error: {str(e)[:80]}"
            results.append(result)

        return {
            "host_probado": db_host,
            "total_probadas": len(candidates),
            "encontradas": found,
            "recomendacion": found[0] if found else "",
            "resultados": results,
        }
    def get_history(self, limit=200):
        return list(reversed(self._history))[:limit]

    def get_sondas(self, limit=100):
        return list(reversed(self._sondas))[:limit]

    def get_matrix(self):
        return self._matrix

    def get_catalogue(self):
        return CLASES_POR_MODULO

    def clear_history(self):
        self._history.clear()
        self._sondas.clear()
        _guardar_json(_HISTORY_FILE, [])
        _guardar_json(_SONDAS_FILE, [])

    def resumen_historial(self):
        tot = len(self._history)
        return {
            "total": tot,
            "ok": sum(1 for r in self._history if r["estado"] == "ok"),
            "falla": sum(1 for r in self._history if r["estado"] == "falla"),
            "sin_permiso": sum(1 for r in self._history if r["estado"] == "sin_permiso"),
            "sin_licencia": sum(1 for r in self._history if r["estado"] == "sin_licencia"),
            "precisa_params": sum(1 for r in self._history if r["estado"] == "precisa_params"),
            "sondas": len(self._sondas),
        }

    def _registrar_sonda(self, resultado: dict) -> None:
        """Guarda el resultado de una sonda en el log de sondas persistente."""
        self._sondas.append(resultado)
        if len(self._sondas) > 200:
            self._sondas = self._sondas[-200:]
        _guardar_json(_SONDAS_FILE, self._sondas)


    def discover_from_db(self) -> dict:
        """Autodescubrimiento seguro: solo SELECT. Sin escrituras. Password no descubrible."""
        import re, os
        result = {
            "success": False, "usuarios_firebird": [], "usuarios_sqlobras": [],
            "tabla_usuarios_encontrada": None, "tablas_config": {},
            "empresa_inferida": None, "tablas_inspeccionadas": 0,
            "recomendaciones": [],
            "nota_seguridad": "Solo SELECT de solo lectura. Sin modificaciones. Contrasenas no descubribles.",
            "error": None,
        }
        try:
            from backend.core.factory.db_factory import DBFactory
            from backend.core.abstract.database import DBConfig
            from backend.core.utils.constants import DBConstants
            if not settings.DB_HOST or not settings.DB_NAME:
                result["error"] = "DB_HOST o DB_NAME no configurados en .env."
                return result
            config = DBConfig(
                host=settings.DB_HOST, port=settings.DB_PORT,
                database=settings.DB_NAME, user=settings.DB_USER,
                password=settings.DB_PASSWORD, charset="utf8",
            )
            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
            try:
                driver.connect(config)
                # 1. Usuarios Firebird (RDB$USERS)
                try:
                    rows = driver.execute_query(
                        "SELECT TRIM(RDB$USER_NAME) AS USUARIO FROM RDB$USERS ORDER BY RDB$USER_NAME"
                    )
                    result["usuarios_firebird"] = [
                        str(r.get("USUARIO") or r.get("usuario") or "").strip()
                        for r in (rows or []) if r
                    ]
                except Exception as e:
                    logger.warning(f"[discover_from_db] RDB$USERS: {e}")
                # 2. Listar todas las tablas de usuario
                tablas_existentes = []
                try:
                    rows = driver.execute_query(
                        "SELECT TRIM(RDB$RELATION_NAME) AS TABLA FROM RDB$RELATIONS "
                        "WHERE RDB$SYSTEM_FLAG = 0 ORDER BY RDB$RELATION_NAME"
                    )
                    tablas_existentes = [
                        str(r.get("TABLA") or r.get("tabla") or "").strip()
                        for r in (rows or []) if r
                    ]
                    result["tablas_inspeccionadas"] = len(tablas_existentes)
                except Exception as e:
                    logger.warning(f"[discover_from_db] RDB$RELATIONS: {e}")
                # 3. Tablas de usuarios de SQL Obras
                for tabla in ["USDLOGIN","USUARIS","USUARIOS","USDUSERS","SIS_USUARIOS","APIUSERS","DK_USUARIOS","DK_USERS"]:
                    if tabla in tablas_existentes:
                        try:
                            rows = driver.execute_query(f"SELECT FIRST 100 * FROM {tabla}")
                            if rows:
                                result["tabla_usuarios_encontrada"] = tabla
                                all_keys = list(rows[0].keys())
                                uc = [k for k in all_keys if any(p in k.upper() for p in ["USER","LOGIN","USUA","NOM","NAME"])] or all_keys[:4]
                                result["usuarios_sqlobras"] = [{c: str(row.get(c) or "").strip() for c in uc} for row in rows]
                        except Exception as e:
                            logger.warning(f"[discover_from_db] {tabla}: {e}")
                        break  # Solo la primera tabla encontrada
                # 4. Tablas de configuracion / empresa
                for tabla in ["SIS_EMPRESA","EMPRESA","CONFIGURACION","CONFIG","SIS_CONFIG","DK_CONFIG"]:
                    if tabla in tablas_existentes:
                        try:
                            rows = driver.execute_query(f"SELECT FIRST 5 * FROM {tabla}")
                            if rows: result["tablas_config"][tabla] = rows[:3]
                        except Exception: pass
                # 5. Inferir empresa desde path de BD
                db_path = settings.DB_NAME or ""
                m = re.search(r'[/\\]([A-Z][A-Z0-9_]{1,20})[/\\][0-9]{4}\.fdb$', db_path, re.IGNORECASE)
                if m:
                    result["empresa_inferida"] = m.group(1).upper()
                else:
                    base = os.path.splitext(os.path.basename(db_path))[0]
                    if base and not base.isdigit():
                        result["empresa_inferida"] = base.upper()
                result["success"] = True
            finally:
                try: driver.disconnect()
                except Exception: pass
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"[discover_from_db] error: {e}")
        # 6. Recomendaciones
        fb = result["usuarios_firebird"]
        no_sysdba = [u for u in fb if u.upper() != "SYSDBA"]
        sqlogins: List[str] = []
        for u in result["usuarios_sqlobras"]:
            for v in u.values():
                v = (v or "").strip()
                if v and len(v) < 30 and v not in sqlogins: sqlogins.append(v)
        if "SYSDBA" in fb:
            result["recomendaciones"].append({"nivel":"advertencia","icono":"⚠️",
                "texto":"SYSDBA detectado. NO uses SYSDBA para la API mPYME. Pide un usuario dedicado con permisos minimos."})
        if no_sysdba:
            result["recomendaciones"].append({"nivel":"info","icono":"ℹ️","usuarios_candidatos":no_sysdba[:10],
                "texto":f"Usuarios Firebird (excl. SYSDBA): {', '.join(no_sysdba[:8])}. Pregunta al admin cual tiene acceso a la API."})
        if sqlogins:
            result["recomendaciones"].append({"nivel":"ok","icono":"✅","usuarios_candidatos":sqlogins[:10],
                "texto":f"SQL Obras logins: {', '.join(sqlogins[:8])}. El usuario API sera uno de estos."})
        if result["empresa_inferida"]:
            result["recomendaciones"].append({"nivel":"info","icono":"🏢",
                "texto":f"Empresa inferida del path: '{result['empresa_inferida']}'. Confirma con Distrito K el codigo correcto."})
        result["recomendaciones"].append({"nivel":"clave","icono":"🔑",
            "texto":"La contrasena NO puede descubrirse. El administrador o Distrito K deben proporcionarla."})
        return result



    def discover_credentials(self, empresa: str, url: str) -> dict:
        """Prueba credenciales por defecto conocidas. Max 10 intentos, 1s delay. Para al primer exito."""
        import hashlib, base64, requests as _req
        MAX = 10; DELAY = 1.0
        # Credenciales factory/default documentadas para Firebird/SQL Obras. NO es ataque de diccionario.
        CREDS = [
            ("SYSDBA","masterkey"), ("SYSDBA",""), ("admin",""), ("admin","admin"),
            ("admin","1234"), ("admin","sqlworks"), ("ADMIN","masterkey"),
            ("usuario","usuario"), ("apiuser",""), ("API_JDDC",""),
        ]
        url_base = (url or "").rstrip("/")
        if not url_base:
            return {"success":False,"error":"URL no proporcionada. Ejecuta antes el Autodescubrimiento de URL.",
                    "intentos":[],"encontrado":None}
        def _hash(pw):
            return base64.b64encode(hashlib.sha1(pw.encode("utf-8")).digest()).decode("ascii")
        intentos: List[Dict] = []; encontrado: Optional[Dict] = None; n = 0
        for usr, pw in CREDS:
            if n >= MAX: logger.warning("[discover_credentials] limite alcanzado"); break
            if n > 0: time.sleep(DELAY)
            n += 1; t0 = time.monotonic()
            it: Dict = {"n":n,"usuario":usr,"password_display":"****" if pw else "(vacia)",
                        "empresa":empresa or "(sin empresa)","estado":"error","code":None,"mensaje":"","ms":0}
            try:
                fields = {"method":"login","user":usr,"pass":_hash(pw)}
                if empresa: fields["empr"] = empresa
                r = _req.post(url_base, data=fields, timeout=5, verify=False, allow_redirects=True,
                              headers={"Content-Type":"application/x-www-form-urlencoded"})
                ms = round((time.monotonic()-t0)*1000,1); it["ms"] = ms
                try: d = r.json()
                except Exception: d = {"raw": r.text[:200]}
                code = d.get("code"); it["code"] = code
                if r.status_code == 200 and code == 0:
                    it["estado"] = "ok"; it["mensaje"] = "Login exitoso — credenciales por defecto aceptadas"
                    encontrado = {"usuario":usr,"password":pw,"empresa":empresa}
                    logger.warning(f"[discover_credentials] DEFAULT FUNCIONA: user={usr} url={url_base}")
                    intentos.append(it); break
                elif r.status_code in (401,403):
                    it["estado"] = "rechazado"; it["mensaje"] = f"HTTP {r.status_code}"
                elif code == 2: it["estado"] = "rechazado"; it["mensaje"] = "code=2 sin permiso"
                elif code == 1: it["estado"] = "rechazado"; it["mensaje"] = "code=1 sin licencia/empresa"
                elif code is not None: it["estado"] = "rechazado"; it["mensaje"] = f"code={code}"
                else: it["estado"] = "sin_info"; it["mensaje"] = f"HTTP {r.status_code} sin code mPYME"
            except _req.exceptions.ConnectTimeout:
                it["ms"] = round((time.monotonic()-t0)*1000,1); it["estado"] = "timeout"; it["mensaje"] = "Timeout"
                intentos.append(it); break
            except _req.exceptions.ConnectionError as e:
                it["ms"] = round((time.monotonic()-t0)*1000,1); it["estado"] = "sin_conexion"; it["mensaje"] = str(e)[:60]
                intentos.append(it); break
            except Exception as e:
                it["ms"] = round((time.monotonic()-t0)*1000,1); it["estado"] = "error"; it["mensaje"] = str(e)[:100]
            intentos.append(it)
        # Generar recomendacion
        if encontrado:
            rec = (f"🚨 CREDENCIALES DEFAULT FUNCIONAN: {encontrado['usuario']} / "
                   f"{'(sin pass)' if not encontrado['password'] else '****'}. "
                   "CAMBIA LA CONTRASENA INMEDIATAMENTE y crea un usuario dedicado para la API.")
        elif all(i["estado"]=="rechazado" for i in intentos):
            rec = ("✅ Ninguna credencial por defecto funciona. "
                   "Sistema bien configurado o usa credenciales personalizadas. "
                   "Pide las credenciales al administrador o a Distrito K.")
        elif any(i["estado"] in ("timeout","sin_conexion") for i in intentos):
            rec = "⚠️ Sin conexion al servidor mPYME. Verifica la URL con el Autodescubrimiento de URL."
        else:
            rec = "ℹ️ Prueba completada. Si ninguna funciono, pide credenciales al administrador o Distrito K."
        return {
            "success": True,
            "url_probada": url_base,
            "empresa_probada": empresa or "(sin empresa)",
            "total_intentos": len(intentos),
            "max_intentos": MAX,
            "encontrado": encontrado,
            "recomendacion": rec,
            "nota_seguridad": (
                f"Probadas {len(intentos)} credenciales predeterminadas con {DELAY}s entre cada intento. "
                "NO es ataque de diccionario. Para al primer exito o al limite de intentos."
            ),
            "intentos": intentos,
        }




    def discover_all(self) -> dict:
        """
        Descubrimiento COMPLETO de la API: ejecuta permiso+info+browse en TODAS las clases.
        Solo se ejecuta si hay sesion activa. Solo lectura, sin riesgo.
        Devuelve para cada clase: permisos reales, campos reales (info), y muestra de datos (browse).
        """
        from backend.modules.api_explorer.api_catalogue_full import get_catalogue, get_campos_clase, CODIGOS_RESPUESTA

        if not self.session_active:
            return {"success": False, "error": "Sin sesion activa. Haz login primero."}

        catalogue = get_catalogue()
        campos_doc = get_campos_clase()

        # Recopilar todas las clases del catalogo
        todas_clases = []
        for mod_data in catalogue.values():
            todas_clases.extend(mod_data.get("clases", []))

        resultados = {}
        resumen = {"total": 0, "con_permiso": 0, "sin_permiso": 0, "sin_licencia": 0, "error": 0}

        for clase in todas_clases:
            resumen["total"] += 1
            entry = {
                "clase": clase,
                "permiso_raw": None,
                "permiso_ops": {},
                "info_raw": None,
                "campos_reales": [],
                "browse_raw": None,
                "muestra": [],
                "total_registros": None,
                "estado": "pendiente",
                "error": None,
            }

            # 1. permiso — saber qué operaciones permite la licencia
            try:
                raw_p, ms_p = self._client().permiso(self.ssid1, self.ssid2, clase)
                code_p = raw_p.get("code")
                http_p = raw_p.get("_http_status", 200)
                entry["permiso_raw"] = {k: v for k, v in raw_p.items() if k != "_http_status"}
                entry["permiso_code"] = code_p
                entry["permiso_http"] = http_p
                if code_p == 0:
                    # extraer flags de permiso — pueden estar a nivel raíz o dentro de "data"
                    raw_data = raw_p.get("data", {})
                    ops_src = raw_data if isinstance(raw_data, dict) and raw_data else raw_p
                    entry["permiso_ops"] = {
                        k: v for k, v in ops_src.items()
                        if k in ("browse","read","new","edit","write","cancel","delete","imputaPro")
                        and isinstance(v, bool)
                    }
                    entry["estado"] = "con_permiso"
                    resumen["con_permiso"] += 1
                elif code_p == 1:
                    entry["estado"] = "sin_licencia"
                    entry["error"] = "Sin licencia para esta clase (code=1)"
                    resumen["sin_licencia"] += 1
                elif code_p == 2:
                    entry["estado"] = "sin_permiso"
                    entry["error"] = "Usuario sin permiso para esta clase (code=2)"
                    resumen["sin_permiso"] += 1
                else:
                    # Código inesperado: puede que 'permiso' no esté soportado en esta versión
                    # No descartamos la clase — intentamos info y browse igualmente
                    entry["estado"] = "error"
                    entry["error"] = f"permiso devolvió code={code_p} (inesperado — se sigue intentando browse/info)"
                    resumen["error"] += 1
            except Exception as e:
                entry["estado"] = "error"
                entry["error"] = str(e)[:150]
                entry["permiso_code"] = -1
                resumen["error"] += 1

            # 2. info — campos reales del servidor (se intenta siempre, no solo si con_permiso)
            try:
                raw_i, _ = self._client().info(self.ssid1, self.ssid2, clase)
                entry["info_raw"] = {k: v for k, v in raw_i.items() if k != "_http_status"}
                entry["info_code"] = raw_i.get("code")
                if raw_i.get("code") == 0:
                    # extraer lista de campos — el servidor puede devolverlos en distintas claves
                    fields = (raw_i.get("fields") or raw_i.get("data")
                              or raw_i.get("columns") or raw_i.get("items") or [])
                    if isinstance(fields, list):
                        entry["campos_reales"] = fields[:50]
                    elif isinstance(fields, dict):
                        # algunos servidores devuelven dict {campo: tipo}
                        entry["campos_reales"] = [{"n": k, "tipo": str(v)} for k, v in fields.items()][:50]
                    # Si info OK pero permiso no → clase accesible aunque permiso retornó código raro
                    if entry["estado"] == "error":
                        entry["estado"] = "con_permiso"
                        resumen["error"] -= 1
                        resumen["con_permiso"] += 1
                        entry["nota_permiso"] = (
                            f"permiso retornó code={entry.get('permiso_code','?')} "
                            f"pero info OK — clase accesible"
                        )
            except Exception as e:
                entry["info_error"] = str(e)[:80]

            # 3. browse — muestra de datos reales (se intenta siempre)
            puede_browse = entry.get("permiso_ops", {}).get("browse", True)  # asumir True si no hay info
            try:
                raw_b, _ = self._client().browse(self.ssid1, self.ssid2, clase, {})
                entry["browse_raw"] = {k: v for k, v in raw_b.items() if k != "_http_status"}
                entry["browse_code"] = raw_b.get("code")
                if raw_b.get("code") == 0:
                    items = raw_b.get("items") or raw_b.get("data") or []
                    entry["muestra"] = items[:5]  # máx 5 registros de muestra
                    entry["total_registros"] = raw_b.get("total")
                    # Si browse OK pero permiso fue "error" → reclasificar como accesible
                    if entry["estado"] == "error":
                        entry["estado"] = "con_permiso"
                        resumen["error"] -= 1
                        resumen["con_permiso"] += 1
                        entry["nota_permiso"] = (
                            f"permiso retornó code={entry.get('permiso_code','?')} "
                            f"pero browse OK — datos reales disponibles"
                        )
                else:
                    browse_code = raw_b.get("code")
                    entry["browse_error_code"] = browse_code
                    entry["browse_error_msg"] = raw_b.get("error") or raw_b.get("msg") or f"code={browse_code}"
                    # code=6 = requiere params obligatorios: la clase EXISTE y está accesible
                    # pero browse sin filtro no funciona para esta clase (necesita codProyecto, etc.)
                    if browse_code == 6:
                        if entry["estado"] == "error":
                            entry["estado"] = "con_permiso"
                            resumen["error"] -= 1
                            resumen["con_permiso"] += 1
                        entry["nota_permiso"] = (
                            entry.get("nota_permiso", "") +
                            " browse(code=6): clase accesible pero requiere parametros (ej: codProyecto)."
                        ).strip()
            except Exception as e:
                entry["browse_error"] = str(e)[:80]

            # Añadir campos documentados para comparación
            entry["campos_doc"] = campos_doc.get(clase, [])

            # ── Segunda pasada inteligente para clases code=6 ─────────────────
            # Si browse sin params devolvió code=6, intentar con variantes de params.
            # Salta variantes con "?" (requieren valor real desconocido en este punto).
            # Prueba más variantes para clases simples (tipostrabajo, repobjetos, etc.)
            if entry.get("browse_code") == 6 or entry.get("permiso_code") == 6:
                variantes = self._SONDA_PARAMS.get(clase, [{"num": 20}, {"nReg": 20}])
                # Filtrar variantes sin "?" — solo las que podemos probar sin datos previos
                variantes_sin_interr = [
                    prm for prm in variantes
                    if prm and "?" not in str(list(prm.values()))
                ]
                for prm in variantes_sin_interr[:5]:  # máx 5 variantes en discover
                    try:
                        raw_b2, _ = self._client().browse(self.ssid1, self.ssid2, clase, dict(prm))
                        bc2 = raw_b2.get("code")
                        if bc2 == 0:
                            items2 = raw_b2.get("items") or raw_b2.get("data") or []
                            if isinstance(items2, list) and items2:
                                entry["muestra"] = items2[:5]
                                entry["total_registros"] = raw_b2.get("total")
                                entry["browse_raw"] = {k: v for k, v in raw_b2.items() if k != "_http_status"}
                                entry["browse_code"] = 0
                                entry["browse_params_exitosos"] = prm
                                if entry["estado"] == "error":
                                    entry["estado"] = "con_permiso"
                                    resumen["error"] -= 1
                                    resumen["con_permiso"] += 1
                                logger.info(f"[discover] {clase}: datos con params={prm}")
                                break  # datos obtenidos — no seguir probando
                        time.sleep(0.12)
                    except Exception:
                        pass

            # Causa real unívoca — explicación inequívoca del estado
            entry["causa_real"] = _clasificar_causa(entry)
            entry["causa_explicacion"] = _explicar_causa(entry, self.use_mock)

            resultados[clase] = entry
            time.sleep(0.15)  # pausa mínima entre clases para no saturar

        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "sesion": {"empresa": self.session_empresa, "usuario": self.session_usuario},
            "use_mock": self.use_mock,
            "resumen": resumen,
            "clases": resultados,
            "catalogue": catalogue,
        }


    def generar_informe(self) -> dict:
        """
        Informe multi-nivel basado en causa_real. Requiere discover_all() previo.
        Carga automáticamente desde disco si hay cache guardado.
        Devuelve texto TXT + secciones estructuradas para HTML en frontend.
        """
        self._cargar_discover_cache()
        dr = getattr(self, '_last_discover', None)
        if not dr:
            return {"error": "Ejecuta primero 'Descubrir todo' en la pestana Inspector.", "texto": ""}

        clases = dr.get("clases", {})
        ts = dr.get("timestamp", "")[:19].replace("T", " ")
        empresa = dr.get("sesion", {}).get("empresa", "?")
        usuario = dr.get("sesion", {}).get("usuario", "?")
        use_mock = dr.get("use_mock", True)
        modo = "BD SIMULADA (datos de ejemplo)" if use_mock else "API REAL (SQL Obras produccion)"

        DESC = {
            "proyectos":"Obras / Proyectos",
            "partidas":"Capitulos y Partidas de una obra",
            "proordutil":"Costes reales imputados a obra (utilizados)",
            "proordprev":"Costes previstos / presupuesto",
            "reporden":"Ordenes de reparacion / mantenimiento",
            "repobjetos":"Equipos reparables (maquinaria...)",
            "repinst":"Instalaciones de los equipos",
            "tipostrabajo":"Tipos de trabajo (averia, preventivo...)",
            "repordutil":"Materiales y horas en reparaciones",
            "articulos":"Catalogo de articulos / materiales",
            "recursos":"Recursos (instaladores, maquinaria...)",
            "proveedores":"Proveedores",
            "clientes":"Clientes",
            "docalbcom":"Albaranes de compra (imputaPro disponible)",
            "docfaccom":"Facturas de compra (imputaPro disponible)",
            "docpedcom":"Pedidos de compra (imputaPro: doc. no concluyente)",
            "ordenfab":"Ordenes de fabricacion",
        }

        # Agrupar por causa_real (no por estado, que era ambiguo)
        grupos: dict = {}
        for c, d in clases.items():
            causa = d.get("causa_real", _clasificar_causa(d))
            grupos.setdefault(causa, []).append(c)

        con_acceso = grupos.get("acceso_confirmado", [])
        req_params  = grupos.get("requiere_parametros", [])
        sin_lic     = grupos.get("sin_licencia", [])
        sin_perm    = grupos.get("sin_permiso_usuario", [])
        cfg_inc     = grupos.get("config_incompleta", [])
        inesperado  = grupos.get("respuesta_inesperada", [])

        # Detalles técnicos por clase para el frontend
        detalles = {}
        for c, d in clases.items():
            ops = list(d.get("permiso_ops", {}).keys())
            campos_raw = d.get("campos_reales", [])
            nombres_campos = []
            for cf in campos_raw[:15]:
                n = cf.get("n") or cf.get("nombre") or cf.get("field")
                if not n and cf:
                    vals = list(cf.values())
                    n = str(vals[0]) if vals else ""
                if n:
                    nombres_campos.append(str(n))
            detalles[c] = {
                "desc": DESC.get(c, c),
                "causa_real": d.get("causa_real", _clasificar_causa(d)),
                "causa_explicacion": d.get("causa_explicacion", _explicar_causa(d, use_mock)),
                "operaciones": ops,
                "campos": nombres_campos,
                "total_registros": d.get("total_registros"),
                "muestra_n": len(d.get("muestra", [])),
                "permiso_code": d.get("permiso_code"),
                "browse_code": d.get("browse_code"),
                "info_code": d.get("info_code"),
            }

        # Aplicaciones posibles basadas en acceso real
        apps = self._calcular_apps(con_acceso, req_params)

        secciones = {
            "con_acceso": con_acceso, "requiere_parametros": req_params,
            "sin_licencia": sin_lic, "sin_permiso": sin_perm,
            "config_incompleta": cfg_inc, "respuesta_inesperada": inesperado,
        }

        sep = "=" * 72
        txt = self._generar_txt(ts, empresa, usuario, modo,
                                detalles, secciones, apps, DESC, sep)
        return {
            "texto": txt, "timestamp": ts, "empresa": empresa,
            "usuario": usuario, "modo": modo, "use_mock": use_mock,
            "secciones": secciones, "detalles": detalles, "apps": apps,
            "totales": {
                "con_acceso": len(con_acceso), "requiere_parametros": len(req_params),
                "sin_licencia": len(sin_lic), "sin_permiso": len(sin_perm),
                "config_incompleta": len(cfg_inc), "respuesta_inesperada": len(inesperado),
                "total": len(clases),
            },
        }

    def _calcular_apps(self, con_acceso: list, req_params: list) -> list:
        """Calcula aplicaciones posibles basándose únicamente en acceso real verificado."""
        todo = con_acceso + req_params
        apps = []
        if "proordutil" in todo:
            apps.append({
                "nombre": "App Operario — Imputacion de costes en campo",
                "desc": ("El operario selecciona la obra y partida desde el movil, "
                         "indica material/recurso y cantidad. "
                         "La app registra el utilizado en SQL Obras sin papel."),
                "requiere": ["proordutil (write)", "proyectos (browse)", "partidas (browse)"],
                "disponible": True,
            })
        if "reporden" in con_acceso:
            apps.append({
                "nombre": "App Mantenimiento — Reparaciones en campo",
                "desc": ("El tecnico ve sus ordenes de reparacion en el movil, "
                         "registra materiales usados y horas, y cierra la orden."),
                "requiere": ["reporden (browse/new/write)", "repordutil (write)"],
                "disponible": True,
            })
        if "docalbcom" in con_acceso or "docfaccom" in con_acceso:
            apps.append({
                "nombre": "Modulo Compras a Obra",
                "desc": ("Al dar de alta un albaran, se vincula la linea al proyecto "
                         "y partida mediante imputaPro. El coste aparece como utilizado."),
                "requiere": ["docalbcom o docfaccom (imputaPro)"],
                "disponible": True,
            })
        if "proyectos" in todo:
            apps.append({
                "nombre": "Cuadro de Mando de Obras",
                "desc": ("Dashboard de costes reales vs previstos por obra y partida, "
                         "actualizado desde SQL Obras."),
                "requiere": ["proyectos", "partidas", "proordutil", "proordprev"],
                "disponible": "proordutil" in todo,
            })
        apps.append({
            "nombre": "Integracion IA",
            "desc": ("La IA consulta obras, partidas y costes para responder: "
                     "cuanto llevamos gastado en la obra 25/184."),
            "requiere": ["Cualquier clase con browse activo"],
            "disponible": len(con_acceso) > 0,
        })
        return apps

    def _generar_txt(self, ts, empresa, usuario, modo,
                     detalles, secciones, apps, DESC, sep) -> str:
        """TXT multi-nivel fiable para exportar. Sin datos inventados."""
        con_acceso = secciones.get("con_acceso", [])
        req_params  = secciones.get("requiere_parametros", [])
        sin_lic     = secciones.get("sin_licencia", [])
        sin_perm    = secciones.get("sin_permiso", [])
        cfg_inc     = secciones.get("config_incompleta", [])
        inesperado  = secciones.get("respuesta_inesperada", [])
        txt = (f"{sep}\nINFORME DE CAPACIDADES — API mPYME v1.2 — DISTRITO K\n"
               f"{sep}\nGenerado: {ts}  Empresa: {empresa}  "
               f"Usuario: {usuario}  Modo: {modo}\n{sep}\n")
        txt += "\n=== N1: RESUMEN ===\nACCESO CONFIRMADO:\n"
        for c in con_acceso:
            txt += f"  [SI]  {DESC.get(c,c)}\n"
        for c in req_params:
            txt += f"  [SI*] {DESC.get(c,c)}  (* requiere params)\n"
        if not con_acceso and not req_params:
            txt += "  (ninguna confirmada aun)\n"
        txt += "\nNO DISPONIBLE — causa exacta:\n"
        for c in sin_lic:
            txt += f"  [SIN LICENCIA] {DESC.get(c,c)}: {detalles[c]['causa_explicacion']}\n"
        for c in sin_perm:
            txt += f"  [SIN PERMISO]  {DESC.get(c,c)}: {detalles[c]['causa_explicacion']}\n"
        for c in cfg_inc:
            txt += f"  [CONFIG INCOMPLETA] {DESC.get(c,c)}: {detalles[c]['causa_explicacion']}\n"
        for c in inesperado:
            txt += f"  [RESP. INESPERADA] {DESC.get(c,c)}: {detalles[c]['causa_explicacion']}\n"
        txt += f"\n{sep}\n=== N2: PARA EL EMPLEADO ===\n"
        for app in apps:
            txt += f"\n  [{'SI' if app['disponible'] else 'NO'}] {app['nombre']}\n  {app['desc']}\n  Requiere: {', '.join(app['requiere'])}\n"
        txt += f"\n{sep}\n=== N3: PARA EL TECNICO ===\n"
        for c in (con_acceso + req_params):
            d = detalles[c]; reg = d.get("total_registros")
            txt += f"\n  [{c}] {d['desc']}\n"
            txt += f"  Causa: {d['causa_real']} — {d['causa_explicacion']}\n"
            if d["operaciones"]: txt += f"  Ops:    {', '.join(d['operaciones'])}\n"
            if d["campos"]:      txt += f"  Campos: {', '.join(d['campos'][:10])}\n"
            if reg is not None:  txt += f"  Regs:   {reg}\n"
            if d["muestra_n"]>0: txt += f"  Muestra: {d['muestra_n']} registros\n"
        txt += f"\n{sep}\n=== CLASES NO DISPONIBLES — detalle verificado ===\n"
        for grupo, label in [
            (sin_lic, "SIN LICENCIA"),
            (sin_perm, "SIN PERMISO USUARIO"),
            (cfg_inc, "CONFIG INCOMPLETA"),
            (inesperado, "RESPUESTA INESPERADA"),
        ]:
            for c in grupo:
                txt += (f"\n  [{c}] {label}\n  {DESC.get(c,c)}\n"
                        f"  {detalles[c]['causa_explicacion']}\n"
                        f"  permiso_code={detalles[c]['permiso_code']} "
                        f"browse_code={detalles[c]['browse_code']}\n")
        txt += f"\n{sep}\n=== N4: PARA GERENCIA ===\n"
        for i, app in enumerate(apps, 1):
            txt += f"\n  {i}. {app['nombre']} [{'DISPONIBLE' if app['disponible'] else 'AMPLIAR LICENCIA'}]\n  {app['desc']}\n"
        txt += (f"\n{sep}\nCODIGOS: 0=OK 1=SinLicencia 2=SinPermiso 3=Validacion "
                "5=ParamsIncompletos 6=RequiereParams 10=NoEncontrado -1=ErrorRed\n"
                f"{sep}\nFIN DEL INFORME\n{sep}\n")
        return txt

    def guardar_discover(self, result: dict):
        """Guarda el discover en memoria Y en disco (persiste entre reinicios)."""
        self._last_discover = result
        try:
            _DISCOVER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _DISCOVER_CACHE_FILE.write_text(
                json.dumps(result, ensure_ascii=False, default=str, indent=2),
                encoding="utf-8"
            )
            logger.info(f"[api_explorer] discover guardado en {_DISCOVER_CACHE_FILE}")
        except Exception as e:
            logger.warning(f"[api_explorer] No se pudo guardar discover cache: {e}")

    def _cargar_discover_cache(self):
        """Carga el último discover desde disco si existe y no hay uno en memoria."""
        if self._last_discover:
            return  # ya hay uno en memoria, no sobreescribir
        try:
            if _DISCOVER_CACHE_FILE.exists():
                data = json.loads(_DISCOVER_CACHE_FILE.read_text(encoding="utf-8"))
                self._last_discover = data
                ts = data.get("timestamp", "")[:19]
                logger.info(f"[api_explorer] discover cache cargado del {ts}")
        except Exception as e:
            logger.warning(f"[api_explorer] No se pudo cargar discover cache: {e}")

    # Parámetros de sonda por clase (browse solo lectura, múltiples estrategias)
    # Variantes de parámetros para sonda/discover.
    # La API mPYME v1.2 usa distintos nombres según la clase:
    # - num / nReg / nregs / max  (paginación)
    # - pag / pagina / page       (número de página)
    # - filtro / filter / where   (filtro genérico)
    # Las clases con "?" en params requieren valor real (codProyecto, codOrden...)
    _SONDA_PARAMS: dict = {
        "proyectos":   [
            {"num": 20}, {"nReg": 20}, {"pag": 1, "num": 20}, {"pag": 1, "nReg": 20},
            {"estado": "activo"}, {"estado": "abierto"}, {}
        ],
        "partidas":    [
            {"codProyecto": "?", "num": 50}, {"codProyecto": "?"},
            {"num": 50}, {"nReg": 50}, {}
        ],
        "proordutil":  [
            {"codProyecto": "?", "num": 20}, {"codProyecto": "?"},
            {"num": 20}, {"nReg": 20}, {}
        ],
        "proordprev":  [
            {"codProyecto": "?", "num": 20}, {"codProyecto": "?"},
            {"num": 20}, {"nReg": 20}, {}
        ],
        "reporden":    [
            {"num": 20}, {"nReg": 20}, {"pag": 1, "num": 20}, {"pag": 1, "nReg": 20},
            {"estado": "abierta"}, {}
        ],
        "repordutil":  [
            {"codOrden": "?", "num": 20}, {"codOrden": "?"}, {"num": 20}, {"nReg": 20}, {}
        ],
        "repobjetos":  [
            {"num": 50}, {"nReg": 50}, {"pag": 1, "num": 50}, {"pag": 1, "nReg": 50}, {}
        ],
        "repinst":     [
            {"num": 50}, {"nReg": 50}, {"pag": 1, "num": 50}, {}
        ],
        "tipostrabajo": [
            {"num": 100}, {"nReg": 100}, {"pag": 1, "num": 100}, {"pag": 1, "nReg": 100}, {}
        ],
        "clientes":    [
            {"num": 50}, {"nReg": 50}, {"pag": 1, "num": 50}, {"pag": 1, "nReg": 50}, {}
        ],
        "articulos":   [
            {"num": 50}, {"nReg": 50}, {"pag": 1, "num": 50}, {}
        ],
        "recursos":    [
            {"num": 50}, {"nReg": 50}, {"pag": 1, "num": 50}, {}
        ],
        "proveedores": [
            {"num": 50}, {"nReg": 50}, {"pag": 1, "num": 50}, {}
        ],
        "ordenfab":    [
            {"num": 20}, {"nReg": 20}, {"pag": 1, "num": 20}, {}
        ],
    }
    def sonda_clase(self, clase: str, params_extra: dict = None) -> dict:
        """Solo lectura: permiso+info+browse(variantes). Nunca escribe."""
        if not self.session_active:
            return {"success": False, "error": "Sin sesión activa."}
        from backend.modules.api_explorer.api_catalogue_full import get_campos_clase
        _NL = ("licencia", "no dispone", "sin licencia")
        res = {"clase":clase,"timestamp":datetime.now().isoformat(),"modo":"mock" if self.use_mock else "real",
               "empresa":self.session_empresa,"usuario":self.session_usuario,
               "intentos":[],"mejor_resultado":None,"datos_reales":[],"campos_servidor":[],
               "total_registros":None,"operaciones_confirmadas":[],"causa_final":"","explicacion_final":"",
               "campos_doc":get_campos_clase().get(clase,[])}
        # permiso
        try:
            raw_p,ms=self._client().permiso(self.ssid1,self.ssid2,clase)
            pc=raw_p.get("code"); pd=str(raw_p.get("data",""))
            if pc==0:
                tip="✅ Permiso OK — licencia y acceso confirmados"
                d2=raw_p.get("data",{}); ops=d2 if isinstance(d2,dict) else raw_p
                for op in ("browse","read","new","edit","write","cancel","delete","imputaPro"):
                    if ops.get(op) is True: res["operaciones_confirmadas"].append(op)
            elif pc==1: tip="🚫 SIN LICENCIA (code=1)"
            elif pc==2: tip="🔒 SIN PERMISO USUARIO (code=2)"
            elif pc==5: tip=("🚫 SIN LICENCIA: " if any(k in pd.lower() for k in _NL) else "⚙️ code=5: ")+pd[:120]
            elif pc==6: tip="🔵 Accesible — browse necesita parámetros (code=6)"
            else: tip=f"⚠️ code={pc}: {pd[:100]}"
            res["intentos"].append({"operacion":"permiso","params":{},"code":pc,"data_raw":pd[:200],"ms":round(ms),"interpretacion":tip,"n_items":0})
        except Exception as e:
            res["intentos"].append({"operacion":"permiso","params":{},"code":-1,"data_raw":str(e)[:150],"ms":0,"interpretacion":f"❌ {e}","n_items":0})
        # info
        try:
            raw_i,ms=self._client().info(self.ssid1,self.ssid2,clase)
            ic=raw_i.get("code")
            if ic==0:
                fl=raw_i.get("fields") or raw_i.get("data") or raw_i.get("columns") or []
                if isinstance(fl,list): res["campos_servidor"]=fl[:50]; ti=f"✅ INFO OK — {len(fl)} campos reales del servidor"
                elif isinstance(fl,dict): res["campos_servidor"]=[{"n":k,"tipo":str(v)} for k,v in fl.items()][:50]; ti=f"✅ INFO OK — {len(fl)} campos"
                else: ti="✅ INFO OK (estructura no estándar)"
            else: ti=f"ℹ️ info code={ic}: {str(raw_i.get('data',''))[:100]}"
            res["intentos"].append({"operacion":"info","params":{},"code":ic,"data_raw":str(raw_i.get("data",""))[:300],"ms":round(ms),"interpretacion":ti,"n_items":0})
        except Exception as e:
            res["intentos"].append({"operacion":"info","params":{},"code":-1,"data_raw":str(e)[:150],"ms":0,"interpretacion":f"❌ {e}","n_items":0})
        # browse variantes
        estrategias=list(self._SONDA_PARAMS.get(clase,[{"num":20},{}]))
        if params_extra: estrategias.insert(0,params_extra)
        ok=False
        for prm in estrategias:
            if ok: break
            try:
                raw_b,ms=self._client().browse(self.ssid1,self.ssid2,clase,dict(prm))
                bc=raw_b.get("code"); items=raw_b.get("items") or raw_b.get("data") or []
                total=raw_b.get("total"); n=len(items) if isinstance(items,list) else 0
                bd=str(raw_b.get("data",""))
                if bc==0:
                    tb=f"✅ DATOS REALES — {n} registros"+(f" (total BD: {total})" if total is not None else "")
                    if isinstance(items,list) and items:
                        res["datos_reales"]=items[:10]; res["total_registros"]=total; res["mejor_resultado"]=prm; ok=True
                elif bc==6: tb=f"🔵 code=6 — '{bd[:80]}'"
                elif bc==5:
                    tb=("🚫 SIN LICENCIA: " if any(k in bd.lower() for k in _NL) else "⚙️ code=5: ")+bd[:100]
                    res["intentos"].append({"operacion":"browse","params":prm,"code":bc,"data_raw":bd[:200],"ms":round(ms),"interpretacion":tb,"n_items":n})
                    if any(k in bd.lower() for k in _NL): break
                    continue
                else: tb=f"⚠️ code={bc}: {bd[:100]}"
                res["intentos"].append({"operacion":"browse","params":prm,"code":bc,"data_raw":bd[:200],"ms":round(ms),"interpretacion":tb,"n_items":n})
                time.sleep(0.1)
            except Exception as e:
                res["intentos"].append({"operacion":"browse","params":prm,"code":-1,"data_raw":str(e)[:150],"ms":0,"interpretacion":f"❌ {e}","n_items":0})
        # clasificación final
        first=res["intentos"][0] if res["intentos"] else {}
        last_b=next((x for x in reversed(res["intentos"]) if x["operacion"]=="browse"),{})
        info_i=next((x for x in res["intentos"] if x["operacion"]=="info"),{})
        ef={"permiso_code":first.get("code"),"permiso_raw":{"data":first.get("data_raw","")},"browse_code":last_b.get("code"),"browse_raw":{"data":last_b.get("data_raw","")},"info_code":info_i.get("code"),"muestra":res["datos_reales"],"campos_reales":res["campos_servidor"]}
        res["causa_final"] = _clasificar_causa(ef)
        res["explicacion_final"] = _explicar_causa(ef, self.use_mock)
        res["success"] = True
        # Guardar en log de sondas persistente
        self._registrar_sonda(res)
        return res

    # ──────────────────────────────────────────────────────────────────
    # PERFILES: qué clases/módulos son relevantes para cada rol
    # ──────────────────────────────────────────────────────────────────
    PERFILES = {
        "gerente": {
            "label": "Gerente / Dirección", "emoji": "📊",
            "desc": "Resumen ejecutivo de valor de negocio y aplicaciones posibles. Sin tecnicismos.",
            "clases_foco": [], "modulos_foco": [],
            "incluir_apps": True, "incluir_tecnico": False, "incluir_raw": False,
        },
        "ingeniero": {
            "label": "Ingeniero / Técnico", "emoji": "🔧",
            "desc": "Detalle de clases, operaciones, campos reales y causas técnicas.",
            "clases_foco": [], "modulos_foco": ["Gestión de Proyectos", "Reparaciones", "Maestros"],
            "incluir_apps": True, "incluir_tecnico": True, "incluir_raw": True,
        },
        "sas": {
            "label": "Administración / SAS", "emoji": "📋",
            "desc": "Permisos, clases disponibles y configuración. Qué funciona y qué no.",
            "clases_foco": [], "modulos_foco": [],
            "incluir_apps": False, "incluir_tecnico": True, "incluir_raw": False,
        },
        "almacen": {
            "label": "Almacén / Compras", "emoji": "📦",
            "desc": "Foco en compras, materiales, artículos y vinculación a obras.",
            "clases_foco": ["articulos", "proveedores", "docalbcom", "docfaccom", "docpedcom"],
            "modulos_foco": ["Documentos de Compra", "Maestros"],
            "incluir_apps": True, "incluir_tecnico": False, "incluir_raw": False,
        },
        "operario": {
            "label": "Operario / Campo", "emoji": "👷",
            "desc": "Qué puede hacer en su trabajo diario con la aplicación.",
            "clases_foco": ["proyectos", "partidas", "proordutil", "articulos", "recursos"],
            "modulos_foco": ["Gestión de Proyectos"],
            "incluir_apps": True, "incluir_tecnico": False, "incluir_raw": False,
        },
        "mantenimiento": {
            "label": "Mantenimiento / SAT", "emoji": "🛠️",
            "desc": "Foco en reparaciones, equipos, instalaciones y tipos de trabajo.",
            "clases_foco": ["reporden", "repobjetos", "repinst", "tipostrabajo", "repordutil"],
            "modulos_foco": ["Reparaciones"],
            "incluir_apps": True, "incluir_tecnico": False, "incluir_raw": False,
        },
        "desarrollador": {
            "label": "Desarrollador / Integrador", "emoji": "💻",
            "desc": "Todo: campos, códigos, operaciones, causas, raw JSON. Sin filtros.",
            "clases_foco": [], "modulos_foco": [],
            "incluir_apps": True, "incluir_tecnico": True, "incluir_raw": True,
        },
    }

    # ──────────────────────────────────────────────────────────────────
    # NIVELES: profundidad de detalle y lenguaje del informe
    # ──────────────────────────────────────────────────────────────────
    NIVELES = {
        "principiante": {
            "label": "Principiante", "emoji": "🟢",
            "desc": "Lenguaje muy sencillo. Sin términos técnicos. Solo lo esencial.",
            "mostrar_codigos": False, "mostrar_campos": False,
            "mostrar_causa_tecnica": False, "mostrar_operaciones": False,
            "max_clases_no_disp": 3,
        },
        "normal": {
            "label": "Normal", "emoji": "🔵",
            "desc": "Lenguaje accesible con algo de detalle.",
            "mostrar_codigos": False, "mostrar_campos": False,
            "mostrar_causa_tecnica": True, "mostrar_operaciones": False,
            "max_clases_no_disp": 10,
        },
        "avanzado": {
            "label": "Avanzado", "emoji": "🟡",
            "desc": "Todo el detalle funcional: operaciones, causas, registros. Sin JSON raw.",
            "mostrar_codigos": True, "mostrar_campos": True,
            "mostrar_causa_tecnica": True, "mostrar_operaciones": True,
            "max_clases_no_disp": 99,
        },
        "tecnico": {
            "label": "Técnico", "emoji": "🟠",
            "desc": "Máximo detalle: campos reales del servidor, códigos exactos, causas técnicas.",
            "mostrar_codigos": True, "mostrar_campos": True,
            "mostrar_causa_tecnica": True, "mostrar_operaciones": True,
            "max_clases_no_disp": 99,
        },
        "raw": {
            "label": "Raw / Debug", "emoji": "🔴",
            "desc": "JSON completo del discover_all. Para depuración y auditoría exhaustiva.",
            "mostrar_codigos": True, "mostrar_campos": True,
            "mostrar_causa_tecnica": True, "mostrar_operaciones": True,
            "max_clases_no_disp": 99,
        },
    }


    def generar_informe_perfil(self, perfil: str, nivel: str) -> dict:
        """Informe filtrado por perfil y nivel. Carga cache desde disco si disponible."""
        self._cargar_discover_cache()
        dr = getattr(self, '_last_discover', None)
        if not dr:
            return {"error": "Ejecuta primero 'Descubrir todo'.", "texto": ""}
        pcfg = self.PERFILES.get(perfil, self.PERFILES["gerente"])
        ncfg = self.NIVELES.get(nivel, self.NIVELES["normal"])
        clases_all = dr.get("clases", {})
        ts = dr.get("timestamp", "")[:19].replace("T", " ")
        empresa = dr.get("sesion", {}).get("empresa", "?")
        usuario = dr.get("sesion", {}).get("usuario", "?")
        use_mock = dr.get("use_mock", True)
        modo = "BD SIMULADA" if use_mock else "API REAL"
        DESC = {
            "proyectos":"Obras/Proyectos","partidas":"Capítulos y Partidas",
            "proordutil":"Costes reales imputados","proordprev":"Costes previstos",
            "reporden":"Órdenes de reparación","repobjetos":"Equipos reparables",
            "repinst":"Instalaciones","tipostrabajo":"Tipos de trabajo",
            "repordutil":"Materiales y horas","articulos":"Artículos/materiales",
            "recursos":"Recursos","proveedores":"Proveedores","clientes":"Clientes",
            "docalbcom":"Albaranes de compra","docfaccom":"Facturas de compra",
            "docpedcom":"Pedidos de compra","ordenfab":"Órdenes de fabricación",
        }
        foco = set(pcfg.get("clases_foco", []))
        clases_f = {c: d for c, d in clases_all.items() if not foco or c in foco}
        grupos: dict = {}
        for c, d in clases_f.items():
            grupos.setdefault(d.get("causa_real", _clasificar_causa(d)), []).append(c)
        lim = ncfg["max_clases_no_disp"]
        con_acc = grupos.get("acceso_confirmado", [])
        req_p   = grupos.get("requiere_parametros", [])
        sin_l   = grupos.get("sin_licencia", [])[:lim]
        sin_p   = grupos.get("sin_permiso_usuario", [])[:lim]
        cfg_i   = grupos.get("config_incompleta", [])[:lim]
        ines    = grupos.get("respuesta_inesperada", [])[:lim]
        det = {}
        for c, d in clases_f.items():
            ops = list(d.get("permiso_ops", {}).keys()) if ncfg["mostrar_operaciones"] else []
            cr = d.get("campos_reales", []) if ncfg["mostrar_campos"] else []
            nms = []
            for cf in cr[:15]:
                n = cf.get("n") or cf.get("nombre") or cf.get("field")
                if not n and cf:
                    v = list(cf.values()); n = str(v[0]) if v else ""
                if n: nms.append(str(n))
            det[c] = {
                "desc": DESC.get(c, c),
                "causa_real": d.get("causa_real", _clasificar_causa(d)),
                "causa_explicacion": d.get("causa_explicacion", _explicar_causa(d, use_mock)) if ncfg["mostrar_causa_tecnica"] else "",
                "operaciones": ops, "campos": nms,
                "total_registros": d.get("total_registros"), "muestra_n": len(d.get("muestra", [])),
                "permiso_code": d.get("permiso_code") if ncfg["mostrar_codigos"] else None,
                "browse_code":  d.get("browse_code")  if ncfg["mostrar_codigos"] else None,
                "info_code":    d.get("info_code")    if ncfg["mostrar_codigos"] else None,
            }
        apps = self._calcular_apps(con_acc, req_p) if pcfg["incluir_apps"] else []
        secc = {"con_acceso":con_acc,"requiere_parametros":req_p,
                "sin_licencia":sin_l,"sin_permiso":sin_p,
                "config_incompleta":cfg_i,"respuesta_inesperada":ines}
        sep = "="*72
        cab = (f"{sep}\nINFORME — Perfil:{pcfg['emoji']}{pcfg['label']} | Nivel:{ncfg['emoji']}{ncfg['label']}\n"
               f"Empresa:{empresa} Usuario:{usuario} Generado:{ts} Modo:{modo}\n"
               f"{pcfg['desc']} / {ncfg['desc']}\n{sep}\n")
        body = self._generar_txt(ts,empresa,usuario,modo,det,secc,apps,DESC,sep)
        idx = body.find("\n=== "); txt = cab+(body[idx:] if idx>0 else body)
        if nivel=="raw":
            import json as _j
            txt += f"\n{sep}\n=== RAW ===\n"+_j.dumps(dr,indent=2,ensure_ascii=False,default=str)[:40000]+f"\n{sep}\n"
        gg:dict={}
        for c,d in clases_all.items(): gg.setdefault(d.get("causa_real",_clasificar_causa(d)),[]).append(c)
        return {
            "texto":txt,"timestamp":ts,"empresa":empresa,"usuario":usuario,
            "modo":modo,"use_mock":use_mock,
            "perfil":perfil,"perfil_label":pcfg["label"],"perfil_emoji":pcfg["emoji"],"perfil_desc":pcfg["desc"],
            "nivel":nivel,"nivel_label":ncfg["label"],"nivel_emoji":ncfg["emoji"],"nivel_desc":ncfg["desc"],
            "secciones":secc,"detalles":det,"apps":apps,
            "incluir_tecnico":pcfg["incluir_tecnico"],"mostrar_codigos":ncfg["mostrar_codigos"],
            "es_raw":nivel=="raw","raw_discover":dr if nivel=="raw" else None,
            "totales":{"con_acceso":len(con_acc),"requiere_parametros":len(req_p),
                       "sin_licencia":len(gg.get("sin_licencia",[])),"sin_permiso":len(gg.get("sin_permiso_usuario",[])),
                       "total_filtrado":len(clases_f),"total_global":len(clases_all)},
            "perfiles_disponibles":{k:{"label":v["label"],"emoji":v["emoji"],"desc":v["desc"]} for k,v in self.PERFILES.items()},
            "niveles_disponibles":{k:{"label":v["label"],"emoji":v["emoji"],"desc":v["desc"]} for k,v in self.NIVELES.items()},
        }


_svc:Optional[ApiExplorerService]=None
def get_service()->ApiExplorerService:
    global _svc
    if _svc is None: _svc=ApiExplorerService()
    return _svc
