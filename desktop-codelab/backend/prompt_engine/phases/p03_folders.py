from .base import BasePhase, PhaseContext


class FoldersPhase(BasePhase):
    @property
    def name(self) -> str:
        return "p03_folders"

    @property
    def description(self) -> str:
        return "Propose folder structure with a single PowerShell New-Item command"

    def render(self, ctx: PhaseContext) -> str:
        base = ctx.project_path or "."
        return (
            f"**CARPETAS** (base: `{base}`):\n"
            f"Carpetas existentes en ese directorio: [{ctx.folders_context}]\n"
            f"⚠️ REGLAS CRÍTICAS — incumplirlas rompe el proyecto:\n"
            f"A) Tu carpeta RAÍZ del proyecto NO puede llamarse igual que ninguna de la lista anterior. "
            f"Si coincide, elige un nombre diferente ANTES de mostrar el árbol "
            f"(ej: 'cyber' existe → usa 'cybersec', 'sec_tools', 'cyberlab').\n"
            f"B) NUNCA incluyas archivos (.py .md .json .txt .html…) en `New-Item -ItemType Directory`. "
            f"Solo carpetas. Los archivos se crean después con el editor.\n"
            f"Flujo OBLIGATORIO en 2 pasos:\n"
            f"**Paso 1 — VERIFICACIÓN** (siempre primero, antes de crear nada):\n"
            f"  Muestra el árbol propuesto. Luego propón [[NEXT_ACTION]] con:\n"
            f"  `Test-Path -Path 'ruta1','ruta2','ruta3'...` (todas las rutas que vas a crear)\n"
            f"  label: `Verificar carpetas`. Explica que comprobará si ya existen.\n"
            f"**Paso 2 — CREACIÓN** (solo DESPUÉS de ver el resultado del Paso 1):\n"
            f"  Lee el resultado: True=ya existe, False=no existe.\n"
            f"  Propón [[NEXT_ACTION]] con `New-Item -ItemType Directory -Force -Path 'ruta1','ruta2'...`\n"
            f"  incluyendo SOLO las rutas que dieron False. Label: `Crear carpetas`.\n\n"
        )
