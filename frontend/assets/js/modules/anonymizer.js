import { api } from '../core/api.js';
import { showNotification, copyToClipboard } from '../core/utils.js';

export class AnonymizerModule {
    constructor() {
        this.viewId = 'anonymizer';

        // UI Elements
        this.configPanel = document.getElementById('anonymizer-config-panel');
        this.inputConfigUrl = document.getElementById('anon-config-url');
        this.inputConfigModel = document.getElementById('anon-config-model');
        this.inputConfigPrompt = document.getElementById('anon-config-prompt');

        // Integrations
        this.chkEnableChat = document.getElementById('chk-enable-chat');
        this.chkEnableOutlook = document.getElementById('chk-enable-outlook');
        this.chkEnableDatabase = document.getElementById('chk-enable-database');

        // Granular Controls
        this.chkAnonIds = document.getElementById('chk-anon-ids');
        this.chkAnonEmails = document.getElementById('chk-anon-emails');
        this.chkAnonPhones = document.getElementById('chk-anon-phones');
        this.chkAnonNames = document.getElementById('chk-anon-names');
        this.chkPreserveProducts = document.getElementById('chk-preserve-products');

        this.btnSaveConfig = document.getElementById('btn-anon-save-config');
        this.inputText = document.getElementById('anon-input-text');
        this.outputText = document.getElementById('anon-output-text');
        this.btnAnonymize = document.getElementById('btn-anonymize');
        this.btnCopy = document.getElementById('btn-anon-copy');
        this.btnRefreshHistory = document.getElementById('btn-anon-refresh-history');
        this.historyList = document.getElementById('anon-history-list');
        this.btnToggleConfig = document.getElementById('btn-toggle-anon-config');
    }

    async init() {
        this.bindEvents();
        await this.loadConfig();
        this.loadHistory();
    }

    bindEvents() {
        this.btnSaveConfig.addEventListener('click', () => this.saveConfig());
        this.btnAnonymize.addEventListener('click', () => this.anonymize());
        this.btnCopy.addEventListener('click', () => this.copyResult());
        this.btnRefreshHistory.addEventListener('click', () => this.loadHistory());
        this.btnToggleConfig.addEventListener('click', () => {
            const isHidden = this.configPanel.style.display === 'none';
            this.configPanel.style.display = isHidden ? 'block' : 'none';
        });
    }

    async loadConfig() {
        try {
            const config = await api.get('/anonymizer/config');
            this.inputConfigUrl.value = config.api_url;
            this.inputConfigModel.value = config.model;
            this.inputConfigPrompt.value = config.system_prompt;

            if (this.chkEnableChat) this.chkEnableChat.checked = config.enable_chat;
            if (this.chkEnableOutlook) this.chkEnableOutlook.checked = config.enable_outlook;
            if (this.chkEnableDatabase) this.chkEnableDatabase.checked = config.enable_database;

            if (this.chkAnonIds) this.chkAnonIds.checked = config.anonymize_ids !== false;
            if (this.chkAnonEmails) this.chkAnonEmails.checked = config.anonymize_emails !== false;
            if (this.chkAnonPhones) this.chkAnonPhones.checked = config.anonymize_phones !== false;
            if (this.chkAnonNames) this.chkAnonNames.checked = config.anonymize_names !== false;
            if (this.chkPreserveProducts) this.chkPreserveProducts.checked = config.preserve_products !== false;

        } catch (error) {
            console.error("Failed to load config:", error);
            showNotification("Error cargando configuración", "error");
        }
    }

    async saveConfig() {
        const config = {
            api_url: this.inputConfigUrl.value,
            model: this.inputConfigModel.value,
            system_prompt: this.inputConfigPrompt.value,
            enable_chat: this.chkEnableChat.checked,
            enable_outlook: this.chkEnableOutlook.checked,
            enable_database: this.chkEnableDatabase.checked,
            anonymize_ids: this.chkAnonIds.checked,
            anonymize_emails: this.chkAnonEmails.checked,
            anonymize_phones: this.chkAnonPhones.checked,
            anonymize_names: this.chkAnonNames.checked,
            preserve_products: this.chkPreserveProducts.checked
        };
        try {
            await api.post('/anonymizer/config', config);
            showNotification("Configuración guardada", "success");
            this.configPanel.style.display = 'none';
        } catch (error) {
            console.error("Failed to save config:", error);
            showNotification("Error guardando configuración", "error");
        }
    }

    async anonymize() {
        const text = this.inputText.value.trim();
        if (!text) {
            showNotification("Ingresa texto para anonimizar", "warning");
            return;
        }

        this.btnAnonymize.disabled = true;
        this.btnAnonymize.innerHTML = "⏳ Procesando...";
        this.outputText.value = "";

        try {
            const response = await api.post('/anonymizer/anonymize', { text: text });
            this.outputText.value = response.anonymized;
            showNotification("Anonimización completada", "success");
            this.loadHistory(); // Refresh history
        } catch (error) {
            console.error("Anonymization failed:", error);
            showNotification("Error al anonimizar: " + error.message, "error");
            this.outputText.value = "Error: " + error.message;
        } finally {
            this.btnAnonymize.disabled = false;
            this.btnAnonymize.innerHTML = "🛡️ Anonimizar ➡️";
        }
    }

    async copyResult() {
        const text = this.outputText.value;
        if (!text) return;

        // Use the util function if available, else simple fallback
        import('../core/utils.js').then(async utils => {
            if (utils.copyToClipboard) {
                await utils.copyToClipboard(text);
                showNotification("Copiado al portapapeles", "success");
            } else {
                navigator.clipboard.writeText(text);
                showNotification("Copiado", "success");
            }
        }).catch(() => {
            navigator.clipboard.writeText(text);
            showNotification("Copiado", "success");
        });
    }

    async loadHistory() {
        try {
            this.historyList.innerHTML = '<div style="text-align:center; padding:10px;">Cargando...</div>';
            const history = await api.get('/anonymizer/history?limit=20');
            this.renderHistory(history);
        } catch (error) {
            console.error("Failed to load history:", error);
            this.historyList.innerHTML = '<div style="color:red; text-align:center;">Error cargando historial</div>';
        }
    }

    renderHistory(items) {
        this.historyList.innerHTML = '';
        if (!items || items.length === 0) {
            this.historyList.innerHTML = '<div style="padding:15px; color:#999; text-align:center;">Sin historial reciente</div>';
            return;
        }

        items.forEach(session => {
            const itemEl = document.createElement('div');
            itemEl.style.padding = '10px 15px';
            itemEl.style.borderBottom = '1px solid #eee';
            itemEl.style.cursor = 'pointer';
            itemEl.style.transition = 'background 0.2s';

            itemEl.onmouseover = () => itemEl.style.background = '#f9f9f9';
            itemEl.onmouseout = () => itemEl.style.background = 'white';

            // Format Date (Force UTC interpretation if "Z" missing)
            let dateStr = session.created_at;
            if (dateStr && !dateStr.endsWith('Z') && !dateStr.includes('+')) {
                dateStr += 'Z';
            }
            const date = new Date(dateStr).toLocaleString('es-ES');

            // Get content preview (from first user message)
            const firstMsg = session.messages.find(m => m.role === 'user');
            const preview = firstMsg ? (firstMsg.content.substring(0, 50) + '...') : session.title;

            // Model used info
            const modelName = session.model_id || session.model || 'Unknown';

            itemEl.innerHTML = `
                <div style="font-size: 0.8em; color: #888; display:flex; justify-content:space-between;">
                    <span>${date}</span>
                    <span style="background:#eee; padding:2px 5px; borderRadius:4px;">${modelName}</span>
                </div>
                <div style="font-weight: 500; margin-top: 5px; font-size: 0.9em; color: #333;">${preview}</div>
            `;

            itemEl.addEventListener('click', () => {
                this.openHistoryModal(session);
            });

            this.historyList.appendChild(itemEl);
        });
    }

    openHistoryModal(session) {
        const modal = document.getElementById('anon-history-modal');
        const modelLabel = document.getElementById('anon-modal-model');
        const dateLabel = document.getElementById('anon-modal-date');
        const messagesContainer = document.getElementById('anon-modal-messages');

        // Headers
        modelLabel.textContent = `Modelo: ${session.model_id || session.model || 'Desconocido'}`;
        let dateStr = session.created_at;
        if (dateStr && !dateStr.endsWith('Z') && !dateStr.includes('+')) dateStr += 'Z';
        dateLabel.textContent = `Fecha: ${new Date(dateStr).toLocaleString('es-ES')}`;

        // Messages
        messagesContainer.innerHTML = '';

        session.messages.forEach((msg, index) => {
            const msgDiv = document.createElement('div');
            msgDiv.style.display = 'flex';
            msgDiv.style.flexDirection = 'column';
            msgDiv.style.alignItems = msg.role === 'user' ? 'flex-end' : 'flex-start';

            let bg = msg.role === 'user' ? '#eef2ff' : '#f0fdf4';
            let border = msg.role === 'user' ? '#c7d2fe' : '#bbf7d0';
            let label = msg.role === 'user' ? '👤 Usuario' : '🛡️ Anonimizador (AI)';
            if (msg.role === 'system') {
                bg = '#fef2f2';
                border = '#fecaca';
                label = '⚙️ Configuración del Sistema (Prompt)';
            }

            msgDiv.innerHTML = `
                <div style="font-size: 0.8em; color: #666; margin-bottom: 3px;">${label}</div>
                <div style="background: ${bg}; padding: 10px 15px; border-radius: 8px; border: 1px solid ${border}; max-width: 90%; white-space: pre-wrap;">${msg.content}</div>
                <div style="font-size: 0.75em; color: #999; margin-top: 2px;">Mensaje #${index + 1}</div>
             `;

            messagesContainer.appendChild(msgDiv);
        });

        modal.showModal();
    }
}
