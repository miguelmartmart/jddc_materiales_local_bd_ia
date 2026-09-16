# DEVIA — Modulo `api_clone`
## API Clone — Replica del API Explorer con SQL Firebird Directo

> **Ruta:** `backend/modules/api_clone/`
> **Version:** 1.0.0
> **Fecha:** 16/09/2026
> **Prefix API:** `/api/api-clone`
> **Frontend:** `frontend/assets/js/modules/api_clone.js`
> **View HTML:** `#view-api-clone` / `#api-clone-root`
> **Estado:** Implementado y funcional

---

## Que es API Clone

Replica **exactamente la semantica del API Explorer** (mismas clases, mismas operaciones:
browse/read/permiso/info/discover-all) pero en lugar de llamar a la API HTTP de mPYME
(Distrito K), ejecuta **SELECT SQL directo en Firebird** usando el mismo `FirebirdDriver`
del proyecto.

**CERO MOCKS.** Todos los valores son datos reales de la BD de produccion.

### Diferencia con API Explorer

| | API Explorer | API Clone |
|-|-------------|----------|
| Datos | API mPYME (mock o real) | SQL Firebird directo |
| Login | Requiere ssid1+ssid2 | No requiere login |
| Mocks | Si (MockApiClient) | No — siempre datos reales |
| Dependencia | API Distrito K activa | Solo Firebird accesible |

### Diferencia con BD Clone

| | BD Clone | API Clone |
|-|---------|---------|
| Interfaz | SQL libre generico | Clases/operaciones del API Explorer |
| Uso | Explorar cualquier tabla | Replicar comportamiento mPYME |

---

## Estructura

```
backend/modules/api_clone/
  __init__.py     vacío
  DEVIA.MD        este fichero
  queries.py      definicion de clases, tablas, columnas, filtros
  service.py      ApiCloneService — browse/read/permiso/info/discover-all
  router.py       11 endpoints FastAPI
  data/
    _history.json historial de operaciones (max 200)
    _matrix.json  matriz de estados por clase/operacion
```

---

## Clases disponibles (17)

| Clase API | Tabla Firebird | Columna PK | Filtro adicional |
|-----------|---------------|-----------|-----------------|
| proyectos | PROYECTOS | CODIGO | — |
| partidas | PRESUPROYE | CODPRESUPUESTO | — |
| proordutil | PREUTILLIN | CODIGO | — |
| proordprev | PREPREVLIN | CODIGO | — |
| reporden | REPARA | CODIGO | — |
| repordutil | RABUTILLIN | CODIGO | — |
| repobjetos | REPOBJETO | CODIGO | — |
| repinst | REPINSTALACION | CODIGO | — |
| tipostrabajo | TIPO | CODIGO | — |
| recursos | RECURSO | CODIGO | — |
| articulos | ARTICULO | CODIGO | — |
| proveedores | PROVEED | CODIGO | — |
| clientes | CLIENTE | CODIGO | — |
| docalbcom | DOCCAB | CODIGO | TIPO = 2 |
| docfaccom | DOCCAB | CODIGO | TIPO = 3 |
| docpedcom | DOCCAB | CODIGO | TIPO = 11 |
| ordenfab | FABCAB | CODIGO | — |

Fuente: `MAPA_FIREBIRD` de api_explorer/router.py + knowledge/tables/*.json

---

## Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/api/api-clone/status` | Estado y config |
| GET | `/api/api-clone/catalogue` | Catalogo de clases/ops |
| POST | `/api/api-clone/permiso` | Simula permiso() — conteo real |
| POST | `/api/api-clone/info` | Simula info() — columnas via RDB$ |
| POST | `/api/api-clone/browse` | Browse real: SELECT FIRST N |
| POST | `/api/api-clone/read` | Read real: SELECT por PK |
| POST | `/api/api-clone/discover-all` | Browse en todas las clases |
| GET | `/api/api-clone/history` | Historial |
| DELETE | `/api/api-clone/history` | Limpiar historial |
| GET | `/api/api-clone/matrix` | Matriz de estados |

---

## Como funciona browse

```sql
-- Ejemplo: browse("clientes", {}, 20)
SELECT FIRST 20 CODIGO, RAZONSOCIAL, NOMBRECOMERCIAL, TEL, CP
FROM CLIENTE
ORDER BY CODIGO

-- browse("docalbcom", {}, 20) — con filtro de TIPO
SELECT FIRST 20 CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL, CODCLIENTE
FROM DOCCAB
WHERE TIPO = 2
ORDER BY CODIGO

-- browse("partidas", {"codProyecto": "45871"}, 20)
SELECT FIRST 20 CODPRESUPUESTO, CODPROYECTO
FROM PRESUPROYE
WHERE CODPROYECTO = '45871'
ORDER BY CODPRESUPUESTO
```

---

## Principios DEVIA

- Sin datos sensibles en logs (historial guarda solo clase/operacion/ms)
- Persistencia atomica en data/ (JSON .tmp + replace)
- Degradacion elegante: errores devuelven {"error": "..."} no HTTP 500
- Patron de conexion identico a database/service.py y api_explorer/router.py
- Las tablas y columnas son las REALES verificadas en BD JDDC
