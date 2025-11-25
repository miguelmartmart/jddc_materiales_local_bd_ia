"""
Sistema de gestión de metadatos de base de datos optimizado para IA
Carga metadatos desde archivo JSON y proporciona búsqueda inteligente
"""

import json
import os
from typing import Dict, List, Optional, Set
from pathlib import Path

class DatabaseMetadataManager:
    """Gestor de metadatos de base de datos optimizado"""
    
    def __init__(self, metadata_file: str = None):
        self.metadata_file = metadata_file or self._get_default_metadata_file()
        self.metadata: Dict = {}
        self.table_index: Dict[str, Set[str]] = {}  # keyword -> set of table names
        self.column_index: Dict[str, Dict[str, Set[str]]] = {}  # table -> column -> keywords
        
        if os.path.exists(self.metadata_file):
            self.load_metadata()
            self._build_indexes()
    
    def _get_default_metadata_file(self) -> str:
        """Obtener ruta por defecto del archivo de metadatos"""
        base_dir = Path(__file__).parent.parent
        return str(base_dir / 'config' / 'db_metadata_optimized.json')
    
    def load_metadata(self):
        """Cargar metadatos desde archivo JSON"""
        with open(self.metadata_file, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
    
    def save_metadata(self, metadata: Dict):
        """Guardar metadatos en archivo JSON"""
        self.metadata = metadata
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        self._build_indexes()
    
    def _build_indexes(self):
        """Construir índices para búsqueda rápida"""
        self.table_index = {}
        self.column_index = {}
        
        for table_name, table_info in self.metadata.get('tables', {}).items():
            # Indexar por nombre de tabla
            keywords = self._extract_keywords(table_name)
            for keyword in keywords:
                if keyword not in self.table_index:
                    self.table_index[keyword] = set()
                self.table_index[keyword].add(table_name)
            
            # Indexar por categoría
            category = table_info.get('category', 'otros')
            if category not in self.table_index:
                self.table_index[category] = set()
            self.table_index[category].add(table_name)
            
            # Indexar columnas
            self.column_index[table_name] = {}
            for col_name in table_info.get('columns', {}).keys():
                col_keywords = self._extract_keywords(col_name)
                for keyword in col_keywords:
                    if keyword not in self.column_index[table_name]:
                        self.column_index[table_name][keyword] = set()
                    self.column_index[table_name][keyword].add(col_name)
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extraer keywords de un texto"""
        # Normalizar y separar por caracteres especiales
        text_upper = text.upper()
        keywords = set()
        
        # Palabra completa
        keywords.add(text_upper)
        
        # Separar por guiones bajos
        parts = text_upper.split('_')
        keywords.update(parts)
        
        # Palabras comunes en español
        common_words = {
            'COD': 'CODIGO',
            'NOM': 'NOMBRE',
            'DESC': 'DESCRIPCION',
            'FEC': 'FECHA',
            'IMP': 'IMPORTE',
            'CANT': 'CANTIDAD',
            'PVP': 'PRECIO',
            'CLI': 'CLIENTE',
            'PROV': 'PROVEEDOR',
            'ART': 'ARTICULO'
        }
        
        for part in parts:
            if part in common_words:
                keywords.add(common_words[part])
        
        return keywords
    
    def find_tables_by_concept(self, concept: str) -> List[str]:
        """Encontrar tablas relacionadas con un concepto"""
        concept_upper = concept.upper()
        keywords = self._extract_keywords(concept_upper)
        
        matching_tables = set()
        for keyword in keywords:
            if keyword in self.table_index:
                matching_tables.update(self.table_index[keyword])
        
        return list(matching_tables)
    
    def find_columns_in_table(self, table_name: str, concept: str) -> List[str]:
        """Encontrar columnas en una tabla relacionadas con un concepto"""
        if table_name not in self.column_index:
            return []
        
        concept_upper = concept.upper()
        keywords = self._extract_keywords(concept_upper)
        
        matching_columns = set()
        for keyword in keywords:
            if keyword in self.column_index[table_name]:
                matching_columns.update(self.column_index[table_name][keyword])
        
        return list(matching_columns)
    
    def get_table_info(self, table_name: str) -> Optional[Dict]:
        """Obtener información completa de una tabla"""
        return self.metadata.get('tables', {}).get(table_name)
    
    def get_tables_by_category(self, category: str) -> List[str]:
        """Obtener tablas por categoría"""
        return list(self.table_index.get(category, set()))
    
    def get_schema_for_ai(self, max_tables: int = 10, categories: List[str] = None) -> str:
        """
        Generar esquema optimizado para enviar a la IA
        
        Args:
            max_tables: Número máximo de tablas a incluir
            categories: Categorías específicas a incluir (None = todas)
        
        Returns:
            String con el esquema en formato legible
        """
        tables = self.metadata.get('tables', {})
        
        # Filtrar por categorías si se especifican
        if categories:
            filtered_tables = {
                name: info for name, info in tables.items()
                if info.get('category') in categories
            }
        else:
            filtered_tables = tables
        
        # Ordenar por número de registros (más importantes primero)
        sorted_tables = sorted(
            filtered_tables.items(),
            key=lambda x: x[1].get('record_count', 0),
            reverse=True
        )[:max_tables]
        
        # Generar esquema
        schema_lines = ["=== ESQUEMA DE BASE DE DATOS ===\n"]
        
        for table_name, table_info in sorted_tables:
            schema_lines.append(f"\n📊 {table_name} ({table_info.get('category', 'otros')})")
            schema_lines.append(f"   Registros: {table_info.get('record_count', 0):,}")
            
            # Primary keys
            pks = table_info.get('primary_keys', [])
            if pks:
                schema_lines.append(f"   PK: {', '.join(pks)}")
            
            # Columnas principales
            columns = table_info.get('columns', {})
            if columns:
                schema_lines.append(f"   Columnas ({len(columns)}):")
                for col_name, col_type in list(columns.items())[:15]:  # Max 15 columnas
                    schema_lines.append(f"     • {col_name}: {col_type}")
                
                if len(columns) > 15:
                    schema_lines.append(f"     ... y {len(columns) - 15} más")
        
        return "\n".join(schema_lines)
    
    def get_focused_schema(self, user_query: str) -> str:
        """
        Generar esquema enfocado basado en la consulta del usuario
        
        Args:
            user_query: Consulta del usuario
        
        Returns:
            Esquema optimizado para esa consulta
        """
        # Detectar conceptos clave en la consulta
        query_upper = user_query.upper()
        
        # Mapeo de conceptos a categorías
        concept_categories = {
            'PRODUCTO': 'productos',
            'ARTICULO': 'productos',
            'CLIENTE': 'clientes',
            'FACTURA': 'ventas',
            'VENTA': 'ventas',
            'PROVEEDOR': 'proveedores',
            'PEDIDO': 'compras',
            'COMPRA': 'compras',
            'STOCK': 'inventario',
            'INVENTARIO': 'inventario'
        }
        
        # Detectar categorías relevantes
        relevant_categories = set()
        for concept, category in concept_categories.items():
            if concept in query_upper:
                relevant_categories.add(category)
        
        # Si no se detectó nada, usar las categorías principales
        if not relevant_categories:
            relevant_categories = {'productos', 'clientes', 'ventas'}
        
        return self.get_schema_for_ai(max_tables=5, categories=list(relevant_categories))
    
    def get_statistics(self) -> Dict:
        """Obtener estadísticas de los metadatos"""
        tables = self.metadata.get('tables', {})
        
        total_tables = len(tables)
        total_columns = sum(len(t.get('columns', {})) for t in tables.values())
        total_records = sum(t.get('record_count', 0) for t in tables.values())
        
        categories = {}
        for table_info in tables.values():
            cat = table_info.get('category', 'otros')
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            'total_tables': total_tables,
            'total_columns': total_columns,
            'total_records': total_records,
            'categories': categories,
            'metadata_file': self.metadata_file,
            'file_size_kb': os.path.getsize(self.metadata_file) / 1024 if os.path.exists(self.metadata_file) else 0
        }


# Instancia global del gestor
_metadata_manager = None

def get_metadata_manager() -> DatabaseMetadataManager:
    """Obtener instancia global del gestor de metadatos"""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = DatabaseMetadataManager()
    return _metadata_manager
