from fastapi import APIRouter, HTTPException

from backend.modules.employees.service import EmployeesService

router = APIRouter()
service = EmployeesService()


@router.get("/employees-real")
async def list_employees():
    try:
        return {"employees": service.list_employees()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))