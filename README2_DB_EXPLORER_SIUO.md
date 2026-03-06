# README2 — DB Explorer & SIUO: Cómo la IA entiende toda la base de datos

> **Versión**: 1.0 — 06/03/2026  
> **Módulo**: `backend/modules/db_explorer/`  
> **Propósito**: Documentación técnica interna para entender, depurar y optimizar el sistema de indexación semántica de la BD Firebird.

---

## 1. EL PROBLEMA QUE RESUELVE

La BD Firebird de JDDC tiene **~437 tablas**. Si enviamos todo el esquema a la IA en cada pregunta:

```
437 tablas × ~50 columnas × ~30 chars/columna ≈ 655.500 chars ≈ 163.875 tokens
```

Eso es **imposible**: los modelos tienen límites de contexto (4K–32K tokens), y aunque cupiera, la IA se "perdería" entre tablas irrelevantes y generaría SQL incorrecto.

**La solución**: el SIUO (Sistema de Índices Unificado Optimizado) analiza la BD **una sola vez** con Qwen3 LAN, construye índices permanentes en disco, y en cada pregunta recupera **solo las 3-8 tablas relevantes** en <1ms.

---

## 2. ARQUITECTURA GENERAL

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SISTEMA DEVIA                                   │
│                                                                         │
│  ┌──────────────┐    pregunta    ┌──────────────────────────────────┐   │
│  │   Usuario /  │ ─────────────► │         ChatService              │   │
│  │  Gafas Meta  │                │  (backend/modules/chat/)         │   │
│  └──────────────┘                └──────────┬───────────────────────┘   │
│                                             │ get_context(pregunta)     │
│                                             ▼                           │
│                                  ┌──────────────────────┐              │
│                                  │   ContextRetriever   │  <1ms        │
│                                  │  (db_explorer/)      │              │
│                                  └──────────┬───────────┘              │
│                                             │ lee índices en RAM        │
│                                             ▼                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    ÍNDICES SIUO (en disco + RAM)                 │   │
│  │                                                                  │   │
│  │  table_index.json   concept_index.json   db_graph.json           │   │
│  │  value_index.json   siuo_progress.json   siuo_query_log.json     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                             ▲                           │
│                                             │ construye (1 vez)         │
│                                  ┌──────────────────────┐              │
│                                  │  DeepIndexerService  │              │
│                                  │  (db_explorer/)      │              │
│                                  └──────────┬───────────┘              │
│                                             │                           │
│                          ┌──────────────────┴──────────────────┐       │
│                          │                                      │       │
│                          ▼                                      ▼       │
│               ┌──────────────────┐                  ┌──────────────┐   │
│               │  Firebird 2.5    │                  │  Qwen3 LAN   │   │
│               │  192.168.0.254   │                  │  192.168.0.36│   │
│               │  (estructura BD) │                  │  (semántica) │   │
│               └──────────────────┘                  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. LOS 4 ÍNDICES PERMANENTES

### 3.1 `table_index.json` — El "diccionario" de tablas

Contiene un resumen ultra-compacto de **cada tabla**, cargado en RAM al arrancar.

```json
{
  "version": "1.0",
  "generated": "2026-03-06T13:39:57",
  "tables": {
    "DOCCAB": {
      "cat":      "documentos",
      "desc":     "Cabecera de documentos (facturas, albaranes, pedidos, presupuestos). TIPO discrimina el tipo de documento.",
      "n":        125847,
      "pk":       ["NUMDOC", "SERIE"],
      "cols_key": ["NUMDOC", "SERIE", "TIPO", "FECHA", "CODCLI", "TOTAL", "ESTADO"],
      "related":  ["DOCLIN", "CLIENTE", "AGENTES", "SERIES"],
      "kw":       ["factura", "albaran", "pedido", "presupuesto", "documento", "venta"],
      "fks":      [{"field": "CODCLI", "ref_table": "CLIENTE", "ref_field": "CODCLI"}],
      "cols_all": ["NUMDOC", "SERIE", "TIPO", "FECHA", "CODCLI", "TOTAL", ...],
      "note":     "TIPO=13 facturas, TIPO=11 albaranes, TIPO=12 pedidos, TIPO=0 presupuestos",
      "queries":  ["SELECT FIRST 10 NUMDOC, FECHA, TOTAL FROM DOCCAB WHERE TIPO=13 ORDER BY FECHA DESC"]
    },
    "DOCLIN": { ... },
    "ARTICULO": { ... },
    "CLIENTE": { ... }
  }
}
```

**¿Por qué es importante?** Cuando la IA necesita contexto sobre DOCCAB, no consulta Firebird — lee este JSON en RAM en microsegundos.

---

### 3.2 `concept_index.json` — El "buscador semántico"

Mapea **palabras en lenguaje natural** → tablas relevantes. Es la clave para que la IA entienda "factura" = tabla DOCCAB con filtro TIPO=13.

```json
{
  "version": "1.0",
  "generated": "2026-03-06T13:39:57",
  "index": {
    "factura":     [{"table": "DOCCAB", "filter": "TIPO=13"}],
    "albaran":     [{"table": "DOCCAB", "filter": "TIPO=11"}],
    "pedido":      [{"table": "DOCCAB", "filter": "TIPO=12"}],
    "presupuesto": [{"table": "DOCCAB", "filter": "TIPO=0"}],
    "articulo":    [{"table": "ARTICULO"}],
    "producto":    [{"table": "ARTICULO"}],
    "stock":       [{"table": "ARTICULO"}, {"table": "ESTALMACEN"}],
    "cliente":     [{"table": "CLIENTE"}],
    "split":       [{"table": "ARTICULO"}],
    "gas":         [{"table": "ARTICULO"}, {"table": "DOCLIN"}],
    "instalacion": [{"table": "DOCCAB", "filter": "TIPO=2"}],
    "mantenimiento":[{"table": "DOCCAB", "filter": "TIPO=10"}]
  }
}
```

**Fuentes del índice**:
1. **Reglas manuales base** (`BASE_CONCEPT_INDEX` en `deep_indexer_service.py`) — siempre presentes
2. **Keywords generados por Qwen3** — añadidos automáticamente al analizar cada tabla

---

### 3.3 `db_graph.json` — El "mapa de relaciones"

Grafo de relaciones entre tablas. Permite expandir el contexto: si preguntas por "facturas", el sistema también incluye automáticamente DOCLIN (líneas de factura) y CLIENTE.

```
DOCCAB ──CODCLI──► CLIENTE
  │
  └──NUMDOC──► DOCLIN ──CODART──► ARTICULO
                                      │
                                      └──CODFAM──► FAMILIAS
```

```json
{
  "nodes": {
    "DOCCAB":  {"n_records": 125847, "category": "documentos"},
    "DOCLIN":  {"n_records": 487293, "category": "documentos"},
    "CLIENTE": {"n_records": 3421,   "category": "clientes"}
  },
  "edges": [
    {"from": "DOCCAB",  "from_col": "CODCLI",  "to": "CLIENTE",  "to_col": "CODCLI",  "type": "fk_explicit"},
    {"from": "DOCLIN",  "from_col": "NUMDOC",  "to": "DOCCAB",   "to_col": "NUMDOC",  "type": "fk_explicit"},
    {"from": "DOCLIN",  "from_col": "CODART",  "to": "ARTICULO", "to_col": "CODART",  "type": "fk_implicit"},
    {"from": "ARTICULO","from_col": "CODFAM",  "to": "FAMILIAS", "to_col": "CODFAM",  "type": "fk_implicit"}
  ],
  "paths": {
    "DOCCAB->ARTICULO": ["DOCCAB", "DOCLIN", "ARTICULO"],
    "CLIENTE->ARTICULO": ["CLIENTE", "DOCCAB", "DOCLIN", "ARTICULO"]
  }
}
```

**Tipos de relaciones detectadas**:
- `fk_explicit`: FKs declaradas en Firebird (`RDB$RELATION_CONSTRAINTS`)
- `fk_implicit`: columnas con el mismo nombre en tablas distintas (CODART, CODCLI, NUMDOC...)

---

### 3.4 `value_index.json` — Los "valores reales"

Contiene valores reales de columnas clave para que la IA sepa qué valores existen sin consultar la BD.

```json
{
  "enums": {
    "DOCCAB.TIPO": {
      "0": 1247,   "2": 892,   "3": 156,
      "10": 2341,  "11": 18432, "12": 9871,
      "13": 45123, "61": 3421
    },
    "DOCCAB.ESTADO": {"0": 12341, "1": 89234, "2": 4521}
  },
  "ranges": {
    "DOCCAB.FECHA":   {"min": "2018-01-02", "max": "2026-03-05"},
    "DOCCAB.TOTAL":   {"min": 0.0, "max": 48750.50, "avg": 1247.83},
    "DOCLIN.PRECIO":  {"min": 0.0, "max": 12500.0,  "avg": 89.45},
    "ARTICULO.STOCK": {"min": -50, "max": 9999,     "avg": 12.3}
  },
  "top_values": {
    "ARTICULO.FAMILIA": [
      {"val": "SPLITS",    "count": 1247},
      {"val": "GAS",       "count": 892},
      {"val": "ACCESORIOS","count": 654}
    ]
  }
}
```

**¿Para qué sirve?** La IA puede responder "¿cuántos tipos de documento hay?" o "¿cuál es el rango de fechas de las facturas?" sin ejecutar SQL.

---

### 3.5 `siuo_progress.json` — Estado del proceso (PERSISTENCIA)

```json
{
  "version": "1.0",
  "started": "2026-03-06T10:00:00",
  "last_updated": "2026-03-06T13:39:57",
  "total_tables": 437,
  "analyzed": 412,
  "failed": 8,
  "pending": 17,
  "failed_tables": ["TABLA_CORRUPTA", "TABLA_SIN_PERMISOS"],
  "status": "running"
}
```

**CLAVE**: Si el proceso se interrumpe (corte de luz, error de red, Qwen3 se cae), al relanzar con `resume=True` **continúa desde donde se quedó**. Las 412 tablas ya analizadas no se reprocesarán.

---

## 4. FLUJO COMPLETO DE INDEXACIÓN (FASE 1: UNA SOLA VEZ)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROCESO DE INDEXACIÓN PROFUNDA                           │
│                    (se ejecuta desde la pestaña "Índices SIUO")             │
└─────────────────────────────────────────────────────────────────────────────┘

  PASO 1: Verificar Qwen3 LAN
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  DeepIndexerService → GET http://192.168.0.36/api/vlm/v1/models         │
  │  Si no responde → CANCELAR (datos nunca salen a internet)                │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │ OK
                                    ▼
  PASO 2: Obtener lista de tablas
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  SELECT RDB$RELATION_NAME FROM RDB$RELATIONS                             │
  │  WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL                     │
  │  → 437 tablas de usuario                                                 │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 3: Para cada tabla (en batches de 5):
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                                                                          │
  │  3a. ESTRUCTURA (Firebird)                                               │
  │      ├── Columnas: nombre, tipo, nullable                                │
  │      ├── Primary Keys (RDB$PRIMARY_KEY)                                  │
  │      ├── Foreign Keys (RDB$FOREIGN_KEY)                                  │
  │      └── COUNT(*) → número de registros                                  │
  │                                                                          │
  │  3b. VALORES REALES (Firebird, sin columnas sensibles)                   │
  │      ├── Columnas TIPO/ESTADO/FLAG → enumerados (GROUP BY)               │
  │      ├── Columnas FECHA/TIMESTAMP → rango min/max                        │
  │      ├── Columnas PRECIO/TOTAL/IMPORTE → min/max/avg                     │
  │      └── Columnas FAMILIA/CATEGORIA → top-20 valores                     │
  │                                                                          │
  │  3c. DESCRIPCIÓN SEMÁNTICA (Qwen3 LAN)                                   │
  │      ├── Prompt: estructura + valores reales (sin datos sensibles)        │
  │      ├── Respuesta JSON: category, description, keywords, queries, nota  │
  │      └── Si Qwen3 falla → fallback local (descripción mínima)            │
  │                                                                          │
  │  3d. ACTUALIZAR ÍNDICES (en memoria + disco)                             │
  │      ├── table_index[tabla] = entrada completa                           │
  │      ├── value_index[tabla.col] = enums/ranges/top_n                     │
  │      └── siuo_progress.json actualizado (persistencia)                   │
  │                                                                          │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 4: Construir grafo de relaciones
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  Para cada tabla:                                                        │
  │    - FKs explícitas → edges tipo "fk_explicit"                           │
  │    - Columnas CODART/CODCLI/NUMDOC... → edges tipo "fk_implicit"         │
  │  BFS entre las 20 tablas más grandes → caminos más cortos                │
  │  → db_graph.json                                                         │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 5: Construir índice de conceptos
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  BASE_CONCEPT_INDEX (reglas manuales) +                                  │
  │  keywords de Qwen3 para cada tabla                                       │
  │  → concept_index.json                                                    │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 6: Sincronizar con db_metadata_optimized.json
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  Solo añade tablas nuevas (no sobreescribe las aprobadas manualmente)    │
  │  → compatibilidad con ChatService v1                                     │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. FLUJO DE RECUPERACIÓN DE CONTEXTO (FASE 2: EN CADA PREGUNTA)

```
Usuario: "¿Qué facturas tiene el cliente García en 2025?"

┌─────────────────────────────────────────────────────────────────────────────┐
│                    ContextRetriever.get_context()                           │
└─────────────────────────────────────────────────────────────────────────────┘

  PASO 1: Normalizar y extraer keywords
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  "¿Qué facturas tiene el cliente García en 2025?"                        │
  │  → lowercase, quitar stopwords (el, tiene, en, qué)                     │
  │  → palabras: ["facturas", "cliente", "garcia", "2025"]                   │
  │  → normalizar plurales: "facturas" → "factura"                           │
  │  → keywords encontrados en concept_index: ["factura", "cliente"]         │
  │  → keywords desconocidos: ["garcia", "2025"] (para autoaprendizaje)      │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 2: Buscar en concept_index (O(1))
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  "factura"  → DOCCAB (filter: TIPO=13)   score=1                        │
  │  "cliente"  → CLIENTE                    score=1                        │
  │  → candidatos directos: {DOCCAB, CLIENTE}                               │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 3: Expandir con grafo (BFS profundidad 2)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  DOCCAB  → vecinos: DOCLIN (score=0.5), AGENTES (score=0.5)             │
  │  CLIENTE → vecinos: DOCCAB (ya está), BANCOS (score=0.5)                │
  │  DOCLIN  → vecinos: ARTICULO (score=0.3)                                │
  │  → expandidos: {DOCCAB, CLIENTE, DOCLIN, AGENTES, ARTICULO}             │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 4: Ordenar por relevancia
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  1. DOCCAB   (score=1,   125.847 registros) ← directo + más datos       │
  │  2. CLIENTE  (score=1,   3.421 registros)   ← directo                   │
  │  3. DOCLIN   (score=0.5, 487.293 registros) ← expandido + muchos datos  │
  │  4. ARTICULO (score=0.3, 8.234 registros)   ← expandido                 │
  │  5. AGENTES  (score=0.5, 45 registros)      ← expandido                 │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 5: Construir contexto con control de tokens
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  max_tokens = 2000                                                       │
  │                                                                          │
  │  TABLA: DOCCAB [WHERE TIPO=13]                                           │
  │    Descripción: Cabecera de documentos...                                │
  │    Registros: 125.847                                                    │
  │    Columnas principales: NUMDOC, SERIE, TIPO, FECHA, CODCLI, TOTAL      │
  │    Relacionada con: DOCLIN, CLIENTE, AGENTES                             │
  │    NOTA: TIPO=13 facturas, TIPO=11 albaranes...                          │
  │    Ejemplo: SELECT FIRST 10 NUMDOC, FECHA, TOTAL FROM DOCCAB...         │
  │  → ~350 tokens                                                           │
  │                                                                          │
  │  TABLA: CLIENTE                                                          │
  │    Descripción: Maestro de clientes...                                   │
  │    Registros: 3.421                                                      │
  │    Columnas principales: CODCLI, NOMBRE, RAZONSOCIAL, POBLACION         │
  │  → ~200 tokens                                                           │
  │                                                                          │
  │  TABLA: DOCLIN                                                           │
  │    Descripción: Líneas de documentos...                                  │
  │    Registros: 487.293                                                    │
  │    Columnas principales: NUMDOC, CODART, CANTIDAD, PRECIO, TOTAL        │
  │  → ~200 tokens                                                           │
  │                                                                          │
  │  Total: ~750 tokens (de 2000 máx) ← MUCHO más eficiente que 163.875    │
  └──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  PASO 6: Registrar para autoaprendizaje
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  siuo_query_log.json:                                                    │
  │  {                                                                       │
  │    "ts": "2026-03-06T13:45:00",                                          │
  │    "question": "¿Qué facturas tiene el cliente García en 2025?",         │
  │    "keywords": ["factura", "cliente"],                                   │
  │    "tables_used": ["DOCCAB", "CLIENTE", "DOCLIN"],                       │
  │    "unknown_kws": ["garcia", "2025"]                                     │
  │  }                                                                       │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## 6. CÓMO LA IA RELACIONA FACTURAS CON ARTÍCULOS, FECHAS Y CLIENTES

### 6.1 El problema de las relaciones multi-tabla

Una pregunta como "¿qué artículos de gas se han vendido en facturas de más de 1000€ en 2025?" implica:

```
DOCCAB (TIPO=13, FECHA 2025, TOTAL>1000)
  └── DOCLIN (líneas de esa factura)
        └── ARTICULO (FAMILIA='GAS')
```

El SIUO resuelve esto en dos niveles:

**Nivel 1 — concept_index**: detecta "factura" → DOCCAB, "artículo" → ARTICULO, "gas" → ARTICULO+DOCLIN

**Nivel 2 — db_graph**: sabe que DOCCAB→DOCLIN→ARTICULO es el camino (path precomputado)

**Resultado en el contexto enviado a la IA**:
```
TABLA: DOCCAB [WHERE TIPO=13]
  Columnas principales: NUMDOC, SERIE, FECHA, TOTAL
  Relacionada con: DOCLIN, CLIENTE

TABLA: DOCLIN
  Columnas principales: NUMDOC, CODART, CANTIDAD, PRECIO
  Relacionada con: DOCCAB, ARTICULO

TABLA: ARTICULO
  Columnas principales: CODART, DESCRIPCION, FAMILIA, PRECIO
  Valores FAMILIA: SPLITS(1247), GAS(892), ACCESORIOS(654)
```

La IA recibe exactamente lo que necesita para generar:
```sql
SELECT FIRST 20
  a.DESCRIPCION, SUM(l.CANTIDAD) as TOTAL_VENDIDO
FROM DOCCAB d
JOIN DOCLIN l ON l.NUMDOC = d.NUMDOC AND l.SERIE = d.SERIE
JOIN ARTICULO a ON a.CODART = l.CODART
WHERE d.TIPO = 13
  AND d.FECHA BETWEEN '01.01.2025' AND '31.12.2025'
  AND d.TOTAL > 1000
  AND a.FAMILIA = 'GAS'
GROUP BY a.DESCRIPCION
ORDER BY TOTAL_VENDIDO DESC
```

### 6.2 El filtro TIPO — clave para documentos

La tabla DOCCAB almacena **todos los tipos de documento** con un discriminador TIPO:

| TIPO | Documento       | Registros aprox |
|------|-----------------|-----------------|
| 0    | Presupuesto     | 1.247           |
| 2    | SAT/Instalación | 892             |
| 3    | Abono           | 156             |
| 10   | Contrato        | 2.341           |
| 11   | Albarán         | 18.432          |
| 12   | Pedido          | 9.871           |
| 13   | Factura         | 45.123          |
| 61   | Recibo          | 3.421           |

El concept_index incluye el filtro automáticamente:
```
"factura" → DOCCAB con filter="TIPO=13"
```

Así la IA **nunca olvida** el WHERE TIPO=13 cuando pregunta por facturas.

---

## 7. ¿QUÉ PASA SI EL CONTEXTO ES MUY LARGO?

### 7.1 Control de tokens en 3 niveles

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTROL DE TOKENS (max_tokens=2000)                      │
└─────────────────────────────────────────────────────────────────────────────┘

  Nivel 1: Límite de tablas
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  MAX_TABLES_IN_CONTEXT = 8                                               │
  │  Solo se incluyen las 8 tablas más relevantes (por score + registros)    │
  └──────────────────────────────────────────────────────────────────────────┘

  Nivel 2: Control por tabla
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  Para cada tabla:                                                        │
  │    tokens_usados + tokens_tabla > max_tokens?                            │
  │      SÍ → intentar versión compacta (1 línea)                           │
  │        ¿Cabe la versión compacta?                                        │
  │          SÍ → incluir compacta y PARAR                                   │
  │          NO → PARAR (no incluir más tablas)                              │
  │      NO → incluir versión completa                                       │
  └──────────────────────────────────────────────────────────────────────────┘

  Nivel 3: Versión compacta
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  Versión completa (~350 tokens):                                         │
  │    TABLA: DOCCAB [WHERE TIPO=13]                                         │
  │      Descripción: Cabecera de documentos...                              │
  │      Registros: 125.847                                                  │
  │      Columnas principales: NUMDOC, SERIE, TIPO, FECHA, CODCLI, TOTAL    │
  │      Relacionada con: DOCLIN, CLIENTE, AGENTES                           │
  │      NOTA: TIPO=13 facturas...                                           │
  │      Ejemplo: SELECT FIRST 10...                                         │
  │                                                                          │
  │  Versión compacta (~30 tokens):                                          │
  │    TABLA: DOCCAB [WHERE TIPO=13] — Cabecera de documentos | Cols: NUMDOC,FECHA,TOTAL,CODCLI
  └──────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Preguntas que implican cientos de tablas

Para preguntas muy amplias ("dame un resumen de toda la actividad de la empresa"), el sistema:

1. **Limita a 8 tablas** (las más relevantes por score)
2. **Usa versiones compactas** si hay muchas tablas
3. **El ChatService puede hacer múltiples llamadas** si necesita más contexto (SQL en varios pasos)

**Ejemplo de pregunta compleja**:
```
"¿Cuál es el margen bruto por familia de artículo en las facturas de 2025?"
```

Keywords detectados: `factura`, `familia`, `articulo`, `margen`

Tablas seleccionadas (por orden de relevancia):
1. DOCCAB (factura, score=1)
2. DOCLIN (líneas, score=0.5, 487K registros)
3. ARTICULO (artículo+familia, score=1)
4. FAMILIAS (familia, score=0.5)

SQL generado:
```sql
SELECT
  a.FAMILIA,
  SUM(l.CANTIDAD * l.PRECIO) as VENTAS,
  SUM(l.CANTIDAD * a.PRECIOCOSTE) as COSTE,
  SUM(l.CANTIDAD * (l.PRECIO - a.PRECIOCOSTE)) as MARGEN
FROM DOCCAB d
JOIN DOCLIN l ON l.NUMDOC = d.NUMDOC
JOIN ARTICULO a ON a.CODART = l.CODART
WHERE d.TIPO = 13
  AND d.FECHA BETWEEN '01.01.2025' AND '31.12.2025'
GROUP BY a.FAMILIA
ORDER BY MARGEN DESC
```

---

## 8. PERSISTENCIA Y RESILIENCIA ANTE ERRORES

### 8.1 ¿Qué pasa si el análisis falla a mitad?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RESILIENCIA DEL PROCESO DE INDEXACIÓN                    │
└─────────────────────────────────────────────────────────────────────────────┘

  Escenario: Analizando tabla 250/437, Qwen3 se cae
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  siuo_progress.json:                                                     │
  │  {                                                                       │
  │    "status": "running",                                                  │
  │    "analyzed": 249,                                                      │
  │    "failed": 1,                                                          │
  │    "pending": 187,                                                       │
  │    "failed_tables": ["TABLA_250"]                                        │
  │  }                                                                       │
  │                                                                          │
  │  table_index.json: contiene las 249 tablas ya analizadas                 │
  │  value_index.json: contiene los valores de las 249 tablas                │
  └──────────────────────────────────────────────────────────────────────────┘

  Al relanzar con resume=True:
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  analyzed_set = {249 tablas ya en table_index}                          │
  │  pending = [tablas NO en analyzed_set] = 188 tablas                     │
  │  → Continúa desde la tabla 250                                           │
  │  → Las 249 tablas anteriores NO se reprocesarán                         │
  └──────────────────────────────────────────────────────────────────────────┘
```

### 8.2 ¿Qué pasa si Qwen3 falla para una tabla específica?

```python
# En _ask_ai_for_description():
try:
    resp = await client.post(...)
    return _parse_json_response(raw)
except Exception:
    # Fallback local — descripción mínima pero funcional
    return {
        "category": "otros",
        "description": f"Tabla {table_name} ({record_count:,} registros)",
        "keywords": [table_name.lower()],
        "consultas_comunes": [f"SELECT FIRST 10 * FROM {table_name}"],
        "_nota_critica": None,
    }
```

La tabla se indexa con descripción mínima. El proceso continúa. La tabla fallida se puede re-analizar individualmente desde la UI.

### 8.3 ¿Qué pasa si el JSON de Qwen3 es inválido?

```python
def _parse_json_response(raw: str) -> Dict:
    # Intenta extraer JSON de bloques markdown (```json ... ```)
    # Busca el primer { y el último }
    # Si falla → devuelve {} → se usa fallback_description()
```

### 8.4 Persistencia de los índices

| Archivo | Cuándo se escribe | Cuándo se lee |
|---------|-------------------|---------------|
| `table_index.json` | Tras cada tabla analizada | Al arrancar DEVIA (cargado en RAM) |
| `concept_index.json` | Al final del proceso | Al arrancar DEVIA (cargado en RAM) |
| `db_graph.json` | Al final del proceso | Al arrancar DEVIA (cargado en RAM) |
| `value_index.json` | Al final del proceso | Al arrancar DEVIA (cargado en RAM) |
| `siuo_progress.json` | Tras cada tabla | Al relanzar el proceso |
| `siuo_query_log.json` | En cada pregunta del chat | Al pedir sugerencias de aprendizaje |

**Los índices sobreviven a reinicios del servidor**. Una vez construidos, DEVIA arranca en <1 segundo con todo el conocimiento de la BD en RAM.

---

## 9. AUTOAPRENDIZAJE Y MEJORA CONTINUA

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CICLO DE AUTOAPRENDIZAJE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  1. Usuario pregunta: "¿Cuántos splits se han instalado este año?"
     → keywords: ["splits", "instalado", "año"]
     → "splits" NO está en concept_index → unknown_kw
     → "instalado" NO está → unknown_kw
     → siuo_query_log["unknown_keywords"]["splits"] += 1

  2. Tras 10 preguntas con "splits":
     → get_learning_suggestions() devuelve:
       {
         "unknown_keywords_frequent": [
           {"keyword": "splits", "count": 10},
           {"keyword": "instalacion", "count": 7}
         ],
         "suggestion": "Considera añadir estos keywords al concept_index"
       }

  3. Acción manual (o automática futura):
     → Añadir al BASE_CONCEPT_INDEX:
       "splits": [{"table": "ARTICULO"}],
       "instalacion": [{"table": "DOCCAB", "filter": "TIPO=2"}]

  4. Re-indexar (o añadir manualmente al concept_index.json)
     → Las próximas preguntas sobre "splits" encontrarán ARTICULO directamente
```

### 9.1 Feedback del usuario

```python
retriever.register_feedback(
    question="¿Cuántos splits se han instalado?",
    sql_used="SELECT COUNT(*) FROM DOCCAB WHERE TIPO=2",
    was_correct=True,
    tables_used=["DOCCAB"]
)
```

El feedback se guarda en `siuo_query_log.json["feedback"]` para análisis futuro.

---

## 10. PRIVACIDAD Y SEGURIDAD

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COLUMNAS SENSIBLES (PrivacyConfig)                       │
└─────────────────────────────────────────────────────────────────────────────┘

  SENSITIVE_COLUMNS = {
    "NIF", "CIF", "DNI", "IBAN", "BIC",
    "EMAIL", "TELEFONO", "TEL", "MOVIL",
    "PASSWORD", "PASS", "CLAVE", "TOKEN", "SECRET",
    "FIRMA", "FIRMATRAZOS",
    "DATOSPASARELA", "DATOSPASARELADESTINO",
    "EFACTURACONTENIDO", "EFACTURAREGISTRO",
    "OBSERVACIONES", "OBSERVACIONESWEB",
    "DIRECCION", "DOMICILIO"
  }

  Estas columnas se excluyen en 3 niveles:

  Nivel 1 — Muestras a Qwen3:
    _get_column_values() → salta columnas sensibles
    → Qwen3 nunca ve valores de NIF, EMAIL, IBAN, etc.

  Nivel 2 — Contexto al chat:
    _build_table_block() → cols_key no incluye columnas sensibles
    → La IA no sabe que existen esas columnas

  Nivel 3 — Fallback v1:
    _filter_sensitive_columns_from_schema() → filtra líneas del esquema
    → Incluso en modo fallback, las columnas sensibles no llegan a la IA

  REGLA ABSOLUTA: Ningún dato sale a internet.
    → Solo se usa Qwen3 LAN (192.168.0.36)
    → Si Qwen3 no está disponible → proceso cancelado
    → Nunca se usa OpenAI/Groq/Gemini para análisis de BD
```

---

## 11. DIAGRAMA DE ARCHIVOS Y DEPENDENCIAS

```
backend/modules/db_explorer/
├── constants.py              ← Constantes (timeouts, privacidad, categorías)
├── deep_indexer_service.py   ← FASE 1: construye los 4 índices
├── context_retriever.py      ← FASE 2: recupera contexto en <1ms
├── metadata_builder_service.py ← Análisis tabla a tabla (UI manual)
├── metadata_builder_router.py  ← API REST /api/metadata-builder/*
├── siuo_router.py              ← API REST /api/siuo/*
└── DEVIA.MD                    ← Documentación del módulo

backend/core/config/
├── table_index.json          ← Índice de tablas (cargado en RAM)
├── concept_index.json        ← Índice de conceptos (cargado en RAM)
├── db_graph.json             ← Grafo de relaciones (cargado en RAM)
├── value_index.json          ← Valores reales (cargado en RAM)
├── siuo_progress.json        ← Estado del proceso (persistencia)
├── siuo_query_log.json       ← Log de consultas (autoaprendizaje)
└── db_metadata_optimized.json ← Metadatos v1 (compatibilidad)

backend/drivers/db/
└── firebird_metadata_queries.py ← SQL de introspección Firebird

frontend/
├── assets/js/modules/siuo.js           ← UI pestaña "Índices SIUO"
├── assets/js/modules/metadata_builder.js ← UI pestaña "Constructor BD"
└── assets/css/siuo.css                 ← Estilos
```

---

## 12. MÉTRICAS DE RENDIMIENTO

| Operación | Sin SIUO | Con SIUO |
|-----------|----------|----------|
| Contexto para 1 pregunta | ~163.875 tokens | ~500-2000 tokens |
| Tiempo de recuperación | N/A (imposible) | <1ms |
| Tablas en contexto | 437 (todo) | 3-8 (relevantes) |
| Precisión SQL | Baja (IA perdida) | Alta (contexto preciso) |
| Coste por pregunta | Imposible | ~0.001€ (IA local) |

---

## 13. CÓMO OPTIMIZARLO

### 13.1 Mejorar el concept_index

El mayor impacto en precisión viene de enriquecer el concept_index con términos del negocio:

```python
# En deep_indexer_service.py → BASE_CONCEPT_INDEX
BASE_CONCEPT_INDEX = {
    # Añadir términos específicos del negocio:
    "split":        [{"table": "ARTICULO"}],
    "inverter":     [{"table": "ARTICULO"}],
    "gas r32":      [{"table": "ARTICULO"}],
    "garantia":     [{"table": "DOCCAB", "filter": "TIPO=10"}],
    "revision":     [{"table": "DOCCAB", "filter": "TIPO=2"}],
    "impago":       [{"table": "DOCCAB"}, {"table": "CAJA"}],
    "comision":     [{"table": "AGENTES"}, {"table": "DOCCAB"}],
}
```

### 13.2 Ajustar MAX_TOKENS_DEFAULT

```python
# En context_retriever.py
MAX_TOKENS_DEFAULT = 2000   # Aumentar si el modelo tiene más contexto
MAX_TABLES_IN_CONTEXT = 8   # Aumentar para preguntas más complejas
BFS_MAX_DEPTH = 2           # Aumentar para relaciones más lejanas
```

### 13.3 Re-indexar tablas con errores

Desde la UI (pestaña "Constructor BD"):
- Ver tablas con descripción mínima (fallback)
- Re-analizar individualmente cuando Qwen3 esté disponible

### 13.4 Añadir FKs implícitas

```python
# En deep_indexer_service.py → IMPLICIT_FK_PATTERNS
IMPLICIT_FK_PATTERNS = {
    "CODART":    "ARTICULO",
    "CODCLI":    "CLIENTE",
    # Añadir más patrones específicos de JDDC:
    "CODTECNICO": "EMPLEADOS",
    "CODZONA":    "ZONAS",
    "CODTARIFA":  "TARIFAS",
}
```

---

## 14. PREGUNTAS FRECUENTES

**¿Cuánto tarda la indexación completa?**
- ~437 tablas × ~30 segundos/tabla (Qwen3 30B) ≈ 3-4 horas
- Con `resume=True`, se puede hacer en varias sesiones
- Una vez hecho, no necesita repetirse (solo si cambia el esquema)

**¿Hay que re-indexar si se añade una tabla nueva?**
- No necesariamente. El fallback v1 sigue funcionando para tablas no indexadas
- Se puede indexar solo la tabla nueva desde la UI

**¿Qué pasa si el concept_index no tiene la palabra buscada?**
- El sistema devuelve `keywords_unknown` en el meta
- Usa el fallback v1 (db_metadata_optimized.json completo)
- Registra el keyword desconocido para sugerencias de mejora

**¿Puede la IA responder preguntas sobre datos históricos con fechas?**
- Sí. El value_index contiene rangos de fechas por tabla
- El contexto incluye: `Rango FECHA: 2018-01-02 a 2026-03-05`
- La IA sabe qué rango de fechas tiene cada tabla y genera SQL correcto

**¿Qué pasa si hay 200 tablas relacionadas con una pregunta?**
- El BFS se limita a profundidad 2 y MAX_TABLES_IN_CONTEXT=8
- Solo las 8 más relevantes (por score + número de registros) llegan al contexto
- El resto se ignora — la IA trabaja con lo más importante

---

*Documento generado el 06/03/2026 — DEVIA v3.1.0*
