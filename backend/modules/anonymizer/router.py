from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from backend.modules.anonymizer.service import AnonymizerService

router = APIRouter()
service = AnonymizerService()

class AnonymizeRequest(BaseModel):
    text: str

class ConfigUpdateRequest(BaseModel):
    api_url: str
    model: str
    system_prompt: str
    enable_chat: bool
    enable_outlook: bool
    enable_database: bool
    anonymize_ids: bool = True
    anonymize_emails: bool = True
    anonymize_phones: bool = True
    anonymize_names: bool = True
    preserve_products: bool = True

@router.post("/anonymize")
async def anonymize_text(request: AnonymizeRequest):
    """Anonymizes the provided text using the configured AI."""
    try:
        result = service.anonymize_text(request.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_config():
    """Returns the current configuration."""
    return service.get_config()

@router.post("/config")
async def update_config(config: ConfigUpdateRequest):
    """Updates the anonymizer configuration."""
    try:
        service.save_config(config.dict())
        return {"status": "success", "config": service.get_config()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(limit: int = 20):
    """Returns recent anonymization sessions."""
    try:
        return service.get_history(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
