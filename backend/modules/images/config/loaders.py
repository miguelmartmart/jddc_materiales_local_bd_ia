import yaml
import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def load_yaml(file_path: str) -> Dict[str, Any]:
    """
    Load a YAML file from the given path.
    Returns an empty dict if file doesn't exist or error occurs.
    """
    if not os.path.exists(file_path):
        logger.warning(f"YAML file not found: {file_path}")
        return {}
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error loading YAML {file_path}: {e}")
        return {}

def load_json(file_path: str) -> Dict[str, Any]:
    """
    Load a JSON file from the given path.
    Returns an empty dict if file doesn't exist or error occurs.
    """
    if not os.path.exists(file_path):
        logger.warning(f"JSON file not found: {file_path}")
        return {}
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception as e:
        logger.error(f"Error loading JSON {file_path}: {e}")
        return {}

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two configuration dictionaries.
    Override takes precedence over base.
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
            
    return result
