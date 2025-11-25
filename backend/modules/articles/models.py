from pydantic import BaseModel
from typing import Optional, Dict, Any

class ArticleAnalysisRequest(BaseModel):
    article_name: str
    provider: str = "gemini"
    model: Optional[str] = None
    task: str = "analisis_completo"

class ArticleAnalysisResponse(BaseModel):
    success: bool
    result: Dict[str, Any]
    error: Optional[str] = None

class DBConnectionParams(BaseModel):
    host: str
    port: int = 3050
    database: str
    username: str
    password: str
    table_name: str = "ARTICULO"
    field_name: str = "NOMBRE"
