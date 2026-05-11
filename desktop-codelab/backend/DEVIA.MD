# Backend — AI Code Lab

> **Última actualización:** 11/05/2026 | **Versión:** 1.2.0

## Propósito

FastAPI en puerto 8002. Orquesta las llamadas al modelo Qwen3 VL 30B (LAN JDDC),
construye el system prompt mediante el motor de fases y devuelve respuestas al frontend Electron.

---

## Estructura

```
backend/
├── server.py              ← Punto de entrada: FastAPI, endpoints, retry LAN
└── prompt_engine/
    ├── builder.py         ← PromptBuilder: ensambla fases en orden
    ├── context.py         ← PhaseContext dataclass
    └── phases/
        ├── base.py        ← BasePhase ABC (name, description, render)
        ├── p01_header.py
        ├── p01b_analysis_first.py
        ├── p02_intent.py
        ├── p02b_conversational.py
        ├── p02c_code_gen.py
        ├── p03_folders.py
        ├── p04_env_verify.py
        ├── p04b_env_failed.py
        ├── p05_plan_confirm.py
        ├── p06_code_create.py
        ├── p07_dep_install.py
        ├── p08_execution.py
        ├── p09_midflow.py
        ├── p10_general_rules.py
        ├── p11_action_buttons.py
        └── p12_error_handling.py
```

---

## Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado, modo y modelos LAN disponibles |
| GET | `/api/models` | Lista modelos LAN habilitados |
| POST | `/api/models/refresh` | Verifica modelos LAN (sin internet) |
| POST | `/api/generate` | Genera respuesta IA (prompt + historial + contexto) |
| GET | `/debug/ping-ai` | Ping directo a IP y mDNS del modelo LAN |

---

## Flujo de `POST /api/generate`

```
1. Recibe: { model_id, prompt, messages, code_context, root_dir, deep_analysis }
2. Construye PhaseContext con datos del proyecto
3. PromptBuilder.build(ctx) → system prompt (≤ 8000 chars)
4. _try_lan_model():
   a. Intento 1 — IP directa (score 100): POST /chat/completions con max_tokens=512
      → Si 400 "context_length": reduce max_tokens a max disponible y reintenta
   b. Intento 2 — mDNS (score 38): si intento 1 falla por red
   c. Último recurso: extrae tokens disponibles exactos del mensaje de error y reintenta
   → Si todos fallan: lanza excepción → HTTP 503
5. _fix_next_action(response_text):
   → Repara JSON malformado en [[NEXT_ACTION:{...}]] (4 capas)
6. Devuelve: { response, model }
```

---

## Motor de Prompts

### PhaseContext (context.py)

```python
@dataclass
class PhaseContext:
    project_path: str | None    # Carpeta raíz abierta en el explorador
    folders_context: str        # Nombres de carpetas existentes en project_path
    task_context: str | None    # Resumen de la tarea activa (de ContextManager)
    deep_analysis: bool         # Flag de análisis profundo (checkbox frontend)
    current_date: str           # Fecha inyectada automáticamente (YYYY-MM-DD)
```

### PromptBuilder (builder.py)

- Itera `DEFAULT_PHASES` en orden y llama a `phase.render(ctx)` en cada una
- Concatena resultados separados por `\n`
- Aplica truncación de seguridad a 8000 chars (`_SYS_CHAR_LIMIT`)
- El orden importa: fases más tempranas establecen contexto para las posteriores

### Añadir una nueva fase

1. Crear `phases/pNN_nombre.py` heredando `BasePhase`
2. Implementar `name`, `description` y `render(ctx)`
3. Importar y añadir a `DEFAULT_PHASES` en `phases/__init__.py`

---

## Robustez LAN

### trust_env=False
```python
async with httpx.AsyncClient(trust_env=False, timeout=60) as client:
```
Evita que Electron herede la configuración de proxy de Windows y redirija
peticiones LAN a través del proxy corporativo.

### Retry con tokens exactos
Si el modelo devuelve `400` con mensaje `"has N input tokens ... context length is M"`,
el backend calcula `available = M - N - 5` y reintenta con `max_tokens = available`.

### _fix_next_action (4 capas)
1. `json.loads()` directo del contenido extraído
2. Extracción de primer objeto `{...}` balanceado (función `_extract_first_json_object`)
3. Corrección de backslashes Windows + reintentos 1 y 2
4. Reconstrucción desde rutas Windows en texto circundante (fallback original)

---

## Restricciones críticas

- **Modelo único**: solo Qwen3 VL 30B en LAN — sin internet, sin fallback externo
- **Contexto 4096 tokens**: system prompt + historial + respuesta deben caber juntos
- **Sistema prompt**: mantenido en ~6110 chars ≈ 1527 tokens (verificado)
- **Safety truncation**: si el prompt supera 8000 chars, se trunca con aviso

---

## Dependencias Python

```
fastapi
uvicorn
httpx
```

Sin dependencias de APIs externas. Todo funciona offline excepto la LAN JDDC.
