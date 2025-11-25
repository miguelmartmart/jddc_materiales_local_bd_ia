from fastapi import APIRouter, HTTPException
from backend.modules.articles.models import ArticleAnalysisRequest, ArticleAnalysisResponse, DBConnectionParams
from backend.modules.articles.service import ArticleService

router = APIRouter()
service = ArticleService()

@router.post("/analyze", response_model=ArticleAnalysisResponse)
async def analyze_article(request: ArticleAnalysisRequest):
    try:
        result = await service.analyze_article(
            request.article_name, 
            request.provider, 
            request.model
        )
        return ArticleAnalysisResponse(success=True, result=result)
    except Exception as e:
        return ArticleAnalysisResponse(success=False, result={}, error=str(e))

@router.post("/count")
async def count_articles(params: DBConnectionParams):
    try:
        total = service.get_articles_count(params.dict())
        return {"success": True, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/list")
async def list_articles(params: DBConnectionParams, limit: int = 50, offset: int = 0):
    try:
        results = service.get_articles(params.dict(), limit, offset)
        return {"success": True, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
