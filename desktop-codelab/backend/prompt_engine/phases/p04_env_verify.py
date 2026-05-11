from .base import BasePhase, PhaseContext


class EnvVerifyPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p04_env_verify"

    @property
    def description(self) -> str:
        return "Mandatory environment check after folder creation, before code generation"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**TRAS CREAR CARPETAS** (Success: True + New-Item): "
            "Verifica el entorno antes de crear código. Anuncia la tecnología elegida. "
            "Propón `python --version` / `node --version` / `docker --version` según corresponda. "
            "[[NEXT_ACTION]] label `Verificar entorno`. No generes código todavía.\n\n"
        )
