# DEVIA FRONTEND CONTEXT
# Chat web UI — conecta con el backend DEVIA en puerto 8001.

```json
{
  "module": "frontend",
  "description": "Interfaz web del chat IA DEVIA. HTML/JS estático servido por FastAPI.",
  "last_updated": "03/07/2026",

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

  "db_mode_selector": {
    "description": "Selector de modo de BD en la barra del chat. Permite elegir entre BD Real, Simulada o Sin BD sin recargar la página.",
    "element_id": "chat-db-mode",
    "badge_id": "chat-db-mode-badge",
    "options": [
      { "value": "real",      "label": "🔥 BD Real",    "badge_color": "green"  },
      { "value": "simulator", "label": "🎭 Simulada",   "badge_color": "amber"  },
      { "value": "no_db",     "label": "💬 Sin BD",     "badge_color": "slate"  }
    ],
    "wire_js": "frontend/assets/js/modules/chat.js — sendMessage() lee #chat-db-mode y envía db_mode en el body del POST /api/chat/send",
    "backend_field": "db_mode en ChatRequest → service.py resuelve la cadena de fallback",
    "commit": "b7b9635 (03/07/2026)"
  },

  "responsive_ux": {
    "description": "Chat completamente responsivo con sidebar colapsable y modo pantalla completa.",
    "fullscreen_button": "⛶ — toggle position:fixed; inset:0. ESC para salir.",
    "sidebar_toggle": "btn-toggle-history — añade/quita clase .collapsed en #chat-history-sidebar",
    "mobile_breakpoint": "@media (max-width:640px) — sidebar oculto, labels ocultos, toolbar compacto",
    "layout": "#chat-outer llena viewport height; #chat-main ocupa espacio restante con flex",
    "commit": "b7b9635 (03/07/2026)"
  },

  "changelog": [
    {
      "date": "03/07/2026",
      "commit": "b7b9635",
      "changes": [
        "Selector #chat-db-mode (Real/Simulada/Sin BD) con badge de color en tiempo real",
        "Layout responsivo: #chat-outer flex-col, sidebar colapsable, toolbar wrappable",
        "Botón ⛶ fullscreen (position:fixed; inset:0) + ESC para salir",
        "Mobile breakpoint 640px: sidebar y labels ocultos automáticamente"
      ]
    },
    {
      "date": "03/07/2026",
      "commit": "51d0234",
      "changes": [
        "Fix error 400 chat IA: max_tokens clamp en jddcia_provider.py",
        "config.json: lan_model_max_tokens=2048, lan_model_context_limit=4096",
        "Router /api/database/tables devuelve 200+warning en vez de 500 cuando Firebird no disponible"
      ]
    },
    {
      "date": "03/07/2026",
      "commit": "d08370b",
      "changes": [
        "metadata_builder: /tables devuelve 200 con lista vacía cuando Firebird no alcanzable",
        "metadata_builder.js: toast de advertencia en vez de error bloqueante"
      ]
    },
    {
      "date": "03/07/2026",
      "commit": "2d1db83",
      "changes": [
        "marked.min.js: CDN → local (bloqueado por Tracking Prevention del navegador)",
        "database_config.js: degradación graceful cuando /tables devuelve vacío"
      ]
    }
  ],

  "related_devia": [
    "bots/interjddcia/DEVIA.MD (documentación principal)",
    "frontend/assets/js/modules/DEVIA.MD (módulos JS)",
    "backend/modules/chat/DEVIA.MD (chat service)"
  ]
}
```
