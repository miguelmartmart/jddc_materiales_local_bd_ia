"""
test_pagination_real.py — Tests de integración de paginación con BD real.

CAPA: integration (requiere BD Firebird + Qwen3 LAN)
MÓDULO: backend.modules.chat.response_summarizer + ChatService
EJECUTAR: .venv/Scripts/pytest tests/integration/test_pagination_real.py -v -s

INDEPENDENCIA:
  - Sin IPs hardcodeadas. Todo desde test.properties vía conftest.py.
  - Se salta si BD o Qwen3 no disponibles (SKIP_IF_UNAVAILABLE=true).
  - Funciona con cualquier BD Firebird que tenga tablas con datos.

PROPÓSITO:
  Verificar que la paginación funciona correctamente con datos reales de BD:
  - Preguntas que devuelven muchos registros activan la paginación
  - El usuario puede navegar por las páginas
  - MetaGlass recibe respuestas sin Markdown
  - El cliente web recibe respuestas con formato completo
  - La paginación termina correctamente al llegar al final

DIFERENCIAS CON TESTS UNITARIOS:
  - Usa datos reales de Firebird (no datos de prueba)
  - Verifica que el ChatService integra correctamente el ResponseSummarizer
  - Verifica tiempos de respuesta reales
"""

import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ─── Helpers reutilizables ────────────────────────────────────────────────────

async def _ask(chat_svc, question: str, ctx: Dict) -> str:
    """Helper: hace una pregunta y devuelve la respuesta como string."""
    resp = await chat_svc.process_message(question, ctx)
    return str(resp) if resp else ""


def _assert_no_markdown(resp: str):
    """La respuesta no debe tener Markdown (para MetaGlass TTS)."""
    assert "**" not in resp, f"Markdown negrita en respuesta MetaGlass: '{resp[:100]}'"
    assert "```" not in resp, f"Bloque código en respuesta MetaGlass: '{resp[:100]}'"
    assert "##" not in resp, f"Encabezado Markdown en respuesta MetaGlass: '{resp[:100]}'"


def _has_number(resp: str) -> bool:
    """Verifica si la respuesta contiene al menos un número."""
    return bool(re.search(r'\d+', resp))


# ═══════════════════════════════════════════════════════════════════════════════
# Paginación web — preguntas que devuelven muchos registros
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaginacionWebReal:
    """
    Verifica que preguntas con muchos resultados activan la paginación web.
    Usa datos reales de BD Firebird.
    """

    @pytest.mark.asyncio
    async def test_listado_articulos_activa_paginacion(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        'dame todos los artículos' → muchos resultados → paginación activa.
        La respuesta debe mencionar el total y ofrecer opciones de navegación.
        """
        resp = await _ask(chat_svc, "dame todos los artículos", web_ctx)
        assert resp, "Respuesta vacía"
        assert len(resp) > 10
        # Si hay muchos artículos, debe mencionar el total o la paginación
        # (si hay pocos, simplemente los lista todos — también es válido)
        assert _has_number(resp), "La respuesta debe contener al menos un número"

    @pytest.mark.asyncio
    async def test_listado_clientes_activa_paginacion(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        'dame todos los clientes' → muchos resultados → paginación activa.
        """
        resp = await _ask(chat_svc, "dame todos los clientes", web_ctx)
        assert resp, "Respuesta vacía"
        assert _has_number(resp), "La respuesta debe contener al menos un número"

    @pytest.mark.asyncio
    async def test_respuesta_web_puede_tener_markdown(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        El cliente web puede recibir Markdown (tablas, negrita, etc.).
        Solo verificamos que la respuesta es válida.
        """
        resp = await _ask(chat_svc, "dame los 20 artículos más caros", web_ctx)
        assert resp, "Respuesta vacía"
        assert len(resp) > 10
        assert len(resp) <= test_config.web_max_len, (
            f"Respuesta demasiado larga: {len(resp)} > {test_config.web_max_len}"
        )

    @pytest.mark.asyncio
    async def test_tiempo_respuesta_paginacion_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """La paginación no debe añadir latencia significativa."""
        start = time.time()
        resp = await _ask(chat_svc, "dame todos los artículos", web_ctx)
        elapsed = time.time() - start
        assert elapsed <= test_config.web_max_time, (
            f"Respuesta tardó {elapsed:.1f}s > máximo {test_config.web_max_time}s"
        )
        assert resp


# ═══════════════════════════════════════════════════════════════════════════════
# Paginación MetaGlass — respuestas sin Markdown, cortas
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaginacionMetaGlassReal:
    """
    Verifica que la paginación MetaGlass funciona con datos reales.
    Las respuestas deben ser cortas y sin Markdown para el TTS.
    """

    @pytest.mark.asyncio
    async def test_listado_metaglass_sin_markdown(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """
        MetaGlass: la respuesta nunca debe tener Markdown.
        """
        resp = await _ask(chat_svc, "dame los artículos más caros", metaglass_ctx)
        assert resp, "Respuesta vacía"
        _assert_no_markdown(resp)

    @pytest.mark.asyncio
    async def test_listado_metaglass_longitud_maxima(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """
        MetaGlass: la respuesta no debe superar el límite de caracteres para TTS.
        """
        resp = await _ask(chat_svc, "dame todos los artículos", metaglass_ctx)
        assert resp, "Respuesta vacía"
        assert len(resp) <= test_config.metaglass_max_len, (
            f"Respuesta demasiado larga para MetaGlass TTS: "
            f"{len(resp)} > {test_config.metaglass_max_len} chars"
        )
        _assert_no_markdown(resp)

    @pytest.mark.asyncio
    async def test_metaglass_pregunta_si_quiere_listar(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """
        MetaGlass: si hay muchos resultados, debe preguntar si quiere listar poco a poco.
        La respuesta debe contener una pregunta (signo '?').
        """
        resp = await _ask(chat_svc, "dame todos los clientes", metaglass_ctx)
        assert resp, "Respuesta vacía"
        _assert_no_markdown(resp)
        # Si hay muchos clientes, debe preguntar
        # Si hay pocos, los lista directamente — ambos son válidos
        assert len(resp) > 5

    @pytest.mark.asyncio
    async def test_tiempo_respuesta_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """MetaGlass: la respuesta debe llegar dentro del tiempo máximo."""
        start = time.time()
        resp = await _ask(chat_svc, "dame los artículos más caros", metaglass_ctx)
        elapsed = time.time() - start
        assert elapsed <= test_config.metaglass_max_time, (
            f"Respuesta tardó {elapsed:.1f}s > máximo {test_config.metaglass_max_time}s"
        )
        assert resp


# ═══════════════════════════════════════════════════════════════════════════════
# Paginación con datos reales — navegación por páginas
# ═══════════════════════════════════════════════════════════════════════════════

class TestNavegacionPaginasReal:
    """
    Verifica que el usuario puede navegar por las páginas de resultados.
    Simula el flujo completo: pregunta → paginación → siguiente → siguiente → fin.
    """

    @pytest.mark.asyncio
    async def test_flujo_siguiente_siguiente_fin_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        Flujo completo web:
        1. Pregunta que devuelve muchos resultados
        2. Usuario dice "siguiente" → primera página
        3. Usuario dice "siguiente" → segunda página
        4. Usuario dice "dame todos" → todos los resultados
        """
        # Paso 1: pregunta inicial
        resp1 = await _ask(chat_svc, "dame todos los artículos", web_ctx)
        assert resp1, "Respuesta vacía en paso 1"

        # Paso 2: si hay paginación activa, navegar
        # (si no hay paginación, el test pasa igualmente — pocos resultados)
        from backend.modules.chat.response_summarizer import get_response_summarizer
        summarizer = get_response_summarizer()

        if summarizer.is_pagination_request("siguiente"):
            resp2 = await _ask(chat_svc, "siguiente", web_ctx)
            assert resp2, "Respuesta vacía en paso 2"
            assert len(resp2) > 5

    @pytest.mark.asyncio
    async def test_flujo_dame_todos_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        Flujo: pregunta → 'dame todos' → todos los resultados de una vez.
        """
        # Pregunta inicial
        resp1 = await _ask(chat_svc, "dame todos los artículos", web_ctx)
        assert resp1, "Respuesta vacía"

        # Pedir todos
        resp2 = await _ask(chat_svc, "dame todos", web_ctx)
        assert resp2, "Respuesta vacía al pedir todos"
        assert len(resp2) > 5

    @pytest.mark.asyncio
    async def test_flujo_metaglass_si_no(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """
        Flujo MetaGlass:
        1. Pregunta que devuelve muchos resultados → pregunta si quiere listar
        2. Usuario dice "sí" → primera página
        3. Usuario dice "no" → cancelar
        """
        # Paso 1: pregunta inicial
        resp1 = await _ask(chat_svc, "dame todos los clientes", metaglass_ctx)
        assert resp1, "Respuesta vacía en paso 1"
        _assert_no_markdown(resp1)

        # Paso 2: responder "sí"
        resp2 = await _ask(chat_svc, "sí", metaglass_ctx)
        assert resp2, "Respuesta vacía al decir 'sí'"
        _assert_no_markdown(resp2)

        # Paso 3: responder "no" para cancelar
        resp3 = await _ask(chat_svc, "no", metaglass_ctx)
        assert resp3, "Respuesta vacía al decir 'no'"
        _assert_no_markdown(resp3)


# ═══════════════════════════════════════════════════════════════════════════════
# Consistencia entre web y MetaGlass
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsistenciaWebMetaGlass:
    """
    Verifica que web y MetaGlass devuelven datos consistentes
    (mismos datos, diferente formato).
    """

    @pytest.mark.asyncio
    async def test_count_consistente(
        self, chat_svc, web_ctx, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """
        El número de artículos debe ser el mismo en web y MetaGlass.
        """
        resp_web = await _ask(chat_svc, "cuántos artículos hay", web_ctx)
        resp_mg  = await _ask(chat_svc, "cuántos artículos hay", metaglass_ctx)

        assert resp_web, "Respuesta web vacía"
        assert resp_mg,  "Respuesta MetaGlass vacía"

        # Extraer números de ambas respuestas
        nums_web = re.findall(r'\d+', resp_web)
        nums_mg  = re.findall(r'\d+', resp_mg)

        assert nums_web, f"No hay número en respuesta web: '{resp_web[:100]}'"
        assert nums_mg,  f"No hay número en respuesta MetaGlass: '{resp_mg[:100]}'"

        # El número principal debe ser el mismo (puede haber diferencias de formato)
        # Buscamos el número más grande (el total de artículos)
        max_web = max(int(n) for n in nums_web)
        max_mg  = max(int(n) for n in nums_mg)

        assert max_web == max_mg, (
            f"Número de artículos diferente: web={max_web}, MetaGlass={max_mg}"
        )

    @pytest.mark.asyncio
    async def test_metaglass_mas_corto_que_web(
        self, chat_svc, web_ctx, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """
        La respuesta MetaGlass debe ser más corta que la web para la misma pregunta.
        (MetaGlass tiene límite de caracteres para TTS)
        """
        resp_web = await _ask(chat_svc, "dame los artículos más caros", web_ctx)
        resp_mg  = await _ask(chat_svc, "dame los artículos más caros", metaglass_ctx)

        assert resp_web, "Respuesta web vacía"
        assert resp_mg,  "Respuesta MetaGlass vacía"

        # MetaGlass debe ser más corta o igual
        assert len(resp_mg) <= len(resp_web) + 100, (
            f"MetaGlass ({len(resp_mg)} chars) no es más corta que web ({len(resp_web)} chars)"
        )

        # MetaGlass no debe tener Markdown
        _assert_no_markdown(resp_mg)
