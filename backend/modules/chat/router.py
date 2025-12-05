from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from backend.modules.chat.service import ChatService

router = APIRouter()
service = ChatService()

class ChatRequest(BaseModel):
    message: str
    db_params: Optional[Dict[str, Any]] = None
    model_id: Optional[str] = "groq-llama-70b"
    conversation_history: Optional[List[Dict[str, str]]] = []  # Lista de mensajes anteriores
    confirm_data_sending: Optional[bool] = False

@router.post("/send")
async def send_message(request: ChatRequest):
    try:
        # Pass the full request dict which includes confirm_data_sending
        response = await service.process_message(request.message, request.dict())
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "response": f"Error: {str(e)}"}


