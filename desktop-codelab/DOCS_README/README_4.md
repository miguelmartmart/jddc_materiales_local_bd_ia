# Robustez, Escalabilidad y Mejores Prácticas

Este documento detalla los principios de diseño de software aplicados en **AI Code Lab**, garantizando su mantenibilidad y capacidad de crecimiento.

## 1. Abstracción y Desacoplamiento
La aplicación sigue el principio de **Separación de Responsabilidades**:

- **Motor de IA**: Desacoplado mediante una interfaz de proveedor común en el backend. Esto permite añadir nuevos modelos (Anthropic, DeepSeek, etc.) sin tocar la lógica de negocio central.
- **Acceso a Disco**: Abstraído a través del proceso `Main` de Electron. El frontend nunca toca el disco directamente, garantizando la seguridad y estabilidad de la app.
- **UI Atómica**: Componentes como `TaskManager`, `CodeBlock` y `CollapsibleSection` son independientes y reutilizables.

## 2. Robustez y Tolerancia a Fallos
El sistema implementa múltiples capas de seguridad:

- **Auto-Guardado**: Antes de ejecutar cualquier script, el sistema persiste automáticamente el contenido del editor para evitar inconsistencias entre el código visual y el ejecutable.
- **Validación de Rutas**: Antes de la ejecución, se verifica la existencia de ficheros y carpetas, creando directorios automáticamente si faltan.
- **Sanitización de Código**: Se eliminan artefactos de Markdown (como backticks ```) de los bloques de código antes de guardarlos.
- **Corrección de Indentación**: Un normalizador específico para Python limpia las sangrías accidentales en la primera línea de los scripts, un error común en las respuestas de LLMs.

## 3. Escalabilidad del Proyecto
La aplicación está diseñada para manejar proyectos de gran tamaño mediante:

- **Jerarquía de Tareas**: Soporte para tareas y sub-tareas infinitamente anidadas, permitiendo organizar proyectos complejos.
- **Memoria por Tarea**: Cada tarea tiene su propio contexto aislado. El `ContextManager` asegura que al cambiar de tarea, el asistente "olvide" lo irrelevante y cargue solo la información pertinente.
- **Arquitectura de Micro-Frontends (Conceptual)**: El uso de componentes aislados en React facilita la expansión de funcionalidades (ej. añadir un panel de Base de Datos) sin afectar al resto de la UI.

## 4. Orden y Estructura de Directorios
El proyecto sigue una estructura estricta y predecible:

- `electron/`: Lógica de la plataforma de escritorio.
- `backend/`: API de orquestación de IA y configuración de modelos.
- `src/`:
  - `components/`: Bloques de construcción visual.
  - `utils/`: Lógica compartida y gestores de estado (ContextManager).
- `.codelab/`: Datos persistentes del proyecto (índices, contextos, logs).

## 5. Accesibilidad y Usabilidad
- **Atajos Nativo**: Integración con los diálogos estándar del sistema operativo.
- **Feedback de Error Detallado**: Los errores de ejecución se reportan íntegramente a la IA para que pueda proponer una solución inmediata, reduciendo el "ciclo de corrección" del usuario.
