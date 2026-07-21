"""
test_sql03_compras.py — Tests QA: módulo SQL-03 (Compras: del presupuesto a la factura).

CAPA: qa_sql_obras (requiere Qwen3 LAN; BD real o simulador según el caso)
EJECUTAR: .venv/Scripts/pytest tests/qa_sql_obras/test_sql03_compras.py -v -s
FUENTE: form_automation/docs/manual_sql_obras/SQL-03.md — secciones 001-011
        (repo pendiente-fact, fuera de este submódulo)

TABLAS REALES CONFIRMADAS (backend/modules/db_simulator/schema.py):
  PROVEED, DOCCAB, DOCLIN, DOCDESTINO
  (todos los documentos de compra son filas de DOCCAB/DOCLIN — no hay tablas
  separadas de "PresupuestoProveedor"/"PedidoProveedor"/etc.; se distinguen
  por DOCCAB.TIPO)

MAPEO DOCCAB.TIPO para compras (verificado con el usuario — ver
backend/modules/chat/DEVIA.MD, entrada 25/06/2026, y
backend/modules/chat/deep_analysis/phase5.py línea ~200-201):
  TIPO=10 → Presupuesto de proveedor   (SQL-03-002)
  TIPO=11 → Pedido de proveedor        (SQL-03-004)
  TIPO=12 → Albarán de proveedor       (SQL-03-006)
  TIPO=13 → Factura de proveedor       (SQL-03-009)
El proveedor de un documento de compra vive en DOCCAB.CODCLIENTE (mismo
campo que "cliente" en documentos de venta — es un campo de "tercero"
compartido; la distinción es por TIPO, no por columna separada). NO existe
columna CODPROVEED en DOCCAB.

TRAZABILIDAD (SQL-03-009 "doble clic navega al documento relacionado",
SQL-03-006 regla de bloqueo "albarán facturado"): se modela con DOCDESTINO
(CODDOCUMENTO → CODDOCUMENTODESTINO), tabla confirmada en schema.py. Un
albarán de proveedor (TIPO=12) que aparece como CODDOCUMENTO de una fila de
DOCDESTINO cuyo destino es una factura (TIPO=13) es, por definición, un
albarán ya facturado (candidato a la regla de bloqueo de SQL-03-006).

CARENCIAS DE ESQUEMA — NO se generan tests sobre esto (ver DEVIA.MD, fila de
esta sesión):
  - Portes, número de bultos, forma de envío (columnas de cabecera de
    compra mencionadas en SQL-03-009) NO están en TABLE_COLUMNS["DOCCAB"].
  - La columna "Servido" por línea (SQL-03-002, indica si una línea de
    presupuesto/pedido ya pasó a documento superior) NO está en
    TABLE_COLUMNS["DOCLIN"] (solo existe DOCDESTINO a nivel de documento
    completo, no de línea).
  - El estado de cabecera "Estado del Pedido" con sus 4 valores textuales
    (sin servir / servido parcialmente / servido totalmente / Forzar
    servido — SQL-03-004) no tiene un mapeo de códigos confirmado: DOCCAB
    sí tiene columnas ESTADO/ESTADOPEND/ESTADOPENDVENCOM, pero
    `backend/core/config/knowledge/tables/DOCCAB.json` marca la semántica
    de ESTADOPEND como no verificada ("ESTADOPEND en presupuestos: {'?': 0}").
    Por eso el test relacionado con "Forzar servido" (más abajo) usa
    `assert_response_valid` en vez de `assert_has_number`/keywords exactos:
    no se afirma qué código representa cada estado, solo que el chat da
    una respuesta válida a una pregunta de negocio realista sobre el tema.

PRIMERA TANDA para SQL-03 — mismo criterio que SQL-02 (proof of concept que
cruza modelo 30B/8B x BD real/simulador). Ver "Registro de progreso" en
tests/qa_sql_obras/DEVIA.MD.

NOTA: no se ha podido ejecutar esta suite en el entorno donde se escribió
(sin acceso a la LAN JDDC ni al backend arrancado) — pendiente de que el
usuario los corra en su máquina y reporte resultados. Solo se verificó
`pytest --collect-only`.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.qa_sql_obras.helpers import (
    MODEL_8B,
    MODEL_30B,
    ask_and_trace,
    assert_has_number,
    assert_response_valid,
    with_overrides,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-03-002 — Presupuestos de proveedores (DOCCAB TIPO=10)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPresupuestosProveedor:

    @pytest.mark.asyncio
    async def test_cuantos_presupuestos_proveedor_simulador(self, chat_svc, web_ctx, test_config, simulator_ready, qwen3_url):
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(web_ctx, model_id=MODEL_8B, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos presupuestos de proveedor hay", ctx,
            test_name="sql03_cuantos_presupuestos_proveedor_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántos presupuestos de proveedor hay")

    @pytest.mark.asyncio
    async def test_cuantos_presupuestos_proveedor_real_30b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        ctx = with_overrides(web_ctx, model_id=MODEL_30B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos presupuestos de proveedor hay registrados", ctx,
            test_name="sql03_cuantos_presupuestos_proveedor_real_30b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántos presupuestos de proveedor hay registrados")


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-03-004 — Pedidos de proveedores (DOCCAB TIPO=11)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPedidosProveedor:

    @pytest.mark.asyncio
    async def test_cuantos_pedidos_proveedor_real_8b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        ctx = with_overrides(web_ctx, model_id=MODEL_8B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos pedidos de proveedor hay", ctx,
            test_name="sql03_cuantos_pedidos_proveedor_real_8b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántos pedidos de proveedor hay")

    @pytest.mark.asyncio
    async def test_pedidos_proveedor_forzados_servir_simulador(self, chat_svc, metaglass_ctx, test_config, simulator_ready, qwen3_url):
        """
        SQL-03-004: estado "Forzar servido" (cierre manual de un pedido de
        proveedor incompleto — deja de contar como pendiente). No se afirma
        un código de ESTADO/ESTADOPEND concreto (semántica no verificada,
        ver docstring del módulo) — solo se comprueba que el chat da una
        respuesta válida a la pregunta de negocio.
        """
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(metaglass_ctx, model_id=MODEL_8B, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc,
            "hay pedidos de proveedor que se hayan forzado a servir sin completarse del todo",
            ctx,
            test_name="sql03_pedidos_proveedor_forzados_servir_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-03-006 — Albaranes de proveedores (DOCCAB TIPO=12)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlbaranesProveedor:

    @pytest.mark.asyncio
    async def test_cuantos_albaranes_proveedor_simulador(self, chat_svc, web_ctx, test_config, simulator_ready, qwen3_url):
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(web_ctx, model_id=MODEL_8B, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántos albaranes de proveedor hay", ctx,
            test_name="sql03_cuantos_albaranes_proveedor_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántos albaranes de proveedor hay")

    @pytest.mark.asyncio
    async def test_albaranes_proveedor_ya_facturados_real_30b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        """
        SQL-03-006: "una vez facturado, el albarán no se puede modificar
        hasta que se elimine la factura asociada". Se pregunta por los
        albaranes de proveedor ya facturados (consultable vía DOCDESTINO,
        tabla confirmada) — no se pide al chat que verifique la regla de
        bloqueo de UI en sí (eso no es una consulta SQL).
        """
        ctx = with_overrides(web_ctx, model_id=MODEL_30B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc,
            "qué albaranes de proveedor ya han sido facturados",
            ctx,
            test_name="sql03_albaranes_proveedor_ya_facturados_real_30b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-03-009 — Facturas de proveedores (DOCCAB TIPO=13)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFacturasProveedor:

    @pytest.mark.asyncio
    async def test_cuantas_facturas_proveedor_hay_real_8b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        ctx = with_overrides(web_ctx, model_id=MODEL_8B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc, "cuántas facturas de proveedor hay", ctx,
            test_name="sql03_cuantas_facturas_proveedor_real_8b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_has_number(resp, "cuántas facturas de proveedor hay")

    @pytest.mark.asyncio
    async def test_total_facturado_por_proveedor_simulador(self, chat_svc, web_ctx, test_config, simulator_ready, qwen3_url):
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(web_ctx, model_id=MODEL_8B, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc, "cuánto se ha facturado en total a cada proveedor", ctx,
            test_name="sql03_total_facturado_por_proveedor_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)

    @pytest.mark.asyncio
    async def test_lista_facturas_proveedor_por_agente_real_30b(self, chat_svc, web_ctx, test_config, db_driver, qwen3_url):
        ctx = with_overrides(web_ctx, model_id=MODEL_30B, db_mode="real")
        resp, _ = await ask_and_trace(
            chat_svc, "dame las facturas de proveedor agrupadas por agente", ctx,
            test_name="sql03_lista_facturas_proveedor_por_agente_real_30b",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.web_max_len,
        )
        assert_response_valid(resp, test_config.web_max_len)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL-03-009/011 — Trazabilidad de documentos de compra (DOCDESTINO)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrazabilidadCompras:

    @pytest.mark.asyncio
    async def test_pedidos_proveedor_sin_convertir_a_documento_superior_simulador(
        self, chat_svc, metaglass_ctx, test_config, simulator_ready, qwen3_url
    ):
        """
        SQL-03-001/002/004: flujo presupuesto → pedido → albarán → factura,
        con "Enviar a" documento superior. Un pedido de proveedor (TIPO=11)
        que no aparece como CODDOCUMENTO en DOCDESTINO todavía no se ha
        enviado a ningún albarán/factura (tabla DOCDESTINO confirmada).
        """
        if not simulator_ready:
            pytest.skip("Simulador sin datos activos (no se generan aquí — ver simulator-data-rule)")
        ctx = with_overrides(metaglass_ctx, model_id=MODEL_8B, db_mode="simulator")
        resp, _ = await ask_and_trace(
            chat_svc,
            "qué pedidos de proveedor todavía no se han pasado a albarán o factura",
            ctx,
            test_name="sql03_pedidos_proveedor_sin_convertir_simulador",
            allowed_networks=test_config.allowed_networks,
            max_len=test_config.metaglass_max_len,
        )
        assert_response_valid(resp, test_config.metaglass_max_len, allow_markdown=False)
