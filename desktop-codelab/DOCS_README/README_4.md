# Robustez, Escalabilidad y Mejores Prácticas

Este documento detalla los principios de diseño aplicados en **AI Code Lab** (v1.2.0) para garantizar fiabilidad y mantenibilidad.

## 1. Abstracción y Desacoplamiento

La aplicación sigue el principio de **Separación de Responsabilidades**:

- **Motor de Prompts**: Las 17 fases están completamente desacopladas de `server.py`. Añadir una fase nueva requiere solo un archivo Python + una línea en `__init__.py`.
- **Motor de IA**: `_try_lan_model()` en `server.py` es el único punto de contacto con Qwen3 LAN. Cambiar el modelo o la URL solo afecta a esa función.
- **Acceso a Disco**: Abstraído completamente en el proceso Main de Electron. El renderer nunca toca el sistema de archivos directamente.
- **UI Atómica**: `TaskManager`, `CodeBlock` y `CollapsibleSection` son componentes independientes y reutilizables.

## 2. Robustez y Tolerancia a Fallos

El sistema implementa múltiples capas de seguridad:

### Parsing de [[NEXT_ACTION]] (3 capas frontend + 4 capas backend)
La IA puede generar JSON malformado. El sistema intenta recuperarlo en cascada:
1. `JSON.parse()` directo (caso ideal)
2. Extracción del primer objeto `{...}` balanceado (maneja texto extra después del `}`)
3. Corrección de backslashes Windows + reintentos anteriores
4. (Solo backend) Reconstrucción desde rutas Windows detectadas en texto circundante

### Retry LAN con cálculo exacto de tokens
Si Qwen3 devuelve `400 context_length_exceeded`, `server.py` extrae los tokens disponibles exactos del mensaje de error y reintenta. No se produce un 503 por token overflow.

### trust_env=False
`httpx.AsyncClient` se crea con `trust_env=False` para evitar que la configuración de proxy de Windows (heredada por Electron) redirija peticiones LAN a través de un proxy corporativo.

### Auto-Guardado antes de ejecución
Antes de ejecutar cualquier script con `run_command`, el sistema persiste automáticamente el contenido del editor para evitar inconsistencias entre código visible y ejecutable.

### Validación de Rutas (Pre-ejecución)
Antes de correr `python script.py`, el sistema verifica que `script.py` existe físicamente. Si no, alerta al usuario en lugar de lanzar un error genérico de consola.

Excepción: comandos con flags (ej. `python --version`) no activan la validación de ruta gracias al guard `!scriptMatch[1].startsWith('-')` en `App.tsx`.

### Sanitización de Código
Se eliminan artefactos de Markdown (backticks, lang tags) de los bloques de código antes de guardarlos en disco.

### Normalización de Indentación Python
Elimina sangrías accidentales en la primera línea de scripts Python — error común en respuestas de LLMs.

### Fail-safe de Contexto
Si la actualización automática de `ContextManager` falla (IA ocupada o timeout), el chat continúa sin interrupciones.

## 3. Detección de Conflictos de Carpetas

La fase `p01b_analysis_first` y la fase `p03_folders` reciben la lista de carpetas existentes en `project_path` mediante `PhaseContext.folders_context`.

Las instrucciones son explícitas:
- Si el nombre raíz propuesto ya existe en la lista, la IA **debe** elegir un nombre diferente antes de proponer estructura o botón.
- Si el conflicto persiste, la IA pide confirmación del nombre al usuario.

## 4. Gestión del Contexto de 4096 Tokens

El modelo Qwen3 tiene 4096 tokens de contexto total. La distribución objetivo:

| Componente | Tokens objetivo | Estado actual |
|------------|----------------|---------------|
| System prompt (17 fases) | ≤ 2000 | ~1527 ✅ |
| Historial de conversación | ~1500 | Variable |
| Respuesta generada | ≥ 512 | 512 mínimo |
| Margen de seguridad | ~500 | Safety truncation a 8000 chars |

Si el historial crece demasiado, el retry con tokens exactos garantiza que siempre se obtenga alguna respuesta.

## 5. Escalabilidad del Proyecto

- **Jerarquía de Tareas**: subtareas anidadas infinitamente.
- **Memoria por Tarea**: cada tarea tiene su propio contexto aislado en `.codelab/contexts/`.
- **Motor de Fases extensible**: añadir comportamientos IA solo requiere un archivo Python nuevo.

## 6. Orden y Estructura de Directorios

```
electron/   ← Lógica de plataforma de escritorio (IPC, ventana)
backend/    ← Motor IA y sistema de fases
  └─ prompt_engine/   ← 17 fases modulares
src/        ← Frontend React
  ├─ components/      ← Bloques visuales reutilizables
  └─ utils/           ← Lógica compartida (nextActionParser, systemReports, ContextManager)
.codelab/   ← Datos persistentes del proyecto (índice, contextos)
DOCS_README/← Documentación técnica detallada
```
