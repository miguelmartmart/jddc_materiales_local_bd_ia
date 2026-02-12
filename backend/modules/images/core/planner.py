import logging
# DEVIA: backend/modules/images/core/DEVIA.md
import json
from typing import Dict, Any, List, Optional
from backend.core.utils.constants import LogPrefixes
from backend.modules.images.config.manager import ConfigurationManager
from backend.core.factory.ai_factory import AIFactory
from backend.core.abstract.ai import AIConfig
from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
import os
import yaml

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT_TEMPLATE = """
You are an Image Generation Planner. Your job is to produce a single STRICT JSON object (no extra text) to plan image generation in a configurable backend. The user request may be in Spanish; you must output POSITIVE and NEGATIVE prompts in ENGLISH.

GOAL:
Return prompts + parameters + workflow/model selection optimized for: (a) correctness, (b) consistency, (c) hardware constraints, (d) target use case.


CONTEXT (Runtime Constraints):
profile: {profile_name}
gpu_vram_gb: {gpu_vram_gb}
default_model_id: {default_model_id}
default_workflow_id: {default_workflow_id}
allowed_models: {allowed_models}
allowed_workflows: {allowed_workflows}
allowed_modes: ["ecommerce_packshot", "interior_lifestyle", "clean_3d_render", "concept_art", "general"]

DOMAIN RULES (HVAC):
{domain_rules}

LIMITS:
default_resolution: {default_resolution}
max_resolution: {max_resolution}
max_steps: {max_steps}
batch_max: {batch_max}

MODE CONSISTENCY RULES:
1. ecommerce_packshot:
   - MUST include: "product photo", "front view", "centered", "isolated on pure white background", "studio lighting", "soft shadow", "sharp focus".
   - MUST NOT include: "room", "interior", "living room", "furniture", "scene", "warm lighting".
   - NEGATIVES for 'air_conditioner': "lamp, vacuum, humidifier, purifier, iron, handle, stand, base".

2. interior_lifestyle:
   - MAY include: "interior", "room", "wall", "decor".
   - MUST NOT include: "isolated on pure white background".

COLOR LOGIC (CRITICAL):
- If user requests a specific color (e.g. "Yellow", "Green"):
  1. INJECT positive prompts for that color (e.g. "yellow casing").
  2. INJECT negative prompts for conflicting colors (e.g. "white casing, gray casing").
  3. DO NOT include "white casing" in positive prompt if the product is not white.
  4. IGNORE "white background" when determining product color.

OUTPUT FORMAT (STRICT JSON ONLY):
{{
    "intent_summary": "Short summary of user intent",
    "mode": "selected_mode",
    "model_id": "selected_model_id",
    "workflow_id": "selected_workflow_id",
    "positive_prompt": "English positive prompt",
    "negative_prompt": "English negative prompt (include anti-confusion terms)",
    "params": {{
        "width": 512,
        "height": 512,
        "steps": 20,
        "cfg": 7.0,
        "sampler": "euler",
        "scheduler": "normal",
        "seed_policy": "randomize_each",
        "batch_size": 1
    }},
    "num_candidates": 1,
    "confidence": 0.0
}}

IMPORTANT:
- If user intent is clearly a PRODUCT for sale, choose 'ecommerce_packshot'.
- Respect hardware limits (resolution/steps).
- JSON only. No markdown formatting.
- If 'yellow' is requested, ensure 'yellow casing' is in positive and 'white casing' is in negative.
"""

class ImagePlanner:
    def __init__(self, config_manager: ConfigurationManager):
        self.config = config_manager
        self.orchestrator = ModelFallbackOrchestrator()

        
    async def generate_plan(self, user_prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generates an execution plan based on user prompt and system constraints.
        """
        logger.info(f"[PLANNER] 🧠 Planning for request: '{user_prompt}'")
        
        # 1. Gather Context & Constraints
        # TODO: Get real profile name and VRAM from config
        profile_name = "local-6gb" 
        limits = self.config.get("limits", {})
        
        # Load Catalogs
        # For now we use the ones we just created. In real app, load from YAMLs via Manager.
        # Simulating basic catalog based on files we created
        models_catalog = ["sd15_base"]
        workflows_catalog = ["txt2img_sd15_base"]
        
        # 2. Load HVAC Config for Context
        # TODO: Move to ConfigurationManager or cache this
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        hvac_config_path = os.path.join(base_dir, "backend/modules/images/config/domains/hvac.yaml")
        domain_rules_text = ""
        if os.path.exists(hvac_config_path):
            with open(hvac_config_path, 'r', encoding='utf-8') as f:
                domain_rules_text = f.read()

        # 3. Build System Prompt
        system_prompt = PLANNER_SYSTEM_PROMPT_TEMPLATE.format(
            profile_name=profile_name,
            gpu_vram_gb=6, # Hardcoded for this profile
            default_model_id="sd15_base",
            default_workflow_id="txt2img_sd15_base",
            allowed_models=models_catalog,
            allowed_workflows=workflows_catalog,
            default_resolution=512,
            max_resolution=limits.get("max_width", 1024),
            max_steps=limits.get("max_steps", 50),
            batch_max=limits.get("max_batch_size", 1),
            domain_rules=domain_rules_text
        )
        
        # 4. Call LLM via Orchestrator
        try:
            logger.info("[PLANNER] 🤖 Invoking ModelFallbackOrchestrator for Plan Generation...")
            response, used_model = await self.orchestrator.execute_with_fallback(
                system_prompt=system_prompt,
                user_message=user_prompt,
                preferred_model_id=None # Let it pick best available (e.g. gemma-3-4b)
            )

            if not response:
                raise Exception("LLM Orchestrator returned no response")

            # Parse JSON
            # Clean response (remove markdown ```json ... ```)
            clean_json = response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            
            plan = json.loads(clean_json)
            logger.info(f"[PLANNER] 📝 Generated Plan (LLM - {used_model}): {json.dumps(plan, indent=2)}")
            return plan

        except Exception as e:
            logger.error(f"[PLANNER] ❌ LLM Planning failed: {e}. Falling back to Rule-Based.")
            # FALLBACK TO RULE BASED (The old code)
            # For brevity/safety, we can keep the old code here in the except block
            # or strictly fail. Given user requirement "use robust AI", we should rely on LLM.
            # But let's keep a minimal safety net return
            return {
                "error": str(e),
                "fallback": True,
                "positive_prompt": user_prompt + ", high quality",
                "negative_prompt": "low quality",
                "model_id": "sd15_base",
                "workflow_id": "txt2img_sd15_base",
                "params": {"width":512, "height":512}
            }

        except Exception as e:
            logger.error(f"[PLANNER] ❌ Planning failed: {e}")
            raise e

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        # Implementation to call actual LLM 
        pass
