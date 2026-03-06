"""
JDDC IA Gateway Provider — Qwen3 VL 30B (vLLM, OpenAI-compatible)
Gateway local en la red JDDC: http://jddcia.local/api/vlm/v1
Auth: Basic Auth (nginx) — header: Authorization: Basic <base64(user:pass)>

El OpenAI SDK envía Bearer, pero el gateway nginx requiere Basic.
Este provider usa httpx directamente para controlar el header de autenticación.

RESILIENCIA (v1.2):
- Timeout separado: connect=3s, read=20s (falla rápido si el host no existe)
- Autodescubrimiento de IP: si las URLs configuradas fallan, escanea la subred
- Cache de IP descubierta: persiste en disco para no re-escanear en cada petición
- Soporte multi-puerto: prueba puertos comunes del gateway (80, 8080, 443)
"""
from typing import Any, Dict, Optional, List
import json
import os
import asyncio
import logging
import ipaddress
import socket
import httpx
from backend.core.abstract.ai import AIProvider, AIConfig

logger = logging.getLogger(__name__)

# ─── Configuración de resiliencia ────────────────────────────────────────────

# Timeout separado: connect rápido (3s), read generoso (20s para inferencia)
# NOTA: Si el servidor IA local está apagado, el connect falla en 3s.
# Si está encendido pero ocupado (vLLM single-request), el read espera hasta 20s.
# Con _READ_TIMEOUT=20s y 2 reintentos por modelo = 45s perdidos si está caído.
# Reducido a 8s: suficiente para inferencia rápida, falla antes si está caído.
_CONNECT_TIMEOUT = 3.0
_READ_TIMEOUT    = 8.0

# Puertos a probar en el gateway (en orden de preferencia)
_GATEWAY_PORTS = [80, 8080, 443, 8443, 3000, 11434]

# Path del gateway en el servidor
_GATEWAY_PATH = "/api/vlm/v1"

# Cache de IP descubierta (archivo en el mismo directorio que este módulo)
_IP_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".jddcia_ip_cache.json")

# Subred a escanear (se detecta automáticamente si es posible)
_DEFAULT_SUBNET = "192.168.0"


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
    """Guarda la IP descubierta en disco para reutilizarla."""
    try:
        with open(_IP_CACHE_FILE, 'w') as f:
            json.dump({"ip": ip, "port": port, "base_url": base_url}, f, indent=2)
        logger.info(f"[JDDCIA] 💾 IP cacheada: {base_url}")
    except Exception as e:
        logger.warning(f"[JDDCIA] No se pudo guardar cache de IP: {e}")


def _clear_ip_cache():
    """Borra la cache de IP (útil cuando la IP cacheada ya no funciona)."""
    try:
        if os.path.exists(_IP_CACHE_FILE):
            os.remove(_IP_CACHE_FILE)
    except Exception:
        pass


def _get_local_subnet() -> str:
    """
    Detecta la subred local del PC automáticamente.
    Ejemplo: si el PC tiene 192.168.1.50, devuelve "192.168.1"
    """
    try:
        # Conectar a un host externo para obtener la IP local (sin enviar datos)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        # Extraer los primeros 3 octetos
        parts = local_ip.split(".")
        if len(parts) == 4:
            subnet = ".".join(parts[:3])
            logger.info(f"[JDDCIA] 🌐 Subred local detectada: {subnet}.x")
            return subnet
    except Exception:
        pass
    return _DEFAULT_SUBNET


async def _probe_url(client: httpx.AsyncClient, url: str, auth_header: str) -> bool:
    """
    Prueba si una URL del gateway responde correctamente.
    Devuelve True si responde con 200 o 401 (el servidor existe aunque la auth falle).
    """
    try:
        resp = await client.get(
            f"{url}/models",
            headers={"Authorization": auth_header},
            timeout=httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT)
        )
        # 200 = OK, 401 = servidor existe pero auth incorrecta, 404 = ruta incorrecta pero servidor existe
        return resp.status_code in (200, 401, 404)
    except Exception:
        return False


async def _discover_gateway_ip(auth_header: str) -> Optional[str]:
    """
    Escanea la subred local buscando el gateway JDDC.
    Prueba IPs .1 a .254 en los puertos configurados.
    
    Estrategia:
    1. Primero prueba IPs "probables" (.1, .38, .100, .200, .254)
    2. Luego escanea el resto en paralelo (lotes de 20)
    
    Returns:
        base_url del gateway si se encuentra, None si no.
    """
    subnet = _get_local_subnet()
    logger.info(f"[JDDCIA] 🔍 Iniciando autodescubrimiento en {subnet}.x ...")

    # IPs prioritarias a probar primero (las más comunes en redes domésticas/oficina)
    priority_ips = [38, 1, 2, 100, 101, 200, 201, 254, 10, 20, 50]
    all_ips = list(range(1, 255))
    remaining_ips = [i for i in all_ips if i not in priority_ips]
    ordered_ips = priority_ips + remaining_ips

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT),
        follow_redirects=True
    ) as client:
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
                    _save_ip_cache(ip, port, base_url)
                    return base_url

    logger.warning(f"[JDDCIA] ❌ Gateway no encontrado en {subnet}.x")
    return None


class JDDCIAProvider(AIProvider):
    """
    Provider para el gateway IA local JDDC (Qwen3 VL 30B via vLLM).
    Usa Basic Auth en lugar de Bearer porque el nginx del gateway lo requiere.
    
    Resiliencia v1.2:
    - Timeout separado connect/read
    - Autodescubrimiento de IP cuando las URLs configuradas fallan
    - Cache de IP descubierta en disco
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

    async def _get_working_base_url(self) -> str:
        """
        Devuelve la base_url que funciona actualmente.
        Orden de intentos:
        1. URL configurada (de jddcia_models.json)
        2. IP cacheada en disco (de un descubrimiento anterior)
        3. Autodescubrimiento escaneando la subred
        """
        auth_header = f"Basic {self.api_key}"

        # 1. Probar URL configurada
        async with httpx.AsyncClient() as client:
            if await _probe_url(client, self._configured_base_url, auth_header):
                return self._configured_base_url

        logger.warning(f"[JDDCIA] ⚠️ URL configurada no responde: {self._configured_base_url}")

        # 2. Probar IP cacheada
        cached = _load_ip_cache()
        if cached and cached["base_url"] != self._configured_base_url:
            async with httpx.AsyncClient() as client:
                if await _probe_url(client, cached["base_url"], auth_header):
                    logger.info(f"[JDDCIA] 💾 Usando IP cacheada: {cached['base_url']}")
                    return cached["base_url"]
            logger.warning(f"[JDDCIA] ⚠️ IP cacheada ya no funciona: {cached['base_url']}")
            _clear_ip_cache()

        # 3. Autodescubrimiento
        logger.info("[JDDCIA] 🔍 Iniciando autodescubrimiento de gateway...")
        discovered = await _discover_gateway_ip(auth_header)
        if discovered:
            return discovered

        # Si todo falla, devolver la URL configurada (el error se manejará en generate_text)
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
            "max_tokens": 2048,
            "temperature": 0.1,
        }

        # Timeout separado: connect rápido (3s), read generoso (20s para inferencia)
        timeout = httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{working_url}/chat/completions",
                headers=self._headers,
                json=payload,
            )

        if response.status_code == 401:
            raise Exception(
                f"JDDC Gateway 401 Unauthorized — verifica la API key Basic Auth en .env (JDDCIA_API_KEY)"
            )
        if response.status_code != 200:
            raise Exception(
                f"JDDC Gateway error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]

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
