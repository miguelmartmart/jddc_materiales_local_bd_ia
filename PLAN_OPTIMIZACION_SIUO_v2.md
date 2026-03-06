# PLAN DE OPTIMIZACIÓN SIUO v2 — Para ejecutar cuando se indique

> **Estado**: PLAN (no ejecutado)  
> **Fecha**: 06/03/2026  
> **Basado en**: revisión del código real de `context_retriever.py`, `deep_indexer_service.py`, `constants.py`

---

## RESUMEN EJECUTIVO DE PROBLEMAS DETECTADOS

| # | Problema | Impacto | Dificultad |
|---|----------|---------|------------|
| 1 | Columnas sensibles ocultas a Qwen3 LAN sin justificación real | Medio | Bajo |
| 2 | Límite fijo de 8 tablas sin análisis progresivo | Alto | Alto |
| 3 | No se leen datos reales de columnas descripción/texto libre | Alto | Alto |
| 4 | Fechas y rangos no se usan para filtrar contexto | Medio | Medio |
| 5 | Datos mal introducidos no se detectan ni interpretan | Alto | Alto |
| 6 | Contexto largo: corte brusco sin síntesis previa | Alto | Alto |
| 7 | Columnas sensibles ocultas también en el contexto del chat | Medio | Bajo |

---

## PROBLEMA 1: ¿Por qué se ocultan columnas sensibles a Qwen3 LAN?

### Situación actual

```python
# constants.py
class PrivacyConfig:
    SENSITIVE_COLUMNS = frozenset({
        "NIF", "CIF", "DNI", "IBAN", "BIC",
        "EMAIL", "TELEFONO", ...
    })
    MAX_SAMPLE_ROWS = 3  # Solo 3 filas de muestra
```

```python
# deep_indexer_service.py → _get_column_values()
for col in columns:
    if col["is_sensitive"] or "BLOB" in col_type:
        continue  # ← Qwen3 nunca ve valores de estas columnas
```

```python
# context_retriever.py → _build_table_block()
# cols_key no incluye columnas sensibles
# → La IA del chat no sabe que existen NIF, EMAIL, etc.
```

### El problema real

**Qwen3 está en la red local (192.168.0.36)**. No hay ninguna razón técnica para ocultarle los *nombres* de columnas sensibles — necesita saber que existen para:
- Entender la estructura completa de la tabla
- Generar SQL correcto que haga JOINs por NIF/CIF cuando sea necesario
- Describir correctamente para qué sirve cada tabla

Lo que SÍ tiene sentido proteger son los **valores reales** (el NIF de un cliente concreto, el IBAN de una cuenta), no los nombres de columna.

### Plan de cambio

**Separar dos conceptos que ahora están mezclados:**

```
ANTES (incorrecto):
  SENSITIVE_COLUMNS → ocultar nombre de columna a Qwen3 LAN
                    → ocultar nombre de columna al chat
                    → ocultar valores a Qwen3 LAN

DESPUÉS (correcto):
  SENSITIVE_DATA_COLUMNS → ocultar VALORES a Qwen3 LAN (muestra de datos)
                         → NO ocultar el nombre de columna a Qwen3 LAN
                         → SÍ ocultar valores al chat (nunca datos reales)
  
  CHAT_HIDDEN_COLUMNS → columnas que el chat NO debe usar para generar SQL
                      → solo: PASSWORD, PASS, CLAVE, TOKEN, SECRET, FIRMA
                      → NIF, EMAIL, TELEFONO SÍ deben estar disponibles
                        para que la IA pueda buscar por cliente
```

**Archivos a modificar:**
- `constants.py`: dividir `SENSITIVE_COLUMNS` en `DATA_PRIVACY_COLUMNS` y `CHAT_BLOCKED_COLUMNS`
- `deep_indexer_service.py`: `_get_column_values()` → solo excluir `DATA_PRIVACY_COLUMNS` de muestras
- `deep_indexer_service.py`: `_ask_ai_for_description()` → incluir todos los nombres de columna
- `context_retriever.py`: `_build_table_block()` → incluir NIF, EMAIL, etc. en cols_key
- `context_retriever.py`: `_get_fallback_context()` → solo filtrar `CHAT_BLOCKED_COLUMNS`

**Resultado esperado:**
- Qwen3 LAN entiende mejor la estructura (sabe que hay NIF, EMAIL, TELEFONO)
- El chat puede generar SQL que busque por NIF o EMAIL cuando el usuario lo pida
- Los valores reales (datos de personas) nunca salen de la BD hacia ningún sitio

---

## PROBLEMA 2: Límite fijo de 8 tablas — Análisis progresivo

### Situación actual

```python
# context_retriever.py
MAX_TABLES_IN_CONTEXT = 8  # Límite fijo, sin importar la complejidad

def _rank_tables(...):
    return sorted(tables.items(), key=sort_key)[:MAX_TABLES_IN_CONTEXT]  # Corte duro

def _build_context(...):
    if tokens_used + block_tokens > max_tokens:
        # Intentar versión compacta
        compact = self._build_table_block_compact(...)
        break  # ← PARA AQUÍ, no analiza más
```

### El problema real

Para preguntas complejas que implican muchas tablas, el sistema:
1. Corta en 8 tablas sin importar si son suficientes
2. Si no caben en tokens, usa versión compacta de 1 línea y para
3. No hay síntesis progresiva: no resume lo que ya sabe para hacer hueco

### Plan de cambio: Análisis progresivo por capas

**Nuevo flujo en `ContextRetriever.get_context()`:**

```
CAPA 1 — Contexto inmediato (siempre, <1ms):
  → Tablas directas del concept_index (score=1)
  → Versión completa si caben en tokens
  → Versión compacta si no caben
  → Resultado: contexto base listo para la IA

CAPA 2 — Expansión por grafo (si quedan tokens):
  → BFS profundidad 1 (vecinos directos)
  → Solo si quedan >500 tokens libres
  → Versión compacta siempre

CAPA 3 — Síntesis Qwen3 (si la pregunta es muy compleja):
  → Si hay >15 tablas candidatas Y quedan tokens
  → Qwen3 LAN genera un resumen de las tablas menos importantes
  → El resumen ocupa ~100 tokens en lugar de 8×350=2800
  → Permite incluir más tablas en el mismo espacio

CAPA 4 — Análisis bajo demanda (para preguntas que necesitan datos reales):
  → Si la pregunta incluye valores específicos ("García", "2025", "R32")
  → Consulta Firebird en tiempo real para esas tablas específicas
  → Añade los resultados al contexto como "DATOS RELEVANTES"
```

**Archivos a modificar:**
- `context_retriever.py`: nuevo método `get_context_progressive()` con las 4 capas
- `context_retriever.py`: nuevo método `_synthesize_tables_with_ai()` para Capa 3
- `context_retriever.py`: nuevo método `_fetch_relevant_data()` para Capa 4
- `constants.py`: nuevas constantes `MAX_TOKENS_LAYER_1`, `MAX_TOKENS_LAYER_2`, etc.

**Nuevo parámetro en `get_context()`:**
```python
def get_context(
    self,
    question: str,
    max_tokens: int = MAX_TOKENS_DEFAULT,
    progressive: bool = True,   # NUEVO: activar análisis por capas
    allow_db_query: bool = True, # NUEVO: permitir consultas Firebird en tiempo real
) -> Tuple[str, Dict[str, Any]]:
```

---

## PROBLEMA 3: Datos en columnas de texto libre no se leen

### Situación actual

```python
# deep_indexer_service.py → _get_column_values()
# Solo lee:
# - Columnas TIPO/ESTADO/FLAG → enumerados
# - Columnas FECHA/TIMESTAMP → rango min/max
# - Columnas PRECIO/TOTAL/IMPORTE → min/max/avg
# - Columnas FAMILIA/CATEGORIA → top-20 valores

# NO lee:
# - Columnas DESCRIPCION, NOMBRE, OBSERVACIONES, REFERENCIA
# - Columnas con datos mal introducidos (ej: FAMILIA='split' en lugar de 'SPLITS')
# - Columnas donde el usuario escribe texto libre
```

### El problema real

En una BD real de empresa, los datos están mal introducidos:
- FAMILIA puede tener 'SPLITS', 'Split', 'split', 'SPLIT MURAL', 'splits murales'
- DESCRIPCION puede contener información clave: "Gas R-32 para split inverter"
- REFERENCIA puede tener formatos inconsistentes: 'ART-001', 'art001', 'ART001'
- OBSERVACIONES puede tener información de negocio crítica

La IA necesita saber esto para generar SQL con `UPPER()` o `LIKE '%split%'` en lugar de `= 'SPLITS'`.

### Plan de cambio: Análisis semántico de texto libre

**Nuevo paso en `_analyze_table_deep()`:**

```python
# PASO 2b: Análisis de texto libre (NUEVO)
text_analysis = await self._analyze_text_columns(table_upper, structure)
```

**Nuevo método `_analyze_text_columns()`:**
```python
async def _analyze_text_columns(self, table_name: str, structure: Dict) -> Dict:
    """
    Para columnas VARCHAR/CHAR importantes (DESCRIPCION, NOMBRE, REFERENCIA):
    1. Lee una muestra de 50-100 valores distintos (sin datos sensibles)
    2. Envía a Qwen3 LAN para que detecte:
       - Patrones de formato (mayúsculas, guiones, prefijos)
       - Variantes del mismo concepto ('split', 'SPLIT', 'Split Mural')
       - Datos mal introducidos o inconsistentes
       - Valores que parecen pertenecer a otra columna
    3. Guarda el análisis en table_index como "text_patterns"
    """
    text_cols = [
        c for c in structure["columns"]
        if "VARCHAR" in c["type"] or "CHAR" in c["type"]
        if not c["is_sensitive"]
        if any(kw in c["name"].upper() for kw in
               ["DESCRIPCION", "NOMBRE", "REFERENCIA", "FAMILIA", "CATEGORIA",
                "CLASE", "GRUPO", "TIPO", "ESTADO", "OBSERVACION"])
    ]
    
    for col in text_cols[:5]:  # Máx 5 columnas por tabla
        # Leer muestra de valores distintos
        rows = driver.execute_query(
            f"SELECT FIRST 100 DISTINCT TRIM({col['name']}) as VAL "
            f"FROM {table_name} WHERE {col['name']} IS NOT NULL "
            f"AND TRIM({col['name']}) <> '' ORDER BY VAL"
        )
        values = [r["VAL"] for r in rows if r["VAL"]]
        
        # Enviar a Qwen3 para análisis semántico
        analysis = await self._ask_ai_text_patterns(table_name, col["name"], values)
        # Guarda: variantes, patrones, inconsistencias, sugerencias SQL
```

**Resultado en `table_index.json`:**
```json
{
  "ARTICULO": {
    "text_patterns": {
      "FAMILIA": {
        "variants": ["SPLITS", "Split", "split", "SPLIT MURAL"],
        "canonical": "SPLITS",
        "sql_hint": "UPPER(TRIM(FAMILIA)) LIKE '%SPLIT%'",
        "inconsistencies": "Hay 3 variantes del mismo concepto"
      },
      "DESCRIPCION": {
        "patterns": ["Contiene modelo, potencia y gas refrigerante"],
        "sql_hint": "UPPER(DESCRIPCION) LIKE '%R-32%' para buscar por gas"
      }
    }
  }
}
```

**Archivos a modificar:**
- `deep_indexer_service.py`: nuevo método `_analyze_text_columns()`
- `deep_indexer_service.py`: nuevo método `_ask_ai_text_patterns()`
- `deep_indexer_service.py`: `_analyze_table_deep()` → añadir paso 2b
- `context_retriever.py`: `_build_table_block()` → incluir `text_patterns` en el contexto

---

## PROBLEMA 4: Fechas y rangos no se usan para filtrar contexto

### Situación actual

```python
# value_index.json contiene:
"ranges": {
    "DOCCAB.FECHA": {"min": "2018-01-02", "max": "2026-03-05"}
}

# context_retriever.py → _build_value_block()
for key, rng in self._value_index.get("ranges", {}).items():
    if key.startswith(f"{table_name}."):
        col_name = key.split(".", 1)[1]
        if any(kw in col_name.lower() for kw in keywords):
            # Solo incluye si el keyword menciona la columna
            # ← PROBLEMA: "2025" no matchea con "fecha"
```

### El problema real

Si el usuario pregunta "facturas de 2025", el keyword "2025" no matchea con "FECHA" en el value_index. El sistema no incluye el rango de fechas en el contexto, y la IA no sabe si hay datos de 2025 o no.

### Plan de cambio: Detección de patrones temporales y numéricos

**Nuevo método `_extract_temporal_context()`:**
```python
def _extract_temporal_context(self, question: str) -> Dict:
    """
    Detecta en la pregunta:
    - Años: "2025", "este año", "el año pasado"
    - Meses: "enero", "en marzo", "el mes pasado"
    - Rangos: "entre 2023 y 2025", "últimos 3 meses"
    - Importes: "más de 1000€", "facturas grandes"
    
    Devuelve filtros SQL sugeridos para añadir al contexto.
    """
    import re
    from datetime import datetime, timedelta
    
    now = datetime.now()
    filters = {}
    
    # Detectar años
    years = re.findall(r'\b(20\d{2})\b', question)
    if years:
        filters["year_hint"] = years
        filters["sql_date_hint"] = f"EXTRACT(YEAR FROM FECHA) IN ({','.join(years)})"
    
    # Detectar "este año"
    if any(w in question.lower() for w in ["este año", "año actual", "2026"]):
        filters["sql_date_hint"] = f"FECHA >= '01.01.{now.year}'"
    
    # Detectar importes
    amounts = re.findall(r'(\d+(?:\.\d+)?)\s*(?:€|euros?|eur)', question.lower())
    if amounts:
        filters["amount_hint"] = amounts
    
    return filters
```

**Integración en `get_context()`:**
```python
# Nuevo paso entre keywords y concept_index
temporal_ctx = self._extract_temporal_context(question)
# Se añade al contexto como:
# "NOTA TEMPORAL: El usuario pregunta por el año 2025.
#  Usar: EXTRACT(YEAR FROM FECHA) = 2025 o FECHA BETWEEN '01.01.2025' AND '31.12.2025'"
```

**Archivos a modificar:**
- `context_retriever.py`: nuevo método `_extract_temporal_context()`
- `context_retriever.py`: `get_context()` → añadir paso de contexto temporal
- `context_retriever.py`: `_build_context()` → incluir hints temporales en el header

---

## PROBLEMA 5: Datos mal introducidos — Interpretación por Qwen3

### Situación actual

El sistema asume que los datos están bien introducidos. No hay ningún mecanismo para detectar:
- Valores en columnas equivocadas
- Formatos inconsistentes
- Datos que parecen de otra tabla
- Campos numéricos con texto, o viceversa

### Plan de cambio: Análisis de calidad de datos durante la indexación

**Nuevo paso en `_analyze_table_deep()` — Paso 2c:**

```python
# PASO 2c: Análisis de calidad de datos (NUEVO)
# Solo para tablas con >100 registros y columnas de texto
if structure["record_count"] > 100:
    quality = await self._analyze_data_quality(table_upper, structure, col_values)
```

**Nuevo método `_analyze_data_quality()`:**
```python
async def _analyze_data_quality(self, table_name, structure, col_values) -> Dict:
    """
    Envía a Qwen3 LAN una muestra de datos reales (sin columnas sensibles)
    y le pide que detecte:
    1. Inconsistencias de formato (mayúsculas/minúsculas, espacios, guiones)
    2. Valores que parecen erróneos (texto en columna numérica, etc.)
    3. Columnas que parecen contener datos de otra categoría
    4. Sugerencias de normalización para SQL
    
    Resultado guardado en table_index como "data_quality"
    """
    # Leer muestra real de la tabla (sin columnas sensibles)
    sample_cols = [
        c["name"] for c in structure["columns"]
        if not c["is_sensitive"] and "BLOB" not in c.get("type", "")
    ][:10]
    
    sample_rows = driver.execute_query(
        f"SELECT FIRST 20 {', '.join(sample_cols)} FROM {table_name}"
    )
    
    prompt = f"""
    Analiza esta muestra de datos de la tabla {table_name} de una empresa de climatización.
    
    MUESTRA (20 filas, columnas no sensibles):
    {json.dumps(sample_rows, ensure_ascii=False, default=str)}
    
    Detecta y describe:
    1. Inconsistencias de formato en columnas de texto
    2. Valores que parecen erróneos o fuera de lugar
    3. Patrones de datos mal introducidos
    4. Sugerencias SQL para buscar correctamente (UPPER, TRIM, LIKE, etc.)
    
    Responde en JSON:
    {{
      "inconsistencies": ["descripción de cada problema encontrado"],
      "sql_hints": ["sugerencia SQL para cada problema"],
      "data_quality_score": 0-10
    }}
    """
    
    return await self._call_qwen3(prompt)
```

**Resultado en `table_index.json`:**
```json
{
  "ARTICULO": {
    "data_quality": {
      "inconsistencies": [
        "FAMILIA tiene variantes: 'SPLITS', 'Split', 'split mural' — mismo concepto",
        "REFERENCIA mezcla formatos: 'ART-001', 'art001', 'ART001'"
      ],
      "sql_hints": [
        "Usar UPPER(TRIM(FAMILIA)) LIKE '%SPLIT%' en lugar de = 'SPLITS'",
        "Usar UPPER(REPLACE(REFERENCIA, '-', '')) para normalizar referencias"
      ],
      "data_quality_score": 6
    }
  }
}
```

---

## PROBLEMA 6: Contexto largo — Síntesis progresiva en lugar de corte brusco

### Situación actual

```python
# context_retriever.py → _build_context()
if tokens_used + block_tokens > max_tokens:
    compact = self._build_table_block_compact(...)
    if tokens_used + compact_tokens <= max_tokens:
        parts.append(compact)
    break  # ← CORTE BRUSCO: las tablas restantes se ignoran completamente
```

### El problema real

Si hay 20 tablas relevantes y solo caben 8 en el contexto, las 12 restantes se ignoran completamente. La IA no sabe que existen, y puede generar SQL incorrecto por falta de información.

### Plan de cambio: Síntesis progresiva con Qwen3

**Nuevo flujo cuando el contexto se llena:**

```
ANTES:
  Tabla 1 (completa) → Tabla 2 (completa) → ... → Tabla 8 (compacta) → STOP

DESPUÉS:
  Tabla 1 (completa) → Tabla 2 (completa) → ... → Tabla 6 (completa)
  → "Hay 14 tablas más relacionadas. Resumen:"
  → Qwen3 LAN genera resumen de las 14 tablas restantes en ~200 tokens
  → El resumen se añade al contexto
  → La IA sabe que existen esas tablas aunque no tenga todos los detalles
```

**Nuevo método `_synthesize_overflow_tables()`:**
```python
async def _synthesize_overflow_tables(
    self,
    overflow_tables: List[Tuple[str, Dict]],
    question: str,
) -> str:
    """
    Cuando hay más tablas de las que caben en el contexto,
    Qwen3 LAN genera un resumen compacto de las tablas sobrantes.
    
    El resumen incluye:
    - Nombres de tablas
    - Para qué sirven (1 línea cada una)
    - Relaciones clave entre ellas
    - Cuándo usarlas
    
    Objetivo: ~200 tokens para 10-20 tablas
    """
    tables_info = []
    for table_name, info in overflow_tables:
        entry = self._table_index.get(table_name, {})
        tables_info.append({
            "tabla": table_name,
            "desc": entry.get("desc", "")[:100],
            "registros": entry.get("n", 0),
            "relacionada_con": entry.get("related", [])[:3],
        })
    
    prompt = f"""
    El usuario pregunta: "{question}"
    
    Estas tablas también son relevantes pero no caben en el contexto principal.
    Genera un resumen MUY COMPACTO (máx 200 tokens) que ayude a la IA a saber
    cuándo y cómo usarlas:
    
    {json.dumps(tables_info, ensure_ascii=False)}
    
    Formato: una línea por tabla: TABLA: para qué sirve | cuándo usarla
    """
    
    return await self._call_qwen3_sync(prompt)
```

**Nuevo parámetro en `_build_context()`:**
```python
async def _build_context_progressive(
    self,
    ordered_tables: List[Tuple[str, Dict]],
    keywords: List[str],
    max_tokens: int,
    question: str,
) -> Tuple[str, List[str]]:
    """
    Versión progresiva de _build_context():
    1. Incluye tablas completas hasta llenar 70% del contexto
    2. Incluye tablas compactas hasta llenar 85% del contexto
    3. Si quedan tablas, genera resumen con Qwen3 para el 15% restante
    """
    THRESHOLD_FULL    = int(max_tokens * 0.70)
    THRESHOLD_COMPACT = int(max_tokens * 0.85)
    
    parts = [header]
    tables_used = []
    overflow = []
    tokens_used = self._estimate_tokens(header)
    
    for table_name, info in ordered_tables:
        entry = self._table_index.get(table_name)
        if not entry:
            continue
        
        block = self._build_table_block(table_name, entry, info)
        block_tokens = self._estimate_tokens(block)
        
        if tokens_used + block_tokens <= THRESHOLD_FULL:
            # Cabe completa
            parts.append(block)
            tables_used.append(table_name)
            tokens_used += block_tokens
        elif tokens_used + 50 <= THRESHOLD_COMPACT:
            # Solo cabe compacta
            compact = self._build_table_block_compact(table_name, entry, info)
            parts.append(compact)
            tables_used.append(table_name)
            tokens_used += self._estimate_tokens(compact)
        else:
            # No cabe ni compacta → overflow
            overflow.append((table_name, info))
    
    # Si hay overflow, generar resumen con Qwen3
    if overflow and tokens_used < max_tokens - 200:
        summary = await self._synthesize_overflow_tables(overflow, question)
        parts.append(f"\n--- TABLAS ADICIONALES RELACIONADAS ---\n{summary}\n")
        tables_used.extend([t[0] for t in overflow])
    
    parts.append("=== FIN DEL ESQUEMA ===\n")
    return "".join(parts), tables_used
```

**Nota importante**: `_build_context_progressive()` es `async` porque llama a Qwen3. Esto requiere que `get_context()` también sea `async`. Hay que actualizar el ChatService para usar `await`.

---

## PROBLEMA 7: Columnas sensibles ocultas en el contexto del chat

### Situación actual

```python
# context_retriever.py → _build_table_block()
cols_key = entry.get("cols_key", [])
# cols_key se construye en deep_indexer_service.py → _extract_key_columns()
# que excluye columnas sensibles:
if not c["is_sensitive"]:
    key_cols.append(c["name"])
```

### El problema real

Si el usuario pregunta "busca el cliente con NIF 12345678A", la IA no sabe que existe la columna NIF en CLIENTE, y no puede generar el SQL correcto.

Las columnas que SÍ deben estar disponibles para el chat:
- NIF, CIF, DNI → para buscar clientes/proveedores
- EMAIL, TELEFONO → para buscar contactos
- DIRECCION, DOMICILIO → para buscar por ubicación

Las columnas que NO deben estar disponibles:
- PASSWORD, PASS, CLAVE, TOKEN, SECRET → credenciales
- FIRMA, FIRMATRAZOS → datos biométricos
- DATOSPASARELA, DATOSPASARELADESTINO → datos de pago
- EFACTURACONTENIDO, EFACTURAREGISTRO → contenido de facturas electrónicas

### Plan de cambio

```python
# constants.py — NUEVA SEPARACIÓN
class PrivacyConfig:
    # Columnas cuyos VALORES no se muestran a Qwen3 en muestras
    # (pero el nombre SÍ se incluye en el esquema)
    DATA_PRIVACY_COLUMNS = frozenset({
        "NIF", "CIF", "DNI", "IBAN", "BIC",
        "EMAIL", "TELEFONO", "TEL", "MOVIL",
        "FIRMA", "FIRMATRAZOS",
        "DATOSPASARELA", "DATOSPASARELADESTINO",
        "EFACTURACONTENIDO", "EFACTURAREGISTRO",
        "OBSERVACIONES", "OBSERVACIONESWEB",
        "DIRECCION", "DOMICILIO",
    })
    
    # Columnas que NUNCA deben aparecer en el contexto del chat
    # (ni nombre ni valores — credenciales y datos críticos)
    CHAT_BLOCKED_COLUMNS = frozenset({
        "PASSWORD", "PASS", "CLAVE", "TOKEN", "SECRET",
        "FIRMA", "FIRMATRAZOS",
        "DATOSPASARELA", "DATOSPASARELADESTINO",
        "EFACTURACONTENIDO", "EFACTURAREGISTRO",
    })
    
    MAX_SAMPLE_ROWS = 3
    MAX_SAMPLE_COLS = 10
```

---

## RESUMEN DE ARCHIVOS A MODIFICAR

```
constants.py
  → Dividir SENSITIVE_COLUMNS en DATA_PRIVACY_COLUMNS + CHAT_BLOCKED_COLUMNS
  → Añadir constantes de capas de tokens

deep_indexer_service.py
  → _get_column_values(): usar DATA_PRIVACY_COLUMNS (no ocultar nombres)
  → _ask_ai_for_description(): incluir todos los nombres de columna
  → _extract_key_columns(): usar CHAT_BLOCKED_COLUMNS (no DATA_PRIVACY_COLUMNS)
  → _analyze_table_deep(): añadir pasos 2b (texto libre) y 2c (calidad datos)
  → NUEVO: _analyze_text_columns()
  → NUEVO: _ask_ai_text_patterns()
  → NUEVO: _analyze_data_quality()

context_retriever.py
  → get_context(): añadir parámetros progressive, allow_db_query
  → get_context(): añadir paso de contexto temporal
  → _build_context(): reemplazar por _build_context_progressive() (async)
  → _build_table_block(): usar CHAT_BLOCKED_COLUMNS
  → _get_fallback_context(): usar CHAT_BLOCKED_COLUMNS
  → NUEVO: _extract_temporal_context()
  → NUEVO: _synthesize_overflow_tables() (async, llama a Qwen3)
  → NUEVO: _fetch_relevant_data() (async, consulta Firebird en tiempo real)
  → NUEVO: _call_qwen3() helper reutilizable
```

---

## ORDEN DE IMPLEMENTACIÓN RECOMENDADO

```
FASE A — Cambios de bajo riesgo (no rompen nada):
  1. constants.py: dividir SENSITIVE_COLUMNS
  2. context_retriever.py: _extract_temporal_context()
  3. context_retriever.py: incluir NIF/EMAIL en cols_key (solo CHAT_BLOCKED ocultas)

FASE B — Mejoras de indexación (requiere re-indexar):
  4. deep_indexer_service.py: _analyze_text_columns()
  5. deep_indexer_service.py: _analyze_data_quality()
  6. Re-indexar las tablas más importantes (DOCCAB, DOCLIN, ARTICULO, CLIENTE)

FASE C — Análisis progresivo (cambio arquitectural):
  7. context_retriever.py: _build_context_progressive() (async)
  8. context_retriever.py: _synthesize_overflow_tables()
  9. Actualizar ChatService para usar await get_context()

FASE D — Consultas en tiempo real:
  10. context_retriever.py: _fetch_relevant_data()
  11. Integrar con ChatService para preguntas con valores específicos
```

---

## ESTIMACIÓN DE IMPACTO

| Fase | Mejora esperada | Riesgo |
|------|-----------------|--------|
| A | +20% precisión en búsquedas por NIF/EMAIL/fecha | Bajo |
| B | +40% precisión en tablas con datos inconsistentes | Medio |
| C | +60% cobertura en preguntas complejas multi-tabla | Medio |
| D | +80% precisión en preguntas con valores específicos | Alto |

---

*Plan creado el 06/03/2026 — Para ejecutar cuando se indique*
