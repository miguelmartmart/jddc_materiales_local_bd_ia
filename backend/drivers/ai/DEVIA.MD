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

## 3. Otros Providers

| Provider | Fichero | Descripción |
|----------|---------|-------------|
| OpenAI | `openai_provider.py` | GPT-4, GPT-4o via API |
| Gemini | `gemini_provider.py` | Gemini Pro/Flash via API |
| Groq | `groq_provider.py` | Llama, Mixtral via Groq API |
| Anthropic | `anthropic_provider.py` | Claude via API |
| JDDCIA | `jddcia_provider.py` | Qwen3 VL 30B local (este módulo) |

---

## 4. Interfaz AIProvider

```python
class AIProvider(ABC):
    def configure(self, config: AIConfig): ...
    async def generate_text(self, prompt, system_instruction, images, ...): ...
    async def generate_json(self, prompt, schema, system_instruction): ...
    async def generate_image(self, prompt, size, quality): ...
```

---

## 5. Principios de Diseño

1. **Ultra-resiliente**: cada provider tiene fallbacks para todos los errores posibles
2. **Sin romper lo existente**: las mejoras son aditivas, no modifican la interfaz
3. **Autoconfigurable**: detecta IPs, puertos, subredes automáticamente
4. **Logging detallado**: siempre incluye `type(e).__name__` para diagnóstico
5. **Cache inteligente**: guarda descubrimientos para evitar re-escaneos

---

*Última actualización: 14/04/2026 — JDDCIAProvider v2.0 multi-red*
