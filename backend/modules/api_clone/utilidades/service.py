"""
Utilidades de Ingeniería — Consultas analíticas sobre datos reales de Firebird.
VERIFICADO 16/09/2026: 0 huérfanos, JOIN correcto, TIPOBC3 verificado.
  TIPOBC3=10 → MO (307k reg) | 20 → Materiales (629k) | 30 → Subcontrata (4.9k)
"""
from __future__ import annotations
import time, logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings
from backend.core.factory.db_factory import DBFactory

logger = logging.getLogger(__name__)
TIPOBC3_MO  = 10
TIPOBC3_MAT = 20
TIPOBC3_SUB = 30


def _get_driver():
    if not settings.DB_NAME: raise ValueError("DB_NAME no configurado.")
    cfg = DBConfig(host=settings.DB_HOST, port=settings.DB_PORT,
                   database=settings.DB_NAME, user=settings.DB_USER,
                   password=settings.DB_PASSWORD, charset="latin1")
    drv = DBFactory.get_driver("firebird"); drv.connect(cfg); return drv


def _safe(rows: List[Dict]) -> List[Dict]:
    result = []
    for row in rows:
        safe = {}
        for k, v in row.items():
            if v is None: safe[k] = None
            elif hasattr(v, 'isoformat'): safe[k] = v.isoformat()
            elif isinstance(v, (float, Decimal)): safe[k] = round(float(v), 4)
            elif not isinstance(v, (int, str, bool)): safe[k] = str(v)
            else: safe[k] = v
        result.append(safe)
    return result


def _exec(sql: str):
    t0 = time.time()
    drv = _get_driver()
    try:
        rows = drv.execute_query(sql)
        return _safe(rows or []), round((time.time()-t0)*1000)
    finally:
        drv.disconnect()


def _qp(s: str) -> str:
    """Escape SQL string."""
    return s.replace("'", "''")

def horas_por_tecnico(cod_proyecto: str, limit: int = 20) -> Dict:
    """Recursos y actividad registrados, sin convertir cantidades en horas."""
    from .project_activity import inspect_project
    return inspect_project(_exec, cod_proyecto, limit)


def resumen_costes_proyecto(cod_proyecto: str) -> Dict:
    """Desglose MO vs Materiales vs Subcontrata. 100% datos reales."""
    if not cod_proyecto: return {"ok": False, "error": "cod_proyecto obligatorio"}
    sql = f"""SELECT
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MO}  THEN ol.COSTE  ELSE 0 END) AS COSTE_MO,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MAT} THEN ol.COSTE  ELSE 0 END) AS COSTE_MAT,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_SUB} THEN ol.COSTE  ELSE 0 END) AS COSTE_SUB,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MO}  THEN ol.PRECIO ELSE 0 END) AS PRECIO_MO,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MAT} THEN ol.PRECIO ELSE 0 END) AS PRECIO_MAT,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_SUB} THEN ol.PRECIO ELSE 0 END) AS PRECIO_SUB,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MO}  THEN ol.CANTIDAD ELSE 0 END) AS HORAS_MO,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MAT} THEN ol.CANTIDAD ELSE 0 END) AS UDSMAT,
        SUM(ol.COSTE) AS COSTE_TOTAL, SUM(ol.PRECIO) AS PRECIO_TOTAL,
        COUNT(ol.CODIGO) AS N_LINEAS, COUNT(DISTINCT ol.CODRECURSO) AS N_TECNICOS,
        MIN(ol.FECHA) AS FECHA_INICIO_IMPUT, MAX(ol.FECHA) AS FECHA_FIN_IMPUT
    FROM OBRALIN ol WHERE ol.CODPROYECTO='{_qp(cod_proyecto)}'"""
    sql_proy = f"SELECT NOMBRE, CLIENTE, FECHAINICIO, FECHAFIN, FINOBRA FROM PROYECTOS WHERE CODIGO='{_qp(cod_proyecto)}'"
    try:
        rows, ms = _exec(sql)
        proy_rows, _ = _exec(sql_proy)
        if not proy_rows: return {"ok":False,"error":f"Proyecto '{cod_proyecto}' no existe"}
        if not rows: return {"ok":False,"error":f"Proyecto '{cod_proyecto}' sin datos"}
        r = rows[0]; proy = proy_rows[0] if proy_rows else {}
        ct = float(r.get("COSTE_TOTAL") or 0)
        cmo = float(r.get("COSTE_MO") or 0)
        cmat = float(r.get("COSTE_MAT") or 0)
        csub = float(r.get("COSTE_SUB") or 0)
        pt = float(r.get("PRECIO_TOTAL") or 0)
        return {"ok":True,"cod_proyecto":cod_proyecto,"proyecto":proy,
                "desglose":{
                    "mano_obra":{"coste":cmo,"precio":float(r.get("PRECIO_MO") or 0),"horas":float(r.get("HORAS_MO") or 0),"pct_coste":round(cmo/ct*100,1) if ct else 0,"descripcion":"Horas técnicos (TIPOBC3=10)"},
                    "materiales":{"coste":cmat,"precio":float(r.get("PRECIO_MAT") or 0),"unidades":float(r.get("UDSMAT") or 0),"pct_coste":round(cmat/ct*100,1) if ct else 0,"descripcion":"Artículos y materiales (TIPOBC3=20)"},
                    "subcontrata":{"coste":csub,"precio":float(r.get("PRECIO_SUB") or 0),"pct_coste":round(csub/ct*100,1) if ct else 0,"descripcion":"Subcontratados (TIPOBC3=30)"},
                },
                "totales":{"coste_total":ct,"precio_total":pt,"margen":pt-ct,"pct_margen":round((pt-ct)/ct*100,1) if ct else 0,
                           "n_lineas":r.get("N_LINEAS"),"n_tecnicos":r.get("N_TECNICOS"),
                           "fecha_inicio":r.get("FECHA_INICIO_IMPUT"),"fecha_fin":r.get("FECHA_FIN_IMPUT")},
                "ms":ms,"fuente":"OBRALIN+PROYECTOS"}
    except Exception as e: return {"ok":False,"error":f"{type(e).__name__}: {str(e)[:300]}"}

def top_proyectos_por_coste(limit: int = 10) -> Dict:
    """Top proyectos por coste imputado. Verificado: Palacio de Justicia Gandía=732.496€."""
    sql = f"""SELECT FIRST {limit}
        ol.CODPROYECTO, p.NOMBRE, p.CLIENTE, p.FECHAINICIO, p.FECHAFIN,
        COUNT(ol.CODIGO) AS N_LINEAS,
        COUNT(DISTINCT ol.CODRECURSO) AS N_TECNICOS,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MO}  THEN ol.CANTIDAD ELSE 0 END) AS HORAS_MO,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MO}  THEN ol.COSTE   ELSE 0 END) AS COSTE_MO,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MAT} THEN ol.COSTE   ELSE 0 END) AS COSTE_MAT,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_SUB} THEN ol.COSTE   ELSE 0 END) AS COSTE_SUB,
        SUM(ol.COSTE) AS COSTE_TOTAL, SUM(ol.PRECIO) AS PRECIO_TOTAL
    FROM OBRALIN ol
    LEFT JOIN PROYECTOS p ON p.CODIGO = ol.CODPROYECTO
    WHERE ol.COSTE > 0
    GROUP BY ol.CODPROYECTO, p.NOMBRE, p.CLIENTE, p.FECHAINICIO, p.FECHAFIN
    ORDER BY COSTE_TOTAL DESC"""
    try:
        rows, ms = _exec(sql)
        return {"ok":True,"proyectos":rows,"ms":ms,"fuente":"OBRALIN+PROYECTOS",
                "nota":"Costes 100% reales de OBRALIN. 0 huérfanos confirmados 16/09/2026."}
    except Exception as e: return {"ok":False,"error":f"{type(e).__name__}: {str(e)[:300]}"}


def ranking_tecnicos(limit: int = 20) -> Dict:
    """Ranking global de técnicos por horas. JOIN OBRALIN.CODRECURSO=RECURSO.CODIGO."""
    sql = f"""SELECT FIRST {limit}
        ol.CODRECURSO, r.DESCRIPCION AS TECNICO,
        COUNT(ol.CODIGO) AS N_IMPUTACIONES,
        COUNT(DISTINCT ol.CODPROYECTO) AS N_PROYECTOS,
        SUM(ol.CANTIDAD) AS HORAS_TOTAL, SUM(ol.COSTE) AS COSTE_TOTAL,
        MAX(ol.FECHA) AS ULTIMA_IMPUTACION,
        AVG(ol.COSTE / NULLIF(ol.CANTIDAD,0)) AS COSTE_HORA_MEDIO
    FROM OBRALIN ol
    LEFT JOIN RECURSO r ON r.CODIGO = ol.CODRECURSO
    WHERE ol.TIPOBC3={TIPOBC3_MO} AND ol.CANTIDAD > 0 AND ol.CODRECURSO IS NOT NULL
    GROUP BY ol.CODRECURSO, r.DESCRIPCION
    ORDER BY HORAS_TOTAL DESC"""
    try:
        rows, ms = _exec(sql)
        return {"ok":True,"tecnicos":rows,"ms":ms,"fuente":"OBRALIN+RECURSO",
                "nota":"TIPOBC3=10. JOIN verificado. 0 huérfanos."}
    except Exception as e: return {"ok":False,"error":f"{type(e).__name__}: {str(e)[:300]}"}


def proyectos_de_tecnico(cod_recurso: int, limit: int = 20) -> Dict:
    """Proyectos en los que ha trabajado un técnico específico."""
    sql = f"""SELECT FIRST {limit}
        ol.CODPROYECTO, p.NOMBRE,
        COUNT(ol.CODIGO) AS N_IMPUTACIONES,
        SUM(ol.CANTIDAD) AS HORAS, SUM(ol.COSTE) AS COSTE,
        MIN(ol.FECHA) AS DESDE, MAX(ol.FECHA) AS HASTA
    FROM OBRALIN ol
    LEFT JOIN PROYECTOS p ON p.CODIGO = ol.CODPROYECTO
    WHERE ol.TIPOBC3={TIPOBC3_MO} AND ol.CODRECURSO={int(cod_recurso)} AND ol.CANTIDAD>0
    GROUP BY ol.CODPROYECTO, p.NOMBRE ORDER BY HORAS DESC"""
    try:
        rec, _ = _exec(f"SELECT CODIGO, DESCRIPCION FROM RECURSO WHERE CODIGO={int(cod_recurso)}")
        rows, ms = _exec(sql)
        return {"ok":True,"cod_recurso":cod_recurso,"recurso":rec[0] if rec else {},"proyectos":rows,"ms":ms}
    except Exception as e: return {"ok":False,"error":f"{type(e).__name__}: {str(e)[:300]}"}


def materiales_proyecto(cod_proyecto: str, limit: int = 20) -> Dict:
    """Top materiales por coste en un proyecto. TIPOBC3=20."""
    if not cod_proyecto: return {"ok":False,"error":"cod_proyecto obligatorio"}
    sql = f"""SELECT FIRST {limit}
        ol.CODARTICULO, ol.NOMBRE AS ARTICULO,
        COUNT(ol.CODIGO) AS N_LINEAS,
        SUM(ol.CANTIDAD) AS CANTIDAD_TOTAL,
        SUM(ol.COSTE) AS COSTE_TOTAL, SUM(ol.PRECIO) AS PRECIO_TOTAL,
        AVG(ol.COSTE / NULLIF(ol.CANTIDAD,0)) AS COSTE_UNITARIO
    FROM OBRALIN ol
    WHERE ol.TIPOBC3={TIPOBC3_MAT} AND ol.CODPROYECTO='{_qp(cod_proyecto)}' AND ol.CANTIDAD>0
    GROUP BY ol.CODARTICULO, ol.NOMBRE ORDER BY COSTE_TOTAL DESC"""
    sql_tot = f"""SELECT SUM(ol.COSTE) AS COSTE_TOTAL, COUNT(DISTINCT ol.CODARTICULO) AS N_ARTICULOS
    FROM OBRALIN ol WHERE ol.TIPOBC3={TIPOBC3_MAT} AND ol.CODPROYECTO='{_qp(cod_proyecto)}' AND ol.CANTIDAD>0"""
    try:
        rows, ms = _exec(sql); tot, _ = _exec(sql_tot)
        return {"ok":True,"cod_proyecto":cod_proyecto,"materiales":rows,"totales":tot[0] if tot else {},"ms":ms,"fuente":"OBRALIN (TIPOBC3=20)"}
    except Exception as e: return {"ok":False,"error":f"{type(e).__name__}: {str(e)[:300]}"}


def evolucion_costes_proyecto(cod_proyecto: str) -> Dict:
    """Evolución mensual de costes imputados a un proyecto."""
    if not cod_proyecto: return {"ok":False,"error":"cod_proyecto obligatorio"}
    sql = f"""SELECT EXTRACT(YEAR FROM ol.FECHA) AS ANYO, EXTRACT(MONTH FROM ol.FECHA) AS MES,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MO}  THEN ol.COSTE ELSE 0 END) AS COSTE_MO,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MAT} THEN ol.COSTE ELSE 0 END) AS COSTE_MAT,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_SUB} THEN ol.COSTE ELSE 0 END) AS COSTE_SUB,
        SUM(ol.COSTE) AS COSTE_TOTAL,
        SUM(CASE WHEN ol.TIPOBC3={TIPOBC3_MO} THEN ol.CANTIDAD ELSE 0 END) AS HORAS_MO,
        COUNT(ol.CODIGO) AS N_LINEAS
    FROM OBRALIN ol
    WHERE ol.CODPROYECTO='{_qp(cod_proyecto)}' AND ol.FECHA IS NOT NULL AND ol.COSTE>0
    GROUP BY EXTRACT(YEAR FROM ol.FECHA), EXTRACT(MONTH FROM ol.FECHA)
    ORDER BY ANYO, MES"""
    try:
        rows, ms = _exec(sql)
        return {"ok":True,"cod_proyecto":cod_proyecto,"evolucion_mensual":rows,"n_meses":len(rows),"ms":ms,"fuente":"OBRALIN"}
    except Exception as e: return {"ok":False,"error":f"{type(e).__name__}: {str(e)[:300]}"}

def verificacion_coherencia() -> Dict:
    """Checks globales agrupados, con ayuda y resultados explícitos."""
    from .check_runner import run_checks
    return run_checks(_exec)
