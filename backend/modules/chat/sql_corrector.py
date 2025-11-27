"""
SQL Auto-Correction System
Detects SQL errors and requests corrected queries from AI models.
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class SQLCorrector:
    """Handles SQL error detection and automatic correction via AI."""
    
    def __init__(self):
        pass
    
    def detect_error_type(self, error_message: str) -> Dict[str, Any]:
        """
        Detect the type of SQL error from error message.
        
        Args:
            error_message: Error message from database
            
        Returns:
            Dictionary with error type and extracted information
        """
        error_upper = error_message.upper()
        
        # Table unknown
        if 'TABLE UNKNOWN' in error_upper:
            table_name = None
            if 'Table unknown' in error_message:
                parts = error_message.split('Table unknown')
                if len(parts) > 1:
                    table_name = parts[1].strip().split()[0] if parts[1].strip() else None
            return {
                'type': 'table_unknown',
                'table': table_name,
                'message': 'La tabla especificada no existe en la base de datos'
            }
        
        # Column unknown
        if 'COLUMN UNKNOWN' in error_upper:
            column_name = None
            if 'Column unknown' in error_message:
                parts = error_message.split('Column unknown')
                if len(parts) > 1:
                    column_name = parts[1].strip().split()[0] if parts[1].strip() else None
            return {
                'type': 'column_unknown',
                'column': column_name,
                'message': 'La columna especificada no existe en la tabla'
            }
        
        # Syntax error
        if 'SYNTAX' in error_upper or 'TOKEN UNKNOWN' in error_upper:
            token = None
            if 'Token unknown' in error_message:
                parts = error_message.split('Token unknown')
                if len(parts) > 1:
                    token = parts[1].strip().split()[0] if parts[1].strip() else None
            return {
                'type': 'syntax_error',
                'token': token,
                'message': 'Error de sintaxis SQL'
            }
        
        # Unknown error
        return {
            'type': 'unknown',
            'message': error_message
        }
    
    async def request_correction(
        self,
        failed_query: str,
        original_question: str,
        error_message: str,
        error_info: Dict[str, Any],
        db_context: str,
        ai_provider: Any
    ) -> str:
        """
        Request SQL correction from AI model.
        
        Args:
            failed_query: The SQL query that failed
            original_question: User's original question
            error_message: Error message from database
            error_info: Parsed error information
            db_context: Database schema context
            ai_provider: AI provider instance
            
        Returns:
            Corrected SQL query or None if correction failed
        """
        correction_prompt = f"""La siguiente consulta SQL falló con un error en Firebird 2.5.

PREGUNTA ORIGINAL DEL USUARIO:
{original_question}

CONSULTA SQL QUE FALLÓ:
```sql
{failed_query}
```

ERROR RECIBIDO:
{error_message}

TIPO DE ERROR: {error_info['type']}

ESQUEMA DE BASE DE DATOS DISPONIBLE:
{db_context}

REGLAS CRÍTICAS DE FIREBIRD 2.5:
1. Para limitar resultados: SELECT FIRST N ... (NO uses LIMIT, ROWS, o TOP)
2. Para calcular fechas:
   - Sintaxis CORRECTA: DATEADD(MONTH, -N, CURRENT_DATE)
   - Sintaxis INCORRECTA: DATEADD(-N MONTH TO ...) ← NO FUNCIONA
   - Sintaxis INCORRECTA: DATEADD(-N MONTH FROM ...) ← NO FUNCIONA
3. Ejemplos de fechas:
   - Mes pasado: DATEADD(MONTH, -1, CURRENT_DATE)
   - Hace 2 meses: DATEADD(MONTH, -2, CURRENT_DATE)
   - Año pasado: DATEADD(YEAR, -1, CURRENT_DATE)

INSTRUCCIONES:
1. Analiza el error específico: "{error_message}"
2. Si el error menciona "Token unknown" y "MONTH", probablemente es sintaxis incorrecta de DATEADD
3. Genera una consulta SQL CORREGIDA que:
   - Resuelva el error específico
   - Use SOLO las tablas y columnas del esquema proporcionado
   - Mantenga la intención original de la pregunta
   - Use sintaxis válida de Firebird 2.5
4. Devuelve SOLO la consulta SQL corregida entre ```sql y ```
5. NO añadas explicaciones

CONSULTA SQL CORREGIDA:"""

        try:
            response = await ai_provider.generate_text(correction_prompt)
            
            # Extract SQL from response
            if "```sql" in response:
                corrected_sql = response.split("```sql")[1].split("```")[0].strip()
                corrected_sql = corrected_sql.rstrip(';').strip()
                return corrected_sql
            else:
                # If no SQL block, try to extract first line
                lines = [l.strip() for l in response.split('\n') if l.strip()]
                if lines:
                    return lines[0].rstrip(';').strip()
                    
        except Exception as e:
            logger.error(f"[SQL AUTO-CORRECTION] ❌ Error solicitando corrección: {str(e)}")
        
        return None
    
    async def execute_with_correction(
        self,
        sql_query: str,
        original_question: str,
        db_context: str,
        ai_provider: Any,
        execute_func: callable,
        max_retries: int = 2,
        attempt: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL with automatic correction on errors.
        
        Args:
            sql_query: SQL query to execute
            original_question: User's original question
            db_context: Database schema context
            ai_provider: AI provider for corrections
            execute_func: Function to execute SQL (should raise on error)
            max_retries: Maximum correction attempts
            attempt: Current attempt number
            
        Returns:
            Query results
            
        Raises:
            Exception: If all correction attempts fail
        """
        try:
            # Try to execute the query
            results = execute_func(sql_query)
            return results
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"[SQL AUTO-CORRECTION] ❌ Error en consulta (intento {attempt + 1}/{max_retries + 1}): {error_str}")
            
            # Check if we can retry
            if attempt >= max_retries:
                logger.error(f"[SQL AUTO-CORRECTION] ❌ Máximo de intentos de corrección alcanzado")
                raise
            
            # Detect error type
            error_info = self.detect_error_type(error_str)
            logger.info(f"[SQL AUTO-CORRECTION] 🔍 Tipo de error detectado: {error_info['type']}")
            
            if error_info['type'] == 'unknown':
                logger.warning(f"[SQL AUTO-CORRECTION] ⚠️ Tipo de error desconocido, no se puede corregir automáticamente")
                raise
            
            # Request correction from AI
            logger.info(f"[SQL AUTO-CORRECTION] 🤖 Solicitando corrección al modelo IA...")
            corrected_query = await self.request_correction(
                sql_query,
                original_question,
                error_str,
                error_info,
                db_context,
                ai_provider
            )
            
            if not corrected_query or corrected_query.strip() == sql_query.strip():
                logger.warning(f"[SQL AUTO-CORRECTION] ⚠️ El modelo no pudo generar una corrección diferente")
                raise
            
            logger.info(f"[SQL AUTO-CORRECTION] ✓ Consulta corregida recibida")
            logger.info(f"[SQL AUTO-CORRECTION] Nueva consulta: {corrected_query}")
            
            # Retry with corrected query
            return await self.execute_with_correction(
                corrected_query,
                original_question,
                db_context,
                ai_provider,
                execute_func,
                max_retries,
                attempt + 1
            )
