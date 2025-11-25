import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from backend.core.config.settings import settings

class ModelManager:
    """Manages AI model configurations from JSON file."""
    
    def __init__(self):
        self.config_path = Path(__file__).parent / "ai_models_config.json"
        self.providers_path = Path(__file__).parent / "ai_providers_config.json"
        self.providers = self._load_providers()
        self.models = self._load_models()
    
    def _load_providers(self) -> Dict[str, Dict[str, Any]]:
        """Load provider configurations from JSON file."""
        try:
            if not self.providers_path.exists():
                return {}
            
            with open(self.providers_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('providers', {})
        except Exception as e:
            print(f"Error loading providers config: {e}")
            return {}
    
    def _get_api_key_from_env(self, env_var_name: str) -> Optional[str]:
        """Get API key from settings based on environment variable name."""
        key_mapping = {
            'GROQ_API_KEY': settings.GROQ_API_KEY,
            'OPENROUTER_API_KEY': settings.OPENROUTER_API_KEY,
            'GEMINI_API_KEY': settings.GEMINI_API_KEY,
            'OPENAI_API_KEY': settings.OPENAI_API_KEY
        }
        return key_mapping.get(env_var_name)
    
    def _load_models(self) -> List[Dict[str, Any]]:
        """Load models from JSON configuration file and merge with provider config."""
        try:
            if not self.config_path.exists():
                return []
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                models = data.get('models', [])
            
            # Merge each model with its provider configuration
            enriched_models = []
            for model in models:
                provider_name = model.get('provider')
                if provider_name and provider_name in self.providers:
                    provider_config = self.providers[provider_name]
                    
                    # Create enriched model with provider data
                    enriched_model = model.copy()
                    enriched_model['base_url'] = provider_config['base_url']
                    enriched_model['schema'] = provider_config['schema']
                    
                    # Get API key from environment/settings
                    api_key = self._get_api_key_from_env(provider_config['api_key_env'])
                    if api_key:
                        enriched_model['api_key'] = api_key
                    
                    # Add extra headers if present
                    if provider_config.get('headers'):
                        enriched_model['headers'] = provider_config['headers']
                    
                    enriched_models.append(enriched_model)
                else:
                    # Model without provider config, keep as is
                    enriched_models.append(model)
            
            return enriched_models
        except Exception as e:
            print(f"Error loading models config: {e}")
            return []
    
    def _save_models(self):
        """Save models to JSON configuration file (without provider data)."""
        try:
            # Strip provider-specific data before saving
            clean_models = []
            for model in self.models:
                clean_model = {
                    'id': model['id'],
                    'name': model['name'],
                    'provider': model['provider'],
                    'model_id': model['model_id'],
                    'description': model.get('description', ''),
                    'enabled': model.get('enabled', True),
                    'parameters': model.get('parameters', {})
                }
                clean_models.append(clean_model)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump({'models': clean_models}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving models config: {e}")
            raise
    
    def list_models(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all models or only enabled ones."""
        if enabled_only:
            return [m for m in self.models if m.get('enabled', True)]
        return self.models
    
    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific model by ID with provider config merged."""
        for model in self.models:
            if model['id'] == model_id:
                return model
        return None
    
    def get_provider(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get provider configuration by name."""
        return self.providers.get(provider_name)
    
    def add_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new model configuration."""
        # Validate required fields
        required = ['id', 'name', 'provider', 'model_id']
        for field in required:
            if field not in model_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Check if ID already exists
        if self.get_model(model_data['id']):
            raise ValueError(f"Model with ID '{model_data['id']}' already exists")
        
        # Set defaults
        if 'enabled' not in model_data:
            model_data['enabled'] = True
        if 'parameters' not in model_data:
            model_data['parameters'] = {}
        
        self.models.append(model_data)
        self._save_models()
        self.reload()  # Reload to get provider data merged
        return self.get_model(model_data['id'])
    
    def update_model(self, model_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing model configuration."""
        for i, model in enumerate(self.models):
            if model['id'] == model_id:
                # Don't allow changing the ID
                if 'id' in updates and updates['id'] != model_id:
                    raise ValueError("Cannot change model ID")
                
                self.models[i].update(updates)
                self._save_models()
                self.reload()  # Reload to get provider data merged
                return self.get_model(model_id)
        
        raise ValueError(f"Model with ID '{model_id}' not found")
    
    def delete_model(self, model_id: str) -> bool:
        """Delete a model configuration."""
        for i, model in enumerate(self.models):
            if model['id'] == model_id:
                self.models.pop(i)
                self._save_models()
                return True
        return False
    
    def reload(self):
        """Reload models and providers from files."""
        self.providers = self._load_providers()
        self.models = self._load_models()

# Global instance
model_manager = ModelManager()
