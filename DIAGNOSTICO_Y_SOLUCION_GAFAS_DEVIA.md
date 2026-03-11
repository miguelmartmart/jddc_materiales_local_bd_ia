# 🔍 DIAGNÓSTICO Y SOLUCIÓN — GAFAS META + CHAT IA DEVIA
## Análisis completo del log Android + Estado del sistema + Pasos para arreglarlo

> **Última actualización:** 02/03/2026  
> **App Android:** `com.jddc.metaglass` (MetaGlass)  
> **Backend DEVIA:** `bots/interjddcia/` (FastAPI + Firebird 2.5)  
> **IP del PC (servidor DEVIA):** `192.168.0.58` (Wi-Fi JDDC.local)  
> **Servidor Firebird:** `HOST1` = `192.168.0.254:3050`

---

## ✅ ESTADO ACTUAL DEL SISTEMA (02/03/2026)

| Componente | Estado | Detalle |
|-----------|--------|---------|
| Backend DEVIA | ✅ FUNCIONANDO | Puerto 8001, responde `/health` |
| Firebird BD | ✅ CONECTADO | `192.168.0.254:3050`, 11.832 artículos |
| IA principal | ✅ FUNCIONANDO | Qwen3 VL 30B en `jddcia.local` (192.168.0.36) |
| Chat completo | ✅ VERIFICADO | SQL generado + ejecutado + respuesta en español |
| settings.py | ✅ CORREGIDO | Carga `.env` desde ruta absoluta (no depende del CWD) |
| sql_corrector | ✅ CORREGIDO | `STOCK` → `STOCKARTICULO` automático |
| db_metadata | ✅ CORREGIDO | Columna `STOCKARTICULO` documentada correctamente |

---

## 📋 ÍNDICE

1. [Qué hace el sistema](#1-qué-hace-el-sistema)
2. [Análisis del log Android](#2-análisis-del-log-android)
3. [Problemas identificados y estado](#3-problemas-identificados)
4. [Cómo levantar el backend DEVIA](#4-cómo-levantar-el-backend-devia)
5. [Correcciones aplicadas en el backend](#5-correcciones-aplicadas-en-el-backend)
6. [Correcciones pendientes en Android](#6-correcciones-pendientes-en-android)
7. [Verificación de que todo funciona](#7-verificación-de-que-todo-funciona)
8. [Comandos de diagnóstico rápido](#8-comandos-de-diagnóstico-rápido)
9. [Historial de problemas resueltos](#9-historial-de-problemas-resueltos)

---

## 1. Qué hace el sistema

```
GAFAS META RAY-BAN (Android)
        │
        │ 1. Usuario dice: "ei clima"  (hotword)
        │ 2. Usuario dice: "cuántos artículos hay"
        ▼
App MetaGlass (com.jddc.metaglass)
        │
        │ HotwordVoiceCommandService detecta hotword
        │ VoiceCommandInterpreter clasifica el comando
        │   → "cuántos artículos hay"  → QUERY_DEVIA ✓
        │   → "cuántos productos hay"  → QUERY_DEVIA ✓ (corregido)
        ▼
DeviaChatClient (Android)
        │
        │ POST http://jddcia.local:8001/api/chat/send
        │   o  http://192.168.0.58:8001/api/chat/send  ← IP CORRECTA
        ▼
Backend DEVIA (bots/interjddcia/) — Puerto 8001
        │
        │ FastAPI → ChatService → IA (Qwen3 VL 30B / Groq)
        │ → Genera SQL → clean_firebird_sql() corrige errores
        │ → Ejecuta en Firebird → Interpreta resultado
        ▼
Firebird 2.5 en HOST1 (192.168.0.254:3050)
        │
        │ BD: C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb
        │ 11.832 artículos, clientes, facturas, etc.
        ▼
Respuesta en español → TTS en las gafas
```

---

## 2. Análisis del log Android

### ✅ Lo que SÍ funciona (primera consulta)

```
13:24:35 → Hotword "el clima" detectado ✅
13:24:43 → Comando capturado: "cuántos productos hay"
13:24:43 → VoiceCommandInterpreter → FREE_TEXT ⚠️ (debería ser QUERY_DEVIA)
13:24:45 → AiClient resuelve backend en 192.168.0.36 (puerto 80, no 8001)
13:27:58 → Respuesta: "Hay 12 productos en el catálogo actual." ✅
```

> ⚠️ La primera consulta fue al `AiClient` (puerto 80, IA genérica), NO al `DeviaChatClient`
> (puerto 8001, DEVIA). La respuesta "12 productos" puede ser inventada por la IA genérica.

### ❌ Lo que NO funcionaba (segunda consulta — ya resuelto)

```
13:28:18 → Comando: "dime algunos de los nombres de esos artículos"
13:28:18 → VoiceCommandInterpreter → QUERY_DEVIA ✅
13:28:21 → DeviaChatClient intenta http://jddcia.local:8001 → FALLA (DNS no resuelve)
13:28:24 → DeviaChatClient intenta http://192.168.0.36:8001 → FALLA (IP incorrecta)
13:28:24 → Inicia escaneo de TODA la subred 192.168.0.x:8001...
13:30:41 → ❌ DEVIA backend not found anywhere (2 minutos de espera)
```

**Causas raíz identificadas:**
1. Backend DEVIA no estaba corriendo
2. IP fallback en Android era `.36` en lugar de `.58`
3. `settings.py` no cargaba el `.env` (DB_HOST quedaba como `localhost`)
4. El LLM generaba `STOCK` (columna inexistente) en lugar de `STOCKARTICULO`

---

## 3. Problemas identificados

### ✅ RESUELTO — P1: Backend DEVIA no estaba corriendo

**Causa:** El backend no se levantaba porque `start_system.bat` buscaba `.venv\Scripts\uvicorn.exe`
pero el ejecutable no existía en esa ruta (solo existe `python.exe` y `uvicorn.exe` en `.venv\Scripts\`).

**Solución:** Lanzar con ruta absoluta:
```cmd
start "DEVIA" /D "C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia" ^
  cmd /c "set PYTHONPATH=C:\...\interjddcia && .venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 8001"
```

> ⚠️ **NOTA:** `start_system.bat` tiene un bug — verifica `.venv\Scripts\uvicorn.exe` pero
> el ejecutable SÍ existe. El problema era el CWD al lanzarlo. Ver sección 4.

---

### ✅ RESUELTO — P2: IP fallback incorrecta en Android

**Archivo:** `C:\Users\migue\AndroidStudioProjects\MetaGlass\app\src\main\res\values\devia_config.xml`

```xml
<!-- ANTES (incorrecto) -->
<string name="devia_backend_fallback_url">http://192.168.0.36:8001</string>

<!-- DESPUÉS (correcto — IP actual del PC servidor) -->
<string name="devia_backend_fallback_url">http://192.168.0.58:8001</string>
```

---

### ✅ RESUELTO — P3: Firebird — hostname HOST1 causa timeout

**Causa:** `firebirdsql` (driver Python) se cuelga indefinidamente con el hostname `HOST1`.
La resolución DNS funciona pero el handshake del protocolo Firebird se bloquea.

**Solución:** Usar IP directa en `.env`:
```env
# ANTES (causa timeout)
DB_HOST=HOST1

# DESPUÉS (funciona correctamente)
DB_HOST=192.168.0.254
```

---

### ✅ RESUELTO — P4: `settings.py` no cargaba el `.env`

**Causa:** `env_file = ".env"` en pydantic-settings usa ruta relativa al CWD.
Cuando uvicorn arranca desde un directorio diferente a `bots/interjddcia/`,
el `.env` no se encuentra y `settings` usa valores por defecto (`DB_HOST=localhost`, `DB_NAME=""`).

**Síntoma:** `Error conectando a Firebird: Unauthorized` (credenciales vacías/incorrectas).

**Solución aplicada en `backend/core/config/settings.py`:**
```python
from pathlib import Path

# Ruta absoluta al .env — funciona independientemente del CWD
_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"

class Settings(BaseSettings):
    class Config:
        env_file = str(_ENV_FILE)  # ← ruta absoluta, no relativa
```

---

### ✅ RESUELTO — P5: LLM genera `STOCK` (columna inexistente)

**Causa:** El LLM genera `SELECT ... STOCK FROM ARTICULO` pero la columna real es `STOCKARTICULO`.

**Solución en dos capas:**

**Capa 1 — `db_metadata_optimized.json`** (prevención):
```json
"STOCKARTICULO": "DECIMAL(10,2) - Cantidad en stock/inventario (USAR ESTA, no 'STOCK')",
"_nota_critica": "NUNCA uses 'STOCK' como nombre de columna — no existe. Usa siempre STOCKARTICULO"
```

**Capa 2 — `sql_corrector.py`** (corrección automática antes de ejecutar):
```python
# En clean_firebird_sql() — se aplica ANTES de ejecutar el SQL
ARTICULO_COLUMN_FIXES = {
    r'\bSTOCK\b': 'STOCKARTICULO',  # \bSTOCK\b NO reemplaza STOCKARTICULO ni STOCKFACTOR
}
```

**Capa 3 — prompt de corrección** (si falla y necesita reintento):
```
4. COLUMNAS CORRECTAS EN TABLA ARTICULO:
   - STOCK → NO EXISTE. Usar STOCKARTICULO (cantidad en inventario)
```

---

### ✅ RESUELTO — P6: Sin endpoint `/health`

**Causa:** El `DeviaChatClient` Android busca `GET /health` para verificar disponibilidad.

**Solución:** Endpoint añadido en `backend/main.py`:
```python
@app.get("/health")
async def health_check():
    return JSONResponse({
        "status": "ok",
        "service": "DEVIA Chat API",
        "version": "3.0.0",
        "timestamp": datetime.datetime.now().isoformat()
    })
```

---

### 🟡 PENDIENTE — P7: "productos" no activa QUERY_DEVIA

**Archivo:** `C:\Users\migue\AndroidStudioProjects\MetaGlass\app\src\main\java\com\jddc\metaglass\session\voice\VoiceCommandInterpreter.kt`

```kotlin
private val DEVIA_DOMAIN_KEYWORDS = listOf(
    "productos", "producto",   // ← AÑADIR ESTAS DOS LÍNEAS
    "artículos", "articulos",
    "facturas", "factura",
    // ...
)
```

---

### 🟡 PENDIENTE — P8: Sin backend disponible, las gafas no avisan al usuario

**Archivo:** `C:\Users\migue\AndroidStudioProjects\MetaGlass\app\src\main\java\com\jddc\metaglass\session\voice\HotwordVoiceCommandService.kt`

```kotlin
is DeviaQueryResult.Unavailable -> {
    ttsQueue.speak("No puedo conectar con el sistema de base de datos. " +
                   "Asegúrate de que el servidor DEVIA está encendido en la red.")
}
```

---

## 4. Cómo levantar el backend DEVIA

### ⚡ Método rápido (recomendado)

Doble clic en `start_system.bat` desde el Explorador de Windows, o desde CMD:

```cmd
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
start_system.bat
```

> ⚠️ **IMPORTANTE:** Ejecutar siempre desde el directorio `bots/interjddcia/`.
> Si se lanza desde otro directorio, el `.env` no se carga correctamente.

### 🔧 Método manual (si el bat falla)

```cmd
start "DEVIA" /D "C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia" ^
  cmd /c "set PYTHONPATH=C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia ^
  && C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia\.venv\Scripts\uvicorn.exe ^
  backend.main:app --host 0.0.0.0 --port 8001 --log-level info && pause"
```

### ✅ Verificar que está corriendo

```cmd
curl http://localhost:8001/health
REM → {"status":"ok","service":"DEVIA Chat API","version":"3.0.0",...}

curl http://192.168.0.58:8001/health
REM → mismo resultado (accesible desde la red local / gafas)
```

### 🔍 Verificar que carga el .env correctamente

```cmd
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from backend.core.config.settings import settings; print('DB_HOST:', settings.DB_HOST)"
REM → DB_HOST: 192.168.0.254   ← CORRECTO
REM → DB_HOST: localhost        ← INCORRECTO (el .env no se cargó)
```

---

## 5. Correcciones aplicadas en el backend

### `backend/core/config/settings.py`
- `env_file` usa ruta absoluta calculada desde `__file__` → funciona independientemente del CWD

### `backend/core/config/db_metadata_optimized.json`
- Tabla `ARTICULO`: columna `STOCKARTICULO` documentada correctamente
- Nota crítica: `NUNCA uses 'STOCK'`
- `consultas_comunes` actualizadas con `STOCKARTICULO`

### `backend/modules/chat/sql_corrector.py`
- `clean_firebird_sql()`: corrección automática `STOCK` → `STOCKARTICULO` (regex `\bSTOCK\b`)
- `request_correction()`: regla explícita en el prompt de corrección para columnas erróneas de ARTICULO

---

## 6. Correcciones pendientes en Android

| # | Archivo | Cambio | Urgencia |
|---|---------|--------|----------|
| 1 | `VoiceCommandInterpreter.kt` | Añadir `"productos", "producto"` a `DEVIA_DOMAIN_KEYWORDS` | 🟡 MEDIO |
| 2 | `HotwordVoiceCommandService.kt` | Mejorar mensaje TTS cuando DEVIA no disponible | 🟡 MEDIO |
| 3 | Android Studio | Recompilar y reinstalar la app en las gafas | 🟡 MEDIO |

---

## 7. Verificación de que todo funciona

### Test 1: Backend responde ✅
```cmd
curl http://localhost:8001/health
REM → {"status":"ok","service":"DEVIA Chat API","version":"3.0.0",...}
```

### Test 2: Accesible desde la red ✅
```cmd
curl http://192.168.0.58:8001/health
REM → {"status":"ok",...}
```

### Test 3: Consulta completa con BD real ✅
```cmd
curl -X POST http://localhost:8001/api/chat/send ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"cuantos articulos hay\", \"confirm_data_sending\": true}"
REM → {"success":true,"response":"Hay 11.832 artículos...","session_id":"..."}
```

### Test 4: Columna STOCKARTICULO funciona ✅
```cmd
curl -X POST http://localhost:8001/api/chat/send ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"dime un articulo con su stock\", \"confirm_data_sending\": true}"
REM → SQL generado usa STOCKARTICULO (no STOCK) ✅
```

### Test 5: Desde las gafas
1. Decir: **"ei clima"** (hotword)
2. Esperar el pitido/confirmación
3. Decir: **"consulta cuántos artículos hay"**
4. Esperar respuesta TTS: "Hay 11.832 artículos..."

---

## 8. Comandos de diagnóstico rápido

```cmd
REM ── Estado general ──────────────────────────────────────────
REM 1. Ver si DEVIA está corriendo
curl -s http://localhost:8001/health

REM 2. Ver si el puerto 8001 está en uso (y qué PID)
netstat -ano | findstr :8001

REM 3. Verificar IP del PC (debe ser 192.168.0.58)
ipconfig | findstr "192.168"

REM 4. Ver contenedores Docker
docker ps -a | findstr jddc

REM ── Firebird ─────────────────────────────────────────────────
REM 5. Test conexión Firebird desde Python
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
.venv\Scripts\python.exe -c "import firebirdsql; conn=firebirdsql.connect(host='192.168.0.254',port=3050,database=r'C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb',user='SYSDBA',password='masterkey',charset='WIN1252'); cur=conn.cursor(); cur.execute('SELECT COUNT(*) FROM ARTICULO'); print('Articulos:',cur.fetchone()[0]); conn.close()"
REM → Articulos: 11832

REM ── Settings ─────────────────────────────────────────────────
REM 6. Verificar que settings carga el .env correctamente
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from backend.core.config.settings import settings; print('DB_HOST:', settings.DB_HOST, '| DB_NAME:', settings.DB_NAME[:20] if settings.DB_NAME else 'VACIO')"
REM → DB_HOST: 192.168.0.254 | DB_NAME: C:\Distrito\OBRAS\Da

REM ── Matar y relanzar ─────────────────────────────────────────
REM 7. Matar proceso en puerto 8001
for /f "tokens=5" %a in ('netstat -ano ^| findstr ":8001 " ^| findstr "LISTENING"') do taskkill /F /PID %a

REM 8. Relanzar backend
start "DEVIA" /D "C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia" cmd /c "set PYTHONPATH=C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia && .venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 8001 --log-level info && pause"
```

---

## 9. Historial de problemas resueltos

| Fecha | Problema | Causa raíz | Solución |
|-------|---------|-----------|---------|
| 02/03/2026 | Backend no arrancaba | PYTHONPATH incorrecto / CWD incorrecto | Lanzar con `/D` y rutas absolutas |
| 02/03/2026 | Firebird "Unauthorized" | `settings.py` usaba `env_file=".env"` relativo → DB_HOST=localhost | `env_file = str(_ENV_FILE)` con ruta absoluta |
| 02/03/2026 | Firebird timeout con hostname | `firebirdsql` se cuelga con hostname `HOST1` | `DB_HOST=192.168.0.254` en `.env` |
| 02/03/2026 | IP fallback Android incorrecta | `.36` en lugar de `.58` | Actualizar `devia_config.xml` |
| 02/03/2026 | Sin endpoint `/health` | No estaba implementado | Añadido en `backend/main.py` |
| 02/03/2026 | SQL usa `STOCK` (columna inexistente) | LLM no conocía el nombre real `STOCKARTICULO` | `db_metadata_optimized.json` + `sql_corrector.py` auto-fix |

---

## 🔑 Referencia rápida del sistema

| Dato | Valor |
|------|-------|
| **IP del PC servidor (DEVIA)** | `192.168.0.58` |
| **Puerto DEVIA** | `8001` |
| **URL DEVIA (local)** | `http://localhost:8001` |
| **URL DEVIA (red)** | `http://192.168.0.58:8001` |
| **mDNS DEVIA** | `http://jddcia.local:8001` |
| **Endpoint chat** | `POST /api/chat/send` |
| **Endpoint health** | `GET /health` ✅ |
| **Servidor Firebird** | `192.168.0.254:3050` (HOST1) |
| **BD Firebird** | `C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb` |
| **Artículos en BD** | 11.832 (verificado 02/03/2026) |
| **IA principal** | Qwen3 VL 30B en `jddcia.local` (192.168.0.36) |
| **IA fallback** | Groq llama-3.3-70b (API key en `.env`) |
| **Proyecto Android** | `C:\Users\migue\AndroidStudioProjects\MetaGlass\` |
| **Script inicio** | `bots/interjddcia/start_system.bat` |
| **Columna stock ARTICULO** | `STOCKARTICULO` (NO `STOCK`) |
