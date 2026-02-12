from typing import Dict, Any, List, Optional
# DEVIA: backend/modules/images/DEVIA.md
from .config.manager import ConfigurationManager
from .core.job_manager import JobManager
from .core.storage import LocalStorageManager
from .providers.comfyui import ComfyUIProvider
from .core.planner import ImagePlanner
from .core.verifier import ImageVerifier
from .schemas import GenerateRequest, JobCreatedResponse, ImageJobType
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
import os
import logging

logger = logging.getLogger(__name__)

class ImageService:
    """
    Main Service for Image Module.
    Initializes components and exposes high-level methods.
    """
    
    def __init__(self):
        self.config = ConfigurationManager()
        self.storage = LocalStorageManager()
        
        # Initialize Provider (Factory pattern logic here ideally)
        provider_config = self.config.get_provider_config()
        self.provider = ComfyUIProvider(provider_config)
        
        # Initialize Agents
        self.planner = ImagePlanner(self.config)
        self.verifier = ImageVerifier(self.config)
        
        # Initialize Job Manager with Agents
        self.job_manager = JobManager(self.config, self.provider, planner=self.planner, verifier=self.verifier)
        
    async def _execute_real_vision_analysis(self, image_path: str) -> str:
        """
        Executes real vision analysis using an LLM Provider (Fallback if ComfyUI is not ready).
        """
        try:
            # 1. Get a Vision-Capable Provider (e.g., OpenAI/Gemini)
            # For now, hardcode a reliable vision model config or load from settings
            # Using 'gpt-4o' or 'gemini-1.5-flash' as they are cost effective and fast
            
            provider = AIFactory.get_provider("openai_compatible")
            
            # Configure it (Should load from environment/config)
            # Assuming ENV vars or existing config for now. 
            # In a robust system, we pick this from 'models' module.
            from backend.core.config.model_manager import model_manager
            
            # Try to find a vision model in available models
            model_id = "gpt-4o-mini" # Default fallback
            model_config = model_manager.get_model(model_id)
            
            if not model_config:
                 # Fallback to whatever is available or raise
                 models = model_manager.get_models()
                 if models: model_config = models[0]
            
            if model_config:
                ai_config = AIConfig(
                    api_key=model_config.get('api_key', 'invalid'),
                    model=model_config.get('model_id', 'gpt-4o-mini'),
                    base_url=model_config.get('base_url'),
                    headers=model_config.get('headers')
                )
                provider.configure(ai_config)
                
                # 2. Read Image
                import base64
                abs_path = self.storage.get_absolute_path(image_path)
                with open(abs_path, "rb") as img_file:
                    b64_image = base64.b64encode(img_file.read()).decode('utf-8')
                
                # 3. Generate Description
                prompt = "Analiza esta imagen detalladamente. Describe qué hay en ella, textos visibles, objetos y contexto. Sé conciso."
                
                # --- PRIORITY: LOCAL VISION SERVER (User Request) ---
                # check http://172.21.32.1:1234
                try:
                    local_provider = AIFactory.get_provider("openai_compatible")
                    local_config = AIConfig(
                        api_key="lm-studio", # Dummy key
                        model="qwen/qwen3-vl-8b", # Exact model requested
                        base_url="http://172.21.32.1:1234/v1" # LM Studio standard endpoint
                    )
                    local_provider.configure(local_config)
                    
                    logger.info("[VISION] 🏠 Intentando análisis con Servidor Local (Qwen3-VL)...")
                    response = await local_provider.generate_text(
                        system_instruction="Eres un asistente de visión útil.",
                        prompt=prompt,
                        images=[b64_image]
                    )
                    logger.info("[VISION] ✅ Servidor Local respondió exitosamente.")
                    return response
                except Exception as local_e:
                    logger.warning(f"[VISION] ⚠️ Servidor Local falló o no disponible: {local_e}. Intentando Cloud Fallback...")
                    # Fallthrough to Cloud Provider (GPT-4o) defined above
                
                # --- CLOUD FALLBACK ---
                response = await provider.generate_text(
                    system_instruction="Eres un experto analista de visión por computador.",
                    prompt=prompt,
                    images=[b64_image]
                )
                return response
                
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"Real Vision Analysis Rate Limited: {e}")
                return "⚠️ El sistema de visión (OpenAI) ha excedido su cuota de uso (Error 429). Para analizar imágenes localmente con ComfyUI, necesitas instalar nodos de visión (VLM). Por ahora, no puedo 'ver' la imagen."
            
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Real Vision Analysis Failed: {e}\n{error_details}")
            return f"Error en análisis visual: {str(e)}"

        return "No se pudo configurar un modelo de visión."

    async def generate_image(self, request: GenerateRequest, user_id: str = "system") -> JobCreatedResponse:
        """
        Starts a generation job using Agentic Planner.
        """
        logger.info(f"[SERVICE] 🤖 Invoke Planner for: '{request.prompt[:50]}...'")
        
        # 1. Planner Step: Generate Execution Plan
        # This translates user intent -> specific workflow/params/prompts
        plan = await self.planner.generate_plan(request.prompt)
        
        # 2. Execution Step: Submit Plan to Job Manager
        # The 'plan' dictionary matches exactly what ComfyUIProvider needs
        job_id = await self.job_manager.create_job(
            job_type=ImageJobType.TXT2IMG,
            params=plan,
            user_id=user_id
        )
        
        # Calculate ETA (Mock logic)
        return JobCreatedResponse(
            job_id=job_id,
            status="PENDING",
            eta_seconds=10.0
        )

    async def get_job(self, job_id: str) -> Optional[Dict]:
        return await self.job_manager.get_job(job_id)

    async def describe_image(self, user_id: str, image_path: str = None, image_url: str = None) -> Dict[str, Any]:
        """
        Analyzes an image and returns a description.
        """
        # Create a job for tracking (optional, but good for consistency)
        params = {
            "image_path": image_path,
            "image_url": image_url,
            "mode": "describe"
        }
        
        # For simplicity in this iteration, we might call provider directly or use job manager
        # Using Job manager for consistency
        job_id = await self.job_manager.create_job(
            job_type=ImageJobType.DESCRIBE,
            params=params,
            user_id=user_id
        )
        
        # Override the job execution to use REAL analysis if provider is ComfyUI (which is currently mocked)
        # and we want real results.
        # Patching the job to run immediately here for the user request "analyize for real"
        
        # Run Real Analysis
        description = await self._execute_real_vision_analysis(image_path)
        
        # Update Job manually (since JobManager runs in background, we might race it, but this is a synchronous wait anyway)
        # Ideally JobManager calls _execute_real_vision_analysis, but for now we hook it here for speed
        
        return {
            "description": description,
            "job_id": job_id
        }

