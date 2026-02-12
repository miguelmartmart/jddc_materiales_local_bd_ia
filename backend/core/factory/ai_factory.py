from backend.core.abstract.ai import AIProvider
from backend.drivers.ai.gemini_provider import GeminiProvider
from backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider

class AIFactory:
    """Factory for creating AI provider instances."""
    
    @staticmethod
    def get_provider(provider_name: str) -> AIProvider:
        """Get an AI provider by name."""
        if provider_name == "gemini" or provider_name == "gemini_native":
            return GeminiProvider()
        elif provider_name in [
            "openai_compatible", "openrouter", "groq", "openai", "deepseek", "qwen", 
            "mistral", "anthropic", "dashscope", "zhipu", "together", "01ai", "azure", 
            "cohere", "reka", "openbrain", "perplexity", "xai", "fireworks", "huggingface"
        ]:
            # All these providers use OpenAI-compatible API
            return OpenAICompatibleProvider()
        else:
            raise ValueError(f"Unsupported AI provider: {provider_name}")
