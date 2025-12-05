import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import DBConstants
from backend.core.config.settings import settings

def list_cliente_columns():
    print("Connecting to database to inspect CLIENTE table...")
    
    try:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        
        # Config params from settings
        config = DBConfig(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        
        driver.connect(config)
        print("✓ Connected successfully")
        
        # Query to list columns of CLIENTE
        query = """
        SELECT TRIM(RDB$FIELD_NAME) as FIELD_NAME
        FROM RDB$RELATION_FIELDS
        WHERE TRIM(RDB$RELATION_NAME) = 'CLIENTE'
        ORDER BY RDB$FIELD_POSITION
        """
        
        results = driver.execute_query(query)
        
        print(f"\nColumns in CLIENTE ({len(results)}):")
        print("-" * 40)
        
        for row in results:
            print(f"- {row['FIELD_NAME']}")
            
        print("-" * 40)
        
        driver.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    list_cliente_columns()
