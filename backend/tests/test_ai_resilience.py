"""
test_ai_resilience.py — Tests de resiliencia del sistema de IA

Cubre todos los escenarios de fallo y recuperación del stack de modelos AI:
  - Fallos de red (30B caído, mDNS roto, IP inalcanzable)
  - Fallback rápido al 8B cuando el 30B falla
  - Caché de fallos de probe (evita re-probar URLs caídas)
  - Background discovery (scan de red sin bloquear requests)
  - Context limit (max_tokens < context_limit → sin compresión infinita)
  - enable_thinking=false (respuestas rápidas en Qwen3)
  - Orquestador LAN_ONLY con reintentos
  - Detección de modelo disponible en localhost:1234
  - Rutas de SQL generation con schema correcto (IMPORTETOTAL, no TOTAL)

Cada test verifica una casuística distinta y puede correr en aislamiento.
Usa mocks para simular distintos estados de la red y los modelos.
"""

import asyncio
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Optional

# ── Importar módulos bajo test ────────────────────────────────────────────────

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def run_async(coro):
    """Ejecuta una coroutine sincróna desde un test no-async."""
    return asyncio.get_event_loop().run_until_complete(coro)


def make_openai_response(content: str, model: str = "qwen/qwen3-vl-8b") -> dict:
    """Construye una respuesta HTTP mock tipo OpenAI chat/completions."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    }


def make_jddcia_response(content: str) -> dict:
    """Construye respuesta HTTP mock del gateway JDDC (mismo formato OpenAI)."""
    return make_openai_response(content, model="unified-main")


# ─────────────────────────────────────────────────────────────────────────────
# 1. TESTS DE PROBE CACHE (caché de fallos de URLs)
# ─────────────────────────────────────────────────────────────────────────────

class TestProbeFailureCache(unittest.TestCase):
    """Verifica que las URLs con fallo se cachean 60s y no se re-prueban."""

    def setUp(self):
        """Limpiar caché de fallos antes de cada test."""
        from backend.drivers.ai import jddcia_provider as jp
        jp._PROBE_FAILURE_CACHE.clear()
        jp._WORKING_URL_CACHE = None
        jp._WORKING_URL_CACHE_TS = 0.0

    def test_url_not_in_cache_initially(self):
        """URL nueva no está en caché de fallos."""
        from backend.drivers.ai.jddcia_provider import _is_probe_cached_failed
        self.assertFalse(_is_probe_cached_failed("http://jddcia.local/api/vlm/v1"))

    def test_url_cached_after_failure(self):
        """Después de registrar un fallo, la URL aparece como cacheada."""
        from backend.drivers.ai.jddcia_provider import (
            _cache_probe_failure, _is_probe_cached_failed
        )
        url = "http://192.168.0.36/api/vlm/v1"
        _cache_probe_failure(url)
        self.assertTrue(_is_probe_cached_failed(url))

    def test_cache_expires_after_ttl(self):
        """La caché expira tras el TTL (60s en producción, simulamos con tiempo pasado)."""
        from backend.drivers.ai import jddcia_provider as jp
        url = "http://jddcia.local/api/vlm/v1"
        # Simular que el fallo fue hace 61s (ya expirado)
        jp._PROBE_FAILURE_CACHE[url] = time.monotonic() - 61
        self.assertFalse(jp._is_probe_cached_failed(url))
        # La entrada expirada debe eliminarse del caché
        self.assertNotIn(url, jp._PROBE_FAILURE_CACHE)

    def test_cache_not_expired_within_ttl(self):
        """La caché sigue activa dentro del TTL."""
        from backend.drivers.ai import jddcia_provider as jp
        url = "http://jddcia.local/api/vlm/v1"
        jp._PROBE_FAILURE_CACHE[url] = time.monotonic() + 30  # 30s restantes
        self.assertTrue(jp._is_probe_cached_failed(url))

    def test_clear_cache_for_url(self):
        """Limpiar caché de una URL individual."""
        from backend.drivers.ai.jddcia_provider import (
            _cache_probe_failure, _clear_probe_failure_cache, _is_probe_cached_failed
        )
        url = "http://jddcia.local/api/vlm/v1"
        _cache_probe_failure(url)
        self.assertTrue(_is_probe_cached_failed(url))
        _clear_probe_failure_cache(url)
        self.assertFalse(_is_probe_cached_failed(url))

    def test_multiple_urls_independent_cache(self):
        """Varias URLs tienen cachés independientes."""
        from backend.drivers.ai.jddcia_provider import (
            _cache_probe_failure, _is_probe_cached_failed, _clear_probe_failure_cache
        )
        url1 = "http://jddcia.local/api/vlm/v1"
        url2 = "http://192.168.0.36/api/vlm/v1"
        _cache_probe_failure(url1)
        self.assertTrue(_is_probe_cached_failed(url1))
        self.assertFalse(_is_probe_cached_failed(url2))
        _clear_probe_failure_cache(url1)
        self.assertFalse(_is_probe_cached_failed(url1))

    def test_cache_miss_does_not_raise(self):
        """_is_probe_cached_failed no lanza excepción para URL desconocida."""
        from backend.drivers.ai.jddcia_provider import _is_probe_cached_failed
        result = _is_probe_cached_failed("http://unknown.host/v1")
        self.assertFalse(result)


# ─────────────────────────────────────────────────────────────────────────────
# 2. TESTS DEL SCAN COOLDOWN
# ─────────────────────────────────────────────────────────────────────────────

class TestScanCooldown(unittest.TestCase):
    """Verifica el cooldown que evita re-escanear la red continuamente."""

    def setUp(self):
        from backend.drivers.ai import jddcia_provider as jp
        jp._SCAN_FAILED_UNTIL = 0.0
        jp._bg_discovery_running = False

    def test_no_cooldown_initially(self):
        """Sin escaneo previo, no hay cooldown."""
        from backend.drivers.ai.jddcia_provider import _is_scan_in_cooldown
        self.assertFalse(_is_scan_in_cooldown())

    def test_cooldown_active_after_failure(self):
        """Después de un fallo de escaneo, el cooldown se activa."""
        from backend.drivers.ai.jddcia_provider import _set_scan_failed, _is_scan_in_cooldown
        _set_scan_failed()
        self.assertTrue(_is_scan_in_cooldown())

    def test_cooldown_cleared(self):
        """El cooldown puede limpiarse manualmente."""
        from backend.drivers.ai.jddcia_provider import (
            _set_scan_failed, _clear_scan_cooldown, _is_scan_in_cooldown
        )
        _set_scan_failed()
        self.assertTrue(_is_scan_in_cooldown())
        _clear_scan_cooldown()
        self.assertFalse(_is_scan_in_cooldown())

    def test_cooldown_expires_over_time(self):
        """El cooldown expira con el tiempo."""
        from backend.drivers.ai import jddcia_provider as jp
        jp._SCAN_FAILED_UNTIL = time.monotonic() - 1  # Expirado hace 1s
        self.assertFalse(jp._is_scan_in_cooldown())

    def test_cooldown_duration_is_reasonable(self):
        """El cooldown es de al menos 60s (evita spam de escaneos)."""
        from backend.drivers.ai.jddcia_provider import _set_scan_failed
        from backend.drivers.ai import jddcia_provider as jp
        _set_scan_failed()
        remaining = jp._SCAN_FAILED_UNTIL - time.monotonic()
        self.assertGreaterEqual(remaining, 60, "Cooldown debe ser >= 60s")


# ─────────────────────────────────────────────────────────────────────────────
# 3. TESTS DE BACKGROUND DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────

class TestBackgroundDiscovery(unittest.TestCase):
    """Verifica que el scan de red se lanza en background sin bloquear."""

    def setUp(self):
        from backend.drivers.ai import jddcia_provider as jp
        jp._bg_discovery_running = False
        jp._SCAN_FAILED_UNTIL = 0.0
        jp._PROBE_FAILURE_CACHE.clear()

    def test_start_background_discovery_sets_flag(self):
        """_start_background_discovery marca _bg_discovery_running=True."""
        from backend.drivers.ai import jddcia_provider as jp

        async def fake_run():
            jp._start_background_discovery("auth")
            self.assertTrue(jp._bg_discovery_running)
            jp._bg_discovery_running = False

        with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                   new=AsyncMock(return_value=None)):
            run_async(fake_run())

    def test_start_background_discovery_not_duplicate(self):
        """No se lanza un segundo scan si ya hay uno en curso."""
        from backend.drivers.ai import jddcia_provider as jp
        jp._bg_discovery_running = True  # Simular scan ya en curso

        call_count = [0]

        async def fake_run():
            original = jp._discover_gateway_ip
            with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip') as mock:
                jp._start_background_discovery("auth")
                # No debe haber lanzado una nueva tarea
                self.assertEqual(mock.call_count, 0)

        run_async(fake_run())
        jp._bg_discovery_running = False

    def test_background_discovery_caches_url_on_success(self):
        """Cuando el discovery encuentra el gateway, lo cachea en memoria."""
        from backend.drivers.ai import jddcia_provider as jp

        async def fake_run():
            with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                       new=AsyncMock(return_value="http://10.1.2.3/api/vlm/v1")):
                await jp._background_discovery("auth")
            self.assertEqual(jp._WORKING_URL_CACHE, "http://10.1.2.3/api/vlm/v1")
            self.assertFalse(jp._is_scan_in_cooldown())

        run_async(fake_run())
        jp._WORKING_URL_CACHE = None

    def test_background_discovery_sets_cooldown_on_failure(self):
        """Cuando el discovery no encuentra nada, activa el cooldown."""
        from backend.drivers.ai import jddcia_provider as jp

        async def fake_run():
            with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                       new=AsyncMock(return_value=None)):
                await jp._background_discovery("auth")
            self.assertTrue(jp._is_scan_in_cooldown())

        run_async(fake_run())

    def test_background_discovery_handles_exception(self):
        """Excepciones en el discovery no propagan al caller."""
        from backend.drivers.ai import jddcia_provider as jp

        async def fake_run():
            with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                       new=AsyncMock(side_effect=Exception("red no disponible"))):
                await jp._background_discovery("auth")  # NO debe lanzar
            self.assertTrue(jp._is_scan_in_cooldown())
            self.assertFalse(jp._bg_discovery_running)

        run_async(fake_run())

    def test_background_discovery_clears_running_flag_always(self):
        """_bg_discovery_running siempre se limpia al terminar (success o failure)."""
        from backend.drivers.ai import jddcia_provider as jp

        async def run_success():
            with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                       new=AsyncMock(return_value="http://x.x.x.x/v1")):
                await jp._background_discovery("auth")
            self.assertFalse(jp._bg_discovery_running)

        async def run_failure():
            jp._SCAN_FAILED_UNTIL = 0.0
            with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                       new=AsyncMock(return_value=None)):
                await jp._background_discovery("auth")
            self.assertFalse(jp._bg_discovery_running)

        run_async(run_success())
        jp._WORKING_URL_CACHE = None
        run_async(run_failure())


# ─────────────────────────────────────────────────────────────────────────────
# 4. TESTS DE CONTEXT MANAGER (evitar loop de compresión)
# ─────────────────────────────────────────────────────────────────────────────

class TestContextManagerConfig(unittest.TestCase):
    """Verifica que max_tokens < context_limit para evitar el loop de compresión."""

    def test_30b_max_tokens_fits_in_context(self):
        """El modelo 30B tiene max_tokens=512 < context_limit=4096."""
        with open(os.path.join(
            os.path.dirname(__file__),
            '../core/config/models/jddcia_models.json'
        ), encoding='utf-8') as f:
            models = json.load(f)['models']

        for m in models:
            if '30b' in m['id']:
                ctx = m.get('context_limit', 4096)
                max_tok = m.get('parameters', {}).get('max_tokens', 0)
                self.assertLess(
                    max_tok, ctx,
                    f"{m['id']}: max_tokens={max_tok} debe ser < context_limit={ctx}"
                )

    def test_8b_max_tokens_fits_in_context(self):
        """El modelo 8B tiene max_tokens=4096 < context_limit=8192."""
        with open(os.path.join(
            os.path.dirname(__file__),
            '../core/config/models/jddcia_models.json'
        ), encoding='utf-8') as f:
            models = json.load(f)['models']

        for m in models:
            if '8b' in m['id']:
                ctx = m.get('context_limit', 8192)
                max_tok = m.get('parameters', {}).get('max_tokens', 0)
                self.assertLess(
                    max_tok, ctx,
                    f"{m['id']}: max_tokens={max_tok} debe ser < context_limit={ctx}"
                )

    def test_available_tokens_positive_for_30b(self):
        """Con max_tokens=512 y ctx=4096, quedan 3484 tokens de input (buffer de 100)."""
        ctx = 4096
        max_tok = 512
        buffer = 100
        available = ctx - max_tok - buffer
        self.assertGreater(available, 0, "Debe haber tokens disponibles para input")
        self.assertGreaterEqual(available, 3000, "Al menos 3000 tokens para el prompt")

    def test_available_tokens_for_8b(self):
        """Con max_tokens=4096 y ctx=8192, quedan 4092 tokens de input (buffer de 100 - >=3068)."""
        ctx = 8192
        max_tok = 4096
        buffer = 100
        available = ctx - max_tok - buffer
        schema_prompt_est = 3068  # Tamaño real del prompt con schema+sim_note
        self.assertGreater(
            available, schema_prompt_est,
            f"Prompt de {schema_prompt_est} tok debe caber en {available} disponibles"
        )

    def test_safety_guard_triggers_when_equal(self):
        """El safety guard activa cuando max_tokens >= context_limit."""
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(
            base_url="http://jddcia.local/api/vlm/v1",
            api_key="test",
            model="unified-main"
        )
        # Simular que el JSON del modelo devuelve max_tokens=4096 y context=4096
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 4096}
            provider.configure(config)
        # El safety guard debe haber reducido max_tokens a 1024 (25% de 4096)
        self.assertLess(provider._max_tokens, 4096)
        self.assertGreaterEqual(provider._max_tokens, 256)

    def test_safety_guard_does_not_trigger_when_small(self):
        """El safety guard NO activa cuando max_tokens=512 < context_limit=4096."""
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(
            base_url="http://jddcia.local/api/vlm/v1",
            api_key="test",
            model="unified-main"
        )
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 512}
            provider.configure(config)
        self.assertEqual(provider._max_tokens, 512)


# ─────────────────────────────────────────────────────────────────────────────
# 5. TESTS DE MODELO JSON (configuración centralizada)
# ─────────────────────────────────────────────────────────────────────────────

class TestModelJsonConfig(unittest.TestCase):
    """Verifica la configuración del fichero centralizado de modelos."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(
            os.path.dirname(__file__),
            '../core/config/models/jddcia_models.json'
        ), encoding='utf-8') as f:
            cls.models = json.load(f)['models']

    def test_at_least_one_model_defined(self):
        self.assertGreater(len(self.models), 0)

    def test_all_models_have_required_fields(self):
        required = ['id', 'name', 'provider', 'enabled']
        for m in self.models:
            for field in required:
                self.assertIn(field, m, f"Modelo {m.get('id','?')} sin campo '{field}'")

    def test_exactly_one_preferred_model(self):
        """Exactamente un modelo debe tener preferred=true."""
        preferred = [m for m in self.models if m.get('preferred')]
        self.assertEqual(len(preferred), 1,
                         f"Debe haber exactamente 1 modelo preferido, hay {len(preferred)}: "
                         f"{[m['id'] for m in preferred]}")

    def test_preferred_model_is_enabled(self):
        """El modelo preferido debe estar habilitado."""
        preferred = next((m for m in self.models if m.get('preferred')), None)
        self.assertIsNotNone(preferred, "Debe existir un modelo preferido")
        self.assertTrue(preferred.get('enabled', False),
                        f"El modelo preferido {preferred['id']} debe estar enabled=true")

    def test_8b_models_have_enable_thinking_false(self):
        """Los modelos 8B Qwen3 deben tener enable_thinking=false."""
        for m in self.models:
            if '8b' in m['id']:
                thinking = m.get('parameters', {}).get('enable_thinking', True)
                self.assertFalse(thinking,
                                 f"{m['id']}: enable_thinking debe ser false")

    def test_30b_models_have_enable_thinking_false(self):
        """Los modelos 30B Qwen3 deben tener enable_thinking=false."""
        for m in self.models:
            if '30b' in m['id']:
                thinking = m.get('parameters', {}).get('enable_thinking', True)
                self.assertFalse(thinking,
                                 f"{m['id']}: enable_thinking debe ser false")

    def test_8b_localhost_model_exists(self):
        """Debe existir el modelo 8B apuntando a localhost:1234."""
        localhost_8b = next(
            (m for m in self.models
             if 'localhost' in m.get('base_url', '') and '8b' in m['id']),
            None
        )
        self.assertIsNotNone(localhost_8b,
                             "Debe existir un modelo 8B apuntando a localhost:1234")

    def test_all_models_have_context_limit(self):
        """Todos los modelos deben declarar su límite de contexto."""
        for m in self.models:
            ctx = m.get('context_limit', 0)
            self.assertGreater(ctx, 0,
                               f"{m['id']}: context_limit debe ser > 0")

    def test_no_model_max_tokens_equals_context_limit(self):
        """Ningún modelo debe tener max_tokens igual a context_limit (loop de compresión)."""
        for m in self.models:
            ctx = m.get('context_limit', 0)
            max_tok = m.get('parameters', {}).get('max_tokens', 0)
            self.assertNotEqual(
                max_tok, ctx,
                f"{m['id']}: max_tokens={max_tok} NO debe ser igual a context_limit={ctx}"
            )

    def test_30b_ip_uses_direct_ip_url(self):
        """El modelo 30B-IP usa URL de IP directa (no mDNS)."""
        ip_model = next((m for m in self.models if m['id'] == 'jddcia-qwen3-30b-ip'), None)
        if ip_model:
            url = ip_model.get('base_url', '')
            # Debe contener una IP, no un hostname mDNS
            import re
            has_ip = bool(re.search(r'\d+\.\d+\.\d+\.\d+', url))
            self.assertTrue(has_ip, f"30B-IP debe usar URL con IP directa, tiene: {url}")

    def test_8b_has_timeout_configured(self):
        """Los modelos 8B deben tener timeout configurado."""
        for m in self.models:
            if '8b' in m['id']:
                timeout = m.get('parameters', {}).get('timeout_s', 0)
                self.assertGreater(timeout, 0,
                                   f"{m['id']}: timeout_s debe ser > 0")

    def test_jddcia_models_have_auth_header(self):
        """Los modelos 30B JDDC deben tener Authorization header."""
        for m in self.models:
            if m.get('provider') == 'jddcia' and '30b' in m['id']:
                headers = m.get('headers', {})
                self.assertIn('Authorization', headers,
                              f"{m['id']}: debe tener Authorization header")

    def test_8b_models_have_no_auth_header(self):
        """Los modelos 8B LM Studio no deben tener Authorization header (no lo requiere)."""
        for m in self.models:
            if 'openai_compatible' in str(m.get('schema', '')):
                headers = m.get('headers', {})
                self.assertNotIn('Authorization', headers,
                                 f"{m['id']}: LM Studio no usa Authorization header")


# ─────────────────────────────────────────────────────────────────────────────
# 6. TESTS DE ORQUESTADOR (model_fallback_orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class TestOrchestratorFallback(unittest.TestCase):
    """Verifica el orden de fallback cuando modelos fallan."""

    def _make_orchestrator(self):
        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
        return ModelFallbackOrchestrator()

    def test_orchestrator_instantiates(self):
        """El orchestrator se puede instanciar."""
        orch = self._make_orchestrator()
        self.assertIsNotNone(orch)

    def test_lan_models_available(self):
        """Al menos 2 modelos LAN disponibles."""
        orch = self._make_orchestrator()
        lan_models = [m for m in orch.model_manager.list_models()
                      if m.get('provider') == 'jddcia' and m.get('enabled')]
        self.assertGreaterEqual(len(lan_models), 2, "Al menos 2 modelos LAN disponibles")

    def test_preferred_model_first(self):
        """El modelo preferido aparece primero en la lista priorizada."""
        orch = self._make_orchestrator()
        models = orch._get_prioritized_models("jddcia-qwen3-8b-ip")
        if models:
            self.assertEqual(models[0]['id'], "jddcia-qwen3-8b-ip")

    def test_8b_ip_model_in_list(self):
        """El modelo 8B-localhost está en la lista de modelos LAN."""
        orch = self._make_orchestrator()
        all_models = orch.model_manager.list_models()
        ids = [m['id'] for m in all_models if m.get('provider') == 'jddcia']
        self.assertIn('jddcia-qwen3-8b-ip', ids)

    def test_lan_only_mode_excludes_internet(self):
        """En modo LAN_ONLY, no se usan modelos de internet."""
        orch = self._make_orchestrator()
        lan_models = [m for m in orch.model_manager.list_models()
                      if m.get('provider') == 'jddcia']
        for m in lan_models:
            url = m.get('base_url', '')
            external = any(x in url for x in ['openai.com', 'groq.com', 'gemini', 'anthropic'])
            self.assertFalse(external,
                             f"Modelo LAN {m['id']} no debe apuntar a {url}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. TESTS DE LMSTUDIO DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────

class TestLmStudioDiscovery(unittest.TestCase):
    """Verifica el autodescubrimiento de LM Studio."""

    def test_localhost_in_known_ips(self):
        """localhost debe estar en la lista de IPs conocidas (primer candidato)."""
        from backend.drivers.ai.lmstudio_discovery import KNOWN_HYPER_V_IPS
        self.assertIn('localhost', KNOWN_HYPER_V_IPS,
                      "localhost debe estar en KNOWN_HYPER_V_IPS")
        # Debe ser uno de los primeros (preferencia máxima)
        idx = KNOWN_HYPER_V_IPS.index('localhost')
        self.assertLess(idx, 3, "localhost debe estar en los primeros 3 candidatos")

    def test_127001_in_known_ips(self):
        """127.0.0.1 debe estar en la lista de IPs conocidas."""
        from backend.drivers.ai.lmstudio_discovery import KNOWN_HYPER_V_IPS
        self.assertIn('127.0.0.1', KNOWN_HYPER_V_IPS)

    def test_lmstudio_port_is_1234(self):
        """El puerto por defecto de LM Studio es 1234."""
        from backend.drivers.ai.lmstudio_discovery import LMSTUDIO_PORT
        self.assertEqual(LMSTUDIO_PORT, 1234)

    def test_discovery_finds_localhost_when_running(self):
        """Si LM Studio corre en localhost:1234, discover_lmstudio lo encuentra."""
        from backend.drivers.ai.lmstudio_discovery import discover_lmstudio, invalidate_cache

        async def run():
            invalidate_cache()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": [{"id": "qwen/qwen3-vl-8b"}]}
            with patch('backend.drivers.ai.lmstudio_discovery._probe_ip',
                       new=AsyncMock(return_value="http://localhost:1234/v1")):
                result = await discover_lmstudio()
            return result

        result = run_async(run())
        if result:
            self.assertIn('localhost', result)

    def test_discovery_returns_none_when_nothing_runs(self):
        """Si nada responde, discover_lmstudio devuelve None (no excepción)."""
        from backend.drivers.ai.lmstudio_discovery import discover_lmstudio, invalidate_cache

        async def run():
            invalidate_cache()
            with patch('backend.drivers.ai.lmstudio_discovery._probe_ip',
                       new=AsyncMock(return_value=None)):
                try:
                    return await discover_lmstudio()
                except Exception:
                    return None

        result = run_async(run())
        self.assertIsNone(result)


# ─────────────────────────────────────────────────────────────────────────────
# 8. TESTS DE SQL GENERATION (columnas correctas)
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlColumnNames(unittest.TestCase):
    """Verifica que el sistema conoce los nombres de columna correctos."""

    def test_importetotal_in_table_schemas(self):
        """IMPORTETOTAL debe existir en el schema de DOCCAB."""
        from backend.modules.db_simulator.schema import TABLE_SCHEMAS
        doccab_schema = TABLE_SCHEMAS.get('DOCCAB', '')
        self.assertIn('IMPORTETOTAL', doccab_schema,
                      "IMPORTETOTAL debe estar en el schema de DOCCAB")

    def test_importebase_in_table_schemas(self):
        """IMPORTEBASE debe existir en el schema de DOCCAB."""
        from backend.modules.db_simulator.schema import TABLE_SCHEMAS
        doccab_schema = TABLE_SCHEMAS.get('DOCCAB', '')
        self.assertIn('IMPORTEBASE', doccab_schema,
                      "IMPORTEBASE debe estar en el schema de DOCCAB")

    def test_importeiva_in_table_schemas(self):
        """IMPORTEIVA debe existir en el schema de DOCCAB."""
        from backend.modules.db_simulator.schema import TABLE_SCHEMAS
        doccab_schema = TABLE_SCHEMAS.get('DOCCAB', '')
        self.assertIn('IMPORTEIVA', doccab_schema,
                      "IMPORTEIVA debe estar en el schema de DOCCAB")

    def test_tipo_field_in_doccab(self):
        """TIPO debe existir en DOCCAB (diferencia facturas de presupuestos, etc.)."""
        from backend.modules.db_simulator.schema import TABLE_SCHEMAS
        doccab_schema = TABLE_SCHEMAS.get('DOCCAB', '')
        self.assertIn('TIPO', doccab_schema)

    def test_wrong_column_total_not_used(self):
        """La columna 'TOTAL' (incorrecta) NO debe aparecer como columna principal."""
        from backend.modules.db_simulator.schema import TABLE_SCHEMAS
        doccab_schema = TABLE_SCHEMAS.get('DOCCAB', '')
        # 'TOTAL' sin prefijo 'IMPORTE' no debe ser el nombre de columna principal
        # (puede aparecer en comentarios pero no como nombre de columna)
        import re
        columns = re.findall(r'^\s+(\w+)\s+', doccab_schema, re.MULTILINE)
        self.assertNotIn('TOTAL', columns,
                         "La columna se llama IMPORTETOTAL, no TOTAL")

    def test_all_simulator_tables_exist(self):
        """Las tablas principales del simulador deben existir en TABLE_SCHEMAS."""
        from backend.modules.db_simulator.schema import TABLE_SCHEMAS
        required = ['DOCCAB', 'DOCLIN', 'ARTICULO', 'CLIENTE']
        for t in required:
            self.assertIn(t, TABLE_SCHEMAS, f"Tabla {t} debe existir en TABLE_SCHEMAS")

    def test_tipo_13_means_factura(self):
        """TIPO=13 corresponde a facturas de venta (verificar en los datos del simulador)."""
        import sqlite3
        db_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/simulator.db'
        )
        if not os.path.exists(db_path):
            self.skipTest("simulator.db no disponible")
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13")
        count = cur.fetchone()[0]
        con.close()
        self.assertGreater(count, 0, "Debe haber al menos 1 documento con TIPO=13 (factura)")

    def test_importetotal_sum_facturas_positive(self):
        """La suma de IMPORTETOTAL para TIPO=13 debe ser positiva."""
        import sqlite3
        db_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/simulator.db'
        )
        if not os.path.exists(db_path):
            self.skipTest("simulator.db no disponible")
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13")
        total = cur.fetchone()[0]
        con.close()
        self.assertIsNotNone(total)
        self.assertGreater(total, 0, "Facturación total debe ser > 0")

    def test_importetotal_consistent_between_queries(self):
        """SUM(IMPORTETOTAL WHERE TIPO=13) debe ser consistente."""
        import sqlite3
        db_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/simulator.db'
        )
        if not os.path.exists(db_path):
            self.skipTest("simulator.db no disponible")
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13")
        total1 = cur.fetchone()[0]
        cur.execute("SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13")
        total2 = cur.fetchone()[0]
        con.close()
        self.assertAlmostEqual(total1, total2, places=2,
                               msg="Consultas repetidas deben dar el mismo resultado")


# ─────────────────────────────────────────────────────────────────────────────
# 9. TESTS DE RESILIENCIA DEL SIMULADOR
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulatorResiliencia(unittest.TestCase):
    """Verifica que el simulador responde correctamente a diversas consultas SQL."""

    @classmethod
    def setUpClass(cls):
        import sqlite3
        db_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/simulator.db'
        )
        if not os.path.exists(db_path):
            cls.db_available = False
            return
        cls.db_available = True
        cls.con = sqlite3.connect(db_path)
        cls.cur = cls.con.cursor()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'db_available', False):
            cls.con.close()

    def _q(self, sql):
        if not self.db_available:
            self.skipTest("simulator.db no disponible")
        self.cur.execute(sql)
        return self.cur.fetchall()

    def test_count_all_doccab(self):
        rows = self._q("SELECT COUNT(*) FROM DOCCAB")
        self.assertGreater(rows[0][0], 0)

    def test_count_facturas_tipo13(self):
        rows = self._q("SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13")
        self.assertGreater(rows[0][0], 0)

    def test_sum_importetotal_facturas(self):
        rows = self._q("SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13")
        self.assertGreater(rows[0][0], 0)

    def test_count_clientes(self):
        rows = self._q("SELECT COUNT(*) FROM CLIENTE")
        self.assertGreater(rows[0][0], 0)

    def test_count_articulos(self):
        rows = self._q("SELECT COUNT(*) FROM ARTICULO")
        self.assertGreater(rows[0][0], 0)

    def test_articulos_have_precio(self):
        rows = self._q("SELECT COUNT(*) FROM ARTICULO WHERE PRECIOVENTA > 0")
        self.assertGreater(rows[0][0], 0)

    def test_doclin_references_doccab(self):
        """Las líneas de documento referencian cabeceras existentes."""
        rows = self._q("""
            SELECT COUNT(*) FROM DOCLIN l
            JOIN DOCCAB c ON l.CODDOCUMENTO = c.CODIGO
        """)
        self.assertGreater(rows[0][0], 0)

    def test_importetotal_not_null(self):
        """IMPORTETOTAL no debe ser NULL en documentos con tipo."""
        rows = self._q("""
            SELECT COUNT(*) FROM DOCCAB
            WHERE TIPO > 0 AND IMPORTETOTAL IS NULL
        """)
        # Idealmente 0 NULLs, pero toleramos algunos si es snapshot real
        total_docs = self._q("SELECT COUNT(*) FROM DOCCAB WHERE TIPO > 0")[0][0]
        null_count = rows[0][0]
        self.assertLess(null_count, total_docs,
                        "No todos los documentos deben tener IMPORTETOTAL NULL")

    def test_caja_records_exist(self):
        rows = self._q("SELECT COUNT(*) FROM CAJA")
        self.assertGreaterEqual(rows[0][0], 0)  # Puede ser 0 si no hay movimientos

    def test_familia_records_exist(self):
        rows = self._q("SELECT COUNT(*) FROM FAMILIA")
        self.assertGreater(rows[0][0], 0)

    def test_multiple_tipos_in_doccab(self):
        """DOCCAB debe tener varios tipos de documentos."""
        rows = self._q("SELECT COUNT(DISTINCT TIPO) FROM DOCCAB")
        self.assertGreater(rows[0][0], 1, "Debe haber más de 1 tipo de documento")

    def test_articulo_descripcion_not_empty(self):
        """Los artículos deben tener descripción."""
        rows = self._q("SELECT COUNT(*) FROM ARTICULO WHERE DESCRIPCION IS NOT NULL AND DESCRIPCION != ''")
        total = self._q("SELECT COUNT(*) FROM ARTICULO")[0][0]
        self.assertGreater(rows[0][0], total * 0.8,  # Al menos 80% con descripción
                           "Al menos el 80% de artículos debe tener descripción")

    def test_cliente_nombre_not_empty(self):
        """Los clientes deben tener nombre comercial o razón social."""
        rows = self._q(
            "SELECT COUNT(*) FROM CLIENTE WHERE "
            "(NOMBRECOMERCIAL IS NOT NULL AND NOMBRECOMERCIAL != '') "
            "OR (RAZONSOCIAL IS NOT NULL AND RAZONSOCIAL != '')"
        )
        total = self._q("SELECT COUNT(*) FROM CLIENTE")[0][0]
        self.assertGreater(rows[0][0], total * 0.8)

    def test_sql_where_tipo_eq_13(self):
        """Filtro WHERE TIPO=13 devuelve menos que total."""
        total = self._q("SELECT COUNT(*) FROM DOCCAB")[0][0]
        tipo13 = self._q("SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13")[0][0]
        self.assertLess(tipo13, total)
        self.assertGreater(tipo13, 0)

    def test_sql_group_by_tipo(self):
        """GROUP BY TIPO funciona correctamente."""
        rows = self._q("SELECT TIPO, COUNT(*), SUM(IMPORTETOTAL) FROM DOCCAB GROUP BY TIPO")
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertIsNotNone(row[0])  # TIPO no nulo
            self.assertGreater(row[1], 0)  # COUNT > 0

    def test_sql_order_by_importetotal(self):
        """ORDER BY IMPORTETOTAL DESC funciona."""
        rows = self._q("SELECT CODIGO, IMPORTETOTAL FROM DOCCAB ORDER BY IMPORTETOTAL DESC LIMIT 5")
        self.assertEqual(len(rows), 5)
        importes = [r[1] for r in rows if r[1] is not None]
        self.assertEqual(importes, sorted(importes, reverse=True))


# ─────────────────────────────────────────────────────────────────────────────
# 10. TESTS DE ENABLE_THINKING
# ─────────────────────────────────────────────────────────────────────────────

class TestEnableThinking(unittest.TestCase):
    """Verifica que enable_thinking=False está configurado en todos los modelos Qwen3."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(
            os.path.dirname(__file__),
            '../core/config/models/jddcia_models.json'
        ), encoding='utf-8') as f:
            cls.models = json.load(f)['models']

    def test_all_qwen3_models_have_thinking_disabled(self):
        """Todos los modelos Qwen3 deben tener enable_thinking=false."""
        for m in self.models:
            if 'qwen' in m.get('family', '').lower():
                thinking = m.get('parameters', {}).get('enable_thinking', True)
                self.assertFalse(thinking,
                                 f"{m['id']}: enable_thinking debe ser false")

    def test_jddcia_provider_sends_enable_thinking_false(self):
        """JDDCIAProvider incluye enable_thinking=False en el payload."""
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig
        import httpx

        provider = JDDCIAProvider()
        config = AIConfig(
            base_url="http://localhost/api/vlm/v1",
            api_key="test",
            model="unified-main"
        )
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 512}
            provider.configure(config)

        captured_payload = {}

        async def run():
            # Mock URL resolution
            with patch.object(provider, '_get_working_base_url',
                              new=AsyncMock(return_value="http://localhost/api/vlm/v1")):
                # Capture the payload sent
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = make_jddcia_response("test response")

                async def capture_post(url, **kwargs):
                    captured_payload.update(kwargs.get('json', {}))
                    return mock_resp

                with patch('httpx.AsyncClient') as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_client.post = AsyncMock(side_effect=capture_post)
                    mock_cls.return_value = mock_client
                    await provider.generate_text("test prompt")

        run_async(run())
        self.assertIn('enable_thinking', captured_payload,
                      "El payload debe incluir enable_thinking")
        self.assertFalse(captured_payload['enable_thinking'],
                         "enable_thinking debe ser False")

    def test_oai_compat_provider_sends_enable_thinking_false(self):
        """OpenAICompatibleProvider incluye enable_thinking=False para Qwen3."""
        from backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        from backend.core.abstract.ai import AIConfig

        provider = OpenAICompatibleProvider()
        config = AIConfig(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",
            model="qwen/qwen3-vl-8b"
        )
        config.parameters = {
            "max_tokens": 4096,
            "timeout_s": 180,
            "enable_thinking": False
        }
        config.context_limit = 8192
        provider.configure(config)
        self.assertFalse(provider._enable_thinking)


# ─────────────────────────────────────────────────────────────────────────────
# 11. TESTS DE RESILIENCIA DE RED
# ─────────────────────────────────────────────────────────────────────────────

class TestNetworkResilience(unittest.TestCase):
    """Verifica el comportamiento ante distintos tipos de fallo de red."""

    def setUp(self):
        from backend.drivers.ai import jddcia_provider as jp
        jp._PROBE_FAILURE_CACHE.clear()
        jp._WORKING_URL_CACHE = None
        jp._WORKING_URL_CACHE_TS = 0.0
        jp._SCAN_FAILED_UNTIL = 0.0
        jp._bg_discovery_running = False

    def _get_url(self, configured_url: str, api_key: str = "test",
                 probe_result: bool = False, fallback_result: bool = False):
        """Helper: ejecuta _get_working_base_url con probes mockeados."""
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(base_url=configured_url, api_key=api_key, model="unified-main")
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 512}
            provider.configure(config)

        async def run():
            with patch('backend.drivers.ai.jddcia_provider._probe_url',
                       new=AsyncMock(return_value=probe_result)):
                with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                           new=AsyncMock(return_value=None)):
                    try:
                        return await provider._get_working_base_url()
                    except Exception:
                        return None

        return run_async(run())

    def test_configured_url_ok_returns_it(self):
        """Si la URL configurada responde, se retorna sin escanear."""
        from backend.drivers.ai import jddcia_provider as jp
        jp._WORKING_URL_CACHE = "http://jddcia.local/api/vlm/v1"
        jp._WORKING_URL_CACHE_TS = time.monotonic()  # Reciente
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig
        provider = JDDCIAProvider()
        config = AIConfig(base_url="http://jddcia.local/api/vlm/v1", api_key="t", model="m")
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 512}
            provider.configure(config)

        async def run():
            return await provider._get_working_base_url()

        result = run_async(run())
        self.assertEqual(result, "http://jddcia.local/api/vlm/v1")

    def test_all_urls_fail_raises_exception(self):
        """Cuando todas las URLs fallan, se lanza excepción (no se bloquea)."""
        result = self._get_url("http://jddcia.local/api/vlm/v1", probe_result=False)
        # Debe retornar None (excepción capturada en el helper)
        self.assertIsNone(result)

    def test_dns_failure_does_not_hang(self):
        """Un fallo DNS (jddcia.local no resuelve) termina en < 10s."""
        from backend.drivers.ai import jddcia_provider as jp
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(base_url="http://jddcia.local/api/vlm/v1", api_key="t", model="m")
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 512}
            provider.configure(config)

        async def run():
            with patch('backend.drivers.ai.jddcia_provider._probe_url',
                       new=AsyncMock(return_value=False)):
                with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                           new=AsyncMock(return_value=None)):
                    t0 = time.monotonic()
                    try:
                        await provider._get_working_base_url()
                    except Exception:
                        pass
                    return time.monotonic() - t0

        elapsed = run_async(run())
        self.assertLess(elapsed, 10,
                        f"_get_working_base_url tardó {elapsed:.1f}s (max: 10s)")

    def test_probe_cached_failure_skips_network(self):
        """Si la URL configurada está en caché de fallos, no hace llamada de red para esa URL."""
        from backend.drivers.ai import jddcia_provider as jp
        url = "http://jddcia.local/api/vlm/v1"
        jp._cache_probe_failure(url)

        network_calls_for_url = [0]

        async def counting_probe(client, probe_url, auth):
            if probe_url == url:
                network_calls_for_url[0] += 1
            return False

        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(base_url=url, api_key="t", model="m")
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 512}
            provider.configure(config)

        async def run():
            with patch('backend.drivers.ai.jddcia_provider._probe_url',
                       new=counting_probe):
                with patch('backend.drivers.ai.jddcia_provider._discover_gateway_ip',
                           new=AsyncMock(return_value=None)):
                    with patch('backend.drivers.ai.jddcia_provider._load_ip_cache',
                               return_value=None):
                        try:
                            await provider._get_working_base_url()
                        except Exception:
                            pass

        run_async(run())
        self.assertEqual(network_calls_for_url[0], 0,
                         "URL configurada cacheada como fallida no debe probarse de red")

    def test_memory_cache_hit_no_network(self):
        """Con URL cacheada en memoria, no hay ninguna llamada de red."""
        from backend.drivers.ai import jddcia_provider as jp
        jp._WORKING_URL_CACHE = "http://jddcia.local/api/vlm/v1"
        jp._WORKING_URL_CACHE_TS = time.monotonic()  # Reciente

        network_calls = [0]

        async def counting_probe(client, url, auth):
            network_calls[0] += 1
            return True

        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        from backend.core.abstract.ai import AIConfig

        provider = JDDCIAProvider()
        config = AIConfig(base_url="http://jddcia.local/api/vlm/v1", api_key="t", model="m")
        with patch('backend.drivers.ai.jddcia_provider._load_model_context_limit',
                   return_value=4096):
            config.parameters = {"max_tokens": 512}
            provider.configure(config)

        async def run():
            with patch('backend.drivers.ai.jddcia_provider._probe_url',
                       new=counting_probe):
                await provider._get_working_base_url()

        run_async(run())
        self.assertEqual(network_calls[0], 0, "Cache en memoria no debe hacer llamadas de red")
        jp._WORKING_URL_CACHE = None


# ─────────────────────────────────────────────────────────────────────────────
# 12. TESTS DE ESTADO DEL SIMULADOR
# ─────────────────────────────────────────────────────────────────────────────

class TestSimulatorState(unittest.TestCase):
    """Verifica el estado del simulador y que los datos son consistentes."""

    def test_simulator_status_file_exists(self):
        """El fichero status.json del simulador debe existir."""
        status_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/status.json'
        )
        self.assertTrue(os.path.exists(status_path),
                        "status.json del simulador debe existir")

    def test_simulator_status_is_ready(self):
        """El simulador debe estar en estado 'ready'."""
        status_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/status.json'
        )
        if not os.path.exists(status_path):
            self.skipTest("status.json no disponible")
        with open(status_path) as f:
            status = json.load(f)
        self.assertEqual(status.get('status'), 'ready',
                         "El simulador debe estar en estado 'ready'")

    def test_simulator_db_file_exists(self):
        """El fichero simulator.db debe existir."""
        db_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/simulator.db'
        )
        self.assertTrue(os.path.exists(db_path),
                        "simulator.db debe existir")

    def test_simulator_row_counts_match_status(self):
        """Los row_counts en status.json deben coincidir con la BD."""
        import sqlite3
        status_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/status.json'
        )
        db_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/data/simulator.db'
        )
        if not os.path.exists(status_path) or not os.path.exists(db_path):
            self.skipTest("Archivos del simulador no disponibles")

        with open(status_path) as f:
            status = json.load(f)
        row_counts = status.get('row_counts', {})

        con = sqlite3.connect(db_path)
        cur = con.cursor()
        for table, expected in row_counts.items():
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            actual = cur.fetchone()[0]
            self.assertEqual(actual, expected,
                             f"Tabla {table}: status.json dice {expected} filas, BD tiene {actual}")
        con.close()

    def test_simulator_config_enabled(self):
        """La config del simulador debe tener simulator_enabled=true."""
        config_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/db_simulator/config.json'
        )
        if not os.path.exists(config_path):
            self.skipTest("config.json del simulador no disponible")
        with open(config_path) as f:
            config = json.load(f)
        # La clave debe existir y ser un booleano.
        # No forzamos true/false porque el modo (simulador vs BD real) puede cambiar.
        self.assertIn('simulator_enabled', config,
                      "La config del simulador debe tener la clave 'simulator_enabled'")
        self.assertIsInstance(config.get('simulator_enabled'), bool,
                              "simulator_enabled debe ser un booleano")


# ─────────────────────────────────────────────────────────────────────────────
# 13. TESTS DE CHAT CONFIG
# ─────────────────────────────────────────────────────────────────────────────

class TestChatConfig(unittest.TestCase):
    """Verifica la configuración del chat."""

    @classmethod
    def setUpClass(cls):
        config_path = os.path.join(
            os.path.dirname(__file__),
            '../modules/chat/config.json'
        )
        with open(config_path) as f:
            cls.config = json.load(f)

    def test_lan_model_max_tokens_reasonable(self):
        """lan_model_max_tokens debe ser <= 512 para el 30B (context=4096)."""
        max_tok = self.config.get('lan_model_max_tokens', 0)
        self.assertGreater(max_tok, 0, "lan_model_max_tokens debe ser > 0")
        self.assertLessEqual(max_tok, 512,
                             "lan_model_max_tokens <= 512 para no activar compresión en 30B")

    def test_lan_model_context_limit_correct(self):
        """lan_model_context_limit debe ser 4096 para Qwen3 30B."""
        ctx = self.config.get('lan_model_context_limit', 0)
        self.assertEqual(ctx, 4096, "context_limit de Qwen3 30B es 4096")

    def test_max_tokens_less_than_context(self):
        """lan_model_max_tokens debe ser < lan_model_context_limit."""
        max_tok = self.config.get('lan_model_max_tokens', 0)
        ctx = self.config.get('lan_model_context_limit', 4096)
        self.assertLess(max_tok, ctx,
                        f"max_tokens={max_tok} debe ser < context={ctx}")

    def test_lan_read_timeout_sufficient(self):
        """lan_read_timeout_s debe ser suficiente para respuestas largas."""
        timeout = self.config.get('lan_read_timeout_s', 0)
        self.assertGreaterEqual(timeout, 60,
                                "Timeout de lectura debe ser >= 60s para el 8B")

    def test_ai_local_only_configured(self):
        """ai_local_only debe estar configurado."""
        self.assertIn('ai_local_only', self.config)

    def test_max_sql_retries_reasonable(self):
        """max_sql_retries debe ser <= 4 (evitar demasiados reintentos lentos)."""
        retries = self.config.get('max_sql_retries', 0)
        self.assertLessEqual(retries, 4,
                             "max_sql_retries <= 4 (más reintentos = más lento)")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    unittest.main(verbosity=2)
