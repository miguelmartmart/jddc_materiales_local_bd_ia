# 📋 DEVIA — Módulo Employees

**Módulo:** `backend/modules/employees`  
**Endpoint:** `GET /api/employees-real`  
**Puerto:** 8001  
**Última modificación:** 20/02/2026

---

## 🎯 Propósito

Expone los registros de la tabla `RECURSO` de Firebird como una API REST JSON.
Actúa como puente entre el **Portal de Empleados JDDC** (NestJS) y la base de datos legacy Firebird.

---

## 📁 Estructura del Módulo

```
modules/employees/
├── router.py       # Endpoint FastAPI: GET /api/employees-real
├── service.py      # Lógica de negocio + query SQL + mapeo de datos
└── DEVIA.MD        # Este archivo
```

---

## 🗄️ Tabla Firebird: RECURSO

```
CODIGO | CODPADRE | ORDEN | DESCRIPCION
-------|----------|-------|---------------------------
     1 |     NULL |     1 | MANO DE OBRA              ← Departamento raíz
     2 |        1 |     2 | DPTO INGENIERIA            ← Departamento
    14 |        2 |    14 | GARCIA GIL, ADRIAN         ← Empleado
   151 |     NULL |   901 | ANTIGUO PERSONAL           ← Departamento raíz
   153 |      151 |   999 |  MARTINEZ ORTEGA, RAFAEL   ← Empleado
```

**Lógica de jerarquía:**
- `CODPADRE = NULL` → Departamento raíz
- `CODPADRE = 1` → Departamento de primer nivel
- `CODPADRE > 1` → Empleado o subdepartamento

---

## 🔌 Endpoint

### `GET /api/employees-real`

**Respuesta exitosa (200):**
```json
{
  "employees": [
    {
      "code": 14,
      "fullName": "GARCIA GIL, ADRIAN",
      "nif": "48510320P",
      "nss": "301056457317",
      "email": null,
      "phone": "601107251",
      "position": null,
      "parentCode": 2,
      "departmentOrder": 14
    }
  ]
}
```

**Campos del modelo:**

| Campo JSON       | Columna Firebird | Tipo     | Descripción                          |
|------------------|------------------|----------|--------------------------------------|
| `code`           | `CODIGO`         | int      | Identificador único del registro     |
| `fullName`       | `DESCRIPCION`    | str      | Nombre del empleado o departamento   |
| `nif`            | `NIF`            | str/null | NIF del empleado                     |
| `nss`            | `NSS`            | str/null | Número de Seguridad Social           |
| `email`          | `EMAIL`          | str/null | Correo electrónico                   |
| `phone`          | `TEL`            | str/null | Teléfono                             |
| `position`       | `PUESTOTRABAJO`  | str/null | Puesto de trabajo                    |
| `parentCode`     | `CODPADRE`       | int/null | Código del departamento padre ⭐     |
| `departmentOrder`| `ORDEN`          | int/null | Orden de visualización ⭐            |

> ⭐ Campos añadidos el 20/02/2026 para soporte de jerarquía departamental.

---

## 🏗️ Arquitectura Interna

```
router.py
  └── GET /employees-real
        └── EmployeesService.list_employees()
              ├── DBFactory.get_driver(FIREBIRD)
              ├── driver.connect(DBConfig)
              ├── driver.execute_query(_QUERY_LIST_EMPLOYEES)
              ├── [_map_row_to_employee(row) for row in results]
              └── driver.disconnect()  ← siempre en finally
```

**Patrones aplicados:**
- **Factory Method**: `DBFactory.get_driver()` para obtener el driver Firebird
- **Strategy**: El driver es intercambiable sin cambiar el servicio
- **Fail-safe**: `disconnect()` siempre en bloque `finally`

---

## 🧪 Tests

**Ubicación:** `backend/tests/modules/employees/`

```
tests/modules/employees/
├── __init__.py
├── test_service.py   # 25 tests: mapeo + servicio
└── test_router.py    # 13 tests: endpoint HTTP
```

**Ejecutar tests:**
```bash
# Desde la raíz del proyecto interjddcia
pushd "C:\...\interjddcia"
.venv\Scripts\python.exe -m pytest backend/tests/modules/employees --rootdir=. -v
```

**Cobertura:**

| Clase/Función          | Tests | Qué verifica                                      |
|------------------------|-------|---------------------------------------------------|
| `_map_row_to_employee` | 12    | Mapeo de campos, None, tipos, casos reales        |
| `EmployeesService`     | 13    | Query SQL, connect/disconnect, errores, DB_NAME   |
| `TestEmployeesRouter`  | 13    | HTTP 200/500, JSON, parentCode, departmentOrder   |

---

## 🔗 Integración con Portal de Empleados

El Portal de Empleados (NestJS) consume este endpoint:

```typescript
// portal_empleados_jddc/backend/src/modules/employees/employees.service.ts
const baseUrl = process.env.RESOURCES_SERVICE_URL || 'http://localhost:8001/api';
const response = await fetch(`${baseUrl}/employees-real`);
```

**Variable de entorno requerida en el portal:**
```bash
RESOURCES_SERVICE_URL=http://localhost:8001/api
```

**Uso de parentCode en el portal:**
```typescript
// Identificar departamento de un empleado
const departmentCode = employee.parentCode;

// Filtrar empleados por departamentos permitidos
const ALLOWED = [2, 10, 11, 12, 13, 37, 71, 135];
const validEmployees = employees.filter(e => ALLOWED.includes(e.parentCode));
```

---

## 📝 Historial de Cambios

| Fecha      | Cambio                                                        | Autor  |
|------------|---------------------------------------------------------------|--------|
| 20/02/2026 | Añadidos campos `parentCode` (CODPADRE) y `departmentOrder` (ORDEN) | Dev |
| 20/02/2026 | Creados 38 tests unitarios e integración                      | Dev    |
| 20/02/2026 | Refactorización: query extraída a constante, mapeo a función  | Dev    |
