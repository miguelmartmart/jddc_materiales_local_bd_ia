import aiohttp
import logging
from typing import List, Dict, Any
from backend.core.config.settings import settings

logger = logging.getLogger(__name__)

class ModelDiscoveryService:
    """Service to discover available models from various AI providers."""

    async def discover_google(self) -> List[Dict[str, Any]]:
        api_key = settings.GEMINI_API_KEY or settings.GOOGLE_AI_STUDIO_API_KEY
        if not api_key:
            return []
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [{
                            "id": m['name'].replace('models/', ''),
                            "name": m.get('displayName', m['name']),
                            "provider": "gemini",
                            "model_id": m['name'], # Keep full resource name e.g. models/gemini-pro
                            "description": m.get('description', ''),
                            "context_window": m.get('inputTokenLimit', 0)
                        } for m in data.get('models', [])]
                    else:
                        logger.error(f"Google discovery failed: {response.status} {await response.text()}")
                        return []
        except Exception as e:
            logger.error(f"Google discovery error: {e}")
            return []

    async def discover_openai(self) -> List[Dict[str, Any]]:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            return []
            
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [{
                            "id": m['id'],
                            "name": m['id'], # OpenAI doesn't give pretty names
                            "provider": "openai",
                            "model_id": m['id'],
                            "created": m['created']
                        } for m in data.get('data', [])]
                    else:
                        logger.error(f"OpenAI discovery failed: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"OpenAI discovery error: {e}")
            return []

    async def discover_anthropic(self) -> List[Dict[str, Any]]:
        api_key = settings.ANTHROPIC_CLAUDE_API_KEY
        if not api_key:
            return []
            
        url = "https://api.anthropic.com/v1/models"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Anthropic list endpoint might check docs if it exists standardly, 
                        # User provided: GET /v1/models
                        return [{
                            "id": m['id'],
                            "name": m['display_name'],
                            "provider": "anthropic",
                            "model_id": m['id']
                        } for m in data.get('data', [])]
                    else:
                        logger.error(f"Anthropic discovery failed: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Anthropic discovery error: {e}")
            return []

    async def discover_groq(self) -> List[Dict[str, Any]]:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return []
            
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [{
                            "id": m['id'],
                            "name": m['id'],
                            "provider": "groq",
                            "model_id": m['id']
                        } for m in data.get('data', [])]
                    else:
                        logger.error(f"Groq discovery failed: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Groq discovery error: {e}")
            return []

    async def discover_all(self):
        results = {}
        results['gemini'] = await self.discover_google()
        results['openai'] = await self.discover_openai()
        results['anthropic'] = await self.discover_anthropic()
        results['groq'] = await self.discover_groq()
        return results

discovery_service = ModelDiscoveryService()
