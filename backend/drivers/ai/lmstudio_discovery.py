"""
lmstudio_discovery.py — Autodescubrimiento de LM Studio en la red local

Responsabilidad única: encontrar la IP donde LM Studio está escuchando,
independientemente de si la IP cambió (Hyper-V/WSL2 cambia IPs al reiniciar).

Estrategia de descubrimiento (en orden de prioridad):
  1. Cache en memoria (TTL 5 min) — evita re-escanear en cada petición
  2. Cache en disco (.lmstudio_ip_cache.json) — persiste entre reinicios del backend
  3. IPs conocidas del JSON de modelos (base_url de jddcia_models.json)
  4. Escaneo de todas las interfaces de red del PC (detecta Hyper-V, WSL2, WiFi, Ethernet)
  5. Escaneo de subredes comunes de Hyper-V/WSL2 (172.x.x.x, 192.168.x.x)

Principios DEVIA:
  - Fichero < 500 líneas, una responsabilidad (SRP)
  - Constantes centralizadas al inicio del fichero
  - Trazabilidad total: cada intento queda en el log con IP, puerto, latencia
  - Fallback gracioso: si no encuentra nada, devuelve None (no lanza excepción)
  - Autoaprendizaje: guarda la IP que funcionó para usarla primero la próxima vez

Autor: DEVIA System
Versión: 1.0.0
"""

import asyncio
import json
import logging
import os
import socket
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

# Puerto por defecto de LM Studio
LMSTUDIO_PORT = 1234

# Ruta del endpoint de health check (GET → 200 si LM Studio está activo)
LMSTUDIO_HEALTH_PATH = "/v1/models"

# Timeout de conexión para probar cada IP (segundos)
PROBE_CONNECT_TIMEOUT = 2.0

# Timeout de lectura para el health check (segundos)
PROBE_READ_TIMEOUT = 3.0

# TTL de la cache en memoria (segundos)
MEMORY_CACHE_TTL = 300.0  # 5 minutos

# Archivo de cache en disco (mismo directorio que este módulo)
DISK_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".lmstudio_ip_cache.json")

# IPs conocidas de Hyper-V/WSL2 (suelen ser estas, pero pueden cambiar)
# Se prueban antes del escaneo completo para ser más rápidos
# NOTA: 192.168.56.1 confirmada el 17/06/2026 como IP activa de LM Studio
KNOWN_HYPER_V_IPS = [
    "192.168.56.1",  # VirtualBox Host-Only / Hyper-V alternativo — CONFIRMADA 17/06/2026
    "172.19.64.1",   # Hyper-V Default Switch (más común)
    "172.20.64.1",
    "172.21.64.1",
    "172.22.64.1",
    "172.23.64.1",
    "172.24.64.1",
    "172.25.64.1",
    "172.26.64.1",
    "172.27.64.1",
    "172.28.64.1",
    "172.29.64.1",
    "172.30.64.1",
    "172.31.64.1",
    "192.168.99.1",  # Docker Toolbox legacy
    "10.0.0.1",      # Hyper-V Internal Switch
    "10.0.75.1",     # Docker for Windows legacy
]

# Path al jddcia_models.json para leer known_ips configuradas
_MODELS_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "../../core/config/models/jddcia_models.json"
)


def _get_known_ips_from_config() -> list[str]:
    """
    Lee las IPs conocidas del jddcia_models.json (campo known_ips de los modelos 8B).
    Devuelve lista de IPs en formato "x.x.x.x" (sin puerto).
    """
    ips = []
    try:
        path = os.path.normpath(_MODELS_JSON_PATH)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for model in data.get("models", []):
                for ip_port in model.get("known_ips", []):
                    ip = ip_port.split(":")[0]
                    if ip and ip not in ips:
                        ips.append(ip)
    except Exception as e:
        logger.debug(f"[LMStudio] No se pudo leer known_ips del config: {e}")
    return ips

# Subredes a escanear si las IPs conocidas fallan (formato: "x.x.x")
SCAN_SUBNETS = [
    "172.19.64",
    "172.20.64",
    "172.21.64",
    "172.22.64",
    "192.168.56",
    "192.168.0",
    "192.168.1",
    "10.0.0",
]

# Rango de hosts a escanear en cada subred (1-10 es suficiente para Hyper-V)
SCAN_HOST_RANGE = range(1, 11)

# Máximo de IPs a probar en paralelo durante el escaneo
MAX_PARALLEL_PROBES = 20

# ── Cache en memoria ──────────────────────────────────────────────────────────

_memory_cache_url: Optional[str] = None
_memory_cache_ts: float = 0.0


def _get_memory_cache() -> Optional[str]:
    """Devuelve la URL cacheada en memoria si no ha expirado."""
    if _memory_cache_url and (time.time() - _memory_cache_ts) < MEMORY_CACHE_TTL:
        return _memory_cache_url
    return None


def _set_memory_cache(url: str) -> None:
    """Guarda la URL en la cache en memoria."""
    global _memory_cache_url, _memory_cache_ts
    _memory_cache_url = url
    _memory_cache_ts = time.time()


def invalidate_cache() -> None:
    """Invalida la cache en memoria (llamar cuando una URL falla)."""
    global _memory_cache_url, _memory_cache_ts
    _memory_cache_url = None
    _memory_cache_ts = 0.0
    logger.info("[LMStudio] Cache en memoria invalidada")


# ── Cache en disco ────────────────────────────────────────────────────────────

def _load_disk_cache() -> Optional[str]:
    """Carga la URL del cache en disco."""
    try:
        if os.path.exists(DISK_CACHE_FILE):
            with open(DISK_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            url = data.get("url")
            saved_at = data.get("saved_at", 0)
            age = time.time() - saved_at
            if url and age < 86400:  # 24 horas
                logger.debug(f"[LMStudio] Cache disco: {url} (hace {age:.0f}s)")
                return url
    except Exception as e:
        logger.debug(f"[LMStudio] Error leyendo cache disco: {e}")
    return None


def _save_disk_cache(url: str) -> None:
    """Guarda la URL en el cache en disco."""
    try:
        with open(DISK_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"url": url, "saved_at": time.time(), "note": "LM Studio base_url"}, f, indent=2)
        logger.debug(f"[LMStudio] Cache disco guardado: {url}")
    except Exception as e:
        logger.warning(f"[LMStudio] No se pudo guardar cache disco: {e}")


# ── Detección de interfaces de red ────────────────────────────────────────────

def _get_local_interfaces() -> list[str]:
    """
    Detecta todas las IPs locales del PC (WiFi, Ethernet, Hyper-V, WSL2).
    Compatible con Windows (sin fcntl).
    Devuelve lista de IPs en formato "x.x.x.x".
    """
    ips = []
    try:
        # Método 1: socket.getaddrinfo (funciona en Windows y Linux)
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):  # Excluir IPv6 y loopback
                ips.append(ip)
    except Exception as e:
        logger.debug(f"[LMStudio] getaddrinfo falló: {e}")

    try:
        # Método 2: conectar a 8.8.8.8 para obtener la IP de salida
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
    except Exception:
        pass

    # Deduplicar y filtrar
    seen = set()
    result = []
    for ip in ips:
        if ip not in seen and not ip.startswith("127."):
            seen.add(ip)
            result.append(ip)

    logger.debug(f"[LMStudio] Interfaces detectadas: {result}")
    return result


def _get_subnets_from_interfaces() -> list[str]:
    """
    Extrae las subredes /24 de las interfaces locales.
    Ej: "192.168.1.100" → "192.168.1"
    """
    subnets = set()
    for ip in _get_local_interfaces():
        parts = ip.rsplit(".", 1)
        if len(parts) == 2:
            subnets.add(parts[0])
    return list(subnets)


# ── Probe de una IP ───────────────────────────────────────────────────────────

async def _probe_ip(ip: str, port: int = LMSTUDIO_PORT) -> Optional[str]:
    """
    Prueba si LM Studio está escuchando en ip:port.
    Devuelve la base_url si responde correctamente, None si no.

    Acepta solo HTTP 200 como válido (evita falsos positivos con routers).
    """
    url = f"http://{ip}:{port}{LMSTUDIO_HEALTH_PATH}"
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=PROBE_CONNECT_TIMEOUT, read=PROBE_READ_TIMEOUT, write=2.0, pool=2.0)
        ) as client:
            t0 = time.time()
            resp = await client.get(url)
            elapsed = time.time() - t0
            if resp.status_code == 200:
                base_url = f"http://{ip}:{port}/v1"
                logger.info(f"[LMStudio] ✅ Encontrado en {base_url} ({elapsed*1000:.0f}ms)")
                return base_url
            else:
                logger.debug(f"[LMStudio] {ip}:{port} → HTTP {resp.status_code} (no es LM Studio)")
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        pass  # Normal — la IP no tiene LM Studio
    except Exception as e:
        logger.debug(f"[LMStudio] {ip}:{port} → {type(e).__name__}: {e}")
    return None


# ── Descubrimiento principal ──────────────────────────────────────────────────

async def discover_lmstudio(force: bool = False) -> Optional[str]:
    """
    Descubre la URL base de LM Studio en la red local.

    Estrategia (en orden):
    1. Cache en memoria (si no ha expirado y no se fuerza redescubrimiento)
    2. Cache en disco
    3. IPs conocidas de Hyper-V/WSL2 (KNOWN_HYPER_V_IPS)
    4. Subredes detectadas en las interfaces del PC
    5. Subredes comunes de Hyper-V/WSL2 (SCAN_SUBNETS)

    @param force: Si True, ignora la cache y re-escanea
    @returns: base_url (ej: "http://172.19.64.1:1234/v1") o None si no se encuentra
    """
    # 1. Cache en memoria
    if not force:
        cached = _get_memory_cache()
        if cached:
            logger.debug(f"[LMStudio] Cache memoria: {cached}")
            return cached

    logger.info("[LMStudio] Iniciando descubrimiento de LM Studio...")

    # 2. Cache en disco
    if not force:
        disk_cached = _load_disk_cache()
        if disk_cached:
            # Verificar que sigue funcionando
            ip_port = disk_cached.replace("http://", "").replace("/v1", "")
            parts = ip_port.rsplit(":", 1)
            if len(parts) == 2:
                result = await _probe_ip(parts[0], int(parts[1]))
                if result:
                    _set_memory_cache(result)
                    return result
                else:
                    logger.info(f"[LMStudio] Cache disco {disk_cached} ya no responde — re-escaneando")

    # 3a. IPs conocidas del config JSON (known_ips de jddcia_models.json) — máxima prioridad
    config_ips = _get_known_ips_from_config()
    if config_ips:
        logger.info(f"[LMStudio] Probando {len(config_ips)} IPs del config JSON: {config_ips}")
        tasks = [_probe_ip(ip) for ip in config_ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, str):
                _set_memory_cache(result)
                _save_disk_cache(result)
                return result

    # 3b. IPs conocidas de Hyper-V/WSL2 (en paralelo)
    # Excluir las que ya probamos en 3a para no duplicar
    config_ips_set = set(config_ips)
    remaining_known = [ip for ip in KNOWN_HYPER_V_IPS if ip not in config_ips_set]
    logger.info(f"[LMStudio] Probando {len(remaining_known)} IPs conocidas de Hyper-V/WSL2...")
    tasks = [_probe_ip(ip) for ip in remaining_known]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, str):
            _set_memory_cache(result)
            _save_disk_cache(result)
            return result

    # 4. Subredes de las interfaces del PC
    local_subnets = _get_subnets_from_interfaces()
    all_subnets = list(dict.fromkeys(local_subnets + SCAN_SUBNETS))  # deduplicar, preservar orden

    logger.info(f"[LMStudio] Escaneando {len(all_subnets)} subredes: {all_subnets}")

    for subnet in all_subnets:
        ips_to_scan = [f"{subnet}.{host}" for host in SCAN_HOST_RANGE]
        # Escanear en lotes paralelos
        for i in range(0, len(ips_to_scan), MAX_PARALLEL_PROBES):
            batch = ips_to_scan[i:i + MAX_PARALLEL_PROBES]
            tasks = [_probe_ip(ip) for ip in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in batch_results:
                if isinstance(result, str):
                    _set_memory_cache(result)
                    _save_disk_cache(result)
                    return result

    logger.warning("[LMStudio] ❌ No se encontró LM Studio en ninguna IP conocida")
    return None


def discover_lmstudio_sync(force: bool = False) -> Optional[str]:
    """
    Versión síncrona de discover_lmstudio para usar desde código no-async.
    Crea un event loop temporal si no hay uno activo.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Ya hay un loop activo (ej: FastAPI) — usar run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(discover_lmstudio(force), loop)
            return future.result(timeout=30)
        else:
            return loop.run_until_complete(discover_lmstudio(force))
    except Exception as e:
        logger.error(f"[LMStudio] Error en discover_lmstudio_sync: {e}")
        return None


async def get_lmstudio_base_url(configured_url: Optional[str] = None, force: bool = False) -> Optional[str]:
    """
    Obtiene la URL base de LM Studio, con fallback a autodescubrimiento.

    Flujo:
    1. Si configured_url está en cache y funciona → usarla
    2. Si configured_url no funciona → autodescubrir
    3. Si no se encuentra → devolver configured_url como último recurso

    @param configured_url: URL configurada en jddcia_models.json (puede estar desactualizada)
    @param force: Forzar redescubrimiento aunque haya cache
    @returns: URL base funcional o None
    """
    # Intentar primero la URL configurada (si no se fuerza redescubrimiento)
    if configured_url and not force:
        cached = _get_memory_cache()
        if cached:
            return cached

        # Probar la URL configurada directamente
        ip_port = configured_url.replace("http://", "").replace("/v1", "").rstrip("/")
        parts = ip_port.rsplit(":", 1)
        if len(parts) == 2:
            result = await _probe_ip(parts[0], int(parts[1]))
            if result:
                _set_memory_cache(result)
                return result
            else:
                logger.info(
                    f"[LMStudio] URL configurada {configured_url} no responde — "
                    f"iniciando autodescubrimiento"
                )

    # Autodescubrimiento
    discovered = await discover_lmstudio(force=force)
    if discovered:
        return discovered

    # Último recurso: devolver la URL configurada aunque no responda
    # (el provider manejará el error con su propio timeout)
    if configured_url:
        logger.warning(
            f"[LMStudio] Usando URL configurada como último recurso: {configured_url}"
        )
        return configured_url

    return None
