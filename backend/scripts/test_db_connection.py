import sys
import os
from pathlib import Path
import time
import firebirdsql

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.core.config.settings import settings

def test_connection_stability():
    print("Testing Firebird connection stability (DIRECT)...")
    
    db_user = "SYSDBA"
    db_pass = "masterkey"
    db_host = "127.0.0.1"
    db_port = 3050
    db_name = settings.DB_NAME
    
    print(f"Config: Host={db_host}, Port={db_port}, User={db_user}, DB={db_name}")
    
    if not db_name:
        print("❌ ERROR: DB_NAME is empty!")
        return

    try:
        print("1. Connecting directly with firebirdsql...")
        conn = firebirdsql.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass,
            charset="latin1"
        )
        print("   Connected.")
        
        print("2. Executing simple query...")
        cursor = conn.cursor()
        cursor.execute("SELECT FIRST 1 * FROM RDB$DATABASE")
        print("   Query success.")
        cursor.close()
        conn.close()
        print("   Disconnected.")
        
    except Exception as e:
        print(f"\n❌ ERROR CAUGHT: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection_stability()
