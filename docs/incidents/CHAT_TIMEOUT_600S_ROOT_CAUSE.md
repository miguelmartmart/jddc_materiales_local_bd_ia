# CHAT_TIMEOUT_600S Root Cause (2026-07-24)

## Executive finding
The user-visible hard failure in phase intent_classification was caused by event-loop blocking network calls in the OpenAI-compatible provider.

## Evidence
- Live trace captured in CHAT_TIMEOUT_600S_TRACE.json:
  - intent_classification ended as degraded at ~5000 ms with TimeoutError.
  - request continued to next phase instead of hard failing.
- Before the fix, service returned:
  - "Se agotó el tiempo o falló la fase intent_classification..."
- Runtime logs showed repeated LAN model failures (405 on JDDC gateway path and local fallback instability), amplifying timeout pressure.

## Technical root cause
1. backend/drivers/ai/openai_compatible_provider.py used synchronous client calls:
   - self.client.chat.completions.create(...)
   inside async functions.
2. Those sync calls blocked the event loop, so asyncio.wait_for phase budgets could not preempt promptly.
3. In backend/modules/chat/service.py, an exception in intent_classification returned an immediate fatal user error, ending the request too early.

## Why quality degraded
- The system spent time in LAN model retries and endpoint probing.
- With the event loop blocked, phase budgets were not enforceable at the intended granularity.
- The request could terminate with a phase-level failure instead of continuing in deterministic fallback mode.

## Scope
- Incident scope limited to chat timeout behavior and intent phase resilience.
- No unrelated cleanup or rollback was performed.
