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

    async def generate_text(self, prompt: str, system_instruction: Optional[str] = None, images: list = None, audios: list = None, videos: list = None) -> str:
        if not self.model:
            raise Exception("Gemini provider not configured")
        
        content = []
        
        # Add system instruction to prompt if present (simple fallback)
        if system_instruction:
            content.append(f"System: {system_instruction}")
            
        content.append(prompt)
        
        # Process Images
        if images:
            import base64
            for img_b64 in images:
                try:
                    # Clean header if present (data:image/png;base64,...)
                    if "," in img_b64:
                        img_b64 = img_b64.split(",")[1]
                    img_bytes = base64.b64decode(img_b64)
                    content.append({"mime_type": "image/png", "data": img_bytes})
                except Exception as e:
                    print(f"Error processing image: {e}")

        # Process Audio
        if audios:
            import base64
            for audio_b64 in audios:
                try:
                    if "," in audio_b64:
                        audio_b64 = audio_b64.split(",")[1]
                    audio_bytes = base64.b64decode(audio_b64)
                    content.append({"mime_type": "audio/wav", "data": audio_bytes})
                except Exception as e:
                    print(f"Error processing audio: {e}")

        # Process Video
        if videos:
            import base64
            for video_b64 in videos:
                try:
                    if "," in video_b64:
                        video_b64 = video_b64.split(",")[1]
                    video_bytes = base64.b64decode(video_b64)
                    content.append({"mime_type": "video/mp4", "data": video_bytes})
                except Exception as e:
                    print(f"Error processing video: {e}")

        try:
            response = self.model.generate_content(content)
            return response.text
        except Exception as e:
            # Handle API errors gracefully
            if "400" in str(e) or "404" in str(e):
                 raise Exception(f"API Error: {str(e)}")
            raise e

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

    async def generate_image(self, prompt: str, size: str = "1024x1024", quality: str = "standard") -> str:
        # Placeholder for Gemini Imagen integration
        raise Exception("Image generation not yet implemented for Gemini Native provider")
