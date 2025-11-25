from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from backend.modules.data_quality.service import DataQualityService

router = APIRouter()
service = DataQualityService()

class ConnectionParams(BaseModel):
    host: str
    port: int = 3050
    database: str
    user: str
    password: str
    charset: str = 'utf8'

class DuplicateRequest(ConnectionParams):
    table_name: str
    field_name: str

@router.post("/duplicates/exact")
async def find_duplicates_exact(request: DuplicateRequest):
    try:
        data = service.find_duplicates_exact(
            request.dict(exclude={'table_name', 'field_name'}), 
            request.table_name, 
            request.field_name
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
