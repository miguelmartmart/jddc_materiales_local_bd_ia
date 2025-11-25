from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.core.config.model_manager import model_manager

router = APIRouter()

class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    model_id: str
    description: Optional[str] = None
    enabled: bool = True
    base_url: Optional[str] = None
    has_api_key: bool = False  # Don't expose actual key

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

@router.post("/reload")
async def reload_models():
    """Reload models from configuration file."""
    try:
        model_manager.reload()
        return {"success": True, "message": "Models reloaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
