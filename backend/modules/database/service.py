import json
import os
from typing import Dict, List, Any
import logging
from backend.core.factory.db_factory import DBFactory
from backend.core.utils.constants import DBConstants
from backend.core.abstract.database import DBConfig
from backend.core.config.settings import settings
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.config.model_manager import model_manager

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.metadata_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "core", "config", "db_metadata_optimized.json"
        )

    def get_metadata(self) -> Dict[str, Any]:
        """Reads the current metadata JSON file."""
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading metadata: {e}")
            raise

    def save_metadata(self, data: Dict[str, Any]) -> None:
        """Saves the metadata JSON file."""
        try:
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            raise

    def get_tables(self, db_params: Dict[str, Any] = None) -> List[str]:
        """Lists all user tables in the database."""
        driver = None
        try:
            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
            
            # Use provided params or fallback to settings
            if db_params:
                # Map username to user if needed
                if 'username' in db_params and 'user' not in db_params:
                    db_params['user'] = db_params.pop('username')
                config = DBConfig(**db_params)
            else:
                config = DBConfig(
                    host=settings.DB_HOST,
                    port=settings.DB_PORT,
                    database=settings.DB_NAME,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD
                )
            
            driver.connect(config)
            
            query = "SELECT TRIM(RDB$RELATION_NAME) as NAME FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0 ORDER BY RDB$RELATION_NAME"
            results = driver.execute_query(query)
            return [r['NAME'] for r in results]
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            raise
        finally:
            if driver:
                try:
                    driver.disconnect()
                except:
                    pass

    async def analyze_table(self, table_name: str, db_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyzes a table using AI to generate metadata."""
        driver = None
        try:
            # 1. Get Table Schema
            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
            
            # Use provided params or fallback to settings
            if db_params:
                # Map username to user if needed
                if 'username' in db_params and 'user' not in db_params:
                    db_params['user'] = db_params.pop('username')
                config = DBConfig(**db_params)
            else:
                config = DBConfig(
                    host=settings.DB_HOST,
                    port=settings.DB_PORT,
                    database=settings.DB_NAME,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD
                )

            driver.connect(config)
            
            # Get columns
            query_cols = f"""
            SELECT TRIM(RDB$FIELD_NAME) as FIELD_NAME
            FROM RDB$RELATION_FIELDS 
            WHERE TRIM(RDB$RELATION_NAME) = '{table_name}'
            ORDER BY RDB$FIELD_POSITION
            """
            columns = driver.execute_query(query_cols)
            col_names = [c['FIELD_NAME'] for c in columns]
            
            # Get sample data (first 3 rows)
            query_sample = f"SELECT FIRST 3 * FROM {table_name}"
            try:
                samples = driver.execute_query(query_sample)
            except:
                samples = []
            
            driver.disconnect()
            driver = None

            # 2. Use AI to generate description
            from backend.modules.prompts.service import PromptService
            prompt_service = PromptService()
            prompt_config = prompt_service.get_prompt("database_analysis")
            
            if prompt_config:
                system_prompt_template = prompt_config.get("system_prompt")
            else:
                # Fallback default prompt
                system_prompt_template = """Actúa como un experto en bases de datos. Genera una entrada JSON para la documentación de la tabla '{table_name}'.
                
                Columnas detectadas: {col_names}
                Datos de ejemplo: {samples}
                
                Formato JSON requerido:
                {{
                    "{table_name}": {{
                        "category": "categoría_sugerida",
                        "record_count": 0,
                        "description": "Descripción breve de la tabla",
                        "primary_keys": ["CLAVE_PRIMARIA_SUGERIDA"],
                        "columns": {{
                            "COLUMNA1": "TIPO - Descripción",
                            "COLUMNA2": "TIPO - Descripción"
                        }},
                        "consultas_comunes": [
                            "ejemplo de consulta 1",
                            "ejemplo de consulta 2"
                        ]
                    }}
                }}
                
                Responde SOLO con el JSON válido."""

            # Prepare prompt
            prompt = system_prompt_template.replace("{table_name}", table_name)\
                                         .replace("{col_names}", ', '.join(col_names))\
                                         .replace("{samples}", str(samples))

            # Select Model (Robust)
            # 1. Try preferred models
            preferred_models = ["gemini-1.5-flash", "gemini-1.5-pro", "grok-2-1212", "groq-llama-70b"]
            model_config = None
            
            # Check enabled models
            enabled_models = [m for m in model_manager.list_models() if m.get('enabled')]
            if not enabled_models:
                raise Exception("No AI models enabled for analysis")
                
            # Try to find a preferred model that is enabled
            for pref in preferred_models:
                for m in enabled_models:
                    if m['id'] == pref or m['model_id'] == pref:
                        model_config = m
                        break
                if model_config:
                    break
            
            # If no preferred model found, use the first enabled one
            if not model_config:
                model_config = enabled_models[0]

            print(f"\n{'='*50}")
            print(f"🤖 ANALIZANDO TABLA: {table_name}")
            print(f"🧠 MODELO SELECCIONADO: {model_config['name']} ({model_config['model_id']})")
            print(f"{'='*50}\n")

            provider = AIFactory.get_provider(model_config['provider'])
            ai_config = AIConfig(
                api_key=model_config['api_key'],
                model=model_config['model_id'],
                base_url=model_config.get('base_url')
            )
            provider.configure(ai_config)

            print(f"📤 PROMPT ENVIADO:\n{'-'*20}\n{prompt}\n{'-'*20}\n")
            
            try:
                response = await provider.generate_text(prompt)
                print(f"📥 RESPUESTA RECIBIDA:\n{'-'*20}\n{response}\n{'-'*20}\n")
            except Exception as ai_error:
                print(f"❌ ERROR IA: {ai_error}")
                # Try fallback to another model if available
                if len(enabled_models) > 1:
                    print("🔄 Intentando con otro modelo...")
                    for fallback_model in enabled_models:
                        if fallback_model['id'] != model_config['id']:
                            print(f"🧠 CAMBIANDO A: {fallback_model['name']}")
                            try:
                                provider = AIFactory.get_provider(fallback_model['provider'])
                                ai_config = AIConfig(
                                    api_key=fallback_model['api_key'],
                                    model=fallback_model['model_id'],
                                    base_url=fallback_model.get('base_url')
                                )
                                provider.configure(ai_config)
                                response = await provider.generate_text(prompt)
                                print(f"📥 RESPUESTA RECIBIDA (FALLBACK):\n{'-'*20}\n{response}\n{'-'*20}\n")
                                break
                            except Exception as fallback_error:
                                print(f"❌ ERROR FALLBACK: {fallback_error}")
                                continue
                    else:
                        raise ai_error # All failed
                else:
                    raise ai_error

            
            # Extract JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                raise Exception("AI did not return valid JSON")

        except Exception as e:
            logger.error(f"Error analyzing table {table_name}: {e}")
            print(f"❌ ERROR FATAL: {e}")
            raise
        finally:
            if driver:
                try:
                    driver.disconnect()
                except:
                    pass
