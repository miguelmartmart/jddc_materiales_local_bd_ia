from fastapi import APIRouter, HTTPException
from backend.modules.prompts.models import PromptConfig, PromptResponse
from backend.modules.prompts.service import PromptService

router = APIRouter()
service = PromptService()

@router.get("/", response_model=PromptResponse)
async def list_prompts():
    try:
        data = service.get_all_prompts()
        return PromptResponse(success=True, message="Prompts retrieved", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=PromptResponse)
async def save_prompt(config: PromptConfig):
    try:
        service.save_prompt(config)
        return PromptResponse(success=True, message="Prompt saved successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
