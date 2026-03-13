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

## SQL Normalizer — Correcciones Deterministas (v1.3.0)

**Ficheros:**
- `firebird_sql_normalizer.py` — Pipeline de normalización (20 pasos)
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
| 20 | **DOCLIN.FECHA / L.FECHA** → JOIN DOCCAB + C.FECHA | DOCLIN no tiene FECHA propia |

### Corrección post-error sin IA (`fix_after_error`)

Cuando Firebird devuelve un error conocido, `SQLCorrector.execute_with_correction`
llama primero a `fix_after_error` **antes de gastar tokens de IA**:

| Error Firebird | Corrección determinista |
|---------------|------------------------|
| `conversion error from string BLOB` | Elimina BLOB de GROUP BY, sustituye en SELECT por NOMBRE |
| `Column unknown FECHA` (en query con DOCLIN) | Añade JOIN DOCCAB C, sustituye L.FECHA → C.FECHA |
| `Column unknown X` | Mapea X a columna correcta via `COLUMN_UNKNOWN_MAP` |
| `Token unknown LIMIT/TOP/ROWS` | Convierte a `SELECT FIRST N` (detecta token en línea siguiente) |

**Flujo de corrección ultra-resiliente (v2.0):**
```
SQL generado por IA
  │
  ▼
[1] FirebirdSQLNormalizer.normalize() — 20 pasos deterministas (sin IA)
  │   • Incluye paso 20: DOCLIN.FECHA → JOIN DOCCAB + C.FECHA
  │
  ▼
[2] execute_func(sql) — ejecutar en Firebird
  │
  ├─ ✅ Éxito → devolver resultados
  │
  └─ ❌ Error → detect_error_type()
        │
        ├─ [3] fix_after_error() determinista (sin IA)
        │       ├─ ✅ Cambio aplicado → reintenta (vuelve a [2])
        │       └─ ❌ No aplicable → escala
        │
        ├─ [4] Consultar metadatos REALES de la BD (RDB$RELATION_FIELDS)
        │       • Columnas reales de cada tabla en el SQL
        │       • Muestra de datos reales (FIRST 3 filas)
        │       • Detectar si columna desconocida existe en otra tabla
        │       • Advertir si tabla tiene pocos registros (LOW_RECORD_TABLES)
        │
        ├─ [5] Corrección por IA con contexto enriquecido
        │       • Prompt incluye: columnas reales + muestra + advertencias
        │       • La IA sabe exactamente qué columnas existen en la BD real
        │
        ├─ [6] Actualizar aprendizaje permanente (db_metadata_optimized.json)
        │       • Columnas reales descubiertas → guardadas para futuras consultas
        │       • Notas críticas (ej: "FECHA no existe en DOCLIN")
        │
        └─ [7] Normalizar query corregida → reintenta (vuelve a [2])
```

---

## Advertencias en Justificación Web

**Fichero:** `service.py` (sección WEB INTERPRETER)

Cuando una consulta usa tablas con pocos registros (`LOW_RECORD_TABLES`),
la justificación incluye un bloque HTML en **rojo** advirtiendo al usuario:

```html
<p style="color:#c0392b;font-weight:bold;">⚠️ ADVERTENCIA: DOCCAB solo tiene 3 registros...</p>
```

**Tablas monitorizadas:** `LOW_RECORD_TABLES` en `firebird_sql_constants.py`

---

## Constantes Nuevas (v1.3.0)

**Fichero:** `firebird_sql_constants.py`

| Constante | Descripción |
|-----------|-------------|
| `TABLE_DATE_COLUMNS` | Qué columna de fecha tiene cada tabla. DOCLIN → no tiene, usar JOIN DOCCAB |
| `LOW_RECORD_TABLES` | Tablas con pocos registros → advertencia en justificación web |
| `COLUMN_UNKNOWN_MAP["FECHA"]` | Señal `__NEEDS_JOIN_DOCCAB__` → activa paso 20 en fix_after_error |

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
- ⚠️ Advertencias en rojo si hay tablas con pocos registros

**Renderizado:** `marked.parse()` en el frontend preserva HTML inline → el `<details>` funciona nativamente sin cambios en el JS.

**CSS:** `.message details.chat-justification` en `frontend/assets/css/style.css`
- Triángulo animado ▶ → ▼ al abrir
- Fondo gris claro, borde sutil
- Código SQL con fondo oscuro

**Clientes de voz (gafas Meta):** No reciben el bloque `<details>` — usan `interpret_results_for_voice()` determinista.

---

## SIUO — Sistema de Índices Ultra-Optimizado (v1.0.0)

**Ficheros:**
- `backend/modules/db_explorer/siuo_router.py` — Endpoints FastAPI
- `frontend/assets/js/modules/siuo_constants.js` — Constantes, estado, `markdownToHtml`
- `frontend/assets/js/modules/siuo_render.js` — Renderizado DOM
- `frontend/assets/js/modules/siuo.js` — Orquestador (lógica de negocio)
- `frontend/assets/css/siuo.css` — Estilos

### Tokens de contexto

| Parámetro | Valor | Dónde |
|-----------|-------|-------|
| `max_tokens` default | **8000** | `ContextAskRequest`, `ContextTestRequest` |
| `max_tokens` máximo | **16000** | Validación Pydantic `le=16000` |
| Input HTML default | **8000** | `siuo_render.js` skeleton |
| Input HTML máximo | **16000** | `max="16000"` en el input |

### markdownToHtml — Algoritmo de renderizado (v2.0)

El backend devuelve **Markdown + HTML mixto** (tablas GFM, `<details>`, `<span style=...>`, `<p style=...>`).
El algoritmo extrae los bloques HTML **antes** de escapar para evitar doble-procesado:

```
Texto Markdown + HTML mixto
  │
  ▼
[0] Detección HTML puro → devolver tal cual (evita doble-procesado)
  │
  ▼
[1] Extraer bloques HTML (placeholder %%HTML_BLOCK_N%%):
    • <details>...</details>  → añade class="chat-justification"
    • <span style=...>        → colores inline del backend
    • <p style=...>           → advertencias de tablas con pocos registros
  │
  ▼
[2] Extraer tablas GFM (placeholder %%TABLE_BLOCK_N%%):
    • | Col | → <table class="md-table"> envuelta en <div class="md-table-wrap">
    • Scroll horizontal automático en móvil/panel estrecho
  │
  ▼
[3] Escapar HTML restante (XSS-safe)
  │
  ▼
[4] Inline Markdown: **negrita**, *cursiva*, `código`
  │
  ▼
[5] Listas: - item → <ul><li>
  │
  ▼
[6] Párrafos: \n\n → </p><p>
  │
  ▼
[7] Restaurar tablas (%%TABLE_BLOCK_N%% → HTML)
  │
  ▼
[8] Restaurar HTML blocks (%%HTML_BLOCK_N%% → HTML)
  │
  ▼
[9] Limpiar párrafos vacíos <p></p>
```

**Anti-regresión crítica:** Los placeholders deben ser `%%TABLE_BLOCK_N%%` y `%%HTML_BLOCK_N%%`
(sin `%%` extra al final del prefijo). Los tests verifican esto automáticamente.

### Tablas con scroll horizontal

Las tablas Markdown se envuelven en `<div class="md-table-wrap">` con `overflow-x: auto`.
Esto permite scroll horizontal en paneles estrechos sin romper el layout.

### Modal de respuesta expandida

El botón **⛶ Expandir** aparece tras una respuesta exitosa en el panel "Probar ContextRetriever".
Abre un modal con el contenido completo, cierra con `Escape` o clic en el overlay.

```javascript
// API pública
window.SIUOModule.expandResult()  // Abre modal
window.SIUOModule.closeModal()    // Cierra modal
```

---

## Tests

| Fichero | Qué cubre |
|---------|-----------|
| `tests/unit/test_normalizer_blob_and_compras.py` | BLOB en GROUP BY, artículos más comprados, fix_after_error |
| `tests/unit/test_ultra_resilience.py` | Paso 20 DOCLIN.FECHA, tablas no indexadas, flujo completo ultra-resiliente, tablas con pocos registros, corrección encadenada |
| `tests/unit/test_sql_normalizer.py` | Pipeline completo de normalización |
| `tests/unit/test_siuo_render_and_tokens.py` | markdownToHtml (tablas, details, span, placeholders), tokens Pydantic, ficheros fuente JS/CSS |

```bash
# Ejecutar desde la raíz del proyecto
python -m pytest bots/interjddcia/tests/unit/ -v
# Resultado esperado: 49+ passed (test_siuo_render_and_tokens: 49/49)
```
