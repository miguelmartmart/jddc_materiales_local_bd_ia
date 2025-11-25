from typing import Dict, Any, List
from backend.core.factory.db_factory import DBFactory
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.database import DBConfig
from backend.core.abstract.ai import AIConfig
from backend.core.config.settings import settings
from backend.core.utils.constants import DBConstants

class ArticleService:
    
    def __init__(self):
        pass

    async def analyze_article(self, article_name: str, provider_name: str, model: str = None) -> Dict[str, Any]:
        # 1. Get AI Provider
        provider = AIFactory.get_provider(provider_name)
        
        # 2. Configure Provider
        # In a real app, we might fetch keys from a secure store or user input
        api_key = getattr(settings, f"{provider_name.upper()}_API_KEY", None)
        if not api_key:
            raise ValueError(f"API Key for {provider_name} not found in settings")
            
        config = AIConfig(api_key=api_key, model="gemini-pro")
        provider.configure(config)
        
        # 3. Define Schema (This could be dynamic based on 'task')
        schema = {
            "material_principal": "string",
            "categoria": "string",
            "familia": "string",
            "marca": "string",
            "modelo": "string",
            "atributos": {"type": "object"},
            "confidence": "number"
        }
        
        # 4. Generate Analysis
        prompt = f"Analiza el siguiente artículo de ferretería/construcción: '{article_name}'."
        result = await provider.generate_json(prompt, schema)
        
        return result

    def get_articles_count(self, params: Dict[str, Any]) -> int:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
        config = DBConfig(
            host=params['host'],
            port=int(params['port']),
            database=params['database'],
            user=params['username'],
            password=params['password']
        )
        
        try:
            driver.connect(config)
            query = f"SELECT COUNT(*) as TOTAL FROM {params['table_name']}"
            result = driver.execute_query(query)
            return result[0]['TOTAL']
        finally:
            driver.disconnect()

    def get_articles(self, params: Dict[str, Any], limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD.value)
        config = DBConfig(
            host=params['host'],
            port=int(params['port']),
            database=params['database'],
            user=params['username'],
            password=params['password']
        )
        
        try:
            driver.connect(config)
            # Firebird 2.5 uses ROWS x TO y syntax or FIRST x SKIP y
            # Using FIRST/SKIP for compatibility
            query = f"SELECT FIRST {limit} SKIP {offset} * FROM {params['table_name']}"
            return driver.execute_query(query)
        finally:
            driver.disconnect()
