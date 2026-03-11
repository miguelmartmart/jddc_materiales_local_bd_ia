# DEVIA TECHNICAL CONTEXT: AI ROBUSTNESS & ORCHESTRATION
# Detailed logic for Model Fallback, Self-Healing, and Error Recovery.

```json
{
  "component": "ModelFallbackOrchestrator",
  "file": "backend/modules/chat/model_fallback_orchestrator.py",
  "mission": "Ensure valid AI response regardless of provider failures or hallucinations.",
  "strategies": {
    "fallback_chain": {
      "concept": "If preferred model fails, try next available model in 'smart_sort' order.",
      "smart_sort": "Prioritize models by: 1. Health (proven success), 2. Speed (for simple tasks), 3. Power (for complex reasoning).",
      "fast_fail": "If a provider returns 401/QuotaExceeded, mark provider as OFF and skip all its models."
    },
    "retry_policies": {
      "technical_error": {
        "triggers": ["Timeout", "ConnectionRefused", "5xx"],
        "action": "Retry immediately with same model (up to 2 times), then switch model."
      },
      "semantic_error": {
        "triggers": ["Invalid JSON", "Hallucinated Format", "Empty Response"],
        "action": "Trigger Self-Correction Loop."
      }
    },
    "self_correction_loop": {
      "mechanism": "Reflection Prompt",
      "steps": [
        "1. Detect malformed output (e.g. JSON expected but got Markdown).",
        "2. Feed error back to AI: 'You sent invalid JSON. Error: X. Fix it.'",
        "3. Retry generation with 'repair mode' instructions.",
        "4. If fails 3 times, switch to 'Dumb/Robust' fallback logic (e.g. Mock)."
      ]
    }
  },
  "prompt_injection_for_robustness": {
    "system_instructions": "Always injected: 'Return STRICT JSON. No markdown backticks.'",
    "error_context": "When retrying, previous error is appended to prompt."
  }
}
```

---

## SQL Normalizer — Correcciones Deterministas (v1.2.0)

**Ficheros:**
- `firebird_sql_normalizer.py` — Pipeline de normalización (19 pasos)
- `firebird_sql_constants.py` — Única fuente de verdad para constantes

### Pipeline de normalización (`FirebirdSQLNormalizer.normalize`)

| # | Corrección | Ejemplo |
|---|-----------|---------|
| 1 | Comentarios SQL `--` y `/* */` | eliminados |
| 2 | Whitespace multilínea → una línea | `\n` → ` ` |
| 3 | Punto y coma final | `SELECT ... ;` → `SELECT ...` |
| 4 | Backticks MySQL | `` `TABLA` `` → `TABLA` |
| 5 | Comillas dobles en identificadores | `"NOMBRE"` → `NOMBRE` |
| 6 | `LIMIT/TOP/ROWS N` → `SELECT FIRST N` | `LIMIT 10` → `FIRST 10` |
| 7 | Añadir `FIRST N` si falta (no en agregaciones) | `SELECT CODIGO` → `SELECT FIRST 100 CODIGO` |
| 8 | `ILIKE` → `UPPER(col) LIKE UPPER(val)` | case-insensitive |
| 9 | `LIKE` → `UPPER(col) LIKE UPPER(val)` | case-insensitive |
| 10 | `!=` → `<>` | operador estándar Firebird |
| 11 | `TRUE/FALSE` → `'T'/'F'` | booleanos Firebird |
| 12 | `NOW()/GETDATE()/SYSDATE` → `CURRENT_TIMESTAMP/CURRENT_DATE` | funciones de fecha |
| 13 | `CONCAT(a,b)` → `a \|\| b` | concatenación Firebird |
| 14 | `SUBSTRING(c,p,l)` → `SUBSTRING(c FROM p FOR l)` | sintaxis Firebird |
| 15 | `OFFSET N` → eliminar | no soportado en FB 2.5 |
| 16 | Columnas erróneas conocidas | `STOCK` → `STOCKARTICULO` |
| 17 | Alias con comillas dobles | `AS "alias"` → `AS alias` |
| 18 | **BLOB en GROUP BY/SELECT** → eliminar/sustituir | `DESCRIPCION` → `NOMBRE` |
| 19 | **Artículos más comprados sin JOIN** → reescribir con JOIN DOCLIN | COUNT(*) real |

### Corrección post-error sin IA (`fix_after_error`)

Cuando Firebird devuelve un error conocido, `SQLCorrector.execute_with_correction`
llama primero a `fix_after_error` **antes de gastar tokens de IA**:

| Error Firebird | Corrección determinista |
|---------------|------------------------|
| `conversion error from string BLOB` | Elimina BLOB de GROUP BY, sustituye en SELECT por NOMBRE |
| `Column unknown X` | Mapea X a columna correcta via `COLUMN_UNKNOWN_MAP` |
| `Token unknown LIMIT/TOP/ROWS` | Convierte a `SELECT FIRST N` |

**Flujo de corrección:**
```
SQL falla → detect_error_type() → ¿error conocido?
  ├─ SÍ → fix_after_error() → ¿cambio aplicado?
  │         ├─ SÍ → reintenta con SQL corregido (sin IA)
  │         └─ NO → escala a IA
  └─ NO (unknown) → lanza excepción
```

---

## Respuesta Web — Justificación en Desplegable

**Fichero:** `service.py` (sección WEB INTERPRETER)

Las respuestas web incluyen un bloque `<details><summary>` colapsado con:
- Tablas consultadas
- Columnas devueltas
- Número exacto de registros
- SQL ejecutado (copiable)
- Cómo verificarlo en la BD
- Razonamiento del SQL

**Renderizado:** `marked.parse()` en el frontend preserva HTML inline → el `<details>` funciona nativamente sin cambios en el JS.

**CSS:** `.message details.chat-justification` en `frontend/assets/css/style.css`
- Triángulo animado ▶ → ▼ al abrir
- Fondo gris claro, borde sutil
- Código SQL con fondo oscuro

**Clientes de voz (gafas Meta):** No reciben el bloque `<details>` — usan `interpret_results_for_voice()` determinista.

---

## Tests

| Fichero | Qué cubre |
|---------|-----------|
| `tests/unit/test_normalizer_blob_and_compras.py` | BLOB en GROUP BY, artículos más comprados, fix_after_error |
| `tests/unit/test_sql_normalizer.py` | Pipeline completo de normalización |

```bash
# Ejecutar desde bots/interjddcia/
python -m pytest tests/unit/ -v
```
