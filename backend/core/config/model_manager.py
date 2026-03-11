import json
import os
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
from backend.core.config.settings import settings

class ModelManager:
    """Manages AI model configurations, scoring, and quota logic."""
    
    TIER_PRIORITY = {
        "elite": 4,
        "high": 3,
        "medium": 2,
        "low": 1
    }

    # Bonus points added to score for sorting purposes
    # This allows higher tier models to be preferred even if they have slightly lower reliability scores
    TIER_BONUS = {
        "elite": 50,
        "high": 25,
        "medium": 0,
        "low": 0
    }

    def __init__(self):
        self.config_path = Path(__file__).parent / "ai_models_config.json"
        self.providers_path = Path(__file__).parent / "ai_providers_config.json"
        self.providers = self._load_providers()
        self.models = self._load_models()
        self._log_key_status()

    def _load_providers(self) -> Dict[str, Dict[str, Any]]:
        try:
            if not self.providers_path.exists(): return {}
            with open(self.providers_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('providers', {})
        except Exception as e:
            print(f"Error loading providers: {e}")
            return {}

    def _get_api_key_from_env(self, env_var_name: str) -> Optional[str]:
        # Legacy/Fallback overrides
        if env_var_name == "GEMINI_API_KEY":
            val = getattr(settings, "GEMINI_API_KEY", None)
            if not val:
                 val = getattr(settings, "GOOGLE_AI_STUDIO_API_KEY", None)
            return val
            
        return getattr(settings, env_var_name, None) if env_var_name else None

    def _log_key_status(self):
        """Log status of expected API Keys to console on startup."""
        try:
            print("\n--- [API Key Status Check] ---")
            for prov_name, conf in self.providers.items():
                env_var = conf.get('api_key_env')
                if env_var:
                    val = getattr(settings, env_var, None)
                    status = "LOADED" if val else "MISSING/EMPTY"
                    masked = f"({val[:4]}...)" if val and len(val) > 4 else ""
                    print(f"  {env_var}: {status} {masked}")
            print("------------------------------\n")
        except Exception as e:
            print(f"[model_manager] Key status check error: {e}")

    def _load_models(self) -> List[Dict[str, Any]]:
        models_dir = Path(__file__).parent / "models"
        all_models = []

        # Load from single main file if it exists (backward compatibility)
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_models.extend(data.get('models', []))
            except Exception as e:
                print(f"Error loading main config: {e}")

        # Load from broken down files in models/ directory
        if models_dir.exists():
            for config_file in models_dir.glob("*.json"):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        file_models = data.get('models', [])
                        for m in file_models:
                            m['_source_file'] = str(config_file)
                        all_models.extend(file_models)
                except Exception as e:
                    print(f"Error loading {config_file}: {e}")

        try:
            # Enrich and Initialize
            enriched = []
            now = time.time()
            # Deduplicate by ID, preferring later loaded ones (or file ones over main)
            seen_ids = set()
            
            # Reverse iterate to keep last occurrence if we want overrides, 
            # but standard dict logic usually means last one wins if we build a dict.
            # Let's simple check duplicates.
            unique_models = {}
            for m in all_models:
                unique_models[m['id']] = m

            for m in unique_models.values():
                # Ensure new schema fields exist
                m.setdefault('score', 100)
                m.setdefault('tier', 'medium')
                m.setdefault('quota', {"blocked": False, "blocked_at": None, "reset_at": None, "avg_reset_time": 60})
                m.setdefault('stats', {"success": 0, "failure": 0})
                m.setdefault('family', 'other')
                m.setdefault('usage', ['chat']) # Default usage

                # Track source for saving
                if '_source_file' not in m:
                     # Default fallback if missing (e.g. from main config)
                     pass 

                # Check Quota Reset (Auto-unblock)
                quota = m['quota']
                if quota['blocked'] and quota['reset_at'] and now > quota['reset_at']:
                    quota['blocked'] = False
                    quota['reset_at'] = None
                    m['score'] = min(m['score'] + 10, 100) # Reset recovery boost

                # Merge Provider Config
                prov_name = m.get('provider')
                if prov_name and prov_name in self.providers:
                    p_conf = self.providers[prov_name]
                    # Only set base_url if not already set by model specific config
                    if not m.get('base_url'):
                         m['base_url'] = p_conf.get('base_url')
                    
                    # Prefer manual key if set in UI, else env
                    if not m.get('api_key'): 
                         m['api_key'] = self._get_api_key_from_env(p_conf.get('api_key_env'))
                
                enriched.append(m)
            return enriched
        except Exception as e:
            print(f"Error processing models: {e}")
            return []

    def _save_models(self):
        try:
            # We need to group models by their source file to save correctly
            # If a model is new (no source), save to 'models/custom.json'
            
            models_by_file = {}
            default_file = self.config_path.parent / "models" / "custom.json"
            
            if not default_file.parent.exists():
                default_file.parent.mkdir(parents=True, exist_ok=True)

            for m in self.models:
                clean = m.copy()
                # Remove sensitive/runtime keys
                prov = self.providers.get(m['provider'], {})
                env_key = self._get_api_key_from_env(prov.get('api_key_env'))
                if m.get('api_key') == env_key:
                    clean.pop('api_key', None)
                
                # Get source file
                source = clean.pop('_source_file', str(default_file))
                
                if source not in models_by_file:
                    models_by_file[source] = []
                models_by_file[source].append(clean)

            # Write each file
            for file_path, models_list in models_by_file.items():
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump({'models': models_list}, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"Error saving to {file_path}: {e}")

        except Exception as e:
            print(f"Error saving models: {e}")

    def list_models(self, enabled_only: bool = False, capability: str = None) -> List[Dict[str, Any]]:
        """Smart list: Sorted by Availability -> Tier -> Score."""
        candidates = self.models
        if enabled_only:
            candidates = [m for m in candidates if m.get('enabled', True)]
        
        if capability:
             candidates = [m for m in candidates if capability in m.get('capabilities', [])]

        # Refresh blocked status check
        now = time.time()
        for m in candidates:
            q = m['quota']
            if q['blocked'] and q['reset_at'] and now > q['reset_at']:
                 q['blocked'] = False
        
        # Sort Logic
        def sort_key(m):
            # 1. Unblocked first (False < True)
            is_blocked = m['quota']['blocked']
            
            # 2. Score with Tier Bonus
            # We add a bonus to the score based on tier to prioritize better models
            # unless they are failing significantly.
            base_score = m.get('score', 0)
            tier = m.get('tier', 'medium')
            bonus = self.TIER_BONUS.get(tier, 0)
            final_score = base_score + bonus

            # 3. Tier Value (Secondary tie-breaker)
            tier_val = self.TIER_PRIORITY.get(tier, 0)
            
            return (not is_blocked, final_score, tier_val)

        return sorted(candidates, key=sort_key, reverse=True)

    def sync_discovered_models(self, discovered_models: List[Dict[str, Any]]) -> Dict[str, int]:
        """Merge discovered models into current configuration and save."""
        added = 0
        updated = 0
        
        # Index existing models by ID for fast lookup
        existing_map = {m['id']: m for m in self.models}
        
        for d_model in discovered_models:
            mid = d_model['id']
            if mid in existing_map:
                # Update existing
                existing = existing_map[mid]
                # Only update static metadata, don't overwrite user settings (enabled, score, etc)
                existing['name'] = d_model.get('name', existing['name'])
                # Merge capabilities safely
                new_caps = set(existing.get('capabilities', []))
                # Add basic text capability if likely
                new_caps.add('text')
                if 'vision' in mid.lower() or 'claude-3' in mid.lower() or 'gemini' in mid.lower():
                    new_caps.add('vision')
                existing['capabilities'] = list(new_caps)
                
                # Update underlying model_id if changed/corrected
                if d_model.get('model_id'):
                    existing['model_id'] = d_model['model_id']
                
                updated += 1
            else:
                # Add new model
                new_model = d_model.copy()
                # Defaults
                new_model.setdefault('enabled', True) # Auto-enable discovered models? Maybe safe.
                new_model.setdefault('score', 80)
                new_model.setdefault('tier', 'medium')
                new_model.setdefault('capabilities', ['text'])
                new_model.setdefault('quota', {"blocked": False, "reset_at": None, "avg_reset_time": 60})
                new_model.setdefault('stats', {"success": 0, "failure": 0})
                
                # Infer provider capabilities
                caps = set(['text'])
                if 'vision' in new_model['id'] or 'gemini' in new_model['id'] or 'claude-3' in new_model['id']:
                    caps.add('vision')
                new_model['capabilities'] = list(caps)
                
                # Assign to appropriate source file based on provider
                prov = new_model.get('provider', 'other')
                if prov == 'gemini':
                    new_model['_source_file'] = str(Path(__file__).parent / "models" / "google.json")
                elif prov == 'openai' or prov == 'groq' or prov == 'anthropic':
                    new_model['_source_file'] = str(Path(__file__).parent / "models" / "open_models.json")
                else:
                    new_model['_source_file'] = str(Path(__file__).parent / "models" / "custom.json")

                self.models.append(new_model)
                added += 1
        
        self._save_models()
        return {"added": added, "updated": updated}

    def reload(self):
        """Reload configuration from disk."""
        self.providers = self._load_providers()
        self.models = self._load_models()

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        for m in self.models:
            if m['id'] == model_id: return m
        return None

    def report_result(self, model_id: str, success: bool, error_type: str = None, error_msg: str = ""):
        """Update score and quota tracking based on usage result."""
        model = self.get_model(model_id)
        if not model: return

        if success:
            model['stats']['success'] += 1
            # Boost score, max 100
            model['score'] = min(100, model['score'] + 2)
            # If was blocked, clear it
            if model['quota']['blocked']:
                model['quota']['blocked'] = False
                model['quota']['reset_at'] = None
        else:
            model['stats']['failure'] += 1
            
            # Smart Error Handling
            # 1. Quota/Payment Errors (402, 429, insufficient)
            if error_type in ['429', '402'] or 'insufficient_quota' in error_msg.lower() or 'credit' in error_msg.lower():
                model['score'] = max(0, model['score'] - 15)
                model['quota']['blocked'] = True
                # Smart reset time: double average or default 60s
                wait_time = model['quota'].get('avg_reset_time', 60)
                model['quota']['reset_at'] = time.time() + wait_time
                # Increase next wait time for backoff
                model['quota']['avg_reset_time'] = min(3600, wait_time * 2)
                
            # 2. Permanent/Configuration Errors (404, 410, Not Found, Gone)
            elif error_type in ['404', '410'] or 'model_not_found' in error_msg.lower() or 'decommissioned' in error_msg.lower() or 'gone' in error_msg.lower():
                 print(f"Disabling model {model_id} due to permanent error: {error_msg}")
                 model['enabled'] = False
                 model['score'] = 0
            
            # 3. Auth Errors (401) - Penalty but don't disable (user might fix key)
            elif error_type == '401' or 'api key' in error_msg.lower():
                 model['score'] = max(0, model['score'] - 10)
                 
            # 4. Other errors
            else:
                model['score'] = max(0, model['score'] - 2)
        
        self._save_models()

    def get_best_model(self, capability: str = None, preferred_provider: str = None) -> Optional[Dict[str, Any]]:
        """Finds the best available model, optionally filtering by provider."""
        candidates = self.list_models(enabled_only=True, capability=capability)
        
        if not candidates:
            return None
            
        if preferred_provider:
            # Try to find one from the preferred provider
            for m in candidates:
                if m.get('provider') == preferred_provider:
                    return m
        
        # Fallback to the absolute best
        return candidates[0]

    def add_model(self, data: Dict[str, Any]):
        if self.get_model(data['id']):
            raise ValueError("ID exists")
        
        # Set defaults
        defaults = {
            "score": 100,
            "quota": {"blocked": False, "avg_reset_time": 60},
            "stats": {"success": 0, "failure": 0},
            "enabled": True,
            "tier": "medium",
            "capabilities": ["text"]
        }
        for k, v in defaults.items():
            data.setdefault(k, v)
            
        self.models.append(data)
        self._save_models()
        return data

    def update_model(self, model_id: str, updates: Dict[str, Any]):
        model = self.get_model(model_id)
        if not model: raise ValueError("Not found")
        
        # Prevent ID change
        updates.pop('id', None)
        model.update(updates)
        self._save_models()
        return model

    def delete_model(self, model_id: str):
         self.models = [m for m in self.models if m['id'] != model_id]
         self._save_models()

    def reset_score(self, model_id: str):
        model = self.get_model(model_id)
        if model:
            model['score'] = 100
            model['quota']['blocked'] = False
            model['quota']['avg_reset_time'] = 60
            self._save_models()

model_manager = ModelManager()
