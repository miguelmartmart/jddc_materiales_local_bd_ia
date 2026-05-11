# Arquitectura Técnica y Stack Tecnológico

Este documento proporciona una visión exhaustiva de las tecnologías y la infraestructura de **AI Code Lab** (v1.2.0, mayo 2026).

## 1. Stack de Tecnologías

- **Frontend Core**: React 19 con TypeScript para tipado estricto.
- **Build Tool**: Vite para HMR ultrarrápido en desarrollo.
- **Desktop Wrapper**: Electron gestionando proceso principal y renderizado.
- **Styling**: Tailwind CSS 4.0 para diseño atómico.
- **Backend**: FastAPI (Python 3.10+) como motor de orquestación IA.
- **Editor**: Monaco Editor (`@monaco-editor/react`) — experiencia similar a VS Code.
- **Iconografía**: Lucide React para interfaz consistente.
- **HTTP Client (backend)**: `httpx` con `trust_env=False` (evita proxies Windows en LAN).

## 2. Arquitectura de Procesos

La aplicación opera mediante un modelo de **Triple Proceso**:

### A. Proceso Principal de Electron (Main Process)
Implementado en [electron/main.ts](../electron/main.ts).
- Gestión de ventana, diálogos nativos y acceso al sistema de archivos.
- Seguridad: `contextIsolation: true`, `nodeIntegration: false`.
- Arranca `backend/server.py` automáticamente al iniciar la aplicación.
- Comunicación con renderer exclusivamente vía `preload.ts`.

### B. Proceso de Renderizado (Renderer Process)
Implementado en [src/](../src/).
- Interfaz de usuario, estado React, visualización de datos.
- Acceso limitado al sistema mediante `window.electronAPI`.
- Incluye [src/utils/nextActionParser.ts](../src/utils/nextActionParser.ts) para parsear `[[NEXT_ACTION]]`.
- Incluye [src/utils/systemReports.ts](../src/utils/systemReports.ts) para generar mensajes `[SYSTEM]`.

### C. Proceso de Backend IA (Sidecar Process)
Implementado en [backend/server.py](../backend/server.py).
- REST API sobre `http://localhost:8002`.
- Motor de orquestación: construye system prompt mediante **17 fases modulares**.
- Conecta exclusivamente a Qwen3 VL 30B en LAN JDDC (IP `10.13.79.31`).
- Sin internet, sin APIs externas, sin claves API.

## 3. Motor de Prompts Modular (`backend/prompt_engine/`)

El sistema prompt no es una cadena estática sino un **conjunto de fases** ensambladas dinámicamente.

### Componentes

| Archivo | Responsabilidad |
|---------|----------------|
| `builder.py` | `PromptBuilder` — itera fases, llama `render(ctx)`, concatena y trunca |
| `context.py` | `PhaseContext` — dataclass con datos del proyecto compartidos entre fases |
| `phases/base.py` | `BasePhase` ABC — interfaz que todas las fases implementan |
| `phases/pNN_*.py` | 17 fases individuales, una clase por archivo |

### Restricción de tamaño
El modelo Qwen3 tiene **4096 tokens de contexto total** (sistema + historial + respuesta).
El system prompt está limitado a 8000 chars ≈ 2000 tokens para dejar margen.
Las 17 fases actuales suman ~6110 chars ≈ 1527 tokens.

## 4. Sistema [[NEXT_ACTION]]

Las respuestas de la IA pueden incluir bloques `[[NEXT_ACTION:{JSON}]]` que el frontend convierte en botones. Solo el **último mensaje del asistente** tiene botones activos (patrón `isLastAssistant`); los anteriores muestran "Acción superada".

El parsing es robusto en 3 capas (frontend) y 4 capas (backend) para manejar JSON malformado, backslashes de rutas Windows y texto después del cierre `}`.

## 5. Despliegue y Replicación

### Requisitos Previos
- Node.js 18+, Python 3.10+
- Red LAN JDDC con acceso a `10.13.79.31`
- Sin necesidad de API keys ni acceso a internet

### Pasos de Instalación
1. `npm install` — dependencias Electron y frontend
2. `pip install fastapi uvicorn httpx` — dependencias backend
3. `npm run dev` — arranque en desarrollo con hot-reload
4. `npm run build && npm start` — arranque en producción

## 6. Scripts de Control

- [start_codelab.bat](../start_codelab.bat): Arranca backend + Electron desde `bots/interjddcia/`
- Diagnóstico: `curl http://127.0.0.1:8002/debug/ping-ai`
