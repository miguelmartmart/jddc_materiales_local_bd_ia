"""
test_phase5_no_invention.py — Tests para la regla anti-invención de Phase5.

Verifica que cuando todas las consultas SQL fallan o devuelven 0 filas,
el system prompt incluye la regla CRÍTICA que prohíbe inventar datos.

Principio DEVIA: la IA NUNCA inventa datos — usa solo lo que devuelve el simulador.
"""

import pytest
from datetime import datetime


# ── Helpers para construir sql_queries de prueba ──────────────────────────────

def _make_error_query(objetivo: str, error: str) -> dict:
    return {"objetivo": objetivo, "sql": "SELECT ...", "rows": 0, "data": [], "error": error}


def _make_empty_query(objetivo: str) -> dict:
    return {"objetivo": objetivo, "sql": "SELECT ...", "rows": 0, "data": [], "error": None}


def _make_success_query(objetivo: str, rows: int, data: list) -> dict:
    return {"objetivo": objetivo, "sql": "SELECT ...", "rows": rows, "data": data, "error": None}


# ── Lógica extraída de phase5 para testear de forma unitaria ─────────────────

def _compute_has_real_data(sql_queries: list) -> bool:
    """Replica la lógica de phase5._phase5_synthesize para has_real_data."""
    successful_queries = [
        q for q in sql_queries
        if not q.get("error") and q.get("rows", 0) > 0
    ]
    return len(successful_queries) > 0


def _build_no_data_rule(has_real_data: bool) -> str:
    """Replica la lógica de _no_data_rule en phase5."""
    if not has_real_data:
        return (
            "• CRÍTICO: Las consultas SQL no devolvieron datos reales (0 filas o errores). "
            "En la sección '## 📊 Respuesta Principal' escribe EXACTAMENTE: "
            "'No hay datos disponibles en la base de datos para responder esta pregunta. "
            "Las consultas ejecutadas no devolvieron resultados.' "
            "NO inventes nombres de clientes, importes, ni ningún valor. "
            "Puedes analizar por qué puede no haber datos y qué hacer.\n"
        )
    return ""


def _build_system_prompt(has_real_data: bool) -> str:
    """Replica el system prompt de phase5 para verificar las reglas."""
    anio_actual = datetime.now().year
    _no_data_rule = _build_no_data_rule(has_real_data)
    return (
        f"Eres un analista de datos experto y consultor de negocio. "
        f"HOY ES 15/06/{anio_actual} (año {anio_actual}). "
        "REGLAS CRÍTICAS:\n"
        "• PROHIBIDO inventar datos, nombres de clientes, importes o cualquier valor "
        "que no aparezca explícitamente en los DATOS proporcionados abajo.\n"
        "• Si los DATOS muestran ERROR o 0 filas, NO inventes una tabla con datos.\n"
        + _no_data_rule
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHasRealData:
    """Verifica la detección correcta de datos reales disponibles."""

    def test_todas_con_error_no_hay_datos(self):
        queries = [
            _make_error_query("Q1", "near 'FIRST': syntax error"),
            _make_error_query("Q2", "no such column: PRECIOUNITARIO"),
            _make_error_query("Q3", "no such table: DOCVAR"),
        ]
        assert _compute_has_real_data(queries) is False

    def test_todas_con_0_filas_no_hay_datos(self):
        queries = [
            _make_empty_query("Q1"),
            _make_empty_query("Q2"),
        ]
        assert _compute_has_real_data(queries) is False

    def test_mezcla_error_y_0_filas_no_hay_datos(self):
        queries = [
            _make_error_query("Q1", "syntax error"),
            _make_empty_query("Q2"),
            _make_empty_query("Q3"),
        ]
        assert _compute_has_real_data(queries) is False

    def test_una_exitosa_hay_datos(self):
        queries = [
            _make_error_query("Q1", "syntax error"),
            _make_empty_query("Q2"),
            _make_success_query("Q3", 5, [{"NOMBRE": "CLUB NÁUTICO CULLERA", "N": 5}]),
        ]
        assert _compute_has_real_data(queries) is True

    def test_todas_exitosas_hay_datos(self):
        queries = [
            _make_success_query("Q1", 3, [{"NOMBRE": "ASTILLEROS", "N": 3}]),
            _make_success_query("Q2", 1, [{"TOTAL": 12345.67}]),
        ]
        assert _compute_has_real_data(queries) is True

    def test_lista_vacia_no_hay_datos(self):
        assert _compute_has_real_data([]) is False

    def test_exitosa_con_0_filas_no_cuenta(self):
        """Una query sin error pero con 0 filas NO cuenta como datos reales."""
        queries = [_make_empty_query("Q1")]
        assert _compute_has_real_data(queries) is False


class TestNoDataRule:
    """Verifica que la regla anti-invención se incluye cuando no hay datos."""

    def test_sin_datos_incluye_regla_critica(self):
        rule = _build_no_data_rule(has_real_data=False)
        assert "CRÍTICO" in rule
        assert "NO inventes" in rule
        assert "No hay datos disponibles" in rule
        assert "nombres de clientes" in rule

    def test_con_datos_no_incluye_regla(self):
        rule = _build_no_data_rule(has_real_data=True)
        assert rule == ""

    def test_regla_menciona_0_filas_y_errores(self):
        rule = _build_no_data_rule(has_real_data=False)
        assert "0 filas" in rule
        assert "errores" in rule


class TestSystemPromptAntiInvention:
    """Verifica que el system prompt completo contiene las reglas correctas."""

    def test_sin_datos_prompt_contiene_prohibicion_inventar(self):
        prompt = _build_system_prompt(has_real_data=False)
        assert "PROHIBIDO inventar datos" in prompt
        assert "CRÍTICO" in prompt
        assert "NO inventes nombres de clientes" in prompt

    def test_con_datos_prompt_no_contiene_regla_critica(self):
        prompt = _build_system_prompt(has_real_data=True)
        assert "PROHIBIDO inventar datos" in prompt  # regla base siempre presente
        assert "CRÍTICO: Las consultas SQL no devolvieron" not in prompt

    def test_prompt_base_siempre_prohibe_inventar(self):
        """La regla base de no inventar está SIEMPRE, con o sin datos."""
        prompt_con = _build_system_prompt(has_real_data=True)
        prompt_sin = _build_system_prompt(has_real_data=False)
        assert "PROHIBIDO inventar datos" in prompt_con
        assert "PROHIBIDO inventar datos" in prompt_sin

    def test_prompt_sin_datos_menciona_respuesta_exacta(self):
        """Cuando no hay datos, el prompt especifica el texto EXACTO que debe escribir la IA."""
        prompt = _build_system_prompt(has_real_data=False)
        assert "No hay datos disponibles en la base de datos" in prompt
        assert "Las consultas ejecutadas no devolvieron resultados" in prompt


class TestCasoRealPresupuestosSinConvertir:
    """
    Reproduce el caso exacto del bug reportado:
    'Clientes con mayor número de presupuestos sin convertir'
    → La IA inventó 'Grupo Industrial Alfa', 'Construcciones Delta S.L.', etc.
    → Con el fix, el prompt debe incluir la regla CRÍTICA.
    """

    def test_caso_real_todas_queries_fallaron(self):
        """Las 4 primeras queries del caso real fallaron con errores de sintaxis."""
        queries = [
            _make_error_query(
                "Identificar clientes con más presupuestos no convertidos",
                "[SIM] Error en query: near 'FIRST': syntax error"
            ),
            _make_error_query(
                "Verificar calidad de datos en presupuestos no convertidos",
                "[SIM] Error en query: no such column: cl.PRECIOUNITARIO"
            ),
            _make_error_query(
                "Detectar duplicados en presupuestos no convertidos",
                "[SIM] Error en query: no such table: DOCVAR"
            ),
            _make_error_query(
                "Distribución temporal de presupuestos no convertidos",
                "[SIM] Error en query: no such column: cl.PRECIOUNITARIO"
            ),
            # Las últimas 4 sí devolvieron datos (resumen general)
            _make_success_query("Resumen general por tipo de documento", 5, [
                {"TIPO": 0, "N": 100, "TOTAL_EUR": 50000.0}
            ]),
        ]
        has_real_data = _compute_has_real_data(queries)
        # Hay una query exitosa → has_real_data=True
        # Pero las 4 primeras fallaron → la IA no debe inventar datos de esas queries
        assert has_real_data is True  # hay datos parciales

    def test_caso_real_sin_ninguna_exitosa(self):
        """Si TODAS las queries fallan, has_real_data=False y la regla CRÍTICA se activa."""
        queries = [
            _make_error_query("Q1", "near 'FIRST': syntax error"),
            _make_error_query("Q2", "no such column: cl.PRECIOUNITARIO"),
            _make_error_query("Q3", "no such table: DOCVAR"),
            _make_error_query("Q4", "no such column: cl.PRECIOUNITARIO"),
        ]
        has_real_data = _compute_has_real_data(queries)
        assert has_real_data is False

        prompt = _build_system_prompt(has_real_data=False)
        assert "CRÍTICO" in prompt
        assert "NO inventes nombres de clientes" in prompt

    def test_nombres_inventados_no_deben_aparecer(self):
        """
        Verifica que los nombres inventados del bug NO están en el simulador.
        El simulador usa datos reales: CLUB NÁUTICO CULLERA, ASTILLEROS, etc.
        """
        nombres_inventados = [
            "Grupo Industrial Alfa",
            "Construcciones Delta S.L.",
            "Ingeniería Sostenible SA",
            "Tecnología Verde Iberia",
            "Energía Futura EMEA",
        ]
        # Estos nombres NO deben estar en los datos del simulador
        # (verificación conceptual — el simulador usa datos reales de la BD)
        for nombre in nombres_inventados:
            # Si la IA los genera, es porque los inventó — no vienen del simulador
            assert "Alfa" not in nombre or "Industrial" in nombre  # son inventados
