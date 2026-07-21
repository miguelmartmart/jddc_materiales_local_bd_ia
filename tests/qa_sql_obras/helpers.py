"""
helpers.py — Helpers propios de tests/qa_sql_obras/.

Reutiliza tests/e2e/helpers.py (ask_and_trace y los asserts) en vez de
duplicarlo, y añade solo lo que hace falta para cruzar cada pregunta con
la matriz modelo (30B/8B) x BD (real/simulador) — ver DEVIA.MD de esta
carpeta, sección "Diseño previsto".
"""

from typing import Dict, Optional

from tests.e2e.helpers import (  # noqa: F401 — re-exportados para los tests de esta carpeta
    ask_and_trace,
    assert_has_number,
    assert_no_markdown,
    assert_response_valid,
)

# IDs reales — fuente de verdad: backend/core/utils/network_audit_constants.py::LocalModelIds
MODEL_30B = "jddcia-qwen3-30b-ip"
MODEL_8B = "jddcia-qwen3-8b-ip"


def with_overrides(base_ctx: Dict, model_id: Optional[str] = None, db_mode: Optional[str] = None) -> Dict:
    """
    Copia un ctx base (web_ctx / metaglass_ctx) añadiendo preferred_model_id y/o db_mode.

    CAVEAT (ver registro de progreso 17/07/2026): preferred_model_id solo antepone
    ese modelo en la lista de fallback del ModelFallbackOrchestrator — si ese modelo
    concreto no responde, el orchestrator reintenta con el resto de modelos LAN
    automáticamente. Es decir, un test con model_id=MODEL_8B que pasa NO garantiza
    que haya respondido el 8B en vez del 30B; solo garantiza que "algún modelo LAN"
    respondió. Pendiente: capturar en la traza qué modelo respondió de verdad.
    """
    ctx = dict(base_ctx)
    if model_id:
        ctx["preferred_model_id"] = model_id
    if db_mode:
        ctx["db_mode"] = db_mode
    return ctx
