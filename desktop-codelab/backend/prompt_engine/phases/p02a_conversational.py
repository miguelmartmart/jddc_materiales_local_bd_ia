from .base import BasePhase, PhaseContext


class ConversationalPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p02a_conversational"

    @property
    def description(self) -> str:
        return "Short natural response for conversational messages"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**CONVERSACIONAL**: 1-2 frases. "
            "PROHIBIDO: '## Resumen', '## Próximos Pasos', [[NEXT_ACTION]].\n\n"
        )
