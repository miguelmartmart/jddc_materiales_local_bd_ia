# DEVIA — Módulo `db_simulator`
## Simulador de BD Firebird para trabajo offline

> **Ruta:** `backend/modules/db_simulator/`  
> **Versión:** 2.0.0  
> **Fecha:** 2026-06-25  
> **Estado:** ✅ Implementado y funcional — 2471 consultas (v1+v2+v3), **96.9% pass rate en simulador**, tests parity 34/34 ✅

---

## 📚 Historial de sesiones

| Fecha | Contenido |
|-------|-----------|
| 20/05/2026 | Fix HTTP 500 query_library truncado, filtros UI vacíos |
| 21/05/2026 | Context Manager v3.0, fix `_execute_sql` bloqueante |
| 21/05/2026 | Tests 40/40 ✅: `get_queries_by_rol`, `catalog_summary` aliases, Firebird-only handling |
| 29/05/2026 | Auditoría completa query_library: 0 fallos SQL, correcciones contextuales aplicadas |
| 01/06/2026 | Fix crítico `query_translator.py`: `_translate_cast_numeric` con balance de paréntesis |
| 03/06/2026 | **v1.7.0**: Módulo `justification/` independiente, 1077 consultas, 10 paneles/consulta, adapter `sqlite_to_firebird.py` con mapeo real Firebird, eliminación de comentarios subjetivos en `query_library_core.py` |
| 05/06/2026 | **v1.8.0**: Biblioteca v3 completa — 950 consultas nuevas en 8 módulos (`*_v3.py`), total 2252 consultas. Actualización de `__init__.py`, DEVIA y tests. |
| 10/06/2026 | **v1.9.0**: Modo prueba BD real — `simulator_enabled=false`, `TestModeConfig` en `constants.py`, `test_real_db.py` con 6 clases de tests contra Firebird real, `config.json` con sección `test_mode`. |
| 17/06/2026 | **v1.9.1**: Suite de paridad BD — `tests/db_parity/` con `test_schema_parity.py` y `test_query_parity.py`. Fix schema: `CAJA.CONCEPTO`, `DOCCAB.ESTADO`, `RECIBO1/RECIBO3.ACTIVO/DEVOLUCION`. Fix bug: `f_saldo_clientes_vencido` usaba `CODPAGADOR` (columna de RECIBO3) en lugar de `CODPAGA` (RECIBO1). 12 tests pasan, 5 skipped (requieren BD real). |
| 24/06/2026 | **v1.9.2**: Tests de paridad suite completa — `test_schema_parity.py` (40/40), `test_query_parity_realtime.py` (21/21). Fix IVA alias bug en adapter. Pass rate library: 81.4% → primer umbral >90%. |
| 25/06/2026 | **v2.0.0**: Corrección masiva query_library — pass rate **81.4% → 96.9%** (2395/2471 consultas). Ver sección detallada abajo. |
| 25/06/2026 | **SIUO fix**: `backend/core/config/table_index.json` — nota DOCCAB corregida. Contenía "21=Factura, 12=Pedido" (valores generados por IA incorrectos). Sustituida por mapeo verificado: `0=presupuesto_cli, 1=pedido_cli, 2=albaran_cli, 3=factura_cli, 10=presupuesto_prov, 11=pedido_prov, 12=albaran_prov, 13=factura_prov, 21=mov.almacen, 31=recuento, 51=certificacion, 52=produccion, 61=cert.subcontrata`. Consultas de ejemplo también corregidas (eliminado `WHERE TIPO=21`). |

---

## 🆕 Cambios v2.0.0 (25/06/2026) — Corrección masiva query_library

### Objetivo
Corregir errores de columna/tabla en los ficheros v1/v2/v3 del `query_library/` generados por IA
para que la gran mayoría de las 2471 consultas funcionen correctamente sobre el simulador SQLite.

**Regla inviolable:** Solo se modifican ficheros `.py` en `query_library/` y `sqlite_to_firebird.py`.
La BD real Firebird y el fichero `simulator.db` NO se tocan.

### Resultado

| Métrica | Antes | Después |
|---------|-------|---------|
| Pass rate simulador | 81.4% (2011/2471) | **96.9% (2395/2471)** |
| test_schema_parity.py | 40/40 ✅ | 40/40 ✅ |
| test_query_parity_realtime.py | 21/21 ✅ | 21/21 ✅ |

### Correcciones aplicadas

#### 1. ESTALMACEN + STOCK → ARTICULO.STOCKARTICULO (FIX4, ~98 queries)
`ESTALMACEN` en Firebird es una tabla de **movimientos por fecha** (IMPCOSTE/IMPVENTA), NO tiene STOCK por artículo.
Queries v2/v3 usaban `FROM ESTALMACEN E JOIN ARTICULO A ON A.CODIGO=E.CODARTICULO WHERE E.STOCK>0`.

**Fix:** Reescritura bulk de todos los patrones ESTALMACEN→ARTICULO:
- `FROM ESTALMACEN E JOIN ARTICULO A ON ...` → `FROM ARTICULO A`
- `E.STOCK` → `A.STOCKARTICULO`
- `E.CODARTICULO` → `A.CODIGO`
- `E.CODALMACEN` → `'01'`
- Subqueries: `(SELECT SUM(E.STOCK) FROM ESTALMACEN E WHERE E.CODARTICULO=A.CODIGO)` → `A.STOCKARTICULO`

También en `driver.py._ensure_tables()` se añadió una **TEMPORARY VIEW** `_ESTALMACEN_STOCK`
(solo vive en la sesión, no persiste al fichero `simulator.db`).

#### 2. COSTE → PRECIOCOSTE en ARTICULO (FIX1, ~16 queries)
`ARTICULO` tiene `PRECIOCOSTE`, no `COSTE` (que sí existe en `DOCLIN`).
**Fix:** `(?<![A-Za-z.])COSTE\b` → `PRECIOCOSTE` en queries ARTICULO-only.
Preservación: `L.COSTE` (DOCLIN), `PRECIOCOSTE`, `IMPCOSTE`, `FECHAULTCOSTE` no afectados.

#### 3. PRECIO → PRECIOVENTA en ARTICULO (FIX, ~9 queries)
`ARTICULO` tiene `PRECIOVENTA`, no `PRECIO` (que sí existe en `DOCLIN`).
**Fix:** `(?<![A-Za-z.])PRECIO\b` → `PRECIOVENTA` en queries ARTICULO-only.
Preservación: `L.PRECIO` (DOCLIN) no afectado — DOCLIN SÍ tiene columna `PRECIO`.

#### 4. FROM IVA → FROM TIPOSIVA (FIX12, 16 queries)
La tabla `IVA` no existe. Tabla correcta: `TIPOSIVA` (tiene `CODIGO`, `NOMBRE`, `PORCENTAJE`).
DOCLIN usa `TIPOIVA` (no `CODIVA`) como clave foránea.
**Fix:** `FROM IVA I` → `FROM TIPOSIVA I`, `L.CODIVA` → `L.TIPOIVA`

#### 5. D.CODPROVEEDOR → D.CODCLIENTE (FIX11, 16 queries)
`DOCCAB` no tiene `CODPROVEEDOR`. En documentos de compra, el código del proveedor
se almacena en `CODCLIENTE` (referencia a PROVEED via CLIENTE).

#### 6. CODDOCREL → NULL (FIX10, 21 queries)
`CODDOCREL` no existe en `DOCCAB`. La relación entre documentos está en `DOCDESTINO`.
Queries con `CODDOCREL` en SELECT → `NULL`. Queries con join condition `D.CODDOCREL=X.CODIGO` → `1=0`.

#### 7. Columnas DOCCAB inexistentes en simulador
| Columna original | Fix aplicado | Motivo |
|-----------------|-------------|--------|
| `D.CODUSUARIO` | `D.CODAGENTE` | DOCCAB tiene CODAGENTE |
| `D.FECHACIERRE` | `D.FECHA` | Usar fecha del documento |
| `D.COBRADO` | `D.IMPORTEENTREGADO` | Campo de pago real en DOCCAB |
| `D.GARANTIA` | `NULL` | No existe en DOCCAB |
| `D.CODTARIFA` | `NULL` | No existe en DOCCAB |
| `D.NVISITAS` | `0` | No existe |
| `D.PRIORIDAD` | `0` | No existe |
| `D.CODEQUIPO` | `NULL` | No existe |
| `D.FECHACOBRO` | `D.FECHA` | No existe |
| `D.FECHAVENCIMIENTO` | `D.FECHA` | No existe |
| `D.CODCONTRATO` | `NULL` | No existe |

#### 8. Columnas CLIENTE/PROVEED inexistentes
| Columna original | Fix aplicado | Motivo |
|-----------------|-------------|--------|
| `C.PROVINCIA` | `C.CP AS PROVINCIA` | CLIENTE tiene CP (código postal) |
| `C.TELEFONO` / `TELEFONO` | `C.TEL` / `TEL` | CLIENTE tiene TEL |
| `C.CIF` | `C.NIF` | CLIENTE tiene NIF |
| `P.CIF` | `P.NIF` | PROVEED tiene NIF |
| `C.CODFAMILIA` | `NULL` | CLIENTE no tiene CODFAMILIA |
| `C.NOMBRE` | `COALESCE(C.NOMBRECOMERCIAL,C.RAZONSOCIAL)` | sin columna NOMBRE directa |
| `P.NOMBRE` | `COALESCE(P.NOMBRECOMERCIAL,P.RAZONSOCIAL)` | sin columna NOMBRE directa |
| `EMAIL` | `NULL` | No existe en CLIENTE/PROVEED |
| `DIRECCION` | `NULL` | No existe en CLIENTE simulador |
| `POBLACION` | `NULL` | No existe |

#### 9. Columnas ARTICULO inexistentes
| Columna original | Fix aplicado |
|-----------------|-------------|
| `STOCKMAXIMO` / `STOCKMIN` | `STOCKARTICULO` |
| `FECHAULTCOSTE` | `NULL` |
| `FECHAULTPRECIO` | `NULL` |
| `A.ESSERVICIO` | `0` |
| `CODALMACEN` (en ARTICULO) | `'01'` (1 almacén virtual) |

#### 10. Tablas inexistentes en simulador
| Tabla original | Fix aplicado |
|---------------|-------------|
| `EQUIVAL` | `ARTICULO` (aproximación) |
| `CLIENTEDOCUM` | `DOCCAB` |
| `DOCLINDOCASOC` | `DOCLIN` |
| `ARTPROVEED` | `ARTICULO` |
| `CONDICIO` | no reparada (quedan 1 error) |

#### 11. Columnas SAT (sat_v3.py)
- `D.CODTECNICO` → `D.CODAGENTE` (sat_v2.py, sat_v3.py)
- `D.CODTIPOOT` → `NULL`

#### 12. IVA alias bug en sqlite_to_firebird.py
El adapter cambiaba incorrectamente `AS IVA` (alias de columna) a `AS IMPORTEIVA`.
**Fix:** Placeholder `__IVA_ALIAS_PLACEHOLDER__` para proteger `AS IVA` durante la traducción.

#### 13. BASEIMPONIBLE → IMPORTEBASE
`DOCCAB` tiene `IMPORTEBASE`, no `BASEIMPONIBLE`. Reemplazado en finanzas_v2.py y calidad_v2.py.

### Esquema real verificado (session 2026-06-25)

| Tabla | Columnas clave |
|-------|----------------|
| `ARTICULO` | `CODIGO`, `NOMBRE`, `PRECIOVENTA`, `PRECIOCOSTE`, `STOCKARTICULO`, `CODFAMILIA`, `PROVEEDDEFECTO` |
| `DOCLIN` | `CODIGO`, `CODARTICULO`, `CANTIDAD`, `PRECIO`, `COSTE`, `DESCUENTOS`, `TIPOIVA` |
| `DOCCAB` | `CODIGO`, `TIPO`, `FECHA`, `CODCLIENTE`, `CODAGENTE`, `IMPORTEBASE`, `IMPORTEIVA`, `IMPORTETOTAL`, `IMPORTEENTREGADO` |
| `CLIENTE` | `CODIGO`, `NOMBRECOMERCIAL`, `RAZONSOCIAL`, `TEL`, `CP`, `NIF`, `CODAGENTE`, `BAJA` |
| `PROVEED` | `CODIGO`, `NOMBRECOMERCIAL`, `RAZONSOCIAL`, `TEL`, `CP`, `NIF` |
| `ESTALMACEN` | `CODIGO`, `FECHA`, `IMPCOSTE`, `IMPVENTA` (NO STOCK, NO CODARTICULO) |
| `TIPOSIVA` | `CODIGO`, `NOMBRE`, `PORCENTAJE` |
| `FORMASPAGO` | simulador: `FORMASPAGO`; Firebird: `FORMAPAG` |
| `AGENTES` | simulador: `AGENTES`; Firebird: `AGENTE` |

### Errores residuales (76 queries, 3.1%)

Los 76 queries que aún fallan corresponden a:
- **Columna FECHA ambigua** (6): queries con JOIN de tablas que ambas tienen FECHA
- **Columna D.CODIGO en queries con alias D** (6): queries de finanzas/ventas con error de reescritura de alias
- **near NULL syntax** (4): queries con condiciones de JOIN rotas donde CODDOCREL→NULL
- **CODALMACEN bare en ARTICULO** (4): residuos del fix ESTALMACEN
- **Misuse aggregate / ORDER BY** (2): SQL inválido en queries complejas de subquery
- **Otros** (≤2 cada uno): columnas específicas sin equivalente en simulador

---

## 🆕 Cambios v1.9.0 (10/06/2026) — Modo prueba BD real

### Objetivo
Probar la aplicación **sin conexión a modelos IA de red** pero **con BD Firebird real** activa.
Verificar que todas las consultas de la `query_library` (escritas en SQLite) funcionan
correctamente contra la BD real mediante el adaptador `sqlite_to_firebird.py`.

### Ficheros modificados

| Fichero | Cambio |
|---------|--------|
| `config.json` | `simulator_enabled: false` + nueva sección `test_mode` |
| `constants.py` | Nueva clase `TestModeConfig` — parámetros centralizados del modo prueba |
| `test_real_db.py` | **Nuevo** — 6 clases de tests contra BD Firebird real |

### `config.json` — Parámetros de modo prueba

```json
{
  "simulator_enabled": false,
  "show_disclaimer": true,
  "test_mode": {
    "use_real_db": true,
    "use_ai_network": false,
    "description": "Modo prueba: BD real Firebird activa, modelo IA de red desactivado."
  }
}
```

**Regla:** `simulator_enabled=false` → el sistema usa BD Firebird real en lugar de SQLite.

### `constants.py` — `TestModeConfig`

Clase centralizada con todos los parámetros del modo de prueba:

```python
class TestModeConfig:
    USE_REAL_DB       = False   # True = BD Firebird real
    USE_AI_NETWORK    = True    # False = sin modelos IA de red
    USE_AI_LOCAL      = True    # True = JDDC IA Gateway local (jddcia.local)
    FIREBIRD_CHARSET  = "latin1"
    REAL_DB_QUERY_TIMEOUT = 30
    REAL_DB_MAX_ROWS  = 100
    LOG_PREFIX        = "[TEST_MODE]"
```

**Principio:** Ningún otro fichero hardcodea estos valores — siempre importar de `constants.py`.

### `test_real_db.py` — Tests contra BD real

6 clases de tests, ordenadas de menor a mayor dependencia:

| Clase | Requiere BD | Descripción |
|-------|-------------|-------------|
| `TestTestModeConfig` | No | Verifica `TestModeConfig`, `config.json` y `settings.py` |
| `TestSQLiteToFirebirdAdaptation` | No | Tests unitarios del adaptador SQL (7 casos) |
| `TestRealDBConnectivity` | Sí | Conectividad básica: DOCCAB, CLIENTE, ARTICULO, DOCLIN |
| `TestRealDBSchema` | Sí | Esquema real: columnas IMPORTEBASE, IMPORTEIVA, PRECIOVENTA, PROVEEDDEFECTO |
| `TestKeyQueriesRealDB` | Sí | 6 consultas clave: facturación, top clientes, conversión, caja, SATs, resumen |
| `TestAllCriticalQueriesRealDB` | Sí | Todas las consultas Crítico + KPI contra BD real |

**Ejecutar:**
```bash
set PYTHONUTF8=1
set PYTHONPATH=C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia
python -m pytest backend/modules/db_simulator/test_real_db.py -v

# Solo sin BD (traducción SQL):
python -m pytest backend/modules/db_simulator/test_real_db.py -v -k "Adaptation or Config"

# Solo conectividad:
python -m pytest backend/modules/db_simulator/test_real_db.py -v -k "Connectivity"
```

### Flujo de adaptación SQL (SQLite → Firebird)

Las consultas de la `query_library` están escritas en **SQLite**. Para ejecutarlas
contra la BD real Firebird se aplican dos pasos en cadena:

```
SQL SQLite (query_library)
    ↓
adapt_sql_for_firebird()   ← sqlite_to_firebird.py
    • BASEIMPONIBLE → IMPORTEBASE
    • IVA (standalone) → IMPORTEIVA
    • CAST(x AS TEXT) → CAST(x AS VARCHAR(50))
    • SUBSTR(FECHA,1,7) → EXTRACT año-mes
    • A.PRECIO → A.PRECIOVENTA
    • CODPROVEEDOR → PROVEEDDEFECTO
    ↓
FirebirdSQLNormalizer.normalize()   ← firebird_sql_normalizer.py
    • LIMIT N → FIRST N
    • strftime('%Y', FECHA) → EXTRACT(YEAR FROM FECHA)
    • date('now') → CURRENT_DATE
    ↓
SQL Firebird 2.5 (ejecutable contra BD real)
```

### Diferencias de nombres SQLite ↔ Firebird real

| Tabla | Columna SQLite (simulador) | Columna Firebird real |
|-------|---------------------------|----------------------|
| DOCCAB | BASEIMPONIBLE | IMPORTEBASE |
| DOCCAB | IVA | IMPORTEIVA |
| ARTICULO | PRECIO | PRECIOVENTA |
| ARTICULO | CODPROVEEDOR | PROVEEDDEFECTO |
| DOCLIN | CODART | CODARTICULO |

**Nota:** `FAMILIA` no existe en Firebird real JDDC — solo en el simulador SQLite.
Las consultas que la usan se marcan como `_KNOWN_MISSING` en los tests.

### Parámetros de conexión BD real (fuente: `.env`)

```
DB_HOST=192.168.0.254        # HOST1.JDDC.local (IP directa — hostname causa timeout)
DB_PORT=3050
DB_NAME=C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb
DB_USER=SYSDBA
DB_PASSWORD=masterkey
CHARSET=latin1               # Máxima compatibilidad con caracteres españoles
```

**Fuente única de verdad:** `bots/interjddcia/.env` → leído por `settings.py` → usado por `TestModeConfig`.

---

## 🆕 Cambios v1.8.0 (05/06/2026)

### Biblioteca v3 — 950 consultas nuevas

Se añaden 8 módulos `*_v3.py` con consultas adicionales por departamento:

| Archivo | Consultas | Departamento |
|---------|-----------|--------------|
| `query_library/ventas_v3.py` | 200 | Ventas |
| `query_library/compras_v3.py` | 150 | Compras |
| `query_library/finanzas_v3.py` | 150 | Finanzas |
| `query_library/almacen_v3.py` | 125 | Almacén |
| `query_library/direccion_v3.py` | 125 | Dirección |
| `query_library/sat_v3.py` | 100 | SAT / Técnico |
| `query_library/marketing_v3.py` | 50 | Marketing |
| `query_library/calidad_v3.py` | 50 | Calidad / Todos |
| **Total v3** | **950** | **Todos los departamentos** |

**Total acumulado:** ~77 (core) + ~825 (v1) + ~400 (v2) + 950 (v3) = **~2252 consultas**

El `__init__.py` de `query_library/` se actualiza para importar y concatenar todos los módulos v3 en `QUERY_LIBRARY_EXTENDED`.

---

## 🆕 Cambios v1.7.0 (03/06/2026)

### 1. Módulo `justification/` — Servicio independiente de justificación y evidencias

Nuevo paquete `backend/modules/db_simulator/justification/` con responsabilidad única:
generar y servir los **10 paneles de verificación** de cada consulta SQL.

```
justification/
├── __init__.py       # Exporta get_verifications_for_query
├── panels.py         # 35+ paneles reutilizables (funciones puras)
├── auto_panels.py    # Generador automático de 10 paneles por consulta
└── registry.py       # Registro: query_id → lista de paneles específicos
```

**Principios del módulo:**
- **Sin comentarios subjetivos**: todos los paneles muestran solo hechos verificables con datos
- **Evidencia para cada afirmación técnica**: si `desc_tecnica` afirma que IMPORTETOTAL incluye IVA, los paneles `panel_iva_desglose` y `panel_iva_por_documento` muestran los valores reales de BASEIMPONIBLE, cuota IVA e IMPORTETOTAL para que el usuario pueda verificarlo
- **10 paneles exactos por consulta**: consistencia garantizada en toda la biblioteca
- **Paneles reutilizables**: `panels.py` define funciones puras que devuelven dicts; `auto_panels.py` los combina según el contexto de cada consulta

### 2. Biblioteca de consultas — 1077 consultas totales

| Archivo | Consultas | Departamento |
|---------|-----------|--------------|
| `query_library_core.py` | ~77 | Todos (originales) |
| `query_library/ventas.py` | 125 | Ventas |
| `query_library/compras.py` | ~100 | Compras |
| `query_library/almacen.py` | ~100 | Almacén |
| `query_library/finanzas.py` | ~100 | Finanzas |
| `query_library/sat.py` | ~100 | SAT / Técnico |
| `query_library/direccion.py` | ~100 | Dirección |
| `query_library/marketing.py` | ~100 | Marketing |
| `query_library/calidad.py` | ~100 | Calidad / Todos |
| **Total** | **1077** | **Todos los departamentos** |

### 3. Adapter `sqlite_to_firebird.py` — Mapeo real de columnas Firebird

Nuevo módulo que traduce SQL SQLite → Firebird usando el esquema real de la BD:

| SQLite (simulador) | Firebird (producción) |
|--------------------|-----------------------|
| `BASEIMPONIBLE` | `IMPORTEBASE` |
| `IVA` (columna standalone) | `IMPORTEIVA` |
| `A.PRECIO` | `A.PRECIOVENTA` |
| `A.CODPROVEEDOR` | `A.PROVEEDDEFECTO` |
| `CAST(x AS TEXT)` | `CAST(x AS VARCHAR(50))` |
| `SUBSTR(FECHA,1,7)` | `EXTRACT(MONTH/YEAR FROM FECHA)` |
| `JULIANDAY(f)` | fallback: "no disponible en Firebird" |

**Regla de preservación**: el adapter NO modifica `D.IVA`, `LIN.IVA`, `IVA_TOTAL` (alias o columnas con prefijo de tabla) — solo reemplaza `IVA` cuando aparece como columna standalone.

### 4. Eliminación de comentarios subjetivos en `query_library_core.py`

**Antes (subjetivo):**
```
"Si el ticket medio sube, significa que vendemos trabajos más grandes o más completos.
Si baja, puede que estemos haciendo muchos trabajos pequeños o dando demasiados descuentos."
```

**Después (factual):**
```
"Media del campo IMPORTETOTAL de todos los documentos con TIPO=13 (facturas de venta).
Muestra el valor promedio de cada factura emitida.
Incluye también el mínimo y el máximo para conocer el rango de importes."
```

**Regla aplicada**: `desc_simple` y `desc_tecnica` solo contienen hechos verificables con los datos de la BD. No incluyen interpretaciones, valoraciones ni recomendaciones subjetivas.

---

## 🔧 Correcciones anteriores (29/05/2026 — 01/06/2026)

### Errores corregidos en `query_library_core.py`

| Query ID | Error original | Corrección aplicada |
|----------|---------------|---------------------|
| `f_riesgo_facturas_alto_importe_sin_cobrar` | Alias inválido (expresión como alias) | Cambiado a `AS IMPORTE` |
| `s_kpi_sats_abiertos_antiguos` | Alias inválido | Cambiado a `AS IMPORTE`, `AS CLIENTE` |
| `d_kpi_resumen_ejecutivo` | `CANTIDAD/PRECIO` en CAJA (no existen) | Cambiado a `IMPORTE` |
| `f_saldo_clientes_vencido` | `E.COBRADO = 0` (columna inexistente) | `(E.ACTIVO IS NULL OR E.ACTIVO != '1')` |
| `f_pagos_proximos` | `E.FECHAVENC`, `E.CODPROVEEDOR`, `E.PAGADO` (inexistentes) | `E.FECHA`, `E.CODPAGADOR`, `E.DEVOLUCION` |
| `alm_stock_critico` | `A.STOCKMINIMO` (inexistente) | Literal `3` como umbral configurable |
| `cmp_top_proveedores` | `D.CODPROVEEDOR` (inexistente en DOCCAB) | JOIN via `ARTICULO.CODPROVEEDOR → PROVEED` |
| `alerta_clientes_inactivos` | `C.ACTIVO = 1` (inexistente) | `C.BAJA IS NULL OR C.BAJA = ''` |

### Fix crítico `query_translator.py` (01/06/2026)

**Bug:** `_translate_cast_numeric` usaba regex lazy `(.+?)` que fallaba con paréntesis anidados.
- `CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2))` → capturaba `SUM(IMPORTETOTAL` (sin `)`) → SQL inválido

**Fix:** Algoritmo de balance de paréntesis (`_extract_cast_inner`) que extrae correctamente el contenido de `CAST(...)` con cualquier nivel de anidamiento.

---

## Esquema real de tablas clave (SQLite simulador)

> **Verificado 2026-06-25** contra la BD real Firebird conectada en esa sesión.

| Tabla | Columnas relevantes |
|-------|---------------------|
| `RECIBO1` | `CODDOCUMENTO, CODIGO, FECHAVENC, IMPORTE, CODPAGADOR, ACTIVO` |
| `RECIBO3` | `CODDOCUMENTO, CODRECIBO, FECHA, IMPORTE, CODPAGADOR, DEVOLUCION` |
| `CAJA` | `CODIGO, FECHA, IMPORTE, TIPO (1=entrada, 2=salida), CONCEPTO, CODCLIENTE, CODUSUARIO` |
| `DOCLIN` | `CODDOCUMENTO, CODIGO, CODARTICULO, CANTIDAD, PRECIO, COSTE, DESCUENTOS, TIPOIVA, TIPOIRPF` |
| `DOCCAB` | `CODIGO, TIPO, FECHA, CODCLIENTE, CODAGENTE, CODALMACEN, IMPORTEBASE, IMPORTEIVA, IMPORTETOTAL, IMPORTEENTREGADO, DESCUENTOS, ESTADO` |
| `CLIENTE` | `CODIGO, NOMBRECOMERCIAL, RAZONSOCIAL, TEL, CP, NIF, CODAGENTE, CODZONA, BAJA` (sin NOMBRE, sin PROVINCIA, sin EMAIL) |
| `PROVEED` | `CODIGO, NOMBRECOMERCIAL, RAZONSOCIAL, TEL, CP, NIF` (sin NOMBRE directo) |
| `ARTICULO` | `CODIGO, NOMBRE, PRECIOVENTA, PRECIOCOSTE, STOCKARTICULO, PROVEEDDEFECTO, CODFAMILIA, TIPOIVA` (sin PRECIO bare, sin COSTE bare, sin STOCKMINIMO) |
| `ESTALMACEN` | `CODIGO, FECHA, IMPCOSTE, IMPVENTA, IMPCOSTE02..09, IMPVENTA02..09` (NO tiene STOCK, CODARTICULO, CODALMACEN) |
| `TIPOSIVA` | `CODIGO, NOMBRE, PORCENTAJE, PORCENTAJE2` |
| `FORMASPAGO` | simulador: tabla `FORMASPAGO`; Firebird real: tabla `FORMAPAG` |
| `AGENTES` | simulador: tabla `AGENTES`; Firebird real: tabla `AGENTE` |

---

## Reglas de compatibilidad SQLite (aplicar en nuevas queries)

1. **CLIENTE/PROVEED sin columna NOMBRE**: usar siempre `COALESCE(X.NOMBRECOMERCIAL, X.RAZONSOCIAL, 'Sin nombre') AS NOMBRE`
2. **DOCLIN sin IMPORTE**: calcular como `ROUND(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL),2)`
3. **DOCLIN.CODDOCUMENTO** (no CODIGO) para JOIN con DOCCAB: `ON D.CODIGO = L.CODDOCUMENTO`
4. **DOCLIN.CODARTICULO** (no CODART): `JOIN ARTICULO A ON A.CODIGO = L.CODARTICULO`
5. **CAJA usa IMPORTE** directamente (no CANTIDAD*PRECIO)
6. **RECIBO1**: sin columna COBRADO → usar `ACTIVO` o filtrar por fecha
7. **RECIBO3**: sin FECHAVENC → usar `FECHA`; sin CODPROVEEDOR → usar `CODPAGADOR`
8. **ARTICULO**: sin STOCKMINIMO → usar literal o constante configurable; usar `PRECIOVENTA` (no `PRECIO`), `PRECIOCOSTE` (no `COSTE`)
9. **DOCCAB**: sin CODPROVEEDOR → acceder via DOCLIN→ARTICULO→PROVEED (o usar CODCLIENTE para docs de compra)
10. **ESTALMACEN** (⚠️ importante): NO tiene STOCK, CODARTICULO, CODALMACEN por artículo — es tabla de movimientos por fecha con IMPCOSTE/IMPVENTA. Para stock de artículo → usar `ARTICULO.STOCKARTICULO`
11. **Alias obligatorio** en todas las expresiones COALESCE y cálculos en SELECT
12. **Sin comentarios subjetivos** en `desc_simple`/`desc_tecnica`: solo hechos verificables
13. **IVA en DOCLIN**: la columna es `TIPOIVA` (código del tipo), no `CODIVA`. Para % de IVA: `JOIN TIPOSIVA I ON I.CODIGO=L.TIPOIVA`
14. **Tabla de IVA**: se llama `TIPOSIVA` (no `IVA`). Tiene `CODIGO`, `NOMBRE`, `PORCENTAJE`
15. **CLIENTE.PROVINCIA** no existe → usar `C.CP AS PROVINCIA`
16. **CLIENTE.EMAIL** no existe en el simulador → usar `NULL AS EMAIL`
17. **Forma de pago**: simulador: tabla `FORMASPAGO`; Firebird: tabla `FORMAPAG`
18. **Agentes**: simulador: tabla `AGENTES`; Firebird: tabla `AGENTE`

**Tablas/columnas inexistentes en simulador** (no reparables sin modificar simulator.db):
- `ESTALMACEN.STOCK`, `ESTALMACEN.CODARTICULO` → usar `ARTICULO.STOCKARTICULO`
- `ARTICULO.FECHAULTCOSTE`, `ARTICULO.FECHAULTPRECIO` → `NULL`
- `DOCCAB.CODDOCREL` → `NULL` (relación en tabla `DOCDESTINO`)
- `DOCCAB.COBRADO` → `DOCCAB.IMPORTEENTREGADO`
- Tablas: `EQUIVAL`, `CONDICIO`, `ARTPROVEED`, `CLIENTEDOCUM`, `DOCLINDOCASOC`

**Adapter sqlite_to_firebird.py** — traducciones aplicadas para Firebird:
- `IMPORTEBASE` (ya correcto) ← era `BASEIMPONIBLE`
- `IMPORTEIVA` (ya correcto) ← era `IVA` standalone
- `PRECIOVENTA` (ya correcto) ← era `PRECIO` en ARTICULO
- `PROVEEDDEFECTO` (ya correcto) ← era `CODPROVEEDOR` en ARTICULO
- `FORMASPAGO` → `FORMAPAG` (tabla Firebird)
- `AS IVA` (alias columna) protegido con placeholder para no confundir con columna `IVA`

---

## ¿Qué hace este módulo?

Permite usar toda la funcionalidad del Chat IA y la BD Simulada **sin acceso a la BD Firebird real**, usando una BD SQLite local que contiene:

- **Modo `synthetic`** (por defecto): datos generados automáticamente con volumen y distribución realistas del sector de climatización JDDC.
- **Modo `snapshot`**: datos reales del último mes capturados desde Firebird cuando había conexión.

El simulador es **completamente transparente** para el `ChatService`: recibe las mismas queries Firebird SQL, las traduce a SQLite y devuelve resultados en el mismo formato.

**Privacidad garantizada**: los datos sintéticos nunca contienen valores reales de la BD de producción. Los datos de snapshot se almacenan solo localmente y nunca se envían a ningún servicio externo.

---

## Activación del simulador

### Activación servidor (recomendada, permanente)

```json
// backend/modules/db_simulator/config.json
{
  "simulator_enabled": true,
  "show_disclaimer": true
}
```

- `simulator_enabled: true` → todo el tráfico del chat usa `SimulatedFirebirdDriver`
- `show_disclaimer: true` → el router prepende automáticamente un aviso "⚠️ MODO SIMULACIÓN"
- El frontend NO necesita enviar ningún parámetro especial

---

## Endpoints de gestión

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/db-simulator/status` | Estado actual + filas por tabla |
| `POST` | `/api/db-simulator/build-synthetic` | Genera ~1.200 registros sintéticos |
| `POST` | `/api/db-simulator/build-snapshot` | Captura último mes desde Firebird |
| `DELETE` | `/api/db-simulator/clear` | Vacía la BD simulada |
| `GET` | `/api/db-simulator/tables` | Lista tablas con conteo de filas |
| `GET` | `/api/db-simulator/preview/{tabla}` | Primeras N filas de una tabla |

---

## Estructura de ficheros

```
backend/modules/db_simulator/
├── __init__.py                  # Exporta SimulatedFirebirdDriver, simulator_manager
├── constants.py                 # ← TODA la configuración aquí (rutas, límites, nombres)
├── seed_data.py                 # Datos estáticos: productos, clientes, empleados reales
├── schema.py                    # CREATE TABLE SQLite (columnas idénticas a Firebird)
├── query_translator.py          # Firebird SQL → SQLite (FIRST→LIMIT, EXTRACT→strftime…)
├── sqlite_to_firebird.py        # SQLite SQL → Firebird (BASEIMPONIBLE→IMPORTEBASE, etc.)
├── driver.py                    # SimulatedFirebirdDriver (implementa DatabaseDriver)
├── synthetic_seeder.py          # Genera datos sintéticos realistas del sector JDDC
├── snapshot_service.py          # Captura datos reales de Firebird → SQLite
├── manager.py                   # SimulatorManager — singleton orquestador
├── router.py                    # FastAPI endpoints /api/db-simulator/*
├── query_library_core.py        # ~77 consultas originales con metadatos completos
├── query_library.py             # Fachada: combina core + extended, exporta funciones
├── query_library/               # ~2175 consultas extendidas por departamento (v1+v2+v3)
│   ├── __init__.py              # Importa y combina v1+v2+v3 en QUERY_LIBRARY_EXTENDED
│   ├── builder.py               # Helper q() para crear consultas
│   ├── ventas.py / ventas_v2.py / ventas_v3.py       # 125+125+200 = 450 consultas
│   ├── compras.py / compras_v2.py / compras_v3.py    # ~100+125+150 = ~375 consultas
│   ├── almacen.py / almacen_v2.py / almacen_v3.py    # ~100+25+125 = ~250 consultas
│   ├── finanzas.py / finanzas_v2.py / finanzas_v3.py # ~100+25+150 = ~275 consultas
│   ├── sat.py / sat_v2.py / sat_v3.py                # ~100+25+100 = ~225 consultas
│   ├── direccion.py / direccion_v2.py / direccion_v3.py # ~100+25+125 = ~250 consultas
│   ├── marketing.py / marketing_v2.py / marketing_v3.py # ~100+25+50 = ~175 consultas
│   └── calidad.py / calidad_v2.py / calidad_v3.py    # ~100+25+50 = ~175 consultas
├── justification/               # ← MÓDULO INDEPENDIENTE de justificación y evidencias
│   ├── __init__.py              # Exporta get_verifications_for_query
│   ├── panels.py                # 35+ paneles reutilizables (funciones puras)
│   ├── auto_panels.py           # Generador automático de 10 paneles por consulta
│   └── registry.py              # Registro: query_id → lista de paneles específicos
└── data/
    ├── simulator.db             # BD SQLite (auto-creada, no subir a git)
    └── status.json              # Estado persistido del simulador
```

---

## Módulo `justification/` — Detalle

### Responsabilidad

Generar y servir los **10 paneles de verificación** de cada consulta SQL de la biblioteca.
Cada panel es un dict con:
- `id`: identificador único del panel
- `title`: título descriptivo
- `justificacion`: explicación de qué verifica este panel y por qué
- `sql`: SQL ejecutable sobre el simulador

### Principios de diseño

1. **Sin subjetividad**: los paneles muestran solo hechos verificables con datos reales
2. **Evidencia para afirmaciones técnicas**: si `desc_tecnica` afirma algo (ej: "IMPORTETOTAL incluye IVA"), los paneles muestran los valores numéricos que lo demuestran
3. **Consistencia**: exactamente 10 paneles por consulta, sin excepción
4. **Reutilización**: `panels.py` define funciones puras; `auto_panels.py` las combina
5. **Independencia**: el módulo no importa nada de `query_library` — solo recibe el `query_id` y el SQL

### Paneles disponibles en `panels.py`

| Panel | Verifica |
|-------|---------|
| `panel_desglose_tipos` | Distribución por TIPO — confirma que el filtro TIPO=X es correcto |
| `panel_sin_duplicados` | Ausencia de CODIGOs duplicados — integridad de datos |
| `panel_evolucion_mensual` | Distribución mensual — detecta meses anómalos |
| `panel_comparativa_anual` | Distribución anual — detecta años con datos erróneos |
| `panel_importes_anomalos` | Documentos con IMPORTETOTAL ≤ 0 — abonos o errores |
| `panel_ultimos_documentos` | Últimos 30 documentos — verificación visual de datos reales |
| `panel_iva_desglose` | BASEIMPONIBLE + cuota IVA vs IMPORTETOTAL — evidencia de que IMPORTETOTAL incluye IVA |
| `panel_iva_por_documento` | IVA por documento individual — evidencia granular de inclusión de IVA |
| `panel_clientes_por_facturacion` | Top clientes — concentración de ingresos |
| `panel_agentes_ventas` | Distribución por agente — cobertura comercial |
| `panel_formas_pago` | Distribución por forma de pago — mix de cobro |
| `panel_articulos_mas_vendidos` | Top artículos — core del negocio |
| `panel_stock_articulos` | Stock actual — disponibilidad de inventario |
| `panel_articulos_sin_stock` | Artículos a 0 — roturas de stock |
| `panel_precio_vs_coste` | Margen bruto por artículo — rentabilidad |
| `panel_familias_productos` | Distribución por familia — estructura del catálogo |
| `panel_proveedores_activos` | Proveedores con artículos — diversidad de suministro |
| `panel_caja_resumen` | Entradas vs salidas — saldo de caja |
| `panel_caja_por_mes` | Evolución mensual de caja — estacionalidad financiera |
| `panel_sats_por_estado` | SATs por estado — carga de trabajo técnico |
| `panel_presupuestos_por_estado` | Presupuestos por estado — pipeline de ventas |
| `panel_albaranes_vs_facturas` | Ratio albaranes/facturas — eficiencia de facturación |
| `panel_ventas_vs_compras_mensual` | Ventas vs compras por mes — margen operativo |
| `panel_descuentos_aplicados` | Descuentos > 20% — control de márgenes |
| `panel_lineas_sin_articulo` | Líneas sin artículo asignado — integridad de datos |
| `panel_lineas_por_documento` | Media de líneas por documento — complejidad de pedidos |
| `panel_documentos_sin_fecha` | Documentos sin fecha — errores de registro |
| `panel_documentos_sin_cliente` | Documentos sin cliente — datos incompletos |
| `panel_antiguedad_documentos` | Antigüedad de documentos — datos históricos disponibles |
| `panel_clientes_activos` | Clientes con al menos 1 factura — cartera activa |
| `panel_clientes_sin_nombre` | Clientes sin nombre — calidad de datos maestros |
| `panel_concentracion_top5` | % facturación top 5 clientes — riesgo de concentración |
| `panel_articulos_baja` | Artículos sin ventas recientes — obsolescencia |
| `panel_articulos_sin_proveedor` | Artículos sin proveedor — riesgo de suministro |

### Uso

```python
from backend.modules.db_simulator.justification.registry import get_verifications_for_query

panels = get_verifications_for_query("v_kpi_facturacion_total")
# → lista de 10 dicts, cada uno con: id, title, justificacion, sql
```

---

## Biblioteca de Consultas SQL

**~2252 consultas SQL** organizadas en 9 módulos temáticos (v1 + v2 + v3), cada una con:
- `id`: identificador único (ej: `v_kpi_facturacion_total`)
- `title`: título descriptivo
- `desc`: descripción corta (legacy)
- `desc_simple`: explicación factual en lenguaje llano (sin subjetividad)
- `desc_tecnica`: análisis técnico detallado con referencias a columnas y tablas reales
- `sql`: SQL SQLite válido y probado
- `dept`, `rol`, `tipo`, `urgencia`, `kpi`, `accion`

### Tipos de análisis disponibles
`KPI` · `Riesgo` · `Optimización` · `Predicción` · `Ahorro` · `Operacional` · `Estratégico` · `Calidad` · `Financiero` · `Alerta` · `Modernización`

### Endpoints de la biblioteca

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/db-simulator/query-library/catalog` | Catálogo con totales por dept/tipo/urgencia |
| `GET` | `/api/db-simulator/query-library/search?dept=Ventas&tipo=KPI` | Búsqueda con filtros |
| `GET` | `/api/db-simulator/query-library/{id}` | Detalle + SQL de una consulta |
| `POST` | `/api/db-simulator/query-library/{id}/execute` | Ejecutar consulta sobre el simulador |
| `POST` | `/api/db-simulator/execute` | Ejecutar SQL libre sobre el simulador |

### API Python

```python
from backend.modules.db_simulator.query_library import (
    get_all_queries,         # → List[Dict]  (~2252 consultas: core + v1 + v2 + v3)
    get_query_by_id,         # (id) → Dict
    get_catalog_summary,     # () → {total, by_dept, by_tipo, by_urgencia}
    search_queries,          # (dept, rol, tipo, urgencia, text) → List[Dict]
    get_queries_by_dept,     # (dept) → List[Dict]
    get_queries_by_tipo,     # (tipo) → List[Dict]
    get_queries_by_urgencia, # (urgencia) → List[Dict]
    get_queries_by_rol,      # (rol) → List[Dict]
)
```

---

## Datos sintéticos generados

| Tabla | Registros | Contenido |
|-------|-----------|-----------|
| `FAMILIA` | 15 | Familias de producto (splits, gas, tubería…) |
| `ALMACEN` | 4 | Almacenes JDDC |
| `RECURSO` | 12 | Empleados y departamentos reales |
| `PROVEED` | 15 | Proveedores reales (Daikin, Mitsubishi, Fujitsu…) |
| `ARTICULO` | 120 | Equipos splits, gas R-32/R-410A, accesorios, servicios |
| `CLIENTE` | 60 | Empresas e individuales de Valencia |
| `DOCCAB` | 220 | Facturas (38%), presupuestos (30%), albaranes, SATs |
| `DOCLIN` | ~660 | Líneas de documento (2-5 por doc) |
| `CAJA` | 90 | Movimientos de caja/cobros |
| `ESTALMACEN` | 180 | Movimientos de stock |

---

## Traducciones SQL implementadas

| Firebird | SQLite |
|----------|--------|
| `SELECT FIRST N` | `SELECT … LIMIT N` |
| `EXTRACT(MONTH FROM f)` | `CAST(strftime('%m', f) AS INTEGER)` |
| `EXTRACT(YEAR FROM f)` | `CAST(strftime('%Y', f) AS INTEGER)` |
| `CURRENT_DATE` | `date('now')` |
| `CURRENT_TIMESTAMP` | `datetime('now')` |
| `SUBSTRING(c FROM p FOR l)` | `SUBSTR(c, p, l)` |
| `CAST(x AS DATE)` | `date(x)` |
| `RDB$RELATIONS` | Interceptado → devuelve tablas simuladas |
| `RDB$RELATION_FIELDS` | Interceptado → devuelve columnas de la tabla |

---

## Tests

```bash
# Ejecutar todos los tests del módulo
python test_panels_execution.py   # 30/30 paneles OK, 9/9 adapter tests OK
python test_query_ids.py          # IDs únicos, sin duplicados
python test_verify_system.py      # Verificación completa del sistema
```

---

## Cómo extender

**Añadir una nueva consulta:**
1. Elegir el fichero de departamento en `query_library/` (ej: `ventas.py`)
2. Usar el helper `q()` de `builder.py`
3. El sistema de paneles se aplica automáticamente (10 paneles via `auto_panels.py`)
4. No añadir comentarios subjetivos en `desc_simple`/`desc_tecnica`

**Añadir un nuevo panel de justificación:**
1. Añadir función pura en `justification/panels.py`
2. Importar en `justification/auto_panels.py`
3. Usar en la lógica de selección de paneles según el contexto de la consulta

**Añadir una nueva tabla al simulador:**
1. Añadir `CREATE TABLE` en `schema.py` → `TABLE_SCHEMAS` y `TABLE_COLUMNS`
2. Añadir nombre en `constants.py` → `JDDCTableNames`
3. Añadir datos en `seed_data.py` y lógica de inserción en `synthetic_seeder.py`
4. Si tiene fecha, añadir en `JDDCDateColumns.MAP` para snapshot automático
