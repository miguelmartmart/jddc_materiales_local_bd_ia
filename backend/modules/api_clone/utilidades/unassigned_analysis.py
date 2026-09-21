"""Clasifica referencias sin obra; no deduce ni cambia asignaciones."""
from .check_runner import _count

DETAIL_SQL = """SELECT
 CASE WHEN c.N IS NULL THEN 'sin_cabecera'
      WHEN c.N>1 THEN 'cabecera_ambigua'
      ELSE 'cabecera_sin_proyecto' END AS CABECERA,
 CASE WHEN l.CODREPARA IS NULL THEN 'sin_referencia'
      WHEN r.CODIGO IS NOT NULL THEN 'referencia_existente'
      ELSE 'referencia_huerfana' END AS REPARACION,
 l.TIPOBC3 AS TIPO, l.ESPREVISION AS PREVISION,
 CASE WHEN l.FECHA IS NULL THEN 'sin_fecha' ELSE 'con_fecha' END AS FECHA_PROPIA
 FROM OBRALIN l
 LEFT JOIN (SELECT CODIGO,COUNT(*) AS N,COUNT(CODPROYECTO) AS PROYECTOS FROM OBRACAB GROUP BY CODIGO) c ON c.CODIGO=l.CODCAB
 LEFT JOIN (SELECT CODIGO FROM REPARA GROUP BY CODIGO) r ON r.CODIGO=l.CODREPARA
 WHERE l.CODPROYECTO IS NULL AND (c.PROYECTOS IS NULL OR c.PROYECTOS=0)
"""
SQL = "SELECT D.CABECERA,D.REPARACION,D.TIPO,D.PREVISION,D.FECHA_PROPIA,COUNT(*) AS LINEAS FROM (" + DETAIL_SQL + ") D GROUP BY D.CABECERA,D.REPARACION,D.TIPO,D.PREVISION,D.FECHA_PROPIA"


def classify_unassigned(execute):
    result = {"estado": "no_verificable", "sql": SQL, "grupos": [], "total": None,
              "alcance": "Líneas sin proyecto propio y sin cabecera que informe proyecto. Incluye cabeceras ausentes o ambiguas, señaladas por separado.",
              "nota": "Grupos disjuntos obtenidos con una única consulta. Una referencia de reparación existente no demuestra el origen ni autoriza asignar una obra. Tipo y previsión se conservan sin reinterpretar valores desconocidos."}
    try:
        rows, ms = execute(SQL)
        groups = []
        seen = set()
        for row in rows:
            labels = {key: row[key] for key in ("CABECERA", "REPARACION", "TIPO", "PREVISION", "FECHA_PROPIA")}
            key = tuple(labels.values())
            if key in seen:
                raise ValueError("Grupos repetidos")
            seen.add(key)
            count = _count(row, "LINEAS")
            if count == 0:
                raise ValueError("Grupo vacío inesperado")
            groups.append({**labels, "LINEAS": count})
        result.update(estado="clasificado" if groups else "no_aplica", grupos=groups,
                      total=sum(g["LINEAS"] for g in groups), ms=ms)
    except Exception:
        result["error"] = "No se pudo completar la clasificación; no se interpreta como ausencia de líneas."
    return result


def reference_coverage(integrity):
    """Un destino existente no corrobora filas cuya FK está vacía."""
    results = []
    for check in integrity.get("checks", []):
        if check.get("tipo") != "FOREIGN KEY" or check.get("regla") != "Componentes nulos":
            continue
        item = {"tabla": check.get("tabla"), "restriccion": check.get("restriccion"), "estado": "no_verificable"}
        try:
            total, missing = _count(check, "total"), _count(check, "incidencias")
            if missing > total or check.get("estado") == "no_verificable":
                raise ValueError("Cobertura desconocida")
            item.update(total=total, sin_referencia_completa=missing, con_referencia_completa=total-missing,
                        estado="no_aplica" if not total else "sin_evidencia_por_esta_relacion" if missing == total else "parcial" if missing else "referencias_informadas",
                        nota="Referencia informada no equivale a referencia válida ni a hecho confirmado. Contrastar los checks de huérfanos y de destinos múltiples.")
        except Exception:
            pass
        results.append(item)
    return results
