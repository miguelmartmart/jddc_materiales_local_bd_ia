from typing import Optional
from backend.core.abstract.database import DatabaseDriver
from backend.core.utils.constants import DBConstants
from backend.drivers.db.firebird_driver import FirebirdDriver

class DBFactory:
    """Factory for creating database drivers."""
    
    @staticmethod
    def get_driver(db_type: any) -> DatabaseDriver:
        # Normalize input to string
        type_str = str(db_type)
        
        # Handle Enum member
        if hasattr(db_type, 'value'):
            type_str = str(db_type.value)
            
        # Check for Firebird (handle both value and Enum string representation)
        if type_str == "firebird" or "TYPE_FIREBIRD" in str(db_type):
            return FirebirdDriver()
            
        # Add other drivers here
        raise ValueError(f"Unsupported database type: {db_type} (type: {type(db_type)}, str: {type_str})")
