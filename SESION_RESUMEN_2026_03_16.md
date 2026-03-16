# 📋 RESUMEN DE SESIÓN — 16/03/2026
## Proyecto: DEVIA / bots/interjddcia
## Branch: `pruebas` → commit `948a52e`

---

## ✅ LO IMPLEMENTADO EN ESTA SESIÓN

### 1. FIX CRÍTICO: Advertencia incorrecta de DOCCAB
**Archivo:** `backend/modules/chat/firebird_sql_constants.py`

- Eliminado `DOCCAB` de `LOW_RECORD_TABLES` (el `record_count: 3` era de muestras SIUO, no de la BD real)
- Añadidas tablas realmente vacías: `CONDICIO`, `EQUIVAL`, `CLIENTEDOCUM`

---

### 2. MEJORA: Prompt de interpretación WEB con análisis profundo
**Archivo:** `backend/modules/chat/service.py`

El `interpretation_system` ahora incluye análisis profundo obligatorio:
- Detección de duplicados, calidad de datos, anomalías estadísticas
- Contexto de negocio: 1 instalación puede tener N presupuestos
- Limitaciones del SQL, advertencias proactivas, sugerencias de mejora

---

### 3. NUEVO MÓDULO: DeepAnalysisAgent modular
**Directorio:** `backend/modules/chat/deep_analysis/` (nuevo)

| Archivo | Descripción |
|---------|-------------|
| `__init__.py` | Exports del módulo |
| `models.py` | AnalysisDepth, AnalysisContext, PhaseResult |
| `phases_1_2.py` | Fase1 comprensión épica + Fase2 exploración total |
| `phases_3_4_5.py` | Fase3 SQLs multi-angular + Fase4 crítico + Fase5 síntesis |
| `agent.py` | Orquestador 5 fases con conversation_history |

**Wrapper de compatibilidad:** `backend/modules/chat/deep_analysis_agent.py`

#### Niveles de profundidad (auto-detectados):
| Nivel | SQLs | Cuándo |
|-------|------|--------|
| BASIC | 2 | Preguntas simples |
| MEDIUM | 4 | Listados moderados |
| DEEP | 8 | Totales, rankings |
| **EPIC** | **12** | **Por defecto — análisis, tasas, tendencias** |

---

### 4. INTEGRACIÓN: DeepAnalysisAgent en service.py
**Archivo:** `backend/modules/chat/service.py`

- Checkbox frontend: `context.get('deep_analysis', False) == True`
- Comando explícito: `/deep`, `/analisis`
- Palabras clave ampliadas: "en profundidad", "tasa de éxito", "analiza", etc.
- **FIX CRÍTICO:** `sql_executor=` (no `execute_sql=`)
- **FIX:** `max(sql_blocks, key=len)` para elegir el SQL más completo
- Pasa `conversation_history` al agente

---

### 5. FRONTEND: Checkbox "Análisis Profundo"
**Archivos:** `frontend/index.html`, `frontend/assets/js/modules/chat.js`

- Checkbox dentro de `chat-input-area` con `flex-wrap: wrap`
- Label con `flex-shrink: 0` y `white-space: nowrap` (siempre visible)
- JS envía `deep_analysis: true` en el body del POST `/api/chat`

---

### 6. MEJORA: Outlook Auth Cache con TTL de fallos
**Archivo:** `backend/modules/outlook/router.py`

- `mark_failed(method_key)`: registra métodos de auth fallidos
- `is_known_failure(method_key)`: evita reintentar durante 10 minutos

---

### 7. TESTS
**Archivos nuevos:**

| Archivo | Tests | Descripción |
|---------|-------|-------------|
| `tests/unit/test_deep_analysis_agent.py` | 49 | Depth detection, fases, fallbacks, conversation_history |
| `tests/unit/test_regression_bugs.py` | 23 | BUG-001 execute_sql, BUG-002 checkbox, BUG-003 DOCDESTINO, BUG-004 SQL block |

**Resultado suite completa:** `886 passed, 64 skipped, 0 failed`

---

## 🔴 PRÓXIMOS PASOS

### PRIORIDAD 3 — Análisis de instalaciones únicas en presupuestos
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → Fase 3

Añadir SQLs específicos para presupuestos:
```sql
-- [OBJETIVO: Presupuestos vs instalaciones únicas]
SELECT 
  COUNT(*) AS TOTAL_PRESUPUESTOS,
  COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS,
  CAST(COUNT(*) AS NUMERIC(15,2)) / NULLIF(COUNT(DISTINCT CODCLIENTE), 0) AS PRESUPUESTOS_POR_CLIENTE
FROM DOCCAB WHERE TIPO = 0
```

---

### PRIORIDAD 4 — Generación dinámica de SQLs de contexto en Fase 3
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → Fase 3

**Principio:** La IA debe generar los SQLs de análisis dinámicamente basándose en lo que descubrió en Fase 2 (columnas reales, tipos de datos, distribuciones). NO hardcodear SQLs específicos para "año/serie" u otros casos concretos — eso solo funcionaría para esa pregunta y rompería la generalidad del agente.

**Cómo debe funcionar:**
- Fase 2 descubre: "DOCCAB tiene columna FECHA (DATE), SERIE (VARCHAR), IMPORTETOTAL (NUMERIC)"
- Fase 3 recibe ese contexto y la IA genera SQLs apropiados:
  - Si hay columna de fecha → genera SQL de distribución temporal
  - Si hay columna de importe → genera SQL de totales/medias
  - Si hay columna de tipo/serie → genera SQL de distribución por categoría
- El prompt de Fase 3 debe instruir a la IA: "Basándote en las columnas descubiertas en Fase 2, genera SQLs que exploren las dimensiones relevantes (temporal, categórica, numérica)"

**Mejora a implementar:** Enriquecer el prompt de Fase 3 para que la IA use los metadatos de Fase 2 como guía para decidir qué ángulos explorar, en lugar de tener ángulos hardcodeados.

---

### PRIORIDAD 6 — DEVIA_ROBUSTNESS.md actualizado
**Archivo:** `backend/modules/chat/DEVIA_ROBUSTNESS.md`

Añadir sección sobre DeepAnalysisAgent con arquitectura de fases,
principios de diseño y reglas de negocio conocidas.

---

## 📁 ARCHIVOS MODIFICADOS EN ESTA SESIÓN

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/modules/chat/deep_analysis/__init__.py` | **NUEVO** | Exports módulo |
| `backend/modules/chat/deep_analysis/models.py` | **NUEVO** | Modelos de datos |
| `backend/modules/chat/deep_analysis/phases_1_2.py` | **NUEVO** | Fases 1-2 |
| `backend/modules/chat/deep_analysis/phases_3_4_5.py` | **NUEVO** | Fases 3-4-5 |
| `backend/modules/chat/deep_analysis/agent.py` | **NUEVO** | Orquestador |
| `backend/modules/chat/deep_analysis_agent.py` | **NUEVO** | Wrapper compatibilidad |
| `backend/modules/chat/service.py` | Modificado | Integra agente + fixes |
| `backend/modules/chat/firebird_sql_constants.py` | Modificado | Fix DOCCAB |
| `backend/modules/outlook/router.py` | Modificado | Auth cache TTL |
| `frontend/index.html` | Modificado | Checkbox análisis profundo |
| `frontend/assets/js/modules/chat.js` | Modificado | Envía deep_analysis |
| `backend/modules/chat/DEVIA_ROBUSTNESS.md` | Modificado | Documentación |
| `tests/unit/test_deep_analysis_agent.py` | **NUEVO** | 49 tests agente |
| `tests/unit/test_regression_bugs.py` | **NUEVO** | 23 tests regresión |

---

## 🏗️ PRINCIPIOS DE DISEÑO DEL PROYECTO

1. **Ficheros < 500 líneas** — si crece, dividir en módulos
2. **Parámetros centralizados** — usar `firebird_sql_constants.py`, `config.json`
3. **Reutilización de código** — no duplicar lógica entre módulos
4. **Ultra-organizado en carpetas** — cada módulo en su directorio
5. **DEVIA por módulo** — cada módulo importante tiene su `.md`
6. **Ultra-resiliente** — try/except en cada operación, fallbacks siempre
7. **Autoconfigurable** — detectar IPs, puertos, tablas, columnas automáticamente
8. **Sin romper funcionalidades existentes** — fall-through si algo falla

---

## 🔗 REFERENCIAS

- **Repo:** https://github.com/miguelmartmart/jddccontafactexcel.git
- **Branch:** `pruebas`
- **Commit actual:** `948a52e`
- **Commit anterior:** `facd301`
