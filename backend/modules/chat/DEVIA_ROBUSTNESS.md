# DEVIA TECHNICAL CONTEXT: AI ROBUSTNESS & ORCHESTRATION
# Detailed logic for Model Fallback, Self-Healing, and Error Recovery.

```json
{
  "component": "ModelFallbackOrchestrator",
  "file": "backend/modules/chat/model_fallback_orchestrator.py",
  "mission": "Ensure valid AI response regardless of provider failures or hallucinations.",
  "strategies": {
    "fallback_chain": {
      "concept": "If preferred model fails, try next available model in 'smart_sort' order.",
      "smart_sort": "Prioritize models by: 1. Health (proven success), 2. Speed (for simple tasks), 3. Power (for complex reasoning).",
      "fast_fail": "If a provider returns 401/QuotaExceeded, mark provider as OFF and skip all its models."
    },
    "retry_policies": {
      "technical_error": {
        "triggers": ["Timeout", "ConnectionRefused", "5xx"],
        "action": "Retry immediately with same model (up to 2 times), then switch model."
      },
      "semantic_error": {
        "triggers": ["Invalid JSON", "Hallucinated Format", "Empty Response"],
        "action": "Trigger Self-Correction Loop."
      }
    },
    "self_correction_loop": {
      "mechanism": "Reflection Prompt",
      "steps": [
        "1. Detect malformed output (e.g. JSON expected but got Markdown).",
        "2. Feed error back to AI: 'You sent invalid JSON. Error: X. Fix it.'",
        "3. Retry generation with 'repair mode' instructions.",
        "4. If fails 3 times, switch to 'Dumb/Robust' fallback logic (e.g. Mock)."
      ]
    }
  },
  "prompt_injection_for_robustness": {
    "system_instructions": "Always injected: 'Return STRICT JSON. No markdown backticks.'",
    "error_context": "When retrying, previous error is appended to prompt."
  }
}
```
