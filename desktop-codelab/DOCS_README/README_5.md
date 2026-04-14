# Gestión de Proyectos, Tareas y Sesiones

Este documento detalla la lógica funcional y técnica detrás de la organización del trabajo en **AI Code Lab**.

## 1. Jerarquía de Tareas y Subtareas
La aplicación utiliza un modelo de datos recursivo para permitir una organización infinita.

### Modelo de Datos (Task)
Definido en [TaskManager.tsx](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/src/components/TaskManager.tsx):
- `id`: String único generado aleatoriamente.
- `title`: Nombre descriptivo de la tarea.
- `status`: Estado actual (`todo`, `in-progress`, `done`).
- `subtasks`: Array de objetos `Task` (recursividad).
- `chats`: Lista de sesiones de conversación asociadas exclusivamente a esta tarea.
- `isExpanded`: Estado visual para la UI.

### Operaciones Funcionales:
- **Creación**: Las tareas raíz se crean desde el input superior del `TaskManager`. Las subtareas se crean pulsando el icono `CornerDownRight` de una tarea existente.
- **Reorganización (Drag & Drop)**: Implementado mediante la API nativa de HTML5 Drag and Drop. Se puede arrastrar una tarea sobre otra para convertirla en subtarea, o al fondo del panel para devolverla a la raíz.
- **Estados**: El clic en el icono de círculo/check alterna entre los tres estados, cambiando visualmente el color y aplicando `line-through` al completar.

## 2. Sesiones de Chat y Usuarios
Actualmente, la aplicación es **monousuario** y local, centrada en la privacidad y el control total del desarrollador.

### Sesiones de Chat (ChatSession)
- Cada tarea puede tener múltiples chats independientes. Esto permite separar, por ejemplo, "Refactorización de UI" de "Corrección de Bugs" dentro de la misma tarea.
- **Persistencia**: Los mensajes se guardan en el historial de la sesión (`messages: Message[]`).
- **Exportación**: El botón de "Documento" en la lista de chats permite volcar toda la conversación al editor principal para su edición o guardado manual.

## 3. Botones de Acción y Flujos
La interfaz está diseñada para minimizar la navegación manual.

### Acciones de Tarea:
- **BookOpen (Amarillo)**: Abre el fichero de contexto específico de la tarea (`.md`).
- **CornerDownRight (Azul)**: Despliega el input para añadir una subtarea.
- **Trash2 (Rojo)**: Elimina la tarea y todas sus subtareas/chats asociados (requiere confirmación).

### Acciones de Chat:
- **Plus**: Crea una nueva sesión de chat en blanco para la tarea activa.
- **MessageSquare**: Selecciona la sesión y carga el historial en el panel derecho.
- **FileText**: Exporta el historial de chat al editor Monaco.

## 4. Asociación de Contexto
Cada vez que se selecciona una tarea o un chat, el [ContextManager.ts](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/src/utils/ContextManager.ts) asegura que el asistente de IA reciba el resumen actualizado de esa unidad de trabajo específica, evitando que la IA "se pierda" en proyectos grandes.
