from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from .service import EmailSimulationService

router = APIRouter()
service = EmailSimulationService()

class SimulationRequest(BaseModel):
    subject: str
    sender: str
    body: Optional[str] = ""

@router.post("/simulate")
async def simulate_email_action(request: SimulationRequest):
    try:
        result = await service.simulate_next_step(request.dict())
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
