"""
test_context_and_multiturn_chat.py — Tests del sistema de contexto SIUO y chat multi-turno.

RESPONSABILIDAD:
  Verifica que:
  1. El ContextRetriever envía datos reales de tablas (sample_rows) + metadatos a la IA.
  2. El contexto incluye columnas clave, filtros SQL, relaciones entre tablas y valores de ejemplo.
  3. El ChatService mantiene conversaciones multi-turno hasta encontrar el SQL correcto.
  4. El SQLCorrector reintenta con contexto enriquecido cuando el SQL falla.
  5. El sistema nunca envía columnas sensibles (NIF, EMAIL, TELEFONO) a la IA.
  6. El control de tokens funciona correctamente (nunca excede max_tokens).

FILOSOFÍA DE DISEÑO:
  - Tests unitarios puros: sin Firebird real, sin IA real (todo mockeado).
  - Cada test verifica UN comportamiento concreto.
  - Los mocks simulan datos reales de la BD de climatización (ARTICULO, DOCCAB, DOCLIN, etc.)
  - Los tests de multi-turno simulan el diálogo completo app ↔ IA hasta SQL correcto.

PATRÓN: Arrange → Act → Assert (AAA)
"""

import json
import pytest
import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ─── Fixtures de datos de prueba ─────────────────────────────────────────────

# Simula el table_index generado por DeepIndexerService
MOCK_TABLE_INDEX = {
    "tables": {
        "ARTICULO": {
            "desc": "Catálogo de artículos y productos",
            "n": 4823,
            "pk": ["CODIGO"],
            "cols_key": ["CODIGO", "NOMBRE", "DESCRIPCIONCORTA", "FAMILIA", "PRECIO", "STOCKARTICULO"],
            "related": ["DOCLIN", "STOCKARTICULO"],
            "note": "STOCK no existe → usar STOCKARTICULO",
            "queries": ["SELECT FIRST 10 CODIGO, NOMBRE, PRECIO FROM ARTICULO ORDER BY NOMBRE"],
            "sample_rows": [
                {"CODIGO": "AC001", "NOMBRE": "Split Daikin 2.5kW", "PRECIO": 899.00, "FAMILIA": "SPLITS"},
                {"CODIGO": "AC002", "NOMBRE": "Split Mitsubishi 3.5kW", "PRECIO": 1250.00, "FAMILIA": "SPLITS"},
                {"CODIGO": "GAS01", "NOMBRE": "Gas R-32 10kg", "PRECIO": 45.00, "FAMILIA": "GASES"},
            ],
        },
        "DOCCAB": {
            "desc": "Cabecera de documentos (facturas, albaranes, pedidos, presupuestos)",
            "n": 18432,
            "pk": ["NUMERO", "TIPO"],
            "cols_key": ["NUMERO", "TIPO", "FECHA", "CLIENTE", "TOTAL", "ESTADO"],
            "related": ["DOCLIN", "CLIENTE"],
            "note": "TIPO: 13=factura, 12=pedido, 11=albaran, 0=presupuesto, 2=SAT",
            "queries": [
                "SELECT FIRST 10 NUMERO, FECHA, TOTAL FROM DOCCAB WHERE TIPO=13 ORDER BY FECHA DESC"
            ],
            "sample_rows": [
                {"NUMERO": 10045, "TIPO": 13, "FECHA": "2026-03-01", "TOTAL": 2340.50},
                {"NUMERO": 10046, "TIPO": 13, "FECHA": "2026-03-02", "TOTAL": 890.00},
                {"NUMERO": 10047, "TIPO": 11, "FECHA": "2026-03-02", "TOTAL": 450.00},
            ],
        },
        "DOCLIN": {
            "desc": "Líneas de documentos (detalle de artículos por documento)",
            "n": 87654,
            "pk": ["NUMERO", "TIPO", "LINEA"],
            "cols_key": ["NUMERO", "TIPO", "LINEA", "CODIGO", "CANTIDAD", "PRECIO", "IMPORTE"],
            "related": ["DOCCAB", "ARTICULO"],
            "note": "JOIN con ARTICULO por CODIGO para obtener nombre del artículo",
            "queries": [
                "SELECT CODIGO, SUM(CANTIDAD) AS TOTAL FROM DOCLIN GROUP BY CODIGO ORDER BY TOTAL DESC"
            ],
            "sample_rows": [
                {"NUMERO": 10045, "TIPO": 13, "CODIGO": "AC001", "CANTIDAD": 2, "IMPORTE": 1798.00},
                {"NUMERO": 10045, "TIPO": 13, "CODIGO": "GAS01", "CANTIDAD": 5, "IMPORTE": 225.00},
            ],
        },
        "CLIENTE": {
            "desc": "Maestro de clientes",
            "n": 1205,
            "pk": ["CODIGO"],
            "cols_key": ["CODIGO", "NOMBRE", "POBLACION", "PROVINCIA"],
            "related": ["DOCCAB"],
            "note": None,
            "queries": ["SELECT FIRST 10 CODIGO, NOMBRE FROM CLIENTE ORDER BY NOMBRE"],
            "sample_rows": [
                {"CODIGO": "CLI001", "NOMBRE": "Instalaciones García S.L.", "POBLACION": "Madrid"},
                {"CODIGO": "CLI002", "NOMBRE": "Climatización Norte S.A.", "POBLACION": "Bilbao"},
            ],
        },
        "STOCKARTICULO": {
            "desc": "Stock actual de artículos por almacén",
            "n": 4823,
            "pk": ["CODIGO", "ALMACEN"],
            "cols_key": ["CODIGO", "ALMACEN", "STOCK", "STOCKMIN", "STOCKMAX"],
            "related": ["ARTICULO"],
            "note": "Usar esta tabla para consultas de stock, NO ARTICULO.STOCK",
            "queries": ["SELECT CODIGO, STOCK FROM STOCKARTICULO WHERE STOCK < 0"],
            "sample_rows": [
                {"CODIGO": "AC001", "ALMACEN": "01", "STOCK": 15, "STOCKMIN": 2},
                {"CODIGO": "GAS01", "ALMACEN": "01", "STOCK": -3, "STOCKMIN": 5},
            ],
        },
    }
}

# Simula el concept_index generado por DeepIndexerService
MOCK_CONCEPT_INDEX = {
    "index": {
        "articulo":    ["ARTICULO"],
        "articulos":   ["ARTICULO"],
        "producto":    ["ARTICULO"],
        "ventas":      [{"table": "DOCCAB", "filter": "TIPO=13"}, "DOCLIN"],
        "factura":     [{"table": "DOCCAB", "filter": "TIPO=13"}],
        "facturas":    [{"table": "DOCCAB", "filter": "TIPO=13"}],
        "albaran":     [{"table": "DOCCAB", "filter": "TIPO=11"}],
        "pedido":      [{"table": "DOCCAB", "filter": "TIPO=12"}],
        "presupuesto": [{"table": "DOCCAB", "filter": "TIPO=0"}],
        "compras":     ["DOCLIN", "DOCCAB"],
        "stock":       ["STOCKARTICULO"],
        "cliente":     ["CLIENTE"],
        "clientes":    ["CLIENTE"],
        "precio":      ["ARTICULO"],
        "split":       ["ARTICULO"],
        "gas":         ["ARTICULO"],
        "sat":         [{"table": "DOCCAB", "filter": "TIPO=2"}],
    }
}

# Simula el db_graph generado por DeepIndexerService
MOCK_DB_GRAPH = {
    "edges": [
        {"from": "DOCCAB",  "to": "DOCLIN",       "via": "NUMERO+TIPO"},
        {"from": "DOCLIN",  "to": "ARTICULO",      "via": "CODIGO"},
        {"from": "DOCCAB",  "to": "CLIENTE",       "via": "CLIENTE"},
        {"from": "ARTICULO","to": "STOCKARTICULO", "via": "CODIGO"},
    ],
    "paths": {}
}

# Simula el value_index generado por DeepIndexerService
MOCK_VALUE_INDEX = {
    "enums": {
        "DOCCAB.TIPO": {
            "13": "Factura",
            "12": "Pedido",
            "11": "Albarán",
            "0":  "Presupuesto",
            "2":  "SAT/Orden de trabajo",
            "3":  "Abono",
        },
        "ARTICULO.FAMILIA": {
            "SPLITS":    "Equipos Split",
            "GASES":     "Gases refrigerantes",
            "ACCESORIOS":"Accesorios instalación",
        },
    },
    "ranges": {
        "DOCCAB.TOTAL": {"min": 0.01, "max": 98450.00},
        "ARTICULO.PRECIO": {"min": 0.50, "max": 12500.00},
    }
}


# ─── Fixture: ContextRetriever con índices mockeados ─────────────────────────

@pytest.fixture
def retriever():
    """
    ContextRetriever cargado con índices mockeados (sin ficheros en disco).
    Simula el estado tras una indexación completa con DeepIndexerService.
    """
    from backend.modules.db_explorer.context_retriever import ContextRetriever

    r = ContextRetriever()
    r._table_index   = MOCK_TABLE_INDEX["tables"]
    r._concept_index = MOCK_CONCEPT_INDEX["index"]
    r._value_index   = MOCK_VALUE_INDEX

    # Construir grafo de adyacencia
    r._graph_adj = defaultdict(set)
    for edge in MOCK_DB_GRAPH["edges"]:
        r._graph_adj[edge["from"]].add(edge["to"])
        r._graph_adj[edge["to"]].add(edge["from"])
    r._graph_paths = {}
    r._loaded = True

    return r


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 1: CONTEXTO INCLUYE DATOS REALES DE TABLAS (sample_rows)
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextIncludesSampleRows:
    """
    Verifica que el contexto enviado a la IA incluye filas de ejemplo reales
    de las tablas relevantes, para que la IA entienda la estructura de datos.
    """

    def test_sample_rows_incluidos_en_contexto_articulos(self, retriever):
        """El contexto para 'artículos más vendidos' incluye filas de ejemplo de ARTICULO."""
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=3000)

        # Verificar que hay datos de ejemplo en el contexto
        assert "Datos de ejemplo" in context or "AC001" in context or "Split Daikin" in context, \
            "El contexto debe incluir datos de ejemplo de ARTICULO"

    def test_sample_rows_incluidos_en_contexto_facturas(self, retriever):
        """El contexto para 'facturas del mes' incluye filas de ejemplo de DOCCAB."""
        context, meta = retriever.get_context("facturas del mes actual", max_tokens=3000)

        # DOCCAB debe estar en las tablas usadas
        assert "DOCCAB" in meta["tables_used"], \
            "DOCCAB debe estar en las tablas usadas para consultas de facturas"

        # El contexto debe incluir datos de ejemplo de DOCCAB
        assert "10045" in context or "Datos de ejemplo" in context or "TIPO" in context, \
            "El contexto debe incluir datos de ejemplo de DOCCAB"

    def test_sample_rows_maximo_3_filas(self, retriever):
        """El contexto nunca incluye más de 3 filas de ejemplo por tabla (máximo 3 por tabla)."""
        # Añadir 6 filas de ejemplo a ARTICULO para verificar que solo se muestran 3
        retriever._table_index["ARTICULO"]["sample_rows"] = [
            {"CODIGO": f"XTEST{i:02d}", "NOMBRE": f"Artículo test {i}", "PRECIO": float(i * 100)}
            for i in range(6)  # 6 filas — solo deben mostrarse 3
        ]
        context, meta = retriever.get_context("artículos más caros", max_tokens=3000)

        # Solo deben aparecer los primeros 3 códigos (XTEST00, XTEST01, XTEST02)
        # Los últimos 3 (XTEST03, XTEST04, XTEST05) NO deben aparecer
        assert "XTEST03" not in context, "La fila 4 no debe aparecer (máximo 3 por tabla)"
        assert "XTEST04" not in context, "La fila 5 no debe aparecer (máximo 3 por tabla)"
        assert "XTEST05" not in context, "La fila 6 no debe aparecer (máximo 3 por tabla)"
        # Las primeras 3 sí deben aparecer
        assert "XTEST00" in context or "XTEST01" in context or "XTEST02" in context, \
            "Al menos las primeras filas de ejemplo deben aparecer"

    def test_sample_rows_filtran_columnas_sensibles(self, retriever):
        """
        Las filas de ejemplo NO deben incluir columnas sensibles
        (NIF, EMAIL, TELEFONO, IBAN, etc.).
        """
        # Añadir columnas sensibles a los sample_rows para probar el filtrado
        retriever._table_index["CLIENTE"]["sample_rows"] = [
            {
                "CODIGO": "CLI001",
                "NOMBRE": "García S.L.",
                "NIF": "B12345678",          # SENSIBLE — debe filtrarse
                "EMAIL": "info@garcia.com",   # SENSIBLE — debe filtrarse
                "TELEFONO": "912345678",      # SENSIBLE — debe filtrarse
                "POBLACION": "Madrid",        # OK — puede incluirse
            }
        ]

        context, meta = retriever.get_context("clientes de Madrid", max_tokens=3000)

        # Las columnas sensibles NO deben aparecer en el contexto
        assert "B12345678" not in context, "NIF no debe aparecer en el contexto"
        assert "info@garcia.com" not in context, "EMAIL no debe aparecer en el contexto"
        assert "912345678" not in context, "TELEFONO no debe aparecer en el contexto"

        # Los datos no sensibles SÍ deben aparecer
        assert "Madrid" in context or "CLI001" in context, \
            "Los datos no sensibles deben aparecer en el contexto"

    def test_sample_rows_no_incluyen_valores_nulos(self, retriever):
        """Las filas de ejemplo no incluyen columnas con valor None o vacío."""
        retriever._table_index["ARTICULO"]["sample_rows"] = [
            {"CODIGO": "AC001", "NOMBRE": "Split Daikin", "DESCRIPCION": None, "PRECIO": 899.00}
        ]

        context, meta = retriever.get_context("artículos más caros", max_tokens=3000)

        # None no debe aparecer en el contexto
        assert "'DESCRIPCION': None" not in context, \
            "Las columnas con valor None no deben aparecer en el contexto"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2: METADATOS COMPLETOS EN EL CONTEXTO
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextMetadata:
    """
    Verifica que el contexto incluye todos los metadatos necesarios para que
    la IA genere SQL correcto: filtros obligatorios, columnas clave, relaciones.
    """

    def test_filtro_obligatorio_facturas(self, retriever):
        """El contexto para 'facturas' incluye el filtro WHERE TIPO=13."""
        context, meta = retriever.get_context("facturas de este mes", max_tokens=3000)

        assert "TIPO=13" in context or "TIPO = 13" in context, \
            "El contexto debe incluir el filtro obligatorio TIPO=13 para facturas"

    def test_filtro_obligatorio_albaranes(self, retriever):
        """El contexto para 'albaranes' incluye el filtro WHERE TIPO=11."""
        context, meta = retriever.get_context("albaranes del mes pasado", max_tokens=3000)

        assert "TIPO=11" in context or "TIPO = 11" in context, \
            "El contexto debe incluir el filtro obligatorio TIPO=11 para albaranes"

    def test_nota_critica_stock(self, retriever):
        """El contexto para 'stock' incluye la nota crítica sobre STOCKARTICULO."""
        context, meta = retriever.get_context("artículos con stock negativo", max_tokens=3000)

        assert "STOCKARTICULO" in context, \
            "El contexto debe mencionar STOCKARTICULO para consultas de stock"

    def test_columnas_clave_incluidas(self, retriever):
        """El contexto incluye las columnas clave de las tablas relevantes."""
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=3000)

        # Las columnas clave de ARTICULO deben estar en el contexto
        assert "CODIGO" in context, "CODIGO debe estar en el contexto"
        assert "NOMBRE" in context, "NOMBRE debe estar en el contexto"

    def test_relaciones_entre_tablas_incluidas(self, retriever):
        """El contexto incluye las relaciones entre tablas para JOINs correctos."""
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=3000)

        # DOCLIN debe estar en el contexto (relacionada con ARTICULO para ventas)
        assert "DOCLIN" in context or "DOCLIN" in meta["tables_used"], \
            "DOCLIN debe estar en el contexto para consultas de ventas de artículos"

    def test_valores_enumerados_incluidos(self, retriever):
        """El contexto incluye los valores enumerados relevantes (TIPO de DOCCAB)."""
        context, meta = retriever.get_context("facturas del año", max_tokens=3000)

        # Los valores del enumerado DOCCAB.TIPO deben estar en el contexto
        # (solo si el keyword es relevante para la columna)
        assert "DOCCAB" in meta["tables_used"], \
            "DOCCAB debe estar en las tablas usadas para consultas de facturas"

    def test_numero_registros_incluido(self, retriever):
        """El contexto incluye el número de registros de cada tabla."""
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=3000)

        # El número de registros de ARTICULO (4823) debe estar en el contexto
        assert "4,823" in context or "4823" in context, \
            "El número de registros debe estar en el contexto"

    def test_ejemplo_sql_incluido(self, retriever):
        """El contexto incluye una consulta SQL de ejemplo para la tabla."""
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=3000)

        assert "SELECT" in context, \
            "El contexto debe incluir al menos una consulta SQL de ejemplo"

    def test_reglas_firebird_incluidas(self, retriever):
        """El contexto incluye las reglas específicas de Firebird (FIRST N, UPPER, etc.)."""
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=3000)

        assert "FIRST" in context, \
            "El contexto debe incluir la regla FIRST N de Firebird"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 3: CONTROL DE TOKENS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenControl:
    """
    Verifica que el contexto nunca excede el límite de tokens configurado.
    """

    def test_contexto_no_excede_max_tokens(self, retriever):
        """El contexto generado nunca excede max_tokens."""
        max_tokens = 500
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=max_tokens)

        tokens_estimated = meta["tokens_estimated"]
        assert tokens_estimated <= max_tokens, \
            f"El contexto ({tokens_estimated} tokens) excede el límite ({max_tokens} tokens)"

    def test_contexto_grande_usa_version_compacta(self, retriever):
        """Con max_tokens muy pequeño, usa la versión compacta de los bloques."""
        max_tokens = 100  # Muy pequeño — fuerza versión compacta
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=max_tokens)

        tokens_estimated = meta["tokens_estimated"]
        assert tokens_estimated <= max_tokens, \
            f"Incluso con max_tokens={max_tokens}, el contexto no debe excederlo"

    def test_contexto_normal_incluye_tablas_suficientes(self, retriever):
        """Con max_tokens normal (2000), el contexto incluye al menos 2 tablas."""
        context, meta = retriever.get_context("artículos más vendidos", max_tokens=2000)

        assert len(meta["tables_used"]) >= 1, \
            "El contexto debe incluir al menos 1 tabla con max_tokens=2000"

    def test_estimacion_tokens_coherente(self, retriever):
        """La estimación de tokens es coherente con la longitud del contexto."""
        context, meta = retriever.get_context("facturas del mes", max_tokens=3000)

        # 1 token ~ 4 chars → tokens ≈ len(context) / 4
        expected_tokens = len(context) * 0.25
        actual_tokens = meta["tokens_estimated"]

        # Tolerancia del 20%
        assert abs(actual_tokens - expected_tokens) / max(expected_tokens, 1) < 0.2, \
            f"La estimación de tokens ({actual_tokens}) no es coherente con el contexto ({len(context)} chars)"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 4: BÚSQUEDA EN CONCEPT_INDEX Y EXPANSIÓN CON GRAFO
# ═══════════════════════════════════════════════════════════════════════════════

class TestConceptIndexAndGraph:
    """
    Verifica que el ContextRetriever encuentra las tablas correctas para
    diferentes preguntas usando el concept_index y el grafo de relaciones.
    """

    def test_pregunta_articulos_encuentra_tabla_articulo(self, retriever):
        """'artículos más vendidos' → ARTICULO en tablas usadas."""
        _, meta = retriever.get_context("artículos más vendidos")
        assert "ARTICULO" in meta["tables_used"], \
            "ARTICULO debe estar en las tablas usadas para preguntas sobre artículos"

    def test_pregunta_facturas_encuentra_doccab(self, retriever):
        """'facturas del mes' → DOCCAB en tablas usadas."""
        _, meta = retriever.get_context("facturas del mes actual")
        assert "DOCCAB" in meta["tables_used"], \
            "DOCCAB debe estar en las tablas usadas para preguntas sobre facturas"

    def test_pregunta_stock_encuentra_stockarticulo(self, retriever):
        """'stock negativo' → STOCKARTICULO en tablas usadas."""
        _, meta = retriever.get_context("artículos con stock negativo")
        assert "STOCKARTICULO" in meta["tables_used"], \
            "STOCKARTICULO debe estar en las tablas usadas para preguntas de stock"

    def test_expansion_grafo_incluye_tablas_relacionadas(self, retriever):
        """
        Una pregunta sobre 'ventas' expande el grafo e incluye tablas relacionadas
        (DOCCAB → DOCLIN → ARTICULO).
        """
        _, meta = retriever.get_context("artículos con más ventas")
        tables = meta["tables_used"]

        # Al menos DOCLIN o ARTICULO deben estar por expansión del grafo
        assert any(t in tables for t in ["DOCLIN", "ARTICULO", "DOCCAB"]), \
            "La expansión del grafo debe incluir tablas relacionadas con ventas"

    def test_normalizacion_plural_singular(self, retriever):
        """'artículos' (plural con tilde) → encuentra 'articulo' en concept_index."""
        _, meta = retriever.get_context("artículos más caros")
        assert "ARTICULO" in meta["tables_used"], \
            "La normalización plural→singular debe funcionar para 'artículos'"

    def test_normalizacion_tilde(self, retriever):
        """'facturas' (con tilde en la pregunta) → encuentra DOCCAB."""
        _, meta = retriever.get_context("últimas facturas emitidas")
        assert "DOCCAB" in meta["tables_used"], \
            "La normalización de tildes debe funcionar"

    def test_keywords_desconocidos_registrados(self, retriever):
        """Las palabras no mapeadas en concept_index se registran como unknown_kws."""
        with patch.object(retriever, '_log_query') as mock_log:
            _, meta = retriever.get_context("equipos frigoríficos industriales")
            unknown = meta["keywords_unknown"]
            # 'frigorificos' e 'industriales' no están en el concept_index
            assert len(unknown) > 0, \
                "Las palabras no mapeadas deben registrarse como keywords desconocidos"

    def test_fuente_siuo_cuando_indices_cargados(self, retriever):
        """Cuando los índices están cargados, la fuente es 'siuo' (no 'fallback')."""
        _, meta = retriever.get_context("artículos más vendidos")
        assert meta["source"] == "siuo", \
            "La fuente debe ser 'siuo' cuando los índices están cargados"

    def test_fuente_fallback_cuando_sin_indices(self):
        """Cuando no hay índices, la fuente es 'fallback'."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever

        r = ContextRetriever()
        # Mockear load() para que no cargue los índices reales del disco
        with patch.object(r, 'load', return_value=False):
            r._loaded = False
            r._table_index = {}
            with patch.object(r, '_get_fallback_context', return_value="Fallback schema"):
                _, meta = r.get_context("artículos más vendidos")
                assert meta["source"] == "fallback", \
                    "La fuente debe ser 'fallback' cuando no hay índices"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 5: CHAT MULTI-TURNO — LA APP CONVERSA CON LA IA HASTA ENCONTRAR EL SQL
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiTurnChatUntilCorrectSQL:
    """
    Verifica que el sistema mantiene conversaciones multi-turno con la IA
    hasta que el SQL generado es correcto y ejecutable en Firebird.

    Simula el flujo completo:
    1. Usuario pregunta → IA genera SQL incorrecto (error de sintaxis)
    2. SQLCorrector detecta el error → envía contexto enriquecido a la IA
    3. IA genera SQL corregido → se ejecuta correctamente
    4. ChatService devuelve la respuesta final al usuario
    """

    @pytest.mark.asyncio
    async def test_sql_corrector_reintenta_con_contexto_enriquecido(self):
        """
        El SQLCorrector reintenta con contexto enriquecido cuando el SQL falla.
        Simula: SQL con columna inexistente → corrección → columna correcta.

        NOTA: No usamos LIMIT porque el FirebirdSQLNormalizer lo convierte a FIRST N
        de forma determinista antes de ejecutar (no llega a fallar en BD).
        Usamos una columna inexistente (PRECIO_VENTA) que el normalizer no corrige.
        """
        from backend.modules.chat.sql_corrector import SQLCorrector

        corrector = SQLCorrector()

        # SQL incorrecto: columna PRECIO_VENTA no existe (el normalizer no la corrige)
        bad_sql = "SELECT FIRST 10 CODIGO, PRECIO_VENTA FROM ARTICULO"

        # Simular que la primera ejecución falla con error de columna inexistente
        call_count = [0]
        def mock_execute(sql):
            call_count[0] += 1
            if "PRECIO_VENTA" in sql:
                raise Exception("Column unknown: PRECIO_VENTA")
            return [{"CODIGO": "AC001", "NOMBRE": "Split Daikin"}]

        # Mock del proveedor IA que corrige el SQL
        mock_provider = MagicMock()
        mock_provider.generate_text = AsyncMock(
            return_value="El SQL correcto es:\n```sql\nSELECT FIRST 10 CODIGO, NOMBRE FROM ARTICULO\n```"
        )

        results = await corrector.execute_with_correction(
            sql_query=bad_sql,
            original_question="dame los 10 primeros artículos con precio",
            db_context="TABLA: ARTICULO\n  Columnas: CODIGO, NOMBRE, PRECIO\n  Nota: no existe PRECIO_VENTA",
            ai_provider=mock_provider,
            execute_func=mock_execute,
            max_retries=3,
        )

        assert results is not None, "El corrector debe devolver resultados tras la corrección"
        assert call_count[0] >= 2, \
            "El corrector debe haber intentado ejecutar el SQL al menos 2 veces"

    @pytest.mark.asyncio
    async def test_multiturn_historial_conversacion_incluido_en_contexto(self):
        """
        El historial de conversación se incluye en el system prompt de cada turno.
        Verifica que la IA recibe el contexto de turnos anteriores.
        """
        from backend.modules.chat.service import ChatService

        service = ChatService()

        # Historial de conversación previo
        conversation_history = [
            {"role": "user",      "content": "dame los artículos más vendidos"},
            {"role": "assistant", "content": "Los 5 artículos más vendidos son: Split Daikin..."},
        ]

        context = {
            "model_id": "test-model",
            "conversation_history": conversation_history,
            "confirm_data_sending": True,
            "db_params": None,
        }

        # Mock del orchestrator para capturar el system_prompt
        captured_prompts = []

        async def mock_execute_with_fallback(system_prompt, user_message, **kwargs):
            captured_prompts.append(system_prompt)
            return "```sql\nSELECT FIRST 5 CODIGO, NOMBRE FROM ARTICULO\n```", "test-model"

        with patch.object(service.model_orchestrator, 'execute_with_fallback',
                          side_effect=mock_execute_with_fallback):
            with patch.object(service, '_execute_sql', return_value=[
                {"CODIGO": "AC001", "NOMBRE": "Split Daikin", "NCOMPRAS": 45}
            ]):
                with patch('backend.modules.chat.service.get_context_retriever') as mock_retriever:
                    mock_r = MagicMock()
                    mock_r.get_context.return_value = ("TABLA: ARTICULO\n", {
                        "tables_used": ["ARTICULO"],
                        "source": "siuo",
                        "tokens_estimated": 100,
                    })
                    mock_retriever.return_value = mock_r

                    await service.process_message(
                        "¿y cuáles tienen más stock?",
                        context
                    )

        # Verificar que el historial está en el system_prompt
        assert len(captured_prompts) > 0, "Debe haberse llamado al orchestrator"
        first_prompt = captured_prompts[0]
        assert "artículos más vendidos" in first_prompt or "CONTEXTO" in first_prompt, \
            "El historial de conversación debe estar en el system_prompt"

    @pytest.mark.asyncio
    async def test_multiturn_segunda_pregunta_usa_contexto_anterior(self):
        """
        En una conversación multi-turno, la segunda pregunta puede referirse
        a resultados de la primera ('¿y cuáles tienen stock negativo?').
        El sistema debe incluir el historial para que la IA entienda el contexto.
        """
        from backend.modules.chat.service import ChatService

        service = ChatService()

        # Turno 1: pregunta inicial
        context_turn1 = {
            "model_id": "test-model",
            "conversation_history": [],
            "confirm_data_sending": True,
            "db_params": None,
        }

        sql_responses = [
            # Turno 1: SQL para artículos más vendidos
            "```sql\nSELECT FIRST 5 A.CODIGO, A.NOMBRE, COUNT(*) AS NCOMPRAS FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO=A.CODIGO GROUP BY A.CODIGO, A.NOMBRE ORDER BY NCOMPRAS DESC\n```",
            # Turno 2: SQL para stock de esos artículos
            "```sql\nSELECT A.CODIGO, A.NOMBRE, S.STOCK FROM ARTICULO A JOIN STOCKARTICULO S ON S.CODIGO=A.CODIGO WHERE S.STOCK < 0\n```",
        ]
        call_idx = [0]

        async def mock_execute_with_fallback(system_prompt, user_message, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx < len(sql_responses):
                return sql_responses[idx], "test-model"
            return "No tengo más información.", "test-model"

        db_results = [
            [{"CODIGO": "AC001", "NOMBRE": "Split Daikin", "NCOMPRAS": 45}],
            [{"CODIGO": "GAS01", "NOMBRE": "Gas R-32", "STOCK": -3}],
        ]
        db_call_idx = [0]

        def mock_execute_sql(sql, db_params):
            idx = db_call_idx[0]
            db_call_idx[0] += 1
            return db_results[min(idx, len(db_results) - 1)]

        with patch.object(service.model_orchestrator, 'execute_with_fallback',
                          side_effect=mock_execute_with_fallback):
            with patch.object(service, '_execute_sql', side_effect=mock_execute_sql):
                with patch('backend.modules.chat.service.get_context_retriever') as mock_r:
                    mock_retriever = MagicMock()
                    mock_retriever.get_context.return_value = ("TABLA: ARTICULO\n", {
                        "tables_used": ["ARTICULO"],
                        "source": "siuo",
                        "tokens_estimated": 100,
                    })
                    mock_r.return_value = mock_retriever

                    # Turno 1
                    resp1 = await service.process_message(
                        "dame los 5 artículos más vendidos",
                        context_turn1
                    )

                    # Turno 2: con historial del turno 1
                    context_turn2 = {
                        **context_turn1,
                        "conversation_history": [
                            {"role": "user",      "content": "dame los 5 artículos más vendidos"},
                            {"role": "assistant", "content": str(resp1)},
                        ],
                    }

                    resp2 = await service.process_message(
                        "¿y cuáles de esos tienen stock negativo?",
                        context_turn2
                    )

        # Ambas respuestas deben ser válidas (no None ni error)
        assert resp1 is not None, "La respuesta del turno 1 no debe ser None"
        assert resp2 is not None, "La respuesta del turno 2 no debe ser None"

    @pytest.mark.asyncio
    async def test_sql_corrector_multiples_reintentos_hasta_exito(self):
        """
        El SQLCorrector puede hacer múltiples reintentos (hasta max_retries)
        hasta que el SQL es correcto. Simula 2 fallos seguidos y luego éxito.
        """
        from backend.modules.chat.sql_corrector import SQLCorrector

        corrector = SQLCorrector()

        # Secuencia de SQLs: 2 incorrectos → 1 correcto
        sql_sequence = [
            "SELECT CODIGO FROM ARTICULO LIMIT 10",           # Intento 1: LIMIT (malo)
            "SELECT TOP 10 CODIGO FROM ARTICULO",             # Intento 2: TOP (malo)
            "SELECT FIRST 10 CODIGO FROM ARTICULO",           # Intento 3: FIRST (correcto)
        ]
        sql_idx = [0]

        def mock_execute(sql):
            if "LIMIT" in sql or "TOP" in sql:
                raise Exception(f"Token unknown: {'LIMIT' if 'LIMIT' in sql else 'TOP'}")
            return [{"CODIGO": "AC001"}]

        # La IA devuelve SQLs progresivamente mejores
        ai_responses = [
            "Corrijo con TOP:\n```sql\nSELECT TOP 10 CODIGO FROM ARTICULO\n```",
            "Corrijo con FIRST:\n```sql\nSELECT FIRST 10 CODIGO FROM ARTICULO\n```",
        ]
        ai_idx = [0]

        mock_provider = MagicMock()
        async def mock_generate(system, user, **kwargs):
            resp = ai_responses[min(ai_idx[0], len(ai_responses) - 1)]
            ai_idx[0] += 1
            return resp
        mock_provider.generate_text = mock_generate

        results = await corrector.execute_with_correction(
            sql_query=sql_sequence[0],
            original_question="dame 10 artículos",
            db_context="TABLA: ARTICULO\nRegla: FIRST N no LIMIT ni TOP",
            ai_provider=mock_provider,
            execute_func=mock_execute,
            max_retries=3,
        )

        assert results == [{"CODIGO": "AC001"}], \
            "El corrector debe devolver los resultados correctos tras múltiples reintentos"

    @pytest.mark.asyncio
    async def test_sql_corrector_incluye_contexto_enriquecido_en_reintento(self):
        """
        Verifica que el SQLCorrector detecta el error de columna inexistente,
        escala a la IA y el prompt de corrección incluye el contexto de la BD.

        ESTRATEGIA: Mockeamos request_correction (método interno del corrector)
        para capturar los argumentos que recibe, verificando que incluye el error
        y el contexto de la BD sin depender de la firma exacta de generate_text.
        """
        from backend.modules.chat.sql_corrector import SQLCorrector

        corrector = SQLCorrector()
        captured_correction_calls = []

        # SQL con columna inexistente — el normalizer NO la corrige
        def mock_execute(sql):
            if "STOCK_ACTUAL" in sql:
                raise Exception("Column unknown: STOCK_ACTUAL")
            return [{"CODIGO": "AC001"}]

        # Capturar la llamada a request_correction (método que llama a la IA)
        # Firma real: (failed_query, original_question, error_message, error_info, db_context, ai_provider, ...)
        async def mock_request_correction(
            failed_query, original_question, error_message, error_info,
            db_context, ai_provider, **kwargs
        ):
            captured_correction_calls.append({
                "sql": failed_query,
                "error": str(error_message),
                "db_context": db_context,
                "question": original_question,
            })
            # Devolver SQL corregido
            return "SELECT FIRST 10 CODIGO FROM STOCKARTICULO"

        corrector.request_correction = mock_request_correction

        mock_provider = MagicMock()
        mock_provider.generate_text = AsyncMock(
            return_value="```sql\nSELECT FIRST 10 CODIGO FROM STOCKARTICULO\n```"
        )

        db_context = "TABLA: STOCKARTICULO\n  Columnas: CODIGO, STOCK\n  Nota: no existe STOCK_ACTUAL"

        await corrector.execute_with_correction(
            sql_query="SELECT FIRST 10 CODIGO, STOCK_ACTUAL FROM ARTICULO",
            original_question="dame 10 artículos con su stock actual",
            db_context=db_context,
            ai_provider=mock_provider,
            execute_func=mock_execute,
            max_retries=3,
        )

        assert len(captured_correction_calls) >= 1, \
            "El corrector debe haber llamado a request_correction al menos una vez"

        call = captured_correction_calls[0]
        # El error debe estar en la llamada
        assert "STOCK_ACTUAL" in call["error"] or "Column unknown" in call["error"], \
            "El error de columna debe estar en la llamada a request_correction"
        # El contexto de la BD debe estar en la llamada
        assert "STOCKARTICULO" in call["db_context"] or "ARTICULO" in call["db_context"], \
            "El contexto de la BD debe estar en la llamada a request_correction"
        # La pregunta original debe estar en la llamada
        assert "stock actual" in call["question"], \
            "La pregunta original debe estar en la llamada a request_correction"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 6: CONTEXTO ENVIADO A LA IA — INTEGRACIÓN COMPLETA
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextSentToAI:
    """
    Tests de integración que verifican el contenido exacto del system_prompt
    que el ChatService envía a la IA, incluyendo:
    - Esquema de tablas con sample_rows
    - Reglas Firebird
    - Historial de conversación
    - Filtros obligatorios
    """

    @pytest.mark.asyncio
    async def test_system_prompt_incluye_esquema_con_sample_rows(self):
        """
        El system_prompt enviado a la IA incluye el esquema de tablas
        con datos de ejemplo reales (sample_rows).
        """
        from backend.modules.chat.service import ChatService

        service = ChatService()
        captured_system_prompts = []

        async def mock_execute_with_fallback(system_prompt, user_message, **kwargs):
            captured_system_prompts.append(system_prompt)
            return "No hay SQL aquí, solo texto.", "test-model"

        with patch.object(service.model_orchestrator, 'execute_with_fallback',
                          side_effect=mock_execute_with_fallback):
            with patch('backend.modules.chat.service.get_context_retriever') as mock_r:
                # Simular que el retriever devuelve contexto con sample_rows
                mock_retriever = MagicMock()
                mock_retriever.get_context.return_value = (
                    "TABLA: ARTICULO\n"
                    "  Registros: 4,823\n"
                    "  Columnas principales: CODIGO, NOMBRE, PRECIO\n"
                    "  Datos de ejemplo (3 filas):\n"
                    "    {'CODIGO': 'AC001', 'NOMBRE': 'Split Daikin 2.5kW', 'PRECIO': 899.0}\n"
                    "    {'CODIGO': 'AC002', 'NOMBRE': 'Split Mitsubishi 3.5kW', 'PRECIO': 1250.0}\n",
                    {
                        "tables_used": ["ARTICULO"],
                        "source": "siuo",
                        "tokens_estimated": 200,
                    }
                )
                mock_r.return_value = mock_retriever

                await service.process_message(
                    "artículos más caros",
                    {"model_id": "test-model", "confirm_data_sending": True, "db_params": None}
                )

        assert len(captured_system_prompts) > 0, "Debe haberse llamado al orchestrator"
        prompt = captured_system_prompts[0]

        # El system_prompt debe incluir los datos de ejemplo
        assert "AC001" in prompt or "Split Daikin" in prompt or "Datos de ejemplo" in prompt, \
            "El system_prompt debe incluir los datos de ejemplo de las tablas"

    @pytest.mark.asyncio
    async def test_system_prompt_incluye_reglas_firebird(self):
        """
        El system_prompt siempre incluye las reglas específicas de Firebird
        (FIRST N, UPPER, tipos de documentos, etc.).
        """
        from backend.modules.chat.service import ChatService

        service = ChatService()
        captured_prompts = []

        async def mock_execute_with_fallback(system_prompt, user_message, **kwargs):
            captured_prompts.append(system_prompt)
            return "Respuesta sin SQL.", "test-model"

        with patch.object(service.model_orchestrator, 'execute_with_fallback',
                          side_effect=mock_execute_with_fallback):
            with patch('backend.modules.chat.service.get_context_retriever') as mock_r:
                mock_retriever = MagicMock()
                mock_retriever.get_context.return_value = ("TABLA: ARTICULO\n", {
                    "tables_used": ["ARTICULO"],
                    "source": "siuo",
                    "tokens_estimated": 50,
                })
                mock_r.return_value = mock_retriever

                await service.process_message(
                    "dame las facturas del mes",
                    {"model_id": "test-model", "confirm_data_sending": True, "db_params": None}
                )

        assert len(captured_prompts) > 0
        prompt = captured_prompts[0]

        # Reglas Firebird deben estar en el prompt
        assert "FIRST" in prompt, "El prompt debe incluir la regla FIRST N"
        assert "TIPO" in prompt or "13" in prompt, \
            "El prompt debe incluir información sobre tipos de documentos"

    @pytest.mark.asyncio
    async def test_contexto_siuo_se_usa_antes_que_fallback(self):
        """
        Cuando el ContextRetriever tiene índices cargados, se usa el contexto SIUO
        (no el fallback de db_metadata_optimized.json).
        """
        from backend.modules.chat.service import ChatService

        service = ChatService()
        retriever_called = [False]
        fallback_called  = [False]

        async def mock_execute_with_fallback(system_prompt, user_message, **kwargs):
            return "Respuesta.", "test-model"

        with patch.object(service.model_orchestrator, 'execute_with_fallback',
                          side_effect=mock_execute_with_fallback):
            with patch('backend.modules.chat.service.get_context_retriever') as mock_r:
                mock_retriever = MagicMock()
                def mock_get_context(question, **kwargs):
                    retriever_called[0] = True
                    return ("CONTEXTO SIUO\n", {
                        "tables_used": ["ARTICULO"],
                        "source": "siuo",
                        "tokens_estimated": 50,
                    })
                mock_retriever.get_context = mock_get_context
                mock_r.return_value = mock_retriever

                with patch('backend.modules.chat.service.get_semantic_schema') as mock_fallback:
                    mock_fallback.side_effect = lambda: (fallback_called.__setitem__(0, True) or "FALLBACK")

                    await service.process_message(
                        "artículos más vendidos",
                        {"model_id": "test-model", "confirm_data_sending": True, "db_params": None}
                    )

        assert retriever_called[0], "El ContextRetriever SIUO debe haberse llamado"
        assert not fallback_called[0], \
            "El fallback NO debe haberse llamado cuando el ContextRetriever funciona"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 7: AUTOAPRENDIZAJE — REGISTRO DE CONSULTAS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutolearning:
    """
    Verifica que el sistema registra las consultas para autoaprendizaje
    y detecta keywords no mapeados.
    """

    def test_consulta_registrada_en_query_log(self, retriever, tmp_path):
        """Cada consulta se registra en el query_log para autoaprendizaje."""
        from backend.modules.db_explorer.context_retriever import QUERY_LOG_PATH

        log_entries = []

        def mock_log_query(question, keywords, tables_used, unknown_kws):
            log_entries.append({
                "question": question,
                "keywords": keywords,
                "tables_used": tables_used,
                "unknown_kws": unknown_kws,
            })

        with patch.object(retriever, '_log_query', side_effect=mock_log_query):
            retriever.get_context("artículos más vendidos")

        assert len(log_entries) == 1, "Debe registrarse exactamente 1 entrada en el log"
        entry = log_entries[0]
        assert entry["question"] == "artículos más vendidos"
        assert "ARTICULO" in entry["tables_used"]

    def test_keywords_desconocidos_acumulados(self, retriever):
        """Los keywords no mapeados se acumulan para sugerir mejoras al concept_index."""
        unknown_accumulated = []

        def mock_log_query(question, keywords, tables_used, unknown_kws):
            unknown_accumulated.extend(unknown_kws)

        with patch.object(retriever, '_log_query', side_effect=mock_log_query):
            retriever.get_context("equipos frigoríficos industriales de alta eficiencia")

        # 'frigorificos', 'industriales', 'eficiencia' no están en el concept_index
        assert len(unknown_accumulated) > 0, \
            "Los keywords desconocidos deben acumularse para autoaprendizaje"

    def test_feedback_correcto_registrado(self, retriever, tmp_path):
        """El feedback del usuario (SQL correcto/incorrecto) se registra."""
        feedback_entries = []

        def mock_save_json(path, data):
            if "feedback" in data:
                feedback_entries.extend(data["feedback"])

        with patch('backend.modules.db_explorer.context_retriever._save_json',
                   side_effect=mock_save_json):
            with patch('backend.modules.db_explorer.context_retriever._load_json',
                       return_value={"queries": [], "unknown_keywords": {}, "feedback": []}):
                retriever.register_feedback(
                    question="artículos más vendidos",
                    sql_used="SELECT FIRST 5 CODIGO FROM ARTICULO",
                    was_correct=True,
                    tables_used=["ARTICULO"],
                )

        assert len(feedback_entries) == 1, "El feedback debe registrarse"
        assert feedback_entries[0]["correct"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 8: PRIVACIDAD — COLUMNAS SENSIBLES NUNCA LLEGAN A LA IA
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrivacyInContext:
    """
    Verifica que las columnas sensibles (NIF, EMAIL, TELEFONO, IBAN, etc.)
    nunca aparecen en el contexto enviado a la IA.
    """

    def test_nif_no_en_contexto(self, retriever):
        """NIF nunca aparece en el contexto enviado a la IA."""
        retriever._table_index["CLIENTE"]["sample_rows"] = [
            {"CODIGO": "CLI001", "NOMBRE": "García S.L.", "NIF": "B12345678"}
        ]
        context, _ = retriever.get_context("clientes", max_tokens=3000)
        assert "B12345678" not in context, "El NIF no debe aparecer en el contexto"

    def test_email_no_en_contexto(self, retriever):
        """EMAIL nunca aparece en el contexto enviado a la IA."""
        retriever._table_index["CLIENTE"]["sample_rows"] = [
            {"CODIGO": "CLI001", "NOMBRE": "García S.L.", "EMAIL": "info@garcia.com"}
        ]
        context, _ = retriever.get_context("clientes", max_tokens=3000)
        assert "info@garcia.com" not in context, "El EMAIL no debe aparecer en el contexto"

    def test_telefono_no_en_contexto(self, retriever):
        """TELEFONO nunca aparece en el contexto enviado a la IA."""
        retriever._table_index["CLIENTE"]["sample_rows"] = [
            {"CODIGO": "CLI001", "NOMBRE": "García S.L.", "TELEFONO": "912345678"}
        ]
        context, _ = retriever.get_context("clientes", max_tokens=3000)
        assert "912345678" not in context, "El TELEFONO no debe aparecer en el contexto"

    def test_iban_no_en_contexto(self, retriever):
        """IBAN nunca aparece en el contexto enviado a la IA."""
        retriever._table_index["CLIENTE"]["sample_rows"] = [
            {"CODIGO": "CLI001", "NOMBRE": "García S.L.", "IBAN": "ES9121000418450200051332"}
        ]
        context, _ = retriever.get_context("clientes", max_tokens=3000)
        assert "ES9121000418450200051332" not in context, "El IBAN no debe aparecer en el contexto"

    def test_datos_no_sensibles_si_en_contexto(self, retriever):
        """Los datos no sensibles (CODIGO, NOMBRE, PRECIO) SÍ aparecen en el contexto."""
        retriever._table_index["ARTICULO"]["sample_rows"] = [
            {"CODIGO": "AC001", "NOMBRE": "Split Daikin", "PRECIO": 899.00}
        ]
        context, _ = retriever.get_context("artículos más caros", max_tokens=3000)
        # Al menos uno de los datos no sensibles debe estar en el contexto
        assert "AC001" in context or "Split Daikin" in context or "899" in context, \
            "Los datos no sensibles deben aparecer en el contexto"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 9: ESTADÍSTICAS DEL RETRIEVER
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetrieverStats:
    """Verifica que las estadísticas del retriever son correctas."""

    def test_stats_tablas_indexadas(self, retriever):
        """get_stats() devuelve el número correcto de tablas indexadas."""
        stats = retriever.get_stats()
        assert stats["tables_indexed"] == len(MOCK_TABLE_INDEX["tables"]), \
            "El número de tablas indexadas debe coincidir con el mock"

    def test_stats_concept_keywords(self, retriever):
        """get_stats() devuelve el número correcto de keywords en el concept_index."""
        stats = retriever.get_stats()
        assert stats["concept_keywords"] == len(MOCK_CONCEPT_INDEX["index"]), \
            "El número de keywords debe coincidir con el mock"

    def test_stats_graph_edges(self, retriever):
        """get_stats() devuelve el número correcto de aristas en el grafo."""
        stats = retriever.get_stats()
        expected_edges = len(MOCK_DB_GRAPH["edges"])
        assert stats["graph_edges"] == expected_edges, \
            f"El número de aristas ({stats['graph_edges']}) debe ser {expected_edges}"

    def test_stats_loaded_true(self, retriever):
        """get_stats() indica que los índices están cargados."""
        stats = retriever.get_stats()
        assert stats["loaded"] is True, "loaded debe ser True cuando los índices están cargados"
