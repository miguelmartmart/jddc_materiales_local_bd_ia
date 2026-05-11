from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PhaseContext:
    """
    Runtime context passed to every phase during prompt assembly.
    All fields are optional; phases use only what they need.
    Keeping this in one place makes it trivial to add context
    to all phases at once without touching individual phase files.
    """
    base_folder: str = ""
    project_path: Optional[str] = None
    folders_context: str = "(Ninguna detectada)"
    has_images: bool = False
    has_documents: bool = False
    attachments_context: str = ""
    content_desc: str = ""


class BasePhase(ABC):
    """
    Abstract base for every system-prompt phase.

    A phase is a single, self-contained block of instructions for the AI.
    Phases are independent: they do not import each other and do not share
    mutable state. The only coupling point is PhaseContext, which is read-only
    inside a render() call.

    Implementing a new phase:
        class MyPhase(BasePhase):
            @property
            def name(self) -> str: return "my_phase"

            @property
            def description(self) -> str: return "What this phase handles"

            def render(self, ctx: PhaseContext) -> str:
                return "Instructions for the AI..."

    To activate a new phase: add an instance to DEFAULT_PHASES in
    prompt_engine/phases/__init__.py. No other file needs touching.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short machine-readable identifier, e.g. 'p04_env_verify'."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line human description of what this phase handles."""
        ...

    @abstractmethod
    def render(self, ctx: PhaseContext) -> str:
        """
        Return the text block for this phase.
        Return an empty string to skip this phase entirely.
        Must be deterministic and side-effect-free.
        """
        ...
