# Interfaz de Usuario y Experiencia (UI/UX)

Este documento describe la capa visual de **AI Code Lab** (v1.2.0): paneles, componentes y flujos de usuario.

## 1. Layout y Distribución de Pantalla

La aplicación utiliza un diseño de **Paneles Colapsables** con Flexbox para maximizar el área de trabajo.

### Estructura de Paneles (De izquierda a derecha)

1. **Sidebar Izquierdo (250px–400px)**:
   - **Explorador de Archivos**: Árbol jerárquico de ficheros del proyecto (`rootDir`).
   - **TaskManager**: Panel inferior para la gestión de tareas, subtareas y chats.

2. **Área Central (Flexible)**:
   - **Editor de Código**: Monaco Editor occupando la mayor parte del espacio.
   - **Terminal (Panel Inferior)**: Salida de comandos PowerShell en tiempo real, colapsable.

3. **Sidebar Derecho (350px–500px)**:
   - **Chat de IA**: Conversación con Qwen3. Soporta Markdown y bloques de código interactivos.

## 2. Componentes de Interfaz y Botones

### Cabecera (Header)
- **CONTEXT**: Botón púrpura — abre el fichero de resumen Markdown de la tarea activa.
- **Selector de Modelo**: Muestra el modelo LAN activo (siempre Qwen3 VL 30B).
- **Deep Analysis**: Checkbox que activa el flag `deep_analysis` en el PhaseContext.

### Bloques de Código (`CodeBlock`)
- **SAVE**: Botón azul — persiste el bloque en el disco usando la ruta del comentario de cabecera.
- **RUN**: Botón verde — ejecuta el script en PowerShell.

### Botones de Acción del Chat (`[[NEXT_ACTION]]`)

Solo el **último mensaje del asistente** muestra botones activos. Los mensajes anteriores con `[[NEXT_ACTION]]` muestran "Acción superada" (badge gris).

| Tipo | Color | Label por defecto | Acción |
|------|-------|-------------------|--------|
| `run_command` | Verde esmeralda | "Ejecutar" | Ejecuta `content` en PowerShell |
| `browser` | Azul | "Abrir en navegador" | Abre `content` en el navegador |
| `confirm_plan` | Verde | "Continuar" | Confirma al asistente para el siguiente paso |
| `open_file` | Azul claro | "Abrir archivo" | Carga `content` en el editor Monaco |

Cada acción tiene un botón de **Cancelar** (gris/rojo) que envía `cancel_message` al chat.

### Mensajes [SYSTEM] en el Chat
Los resultados de ejecución, guardados de archivos y errores aparecen como mensajes de sistema
en el hilo de conversación con fondo diferenciado. La IA los recibe como contexto para auto-repararse.

## 3. Flujos de Usuario Detallados

### Flujo de Desarrollo (caso principal)
1. Usuario abre una carpeta (`rootDir`) con el explorador de archivos.
2. Crea una tarea en el TaskManager y un chat asociado.
3. Escribe en el chat: "Crea una app Flask que liste archivos".
4. La IA responde con:
   - Análisis previo (qué va a crear y por qué — fase `p01b_analysis_first`)
   - Árbol de carpetas propuesto (verificando que no existan ya — fase `p03_folders`)
   - Botón "Crear carpetas" (`run_command` con `New-Item`)
5. Usuario pulsa "Crear carpetas" → PowerShell crea la estructura → `[SYSTEM]` reporta el resultado.
6. IA propone el código → Usuario pulsa **Save** en el CodeBlock → `[SYSTEM]` confirma guardado.
7. IA propone ejecutar → Usuario pulsa botón "Ejecutar" → Terminal muestra resultado → `[SYSTEM]` reporta.
8. Si hay error, la IA lo recibe y propone corrección automáticamente.

### Flujo de Contexto
1. Usuario pulsa **CONTEXT** en el header.
2. Se abre el fichero `.codelab/contexts/task_<id>.md` en el editor.
3. Usuario puede editar el resumen manualmente.
4. En la siguiente consulta, la IA recibe ese resumen como `task_context`.

### Flujo de Tareas
1. Crear tarea raíz → Crear subtareas (icono `CornerDownRight`).
2. Drag & drop para reorganizar jerarquía.
3. Clic en icono de círculo alterna estados: `todo` → `in-progress` → `done`.
4. Cada tarea puede tener múltiples chats independientes (ej. "Refactor UI" vs "Fix bug login").

## 4. Características de Diseño

- **Tailwind CSS**: escala de colores consistente (gray, blue, green, red, purple).
- **Interactividad**: efectos `hover` en todos los botones y nodos del árbol de archivos.
- **Animaciones**: transiciones suaves en apertura/cierre de paneles, spinner de generación IA.
- **Seguridad**: confirmación nativa del sistema operativo antes de ejecutar cualquier comando PowerShell.
- **Robustez visual**: si `[[NEXT_ACTION]]` tiene JSON malformado, el parser de 3 capas lo recupera en silencio sin romper la UI.
