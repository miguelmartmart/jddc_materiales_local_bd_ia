# 📋 RESUMEN DE SESIÓN — 16/03/2026
## Proyecto: DEVIA / bots/interjddcia
## Commit: `27e9aa7` → `main` (7c0ec3e → 27e9aa7)

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

### 3. NUEVO MÓDULO: DeepAnalysisAgent ÉPICO
**Archivo:** `backend/modules/chat/deep_analysis_agent.py` (nuevo, ~500 líneas)

Sistema ultra-resiliente de análisis multi-fase con **auto-detección de profundidad**:

#### Niveles de profundidad (auto-detectados):
| Nivel | SQLs | Tablas | Cuándo |
|-------|------|--------|--------|
| BASIC | 2 | 2 | Preguntas simples directas |
| MEDIUM | 4 | 4 | Listados, consultas moderadas |
| DEEP | 8 | 6 | Totales, rankings, comparativas |
| **EPIC** | **12** | **8** | **Por defecto — análisis, tasas, tendencias** |

#### Arquitectura de 5 fases (30+ subfases):

**FASE 1 — Comprensión Épica:**
- 1.1 Detección de intención (JSON estructurado)
- 1.2 Descomposición en sub-preguntas investigables
- 1.3 Identificación de tablas candidatas (determinista + IA)
- 1.4 Evaluación de profundidad requerida
- 1.5 Identificación de posibles problemas de datos

**FASE 2 — Exploración Total:**
- 2.1 Conteo REAL de registros en cada tabla
- 2.2 Columnas disponibles (desde RDB$RELATION_FIELDS)
- 2.3 Detección de columnas clave (FECHA, IMPORTE, CODCLIENTE, TIPO)
- 2.4 Muestreo de datos reales (primeras 3 filas)
- 2.5 Distribución por TIPO en DOCCAB (presupuestos, facturas, etc.)
- 2.6 Conteo de nulos en CODCLIENTE

**FASE 3 — Investigación Multi-Angular:**
- Genera hasta 12 SQLs desde distintos ángulos
- Cada SQL con objetivo declarado: `-- [OBJETIVO: descripción]`
- Ángulos: principal, calidad, duplicados, temporal, por cliente/agente, outliers, contexto, cruzado
- Auto-corrección de SQLs fallidos (hasta 2 reintentos + IA)
- Normalización automática con FirebirdSQLNormalizer

**FASE 4 — Análisis Crítico Profundo:**
- 4.1 Anomalías estadísticas
- 4.2 Calidad de datos
- 4.3 Contexto de negocio (climatización)
- 4.4 Limitaciones del SQL
- 4.5 Patrones ocultos (estacionalidad, concentración)
- 4.6 Hipótesis explicativas
- 4.7 Score de fiabilidad (alto/medio/bajo)

**FASE 5 — Síntesis Épica:**
- Respuesta principal con datos reales en tabla Markdown
- Análisis crítico
- Advertencias y objeciones (HTML coloreado)
- Contexto de negocio
- Sugerencias y próximos pasos
- Detalles técnicos en `<details>` desplegable

#### Principios de resiliencia:
- Cada subfase tiene `try/except` independiente
- Si una fase falla → continúa con lo que tiene
- Fallback de emergencia si todo falla
- Logs detallados de cada subfase

---

### 4. INTEGRACIÓN: DeepAnalysisAgent en service.py
**Archivo:** `backend/modules/chat/service.py`

**Activación:**
- Comando explícito: `/deep <pregunta>` o `/analisis <pregunta>`
- Palabras clave: "analiza en profundidad", "análisis completo", "investiga", "a fondo", etc.
- Fall-through al flujo normal si el agente falla (ultra-resiliente)

---

### 5. MEJORA: Outlook Auth Cache con TTL de fallos
**Archivo:** `backend/modules/outlook/router.py`

- `mark_failed(method_key)`: registra que un método de auth falló
- `is_known_failure(method_key)`: evita reintentar métodos fallidos durante 10 minutos
- Evita loops de autenticación fallida en cada poll

---

## 🔴 PRÓXIMOS PASOS EXACTOS

### PRIORIDAD 1 — Frontend: Checkbox "Análisis Profundo"
**Archivo:** `frontend/assets/js/modules/chat.js`

Añadir un checkbox marcado por defecto que active el modo análisis profundo:
```html
<label>
  <input type="checkbox" id="deep-analysis-toggle" checked>
  🔬 Análisis profundo
</label>
```
- Si está marcado → enviar `deep_analysis: true` en el body del POST `/api/chat`
- El backend en `service.py` debe leer `context.get('deep_analysis', True)` para activar el agente
- Actualmente se activa solo por palabras clave — con el checkbox se activa siempre

**Cambio en service.py:**
```python
# Activar si: checkbox marcado O palabras clave detectadas
if context.get('deep_analysis', False) or self._is_deep_analysis_request(message):
    # → DeepAnalysisAgent
```

---

### PRIORIDAD 2 — Contexto de conversación en DeepAnalysisAgent
**Archivo:** `backend/modules/chat/deep_analysis_agent.py`

El agente actualmente no usa el historial de conversación. Necesita:
- Recibir `conversation_history` en `analyze()`
- En Fase 1, incluir el historial para entender el contexto acumulado
- Ejemplo: si el usuario preguntó antes "¿cuántos presupuestos hay?" y ahora pregunta "¿y cuántos se aceptaron?", el agente debe entender la relación

---

### PRIORIDAD 3 — Análisis de instalaciones únicas en presupuestos
**Archivo:** `backend/modules/chat/deep_analysis_agent.py` → Fase 3

Para presupuestos, añadir SQLs específicos que cuenten:
1. Total presupuestos (COUNT(*))
2. Instalaciones únicas (COUNT(DISTINCT CODCLIENTE || CODIGOOBRA) o similar)
3. Presupuestos por instalación (distribución)

Esto requiere conocer qué columna identifica la "instalación" en DOCCAB (puede ser CODIGOOBRA, REFERENCIA, o una combinación).

**SQL de investigación a añadir en Fase 3:**
```sql
-- [OBJETIVO: Presupuestos vs instalaciones únicas]
SELECT 
  COUNT(*) AS TOTAL_PRESUPUESTOS,
  COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS,
  CAST(COUNT(*) AS NUMERIC(15,2)) / NULLIF(COUNT(DISTINCT CODCLIENTE), 0) AS PRESUPUESTOS_POR_CLIENTE
FROM DOCCAB WHERE TIPO = 0
```

---

### PRIORIDAD 4 — Análisis por serie/año en respuesta
**Archivo:** `backend/modules/chat/deep_analysis_agent.py` → Fase 3 + Fase 5

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

### PRIORIDAD 5 — Tests del DeepAnalysisAgent
**Archivo nuevo:** `tests/unit/test_deep_analysis_agent.py`

Tests a implementar:
- `test_detect_depth_epic()` — palabras clave → EPIC
- `test_detect_depth_basic()` — pregunta simple → BASIC
- `test_phase1_fallback()` — si IA falla, usa datos por defecto
- `test_phase2_exploration()` — mock de execute_sql
- `test_emergency_fallback()` — si todo falla, devuelve respuesta útil
- `test_full_analysis_mock()` — análisis completo con mocks

---

### PRIORIDAD 6 — DEVIA principal actualizado
**Archivo:** `backend/modules/chat/DEVIA_ROBUSTNESS.md`

Añadir sección sobre DeepAnalysisAgent con:
- Arquitectura de fases
- Principios de diseño
- Cómo extender con nuevas subfases
- Reglas de negocio conocidas (1 instalación = N presupuestos, etc.)

---

## 📁 ARCHIVOS MODIFICADOS EN ESTA SESIÓN

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/modules/chat/deep_analysis_agent.py` | **NUEVO** | Agente épico 5 fases |
| `backend/modules/chat/service.py` | Modificado | Integra agente + mejora prompt |
| `backend/modules/chat/firebird_sql_constants.py` | Modificado | Fix DOCCAB LOW_RECORD_TABLES |
| `backend/modules/outlook/router.py` | Modificado | Auth cache TTL fallos |
| `backend/core/utils/unsolvable_error_registry.py` | Nuevo | Registro errores irresolubles |
| `tests/unit/test_siuo_context_ask.py` | Nuevo | Tests SIUO |
| `tests/unit/test_unsolvable_registry.py` | Nuevo | Tests registry |
| `tests/unit/test_unsupported_functions.py` | Nuevo | Tests funciones no soportadas |

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

---

## 🔗 REFERENCIAS

- **Repo:** https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
- **Commit actual:** `27e9aa7`
- **Commit anterior:** `7c0ec3e`
- **Branch:** `main`
