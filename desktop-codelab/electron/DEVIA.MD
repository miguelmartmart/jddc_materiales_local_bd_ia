# Directory: desktop-codelab/electron

> **Última actualización:** 11/05/2026 | **Versión:** 1.2.0

## Propósito

Proceso principal de Electron. Gestiona la ventana, los menús, los handlers IPC (sistema de archivos, shell) y el arranque del backend Python.

## Contenido

### `main.ts`
- Crea y gestiona la ventana principal de la aplicación.
- Carga el frontend React (dev server en desarrollo, `dist/` en producción).
- Arranca `backend/server.py` automáticamente como proceso hijo al iniciar.
- **IPC Handlers registrados:**
  - `fs:readDir` — lista contenido de un directorio
  - `fs:readFile` — lee un fichero como texto
  - `fs:writeFile` — escribe un fichero en disco (crea directorios intermedios si es necesario)
  - `shell:execute` — ejecuta un comando en `powershell.exe` (con confirmación de seguridad)
  - `dialog:openFolder` — abre el explorador nativo de carpetas
- Gestiona el ciclo de vida: `ready`, `window-all-closed`, `before-quit` (termina el proceso Python hijo).

### `preload.ts`
- Bridge seguro entre el proceso de renderizado (React) y el proceso principal.
- Expone `window.electronAPI` con las funciones IPC tipadas.
- Seguridad: `contextIsolation: true`, `nodeIntegration: false` — el renderer no tiene acceso directo a Node.js.

## Seguridad

- `contextIsolation: true` — el código React no puede acceder a APIs de Node.js directamente.
- Todos los accesos al sistema de archivos y shell pasan por IPC handlers validados.
- `shell:execute` muestra un diálogo de confirmación nativo antes de ejecutar cualquier comando PowerShell.
