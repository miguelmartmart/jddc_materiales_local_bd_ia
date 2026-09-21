# DEVIA — Modulo `api_clone`

> **Botón BD y contadores a cero:** [diagnóstico específico](../../../docs/DIAGNOSTICO_SELECTOR_PROYECTOS_Y_CEROS_2026_09_17.md).
> Lookup limitado a 15; CANTIDAD>0 excluye toda la MO con ESPREVISION=0 observada.

> **Auditoría 17/09/2026:** las afirmaciones históricas de equivalencia y fiabilidad
> absoluta de este módulo NO constituyen garantías. Hay claves compuestas mal
> resueltas, filtros omitidos y mezcla de previsiones. Ver
> [informe y evidencias](../../../docs/AUDITORIA_API_CLONE_FIABILIDAD_2026_09_17.md).

> **Utilidades de Ingeniería (17/09/2026):** ver [utilidades/DEVIA.MD](utilidades/DEVIA.MD)
> para las ocho consultas, contratos, pruebas y registro de continuidad.
## API Clone — Replica del API Explorer con SQL Firebird Directo

> **Ruta:** `backend/modules/api_clone/`
> **Version:** 1.0.0
> **Fecha:** 16/09/2026
> **Prefix API:** `/api/api-clone`
> **Frontend:** `frontend/assets/js/modules/api_clone.js`
> **View HTML:** `#view-api-clone` / `#api-clone-root`
> **Estado:** Implementado y funcional

---

## Que es API Clone

Replica **exactamente la semantica del API Explorer** (mismas clases, mismas operaciones:
browse/read/permiso/info/discover-all) pero en lugar de llamar a la API HTTP de mPYME
(Distrito K), ejecuta **SELECT SQL directo en Firebird** usando el mismo `FirebirdDriver`
del proyecto.

**CERO MOCKS.** Todos los valores son datos reales de la BD de produccion.

### Diferencia con API Explorer

| | API Explorer | API Clone |
|-|-------------|----------|
| Datos | API mPYME (mock o real) | SQL Firebird directo |
| Login | Requiere ssid1+ssid2 | No requiere login |
| Mocks | Si (MockApiClient) | No — siempre datos reales |
| Dependencia | API Distrito K activa | Solo Firebird accesible |

### Diferencia con BD Clone

| | BD Clone | API Clone |
|-|---------|---------|
| Interfaz | SQL libre generico | Clases/operaciones del API Explorer |
| Uso | Explorar cualquier tabla | Replicar comportamiento mPYME |

---

## Estructura

```
backend/modules/api_clone/
  __init__.py     vacío
  DEVIA.MD        este fichero
  queries.py      definicion de clases, tablas, columnas, filtros
  service.py      ApiCloneService — browse/read/permiso/info/discover-all
  router.py       11 endpoints FastAPI
  data/
    _history.json historial de operaciones (max 200)
    _matrix.json  matriz de estados por clase/operacion
```

---

## Clases disponibles (17)

| Clase API | Tabla Firebird | Columna PK | Filtro adicional |
|-----------|---------------|-----------|-----------------|
| proyectos | PROYECTOS | CODIGO | — |
| partidas | PRESUPROYE | CODPRESUPUESTO | — |
| proordutil | PREUTILLIN | CODIGO | — |
| proordprev | PREPREVLIN | CODIGO | — |
| reporden | REPARA | CODIGO | — |
| repordutil | RABUTILLIN | CODIGO | — |
| repobjetos | REPOBJETO | CODIGO | — |
| repinst | REPINSTALACION | CODIGO | — |
| tipostrabajo | TIPO | CODIGO | — |
| recursos | RECURSO | CODIGO | — |
| articulos | ARTICULO | CODIGO | — |
| proveedores | PROVEED | CODIGO | — |
| clientes | CLIENTE | CODIGO | — |
| docalbcom | DOCCAB | CODIGO | TIPO = 2 |
| docfaccom | DOCCAB | CODIGO | TIPO = 3 |
| docpedcom | DOCCAB | CODIGO | TIPO = 11 |
| ordenfab | FABCAB | CODIGO | — |

Fuente: `MAPA_FIREBIRD` de api_explorer/router.py + knowledge/tables/*.json

---

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/api/api-clone/status` | Estado y config |
| GET | `/api/api-clone/catalogue` | Catalogo de clases/ops |
| POST | `/api/api-clone/permiso` | Simula permiso() — conteo real |
| POST | `/api/api-clone/info` | Simula info() — columnas via RDB$ |
| POST | `/api/api-clone/browse` | Browse real: SELECT FIRST N |
| POST | `/api/api-clone/read` | Read real: SELECT por PK |
| POST | `/api/api-clone/discover-all` | Browse en todas las clases |
| GET | `/api/api-clone/history` | Historial |
| DELETE | `/api/api-clone/history` | Limpiar historial |
| GET | `/api/api-clone/matrix` | Matriz de estados |

---

## Como funciona browse

```sql
-- Ejemplo: browse("clientes", {}, 20)
SELECT FIRST 20 CODIGO, RAZONSOCIAL, NOMBRECOMERCIAL, TEL, CP
FROM CLIENTE
ORDER BY CODIGO

-- browse("docalbcom", {}, 20) — con filtro de TIPO
SELECT FIRST 20 CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL, CODCLIENTE
FROM DOCCAB
WHERE TIPO = 2
ORDER BY CODIGO

-- browse("partidas", {"codProyecto": "45871"}, 20)
SELECT FIRST 20 CODPRESUPUESTO, CODPROYECTO
FROM PRESUPROYE
WHERE CODPROYECTO = '45871'
ORDER BY CODPRESUPUESTO
```

---

## Principios DEVIA

- Sin datos sensibles en logs (historial guarda solo clase/operacion/ms)
- Persistencia atomica en data/ (JSON .tmp + replace)
- Degradacion elegante: errores devuelven {"error": "..."} no HTTP 500
- Patron de conexion identico a database/service.py y api_explorer/router.py
- Las tablas y columnas son las REALES verificadas en BD JDDC

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
