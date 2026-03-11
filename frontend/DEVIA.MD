# DEVIA FRONTEND CONTEXT
# Chat web UI — conecta con el backend DEVIA en puerto 8001.

```json
{
  "module": "frontend",
  "description": "Interfaz web del chat IA DEVIA. HTML/JS estático servido por FastAPI.",
  "last_updated": "03/03/2026",

  "backend_connection": {
    "url": "http://localhost:8001",
    "endpoints": {
      "chat": "POST /api/chat/send",
      "config": "GET/POST /api/chat/config",
      "health": "GET /health"
    }
  },

  "ai_mode_actual": {
    "mode": "LOCAL_ONLY",
    "ai_local_only": true,
    "model": "Qwen3 VL 30B @ 192.168.0.36",
    "note": "El fallback multi-modelo está DESHABILITADO. Solo usa la IA local LAN."
  },

  "arranque": {
    "script": "ARRANCAR_DEVIA.bat (doble clic en bots/interjddcia/)",
    "url_local": "http://localhost:8001",
    "url_red": "http://192.168.0.38:8001"
  },

  "related_devia": [
    "bots/interjddcia/DEVIA.MD (documentación principal)",
    "frontend/assets/js/modules/DEVIA.MD (módulos JS)"
  ]
}
```
