import sqlite3
import pytest
from backend.modules.api_clone.utilidades.unassigned_analysis import classify_unassigned, reference_coverage
from backend.modules.api_clone.utilidades.constraint_checks import check_constraints


def test_classification_is_disjoint_keeps_unknown_values_and_does_not_write():
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    db.executescript("""
    CREATE TABLE OBRACAB(CODIGO INTEGER,CODPROYECTO TEXT);
    CREATE TABLE REPARA(CODIGO INTEGER);
    CREATE TABLE OBRALIN(CODCAB INTEGER,CODPROYECTO TEXT,CODREPARA INTEGER,TIPOBC3 INTEGER,ESPREVISION INTEGER,FECHA TEXT);
    INSERT INTO OBRACAB VALUES(1,NULL),(2,'A'),(3,NULL),(3,NULL);
    INSERT INTO REPARA VALUES(10),(10);
    INSERT INTO OBRALIN VALUES(1,NULL,NULL,10,0,NULL),(1,NULL,10,20,1,'2026-01-01'),
    (1,NULL,99,999,NULL,NULL),(99,NULL,NULL,10,0,NULL),(3,NULL,NULL,10,0,NULL),
    (2,NULL,NULL,10,0,NULL),(1,'A',NULL,10,0,NULL);
    """)
    before=db.total_changes
    def execute(sql): return [dict(r) for r in db.execute(sql)],0
    report=classify_unassigned(execute)
    assert report["estado"]=="clasificado"
    assert report["total"]==5
    assert sum(g["LINEAS"] for g in report["grupos"])==5
    assert {g["CABECERA"] for g in report["grupos"]}=={"sin_cabecera","cabecera_ambigua","cabecera_sin_proyecto"}
    assert {g["REPARACION"] for g in report["grupos"]}=={"sin_referencia","referencia_existente","referencia_huerfana"}
    assert any(g["TIPO"]==999 and g["PREVISION"] is None for g in report["grupos"])
    assert db.total_changes==before
    db.close()


@pytest.mark.parametrize("rows", [[{}],[{"LINEAS":0}],[{"LINEAS":None}]])
def test_bad_result_cannot_be_classified(rows):
    assert classify_unassigned(lambda sql:(rows,0))["estado"]=="no_verificable"


def test_failure_is_not_an_empty_success():
    def fail(sql): raise RuntimeError("secret database details")
    result=classify_unassigned(fail)
    assert result["estado"]=="no_verificable" and result["total"] is None
    assert "secret" not in str(result)
    assert classify_unassigned(lambda sql:([],0))["estado"]=="no_aplica"


@pytest.mark.parametrize("total,missing,status",[(186,186,"sin_evidencia_por_esta_relacion"),(124,124,"sin_evidencia_por_esta_relacion"),(12398,12392,"parcial"),(10,0,"referencias_informadas"),(0,0,"no_aplica"),(1,2,"no_verificable"),(None,0,"no_verificable")])
def test_empty_foreign_keys_do_not_prove_correspondence(total,missing,status):
    result=reference_coverage({"checks":[{"tabla":"TEST","restriccion":"FK","tipo":"FOREIGN KEY","regla":"Componentes nulos","estado":"informativo","total":total,"incidencias":missing}]})
    assert result[0]["estado"]==status


def test_constraint_called_pk_but_declared_unique_is_not_a_primary_key():
    schema={"restricciones":[{"TABLA":"PRESUPROYE","RESTRICCION":"PRESUPROYE_PK","TIPO":"UNIQUE","CAMPO":"CODPROYECTO","POSICION":0}]}
    result=check_constraints(lambda sql:([{"TOTAL":10,"INCIDENCIAS":0}],0),schema)
    item=next(c for c in result["checks"] if c["tabla"]=="PRESUPROYE" and c["regla"]=="PK declarada")
    assert item["estado"]=="no_verificable"



def test_duplicate_groups_fail_instead_of_inflating_total():
    row={"CABECERA":"cabecera_sin_proyecto","REPARACION":"sin_referencia","TIPO":10,"PREVISION":0,"FECHA_PROPIA":"sin_fecha","LINEAS":2}
    result=classify_unassigned(lambda sql:([row,row],0))
    assert result["estado"]=="no_verificable" and result["total"] is None


def test_no_sql_injection_or_write_in_classifier():
    from backend.modules.api_clone.utilidades.unassigned_analysis import SQL
    assert SQL.lstrip().upper().startswith("SELECT ")
    assert ";" not in SQL
    assert "GROUP BY D.CABECERA" in SQL
