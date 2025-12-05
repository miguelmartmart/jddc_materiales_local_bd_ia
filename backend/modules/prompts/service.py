import json
import os
from typing import List, Dict, Any
from backend.modules.prompts.models import PromptConfig

PROMPTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "core", "config", "prompts.json"
)

class PromptService:
    
    def __init__(self):
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(PROMPTS_FILE):
            with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def get_all_prompts(self) -> Dict[str, Any]:
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_prompt(self, config: PromptConfig):
        prompts = self.get_all_prompts()
        prompts[config.name] = config.dict()
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(prompts, f, indent=2)
            
    def get_prompt(self, name: str) -> Dict[str, Any]:
        prompts = self.get_all_prompts()
        return prompts.get(name)
