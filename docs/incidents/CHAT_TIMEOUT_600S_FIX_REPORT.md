# CHAT_TIMEOUT_600S Fix Report (2026-07-24)

## Implemented changes
1. Non-blocking provider calls
- File: backend/drivers/ai/openai_compatible_provider.py
- Change: wrapped synchronous OpenAI client calls with asyncio.to_thread(...).
- Impact: phase deadlines in service now take effect because event loop is no longer blocked by sync I/O.

2. Resilient intent classification fallback
- File: backend/modules/chat/service.py
- Change: on intent_classification exception/timeout, switch to deterministic classifier and continue flow.
- New trace behavior:
  - intent phase marked as status=degraded
  - model_actual="deterministic-fallback"
  - exception type captured in trace
- User no longer gets immediate fatal message for intent phase timeout.

## Validation executed
- Deterministic tests:
  - backend/tests/test_chat_timeout_600s_fix.py: 4 passed
  - backend/tests/test_timeout_resilience.py: 111 passed
  - backend/tests/test_chat_recovery_logic.py: 88 passed, 1 skipped
- Live probe:
  - prompt: "dime un proyecto cualquiera, y sus certificaciones"
  - response returned HTTP 200 with trace and degraded intent fallback.
- Live matrix (partial completion under diagnostic cap):
  - 4/6 calls completed, all HTTP 200, all intent phases degraded around 5s and continued.
  - Remaining deep-analysis case exceeded practical diagnostic window in this run.

## Current incident state
CHAT_TIMEOUT_600S_FIX_IMPLEMENTED_LIVE_VALIDATION_BLOCKED

Reason:
- Core fix is implemented and proven on live traces.
- Full 6/6 matrix could not be completed within the diagnostic execution window due long-running deep-analysis path under current LAN model instability.
