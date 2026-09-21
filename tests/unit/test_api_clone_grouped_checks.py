"""Estados de verificación: nunca certificar ausencia de datos ni errores."""
import pytest
from backend.modules.api_clone.utilidades.check_catalog import CHECKS, GROUPS
from backend.modules.api_clone.utilidades.check_runner import run_checks


@pytest.mark.parametrize("total,issues,status", [(0, 0, "no_aplica"), (10, 0, "correcto"), (10, 2, "revisar")])
def test_states(total, issues, status):
    result = run_checks(lambda sql: ([{"TOTAL": total, "INCIDENCIAS": issues}], 2))
    queried = [c for c in result["checks"] if c["sql"]]
    assert all(c["estado_codigo"] == status for c in queried)
    assert all(c["ok"] == (status == "correcto") for c in queried)
    assert result["resumen"]["no_verificable"] == 3
    assert sum(result["resumen"].values()) == len(CHECKS)


@pytest.mark.parametrize("row", [{}, {"TOTAL": None, "INCIDENCIAS": 0},
    {"TOTAL": 1, "INCIDENCIAS": None}, {"TOTAL": 1, "INCIDENCIAS": 2},
    {"TOTAL": -1, "INCIDENCIAS": 0}, {"TOTAL": 1.5, "INCIDENCIAS": 0},
    {"TOTAL": True, "INCIDENCIAS": 0}, {"TOTAL": "NaN", "INCIDENCIAS": 0},
    {"TOTAL": 1, "INCIDENCIAS": "Infinity"}])
def test_invalid_counts_are_unknown(row):
    result = run_checks(lambda sql: ([row], 0))
    assert result["resumen"]["no_verificable"] == len(CHECKS)
    assert result["n_ok"] == result["n_falla"] == 0


def test_all_groups_have_help_and_examples():
    result = run_checks(lambda sql: ([{"total": 2, "incidencias": 0}], 0))
    assert len(result["grupos"]) == 6
    assert {c["id"] for g in result["grupos"] for c in g["checks"]} == {c["id"] for c in CHECKS}
    assert all(g["ayuda"] and g["checks"] for g in result["grupos"])
    assert all(c["descripcion"] and c["ejemplo"] and c["accion"] for c in CHECKS)
    assert all(g["estado_codigo"] == "no_verificable" for g in result["grupos"] if g["id"] in {"estado", "prevision", "totales"})


def test_disconnect_is_not_a_green_report():
    calls = []
    def fail(sql):
        calls.append(sql)
        raise RuntimeError("private connection details")
    result = run_checks(fail)
    assert len(calls) == sum(bool(c["sql"]) for c in CHECKS)
    assert result["resumen"]["no_verificable"] == len(CHECKS)
    assert "private connection details" not in str(result)
    assert all(g["estado_codigo"] == "no_verificable" for g in result["grupos"])
