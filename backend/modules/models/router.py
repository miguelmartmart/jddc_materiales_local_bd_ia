from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.core.config.model_manager import model_manager

router = APIRouter()

from backend.core.utils.env_manager import env_manager
from backend.modules.models.discovery_service import discovery_service

@router.get("/discovery")
async def discover_models():
    """Fetch available models directly from providers."""
    return await discovery_service.discover_all()

@router.post("/discovery/sync")
async def sync_discovered_models():
    """Discover models and save them to configuration."""
    try:
        discovered = await discovery_service.discover_all()
        # Flatten dictionary to list
        flat_list = []
        for provider, models in discovered.items():
            flat_list.extend(models)
            
        result = model_manager.sync_discovered_models(flat_list)
        return {"success": True, "stats": result, "message": f"Synced: {result['added']} added, {result['updated']} updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class KeyUpdate(BaseModel):
    keys: Dict[str, str]

@router.get("/keys")
async def get_keys_status():
    """Get status of important API keys."""
    target_keys = [
        "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_STUDIO_API_KEY",
        "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ALIBABA_API_KEY", "MISTRAL_API_KEY",
        "ANTHROPIC_CLAUDE_API_KEY", "COHERE_API_KEY", "REKA_API_KEY", "AI21_API_KEY",
        "SNOWFLAKE_API_KEY", "TOGETHER_API_KEY", "FIREWORKS_API_KEY", "HUGGINGFACE_API_KEY",
        "YI_API_KEY", "DASHSCOPE_API_KEY", "APIDOG_KIMI_API_KEY", "ZAI_GLM_API_KEY"
    ]
    raw_values = env_manager.get_keys(target_keys)
    
    result = []
    for k in target_keys:
        val = raw_values.get(k)
        has_val = bool(val and len(val) > 5)
        masked = f"{val[:4]}...{val[-4:]}" if has_val else ""
        result.append({
            "key": k,
            "has_value": has_val,
            "masked": masked,
            "value": "" # Never return full key
        })
    return result

@router.post("/keys")
async def update_keys(data: KeyUpdate):
    """Update API keys in .env file."""
    try:
        # Filter empty values
        updates = {k: v for k, v in data.keys.items() if v and v.strip()}
        if updates:
            env_manager.update_keys(updates)
            # Reload settings/models might be needed, but for now just save
            model_manager.reload() 
        return {"success": True, "message": "Keys updated. Restart might be required for some."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    model_id: str
    description: Optional[str] = None
    enabled: bool = True
    base_url: Optional[str] = None
    has_api_key: bool = False  # Don't expose actual key
    tier: str = "medium"
    score: int = 100
    family: str = "other"
    capabilities: List[str] = ["text"]
    usage: List[str] = ["chat"]
    quota: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None

class ModelCreateUpdate(BaseModel):
    id: Optional[str] = None
    name: str
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_id: str
    description: Optional[str] = None
    enabled: Optional[bool] = True
    parameters: Optional[Dict[str, Any]] = None
    tier: Optional[str] = "medium"
    family: Optional[str] = "other"
    score: Optional[int] = None # Allow manual score override
    capabilities: Optional[List[str]] = ["text"]
    usage: Optional[List[str]] = ["chat"]

@router.get("/", response_model=List[ModelResponse])
async def list_models(enabled_only: bool = False):
    """List all AI models."""
    try:
        models = model_manager.list_models(enabled_only=enabled_only)
        # Don't expose API keys
        return [
            {
                **{k: v for k, v in m.items() if k != 'api_key'},
                'has_api_key': bool(m.get('api_key'))
            }
            for m in models
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{model_id}")
async def get_model(model_id: str):
    """Get a specific model configuration."""
    try:
        model = model_manager.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Don't expose API key
        result = {k: v for k, v in model.items() if k != 'api_key'}
        result['has_api_key'] = bool(model.get('api_key'))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def create_model(model_data: ModelCreateUpdate):
    """Create a new model configuration."""
    try:
        data = model_data.dict(exclude_none=True)
        result = model_manager.add_model(data)
        return {"success": True, "model": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{model_id}")
async def update_model(model_id: str, updates: ModelCreateUpdate):
    """Update an existing model configuration."""
    try:
        data = updates.dict(exclude_none=True)
        result = model_manager.update_model(model_id, data)
        return {"success": True, "model": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{model_id}")
async def delete_model(model_id: str):
    """Delete a model configuration."""
    try:
        success = model_manager.delete_model(model_id)
        if not success:
            raise HTTPException(status_code=404, detail="Model not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{model_id}/reset")
async def reset_score(model_id: str):
    """Reset the score and quota blockage for a model."""
    try:
        model_manager.reset_score(model_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reload")
async def reload_models():
    """Reload models from configuration file."""
    try:
        model_manager.reload()
        return {"success": True, "message": "Models reloaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
