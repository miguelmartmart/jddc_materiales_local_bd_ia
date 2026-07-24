import asyncio
import time

import pytest

from backend.modules.chat.request_trace import RequestTrace
from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator


class _FakeSvc:
    def _phase_timeout_s(self, deadline_monotonic: float, phase_budget_ms: int) -> float:
        remaining = int(max(0.0, deadline_monotonic - time.monotonic()) * 1000)
        if remaining <= 0:
            raise TimeoutError("REQUEST_DEADLINE_EXCEEDED")
        return max(0.1, min(phase_budget_ms, remaining) / 1000.0)


@pytest.mark.asyncio
async def test_request_trace_includes_phase_timings_and_models():
    trace = RequestTrace.create(
        trace_id="trace-1",
        timeout_ms=60000,
        model_requested="jddcia-qwen3-8b-ip",
        database_mode="real",
    )

    p = trace.start_phase("intent_classification", timeout_budget_ms=5000)
    await asyncio.sleep(0.01)
    trace.finish_phase(
        p,
        status="ok",
        model_actual="jddcia-qwen3-8b-ip",
        retry_number=0,
        fallback_number=0,
    )
    trace.mark_done("ok")

    data = trace.to_dict()
    assert data["trace_id"] == "trace-1"
    assert data["phases"][0]["phase_name"] == "intent_classification"
    assert data["phases"][0]["elapsed_ms"] is not None
    assert data["phases"][0]["model_requested"] == "jddcia-qwen3-8b-ip"
    assert data["phases"][0]["model_actual"] == "jddcia-qwen3-8b-ip"


def test_phase_timeout_respects_remaining_budget():
    svc = _FakeSvc()
    deadline = time.monotonic() + 0.05
    timeout_s = svc._phase_timeout_s(deadline, 5000)
    assert timeout_s <= 0.2


@pytest.mark.asyncio
async def test_orchestrator_stops_when_deadline_exceeded():
    orch = ModelFallbackOrchestrator()
    resp, model = await orch.execute_with_fallback(
        system_prompt="x",
        user_message="y",
        preferred_model_id="jddcia-qwen3-8b-ip",
        execution_policy={"max_retries_per_model": 0, "max_models": 1},
        deadline_monotonic=asyncio.get_running_loop().time() - 0.001,
    )
    assert resp is None
    assert model is None
    assert orch.last_execution_stats.get("aborted_by_deadline") is True


def test_trace_marks_exception_type_message_without_secrets():
    trace = RequestTrace.create("trace-2", 60000, "jddcia-qwen3-8b-ip", "real")
    p = trace.start_phase("firebird_execution", timeout_budget_ms=15000)
    err = RuntimeError("timeout while reading response")
    trace.finish_phase(p, status="failed", exception=err)
    out = trace.to_dict()["phases"][0]
    assert out["exception_type"] == "RuntimeError"
    assert "timeout" in (out["exception_message"] or "")
