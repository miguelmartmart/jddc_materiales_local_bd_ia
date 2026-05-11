from .base import BasePhase, PhaseContext


class GeneralRulesPhase(BasePhase):
    @property
    def name(self) -> str:
        return "shared_rules"

    @property
    def description(self) -> str:
        return "Language, tone, and format rules for all responses"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**REGLAS**: Responde en español. Trato de tú. "
            "Directo y profesional. No repitas código o explicaciones previas.\n\n"
        )
