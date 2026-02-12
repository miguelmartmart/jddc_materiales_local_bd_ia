# 📜 Módulo de Historial de Interacciones (Interaction History)

Este módulo centralizado gestiona el registro y consulta de todas las interacciones realizadas con la Inteligencia Artificial en el sistema.

## 🏛️ Arquitectura

Diseñado para ser agnóstico al módulo que lo invoca, permite trazar el flujo completo de "input usuario -> respuesta IA".

*   **Ruta Base**: `backend/modules/interaction_history/`
*   **Base de Datos**: `backend/data/interaction_history.db` (SQLite independiente).
*   **Servicio**: `service.py` (`InteractionHistoryService`).
*   **Router**: `router.py`.

## 📦 Estructura de Datos

La tabla `interactions` almacena:

*   **Module**: Origen (`OUTLOOK`, `CHAT`, `SIMULATION`).
*   **Action**: Tipo de operación (`ANALYSIS`, `DEEP_ANALYSIS`).
*   **Input/Output**: Contexto completo y respuesta raw.
*   **Metadata**: JSON flexible para referencias (ej: `email_id`, `sender` en caso de correos).

## 🔗 Uso

### Registrar un Evento (Backend)

```python
from backend.modules.interaction_history.service import InteractionHistoryService

history = InteractionHistoryService()
history.log_interaction(
    module="OUTLOOK",
    action="DEEP_ANALYSIS",
    input_context="Analiza este correo...",
    output_result="{ 'summary': '...' }",
    model_id="gemini-1.5-pro",
    metadata={"email_id": "123", "subject": "Factura"}
)
```

### Consultar Historial (API)

`GET /api/history/logs?limit=50&module=OUTLOOK`

Respuesta:
```json
{
  "success": true,
  "logs": [ ... ]
}
```
