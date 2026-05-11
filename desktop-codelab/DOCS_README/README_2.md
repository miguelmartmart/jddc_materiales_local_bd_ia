# Lógica de Negocio y Gestión de Estados

Este documento detalla el motor funcional de **AI Code Lab** (v1.2.0): comunicación inter-proceso, motor de contexto, backend IA y el sistema de botones de acción.

## 1. Comunicación Inter-Proceso (IPC)

El sistema usa el puente seguro definido en [electron/preload.ts](../electron/preload.ts).

### Métodos Expuestos (`window.electronAPI`)
- **`fs:readDir` / `fs:readFile` / `fs:writeFile`**: Abstracciones asíncronas para el sistema de archivos de Windows.
- **`shell:execute`**: Ejecución de comandos en `powershell.exe`. Incluye diálogo de confirmación de seguridad antes de cada ejecución.
- **`dialog:openFolder`**: Explorador nativo para definir el `rootDir` del proyecto.

## 2. Motor de Contexto y Memoria

[src/utils/ContextManager.ts](../src/utils/ContextManager.ts) implementa un patrón Singleton para la gestión de memoria a largo plazo.

### Flujo de Trabajo del Contexto
1. **Selección de Tarea**: el usuario selecciona una tarea en el `TaskManager`.
2. **Carga de Resumen**: se busca el fichero Markdown en `.codelab/contexts/task_<id>.md`.
3. **Inyección en Prompt**: el contenido se concatena como `task_context` en el `PhaseContext`.
4. **Auto-actualización**: tras cada interacción relevante, `updateContextWithAI()` solicita a Qwen3 que actualice el resumen.
5. **Fail-safe**: si la actualización falla (IA ocupada, timeout), el chat continúa sin interrupciones.

## 3. Mensajes de Sistema (`systemReports.ts`)

[src/utils/systemReports.ts](../src/utils/systemReports.ts) genera mensajes estructurados de tipo `[SYSTEM]` que se inyectan automáticamente al historial del chat. Estos mensajes son visibles para la IA en su contexto de conversación.

### Tipos de Mensajes [SYSTEM]
- **Resultado de ejecución de comando**: `stdout`, `stderr`, código de salida
- **Guardado de archivo**: ruta donde se guardó, si fue nuevo o actualizado
- **Error de ejecución**: error completo para que la IA proponga auto-reparación
- **Resultado de acción cancelada**: el usuario declinó una acción sugerida

Este sistema forma el **feedback loop** que permite a la IA detectar errores y auto-corregirse.

## 4. Lógica del Backend (Orquestación de IA)

Implementado en [backend/server.py](../backend/server.py).

### Endpoint principal: `POST /api/generate`

**Entrada:**
```json
{
  "model_id": "jddcia-qwen3-30b-ip",
  "prompt": "...",
  "messages": [{"role": "user", "content": "..."}, ...],
  "code_context": "...",
  "root_dir": "C:/Users/...",
  "deep_analysis": false
}
```

**Proceso:**
1. Construye `PhaseContext` con `project_path`, `folders_context` (carpetas existentes), `task_context`, `deep_analysis`, `current_date`.
2. `PromptBuilder.build(ctx)` → system prompt (~6110 chars, 17 fases).
3. `_try_lan_model()` → llama a Qwen3 LAN con retry automático.
4. `_fix_next_action()` → repara JSON malformado en `[[NEXT_ACTION]]`.

**Salida:**
```json
{
  "response": "Texto de la IA con posible [[NEXT_ACTION:{...}]]",
  "model": "jddcia-qwen3-30b-ip"
}
```

## 5. Sistema [[NEXT_ACTION]]

### Generación (backend)
La fase `p11_action_buttons` instruye a la IA a generar `[[NEXT_ACTION:{...}]]` al final de respuestas que requieren acción del usuario.

### Parsing (frontend — `nextActionParser.ts`)
```typescript
parseNextAction(rawContent: string): ParseResult
// Capa 1: JSON.parse() directo
// Capa 2: extracción de primer { } balanceado
// Capa 3: corrección backslashes Windows + reintentos 1 y 2
// → { action: NextAction | null, error: string | null }
```

### Renderizado (App.tsx)
- Solo el **último mensaje del asistente** (`isLastAssistant = true`) muestra botones activos.
- Mensajes anteriores muestran "Acción superada" si tenían `[[NEXT_ACTION]]`.
- Si `action.type` no está en `EXECUTABLE_TYPES`, no se renderiza botón.

### Tipos de acción
| `type` | Comportamiento |
|--------|---------------|
| `run_command` | Ejecuta `content` en PowerShell vía `shell:execute` |
| `browser` | Abre `content` en el navegador por defecto |
| `confirm_plan` | Envía el `cancel_message` o un mensaje de confirmación al chat |
| `open_file` | Abre `content` en el editor Monaco |

## 6. Persistencia del Proyecto

El índice del proyecto se guarda en `.codelab/project_index.json`.

```typescript
interface Task {
  id: string;
  title: string;
  status: 'todo' | 'in-progress' | 'done';
  subtasks: Task[];
  chats: ChatSession[];
  isExpanded: boolean;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  model?: string;
  timestamp: number;
}
```
