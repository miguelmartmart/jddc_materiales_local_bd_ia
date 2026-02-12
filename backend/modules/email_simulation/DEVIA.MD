# 🔮 Módulo de Simulación de Respuesta (Email Simulation)

Este módulo independiente proporciona capacidades de simulación de decisiones para correos electrónicos. Utiliza IA para determinar cuál sería la siguiente mejor acción (Responder, Ignorar, Acción de Usuario) y genera el contenido correspondiente (borrador de respuesta o instrucciones).

## 🏛️ Arquitectura

Este módulo sigue el patrón de diseño modular del sistema, desacoplado del módulo de lectura de correos (`outlook`), permitiendo su reutilización.

*   **Ruta Base**: `backend/modules/email_simulation/`
*   **Router**: `router.py` (Exposición del endpoint API).
*   **Servicio**: `service.py` (Lógica de negocio e integración con `AIFactory`).

## 🧠 Lógica de Simulación

El servicio `EmailSimulationService` evalúa el contexto del correo (Asunto, Remitente, Cuerpo) y utiliza un modelo LLM (vía `AIFactory`) para generar una estructura JSON con:

1.  **Acción (`action`)**:
    *   `REPLY`: La IA redacta una respuesta formal o apropiada.
    *   `IGNORE`: Se determina que es spam o irrelevante.
    *   `USER_ACTION`: Se detecta que el usuario debe realizar una tarea fuera del cliente de correo (ej: pagar factura).
2.  **Razonamiento (`reasoning`)**: Explicación breve de la decisión.
3.  **Contenido de Simulación (`simulation_content`)**: El texto del borrador o la descripción de la tarea.

## 🔗 Endpoints API

| Método | Endpoint | Descripción | Body (JSON) |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/simulation/simulate` | Simula la siguiente acción para un correo dado. | `{ "subject": "...", "sender": "...", "body": "..." }` |

## 🛠️ Integración Frontend

Se integra en el módulo de Outlook (`outlook.js`) mediante un botón "🔮 Simular Siguiente Paso". Utiliza un overlay modal para mostrar los resultados y permite acciones directas (como abrir el cliente de correo con el borrador generado).
