from .base import BasePhase, PhaseContext


class PlanConfirmPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p05_plan_confirm"

    @property
    def description(self) -> str:
        return "Present implementation plan for user confirmation after env verification"

    def render(self, ctx: PhaseContext) -> str:
        return (
            "**TRAS VERIFICACIÓN OK** (output con 'Python 3.x'/'v18.x'/'Docker version'/etc.): "
            "Confirma la versión detectada. Presenta el plan: archivos a crear, arquitectura, "
            "dependencias externas, consideraciones. "
            r'[[NEXT_ACTION]] exacto: {"type":"confirm_plan",'
            r'"content":"Confirmado. Procede a crear los archivos de código según el plan.",'
            r'"label":"Crear archivos de código","cancel_label":"Modificar plan"}. '
            "No generes código todavía.\n\n"
        )
