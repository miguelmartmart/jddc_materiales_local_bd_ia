from typing import Dict, Any, List
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.config.settings import settings
from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import (
    DBConstants, DBDefaults, LogPrefixes, LogEmojis,
    SQLDelimiters, SQLLimits, SQLKeywords
)
from backend.drivers.db.firebird_queries import QUERY_TABLES, QUERY_TABLE_COLUMNS
from backend.core.config.database_metadata import get_semantic_schema, get_table_for_concept
from backend.modules.chat.sql_corrector import SQLCorrector
from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
import logging

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ChatService:
    
    def __init__(self):
        self.sql_corrector = SQLCorrector()
        self.model_orchestrator = ModelFallbackOrchestrator()

    async def process_message(self, message: str, context: Dict[str, Any]) -> str:
        logger.info("="*80)
        logger.info(f"{LogPrefixes.CHAT_SERVICE} {LogEmojis.NEW_MESSAGE} NUEVO MENSAJE RECIBIDO")
        logger.info(f"{LogPrefixes.EMISOR} Usuario")
        logger.info(f"{LogPrefixes.MENSAJE} {message}")
        logger.info(f"{LogPrefixes.CONTEXTO} model_id={context.get('model_id')}")
        logger.info("="*80)
        
        # DEBUG: List tables command
        if message.strip() == "DEBUG_TABLES":
            try:
                logger.info("[DEBUG] Ejecutando comando DEBUG_TABLES")
                driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
                
                # Map username to user for DBConfig
                config_params = context.get('db_params', {}).copy()
                if 'username' in config_params:
                    config_params['user'] = config_params.pop('username')
                
                config = DBConfig(**config_params)
                driver.connect(config)
                
                # List tables
                query = "SELECT TRIM(RDB$RELATION_NAME) as NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 ORDER BY RDB$RELATION_NAME"
                results = driver.execute_query(query)
                tables = [r['NAME'] for r in results]
                
                # Find candidates
                keywords = ['FACT', 'VENT', 'CAB', 'ALB']
                candidates = []
                for t in tables:
                    if any(k in t for k in keywords):
                        try:
                            count_res = driver.execute_query(f"SELECT COUNT(*) as C FROM {t}")
                            count = count_res[0]['C']
                            candidates.append(f"{t} ({count} filas)")
                            
                            # Log columns for candidates
                            col_res = driver.execute_query(f"SELECT TRIM(RDB$FIELD_NAME) as F FROM RDB$RELATION_FIELDS WHERE TRIM(RDB$RELATION_NAME) = '{t}'")
                            cols = [c['F'] for c in col_res]
                            logger.info(f"[DEBUG] Tabla {t}: {', '.join(cols)}")
                        except:
                            candidates.append(f"{t} (Error leyendo)")
                
                driver.disconnect()
                return f"Tablas encontradas ({len(tables)}): {', '.join(tables)}\n\nCandidatos facturas:\n" + "\n".join(candidates)
            except Exception as e:
                logger.error(f"[DEBUG ERROR] {str(e)}")
                return f"Error debug: {str(e)}"
        
        # DEBUG: Inspect columns command
        if message.strip().startswith("DEBUG_COLUMNS"):
            try:
                table_name = message.strip().split(" ")[1]
                logger.info(f"[DEBUG] Inspeccionando tabla {table_name}")
                driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
                
                config_params = context.get('db_params', {}).copy()
                if 'username' in config_params:
                    config_params['user'] = config_params.pop('username')
                
                config = DBConfig(**config_params)
                driver.connect(config)
                
                query = f"""
                SELECT TRIM(RDB$FIELD_NAME) as FIELD_NAME
                FROM RDB$RELATION_FIELDS 
                WHERE TRIM(RDB$RELATION_NAME) = '{table_name}'
                ORDER BY RDB$FIELD_POSITION
                """
                results = driver.execute_query(query)
                columns = [r['FIELD_NAME'] for r in results]
                
                # Try to get sample data
                sample = ""
                try:
                    sample_res = driver.execute_query(f"SELECT FIRST 1 * FROM {table_name}")
                    if sample_res:
                        sample = f"\nEjemplo de datos:\n{sample_res[0]}"
                except:
                    sample = "\nNo se pudo obtener datos de ejemplo"

                driver.disconnect()
                return f"Columnas de {table_name}:\n" + "\n".join(columns) + sample
            except Exception as e:
                return f"Error debug columns: {str(e)}"
        
        # 1. Get DB Schema Context - Use semantic schema
        logger.info(f"[DATABASE] Generando esquema semántico optimizado...")
        db_context = get_semantic_schema()
        logger.info(f"[DATABASE] Esquema semántico: {len(db_context)} caracteres (optimizado para tokens)")
        
        # 2. Build conversation history context
        from backend.core.utils.constants import UILimits
        conversation_history = context.get('conversation_history', [])
        
        # Limit to last N messages
        max_history = UILimits.CONVERSATION_MEMORY_MESSAGES
        recent_history = conversation_history[-max_history:] if len(conversation_history) > max_history else conversation_history
        
        # Format conversation history for prompt
        history_context = ""
        if recent_history:
            history_context = "\n\n=== CONTEXTO DE CONVERSACIÓN ANTERIOR ===\n"
            for msg in recent_history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'user':
                    history_context += f"Usuario: {content}\n"
                elif role == 'assistant':
                    history_context += f"Asistente: {content}\n"
            history_context += "=== FIN DEL CONTEXTO ===\n"
            logger.info(f"[CHAT] Incluyendo {len(recent_history)} mensajes de historial en el contexto")
        
        # 3. Prompt Engineering for Text-to-SQL
        system_prompt = f"""
Eres un asistente experto en bases de datos Firebird SQL.
Convierte preguntas en lenguaje natural a consultas SQL válidas.
{history_context}
{db_context}

INSTRUCCIONES CRÍTICAS:
1. Usa SOLO las tablas y columnas del esquema arriba
2. Para "productos" → tabla ARTICULO
3. Para "clientes" → tabla CLIENTE  
4. Para "facturas/ventas" → tabla DOCCAB
5. Genera SQL válido para Firebird 2.5
6. Delimita SQL con ```sql y ```
7. Si no requiere SQL, responde directamente
8. IMPORTANTE: Para limitar resultados usa FIRST N (ej: SELECT FIRST 10...)
9. NUNCA uses LIMIT, ROWS, o TOP - solo FIRST es válido en Firebird

SINTAXIS FIREBIRD PARA FECHAS (MUY IMPORTANTE):
10. Para calcular fechas en Firebird 2.5, usa CAST con aritmética de fechas:
    - Mes actual: WHERE CAST(FECHA AS DATE) >= CAST('FIRST_DAY_OF_MONTH' AS DATE)
    - Mes pasado: Calcula manualmente el primer y último día del mes anterior
    
11. Ejemplos CORRECTOS para consultas de fechas:
    - "facturas de este mes":
      WHERE EXTRACT(MONTH FROM FECHA) = EXTRACT(MONTH FROM CURRENT_DATE)
      AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)
    
    - "facturas del mes pasado" (USAR ESTA SINTAXIS):
      WHERE FECHA >= CAST(EXTRACT(YEAR FROM CURRENT_DATE) || '-' || 
                          CASE WHEN EXTRACT(MONTH FROM CURRENT_DATE) = 1 THEN 12 
                               ELSE EXTRACT(MONTH FROM CURRENT_DATE) - 1 END || '-01' AS DATE)
      AND FECHA < CAST(EXTRACT(YEAR FROM CURRENT_DATE) || '-' || 
                       EXTRACT(MONTH FROM CURRENT_DATE) || '-01' AS DATE)
    
    - ALTERNATIVA MÁS SIMPLE para "mes pasado" (RECOMENDADA):
      WHERE (EXTRACT(YEAR FROM FECHA) * 12 + EXTRACT(MONTH FROM FECHA)) = 
            (EXTRACT(YEAR FROM CURRENT_DATE) * 12 + EXTRACT(MONTH FROM CURRENT_DATE) - 1)
    
    - "hace 2 meses":
      WHERE (EXTRACT(YEAR FROM FECHA) * 12 + EXTRACT(MONTH FROM FECHA)) = 
            (EXTRACT(YEAR FROM CURRENT_DATE) * 12 + EXTRACT(MONTH FROM CURRENT_DATE) - 2)

12. NUNCA uses DATEADD dentro de EXTRACT - NO FUNCIONA en Firebird 2.5


"""
        logger.info(f"[AI PROVIDER] 📤 Usando sistema de fallback multi-modelo...")
        logger.info(f"[AI PROVIDER] System Prompt:\n{system_prompt}")
        logger.info(f"[AI PROVIDER] User Message: {message}")
        
        # Use ModelFallbackOrchestrator for robust multi-model generation
        response_text, used_model_id = await self.model_orchestrator.execute_with_fallback(
            system_prompt=system_prompt,
            user_message=message,
            feedback_callback=None  # TODO: Implement real-time feedback to user
        )
        
        if not response_text:
            logger.error(f"[AI PROVIDER] ❌ Todos los modelos fallaron")
            return "❌ No se pudo generar la consulta con ningún modelo disponible. Por favor, inténtalo más tarde."
        
        logger.info(f"[AI PROVIDER] ✅ Respuesta generada con modelo: {used_model_id}")
        logger.info(f"[AI PROVIDER] Respuesta completa: {response_text}")
        
        # Configure provider for SQL correction and result interpretation
        from backend.core.config.model_manager import model_manager
        model_config = model_manager.get_model(used_model_id)
        
        if model_config:
            provider_schema = model_config.get('schema', model_config.get('provider'))
            provider = AIFactory.get_provider(provider_schema)
            
            ai_config_params = {
                'api_key': model_config.get('api_key'),
                'model': model_config['model_id']
            }
            if model_config.get('base_url'):
                ai_config_params['base_url'] = model_config['base_url']
            if model_config.get('headers'):
                ai_config_params['headers'] = model_config['headers']
            
            ai_config = AIConfig(**ai_config_params)
            provider.configure(ai_config)
        else:
            logger.warning(f"[AI PROVIDER] ⚠️ No se pudo configurar provider para interpretación")
            provider = None
        
        # 5. Execute SQL if present
        if "```sql" in response_text:
            logger.info(f"[SQL] 🔍 Detectada consulta SQL en la respuesta")
            try:
                sql_query = response_text.split(SQLDelimiters.START)[1].split(SQLDelimiters.END)[0].strip()
                
                # Limpiar query: remover punto y coma al final
                sql_query = sql_query.rstrip(';').strip()
                
                # Añadir FIRST si es SELECT y no tiene FIRST
                sql_upper = sql_query.upper()
                if sql_upper.startswith(SQLKeywords.SELECT) and SQLKeywords.FIRST not in sql_upper:
                    # Insertar FIRST después de SELECT
                    sql_query = sql_query[:6] + f' {SQLKeywords.FIRST} {SQLLimits.DEFAULT_FIRST}' + sql_query[6:]
                    logger.info(f"{LogPrefixes.SQL} {LogEmojis.WARNING} Añadido FIRST {SQLLimits.DEFAULT_FIRST} automáticamente para limitar resultados")
                
                logger.info(f"[SQL] Consulta extraída: {sql_query}")
                logger.info(f"[DATABASE] 🔄 Ejecutando consulta SQL...")
                
                # Execute with auto-correction
                results = await self.sql_corrector.execute_with_correction(
                    sql_query=sql_query,
                    original_question=message,
                    db_context=db_context,
                    ai_provider=provider,
                    execute_func=lambda q: self._execute_sql(q, context.get('db_params')),
                    max_retries=DBDefaults.MAX_SQL_CORRECTION_RETRIES
                )
                
                logger.info(f"[DATABASE] ✓ Consulta ejecutada exitosamente")
                logger.info(f"[DATABASE] Resultados: {len(results)} filas")
                logger.info(f"[DATABASE] Datos: {results[:3] if len(results) > 3 else results}")  # First 3 rows
                
                # 6. Interpret Results
                interpretation_prompt = (
                    f"Pregunta original: {message}\n"
                    f"Consulta SQL ejecutada: {sql_query}\n"
                    f"Resultados obtenidos: {results}\n\n"
                    "Responde al usuario siguiendo estas REGLAS ESTRICTAS:\n"
                    "1. NO inventes datos. Usa SOLO los resultados proporcionados.\n"
                    "2. Sé objetivo y directo. Evita frases subjetivas como 'Es importante destacar', 'Los precios pueden variar', etc.\n"
                    "3. Los precios están en EUROS (EUR). Nunca uses el símbolo $.\n"
                    "4. Presenta los datos de forma clara y concisa (lista o tabla si es apropiado).\n"
                    "5. Si no hay resultados, dilo claramente."
                )
                
                logger.info(f"[AI PROVIDER] 📤 Solicitando interpretación de resultados...")
                final_response = await provider.generate_text(interpretation_prompt)
                logger.info(f"[AI PROVIDER] 📥 Interpretación recibida")
                logger.info(f"[RESPUESTA FINAL] {final_response}")
                logger.info("="*80)
                
                return final_response
            except Exception as e:
                logger.error(f"[ERROR SQL] ❌ Error ejecutando consulta: {str(e)}")
                logger.error(f"[ERROR SQL] Consulta fallida: {sql_query}")
                return f"Intenté ejecutar una consulta pero falló: {str(e)}\nConsulta: {sql_query}"
        
        logger.info(f"[RESPUESTA FINAL] {response_text}")
        logger.info("="*80)
        return response_text
        # 1. Get model configuration
        from backend.core.config.model_manager import model_manager
        
        model_id = context.get('model_id', 'gemini-pro')
        model_config = model_manager.get_model(model_id)
        
        if not model_config:
            return f"Error: Modelo '{model_id}' no encontrado en la configuración."
        
        if not model_config.get('enabled', False):
            return f"Error: Modelo '{model_config['name']}' está deshabilitado."
        
        # 2. Configure AI Provider
        provider_name = model_config['provider']
        provider = AIFactory.get_provider(provider_name)
        
        api_key = model_config.get('api_key')
        if not api_key:
            return f"Error: No se ha configurado la API Key para el modelo '{model_config['name']}'."

        # Build config with base_url if needed
        config_dict = {
            'api_key': api_key,
            'model': model_config['model_id']
        }
        if model_config.get('base_url'):
            config_dict['base_url'] = model_config['base_url']
        
        config = AIConfig(**config_dict)
        provider.configure(config)

        # 2. Get DB Schema Context (Simplified)
        # In a real app, we would cache this or retrieve only relevant parts
        db_context = self._get_db_context(context.get('db_params'))
        
        # 3. Prompt Engineering for Text-to-SQL
        system_prompt = f"""
        Eres un asistente experto en bases de datos Firebird SQL.
        Tu tarea es responder a preguntas sobre los datos convirtiéndolas en consultas SQL.
        
        Esquema de la Base de Datos:
        {db_context}
        
        INSTRUCCIONES CRÍTICAS:
        1. Usa SOLO las tablas y columnas definidas en el esquema proporcionado arriba.
        2. NO asumas la existencia de columnas como PVPIVA, STOCK, etc. si no están en el esquema.
        3. Genera SQL válido para Firebird 2.5.
        4. Delimita SQL con ```sql y ```.
        5. Si no requiere SQL, responde directamente.
        6. Para limitar resultados usa FIRST N (ej: SELECT FIRST 10).
        7. Si te preguntan por precios, busca columnas relacionadas con precio/importe en el esquema.
        
        EJEMPLOS GENÉRICOS:
        - "productos más caros" -> SELECT FIRST 10 * FROM [TABLA_ARTICULOS] ORDER BY [COLUMNA_PRECIO] DESC
        - "cuántos productos" -> SELECT COUNT(*) FROM [TABLA_ARTICULOS]
        """
        
        # 4. Generate SQL or Response
        logger.info(f"{LogPrefixes.DATABASE} Esquema semántico COMPLETO:\n{db_context}")
        logger.info(f"{LogPrefixes.AI_PROVIDER} System Prompt COMPLETO:\n{system_prompt}")
        
        response_text = await provider.generate_text(message, system_instruction=system_prompt)
        
        # 5. Execute SQL if present
        if "```sql" in response_text:
            try:
                sql_query = response_text.split("```sql")[1].split("```")[0].strip()
                results = self._execute_sql(sql_query, context.get('db_params'))
                
                # 6. Interpret Results
                interpretation_prompt = f"""
                Pregunta original: {message}
                Consulta SQL ejecutada: {sql_query}
                Resultados obtenidos: {results}
                
                Responde al usuario siguiendo estas REGLAS ESTRICTAS:
                1. NO inventes datos. Usa SOLO los resultados proporcionados.
                2. Sé objetivo y directo. Evita frases subjetivas como "Es importante destacar", "Los precios pueden variar", etc.
                3. Los precios están en EUROS (EUR). Nunca uses el símbolo $.
                4. Presenta los datos de forma clara y concisa (lista o tabla si es apropiado).
                5. Si no hay resultados, dilo claramente.
                """
                final_response = await provider.generate_text(interpretation_prompt)
                return final_response
            except Exception as e:
                return f"Intenté ejecutar una consulta pero falló: {str(e)}\nConsulta: {sql_query}"
        
        return response_text

    def _get_db_context(self, db_params: Dict[str, Any]) -> str:
        if not db_params:
            logger.warning("[DATABASE] No hay parámetros de conexión")
            return "No hay conexión a base de datos definida."
            
        try:
            logger.info(f"[DATABASE] Conectando a: {db_params.get('host')}:{db_params.get('port')}")
            logger.info(f"[DATABASE] Base de datos: {db_params.get('database')}")
            
            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
            # Map username to user for DBConfig
            config_params = db_params.copy()
            if 'username' in config_params:
                config_params['user'] = config_params.pop('username')
            config = DBConfig(**config_params)
            driver.connect(config)
            
            logger.info(f"[DATABASE] ✓ Conexión establecida")
            
            # Get all user tables (excluding system tables)
            logger.info(f"[DATABASE] Consultando lista de tablas...")
            tables = driver.execute_query(QUERY_TABLES)
            table_names = [t['TABLE_NAME'] for t in tables if not t['TABLE_NAME'].startswith('RDB$')]
            logger.info(f"[DATABASE] Tablas de usuario encontradas: {len(table_names)}")
            logger.info(f"[DATABASE] Tablas: {', '.join(table_names[:10])}")  # Log first 10
            
            # Build detailed schema for main tables
            schema_parts = [f"Base de datos Firebird con {len(table_names)} tablas de usuario.\n"]
            schema_parts.append(f"Tablas disponibles: {', '.join(table_names)}\n")
            
            # Get detailed info for important tables (limit to avoid token overflow)
            important_tables = ['ARTICULO', 'CLIENTE', 'FACTURA', 'PROVEEDOR', 'PEDIDO']
            available_important = [t for t in important_tables if t in table_names]
            
            logger.info(f"[DATABASE] Obteniendo esquema detallado de {len(available_important)} tablas principales...")
            
            for table_name in available_important:
                try:
                    logger.info(f"[DATABASE] Consultando columnas de {table_name}...")
                    columns = driver.execute_query(QUERY_TABLE_COLUMNS, (table_name,))
                    
                    if columns:
                        col_details = []
                        for c in columns:
                            col_info = f"  - {c['FIELD_NAME']} ({c['FIELD_TYPE']})"
                            col_details.append(col_info)
                        
                        schema_parts.append(f"\nTabla: {table_name}")
                        schema_parts.append(f"Columnas ({len(columns)}):")
                        schema_parts.extend(col_details)
                        
                        logger.info(f"[DATABASE] {table_name}: {len(columns)} columnas")
                except Exception as e:
                    logger.warning(f"[DATABASE] No se pudo obtener esquema de {table_name}: {str(e)}")
            
            schema = "\n".join(schema_parts)
            
            driver.disconnect()
            logger.info(f"[DATABASE] ✓ Desconectado")
            logger.info(f"[DATABASE] Esquema generado: {len(schema)} caracteres, {len(available_important)} tablas detalladas")
            
            return schema
        except Exception as e:
            logger.error(f"[DATABASE ERROR] ❌ {str(e)}")
            return f"Error obteniendo esquema: {str(e)}"

    def _execute_sql(self, query: str, db_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[DATABASE] Preparando ejecución de consulta...")
        
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            driver = None
            try:
                logger.info(f"[DATABASE] Intento {retry_count + 1}/{max_retries}")
                
                driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
                
                # Map username to user for DBConfig
                config_params = db_params.copy()
                if 'username' in config_params:
                    config_params['user'] = config_params.pop('username')
                
                config = DBConfig(**config_params)
                
                logger.info(f"[DATABASE] Conectando para ejecutar consulta...")
                driver.connect(config)
                
                logger.info(f"[DATABASE] Ejecutando: {query}")
                results = driver.execute_query(query)
                
                logger.info(f"[DATABASE] ✓ Consulta ejecutada: {len(results)} filas retornadas")
                
                return results
                
            except Exception as e:
                last_error = e
                retry_count += 1
                logger.error(f"[DATABASE] ❌ Error en intento {retry_count}: {str(e)}")
                
                if retry_count < max_retries:
                    import time
                    wait_time = retry_count * 0.5  # Espera incremental
                    logger.info(f"[DATABASE] Esperando {wait_time}s antes de reintentar...")
                    time.sleep(wait_time)
            finally:
                if driver:
                    try:
                        driver.disconnect()
                        logger.info(f"[DATABASE] ✓ Desconectado")
                    except:
                        pass
        
        # Si llegamos aquí, todos los intentos fallaron
        error_msg = f"Error después de {max_retries} intentos: {str(last_error)}"
        logger.error(f"[DATABASE] ❌ {error_msg}")
        raise Exception(error_msg)
