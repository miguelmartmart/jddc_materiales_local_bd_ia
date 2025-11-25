from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional

class DBConfig:
    """Configuration for database connection."""
    def __init__(self, host: str, port: int, database: str, user: str, password: str, charset: str = 'latin1'):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.charset = charset

class DatabaseDriver(ABC):
    """Abstract base class for database drivers."""

    @abstractmethod
    def connect(self, config: DBConfig) -> Any:
        """Establish connection to the database."""
        pass

    @abstractmethod
    def disconnect(self):
        """Close the database connection."""
        pass

    @abstractmethod
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as a list of dictionaries."""
        pass

    @abstractmethod
    def execute_command(self, command: str, params: Optional[tuple] = None) -> int:
        """Execute an INSERT/UPDATE/DELETE command and return affected rows."""
        pass

    @abstractmethod
    def get_table_metadata(self, table_name: str) -> List[Dict[str, Any]]:
        """Get metadata for a specific table."""
        pass
