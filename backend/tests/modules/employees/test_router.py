"""
Tests para el router del módulo de empleados: endpoint GET /api/employees-real.

Cubre:
- Respuesta 200 con lista de empleados (incluyendo parentCode y departmentOrder).
- Respuesta 200 con lista vacía.
- Respuesta 500 cuando el servicio lanza una excepción.
- Estructura correcta del JSON de respuesta.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.modules.employees.router import router


# ---------------------------------------------------------------------------
# Setup: aplicación FastAPI mínima para pruebas
# ---------------------------------------------------------------------------

def _create_test_app() -> FastAPI:
    """Crea una aplicación FastAPI mínima con el router de empleados montado."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def client():
    """Cliente de prueba HTTP para el router de empleados."""
    app = _create_test_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

EMPLOYEE_GARCIA = {
    "code": 14,
    "fullName": "GARCIA GIL, ADRIAN",
    "nif": "48510320P",
    "nss": "301056457317",
    "email": None,
    "phone": "601107251",
    "position": None,
    "parentCode": 2,
    "departmentOrder": 14,
}

EMPLOYEE_MARTINEZ = {
    "code": 153,
    "fullName": " MARTINEZ ORTEGA, RAFAEL",
    "nif": "34804971Z",
    "nss": None,
    "email": None,
    "phone": None,
    "position": None,
    "parentCode": 151,
    "departmentOrder": 999,
}


# ---------------------------------------------------------------------------
# Tests: GET /api/employees-real
# ---------------------------------------------------------------------------

class TestEmployeesRouter:
    """Tests del endpoint GET /api/employees-real."""

    @patch("backend.modules.employees.router.service")
    def test_retorna_200_con_lista_de_empleados(self, mock_service, client):
        """Verifica que el endpoint devuelve 200 con la lista de empleados."""
        mock_service.list_employees.return_value = [EMPLOYEE_GARCIA, EMPLOYEE_MARTINEZ]

        response = client.get("/api/employees-real")

        assert response.status_code == 200

    @patch("backend.modules.employees.router.service")
    def test_respuesta_contiene_clave_employees(self, mock_service, client):
        """Verifica que la respuesta JSON tiene la clave 'employees'."""
        mock_service.list_employees.return_value = [EMPLOYEE_GARCIA]

        response = client.get("/api/employees-real")
        data = response.json()

        assert "employees" in data

    @patch("backend.modules.employees.router.service")
    def test_respuesta_contiene_parentCode(self, mock_service, client):
        """Verifica que cada empleado en la respuesta incluye el campo parentCode."""
        mock_service.list_employees.return_value = [EMPLOYEE_GARCIA]

        response = client.get("/api/employees-real")
        employees = response.json()["employees"]

        assert "parentCode" in employees[0]
        assert employees[0]["parentCode"] == 2

    @patch("backend.modules.employees.router.service")
    def test_respuesta_contiene_departmentOrder(self, mock_service, client):
        """Verifica que cada empleado en la respuesta incluye el campo departmentOrder."""
        mock_service.list_employees.return_value = [EMPLOYEE_GARCIA]

        response = client.get("/api/employees-real")
        employees = response.json()["employees"]

        assert "departmentOrder" in employees[0]
        assert employees[0]["departmentOrder"] == 14

    @patch("backend.modules.employees.router.service")
    def test_respuesta_contiene_todos_los_campos_del_empleado(self, mock_service, client):
        """Verifica que la respuesta incluye todos los campos del modelo de empleado."""
        mock_service.list_employees.return_value = [EMPLOYEE_GARCIA]

        response = client.get("/api/employees-real")
        employee = response.json()["employees"][0]

        expected_keys = {
            "code", "fullName", "nif", "nss", "email",
            "phone", "position", "parentCode", "departmentOrder",
        }
        assert set(employee.keys()) == expected_keys

    @patch("backend.modules.employees.router.service")
    def test_retorna_lista_vacia_cuando_no_hay_empleados(self, mock_service, client):
        """Verifica que el endpoint devuelve 200 con lista vacía si no hay empleados."""
        mock_service.list_employees.return_value = []

        response = client.get("/api/employees-real")

        assert response.status_code == 200
        assert response.json() == {"employees": []}

    @patch("backend.modules.employees.router.service")
    def test_retorna_multiples_empleados(self, mock_service, client):
        """Verifica que el endpoint devuelve correctamente múltiples empleados."""
        mock_service.list_employees.return_value = [EMPLOYEE_GARCIA, EMPLOYEE_MARTINEZ]

        response = client.get("/api/employees-real")
        employees = response.json()["employees"]

        assert len(employees) == 2
        assert employees[0]["code"] == 14
        assert employees[0]["parentCode"] == 2
        assert employees[1]["code"] == 153
        assert employees[1]["parentCode"] == 151

    @patch("backend.modules.employees.router.service")
    def test_retorna_500_cuando_el_servicio_falla(self, mock_service, client):
        """Verifica que el endpoint devuelve 500 cuando el servicio lanza una excepción."""
        mock_service.list_employees.side_effect = RuntimeError("Error interno de BD")

        response = client.get("/api/employees-real")

        assert response.status_code == 500

    @patch("backend.modules.employees.router.service")
    def test_error_500_contiene_detalle(self, mock_service, client):
        """Verifica que la respuesta 500 incluye el detalle del error."""
        mock_service.list_employees.side_effect = Exception("Fallo de conexión Firebird")

        response = client.get("/api/employees-real")
        data = response.json()

        assert "detail" in data
        assert "Fallo de conexión Firebird" in data["detail"]

    @patch("backend.modules.employees.router.service")
    def test_parentCode_none_para_departamento_raiz(self, mock_service, client):
        """Verifica que parentCode es null en JSON para departamentos raíz."""
        root_dept = {
            "code": 1,
            "fullName": "MANO DE OBRA",
            "nif": None,
            "nss": None,
            "email": None,
            "phone": None,
            "position": None,
            "parentCode": None,
            "departmentOrder": 1,
        }
        mock_service.list_employees.return_value = [root_dept]

        response = client.get("/api/employees-real")
        employee = response.json()["employees"][0]

        assert employee["parentCode"] is None

    @patch("backend.modules.employees.router.service")
    def test_valores_numericos_correctos_en_json(self, mock_service, client):
        """Verifica que los valores numéricos se serializan correctamente en JSON."""
        mock_service.list_employees.return_value = [EMPLOYEE_MARTINEZ]

        response = client.get("/api/employees-real")
        employee = response.json()["employees"][0]

        assert employee["code"] == 153
        assert employee["parentCode"] == 151
        assert employee["departmentOrder"] == 999

    @patch("backend.modules.employees.router.service")
    def test_llama_al_servicio_exactamente_una_vez(self, mock_service, client):
        """Verifica que el endpoint llama a list_employees exactamente una vez."""
        mock_service.list_employees.return_value = []

        client.get("/api/employees-real")

        mock_service.list_employees.assert_called_once()

    @patch("backend.modules.employees.router.service")
    def test_retorna_500_cuando_db_name_no_configurado(self, mock_service, client):
        """Verifica que el endpoint devuelve 500 si DB_NAME no está configurado."""
        mock_service.list_employees.side_effect = ValueError(
            "DB_NAME no está configurado en .env"
        )

        response = client.get("/api/employees-real")

        assert response.status_code == 500
        assert "DB_NAME" in response.json()["detail"]
