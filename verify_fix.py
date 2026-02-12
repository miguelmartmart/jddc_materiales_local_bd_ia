import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

try:
    from backend.core.config.model_manager import ModelManager
except ImportError:
    # Try adding desktop-codelab if running from root but code is there?
    # Based on file paths, backend is in root/backend AND root/desktop-codelab/backend?
    # User edited root/backend/.../model_manager.py
    pass

from backend.core.config.model_manager import ModelManager

def test():
    try:
        mgr = ModelManager()
        models = mgr.list_models(enabled_only=False)
        print(f"Models type: {type(models)}")
        if models is None:
            print("FAIL: list_models returned None")
            sys.exit(1)
        print(f"Models count: {len(models)}")
        print("SUCCESS: list_models returned a list")
    except Exception as e:
        print(f"FAIL: Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test()
