# DEVIA — pipeline/

> Documentación técnica del módulo `pipeline/` dentro de `chat/`.
> Detalla cómo se aplican los principios DEVIA del proyecto a este submódulo específico.
> Fuente de principios generales: `bots/interjddcia/DEVIA.MD`

---

## 1. RESPONSABILIDAD DEL MÓDULO

El módulo `pipeline/` implementa el **pipeline modular de procesamiento de mensajes del chat**.
Cada fase del pipeline es un módulo Python independiente que:
- Puede activarse/desactivarse desde `config.json` sin modificar código
- Tiene una única responsabilidad (SRP)
- Tiene fallback determinista si la IA falla
- Es testeable de forma aislada

**NO es responsabilidad de este módulo:**
- Ejecutar SQL (responsabilidad de `db_simulator/` o `drivers/db/`)
- Gestionar sesiones de usuario (responsabilidad de `chat/service.py`)
- Almacenar historial (responsabilidad de `interaction_history/`)

---

## 2. ESTRUCTURA DE FICHEROS

```
pipeline/
  __init__.py          ← Exporta todas las clases públicas + principios DEVIA completos
  DEVIA.md             ← Este fichero
  pipeline_config.py   ← Configuración centralizada de todas las fases (única fuente de verdad)
  phase0_safety.py     ← Fase 0: Seguridad (protección BD + filtro ético/legal)
  phase4_formatter.py  ← Fase 4: Formateador de respuesta (determinista + IA opcional)
```

**Regla de nomenclatura**: `phase{N}_{nombre}.py` donde N es el orden de ejecución en el pipeline.
Las fases se numeran con saltos (0, 4, ...) para permitir insertar nuevas fases sin renombrar.

---

## 3. FASES DEL PIPELINE

### Fase 0 — Safety (`phase0_safety.py`)

**Responsabilidad**: Proteger la BD y filtrar contenido ético/legal.

**Dos capas independientes**:
1. **Determinista** (`evaluate_deterministic`): patrones regex + keywords → instantáneo, sin IA
2. **IA** (`SafetyGuard.evaluate_with_ai`): análisis semántico profundo → solo si la capa 1 no es concluyente

**Niveles de riesgo** (`RiskLevel`):
- `SAFE` → pasar al siguiente paso del pipeline
- `WARN` → pasar con advertencia en los metadatos
- `BLOCK` → rechazar con mensaje explicativo

**Razones de bloqueo** (`BlockReason`):
- `DB_PROTECTION` → intento de modificar/eliminar datos de la BD
- `PRIVACY` → solicitud de datos personales sensibles
- `ETHICS` → contenido inapropiado
- `LEGAL` → contenido ilegal

**Principios DEVIA aplicados**:
- ✅ Fallback determinista: si la IA falla, la capa determinista siempre responde
- ✅ Privacidad por diseño: datos sensibles detectados antes de llegar a la IA
- ✅ Trazabilidad: cada decisión de bloqueo queda en logs con razón y nivel
- ✅ Sin magic numbers: todos los patrones en `pipeline_config.py`

---

### Fase 4 — Formatter (`phase4_formatter.py`)

**Responsabilidad**: Formatear el resultado SQL para presentación al usuario.

**Dos fases independientes**:
1. **Determinista** (`format_deterministic`): detecta tipo de resultado y aplica formato Markdown
2. **IA** (`generate_ai_narrative`): genera narrativa explicativa → solo si `use_ai=True`

**Tipos de resultado** (`ResultType`):
- `KPI_SINGLE` → 1 fila, 1-3 columnas → formato destacado con negrita
- `TABLE` → múltiples filas/columnas → tabla Markdown
- `LIST` → 1 columna, múltiples filas → lista Markdown
- `EMPTY` → sin resultados → mensaje informativo
- `ERROR` → error en la consulta → mensaje de error con detalle

**Formateo de valores** (determinista, sin IA):
- Columnas monetarias (`IMPORTETOTAL`, `TOTAL`, etc.) → `1.234,56 €`
- Columnas de porcentaje (`PCT`, `TASA_EXITO`, etc.) → `12,3%`
- Columnas de conteo (`N_FACTURAS`, `COUNT`, etc.) → `1.234`
- Columnas de fecha (`FECHA`, `FECHAEMISION`, etc.) → `DD/MM/YYYY`

**Principios DEVIA aplicados**:
- ✅ Fallback determinista: si la IA falla, el formato determinista siempre funciona
- ✅ Constantes centralizadas: `_MONEY_COLUMNS`, `_PCT_COLUMNS`, etc. al inicio del fichero
- ✅ Timeout configurable: `ai_timeout_s` (default 8s) — nunca esperar indefinidamente
- ✅ Activable/desactivable: `use_ai=False` desactiva la narrativa IA sin cambiar código

---

## 4. CONFIGURACIÓN CENTRALIZADA (`pipeline_config.py`)

**Única fuente de verdad** para todos los parámetros del pipeline.

```python
# Ejemplo de configuración
config = get_pipeline_config()
config.phase0.enabled          # True/False — activar/desactivar fase 0
config.phase0.use_ai           # True/False — usar IA en fase 0
config.phase4.ai_timeout_s     # 8 — timeout para narrativa IA
```

**Recarga sin reiniciar**:
```python
reload_pipeline_config()  # Recarga desde config.json en caliente
```

**Principios DEVIA aplicados**:
- ✅ Sin magic numbers: todos los valores tienen nombre y están aquí
- ✅ Singleton: `get_pipeline_config()` devuelve siempre la misma instancia
- ✅ Recarga en caliente: `reload_pipeline_config()` sin reiniciar el servidor

---

## 5. CÓMO AÑADIR UNA NUEVA FASE

1. Crear `phase{N}_{nombre}.py` en esta carpeta
2. Implementar la clase principal con:
   - `__init__(self, config: PhaseConfig)` — recibe config centralizada
   - Método principal `async def process(self, ctx: dict) -> dict`
   - Fallback determinista si la IA falla
   - Logging en cada paso crítico
3. Añadir la configuración en `pipeline_config.py`:
   ```python
   @dataclass
   class PipelineConfig:
       phaseN: PhaseConfig = field(default_factory=lambda: PhaseConfig(
           enabled=True,
           use_ai=True,
           ai_timeout_s=8,
       ))
   ```
4. Exportar en `__init__.py`
5. Añadir la fase al pipeline en `chat/service.py`
6. Documentar en este DEVIA.md

---

## 6. PATRONES DE DISEÑO APLICADOS EN ESTE MÓDULO

| Patrón | Dónde | Por qué |
|--------|-------|---------|
| **Strategy** | `phase0_safety.py` — dos estrategias: determinista vs IA | Intercambiables sin cambiar el código cliente |
| **Template Method** | Cada fase: `process()` = flujo fijo + pasos variables | El flujo del pipeline es fijo; la implementación varía |
| **Singleton** | `get_pipeline_config()` | Una sola instancia de config en toda la app |
| **Factory** | `format_deterministic()` crea `FormattedResult` según tipo | Encapsula la lógica de creación |
| **Null Object** | `FormattedResult` con `result_type=EMPTY` | Evita None checks en el código cliente |

---

## 7. SEGURIDAD Y PRIVACIDAD

**Regla crítica**: Este módulo NO tiene acceso directo a la BD.
- La Fase 0 analiza el **texto de la pregunta**, no los datos de la BD
- La Fase 4 formatea **resultados ya obtenidos**, no consulta la BD
- Ningún dato de la BD pasa por la IA de red (solo la IA local LAN)

**Datos que SÍ pueden ir a la IA local (LAN)**:
- Texto de la pregunta del usuario
- Resumen de resultados SQL (máximo 5 filas de muestra)
- Metadatos de columnas (nombres, tipos)

**Datos que NUNCA van a ninguna IA**:
- Valores de columnas sensibles (NIF, DNI, teléfonos, emails)
- Contraseñas o tokens
- Datos bancarios

---

## 8. TESTS

```
tests/unit/
  test_phase0_safety.py      ← Tests de la fase 0 (determinista + IA mock)
  test_phase4_formatter.py   ← Tests del formateador (determinista)
```

**Cómo ejecutar**:
```bash
cd bots/interjddcia
python -m pytest tests/unit/test_phase0_safety.py -v
python -m pytest tests/unit/test_phase4_formatter.py -v
```

**Cobertura mínima requerida**: 80% en cada fase.

---

## 9. DEPENDENCIAS

```
pipeline/ depende de:
  ← chat/firebird_sql_constants.py  (constantes SQL — solo phase0)
  ← core/config/settings.py         (configuración global)
  ← drivers/ai/                     (modelos IA — solo si use_ai=True)

pipeline/ NO depende de:
  ✗ db_simulator/    (no accede a BD)
  ✗ db_explorer/     (no accede a metadatos)
  ✗ interaction_history/  (no gestiona historial)
  ✗ otros módulos de chat/ (independencia total)
```

---

## 10. DIAGNÓSTICO Y MONITORIZACIÓN

```bash
# Ver logs del pipeline en tiempo real
tail -f logs/chat.log | grep "\[PIPELINE\]\|\[SAFETY\]\|\[FORMATTER\]"

# Verificar que la fase 0 está activa
curl http://localhost:8001/api/chat/pipeline/status

# Recargar configuración del pipeline sin reiniciar
curl -X POST http://localhost:8001/api/chat/pipeline/reload-config
```

**Formato de logs**:
```
[SAFETY][DETERMINISTIC] INPUT → EVALUATOR: "DROP TABLE" → BLOCK (DB_PROTECTION)
[FORMATTER] Resultado formateado: type=table rows=25 ai=True
[PIPELINE][PHASE0] ✅ SAFE — pasando a fase siguiente
```

---

## 11. HISTORIAL DE CAMBIOS

| Versión | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-06-05 | Creación del módulo pipeline/ con phase0_safety y phase4_formatter |
| 1.1.0 | 2026-06-05 | Añadidos principios DEVIA completos en __init__.py y DEVIA.md |
