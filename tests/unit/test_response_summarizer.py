"""
test_response_summarizer.py — Tests unitarios del ResponseSummarizer.

CAPA: unit (sin BD, sin IA, sin red)
MÓDULO: backend.modules.chat.response_summarizer
EJECUTAR: .venv/Scripts/pytest tests/unit/test_response_summarizer.py -v -s
"""

import sys
from pathlib import Path
from typing import Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.modules.chat.response_summarizer import (
    ResponseSummarizer, SUMMARY_THRESHOLD, PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX,
    METAGLASS_PAGINATION_THRESHOLD, METAGLASS_PAGE_SIZE,
)


@pytest.fixture
def s() -> ResponseSummarizer:
    return ResponseSummarizer()


def _rows(n: int, with_total=False) -> List[Dict]:
    rows = [{"NOMBRE": f"Artículo {i}", "CODIGO": f"ART{i:04d}"} for i in range(1, n+1)]
    if with_total:
        for i, r in enumerate(rows):
            r["TOTAL"] = float((i+1) * 100)
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Sin resultados
# ═══════════════════════════════════════════════════════════════════════════════

class TestSinResultados:
    def test_vacio_devuelve_mensaje(self, s):
        resp, state = s.summarize("dame artículos", [], "SELECT * FROM ARTICULO")
        assert "No se encontraron" in resp
        assert state is None

    def test_vacio_no_activa_paginacion(self, s):
        _, state = s.summarize("dame artículos", [], "SELECT * FROM ARTICULO")
        assert state is None


# ═══════════════════════════════════════════════════════════════════════════════
# Pocos resultados (≤ SUMMARY_THRESHOLD)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPocosResultados:
    def test_1_resultado_sin_paginacion(self, s):
        resp, state = s.summarize("dame artículos", _rows(1), "SELECT 1")
        assert state is None
        assert "Artículo 1" in resp

    def test_5_resultados_sin_paginacion(self, s):
        resp, state = s.summarize("dame artículos", _rows(5), "SELECT 5")
        assert state is None
        assert "Artículo 1" in resp
        assert "Artículo 5" in resp

    def test_exactamente_threshold_sin_paginacion(self, s):
        resp, state = s.summarize("dame artículos", _rows(SUMMARY_THRESHOLD), "SELECT N")
        assert state is None

    def test_threshold_menos_1_sin_paginacion(self, s):
        resp, state = s.summarize("dame artículos", _rows(SUMMARY_THRESHOLD - 1), "SELECT N")
        assert state is None


# ═══════════════════════════════════════════════════════════════════════════════
# Muchos resultados (> SUMMARY_THRESHOLD)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMuchosResultados:
    def test_threshold_mas_1_activa_paginacion(self, s):
        _, state = s.summarize("dame artículos", _rows(SUMMARY_THRESHOLD + 1), "SELECT N")
        assert state is not None

    def test_50_resultados_activa_paginacion(self, s):
        resp, state = s.summarize("dame artículos", _rows(50), "SELECT 50")
        assert state is not None
        assert state["total"] == 50
        assert state["shown"] == 0
        assert "50" in resp

    def test_100_resultados_activa_paginacion(self, s):
        resp, state = s.summarize("dame artículos", _rows(100), "SELECT 100")
        assert state is not None
        assert state["total"] == 100
        assert "100" in resp

    def test_resumen_contiene_primeros_10(self, s):
        resp, state = s.summarize("dame artículos", _rows(50), "SELECT 50")
        assert "Artículo 1" in resp
        assert "Artículo 10" in resp
        # No debe listar el 11 en el resumen
        assert "Artículo 11" not in resp

    def test_resumen_pregunta_si_quiere_mas(self, s):
        resp, _ = s.summarize("dame artículos", _rows(50), "SELECT 50")
        assert "muéstrame" in resp.lower() or "dame" in resp.lower() or "siguiente" in resp.lower()

    def test_con_campo_total_aparece_en_resumen(self, s):
        resp, state = s.summarize("facturas", _rows(20, with_total=True), "SELECT 20")
        assert state is not None
        # Debe haber algún valor numérico en el resumen
        import re
        assert re.search(r'\d+', resp)


# ═══════════════════════════════════════════════════════════════════════════════
# Paginación
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaginacion:
    def test_siguiente_devuelve_primera_pagina(self, s):
        _, state = s.summarize("dame artículos", _rows(50), "SELECT 50")
        resp, state2 = s.handle_pagination_request("siguiente", state)
        assert state2 is not None
        assert state2["shown"] == PAGE_SIZE_DEFAULT
        assert "Artículo 1" in resp
        assert f"Artículo {PAGE_SIZE_DEFAULT}" in resp

    def test_dame_5_devuelve_5(self, s):
        _, state = s.summarize("dame artículos", _rows(50), "SELECT 50")
        resp, state2 = s.handle_pagination_request("dame 5", state)
        assert state2 is not None
        assert state2["shown"] == 5
        assert "Artículo 5" in resp
        assert "Artículo 6" not in resp

    def test_dame_todos_termina_paginacion(self, s):
        _, state = s.summarize("dame artículos", _rows(30), "SELECT 30")
        resp, state2 = s.handle_pagination_request("dame todos", state)
        assert state2 is None
        assert "Artículo 30" in resp

    def test_segunda_pagina_correcta(self, s):
        _, state = s.summarize("dame artículos", _rows(50), "SELECT 50")
        _, state2 = s.handle_pagination_request("siguiente", state)
        resp3, state3 = s.handle_pagination_request("siguiente", state2)
        assert state3 is not None
        assert state3["shown"] == PAGE_SIZE_DEFAULT * 2
        assert "Artículo 11" in resp3
        assert "Artículo 20" in resp3

    def test_ultima_pagina_termina(self, s):
        _, state = s.summarize("dame artículos", _rows(20), "SELECT 20")
        _, state2 = s.handle_pagination_request("siguiente", state)   # 1-10
        resp3, state3 = s.handle_pagination_request("siguiente", state2)  # 11-20
        assert state3 is None
        assert "todos los 20 resultados" in resp3

    def test_pagina_vacia_termina(self, s):
        _, state = s.summarize("dame artículos", _rows(20), "SELECT 20")
        state_al_final = {**state, "shown": 20}
        resp, state2 = s.handle_pagination_request("siguiente", state_al_final)
        assert state2 is None
        assert "Ya has visto" in resp

    def test_dame_mas_de_max_se_limita(self, s):
        _, state = s.summarize("dame artículos", _rows(200), "SELECT 200")
        resp, state2 = s.handle_pagination_request(f"dame {PAGE_SIZE_MAX + 50}", state)
        assert state2 is not None
        assert state2["shown"] <= PAGE_SIZE_MAX

    def test_quedan_registros_se_informa(self, s):
        _, state = s.summarize("dame artículos", _rows(50), "SELECT 50")
        resp, _ = s.handle_pagination_request("siguiente", state)
        assert "Quedan" in resp or "quedan" in resp


# ═══════════════════════════════════════════════════════════════════════════════
# Detección de peticiones de paginación
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeteccionPaginacion:
    def test_todos_es_paginacion(self, s):
        assert s.is_pagination_request("dame todos")
        assert s.is_pagination_request("ver todos")
        assert s.is_pagination_request("muéstrame todos")

    def test_siguiente_es_paginacion(self, s):
        assert s.is_pagination_request("siguiente")
        assert s.is_pagination_request("siguiente página")
        assert s.is_pagination_request("más resultados")

    def test_numero_es_paginacion(self, s):
        assert s.is_pagination_request("dame 20")
        assert s.is_pagination_request("muéstrame 5 más")
        assert s.is_pagination_request("ver 10")

    def test_pregunta_normal_no_es_paginacion(self, s):
        assert not s.is_pagination_request("dame los artículos más vendidos")
        assert not s.is_pagination_request("cuántas facturas hay")
        assert not s.is_pagination_request("hola")
        assert not s.is_pagination_request("qué almacenes hay")

    def test_detect_count_todos(self, s):
        assert s._detect_requested_count("dame todos") == -1
        assert s._detect_requested_count("ver todas") == -1
        assert s._detect_requested_count("lista completa") == -1

    def test_detect_count_numero_digitos(self, s):
        assert s._detect_requested_count("dame 20") == 20
        assert s._detect_requested_count("muéstrame 5") == 5
        assert s._detect_requested_count("ver 100") == 100

    def test_detect_count_numero_palabras(self, s):
        assert s._detect_requested_count("diez") == 10
        assert s._detect_requested_count("veinte") == 20
        assert s._detect_requested_count("cinco") == 5

    def test_detect_count_siguiente_es_none(self, s):
        assert s._detect_requested_count("siguiente") is None
        assert s._detect_requested_count("más") is None
        assert s._detect_requested_count("continúa") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Campos de display
# ═══════════════════════════════════════════════════════════════════════════════

class TestCamposDisplay:
    def test_encuentra_campo_nombre(self, s):
        rows = [{"NOMBRE": "Split A", "CODIGO": "ART001"}]
        assert s._find_display_key(rows) == "NOMBRE"

    def test_encuentra_campo_descripcion(self, s):
        rows = [{"DESCRIPCION": "Split Samsung", "CODART": "ART001"}]
        assert s._find_display_key(rows) == "DESCRIPCION"

    def test_encuentra_campo_razonsocial(self, s):
        rows = [{"RAZONSOCIAL": "García S.L.", "CODCLI": "CLI001"}]
        assert s._find_display_key(rows) == "RAZONSOCIAL"

    def test_encuentra_campo_total(self, s):
        rows = [{"NOMBRE": "Split", "TOTAL": 1500.0}]
        assert s._find_numeric_key(rows) == "TOTAL"

    def test_encuentra_campo_precio(self, s):
        rows = [{"NOMBRE": "Split", "PRECIO": 599.99}]
        assert s._find_numeric_key(rows) == "PRECIO"

    def test_sin_resultados_devuelve_none(self, s):
        assert s._find_display_key([]) is None
        assert s._find_numeric_key([]) is None


# ═══════════════════════════════════════════════════════════════════════════════
# MetaGlass: paginación por voz con umbral configurable
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetaGlassPaginacion:
    """
    Tests para summarize_for_metaglass — paginación por voz.

    DIFERENCIAS con web:
      - Umbral más bajo (METAGLASS_PAGINATION_THRESHOLD, default 5)
      - Respuesta sin Markdown
      - Pregunta si quiere listar poco a poco
    """

    def test_pocos_resultados_sin_paginacion(self, s):
        """Con ≤ threshold resultados → mostrar todos directamente."""
        resp, state = s.summarize_for_metaglass(
            "dame artículos", _rows(METAGLASS_PAGINATION_THRESHOLD), "SELECT N"
        )
        assert state is None
        assert "Artículo 1" in resp
        assert "**" not in resp  # Sin Markdown

    def test_muchos_resultados_activa_paginacion(self, s):
        """Con > threshold resultados → preguntar si quiere listar poco a poco."""
        resp, state = s.summarize_for_metaglass(
            "dame artículos", _rows(METAGLASS_PAGINATION_THRESHOLD + 1), "SELECT N"
        )
        assert state is not None
        assert state["client"] == "metaglass"
        assert "**" not in resp  # Sin Markdown

    def test_pregunta_si_quiere_listar(self, s):
        """La respuesta debe preguntar si quiere listar poco a poco."""
        resp, state = s.summarize_for_metaglass(
            "dame artículos", _rows(20), "SELECT 20"
        )
        assert state is not None
        # Debe preguntar de alguna forma
        assert "?" in resp
        assert "20" in resp

    def test_preview_primeros_items(self, s):
        """La respuesta debe incluir preview de los primeros items."""
        resp, state = s.summarize_for_metaglass(
            "dame artículos", _rows(20), "SELECT 20"
        )
        assert state is not None
        # Debe mencionar alguno de los primeros artículos
        assert "Artículo 1" in resp or "Artículo 2" in resp

    def test_page_size_configurable(self, s):
        """El page_size debe ser configurable."""
        resp, state = s.summarize_for_metaglass(
            "dame artículos", _rows(20), "SELECT 20",
            threshold=3, page_size=2
        )
        assert state is not None
        assert state["page_size"] == 2
        assert "2" in resp  # Menciona el page_size en la pregunta

    def test_threshold_configurable(self, s):
        """El threshold debe ser configurable."""
        # Con threshold=10, 8 resultados no activan paginación
        resp, state = s.summarize_for_metaglass(
            "dame artículos", _rows(8), "SELECT 8", threshold=10
        )
        assert state is None

        # Con threshold=5, 8 resultados SÍ activan paginación
        resp2, state2 = s.summarize_for_metaglass(
            "dame artículos", _rows(8), "SELECT 8", threshold=5
        )
        assert state2 is not None

    def test_sin_resultados(self, s):
        """Sin resultados → mensaje sin paginación."""
        resp, state = s.summarize_for_metaglass("dame artículos", [], "SELECT N")
        assert state is None
        assert "No encontré" in resp

    def test_sin_markdown_en_respuesta(self, s):
        """La respuesta MetaGlass nunca debe tener Markdown."""
        resp, _ = s.summarize_for_metaglass(
            "dame artículos", _rows(20), "SELECT 20"
        )
        assert "**" not in resp
        assert "```" not in resp
        assert "##" not in resp
        assert "*" not in resp or resp.count("*") == 0


class TestMetaGlassIntent:
    """Tests para la detección de intención de paginación MetaGlass."""

    def test_si_activa_paginacion(self, s):
        intent = s._detect_intent_deterministic("sí")
        assert intent == "si"

    def test_vale_activa_paginacion(self, s):
        intent = s._detect_intent_deterministic("vale")
        assert intent == "si"

    def test_no_cancela_paginacion(self, s):
        intent = s._detect_intent_deterministic("no")
        assert intent == "no"

    def test_no_gracias_cancela(self, s):
        intent = s._detect_intent_deterministic("no gracias")
        assert intent == "no"

    def test_todos_pide_todos(self, s):
        intent = s._detect_intent_deterministic("dame todos")
        assert intent == "todos"

    def test_no_dame_todos_pide_todos(self, s):
        """'no, dame todos' debe interpretarse como 'todos', no como 'no'."""
        intent = s._detect_intent_deterministic("no, dame todos")
        assert intent == "todos"

    def test_siguiente_activa_paginacion(self, s):
        intent = s._detect_intent_deterministic("siguiente")
        assert intent == "si"

    def test_default_es_si(self, s):
        """Respuesta ambigua → asumir 'sí'."""
        intent = s._detect_intent_deterministic("mmm")
        assert intent == "si"


class TestMetaGlassPaginacionHandle:
    """Tests para handle_metaglass_pagination."""

    def test_si_da_primera_pagina(self, s):
        """Responder 'sí' → dar la primera página."""
        _, state = s.summarize_for_metaglass(
            "dame artículos", _rows(20), "SELECT 20", threshold=3, page_size=3
        )
        resp, state2 = s.handle_metaglass_pagination("sí", state, use_ai=False)
        assert resp
        assert "Artículo 1" in resp

    def test_no_cancela(self, s):
        """Responder 'no' → cancelar paginación."""
        _, state = s.summarize_for_metaglass(
            "dame artículos", _rows(20), "SELECT 20", threshold=3, page_size=3
        )
        resp, state2 = s.handle_metaglass_pagination("no", state, use_ai=False)
        assert state2 is None
        assert "De acuerdo" in resp or "no" in resp.lower()

    def test_todos_da_todos(self, s):
        """Responder 'dame todos' → dar todos los resultados (formato compacto TTS)."""
        _, state = s.summarize_for_metaglass(
            "dame artículos", _rows(10), "SELECT 10", threshold=3, page_size=3
        )
        resp, state2 = s.handle_metaglass_pagination("dame todos", state, use_ai=False)
        assert state2 is None
        # Con 10 items, _format_for_voice muestra los 3 primeros + "y 7 más"
        # Verificamos que hay contenido y menciona el total
        assert resp
        assert "Artículo 1" in resp
        assert "10" in resp  # Menciona el total de alguna forma
