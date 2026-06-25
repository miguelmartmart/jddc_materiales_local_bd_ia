# DEVIA MODULE CONTEXT: CHAT & AI CONVERSATION
# Context for the Chat Service, Prompt Engineering, and Intent Management.

## 📚 Documentación de sesiones

| Sesión | Archivo | Contenido |
|--------|---------|-----------|
| 25/06/2026 | `DEVIA.MD` | **FIX ORDEN RESPUESTA deep_analysis**: `phase5.py` — las anomalías y advertencias ahora aparecen DESPUES del cuerpo principal, bajo sección "## 🔎 Evidencias y Aclaraciones". Antes preprendían al principio. |
| 25/06/2026 | `DEVIA.MD` | **FIX SQL INCOMPLETO**: `phase3.py` — comprobación de paréntesis balanceados antes de ejecutar SQL. SQL con paréntesis desbalanceados (IA truncada) se descarta con mensaje limpio. |
| 25/06/2026 | `DEVIA.MD` | **FIX TIPO MAPPING** (deep_analysis): Mapeo DOCCAB.TIPO verificado con usuario el 25/06/2026. `_detect_tipo_filter` en `phase3_sqls.py` ahora usa TIPO=2 para albarán cliente (era 11), TIPO=1 para pedido cliente (era 12), TIPO=11 para pedido proveedor, TIPO=3 para factura cliente, TIPO=13 para factura proveedor. Distinción proveedor/cliente por contexto. |
| 25/06/2026 | `DEVIA.MD` | **FIX IA ETIQUETAS TIPO**: prompt de síntesis en `phase5.py` incluye las 15 etiquetas verificadas de DOCCAB.TIPO y exige mostrar TODOS los tipos presentes (no solo top-3). Regla explícita: "TIPO=0 es PRESUPUESTO, NUNCA Albarán". |
| 25/06/2026 | `DEVIA.MD` | **FIX SIUO DOCCAB NOTE**: `table_index.json` — nota de DOCCAB corregida. Contenía "21=Factura, 12=Pedido" (alucinación de IA). Sustituida por mapeo verificado completo. Consultas de ejemplo también corregidas (eliminado `WHERE TIPO=21`). |
| 21/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Fix `_execute_sql`: eliminado `time.sleep()` síncrono, 1 intento directo sin bloquear asyncio |
| 21/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Context Manager v3.0 integrado en `jddcia_provider.py` |
| 10/06/2026 | `DEVIA.MD` | Añadido soporte Qwen3 8B VL en LM Studio (jddcia-qwen3-8b-ip / jddcia-qwen3-8b) |
| 10/06/2026 | `DEVIA.MD` | FirebirdSQLNormalizer: paso 23 (CAST AS TEXT→VARCHAR(100)), paso 24 (derived table AS alias), fix_after_error TOKEN UNKNOWN AS. 34/34 tests ✅ |
| 10/06/2026 | `DEVIA.MD` | **BUG FIX**: `ChatRequest` en `router.py` no tenía campo `preferred_model_id` ni `no_db` → Pydantic los ignoraba silenciosamente. Añadidos ambos campos. |
| 10/06/2026 | `DEVIA.MD` | **BUG FIX**: `service.py` usaba `context.get('model_id')` como `preferred_model_id` en el orchestrator (2 lugares: `_chat_no_db` y `process_message`). Corregido a `context.get('preferred_model_id') or context.get('model_id')`. |
| 11/06/2026 | `DEVIA.MD` | **BUG FIX CRÍTICO — Respuesta cortada**: `max_tokens=512` en todos los modelos Qwen3 cortaba respuestas largas (análisis profundo ~2000-3500 tokens). Causa raíz: `jddcia_provider.py` calculaba `max_tokens = context_limit // 8` ignorando el valor del JSON. |
| 11/06/2026 | `DEVIA.MD` | **FIX**: `jddcia_provider.py` `configure()` ahora lee `max_tokens` con prioridad: 1) `parameters.max_tokens` del JSON del modelo, 2) `lan_model_max_tokens` en `config.json`, 3) auto-cálculo 50% del contexto (mínimo 512). |
| 11/06/2026 | `DEVIA.MD` | **FIX**: `jddcia_models.json` — `max_tokens` actualizado a 4096 para los 4 modelos Qwen3 (30B-ip, 30B-mDNS, 8B-ip, 8B-mDNS). Timeout 8B actualizado a 180s. |
| 11/06/2026 | `DEVIA.MD` | **FIX**: `chat/config.json` — añadidos `lan_model_max_tokens=4096` y `lan_model_context_limit=4096` como overrides globales. |
| 11/06/2026 | `DEVIA.MD` | **NUEVO**: `phase5.py` — `_continue_if_truncated()`: detecta respuesta cortada (secciones obligatorias ausentes) y pide al modelo que continúe hasta 3 veces. Si no se puede completar, añade aviso amigable al usuario. |

**Regla crítica `_execute_sql`:** NO usar `time.sleep()` ni reintentos en código async.
Un único intento directo. Si falla → excepción inmediata. El caller decide cómo manejarla.

---

## 🤖 Modelos IA locales disponibles (LAN JDDC)

| ID | Nombre | Provider/Schema | URL | Auth | Notas |
|----|--------|-----------------|-----|------|-------|
| `jddcia-qwen3-30b-ip` | Qwen3 VL 30B (IP directa) | `jddcia` | `http://192.168.0.36/api/vlm/v1` | Basic Auth (nginx) | **Preferido**. tier=elite |
| `jddcia-qwen3-30b` | Qwen3 VL 30B (mDNS) | `jddcia` | `http://jddcia.local/api/vlm/v1` | Basic Auth (nginx) | Fallback del 30B-IP |
| `jddcia-qwen3-8b-ip` | ⚡ Qwen3 8B VL (LM Studio IP) | `jddcia` / schema=`openai_compatible` | `http://192.168.0.36:1234/v1` | Bearer `lm-studio` | **Nuevo**. tier=high. Más rápido |
| `jddcia-qwen3-8b` | ⚡ Qwen3 8B VL (LM Studio mDNS) | `jddcia` / schema=`openai_compatible` | `http://jddcia.local:1234/v1` | Bearer `lm-studio` | **Nuevo**. Fallback del 8B-IP |

### Diferencias clave 30B vs 8B

| Aspecto | Qwen3 30B (vLLM gateway) | Qwen3 8B (LM Studio) |
|---------|--------------------------|----------------------|
| Puerto | 80 (nginx) | 1234 (LM Studio) |
| Auth | Basic Auth (nginx) | Bearer `lm-studio` (cualquier string) |
| Provider Python | `JDDCIAProvider` | `OpenAICompatibleProvider` |
| Schema en JSON | `jddcia` | `openai_compatible` |
| Velocidad | 30-60s primera petición | 5-15s |
| Context | 4096 tokens | 8192 tokens |
| Autodescubrimiento | Sí (escanea subred) | No (URL fija) |

### ⚠️ Configuración del model_id en LM Studio

El campo `model_id` en `jddcia_models.json` debe coincidir con el identificador que LM Studio
asigna al modelo cargado. Para verificarlo:
1. Abrir LM Studio → pestaña **Developer**
2. Iniciar el servidor local
3. Hacer `GET http://192.168.0.36:1234/v1/models` → ver el campo `id` en la respuesta
4. Si difiere de `qwen/qwen3-vl-8b`, actualizar `model_id` en `jddcia_models.json`

**Valor confirmado (10/06/2026):** `qwen/qwen3-vl-8b`

Otros valores posibles según la versión del modelo GGUF:
- `qwen3-8b` (nombre corto, versiones antiguas)
- `Qwen3-8B` (con mayúsculas)
- `qwen3-8b-instruct` (con sufijo instruct)
- Nombre del archivo GGUF sin extensión (ej: `Qwen3-8B-Q4_K_M`)

### ⚠️ Caveat técnico: timeout de socket con stream=false

LM Studio usa `stream: false` por defecto. Esto significa que el servidor genera **todos los tokens
internamente** y envía la respuesta de golpe al final. Durante la generación, el socket HTTP no
recibe datos → el timeout de socket salta aunque el servidor esté trabajando.

**Síntoma:** `ReadTimeout` o `ConnectionTimeout` después de 60s aunque el modelo esté procesando.

**Solución:** Timeouts generosos en `config.json`:
```json
{
  "lan_read_timeout_s": 120,
  "lan_connect_timeout_s": 10
}
```

Valores recomendados:
- Chat conversacional: **120s** (Qwen3 8B en CPU puede tardar 60-90s)
- Análisis profundo: **180s** (consultas complejas con contexto largo)
- Status check: **3s** (falla rápido si LM Studio no está activo)

Si el hardware tiene GPU, los tiempos bajan a 5-15s y estos timeouts son más que suficientes.

### Fuente única de verdad para IDs de modelos locales

`backend/core/utils/network_audit_constants.py` → clase `LocalModelIds`

```python
LocalModelIds.QWEN3_MDNS    = "jddcia-qwen3-30b"
LocalModelIds.QWEN3_IP      = "jddcia-qwen3-30b-ip"
LocalModelIds.QWEN3_8B_IP   = "jddcia-qwen3-8b-ip"   # NUEVO
LocalModelIds.QWEN3_8B_MDNS = "jddcia-qwen3-8b"       # NUEVO
LocalModelIds.ALL            = frozenset({...todos...})
```

El orchestrator usa `LocalModelIds.ALL` para filtrar modelos LAN en modo `ai_local_only=true`.
Al añadir los IDs 8B aquí, el orchestrator los incluye automáticamente sin más cambios.

---

```json
{
  "module": "backend.modules.chat",
  "description": "Core conversational engine. Manages user intent, context window, and system prompts.",
  "components": {
    "ChatService": "Main entry point. Handles message history, intention classification (SQL vs Visual vs General). _execute_sql NO usa time.sleep() — un único intento directo para no bloquear asyncio.",
    "SQLCorrector": "Specialized component to fix malformed SQL queries generated by AI.",
    "FirebirdSQLNormalizer": "Deterministic corrections: removes semicolons, fixes LIMIT->FIRST, etc.",
    "ChatHistoryService": "Manages persistence of conversation turns.",
    "ChatVoiceInterpreter": "ÚNICA FUENTE DE VERDAD para interpret_results_for_voice y clean_for_tts. service.py delega aquí.",
    "ResponseSummarizer": "Paginación de resultados para web (summarize/handle_pagination_request) y MetaGlass voz (summarize_for_metaglass/handle_metaglass_pagination)."
  },
  "voice_pipeline": {
    "description": "Pipeline determinista para clientes de voz (gafas Meta). Elimina 2ª llamada IA (~20s).",
    "source_of_truth": "backend/modules/chat/chat_voice_interpreter.py",
    "delegation": "service.py importa interpret_results_for_voice y clean_for_tts desde chat_voice_interpreter.py",
    "bug_fixed_2026_03_09": {
      "bug": "TOTAL (monetario, float) se confundía con COUNT (entero). Ej: '45678.90 facturas' en vez de '45.678,90 euros'.",
      "fix": "_is_monetary_value() detecta si el valor es float con decimales → usa formato monetario con 'euros'.",
      "test": "tests/unit/test_voice_and_tts.py::TestInterpretResultsForVoice::test_total_facturado"
    },
    "functions": {
      "interpret_results_for_voice(message, results, sql_query)": "Formatea resultados BD en lenguaje natural para TTS. 100% determinista.",
      "clean_for_tts(text)": "Elimina Markdown (**, ##, ```, etc.) para que el TTS no lea 'asterisco'."
    }
  },
  "pagination": {
    "web": {
      "class": "ResponseSummarizer",
      "threshold": "SUMMARY_THRESHOLD (default 20)",
      "page_size": "PAGE_SIZE_DEFAULT (default 10), PAGE_SIZE_MAX (default 50)",
      "methods": ["summarize(message, rows, sql)", "handle_pagination_request(user_msg, state)"],
      "state_keys": ["rows", "total", "shown", "sql", "question"]
    },
    "metaglass": {
      "class": "ResponseSummarizer",
      "threshold": "METAGLASS_PAGINATION_THRESHOLD (default 5) — más bajo que web",
      "page_size": "METAGLASS_PAGE_SIZE (default 3) — pequeño para TTS",
      "methods": ["summarize_for_metaglass(message, rows, sql, threshold?, page_size?)", "handle_metaglass_pagination(user_msg, state, use_ai?)"],
      "state_keys": ["rows", "total", "shown", "sql", "question", "page_size", "client='metaglass'"],
      "intent_detection": {
        "deterministic": "_detect_intent_deterministic(msg) → 'si'|'no'|'todos'",
        "ai_fallback": "use_ai=True llama a IA para intenciones ambiguas",
        "priority": "'todos' tiene prioridad sobre 'no' (ej: 'no, dame todos' → 'todos')"
      },
      "format": "Sin Markdown. Pregunta si quiere listar poco a poco. Preview de primeros items."
    }
  },
  "ai_mode": {
    "current": "LOCAL_ONLY",
    "config_file": "backend/modules/chat/config.json",
    "ai_local_only": true,
    "description": "SOLO usa la IA local Qwen3 VL 30B (red LAN JDDC, 192.168.0.36). El sistema de fallback multi-modelo (Groq, Gemini, OpenAI, etc.) está DESHABILITADO pero NO eliminado.",
    "models_local": [
      "jddcia-qwen3-30b-ip → http://192.168.0.36/api/vlm/v1 (score 95, PRIMERO)",
      "jddcia-qwen3-30b   → http://jddcia.local/api/vlm/v1  (score 50, fallback mDNS)"
    ],
    "change_mode_api": "POST http://localhost:8001/api/chat/config con {ai_local_only: true/false}",
    "warning": "Si ai_local_only=true y la IA local está ocupada/caída, el sistema falla. Usar false para fallback a internet."
  },
  "prompt_engineering": {
    "system_prompt_construction": {
      "base": "Eres un asistente experto en bases de datos Firebird SQL...",
      "dynamic_injection": [
        "Database Schema (si SQL intent) — db_metadata_optimized.json",
        "Image Analysis Results (si hay imágenes)",
        "Current Date/Time",
        "User Profile Context"
      ]
    },
    "intent_rules": {
      "visual_analysis": "IF user asks 'What do you see?', DISABLE SQL tools. Force VLM mode.",
      "sql_generation": "IF user asks for data/stock, ENABLE SQL tools. Inject Schema.",
      "image_generation": "IF user asks 'dibuja...', respond with [GENERAR_IMAGEN: prompt]"
    }
  },
  "sql_pipeline": {
    "order": [
      "1. IA genera SQL",
      "2. FirebirdSQLNormalizer.normalize() — correcciones deterministas",
      "3. clean_firebird_sql() — elimina LIMIT, ROWS, etc.",
      "4. Añadir FIRST N si SELECT sin FIRST y sin agregados",
      "5. execute_with_correction() — ejecuta con reintentos (max_sql_retries=4)"
    ],
    "critical": "clean_firebird_sql DEBE llamarse ANTES de añadir FIRST N"
  },
  "context_management": {
    "window_size": "Automatic truncation of old messages to fit model context (16384 tokens para Qwen3).",
    "history_tracking": "Stores 'role' (user/assistant) and 'content'."
  },
  "endpoints": {
    "POST /api/chat/send": "Enviar mensaje al chat IA",
    "GET /api/chat/config": "Ver configuración actual (incluye ai_local_only)",
    "POST /api/chat/config": "Cambiar configuración en caliente",
    "GET /api/chat/history": "Ver historial de conversación"
  },
  "frontend_lan_model_selector": {
    "description": "Desplegable '⚡ Motor LAN:' en la cabecera del Chat IA para elegir entre Qwen3 30B y Qwen3 8B VL sin recargar la página.",
    "element_id": "chat-lan-model-selector",
    "location": "frontend/index.html — sección #view-chat, junto al selector de modelo IA",
    "options": [
      { "value": "jddcia-qwen3-30b-ip", "label": "🏠 Qwen3 30B (potente)" },
      { "value": "jddcia-qwen3-8b-ip",  "label": "⚡ Qwen3 8B VL (rápido)" }
    ],
    "wire_js": "frontend/assets/js/modules/chat.js — sendMessage() y confirmAndSend() leen el selector y envían preferred_model_id en el body del POST /api/chat/send",
    "backend_field": "preferred_model_id en ChatRequest → el orchestrator coloca ese modelo primero en la lista de fallback",
    "visual": "Borde azul (#93c5fd), fondo #eff6ff, texto azul oscuro — diferenciado del selector de modelo general",
    "nota": "El selector LAN es independiente del selector de modelo IA general. El selector general elige el 'canal' (jddcia, groq, etc.); el selector LAN elige el motor específico dentro del canal JDDC."
  },
  "tests": {
    "unit": "tests/unit/test_voice_and_tts.py (voz+TTS), tests/unit/test_response_summarizer.py (paginación web+MetaGlass), tests/unit/test_qwen3_8b_lmstudio.py (Qwen3 8B VL — 27 tests, 8 sistemas)",
    "coverage": "115 tests unitarios, 0 fallos (09/03/2026) + 27 tests Qwen3 8B (10/06/2026)",
    "run": ".venv/Scripts/pytest tests/unit/ -v",
    "run_8b_only": "python -m pytest bots/interjddcia/tests/unit/test_qwen3_8b_lmstudio.py -v",
    "run_8b_fast": "python -m pytest bots/interjddcia/tests/unit/test_qwen3_8b_lmstudio.py -v -k 'Configuracion or Privacidad or Timeouts or Frontend'",
    "test_8b_sistemas": [
      "1. TestConfiguracionModelos — jddcia_models.json: model_id, schema, api_key, base_url, auth, tier, context_limit",
      "2. TestLocalModelIds — LocalModelIds.ALL incluye los 4 IDs (30B×2 + 8B×2)",
      "3. TestAIFactory — schema='openai_compatible' → OpenAICompatibleProvider; schema='jddcia' → JDDCIAProvider",
      "4. TestDiscoveryServiceLMStudio — discover_lmstudio(): sin servidor→[], con servidor→parsea correctamente",
      "5. TestOrchestratorPreferredModel8B — preferred_model_id coloca el 8B primero; sin preferred→orden por score",
      "6. TestPrivacidad8BEsLAN — URLs 192.168.0.36:1234 y jddcia.local:1234 son LAN (RFC 1918 / .local)",
      "7. TestTimeouts8B — CHAT_MS>=120s, ANALYZE_MS>=180s, STATUS_MS<=5s, lan_read_timeout_s>=120",
      "8. TestFrontendDesplegableLAN — #chat-lan-model-selector en HTML, preferred_model_id en chat.js"
    ]
  },
  "simulator_onboarding": {
    "why_tests_pass_but_app_fails": "Los tests usan BD SQLite en :memory: (siempre vacía pero con tablas). La app usa simulator.db en disco. Si simulator_enabled=false en config.json, _execute_sql intenta Firebird real → falla. Si simulator_enabled=true pero sin datos → falla con tabla vacía.",
    "pasos_exactos_para_chat_ia": [
      "1. Activar simulador: POST /api/db-simulator/config  {simulator_enabled: true}",
      "2. Generar datos: POST /api/db-simulator/build-synthetic  (~2s, sin Firebird)",
      "3. El chat ya funciona: preguntar '¿Cuántas facturas hay?' etc."
    ],
    "endpoint_onboarding": "GET /api/db-simulator/onboarding-status → devuelve ready:bool, steps[], message amigable",
    "onboarding_en_chat": "Si simulator_enabled=true pero sin datos, el router del chat devuelve HTML con los 3 pasos en lugar de un error críptico",
    "flujo_execute_sql": "_execute_sql() → simulator_manager.is_enabled() → si true: SimulatedFirebirdDriver.connect(simulator.db) → si false: FirebirdDriver.connect(Firebird real)"
  },
  "intent_classification_v2": {
    "description": "Sistema de interpretacion por fases con IA local (generico, sin keywords hardcodeadas)",
    "module": "backend/modules/chat/intent_classifier.py",
    "class": "IntentClassifier",
    "how_it_works": "UNA sola llamada ligera al modelo IA (Qwen3 30B LAN). Respuesta JSON con intent+confidence+reasoning.",
    "intent_types": ["CONVERSATIONAL", "DB_QUERY", "CLARIFICATION", "DEEP_ANALYSIS", "IMAGE_GEN", "COMMAND"],
    "fallback": "Si la IA falla, usa clasificador determinista con patrones semanticos amplios (no solo keywords exactas)",
    "ventajas": [
      "Funciona con cualquier idioma, sinonimo, parafrasis o expresion coloquial",
      "'cuanto vendimos?' -> DB_QUERY (sin keyword 'factura')",
      "'no me queda claro' -> CLARIFICATION (sin keyword 'justifica')",
      "'hazme un resumen completo' -> DEEP_ANALYSIS (sin keyword 'analiza en profundidad')",
      "'dibuja un logo' -> IMAGE_GEN (sin keyword 'generar imagen')"
    ],
    "fases": {
      "FASE_1": "IntentClassifier.classify(message, history) -> IntentResult",
      "FASE_2": "Accion segun intent: CONVERSATIONAL->_chat_no_db | DB_QUERY->SQL | CLARIFICATION->historial | DEEP_ANALYSIS->DeepAgent | IMAGE_GEN->ImageService",
      "FASE_3": "Interpretacion con lenguaje de negocio, sin SQL visible, con justificacion en <details>"
    },
    "integration_status": "IntentClassifier creado y disponible. Integracion gradual en process_message en curso.",
    "commit": "a6deed5 (01/06/2026)"
  },
  "last_updated": "10/06/2026",
  "related_devia": [
    "bots/interjddcia/DEVIA.MD (documentación principal)",
    "backend/modules/chat/DEVIA_ROBUSTNESS.md (Model Fallback & Self-Healing)",
    "backend/core/config/DEVIA.MD (configuración de modelos)"
  ]
}
```
