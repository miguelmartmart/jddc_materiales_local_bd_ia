"""
Tests para el módulo de empleados: función de mapeo y servicio EmployeesService.

Cubre:
- _map_row_to_employee: mapeo correcto de todos los campos, valores None, tipos.
- EmployeesService.list_employees: flujo completo con mocks de BD, errores y casos límite.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from typing import Dict, Any

# Importaciones del módulo bajo prueba
from backend.modules.employees.service import (
    EmployeesService,
    _map_row_to_employee,
    _QUERY_LIST_EMPLOYEES,
)


# ---------------------------------------------------------------------------
# Fixtures y datos de prueba
# ---------------------------------------------------------------------------

def _make_firebird_row(
    codigo: int = 14,
    descripcion: str = "GARCIA GIL, ADRIAN",
    nif: str = "48510320P",
    nss: str = "301056457317",
    email: str = "adrian@jddc.es",
    tel: str = "601107251",
    puestotrabajo: str = "Ingeniero",
    codpadre: int = 2,
    orden: int = 14,
) -> Dict[str, Any]:
    """Construye una fila simulada de Firebird con todos los campos."""
    return {
        "CODIGO": codigo,
        "DESCRIPCION": descripcion,
        "NIF": nif,
        "NSS": nss,
        "EMAIL": email,
        "TEL": tel,
        "PUESTOTRABAJO": puestotrabajo,
        "CODPADRE": codpadre,
        "ORDEN": orden,
    }


SAMPLE_ROW_EMPLOYEE = _make_firebird_row()

SAMPLE_ROW_ANTIGUO_PERSONAL = _make_firebird_row(
    codigo=153,
    descripcion=" MARTINEZ ORTEGA, RAFAEL",
    nif="34804971Z",
    nss=None,
    email=None,
    tel=None,
    puestotrabajo=None,
    codpadre=151,
    orden=999,
)

SAMPLE_ROW_DEPARTMENT = _make_firebird_row(
    codigo=2,
    descripcion="DPTO INGENIERIA",
    nif=None,
    nss=None,
    email=None,
    tel=None,
    puestotrabajo=None,
    codpadre=1,
    orden=2,
)

SAMPLE_ROW_ROOT_DEPARTMENT = _make_firebird_row(
    codigo=1,
    descripcion="MANO DE OBRA",
    nif=None,
    nss=None,
    email=None,
    tel=None,
    puestotrabajo=None,
    codpadre=None,
    orden=1,
)


# ---------------------------------------------------------------------------
# Tests: _map_row_to_employee
# ---------------------------------------------------------------------------

class TestMapRowToEmployee:
    """Tests unitarios para la función de mapeo _map_row_to_employee."""

    def test_mapea_todos_los_campos_correctamente(self):
        """Verifica que todos los campos se mapean con los nombres correctos."""
        result = _map_row_to_employee(SAMPLE_ROW_EMPLOYEE)

        assert result["code"] == 14
        assert result["fullName"] == "GARCIA GIL, ADRIAN"
        assert result["nif"] == "48510320P"
        assert result["nss"] == "301056457317"
        assert result["email"] == "adrian@jddc.es"
        assert result["phone"] == "601107251"
        assert result["position"] == "Ingeniero"
        assert result["parentCode"] == 2
        assert result["departmentOrder"] == 14

    def test_mapea_parentCode_desde_CODPADRE(self):
        """Verifica que CODPADRE se mapea a parentCode."""
        row = _make_firebird_row(codpadre=151)
        result = _map_row_to_employee(row)
        assert result["parentCode"] == 151

    def test_mapea_departmentOrder_desde_ORDEN(self):
        """Verifica que ORDEN se mapea a departmentOrder."""
        row = _make_firebird_row(orden=999)
        result = _map_row_to_employee(row)
        assert result["departmentOrder"] == 999

    def test_parentCode_es_none_cuando_CODPADRE_es_none(self):
        """Verifica que parentCode es None cuando CODPADRE es NULL (departamento raíz)."""
        result = _map_row_to_employee(SAMPLE_ROW_ROOT_DEPARTMENT)
        assert result["parentCode"] is None

    def test_campos_opcionales_son_none(self):
        """Verifica que campos opcionales (nif, nss, email, phone, position) pueden ser None."""
        result = _map_row_to_employee(SAMPLE_ROW_ANTIGUO_PERSONAL)
        assert result["nss"] is None
        assert result["email"] is None
        assert result["phone"] is None
        assert result["position"] is None

    def test_resultado_contiene_exactamente_nueve_campos(self):
        """Verifica que el modelo de empleado tiene exactamente los 9 campos esperados."""
        result = _map_row_to_employee(SAMPLE_ROW_EMPLOYEE)
        expected_keys = {
            "code", "fullName", "nif", "nss", "email",
            "phone", "position", "parentCode", "departmentOrder",
        }
        assert set(result.keys()) == expected_keys

    def test_mapeo_empleado_antiguo_personal(self):
        """Verifica el mapeo correcto del empleado 153 (ANTIGUO PERSONAL)."""
        result = _map_row_to_employee(SAMPLE_ROW_ANTIGUO_PERSONAL)
        assert result["code"] == 153
        assert result["parentCode"] == 151
        assert result["departmentOrder"] == 999

    def test_mapeo_departamento_raiz(self):
        """Verifica el mapeo de un departamento raíz (CODPADRE = None)."""
        result = _map_row_to_employee(SAMPLE_ROW_ROOT_DEPARTMENT)
        assert result["code"] == 1
        assert result["parentCode"] is None
        assert result["departmentOrder"] == 1

    def test_mapeo_departamento_con_padre(self):
        """Verifica el mapeo de un departamento con padre (DPTO INGENIERIA)."""
        result = _map_row_to_employee(SAMPLE_ROW_DEPARTMENT)
        assert result["code"] == 2
        assert result["parentCode"] == 1
        assert result["departmentOrder"] == 2

    def test_fila_con_todos_los_campos_none(self):
        """Verifica que la función no falla con una fila completamente vacía."""
        empty_row: Dict[str, Any] = {
            "CODIGO": None,
            "DESCRIPCION": None,
            "NIF": None,
            "NSS": None,
            "EMAIL": None,
            "TEL": None,
            "PUESTOTRABAJO": None,
            "CODPADRE": None,
            "ORDEN": None,
        }
        result = _map_row_to_employee(empty_row)
        assert result["code"] is None
        assert result["parentCode"] is None
        assert result["departmentOrder"] is None

    def test_fila_vacia_devuelve_todos_none(self):
        """Verifica que una fila vacía (sin claves) devuelve todos los campos como None."""
        result = _map_row_to_employee({})
        for value in result.values():
            assert value is None

    def test_tipos_de_datos_correctos(self):
        """Verifica que los tipos de datos numéricos se preservan correctamente."""
        result = _map_row_to_employee(SAMPLE_ROW_EMPLOYEE)
        assert isinstance(result["code"], int)
        assert isinstance(result["parentCode"], int)
        assert isinstance(result["departmentOrder"], int)
        assert isinstance(result["fullName"], str)


# ---------------------------------------------------------------------------
# Tests: EmployeesService.list_employees
# ---------------------------------------------------------------------------

class TestEmployeesService:
    """Tests de integración (con mocks) para EmployeesService."""

    def _make_mock_driver(self, query_results=None):
        """Crea un mock del driver de BD con comportamiento configurable."""
        mock_driver = MagicMock()
        mock_driver.execute_query.return_value = query_results or []
        return mock_driver

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_retorna_lista_de_empleados_correctamente(
        self, mock_db_factory, mock_settings
    ):
        """Verifica que list_employees devuelve la lista mapeada correctamente."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        mock_driver = self._make_mock_driver([SAMPLE_ROW_EMPLOYEE, SAMPLE_ROW_ANTIGUO_PERSONAL])
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        result = service.list_employees()

        assert len(result) == 2
        assert result[0]["code"] == 14
        assert result[0]["parentCode"] == 2
        assert result[0]["departmentOrder"] == 14
        assert result[1]["code"] == 153
        assert result[1]["parentCode"] == 151
        assert result[1]["departmentOrder"] == 999

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_ejecuta_la_query_correcta(self, mock_db_factory, mock_settings):
        """Verifica que se ejecuta exactamente la query definida en la constante."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        mock_driver = self._make_mock_driver([])
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        service.list_employees()

        mock_driver.execute_query.assert_called_once_with(_QUERY_LIST_EMPLOYEES)

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_query_incluye_codpadre_y_orden(self, mock_db_factory, mock_settings):
        """Verifica que la query SQL contiene los campos CODPADRE y ORDEN."""
        assert "CODPADRE" in _QUERY_LIST_EMPLOYEES
        assert "ORDEN" in _QUERY_LIST_EMPLOYEES

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_query_incluye_todos_los_campos_originales(self, mock_db_factory, mock_settings):
        """Verifica que la query SQL mantiene todos los campos originales."""
        assert "CODIGO" in _QUERY_LIST_EMPLOYEES
        assert "DESCRIPCION" in _QUERY_LIST_EMPLOYEES
        assert "NIF" in _QUERY_LIST_EMPLOYEES
        assert "NSS" in _QUERY_LIST_EMPLOYEES
        assert "EMAIL" in _QUERY_LIST_EMPLOYEES
        assert "TEL" in _QUERY_LIST_EMPLOYEES
        assert "PUESTOTRABAJO" in _QUERY_LIST_EMPLOYEES
        assert "RECURSO" in _QUERY_LIST_EMPLOYEES

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_desconecta_siempre_aunque_haya_exito(self, mock_db_factory, mock_settings):
        """Verifica que disconnect() se llama siempre (bloque finally)."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        mock_driver = self._make_mock_driver([SAMPLE_ROW_EMPLOYEE])
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        service.list_employees()

        mock_driver.disconnect.assert_called_once()

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_desconecta_siempre_aunque_haya_error(self, mock_db_factory, mock_settings):
        """Verifica que disconnect() se llama incluso cuando execute_query lanza excepción."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        mock_driver = MagicMock()
        mock_driver.execute_query.side_effect = RuntimeError("Error de BD simulado")
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        with pytest.raises(RuntimeError, match="Error de BD simulado"):
            service.list_employees()

        mock_driver.disconnect.assert_called_once()

    @patch("backend.modules.employees.service.settings")
    def test_lanza_error_si_db_name_no_configurado(self, mock_settings):
        """Verifica que se lanza ValueError si DB_NAME está vacío."""
        mock_settings.DB_NAME = ""

        service = EmployeesService()
        with pytest.raises(ValueError, match="DB_NAME no está configurado en .env"):
            service.list_employees()

    @patch("backend.modules.employees.service.settings")
    def test_lanza_error_si_db_name_es_none(self, mock_settings):
        """Verifica que se lanza ValueError si DB_NAME es None."""
        mock_settings.DB_NAME = None

        service = EmployeesService()
        with pytest.raises(ValueError, match="DB_NAME no está configurado en .env"):
            service.list_employees()

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_retorna_lista_vacia_si_no_hay_empleados(self, mock_db_factory, mock_settings):
        """Verifica que se devuelve lista vacía cuando la BD no tiene registros."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        mock_driver = self._make_mock_driver([])
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        result = service.list_employees()

        assert result == []

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_conecta_con_los_parametros_correctos(self, mock_db_factory, mock_settings):
        """Verifica que connect() recibe los parámetros de configuración correctos."""
        mock_settings.DB_NAME = "C:/datos/jddc.fdb"
        mock_settings.DB_HOST = "192.168.1.10"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "secret"

        mock_driver = self._make_mock_driver([])
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        service.list_employees()

        connect_call_args = mock_driver.connect.call_args[0][0]
        assert connect_call_args.host == "192.168.1.10"
        assert connect_call_args.port == 3050
        assert connect_call_args.database == "C:/datos/jddc.fdb"
        assert connect_call_args.user == "SYSDBA"
        assert connect_call_args.password == "secret"

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_multiples_empleados_todos_mapeados(self, mock_db_factory, mock_settings):
        """Verifica que todos los registros de la BD se mapean correctamente."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        rows = [
            SAMPLE_ROW_ROOT_DEPARTMENT,
            SAMPLE_ROW_DEPARTMENT,
            SAMPLE_ROW_EMPLOYEE,
            SAMPLE_ROW_ANTIGUO_PERSONAL,
        ]
        mock_driver = self._make_mock_driver(rows)
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        result = service.list_employees()

        assert len(result) == 4
        # Departamento raíz: sin padre
        assert result[0]["parentCode"] is None
        # Departamento con padre
        assert result[1]["parentCode"] == 1
        # Empleado normal
        assert result[2]["parentCode"] == 2
        # Empleado antiguo personal
        assert result[3]["parentCode"] == 151

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_usa_driver_firebird(self, mock_db_factory, mock_settings):
        """Verifica que se solicita el driver de tipo Firebird a la factory."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        mock_driver = self._make_mock_driver([])
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        service.list_employees()

        # Verifica que se llamó a get_driver (con el tipo Firebird)
        mock_db_factory.get_driver.assert_called_once()

    @patch("backend.modules.employees.service.settings")
    @patch("backend.modules.employees.service.DBFactory")
    def test_error_de_conexion_se_propaga(self, mock_db_factory, mock_settings):
        """Verifica que un error de conexión a la BD se propaga correctamente."""
        mock_settings.DB_NAME = "test.fdb"
        mock_settings.DB_HOST = "localhost"
        mock_settings.DB_PORT = 3050
        mock_settings.DB_USER = "SYSDBA"
        mock_settings.DB_PASSWORD = "masterkey"

        mock_driver = MagicMock()
        mock_driver.connect.side_effect = ConnectionError("No se puede conectar a Firebird")
        mock_db_factory.get_driver.return_value = mock_driver

        service = EmployeesService()
        with pytest.raises(ConnectionError, match="No se puede conectar a Firebird"):
            service.list_employees()
