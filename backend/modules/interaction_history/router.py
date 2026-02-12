from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from .service import InteractionHistoryService

router = APIRouter()
service = InteractionHistoryService()

@router.get("/logs")
async def get_history_logs(
    limit: int = 50, 
    offset: int = 0, 
    module: Optional[str] = None
):
    try:
        logs = service.get_history(limit=limit, offset=offset, module=module)
        return {"success": True, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
