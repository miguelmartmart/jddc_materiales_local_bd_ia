"""
test_regresiones.py — Tests de regresión conocida.

CAPA: e2e (requiere BD Firebird + Qwen3 LAN)
EJECUTAR: .venv/Scripts/pytest tests/e2e/test_regresiones.py -v -s

INDEPENDENCIA:
  - Sin IPs ni tablas hardcodeadas. Todo desde test.properties vía conftest.py.
  - helpers.py centraliza la lógica de traza y auditoría de red.

PROPÓSITO:
  Detectar regresiones conocidas — bugs que ya ocurrieron y se corrigieron.
  Si alguno de estos tests falla, significa que el bug ha vuelto.

REGRESIONES DOCUMENTADAS:
  REG-001: artículos más vendidos → antes mapeaba a HISTORICOPRECIOS (incorrecto)
           Causa: SIUO no tenía el concepto "ventas" mapeado a DOCLIN
           Fix: añadir "ventas", "vendido", "vender" al índice de DOCLIN

  REG-002: artículos con más compras → antes devolvía FABARTFABASOC (incorrecto)
           Causa: SIUO confundía "compras" con fabricación
           Fix: añadir "compra", "comprado", "comprar" al índice de DOCLIN

  REG-003: SQL con LIMIT → Firebird no soporta LIMIT, debe ser FIRST N
           Causa: la IA generaba LIMIT en lugar de FIRST
           Fix: FirebirdSQLNormalizer convierte LIMIT → FIRST N

  REG-004: SQL con ILIKE → Firebird no soporta ILIKE
           Causa: la IA generaba ILIKE para búsquedas case-insensitive
           Fix: FirebirdSQLNormalizer convierte ILIKE → UPPER(col) LIKE UPPER(val)
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.e2e.helpers import ask_and_trace, assert_response_valid, assert_no_markdown


# ═══════════════════════════════════════════════════════════════════════════════
# REG-001: artículos más vendidos → HISTORICOPRECIOS (incorrecto)
# ═══════════════════════════════════════════════════════════════════════════════

class TestReg001ArticulosMasVendidos:
    """
    REG-001: La pregunta 'artículos más vendidos' debe usar DOCLIN,
    NO HISTORICOPRECIOS, FOTOGRAF ni COMISART.
    """

    FORBIDDEN = ["HISTORICOPRECIOS", "FOTOGRAF", "COMISART", "FABARTFABASOC"]

    @pytest.mark.asyncio
    async def test_articulos_mas_vendidos_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-001 — MetaGlass."""
        resp, _ = await ask_and_trace(
            chat_svc, "dime los artículos más vendidos", metaglass_ctx,
            test_name="REG-001_articulos_mas_vendidos_metaglass",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_articulos_mas_vendidos_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-001 — Web."""
        resp, _ = await ask_and_trace(
            chat_svc, "ranking de artículos más vendidos", web_ctx,
            test_name="REG-001_articulos_mas_vendidos_web",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)


# ═══════════════════════════════════════════════════════════════════════════════
# REG-002: artículos con más compras → FABARTFABASOC (incorrecto)
# ═══════════════════════════════════════════════════════════════════════════════

class TestReg002ArticulosMasCompras:
    """
    REG-002 CRÍTICA: La pregunta 'artículos con más compras' debe usar DOCLIN,
    NO FABARTFABASOC, HISTORICOPRECIOS ni FOTOGRAF.
    """

    FORBIDDEN = ["HISTORICOPRECIOS", "FOTOGRAF", "COMISART", "FABARTFABASOC"]

    @pytest.mark.asyncio
    async def test_articulos_mas_compras_metaglass(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-002 CRÍTICA — MetaGlass."""
        resp, _ = await ask_and_trace(
            chat_svc, "dime los artículos con más compras", metaglass_ctx,
            test_name="REG-002_articulos_mas_compras_metaglass",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)

    @pytest.mark.asyncio
    async def test_articulos_mas_compras_web(
        self, chat_svc, web_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-002 CRÍTICA — Web."""
        resp, _ = await ask_and_trace(
            chat_svc, "qué artículos se compran más", web_ctx,
            test_name="REG-002_articulos_mas_compras_web",
            allowed_networks=test_config.allowed_networks,
            forbidden_keywords=self.FORBIDDEN,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)


# ═══════════════════════════════════════════════════════════════════════════════
# REG-003: SQL con LIMIT → debe ser FIRST N (Firebird)
# ═══════════════════════════════════════════════════════════════════════════════

class TestReg003LimitToFirst:
    """
    REG-003: El normalizador SQL debe convertir LIMIT → FIRST N.
    Este test verifica que la respuesta llega (no falla por SQL inválido).
    """

    @pytest.mark.asyncio
    async def test_listado_no_falla_por_limit(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-003: Si la IA genera LIMIT, el normalizador lo convierte y la BD responde."""
        resp, _ = await ask_and_trace(
            chat_svc, "dame los 10 artículos más caros", metaglass_ctx,
            test_name="REG-003_limit_to_first",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        # Si llegamos aquí sin excepción, el normalizador funcionó
        assert resp, "La respuesta está vacía — posible error de SQL con LIMIT"
        assert_no_markdown(resp)


# ═══════════════════════════════════════════════════════════════════════════════
# REG-004: SQL con ILIKE → debe ser UPPER(col) LIKE UPPER(val)
# ═══════════════════════════════════════════════════════════════════════════════

class TestReg004IlikeToUpper:
    """
    REG-004: El normalizador SQL debe convertir ILIKE → UPPER(col) LIKE UPPER(val).
    """

    @pytest.mark.asyncio
    async def test_busqueda_nombre_no_falla_por_ilike(
        self, chat_svc, metaglass_ctx, test_config, db_driver, qwen3_url
    ):
        """REG-004: Búsqueda por nombre no falla por ILIKE."""
        resp, _ = await ask_and_trace(
            chat_svc, "busca artículos que contengan 'split' en el nombre", metaglass_ctx,
            test_name="REG-004_ilike_to_upper",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert resp, "La respuesta está vacía — posible error de SQL con ILIKE"
