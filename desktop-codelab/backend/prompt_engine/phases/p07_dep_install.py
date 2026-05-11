from .base import BasePhase, PhaseContext


class DepInstallPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p07_dep_install"

    @property
    def description(self) -> str:
        return "Install project dependencies before the first execution"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**TRAS INSTALAR DEPENDENCIAS** (pip/npm/yarn + Success:True): "
            "Confirma e inicia [[NEXT_ACTION]] label `Ejecutar`. "
            "Si falló: analiza error, corrige requirements.txt/package.json, "
            "[[NEXT_ACTION]] label `Instalar dependencias` con comando corregido.\n\n"
        )
