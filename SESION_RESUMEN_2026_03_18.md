# 📋 RESUMEN DE SESIÓN — 18/03/2026
## Proyecto: DEVIA / bots/interjddcia
## Commit: `5814863` → `d013827` (main)

---

## ✅ LO IMPLEMENTADO EN ESTA SESIÓN

### 1. PARÁMETROS CENTRALIZADOS DEL BUCLE
**Archivo:** `backend/modules/chat/deep_analysis/models.py`

Añadidas constantes centralizadas para el bucle de investigación iterativa:
```python
MAX_INVESTIGATION_CYCLES: int = 4      # Máx ciclos del bucle
MIN_ISSUES_TO_CONTINUE: int = 1        # Mín anomalías para continuar
RELIABILITY_EXIT_THRESHOLD: str = "alto"  # Fiabilidad para salir
MAX_SQLS_PER_CYCLE: int = 6            # Máx SQLs adicionales por ciclo
```
También añadido `investigation_cycles: int = 0` en `EpicAnalysisResult` para tracking.

---

### 2. BUCLE DE INVESTIGACIÓN ITERATIVA — DeepAnalysisAgent v3.0
**Archivo:** `backend/modules/chat/deep_analysis/agent.py`

**Arquitectura del bucle:**
```
Fase 0 → Fase 1 → Fase 2 → BUCLE(hasta MAX_INVESTIGATION_CYCLES):
    Fase 3 (SQLs) → Fase 4 (análisis) → Fase 3b (resolución)
    → _should_continue_investigation() → continuar/salir
→ Fase 4b (aprendizaje) → Fase 5 (síntesis)
```

**Criterios de SALIDA del bucle (deterministas + IA):**
1. Último ciclo alcanzado (`cycle >= MAX_INVESTIGATION_CYCLES - 1`)
2. Presupuesto de tokens casi agotado (>85%)
3. Fiabilidad "alto" + pocas anomalías → análisis completo
4. Sin anomalías ni warnings → convergió
5. IA decide explícitamente (`_ai_continue_decision`)

**`_ai_continue_decision`:** La IA evalúa si hay más que investigar:
- ¿Columnas con contenido mixto sin resolver?
- ¿Registros con estructura heterogénea?
- ¿Hipótesis sin verificar?
- Devuelve JSON: `{"continue": bool, "reason": str, "new_angles": [...]}`

**Optimización de ciclos > 0:** En ciclos adicionales, `max_sqls` se limita a `MAX_SQLS_PER_CYCLE` para no saturar el contexto.

**Import a nivel de módulo:** `get_knowledge_store` importado al nivel del módulo (no dentro de funciones) para permitir mocking correcto en tests.

---

### 3. DETECCIÓN DE INCONSISTENCIAS ESTRUCTURALES — Fase 4
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py`

**Problema del usuario:** Los datos pueden tener:
- Datos en columnas incorrectas (ej: código en campo descripción)
- Columnas con contenido MIXTO (ej: `"COD001 - Nombre - Descripción"` en un campo)
- Registros con estructura HETEROGÉNEA (algunos con código+nombre, otros sin)
- Formatos de datos distintos en la misma columna

**Solución:** Añadida dimensión 3 obligatoria en el prompt de Fase 4:
```
3. INCONSISTENCIAS ESTRUCTURALES (MUY IMPORTANTE):
   - Datos en columnas incorrectas
   - Columnas con contenido MIXTO
   - Registros con estructura HETEROGÉNEA
   - Formatos de datos distintos en la misma columna
   - Campos numéricos con texto
```

El JSON de respuesta ahora incluye `"structural_issues": []` además de los campos anteriores.

---

### 4. SQLs DE RESOLUCIÓN DE CONTENIDO MIXTO — Fase 3b
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → `_build_resolution_sqls`

**RESOLUCIÓN 4 (nueva):** Cuando se detectan inconsistencias estructurales:
```sql
-- Muestra de DESCRIPCION/NOMBRE en ARTICULO para detectar contenido mixto
SELECT FIRST 20 CODIGO, DESCRIPCION, NOMBRE FROM ARTICULO
WHERE DESCRIPCION IS NOT NULL ORDER BY CODIGO

-- Registros con contenido mixto (patrón COD - NOMBRE)
SELECT FIRST 20 CODIGO, DESCRIPCION FROM ARTICULO
WHERE DESCRIPCION LIKE '% - %' OR DESCRIPCION LIKE '%|%' OR DESCRIPCION LIKE '%;%'

-- Proporción de registros con vs sin código en DESCRIPCION
SELECT
  SUM(CASE WHEN DESCRIPCION LIKE '% - %' THEN 1 ELSE 0 END) AS CON_SEPARADOR,
  SUM(CASE WHEN DESCRIPCION NOT LIKE '% - %' OR DESCRIPCION IS NULL THEN 1 ELSE 0 END) AS SIN_SEPARADOR,
  COUNT(*) AS TOTAL
FROM ARTICULO
```

**Resiliencia:** `_phase4b_learn_and_persist` ahora captura excepciones de `get_knowledge_store()` con `try/except` explícito.

---

### 5. TESTS — 215/215 ✅
**Archivos:** `tests/unit/test_deep_analysis_agent.py`, `tests/unit/test_knowledge_store.py`

Todos los tests pasan. Correcciones aplicadas:
- `get_knowledge_store` importado a nivel de módulo en `agent.py` (permite mocking con `patch`)
- `_phase4b_learn_and_persist` captura excepción de `get_knowledge_store()` (test de resiliencia)

---

## 🔴 PRÓXIMOS PASOS EXACTOS

### PRIORIDAD 1 — Frontend: Checkbox "Análisis Profundo"
**Archivo:** `frontend/assets/js/modules/chat.js`

Añadir checkbox marcado por defecto:
```html
<label>
  <input type="checkbox" id="deep-analysis-toggle" checked>
  🔬 Análisis profundo
</label>
```
- Si marcado → enviar `deep_analysis: true` en el body del POST `/api/chat`
- `service.py`: `if context.get('deep_analysis', False) or self._is_deep_analysis_request(message):`

---

### PRIORIDAD 2 — Tests del bucle de investigación
**Archivo:** `tests/unit/test_deep_analysis_agent.py`

Tests a añadir:
- `test_investigation_loop_exits_on_max_cycles()` — bucle sale al llegar al máximo
- `test_investigation_loop_exits_on_high_reliability()` — sale si fiabilidad=alto + pocas anomalías
- `test_investigation_loop_exits_on_convergence()` — sale si sin anomalías
- `test_should_continue_returns_false_last_cycle()` — criterio determinista
- `test_ai_continue_decision_returns_dict()` — IA devuelve JSON válido
- `test_structural_issues_in_phase4_prompt()` — prompt incluye dimensión 3

---

### PRIORIDAD 3 — Detección de contenido mixto en más tablas
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → `_build_resolution_sqls`

Actualmente solo detecta en `ARTICULO.DESCRIPCION`. Ampliar a:
- `CLIENTE.NOMBRE` — puede tener código+nombre
- `DOCCAB.OBSERVACIONES` — puede tener datos estructurados en texto libre
- Cualquier tabla con columnas de tipo texto largo

SQL genérico de detección:
```sql
-- Detectar columnas de texto con contenido mixto en cualquier tabla
SELECT FIRST 20 RDB$RELATION_NAME, RDB$FIELD_NAME
FROM RDB$RELATION_FIELDS rf
JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
WHERE f.RDB$FIELD_TYPE IN (37, 40)  -- VARCHAR, BLOB TEXT
AND rf.RDB$SYSTEM_FLAG = 0
ORDER BY rf.RDB$RELATION_NAME, rf.RDB$FIELD_POSITION
```

---

### PRIORIDAD 4 — Documentación DEVIA_ROBUSTNESS.md
**Archivo:** `backend/modules/chat/DEVIA_ROBUSTNESS.md`

Añadir sección sobre el bucle de investigación:
- Arquitectura del bucle (diagrama ASCII)
- Criterios de salida (deterministas + IA)
- Cómo extender con nuevos criterios
- Principio: "No basta con advertir — hay que RESOLVER"
- Reglas de negocio conocidas sobre calidad de datos

---

## 📁 ARCHIVOS MODIFICADOS EN ESTA SESIÓN

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/modules/chat/deep_analysis/models.py` | Modificado | Parámetros del bucle centralizados |
| `backend/modules/chat/deep_analysis/agent.py` | Modificado | v3.0 con bucle iterativo |
| `backend/modules/chat/deep_analysis/phases_3_4_5.py` | Modificado | Detección datos mixtos + resiliencia |

---

## 🏗️ PRINCIPIOS DE DISEÑO DEL PROYECTO (recordatorio)

1. **Ficheros < 500 líneas** — si crece, dividir en módulos
2. **Parámetros centralizados** — usar `models.py`, `firebird_sql_constants.py`, `config.json`
3. **Reutilización de código** — no duplicar lógica entre módulos
4. **Ultra-organizado en carpetas** — cada módulo en su directorio
5. **DEVIA por módulo** — cada módulo importante tiene su `.md` de documentación
6. **Ultra-resiliente** — try/except en cada operación, fallbacks siempre
7. **Autoconfigurable** — detectar IPs, puertos, tablas, columnas automáticamente
8. **Sin romper funcionalidades existentes** — fall-through si algo falla
9. **Tests primero** — 215/215 siempre verde antes de commit

---

## 🔗 REFERENCIAS

- **Repo:** https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
- **Commit actual:** `d013827`
- **Commit anterior:** `5814863`
- **Branch:** `main`
