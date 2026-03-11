# DEVIA DESKTOP CODELAB CONTEXT
# Editor de código con IA — Electron app, puerto 3000.

```json
{
  "module": "desktop-codelab",
  "description": "Editor de código con IA integrada. App Electron (React + Monaco Editor).",
  "last_updated": "03/03/2026",

  "ports": {
    "electron_app": 3000,
    "backend_devia": 8001
  },

  "ai_mode_actual": {
    "mode": "LOCAL_ONLY",
    "ai_local_only": true,
    "model": "Qwen3 VL 30B @ 192.168.0.36",
    "note": "Comparte el mismo backend DEVIA (puerto 8001). El fallback multi-modelo está DESHABILITADO."
  },

  "arranque": {
    "script": "ARRANCAR_DEVIA.bat opción 2 (Backend + CodeLab) o opción 3 (solo CodeLab)",
    "note": "El CodeLab requiere que el backend DEVIA esté corriendo en puerto 8001"
  },

  "related_devia": [
    "bots/interjddcia/DEVIA.MD (documentación principal)"
  ]
}
```
