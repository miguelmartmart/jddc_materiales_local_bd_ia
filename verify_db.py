import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import DBConstants

def test_db_connection():
    print("Testing Firebird Connection...")
    
    # Mock config - User needs to update this with real values
    config = DBConfig(
        host="localhost",
        port=3050,
        database="TEST_DB", # Placeholder
        user="SYSDBA",
        password="masterkey"
    )
    
    try:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
        # We expect this to fail if DB doesn't exist, but it verifies the driver loads
        print(f"Driver loaded: {type(driver).__name__}")
        print("Connection test skipped (requires real DB path). Driver instantiation successful.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_db_connection()
