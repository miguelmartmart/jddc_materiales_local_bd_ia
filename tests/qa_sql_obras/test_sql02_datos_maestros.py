"""
test_sql02_datos_maestros.py — Tests QA: módulo SQL-02 (Datos maestros y estructura operativa).

CAPA: qa_sql_obras (requiere Qwen3 LAN; BD real o simulador según el caso)
EJECUTAR: .venv/Scripts/pytest tests/qa_sql_obras/test_sql02_datos_maestros.py -v -s
FUENTE: form_automation/docs/MANUAL_SQL_OBRAS.md — módulo SQL-02, secciones 001-012
        (repo pendiente-fact, fuera de este submódulo)

TABLAS REALES CONFIRMADAS (backend/modules/db_simulator/schema.py):
  AGENTES, ALMACEN, FAMILIA, TARIFAS, SERIES, RECURSO
  (Zonas/Estaciones de trabajo/Mensajes personalizados/Datos adicionales/Horario
  laboral del manual NO tienen tabla confirmada — no se generan tests de esas
  entidades hasta confirmar dónde viven esos datos)

PRIMERA TANDA — proof of concept: valida que el patrón de override modelo
(30B/8B) x BD (real/simulador) funciona end-to-end, antes de escalar a
cientos de casos. Ver "Registro de progreso" en tests/qa_sql_obras/DEVIA.MD.

NOTA: no se ha podido ejecutar esta suite en el entorno donde se escribió
(sin acceso a la LAN JDDC ni al backend arrancado) — pendiente de que el
usuario la ejecute en su máquina y reporte resultados.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.qa_sql_obras.helpers import (
    MODEL_8B,
    MODEL_30B,
    ask_and_trace,
    assert_has_number,
    assert_response_valid,
    with_overrides,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-02-002 — Agentes (tabla real: AGENTES)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentes:

    @pytest.mark.asyncio
    async def test_cuantos_agentes_simulador(self, chat_svc, web_ctx, test_config, simulator_ready, qwen3_url):
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(web_ctx, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos agentes hay", ctx,
            test_name="sql02_cuantos_agentes_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántos agentes hay")

    @pytest.mark.asyncio
    async def test_cuantos_agentes_real_30b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        ctx = with_overrides(web_ctx, model_id=MODEL_30B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos agentes hay", ctx,
            test_name="sql02_cuantos_agentes_real_30b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántos agentes hay")

    @pytest.mark.asyncio
    async def test_lista_agentes_real_8b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        ctx = with_overrides(web_ctx, model_id=MODEL_8B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc, "dame la lista de agentes con su comisión", ctx,
            test_name="sql02_lista_agentes_real_8b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-02-003 — Almacenes (tabla real: ALMACEN)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlmacenes:

    @pytest.mark.asyncio
    async def test_que_almacenes_hay_simulador(self, chat_svc, metaglass_ctx, test_config, simulator_ready, qwen3_url):
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(metaglass_ctx, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc, "qué almacenes hay", ctx,
            test_name="sql02_almacenes_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-02-004 — Familias (tabla real: FAMILIA)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFamilias:

    @pytest.mark.asyncio
    async def test_cuantas_familias_hay_real_30b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        ctx = with_overrides(web_ctx, model_id=MODEL_30B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántas familias de artículos hay", ctx,
            test_name="sql02_cuantas_familias_real_30b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántas familias de artículos hay")


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-02-005 — Tarifas (tabla real: TARIFAS)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTarifas:

    @pytest.mark.asyncio
    async def test_que_tarifas_hay_simulador(self, chat_svc, web_ctx, test_config, simulator_ready, qwen3_url):
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(web_ctx, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc, "qué tarifas de precios hay configuradas", ctx,
            test_name="sql02_tarifas_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)
