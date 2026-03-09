"""
test_preguntas_1tabla.py — Tests e2e de preguntas que usan 1 tabla.

CAPA: e2e (requiere BD Firebird + Qwen3 LAN)
EJECUTAR: .venv/Scripts/pytest tests/e2e/test_preguntas_1tabla.py -v -s

INDEPENDENCIA:
  - Sin IPs ni tablas hardcodeadas. Todo desde test.properties vía conftest.py.
  - helpers.py centraliza la lógica de traza y auditoría de red.
  - Se salta si BD o Qwen3 no disponibles.

PROPÓSITO:
  Verificar el flujo completo para preguntas simples:
  pregunta → SIUO (1 tabla) → SQL → BD → respuesta
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.e2e.helpers import ask_and_trace, assert_has_number, assert_no_markdown, assert_response_valid


# ═══════════════════════════════════════════════════════════════════════════════
# COUNT — 1 tabla, 1 valor numérico
# ═══════════════════════════════════════════════════════════════════════════════

class TestCount1Tabla:
    """Preguntas de conteo — flujo más simple posible."""

    @pytest.mark.asyncio
    async def test_count_articulos_metaglass(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos artículos hay", metaglass_ctx,
            test_name="count_articulos_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_has_number(resp, "cuántos artículos hay")
        assert_no_markdown(resp)

    @pytest.mark.asyncio
    async def test_count_clientes_metaglass(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos clientes tenemos", metaglass_ctx,
            test_name="count_clientes_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_has_number(resp, "cuántos clientes tenemos")
        assert_no_markdown(resp)

    @pytest.mark.asyncio
    async def test_count_proveedores_metaglass(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos proveedores hay", metaglass_ctx,
            test_name="count_proveedores_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_has_number(resp, "cuántos proveedores hay")
        assert_no_markdown(resp)

    @pytest.mark.asyncio
    async def test_count_articulos_web(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos artículos hay en la base de datos", web_ctx,
            test_name="count_articulos_web",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántos artículos hay")


# ═══════════════════════════════════════════════════════════════════════════════
# Listado simple — 1 tabla, múltiples registros
# ═══════════════════════════════════════════════════════════════════════════════

class TestListado1Tabla:
    """Preguntas de listado simple — 1 tabla."""

    @pytest.mark.asyncio
    async def test_articulo_mas_caro(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "cuál es el artículo más caro", metaglass_ctx,
            test_name="articulo_mas_caro",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_almacenes(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "qué almacenes hay", metaglass_ctx,
            test_name="almacenes",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_familias_articulos(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "qué familias de artículos hay", web_ctx,
            test_name="familias_articulos",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)

    @pytest.mark.asyncio
    async def test_agentes(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp, _ = await ask_and_trace(
            chat_svc, "dame la lista de agentes", web_ctx,
            test_name="lista_agentes",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)
