"""Informe reproducible de las comprobaciones disponibles; nunca certificación absoluta."""
import hashlib
import json
from datetime import datetime, timezone

from .check_runner import run_checks

VERSION = "2026-09-21.5"


def build_report(execute):
    started = datetime.now(timezone.utc).isoformat()
    result = run_checks(execute)
    from .schema_evidence import inspect_schema
    result["estructura"] = inspect_schema(execute)
    from .constraint_checks import check_constraints
    result["integridad_declarada"] = check_constraints(execute, result["estructura"])
    from .unassigned_analysis import classify_unassigned, reference_coverage
    result["sin_proyecto"] = classify_unassigned(execute)
    result["cobertura_referencias"] = reference_coverage(result["integridad_declarada"])
    result["fin_informe_utc"] = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    lines = [
        "DEVIA — INFORME DE COMPROBACIONES API CLONE", f"Versión del informe: {VERSION}",
        f"Inicio UTC: {started}", f"Fin UTC: {result['fin_informe_utc']}",
        "Origen: Firebird configurado en el servidor que genera este informe; no datos simulados.",
        "GARANTÍA DEL 100 %: NO DEMOSTRADA", result['alcance'], result['nota'],
        "Solo lectura. Se ejecutan de nuevo las consultas del catálogo, no se reutilizan resultados históricos.",
        "Cobertura: todas las filas que cumplen el WHERE de cada SQL; los grupos pueden solaparse.",
        "No sumar poblaciones de checks ni clases Discover All: pueden consultar las mismas filas.",
        "Un check correcto acredita solo su regla y población. No equivale a equivalencia con mPYME.",
        "RESUMEN", json.dumps(result['resumen'], ensure_ascii=False),
    ]
    for group in result['grupos']:
        lines += ["", f"GRUPO: {group['nombre']} — {group['estado']}", group['ayuda']]
        for check in group['checks']:
            lines += ["", f"{check['id']} — {check['nombre']} — {check['estado']}",
                      check['descripcion'], f"Resultado: {check['detalle']}",
                      f"Población evaluada: {check['total_evaluado']}; incidencias: {check['resultado']}; duración ms: {check['ms']}",
                      f"Ejemplo: {check['ejemplo']}", f"Acción: {check['accion']}",
                      "SQL ejecutado: " + (check['sql'] or "NO EJECUTADO: falta una regla validada.")]
    lines += ["", "PK / FK / UNIQUE DECLARADAS EN FIREBIRD",
              json.dumps(result["estructura"], ensure_ascii=False, indent=2)]
    integrity = result["integridad_declarada"]
    lines += ["", "CONTRASTE DE RESTRICCIONES CON LOS DATOS (todas las tablas mapeadas)",
              "PK: identidad completa. FK: referencia a otra tabla. UNIQUE: combinación que no debe repetirse.",
              "Inventariada significa encontrada en el esquema, no datos certificados.",
              integrity["nota"], "Resumen estructural: " + json.dumps(integrity["resumen"], ensure_ascii=False)]
    for check in integrity["checks"]:
        lines += [f"{check['tabla']} / {check.get('restriccion', '')} / {check['regla']}: {check['estado']}",
                  f"Evaluados: {check.get('total', 'no disponible')}; incidencias: {check.get('incidencias', 'no disponible')}"]
        if check.get("nota"):
            lines.append(check["nota"])
        if check.get("sql"):
            lines.append("SQL: " + check["sql"])

    lines += ["", "COBERTURA REAL DE LAS RELACIONES",
              "Una FK vacía no aporta corroboración aunque no existan referencias huérfanas.",
              json.dumps(result["cobertura_referencias"], ensure_ascii=False, indent=2),
              "", "CLASIFICACIÓN DE LÍNEAS SIN PROYECTO",
              json.dumps(result["sin_proyecto"], ensure_ascii=False, indent=2)]
    lines += ["", "PRUEBAS NO REALIZADAS POR ESTE INFORME",
              "Comparación independiente respuesta a respuesta con mPYME / SQL Obras.",
              "Aislamiento por proyecto de cada endpoint y tratamiento de claves compuestas.",
              "Reglas completas de borradores, bloqueos, permisos y cierre de ejercicio.",
              "Certificación de horas/costes, unidades, tarifas y conciliación contable.",
              "Paginación exhaustiva de todos los endpoints, concurrencia e instantánea transaccional común.",
              "Pruebas automáticas del código: no se ejecuta pytest desde este informe.",
              "La referencia a una obra existente no demuestra que la obra elegida en el parte sea correcta.",
              "EVIDENCIA ESTRUCTURADA COMPLETA (JSON)",
              "SHA-256 del JSON UTF-8 siguiente: " + hashlib.sha256(payload.encode('utf-8')).hexdigest(),
              "La huella detecta cambios del JSON; no acredita la veracidad de la fuente.", payload]
    return "\n".join(lines) + "\n"
