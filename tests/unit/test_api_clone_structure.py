"""SQL structure checks run against deliberately inconsistent synthetic records."""
import sqlite3
from backend.modules.api_clone.utilidades.check_catalog import CHECKS
from backend.modules.api_clone.utilidades.schema_evidence import inspect_schema


def test_structure_detects_duplicate_composite_keys_and_cross_project_lines():
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    db.executescript("""
    CREATE TABLE OBRALIN(CODCAB INTEGER,CODIGO INTEGER,CODPROYECTO TEXT,ESPREVISION INTEGER);
    CREATE TABLE OBRACAB(CODIGO INTEGER,CODPROYECTO TEXT,ESPREVISION INTEGER);
    INSERT INTO OBRACAB VALUES(1,'A',0),(2,'B',1);
    INSERT INTO OBRALIN VALUES(1,1,'A',0),(1,1,'B',1),(2,1,'B',1),(99,3,'A',0),(NULL,4,'A',0);
    """)
    expected={"CHK-014":2,"CHK-015":1,"CHK-018":1,"CHK-025":1,"CHK-026":1,"CHK-027":1}
    for spec in CHECKS:
        if spec["id"] in expected:
            row=db.execute(spec["sql"]).fetchone()
            assert row["INCIDENCIAS"] == expected[spec["id"]], spec["id"]
    db.close()


def test_schema_empty_is_unknown_not_certified():
    result=inspect_schema(lambda sql:([],0))
    assert result["estado"] == "no_verificable"


def test_schema_preserves_composite_segments_and_foreign_targets():
    rows=[{"TABLA":"OBRALIN","TIPO":"PRIMARY KEY","CAMPO":"CODCAB","POSICION":0},
          {"TABLA":"OBRALIN","TIPO":"PRIMARY KEY","CAMPO":"CODIGO","POSICION":1},
          {"TABLA":"OBRALIN","TIPO":"FOREIGN KEY","CAMPO":"CODCAB","TABLA_REFERIDA":"OBRACAB","CAMPO_REFERIDO":"CODIGO"}]
    result=inspect_schema(lambda sql:(rows,3))
    assert result["restricciones"] == rows
    assert result["estado"] == "inventariado"
