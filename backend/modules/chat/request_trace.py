"""
request_trace.py — Trazabilidad mínima por petición de chat.

Registra fases, presupuestos y metadatos de ejecución sin incluir secretos
ni prompts completos. Diseñado para diagnóstico de incidentes de timeout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_exc(exc: Exception) -> str:
    text = str(exc) if exc else ""
    # Redacción mínima de rutas/credenciales accidentales en mensajes largos
    text = text.replace("\\", "/")
    if len(text) > 240:
        text = text[:240] + "..."
    return text


@dataclass
class PhaseTrace:
    phase_name: str
    phase_started_at: str
    phase_ended_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    remaining_budget_ms: Optional[int] = None
    timeout_budget_ms: Optional[int] = None
    model_requested: Optional[str] = None
    model_actual: Optional[str] = None
    retry_number: int = 0
    fallback_number: int = 0
    database_mode: Optional[str] = None
    sql_execution_ms: Optional[int] = None
    rows_returned: Optional[int] = None
    status: str = "started"
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None


@dataclass
class RequestTrace:
    trace_id: str
    request_started_at: str
    request_deadline_at: str
    request_timeout_ms: int
    model_requested: Optional[str]
    database_mode: str
    phases: List[PhaseTrace] = field(default_factory=list)
    total_elapsed_ms: Optional[int] = None
    status: str = "started"

    _started_monotonic: float = field(default_factory=time.monotonic, repr=False)
    _deadline_monotonic: float = field(default=0.0, repr=False)

    @classmethod
    def create(
        cls,
        trace_id: str,
        timeout_ms: int,
        model_requested: Optional[str],
        database_mode: str,
    ) -> "RequestTrace":
        now = datetime.now(timezone.utc)
        deadline = now.timestamp() + (timeout_ms / 1000.0)
        return cls(
            trace_id=trace_id,
            request_started_at=now.isoformat(),
            request_deadline_at=datetime.fromtimestamp(deadline, tz=timezone.utc).isoformat(),
            request_timeout_ms=timeout_ms,
            model_requested=model_requested,
            database_mode=database_mode,
            _deadline_monotonic=time.monotonic() + (timeout_ms / 1000.0),
        )

    def remaining_budget_ms(self) -> int:
        remaining = int(max(0.0, self._deadline_monotonic - time.monotonic()) * 1000)
        return remaining

    def start_phase(self, phase_name: str, timeout_budget_ms: Optional[int] = None) -> PhaseTrace:
        phase = PhaseTrace(
            phase_name=phase_name,
            phase_started_at=_utc_now_iso(),
            timeout_budget_ms=timeout_budget_ms,
            remaining_budget_ms=self.remaining_budget_ms(),
            model_requested=self.model_requested,
            database_mode=self.database_mode,
            status="started",
        )
        self.phases.append(phase)
        return phase

    def finish_phase(
        self,
        phase: PhaseTrace,
        *,
        status: str,
        model_actual: Optional[str] = None,
        retry_number: int = 0,
        fallback_number: int = 0,
        sql_execution_ms: Optional[int] = None,
        rows_returned: Optional[int] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        phase.phase_ended_at = _utc_now_iso()
        started = datetime.fromisoformat(phase.phase_started_at)
        ended = datetime.fromisoformat(phase.phase_ended_at)
        phase.elapsed_ms = int((ended - started).total_seconds() * 1000)
        phase.remaining_budget_ms = self.remaining_budget_ms()
        phase.status = status
        phase.model_actual = model_actual
        phase.retry_number = retry_number
        phase.fallback_number = fallback_number
        phase.sql_execution_ms = sql_execution_ms
        phase.rows_returned = rows_returned
        if exception is not None:
            phase.exception_type = type(exception).__name__
            phase.exception_message = _safe_exc(exception)

    def mark_done(self, status: str) -> None:
        self.total_elapsed_ms = int((time.monotonic() - self._started_monotonic) * 1000)
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "request_started_at": self.request_started_at,
            "request_deadline_at": self.request_deadline_at,
            "request_timeout_ms": self.request_timeout_ms,
            "model_requested": self.model_requested,
            "database_mode": self.database_mode,
            "total_elapsed_ms": self.total_elapsed_ms,
            "status": self.status,
            "phases": [
                {
                    "phase_name": p.phase_name,
                    "phase_started_at": p.phase_started_at,
                    "phase_ended_at": p.phase_ended_at,
                    "elapsed_ms": p.elapsed_ms,
                    "remaining_budget_ms": p.remaining_budget_ms,
                    "timeout_budget_ms": p.timeout_budget_ms,
                    "model_requested": p.model_requested,
                    "model_actual": p.model_actual,
                    "retry_number": p.retry_number,
                    "fallback_number": p.fallback_number,
                    "database_mode": p.database_mode,
                    "sql_execution_ms": p.sql_execution_ms,
                    "rows_returned": p.rows_returned,
                    "status": p.status,
                    "exception_type": p.exception_type,
                    "exception_message": p.exception_message,
                }
                for p in self.phases
            ],
        }

    def write_json(self, file_path: str) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
