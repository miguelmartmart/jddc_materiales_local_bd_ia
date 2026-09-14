# Estado para retomar — 14/09/2026 (v7.0.0 — Modo Mantenimiento + Fix new())

> **LEER ESTO PRIMERO. Es el unico fichero de estado valido. Fecha: 14/09/2026.**

---

## El problema central — causa identificada

**code=6 = Maintenance mode** segun documentacion oficial mPYME v1.2, pag. 7:

> `"6 = Maintenance mode: no se puede ejecutar la peticion por encontrarse el sistema en modo de mantenimiento. La sesion sigue siendo valida."`

**Mensaje exacto del servidor JDDC:** `"No es posible acceder a la base de datos en este momento"`

Esto NO es un error de parametros. Es el modo mantenimiento de SQL Obras activado.

---

## Evidencia del diagnostico (700 variantes probadas)

| Clase | permiso | browse | new() | Causa |
|---|---|---|---|---|
| proyectos | code=6 | code=6 | code=5 (No licencia) | Mantenimiento + sin licencia modulo |
| partidas | code=0 | code=6 | code=6 | Mantenimiento |
| clientes | code=6 | code=6 | code=6 | Mantenimiento |
| reporden | code=6 | code=6 | code=6 | Mantenimiento |
| repobjetos | code=0 | code=6 | — | Mantenimiento |
| tipostrabajo | code=0 | code=6 | — | Mantenimiento |
| ordenfab | code=0 | code=5 | — | Peticion no soportada |
| proordprev | code=6 | code=5 | — | Peticion no soportada |

---

## Dos problemas distintos

### Problema 1: SQL Obras en modo mantenimiento (code=6)
- Bloquea browse(), new(), write(), read() en TODAS las clases
- El usuario tiene acceso a SQL Obras en el servidor 192.168.0.254
- Solucion: Desactivar el modo mantenimiento (ver instrucciones abajo)

### Problema 2: Modulos mPYME sin licencia (new=code=5)
- new(proyectos) = "No dispone de licencia para el modulo Proyectos. (Funcion proyectos)"
- Los modulos de Proyectos, Reparaciones, Fabricacion son licencias adicionales de pago
- Solucion: Contratar modulos con Distrito K

---

## Como desactivar el modo mantenimiento en SQL Obras

### Opcion A (recomendada) — Desde SQL Obras desktop
1. Abrir SQL Obras en el PC servidor (192.168.0.254)
2. Menu: Administracion > Sistema (o Herramientas > Opciones del sistema)
3. Buscar "Modo mantenimiento" o "Mantenimiento API"
4. Si esta activo: DESACTIVAR y guardar
5. Alternativa: Utilidades > Modo servicio > Desactivar
6. Reiniciar PymeMobileServer.exe despues

### Opcion B — Reiniciar PymeMobileServer.exe
1. Servicios de Windows (services.msc) en servidor 192.168.0.254
2. Buscar "PymeMobile Server" o "mPYME"
3. Click derecho > Reiniciar
4. Esperar 30 segundos y verificar

### Opcion C — Contactar Distrito K
Si las opciones A y B no funcionan:
> "Nuestro servidor devuelve code=6 (Maintenance mode segun doc v1.2) con mensaje
> `No es posible acceder a la base de datos en este momento`.
> browse() y new() fallan en todas las clases. Por favor verificad si el modo
> mantenimiento esta activo en nuestra instalacion y como desactivarlo."

---

## Fix tecnico aplicado en esta sesion

### Bug corregido: new() enviaba objectid=new incorrectamente
**Antes:** `method=new&objectclass=proyectos&ssid1=...&ssid2=...&objectid=new`
**Ahora:** `method=new&objectclass=proyectos&ssid1=...&ssid2=...`

La doc oficial dice: new() obligatorios = ssid1, ssid2, objectclass. SOLO.
`objectid` solo se usa en clases hija (ej: proordutil con id del proyecto padre).

### Endpoint nuevo: GET /modo-mantenimiento
- Verifica si browse(clientes) = code=6
- Devuelve instrucciones paso a paso para desactivar el modo mantenimiento
- Accesible desde el boton naranja en el Probador Visual

---

## Estado de implementacion (v7.0.0)

| Componente | Estado |
|---|---|
| F1 Firebird | OK — 1212 proyectos |
| F2 IDs de BD | OK — 16 tablas con IDs reales |
| F3 Browse | 700 variantes probadas, todas code=6/5 |
| F4 new() corrected | Fix: ya no envia objectid=new incorrectamente |
| Boton Modo mantenimiento | NUEVO — verifica y da instrucciones |
| Diagnostico completo | OK — conclusiones correctas |
| Pregunta Distrito K | Generada automaticamente |

---

## Lo que queda por hacer

1. **PRIMERO:** Desactivar el modo mantenimiento en SQL Obras
2. **DESPUES:** Ejecutar Diagnostico completo para ver si browse() funciona
3. **Si sigue sin funcionar:** Ver si hay modulos sin licencia (code=5 en new)
4. **Si todo OK:** La integracion deberia funcionar correctamente

---

## Archivos clave

- `backend/modules/api_explorer/service.py` — RealApiClient, fix new() sin objectid
- `backend/modules/api_explorer/router.py` — super-diagnostico, /modo-mantenimiento
- `frontend/assets/js/modules/api_explorer.js` — UI, boton modo mantenimiento
- `docs/SESION_2026_09_14_ESTADO_ACTUAL.md` — este fichero
