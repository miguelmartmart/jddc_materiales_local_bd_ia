# DEVIA — Módulo `db_simulator`
## Simulador de BD Firebird para trabajo offline

> **Ruta:** `backend/modules/db_simulator/`  
> **Versión:** 1.3.0  
> **Fecha:** 2026-05-22  
> **Estado:** ✅ Implementado y funcional

## 📚 Documentación de sesiones

| Sesión | Archivo | Contenido |
|--------|---------|-----------|
| 20/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Fix HTTP 500 query_library truncado, filtros UI vacíos |
| 21/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Context Manager v3.0, fix _execute_sql bloqueante |
| 21/05/2026 | `SESION_RESUMEN_2026_05_20.md` | Tests 40/40 ✅: get_queries_by_rol, catalog_summary aliases, Firebird-only handling |

**Tablas/columnas Firebird-only** (válidas en producción, no disponibles en SQLite del simulador):
- Tablas: `EFECTOSCOBRO`, `EFECTOSPAGO`, `PROVEEDOR`
- Columnas: `STOCKACTUAL`, `STOCKMINIMO`, `PRECIOCOSTE`, `ACTIVO`, `CODDOCREL`
- Las consultas que las usan están marcadas en `test_query_library.py::_FIREBIRD_ONLY_*`

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
