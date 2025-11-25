import { API, DB_CONFIG, UI_MESSAGES, CHAT_ROLES, UI_STYLES, EVENTS, DOM_SELECTORS, HTTP_METHODS } from '../core/constants.js';

export class ChatModule {
    constructor() {
        this.apiBase = API.ENDPOINTS.CHAT;
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
                    model_id: selectedModel
                })
            });

            const data = await response.json();

            const thinkingEl = document.getElementById(thinkingId);
            if (thinkingEl) thinkingEl.remove();

            if (data.success) {
                this.appendMessage(CHAT_ROLES.AI, data.response);
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
