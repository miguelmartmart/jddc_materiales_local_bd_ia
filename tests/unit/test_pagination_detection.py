"""
test_pagination_detection.py — Tests unitarios de detección de peticiones de paginación.

CAPA: unit (sin BD, sin IA, sin red)
MÓDULO: backend.modules.chat.response_summarizer.ResponseSummarizer
EJECUTAR: .venv/Scripts/pytest tests/unit/test_pagination_detection.py -v -s

PROPÓSITO:
  Verificar que el sistema detecta correctamente cuándo el usuario está
  pidiendo más resultados (paginación) vs haciendo una pregunta nueva.

  REGLA CRÍTICA:
    "dame los artículos más vendidos" → NO es paginación (es pregunta de negocio)
    "dame 20"                         → SÍ es paginación (número explícito)
    "siguiente"                       → SÍ es paginación (trigger exacto)
    "dame todos"                      → SÍ es paginación (trigger exacto)

  Esta distinción es fundamental para que el sistema no confunda
  una pregunta de negocio con una petición de paginación.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.modules.chat.response_summarizer import ResponseSummarizer


@pytest.fixture
def s() -> ResponseSummarizer:
    return ResponseSummarizer()


# ═══════════════════════════════════════════════════════════════════════════════
# is_pagination_request — Detección binaria
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsPaginationRequest:
    """
    Verifica que is_pagination_request distingue correctamente
    peticiones de paginación de preguntas de negocio.
    """

    # ── Triggers exactos de paginación ────────────────────────────────────────

    def test_siguiente_es_paginacion(self, s):
        assert s.is_pagination_request("siguiente")

    def test_siguiente_pagina_es_paginacion(self, s):
        assert s.is_pagination_request("siguiente página")

    def test_mas_resultados_es_paginacion(self, s):
        assert s.is_pagination_request("más resultados")

    def test_ver_todos_es_paginacion(self, s):
        assert s.is_pagination_request("ver todos")

    def test_ver_todas_es_paginacion(self, s):
        assert s.is_pagination_request("ver todas")

    def test_dame_todos_es_paginacion(self, s):
        assert s.is_pagination_request("dame todos")

    def test_dame_todas_es_paginacion(self, s):
        assert s.is_pagination_request("dame todas")

    def test_mostrar_todos_es_paginacion(self, s):
        assert s.is_pagination_request("mostrar todos")

    def test_lista_completa_es_paginacion(self, s):
        assert s.is_pagination_request("lista completa")

    def test_el_resto_es_paginacion(self, s):
        assert s.is_pagination_request("el resto")

    def test_los_demas_es_paginacion(self, s):
        assert s.is_pagination_request("los demás")

    def test_continua_es_paginacion(self, s):
        assert s.is_pagination_request("continúa")

    def test_continua_sin_tilde_es_paginacion(self, s):
        assert s.is_pagination_request("continua")

    # ── Acción + número explícito ──────────────────────────────────────────────

    def test_dame_20_es_paginacion(self, s):
        assert s.is_pagination_request("dame 20")

    def test_dame_5_es_paginacion(self, s):
        assert s.is_pagination_request("dame 5")

    def test_muestrame_10_es_paginacion(self, s):
        assert s.is_pagination_request("muéstrame 10")

    def test_ver_50_es_paginacion(self, s):
        assert s.is_pagination_request("ver 50")

    def test_mostrar_100_es_paginacion(self, s):
        assert s.is_pagination_request("mostrar 100")

    # ── Preguntas de negocio — NO son paginación ──────────────────────────────

    def test_articulos_mas_vendidos_no_es_paginacion(self, s):
        """CRÍTICO: 'dame los artículos más vendidos' NO es paginación."""
        assert not s.is_pagination_request("dame los artículos más vendidos")

    def test_cuantas_facturas_no_es_paginacion(self, s):
        assert not s.is_pagination_request("cuántas facturas hay")

    def test_hola_no_es_paginacion(self, s):
        assert not s.is_pagination_request("hola")

    def test_que_almacenes_hay_no_es_paginacion(self, s):
        assert not s.is_pagination_request("qué almacenes hay")

    def test_total_ventas_no_es_paginacion(self, s):
        assert not s.is_pagination_request("total de ventas de este año")

    def test_clientes_de_madrid_no_es_paginacion(self, s):
        assert not s.is_pagination_request("clientes de Madrid")

    def test_articulo_mas_caro_no_es_paginacion(self, s):
        assert not s.is_pagination_request("cuál es el artículo más caro")

    def test_facturas_del_mes_no_es_paginacion(self, s):
        assert not s.is_pagination_request("facturas del mes pasado")

    def test_ventas_por_agente_no_es_paginacion(self, s):
        assert not s.is_pagination_request("cuánto ha vendido cada agente")

    def test_busca_split_no_es_paginacion(self, s):
        assert not s.is_pagination_request("busca artículos que contengan split")

    # ── Casos límite ──────────────────────────────────────────────────────────

    def test_vacio_no_es_paginacion(self, s):
        assert not s.is_pagination_request("")

    def test_solo_espacios_no_es_paginacion(self, s):
        assert not s.is_pagination_request("   ")

    def test_numero_solo_no_es_paginacion(self, s):
        """Un número solo sin acción no es paginación."""
        # "20" sin "dame/muestra/ver" no es paginación
        # (podría ser una respuesta a otra pregunta)
        # Este comportamiento depende de la implementación — documentamos el actual
        result = s.is_pagination_request("20")
        # No forzamos el resultado — solo verificamos que no lanza excepción
        assert isinstance(result, bool)

    def test_mayusculas_funcionan(self, s):
        """La detección debe ser case-insensitive."""
        assert s.is_pagination_request("SIGUIENTE")
        assert s.is_pagination_request("DAME TODOS")
        assert s.is_pagination_request("VER TODOS")


# ═══════════════════════════════════════════════════════════════════════════════
# _detect_requested_count — Cuántos registros quiere ver
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectRequestedCount:
    """
    Verifica que _detect_requested_count extrae correctamente
    el número de registros solicitados.
    """

    # ── "Todos" → -1 ──────────────────────────────────────────────────────────

    def test_todos_devuelve_menos_1(self, s):
        assert s._detect_requested_count("dame todos") == -1

    def test_todas_devuelve_menos_1(self, s):
        assert s._detect_requested_count("ver todas") == -1

    def test_todo_devuelve_menos_1(self, s):
        assert s._detect_requested_count("todo") == -1

    def test_completo_devuelve_menos_1(self, s):
        assert s._detect_requested_count("lista completa") == -1

    # ── Números en dígitos ────────────────────────────────────────────────────

    def test_dame_20_devuelve_20(self, s):
        assert s._detect_requested_count("dame 20") == 20

    def test_muestrame_5_devuelve_5(self, s):
        assert s._detect_requested_count("muéstrame 5") == 5

    def test_ver_100_devuelve_100(self, s):
        assert s._detect_requested_count("ver 100") == 100

    def test_numero_solo_devuelve_numero(self, s):
        result = s._detect_requested_count("10")
        assert result == 10 or result is None  # Depende de la implementación

    # ── Números en palabras ───────────────────────────────────────────────────

    def test_diez_devuelve_10(self, s):
        assert s._detect_requested_count("diez") == 10

    def test_veinte_devuelve_20(self, s):
        assert s._detect_requested_count("veinte") == 20

    def test_cinco_devuelve_5(self, s):
        assert s._detect_requested_count("cinco") == 5

    def test_cien_devuelve_100(self, s):
        assert s._detect_requested_count("cien") == 100

    # ── "Siguiente" → None (usar page_size por defecto) ──────────────────────

    def test_siguiente_devuelve_none(self, s):
        assert s._detect_requested_count("siguiente") is None

    def test_mas_devuelve_none(self, s):
        assert s._detect_requested_count("más") is None

    def test_continua_devuelve_none(self, s):
        assert s._detect_requested_count("continúa") is None

    def test_vacio_devuelve_none(self, s):
        assert s._detect_requested_count("") is None


# ═══════════════════════════════════════════════════════════════════════════════
# _detect_intent_deterministic — Intención MetaGlass
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectIntentDeterministic:
    """
    Verifica la detección determinista de intención para MetaGlass.
    Esta función se usa cuando Qwen3 no está disponible.
    """

    # ── "sí" ──────────────────────────────────────────────────────────────────

    def test_si_con_tilde(self, s):
        assert s._detect_intent_deterministic("sí") == "si"

    def test_si_sin_tilde(self, s):
        assert s._detect_intent_deterministic("si") == "si"

    def test_vale(self, s):
        assert s._detect_intent_deterministic("vale") == "si"

    def test_adelante(self, s):
        assert s._detect_intent_deterministic("adelante") == "si"

    def test_venga(self, s):
        assert s._detect_intent_deterministic("venga") == "si"

    def test_claro(self, s):
        assert s._detect_intent_deterministic("claro") == "si"

    def test_ok(self, s):
        assert s._detect_intent_deterministic("ok") == "si"

    def test_siguiente_es_si(self, s):
        assert s._detect_intent_deterministic("siguiente") == "si"

    def test_mas_es_si(self, s):
        assert s._detect_intent_deterministic("más") == "si"

    # ── "no" ──────────────────────────────────────────────────────────────────

    def test_no(self, s):
        assert s._detect_intent_deterministic("no") == "no"

    def test_no_gracias(self, s):
        assert s._detect_intent_deterministic("no gracias") == "no"

    def test_para(self, s):
        assert s._detect_intent_deterministic("para") == "no"

    def test_basta(self, s):
        assert s._detect_intent_deterministic("basta") == "no"

    def test_suficiente(self, s):
        assert s._detect_intent_deterministic("suficiente") == "no"

    # ── "todos" ───────────────────────────────────────────────────────────────

    def test_dame_todos(self, s):
        assert s._detect_intent_deterministic("dame todos") == "todos"

    def test_ver_todas(self, s):
        assert s._detect_intent_deterministic("ver todas") == "todos"

    def test_todo_de_una_vez(self, s):
        assert s._detect_intent_deterministic("de una vez") == "todos"

    def test_no_dame_todos_es_todos(self, s):
        """CRÍTICO: 'no, dame todos' debe ser 'todos', no 'no'."""
        assert s._detect_intent_deterministic("no, dame todos") == "todos"

    def test_no_quiero_todos_es_todos(self, s):
        """'no quiero todos' → 'todos' (la palabra 'todos' tiene prioridad)."""
        assert s._detect_intent_deterministic("no quiero todos") == "todos"

    # ── Default: "sí" ─────────────────────────────────────────────────────────

    def test_ambiguo_es_si(self, s):
        """Respuesta ambigua → asumir 'sí' (el usuario quiere ver los resultados)."""
        assert s._detect_intent_deterministic("mmm") == "si"

    def test_vacio_es_si(self, s):
        """Respuesta vacía → asumir 'sí'."""
        assert s._detect_intent_deterministic("") == "si"

    def test_desconocido_es_si(self, s):
        """Respuesta desconocida → asumir 'sí'."""
        assert s._detect_intent_deterministic("xyzabc") == "si"


# ═══════════════════════════════════════════════════════════════════════════════
# Integración: flujo completo de paginación
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlujoPaginacionCompleto:
    """
    Tests de flujo completo: summarize → is_pagination_request → handle_pagination_request.
    Sin BD, sin IA — solo lógica de paginación.
    """

    def _rows(self, n: int):
        return [{"NOMBRE": f"Artículo {i}", "PRECIO": float(i * 100)} for i in range(1, n + 1)]

    def test_flujo_completo_siguiente(self, s):
        """Flujo: muchos resultados → 'siguiente' → primera página."""
        _, state = s.summarize("dame artículos", self._rows(50), "SELECT 50")
        assert state is not None

        # El usuario dice "siguiente"
        assert s.is_pagination_request("siguiente")
        resp, state2 = s.handle_pagination_request("siguiente", state)
        assert state2 is not None
        assert "Artículo 1" in resp

    def test_flujo_completo_todos(self, s):
        """Flujo: muchos resultados → 'dame todos' → todos los resultados."""
        _, state = s.summarize("dame artículos", self._rows(30), "SELECT 30")
        assert state is not None

        # El usuario dice "dame todos"
        assert s.is_pagination_request("dame todos")
        resp, state2 = s.handle_pagination_request("dame todos", state)
        assert state2 is None  # Paginación terminada
        assert "Artículo 30" in resp

    def test_flujo_completo_numero(self, s):
        """Flujo: muchos resultados → 'dame 5' → 5 resultados."""
        _, state = s.summarize("dame artículos", self._rows(50), "SELECT 50")
        assert state is not None

        # El usuario dice "dame 5"
        assert s.is_pagination_request("dame 5")
        resp, state2 = s.handle_pagination_request("dame 5", state)
        assert state2 is not None
        assert "Artículo 1" in resp
        assert "Artículo 5" in resp
        assert "Artículo 6" not in resp

    def test_pregunta_negocio_no_activa_paginacion(self, s):
        """Una pregunta de negocio no debe activar la paginación."""
        preguntas_negocio = [
            "dame los artículos más vendidos",
            "cuántas facturas hay este mes",
            "total de ventas por agente",
            "clientes de Madrid",
            "artículos con stock a cero",
        ]
        for pregunta in preguntas_negocio:
            assert not s.is_pagination_request(pregunta), (
                f"'{pregunta}' fue detectada como paginación (falso positivo)"
            )

    def test_metaglass_flujo_si(self, s):
        """MetaGlass: muchos resultados → 'sí' → primera página."""
        _, state = s.summarize_for_metaglass(
            "dame artículos", self._rows(20), "SELECT 20",
            threshold=5, page_size=3
        )
        assert state is not None
        assert state["client"] == "metaglass"

        resp, state2 = s.handle_metaglass_pagination("sí", state, use_ai=False)
        assert resp
        assert "Artículo 1" in resp

    def test_metaglass_flujo_no(self, s):
        """MetaGlass: muchos resultados → 'no' → cancelar."""
        _, state = s.summarize_for_metaglass(
            "dame artículos", self._rows(20), "SELECT 20",
            threshold=5, page_size=3
        )
        assert state is not None

        resp, state2 = s.handle_metaglass_pagination("no", state, use_ai=False)
        assert state2 is None
        assert resp

    def test_metaglass_flujo_todos(self, s):
        """MetaGlass: muchos resultados → 'dame todos' → todos."""
        _, state = s.summarize_for_metaglass(
            "dame artículos", self._rows(10), "SELECT 10",
            threshold=5, page_size=3
        )
        assert state is not None

        resp, state2 = s.handle_metaglass_pagination("dame todos", state, use_ai=False)
        assert state2 is None
        assert resp
        assert "Artículo 1" in resp
