# Historial de Conversación y Persistencia de Datos

Este documento describe cómo se almacenan, estructuran y persisten las interacciones en **AI Code Lab** (v1.2.0).

## 1. Modelo de Persistencia Local

La aplicación usa exclusivamente ficheros locales — sin bases de datos externas, sin cloud.

### Estructura del índice principal (`.codelab/project_index.json`)

```json
[
  {
    "id": "task_123",
    "title": "App Flask de archivos",
    "status": "in-progress",
    "subtasks": [],
    "chats": [
      {
        "id": "chat_456",
        "title": "Sesión inicial",
        "messages": [
          { "role": "user", "content": "Crea la estructura", "timestamp": 1746960000 },
          { "role": "assistant", "content": "...", "model": "jddcia-qwen3-30b-ip", "timestamp": 1746960005 },
          { "role": "system", "content": "[SYSTEM] Comando ejecutado: exit 0\nstdout: ...", "timestamp": 1746960010 }
        ]
      }
    ]
  }
]
```

## 2. Gestión de Mensajes (`submitMessage` en App.tsx)

### Flujo de Envío
1. El usuario escribe y pulsa Enter (o el botón de envío).
2. El mensaje se añade al estado local con `role: 'user'`.
3. Se construye el historial contextual (todos los mensajes previos del chat).
4. Se llama a `api.generateCode()` → `POST /api/generate` con el historial completo.
5. La respuesta se añade con `role: 'assistant'`.
6. `parseNextAction()` detecta `[[NEXT_ACTION]]` y renderiza el botón correspondiente.

### Roles de Mensaje
- **`user`**: Entrada directa del usuario.
- **`assistant`**: Respuesta generada por Qwen3 LAN. Puede contener `[[NEXT_ACTION:{...}]]`.
- **`system`**: Mensajes automáticos del entorno generados por `systemReports.ts`.

## 3. Mensajes de Sistema (`systemReports.ts`)

`systemReports.ts` es una fábrica de mensajes `[SYSTEM]` estructurados que se inyectan al historial automáticamente. Son visibles en el chat con fondo diferenciado y la IA los recibe como contexto.

### Tipos de Reportes

**Resultado de ejecución de comando:**
```
[SYSTEM] Comando ejecutado: python main.py
Exit code: 0
stdout:
  Hello from Flask! Running on http://127.0.0.1:5000
```

**Error de ejecución:**
```
[SYSTEM] Error al ejecutar: python main.py
Exit code: 1
stderr:
  ModuleNotFoundError: No module named 'flask'
```

**Guardado de archivo:**
```
[SYSTEM] Archivo guardado: C:/proyectos/app/main.py (nuevo)
```

**Acción cancelada:**
```
[SYSTEM] El usuario canceló la acción: Crear carpetas
```

### Feedback Loop
La IA recibe estos mensajes como parte del historial de conversación. Si hay un error, en su siguiente respuesta puede proponer auto-reparación (ej. `pip install flask`) sin que el usuario tenga que describir el problema.

## 4. Exportación y Backup

- **Exportar Chat**: botón `FileText` en el TaskManager vuelca el historial completo al editor Monaco como texto plano para edición o guardado manual.
- **Context Files**: los resúmenes en `.codelab/contexts/` actúan como backup funcional del estado del proyecto. Si se pierde el historial de chat detallado, la IA puede retomar desde el último resumen.
- **Sin sincronización remota**: todos los datos permanecen en el disco local del usuario.

## 5. Ciclo de Vida de un Chat

```
Crear chat → Escribir mensaje → [IA responde + [[NEXT_ACTION]]]
    │
    ├─ Usuario acepta acción → PowerShell ejecuta → [SYSTEM] resultado
    │       │
    │       └─ IA recibe resultado → propone siguiente paso
    │
    ├─ Usuario cancela acción → [SYSTEM] cancelación → IA espera instrucciones
    │
    └─ Usuario escribe nuevo mensaje → ciclo se repite
```

El historial crece hasta que el contexto de 4096 tokens se acerca al límite. El backend gestiona esto reduciendo automáticamente `max_tokens` para siempre obtener alguna respuesta.
