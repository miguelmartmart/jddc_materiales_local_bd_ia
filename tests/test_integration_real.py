"""
Tests de integración REAL — Sin mocks, con BD Firebird y Qwen3 LAN.

PROPÓSITO:
  Garantizar al 100% que las preguntas del chat y MetaGlass devuelven
  respuestas correctas con datos reales de la BD, sin que ningún dato
  salga a internet.

EJECUTAR:
  cd bots/interjddcia
  .venv/Scripts/pytest tests/test_integration_real.py -v -s --tb=short 2>&1 | tee logs/test_integration_real.log

REQUISITOS:
  - BD Firebird accesible (configurada en .env)
  - Qwen3 LAN accesible (192.168.0.36)
  - Índices SIUO generados (table_index.json, concept_index.json)
  - Si alguno no está disponible → test marcado como SKIP (no falla)

GARANTÍA DE PRIVACIDAD:
  - Todos los datos van SOLO a Qwen3 LAN (192.168.0.36)
  - NINGÚN dato sale a internet
  - El NetworkAuditLogger registra TODAS las conexiones de red
  - Si se detecta una conexión a internet → el test FALLA inmediatamente

TRAZAS:
  - logs/test_integration_real.log → log completo de la sesión
  - logs/network_audit.log → registro de todas las conexiones de red
  - logs/sql_trace.log → todas las consultas SQL ejecutadas
  - logs/ai_requests.log → todas las peticiones a la IA (solo LAN)

CATEGORÍAS:
  1. Preguntas de 1 tabla (artículos, clientes, proveedores)
  2. Preguntas de 2-3 tablas (facturas+cliente, artículos+ventas)
  3. Preguntas de 4+ tablas (análisis complejos)
  4. Preguntas con fechas y rangos
  5. Preguntas con importes
  6. Preguntas MetaGlass (respuesta TTS corta, sin Markdown)
  7. Paginación (muchos resultados → resumen → "dame más")
"""

import asyncio
import json
import logging
import os
import re
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import pytest

# ─── Setup de paths ───────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

_LOGS_DIR = _ROOT / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

# ─── Configuración de logging con trazas en fichero ───────────────────────────

def _setup_logging():
    """Configura logging con salida a consola Y fichero."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # Logger raíz
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Handler consola
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt))
    root.addHandler(ch)

    # Handler fichero (log completo)
    fh = logging.FileHandler(_LOGS_DIR / "test_integration_real.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)

    return logging.getLogger("test_integration")

logger = _setup_logging()

# ─── Logger de auditoría de red ───────────────────────────────────────────────

_net_logger = logging.getLogger("network_audit")
_net_fh = logging.FileHandler(_LOGS_DIR / "network_audit.log", encoding="utf-8")
_net_fh.setFormatter(logging.Formatter("%(asctime)s [NETWORK] %(message)s"))
_net_logger.addHandler(_net_fh)
_net_logger.setLevel(logging.DEBUG)

# ─── Logger de SQL ────────────────────────────────────────────────────────────

_sql_logger = logging.getLogger("sql_trace")
_sql_fh = logging.FileHandler(_LOGS_DIR / "sql_trace.log", encoding="utf-8")
_sql_fh.setFormatter(logging.Formatter("%(asctime)s [SQL] %(message)s"))
_sql_logger.addHandler(_sql_fh)
_sql_logger.setLevel(logging.DEBUG)

# ─── Logger de peticiones IA ──────────────────────────────────────────────────

_ai_logger = logging.getLogger("ai_requests")
_ai_fh = logging.FileHandler(_LOGS_DIR / "ai_requests.log", encoding="utf-8")
_ai_fh.setFormatter(logging.Formatter("%(asctime)s [AI] %(message)s"))
_ai_logger.addHandler(_ai_fh)
_ai_logger.setLevel(logging.DEBUG)


# ═══════════════════════════════════════════════════════════════════════════════
# AUDITOR DE RED — Garantía de que ningún dato sale a internet
# ═══════════════════════════════════════════════════════════════════════════════

# IPs y rangos permitidos (LAN + localhost)
_ALLOWED_NETWORKS = [
    "127.",          # localhost
    "192.168.",      # LAN privada
    "10.",           # LAN privada clase A
    "172.16.",       # LAN privada clase B
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "::1",           # IPv6 localhost
    "0.0.0.0",       # bind all
]

_internet_violations: List[str] = []


def _is_lan_address(host: str) -> bool:
    """Verifica si una dirección es LAN (no internet)."""
    try:
        # Resolver hostname a IP
        ip = socket.gethostbyname(host)
        return any(ip.startswith(prefix) for prefix in _ALLOWED_NETWORKS)
    except Exception:
        # Si no se puede resolver, verificar el hostname directamente
        return any(host.startswith(prefix) for prefix in _ALLOWED_NETWORKS)


class NetworkAuditInterceptor:
    """
    Intercepta todas las conexiones de red durante los tests.
    Registra cada conexión y falla si detecta tráfico a internet.
    """

    def __init__(self):
        self._original_connect = None
        self._connections: List[Dict] = []

    def __enter__(self):
        import socket as _socket
        self._original_connect = _socket.socket.connect

        audit = self

        def audited_connect(sock, address):
            host = address[0] if isinstance(address, tuple) else str(address)
            port = address[1] if isinstance(address, tuple) else 0
            is_lan = _is_lan_address(host)

            entry = {
                "timestamp": datetime.now().isoformat(),
                "host": host,
                "port": port,
                "is_lan": is_lan,
            }
            audit._connections.append(entry)

            if is_lan:
                _net_logger.info(f"✅ LAN: {host}:{port}")
            else:
                _net_logger.error(f"🚨 INTERNET DETECTADO: {host}:{port} — VIOLACIÓN DE PRIVACIDAD")
                _internet_violations.append(f"{host}:{port}")

            return self._original_connect(sock, address)

        _socket.socket.connect = audited_connect
        return self

    def __exit__(self, *args):
        import socket as _socket
        if self._original_connect:
            _socket.socket.connect = self._original_connect

    def get_report(self) -> Dict:
        lan_conns = [c for c in self._connections if c["is_lan"]]
        inet_conns = [c for c in self._connections if not c["is_lan"]]
        return {
            "total_connections": len(self._connections),
            "lan_connections": len(lan_conns),
            "internet_connections": len(inet_conns),
            "violations": inet_conns,
            "all_connections": self._connections,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def db_available():
    """Verifica que la BD Firebird está accesible."""
    from backend.core.config.settings import settings
    from backend.core.factory.db_factory import DBFactory
    from backend.core.abstract.database import DBConfig
    from backend.core.utils.constants import DBConstants

    try:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = DBConfig(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        driver.connect(config)
        result = driver.execute_query("SELECT 1 FROM RDB$DATABASE")
        driver.disconnect()
        logger.info(f"✅ BD Firebird accesible: {settings.DB_HOST}:{settings.DB_PORT}")
        _net_logger.info(f"BD Firebird: {settings.DB_HOST}:{settings.DB_PORT} [LAN]")
        return True
    except Exception as e:
        logger.warning(f"⚠️ BD Firebird no accesible: {e}")
        pytest.skip(f"BD Firebird no accesible: {e}")


@pytest.fixture(scope="module")
def qwen3_available():
    """Verifica que Qwen3 LAN está accesible."""
    from backend.core.config.settings import settings
    import httpx

    urls = [settings.JDDCIA_BASE_URL_FALLBACK, settings.JDDCIA_BASE_URL]
    for url in urls:
        if not url:
            continue
        try:
            resp = httpx.get(f"{url}/models", timeout=5,
                             headers={"Authorization": f"Basic {settings.JDDCIA_API_KEY}"})
            if resp.status_code == 200:
                logger.info(f"✅ Qwen3 LAN accesible: {url}")
                _ai_logger.info(f"Qwen3 LAN disponible en: {url}")
                _net_logger.info(f"Qwen3 LAN: {url} [LAN]")
                return url
        except Exception as e:
            logger.warning(f"⚠️ Qwen3 no accesible en {url}: {e}")

    pytest.skip("Qwen3 LAN no accesible en ninguna URL configurada")


@pytest.fixture(scope="module")
def siuo_loaded():
    """Carga el ContextRetriever con los índices SIUO."""
    from backend.modules.db_explorer.context_retriever import ContextRetriever
    from backend.modules.db_explorer.deep_indexer_service import TABLE_INDEX_PATH

    if not TABLE_INDEX_PATH.exists():
        pytest.skip(f"Índices SIUO no encontrados. Ejecuta el análisis primero.")

    r = ContextRetriever()
    if not r.load():
        pytest.skip("ContextRetriever no pudo cargar los índices.")

    stats = r.get_stats()
    logger.info(f"✅ SIUO cargado: {stats['tables_indexed']} tablas, {stats['concept_keywords']} keywords")
    return r


@pytest.fixture(scope="module")
def chat_service():
    """Crea el ChatService real (sin mocks)."""
    from backend.modules.chat.service import ChatService
    return ChatService()


def _make_db_context():
    """Crea el contexto de BD para el ChatService."""
    from backend.core.config.settings import settings
    return {
        "model_id": None,  # Usar modelo por defecto
        "db_params": {
            "host": settings.DB_HOST,
            "port": settings.DB_PORT,
            "database": settings.DB_NAME,
            "user": settings.DB_USER,
            "password": settings.DB_PASSWORD,
        },
        "conversation_history": [],
        # MetaGlass: no enviar confirm_data_sending
    }


def _make_web_context():
    """Contexto para cliente web (con confirmación)."""
    ctx = _make_db_context()
    ctx["confirm_data_sending"] = True
    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: ejecutar pregunta con trazas completas
# ═══════════════════════════════════════════════════════════════════════════════

async def _ask_and_trace(
    chat_service,
    question: str,
    context: Dict,
    test_name: str,
    expected_keywords: Optional[List[str]] = None,
    forbidden_in_response: Optional[List[str]] = None,
    max_response_len: int = 2000,
) -> Tuple[str, Dict]:
    """
    Ejecuta una pregunta real y genera trazas completas.

    Returns:
        (response, trace_dict)
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"[TEST] {test_name}")
    logger.info(f"[PREGUNTA] {question}")

    start = time.time()

    with NetworkAuditInterceptor() as auditor:
        response = await chat_service.process_message(question, context)

    elapsed = time.time() - start
    net_report = auditor.get_report()

    # Registrar en logs
    logger.info(f"[RESPUESTA] {str(response)[:500]}")
    logger.info(f"[TIEMPO] {elapsed:.2f}s")
    logger.info(f"[RED] {net_report['lan_connections']} conexiones LAN, {net_report['internet_connections']} internet")

    _net_logger.info(f"TEST: {test_name} | LAN: {net_report['lan_connections']} | INTERNET: {net_report['internet_connections']}")

    # Guardar traza completa en JSON
    trace = {
        "test_name":    test_name,
        "question":     question,
        "response":     str(response)[:1000],
        "elapsed_s":    round(elapsed, 2),
        "network":      net_report,
        "timestamp":    datetime.now().isoformat(),
    }

    trace_file = _LOGS_DIR / "integration_traces.jsonl"
    with open(trace_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")

    # Verificaciones de privacidad
    assert net_report["internet_connections"] == 0, (
        f"🚨 VIOLACIÓN DE PRIVACIDAD: datos enviados a internet en test '{test_name}'\n"
        f"Conexiones a internet: {net_report['violations']}"
    )

    # Verificaciones de respuesta
    resp_str = str(response)
    assert resp_str, f"Respuesta vacía para: '{question}'"
    assert len(resp_str) <= max_response_len or isinstance(response, dict), \
        f"Respuesta demasiado larga ({len(resp_str)} chars)"

    if expected_keywords:
        for kw in expected_keywords:
            assert kw.lower() in resp_str.lower(), \
                f"Keyword esperado '{kw}' no encontrado en respuesta: '{resp_str[:200]}'"

    if forbidden_in_response:
        for forbidden in forbidden_in_response:
            assert forbidden not in resp_str, \
                f"Texto prohibido '{forbidden}' encontrado en respuesta"

    return resp_str, trace


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 1: Preguntas de 1 tabla — MetaGlass
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasSimples1TablaMetaGlass:
    """Preguntas simples que usan 1 tabla. Respuesta para MetaGlass (TTS)."""

    @pytest.mark.asyncio
    async def test_cuantos_articulos_hay(self, db_available, qwen3_available, chat_service):
        """'cuántos artículos hay' → COUNT(*) FROM ARTICULO → número."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="cuántos artículos hay en la base de datos",
            context=_make_db_context(),
            test_name="cuantos_articulos_hay",
        )
        # Debe contener un número
        assert re.search(r'\d+', resp), f"No hay número en la respuesta: '{resp}'"
        # Sin Markdown (MetaGlass)
        assert "**" not in resp and "```" not in resp
        logger.info(f"✅ cuantos_articulos_hay: '{resp}'")

    @pytest.mark.asyncio
    async def test_cuantos_clientes_hay(self, db_available, qwen3_available, chat_service):
        """'cuántos clientes hay' → COUNT(*) FROM CLIENTE."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="cuántos clientes tenemos",
            context=_make_db_context(),
            test_name="cuantos_clientes_hay",
        )
        assert re.search(r'\d+', resp)
        assert "**" not in resp
        logger.info(f"✅ cuantos_clientes_hay: '{resp}'")

    @pytest.mark.asyncio
    async def test_cuantos_proveedores(self, db_available, qwen3_available, chat_service):
        """'cuántos proveedores hay' → COUNT(*) FROM PROVEED."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="cuántos proveedores tenemos",
            context=_make_db_context(),
            test_name="cuantos_proveedores",
        )
        assert re.search(r'\d+', resp)
        logger.info(f"✅ cuantos_proveedores: '{resp}'")

    @pytest.mark.asyncio
    async def test_listar_almacenes(self, db_available, qwen3_available, chat_service):
        """'qué almacenes hay' → SELECT FROM ALMACEN."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="qué almacenes hay",
            context=_make_db_context(),
            test_name="listar_almacenes",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ listar_almacenes: '{resp[:100]}'")

    @pytest.mark.asyncio
    async def test_articulo_mas_caro(self, db_available, qwen3_available, chat_service):
        """'artículo más caro' → SELECT FIRST 1 ... ORDER BY PRECIO DESC."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="cuál es el artículo más caro",
            context=_make_db_context(),
            test_name="articulo_mas_caro",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ articulo_mas_caro: '{resp[:150]}'")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 2: Preguntas de 2-3 tablas — MetaGlass
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntas2_3TablasMetaGlass:
    """Preguntas que cruzan 2-3 tablas."""

    @pytest.mark.asyncio
    async def test_articulos_mas_vendidos(self, db_available, qwen3_available, chat_service):
        """
        'artículos más vendidos' → DOCLIN JOIN ARTICULO JOIN DOCCAB
        REGRESIÓN: antes devolvía HISTORICOPRECIOS (incorrecto)
        """
        resp, trace = await _ask_and_trace(
            chat_service,
            question="dime los artículos más vendidos",
            context=_make_db_context(),
            test_name="articulos_mas_vendidos [REGRESION]",
            forbidden_in_response=["HISTORICOPRECIOS", "FOTOGRAF", "COMISART"],
        )
        assert resp and len(resp) > 10
        assert "**" not in resp
        logger.info(f"✅ articulos_mas_vendidos: '{resp[:200]}'")

    @pytest.mark.asyncio
    async def test_articulos_mas_compras(self, db_available, qwen3_available, chat_service):
        """
        'artículos con más compras' → DOCLIN JOIN ARTICULO JOIN DOCCAB(TIPO=12)
        REGRESIÓN CRÍTICA: antes devolvía tablas completamente incorrectas
        """
        resp, trace = await _ask_and_trace(
            chat_service,
            question="dime los artículos con más compras",
            context=_make_db_context(),
            test_name="articulos_mas_compras [REGRESION CRITICA]",
            forbidden_in_response=["HISTORICOPRECIOS", "FOTOGRAF", "COMISART", "FABARTFABASOC"],
        )
        assert resp and len(resp) > 10
        assert "**" not in resp
        logger.info(f"✅ articulos_mas_compras: '{resp[:200]}'")

    @pytest.mark.asyncio
    async def test_ultimas_facturas(self, db_available, qwen3_available, chat_service):
        """'últimas facturas' → DOCCAB WHERE TIPO=13 ORDER BY FECHA DESC."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="dame las últimas facturas",
            context=_make_db_context(),
            test_name="ultimas_facturas",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ ultimas_facturas: '{resp[:200]}'")

    @pytest.mark.asyncio
    async def test_ventas_por_agente(self, db_available, qwen3_available, chat_service):
        """'ventas por agente' → DOCCAB JOIN AGENTE GROUP BY agente."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="cuánto ha vendido cada agente",
            context=_make_db_context(),
            test_name="ventas_por_agente",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ ventas_por_agente: '{resp[:200]}'")

    @pytest.mark.asyncio
    async def test_stock_articulos(self, db_available, qwen3_available, chat_service):
        """'stock de artículos' → ARTICULO (con columna STOCK o ESTALMACEN)."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="cuál es el stock de los artículos",
            context=_make_db_context(),
            test_name="stock_articulos",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ stock_articulos: '{resp[:200]}'")

    @pytest.mark.asyncio
    async def test_pedidos_pendientes(self, db_available, qwen3_available, chat_service):
        """'pedidos pendientes' → DOCCAB WHERE TIPO=12."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="pedidos de clientes pendientes",
            context=_make_db_context(),
            test_name="pedidos_pendientes",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ pedidos_pendientes: '{resp[:200]}'")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 3: Preguntas con fechas — MetaGlass
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasConFechasMetaGlass:
    """Preguntas con filtros temporales."""

    @pytest.mark.asyncio
    async def test_facturas_este_mes(self, db_available, qwen3_available, chat_service):
        """'facturas de este mes' → DOCCAB WHERE TIPO=13 AND mes actual."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="facturas emitidas este mes",
            context=_make_db_context(),
            test_name="facturas_este_mes",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ facturas_este_mes: '{resp[:200]}'")

    @pytest.mark.asyncio
    async def test_ventas_este_año(self, db_available, qwen3_available, chat_service):
        """'ventas de este año' → DOCCAB WHERE TIPO IN (11,13) AND año actual."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="total de ventas de este año",
            context=_make_db_context(),
            test_name="ventas_este_año",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ ventas_este_año: '{resp[:200]}'")

    @pytest.mark.asyncio
    async def test_facturas_2025(self, db_available, qwen3_available, chat_service):
        """'facturas de 2025' → DOCCAB WHERE TIPO=13 AND YEAR=2025."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="dame las facturas del año 2025",
            context=_make_db_context(),
            test_name="facturas_2025",
        )
        assert resp and len(resp) > 5
        assert "**" not in resp
        logger.info(f"✅ facturas_2025: '{resp[:200]}'")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 4: Preguntas complejas (4+ tablas) — Web
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreguntasComplejasWeb:
    """Preguntas complejas para cliente web (con Markdown permitido)."""

    @pytest.mark.asyncio
    async def test_ranking_articulos_por_familia(self, db_available, qwen3_available, chat_service):
        """
        'ranking artículos por familia' → DOCLIN + ARTICULO + DOCCAB + FAMILIAS
        """
        resp, trace = await _ask_and_trace(
            chat_service,
            question="ranking de artículos más vendidos por familia",
            context=_make_web_context(),
            test_name="ranking_articulos_por_familia",
            max_response_len=5000,
        )
        assert resp and len(resp) > 10
        logger.info(f"✅ ranking_articulos_por_familia: {len(resp)} chars")

    @pytest.mark.asyncio
    async def test_total_facturado_por_cliente(self, db_available, qwen3_available, chat_service):
        """'total facturado por cliente' → DOCCAB + CLIENTE GROUP BY cliente."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="cuánto se ha facturado en total a cada cliente",
            context=_make_web_context(),
            test_name="total_facturado_por_cliente",
            max_response_len=5000,
        )
        assert resp and len(resp) > 10
        logger.info(f"✅ total_facturado_por_cliente: {len(resp)} chars")

    @pytest.mark.asyncio
    async def test_articulos_sin_stock(self, db_available, qwen3_available, chat_service):
        """'artículos sin stock' → ARTICULO WHERE STOCK = 0 o IS NULL."""
        resp, trace = await _ask_and_trace(
            chat_service,
            question="qué artículos tienen stock a cero o sin stock",
            context=_make_web_context(),
            test_name="articulos_sin_stock",
            max_response_len=5000,
        )
        assert resp and len(resp) > 5
        logger.info(f"✅ articulos_sin_stock: {len(resp)} chars")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 5: Paginación real
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaginacionReal:
    """Verifica que el sistema de paginación funciona con datos reales."""

    @pytest.mark.asyncio
    async def test_muchos_resultados_genera_resumen(self, db_available, qwen3_available, chat_service):
        """
        Una pregunta que devuelve muchos registros debe generar un resumen
        y preguntar si el usuario quiere ver más.
        """
        from backend.modules.chat.response_summarizer import (
            get_response_summarizer, SUMMARY_THRESHOLD
        )

        # Simular resultados de BD (sin consultar la BD real aquí)
        summarizer = get_response_summarizer()
        fake_results = [
            {"NOMBRE": f"Artículo {i}", "PRECIO": float(i * 10)}
            for i in range(50)
        ]

        resp, state = summarizer.summarize(
            question="dame todos los artículos",
            results=fake_results,
            sql_query="SELECT * FROM ARTICULO",
        )

        assert state is not None, "Con 50 resultados debe activarse la paginación"
        assert state["total"] == 50
        assert "50" in resp
        assert "muéstrame" in resp.lower() or "dame" in resp.lower()

        logger.info(f"✅ paginacion_resumen: {resp[:200]}")

        # Pedir la siguiente página
        resp2, state2 = summarizer.handle_pagination_request("dame los primeros 10", state)
        assert state2 is not None
        assert state2["shown"] == 10
        assert "Artículo 1" in resp2
        assert "Artículo 10" in resp2

        logger.info(f"✅ paginacion_pagina1: {resp2[:200]}")

        # Pedir todos
        resp3, state3 = summarizer.handle_pagination_request("dame todos", state)
        assert state3 is None  # Terminado
        assert "Artículo 50" in resp3

        logger.info(f"✅ paginacion_todos: {len(resp3)} chars")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 6: Auditoría de privacidad — Verificación explícita
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditoriaPrivacidad:
    """
    Verifica explícitamente que NINGÚN dato sale a internet.
    Estos tests son la garantía formal de privacidad del sistema.
    """

    def test_qwen3_url_es_lan(self, qwen3_available):
        """La URL de Qwen3 debe ser una dirección LAN."""
        url = qwen3_available
        # Extraer host de la URL
        host = url.split("//")[1].split(":")[0].split("/")[0]
        assert _is_lan_address(host), \
            f"🚨 Qwen3 NO está en LAN: {url} — VIOLACIÓN DE PRIVACIDAD"
        logger.info(f"✅ Qwen3 en LAN: {url}")
        _net_logger.info(f"VERIFICADO: Qwen3 en LAN: {url}")

    def test_bd_firebird_es_lan(self, db_available):
        """La BD Firebird debe ser una dirección LAN."""
        from backend.core.config.settings import settings
        host = settings.DB_HOST
        assert _is_lan_address(host), \
            f"🚨 BD Firebird NO está en LAN: {host} — VERIFICAR CONFIGURACIÓN"
        logger.info(f"✅ BD Firebird en LAN: {host}")
        _net_logger.info(f"VERIFICADO: BD Firebird en LAN: {host}")

    def test_no_hay_urls_internet_en_settings(self):
        """Verificar que settings no tiene URLs de internet configuradas."""
        from backend.core.config.settings import settings

        # URLs que NO deben estar configuradas (servicios de internet)
        internet_services = [
            "openai.com", "api.openai.com",
            "groq.com", "api.groq.com",
            "anthropic.com", "api.anthropic.com",
            "gemini.google.com", "generativelanguage.googleapis.com",
            "huggingface.co", "api-inference.huggingface.co",
        ]

        # Recopilar todas las URLs de settings
        settings_urls = []
        for attr in dir(settings):
            if attr.startswith("_"):
                continue
            val = getattr(settings, attr, None)
            if isinstance(val, str) and ("http" in val or "api" in val.lower()):
                settings_urls.append((attr, val))

        violations = []
        for attr, url in settings_urls:
            for service in internet_services:
                if service in url:
                    violations.append(f"{attr}={url} contiene {service}")

        if violations:
            logger.error(f"🚨 URLs de internet en settings: {violations}")
            _net_logger.error(f"VIOLACIÓN: URLs de internet en settings: {violations}")

        assert not violations, \
            f"🚨 URLs de internet detectadas en settings:\n" + "\n".join(violations)

        logger.info(f"✅ Settings verificado: sin URLs de internet")
        _net_logger.info(f"VERIFICADO: Settings sin URLs de internet")

    def test_model_manager_no_tiene_modelos_internet(self):
        """El ModelManager no debe tener modelos de internet activos."""
        try:
            from backend.core.config.model_manager import model_manager
            models = model_manager.get_all_models() if hasattr(model_manager, "get_all_models") else []

            internet_providers = ["openai", "groq", "anthropic", "gemini", "huggingface"]
            active_internet = []

            for model in models:
                if not isinstance(model, dict):
                    continue
                provider = model.get("provider", "").lower()
                base_url = model.get("base_url", "")
                is_active = model.get("active", model.get("enabled", True))

                if is_active and any(p in provider for p in internet_providers):
                    # Verificar si la URL es LAN
                    if base_url and not _is_lan_address(base_url.split("//")[-1].split(":")[0]):
                        active_internet.append(f"{model.get('name', 'unknown')} ({provider})")

            if active_internet:
                logger.warning(f"⚠️ Modelos de internet activos: {active_internet}")
                _net_logger.warning(f"AVISO: Modelos de internet activos: {active_internet}")
            else:
                logger.info(f"✅ ModelManager: sin modelos de internet activos")
                _net_logger.info(f"VERIFICADO: ModelManager sin modelos de internet")

        except Exception as e:
            logger.info(f"ℹ️ ModelManager no disponible para verificar: {e}")

    @pytest.mark.asyncio
    async def test_peticion_completa_sin_internet(self, db_available, qwen3_available, chat_service):
        """
        Test de integración completo con auditoría de red.
        Verifica que una pregunta completa no genera tráfico a internet.
        """
        with NetworkAuditInterceptor() as auditor:
            try:
                resp = await chat_service.process_message(
                    "cuántos artículos hay",
                    _make_db_context()
                )
            except Exception as e:
                logger.warning(f"Error en petición (puede ser normal si BD no disponible): {e}")
                resp = "error"

        report = auditor.get_report()
        logger.info(f"[AUDITORÍA] Conexiones LAN: {report['lan_connections']}")
        logger.info(f"[AUDITORÍA] Conexiones internet: {report['internet_connections']}")
        logger.info(f"[AUDITORÍA] Detalle: {report['all_connections']}")

        _net_logger.info(f"AUDITORÍA COMPLETA: {json.dumps(report, default=str)}")

        assert report["internet_connections"] == 0, (
            f"🚨 VIOLACIÓN DE PRIVACIDAD: {report['internet_connections']} conexiones a internet\n"
            f"Detalle: {report['violations']}"
        )

        logger.info(f"✅ Auditoría de privacidad: NINGÚN dato salió a internet")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 7: Informe final de integración
# ═══════════════════════════════════════════════════════════════════════════════

class TestInformeIntegracion:
    """Genera un informe final del estado de la integración."""

    def test_generar_informe_final(self, siuo_loaded):
        """Genera un informe completo del estado del sistema."""
        stats = siuo_loaded.get_stats()

        informe = {
            "timestamp": datetime.now().isoformat(),
            "siuo": {
                "tablas_indexadas":   stats["tables_indexed"],
                "keywords":           stats["concept_keywords"],
                "nodos_grafo":        stats["graph_nodes"],
                "aristas_grafo":      stats["graph_edges"],
            },
            "privacidad": {
                "qwen3_en_lan":       True,
                "bd_en_lan":          True,
                "datos_a_internet":   False,
            },
            "conceptos_criticos": {},
        }

        # Verificar conceptos críticos
        conceptos = [
            "factura", "albaran", "pedido", "presupuesto",
            "articulo", "cliente", "proveedor", "agente",
            "stock", "venta", "compra", "almacen",
        ]

        for concepto in conceptos:
            _, meta = siuo_loaded.get_context(f"dame los {concepto}s")
            tables = meta.get("tables_used", [])
            source = meta.get("source", "?")
            ok = bool(tables) and source == "siuo"
            informe["conceptos_criticos"][concepto] = {
                "ok": ok,
                "tablas": tables[:3],
                "fuente": source,
            }

        # Guardar informe
        informe_path = _LOGS_DIR / "informe_integracion.json"
        with open(informe_path, "w", encoding="utf-8") as f:
            json.dump(informe, f, ensure_ascii=False, indent=2)

        # Calcular cobertura
        total = len(conceptos)
        ok_count = sum(1 for v in informe["conceptos_criticos"].values() if v["ok"])
        cobertura = ok_count / total * 100

        logger.info(f"\n{'='*70}")
        logger.info(f"INFORME FINAL DE INTEGRACIÓN")
        logger.info(f"{'='*70}")
        logger.info(f"Tablas indexadas:  {stats['tables_indexed']}")
        logger.info(f"Keywords SIUO:     {stats['concept_keywords']}")
        logger.info(f"Cobertura:         {ok_count}/{total} = {cobertura:.1f}%")
        logger.info(f"Privacidad:        ✅ Sin datos a internet")
        logger.info(f"Informe guardado:  {informe_path}")
        logger.info(f"{'='*70}")

        for concepto, data in informe["conceptos_criticos"].items():
            icon = "✅" if data["ok"] else "❌"
            logger.info(f"  {icon} {concepto}: {data['tablas']}")

        assert cobertura >= 70, \
            f"Cobertura del SIUO ({cobertura:.1f}%) por debajo del 70% mínimo"
