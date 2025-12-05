import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.core.config.model_manager import model_manager

try:
    print("Loading models...")
    models = model_manager.list_models()
    print(f"Loaded {len(models)} models:")
    for m in models:
        print(f"- {m['name']} ({m['provider']}) - Key: {'Yes' if m.get('api_key') else 'No'}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
