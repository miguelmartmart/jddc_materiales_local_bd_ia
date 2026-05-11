from .base import BasePhase, PhaseContext


class ExecutionPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p08_execution"

    @property
    def description(self) -> str:
        return "Analyse execution output and suggest next steps; break infinite retry loops"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**TRAS EJECUTAR** (python/node/dotnet + Success:True): "
            "Confirma el éxito. Si lanzó servidor/app web: [[NEXT_ACTION]] type `browser` "
            "label `Abrir en navegador`. Pregunta qué quiere hacer ahora.\n"
            "**BUCLE DE FALLOS**: Si el historial tiene 3+ CRITICAL EXECUTION FAILURE consecutivos "
            "del mismo comando: para el ciclo, resume los intentos y pide más contexto al usuario. "
            "Sin [[NEXT_ACTION]] hasta nueva instrucción.\n\n"
        )
