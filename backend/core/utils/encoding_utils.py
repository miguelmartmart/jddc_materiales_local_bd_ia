"""
Utilidades para manejo de encoding de Firebird
Centraliza la lógica de decodificación de bytes
"""

import logging

# Configurar logging
logger = logging.getLogger(__name__)

def safe_decode(value, verbose=False):
    """
    Decodifica un valor de forma segura, probando múltiples encodings
    
    Args:
        value: Valor a decodificar (puede ser bytes, str, None, etc.)
        verbose: Si es True, imprime trazas de decodificación
    
    Returns:
        String decodificado o el valor original si no es bytes
    """
    if value is None:
        return None
    
    if isinstance(value, bytes):
        # Mostrar bytes originales si verbose
        if verbose:
            logger.info(f"🔍 Decodificando bytes: {value[:50]}... (len={len(value)})")
            logger.info(f"   Hex: {value[:20].hex()}")
        
        # Intentar UTF-8 primero
        try:
            decoded = value.decode('utf-8')
            if verbose:
                logger.info(f"   ✅ UTF-8 exitoso: {decoded[:50]}...")
            return decoded
        except UnicodeDecodeError as e:
            if verbose:
                logger.info(f"   ❌ UTF-8 falló: {e}")
        
        # Intentar Latin-1 (ISO-8859-1)
        try:
            decoded = value.decode('latin1')
            if verbose:
                logger.info(f"   ✅ Latin-1 exitoso: {decoded[:50]}...")
            return decoded
        except UnicodeDecodeError as e:
            if verbose:
                logger.info(f"   ❌ Latin-1 falló: {e}")
        
        # Intentar CP1252 (Windows Western European)
        try:
            decoded = value.decode('cp1252')
            if verbose:
                logger.info(f"   ✅ CP1252 exitoso: {decoded[:50]}...")
            return decoded
        except UnicodeDecodeError as e:
            if verbose:
                logger.info(f"   ❌ CP1252 falló: {e}")
        
        # Intentar ISO-8859-15 (Latin-9, incluye símbolo €)
        try:
            decoded = value.decode('iso-8859-15')
            if verbose:
                logger.info(f"   ✅ ISO-8859-15 exitoso: {decoded[:50]}...")
            return decoded
        except:
            if verbose:
                logger.info(f"   ❌ ISO-8859-15 falló")
        
        # Último recurso: convertir a string con repr
        result = str(value)
        if verbose:
            logger.info(f"   ⚠️ Usando str(): {result[:50]}...")
        return result
    
    return value


def row_to_dict_safe(columns, row, verbose=False):
    """
    Convierte una fila de Firebird a diccionario manejando encoding
    
    Args:
        columns: Lista de nombres de columnas
        row: Tupla con los valores de la fila
        verbose: Si es True, imprime trazas de decodificación
    
    Returns:
        Diccionario con los datos decodificados
    """
    row_dict = {}
    for col, val in zip(columns, row):
        if verbose and isinstance(val, bytes):
            logger.info(f"🔍 Columna {col}:")
        row_dict[col] = safe_decode(val, verbose=verbose)
    return row_dict


def get_field_value_safe(row_dict, field_name, verbose=False):
    """
    Obtiene el valor de un campo de forma segura
    
    Args:
        row_dict: Diccionario con los datos de la fila
        field_name: Nombre del campo a obtener
        verbose: Si es True, imprime trazas de decodificación
    
    Returns:
        String con el valor decodificado
    """
    field_value = row_dict.get(field_name, '')
    
    if isinstance(field_value, bytes):
        if verbose:
            logger.info(f"🔍 Campo {field_name} es bytes, decodificando...")
        return safe_decode(field_value, verbose=verbose)
    
    return str(field_value) if field_value else ''
