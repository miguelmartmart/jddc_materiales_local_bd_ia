# DEVIA: TESTS — Estrategia, Estructura y Principios

```json
{
  "module": "tests",
  "description": "Suite de tests de DEVIA. Organizada en capas: unitarios, integración, e2e. Garantiza que ningún dato sale a internet.",
  "version": "2.0",
  "last_updated": "09/03/2026",

  "estructura": {
    "tests/": {
      "DEVIA.MD":          "Este fichero — estrategia global de tests",
      "conftest.py":       "Fixtures compartidos + TestConfig + autodetección de IPs",
      "test.properties":   "ÚNICA fuente de verdad de parámetros de tests",
      "unit/":             "Tests unitarios — sin BD, sin IA, sin red",
      "integration/":      "Tests de integración — con BD real + Qwen3 LAN",
      "e2e/":              "Tests end-to-end — flujo completo chat→SQL→respuesta",
      "privacy/":          "Tests de auditoría de privacidad — garantía LAN-only"
    }
  },

  "principios": {
    "1_parametros_centralizados": "TODOS los parámetros en test.properties. Nunca hardcodeados en tests.",
    "2_autodeteccion": "QWEN3_HOST=auto y DB_HOST=auto se resuelven automáticamente.",
    "3_lan_only": "ENFORCE_LAN_ONLY=true. Cualquier conexión a internet → FALLO inmediato.",
    "4_skip_si_no_disponible": "Si BD o Qwen3 no están disponibles → SKIP (no FAIL).",
    "5_trazas_completas": "Cada test genera trazas en logs/. Ver logs/ para depurar.",
    "6_ficheros_max_500_lineas": "Ningún fichero de test supera 500 líneas.",
    "7_devia_por_carpeta": "Cada carpeta tiene su DEVIA.MD que detalla los tests de esa capa.",
    "8_sin_mocks_en_integracion": "Los tests de integración usan BD y Qwen3 reales.",
    "9_mocks_solo_en_unit": "Los tests unitarios usan mocks para aislar la lógica.",
    "10_robustez": "Los tests son tolerantes a errores: reintentos, timeouts, skip automático."
  },

  "capas": {
    "unit": {
      "descripcion": "Tests unitarios. Sin BD, sin IA, sin red. Rápidos (<1s cada uno).",
      "carpeta": "tests/unit/",
      "ficheros": [
        "test_response_summarizer.py  — lógica de resumen y paginación",
        "test_voice_interpreter.py    — interpret_results_for_voice (MetaGlass TTS)",
        "test_tts_cleaner.py          — clean_for_tts (limpieza de Markdown)",
        "test_sql_normalizer.py       — FirebirdSQLNormalizer (correcciones SQL)",
        "test_pagination_detection.py — detección de peticiones de paginación"
      ],
      "ejecutar": ".venv/Scripts/pytest tests/unit/ -v -s"
    },
    "integration": {
      "descripcion": "Tests de integración. Con BD Firebird real + Qwen3 LAN. Sin mocks.",
      "carpeta": "tests/integration/",
      "ficheros": [
        "test_siuo_retriever.py    — ContextRetriever con índices SIUO reales",
        "test_chat_metaglass.py    — preguntas reales desde MetaGlass",
        "test_chat_web.py          — preguntas reales desde cliente web",
        "test_pagination_real.py   — paginación con datos reales de BD"
      ],
      "ejecutar": ".venv/Scripts/pytest tests/integration/ -v -s",
      "requisitos": ["BD Firebird accesible", "Qwen3 LAN accesible", "Índices SIUO generados"]
    },
    "e2e": {
      "descripcion": "Tests end-to-end. Flujo completo: pregunta → SQL → BD → respuesta.",
      "carpeta": "tests/e2e/",
      "ficheros": [
        "test_preguntas_1tabla.py   — preguntas que usan 1 tabla",
        "test_preguntas_2tablas.py  — preguntas que cruzan 2-3 tablas",
        "test_preguntas_complejas.py — preguntas con 4+ tablas",
        "test_regresiones.py        — regresiones conocidas (artículos+compras, etc.)"
      ],
      "ejecutar": ".venv/Scripts/pytest tests/e2e/ -v -s"
    },
    "privacy": {
      "descripcion": "Tests de auditoría de privacidad. Garantizan que ningún dato sale a internet.",
      "carpeta": "tests/privacy/",
      "ficheros": [
        "test_network_audit.py     — intercepta socket.connect y verifica LAN-only",
        "test_settings_privacy.py  — verifica que settings no tiene URLs de internet",
        "test_model_manager.py     — verifica que no hay modelos de internet activos"
      ],
      "ejecutar": ".venv/Scripts/pytest tests/privacy/ -v -s"
    }
  },

  "logs": {
    "directorio": "bots/interjddcia/logs/",
    "ficheros": {
      "conftest.log":             "Arranque, autodetección de IPs, configuración",
      "network_audit.log":        "TODAS las conexiones de red (LAN ✅ / Internet 🚨)",
      "sql_trace.log":            "Todas las consultas SQL ejecutadas",
      "ai_requests.log":          "Peticiones a Qwen3 LAN (nunca a internet)",
      "integration_traces.jsonl": "Trazas JSON de cada test de integración",
      "test_integration_real.log":"Log completo de tests de integración"
    }
  },

  "ejecutar_todos": {
    "comando": ".venv/Scripts/pytest tests/ -v -s --tb=short 2>&1 | tee logs/test_all.log",
    "solo_unit": ".venv/Scripts/pytest tests/unit/ -v -s",
    "solo_integracion": ".venv/Scripts/pytest tests/integration/ tests/e2e/ -v -s",
    "solo_privacidad": ".venv/Scripts/pytest tests/privacy/ -v -s",
    "con_cobertura": ".venv/Scripts/pytest tests/ --cov=backend --cov-report=html"
  },

  "garantia_privacidad": {
    "mecanismo": "NetworkAuditInterceptor intercepta socket.connect en tiempo de ejecución",
    "resultado": "Si se detecta conexión a internet → AssertionError inmediato",
    "log": "logs/network_audit.log registra TODAS las conexiones con timestamp",
    "verificacion_manual": "grep 'INTERNET' logs/network_audit.log → debe estar vacío"
  },

  "related_devia": [
    "bots/interjddcia/DEVIA.MD (documentación principal del bot)",
    "bots/interjddcia/backend/modules/chat/DEVIA.MD (módulo de chat)",
    "bots/interjddcia/backend/modules/db_explorer/DEVIA.MD (módulo SIUO)",
    "bots/interjddcia/tests/unit/DEVIA.MD (tests unitarios)",
    "bots/interjddcia/tests/integration/DEVIA.MD (tests de integración)",
    "bots/interjddcia/tests/e2e/DEVIA.MD (tests end-to-end)",
    "bots/interjddcia/tests/privacy/DEVIA.MD (tests de privacidad)"
  ]
}
```
