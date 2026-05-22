# DEVIA — Robustez y Arquitectura del Sistema de Chat IA

## Módulo: `backend/modules/chat/`

---

## 1. Visión General

El módulo de chat implementa un sistema de análisis de datos en lenguaje natural sobre Firebird 2.5, con dos modos de operación:

| Modo | Activación | Descripción |
|------|-----------|-------------|
| **Normal** | Por defecto | SQL único + interpretación WEB |
| **Análisis Profundo** | Checkbox frontend / palabras clave / `/deep` | DeepAnalysisAgent 5 fases |

---

## 2. DeepAnalysisAgent — Arquitectura Multi-Fase

### 2.1 Estructura de ficheros

```
backend/modules/chat/
├── deep_analysis_agent.py          ← Shim de compatibilidad (re-exporta)
└── deep_analysis/                  ← Paquete real (<500 líneas cada fichero)
    ├── __init__.py                 ← Exportaciones públicas
    ├── models.py                   ← Dataclasses, Enums, TokenBudget, detect_depth
    ├── phases_1_2.py               ← Fases 0, 1, 2 (comprensión + exploración)
    ├── phase2_explore.py           ← Exploración de tablas (Fase 2)
    ├── phase3.py                   ← Generación de SQLs (Fase 3)
    ├── phase4.py                   ← Análisis crítico (Fase 4)
    ├── phases_3_4_5.py             ← Fases 3, 4, 5 (investigación + análisis + síntesis)
    ├── helpers.py                  ← Helpers: SIUO, _phase0_lan_optimize, etc.
    ├── knowledge_store.py          ← KnowledgeStore: aprendizaje permanente
    └── agent.py                    ← DeepAnalysisAgent (orquestador)
```

### 2.2 Niveles de profundidad (auto-detectados)

| Nivel | SQLs | Tablas | Cuándo |
|-------|------|--------|--------|
| BASIC | 2 | 2 | Preguntas simples directas |
| MEDIUM | 4 | 4 | Listados, consultas moderadas |
| DEEP | 8 | 6 | Totales, rankings, comparativas |
| **EPIC** | **12** | **8** | **Por defecto — análisis, tasas, tendencias** |

La detección es determinista (palabras clave) y siempre cae en EPIC si no hay match claro.

### 2.3 Arquitectura de 5 fases

```
FASE 0: Presupuesto de tokens + optimización LAN
  ├─ Ajusta max_sqls y explore_tables según tokens disponibles
  ├─ Detecta si el modelo es LAN (jddcia) o internet
  └─ Carga patrones conocidos del KnowledgeStore (known_sqls_count)

FASE 1: Comprensión Épica
  ├─ 1.1 Detección de intención (JSON estructurado)
  ├─ 1.2 Descomposición en sub-preguntas
  ├─ 1.3 Identificación de tablas candidatas (determinista + IA)
  ├─ 1.4 Evaluación de profundidad requerida
  └─ 1.5 Identificación de posibles problemas de datos

FASE 2: Exploración Total
  ├─ Conteo REAL de registros en cada tabla
  ├─ Columnas disponibles (RDB$RELATION_FIELDS)
  ├─ Detección de columnas clave (FECHA, IMPORTE, CODCLIENTE, TIPO)
  ├─ Muestreo de datos reales (primeras 3 filas)
  ├─ Distribución por TIPO en DOCCAB
  ├─ Conteo de nulos en CODCLIENTE
  └─ Expansión dinámica: IA puede solicitar tablas adicionales

  Resiliencia de metadatos (3 niveles):
    1. BD Firebird real (RDB$RELATION_FIELDS)
    2. SIUO JSON (db_metadata_optimized.json) → _get_siuo_columns()
    3. db_context texto → _extract_columns_from_context()

FASE 3: Investigación Multi-Angular
  ├─ SQLs dinámicos generados por IA (hasta 12+)
  ├─ SQLs fijos SIEMPRE incluidos (fallback cuando IA no disponible):
  │   ├─ SQL FIJO 0: resumen general por tipo (SIEMPRE si hay DOCCAB)
  │   ├─ Distribución temporal (año/serie)
  │   ├─ Instalaciones únicas vs presupuestos
  │   ├─ Grupo importe/media (si pregunta contiene importe/precio/total…)
  │   └─ Grupo cliente (si pregunta contiene cliente/clientes)
  ├─ Expansión dinámica (<!-- NECESITO_MAS_SQLS: N -->)
  ├─ Auto-corrección de SQLs fallidos (hasta 2 reintentos + IA)
  ├─ Resumen progresivo si se supera el presupuesto de tokens
  └─ Si IA devuelve None → marca result.ai_unavailable = True y ejecuta solo SQLs fijos

FASE 4: Análisis Crítico Profundo
  ├─ 4.1 Anomalías estadísticas
  ├─ 4.2 Calidad de datos
  ├─ 4.3 Contexto de negocio
  ├─ 4.4 Limitaciones del SQL
  ├─ 4.5 Patrones ocultos
  ├─ 4.6 Hipótesis explicativas
  ├─ 4.7 Score de fiabilidad (alto/medio/bajo)
  └─ Registro de feedback en SIUO (autoaprendizaje)

FASE 5: Síntesis Épica
  ├─ Respuesta principal con datos reales en tabla Markdown
  ├─ Análisis crítico
  ├─ Advertencias y anomalías (Markdown puro, sin HTML)
  ├─ Contexto de negocio
  ├─ Sugerencias y próximos pasos
  └─ Detalles técnicos en <details> desplegable
```

---

## 3. Integración con SIUO (Sistema de Índices Ultra-Optimizados)

### 3.1 Flujo de integración

```
DeepAnalysisAgent
    │
    ├─ FASE 3 → get_context_retriever().get_context(question, max_tokens)
    │           └─ Contexto jerárquico optimizado (tablas relevantes + relaciones)
    │           └─ Fallback a db_context si SIUO no disponible
    │
    └─ FASE 4 → retriever.register_feedback(question, sql, was_correct, tables)
                └─ Registra en siuo_query_log.json para autoaprendizaje
                └─ was_correct = reliability_score in ("alto", "medio")
```

### 3.2 Tokens de contexto adaptativos

```python
# Más SQLs → más tokens de contexto SIUO (mejor calidad de SQLs generados)
max_tokens = min(2000 + n_sqls * 500, 8000)
```

| max_sqls | max_tokens SIUO |
|----------|----------------|
| 2 (BASIC) | 3000 |
| 4 (MEDIUM) | 4000 |
| 8 (DEEP) | 6000 |
| 12 (EPIC) | 8000 |

### 3.3 Autoaprendizaje (KnowledgeStore)

El sistema aprende de cada análisis exitoso:
- **Patrones SQL** → guardados en `knowledge_store.json` con intent + sql + rows_returned
- **Optimización LAN** → `_phase0_lan_optimize()` carga patrones conocidos para evitar SQLs redundantes
- **Feedback de fiabilidad** → `register_feedback()` actualiza el índice SIUO
- **Sugerencias** → `retriever.get_learning_suggestions()` devuelve candidatos para enriquecer el índice

---

## 4. TokenBudget — Gestión de Contexto

### 4.1 Principio

Ninguna llamada a la IA supera el límite de contexto del modelo. El `TokenBudget` garantiza esto:

```python
budget = TokenBudget(context_limit_tokens)  # auto-detectado del orchestrator
budget.truncate_to_fit(data, system, question)  # trunca si es necesario
budget.usage_pct(data)  # % de uso → activa resumen progresivo si > 75%
```

### 4.2 Resumen progresivo

Si los datos de investigación superan el 75% del presupuesto:
1. Se resume con IA (≤30% del tamaño original)
2. Si el resumen sigue siendo grande → se vuelca a fichero temporal
3. Los ficheros temporales se limpian al finalizar el análisis

---

## 5. Principios de Resiliencia

Cada subfase tiene `try/except` independiente:

```python
# Patrón estándar en todas las fases
try:
    result = await self._sub_detect_intent(question, history)
except Exception as e:
    result = {"intent": question, "category": "otro", "error": str(e)}
    # Continúa con valores por defecto
```

Jerarquía de fallbacks:
1. **Subfase falla** → usa valores por defecto, continúa
2. **Fase falla** → continúa con lo que tiene
3. **IA falla / no disponible** → activa `result.ai_unavailable = True`, ejecuta SQLs fijos deterministas
4. **Todo falla** → `_emergency_fallback()` devuelve datos crudos con aviso explícito de IA caída

> Si `ai_unavailable` es `True`, `_emergency_fallback()` muestra el aviso:
> *"❌ El servidor de IA no está disponible en este momento. Comprueba que el servidor Qwen3 (192.168.0.36) esté activo."*

---

## 6. Reglas de Negocio Conocidas

### 6.1 DOCCAB — Tipos de documento

| TIPO | Descripción |
|------|-------------|
| 0 | Presupuesto |
| 2 | SAT / Orden de trabajo |
| 11 | Albarán |
| 12 | Pedido |
| 13 | Factura |

### 6.2 Instalaciones vs Presupuestos

**CRÍTICO**: 1 instalación puede tener N presupuestos.
- `COUNT(*)` en DOCCAB WHERE TIPO=0 = total presupuestos (NO instalaciones)
- `COUNT(DISTINCT CODIGOOBRA)` = instalaciones únicas (si existe la columna)
- `COUNT(DISTINCT CODCLIENTE)` = clientes únicos (aproximación)

### 6.3 DOCDESTINO — Trazabilidad de documentos

Vincula documentos origen → destino:
- Presupuesto → Pedido → Albarán → Factura
- Para calcular tasa de éxito: JOIN DOCCAB con DOCDESTINO

### 6.4 Columnas BLOB

`DESCRIPCION` es BLOB en muchas tablas → **NO usar en GROUP BY**.
Usar `CAST(DESCRIPCION AS VARCHAR(200))` si es necesario.

---

## 7. Cómo Extender con Nuevas Subfases

### 7.1 Añadir una subfase a Fase 1

```python
# En phases_1_2.py → _phase1_understand()
new_data = await self._sub_new_analysis(question, history_text)
phase.sub_phases.append(SubPhaseResult("1.6 Nueva subfase", bool(new_data), new_data))
phase.data["new_analysis"] = new_data
```

### 7.2 Añadir un SQL fijo a Fase 3

```python
# En phase3.py → _build_fixed_sqls()
if "nueva_condicion" in msg:
    fixed.append({
        "objetivo": "Descripción del SQL",
        "sql": "SELECT ... FROM TABLA WHERE ..."
    })
```

### 7.3 Añadir una dimensión de análisis a Fase 4

```python
# En phase4.py → _phase4_analyze() → system prompt
"7. NUEVA DIMENSIÓN: descripción\n"
# Y en el JSON de respuesta:
'"nueva_dimension":[],'
# Y en el procesamiento:
result.nueva_lista.extend(analysis.get("nueva_dimension", []))
```

---

## 8. Activación del Modo Análisis Profundo

### 8.1 Frontend (chat.js)

```javascript
// Checkbox en el formulario de chat
const deepAnalysis = document.getElementById('deep-analysis-toggle')?.checked ?? true;
body.deep_analysis = deepAnalysis;
```

### 8.2 Backend (service.py)

```python
# Activar si: checkbox marcado O palabras clave detectadas
if context.get('deep_analysis', False) or self._is_deep_analysis_request(message):
    agent = DeepAnalysisAgent(orchestrator, db_context, sql_executor, sql_normalizer)
    return await agent.analyze(message, conversation_history)
```

### 8.3 Comandos explícitos

- `/deep <pregunta>` — activa modo épico
- `/analisis <pregunta>` — activa modo épico
- Palabras clave: "analiza en profundidad", "análisis completo", "investiga", "a fondo"

---

## 9. Tests

Los tests están divididos en 7 ficheros especializados (150 tests en total):

```
tests/unit/
├── test_deep_analysis_agent.py      ← Re-exportador (importa todos los ficheros)
├── test_deep_analysis_1_core.py     ← detect_depth, TokenBudget, Fase 1/2/3/4, fallback
├── test_deep_analysis_2_phases.py   ← _phase0_lan_optimize, _build_phase3_system, Fase 3 None
├── test_deep_analysis_3_learn.py    ← Fase 4b aprendizaje, estado pend/ven/com
├── test_deep_analysis_4_advanced.py ← SIUO helpers, _build_warnings_html
├── test_deep_analysis_5_knowledge.py ← KnowledgeStore básico
├── test_deep_analysis_6_knowledge2.py ← KnowledgeStore avanzado
└── test_deep_analysis_7_knowledge3.py ← KnowledgeStore edge cases
```

Ejecutar:
```bash
cd bots/interjddcia
pytest tests/unit/test_deep_analysis_1_core.py \
       tests/unit/test_deep_analysis_2_phases.py \
       tests/unit/test_deep_analysis_3_learn.py \
       tests/unit/test_deep_analysis_4_advanced.py \
       tests/unit/test_deep_analysis_5_knowledge.py \
       tests/unit/test_deep_analysis_6_knowledge2.py \
       tests/unit/test_deep_analysis_7_knowledge3.py -v
# Resultado esperado: 150 passed, 0 failed
```

---

## 10. Ficheros del Módulo

| Fichero | Líneas | Descripción |
|---------|--------|-------------|
| `deep_analysis/__init__.py` | ~20 | Exportaciones públicas |
| `deep_analysis/models.py` | ~170 | Dataclasses, Enums, TokenBudget |
| `deep_analysis/phases_1_2.py` | ~280 | Fases 0, 1, 2 |
| `deep_analysis/phase2_explore.py` | ~200 | Exploración de tablas (Fase 2) |
| `deep_analysis/phase3.py` | ~180 | Generación de SQLs (Fase 3) |
| `deep_analysis/phase4.py` | ~150 | Análisis crítico (Fase 4) |
| `deep_analysis/phases_3_4_5.py` | ~380 | Fases 3, 4, 5 + SIUO |
| `deep_analysis/helpers.py` | ~380 | Helpers: SIUO, _phase0_lan_optimize, etc. |
| `deep_analysis/knowledge_store.py` | ~250 | KnowledgeStore: aprendizaje permanente |
| `deep_analysis/agent.py` | ~130 | Orquestador principal |
| `deep_analysis_agent.py` | ~30 | Shim de compatibilidad |
| `service.py` | ~400 | ChatService (integra agente) |
| `firebird_sql_constants.py` | ~200 | Constantes SQL centralizadas |

---

---

## 11. Informe de Disponibilidad del Servidor IA (22/05/2026)

### 11.1 Problema anterior

Cuando el servidor Qwen3 (192.168.0.36) no está disponible, las fases 3 y 5 del DeepAgent recibían `None` de `orchestrator.execute_with_fallback()`. El sistema ejecutaba SQLs fijos y generaba datos correctos, pero `_emergency_fallback()` mostraba:

> "No se pudieron ejecutar consultas SQL. Comprueba la conexión a la base de datos."

…aunque los datos SÍ existían (se habían ejecutado los SQLs fijos). El mensaje era confuso.

### 11.2 Solución implementada

#### Campo `ai_unavailable` en `EpicAnalysisResult`

```python
# models.py
@dataclass
class EpicAnalysisResult:
    ...
    # True si la IA devolvió None en alguna fase crítica (servidor IA no disponible)
    ai_unavailable: bool = False
```

#### Fases que activan el flag

**Fase 3** (`phase3.py`) — dos rutas:

```python
# Ruta 1: excepción al llamar a la IA
except Exception as e:
    result.ai_unavailable = True
    await self._execute_fixed_sqls(fixed_sqls, result, phase)

# Ruta 2: IA devuelve vacío/None
if not response or not isinstance(response, str):
    result.ai_unavailable = True
    await self._execute_fixed_sqls(fixed_sqls, result, phase)
```

**Fase 5** (`phase5.py`) — dos rutas:

```python
# Ruta 1: IA devuelve None (resp vacío)
result.ai_unavailable = True
result.final_answer = self._emergency_fallback(result)

# Ruta 2: excepción
result.ai_unavailable = True
result.final_answer = self._emergency_fallback(result)
```

#### `_emergency_fallback()` actualizado

Distingue dos escenarios según `result.ai_unavailable`:

**IA caída + datos de BD disponibles:**

```
## 📊 <pregunta>

> ❌ **El servidor de IA no está disponible en este momento.**
> El asistente no puede generar una respuesta.
> Comprueba que el servidor Qwen3 (192.168.0.36) esté activo e inténtalo de nuevo.

Se obtuvieron datos directamente de la base de datos (N consultas exitosas):
### Resumen general por tipo de documento (5 filas)
- `{'TIPO': 13, 'N': 85, 'TOTAL_EUR': 348585.0, 'MEDIA_EUR': 4101.0}`
...

> ⚠️ Los datos anteriores son resultados directos de la BD, sin síntesis
>    ni interpretación — el servidor de IA estaba inaccesible.
```

**Sin datos de BD ni IA (fallo total):**

```
> ❌ **El servidor de IA no está disponible en este momento.**
No se pudieron ejecutar consultas SQL. Comprueba la conexión a la base de datos.
```

---

## 12. SQLs Fijos Generalizados (Fase 3)

Los SQLs fijos (`_build_fixed_sqls()` en `phase3_sqls.py`) son la última línea defensiva cuando la IA no responde. Se han extendido con nuevos grupos:

### SQL FIJO 0 — Siempre activo para DOCCAB

Se incluye **siempre** que DOCCAB aparezca en los datos de exploración (Fase 2), independientemente de la pregunta:

```sql
SELECT TIPO, COUNT(*) AS N,
  CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR,
  CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR
FROM DOCCAB WHERE FECHA IS NOT NULL
GROUP BY TIPO ORDER BY N DESC
```

Esto garantiza que cualquier pregunta sobre DOCCAB tenga al menos estadísticas básicas reales.

### Grupo importe/media/promedio

Activo si la pregunta contiene: `importe`, `media`, `promedio`, `precio`, `facturado`, `facturación`, `ingreso`, `cobro`, `total`:

```sql
-- Importe medio, mínimo y máximo por tipo de documento
SELECT TIPO, COUNT(*) AS N,
  CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR,
  CAST(MIN(IMPORTETOTAL) AS NUMERIC(15,2)) AS MIN_EUR,
  CAST(MAX(IMPORTETOTAL) AS NUMERIC(15,2)) AS MAX_EUR
FROM DOCCAB WHERE IMPORTETOTAL > 0
GROUP BY TIPO ORDER BY N DESC

-- Importe total y medio de facturas (TIPO=13) por año
SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N_FACTURAS,
  CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR,
  CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR
FROM DOCCAB WHERE TIPO = 13 AND FECHA IS NOT NULL
GROUP BY EXTRACT(YEAR FROM FECHA) ORDER BY ANO DESC
```

### Grupo cliente

Activo si la pregunta contiene: `cliente`, `clientes`, `compradores`:

```sql
-- TOP 10 clientes por importe facturado
SELECT FIRST 10 CODCLIENTE, COUNT(*) AS N_DOCS,
  CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR
FROM DOCCAB WHERE CODCLIENTE IS NOT NULL
GROUP BY CODCLIENTE ORDER BY TOTAL_EUR DESC

-- Estadísticas generales de clientes
SELECT COUNT(DISTINCT CODCLIENTE) AS N_CLIENTES,
  COUNT(*) AS N_DOCS,
  CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_DOC_EUR
FROM DOCCAB WHERE CODCLIENTE IS NOT NULL
```

### Regla general

Todos los SQLs fijos usan **sintaxis Firebird nativa** (`EXTRACT`, `FIRST`, `CAST AS NUMERIC(15,2)`). El `SimulatedFirebirdDriver` los traduce automáticamente a SQLite vía `query_translator.py`. No se necesita ningún tratamiento especial en el DeepAgent.

---

*Última actualización: 22/05/2026 — AI unavailability reporting + SQLs fijos generalizados + simulador server-side*
