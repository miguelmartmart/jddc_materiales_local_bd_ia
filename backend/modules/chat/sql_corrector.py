"""
SQL Auto-Correction System
Detects SQL errors and requests corrected queries from AI models.
"""
# DEVIA: backend/modules/chat/DEVIA_ROBUSTNESS.md

from typing import Dict, Any, List
import logging
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

logger = logging.getLogger(__name__)

# Instancia compartida del normalizador determinista
_normalizer = FirebirdSQLNormalizer()


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
        
        # Limit/Rows/Top invalid keywords
        if 'TOKEN UNKNOWN' in error_upper:
            parts = error_message.split('Token unknown')
            token = parts[1].strip().split()[0] if len(parts) > 1 and parts[1].strip() else None
            
            if token and token.upper() in ['LIMIT', 'ROWS', 'TOP']:
                return {
                    'type': 'invalid_keyword',
                    'token': token,
                    'message': f"El comando '{token}' NO existe en Firebird 2.5. Para limitar filas debes usar 'SELECT FIRST N ...'"
                }
            
            return {
                'type': 'syntax_error',
                'token': token,
                'message': 'Error de sintaxis SQL (Token desconocido)'
            }
        
        # Syntax error (General)
        if 'SYNTAX' in error_upper:
            return {
                'type': 'syntax_error',
                'message': 'Error de sintaxis SQL'
            }
        
        # BLOB conversion error: GROUP BY / ORDER BY sobre campo BLOB
        if 'BLOB' in error_upper and 'CONVERSION' in error_upper:
            return {
                'type': 'blob_in_groupby',
                'message': (
                    'Columna BLOB (ej: DESCRIPCION en ARTICULO) no puede usarse en GROUP BY. '
                    'Usa CODIGO, NOMBRE o DESCRIPCIONCORTA en el GROUP BY.'
                )
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
MENSAJE AMIGABLE: {error_info.get('message', '')}

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
4. COLUMNAS CORRECTAS EN TABLA ARTICULO (errores frecuentes del LLM):
   - STOCK → NO EXISTE. Usar STOCKARTICULO (cantidad en inventario)
   - STOCKFACTOR → factor de conversión de unidades (no es el stock)
   - CONTROLSTOCK → indica si el artículo controla stock ('T'/'F'), NO es la cantidad

INSTRUCCIONES:
1. Analiza el error específico: "{error_message}"
2. Si el error es 'invalid_keyword' (LIMIT/ROWS), REESCRIBE usando 'SELECT FIRST N'.
3. Si el error menciona "Token unknown" y "MONTH", revisa sintaxis DATEADD.
4. Genera una consulta SQL CORREGIDA que:
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
    
    def enforce_case_insensitive(self, sql: str) -> str:
        """
        Programmatically enforces case-insensitive LIKE clauses.
        Converts: col LIKE '%val%' -> UPPER(col) LIKE UPPER('%val%')
        """
        import re
        
        # Regex to find simple LIKE clauses: column LIKE 'value'
        # Matches: NOMBRE LIKE '%val%', T.NOMBRE LIKE '%val%'
        # Does NOT match: UPPER(NOMBRE) LIKE ... (due to parenthesis check implied by \s+LIKE)
        pattern = re.compile(r'\b([a-zA-Z0-9_.]+)\s+LIKE\s+\'([^\']*)\'', re.IGNORECASE)
        
        def replace_like(match):
            col = match.group(1)
            val = match.group(2)
            return f"UPPER({col}) LIKE UPPER('{val}')"
            
        new_sql = pattern.sub(replace_like, sql)
        if new_sql != sql:
            logger.info(f"[SQL AUTO-CORRECTION] 🛡️ Aplicada corrección CASE-INSENSITIVE automática")
            logger.info(f"[SQL AUTO-CORRECTION] Original: {sql}")
            logger.info(f"[SQL AUTO-CORRECTION] Corregida: {new_sql}")
        return new_sql
        
    def clean_firebird_sql(self, sql: str) -> str:
        """
        Aggressively cleans SQL to match Firebird 2.5 constraints.
        1. Removes 'LIMIT N' -> Converts to 'SELECT FIRST N' if possible or just strips it.
        2. Removes 'OFFSET N' -> Not supported in FB 2.5 easily.
        3. Fixes known wrong column names in ARTICULO table (e.g. STOCK -> STOCKARTICULO).
        """
        import re
        
        # 1. Handle LIMIT
        # Pattern: SELECT ... LIMIT N ...
        # Goal: SELECT FIRST N ... ...
        
        # Check if LIMIT exists
        if re.search(r'\bLIMIT\s+\d+', sql, re.IGNORECASE):
            # Extract limit value
            limit_match = re.search(r'\bLIMIT\s+(\d+)', sql, re.IGNORECASE)
            if limit_match:
                limit_val = limit_match.group(1)
                
                # Check if it already has FIRST
                if not re.search(r'SELECT\s+FIRST\s+\d+', sql, re.IGNORECASE):
                    # Insert FIRST N after SELECT
                    # This is naive but works for standard queries
                    sql = re.sub(r'SELECT\s+', f'SELECT FIRST {limit_val} ', sql, count=1, flags=re.IGNORECASE)
                    
                # Remove the LIMIT clause
                sql = re.sub(r'\bLIMIT\s+\d+', '', sql, flags=re.IGNORECASE)
                
                logger.info(f"[SQL CLEANER] Corregido LIMIT -> FIRST {limit_val}")

        # 2. Handle ROWS (Alternative to LIMIT often used by AI)
        if re.search(r'\bROWS\s+\d+', sql, re.IGNORECASE):
             # Similar logic
             rows_match = re.search(r'\bROWS\s+(\d+)', sql, re.IGNORECASE)
             if rows_match:
                 val = rows_match.group(1)
                 if not re.search(r'SELECT\s+FIRST\s+\d+', sql, re.IGNORECASE):
                     sql = re.sub(r'SELECT\s+', f'SELECT FIRST {val} ', sql, count=1, flags=re.IGNORECASE)
                 sql = re.sub(r'\bROWS\s+\d+(\s+TO\s+\d+)?', '', sql, flags=re.IGNORECASE)
                 logger.info(f"[SQL CLEANER] Corregido ROWS -> FIRST {val}")

        # 3. Fix known wrong column names in ARTICULO table
        #    The LLM often generates 'STOCK' but the real column is 'STOCKARTICULO'.
        #    We use word-boundary matching to avoid replacing 'STOCKARTICULO' itself.
        #    Pattern: \bSTOCK\b matches 'STOCK' but NOT 'STOCKARTICULO' or 'STOCKFACTOR'.
        ARTICULO_COLUMN_FIXES = {
            # wrong_name: correct_name
            r'\bSTOCK\b': 'STOCKARTICULO',   # LLM generates STOCK, real col is STOCKARTICULO
        }
        for wrong_pattern, correct_col in ARTICULO_COLUMN_FIXES.items():
            if re.search(wrong_pattern, sql, re.IGNORECASE):
                sql_fixed = re.sub(wrong_pattern, correct_col, sql, flags=re.IGNORECASE)
                if sql_fixed != sql:
                    logger.info(
                        f"[SQL CLEANER] Corregida columna erronea: "
                        f"'{wrong_pattern}' -> '{correct_col}' en ARTICULO"
                    )
                    sql = sql_fixed

        return sql

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
        # En el primer intento: aplicar normalización determinista completa
        # (FirebirdSQLNormalizer cubre todo lo que antes hacían enforce_case_insensitive
        # y clean_firebird_sql, más 15 correcciones adicionales)
        if attempt == 0:
            sql_query, norm_changes = _normalizer.normalize(sql_query)
            if norm_changes:
                logger.info(f"[SQL AUTO-CORRECTION] 🔧 {len(norm_changes)} normalizaciones deterministas aplicadas antes de ejecutar")

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

            # ── Intento 1: corrección DETERMINISTA (sin IA) ───────────────────
            # Para errores conocidos (BLOB, column_unknown, token_unknown) el
            # normalizador puede corregir sin gastar tokens de IA.
            deterministic_types = {'blob_in_groupby', 'column_unknown', 'invalid_keyword', 'syntax_error'}
            if error_info['type'] in deterministic_types:
                det_query, det_changes = _normalizer.fix_after_error(sql_query, error_str)
                if det_changes and det_query.strip() != sql_query.strip():
                    logger.info(f"[SQL AUTO-CORRECTION] ✅ Corrección DETERMINISTA aplicada ({len(det_changes)} cambios):")
                    for ch in det_changes:
                        logger.info(f"[SQL AUTO-CORRECTION]   • {ch}")
                    return await self.execute_with_correction(
                        det_query, original_question, db_context, ai_provider,
                        execute_func, max_retries, attempt + 1
                    )
                else:
                    logger.info(f"[SQL AUTO-CORRECTION] ℹ️ Corrección determinista no aplicable, escalando a IA...")

            # ── Intento 2: corrección por IA ──────────────────────────────────
            logger.info(f"[SQL AUTO-CORRECTION] 🤖 Solicitando corrección al modelo IA...")
            corrected_query = await self.request_correction(
                sql_query, original_question, error_str, error_info, db_context, ai_provider
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
