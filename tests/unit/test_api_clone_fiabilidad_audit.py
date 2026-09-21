"""Auditoría ejecutable. Datos SINTÉTICOS, SQL real del servicio en SQLite.

Solo adapta FIRST y EXTRACT; no prueba tipos/collations/transacciones Firebird.
Los xfail(strict=True) son garantías NO cumplidas, no pruebas aprobadas.
Para ver los fallos sin ocultarlos: pytest este_fichero --runxfail -q.
No conecta a red ni escribe el historial de producción.
"""
import re
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modules.api_clone import service as api
from backend.modules.api_clone import router as routes
from backend.modules.api_clone.utilidades import service as utils


class SqliteDriver:
    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.queries = []

    def execute_query(self, sql):
        self.queries.append(sql)
        first = re.match(r"SELECT FIRST (\d+) ", sql)
        if first:
            sql = "SELECT " + sql[first.end():] + " LIMIT " + first.group(1)
        sql = re.sub(r"EXTRACT\(YEAR FROM (\w+\.\w+)\)", r"CAST(strftime('%Y', \1) AS INTEGER)", sql)
        sql = re.sub(r"EXTRACT\(MONTH FROM (\w+\.\w+)\)", r"CAST(strftime('%m', \1) AS INTEGER)", sql)
        return [dict(row) for row in self.db.execute(sql).fetchall()]

    def disconnect(self):
        pass


@pytest.fixture
def audit(monkeypatch, tmp_path):
    drv = SqliteDriver()
    drv.db.executescript("""
        CREATE TABLE PROYECTOS(CODIGO TEXT PRIMARY KEY, NOMBRE TEXT, CLIENTE INTEGER,
            FECHAINICIO TEXT, FECHAFIN TEXT, TIPOOBRA INTEGER, FINOBRA TEXT,
            OBSERVACIONES TEXT, PORCRETENCION REAL);
        CREATE TABLE OBRACAB(CODIGO INTEGER PRIMARY KEY, CODPROYECTO TEXT, ESPREVISION INTEGER);
        CREATE TABLE OBRALIN(CODCAB INTEGER, CODIGO INTEGER, CODPROYECTO TEXT,
            ESPREVISION INTEGER, FECHA TEXT, FECHAALTA TEXT, PARTIDA TEXT,
            CODARTICULO TEXT, CODRECURSO INTEGER, NOMBRE TEXT, TIPOBC3 INTEGER,
            COSTE REAL, PRECIO REAL, CANTIDAD REAL, PRIMARY KEY(CODCAB,CODIGO));
        CREATE TABLE RECURSO(CODIGO INTEGER PRIMARY KEY, DESCRIPCION TEXT, FECHABAJA TEXT);
        CREATE TABLE PRESUPROYE(CODPRESUPUESTO INTEGER, CODPROYECTO TEXT, CODPROYSUBCONTRATA TEXT);
        CREATE TABLE DOCCAB(CODIGO INTEGER PRIMARY KEY, TIPO INTEGER, SERIE TEXT,
            NUMERO INTEGER, FECHA TEXT, IMPORTETOTAL REAL, CODCLIENTE INTEGER,
            IMPORTEBASE REAL, IMPORTEIVA REAL, OBSERVACIONES TEXT, CODPROYECTO TEXT);
        INSERT INTO PROYECTOS VALUES('A','Activo',1,'2026-01-01','2026-12-31',0,'F',NULL,0);
        INSERT INTO PROYECTOS VALUES('B','Cerrado',1,'2025-01-01','2025-12-31',0,'T',NULL,0);
        INSERT INTO RECURSO VALUES(1,'Solo A',NULL),(2,'Solo B','2025-01-01');
        INSERT INTO OBRACAB VALUES(10,'B',0),(20,'A',0),(30,'A',1),(40,'A',0);
        INSERT INTO OBRALIN VALUES(10,1,'B',0,'2025-06-01',NULL,NULL,NULL,2,'B',10,90,100,9);
        INSERT INTO OBRALIN VALUES(20,1,'A',0,'2026-06-01',NULL,NULL,NULL,1,'A',10,10,15,1);
        INSERT INTO OBRALIN VALUES(30,2,'A',1,'2026-06-01',NULL,NULL,NULL,1,'Prev',10,20,30,2);
        INSERT INTO OBRALIN VALUES(40,3,NULL,0,NULL,NULL,NULL,NULL,1,'Cab A',10,30,45,3);
        INSERT INTO PRESUPROYE VALUES(11,'A',NULL),(12,'B',NULL);
        INSERT INTO DOCCAB VALUES(101,2,'S',1,'2026-01-01',10,1,10,0,NULL,'A');
        INSERT INTO DOCCAB VALUES(102,2,'S',2,'2026-01-01',20,1,20,0,NULL,'B');
        INSERT INTO DOCCAB VALUES(103,3,'S',3,'2026-01-01',30,1,30,0,NULL,'B');
    """)
    monkeypatch.setattr(api, "_get_driver", lambda: drv)
    monkeypatch.setattr(utils, "_get_driver", lambda: drv)
    monkeypatch.setattr(api, "_HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(api, "_MATRIX_FILE", tmp_path / "matrix.json")
    svc = api.ApiCloneService()
    monkeypatch.setattr(routes, "get_service", lambda: svc)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/api-clone")
    with TestClient(app) as client:
        yield svc, drv, client
    drv.db.close()


@pytest.mark.parametrize("clase", ["partidas", "proordutil", "proordprev"])
@pytest.mark.parametrize("project", ["A", "B", "MISSING", "A' OR '1'='1"])
def test_valid_project_filter_does_not_leak(audit, clase, project):
    svc, _, _ = audit
    result = svc.browse(clase, {"codProyecto": project})
    assert result["estado"] == "ok"
    assert all(row["CODPROYECTO"] == project for row in result["data"]["items"])
    if project in ("A", "B"):
        assert result["data"]["items"]


def test_document_type_filter_applies_to_read_and_browse(audit):
    svc, _, _ = audit
    assert {r["TIPO"] for r in svc.browse("docalbcom", {})["data"]["items"]} == {2}
    assert svc.read("docalbcom", "103")["estado"] == "falla"


@pytest.mark.xfail(strict=True, reason="AUD-01: espacios eliminan WHERE tras superar validación")
def test_whitespace_project_must_not_return_global_data(audit):
    _, _, client = audit
    r = client.post("/api/api-clone/browse", json={"clase": "proordutil", "params": {"codProyecto": "   "}}).json()
    assert r["estado"] == "falla" or not r["data"]["items"]


@pytest.mark.xfail(strict=True, reason="AUD-02: parámetro de proyecto no soportado se ignora")
@pytest.mark.parametrize("clase,key,allowed", [("recursos", "CODIGO", {1}), ("docalbcom", "CODIGO", {101})])
def test_project_scope_must_be_enforced_or_rejected(audit, clase, key, allowed):
    svc, _, _ = audit
    r = svc.browse(clase, {"codProyecto": "A"})
    assert r["estado"] == "falla" or {x[key] for x in r["data"]["items"]} <= allowed


@pytest.mark.xfail(strict=True, reason="AUD-03: read omite CODCAB, devuelve primera coincidencia")
def test_ambiguous_line_id_must_be_rejected(audit):
    svc, _, _ = audit
    row_a = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"][0]
    r = svc.read("proordutil", str(row_a["CODIGO"]))
    assert r["estado"] == "falla" or r["data"]["CODPROYECTO"] == "A"


@pytest.mark.xfail(strict=True, reason="AUD-04: ambas clases consultan la misma población")
def test_real_and_forecast_sets_must_not_overlap(audit):
    svc, _, _ = audit
    real = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"]
    forecast = svc.browse("proordprev", {"codProyecto": "A"})["data"]["items"]
    assert {(r["CODCAB"], r["CODIGO"]) for r in real}.isdisjoint(
        {(r["CODCAB"], r["CODIGO"]) for r in forecast})


@pytest.mark.xfail(strict=True, reason="AUD-05: líneas relacionadas por cabecera desaparecen")
def test_all_project_lines_include_header_relationship(audit):
    svc, drv, _ = audit
    expected = drv.db.execute("SELECT o.CODCAB,o.CODIGO FROM OBRALIN o JOIN OBRACAB c ON c.CODIGO=o.CODCAB WHERE c.CODPROYECTO='A'").fetchall()
    actual = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"]
    assert {(r["CODCAB"], r["CODIGO"]) for r in actual} == {tuple(r) for r in expected}


@pytest.mark.xfail(strict=True, reason="AUD-06: filtro FINOBRA no está admitido ni se rechaza")
def test_active_project_filter_must_work_or_be_rejected(audit):
    svc, _, _ = audit
    r = svc.browse("proyectos", {"FINOBRA": "F"})
    assert r["estado"] == "falla" or {p["CODIGO"] for p in r["data"]["items"]} == {"A"}


@pytest.mark.xfail(strict=True, reason="AUD-07: no se devuelve el estado FINOBRA")
def test_project_result_exposes_lifecycle(audit):
    svc, _, _ = audit
    assert svc.read("proyectos", "B")["data"]["FINOBRA"] == "T"


@pytest.mark.xfail(strict=True, reason="AUD-08: FIRST es truncado, sin paginación offset")
def test_offset_must_advance_or_be_rejected(audit):
    svc, _, _ = audit
    first = svc.browse("proyectos", {}, 1)
    second = svc.browse("proyectos", {"offset": 1}, 1)
    assert second["estado"] == "falla" or second["data"]["items"] != first["data"]["items"]


def test_coherence_must_report_unknown_project(audit):
    r = utils.verificacion_coherencia()
    assert r["checks"][0]["ok"] is False
    assert r["checks"][0]["estado_codigo"] == "revisar"
    assert r["checks"][0]["resultado"] == 1


def test_hours_exclude_forecasts(audit):
    _, drv, _ = audit
    drv.db.execute("DELETE FROM OBRALIN WHERE CODPROYECTO IS NULL")
    r = utils.horas_por_tecnico("A")
    assert r["horas_verificadas"] is False
    assert "HORAS_TOTAL" not in r.get("totales", {})
    assert r["actividad"]["MO_REAL"] == 1
    assert r["actividad"]["MO_PREVISTA"] == 1


def test_resource_with_zero_quantity_is_visible(audit):
    _, drv, _ = audit
    drv.db.execute("UPDATE OBRALIN SET CANTIDAD=0 WHERE CODPROYECTO='A'")
    result = utils.horas_por_tecnico("A")
    assert result["ok"]
    assert result["actividad"]["RECURSOS"] == 1
    assert result["actividad"]["MO_POSITIVA"] == 0
    assert result["tecnicos"][0]["CODRECURSO"] == 1
    assert result["tecnicos"][0]["LINEAS_REGISTRADAS"] == 2
    assert result["horas_verificadas"] is False


def test_existing_empty_project_is_explained(audit):
    _, drv, _ = audit
    drv.db.execute("INSERT INTO PROYECTOS(CODIGO,NOMBRE,FINOBRA) VALUES('EMPTY','Vacío','T')")
    result = utils.horas_por_tecnico("EMPTY")
    assert result["ok"]
    assert result["actividad"]["LINEAS"] == 0
    assert result["tecnicos"] == []
    assert "no tiene líneas" in result["mensaje"]
    assert result["grupos"][1]["estado_codigo"] == "no_aplica"


def test_unknown_project_is_not_a_zero_success(audit):
    result = utils.horas_por_tecnico("MISSING")
    assert result["ok"] is False
    assert "no existe" in result["error"]


@pytest.mark.xfail(strict=True, reason="AUD-11: resumen y ranking excluyen conjuntos distintos")
def test_top_and_summary_agree_with_negative_adjustment(audit):
    _, drv, _ = audit
    drv.db.execute("INSERT INTO OBRALIN(CODCAB,CODIGO,CODPROYECTO,TIPOBC3,COSTE,PRECIO,CANTIDAD) VALUES(20,99,'A',10,-5,-5,-1)")
    summary = utils.resumen_costes_proyecto("A")["totales"]["coste_total"]
    top = next(p for p in utils.top_proyectos_por_coste()["proyectos"] if p["CODPROYECTO"] == "A")
    assert top["COSTE_TOTAL"] == summary


@pytest.mark.xfail(strict=True, reason="AUD-12: read HTTP descarta codProyecto extra")
def test_read_cannot_silently_ignore_requested_project(audit):
    _, _, client = audit
    r = client.post("/api/api-clone/read", json={"clase": "proordutil", "objectid": "1", "codProyecto": "A"})
    assert r.status_code == 422 or r.json()["estado"] == "falla" or r.json()["data"]["CODPROYECTO"] == "A"


def test_missing_required_parameter_is_warning_not_valid_empty_query(audit):
    svc, drv, _ = audit
    r = svc.browse("proordutil", {})
    assert r["data"]["param_requerido"] == "codProyecto"
    assert drv.queries == []


def test_read_foreign_project_demonstration(audit):
    """Caracteriza explícitamente el defecto, sin presentarlo como garantía."""
    svc, _, _ = audit
    requested = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"][0]
    returned = svc.read("proordutil", str(requested["CODIGO"]))["data"]
    assert (requested["CODPROYECTO"], returned["CODPROYECTO"]) == ("A", "B")
