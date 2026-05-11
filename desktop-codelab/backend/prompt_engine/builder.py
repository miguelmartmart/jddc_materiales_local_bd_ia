"""
prompt_engine.builder
=====================
Assembles the final system prompt from an ordered list of phases.

Usage
-----
    from prompt_engine.builder import PromptBuilder
    from prompt_engine.phases import DEFAULT_PHASES, PhaseContext

    ctx = PhaseContext(base_folder="my-project", ...)
    prompt = PromptBuilder(DEFAULT_PHASES).build(ctx)

Customising phases for a different project
------------------------------------------
    from prompt_engine.phases import (
        HeaderPhase, IntentPhase, GeneralRulesPhase, ActionButtonsPhase
    )

    minimal_phases = [HeaderPhase(), IntentPhase(), GeneralRulesPhase(), ActionButtonsPhase()]
    prompt = PromptBuilder(minimal_phases).build(ctx)
"""

from typing import List
from .phases.base import BasePhase, PhaseContext


class PromptBuilder:
    """
    Immutable after construction — call build() as many times as needed.
    Thread-safe: phases are stateless and build() creates no shared state.
    """

    def __init__(self, phases: List[BasePhase]) -> None:
        self._phases = list(phases)

    # ── Fluent API for one-off phase additions ────────────────────────────────

    def with_phase(self, phase: BasePhase) -> "PromptBuilder":
        """Return a new builder with an additional phase appended."""
        return PromptBuilder(self._phases + [phase])

    def without_phase(self, name: str) -> "PromptBuilder":
        """Return a new builder with the named phase removed."""
        return PromptBuilder([p for p in self._phases if p.name != name])

    # ── Core assembly ─────────────────────────────────────────────────────────

    def build(self, ctx: PhaseContext) -> str:
        """
        Render all phases in order and join non-empty blocks with a newline.
        Each phase is independent: a crash in one is caught and annotated
        rather than silently propagated or silently skipped.
        """
        blocks: List[str] = []
        for phase in self._phases:
            try:
                block = phase.render(ctx)
                if block:
                    blocks.append(block)
            except Exception as exc:
                # Annotate the failure in-prompt so the AI can surface it
                # rather than receiving a silently truncated prompt.
                blocks.append(
                    f"[PROMPT_ENGINE ERROR in phase '{phase.name}': {exc}]"
                )
        return "\n".join(blocks)

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def phase_names(self) -> List[str]:
        """Ordered list of phase names — useful for logging and tests."""
        return [p.name for p in self._phases]
