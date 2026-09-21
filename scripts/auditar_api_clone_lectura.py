"""Evidencias de esquema/contadores Firebird. Solo lectura, sin datos personales.

Desde la raíz DEVIA: .venv\Scripts\python.exe scripts/auditar_api_clone_lectura.py
--contadores añade distribuciones e integridad (puede recorrer OBRALIN completa).
No certifica semántica mPYME ni toma un snapshot común entre llamadas del API.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TABLES = ("PROYECTOS", "OBRALIN", "OBRACAB", "RECURSO", "PRESUPROYE",
          "PRESUCAB", "PRESULIN", "REPARA", "REPCAR", "TIPO", "FABCAB",
          "DOCCAB", "DOCLIN", "DOCLINIMPUTACION", "ARTICULO", "REPLIN")


def run(counts=False):
    import firebirdsql
    from backend.core.config.settings import settings

    result = {"inicio_utc": datetime.now(timezone.utc).isoformat(),
              "aislamiento": "READ_COMMITTED_RO", "conexion": False,
              "esquema": {}, "contadores": {}, "errores": {}}
    result["sha256_codigo"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("backend/modules/api_clone/service.py", "backend/modules/api_clone/queries.py",
                     "backend/modules/api_clone/router.py", "backend/modules/api_clone/utilidades/service.py",
                     "scripts/auditar_api_clone_lectura.py")}
    try:
        connection = firebirdsql.connect(
            host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
            user=settings.DB_USER, password=settings.DB_PASSWORD, charset="latin1",
            timeout=20, isolation_level=firebirdsql.ISOLATION_LEVEL_READ_COMMITED_RO)
    except Exception as exc:
        result["errores"]["conexion"] = type(exc).__name__
        return result
    result["conexion"] = True

    def query(sql, params=()):
        if not sql.lstrip().upper().startswith("SELECT "):
            raise ValueError("Solo SELECT")
        cur = connection.cursor()
        try:
            cur.execute(sql, params)
            names = [x[0].strip() for x in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchall()]
        finally:
            cur.close()

    try:
        for table in TABLES:
            columns = query("SELECT TRIM(RDB$FIELD_NAME) AS CAMPO FROM RDB$RELATION_FIELDS "
                            "WHERE RDB$RELATION_NAME = ? ORDER BY RDB$FIELD_POSITION", (table,))
            keys = query("SELECT TRIM(c.RDB$CONSTRAINT_TYPE) AS TIPO, "
                         "TRIM(c.RDB$CONSTRAINT_NAME) AS NOMBRE, "
                         "TRIM(s.RDB$FIELD_NAME) AS CAMPO, s.RDB$FIELD_POSITION AS POSICION "
                         "FROM RDB$RELATION_CONSTRAINTS c JOIN RDB$INDEX_SEGMENTS s "
                         "ON s.RDB$INDEX_NAME = c.RDB$INDEX_NAME "
                         "WHERE c.RDB$RELATION_NAME = ? ORDER BY 2,4", (table,))
            foreign = query("SELECT TRIM(s.RDB$FIELD_NAME) AS CAMPO, "
                            "TRIM(p.RDB$RELATION_NAME) AS TABLA_DESTINO, "
                            "TRIM(ps.RDB$FIELD_NAME) AS CAMPO_DESTINO "
                            "FROM RDB$RELATION_CONSTRAINTS c "
                            "JOIN RDB$REF_CONSTRAINTS r ON r.RDB$CONSTRAINT_NAME=c.RDB$CONSTRAINT_NAME "
                            "JOIN RDB$RELATION_CONSTRAINTS p ON p.RDB$CONSTRAINT_NAME=r.RDB$CONST_NAME_UQ "
                            "JOIN RDB$INDEX_SEGMENTS s ON s.RDB$INDEX_NAME=c.RDB$INDEX_NAME "
                            "JOIN RDB$INDEX_SEGMENTS ps ON ps.RDB$INDEX_NAME=p.RDB$INDEX_NAME "
                            "AND ps.RDB$FIELD_POSITION=s.RDB$FIELD_POSITION "
                            "WHERE c.RDB$RELATION_NAME=?", (table,))
            result["esquema"][table] = {"columnas": [c["CAMPO"] for c in columns],
                                         "claves": keys, "fk": foreign}
        if counts:
            sqls = {
                "proyectos_estados": "SELECT FINOBRA, TIPOOBRA, COUNT(*) AS N FROM PROYECTOS GROUP BY FINOBRA, TIPOOBRA",
                "previsiones": "SELECT ESPREVISION, TIPOBC3, COUNT(*) AS N FROM OBRALIN GROUP BY ESPREVISION, TIPOBC3",
                "proyecto_nulo": "SELECT COUNT(*) AS N FROM OBRALIN WHERE CODPROYECTO IS NULL",
                "proyecto_vacio": "SELECT COUNT(*) AS N FROM OBRALIN WHERE TRIM(CODPROYECTO) = ''",
                "proyecto_huerfano": "SELECT COUNT(*) AS N FROM OBRALIN o WHERE o.CODPROYECTO IS NOT NULL AND NOT EXISTS (SELECT 1 FROM PROYECTOS p WHERE p.CODIGO=o.CODPROYECTO)",
                "tecnico_huerfano": "SELECT COUNT(*) AS N FROM OBRALIN o WHERE o.TIPOBC3=10 AND o.CODRECURSO IS NOT NULL AND NOT EXISTS (SELECT 1 FROM RECURSO r WHERE r.CODIGO=o.CODRECURSO)",
                "codigo_linea_ambiguo": "SELECT COUNT(*) AS N FROM (SELECT CODIGO FROM OBRALIN GROUP BY CODIGO HAVING COUNT(*)>1) d",
                "codigo_linea_varios_proyectos": "SELECT COUNT(*) AS N FROM (SELECT CODIGO FROM OBRALIN GROUP BY CODIGO HAVING COUNT(DISTINCT CODPROYECTO)>1) d",
                "presupuesto_varios_proyectos": "SELECT COUNT(*) AS N FROM (SELECT CODPRESUPUESTO FROM PRESUPROYE GROUP BY CODPRESUPUESTO HAVING COUNT(DISTINCT CODPROYECTO)>1) d",
                "fechas_proyectos": "SELECT COUNT(*) AS N FROM PROYECTOS WHERE FECHAINICIO IS NOT NULL AND FECHAFIN IS NOT NULL AND FECHAFIN<FECHAINICIO",
                "fechas_lineas": "SELECT SUM(CASE WHEN o.FECHA IS NULL THEN 1 ELSE 0 END) AS SIN_FECHA, SUM(CASE WHEN o.FECHA<p.FECHAINICIO THEN 1 ELSE 0 END) AS ANTES_INICIO, SUM(CASE WHEN o.FECHA>p.FECHAFIN THEN 1 ELSE 0 END) AS DESPUES_FIN, SUM(CASE WHEN o.FECHA>CURRENT_DATE THEN 1 ELSE 0 END) AS FUTURAS FROM OBRALIN o LEFT JOIN PROYECTOS p ON p.CODIGO=o.CODPROYECTO",
                "lineas_por_finobra": "SELECT p.FINOBRA, COUNT(*) AS N FROM OBRALIN o JOIN PROYECTOS p ON p.CODIGO=o.CODPROYECTO GROUP BY p.FINOBRA",
                "signos": "SELECT SUM(CASE WHEN COSTE<0 THEN 1 ELSE 0 END) AS COSTE_NEGATIVO, SUM(CASE WHEN CANTIDAD<0 THEN 1 ELSE 0 END) AS CANTIDAD_NEGATIVA, SUM(CASE WHEN TIPOBC3 IS NULL THEN 1 ELSE 0 END) AS TIPO_NULO FROM OBRALIN",
                "cabecera_proyecto": "SELECT COUNT(*) AS N, SUM(CASE WHEN o.CODPROYECTO IS NULL AND p.CODIGO IS NOT NULL THEN 1 ELSE 0 END) AS LINEA_NULA_CON_PROYECTO_CAB, SUM(CASE WHEN o.CODPROYECTO IS NOT NULL AND o.CODPROYECTO<>c.CODPROYECTO THEN 1 ELSE 0 END) AS PROYECTOS_DIFERENTES, SUM(CASE WHEN c.CODIGO IS NULL THEN 1 ELSE 0 END) AS SIN_CABECERA, SUM(CASE WHEN p.CODIGO IS NULL THEN 1 ELSE 0 END) AS SIN_PROYECTO_CAB FROM OBRALIN o LEFT JOIN OBRACAB c ON c.CODIGO=o.CODCAB LEFT JOIN PROYECTOS p ON p.CODIGO=c.CODPROYECTO",
                "cabecera_prevision": "SELECT o.ESPREVISION AS LINEA, c.ESPREVISION AS CABECERA, COUNT(*) AS N FROM OBRALIN o JOIN OBRACAB c ON c.CODIGO=o.CODCAB GROUP BY o.ESPREVISION,c.ESPREVISION",
                "fechas_cabecera": "SELECT SUM(CASE WHEN o.FECHA IS NULL AND c.FECHA IS NOT NULL THEN 1 ELSE 0 END) AS LINEA_NULA_CAB_FECHADA, SUM(CASE WHEN o.FECHA IS NOT NULL AND c.FECHA IS NOT NULL AND o.FECHA<>c.FECHA THEN 1 ELSE 0 END) AS FECHAS_DISTINTAS FROM OBRALIN o JOIN OBRACAB c ON c.CODIGO=o.CODCAB",
                "recursos_baja": "SELECT COUNT(*) AS N FROM RECURSO WHERE FECHABAJA IS NOT NULL AND FECHABAJA<=CURRENT_DATE",
                "articulos_baja": "SELECT BAJA,COUNT(*) AS N FROM ARTICULO GROUP BY BAJA",
                "repara_estados": "SELECT CODESTADO,ESTADOCIERRE,COUNT(*) AS N FROM REPARA GROUP BY CODESTADO,ESTADOCIERRE",
                "documentos_tipos": "SELECT TIPO,COUNT(*) AS N FROM DOCCAB GROUP BY TIPO",
                "imputaciones_proyecto_huerfano": "SELECT COUNT(*) AS N FROM DOCLINIMPUTACION d WHERE d.CODPROYECTO IS NOT NULL AND NOT EXISTS (SELECT 1 FROM PROYECTOS p WHERE p.CODIGO=d.CODPROYECTO)",
                "previsiones_con_proyecto": "SELECT ESPREVISION,COUNT(*) AS N FROM OBRALIN WHERE CODPROYECTO IS NOT NULL GROUP BY ESPREVISION",
            }
            for name, sql in sqls.items():
                print("Comprobando " + name, flush=True)
                try:
                    result["contadores"][name] = {"sql": sql, "filas": query(sql)}
                except Exception as exc:
                    result["errores"][name] = type(exc).__name__
                    break  # No continuar sobre una conexión potencialmente interrumpida.
    except Exception as exc:
        result["errores"]["auditoria"] = type(exc).__name__
    finally:
        try:
            connection.close()
        except Exception as exc:
            result["errores"]["cierre"] = type(exc).__name__
    result["fin_utc"] = datetime.now(timezone.utc).isoformat()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contadores", action="store_true")
    args = parser.parse_args()
    result = run(args.contadores)
    output = ROOT / "docs" / "auditoria_api_clone_2026_09_17_evidencias.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"archivo": str(output), "conexion": result["conexion"], "errores": result["errores"]}))
    sys.exit(1 if result["errores"] else 0)
