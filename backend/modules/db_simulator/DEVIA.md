# DEVIA — Módulo `db_simulator`
## Simulador de BD Firebird para trabajo offline

> **Ruta:** `backend/modules/db_simulator/`  
> **Versión:** 1.5.0  
> **Fecha:** 2026-06-01  
> **Estado:** ✅ Implementado y funcional — 1464 tests OK, 0 fallos, 67 omitidos (integración sin servidor)

## 📚 Documentación de sesiones

| Sesión | Archivo | Contenido |
|--------|---------|-----------|
| 20/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Fix HTTP 500 query_library truncado, filtros UI vacíos |
| 21/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Context Manager v3.0, fix _execute_sql bloqueante |
| 21/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Tests 40/40 ✅: get_queries_by_rol, catalog_summary aliases, Firebird-only handling |
| 29/05/2026 | `DEVIA.md` | Auditoría completa query_library: 0 fallos SQL, correcciones contextuales aplicadas |
| 01/06/2026 | `DEVIA.md` | Fix crítico `query_translator.py`: `_translate_cast_numeric` con balance de paréntesis para `CAST(SUM(col) AS NUMERIC(15,2))` |

## 🔧 Correcciones aplicadas (29/05/2026)

### Errores corregidos en `query_library.py`

| Query ID | Error original | Corrección aplicada |
|----------|---------------|---------------------|
| `f_riesgo_facturas_alto_importe_sin_cobrar` | `AS ROUND(CAST(CANTIDAD AS REAL)*...)` — alias inválido (expresión como alias) | Cambiado a `AS IMPORTE`, `ORDER BY D.IMPORTETOTAL` |
| `s_kpi_sats_abiertos_antiguos` | `AS ROUND(CAST(CANTIDAD AS REAL)*...)` — alias inválido | Cambiado a `AS IMPORTE`, alias `AS CLIENTE` añadido |
| `d_kpi_resumen_ejecutivo` | `ROUND(CAST(CANTIDAD AS REAL)*CAST(PRECIO AS REAL),2)` en CAJA — CAJA no tiene CANTIDAD/PRECIO | Cambiado a `IMPORTE` (columna real de CAJA) |
| `f_saldo_clientes_vencido` | `E.COBRADO = 0` — columna inexistente en RECIBO1 | Cambiado a `(E.ACTIVO IS NULL OR E.ACTIVO != '1')` |
| `f_pagos_proximos` | `E.FECHAVENC`, `E.CODPROVEEDOR`, `E.PAGADO`, `R.FECHAVENC` — columnas/alias inexistentes en RECIBO3 | Cambiado a `E.FECHA`, `E.CODPAGADOR`, `E.DEVOLUCION`, alias `E.` |
| `alm_stock_critico` | `A.STOCKMINIMO` — columna inexistente en ARTICULO | Sustituido por literal `3` como umbral mínimo configurable |
| `cmp_top_proveedores` | `D.CODPROVEEDOR` — columna inexistente en DOCCAB | Reescrita: JOIN via ARTICULO.CODPROVEEDOR → PROVEED |
| `alerta_clientes_inactivos` | `C.ACTIVO = 1` — columna inexistente en CLIENTE | Cambiado a `C.BAJA IS NULL OR C.BAJA = ''` |
| `v_kpi_top10_clientes` | COALESCE sin alias `AS NOMBRE` | Añadido `AS NOMBRE` |
| `mod_segmentacion_rfm` | COALESCE sin alias `AS NOMBRE` | Añadido `AS NOMBRE` |
| `f_ahorro_descuentos_excesivos` | Expresión sin alias en SELECT | Añadido `AS IMPORTE_CON_DTO`, lógica de descuento corregida |

### Esquema real de tablas clave (SQLite simulador)

| Tabla | Columnas relevantes |
|-------|---------------------|
| `RECIBO1` | `CODDOCUMENTO, CODIGO, FECHAVENC, IMPORTE, CODPAGADOR, ACTIVO` |
| `RECIBO3` | `CODDOCUMENTO, CODRECIBO, FECHA, IMPORTE, CODPAGADOR, DEVOLUCION` |
| `CAJA` | `CODIGO, FECHA, IMPORTE, TIPO (1=entrada, 2=salida), CONCEPTO` |
| `DOCLIN` | `CODDOCUMENTO, CODIGO, CODARTICULO, CANTIDAD, PRECIO, DESCUENTOS` |
| `DOCCAB` | `CODIGO, TIPO, FECHA, CODCLIENTE, CODAGENTE, IMPORTETOTAL, ESTADO` |
| `CLIENTE` | `CODIGO, NOMBRECOMERCIAL, RAZONSOCIAL, TEL, BAJA` (sin ACTIVO, sin NOMBRE) |
| `PROVEED` | `CODIGO, NOMBRECOMERCIAL, RAZONSOCIAL, TEL` (sin NOMBRE directo) |
| `ARTICULO` | `CODIGO, NOMBRE, PRECIO, PRECIOCOSTE, STOCKARTICULO, CODPROVEEDOR, CODFAMILIA` (sin STOCKMINIMO) |
| `ESTALMACEN` | `CODIGO, FECHA, IMPCOSTE, IMPVENTA` |

### Fix crítico query_translator.py (01/06/2026)

**Bug:** `_translate_cast_numeric` usaba regex lazy `(.+?)` que fallaba con paréntesis anidados.
- `CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2))` → capturaba `SUM(IMPORTETOTAL` (sin `)`) → SQL inválido
- `EXTRACT(YEAR FROM FECHA) AS ANO, CAST(SUM(...) AS NUMERIC(15,2))` → `near "AS": syntax error`

**Fix:** Reemplazado por algoritmo de balance de paréntesis (`_extract_cast_inner`) que extrae correctamente el contenido de `CAST(...)` con cualquier nivel de anidamiento.

**Impacto:** Todas las queries del DeepAnalysisAgent con `CAST(SUM/AVG/MIN/MAX(col) AS NUMERIC(15,2))` ahora se traducen correctamente a `ROUND(CAST(expr AS REAL), 2)`.

**Tests:** 9 nuevos tests en `TestTranslatorNestedParentheses` (test_db_simulator_core.py).

---

### Reglas de compatibilidad SQLite (aplicar en nuevas queries)

1. **CLIENTE/PROVEED sin columna NOMBRE**: usar siempre `COALESCE(X.NOMBRECOMERCIAL, X.RAZONSOCIAL, 'Sin nombre') AS NOMBRE`
2. **DOCLIN sin IMPORTE**: calcular como `ROUND(CAST(L.CANTIDAD AS REAL)*CAST(L.PRECIO AS REAL),2)`
3. **DOCLIN.CODDOCUMENTO** (no CODIGO) para JOIN con DOCCAB: `ON D.CODIGO = L.CODDOCUMENTO`
4. **DOCLIN.CODARTICULO** (no CODART): `JOIN ARTICULO A ON A.CODIGO = L.CODARTICULO`
5. **CAJA usa IMPORTE** directamente (no CANTIDAD*PRECIO)
6. **RECIBO1**: sin columna COBRADO → usar `ACTIVO` o filtrar por fecha
7. **RECIBO3**: sin FECHAVENC → usar `FECHA`; sin CODPROVEEDOR → usar `CODPAGADOR`
8. **ARTICULO**: sin STOCKMINIMO → usar literal o constante configurable
9. **DOCCAB**: sin CODPROVEEDOR → acceder via DOCLIN→ARTICULO→PROVEED
10. **Alias obligatorio** en todas las expresiones COALESCE y cálculos en SELECT

**Tablas/columnas Firebird-only** (válidas en producción, no disponibles en SQLite del simulador):
- Columnas: `STOCKMINIMO`, `ACTIVO` (en CLIENTE), `COBRADO` (en RECIBO1), `CODPROVEEDOR` (en DOCCAB), `FECHAVENC` (en RECIBO3)
- Las consultas adaptadas usan equivalentes SQLite documentados arriba

---

## ¿Qué hace este módulo?

Permite usar toda la funcionalidad del Chat IA **sin acceso a la BD Firebird real**, usando una BD SQLite local que contiene:

- **Modo `synthetic`** (por defecto): datos generados automáticamente con volumen y distribución realistas del sector de climatización JDDC.
- **Modo `snapshot`**: datos reales del último mes capturados desde Firebird cuando había conexión.

El simulador es **completamente transparente** para el `ChatService`: recibe las mismas queries Firebird SQL, las traduce a SQLite y devuelve resultados en el mismo formato.

---

## Activación del simulador

### Activación servidor (recomendada, permanente)

El simulador se activa mediante el fichero de configuración del servidor:

```json
// backend/modules/db_simulator/config.json
{
  "simulator_enabled": true,
  "show_disclaimer": true
}
```

- `simulator_enabled: true` → todo el tráfico del chat usa `SimulatedFirebirdDriver` en lugar de `FirebirdDriver`.
- `show_disclaimer: true` → el router prepende automáticamente un aviso "⚠️ MODO SIMULACIÓN" a cada respuesta.
- El frontend NO necesita enviar ningún parámetro especial; el switch es completamente servidor.

### Disclaimer automático

Cuando `show_disclaimer: true`, el router (`chat/router.py`) antepone:

```
⚠️ **MODO SIMULACIÓN** — Datos sintéticos. No conectado a Firebird real.
```

El `ChatService` no sabe si está en modo simulación; solo recibe el resultado. La transparencia es total.

### Nota histórica: `sim_mode` en `db_params` (obsoleto)

Versiones anteriores aceptaban `"sim_mode": true` en el campo `db_params` del request. Esta forma de activación ya **no se usa** — el control es exclusivamente servidor vía `config.json`.

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
├── __init__.py            # Exporta SimulatedFirebirdDriver, simulator_manager
├── constants.py           # ← TODA la configuración aquí (rutas, límites, nombres)
├── seed_data.py           # Datos estáticos: productos, clientes, empleados reales
├── schema.py              # CREATE TABLE SQLite (columnas idénticas a Firebird)
├── query_translator.py    # Firebird SQL → SQLite (FIRST→LIMIT, EXTRACT→strftime…)
├── driver.py              # SimulatedFirebirdDriver (implementa DatabaseDriver)
├── synthetic_seeder.py    # Genera datos sintéticos realistas del sector JDDC
├── snapshot_service.py    # Captura datos reales de Firebird → SQLite
├── manager.py             # SimulatorManager — singleton orquestador
├── router.py              # FastAPI endpoints /api/db-simulator/*
└── data/
    ├── simulator.db       # BD SQLite (auto-creada, no subir a git)
    └── status.json        # Estado persistido del simulador
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

## Biblioteca de Consultas SQL (`query_library.py`)

**77 consultas SQL** organizadas en 15 bloques temáticos, cada una con:
- `desc_simple`: explicación en lenguaje llano para cualquier usuario
- `desc_tecnica`: análisis técnico detallado en contexto JDDC
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
    get_all_queries,        # → List[Dict]  (77 consultas)
    get_query_by_id,        # (id) → Dict
    get_catalog_summary,    # () → {total, by_dept, by_tipo, by_urgencia}
    search_queries,         # (dept, rol, tipo, urgencia, text) → List[Dict]
    get_queries_by_dept,    # (dept) → List[Dict]
    get_queries_by_tipo,    # (tipo) → List[Dict]
    get_queries_by_urgencia,# (urgencia) → List[Dict]
)
```

### Constantes de negocio (`query_library_constants.py`)

Centraliza umbrales configurables:
- `UMBRAL_FACTURA_ALTO_IMPORTE = 5000` €
- `UMBRAL_DIAS_CLIENTE_INACTIVO = 90` días
- `UMBRAL_STOCK_CRITICO = 2` unidades
- `UMBRAL_MARGEN_MINIMO = 10` %
- etc. (20+ umbrales)

---

## Cómo extender

**Añadir una nueva tabla al simulador:**
1. Añadir `CREATE TABLE` en `schema.py` → `TABLE_SCHEMAS` y `TABLE_COLUMNS`
2. Añadir nombre en `constants.py` → `JDDCTableNames`
3. Añadir datos en `seed_data.py` y lógica de inserción en `synthetic_seeder.py`
4. Si tiene fecha, añadir en `JDDCDateColumns.MAP` para snapshot automático

**Cambiar volumen de datos sintéticos:**
Editar `constants.py` → `SimulatorConfig` (sin reiniciar el servidor, sí hay que re-ejecutar `build_synthetic`).
