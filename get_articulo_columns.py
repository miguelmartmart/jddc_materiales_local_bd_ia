"""Script temporal para obtener columnas reales de ARTICULO en Firebird."""
import sys
sys.path.insert(0, r'C:\Users\migue\Documents\activepieces\pendiente-fact\bots\interjddcia')

try:
    import firebirdsql
    con = firebirdsql.connect(
        host='192.168.0.254',
        port=3050,
        database=r'C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb',
        user='SYSDBA',
        password='masterkey',
        charset='UTF8'
    )
    cur = con.cursor()
    
    # Columnas de ARTICULO
    cur.execute("""
        SELECT TRIM(RDB$FIELD_NAME) as CAMPO
        FROM RDB$RELATION_FIELDS 
        WHERE TRIM(RDB$RELATION_NAME) = 'ARTICULO'
        ORDER BY RDB$FIELD_POSITION
    """)
    cols = [r[0] for r in cur.fetchall()]
    print("=== COLUMNAS DE ARTICULO ===")
    for c in cols:
        print(f"  {c}")
    print(f"\nTotal: {len(cols)} columnas")
    
    # Muestra de datos (primeras 2 filas, solo columnas básicas)
    print("\n=== MUESTRA (primeras 2 filas) ===")
    try:
        cur.execute("SELECT FIRST 2 CODIGO, NOMBRE FROM ARTICULO")
        for row in cur.fetchall():
            print(f"  CODIGO={row[0]}, NOMBRE={row[1]}")
    except Exception as e:
        print(f"  Error muestra: {e}")
    
    con.close()
    print("\n✅ Conexión cerrada")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
