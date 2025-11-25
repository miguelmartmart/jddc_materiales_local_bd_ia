"""
Metadatos semánticos de la base de datos.
Mapea conceptos de negocio a tablas y columnas reales.
"""

DATABASE_METADATA = {
    "ARTICULO": {
        "descripcion": "Productos/artículos del inventario",
        "conceptos": ["productos", "artículos", "items", "mercancía", "inventario"],
        "columnas_clave": {
            "CODIGO": "Código único del artículo",
            "NOMBRE": "Nombre/descripción del producto",
            "PVPIVA": "Precio de venta con IVA",
            "PVPSIVA": "Precio de venta sin IVA",
            "PRECIOCMPONDERADO": "Precio de compra ponderado",
            "COSTE": "Precio de coste",
            "STOCK": "Cantidad en stock/inventario",
            "CODFAMILIA": "Código de familia/categoría",
            "CODMARCA": "Código de marca",
            "OBSERVACIONES": "Observaciones del artículo"
        },
        "consultas_comunes": [
            "productos más caros: ORDER BY PVPIVA DESC FIRST 10",
            "productos por precio compra: ORDER BY PRECIOCMPONDERADO DESC",
            "productos con stock: WHERE STOCK > 0",
            "productos sin stock: WHERE STOCK = 0 OR STOCK IS NULL",
            "productos por familia: WHERE CODFAMILIA = 'X'",
            "contar productos: COUNT(*)",
            "productos por nombre: WHERE NOMBRE LIKE '%texto%'"
        ]
    },
    "CLIENTE": {
        "descripcion": "Clientes de la empresa",
        "conceptos": ["clientes", "compradores", "consumidores"],
        "columnas_clave": {
            "CODIGO": "Código único del cliente",
            "NOMBRE": "Nombre o razón social",
            "NIF": "NIF/CIF",
            "DIRECCION": "Dirección postal",
            "TELEFONO": "Teléfono de contacto",
            "EMAIL": "Email de contacto",
            "DESCUENTO": "Descuento aplicable"
        },
        "consultas_comunes": [
            "buscar cliente por nombre: WHERE NOMBRE LIKE '%X%'",
            "clientes con descuento: WHERE DESCUENTO > 0"
        ]
    },
    "FACTURA": {
        "descripcion": "Facturas de venta",
        "conceptos": ["facturas", "ventas", "pedidos facturados"],
        "columnas_clave": {
            "NUMERO": "Número de factura",
            "FECHA": "Fecha de emisión",
            "CLIENTE": "Código del cliente",
            "TOTAL": "Importe total",
            "IVA": "Importe de IVA",
            "PAGADO": "Estado de pago"
        },
        "consultas_comunes": [
            "facturas por cliente: WHERE CLIENTE = X",
            "facturas pendientes: WHERE PAGADO = 'N'",
            "total facturado: SUM(TOTAL)",
            "facturas por fecha: WHERE FECHA BETWEEN X AND Y"
        ]
    },
    "PROVEEDOR": {
        "descripcion": "Proveedores de productos",
        "conceptos": ["proveedores", "suministradores", "distribuidores"],
        "columnas_clave": {
            "CODIGO": "Código único del proveedor",
            "NOMBRE": "Nombre o razón social",
            "NIF": "NIF/CIF",
            "CONTACTO": "Persona de contacto",
            "TELEFONO": "Teléfono"
        },
        "consultas_comunes": [
            "buscar proveedor: WHERE NOMBRE LIKE '%X%'"
        ]
    },
    "PEDIDO": {
        "descripcion": "Pedidos de compra a proveedores",
        "conceptos": ["pedidos", "órdenes de compra", "compras"],
        "columnas_clave": {
            "NUMERO": "Número de pedido",
            "FECHA": "Fecha del pedido",
            "PROVEEDOR": "Código del proveedor",
            "TOTAL": "Importe total",
            "RECIBIDO": "Estado de recepción"
        },
        "consultas_comunes": [
            "pedidos pendientes: WHERE RECIBIDO = 'N'",
            "pedidos por proveedor: WHERE PROVEEDOR = X"
        ]
    }
}

def get_table_for_concept(concept: str) -> str:
    """
    Encuentra la tabla más apropiada para un concepto de negocio.
    
    Args:
        concept: Concepto buscado (ej: "productos", "clientes")
        
    Returns:
        Nombre de la tabla o None si no se encuentra
    """
    concept_lower = concept.lower()
    
    for table_name, metadata in DATABASE_METADATA.items():
        if concept_lower in [c.lower() for c in metadata["conceptos"]]:
            return table_name
    
    return None

def get_semantic_schema() -> str:
    """
    Genera un esquema semántico compacto para enviar a la IA.
    Optimizado para minimizar tokens.
    
    Returns:
        String con el esquema semántico
    """
    schema_lines = ["=== ESQUEMA DE BASE DE DATOS ===\n"]
    
    for table_name, metadata in DATABASE_METADATA.items():
        schema_lines.append(f"\n📊 {table_name}: {metadata['descripcion']}")
        schema_lines.append(f"   Conceptos: {', '.join(metadata['conceptos'])}")
        schema_lines.append(f"   Columnas principales:")
        
        for col_name, col_desc in metadata['columnas_clave'].items():
            schema_lines.append(f"     • {col_name}: {col_desc}")
    
    schema_lines.append("\n=== REGLAS ===")
    schema_lines.append("• Usa SOLO las tablas y columnas listadas arriba")
    schema_lines.append("• Para 'productos' usa tabla ARTICULO")
    schema_lines.append("• Para ordenar por precio: ORDER BY PRECIO DESC")
    schema_lines.append("• Para contar: SELECT COUNT(*) FROM tabla")
    
    return "\n".join(schema_lines)

def get_detailed_schema_for_table(table_name: str) -> str:
    """
    Obtiene el esquema detallado de una tabla específica.
    
    Args:
        table_name: Nombre de la tabla
        
    Returns:
        String con el esquema detallado
    """
    if table_name not in DATABASE_METADATA:
        return f"Tabla {table_name} no tiene metadatos definidos."
    
    metadata = DATABASE_METADATA[table_name]
    lines = [f"Tabla: {table_name}"]
    lines.append(f"Descripción: {metadata['descripcion']}")
    lines.append(f"Conceptos relacionados: {', '.join(metadata['conceptos'])}")
    lines.append("\nColumnas:")
    
    for col_name, col_desc in metadata['columnas_clave'].items():
        lines.append(f"  {col_name}: {col_desc}")
    
    if metadata.get('consultas_comunes'):
        lines.append("\nConsultas comunes:")
        for query in metadata['consultas_comunes']:
            lines.append(f"  - {query}")
    
    return "\n".join(lines)
