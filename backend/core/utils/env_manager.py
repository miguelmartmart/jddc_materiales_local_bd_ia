import os
from pathlib import Path
from typing import Dict, List

class EnvManager:
    def __init__(self, env_path: str = ".env"):
        self.env_path = Path(env_path)
        # Try to resolve relative path from backend root if needed
        if not self.env_path.exists():
             # fallback assuming we are running from project root
             self.env_path = Path(os.getcwd()) / ".env"

    def get_keys(self, target_keys: List[str]) -> Dict[str, str]:
        """Get current values for specific keys (masked)."""
        if not self.env_path.exists():
            return {}
        
        current_vals = {}
        try:
            with open(self.env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        if key in target_keys:
                            val = val.strip()
                            current_vals[key] = val
        except Exception as e:
            print(f"Error reading .env: {e}")
            
        return current_vals

    def update_keys(self, updates: Dict[str, str]):
        """Update or add keys to .env file."""
        if not self.env_path.exists():
            # Create if valid path
            self.env_path.touch()

        lines = []
        try:
            with open(self.env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        new_lines = []
        processed_keys = set()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue
            
            if "=" in stripped:
                key, _ = stripped.split("=", 1)
                key = key.strip()
                if key in updates:
                    # Replace this line
                    val = updates[key]
                    new_lines.append(f"{key}={val}\n")
                    processed_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Append new keys
        for key, val in updates.items():
            if key not in processed_keys:
                new_lines.append(f"\n{key}={val}\n")

        with open(self.env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

env_manager = EnvManager()
