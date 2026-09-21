# DEVIA: tests/unit — Tests Unitarios

`test_api_clone_fiabilidad_audit.py`: 28 casos adversariales, 16 pasan y 12 son
xfail estrictos (garantías pendientes). AUD-09 se corrigió con los checks agrupados.
`test_api_clone_grouped_checks.py`: estados, vacíos, errores, ayudas y grupos.
`test_api_clone_checks_ui.cjs`: Node, render seguro y respuestas atrasadas.
Ver [auditoría](../../docs/AUDITORIA_API_CLONE_FIABILIDAD_2026_09_17.md).

`test_api_clone_utilidades.py`: 33 pruebas sin BD/red de contratos HTTP,
validación de parámetros, cálculos, serialización y errores de coherencia.
Detalle: [Utilidades](../../backend/modules/api_clone/utilidades/DEVIA.MD).

```json
{
  "capa": "unit",
  "descripcion": "Tests unitarios de DEVIA. Sin BD, sin IA, sin red. Rápidos (<1s cada uno).",
  "principio": "Cada test verifica UNA sola función o clase en aislamiento total.",
  "hereda_de": "tests/DEVIA.MD",

  "ficheros": {
    "conftest.py":               "Fixtures locales de unit (datos de prueba, factories)",
    "test_response_summarizer.py": "ResponseSummarizer: resumen, paginación, detección",
    "test_voice_interpreter.py":   "interpret_results_for_voice: respuestas TTS MetaGlass",
    "test_tts_cleaner.py":         "clean_for_tts: limpieza de Markdown para TTS",
    "test_sql_normalizer.py":      "FirebirdSQLNormalizer: LIMIT→FIRST, LIKE→UPPER, etc.",
    "test_pagination_detection.py":"Detección de peticiones de paginación del usuario"
  },

  "reglas": {
    "sin_red":    "Ningún test hace conexiones de red. Si lo hace → error de diseño.",
    "sin_bd":     "Ningún test conecta a Firebird. Usar datos de prueba en conftest.py.",
    "sin_ia":     "Ningún test llama a Qwen3. Usar mocks si es necesario.",
    "deterministicos": "Misma entrada → misma salida siempre.",
    "rapidos":    "Cada test < 100ms. Suite completa < 10s."
  },

  "datos_prueba": {
    "ubicacion": "tests/unit/conftest.py → fixtures de datos",
    "ejemplos": [
      "ARTICULOS_SAMPLE: lista de 50 artículos de prueba",
      "FACTURAS_SAMPLE: lista de 20 facturas de prueba",
      "CLIENTES_SAMPLE: lista de 10 clientes de prueba"
    ]
  },

  "ejecutar": ".venv/Scripts/pytest tests/unit/ -v -s",
  "cobertura": ".venv/Scripts/pytest tests/unit/ --cov=backend.modules.chat --cov-report=term"
}
```

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


## Integridad ampliada, solo consultas — 21/09/2026, versión 2026-09-21.4
Inventario PK/FK/UNIQUE en las 15 tablas de las 17 clases más OBRACAB (incluida en esas 15). Nuevos contrastes dinámicos por restricción: componentes nulos, grupos duplicados por clave completa, huérfanos no nulos y multiplicación de destinos de JOIN. No se unen entidades por nombres ni se reasignan registros. PK ausente, metadatos incompletos y errores de consulta quedan no verificables. NULL en UNIQUE/FK se informa separadamente; no se declara huérfano por un componente NULL.
Se añaden CHK-028/029/030 para proyecto solo en cabecera, solo en línea o ausente en ambas. La relación heredada sigue pendiente de regla de negocio; no se inventa una asignación.
El endpoint TXT abre una conexión Firebird READ COMMITTED READ ONLY, solo permite SELECT único, hace rollback y cierra incluso ante error. No es una instantánea común: cambios concurrentes siguen siendo una limitación declarada. Fallo de conexión devuelve 503, nunca un archivo de éxito aparente.
Browse acepta offset superior (no dentro de params), con orden estable para proyectos, recursos, proordutil y proordprev; otras clases rechazan offset positivo hasta validar orden completo. El Probador incluye posición inicial; cambiar clase, filtro o límite vuelve a cero. Páginas separadas no aseguran instantánea común.
Evidencia real: docs/informe_integridad_ampliada_2026_09_21.txt. Treinta checks de negocio: 18 correctos, 9 revisar, 3 no verificables. Estructura: 60 correctos, 19 informativos, 14 PK inventariadas, 20 no aplica y 1 no verificable (PK de PRESUPROYE); 21 checks de multiplicación de JOIN incluidos. Sin escrituras al ERP. El informe incluye SQL, conteos y ayudas; no certifica verdad del hecho ni comparación independiente con partes/ERP.
Pruebas nuevas ejecutan SQL real de los checks sobre SQLite sintético, comprueban ausencia de escrituras durante los checks, fallos y limpieza de conexión, mutación de segmento FK, destino duplicado y recorrido completo de páginas. Las tablas sintéticas de tests se crean solo en memoria. Se conserva un xfail de cobertura heredada desde cabecera, y siguen pendientes reglas de unidades/importes, fuentes independientes y paginación de otras clases.

Resultado final de esta ampliación: **232 passed, 1 xfailed**, una advertencia preexistente; **10 tests Node correctos**. El xfail sigue siendo una garantía no cumplida, no un éxito.
