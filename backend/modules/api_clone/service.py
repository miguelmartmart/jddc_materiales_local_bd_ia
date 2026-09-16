"""API Clone Service — SQL Firebird real. CERO MOCKS."""
from __future__ import annotations
import json, logging, time, uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings
from backend.core.factory.db_factory import DBFactory
from backend.modules.api_clone.queries import (
    CLASE_TABLA_MAP, CLASE_WHERE, CLASE_MODULO, CLASE_OPERACIONES,
    CLASE_COLS_BROWSE, CLASE_COLS_READ, CLASE_PARAM_REQUERIDO,
    PARAM_A_COLUMNA, ALL_CLASES,
    RIESGO_OPERACION, CONFIRMACION_REQUERIDA,
    OPERACIONES_ESCRITURA_REAL, OPERACIONES_TEMPORALES,
)

logger = logging.getLogger(__name__)
_DATA_DIR     = Path(__file__).parent / "data"
_HISTORY_FILE = _DATA_DIR / "_history.json"
_MATRIX_FILE  = _DATA_DIR / "_matrix.json"
MAX_BROWSE    = 50
MAX_HISTORY   = 200


def _guardar_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.warning(f"[api_clone] guardar {path.name}: {exc}")


def _cargar_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _rows_to_safe(rows):
    return [
        {k: str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v
         for k, v in r.items()}
        for r in rows
    ]


def _get_driver():
    if not settings.DB_NAME:
        raise ValueError("DB_NAME no configurado en el .env.")
    cfg = DBConfig(host=settings.DB_HOST, port=settings.DB_PORT,
                   database=settings.DB_NAME, user=settings.DB_USER,
                   password=settings.DB_PASSWORD, charset="latin1")
    drv = DBFactory.get_driver("firebird")
    drv.connect(cfg)
    return drv

class ApiCloneService:
    """
    Replica browse/read/permiso/info/discover-all CON datos reales de Firebird.
    Ademas soporta new/edit/write/cancel/imputaPro/imputaRep segun doc mPYME v1.2.

    SISTEMA DE PROTECCION DE ESCRITURA (3 niveles):
      Nivel 0 — lectura: browse, read, permiso, info, cancel → siempre permitido
      Nivel 1 — temporal: new, edit → permitido con modo_escritura=True (no persiste)
      Nivel 2 — ESCRITURA REAL: write, imputaPro, imputaRep → requiere:
                  (a) modo_escritura=True
                  (b) confirmacion exacta == 'CONFIRMAR ESCRITURA'
                  (c) session_escritura activa (activada explicitamente)
      Nivel 3 — DESTRUCTIVO: delete → requiere ademas confirmacion='CONFIRMAR BORRADO DEFINITIVO'
    """

    def __init__(self):
        self._history = _cargar_json(_HISTORY_FILE, [])
        self._matrix  = _cargar_json(_MATRIX_FILE, {})
        self.modo_escritura: bool = False       # Habilita new/edit
        self.session_escritura: bool = False    # Habilita write/imputaPro (requiere activacion explicita)
        self._objetos_temporales: Dict = {}     # objectid -> {clase, data, ts}

    def _log(self, clase, op, params, data, ms, n=0, n_items=None, error=None):
        # n_items es alias de n para compatibilidad con las llamadas existentes
        if n_items is not None:
            n = n_items
        estado = "falla" if error else "ok"
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "clase": clase, "operacion": op, "params": params,
            "code": 0 if not error else -1, "estado": estado,
            "n_items": n, "data": data if not error else None,
            "error": error, "duracion_ms": round(ms, 1),
            "fuente": "firebird_directo",
        }
        self._history.insert(0, entry)
        self._history = self._history[:MAX_HISTORY]
        if clase not in self._matrix:
            self._matrix[clase] = {}
        self._matrix[clase][op] = {"estado": estado, "ts": entry["timestamp"]}
        _guardar_json(_HISTORY_FILE, self._history)
        _guardar_json(_MATRIX_FILE, self._matrix)
        return entry

    def _where(self, clase, params):
        clauses = []
        cw = CLASE_WHERE.get(clase)
        if cw:
            clauses.append(cw)
        col_map = PARAM_A_COLUMNA.get(clase, {})
        for p_api, valor in params.items():
            col = col_map.get(p_api)
            if col and valor and str(valor).strip():
                v = str(valor).strip().replace("'", "''")
                clauses.append(f"{col} = '{v}'")
        return " AND ".join(clauses) if clauses else ""

    def _browse_sql(self, clase, params, num=MAX_BROWSE):
        info = CLASE_TABLA_MAP.get(clase)
        if not info:
            return {"ok": False, "error": f"Clase '{clase}' no reconocida"}
        tabla, campo_pk = info[0], info[1]
        cols = CLASE_COLS_BROWSE.get(clase, "*")
        where = self._where(clase, params)
        sql = f"SELECT FIRST {num} {cols} FROM {tabla}"
        if where:
            sql += f" WHERE {where}"
        sql += f" ORDER BY {campo_pk}"
        t0 = time.time()
        try:
            drv = _get_driver()
            try:
                rows = drv.execute_query(sql)
                sql_cnt = f"SELECT COUNT(*) AS N FROM {tabla}"
                if where:
                    sql_cnt += f" WHERE {where}"
                cnt = drv.execute_query(sql_cnt)
                total = int(cnt[0].get("N") or cnt[0].get("n") or 0) if cnt else 0
            finally:
                drv.disconnect()
            return {"ok": True, "items": _rows_to_safe(rows), "total": total,
                    "ms": round((time.time()-t0)*1000), "sql": sql}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    "ms": round((time.time()-t0)*1000), "sql": sql}

    def _read_sql(self, clase, objectid):
        info = CLASE_TABLA_MAP.get(clase)
        if not info:
            return {"ok": False, "error": f"Clase '{clase}' no reconocida"}
        tabla, campo_pk = info[0], info[1]
        cols = CLASE_COLS_READ.get(clase, "*")
        val = str(objectid).strip().replace("'", "''")
        where_extra = CLASE_WHERE.get(clase, "")
        where = f"{campo_pk} = '{val}'"
        if where_extra:
            where = f"{where_extra} AND {where}"
        sql = f"SELECT {cols} FROM {tabla} WHERE {where}"
        t0 = time.time()
        try:
            drv = _get_driver()
            try:
                rows = drv.execute_query(sql)
            finally:
                drv.disconnect()
            ms = round((time.time()-t0)*1000)
            if not rows:
                return {"ok": False, "error": f"No encontrado: {campo_pk}='{objectid}'", "ms": ms}
            return {"ok": True, "data": _rows_to_safe(rows)[0], "ms": ms}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    "ms": round((time.time()-t0)*1000)}

    def _info_sql(self, clase):
        info = CLASE_TABLA_MAP.get(clase)
        if not info:
            return {"ok": False, "error": f"Clase '{clase}' no reconocida"}
        tabla = info[0]
        SQL = (
            "SELECT TRIM(f.RDB$FIELD_NAME) AS CAMPO,"
            " f.RDB$FIELD_POSITION AS POSICION,"
            " TRIM(tp.RDB$TYPE_NAME) AS TIPO"
            " FROM RDB$RELATION_FIELDS f"
            " LEFT JOIN RDB$FIELDS fd ON fd.RDB$FIELD_NAME = f.RDB$FIELD_SOURCE"
            " LEFT JOIN RDB$TYPES tp ON tp.RDB$TYPE = fd.RDB$FIELD_TYPE"
            "   AND tp.RDB$FIELD_NAME = 'RDB$FIELD_TYPE'"
            f" WHERE TRIM(f.RDB$RELATION_NAME) = '{tabla}'"
            " ORDER BY f.RDB$FIELD_POSITION"
        )
        t0 = time.time()
        try:
            drv = _get_driver()
            try:
                rows = drv.execute_query(SQL)
            finally:
                drv.disconnect()
            campos = [
                {"nombre": (r.get("CAMPO") or r.get("campo") or "").strip(),
                 "posicion": r.get("POSICION") or r.get("posicion") or 0,
                 "tipo": (r.get("TIPO") or r.get("tipo") or "UNKNOWN").strip()}
                for r in rows
                if (r.get("CAMPO") or r.get("campo") or "").strip()
            ]
            return {"ok": True, "tabla": tabla, "campos": campos, "ms": round((time.time()-t0)*1000)}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    "ms": round((time.time()-t0)*1000)}

    def permiso(self, clase):
        t0 = time.time()
        info = CLASE_TABLA_MAP.get(clase)
        if not info:
            return self._log(clase,"permiso",{},None,0,error=f"Clase '{clase}' desconocida")
        tabla = info[0]
        try:
            drv = _get_driver()
            try:
                cw = CLASE_WHERE.get(clase,"")
                sql = f"SELECT COUNT(*) AS N FROM {tabla}" + (f" WHERE {cw}" if cw else "")
                cnt = drv.execute_query(sql)
                n = int(cnt[0].get("N") or cnt[0].get("n") or 0) if cnt else 0
            finally:
                drv.disconnect()
            ms = round((time.time()-t0)*1000)
            meta = CLASE_MODULO.get(clase,{})
            data = {"objectClass":clase,"tabla_firebird":tabla,"n_registros":n,
                    "operaciones":CLASE_OPERACIONES.get(clase,[]),
                    "modulo":meta.get("modulo",""),"licencia":meta.get("licencia",""),
                    "acceso":"directo_firebird"}
            return self._log(clase,"permiso",{},data,ms,n_items=1)
        except Exception as exc:
            return self._log(clase,"permiso",{},None,round((time.time()-t0)*1000),
                             error=f"{type(exc).__name__}: {str(exc)[:200]}")

    def info(self, clase):
        t0 = time.time()
        r = self._info_sql(clase)
        ms = r.get("ms", round((time.time()-t0)*1000))
        if r["ok"]:
            return self._log(clase,"info",{},r,ms,n_items=len(r.get("campos",[])))
        return self._log(clase,"info",{},None,ms,error=r.get("error"))

    def browse(self, clase, params, num=MAX_BROWSE):
        t0 = time.time()
        pq = CLASE_PARAM_REQUERIDO.get(clase)
        if pq and not params.get(pq):
            av = {"aviso":f"'{clase}' requiere param '{pq}'","param_requerido":pq,"items":[],"total":0}
            return self._log(clase,"browse",params,av,round((time.time()-t0)*1000))
        r = self._browse_sql(clase, params, num)
        ms = r.get("ms", round((time.time()-t0)*1000))
        if r["ok"]:
            return self._log(clase,"browse",params,{"items":r["items"],"total":r["total"]},
                             ms,n_items=len(r["items"]))
        return self._log(clase,"browse",params,None,ms,error=r.get("error"))

    def read(self, clase, objectid):
        t0 = time.time()
        if not objectid:
            return self._log(clase,"read",{},None,0,error="objectid obligatorio")
        r = self._read_sql(clase, objectid)
        ms = r.get("ms",round((time.time()-t0)*1000))
        if r["ok"]:
            return self._log(clase,"read",{"objectid":objectid},r["data"],ms,n_items=1)
        return self._log(clase,"read",{"objectid":objectid},None,ms,error=r.get("error"))

    def discover_all(self, num_por_clase=5):
        """Browse en todas las clases — datos 100% reales de Firebird."""
        t0g = time.time()
        resultados = {}
        clases_ok = clases_error = total_reg = 0
        for clase in ALL_CLASES:
            t0 = time.time()
            meta = CLASE_MODULO.get(clase, {})
            entry: Dict = {"clase": clase, "modulo": meta.get("modulo",""),
                           "licencia": meta.get("licencia",""),
                           "operaciones": CLASE_OPERACIONES.get(clase,[])}
            info = CLASE_TABLA_MAP.get(clase)
            tabla = info[0] if info else "?"
            try:
                drv = _get_driver()
                try:
                    cw = CLASE_WHERE.get(clase,"")
                    sql_cnt = f"SELECT COUNT(*) AS N FROM {tabla}" + (f" WHERE {cw}" if cw else "")
                    cnt = drv.execute_query(sql_cnt)
                    n = int(cnt[0].get("N") or cnt[0].get("n") or 0) if cnt else 0
                finally:
                    drv.disconnect()
                entry["permiso_code"] = 0
                entry["n_registros"] = n
                total_reg += n
            except Exception as exc:
                entry["permiso_code"] = -1
                entry["error_permiso"] = str(exc)[:150]
                entry["n_registros"] = 0
            br = self._browse_sql(clase, {}, num_por_clase)
            if br["ok"]:
                entry["browse_code"] = 0
                entry["muestra"] = br["items"]
                entry["campos_detectados"] = list(br["items"][0].keys()) if br["items"] else []
                clases_ok += 1
            else:
                entry["browse_code"] = -1
                entry["browse_error"] = br.get("error","")[:150]
                entry["muestra"] = []
                entry["campos_detectados"] = []
                clases_error += 1
            entry["ms"] = round((time.time()-t0)*1000)
            resultados[clase] = entry
        return {
            "timestamp": datetime.now().isoformat(),
            "fuente": "firebird_directo",
            "ms_total": round((time.time()-t0g)*1000),
            "resumen": {"total_clases": len(ALL_CLASES), "clases_ok": clases_ok,
                        "clases_error": clases_error, "total_registros_bd": total_reg},
            "clases": resultados,
        }

    # ── PROTECCION DE ESCRITURA ───────────────────────────────────────────────

    def _verificar_escritura(self, op: str, confirmacion: str = "") -> Optional[str]:
        """Devuelve None si OK, string con motivo de bloqueo si no."""
        riesgo = RIESGO_OPERACION.get(op, 0)
        if riesgo == 0:
            return None
        if riesgo >= 1 and not self.modo_escritura:
            return (f"'{op}' requiere modo escritura (Paso 1). "
                    "Activa en la pestana Escritura -> 'Activar Modo Escritura'.")
        if riesgo >= 2 and not self.session_escritura:
            return (f"'{op}' es ESCRITURA REAL IRREVERSIBLE. "
                    "Requiere activar sesion de escritura (Paso 2) con 'CONFIRMAR ESCRITURA'.")
        if riesgo >= 2 and confirmacion != CONFIRMACION_REQUERIDA.get(2, ""):
            texto = CONFIRMACION_REQUERIDA[2]
            return f"'{op}' requiere confirmacion exacta en el body: '{texto}'. Recibido: '{confirmacion}'"
        if riesgo >= 3 and confirmacion != CONFIRMACION_REQUERIDA.get(3, ""):
            texto = CONFIRMACION_REQUERIDA[3]
            return f"'{op}' DESTRUCTIVO. Confirmacion: '{texto}'. Recibido: '{confirmacion}'"
        return None

    def new(self, clase: str) -> Dict:
        """Crea objeto TEMPORAL en memoria (Riesgo 1 — no persiste hasta write)."""
        t0 = time.time()
        bloqueo = self._verificar_escritura("new")
        if bloqueo:
            return self._log(clase, "new", {}, None, 0, error=f"BLOQUEADO: {bloqueo}")
        info = CLASE_TABLA_MAP.get(clase)
        if not info:
            return self._log(clase, "new", {}, None, 0, error=f"Clase '{clase}' no reconocida")
        oid = f"TMP_{clase.upper()}_{uuid.uuid4().hex[:8].upper()}"
        self._objetos_temporales[oid] = {
            "clase": clase, "tabla": info[0], "data": {}, "ts": datetime.now().isoformat(),
        }
        ms = round((time.time()-t0)*1000)
        data = {"objectid": oid, "clase": clase, "estado": "temporal",
                "nota": "NO persiste hasta 'write'. Usa 'edit' para rellenar campos. Usa 'cancel' para descartar."}
        return self._log(clase, "new", {}, data, ms, n_items=1)

    def edit(self, clase: str, objectid: str, data: Dict) -> Dict:
        """Modifica datos del objeto temporal (Riesgo 1 — no persiste hasta write)."""
        t0 = time.time()
        bloqueo = self._verificar_escritura("edit")
        if bloqueo:
            return self._log(clase, "edit", {"objectid": objectid}, None, 0, error=f"BLOQUEADO: {bloqueo}")
        if objectid not in self._objetos_temporales:
            return self._log(clase, "edit", {"objectid": objectid}, None, 0,
                             error=f"objectid '{objectid}' no encontrado. Ejecuta 'new' primero.")
        obj = self._objetos_temporales[objectid]
        obj["data"].update(data)
        obj["ts_edit"] = datetime.now().isoformat()
        ms = round((time.time()-t0)*1000)
        result = {"objectid": objectid, "clase": clase, "data_actual": obj["data"],
                  "nota": "Datos en memoria. Aun NO persistidos en BD. Usa 'write' para guardar."}
        return self._log(clase, "edit", {"objectid": objectid}, result, ms, n_items=1)

    def cancel(self, clase: str, objectid: str) -> Dict:
        """Descarta objeto temporal. Seguro (riesgo 0) — no persiste nada."""
        t0 = time.time()
        if objectid in self._objetos_temporales:
            del self._objetos_temporales[objectid]
            data = {"objectid": objectid, "estado": "cancelado",
                    "nota": "Objeto descartado. NADA guardado en BD."}
        else:
            data = {"objectid": objectid, "estado": "no_encontrado",
                    "nota": "objectid no estaba en memoria (ya cancelado o nunca creado)."}
        ms = round((time.time()-t0)*1000)
        return self._log(clase, "cancel", {"objectid": objectid}, data, ms)

    def write(self, clase: str, objectid: str, data: Dict, confirmacion: str = "") -> Dict:
        """PERSISTE en Firebird via INSERT. RIESGO 2 — IRREVERSIBLE."""
        t0 = time.time()
        bloqueo = self._verificar_escritura("write", confirmacion)
        if bloqueo:
            return self._log(clase, "write", {"objectid": objectid}, None, 0, error=f"BLOQUEADO: {bloqueo}")
        info = CLASE_TABLA_MAP.get(clase)
        if not info:
            return self._log(clase, "write", {"objectid": objectid}, None, 0, error=f"Clase '{clase}' desconocida")
        tabla = info[0]
        obj_temp = self._objetos_temporales.get(objectid, {})
        datos = {**obj_temp.get("data", {}), **data}
        if not datos:
            return self._log(clase, "write", {"objectid": objectid}, None, 0,
                             error="Sin datos. Usa 'new' + 'edit' para rellenar campos primero.")
        cols = list(datos.keys())
        vals = [str(v) if not isinstance(v, (int, float, bool, type(None))) else v for v in datos.values()]
        sql = f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({', '.join(['?' for _ in cols])})"
        try:
            drv = _get_driver()
            try:
                affected = drv.execute_command(sql, tuple(vals))
            finally:
                drv.disconnect()
            if objectid in self._objetos_temporales:
                del self._objetos_temporales[objectid]
            ms = round((time.time()-t0)*1000)
            result = {"objectid": objectid, "tabla": tabla, "filas_afectadas": affected,
                      "ADVERTENCIA": "IRREVERSIBLE — persistido en BD produccion"}
            return self._log(clase, "write", {"objectid": objectid}, result, ms, n_items=affected)
        except Exception as exc:
            ms = round((time.time()-t0)*1000)
            return self._log(clase, "write", {"objectid": objectid}, None, ms,
                             error=f"{type(exc).__name__}: {str(exc)[:400]}")

    def imputa(self, clase: str, objectid: str, accion: str,
               cod_maestro: str, cod_detalle: str = "",
               subcontrata: str = "F", confirmacion: str = "") -> Dict:
        """Imputa linea de compra a Proyecto/Reparacion. RIESGO 2 — IRREVERSIBLE."""
        t0 = time.time()
        bloqueo = self._verificar_escritura(accion, confirmacion)
        if bloqueo:
            return self._log(clase, accion, {"objectid": objectid}, None, 0, error=f"BLOQUEADO: {bloqueo}")
        if accion not in ("imputaPro", "imputaRep", "imputaFab"):
            return self._log(clase, accion, {}, None, 0, error=f"accion '{accion}' no valida")
        partes = str(objectid).split("-")
        cod_doc = partes[0]; cod_lin = partes[1] if len(partes) > 1 else "1"
        sql = ("INSERT INTO DOCLINIMPUTACION (CODDOCUMENTO, CODLINEA, CODIGO, CODPROYECTO, PARTIDA, SUBCONTRATA) "
               "VALUES (?, ?, ?, ?, ?, ?)")
        try:
            drv = _get_driver()
            try:
                affected = drv.execute_command(sql, (cod_doc, cod_lin, "1", cod_maestro, cod_detalle, subcontrata))
            finally:
                drv.disconnect()
            ms = round((time.time()-t0)*1000)
            tipo = {"imputaPro":"proyecto","imputaRep":"reparacion","imputaFab":"fabricacion"}.get(accion)
            result = {"clase": clase, "objectid": objectid, "accion": accion, "tipo": tipo,
                      "cod_maestro": cod_maestro, "cod_detalle": cod_detalle,
                      "filas_afectadas": affected, "ADVERTENCIA": "IRREVERSIBLE"}
            return self._log(clase, accion, {"objectid": objectid}, result, ms, n_items=affected)
        except Exception as exc:
            ms = round((time.time()-t0)*1000)
            return self._log(clase, accion, {"objectid": objectid}, None, ms,
                             error=f"{type(exc).__name__}: {str(exc)[:400]}")

    def activar_modo_escritura(self, conf: str) -> Dict:
        """Paso 1/2: habilita new/edit (temporales). Req: 'ACTIVAR ESCRITURA'"""
        if conf != "ACTIVAR ESCRITURA":
            return {"ok": False,
                    "error": "Escribe exactamente: ACTIVAR ESCRITURA",
                    "nota": "Paso 1 solo activa new/edit (temporales). write requiere Paso 2."}
        self.modo_escritura = True; self.session_escritura = False
        return {"ok": True, "modo_escritura": True, "session_escritura": False,
                "mensaje": "Paso 1/2 ACTIVADO. new/edit disponibles (temporales, sin persistir). "
                           "Para write/imputaPro: Paso 2 con 'CONFIRMAR ESCRITURA'."}

    def activar_session_escritura(self, conf: str) -> Dict:
        """Paso 2/2: habilita write/imputaPro (IRREVERSIBLE). Req: 'CONFIRMAR ESCRITURA'"""
        if not self.modo_escritura:
            return {"ok": False, "error": "Activa primero el Paso 1 (Activar Modo Escritura)."}
        if conf != "CONFIRMAR ESCRITURA":
            return {"ok": False, "error": "Escribe exactamente: CONFIRMAR ESCRITURA",
                    "ADVERTENCIA": "write/imputaPro son IRREVERSIBLES — modifican BD produccion."}
        self.session_escritura = True
        return {"ok": True, "modo_escritura": True, "session_escritura": True,
                "ADVERTENCIA": "SESION ESCRITURA ACTIVA. write/imputaPro DISPONIBLES y son IRREVERSIBLES. "
                               "Cada peticion requiere ademas confirmacion='CONFIRMAR ESCRITURA'."}

    def desactivar_escritura(self) -> Dict:
        """Desactiva ambos niveles. Descarta objetos temporales."""
        self.modo_escritura = False; self.session_escritura = False
        n_tmp = len(self._objetos_temporales); self._objetos_temporales.clear()
        return {"ok": True, "modo_escritura": False, "session_escritura": False,
                "objetos_temporales_descartados": n_tmp,
                "mensaje": "Escritura desactivada. Solo lectura activa."}

    def get_objetos_temporales(self) -> Dict:
        return {"total": len(self._objetos_temporales),
                "objetos": [{"objectid": oid, "clase": obj["clase"], "ts": obj["ts"],
                             "campos": list(obj["data"].keys())}
                            for oid, obj in self._objetos_temporales.items()]}

    def get_catalogue(self):
        from collections import defaultdict
        pm: Dict = defaultdict(dict)
        for clase, ops in CLASE_OPERACIONES.items():
            mod = CLASE_MODULO.get(clase,{}).get("modulo","Otros")
            pm[mod][clase] = ops
        return {"catalogue": dict(pm), "all_classes": ALL_CLASES, "fuente": "firebird_directo",
                "riesgo_operaciones": RIESGO_OPERACION,
                "confirmaciones_requeridas": CONFIRMACION_REQUERIDA}

    def get_status(self):
        return {
            "fuente": "firebird_directo",
            "db_host": settings.DB_HOST,
            "db_name_short": settings.DB_NAME[-40:] if settings.DB_NAME else "(no config)",
            "db_configurada": bool(settings.DB_NAME),
            "total_clases": len(ALL_CLASES),
            "historial_entradas": len(self._history),
            "modo_escritura": self.modo_escritura,
            "session_escritura": self.session_escritura,
            "objetos_temporales": len(self._objetos_temporales),
        }

    def get_history(self, limit=100): return self._history[:min(limit, MAX_HISTORY)]
    def get_matrix(self): return self._matrix
    def clear_history(self):
        self._history = []; self._matrix = {}
        _guardar_json(_HISTORY_FILE, self._history); _guardar_json(_MATRIX_FILE, self._matrix)


_svc = None
def get_service():
    global _svc
    if _svc is None: _svc = ApiCloneService()
    return _svc
