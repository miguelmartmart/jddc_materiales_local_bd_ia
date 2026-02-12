import os
import logging
from typing import Dict, Any, Optional
from .loaders import load_yaml, load_json, merge_configs

logger = logging.getLogger(__name__)

class ConfigurationManager:
    """
    Manages loading and merging of configurations for Image Services.
    Priority: Defaults < Base Config < Profile Config < Preset < Runtime Overrides
    """
    
    def __init__(self, root_path: str = None):
        if not root_path:
            # Default to project_root/config/images
            # Assuming this file is in backend/modules/images/config/manager.py
            # ../../../.. -> backend/modules/images/config -> backend/modules/images -> backend/modules -> backend -> root (interjddcia)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.root_path = os.path.abspath(os.path.join(current_dir, "../../../../config/images"))
        else:
            self.root_path = root_path
            
        self.config = {}
        self.current_profile = os.getenv("DEVIA_IMAGES_PROFILE", "local-6gb")
        self.load_configuration()
        
    def load_configuration(self):
        """Loads and merges all configuration layers."""
        logger.info(f"[IMAGES] Loading configuration for profile: {self.current_profile}")
        
        # 1. Base Config
        base_path = os.path.join(self.root_path, "base.yaml")
        base_config = load_yaml(base_path)
        
        # 2. Profile Config
        profile_path = os.path.join(self.root_path, "profiles", f"{self.current_profile}.yaml")
        profile_config = load_yaml(profile_path)
        
        # Merge
        self.config = merge_configs(base_config, profile_config)
        
        if not self.config:
            logger.warning("[IMAGES] Configuration is empty! Check paths.")
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation (e.g., 'limits.max_width')."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_provider_config(self, provider_name: str = None) -> Dict[str, Any]:
        """Get config for a specific provider or the default one."""
        if not provider_name:
            provider_name = self.get("providers.default", "comfyui_local")
            
        return self.get(f"providers.{provider_name}", {})
