# Guía de Testing, Calidad y Validación

Este documento detalla las estrategias de validación y los mecanismos de control de calidad en **AI Code Lab** (v1.2.0).

## 1. Validación de Código Generado (IA)

### Mecanismos de Robustez
- **Sanitización de Bloques**: detecta bloques mal formados (ej. ```` ```// ruta.py ````) y extrae lenguaje y ruta real mediante expresiones regulares.
- **Normalización de Indentación (Python)**: implementado en `handleSaveFile`, elimina sangrías accidentales en la primera línea de scripts Python.
- **Validación de Rutas (Pre-ejecución)**: antes de `python script.py`, verifica que `script.py` existe en disco. Si no existe, muestra alerta en lugar de error genérico de consola.
  - **Excepción**: comandos con flags (`python --version`, `node --version`) no activan la validación. Guard: `!scriptMatch[1].startsWith('-')`.

### Validación de [[NEXT_ACTION]]
- **Frontend (3 capas)**: `nextActionParser.ts` intenta JSON.parse directo, luego extracción balanceada, luego corrección de backslashes.
- **Backend (4 capas)**: `_fix_next_action()` en `server.py` aplica los mismos pasos más reconstrucción desde rutas Windows.
- Si todas las capas fallan, se muestra un error claro al usuario sin romper la UI.

## 2. Testing de Integración (Electron + IPC)

- **Puente Seguro**: `preload.ts` es el único canal de comunicación, tipado con TypeScript.
- **Confirmación de Ejecución**: `shell:execute` muestra diálogo nativo antes de correr cualquier comando — actúa como "test de seguridad" manual en tiempo real.
- **Verificación de Proxy**: `trust_env=False` en httpx garantiza que las peticiones LAN no pasen por configuraciones de proxy heredadas de Electron.

## 3. Tests Automatizados

Los scripts de test viven en la raíz del proyecto. Ejecutar con el backend corriendo.

### `test_connectivity.py` — Conectividad (4 tests)
```cmd
python test_connectivity.py
```
Cubre: backend local (8002), IA LAN directa (10.13.79.31), `/debug/ping-ai`, generación end-to-end.

### `test_backend_generation.py` — Integración backend (8 tests)
```cmd
python test_backend_generation.py
```
Cubre: `/health`, `/api/models`, `/debug/ping-ai`, generación básica, con historial, con `project_path`, tamaño del prompt engine (≤ 8000 chars), orden de fases.

### `test_coherence.py` — Coherencia de respuestas IA (11 tests)
```cmd
python test_coherence.py
```
- **Grupo A**: respuestas con system_prompt manual (saludo, pregunta, código)
- **Grupo B**: flujo real — no inyectar estructura en mensajes conversacionales
- **Grupo C — fase de carpetas**:
  - `C1`: la IA propone `Test-Path` (verificación) ANTES de `New-Item` (creación)
  - `C2`: la IA no reutiliza nombres de carpetas ya existentes como raíz del proyecto
  - `C3`: `New-Item -ItemType Directory` no contiene archivos `.py`, `.md`, etc.
  - `C4`: en el Paso 2, la IA crea solo las carpetas que dieron `False` en `Test-Path`

### Ejecutar todos de una vez
```cmd
python test_connectivity.py && python test_backend_generation.py && python test_coherence.py
```

## 4. Tests Manuales Complementarios

Para validar una instalación nueva:

1. **Guardado**: escribir en el editor y pulsar `Ctrl+S` → verificar que el archivo aparece en el explorador.
2. **Ejecución**: crear `test.py` con `print("Hola")`, guardarlo, pulsar **Run** → ver salida en terminal.
3. **Flujo de carpetas — verificación primero**: pedir "crea la estructura de carpetas" → el primer botón debe ser "Verificar carpetas" (`Test-Path`), NO "Crear carpetas" directamente.
4. **Conflicto de carpetas**: con carpeta `cyber` existente, pedir "crea un proyecto cyber" → la IA debe detectar el conflicto y proponer nombre alternativo (`cybersec`, etc.).
5. **No archivos en directories**: verificar que el comando `New-Item -ItemType Directory` del botón no incluye rutas con `.py`, `.md`, `.json`.
6. **Flag `--version`**: pedir "¿Qué versión de Python tengo?" → al ejecutar `python --version`, debe mostrar la versión, NO un error de "archivo no encontrado".
7. **Persistencia**: crear tarea + chat + mensajes → cerrar app → volver a abrir → verificar `.codelab/project_index.json`.

## 4b. Verificación del Tamaño del Prompt Engine

```cmd
cd backend
python -c "
from prompt_engine.builder import PromptBuilder
from prompt_engine.phases import DEFAULT_PHASES, PhaseContext
ctx = PhaseContext(project_path='C:/test', folders_context='src, backend, electron')
p = PromptBuilder(DEFAULT_PHASES).build(ctx)
print(f'Chars: {len(p)} | Tokens: {len(p)//4}')
"
```
Esperado: Chars ≤ 8000, Tokens ≤ 2000.

### Añadir una Fase (Checklist de Regresión)
1. Verificar que el total de chars sigue bajo 8000.
2. Verificar que `action_buttons` y `error_handling` siguen al final.
3. Ejecutar `python test_backend_generation.py` completo.

## 5. Escalabilidad Técnica

- **Separación de Concern**: lógica de terminal aislada de lógica de chat en `App.tsx`.
- **Estados Complejos**: `setTasks` con actualizaciones in-place en árbol recursivo — la UI permanece sincronizada con jerarquías profundas.
- **Motor de Fases extensible**: cada fase es independiente, testeable en aislamiento con un `PhaseContext` mock.
