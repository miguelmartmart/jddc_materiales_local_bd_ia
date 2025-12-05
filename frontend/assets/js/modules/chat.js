import { API, DB_CONFIG, UI_MESSAGES, CHAT_ROLES, UI_STYLES, EVENTS, DOM_SELECTORS, HTTP_METHODS } from '../core/constants.js';

export class ChatModule {
    constructor() {
        this.apiBase = API.ENDPOINTS.CHAT;
        this.conversationHistory = [];
    }

    init() {
        const sendBtn = document.getElementById(DOM_SELECTORS.CHAT.SEND_BTN);
        const input = document.getElementById(DOM_SELECTORS.CHAT.INPUT);

        if (sendBtn && input) {
            const newBtn = sendBtn.cloneNode(true);
            sendBtn.parentNode.replaceChild(newBtn, sendBtn);

            const newInput = input.cloneNode(true);
            input.parentNode.replaceChild(newInput, input);

            newBtn.addEventListener(EVENTS.CLICK, () => this.sendMessage());
            newInput.addEventListener(EVENTS.KEYPRESS, (e) => {
                if (e.key === EVENTS.ENTER_KEY) this.sendMessage();
            });
        }

        this.loadModels();
    }

    async loadModels() {
        try {
            const response = await fetch(API.ENDPOINTS.MODELS_ENABLED);
            const models = await response.json();

            const selector = document.getElementById(DOM_SELECTORS.CHAT.MODEL_SELECTOR);
            if (selector) {
                selector.innerHTML = models.map(m =>
                    `<option value="${m.id}">${m.name}</option>`
                ).join('');

                if (models.length > 0) {
                    selector.value = models[0].id;
                }
            }
        } catch (error) {
            console.error('Error loading models:', error);
        }
    }

    async sendMessage() {
        const input = document.getElementById(DOM_SELECTORS.CHAT.INPUT);
        const message = input.value.trim();
        const modelSelector = document.getElementById(DOM_SELECTORS.CHAT.MODEL_SELECTOR);
        const selectedModel = modelSelector ? modelSelector.value : null;

        if (!message) return;

        if (!selectedModel) {
            alert(UI_MESSAGES.SELECT_MODEL);
            return;
        }

        this.appendMessage(CHAT_ROLES.USER, message);
        this.conversationHistory.push({ role: 'user', content: message });
        input.value = '';

        const thinkingId = 'thinking-' + Date.now();
        this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.THINKING, thinkingId);

        try {
            const dbParams = {
                host: DB_CONFIG.HOST,
                port: DB_CONFIG.PORT,
                database: DB_CONFIG.DATABASE,
                username: DB_CONFIG.USERNAME,
                password: DB_CONFIG.PASSWORD
            };

            const response = await fetch(`${this.apiBase}/send`, {
                method: HTTP_METHODS.POST,
                headers: { 'Content-Type': API.HEADERS.CONTENT_TYPE },
                body: JSON.stringify({
                    message: message,
                    db_params: dbParams,
                    model_id: selectedModel,
                    conversation_history: this.conversationHistory
                })
            });

            const data = await response.json();

            const thinkingEl = document.getElementById(thinkingId);
            if (thinkingEl) thinkingEl.remove();

            if (data.success) {
                // Check if confirmation is required
                if (data.response && data.response.status === 'confirmation_required') {
                    this.showConfirmationModal(data.response, message, selectedModel);
                } else {
                    this.appendMessage(CHAT_ROLES.AI, data.response);
                    this.conversationHistory.push({ role: 'assistant', content: data.response });
                }
            } else {
                this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.ERROR_GENERIC + (data.response || UI_MESSAGES.ERROR_UNKNOWN));
            }

        } catch (error) {
            console.error('Chat Error:', error);
            const thinkingEl = document.getElementById(thinkingId);
            if (thinkingEl) thinkingEl.remove();
            this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.ERROR_CONNECTION);
        }
    }

    showConfirmationModal(data, originalMessage, modelId) {
        // Remove existing modal if any
        const existingModal = document.getElementById('confirmation-modal');
        if (existingModal) existingModal.remove();

        const modalOverlay = document.createElement('div');
        modalOverlay.id = 'confirmation-modal';
        modalOverlay.style.position = 'fixed';
        modalOverlay.style.top = '0';
        modalOverlay.style.left = '0';
        modalOverlay.style.width = '100%';
        modalOverlay.style.height = '100%';
        modalOverlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
        modalOverlay.style.display = 'flex';
        modalOverlay.style.justifyContent = 'center';
        modalOverlay.style.alignItems = 'center';
        modalOverlay.style.zIndex = '1000';

        const modalContent = document.createElement('div');
        modalContent.style.backgroundColor = 'white';
        modalContent.style.padding = '20px';
        modalContent.style.borderRadius = '8px';
        modalContent.style.maxWidth = '80%';
        modalContent.style.maxHeight = '80%';
        modalContent.style.overflow = 'auto';
        modalContent.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';

        const title = document.createElement('h3');
        title.textContent = '⚠️ Confirmar Envío de Datos';
        title.style.marginTop = '0';
        title.style.color = '#d32f2f';

        const message = document.createElement('p');
        message.textContent = `Se han encontrado ${data.total_rows} registros. ¿Deseas enviarlos a la IA para su análisis?`;

        const previewTitle = document.createElement('h4');
        previewTitle.textContent = 'Vista Previa (Primeros 5 registros):';
        previewTitle.style.marginTop = '15px';

        const pre = document.createElement('pre');
        pre.style.backgroundColor = '#f5f5f5';
        pre.style.padding = '10px';
        pre.style.borderRadius = '4px';
        pre.style.overflowX = 'auto';
        pre.style.fontSize = '12px';
        pre.textContent = JSON.stringify(data.data_preview, null, 2);

        const buttonContainer = document.createElement('div');
        buttonContainer.style.display = 'flex';
        buttonContainer.style.justifyContent = 'flex-end';
        buttonContainer.style.gap = '10px';
        buttonContainer.style.marginTop = '20px';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancelar';
        cancelBtn.style.padding = '8px 16px';
        cancelBtn.style.border = '1px solid #ccc';
        cancelBtn.style.borderRadius = '4px';
        cancelBtn.style.backgroundColor = 'white';
        cancelBtn.style.cursor = 'pointer';
        cancelBtn.onclick = () => {
            modalOverlay.remove();
            this.appendMessage(CHAT_ROLES.AI, "❌ Envío de datos cancelado por el usuario.");
        };

        const confirmBtn = document.createElement('button');
        confirmBtn.textContent = 'Confirmar y Analizar';
        confirmBtn.style.padding = '8px 16px';
        confirmBtn.style.border = 'none';
        confirmBtn.style.borderRadius = '4px';
        confirmBtn.style.backgroundColor = '#1976d2';
        confirmBtn.style.color = 'white';
        confirmBtn.style.cursor = 'pointer';
        confirmBtn.onclick = () => {
            modalOverlay.remove();
            this.confirmAndSend(originalMessage, modelId);
        };

        buttonContainer.appendChild(cancelBtn);
        buttonContainer.appendChild(confirmBtn);

        modalContent.appendChild(title);
        modalContent.appendChild(message);
        modalContent.appendChild(previewTitle);
        modalContent.appendChild(pre);
        modalContent.appendChild(buttonContainer);
        modalOverlay.appendChild(modalContent);

        document.body.appendChild(modalOverlay);
    }

    async confirmAndSend(message, modelId) {
        const thinkingId = 'thinking-confirm-' + Date.now();
        this.appendMessage(CHAT_ROLES.AI, "✅ Datos confirmados. Analizando...", thinkingId);

        try {
            const dbParams = {
                host: DB_CONFIG.HOST,
                port: DB_CONFIG.PORT,
                database: DB_CONFIG.DATABASE,
                username: DB_CONFIG.USERNAME,
                password: DB_CONFIG.PASSWORD,
                confirm_data_sending: true // FLAG CRITICA
            };

            const response = await fetch(`${this.apiBase}/send`, {
                method: HTTP_METHODS.POST,
                headers: { 'Content-Type': API.HEADERS.CONTENT_TYPE },
                body: JSON.stringify({
                    message: message,
                    db_params: dbParams,
                    model_id: modelId,
                    conversation_history: this.conversationHistory,
                    confirm_data_sending: true
                })
            });

            const data = await response.json();

            const thinkingEl = document.getElementById(thinkingId);
            if (thinkingEl) thinkingEl.remove();

            if (data.success) {
                this.appendMessage(CHAT_ROLES.AI, data.response);
                this.conversationHistory.push({ role: 'assistant', content: data.response });
            } else {
                this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.ERROR_GENERIC + (data.response || UI_MESSAGES.ERROR_UNKNOWN));
            }
        } catch (error) {
            console.error('Confirmation Error:', error);
            const thinkingEl = document.getElementById(thinkingId);
            if (thinkingEl) thinkingEl.remove();
            this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.ERROR_CONNECTION);
        }
    }

    appendMessage(role, text, id = null) {
        const messagesArea = document.getElementById('chat-messages');
        if (!messagesArea) return;

        const msgDiv = document.createElement('div');
        if (id) msgDiv.id = id;
        msgDiv.className = `message ${role}`;
        msgDiv.style.marginBottom = '10px';
        msgDiv.style.padding = '10px';
        msgDiv.style.borderRadius = '8px';
        msgDiv.style.maxWidth = '80%';

        if (role === 'user') {
            msgDiv.style.backgroundColor = '#e3f2fd';
            msgDiv.style.marginLeft = 'auto';
            msgDiv.style.textAlign = 'right';
        } else {
            msgDiv.style.backgroundColor = '#f5f5f5';
            msgDiv.style.marginRight = 'auto';
        }

        msgDiv.textContent = text;
        messagesArea.appendChild(msgDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }
}
