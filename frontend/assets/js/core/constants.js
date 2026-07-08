/**
 * Constantes del Sistema DEVIA - Frontend
 * Centraliza todos los valores constantes del frontend
 */

// ============================================================================
// CONFIGURACIÓN DE API
// ============================================================================

export const API = {
    BASE_URL: '/api',
    ENDPOINTS: {
        CHAT: '/api/chat',
        CHAT_SEND: '/api/chat/send',
        MODELS: '/api/models',
        MODELS_ENABLED: '/api/models/?enabled_only=true',
        PROMPTS: '/api/prompts',
        ARTICLES: '/api/articles'
    },
    HEADERS: {
        CONTENT_TYPE: 'application/json'
    }
};

// ============================================================================
// CONFIGURACIÓN DE BASE DE DATOS
// ============================================================================

export const DB_CONFIG = {
    HOST: 'HOST1',
    PORT: 3050,
    DATABASE: 'C:\\Distrito\\OBRAS\\Database\\JUANDEDI\\2021.fdb',
    USERNAME: 'SYSDBA',
    PASSWORD: 'masterkey'
};

// ============================================================================
// MENSAJES DE UI
// ============================================================================

export const UI_MESSAGES = {
    LOADING: 'Cargando...',
    THINKING: 'Pensando...',
    ERROR_CONNECTION: 'Error de conexión.',
    ERROR_GENERIC: 'Error: ',
    ERROR_UNKNOWN: 'Unknown error',
    SELECT_MODEL: 'Por favor selecciona un modelo IA',
    NO_MESSAGE: 'Por favor escribe un mensaje'
};

// ============================================================================
// ROLES DE CHAT
// ============================================================================

export const CHAT_ROLES = {
    USER: 'user',
    AI: 'ai',
    SYSTEM: 'system'
};

// ============================================================================
// ESTILOS DE UI
// ============================================================================

export const UI_STYLES = {
    MESSAGE: {
        MARGIN_BOTTOM: '10px',
        PADDING: '10px',
        BORDER_RADIUS: '8px',
        MAX_WIDTH: '80%'
    },
    COLORS: {
        USER_BG: '#e3f2fd',
        AI_BG: '#f5f5f5',
        ERROR_BG: '#ffebee'
    },
    ALIGNMENT: {
        LEFT: 'left',
        RIGHT: 'right',
        AUTO: 'auto'
    }
};

// ============================================================================
// EVENTOS
// ============================================================================

export const EVENTS = {
    CLICK: 'click',
    KEYPRESS: 'keypress',
    ENTER_KEY: 'Enter'
};

// ============================================================================
// SELECTORES DE DOM
// ============================================================================

export const DOM_SELECTORS = {
    CHAT: {
        SEND_BTN: 'btn-send-chat',
        INPUT: 'chat-input',
        MESSAGES: 'chat-messages',
        MODEL_SELECTOR: 'chat-model-selector',
        ATTACH_BTN: 'btn-attach-file',
        FILE_INPUT: 'chat-file-input',
        PREVIEW: 'chat-preview-container'
    },
    ARTICLES: {
        ANALYZE_BTN: 'btn-analyze',
        RESULTS: 'analysis-results',
        MODEL_SELECTOR: 'articles-model-selector'
    }
};

// ============================================================================
// LÍMITES
// ============================================================================

export const LIMITS = {
    MAX_MESSAGE_LENGTH: 2000,
    CHAT_HISTORY: 50,
    MAX_RETRIES: 3
};

// ============================================================================
// TIMEOUTS
// ============================================================================

export const TIMEOUTS = {
    API_REQUEST:            120000, // 120s — petición normal al modelo IA
    AI_REQUEST:             120000, // alias para compatibilidad con chat-recovery.js
    AI_REQUEST_DEEP:        600000, // 600s — análisis profundo (modelo LAN 30B puede tardar 5-10 min)
                                    // DEVIA: el backend no tiene timeout propio — el frontend espera
                                    // todo lo que necesite mientras el heartbeat confirme que el
                                    // backend sigue vivo. 600s es el primer checkpoint, no el límite.
    HEARTBEAT_INTERVAL:      30000, // 30s — intervalo entre pings de heartbeat
    HEARTBEAT_PING_TIMEOUT:   5000, // 5s  — timeout de cada ping individual
    MAX_TIMEOUT_EXTENSIONS:     20, // DEVIA: mientras el backend esté vivo (ping OK), seguir esperando.
                                    // 20 extensiones × 600s = 200 min máximo teórico.
                                    // En la práctica: el backend responde antes de agotar las extensiones.
                                    // Si el backend muere (ping falla) → abortar inmediatamente.
    DEBOUNCE:                  300, // 300ms — debounce de inputs
};

// ============================================================================
// MENSAJES DE RECUPERACIÓN DE CHAT (chat-recovery-ui.js)
// ============================================================================

export const RECOVERY_MESSAGES = {
    BTN_CANCEL:       '✕ Cancelar',
    BTN_CANCEL_TITLE: 'Cancelar la petición en curso',
    BTN_RETRY:        '🔄 Reintentar',
    BTN_RETRY_TITLE:  'Volver a enviar el mensaje',
    RETRY_HINT:       'Puedes reintentar la petición.',
};

// ============================================================================
// MÉTODOS HTTP
// ============================================================================

export const HTTP_METHODS = {
    GET: 'GET',
    POST: 'POST',
    PUT: 'PUT',
    DELETE: 'DELETE',
    PATCH: 'PATCH'
};

// ============================================================================
// CÓDIGOS DE ESTADO HTTP
// ============================================================================

export const HTTP_STATUS = {
    OK: 200,
    CREATED: 201,
    BAD_REQUEST: 400,
    UNAUTHORIZED: 401,
    NOT_FOUND: 404,
    INTERNAL_ERROR: 500
};
