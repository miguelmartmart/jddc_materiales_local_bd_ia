from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from backend.core.config.settings import settings
from backend.core.utils.constants import AppConstants
from backend.core.utils.network_audit import NetworkAuditLogger
from backend.core.utils.network_audit_constants import NetworkAuditConfig
from backend.core.utils.unsolvable_error_registry import check_and_alert_unsolvable_errors
import datetime
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de la aplicación.
    - Startup: instala el auditor de red global (registra TODAS las conexiones HTTP)
    - Shutdown: desinstala el auditor y escribe el resumen final en el log
    """
    # ── STARTUP ──────────────────────────────────────────────────────────────
    # Instalar auditor de red global — registra todas las conexiones HTTP
    # en logs/network_audit.log. strict=False en producción (no bloquea,
    # solo registra). Para activar modo estricto (bloquea internet):
    #   NetworkAuditLogger.install_global(strict=True)
    NetworkAuditLogger.install_global(
        strict=NetworkAuditConfig.DEFAULT_STRICT_MODE
    )
    logger.info("[MAIN][STARTUP] Auditor de red instalado — log: logs/network_audit.log")

    # ── Alerta de errores irresolubles pendientes de revisión humana ──────────
    # Si hay errores SQL que ni el normalizador ni la IA pudieron resolver,
    # se muestran en consola y log al arrancar para que el equipo los revise.
    try:
        check_and_alert_unsolvable_errors()
    except Exception as _e:
        logger.warning(f"[MAIN][STARTUP] ⚠️ No se pudo comprobar errores irresolubles: {_e}")

    yield  # ── La aplicación está corriendo ──────────────────────────────────

    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    auditor = NetworkAuditLogger.get_global()
    if auditor:
        summary = auditor.get_summary()
        logger.info(
            "[MAIN][SHUTDOWN] Resumen auditoría de red: "
            f"{summary['total_calls']} llamadas totales, "
            f"{summary['lan_calls']} LAN, "
            f"{summary['internet_calls']} internet"
        )
        if summary["internet_calls"] > 0:
            logger.warning(
                f"[MAIN][SHUTDOWN] ⚠️  ATENCION: {summary['internet_calls']} "
                f"llamadas a internet detectadas: {summary['internet_hosts']}"
            )
    NetworkAuditLogger.uninstall_global()
    logger.info("[MAIN][SHUTDOWN] Auditor de red desinstalado")


app = FastAPI(
    title=AppConstants.APP_NAME,
    version=AppConstants.VERSION,
    description="Generic AI Database System API",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint para el cliente Android (DeviaChatClient).
    El app MetaGlass hace GET /health para verificar que el backend está disponible
    antes de enviar consultas de voz al endpoint POST /api/chat/send.
    """
    return JSONResponse({
        "status": "ok",
        "service": "DEVIA Chat API",
        "version": AppConstants.VERSION,
        "timestamp": datetime.datetime.now().isoformat()
    })



from backend.modules.articles.router import router as articles_router
from backend.modules.prompts.router import router as prompts_router
from backend.modules.db_explorer.router import router as db_explorer_router
from backend.modules.data_quality.router import router as data_quality_router
from backend.modules.models.router import router as models_router

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Mount frontend static files
# Use path relative to this file (backend/main.py → ../frontend)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_path = os.path.join(_BASE_DIR, "frontend")
_assets_dir = os.path.join(frontend_path, "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

app.include_router(articles_router, prefix="/api/articles", tags=["Articles"])
app.include_router(prompts_router, prefix="/api/prompts", tags=["Prompts"])
app.include_router(db_explorer_router, prefix="/api/db-explorer", tags=["DB Explorer"])
app.include_router(data_quality_router, prefix="/api/data-quality", tags=["Data Quality"])
app.include_router(models_router, prefix="/api/models", tags=["AI Models"])

from backend.modules.models.test_router import router as test_router
app.include_router(test_router) # Prefix defined in router

from backend.modules.chat.router import router as chat_router
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])

from backend.modules.database.router import router as database_router
app.include_router(database_router, prefix="/api/database", tags=["Database Config"])

from backend.modules.outlook.router import router as outlook_router
app.include_router(outlook_router) # The prefix is already defined in the router itself

from backend.modules.email_simulation.router import router as email_simulation_router
app.include_router(email_simulation_router, prefix="/api/simulation", tags=["Email Simulation"])

from backend.modules.interaction_history.router import router as interaction_history_router
app.include_router(interaction_history_router, prefix="/api/history", tags=["Interaction History"])

from backend.modules.anonymizer.router import router as anonymizer_router
app.include_router(anonymizer_router, prefix="/api/anonymizer", tags=["Anonymizer"])

from backend.modules.images.router import router as images_router
app.include_router(images_router, prefix="/api/images", tags=["Image Services"])

from backend.modules.resources.router import router as resources_router
app.include_router(resources_router, prefix="/api", tags=["Resources"])

from backend.modules.employees.router import router as employees_router
app.include_router(employees_router, prefix="/api", tags=["Employees"])

# Metadata Builder — módulo independiente para construir db_metadata_optimized.json
# con IA local LAN. No interfiere con ningún módulo existente.
from backend.modules.db_explorer.metadata_builder_router import router as metadata_builder_router
app.include_router(metadata_builder_router, prefix="/api/metadata-builder", tags=["Metadata Builder"])

# SIUO — Sistema de Indices Ultra-Optimizado
# Indexacion completa de las 437 tablas, grafo de relaciones, concept_index,
# value_index y ContextRetriever para contexto optimo en el chat IA.
# Endpoints: /api/siuo/analyze/start (SSE), /stats, /learning/*, /context/test
from backend.modules.db_explorer.siuo_router import router as siuo_router
app.include_router(siuo_router, prefix="/api/siuo", tags=["SIUO — Indices IA"])

# Pre-cargar ContextRetriever al arrancar (indices en memoria desde el inicio)
from backend.modules.db_explorer.context_retriever import get_context_retriever as _load_retriever
_load_retriever()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.PORT, reload=settings.APP_DEBUG)
