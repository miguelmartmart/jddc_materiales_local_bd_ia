{
  "module": "backend.modules.db_explorer.metadata_builder",
  "description": "Módulo para construir db_metadata_optimized.json usando la IA local LAN. Analiza tablas Firebird y genera metadatos semánticos para que el chat IA pueda crear consultas SQL correctas.",
  "last_updated": "03/03/2026",
  "version": "1.0.0",

  "security": {
    "principle": "DATOS SOLO A IA LOCAL LAN. NUNCA a internet.",
    "ai_urls_from": "settings.JDDCIA_BASE_URL_FALLBACK (IP directa) y settings.JDDCIA_BASE_URL (mDNS)",
    "auth_from": "settings.JDDCIA_API_KEY (Basic Auth Base64)",
    "model_from": "settings.JDDCIA_MODEL o LocalAIParams.MODEL_DEFAULT ('unified-main')",
    "sensitive_columns": "Definidas en PrivacyConfig.SENSITIVE_COLUMNS (constants.py) — excluidas de muestras",
    "block_if_ai_unavailable": true
  },

  "flow": {
    "1_check_ai":    "Service → Qwen3 LAN: verifica disponibilidad antes de cualquier operación",
    "2_get_tables":  "Service → Firebird: lista tablas de usuario con estado de metadatos",
    "3_get_struct":  "Service → Firebird: columnas, tipos, PKs, FKs, conteo, muestra sin sensibles",
    "4_analyze_ai":  "Service → Qwen3 LAN: genera JSON de metadatos semánticos",
    "5_save":        "Service → db_metadata_optimized.json: persiste tras aprobación del usuario"
  },

  "files": {
    "constants.py":                  "Constantes del módulo (timeouts, privacidad, categorías, mensajes). Sin valores hardcodeados.",
    "metadata_builder_service.py":   "Lógica principal. Usa settings para IPs/credenciales.",
    "metadata_builder_router.py":    "Endpoints FastAPI. Independiente de router.py existente.",
    "../../drivers/db/firebird_metadata_queries.py": "SQL de introspección Firebird (RDB$*).",
    "../../core/config/db_metadata_optimized.json":  "Archivo de salida — metadatos del chat IA."
  },

  "endpoints": {
    "GET  /api/metadata-builder/status":                  "Estado IA local + resumen metadatos",
    "GET  /api/metadata-builder/tables":                  "Lista tablas BD con estado metadatos",
    "GET  /api/metadata-builder/tables/{name}":           "Estructura real de una tabla",
    "POST /api/metadata-builder/tables/{name}/analyze":   "Analiza tabla con IA local → JSON",
    "POST /api/metadata-builder/tables/{name}/save":      "Guarda metadatos aprobados",
    "GET  /api/metadata-builder/tables/{name}/metadata":  "Metadatos actuales de una tabla",
    "DELETE /api/metadata-builder/tables/{name}/metadata": "Elimina metadatos de una tabla"
  },

  "independence": {
    "does_not_modify": ["router.py", "service.py", "chat/service.py", "db_metadata_optimized.json sin aprobación"],
    "only_adds": "Nuevo router registrado al final de main.py",
    "hot_reload": "Los cambios en db_metadata_optimized.json son inmediatos (metadata_manager los lee en cada petición)"
  },

  "configuration": {
    "change_ai_url":   "Editar .env → JDDCIA_BASE_URL_FALLBACK o JDDCIA_BASE_URL",
    "change_ai_model": "Añadir JDDCIA_MODEL=nuevo-modelo en .env",
    "change_timeouts": "Editar constants.py → LocalAITimeouts.CONNECT / READ",
    "add_sensitive_col": "Editar constants.py → PrivacyConfig.SENSITIVE_COLUMNS"
  },

  "traces": {
    "format": "[METADATA_BUILDER][PASO] EMISOR → RECEPTOR: mensaje",
    "prefixes": "Definidos en MetadataBuilderLog (constants.py)",
    "data_logged": "Nombres de tablas, conteos, columnas. NUNCA datos de negocio."
  },

  "tests": {
    "file": "tests/test_metadata_builder.py",
    "run":  "cd bots/interjddcia && .venv/Scripts/pytest tests/test_metadata_builder.py -v"
  },

  "frontend": {
    "js":  "frontend/assets/js/modules/metadata_builder.js",
    "tab": "Pestaña 'Constructor BD' en el menú principal de index.html"
  }
}