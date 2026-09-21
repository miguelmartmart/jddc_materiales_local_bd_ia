"""Prueba real de lectura, sin historial ni cambios en datos del ERP."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import firebirdsql
    from backend.core.config.settings import settings
    from backend.modules.api_clone import service
    connection=firebirdsql.connect(host=settings.DB_HOST,port=settings.DB_PORT,database=settings.DB_NAME,
        user=settings.DB_USER,password=settings.DB_PASSWORD,charset="latin1",timeout=20,
        isolation_level=firebirdsql.ISOLATION_LEVEL_READ_COMMITED_RO)
    class Driver:
        def execute_query(self,sql):
            assert sql.lstrip().upper().startswith("SELECT ")
            cursor=connection.cursor()
            try:
                cursor.execute(sql)
                names=[c[0] for c in cursor.description]
                return [dict(zip(names,row)) for row in cursor.fetchall()]
            finally:
                cursor.close()
        def disconnect(self):
            pass
    old=service._get_driver
    service._get_driver=lambda:Driver()
    evidence={"inicio_utc":datetime.now(timezone.utc).isoformat(),"modo":"READ COMMITTED READ ONLY",
        "alcance":"Muestra limitada: proyecto 45215, hasta cinco líneas por clase. No certifica todos los proyectos ni la equivalencia mPYME.","resultados":[]}
    try:
        api=service.ApiCloneService()
        keys=[]
        for clase,flag in [("proordutil",0),("proordprev",1)]:
            result=api._browse_sql(clase,{"codProyecto":"45215"},5)
            assert result["ok"],result.get("error")
            assert result["items"],"Muestra sin datos: no hay prueba positiva"
            seen=set()
            for row in result["items"]:
                assert str(row["CODPROYECTO"])=="45215" and row["ESPREVISION"]==flag
                key=f"{row['CODCAB']}:{row['CODIGO']}"
                detail=api._read_sql(clase,key)
                assert detail["ok"] and detail["data"]["CODPROYECTO"]==row["CODPROYECTO"]
                assert detail["data"]["CODCAB"]==row["CODCAB"] and detail["data"]["CODIGO"]==row["CODIGO"]
                assert not api._read_sql(clase,str(row["CODIGO"]))["ok"]
                seen.add(key)
            keys.append(seen)
            evidence["resultados"].append({"clase":clase,"total":result["total"],"claves_verificadas":sorted(seen),"sql":result["sql"]})
        assert keys[0].isdisjoint(keys[1])
        evidence["resultado"]="correcto_en_la_muestra"
    finally:
        service._get_driver=old
        connection.close()
    evidence["fin_utc"]=datetime.now(timezone.utc).isoformat()
    output=ROOT/"docs"/"lecturas_api_clone_2026_09_21.json"
    output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(evidence,ensure_ascii=False))

if __name__=="__main__":
    main()

