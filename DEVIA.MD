# DEVIA — Documentacion Tecnica del Sistema
## Backend IA para Gafas Meta Ray-Ban + Chat Web + Constructor BD

> **Ultima actualizacion:** 09/03/2026
> **Version:** 2.4.0
> **Ruta:** `bots/interjddcia/`

---

## ARRANQUE RAPIDO

```
ARRANCAR_DEVIA.bat   <- doble clic para arrancar todo
PARAR_DEVIA.bat      <- doble clic para parar todo
```

El script `ARRANCAR_DEVIA.bat` muestra un menu con 4 opciones:

| Opcion | Que arranca | Cuando usarla |
|--------|------------|---------------|
| **1** | Solo Backend DEVIA (puerto 8001) | Chat IA web, gafas Meta, API |
| **2** | Backend DEVIA + CodeLab desktop | Uso completo del sistema |
| **3** | Solo CodeLab desktop | Editor de codigo con IA |
| **4** | Diagnostico (sin arrancar nada) | Verificar estado del sistema |

**Uso mas habitual -> opcion 1** (o simplemente pulsa Enter).

Tras arrancar, se abre automaticamente: **http://localhost:8001**

---

## INDICE

1. [Arquitectura del sistema](#1-arquitectura)
2. [Sistema actual de metadatos — analisis critico](#2-sistema-actual-analisis-critico)
3. [NUEVO: Sistema de Indices Ultra-Optimizado (SIUO)](#3-nuevo-sistema-siuo)
4. [Arquitectura de ficheros del SIUO](#4-arquitectura-ficheros-siuo)
5. [Flujo completo: pregunta -> SQL -> respuesta](#5-flujo-completo)
6. [Modo AI_LOCAL_ONLY — Solo Qwen3 LAN](#6-modo-ai_local_only)
7. [Resiliencia del sistema](#7-resiliencia)
8. [Diagnosticos frecuentes](#8-diagnosticos)
9. [Como levantar el backend](#9-como-levantar)
10. [Comandos de diagnostico rapido](#10-comandos-diagnostico)
11. [Archivos clave](#11-archivos-clave)

---

## 1. Arquitectura

```
GAFAS META RAY-BAN (Android)
        |
        | POST http://192.168.0.38:8001/api/chat/send
        v
Backend DEVIA (bots/interjddcia/)
        |  FastAPI + Python
        |
        +- ChatService (service.py)
        |    +- get_semantic_schema() -> db_metadata_optimized.json (ACTUAL)
        |    +- [NUEVO] ContextRetriever -> SIUO indices (FUTURO)
        |    +- Extrae SQL de la respuesta IA
        |    +- FirebirdSQLNormalizer -> limpia LIMIT/ROWS/ILIKE
        |    +- SQLCorrector -> reintentos con correccion IA
        |    +- execute_with_correction() -> reintentos SQL
        |
        +- ModelFallbackOrchestrator (model_fallback_orchestrator.py)
        |    +- Lee ai_local_only de config.json en cada llamada
        |    +- Si ai_local_only=true -> solo modelos jddcia-* (LAN)
        |    +- Si ai_local_only=false -> fallback multi-modelo (189 modelos)
        |
        +- JDDCIAProvider (drivers/ai/jddcia_provider.py)
        |    +- URL primaria:   http://192.168.0.36/api/vlm/v1  (IP directa)
        |    +- URL secundaria: http://jddcia.local/api/vlm/v1  (mDNS, falla en Windows)
        |    +- Modelo: unified-main (Qwen3 VL 30B)
        |    +- Timeout: 20s
        |
        +- MetadataBuilderService (modules/db_explorer/)
        |    +- check_local_ai() -> verifica Qwen3 LAN
        |    +- get_all_tables() -> lista 437 tablas Firebird
        |    +- get_table_structure() -> columnas, PKs, FKs, muestra
        |    +- analyze_table_with_local_ai() -> genera JSON metadatos
        |    +- save_table_metadata() -> persiste en db_metadata_optimized.json
        |    +- [NUEVO] deep_analyze_table() -> analisis profundo con SIUO
        |
        +- FirebirdDriver (drivers/db/)
             +- BD: Firebird 2.5 @ 192.168.0.254:3050 (empresa.fdb)
             +- 437 tablas de usuario
             +- ~11.846 articulos, datos reales de empresa
```

---

## 2. Sistema actual de metadatos — analisis critico

### Como funciona HOY

El sistema actual usa un unico fichero JSON (`db_metadata_optimized.json`) que contiene
metadatos de las tablas analizadas. Cuando el usuario hace una pregunta al chat:

```
Pregunta: "dime los articulos con mas compras"
    |
    v
get_semantic_schema()
    |
    v
Lee db_metadata_optimized.json COMPLETO
    |
    v
Construye un string de texto con TODAS las tablas que tienen metadatos
    |
    v
Envia ese string al modelo IA como contexto del system prompt
    |
    v
IA genera SQL
    |
    v
Se ejecuta en Firebird
```

### Problemas criticos del sistema actual

**PROBLEMA 1: Contexto monolitico — todo o nada**
- Se envia el JSON completo al modelo, independientemente de la pregunta
- Con 8 tablas ya son ~3.000 tokens de contexto
- Con 437 tablas analizadas serian ~160.000 tokens — IMPOSIBLE de enviar
- El modelo no puede procesar tanto contexto de golpe

**PROBLEMA 2: Sin indices — busqueda lineal**
- Para saber que tablas son relevantes para "articulos con mas compras",
  el sistema no tiene forma de buscar rapidamente
- No hay indices por concepto, por relacion, por tipo de dato, etc.
- No hay mapa de relaciones entre tablas

**PROBLEMA 3: Metadatos superficiales**
- Solo se guarda: categoria, descripcion, columnas con descripcion corta, consultas ejemplo
- No se guardan: valores reales de columnas clave, distribuciones, rangos, enumerados
- No se sabe que valores tiene DOCCAB.TIPO (13=factura, 11=albaran, etc.)
- No se sabe que rango de fechas hay en los datos
- No se sabe cuales son los articulos mas vendidos, los clientes mas activos, etc.

**PROBLEMA 4: Sin grafo de relaciones**
- No hay un mapa de como se relacionan las 437 tablas entre si
- Para responder "articulos con mas compras" hay que saber:
  ARTICULO -> DOCCAB (via CODART) -> DOCLIN (lineas de documento)
  Pero el sistema no tiene este mapa disponible rapidamente

**PROBLEMA 5: Sin manejo de fallos inteligente**
- Si el SQL falla, se reintenta con la misma IA pero sin contexto adicional
- No se guarda el historial de fallos para aprender
- No se descompone la pregunta en sub-preguntas mas simples

**PROBLEMA 6: Solo 8 de 437 tablas analizadas**
- El 98% de la base de datos es desconocida para la IA
- Tablas criticas como DOCLIN (lineas de documentos) no tienen metadatos

### Lo que SI funciona bien

- FirebirdSQLNormalizer: correccion determinista de SQL (LIMIT->FIRST, ILIKE->UPPER)
- SQLCorrector: reintentos con correccion IA (hasta 4 intentos)
- ModelFallbackOrchestrator: fallback a 189 modelos si la IA local falla
- Interpretacion determinista para voz (sin segunda llamada IA)
- Constructor BD: UI para analizar tablas una a una con Qwen3 LAN

---

## 3. NUEVO: Sistema de Indices Ultra-Optimizado (SIUO)

### Vision general

El SIUO es un sistema de conocimiento permanente sobre la base de datos Firebird,
construido y mantenido por Qwen3 VL 30B (IA local LAN), que permite:

1. **Indexacion completa**: todas las 437 tablas analizadas y catalogadas
2. **Busqueda rapida por concepto**: dado "articulos con mas compras", encontrar
   en <100ms las tablas y columnas relevantes sin enviar nada a la IA
3. **Contexto minimo y preciso**: enviar a la IA SOLO lo que necesita para
   responder la pregunta concreta (no todo el esquema)
4. **Grafo de relaciones**: mapa completo de como se relacionan todas las tablas
5. **Valores reales**: enumerados, rangos, top-N valores de columnas clave
6. **Analisis incremental**: procesar tabla a tabla, guardando resultados parciales
7. **Auto-correccion**: si el SQL falla, la IA recibe el error y el contexto
   adicional para intentarlo de otra forma

### Principios de diseno

- **Solo Qwen3 LAN**: ningun dato de la BD sale a internet. Nunca.
- **Permanente**: los indices se construyen una vez y se actualizan incrementalmente
- **Rapido**: busqueda por indices en memoria, no consultas a Firebird en cada pregunta
- **Tolerante a fallos**: si Qwen3 falla en una tabla, se guarda el progreso y se continua
- **Incremental**: se puede analizar 1 tabla, 10 tablas, o todas — el progreso se guarda
- **Tokens controlados**: cada chunk enviado a Qwen3 tiene un limite de tokens calculado

### Componentes del SIUO

```
SIUO/
|
+-- [1] INDEXADOR (nuevo: deep_indexer_service.py)
|       Analiza cada tabla en profundidad:
|       - Estructura completa (columnas, tipos, PKs, FKs)
|       - Valores reales de columnas clave (enumerados, rangos, top-N)
|       - Relaciones con otras tablas (via FKs y nombres de columnas)
|       - Descripcion semantica generada por Qwen3
|       - Consultas SQL de ejemplo validadas
|       - Errores comunes y como evitarlos
|
+-- [2] GRAFO DE RELACIONES (nuevo: db_graph.json)
|       Mapa de todas las relaciones entre tablas:
|       - FKs explicitas (definidas en Firebird)
|       - FKs implicitas (detectadas por nombre de columna: CODART, CODCLI, etc.)
|       - Peso de cada relacion (cuantos registros relacionados hay)
|       - Camino mas corto entre dos tablas
|
+-- [3] INDICE DE CONCEPTOS (nuevo: concept_index.json)
|       Mapa de palabras/conceptos -> tablas relevantes:
|       - "articulo", "producto", "referencia" -> ARTICULO
|       - "factura", "venta", "documento" -> DOCCAB (TIPO=13)
|       - "compra", "pedido proveedor" -> DOCCAB (TIPO=12)
|       - "linea", "detalle", "cantidad" -> DOCLIN
|       - "cliente" -> CLIENTE
|       - "proveedor" -> PROVEED
|       - "stock", "almacen" -> ALMACEN, ESTALMACEN
|       Generado automaticamente por Qwen3 + reglas manuales
|
+-- [4] INDICE DE VALORES (nuevo: value_index.json)
|       Valores reales de columnas clave:
|       - DOCCAB.TIPO: {0: "presupuesto", 2: "SAT", 3: "abono", 10: "contrato",
|                       11: "albaran", 12: "pedido", 13: "factura", 51: "certificacion",
|                       61: "recibo"}
|       - ARTICULO.FAMILIA: lista de familias reales con conteo
|       - CLIENTE.PROVINCIA: lista de provincias con conteo
|       - Rangos de fechas en DOCCAB, DOCLIN, etc.
|       - Top-10 articulos mas vendidos, clientes mas activos, etc.
|
+-- [5] INDICE DE TABLAS (nuevo: table_index.json)
|       Resumen ultra-compacto de cada tabla (para busqueda rapida):
|       - nombre, categoria, descripcion (1 linea), n_registros
|       - columnas_clave (solo las importantes)
|       - tablas_relacionadas (lista de nombres)
|       - keywords (palabras clave para busqueda)
|       Cargado en memoria al arrancar el backend
|
+-- [6] CONTEXT RETRIEVER (nuevo: context_retriever.py)
|       Dado una pregunta en lenguaje natural:
|       1. Extrae keywords de la pregunta
|       2. Busca en concept_index.json -> tablas candidatas
|       3. Expande con grafo de relaciones -> tablas relacionadas
|       4. Carga detalles de table_index.json -> contexto compacto
|       5. Si necesita mas detalle, carga de db_metadata_optimized.json
|       6. Calcula tokens del contexto -> si excede limite, recorta
|       7. Devuelve contexto optimo para enviar a la IA
|
+-- [7] ANALIZADOR PROFUNDO (nuevo: deep_analyzer.py)
|       Analiza una tabla en profundidad con Qwen3:
|       - Paso 1: estructura basica (columnas, tipos, PKs, FKs)
|       - Paso 2: valores reales de columnas clave (muestra sin sensibles)
|       - Paso 3: relaciones implicitas (por nombre de columna)
|       - Paso 4: descripcion semantica completa
|       - Paso 5: consultas SQL de ejemplo y validacion
|       Cada paso es independiente -> si falla uno, se guarda lo que hay
```

### Flujo de construccion del SIUO (una vez, o cuando hay cambios)

```
Usuario pulsa "Analizar BD completa con Qwen3"
    |
    v
[1] Obtener lista de 437 tablas de Firebird
    |
    v
[2] Para cada tabla (en batches de 10):
    |
    +-- [2a] Obtener estructura (columnas, PKs, FKs) de Firebird
    |
    +-- [2b] Obtener muestra de datos (sin columnas sensibles)
    |
    +-- [2c] Obtener valores de columnas clave (enumerados, top-N)
    |
    +-- [2d] Enviar a Qwen3 LAN (chunk <= 2000 tokens):
    |         "Analiza esta tabla y genera metadatos JSON"
    |
    +-- [2e] Si Qwen3 falla:
    |         - Guardar error en progress.json
    |         - Continuar con la siguiente tabla
    |         - Reintentar las fallidas al final
    |
    +-- [2f] Guardar resultado en:
    |         - db_metadata_optimized.json (metadatos completos)
    |         - table_index.json (resumen compacto)
    |         - concept_index.json (keywords -> tabla)
    |         - db_graph.json (relaciones)
    |
    v
[3] Construir grafo de relaciones completo
    |
    v
[4] Construir indice de conceptos completo
    |
    v
[5] Construir indice de valores (enumerados, rangos, top-N)
    |
    v
[6] Guardar progress.json con estado final
    |
    v
Sistema listo para responder preguntas con contexto optimo
```

### Flujo de respuesta a una pregunta (con SIUO activo)

```
Pregunta: "dime los articulos que tienen mas compras"
    |
    v
[1] ContextRetriever.get_context(pregunta)
    |
    +-- Extrae keywords: ["articulos", "compras", "mas"]
    |
    +-- Busca en concept_index: 
    |     "articulo" -> ARTICULO
    |     "compra" -> DOCCAB (TIPO=12), DOCLIN
    |
    +-- Expande con grafo:
    |     ARTICULO <-> DOCLIN (via CODART)
    |     DOCLIN <-> DOCCAB (via NUMDOC)
    |
    +-- Carga contexto compacto de table_index:
    |     ARTICULO: tabla de articulos, columnas clave: CODART, NOMBRE, FAMILIA
    |     DOCCAB: cabecera documentos, TIPO=12 son pedidos a proveedor
    |     DOCLIN: lineas de documentos, CODART, CANTIDAD, PRECIO
    |
    +-- Calcula tokens: ~800 tokens (dentro del limite)
    |
    +-- Devuelve contexto optimo
    |
    v
[2] Enviar a Qwen3 LAN:
    system: "Eres experto en Firebird. Esquema relevante: [contexto 800 tokens]"
    user: "dime los articulos que tienen mas compras"
    |
    v
[3] Qwen3 genera SQL:
    SELECT FIRST 10 a.CODART, a.NOMBRE, SUM(l.CANTIDAD) as TOTAL_COMPRADO
    FROM ARTICULO a
    JOIN DOCLIN l ON l.CODART = a.CODART
    JOIN DOCCAB d ON d.NUMDOC = l.NUMDOC AND d.TIPO = 12
    GROUP BY a.CODART, a.NOMBRE
    ORDER BY TOTAL_COMPRADO DESC
    |
    v
[4] FirebirdSQLNormalizer normaliza el SQL
    |
    v
[5] Ejecutar en Firebird
    |
    +-- Si falla:
    |     - Enviar a Qwen3: error + SQL fallido + contexto adicional
    |     - Qwen3 corrige el SQL
    |     - Reintentar (hasta 4 veces)
    |
    v
[6] Interpretar resultados y responder al usuario
```

---

## 4. Arquitectura de ficheros del SIUO

```
bots/interjddcia/backend/core/config/
|
+-- db_metadata_optimized.json          <- EXISTENTE: metadatos completos por tabla
|   {
|     "tables": {
|       "ARTICULO": {
|         "category": "maestros",
|         "description": "Catalogo de articulos/productos",
|         "primary_keys": ["CODART"],
|         "columns": {"CODART": "VARCHAR - codigo unico del articulo", ...},
|         "consultas_comunes": ["SELECT FIRST 10 CODART, NOMBRE FROM ARTICULO"],
|         "record_count": 11846
|       }
|     }
|   }
|
+-- [NUEVO] table_index.json            <- Resumen ultra-compacto (cargado en memoria)
|   {
|     "version": "1.0",
|     "generated": "2026-03-04",
|     "tables": {
|       "ARTICULO": {
|         "cat": "maestros",
|         "desc": "Catalogo de articulos/productos de la empresa",
|         "n": 11846,
|         "pk": ["CODART"],
|         "cols_key": ["CODART", "NOMBRE", "FAMILIA", "PRECIO", "STOCKARTICULO"],
|         "related": ["DOCLIN", "ALMACEN", "ESTALMACEN"],
|         "kw": ["articulo", "producto", "referencia", "stock", "precio", "familia"]
|       },
|       "DOCCAB": {
|         "cat": "transacciones",
|         "desc": "Cabecera de documentos (facturas, albaranes, pedidos, etc.)",
|         "n": 85000,
|         "pk": ["NUMDOC", "TIPO"],
|         "cols_key": ["NUMDOC", "TIPO", "FECHA", "CODCLI", "TOTAL", "ESTADO"],
|         "related": ["DOCLIN", "CLIENTE", "PROVEED"],
|         "kw": ["factura", "albaran", "pedido", "presupuesto", "venta", "compra",
|                "documento", "cabecera", "total", "importe"]
|       }
|     }
|   }
|
+-- [NUEVO] concept_index.json          <- Mapa concepto -> tablas
|   {
|     "version": "1.0",
|     "index": {
|       "articulo":    ["ARTICULO"],
|       "producto":    ["ARTICULO"],
|       "referencia":  ["ARTICULO"],
|       "stock":       ["ARTICULO", "ALMACEN", "ESTALMACEN"],
|       "factura":     [{"table": "DOCCAB", "filter": "TIPO=13"}],
|       "albaran":     [{"table": "DOCCAB", "filter": "TIPO=11"}],
|       "pedido":      [{"table": "DOCCAB", "filter": "TIPO=12"}],
|       "presupuesto": [{"table": "DOCCAB", "filter": "TIPO=0"}],
|       "venta":       [{"table": "DOCCAB", "filter": "TIPO IN (11,13)"}],
|       "compra":      [{"table": "DOCCAB", "filter": "TIPO=12"}],
|       "linea":       ["DOCLIN"],
|       "detalle":     ["DOCLIN"],
|       "cantidad":    ["DOCLIN"],
|       "cliente":     ["CLIENTE"],
|       "proveedor":   ["PROVEED"],
|       "almacen":     ["ALMACEN", "ESTALMACEN"],
|       "precio":      ["ARTICULO", "DOCLIN"],
|       "familia":     ["ARTICULO"],
|       "caja":        ["CAJA"],
|       "aviso":       ["AVISOS"]
|     }
|   }
|
+-- [NUEVO] db_graph.json               <- Grafo de relaciones entre tablas
|   {
|     "version": "1.0",
|     "nodes": {
|       "ARTICULO": {"n_records": 11846, "category": "maestros"},
|       "DOCCAB":   {"n_records": 85000, "category": "transacciones"},
|       "DOCLIN":   {"n_records": 320000, "category": "transacciones"}
|     },
|     "edges": [
|       {
|         "from": "DOCLIN", "from_col": "CODART",
|         "to": "ARTICULO", "to_col": "CODART",
|         "type": "fk_explicit",
|         "weight": 320000
|       },
|       {
|         "from": "DOCLIN", "from_col": "NUMDOC",
|         "to": "DOCCAB", "to_col": "NUMDOC",
|         "type": "fk_explicit",
|         "weight": 320000
|       },
|       {
|         "from": "DOCCAB", "from_col": "CODCLI",
|         "to": "CLIENTE", "to_col": "CODCLI",
|         "type": "fk_implicit",
|         "weight": 85000
|       }
|     ],
|     "paths": {
|       "ARTICULO->DOCCAB": ["ARTICULO", "DOCLIN", "DOCCAB"],
|       "CLIENTE->ARTICULO": ["CLIENTE", "DOCCAB", "DOCLIN", "ARTICULO"]
|     }
|   }
|
+-- [NUEVO] value_index.json            <- Valores reales de columnas clave
|   {
|     "version": "1.0",
|     "enums": {
|       "DOCCAB.TIPO": {
|         "0": "presupuesto",
|         "2": "orden de trabajo / SAT",
|         "3": "abono",
|         "10": "contrato",
|         "11": "albaran",
|         "12": "pedido a proveedor",
|         "13": "factura",
|         "51": "certificacion",
|         "61": "recibo"
|       },
|       "ARTICULO.FAMILIA": {
|         "values": ["SPLIT", "CASSETTE", "CONDUCTOS", "RECAMBIOS", "GAS", ...],
|         "top10": [{"val": "SPLIT", "count": 3200}, ...]
|       }
|     },
|     "ranges": {
|       "DOCCAB.FECHA": {"min": "2015-01-01", "max": "2026-03-04"},
|       "ARTICULO.PRECIO": {"min": 0.5, "max": 15000.0, "avg": 245.3}
|     },
|     "top_values": {
|       "ARTICULO_mas_vendidos": [
|         {"CODART": "ART001", "NOMBRE": "Split 2.5kW", "total_vendido": 450},
|         ...
|       ],
|       "CLIENTE_mas_activos": [
|         {"CODCLI": "CLI001", "NOMBRE": "Empresa X", "n_facturas": 120},
|         ...
|       ]
|     }
|   }
|
+-- [NUEVO] siuo_progress.json          <- Estado del proceso de indexacion
    {
      "version": "1.0",
      "started": "2026-03-04T10:00:00",
      "last_updated": "2026-03-04T11:30:00",
      "total_tables": 437,
      "analyzed": 150,
      "failed": 5,
      "pending": 282,
      "failed_tables": ["TABLA_X", "TABLA_Y"],
      "status": "running"  // "running" | "completed" | "paused"
    }
```

---

## 5. Flujo completo: pregunta -> SQL -> respuesta

### Flujo actual (v1 — sistema existente)

```
Pregunta usuario
    -> get_semantic_schema() -> db_metadata_optimized.json COMPLETO (~3000 tokens)
    -> System prompt con TODO el esquema
    -> IA genera SQL
    -> FirebirdSQLNormalizer (determinista)
    -> SQLCorrector (reintentos con IA si falla)
    -> Ejecutar en Firebird
    -> Interpretar resultados (determinista para voz, IA para web)
    -> Respuesta
```

### Flujo nuevo (v2 — con SIUO)

```
Pregunta usuario
    -> ContextRetriever.get_context(pregunta)
       |-> Extrae keywords
       |-> Busca en concept_index (en memoria, <1ms)
       |-> Expande con db_graph (en memoria, <1ms)
       |-> Carga detalles de table_index (en memoria, <1ms)
       |-> Calcula tokens -> recorta si necesario
       |-> Devuelve contexto optimo (~500-1500 tokens)
    -> System prompt con contexto MINIMO Y PRECISO
    -> IA genera SQL
    -> FirebirdSQLNormalizer (determinista)
    -> SQLCorrector con contexto adicional si falla:
       |-> Si falla: enviar a IA el error + SQL fallido + contexto adicional
       |-> IA corrige el SQL con mas informacion
       |-> Reintentar (hasta 4 veces)
    -> Ejecutar en Firebird
    -> Interpretar resultados
    -> Respuesta
```

### Ventajas del flujo v2

| Aspecto | v1 (actual) | v2 (SIUO) |
|---------|------------|-----------|
| Tokens de contexto | ~3000 (fijo, todo el esquema) | ~500-1500 (solo lo relevante) |
| Velocidad de busqueda | N/A (todo en memoria) | <1ms (indices en memoria) |
| Cobertura de tablas | 8/437 (2%) | 437/437 (100%) |
| Relaciones conocidas | Solo las 8 tablas analizadas | Todas las relaciones |
| Valores reales | No | Si (enumerados, rangos, top-N) |
| Manejo de fallos | Reintento ciego | Reintento con contexto adicional |
| Escalabilidad | No escala (limite de tokens) | Escala a cualquier BD |

---

## 6. Modo AI_LOCAL_ONLY — Solo Qwen3 LAN

### Que es

Cuando esta activo, el sistema **solo usa la IA local Qwen3 VL 30B** (servidor en la red LAN JDDC).
**No sale ninguna peticion a internet**.

> MODO DE PRODUCCION (04/03/2026): `ai_local_only=true` — Solo Qwen3 VL 30B LAN.
> Sin salida a internet. El fallback multi-modelo esta deshabilitado (pero no eliminado).

### Como activar/desactivar

**Archivo de configuracion:**
```
bots/interjddcia/backend/modules/chat/config.json
```

```json
{
    "max_sql_retries": 4,
    "enable_auto_correction": true,
    "log_sql_errors": true,
    "ai_local_only": true
}
```

| Valor | Comportamiento | Resiliencia |
|-------|---------------|-------------|
| `"ai_local_only": true` | Solo Qwen3 LAN — sin internet, sin fallback | Baja — si la IA local falla, error total |
| `"ai_local_only": false` | Fallback completo — Qwen3 -> Groq -> Gemma -> ... | Alta — 189 modelos de respaldo |

> El cambio surte efecto inmediatamente — no hace falta reiniciar el servidor.

### Modelos locales reconocidos

```python
LOCAL_MODEL_IDS = {"jddcia-qwen3-30b", "jddcia-qwen3-30b-ip"}
```

- `jddcia-qwen3-30b-ip` -> `http://192.168.0.36/api/vlm/v1` (score 95 — se intenta primero)
- `jddcia-qwen3-30b` -> `http://jddcia.local/api/vlm/v1` (score 50 — fallback mDNS)

> AVISO: `jddcia.local` no resuelve en Windows (mDNS/Bonjour no esta activo por defecto).
> Usar siempre la IP directa `192.168.0.36`.

### Cambiar el modo via API

```cmd
REM Activar modo local (sin internet)
curl -X POST http://localhost:8001/api/chat/config ^
  -H "Content-Type: application/json" ^
  -d "{\"max_sql_retries\": 4, \"ai_local_only\": true}"

REM Activar modo fallback completo (con internet) — RECOMENDADO
curl -X POST http://localhost:8001/api/chat/config ^
  -H "Content-Type: application/json" ^
  -d "{\"max_sql_retries\": 4, \"ai_local_only\": false}"
```

---

## 7. Resiliencia del sistema

### Analisis completo (04/03/2026)

#### Lo que SI es resiliente

| Componente | Resiliencia | Detalle |
|-----------|-------------|---------|
| Fallback IA | Excelente | 189 modelos — si uno falla, prueba el siguiente |
| BD Firebird | Buena | Conecta directamente por IP, no depende de la IA |
| Reintentos SQL | Buena | 4 reintentos con correccion automatica de SQL |
| API keys | Excelente | 18 proveedores cargados |
| Config en caliente | Excelente | `ai_local_only` se lee en cada peticion |
| FirebirdSQLNormalizer | Excelente | Correccion determinista sin IA |

#### Puntos debiles identificados

| Problema | Impacto | Solucion |
|---------|---------|---------|
| `ai_local_only=true` + IA local caida | Error total | Usar `ai_local_only=false` |
| IP del servidor IA hardcodeada | Medio | Si cambia la IP, editar `jddcia_models.json` |
| `jddcia.local` no resuelve en Windows | Medio | Ya corregido: IP directa tiene score 95 |
| vLLM single-request | Medio | Si el modelo esta ocupado, timeout en 20s |
| Solo 8/437 tablas con metadatos | Alto | SIUO resuelve esto |
| Contexto monolitico | Alto | SIUO con ContextRetriever resuelve esto |

---

## 8. Diagnosticos frecuentes

### Diagnostico: IA local no responde

**Sintoma:**
```
Error con Qwen3 VL 30B (JDDC LAN — IP directa): All connection attempts failed
```

**Causas y soluciones:**

| Causa | Diagnostico | Solucion |
|-------|------------|---------|
| Modelo ocupado (vLLM single-request) | curl a /models OK pero /chat/completions timeout | Esperar o usar ai_local_only=false |
| Servidor apagado | curl a /models tambien falla | Encender el servidor IA |
| IP cambiada | curl a la IP falla | Actualizar jddcia_models.json |
| Puerto bloqueado | curl falla con "connection refused" | Verificar firewall del servidor |

**Verificar estado:**
```cmd
curl -s --max-time 5 http://192.168.0.36/api/vlm/v1/models ^
  -H "Authorization: Basic YWRtaW46YWlzdGFjazIwMjY="
```

**Solucion inmediata:**
```cmd
curl -X POST http://localhost:8001/api/chat/config ^
  -H "Content-Type: application/json" ^
  -d "{\"max_sql_retries\": 4, \"ai_local_only\": false}"
```

### Diagnostico: Error Firebird LIMIT vs FIRST

**Sintoma:**
```
Error despues de 3 intentos: _op_response:op_code = 1
Consulta: SELECT FIRST 100 NOMBRE FROM ARTICULO LIMIT 1
```

**Causa:** La IA genera LIMIT y el normalizador anade FIRST, resultando en ambos.

**Solucion aplicada:** FirebirdSQLNormalizer elimina LIMIT/ROWS ANTES de que se anade FIRST.

### Diagnostico: Error POSITION en indexacion masiva SIUO

**Sintoma:**
```
[ERROR] ACC_ACC: Dynamic SQL Error SQL error code = -104 Token unknown - line 24, column 37 POSITION
[ERROR] ACC_EXTRANET: Dynamic SQL Error SQL error code = -104 Token unknown - line 24, column 37 POSITION
... (todas las tablas fallan con el mismo error)
```

**Causa:** `POSITION` es una **palabra reservada en Firebird 2.5** y no puede usarse como alias
de columna sin comillas. La query `QUERY_TABLE_COLUMNS_TYPED` en `firebird_metadata_queries.py`
tenia `rf.RDB$FIELD_POSITION AS POSITION` — Firebird lo rechaza.

**Solucion aplicada (06/03/2026):**
- Cambiado `AS POSITION` → `AS FIELD_POS` en `firebird_metadata_queries.py`
- El codigo Python no usaba el alias (accede por `FIELD_NAME`, `FIELD_TYPE`, etc.)
- Verificado con `test_fix_position.py` — 5/5 OK

**Palabras reservadas de Firebird 2.5 que NO pueden usarse como alias sin comillas:**
`POSITION`, `VALUE`, `TYPE`, `TIME`, `DATE`, `YEAR`, `MONTH`, `DAY`, `HOUR`, `MINUTE`,
`SECOND`, `WEEKDAY`, `YEARDAY`, `INDEX`, `PLAN`, `ORDER`, `BY`, `GROUP`, `WHERE`, `FROM`

**Regla:** En queries de introspeccion Firebird, usar siempre prefijos descriptivos para
los aliases: `FIELD_NAME`, `FIELD_TYPE`, `FIELD_POS`, `FK_NAME`, `PK_FIELD`, etc.

### Diagnostico: Qwen3 VL 30B bajo carga

**Sintoma:** Timeout de 63 segundos en una peticion.

**Causa:** vLLM es single-request — encola peticiones silenciosamente.

**Solucion aplicada:** Timeout reducido a 20s en `jddcia_provider.py`.

### Diagnostico: Bug TOTAL monetario interpretado como COUNT (09/03/2026)

**Sintoma:**
```
Usuario pregunta: "cuanto hemos facturado este mes"
Respuesta incorrecta: "hay 45.678,90 facturas en la base de datos"
Respuesta correcta:   "el total facturado es 45.678,90 euros"
```

**Causa:** `interpret_results_for_voice` en `service.py` tenia una copia duplicada
de la logica que no distinguia entre:
- `COUNT(*)` → resultado entero → "hay N facturas"
- `SUM(TOTAL)` → resultado float con decimales → "el total es X euros"

Ambos casos llegaban como `{n == 1, len(row) == 1}` y se trataban igual.

**Solucion aplicada (09/03/2026):**
1. `chat_voice_interpreter.py` es la **UNICA FUENTE DE VERDAD** para `interpret_results_for_voice`
2. Se añadio `_is_monetary_value(val)` que detecta si el valor es float con decimales
3. `service.py` ahora **delega** a `chat_voice_interpreter.py` — no tiene logica propia
4. La funcion LEGACY en `service.py` se renombro a `_interpret_results_for_voice_LEGACY`
   y nunca se ejecuta (documentada para referencia historica)

**Regla para evitar recurrencia:**
> NUNCA duplicar la logica de interpretacion de voz. `service.py` SIEMPRE delega a
> `chat_voice_interpreter.py`. Si hay que cambiar el comportamiento, cambiar SOLO
> `chat_voice_interpreter.py`.

**Test que lo cubre:**
```
tests/unit/test_voice_and_tts.py::TestInterpretResultsForVoice::test_total_facturado
```

### Diagnostico: Codigo duplicado entre service.py y chat_voice_interpreter.py

**Sintoma:** Un bug corregido en `chat_voice_interpreter.py` no se refleja en produccion
porque `service.py` tiene su propia copia de la misma funcion.

**Causa:** Al crear `chat_voice_interpreter.py` como modulo separado, la funcion original
en `service.py` no se elimino — quedaron dos implementaciones divergentes.

**Solucion aplicada (09/03/2026):**
- `service.py` importa y delega:
  ```python
  from backend.modules.chat.chat_voice_interpreter import (
      interpret_results_for_voice as _interpret_voice_impl,
      clean_for_tts as _clean_tts_impl,
  )
  def interpret_results_for_voice(message, results, sql_query):
      return _interpret_voice_impl(message, results, sql_query)
  ```
- La implementacion LEGACY queda como `_interpret_results_for_voice_LEGACY` (nunca llamada)

**Regla para evitar recurrencia:**
> Cuando se extrae logica a un modulo nuevo, SIEMPRE eliminar o delegar la version antigua.
> Nunca dejar dos implementaciones activas de la misma funcion.

### Diagnostico: Paginacion MetaGlass — umbral y formato diferente al web

**Contexto:** Las gafas Meta Ray-Ban tienen TTS con limite de ~3 items por respuesta.
El sistema web puede mostrar 10-50 resultados en una tabla. Necesitan umbrales distintos.

**Solucion implementada (09/03/2026):**
- `ResponseSummarizer.summarize_for_metaglass()` — umbral configurable (default 5)
- `ResponseSummarizer.handle_metaglass_pagination()` — paginacion por voz
- `_detect_intent_deterministic()` — detecta si/no/todos sin IA
- Respuestas sin Markdown (nunca `**`, `##`, ` ``` `)
- `METAGLASS_PAGINATION_THRESHOLD = 5` (vs `SUMMARY_THRESHOLD = 20` para web)
- `METAGLASS_PAGE_SIZE = 3` (vs `PAGE_SIZE_DEFAULT = 10` para web)

**Regla para evitar recurrencia:**
> Los clientes de voz (MetaGlass) y web tienen requisitos distintos de paginacion.
> Usar siempre `summarize_for_metaglass()` para MetaGlass, nunca `summarize()` de web.
> Verificar con `tests/unit/test_response_summarizer.py::TestMetaGlassPaginacion`.

---

## 9. Como levantar el backend

### Opcion A — Script automatico (recomendado)

```cmd
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
ARRANCAR_DEVIA.bat
```

O simplemente **doble clic** en `ARRANCAR_DEVIA.bat`.

### Opcion B — Manual con uvicorn

```cmd
cd C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
set PYTHONPATH=%CD%
.venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 8001 --log-level info
```

### Verificar que esta corriendo

```cmd
curl http://localhost:8001/health
curl http://localhost:8001/api/chat/config
curl http://localhost:8001/api/metadata-builder/status
```

---

## 10. Comandos de diagnostico rapido

```cmd
REM 1. Ver si DEVIA esta corriendo
curl -s http://localhost:8001/health

REM 2. Ver configuracion actual (incluye ai_local_only)
curl -s http://localhost:8001/api/chat/config

REM 3. Verificar que Qwen3 LAN responde (IP directa — RECOMENDADO)
curl -s --max-time 5 http://192.168.0.36/api/vlm/v1/models ^
  -H "Authorization: Basic YWRtaW46YWlzdGFjazIwMjY="

REM 4. Test completo de consulta a BD real
curl -X POST http://localhost:8001/api/chat/send ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"cuantos articulos hay\"}"

REM 5. Ver estado del Constructor BD (SIUO)
curl -s http://localhost:8001/api/metadata-builder/status

REM 6. Ver tablas con metadatos
curl -s http://localhost:8001/api/metadata-builder/tables

REM 7. Activar modo local (sin internet) — BAJA RESILIENCIA
curl -X POST http://localhost:8001/api/chat/config ^
  -H "Content-Type: application/json" ^
  -d "{\"max_sql_retries\": 4, \"ai_local_only\": true}"

REM 8. Activar modo fallback completo (con internet) — RECOMENDADO
curl -X POST http://localhost:8001/api/chat/config ^
  -H "Content-Type: application/json" ^
  -d "{\"max_sql_retries\": 4, \"ai_local_only\": false}"

REM 9. Ver que proceso usa el puerto 8001
netstat -ano | findstr :8001

REM 10. Ver IP del PC
ipconfig | findstr "192.168"

REM 11. Matar proceso en puerto 8001 (si hay que reiniciar)
for /f "tokens=5" %p in ('netstat -ano ^| findstr ":8001 " ^| findstr "LISTENING"') do taskkill /F /PID %p
```

---

## 11. Archivos clave

```
bots/interjddcia/
|
+-- ARRANCAR_DEVIA.bat                   <- Script maestro de arranque (menu 4 opciones)
+-- PARAR_DEVIA.bat                      <- Script para parar todos los servidores
+-- .env                                 <- API keys, credenciales Firebird
+-- DEVIA.MD                             <- Este documento
|
+-- backend/
    +-- main.py                          <- FastAPI app, endpoint /health
    |
    +-- modules/
    |   +-- chat/
    |   |   +-- config.json              <- CONFIGURACION RUNTIME (ai_local_only aqui)
    |   |   +-- router.py                <- Endpoints /send, /config, /history
    |   |   +-- service.py               <- Logica principal, SQL, TTS cleanup
    |   |   +-- sql_corrector.py         <- clean_firebird_sql, LIMIT->FIRST
    |   |   +-- firebird_sql_normalizer.py <- Normalizacion SQL Firebird
    |   |   +-- model_fallback_orchestrator.py <- Fallback IA, filtro LOCAL_ONLY
    |   |
    |   +-- db_explorer/                 <- Constructor BD (SIUO)
    |       +-- metadata_builder_service.py <- Analisis de tablas con Qwen3
    |       +-- metadata_builder_router.py  <- Endpoints /api/metadata-builder/*
    |       +-- constants.py               <- Timeouts, limites, privacidad
    |       +-- [NUEVO] deep_indexer_service.py  <- Indexacion profunda SIUO
    |       +-- [NUEVO] context_retriever.py     <- Busqueda de contexto optimo
    |
    +-- drivers/
    |   +-- ai/
    |   |   +-- jddcia_provider.py       <- Cliente HTTP para Qwen3 LAN (timeout 20s)
    |   +-- db/
    |       +-- firebird_metadata_queries.py <- SQL de introspeccion Firebird
    |
    +-- core/
        +-- config/
            +-- settings.py              <- Variables de entorno (.env)
            +-- metadata_manager.py      <- Lectura/escritura db_metadata_optimized.json
            +-- database_metadata.py     <- get_semantic_schema() para el chat
            +-- db_metadata_optimized.json <- Metadatos actuales (8 tablas)
            +-- [NUEVO] table_index.json    <- Indice compacto de todas las tablas
            +-- [NUEVO] concept_index.json  <- Mapa concepto -> tablas
            +-- [NUEVO] db_graph.json       <- Grafo de relaciones
            +-- [NUEVO] value_index.json    <- Valores reales de columnas clave
            +-- [NUEVO] siuo_progress.json  <- Estado del proceso de indexacion
            +-- models/
                +-- jddcia_models.json   <- IPs y scores de modelos locales
|
+-- frontend/
    +-- index.html                       <- UI web (9 pestanas: Dashboard, Articulos, Prompts,
    |                                       Modelos, BD Config, Chat, Outlook, Anonimizar,
    |                                       Constructor BD, Indices SIUO)
    +-- assets/
        +-- css/
        |   +-- style.css                <- Estilos generales
        |   +-- metadata_builder.css     <- Estilos del Constructor BD
        |   +-- siuo.css                 <- [NUEVO] Estilos del modulo SIUO
        +-- js/
            +-- core/
            |   +-- app.js               <- Navegacion y modulos (lazy-init SIUO)
            +-- modules/
                +-- metadata_builder.js  <- UI del Constructor BD
                +-- siuo.js              <- [NUEVO] UI del SIUO (SSE, stats, test retriever)
                +-- chat.js              <- UI del Chat IA
                +-- [otros modulos]
```

### Datos de conexion

| Dato | Valor |
|------|-------|
| IP del PC servidor | 192.168.0.58 (Wi-Fi) |
| Puerto DEVIA | 8001 |
| URL DEVIA (local) | http://localhost:8001 |
| URL DEVIA (red) | http://192.168.0.58:8001 |
| Servidor Qwen3 (IP) | http://192.168.0.36 <- usar esta |
| Servidor Qwen3 (mDNS) | http://jddcia.local <- falla en Windows |
| Modelo Qwen3 | unified-main (Qwen3 VL 30B) |
| Timeout Qwen3 | 20s |
| BD Firebird | 192.168.0.254:3050 |
| Endpoint chat | POST /api/chat/send |
| Endpoint health | GET /health |
| Endpoint config | GET/POST /api/chat/config |
| Endpoint Constructor BD | GET /api/metadata-builder/status |
| Modo produccion | ai_local_only: true (solo Qwen3 LAN) |

### Estado actual del sistema (06/03/2026)

| Componente | Estado | Notas |
|-----------|--------|-------|
| Backend DEVIA | Corriendo (puerto 8001) | v3.0.0 |
| BD Firebird | Conectada | 11.866 articulos, 437 tablas |
| IA local (192.168.0.36) | Disponible | Qwen3 VL 30B |
| IA local (jddcia.local) | No resuelve en Windows | Usar IP directa |
| Fallback Groq/Gemma | Disponible | Activar con ai_local_only=false |
| Modo activo | ai_local_only: true | Solo Qwen3 LAN |
| Constructor BD (UI) | Funcionando | http://localhost:8001 -> Constructor BD |
| Tablas con metadatos | 8/437 (2%) | Pendiente ejecutar indexacion masiva con Qwen3 |
| SIUO Fase 1 (DeepIndexerService) | ✅ COMPLETADA | deep_indexer_service.py |
| SIUO Fase 2 (ContextRetriever) | ✅ COMPLETADA | context_retriever.py |
| SIUO Fase 3 (ChatService integrado) | ✅ COMPLETADA | service.py usa ContextRetriever |
| SIUO Fase 4 (Frontend UI) | ✅ COMPLETADA | siuo.js + siuo.css + pestana "Indices SIUO" |
| SIUO Fase 5 (Tests y validacion) | ✅ COMPLETADA | 26/26 tests OK (06/03/2026) |
| SIUO Router | ✅ ACTIVO | /api/siuo/* registrado en main.py |
| SIUO Indexacion masiva | ⏳ PENDIENTE | 0/437 tablas — ejecutar desde UI "Indices SIUO" |
| ContextRetriever modo actual | fallback v1 | Activa SIUO completo tras indexacion masiva |
| Auditor de red (NetworkAuditLogger) | ✅ ACTIVO | Instalado en main.py lifespan — log: logs/network_audit.log |
| Tests de privacidad (test_privacidad_datos.py) | ✅ 12/12 OK | Sistemas 1 y 5 verificados (06/03/2026) |

### PROXIMO PASO: Ejecutar indexacion masiva

El sistema SIUO esta 100% implementado y testado. Para activarlo completamente:

1. Asegurarse de que Qwen3 LAN esta disponible: `curl http://192.168.0.36/api/vlm/v1/models`
2. Abrir http://localhost:8001 -> pestana "Indices SIUO"
3. Pulsar "Iniciar Analisis Completo" (batch=5, reanudar=true)
4. Esperar ~2-4 horas para las 437 tablas (depende de la velocidad de Qwen3)
5. Tras completar: el ContextRetriever usara SIUO en lugar del fallback v1
6. Verificar con: `curl http://localhost:8001/api/siuo/stats`

---

## PRINCIPIOS DE DESARROLLO DEL PROYECTO

> Estos principios son OBLIGATORIOS en todo el codigo nuevo y en refactorizaciones.
> La IA que desarrolla este proyecto debe aplicarlos siempre, sin excepcion.

### 1. Arquitectura orientada a IA

- **Contexto minimo y preciso**: nunca enviar mas tokens de los necesarios a la IA
- **Fallback gracioso**: si la IA falla, el sistema sigue funcionando (degradado, no roto)
- **Autoaprendizaje**: registrar que funciona y que no para mejorar el sistema
- **Trazabilidad total**: cada llamada a la IA queda registrada con tokens, modelo, latencia
- **Privacidad por diseno**: datos sensibles nunca salen a internet (PrivacyConfig)
- **Resiliencia multi-modelo**: 189 modelos de fallback, nunca un punto unico de fallo

### 2. Calidad de codigo

- **Ficheros <= 500 lineas**: si un fichero crece mas, refactorizar en modulos
- **Una responsabilidad por clase/modulo** (SRP — Single Responsibility Principle)
- **Constantes en ficheros dedicados**: `constants.py`, `settings.py`, nunca literales en el codigo
- **Tipos en todas las funciones**: `def foo(x: str) -> Dict[str, Any]:`
- **Docstrings en todas las clases y metodos publicos**
- **Sin imports circulares**: dependencias siempre en una sola direccion
- **Sin magic numbers**: todo valor numerico tiene nombre y esta en constants.py

### 3. Patrones de diseno aplicados

| Patron | Donde se usa |
|--------|-------------|
| Singleton | DeepIndexerService, ContextRetriever, MetadataManager |
| Factory | DBFactory, AIFactory — abstraccion de drivers |
| Strategy | ModelFallbackOrchestrator — estrategia de fallback |
| Observer | SSE (Server-Sent Events) — progreso en tiempo real |
| Repository | MetadataManager — acceso a datos centralizado |
| Facade | ChatService — fachada que orquesta todos los subsistemas |
| Template Method | SQLCorrector — flujo fijo con pasos variables |

### 4. Seguridad y ciberseguridad

- **Zero-trust para datos de BD**: ningun dato de Firebird sale a internet
- **Validacion de entrada**: Pydantic en todos los endpoints (min_length, max_length, ge, le)
- **Sin SQL injection**: parametros siempre como tuplas, nunca f-strings en SQL
- **Columnas sensibles**: PrivacyConfig.SENSITIVE_COLUMNS excluidas de muestras a IA
- **API keys en .env**: nunca en el codigo, nunca en logs
- **Logs sin datos sensibles**: los logs muestran estructura, no valores de columnas sensibles
- **CORS configurado**: solo origenes conocidos en produccion
- **Timeouts en todas las llamadas HTTP**: nunca esperar indefinidamente

### 5. Modularidad y estructura de carpetas

```
backend/
  core/           <- Abstracciones, factories, configuracion global
    abstract/     <- Interfaces (ABCs): database.py, ai.py
    config/       <- settings.py, constants, JSON de configuracion
    factory/      <- DBFactory, AIFactory
    utils/        <- constants.py, helpers sin dependencias
  modules/        <- Modulos de negocio (cada uno independiente)
    chat/         <- ChatService, router, SQL corrector, normalizer
    db_explorer/  <- MetadataBuilder, SIUO, ContextRetriever
    images/       <- Generacion y analisis de imagenes
    [otros]       <- Cada modulo tiene su router.py, service.py, constants.py
  drivers/        <- Implementaciones concretas
    ai/           <- JDDCIAProvider, GroqProvider, etc.
    db/           <- FirebirdDriver, queries SQL
```

**Regla**: un modulo no importa de otro modulo directamente.
Si necesita algo de otro modulo, lo hace a traves de `core/`.

### 6. Escalabilidad y rendimiento

- **Indices en memoria**: table_index, concept_index, db_graph cargados al arrancar
- **Busqueda O(1)**: concept_index es un dict, no una lista que hay que recorrer
- **Batches configurables**: batch_size en DeepIndexerService (1-20 tablas por batch)
- **SSE para procesos largos**: nunca bloquear el cliente con un proceso de 30 minutos
- **Progreso guardado**: siuo_progress.json permite reanudar si se interrumpe
- **Singleton para servicios pesados**: no crear instancias nuevas en cada peticion
- **Timeout en todas las llamadas**: Qwen3 20s, Firebird 3 reintentos con backoff

### 7. Robustez y deteccion de errores

- **Try/except en todo acceso externo**: BD, IA, ficheros, red
- **Errores tipados**: nunca `except Exception: pass` sin log
- **Fallback en cascada**: SIUO -> db_metadata_optimized.json -> esquema minimo
- **Reintentos con backoff**: SQL hasta 4 intentos, BD hasta 3 intentos
- **Estado de error persistido**: siuo_progress.json guarda tablas fallidas
- **Logs estructurados**: `[MODULO][PASO] EMISOR -> RECEPTOR: mensaje`
- **Health check**: GET /health siempre disponible, incluso si la BD falla

### 8. Trazabilidad y medicion

- **Logs en cada paso critico**: conexion BD, llamada IA, SQL generado, resultado
- **Metadatos de contexto**: cada respuesta del chat incluye tablas usadas, tokens, fuente
- **Query log**: siuo_query_log.json registra cada pregunta con keywords y tablas usadas
- **Feedback loop**: endpoint POST /api/siuo/learning/feedback para marcar SQL correcto/incorrecto
- **Estadisticas de indices**: GET /api/siuo/stats muestra estado del SIUO en tiempo real
- **Progreso SSE**: el frontend recibe eventos en tiempo real durante la indexacion

### 9. Autoaprendizaje y mejora continua

El sistema aprende de su propio uso:

```
Pregunta del usuario
    |
    v
ContextRetriever._log_query()
    -> Registra keywords encontrados y desconocidos
    -> Acumula frecuencia de keywords sin mapear
    |
    v
GET /api/siuo/learning/suggestions
    -> Devuelve keywords frecuentes sin mapear
    -> Sugiere nuevas entradas para concept_index
    -> Muestra tablas mas usadas (candidatas a analisis prioritario)
    |
    v
POST /api/siuo/learning/feedback
    -> Usuario marca si el SQL fue correcto o no
    -> Se guarda en siuo_query_log.json
    -> Permite detectar patrones de error sistematicos
    |
    v
Mejora manual o automatica del concept_index
    -> Anadir nuevos keywords
    -> Corregir filtros SQL (ej: TIPO=13 para facturas)
    -> POST /api/siuo/reload para recargar sin reiniciar
```

**Ciclo de mejora continua**:
1. El sistema detecta keywords no mapeados frecuentes
2. El desarrollador (o la IA) los anade al concept_index
3. POST /api/siuo/reload recarga los indices en memoria
4. Las siguientes preguntas con esos keywords funcionan mejor
5. El feedback confirma la mejora

### 10. Usabilidad y experiencia de desarrollo

- **DEVIA.MD en cada modulo**: documentacion local de responsabilidad, flujo y dependencias
- **Comandos de diagnostico**: seccion 10 del DEVIA principal con curl commands listos
- **Script de arranque**: ARRANCAR_DEVIA.bat con menu de 4 opciones
- **Endpoint de test**: POST /api/siuo/context/test para probar el retriever sin chat
- **Swagger UI**: http://localhost:8001/docs con todos los endpoints documentados
- **Errores en JSON**: nunca HTML de error, siempre `{"detail": "mensaje claro"}`
- **Mensajes de progreso claros**: `[150/437] DOCCAB — 85.000 registros`

---

## PLAN DE IMPLEMENTACION DEL SIUO

### Fase 1 — Backend: DeepIndexerService (1-2 dias)

Crear `backend/modules/db_explorer/deep_indexer_service.py`:

- Metodo `analyze_table_deep(table_name)`:
  - Paso 1: estructura (columnas, PKs, FKs) — ya existe en MetadataBuilderService
  - Paso 2: valores de columnas clave (enumerados, top-N, rangos)
  - Paso 3: relaciones implicitas (por nombre de columna: CODART, CODCLI, etc.)
  - Paso 4: enviar a Qwen3 en chunks <= 2000 tokens
  - Paso 5: guardar en todos los indices

- Metodo `analyze_all_tables_batch(batch_size=10)`:
  - Procesa tablas en batches
  - Guarda progreso en siuo_progress.json
  - Continua desde donde se quedo si se interrumpe
  - Reporta progreso via SSE (Server-Sent Events) al frontend

- Metodo `build_graph()`:
  - Construye db_graph.json con todas las relaciones
  - FKs explicitas de Firebird
  - FKs implicitas por nombre de columna

- Metodo `build_concept_index()`:
  - Construye concept_index.json
  - Combina reglas manuales + keywords generados por Qwen3

### Fase 2 — Backend: ContextRetriever (1 dia)

Crear `backend/modules/db_explorer/context_retriever.py`:

- Carga table_index.json, concept_index.json, db_graph.json en memoria al arrancar
- Metodo `get_context(question, max_tokens=2000)`:
  - Extrae keywords de la pregunta
  - Busca en concept_index
  - Expande con db_graph (BFS hasta profundidad 2)
  - Carga detalles de table_index
  - Calcula tokens y recorta si necesario
  - Devuelve contexto optimo

### Fase 3 — Integracion en ChatService (0.5 dias)

Modificar `backend/modules/chat/service.py`:

- Reemplazar `get_semantic_schema()` por `ContextRetriever.get_context(message)`
- Pasar contexto adicional al SQLCorrector cuando falla

### Fase 4 — Frontend: UI de indexacion masiva (1 dia)

Anadir en el Constructor BD:

- Boton "Analizar BD completa con Qwen3"
- Barra de progreso en tiempo real (SSE)
- Log de tablas procesadas / fallidas
- Boton "Pausar" / "Reanudar"
- Vista del grafo de relaciones (opcional)

### Fase 5 — Tests y validacion (0.5 dias)

- Test: "dime los articulos con mas compras" -> SQL correcto
- Test: "facturas del mes pasado" -> SQL correcto con TIPO=13
- Test: "clientes de Madrid" -> SQL correcto
- Test: pregunta con tabla desconocida -> manejo gracioso

---

## TESTS AUTOMATIZADOS — LOS 3 SISTEMAS IA

> **Estado (04/03/2026): 26/26 tests pasados ✓**

### Ejecutar los tests

```cmd
REM Desde la raiz del proyecto (bots/interjddcia/)
set PYTHONUTF8=1
set PYTHONPATH=C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
.venv\Scripts\python.exe -X utf8 test_sistemas_ia.py
```

O con el script de arranque (opcion 4 — diagnostico):
```cmd
ARRANCAR_DEVIA.bat   <- opcion 4
```

### Opciones del script de tests

```cmd
REM Todos los tests (modo compacto — recomendado)
python test_sistemas_ia.py

REM Modo verbose (unittest estandar)
python test_sistemas_ia.py -v

REM Solo un sistema
python test_sistemas_ia.py --solo memoria
python test_sistemas_ia.py --solo relaciones
python test_sistemas_ia.py --solo calidad
python test_sistemas_ia.py --solo api        <- requiere servidor corriendo
```

### Sistemas testados

#### SISTEMA 1: MEMORIA PERMANENTE (6 tests)

| Test | Que verifica |
|------|-------------|
| `test_guardar_y_recuperar_interaccion` | SQLite guarda y recupera interacciones correctamente |
| `test_persistencia_entre_sesiones` | Los datos persisten aunque se reinicie el servicio |
| `test_filtrado_por_modulo` | Se puede filtrar historial por CHAT, OUTLOOK, etc. |
| `test_metadata_json_persistido` | Los metadatos JSON se serializan/deserializan bien |
| `test_query_log_contextretriever` | El ContextRetriever registra consultas en siuo_query_log.json |
| `test_feedback_loop` | El feedback SQL correcto/incorrecto se persiste |

#### SISTEMA 2: RELACIONES MULTI-TABLA (8 tests)

| Test | Que verifica |
|------|-------------|
| `test_pregunta_simple_una_tabla` | "cuantos articulos hay" -> encuentra ARTICULO |
| `test_pregunta_compleja_join_tres_tablas` | "articulos con mas ventas" -> ARTICULO + DOCLIN + DOCCAB |
| `test_filtro_sql_en_contexto` | "facturas" -> contexto incluye WHERE TIPO=13 |
| `test_expansion_bfs_sin_bucles` | BFS no entra en bucles con grafos ciclicos |
| `test_ranking_tablas_directas_primero` | Tablas directas tienen mayor score que expandidas |
| `test_pregunta_proveedor_compras` | "pedidos a proveedores" -> PROVEED + DOCCAB (TIPO=12) |
| `test_control_de_tokens` | El contexto nunca excede el limite de tokens |
| `test_fallback_sin_indices` | Sin indices SIUO, usa db_metadata_optimized.json |

#### SISTEMA 3: CALIDAD DE DATOS + IA (7 tests)

| Test | Que verifica |
|------|-------------|
| `test_data_quality_service_instancia` | DataQualityService se instancia sin errores |
| `test_analyze_impact_estructura` | analyze_impact devuelve estructura correcta |
| `test_sql_calidad_datos_valido_firebird` | SQL de duplicados no usa LIMIT (invalido en Firebird) |
| `test_interpretacion_ia_datos_incorrectos` | interpret_results_for_voice interpreta duplicados |
| `test_clean_for_tts_elimina_markdown` | clean_for_tts elimina ** ## ` para las gafas Meta |
| `test_privacidad_columnas_sensibles` | PASSWORD/DNI no aparecen en el contexto enviado a la IA |
| `test_sugerencias_autoaprendizaje` | get_learning_suggestions devuelve keywords frecuentes |

#### INTEGRACION API (5 tests — requieren servidor en :8001)

| Test | Que verifica |
|------|-------------|
| `test_health_endpoint` | GET /health devuelve status ok |
| `test_siuo_stats_endpoint` | GET /api/siuo/stats devuelve estadisticas |
| `test_siuo_context_test_endpoint` | POST /api/siuo/context/test devuelve contexto |
| `test_siuo_learning_suggestions` | GET /api/siuo/learning/suggestions funciona |
| `test_chat_pregunta_simple` | POST /api/chat/send responde a pregunta real con BD |

### Mejora aplicada durante los tests

Durante la ejecucion de los tests se detecto y corrigio un bug en `context_retriever.py`:

**Bug:** `_extract_keywords()` no normalizaba plurales ni acentos.
- "articulos" no encontraba "articulo" en el concept_index
- "facturas" no encontraba "factura"
- Resultado: 0 tablas encontradas para preguntas en plural

**Correccion aplicada:** Se añadio el metodo `_normalize_word()` que:
1. Elimina acentos (unicodedata NFKD)
2. Intenta quitar plural en `-es` (si la raiz esta en el indice)
3. Intenta quitar plural en `-s` (si la raiz esta en el indice)

```python
# Antes (fallaba con plurales)
if w in self._concept_index:
    found.append(w)

# Despues (funciona con plurales y acentos)
normalized = self._normalize_word(w)  # "articulos" -> "articulo"
if normalized in self._concept_index:
    found.append(normalized)
```

**Impacto:** Todas las preguntas en plural ahora funcionan correctamente.
