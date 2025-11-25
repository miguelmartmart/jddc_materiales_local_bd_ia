from pydantic import BaseModel
from typing import Dict, Any, Optional

class PromptConfig(BaseModel):
    name: str
    system_prompt: str
    user_prompt_template: str
    complexity_level: str = "expert" # beginner, intermediate, expert

class PromptResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
