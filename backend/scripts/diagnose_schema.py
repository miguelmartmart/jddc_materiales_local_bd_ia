import os
import sys
from dotenv import load_dotenv
import firebirdsql

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Load env vars
load_dotenv()

def get_connection():
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', 3050))
    database = os.getenv('DB_NAME')
    user = os.getenv('DB_USER', 'SYSDBA')
    password = os.getenv('DB_PASSWORD', 'masterkey')
    
    print(f"Debug: Host={host}, Port={port}, DB={database}, User={user}")
    
    if not database:
        raise ValueError("DB_NAME not set in .env")

    return firebirdsql.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        charset='UTF8'
    )

def list_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT RDB$RELATION_NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 AND RDB$VIEW_BLR IS NULL ORDER BY RDB$RELATION_NAME")
    tables = [row[0].strip() for row in cur.fetchall()]
    return tables

def list_columns(conn, table_name):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT RDB$FIELD_NAME 
        FROM RDB$RELATION_FIELDS 
        WHERE RDB$RELATION_NAME = '{table_name}' 
        ORDER BY RDB$FIELD_POSITION
    """)
    columns = [row[0].strip() for row in cur.fetchall()]
    return columns

def main():
    try:
        print("Connecting to Firebird...")
        conn = get_connection()
        print("Connected successfully!")
        
        tables = list_tables(conn)
        print(f"\nFound {len(tables)} tables.")
        
        # Check for specific tables of interest
        keywords = ['FACT', 'VENT', 'ART', 'PROD', 'CLI', 'CAB', 'LIN']
        print(f"\n--- Searching for tables containing {keywords} ---")
        
        found_tables = []
        for t in tables:
            if any(k in t for k in keywords):
                print(f"Found match: {t}")
                found_tables.append(t)
                cols = list_columns(conn, t)
                print(f"  Columns: {', '.join(cols[:15])}...") 
        
        if not found_tables:
            print("\nNo matching tables found. Listing ALL tables:")
            print(", ".join(tables))
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
