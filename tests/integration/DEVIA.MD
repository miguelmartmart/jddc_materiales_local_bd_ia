# DEVIA: tests/integration — Tests de Integración

```json
{
  "capa": "integration",
  "descripcion": "Tests con BD Firebird real + Qwen3 LAN. Sin mocks. Se saltan si los servicios no están disponibles.",
  "hereda_de": "tests/DEVIA.MD",

  "ficheros": {
    "conftest.py":          "Fixtures de integración (db_driver, qwen3_url, siuo_retriever)",
    "test_siuo_retriever.py": "ContextRetriever: carga índices SIUO y mapea conceptos a tablas",
    "test_chat_metaglass.py": "ChatService: preguntas reales desde MetaGlass (TTS, sin Markdown)",
    "test_chat_web.py":       "ChatService: preguntas reales desde cliente web (con Markdown)",
    "test_pagination_real.py":"Paginación con datos reales de BD Firebird"
  },

  "independencia": {
    "parametros": "Todos los parámetros vienen de tests/conftest.py → TestConfig → test.properties",
    "skip_automatico": "Si BD o Qwen3 no disponibles → SKIP (no FAIL). Cambiar SKIP_IF_UNAVAILABLE=false para forzar FAIL.",
    "sin_hardcode": "Ninguna IP, puerto, usuario o contraseña hardcodeada en los tests.",
    "portabilidad": "Cambiar test.properties → funciona en otro PC o con otra BD."
  },

  "requisitos": [
    "BD Firebird accesible (configurada en test.properties o .env)",
    "Qwen3 LAN accesible (autodetectado o configurado en test.properties)",
    "Índices SIUO generados (ejecutar deep_indexer_service.py primero)"
  ],

  "ejecutar": ".venv/Scripts/pytest tests/integration/ -v -s --tb=short"
}
```
