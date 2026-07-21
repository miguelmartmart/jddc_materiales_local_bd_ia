# DEVIA — Sistema DEVIA: Resumen Ejecutivo y Jerarquía
## Backend IA para Gafas Meta Ray-Ban + Chat Web + Constructor BD

> **Última actualización:** 10/07/2026  
> **Versión:** 3.1.0  
> **Ruta raíz:** `bots/interjddcia/`  
> **Tests:** ✅ 10.343+ passed · 69 skipped · 71 xfailed (suite completa)

---

## PRINCIPIOS DEVIA (obligatorios en todo el sistema)

| # | Principio | Descripción |
|---|-----------|-------------|
| 1 | **Sin inventar** | Nunca generar datos, tablas, columnas o valores que no existan en el esquema real |
| 2 | **Ultra-resiliente** | Cada módulo falla de forma segura; si falla, devuelve el estado anterior sin modificar |
| 3 | **Determinista primero** | Lógica determinista antes que IA; la IA es enriquecimiento opcional |
| 4 | **Genérico** | Sin hardcoding de casos concretos; el sistema deduce, infiere y analiza |
| 5 | **Modular** | Sin dependencias circulares; cada módulo < 500 líneas |
| 6 | **Jerárquico** | Este DEVIA es el resumen; los detalles están en los DEVIAs secundarios, con referencias EXACTAS a cada DEVIA secundario y a los ficheros/funcionalidades importantes que describe, para que ninguna funcionalidad quede huérfana o se pierda; cada DEVIA debe mantenerse breve, pero el conjunto de todos los DEVIAs debe describir el proyecto completo |
| 7 | **Sin alucinaciones** | Módulos específicos verifican que tablas/columnas/valores existen en el esquema real |
| 8 | **Logging de auditoría** | Cada decisión relevante queda registrada para trazabilidad |
| 9 | **Tests independientes** | Cada test es independiente; sin mocks de datos, solo mocks de preguntas |
| 10 | **Privacidad LAN** | Ningún dato de la BD sale a internet; solo Qwen3 LAN para análisis |

---

## ARRANQUE RÁPIDO

```
ARRANCAR_DEVIA.bat   ← doble clic para arrancar todo
PARAR_DEVIA.bat      ← doble clic para parar todo
```

| Opción | Qué arranca | Cuándo usarla |
|--------|------------|---------------|
| **1** | Solo Backend DEVIA (puerto 8001) | Chat IA web, gafas Meta, API |
| **2** | Backend DEVIA + CodeLab desktop | Uso completo del sistema |
| **3** | Solo CodeLab desktop | Editor de código con IA |
| **4** | Diagnóstico (sin arrancar nada) | Verificar estado del sistema |

Tras arrancar: **http://localhost:8001**

---

## ARQUITECTURA DEL SISTEMA

```
GAFAS META RAY-BAN / CHAT WEB / API
        │
        ▼ POST /api/chat/send
Backend DEVIA (FastAPI + Python)
        │
        ├─ ChatService (service.py)
        │   ├─ SemanticReasoningEngine  ← razona ANTES de generar SQL
        │   ├─ HallucinationGuard       ← verifica SQL generado por IA
        │   ├─ FirebirdSQLNormalizer    ← corrige SQL (LIMIT→FIRST, ILIKE→LIKE)
        │   ├─ SQLCorrector             ← reintentos con corrección IA
        │   └─ ModelFallbackOrchestrator ← fallback multi-modelo
        │
        ├─ DB Simulator (SQLite)        ← tests sin BD real
        │   ├─ schema.py               ← fuente de verdad del esquema
        │   ├─ query_library.py        ← biblioteca de consultas
        │   └─ snapshot_service.py     ← snapshot de BD real
        │
        ├─ Deep Analysis Agent          ← análisis profundo multi-fase
        │   └─ pipeline/ (phase1..5)
        │
        └─ SIUO (Sistema de Índices Ultra-Optimizado)
            ├─ context_retriever.py    ← contexto mínimo y preciso para IA
            ├─ concept_index.json      ← concepto → tablas
            ├─ table_index.json        ← resumen compacto de tablas
            └─ db_graph.json           ← grafo de relaciones
```

---

## JERARQUÍA DE DEVIAs

> Cada DEVIA secundario entra en detalle sobre su módulo.  
> Este documento es el punto de entrada; no repetir aquí lo que está en los secundarios.

### Nivel 1 — Sistema completo
| DEVIA | Ruta | Contenido |
|-------|------|-----------|
| **Este documento** | `bots/interjddcia/DEVIA.MD` | Resumen ejecutivo, arquitectura, principios, jerarquía |

### Nivel 2 — Módulos principales
| DEVIA | Ruta | Contenido |
|-------|------|-----------|
| Chat & IA | `backend/modules/chat/DEVIA.MD` | Pipeline SQL, modelos LAN, razonamiento semántico, anti-alucinaciones |
| Chat Robustez | `backend/modules/chat/DEVIA_ROBUSTNESS.md` | Model Fallback, Self-Healing, timeouts |
| DB Simulator | `backend/modules/db_simulator/DEVIA.md` | Esquema SQLite, seed data, query library |
| Configuración | `backend/core/config/DEVIA.MD` | Settings, modelos IA, API keys |

### Nivel 3 — Submódulos (detalle técnico)
| DEVIA | Ruta | Contenido |
|-------|------|-----------|
| Deep Analysis | `backend/modules/chat/deep_analysis/DEVIA.md` | Pipeline fases 1-5, síntesis, verificación |
| Pipeline Chat | `backend/modules/chat/pipeline/DEVIA.md` | Fases del pipeline de chat |
| **Tests QA SQL Obras** | `tests/qa_sql_obras/DEVIA.MD` | Cientos de tests que simulan preguntas de usuario sobre SQL Obras contra `POST /api/chat/send` real (sin mocks), cruzando modelo (30B/8B) × BD (real/simulador). Contiene el **registro de progreso** de esta iniciativa (ver sección siguiente) |

---

## 📋 REGISTROS DE PROGRESO (para retomar tras cortes de conversación)

> Estos ficheros son logs Markdown persistentes, con una fila por sesión, pensados para que un asistente (o una persona) pueda retomar el trabajo sin releer todo el historial de chat. Se añade una fila nueva cada sesión; no se borran las anteriores.

| Registro | Ruta | Qué guarda |
|----------|------|------------|
| QA SQL Obras | `tests/qa_sql_obras/DEVIA.MD` (tabla "Registro de progreso") | Avance de la generación de tests de preguntas de usuario sobre SQL Obras: decisiones de diseño, lotes de casos generados, incongruencias detectadas entre el manual técnico y los valores reales de la BD |
| **Observaciones y conclusiones (optimización de fases)** | `tests/qa_sql_obras/OBSERVACIONES_OPTIMIZACION.md` | Distinto del registro de progreso: aquí se acumulan hallazgos sobre **carencias del sistema** (huecos de conocimiento, fiabilidad de modelos LAN, gaps de esquema, reglas de negocio no capturadas...) detectados mientras se generan/ejecutan los tests de QA SQL Obras, cada uno con la fase del pipeline de chat a la que apunta. Se irá sintetizando en una propuesta concreta de optimización de fases para que las respuestas del chat IA sean de ultra calidad |

---

## FLUJO PRINCIPAL: PREGUNTA → SQL → RESPUESTA

```
[1] Usuario pregunta en lenguaje natural
        │
        ▼
[2] SemanticReasoningEngine.reason()
    → Detecta dominio (certificaciones, retenciones, artículos...)
    → Infiere tablas y relaciones correctas
    → Genera hints SQL deterministas
    → Enriquece el system prompt
        │
        ▼
[3] IA genera SQL (Qwen3 8B/30B LAN o fallback internet)
        │
        ▼
[4] HallucinationGuard.validate()
    → Verifica que tablas existen en el esquema real
    → Verifica que columnas existen en las tablas
    → Verifica valores de columnas enumeradas (TIPO, BAJA...)
    → Si hay errores críticos → no ejecutar
        │
        ▼
[5] FirebirdSQLNormalizer.normalize()
    → LIMIT → FIRST N
    → ILIKE → LIKE + UPPER()
    → DOCLIN.FECHA → JOIN DOCCAB
    → Elimina punto y coma final
        │
        ▼
[6] Ejecutar en BD (Firebird real o SQLite simulador)
    → Si falla → SQLCorrector con contexto del error (hasta 4 reintentos)
        │
        ▼
[7] Interpretar resultados y responder al usuario
    → Voz (MetaGlass): interpret_results_for_voice() — determinista
    → Web: ResponseSummarizer con paginación
```

---

## MÓDULOS CLAVE Y SUS RESPONSABILIDADES

| Módulo | Archivo | Responsabilidad |
|--------|---------|-----------------|
| **SemanticReasoningEngine** | `chat/semantic_reasoning_engine.py` | Razona sobre la pregunta ANTES de generar SQL. Detecta dominio, infiere tablas, genera hints. |
| **HallucinationGuard** | `chat/hallucination_guard.py` | Verifica que el SQL generado NO contiene tablas/columnas/valores inventados. |
| **FirebirdSQLNormalizer** | `chat/firebird_sql_normalizer.py` | Correcciones deterministas de SQL para Firebird. |
| **SafetyGuard** | `chat/safety_guard.py` | Bloquea operaciones destructivas (DROP, DELETE, UPDATE...) e inyecciones de prompt. |
| **SQLCorrector** | `chat/sql_corrector.py` | Reintentos con corrección IA cuando el SQL falla. |
| **ModelFallbackOrchestrator** | `chat/model_fallback_orchestrator.py` | Fallback entre modelos IA (LAN → internet). |
| **DB Simulator** | `db_simulator/driver.py` | SQLite en memoria/disco que replica el esquema Firebird para tests. |
| **QueryLibrary** | `db_simulator/query_library.py` | Biblioteca de consultas SQL validadas (Firebird + SQLite). |
| **ContextRetriever** | `db_explorer/context_retriever.py` | Recupera contexto mínimo y preciso del SIUO para cada pregunta. |

---

## MODELOS IA DISPONIBLES

| ID | Modelo | Velocidad | Uso |
|----|--------|-----------|-----|
| `jddcia-qwen3-30b-ip` | Qwen3 30B (IP directa) | 30-60s | Análisis profundo, preferido |
| `jddcia-qwen3-8b-ip` | Qwen3 8B VL (LM Studio) | 5-15s | Chat conversacional, rápido |
| Fallback internet | Gemini, Groq, OpenAI... | Variable | Si LAN no disponible |

> **Configuración:** `backend/modules/chat/config.json` → `ai_local_only: true/false`  
> **Detalle completo:** → `backend/modules/chat/DEVIA.MD`

---

## TESTS

```cmd
# Suite completa
python -m pytest bots/interjddcia/tests/ -v

# Solo tests unitarios (sin BD real, sin IA)
python -m pytest bots/interjddcia/tests/unit/ -v

# Tests de abstracción semántica (284 tests)
python -m pytest bots/interjddcia/tests/unit/test_semantica_*.py -v

# Tests anti-alucinaciones
python -m pytest bots/interjddcia/tests/unit/test_hallucination_guard.py -v

# Tests de conversaciones complejas reales (116 tests)
python -m pytest bots/interjddcia/tests/unit/test_conversaciones_complejas_reales.py -v
```

| Suite | Tests | Estado |
|-------|-------|--------|
| Conversaciones complejas reales | 116 | ✅ |
| Abstracción semántica (6 módulos) | 284 | ✅ |
| Anti-alucinaciones | ~60 | ✅ |
| Normalización SQL | 34 | ✅ |
| Voz + TTS | ~30 | ✅ |
| Paginación web + MetaGlass | ~25 | ✅ |

---

## DIAGNÓSTICOS RÁPIDOS

```cmd
# ¿Está corriendo?
curl http://localhost:8001/health

# Configuración actual
curl http://localhost:8001/api/chat/config

# ¿Qwen3 LAN responde?
curl -s --max-time 5 http://192.168.0.36/api/vlm/v1/models -H "Authorization: Basic YWRtaW46YWlzdGFjazIwMjY="

# Activar fallback internet (si LAN caída)
curl -X POST http://localhost:8001/api/chat/config -H "Content-Type: application/json" -d "{\"ai_local_only\": false}"
```

> **Diagnósticos detallados:** → `backend/modules/chat/DEVIA.MD` (sección Diagnósticos)

---

## HISTORIAL DE CAMBIOS RECIENTES

| Fecha | Cambio | Módulo |
|-------|--------|--------|
| 10/07/2026 | `HallucinationGuard`: módulo anti-alucinaciones. Verifica tablas/columnas/valores contra esquema real | `chat/hallucination_guard.py` |
| 10/07/2026 | `SemanticReasoningEngine`: handler clientes_proveedores infiere AGENTES dinámicamente | `chat/semantic_reasoning_engine.py` |
| 10/07/2026 | 284 tests de abstracción semántica en 6 módulos (artículos, clientes, documentos, financiero, estructura BD, vocabulario) | `tests/unit/test_semantica_*.py` |
| 09/07/2026 | 116 tests de conversaciones complejas reales sin mocks | `tests/unit/test_conversaciones_complejas_reales.py` |
| 08/07/2026 | Fix timeout análisis profundo: frontend heartbeat 30s + extensiones automáticas | `chat/service.py`, `constants.js` |
| 08/07/2026 | ProgressTracker en DeepAnalysisAgent: fases reportadas en tiempo real | `chat/deep_analysis_agent.py` |

> **Historial completo:** → `backend/modules/chat/DEVIA.MD` (sección Documentación de sesiones)
