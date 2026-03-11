"""
test_siuo_retriever.py — Tests de integración del ContextRetriever (SIUO).

CAPA: integration (requiere índices SIUO generados)
MÓDULO: backend.modules.db_explorer.context_retriever
EJECUTAR: .venv/Scripts/pytest tests/integration/test_siuo_retriever.py -v -s

INDEPENDENCIA:
  - Sin IPs hardcodeadas. Parámetros desde test.properties vía conftest.py.
  - Se salta automáticamente si los índices SIUO no existen.
  - Funciona en cualquier PC con los índices generados.

PROPÓSITO:
  Verificar que el ContextRetriever mapea correctamente conceptos de negocio
  a tablas de la BD. Esto es crítico para que la IA genere SQL correcto.
"""

import sys
from pathlib import Path
from typing import List, Tuple
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ─── Helpers reutilizables ────────────────────────────────────────────────────

def _assert_siuo_maps(retriever, question: str, expected_tables: List[str],
                      forbidden_tables: List[str] = None, min_score: float = 0.0):
    """
    Helper reutilizable: verifica que una pregunta mapea a las tablas esperadas.
    Independiente de la BD concreta — usa los índices SIUO generados.
    """
    context, meta = retriever.get_context(question)
    tables = meta.get("tables_used", [])
    source = meta.get("source", "?")

    assert source == "siuo", f"Fuente esperada 'siuo', obtenida '{source}' para: '{question}'"
    assert tables, f"No se encontraron tablas para: '{question}'"

    for expected in expected_tables:
        assert expected in tables, (
            f"Tabla '{expected}' esperada pero no encontrada para: '{question}'\n"
            f"Tablas obtenidas: {tables}"
        )

    if forbidden_tables:
        for forbidden in forbidden_tables:
            assert forbidden not in tables, (
                f"Tabla '{forbidden}' NO debería aparecer para: '{question}'\n"
                f"Tablas obtenidas: {tables}"
            )

    return tables, meta


# ═══════════════════════════════════════════════════════════════════════════════
# Conceptos de 1 tabla
# ═══════════════════════════════════════════════════════════════════════════════

class TestConceptos1Tabla:
    """Preguntas que deben mapear a una sola tabla principal."""

    def test_articulos_mapea_a_articulo(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "cuántos artículos hay", ["ARTICULO"])

    def test_clientes_mapea_a_cliente(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "cuántos clientes tenemos", ["CLIENTE"])

    def test_proveedores_mapea_a_proveed(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "cuántos proveedores hay", ["PROVEED"])

    def test_agentes_mapea_a_agente(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "cuántos agentes hay", ["AGENTE"])

    def test_almacenes_mapea_a_almacen(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "qué almacenes hay", ["ALMACEN"])

    def test_familias_mapea_a_familias(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "qué familias de artículos hay", ["FAMILIAS"])


# ═══════════════════════════════════════════════════════════════════════════════
# Conceptos de documentos (DOCCAB)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConceptosDocumentos:
    """Preguntas sobre facturas, albaranes, pedidos → DOCCAB."""

    def test_facturas_mapea_a_doccab(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "dame las últimas facturas", ["DOCCAB"])

    def test_albaranes_mapea_a_doccab(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "dame los albaranes de hoy", ["DOCCAB"])

    def test_pedidos_mapea_a_doccab(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "pedidos de clientes pendientes", ["DOCCAB"])

    def test_presupuestos_mapea_a_doccab(self, siuo_retriever):
        _assert_siuo_maps(siuo_retriever, "dame los presupuestos del mes", ["DOCCAB"])


# ═══════════════════════════════════════════════════════════════════════════════
# Conceptos de ventas (DOCLIN + DOCCAB)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConceptosVentas:
    """
    Preguntas sobre ventas → DOCLIN + DOCCAB + ARTICULO.
    REGRESIÓN CRÍTICA: antes mapeaba a HISTORICOPRECIOS (incorrecto).
    """

    def test_articulos_mas_vendidos_usa_doclin(self, siuo_retriever):
        tables, _ = _assert_siuo_maps(
            siuo_retriever,
            "dime los artículos más vendidos",
            ["DOCLIN"],
            forbidden_tables=["HISTORICOPRECIOS", "FOTOGRAF", "COMISART"],
        )

    def test_articulos_mas_compras_usa_doclin(self, siuo_retriever):
        """REGRESIÓN CRÍTICA: antes devolvía tablas completamente incorrectas."""
        tables, _ = _assert_siuo_maps(
            siuo_retriever,
            "dime los artículos con más compras",
            ["DOCLIN"],
            forbidden_tables=["HISTORICOPRECIOS", "FOTOGRAF", "COMISART", "FABARTFABASOC"],
        )

    def test_ventas_por_agente_usa_doccab(self, siuo_retriever):
        _assert_siuo_maps(
            siuo_retriever,
            "cuánto ha vendido cada agente",
            ["DOCCAB"],
        )

    def test_total_facturado_usa_doccab(self, siuo_retriever):
        _assert_siuo_maps(
            siuo_retriever,
            "total facturado este mes",
            ["DOCCAB"],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Cobertura mínima del SIUO
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoberturaSIUO:
    """Verifica que el SIUO cubre los conceptos críticos de negocio."""

    # Conceptos críticos que DEBEN estar mapeados
    CONCEPTOS_CRITICOS: List[Tuple[str, str]] = [
        ("factura",     "DOCCAB"),
        ("albaran",     "DOCCAB"),
        ("pedido",      "DOCCAB"),
        ("articulo",    "ARTICULO"),
        ("cliente",     "CLIENTE"),
        ("proveedor",   "PROVEED"),
        ("agente",      "AGENTE"),
        ("almacen",     "ALMACEN"),
        ("venta",       "DOCLIN"),
        ("compra",      "DOCLIN"),
    ]

    def test_cobertura_minima(self, siuo_retriever, test_config):
        """Al menos MIN_SIUO_COVERAGE_PCT% de conceptos críticos deben estar mapeados."""
        ok = 0
        total = len(self.CONCEPTOS_CRITICOS)
        fallos = []

        for concepto, tabla_esperada in self.CONCEPTOS_CRITICOS:
            _, meta = siuo_retriever.get_context(f"dame los {concepto}s")
            tables = meta.get("tables_used", [])
            source = meta.get("source", "?")
            if tabla_esperada in tables and source == "siuo":
                ok += 1
            else:
                fallos.append(f"{concepto} → esperaba {tabla_esperada}, obtuvo {tables}")

        cobertura = ok / total * 100
        min_cov = test_config.min_siuo_coverage

        if fallos:
            print(f"\n⚠️ Conceptos no mapeados ({len(fallos)}/{total}):")
            for f in fallos:
                print(f"  ❌ {f}")

        assert cobertura >= min_cov, (
            f"Cobertura SIUO {cobertura:.1f}% < mínimo {min_cov}%\n"
            f"Fallos: {fallos}"
        )

    def test_estadisticas_siuo(self, siuo_retriever):
        """Verifica que el SIUO tiene estadísticas razonables."""
        stats = siuo_retriever.get_stats()
        assert stats["tables_indexed"] > 0, "SIUO sin tablas indexadas"
        assert stats["concept_keywords"] > 0, "SIUO sin keywords"
        print(f"\n📊 SIUO: {stats['tables_indexed']} tablas, {stats['concept_keywords']} keywords")
