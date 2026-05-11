"""
prompt_engine
=============
Modular system-prompt assembly for the desktop-codelab AI assistant.

Public surface
--------------
    from prompt_engine import PromptBuilder, PhaseContext, DEFAULT_PHASES

The rest of the sub-modules are implementation details.
"""

from .builder import PromptBuilder
from .phases import DEFAULT_PHASES, PhaseContext

__all__ = ["PromptBuilder", "PhaseContext", "DEFAULT_PHASES"]
