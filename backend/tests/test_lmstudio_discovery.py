"""
test_lmstudio_discovery.py — Tests del módulo de autodescubrimiento de LM Studio

Cubre:
  - Cache en memoria (TTL, invalidación)
  - Cache en disco (lectura, escritura, expiración)
  - _probe_ip: respuesta 200 → URL válida, otros códigos → None
  - discover_lmstudio: orden de prioridad (config JSON > Hyper-V > subredes)
  - get_lmstudio_base_url: fallback a autodescubrimiento cuando la URL configurada falla
  - _get_known_ips_from_config: lectura correcta del JSON

Principios DEVIA:
  - Tests simulan el flujo real (no mocks de alto nivel)
  - Cada test tiene una sola responsabilidad
  - Sin datos reales de red — todo mockeado con respuestas HTTP simuladas
"""

import asyncio
import json
import os
import time
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_memory_cache():
    """Resetea la cache en memoria antes de cada test."""
    import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
    disc._memory_cache_url = None
    disc._memory_cache_ts = 0.0
    yield
    disc._memory_cache_url = None
    disc._memory_cache_ts = 0.0


@pytest.fixture
def tmp_cache_file(tmp_path):
    """Archivo de cache temporal para tests de disco."""
    return str(tmp_path / ".lmstudio_ip_cache.json")


# ── Tests de cache en memoria ─────────────────────────────────────────────────

class TestMemoryCache:

    def test_cache_vacia_devuelve_none(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import _get_memory_cache
        assert _get_memory_cache() is None

    def test_cache_guardada_se_recupera(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import (
            _get_memory_cache, _set_memory_cache
        )
        _set_memory_cache("http://192.168.56.1:1234/v1")
        assert _get_memory_cache() == "http://192.168.56.1:1234/v1"

    def test_cache_expirada_devuelve_none(self):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        disc._memory_cache_url = "http://192.168.56.1:1234/v1"
        disc._memory_cache_ts = time.time() - 400  # 400s > TTL de 300s
        assert disc._get_memory_cache() is None

    def test_invalidate_cache_limpia_memoria(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import (
            _set_memory_cache, invalidate_cache, _get_memory_cache
        )
        _set_memory_cache("http://192.168.56.1:1234/v1")
        invalidate_cache()
        assert _get_memory_cache() is None


# ── Tests de cache en disco ───────────────────────────────────────────────────

class TestDiskCache:

    def test_cache_disco_guardado_y_leido(self, tmp_cache_file):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc.DISK_CACHE_FILE
        disc.DISK_CACHE_FILE = tmp_cache_file
        try:
            disc._save_disk_cache("http://172.19.64.1:1234/v1")
            result = disc._load_disk_cache()
            assert result == "http://172.19.64.1:1234/v1"
        finally:
            disc.DISK_CACHE_FILE = original

    def test_cache_disco_expirado_devuelve_none(self, tmp_cache_file):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc.DISK_CACHE_FILE
        disc.DISK_CACHE_FILE = tmp_cache_file
        try:
            # Guardar con timestamp antiguo (25 horas)
            with open(tmp_cache_file, "w") as f:
                json.dump({
                    "url": "http://172.19.64.1:1234/v1",
                    "saved_at": time.time() - 90000  # 25 horas
                }, f)
            result = disc._load_disk_cache()
            assert result is None
        finally:
            disc.DISK_CACHE_FILE = original

    def test_cache_disco_archivo_inexistente_devuelve_none(self, tmp_cache_file):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc.DISK_CACHE_FILE
        disc.DISK_CACHE_FILE = "/ruta/que/no/existe/.cache.json"
        try:
            result = disc._load_disk_cache()
            assert result is None
        finally:
            disc.DISK_CACHE_FILE = original

    def test_cache_disco_json_corrupto_devuelve_none(self, tmp_cache_file):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc.DISK_CACHE_FILE
        disc.DISK_CACHE_FILE = tmp_cache_file
        try:
            with open(tmp_cache_file, "w") as f:
                f.write("esto no es json {{{")
            result = disc._load_disk_cache()
            assert result is None
        finally:
            disc.DISK_CACHE_FILE = original


# ── Tests de _probe_ip ────────────────────────────────────────────────────────

class TestProbeIp:

    @pytest.mark.asyncio
    async def test_probe_200_devuelve_base_url(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import _probe_ip

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _probe_ip("192.168.56.1", 1234)

        assert result == "http://192.168.56.1:1234/v1"

    @pytest.mark.asyncio
    async def test_probe_404_devuelve_none(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import _probe_ip

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _probe_ip("192.168.56.1", 1234)

        assert result is None

    @pytest.mark.asyncio
    async def test_probe_connection_error_devuelve_none(self):
        import httpx
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import _probe_ip

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _probe_ip("10.0.0.1", 1234)

        assert result is None

    @pytest.mark.asyncio
    async def test_probe_timeout_devuelve_none(self):
        import httpx
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import _probe_ip

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectTimeout("Timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await _probe_ip("172.19.64.1", 1234)

        assert result is None


# ── Tests de _get_known_ips_from_config ───────────────────────────────────────

class TestGetKnownIpsFromConfig:

    def test_lee_known_ips_del_json(self, tmp_path):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc._MODELS_JSON_PATH

        config = {
            "models": [
                {
                    "id": "jddcia-qwen3-8b-ip",
                    "known_ips": ["192.168.56.1:1234", "172.19.64.1:1234"]
                }
            ]
        }
        config_file = tmp_path / "jddcia_models.json"
        config_file.write_text(json.dumps(config))

        disc._MODELS_JSON_PATH = str(config_file)
        try:
            ips = disc._get_known_ips_from_config()
            assert "192.168.56.1" in ips
            assert "172.19.64.1" in ips
            assert len(ips) == 2
        finally:
            disc._MODELS_JSON_PATH = original

    def test_json_sin_known_ips_devuelve_lista_vacia(self, tmp_path):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc._MODELS_JSON_PATH

        config = {"models": [{"id": "jddcia-qwen3-30b"}]}
        config_file = tmp_path / "jddcia_models.json"
        config_file.write_text(json.dumps(config))

        disc._MODELS_JSON_PATH = str(config_file)
        try:
            ips = disc._get_known_ips_from_config()
            assert ips == []
        finally:
            disc._MODELS_JSON_PATH = original

    def test_archivo_inexistente_devuelve_lista_vacia(self):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc._MODELS_JSON_PATH
        disc._MODELS_JSON_PATH = "/ruta/inexistente/models.json"
        try:
            ips = disc._get_known_ips_from_config()
            assert ips == []
        finally:
            disc._MODELS_JSON_PATH = original

    def test_deduplica_ips_repetidas(self, tmp_path):
        import bots.interjddcia.backend.drivers.ai.lmstudio_discovery as disc
        original = disc._MODELS_JSON_PATH

        config = {
            "models": [
                {"id": "model-a", "known_ips": ["192.168.56.1:1234"]},
                {"id": "model-b", "known_ips": ["192.168.56.1:1234", "172.19.64.1:1234"]},
            ]
        }
        config_file = tmp_path / "jddcia_models.json"
        config_file.write_text(json.dumps(config))

        disc._MODELS_JSON_PATH = str(config_file)
        try:
            ips = disc._get_known_ips_from_config()
            assert ips.count("192.168.56.1") == 1  # No duplicados
        finally:
            disc._MODELS_JSON_PATH = original


# ── Tests de discover_lmstudio ────────────────────────────────────────────────

class TestDiscoverLmstudio:

    @pytest.mark.asyncio
    async def test_usa_cache_memoria_si_disponible(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import (
            _set_memory_cache, discover_lmstudio
        )
        _set_memory_cache("http://192.168.56.1:1234/v1")

        # No debería llamar a _probe_ip si hay cache
        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip") as mock_probe:
            result = await discover_lmstudio(force=False)

        assert result == "http://192.168.56.1:1234/v1"
        mock_probe.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_ignora_cache_memoria(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import (
            _set_memory_cache, discover_lmstudio
        )
        _set_memory_cache("http://192.168.56.1:1234/v1")

        # Con force=True, debe re-escanear aunque haya cache
        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   new_callable=AsyncMock, return_value=None) as mock_probe:
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=[]):
                result = await discover_lmstudio(force=True)

        assert mock_probe.called  # Sí llamó a _probe_ip

    @pytest.mark.asyncio
    async def test_encuentra_ip_en_config_json(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import discover_lmstudio

        async def mock_probe(ip, port=1234):
            if ip == "192.168.56.1":
                return f"http://{ip}:{port}/v1"
            return None

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   side_effect=mock_probe):
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=["192.168.56.1"]):
                with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._load_disk_cache",
                           return_value=None):
                    with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._save_disk_cache"):
                        result = await discover_lmstudio(force=True)

        assert result == "http://192.168.56.1:1234/v1"

    @pytest.mark.asyncio
    async def test_devuelve_none_si_no_encuentra_nada(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import discover_lmstudio

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   new_callable=AsyncMock, return_value=None):
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=[]):
                with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._load_disk_cache",
                           return_value=None):
                    with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_subnets_from_interfaces",
                               return_value=[]):
                        result = await discover_lmstudio(force=True)

        assert result is None

    @pytest.mark.asyncio
    async def test_guarda_en_cache_cuando_encuentra(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import (
            discover_lmstudio, _get_memory_cache
        )

        async def mock_probe(ip, port=1234):
            if ip == "192.168.56.1":
                return f"http://{ip}:{port}/v1"
            return None

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   side_effect=mock_probe):
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=["192.168.56.1"]):
                with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._load_disk_cache",
                           return_value=None):
                    with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._save_disk_cache"):
                        await discover_lmstudio(force=True)

        # Debe haber guardado en cache de memoria
        assert _get_memory_cache() == "http://192.168.56.1:1234/v1"


# ── Tests de get_lmstudio_base_url ────────────────────────────────────────────

class TestGetLmstudioBaseUrl:

    @pytest.mark.asyncio
    async def test_url_configurada_funciona_la_usa(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import get_lmstudio_base_url

        async def mock_probe(ip, port=1234):
            if ip == "192.168.56.1":
                return f"http://{ip}:{port}/v1"
            return None

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   side_effect=mock_probe):
            result = await get_lmstudio_base_url("http://192.168.56.1:1234/v1")

        assert result == "http://192.168.56.1:1234/v1"

    @pytest.mark.asyncio
    async def test_url_configurada_falla_autodescubre(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import get_lmstudio_base_url

        async def mock_probe(ip, port=1234):
            # La URL configurada (172.19.64.1) falla, pero 192.168.56.1 funciona
            if ip == "192.168.56.1":
                return f"http://{ip}:{port}/v1"
            return None

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   side_effect=mock_probe):
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=["192.168.56.1"]):
                with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._load_disk_cache",
                           return_value=None):
                    with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._save_disk_cache"):
                        result = await get_lmstudio_base_url("http://172.19.64.1:1234/v1")

        assert result == "http://192.168.56.1:1234/v1"

    @pytest.mark.asyncio
    async def test_sin_url_configurada_autodescubre(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import get_lmstudio_base_url

        async def mock_probe(ip, port=1234):
            if ip == "192.168.56.1":
                return f"http://{ip}:{port}/v1"
            return None

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   side_effect=mock_probe):
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=["192.168.56.1"]):
                with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._load_disk_cache",
                           return_value=None):
                    with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._save_disk_cache"):
                        result = await get_lmstudio_base_url(None)

        assert result == "http://192.168.56.1:1234/v1"

    @pytest.mark.asyncio
    async def test_fallback_a_url_configurada_si_no_encuentra_nada(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import get_lmstudio_base_url

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   new_callable=AsyncMock, return_value=None):
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=[]):
                with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._load_disk_cache",
                           return_value=None):
                    with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_subnets_from_interfaces",
                               return_value=[]):
                        result = await get_lmstudio_base_url("http://172.19.64.1:1234/v1")

        # Último recurso: devuelve la URL configurada aunque no responda
        assert result == "http://172.19.64.1:1234/v1"

    @pytest.mark.asyncio
    async def test_devuelve_none_si_no_hay_url_ni_descubrimiento(self):
        from bots.interjddcia.backend.drivers.ai.lmstudio_discovery import get_lmstudio_base_url

        with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._probe_ip",
                   new_callable=AsyncMock, return_value=None):
            with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_known_ips_from_config",
                       return_value=[]):
                with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._load_disk_cache",
                           return_value=None):
                    with patch("bots.interjddcia.backend.drivers.ai.lmstudio_discovery._get_subnets_from_interfaces",
                               return_value=[]):
                        result = await get_lmstudio_base_url(None)

        assert result is None
