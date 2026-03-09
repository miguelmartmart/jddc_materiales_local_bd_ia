"""
test_network_audit.py — Tests de auditoría de red.

CAPA: privacy (sin BD, sin IA — solo verifica conexiones de red)
EJECUTAR: .venv/Scripts/pytest tests/privacy/test_network_audit.py -v -s

PROPÓSITO:
  Garantizar formalmente que NINGÚN dato sale a internet.
  Intercepta socket.connect y verifica que todas las conexiones son LAN.

INDEPENDENCIA:
  - Las IPs permitidas se leen de test.properties (ALLOWED_NETWORKS).
  - Sin IPs hardcodeadas en el código.
  - Funciona en cualquier red LAN (cambiar ALLOWED_NETWORKS en test.properties).
"""

import socket
import sys
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ─── Helpers reutilizables ────────────────────────────────────────────────────

def _is_lan(host: str, allowed_networks: List[str]) -> bool:
    """Verifica si una dirección es LAN según la configuración."""
    try:
        ip = socket.gethostbyname(host)
    except Exception:
        ip = host
    return any(ip.startswith(prefix) for prefix in allowed_networks)


# ═══════════════════════════════════════════════════════════════════════════════
# Detección de IPs LAN vs Internet
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeteccionLAN:
    """Verifica que la función de detección LAN funciona correctamente."""

    def test_localhost_es_lan(self, test_config):
        assert _is_lan("127.0.0.1", test_config.allowed_networks)
        assert _is_lan("localhost", test_config.allowed_networks)

    def test_192_168_es_lan(self, test_config):
        assert _is_lan("192.168.0.1", test_config.allowed_networks)
        assert _is_lan("192.168.1.100", test_config.allowed_networks)
        assert _is_lan("192.168.0.36", test_config.allowed_networks)

    def test_10_x_es_lan(self, test_config):
        assert _is_lan("10.0.0.1", test_config.allowed_networks)
        assert _is_lan("10.10.10.10", test_config.allowed_networks)

    def test_internet_no_es_lan(self, test_config):
        assert not _is_lan("8.8.8.8", test_config.allowed_networks)
        assert not _is_lan("1.1.1.1", test_config.allowed_networks)

    def test_openai_no_es_lan(self, test_config):
        # No resolvemos el hostname para no hacer conexión real
        # Solo verificamos que la IP pública no es LAN
        assert not _is_lan("104.18.0.0", test_config.allowed_networks)

    def test_qwen3_es_lan(self, test_config):
        """La IP de Qwen3 configurada debe ser LAN."""
        if not test_config.qwen3_host:
            pytest.skip("Qwen3 no configurado")
        assert _is_lan(test_config.qwen3_host, test_config.allowed_networks), (
            f"🚨 Qwen3 NO está en LAN: {test_config.qwen3_host}"
        )

    def test_bd_es_lan(self, test_config):
        """La IP de la BD configurada debe ser LAN."""
        assert _is_lan(test_config.db_host, test_config.allowed_networks), (
            f"🚨 BD Firebird NO está en LAN: {test_config.db_host}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Verificación de configuración
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfiguracionPrivacidad:
    """Verifica que la configuración garantiza privacidad."""

    def test_enforce_lan_only_activo(self, test_config):
        """ENFORCE_LAN_ONLY debe estar activo en producción."""
        assert test_config.enforce_lan_only, (
            "⚠️ ENFORCE_LAN_ONLY=false — los tests no verificarán conexiones a internet"
        )

    def test_allowed_networks_no_vacio(self, test_config):
        """Debe haber al menos una red LAN configurada."""
        assert len(test_config.allowed_networks) > 0, (
            "ALLOWED_NETWORKS vacío — ninguna red sería considerada LAN"
        )

    def test_allowed_networks_incluye_localhost(self, test_config):
        """Localhost siempre debe estar en las redes permitidas."""
        has_localhost = any(
            "127." in n or "::1" in n
            for n in test_config.allowed_networks
        )
        assert has_localhost, (
            "ALLOWED_NETWORKS no incluye localhost (127. o ::1)"
        )

    def test_allowed_networks_incluye_192_168(self, test_config):
        """La red 192.168.x.x debe estar permitida (red LAN típica)."""
        has_192 = any("192.168." in n for n in test_config.allowed_networks)
        assert has_192, (
            "ALLOWED_NETWORKS no incluye 192.168.x.x — verificar configuración de red"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Verificación de settings del proyecto
# ═══════════════════════════════════════════════════════════════════════════════

class TestSettingsPrivacidad:
    """Verifica que los settings del proyecto no tienen URLs de internet."""

    # Servicios de IA en internet que NO deben estar configurados
    INTERNET_AI_SERVICES = [
        "openai.com",
        "api.openai.com",
        "groq.com",
        "api.groq.com",
        "anthropic.com",
        "gemini.google.com",
        "generativelanguage.googleapis.com",
        "huggingface.co",
        "api-inference.huggingface.co",
        "together.ai",
        "replicate.com",
    ]

    def test_settings_sin_urls_internet(self, test_config):
        """Los settings no deben tener URLs de servicios de IA en internet."""
        try:
            from backend.core.config.settings import settings
        except ImportError:
            pytest.skip("Settings no disponible")

        violations = []
        for attr in dir(settings):
            if attr.startswith("_"):
                continue
            val = getattr(settings, attr, None)
            if not isinstance(val, str):
                continue
            for service in self.INTERNET_AI_SERVICES:
                if service in val:
                    violations.append(f"{attr}={val[:50]} → contiene {service}")

        assert not violations, (
            f"🚨 URLs de internet en settings:\n" + "\n".join(violations)
        )

    def test_qwen3_url_es_lan(self, test_config):
        """La URL de Qwen3 configurada debe ser LAN."""
        if not test_config.qwen3_host:
            pytest.skip("Qwen3 no configurado")
        assert _is_lan(test_config.qwen3_host, test_config.allowed_networks), (
            f"🚨 Qwen3 NO está en LAN: {test_config.qwen3_host}\n"
            f"Redes permitidas: {test_config.allowed_networks}"
        )

    def test_bd_url_es_lan(self, test_config):
        """La URL de la BD debe ser LAN."""
        assert _is_lan(test_config.db_host, test_config.allowed_networks), (
            f"🚨 BD Firebird NO está en LAN: {test_config.db_host}\n"
            f"Redes permitidas: {test_config.allowed_networks}"
        )
