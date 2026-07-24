# DEVIA — Drivers de IA

## Módulo: `backend/drivers/ai/`

---

## 1. Visión General

Este módulo contiene los drivers (providers) para cada proveedor de IA soportado.
Cada driver implementa la interfaz `AIProvider` de `backend/core/abstract/ai.py`.

---

## 2. JDDCIAProvider — Gateway Local Qwen3 VL 30B

**Fichero:** `jddcia_provider.py`  
**Versión:** v2.0 (multi-red)

### 2.1 Descripción

Provider para el gateway IA local JDDC (Qwen3 VL 30B via vLLM).
- Protocolo: OpenAI-compatible (httpx directo, no SDK)
- Auth: Basic Auth (nginx) — `Authorization: Basic <base64(user:pass)>`
- Timeout: connect=3s, read=60s (configurable en `config.json → lan_read_timeout_s`)

### 2.2 Resiliencia Multi-Red (v2.0)

El provider es **ultra-resiliente** ante cambios de red. Cuando el PC cambia de red
(ej: oficina → casa → otra oficina → VPN), el sistema detecta automáticamente
la nueva ubicación del gateway sin intervención manual.

#### Orden de intentos en `_get_working_base_url()`:

```
1. URL configurada (jddcia.local — mDNS)
   ↓ falla
2. FALLBACK URL de settings (JDDCIA_BASE_URL_FALLBACK — IP fija habitual)
   ↓ falla
3. IP cacheada en disco (.jddcia_ip_cache.json)
   ├─ Si subred cacheada ≠ subred actual → CAMBIO DE RED → limpiar cache
   └─ Si misma subred → probar IP cacheada
   ↓ falla o cambio de red
4. Autodescubrimiento en TODAS las subredes locales
   ├─ Detecta WiFi + Ethernet + VPN (3 métodos, sin fcntl)
   ├─ Escanea cada subred en paralelo (lotes de 20)
   └─ Prueba IPs prioritarias primero (.38, .1, .100, .200...)
```

#### Detección de subredes (`_get_all_local_subnets()`):

```python
# Método 1: IP de la ruta por defecto (más fiable)
socket.connect("8.8.8.8", 80) → IP local activa

# Método 2: Todas las IPs del hostname
socket.getaddrinfo(hostname, None, AF_INET) → interfaces adicionales

# Método 3 (Windows): ipconfig
subprocess.run(["ipconfig"]) → parseo de "Dirección IPv4"
```

Filtra solo IPs privadas RFC 1918:
- `10.0.0.0/8` — redes corporativas/VPN
- `172.16.0.0/12` — redes privadas clase B
- `192.168.0.0/16` — redes domésticas/oficina

#### Ejemplo real (PC con múltiples interfaces):
```
Subredes detectadas: ['10.155.135', '192.168.56', '172.19.96']
                      ↑ VPN/corp    ↑ VirtualBox   ↑ Docker/WSL
```

### 2.3 Cache de IP

**Fichero:** `.jddcia_ip_cache.json` (en el mismo directorio que el provider)

```json
{
  "ip": "192.168.0.38",
  "port": 80,
  "base_url": "http://192.168.0.38/api/vlm/v1"
}
```

- Se guarda cuando `_probe_url()` devuelve `True` (200/401)
- Se limpia automáticamente cuando:
  - La IP cacheada devuelve 404 (puede ser el router)
  - La subred cacheada difiere de la subred actual (cambio de red)
  - La IP cacheada deja de responder

### 2.4 Criterio de validez de URL (`_probe_url()`)

```
✅ 200 — Gateway responde correctamente
✅ 401 — Gateway existe pero auth falló (nginx Basic Auth)
❌ 404 — Puede ser el ROUTER devolviendo HTML (NO cachear)
❌ Otros — No es el gateway JDDC
```

**IMPORTANTE**: El 404 se rechaza explícitamente para evitar que el router
(ej: `192.168.0.1` → Movistar) se cachee como gateway válido.

### 2.5 Configuración

En `settings.py`:
```python
JDDCIA_API_KEY = "YWRtaW46YWlzdGFjazIwMjY="  # Base64(admin:aistack2026)
JDDCIA_BASE_URL = "http://jddcia.local/api/vlm/v1"  # mDNS (preferido)
JDDCIA_BASE_URL_FALLBACK = "http://192.168.0.36/api/vlm/v1"  # IP fija (fallback)
```

En `config.json` (módulo chat):
```json
{
  "lan_read_timeout_s": 60
}
```

### 2.6 Puertos probados en autodescubrimiento

```python
_GATEWAY_PORTS = [80, 8080, 443, 8443, 3000, 11434]
```

---

## 3. LM Studio Discovery — Autodescubrimiento de IP Local

**Fichero:** `lmstudio_discovery.py`  
**Versión:** v1.0 (17/06/2026)

### 3.1 Descripción

Módulo de autodescubrimiento de LM Studio en red local. Resuelve el problema de que
la IP de LM Studio cambia según la interfaz de red activa (VirtualBox, WSL2, Hyper-V).

### 3.2 Estrategia de descubrimiento (en orden de prioridad)

```
1. Cache en memoria (TTL 5 min) — evita re-escaneos en cada llamada
   ↓ miss o force=True
2. Cache en disco (.lmstudio_ip_cache.json, TTL 24h) — persiste entre reinicios
   ↓ miss o expirada
3. IPs conocidas del config JSON (jddcia_models.json → lmstudio.known_ips)
   ↓ ninguna responde
4. Escaneo paralelo de subredes locales (MAX_PARALLEL_PROBES=20)
   ↓ nada encontrado
5. Devuelve None → el provider usa la URL configurada como fallback
```

### 3.3 IPs conocidas configuradas

En `backend/core/config/models/jddcia_models.json`:
```json
{
  "lmstudio": {
    "known_ips": ["192.168.56.1:1234", "172.19.64.1:1234"]
  }
}
```

- `192.168.56.1:1234` — VirtualBox Host-Only (confirmada activa)
- `172.19.64.1:1234` — Hyper-V/WSL2 (alternativa)

### 3.4 Cache en disco

**Fichero:** `.lmstudio_ip_cache.json` (en el mismo directorio que el provider)

```json
{
  "base_url": "http://192.168.56.1:1234/v1",
  "timestamp": 1718625000.0
}
```

TTL: 24 horas. Se invalida con `invalidate_cache()`.

### 3.5 API pública

```python
# Obtener URL base (con autodescubrimiento)
base_url = get_lmstudio_base_url(configured_url="http://192.168.56.1:1234/v1")
# → "http://192.168.56.1:1234/v1" si responde, o autodescubierta, o None

# Descubrimiento directo
base_url = discover_lmstudio(force=False)
# → "http://192.168.56.1:1234/v1" o None

# Invalidar cache (tras error de conexión)
invalidate_cache()
```

### 3.6 Integración con OpenAICompatibleProvider

> **⚠️ Corregido 13/07/2026**: hasta esa fecha esta sección describía una
> integración que **no existía en el código**. `openai_compatible_provider.py`
> no importaba `lmstudio_discovery.py` en absoluto — hacía una única llamada
> a la `base_url` fija de `jddcia_models.json` y, si fallaba (típico: la IP de
> la interfaz Hyper-V/WSL2 cambia al reiniciar el host), lanzaba la excepción
> directamente sin reintentar ni redescubrir. Esto causó un "IA local no
> disponible" real con LM Studio corriendo y accesible por 4 IPs distintas.
> Ahora sí está conectado de verdad — ver el método real abajo.

`openai_compatible_provider.py::generate_text()` reintenta hasta 3 veces
(`_MAX_RETRIES`). Si el modelo es LM Studio (`self._is_lmstudio_model()` —
mira si `"qwen3"` está en el nombre del modelo) y la llamada falla con un
error no permanente (no 401, no contexto excedido), invalida la cache y
redescubre antes del siguiente intento:

```python
# En generate_text(), bucle de reintentos:
if is_lmstudio:
    import backend.drivers.ai.lmstudio_discovery as disc_module
    disc_module.invalidate_cache()
    new_base_url = await disc_module.discover_lmstudio(force=True)
    if new_base_url:
        self._reconfigure_client(new_base_url)  # recrea el cliente OpenAI con la IP nueva
await asyncio.sleep(attempt + 1)
```

Verificado end-to-end: configurando el provider a propósito con una IP
muerta, `generate_text()` se autorrecupera y obtiene respuesta real del
modelo tras redescubrir la IP viva.

### 3.7 Tests

**Fichero:** `backend/tests/test_lmstudio_discovery.py` — 25 tests
**Fichero:** `backend/tests/test_openai_compatible_provider.py` — 23 tests
**Fichero:** `backend/tests/test_service_model_precedence.py` — 4 tests (precedencia `preferred_model_id`, módulo `chat`)

> **⚠️ Corregido 13/07/2026**: esta sección afirmaba "49 tests / 0 fallos" —
> tampoco era cierto. Ambos ficheros de test importaban con el prefijo
> `bots.interjddcia.backend...`, que no existe en el `sys.path` de este
> proyecto (`pytest.ini` usa `pythonpath = .` desde `bots/interjddcia`, sin
> paquete `bots`). Los tests fallaban en el `import`, nunca se llegó a
> ejecutar la lógica que verificaban. Corregido el prefijo en
> `test_openai_compatible_provider.py` (import → `backend...`, igual que el
> resto de la suite). De paso se corrigieron dos bugs reales que estos tests
> sacaron a la luz: `_build_extra_body()` trataba `enable_thinking=None`
> como `False`, y `_build_messages()` no truncaba el prompt cuando el
> presupuesto de tokens quedaba en negativo (relevante para los errores 400
> por contexto ya documentados en otras sesiones).

Cobertura:
- Cache memoria: TTL, invalidación, hit/miss
- Cache disco: guardado, lectura, expiración, JSON corrupto
- `probe_ip()`: 200 OK, 404, ConnectionError, Timeout
- `get_known_ips_from_config()`: lectura JSON, deduplicación, archivo inexistente
- `discover_lmstudio()`: cache hit, force, config JSON, sin resultado
- `get_lmstudio_base_url()`: URL configurada OK/falla, sin URL, fallback
- `is_lmstudio_model()`: detección por nombre de modelo
- `build_extra_body()`: enable_thinking False/True/None
- `build_messages()`: truncado, system instruction
- `generate_text()`: éxito, reintentos, backoff, errores no reintentables

---

## 4. Otros Providers

| Provider | Fichero | Descripción |
|----------|---------|-------------|
| OpenAI Compatible | `openai_compatible_provider.py` | LM Studio local (Qwen3 VL 8B) |
| Gemini | `gemini_provider.py` | Gemini Pro/Flash via API |
| JDDCIA | `jddcia_provider.py` | Qwen3 VL 30B local LAN |
| LM Studio Discovery | `lmstudio_discovery.py` | Autodescubrimiento de IP LM Studio |

---

## 4.1 Actualización crítica (24/07/2026) — OpenAICompatibleProvider

**Fichero:** `openai_compatible_provider.py`

Cambios aplicados con foco en timeouts de fase del chat:

1. Migración a cliente async nativo:
- `OpenAI` → `AsyncOpenAI`.

2. Retries internos desactivados:
- Cliente configurado con `max_retries=0`.
- Evita reintentos opacos del SDK que podían extender latencia fuera del presupuesto de fase.

3. Compatibilidad de tests/mocks preservada:
- Nuevo helper interno soporta clientes awaitable y mocks sync.
- La suite `backend/tests/test_openai_compatible_provider.py` se mantiene en verde.

4. Objetivo operativo:
- Reducir riesgo de trabajo tardío tras timeout de fase.
- Mantener control de retries/fallbacks en orquestación del chat (`ModelFallbackOrchestrator` + deadlines de `service.py`).

---

## 5. Interfaz AIProvider

```python
class AIProvider(ABC):
    def configure(self, config: AIConfig): ...
    async def generate_text(self, prompt, system_instruction, images, ...): ...
    async def generate_json(self, prompt, schema, system_instruction): ...
    async def generate_image(self, prompt, size, quality): ...
```

---

## 6. Principios de Diseño

1. **Ultra-resiliente**: cada provider tiene fallbacks para todos los errores posibles
2. **Sin romper lo existente**: las mejoras son aditivas, no modifican la interfaz
3. **Autoconfigurable**: detecta IPs, puertos, subredes automáticamente
4. **Logging detallado**: siempre incluye `type(e).__name__` para diagnóstico
5. **Cache inteligente**: guarda descubrimientos para evitar re-escaneos

---

*Última actualización: 24/07/2026 — OpenAICompatibleProvider migrado a AsyncOpenAI, retries internos desactivados, compatibilidad de mocks mantenida*
