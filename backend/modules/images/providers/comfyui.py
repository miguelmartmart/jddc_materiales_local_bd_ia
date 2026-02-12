import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from .base import BaseImageProvider
from ..schemas import GenerateRequest, JobStatus

logger = logging.getLogger(__name__)

class ComfyUIProvider(BaseImageProvider):
    """
    Provider implementation for ComfyUI.
    Connects to local/remote ComfyUI API.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("url", "http://127.0.0.1:8188")
        
    async def validate_connection(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/system_stats", timeout=2) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.warning(f"ComfyUI offline: {e}")
            return False

    async def submit_job(self, job_id: str, request: Dict) -> str:
        """
        Submits job to ComfyUI based on a Planner execution plan.
        Request is expected to be the JSON Plan from ImagePlanner.
        """
        import json
        import os
        import yaml
        
        logger.info(f"[COMFYUI] 🚀 Executing Agentic Plan for Job {job_id}")
        
        # 1. Extract details from Plan
        workflow_id = request.get("workflow_id", "txt2img_sd15_base")
        positive_prompt = request.get("positive_prompt", "")
        negative_prompt = request.get("negative_prompt", "")
        params = request.get("params", {})
        
        # 2. Load Workflows Catalog
        # TODO: Use ConfigurationManager properly
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        workflows_config_path = os.path.join(base_dir, "config/images/workflows.yaml")
        
        if not os.path.exists(workflows_config_path):
             raise FileNotFoundError(f"Workflows config not found: {workflows_config_path}")
             
        with open(workflows_config_path, 'r') as f:
            workflows_catalog = yaml.safe_load(f) or {}

        # Load Models Catalog to resolve filename
        models_config_path = os.path.join(base_dir, "config/images/models.yaml")
        models_catalog = {}
        if os.path.exists(models_config_path):
            with open(models_config_path, 'r') as f:
                models_catalog = yaml.safe_load(f) or {}
            
        workflow_config = workflows_catalog.get("workflows", {}).get(workflow_id)
        if not workflow_config:
            logger.error(f"[COMFYUI] Workflow ID '{workflow_id}' not defined in catalog. Fallback to base.")
            workflow_config = workflows_catalog.get("workflows", {}).get("txt2img_sd15_base")
            if not workflow_config:
                 raise ValueError("Critical: Base workflow not found.")

        # 3. Load Workflow Template JSON
        template_filename = workflow_config["file"]
        manifest = workflow_config["manifest"]
        
        template_path = os.path.join(base_dir, "config/images/workflows", template_filename)
        if not os.path.exists(template_path):
             raise FileNotFoundError(f"Workflow template file not found: {template_path}")
             
        with open(template_path, 'r') as f:
            workflow = json.load(f)

        # 4. Bind Plan to Workflow Nodes (Using Manifest)
        logger.info(f"[COMFYUI] Binding plan to workflow '{workflow_id}'...")
        
        # Helper to safely set input
        def set_node_input(node_key, input_key, value):
            node_id = manifest.get(node_key)
            if node_id and node_id in workflow:
                if "inputs" not in workflow[node_id]: workflow[node_id]["inputs"] = {}
                workflow[node_id]["inputs"][input_key] = value
                return True
            logger.warning(f"[COMFYUI] ⚠️ Manifest key '{node_key}' (Node {node_id}) not found in workflow")
            return False

        # Bind Prompts
        set_node_input("positive_prompt", "text", positive_prompt)
        set_node_input("negative_prompt", "text", negative_prompt)
        
        # Bind Params
        set_node_input("seed", "seed", params.get("seed", 12345))
        set_node_input("steps", "steps", params.get("steps", 20))
        set_node_input("cfg", "cfg", params.get("cfg", 7.0))
        set_node_input("sampler_name", "sampler_name", params.get("sampler", "euler"))
        set_node_input("scheduler", "scheduler", params.get("scheduler", "normal"))
        set_node_input("width", "width", params.get("width", 512))
        set_node_input("height", "height", params.get("height", 512))
        
        # Resolve Checkpoint Filename
        req_model_id = request.get("model_id", "sd15_base")
        ckpt_filename = "v1-5-pruned-emaonly.safetensors" # Default fallback
        
        if models_catalog:
            model_info = models_catalog.get("models", {}).get(req_model_id)
            if model_info:
                ckpt_filename = model_info.get("filename", ckpt_filename)
            else:
                logger.warning(f"[COMFYUI] Model ID '{req_model_id}' not found in catalog. Using default: {ckpt_filename}")
        
        set_node_input("checkpoint", "ckpt_name", ckpt_filename)

        # 5. Log Execution Details
        logger.info("="*40)
        logger.info(f"✅ PLANNER PROMPT: {positive_prompt}")
        logger.info(f"⛔ NEGATIVE PROMPT: {negative_prompt}")
        logger.info(f"⚙️ PARAMS: {params}")
        logger.info("="*40)

        # 6. Submit
        payload = {"prompt": workflow, "client_id": "devia_backend"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/prompt", json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"ComfyUI Error {resp.status}: {text}")
                
                response_data = await resp.json()
                provider_job_id = response_data.get("prompt_id")
                logger.info(f"[COMFYUI] Job submitted successfully. Prompt ID: {provider_job_id}")
                return provider_job_id


    async def get_job_status(self, provider_job_id: str) -> JobStatus:
        """
        Query history from ComfyUI to check if job is done.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/history/{provider_job_id}") as resp:
                    if resp.status == 200:
                        history = await resp.json()
                        if history and provider_job_id in history:
                             # Job found in history = Completed
                             logger.info(f"[COMFYUI] Job {provider_job_id} completed.")
                             
                             # Extract outputs from history if available
                             outputs = history[provider_job_id].get("outputs", {})
                             files = []
                             for node_id, node_output in outputs.items():
                                 if "images" in node_output:
                                     for img in node_output["images"]:
                                         filename = img.get("filename")
                                         if filename:
                                             files.append(filename)
                             
                             if files:
                                 return JobStatus.COMPLETED, files
                                 
                             return JobStatus.COMPLETED, []
                    
                    # If not in history, check queue
                    async with session.get(f"{self.base_url}/queue") as q_resp:
                        if q_resp.status == 200:
                            # queue = await q_resp.json()
                            # Check pending or running
                            # Simplify: if not in history, assume RUNNING for now as queue structure is complex
                            return JobStatus.RUNNING, []

            return JobStatus.RUNNING, [] # Default to running if no error
        except Exception as e:
             logger.error(f"Error checking ComfyUI status: {e}")
             return JobStatus.RUNNING, []

    async def cancel_job(self, provider_job_id: str) -> bool:
        # TODO: Send cancel request
        return True

    async def describe_image(self, request: Dict) -> str:
        """
        Submits an image description job.
        For now, this mocks the response since we don't have a VLM workflow yet.
        """
        job_id = request.get("job_id")
        logger.info(f"[COMFYUI] Analyzing image job {job_id}")
        
        # In a real implementation:
        # 1. Provide image to ComfyUI (upload or path)
        # 2. Run workflow with VLM (JoyTag, WD14, or MLLM)
        # 3. Retrieve text output
        
        await asyncio.sleep(2) # Sim processing
        
        return "Descripción simulada: La imagen muestra una captura de pantalla de una interfaz de chat con código SQL visible."
