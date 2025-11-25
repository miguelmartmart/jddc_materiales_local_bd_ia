from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class AIConfig:
    """Configuration for AI Provider."""
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.extra_params = kwargs

class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def configure(self, config: AIConfig):
        """Configure the provider with API keys and settings."""
        pass

    @abstractmethod
    async def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate text response from the model."""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, schema: Dict[str, Any], system_instruction: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured JSON response from the model."""
        pass
