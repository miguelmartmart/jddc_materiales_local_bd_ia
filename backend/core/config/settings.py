import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional

# Ruta absoluta al .env — funciona independientemente del CWD al arrancar uvicorn
# El .env está en bots/interjddcia/.env (dos niveles arriba de este archivo)
_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"

class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""
    
    # App
    APP_ENV: str = "development"
    APP_DEBUG: bool = False  # Renombrado de DEBUG para evitar conflicto con DEBUG=WARN del sistema
    PORT: int = 8001
    
    # Database (Default/Fallback)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3050
    DB_NAME: str = ""
    DB_USER: str = "SYSDBA"
    DB_PASSWORD: str = "masterkey"
    
    # AI (API Keys)
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_AI_STUDIO_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    COPILOT_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    ALIBABA_API_KEY: Optional[str] = None
    QWEN_API_KEY: Optional[str] = None
    
    # Extended Providers
    ANTHROPIC_CLAUDE_API_KEY: Optional[str] = None
    APIDOG_KIMI_API_KEY: Optional[str] = None
    ZAI_GLM_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None
    REKA_API_KEY: Optional[str] = None
    YI_API_KEY: Optional[str] = None
    DASHSCOPE_API_KEY: Optional[str] = None
    AI21_API_KEY: Optional[str] = None
    SNOWFLAKE_API_KEY: Optional[str] = None
    TOGETHER_API_KEY: Optional[str] = None
    FIREWORKS_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None

    # JDDC IA Gateway (LAN) — Qwen3 VL 30B local
    # Basic Auth en Base64: admin:aistack2026 → YWRtaW46YWlzdGFjazIwMjY=
    # El valor real de la "API key" es el token Basic Auth codificado en Base64
    JDDCIA_API_KEY: Optional[str] = "YWRtaW46YWlzdGFjazIwMjY="
    JDDCIA_BASE_URL: Optional[str] = "http://jddcia.local/api/vlm/v1"
    JDDCIA_BASE_URL_FALLBACK: Optional[str] = "http://192.168.0.36/api/vlm/v1"

    # Outlook
    OUTLOOK_EMAIL: Optional[str] = None
    OUTLOOK_PASSWORD: Optional[str] = None
    OUTLOOK_PASSWORD_APP: Optional[str] = None

    # Gmail
    GMAIL_EMAIL: Optional[str] = None
    GMAIL_PASSWORD: Optional[str] = None
    
    # Privacy
    REQUIRE_DB_DATA_CONFIRMATION: bool = True
    
    class Config:
        # Ruta absoluta al .env — funciona independientemente del CWD al arrancar uvicorn
        env_file = str(_ENV_FILE)
        case_sensitive = True
        extra = "ignore"  # Allow extra keys in .env without crashing

settings = Settings()
