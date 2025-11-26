"""
Metadatos semánticos de la base de datos.
Mapea conceptos de negocio a tablas y columnas reales.
Ahora centralizado usando DatabaseMetadataManager y db_metadata_optimized.json
"""

from backend.core.config.metadata_manager import get_metadata_manager

# Instancia del gestor
metadata_manager = get_metadata_manager()

# Mantener compatibilidad con código existente que importa DATABASE_METADATA
# aunque se recomienda usar get_semantic_schema()
DATABASE_METADATA = metadata_manager.metadata.get('tables', {})

def get_table_for_concept(concept: str) -> str:
    """
    Encuentra la tabla más apropiada para un concepto de negocio.
    Delegamos en el MetadataManager.
    """
    tables = metadata_manager.find_tables_by_concept(concept)
    if tables:
        return tables[0]
    return None

def get_semantic_schema(max_tables: int = 10) -> str:
    """
    Genera una descripción semántica del esquema para el prompt del sistema.
    Delegamos en el MetadataManager.
    """
    return metadata_manager.get_schema_for_ai(max_tables=max_tables)

def get_detailed_schema_for_table(table_name: str) -> str:
    """
    Obtiene el esquema detallado de una tabla específica.
    
    Args:
        table_name: Nombre de la tabla
        
    Returns:
        String con el esquema detallado
    """
    table_info = metadata_manager.get_table_info(table_name)
    if not table_info:
        return f"Tabla {table_name} no tiene metadatos definidos."
    
    lines = [f"Tabla: {table_name}"]
    lines.append(f"Descripción: {table_info.get('description', 'N/A')}")
    lines.append("\nColumnas:")
    
    for col_name, col_desc in table_info.get('columns', {}).items():
        lines.append(f"  {col_name}: {col_desc}")
    
    if table_info.get('consultas_comunes'):
        lines.append("\nConsultas comunes:")
        for query in table_info['consultas_comunes']:
            lines.append(f"  - {query}")
    
    return "\n".join(lines)
