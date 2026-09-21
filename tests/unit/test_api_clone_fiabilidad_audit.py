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
        first = re.match(r"SELECT FIRST (\d+)(?: SKIP (\d+))?\s+", sql)
        if first:
            sql = "SELECT " + sql[first.end():] + " LIMIT " + first.group(1) + (" OFFSET " + first.group(2) if first.group(2) else "")
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
    if project == "A" or (project == "B" and clase != "proordprev"):
        assert result["data"]["items"]


def test_document_type_filter_applies_to_read_and_browse(audit):
    svc, _, _ = audit
    assert {r["TIPO"] for r in svc.browse("docalbcom", {})["data"]["items"]} == {2}
    assert svc.read("docalbcom", "103")["estado"] == "falla"


def test_whitespace_project_must_not_return_global_data(audit):
    _, _, client = audit
    r = client.post("/api/api-clone/browse", json={"clase": "proordutil", "params": {"codProyecto": "   "}}).json()
    assert r["estado"] == "falla" or not r["data"]["items"]


@pytest.mark.parametrize("clase,key,allowed", [("recursos", "CODIGO", {1}), ("docalbcom", "CODIGO", {101})])
def test_project_scope_must_be_enforced_or_rejected(audit, clase, key, allowed):
    svc, _, _ = audit
    r = svc.browse(clase, {"codProyecto": "A"})
    assert r["estado"] == "falla" or {x[key] for x in r["data"]["items"]} <= allowed


def test_ambiguous_line_id_must_be_rejected(audit):
    svc, _, _ = audit
    row_a = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"][0]
    r = svc.read("proordutil", str(row_a["CODIGO"]))
    assert r["estado"] == "falla" or r["data"]["CODPROYECTO"] == "A"


def test_real_and_forecast_sets_must_not_overlap(audit):
    svc, _, _ = audit
    real = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"]
    forecast = svc.browse("proordprev", {"codProyecto": "A"})["data"]["items"]
    assert {(r["CODCAB"], r["CODIGO"]) for r in real}.isdisjoint(
        {(r["CODCAB"], r["CODIGO"]) for r in forecast})


@pytest.mark.xfail(strict=True, reason="AUD-05: líneas relacionadas por cabecera desaparecen")
def test_all_project_lines_include_header_relationship(audit):
    svc, drv, _ = audit
    expected = drv.db.execute("SELECT o.CODCAB,o.CODIGO FROM OBRALIN o JOIN OBRACAB c ON c.CODIGO=o.CODCAB WHERE c.CODPROYECTO='A' AND o.ESPREVISION=0").fetchall()
    actual = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"]
    assert {(r["CODCAB"], r["CODIGO"]) for r in actual} == {tuple(r) for r in expected}


def test_active_project_filter_must_work_or_be_rejected(audit):
    svc, _, _ = audit
    r = svc.browse("proyectos", {"FINOBRA": "F"})
    assert r["estado"] == "falla" or {p["CODIGO"] for p in r["data"]["items"]} == {"A"}


def test_project_result_exposes_lifecycle(audit):
    svc, _, _ = audit
    assert svc.read("proyectos", "B")["data"]["FINOBRA"] == "T"


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


def test_top_and_summary_agree_with_negative_adjustment(audit):
    _, drv, _ = audit
    drv.db.execute("INSERT INTO OBRALIN(CODCAB,CODIGO,CODPROYECTO,TIPOBC3,COSTE,PRECIO,CANTIDAD) VALUES(20,99,'A',10,-5,-5,-1)")
    summary = utils.resumen_costes_proyecto("A")["totales"]["coste_total"]
    top = next(p for p in utils.top_proyectos_por_coste()["proyectos"] if p["CODPROYECTO"] == "A")
    assert top["COSTE_TOTAL"] == summary


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
    """Regresión: una clave incompleta ya no devuelve la línea de otra obra."""
    svc, _, _ = audit
    requested = svc.browse("proordutil", {"codProyecto": "A"})["data"]["items"][0]
    assert svc.read("proordutil", str(requested["CODIGO"]))["estado"] == "falla"
    full_key = f"{requested['CODCAB']}:{requested['CODIGO']}"
    assert svc.read("proordutil", full_key)["data"]["CODPROYECTO"] == "A"


@pytest.mark.parametrize("value", ["", " ", "\t\n", None, [], {}, True, False])
def test_invalid_scope_never_executes_global_query(audit, value):
    svc, driver, _ = audit
    r=svc.browse("proordutil", {"codProyecto":value})
    assert r["estado"] == "falla"
    assert driver.queries == []


@pytest.mark.parametrize("limit", [0,-1,1001,True,1.5,"20",None])
def test_invalid_limit_is_rejected_before_sql(audit, limit):
    svc, driver, _=audit
    assert svc.browse("proyectos",{},limit)["estado"] == "falla"
    assert driver.queries == []


@pytest.mark.parametrize("identifier", ["1","20",":1","20:","20:1:3","20:1 OR 1=1","-20:1","２０:１"])
def test_malformed_line_key_never_queries(audit, identifier):
    svc, driver, _=audit
    assert svc.read("proordutil",identifier)["estado"] == "falla"
    assert driver.queries == []


@pytest.mark.parametrize("seed", range(20))
def test_generated_cross_project_and_forecast_isolation(audit, seed):
    import random
    rng=random.Random(seed)
    svc,driver,_=audit
    for cab in range(100,140):
        project=rng.choice(["A","B",None,"A' OR '1'='1"])
        forecast=rng.choice([0,1,None,9])
        driver.db.execute("INSERT INTO OBRALIN(CODCAB,CODIGO,CODPROYECTO,ESPREVISION) VALUES(?,?,?,?)",(cab,1,project,forecast))
    for project in ["A","B","A' OR '1'='1"]:
        sets=[]
        for clase,forecast in [("proordutil",0),("proordprev",1)]:
            result=svc.browse(clase,{"codProyecto":project},1000)
            assert result["estado"] == "ok"
            expected={tuple(r) for r in driver.db.execute("SELECT CODCAB,CODIGO FROM OBRALIN WHERE CODPROYECTO=? AND ESPREVISION=?",(project,forecast))}
            actual={(r["CODCAB"],r["CODIGO"]) for r in result["data"]["items"]}
            assert actual == expected
            assert result["data"]["total"] == len(expected)
            for cab,code in actual:
                assert svc.read(clase,f"{cab}:{code}")["data"]["CODPROYECTO"] == project
            sets.append(actual)
        assert sets[0].isdisjoint(sets[1])


def test_human_error_is_detected_not_reassigned(audit):
    svc,driver,_=audit
    driver.db.execute("UPDATE OBRALIN SET CODPROYECTO='B' WHERE CODCAB=20")
    before=[tuple(r) for r in driver.db.execute("SELECT * FROM OBRALIN")]
    checks={c["id"]:c for c in utils.verificacion_coherencia()["checks"]}
    assert checks["CHK-015"]["resultado"] == 1
    assert checks["CHK-015"]["estado_codigo"] == "revisar"
    assert all(r["CODCAB"] != 20 for r in svc.browse("proordutil",{"codProyecto":"A"})["data"]["items"])
    assert [tuple(r) for r in driver.db.execute("SELECT * FROM OBRALIN")] == before


def test_closed_project_is_historical_not_hidden_or_authorized(audit):
    svc,_,_=audit
    assert svc.read("proyectos","B")["data"]["FINOBRA"] == "T"
    result=svc.browse("proyectos",{},1)["data"]
    assert result["lista_truncada"] is True
    assert result["fiabilidad_negocio"] == "no_verificada"


def test_duplicate_read_returns_error_not_first_row(audit):
    svc,driver,_=audit
    driver.db.execute("INSERT INTO PRESUPROYE VALUES(11,'B',NULL)")
    assert svc.read("partidas","11")["estado"] == "falla"


@pytest.mark.parametrize("extra", [{"codProyecto":"A"},{"params":{"codProyecto":"A"}},{"offset":1}])
def test_http_never_discards_unknown_read_fields(audit,extra):
    _,driver,client=audit
    response=client.post("/api/api-clone/read",json={"clase":"proordutil","objectid":"10:1",**extra})
    assert response.status_code == 422
    assert driver.queries == []


@pytest.mark.parametrize("count", [[],[{"N":None}],[{"N":-1}],[{"N":True}],[{"N":1.5}]])
def test_unavailable_total_cannot_become_zero_success(audit,monkeypatch,count):
    svc,driver,_=audit
    original=driver.execute_query
    monkeypatch.setattr(driver,"execute_query",lambda sql: count if "COUNT(*) AS N" in sql else original(sql))
    assert svc.browse("proyectos",{})["estado"] == "falla"


def test_unknown_filter_without_required_scope_is_rejected(audit):
    svc,driver,_=audit
    assert svc.browse("proordutil",{"codProyeto":"A"})["estado"] == "falla"
    assert driver.queries == []


def test_oversized_composite_key_is_rejected_before_conversion(audit):
    svc,driver,_=audit
    assert svc.read("proordutil","9"*5000+":1")["estado"] == "falla"
    assert driver.queries == []


@pytest.mark.parametrize("clase,params",[("proyectos",{}),("recursos",{}),("proordutil",{"codProyecto":"A"}),("proordprev",{"codProyecto":"A"})])
def test_all_pages_equal_full_set_without_duplicate_or_gap(audit,clase,params):
    svc,driver,_=audit
    for cab in range(101,107):
        driver.db.execute("INSERT INTO OBRALIN(CODCAB,CODIGO,CODPROYECTO,ESPREVISION) VALUES(?,1,'A',?)",(cab,cab%2))
    expected=svc.browse(clase,params,1000)["data"]["items"]
    rows=[]
    offset=0
    while True:
        result=svc.browse(clase,params,2,offset)
        assert result["estado"]=="ok"
        page=result["data"]
        rows.extend(page["items"])
        if page["siguiente_offset"] is None: break
        assert page["siguiente_offset"]>offset
        offset=page["siguiente_offset"]
    assert rows==expected
    assert len(rows)==page["total"]
    assert svc.browse(clase,params,2,page["total"])["data"]["items"]==[]


def test_http_pagination_and_invalid_offset(audit):
    _,driver,client=audit
    a=client.post("/api/api-clone/browse",json={"clase":"proyectos","num":1,"offset":0}).json()
    b=client.post("/api/api-clone/browse",json={"clase":"proyectos","num":1,"offset":1}).json()
    assert a["data"]["items"]!=b["data"]["items"]
    for offset in [-1,True,1.5,"1"]:
        assert client.post("/api/api-clone/browse",json={"clase":"proyectos","offset":offset}).status_code==422


def test_header_candidates_are_reported_without_assigning(audit):
    svc,driver,_=audit
    before=[tuple(r) for r in driver.db.execute("SELECT * FROM OBRALIN")]
    report=utils.verificacion_coherencia()
    candidate=next(c for c in report["checks"] if c["id"]=="CHK-028")
    assert candidate["resultado"]==1
    assert candidate["estado_codigo"]=="revisar"
    assert [tuple(r) for r in driver.db.execute("SELECT * FROM OBRALIN")]==before
