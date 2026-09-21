"""Router FastAPI — Utilidades de Ingeniería. Prefix: /api/api-clone/utilidades"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from backend.modules.api_clone.utilidades import service as svc

router = APIRouter()


@router.get("/informe-fiabilidad.txt")
def informe_fiabilidad():
    from fastapi.responses import Response
    from .report import build_report
    return Response(build_report(svc._exec), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="api-clone-fiabilidad.txt"',
                             "Cache-Control": "no-store"})


@router.get("/proyectos-buscar")
def proyectos_buscar(q: str = Query("", max_length=150), offset: int = Query(0, ge=0), limit: int = Query(15, ge=1, le=50)):
    from .project_lookup import search
    try:
        return search(svc._get_driver, q, offset, limit)
    except Exception:
        raise HTTPException(status_code=503, detail="No se pudo consultar el selector de proyectos.")


class ProyectoRequest(BaseModel):
    cod_proyecto: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("cod_proyecto")
    @classmethod
    def proyecto_no_vacio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("cod_proyecto obligatorio")
        return value


class TecnicoRequest(BaseModel):
    cod_recurso: int
    limit: int = Field(default=20, ge=1, le=100)


@router.post("/horas-por-tecnico")
async def horas_por_tecnico(request: ProyectoRequest):
    """Horas+coste por técnico en proyecto. JOIN OBRALIN(T=10)+RECURSO. 0 huerfanos."""
    try: return svc.horas_por_tecnico(request.cod_proyecto, request.limit)
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resumen-costes")
async def resumen_costes(request: ProyectoRequest):
    """Desglose MO vs Mat vs Sub + margen. JOIN OBRALIN+PROYECTOS."""
    try: return svc.resumen_costes_proyecto(request.cod_proyecto)
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.get("/top-proyectos")
async def top_proyectos(limit: int = Query(10, ge=1, le=50)):
    """Top N proyectos por coste. Verificado: 45215=732.496€."""
    try: return svc.top_proyectos_por_coste(limit)
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.get("/ranking-tecnicos")
async def ranking_tecnicos(limit: int = Query(20, ge=1, le=100)):
    """Ranking técnicos por horas. 307.049 líneas MO en BD."""
    try: return svc.ranking_tecnicos(limit)
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.post("/proyectos-de-tecnico")
async def proyectos_de_tecnico(request: TecnicoRequest):
    """Proyectos de un técnico. cod_recurso=INTEGER (RECURSO.CODIGO)."""
    try: return svc.proyectos_de_tecnico(request.cod_recurso, request.limit)
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.post("/materiales-proyecto")
async def materiales_proyecto(request: ProyectoRequest):
    """Top materiales por coste. OBRALIN(TIPOBC3=20)."""
    try: return svc.materiales_proyecto(request.cod_proyecto, request.limit)
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.post("/evolucion-costes")
async def evolucion_costes(request: ProyectoRequest):
    """Evolución mensual MO+Mat+Sub. Curva de ejecución."""
    try: return svc.evolucion_costes_proyecto(request.cod_proyecto)
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.get("/verificacion-coherencia")
def verificacion_coherencia():
    """Checks globales agrupados con ayuda y cuatro estados explícitos."""
    try: return svc.verificacion_coherencia()
    except Exception as exc: raise HTTPException(status_code=500, detail=str(exc))


@router.get("/catalogo")
async def catalogo():
    """Catálogo de utilidades disponibles."""
    return {
        "utilidades": [
            {"id":"horas-por-tecnico","nombre":"👷 Técnicos y actividad registrada",
             "desc":"Recursos referenciados y líneas de la obra. Horas realizadas no verificadas.",
             "params":["cod_proyecto"],"perfiles":["🏗️ Ingenieros","💰 Gerencia","👷 RRHH"]},
            {"id":"resumen-costes","nombre":"📊 Resumen MO vs Mat vs Sub",
             "desc":"Desglose coste total + margen real del proyecto.",
             "params":["cod_proyecto"],"perfiles":["📊 Dirección","💰 Gerencia","🏗️ Ingenieros"]},
            {"id":"top-proyectos","nombre":"🏆 Top proyectos por coste",
             "desc":"Los N proyectos más costosos. Verificado: 45215=732.496€",
             "params":["limit"],"perfiles":["📊 Dirección","💰 Gerencia"]},
            {"id":"ranking-tecnicos","nombre":"👷 Ranking global de técnicos",
             "desc":"Técnicos por horas totales en todos los proyectos.",
             "params":["limit"],"perfiles":["👷 RRHH","💰 Gerencia","🏗️ Ingenieros"]},
            {"id":"proyectos-de-tecnico","nombre":"🗂️ Proyectos de un técnico",
             "desc":"Historial de proyectos con horas y fechas.",
             "params":["cod_recurso (int)"],"perfiles":["👷 Técnicos","🏗️ Ingenieros"]},
            {"id":"materiales-proyecto","nombre":"📦 Materiales de un proyecto",
             "desc":"Top materiales por coste imputados.",
             "params":["cod_proyecto"],"perfiles":["🏗️ Ingenieros","📦 Compras"]},
            {"id":"evolucion-costes","nombre":"📈 Evolución mensual de costes",
             "desc":"Costes mes a mes. Curva de ejecución.",
             "params":["cod_proyecto"],"perfiles":["📊 Dirección","💰 Gerencia"]},
            {"id":"verificacion-coherencia","nombre":"🔍 Verificación y evidencias",
             "desc":"Seis grupos de checks con ayuda, incidencias y límites de verificación.",
             "params":[],"perfiles":["🔍 Auditoría","📊 Dirección","🏗️ Ingenieros"]},
        ],
        "tablas":{"OBRALIN":"942.088 líneas","RECURSO":"186","PROYECTOS":"1.213"},
        "tipobc3":{"10":"Mano de obra","20":"Materiales","30":"Subcontrata"},
    }
