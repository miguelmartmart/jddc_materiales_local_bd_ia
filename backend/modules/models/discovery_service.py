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

    async def discover_lmstudio(self, base_url: str) -> List[Dict[str, Any]]:
        """
        Descubre modelos disponibles en un servidor LM Studio via GET /v1/models.
        Devuelve [] si LM Studio no está disponible (timeout, error de conexión, etc.).
        """
        url = base_url.rstrip("/") + "/v1/models"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = []
                        for m in data.get("data", []):
                            model_id = m.get("id", "")
                            family = "qwen" if "qwen" in model_id.lower() else "other"
                            logical_id = f"jddcia-lmstudio-{model_id.replace('/', '-')}"
                            models.append({
                                "id": logical_id,
                                "model_id": model_id,
                                "base_url": base_url.rstrip("/") + "/v1",
                                "schema": "openai_compatible",
                                "api_key": "lm-studio",
                                "provider": "jddcia",
                                "family": family,
                            })
                        return models
                    return []
        except Exception as e:
            logger.debug(f"[LMStudio] No disponible en {base_url}: {e}")
            return []

    async def discover_all(self):
        results = {}
        results['gemini'] = await self.discover_google()
        results['openai'] = await self.discover_openai()
        results['anthropic'] = await self.discover_anthropic()
        results['groq'] = await self.discover_groq()

        # Descubrir LM Studio en IP y mDNS, deduplicar por model_id
        lmstudio_ip   = await self.discover_lmstudio("http://172.19.64.1:1234")
        lmstudio_mdns = await self.discover_lmstudio("http://jddcia.local:1234")
        seen_model_ids: set = set()
        lmstudio_models: List[Dict[str, Any]] = []
        for model in lmstudio_ip + lmstudio_mdns:
            if model["model_id"] not in seen_model_ids:
                seen_model_ids.add(model["model_id"])
                lmstudio_models.append(model)
        results["lmstudio"] = lmstudio_models
        return results

discovery_service = ModelDiscoveryService()
