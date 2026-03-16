"""
unsolvable_error_registry.py — Registro de errores irresolubles por el sistema automático.

FILOSOFÍA:
  Hay errores que NI el normalizador determinista NI la IA pueden resolver
  automáticamente porque requieren intervención humana:
    - Esquema de BD desconocido (tabla/columna que no existe y no hay alternativa)
    - Lógica de negocio ambigua que la IA no puede inferir del contexto
    - Errores de permisos de BD (acceso denegado)
    - Errores de integridad referencial que requieren datos reales
    - Funciones UDF personalizadas de Firebird no documentadas
    - Cualquier error que agote todos los reintentos sin solución

FUNCIONAMIENTO:
  1. Cuando sql_corrector.execute_with_correction() agota todos los reintentos
     sin resolver el error → llama a register_unsolvable_error()
  2. El error se guarda en unsolvable_errors.json con:
     - timestamp, pregunta original, SQL fallido, error, tipo, intentos
     - hash único para deduplicar (mismo error no se registra dos veces)
  3. Al arrancar el servidor (lifespan) → check_and_alert_unsolvable_errors()
     imprime alertas en log y consola si hay errores pendientes de revisión
  4. Los errores se marcan como "revisado" manualmente o via API

INTEGRACIÓN:
  - sql_corrector.py: llama a register_unsolvable_error() en el except final
  - main.py lifespan: llama a check_and_alert_unsolvable_errors() al arrancar

AUTOR: DEVIA System · v1.0.0
"""

import json
import os
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ─── Ruta del fichero de registro ────────────────────────────────────────────
_REGISTRY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "core", "config", "unsolvable_errors.json"
)
_REGISTRY_PATH = os.path.normpath(_REGISTRY_PATH)

# ─── Categorías de errores irresolubles ──────────────────────────────────────
# Ayuda a priorizar la revisión humana.
UNSOLVABLE_CATEGORIES = {
    "unknown_error":        "❓ Error desconocido — no clasificado por el sistema",
    "max_retries_exceeded": "🔁 Máximo de reintentos agotado sin solución",
    "ai_correction_failed": "🤖 La IA no pudo generar una corrección válida",
    "placeholder_unresolved": "📌 Placeholder <...> no resuelto — falta dato del usuario",
    "permission_denied":    "🔒 Permiso denegado en la BD",
    "schema_unknown":       "🗂️ Tabla/columna no existe y no hay alternativa conocida",
    "logic_ambiguous":      "🧠 Lógica de negocio ambigua — requiere aclaración humana",
    "udf_unknown":          "⚙️ Función UDF personalizada de Firebird no documentada",
    "data_integrity":       "🔗 Error de integridad referencial",
    "other":                "📋 Otro error no categorizado",
}


def _compute_hash(question: str, sql: str, error: str) -> str:
    """Hash SHA-256 de los 3 campos clave para deduplicar entradas."""
    content = f"{question.strip()}|{sql.strip()}|{error.strip()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _load_registry() -> Dict[str, Any]:
    """Carga el registro desde disco. Devuelve dict vacío si no existe o está corrupto."""
    if not os.path.exists(_REGISTRY_PATH):
        return {"errors": [], "_meta": {"version": "1.0", "total_registered": 0}}
    try:
        with open(_REGISTRY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if "errors" not in data:
            data["errors"] = []
        return data
    except Exception as e:
        logger.warning(f"[UNSOLVABLE REGISTRY] ⚠️ No se pudo leer el registro: {e}. Iniciando vacío.")
        return {"errors": [], "_meta": {"version": "1.0", "total_registered": 0}}


def _save_registry(data: Dict[str, Any]) -> None:
    """Guarda el registro en disco de forma atómica (write + rename)."""
    try:
        os.makedirs(os.path.dirname(_REGISTRY_PATH), exist_ok=True)
        tmp_path = _REGISTRY_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, _REGISTRY_PATH)
    except Exception as e:
        logger.error(f"[UNSOLVABLE REGISTRY] ❌ No se pudo guardar el registro: {e}")


def register_unsolvable_error(
    question: str,
    sql: str,
    error_message: str,
    error_type: str = "unknown_error",
    attempts: int = 0,
    context: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Registra un error irresoluble en unsolvable_errors.json.

    Parámetros:
      question:      Pregunta original del usuario
      sql:           SQL que falló (último intento)
      error_message: Mensaje de error de Firebird
      error_type:    Categoría del error (ver UNSOLVABLE_CATEGORIES)
      attempts:      Número de intentos realizados
      context:       Contexto adicional (tablas, columnas, etc.)
      extra:         Dict con datos adicionales libres

    Retorna:
      El hash único del error registrado (para referencia en logs)

    Comportamiento:
      - Si el mismo error ya está registrado (mismo hash) → actualiza contador
        de ocurrencias y timestamp de última vez, NO duplica
      - Si es nuevo → añade entrada nueva con estado "pending"
    """
    error_hash = _compute_hash(question, sql, error_message)
    registry = _load_registry()

    # Buscar si ya existe este error
    existing = next(
        (e for e in registry["errors"] if e.get("hash") == error_hash),
        None
    )

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        # Actualizar contador de ocurrencias
        existing["occurrences"] = existing.get("occurrences", 1) + 1
        existing["last_seen"] = now
        logger.warning(
            f"[UNSOLVABLE REGISTRY] ⚠️ Error ya registrado (hash={error_hash}, "
            f"ocurrencias={existing['occurrences']}): {error_message[:80]}"
        )
    else:
        # Nuevo error irresoluble
        entry = {
            "hash":          error_hash,
            "status":        "pending",   # pending | reviewed | resolved
            "category":      error_type,
            "category_desc": UNSOLVABLE_CATEGORIES.get(error_type, "Desconocido"),
            "first_seen":    now,
            "last_seen":     now,
            "occurrences":   1,
            "attempts":      attempts,
            "question":      question[:500],   # truncar para no inflar el fichero
            "sql_failed":    sql[:2000],
            "error_message": error_message[:500],
            "context":       (context or "")[:500],
            "extra":         extra or {},
            "resolution":    None,   # se rellena manualmente cuando se resuelve
        }
        registry["errors"].append(entry)
        meta = registry.setdefault("_meta", {})
        meta["total_registered"] = meta.get("total_registered", 0) + 1
        meta["last_updated"] = now

        logger.error(
            f"[UNSOLVABLE REGISTRY] 🆕 Nuevo error irresoluble registrado "
            f"(hash={error_hash}, tipo={error_type}): {error_message[:80]}"
        )

    _save_registry(registry)
    return error_hash


def check_and_alert_unsolvable_errors() -> List[Dict[str, Any]]:
    """
    Comprueba si hay errores irresolubles pendientes de revisión.
    Llamar al arrancar el servidor (lifespan).

    Retorna la lista de errores pendientes.
    Imprime alertas en log y consola si hay errores pendientes.
    """
    registry = _load_registry()
    pending = [e for e in registry.get("errors", []) if e.get("status") == "pending"]

    if not pending:
        logger.info("[UNSOLVABLE REGISTRY] ✅ No hay errores irresolubles pendientes de revisión.")
        return []

    # ── Alerta visible en consola y log ──────────────────────────────────────
    sep = "=" * 70
    msg_lines = [
        "",
        sep,
        f"⚠️  ALERTA: {len(pending)} ERROR(ES) IRRESOLUBLE(S) PENDIENTE(S) DE REVISIÓN",
        f"   Fichero: {_REGISTRY_PATH}",
        sep,
    ]
    for i, err in enumerate(pending[:10], 1):  # mostrar máximo 10
        msg_lines.append(
            f"  [{i}] hash={err['hash']} | tipo={err['category']} | "
            f"ocurrencias={err.get('occurrences',1)} | "
            f"último={err.get('last_seen','?')[:19]}"
        )
        msg_lines.append(f"      Pregunta: {err.get('question','?')[:80]}")
        msg_lines.append(f"      Error:    {err.get('error_message','?')[:80]}")
        msg_lines.append(f"      Desc:     {err.get('category_desc','?')}")
        msg_lines.append("")

    if len(pending) > 10:
        msg_lines.append(f"  ... y {len(pending) - 10} más. Ver fichero completo.")
        msg_lines.append("")

    msg_lines += [
        "  ACCIÓN REQUERIDA:",
        "  1. Revisar el fichero unsolvable_errors.json",
        "  2. Para cada error: añadir 'resolution' y cambiar 'status' a 'reviewed'",
        "  3. Si el error es sistémico: añadir corrección determinista al normalizador",
        "  4. Si requiere cambio de esquema BD: coordinar con DBA",
        sep,
        "",
    ]

    full_msg = "\n".join(msg_lines)
    # Imprimir en consola (visible aunque el log esté en fichero)
    print(full_msg)
    # También en log como WARNING para que aparezca en los ficheros de log
    logger.warning(full_msg)

    return pending


def mark_error_reviewed(error_hash: str, resolution: str) -> bool:
    """
    Marca un error como revisado con la resolución aplicada.
    Llamar manualmente o via API de administración.

    Retorna True si se encontró y actualizó, False si no existe.
    """
    registry = _load_registry()
    for err in registry["errors"]:
        if err.get("hash") == error_hash:
            err["status"] = "reviewed"
            err["resolution"] = resolution
            err["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            _save_registry(registry)
            logger.info(
                f"[UNSOLVABLE REGISTRY] ✅ Error {error_hash} marcado como revisado: {resolution}"
            )
            return True
    logger.warning(f"[UNSOLVABLE REGISTRY] ⚠️ Error {error_hash} no encontrado en el registro.")
    return False


def get_pending_errors() -> List[Dict[str, Any]]:
    """Devuelve la lista de errores pendientes de revisión."""
    registry = _load_registry()
    return [e for e in registry.get("errors", []) if e.get("status") == "pending"]


def get_registry_summary() -> Dict[str, Any]:
    """Devuelve un resumen del estado del registro para monitorización."""
    registry = _load_registry()
    errors = registry.get("errors", [])
    by_status = {}
    by_category = {}
    for e in errors:
        s = e.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        c = e.get("category", "other")
        by_category[c] = by_category.get(c, 0) + 1
    return {
        "total": len(errors),
        "by_status": by_status,
        "by_category": by_category,
        "pending": by_status.get("pending", 0),
        "registry_path": _REGISTRY_PATH,
    }
