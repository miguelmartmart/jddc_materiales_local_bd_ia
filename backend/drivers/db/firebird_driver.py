import firebirdsql
from typing import Any, List, Dict, Optional
from backend.core.abstract.database import DatabaseDriver, DBConfig
from backend.core.utils.encoding_utils import safe_decode, row_to_dict_safe

class FirebirdDriver(DatabaseDriver):
    """Concrete implementation for Firebird database with robust encoding handling."""

    def __init__(self):
        self.conn = None

    def connect(self, config: DBConfig) -> Any:
        """Establish connection to Firebird database with proper charset handling."""
        try:
            # Use latin1 charset for maximum compatibility with Spanish/European characters
            # latin1 is more permissive and handles special bytes better
            charset = getattr(config, 'charset', 'latin1')
            
            self.conn = firebirdsql.connect(
                host=config.host,
                port=config.port,
                database=config.database,
                user=config.user,
                password=config.password,
                charset=charset
            )
            return self.conn
        except Exception as e:
            raise Exception(f"Error conectando a Firebird: {str(e)}")

    def disconnect(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results with safe encoding handling."""
        if not self.conn:
            raise Exception("No hay conexión activa a la base de datos.")
        
        cursor = self.conn.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            # Use row_to_dict_safe for robust encoding handling
            for row in cursor.fetchall():
                row_dict = row_to_dict_safe(columns, row, verbose=False)
                results.append(row_dict)
            
            return results
        finally:
            cursor.close()

    def execute_command(self, command: str, params: Optional[tuple] = None) -> int:
        """Execute an INSERT/UPDATE/DELETE command and return affected rows."""
        if not self.conn:
            raise Exception("No hay conexión activa a la base de datos.")
            
        cursor = self.conn.cursor()
        try:
            if params:
                cursor.execute(command, params)
            else:
                cursor.execute(command)
            self.conn.commit()
            return cursor.rowcount
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()

    def get_table_metadata(self, table_name: str) -> List[Dict[str, Any]]:
        """Get metadata for a specific table."""
        query = """
        SELECT 
            TRIM(r.RDB$FIELD_NAME) as FIELD_NAME,
            f.RDB$FIELD_TYPE as FIELD_TYPE,
            f.RDB$FIELD_LENGTH as FIELD_LENGTH
        FROM RDB$RELATION_FIELDS r
        JOIN RDB$FIELDS f ON r.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
        WHERE TRIM(r.RDB$RELATION_NAME) = ?
        ORDER BY r.RDB$FIELD_POSITION
        """
        return self.execute_query(query, (table_name,))
