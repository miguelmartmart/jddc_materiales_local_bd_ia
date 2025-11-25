"""
Script para extraer metadatos completos de la base de datos Firebird
y generar un archivo JSON optimizado para el sistema de IA
"""

import firebirdsql
import json
from collections import defaultdict

# Configuración de conexión
DB_CONFIG = {
    'host': 'HOST1',
    'port': 3050,
    'database': r'C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb',
    'user': 'SYSDBA',
    'password': 'masterkey',
    'charset': 'latin1'
}

def connect_db():
    """Conectar a la base de datos"""
    return firebirdsql.connect(**DB_CONFIG)

def get_all_tables(cursor):
    """Obtener todas las tablas de usuario"""
    query = """
        SELECT TRIM(RDB$RELATION_NAME) AS TABLE_NAME
        FROM RDB$RELATIONS
        WHERE RDB$SYSTEM_FLAG = 0
        AND RDB$VIEW_BLR IS NULL
        ORDER BY RDB$RELATION_NAME
    """
    cursor.execute(query)
    return [row[0] for row in cursor.fetchall()]

def get_table_columns(cursor, table_name):
    """Obtener columnas de una tabla con sus tipos"""
    query = """
        SELECT 
            TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME,
            TRIM(f.RDB$FIELD_NAME) AS FIELD_SOURCE,
            f.RDB$FIELD_TYPE AS FIELD_TYPE,
            f.RDB$FIELD_LENGTH AS FIELD_LENGTH,
            r.RDB$NULL_FLAG AS NOT_NULL,
            r.RDB$DEFAULT_SOURCE AS DEFAULT_VALUE
        FROM RDB$RELATION_FIELDS r
        JOIN RDB$FIELDS f ON r.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
        WHERE TRIM(r.RDB$RELATION_NAME) = ?
        ORDER BY r.RDB$FIELD_POSITION
    """
    cursor.execute(query, (table_name,))
    
    # Mapeo de tipos de Firebird
    type_mapping = {
        7: 'SMALLINT',
        8: 'INTEGER',
        10: 'FLOAT',
        12: 'DATE',
        13: 'TIME',
        14: 'CHAR',
        16: 'BIGINT',
        27: 'DOUBLE',
        35: 'TIMESTAMP',
        37: 'VARCHAR',
        261: 'BLOB'
    }
    
    columns = []
    for row in cursor.fetchall():
        field_type = type_mapping.get(row[2], f'TYPE_{row[2]}')
        if field_type in ['CHAR', 'VARCHAR']:
            field_type = f'{field_type}({row[3]})'
        
        columns.append({
            'name': row[0],
            'type': field_type,
            'nullable': row[4] is None,
            'has_default': row[5] is not None
        })
    
    return columns

def get_primary_keys(cursor, table_name):
    """Obtener primary keys de una tabla"""
    query = """
        SELECT TRIM(s.RDB$FIELD_NAME) AS PK_FIELD
        FROM RDB$RELATION_CONSTRAINTS rc
        JOIN RDB$INDEX_SEGMENTS s ON rc.RDB$INDEX_NAME = s.RDB$INDEX_NAME
        WHERE rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
        AND TRIM(rc.RDB$RELATION_NAME) = ?
        ORDER BY s.RDB$FIELD_POSITION
    """
    cursor.execute(query, (table_name,))
    return [row[0] for row in cursor.fetchall()]

def get_foreign_keys(cursor, table_name):
    """Obtener foreign keys de una tabla"""
    query = """
        SELECT 
            TRIM(rc.RDB$CONSTRAINT_NAME) AS FK_NAME,
            TRIM(d.RDB$FIELD_NAME) AS SOURCE_FIELD,
            TRIM(rc2.RDB$RELATION_NAME) AS TARGET_TABLE,
            TRIM(d2.RDB$FIELD_NAME) AS TARGET_FIELD
        FROM RDB$RELATION_CONSTRAINTS rc
        JOIN RDB$REF_CONSTRAINTS refc ON rc.RDB$CONSTRAINT_NAME = refc.RDB$CONSTRAINT_NAME
        JOIN RDB$RELATION_CONSTRAINTS rc2 ON refc.RDB$CONST_NAME_UQ = rc2.RDB$CONSTRAINT_NAME
        JOIN RDB$INDEX_SEGMENTS d ON rc.RDB$INDEX_NAME = d.RDB$INDEX_NAME
        JOIN RDB$INDEX_SEGMENTS d2 ON rc2.RDB$INDEX_NAME = d2.RDB$INDEX_NAME
        WHERE rc.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY'
        AND TRIM(rc.RDB$RELATION_NAME) = ?
    """
    cursor.execute(query, (table_name,))
    
    fks = []
    for row in cursor.fetchall():
        fks.append({
            'name': row[0],
            'source_field': row[1],
            'target_table': row[2],
            'target_field': row[3]
        })
    
    return fks

def get_table_record_count(cursor, table_name):
    """Obtener conteo aproximado de registros"""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]
    except:
        return 0

def classify_table_by_name(table_name):
    """Clasificar tabla por su nombre para categorización"""
    name_upper = table_name.upper()
    
    # Categorías comunes
    if any(x in name_upper for x in ['ARTICULO', 'PRODUCTO', 'ITEM']):
        return 'productos'
    elif any(x in name_upper for x in ['CLIENTE', 'CUSTOMER']):
        return 'clientes'
    elif any(x in name_upper for x in ['FACTURA', 'INVOICE', 'VENTA', 'SALE']):
        return 'ventas'
    elif any(x in name_upper for x in ['PROVEEDOR', 'SUPPLIER']):
        return 'proveedores'
    elif any(x in name_upper for x in ['PEDIDO', 'ORDER', 'COMPRA']):
        return 'compras'
    elif any(x in name_upper for x in ['STOCK', 'INVENTARIO', 'ALMACEN']):
        return 'inventario'
    elif any(x in name_upper for x in ['USUARIO', 'USER', 'EMPLEADO']):
        return 'usuarios'
    elif any(x in name_upper for x in ['CONFIG', 'PARAM', 'SETTING']):
        return 'configuracion'
    else:
        return 'otros'

def extract_metadata():
    """Extraer todos los metadatos de la base de datos"""
    print("🔍 Conectando a la base de datos...")
    conn = connect_db()
    cursor = conn.cursor()
    
    print("📊 Obteniendo lista de tablas...")
    tables = get_all_tables(cursor)
    print(f"✓ Encontradas {len(tables)} tablas")
    
    metadata = {
        'database_info': {
            'total_tables': len(tables),
            'extraction_date': None  # Se añadirá al guardar
        },
        'tables': {},
        'categories': defaultdict(list)
    }
    
    print("\n📋 Extrayendo metadatos de cada tabla...")
    for idx, table_name in enumerate(tables, 1):
        print(f"  [{idx}/{len(tables)}] {table_name}...", end=' ')
        
        try:
            columns = get_table_columns(cursor, table_name)
            primary_keys = get_primary_keys(cursor, table_name)
            foreign_keys = get_foreign_keys(cursor, table_name)
            record_count = get_table_record_count(cursor, table_name)
            category = classify_table_by_name(table_name)
            
            metadata['tables'][table_name] = {
                'columns': columns,
                'primary_keys': primary_keys,
                'foreign_keys': foreign_keys,
                'record_count': record_count,
                'category': category,
                'column_count': len(columns)
            }
            
            metadata['categories'][category].append(table_name)
            
            print(f"✓ ({len(columns)} cols, {record_count} rows)")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    cursor.close()
    conn.close()
    
    return metadata

def save_metadata(metadata, output_file='db_metadata_full.json'):
    """Guardar metadatos en archivo JSON"""
    from datetime import datetime
    
    metadata['database_info']['extraction_date'] = datetime.now().isoformat()
    
    print(f"\n💾 Guardando metadatos en {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Metadatos guardados exitosamente")
    print(f"   Tamaño del archivo: {len(json.dumps(metadata)) / 1024:.2f} KB")

def generate_optimized_metadata(full_metadata, output_file='db_metadata_optimized.json'):
    """Generar versión optimizada solo con información esencial para la IA"""
    print("\n🎯 Generando versión optimizada para IA...")
    
    optimized = {
        'tables': {}
    }
    
    for table_name, table_info in full_metadata['tables'].items():
        # Solo incluir tablas con datos
        if table_info['record_count'] > 0:
            # Solo columnas esenciales (primeras 10 + PKs + FKs)
            essential_columns = {}
            pk_fields = set(table_info['primary_keys'])
            fk_fields = set(fk['source_field'] for fk in table_info['foreign_keys'])
            
            for col in table_info['columns'][:10]:  # Primeras 10 columnas
                essential_columns[col['name']] = col['type']
            
            # Añadir PKs y FKs si no están
            for col in table_info['columns']:
                if col['name'] in pk_fields or col['name'] in fk_fields:
                    essential_columns[col['name']] = col['type']
            
            optimized['tables'][table_name] = {
                'columns': essential_columns,
                'primary_keys': table_info['primary_keys'],
                'category': table_info['category'],
                'record_count': table_info['record_count']
            }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(optimized, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Versión optimizada guardada en {output_file}")
    print(f"   Tamaño: {len(json.dumps(optimized)) / 1024:.2f} KB")
    print(f"   Tablas incluidas: {len(optimized['tables'])}")

if __name__ == '__main__':
    print("=" * 60)
    print("EXTRACTOR DE METADATOS DE BASE DE DATOS FIREBIRD")
    print("=" * 60)
    print()
    print("⚠️  IMPORTANTE: Ajusta DB_CONFIG en este script antes de ejecutar")
    print()
    
    try:
        metadata = extract_metadata()
        save_metadata(metadata)
        generate_optimized_metadata(metadata)
        
        print("\n" + "=" * 60)
        print("✅ PROCESO COMPLETADO")
        print("=" * 60)
        print("\nArchivos generados:")
        print("  1. db_metadata_full.json - Metadatos completos")
        print("  2. db_metadata_optimized.json - Versión optimizada para IA")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
