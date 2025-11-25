from typing import List, Dict, Any
from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import DBConstants
from backend.drivers.db.firebird_queries import (
    QUERY_TABLES, QUERY_VIEWS, QUERY_PROCEDURES, QUERY_TRIGGERS,
    QUERY_TABLE_COLUMNS, QUERY_RECENT_ACTIVITY, QUERY_ACTIVITY_SUMMARY
)

class DBExplorerService:
    
    def get_metadata(self, params: Dict[str, Any]) -> Dict[str, Any]:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
        config = DBConfig(**params)
        
        try:
            driver.connect(config)
            tables = driver.execute_query(QUERY_TABLES)
            views = driver.execute_query(QUERY_VIEWS)
            procedures = driver.execute_query(QUERY_PROCEDURES)
            triggers = driver.execute_query(QUERY_TRIGGERS)
            
            return {
                "tables": tables,
                "views": views,
                "procedures": procedures,
                "triggers": triggers
            }
        finally:
            driver.disconnect()

    def get_table_columns(self, params: Dict[str, Any], table_name: str) -> List[Dict[str, Any]]:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
        config = DBConfig(**params)
        
        try:
            driver.connect(config)
            return driver.execute_query(QUERY_TABLE_COLUMNS, (table_name,))
        finally:
            driver.disconnect()

    def get_recent_activity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
        config = DBConfig(**params)
        
        try:
            driver.connect(config)
            # Assuming DK$OPERATIONLOG exists
            try:
                activity = driver.execute_query(QUERY_RECENT_ACTIVITY)
                summary = driver.execute_query(QUERY_ACTIVITY_SUMMARY)
                return {"activity": activity, "summary": summary}
            except Exception:
                return {"activity": [], "summary": [], "warning": "Activity log table not found"}
        finally:
            driver.disconnect()
