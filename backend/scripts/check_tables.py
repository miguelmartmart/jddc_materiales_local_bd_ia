import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import DBConstants
from backend.core.config.settings import settings

def list_tables():
    print("Conectando a la base de datos...")
    
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
        print("✓ Conectado exitosamente")
        
        # Query to list all tables
        query = """
        SELECT RDB$RELATION_NAME 
        FROM RDB$RELATIONS 
        WHERE RDB$SYSTEM_FLAG = 0 
        ORDER BY RDB$RELATION_NAME
        """
        
        results = driver.execute_query(query)
        
        print(f"\nEncontradas {len(results)} tablas:")
        print("-" * 40)
        
        for row in results:
            name = row['RDB$RELATION_NAME'].strip()
            print(f"- {name}")
            
        print("-" * 40)
        
        # Search for invoice related tables
        print("\nBuscando tablas de facturas (FACT, VENT, CAB)...")
        keywords = ['FACT', 'VENT', 'CAB', 'ALB']
        found = []
        for row in results:
            name = row['RDB$RELATION_NAME'].strip()
            if any(k in name for k in keywords):
                found.append(name)
        
        for name in found:
            print(f"👉 CANDIDATO: {name}")
            
            # Try to count rows to see if it has data
            try:
                count_query = f"SELECT COUNT(*) FROM {name}"
                count_res = driver.execute_query(count_query)
                count = list(count_res[0].values())[0]
                print(f"   Registros: {count}")
            except Exception as e:
                print(f"   Error contando: {e}")

        driver.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    list_tables()
