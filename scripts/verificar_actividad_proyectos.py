"""Validación de selector y actividad con datos reales, exclusivamente SELECT."""
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import firebirdsql
    from backend.core.config.settings import settings
    from backend.modules.api_clone.utilidades.project_activity import inspect_project
    from backend.modules.api_clone.utilidades.project_lookup import search
    from backend.modules.api_clone.utilidades.service import _safe

    connection = firebirdsql.connect(host=settings.DB_HOST, port=settings.DB_PORT,
        database=settings.DB_NAME, user=settings.DB_USER, password=settings.DB_PASSWORD,
        charset="latin1", timeout=20, isolation_level=firebirdsql.ISOLATION_LEVEL_READ_COMMITED_RO)

    class Driver:
        def execute_query(self, sql, params=None):
            assert sql.lstrip().upper().startswith("SELECT ")
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params or ())
                columns = [c[0] for c in cursor.description]
                return _safe([dict(zip(columns, row)) for row in cursor.fetchall()])
            finally:
                cursor.close()

        def disconnect(self):
            pass

    driver = Driver()
    try:
        first = search(lambda: driver)
        second = search(lambda: driver, offset=15)
        exact = search(lambda: driver, "1001331")
        assert not ({v["id"] for v in first["valores"]} & {v["id"] for v in second["valores"]})
        assert "1001331" in {v["id"] for v in exact["valores"]}
        output = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "total_proyectos": first["total"],
                  "paginacion_sin_solapamientos": True, "busqueda_verificada": True, "proyectos": []}
        for code in ("1001331", "10", "45215"):
            result = inspect_project(lambda sql: (driver.execute_query(sql), 0), code)
            assert result["ok"], result
            output["proyectos"].append({"codigo": code, "actividad": result["actividad"],
                "recursos_mostrados": len(result["tecnicos"]), "horas_verificadas": result["horas_verificadas"],
                "mensaje": result["mensaje"]})
        (ROOT / "docs" / "validacion_actividad_proyectos_2026_09_17.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(output, ensure_ascii=True))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
