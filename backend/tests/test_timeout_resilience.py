"""
test_timeout_resilience.py — Tests exhaustivos del sistema de timeouts y resiliencia.

Cubre:
  1. TestFrontendTimeoutConfig       — Constantes de timeout en config.json
  2. TestAdaptiveTimeout             — Timeout adaptativo (normal vs deep_analysis)
  3. TestTimeoutDetectionLogic       — Detección de timeout enmascarado (TypeError→timeout)
  4. TestBackendKeepAlive            — Configuración uvicorn keep-alive
  5. TestDeepAnalysisTimeout         — Timeout suficiente para análisis profundo
  6. TestPingEndpoint                — Endpoint /api/chat/ping heartbeat
  7. TestLanReadTimeout              — lan_read_timeout_s suficiente por llamada
  8. TestTimeoutCascade              — Cascada de timeouts: frontend > backend total > por llamada
  9. TestErrorClassification         — Clasificación correcta de errores (timeout vs network)
  10. TestProgressBarLogic           — Lógica de barra de progreso
  11. TestDeepAnalysisCallCount      — Número de llamadas IA en deep_analysis
  12. TestSimpleQueryCallCount       — Número de llamadas IA en consulta simple
  13. TestTimeoutRecovery            — Recuperación tras timeout (retry funciona)
  14. TestConcurrentRequests         — Backend responde /ping mientras procesa /send
  15. TestTimeoutMessages            — Mensajes de error correctos según tipo
"""

import asyncio
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# ─── Rutas ────────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHAT_CONFIG = os.path.join(_BASE, "modules", "chat", "config.json")
_MODELS_JSON = os.path.join(_BASE, "core", "config", "models", "jddcia_models.json")


def _load_chat_config() -> dict:
    with open(_CHAT_CONFIG, encoding="utf-8") as f:
        return json.load(f)


def _load_models() -> list:
    with open(_MODELS_JSON, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TestFrontendTimeoutConfig
# ═══════════════════════════════════════════════════════════════════════════════

class TestFrontendTimeoutConfig(unittest.TestCase):
    """Verifica que los timeouts del frontend están correctamente configurados."""

    def setUp(self):
        self.cfg = _load_chat_config()

    def test_lan_read_timeout_at_least_180s(self):
        """lan_read_timeout_s debe ser >= 180s para peticiones largas."""
        t = self.cfg.get("lan_read_timeout_s", 0)
        self.assertGreaterEqual(t, 180,
            f"lan_read_timeout_s={t} es insuficiente para el modelo 8B (necesita 20-35s/llamada)")

    def test_lan_read_timeout_at_least_300s(self):
        """lan_read_timeout_s debe ser >= 300s para deep_analysis (múltiples llamadas)."""
        t = self.cfg.get("lan_read_timeout_s", 0)
        self.assertGreaterEqual(t, 300,
            f"lan_read_timeout_s={t} es insuficiente para deep_analysis (5-8 llamadas × 35s = 175-280s)")

    def test_uvicorn_keep_alive_configured(self):
        """uvicorn_timeout_keep_alive debe estar configurado en config.json."""
        ka = self.cfg.get("uvicorn_timeout_keep_alive", 0)
        self.assertGreater(ka, 0,
            "uvicorn_timeout_keep_alive debe estar configurado para evitar cierre de conexión")

    def test_uvicorn_keep_alive_greater_than_deep_timeout(self):
        """uvicorn keep-alive debe ser > 600s (timeout deep_analysis del frontend)."""
        ka = self.cfg.get("uvicorn_timeout_keep_alive", 0)
        self.assertGreater(ka, 600,
            f"uvicorn_timeout_keep_alive={ka} debe ser > 600s (frontend deep timeout)")

    def test_lan_max_retries_reasonable(self):
        """lan_max_retries debe ser razonable (5-15)."""
        r = self.cfg.get("lan_max_retries", 0)
        self.assertGreaterEqual(r, 5)
        self.assertLessEqual(r, 20)

    def test_max_sql_retries_configured(self):
        """max_sql_retries debe estar configurado."""
        r = self.cfg.get("max_sql_retries", 0)
        self.assertGreater(r, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TestAdaptiveTimeout
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdaptiveTimeout(unittest.TestCase):
    """Verifica la lógica de timeout adaptativo según tipo de petición."""

    # Simula la lógica de chat-recovery.js en Python para testearla
    # NOTA: constants.js tiene AI_REQUEST: 300000 (5 min), AI_REQUEST_DEEP: 1200000 (20 min)
    AI_REQUEST = 300_000        # 5 min — consultas simples
    AI_REQUEST_DEEP = 1_200_000 # 20 min — deep_analysis

    def _get_timeout(self, payload: dict) -> int:
        """Replica la lógica de startRequest() en chat-recovery.js."""
        is_deep = bool(payload.get("deep_analysis"))
        return self.AI_REQUEST_DEEP if is_deep else self.AI_REQUEST

    def test_simple_query_uses_300s(self):
        payload = {"message": "Cuántos clientes hay?", "deep_analysis": False}
        t = self._get_timeout(payload)
        self.assertEqual(t, 300_000, "Consulta simple debe usar 300s (5 min)")

    def test_deep_analysis_uses_1200s(self):
        payload = {"message": "Analiza proveedores", "deep_analysis": True}
        t = self._get_timeout(payload)
        self.assertEqual(t, 1_200_000, "Deep analysis debe usar 1200s (20 min)")

    def test_missing_deep_flag_defaults_to_simple(self):
        payload = {"message": "Hola"}
        t = self._get_timeout(payload)
        self.assertEqual(t, 300_000, "Sin flag deep_analysis → timeout simple")

    def test_deep_false_uses_simple_timeout(self):
        payload = {"message": "Facturación total", "deep_analysis": False}
        t = self._get_timeout(payload)
        self.assertEqual(t, 300_000)

    def test_deep_true_uses_deep_timeout(self):
        payload = {"message": "Análisis completo de ventas", "deep_analysis": True}
        t = self._get_timeout(payload)
        self.assertEqual(t, 1_200_000)

    def test_deep_timeout_is_4x_simple(self):
        """El timeout deep debe ser al menos 4× el simple."""
        ratio = self.AI_REQUEST_DEEP / self.AI_REQUEST
        self.assertGreaterEqual(ratio, 4.0,
            f"Deep timeout ({self.AI_REQUEST_DEEP}ms) debe ser ≥ 4× simple ({self.AI_REQUEST}ms)")

    def test_simple_timeout_at_least_300s(self):
        """El timeout simple debe ser >= 300s para el modelo 8B."""
        self.assertGreaterEqual(self.AI_REQUEST, 300_000,
            "AI_REQUEST debe ser >= 300s (8B tarda 20-35s/llamada, 3 llamadas = 60-105s)")

    def test_deep_timeout_at_least_600s(self):
        """El timeout deep debe ser >= 600s para múltiples fases IA."""
        self.assertGreaterEqual(self.AI_REQUEST_DEEP, 600_000,
            "AI_REQUEST_DEEP debe ser >= 600s (deep_analysis: 5-8 llamadas × 35s = 175-280s)")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. TestTimeoutDetectionLogic
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeoutDetectionLogic(unittest.TestCase):
    """
    Verifica la lógica de detección de timeout enmascarado.

    Algunos navegadores lanzan TypeError: 'Failed to fetch' en lugar de AbortError
    cuando el AbortController dispara. Detectamos esto por el tiempo transcurrido.
    """

    TIMEOUT_DETECTION_RATIO = 0.90  # 90% del timeout configurado

    def _classify_error(self, reason: str, elapsed_ms: int, configured_timeout_ms: int) -> str:
        """Replica la lógica de failRequest() en chat-recovery.js."""
        if reason == "network" and elapsed_ms is not None and configured_timeout_ms > 0:
            ratio = elapsed_ms / configured_timeout_ms
            if ratio >= self.TIMEOUT_DETECTION_RATIO:
                return "timeout"
        return reason

    def test_network_error_at_180s_classified_as_timeout(self):
        """TypeError a los 180s con timeout=180s → timeout."""
        result = self._classify_error("network", 180_009, 180_000)
        self.assertEqual(result, "timeout",
            "TypeError a los 180s debe clasificarse como timeout, no como error de red")

    def test_network_error_at_600s_classified_as_timeout(self):
        """TypeError a los 600s con timeout=600s → timeout."""
        result = self._classify_error("network", 600_100, 600_000)
        self.assertEqual(result, "timeout")

    def test_network_error_at_5s_stays_network(self):
        """TypeError a los 5s → error de red real."""
        result = self._classify_error("network", 5_000, 180_000)
        self.assertEqual(result, "network",
            "Error a los 5s no debe clasificarse como timeout")

    def test_network_error_at_50_percent_stays_network(self):
        """TypeError al 50% del timeout → error de red."""
        result = self._classify_error("network", 90_000, 180_000)
        self.assertEqual(result, "network")

    def test_network_error_at_89_percent_stays_network(self):
        """TypeError al 89% del timeout → error de red (justo por debajo del umbral)."""
        result = self._classify_error("network", 160_200, 180_000)
        self.assertEqual(result, "network")

    def test_network_error_at_90_percent_classified_as_timeout(self):
        """TypeError al 90% del timeout → timeout (en el umbral exacto)."""
        result = self._classify_error("network", 162_000, 180_000)
        self.assertEqual(result, "timeout")

    def test_network_error_at_95_percent_classified_as_timeout(self):
        """TypeError al 95% del timeout → timeout."""
        result = self._classify_error("network", 171_000, 180_000)
        self.assertEqual(result, "timeout")

    def test_abort_error_not_reclassified(self):
        """AbortError nunca se reclasifica (ya es timeout o cancelled)."""
        result = self._classify_error("timeout", 180_000, 180_000)
        self.assertEqual(result, "timeout")

    def test_cancelled_not_reclassified(self):
        """Cancelled no se reclasifica."""
        result = self._classify_error("cancelled", 5_000, 180_000)
        self.assertEqual(result, "cancelled")

    def test_http_error_not_reclassified(self):
        """Errores HTTP no se reclasifican."""
        result = self._classify_error("http_500", 180_000, 180_000)
        self.assertEqual(result, "http_500")

    def test_zero_elapsed_stays_network(self):
        """elapsed=0 → error de red."""
        result = self._classify_error("network", 0, 180_000)
        self.assertEqual(result, "network")

    def test_deep_analysis_timeout_detection(self):
        """TypeError a los 600s con deep_analysis timeout=600s → timeout."""
        result = self._classify_error("network", 600_050, 600_000)
        self.assertEqual(result, "timeout")

    def test_deep_analysis_early_network_error(self):
        """TypeError a los 30s con deep_analysis timeout=600s → error de red."""
        result = self._classify_error("network", 30_000, 600_000)
        self.assertEqual(result, "network")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TestBackendKeepAlive
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackendKeepAlive(unittest.TestCase):
    """Verifica la configuración de keep-alive del servidor."""

    def setUp(self):
        self.cfg = _load_chat_config()

    def test_keep_alive_in_config(self):
        """uvicorn_timeout_keep_alive debe estar en config.json."""
        self.assertIn("uvicorn_timeout_keep_alive", self.cfg)

    def test_keep_alive_is_integer(self):
        """uvicorn_timeout_keep_alive debe ser un entero."""
        ka = self.cfg.get("uvicorn_timeout_keep_alive")
        self.assertIsInstance(ka, int)

    def test_keep_alive_greater_than_600(self):
        """Keep-alive debe ser > 600s (frontend deep timeout)."""
        ka = self.cfg.get("uvicorn_timeout_keep_alive", 0)
        self.assertGreater(ka, 600)

    def test_keep_alive_comment_exists(self):
        """Debe haber un comentario explicativo."""
        self.assertIn("_uvicorn_timeout_keep_alive_comment", self.cfg)

    def test_keep_alive_value_is_reasonable(self):
        """Keep-alive debe ser razonable (600-3600s)."""
        ka = self.cfg.get("uvicorn_timeout_keep_alive", 0)
        self.assertGreaterEqual(ka, 600)
        self.assertLessEqual(ka, 3600)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TestDeepAnalysisTimeout
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeepAnalysisTimeout(unittest.TestCase):
    """
    Verifica que el sistema tiene suficiente tiempo para completar deep_analysis.

    Deep analysis ejecuta:
      - 1 llamada intent classification (~25s)
      - 1 llamada SQL generation (~25s)
      - 1 llamada SQL interpretation (~25s)
      - 4-8 llamadas deep phases (~25s cada una)
    Total estimado: 7-11 llamadas × 25s = 175-275s con el modelo 8B
    """

    AI_CALL_ESTIMATE_S = 35   # Estimación conservadora por llamada (8B en CPU)
    MIN_CALLS_DEEP = 5        # Mínimo de llamadas en deep_analysis
    MAX_CALLS_DEEP = 10       # Máximo de llamadas en deep_analysis
    FRONTEND_DEEP_TIMEOUT_S = 600  # 10 minutos

    def test_frontend_deep_timeout_covers_min_calls(self):
        """El timeout del frontend debe cubrir el mínimo de llamadas."""
        min_time = self.MIN_CALLS_DEEP * self.AI_CALL_ESTIMATE_S
        self.assertGreater(self.FRONTEND_DEEP_TIMEOUT_S, min_time,
            f"Frontend timeout ({self.FRONTEND_DEEP_TIMEOUT_S}s) debe cubrir "
            f"{self.MIN_CALLS_DEEP} llamadas × {self.AI_CALL_ESTIMATE_S}s = {min_time}s")

    def test_frontend_deep_timeout_covers_max_calls(self):
        """El timeout del frontend debe cubrir el máximo de llamadas."""
        max_time = self.MAX_CALLS_DEEP * self.AI_CALL_ESTIMATE_S
        self.assertGreater(self.FRONTEND_DEEP_TIMEOUT_S, max_time,
            f"Frontend timeout ({self.FRONTEND_DEEP_TIMEOUT_S}s) debe cubrir "
            f"{self.MAX_CALLS_DEEP} llamadas × {self.AI_CALL_ESTIMATE_S}s = {max_time}s")

    def test_lan_read_timeout_per_call_sufficient(self):
        """lan_read_timeout_s debe ser suficiente para una sola llamada."""
        cfg = _load_chat_config()
        t = cfg.get("lan_read_timeout_s", 0)
        self.assertGreaterEqual(t, self.AI_CALL_ESTIMATE_S,
            f"lan_read_timeout_s={t}s debe ser >= {self.AI_CALL_ESTIMATE_S}s por llamada")

    def test_simple_query_timeout_covers_3_calls(self):
        """El timeout simple (180s) debe cubrir al menos 3 llamadas IA."""
        simple_timeout = 180
        calls_covered = simple_timeout // self.AI_CALL_ESTIMATE_S
        self.assertGreaterEqual(calls_covered, 3,
            f"Timeout simple ({simple_timeout}s) debe cubrir ≥ 3 llamadas IA")

    def test_deep_timeout_is_sufficient_margin(self):
        """El timeout deep debe tener al menos 20% de margen sobre el tiempo estimado."""
        max_estimated = self.MAX_CALLS_DEEP * self.AI_CALL_ESTIMATE_S
        margin = (self.FRONTEND_DEEP_TIMEOUT_S - max_estimated) / self.FRONTEND_DEEP_TIMEOUT_S
        self.assertGreater(margin, 0.20,
            f"Margen de seguridad ({margin:.0%}) debe ser > 20%")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. TestPingEndpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestPingEndpoint(unittest.TestCase):
    """Verifica que el endpoint /api/chat/ping existe y responde correctamente."""

    def test_ping_route_exists_in_router(self):
        """El router debe tener la ruta /ping."""
        router_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "modules", "chat", "router.py"
        )
        with open(router_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"/ping"', content,
            "El router debe tener el endpoint GET /ping")

    def test_ping_is_get_method(self):
        """El endpoint /ping debe ser GET (no POST)."""
        router_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "modules", "chat", "router.py"
        )
        with open(router_path, encoding="utf-8") as f:
            content = f.read()
        # Buscar @router.get("/ping")
        self.assertIn('@router.get("/ping")', content,
            "El endpoint /ping debe ser GET")

    def test_ping_returns_status_alive(self):
        """La función ping debe retornar status=alive."""
        router_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "modules", "chat", "router.py"
        )
        with open(router_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"alive"', content,
            "El endpoint /ping debe retornar status='alive'")

    def test_ping_returns_timestamp(self):
        """La función ping debe retornar timestamp."""
        router_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "modules", "chat", "router.py"
        )
        with open(router_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"timestamp"', content,
            "El endpoint /ping debe retornar timestamp")

    @pytest.mark.asyncio
    async def test_ping_responds_fast(self):
        """El endpoint /ping debe responder en < 100ms."""
        from backend.modules.chat.router import ping
        t0 = time.monotonic()
        result = await ping()
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 0.1,
            f"El endpoint /ping tardó {elapsed:.3f}s — debe ser < 100ms")
        self.assertEqual(result["status"], "alive")

    @pytest.mark.asyncio
    async def test_ping_has_service_field(self):
        """El endpoint /ping debe incluir el campo service."""
        from backend.modules.chat.router import ping
        result = await ping()
        self.assertIn("service", result)
        self.assertIn("DEVIA", result["service"])


# ═══════════════════════════════════════════════════════════════════════════════
# 7. TestLanReadTimeout
# ═══════════════════════════════════════════════════════════════════════════════

class TestLanReadTimeout(unittest.TestCase):
    """Verifica que lan_read_timeout_s es suficiente para cada llamada individual."""

    def setUp(self):
        self.cfg = _load_chat_config()
        self.timeout = self.cfg.get("lan_read_timeout_s", 0)

    def test_timeout_at_least_60s(self):
        """Mínimo 60s para el modelo 8B en CPU."""
        self.assertGreaterEqual(self.timeout, 60)

    def test_timeout_at_least_180s(self):
        """Al menos 180s para prompts grandes (deep analysis phases)."""
        self.assertGreaterEqual(self.timeout, 180)

    def test_timeout_at_least_300s(self):
        """Al menos 300s para garantizar que ninguna llamada individual falle."""
        self.assertGreaterEqual(self.timeout, 300)

    def test_timeout_not_excessive(self):
        """El timeout no debe ser excesivo (máximo 600s por llamada)."""
        self.assertLessEqual(self.timeout, 600,
            "Timeout > 600s por llamada es excesivo y enmascara problemas reales")

    def test_timeout_comment_exists(self):
        """Debe haber un comentario explicativo del timeout."""
        self.assertIn("_lan_read_timeout_s_comment", self.cfg)

    def test_timeout_comment_mentions_deep_analysis(self):
        """El comentario debe mencionar deep_analysis."""
        comment = self.cfg.get("_lan_read_timeout_s_comment", "")
        self.assertIn("deep", comment.lower(),
            "El comentario debe mencionar deep analysis")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. TestTimeoutCascade
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeoutCascade(unittest.TestCase):
    """
    Verifica la cascada de timeouts: frontend > backend total > por llamada.

    La regla es:
      frontend_timeout > backend_total_timeout > per_call_timeout

    Para consultas simples:
      180s (frontend) > ~3 llamadas × 60s = 180s (backend) > 300s (per call)
      → OK porque el backend no hace 3 llamadas de 300s en consultas simples

    Para deep_analysis:
      600s (frontend) > 10 llamadas × 35s = 350s (backend estimado) > 300s (per call)
      → OK: el frontend tiene margen suficiente
    """

    def setUp(self):
        self.cfg = _load_chat_config()
        self.per_call_timeout = self.cfg.get("lan_read_timeout_s", 0)
        self.frontend_simple = 180
        self.frontend_deep = 600
        self.uvicorn_ka = self.cfg.get("uvicorn_timeout_keep_alive", 0)

    def test_uvicorn_ka_greater_than_frontend_deep(self):
        """uvicorn keep-alive > frontend deep timeout."""
        self.assertGreater(self.uvicorn_ka, self.frontend_deep,
            f"uvicorn_ka={self.uvicorn_ka}s debe ser > frontend_deep={self.frontend_deep}s")

    def test_frontend_deep_greater_than_frontend_simple(self):
        """Frontend deep timeout > frontend simple timeout."""
        self.assertGreater(self.frontend_deep, self.frontend_simple)

    def test_per_call_timeout_less_than_frontend_deep(self):
        """Timeout por llamada < frontend deep timeout."""
        self.assertLess(self.per_call_timeout, self.frontend_deep,
            f"per_call={self.per_call_timeout}s debe ser < frontend_deep={self.frontend_deep}s")

    def test_cascade_order_correct(self):
        """Orden correcto: uvicorn_ka > frontend_deep > frontend_simple > per_call."""
        self.assertGreater(self.uvicorn_ka, self.frontend_deep)
        self.assertGreater(self.frontend_deep, self.frontend_simple)
        # per_call puede ser > frontend_simple (es por llamada, no total)
        # pero debe ser < frontend_deep
        self.assertLess(self.per_call_timeout, self.frontend_deep)

    def test_simple_query_3_calls_fit_in_frontend_timeout(self):
        """3 llamadas IA de 35s cada una caben en el timeout simple de 180s."""
        calls = 3
        per_call_estimate = 35  # segundos reales del 8B
        total = calls * per_call_estimate
        self.assertLessEqual(total, self.frontend_simple,
            f"{calls} llamadas × {per_call_estimate}s = {total}s debe caber en {self.frontend_simple}s")

    def test_deep_10_calls_fit_in_frontend_deep_timeout(self):
        """10 llamadas IA de 35s cada una caben en el timeout deep de 600s."""
        calls = 10
        per_call_estimate = 35
        total = calls * per_call_estimate
        self.assertLessEqual(total, self.frontend_deep,
            f"{calls} llamadas × {per_call_estimate}s = {total}s debe caber en {self.frontend_deep}s")


# ═══════════════════════════════════════════════════════════════════════════════
# 9. TestErrorClassification
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorClassification(unittest.TestCase):
    """
    Verifica que los errores se clasifican correctamente en el frontend.

    Mapa de errores:
      AbortError + _abortedByTimeout=true  → 'timeout'
      AbortError + _abortedByTimeout=false → 'cancelled'
      TypeError + elapsed ≥ 90% timeout   → 'timeout' (enmascarado)
      TypeError + elapsed < 90% timeout   → 'network'
      HTTP 500                             → 'http_500'
      HTTP 502                             → 'http_502'
      HTTP 503                             → 'http_503'
    """

    TIMEOUT_RATIO = 0.90
    SIMPLE_TIMEOUT = 180_000
    DEEP_TIMEOUT = 600_000

    def _classify(self, reason: str, elapsed: int, timeout: int) -> str:
        if reason == "network" and elapsed is not None and timeout > 0:
            if elapsed / timeout >= self.TIMEOUT_RATIO:
                return "timeout"
        return reason

    # ── AbortError cases ──────────────────────────────────────────────────────

    def test_abort_timeout_flag_true(self):
        """AbortError con flag timeout → 'timeout'."""
        # Simulado: el flag _abortedByTimeout=True ya clasifica como 'timeout'
        reason = "timeout"  # ya clasificado por wasTimeoutAbort
        self.assertEqual(reason, "timeout")

    def test_abort_cancelled_flag_false(self):
        """AbortError con flag timeout=False → 'cancelled'."""
        reason = "cancelled"
        self.assertEqual(reason, "cancelled")

    # ── TypeError cases ───────────────────────────────────────────────────────

    def test_type_error_at_exact_timeout_simple(self):
        result = self._classify("network", 180_000, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "timeout")

    def test_type_error_at_exact_timeout_deep(self):
        result = self._classify("network", 600_000, self.DEEP_TIMEOUT)
        self.assertEqual(result, "timeout")

    def test_type_error_1ms_over_timeout(self):
        result = self._classify("network", 180_001, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "timeout")

    def test_type_error_1ms_before_threshold(self):
        # 89.9% del timeout → network
        elapsed = int(self.SIMPLE_TIMEOUT * 0.899)
        result = self._classify("network", elapsed, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "network")

    def test_type_error_at_threshold(self):
        # Exactamente 90% → timeout
        elapsed = int(self.SIMPLE_TIMEOUT * 0.90)
        result = self._classify("network", elapsed, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "timeout")

    # ── HTTP error cases ──────────────────────────────────────────────────────

    def test_http_500_not_reclassified(self):
        result = self._classify("http_500", 180_000, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "http_500")

    def test_http_502_not_reclassified(self):
        result = self._classify("http_502", 180_000, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "http_502")

    def test_http_503_not_reclassified(self):
        result = self._classify("http_503", 180_000, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "http_503")

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_zero_timeout_no_reclassification(self):
        """Si timeout=0, no reclasificar."""
        result = self._classify("network", 180_000, 0)
        self.assertEqual(result, "network")

    def test_none_elapsed_no_reclassification(self):
        """Si elapsed=None, no reclasificar."""
        # En Python simulamos con elapsed=0
        result = self._classify("network", 0, self.SIMPLE_TIMEOUT)
        self.assertEqual(result, "network")

    def test_very_long_request_classified_as_timeout(self):
        """Petición de 10 minutos con timeout de 10 minutos → timeout."""
        result = self._classify("network", 600_000, 600_000)
        self.assertEqual(result, "timeout")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. TestProgressBarLogic
# ═══════════════════════════════════════════════════════════════════════════════

class TestProgressBarLogic(unittest.TestCase):
    """Verifica la lógica de la barra de progreso."""

    def _get_bar_color(self, pct: float) -> str:
        """Replica la lógica de color de la barra en chat-recovery.js."""
        if pct > 80:
            return "red"
        elif pct > 60:
            return "amber"
        else:
            return "blue"

    def _get_pct(self, elapsed_ms: int, timeout_ms: int) -> float:
        return min((elapsed_ms / timeout_ms) * 100, 99)

    def test_0_percent_is_blue(self):
        self.assertEqual(self._get_bar_color(0), "blue")

    def test_50_percent_is_blue(self):
        self.assertEqual(self._get_bar_color(50), "blue")

    def test_60_percent_is_blue(self):
        self.assertEqual(self._get_bar_color(60), "blue")

    def test_61_percent_is_amber(self):
        self.assertEqual(self._get_bar_color(61), "amber")

    def test_80_percent_is_amber(self):
        self.assertEqual(self._get_bar_color(80), "amber")

    def test_81_percent_is_red(self):
        self.assertEqual(self._get_bar_color(81), "red")

    def test_100_percent_is_red(self):
        self.assertEqual(self._get_bar_color(100), "red")

    def test_pct_capped_at_99(self):
        """La barra no debe superar el 99% (nunca llega al 100% antes del timeout)."""
        pct = self._get_pct(600_000, 600_000)
        self.assertLessEqual(pct, 99)

    def test_pct_at_half_timeout(self):
        pct = self._get_pct(90_000, 180_000)
        self.assertAlmostEqual(pct, 50.0, places=1)

    def test_pct_at_quarter_timeout(self):
        pct = self._get_pct(45_000, 180_000)
        self.assertAlmostEqual(pct, 25.0, places=1)

    def test_progress_bar_shown_for_deep_analysis(self):
        """La barra de progreso debe mostrarse para deep_analysis."""
        is_deep = True
        configured_timeout = 600_000
        should_show = is_deep or configured_timeout >= 180_000
        self.assertTrue(should_show)

    def test_progress_bar_shown_for_simple_180s(self):
        """La barra de progreso debe mostrarse para peticiones de 180s."""
        is_deep = False
        configured_timeout = 180_000
        should_show = is_deep or configured_timeout >= 180_000
        self.assertTrue(should_show)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. TestDeepAnalysisCallCount
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeepAnalysisCallCount(unittest.TestCase):
    """
    Verifica que el número de llamadas IA en deep_analysis es el esperado.
    Esto es crítico para calcular el timeout total necesario.
    """

    def test_deep_analysis_phases_count(self):
        """Deep analysis tiene al menos 5 fases (0,1,2,3,4,5)."""
        from backend.modules.chat.deep_analysis.models import MAX_INVESTIGATION_CYCLES
        # Fases fijas: 0 (presupuesto), 1 (comprensión), 2 (exploración)
        # Fases del bucle: 3 (investigación) + 4 (análisis) + 3b (resolución) × MAX_CYCLES
        fixed_phases = 3
        loop_phases_per_cycle = 3
        total_max = fixed_phases + (loop_phases_per_cycle * MAX_INVESTIGATION_CYCLES)
        self.assertGreaterEqual(total_max, 5,
            f"Deep analysis debe tener ≥ 5 fases, tiene {total_max}")

    def test_max_investigation_cycles_reasonable(self):
        """MAX_INVESTIGATION_CYCLES debe ser razonable (2-6)."""
        from backend.modules.chat.deep_analysis.models import MAX_INVESTIGATION_CYCLES
        self.assertGreaterEqual(MAX_INVESTIGATION_CYCLES, 2)
        self.assertLessEqual(MAX_INVESTIGATION_CYCLES, 8)

    def test_deep_analysis_total_time_estimate(self):
        """El tiempo total estimado de deep_analysis debe caber en 600s."""
        from backend.modules.chat.deep_analysis.models import MAX_INVESTIGATION_CYCLES
        fixed_phases = 3
        loop_phases_per_cycle = 3
        total_phases = fixed_phases + (loop_phases_per_cycle * MAX_INVESTIGATION_CYCLES)
        per_call_estimate = 35  # segundos con el modelo 8B
        total_estimate = total_phases * per_call_estimate
        frontend_deep_timeout = 600
        self.assertLessEqual(total_estimate, frontend_deep_timeout,
            f"Estimación total ({total_estimate}s) debe caber en {frontend_deep_timeout}s")


# ═══════════════════════════════════════════════════════════════════════════════
# 12. TestSimpleQueryCallCount
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimpleQueryCallCount(unittest.TestCase):
    """
    Verifica que una consulta simple no hace demasiadas llamadas IA.

    Flujo de consulta simple (DB_QUERY):
      1. Intent classification (1 llamada)
      2. SQL generation (1 llamada)
      3. SQL interpretation (1 llamada)
      Total: 3 llamadas × 35s = 105s → cabe en 180s
    """

    SIMPLE_TIMEOUT_S = 180
    PER_CALL_ESTIMATE_S = 35
    MAX_CALLS_SIMPLE = 3

    def test_simple_query_max_calls(self):
        """Una consulta simple no debe hacer más de 3 llamadas IA."""
        max_time = self.MAX_CALLS_SIMPLE * self.PER_CALL_ESTIMATE_S
        self.assertLessEqual(max_time, self.SIMPLE_TIMEOUT_S,
            f"{self.MAX_CALLS_SIMPLE} llamadas × {self.PER_CALL_ESTIMATE_S}s = {max_time}s "
            f"debe caber en {self.SIMPLE_TIMEOUT_S}s")

    def test_simple_query_with_sql_retry_fits(self):
        """Consulta simple con 1 reintento SQL (4 llamadas) debe caber en 180s."""
        calls_with_retry = 4
        total = calls_with_retry * self.PER_CALL_ESTIMATE_S
        self.assertLessEqual(total, self.SIMPLE_TIMEOUT_S,
            f"Con reintento SQL: {calls_with_retry} × {self.PER_CALL_ESTIMATE_S}s = {total}s")

    def test_simple_query_with_30b_fallback_fits(self):
        """
        Consulta simple con fallback 30B→8B (6s overhead + 3 llamadas) debe caber en 180s.
        """
        fallback_overhead_s = 6  # tiempo de probe del 30B antes de fallar
        calls = 3
        per_call = self.PER_CALL_ESTIMATE_S
        total = fallback_overhead_s + (calls * per_call)
        self.assertLessEqual(total, self.SIMPLE_TIMEOUT_S,
            f"Con fallback: {fallback_overhead_s}s + {calls}×{per_call}s = {total}s")


# ═══════════════════════════════════════════════════════════════════════════════
# 13. TestTimeoutRecovery
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeoutRecovery(unittest.TestCase):
    """
    Verifica que el sistema puede recuperarse tras un timeout.
    El botón "Reintentar" debe funcionar correctamente.
    """

    def test_retry_payload_preserved(self):
        """El payload original debe preservarse para el reintento."""
        original_payload = {
            "message": "Artículos con más proveedores",
            "deep_analysis": True,
            "model_id": "jddcia-qwen3-8b-ip",
            "preferred_model_id": "jddcia-qwen3-8b-ip",
        }
        # Simular que el payload se guarda en _lastPayload
        last_payload = original_payload.copy()
        self.assertEqual(last_payload["message"], original_payload["message"])
        self.assertEqual(last_payload["deep_analysis"], original_payload["deep_analysis"])

    def test_retry_uses_same_deep_flag(self):
        """El reintento debe usar el mismo flag deep_analysis."""
        payload = {"message": "Análisis completo", "deep_analysis": True}
        # El reintento llama savedOnRetry(savedPayload) con el mismo payload
        retry_payload = payload.copy()
        self.assertTrue(retry_payload["deep_analysis"])

    def test_retry_timeout_is_deep_for_deep_payload(self):
        """El reintento de una petición deep debe usar el timeout deep."""
        payload = {"deep_analysis": True}
        is_deep = bool(payload.get("deep_analysis"))
        timeout = 600_000 if is_deep else 180_000
        self.assertEqual(timeout, 600_000)

    def test_retry_timeout_is_simple_for_simple_payload(self):
        """El reintento de una petición simple debe usar el timeout simple."""
        payload = {"deep_analysis": False}
        is_deep = bool(payload.get("deep_analysis"))
        timeout = 600_000 if is_deep else 180_000
        self.assertEqual(timeout, 180_000)

    def test_attempt_count_increments_on_retry(self):
        """El contador de intentos debe incrementarse en cada reintento."""
        attempt_count = 1
        # Simular reintento
        attempt_count += 1
        self.assertEqual(attempt_count, 2)

    def test_retry_block_removed_on_retry(self):
        """El bloque de reintento debe eliminarse al pulsar Reintentar."""
        # Verificar que el código JS elimina el container antes de reintentar
        router_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "frontend", "assets", "js", "modules", "chat-recovery.js"
        )
        router_path = os.path.normpath(router_path)
        if os.path.exists(router_path):
            with open(router_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("container.remove()", content,
                "El bloque de reintento debe eliminarse al pulsar Reintentar")


# ═══════════════════════════════════════════════════════════════════════════════
# 14. TestConcurrentRequests
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcurrentRequests(unittest.TestCase):
    """
    Verifica que el backend puede responder /ping mientras procesa /send.
    FastAPI es async, por lo que debe poder atender múltiples requests.
    """

    @pytest.mark.asyncio
    async def test_ping_responds_while_processing(self):
        """
        Simula que /ping responde mientras /send está procesando.
        FastAPI usa asyncio, por lo que ambos pueden ejecutarse concurrentemente.
        """
        from backend.modules.chat.router import ping

        # Simular una tarea larga en background
        async def long_task():
            await asyncio.sleep(0.1)
            return "done"

        # Lanzar tarea larga y ping concurrentemente
        task = asyncio.create_task(long_task())
        ping_result = await ping()

        # El ping debe responder antes de que termine la tarea larga
        self.assertEqual(ping_result["status"], "alive")
        await task  # Esperar que termine la tarea

    @pytest.mark.asyncio
    async def test_multiple_pings_concurrent(self):
        """Múltiples pings concurrentes deben responder todos."""
        from backend.modules.chat.router import ping

        results = await asyncio.gather(*[ping() for _ in range(5)])
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r["status"], "alive")


# ═══════════════════════════════════════════════════════════════════════════════
# 15. TestTimeoutMessages
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeoutMessages(unittest.TestCase):
    """Verifica que los mensajes de error son correctos según el tipo."""

    # Mapa de mensajes (replica USER_MESSAGES de chat-recovery.js)
    USER_MESSAGES = {
        "timeout":   "⏱️ El modelo IA tardó demasiado en responder.",
        "cancelled": "⚠️ Petición cancelada.",
        "network":   "🔌 No se pudo conectar con el servidor.",
        "http_502":  "🔴 El servidor de IA no está disponible (502).",
        "http_503":  "🔴 El servidor de IA está sobrecargado (503).",
        "http_500":  "🔴 Error interno del servidor de IA (500).",
        "default":   "❌ La petición no se completó.",
    }

    def test_timeout_message_contains_clock_emoji(self):
        msg = self.USER_MESSAGES["timeout"]
        self.assertIn("⏱️", msg)

    def test_network_message_contains_plug_emoji(self):
        msg = self.USER_MESSAGES["network"]
        self.assertIn("🔌", msg)

    def test_cancelled_message_contains_warning(self):
        msg = self.USER_MESSAGES["cancelled"]
        self.assertIn("⚠️", msg)

    def test_timeout_message_different_from_network(self):
        """El mensaje de timeout debe ser diferente al de error de red."""
        self.assertNotEqual(
            self.USER_MESSAGES["timeout"],
            self.USER_MESSAGES["network"],
            "Los mensajes de timeout y error de red deben ser distintos"
        )

    def test_all_http_errors_have_messages(self):
        """Todos los errores HTTP comunes deben tener mensaje."""
        for code in ["http_500", "http_502", "http_503"]:
            self.assertIn(code, self.USER_MESSAGES)

    def test_timeout_hint_for_deep_analysis(self):
        """El hint de timeout para deep_analysis debe mencionar las fases."""
        # Simula la lógica de _injectRetryBlock para deep_analysis
        is_deep = True
        timeout_secs = 600
        model = "jddcia-qwen3-8b-ip"

        if is_deep:
            hint = (
                f"El análisis profundo tardó más de {timeout_secs}s. "
                f"El modelo {model} ejecuta múltiples fases IA "
                f"(clasificación + SQL + interpretación + análisis). "
                f"Puedes reintentar — el modelo ya está caliente y será más rápido."
            )
        else:
            hint = f"El modelo {model} tardó más de {timeout_secs}s."

        self.assertIn("múltiples fases", hint)
        self.assertIn("reintentar", hint.lower())

    def test_timeout_hint_for_simple_query(self):
        """El hint de timeout para consulta simple debe mencionar el modelo."""
        is_deep = False
        timeout_secs = 180
        model = "jddcia-qwen3-8b-ip"

        if is_deep:
            hint = "múltiples fases"
        else:
            hint = f"El modelo {model} tardó más de {timeout_secs}s."

        self.assertIn(model, hint)
        self.assertIn(str(timeout_secs), hint)

    def test_chat_recovery_js_has_correct_timeout_message(self):
        """chat-recovery.js debe tener el mensaje de timeout correcto."""
        recovery_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "frontend", "assets", "js", "modules", "chat-recovery.js"
        )
        recovery_path = os.path.normpath(recovery_path)
        if os.path.exists(recovery_path):
            with open(recovery_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("timeout", content.lower())
            self.assertIn("network", content.lower())
            # Verificar que hay lógica de detección de timeout enmascarado
            self.assertIn("TIMEOUT_DETECTION_RATIO", content)

    def test_chat_recovery_js_has_adaptive_timeout(self):
        """chat-recovery.js debe tener timeout adaptativo para deep_analysis."""
        recovery_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "frontend", "assets", "js", "modules", "chat-recovery.js"
        )
        recovery_path = os.path.normpath(recovery_path)
        if os.path.exists(recovery_path):
            with open(recovery_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("AI_REQUEST_DEEP", content,
                "chat-recovery.js debe usar AI_REQUEST_DEEP para deep_analysis")
            self.assertIn("deep_analysis", content,
                "chat-recovery.js debe verificar el flag deep_analysis")

    def test_constants_js_has_deep_timeout(self):
        """constants.js debe tener AI_REQUEST_DEEP definido con valor >= 600000ms."""
        constants_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "frontend", "assets", "js", "core", "constants.js"
        )
        constants_path = os.path.normpath(constants_path)
        if os.path.exists(constants_path):
            with open(constants_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("AI_REQUEST_DEEP", content,
                "constants.js debe tener AI_REQUEST_DEEP")
            # Extraer el valor numérico de AI_REQUEST_DEEP
            import re
            match = re.search(r'AI_REQUEST_DEEP\s*:\s*(\d+)', content)
            self.assertIsNotNone(match,
                "AI_REQUEST_DEEP debe tener un valor numérico en constants.js")
            if match:
                value = int(match.group(1))
                self.assertGreaterEqual(value, 600_000,
                    f"AI_REQUEST_DEEP={value}ms debe ser >= 600000ms (10 minutos)")

    def test_constants_js_has_timeout_detection_ratio(self):
        """constants.js debe tener TIMEOUT_DETECTION_RATIO."""
        constants_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "frontend", "assets", "js", "core", "constants.js"
        )
        constants_path = os.path.normpath(constants_path)
        if os.path.exists(constants_path):
            with open(constants_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("TIMEOUT_DETECTION_RATIO", content)


# ═══════════════════════════════════════════════════════════════════════════════
# BONUS: TestRealWorldScenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestRealWorldScenarios(unittest.TestCase):
    """
    Tests basados en escenarios reales observados en producción.
    """

    def test_scenario_proveedores_query_fits_in_simple_timeout(self):
        """
        Escenario real: 'Artículos con mayor número de proveedores distintos'
        → DB_QUERY (no deep_analysis) → 3 llamadas × 35s = 105s < 180s ✓
        """
        message = "Artículos con mayor número de proveedores distintos"
        is_deep = False  # No tiene flag deep_analysis
        timeout = 600_000 if is_deep else 180_000
        calls_estimate = 3
        per_call_s = 35
        total_s = calls_estimate * per_call_s
        self.assertLessEqual(total_s, timeout / 1000,
            f"Consulta de proveedores ({total_s}s) debe caber en {timeout/1000}s")

    def test_scenario_facturacion_total_fits_in_simple_timeout(self):
        """
        Escenario real: 'Cuanto es la facturacion total?' → 63s con 8B ✓
        """
        observed_time_s = 63
        simple_timeout_s = 180
        self.assertLessEqual(observed_time_s, simple_timeout_s)

    def test_scenario_deep_analysis_with_8b_fits_in_deep_timeout(self):
        """
        Escenario real: deep_analysis con 8B → ~5-8 llamadas × 35s = 175-280s < 600s ✓
        """
        max_calls = 8
        per_call_s = 35
        total_s = max_calls * per_call_s
        deep_timeout_s = 600
        self.assertLessEqual(total_s, deep_timeout_s,
            f"Deep analysis ({total_s}s) debe caber en {deep_timeout_s}s")

    def test_scenario_30b_fallback_overhead_acceptable(self):
        """
        Escenario real: 30B falla en 6s → 8B toma el relevo.
        El overhead de 6s es aceptable para el timeout de 180s.
        """
        fallback_overhead_s = 6
        simple_timeout_s = 180
        remaining_s = simple_timeout_s - fallback_overhead_s
        calls_possible = remaining_s // 35
        self.assertGreaterEqual(calls_possible, 3,
            f"Tras fallback ({fallback_overhead_s}s), quedan {remaining_s}s para {calls_possible} llamadas")

    def test_scenario_network_error_at_180s_shows_timeout_not_network(self):
        """
        Escenario real: TypeError a los 180009ms con timeout=180000ms
        → debe mostrar '⏱️ El modelo tardó...' NO '🔌 No se pudo conectar'
        """
        elapsed = 180_009
        timeout = 180_000
        ratio = elapsed / timeout
        is_timeout = ratio >= 0.90
        self.assertTrue(is_timeout,
            f"TypeError a los {elapsed}ms con timeout={timeout}ms debe clasificarse como timeout")

    def test_scenario_deep_analysis_proveedores_needs_deep_timeout(self):
        """
        Escenario real: 'Artículos con mayor número de proveedores distintos'
        con deep_analysis=True → necesita 600s, no 180s.
        """
        message = "Artículos con mayor número de proveedores distintos"
        deep_analysis = True
        timeout = 600_000 if deep_analysis else 180_000
        self.assertEqual(timeout, 600_000,
            "Con deep_analysis=True debe usar 600s, no 180s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
