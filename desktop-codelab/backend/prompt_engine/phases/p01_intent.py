from .base import BasePhase, PhaseContext


class IntentPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p01_intent"

    @property
    def description(self) -> str:
        return "Mandatory intent detection before any action"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**INTENCIÓN (OBLIGATORIA)**: Detecta qué quiere el usuario antes de responder:\n"
            "- Saludo/gracias/pregunta corta → responde en 1-2 frases. Sin código. Sin [[NEXT_ACTION]].\n"
            "- Análisis/resumen de adjuntos → hazlo directamente. Sin [[NEXT_ACTION]].\n"
            "- Crear/modificar código → genera código completo.\n"
            "- Ejecutar algo → propón comando con [[NEXT_ACTION]].\n"
            "- Ambiguo → infiere la intención más probable y actúa. No preguntes.\n\n"
        )
