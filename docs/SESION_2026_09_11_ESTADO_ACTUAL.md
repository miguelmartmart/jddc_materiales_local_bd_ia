# Estado para retomar — 11/09/2026 (v3.3.0)

> **LEER ESTO PRIMERO antes de tocar nada.**

---

## Repo y commits

- **Repo:** ots/interjddcia rama main — commit 9b08fc7
- **En VM:** cd bots/interjddcia && git pull + reiniciar DEVIA + Ctrl+F5

`
9b08fc7  fix(code5): code=5 generico = requiere_params, auto-resolve con IDs Firebird
b04232a  fix(probar-todo): pool IDs Firebird 1 conexion, cache 5min
206f540  fix(informe): URL real, auto-ID error exacto, debug-firebird-ids
ecb86fb  fix(code6): REPCAB PK=CODMAESTRO, info() automatico code=6
372b076  fix(probador): crash mPYME detectado como crash_servidor
981e96a  feat(probador): ultra-robusto - 6 variantes/ID, items_muestra en TXT
9321708  docs: README v3.1 + DEVIA v3.2

## Modulo: API Explorer → pestana Probador

**URL:** `http://localhost:8001` → "API Explorer" → "🧪 Probador"

### Ficheros clave

| Fichero | Aprox. lineas | Seccion relevante |
|---|---|---|
| `backend/modules/api_explorer/router.py` | ~1450 | L881: MAPA_FIREBIRD · L903: cache IDs · L1033: auto_probar · L1218: probar_todo |
| `backend/modules/api_explorer/service.py` | ~1900 | L115: RealApiClient · L216: browse() |
| `frontend/assets/js/modules/api_explorer.js` | ~3600 | L164: PARAMS_DB · L780: _mkOpCard · L2695: doExportarProbadorTxt |

---

## Estado actual — que funciona

- JS sin errores (`node --check` pasa) · Python compila sin errores
- mPYME conecta: `http://192.168.0.254:8081/` usuario MMMIGUELANGEL
- Firebird en VM: 1212 proyectos, 19067 reparaciones, 12378 articulos
- Diagnostico BD: conexion OK, 6 tablas verificadas
- Boton BD: chips con valores reales · Boton Ejecutar: tabla verde con datos reales
- Boton Debug IDs: tabla con IDs por clase y errores exactos
- Exportar TXT: 9 secciones con muestras de datos reales

## Problema pendiente: code=6 persistente para proyectos/partidas/proordutil

`PROYECTOS.CODIGO` en Firebird es INTEGER (48511) pero mPYME puede esperar otro formato.

**Pasos para resolverlo en la VM:**
```
1. Probador → Diagnostico BD → Debug IDs → anotar valores exactos PROYECTOS.CODIGO
2. Probador → proyectos → info → Ejecutar sin params → ver estructura real mPYME
3. Probador → proyectos → browse → campos vacios → Ejecutar → si code=0: ver formato
4. Si sigue code=6: ejecutar en BD Firebird: SELECT FIRST 5 * FROM PROYECTOS
   Ver TODAS las columnas → encontrar cual tiene el formato "25/184" o similar
5. Actualizar MAPA_FIREBIRD en router.py L884 con el campo correcto
```

## Estado por clase (ultimo informe 11/09/2026)

```
proyectos/partidas/proordutil/proordprev → NecesitaID (code=6 o code=5 generico)
reporden/repobjetos/repinst/repordutil   → NecesitaID
tipostrabajo/recursos/clientes           → NecesitaID
articulos/proveedores/docalbcom/docfaccom/docpedcom → SinLicencia (contactar Distrito K)
ordenfab                                 → NecesitaID (sin licencia fabricacion)
```

---

## MAPA_FIREBIRD actual en router.py (L881)

```python
"proyectos":   ("PROYECTOS",      "CODIGO",  "NOMBRE",      "codProyecto"),  # ATENCION: CODIGO puede ser ID interno, no el que usa mPYME
"reporden":    ("REPCAB",         "CODMAESTRO","CODMAESTRO", "codOrden"),     # PK compuesta, CODMAESTRO es el 1er campo
"recursos":    ("RECURSO",        "CODIGO",  "DESCRIPCION", "codRecurso"),
"repobjetos":  ("REPOBJETO",      "CODIGO",  "NOMBRE",      "codObjeto"),
"repinst":     ("REPINSTALACION", "CODIGO",  "NOMBRE",      "codInst"),
"tipostrabajo":("REPARA",         "CODIGO",  "DESCRIPCION", "codTrabajo"),
"articulos":   ("ARTICULO",       "CODIGO",  "NOMBRE",      "codArticulo"),
"proveedores": ("PROVEED",        "CODIGO",  "RAZONSOCIAL", "codProv"),
"clientes":    ("CLIENTE",        "CODIGO",  "NOMBRE",      "codCliente"),
```

---

## Auto-resolve: como funciona ahora

`auto_probar` (boton Ejecutar individual):
1. Llama con params del usuario
2. browse vacio, browse pagesize=1
3. code=6 O code=5-generico: obtiene hasta 10 IDs de Firebird (cache 5min)
   × 6 variantes de llamada por ID = hasta 60 intentos
4. Filtros dominio adicionales
5. Si sigue code=6: llama info() automaticamente → panel verde con estructura mPYME

`probar_todo_catalogo` (boton Probar todas):
1. Pre-carga TODOS los IDs de TODAS las clases con 1 sola conexion Firebird
2. Para cada clase/op: reutiliza el pool (sin nuevas conexiones)
3. code=5 generico activa auto-resolve igual que code=6 (desde 9b08fc7)

---

## Protocolo API mPYME

```
URL base: http://192.168.0.254:8081/ — POST form-urlencoded
Codigos: 0=OK, 1=sinLic, 2=sinPerm, 5=config/params/licencia/crash, 6=necesitaParam, -1=errRed
```

## Modulo BD (SIEMPRE ESTE, nunca firebirdsql directo)

```python
from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings
cfg = DBConfig(host=settings.DB_HOST, port=settings.DB_PORT,
               database=settings.DB_NAME, user=settings.DB_USER,
               password=settings.DB_PASSWORD, charset="latin1")
drv = DBFactory.get_driver("firebird")
drv.connect(cfg)
rows = drv.execute_query("SELECT FIRST 5 CODIGO, NOMBRE FROM PROYECTOS")
drv.disconnect()
```

---

## Endpoints del modulo

| Endpoint | Metodo | Descripcion |
|---|---|---|
| `/auto-probar` | POST | Prueba clase+op. 60 intentos maximo. info() automatico |
| `/probar-todo-catalogo` | POST | Todas las clases. Pool 1 conexion. Auto-resolve |
| `/valores-param` | POST | IDs reales para autocompletar formulario |
| `/diagnostico-firebird` | GET | Estado conexion BD + n_registros tablas |
| `/debug-firebird-ids` | POST | Debug: IDs por clase, errores exactos |

---

## Seguridad (OBLIGATORIO)

```
browse/read/permiso/info/cancel → SEGUROS (solo lectura)
write/imputaPro/delete → IRREVERSIBLES → Solo con modo escritura + confirm()
new/edit → temporal, no persiste hasta write
```

## Pendientes por prioridad

1. [BLOQUEANTE] Averiguar formato objectid de proyectos en mPYME → pasos arriba
2. [IMPORTANTE] Confirmar que pool IDs (b04232a) resuelve AUTO-ID FALLO en probar-todo
3. [IMPORTANTE] Confirmar clases SinLicencia con Distrito K (articulos, proveedores...)
4. [DESEADO] Probar new() → write() → cancel() manualmente documentado
5. [DESEADO] Tests pytest para api_explorer
6. [DESEADO] localStorage para persistir resultados del Probador

df0da67  feat(probador): auto-probar exhaustivo + items REALES + panel diagnostico
`
