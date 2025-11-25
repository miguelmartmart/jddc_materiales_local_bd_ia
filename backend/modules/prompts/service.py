import json
import os
from typing import List, Dict, Any
from backend.modules.prompts.models import PromptConfig

PROMPTS_FILE = "prompts.json"

class PromptService:
    
    def __init__(self):
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(PROMPTS_FILE):
            with open(PROMPTS_FILE, 'w') as f:
                json.dump({}, f)

    def get_all_prompts(self) -> Dict[str, Any]:
        with open(PROMPTS_FILE, 'r') as f:
            return json.load(f)

    def save_prompt(self, config: PromptConfig):
        prompts = self.get_all_prompts()
        prompts[config.name] = config.dict()
        with open(PROMPTS_FILE, 'w') as f:
            json.dump(prompts, f, indent=2)
            
    def get_prompt(self, name: str) -> Dict[str, Any]:
        prompts = self.get_all_prompts()
        return prompts.get(name)
