# DEVIA MODULE CONTEXT: IMAGES
# This file contains the AI Context for the Image Generation Module.
# When modifying this module, load this context to understand architecture and intent.

```json
{
  "module": "backend.modules.images",
  "description": "Agentic Image Generation Service specialized in HVAC and Ecommerce domains.",
  "architecture": {
    "pattern": "Agentic Loop (Plan -> Execute -> Verify -> Repair)",
    "entry_point": "ImageService.generate_image",
    "components": {
      "ImageService": "Orchestrator. Initializes Planner, Verifier, and JobManager. exposes API.",
      "JobManager": "Async execution engine. Manages the Retry/Repair Loop.",
      "ImagePlanner": "LLM-based (Grok/Gemma). improved prompt engineering. Converts user request -> JSON Plan.",
      "ImageVerifier": "VLM-based (Qwen3-VL/GPT-V). Validates output against constraints.",
      "ComfyUIProvider": "Execution engine (txt2img/img2img) via Websocket."
    },
    "file_structure_map": {
      "roots": ["backend/modules/images/"],
      "core": ["core/planner.py (LLM)", "core/job_manager.py (Loop)", "core/verifier.py (VLM)", "core/storage.py"],
      "config": ["config/manager.py", "config/domains/*.yaml (Parameters)", "config/workflows/*.json"],
      "api": ["router.py", "service.py", "schemas.py"]
    }
  },
  "functional_requirements": {
    "robustness": "Must self-correct if generation fails (e.g., wrong color, wrong object). Loop: Plan -> Execute -> Verify -> Repair -> Retry.",
    "hvac_specialization": "Must respect canonical terms and negative packs defined in hvac.yaml.",
    "color_fidelity": "Strict adherence to requested colors (e.g., 'Yellow Split' must be yellow, not white).",
    "modes": ["packshot (ecommerce)", "lifestyle (interior)", "artistic"],
    "configuration": "Parameter files (YAML) must be editable without code changes. See config/DEVIA.md."
  },
  "data_flow": [
    "User Prompt -> ImageService",
    "ImageService -> ImagePlanner.generate_plan() -> JSON Plan",
    "ImageService -> JobManager.create_job(Plan)",
    "JobManager -> ComfyUIProvider.submit() -> Images",
    "JobManager -> ImageVerifier.verify() -> Report",
    "JobManager (if fail) -> Planner.repair() -> New Plan -> Retry",
    "JobManager -> Result"
  ],
  "configuration": {
    "domains": "backend/modules/images/config/domains/*.yaml",
    "workflows": "backend/modules/images/config/workflows/*.json"
  }
}
```
