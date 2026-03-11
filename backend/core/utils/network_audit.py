"""
network_audit.py — Auditoría de red: intercepta y registra TODAS las conexiones HTTP.

PROPÓSITO:
  Garantizar que NINGÚN dato de la BD Firebird sale a internet.
  Solo se permiten conexiones a la red LAN local (RFC 1918: 192.168.x.x, 10.x.x.x, etc.).

RESILIENCIA:
  - La clasificación LAN/INTERNET se basa en rangos RFC 1918, NO en IPs concretas.
  - Si cambia la IP del servidor Qwen3 o del PC, el sistema sigue funcionando.
  - Los hostnames LAN se detectan por sufijo .local (mDNS) — sin IPs hardcodeadas.
  - Las URLs del gateway vienen de settings.py / .env (JDDCIA_BASE_URL_FALLBACK).

CONFIGURACIÓN:
  Todas las constantes están en network_audit_constants.py.
  Las URLs/IPs del gateway vienen de settings.py / .env.
  Este fichero NO contiene ninguna IP, hostname ni puerto hardcodeado.

USO EN TESTS:
  from backend.core.utils.network_audit import NetworkAuditLogger
  with NetworkAuditLogger(strict=True) as audit:
      await mi_funcion()
      audit.assert_no_internet_calls()

USO EN PRODUCCIÓN:
  NetworkAuditLogger.install_global()  # En main.py al arrancar

FICHERO DE LOG:
  logs/network_audit.log  (ruta definida en NetworkAuditPaths)

DEPENDENCIAS:
  - network_audit_constants.py: constantes de configuración
  - settings.py: URLs del gateway LAN (JDDCIA_BASE_URL_FALLBACK)
  - Sin dependencias de módulos de negocio (core/utils/ es la capa más baja)
"""

import ipaddress
import json
import logging
import re
import socket
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from unittest.mock import patch

from backend.core.utils.network_audit_constants import (
    LanHostnames,
    NetworkAuditConfig,
    NetworkAuditMessages,
    NetworkAuditPaths,
    PrivateNetworkRanges,
)

# ─── Logger de auditoría ──────────────────────────────────────────────────────

def _build_audit_logger() -> logging.Logger:
    """Construye el logger dedicado para auditoría de red."""
    NetworkAuditPaths.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(NetworkAuditConfig.LOGGER_NAME)
    if not log.handlers:
        log.setLevel(logging.DEBUG)
        fh = logging.FileHandler(NetworkAuditPaths.LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            NetworkAuditConfig.LOG_FORMAT_FILE,
            datefmt=NetworkAuditConfig.LOG_DATE_FORMAT,
        ))
        log.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(NetworkAuditConfig.LOG_FORMAT_CONSOLE))
        log.addHandler(ch)
    return log


_audit_log = _build_audit_logger()

# ─── Redes privadas precalculadas ─────────────────────────────────────────────

_PRIVATE_NETS = [
    ipaddress.ip_network(cidr)
    for cidr in PrivateNetworkRanges.CIDR_BLOCKS
    if ":" not in cidr  # IPv4 only para ip_network sin flag
]
_PRIVATE_NETS_V6 = [
    ipaddress.ip_network(cidr)
    for cidr in PrivateNetworkRanges.CIDR_BLOCKS
    if ":" in cidr  # IPv6
]


# ─── Clasificación de hosts ───────────────────────────────────────────────────

def _is_lan_host(host: str) -> bool:
    """
    Determina si un host pertenece a la red LAN local.

    Orden de comprobación:
    1. Hostname explícito conocido (localhost, jddcia.local, etc.)
    2. Sufijo .local / .lan / .home / .internal (mDNS)
    3. IP privada RFC 1918 (sin resolver DNS)
    4. Resolución DNS → IP privada RFC 1918

    RESILIENCIA: No depende de IPs concretas. Funciona aunque cambie
    la IP del servidor Qwen3 o del PC.
    """
    if not host:
        return False

    host_lower = host.lower()

    # 1. Hostnames explícitos conocidos
    if host_lower in LanHostnames.EXPLICIT_HOSTS:
        return True

    # 2. Sufijos de red local (mDNS / Bonjour / Avahi)
    if any(host_lower.endswith(sfx) for sfx in LanHostnames.LOCAL_SUFFIXES):
        return True

    # 3. Intentar parsear como IP directamente
    try:
        ip = ipaddress.ip_address(host)
        if ip.version == 4:
            return any(ip in net for net in _PRIVATE_NETS)
        return any(ip in net for net in _PRIVATE_NETS_V6)
    except ValueError:
        pass

    # 4. Resolver hostname a IP (con timeout implícito del SO)
    try:
        resolved = socket.gethostbyname(host)
        ip = ipaddress.ip_address(resolved)
        return any(ip in net for net in _PRIVATE_NETS)
    except Exception:
        pass

    return False


def _classify_url(url: str) -> Dict[str, Any]:
    """
    Clasifica una URL como LAN o INTERNET.

    Returns:
        Dict con: url, host, is_lan, is_internet, destination_type
    """
    host = ""
    try:
        m = re.match(r"https?://([^/:?#]+)", url)
        if m:
            host = m.group(1)
    except Exception:
        pass

    is_lan = _is_lan_host(host)
    return {
        "url":              url,
        "host":             host,
        "is_lan":           is_lan,
        "is_internet":      not is_lan,
        "destination_type": "LAN" if is_lan else "INTERNET",
    }


# ─── Registro de una llamada HTTP ─────────────────────────────────────────────

class NetworkCall:
    """Registro inmutable de una llamada HTTP interceptada."""

    __slots__ = (
        "timestamp", "method", "url", "caller",
        "host", "is_lan", "is_internet", "destination_type",
    )

    def __init__(self, method: str, url: str, caller: str = "unknown") -> None:
        self.timestamp = datetime.now().isoformat()
        self.method    = method.upper()
        self.url       = url
        self.caller    = caller
        c = _classify_url(url)
        self.host             = c["host"]
        self.is_lan           = c["is_lan"]
        self.is_internet      = c["is_internet"]
        self.destination_type = c["destination_type"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp":        self.timestamp,
            "method":           self.method,
            "url":              self.url,
            "host":             self.host,
            "destination_type": self.destination_type,
            "is_lan":           self.is_lan,
            "is_internet":      self.is_internet,
            "caller":           self.caller,
        }

    def __repr__(self) -> str:
        icon = "🏠" if self.is_lan else "🌐❌"
        return f"{icon} [{self.destination_type}] {self.method} {self.url} (caller={self.caller})"


# ─── NetworkAuditLogger ───────────────────────────────────────────────────────

class NetworkAuditLogger:
    """
    Intercepta y audita TODAS las conexiones HTTP salientes.

    Parchea httpx.AsyncClient, httpx.Client, urllib.request y requests
    para registrar cada petición HTTP con su clasificación LAN/INTERNET.

    Uso como context manager (tests):
        with NetworkAuditLogger(strict=True) as audit:
            await mi_funcion()
            audit.assert_no_internet_calls()

    Uso global (producción — llamar en main.py):
        NetworkAuditLogger.install_global()
    """

    _global_instance: Optional["NetworkAuditLogger"] = None
    _global_lock = threading.Lock()

    def __init__(
        self,
        strict: bool = NetworkAuditConfig.DEFAULT_STRICT_MODE,
        log_to_file: bool = True,
    ) -> None:
        self.strict      = strict
        self.log_to_file = log_to_file
        self.calls: List[NetworkCall] = []
        self._lock    = threading.Lock()
        self._patches: List[Any] = []

    # ── Registro ──────────────────────────────────────────────────────────────

    def _record_call(self, method: str, url: str, caller: str = "unknown") -> NetworkCall:
        """Registra una llamada HTTP, la clasifica y la persiste en el log."""
        call = NetworkCall(method=method, url=url, caller=caller)

        with self._lock:
            self.calls.append(call)

        level = logging.WARNING if call.is_internet else logging.INFO
        _audit_log.log(level, str(call))

        if self.log_to_file:
            self._append_to_log(call)

        if self.strict and call.is_internet:
            msg = NetworkAuditMessages.PRIVACY_VIOLATION.format(
                url=call.url,
                host=call.host,
                caller=call.caller,
                timestamp=call.timestamp,
            )
            _audit_log.critical(msg)
            raise PrivacyViolationError(msg)

        return call

    def _append_to_log(self, call: NetworkCall) -> None:
        """Añade la llamada al fichero de log en formato JSON Lines."""
        try:
            NetworkAuditPaths.LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(NetworkAuditPaths.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(call.to_dict(), ensure_ascii=False) + "\n")
        except Exception as exc:
            _audit_log.warning(f"No se pudo escribir en log de auditoría: {exc}")

    # ── Instalación de parches ────────────────────────────────────────────────

    def _install_patches(self) -> None:
        """Parchea httpx, urllib y requests para interceptar todas las peticiones."""
        self._patch_httpx_async()
        self._patch_httpx_sync()
        self._patch_urllib()
        self._patch_requests()

    def _patch_httpx_async(self) -> None:
        """Parchea httpx.AsyncClient.send."""
        try:
            import httpx
            original = httpx.AsyncClient.send
            auditor  = self

            async def _patched(self_client, request, *args, **kwargs):
                auditor._record_call(request.method, str(request.url), "httpx.AsyncClient")
                return await original(self_client, request, *args, **kwargs)

            p = patch.object(httpx.AsyncClient, "send", _patched)
            p.start()
            self._patches.append(p)
            _audit_log.debug(NetworkAuditMessages.PATCH_INSTALLED.format(
                target="httpx.AsyncClient.send"
            ))
        except Exception as exc:
            _audit_log.warning(NetworkAuditMessages.PATCH_FAILED.format(
                target="httpx.AsyncClient", error=exc
            ))

    def _patch_httpx_sync(self) -> None:
        """Parchea httpx.Client.send (síncrono)."""
        try:
            import httpx
            original = httpx.Client.send
            auditor  = self

            def _patched(self_client, request, *args, **kwargs):
                auditor._record_call(request.method, str(request.url), "httpx.Client")
                return original(self_client, request, *args, **kwargs)

            p = patch.object(httpx.Client, "send", _patched)
            p.start()
            self._patches.append(p)
            _audit_log.debug(NetworkAuditMessages.PATCH_INSTALLED.format(
                target="httpx.Client.send"
            ))
        except Exception as exc:
            _audit_log.warning(NetworkAuditMessages.PATCH_FAILED.format(
                target="httpx.Client", error=exc
            ))

    def _patch_urllib(self) -> None:
        """Parchea urllib.request.urlopen."""
        try:
            import urllib.request
            original = urllib.request.urlopen
            auditor  = self

            def _patched(url_or_req, *args, **kwargs):
                url = (
                    url_or_req
                    if isinstance(url_or_req, str)
                    else getattr(url_or_req, "full_url", str(url_or_req))
                )
                auditor._record_call("GET", url, "urllib.request.urlopen")
                return original(url_or_req, *args, **kwargs)

            p = patch("urllib.request.urlopen", _patched)
            p.start()
            self._patches.append(p)
            _audit_log.debug(NetworkAuditMessages.PATCH_INSTALLED.format(
                target="urllib.request.urlopen"
            ))
        except Exception as exc:
            _audit_log.warning(NetworkAuditMessages.PATCH_FAILED.format(
                target="urllib.request", error=exc
            ))

    def _patch_requests(self) -> None:
        """Parchea requests.Session.send (si requests está instalado)."""
        try:
            import requests
            original = requests.Session.send
            auditor  = self

            def _patched(self_session, prepared, *args, **kwargs):
                auditor._record_call(
                    prepared.method or "GET",
                    prepared.url or "",
                    "requests.Session",
                )
                return original(self_session, prepared, *args, **kwargs)

            p = patch.object(requests.Session, "send", _patched)
            p.start()
            self._patches.append(p)
            _audit_log.debug(NetworkAuditMessages.PATCH_INSTALLED.format(
                target="requests.Session.send"
            ))
        except ImportError:
            pass  # requests no instalado — OK
        except Exception as exc:
            _audit_log.warning(NetworkAuditMessages.PATCH_FAILED.format(
                target="requests.Session", error=exc
            ))

    def _remove_patches(self) -> None:
        """Elimina todos los parches instalados."""
        for p in reversed(self._patches):
            try:
                p.stop()
            except Exception:
                pass
        self._patches.clear()

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "NetworkAuditLogger":
        self.calls.clear()
        self._install_patches()
        _audit_log.info(NetworkAuditMessages.AUDIT_STARTED.format(
            strict="SÍ" if self.strict else "NO"
        ))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._remove_patches()
        self._log_summary()
        _audit_log.info(NetworkAuditMessages.AUDIT_STOPPED)
        return False  # No suprimir excepciones

    # ── Instalación global (producción) ──────────────────────────────────────

    @classmethod
    def install_global(
        cls,
        strict: bool = NetworkAuditConfig.DEFAULT_STRICT_MODE,
    ) -> "NetworkAuditLogger":
        """
        Instala el auditor globalmente al arrancar el servidor.
        Todas las peticiones HTTP quedan registradas en logs/network_audit.log.
        """
        with cls._global_lock:
            if cls._global_instance is not None:
                _audit_log.warning(NetworkAuditMessages.ALREADY_INSTALLED)
                return cls._global_instance
            instance = cls(strict=strict, log_to_file=True)
            instance._install_patches()
            cls._global_instance = instance
            _audit_log.info(NetworkAuditMessages.GLOBAL_INSTALLED.format(
                strict="SÍ" if strict else "NO",
                log_file=NetworkAuditPaths.LOG_FILE,
            ))
            return instance

    @classmethod
    def uninstall_global(cls) -> None:
        """Desinstala el auditor global."""
        with cls._global_lock:
            if cls._global_instance:
                cls._global_instance._remove_patches()
                cls._global_instance = None
                _audit_log.info(NetworkAuditMessages.GLOBAL_REMOVED)

    @classmethod
    def get_global(cls) -> Optional["NetworkAuditLogger"]:
        """Devuelve la instancia global si existe."""
        return cls._global_instance

    # ── Propiedades de consulta ───────────────────────────────────────────────

    @property
    def internet_calls(self) -> List[NetworkCall]:
        return [c for c in self.calls if c.is_internet]

    @property
    def lan_calls(self) -> List[NetworkCall]:
        return [c for c in self.calls if c.is_lan]

    # ── Aserciones para tests ─────────────────────────────────────────────────

    def assert_no_internet_calls(self) -> None:
        """Lanza AssertionError si hubo alguna llamada a internet."""
        internet = self.internet_calls
        if internet:
            details = "\n".join(f"  • {c}" for c in internet)
            raise AssertionError(
                NetworkAuditMessages.ASSERT_INTERNET_CALLS.format(
                    count=len(internet), details=details
                )
            )

    def assert_all_calls_to_lan(self) -> None:
        """Lanza AssertionError si hay llamadas fuera de la LAN."""
        self.assert_no_internet_calls()
        non_lan = [c for c in self.calls if not c.is_lan]
        if non_lan:
            details = "\n".join(f"  • {c}" for c in non_lan)
            raise AssertionError(
                NetworkAuditMessages.ASSERT_NON_LAN_CALLS.format(
                    count=len(non_lan), details=details
                )
            )

    def assert_calls_only_to(self, allowed_hosts: Set[str]) -> None:
        """Lanza AssertionError si hay llamadas a hosts no permitidos."""
        violations = [c for c in self.calls if c.host not in allowed_hosts]
        if violations:
            details = "\n".join(f"  • {c}" for c in violations)
            raise AssertionError(
                NetworkAuditMessages.ASSERT_FORBIDDEN_HOST.format(
                    details=details, allowed=allowed_hosts
                )
            )

    # ── Resumen ───────────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Devuelve estadísticas de la auditoría."""
        return {
            "total_calls":     len(self.calls),
            "lan_calls":       len(self.lan_calls),
            "internet_calls":  len(self.internet_calls),
            "hosts_contacted": sorted({c.host for c in self.calls}),
            "internet_hosts":  sorted({c.host for c in self.internet_calls}),
            "lan_hosts":       sorted({c.host for c in self.lan_calls}),
            "calls":           [c.to_dict() for c in self.calls],
        }

    def _log_summary(self) -> None:
        """Escribe el resumen en el log."""
        s = self.get_summary()
        _audit_log.info(NetworkAuditMessages.SUMMARY.format(
            total=s["total_calls"],
            lan=s["lan_calls"],
            internet=s["internet_calls"],
            internet_icon="❌" if s["internet_calls"] else "✅",
        ))
        if s["internet_hosts"]:
            _audit_log.warning(NetworkAuditMessages.INTERNET_HOSTS.format(
                hosts=s["internet_hosts"]
            ))
        if s["lan_hosts"]:
            _audit_log.info(NetworkAuditMessages.LAN_HOSTS.format(
                hosts=s["lan_hosts"]
            ))


# ─── Excepción de violación de privacidad ────────────────────────────────────

class PrivacyViolationError(Exception):
    """
    Se lanza cuando se detecta un intento de enviar datos a internet
    en modo strict=True del NetworkAuditLogger.
    """
    pass
