from .base import BasePhase, PhaseContext


class EnvFailedPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p04b_env_failed"

    @property
    def description(self) -> str:
        return "Structured recovery when environment verification fails (tool not installed)"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**HERRAMIENTA NO INSTALADA** (output: 'not recognized'/'not found'/'no se reconoce' "
            "en cmd --version): No corrijas código — la herramienta falta.\n"
            "Paso 1 — Localizar la herramienta: ofrece un [[NEXT_ACTION]] con "
            "`Get-Command python -ErrorAction SilentlyContinue; "
            "where.exe python 2>$null; "
            "python --version 2>&1` para encontrar si está instalada en otra ruta.\n"
            "Paso 2 — Si no está instalada: ofrece instalación via "
            "`winget install Python.Python.3` / `winget install OpenJS.NodeJS.LTS` / "
            "`winget install Docker.DockerDesktop`. "
            "[[NEXT_ACTION]] label `Instalar X`, cancel_label `Cambiar tecnología`, "
            "cancel_message `Propón una alternativa ya instalada`. "
            "No generes código hasta instalar.\n"
            "**TRAS INSTALAR** (winget/choco + Success:True): confirma e inicia verificación de nuevo.\n\n"
        )
