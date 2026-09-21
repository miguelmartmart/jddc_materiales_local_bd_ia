"""Actividad registrada por proyecto. No interpreta cantidades como horas."""


def inspect_project(execute, code, limit=20):
    code = str(code or "").strip()
    if not code:
        return {"ok": False, "error": "cod_proyecto obligatorio"}
    limit = max(1, min(int(limit), 100))
    escaped = code.replace("'", "''")
    where = f"CODPROYECTO='{escaped}'"
    try:
        project, _ = execute(f"SELECT CODIGO,NOMBRE,FINOBRA FROM PROYECTOS WHERE CODIGO='{escaped}'")
        if not project:
            return {"ok": False, "error": "El proyecto indicado no existe."}
        aggregate, ms = execute(f"""SELECT COUNT(*) AS LINEAS,
            COUNT(DISTINCT CASE WHEN TIPOBC3=10 THEN CODRECURSO ELSE NULL END) AS RECURSOS,
            COALESCE(SUM(CASE WHEN TIPOBC3=10 THEN 1 ELSE 0 END),0) AS MO,
            COALESCE(SUM(CASE WHEN TIPOBC3=10 AND ESPREVISION=0 THEN 1 ELSE 0 END),0) AS MO_REAL,
            COALESCE(SUM(CASE WHEN TIPOBC3=10 AND ESPREVISION=1 THEN 1 ELSE 0 END),0) AS MO_PREVISTA,
            COALESCE(SUM(CASE WHEN TIPOBC3=10 AND CANTIDAD>0 THEN 1 ELSE 0 END),0) AS MO_POSITIVA,
            COALESCE(SUM(CASE WHEN TIPOBC3=10 AND CODRECURSO IS NULL THEN 1 ELSE 0 END),0) AS MO_SIN_RECURSO
            FROM OBRALIN WHERE {where}""")
        if len(aggregate) != 1:
            raise ValueError("Resumen de actividad no disponible")
        totals = {k: int(aggregate[0][k]) for k in
                  ("LINEAS", "RECURSOS", "MO", "MO_REAL", "MO_PREVISTA", "MO_POSITIVA", "MO_SIN_RECURSO")}
        rows, _ = execute(f"""SELECT FIRST {limit} ol.CODRECURSO, r.DESCRIPCION AS TECNICO,
            COUNT(*) AS LINEAS_REGISTRADAS,
            SUM(CASE WHEN ol.ESPREVISION=0 THEN 1 ELSE 0 END) AS LINEAS_NO_PREVISTAS,
            SUM(CASE WHEN ol.ESPREVISION=1 THEN 1 ELSE 0 END) AS LINEAS_PREVISTAS,
            SUM(CASE WHEN ol.CANTIDAD>0 THEN 1 ELSE 0 END) AS LINEAS_CANTIDAD_POSITIVA
            FROM OBRALIN ol LEFT JOIN RECURSO r ON r.CODIGO=ol.CODRECURSO
            WHERE ol.CODPROYECTO='{escaped}' AND ol.TIPOBC3=10 AND ol.CODRECURSO IS NOT NULL
            GROUP BY ol.CODRECURSO,r.DESCRIPCION ORDER BY LINEAS_REGISTRADAS DESC,ol.CODRECURSO""")
        for row in rows:
            row["TECNICO"] = row.get("TECNICO") or "Referencia sin nombre en el catálogo"
        empty = not totals["LINEAS"]
        message = ("Este proyecto existe, pero no tiene líneas vinculadas directamente en OBRALIN. No podemos deducir su actividad en otras fuentes."
                   if empty else "Hay líneas registradas, pero ninguna de mano de obra." if not totals["MO"]
                   else "Se muestran los recursos referenciados en las líneas, aunque su cantidad sea cero. No equivale a personal asignado ni a horas realizadas.")
        closed = project[0].get("FINOBRA")
        return {"ok": True, "cod_proyecto": code, "proyecto": project[0], "tecnicos": rows,
                "actividad": totals, "horas_verificadas": False,
                "mensaje": message, "ms": ms, "fuente": "OBRALIN + RECURSO + PROYECTOS",
                "grupos": [
                    {"nombre": "Proyecto y estado", "estado_codigo": "revisar" if closed == "T" else "no_verificable",
                     "detalle": "Proyecto marcado como finalizado. Se consulta su histórico." if closed == "T" else "El indicador de fin no permite certificar por sí solo que se puedan registrar nuevos trabajos.",
                     "ayuda": "Un proyecto cerrado puede tener histórico. No se excluye ni se habilitan escrituras con esta consulta."},
                    {"nombre": "Datos y técnicos disponibles", "estado_codigo": "no_aplica" if empty else "revisar" if not totals["MO_POSITIVA"] or totals["MO_SIN_RECURSO"] else "correcto",
                     "detalle": message,
                     "ayuda": "Antes se exigía cantidad positiva para contar técnicos. Ahora se cuentan referencias de recurso en todas las líneas de mano de obra. Los recursos repetidos se cuentan una sola vez."},
                    {"nombre": "Horas reales y previsiones", "estado_codigo": "no_aplica" if not totals["MO"] else "no_verificable",
                     "detalle": "Horas y costes realizados: no verificados. Las líneas previstas se muestran separadas.",
                     "ayuda": "No convertimos CANTIDAD, CANTIDADPADRE o CANTIDADREALDOCLIN en horas sin contrastar su significado con SQL Obras. Una línea registrada no es una imputación de horas certificada."},
                ]}
    except Exception:
        return {"ok": False, "error": "No se pudo comprobar la actividad del proyecto. Revisa la conexión y vuelve a intentarlo."}
