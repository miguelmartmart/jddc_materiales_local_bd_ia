import sys
import os
from pathlib import Path
import firebirdsql

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.core.config.settings import settings

def inspect_schema():
    print("Inspecting DB Schema...")
    
    db_user = "SYSDBA"
    db_pass = "masterkey"
    db_host = "127.0.0.1"
    db_port = 3050
    db_name = settings.DB_NAME
    
    try:
        conn = firebirdsql.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass,
            charset="latin1"
        )
        cursor = conn.cursor()
        
        # 1. Check CLIENTE columns
        print("\n--- Columns of CLIENTE ---")
        cursor.execute("""
            SELECT TRIM(RDB$FIELD_NAME)
            FROM RDB$RELATION_FIELDS
            WHERE TRIM(RDB$RELATION_NAME) = 'CLIENTE'
            ORDER BY RDB$FIELD_POSITION
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}")
            
        # 2. List all tables (to find 'PROYECTO')
        print("\n--- All Tables ---")
        cursor.execute("""
            SELECT TRIM(RDB$RELATION_NAME)
            FROM RDB$RELATIONS
            WHERE RDB$VIEW_BLR IS NULL 
            AND (RDB$SYSTEM_FLAG IS NULL OR RDB$SYSTEM_FLAG = 0)
            ORDER BY 1
        """)
        tables = [row[0] for row in cursor.fetchall()]
        for t in tables:
            if "PROY" in t or "OBRA" in t:
                print(f"  FOUND POTENTIAL PROJECT TABLE: {t}")
            # else:
            #     print(f"  {t}")
                
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_schema()
