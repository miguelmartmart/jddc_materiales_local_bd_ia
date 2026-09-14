# Estado completo — 14/09/2026 (v6.0.0)

> **LEER ESTO PRIMERO antes de cualquier sesion de IA.**
> Reemplaza todas las versiones anteriores de documentacion.

---

## HALLAZGO CRITICO — 14/09/2026 (tarde)

### code=6 = MAINTENANCE MODE (no es falta de parametro)

La documentacion oficial mPYME v1.2 (PDF adjunto), pagina 7, dice:

```
codigos de respuesta:
  0 = Success
  1 = Warning and retry
  2 = Confirm and retry
  3 = Dialog and retry
  5 = Failed: no se ha podido ejecutar la peticion
  6 = Maintenance mode: no se puede ejecutar la peticion por encontrarse
      el sistema en modo de mantenimiento. La sesion sigue siendo valida.
  7 = Invalid session
  8 = Exception
```

**CONCLUSION: code=6 NO significa "falta parametro". Significa que SQL Obras esta en MODO MANTENIMIENTO.**

### new() = code=5 con mensaje "No dispone de licencia para el modulo Proyectos"

Esto indica que el modulo mPYME de Proyectos (y posiblemente Reparaciones y Compras) **no esta contratado o no esta activado** para este cliente.

Dos posibles causas del problema:
1. **SQL Obras en modo mantenimiento** (code=6 en browse y new)
2. **Modulo mPYME no contratado** (code=5 en new con msg de licencia)

Ambas causas requieren intervencion de Distrito K.

---

## Lo que SÍ funciona

| Operacion | Resultado | Nota |
|---|---|---|
| Login | ✅ code=0 | Sesion activa correctamente |
| permiso(partidas) | ✅ code=0 | Tiene acceso |
| permiso(repobjetos) | ✅ code=0 | Tiene acceso |
| permiso(repinst) | ✅ code=0 | Tiene acceso |
| permiso(tipostrabajo) | ✅ code=0 | Tiene acceso |
| permiso(ordenfab) | ✅ code=0 | Tiene acceso |
| info(clientes) | ✅ code=0 | Funcion de auditoria (no da campos) |
| Firebird directo | ✅ 1212 proyectos | BD accesible directamente |

## Lo que NO funciona

| Operacion | Resultado | Causa segun docs |
|---|---|---|
| browse(*) | ❌ code=6 | Modo mantenimiento |
| new(proyectos) | ❌ code=5 | "No dispone de licencia para el modulo Proyectos" |
| new(clientes) | ❌ code=6 | Modo mantenimiento |
| read(proyectos) | ❌ code=6 | Modo mantenimiento |

---

## Por que code=6 no es problema de parametros

- La documentacion dice que browse(proyectos) SOLO requiere filter (opcional)
- Se han probado 774 variantes sin exito
- El mensaje exacto es "No es posible acceder a la base de datos en este momento"
- new() sin parametros tambien da code=6 (new no necesita parametros segun doc)
- Esto es coherente con modo mantenimiento: TODAS las operaciones fallan

---

## Lo que hay que preguntar a Distrito K

### Pregunta generada automaticamente (ver app DEVIA)

La app genera la pregunta completa con toda la evidencia.
Los puntos clave son:

1. **SQL Obras esta en modo mantenimiento?** Como desactivarlo?
2. **El modulo mPYME de Proyectos esta contratado/activado** para JDDC?
3. Si no es modo mantenimiento, que parametro requiere browse()?

---

## Lo que ya se ha probado en browse (774 variantes)

- Vacio (sin parametros)
- filter="" (vacio), filter={}
- pagesize=1/25, more=first
- ejercicio=2021/2025/2026, anyo=2021/2026
- estado=abierta/activa, soloActivos=T, activo=T, todos=T
- objectid=new
- IDs reales de Firebird (codProyecto=1, codOrden=1, etc.)
- masterid=<id>, master=<id> (para proordutil, partidas, repobjetos)
- desde/hasta (para proordutil segun doc oficial)
- serie=A (para documentos)
- mode=add (para repobjetos)
- columns=[] (ordenacion)

---

## Informacion tecnica del servidor

- URL API: http://192.168.0.254:80/
- Empresa: JDDC
- BD Firebird: 192.168.0.254 / C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb
- 1212 proyectos en Firebird
- PymeMobileServer.exe: responde HTTP 200, devuelve JSON valido
- Sesion: ssid1/ssid2 obtenidos correctamente en login

---

## Archivos de documentacion tecnica en Downloads

- `mpyme_auth.txt` — Protocolos autenticacion, codigos de error (KEY: code=6=maintenance)
- `mpyme_paginas_clave.txt` — Intro, browse, filter, columns, more
- `mpyme_gestion_proyectos.txt` — Proyectos, proordutil (masterid+desde/hasta), partidas
- `mpyme_ejemplos.txt` — Ejemplos curl completos de todas las operaciones
- `mpyme_proyectos_full.txt` — Doc completa incluyendo Maestros, Documentos, Fabricacion
- `mpyme_proyectos_reps.txt` — Doc completa incluyendo Reparaciones
- `mPYME_API_Documentacion 1.2.pdf` — PDF original completo

---

## Estructura del proyecto DEVIA

```
bots/interjddcia/
  backend/modules/api_explorer/
    router.py           -- Endpoints FastAPI (super-diagnostico v6)
    service.py          -- Cliente mPYME + sesion stateful
    api_catalogue_full.py -- Catalogo de clases y operaciones
    data/               -- Cache de sesion y descubrimiento
  frontend/assets/js/modules/
    api_explorer.js     -- UI completa (boton diagnostico + render)
  docs/
    SESION_2026_09_14_ESTADO_ACTUAL.md -- este archivo
```

## Endpoint super-diagnostico

`POST /api/api-explorer/super-diagnostico`

Fases:
- F1: Firebird directo (conexion + conteo tablas)
- F2: Pool de IDs reales de Firebird por clase
- F3: browse (774+ variantes por clase) + read con IDs reales
- F4: new()+cancel() en 4 clases con variantes de params
- F5: Conclusiones automaticas + aviso_admin + pregunta_dk

Respuesta incluye:
- `conclusiones[]` con tipo (ok/licencia/params/bd_inacc/config/firebird)
- `pregunta_distrito_k` texto completo para enviar
- `aviso_admin` aviso si hay modo mantenimiento
- `nc_new_codes` codigos de new()
- `clases_permiso_ok` clases con permiso=0

---

## QUE HACER EN LA PROXIMA SESION

1. `git pull` en la VM, reiniciar DEVIA, Ctrl+F5
2. Ejecutar diagnostico completo
3. Leer el panel F4 — si new()=code=6: SQL Obras en modo mantenimiento
4. Copiar la pregunta generada y enviarla a Distrito K
5. Pedir a Distrito K:
   a. Desactivar modo mantenimiento si esta activo
   b. Confirmar que el modulo mPYME Proyectos+Reparaciones esta contratado
6. Una vez resuelto, repetir diagnostico — deberia dar code=0 en browse
