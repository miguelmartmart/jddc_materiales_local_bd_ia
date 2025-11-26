
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.core.config.settings import settings
from backend.core.factory.db_factory import DBFactory
from backend.core.utils.constants import DBConstants
from backend.core.abstract.database import DBConfig

def extract_metadata():
    print("🚀 Iniciando extracción de metadatos (V2)...")
    
    # Configurar conexión usando settings
    config = DBConfig(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    
    print(f"🔌 Conectando a {config.host}:{config.port} -> {config.database}")
    
    try:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        driver.connect(config)
        print("✅ Conexión establecida")
        
        # Obtener tablas
        print("📊 Obteniendo tablas...")
        tables = driver.execute_query("""
            SELECT TRIM(RDB$RELATION_NAME) AS TABLE_NAME
            FROM RDB$RELATIONS
            WHERE RDB$SYSTEM_FLAG = 0
            AND RDB$VIEW_BLR IS NULL
            ORDER BY RDB$RELATION_NAME
        """)
        
        metadata = {'tables': {}}
        
        for t in tables:
            table_name = t['TABLE_NAME']
            print(f"  - Procesando {table_name}...")
            
            # Columnas
            columns = driver.execute_query("""
                SELECT 
                    TRIM(r.RDB$FIELD_NAME) AS FIELD_NAME,
                    f.RDB$FIELD_TYPE AS FIELD_TYPE
                FROM RDB$RELATION_FIELDS r
                JOIN RDB$FIELDS f ON r.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
                WHERE TRIM(r.RDB$RELATION_NAME) = ?
                ORDER BY r.RDB$FIELD_POSITION
            """, (table_name,))
            
            # PKs
            pks = driver.execute_query("""
                SELECT TRIM(s.RDB$FIELD_NAME) AS PK_FIELD
                FROM RDB$RELATION_CONSTRAINTS rc
                JOIN RDB$INDEX_SEGMENTS s ON rc.RDB$INDEX_NAME = s.RDB$INDEX_NAME
                WHERE rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
                AND TRIM(rc.RDB$RELATION_NAME) = ?
            """, (table_name,))
            
            pk_fields = [pk['PK_FIELD'] for pk in pks]
            
            # Count
            try:
                count_res = driver.execute_query(f"SELECT COUNT(*) as CNT FROM {table_name}")
                count = count_res[0]['CNT']
            except:
                count = 0
                
            metadata['tables'][table_name] = {
                'columns': {c['FIELD_NAME']: str(c['FIELD_TYPE']) for c in columns},
                'primary_keys': pk_fields,
                'record_count': count
            }
            
        # Guardar
        output_file = 'db_metadata_optimized.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
            
        print(f"✅ Metadatos guardados en {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'driver' in locals():
            driver.disconnect()

if __name__ == "__main__":
    extract_metadata()
