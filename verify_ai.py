import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.core.utils.constants import AIConstants

async def test_ai_integration():
    print("Testing AI Integration...")
    
    try:
        provider = AIFactory.get_provider(AIConstants.PROVIDER_GEMINI.value)
        print(f"Provider loaded: {type(provider).__name__}")
        
        # Mock config
        config = AIConfig(api_key="TEST_KEY", model="gemini-1.5-flash")
        provider.configure(config)
        print("Provider configured successfully.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_integration())
