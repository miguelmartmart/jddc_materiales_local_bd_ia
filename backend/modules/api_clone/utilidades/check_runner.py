"""Ejecuta checks sin convertir falta de datos o errores en éxitos."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import logging
import time

from .check_catalog import CHECKS, GROUPS

logger = logging.getLogger(__name__)
LABELS = {"correcto": "Correcto", "revisar": "Revisar",
          "no_verificable": "No verificable", "no_aplica": "No aplica"}


def _count(row, key):
    raw = row.get(key, row.get(key.lower()))
    if raw is None or isinstance(raw, bool):
        raise ValueError("Contador ausente")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ValueError("Contador inválido") from None
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        raise ValueError("Contador inválido")
    return int(value)


def run_checks(execute):
    started = time.monotonic()
    checks = []
    for spec in CHECKS:
        item = {**spec, "resultado": None, "total_evaluado": None, "ms": 0}
        status = "no_verificable"
        detail = spec["descripcion"]
        if spec["sql"]:
            try:
                rows, ms = execute(spec["sql"])
                if len(rows) != 1:
                    raise ValueError("Resultado agregado ausente o ambiguo")
                total, count = _count(rows[0], "TOTAL"), _count(rows[0], "INCIDENCIAS")
                if count > total:
                    raise ValueError("Contadores incoherentes")
                status = "no_aplica" if total == 0 else "revisar" if count else "correcto"
                detail = ("No hay registros que cumplan las condiciones de este check. No demuestra que el sistema completo sea correcto."
                          if not total else f"{count} de {total} registros requieren revisión en esta comprobación.")
                item.update(resultado=count, total_evaluado=total, ms=ms)
            except Exception as exc:
                detail = "No se pudo completar la consulta. El resultado es desconocido; comprueba la conexión y vuelve a intentarlo."
                logger.warning("Check %s no verificable (%s)", spec["id"], type(exc).__name__)
        item.update(estado_codigo=status, estado=LABELS[status], ok=status == "correcto", detalle=detail)
        checks.append(item)
    counts = {key: sum(c["estado_codigo"] == key for c in checks) for key in LABELS}
    groups = []
    for group in GROUPS:
        items = [c for c in checks if c["grupo"] == group["id"]]
        status = next((key for key in ("revisar", "no_verificable", "correcto", "no_aplica")
                       if any(c["estado_codigo"] == key for c in items)), "no_verificable")
        groups.append({**group, "estado_codigo": status, "estado": LABELS[status], "checks": items})
    return {"ok": True, "timestamp": datetime.now(timezone.utc).isoformat(),
            "alcance": "Comprobación global de la base configurada; no certifica un proyecto seleccionado ni autoriza operaciones.",
            "veredicto": f"{counts['revisar']} para revisar · {counts['no_verificable']} no verificables",
            "nota": "Correcto solo se refiere a la regla indicada. Las consultas se ejecutan por separado y no forman una instantánea común.",
            "n_checks": len(checks), "n_ok": counts["correcto"], "n_falla": counts["revisar"],
            "resumen": counts, "grupos": groups, "checks": checks,
            "fuente": "Consultas de lectura Firebird y limitaciones documentadas",
            "ms_total": round((time.monotonic() - started) * 1000)}
