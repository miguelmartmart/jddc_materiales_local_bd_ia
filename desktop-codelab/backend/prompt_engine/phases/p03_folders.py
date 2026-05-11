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
            f"[INTERNO — no verbalizar] Carpetas ya presentes: [{ctx.folders_context}]\n"
            f"Usa esa lista solo para elegir un nombre raíz que no colisione. "
            f"NUNCA menciones en tu respuesta qué carpetas 'ya existen' — el Test-Path lo descubrirá.\n"
            f"NUNCA incluyas archivos (.py .md .json .txt .html…) en `New-Item -ItemType Directory`. Solo carpetas.\n"
            f"Flujo OBLIGATORIO en 2 pasos:\n"
            f"**Paso 1 — VERIFICACIÓN** (siempre primero):\n"
            f"  Muestra el árbol propuesto. Di 'Voy a verificar que las rutas estén libres antes de crear nada.'\n"
            f"  Propón [[NEXT_ACTION]] con `Test-Path -Path 'base/raiz','base/raiz/sub1','base/raiz/sub2',...`\n"
            f"  INCLUYE LA RAÍZ Y TODAS LAS SUBCARPETAS — no solo la raíz. Label: `Verificar carpetas`.\n"
            f"**Paso 2 — CREACIÓN** (solo DESPUÉS de ver el resultado del Paso 1):\n"
            f"  True=ya existe, False=libre. Propón [[NEXT_ACTION]] con\n"
            f"  `New-Item -ItemType Directory -Force -Path 'ruta1','ruta2','ruta3',...`\n"
            f"  INCLUYE TODAS LAS RUTAS QUE DIERON FALSE (raíz y subcarpetas). Label: `Crear carpetas`.\n"
            f"  IMPORTANTE: no digas 'estructura creada' si New-Item no incluía todas las subcarpetas.\n\n"
        )
