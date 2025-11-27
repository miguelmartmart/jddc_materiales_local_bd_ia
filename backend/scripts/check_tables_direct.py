import os
import sys
import firebirdsql

def check_tables_direct():
    # Hardcoded credentials from .env
    host = 'localhost'
    port = 3050
    # Path extracted from .env output
    database = r'C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb'
    user = 'SYSDBA'
    password = 'masterkey'
    
    print(f"Configuración:")
    print(f"Host: {host}:{port}")
    print(f"Database: {database}")
    print(f"User: {user}")
    
    try:
        print("\nConectando directamente con firebirdsql...")
        conn = firebirdsql.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            charset='latin1'
        )
        print("✓ Conectado exitosamente")
        
        cursor = conn.cursor()
        
        # Inspect DOCCAB columns
        print("\nInspeccionando DOCCAB...")
        query = """
        SELECT TRIM(RDB$FIELD_NAME)
        FROM RDB$RELATION_FIELDS
        WHERE TRIM(RDB$RELATION_NAME) = 'DOCCAB'
        ORDER BY RDB$FIELD_POSITION
        """
        
        cursor.execute(query)
        cols = [row[0] for row in cursor.fetchall()]
        
        print(f"Columnas encontradas ({len(cols)}):")
        print("-" * 40)
        # Print all columns to find the right ones
        for c in cols:
            print(f"- {c}")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    check_tables_direct()
