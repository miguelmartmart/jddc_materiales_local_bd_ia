"""
test_preguntas_2tablas.py — Tests e2e de preguntas que cruzan 2-3 tablas.

CAPA: e2e (requiere BD Firebird + Qwen3 LAN)
EJECUTAR: .venv/Scripts/pytest tests/e2e/test_preguntas_2tablas.py -v -s

INDEPENDENCIA:
  - Sin IPs ni tablas hardcodeadas. Todo desde test.properties vía conftest.py.
  - helpers.py centraliza la lógica de traza y auditoría de red.
  - Se salta si BD o Qwen3 no disponibles.

PROPÓSITO:
  Verificar el flujo completo para preguntas que requieren JOINs:
  pregunta → SIUO (2-3 tablas) → SQL con JOIN → BD → respuesta

JOINS TÍPICOS:
  - ARTICULO + DOCLIN (artículos más vendidos/comprados)
  - DOCCAB + CLIENTE (facturas por cliente)
  - DOCCAB + DOCLIN (total de líneas por documento)
  - DOCCAB + DOCLIN + ARTICULO (artículos en facturas)
  - DOCCAB + AGENTE (ventas por agente)
  - ARTICULO + ALMACEN/ESTALMACEN (stock por almacén)

REGRESIONES CUBIERTAS:
  - REG-001: artículos más vendidos → DOCLIN (no HISTORICOPRECIOS)
  - REG-002: artículos con más compras → DOCLIN (no FABARTFABASOC)
  - REG-003: SQL con LIMIT → FIRST N (Firebird)
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.e2e.helpers import (
    ask_and_trace,
    assert_has_number,
    assert_no_markdown,
    assert_response_valid,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ARTICULO + DOCLIN — artículos más vendidos/comprados
# ═══════════════════════════════════════════════════════════════════════════════

class TestArticuloDoclin:
    """
    Preguntas que cruzan ARTICULO y DOCLIN.
    REGRESIÓN CRÍTICA: antes mapeaba a HISTORICOPRECIOS o FABARTFABASOC.
    """

    FORBIDDEN = ["HISTORICOPRECIOS", "FOTOGRAF", "COMISART", "FABARTFABASOC"]

    @pytest.mark.asyncio
    async def test_articulos_mas_vendidos_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-001: artículos más vendidos → ARTICULO + DOCLIN (no HISTORICOPRECIOS)."""
        resp, _ = await ask_and_trace(
            chat_svc, "dime los artículos más vendidos", metaglass_ctx,
            test_name="articulos_mas_vendidos_metaglass",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)
        assert_has_number(resp, "artículos más vendidos")

    @pytest.mark.asyncio
    async def test_articulos_mas_vendidos_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-001: artículos más vendidos — cliente web."""
        resp, _ = await ask_and_trace(
            chat_svc, "ranking de artículos más vendidos", web_ctx,
            test_name="articulos_mas_vendidos_web",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)

    @pytest.mark.asyncio
    async def test_articulos_mas_comprados_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-002 CRÍTICA: artículos con más compras → DOCLIN (no FABARTFABASOC)."""
        resp, _ = await ask_and_trace(
            chat_svc, "dime los artículos con más compras", metaglass_ctx,
            test_name="articulos_mas_comprados_metaglass",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_articulos_mas_comprados_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-002 CRÍTICA: artículos con más compras — cliente web."""
        resp, _ = await ask_and_trace(
            chat_svc, "qué artículos se compran más", web_ctx,
            test_name="articulos_mas_comprados_web",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)

    @pytest.mark.asyncio
    async def test_articulos_por_familia_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Artículos más vendidos por familia → ARTICULO + DOCLIN agrupado por FAMILIA."""
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos artículos se han vendido de cada familia", metaglass_ctx,
            test_name="articulos_por_familia_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCCAB + CLIENTE — facturas por cliente
# ═══════════════════════════════════════════════════════════════════════════════

class TestDoccabCliente:
    """
    Preguntas que cruzan DOCCAB y CLIENTE.
    Verifican que el JOIN entre documentos y clientes funciona correctamente.
    """

    @pytest.mark.asyncio
    async def test_clientes_con_mas_facturas_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Clientes con más facturas → DOCCAB JOIN CLIENTE."""
        resp, _ = await ask_and_trace(
            chat_svc, "qué clientes tienen más facturas", metaglass_ctx,
            test_name="clientes_mas_facturas_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_total_facturado_por_cliente_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """Total facturado por cliente → DOCCAB JOIN CLIENTE con SUM(TOTAL)."""
        resp, _ = await ask_and_trace(
            chat_svc, "cuánto hemos facturado a cada cliente", web_ctx,
            test_name="total_facturado_por_cliente_web",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)
        assert_has_number(resp, "total facturado por cliente")

    @pytest.mark.asyncio
    async def test_ultimas_facturas_con_cliente_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """Últimas facturas con nombre de cliente → DOCCAB JOIN CLIENTE."""
        resp, _ = await ask_and_trace(
            chat_svc, "dame las últimas 10 facturas con el nombre del cliente", web_ctx,
            test_name="ultimas_facturas_con_cliente_web",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCCAB + AGENTE — ventas por agente
# ═══════════════════════════════════════════════════════════════════════════════

class TestDoccabAgente:
    """
    Preguntas que cruzan DOCCAB y AGENTE.
    Verifican el ranking de ventas por agente comercial.
    """

    @pytest.mark.asyncio
    async def test_ventas_por_agente_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Ventas por agente → DOCCAB JOIN AGENTE con SUM(TOTAL)."""
        resp, _ = await ask_and_trace(
            chat_svc, "cuánto ha vendido cada agente", metaglass_ctx,
            test_name="ventas_por_agente_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)
        assert_has_number(resp, "ventas por agente")

    @pytest.mark.asyncio
    async def test_ventas_por_agente_este_año_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """Ventas por agente este año → DOCCAB JOIN AGENTE con filtro de fecha."""
        resp, _ = await ask_and_trace(
            chat_svc, "cuánto ha vendido cada agente este año", web_ctx,
            test_name="ventas_por_agente_año_web",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)

    @pytest.mark.asyncio
    async def test_agente_mas_ventas_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """El agente con más ventas → DOCCAB JOIN AGENTE ORDER BY SUM DESC FIRST 1."""
        resp, _ = await ask_and_trace(
            chat_svc, "cuál es el agente que más ha vendido", metaglass_ctx,
            test_name="agente_mas_ventas_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCCAB + DOCLIN + ARTICULO — 3 tablas
# ═══════════════════════════════════════════════════════════════════════════════

class TestTresTablas:
    """
    Preguntas que cruzan 3 tablas: DOCCAB + DOCLIN + ARTICULO.
    Son las consultas más complejas del sistema.
    """

    FORBIDDEN = ["HISTORICOPRECIOS", "FOTOGRAF", "COMISART", "FABARTFABASOC"]

    @pytest.mark.asyncio
    async def test_articulos_en_facturas_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """
        Artículos que aparecen en facturas →
        ARTICULO JOIN DOCLIN JOIN DOCCAB WHERE TIPO=13.
        """
        resp, _ = await ask_and_trace(
            chat_svc, "qué artículos se han facturado este mes", metaglass_ctx,
            test_name="articulos_en_facturas_metaglass",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_total_ventas_por_articulo_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        Total de ventas por artículo →
        ARTICULO JOIN DOCLIN JOIN DOCCAB WHERE TIPO IN (11,13) GROUP BY ARTICULO.
        """
        resp, _ = await ask_and_trace(
            chat_svc, "total de ventas por artículo", web_ctx,
            test_name="total_ventas_por_articulo_web",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)
        assert_has_number(resp, "total ventas por artículo")

    @pytest.mark.asyncio
    async def test_articulos_pedidos_a_proveedor_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        Artículos pedidos a proveedor →
        ARTICULO JOIN DOCLIN JOIN DOCCAB WHERE TIPO=12.
        REGRESIÓN: 'compras' no debe mapear a FABARTFABASOC.
        """
        resp, _ = await ask_and_trace(
            chat_svc, "qué artículos hemos pedido a proveedores", web_ctx,
            test_name="articulos_pedidos_proveedor_web",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)

    @pytest.mark.asyncio
    async def test_ranking_articulos_mas_vendidos_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """
        Ranking de artículos más vendidos →
        ARTICULO JOIN DOCLIN JOIN DOCCAB ORDER BY SUM(CANTIDAD) DESC.
        """
        resp, _ = await ask_and_trace(
            chat_svc, "ranking de los 10 artículos más vendidos", web_ctx,
            test_name="ranking_articulos_mas_vendidos_web",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)
        assert_has_number(resp, "ranking artículos más vendidos")


# ═══════════════════════════════════════════════════════════════════════════════
# Filtros de fecha — preguntas con rango temporal
# ═══════════════════════════════════════════════════════════════════════════════

class TestFiltrosFecha:
    """
    Preguntas con filtros de fecha.
    Verifican que el SQL generado usa EXTRACT o comparación de fechas correctamente.
    """

    @pytest.mark.asyncio
    async def test_facturas_este_mes_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Facturas de este mes → DOCCAB WHERE TIPO=13 AND EXTRACT(MONTH FROM FECHA)."""
        resp, _ = await ask_and_trace(
            chat_svc, "facturas de este mes", metaglass_ctx,
            test_name="facturas_este_mes_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_total_facturado_este_mes_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Total facturado este mes → DOCCAB WHERE TIPO=13 AND fecha actual."""
        resp, _ = await ask_and_trace(
            chat_svc, "cuánto hemos facturado este mes", metaglass_ctx,
            test_name="total_facturado_este_mes_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)
        assert_has_number(resp, "total facturado este mes")

    @pytest.mark.asyncio
    async def test_ventas_este_año_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """Total de ventas de este año → DOCCAB WHERE TIPO IN (11,13) AND año actual."""
        resp, _ = await ask_and_trace(
            chat_svc, "total de ventas de este año", web_ctx,
            test_name="ventas_este_año_web",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)
        assert_has_number(resp, "total ventas este año")

    @pytest.mark.asyncio
    async def test_pedidos_pendientes_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Pedidos pendientes → DOCCAB WHERE TIPO=12 AND ESTADO pendiente."""
        resp, _ = await ask_and_trace(
            chat_svc, "pedidos de clientes pendientes", metaglass_ctx,
            test_name="pedidos_pendientes_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Búsquedas por nombre — LIKE/UPPER (REG-004)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBusquedasNombre:
    """
    Preguntas con búsqueda por nombre (LIKE).
    Verifican que el normalizador convierte ILIKE → UPPER(col) LIKE UPPER(val).
    """

    @pytest.mark.asyncio
    async def test_buscar_cliente_por_nombre_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Buscar cliente por nombre → CLIENTE WHERE UPPER(RAZONSOCIAL) LIKE UPPER(%)."""
        resp, _ = await ask_and_trace(
            chat_svc, "busca clientes que se llamen García", metaglass_ctx,
            test_name="buscar_cliente_garcia_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        # Puede no haber clientes García — la respuesta puede ser "no encontré"
        assert resp, "Respuesta vacía"
        assert_no_markdown(resp)

    @pytest.mark.asyncio
    async def test_buscar_articulo_por_nombre_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """Buscar artículo por nombre → ARTICULO WHERE UPPER(NOMBRE) LIKE UPPER(%)."""
        resp, _ = await ask_and_trace(
            chat_svc, "busca artículos que contengan 'split' en el nombre", web_ctx,
            test_name="buscar_articulo_split_web",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert resp, "Respuesta vacía"
        assert len(resp) > 5

    @pytest.mark.asyncio
    async def test_buscar_proveedor_por_nombre_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """Buscar proveedor por nombre → PROVEED WHERE UPPER(NOMBRE) LIKE UPPER(%)."""
        resp, _ = await ask_and_trace(
            chat_svc, "busca proveedores de climatización", metaglass_ctx,
            test_name="buscar_proveedor_climatizacion_metaglass",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert resp, "Respuesta vacía"
        assert_no_markdown(resp)
