"""BD Clone - Servicio SQL directo sobre Firebird real. Principios DEVIA."""
from __future__ import annotations
import json, logging, time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings
from backend.core.factory.db_factory import DBFactory

logger = logging.getLogger(__name__)
_DATA_DIR     = Path(__file__).parent / "data"
_HISTORY_FILE = _DATA_DIR / "_history.json"
_CATALOG_FILE = _DATA_DIR / "_catalog_cache.json"
_CATALOG_TTL  = 3600
MAX_ROWS_SELECT = 500
MAX_HISTORY     = 200


def _guardar_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.warning(f"[bd_clone] guardar {path.name}: {exc}")


def _cargar_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[bd_clone] cargar {path.name}: {exc}")
    return default


def _rows_to_safe(rows):
    return [
        {k: str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v
         for k, v in r.items()}
        for r in rows
    ]


def _get_driver(db_params=None):
    """Obtiene y conecta el FirebirdDriver (patron DEVIA)."""
    if db_params:
        p = dict(db_params)
        if "username" in p and "user" not in p:
            p["user"] = p.pop("username")
        cfg = DBConfig(**p)
    else:
        if not settings.DB_NAME:
            raise ValueError("DB_NAME no configurado en el .env.")
        cfg = DBConfig(
            host=settings.DB_HOST, port=settings.DB_PORT,
            database=settings.DB_NAME, user=settings.DB_USER,
            password=settings.DB_PASSWORD, charset="latin1",
        )
    drv = DBFactory.get_driver("firebird")
    drv.connect(cfg)
    return drv


# ── BDCloneService ─────────────────────────────────────────────────────────────
class BDCloneService:
    """Servicio singleton para BD Clone. Solo lectura por defecto."""

    def __init__(self):
        self.modo_escritura = False
        self._history = _cargar_json(_HISTORY_FILE, [])
        self._catalog_cache = _cargar_json(_CATALOG_FILE, {})

    def get_status(self):
        db_cfg = bool(settings.DB_NAME)
        return {
            "db_configurada": db_cfg,
            "db_host": settings.DB_HOST if db_cfg else "(no configurado)",
            "db_name_short": settings.DB_NAME[-40:] if settings.DB_NAME else "(no configurado)",
            "db_port": settings.DB_PORT, "db_user": settings.DB_USER,
            "modo_escritura": self.modo_escritura, "max_rows": MAX_ROWS_SELECT,
            "historial_entradas": len(self._history),
        }

    def probar_conexion(self):
        t0 = time.time()
        SQL = "SELECT COUNT(*) AS N FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0"
        try:
            drv = _get_driver()
            try:
                rows = drv.execute_query(SQL)
                n_tablas = int(rows[0].get("N", rows[0].get("n", 0))) if rows else 0
            finally:
                drv.disconnect()
            ms = round((time.time() - t0) * 1000)
            return {"ok": True, "ms": ms, "n_tablas": n_tablas,
                    "db_host": settings.DB_HOST,
                    "db_name_short": settings.DB_NAME[-40:] if settings.DB_NAME else ""}
        except Exception as exc:
            ms = round((time.time() - t0) * 1000)
            return {"ok": False, "ms": ms,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    "db_host": settings.DB_HOST,
                    "db_name_short": settings.DB_NAME[-40:] if settings.DB_NAME else ""}

    def get_catalog(self, force_refresh=False):
        """Lista tablas de usuario. Cache 1 hora."""
        ahora = time.time()
        cached_ts = self._catalog_cache.get("ts", 0)
        if not force_refresh and (ahora - cached_ts) < _CATALOG_TTL and self._catalog_cache.get("tablas"):
            return {"tablas": self._catalog_cache["tablas"],
                    "total": len(self._catalog_cache["tablas"]),
                    "desde_cache": True,
                    "cache_ts": datetime.fromtimestamp(cached_ts).isoformat()}
        SQL_CAT = (
            "SELECT TRIM(r.RDB$RELATION_NAME) AS TABLA,"
            " COUNT(f.RDB$FIELD_NAME) AS N_COLS"
            " FROM RDB$RELATIONS r"
            " LEFT JOIN RDB$RELATION_FIELDS f"
            "   ON TRIM(f.RDB$RELATION_NAME) = TRIM(r.RDB$RELATION_NAME)"
            " WHERE r.RDB$SYSTEM_FLAG = 0"
            " GROUP BY r.RDB$RELATION_NAME"
            " ORDER BY r.RDB$RELATION_NAME"
        )
        try:
            drv = _get_driver()
            try:
                rows_tablas = drv.execute_query(SQL_CAT)
            finally:
                drv.disconnect()
            tablas = []
            for row in rows_tablas:
                nombre = (row.get("TABLA") or row.get("tabla") or "").strip()
                n_cols = int(row.get("N_COLS") or row.get("n_cols") or 0)
                if nombre:
                    tablas.append({"nombre": nombre, "n_columnas": n_cols, "n_registros": None})
            self._catalog_cache = {"ts": ahora, "tablas": tablas}
            _guardar_json(_CATALOG_FILE, self._catalog_cache)
            return {"tablas": tablas, "total": len(tablas), "desde_cache": False}
        except Exception as exc:
            return {"tablas": [], "total": 0, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}

    def get_tabla_detalle(self, tabla):
        """Columnas + conteo + primeras 5 filas."""
        tabla = tabla.strip().upper()
        t0 = time.time()
        SQL_COLS = (
            "SELECT TRIM(f.RDB$FIELD_NAME) AS CAMPO,"
            " f.RDB$FIELD_POSITION AS POSICION,"
            " TRIM(tp.RDB$TYPE_NAME) AS TIPO"
            " FROM RDB$RELATION_FIELDS f"
            " LEFT JOIN RDB$FIELDS fd ON fd.RDB$FIELD_NAME = f.RDB$FIELD_SOURCE"
            " LEFT JOIN RDB$TYPES tp ON tp.RDB$TYPE = fd.RDB$FIELD_TYPE"
            "   AND tp.RDB$FIELD_NAME = 'RDB$FIELD_TYPE'"
        )
        try:
            drv = _get_driver()
            try:
                cols_rows = drv.execute_query(
                    SQL_COLS + f" WHERE TRIM(f.RDB$RELATION_NAME) = '{tabla}' ORDER BY f.RDB$FIELD_POSITION"
                )
                columnas = [
                    {"campo": (r.get("CAMPO") or r.get("campo") or "").strip(),
                     "posicion": r.get("POSICION") or r.get("posicion") or 0,
                     "tipo": (r.get("TIPO") or r.get("tipo") or "UNKNOWN").strip()}
                    for r in cols_rows
                    if (r.get("CAMPO") or r.get("campo") or "").strip()
                ]
                try:
                    cnt = drv.execute_query(f"SELECT COUNT(*) AS N FROM {tabla}")
                    n_registros = int(cnt[0].get("N") or cnt[0].get("n") or 0) if cnt else 0
                except Exception:
                    n_registros = None
                try:
                    muestra = _rows_to_safe(drv.execute_query(f"SELECT FIRST 5 * FROM {tabla}"))
                except Exception:
                    muestra = []
            finally:
                drv.disconnect()
            ms = round((time.time() - t0) * 1000)
            return {"tabla": tabla, "columnas": columnas,
                    "n_registros": n_registros, "muestra": muestra, "ms": ms}
        except Exception as exc:
            ms = round((time.time() - t0) * 1000)
            return {"tabla": tabla, "columnas": [], "n_registros": None,
                    "muestra": [], "ms": ms,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}"}

    @staticmethod
    def _inyectar_first(sql, limit):
        """Inyecta FIRST N en SELECT Firebird si no tiene ya limite."""
        up = sql.upper().lstrip()
        if up.startswith("SELECT FIRST") or up.startswith("SELECT SKIP"):
            return sql
        if up.startswith("SELECT"):
            return "SELECT FIRST " + str(limit) + sql[len("SELECT"):]
        return sql

    def ejecutar_sql(self, sql):
        """Ejecuta SQL libre. Solo SELECT salvo modo_escritura activo."""
        sql_clean = sql.strip()
        if not sql_clean:
            return {"ok": False, "error": "SQL vacio"}
        sql_upper = sql_clean.upper().lstrip()
        es_select = sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")
        es_esc = any(
            sql_upper.startswith(k)
            for k in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "EXECUTE")
        )
        if es_esc and not self.modo_escritura:
            self._add_history(sql_clean, ok=False, ms=0, n_rows=0, error="BLOQUEADO")
            return {"ok": False, "error": "Escritura bloqueada. Activa modo escritura.", "bloqueado": True}
        t0 = time.time()
        try:
            drv = _get_driver()
            try:
                if es_select:
                    sql_exec = self._inyectar_first(sql_clean, MAX_ROWS_SELECT)
                    rows = _rows_to_safe(drv.execute_query(sql_exec)[:MAX_ROWS_SELECT])
                    n_rows = len(rows)
                    cols = list(rows[0].keys()) if rows else []
                    ms = round((time.time() - t0) * 1000)
                    self._add_history(sql_clean, ok=True, ms=ms, n_rows=n_rows)
                    return {"ok": True, "filas": rows, "n_filas": n_rows,
                            "columnas": cols, "ms": ms, "truncado": n_rows >= MAX_ROWS_SELECT}
                else:
                    affected = drv.execute_command(sql_clean)
                    ms = round((time.time() - t0) * 1000)
                    self._add_history(sql_clean, ok=True, ms=ms, n_rows=affected, nota="ESCRITURA")
                    return {"ok": True, "filas_afectadas": affected, "ms": ms, "escritura": True}
            finally:
                drv.disconnect()
        except Exception as exc:
            ms = round((time.time() - t0) * 1000)
            err = f"{type(exc).__name__}: {str(exc)[:400]}"
            self._add_history(sql_clean, ok=False, ms=ms, n_rows=0, error=err)
            return {"ok": False, "error": err, "ms": ms}

    def get_consultas_predefinidas(self):
        """Consultas de query_library compatibles con Firebird real."""
        try:
            from backend.modules.db_simulator.query_library import get_all_queries
            predefinidas = []
            for q in get_all_queries():
                sql = (q.get("sql") or "").strip()
                if not sql:
                    continue
                if any(kw in sql.upper() for kw in ("STRFTIME", "JULIANDAY")):
                    continue
                predefinidas.append({
                    "id": q.get("id", ""),
                    "nombre": q.get("nombre", q.get("name", "")),
                    "desc_simple": q.get("desc_simple", ""),
                    "dept": q.get("dept", []),
                    "tipo": q.get("tipo", ""),
                    "urgencia": q.get("urgencia", ""),
                    "sql": sql,
                    "params": q.get("params", []),
                })
            return predefinidas
        except Exception as exc:
            logger.warning(f"[bd_clone] Error consultas predefinidas: {exc}")
            return []

    def ejecutar_predefinida(self, query_id, params):
        """Ejecuta consulta predefinida con sustitucion de parametros."""
        try:
            from backend.modules.db_simulator.query_library import get_query_by_id
            q = get_query_by_id(query_id)
            if not q:
                return {"ok": False, "error": f"Consulta no encontrada: {query_id}"}
            sql = q.get("sql", "").strip()
            if not sql:
                return {"ok": False, "error": "Consulta sin SQL"}
            for k, v in params.items():
                sql = sql.replace(f"{{{{{k}}}}}", str(v)).replace(f":{k}", str(v))
            return self.ejecutar_sql(sql)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}

    def diagnostico(self):
        """Conexion + conteo tablas clave. Sin valores de negocio."""
        TABLAS = [
            "PROYECTOS", "REPCAB", "REPOBJETO", "REPINSTALACION",
            "RECURSO", "ARTICULO", "CLIENTE", "PROVEED",
            "DOCCAB", "DOCLIN", "PRESUPROYE",
        ]
        result = {
            "db_host": settings.DB_HOST, "db_port": settings.DB_PORT,
            "db_name_short": settings.DB_NAME[-40:] if settings.DB_NAME else "",
            "db_user": settings.DB_USER, "db_configurada": bool(settings.DB_NAME),
            "conexion_ok": False, "error": None, "tablas_clave": {},
        }
        if not settings.DB_NAME:
            result["error"] = "DB_NAME vacio en el .env"
            return result
        t0 = time.time()
        try:
            drv = _get_driver()
            result["conexion_ok"] = True
            for tabla in TABLAS:
                try:
                    rows = drv.execute_query(f"SELECT COUNT(*) AS N FROM {tabla}")
                    cnt = int(rows[0].get("N") or rows[0].get("n") or 0) if rows else 0
                    result["tablas_clave"][tabla] = {"ok": True, "n": cnt}
                except Exception as exc:
                    result["tablas_clave"][tabla] = {"ok": False, "error": str(exc)[:80]}
            drv.disconnect()
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        result["ms"] = round((time.time() - t0) * 1000)
        return result

    def _add_history(self, sql, ok, ms, n_rows, error=None, nota=None):
        entry = {"ts": datetime.now().isoformat(), "sql_preview": sql[:120],
                 "ok": ok, "ms": ms, "n_filas": n_rows}
        if error:
            entry["error"] = error[:200]
        if nota:
            entry["nota"] = nota
        self._history.insert(0, entry)
        self._history = self._history[:MAX_HISTORY]
        _guardar_json(_HISTORY_FILE, self._history)

    def get_history(self, limit=50):
        return self._history[:min(limit, MAX_HISTORY)]

    def clear_history(self):
        self._history = []
        _guardar_json(_HISTORY_FILE, self._history)

    def activar_escritura(self, confirmacion):
        if confirmacion != "ACTIVAR ESCRITURA BD":
            return {"ok": False, "error": "Confirmacion incorrecta. Escribe: ACTIVAR ESCRITURA BD"}
        self.modo_escritura = True
        return {"ok": True, "modo_escritura": True, "mensaje": "Modo escritura ACTIVADO."}

    def desactivar_escritura(self):
        self.modo_escritura = False
        return {"ok": True, "modo_escritura": False, "mensaje": "Modo escritura desactivado."}


# ── Singleton ──────────────────────────────────────────────────────────────────
_service_instance = None


def get_service():
    global _service_instance
    if _service_instance is None:
        _service_instance = BDCloneService()
    return _service_instance
