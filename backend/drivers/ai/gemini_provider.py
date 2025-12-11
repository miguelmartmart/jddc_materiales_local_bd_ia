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
            
        json_prompt = f"""
        {prompt}
        
        You must respond with valid JSON matching this schema:
        {json.dumps(schema, indent=2)}
        
        Response must be ONLY the JSON object, no markdown formatting.
        """
        
        if system_instruction:
            # For Gemini models, system_instruction should ideally be passed at __init__, 
            # but since we reuse the instance, we prepend it. 
            # (Alternatively, we could re-init the model per request if we wanted true system prompt support)
            json_prompt = f"System Instruction: {system_instruction}\n\n{json_prompt}"
            
        # Try-catch for model versions that might not support generation_config
        try:
             generation_config = {"response_mime_type": "application/json"}
             response = self.model.generate_content(json_prompt, generation_config=generation_config)
        except:
             # Fallback to standard text generation
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
