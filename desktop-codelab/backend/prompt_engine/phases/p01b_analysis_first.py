from .base import BasePhase, PhaseContext


class AnalysisFirstPhase(BasePhase):
    """
    Forces the AI to think and communicate its reasoning BEFORE taking any action.
    Also enforces folder-name conflict detection before any New-Item proposal.
    """

    @property
    def name(self) -> str:
        return "p01b_analysis_first"

    @property
    def description(self) -> str:
        return "Analyse request and check for conflicts before proposing any action"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**ANÁLISIS PREVIO (ANTES DE CUALQUIER ACCIÓN)**:\n"
            "Para tareas técnicas (crear estructura, escribir código, ejecutar algo):\n"
            "- Explica QUÉ vas a crear y POR QUÉ esa elección es la mejor.\n"
            "- Para estructuras de carpetas: muestra el árbol propuesto con la función de cada carpeta.\n"
            "- Para código: indica arquitectura, dependencias y posibles riesgos.\n"
            "DATOS INTERNOS (úsalos para decidir, NO los menciones en tu respuesta al usuario):\n"
            f"Carpetas que ya existen en el directorio: [{ctx.folders_context}]\n"
            "Con esta info interna:\n"
            "1. Elige un nombre raíz que no colisione — pero NO digas 'ya existe X' ni 'evito Y porque existe'. "
            "Simplemente presenta la estructura como si fuera tu propuesta natural.\n"
            "2. Los archivos (.py .md .json .html .txt…) NUNCA van en `New-Item -ItemType Directory`. "
            "Solo carpetas. Los archivos se crean después desde el editor.\n\n"
        )
