# Estado para retomar — 11/09/2026 (actualizado)

> **LEER ESTO PRIMERO.** Punto de entrada para la próxima sesión de IA.

---

## Repo y commits

- **Repo:** `bots/interjddcia` rama `main` — commit `b04232a`
- **En VM:** `cd bots/interjddcia && git pull` + reiniciar DEVIA + `Ctrl+F5`

```
b04232a  fix(probar-todo): pool IDs Firebird 1 conexion, cache 5min en auto-probar
206f540  fix(informe): URL configurada, auto-ID error exacto, debug-firebird-ids endpoint
ecb86fb  fix(code6): REPCAB PK=CODMAESTRO, info() automatico code=6, panel azul aclarado
372b076  fix(probador): crash mPYME detectado como crash_servidor, no config_incompleta
981e96a  feat(probador): ultra-robusto - browse vacio, 6 variantes/ID, items_muestra en TXT
9321708  docs: README v3.1 + DEVIA v3.2 + estado sesion 2026-09-11
df0da67  feat(probador): auto-probar exhaustivo + items REALES + panel diagnostico intentos
```

---

## Modulo: API Explorer → pestana Probador

**URL en DEVIA:** `http://localhost:8001` → "API Explorer" → "🧪 Probador"

### Ficheros clave

| Fichero | Lineas | Seccion relevante |
|---|---|---|
| `backend/modules/api_explorer/router.py` | ~1320 | L881: MAPA_FIREBIRD · L1033: auto_probar · L1241: valores-param |
| `backend/modules/api_explorer/service.py` | ~1900 | L115: RealApiClient · L224: read() · L216: browse() |
| `frontend/assets/js/modules/api_explorer.js` | ~3350 | L164: PARAMS_DB · L780: _mkOpCard · L3022: doEjecutarProbador |

---

## Estado actual

### Funciona
- Probador renderiza sin errores JS · node --check pasa
- mPYME conecta: `http://192.168.0.254:8081/` usuario MMMIGUELANGEL
- Firebird en VM: 1212 proyectos, 19065 reparaciones, 12374 articulos
- Boton BD: chips con IDs reales de Firebird
- Boton Ejecutar: llama `/auto-probar`, muestra tabla verde con datos reales
- Exportar TXT: 9 secciones con todo (OKs, fallos, licencias, errores, BD)

### PROBLEMA PRINCIPAL (en investigacion)

**code=6 persistente aunque Firebird tiene datos (1212 proyectos).**

Lo que sabemos con certeza:
- Firebird conecta OK, tablas OK, IDs se obtienen bien (PROYECTOS.CODIGO = 48511, 50123...)
- Mensaje mPYME: "No es posible acceder a la BD en este momento" = texto GENERICO para code=6
- NO significa Firebird caido. Significa: "el identificador enviado no es el formato correcto"
- `PROYECTOS.CODIGO` en Firebird es un INTEGER (48511) pero mPYME puede esperar formato "25/184"

Fix aplicado:
- Pool de IDs: probar-todo carga TODOS los IDs con 1 sola conexion al inicio
- Cache 5 min en auto-probar
- 6 variantes de llamada por ID
- info() automatico cuando todo falla (muestra estructura real de mPYME)
- Botón "🔬 Debug: Ver IDs reales por clase" en diagnostico BD

Que hacer en la VM para resolver definitivamente:
1. Abrir Probador → 🔌 Diagnostico BD → 🔬 Debug IDs → ver que valores tiene PROYECTOS.CODIGO
2. Si son numeros (48511): probar manualmente proyectos.browse con esos numeros
3. Si code=6 persiste: ejecutar proyectos.info() — ver el campo objectid real que espera mPYME
4. Puede que mPYME use CODPROYE (campo diferente al CODIGO de Firebird)

### Estado por clase (del informe txt real)
```
OK permiso=0:        repobjetos, repinst, tipostrabajo, partidas, ordenfab, clientes
NecesitaID code=6:   proyectos, reporden, repordutil, proordutil, proordprev, recursos
SinLicencia code=5:  docalbcom, docfaccom, docpedcom, articulos, proveedores
ConfigIncomp code=5: repinst.browse, tipostrabajo.browse, ordenfab.browse
```

---

## TAREA PRINCIPAL: Resolver code=6

### Paso 1 — Diagnostico en VM (solo lectura)
```
1. Probador → proyectos → info → Ejecutar (sin params)
   Ver campos reales que devuelve mPYME. Anotar el nombre del campo PK/objectid.

2. Probador → proyectos → browse → todos los campos vacios → Ejecutar
   code=0 + items: browse sin filtro OK → el auto-resolve con IDs era incorrecto
   code=6: browse siempre necesita parametro obligatorio

3. Probador → clientes → browse → Ejecutar vacio
   clientes.permiso=OK → deberia dar code=0 con lista de clientes
```

### Paso 2 — Correcciones segun diagnostico

**Si browse vacio da code=0:** Actualizar `/auto-probar` para intentar browse vacio PRIMERO.

**Si el formato mPYME es distinto al CODIGO de Firebird:**
```sql
-- Investigar estructura real:
SELECT FIRST 3 * FROM PROYECTOS ORDER BY CODIGO
-- Buscar columna con formato "25/184". Si hay ANIO + NUMERO:
SELECT TRIM(ANIO)||'/'||TRIM(NUMERO) AS CODMPYME, NOMBRE FROM PROYECTOS
-- O si hay columna CODPROYE:
SELECT FIRST 5 CODPROYE, NOMBRE FROM PROYECTOS
```
Actualizar MAPA_FIREBIRD en `router.py` L881 con el campo correcto.

---

## Protocolo API mPYME

```
URL: http://192.168.0.254:8081/ — POST form-urlencoded (NO JSON)
Params: ssid1, ssid2, empr, method, objectclass, [objectid], [filter], [data]
Codigos: 0=OK 1=sinLic 2=sinPerm 5=config/lic 6=necesitaParam 10=notFound -1=errRed
```

---

## Modulo BD del proyecto (USAR SIEMPRE ESTE, no firebirdsql directo)

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
# rows = [{"CODIGO": "48511", "NOMBRE": "Hospital..."}, ...]
```

---

## MAPA_FIREBIRD actual en router.py (L881)

```python
"proyectos":   ("PROYECTOS",      "CODIGO",  "NOMBRE",      "codProyecto"),
"reporden":    ("REPCAB",         "CODIGO",  "CODIGO",      "codOrden"),
"recursos":    ("RECURSO",        "CODIGO",  "DESCRIPCION", "codRecurso"),
"repobjetos":  ("REPOBJETO",      "CODIGO",  "NOMBRE",      "codObjeto"),
"repinst":     ("REPINSTALACION", "CODIGO",  "NOMBRE",      "codInst"),
"tipostrabajo":("REPARA",         "CODIGO",  "DESCRIPCION", "codTrabajo"),
"articulos":   ("ARTICULO",       "CODIGO",  "NOMBRE",      "codArticulo"),
"proveedores": ("PROVEED",        "CODIGO",  "RAZONSOCIAL", "codProv"),
"clientes":    ("CLIENTE",        "CODIGO",  "NOMBRE",      "codCliente"),
```

AVISO: El CODIGO de Firebird puede ser ID interno numerico, no el que usa mPYME.

---

## Seguridad (OBLIGATORIO)

```
browse, read, permiso, info, cancel → SEGUROS (solo lectura)
write, imputaPro, delete → IRREVERSIBLES. Solo con modo escritura + confirm()
new/edit → objeto temporal, no persiste hasta write
```

---

## Pendientes por prioridad

1. [BLOQUEANTE] Resolver code=6 proyectos.browse/read → datos reales en pantalla
2. [IMPORTANTE] Clases con permiso=0 que aun dan code=6
3. [DESEADO] Probar new → write → cancel documentado
4. [DESEADO] Tests pytest para api_explorer
5. [DESEADO] localStorage para persistir resultados del Probador
