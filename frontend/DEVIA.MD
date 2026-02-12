# 🖥️ Frontend (SPA) - DEVIA

El frontend es una Single Page Application (SPA) ligera, sin frameworks pesados (Vanilla JS), diseñada para ser rápida y fácil de mantener.

## Arquitectura

*   **Ruta Base**: `frontend/`
*   **Entry Point**: `index.html` (Estructura HTML única).
*   **Gestor de Módulos**: `assets/js/core/router.js` (Simulado, cambio de vistas).
*   **Estilos**: `assets/css/` (CSS puro, variables CSS para temas).

## Módulos JS (`assets/js/modules/`)

> [!NOTE]
> Para detalles técnicos profundos, ver [DEVIA.MD](file:///c:/Users/migue/Documents/activepieces/pendiente-fact/bots/interjddcia/frontend/assets/js/modules/DEVIA.MD) en dicha carpeta.

### 1. `chat.js`
*   Gestiona la interfaz de chat (Text-to-SQL).
*   Stateful: Mantiene historial de conversación en memoria.
*   Conecta con `POST /api/chat/send`.

### 2. `models.js`
*   Gestión de modelos de IA.
*   Sistema de filtrado y configuración.

### 3. `outlook.js`
*   Cliente de correo unificado.

## Estándares UI
*   **Simplicidad**: No usar librerías externas si no es 100% necesario.
*   **Feedback**: Mostrar siempre estados de carga (spinners, "thinking...") y notificaciones de error claras.
*   **Responsive**: Diseño fluido compatible con `flex` y `grid`.
