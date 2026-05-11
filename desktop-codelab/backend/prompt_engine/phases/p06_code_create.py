from .base import BasePhase, PhaseContext


class CodeCreatePhase(BasePhase):
    @property
    def name(self) -> str:
        return "p06_code_create"

    @property
    def description(self) -> str:
        return "Generate all code files after plan is confirmed"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**TRAS CONFIRMAR PLAN** (mensaje: 'Confirmado. Procede a crear...'): "
            "Genera TODOS los archivos, completos y funcionales. `// ruta/archivo.ext`. "
            "Con dependencias externas: [[NEXT_ACTION]] label `Instalar dependencias`. "
            "Sin dependencias: [[NEXT_ACTION]] label `Ejecutar`.\n\n"
        )
