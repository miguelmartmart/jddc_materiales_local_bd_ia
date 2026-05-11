from .base import BasePhase, PhaseContext


class ErrorHandlingPhase(BasePhase):
    @property
    def name(self) -> str:
        return "shared_errors"

    @property
    def description(self) -> str:
        return "General command/script failure response — analyse, fix, re-offer button"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**ERRORES (PRIORIDAD MÁXIMA)**: CRITICAL EXECUTION FAILURE → "
            "analiza el error, corrige el código, termina con botón `run_command`.\n"
            "USER_CANCELLED → el usuario canceló (no es un bug), vuelve a ofrecer el mismo botón. "
            "No digas 'Perfecto' ni 'Genial' hasta una ejecución exitosa real.\n"
        )
