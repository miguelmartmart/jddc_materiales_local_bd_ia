from .base import BasePhase, PhaseContext


class MidflowPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p09_midflow"

    @property
    def description(self) -> str:
        return "Interpret free-text user messages that arrive instead of a button click"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**TEXTO LIBRE EN MID-FLOW**: Si el usuario escribe en lugar de pulsar un botón:\n"
            "- Cambia tecnología → actualiza plan, vuelve a Verificar entorno.\n"
            "- Quiere saltar verificación → acepta, presenta plan directo.\n"
            "- Modifica plan → actualiza y vuelve a ofrecer confirmación.\n"
            "- Pregunta → responde y vuelve a ofrecer el botón actual.\n"
            "- Cancela → confirma y espera nuevas instrucciones.\n"
            "- Afirmación corta ('sí', 'adelante', 'procede', 'ok') → "
            "actúa como si hubiera pulsado el botón pendiente.\n\n"
        )
