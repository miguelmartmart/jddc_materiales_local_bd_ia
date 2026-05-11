# Directory: desktop-codelab
## AI Code Lab — Editor de Código con IA Local

> **Última actualización:** 11/05/2026
> **Versión:** 1.2.0
> **Modo:** AI_LOCAL_ONLY — Solo Qwen3 VL 30B en red LAN JDDC (sin internet)

---

## Propósito

Aplicación de escritorio tipo VS Code con asistente IA integrado para desarrollo de software guiado.
El asistente analiza, propone estructuras, genera código y ejecuta comandos — todo paso a paso,
con botones de acción interactivos y sin salir de la LAN corporativa.

---

## Arquitectura

```
desktop-codelab/
│
├── backend/
│   ├── server.py               ← FastAPI puerto 8002 (AI_LOCAL_ONLY)
│   │                              Endpoints: /health, /api/models, /api/generate,
│   │                              /api/models/refresh, /debug/ping-ai
│   │                              Retry dual (IP + mDNS), _fix_next_action (4 capas),
│   │                              trust_env=False (evita proxies Windows en LAN)
│   └── prompt_engine/
│       ├── builder.py          ← PromptBuilder: ensambla fases activas en orden
│       ├── context.py          ← PhaseContext dataclass (project_path, folders_context…)
│       └── phases/             ← 17 fases modulares (una clase Python por fase)
│           ├── base.py         ← BasePhase ABC
│           ├── p01_header.py
│           ├── p01b_analysis_first.py  ← Análisis previo + detección conflictos carpetas
│           ├── p02_intent.py
│           ├── p02b_conversational.py
│           ├── p02c_code_gen.py
│           ├── p03_folders.py          ← Propuesta carpetas + lista existentes
│           ├── p04_env_verify.py
│           ├── p04b_env_failed.py
│           ├── p05_plan_confirm.py
│           ├── p06_code_create.py
│           ├── p07_dep_install.py
│           ├── p08_execution.py
│           ├── p09_midflow.py
│           ├── p10_general_rules.py
│           ├── p11_action_buttons.py
│           └── p12_error_handling.py
│
├── electron/
│   ├── main.ts                 ← Proceso principal: ventana, menús, IPC handlers
│   │                              Arranca server.py automáticamente
│   └── preload.ts              ← Bridge seguro (contextIsolation: true)
│
├── src/
│   ├── App.tsx                 ← UI principal (chat + Monaco + terminal + árbol)
│   ├── api.ts                  ← Cliente HTTP (LAN_MODEL_ID forzado)
│   ├── index.css               ← Estilos globales (Tailwind v4)
│   ├── main.tsx                ← Entry point React
│   ├── components/
│   │   └── TaskManager.tsx     ← Tareas/subtareas/chats drag & drop
│   └── utils/
│       ├── nextActionParser.ts ← Parser robusto [[NEXT_ACTION]] (3 capas)
│       ├── systemReports.ts    ← Mensajes [SYSTEM] estructurados al chat
│       └── ContextManager.ts   ← Memoria persistente en .codelab/
│
├── DOCS_README/                ← 7 documentos técnicos detallados
├── start_codelab.bat           ← Script arranque recomendado
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## Modelos IA disponibles

| ID | Nombre | URL | Score | Estado |
|----|--------|-----|-------|--------|
| `jddcia-qwen3-30b-ip` | Qwen3 VL 30B (IP directa) | http://10.13.79.31/api/vlm/v1 | 100 | ✅ Preferido |
| `jddcia-qwen3-30b` | Qwen3 VL 30B (mDNS) | http://jddcia.local/api/vlm/v1 | 38 | ⚠️ Fallback |

> El mDNS `jddcia.local` puede no resolver en Windows sin Bonjour activo.
> Siempre se intenta primero la IP directa.

**Contexto disponible:** 4096 tokens (modelo Qwen3).
**Restricción crítica:** el sistema prompt debe mantenerse bajo ~2000 tokens para dejar espacio
a la conversación y la respuesta. Actualmente: ~6110 chars ≈ 1527 tokens.

---

## Motor de Prompts (Fases)

El backend usa un motor modular donde cada fase es una clase Python que hereda de `BasePhase`.
El `PromptBuilder` las ensambla en orden, pasando un `PhaseContext` con los datos del proyecto.

### Orden de fases (DEFAULT_PHASES)

| # | Fase | Propósito |
|---|------|-----------|
| 1 | `p01_header` | Identidad, modelo, restricciones globales |
| 2 | `p01b_analysis_first` | Análisis previo obligatorio + detección conflictos de carpetas |
| 3 | `p02_intent` | Clasificación de intención del usuario |
| 4 | `p02b_conversational` | Respuestas conversacionales cortas |
| 5 | `p02c_code_gen` | Generación de código completo con cabecera de ruta |
| 6 | `p03_folders` | Propuesta de estructura de carpetas (con lista de existentes) |
| 7 | `p04_env_verify` | Verificación del entorno antes de ejecutar |
| 8 | `p04b_env_failed` | Recuperación si el entorno falla |
| 9 | `p05_plan_confirm` | Confirmación de plan antes de actuar |
| 10 | `p06_code_create` | Creación ordenada de archivos |
| 11 | `p07_dep_install` | Instalación de dependencias |
| 12 | `p08_execution` | Ejecución y reporte de resultados |
| 13 | `p09_midflow` | Continuación de flujos a mitad de tarea |
| 14 | `p10_general_rules` | Reglas generales de formato y comportamiento |
| 15 | `p11_action_buttons` | Instrucciones para generar `[[NEXT_ACTION]]` |
| 16 | `p12_error_handling` | Manejo de errores y auto-reparación |

### PhaseContext

```python
@dataclass
class PhaseContext:
    project_path: str | None       # Carpeta raíz del proyecto
    folders_context: str           # Lista de carpetas existentes en project_path
    task_context: str | None       # Resumen de la tarea activa (de ContextManager)
    deep_analysis: bool            # Si el usuario activó análisis profundo
    current_date: str              # Fecha actual inyectada automáticamente
```

---

## Sistema [[NEXT_ACTION]]

Las respuestas de la IA pueden incluir un bloque `[[NEXT_ACTION:{...}]]` que el frontend
convierte en botones interactivos. Solo el **último mensaje del asistente** muestra botones activos;
los anteriores muestran "Acción superada".

### Tipos disponibles

| Tipo | Botón UI | Acción |
|------|----------|--------|
| `run_command` | Verde — Ejecutar | Ejecuta `content` en PowerShell |
| `browser` | Azul — Abrir navegador | Abre `content` en el navegador por defecto |
| `confirm_plan` | Verde — Continuar | Envía mensaje de confirmación al chat |
| `open_file` | Azul claro — Abrir archivo | Abre `content` en el editor Monaco |

### Estructura JSON

```json
[[NEXT_ACTION:{
  "type": "run_command",
  "content": "python main.py",
  "label": "Ejecutar script",
  "cancel_label": "Cancelar",
  "cancel_message": "El usuario canceló la ejecución."
}]]
```

### Robustez de parsing (3 capas — frontend, `nextActionParser.ts`)

1. `JSON.parse()` directo del bloque extraído
2. Extracción de primer objeto `{...}` balanceado (maneja texto después del `}`)
3. Corrección de backslashes Windows + reintentos 1 y 2

### Robustez de parsing (4 capas — backend, `_fix_next_action` en `server.py`)

1. `json.loads()` directo
2. Extracción de primer objeto `{...}` balanceado
3. Corrección de backslashes + extracción balanceada
4. Reconstrucción a partir de rutas Windows detectadas en el texto circundante

---

## Endpoints del backend (puerto 8002)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del backend, modo y modelos LAN disponibles |
| GET | `/api/models` | Lista de modelos LAN habilitados |
| POST | `/api/models/refresh` | Verifica modelos LAN (sin internet) |
| POST | `/api/generate` | Genera respuesta con Qwen3 LAN |
| GET | `/debug/ping-ai` | Diagnóstico directo de conectividad con la IA LAN |

### Ejemplo `/health`
```cmd
curl http://127.0.0.1:8002/health
```
```json
{
  "status": "ok",
  "mode": "AI_LOCAL_ONLY",
  "lan_models": ["Qwen3 VL 30B (JDDC LAN — IP directa)", "Qwen3 VL 30B (JDDC LAN — mDNS)"],
  "lan_models_count": 2
}
```

### Ejemplo `/debug/ping-ai`
```cmd
curl http://127.0.0.1:8002/debug/ping-ai
```
```json
{
  "ip_url": "http://10.13.79.31/api/vlm/v1",
  "ip_status": 200,
  "mdns_url": "http://jddcia.local/api/vlm/v1",
  "mdns_status": "error: ...",
  "recommendation": "Usar IP directa"
}
```

---

## Flujo de generación de código

```
Usuario escribe en el chat
    │
    ▼
App.tsx → api.generateCode(prompt, codeContext, LAN_MODEL_ID, messages, rootDir)
    │
    ▼
api.ts → POST http://127.0.0.1:8002/api/generate
    │
    ▼
server.py:
    ├─ PromptBuilder.build(ctx) → system prompt (17 fases, ~1527 tokens)
    ├─ Intento 1: jddcia-qwen3-30b-ip (IP directa, score 100)
    │   └─ Si 400 "context length": reduce max_tokens automáticamente y reintenta
    ├─ Intento 2: jddcia-qwen3-30b (mDNS, score 38) — si intento 1 falla
    ├─ Último recurso: calcula tokens disponibles exactos del mensaje de error y reintenta
    └─ Si todos fallan → HTTP 503
    │
    ▼
_fix_next_action() → repara JSON malformado en [[NEXT_ACTION]]
    │
    ▼
App.tsx → renderiza respuesta, parseNextAction() detecta [[NEXT_ACTION]]
    │
    └─ Si isLastAssistant: muestra botón activo
       Si no: muestra "Acción superada"
```

---

## Garantías de privacidad (AI_LOCAL_ONLY)

1. `_get_lan_models()` filtra exclusivamente por `LocalModelIds.ALL` — solo IDs locales
2. `_try_lan_model()` verifica `model_id not in LOCAL_MODEL_IDS` antes de llamar
3. `api.ts`: `LAN_MODEL_ID = 'jddcia-qwen3-30b-ip'` — constante en todas las llamadas
4. `trust_env=False` en `httpx.AsyncClient` — ignora configuración de proxy del sistema Windows
5. `/api/models/refresh` no conecta a APIs externas en modo LAN_ONLY

---

## Sistema de Tareas y Contexto

### TaskManager (`src/components/TaskManager.tsx`)
- Tareas con subtareas anidadas (drag & drop)
- Cada tarea tiene múltiples chats independientes
- Estados: `todo` | `in-progress` | `done`
- Persistencia en `.codelab/project_index.json`

### ContextManager (`src/utils/ContextManager.ts`)
- Memoria persistente en `.codelab/contexts/`
- `task_<id>.md` — contexto de cada tarea
- `chat_<id>.md` — contexto de cada chat
- Actualización automática con Qwen3 LAN tras cada respuesta
- Fail-safe: si la IA falla, el chat continúa sin actualizar el contexto

### Mensajes [SYSTEM] (`src/utils/systemReports.ts`)
- Fábrica de mensajes estructurados que se inyectan al historial del chat
- Reportan resultados de ejecución, errores, guardado de archivos
- La IA los recibe como contexto para auto-reparar errores o continuar flujos

### Estructura `.codelab/`
```
.codelab/
├── project_index.json     ← Árbol de tareas serializado
└── contexts/
    ├── task_<id>.md       ← Contexto de cada tarea
    └── chat_<id>.md       ← Contexto de cada chat
```

---

## Cómo arrancar

### Opción A — Script automático (recomendado)
```cmd
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
start_codelab.bat
```

### Opción B — Modo desarrollo (hot-reload)
```cmd
cd desktop-codelab
npm run dev
```

### Opción C — Manual
```cmd
REM Terminal 1: Backend
cd desktop-codelab
python backend/server.py

REM Terminal 2: Electron
cd desktop-codelab
npm run build && npm start
```

---

## Diagnóstico rápido

```cmd
REM 1. Backend activo?
curl http://127.0.0.1:8002/health

REM 2. IA LAN alcanzable?
curl http://127.0.0.1:8002/debug/ping-ai

REM 3. Test generación
curl -X POST http://127.0.0.1:8002/api/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"hola, escribe un hello world en Python\"}"

REM 4. Modelos LAN disponibles
curl http://127.0.0.1:8002/api/models
```

---

## Problemas conocidos y soluciones

| Problema | Causa | Solución |
|---------|-------|---------|
| `503 Service Unavailable` | Qwen3 LAN no alcanzable | `curl /debug/ping-ai` — verificar IP 10.13.79.31 |
| `400 context_length_exceeded` | Prompt + historial excede 4096 tokens | server.py auto-reduce max_tokens; si persiste, acortar historial |
| `jddcia.local` no resuelve | mDNS no activo en Windows | Normal — usar siempre IP directa (jddcia-qwen3-30b-ip) |
| JSON parse error `[[NEXT_ACTION]]` | IA genera JSON malformado | Corregido: 4 capas backend + 3 capas frontend |
| `python --version` muestra error archivo | Bug regex capturaba `--version` como ruta | Corregido: guard `!startsWith('-')` en App.tsx |
| Backend no arranca | Python no en PATH o deps faltantes | `pip install fastapi uvicorn httpx` |
| Electron no abre | `npm run build` falló | Revisar errores TypeScript en consola |

---

## Archivos modificados (11/05/2026) — v1.2.0

| Archivo | Cambio |
|---------|--------|
| `backend/server.py` | `trust_env=False` en httpx; retry con tokens exactos del error 400; `_fix_next_action` 4 capas; endpoint `/debug/ping-ai`; safety truncation a 8000 chars |
| `backend/prompt_engine/` | Sistema modular de 17 fases; `PhaseContext`; `PromptBuilder` |
| `backend/prompt_engine/phases/p01b_analysis_first.py` | Nueva fase: análisis previo obligatorio + detección conflictos de carpetas |
| `backend/prompt_engine/phases/p03_folders.py` | Ahora incluye `folders_context` con regla explícita de no reutilizar nombres |
| `backend/prompt_engine/phases/p02c_code_gen.py` | Eliminado `folders_context` (trasladado a p03) |
| `src/utils/nextActionParser.ts` | Reescrito: 3 capas de parsing con extracción balanceada y corrección backslashes |
| `src/utils/systemReports.ts` | Nuevo: fábrica de mensajes [SYSTEM] estructurados |
| `src/App.tsx` | Fix bug `python --version`; integración `nextActionParser`; `isLastAssistant` |
