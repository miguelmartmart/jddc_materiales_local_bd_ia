# Historial de Conversación y Persistencia de Datos

Este documento describe cómo se almacenan, estructuran y persisten las interacciones entre el usuario y la IA en **AI Code Lab**.

## 1. Modelo de Persistencia Local
La aplicación utiliza un sistema de ficheros local para garantizar la privacidad y el acceso offline. No se requieren bases de datos externas.

### Estructura de Datos (JSON)
El estado completo del proyecto se centraliza en `.codelab/project_index.json`:
- **Root Tasks**: Array de tareas principales.
- **Chats**: Cada tarea contiene un array de sesiones de chat.
- **Messages**: Cada chat contiene el historial completo de mensajes.

```json
{
  "id": "task_123",
  "title": "Implementar Login",
  "chats": [
    {
      "id": "chat_456",
      "title": "Configuración inicial",
      "messages": [
        { "role": "user", "content": "Hola", "timestamp": 1710768000 },
        { "role": "assistant", "content": "En qué puedo ayudarte?", "timestamp": 1710768005 }
      ]
    }
  ]
}
```

## 2. Gestión de Mensajes (submitMessage)
Implementado en [App.tsx](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/desktop-codelab/src/App.tsx).

### Flujo de Envío:
1. **Captura**: Se recibe el texto del usuario y se añade al estado `messages`.
2. **Historial Contextual**: Se recuperan los mensajes previos de la sesión activa para enviarlos al modelo de IA, permitiendo conversaciones con memoria de corto plazo.
3. **Roles**: 
   - `user`: Entrada directa del usuario.
   - `assistant`: Respuesta generada por la IA.
   - `system`: Mensajes automáticos del entorno (errores de terminal, avisos de guardado).

## 3. Historial de Sistema (Auto-Reporte)
Una característica única es el envío de resultados de ejecución a la IA.
- **Logs de Terminal**: Si un comando falla, el error se inyecta como un mensaje `system`.
- **Feedback Loop**: La IA recibe el `ERROR_OUTPUT` y automáticamente analiza la causa para proponer una corrección en su siguiente respuesta.

## 4. Exportación y Backup
- **Exportar Chat**: Permite volcar el historial completo a un fichero Markdown mediante el botón `FileText` en el TaskManager.
- **Context Files**: Los resúmenes generados por la IA en `.codelab/contexts/` actúan como un backup funcional del estado del proyecto, permitiendo que incluso si se pierde el historial de chat detallado, la IA pueda retomar el trabajo desde el último resumen optimizado.
