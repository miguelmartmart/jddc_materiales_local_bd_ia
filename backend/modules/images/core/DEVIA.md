# DEVIA CORE CONTEXT: IMAGES/CORE
# Deep Technical Context for Planner, Verifier, and JobManager logic.

```json
{
  "namespace": "backend.modules.images.core",
  "critical_logic": {
    "planner.py": {
      "role": "Intent Understanding & Prompt Engineering",
      "mechanism": "ModelFallbackOrchestrator (LLM)",
      "inputs": ["User Prompt", "HVAC Domain Config (YAML)", "Hardware Limits"],
      "heuristic": "Injects `hvac.yaml` into System Prompt. Enforces 'Strong Color' logic to prevent white-casing hallucinations."
    },
    "job_manager.py": {
      "role": "Execution Loop & State Management",
      "mechanism": "Async Loop with Semaphore",
      "retry_logic": {
        "technical": "Retries connection/timeout errors (Fast)",
        "semantic": "Retries generation failures (Slow). Uses Verifier + Repair.",
        "max_attempts": 3
      }
    },
    "verifier.py": {
      "role": "Visual Quality Assurance",
      "mechanism": "VLM (Qwen3-VL/GPT4-V)",
      "constraints": ["Object Presence", "Color Accuracy", "Background Compliance"],
      "output": "JSON Report (passed: bool, issues: list)"
    }
  },
  "prompts": {
    "planner_system": "Defined in planner.py (PLANNER_SYSTEM_PROMPT_TEMPLATE). Contains YAML injection marker.",
    "verifier_system": "Defined in verifier.py (VERIFICATION_SYSTEM_PROMPT). Strict rules."
  },
  "usage_rules": {
    "dependency_injection": "Planner and Verifier must be injected into JobManager at runtime.",
    "async": "All core methods are async. Use await."
  }
}
```
