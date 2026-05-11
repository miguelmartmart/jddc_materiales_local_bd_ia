# Directory: desktop-codelab/src

> **Última actualización:** 11/05/2026 | **Versión:** 1.2.0

## Propósito

Proceso de renderizado React + TypeScript. Contiene la UI principal, el cliente HTTP al backend y las utilidades de contexto e IA.

## Archivos principales

### `App.tsx`
Componente raíz. Gestiona todo el estado de la aplicación:
- **Chat de IA**: historial de mensajes, envío a `/api/generate`, renderizado de respuestas.
- **Editor Monaco**: apertura, edición y guardado de archivos.
- **Terminal**: ejecución de comandos vía `shell:execute`, visualización de salida.
- **Árbol de archivos**: exploración del `rootDir` abierto.
- **`[[NEXT_ACTION]]`**: usa `parseNextAction()` para detectar acciones; solo el último mensaje del asistente (`isLastAssistant`) muestra botones activos.
- **Fix `python --version`**: guard `!scriptMatch[1].startsWith('-')` para no tratar flags como rutas de archivo.

### `api.ts`
Cliente HTTP hacia el backend (puerto 8002):
- `LAN_MODEL_ID = 'jddcia-qwen3-30b-ip'` — constante usada en todas las llamadas.
- `generateCode(prompt, codeContext, modelId, messages, rootDir)` → `POST /api/generate`.
- `generateContextUpdate(prompt)` → `POST /api/generate` forzando `LAN_MODEL_ID`.
- `checkHealth()` → `GET /health`.
- `pingAI()` → `GET /debug/ping-ai`.

### `utils/nextActionParser.ts`
Parser robusto de bloques `[[NEXT_ACTION:{...}]]` en respuestas de la IA.

**Exports:**
- `parseNextAction(rawContent)` → `{ action: NextAction | null, error: string | null }`
- `isExecutableAction(action)` → `boolean`
- `extractRawNextAction(rawContent)` → `string | null`

**Capas de robustez:**
1. `JSON.parse()` directo
2. Extracción del primer objeto `{...}` balanceado (`extractFirstJsonObject`)
3. Corrección de backslashes Windows + reintentos 1 y 2

### `utils/systemReports.ts`
Fábrica de mensajes `[SYSTEM]` estructurados que se inyectan al historial del chat.

Tipos de mensajes generados:
- Resultado de ejecución de comando (stdout, stderr, exit code)
- Error de ejecución (para que la IA proponga auto-reparación)
- Guardado de archivo (ruta, nuevo o actualizado)
- Cancelación de acción por el usuario

### `utils/ContextManager.ts`
Singleton para gestión de memoria a largo plazo.
- Carga resúmenes Markdown desde `.codelab/contexts/`.
- Inyecta el resumen como `task_context` en cada consulta a la IA.
- `updateContextWithAI()` solicita a Qwen3 que actualice el resumen tras cada interacción relevante.
- Fail-safe: si la actualización falla, el chat continúa sin interrupciones.

## Componentes

### `components/TaskManager.tsx`
- Árbol de tareas/subtareas con drag & drop (API nativa HTML5).
- Cada tarea tiene múltiples chats independientes.
- Estados: `todo | in-progress | done`.
- Persistencia en `.codelab/project_index.json`.

## Puertos y conexiones

| Destino | URL | Propósito |
|---------|-----|-----------|
| Backend FastAPI | `http://127.0.0.1:8002` | Generación IA, health, modelos |
| Proceso Main (IPC) | `window.electronAPI` | Sistema de archivos, shell, diálogos |
