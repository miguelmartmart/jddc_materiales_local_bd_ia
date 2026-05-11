"""
prompt_engine.phases
====================
All system-prompt phases, each in its own module.

To add a new phase:
  1. Create a new file pNN_name.py with a class that extends BasePhase.
  2. Import it here and add an instance to DEFAULT_PHASES at the correct position.
  3. No other file needs to change.

Phase ordering is intentional: the AI reads the prompt top-to-bottom, so
earlier phases set context that later ones build on.
"""

from typing import List
from .base import BasePhase, PhaseContext
from .p00_header import HeaderPhase
from .p01_intent import IntentPhase
from .p01b_analysis_first import AnalysisFirstPhase
from .p02a_conversational import ConversationalPhase
from .p02b_analysis import AnalysisPhase
from .p02c_code_gen import CodeGenPhase
from .p03_folders import FoldersPhase
from .p04_env_verify import EnvVerifyPhase
from .p04b_env_failed import EnvFailedPhase
from .p05_plan_confirm import PlanConfirmPhase
from .p06_code_create import CodeCreatePhase
from .p07_dep_install import DepInstallPhase
from .p08_execution import ExecutionPhase
from .p09_midflow import MidflowPhase
from .shared_rules import GeneralRulesPhase
from .shared_actions import ActionButtonsPhase
from .shared_errors import ErrorHandlingPhase

DEFAULT_PHASES: List[BasePhase] = [
    HeaderPhase(),
    IntentPhase(),
    AnalysisFirstPhase(),   # Explain reasoning before any action
    ConversationalPhase(),
    AnalysisPhase(),
    CodeGenPhase(),
    FoldersPhase(),
    EnvVerifyPhase(),
    EnvFailedPhase(),   # NEW: recovery when tool not installed
    PlanConfirmPhase(),
    CodeCreatePhase(),
    DepInstallPhase(),  # NEW: install deps before first run
    ExecutionPhase(),   # NEW: analyse output + break retry loops
    MidflowPhase(),
    GeneralRulesPhase(),
    ActionButtonsPhase(),
    ErrorHandlingPhase(),
]

__all__ = [
    "BasePhase",
    "PhaseContext",
    "DEFAULT_PHASES",
    "HeaderPhase",
    "IntentPhase",
    "AnalysisFirstPhase",
    "ConversationalPhase",
    "AnalysisPhase",
    "CodeGenPhase",
    "FoldersPhase",
    "EnvVerifyPhase",
    "EnvFailedPhase",
    "PlanConfirmPhase",
    "CodeCreatePhase",
    "DepInstallPhase",
    "ExecutionPhase",
    "MidflowPhase",
    "GeneralRulesPhase",
    "ActionButtonsPhase",
    "ErrorHandlingPhase",
]
