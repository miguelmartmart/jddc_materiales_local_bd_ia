import google.generativeai as genai
from typing import Any, Dict, Optional
import json
from backend.core.abstract.ai import AIProvider, AIConfig

class GeminiProvider(AIProvider):
    """Concrete implementation for Google Gemini AI."""
    
    def __init__(self):
        self.model = None

    def configure(self, config: AIConfig):
        genai.configure(api_key=config.api_key)
        self.model = genai.GenerativeModel(config.model)

    async def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.model:
            raise Exception("Gemini provider not configured")
        
        # Note: Gemini python SDK handles system instructions differently depending on version/model,
        # but for simplicity we'll prepend it to the prompt if needed or use the system_instruction arg if supported.
        # For this generic implementation, we will assume standard generation.
        
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System Instruction: {system_instruction}\n\nUser Prompt: {prompt}"
            
        response = self.model.generate_content(full_prompt)
        return response.text

    async def generate_json(self, prompt: str, schema: Dict[str, Any], system_instruction: Optional[str] = None) -> Dict[str, Any]:
        if not self.model:
            raise Exception("Gemini provider not configured")
            
        # Enforce JSON structure via prompt engineering for now, 
        # as strict JSON mode varies by model version.
        json_prompt = f"""
        {prompt}
        
        You must respond with valid JSON matching this schema:
        {json.dumps(schema, indent=2)}
        
        Response must be ONLY the JSON object, no markdown formatting.
        """
        
        if system_instruction:
            json_prompt = f"System Instruction: {system_instruction}\n\n{json_prompt}"
            
        response = self.model.generate_content(json_prompt)
        text = response.text.strip()
        
        # Clean up markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        return json.loads(text.strip())
