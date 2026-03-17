# 📋 RESUMEN DE SESIÓN — 17/03/2026
## Proyecto: DEVIA / bots/interjddcia
## Sesión: continuación de 16/03/2026

---

## ✅ LO IMPLEMENTADO EN ESTA SESIÓN

### 1. REFACTORIZACIÓN: DeepAnalysisAgent dividido en módulos
**Directorio:** `backend/modules/chat/deep_analysis/`

El monolito `deep_analysis_agent.py` (~500 líneas) se dividió en módulos especializados:

| Archivo | Responsabilidad |
|---------|----------------|
| `agent.py` | Orquestador principal, helpers compartidos, metadatos SIUO |
| `phases_1_2.py` | Fases 0, 1, 2 (presupuesto tokens, comprensión, exploración) |
| `phases_3_4_5.py` | Fases 3, 4, 5 (investigación, análisis, síntesis) |
| `models.py` | Dataclasses, enums, constantes |
| `knowledge_store.py` | Aprendizaje permanente (nuevo) |
| `__init__.py` | Exports públicos |

---

### 2. NUEVO MÓDULO: KnowledgeStore — Aprendizaje Permanente Épico
**Archivo:** `backend/modules/chat/deep_analysis/knowledge_store.py`

Sistema de aprendizaje permanente que persiste en disco (`core/config/knowledge/`):

#### Estructura en disco:
```
core/config/knowledge/
  tables/DOCCAB.json          ← metadatos reales por tabla
  tables/CLIENTE.json
  index.json                  ← índice de tablas conocidas
  business_rules.json         ← reglas de negocio descubiertas
  query_patterns.json         ← patrones SQL exitosos
  discoveries_log.jsonl       ← log append-only de descubrimientos
```

#### Qué aprende automáticamente:
- **Columnas reales** de cada tabla (desde RDB$RELATION_FIELDS)
- **Conteos reales** de registros (no los de SIUO)
- **Distribución de TIPO** en DOCCAB (presupuestos, facturas, etc.)
- **Distribución de ESTADOPEND** en presupuestos
- **Relación DOCDESTINO** (% presupuestos con documento destino)
- **Reglas de negocio** descubiertas por la IA (insights)
- **Patrones SQL exitosos** con su objetivo, tablas y fiabilidad

#### Garantías:
- **GARANTÍA LAN**: No se envía ningún dato a internet
- **Ultra-resiliente**: try/except en cada operación, nunca lanza excepción
- **Append-only log**: `discoveries_log.jsonl` nunca se sobreescribe
- **Singleton**: `get_knowledge_store()` devuelve siempre la misma instancia

---

### 3. NUEVA FASE 4b: Aprendizaje Permanente
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py`

Se ejecuta entre Fase 4 (análisis) y Fase 5 (síntesis). Persiste en KnowledgeStore:
- Metadatos de tablas exploradas en Fase 2
- ESTADOPEND, DOCDESTINO, columnas de estado descubiertas en Fase 3
- Reglas de negocio e insights de Fase 4
- Patrones SQL exitosos de Fase 3

---

### 4. NUEVOS SQLs FIJOS en Fase 3 (investigación de estado)
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → `_build_fixed_sqls()`

Para preguntas sobre presupuestos/tasa/éxito, se añaden SIEMPRE:

```sql
-- [OBJETIVO: Distribución de ESTADOPEND en presupuestos (estado real)]
SELECT ESTADOPEND, COUNT(*) AS N FROM DOCCAB WHERE TIPO = 0
GROUP BY ESTADOPEND ORDER BY N DESC

-- [OBJETIVO: Presupuestos aceptados por tipo de documento destino]
SELECT d.TIPO AS TIPO_DESTINO, COUNT(DISTINCT dd.CODDOCUMENTO) AS N_PRESUPUESTOS
FROM DOCDESTINO dd
JOIN DOCCAB c ON c.CODIGO = dd.CODDOCUMENTO AND c.TIPO = 0
JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO
GROUP BY d.TIPO ORDER BY N_PRESUPUESTOS DESC

-- [OBJETIVO: Total presupuestos con cualquier documento destino vinculado]
SELECT COUNT(DISTINCT c.CODIGO) AS TOTAL_PRESUPUESTOS,
       COUNT(DISTINCT dd.CODDOCUMENTO) AS CON_DESTINO,
       COUNT(DISTINCT c.CODIGO) - COUNT(DISTINCT dd.CODDOCUMENTO) AS SIN_DESTINO
FROM DOCCAB c LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
WHERE c.TIPO = 0

-- [OBJETIVO: Columnas de DOCCAB que contienen ESTADO o ACEPTA (metadatos BD)]
SELECT FIRST 20 RDB$FIELD_NAME FROM RDB$RELATION_FIELDS
WHERE RDB$RELATION_NAME = 'DOCCAB'
AND (UPPER(RDB$FIELD_NAME) LIKE '%ESTADO%' OR UPPER(RDB$FIELD_NAME) LIKE '%ACEPTA%'
     OR UPPER(RDB$FIELD_NAME) LIKE '%SEGUIM%' OR UPPER(RDB$FIELD_NAME) LIKE '%RESULT%')
ORDER BY RDB$FIELD_POSITION
```

---

### 5. FIX BUG: response=None en Fase 3 → TypeError re.search
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py`

**Problema:** Si la IA devolvía `None` (timeout LAN), `re.search(r'<!--...-->', None)` lanzaba `TypeError`.

**Solución:** Guardia explícita antes del `re.search`:
```python
if not response or not isinstance(response, str):
    logger.warning("[DEEP AGENT] Fase 3: respuesta IA vacía — usando solo SQLs fijos")
    await self._execute_fixed_sqls(fixed_sqls, result, phase)
    phase.success = len(result.sql_queries) > 0
    return phase
```

---

### 6. FIX RENDIMIENTO: Límite de tokens SIUO para modelo LAN
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → `_get_siuo_context()`

**Problema:** El SIUO enviaba todo el contexto (~8000 tokens) al modelo LAN, que tiene timeout de 60s.

**Solución:** Límite estricto de 3000 tokens para el contexto SIUO:
```python
max_tokens = min(1500 + n_sqls * 100, 3000)
```

---

### 7. OPTIMIZACIÓN: Prompt conciso para modelo LAN (sin pérdida de calidad)
**Archivos:** `agent.py` → `_phase0_lan_optimize()`, `phases_3_4_5.py` → `_build_phase3_system()`

**Estrategia:** No reducir SQLs, sino reducir el TEXTO del prompt:
- `_phase0_lan_optimize()`: detecta si el modelo es LAN y cuenta patrones en KnowledgeStore
- `_build_phase3_system(lan_mode=True)`: prompt conciso (mismos SQLs, menos instrucciones)
- `_get_known_patterns_text()`: incluye patrones ya conocidos → la IA genera solo los NUEVOS

**Resultado:** Misma calidad (o mejor por KnowledgeStore), menos tiempo de generación.

---

### 8. DOCUMENTACIÓN: DEVIA_KNOWLEDGE_STORE.md
**Archivo:** `backend/modules/chat/deep_analysis/DEVIA_KNOWLEDGE_STORE.md`

Documentación completa del KnowledgeStore con:
- Arquitectura y estructura en disco
- Qué aprende y cómo
- Cómo extender con nuevos tipos de descubrimiento
- Reglas de negocio conocidas
- Garantías de privacidad (LAN)

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

**Cambio en service.py:**
```python
if context.get('deep_analysis', False) or self._is_deep_analysis_request(message):
    # → DeepAnalysisAgent
```

---

### PRIORIDAD 2 — Usar KnowledgeStore en Fase 1 (tablas candidatas)
**Archivo:** `backend/modules/chat/deep_analysis/phases_1_2.py` → `_sub_identify_tables()`

El KnowledgeStore ya sabe qué tablas tienen datos reales. Usarlo en Fase 1:
```python
# Si KnowledgeStore tiene tablas conocidas para esta intención → usarlas primero
store = get_knowledge_store()
known_tables = store.get_tables_for_intent(keywords)
tables = known_tables + deterministic_tables  # KnowledgeStore primero
```

---

### PRIORIDAD 3 — Usar KnowledgeStore en Fase 2 (columnas conocidas)
**Archivo:** `backend/modules/chat/deep_analysis/phases_1_2.py` → `_explore_table()`

Si RDB$RELATION_FIELDS falla Y el KnowledgeStore tiene columnas reales → usarlas:
```python
# Fuente 1.5: KnowledgeStore (columnas reales de sesiones anteriores)
if not columns_from_db:
    ks_cols = store.get_table_columns(table)  # columnas_real del KnowledgeStore
    if ks_cols:
        info["columns"] = ks_cols
        info["columns_source"] = "knowledge_store"
```

---

### PRIORIDAD 4 — Tests del DeepAnalysisAgent refactorizado
**Archivo:** `tests/unit/test_deep_analysis_agent.py`

Tests a actualizar/añadir:
- `test_phase0_lan_optimize_detects_lan()` — detecta modelo LAN
- `test_phase0_lan_optimize_counts_patterns()` — cuenta patrones KnowledgeStore
- `test_build_phase3_system_lan_mode()` — prompt conciso en LAN
- `test_get_known_patterns_text()` — patrones del KnowledgeStore en prompt
- `test_phase4b_persists_estadopend()` — ESTADOPEND se persiste
- `test_phase4b_persists_docdestino()` — DOCDESTINO se persiste
- `test_knowledge_store_get_patterns_for_intent()` — búsqueda por keywords

---

### PRIORIDAD 5 — Integrar KnowledgeStore en Fase 5 (síntesis)
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → `_phase5_synthesize()`

Incluir en el prompt de Fase 5 las reglas de negocio del KnowledgeStore:
```python
store = get_knowledge_store()
business_rules = store.get_business_rules(table="DOCCAB")
rules_text = "\n".join(f"• {r['rule']}" for r in business_rules[:5])
# Añadir al user_msg: f"REGLAS DE NEGOCIO CONOCIDAS:\n{rules_text}\n\n"
```

---

### PRIORIDAD 6 — DEVIA_ROBUSTNESS.md actualizado
**Archivo:** `backend/modules/chat/DEVIA_ROBUSTNESS.md`

Añadir sección sobre:
- Arquitectura modular del DeepAnalysisAgent
- KnowledgeStore y aprendizaje permanente
- Optimización LAN (prompt conciso + patrones conocidos)
- Flujo completo de las 5+1 fases

---

## 📁 ARCHIVOS MODIFICADOS EN ESTA SESIÓN

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/modules/chat/deep_analysis/agent.py` | Modificado | `_phase0_lan_optimize()`, `_phase0_lan_cap` → `_phase0_lan_optimize` |
| `backend/modules/chat/deep_analysis/phases_3_4_5.py` | Modificado | `_build_phase3_system(lan_mode, known_patterns_text)`, `_get_known_patterns_text()`, SQLs fijos ESTADOPEND/DOCDESTINO/RDB$, fix response=None |
| `backend/modules/chat/deep_analysis/knowledge_store.py` | **NUEVO** | KnowledgeStore épico con aprendizaje permanente |
| `backend/modules/chat/deep_analysis/DEVIA_KNOWLEDGE_STORE.md` | **NUEVO** | Documentación del KnowledgeStore |
| `backend/modules/chat/deep_analysis/__init__.py` | Modificado | Exports de KnowledgeStore |
| `SESION_RESUMEN_2026_03_17.md` | **NUEVO** | Este resumen |

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
9. **Aprendizaje permanente** — KnowledgeStore mejora con cada consulta
10. **Calidad sin sacrificar rendimiento** — prompt conciso LAN, no menos SQLs

---

## 🔗 REFERENCIAS

- **Repo:** https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
- **Branch:** `main`
- **Sesión anterior:** `SESION_RESUMEN_2026_03_16.md` (commit `27e9aa7`)
