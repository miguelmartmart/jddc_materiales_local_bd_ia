# DEVIA: tests/unit — Tests Unitarios

```json
{
  "capa": "unit",
  "descripcion": "Tests unitarios de DEVIA. Sin BD, sin IA, sin red. Rápidos (<1s cada uno).",
  "principio": "Cada test verifica UNA sola función o clase en aislamiento total.",
  "hereda_de": "tests/DEVIA.MD",

  "ficheros": {
    "conftest.py":               "Fixtures locales de unit (datos de prueba, factories)",
    "test_response_summarizer.py": "ResponseSummarizer: resumen, paginación, detección",
    "test_voice_interpreter.py":   "interpret_results_for_voice: respuestas TTS MetaGlass",
    "test_tts_cleaner.py":         "clean_for_tts: limpieza de Markdown para TTS",
    "test_sql_normalizer.py":      "FirebirdSQLNormalizer: LIMIT→FIRST, LIKE→UPPER, etc.",
    "test_pagination_detection.py":"Detección de peticiones de paginación del usuario"
  },

  "reglas": {
    "sin_red":    "Ningún test hace conexiones de red. Si lo hace → error de diseño.",
    "sin_bd":     "Ningún test conecta a Firebird. Usar datos de prueba en conftest.py.",
    "sin_ia":     "Ningún test llama a Qwen3. Usar mocks si es necesario.",
    "deterministicos": "Misma entrada → misma salida siempre.",
    "rapidos":    "Cada test < 100ms. Suite completa < 10s."
  },

  "datos_prueba": {
    "ubicacion": "tests/unit/conftest.py → fixtures de datos",
    "ejemplos": [
      "ARTICULOS_SAMPLE: lista de 50 artículos de prueba",
      "FACTURAS_SAMPLE: lista de 20 facturas de prueba",
      "CLIENTES_SAMPLE: lista de 10 clientes de prueba"
    ]
  },

  "ejecutar": ".venv/Scripts/pytest tests/unit/ -v -s",
  "cobertura": ".venv/Scripts/pytest tests/unit/ --cov=backend.modules.chat --cov-report=term"
}
```
