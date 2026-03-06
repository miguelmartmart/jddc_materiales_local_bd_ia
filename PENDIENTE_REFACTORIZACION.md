# PENDIENTE — Refactorización Robustez y Resiliencia
## Sesión: 04/03/2026 → Continuar 05/03/2026

---

## ESTADO ACTUAL (lo que ya está hecho)

### ✅ Tests — 26/26 pasados
```cmd
set PYTHONUTF8=1
set PYTHONPATH=C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
.venv\Scripts\python.exe -X utf8 test_sistemas_ia.py
```

### ✅ Ficheros nuevos ya creados

| Fichero | Líneas | Estado |
|---------|--------|--------|
| `backend/modules/chat/chat_voice_interpreter.py` | ~230 | ✅ CREADO |
| `backend/modules/chat/chat_db_executor.py` | ~220 | ✅ CREADO |
| `backend/modules/db_explorer/context_retriever.py` | 724 | ✅ Refactorizado (normalización plurales) |

### ✅ Bug corregido en context_retriever.py
- `_normalize_word()` añadido: "articulos" → "articulo" en concept_index
- Impacto: todas las preguntas en plural ahora funcionan

---

## PENDIENTE — Ficheros que exceden 500 líneas

| Fichero | Líneas | Acción necesaria |
|---------|--------|-----------------|
| `backend/modules/chat/service.py` | **912** | ⚠️ REFACTORIZAR — importar desde chat_voice_interpreter y chat_db_executor |
| `backend/modules/db_explorer/deep_indexer_service.py` | **1083** | ⚠️ REFACTORIZAR — dividir en 3 ficheros |
| `backend/modules/chat/firebird_sql_normalizer.py` | **515** | ⚠️ Añadir try/except en normalize() |
| `backend/modules/db_explorer/metadata_builder_service.py` | **535** | ⚠️ REFACTORIZAR — extraer métodos |

---

## PLAN DETALLADO PARA MAÑANA

### PASO 1 — Refactorizar service.py (912 → ~400 líneas)

**Qué hacer:**
Reemplazar en `service.py` las funciones que ya están en los nuevos módulos:

```python
# ELIMINAR de service.py (ya están en chat_voice_interpreter.py):
def interpret_results_for_voice(...)  # líneas ~30-140
def clean_for_tts(...)                # líneas ~143-200

# ELIMINAR de service.py (ya están en chat_db_executor.py):
def _execute_sql(...)                 # líneas ~800-870
def _get_db_context(...)              # líneas ~720-790

# AÑADIR imports al inicio de service.py:
from backend.modules.chat.chat_voice_interpreter import (
    interpret_results_for_voice, clean_for_tts
)
from backend.modules.chat.chat_db_executor import execute_sql
```

**Resultado esperado:** service.py ~400 líneas, solo con la lógica de orquestación.

**IMPORTANTE:** Los tests de Sistema 3 usan `interpret_results_for_voice` y `clean_for_tts`
importados desde `service.py`. Hay que actualizar el import en `test_sistemas_ia.py`:
```python
# ANTES (en test_sistemas_ia.py):
from backend.modules.chat.service import interpret_results_for_voice
from backend.modules.chat.service import clean_for_tts

# DESPUÉS:
from backend.modules.chat.chat_voice_interpreter import interpret_results_for_voice, clean_for_tts
```

O bien mantener re-exports en service.py para compatibilidad:
```python
# En service.py (re-exports para compatibilidad):
from backend.modules.chat.chat_voice_interpreter import (
    interpret_results_for_voice, clean_for_tts
)
```

---

### PASO 2 — Refactorizar deep_indexer_service.py (1083 → 3 ficheros)

**División propuesta:**

```
backend/modules/db_explorer/
├── deep_indexer_service.py      (~350 líneas) — Orquestador principal
├── deep_indexer_graph.py        (~250 líneas) — build_graph(), relaciones FK
├── deep_indexer_concepts.py     (~200 líneas) — build_concept_index(), keywords
└── deep_indexer_values.py       (~200 líneas) — build_value_index(), enumerados/rangos
```

**Qué va en cada fichero:**

`deep_indexer_service.py` (orquestador):
- `DeepIndexerService` clase principal
- `analyze_table_deep()` — análisis de una tabla
- `analyze_all_tables_batch()` — análisis masivo con SSE
- `_save_progress()`, `_load_progress()` — persistencia de estado
- Imports de los 3 submódulos

`deep_indexer_graph.py`:
- `build_graph(table_list, driver)` — construye db_graph.json
- `_detect_implicit_fks(table_name, columns)` — FKs por nombre de columna
- `_get_explicit_fks(table_name, driver)` — FKs de Firebird
- `_find_shortest_path(graph, from_table, to_table)` — BFS

`deep_indexer_concepts.py`:
- `build_concept_index(table_index)` — construye concept_index.json
- `_extract_keywords_from_table(table_entry)` — keywords de una tabla
- `MANUAL_CONCEPT_RULES` — dict con reglas manuales (factura→DOCCAB TIPO=13, etc.)

`deep_indexer_values.py`:
- `build_value_index(table_list, driver)` — construye value_index.json
- `_get_enum_values(table, col, driver)` — valores distintos de una columna
- `_get_range_values(table, col, driver)` — min/max/avg de columnas numéricas
- `_get_top_n_values(table, col, driver, n=10)` — top N valores más frecuentes

---

### PASO 3 — Añadir resiliencia en firebird_sql_normalizer.py (515 líneas)

**Qué hacer:**
El fichero tiene 515 líneas (solo 15 sobre el límite). No necesita dividirse,
solo añadir manejo de errores en el método `normalize()`:

```python
def normalize(self, sql: str) -> Tuple[str, List[str]]:
    """..."""
    # AÑADIR al inicio:
    if not sql or not isinstance(sql, str):
        logger.warning("[SQLNormalizer] SQL vacío o no es string")
        return str(sql) if sql else "", []
    
    changes = []
    original = sql
    
    try:
        # ... código existente ...
    except Exception as e:
        logger.error(f"[SQLNormalizer] Error inesperado: {e}", exc_info=True)
        # Fallback: devolver SQL original sin normalizar
        return original, [f"ERROR en normalización: {e} — SQL devuelto sin cambios"]
```

También añadir try/except en cada paso individual para que un fallo en un paso
no rompa los demás.

---

### PASO 4 — Refactorizar metadata_builder_service.py (535 líneas)

**División propuesta:**

```
backend/modules/db_explorer/
├── metadata_builder_service.py  (~350 líneas) — Servicio principal
└── metadata_builder_ai.py       (~200 líneas) — Análisis con Qwen3 LAN
```

`metadata_builder_service.py`:
- `MetadataBuilderService` clase principal
- `get_all_tables()`, `get_table_structure()`, `get_table_sample()`
- `save_table_metadata()`, `get_progress()`
- `check_local_ai()` — verificar Qwen3 LAN

`metadata_builder_ai.py`:
- `analyze_table_with_local_ai(table_name, structure, sample)` — llamada a Qwen3
- `_build_analysis_prompt(table_name, structure, sample)` — construir prompt
- `_parse_ai_response(response_text)` — parsear JSON de la respuesta
- `_validate_metadata(metadata)` — validar estructura del JSON

---

### PASO 5 — Verificar tests tras refactorización

```cmd
set PYTHONUTF8=1
set PYTHONPATH=C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
.venv\Scripts\python.exe -X utf8 test_sistemas_ia.py
```

**Resultado esperado:** 26/26 tests pasados (igual que antes).

Si algún test falla, será por imports rotos — revisar los re-exports.

---

### PASO 6 — Verificar tamaños finales

```powershell
$base='C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia'
$files=@(
    'backend\modules\chat\service.py',
    'backend\modules\chat\chat_voice_interpreter.py',
    'backend\modules\chat\chat_db_executor.py',
    'backend\modules\chat\firebird_sql_normalizer.py',
    'backend\modules\db_explorer\context_retriever.py',
    'backend\modules\db_explorer\deep_indexer_service.py',
    'backend\modules\db_explorer\deep_indexer_graph.py',
    'backend\modules\db_explorer\deep_indexer_concepts.py',
    'backend\modules\db_explorer\deep_indexer_values.py',
    'backend\modules\db_explorer\metadata_builder_service.py',
    'backend\modules\db_explorer\metadata_builder_ai.py'
)
foreach($f in $files){
    $p=Join-Path $base $f
    if(Test-Path $p){
        $n=(Get-Content $p).Count
        $flag=if($n -gt 500){'<<< EXCEDE 500'}else{'OK'}
        Write-Host "$n`t$flag`t$f"
    } else {
        Write-Host "NO EXISTE`t`t$f"
    }
}
```

**Resultado esperado:** Todos los ficheros ≤500 líneas.

---

## RESUMEN DE FICHEROS TRAS REFACTORIZACIÓN COMPLETA

```
backend/modules/chat/
├── service.py                    ~400 líneas  ← orquestador principal
├── chat_voice_interpreter.py     ~230 líneas  ✅ ya creado
├── chat_db_executor.py           ~220 líneas  ✅ ya creado
├── firebird_sql_normalizer.py    ~515 líneas  ← añadir try/except
├── sql_corrector.py              353 líneas   ✅ OK
├── model_fallback_orchestrator.py 326 líneas  ✅ OK
└── router.py                     290 líneas   ✅ OK

backend/modules/db_explorer/
├── context_retriever.py          ~400 líneas  ✅ ya refactorizado
├── deep_indexer_service.py       ~350 líneas  ← dividir
├── deep_indexer_graph.py         ~250 líneas  ← nuevo
├── deep_indexer_concepts.py      ~200 líneas  ← nuevo
├── deep_indexer_values.py        ~200 líneas  ← nuevo
├── metadata_builder_service.py   ~350 líneas  ← dividir
├── metadata_builder_ai.py        ~200 líneas  ← nuevo
└── siuo_router.py                194 líneas   ✅ OK
```

---

## COMANDO PARA ARRANCAR EL SISTEMA

```cmd
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
ARRANCAR_DEVIA.bat
```
→ Elegir opción 1 (Chat IA + BD, puerto 8001)

**URLs tras arrancar:**
- Chat web: http://localhost:8001
- API docs: http://localhost:8001/docs
- Health:   http://localhost:8001/health

**Test rápido con BD real:**
```cmd
curl -X POST http://localhost:8001/api/chat/send -H "Content-Type: application/json" -d "{\"message\": \"cuantos articulos hay\"}"
```

---

## NOTAS IMPORTANTES

1. **Los tests ya pasan (26/26)** — no romper nada al refactorizar
2. **Mantener re-exports** en service.py para compatibilidad con imports existentes
3. **Cada fichero nuevo** debe tener docstring con RESPONSABILIDAD, RESILIENCIA, PRINCIPIOS
4. **Cada método público** debe tener try/except con fallback gracioso
5. **Nunca `except Exception: pass`** — siempre loggear el error
6. **context_retriever.py** ya tiene 724 líneas pero es el más complejo — si se divide,
   separar en `context_retriever.py` + `keyword_extractor.py` + `context_builder.py`
