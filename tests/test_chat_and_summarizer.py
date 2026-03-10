"""
Tests del ChatService, ResponseSummarizer y compatibilidad con MetaGlass.

EJECUTAR:
  cd bots/interjddcia
  .venv/Scripts/pytest tests/test_chat_and_summarizer.py -v -s

COBERTURA:
  1. ResponseSummarizer — lógica de resumen y paginación (sin BD, sin IA)
  2. interpret_results_for_voice — respuestas para MetaGlass (deterministas)
  3. clean_for_tts — limpieza de Markdown para TTS de MetaGlass
  4. is_pagination_request — detección de peticiones de paginación
  5. Flujo completo de chat con mocks (sin BD real, sin Qwen3)

PRINCIPIO: Tests 100% unitarios con mocks — no requieren BD ni IA.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 1: ResponseSummarizer — Resumen y paginación
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseSummarizer:
    """Tests del módulo de resúmenes paginados."""

    def _get_summarizer(self):
        from backend.modules.chat.response_summarizer import ResponseSummarizer
        return ResponseSummarizer()

    def _make_results(self, n: int, with_nombre=True, with_total=False) -> List[Dict]:
        rows = []
        for i in range(n):
            row = {}
            if with_nombre:
                row["NOMBRE"] = f"Artículo {i+1}"
            if with_total:
                row["TOTAL"] = float((i+1) * 100)
            row["CODIGO"] = f"ART{i+1:04d}"
            rows.append(row)
        return rows

    # ── Casos sin paginación (pocos resultados) ────────────────────────────────

    def test_sin_resultados_devuelve_mensaje_vacio(self):
        s = self._get_summarizer()
        resp, state = s.summarize("dame artículos", [], "SELECT * FROM ARTICULO")
        assert "No se encontraron" in resp
        assert state is None

    def test_un_resultado_sin_paginacion(self):
        s = self._get_summarizer()
        results = [{"NOMBRE": "Split Samsung 3000W", "PRECIO": 599.99}]
        resp, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")
        assert state is None
        assert "Split Samsung" in resp
        print(f"\n[TEST] 1 resultado: {resp}")

    def test_pocos_resultados_sin_paginacion(self):
        """≤15 resultados → mostrar todos, sin paginación."""
        s = self._get_summarizer()
        results = self._make_results(10)
        resp, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")
        assert state is None
        assert "Artículo 1" in resp
        assert "Artículo 10" in resp
        print(f"\n[TEST] 10 resultados sin paginación: {len(resp)} chars")

    def test_exactamente_threshold_sin_paginacion(self):
        """Exactamente 15 resultados → sin paginación."""
        from backend.modules.chat.response_summarizer import SUMMARY_THRESHOLD
        s = self._get_summarizer()
        results = self._make_results(SUMMARY_THRESHOLD)
        resp, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")
        assert state is None

    # ── Casos con paginación (muchos resultados) ───────────────────────────────

    def test_muchos_resultados_activa_paginacion(self):
        """Más de 15 resultados → resumen + estado de paginación."""
        s = self._get_summarizer()
        results = self._make_results(100)
        resp, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")

        assert state is not None
        assert state["total"] == 100
        assert state["shown"] == 0
        assert "100 registros" in resp
        assert "muéstrame" in resp.lower() or "dame" in resp.lower()
        print(f"\n[TEST] 100 resultados con paginación:\n{resp[:300]}")

    def test_paginacion_siguiente_pagina(self):
        """'siguiente' → devuelve los primeros 10."""
        s = self._get_summarizer()
        results = self._make_results(50)
        _, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")

        resp, new_state = s.handle_pagination_request("siguiente", state)
        assert new_state is not None
        assert new_state["shown"] == 10
        assert "Artículo 1" in resp
        assert "Artículo 10" in resp
        assert "Quedan 40" in resp
        print(f"\n[TEST] siguiente página:\n{resp[:300]}")

    def test_paginacion_pedir_numero_especifico(self):
        """'dame 5' → devuelve exactamente 5."""
        s = self._get_summarizer()
        results = self._make_results(50)
        _, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")

        resp, new_state = s.handle_pagination_request("dame 5", state)
        assert new_state is not None
        assert new_state["shown"] == 5
        assert "Artículo 5" in resp
        assert "Artículo 6" not in resp
        print(f"\n[TEST] dame 5:\n{resp[:200]}")

    def test_paginacion_pedir_todos(self):
        """'dame todos' → devuelve todos y termina paginación."""
        s = self._get_summarizer()
        results = self._make_results(30)
        _, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")

        resp, new_state = s.handle_pagination_request("dame todos", state)
        assert new_state is None  # Paginación terminada
        assert "Artículo 30" in resp
        print(f"\n[TEST] dame todos: {len(resp)} chars")

    def test_paginacion_segunda_pagina(self):
        """Dos peticiones de 'siguiente' → páginas 1-10 y 11-20."""
        s = self._get_summarizer()
        results = self._make_results(50)
        _, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")

        _, state2 = s.handle_pagination_request("siguiente", state)
        resp2, state3 = s.handle_pagination_request("siguiente", state2)

        assert state3 is not None
        assert state3["shown"] == 20
        assert "Artículo 11" in resp2
        assert "Artículo 20" in resp2
        print(f"\n[TEST] segunda página:\n{resp2[:200]}")

    def test_paginacion_ultima_pagina_termina(self):
        """Al llegar al final, la paginación termina."""
        s = self._get_summarizer()
        results = self._make_results(12)
        _, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")
        # 12 > 10 (page_size) pero ≤ 15 (threshold)... ajustar con 20 resultados
        results = self._make_results(20)
        _, state = s.summarize("dame artículos", results, "SELECT * FROM ARTICULO")

        _, state2 = s.handle_pagination_request("siguiente", state)   # 1-10
        resp3, state3 = s.handle_pagination_request("siguiente", state2)  # 11-20

        assert state3 is None  # Terminado
        assert "todos los 20 resultados" in resp3
        print(f"\n[TEST] última página: {resp3[-100:]}")

    def test_paginacion_con_campo_total(self):
        """Resultados con campo TOTAL → se muestra en el resumen."""
        s = self._get_summarizer()
        results = self._make_results(20, with_nombre=True, with_total=True)
        resp, state = s.summarize("facturas", results, "SELECT * FROM DOCCAB")

        assert state is not None
        # El resumen debe incluir algún valor numérico
        assert "100" in resp or "200" in resp or "TOTAL" in resp.upper()
        print(f"\n[TEST] con campo TOTAL:\n{resp[:300]}")

    # ── Detección de peticiones de paginación ─────────────────────────────────

    def test_is_pagination_request_todos(self):
        s = self._get_summarizer()
        assert s.is_pagination_request("dame todos")
        assert s.is_pagination_request("muéstrame todos")
        assert s.is_pagination_request("ver todos los resultados")

    def test_is_pagination_request_siguiente(self):
        s = self._get_summarizer()
        assert s.is_pagination_request("siguiente")
        assert s.is_pagination_request("siguiente página")
        assert s.is_pagination_request("más resultados")

    def test_is_pagination_request_numero(self):
        s = self._get_summarizer()
        assert s.is_pagination_request("dame 20")
        assert s.is_pagination_request("muéstrame 5 más")
        assert s.is_pagination_request("ver 10")

    def test_is_pagination_request_no_es_paginacion(self):
        s = self._get_summarizer()
        assert not s.is_pagination_request("dame los artículos más vendidos")
        assert not s.is_pagination_request("cuántas facturas hay")
        assert not s.is_pagination_request("hola")

    def test_detect_count_todos(self):
        from backend.modules.chat.response_summarizer import ResponseSummarizer
        s = ResponseSummarizer()
        assert s._detect_requested_count("dame todos") == -1
        assert s._detect_requested_count("ver todas") == -1
        assert s._detect_requested_count("lista completa") == -1

    def test_detect_count_numero(self):
        from backend.modules.chat.response_summarizer import ResponseSummarizer
        s = ResponseSummarizer()
        assert s._detect_requested_count("dame 20") == 20
        assert s._detect_requested_count("muéstrame 5") == 5
        assert s._detect_requested_count("diez") == 10

    def test_detect_count_siguiente(self):
        from backend.modules.chat.response_summarizer import ResponseSummarizer
        s = ResponseSummarizer()
        assert s._detect_requested_count("siguiente") is None
        assert s._detect_requested_count("más") is None


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 2: interpret_results_for_voice — MetaGlass TTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestInterpretResultsForVoice:
    """
    Tests de la función determinista para MetaGlass.
    CRÍTICO: estas respuestas van al TTS de las gafas Meta.
    Deben ser cortas, claras y sin Markdown.
    """

    def _interpret(self, message, results, sql="SELECT 1"):
        from backend.modules.chat.service import interpret_results_for_voice
        return interpret_results_for_voice(message, results, sql)

    # ── Sin resultados ─────────────────────────────────────────────────────────

    def test_sin_resultados(self):
        resp = self._interpret("cuántos artículos hay", [])
        assert "No encontré" in resp or "ningún" in resp
        print(f"\n[VOICE] sin resultados: '{resp}'")

    # ── COUNT / SUM (una fila, una columna) ────────────────────────────────────

    def test_count_articulos(self):
        resp = self._interpret("cuántos artículos hay", [{"COUNT": 437}])
        assert "437" in resp
        assert "artículo" in resp.lower()
        print(f"\n[VOICE] count artículos: '{resp}'")

    def test_count_clientes(self):
        resp = self._interpret("cuántos clientes tenemos", [{"COUNT": 1250}])
        assert "1.250" in resp or "1250" in resp
        assert "cliente" in resp.lower()
        print(f"\n[VOICE] count clientes: '{resp}'")

    def test_total_facturado(self):
        resp = self._interpret("total facturado este mes", [{"TOTAL": 45678.90}])
        assert "45" in resp
        assert "euro" in resp.lower() or "€" in resp
        print(f"\n[VOICE] total facturado: '{resp}'")

    # ── Un registro con múltiples columnas ────────────────────────────────────

    def test_un_registro_articulo(self):
        resp = self._interpret(
            "dame el artículo más caro",
            [{"NOMBRE": "Split Samsung 5000W", "PRECIO": 1299.99}]
        )
        assert "Split Samsung" in resp
        print(f"\n[VOICE] un registro: '{resp}'")

    def test_un_registro_cliente(self):
        resp = self._interpret(
            "dame el cliente García",
            [{"RAZONSOCIAL": "García e Hijos S.L.", "CODCLI": "CLI001"}]
        )
        assert "García" in resp
        print(f"\n[VOICE] un cliente: '{resp}'")

    # ── Múltiples registros ────────────────────────────────────────────────────

    def test_dos_resultados(self):
        resp = self._interpret(
            "dame los artículos más caros",
            [{"NOMBRE": "Split A"}, {"NOMBRE": "Split B"}]
        )
        assert "Split A" in resp and "Split B" in resp
        assert "dos" in resp.lower() or "2" in resp
        print(f"\n[VOICE] dos resultados: '{resp}'")

    def test_tres_resultados(self):
        resp = self._interpret(
            "dame los 3 artículos más vendidos",
            [{"NOMBRE": "Split A"}, {"NOMBRE": "Split B"}, {"NOMBRE": "Split C"}]
        )
        assert "Split A" in resp
        assert "Split C" in resp
        print(f"\n[VOICE] tres resultados: '{resp}'")

    def test_muchos_resultados_voz_resumido(self):
        """Con muchos resultados, la voz debe dar un resumen corto."""
        results = [{"NOMBRE": f"Artículo {i}"} for i in range(50)]
        resp = self._interpret("dame todos los artículos", results)
        # No debe listar los 50 — debe resumir
        assert "50" in resp or "Encontré" in resp
        assert len(resp) < 300  # Respuesta corta para TTS
        print(f"\n[VOICE] muchos resultados: '{resp}'")

    def test_respuesta_voz_sin_markdown(self):
        """Las respuestas de voz NO deben contener Markdown."""
        results = [{"NOMBRE": "Split Samsung"}, {"NOMBRE": "Split LG"}]
        resp = self._interpret("dame artículos", results)
        assert "**" not in resp
        assert "```" not in resp
        assert "#" not in resp
        print(f"\n[VOICE] sin markdown: '{resp}'")

    def test_respuesta_voz_en_espanol(self):
        """Las respuestas deben estar en español."""
        resp = self._interpret("cuántos artículos hay", [{"COUNT": 100}])
        # Debe contener palabras en español
        spanish_words = ["hay", "artículo", "resultado", "encontré", "base"]
        assert any(w in resp.lower() for w in spanish_words), \
            f"Respuesta no parece estar en español: '{resp}'"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 3: clean_for_tts — Limpieza de Markdown para MetaGlass
# ═══════════════════════════════════════════════════════════════════════════════

class TestCleanForTts:
    """Tests de la función de limpieza de Markdown para TTS."""

    def _clean(self, text):
        from backend.modules.chat.service import clean_for_tts
        return clean_for_tts(text)

    def test_elimina_negrita(self):
        assert "**texto**" not in self._clean("**texto** normal")
        assert "texto" in self._clean("**texto** normal")

    def test_elimina_cursiva(self):
        assert "*texto*" not in self._clean("*texto* normal")
        assert "texto" in self._clean("*texto* normal")

    def test_elimina_codigo_inline(self):
        result = self._clean("usa `SELECT * FROM ARTICULO`")
        assert "`" not in result
        assert "SELECT" in result

    def test_elimina_bloque_codigo(self):
        result = self._clean("```sql\nSELECT * FROM ARTICULO\n```")
        assert "```" not in result

    def test_elimina_encabezados(self):
        result = self._clean("## Resultados\nAquí están")
        assert "##" not in result
        assert "Resultados" in result

    def test_elimina_listas_guion(self):
        result = self._clean("- Elemento 1\n- Elemento 2")
        assert "- " not in result
        assert "Elemento 1" in result

    def test_elimina_links_markdown(self):
        result = self._clean("[texto](http://example.com)")
        assert "[" not in result
        assert "http" not in result
        assert "texto" in result

    def test_texto_limpio_no_cambia(self):
        text = "Hay 5 artículos disponibles."
        assert self._clean(text) == text

    def test_respuesta_tipica_chat_limpiada(self):
        """Simula una respuesta típica del chat con Markdown."""
        raw = (
            "**Resultados encontrados:**\n\n"
            "1. Split Samsung 3000W — `ART001` — **599,99€**\n"
            "2. Split LG 5000W — `ART002` — **899,99€**\n\n"
            "## Resumen\n"
            "- Total: 2 artículos\n"
            "- Precio medio: **749,99€**"
        )
        result = self._clean(raw)
        assert "**" not in result
        assert "`" not in result
        assert "##" not in result
        assert "Samsung" in result
        assert "LG" in result
        print(f"\n[TTS] respuesta limpiada:\n{result}")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 4: Flujo completo de chat con mocks
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatServiceFlow:
    """
    Tests del flujo completo del ChatService con mocks.
    Simula exactamente lo que ocurre cuando un usuario hace una pregunta.
    NO requiere BD real ni Qwen3.
    """

    def _make_context(self, is_voice=False, confirm=None):
        """Crea un contexto de chat simulado."""
        ctx = {
            "model_id": "qwen3-local",
            "db_params": {
                "host": "localhost", "port": 3050,
                "database": "test.fdb", "user": "SYSDBA", "password": "masterkey"
            },
            "conversation_history": [],
        }
        if is_voice:
            # MetaGlass: confirm_data_sending no se envía (None)
            pass
        else:
            ctx["confirm_data_sending"] = confirm if confirm is not None else True
        return ctx

    @pytest.mark.asyncio
    async def test_pregunta_simple_articulos_web(self):
        """
        Simula: usuario web pregunta 'dame los artículos más vendidos'
        → IA genera SQL → se ejecuta → se interpreta con IA
        """
        mock_sql_response = "```sql\nSELECT FIRST 10 a.NOMBRE, SUM(l.CANTIDAD) as TOTAL FROM DOCLIN l JOIN ARTICULO a ON a.CODART=l.CODART GROUP BY a.NOMBRE ORDER BY 2 DESC\n```"
        mock_results = [
            {"NOMBRE": "Split Samsung 3000W", "TOTAL": 45},
            {"NOMBRE": "Split LG 5000W", "TOTAL": 32},
        ]
        mock_interpretation = "Los artículos más vendidos son: Split Samsung 3000W (45 unidades) y Split LG 5000W (32 unidades)."

        with patch("backend.modules.chat.service.get_context_retriever") as mock_cr, \
             patch("backend.modules.chat.service.ModelFallbackOrchestrator") as mock_orch_cls:

            # Mock del ContextRetriever
            mock_retriever = MagicMock()
            mock_retriever.get_context.return_value = ("ESQUEMA BD...", {"source": "siuo", "tables_used": ["DOCLIN", "ARTICULO"], "tokens_estimated": 500})
            mock_cr.return_value = mock_retriever

            # Mock del orquestador (primera llamada = SQL, segunda = interpretación)
            mock_orch = MagicMock()
            mock_orch.execute_with_fallback = AsyncMock(side_effect=[
                (mock_sql_response, "qwen3-local"),
                (mock_interpretation, "qwen3-local"),
            ])
            mock_orch_cls.return_value = mock_orch

            from backend.modules.chat.service import ChatService
            svc = ChatService()
            svc.model_orchestrator = mock_orch

            with patch.object(svc, "_execute_sql", return_value=mock_results), \
                 patch("backend.modules.chat.service.model_manager") as mock_mm:
                mock_mm.get_model.return_value = {
                    "schema": "openai", "model_id": "qwen3", "api_key": "test"
                }
                result = await svc.process_message(
                    "dame los artículos más vendidos",
                    self._make_context(is_voice=False, confirm=True)
                )

        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 10
        print(f"\n[CHAT WEB] respuesta: '{result[:200]}'")

    @pytest.mark.asyncio
    async def test_pregunta_simple_articulos_metaglass(self):
        """
        Simula: MetaGlass pregunta 'dame los artículos más vendidos'
        → IA genera SQL → se ejecuta → interpretación DETERMINISTA (sin 2ª IA)
        → respuesta corta para TTS
        """
        mock_sql_response = "```sql\nSELECT FIRST 10 a.NOMBRE, SUM(l.CANTIDAD) as TOTAL FROM DOCLIN l JOIN ARTICULO a ON a.CODART=l.CODART GROUP BY a.NOMBRE ORDER BY 2 DESC\n```"
        mock_results = [
            {"NOMBRE": "Split Samsung 3000W", "TOTAL": 45},
            {"NOMBRE": "Split LG 5000W", "TOTAL": 32},
            {"NOMBRE": "Cassette Daikin 9000", "TOTAL": 28},
        ]

        with patch("backend.modules.chat.service.get_context_retriever") as mock_cr, \
             patch("backend.modules.chat.service.ModelFallbackOrchestrator") as mock_orch_cls:

            mock_retriever = MagicMock()
            mock_retriever.get_context.return_value = ("ESQUEMA BD...", {"source": "siuo", "tables_used": ["DOCLIN", "ARTICULO"], "tokens_estimated": 500})
            mock_cr.return_value = mock_retriever

            mock_orch = MagicMock()
            # Solo UNA llamada a IA (la segunda es determinista para voz)
            mock_orch.execute_with_fallback = AsyncMock(return_value=(mock_sql_response, "qwen3-local"))
            mock_orch_cls.return_value = mock_orch

            from backend.modules.chat.service import ChatService
            svc = ChatService()
            svc.model_orchestrator = mock_orch

            with patch.object(svc, "_execute_sql", return_value=mock_results), \
                 patch("backend.modules.chat.service.model_manager") as mock_mm:
                mock_mm.get_model.return_value = {
                    "schema": "openai", "model_id": "qwen3", "api_key": "test"
                }
                # MetaGlass: NO envía confirm_data_sending
                result = await svc.process_message(
                    "dame los artículos más vendidos",
                    self._make_context(is_voice=True)
                )

        assert result is not None
        assert isinstance(result, str)
        # Para voz: debe ser corta y sin Markdown
        assert "**" not in result
        assert "```" not in result
        assert len(result) < 500  # Respuesta corta para TTS
        # Debe mencionar los artículos
        assert "Samsung" in result or "LG" in result or "Daikin" in result or "3" in result
        print(f"\n[METAGLASS] respuesta TTS: '{result}'")

    @pytest.mark.asyncio
    async def test_pregunta_sin_sql_metaglass(self):
        """
        MetaGlass pregunta algo que no requiere SQL.
        → La IA responde directamente → se limpia el Markdown
        """
        mock_response = "**Hola!** Soy DEVIA, tu asistente de base de datos.\n- Puedo ayudarte con consultas SQL\n- Buscar artículos, clientes, facturas..."

        with patch("backend.modules.chat.service.get_context_retriever") as mock_cr, \
             patch("backend.modules.chat.service.ModelFallbackOrchestrator") as mock_orch_cls:

            mock_retriever = MagicMock()
            mock_retriever.get_context.return_value = ("ESQUEMA...", {"source": "siuo", "tables_used": [], "tokens_estimated": 100})
            mock_cr.return_value = mock_retriever

            mock_orch = MagicMock()
            mock_orch.execute_with_fallback = AsyncMock(return_value=(mock_response, "qwen3-local"))
            mock_orch_cls.return_value = mock_orch

            from backend.modules.chat.service import ChatService
            svc = ChatService()
            svc.model_orchestrator = mock_orch

            result = await svc.process_message(
                "hola, qué puedes hacer",
                self._make_context(is_voice=True)
            )

        assert result is not None
        # Para voz: sin Markdown
        assert "**" not in result
        assert "- " not in result
        assert "Hola" in result or "DEVIA" in result or "asistente" in result.lower()
        print(f"\n[METAGLASS] respuesta sin SQL: '{result}'")

    @pytest.mark.asyncio
    async def test_pregunta_count_metaglass(self):
        """
        MetaGlass: 'cuántos artículos hay'
        → SQL COUNT → respuesta determinista corta
        """
        mock_sql = "```sql\nSELECT COUNT(*) as TOTAL FROM ARTICULO\n```"
        mock_results = [{"TOTAL": 437}]

        with patch("backend.modules.chat.service.get_context_retriever") as mock_cr, \
             patch("backend.modules.chat.service.ModelFallbackOrchestrator") as mock_orch_cls:

            mock_retriever = MagicMock()
            mock_retriever.get_context.return_value = ("ESQUEMA...", {"source": "siuo", "tables_used": ["ARTICULO"], "tokens_estimated": 200})
            mock_cr.return_value = mock_retriever

            mock_orch = MagicMock()
            mock_orch.execute_with_fallback = AsyncMock(return_value=(mock_sql, "qwen3-local"))
            mock_orch_cls.return_value = mock_orch

            from backend.modules.chat.service import ChatService
            svc = ChatService()
            svc.model_orchestrator = mock_orch

            with patch.object(svc, "_execute_sql", return_value=mock_results), \
                 patch("backend.modules.chat.service.model_manager") as mock_mm:
                mock_mm.get_model.return_value = {"schema": "openai", "model_id": "qwen3", "api_key": "test"}
                result = await svc.process_message(
                    "cuántos artículos hay",
                    self._make_context(is_voice=True)
                )

        assert "437" in result
        assert "artículo" in result.lower()
        assert "**" not in result
        print(f"\n[METAGLASS] count: '{result}'")

    @pytest.mark.asyncio
    async def test_pregunta_facturas_metaglass(self):
        """
        MetaGlass: 'dame las últimas facturas'
        → SQL con TIPO=13 → respuesta determinista
        """
        mock_sql = "```sql\nSELECT FIRST 5 NUMDOC, FECHA, TOTAL FROM DOCCAB WHERE TIPO=13 ORDER BY FECHA DESC\n```"
        mock_results = [
            {"NUMDOC": "F2026-001", "FECHA": "2026-03-05", "TOTAL": 1250.00},
            {"NUMDOC": "F2026-002", "FECHA": "2026-03-04", "TOTAL": 890.50},
        ]

        with patch("backend.modules.chat.service.get_context_retriever") as mock_cr, \
             patch("backend.modules.chat.service.ModelFallbackOrchestrator") as mock_orch_cls:

            mock_retriever = MagicMock()
            mock_retriever.get_context.return_value = ("ESQUEMA...", {"source": "siuo", "tables_used": ["DOCCAB"], "tokens_estimated": 300})
            mock_cr.return_value = mock_retriever

            mock_orch = MagicMock()
            mock_orch.execute_with_fallback = AsyncMock(return_value=(mock_sql, "qwen3-local"))
            mock_orch_cls.return_value = mock_orch

            from backend.modules.chat.service import ChatService
            svc = ChatService()
            svc.model_orchestrator = mock_orch

            with patch.object(svc, "_execute_sql", return_value=mock_results), \
                 patch("backend.modules.chat.service.model_manager") as mock_mm:
                mock_mm.get_model.return_value = {"schema": "openai", "model_id": "qwen3", "api_key": "test"}
                result = await svc.process_message(
                    "dame las últimas facturas",
                    self._make_context(is_voice=True)
                )

        assert result is not None
        assert "**" not in result
        assert len(result) < 500
        print(f"\n[METAGLASS] facturas: '{result}'")

    @pytest.mark.asyncio
    async def test_sql_error_devuelve_mensaje_claro(self):
        """Si el SQL falla, el usuario recibe un mensaje claro (no un traceback)."""
        mock_sql = "```sql\nSELECT * FROM TABLA_INEXISTENTE\n```"

        with patch("backend.modules.chat.service.get_context_retriever") as mock_cr, \
             patch("backend.modules.chat.service.ModelFallbackOrchestrator") as mock_orch_cls:

            mock_retriever = MagicMock()
            mock_retriever.get_context.return_value = ("ESQUEMA...", {"source": "siuo", "tables_used": [], "tokens_estimated": 100})
            mock_cr.return_value = mock_retriever

            mock_orch = MagicMock()
            mock_orch.execute_with_fallback = AsyncMock(return_value=(mock_sql, "qwen3-local"))
            mock_orch_cls.return_value = mock_orch

            from backend.modules.chat.service import ChatService
            svc = ChatService()
            svc.model_orchestrator = mock_orch

            with patch.object(svc, "_execute_sql", side_effect=Exception("Table TABLA_INEXISTENTE not found")), \
                 patch("backend.modules.chat.service.model_manager") as mock_mm:
                mock_mm.get_model.return_value = {"schema": "openai", "model_id": "qwen3", "api_key": "test"}
                result = await svc.process_message(
                    "dame datos de tabla inexistente",
                    self._make_context(is_voice=True)
                )

        assert result is not None
        assert isinstance(result, str)
        # No debe ser un traceback de Python
        assert "Traceback" not in result
        assert "File " not in result
        print(f"\n[ERROR] mensaje de error: '{result[:200]}'")

    @pytest.mark.asyncio
    async def test_todos_modelos_fallan_devuelve_mensaje(self):
        """Si todos los modelos de IA fallan, el usuario recibe un mensaje claro."""
        with patch("backend.modules.chat.service.get_context_retriever") as mock_cr, \
             patch("backend.modules.chat.service.ModelFallbackOrchestrator") as mock_orch_cls:

            mock_retriever = MagicMock()
            mock_retriever.get_context.return_value = ("ESQUEMA...", {"source": "siuo", "tables_used": [], "tokens_estimated": 100})
            mock_cr.return_value = mock_retriever

            mock_orch = MagicMock()
            mock_orch.execute_with_fallback = AsyncMock(return_value=(None, None))
            mock_orch_cls.return_value = mock_orch

            from backend.modules.chat.service import ChatService
            svc = ChatService()
            svc.model_orchestrator = mock_orch

            result = await svc.process_message(
                "dame los artículos",
                self._make_context(is_voice=True)
            )

        assert result is not None
        assert "❌" in result or "No se pudo" in result or "disponible" in result.lower()
        print(f"\n[ERROR] todos modelos fallan: '{result}'")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 5: Preguntas reales — Verificación de SQL generado
# ═══════════════════════════════════════════════════════════════════════════════

class TestSQLGeneradoCorrectamente:
    """
    Verifica que el SQL generado por la IA es correcto para Firebird.
    Usa el FirebirdSQLNormalizer para detectar problemas.
    """

    def _normalize(self, sql):
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
        normalizer = FirebirdSQLNormalizer()
        normalized, changes = normalizer.normalize(sql)
        return normalized, changes

    def test_sql_con_limit_se_convierte_a_first(self):
        sql = "SELECT * FROM ARTICULO LIMIT 10"
        normalized, changes = self._normalize(sql)
        assert "LIMIT" not in normalized
        assert "FIRST 10" in normalized
        assert len(changes) > 0
        print(f"\n[SQL] LIMIT→FIRST: '{normalized}'")

    def test_sql_con_top_se_convierte_a_first(self):
        sql = "SELECT TOP 5 * FROM DOCCAB WHERE TIPO=13"
        normalized, changes = self._normalize(sql)
        assert "TOP" not in normalized
        assert "FIRST 5" in normalized
        print(f"\n[SQL] TOP→FIRST: '{normalized}'")

    def test_sql_like_se_convierte_a_upper(self):
        sql = "SELECT * FROM ARTICULO WHERE NOMBRE LIKE '%split%'"
        normalized, changes = self._normalize(sql)
        assert "UPPER" in normalized.upper()
        print(f"\n[SQL] LIKE→UPPER: '{normalized}'")

    def test_sql_ilike_se_convierte(self):
        sql = "SELECT * FROM CLIENTE WHERE RAZONSOCIAL ILIKE '%garcia%'"
        normalized, changes = self._normalize(sql)
        assert "ILIKE" not in normalized
        print(f"\n[SQL] ILIKE→UPPER: '{normalized}'")

    def test_sql_correcto_no_cambia(self):
        sql = "SELECT FIRST 10 CODART, NOMBRE, PRECIO FROM ARTICULO ORDER BY PRECIO DESC"
        normalized, changes = self._normalize(sql)
        assert "FIRST 10" in normalized
        assert len(changes) == 0 or all("FIRST" not in c for c in changes)
        print(f"\n[SQL] correcto sin cambios: '{normalized}'")

    def test_sql_facturas_tipo_correcto(self):
        """El SQL de facturas debe incluir TIPO=13."""
        sql = "SELECT FIRST 10 NUMDOC, FECHA, TOTAL FROM DOCCAB WHERE TIPO=13 ORDER BY FECHA DESC"
        normalized, changes = self._normalize(sql)
        assert "TIPO=13" in normalized or "TIPO = 13" in normalized
        assert "FIRST 10" in normalized
        print(f"\n[SQL] facturas: '{normalized}'")

    def test_sql_articulos_mas_vendidos(self):
        """SQL típico para artículos más vendidos."""
        sql = (
            "SELECT FIRST 10 a.NOMBRE, SUM(l.CANTIDAD) as TOTAL_VENDIDO "
            "FROM DOCLIN l "
            "JOIN ARTICULO a ON a.CODART = l.CODART "
            "JOIN DOCCAB d ON d.NUMDOC = l.NUMDOC "
            "WHERE d.TIPO IN (11, 13) "
            "GROUP BY a.NOMBRE "
            "ORDER BY TOTAL_VENDIDO DESC"
        )
        normalized, changes = self._normalize(sql)
        assert "FIRST 10" in normalized
        assert "DOCLIN" in normalized
        assert "ARTICULO" in normalized
        print(f"\n[SQL] artículos más vendidos: OK")

    def test_sql_ventas_por_agente(self):
        """SQL típico para ventas por agente."""
        sql = (
            "SELECT FIRST 20 ag.NOMBRE, SUM(d.TOTAL) as TOTAL_VENTAS "
            "FROM DOCCAB d "
            "JOIN AGENTE ag ON ag.CODAGENTE = d.CODAGENTE "
            "WHERE d.TIPO IN (11, 13) "
            "GROUP BY ag.NOMBRE "
            "ORDER BY TOTAL_VENTAS DESC"
        )
        normalized, changes = self._normalize(sql)
        assert "FIRST 20" in normalized
        assert "AGENTE" in normalized
        print(f"\n[SQL] ventas por agente: OK")
