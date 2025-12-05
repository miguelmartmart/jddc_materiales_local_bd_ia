from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from backend.modules.database.service import DatabaseService

router = APIRouter()
service = DatabaseService()

@router.get("/metadata")
async def get_metadata():
    try:
        return service.get_metadata()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/metadata")
async def save_metadata(data: Dict[str, Any]):
    try:
        service.save_metadata(data)
        return {"success": True, "message": "Metadata saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from typing import Optional

class DBRequest(BaseModel):
    db_params: Optional[Dict[str, Any]] = None

@router.post("/tables")
async def get_tables(request: DBRequest):
    try:
        tables = service.get_tables(request.db_params)
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/{table_name}")
async def analyze_table(table_name: str, request: DBRequest):
    try:
        result = await service.analyze_table(table_name, request.db_params)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
