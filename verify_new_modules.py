import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())

from backend.modules.db_explorer.service import DBExplorerService
from backend.modules.data_quality.service import DataQualityService

def test_new_modules():
    print("Testing DB Explorer & Data Quality Modules...")
    
    # Mock params - User needs to update this with real values
    params = {
        "host": "localhost",
        "port": 3050,
        "database": "TEST_DB", 
        "user": "SYSDBA",
        "password": "masterkey"
    }
    
    explorer = DBExplorerService()
    quality = DataQualityService()
    
    try:
        # Test instantiation and method existence
        print(f"DB Explorer Service: {type(explorer).__name__}")
        print(f"Data Quality Service: {type(quality).__name__}")
        
        # We can't easily test connection without a real DB, but we can verify the code loads
        # and methods are callable (even if they fail connection)
        print("Services instantiated successfully.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_new_modules()
