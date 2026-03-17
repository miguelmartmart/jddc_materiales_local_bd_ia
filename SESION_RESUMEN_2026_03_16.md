# 📋 RESUMEN DE SESIÓN — 16/03/2026
## Proyecto: DEVIA / bots/interjddcia
## Commits: `7c0ec3e` → `089ce03` → `24627bf` (branch: `main`)

---

## ✅ LO IMPLEMENTADO EN ESTA SESIÓN

### 1. FIX CRÍTICO: Advertencia incorrecta de DOCCAB
**Archivo:** `backend/modules/chat/firebird_sql_constants.py`

**Problema:** `LOW_RECORD_TABLES` tenía `DOCCAB` con `record_count: 3` — ese número era de los metadatos SIUO (muestras), NO de los registros reales. DOCCAB tiene miles de registros reales. Esto generaba la advertencia falsa:
> ⚠️ ADVERTENCIA: DOCCAB solo tiene 3 registros en los metadatos indexados...

**Solución:**
- Eliminado `DOCCAB` de `LOW_RECORD_TABLES`
- Añadido comentario explicativo: el `record_count` es de muestras SIUO, no de la BD real
- Añadidas tablas que SÍ están realmente vacías: `CONDICIO`, `EQUIVAL`, `CLIENTEDOCUM`

---

### 2. MEJORA: Prompt de interpretación WEB con análisis profundo
**Archivo:** `backend/modules/chat/service.py`

**Cambio:** El `interpretation_system` ahora incluye análisis profundo obligatorio:
- Detección de duplicados (mismo cliente con varios presupuestos para la misma instalación)
- Calidad de datos (nulos, fechas incoherentes, importes negativos)
- Anomalías estadísticas (valores extremos, tasas inusuales)
- **Contexto de negocio clave:** 1 instalación puede tener N presupuestos → total presupuestos ≠ total instalaciones
- Limitaciones del SQL (LEFT JOINs, COUNT(*) vs COUNT(DISTINCT))
- Advertencias proactivas y sugerencias de mejora

---

### 3. NUEVO MÓDULO: DeepAnalysisAgent ÉPICO (refactorizado en paquete)
**Directorio:** `backend/modules/chat/deep_analysis/` (nuevo paquete)

| Archivo | Descripción |
|---------|-------------|
| `__init__.py` | Exportaciones públicas |
| `models.py` | AnalysisDepth, TokenBudget, EpicAnalysisResult, detect_depth() |
| `agent.py` | Orquestador principal + helpers compartidos |
| `phases_1_2.py` | Fases 0, 1, 2 (comprensión + exploración) |
| `phases_3_4_5.py` | Fases 3, 4, 5 (investigación + análisis + síntesis) |

#### Niveles de profundidad (auto-detectados):
| Nivel | SQLs | Tablas | Cuándo |
|-------|------|--------|--------|
| BASIC | 2 | 2 | Preguntas simples directas |
| MEDIUM | 4 | 4 | Listados, consultas moderadas |
| DEEP | 8 | 6 | Totales, rankings, comparativas |
| **EPIC** | **12** | **8** | **Por defecto — análisis, tasas, tendencias** |

#### Helpers de resiliencia multi-fuente (agent.py):
- `_get_siuo_columns(table)`: BD real → SIUO JSON → lista vacía
- `_get_siuo_record_count(table)`: BD real → SIUO JSON → None
- `_extract_columns_from_context(table)`: 4 patrones regex sobre db_context texto
- `_load_metadata_json()`: carga `db_metadata_optimized.json` de forma segura
- Todos ultra-resilientes: nunca lanzan excepción, siempre devuelven fallback

#### Flujo de resiliencia en _explore_table():
```
BD Firebird disponible → columnas_source = "rdb_fields"
BD falla → SIUO JSON disponible → columnas_source = "siuo_metadata"
BD falla + JSON vacío → db_context texto → columnas_source = "db_context_text"
Todo falla → columnas = [] → columnas_source = "unknown"
```

---

### 4. INTEGRACIÓN: DeepAnalysisAgent en service.py
**Archivo:** `backend/modules/chat/service.py`

**Activación:**
- Comando explícito: `/deep <pregunta>` o `/analisis <pregunta>`
- Palabras clave: "analiza en profundidad", "análisis completo", "investiga", "a fondo", etc.
- **Checkbox frontend:** `context.get('deep_analysis', False)` — activa siempre si marcado
- Fall-through al flujo normal si el agente falla (ultra-resiliente)

---

### 5. FRONTEND: Checkbox "Análisis Profundo" en Chat IA
**Archivo:** `frontend/index.html` + `frontend/assets/js/modules/chat.js`

- Checkbox `#deep-analysis-toggle` marcado por defecto en la barra de chat
- Envía `deep_analysis: true` en el body del POST `/api/chat/send`
- El backend en `service.py` lee `context.get('deep_analysis', False)`

---

### 6. FRONTEND: Checkbox "Análisis Profundo" en Índices SIUO
**Archivos:** `frontend/assets/js/modules/siuo_render.js` + `siuo.js`

**Problema:** La página de Índices SIUO no tenía el checkbox de análisis profundo.

**Solución:**
- `siuo_render.js`: añadido checkbox `#siuo-deep-analysis-toggle` (marcado por defecto) en la sección "Probar ContextRetriever"
- `siuo.js`: nueva función `_callDeepAnalysisAPI(question)` que llama a `/api/chat/send` con `deep_analysis: true`
- `siuo.js`: función `_isSiuoDeepEnabled()` lee el estado del checkbox
- `siuoTestContext()` y `siuoRunQuickTest()`: si checkbox marcado → DeepAgent, si no → flujo SIUO normal
- Mensajes de loading diferenciados: "🔬 Análisis profundo activado — ejecutando 5 fases..."
- **Fix crítico:** URL corregida de `/api/chat` (404) a `/api/chat/send` (correcto)

---

### 7. MEJORA: Outlook Auth Cache con TTL de fallos
**Archivo:** `backend/modules/outlook/router.py`

- `mark_failed(method_key)`: registra que un método de auth falló
- `is_known_failure(method_key)`: evita reintentar métodos fallidos durante 10 minutos
- Evita loops de autenticación fallida en cada poll

---

### 8. TESTS: 71/71 tests unitarios
**Archivo:** `tests/unit/test_deep_analysis_agent.py`

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestDetectDepth` | 8 | Auto-detección de profundidad |
| `TestTokenBudget` | 8 | Conteo, fits, truncate, usage_pct |
| `TestPhase1Fallback` | 5 | Fallback si IA falla, tablas candidatas |
| `TestPhase2Exploration` | 3 | Exploración de tablas con mock SQL |
| `TestPhase3FixedSQLs` | 6 | SQLs fijos (temporal + instalaciones) |
| `TestPhase4SIUOFeedback` | 3 | Registro de feedback SIUO |
| `TestEmergencyFallback` | 3 | Fallback de emergencia |
| `TestFullAnalysisMock` | 3 | Análisis completo con mocks |
| `TestHelpers` | 10 | parse_json, fmt_*, build_warnings_html |
| `TestSIUOMetadataHelpers` | **22** | **Flujo real BD→SIUO JSON→db_context** |

#### Tests de resiliencia multi-fuente (TestSIUOMetadataHelpers):
- `test_load_metadata_json_*`: fichero no existe, corrupto, válido
- `test_get_siuo_columns_*`: formato dict, dict-of-dicts, lista, tabla no encontrada, case-insensitive, sin fichero
- `test_get_siuo_record_count_*`: record_count, row_count, no encontrado, sin fichero
- `test_extract_columns_*`: 4 patrones regex, contexto vacío, tabla no encontrada, input malformado
- `test_explore_table_fallback_to_siuo_json`: BD falla → columnas desde JSON ✅
- `test_explore_table_fallback_to_db_context`: BD falla + JSON vacío → columnas desde texto ✅
- `test_explore_table_all_sources_fail_no_exception`: todo falla → columnas=[], sin excepción ✅

---

### 9. DOCUMENTACIÓN: DEVIA_ROBUSTNESS.md actualizado
**Archivo:** `backend/modules/chat/DEVIA_ROBUSTNESS.md`

Añadida sección sobre DeepAnalysisAgent con:
- Arquitectura de fases y paquete
- Principios de diseño y resiliencia
- Reglas de negocio conocidas
- Cómo extender con nuevas subfases

---

## 📁 ARCHIVOS MODIFICADOS EN ESTA SESIÓN

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/modules/chat/deep_analysis/__init__.py` | **NUEVO** | Exportaciones del paquete |
| `backend/modules/chat/deep_analysis/models.py` | **NUEVO** | Modelos y detect_depth() |
| `backend/modules/chat/deep_analysis/agent.py` | **NUEVO** | Orquestador + helpers SIUO |
| `backend/modules/chat/deep_analysis/phases_1_2.py` | **NUEVO** | Fases 0, 1, 2 |
| `backend/modules/chat/deep_analysis/phases_3_4_5.py` | **NUEVO** | Fases 3, 4, 5 |
| `backend/modules/chat/deep_analysis_agent.py` | Modificado | Wrapper de compatibilidad |
| `backend/modules/chat/service.py` | Modificado | Integra agente + mejora prompt + deep_analysis flag |
| `backend/modules/chat/firebird_sql_constants.py` | Modificado | Fix DOCCAB LOW_RECORD_TABLES |
| `backend/modules/chat/DEVIA_ROBUSTNESS.md` | Modificado | Documentación actualizada |
| `backend/modules/outlook/router.py` | Modificado | Auth cache TTL fallos |
| `frontend/index.html` | Modificado | Checkbox deep-analysis-toggle en chat |
| `frontend/assets/js/modules/chat.js` | Modificado | Envía deep_analysis en POST |
| `frontend/assets/js/modules/siuo_render.js` | Modificado | Checkbox en Probar ContextRetriever |
| `frontend/assets/js/modules/siuo.js` | Modificado | _callDeepAnalysisAPI + _isSiuoDeepEnabled |
| `backend/core/config/unsolvable_errors.json` | **NUEVO** | Registro errores irresolubles |
| `tests/unit/test_deep_analysis_agent.py` | **NUEVO** | 71 tests unitarios |
| `tests/unit/test_regression_bugs.py` | **NUEVO** | Tests de regresión |
| `tests/unit/test_siuo_probar_integration.py` | **NUEVO** | Tests integración SIUO |

---

## 🔴 PRÓXIMOS PASOS

### PRIORIDAD 1 — Contexto de conversación en DeepAnalysisAgent
**Archivo:** `backend/modules/chat/deep_analysis/phases_1_2.py`

El agente recibe `conversation_history` pero en Fase 1 no lo usa para entender el contexto acumulado. Necesita incluirlo en el prompt de detección de intención para preguntas de seguimiento.

---

### PRIORIDAD 2 — Análisis de instalaciones únicas en presupuestos
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → `_build_fixed_sqls()`

Para presupuestos, añadir SQLs específicos que cuenten:
1. Total presupuestos (COUNT(*))
2. Instalaciones únicas (COUNT(DISTINCT CODCLIENTE || CODIGOOBRA) o similar)
3. Presupuestos por instalación (distribución)

Requiere conocer qué columna identifica la "instalación" en DOCCAB (puede ser CODIGOOBRA, REFERENCIA, o una combinación).

---

### PRIORIDAD 3 — Análisis por serie/año en respuesta
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → Fase 3 + Fase 5

Añadir siempre en Fase 3 un SQL de distribución temporal:
```sql
-- [OBJETIVO: Distribución por año y serie]
SELECT EXTRACT(YEAR FROM FECHA) AS AÑO, SERIE, COUNT(*) AS N,
       SUM(IMPORTETOTAL) AS TOTAL_EUR
FROM DOCCAB WHERE TIPO = 0
GROUP BY EXTRACT(YEAR FROM FECHA), SERIE
ORDER BY AÑO DESC, N DESC
```

Y en Fase 5, la síntesis debe incluir siempre una tabla por año/serie.

---

### PRIORIDAD 4 — Error SQL "Dynamic SQL Error" en tasa de éxito
**Archivo:** `backend/core/config/unsolvable_errors.json`

El error `Dynamic SQL Error / SQL error code = -104 / Unexpected` al preguntar por "tasa de éxito de presupuestos aceptados" está registrado como irresoluble. Necesita:
1. Revisar el SQL generado para esa pregunta
2. Añadir corrección determinista en `sql_corrector.py` o `firebird_sql_constants.py`
3. Marcar como `"status": "reviewed"` en `unsolvable_errors.json`

---

### PRIORIDAD 5 — Mejorar renderizado de respuesta DeepAgent en SIUO
**Archivo:** `frontend/assets/js/modules/siuo_render.js` → `renderTestResult()`

Cuando `source === "deep_agent"`, la respuesta es Markdown completo con tablas, advertencias HTML, etc. El renderizado actual funciona pero podría mejorar:
- Badge especial "🔬 DeepAgent" en lugar de "🧠 SIUO"
- Mostrar número de SQLs ejecutados si viene en la respuesta
- Mostrar score de fiabilidad si viene en la respuesta

---

### PRIORIDAD 6 — Tests de integración SIUO + DeepAgent
**Archivo nuevo:** `tests/unit/test_siuo_deep_integration.py`

Tests a implementar:
- `test_siuo_deep_enabled_calls_chat_send()` — checkbox marcado → llama a /api/chat/send
- `test_siuo_deep_disabled_calls_context_ask()` — checkbox desmarcado → llama a /api/siuo/context/ask
- `test_siuo_deep_response_normalized()` — respuesta de /api/chat/send normalizada correctamente

---

## 🏗️ PRINCIPIOS DE DISEÑO DEL PROYECTO (recordatorio)

1. **Ficheros < 500 líneas** — si crece, dividir en módulos
2. **Parámetros centralizados** — usar `firebird_sql_constants.py`, `config.json`, `network_audit_constants.py`
3. **Reutilización de código** — no duplicar lógica entre módulos
4. **Ultra-organizado en carpetas** — cada módulo en su directorio
5. **DEVIA por módulo** — cada módulo importante tiene su `.md` de documentación
6. **Ultra-resiliente** — try/except en cada operación, fallbacks siempre
7. **Autoconfigurable** — detectar IPs, puertos, tablas, columnas automáticamente
8. **Sin romper funcionalidades existentes** — fall-through si algo falla
9. **Analizar antes de actuar** — leer el código relevante antes de modificar

---

## 🔗 REFERENCIAS

- **Repo:** https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
- **Commit inicial sesión:** `7c0ec3e`
- **Commit intermedio:** `089ce03` — helpers SIUO + 71 tests
- **Commit final:** `24627bf` — fix /api/chat/send + checkbox SIUO
- **Branch:** `main`
- **Tests:** 71/71 pasan ✅
