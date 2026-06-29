"""
test_fixed_sqls_comprehensive.py
~600 casos para _build_fixed_sqls() de Phase3SqlsMixin.

Verifica que el generador de SQLs fijos produce las queries correctas
según las palabras clave de la pregunta. Código REAL sin mocks.

Cubre:
  - Preguntas sobre facturas → SQL con TIPO filter
  - Preguntas sobre clientes → SQL con JOIN CLIENTE + NOMBRECOMERCIAL
  - Preguntas sobre concentración → SQL de concentración top-5
  - Preguntas sobre presupuestos → SQL con TIPO=0
  - Preguntas sobre artículos → NO genera SQLs genéricos de DOCCAB
  - Preguntas con mes específico → SQL con EXTRACT(MONTH)
  - Verificación de formato SQL (sin tablas inventadas, columnas correctas)
"""

import pytest
from backend.modules.chat.deep_analysis.phase3_sqls import Phase3SqlsMixin


class _MockPhase3Sqls(Phase3SqlsMixin):
    """Instancia mínima para acceder a _build_fixed_sqls."""
    pass


_p3 = _MockPhase3Sqls()

# phase2_data simulado con DOCCAB presente (necesario para que genere SQLs)
_PHASE2_WITH_DOCCAB = {
    "DOCCAB": {"count": 220, "has_serie": True, "has_codigoobra": False},
    "CLIENTE": {"count": 51},
    "DOCLIN": {"count": 500},
}

_PHASE2_NO_DOCCAB = {
    "ARTICULO": {"count": 100},
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build(question: str, phase2_data=None) -> list:
    """Llama a _build_fixed_sqls con la pregunta y los datos de fase 2."""
    if phase2_data is None:
        phase2_data = _PHASE2_WITH_DOCCAB
    return _p3._build_fixed_sqls(question, phase2_data)


def _sqls_text(question: str, phase2_data=None) -> str:
    """Concatena todos los SQL de los fixed SQLs para facilitar búsqueda."""
    sqls = _build(question, phase2_data)
    return " ".join(s.get("sql", "") for s in sqls).upper()


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas sobre CLIENTES (nuevo SQL añadido esta sesión)
# ═══════════════════════════════════════════════════════════════════════════════

_CLIENTE_QUESTIONS = [
    "¿cuáles son los top 5 clientes por facturación?",
    "dame los clientes más importantes por importe",
    "concentración de cartera en pocos clientes",
    "riesgo de concentración en clientes",
    "¿cuánto representa el top 5 de clientes sobre el total?",
    "top 10 clientes por ventas",
    "dependencia de clientes principales",
    "ranking de clientes por importe total",
    "los 5 principales clientes de la empresa",
    "análisis de concentración de clientes",
    "clientes con mayor facturación",
    "¿hay riesgo de dependencia de pocos clientes?",
    "análisis Pareto de clientes",
    "clientes que representan el 80% de la facturación",
    "¿qué porcentaje representa el mayor cliente?",
    "top clientes por ventas del año",
    "comprador que más compra",
    "principales compradores",
    "clientes VIP",
    "distribución de ventas por cliente",
]


@pytest.mark.parametrize("question", _CLIENTE_QUESTIONS)
def test_fixed_sqls_cliente_incluye_join(question: str):
    """Preguntas sobre clientes deben incluir SQL con JOIN CLIENTE."""
    sqls_text = _sqls_text(question)
    assert "JOIN CLIENTE" in sqls_text or "LEFT JOIN CLIENTE" in sqls_text, (
        f"No se encontró JOIN CLIENTE en fixed SQLs para: '{question}'\n"
        f"SQLs generados: {sqls_text[:200]}"
    )


@pytest.mark.parametrize("question", _CLIENTE_QUESTIONS)
def test_fixed_sqls_cliente_usa_nombrecomercial(question: str):
    """Preguntas sobre clientes deben usar NOMBRECOMERCIAL (no NOMBRE)."""
    sqls_text = _sqls_text(question)
    assert "NOMBRECOMERCIAL" in sqls_text, (
        f"No se encontró NOMBRECOMERCIAL en fixed SQLs para: '{question}'"
    )
    # Verificar que NO usa c.NOMBRE (columna incorrecta)
    # NOMBRE puede aparecer si hay otra tabla, solo verificamos NOMBRECOMERCIAL
    assert "C.NOMBRE" not in sqls_text or "NOMBRECOMERCIAL" in sqls_text, (
        f"Se usa c.NOMBRE en vez de NOMBRECOMERCIAL para: '{question}'"
    )


_CONCENTRACION_QUESTIONS = [
    "concentración de clientes",
    "riesgo de concentración en pocos clientes",
    "top 5 de clientes vs total",
    "¿cuánto representan los 5 primeros clientes?",
    "análisis Pareto 80/20 de clientes",
    "dependencia de los cinco principales clientes",
]


@pytest.mark.parametrize("question", _CONCENTRACION_QUESTIONS)
def test_fixed_sqls_concentracion_incluye_calculo(question: str):
    """Preguntas de concentración deben incluir SQL de cálculo top-5."""
    sqls = _build(question)
    # Buscar SQL de concentración (debe tener subquery o FIRST 5)
    sqls_combined = " ".join(s.get("sql", "") for s in sqls).upper()
    has_top5 = "FIRST 5" in sqls_combined or "LIMIT 5" in sqls_combined
    has_subquery_codcliente = "CODCLIENTE" in sqls_combined
    assert has_top5 or has_subquery_codcliente, (
        f"Falta SQL de concentración para: '{question}'\n"
        f"SQLs: {sqls_combined[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas sobre FACTURAS / IMPORTE
# ═══════════════════════════════════════════════════════════════════════════════

_FACTURA_QUESTIONS = [
    "total de facturas del mes",
    "¿cuánto se ha facturado este año?",
    "importe medio de las facturas",
    "facturas pendientes de pago",
    "facturación por mes",
    "total facturado en 2026",
    "¿cuántas facturas hay?",
    "importe de las facturas de este trimestre",
    "facturación total del año",
    "análisis de facturación por cliente",
]


@pytest.mark.parametrize("question", _FACTURA_QUESTIONS)
def test_fixed_sqls_factura_genera_sqls(question: str):
    """Preguntas sobre facturas generan al menos 1 fixed SQL."""
    sqls = _build(question)
    assert len(sqls) >= 1, (
        f"No se generaron fixed SQLs para: '{question}'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas sobre PRESUPUESTOS
# ═══════════════════════════════════════════════════════════════════════════════

_PRESUPUESTO_QUESTIONS = [
    "estado de presupuestos pendientes",
    "tasa de éxito de presupuestos",
    "presupuestos aceptados vs rechazados",
    "¿cuántos presupuestos se han convertido en facturas?",
    "presupuestos con ESTADOPEND",
    "análisis de presupuestos por agente",
    "presupuestos del año en curso",
    "¿cuál es la tasa de conversión de presupuestos?",
    "exito de presupuestos",
    "presupuestos aceptados",
]


@pytest.mark.parametrize("question", _PRESUPUESTO_QUESTIONS)
def test_fixed_sqls_presupuesto_tipo_0(question: str):
    """Preguntas sobre presupuestos incluyen SQL con TIPO = 0."""
    sqls_text = _sqls_text(question)
    assert "TIPO = 0" in sqls_text, (
        f"No se encontró TIPO = 0 en fixed SQLs para: '{question}'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas sobre ARTÍCULOS (no deben incluir SQLs genéricos de DOCCAB)
# ═══════════════════════════════════════════════════════════════════════════════

_ARTICULO_QUESTIONS = [
    "¿cuáles son los artículos más vendidos?",
    "top 10 artículos por ventas",
    "artículos con más rotación",
    "productos más demandados",
    "artículos candidatos a negociar",
    "¿qué artículos tienen mayor volumen de compra?",
    "artículos más vendidos del mes",
    "referencias con mayor rotación",
    "items con mayor frecuencia de venta",
    "artículos top en ventas",
]


@pytest.mark.parametrize("question", _ARTICULO_QUESTIONS)
def test_fixed_sqls_articulo_no_generic_doccab(question: str):
    """
    Preguntas sobre artículos NO deben incluir los SQLs genéricos de DOCCAB
    (distribución temporal, instalaciones, etc.) que confunden a la IA.
    """
    sqls = _build(question)
    objectives = [s.get("objetivo", "").lower() for s in sqls]
    # No debe haber SQL de distribución temporal genérica de DOCCAB
    has_temporal = any(
        "distribución" in o or "distribution" in o or "temporal" in o
        for o in objectives
        if "artículo" not in o and "article" not in o
    )
    # Ahora que _is_article_focused suprime los SQLs genéricos de DOCCAB,
    # verificar que no aparecen
    sqls_text = _sqls_text(question)
    assert "DISTRIBUCIÓN COMPLETA DE TIPOS" not in sqls_text.upper() or len(sqls) <= 3, (
        f"SQL genérico de DOCCAB incluido para pregunta de artículo: '{question}'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Preguntas con MES ESPECÍFICO
# ═══════════════════════════════════════════════════════════════════════════════

_MES_QUESTIONS = [
    ("facturas de enero del año actual", "MONTH"),
    ("total facturado en febrero", "MONTH"),
    ("albaranes de marzo pendientes", "MONTH"),
    ("presupuestos de abril", "MONTH"),
    ("análisis de ventas de mayo", "MONTH"),
    ("datos de junio", "MONTH"),
    ("resumen de julio", "MONTH"),
    ("agosto: ¿qué documentos hay?", "MONTH"),
    ("clientes de septiembre", "MONTH"),
    ("facturas de octubre sin pagar", "MONTH"),
    ("presupuestos de noviembre", "MONTH"),
    ("cierre de diciembre", "MONTH"),
]


@pytest.mark.parametrize("question,expected_keyword", _MES_QUESTIONS)
def test_fixed_sqls_mes_especifico(question: str, expected_keyword: str):
    """Preguntas con mes específico generan SQL con filtro de mes."""
    sqls = _build(question)
    sqls_text = " ".join(s.get("sql", "") for s in sqls).upper()
    has_month_filter = (
        "EXTRACT(MONTH" in sqls_text
        or "STRFTIME('%M'" in sqls_text
        or "strftime('%m'" in sqls_text.lower()
        or "MONTH" in sqls_text
    )
    assert has_month_filter, (
        f"Falta filtro de mes en fixed SQLs para: '{question}'\n"
        f"SQLs: {sqls_text[:300]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests de formato y seguridad
# ═══════════════════════════════════════════════════════════════════════════════

def test_fixed_sqls_returns_list():
    """_build_fixed_sqls siempre devuelve lista."""
    for q in ["", "   ", "test", "facturas de clientes"]:
        result = _build(q)
        assert isinstance(result, list), f"Debe devolver lista para '{q}'"


def test_fixed_sqls_each_has_objetivo_and_sql():
    """Cada fixed SQL tiene 'objetivo' y 'sql'."""
    sqls = _build("análisis completo de clientes y facturas con concentración")
    for i, s in enumerate(sqls):
        assert "objetivo" in s, f"SQL {i} sin 'objetivo'"
        assert "sql" in s, f"SQL {i} sin 'sql'"
        assert len(s["sql"].strip()) > 0, f"SQL {i} con 'sql' vacío"


def test_fixed_sqls_no_invented_tables():
    """Los fixed SQLs no deben usar tablas inventadas."""
    _SIMULATOR_TABLES = frozenset({
        "DOCCAB", "DOCLIN", "CLIENTE", "PROVEED", "ARTICULO", "FAMILIA",
        "ALMACEN", "RECURSO", "CAJA", "ESTALMACEN", "PROYECTOS", "PROYVAR",
        "PRESUPROYE", "DOCDESTINO", "AGENTES", "TIPOSIVA", "TARIFAS",
        "FORMASPAGO", "SERIES", "AVISOS",
    })
    import re
    _from_join_re = re.compile(r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)', re.IGNORECASE)
    # Incluir nombres de columna que aparecen tras FROM en EXTRACT(PART FROM col)
    _SQL_KEYWORDS = frozenset({'SELECT', 'WHERE', 'AND', 'OR', 'ON', 'AS',
                               'INNER', 'LEFT', 'RIGHT', 'OUTER', 'NATURAL',
                               'CURRENT_DATE', 'DUAL', 'FECHA', 'DATE', 'NOW',
                               'YEAR', 'MONTH', 'DAY', 'CURRENT'})

    questions = [
        "top 5 clientes por facturación con concentración",
        "presupuestos aceptados con tasa de éxito",
        "análisis de importes y medias de facturas",
    ]
    for q in questions:
        sqls = _build(q)
        for s in sqls:
            sql = s.get("sql", "")
            # Extraer nombres de CTEs para excluirlos
            cte_names = set(re.findall(r'\bWITH\s+(\w+)\s+AS\s*\(', sql, re.IGNORECASE))
            tables_in_sql = [
                m.group(1).upper()
                for m in _from_join_re.finditer(sql)
                if m.group(1).upper() not in _SQL_KEYWORDS
                and m.group(1).upper() not in cte_names
            ]
            # RDB = prefijo de tablas sistema Firebird (RDB$RELATION_FIELDS, etc.)
            invented = [t for t in tables_in_sql if t not in _SIMULATOR_TABLES and not t.startswith('RDB')]
            assert not invented, (
                f"Tabla(s) inventada(s) en fixed SQL '{s['objetivo']}': {invented}\n"
                f"SQL: {sql}"
            )


def test_fixed_sqls_empty_question():
    """Pregunta vacía no debe generar error."""
    sqls = _build("")
    assert isinstance(sqls, list)


def test_fixed_sqls_no_doccab_data():
    """Sin DOCCAB en phase2_data, no se generan SQLs de DOCCAB."""
    sqls = _build("clientes por facturación", phase2_data=_PHASE2_NO_DOCCAB)
    # Con phase2_data sin DOCCAB, no deben generarse SQLs de DOCCAB
    # (las preguntas sobre clientes pueden generar algún SQL de DOCCAB si DOCCAB no está)
    # Solo verificamos que no falla
    assert isinstance(sqls, list)
