import logging
from typing import List, Dict, Any

from backend.core.factory.db_factory import DBFactory
from backend.core.utils.constants import DBConstants
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)


class ResourcesService:
    def list_resources(self) -> List[Dict[str, Any]]:
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
            query = """
            SELECT CODIGO, DESCRIPCION
            FROM RECURSO
            WHERE DESCRIPCION IS NOT NULL
            ORDER BY DESCRIPCION
            """
            results = driver.execute_query(query)
            return [
                {
                    "id": row.get("CODIGO"),
                    "name": row.get("DESCRIPCION"),
                }
                for row in results
            ]
        finally:
            driver.disconnect()