import logging
from typing import List, Dict, Any

from backend.core.factory.db_factory import DBFactory
from backend.core.utils.constants import DBConstants
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

# SQL query para obtener empleados/recursos de la tabla RECURSO
_QUERY_LIST_EMPLOYEES = """
SELECT
    CODIGO,
    DESCRIPCION,
    NIF,
    NSS,
    EMAIL,
    TEL,
    PUESTOTRABAJO,
    CODPADRE,
    ORDEN
FROM RECURSO
WHERE DESCRIPCION IS NOT NULL
ORDER BY DESCRIPCION
"""


def _map_row_to_employee(row: Dict[str, Any]) -> Dict[str, Any]:
    """Mapea una fila de la tabla RECURSO al modelo de empleado.

    Args:
        row: Diccionario con los campos de la fila de Firebird.

    Returns:
        Diccionario con el modelo de empleado normalizado.
    """
    return {
        "code": row.get("CODIGO"),
        "fullName": row.get("DESCRIPCION"),
        "nif": row.get("NIF"),
        "nss": row.get("NSS"),
        "email": row.get("EMAIL"),
        "phone": row.get("TEL"),
        "position": row.get("PUESTOTRABAJO"),
        "parentCode": row.get("CODPADRE"),        # Código del departamento padre
        "departmentOrder": row.get("ORDEN"),       # Orden de visualización
    }


class EmployeesService:
    """Servicio para gestionar empleados/recursos desde la BD Firebird."""

    def list_employees(self) -> List[Dict[str, Any]]:
        """Obtiene la lista completa de empleados desde la tabla RECURSO.

        Incluye los campos parentCode (CODPADRE) y departmentOrder (ORDEN)
        para permitir la identificación correcta del departamento de cada empleado.

        Returns:
            Lista de diccionarios con los datos de cada empleado/recurso.

        Raises:
            ValueError: Si DB_NAME no está configurado en .env.
        """
        if not settings.DB_NAME:
            raise ValueError("DB_NAME no está configurado en .env")

        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
        config = DBConfig(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )

        try:
            driver.connect(config)
            results = driver.execute_query(_QUERY_LIST_EMPLOYEES)
            return [_map_row_to_employee(row) for row in results]
        finally:
            driver.disconnect()
