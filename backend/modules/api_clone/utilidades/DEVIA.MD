# DEVIA — Utilidades de Ingeniería

> **Ceros en horas/técnicos:** ver [diagnóstico real](../../../../docs/DIAGNOSTICO_SELECTOR_PROYECTOS_Y_CEROS_2026_09_17.md).
> No confundir ausencia de CANTIDAD positiva con ausencia de líneas o recursos.

> **Auditoría posterior 17/09/2026:** los tests iniciales no certifican fiabilidad
> de negocio. Se detectaron mezcla de previsiones, poblaciones distintas en totales
> y un check que ignora NULL. Ver [informe](../../../../docs/AUDITORIA_API_CLONE_FIABILIDAD_2026_09_17.md).

## Estado y alcance (17/09/2026)

Última validación de checks agrupados contra Firebird, solo lectura: **5 correctos,
5 para revisar y 3 no verificables**. Evidencia en `docs/checks_agrupados_2026_09_17.json`;
vista previa navegable con ayudas en `docs/checks_agrupados_vista_previa.html`.
Pruebas: 63 Python específicas aprobadas, 72 previas API/BD Clone aprobadas,
4 Node aprobadas; 12 xfail de la auditoría aún pendientes.

Ocho consultas de lectura sobre OBRALIN, PROYECTOS y RECURSO, disponibles
en API Clone → Utilidades. No requieren IA ni API mPYME.

- `service.py`: horas por técnico, resumen de costes, top proyectos, ranking
  de técnicos, proyectos de técnico, materiales y evolución mensual. Delega la
  verificación global en `check_runner.py`. Cada consulta cierra su conexión incluso si falla.
- `check_catalog.py`: 13 checks organizados en seis grupos. Cada check contiene
  explicación, ejemplo y acción recomendada. Diez consultas y tres límites explícitos
  aún no verificables (elegibilidad, separación real/previsión y conciliación completa).
- `check_runner.py`: cuatro estados `correcto`, `revisar`, `no_verificable`,
  `no_aplica`; cuenta población e incidencias en el mismo SELECT. Sin población →
  no aplica; error/contador ausente → no verificable. Nunca certifica el sistema entero.
- `router.py`: prefijo `/api/api-clone/utilidades`, registrado en `backend/main.py`.
  Cinco POST por proyecto/técnico, tres GET de análisis y GET `/catalogo`.
  Los POST admiten límites de 1 a 100; top proyectos hasta 50 y ranking hasta 100.
  El código de proyecto se recorta y no puede estar vacío.
- `frontend/assets/js/modules/api_clone.js`: selección, formularios, búsqueda
  de proyectos, tablas y desglose de resultados.

## Contratos y limitaciones

`ok` indica construcción del informe; en coherencia, consultar `resumen`,
`grupos` y `estado_codigo` de cada check. `n_ok` cuenta correctos y `n_falla`
solo los que requieren revisión; no incluye desconocidos ni no aplicables.
Se conserva `checks` plano para consumidores anteriores. El endpoint síncrono usa
el pool de FastAPI, evitando bloquear el bucle asíncrono durante las consultas.
Un contador ausente o nulo se considera error,
nunca prueba de integridad. Un proyecto inexistente devuelve `ok: false`.
Los Decimal de Firebird se serializan como números redondeados a cuatro decimales.
`pct_margen` mantiene la fórmula existente: (precio - coste) / coste × 100.

Los datos y badges que citan 16/09/2026 son referencias de la implementación
anterior, no una comprobación actual. La implementación inicial no verificó producción;
la validación posterior de los checks agrupados se registra arriba.
Los checks son indicadores: sus incidencias requieren interpretación de negocio.

La interfaz presenta ayudas con `<details>/<summary>`, ejemplos y acciones en
lenguaje sencillo; SQL en detalle técnico opcional y textos escapados. Muestra
alcance global y fecha UTC. No existe filtro por proyecto para esta verificación.
Las respuestas atrasadas de utilidades se descartan al cambiar selección/parámetros.

Pruebas nuevas: `tests/unit/test_api_clone_grouped_checks.py`, caso HTTP en
`test_api_clone_utilidades.py` y `test_api_clone_checks_ui.cjs` (Node).
`scripts/verificar_checks_agrupados.py` permite comprobación real de solo lectura,
con informe en `docs/checks_agrupados_2026_09_17.json`.

## Validación y limpieza

Desde `bots/interjddcia`:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_api_clone_utilidades.py tests/unit/test_api_clone_bd_clone.py -q
```

Resultado 17/09/2026: **104 passed** (32 nuevos + 72 existentes), con una
advertencia preexistente de Pydantic. Los tests nuevos aíslan el driver y
prueban las rutas con FastAPI TestClient, sin conexiones de red ni BD.

`scripts/limpiar_exploracion_utilidades.ps1` muestra por defecto los tres
`_explore_utilidades*.py` concretos. `-Aplicar` los mueve a una carpeta única
en `archives/utilidades/`, sin borrarlos. Admite `-WhatIf`, valida rutas y
rechaza enlaces. No modifica datos, historial, configuración ni otros scripts.

## Registro de progreso

| Fecha | Avance |
|---|---|
| 17/09/2026 | Retomada conversación de Cline: añadidos tests específicos y script de limpieza; corregidos límites POST, proyectos inexistentes, contadores ausentes y serialización Decimal. Pendiente validación real en navegador y Firebird. |

Documentación padre: `backend/modules/api_clone/DEVIA.MD`.

## Corrección de técnicos y selector — 17/09/2026

La utilidad «Técnicos y actividad registrada» reemplaza la interpretación anterior de horas. `project_activity.py` consulta recursos vinculados mediante CODPROYECTO, incluye líneas con CANTIDAD=0 y separa ESPREVISION=0/1. La respuesta contiene `actividad`, `tecnicos`, `grupos` y `horas_verificadas: false`; no devuelve los antiguos totales de horas/costes como si estuvieran certificados. Los grupos incluyen explicaciones desplegables. Esto no certifica que cada recurso haya trabajado ni resuelve los demás hallazgos de auditoría.

El selector BD de Utilidades incorpora búsqueda por código/nombre y páginas de 15 mediante GET `/proyectos-buscar`. El selector antiguo del Probador no forma parte de esta corrección.

Validación directa de solo lectura en Firebird: 1214 proyectos; búsqueda y páginas disjuntas comprobadas. Proyecto 1001331: existe, sin líneas OBRALIN directamente vinculadas. Proyecto 10: 6 recursos, 2507 líneas MO previstas. Proyecto 45215: 26 recursos, 6490 líneas MO (72 no previstas y 6418 previstas), 66 sin código de recurso. Evidencia: `docs/validacion_actividad_proyectos_2026_09_17.json`; reproducción: `scripts/verificar_actividad_proyectos.py`.

Pruebas: utilidades + auditoría + selector + checks agrupados: 70 passed, 11 xfailed (hallazgos pendientes), una advertencia preexistente. Interfaz Node: 6 passed; comprobación sintáctica JS correcta. El caso AUD10 queda mitigado para esta utilidad al dejar de presentar previsiones como horas verificadas; no para las demás consultas.

Despliegue local pendiente: el servidor Python PID 19320 en puerto 8001 sigue con el backend anterior. El script `scripts/recargar_backend_api_clone.ps1` verifica que sirve el JS de este directorio y que existe un único listener Python antes de intentar reiniciarlo. Windows denegó Stop-Process incluso fuera del sandbox; no se detuvo el servidor. Es necesario reiniciarlo desde la sesión con permisos que lo inició y recargar el navegador. No se verificó el nuevo endpoint por HTTP en ese proceso.

### Verificación HTTP y caché — 17/09/2026
El servidor 8001 ya carga el endpoint proyectos-buscar y la respuesta actividad. Verificado por HTTP: proyecto 10 devuelve 6 recursos y 2507 líneas MO; 45215 devuelve 26 recursos y 6490 líneas MO. Queda superada la nota anterior de backend pendiente de reinicio. Se actualiza en frontend/index.html la versión de api_clone.js a 20260917-activity-2 para descargar el renderizador nuevo al recargar. HTML y JS servidos comprobados por HTTP; no se ha inspeccionado la pestaña del usuario. No confundir líneas (incluidas previsiones) con imputaciones reales certificadas.


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
