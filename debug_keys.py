from backend.core.utils.env_manager import env_manager
import os

print("Checking .env file...")
print(f"Path: {env_manager.env_path}")
print(f"Exists: {env_manager.env_path.exists()}")

keys = [
    "GROQ_API_KEY", "FIREWORKS_API_KEY", "OPENROUTER_API_KEY", 
    "GEMINI_API_KEY", "GOOGLE_AI_STUDIO_API_KEY", "HUGGINGFACE_API_KEY"
]

vals = env_manager.get_keys(keys)
for k in keys:
    val = vals.get(k)
    status = "MISSING"
    if val:
        status = f"PRESENT (len={len(val)})"
        if len(val) < 10: status += " [WARNING: TOO SHORT]"
    print(f"{k}: {status}")
