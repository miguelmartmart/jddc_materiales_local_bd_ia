# Arquitectura Técnica y Stack Tecnológico

Este documento proporciona una visión exhaustiva de las tecnologías y la infraestructura de **AI Code Lab**, permitiendo su replicación y despliegue en nuevos entornos.

## 1. Stack de Tecnologías
- **Frontend Core**: React 19 con TypeScript para un tipado estricto y seguridad en tiempo de desarrollo.
- **Build Tool**: Vite 7.3.0 para un HMR (Hot Module Replacement) ultrarrápido.
- **Desktop Wrapper**: Electron 39.2.7 gestionando procesos de renderizado y proceso principal.
- **Styling**: Tailwind CSS 4.0 para diseño atómico y responsivo.
- **Backend**: FastAPI (Python 3.10+) para el motor de orquestación de IA.
- **Editor**: Monaco Editor (@monaco-editor/react) para una experiencia de edición similar a VS Code.
- **Iconografía**: Lucide React para una interfaz consistente y ligera.

## 2. Arquitectura de Procesos
La aplicación opera mediante un modelo de **Triple Proceso**:

### A. Proceso Principal de Electron (Main Process)
Implementado en [main.ts](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/electron/main.ts).
- **Responsabilidad**: Gestión de ventanas, diálogos nativos y acceso al sistema de archivos (OS level).
- **Seguridad**: `contextIsolation: true`, `nodeIntegration: false`. La comunicación se realiza exclusivamente vía `preload.js`.

### B. Proceso de Renderizado (Renderer Process)
Implementado en la carpeta `src/`.
- **Responsabilidad**: Interfaz de usuario, gestión de estado de React y visualización de datos.
- **Puente IPC**: Acceso limitado a funciones del sistema mediante `window.electronAPI`.

### C. Proceso de Backend IA (Sidecar Process)
Implementado en [server.py](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/backend/server.py).
- **Responsabilidad**: Motor de inferencia, gestión de modelos (Gemini, OpenAI) y fallback de modelos.
- **Comunicación**: REST API sobre `http://localhost:8002`.

## 3. Despliegue y Replicación
Para reproducir la aplicación en otro equipo, se requieren los siguientes pasos:

### Requisitos Previos
- **Node.js**: v18 o superior.
- **Python**: 3.10 o superior con `pip`.
- **Variables de Entorno**: Fichero `.env` en la raíz con las API Keys de los proveedores (GOOGLE_API_KEY, OPENAI_API_KEY).

### Pasos de Instalación
1. `npm install` (Instala dependencias de Electron y Frontend).
2. `pip install -r backend/requirements.txt` (Instala dependencias del backend de IA).
3. `npm run dev` (Arranca Vite, compila Electron y levanta el entorno de desarrollo).
4. `npm run build` (Genera el bundle de producción en la carpeta `dist/`).

## 4. Scripts de Control (Automation)
- [start_codelab.bat](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/start_codelab.bat): Orquestador de arranque en Windows.
- [stop_servers.bat](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/stop_servers.bat): Limpieza forzada de procesos colgantes (node, electron, python).
