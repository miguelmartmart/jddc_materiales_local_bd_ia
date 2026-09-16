# DEVIA — Módulo `bd_clone`
## BD Clone — Explorador SQL Directo sobre Firebird Real

> **Ruta:** `backend/modules/bd_clone/`
> **Versión:** 1.0.0
> **Fecha:** 16/09/2026
> **Prefix API:** `/api/bd-clone`
> **Frontend:** `frontend/assets/js/modules/bd_clone.js`
> **View HTML:** `#view-bd-clone` / `#bd-clone-root`
> **Estado:** ✅ Implementado y funcional

---

## ¿Qué es BD Clone?

BD Clone es una nueva sección del panel DEVIA que permite explorar y consultar
la base de datos Firebird **directamente mediante SQL**, sin necesidad de la
API mPYME (Distrito K) ni de la máquina virtual / VPN.

Mientras `API Explorer` usa la API REST de Distrito K (mPYME),
`BD Clone` usa el `FirebirdDriver` del proyecto para conectarse directamente al
fichero `.fdb` via TCP — igual que hace el Chat IA, el módulo Database Config
y el api_explorer interno.

---

## Arquitectura

```
backend/modules/bd_clone/
  __init__.py          ← vacío
  DEVIA.MD             ← este fichero
  router.py            ← FastAPI endpoints (/api/bd-clone/*)
  service.py           ← BDCloneService (lógica SQL + persistencia)
  data/
    _history.json      ← historial de consultas (max 200, atómico)
    _catalog_cache.json← caché del catálogo de tablas (TTL 1h)

frontend/assets/js/modules/
  bd_clone.js          ← módulo ES6 (window.BDCloneModule)
```

---

## Principios DEVIA aplicados

| Principio | Implementación |
|-----------|---------------|
| **Sin inventar nada** | Usa `DBFactory.get_driver("firebird")` + `DBConfig` idéntico a `database/service.py` |
| **Solo lectura por defecto** | `ejecutar_sql()` bloquea INSERT/UPDATE/DELETE salvo `modo_escritura=True` |
| **Escritura con doble confirmación** | Requiere string exacto `"ACTIVAR ESCRITURA BD"` |
| **Persistencia atómica** | `_guardar_json()` con fichero `.tmp` + `replace()` |
| **Degradación elegante** | Todos los errores se capturan y devuelven `{"ok": False, "error": ...}` |
| **Sin datos sensibles en logs** | El historial guarda solo `sql_preview[:120]` |
| **Cache inteligente** | Catálogo de tablas: TTL 1h + `force_refresh` disponible |
| **Límites** | MAX_ROWS_SELECT=500, MAX_HISTORY=200 |

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET`  | `/api/bd-clone/status` | Estado de la conexión y configuración |
| `GET`  | `/api/bd-clone/probar-conexion` | Prueba real (COUNT tablas de usuario) |
| `POST` | `/api/bd-clone/catalogo` | Lista tablas de usuario con n_columnas (caché 1h) |
| `POST` | `/api/bd-clone/tabla-detalle` | Columnas + conteo + muestra de 5 filas |
| `POST` | `/api/bd-clone/ejecutar-sql` | Ejecuta SELECT libre (máx 500 filas) |
| `GET`  | `/api/bd-clone/consultas-predefinidas` | Consultas de query_library compatibles con Firebird |
| `POST` | `/api/bd-clone/ejecutar-predefinida` | Ejecuta consulta predefinida con parámetros |
| `GET`  | `/api/bd-clone/diagnostico` | Conexión + conteo de 12 tablas clave |
| `GET`  | `/api/bd-clone/historial` | Últimas N consultas (max 200) |
| `DELETE`| `/api/bd-clone/historial` | Limpiar historial |
| `POST` | `/api/bd-clone/escritura` | Activar/desactivar modo escritura |

---

## Frontend — Pestañas

| Pestaña | Descripción |
|---------|-------------|
| **🔌 Conexion** | Estado BD, probar conexión, diagnóstico, modo escritura |
| **📋 Catalogo** | Lista de todas las tablas con búsqueda + detalle (columnas/muestra) al clic |
| **⚡ SQL Libre** | Editor SQL con autoejecutar, Ctrl+Enter, ejemplos rápidos |
| **📚 Consultas** | Consultas de la query_library compatibles con Firebird real |
| **🕐 Historial** | Últimas consultas ejecutadas con estado y ms |

---

## Relación con otros módulos

| Módulo | Diferencia |
|--------|-----------|
| `api_explorer` | Usa API REST mPYME (Distrito K) — requiere login + ssid |
| `bd_clone` | Usa SQL directo en Firebird — sin login, sin API, sin VPN |
| `db_simulator` | Usa SQLite con datos sintéticos — sin BD real |
| `database` (config) | Analiza tablas con IA para generar metadatos — no para explorar datos |
| `chat` | Genera SQL con IA y lo ejecuta vía `FirebirdDriver` — bd_clone hace lo mismo pero manualmente |

---

## Uso del FirebirdDriver

Usa exactamente el mismo patrón que el resto del proyecto:

```python
from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings

cfg = DBConfig(
    host=settings.DB_HOST, port=settings.DB_PORT,
    database=settings.DB_NAME, user=settings.DB_USER,
    password=settings.DB_PASSWORD, charset="latin1",
)
drv = DBFactory.get_driver("firebird")
drv.connect(cfg)
rows = drv.execute_query("SELECT FIRST 10 * FROM PROYECTOS")
drv.disconnect()
```

---

## Seguridad SQL

- **SELECT** → siempre permitido
- **INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/EXECUTE** → bloqueados salvo `modo_escritura=True`
- **Inyección FIRST N** automática: `SELECT * FROM TABLA` → `SELECT FIRST 500 * FROM TABLA`
- **Historial**: solo guarda `sql[:120]` — no se registran resultados ni datos de negocio

---

## Configuración requerida (`.env`)

```
DB_HOST=192.168.0.254
DB_PORT=3050
DB_NAME=C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb
DB_USER=SYSDBA
DB_PASSWORD=masterkey
```

Si `DB_NAME` está vacío, todos los endpoints devuelven `{"ok": false, "error": "DB_NAME no configurado"}`.
