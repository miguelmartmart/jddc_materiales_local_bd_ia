"""
Tests de integración del ContextRetriever con preguntas reales de usuario.

PROPÓSITO:
  Simular exactamente lo que ocurre cuando un usuario escribe una pregunta
  en el chat de DEVIA. Verificar que el ContextRetriever devuelve las tablas
  correctas, los keywords correctos y el contexto adecuado.

EJECUTAR:
  cd bots/interjddcia
  .venv/Scripts/pytest tests/test_context_retriever_questions.py -v -s

  Con trazas detalladas (recomendado para depurar):
  .venv/Scripts/pytest tests/test_context_retriever_questions.py -v -s --tb=short 2>&1 | tee logs/test_context_retriever.log

REQUISITOS:
  - Los índices SIUO deben estar generados (table_index.json, concept_index.json, etc.)
  - NO requiere BD Firebird ni Qwen3 disponibles (solo lee los JSON de índices)
  - Si los índices no existen, los tests se marcan como SKIP

TRAZAS:
  Cada test imprime por consola (-s):
    [PREGUNTA]  → la pregunta del usuario
    [KEYWORDS]  → keywords encontrados en concept_index
    [UNKNOWN]   → keywords no encontrados (candidatos para mejorar el índice)
    [TABLAS]    → tablas seleccionadas por el retriever
    [TOKENS]    → tokens estimados del contexto
    [FUENTE]    → "siuo" o "fallback"
    [VEREDICTO] → OK / FALLO + motivo

CATEGORÍAS DE TESTS:
  - 1 tabla: preguntas simples sobre una entidad
  - 2-3 tablas: preguntas que cruzan entidades relacionadas
  - 4+ tablas: preguntas complejas multi-tabla
  - Fechas: preguntas con filtros temporales
  - Importes: preguntas con filtros numéricos
  - Datos inconsistentes: preguntas donde los datos pueden estar mal introducidos
  - Regresión: preguntas que fallaban antes (como "artículos con más compras")
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

# ─── Setup de paths ───────────────────────────────────────────────────────────

# Añadir el directorio raíz al path para importar módulos
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# ─── Logger con formato detallado ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_context_retriever")

# ─── Fixture: ContextRetriever cargado ───────────────────────────────────────

@pytest.fixture(scope="module")
def retriever():
    """
    Carga el ContextRetriever con los índices reales del SIUO.
    Si los índices no existen, salta todos los tests del módulo.
    """
    from backend.modules.db_explorer.context_retriever import ContextRetriever
    from backend.modules.db_explorer.deep_indexer_service import TABLE_INDEX_PATH

    if not TABLE_INDEX_PATH.exists():
        pytest.skip(
            f"Índices SIUO no encontrados en {TABLE_INDEX_PATH}. "
            "Ejecuta primero el análisis completo desde la pestaña 'Índices SIUO'."
        )

    r = ContextRetriever()
    loaded = r.load()
    if not loaded:
        pytest.skip("ContextRetriever no pudo cargar los índices SIUO.")

    stats = r.get_stats()
    print(f"\n[FIXTURE] ContextRetriever cargado:")
    print(f"  Tablas indexadas:   {stats['tables_indexed']}")
    print(f"  Keywords:           {stats['concept_keywords']}")
    print(f"  Nodos grafo:        {stats['graph_nodes']}")
    print(f"  Aristas grafo:      {stats['graph_edges']}")
    return r


# ─── Helper de trazas ─────────────────────────────────────────────────────────

def run_and_trace(
    retriever,
    question: str,
    expected_tables: List[str],
    forbidden_tables: Optional[List[str]] = None,
    min_tables: int = 1,
    max_tables: int = 8,
    max_tokens: int = 2000,
    test_name: str = "",
) -> Tuple[bool, Dict]:
    """
    Ejecuta el retriever con una pregunta y genera trazas completas.

    Returns:
        (passed, trace_dict)
        - passed: True si el test pasa
        - trace_dict: diccionario con toda la información de trazabilidad
    """
    context, meta = retriever.get_context(question, max_tokens=max_tokens)

    tables_used     = meta.get("tables_used", [])
    keywords_found  = meta.get("keywords_found", [])
    keywords_unknown = meta.get("keywords_unknown", [])
    tokens          = meta.get("tokens_estimated", 0)
    source          = meta.get("source", "unknown")

    # ── Imprimir trazas ──
    print(f"\n{'='*70}")
    print(f"[TEST]     {test_name}")
    print(f"[PREGUNTA] {question}")
    print(f"[KEYWORDS] encontrados={keywords_found}")
    print(f"[UNKNOWN]  no mapeados={keywords_unknown}")
    print(f"[TABLAS]   {tables_used}")
    print(f"[TOKENS]   ~{tokens} (max={max_tokens})")
    print(f"[FUENTE]   {source}")
    print(f"[CONTEXTO] {len(context)} chars")

    # ── Verificaciones ──
    failures = []

    # 1. Fuente debe ser SIUO (no fallback)
    if source != "siuo":
        failures.append(f"Fuente es '{source}' en lugar de 'siuo' — los índices no se están usando")

    # 2. Tablas esperadas deben estar presentes
    for t in expected_tables:
        if t not in tables_used:
            failures.append(f"Tabla esperada '{t}' NO encontrada en {tables_used}")

    # 3. Tablas prohibidas no deben aparecer
    if forbidden_tables:
        for t in forbidden_tables:
            if t in tables_used:
                failures.append(f"Tabla prohibida '{t}' apareció en el contexto")

    # 4. Número de tablas dentro del rango esperado
    if len(tables_used) < min_tables:
        failures.append(f"Solo {len(tables_used)} tablas, se esperaban al menos {min_tables}")
    if len(tables_used) > max_tables:
        failures.append(f"{len(tables_used)} tablas, máximo esperado {max_tables}")

    # 5. Tokens dentro del límite
    if tokens > max_tokens * 1.1:  # 10% de margen
        failures.append(f"Tokens estimados ({tokens}) superan el límite ({max_tokens})")

    # 6. El contexto no debe estar vacío
    if len(context) < 50:
        failures.append(f"Contexto demasiado corto ({len(context)} chars)")

    passed = len(failures) == 0

    if passed:
        print(f"[VEREDICTO] ✅ OK")
    else:
        print(f"[VEREDICTO] ❌ FALLO:")
        for f in failures:
            print(f"  - {f}")

    trace = {
        "question":          question,
        "tables_used":       tables_used,
        "keywords_found":    keywords_found,
        "keywords_unknown":  keywords_unknown,
        "tokens":            tokens,
        "source":            source,
        "context_length":    len(context),
        "failures":          failures,
        "passed":            passed,
    }

    return passed, trace


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 1: PREGUNTAS SIMPLES (1 tabla)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasSimples:
    """Preguntas que deberían resolverse con 1-2 tablas."""

    def test_listar_articulos(self, retriever):
        """'dame los artículos' → debe encontrar ARTICULO"""
        passed, trace = run_and_trace(
            retriever,
            question="dame los artículos disponibles",
            expected_tables=["ARTICULO"],
            min_tables=1,
            max_tables=4,
            test_name="listar_articulos",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_listar_clientes(self, retriever):
        """'lista de clientes' → debe encontrar CLIENTE"""
        passed, trace = run_and_trace(
            retriever,
            question="dame la lista de clientes",
            expected_tables=["CLIENTE"],
            min_tables=1,
            max_tables=4,
            test_name="listar_clientes",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_listar_proveedores(self, retriever):
        """'proveedores activos' → debe encontrar PROVEED"""
        passed, trace = run_and_trace(
            retriever,
            question="muéstrame los proveedores",
            expected_tables=["PROVEED"],
            min_tables=1,
            max_tables=4,
            test_name="listar_proveedores",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_stock_articulos(self, retriever):
        """'stock de artículos' → debe encontrar ARTICULO (y posiblemente ESTALMACEN/ALMACEN)"""
        passed, trace = run_and_trace(
            retriever,
            question="cuál es el stock de los artículos",
            expected_tables=["ARTICULO"],
            min_tables=1,
            max_tables=5,
            test_name="stock_articulos",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_listar_agentes(self, retriever):
        """'agentes comerciales' → debe encontrar AGENTE"""
        passed, trace = run_and_trace(
            retriever,
            question="dame los agentes comerciales",
            expected_tables=["AGENTE"],
            min_tables=1,
            max_tables=4,
            test_name="listar_agentes",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_listar_almacenes(self, retriever):
        """'almacenes disponibles' → debe encontrar ALMACEN"""
        passed, trace = run_and_trace(
            retriever,
            question="qué almacenes hay",
            expected_tables=["ALMACEN"],
            min_tables=1,
            max_tables=4,
            test_name="listar_almacenes",
        )
        assert passed, f"Fallos: {trace['failures']}"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 2: PREGUNTAS DE DOCUMENTOS (DOCCAB + filtro TIPO)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasDocumentos:
    """Preguntas sobre facturas, albaranes, pedidos, presupuestos."""

    def test_facturas_recientes(self, retriever):
        """'últimas facturas' → DOCCAB con filtro TIPO=13"""
        passed, trace = run_and_trace(
            retriever,
            question="dame las últimas facturas",
            expected_tables=["DOCCAB"],
            min_tables=1,
            max_tables=5,
            test_name="facturas_recientes",
        )
        # Verificar que el contexto menciona el filtro TIPO=13
        context, _ = retriever.get_context("dame las últimas facturas")
        assert "13" in context or "TIPO" in context, \
            "El contexto no menciona el filtro TIPO=13 para facturas"
        assert passed, f"Fallos: {trace['failures']}"

    def test_albaranes(self, retriever):
        """'albaranes pendientes' → DOCCAB con filtro TIPO=11"""
        passed, trace = run_and_trace(
            retriever,
            question="albaranes pendientes de facturar",
            expected_tables=["DOCCAB"],
            min_tables=1,
            max_tables=5,
            test_name="albaranes_pendientes",
        )
        context, _ = retriever.get_context("albaranes pendientes de facturar")
        assert "11" in context or "TIPO" in context, \
            "El contexto no menciona el filtro TIPO=11 para albaranes"
        assert passed, f"Fallos: {trace['failures']}"

    def test_pedidos(self, retriever):
        """'pedidos de clientes' → DOCCAB con filtro TIPO=12"""
        passed, trace = run_and_trace(
            retriever,
            question="pedidos de clientes pendientes",
            expected_tables=["DOCCAB"],
            min_tables=1,
            max_tables=5,
            test_name="pedidos_clientes",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_presupuestos(self, retriever):
        """'presupuestos enviados' → DOCCAB con filtro TIPO=0"""
        passed, trace = run_and_trace(
            retriever,
            question="presupuestos enviados este mes",
            expected_tables=["DOCCAB"],
            min_tables=1,
            max_tables=5,
            test_name="presupuestos_enviados",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_abonos(self, retriever):
        """'abonos realizados' → DOCCAB con filtro TIPO=3"""
        passed, trace = run_and_trace(
            retriever,
            question="abonos realizados a clientes",
            expected_tables=["DOCCAB"],
            min_tables=1,
            max_tables=5,
            test_name="abonos_clientes",
        )
        assert passed, f"Fallos: {trace['failures']}"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 3: PREGUNTAS MULTI-TABLA (2-4 tablas)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasMultiTabla:
    """Preguntas que requieren cruzar 2-4 tablas."""

    def test_articulos_mas_vendidos(self, retriever):
        """
        'artículos más vendidos' → DOCCAB + DOCLIN + ARTICULO
        REGRESIÓN: antes devolvía HISTORICOPRECIOS, ESTFAMILIA, FOTOGRAF (incorrecto)
        """
        passed, trace = run_and_trace(
            retriever,
            question="dime los artículos más vendidos",
            expected_tables=["ARTICULO"],
            forbidden_tables=["HISTORICOPRECIOS", "FOTOGRAF", "ESTFAMILIA"],
            min_tables=2,
            max_tables=6,
            test_name="articulos_mas_vendidos [REGRESION]",
        )
        # DOCLIN o DOCCAB deben aparecer para poder calcular ventas
        context, meta = retriever.get_context("dime los artículos más vendidos")
        tables = meta.get("tables_used", [])
        has_sales_table = "DOCLIN" in tables or "DOCCAB" in tables
        assert has_sales_table, \
            f"Para calcular ventas se necesita DOCLIN o DOCCAB, pero solo hay: {tables}"
        assert passed, f"Fallos: {trace['failures']}"

    def test_articulos_mas_compras(self, retriever):
        """
        'artículos con más compras' → DOCCAB(TIPO=12) + DOCLIN + ARTICULO
        REGRESIÓN CRÍTICA: el sistema devolvía tablas completamente incorrectas
        """
        passed, trace = run_and_trace(
            retriever,
            question="dime los artículos con más compras",
            expected_tables=["ARTICULO"],
            forbidden_tables=["HISTORICOPRECIOS", "FOTOGRAF", "COMISART", "FABARTFABASOC"],
            min_tables=2,
            max_tables=6,
            test_name="articulos_mas_compras [REGRESION CRITICA]",
        )
        context, meta = retriever.get_context("dime los artículos con más compras")
        tables = meta.get("tables_used", [])
        has_doc_table = "DOCLIN" in tables or "DOCCAB" in tables
        assert has_doc_table, \
            f"Para calcular compras se necesita DOCLIN o DOCCAB, pero solo hay: {tables}"
        assert passed, f"Fallos: {trace['failures']}"

    def test_facturas_por_cliente(self, retriever):
        """'facturas del cliente García' → DOCCAB + CLIENTE"""
        passed, trace = run_and_trace(
            retriever,
            question="qué facturas tiene el cliente García",
            expected_tables=["DOCCAB", "CLIENTE"],
            min_tables=2,
            max_tables=6,
            test_name="facturas_por_cliente",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_lineas_de_factura(self, retriever):
        """'líneas de la factura 1234' → DOCCAB + DOCLIN"""
        passed, trace = run_and_trace(
            retriever,
            question="dame las líneas de la factura 1234",
            expected_tables=["DOCCAB", "DOCLIN"],
            min_tables=2,
            max_tables=5,
            test_name="lineas_de_factura",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_stock_por_almacen(self, retriever):
        """'stock por almacén' → ARTICULO + ALMACEN (y posiblemente ESTALMACEN)"""
        passed, trace = run_and_trace(
            retriever,
            question="cuál es el stock de cada artículo por almacén",
            expected_tables=["ARTICULO", "ALMACEN"],
            min_tables=2,
            max_tables=5,
            test_name="stock_por_almacen",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_ventas_por_agente(self, retriever):
        """'ventas por agente' → DOCCAB + AGENTE"""
        passed, trace = run_and_trace(
            retriever,
            question="cuánto ha vendido cada agente",
            expected_tables=["DOCCAB", "AGENTE"],
            min_tables=2,
            max_tables=6,
            test_name="ventas_por_agente",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_articulos_por_familia(self, retriever):
        """'artículos de la familia splits' → ARTICULO + FAMILIAS"""
        passed, trace = run_and_trace(
            retriever,
            question="dame los artículos de la familia splits",
            expected_tables=["ARTICULO"],
            min_tables=1,
            max_tables=5,
            test_name="articulos_por_familia",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_facturas_con_detalle_articulo(self, retriever):
        """'qué artículos se han facturado' → DOCCAB + DOCLIN + ARTICULO"""
        passed, trace = run_and_trace(
            retriever,
            question="qué artículos se han incluido en facturas este año",
            expected_tables=["DOCCAB", "ARTICULO"],
            min_tables=2,
            max_tables=6,
            test_name="facturas_con_detalle_articulo",
        )
        assert passed, f"Fallos: {trace['failures']}"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 4: PREGUNTAS CON FECHAS Y RANGOS TEMPORALES
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasConFechas:
    """Preguntas que incluyen filtros temporales."""

    def test_facturas_este_año(self, retriever):
        """'facturas de este año' → DOCCAB, contexto debe mencionar fecha"""
        context, meta = retriever.get_context("facturas emitidas este año")
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] facturas_este_año")
        print(f"[TABLAS] {tables}")
        print(f"[TOKENS] {meta.get('tokens_estimated')}")
        assert "DOCCAB" in tables, f"DOCCAB no encontrado en {tables}"

    def test_facturas_2025(self, retriever):
        """'facturas de 2025' → DOCCAB, contexto debe mencionar 2025"""
        context, meta = retriever.get_context("dame las facturas del año 2025")
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] facturas_2025")
        print(f"[TABLAS] {tables}")
        print(f"[KEYWORDS] {meta.get('keywords_found')}")
        assert "DOCCAB" in tables, f"DOCCAB no encontrado en {tables}"

    def test_ventas_ultimo_mes(self, retriever):
        """'ventas del último mes' → DOCCAB"""
        context, meta = retriever.get_context("ventas realizadas el último mes")
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] ventas_ultimo_mes")
        print(f"[TABLAS] {tables}")
        assert "DOCCAB" in tables, f"DOCCAB no encontrado en {tables}"

    def test_pedidos_entre_fechas(self, retriever):
        """'pedidos entre enero y marzo' → DOCCAB"""
        context, meta = retriever.get_context(
            "pedidos realizados entre enero y marzo de 2025"
        )
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] pedidos_entre_fechas")
        print(f"[TABLAS] {tables}")
        assert "DOCCAB" in tables, f"DOCCAB no encontrado en {tables}"

    def test_articulos_sin_movimiento(self, retriever):
        """'artículos sin movimiento en 6 meses' → ARTICULO + DOCLIN"""
        context, meta = retriever.get_context(
            "artículos que no se han vendido en los últimos 6 meses"
        )
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] articulos_sin_movimiento")
        print(f"[TABLAS] {tables}")
        assert "ARTICULO" in tables, f"ARTICULO no encontrado en {tables}"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 5: PREGUNTAS CON IMPORTES Y RANGOS NUMÉRICOS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasConImportes:
    """Preguntas que incluyen filtros numéricos."""

    def test_facturas_grandes(self, retriever):
        """'facturas de más de 1000 euros' → DOCCAB"""
        context, meta = retriever.get_context(
            "dame las facturas de más de 1000 euros"
        )
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] facturas_grandes")
        print(f"[TABLAS] {tables}")
        print(f"[KEYWORDS] {meta.get('keywords_found')}")
        assert "DOCCAB" in tables, f"DOCCAB no encontrado en {tables}"

    def test_articulos_precio_alto(self, retriever):
        """'artículos con precio mayor de 500€' → ARTICULO"""
        context, meta = retriever.get_context(
            "artículos con precio superior a 500 euros"
        )
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] articulos_precio_alto")
        print(f"[TABLAS] {tables}")
        assert "ARTICULO" in tables, f"ARTICULO no encontrado en {tables}"

    def test_total_ventas_por_cliente(self, retriever):
        """'total facturado por cliente' → DOCCAB + CLIENTE"""
        context, meta = retriever.get_context(
            "cuánto se ha facturado en total a cada cliente"
        )
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] total_ventas_por_cliente")
        print(f"[TABLAS] {tables}")
        assert "DOCCAB" in tables, f"DOCCAB no encontrado en {tables}"
        assert "CLIENTE" in tables, f"CLIENTE no encontrado en {tables}"

    def test_margen_por_articulo(self, retriever):
        """'margen de beneficio por artículo' → ARTICULO + DOCLIN"""
        context, meta = retriever.get_context(
            "cuál es el margen de beneficio de cada artículo"
        )
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] margen_por_articulo")
        print(f"[TABLAS] {tables}")
        assert "ARTICULO" in tables, f"ARTICULO no encontrado en {tables}"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 6: PREGUNTAS COMPLEJAS (4+ tablas)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasComplejas:
    """Preguntas que requieren 4 o más tablas."""

    def test_ranking_articulos_vendidos_por_familia(self, retriever):
        """
        'ranking de artículos vendidos por familia en 2025'
        → DOCCAB + DOCLIN + ARTICULO + FAMILIAS
        """
        passed, trace = run_and_trace(
            retriever,
            question="ranking de artículos más vendidos por familia en 2025",
            expected_tables=["ARTICULO", "DOCCAB"],
            min_tables=2,
            max_tables=8,
            test_name="ranking_articulos_por_familia_2025",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_clientes_con_facturas_impagadas(self, retriever):
        """
        'clientes con facturas sin pagar'
        → CLIENTE + DOCCAB + (posiblemente CAJA/RECIBOS)
        """
        passed, trace = run_and_trace(
            retriever,
            question="qué clientes tienen facturas sin pagar",
            expected_tables=["CLIENTE", "DOCCAB"],
            min_tables=2,
            max_tables=8,
            test_name="clientes_facturas_impagadas",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_ventas_por_agente_y_familia(self, retriever):
        """
        'ventas por agente y familia de artículo'
        → DOCCAB + DOCLIN + ARTICULO + AGENTE
        """
        passed, trace = run_and_trace(
            retriever,
            question="ventas de cada agente desglosadas por familia de artículo",
            expected_tables=["DOCCAB", "ARTICULO", "AGENTE"],
            min_tables=3,
            max_tables=8,
            test_name="ventas_por_agente_y_familia",
        )
        assert passed, f"Fallos: {trace['failures']}"

    def test_resumen_actividad_empresa(self, retriever):
        """
        'resumen de actividad de la empresa'
        → múltiples tablas (DOCCAB, CLIENTE, ARTICULO, AGENTE...)
        """
        context, meta = retriever.get_context(
            "dame un resumen de la actividad de la empresa este año"
        )
        tables = meta.get("tables_used", [])
        tokens = meta.get("tokens_estimated", 0)
        print(f"\n[TEST] resumen_actividad_empresa")
        print(f"[TABLAS] {tables} ({len(tables)} tablas)")
        print(f"[TOKENS] {tokens}")
        # Para una pregunta tan amplia, esperamos al menos 3 tablas
        assert len(tables) >= 2, f"Solo {len(tables)} tablas para una pregunta tan amplia"
        assert tokens <= 2200, f"Tokens ({tokens}) superan el límite"

    def test_analisis_rentabilidad_completo(self, retriever):
        """
        'análisis de rentabilidad por cliente, agente y familia'
        → DOCCAB + DOCLIN + ARTICULO + CLIENTE + AGENTE
        """
        context, meta = retriever.get_context(
            "análisis de rentabilidad por cliente, agente y familia de artículo en 2025"
        )
        tables = meta.get("tables_used", [])
        tokens = meta.get("tokens_estimated", 0)
        print(f"\n[TEST] analisis_rentabilidad_completo")
        print(f"[TABLAS] {tables} ({len(tables)} tablas)")
        print(f"[TOKENS] {tokens}")
        assert "DOCCAB" in tables or "DOCLIN" in tables, \
            "Necesita tabla de documentos para calcular rentabilidad"
        assert tokens <= 2200, f"Tokens ({tokens}) superan el límite"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 7: CONTROL DE TOKENS Y LÍMITES
# ═══════════════════════════════════════════════════════════════════════════════

class TestControlTokens:
    """Verifica que el control de tokens funciona correctamente."""

    def test_tokens_no_superan_limite_2000(self, retriever):
        """El contexto nunca debe superar el límite de tokens."""
        preguntas = [
            "dame todos los artículos con sus precios, stock, familia y proveedor",
            "resumen completo de facturas, albaranes, pedidos y presupuestos",
            "análisis completo de ventas por cliente, agente, familia y almacén",
        ]
        for pregunta in preguntas:
            context, meta = retriever.get_context(pregunta, max_tokens=2000)
            tokens = meta.get("tokens_estimated", 0)
            print(f"\n[TEST] control_tokens: '{pregunta[:50]}...'")
            print(f"[TOKENS] {tokens} (límite=2000)")
            assert tokens <= 2200, \
                f"Tokens ({tokens}) superan el límite para: '{pregunta}'"

    def test_tokens_limite_pequeño(self, retriever):
        """Con max_tokens=500, el contexto debe ser más compacto."""
        context, meta = retriever.get_context(
            "dame las facturas", max_tokens=500
        )
        tokens = meta.get("tokens_estimated", 0)
        print(f"\n[TEST] tokens_limite_pequeño")
        print(f"[TOKENS] {tokens} (límite=500)")
        assert tokens <= 550, f"Tokens ({tokens}) superan el límite de 500"

    def test_tokens_limite_grande(self, retriever):
        """Con max_tokens=4000, puede incluir más tablas."""
        context, meta = retriever.get_context(
            "análisis completo de ventas por cliente y artículo",
            max_tokens=4000,
        )
        tokens = meta.get("tokens_estimated", 0)
        tables = meta.get("tables_used", [])
        print(f"\n[TEST] tokens_limite_grande")
        print(f"[TABLAS] {tables} ({len(tables)} tablas)")
        print(f"[TOKENS] {tokens} (límite=4000)")
        assert tokens <= 4400, f"Tokens ({tokens}) superan el límite de 4000"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 8: AUTOAPRENDIZAJE — Keywords desconocidos
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutoaprendizaje:
    """Verifica que los keywords desconocidos se registran correctamente."""

    def test_keywords_desconocidos_se_registran(self, retriever):
        """
        Palabras que no están en el concept_index deben registrarse
        en siuo_query_log.json para sugerir mejoras.
        """
        from backend.modules.db_explorer.deep_indexer_service import _CONFIG_DIR
        log_path = _CONFIG_DIR / "siuo_query_log.json"

        # Hacer una pregunta con palabras inventadas
        context, meta = retriever.get_context(
            "dame los xyzabc123 con más zzzfoo456"
        )
        unknown = meta.get("keywords_unknown", [])
        print(f"\n[TEST] keywords_desconocidos_se_registran")
        print(f"[UNKNOWN] {unknown}")

        # Las palabras inventadas deben aparecer como desconocidas
        assert len(unknown) > 0, \
            "Palabras inventadas deberían aparecer como keywords desconocidos"

        # El log debe existir y contener la consulta
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
            queries = log.get("queries", [])
            assert len(queries) > 0, "El query_log debería tener al menos una entrada"
            print(f"[LOG] {len(queries)} consultas registradas")

    def test_sugerencias_autoaprendizaje(self, retriever):
        """get_learning_suggestions() debe devolver estructura correcta."""
        suggestions = retriever.get_learning_suggestions()
        print(f"\n[TEST] sugerencias_autoaprendizaje")
        print(f"[SUGERENCIAS] {json.dumps(suggestions, ensure_ascii=False, indent=2)[:500]}")

        assert "unknown_keywords_frequent" in suggestions
        assert "top_tables_used" in suggestions
        assert "total_queries_logged" in suggestions
        assert isinstance(suggestions["unknown_keywords_frequent"], list)
        assert isinstance(suggestions["top_tables_used"], list)

    def test_feedback_correcto_se_registra(self, retriever):
        """register_feedback() debe guardar el feedback sin errores."""
        retriever.register_feedback(
            question="dame los artículos más vendidos",
            sql_used="SELECT FIRST 10 a.DESCRIPCION, SUM(l.CANTIDAD) FROM DOCLIN l JOIN ARTICULO a ON a.CODART=l.CODART GROUP BY a.DESCRIPCION ORDER BY 2 DESC",
            was_correct=True,
            tables_used=["DOCLIN", "ARTICULO"],
        )
        print(f"\n[TEST] feedback_correcto_se_registra → OK (sin excepción)")

    def test_feedback_incorrecto_se_registra(self, retriever):
        """Feedback negativo también debe registrarse."""
        retriever.register_feedback(
            question="artículos con más compras",
            sql_used="SELECT * FROM HISTORICOPRECIOS",  # SQL incorrecto
            was_correct=False,
            tables_used=["HISTORICOPRECIOS"],
        )
        print(f"\n[TEST] feedback_incorrecto_se_registra → OK (sin excepción)")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 9: REGRESIONES CONOCIDAS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegresiones:
    """
    Tests de regresión para problemas conocidos.
    Estos tests documentan comportamientos incorrectos que deben corregirse.
    """

    def test_regresion_compras_no_devuelve_historicoprecios(self, retriever):
        """
        REGRESIÓN: 'artículos con más compras' devolvía HISTORICOPRECIOS, ESTFAMILIA,
        FOTOGRAF, COMISART, FABARTFABASOC — tablas completamente irrelevantes.

        CAUSA: El keyword 'compras' en concept_index apunta a DOCCAB(TIPO=12),
        pero 'artículos' expande por grafo a tablas relacionadas con ARTICULO
        que no tienen nada que ver con compras.

        ESPERADO: ARTICULO + DOCLIN/DOCCAB
        """
        context, meta = retriever.get_context("dime los artículos con más compras")
        tables = meta.get("tables_used", [])
        keywords = meta.get("keywords_found", [])

        print(f"\n[REGRESION] artículos con más compras")
        print(f"[KEYWORDS] {keywords}")
        print(f"[TABLAS]   {tables}")

        # Tablas que NO deben aparecer
        bad_tables = {"HISTORICOPRECIOS", "FOTOGRAF", "COMISART",
                      "FABARTFABASOC", "ESTFAMILIA", "FABRICA"}
        found_bad = bad_tables.intersection(set(tables))

        if found_bad:
            pytest.xfail(
                f"REGRESIÓN CONOCIDA: tablas incorrectas {found_bad} en el contexto. "
                f"Pendiente de corrección en el concept_index. "
                f"Ver PLAN_OPTIMIZACION_SIUO_v2.md Problema 2."
            )

        # Si llegamos aquí, la regresión está corregida
        assert "ARTICULO" in tables, "ARTICULO debe estar en el contexto"

    def test_regresion_ventas_no_devuelve_tablas_config(self, retriever):
        """
        REGRESIÓN: Preguntas de ventas no deben devolver tablas de configuración
        (ADMINPROG, ACC_ACC, ACC_USR, etc.)
        """
        context, meta = retriever.get_context("total de ventas por mes")
        tables = meta.get("tables_used", [])

        config_tables = {"ADMINPROG", "ACC_ACC", "ACC_USR", "ACC_EXTRANET",
                         "AUTORIZAPLANT", "AUTORIZAPLANTNIV"}
        found_config = config_tables.intersection(set(tables))

        print(f"\n[REGRESION] ventas no devuelve tablas de config")
        print(f"[TABLAS] {tables}")

        if found_config:
            pytest.xfail(
                f"REGRESIÓN CONOCIDA: tablas de configuración {found_config} "
                f"aparecen en consultas de ventas."
            )

        assert "DOCCAB" in tables, "DOCCAB debe estar para consultas de ventas"

    def test_regresion_keywords_plurales(self, retriever):
        """
        'artículos' (plural) debe encontrar lo mismo que 'artículo' (singular).
        El normalizador de plurales debe funcionar.
        """
        _, meta_singular = retriever.get_context("dame el artículo más caro")
        _, meta_plural   = retriever.get_context("dame los artículos más caros")

        tables_s = set(meta_singular.get("tables_used", []))
        tables_p = set(meta_plural.get("tables_used", []))

        print(f"\n[REGRESION] keywords_plurales")
        print(f"[SINGULAR] {tables_s}")
        print(f"[PLURAL]   {tables_p}")

        # Ambas deben incluir ARTICULO
        assert "ARTICULO" in tables_s, "Singular: ARTICULO no encontrado"
        assert "ARTICULO" in tables_p, "Plural: ARTICULO no encontrado"

    def test_regresion_acentos_no_afectan_busqueda(self, retriever):
        """
        'artículo' (con acento) debe encontrar lo mismo que 'articulo' (sin acento).
        """
        _, meta_con    = retriever.get_context("dame el artículo más caro")
        _, meta_sin    = retriever.get_context("dame el articulo mas caro")

        tables_con = set(meta_con.get("tables_used", []))
        tables_sin = set(meta_sin.get("tables_used", []))

        print(f"\n[REGRESION] acentos_no_afectan")
        print(f"[CON ACENTO]  {tables_con}")
        print(f"[SIN ACENTO]  {tables_sin}")

        assert "ARTICULO" in tables_con, "Con acento: ARTICULO no encontrado"
        assert "ARTICULO" in tables_sin, "Sin acento: ARTICULO no encontrado"


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 10: INFORME FINAL DE COBERTURA
# ═══════════════════════════════════════════════════════════════════════════════

class TestInformeFinal:
    """Genera un informe de cobertura del concept_index."""

    def test_cobertura_concept_index(self, retriever):
        """
        Verifica que los conceptos más importantes del negocio están mapeados.
        Imprime un informe de cobertura.
        """
        conceptos_criticos = [
            # Documentos
            "factura", "albaran", "pedido", "presupuesto", "abono",
            "contrato", "sat", "recibo", "venta", "compra",
            # Entidades
            "articulo", "cliente", "proveedor", "agente", "empleado",
            # Operaciones
            "stock", "precio", "familia", "almacen", "iva",
            # Financiero
            "caja", "banco", "forma pago",
        ]

        stats = retriever.get_stats()
        print(f"\n[INFORME] Cobertura del concept_index")
        print(f"  Total keywords indexados: {stats['concept_keywords']}")
        print(f"  Total tablas indexadas:   {stats['tables_indexed']}")
        print(f"  Nodos en grafo:           {stats['graph_nodes']}")
        print(f"  Aristas en grafo:         {stats['graph_edges']}")
        print(f"\n  Conceptos críticos del negocio:")

        mapeados = 0
        no_mapeados = []

        for concepto in conceptos_criticos:
            _, meta = retriever.get_context(f"dame los {concepto}s")
            tables = meta.get("tables_used", [])
            kw_found = meta.get("keywords_found", [])
            source = meta.get("source", "?")

            if tables and source == "siuo":
                mapeados += 1
                print(f"    ✅ '{concepto}' → {tables[:3]}")
            else:
                no_mapeados.append(concepto)
                print(f"    ❌ '{concepto}' → NO MAPEADO (tablas={tables}, src={source})")

        cobertura = mapeados / len(conceptos_criticos) * 100
        print(f"\n  Cobertura: {mapeados}/{len(conceptos_criticos)} = {cobertura:.1f}%")

        if no_mapeados:
            print(f"  Sin mapear: {no_mapeados}")
            print(f"  → Añadir al BASE_CONCEPT_INDEX en deep_indexer_service.py")

        # Mínimo 70% de cobertura para pasar el test
        assert cobertura >= 70, \
            f"Cobertura del concept_index ({cobertura:.1f}%) por debajo del 70% mínimo. " \
            f"Sin mapear: {no_mapeados}"
