import os
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional

class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""
    
    # App
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8001
    
    # Database (Default/Fallback)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3050
    DB_NAME: str = ""
    DB_USER: str = "SYSDBA"
    DB_PASSWORD: str = "masterkey"
    
    # AI (API Keys)
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    COPILOT_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    
    # Privacy
    REQUIRE_DB_DATA_CONFIRMATION: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
