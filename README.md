# DEVIA - Sistema de Gestión e Inteligencia Artificial

Sistema de chat IA sobre la base de datos Firebird de la empresa JDDC (climatización).  
Permite consultar la BD en lenguaje natural, analizar artículos, gestionar prompts y modelos IA.

> **Última actualización:** 08/07/2026  
> **Versión:** 2.9.0  
> **Estado tests:** ✅ 39 passed · 2 skipped · 0 failures (suite principal)

---

## 🚀 Características

- **Chat IA**: Consulta la BD Firebird en lenguaje natural (Qwen3 VL 30B local LAN)
- **SIUO**: Sistema de Índices Ultra-Optimizado — indexa las 443 tablas de la BD para contexto preciso
- **Múltiples Modelos IA**: Qwen3 LAN (principal), Groq, Gemini, OpenAI, Anthropic (fallback)
- **Gestión de Artículos**: CRUD completo con análisis de IA
- **Analista BD**: Módulo de análisis profundo con 70+ consultas SQL predefinidas por categoría
- **Constructor BD**: Análisis manual tabla a tabla con Qwen3 LAN
- **DB Simulator**: Simulador SQLite con datos sintéticos para tests sin BD real
- **Anonimizador**: Anonimización de datos sensibles (RGPD)
- **Outlook**: Bandeja de entrada unificada
- **Seguridad**: API keys en `.env`, datos de BD solo a IA local LAN (nunca a internet)
- **Análisis Profundo**: Pipeline multi-fase con verificación de fiabilidad (anti-alucinación)
- **Tests automatizados**: Suite pytest con 10.300+ tests (10.139 passing, 70 xfailed)

---

## 📋 Requisitos

- Python 3.10+
- Firebird 2.5+ (o compatible)
- API Keys para los modelos de IA que desees usar

---

## 🔧 Instalación

### 1. Clona el repositorio:
```bash
git clone https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
cd jddc_materiales_local_bd_ia/bots/interjddcia
```

### 2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

### 3. Configura las variables de entorno:

Crea un archivo `.env` en la raíz del proyecto (copia desde `.env.example`):

```bash
copy .env.example .env
```

Edita `.env` y añade tus API keys:

```env
# AI API Keys
GROQ_API_KEY=tu_api_key_de_groq
OPENROUTER_API_KEY=tu_api_key_de_openrouter
GEMINI_API_KEY=tu_api_key_de_gemini
OPENAI_API_KEY=tu_api_key_de_openai

# Database Configuration
DB_HOST=192.168.0.254
DB_PORT=3050
DB_NAME=C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb
DB_USER=SYSDBA
DB_PASSWORD=masterkey
```

### 4. Arranca el sistema:

**Windows (recomendado):**
```
ARRANCAR_DEVIA.bat   ← doble clic
```

**Manual:**
```bash
python start_backend.py
# o
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001
```

Accede a:
- **Frontend**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

---

## 🗄️ Base de Datos Firebird — Configuración Real

| Parámetro | Valor real |
|-----------|-----------|
| **Ruta del .fdb** | `C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb` |
| **Servidor (IP)** | `192.168.0.254` |
| **Puerto** | `3050` |
| **Usuario** | `SYSDBA` |
| **Password** | `masterkey` |
| **Charset** | `latin1` (para caracteres españoles) |

> ⚠️ El hostname `HOST1.JDDC.local` **NO funciona** en Python/firebirdsql en Windows.
> Siempre usar la IP directa `192.168.0.254`.

### Cambiar el archivo .fdb (ej: nuevo año)

```bash
# Editar bots/interjddcia/.env:
DB_NAME=C:\Distrito\OBRAS\Database\JUANDEDI\2022.fdb

# Reiniciar el backend:
ARRANCAR_DEVIA.bat
```

---

## 🏗️ Arquitectura

```
bots/interjddcia/
├── backend/
│   ├── core/
│   │   ├── config/        # Settings, concept_index.json, table_index.json (SIUO)
│   │   ├── context/       # ContextManager (historial multi-turno)
│   │   └── utils/         # Constantes, encoding, network audit
│   ├── drivers/
│   │   ├── ai/            # JDDCIAProvider (Qwen3 LAN), OpenAI-compatible
│   │   └── db/            # FirebirdDriver
│   └── modules/
│       ├── chat/          # Pipeline chat: safety → SQL → corrección → formato
│       │   ├── pipeline/  # Fases 0-4 del pipeline
│       │   └── deep_analysis/  # Análisis profundo multi-fase
│       ├── db_analyst/    # Analista BD: 70+ consultas por categoría
│       ├── db_explorer/   # SIUO: indexación + ContextRetriever
│       ├── db_simulator/  # Simulador SQLite para tests
│       │   ├── schema.py          # DDL de todas las tablas
│       │   ├── synthetic_seeder.py # Datos sintéticos realistas
│       │   ├── driver.py          # Driver SQLite compatible Firebird
│       │   └── data/simulator.db  # BD SQLite con datos de prueba
│       └── models/        # Gestión de modelos IA
├── frontend/
│   ├── index.html         # SPA
│   └── assets/
│       ├── css/           # Estilos
│       └── js/modules/    # chat.js, db_analyst.js, chat-recovery.js...
├── tests/
│   ├── unit/              # Tests unitarios (sin BD real ni IA)
│   ├── integration/       # Tests de integración SIUO
│   └── e2e/               # Tests end-to-end
├── DEVIA.MD               # Documentación técnica completa
├── pytest.ini             # Configuración pytest
└── conftest.py            # Fixtures globales
```

---

## 🧠 SIUO — Sistema de Índices Ultra-Optimizado

El SIUO indexa las **443 tablas** de la BD Firebird para que el ContextRetriever
seleccione automáticamente las tablas relevantes para cada pregunta del usuario.

### Ficheros del SIUO

| Fichero | Descripción |
|---------|-------------|
| `backend/core/config/table_index.json` | Índice de tablas con columnas, n_records, descripción |
| `backend/core/config/concept_index.json` | Mapa keyword → tablas (2.113 conceptos) |
| `backend/core/config/graph_index.json` | Grafo de relaciones entre tablas (383 aristas) |
| `backend/core/config/siuo_query_log.json` | Log de consultas para autoaprendizaje |

### Cómo funciona

```
Pregunta usuario: "dame las últimas facturas"
        ↓
ContextRetriever.get_context(pregunta)
        ↓
1. Normaliza texto → keywords: ["ultima", "facturas"]
2. concept_index: "facturas" → DOCCAB (TIPO=13), DOCLIN, SERIE...
3. Grafo: expande tablas relacionadas
4. Selecciona top-8 tablas por relevancia
5. Devuelve contexto DDL + filtros sugeridos (~1500 tokens)
        ↓
LLM genera SQL con el contexto correcto
```

---

## 🔑 Sistema de Proveedores de IA

| Proveedor | Uso | Configuración |
|-----------|-----|---------------|
| **Qwen3 VL 30B (LAN)** | Principal — datos reales de BD | `192.168.0.36` (LMStudio) |
| **Groq** | Fallback rápido | `GROQ_API_KEY` en `.env` |
| **OpenRouter** | Fallback multi-modelo | `OPENROUTER_API_KEY` en `.env` |
| **Google Gemini** | Fallback | `GEMINI_API_KEY` en `.env` |
| **OpenAI** | Fallback | `OPENAI_API_KEY` en `.env` |

> ⚠️ **Seguridad**: Los datos reales de la BD **nunca** se envían a proveedores externos.
> Solo el modelo LAN (Qwen3) recibe datos reales. Los modelos externos solo reciben
> el esquema de tablas (sin datos).

---

## 🛡️ Seguridad

- ✅ API keys en `.env` (nunca en el código)
- ✅ `.gitignore` configurado para secretos
- ✅ Validación de consultas SQL (solo SELECT)
- ✅ Límites automáticos en consultas (FIRST 100)
- ✅ `AI_LOCAL_ONLY` mode: bloquea todos los modelos externos
- ✅ Network audit: registra todas las llamadas de red

---

## 🧪 Tests

### Estado actual (03/07/2026)

```
tests/                          10.139 passed
                                   162 skipped
                                    70 xfailed  (vacíos en simulador — esperado)
                                     7 failed   (aislamiento de tests — pasan solos)
```

### Ejecutar tests

```bash
# Todos los tests (desde bots/interjddcia/)
python -m pytest tests/ --tb=no -q

# Solo tests unitarios (rápido, sin BD real)
python -m pytest tests/unit/ --tb=short -q

# Tests de integración SIUO
python -m pytest tests/integration/ --tb=short -q

# Un fichero específico
python -m pytest tests/unit/test_simulator_sql_comprehensive.py -v
```

### Estructura de tests

```
tests/
├── unit/
│   ├── test_simulator_sql_comprehensive.py  # 156 tests SQL en simulador
│   ├── test_analista_bd_catalog.py          # 70 tests analista BD
│   ├── test_db_simulator_queries.py         # 57 tests queries simulador
│   ├── test_db_simulator_core.py            # Tests core simulador
│   ├── test_knowledge_and_helpers_comprehensive.py  # 1200+ tests helpers
│   ├── test_context_and_multiturn_chat.py   # Tests chat multi-turno
│   ├── test_ultra_resilience.py             # Tests resiliencia SQL
│   ├── test_deep_analysis_*.py              # Tests análisis profundo
│   └── ...
├── integration/
│   ├── test_siuo_retriever.py               # 16 tests SIUO retriever
│   └── test_sistemas_ia.py                  # Tests sistemas IA
└── test_context_retriever_questions.py      # 44 tests preguntas reales
```

### DB Simulator

El **DB Simulator** permite ejecutar tests SQL sin necesidad de la BD Firebird real.
Usa SQLite con datos sintéticos que replican la estructura de la BD JDDC.

```python
# Usar el simulador en tests
from backend.modules.db_simulator.driver import SimulatorDriver
db = SimulatorDriver()
rows = db.execute_query("SELECT * FROM ARTICULO LIMIT 5")
```

---

## 📊 Módulo Analista BD

El módulo `db_analyst` proporciona **70+ consultas SQL predefinidas** organizadas por categoría:

| Categoría | Descripción |
|-----------|-------------|
| **Gerencia** | KPIs globales, facturación, proyectos |
| **Contabilidad** | IVA, recibos, aging, variación precios |
| **Almacén** | Stock, roturas, valor inventario, ubicaciones |
| **Comercial** | Ranking clientes, estacionalidad, ciclo vida |
| **Predicciones** | Tendencias, RFM, proyecciones |
| **Alertas** | Duplicados, anomalías, incoherencias |
| **Reporting** | Cuadro mando, dashboards, KPIs financieros |

Acceso desde el frontend: pestaña **"Analista BD"**.

---

## 📚 Documentación adicional

| Fichero | Contenido |
|---------|-----------|
| [DEVIA.MD](DEVIA.MD) | Documentación técnica completa del sistema |
| [SIUO_SISTEMA_COMPLETO.md](SIUO_SISTEMA_COMPLETO.md) | Documentación del SIUO |
| [PLAN_OPTIMIZACION_SIUO_v2.md](PLAN_OPTIMIZACION_SIUO_v2.md) | Plan de mejoras SIUO |
| [PENDIENTE_REFACTORIZACION.md](PENDIENTE_REFACTORIZACION.md) | Tareas pendientes |
| [PENDIENTES_QUERY_LIBRARY.md](PENDIENTES_QUERY_LIBRARY.md) | Mejoras query library |
| [README2_DB_EXPLORER_SIUO.md](README2_DB_EXPLORER_SIUO.md) | DB Explorer detallado |

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo licencia MIT.

## 👤 Autor

Miguel Martínez - [@miguelmartmart](https://github.com/miguelmartmart)
