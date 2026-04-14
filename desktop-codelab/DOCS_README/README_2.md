# Lógica de Negocio y Gestión de Estados

Este documento detalla el motor funcional de **AI Code Lab**, desde la comunicación inter-proceso (IPC) hasta la persistencia de la "memoria" del asistente.

## 1. Comunicación Inter-Proceso (IPC)
El sistema utiliza el puente seguro definido en [preload.ts](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/electron/preload.ts).

### Métodos Expuestos:
- **fs:readDir/readFile/writeFile**: Abstracciones asíncronas para el sistema de archivos de Windows.
- **shell:execute**: Ejecución de comandos en `powershell.exe`. Incluye un diálogo de confirmación de seguridad nativo antes de cada ejecución.
- **dialog:openFolder**: Invocación del explorador de carpetas nativo para definir el `rootDir` del proyecto.

## 2. Motor de Contexto y Memoria
El [ContextManager.ts](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/src/utils/ContextManager.ts) implementa un patrón Singleton para la gestión de la "Long Term Memory".

### Flujo de Trabajo del Contexto:
1. **Detección de Tarea**: Cuando el usuario selecciona una tarea en el `TaskManager`.
2. **Carga de Resumen**: Se busca el fichero Markdown correspondiente en `.codelab/contexts/`.
3. **Inyección en Prompt**: El contenido se concatena al prompt enviado al backend (`server.py`).
4. **Auto-actualización**: Tras cada interacción relevante, se solicita a la IA que actualice el resumen del contexto mediante `updateContextWithAI()`.

## 3. Lógica del Backend (Orquestación de IA)
Implementado en [server.py](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/backend/server.py).

### Características Técnicas:
- **FastAPI Endpoint**: `@app.post("/api/generate")` recibe el prompt, historial y contexto.
- **Prompt Engineering**: Define un System Prompt estricto (Personalidad, Reglas Críticas, Formatos de Código).
- **Formatos de Respuesta**: Fuerza a la IA a incluir `[[NEXT_ACTION:{...}]]` al final de cada mensaje para habilitar botones interactivos.
- **Manejo de Errores Críticos**: Captura fallos de ejecución (como `IndentationError`) y genera instrucciones de reparación automáticas.

## 4. Persistencia del Proyecto
El índice del proyecto se guarda en `project_index.json`.
- **Estructura**: `Task { id, title, status, chats: ChatSession[], subtasks: Task[] }`.
- **Chats**: Cada sesión mantiene su propio historial de mensajes (`Message { role, content, model, timestamp }`).
