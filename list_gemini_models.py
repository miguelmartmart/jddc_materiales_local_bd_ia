import sys
import os
import traceback

try:
    import json
    import google.generativeai as genai
    from dotenv import load_dotenv
    
    load_dotenv()
    with open('backend/core/config/models/google.json', 'r') as f:
        config = json.load(f)
        # Assuming the first model often has the key or it's in a common place
        # In this user's config structure, api_key might be in the first item or omitted (using env)
        # Let's check environment variable first
        api_key = os.environ.get("GOOGLE_API_KEY")
        
        if not api_key:
             # Try to find it in the config file items
             for model in config.get('models', []):
                 if model.get('api_key'):
                     api_key = model['api_key']
                     break
        
    if not api_key:
        print("❌ ERROR: No GOOGLE_API_KEY found in env or google.json")
        exit(1)

    print(f"🔑 Using API Key: {api_key[:5]}...{api_key[-3:]}")
    genai.configure(api_key=api_key)

    print("\n📡 Fetching available models...")
    models = list(genai.list_models())
    
    print("\n✅ Available Gemini Models:")
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            print(f" - {m.name} (Display: {m.displayName})")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"\n❌ EXCEPTION: {e}")
