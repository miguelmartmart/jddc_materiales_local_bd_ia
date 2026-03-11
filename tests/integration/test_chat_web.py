"""
test_chat_web.py — Tests de integración del ChatService para cliente web.

CAPA: integration (requiere BD Firebird + Qwen3 LAN)
MÓDULO: backend.modules.chat.service.ChatService
EJECUTAR: .venv/Scripts/pytest tests/integration/test_chat_web.py -v -s

INDEPENDENCIA:
  - Sin IPs hardcodeadas. Todo desde test.properties vía conftest.py.
  - Se salta si BD o Qwen3 no disponibles (SKIP_IF_UNAVAILABLE=true).

DIFERENCIAS CON METAGLASS:
  - El cliente web puede recibir Markdown (tablas, negrita, etc.)
  - Respuestas más largas permitidas (WEB_MAX_RESPONSE_LEN)
  - confirm_data_sending=True en el contexto
"""

import re
import sys
import time
from pathlib import Path
from typing import Dict

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ─── Helpers reutilizables (compartidos con test_chat_metaglass) ──────────────

async def _ask(chat_svc, question: str, ctx: Dict) -> str:
    """Helper: hace una pregunta y devuelve la respuesta como string."""
    resp = await chat_svc.process_message(question, ctx)
    return str(resp) if resp else ""


def _assert_web_response(resp: str, max_len: int):
    """Verifica que la respuesta web es válida (puede tener Markdown)."""
    assert resp, "Respuesta vacía"
    assert len(resp) > 5, f"Respuesta demasiado corta: '{resp}'"
    assert len(resp) <= max_len, (
        f"Respuesta demasiado larga: {len(resp)} > {max_len} chars"
    )


def _assert_contains_number(resp: str, context: str = ""):
    """Verifica que la respuesta contiene al menos un número."""
    assert re.search(r'\d+', resp), (
        f"No hay número en la respuesta para: '{context}': '{resp[:200]}'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas de COUNT
# ═══════════════════════════════════════════════════════════════════════════════

class TestCountWeb:
    """Preguntas de conteo para cliente web."""

    @pytest.mark.asyncio
    async def test_cuantos_articulos(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "cuántos artículos hay en la base de datos", web_ctx)
        _assert_web_response(resp, test_config.web_max_len)
        _assert_contains_number(resp, "cuántos artículos hay")

    @pytest.mark.asyncio
    async def test_cuantos_clientes(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "cuántos clientes tenemos registrados", web_ctx)
        _assert_web_response(resp, test_config.web_max_len)
        _assert_contains_number(resp, "cuántos clientes")

    @pytest.mark.asyncio
    async def test_total_ventas_año(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "total de ventas de este año", web_ctx)
        _assert_web_response(resp, test_config.web_max_len)
        assert resp


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas de listado con posible Markdown
# ═══════════════════════════════════════════════════════════════════════════════

class TestListadoWeb:
    """Preguntas de listado — el cliente web puede recibir tablas Markdown."""

    @pytest.mark.asyncio
    async def test_articulos_mas_vendidos(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        """REGRESIÓN: antes devolvía HISTORICOPRECIOS en lugar de DOCLIN."""
        resp = await _ask(chat_svc, "dime los artículos más vendidos", web_ctx)
        _assert_web_response(resp, test_config.web_max_len)
        # No debe mencionar tablas internas incorrectas
        assert "HISTORICOPRECIOS" not in resp
        assert "FOTOGRAF" not in resp

    @pytest.mark.asyncio
    async def test_ventas_por_agente(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "cuánto ha vendido cada agente este año", web_ctx)
        _assert_web_response(resp, test_config.web_max_len)
        assert resp

    @pytest.mark.asyncio
    async def test_ultimas_facturas(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "dame las últimas 10 facturas emitidas", web_ctx)
        _assert_web_response(resp, test_config.web_max_len)
        assert resp

    @pytest.mark.asyncio
    async def test_stock_articulos(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "artículos con stock a cero o sin stock", web_ctx)
        _assert_web_response(resp, test_config.web_max_len)
        assert resp


# ═══════════════════════════════════════════════════════════════════════════════
# Tiempo de respuesta web
# ═══════════════════════════════════════════════════════════════════════════════

class TestTiempoRespuestaWeb:
    """Verifica tiempos de respuesta para cliente web (umbral más alto que MetaGlass)."""

    @pytest.mark.asyncio
    async def test_tiempo_respuesta_simple(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        start = time.time()
        resp = await _ask(chat_svc, "cuántos artículos hay", web_ctx)
        elapsed = time.time() - start
        assert elapsed <= test_config.web_max_time, (
            f"Respuesta tardó {elapsed:.1f}s > máximo {test_config.web_max_time}s"
        )
        assert resp

    @pytest.mark.asyncio
    async def test_tiempo_respuesta_compleja(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        start = time.time()
        resp = await _ask(chat_svc, "ranking de artículos más vendidos por familia", web_ctx)
        elapsed = time.time() - start
        assert elapsed <= test_config.web_max_time, (
            f"Respuesta tardó {elapsed:.1f}s > máximo {test_config.web_max_time}s"
        )
        assert resp
