from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from backend.modules.db_explorer.service import DBExplorerService

router = APIRouter()
service = DBExplorerService()

class ConnectionParams(BaseModel):
    host: str
    port: int = 3050
    database: str
    user: str
    password: str
    charset: str = 'utf8'

class TableRequest(ConnectionParams):
    table_name: str

@router.post("/metadata")
async def get_metadata(params: ConnectionParams):
    try:
        data = service.get_metadata(params.dict())
        return {"success": True, "metadata": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/columns")
async def get_columns(request: TableRequest):
    try:
        columns = service.get_table_columns(request.dict(exclude={'table_name'}), request.table_name)
        return {"success": True, "columns": columns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/activity")
async def get_activity(params: ConnectionParams):
    try:
        data = service.get_recent_activity(params.dict())
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
