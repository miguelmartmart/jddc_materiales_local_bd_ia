# Sesión 16/09/2026 — Fixes post-imágenes de usuario

Commit: `06bdd54` — rama `main`

---

## Problemas detectados en capturas de pantalla

### 1. 🔴 Catálogo de datos — texto sin formatear (`\n` literal visible)
**Causa:** `JSON.stringify(correo)` dentro de `onclick=""` → el texto del correo (que contiene
comillas como `filter=" "`) rompía el atributo HTML. El navegador lo renderizaba como texto plano
con `\n` literal en pantalla.

**Fix (JS `_renderCatalogoDatos`):**
- El correo se codifica con `btoa(unescape(encodeURIComponent(...)))` (base64 seguro UTF-8)
- Se guarda en `<textarea id="cat-correo-hidden" style="display:none">`
- Los botones copiar/descargar leen el textarea con `atob()` y reconstruyen el texto sin
  interferencia de comillas HTML

### 2. 🟡 Tablas con `ERR:Dynamic SQL Error SQL error code = -204 Table unknown`
Tablas afectadas: `PREUTILLIN`, `PREUTILCAB`, `PREPREVLIN`, `PREPREV`, `PARTPROYE`, `RABUTILLIN`, `RABUTILCAB`

**Causa:** Esas tablas no existen en esta instalación concreta de SQL Obras. El error raw de
Firebird se mostraba en rojo en la UI.

**Fix (Python `router.py` — ambas funciones `_count/_q` en validar-datos-bd e informe-maestro):**
- Si el error contiene `-204` o `Table unknown` → `_count` devuelve `"NO_EXISTE"`, `_q` devuelve `[]`
- Si el error contiene `-206` o `Column unknown` → `_count` devuelve `"COL_ERROR"`

**Fix (JS `_tablaRow`):**
- `n === 'NO_EXISTE'` → muestra `— no existe` en gris, `opacity:0.55`
- `n === 'COL_ERROR'` → muestra `⚠ col?` en naranja con tooltip explicativo
- `n.startsWith('ERR:')` → muestra `ERR` en rojo (casos genéricos)

### 3. 🟡 `alb_con_proyecto` — "conversion error from string 45382-2"
**Causa:** `CODPROYECTO<>0` intentaba comparar un VARCHAR con un número entero.

**Fix:** `TRIM(CODPROYECTO)<>''` — compara string con string.

### 4. 🟡 `PRESUPROYE` — "Column unknown CODIGO At line 1, column 16"
**Causa:** La tabla `PRESUPROYE` en esta BD no tiene columna `CODIGO`.

**Fix:** Query cambiada a `SELECT FIRST 3 CODPROYECTO,DESCRIPCION,IMPORTE FROM PRESUPROYE`

### 5. 🔴 `_renderValidarBD` — estructura JS rota
**Causa:** La función `forEach` no tenía cierre `});`, y `_renderInformeMaestro` empezaba
literalmente dentro de la función anterior. Había también un bloque `h += '</div>'; return h; }`
duplicado y huérfano al final del archivo.

**Fix:** Añadido `});  // cierre forEach mods` + `h += '</div>';` + `return h; }` correctos.
Eliminado bloque duplicado final.

### 6. 🟡 CSV exportado — valores erróneos (`.map(v=>'+v+')`)
**Causa:** La función `_eC` tenía `.map(v=>'+v+')` — literalmente ponía `+v+` como texto.

**Fix:** `.map(v=>'"'+String(v||'').replace(/"/g,"'")+'"')` — CSV correctamente comillado con
comillas dobles, escapando las internas.

---

## Nuevas funciones añadidas

### 📂 PDF / Imprimir (Informe Maestro)
- Botón `📂 PDF / Imprimir` en el footer oscuro del Informe Maestro
- Abre ventana nueva con HTML imprimible: tabla cruzada BD+API, Nivel 1 ejecutivo,
  Nivel 2 módulos, correo DK completo
- Lanza `window.print()` automáticamente → usuario elige "Guardar como PDF"
- Código: método `_ePDF(r,cl,nv,em,fch)` en `ApiExplorerModule`

### ⬇ Descargar TXT del correo (Catálogo)
- Botón adicional `⬇ Descargar TXT` junto al correo en el Catálogo de datos
- Descarga directa del correo formateado para Distrito K

---

## Estado BD confirmado desde capturas

| Tabla | Registros | Notas |
|---|---|---|
| CLIENTE | 9.426 | ✅ OK |
| PROVEED | 1.789 | ✅ OK |
| ARTICULO | 12.377 | ✅ OK |
| RECURSO | 186 técnicos | ✅ OK |
| REPOBJETO | 445 objetos | ✅ OK |
| PROYECTOS | 1.213 | ✅ OK |
| PRESUPROYE | 1.710 | ✅ existe, pero col CODIGO no existe |
| PREUTILLIN | — | ❌ tabla no existe (módulo Proyectos no activado) |
| RABUTILLIN | — | ❌ tabla no existe (horas técnico SAT no registradas en BD) |
| PREPREVLIN | — | ❌ tabla no existe |
| PARTPROYE | — | ❌ tabla no existe |
| REPARA | (partes SAT) | Ver módulo Reparaciones |

**Implicación:** La empresa JDDC tiene 1.213 proyectos en BD pero NO imputa horas/costes en
SQL Obras (PREUTILLIN vacío o inexistente). La licencia mPyme Proyectos daría acceso a proyectos
pero no a datos de horas reales de técnicos — hay que preguntar a DK sobre el flujo de trabajo.

---

## Para la VM

```bash
git pull origin main
# Reiniciar DEVIA
# Ctrl+F5 en el navegador
```

### Flujo de prueba recomendado:
1. **Conectarse** (pestaña Conexión)
2. **🔬 Validar datos en BD** → tablas inexistentes ahora aparecen en gris `— no existe`
3. **📊 Catálogo de datos** → correo formateado correctamente, botón copiar funciona
4. **📋 Informe Maestro** → 6 botones de exportar: TXT, JSON, CSV, HTML, Correo DK, PDF
5. **📂 PDF** → abre ventana de impresión → `Ctrl+P` → `Guardar como PDF`
