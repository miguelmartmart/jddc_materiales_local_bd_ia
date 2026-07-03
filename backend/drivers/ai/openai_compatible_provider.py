from typing import Any, Dict, Optional, Tuple
import json
from backend.core.abstract.ai import AIProvider, AIConfig

_CHARS_PER_TOKEN: float = 4.0
_SAFETY_MARGIN_TOKENS: int = 100


def _estimate_tokens(text: str) -> int:
    """Estima el número de tokens de un texto (1 token ≈ 4 chars, mínimo 1)."""
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def _truncate_to_token_budget(text: str, max_tokens: int) -> Tuple[str, bool]:
    """
    Trunca el texto para que quepa en max_tokens, preservando el FINAL.
    El final del texto tiende a ser la pregunta/tarea más relevante.
    Devuelve (texto_truncado, fue_truncado).
    """
    max_chars = max_tokens * int(_CHARS_PER_TOKEN)
    marker = "\n[TRUNCADO]\n"
    if len(text) <= max_chars:
        return text, False
    effective_chars = max_chars - len(marker)
    truncated = marker + text[-effective_chars:]
    return truncated, True


class OpenAICompatibleProvider(AIProvider):
    """Provider for OpenAI-compatible APIs (Groq, DeepSeek, Qwen, etc.)."""
    
    def __init__(self):
        self.client = None
        self.model_name = None
        self._context_limit: int = 8192
        self._max_tokens: int = 512
        self._timeout_s: int = 120
        self._enable_thinking: bool = True

    def configure(self, config: AIConfig):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        # Create client with custom base_url if provided
        kwargs = {"api_key": config.api_key}
        if hasattr(config, 'base_url') and config.base_url:
            base_url = config.base_url.rstrip("/")
            if base_url.endswith("/chat/completions"):
                base_url = base_url.replace("/chat/completions", "")
            kwargs["base_url"] = base_url

        self.client = OpenAI(**kwargs)
        self.model_name = config.model

        # ── Leer parámetros extendidos desde extra_params ────────────────────
        extra = getattr(config, "extra_params", {})
        params = extra.get("parameters") or {}
        self._context_limit = int(extra.get("context_limit", 8192))
        self._max_tokens = int(params.get("max_tokens", 512))
        self._timeout_s = int(params.get("timeout_s", 120))

        # enable_thinking: explícito > auto-detección (Qwen3 → False)
        if "enable_thinking" in params:
            self._enable_thinking = bool(params["enable_thinking"])
        elif "qwen3" in (self.model_name or "").lower():
            self._enable_thinking = False
        else:
            self._enable_thinking = True

    def _build_extra_body(self) -> Optional[Dict]:
        """Devuelve extra_body para la petición (enable_thinking para Qwen3)."""
        if not self._enable_thinking:
            return {"enable_thinking": False}
        return None

    def _build_messages(self, prompt: str, system_instruction: Optional[str] = None) -> list:
        """Construye la lista de mensajes, truncando el prompt si supera el presupuesto."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
            sys_tokens = _estimate_tokens(system_instruction)
        else:
            sys_tokens = 0

        budget_tokens = self._context_limit - self._max_tokens - _SAFETY_MARGIN_TOKENS - sys_tokens
        prompt_tokens = _estimate_tokens(prompt)

        if prompt_tokens > budget_tokens > 0:
            prompt, _ = _truncate_to_token_budget(prompt, budget_tokens)

        messages.append({"role": "user", "content": prompt})
        return messages
    
    async def generate_text(self, prompt: str, system_instruction: Optional[str] = None, images: list = None, audios: list = None, videos: list = None) -> str:
        if not self.client:
            raise Exception("Provider not configured")
        
        # Determine strict or flexible input mode based on provider/model
        # For simplicity in this generic provider, we use standard OpenAI Vision format
        
        messages = []
        if system_instruction:
             # Some models like o1 don't support system role, but we assume standart behavior here.
            messages.append({"role": "system", "content": system_instruction})
            
        user_content = [{"type": "text", "text": prompt}]
        
        if images:
            for img_b64 in images:
                # Ensure header
                if "," not in img_b64:
                     # Guess png if no header
                    img_b64 = f"data:image/png;base64,{img_b64}"
                
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": img_b64}
                })

        # Audio is typically handled via whisper endpoint, not chat completion "audio" input in standard OpenAI
        # BUT some new models (Gemini via OpenAIcompat, or GPT-4o-audio) might support it.
        # For now, if audios present, we just append a text note (or implement audio-specific logic if known).
        # We will skip audio payload for robust chat completion unless the model is known to handle it.
        # This prevents 400 errors on standard models.
        if audios:
             # Placeholder: In a real advanced provider, we'd use the appropriate audio input format
             pass
             
        if videos:
             # Video support: Typically processed as list of frames (images) or specific video URL input
             # For generic OpenAI compatible, we'll try to treat it as content if possible or skip.
             # Placeholder.
             pass

        messages.append({"role": "user", "content": user_content if images else prompt})
        
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

You must respond with a VALID JSON OBJECT that satisfies the schema below.
CRITICAL: 
- Return ONLY the data object (instance).
- Do NOT return the schema definition (no "properties", "type", etc).
- Do NOT fill the schema in-place.

Target Schema (Reference Only):
{json.dumps(schema, indent=2)}

Response must be ONLY the JSON object."""
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": json_prompt})
        
        # Enable JSON mode for compatible models (Groq/OpenAI/etc)
        use_json_mode = any(x in self.model_name.lower() for x in ["gpt", "llama", "mix", "gemma", "deepseek"])
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={"type": "json_object"} if use_json_mode else None
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

    async def generate_image(self, prompt: str, size: str = "1024x1024", quality: str = "standard") -> str:
        if not self.client:
            raise Exception("Provider not configured")
            
        try:
            response = self.client.images.generate(
                model=self.model_name,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )
            return response.data[0].url
        except Exception as e:
             # If model doesn't support images or other error
             raise Exception(f"Image generation failed: {str(e)}")
