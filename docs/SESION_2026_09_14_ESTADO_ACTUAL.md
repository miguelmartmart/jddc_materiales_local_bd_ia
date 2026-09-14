# Estado para retomar — 14/09/2026 (v5.0.0)

> **LEER ESTO PRIMERO. Reemplaza todas las versiones anteriores.**

## Repo

- **Remote:** https://github.com/miguelmartmart/jddc_materiales_local_bd_ia.git
- **Rama:** main · **Commit:** e5f414a
- **En VM:** cd bots/interjddcia && git pull && reiniciar DEVIA && Ctrl+F5

```
e5f414a  fix(super-diag): corregir sets malformados en variantes F3
091b9d8  fix(super-diag): code=6=falta-param + read() + info_campos + msg exacto
a5675ef  feat(super-diag): panel ACCION REQUERIDA
df9687a  feat(super-diagnostico): Centro de Diagnostico Inteligente v4.0.0
```

---

## Infraestructura OK

| Componente | Estado | Detalle |
|---|---|---|
| DEVIA FastAPI | OK | http://localhost:8001 |
| Firebird | OK | 192.168.0.254:3050 SYSDBA · JUANDEDI\2021.fdb |
| mPYME API | OK | http://192.168.0.254:80/ · Login OK usuario MMMIGUELANGEL |
| PROYECTOS | OK | 1212 registros · CODIGO = 1, 10, 1001301 |
| REPARA | OK | 8398 registros · CODIGO = 3, 4, 7 |
| REPOBJETO | OK | 445 registros · CODIGO = 002KCPY1S368, 003KCHE1AC81 |
| CLIENTE | OK | CODIGO = 1, 3, 10 |
| DOCCAB | OK | CODIGO = 4, 6, 8 |
| FABCAB | SIN DATOS | Tabla vacia |

---

## El problema central: browse() y new() = code=6

### Significado de code=6

**code=6 = "No es posible acceder a la BD en este momento"**
Segun service.py L281-283 (documentado en el propio codigo):
> NO es error de BD. Es como mPYME dice "falta un parametro obligatorio".

- Firebird conecta directamente (1212 proyectos OK)
- PymeMobileServer responde HTTP 200
- Conclusion: falta algun parametro que el servidor exige pero no documenta

### new() tambien devuelve code=6
new() con {} vacio devuelve code=6 = new() tambien exige parametros de contexto desconocidos.

### Clases por resultado en permiso()

| permiso=0 (acceso autenticado) | permiso=6 | permiso=5 |
|---|---|---|
| partidas, repobjetos, repinst, tipostrabajo, clientes, ordenfab | proyectos, proordutil, reporden, repordutil, recursos, docalbcom, docfaccom, docpedcom | proveedores, articulos |

### Variantes YA PROBADAS en browse (~650 total, todas code=6)

```
vacio, pagesize=1/25, num=20/100, filter={}, estado=abierta/activa
soloActivos=T, activo=T, todos=T
ejercicio=2021 (anyo real .fdb), ejercicio=2025/2026, anyo=2021/2026
tipo=EMPLEADO/M, columns=[], page=1+pagesize=25
objectid=new, empr=JDDC+pagesize=25
codProyecto=1/10/1001301 (IDs reales Firebird PROYECTOS)
codOrden=3/4/7 (IDs reales REPARA)
codObjeto=002KCPY1S368 (IDs reales REPOBJETO)
+ combinaciones: ID+pagesize, ID+ejercicio, ID+p1
IDs reales de todas las tablas con 5 variantes cada uno
```

### Variantes YA PROBADAS en new() (todas code=6)
```
{} vacio, {ejercicio:"2021"}, {ejercicio:"2026"}, {empr:"JDDC"}
```

---

## LO QUE SI FUNCIONA

- permiso() = code=0 en: partidas, repobjetos, repinst, tipostrabajo, clientes, ordenfab
- info() = code=0 en: clientes (devuelve campos del servidor)
- login() y logout() siempre funcionan
- read() con IDs Firebird: PENDIENTE DE VERIFICAR en proximo diagnostico

---

## COSAS QUE NO SE HAN PROBADO (trabajo para la proxima sesion)

### GRUPO A: Variantes de browse pendientes (PRIORIDAD ALTA)

| Prueba | Por que puede funcionar |
|---|---|
| filter={"codProyecto":"1"} (JSON serializado) | filter puede esperar JSON real, no string vacio |
| filter={"CODIGO":"1"} | El filtro puede usar nombre de campo Firebird |
| filter={"estado":"A"} | Codigos internos: A=Activo, C=Cerrado, P=Pendiente |
| empr="1" (numero, no texto) | El protocolo doc dice empr=1 numerico, no "JDDC" |
| empr="2", empr="3" | Probar otros numeros de empresa |
| Sin empr en la llamada | La sesion puede ser suficiente sin empr en cada peticion |
| rows=1, limit=1, top=1 | Nombres alternativos de pagesize |
| objectclass=Proyectos (mayuscula inicial) | El servidor puede ser case-sensitive |
| codProyecto="25/184" o "JDDC-001" | El ID mPYME puede ser distinto al CODIGO Firebird |
| pagesize=1 & page=0 | Paginacion desde cero |
| v=1.2, version=1.2 | La API puede requerir version explicita |
| modulo=obras, vista=proyectos | Parametro de contexto de modulo ERP |

### GRUPO B: Variantes de new() pendientes

| Prueba | Por que |
|---|---|
| new({objectid:"new", codProyecto:"1"}) | Con ID de contexto |
| new en tipostrabajo o repinst | Clases con permiso=0, mas prob. de funcionar |
| new({objectid:"", ejercicio:"2021"}) | objectid vacio en vez de "new" |

### GRUPO C: Operaciones no probadas nunca

| Prueba | Riesgo | Por que |
|---|---|---|
| exec action=list | Bajo | Puede ser un browse alternativo sin filtros |
| exec action=count | Bajo | Devuelve numero de registros |
| exec action=getAll | Bajo | Variante de browse total |
| exec action=find | Bajo | Busqueda alternativa |

### GRUPO D: Verificaciones de protocolo

| Prueba | Como |
|---|---|
| Texto exacto del data en code=6 | Ya capturado en browse_msg_exacto -- LEER EN PROXIMO DIAG |
| Varia el mensaje entre clases? | Comparar browse_msg_exacto por clase |
| HTTP status code en cada respuesta | Capturado en _http_status -- ver si siempre 200 |
| info() en TODAS las clases (no solo clientes) | info(proyectos), info(reporden)... puede revelar campos |

### GRUPO E: Hipotesis no descartadas

| Hipotesis | Evidencia | Como descartar |
|---|---|---|
| El ID mPYME != CODIGO Firebird | REPOBJETO tiene IDs alfanumericos tipo UUID | read() con codigo alfanumerico completo |
| empr debe ser numero | Protocolo doc dice empr=1 | Probar empr=1, empr=2 |
| La sesion caduca sin avisar | Si ssid1/ssid2 caducan, code=6 en todo | Re-login forzado antes del diagnostico |
| Hay parametro de "vista" o "rol" | Los ERP suelen tenerlo | Probar vista=, rol=, perfil=, modulo= |
| filter va como query string no form | Algunos servidores PHP lo mezclan | Cambiar cliente HTTP |

---

## Ficheros clave

| Fichero | Lineas | Seccion |
|---|---|---|
| backend/modules/api_explorer/router.py | ~1953 | L1601: /super-diagnostico, L1637: F3, L1732: F4, L1764: F5 |
| backend/modules/api_explorer/service.py | ~350 | L115: RealApiClient, L170: _base(), L216: browse(), L242: new() |
| frontend/assets/js/modules/api_explorer.js | ~3960 | L575: boton, L3188: doCentroDiagnostico, L3662: _renderCentroDiag |

### MAPA_FIREBIRD (router.py ~L881)

```python
"proyectos":   ("PROYECTOS",      "CODIGO", "NOMBRE",      "codProyecto")
"reporden":    ("REPARA",          "CODIGO", "CODIGO",      "codOrden")
"tipostrabajo":("TIPO",            "CODIGO", "DESCRIPCION", "codTrabajo")
"repobjetos":  ("REPOBJETO",       "CODIGO", "NOMBRE",      "codObjeto")
"repinst":     ("REPINSTALACION",  "CODIGO", "NOMBRE",      "codInst")
"recursos":    ("RECURSO",         "CODIGO", "DESCRIPCION", "codRecurso")
"articulos":   ("ARTICULO",        "CODIGO", "NOMBRE",      "codArticulo")
"proveedores": ("PROVEED",         "CODIGO", "RAZONSOCIAL", "codProv")
"clientes":    ("CLIENTE",         "CODIGO", "NOMBRE",      "codCliente")
"docalbcom":   ("DOCCAB",          "CODIGO", "CODIGO",      "codDocumento")
"ordenfab":    ("FABCAB",          "CODIGO", "CODIGO",      "codFab")  # tabla vacia
```

ATENCION: El CODIGO de Firebird puede NO ser el objectid que espera mPYME.
REPOBJETO tiene CODIGO alfanumerico tipo 002KCPY1S368 -- parece un codigo interno.

---

## Protocolo API mPYME

```
URL:     http://192.168.0.254:80/
Metodo:  POST form-urlencoded (NO JSON)
Campos:  ssid1=X ssid2=X empr=JDDC method=browse objectclass=proyectos [+params]
```

### Codigos de respuesta
```
0  = OK
1  = Sin licencia
2  = Sin permiso
5  = Params incompletos / peticion no reconocida / crash
6  = Falta parametro obligatorio (NO error de BD)
10 = Registro no encontrado
20 = objectId no valido
-1 = Error de red
```

---

## Lo que hace el Diagnostico Completo (boton en Probador)

### F1: Firebird
Conexion directa + COUNT de todas las tablas del MAPA_FIREBIRD.

### F2: Pool de IDs
1 sola conexion Firebird. Extrae hasta 10 IDs reales por clase.

### F3: Browse + read + info por clase
Para cada una de las 17 clases:
- permiso() -- captura code y mensaje
- info() -- captura code y si=0, nombres de campo del servidor
- 23 variantes base de browse
- +5 variantes x hasta 5 IDs Firebird reales (param, objectid, +pagesize, +ejercicio)
- Captura el mensaje exacto del data en code=6
- read() con hasta 3 IDs reales Firebird

### F4: new() con variantes de contexto
Proyectos, repobjetos, reporden, clientes.
Variantes: vacio, ejercicio=2021, ejercicio=2026, empr=JDDC

### F5: Conclusiones + Pregunta para Distrito K
Genera pregunta con: mensaje exacto code=6, 650+ variantes probadas, que si funciona.

---

## QUE HACER EN LA PROXIMA SESION DE IA

### Paso 1 -- Ejecutar nuevo diagnostico en la VM y LEER resultados

```
git pull origin main
reiniciar DEVIA
Ctrl+F5
Probador Visual -> Diagnostico completo
Esperar 90-120 segundos
```

Lo mas importante es anotar:
1. El texto EXACTO de browse_msg_exacto (data en code=6) -- puede decir que param falta
2. Si read() funciona en alguna clase y con que ID
3. Si info() devuelve campos en alguna clase (y cuales campos)
4. El mensaje exacto de new() code=6 -- puede diferir del de browse
5. Si alguna clase tiene permiso=0 Y browse diferente de code=6

### Paso 2 -- Implementar Grupo A (variantes pendientes)

En router.py F3, anyadir a _variantes:
```python
# filter como JSON real con ID real
({{"filter": json.dumps({{"codProyecto": _fb["valores"][0]}})}} , "filter-json"),
# empr numerico
({{"empr": "1", "pagesize": "25"}}, "empr1+p25"),
({{"empr": "2", "pagesize": "25"}}, "empr2+p25"),
# Llamada sin empr (quitarlo de _base para una prueba)
# rows/limit como alternativas a pagesize
({{"rows": "1"}}, "rows=1"),
({{"limit": "1"}}, "limit=1"),
# exec actions alternativas
({{"method": "exec", "action": "list"}}, "exec-list"),
```

### Paso 3 -- Si ninguna variante funciona, enviar pregunta a Distrito K

La pregunta ya esta generada en el panel amarillo del diagnostico.
Boton Copiar -> enviar a Distrito K por email.

La pregunta incluye:
- Mensaje exacto code=6
- Las 650+ variantes ya probadas
- Que si funciona (read/info si aplica)
- 5 preguntas precisas sobre parametros obligatorios

### Paso 4 -- Cuando Distrito K responda

Implementar el parametro que indiquen y probar.
Si la respuesta es un nombre de parametro, se anyadira a _variantes y se re-ejecuta el diagnostico.

---

## Seguridad (OBLIGATORIO respetar)

```
browse / read / permiso / info / cancel -> SEGUROS (solo lectura)
new + cancel -> temporal, no persiste, SEGURO
write / imputaPro / delete / exec       -> ESCRITURA REAL IRREVERSIBLE
                                          Solo con modo escritura activado + doble confirmacion
```

---

## Modulo BD -- patron correcto

```python
from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings

cfg = DBConfig(
    host=settings.DB_HOST, port=settings.DB_PORT,
    database=settings.DB_NAME, user=settings.DB_USER,
    password=settings.DB_PASSWORD, charset="latin1"
)
drv = DBFactory.get_driver("firebird")
drv.connect(cfg)
rows = drv.execute_query("SELECT FIRST 5 CODIGO, NOMBRE FROM PROYECTOS")
drv.disconnect()
```

---

## Hipotesis principal (la mas probable)

El servidor mPYME requiere un parametro de contexto en browse y new
que NO se llama ejercicio ni anyo.

Candidatos:
- El numero interno de empresa (empr=1 numerico, no texto)
- Un parametro de "ejercicio contable" con nombre diferente (codEjercicio, ej, anio...)
- Un parametro de modulo o vista (modulo=obras, vista=proyectos)
- El objectid del objeto padre en clases jerarquicas (partidas necesita codProyecto padre)

Solo Distrito K puede confirmar cual es.
