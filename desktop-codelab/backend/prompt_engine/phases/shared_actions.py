from .base import BasePhase, PhaseContext


class ActionButtonsPhase(BasePhase):
    @property
    def name(self) -> str:
        return "shared_actions"

    @property
    def description(self) -> str:
        return "[[NEXT_ACTION]] JSON format reference for all supported action types"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**[[NEXT_ACTION]]** (SOLO tareas técnicas ejecutables, NUNCA en conversación/análisis):\n"
            r'Formato: [[NEXT_ACTION:{"type":"...","content":"...","label":"..."}]]' "\n"
            "Tipos: `run_command` (PowerShell/cmd), `browser` (abrir HTML/URL), "
            "`confirm_plan` (confirmar plan), `open_file` (abrir en editor).\n"
            "Opcionales: `cancel_label` (texto botón cancelar), "
            "`cancel_message` (mensaje enviado al cancelar).\n\n"
        )
