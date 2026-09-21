"""Contrastes de datos guiados por restricciones reales, sin modificar registros."""
from collections import defaultdict
import re

from .check_runner import _count
from .schema_evidence import TABLES


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value):
        raise ValueError("Identificador de esquema no admitido")
    return '"' + value + '"'


def check_constraints(execute, schema):
    checks = []
    grouped = defaultdict(list)
    for row in schema.get("restricciones", []):
        grouped[(row.get("TABLA"), row.get("RESTRICCION"))].append(row)
    for table in TABLES:
        has_pk = any(r.get("TABLA") == table and r.get("TIPO") == "PRIMARY KEY"
                     for r in schema.get("restricciones", []))
        checks.append({"tabla": table, "regla": "PK declarada", "estado": "inventariada" if has_pk else "no_verificable",
                       "nota": "No encontrar una PK no demuestra que los datos sean únicos ni que la tabla esté vacía."})
    for (table, constraint), rows in grouped.items():
        base = {"tabla": table, "restriccion": constraint, "tipo": rows[0].get("TIPO")}
        try:
            if table not in TABLES or not constraint:
                raise ValueError("Metadatos incompletos")
            rows = sorted(rows, key=lambda r: int(r["POSICION"]))
            if [int(r["POSICION"]) for r in rows] != list(range(len(rows))):
                raise ValueError("Segmentos incompletos")
            fields = [identifier(r["CAMPO"]) for r in rows]
            if len(set(fields)) != len(fields) or any(r["TIPO"] != base["tipo"] for r in rows):
                raise ValueError("Segmentos incoherentes")
            source = identifier(table)
            nonnull = " AND ".join(f"{f} IS NOT NULL" for f in fields)
            nulls = " OR ".join(f"{f} IS NULL" for f in fields)
            specs = [("Componentes nulos", source, nulls, "",
                      "revisar" if base["tipo"] == "PRIMARY KEY" else "informativo")]
            if base["tipo"] in {"PRIMARY KEY", "UNIQUE"}:
                keys = ",".join(fields)
                specs.append(("Grupos duplicados no nulos",
                              f"(SELECT {keys}, COUNT(*) AS N FROM {source} WHERE {nonnull} GROUP BY {keys}) K",
                              "K.N>1", "", "revisar"))
            elif base["tipo"] == "FOREIGN KEY":
                target = rows[0]["TABLA_REFERIDA"]
                if any(r["TABLA_REFERIDA"] != target for r in rows):
                    raise ValueError("Destino ambiguo")
                predicates = " AND ".join(f"P.{identifier(r['CAMPO_REFERIDO'])}=C.{f}" for r, f in zip(rows, fields))
                specs.append(("Referencias huérfanas no nulas", source + " C",
                              f"NOT EXISTS (SELECT 1 FROM {identifier(target)} P WHERE {predicates})",
                              " AND ".join(f"C.{f} IS NOT NULL" for f in fields), "revisar"))
                specs.append(("Referencia con varios destinos (multiplica JOIN)", source + " C",
                              f"(SELECT COUNT(*) FROM {identifier(target)} P WHERE {predicates})>1",
                              " AND ".join(f"C.{f} IS NOT NULL" for f in fields), "revisar"))
            else:
                raise ValueError("Restricción no admitida")
            for name, source, condition, cohort, issue_status in specs:
                sql = f"SELECT COUNT(*) AS TOTAL, COALESCE(SUM(CASE WHEN {condition} THEN 1 ELSE 0 END),0) AS INCIDENCIAS FROM {source}"
                if cohort:
                    sql += " WHERE " + cohort
                item = {**base, "regla": name, "sql": sql, "estado": "no_verificable"}
                try:
                    result, ms = execute(sql)
                    if len(result) != 1:
                        raise ValueError("Resultado incompleto")
                    total, issues = _count(result[0], "TOTAL"), _count(result[0], "INCIDENCIAS")
                    if issues > total:
                        raise ValueError("Conteos incoherentes")
                    item.update(total=total, incidencias=issues, ms=ms,
                                estado="no_aplica" if total == 0 else issue_status if issues else "correcto")
                except Exception:
                    item["nota"] = "Consulta no completada; no se interpreta como cero incidencias."
                checks.append(item)
            if any(r.get("INDICE_INACTIVO") not in (0, None) for r in rows):
                checks.append({**base, "regla": "Índice activo", "estado": "revisar"})
        except Exception:
            checks.append({**base, "regla": "Metadatos completos", "estado": "no_verificable"})
    return {"checks": checks, "resumen": {s: sum(c["estado"] == s for c in checks)
            for s in ("correcto", "revisar", "no_verificable", "no_aplica", "informativo", "inventariada")},
            "nota": "FK con algún componente NULL: dato incompleto, no huérfano probado. UNIQUE con NULL: no se declara duplicado por esa causa. Cada restricción se comprueba por separado; no sumar sus poblaciones."}
