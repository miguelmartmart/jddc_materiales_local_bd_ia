# 📋 RESUMEN DE SESIÓN — 18/03/2026
## Proyecto: DEVIA / bots/interjddcia
## Commit: `c5e75b7` → `pruebas`

---

## ✅ LO IMPLEMENTADO EN ESTA SESIÓN

### 1. KnowledgeStore: Cache-First en Fase 2 + Persistencia Automática
**Archivo:** `backend/modules/chat/deep_analysis/phases_1_2.py`

**Problema:** Cada consulta re-exploraba las tablas desde la BD (COUNT, RDB$RELATION_FIELDS, muestreo), aunque ya se habían explorado antes. Costoso en tiempo y recursos.

**Solución — Cache-First (TTL 7 días):**
- Antes de explorar una tabla, se consulta el KnowledgeStore
- Si hay datos frescos (< 7 días): se usan directamente, **sin queries a la BD**
- Si los datos son obsoletos (> 7 días): se re-explora y se actualiza el cache
- `cfg["force_refresh"] = True` fuerza re-exploración aunque el cache sea fresco

**Solución — Persistencia automática:**
- Tras explorar una tabla desde la BD, los resultados se guardan en el KnowledgeStore
- Se persisten: columnas reales, conteo real, distribución TIPO, nulos CODCLIENTE, muestra
- Solo se persisten datos de fuente `firebird_rdb` (no de SIUO/contexto)
- Log de descubrimiento automático en `discoveries_log.jsonl`

**Resiliencia de metadatos (multi-fuente):**
1. RDB$RELATION_FIELDS (BD real) → fuente preferida
2. db_metadata_optimized.json (SIUO) → fallback si BD no disponible
3. db_context (texto libre del esquema) → fallback final
4. Columnas vacías → el agente continúa con lo que tiene

---

### 2. Fix CRÍTICO: HTML crudo visible en el chat
**Archivo:** `backend/modules/chat/deep_analysis/agent.py`

**Problema:** `_build_warnings_html()` generaba `<div style="...">` con anomalías que eran **objetos Python** serializados como texto:
```
{'type': 'anomalia_estadistica', 'description': 'El 99.1% de los presupuestos...', 'value': 0.0995, ...}
```
El frontend no renderizaba el HTML → aparecía como texto crudo con etiquetas visibles.

**Solución:**
- `_build_warnings_html()` renombrado conceptualmente a "build_warnings_markdown"
- Genera **Markdown puro** (sin HTML) con `### 🔴 Anomalías detectadas` y listas `-`
- Nueva función `_to_text(item)` que convierte dicts a texto legible:
  - Extrae campo `description`, `details`, `message`, `text`, `rule` o `reason`
  - Fallback: concatena los valores más relevantes del dict
- Resultado: las anomalías aparecen como texto legible en el chat

**Además:** `_strip_html_from_markdown()` en Fase 5 limpia cualquier HTML residual que la IA genere en el texto Markdown (convierte `<div>` → texto, `<strong>` → `**bold**`, etc.)

---

### 3. Fix CRÍTICO: Tasa de éxito de presupuestos incorrecta (~10%)
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py`

**Problema:** El sistema calculaba la tasa de éxito solo via DOCDESTINO (presupuestos con documento destino vinculado), obteniendo ~10%. Pero DOCDESTINO puede no ser el indicador correcto de "aceptado" — la columna real puede ser ESTADOPEND o ESTADOPENDVENCOM.

**Solución — Nuevos SQLs fijos en `_build_fixed_sqls()`:**

| SQL | Objetivo |
|-----|----------|
| **3e** | `ESTADOPENDVENCOM` distribución — estado desde el punto de vista del vendedor/comercial |
| **3f** | Cruce `ESTADOPEND × ESTADOPENDVENCOM` — combinación que define "aceptado" en este negocio |
| **3g** | Presupuestos convertidos a factura (TIPO=13), pedido (TIPO=12) o albarán (TIPO=11) via DOCDESTINO |
| **3h** | Muestra de 10 presupuestos con valores reales de ESTADOPEND y ESTADOPENDVENCOM |

**Lógica:** El sistema ahora investiga **3 definiciones posibles de "aceptado"**:
1. `ESTADOPEND` con valor específico (ej: 1, 2, "A")
2. `ESTADOPENDVENCOM` con valor específico (estado comercial)
3. Conversión a factura/pedido via DOCDESTINO (más fiable)

La IA en Fase 4 y Fase 5 recibe todos estos datos y puede determinar cuál es la definición correcta para este negocio específico.

---

### 4. Persistencia de ESTADOPENDVENCOM en KnowledgeStore (Fase 4b)
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py`

Nuevos bloques de persistencia en `_phase4b_learn_and_persist()`:

- **ESTADOPENDVENCOM**: distribución + nota explicativa → `DOCCAB.estadopendvencom_distribution`
- **Cruce ESTADOPEND × ESTADOPENDVENCOM**: mapa de combinaciones → `DOCCAB.estadopend_cruce`
- **Conversión factura/pedido**: conteos por tipo → `DOCCAB.conversion_distribution`
- **Regla de negocio automática**: si hay conversiones, se registra la definición de "aceptado"

Esto significa que en la **segunda consulta** sobre tasa de éxito, el sistema ya sabe:
- Qué valores de ESTADOPEND/ESTADOPENDVENCOM indican "aceptado"
- Cuántos presupuestos se convierten a factura vs pedido
- La definición correcta de "aceptado" para este negocio

---

## 🔴 PROBLEMAS PENDIENTES / PRÓXIMOS PASOS

### PRIORIDAD 1 — Investigar por qué la tasa real puede ser mayor del 10%
El sistema ahora tiene los SQLs correctos. Pero necesita que la **Fase 5 (síntesis)** interprete correctamente los valores de ESTADOPEND/ESTADOPENDVENCOM.

**Acción necesaria:** Tras la próxima ejecución, revisar en los logs:
- ¿Qué valores tiene ESTADOPENDVENCOM? (ej: 0=pendiente, 1=aceptado, 2=rechazado)
- ¿Cuántos presupuestos tienen ESTADOPENDVENCOM=1 (o el valor de "aceptado")?
- ¿Coincide con la tasa via DOCDESTINO o es diferente?

Si los valores son numéricos (0, 1, 2), añadir en `_sub_identify_issues()`:
```python
issues.append("ESTADOPEND/ESTADOPENDVENCOM: verificar qué valor numérico significa 'aceptado'")
```

### PRIORIDAD 2 — Prompt de Fase 5 con contexto de ESTADOPEND conocido
**Archivo:** `backend/modules/chat/deep_analysis/phases_3_4_5.py` → `_phase5_synthesize()`

Si el KnowledgeStore ya tiene `estadopendvencom_distribution`, incluirlo en el prompt de Fase 5:
```python
# Añadir al user_msg de Fase 5:
vencom_dist = store.get_table("DOCCAB").get("estadopendvencom_distribution", {})
if vencom_dist:
    user_msg += f"\nESTADOPENDVENCOM conocido: {vencom_dist}"
```

### PRIORIDAD 3 — Análisis de columnas con datos en posición incorrecta
El feedback menciona que hay registros donde la información está en columnas que no deberían tenerla. El sistema ya detecta esto en Fase 4 (`structural_issues`), pero necesita:
- SQLs específicos para detectar patrones de datos mixtos en DOCCAB (no solo ARTICULO)
- Análisis de columnas de texto que contienen códigos, fechas o importes

### PRIORIDAD 4 — Optimización de tokens para preguntas simples
El sistema usa EPIC (12 SQLs) por defecto. Para preguntas simples como "¿cuántos clientes hay?", debería usar BASIC (2 SQLs). Revisar `detect_depth()` en `models.py` para que sea más preciso.

### PRIORIDAD 5 — Tests actualizados
**Archivo:** `tests/unit/test_deep_analysis_agent.py`

Añadir tests para:
- `test_build_warnings_markdown()` — verifica que no hay HTML en la salida
- `test_to_text_dict()` — verifica extracción de texto de dicts
- `test_fixed_sqls_estadopendvencom()` — verifica que se generan los SQLs 3e-3h
- `test_phase4b_vencom_persistence()` — verifica persistencia de ESTADOPENDVENCOM

---

## 📁 ARCHIVOS MODIFICADOS EN ESTA SESIÓN

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/modules/chat/deep_analysis/phases_1_2.py` | Modificado | Cache-first KnowledgeStore + persistencia automática |
| `backend/modules/chat/deep_analysis/phases_3_4_5.py` | Modificado | SQLs 3e-3h para tasa éxito + persistencia ESTADOPENDVENCOM |
| `backend/modules/chat/deep_analysis/agent.py` | Modificado | Fix HTML→Markdown en warnings + _to_text() |

---

## 🏗️ ARQUITECTURA DEL SISTEMA (estado actual)

```
DeepAnalysisAgent v3.0
├── Fase 0: Presupuesto tokens + optimización LAN
├── Fase 1: Comprensión épica (intención, sub-preguntas, tablas)
│   └── KnowledgeStore: enriquece tablas candidatas con datos conocidos
├── Fase 2: Exploración total
│   ├── CACHE-FIRST: usa KnowledgeStore si datos < 7 días
│   ├── EXPLORACIÓN REAL: BD → RDB$RELATION_FIELDS → SIUO → db_context
│   └── PERSISTENCIA: guarda resultados en KnowledgeStore
├── BUCLE (hasta MAX_INVESTIGATION_CYCLES):
│   ├── Fase 3: Investigación multi-angular
│   │   ├── SQLs dinámicos (IA)
│   │   └── SQLs fijos: temporal, instalaciones, ESTADOPEND, ESTADOPENDVENCOM,
│   │       cruce estados, conversión factura/pedido, muestra valores reales
│   ├── Fase 4: Análisis crítico (anomalías, calidad, estructural, hipótesis)
│   ├── Fase 3b: Resolución de inconsistencias detectadas
│   └── Decisión IA: ¿continuar o parar?
├── Fase 4b: Aprendizaje permanente (KnowledgeStore)
│   ├── Columnas reales, conteos, distribuciones
│   ├── ESTADOPEND, ESTADOPENDVENCOM, cruce, conversión
│   └── Reglas de negocio + patrones SQL exitosos
└── Fase 5: Síntesis épica
    ├── Markdown puro (SIN HTML)
    ├── Advertencias como Markdown (no divs)
    └── _strip_html_from_markdown() limpia residuos
```

---

## 🔗 REFERENCIAS

- **Repo:** https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
- **Commit actual:** `c5e75b7`
- **Branch:** `pruebas`
- **Sesión anterior:** `SESION_RESUMEN_2026_03_17.md`
