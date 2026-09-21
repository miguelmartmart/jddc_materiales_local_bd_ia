# DEVIA — Sistema DEVIA: Resumen Ejecutivo y Jerarquía
## Backend IA para Gafas Meta Ray-Ban + Chat Web + Constructor BD

> **Última actualización:** 11/09/2026  
> **Versión:** 3.3.0  
> **Ruta raíz:** `bots/interjddcia/`  
> **Commit actual:** `9b08fc7`  
> **Tests:** ✅ 10.343+ passed · 69 skipped · 71 xfailed (suite completa)

---

## PRINCIPIOS DEVIA (obligatorios en todo el sistema)

| # | Principio | Descripción |
|---|-----------|-------------|
| 1 | **Sin inventar** | Nunca generar datos, tablas, columnas o valores que no existan en el esquema real |
| 2 | **Ultra-resiliente** | Cada módulo falla de forma segura; si falla, devuelve el estado anterior sin modificar |
| 3 | **Determinista primero** | Lógica determinista antes que IA; la IA es enriquecimiento opcional |
| 4 | **Genérico** | Sin hardcoding de casos concretos; el sistema deduce, infiere y analiza |
| 5 | **Modular** | Sin dependencias circulares; cada módulo < 500 líneas |
| 6 | **Jerárquico** | Este DEVIA es el resumen; los detalles están en los DEVIAs secundarios, con referencias EXACTAS a cada DEVIA secundario y a los ficheros/funcionalidades importantes que describe, para que ninguna funcionalidad quede huérfana o se pierda; cada DEVIA debe mantenerse breve, pero el conjunto de todos los DEVIAs debe describir el proyecto completo |
| 7 | **Sin alucinaciones** | Módulos específicos verifican que tablas/columnas/valores existen en el esquema real |
| 8 | **Logging de auditoría** | Cada decisión relevante queda registrada para trazabilidad |
| 9 | **Tests independientes** | Cada test es independiente; sin mocks de datos, solo mocks de preguntas |
| 10 | **Privacidad LAN** | Ningún dato de la BD sale a internet; solo Qwen3 LAN para análisis |

---

## ARRANQUE RÁPIDO

```
ARRANCAR_DEVIA.bat   ← doble clic para arrancar todo
PARAR_DEVIA.bat      ← doble clic para parar todo
```

| Opción | Qué arranca | Cuándo usarla |
|--------|------------|---------------|
| **1** | Solo Backend DEVIA (puerto 8001) | Chat IA web, gafas Meta, API |
| **2** | Backend DEVIA + CodeLab desktop | Uso completo del sistema |
| **3** | Solo CodeLab desktop | Editor de código con IA |
| **4** | Diagnóstico (sin arrancar nada) | Verificar estado del sistema |

Tras arrancar: **http://localhost:8001**

---

## ARQUITECTURA DEL SISTEMA

```
GAFAS META RAY-BAN / CHAT WEB / API
        │
        ▼ POST /api/chat/send
Backend DEVIA (FastAPI + Python)
        │
        ├─ ChatService (service.py)
        │   ├─ SemanticReasoningEngine  ← razona ANTES de generar SQL
        │   ├─ HallucinationGuard       ← verifica SQL generado por IA
        │   ├─ FirebirdSQLNormalizer    ← corrige SQL (LIMIT→FIRST, ILIKE→LIKE)
        │   ├─ SQLCorrector             ← reintentos con corrección IA
        │   └─ ModelFallbackOrchestrator ← fallback multi-modelo
        │
        ├─ DB Simulator (SQLite)        ← tests sin BD real
        │   ├─ schema.py               ← fuente de verdad del esquema
        │   ├─ query_library.py        ← biblioteca de consultas
        │   └─ snapshot_service.py     ← snapshot de BD real
        │
        ├─ Deep Analysis Agent          ← análisis profundo multi-fase
        │   └─ pipeline/ (phase1..5)
        │
        └─ SIUO (Sistema de Índices Ultra-Optimizado)
            ├─ context_retriever.py    ← contexto mínimo y preciso para IA
            ├─ concept_index.json      ← concepto → tablas
            ├─ table_index.json        ← resumen compacto de tablas
            └─ db_graph.json           ← grafo de relaciones
```

---

## JERARQUÍA DE DEVIAs

API Clone y Utilidades de Ingeniería: [backend/modules/api_clone/DEVIA.MD](backend/modules/api_clone/DEVIA.MD)
→ [utilidades/DEVIA.MD](backend/modules/api_clone/utilidades/DEVIA.MD)
(estado, pruebas y continuidad de la sesión del 17/09/2026).

> Cada DEVIA secundario entra en detalle sobre su módulo.  
> Este documento es el punto de entrada; no repetir aquí lo que está en los secundarios.

### Nivel 1 — Sistema completo
| DEVIA | Ruta | Contenido |
|-------|------|-----------|
| **Este documento** | `bots/interjddcia/DEVIA.MD` | Resumen ejecutivo, arquitectura, principios, jerarquía |

### Nivel 2 — Módulos principales
| DEVIA | Ruta | Contenido |
|-------|------|-----------|
| Chat & IA | `backend/modules/chat/DEVIA.MD` | Pipeline SQL, modelos LAN, razonamiento semántico, anti-alucinaciones |
| Chat Robustez | `backend/modules/chat/DEVIA_ROBUSTNESS.md` | Model Fallback, Self-Healing, timeouts |
| DB Simulator | `backend/modules/db_simulator/DEVIA.md` | Esquema SQLite, seed data, query library |
| Configuración | `backend/core/config/DEVIA.MD` | Settings, modelos IA, API keys |
| **API Explorer** | `docs/SESION_2026_09_11_ESTADO_ACTUAL.md` | Probador Visual API mPYME. Estado actual, pendientes y arquitectura. LEER PRIMERO. |

### Nivel 3 — Submódulos (detalle técnico)
| DEVIA | Ruta | Contenido |
|-------|------|-----------|
| Deep Analysis | `backend/modules/chat/deep_analysis/DEVIA.md` | Pipeline fases 1-5, síntesis, verificación |
| Pipeline Chat | `backend/modules/chat/pipeline/DEVIA.md` | Fases del pipeline de chat |
| **Tests QA SQL Obras** | `tests/qa_sql_obras/DEVIA.MD` | Cientos de tests que simulan preguntas de usuario sobre SQL Obras contra `POST /api/chat/send` real (sin mocks), cruzando modelo (30B/8B) × BD (real/simulador). Contiene el **registro de progreso** de esta iniciativa (ver sección siguiente) |

---

## 📋 REGISTROS DE PROGRESO (para retomar tras cortes de conversación)

Auditoría API Clone del 17/09/2026: [fiabilidad, evidencias Firebird y tests adversariales](docs/AUDITORIA_API_CLONE_FIABILIDAD_2026_09_17.md).
No certificar fiabilidad absoluta: 13 casos iniciales de garantías incumplidas;
tras corregir AUD-09 quedan 12 pendientes. Checks agrupados con ayudas implementados
en `backend/modules/api_clone/utilidades/check_catalog.py` y `check_runner.py`.

> Estos ficheros son logs Markdown persistentes, con una fila por sesión, pensados para que un asistente (o una persona) pueda retomar el trabajo sin releer todo el historial de chat. Se añade una fila nueva cada sesión; no se borran las anteriores.

| Registro | Ruta | Qué guarda |
|----------|------|------------|
| QA SQL Obras | `tests/qa_sql_obras/DEVIA.MD` (tabla "Registro de progreso") | Avance de la generación de tests de preguntas de usuario sobre SQL Obras: decisiones de diseño, lotes de casos generados, incongruencias detectadas entre el manual técnico y los valores reales de la BD |
| **Observaciones y conclusiones (optimización de fases)** | `tests/qa_sql_obras/OBSERVACIONES_OPTIMIZACION.md` | Distinto del registro de progreso: aquí se acumulan hallazgos sobre **carencias del sistema** (huecos de conocimiento, fiabilidad de modelos LAN, gaps de esquema, reglas de negocio no capturadas...) detectados mientras se generan/ejecutan los tests de QA SQL Obras, cada uno con la fase del pipeline de chat a la que apunta. Se irá sintetizando en una propuesta concreta de optimización de fases para que las respuestas del chat IA sean de ultra calidad |

---

## FLUJO PRINCIPAL: PREGUNTA → SQL → RESPUESTA

```
[1] Usuario pregunta en lenguaje natural
        │
        ▼
[2] SemanticReasoningEngine.reason()
    → Detecta dominio (certificaciones, retenciones, artículos...)
    → Infiere tablas y relaciones correctas
    → Genera hints SQL deterministas
    → Enriquece el system prompt
        │
        ▼
[3] IA genera SQL (Qwen3 8B/30B LAN o fallback internet)
        │
        ▼
[4] HallucinationGuard.validate()
    → Verifica que tablas existen en el esquema real
    → Verifica que columnas existen en las tablas
    → Verifica valores de columnas enumeradas (TIPO, BAJA...)
    → Si hay errores críticos → no ejecutar
        │
        ▼
[5] FirebirdSQLNormalizer.normalize()
    → LIMIT → FIRST N
    → ILIKE → LIKE + UPPER()
    → DOCLIN.FECHA → JOIN DOCCAB
    → Elimina punto y coma final
        │
        ▼
[6] Ejecutar en BD (Firebird real o SQLite simulador)
    → Si falla → SQLCorrector con contexto del error (hasta 4 reintentos)
        │
        ▼
[7] Interpretar resultados y responder al usuario
    → Voz (MetaGlass): interpret_results_for_voice() — determinista
    → Web: ResponseSummarizer con paginación
```

---

## MÓDULOS CLAVE Y SUS RESPONSABILIDADES

| Módulo | Archivo | Responsabilidad |
|--------|---------|-----------------|
| **SemanticReasoningEngine** | `chat/semantic_reasoning_engine.py` | Razona sobre la pregunta ANTES de generar SQL. Detecta dominio, infiere tablas, genera hints. |
| **HallucinationGuard** | `chat/hallucination_guard.py` | Verifica que el SQL generado NO contiene tablas/columnas/valores inventados. |
| **FirebirdSQLNormalizer** | `chat/firebird_sql_normalizer.py` | Correcciones deterministas de SQL para Firebird. |
| **SafetyGuard** | `chat/safety_guard.py` | Bloquea operaciones destructivas (DROP, DELETE, UPDATE...) e inyecciones de prompt. |
| **SQLCorrector** | `chat/sql_corrector.py` | Reintentos con corrección IA cuando el SQL falla. |
| **ModelFallbackOrchestrator** | `chat/model_fallback_orchestrator.py` | Fallback entre modelos IA (LAN → internet). |
| **DB Simulator** | `db_simulator/driver.py` | SQLite en memoria/disco que replica el esquema Firebird para tests. |
| **QueryLibrary** | `db_simulator/query_library.py` | Biblioteca de consultas SQL validadas (Firebird + SQLite). |
| **ContextRetriever** | `db_explorer/context_retriever.py` | Recupera contexto mínimo y preciso del SIUO para cada pregunta. |
| **RealApiClient** | `api_explorer/service.py` | Cliente HTTP para la API mPYME de SQL Obras (browse/read/permiso/info/write...). |
| **ApiExplorer router** | `api_explorer/router.py` | Endpoints del Probador Visual: auto-probar exhaustivo, valores-param, diagnostico-firebird. |

> **Estado API Explorer:** ver `docs/SESION_2026_09_11_ESTADO_ACTUAL.md`

---

## MODELOS IA DISPONIBLES

| ID | Modelo | Velocidad | Uso |
|----|--------|-----------|-----|
| `jddcia-qwen3-30b-ip` | Qwen3 30B (IP directa) | 30-60s | Análisis profundo, preferido |
| `jddcia-qwen3-8b-ip` | Qwen3 8B VL (LM Studio) | 5-15s | Chat conversacional, rápido |
| Fallback internet | Gemini, Groq, OpenAI... | Variable | Si LAN no disponible |

> **Configuración:** `backend/modules/chat/config.json` → `ai_local_only: true/false`  
> **Detalle completo:** → `backend/modules/chat/DEVIA.MD`

---

## TESTS

```cmd
# Suite completa
python -m pytest bots/interjddcia/tests/ -v

# Solo tests unitarios (sin BD real, sin IA)
python -m pytest bots/interjddcia/tests/unit/ -v

# Tests de abstracción semántica (284 tests)
python -m pytest bots/interjddcia/tests/unit/test_semantica_*.py -v

# Tests anti-alucinaciones
python -m pytest bots/interjddcia/tests/unit/test_hallucination_guard.py -v

# Tests de conversaciones complejas reales (116 tests)
python -m pytest bots/interjddcia/tests/unit/test_conversaciones_complejas_reales.py -v
```

| Suite | Tests | Estado |
|-------|-------|--------|
| Conversaciones complejas reales | 116 | ✅ |
| Abstracción semántica (6 módulos) | 284 | ✅ |
| Anti-alucinaciones | ~60 | ✅ |
| Normalización SQL | 34 | ✅ |
| Voz + TTS | ~30 | ✅ |
| Paginación web + MetaGlass | ~25 | ✅ |

---

## DIAGNÓSTICOS RÁPIDOS

```cmd
# ¿Está corriendo?
curl http://localhost:8001/health

# Configuración actual
curl http://localhost:8001/api/chat/config

# ¿Qwen3 LAN responde?
curl -s --max-time 5 http://192.168.0.36/api/vlm/v1/models -H "Authorization: Basic YWRtaW46YWlzdGFjazIwMjY="

# Activar fallback internet (si LAN caída)
curl -X POST http://localhost:8001/api/chat/config -H "Content-Type: application/json" -d "{\"ai_local_only\": false}"
```

> **Diagnósticos detallados:** → `backend/modules/chat/DEVIA.MD` (sección Diagnósticos)

---

## HISTORIAL DE CAMBIOS RECIENTES

| Fecha | Cambio | Módulo |
|-------|--------|--------|
| 10/07/2026 | `HallucinationGuard`: módulo anti-alucinaciones. Verifica tablas/columnas/valores contra esquema real | `chat/hallucination_guard.py` |
| 10/07/2026 | `SemanticReasoningEngine`: handler clientes_proveedores infiere AGENTES dinámicamente | `chat/semantic_reasoning_engine.py` |
| 10/07/2026 | 284 tests de abstracción semántica en 6 módulos (artículos, clientes, documentos, financiero, estructura BD, vocabulario) | `tests/unit/test_semantica_*.py` |
| 09/07/2026 | 116 tests de conversaciones complejas reales sin mocks | `tests/unit/test_conversaciones_complejas_reales.py` |
| 08/07/2026 | Fix timeout análisis profundo: frontend heartbeat 30s + extensiones automáticas | `chat/service.py`, `constants.js` |
| 08/07/2026 | ProgressTracker en DeepAnalysisAgent: fases reportadas en tiempo real | `chat/deep_analysis_agent.py` |

> **Historial completo:** → `backend/modules/chat/DEVIA.MD` (sección Documentación de sesiones)

## Corrección de técnicos y selector — 17/09/2026

La utilidad «Técnicos y actividad registrada» reemplaza la interpretación anterior de horas. `project_activity.py` consulta recursos vinculados mediante CODPROYECTO, incluye líneas con CANTIDAD=0 y separa ESPREVISION=0/1. La respuesta contiene `actividad`, `tecnicos`, `grupos` y `horas_verificadas: false`; no devuelve los antiguos totales de horas/costes como si estuvieran certificados. Los grupos incluyen explicaciones desplegables. Esto no certifica que cada recurso haya trabajado ni resuelve los demás hallazgos de auditoría.

El selector BD de Utilidades incorpora búsqueda por código/nombre y páginas de 15 mediante GET `/proyectos-buscar`. El selector antiguo del Probador no forma parte de esta corrección.

Validación directa de solo lectura en Firebird: 1214 proyectos; búsqueda y páginas disjuntas comprobadas. Proyecto 1001331: existe, sin líneas OBRALIN directamente vinculadas. Proyecto 10: 6 recursos, 2507 líneas MO previstas. Proyecto 45215: 26 recursos, 6490 líneas MO (72 no previstas y 6418 previstas), 66 sin código de recurso. Evidencia: `docs/validacion_actividad_proyectos_2026_09_17.json`; reproducción: `scripts/verificar_actividad_proyectos.py`.

Pruebas: utilidades + auditoría + selector + checks agrupados: 70 passed, 11 xfailed (hallazgos pendientes), una advertencia preexistente. Interfaz Node: 6 passed; comprobación sintáctica JS correcta. El caso AUD10 queda mitigado para esta utilidad al dejar de presentar previsiones como horas verificadas; no para las demás consultas.

Despliegue local pendiente: el servidor Python PID 19320 en puerto 8001 sigue con el backend anterior. El script `scripts/recargar_backend_api_clone.ps1` verifica que sirve el JS de este directorio y que existe un único listener Python antes de intentar reiniciarlo. Windows denegó Stop-Process incluso fuera del sandbox; no se detuvo el servidor. Es necesario reiniciarlo desde la sesión con permisos que lo inició y recargar el navegador. No se verificó el nuevo endpoint por HTTP en ese proceso.


## Informe TXT y distribución — 21/09/2026
Botón permanente en cabecera API Clone: «Comprobar y exportar informe TXT», más acceso a checks y ayudas. GET /api/api-clone/utilidades/informe-fiabilidad.txt ejecuta los 13 checks globales y devuelve TXT UTF-8 sin caché con SQL, poblaciones, incidencias, estados, ayudas, pendientes y JSON completo con SHA-256. La huella no certifica veracidad. Errores de consulta aparecen como no verificables, no como éxitos. No ejecuta pytest ni compara cada endpoint con el ERP, ni certifica estados/bloqueos o pertenencia de negocio al 100 %. Las consultas no comparten una instantánea.
Retirados del Probador los badges históricos de garantía absoluta; revisada la afirmación de equivalencia con mPYME. Versión visible 2026-09-21.1 y versión de JS actualizada.
Validación: 72 passed, 11 xfailed (defectos pendientes de auditoría), 8 tests Node correctos y sintaxis JS válida. Contrato HTTP comprobado con TestClient, sin acceso a la VM.
La carpeta utilidades y la integración estaban sin registrar/confirmar en Git local: un pull en otra máquina no transporta estos cambios. Parche de entrega: docs/api_clone_utilidades_20260921.patch. No se ha publicado ni aplicado en la VM.


## Publicación y evidencia ampliada — 21/09/2026
Informe TXT ampliado a 27 checks en seis grupos y catálogo real de PK/FK/UNIQUE en cinco tablas. Se comprueban nulos/duplicados de claves completas, relación cabecera-línea, proyecto y previsión discrepantes, recursos sin identificar y ambigüedad de CODIGO sin CODCAB. El inventario incluye segmentos ordenados y destino de las FKs; no infiere relaciones declaradas cuando no existen.
Ejecución desde este PC, Firebird en transacción de solo lectura: 16 correctos, 8 revisar, 3 no verificables; 944001 líneas y 1216 proyectos en esta ejecución. No hay instantánea común garantizada. Evidencia íntegra: docs/informe_fiabilidad_2026_09_21.txt. OBRALIN tiene PK (CODCAB,CODIGO); 6401 grupos de CODIGO repetidos entre cabeceras. Las incidencias necesitan interpretación de negocio; no se modificaron datos.
Pruebas: 147 passed + 11 xfailed, 8 Node. Auditoría con --runxfail: 20 passed y 11 failed. Los 11 fallos se documentan como defectos abiertos, nunca como éxitos; no se certifica el 100 %. Logs en docs/tests_api_clone_2026_09_21.txt y docs/fallos_api_clone_2026_09_21.txt. Reproducir lectura real con .venv\Scripts\python.exe scripts/verificar_informe_fiabilidad.py.
Despliegue: tras incorporar el commit en la VM, reiniciar backend y Ctrl+F5. La cabecera debe mostrar versión 2026-09-21.2 y el botón TXT. Los párrafos anteriores sobre cambios sin publicar describen el estado anterior a esta publicación.


## Refuerzo ante errores humanos — 21/09/2026, versión de interfaz 2026-09-21.3
Diez casos antes xfail pasan como regresiones ordinarias: filtros no soportados rechazados (incluido offset), valores vacíos/estructurados rechazados, límites validados, read de OBRALIN exige CODCAB:CODIGO, read ambiguo falla, cuerpos HTTP no ignoran extras, ESPREVISION=0/1 separa clases, FINOBRA se devuelve, ranking incluye ajustes negativos. Los totales ausentes/incorrectos fallan y las listas indican truncamiento. Rechazar FINOBRA/offset no implementa esos filtros: evita ignorarlos silenciosamente.
El Probador permite escribir la clave compuesta para read de líneas. Cambio incompatible intencional: el CODIGO aislado ya no sirve para leer OBRALIN. La clave identifica una fila, no certifica la obra elegida por una persona. Browse/read marcan fiabilidad_negocio=no_verificada; no se corrigen ni reasignan datos del ERP.
213 pruebas Python aprobadas, 1 xfail pendiente y 9 Node aprobadas. Incluye 20 semillas reproducibles de datos mezclados, entradas malformadas, NULL, límites, duplicados, claves sobredimensionadas y error humano de proyecto con verificación de que no cambia la BD. SQLite valida lógica; no sustituye Firebird.
Pendiente AUD-05: líneas sin CODPROYECTO pero relacionadas mediante cabecera. No se infiere pertenencia automáticamente; la cobertura declarada es la referencia explícita. La prueba pendiente ahora compara solo ESPREVISION=0, pues previsiones se consultan por separado. Los informes históricos con 11 fallos describen el estado anterior.
Lectura real de solo lectura en este PC: proyecto 45215 tiene 702 líneas no previstas y 8168 previstas; cinco de cada grupo contrastadas por PK completa con read. Muestra limitada, no certificación global. Evidencia: docs/lecturas_api_clone_2026_09_21.json. Reproducción: scripts/verificar_lecturas_api_clone.py. Resultados de tests: docs/tests_api_clone_refuerzo_2026_09_21.txt. No se han probado todos los estados ni permisos del ERP, ni se demuestra fiabilidad absoluta.
