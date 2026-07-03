# DEVIA MODULE CONTEXT: ANALISTA BD
# Chat conversacional sobre BD simulada/real con procedencia completa (audit trail).

```json
{
  "module": "backend.modules.db_analyst",
  "description": "Chat analítico sobre BD. Cada respuesta incluye Provenance completa: SQL generado, tablas SIUO, datos brutos y tiempo de ejecución. Diseñado para trabajo con BD simulada, listo para cambiar a BD real solo con config.",
  "components": {
    "AnalystService": "Núcleo. Flujo: SIUO context → Qwen3 SQL → normalizar → ejecutar (SQLCorrector) → interpretar con <details> de justificación. Siempre devuelve (response_text, Provenance).",
    "AnalystSessionStore": "SQLite propio (backend/data/db_analyst_sessions.db). Guarda mensajes con provenance_json. Independiente de ChatHistoryService.",
    "Provenance": "Modelo Pydantic con: sql_generated, sql_executed, raw_results (max 50), tables_used, siuo_keywords, siuo_source, context_tokens, data_source, model_used, execution_time_ms.",
    "router.py": "Endpoints FastAPI. POST /chat devuelve AnalystChatResponse con Provenance. POST /chat/justify explica de dónde vienen los datos."
  },
  "reusos_clave": {
    "ContextRetriever": "SIUO índices en RAM — mismos que usa ChatService. Sin cambios.",
    "ModelFallbackOrchestrator": "Qwen3 LAN → Groq → Gemini. Sin cambios.",
    "FirebirdSQLNormalizer": "Correcciones deterministas SQL. Sin cambios.",
    "SQLCorrector.execute_with_correction": "Ejecución con reintentos y auto-corrección IA. Sin cambios.",
    "SimulatedFirebirdDriver": "Execute SQL contra SQLite (simulador). Sin cambios."
  },
  "diferencias_vs_chat_service": {
    "procedencia": "Siempre devuelve Provenance — no es opcional.",
    "sin_imagenes": "No soporta imágenes ni voz. Solo análisis de BD.",
    "sin_confirmacion": "Sin flujo de confirmación de datos — transparencia total.",
    "justify_endpoint": "POST /chat/justify: replay de la procedencia guardada para explicar la evidencia.",
    "session_store_propio": "BD SQLite separada. No interfiere con chat_history.db.",
    "diseñado_para_simulador": "Funciona con BD simulada por defecto. Cambiar a real: desactivar simulador en config.json."
  },
  "flujo_proceso": [
    "1. ContextRetriever.get_context(pregunta) → db_context + meta SIUO",
    "2. _build_system_prompt() → incluye historial + esquema + nota simulador",
    "3. orchestrator.execute_with_fallback() → SQL generado por Qwen3",
    "4. re.findall(```sql…```) → extraer bloque SQL más completo",
    "5. FirebirdSQLNormalizer.normalize() → correcciones deterministas",
    "6. SQLCorrector.execute_with_correction() → ejecutar con hasta 3 reintentos",
    "7. orchestrator.execute_with_fallback() → interpretar resultados con <details>",
    "8. Devolver (final_text, Provenance)"
  ],
  "endpoints": {
    "GET  /api/db-analyst/status":         "Estado: fuente de datos, SIUO listo, simulador",
    "POST /api/db-analyst/session/new":    "Nueva sesión",
    "GET  /api/db-analyst/sessions":       "Listar sesiones (limit=50)",
    "GET  /api/db-analyst/session/{id}":   "Mensajes + provenance de una sesión",
    "DELETE /api/db-analyst/session/{id}": "Eliminar sesión",
    "POST /api/db-analyst/chat":           "Pregunta → respuesta + Provenance completa",
    "POST /api/db-analyst/chat/justify":   "Justificar respuesta anterior con datos brutos"
  },
  "cuando_usar_real_bd": "Desactivar simulador: POST /api/db-simulator/config {enabled: false}. El módulo usará FirebirdDriver automáticamente. Sin cambios de código.",
  "tests": {
    "unit": "tests/unit/test_db_analyst.py",
    "run": ".venv/Scripts/pytest tests/unit/test_db_analyst.py -v"
  },
  "last_updated": "28/05/2026"
}
```
