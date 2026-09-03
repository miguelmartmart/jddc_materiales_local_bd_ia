"""Servicio del modulo API Explorer para DEVIA. Sesion stateful + mock/real."""
import logging, time, random, uuid, os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from backend.core.config.settings import settings

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
        self.emp = emp
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
        """Campos comunes: ssid1, ssid2."""
        return {"ssid1": self._s1, "ssid2": self._s2}

    def login(self, empresa, usuario, password):
        """
        Login segun doc: method=login&empr=<n>&user=<u>&pass=<sha1_base64>
        'empr' puede ser numero de empresa o codigo. Si es texto, se envia tal cual.
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


class ApiExplorerService:
    def __init__(self):
        self.ssid1=""; self.ssid2=""; self.session_active=False
        self.session_empresa=""; self.session_usuario=""; self.session_started=None
        self.use_mock=True; self.modo_escritura=False
        self._mock=MockApiClient(); self._real:Optional[RealApiClient]=None
        self._history:List[Dict]=[]; self._matrix:Dict[str,Dict]={}

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
        if raw.get("error") and code==-1: e="falla"; m=f"Error: {raw.get('error')}"
        elif hs==401: e="sin_permiso"; m="Sin autorizacion (401)"
        elif hs==403: e="sin_permiso"; m="Acceso denegado (403)"
        elif hs not in (200,201): e="falla"; m=f"HTTP {hs}"
        elif code==0: e="ok"; m="Operacion exitosa. code=0"
        elif code==1: e="sin_licencia"; m="Sin licencia (code=1)."
        elif code==2: e="sin_permiso"; m="Sin permiso (code=2)."
        elif code is not None: e="falla"; m=f"Error: code={code}"
        else: e="ok"; m="HTTP 200 sin code interno."
        r={"id":str(uuid.uuid4())[:8],"timestamp":datetime.now().isoformat(),"clase":clase,"operacion":op,"params":params,"http_status":hs,"code":code,"json":raw,"duracion_ms":round(ms,1),"estado":e,"mensaje":m,"use_mock":self.use_mock,"nota_doc":NOTAS_DOC.get((clase,op),""),"nota_seguridad":NOTAS_SEGURIDAD.get((clase,op),"")}
        self._history.append(r)
        if len(self._history)>200: self._history=self._history[-200:]
        if clase not in self._matrix: self._matrix[clase]={}
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
    def get_history(self,limit=50): return list(reversed(self._history))[:limit]
    def get_matrix(self): return self._matrix
    def get_catalogue(self): return CLASES_POR_MODULO
    def clear_history(self): self._history.clear()
    def resumen_historial(self): return {"total":len(self._history),"ok":sum(1 for r in self._history if r["estado"]=="ok"),"falla":sum(1 for r in self._history if r["estado"]=="falla"),"sin_permiso":sum(1 for r in self._history if r["estado"]=="sin_permiso"),"sin_licencia":sum(1 for r in self._history if r["estado"]=="sin_licencia")}


_svc:Optional[ApiExplorerService]=None
def get_service()->ApiExplorerService:
    global _svc
    if _svc is None: _svc=ApiExplorerService()
    return _svc
