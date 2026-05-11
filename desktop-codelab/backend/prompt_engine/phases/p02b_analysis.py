from .base import BasePhase, PhaseContext


class AnalysisPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p02b_analysis"

    @property
    def description(self) -> str:
        return "Direct analysis or extraction of information from documents/images"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**ANÁLISIS/RESUMEN**: Responde directamente. Analiza TODOS los adjuntos "
            "(imágenes y documentos, ninguno omitido). Sin [[NEXT_ACTION]].\n\n"
        )
