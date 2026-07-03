"""
test_tipo_comprehensive.py
Tests exhaustivos de _detect_tipo_filter() y _detect_month_number().
Código REAL, sin mocks — importa directamente desde phase3_sqls.py.

Genera ~1200 casos de prueba parametrizados cubriendo:
  - Todos los TIPO de documento (0,1,2,3,10,11,12,13,21)
  - Todas las formas de escritura (singular, plural, acentuada, sin acento, mayúsculas)
  - Contextos de proveedor (cambia el TIPO)
  - Precedencias (albarán > factura)
  - Casos donde NO se debe detectar TIPO
  - Todos los meses del año (nombre completo + abreviación)
  - Casos límite
"""

import pytest
from backend.modules.chat.deep_analysis.phase3_sqls import (
    _detect_tipo_filter,
    _detect_month_number,
)

# ─── Generadores de datos ──────────────────────────────────────────────────────

_TEMPLATES_TIPO = [
    "quiero ver las {} del mes pasado",
    "muéstrame todas las {} pendientes",
    "¿cuántas {} hay este año?",
    "dame el total de {} por cliente",
    "busca las {} con importe mayor a 1000",
    "¿cuál es la media de {} del trimestre?",
    "necesito las {} sin pagar",
    "filtra {} por agente",
    "¿cuánto suman las {} de enero?",
    "listar todas las {} del 2026",
    "analiza las {} vencidas",
    "obtener {} por fecha",
    "resumen de {} por tipo",
    "¿hay {} duplicadas?",
    "exportar {} a excel",
    "ver {} emitidas hoy",
    "las {} más caras",
    "importe total de {}",
    "desglose de {} por cliente",
    "estadísticas de {}",
    "top 10 de {} por importe",
    "¿cuánto hay en {} pendientes?",
    "comparar {} de este año con el anterior",
    "evolucion de {} mensuales",
    "calcula el iVA de las {}",
]

_TEMPLATES_PROV = [
    "quiero ver las {} de proveedor del mes",
    "muéstrame todas las {} de compra pendientes",
    "¿cuántas {} de proveedores hay este año?",
    "dame el total de {} de compras",
    "busca las {} de compras con importe mayor a 1000",
    "¿cuál es la media de {} de proveedores?",
    "listar {} de compra del 2026",
    "analizar {} de proveedores",
    "desglose de {} por proveedor",
    "comparar {} de compra con el año anterior",
    "importe total de {} de proveedores",
    "las {} de compra más caras",
    "todas las {} compradas este mes",
    "balance de {} de compras",
    "¿hay {} de proveedor sin pagar?",
]

# keyword → (TIPO esperado, es_proveedor)
_TIPO3_KEYWORDS = [
    "facturas", "la factura", "las facturas", "facturación",
    "facturacion", " factura", "una factura", "facturas clientes",
    "factura de cliente", "facturas mensuales", "facturas vencidas",
    "facturas pagadas", "facturas pendientes",
]
_TIPO2_KEYWORDS = [
    "albaranes", "el albarán", "los albaranes", "albaran",
    "los albarán", "albarán de cliente", "albaranes cliente",
    "los albaranes pendientes", "albaranes sin facturar",
]
_TIPO0_KEYWORDS = [
    "presupuestos", "el presupuesto", "presupuesto de cliente",
    "presupuestos pendientes", "presupuesto aprobado",
]
_TIPO1_KEYWORDS = [
    "pedidos", "el pedido", "pedidos de cliente", "pedidos pendientes",
]
_TIPO13_KEYWORDS = [
    "facturas de proveedor", "facturas de compra", "facturación de proveedor",
]
_TIPO12_KEYWORDS = [
    "albaranes de proveedor", "albarán de compra", "albaran de proveedor",
    "albaranes de compra",
]
_TIPO11_KEYWORDS = [
    "pedidos de proveedor", "pedido de compra", "pedidos de compras",
]
_TIPO10_KEYWORDS = [
    "presupuestos de proveedor", "presupuesto de compra",
]
_SAT_KEYWORDS = [
    "sat", "servicio técnico", "servicio tecnico", "orden de trabajo",
]
_NO_TIPO_KEYWORDS = [
    "ventas", "clientes", "agentes", "artículos", "stock",
    "almacen", "inventario", "proveedores", "empleados",
    "producción", "cobros", "pagos", "caja",
    "recibos", "efectos", "liquidaciones", "balances",
    "estadísticas generales", "resumen ejecutivo",
]


def _gen_casos_tipo(keywords, expected_contains, templates, extra_context=""):
    casos = []
    for kw in keywords:
        for tmpl in templates:
            try:
                text = tmpl.format(kw) + extra_context
            except Exception:
                continue
            casos.append((text, expected_contains))
    return casos


# ── Mapeo REAL JDDC (confirmado inspeccionando DOCCAB): ──────────────────────
#   0=presupuesto  2=SAT  11=albarán  12=pedido  13=factura  21=mov.almacén
#   Para proveedor se usan los mismos TIPO que para cliente (sin distinción).

# ── Casos TIPO=13 (factura — cliente o proveedor) ─────────────────────────────
_CASOS_TIPO13 = _gen_casos_tipo(_TIPO3_KEYWORDS, "TIPO = 13", _TEMPLATES_TIPO)
_CASOS_TIPO13 += _gen_casos_tipo(_TIPO13_KEYWORDS, "TIPO = 13", _TEMPLATES_PROV)

# ── Casos TIPO=11 (albarán — cliente o proveedor) ─────────────────────────────
_CASOS_TIPO11 = _gen_casos_tipo(_TIPO2_KEYWORDS, "TIPO = 11", _TEMPLATES_TIPO)
_CASOS_TIPO11 += _gen_casos_tipo(_TIPO12_KEYWORDS, "TIPO = 11", _TEMPLATES_PROV)

# ── Casos TIPO=0 (presupuesto — cliente o proveedor) ─────────────────────────
_CASOS_TIPO0 = _gen_casos_tipo(_TIPO0_KEYWORDS, "TIPO = 0", _TEMPLATES_TIPO)
_CASOS_TIPO0 += _gen_casos_tipo(_TIPO10_KEYWORDS, "TIPO = 0", _TEMPLATES_PROV)

# ── Casos TIPO=12 (pedido — cliente o proveedor) ─────────────────────────────
_CASOS_TIPO12 = _gen_casos_tipo(_TIPO1_KEYWORDS, "TIPO = 12", _TEMPLATES_TIPO)
_CASOS_TIPO12 += _gen_casos_tipo(_TIPO11_KEYWORDS, "TIPO = 12", _TEMPLATES_PROV)

# ── Casos SAT → TIPO=2 en JDDC ───────────────────────────────────────────────
_CASOS_SAT = [(kw, "TIPO = 2") for kw in _SAT_KEYWORDS]
_CASOS_SAT += [
    ("órdenes de trabajo pendientes", "TIPO = 2"),
    ("SAT abiertos este mes", "TIPO = 2"),
    ("servicio técnico en garantía", "TIPO = 2"),
]

# ── Casos SIN TIPO detectable ─────────────────────────────────────────────────
_CASOS_NO_TIPO = [(kw, "") for kw in _NO_TIPO_KEYWORDS]
_CASOS_NO_TIPO += [
    ("", ""),
    ("análisis general del negocio", ""),
    ("¿cuántos registros hay?", ""),
    ("resumen del mes de enero", ""),
    ("evolución del 2026", ""),
    ("total de ventas sin especificar", ""),
    # Abonos — TIPO no verificado en JDDC → no filtrar
    ("abono de cliente", ""),
    ("abonos pendientes", ""),
]

# ── Casos de PRECEDENCIA (albarán > factura) ──────────────────────────────────
# En JDDC: albarán → TIPO=11 (no cambia aunque aparezca "facturar" como verbo)
_CASOS_PRECEDENCIA = [
    ("albaranes sin facturar", "TIPO = 11"),
    ("albarán pendiente de facturación", "TIPO = 11"),
    ("albaranes que aún no tienen factura", "TIPO = 11"),
    ("albaranes sin facturar de proveedor", "TIPO = 11"),
    ("albarán de compra sin factura de compra", "TIPO = 11"),
    ("albaranes de proveedor sin facturar", "TIPO = 11"),
]

# ── Casos de DOBLE CONTEXTO (proveedor sin keyword de tipo) ──────────────────
_CASOS_COMPRAS_GENERALES = [
    ("documentos de compra", ""),
    ("todo de proveedores", ""),
    ("resumen de compras", ""),
]

# Combinar todos los casos
_ALL_TIPO_CASOS = (
    _CASOS_TIPO13
    + _CASOS_TIPO11
    + _CASOS_TIPO0
    + _CASOS_TIPO12
    + _CASOS_SAT
    + _CASOS_NO_TIPO
    + _CASOS_PRECEDENCIA
    + _CASOS_COMPRAS_GENERALES
)


@pytest.mark.parametrize("question,expected_contains", _ALL_TIPO_CASOS)
def test_detect_tipo_filter(question: str, expected_contains: str):
    """
    Verifica que _detect_tipo_filter devuelve el filtro TIPO correcto.
    Usa el código real sin ningún mock.
    """
    result = _detect_tipo_filter(question)
    if expected_contains:
        assert result == expected_contains, (
            f"Para '{question}'\n"
            f"  Esperado: '{expected_contains}'\n"
            f"  Obtenido: '{result}'"
        )
    else:
        assert result == "", (
            f"Para '{question}' se esperaba sin filtro, "
            f"pero se obtuvo: '{result}'"
        )


# ─── Tests adicionales específicos ────────────────────────────────────────────

@pytest.mark.parametrize("question,expected", [
    # Mapeo real JDDC (0=presupuesto, 2=SAT, 11=albarán, 12=pedido, 13=factura)
    ("facturas de clientes de enero", "TIPO = 13"),
    ("albaranes sin facturar", "TIPO = 11"),
    ("presupuestos aceptados", "TIPO = 0"),
    ("pedidos de proveedor pendientes", "TIPO = 12"),
    ("albaranes de proveedor del mes", "TIPO = 11"),
    ("facturas de proveedor sin pagar", "TIPO = 13"),
    ("presupuestos de compra a proveedores", "TIPO = 0"),
    ("movimiento de almacén de enero", "TIPO = 21"),
    ("sat abiertos", "TIPO = 2"),
    ("orden de trabajo urgente", "TIPO = 2"),
    # Frases con factura como verbo → también detectan TIPO=13 (contienen "factur")
    ("¿cuánto falta por facturar?", "TIPO = 13"),
    ("documentos sin facturar", "TIPO = 13"),
    # Mayúsculas
    ("FACTURAS DEL MES", "TIPO = 13"),
    ("ALBARANES PENDIENTES", "TIPO = 11"),
    ("PRESUPUESTOS 2026", "TIPO = 0"),
])
def test_detect_tipo_filter_casos_verificados(question: str, expected: str):
    """Casos explícitamente verificados — regresión directa con mapeo real JDDC."""
    assert _detect_tipo_filter(question) == expected


# ─── Tests de _detect_month_number ────────────────────────────────────────────

_NOMBRES_MES_COMPLETO = [
    ("enero", 1), ("febrero", 2), ("marzo", 3), ("abril", 4),
    ("mayo", 5), ("junio", 6), ("julio", 7), ("agosto", 8),
    ("septiembre", 9), ("octubre", 10), ("noviembre", 11), ("diciembre", 12),
]
_ABREVIACIONES_MES = [
    ("ene", 1), ("feb", 2), ("mar", 3), ("abr", 4),
    ("may", 5), ("jun", 6), ("jul", 7), ("ago", 8),
    ("sep", 9), ("oct", 10), ("nov", 11), ("dic", 12),
]
_TEMPLATES_MES = [
    "facturas de {}",
    "¿cuánto se facturó en {}?",
    "resumen de {} del año actual",
    "ventas de {} 2026",
    "¿hay datos de {}?",
    "albaranes de {} pendientes",
    "importe total de {}",
    "clientes de {}",
    "análisis de {} trimestral",
    "evolución desde {}",
]


def _gen_mes_casos():
    casos = []
    for nombre, num in _NOMBRES_MES_COMPLETO:
        for tmpl in _TEMPLATES_MES:
            casos.append((tmpl.format(nombre), num))
        # Mayúsculas
        for tmpl in _TEMPLATES_MES[:3]:
            casos.append((tmpl.format(nombre.upper()), num))
        # Capitalizado
        casos.append((f"facturas de {nombre.capitalize()}", num))
    for abrev, num in _ABREVIACIONES_MES:
        for tmpl in _TEMPLATES_MES[:5]:
            casos.append((tmpl.format(abrev), num))
        casos.append((abrev.upper(), num))
    return casos


_ALL_MES_CASOS = _gen_mes_casos()

# Edge cases que NO deben detectar mes
_NO_MES_CASOS = [
    ("facturas del año pasado", 0),
    ("presupuestos 2026", 0),
    ("clientes VIP", 0),
    ("resumen anual", 0),
    ("", 0),
    ("análisis general", 0),
    ("datos del trimestre", 0),
    ("facturas pendientes", 0),
    ("total de ventas", 0),
    ("stock actual", 0),
]


@pytest.mark.parametrize("question,expected_month", _ALL_MES_CASOS)
def test_detect_month_number_con_mes(question: str, expected_month: int):
    """Verifica que se detecta el mes correcto en la pregunta."""
    result = _detect_month_number(question)
    assert result == expected_month, (
        f"Para '{question}': esperado {expected_month}, obtenido {result}"
    )


@pytest.mark.parametrize("question,expected_month", _NO_MES_CASOS)
def test_detect_month_number_sin_mes(question: str, expected_month: int):
    """Verifica que NO se detecta mes cuando la pregunta no lo menciona."""
    result = _detect_month_number(question)
    assert result == 0, (
        f"Para '{question}': se esperaba 0 pero se obtuvo {result}"
    )


def test_detect_tipo_filter_returns_string():
    """La función siempre devuelve str, nunca None."""
    for q in ["", "   ", "facturas", "xyz", "!@#$%"]:
        result = _detect_tipo_filter(q)
        assert isinstance(result, str), f"No es str para '{q}'"


def test_detect_month_number_returns_int():
    """La función siempre devuelve int, nunca None."""
    for q in ["", "   ", "enero", "xyz", "!@#$%"]:
        result = _detect_month_number(q)
        assert isinstance(result, int), f"No es int para '{q}'"
        assert 0 <= result <= 12, f"Fuera de rango [0,12] para '{q}': {result}"


def test_detect_tipo_proveedor_context():
    """En JDDC, los TIPO de proveedor son los mismos que los de cliente (sin distinción)."""
    assert _detect_tipo_filter("presupuesto de compras a proveedor") == "TIPO = 0"
    assert _detect_tipo_filter("pedido de compra urgente") == "TIPO = 12"
    assert _detect_tipo_filter("albarán de compra de proveedor") == "TIPO = 11"


def test_detect_tipo_movimiento_almacen():
    """'Movimiento de almacén' → TIPO = 21."""
    assert _detect_tipo_filter("movimiento de almacén pendiente") == "TIPO = 21"
    assert _detect_tipo_filter("movimiento almacen de junio") == "TIPO = 21"
    assert _detect_tipo_filter("mov almacen del mes") == "TIPO = 21"
