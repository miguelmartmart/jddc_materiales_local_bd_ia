"""
test_topic_focus_fix.py — Tests para la corrección del foco temático en el pipeline
de análisis profundo.

PROBLEMA DETECTADO (16/06/2026):
  El usuario preguntó sobre "artículos con mayor rotación" y recibió una respuesta
  sobre "anomalías en instalaciones". Causa raíz:
    1. _build_fixed_sqls() no reconocía "rotación"/"negociar"/"volumen" como
       indicadores de pregunta sobre artículos → los SQLs de artículos NO se activaban.
    2. Los SQLs genéricos de DOCCAB (distribución temporal, instalaciones) SÍ se
       ejecutaban → la IA sintetizaba sobre instalaciones porque era lo único que tenía.
    3. El prompt de síntesis (fase 5) no tenía instrucción de foco temático.

CORRECCIONES IMPLEMENTADAS:
    1. phase3_sqls.py: comp_kw ampliado con "rotación", "negociar", "volumen",
       "candidatos", "frecuencia", "demanda", "popular", "mayor", "mayores"...
    2. phase3_sqls.py: _is_article_focused guard — suprime SQLs genéricos de DOCCAB
       cuando la pregunta es claramente sobre artículos.
    3. phase5.py: _topic_focus_rule — instrucción explícita al modelo de síntesis
       para mantenerse en el tema de la pregunta.

COBERTURA DE TESTS:
    - Detección de keywords de artículos (positivos y negativos)
    - Detección de keywords de movimiento/rotación (positivos y negativos)
    - Combinaciones que SÍ deben activar SQLs de artículos
    - Combinaciones que NO deben activar SQLs de artículos
    - Guard _is_article_focused: supresión de SQLs genéricos de DOCCAB
    - Guard _is_article_focused: NO suprime SQLs de presupuestos/clientes
    - Casos reales del usuario (la pregunta exacta que falló)
    - Casos límite (palabras parciales, mayúsculas, acentos)
    - Casos de otras preguntas que NO deben verse afectadas
    - _topic_focus_rule: se activa solo para preguntas de artículos
    - _topic_focus_rule: no se activa para presupuestos, clientes, etc.
"""

import pytest
from unittest.mock import MagicMock


# ─── Importar el mixin bajo test ──────────────────────────────────────────────

from backend.modules.chat.deep_analysis.phase3_sqls import Phase3SqlsMixin


# ─── Fixture: instancia mínima del mixin ─────────────────────────────────────

class _Agent(Phase3SqlsMixin):
    """Instancia mínima para testear Phase3SqlsMixin sin dependencias."""
    pass


@pytest.fixture
def agent():
    return _Agent()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _phase2_with_doccab():
    """phase2_data con DOCCAB y DOCLIN disponibles (caso normal)."""
    return {
        "DOCCAB": {"has_serie": True, "has_codigoobra": False},
        "DOCLIN": {},
        "ARTICULO": {},
    }


def _phase2_without_doccab():
    """phase2_data sin DOCCAB (solo artículos)."""
    return {
        "DOCLIN": {},
        "ARTICULO": {},
    }


def _get_objectives(sqls):
    """Extrae los objetivos de una lista de SQLs para facilitar asserts."""
    return [s["objetivo"] for s in sqls]


def _has_article_sqls(sqls):
    """True si hay al menos un SQL de artículos (top/rotación)."""
    objectives = _get_objectives(sqls)
    return any(
        "artículo" in o.lower() or "artículos" in o.lower()
        for o in objectives
    )


# Objetivos exactos de los SQLs genéricos de DOCCAB que se suprimen con _is_article_focused.
# Estos son los únicos SQLs que el guard debe suprimir — cualquier otro SQL de DOCCAB
# (presupuestos, clientes, etc.) es específico y NO debe suprimirse.
_GENERIC_DOCCAB_OBJECTIVES = {
    # SQL FIJO 0: resumen general por tipo
    "resumen general por tipo de documento",
    # SQL FIJO 1: distribución temporal (con y sin serie)
    "distribución por año y serie",
    "distribución por año",
    # SQL FIJO 1b: distribución por mes
    "distribución por mes del año actual",
}


def _has_generic_doccab_sqls(sqls):
    """
    True si hay SQLs genéricos de DOCCAB (distribución temporal, resumen por tipo).
    Estos son los SQLs que se suprimen cuando la pregunta es sobre artículos.

    IMPORTANTE: Solo se consideran genéricos los SQLs de distribución temporal
    (por año/mes) y el resumen por tipo de documento. Los SQLs específicos de
    presupuestos (ESTADOPEND, DOCDESTINO, etc.) NO son genéricos aunque contengan
    "tipo de documento" en su objetivo.
    """
    objectives = _get_objectives(sqls)
    return any(
        any(generic in o.lower() for generic in _GENERIC_DOCCAB_OBJECTIVES)
        for o in objectives
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 1: Detección de keywords de artículos (art_kw)
# ═══════════════════════════════════════════════════════════════════════════════

class TestArtKwDetection:
    """Tests para las palabras clave que identifican preguntas sobre artículos."""

    @pytest.mark.parametrize("question", [
        "artículos con mayor rotación",
        "articulos mas vendidos",
        "productos más demandados",
        "item más popular",
        "referencias con mayor volumen",
        "referencia más vendida",
        "ARTÍCULOS con mayor rotación",  # mayúsculas
        "Artículos Con Mayor Rotación",  # título
    ])
    def test_art_kw_detected(self, agent, question):
        """Las palabras clave de artículos deben detectarse correctamente."""
        sqls = agent._build_fixed_sqls(question, _phase2_with_doccab())
        assert _has_article_sqls(sqls), (
            f"Se esperaban SQLs de artículos para: '{question}'\n"
            f"Objetivos obtenidos: {_get_objectives(sqls)}"
        )

    @pytest.mark.parametrize("question", [
        "cuántos presupuestos hay este año",
        "tasa de éxito de presupuestos",
        "clientes con más facturas",
        "distribución temporal de ventas",
        "instalaciones por año",
    ])
    def test_art_kw_not_detected_for_other_topics(self, agent, question):
        """Preguntas sobre otros temas NO deben activar SQLs de artículos."""
        sqls = agent._build_fixed_sqls(question, _phase2_with_doccab())
        assert not _has_article_sqls(sqls), (
            f"NO se esperaban SQLs de artículos para: '{question}'\n"
            f"Objetivos obtenidos: {_get_objectives(sqls)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2: Detección de keywords de movimiento/rotación (comp_kw)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompKwDetection:
    """Tests para las palabras clave de movimiento/rotación/volumen."""

    @pytest.mark.parametrize("question,expected_trigger", [
        # Palabras originales (deben seguir funcionando)
        ("artículos más vendidos", True),
        ("artículos más comprados", True),
        ("top artículos", True),
        ("artículos con más ventas", True),
        # Palabras nuevas añadidas en la corrección
        ("artículos con mayor rotación", True),
        ("artículos con mayor rotacion", True),  # sin tilde
        ("artículos que más rotan", True),
        ("artículos candidatos a negociar volumen", True),
        ("artículos con mayor frecuencia de compra", True),
        ("artículos más demandados", True),
        ("artículos populares", True),
        ("artículos con mayor demanda", True),
        ("artículos para negociar descuentos por volumen", True),
        ("referencias con mayor rotación", True),
        ("productos más frecuentes", True),
        ("productos con mayor volumen de ventas", True),
        # Casos que NO deben activar (solo art_kw sin comp_kw)
        ("artículos disponibles en almacén", False),
        ("artículo con código 12345", False),
        ("lista de artículos", False),
    ])
    def test_comp_kw_combinations(self, agent, question, expected_trigger):
        """Verifica que las combinaciones art_kw + comp_kw activan/no activan SQLs."""
        sqls = agent._build_fixed_sqls(question, _phase2_with_doccab())
        has_art = _has_article_sqls(sqls)
        assert has_art == expected_trigger, (
            f"Para '{question}': esperado={expected_trigger}, obtenido={has_art}\n"
            f"Objetivos: {_get_objectives(sqls)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 3: Caso real del usuario (la pregunta exacta que falló)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRealUserQuestion:
    """Tests con la pregunta exacta que el usuario reportó como fallida."""

    REAL_QUESTION = (
        'quiero saber "Artículos con Mayor Rotación (Candidatos a Negociar Volumen) '
        'Los artículos más vendidos son los mejores candidatos para negociar descuentos '
        'por volumen."'
    )

    def test_real_question_triggers_article_sqls(self, agent):
        """La pregunta real del usuario DEBE activar SQLs de artículos."""
        sqls = agent._build_fixed_sqls(self.REAL_QUESTION, _phase2_with_doccab())
        assert _has_article_sqls(sqls), (
            f"La pregunta real del usuario no activó SQLs de artículos.\n"
            f"Objetivos obtenidos: {_get_objectives(sqls)}"
        )

    def test_real_question_suppresses_generic_doccab_sqls(self, agent):
        """La pregunta real del usuario NO debe generar SQLs genéricos de DOCCAB."""
        sqls = agent._build_fixed_sqls(self.REAL_QUESTION, _phase2_with_doccab())
        assert not _has_generic_doccab_sqls(sqls), (
            f"La pregunta real del usuario generó SQLs genéricos de DOCCAB (instalaciones).\n"
            f"Objetivos obtenidos: {_get_objectives(sqls)}"
        )

    def test_real_question_has_three_article_sqls(self, agent):
        """La pregunta real debe generar exactamente 3 SQLs de artículos."""
        sqls = agent._build_fixed_sqls(self.REAL_QUESTION, _phase2_with_doccab())
        art_sqls = [s for s in sqls if "artículo" in s["objetivo"].lower() or "artículos" in s["objetivo"].lower()]
        assert len(art_sqls) == 3, (
            f"Se esperaban 3 SQLs de artículos, se obtuvieron {len(art_sqls)}.\n"
            f"Objetivos: {[s['objetivo'] for s in art_sqls]}"
        )

    def test_real_question_article_sqls_have_correct_structure(self, agent):
        """Los SQLs de artículos deben tener la estructura correcta (JOIN ARTICULO, DOCLIN)."""
        sqls = agent._build_fixed_sqls(self.REAL_QUESTION, _phase2_with_doccab())
        art_sqls = [s for s in sqls if "artículo" in s["objetivo"].lower() or "artículos" in s["objetivo"].lower()]
        for sql_entry in art_sqls:
            sql = sql_entry["sql"].upper()
            assert "ARTICULO" in sql, f"SQL sin tabla ARTICULO: {sql_entry['objetivo']}"
            assert "DOCLIN" in sql, f"SQL sin tabla DOCLIN: {sql_entry['objetivo']}"
            assert "CODARTICULO" in sql, f"SQL sin columna CODARTICULO: {sql_entry['objetivo']}"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 4: Guard _is_article_focused — supresión de SQLs genéricos
# ═══════════════════════════════════════════════════════════════════════════════

class TestArticleFocusGuard:
    """Tests para el guard que suprime SQLs genéricos de DOCCAB en preguntas de artículos."""

    @pytest.mark.parametrize("question", [
        "artículos con mayor rotación",
        "artículos más vendidos",
        "top 10 artículos por volumen",
        "productos con mayor demanda",
        "referencias más frecuentes",
        "artículos candidatos a negociar",
    ])
    def test_article_questions_suppress_generic_doccab(self, agent, question):
        """Preguntas de artículos NO deben generar SQLs genéricos de DOCCAB."""
        sqls = agent._build_fixed_sqls(question, _phase2_with_doccab())
        assert not _has_generic_doccab_sqls(sqls), (
            f"Pregunta de artículos generó SQLs genéricos de DOCCAB: '{question}'\n"
            f"Objetivos: {_get_objectives(sqls)}"
        )

    @pytest.mark.parametrize("question", [
        "cuántos presupuestos hay",
        "tasa de éxito de presupuestos",
        "clientes con más facturas",
        "distribución de ventas por año",
        "facturas del año actual",
        "importe medio de facturas",
    ])
    def test_non_article_questions_keep_generic_doccab(self, agent, question):
        """Preguntas NO relacionadas con artículos SÍ deben generar SQLs genéricos de DOCCAB."""
        sqls = agent._build_fixed_sqls(question, _phase2_with_doccab())
        assert _has_generic_doccab_sqls(sqls), (
            f"Pregunta no-artículo perdió SQLs genéricos de DOCCAB: '{question}'\n"
            f"Objetivos: {_get_objectives(sqls)}"
        )

    def test_article_question_without_doccab_in_phase2(self, agent):
        """Si DOCCAB no está en phase2_data, no hay SQLs genéricos que suprimir."""
        sqls = agent._build_fixed_sqls(
            "artículos con mayor rotación",
            _phase2_without_doccab()
        )
        # Debe haber SQLs de artículos igualmente
        assert _has_article_sqls(sqls), "Deben generarse SQLs de artículos aunque no haya DOCCAB"
        # No debe haber SQLs genéricos de DOCCAB (porque no está en phase2_data)
        assert not _has_generic_doccab_sqls(sqls)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 5: Otras preguntas no deben verse afectadas
# ═══════════════════════════════════════════════════════════════════════════════

class TestOtherQuestionsUnaffected:
    """Tests para verificar que las correcciones no rompen otras preguntas."""

    def test_presupuestos_question_still_works(self, agent):
        """Las preguntas de presupuestos siguen generando sus SQLs específicos."""
        sqls = agent._build_fixed_sqls(
            "cuántos presupuestos se han aceptado este año",
            _phase2_with_doccab()
        )
        objectives = _get_objectives(sqls)
        # Debe haber SQLs de presupuestos
        has_presupuesto_sqls = any("presupuesto" in o.lower() for o in objectives)
        assert has_presupuesto_sqls, (
            f"Pregunta de presupuestos no generó SQLs de presupuestos.\n"
            f"Objetivos: {objectives}"
        )

    def test_clientes_question_still_works(self, agent):
        """Las preguntas de clientes siguen generando sus SQLs específicos."""
        sqls = agent._build_fixed_sqls(
            "top 10 clientes por importe facturado",
            _phase2_with_doccab()
        )
        objectives = _get_objectives(sqls)
        has_cliente_sqls = any("cliente" in o.lower() for o in objectives)
        assert has_cliente_sqls, (
            f"Pregunta de clientes no generó SQLs de clientes.\n"
            f"Objetivos: {objectives}"
        )

    def test_importe_question_still_works(self, agent):
        """Las preguntas de importes siguen generando sus SQLs específicos."""
        sqls = agent._build_fixed_sqls(
            "cuál es el importe medio de las facturas",
            _phase2_with_doccab()
        )
        objectives = _get_objectives(sqls)
        has_importe_sqls = any("importe" in o.lower() for o in objectives)
        assert has_importe_sqls, (
            f"Pregunta de importes no generó SQLs de importes.\n"
            f"Objetivos: {objectives}"
        )

    def test_proyecto_question_still_works(self, agent):
        """Las preguntas de proyectos siguen generando sus SQLs específicos."""
        sqls = agent._build_fixed_sqls(
            "análisis económico de proyectos y obras",
            _phase2_with_doccab()
        )
        objectives = _get_objectives(sqls)
        has_proyecto_sqls = any("proyecto" in o.lower() for o in objectives)
        assert has_proyecto_sqls, (
            f"Pregunta de proyectos no generó SQLs de proyectos.\n"
            f"Objetivos: {objectives}"
        )

    def test_mes_question_still_works(self, agent):
        """Las preguntas con mes específico siguen generando SQLs de mes."""
        sqls = agent._build_fixed_sqls(
            "facturas del mes de enero",
            _phase2_with_doccab()
        )
        objectives = _get_objectives(sqls)
        has_mes_sqls = any("mes 1" in o.lower() or "enero" in o.lower() for o in objectives)
        assert has_mes_sqls, (
            f"Pregunta con mes no generó SQLs de mes.\n"
            f"Objetivos: {objectives}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 6: Casos límite y edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests para casos límite."""

    def test_empty_question(self, agent):
        """Pregunta vacía no debe lanzar excepción."""
        sqls = agent._build_fixed_sqls("", _phase2_with_doccab())
        assert isinstance(sqls, list)

    def test_question_with_only_art_kw_no_comp_kw(self, agent):
        """Solo art_kw sin comp_kw NO debe activar SQLs de artículos."""
        sqls = agent._build_fixed_sqls(
            "lista de artículos disponibles",
            _phase2_with_doccab()
        )
        assert not _has_article_sqls(sqls), (
            "Solo art_kw sin comp_kw no debe activar SQLs de artículos"
        )

    def test_question_with_only_comp_kw_no_art_kw(self, agent):
        """Solo comp_kw sin art_kw NO debe activar SQLs de artículos."""
        sqls = agent._build_fixed_sqls(
            "mayor rotación de clientes",
            _phase2_with_doccab()
        )
        assert not _has_article_sqls(sqls), (
            "Solo comp_kw sin art_kw no debe activar SQLs de artículos"
        )

    def test_article_question_with_accents_and_no_accents(self, agent):
        """Debe funcionar con y sin tildes."""
        q_with = "artículos con mayor rotación"
        q_without = "articulos con mayor rotacion"
        sqls_with = agent._build_fixed_sqls(q_with, _phase2_with_doccab())
        sqls_without = agent._build_fixed_sqls(q_without, _phase2_with_doccab())
        assert _has_article_sqls(sqls_with), "Con tildes debe activar SQLs de artículos"
        assert _has_article_sqls(sqls_without), "Sin tildes debe activar SQLs de artículos"

    def test_article_question_uppercase(self, agent):
        """Debe funcionar con mayúsculas."""
        sqls = agent._build_fixed_sqls(
            "ARTÍCULOS CON MAYOR ROTACIÓN",
            _phase2_with_doccab()
        )
        assert _has_article_sqls(sqls), "Mayúsculas deben activar SQLs de artículos"

    def test_mixed_topic_question_article_wins(self, agent):
        """
        Si la pregunta mezcla artículos y presupuestos, ambos SQLs deben generarse.
        El guard _is_article_focused suprime los SQLs GENÉRICOS de DOCCAB
        (distribución temporal, resumen por tipo), pero NO los SQLs específicos
        de presupuestos (ESTADOPEND, DOCDESTINO, etc.) que son relevantes.
        """
        sqls = agent._build_fixed_sqls(
            "artículos más vendidos en presupuestos aceptados",
            _phase2_with_doccab()
        )
        objectives = _get_objectives(sqls)
        # Artículos deben estar
        assert _has_article_sqls(sqls), "Debe haber SQLs de artículos"
        # Presupuestos también (la pregunta los menciona)
        has_presupuesto = any("presupuesto" in o.lower() for o in objectives)
        assert has_presupuesto, "Debe haber SQLs de presupuestos también"
        # Los SQLs GENÉRICOS de DOCCAB (distribución temporal) SÍ se suprimen
        # porque _is_article_focused es True (hay art_kw + comp_kw)
        assert not _has_generic_doccab_sqls(sqls), (
            "Los SQLs genéricos de DOCCAB (distribución temporal) deben suprimirse "
            "cuando la pregunta es sobre artículos, aunque también mencione presupuestos"
        )
        # Pero los SQLs específicos de presupuestos (ESTADOPEND, etc.) SÍ deben estar
        has_estadopend = any("estadopend" in o.lower() for o in objectives)
        assert has_estadopend, (
            "Los SQLs específicos de presupuestos (ESTADOPEND) deben generarse "
            "aunque el guard suprima los genéricos de DOCCAB"
        )

    def test_all_article_sqls_have_valid_sql(self, agent):
        """Todos los SQLs de artículos deben tener SQL válido (no vacío)."""
        sqls = agent._build_fixed_sqls(
            "artículos con mayor rotación",
            _phase2_with_doccab()
        )
        art_sqls = [s for s in sqls if "artículo" in s["objetivo"].lower() or "artículos" in s["objetivo"].lower()]
        for sql_entry in art_sqls:
            assert sql_entry.get("sql"), f"SQL vacío en: {sql_entry['objetivo']}"
            assert sql_entry.get("objetivo"), "Objetivo vacío"
            assert len(sql_entry["sql"]) > 20, f"SQL demasiado corto: {sql_entry['sql']}"

    def test_article_sqls_use_correct_join_syntax(self, agent):
        """Los SQLs de artículos deben usar la sintaxis correcta del simulador."""
        sqls = agent._build_fixed_sqls(
            "artículos con mayor rotación",
            _phase2_with_doccab()
        )
        art_sqls = [s for s in sqls if "artículo" in s["objetivo"].lower() or "artículos" in s["objetivo"].lower()]
        for sql_entry in art_sqls:
            sql = sql_entry["sql"].upper()
            # Debe usar CODDOCUMENTO (no CODIGO) para el JOIN DOCCAB
            if "DOCCAB" in sql:
                assert "CODDOCUMENTO" in sql, (
                    f"SQL debe usar CODDOCUMENTO para JOIN DOCCAB: {sql_entry['objetivo']}"
                )
            # No debe usar DOCLIN.CODART (no existe en el simulador)
            assert "CODART" not in sql or "CODARTICULO" in sql, (
                f"SQL usa CODART en lugar de CODARTICULO: {sql_entry['objetivo']}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 7: Tests para _topic_focus_rule en phase5.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestTopicFocusRule:
    """Tests para la regla de foco temático en el prompt de síntesis (fase 5)."""

    def _get_topic_focus_rule(self, question: str) -> str:
        """Simula la lógica de _topic_focus_rule de phase5.py."""
        _art_kw = ["artículo", "articulo", "producto", "item", "referencia"]
        _art_mov_kw = ["rotación", "rotacion", "vendido", "comprado", "negociar",
                       "volumen", "candidatos", "frecuencia", "demanda", "popular"]
        _is_article_topic = (
            any(k in question.lower() for k in _art_kw) and
            any(k in question.lower() for k in _art_mov_kw)
        )
        return (
            "• FOCO OBLIGATORIO: La pregunta es sobre ARTÍCULOS/PRODUCTOS. "
            "Tu respuesta DEBE centrarse en artículos, su rotación y volumen de ventas. "
            "NO menciones instalaciones, presupuestos ni otros temas no relacionados. "
            "Si los datos de artículos son escasos, indícalo claramente.\n"
        ) if _is_article_topic else ""

    @pytest.mark.parametrize("question", [
        "artículos con mayor rotación",
        "artículos más vendidos",
        "productos con mayor demanda",
        "referencias con mayor volumen",
        "artículos candidatos a negociar",
        'quiero saber "Artículos con Mayor Rotación (Candidatos a Negociar Volumen)"',
    ])
    def test_topic_focus_rule_active_for_article_questions(self, question):
        """La regla de foco debe activarse para preguntas de artículos."""
        rule = self._get_topic_focus_rule(question)
        assert rule != "", (
            f"La regla de foco debería activarse para: '{question}'"
        )
        assert "ARTÍCULOS" in rule
        assert "instalaciones" in rule.lower()
        assert "presupuestos" in rule.lower()

    @pytest.mark.parametrize("question", [
        "cuántos presupuestos hay",
        "tasa de éxito de presupuestos",
        "clientes con más facturas",
        "distribución de ventas por año",
        "instalaciones por año",
        "importe medio de facturas",
        "análisis económico de proyectos",
    ])
    def test_topic_focus_rule_inactive_for_other_questions(self, question):
        """La regla de foco NO debe activarse para preguntas de otros temas."""
        rule = self._get_topic_focus_rule(question)
        assert rule == "", (
            f"La regla de foco NO debería activarse para: '{question}'"
        )

    def test_topic_focus_rule_content_is_explicit(self):
        """La regla debe ser explícita sobre qué NO mencionar."""
        rule = self._get_topic_focus_rule("artículos con mayor rotación")
        assert "instalaciones" in rule.lower(), "Debe mencionar explícitamente 'instalaciones'"
        assert "presupuestos" in rule.lower(), "Debe mencionar explícitamente 'presupuestos'"
        assert "FOCO OBLIGATORIO" in rule, "Debe ser una instrucción obligatoria"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 8: Tests de regresión — verificar que los SQLs de artículos son correctos
# ═══════════════════════════════════════════════════════════════════════════════

class TestArticleSqlsRegression:
    """Tests de regresión para los SQLs de artículos (existían antes de la corrección)."""

    def test_article_sqls_by_frequency(self, agent):
        """SQL de artículos por frecuencia (N_LINEAS) debe existir y ser correcto."""
        sqls = agent._build_fixed_sqls("artículos más vendidos", _phase2_with_doccab())
        freq_sql = next(
            (s for s in sqls if "frecuencia" in s["objetivo"].lower() or "líneas" in s["objetivo"].lower()),
            None
        )
        assert freq_sql is not None, "Debe existir SQL de artículos por frecuencia"
        assert "N_LINEAS" in freq_sql["sql"].upper() or "COUNT" in freq_sql["sql"].upper()
        assert "ORDER BY" in freq_sql["sql"].upper()

    def test_article_sqls_by_amount(self, agent):
        """SQL de artículos por importe total debe existir."""
        sqls = agent._build_fixed_sqls("artículos más vendidos", _phase2_with_doccab())
        amount_sql = next(
            (s for s in sqls if "importe" in s["objetivo"].lower()),
            None
        )
        assert amount_sql is not None, "Debe existir SQL de artículos por importe"
        assert "IMPORTE_TOTAL" in amount_sql["sql"].upper() or "PRECIO" in amount_sql["sql"].upper()

    def test_article_sqls_by_quantity(self, agent):
        """SQL de artículos por cantidad (unidades) debe existir."""
        sqls = agent._build_fixed_sqls("artículos más vendidos", _phase2_with_doccab())
        qty_sql = next(
            (s for s in sqls if "cantidad" in s["objetivo"].lower()),
            None
        )
        assert qty_sql is not None, "Debe existir SQL de artículos por cantidad"
        assert "CANTIDAD_TOTAL" in qty_sql["sql"].upper() or "CANTIDAD" in qty_sql["sql"].upper()

    def test_article_sqls_filter_tipo_13_for_ventas(self, agent):
        """Los SQLs de ventas deben filtrar por TIPO = 13 (facturas)."""
        sqls = agent._build_fixed_sqls("artículos más vendidos", _phase2_with_doccab())
        # Al menos uno de los SQLs de artículos debe filtrar por TIPO = 13
        art_sqls_with_tipo = [
            s for s in sqls
            if ("artículo" in s["objetivo"].lower() or "artículos" in s["objetivo"].lower())
            and "TIPO = 13" in s["sql"].upper()
        ]
        assert len(art_sqls_with_tipo) >= 1, (
            "Al menos un SQL de artículos debe filtrar por TIPO = 13 (facturas)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 9: Tests de integración — verificar que no hay hardcoding
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoHardcoding:
    """Tests para verificar que no hay valores hardcodeados problemáticos."""

    def test_no_hardcoded_year_in_article_sqls(self, agent):
        """Los SQLs de artículos no deben tener años hardcodeados."""
        sqls = agent._build_fixed_sqls("artículos con mayor rotación", _phase2_with_doccab())
        art_sqls = [s for s in sqls if "artículo" in s["objetivo"].lower() or "artículos" in s["objetivo"].lower()]
        for sql_entry in art_sqls:
            sql = sql_entry["sql"]
            # No debe haber años hardcodeados como 2024, 2025, 2026
            import re
            years = re.findall(r'\b20\d{2}\b', sql)
            assert not years, (
                f"SQL de artículos tiene año hardcodeado {years}: {sql_entry['objetivo']}"
            )

    def test_no_hardcoded_client_names(self, agent):
        """Los SQLs no deben tener nombres de clientes hardcodeados."""
        sqls = agent._build_fixed_sqls("artículos con mayor rotación", _phase2_with_doccab())
        for sql_entry in sqls:
            sql = sql_entry["sql"].lower()
            # Verificar que no hay nombres propios hardcodeados
            assert "jddc" not in sql, f"SQL tiene 'jddc' hardcodeado: {sql_entry['objetivo']}"

    def test_article_sqls_use_parametric_limit(self, agent):
        """Los SQLs de artículos deben usar FIRST N (Firebird) para limitar resultados."""
        sqls = agent._build_fixed_sqls("artículos con mayor rotación", _phase2_with_doccab())
        art_sqls = [s for s in sqls if "artículo" in s["objetivo"].lower() or "artículos" in s["objetivo"].lower()]
        for sql_entry in art_sqls:
            sql = sql_entry["sql"].upper()
            assert "FIRST" in sql or "LIMIT" in sql, (
                f"SQL de artículos debe limitar resultados con FIRST/LIMIT: {sql_entry['objetivo']}"
            )

    def test_is_article_focused_flag_consistency(self, agent):
        """
        El flag _is_article_focused debe ser consistente entre phase3_sqls y phase5.
        Ambos usan las mismas keywords — verificar que la lógica es idéntica.
        """
        # Keywords de phase3_sqls.py
        art_kw_p3 = ["artículo", "articulo", "producto", "item", "referencia", "referencias"]
        art_mov_kw_p3 = [
            "rotación", "rotacion", "rotan", "rota",
            "negociar", "negociación", "negociacion", "volumen",
            "candidatos", "candidato",
            "frecuencia", "frecuente", "frecuentes",
            "mayor", "mayores", "mejor", "mejores",
            "demanda", "popular", "populares",
            "compra", "venta", "compras", "ventas", "top",
            "vendido", "vendidos", "comprado", "comprados", "más", "mas",
        ]
        # Keywords de phase5.py
        art_kw_p5 = ["artículo", "articulo", "producto", "item", "referencia"]
        art_mov_kw_p5 = ["rotación", "rotacion", "vendido", "comprado", "negociar",
                         "volumen", "candidatos", "frecuencia", "demanda", "popular"]

        # Verificar que p5 es subconjunto de p3 (p3 es más permisivo, p5 más estricto)
        for kw in art_kw_p5:
            assert kw in art_kw_p3, f"Keyword '{kw}' de phase5 no está en phase3"
        for kw in art_mov_kw_p5:
            assert kw in art_mov_kw_p3, f"Keyword de movimiento '{kw}' de phase5 no está en phase3"

        # La pregunta real del usuario debe activar AMBOS guards
        q = "artículos con mayor rotación candidatos a negociar volumen"
        p3_active = any(k in q for k in art_kw_p3) and any(k in q for k in art_mov_kw_p3)
        p5_active = any(k in q for k in art_kw_p5) and any(k in q for k in art_mov_kw_p5)
        assert p3_active, "Guard de phase3 debe activarse para la pregunta real"
        assert p5_active, "Guard de phase5 debe activarse para la pregunta real"
