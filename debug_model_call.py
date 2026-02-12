import asyncio
import os
from backend.core.config.model_manager import model_manager
from backend.core.domain.ai_models import AIRequest

async def test_model():
    print("Reloading models...")
    model_manager.reload()
    
    model_id = "llama-3-3-70b" # Groq Llama 3.3 70B
    print(f"Testing model: {model_id}")
    
    try:
        model = model_manager.get_model(model_id)
        if not model:
            print(f"ERROR: Model {model_id} not found in manager!")
            return

        print(f"Model found: {model.name} (Provider: {model.provider})")
        
        req = AIRequest(
            model_id=model_id,
            prompt="Hello, are you working?",
            temperature=0.7
        )
        
        print("Sending request...")
        response = await model_manager.generate_response(req)
        print(f"Response: {response.text}")
        print("SUCCESS")
        
    except Exception as e:
        print(f"FAILURE: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_model())
