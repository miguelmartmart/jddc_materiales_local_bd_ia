# Estado para retomar — 11/09/2026

> **LEER ESTO PRIMERO.** Punto de entrada para la próxima sesión de IA.

---

## Repo y commits

- **Repo:** `bots/interjddcia` rama `main` — commit `df0da67`
- **En VM:** `cd bots/interjddcia && git pull` + reiniciar DEVIA + `Ctrl+F5`

```
df0da67  feat(probador): auto-probar exhaustivo + items REALES + panel diagnostico
5266142  fix(probador): 4 bugs - read objectid, browse filter/page, auto-resolve
8f959c5  fix(probador): doEjecutarProbador - funcion, data-param, data-exec
677bde5  fix(probador): nombres reales tablas/columnas Firebird en MAPA_FIREBIRD
c54ddb3  fix(critical): SyntaxError JS, favicon.ico
8a3d2b0  feat(ux+export): formulario ultra-amigable + TXT 9 secciones
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

### PROBLEMA PRINCIPAL (sin resolver)

**code=6 persistente en browse/read para proyectos y otras clases.**

```
proyectos.browse → code=6 con {filter:"Hospital", page:"1"}
proyectos.browse → code=6 con IDs de Firebird: 48511, 50123...
proyectos.read   → code=6 con objectid="48511"
```

**Causa probable:** `PROYECTOS.CODIGO` en Firebird = ID interno numerico (48511).
mPYME puede esperar formato "25/184" (anio/secuencial). Son identificadores distintos.

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
