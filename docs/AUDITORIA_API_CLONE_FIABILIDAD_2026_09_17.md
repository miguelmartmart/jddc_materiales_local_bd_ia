# Auditoría de fiabilidad de API Clone — 17/09/2026

> Avance posterior: implementados 13 checks en seis grupos con ayuda y cuatro
> estados. Corregido AUD-09 (NULL no pasa inadvertido); la suite adversarial actual
> tiene 16 passed y 12 xfailed. Los resultados y hashes del informe original
> describen el código anterior. Las demás correcciones del API siguen pendientes.

## Dictamen

**No es justificable afirmar que API Clone es «100 % fiable» o equivalente a mPYME.**
Consulta Firebird real, pero identidad, alcance, significado de las clases,
estado operativo y exhaustividad no están garantizados. Se han reproducido
defectos con SQL ejecutado y comprobado claves y distribuciones en producción.

Este trabajo audita el estado existente; no cambia el comportamiento del API.
No se ejecutaron escrituras en Firebird ni activaciones de escritura del API.
Los tests anteriores (104 aprobados) validaban contratos parciales; no certificaban
pertenencia, ciclo de vida o equivalencia con SQL Obras.

## Evidencias y cómo reproducirlas

- [Evidencia real JSON](auditoria_api_clone_2026_09_17_evidencias.json): columnas,
  restricciones PK/UNIQUE/FK, distribuciones y contadores, SQL, timestamps UTC
  y SHA256 del código auditado. Sin nombres, documentos completos ni credenciales.
- [Auditor de lectura](../scripts/auditar_api_clone_lectura.py): usa la conexión
  configurada en DEVIA con transacción `READ_COMMITTED_RO` y timeout de 20 s.
- [Tests adversariales](../tests/unit/test_api_clone_fiabilidad_audit.py): 28 casos,
  SQL del servicio ejecutado en SQLite sobre datos sintéticos explícitos.
- [Salida sin xfail](auditoria_api_clone_2026_09_17_tests.txt): **15 passed, 13 failed**.
  Ejecución normal: 15 passed y 13 xfailed estrictos. Los xfailed documentan
  garantías incumplidas; NO significan que el sistema sea correcto.

```powershell
# Desde bots/interjddcia. Primera orden: conexión real LAN, solo lectura.
.venv\Scripts\python.exe scripts/auditar_api_clone_lectura.py --contadores
# Segunda orden: sin red/Firebird; muestra los fallos conocidos como fallos.
.venv\Scripts\python.exe -m pytest tests/unit/test_api_clone_fiabilidad_audit.py --runxfail -q --tb=short
```

Límites: los SELECT de producción no comparten un snapshot de toda la auditoría;
son observaciones sucesivas. SQLite no demuestra collation, coerciones ni aislamiento
Firebird. No se contrastó con una sesión operativa mPYME, sus permisos o su interfaz.
El script vuelve a generar el JSON de esta sesión; archivar cada ejecución para
conservar evidencias históricas. La fecha de la evidencia prevalece sobre badges.

La reproducción A→B de `read` se ejecutó en el test sintético. Una comprobación
adicional para seleccionar un caso y ejecutar ese método en producción terminó
con un error de protocolo Firebird al cerrar la conexión; no se presenta como
prueba real completada. Las claves y los 944 códigos ambiguos sí se comprobaron
mediante SELECT independientes incluidos en la evidencia final.

## Hallazgos prioritarios

| ID | Gravedad | Hallazgo y consecuencia | Evidencia |
|---|---|---|---|
| AUD-01 | Crítica | `codProyecto="   "` supera `browse` y `_where` elimina el filtro. Devuelve datos globales en clases que exigen proyecto. | Test HTTP con SQL ejecutado; service.py:110 y :248 |
| AUD-02 | Alta | Parámetros desconocidos se ignoran. `recursos` o `docalbcom` con `codProyecto=A` siguen siendo catálogos globales. Deben rechazar el filtro o aplicarlo. | Dos contraejemplos; PARAM_A_COLUMNA |
| AUD-03 | Crítica | OBRALIN tiene PK `(CODCAB,CODIGO)`; `read` usa solo `CODIGO` y toma `rows[0]`. Puede devolver la línea de otro proyecto. | RDB$: PK compuesta; 6.401 códigos repetidos, 944 con varios proyectos no nulos; contraejemplo A→B |
| AUD-04 | Crítica | `proordutil` y `proordprev` generan el mismo SQL. No filtran ESPREVISION. | CLASE_WHERE y tests; producción contiene ambos valores |
| AUD-05 | Alta, escenario preventivo | No existe regla de resolución o rechazo para discrepancias línea/cabecera o proyecto nulo en línea. El servicio solo mira OBRALIN.CODPROYECTO. | Caso sintético falla; no observado el caso «nulo en línea con proyecto en cabecera» en producción |
| AUD-06 | Alta | No hay política de proyectos operativos. Un filtro FINOBRA se ignora. Se incluyen proyectos cerrados. | 1.058 FINOBRA=T, 156 FINOBRA=F; test |
| AUD-07 | Alta | `browse/read(proyectos)` omiten FINOBRA, aunque existe. El consumidor no puede conocer ese estado con esas respuestas. | Proyecciones CLASE_COLS_*; test |
| AUD-08 | Alta | `FIRST N` devuelve una muestra; no hay cursor/offset. Repetir no permite recorrer todo. ORDER BY CODIGO no es único en varias clases. | Test; SQL y modelos de petición |
| AUD-09 | Alta | CHK-001 usa COUNT(DISTINCT CODPROYECTO), que ignora NULL. Un resultado cero no cubre filas sin proyecto. | 676.376 NULL reales; test |
| AUD-10 | Alta | Las utilidades no separan ESPREVISION; sus «horas/costes reales» mezclan previsión con ejecución. | 216.684 previsiones con proyecto; test de horas |
| AUD-11 | Alta | Resumen, ranking y evolución usan distintas poblaciones: todo, COSTE>0 o CANTIDAD>0. Los ajustes negativos pueden desaparecer de unos totales. | Test de conciliación; 98 costes y 18.618 cantidades negativas |
| AUD-12 | Alta | `ReadRequest` solo admite clase/objectid; Pydantic descarta un codProyecto extra. No existe verificación de pertenencia en lectura individual. | Test HTTP |

## Identidad y relaciones por clase

| Clase | Lo que hace realmente | Garantía pendiente |
|---|---|---|
| proyectos | PK CODIGO directa, catálogo sin filtro de vigencia | FINOBRA, fechas, permiso operativo y estados externos |
| partidas | Lee PRESUPROYE, enlace proyecto-presupuesto | No demuestra que sean partidas. Solo tiene CODPROYECTO, CODPROYSUBCONTRATA y CODPRESUPUESTO; FK del presupuesto a DOCCAB. Su restricción «PRESUPROYE_PK» es UNIQUE de tres columnas, no PK individual de CODPRESUPUESTO |
| proordutil / proordprev | Misma tabla y mismo predicado | PK compuesta, discriminador real/previsión, regla línea/cabecera |
| reporden | Lee REPARA por CODIGO; ignora proyecto | REPARA sí tiene CODPROYECTO, CODESTADO, ESTADOCIERRE y fechas; faltan alcance y elegibilidad |
| repordutil | Lee REPCAR filtrada por CODREPARA | PK de cuatro columnas; su esquema es de características, no prueba de horas/materiales. REPLIN existe con campos de recursos, coste, cantidad y fechas; es candidato a investigar, no reemplazo ya validado |
| recursos | Catálogo RECURSO | Ser recurso existente no implica haber trabajado ni estar asignado al proyecto. FECHAALTA/FECHABAJA existen y no se exponen ni filtran |
| articulos | Catálogo ARTICULO | Consumo real y pertenencia deben salir de líneas/imputaciones, no del catálogo. BAJA existe, con 153 artículos T |
| proveedores / clientes | Maestros globales | Coincidencia de cliente/proveedor no prueba pertenencia de un documento al proyecto |
| docalbcom / docfaccom / docpedcom | DOCCAB con TIPO 2/3/11 | El tipo se conserva en browse/read, pero no hay vínculo por proyecto. Hay vínculo de cabecera y DOCLINIMPUTACION: un documento puede repartirse y no se debe atribuir el importe completo a cada proyecto |
| repobjetos / repinst | Maestros de equipos/instalaciones | Requieren camino relacional validado a proyecto; el cliente común no basta |
| tipostrabajo | Toda TIPO sin discriminador de familia | PK real `(TIPO,CODIGO)`, no CODIGO único. No está demostrado que todo TIPO sea tipo de trabajo |
| ordenfab | FABCAB por CODIGO | PK real `(CODMAESTRO,ESPREVISION,CODIGO)`; identidad incompleta |

Las FK comprobadas para OBRALIN son CODCAB→OBRACAB y CODREPARA→REPARA.
**No hay FK declarada OBRALIN.CODPROYECTO→PROYECTOS ni CODRECURSO→RECURSO.**
OBRACAB sí tiene FK a PROYECTOS. No equivale a exigir que el proyecto copiado
en cada línea sea igual al de la cabecera. Hoy se observaron cero discrepancias
no nulas entre ambos; eso es una evidencia de datos, no una restricción futura.

Una FK garantiza existencia del destino según su definición, no que un operario
haya elegido la obra correcta. Incluso una asociación equivocada A→B satisface
una FK si B existe. [Referencia oficial Firebird](https://www.firebirdsql.org/file/documentation/chunk/en/refdocs/fblangref25/fblangref25-ddl-tbl.html).

## Producción: qué se observó y qué NO se deduce

| Comprobación | Resultado | Interpretación |
|---|---:|---|
| Proyectos | 1.214 | 156 F y 1.058 T en FINOBRA. F no demuestra ausencia de bloqueos externos |
| OBRALIN | 942.592 | 725.608 ESPREVISION=0 y 216.984 ESPREVISION=1 |
| OBRALIN con proyecto | 266.216 | 49.532 ESPREVISION=0 y 216.684 ESPREVISION=1 |
| Proyecto nulo en línea | 676.376 | Ninguna se recuperó con proyecto de cabecera; no atribuirlas ni llamarlas «costes perdidos de proyectos» sin investigar origen |
| Proyecto no nulo sin maestro | 0 | Pasa existencia para esa población, no todos los controles |
| Mano de obra con recurso no nulo inexistente | 0 | No demuestra asignación correcta, baja ni fechas |
| Línea/cabecera: proyecto no nulo diferente | 0 | Observación actual; la FK no impone esa igualdad |
| Línea/cabecera: ESPREVISION diferente | 0 | Coherencia observada del discriminador |
| DOCLINIMPUTACION con proyecto no nulo inexistente | 10 | Revisar significado/códigos y origen. Fuera de los seis checks actuales |
| Proyectos con fin anterior al inicio | 0 | No certifica fechas de imputación |
| Líneas sin FECHA | 264.596 | 4.376 tienen cabecera fechada; un fallback necesita regla de negocio |
| Líneas antes del inicio de proyecto | 22.494 | No son automáticamente errores: puede haber preparación u otras fechas de referencia |
| Líneas después del fin de proyecto | 1.443 | Puede ser ajuste, registro tardío o error; hace falta clasificar |
| Líneas con fecha futura | 1 | Evaluar junto a previsión y fecha de corte del servidor |
| Fechas línea/cabecera distintas | 41.222 | Pueden representar hechos diferentes; no imponer igualdad automáticamente |
| Líneas enlazadas a FINOBRA=T | 194.941 | No significa que se registraran después del cierre: no hay timestamp de cierre auditado |
| Recursos con baja anterior/igual a hoy | 0 | El API tampoco protege el caso cuando aparezca |
| Artículos BAJA=T | 153 | Actualmente presentes y no excluidos del catálogo |

Los contadores pueden solaparse. Las comparaciones de fecha solo evalúan filas
con operandos no nulos; no son una evaluación completa de todos los históricos.
Las cifras son de la ejecución cuya fecha consta en JSON, no constantes del producto.

## Estados: operativa e histórico requieren contratos distintos

Hipótesis de diseño para esta auditoría: separar consultas operativas e históricas.
No se ha confirmado una lista oficial de estados válidos en esta instalación.

- **Histórico**: conservar cerrados/bajas si participaron, mostrando estado y fecha
  de corte. Ocultarlos alteraría costes, trazabilidad y conciliación.
- **Operativa**: permitir únicamente proyectos/recursos que cumplen reglas positivas
  de elegibilidad en la fecha de operación, con motivos de exclusión.
- **Desconocido**: estado nulo, nuevo o no mapeado se trata como indeterminado;
  no asumir «activo». Bloquear nuevas imputaciones hasta resolverlo si ese es el contrato.
- **Borrador, bloqueado, cancelado, archivado, suspendido, reabierto**: no se encontró
  en PROYECTOS una columna que por sí sola modele todos esos estados. Pueden depender
  de documentos, configuración, permisos o lógica ERP. FINOBRA=F no los descarta.
- **«Pasado»**: diferenciar fecha planificada vencida, fin real, cierre administrativo,
  ejercicio contable cerrado y ventana permitida de imputación.
- REPARA presenta varios CODESTADO y ESTADOCIERRE 0/1. Un mismo CODESTADO aparece
  con ambos cierres. No reducir el ciclo de vida a un único código sin catálogo oficial.

## Importes, fechas y coherencia temporal

`SUM(COSTE)` y `SUM(PRECIO)` no demuestran que se esté calculando el importe
económico correcto. Falta validar si son importes unitarios o extendidos, factores
de unidad, descuentos, indirectos, jerarquía de líneas/porcentuales, subcontratas,
orígenes de documento y reglas de duplicación. No cambiar a COSTE*CANTIDAD a ciegas.

`AVG(COSTE/CANTIDAD)` es media por línea, no coste/hora ponderado. Si el contrato
es coste total dividido entre horas totales, las fórmulas divergen. El porcentaje
de margen actual divide por coste; debe explicitarse frente al margen sobre venta.
Los cálculos usan float y redondean: una certificación monetaria debe fijar escala
Decimal, reglas de redondeo y tolerancias aprobadas.

FECHA, FECHAALTA, FECHAINICIO, FECHAFIN y fechas de cabecera no son intercambiables.
Definir fecha de realización frente a registro, planificación y contabilización;
zona horaria, límites inclusivos, fin de día, DST y correcciones retroactivas.

El driver instalado usa READ_COMMITTED por defecto. Browse y COUNT pueden observar
distintos commits; las utilidades abren conexiones separadas para detalle, total y
proyecto. El autoreconnect puede cambiar la vista. Para certificar un informe se
necesita una misma transacción snapshot o una copia inmutable con versión explícita.
[Aislamiento en Firebird](https://www.firebirdsql.org/file/documentation/chunk/en/refdocs/fblangref25/fblangref25-transacs.html).

## Casuísticas de la batería de certificación propuesta

| Familia | Casos mínimos | Oráculo / resultado requerido |
|---|---|---|
| Parámetros | ausente, vacío, espacios, 0, False, lista, objeto, tipo erróneo, nombre desconocido | Error explícito, nunca consulta global accidental |
| Identidad | misma línea en dos cabeceras, mismo código en familias, empresa/ejercicio distintos | Clave completa y ámbito; exactamente un resultado o error |
| Textos | apóstrofes, guiones, ceros iniciales, espacios finales, mayúsculas y acentos | Semántica acorde al dominio/collation real; prueba en Firebird |
| Pertenencia | A/B con mismo cliente, técnico compartido, línea reasignada, cabecera discrepante | Ningún elemento fuera de la relación aprobada |
| Completitud | 0, 1, N-1, N, N+1 registros; múltiples páginas, empates de orden | Diferencia de conjuntos vacía, sin duplicados, cursor estable |
| Previsión | 0, 1, NULL, valor nuevo; conversión previsión→ejecución | Conjuntos separados o error indeterminado; no doble contabilización |
| Estado proyecto | abierto, cerrado, borrador, bloqueado, anulado, reabierto, desconocido | Reglas distintas para histórico/operativa |
| Estado recurso | baja antes/durante/después, alta futura, asignado sin imputación | Vigencia por fecha; diferenciar participación de asignación |
| Relaciones múltiples | subcontrata, presupuesto revisado, partida reutilizada, documento repartido | Identidad contextual; sumar solo asignación correspondiente |
| Reparaciones | mismo cliente, otra instalación, orden cerrada, origen documental | Vínculos explícitos, no inferir pertenencia por cliente |
| Fechas | NULL, antes/después, futura, registro tardío, cambio horario, reapertura | Política por fecha de negocio y de corte |
| Dinero | negativos, ceros, nulos, abonos, unidades mixtas, redondeo, padres/hijos | Conciliación de importe y unidades con informe ERP independiente |
| Integridad | huérfano, NULL, FK ausente, duplicado lógico, maestro borrado | Contadores separados y estado desconocido visible |
| Concurrencia | inserción/borrado/reasignación/cierre entre páginas, timeout/reconexión | Snapshot consistente o resultado invalidado, sin éxito parcial |
| Autorización | usuario ajeno, cambio de sesión, empresa/ejercicio, sesión escritura | Permisos por identidad/contexto, no flags globales |
| Presentación | respuesta antigua tras cambiar proyecto, solicitudes simultáneas, HTML en texto | Resultado ligado a petición y contexto; escapar HTML |
| Oracle ERP | iguales versión, empresa, ejercicio, usuario, fecha y filtros | Igualdad de claves y valores contra informe/API oficial no basado en el mismo SQL |

Los 28 tests añadidos cubren parte de esta matriz. No afirmar que el resto está
implementado o que un test sintético demuestra la distribución de producción.

## Otros riesgos relevantes para fiabilidad

- `permiso()` cuenta filas; no verifica permisos/licencia ni equivalencia con mPYME.
- `discover_all()` usa consultas globales sin parámetros; el total suma tablas/clases
  que se solapan. No es un número de recursos únicos del proyecto.
- `imputaPro`, `imputaRep` e `imputaFab` usan la misma inserción con CODPROYECTO.
  No valida el destino por acción, pertenencia de partida, estado ni fecha. No se
  probó ninguna escritura real. Requiere revisión antes de considerarse paridad ERP.
- `write()` hace INSERT directo; no reproduce automáticamente reglas de negocio del ERP.
  Los flags y temporales de escritura pertenecen al singleton del proceso, no a un usuario.
- `_log()` guarda params y data, contradiciendo el DEVIA antiguo que dice «solo
  clase/operación/ms». El historial no es un certificado inmutable de auditoría.
- En frontend hay interpolación de datos en innerHTML y resultados asincrónicos sin
  comprobar que siga seleccionado el mismo proyecto/utilidad. Una respuesta atrasada
  puede mostrarse bajo otro contexto aunque el WHERE original fuera correcto.
- Los textos FIABILIDAD_CLASE y badges «100 %», «FK garantiza», «6/6» están escritos
  estáticamente; no proceden de una evaluación actual. Deben sustituirse por alcance,
  fecha y resultado de comprobaciones verificables.

## Qué significa una demostración defendible

Para una copia/snapshot S, proyecto P y política versionada R:

1. **Identidad:** cada elemento tiene una clave completa única.
2. **Aislamiento:** devueltos(P,S,R) − esperados(P,S,R) = vacío.
3. **Completitud:** esperados(P,S,R) − devueltos(P,S,R) = vacío.
4. **Valores:** estados, fechas y magnitudes coinciden con un oráculo independiente.
5. **Elegibilidad:** los operativos satisfacen R; los históricos mantienen su trazabilidad.
6. **Integridad del certificado:** versión de código/esquema/política, snapshot, filtros,
   número de filas, hashes, diferencias, incidencias y pruebas ejecutadas quedan registrados.

La igualdad de conteos o sumas por sí sola no basta: una fila A puede sustituirse
por B conservando ambos. Comparar claves completas y después valores por clave.
Un hash detecta cambios, pero no demuestra semántica correcta.

Sí se puede comprobar el **100 % de una población finita definida** en ese snapshot,
o demostrar formalmente propiedades del código bajo supuestos explícitos. No se
puede prometer que todos los datos introducidos por humanos sean correctos para
siempre ni equivalencia con reglas ERP desconocidas mediante tests finitos.

## Orden recomendado de remediación y aceptación

1. Retirar garantías absolutas; rechazar filtros desconocidos/vacíos y claves ambiguas.
2. Validar con SQL Obras/Distrito K las clases partidas/repordutil/tipostrabajo y estados.
3. Claves compuestas, ámbito obligatorio y discriminador real/previsión explícito.
4. Definir histórico/operativa y reglas de estados/fechas/importe; no ocultar cerrados globalmente.
5. Paginación estable, snapshot común, conciliación de detalle/totales y control de errores.
6. Convertir los 13 casos xfail en tests aprobados; ampliar matriz en Firebird aislado.
7. Comparar todos los proyectos en copia consistente con un oráculo ERP aprobado,
   incluyendo negativos y nulos. Cualquier fila no clasificada impide certificar esa parte.
8. Monitorizar cambios de esquema, nuevos estados e incidencias; invalidar el certificado
   cuando cambien código/política/datos fuera del snapshot certificado.

**Estado final de esta sesión: auditoría realizada; defectos documentados y reproducidos,
correcciones funcionales y certificación ERP todavía pendientes.**

## Corrección de técnicos y selector — 17/09/2026

La utilidad «Técnicos y actividad registrada» reemplaza la interpretación anterior de horas. `project_activity.py` consulta recursos vinculados mediante CODPROYECTO, incluye líneas con CANTIDAD=0 y separa ESPREVISION=0/1. La respuesta contiene `actividad`, `tecnicos`, `grupos` y `horas_verificadas: false`; no devuelve los antiguos totales de horas/costes como si estuvieran certificados. Los grupos incluyen explicaciones desplegables. Esto no certifica que cada recurso haya trabajado ni resuelve los demás hallazgos de auditoría.

El selector BD de Utilidades incorpora búsqueda por código/nombre y páginas de 15 mediante GET `/proyectos-buscar`. El selector antiguo del Probador no forma parte de esta corrección.

Validación directa de solo lectura en Firebird: 1214 proyectos; búsqueda y páginas disjuntas comprobadas. Proyecto 1001331: existe, sin líneas OBRALIN directamente vinculadas. Proyecto 10: 6 recursos, 2507 líneas MO previstas. Proyecto 45215: 26 recursos, 6490 líneas MO (72 no previstas y 6418 previstas), 66 sin código de recurso. Evidencia: `docs/validacion_actividad_proyectos_2026_09_17.json`; reproducción: `scripts/verificar_actividad_proyectos.py`.

Pruebas: utilidades + auditoría + selector + checks agrupados: 70 passed, 11 xfailed (hallazgos pendientes), una advertencia preexistente. Interfaz Node: 6 passed; comprobación sintáctica JS correcta. El caso AUD10 queda mitigado para esta utilidad al dejar de presentar previsiones como horas verificadas; no para las demás consultas.

Despliegue local pendiente: el servidor Python PID 19320 en puerto 8001 sigue con el backend anterior. El script `scripts/recargar_backend_api_clone.ps1` verifica que sirve el JS de este directorio y que existe un único listener Python antes de intentar reiniciarlo. Windows denegó Stop-Process incluso fuera del sandbox; no se detuvo el servidor. Es necesario reiniciarlo desde la sesión con permisos que lo inició y recargar el navegador. No se verificó el nuevo endpoint por HTTP en ese proceso.
