# Interfaz de Usuario y Experiencia (UI/UX)

Este documento describe detalladamente la capa visual de **AI Code Lab**, sus componentes, distribución y principios de diseño.

## 1. Layout y Distribución de Pantalla
La aplicación utiliza un diseño de **Paneles Colapsables** con Flexbox y CSS Grid para maximizar el área de trabajo.

### Estructura de Paneles (De izquierda a derecha):
1. **Sidebar Izquierdo (250px - 400px)**:
   - **Explorador de Archivos**: Árbol jerárquico de ficheros del proyecto.
   - **TaskManager**: Panel inferior para la gestión de tareas y chats.
2. **Área Central (Flexible)**:
   - **Editor de Código**: Editor Monaco ocupando la mayor parte del espacio.
   - **Terminal (Panel Inferior)**: Salida de comandos en tiempo real, colapsable.
3. **Sidebar Derecho (350px - 500px)**:
   - **Chat de IA**: Interfaz de conversación con soporte para Markdown y bloques de código interactivos.

## 2. Componentes de Interfaz y Botones
La aplicación cuenta con botones dinámicos basados en el estado:

### Cabecera (Header):
- **CONTEXT**: Botón púrpura para abrir el fichero de resumen optimizado de la tarea activa.
- **Selector de Modelo**: Dropdown para cambiar entre Gemini 2.0, 1.5 Pro, GPT-4o, etc.
- **Botones de Sincronización**: Recarga de modelos y descubrimiento de nuevos proveedores.

### Bloques de Código (CodeBlock.tsx):
- **SAVE**: Botón azul para persistir cambios en el disco.
- **RUN**: Botón verde para ejecutar el script actual.

### Acciones del Chat (Next Actions):
- **Ejecutar Pasos (Verde Esmeralda)**: 
  - **Lógica**: Automatiza el guardado de los archivos modificados en el mensaje de la IA y lanza el comando de ejecución (`python`, `node`, `npm`, etc.) en la terminal.
  - **Ubicación**: Aparece al final de los mensajes del asistente que contienen bloques de código ejecutables.
- **Abrir en Navegador (Azul)**: 
  - **Lógica**: Llama a `handleOpenInBrowser` para abrir ficheros HTML generados por la IA en el navegador predeterminado del sistema.
- **Continuar (Verde)**: Botón genérico para solicitar el siguiente paso a la IA si no hay una acción específica detectada.
- **Cancelar (Gris/Rojo)**: Detiene la ejecución sugerida y solicita a la IA que espere nuevas instrucciones.

## 3. Flujos de Usuario Detallados
1. **Flujo de Tarea**: Crear Tarea > Seleccionar Tarea > Crear Chat > Preguntar a la IA.
2. **Flujo de Desarrollo**: IA propone código > Usuario pulsa **Save** (o **Ejecutar Pasos**) > Terminal muestra resultado > IA recibe reporte de ejecución > IA propone corrección o siguiente paso.
3. **Flujo de Contexto**: Usuario pulsa **CONTEXT** en el header > Se abre el fichero Markdown de resumen > Usuario edita el resumen manualmente si lo desea > IA usa ese resumen como "memoria" en la siguiente consulta.

## 4. Características de Diseño (Tailwind CSS)
- **Consistencia**: Uso de la escala de colores de Tailwind (gray, blue, green, red, purple).
- **Interactividad**: Efectos `hover` en todos los botones y nodos del árbol de archivos.
- **Animaciones**: Transiciones suaves en la apertura/cierre de paneles y el spinner de generación de IA.
