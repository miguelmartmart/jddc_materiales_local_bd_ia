"""
conftest.py — Fixtures específicos de tests/qa_sql_obras/.

Reutiliza TestConfig y los fixtures compartidos de tests/conftest.py
(chat_svc, web_ctx, metaglass_ctx, db_driver, qwen3_url, test_config).
Aquí solo se añade lo que es propio de esta suite: verificar si el
simulador tiene datos listos (SIN generarlos nunca — ver regla de oro).
"""

import pytest


@pytest.fixture(scope="session")
def simulator_ready() -> bool:
    """
    True si el simulador está activado (simulator_enabled=true) y tiene datos.

    REGLA DE ORO (memoria simulator-data-rule): este fixture NUNCA debe
    generar datos (build_synthetic / build_snapshot / seed_all). Si el
    simulador no está listo, el test que dependa de esto debe hacer
    pytest.skip — nunca intentar arreglarlo aquí.
    """
    try:
        from backend.modules.db_simulator.manager import simulator_manager
        if not simulator_manager.is_enabled():
            return False
        status = simulator_manager.get_status()
        return status.get("total_rows", 0) > 0
    except Exception:
        return False
