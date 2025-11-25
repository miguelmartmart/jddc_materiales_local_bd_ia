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
import logging

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class ChatService:
    
    def __init__(self):
        pass

    async def process_message(self, message: str, context: Dict[str, Any]) -> str:
        logger.info("="*80)
        logger.info(f"{LogPrefixes.CHAT_SERVICE.value} {LogEmojis.NEW_MESSAGE.value} NUEVO MENSAJE RECIBIDO")
        logger.info(f"{LogPrefixes.EMISOR.value} Usuario")
        logger.info(f"{LogPrefixes.MENSAJE.value} {message}")
        logger.info(f"{LogPrefixes.CONTEXTO.value} model_id={context.get('model_id')}")
        logger.info("="*80)
        
        # 1. Get model configuration
        from backend.core.config.model_manager import model_manager
        
        model_id = context.get('model_id', 'gemini-pro')
        logger.info(f"{LogPrefixes.MODELO.value} Solicitando configuración para: {model_id}")
        
        model_config = model_manager.get_model(model_id)
        
        if not model_config:
            logger.error(f"[ERROR] Modelo '{model_id}' no encontrado")
            return f"Error: Modelo '{model_id}' no encontrado en la configuración."
        
        if not model_config.get('enabled', False):
            logger.warning(f"[WARNING] Modelo '{model_config['name']}' está deshabilitado")
            return f"Error: Modelo '{model_config['name']}' está deshabilitado."
        
        logger.info(f"[MODELO] ✓ Configuración cargada: {model_config['name']}")
        logger.info(f"[MODELO] Provider: {model_config['provider']}, Model ID: {model_config['model_id']}")
        
        # 2. Configure AI Provider
        # Use 'schema' to determine which provider class to use (openai_compatible, gemini_native, etc.)
        provider_schema = model_config.get('schema', model_config['provider'])  # Fallback to provider if no schema
        logger.info(f"[AI PROVIDER] Inicializando provider schema: {provider_schema}")
        provider = AIFactory.get_provider(provider_schema)
        
        api_key = model_config.get('api_key')
        if not api_key:
            logger.error(f"[ERROR] No hay API Key configurada para {model_config['name']}")
            return f"Error: No se ha configurado la API Key para el modelo '{model_config['name']}'."

        # Build config with base_url and headers if needed
        config_dict = {
            'api_key': api_key[:10] + "..." if api_key else "None",  # Log only first 10 chars
            'model': model_config['model_id']
        }
        if model_config.get('base_url'):
            config_dict['base_url'] = model_config['base_url']
        if model_config.get('headers'):
            config_dict['headers'] = model_config['headers']
        
        logger.info(f"[AI PROVIDER] Configuración: {config_dict}")
        
        # Create AI config (with full api_key, not truncated)
        ai_config_params = {
            'api_key': api_key,
            'model': model_config['model_id']
        }
        if model_config.get('base_url'):
            ai_config_params['base_url'] = model_config['base_url']
        if model_config.get('headers'):
            ai_config_params['headers'] = model_config['headers']
        
        ai_config = AIConfig(**ai_config_params)
        provider.configure(ai_config)
        logger.info(f"[AI PROVIDER] ✓ Provider configurado correctamente")

        # 2. Get DB Schema Context - Use semantic schema
        logger.info(f"[DATABASE] Generando esquema semántico optimizado...")
        db_context = get_semantic_schema()
        logger.info(f"[DATABASE] Esquema semántico: {len(db_context)} caracteres (optimizado para tokens)")
        
        # 3. Prompt Engineering for Text-to-SQL
        system_prompt = f"""
Eres un asistente experto en bases de datos Firebird SQL.
Convierte preguntas en lenguaje natural a consultas SQL válidas.

{db_context}

INSTRUCCIONES CRÍTICAS:
1. Usa SOLO las tablas y columnas del esquema arriba
2. Para "productos" → tabla ARTICULO
3. Para "clientes" → tabla CLIENTE  
4. Para "facturas/ventas" → tabla FACTURA
5. Genera SQL válido para Firebird 2.5
6. Delimita SQL con ```sql y ```
7. Si no requiere SQL, responde directamente
8. NUNCA inventes tablas o columnas
9. Para limitar resultados usa FIRST N (ej: SELECT FIRST 10)
10. Los precios están en PVPIVA (con IVA) o PVPSIVA (sin IVA)

EJEMPLOS:
- "productos más caros" → SELECT FIRST 10 * FROM ARTICULO ORDER BY PVPIVA DESC
- "cuántos productos" → SELECT COUNT(*) FROM ARTICULO
- "productos con stock" → SELECT * FROM ARTICULO WHERE STOCK > 0
- "clientes con descuento" → SELECT * FROM CLIENTE WHERE DESCUENTO > 0
"""
        
        logger.info(f"{LogPrefixes.AI_PROVIDER.value} {LogEmojis.SEND.value} Enviando mensaje al modelo {model_config['name']}")
        logger.info(f"{LogPrefixes.AI_PROVIDER.value} System Prompt: {len(system_prompt)} caracteres")
        logger.info(f"{LogPrefixes.AI_PROVIDER.value} Mensaje del usuario: '{message}'")
        
        # 4. Generate SQL or Response
        response_text = await provider.generate_text(message, system_instruction=system_prompt)
        
        logger.info(f"[AI PROVIDER] 📥 Respuesta recibida del modelo")
        logger.info(f"[AI PROVIDER] Respuesta completa: {response_text}")
        
        # 5. Execute SQL if present
        if "```sql" in response_text:
            logger.info(f"[SQL] 🔍 Detectada consulta SQL en la respuesta")
            try:
                sql_query = response_text.split(SQLDelimiters.START.value)[1].split(SQLDelimiters.END.value)[0].strip()
                
                # Limpiar query: remover punto y coma al final
                sql_query = sql_query.rstrip(';').strip()
                
                # Añadir FIRST si es SELECT y no tiene FIRST
                sql_upper = sql_query.upper()
                if sql_upper.startswith(SQLKeywords.SELECT.value) and SQLKeywords.FIRST.value not in sql_upper:
                    # Insertar FIRST después de SELECT
                    sql_query = sql_query[:6] + f' {SQLKeywords.FIRST.value} {SQLLimits.DEFAULT_FIRST.value}' + sql_query[6:]
                    logger.info(f"{LogPrefixes.SQL.value} {LogEmojis.WARNING.value} Añadido FIRST {SQLLimits.DEFAULT_FIRST.value} automáticamente para limitar resultados")
                
                logger.info(f"[SQL] Consulta extraída: {sql_query}")
                logger.info(f"[DATABASE] 🔄 Ejecutando consulta SQL...")
                
                results = self._execute_sql(sql_query, context.get('db_params'))
                
                logger.info(f"[DATABASE] ✓ Consulta ejecutada exitosamente")
                logger.info(f"[DATABASE] Resultados: {len(results)} filas")
                logger.info(f"[DATABASE] Datos: {results[:3] if len(results) > 3 else results}")  # First 3 rows
                
                # 6. Interpret Results
                interpretation_prompt = f"""
                Pregunta original: {message}
                Consulta SQL ejecutada: {sql_query}
                Resultados obtenidos: {results}
                
                Responde al usuario de forma natural resumiendo los resultados.
                """
                
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
        
        Instrucciones:
        1. Si la pregunta requiere datos, genera una consulta SQL SELECT válida para Firebird 2.5.
        2. La consulta debe estar delimitada por ```sql y ```.
        3. Si la pregunta es general o no requiere datos, responde amablemente.
        4. NO inventes tablas ni campos. Usa solo los del esquema.
        5. Para contar, usa COUNT(*).
        """
        
        # 4. Generate SQL or Response
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
                
                Responde al usuario de forma natural resumiendo los resultados.
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
            
            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
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
                
                driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
                
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
