import sqlite3
from unittest.mock import MagicMock
import pytest
from backend.modules.api_clone.utilidades.constraint_checks import check_constraints
from backend.modules.api_clone.utilidades.schema_evidence import TABLES
from backend.modules.api_clone.queries import CLASE_TABLA_MAP


def test_all_api_tables_are_inventoried():
    assert {v[0] for v in CLASE_TABLA_MAP.values()} <= set(TABLES)


def database():
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    db.executescript("""
    CREATE TABLE OBRALIN(A INTEGER,B INTEGER);
    CREATE TABLE OBRACAB(A INTEGER,B INTEGER);
    INSERT INTO OBRACAB VALUES(1,1),(2,2);
    INSERT INTO OBRALIN VALUES(1,1),(1,2),(2,2),(2,2),(NULL,1),(NULL,1);
    """)
    def execute(sql):
        assert sql.startswith("SELECT ")
        return [dict(r) for r in db.execute(sql)],1
    return db,execute


def schema(kind):
    return {"restricciones":[{"TABLA":"OBRALIN","RESTRICCION":"TEST_KEY","TIPO":kind,
        "CAMPO":field,"POSICION":i,"TABLA_REFERIDA":"OBRACAB","CAMPO_REFERIDO":field,"INDICE_INACTIVO":0}
        for i,field in enumerate(["A","B"])]}


@pytest.mark.parametrize("kind",["PRIMARY KEY","UNIQUE","FOREIGN KEY"])
def test_complete_keys_nulls_and_duplicates_without_writes(kind):
    db,execute=database()
    before=db.total_changes
    r=check_constraints(execute,schema(kind))
    queried=[c for c in r["checks"] if c.get("sql")]
    nulls=next(c for c in queried if c["regla"]=="Componentes nulos")
    assert nulls["incidencias"]==2
    assert nulls["estado"]==("revisar" if kind=="PRIMARY KEY" else "informativo")
    other=next(c for c in queried if c["regla"]!="Componentes nulos")
    assert other["incidencias"]==1
    assert other["estado"]=="revisar"
    assert db.total_changes==before
    db.close()


def test_mutation_omitting_fk_segment_would_hide_orphan():
    db,execute=database()
    checks=check_constraints(execute,schema("FOREIGN KEY"))["checks"]
    c=next(c for c in checks if c["regla"]=="Referencias huérfanas no nulas")
    broken=c["sql"].replace(' AND P."B"=C."B"','')
    assert execute(c["sql"])[0][0]["INCIDENCIAS"]==1
    assert execute(broken)[0][0]["INCIDENCIAS"]==0
    db.close()


@pytest.mark.parametrize("corrupt", ["position","identifier","target"])
def test_bad_metadata_is_not_used_to_generate_sql(corrupt):
    data=schema("FOREIGN KEY")
    if corrupt=="position": data["restricciones"][1]["POSICION"]=3
    if corrupt=="identifier": data["restricciones"][0]["CAMPO"]='A; DELETE FROM OBRALIN'
    if corrupt=="target": data["restricciones"][1]["TABLA_REFERIDA"]='OTHER'
    execute=MagicMock(side_effect=AssertionError("No ejecutar"))
    r=check_constraints(execute,data)
    execute.assert_not_called()
    assert any(c["regla"]=="Metadatos completos" and c["estado"]=="no_verificable" for c in r["checks"])


def test_read_only_reader_enforces_mode_and_cleans_up(monkeypatch):
    import firebirdsql
    from backend.modules.api_clone.utilidades.read_only import open_reader
    connection=MagicMock()
    connect=MagicMock(return_value=connection)
    monkeypatch.setattr(firebirdsql,"connect",connect)
    with open_reader() as execute:
        for sql in ["DELETE FROM OBRALIN","UPDATE X SET A=1","SELECT 1; DELETE FROM X"]:
            with pytest.raises(ValueError): execute(sql)
    connection.cursor.assert_not_called()
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
    assert connect.call_args.kwargs["isolation_level"]==firebirdsql.ISOLATION_LEVEL_READ_COMMITED_RO


def test_read_only_cleanup_on_query_failure(monkeypatch):
    import firebirdsql
    from backend.modules.api_clone.utilidades.read_only import open_reader
    connection=MagicMock()
    connection.cursor.return_value.execute.side_effect=RuntimeError("query failed")
    monkeypatch.setattr(firebirdsql,"connect",lambda **kwargs:connection)
    with pytest.raises(RuntimeError):
        with open_reader() as execute: execute("SELECT X FROM Y")
    connection.cursor.return_value.close.assert_called_once()
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_fk_target_duplication_cannot_silently_multiply_rows():
    db,execute=database()
    db.execute("INSERT INTO OBRACAB VALUES(2,2)")
    result=check_constraints(execute,schema("FOREIGN KEY"))
    c=next(c for c in result["checks"] if "multiplica JOIN" in c["regla"])
    assert c["estado"]=="revisar" and c["incidencias"]==2
    db.close()


def test_incomplete_query_is_not_zero_incidents():
    result=check_constraints(lambda sql: ([],0),schema("PRIMARY KEY"))
    assert all(c["estado"]=="no_verificable" for c in result["checks"] if c.get("sql"))
