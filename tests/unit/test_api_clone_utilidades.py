"""Contratos HTTP y regresiones de utilidades; sin red ni Firebird."""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modules.api_clone.utilidades import service as svc
from backend.modules.api_clone.utilidades.router import router


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    driver = MagicMock(side_effect=AssertionError("No conectar a Firebird"))
    monkeypatch.setattr(svc, "_get_driver", driver)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/api-clone/utilidades")
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("path,body,function,args", [
    ("horas-por-tecnico", {"cod_proyecto": " P1 ", "limit": 4}, "horas_por_tecnico", ("P1", 4)),
    ("resumen-costes", {"cod_proyecto": "P1"}, "resumen_costes_proyecto", ("P1",)),
    ("materiales-proyecto", {"cod_proyecto": "P1"}, "materiales_proyecto", ("P1", 20)),
    ("evolucion-costes", {"cod_proyecto": "P1"}, "evolucion_costes_proyecto", ("P1",)),
    ("proyectos-de-tecnico", {"cod_recurso": 2}, "proyectos_de_tecnico", (2, 20)),
])
def test_post_dispatch(client, monkeypatch, path, body, function, args):
    call = MagicMock(return_value={"ok": True})
    monkeypatch.setattr(svc, function, call)
    response = client.post("/api/api-clone/utilidades/" + path, json=body)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    call.assert_called_once_with(*args)


@pytest.mark.parametrize("path,function,args", [
    ("top-proyectos?limit=3", "top_proyectos_por_coste", (3,)),
    ("ranking-tecnicos?limit=4", "ranking_tecnicos", (4,)),
    ("verificacion-coherencia", "verificacion_coherencia", ()),
])
def test_get_dispatch(client, monkeypatch, path, function, args):
    call = MagicMock(return_value={"ok": True})
    monkeypatch.setattr(svc, function, call)
    assert client.get("/api/api-clone/utilidades/" + path).status_code == 200
    call.assert_called_once_with(*args)


@pytest.mark.parametrize("limit", [0, -1, 101, "1; DELETE FROM OBRALIN", 1.5])
@pytest.mark.parametrize("path,body", [
    ("horas-por-tecnico", {"cod_proyecto": "P1"}),
    ("proyectos-de-tecnico", {"cod_recurso": 1}),
])
def test_invalid_limits_rejected(client, path, body, limit):
    response = client.post("/api/api-clone/utilidades/" + path, json={**body, "limit": limit})
    assert response.status_code == 422


@pytest.mark.parametrize("code", ["", "   ", None])
def test_empty_project_rejected(client, code):
    assert client.post("/api/api-clone/utilidades/resumen-costes", json={"cod_proyecto": code}).status_code == 422


def test_catalog_matches_routes(client):
    catalog = client.get("/api/api-clone/utilidades/catalogo").json()
    ids = {item["id"] for item in catalog["utilidades"]}
    assert len(ids) == 8
    assert ids == {route.path.rsplit("/", 1)[-1] for route in router.routes} - {"catalogo", "proyectos-buscar", "informe-fiabilidad.txt"}


def test_safe_serialization():
    assert svc._safe([{"N": Decimal("1234.56789"), "D": date(2026, 1, 2), "V": None}]) == [
        {"N": 1234.5679, "D": "2026-01-02", "V": None}]


@pytest.mark.parametrize("fails", [False, True])
def test_connection_closed(monkeypatch, fails):
    driver = MagicMock()
    driver.execute_query.return_value = [{"N": 1}]
    if fails:
        driver.execute_query.side_effect = RuntimeError("consulta fallida")
    monkeypatch.setattr(svc, "_get_driver", lambda: driver)
    if fails:
        with pytest.raises(RuntimeError):
            svc._exec("SELECT 1")
    else:
        assert svc._exec("SELECT 1")[0] == [{"N": 1}]
    driver.disconnect.assert_called_once()


def test_nonexistent_project(monkeypatch):
    monkeypatch.setattr(svc, "_exec", MagicMock(side_effect=[([{"COSTE_TOTAL": None}], 0), ([], 0)]))
    result = svc.resumen_costes_proyecto("missing")
    assert result["ok"] is False
    assert "no existe" in result["error"]


def test_summary_and_zero_cost(monkeypatch):
    execute = MagicMock(side_effect=[
        ([{"COSTE_TOTAL": 100, "COSTE_MO": 60, "COSTE_MAT": 40, "PRECIO_TOTAL": 125}], 0),
        ([{"NOMBRE": "Proyecto"}], 0),
        ([{"COSTE_TOTAL": None}], 0), ([{"NOMBRE": "Proyecto"}], 0),
    ])
    monkeypatch.setattr(svc, "_exec", execute)
    result = svc.resumen_costes_proyecto("P1")
    assert result["totales"]["margen"] == 25
    assert result["desglose"]["mano_obra"]["pct_coste"] == 60
    assert svc.resumen_costes_proyecto("P1")["totales"]["pct_margen"] == 0


@pytest.mark.parametrize("rows", [[], [{}], [{"HUERFANOS": None}]])
def test_missing_check_result_never_passes(monkeypatch, rows):
    monkeypatch.setattr(svc, "_exec", lambda sql: (rows, 0))
    result = svc.verificacion_coherencia()
    assert result["n_ok"] == 0
    assert result["resumen"]["no_verificable"] == result["n_checks"]
    assert result["n_falla"] == 0


def test_checks_continue_after_error(monkeypatch):
    from backend.modules.api_clone.utilidades.check_catalog import CHECKS
    query_count = sum(bool(c["sql"]) for c in CHECKS)
    execute = MagicMock(side_effect=[RuntimeError("BD no disponible")] + [
        ([{"TOTAL": 1, "INCIDENCIAS": 0}], 0)] * (query_count - 1))
    monkeypatch.setattr(svc, "_exec", execute)
    result = svc.verificacion_coherencia()
    assert result["n_ok"] == query_count - 1
    assert result["resumen"]["no_verificable"] == len(CHECKS) - query_count + 1
    assert result["n_falla"] == 0
    assert result["checks"][0]["resultado"] is None


def test_project_quotes_are_escaped(monkeypatch):
    execute = MagicMock(side_effect=[([{"CODIGO": "O'Brien", "FINOBRA": "F"}], 0),
        ([dict.fromkeys(("LINEAS", "RECURSOS", "MO", "MO_REAL", "MO_PREVISTA", "MO_POSITIVA", "MO_SIN_RECURSO"), 0)], 0), ([], 0)])
    monkeypatch.setattr(svc, "_exec", execute)
    assert svc.horas_por_tecnico("O'Brien")["ok"]
    assert all("'O''Brien'" in call.args[0] for call in execute.call_args_list)


def test_http_grouped_report(client, monkeypatch):
    monkeypatch.setattr(svc, "_exec", lambda sql: ([{"TOTAL": 0, "INCIDENCIAS": 0}], 0))
    response = client.get("/api/api-clone/utilidades/verificacion-coherencia")
    assert response.status_code == 200
    report = response.json()
    assert len(report["grupos"]) == 6
    from backend.modules.api_clone.utilidades.check_catalog import CHECKS
    assert report["resumen"]["no_aplica"] == sum(bool(c["sql"]) for c in CHECKS)
    assert report["resumen"]["no_verificable"] == 3
    assert report["n_ok"] == 0


def test_report_download_preserves_failed_checks(client, monkeypatch):
    def unavailable(sql):
        raise RuntimeError("secret connection string")
    from contextlib import contextmanager
    from backend.modules.api_clone.utilidades import read_only
    @contextmanager
    def reader():
        yield unavailable
    monkeypatch.setattr(read_only, "open_reader", reader)
    response = client.get("/api/api-clone/utilidades/informe-fiabilidad.txt")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert "GARANTÍA DEL 100 %: NO DEMOSTRADA" in response.text
    assert "No verificable" in response.text
    assert "secret connection string" not in response.text
    assert "PRUEBAS NO REALIZADAS" in response.text


def test_report_contains_all_evidence_and_valid_hash():
    import hashlib
    import json
    from backend.modules.api_clone.utilidades.report import build_report
    from backend.modules.api_clone.utilidades.check_catalog import CHECKS
    calls = []
    def execute(sql):
        calls.append(sql)
        return [{"TOTAL": 10, "INCIDENCIAS": 2}], 1
    report = build_report(execute)
    assert calls[:-1] == [c["sql"] for c in CHECKS if c["sql"]]
    payload = report[report.rindex('La huella detecta cambios del JSON; no acredita la veracidad de la fuente.\n') + len('La huella detecta cambios del JSON; no acredita la veracidad de la fuente.\n'):].rstrip('\n')
    evidence = json.loads(payload)
    assert len(evidence["checks"]) == len(CHECKS)
    assert hashlib.sha256(payload.encode("utf-8")).hexdigest() in report
    assert all(c["estado_codigo"] == "revisar" for c in evidence["checks"] if c["sql"])



def test_report_connection_failure_is_503_not_successful_download(client, monkeypatch):
    from backend.modules.api_clone.utilidades import read_only
    def fail():
        raise RuntimeError("secret credentials")
    monkeypatch.setattr(read_only, "open_reader", fail)
    response=client.get("/api/api-clone/utilidades/informe-fiabilidad.txt")
    assert response.status_code==503
    assert "secret credentials" not in response.text
    assert "content-disposition" not in response.headers
