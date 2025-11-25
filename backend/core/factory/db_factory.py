from typing import Optional
from backend.core.abstract.database import DatabaseDriver
from backend.core.utils.constants import DBConstants
from backend.drivers.db.firebird_driver import FirebirdDriver

class DBFactory:
    """Factory for creating database drivers."""
    
    @staticmethod
    def get_driver(db_type: str) -> DatabaseDriver:
        if db_type == DBConstants.TYPE_FIREBIRD.value:
            return FirebirdDriver()
        # Add other drivers here
        raise ValueError(f"Unsupported database type: {db_type}")
