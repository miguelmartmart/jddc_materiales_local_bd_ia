"""
test_chat_metaglass.py — Tests de integración del ChatService para MetaGlass.

CAPA: integration (requiere BD Firebird + Qwen3 LAN)
MÓDULO: backend.modules.chat.service.ChatService
EJECUTAR: .venv/Scripts/pytest tests/integration/test_chat_metaglass.py -v -s

INDEPENDENCIA:
  - Sin IPs hardcodeadas. Todo desde test.properties vía conftest.py.
  - Se salta si BD o Qwen3 no disponibles (SKIP_IF_UNAVAILABLE=true).
  - Funciona en cualquier PC con BD Firebird y Qwen3 LAN.

PROPÓSITO:
  Verificar que el ChatService genera respuestas correctas para MetaGlass:
  - Sin Markdown (para TTS de las gafas)
  - Cortas (< METAGLASS_MAX_RESPONSE_LEN chars)
  - Con datos reales de la BD
  - Sin enviar datos a internet
"""

import asyncio
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ─── Helpers reutilizables ────────────────────────────────────────────────────

def _assert_metaglass_format(resp: str, max_len: int):
    """Verifica que la respuesta cumple el formato MetaGlass (sin Markdown, corta)."""
    assert resp, "Respuesta vacía"
    assert "**" not in resp, f"Markdown negrita en respuesta MetaGlass: '{resp[:100]}'"
    assert "```" not in resp, f"Bloque código en respuesta MetaGlass: '{resp[:100]}'"
    assert "##" not in resp, f"Encabezado Markdown en respuesta MetaGlass: '{resp[:100]}'"
    assert len(resp) <= max_len, (
        f"Respuesta demasiado larga para MetaGlass: {len(resp)} > {max_len} chars"
    )


def _assert_contains_number(resp: str, context: str = ""):
    """Verifica que la respuesta contiene al menos un número."""
    assert re.search(r'\d+', resp), (
        f"No hay número en la respuesta{' para: ' + context if context else ''}: '{resp}'"
    )


async def _ask(chat_svc, question: str, ctx: Dict) -> str:
    """Helper: hace una pregunta y devuelve la respuesta como string."""
    resp = await chat_svc.process_message(question, ctx)
    return str(resp) if resp else ""


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas de COUNT (1 tabla, 1 valor)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCountMetaGlass:
    """Preguntas de conteo — respuesta debe ser un número claro."""

    @pytest.mark.asyncio
    async def test_cuantos_articulos(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "cuántos artículos hay", metaglass_ctx)
        _assert_metaglass_format(resp, test_config.metaglass_max_len)
        _assert_contains_number(resp, "cuántos artículos hay")

    @pytest.mark.asyncio
    async def test_cuantos_clientes(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "cuántos clientes tenemos", metaglass_ctx)
        _assert_metaglass_format(resp, test_config.metaglass_max_len)
        _assert_contains_number(resp, "cuántos clientes tenemos")

    @pytest.mark.asyncio
    async def test_cuantos_proveedores(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "cuántos proveedores hay", metaglass_ctx)
        _assert_metaglass_format(resp, test_config.metaglass_max_len)
        _assert_contains_number(resp, "cuántos proveedores hay")


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas de listado (múltiples registros)
# ═══════════════════════════════════════════════════════════════════════════════

class TestListadoMetaGlass:
    """Preguntas de listado — respuesta debe ser concisa para TTS."""

    @pytest.mark.asyncio
    async def test_articulo_mas_caro(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "cuál es el artículo más caro", metaglass_ctx)
        _assert_metaglass_format(resp, test_config.metaglass_max_len)
        assert len(resp) > 5

    @pytest.mark.asyncio
    async def test_ultimas_facturas(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "dame las últimas facturas", metaglass_ctx)
        _assert_metaglass_format(resp, test_config.metaglass_max_len)
        assert len(resp) > 5

    @pytest.mark.asyncio
    async def test_almacenes(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        resp = await _ask(chat_svc, "qué almacenes hay", metaglass_ctx)
        _assert_metaglass_format(resp, test_config.metaglass_max_len)
        assert len(resp) > 5


# ═══════════════════════════════════════════════════════════════════════════════
# Tiempo de respuesta
# ═══════════════════════════════════════════════════════════════════════════════

class TestTiempoRespuestaMetaGlass:
    """Verifica que las respuestas llegan dentro del tiempo máximo configurado."""

    @pytest.mark.asyncio
    async def test_tiempo_respuesta_count(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        start = time.time()
        resp = await _ask(chat_svc, "cuántos artículos hay", metaglass_ctx)
        elapsed = time.time() - start
        assert elapsed <= test_config.metaglass_max_time, (
            f"Respuesta tardó {elapsed:.1f}s > máximo {test_config.metaglass_max_time}s"
        )
        assert resp

    @pytest.mark.asyncio
    async def test_tiempo_respuesta_listado(self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url):
        start = time.time()
        resp = await _ask(chat_svc, "dame las últimas facturas", metaglass_ctx)
        elapsed = time.time() - start
        assert elapsed <= test_config.metaglass_max_time, (
            f"Respuesta tardó {elapsed:.1f}s > máximo {test_config.metaglass_max_time}s"
        )
        assert resp
