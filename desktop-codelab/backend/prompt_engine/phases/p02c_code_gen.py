from .base import BasePhase, PhaseContext


class CodeGenPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p02c_code_gen"

    @property
    def description(self) -> str:
        return "Generate complete, functional code with file-path headers"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**CÓDIGO**: Genera código completo. `// ruta/archivo.ext` al inicio de cada bloque. "
            "Sin `input()` interactivo. "
            "Estructura de respuesta: ESTADO → EXPLICACIÓN → CÓDIGO → [[NEXT_ACTION]]\n\n"
        )
