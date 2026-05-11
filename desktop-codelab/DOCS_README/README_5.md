# Gestión de Proyectos, Tareas y Sesiones

Este documento detalla la lógica funcional y técnica detrás de la organización del trabajo en **AI Code Lab** (v1.2.0).

## 1. Jerarquía de Tareas y Subtareas

La aplicación usa un modelo de datos recursivo para organización flexible de proyectos.

### Modelo de Datos (Task)
Definido en [src/components/TaskManager.tsx](../src/components/TaskManager.tsx):

```typescript
interface Task {
  id: string;           // Único, generado aleatoriamente
  title: string;        // Nombre descriptivo
  status: 'todo' | 'in-progress' | 'done';
  subtasks: Task[];     // Recursivo — permite anidamiento infinito
  chats: ChatSession[]; // Sesiones de chat exclusivas de esta tarea
  isExpanded: boolean;  // Estado visual (no persistido en AI context)
}
```

### Operaciones Funcionales
- **Creación**: tareas raíz desde el input superior del `TaskManager`. Subtareas con el icono `CornerDownRight`.
- **Reorganización (Drag & Drop)**: API nativa HTML5. Arrastrar sobre otra tarea la convierte en subtarea; arrastrar al fondo la devuelve a la raíz.
- **Estados**: clic en el icono de estado alterna `todo → in-progress → done`. El estado `done` aplica `line-through` al título.
- **Eliminación**: icono `Trash2` requiere confirmación antes de borrar la tarea y todos sus chats y subtareas.

## 2. Sesiones de Chat

La aplicación es **monousuario y local** — sin sincronización en la nube, sin autenticación.

### Modelo ChatSession
```typescript
interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  model?: string;      // 'jddcia-qwen3-30b-ip' para respuestas IA
  timestamp: number;
}
```

### Características
- Cada tarea puede tener **múltiples chats independientes** (ej. "Refactorización UI" vs "Fix bug login").
- El historial completo de cada chat se envía al modelo como contexto de conversación.
- Los mensajes de tipo `system` (resultados de ejecución, errores) son visibles en el hilo y los recibe la IA.

## 3. Botones de Acción por Contexto

### Acciones de Tarea
- **BookOpen (Amarillo)**: Abre el fichero de contexto Markdown de la tarea (`.codelab/contexts/task_<id>.md`).
- **CornerDownRight (Azul)**: Despliega input para añadir subtarea.
- **Trash2 (Rojo)**: Elimina la tarea y todo su contenido (requiere confirmación).

### Acciones de Chat
- **Plus**: Crea nueva sesión de chat en blanco para la tarea activa.
- **MessageSquare**: Selecciona la sesión y carga su historial en el panel derecho.
- **FileText**: Exporta el historial de chat al editor Monaco como texto plano.

## 4. Asociación de Contexto IA

Cuando el usuario selecciona una tarea o chat, `ContextManager` carga automáticamente el resumen correspondiente y lo inyecta en el `PhaseContext.task_context`. La IA recibe ese resumen en todas las consultas de esa sesión, evitando perder el hilo en proyectos grandes.

### Actualización Automática
Tras cada respuesta relevante de la IA, `updateContextWithAI()` solicita a Qwen3 que actualice el resumen de la tarea con la nueva información del intercambio. Si la actualización falla (IA ocupada), el chat continúa sin interrupción.

## 5. Persistencia

- **Índice del proyecto**: `.codelab/project_index.json` — árbol completo de tareas serializado.
- **Contextos de tarea**: `.codelab/contexts/task_<id>.md` — resumen Markdown por tarea.
- **Contextos de chat**: `.codelab/contexts/chat_<id>.md` — resumen Markdown por chat.
- **Sin base de datos**: todo en ficheros locales, garantía de privacidad y acceso offline.
