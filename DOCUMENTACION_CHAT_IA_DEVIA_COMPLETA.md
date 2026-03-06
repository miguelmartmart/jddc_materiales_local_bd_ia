# 📖 DOCUMENTACIÓN COMPLETA — CHAT IA DEVIA
## Sistema de Consulta de Base de Datos en Lenguaje Natural (Text-to-SQL)

> **Proyecto:** DEVIA — Sistema Genérico de Gestión & Inteligencia Artificial  
> **Ubicación:** `bots/interjddcia/`  
> **Base de datos:** Firebird 2.5 (base de datos real de la empresa JDDC)  
> **Fecha doc.:** 27/02/2026

---

## 📋 ÍNDICE

1. [¿Qué es el Chat IA?](#1-qué-es-el-chat-ia)
2. [Arquitectura General del Sistema](#2-arquitectura-general-del-sistema)
3. [Mapa de Rutas del Proyecto](#3-mapa-de-rutas-del-proyecto)
4. [Rutas de la API (Endpoints)](#4-rutas-de-la-api-endpoints)
5. [Flujo Completo de una Consulta](#5-flujo-completo-de-una-consulta)
6. [Componentes Clave](#6-componentes-clave)
7. [Sistema de Metadatos de la BD](#7-sistema-de-metadatos-de-la-bd)
8. [Modelos IA Soportados](#8-modelos-ia-soportados)
9. [Sistema de Fallback y Robustez](#9-sistema-de-fallback-y-robustez)
10. [Corrección Automática de SQL](#10-corrección-automática-de-sql)
11. [Historial de Conversaciones](#11-historial-de-conversaciones)
12. [Configuración (.env)](#12-configuración-env)
13. [Cómo Ejecutar el Sistema](#13-cómo-ejecutar-el-sistema)
14. [Tablas de la BD Real Configuradas](#14-tablas-de-la-bd-real-configuradas)
15. [Seguridad y Privacidad](#15-seguridad-y-privacidad)
16. [Comandos de Depuración](#16-comandos-de-depuración)

---

## 1. ¿Qué es el Chat IA?

El **Chat IA de DEVIA** es un módulo que permite a los usuarios de la empresa **hacer preguntas en lenguaje natural** sobre los datos reales de la base de datos Firebird de la empresa (JDDC), y recibir respuestas interpretadas en español.

### ¿Cómo funciona en términos simples?

```
Usuario escribe:  "¿Cuántas facturas hemos emitido este mes?"
        ↓
Sistema traduce:  SELECT COUNT(*) FROM DOCCAB WHERE TIPO=13 
                  AND EXTRACT(MONTH FROM FECHA) = EXTRACT(MONTH FROM CURRENT_DATE)
                  AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)
        ↓
Ejecuta en BD:    Firebird 2.5 → devuelve: [{COUNT: 47}]
        ↓
IA interpreta:    "Este mes se han emitido 47 facturas."
        ↓
Usuario recibe:   Respuesta en lenguaje natural con los datos reales
```

### Capacidades del Chat IA

| Capacidad | Descripción |
|-----------|-------------|
| 🗣️ **Text-to-SQL** | Convierte preguntas en español a SQL Firebird 2.5 |
| 🔄 **Fallback multi-modelo** | Si un modelo IA falla, prueba automáticamente el siguiente |
| 🛠️ **Auto-corrección SQL** | Detecta y corrige errores SQL automáticamente |
| 📸 **Análisis de imágenes** | Puede analizar imágenes adjuntas al chat |
| 🎨 **Generación de imágenes** | Puede generar imágenes con IA si se solicita |
| 📜 **Historial persistente** | Guarda todas las conversaciones en SQLite |
| 🔒 **Privacidad** | Pide confirmación antes de enviar datos a la IA |
| 🌐 **Contexto conversacional** | Recuerda mensajes anteriores de la sesión |

---

## 2. Arquitectura General del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENTE WEB (SPA)                            │
│              http://localhost:8001                               │
│         frontend/index.html + frontend/assets/js/               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP POST /api/chat/send
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND (backend/main.py)                  │
│                    Puerto: 8001                                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              MÓDULO CHAT (/api/chat)                     │   │
│  │                                                          │   │
│  │  router.py ──► service.py ──► ModelFallbackOrchestrator │   │
│  │                    │                                     │   │
│  │                    ├──► SQLCorrector                     │   │
│  │                    ├──► ChatHistoryService (SQLite)      │   │
│  │                    └──► ImageService                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                      │
│         ┌─────────────────┼─────────────────┐                  │
│         ▼                 ▼                 ▼                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│  │  AI Factory │  │  DB Factory │  │  MetadataManager    │    │
│  │             │  │             │  │  (db_metadata_       │    │
│  │  Gemini     │  │  Firebird   │  │   optimized.json)   │    │
│  │  Groq       │  │  Driver     │  └─────────────────────┘    │
│  │  OpenAI     │  │             │                              │
│  │  OpenRouter │  └──────┬──────┘                             │
│  └─────────────┘         │                                     │
└─────────────────────────────────────────────────────────────────┘
                           │ firebirdsql
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           BASE DE DATOS FIREBIRD 2.5 (REAL EMPRESA)             │
│                  localhost:3050                                  │
│         Tablas: DOCCAB, ARTICULO, CLIENTE, PROVEED...           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Mapa de Rutas del Proyecto

```
bots/interjddcia/                          ← RAÍZ DEL PROYECTO DEVIA
│
├── 📄 DEVIA.MD                            ← Documentación técnica principal
├── 📄 README.md                           ← Guía de inicio rápido
├── 📄 .env                                ← 🔐 Credenciales reales (NO subir a git)
├── 📄 .env.example                        ← Plantilla de configuración
├── 📄 start_system.bat                    ← ▶️ SCRIPT DE INICIO (Windows)
├── 📄 pytest.ini                          ← Configuración de tests
├── 📄 conftest.py                         ← Setup de tests
│
├── backend/                               ← TODO EL CÓDIGO PYTHON
│   │
│   ├── 📄 main.py                         ← 🚀 PUNTO DE ENTRADA FastAPI
│   │                                         (registra todos los routers)
│   │
│   ├── core/                              ← NÚCLEO DEL SISTEMA
│   │   ├── abstract/
│   │   │   ├── ai.py                      ← Interface AIProvider (ABC)
│   │   │   └── database.py                ← Interface DatabaseDriver (ABC)
│   │   │
│   │   ├── config/
│   │   │   ├── settings.py                ← ⚙️ Variables de entorno (.env)
│   │   │   ├── database_metadata.py       ← Wrapper: get_semantic_schema()
│   │   │   ├── metadata_manager.py        ← 🧠 Gestor de metadatos BD
│   │   │   ├── model_manager.py           ← Gestor de modelos IA
│   │   │   ├── ai_presets.py              ← Presets de modelos
│   │   │   ├── ai_providers_config.json   ← 📋 Config de proveedores IA
│   │   │   ├── db_metadata_optimized.json ← 📊 ESQUEMA BD REAL (editable)
│   │   │   └── prompts.json               ← Prompts configurables
│   │   │
│   │   ├── factory/
│   │   │   ├── ai_factory.py              ← Factory: crea proveedores IA
│   │   │   └── db_factory.py              ← Factory: crea drivers BD
│   │   │
│   │   └── utils/
│   │       ├── constants.py               ← 🔧 TODAS LAS CONSTANTES
│   │       ├── encoding_utils.py          ← Manejo de encoding (latin1)
│   │       └── env_manager.py             ← Gestor de variables de entorno
│   │
│   ├── drivers/                           ← IMPLEMENTACIONES CONCRETAS
│   │   ├── ai/
│   │   │   ├── gemini_provider.py         ← Driver Google Gemini
│   │   │   └── openai_compatible_provider.py ← Driver OpenAI/Groq/OpenRouter
│   │   │
│   │   └── db/
│   │       ├── firebird_driver.py         ← 🔥 Driver Firebird 2.5
│   │       └── firebird_queries.py        ← Queries de sistema Firebird
│   │
│   ├── modules/                           ← MÓDULOS DE NEGOCIO
│   │   │
│   │   ├── chat/                          ← 💬 MÓDULO PRINCIPAL CHAT IA
│   │   │   ├── router.py                  ← Endpoints: /api/chat/*
│   │   │   ├── service.py                 ← 🧠 Lógica principal Text-to-SQL
│   │   │   ├── sql_corrector.py           ← Auto-corrección SQL
│   │   │   ├── model_fallback_orchestrator.py ← Fallback multi-modelo
│   │   │   ├── chat_history_service.py    ← Historial SQLite
│   │   │   ├── config.json                ← Config del módulo chat
│   │   │   ├── DEVIA.MD                   ← Doc del módulo
│   │   │   └── DEVIA_ROBUSTNESS.md        ← Doc de robustez/fallback
│   │   │
│   │   ├── database/                      ← Módulo gestión metadatos BD
│   │   │   ├── router.py                  ← Endpoints: /api/database/*
│   │   │   ├── service.py                 ← Análisis IA de tablas
│   │   │   └── DEVIA.MD                   ← Doc del módulo
│   │   │
│   │   ├── articles/                      ← CRUD artículos
│   │   ├── models/                        ← Gestión modelos IA (UI)
│   │   ├── prompts/                       ← Gestión prompts (UI)
│   │   ├── db_explorer/                   ← Explorador de BD
│   │   ├── data_quality/                  ← Calidad de datos
│   │   ├── anonymizer/                    ← Anonimizador de datos
│   │   ├── images/                        ← Generación/análisis imágenes
│   │   ├── employees/                     ← API empleados (tabla RECURSO)
│   │   ├── resources/                     ← Recursos generales
│   │   ├── outlook/                       ← Integración correo Outlook
│   │   ├── email_simulation/              ← Simulación respuestas email
│   │   └── interaction_history/           ← Historial interacciones IA
│   │
│   ├── data/
│   │   └── chat_history.db                ← 💾 SQLite historial de chats
│   │
│   ├── scripts/                           ← Scripts de utilidad
│   │   ├── extract_db_metadata.py         ← Extrae esquema de Firebird
│   │   ├── extract_metadata_v2.py         ← Versión mejorada
│   │   ├── diagnose_schema.py             ← Diagnóstico conexión BD
│   │   ├── test_db_connection.py          ← Test de conexión
│   │   └── check_tables.py                ← Verificar tablas
│   │
│   └── tests/                             ← Tests automatizados
│       └── modules/
│           └── employees/
│               ├── test_service.py        ← 25 tests
│               └── test_router.py         ← 13 tests
│
├── frontend/                              ← INTERFAZ WEB (SPA)
│   ├── index.html                         ← Página principal
│   └── assets/
│       ├── css/
│       │   ├── base.css
│       │   └── components.css
│       └── js/
│           ├── core/
│           │   ├── api.js                 ← Cliente HTTP
│           │   ├── constants.js           ← Constantes frontend
│           │   └── router.js              ← Enrutador SPA
│           └── modules/
│               ├── chat.js                ← 💬 Interfaz del chat
│               └── models.js              ← Gestión de modelos
│
└── desktop-codelab/                       ← IDE de escritorio (Electron+React)
    └── ...
```

---

## 4. Rutas de la API (Endpoints)

### 🌐 URL Base: `http://localhost:8001`

#### 💬 Chat IA — `/api/chat`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/chat/send` | **Enviar mensaje al chat IA** (endpoint principal) |
| `GET` | `/api/chat/history` | Listar sesiones recientes (últimas 50) |
| `GET` | `/api/chat/history/all` | Obtener todo el historial en JSON |
| `GET` | `/api/chat/history/{session_id}` | Mensajes de una sesión específica |
| `DELETE` | `/api/chat/history/{session_id}` | Eliminar una sesión |
| `GET` | `/api/chat/config` | Ver configuración actual del chat |
| `POST` | `/api/chat/config` | Actualizar configuración (ej: max_sql_retries) |
| `GET` | `/api/chat/export-full` | Exportar historial completo en HTML |

#### 📊 Base de Datos — `/api/database`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/database/metadata` | Ver metadatos actuales de la BD |
| `POST` | `/api/database/analyze-table` | Analizar tabla con IA y generar metadatos |
| `PUT` | `/api/database/metadata` | Actualizar metadatos manualmente |

#### 🤖 Modelos IA — `/api/models`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/models` | Listar todos los modelos configurados |
| `POST` | `/api/models` | Añadir nuevo modelo |
| `PUT` | `/api/models/{id}` | Actualizar modelo |
| `DELETE` | `/api/models/{id}` | Eliminar modelo |

#### 🔍 Explorador BD — `/api/db-explorer`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/db-explorer/tables` | Listar tablas de la BD |
| `GET` | `/api/db-explorer/table/{name}` | Ver columnas de una tabla |

#### 📚 Documentación API Interactiva

- **Swagger UI:** `http://localhost:8001/docs`
- **ReDoc:** `http://localhost:8001/redoc`

---

## 5. Flujo Completo de una Consulta

```
PASO 1: Usuario envía mensaje
────────────────────────────
POST /api/chat/send
{
  "message": "¿Cuántas facturas hay del mes pasado?",
  "model_id": "groq-llama-70b",
  "conversation_history": [...],
  "db_params": {
    "host": "localhost",
    "port": 3050,
    "database": "C:\\ruta\\empresa.fdb",
    "user": "SYSDBA",
    "password": "masterkey"
  }
}

PASO 2: router.py recibe la petición
─────────────────────────────────────
- Crea sesión en SQLite si no existe
- Guarda mensaje del usuario en historial
- Llama a service.process_message()

PASO 3: service.py — Construcción del contexto
───────────────────────────────────────────────
- Carga esquema semántico desde db_metadata_optimized.json
  → Solo tablas relevantes (ahorra ~90% tokens)
- Recupera historial de conversación (últimos N mensajes)
- Detecta intención: ¿SQL? ¿Visual? ¿Imagen?

PASO 4: service.py — Construcción del System Prompt
─────────────────────────────────────────────────────
System Prompt incluye:
  ✓ Rol: "Eres experto en Firebird SQL"
  ✓ Historial de conversación anterior
  ✓ Esquema de BD (tablas relevantes)
  ✓ Instrucciones críticas Firebird 2.5:
      - Usar FIRST N (no LIMIT)
      - Búsquedas UPPER() para case-insensitive
      - Sintaxis de fechas con EXTRACT()
  ✓ Tipos de documentos (TIPO=13 facturas, etc.)
  ✓ Terminología específica (splits, gas refrigerante)

PASO 5: ModelFallbackOrchestrator — Llamada a IA
──────────────────────────────────────────────────
- Ordena modelos por prioridad (score + tier)
- Intenta con modelo preferido primero
- Si falla → espera → reintenta → cambia modelo
- Devuelve: (respuesta_texto, model_id_usado)

PASO 6: service.py — Detección de SQL en respuesta
────────────────────────────────────────────────────
Si la IA devuelve ```sql ... ```:
  → Extrae la consulta SQL
  → Añade FIRST 100 automáticamente si no tiene límite
  → Llama a SQLCorrector.execute_with_correction()

PASO 7: SQLCorrector — Ejecución con auto-corrección
──────────────────────────────────────────────────────
Intento 1:
  - Aplica enforce_case_insensitive() (UPPER para LIKE)
  - Aplica clean_firebird_sql() (convierte LIMIT→FIRST)
  - Ejecuta en Firebird via FirebirdDriver

Si falla:
  - detect_error_type() → identifica: tabla?, columna?, sintaxis?
  - request_correction() → pide corrección a la IA
  - Reintenta con SQL corregido (hasta max_retries veces)

PASO 8: service.py — Verificación de privacidad
─────────────────────────────────────────────────
Si REQUIRE_DB_DATA_CONFIRMATION=True:
  → Devuelve preview de datos al usuario
  → Espera confirmación antes de enviar a IA

PASO 9: service.py — Interpretación de resultados
───────────────────────────────────────────────────
Segundo prompt a la IA:
  "Pregunta: ¿Cuántas facturas hay del mes pasado?
   SQL ejecutado: SELECT COUNT(*) FROM DOCCAB WHERE...
   Resultados: [{COUNT: 47}]
   Responde de forma clara, en euros, sin inventar datos."

PASO 10: router.py — Respuesta al usuario
───────────────────────────────────────────
- Guarda respuesta en historial SQLite
- Devuelve:
{
  "success": true,
  "response": "El mes pasado se emitieron 47 facturas.",
  "session_id": "uuid-de-la-sesion"
}
```

---

## 6. Componentes Clave

### 6.1 `ChatService` — `backend/modules/chat/service.py`

El cerebro del sistema. Orquesta todo el proceso:

```python
# Método principal
async def process_message(message: str, context: Dict) -> str:
    # 1. Carga esquema semántico de BD
    # 2. Construye historial de conversación
    # 3. Detecta intención (SQL / Visual / Imagen)
    # 4. Construye system prompt con reglas Firebird
    # 5. Llama a ModelFallbackOrchestrator
    # 6. Si hay SQL → ejecuta con auto-corrección
    # 7. Interpreta resultados con IA
    # 8. Devuelve respuesta final
```

**Comandos de debug especiales:**
- `DEBUG_TABLES` → Lista todas las tablas de la BD
- `DEBUG_COLUMNS <TABLA>` → Lista columnas de una tabla

### 6.2 `ModelFallbackOrchestrator` — `backend/modules/chat/model_fallback_orchestrator.py`

Garantiza que siempre haya respuesta aunque fallen modelos:

```
Modelos ordenados por: Score (éxitos históricos) → Tier (potencia)
  1. groq-llama-70b (preferido si se especifica)
  2. gemini-1.5-flash
  3. openrouter-claude
  ... etc.

Por cada modelo:
  - Intento 1 → falla → espera 2s → Intento 2 → falla → siguiente modelo
```

### 6.3 `SQLCorrector` — `backend/modules/chat/sql_corrector.py`

Auto-corrección de SQL en 3 niveles:

| Nivel | Qué hace |
|-------|----------|
| **Pre-ejecución** | `enforce_case_insensitive()`: convierte `LIKE '%x%'` → `UPPER(col) LIKE UPPER('%x%')` |
| **Pre-ejecución** | `clean_firebird_sql()`: convierte `LIMIT N` → `SELECT FIRST N` |
| **Post-error** | `detect_error_type()` + `request_correction()`: pide corrección a la IA |

**Tipos de errores detectados:**
- `table_unknown` → tabla no existe
- `column_unknown` → columna no existe  
- `invalid_keyword` → LIMIT/ROWS/TOP (no válidos en Firebird)
- `syntax_error` → error de sintaxis general

### 6.4 `FirebirdDriver` — `backend/drivers/db/firebird_driver.py`

Conexión robusta a Firebird 2.5:

```python
# Características:
- Charset: latin1 (máxima compatibilidad con caracteres españoles)
- Auto-reconexión: 3 reintentos si se pierde la conexión
- Encoding seguro: row_to_dict_safe() para manejar bytes/strings
- Credenciales por defecto: SYSDBA / masterkey
```

### 6.5 `ChatHistoryService` — `backend/modules/chat/chat_history_service.py`

Persistencia de conversaciones en SQLite local:

```
backend/data/chat_history.db
├── sessions (id, title, model_id, created_at, updated_at)
└── messages (id, session_id, role, content, meta, created_at)
```

---

## 7. Sistema de Metadatos de la BD

### ¿Por qué existe?

La BD Firebird tiene **436+ tablas**. Enviar todo el esquema a la IA en cada pregunta sería:
- Muy caro en tokens (coste API)
- Lento
- Confuso para la IA

### Solución: Metadatos Semánticos Optimizados

```
db_metadata_optimized.json
    ↓ carga al inicio
MetadataManager (singleton en memoria)
    ↓ cuando llega una pregunta
get_semantic_schema() → solo tablas relevantes
    ↓ se inyecta en el prompt
IA recibe esquema enfocado (~90% menos tokens)
```

### Archivo de metadatos: `backend/core/config/db_metadata_optimized.json`

Estructura de cada tabla:
```json
{
  "tables": {
    "DOCCAB": {
      "category": "Documentos de cabecera",
      "record_count": 3,
      "description": "Facturas, pedidos, albaranes...",
      "primary_keys": ["CODIGO"],
      "columns": {
        "TIPO": "ENTERO - Tipo de documento (13=factura, 11=albarán...)",
        "FECHA": "FECHA - Fecha del documento",
        "IMPORTETOTAL": "FLOAT - Importe total",
        ...
      },
      "consultas_comunes": [
        "SELECT * FROM DOCCAB WHERE CODCLIENTE = 15590"
      ]
    }
  }
}
```

### Cómo actualizar los metadatos

```bash
# Opción 1: Script automático (extrae de la BD real)
cd bots/interjddcia
python backend/scripts/extract_db_metadata.py

# Opción 2: Análisis con IA desde la UI
# Ir a: http://localhost:8001 → sección "Base de Datos" → "Analizar Tabla"

# Opción 3: Editar manualmente
# Editar: backend/core/config/db_metadata_optimized.json
```

---

## 8. Modelos IA Soportados

Configurados en `backend/core/config/ai_providers_config.json`:

| Proveedor | Modelos | API Key Variable |
|-----------|---------|-----------------|
| **Groq** | Llama 3.3 70B, Mixtral | `GROQ_API_KEY` |
| **Google Gemini** | Gemini 1.5 Pro/Flash | `GEMINI_API_KEY` |
| **OpenRouter** | Claude, GPT-4, DeepSeek, Qwen... | `OPENROUTER_API_KEY` |
| **OpenAI** | GPT-4o, GPT-4 Turbo | `OPENAI_API_KEY` |
| **DeepSeek** | DeepSeek V3, R1 | `DEEPSEEK_API_KEY` |
| **Mistral** | Mistral Large, Codestral | `MISTRAL_API_KEY` |
| **Anthropic** | Claude 3.5 Sonnet | `ANTHROPIC_CLAUDE_API_KEY` |
| **Cohere** | Command R+ | `COHERE_API_KEY` |
| **Qwen (Alibaba)** | Qwen Max | `ALIBABA_API_KEY` |
| **Together AI** | Llama, Mixtral open-source | `TOGETHER_API_KEY` |
| **Hugging Face** | Modelos open-source | `HUGGINGFACE_API_KEY` |
| + 8 más | Zhipu, Moonshot, Yi, Reka... | Ver `.env.example` |

> **Nota:** Solo necesitas configurar las API keys de los proveedores que quieras usar. El sistema usa los que estén disponibles.

---

## 9. Sistema de Fallback y Robustez

### Estrategia de Fallback

```
Modelo 1 (preferido) ──► Falla ──► Espera 2s ──► Reintento
                                                      │
                                                   Falla
                                                      │
Modelo 2 ──────────────────────────────────────────► Intento
    │
  Éxito ──► Devuelve respuesta + model_id_usado
```

### Tipos de errores y respuesta

| Error | Acción |
|-------|--------|
| `429 Quota Exceeded` | Marca proveedor como fallido, salta todos sus modelos |
| `401 Unauthorized` | Marca proveedor como fallido |
| `Timeout / 5xx` | Reintenta hasta 2 veces, luego cambia modelo |
| `Respuesta vacía` | Cambia al siguiente modelo |
| `JSON inválido` | Loop de auto-corrección (Reflection Prompt) |

### Ordenación de modelos

Los modelos se ordenan automáticamente por:
1. **Score** (historial de éxitos/fallos en la sesión actual)
2. **Tier** (potencia del modelo: flash < pro < ultra)

---

## 10. Corrección Automática de SQL

### Reglas específicas de Firebird 2.5 aplicadas automáticamente

```sql
-- ❌ INCORRECTO (MySQL/PostgreSQL)
SELECT * FROM DOCCAB LIMIT 10;
SELECT * FROM DOCCAB WHERE NOMBRE LIKE '%split%';

-- ✅ CORRECTO (Firebird 2.5) — aplicado automáticamente
SELECT FIRST 10 * FROM DOCCAB;
SELECT * FROM DOCCAB WHERE UPPER(NOMBRE) LIKE UPPER('%split%');
```

### Sintaxis de fechas en Firebird 2.5

```sql
-- Mes actual
WHERE EXTRACT(MONTH FROM FECHA) = EXTRACT(MONTH FROM CURRENT_DATE)
  AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)

-- Mes pasado (fórmula recomendada)
WHERE (EXTRACT(YEAR FROM FECHA) * 12 + EXTRACT(MONTH FROM FECHA)) = 
      (EXTRACT(YEAR FROM CURRENT_DATE) * 12 + EXTRACT(MONTH FROM CURRENT_DATE) - 1)

-- Hace N meses
WHERE (EXTRACT(YEAR FROM FECHA) * 12 + EXTRACT(MONTH FROM FECHA)) = 
      (EXTRACT(YEAR FROM CURRENT_DATE) * 12 + EXTRACT(MONTH FROM CURRENT_DATE) - N)
```

### Tipos de documentos (tabla DOCCAB, columna TIPO)

| TIPO | Documento |
|------|-----------|
| `0` | Presupuestos |
| `2` | Órdenes de trabajo / SAT |
| `3` | Abonos |
| `10` | Contratos |
| `11` | Albaranes |
| `12` | Pedidos |
| `13` | **Facturas** |
| `51` | Certificaciones |
| `61` | Recibos |

---

## 11. Historial de Conversaciones

### Almacenamiento

- **Tecnología:** SQLite (local, sin servidor)
- **Ubicación:** `backend/data/chat_history.db`
- **Tablas:** `sessions` + `messages`

### Acceso al historial

```bash
# Via API
GET http://localhost:8001/api/chat/history

# Exportar HTML completo (con todas las conversaciones)
GET http://localhost:8001/api/chat/export-full
```

### Contexto conversacional

El chat recuerda los últimos **N mensajes** de la sesión actual (configurable en `constants.py` → `UILimits.CONVERSATION_MEMORY_MESSAGES`). Esto permite preguntas de seguimiento:

```
Usuario: "¿Cuántas facturas hay este mes?"
IA: "Este mes hay 47 facturas."
Usuario: "¿Y del mes pasado?"  ← entiende que sigue hablando de facturas
IA: "El mes pasado hubo 52 facturas."
```

---

## 12. Configuración (.env)

Archivo: `bots/interjddcia/.env`

```env
# ═══════════════════════════════════════════
# BASE DE DATOS FIREBIRD (EMPRESA REAL)
# ═══════════════════════════════════════════
DB_HOST=localhost
DB_PORT=3050
DB_NAME=C:\Ruta\A\La\BaseDatos\empresa.fdb
DB_USER=SYSDBA
DB_PASSWORD=masterkey

# ═══════════════════════════════════════════
# MODELOS IA (configura los que uses)
# ═══════════════════════════════════════════
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxx
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxx
MISTRAL_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_CLAUDE_API_KEY=sk-ant-xxxxxxxxxx

# ═══════════════════════════════════════════
# CORREO ELECTRÓNICO (opcional)
# ═══════════════════════════════════════════
OUTLOOK_EMAIL=usuario@empresa.com
OUTLOOK_PASSWORD=contraseña
OUTLOOK_PASSWORD_APP=app_password_2fa

# ═══════════════════════════════════════════
# PRIVACIDAD
# ═══════════════════════════════════════════
REQUIRE_DB_DATA_CONFIRMATION=True  # Pide confirmación antes de enviar datos a IA
```

---

## 13. Cómo Ejecutar el Sistema

### ▶️ Método 1: Script automático (recomendado, Windows)

```batch
cd bots\interjddcia
start_system.bat
```

El script hace automáticamente:
1. Instala dependencias necesarias (`pip install aiofiles`)
2. Lanza el servidor FastAPI en puerto 8001
3. Abre el navegador en `http://localhost:8001`

### ▶️ Método 2: Manual

```bash
# 1. Ir al directorio del proyecto
cd bots/interjddcia

# 2. Instalar dependencias (primera vez)
pip install -r requirements.txt
# O instalar manualmente las principales:
pip install fastapi uvicorn firebirdsql pydantic-settings aiofiles

# 3. Configurar variables de entorno
copy .env.example .env
# Editar .env con tus credenciales reales

# 4. (Opcional) Extraer metadatos de la BD
python backend/scripts/extract_db_metadata.py

# 5. Iniciar el servidor
set PYTHONPATH=%CD%
python -m backend.main

# O con uvicorn directamente:
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001
```

### 🌐 URLs de acceso

| URL | Descripción |
|-----|-------------|
| `http://localhost:8001` | **Interfaz web del chat** |
| `http://localhost:8001/docs` | Documentación API Swagger |
| `http://localhost:8001/redoc` | Documentación API ReDoc |
| `http://localhost:8001/api/chat/export-full` | Exportar historial HTML |

### 🧪 Ejecutar tests

```bash
cd bots/interjddcia
.venv\Scripts\python.exe -m pytest backend/tests --rootdir=. -v
# Resultado esperado: 38 passed, 1 warning
```

---

## 14. Tablas de la BD Real Configuradas

Las siguientes tablas están documentadas en `db_metadata_optimized.json`:

| Tabla | Categoría | Registros | Descripción |
|-------|-----------|-----------|-------------|
| **DOCCAB** | Documentos | ~miles | Facturas, albaranes, pedidos, presupuestos... |
| **ARTICULO** | Productos | ~1.000 | Artículos/productos del inventario |
| **CLIENTE** | Clientes | ~500 | Clientes de la empresa |
| **PROVEED** | Proveedores | ~cientos | Proveedores |
| **ALMACEN** | Inventario | 10 | Almacenes de la empresa |
| **ESTALMACEN** | Almacenamiento | ~miles | Costes y ventas por almacén/fecha |
| **CAJA** | Finanzas | ~miles | Transacciones de caja |
| **AVISOS** | Notificaciones | 0 | Avisos del sistema |

> **Para añadir más tablas:** Editar `backend/core/config/db_metadata_optimized.json` o usar el script `extract_db_metadata.py`.

---

## 15. Seguridad y Privacidad

| Medida | Implementación |
|--------|---------------|
| **API Keys seguras** | Solo en `.env`, nunca en código. `.gitignore` configurado |
| **Solo SELECT** | El sistema solo ejecuta consultas de lectura |
| **Límite automático** | `SELECT FIRST 100` añadido automáticamente |
| **Confirmación de datos** | `REQUIRE_DB_DATA_CONFIRMATION=True` pide OK antes de enviar datos a IA |
| **Anonimizador** | Módulo `anonymizer` puede anonimizar datos sensibles antes de enviar a IA |
| **Logs sanitizados** | Las API keys se truncan en los logs |
| **CORS** | Configurado en `main.py` (actualmente `allow_origins=["*"]` para desarrollo) |

---

## 16. Comandos de Depuración

Escribe estos mensajes directamente en el chat para depurar:

```
DEBUG_TABLES
→ Lista todas las tablas de la BD con conteo de filas
→ Identifica candidatos para facturas/ventas

DEBUG_COLUMNS DOCCAB
→ Lista todas las columnas de la tabla DOCCAB

DEBUG_COLUMNS ARTICULO
→ Lista todas las columnas de la tabla ARTICULO
```

### Scripts de diagnóstico

```bash
# Verificar conexión a BD
python backend/scripts/test_db_connection.py

# Diagnosticar esquema
python backend/scripts/diagnose_schema.py

# Verificar tablas disponibles
python backend/scripts/check_tables.py

# Verificar variables de entorno
python check_env_vars.py

# Verificar modelos IA configurados
python verify_ai.py

# Verificar conexión BD
python verify_db.py
```

---

## 📊 Resumen Visual del Flujo

```
┌──────────────────────────────────────────────────────────────────┐
│  USUARIO: "¿Cuánto hemos facturado este mes?"                    │
└─────────────────────────┬────────────────────────────────────────┘
                          │ POST /api/chat/send
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  ROUTER: Crea sesión → Guarda mensaje → Llama service            │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  SERVICE: Carga metadatos BD → Construye prompt con esquema      │
│           + historial + reglas Firebird                          │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR: Llama a Groq Llama 70B                            │
│  IA responde: ```sql                                             │
│    SELECT SUM(IMPORTETOTAL) FROM DOCCAB                          │
│    WHERE TIPO=13                                                  │
│    AND EXTRACT(MONTH FROM FECHA)=EXTRACT(MONTH FROM CURRENT_DATE)│
│    AND EXTRACT(YEAR FROM FECHA)=EXTRACT(YEAR FROM CURRENT_DATE)  │
│  ```                                                             │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  SQL CORRECTOR:                                                   │
│  1. enforce_case_insensitive() → OK (no hay LIKE)                │
│  2. clean_firebird_sql() → OK (no hay LIMIT)                     │
│  3. Ejecuta en Firebird → [{SUM: 125430.50}]                     │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  SERVICE: Segundo prompt → "Interpreta: SUM=125430.50"           │
│  IA responde: "Este mes se ha facturado un total de              │
│               125.430,50 €"                                      │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  ROUTER: Guarda respuesta en SQLite → Devuelve al usuario        │
│  {"success": true, "response": "Este mes se ha facturado..."}    │
└──────────────────────────────────────────────────────────────────┘
```

---

*Documentación generada el 27/02/2026 — DEVIA System v1.0*
