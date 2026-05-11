from .base import BasePhase, PhaseContext


class HeaderPhase(BasePhase):
    """Personalised project intro + attached-document/image summary."""

    @property
    def name(self) -> str:
        return "p00_header"

    @property
    def description(self) -> str:
        return "Project identity and attachment inventory"

    def render(self, ctx: PhaseContext) -> str:
        return (
            f"Eres un asistente inteligente y versátil trabajando en el proyecto "
            f"'{ctx.base_folder}'{ctx.content_desc}."
            f"{ctx.attachments_context}\n"
        )
