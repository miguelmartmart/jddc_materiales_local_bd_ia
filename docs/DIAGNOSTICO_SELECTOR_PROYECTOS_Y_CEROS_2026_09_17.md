# Diagnóstico: pocos proyectos en BD y cero técnicos/imputaciones

## Resultado

Hay dos causas distintas y comprobadas:

1. El botón BD solicita únicamente los primeros **15 proyectos por código**.
2. La consulta de horas elimina todas las líneas que no tienen **CANTIDAD > 0**.
   Los 15 proyectos ofrecidos tienen cero líneas de mano de obra que pasen ese filtro.

En Firebird hay **1.214 proyectos**. No es un catálogo de solo 15 proyectos ni
una limitación de licencia que se haya observado en este recorrido: el servicio
consulta directamente Firebird, no mPYME.

La captura mencionada no llegó a esta conversación. El diagnóstico corresponde
al código local y a su base configurada; no demuestra qué proyecto concreto
aparecía seleccionado en una captura ni qué versión sirve otro despliegue.

## Recorrido del botón

- `frontend/assets/js/modules/api_clone.js:389`: Utilidades manda
  `{campo: fk, limit: 15}` a `/api/api-clone/valores-campo`.
- `frontend/assets/js/modules/api_clone.js:660`: Probador manda también `limit: 15`.
- `backend/modules/api_clone/service.py:495`: `valores_campo` usa el mapa de proyectos
  y ejecuta `SELECT FIRST 15 CODIGO, NOMBRE FROM PROYECTOS ORDER BY CODIGO`.

Consecuencias:

- Ordenación del código textual, no por actualidad o relevancia: aparecen `1`, `10`,
  `1001301`, `1001302`, etc. No significa que sean las obras más recientes.
- No hay búsqueda por el nombre/código escrito, filtro por estado, siguiente página,
  ni contador «15 de 1.214» en esa respuesta.
- El selector de máximo de resultados de una utilidad NO cambia este límite de 15.
- El desplegable tiene altura máxima de 160 px en Utilidades y 180 px en Probador:
  es necesario desplazarlo para ver todos los 15; desplazarse no carga otros proyectos.
- 11 de esos 15 tienen FINOBRA=T; cuatro tienen F. Filtrar solo abiertos tampoco
  arreglaría los ceros: esos cuatro también carecen de CANTIDAD positiva de MO.

## Qué significan los dos ceros

`horas_por_tecnico` aplica a detalle y totales:

```sql
WHERE ol.TIPOBC3 = 10
  AND ol.CODPROYECTO = '<proyecto seleccionado>'
  AND ol.CANTIDAD > 0
```

Después calcula:

```sql
COUNT(DISTINCT ol.CODRECURSO) AS N_TECNICOS,
COUNT(ol.CODIGO) AS N_IMPUTACIONES
```

Por tanto, no cuenta todos los técnicos del maestro ni todas las líneas del
proyecto: cuenta solo los recursos distintos y líneas que sobreviven al filtro.
COUNT DISTINCT tampoco cuenta referencias nulas. Tener líneas, recursos informados,
horas realizadas y personal asignado son conceptos diferentes.

Cuando no sobrevive ninguna fila, COUNT devuelve 0 y SUM devuelve NULL. El servicio
devuelve `ok: true` porque la consulta se ejecutó; el frontend muestra «Datos reales
Firebird» y «Sin datos». Esto no demuestra que el proyecto no tenga actividad.

## Reproducción con datos reales

| Proyecto | Líneas totales | Líneas TIPOBC3=10 | Imputaciones que muestra la consulta | Técnicos que muestra |
|---|---:|---:|---:|---:|
| 1 | 10 | 0 | 0 | 0 |
| 10 | 2.511 | 2.507 | 0 | 0 |
| 1001301 | 4 | 3 | 0 | 0 |
| 1001674 | 21 | 13 | 0 | 0 |

Todos los primeros 15 terminan en cero. Se ejecutó también el servicio existente
`horas_por_tecnico('1')` sobre la conexión real: devolvió éxito, ningún técnico,
N_TECNICOS=0, N_IMPUTACIONES=0 y sumas nulas. No se fabricaron respuestas.

## La causa de fondo: el campo usado no sostiene la métrica presentada

Distribución de mano de obra con proyecto informado y ESPREVISION=0:

- **14.062 líneas**.
- En **las 14.062, CANTIDAD=0**; no son valores NULL ni cantidades negativas.
- **8.890 líneas tienen CODRECURSO informado** (no son 8.890 técnicos distintos).
- **13.554 tienen CANTIDADREALDOCLIN>0**.
- **14.062 tienen CANTIDADPADRE>0**.

En toda la población TIPOBC3=10, ESPREVISION=0, incluso sin proyecto informado,
el diagnóstico encontró CANTIDAD=0. El problema no se resuelve eligiendo otra
obra si se mantienen ese campo, ese filtro y el requisito de ejecución real.

La distribución global devuelve **1.187 proyectos con líneas**, pero solo **seis**
con mano de obra de CANTIDAD positiva. Ninguno tiene esa mano de obra con ESPREVISION=0.

| Proyecto | Líneas que pasan el filtro | Recursos distintos | ESPREVISION | FINOBRA |
|---|---:|---:|---|---|
| 45160.2 | 1 | 1 | 1 | T |
| 45215 | 1.677 | 20 | 1 | T |
| 46019 | 2 | 1 | 1 | T |
| 46215 | 53 | 4 | 1 | T |
| 47914 | 2 | 2 | 1 | T |
| 48231 | 2 | 2 | 1 | T |

El control positivo ejecutó `horas_por_tecnico('45160.2')`: un recurso y una línea.
Demuestra que el mismo servicio sí devuelve resultados cuando se cumple su filtro.
No demuestra que esas cifras sean horas ejecutadas: corresponden a ESPREVISION=1.
El ejemplo estático del proyecto 45215 que aparece en la interfaz es por ello
especialmente engañoso como demostración de imputaciones reales.

## Qué falta demostrar antes de corregir el cálculo

CANTIDAD, CANTIDADPADRE y CANTIDADREALDOCLIN contienen datos distintos. No basta
con sustituir uno por otro ni con eliminar `CANTIDAD>0` para obtener horas correctas.
La metadata consultada no contiene descripción ni expresión de columna calculada
para esos campos. Esto no descarta lógica en triggers, procedimientos o el ERP.

Hay que contrastar un parte/informe conocido de SQL Obras con sus líneas y fijar:

- qué campo representa horas/unidades realizadas y cuál cantidades heredadas o de documento;
- qué conversiones de unidad y relaciones de líneas padre/hijo deben aplicarse;
- cómo se excluyen previsiones y se conservan ajustes negativos;
- cómo se vincula la actividad al proyecto sin atribuirle registros sin relación;
- si «técnicos» significa asignados, con líneas registradas o con horas realizadas.

Sin ese contraste, cambiar el campo podría sustituir un cero explicable por una
cifra positiva incorrecta. El diagnóstico no ha modificado la consulta de negocio.

## Cambios propuestos

1. Selector buscable por código/nombre, paginación y total visible. Mostrar FINOBRA
   y ofrecer filtros explícitos para histórico/operativa, sin ocultar obras arbitrariamente.
2. Mostrar «líneas registradas», «líneas con cantidad válida» y «recursos identificados»
   por separado, con el motivo de exclusión. No rotular un conjunto filtrado como toda actividad.
3. Mensaje útil cuando existe actividad pero el campo de cantidad consultado es cero.
4. Separación visible y obligatoria de ejecución/previsión; retirar ejemplos estáticos de fiabilidad.
5. Elegir y validar la fórmula de horas con un oráculo ERP antes de mostrar horas reales.

Pruebas de aceptación: selector con más de 15 proyectos y búsqueda fuera de la
primera página; proyecto existente sin líneas; líneas solo materiales; MO con
cantidad cero/nula/negativa/positiva; referencias de recurso nulas; previsiones
sin ejecución; proyecto cerrado; conciliación contra horas de un informe ERP.

## Archivos y alcance de la comprobación

- [Evidencia JSON](diagnostico_lookup_proyectos_2026_09_17.json): datos sin nombres
  personales, contadores, códigos, metadata y resultados reales de los servicios.
- [Script reproducible](../scripts/diagnosticar_lookup_proyectos.py): Firebird
  READ_COMMITTED_RO, SELECT exclusivamente, sin persistir historial del API.
- [Auditoría general](AUDITORIA_API_CLONE_FIABILIDAD_2026_09_17.md): problemas
  adicionales de claves, estados, previsiones y exhaustividad.

Las consultas no comparten un snapshot inmutable y las cifras corresponden al
timestamp del JSON. Se observó actividad concurrente entre ejecuciones; no usar
los contadores como constantes del producto. La última ejecución terminó sin errores.

## Corrección de técnicos y selector — 17/09/2026

La utilidad «Técnicos y actividad registrada» reemplaza la interpretación anterior de horas. `project_activity.py` consulta recursos vinculados mediante CODPROYECTO, incluye líneas con CANTIDAD=0 y separa ESPREVISION=0/1. La respuesta contiene `actividad`, `tecnicos`, `grupos` y `horas_verificadas: false`; no devuelve los antiguos totales de horas/costes como si estuvieran certificados. Los grupos incluyen explicaciones desplegables. Esto no certifica que cada recurso haya trabajado ni resuelve los demás hallazgos de auditoría.

El selector BD de Utilidades incorpora búsqueda por código/nombre y páginas de 15 mediante GET `/proyectos-buscar`. El selector antiguo del Probador no forma parte de esta corrección.

Validación directa de solo lectura en Firebird: 1214 proyectos; búsqueda y páginas disjuntas comprobadas. Proyecto 1001331: existe, sin líneas OBRALIN directamente vinculadas. Proyecto 10: 6 recursos, 2507 líneas MO previstas. Proyecto 45215: 26 recursos, 6490 líneas MO (72 no previstas y 6418 previstas), 66 sin código de recurso. Evidencia: `docs/validacion_actividad_proyectos_2026_09_17.json`; reproducción: `scripts/verificar_actividad_proyectos.py`.

Pruebas: utilidades + auditoría + selector + checks agrupados: 70 passed, 11 xfailed (hallazgos pendientes), una advertencia preexistente. Interfaz Node: 6 passed; comprobación sintáctica JS correcta. El caso AUD10 queda mitigado para esta utilidad al dejar de presentar previsiones como horas verificadas; no para las demás consultas.

Despliegue local pendiente: el servidor Python PID 19320 en puerto 8001 sigue con el backend anterior. El script `scripts/recargar_backend_api_clone.ps1` verifica que sirve el JS de este directorio y que existe un único listener Python antes de intentar reiniciarlo. Windows denegó Stop-Process incluso fuera del sandbox; no se detuvo el servidor. Es necesario reiniciarlo desde la sesión con permisos que lo inició y recargar el navegador. No se verificó el nuevo endpoint por HTTP en ese proceso.

### Verificación HTTP y caché — 17/09/2026
El servidor 8001 ya carga el endpoint proyectos-buscar y la respuesta actividad. Verificado por HTTP: proyecto 10 devuelve 6 recursos y 2507 líneas MO; 45215 devuelve 26 recursos y 6490 líneas MO. Queda superada la nota anterior de backend pendiente de reinicio. Se actualiza en frontend/index.html la versión de api_clone.js a 20260917-activity-2 para descargar el renderizador nuevo al recargar. HTML y JS servidos comprobados por HTTP; no se ha inspeccionado la pestaña del usuario. No confundir líneas (incluidas previsiones) con imputaciones reales certificadas.
