"""
JDDC IA Gateway Provider — Qwen3 VL 30B (vLLM, OpenAI-compatible)
Gateway local en la red JDDC: http://jddcia.local/api/vlm/v1
Auth: Basic Auth (nginx) — header: Authorization: Basic <base64(user:pass)>

El OpenAI SDK envía Bearer, pero el gateway nginx requiere Basic.
Este provider usa httpx directamente para controlar el header de autenticación.

RESILIENCIA (v2.0):
- Timeout separado: connect=3s, read=60s (leído de config.json → lan_read_timeout_s)
  Qwen3 30B puede tardar 30-60s en la primera petición; 8s era insuficiente.
- _probe_url: SOLO acepta 200/401 como "servidor válido". 404 = ruta incorrecta
  (puede ser el router devolviendo HTML) → NO se cachea, NO se considera válido.
- Cache de IP: se limpia automáticamente si la IP cacheada devuelve 404 (router).
- Logging de excepciones: siempre incluye type(e).__name__ para diagnóstico.
- Autodescubrimiento de IP: si las URLs configuradas fallan, escanea la subred.
- Soporte multi-puerto: prueba puertos comunes del gateway (80, 8080, 443, etc.)
- MULTI-RED (v2.0): detecta TODAS las interfaces de red del PC (WiFi + Ethernet).
  Si el PC cambia de red (ej: oficina → casa → otra oficina), escanea todas las
  subredes disponibles automáticamente. Compatible con Windows (sin fcntl).
- DETECCIÓN DE CAMBIO DE RED: si la subred cacheada difiere de la actual,
  invalida la cache y re-escanea. Evita intentar IPs de redes anteriores.
"""
from typing import Any, Dict, List, Optional
import json
import os
import asyncio
import logging
import socket
import httpx
from backend.core.abstract.ai import AIProvider, AIConfig

logger = logging.getLogger(__name__)

# ─── Configuración de resiliencia ────────────────────────────────────────────

# Timeout de conexión: siempre 3s (falla rápido si el host no existe)
_CONNECT_TIMEOUT = 3.0

# Timeout de lectura: se lee de config.json (lan_read_timeout_s).
# Qwen3 30B necesita 30-60s para la primera inferencia.
# Valor por defecto conservador si config.json no está disponible.
_READ_TIMEOUT_DEFAULT = 60.0

# Puertos a probar en el gateway (en orden de preferencia)
_GATEWAY_PORTS = [80, 8080, 443, 8443, 3000, 11434]

# Path del gateway en el servidor
_GATEWAY_PATH = "/api/vlm/v1"

# Cache de IP descubierta (archivo en el mismo directorio que este módulo)
_IP_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".jddcia_ip_cache.json")

# Subred a escanear (se detecta automáticamente si es posible)
_DEFAULT_SUBNET = "192.168.0"

# Path del config.json del chat (fuente única de verdad para timeouts)
_CONFIG_JSON_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../modules/chat/config.json")
)


def _load_read_timeout() -> float:
    """
    Lee lan_read_timeout_s de config.json.
    Qwen3 30B puede tardar 30-60s en la primera petición.
    Si no se puede leer, usa _READ_TIMEOUT_DEFAULT (60s).
    """
    try:
        if os.path.exists(_CONFIG_JSON_PATH):
            with open(_CONFIG_JSON_PATH, 'r') as f:
                cfg = json.load(f)
            timeout = float(cfg.get("lan_read_timeout_s", _READ_TIMEOUT_DEFAULT))
            logger.debug(f"[JDDCIA] ⏱️ Read timeout cargado de config.json: {timeout}s")
            return timeout
    except Exception as e:
        logger.warning(f"[JDDCIA] No se pudo leer lan_read_timeout_s de config.json: {e}. "
                       f"Usando default {_READ_TIMEOUT_DEFAULT}s")
    return _READ_TIMEOUT_DEFAULT


def _get_read_timeout() -> float:
    """Devuelve el timeout de lectura actual (leído de config.json en cada llamada)."""
    return _load_read_timeout()


def _load_ip_cache() -> Optional[Dict]:
    """Carga la IP cacheada del disco. Devuelve None si no existe o está corrupta."""
    try:
        if os.path.exists(_IP_CACHE_FILE):
            with open(_IP_CACHE_FILE, 'r') as f:
                data = json.load(f)
            # Validar que tiene los campos necesarios
            if data.get("base_url") and data.get("ip"):
                return data
    except Exception:
        pass
    return None


def _save_ip_cache(ip: str, port: int, base_url: str):
    """
    Guarda la IP descubierta en disco para reutilizarla.
    IMPORTANTE: Solo llamar cuando la URL ha respondido con 200/401 (no 404).
    Un 404 puede ser el router devolviendo HTML — no es el gateway JDDC.
    """
    try:
        with open(_IP_CACHE_FILE, 'w') as f:
            json.dump({"ip": ip, "port": port, "base_url": base_url}, f, indent=2)
        logger.info(f"[JDDCIA] 💾 IP cacheada: {base_url}")
    except Exception as e:
        logger.warning(f"[JDDCIA] No se pudo guardar cache de IP: {e}")


def _clear_ip_cache():
    """
    Borra la cache de IP.
    Se llama cuando la IP cacheada devuelve 404 (router) o deja de responder.
    """
    try:
        if os.path.exists(_IP_CACHE_FILE):
            os.remove(_IP_CACHE_FILE)
            logger.info("[JDDCIA] 🗑️ Cache de IP eliminada (IP cacheada ya no es válida)")
    except Exception:
        pass


def _get_all_local_subnets() -> List[str]:
    """
    Detecta TODAS las subredes locales del PC (WiFi + Ethernet + VPN).
    Compatible con Windows, Linux y macOS (sin fcntl).

    Estrategia:
    1. Obtiene el hostname del PC
    2. Resuelve todas las IPs asociadas al hostname
    3. Añade la IP de la ruta por defecto (para VPNs y redes adicionales)
    4. Filtra IPs privadas (10.x, 172.16-31.x, 192.168.x)
    5. Deduplica subredes

    Ejemplo: PC con WiFi (192.168.1.50) + VPN (10.155.135.28)
    → devuelve ["192.168.1", "10.155.135"]

    Returns:
        Lista de subredes en formato "A.B.C" (sin el último octeto).
        Nunca lanza excepción — devuelve [_DEFAULT_SUBNET] como fallback.
    """
    subnets: List[str] = []

    def _is_private_ip(ip: str) -> bool:
        """Filtra IPs privadas (RFC 1918) y excluye loopback."""
        try:
            parts = [int(x) for x in ip.split(".")]
            if len(parts) != 4:
                return False
            if parts[0] == 127:  # loopback
                return False
            if parts[0] == 10:  # 10.0.0.0/8
                return True
            if parts[0] == 172 and 16 <= parts[1] <= 31:  # 172.16.0.0/12
                return True
            if parts[0] == 192 and parts[1] == 168:  # 192.168.0.0/16
                return True
        except Exception:
            pass
        return False

    def _ip_to_subnet(ip: str) -> Optional[str]:
        """Extrae los primeros 3 octetos de una IP."""
        try:
            parts = ip.split(".")
            if len(parts) == 4:
                return ".".join(parts[:3])
        except Exception:
            pass
        return None

    # Método 1: IP de la ruta por defecto (la más fiable para la red activa)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        if _is_private_ip(local_ip):
            subnet = _ip_to_subnet(local_ip)
            if subnet and subnet not in subnets:
                subnets.append(subnet)
                logger.info(f"[JDDCIA] 🌐 Red activa detectada: {subnet}.x (IP: {local_ip})")
    except Exception as e:
        logger.debug(f"[JDDCIA] _get_all_local_subnets método 1: {e}")

    # Método 2: Todas las IPs del hostname (detecta interfaces adicionales)
    try:
        hostname = socket.gethostname()
        all_ips = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for info in all_ips:
            ip = info[4][0]
            if _is_private_ip(ip):
                subnet = _ip_to_subnet(ip)
                if subnet and subnet not in subnets:
                    subnets.append(subnet)
                    logger.info(f"[JDDCIA] 🌐 Interfaz adicional detectada: {subnet}.x (IP: {ip})")
    except Exception as e:
        logger.debug(f"[JDDCIA] _get_all_local_subnets método 2: {e}")

    # Método 3 (Windows): usar ipconfig para detectar todas las interfaces
    if not subnets or len(subnets) < 2:
        try:
            import subprocess
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True, text=True, timeout=3,
                encoding="cp850"  # Windows usa cp850 en la consola
            )
            import re
            # Buscar líneas "Dirección IPv4" o "IPv4 Address"
            for line in result.stdout.splitlines():
                match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                if match and ('IPv4' in line or 'Direcci' in line):
                    ip = match.group(1)
                    if _is_private_ip(ip):
                        subnet = _ip_to_subnet(ip)
                        if subnet and subnet not in subnets:
                            subnets.append(subnet)
                            logger.info(f"[JDDCIA] 🌐 Interfaz (ipconfig): {subnet}.x (IP: {ip})")
        except Exception as e:
            logger.debug(f"[JDDCIA] _get_all_local_subnets método 3 (ipconfig): {e}")

    if not subnets:
        logger.warning(f"[JDDCIA] ⚠️ No se detectaron subredes locales. Usando fallback: {_DEFAULT_SUBNET}.x")
        return [_DEFAULT_SUBNET]

    logger.info(f"[JDDCIA] 🌐 Subredes detectadas: {[s + '.x' for s in subnets]}")
    return subnets


def _get_local_subnet() -> str:
    """
    Detecta la subred local principal del PC.
    Wrapper de _get_all_local_subnets() para compatibilidad.
    """
    subnets = _get_all_local_subnets()
    return subnets[0] if subnets else _DEFAULT_SUBNET


def _get_cached_subnet() -> Optional[str]:
    """
    Devuelve la subred de la IP cacheada (si existe).
    Útil para detectar si el PC cambió de red.
    """
    cached = _load_ip_cache()
    if cached and cached.get("ip"):
        parts = cached["ip"].split(".")
        if len(parts) == 4:
            return ".".join(parts[:3])
    return None


async def _probe_url(client: httpx.AsyncClient, url: str, auth_header: str) -> bool:
    """
    Prueba si una URL del gateway JDDC responde correctamente.

    CRITERIO DE VALIDEZ (v1.3 — corregido):
      ✅ 200 = OK, el gateway responde y la ruta existe
      ✅ 401 = el servidor existe pero la autenticación falló (gateway nginx)
      ❌ 404 = ruta no encontrada — puede ser el ROUTER devolviendo HTML
               (ej: 192.168.0.1 → router Movistar → 404 HTML)
               NO se considera válido para evitar cachear el router.
      ❌ Cualquier otra respuesta = no es el gateway JDDC

    PROBLEMA ANTERIOR: aceptar 404 causaba que la IP del router (192.168.0.1)
    se cacheara como gateway válido, rompiendo todas las peticiones posteriores.
    """
    read_timeout = _get_read_timeout()
    try:
        resp = await client.get(
            f"{url}/models",
            headers={"Authorization": auth_header},
            timeout=httpx.Timeout(read_timeout, connect=_CONNECT_TIMEOUT)
        )
        # SOLO 200 y 401 son válidos — 404 puede ser el router
        is_valid = resp.status_code in (200, 401)
        if not is_valid and resp.status_code == 404:
            logger.debug(
                f"[JDDCIA] ⚠️ _probe_url: {url} devolvió 404 — "
                f"posiblemente el router, NO el gateway JDDC. Ignorando."
            )
        return is_valid
    except Exception as e:
        logger.debug(f"[JDDCIA] _probe_url: {url} → {type(e).__name__}: {e}")
        return False


async def _discover_gateway_ip(auth_header: str) -> Optional[str]:
    """
    Escanea TODAS las subredes locales buscando el gateway JDDC.
    Prueba IPs .1 a .254 en los puertos configurados.

    Estrategia (v2.0 — multi-red):
    1. Detecta TODAS las subredes del PC (WiFi + Ethernet + VPN)
    2. Detecta si el PC cambió de red (subred cacheada ≠ subred actual)
    3. Para cada subred, prueba IPs "probables" primero (.1, .38, .100, etc.)
    4. Luego escanea el resto en paralelo (lotes de 20)

    NOTA: _probe_url ya rechaza 404, así que el router (.1) no se cacheará
    aunque responda con 404 HTML.

    Returns:
        base_url del gateway si se encuentra, None si no.
    """
    subnets = _get_all_local_subnets()
    cached_subnet = _get_cached_subnet()

    # Detectar cambio de red
    if cached_subnet and cached_subnet not in subnets:
        logger.warning(
            f"[JDDCIA] 🔄 CAMBIO DE RED DETECTADO: "
            f"subred cacheada={cached_subnet}.x, "
            f"subredes actuales={[s + '.x' for s in subnets]}. "
            f"Limpiando cache y re-escaneando."
        )
        _clear_ip_cache()

    logger.info(
        f"[JDDCIA] 🔍 Iniciando autodescubrimiento en "
        f"{len(subnets)} subred(es): {[s + '.x' for s in subnets]}"
    )

    # IPs prioritarias a probar primero (las más comunes en redes domésticas/oficina)
    priority_ips = [38, 1, 2, 100, 101, 200, 201, 254, 10, 20, 50]
    all_ips = list(range(1, 255))
    remaining_ips = [i for i in all_ips if i not in priority_ips]
    ordered_ips = priority_ips + remaining_ips

    read_timeout = _get_read_timeout()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(read_timeout, connect=_CONNECT_TIMEOUT),
        follow_redirects=True
    ) as client:
        # Escanear cada subred
        for subnet in subnets:
            logger.info(f"[JDDCIA] 🔍 Escaneando subred {subnet}.x ...")

            # Escanear en lotes para no saturar la red
            batch_size = 20
            for batch_start in range(0, len(ordered_ips), batch_size):
                batch = ordered_ips[batch_start:batch_start + batch_size]
                tasks = []
                url_map = {}

                for last_octet in batch:
                    ip = f"{subnet}.{last_octet}"
                    for port in _GATEWAY_PORTS:
                        if port in (80, 443):
                            url = f"{'https' if port == 443 else 'http'}://{ip}{_GATEWAY_PATH}"
                        else:
                            url = f"http://{ip}:{port}{_GATEWAY_PATH}"
                        task = asyncio.create_task(_probe_url(client, url, auth_header))
                        tasks.append(task)
                        url_map[id(task)] = (ip, port, url)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for task, result in zip(tasks, results):
                    if result is True:
                        ip, port, base_url = url_map[id(task)]
                        logger.info(f"[JDDCIA] ✅ Gateway encontrado en: {base_url}")
                        # _save_ip_cache solo se llama cuando _probe_url devuelve True
                        # (200/401), nunca para 404 — garantía anti-router
                        _save_ip_cache(ip, port, base_url)
                        return base_url

    logger.warning(
        f"[JDDCIA] ❌ Gateway no encontrado en ninguna subred: "
        f"{[s + '.x' for s in subnets]}"
    )
    return None


class JDDCIAProvider(AIProvider):
    """
    Provider para el gateway IA local JDDC (Qwen3 VL 30B via vLLM).
    Usa Basic Auth en lugar de Bearer porque el nginx del gateway lo requiere.

    Resiliencia v1.3:
    - Timeout de lectura configurable desde config.json (lan_read_timeout_s=60s)
    - _probe_url rechaza 404 (evita cachear el router como gateway)
    - Cache de IP se limpia automáticamente si devuelve 404
    - Logging de excepciones con type(e).__name__ para diagnóstico
    - Autodescubrimiento de IP cuando las URLs configuradas fallan
    """

    def __init__(self):
        self.base_url: Optional[str] = None
        self.api_key: Optional[str] = None  # Base64 de user:pass
        self.model_name: Optional[str] = None
        self._headers: Dict[str, str] = {}
        self._configured_base_url: Optional[str] = None  # URL original de config

    def configure(self, config: AIConfig):
        self._configured_base_url = (config.base_url or "http://jddcia.local/api/vlm/v1").rstrip("/")
        self.base_url = self._configured_base_url
        self.api_key = config.api_key or ""
        self.model_name = config.model or "unified-main"

        # El gateway nginx requiere Basic Auth, no Bearer
        self._headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }

        # ── max_tokens con prioridad: JSON modelo → config.json → auto(50%) ──
        extra = getattr(config, "extra_params", {})
        context_limit = int(extra.get("context_limit", 4096))
        parameters = extra.get("parameters") or {}

        # Prioridad 1: parameters.max_tokens del JSON del modelo
        if parameters.get("max_tokens"):
            self._max_tokens = int(parameters["max_tokens"])
        else:
            # Prioridad 2: lan_model_max_tokens de config.json
            global_override = None
            try:
                if os.path.exists(_CONFIG_JSON_PATH):
                    with open(_CONFIG_JSON_PATH, "r") as f:
                        cfg_json = json.load(f)
                    global_override = cfg_json.get("lan_model_max_tokens")
            except Exception:
                pass
            if global_override:
                self._max_tokens = int(global_override)
            else:
                # Prioridad 3: 50% del contexto (mínimo 512, máximo 8192)
                self._max_tokens = max(512, min(8192, context_limit // 2))

        # ── Safety clamp: max_tokens nunca puede >= context_limit ─────────────
        # Si max_tokens >= context_limit, el modelo devuelve error 400 porque
        # no quedan tokens para el input. Dejamos al menos 500 tokens de margen.
        _safe_max = max(256, context_limit - 500)
        if self._max_tokens >= context_limit:
            logger.warning(
                f"[JDDCIA] ⚠️ Safety clamp: max_tokens={self._max_tokens} >= "
                f"context_limit={context_limit}. Reduciendo a {_safe_max} "
                f"(context_limit - 500) para evitar error 400."
            )
            self._max_tokens = _safe_max

        # ── ContextManager para gestión inteligente de tokens ─────────────────
        from backend.core.context.context_manager import ContextManager, ContextManagerConfig
        ctx_cfg = ContextManagerConfig(
            model_context_limit=context_limit,
            max_tokens_response=self._max_tokens,
        )
        self._context_manager = ContextManager(ctx_cfg)

    async def _get_working_base_url(self) -> str:
        """
        Devuelve la base_url que funciona actualmente.
        Orden de intentos (v2.0 — multi-red):
        1. URL configurada (de jddcia_models.json / settings.py)
        2. FALLBACK URL de settings (JDDCIA_BASE_URL_FALLBACK)
        3. IP cacheada en disco (de un descubrimiento anterior)
           → Si la subred cacheada ≠ subred actual → cambio de red → limpiar cache
        4. Autodescubrimiento en TODAS las subredes locales (WiFi + Ethernet + VPN)

        NUEVO (v2.0): Detecta cambio de red automáticamente.
        Si el PC está en otra red, invalida la cache y re-escanea todas las
        subredes disponibles para encontrar el gateway en la nueva ubicación.
        """
        from backend.core.config.settings import settings as app_settings
        auth_header = f"Basic {self.api_key}"

        # 1. Probar URL configurada (hostname mDNS: jddcia.local)
        async with httpx.AsyncClient() as client:
            if await _probe_url(client, self._configured_base_url, auth_header):
                logger.debug(f"[JDDCIA] ✅ URL configurada OK: {self._configured_base_url}")
                return self._configured_base_url

        logger.warning(f"[JDDCIA] ⚠️ URL configurada no responde: {self._configured_base_url}")

        # 2. Probar FALLBACK URL de settings (IP fija de la red habitual)
        fallback_url = getattr(app_settings, "JDDCIA_BASE_URL_FALLBACK", None)
        if fallback_url and fallback_url != self._configured_base_url:
            async with httpx.AsyncClient() as client:
                if await _probe_url(client, fallback_url, auth_header):
                    logger.info(f"[JDDCIA] ✅ Fallback URL OK: {fallback_url}")
                    return fallback_url
            logger.warning(f"[JDDCIA] ⚠️ Fallback URL no responde: {fallback_url}")

        # 3. Probar IP cacheada (con detección de cambio de red)
        cached = _load_ip_cache()
        if cached:
            cached_url = cached["base_url"]
            cached_subnet = _get_cached_subnet()
            current_subnets = _get_all_local_subnets()

            # Detectar cambio de red
            if cached_subnet and cached_subnet not in current_subnets:
                logger.warning(
                    f"[JDDCIA] 🔄 CAMBIO DE RED: cache={cached_subnet}.x, "
                    f"actual={[s + '.x' for s in current_subnets]}. "
                    f"Saltando cache — el gateway está en otra red."
                )
                _clear_ip_cache()
            elif cached_url not in (self._configured_base_url, fallback_url):
                async with httpx.AsyncClient() as client:
                    if await _probe_url(client, cached_url, auth_header):
                        logger.info(f"[JDDCIA] 💾 Usando IP cacheada: {cached_url}")
                        return cached_url
                logger.warning(f"[JDDCIA] ⚠️ IP cacheada ya no funciona: {cached_url} — limpiando cache")
                _clear_ip_cache()

        # 4. Autodescubrimiento en todas las subredes
        logger.info("[JDDCIA] 🔍 Iniciando autodescubrimiento multi-red...")
        discovered = await _discover_gateway_ip(auth_header)
        if discovered:
            return discovered

        # Si todo falla, devolver la URL configurada (el error se manejará en generate_text)
        logger.warning(
            "[JDDCIA] ⚠️ Autodescubrimiento fallido en todas las redes. "
            "Usando URL configurada como último recurso."
        )
        return self._configured_base_url

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        images: list = None,
        audios: list = None,
        videos: list = None,
    ) -> str:
        if not self.base_url:
            raise Exception("JDDCIAProvider not configured")

        # Obtener URL que funciona (con autodescubrimiento si es necesario)
        working_url = await self._get_working_base_url()

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        # Build user content
        if images:
            user_content = [{"type": "text", "text": prompt}]
            for img_b64 in images:
                if "," not in img_b64:
                    img_b64 = f"data:image/png;base64,{img_b64}"
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": img_b64}
                })
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": getattr(self, "_max_tokens", 2048),
            "temperature": 0.1,
        }

        # Timeout: connect rápido (3s), read desde config.json (60s para Qwen3 30B)
        read_timeout = _get_read_timeout()
        timeout = httpx.Timeout(read_timeout, connect=_CONNECT_TIMEOUT)
        logger.debug(f"[JDDCIA] ⏱️ Timeout: connect={_CONNECT_TIMEOUT}s, read={read_timeout}s")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{working_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
        except Exception as e:
            # Loguear tipo de excepción completo para diagnóstico
            logger.error(
                f"[JDDCIA] ❌ Error HTTP en generate_text — "
                f"{type(e).__name__}: {e} "
                f"(url={working_url}, model={self.model_name}, "
                f"read_timeout={read_timeout}s)"
            )
            raise

        if response.status_code == 401:
            raise Exception(
                f"JDDC Gateway 401 Unauthorized — verifica la API key Basic Auth en .env (JDDCIA_API_KEY)"
            )
        if response.status_code == 404:
            # 404 inesperado en /chat/completions — puede ser que la URL sea incorrecta
            logger.error(
                f"[JDDCIA] ❌ 404 en /chat/completions — URL incorrecta o gateway no disponible: "
                f"{working_url}/chat/completions"
            )
            raise Exception(
                f"JDDC Gateway 404 — URL incorrecta: {working_url}/chat/completions. "
                f"Verifica que el gateway esté levantado y la ruta sea correcta."
            )
        if response.status_code != 200:
            logger.error(
                f"[JDDCIA] ❌ Error {response.status_code} en generate_text — "
                f"url={working_url}, respuesta: {response.text[:300]}"
            )
            raise Exception(
                f"JDDC Gateway error {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(
                f"[JDDCIA] ❌ Error parseando respuesta JSON — "
                f"{type(e).__name__}: {e} — respuesta raw: {response.text[:300]}"
            )
            raise Exception(
                f"JDDC Gateway: respuesta JSON inválida — {type(e).__name__}: {e}"
            )

    async def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        json_prompt = f"""{prompt}

Responde SOLO con un objeto JSON válido que satisfaga este esquema:
{json.dumps(schema, indent=2)}

Responde ÚNICAMENTE el objeto JSON, sin texto adicional."""

        text = await self.generate_text(json_prompt, system_instruction=system_instruction)

        # Clean markdown code blocks
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    async def generate_image(self, prompt: str, size: str = "1024x1024", quality: str = "standard") -> str:
        raise NotImplementedError("El gateway JDDC no soporta generación de imágenes")
