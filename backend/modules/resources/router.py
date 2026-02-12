from fastapi import APIRouter, HTTPException

from backend.modules.resources.service import ResourcesService

router = APIRouter()
service = ResourcesService()


@router.get("/resources")
async def list_resources():
    try:
        return {"resources": service.list_resources()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))