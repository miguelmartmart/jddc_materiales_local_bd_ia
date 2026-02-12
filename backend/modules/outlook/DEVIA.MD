# 📧 Módulo Outlook/Email (Integración y Análisis)

Este módulo gestiona la conexión con servicios de correo (Outlook, Gmail), la descarga de mensajes y su análisis inteligente mediante IA.

## Arquitectura

*   **Ruta Base**: `backend/modules/outlook/`
*   **Router**: `router.py` (Endpoints análisis/sync).
*   **Servicio Base**: `service.py` (Conexión IMAP, `imaplib`).
*   **Servicio Análisis**: `analysis_service.py` (Lógica de IA, Prompts).
*   **Config**: `analysis_config.py` (Reglas de exclusión/filters).
*   **Adjuntos**: `attachment_analyzer.py` (Extracción de texto de PDF, DOCX, etc.).

## Características Clave

### 1. Estrategia de Autenticación Híbrida
El sistema intenta conectar en cascada para garantizar acceso:
1.  **Outlook Nativo**: Credenciales directas.
2.  **Outlook App Password**: Para cuentas con 2FA.
3.  **Híbrido (Gmail -> Outlook)**: Credenciales Gmail contra servidor Outlook (casos legacy).
4.  **Gmail Nativo**: Fallback final.

### 2. Análisis IA (`analysis_service.py`)
*   **Categorización Estricta**: Clasifica en `Trabajo`, `Publicidad`, `Factura`, `Notificación`, `Personal`.
*   **Detección de "Ofertas"**: Distingue rigurosamente entre *Ofertas de Empleo* (Trabajo) y *Ofertas Comerciales* (Publicidad) mediante prompts negativos.
*   **Resumen Global**: Genera un "Morning Briefing" de los correos más importantes.

### 3. Exclusiones (`analysis_config.py`)
*   Sistema de "Blacklist" para ignorar remitentes o asuntos específicos (newsletter, spam recurrente).
*   Configurable desde la UI.

## Endpoints API

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/outlook/sync` | Forzar sincronización IMAP. |
| `POST` | `/api/outlook/analyze` | Analizar correos con IA (resumen, categorías). |
| `POST` | `/api/outlook/deep-analyze` | Análisis profundo de un solo correo. |
| `POST` | `/api/outlook/analyze-attachment` | Analizar contenido de adjuntos. |
