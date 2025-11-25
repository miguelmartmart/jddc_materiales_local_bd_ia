from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config.settings import settings
from backend.core.utils.constants import AppConstants

app = FastAPI(
    title=AppConstants.APP_NAME,
    version=AppConstants.VERSION,
    description="Generic AI Database System API"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)



from backend.modules.articles.router import router as articles_router
from backend.modules.prompts.router import router as prompts_router
from backend.modules.db_explorer.router import router as db_explorer_router
from backend.modules.data_quality.router import router as data_quality_router
from backend.modules.models.router import router as models_router

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Mount frontend static files
# Ensure we point to the correct absolute path or relative to execution
frontend_path = os.path.join(os.getcwd(), "frontend")
app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

app.include_router(articles_router, prefix="/api/articles", tags=["Articles"])
app.include_router(prompts_router, prefix="/api/prompts", tags=["Prompts"])
app.include_router(db_explorer_router, prefix="/api/db-explorer", tags=["DB Explorer"])
app.include_router(data_quality_router, prefix="/api/data-quality", tags=["Data Quality"])
app.include_router(models_router, prefix="/api/models", tags=["AI Models"])

from backend.modules.chat.router import router as chat_router
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG)
