# DEVIA — Guía de Uso de la IA Local (Qwen3 VL 30B)

## Documento: `DEVIA_IA_LOCAL.md`
## Aplica a: TODAS las funcionalidades del sistema

---

## 1. ¿Qué es la IA Local?

El sistema DEVIA tiene acceso a un modelo de IA que corre **en la red local JDDC**,
sin necesidad de internet:

| Parámetro | Valor |
|-----------|-------|
| **Modelo** | Qwen3 VL 30B (visión + texto + código) |
| **Servidor** | `jddcia.local` (mDNS) o `192.168.0.36` (IP directa) |
| **Puerto** | 80 (HTTP) |
| **Ruta API** | `/api/vlm/v1` (OpenAI-compatible) |
| **Auth** | Basic Auth (nginx) — `Authorization: Basic YWRtaW46YWlzdGFjazIwMjY=` |
| **IDs en el sistema** | `jddcia-qwen3-30b` (mDNS) / `jddcia-qwen3-30b-ip` (IP directa) |

---

## 2. Configuración Central

### 2.1 `backend/modules/chat/config.json` — Flags de comportamiento

```json
{
  "ai_local_only": true,
  "lan_max_retries": 10,
  "lan_read_timeout_s": 180,
  "max_sql_retries": 4
}
```

| Flag | Tipo | Descripción |
|------|------|-------------|
| `ai_local_only` | bool | `true` = SOLO usa Qwen3 LAN, nunca internet. `false` = fallback multi-modelo (Groq, Gemini, OpenAI...) |
| `lan_max_retries` | int | Reintentos máximos en modo LAN antes de devolver error (recomendado: 5-15) |
| `lan_read_timeout_s` | int | Timeout de lectura en segundos (Qwen3 30B: 30-60s normal, 120-180s para análisis profundo) |
| `max_sql_retries` | int | Reintentos de SQL con auto-corrección |

**IMPORTANTE**: El cambio en `config.json` surte efecto **inmediatamente** sin reiniciar el servidor.

### 2.2 `settings.py` / `.env` — URLs del gateway

```python
JDDCIA_BASE_URL = "http://jddcia.local/api/vlm/v1"          # mDNS (preferido)
JDDCIA_BASE_URL_FALLBACK = "http://192.168.0.36/api/vlm/v1" # IP directa (fallback)
JDDCIA_API_KEY = "YWRtaW46YWlzdGFjazIwMjY="                 # Base64(admin:aistack2026)
```

Si el servidor cambia de IP, **solo hay que actualizar `JDDCIA_BASE_URL_FALLBACK`** en el `.env`.
No hay que tocar ningún fichero de código.

---

## 3. Cómo Usa la IA Local Cada Funcionalidad

### 3.1 Chat con Base de Datos (módulo principal)

**Archivo:** `backend/modules/chat/service.py`

```python
# El modelo preferido viene del frontend (desplegable "Modelo IA")
response, model_used = await orchestrator.execute_with_fallback(
    system_prompt=system,
    user_message=user_msg,
    preferred_model_id=context.get('model_id')  # ← viene del frontend
)
```

**Flujo:**
1. El usuario selecciona el modelo en el desplegable del chat
2. El frontend envía `model_id: "jddcia-qwen3-30b-ip"` en el POST `/api/chat/send`
3. El orquestador coloca ese modelo primero en la lista de prioridad
4. Si `ai_local_only=true` en `config.json`, SOLO usa modelos LAN

**Para preseleccionar Qwen en el frontend:**
- El desplegable carga los modelos de `/api/models/enabled`
- El modelo `jddcia-qwen3-30b-ip` tiene `"enabled": true` en `jddcia_models.json`
- Para que aparezca primero, debe tener el `score` más alto o estar primero en la lista

### 3.2 DeepAnalysisAgent (análisis profundo)

**Archivo:** `backend/modules/chat/deep_analysis/helpers.py`

```python
# Siempre usa la IA local para el análisis profundo
response, model_used = await orchestrator.execute_with_fallback(
    system_prompt=system,
    user_message=user_msg,
    preferred_model_id="jddcia-qwen3-30b"  # ← hardcodeado: siempre LAN
)
```

**Flujo:**
- Las 5 fases del análisis (comprensión, exploración, investigación, análisis, síntesis)
  usan **siempre** la IA local como modelo preferido
- Si la IA local no está disponible y `ai_local_only=false`, hace fallback a internet
- Si `ai_local_only=true`, reintenta hasta `lan_max_retries` veces antes de fallar

### 3.3 SIUO (Sistema de Índices Ultra-Optimizados)

**Archivo:** `backend/modules/chat/deep_analysis/agent.py`

```python
# El agente SIUO también usa la IA local
response, model_used = await orchestrator.execute_with_fallback(
    system_prompt=system,
    user_message=user_msg,
    preferred_model_id="jddcia-qwen3-30b"  # ← siempre LAN
)
```

**Flujo:**
- La generación de índices SIUO usa la IA local para analizar la estructura de la BD
- El `KnowledgeStore` guarda los patrones aprendidos para evitar llamadas redundantes
- La optimización LAN (`_phase0_lan_optimize`) carga patrones conocidos antes de llamar a la IA

### 3.4 Artículos (generación de contenido)

**Archivo:** `backend/modules/articles/` (si existe)

```python
# El modelo se selecciona desde el desplegable "Modelo IA" de la sección Artículos
# ID del selector: "articles-model-selector"
```

**Flujo:**
- El usuario selecciona el modelo en el desplegable de la sección Artículos
- Se envía `model_id` al backend
- El orquestador usa ese modelo como preferido

---

## 4. El Orquestador de Fallback

**Archivo:** `backend/modules/chat/model_fallback_orchestrator.py`

### 4.1 API principal

```python
response, model_used = await orchestrator.execute_with_fallback(
    system_prompt="Eres un asistente...",
    user_message="¿Cuántos presupuestos hay?",
    images=None,                              # Opcional: lista de imágenes base64
    feedback_callback=None,                   # Opcional: función para feedback al usuario
    preferred_model_id="jddcia-qwen3-30b-ip"  # Opcional: modelo preferido
)
```

### 4.2 Modos de operación

| Modo | Config | Comportamiento |
|------|--------|----------------|
| **LAN_ONLY** | `ai_local_only: true` | Solo Qwen3 LAN. Reintenta `lan_max_retries` veces. Nunca internet. |
| **FALLBACK** | `ai_local_only: false` | Intenta el modelo preferido primero, luego fallback por score. |

### 4.3 Orden de prioridad de modelos (modo FALLBACK)

1. `preferred_model_id` (si se especifica y está habilitado)
2. Modelos ordenados por `score` descendente (en `ai_models_config.json`)
3. Si un modelo falla → siguiente en la lista
4. Si todos fallan → devuelve `(None, None)`

### 4.4 Modelos LAN conocidos

Definidos en `backend/core/utils/network_audit_constants.py`:

```python
class LocalModelIds:
    JDDCIA_MDNS = "jddcia-qwen3-30b"       # via jddcia.local (mDNS)
    JDDCIA_IP   = "jddcia-qwen3-30b-ip"    # via 192.168.0.36 (IP directa)
    ALL = frozenset([JDDCIA_MDNS, JDDCIA_IP])
```

---

## 5. Auto-Descubrimiento de Red (v2.0)

El `JDDCIAProvider` detecta automáticamente el gateway aunque el PC cambie de red:

```
1. Prueba jddcia.local (mDNS)
   ↓ falla
2. Prueba JDDCIA_BASE_URL_FALLBACK (IP fija del .env)
   ↓ falla
3. Prueba IP cacheada (.jddcia_ip_cache.json)
   ├─ Si subred cacheada ≠ subred actual → CAMBIO DE RED → limpiar cache
   └─ Si misma subred → probar IP cacheada
   ↓ falla
4. Autodescubrimiento en TODAS las subredes locales
   ├─ Detecta WiFi + Ethernet + VPN (sin fcntl, compatible Windows)
   ├─ Escanea cada subred en paralelo (lotes de 20)
   └─ Prueba IPs prioritarias primero (.38, .1, .100, .200...)
```

**Criterio de validez:** Solo acepta HTTP 200 o 401 (nunca 404 — puede ser el router).

---

## 6. Cómo Añadir la IA Local a una Nueva Funcionalidad

### Patrón estándar:

```python
from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
from backend.core.utils.network_audit_constants import LocalModelIds

# En el constructor de tu módulo:
self.orchestrator = ModelFallbackOrchestrator()

# En el método que necesita IA:
async def _call_ai(self, system: str, user_msg: str) -> str:
    response, model_used = await self.orchestrator.execute_with_fallback(
        system_prompt=system,
        user_message=user_msg,
        preferred_model_id=LocalModelIds.JDDCIA_IP  # "jddcia-qwen3-30b-ip"
    )
    if response is None:
        return "Error: IA no disponible"
    return response
```

### Con imágenes (visión):

```python
response, model_used = await self.orchestrator.execute_with_fallback(
    system_prompt="Analiza esta imagen...",
    user_message="¿Qué ves en la imagen?",
    images=["data:image/png;base64,iVBORw0KGgo..."],  # Lista de base64
    preferred_model_id=LocalModelIds.JDDCIA_IP
)
```

### Con feedback al usuario:

```python
def _feedback(msg: str):
    print(f"[IA] {msg}")  # O enviar por WebSocket, etc.

response, model_used = await self.orchestrator.execute_with_fallback(
    system_prompt=system,
    user_message=user_msg,
    feedback_callback=_feedback,
    preferred_model_id=LocalModelIds.JDDCIA_IP
)
```

---

## 7. Frontend — Desplegable de Modelos

### 7.1 Cómo se carga el desplegable

El endpoint `/api/models/enabled` devuelve los modelos habilitados ordenados por score.
El frontend (`chat.js → loadModels()`) los carga en el `<select id="chat-model-selector">`.

### 7.2 Para preseleccionar Qwen como modelo por defecto

**Opción A — Subir el score en `jddcia_models.json`:**
```json
{
  "id": "jddcia-qwen3-30b-ip",
  "score": 100,   ← El más alto → aparece primero
  "enabled": true
}
```

**Opción B — Marcar como `preferred: true` en el JSON** (si se implementa):
```json
{
  "id": "jddcia-qwen3-30b-ip",
  "preferred": true
}
```
Y en `loadModels()` del `chat.js`:
```javascript
const preferred = models.find(m => m.preferred) || models[0];
selector.value = preferred.id;
```

**Opción C — Usar `ai_local_only: true` en `config.json`:**
Con este flag activo, el backend siempre usa la IA local independientemente
del modelo seleccionado en el frontend.

### 7.3 Envío del modelo al backend

```javascript
// En sendMessage() de chat.js:
body: JSON.stringify({
  message: message,
  model_id: selectedModel,   // ← ID del modelo seleccionado
  deep_analysis: deepAnalysisEnabled,
  // ...
})
```

El backend en `service.py` lo recibe como:
```python
preferred_model_id = context.get('model_id')  # "jddcia-qwen3-30b-ip"
```

---

## 8. Modo Chat Sin Base de Datos

Para usar la IA local como chat conversacional puro (sin consultar Firebird):

### Backend — `service.py`

El servicio detecta si `db_params` es `null` o si `no_db: true`:
```python
no_db = context.get('no_db', False)
if no_db or not context.get('db_params'):
    # Modo conversacional puro — sin SQL, sin BD
    response, model_used = await orchestrator.execute_with_fallback(
        system_prompt="Eres DEVIA, asistente de JDDC...",
        user_message=message,
        preferred_model_id=context.get('model_id')
    )
    return {"success": True, "response": response}
```

### Frontend — `chat.js`

```javascript
// Checkbox "Sin BD" en el formulario
const noDbMode = document.getElementById("no-db-toggle")?.checked ?? false;

body: JSON.stringify({
  message: message,
  db_params: noDbMode ? null : dbParams,
  no_db: noDbMode,
  model_id: selectedModel,
})
```

---

## 9. Diagnóstico y Troubleshooting

### 9.1 El modelo no aparece en el desplegable

1. Verificar que `"enabled": true` en `jddcia_models.json`
2. Verificar que el endpoint `/api/models/enabled` devuelve el modelo
3. Verificar que el servidor JDDC está accesible: `curl http://192.168.0.36/api/vlm/v1/models`

### 9.2 La IA local no responde

1. Verificar `ai_local_only` en `config.json`
2. Revisar logs: `devia.log` y `devia_err.log`
3. Verificar la cache de IP: `backend/drivers/ai/.jddcia_ip_cache.json`
4. Borrar la cache si la IP cambió: eliminar `.jddcia_ip_cache.json`
5. El autodescubrimiento escaneará la red automáticamente en la siguiente petición

### 9.3 Timeout en análisis profundo

Aumentar `lan_read_timeout_s` en `config.json`:
```json
{
  "lan_read_timeout_s": 300
}
```
El cambio surte efecto inmediatamente sin reiniciar el servidor.

### 9.4 Verificar qué modelo se usó

El backend devuelve `model_id` en la respuesta:
```json
{
  "success": true,
  "response": "...",
  "model_id": "jddcia-qwen3-30b-ip"
}
```

---

## 10. Resumen de Ficheros Clave

| Fichero | Descripción |
|---------|-------------|
| `backend/modules/chat/config.json` | Flags: `ai_local_only`, `lan_max_retries`, `lan_read_timeout_s` |
| `backend/core/config/models/jddcia_models.json` | Definición del modelo Qwen3 LAN |
| `backend/core/utils/network_audit_constants.py` | IDs de modelos LAN (`LocalModelIds`) |
| `backend/modules/chat/model_fallback_orchestrator.py` | Orquestador con fallback y modo LAN_ONLY |
| `backend/drivers/ai/jddcia_provider.py` | Driver HTTP para el gateway JDDC (v2.0 multi-red) |
| `backend/core/config/settings.py` | URLs del gateway (`JDDCIA_BASE_URL`, `JDDCIA_BASE_URL_FALLBACK`) |
| `frontend/assets/js/modules/chat.js` | `loadModels()` — carga el desplegable de modelos |
| `frontend/index.html` | `<select id="chat-model-selector">` — desplegable de modelos |

---

*Última actualización: 14/04/2026 — JDDCIAProvider v2.0 + DeepAnalysisAgent v3.0*
