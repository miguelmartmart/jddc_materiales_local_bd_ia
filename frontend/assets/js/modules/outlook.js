export class OutlookModule {
    constructor() {
        this.apiBase = '/api/outlook';
        this.emails = [];
        this.config = { configured: false, email: null };
        this.pollingInterval = null;
        this.lastEmailId = null;
        this.currentSource = null; // 'outlook' | 'gmail' | null
    }

    init() {
        this.checkConfig();
        this.setupEventListeners();
        this.setupNotifications();
    }

    setupEventListeners() {
        const btnFetch = document.getElementById('btn-fetch-emails');
        if (btnFetch) {
            btnFetch.addEventListener('click', () => this.fetchEmails());
        }

        const btnNotify = document.getElementById('btn-enable-notifications');
        if (btnNotify) {
            btnNotify.addEventListener('click', () => this.requestNotificationPermission());
        }

        const btnAnalyze = document.getElementById('btn-analyze-emails');
        if (btnAnalyze) {
            btnAnalyze.addEventListener('click', () => this.analyzeEmails());
        }

        const btnCloseAnalysis = document.getElementById('close-analysis');
        if (btnCloseAnalysis) {
            btnCloseAnalysis.addEventListener('click', () => {
                document.getElementById('analysis-panel').style.display = 'none';
            });
        }
    }

    updateStatusBadge(status, source) {
        const badge = document.getElementById('connection-status');
        if (!badge) return;

        badge.className = 'status-badge'; // reset

        if (status === 'connected') {
            if (source && source.includes('gmail')) {
                badge.classList.add('gmail');
                badge.innerHTML = '🔴 Conectado (Gmail)';
            } else {
                badge.classList.add('outlook');
                badge.innerHTML = '🔵 Conectado (Outlook)';
            }
        } else if (status === 'error') {
            badge.classList.add('disconnected');
            badge.innerHTML = '❌ Error de Conexión';
        } else {
            badge.classList.add('disconnected');
            badge.innerHTML = '⚪ Desconectado';
        }
    }

    updateLastUpdated() {
        const el = document.getElementById('last-updated');
        if (el) {
            const time = new Date().toLocaleTimeString();
            el.textContent = `Actualizado: ${time}`;
        }
    }

    async checkConfig() {
        try {
            const response = await fetch(`${this.apiBase}/config-status`);
            this.config = await response.json();

            const configAlert = document.getElementById('config-alert');
            const manualForm = document.getElementById('manual-login-form');

            if (this.config.configured) {
                // Configured via Backend
                if (configAlert) configAlert.style.display = 'block'; // Show "Configured in env" msg
                if (manualForm) manualForm.style.display = 'none'; // Hide manual inputs

                // Initial fetch
                this.fetchEmails(true);
                this.startPolling();
            } else {
                // Not configured
                if (configAlert) configAlert.style.display = 'block';
                configAlert.innerHTML = '<p>⚠️ Configure credenciales en <code>.env</code> o inicie sesión manual.</p>';
                if (manualForm) manualForm.style.display = 'flex';
            }
        } catch (e) {
            console.error("Error checking config:", e);
        }
    }

    setupNotifications() {
        if ("Notification" in window && Notification.permission === "granted") {
            const btn = document.getElementById('btn-enable-notifications');
            if (btn) btn.style.display = 'none';
        }
    }

    requestNotificationPermission() {
        if (!("Notification" in window)) {
            alert("Tu navegador no soporta notificaciones de escritorio.");
        } else {
            Notification.requestPermission().then(permission => {
                if (permission === "granted") {
                    this.setupNotifications();
                }
            });
        }
    }

    startPolling() {
        if (this.pollingInterval) clearInterval(this.pollingInterval);
        // Poll every 60 seconds
        this.pollingInterval = setInterval(async () => {
            await this.checkNewEmails();
        }, 60000);
    }

    async checkNewEmails() {
        try {
            const response = await fetch(`${this.apiBase}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ limit: 1 }) // Just check latest
            });
            const data = await response.json();

            if (data.success && data.messages.length > 0) {
                const latest = data.messages[0];

                // Update badge if provided
                if (data.source) this.updateStatusBadge('connected', data.source);
                this.updateLastUpdated();

                // Notification logic
                if (this.lastEmailId && latest.id !== this.lastEmailId) {
                    this.sendNotification(latest);

                    // Optimization: Prepend locally instead of re-fetching
                    // This avoids double-connection issues with IMAP servers
                    this.emails.unshift(latest);
                    this.renderEmails();

                    // Update status just in case
                    if (data.source) this.updateStatusBadge('connected', data.source);
                    this.updateLastUpdated();
                }
                this.lastEmailId = latest.id;
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }

    sendNotification(email) {
        if (Notification.permission === "granted") {
            const n = new Notification("Nuevo Correo DEVIA", {
                body: `De: ${email.sender}\nAsunto: ${email.subject}`,
                icon: '/assets/favicon.ico'
            });
            n.onclick = () => {
                window.focus();
                document.querySelector('[data-view="outlook"]').click();
            };
        }
    }

    async fetchEmails(isAuto = false) {
        let email = null;
        let password = null;

        if (!this.config.configured) {
            email = document.getElementById('outlook-email').value;
            password = document.getElementById('outlook-password').value;

            if (!email || !password) {
                if (!isAuto) alert('Por favor introduce credenciales.');
                return;
            }
        }

        const btnFetch = document.getElementById('btn-fetch-emails');
        if (btnFetch) {
            btnFetch.disabled = true;
            btnFetch.textContent = '⏳ Sincronizando...';
        }

        try {
            const payload = { limit: 10 };
            if (email) payload.email = email;
            if (password) payload.password = password;

            const response = await fetch(`${this.apiBase}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Error en la petición');
            }

            this.emails = data.messages;
            this.currentSource = data.source; // Store source for rendering

            if (this.emails.length > 0) {
                this.lastEmailId = this.emails[0].id;
            }

            this.updateStatusBadge('connected', data.source);
            this.updateLastUpdated();
            this.renderEmails();

        } catch (error) {
            console.error('Error:', error);
            this.updateStatusBadge('error');
            if (!isAuto) alert('Error: ' + error.message);
        } finally {
            if (btnFetch) {
                btnFetch.disabled = false;
                btnFetch.textContent = '🔄 Sincronizar Ahora';
            }
        }
    }

    renderEmails() {
        const container = document.getElementById('email-list');
        if (!container) return;

        container.innerHTML = '';

        if (this.emails.length === 0) {
            container.innerHTML = '<div class="no-data" style="text-align: center; padding: 20px; color: #666;">No hay correos recientes.</div>';
            return;
        }

        const sourceClass = (this.currentSource && this.currentSource.includes('gmail')) ? 'source-gmail' : 'source-outlook';

        this.emails.forEach(email => {
            const el = document.createElement('div');
            el.className = `email-item ${sourceClass}`;
            el.innerHTML = `
                <div class="email-header" style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <strong style="color: #333;">${this.escapeHtml(email.subject || '(Sin Asunto)')}</strong>
                    <span class="email-date" style="font-size: 0.85em; color: #888;">${this.formatDate(email.date)}</span>
                </div>
                <div class="email-meta" style="font-size: 0.9em; color: #555; margin-bottom: 8px;">De: ${this.escapeHtml(email.sender || 'Desconocido')}</div>
                <div class="email-body" style="color: #444; font-size: 0.95em; line-height: 1.4;">${this.escapeHtml(email.body)}</div>
            `;
            container.appendChild(el);
        });
    }

    async analyzeEmails() {
        const panel = document.getElementById('analysis-panel');
        const resultsContainer = document.getElementById('analysis-results');
        if (!panel || !resultsContainer) return;

        panel.style.display = 'block';
        resultsContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;">🤖 Analizando correos con IA... Esto puede tardar unos segundos.</div>';

        try {
            const email = this.config.email || document.getElementById('outlook-email').value;
            const password = this.config.configured ? null : document.getElementById('outlook-password').value;

            const limitInput = document.getElementById('analyze-limit');
            const limit = limitInput ? parseInt(limitInput.value) : 5;

            const payload = { limit: limit };
            if (email && !this.config.configured) payload.email = email;
            if (password && !this.config.configured) payload.password = password;

            const response = await fetch(`${this.apiBase}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (!data.success) throw new Error(data.detail || "Error en análisis");

            this.renderAnalysis(data);

        } catch (e) {
            console.error(e);
            resultsContainer.innerHTML = `<div style="color: #d32f2f; padding: 10px; background: #ffebee; border-radius: 4px;">Error: ${this.escapeHtml(e.message)}</div>`;
        }
    }

    renderAnalysis(data) {
        // Render Stats
        if (data.stats) {
            document.getElementById('stat-total').textContent = data.stats.total_analyzed;
            document.getElementById('stat-unread').textContent = data.stats.unread_total;
            document.getElementById('stat-attachments').textContent = data.stats.emails_with_attachments;

            // Render Timeline
            const timelineEl = document.getElementById('stat-timeline');
            if (timelineEl) {
                timelineEl.innerHTML = data.stats.timeline.map(t =>
                    `<span style="display: inline-block; background: #e0f2f1; color: #00695c; padding: 2px 8px; border-radius: 12px; margin: 2px; font-size: 0.85em;">${t.date}: <b>${t.count}</b></span>`
                ).join(' ');
            }
        }

        // Render AI Cards
        const container = document.getElementById('analysis-results');
        container.innerHTML = '';

        if (!data.analysis || data.analysis.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #666;">No se obtuvieron resultados de análisis.</div>';
            return;
        }

        data.analysis.forEach(item => {
            const ai = item.ai_data;
            const el = document.createElement('div');
            el.style.cssText = "background: white; border: 1px solid #eee; border-radius: 6px; padding: 15px; border-left: 4px solid #673ab7; box-shadow: 0 2px 4px rgba(0,0,0,0.05);";

            let badges = `<span style="background: #ede7f6; color: #512da8; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">${this.escapeHtml(ai.category || 'General')}</span>`;
            if (ai.priority === 'Alta') badges += ` <span style="background: #ffebee; color: #c62828; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold;">⚡ ALTA</span>`;

            el.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                     <strong style="color: #333;">${this.escapeHtml(item.subject || '(Sin Asunto)')}</strong>
                     <small style="color: #888;">${this.formatDate(item.date)}</small>
                </div>
                <div style="font-size: 0.85em; color: #666; margin-bottom: 8px;">De: ${this.escapeHtml(item.sender)}</div>
                <div style="margin-bottom: 8px;">${badges}</div>
                <div style="font-style: italic; color: #444; background: #fafafa; padding: 10px; border-radius: 4px; border: 1px dashed #ddd; margin-bottom: 8px;">
                    🤖 "${this.escapeHtml(ai.summary)}"
                </div>
                ${ai.attachments_analysis && ai.attachments_analysis !== 'Sin adjuntos' && ai.attachments_analysis !== 'None' ?
                    `<div style="margin-top: 8px; font-size: 0.85em; color: #0277bd; background: #e1f5fe; padding: 5px; border-radius: 4px;">📎 <b>Adjuntos:</b> ${this.escapeHtml(ai.attachments_analysis)}</div>` : ''}
            `;
            container.appendChild(el);
        });
    }

    escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    formatDate(dateStr) {
        try {
            return new Date(dateStr).toLocaleString();
        } catch (e) {
            return dateStr;
        }
    }
}
