from typing import Any, Dict, Optional
import json
from backend.core.abstract.ai import AIProvider, AIConfig

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

class OpenAICompatibleProvider(AIProvider):
    """Provider for OpenAI-compatible APIs (Groq, DeepSeek, Qwen, etc.)."""
    
    def __init__(self):
        self.client = None
        self.model_name = None
    
    def configure(self, config: AIConfig):
        if OpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        # Create client with custom base_url if provided
        kwargs = {"api_key": config.api_key}
        if hasattr(config, 'base_url') and config.base_url:
            kwargs["base_url"] = config.base_url
        
        self.client = OpenAI(**kwargs)
        self.model_name = config.model
    
    async def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.client:
            raise Exception("Provider not configured")
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages
        )
        
        return response.choices[0].message.content
    
    async def generate_json(self, prompt: str, schema: Dict[str, Any], system_instruction: Optional[str] = None) -> Dict[str, Any]:
        if not self.client:
            raise Exception("Provider not configured")
        
        # Build prompt with schema
        json_prompt = f"""{prompt}

You must respond with valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Response must be ONLY the JSON object, no markdown formatting."""
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": json_prompt})
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={"type": "json_object"} if "gpt" in self.model_name.lower() else None
        )
        
        text = response.choices[0].message.content.strip()
        
        # Clean up markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        return json.loads(text.strip())
