# Guía de Testing, Calidad y Validación

Este documento detalla las estrategias de validación y los mecanismos de control de calidad implementados en **AI Code Lab**.

## 1. Validación de Código Generado (IA)
A diferencia de los editores convencionales, **AI Code Lab** aplica una capa de validación dinámica sobre el código que la IA propone.

### Mecanismos de Robustez:
- **Sanitización de Bloques**: El sistema detecta automáticamente bloques mal formados (ej. ```// ruta.py) y extrae el lenguaje y la ruta real mediante expresiones regulares robustas.
- **Normalización de Indentación (Python)**: Implementado en `handleSaveFile`, elimina automáticamente sangrías accidentales en la primera línea de scripts Python, un error común en LLMs.
- **Validación de Rutas (Pre-ejecución)**: Antes de correr un comando como `python script.py`, el sistema verifica si `script.py` existe físicamente en el disco. Si no, alerta al usuario en lugar de lanzar un error genérico de consola.

## 2. Testing de Integración (Electron + IPC)
La comunicación entre procesos se valida mediante:
- **Puente Seguro**: El fichero [preload.ts](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/electron/preload.ts) actúa como la única vía de comunicación, validada mediante TypeScript para asegurar que solo se envían tipos de datos permitidos.
- **Diálogos de Confirmación**: Todas las ejecuciones de comandos en la terminal (`shell:execute`) requieren una confirmación manual del usuario, actuando como un "test de seguridad" en tiempo real.

## 3. Calidad de la Memoria (ContextManager)
El sistema valida la calidad de la documentación generada por la IA:
- **Schema-Check**: Al actualizar contextos (`updateContextWithAI`), el sistema limpia los bloques de código y las cercas de Markdown adicionales para asegurar que el resumen sea un Markdown puro y procesable.
- **Deduplicación**: El `ContextManager` asegura que no se dupliquen entradas de ficheros en el índice del proyecto durante las actualizaciones automáticas.

## 4. Tests Manuales Recomendados (Replicación)
Para validar una nueva instalación de la aplicación, se recomiendan estos tests:
1. **Test de Guardado**: Escribir en el editor y pulsar `Ctrl+S`. Verificar que el archivo aparece en el explorador y en el disco.
2. **Test de Ejecución**: Crear un `test.py` con `print("Hola")`, guardarlo y pulsar **Run**. Verificar la salida en el panel de logs.
3. **Test de IA**: Enviar un mensaje y verificar que la respuesta incluye un bloque de código con su correspondiente botón **Save**.
4. **Test de Tareas**: Crear una tarea, una subtarea y un chat. Cerrar y volver a abrir la app para verificar la persistencia en `project_index.json`.

## 5. Escalabilidad Técnica
- **Separación de Concern**: La lógica de la terminal está aislada de la lógica del chat.
- **Manejo de Estados Complejos**: El uso de `setTasks` con actualizaciones in-place en el árbol recursivo asegura que la UI se mantenga sincronizada incluso con jerarquías profundas.
