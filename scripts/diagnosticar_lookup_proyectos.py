"""Diagnóstico de los 15 proyectos del botón BD. Solo lectura Firebird LAN."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    import firebirdsql
    from backend.core.config.settings import settings
    from backend.modules.api_clone import service as api
    from backend.modules.api_clone.utilidades import service as util

    result = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
              "solo_lectura": True, "errores": {}}
    connection = None
    original_api, original_util = api._get_driver, util._get_driver
    try:
        connection = firebirdsql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
            user=settings.DB_USER, password=settings.DB_PASSWORD, charset="latin1",
            timeout=20, isolation_level=firebirdsql.ISOLATION_LEVEL_READ_COMMITED_RO)

        def query(sql, params=()):
            if not sql.lstrip().upper().startswith("SELECT "):
                raise ValueError("Solo SELECT")
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                names = [col[0] for col in cursor.description]
                return [dict(zip(names, row)) for row in cursor.fetchall()]
            finally:
                cursor.close()

        class ReadOnlyDriver:
            execute_query = staticmethod(query)

            def disconnect(self):
                pass  # La conexión pertenece al diagnóstico y se cierra al terminar.

        # Ejecutar los servicios existentes con datos REALES; no usar su historial.
        api._get_driver = util._get_driver = lambda: ReadOnlyDriver()
        result["metadatos_cantidades"] = query("""SELECT TRIM(r.RDB$FIELD_NAME) AS CAMPO,
            f.RDB$FIELD_TYPE AS TIPO, f.RDB$FIELD_SCALE AS ESCALA,
            f.RDB$COMPUTED_SOURCE AS EXPRESION_CALCULADA, r.RDB$DESCRIPTION AS DESCRIPCION
            FROM RDB$RELATION_FIELDS r JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME=r.RDB$FIELD_SOURCE
            WHERE r.RDB$RELATION_NAME='OBRALIN'
            AND r.RDB$FIELD_NAME IN ('CANTIDAD','CANTIDADPADRE','CANTIDADREALDOCLIN','CANTIDADCERTANTDOCLIN','UNIDADMEDIDACANTIDAD','UNIDADMEDIDAFACTOR')
            ORDER BY r.RDB$FIELD_POSITION""")
        lookup = api.ApiCloneService.__new__(api.ApiCloneService).valores_campo("codProyecto", 15)
        if not lookup["ok"]:
            raise RuntimeError("Lookup fallido")
        codes = [row["id"] for row in lookup["valores"]]
        result["codigos_lookup"] = codes
        result["total_proyectos"] = query("SELECT COUNT(*) AS N FROM PROYECTOS")[0]["N"]
        if codes:
            placeholders = ",".join("?" for _ in codes)
            sql = """SELECT p.CODIGO, p.FINOBRA, COUNT(o.CODCAB) AS LINEAS_TODAS,
                SUM(CASE WHEN o.TIPOBC3=10 THEN 1 ELSE 0 END) AS LINEAS_MO,
                SUM(CASE WHEN o.TIPOBC3=10 AND o.CANTIDAD>0 THEN 1 ELSE 0 END) AS IMPUTACIONES_PANTALLA,
                COUNT(DISTINCT CASE WHEN o.TIPOBC3=10 AND o.CANTIDAD>0 THEN o.CODRECURSO ELSE NULL END) AS TECNICOS_PANTALLA,
                SUM(CASE WHEN o.TIPOBC3=10 AND o.CANTIDAD>0 AND o.ESPREVISION=0 THEN 1 ELSE 0 END) AS MO_REAL,
                SUM(CASE WHEN o.TIPOBC3=10 AND o.CANTIDAD>0 AND o.ESPREVISION=1 THEN 1 ELSE 0 END) AS MO_PREVISTA
                FROM PROYECTOS p LEFT JOIN OBRALIN o ON o.CODPROYECTO=p.CODIGO
                WHERE p.CODIGO IN (""" + placeholders + ") GROUP BY p.CODIGO,p.FINOBRA ORDER BY p.CODIGO"
            result["diagnostico_primeros_15"] = {"sql": sql, "filas": query(sql, tuple(codes))}
            sample = util.horas_por_tecnico(codes[0])
            result["servicio_primer_proyecto"] = {"codigo": codes[0], "ok": sample["ok"],
                                                  "totales": sample.get("totales"), "filas": len(sample.get("tecnicos", []))}
        positive = query("SELECT FIRST 1 o.CODPROYECTO FROM OBRALIN o "
                         "WHERE o.TIPOBC3=10 AND o.CANTIDAD>0 AND o.ESPREVISION=0 "
                         "AND EXISTS(SELECT 1 FROM PROYECTOS p WHERE p.CODIGO=o.CODPROYECTO)")
        if positive:
            code = positive[0]["CODPROYECTO"]
            sample = util.horas_por_tecnico(code)
            result["control_positivo"] = {"codigo": code, "ok": sample["ok"],
                                           "totales": sample.get("totales"), "filas": len(sample.get("tecnicos", []))}
        result["cobertura"] = query("""SELECT COUNT(*) AS PROYECTOS_CON_LINEAS,
            SUM(CASE WHEN d.MO>0 THEN 1 ELSE 0 END) AS CON_MO_POSITIVA,
            SUM(CASE WHEN d.MOREAL>0 THEN 1 ELSE 0 END) AS CON_MO_REAL_POSITIVA
            FROM (SELECT o.CODPROYECTO,
              SUM(CASE WHEN o.TIPOBC3=10 AND o.CANTIDAD>0 THEN 1 ELSE 0 END) AS MO,
              SUM(CASE WHEN o.TIPOBC3=10 AND o.CANTIDAD>0 AND o.ESPREVISION=0 THEN 1 ELSE 0 END) AS MOREAL
              FROM OBRALIN o JOIN PROYECTOS p ON p.CODIGO=o.CODPROYECTO GROUP BY o.CODPROYECTO) d""")
        result["mo_cantidades"] = query("""SELECT ESPREVISION,
            CASE WHEN CODPROYECTO IS NULL THEN 0 ELSE 1 END AS TIENE_PROYECTO,
            COUNT(*) AS LINEAS,
            SUM(CASE WHEN CANTIDAD IS NULL THEN 1 ELSE 0 END) AS CANTIDAD_NULA,
            SUM(CASE WHEN CANTIDAD=0 THEN 1 ELSE 0 END) AS CANTIDAD_CERO,
            SUM(CASE WHEN CANTIDAD<0 THEN 1 ELSE 0 END) AS CANTIDAD_NEGATIVA,
            SUM(CASE WHEN CANTIDAD>0 THEN 1 ELSE 0 END) AS CANTIDAD_POSITIVA,
            SUM(CASE WHEN CODRECURSO IS NOT NULL THEN 1 ELSE 0 END) AS RECURSO_INFORMADO,
            SUM(CASE WHEN CANTIDADREALDOCLIN>0 THEN 1 ELSE 0 END) AS CANTIDAD_REAL_DOC_POSITIVA,
            SUM(CASE WHEN CANTIDADPADRE>0 THEN 1 ELSE 0 END) AS CANTIDAD_PADRE_POSITIVA
            FROM OBRALIN WHERE TIPOBC3=10
            GROUP BY ESPREVISION,CASE WHEN CODPROYECTO IS NULL THEN 0 ELSE 1 END""")
        result["proyectos_mo_positiva"] = query("""SELECT o.CODPROYECTO,p.FINOBRA,
            COUNT(*) AS IMPUTACIONES_PANTALLA, COUNT(DISTINCT o.CODRECURSO) AS TECNICOS_PANTALLA,
            SUM(CASE WHEN o.ESPREVISION=0 THEN 1 ELSE 0 END) AS MO_REAL,
            SUM(CASE WHEN o.ESPREVISION=1 THEN 1 ELSE 0 END) AS MO_PREVISTA
            FROM OBRALIN o JOIN PROYECTOS p ON p.CODIGO=o.CODPROYECTO
            WHERE o.TIPOBC3=10 AND o.CANTIDAD>0
            GROUP BY o.CODPROYECTO,p.FINOBRA ORDER BY o.CODPROYECTO""")
        if result["proyectos_mo_positiva"]:
            code = result["proyectos_mo_positiva"][0]["CODPROYECTO"]
            sample = util.horas_por_tecnico(code)
            result["control_positivo_pantalla"] = {"codigo": code, "ok": sample["ok"],
                "totales": sample.get("totales"), "filas": len(sample.get("tecnicos", [])),
                "advertencia": "El servicio actual incluye previsiones; no equivale a horas reales."}
    except Exception as exc:
        result["errores"]["diagnostico"] = type(exc).__name__
    finally:
        api._get_driver, util._get_driver = original_api, original_util
        if connection:
            try:
                connection.close()
            except Exception as exc:
                result["errores"]["cierre"] = type(exc).__name__
    return result


if __name__ == "__main__":
    result = run()
    output = ROOT / "docs" / "diagnostico_lookup_proyectos_2026_09_17.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, default=str))
    sys.exit(1 if result["errores"] else 0)
