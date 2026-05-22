# DEVIA — KnowledgeStore: Almacén de Conocimiento Persistente

**Módulo:** `backend/modules/chat/deep_analysis/knowledge_store.py`  
**Versión:** 1.1 — 22/05/2026  
**Principio:** LAN_ONLY — Nunca se envían datos a internet

---

## ¿Qué es el KnowledgeStore?

Sistema de aprendizaje permanente del DeepAnalysisAgent. Cada vez que el agente
ejecuta un análisis profundo (Fase 4b), persiste en disco los descubrimientos:

- Columnas reales de cada tabla (desde `RDB$RELATION_FIELDS`)
- Conteos reales de registros (desde `COUNT(*)`)
- Distribuciones de valores clave (TIPO, ESTADOPEND, DOCDESTINO)
- Reglas de negocio descubiertas por la IA
- Patrones SQL exitosos (para reutilizar en análisis futuros)
- Log append-only de todos los descubrimientos

---

## Estructura de carpetas

```
core/config/knowledge/
├── tables/
│   ├── DOCCAB.json          ← metadatos ricos de DOCCAB
│   ├── CLIENTE.json
│   ├── DOCLIN.json
│   └── ...
├── index.json               ← índice global (resumen de todas las tablas)
├── business_rules.json      ← reglas de negocio descubiertas
├── query_patterns.json      ← patrones SQL exitosos por intención
└── discoveries_log.jsonl    ← log append-only (JSONL)
```

---

## Formato de cada fichero

### `tables/DOCCAB.json` (ejemplo)
```json
{
  "_table": "DOCCAB",
  "_updated_at": "2026-03-17T11:00:00",
  "columns_real": ["CODIGO", "TIPO", "FECHA", "SERIE", "IMPORTETOTAL", ...],
  "columns_count": 87,
  "columns_source": "firebird_rdb",
  "record_count_real": 74034,
  "record_count_source": "firebird_count",
  "tipo_distribution": [{"TIPO": 13, "N": 42000}, {"TIPO": 0, "N": 18500}, {"TIPO": 11, "N": 8000}, {"TIPO": 12, "N": 5534}],
  "estadopend_distribution": {"0": 15000, "1": 2500, "2": 1000},
  "columns_estado": ["ESTADOPEND", "ESTADOPENDVENCOM", "CODSEGUIMIENTO"],
  "docdestino_tipo_distribution": {"13": 768, "12": 120},
  "_nota_estadopend": "ESTADOPEND en presupuestos (TIPO=0): {...}. Verificar qué valor indica 'aceptado'.",
  "_nota_docdestino": "De 18500 presupuestos: 888 tienen documento destino (4.8%)..."
}
```

### `index.json` (ejemplo)
```json
{
  "_total_tables": 12,
  "_updated_at": "2026-03-17T11:00:00",
  "tables": {
    "DOCCAB": {"record_count": 74034, "columns_count": 87, "has_tipo": true, "has_fecha": true},
    "CLIENTE": {"record_count": 5200, "columns_count": 45, "has_tipo": false, "has_fecha": false}
  }
}
```

### `business_rules.json` (ejemplo)
```json
{
  "_count": 3,
  "rules": [
    {
      "rule": "Solo el 4.8% de presupuestos tienen documento destino — DOCDESTINO no es indicador fiable de 'aceptado'",
      "table": "DOCCAB",
      "confidence": "alto",
      "source": "deep_analysis",
      "discovered_at": "2026-03-17T11:00:00"
    }
  ]
}
```

### `discoveries_log.jsonl` (formato JSONL)
```jsonl
{"ts":"2026-03-17T11:00:00","type":"columns_real","table":"DOCCAB","question":"¿cuántos presupuestos?","data":{...}}
{"ts":"2026-03-17T11:01:00","type":"estadopend","table":"DOCCAB","question":"tasa de éxito","data":{"0":15000,"1":2500}}
```

---

## API pública

```python
from backend.modules.chat.deep_analysis import get_knowledge_store

store = get_knowledge_store()  # singleton

# Leer metadatos de una tabla
doccab = store.get_table("DOCCAB")

# Actualizar metadatos (merge inteligente — solo actualiza si cambió)
store.update_table("DOCCAB", {
    "columns_real": ["CODIGO", "TIPO", ...],
    "record_count_real": 74034,
    "_nota_estadopend": "...",
})

# Añadir regla de negocio (sin duplicados)
store.add_business_rule(
    "1 instalación puede tener N presupuestos",
    table="DOCCAB", confidence="alto"
)

# Registrar patrón SQL exitoso
store.add_query_pattern(
    intent="presupuestos por año",
    sql="SELECT EXTRACT(YEAR FROM FECHA)...",
    tables=["DOCCAB"],
    rows_returned=12,
    reliability="alto"
)

# Obtener patrones relevantes para una intención
patterns = store.get_patterns_for_intent(["presupuesto", "año"])

# Resumen IA-friendly para incluir en prompts
summary = store.get_ia_summary(tables=["DOCCAB", "CLIENTE"])

# Log de descubrimientos
store.log_discovery("estadopend", "DOCCAB", {"0": 15000, "1": 2500}, question)
recent = store.get_recent_discoveries(n=10)
```

---

## Integración con DeepAnalysisAgent

La Fase 4b (`_phase4b_learn_and_persist`) se ejecuta automáticamente entre
Fase 4 (análisis) y Fase 5 (síntesis) en cada análisis profundo.

**Flujo:**
```
Fase 2 (exploración) → descubre columnas reales, conteos
Fase 3 (investigación) → ejecuta SQLs de ESTADOPEND, DOCDESTINO, etc.
Fase 4 (análisis) → detecta anomalías, reglas de negocio
Fase 4b (aprendizaje) → persiste TODO en KnowledgeStore
Fase 5 (síntesis) → usa el conocimiento acumulado
```

**El KnowledgeStore se usa también en Fase 3** para enriquecer el contexto
del prompt con conocimiento previo (via `get_ia_summary()`).

---

## Principios de diseño

1. **LAN_ONLY**: Nunca se envían datos a internet. Todo es local.
2. **Merge inteligente**: Solo actualiza campos que han cambiado.
3. **Backup automático**: Cada escritura hace backup del fichero anterior (`.bak`).
4. **Sin duplicados**: Reglas y patrones no se duplican.
5. **Log rotativo**: `discoveries_log.jsonl` se rota al superar 5000 entradas.
6. **Ultra-resiliente**: Cada operación con `try/except` independiente.
7. **Singleton**: `get_knowledge_store()` devuelve siempre la misma instancia.
8. **IA-friendly**: `get_ia_summary()` genera texto compacto para prompts.

---

## ⚠️ Formato obligatorio de `tipo_distribution`

> **Bug conocido (corregido 22/05/2026):** El campo `tipo_distribution` en los ficheros
> de tabla (ej. `DOCCAB.json`) **DEBE ser una lista de dicts**, no un dict.

### ✅ Formato correcto (lista de dicts)

```json
"tipo_distribution": [
  {"TIPO": 13, "N": 85},
  {"TIPO": 0,  "N": 66},
  {"TIPO": 11, "N": 30}
]
```

### ❌ Formato incorrecto (dict — causa crashes)

```json
"tipo_distribution": {"13": 85, "0": 66, "11": 30}
```

**Por qué importa:**

- `_fmt_exploration()` en `helpers.py` hace `tipo_dist[:5]` (slicing). Sobre una lista → OK. Sobre un dict → `TypeError: unhashable type: 'slice'`.
- Este TypeError escapa al bloque `except Exception` del agente antes de que la Fase 3 pueda ejecutar SQLs, dejando `sql_queries` vacío y mostrando "No se pudieron ejecutar consultas SQL" aunque el simulador funcione correctamente.

**Origen del bug:**

`_phase4b_learn_and_persist` (en `phase4.py`) convertía la lista a dict antes de guardar:

```python
# ANTES (bug) — convertía a dict:
{str(r.get("TIPO","?")): r.get("N",0) for r in tipo_dist}

# AHORA (correcto) — conserva lista de dicts:
[{"TIPO": r.get("TIPO","?"), "N": r.get("N",0)} for r in tipo_dist if isinstance(r, dict)]
```

**Defensa adicional:**

`_fmt_exploration()` y `_phase4b_learn_and_persist` comprueban `isinstance(tipo_dist, list)` antes de operar, con `try/except` interior para absorber cualquier formato inesperado sin crashear.

---

## Cómo extender

### Añadir un nuevo tipo de descubrimiento
1. Añadir la clave en `DISCOVERY_TYPES` en `knowledge_store.py`
2. En `_phase4b_learn_and_persist` (phases_3_4_5.py), detectar el patrón en los resultados SQL
3. Llamar a `store.update_table()` o `store.log_discovery()`

### Añadir un nuevo fichero de conocimiento
1. Añadir la ruta en `KNOWLEDGE_STORE_CONSTANTS`
2. Crear métodos `get_X()` y `add_X()` en `KnowledgeStore`
3. Exportar en `__init__.py`

---

## Reglas de negocio conocidas (actualizadas por el agente)

Ver `core/config/knowledge/business_rules.json` para las reglas actuales.

Reglas iniciales conocidas:
- `DOCCAB.TIPO`: 0=presupuesto, 13=factura, 11=albarán, 12=pedido, 2=SAT
- 1 instalación puede tener N presupuestos → total presupuestos ≠ total instalaciones
- `DOCDESTINO` puede NO ser el indicador correcto de "aceptado" — verificar `ESTADOPEND`
- `DOCLIN` no tiene `FECHA` propia → JOIN con `DOCCAB` para obtener fecha
- `DESCRIPCION` es BLOB → NO usar en GROUP BY
