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
            el.id = `msg-${email.id}`; // Add ID for linking

            // Body Preview Logic
            const bodyContent = email.body ? this.escapeHtml(email.body) : '<span style="color:#999; font-style:italic;">(Contenido no textual o vacío)</span>';
            const toggleId = `list-body-${email.id}`;

            el.innerHTML = `
                <div class="email-header" style="display: flex; justify-content: space-between; margin-bottom: 5px; cursor:pointer;" onclick="document.getElementById('${toggleId}').style.display = document.getElementById('${toggleId}').style.display === 'none' ? 'block' : 'none'">
                    <div>
                        <span style="font-size:0.8em; color:#999; margin-right:5px;">▼</span>
                        <strong style="color: #333;">${this.escapeHtml(email.subject || '(Sin Asunto)')}</strong>
                    </div>
                    <span class="email-date" style="font-size: 0.85em; color: #888;">${this.formatDate(email.date)}</span>
                </div>
                <div class="email-meta" style="font-size: 0.9em; color: #555; margin-bottom: 8px;">De: ${this.escapeHtml(email.sender || 'Desconocido')}</div>
                
                <div id="${toggleId}" class="email-body" style="display:none; color: #444; font-size: 0.95em; line-height: 1.4; border-top:1px solid #eee; margin-top:5px; padding-top:10px; white-space: pre-wrap;">
                    ${bodyContent}
                </div>
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
            const limit = limitInput ? parseInt(limitInput.value) : 30;

            // Get Filters
            const unreadOnly = document.getElementById('analyze-unread-only')?.checked || false;
            const dateFilter = document.getElementById('analyze-date-filter')?.value || 'all';

            const payload = {
                limit: limit,
                unread_only: unreadOnly,
                date_filter: dateFilter
            };

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
        let items = [];
        // Stats
        if (data.stats) {
            this.setText('stat-total', data.stats.total_analyzed);
            this.setText('stat-unread', data.stats.unread_total);
            this.setText('stat-attachments', data.stats.emails_with_attachments);
            this.setText('stat-today', data.stats.received_today || 0);

            // Calculate Read Since Monday
            let readSinceMonday = 0;
            items = data.stats.daily_breakdown || data.stats.timeline || [];

            // Helper to get day index (0=Sun, 1=Mon...)
            const today = new Date().getDay();
            // We want "Since Monday". If today is Monday(1), standard logic.
            // Loop through items. If item string contains "Lunes", "Martes" etc.

            if (Array.isArray(items) && items.length > 0) {
                items.forEach(dayStr => {
                    // Check if it's the new object format
                    let countsStr = "";
                    if (typeof dayStr === 'object') {
                        countsStr = dayStr.counts; // e.g., "3 sin leer, 5 leídos"
                    } else {
                        return; // Skip old format for now or parse regex
                    }

                    // Parse "X leídos"
                    // Spanish: "0 sin leer, 3 leídos"
                    const match = countsStr.match(/(\d+)\s+leídos/);
                    if (match) {
                        readSinceMonday += parseInt(match[1]);
                    }
                });
            }

            const readStatEl = document.getElementById('read-since-monday');
            if (readStatEl) {
                readStatEl.textContent = `📖 Leídos desde el Lunes: ${readSinceMonday}`;
            }
        }

        // Timeline Rendering
        const timelineList = document.getElementById('timeline-list');
        if (timelineList) {
            timelineList.innerHTML = '';

            // 1. Render Global Daily Stats Table (if available)
            if (data.global_daily && Array.isArray(data.global_daily)) {
                const tableLi = document.createElement('li');
                tableLi.style.marginBottom = '15px';
                tableLi.style.listStyle = 'none';

                let rows = data.global_daily.map(d => `
                        <tr>
                            <td style="padding:5px; border-bottom:1px solid #eee;">${d.label}</td>
                            <td style="padding:5px; border-bottom:1px solid #eee; text-align:center;">${d.total}</td>
                            <td style="padding:5px; border-bottom:1px solid #eee; text-align:center; color:${d.unread > 0 ? 'red' : '#888'}; font-weight:${d.unread > 0 ? 'bold' : 'normal'};">${d.unread}</td>
                        </tr>
                    `).join('');

                tableLi.innerHTML = `
                        <div style="font-weight:600; margin-bottom:5px; font-size:0.9em; color:#333;">📊 Resumen Global (Todo el buzón):</div>
                        <div style="border:1px solid #e0e0e0; border-radius:6px; overflow:hidden;">
                            <table style="width:100%; border-collapse:collapse; font-size:0.85em;">
                                <tr style="background:#f5f5f5;">
                                    <th style="padding:5px; text-align:left; color:#666;">Fecha</th>
                                    <th style="padding:5px; text-align:center; color:#666;">Total</th>
                                    <th style="padding:5px; text-align:center; color:#666;">No Leídos</th>
                                </tr>
                                ${rows}
                            </table>
                        </div>
                    `;
                timelineList.appendChild(tableLi);
            }

            // 2. Render "Detailed Analysis Breakdown" (Tree View) - HIERARCHICAL
            const analysisData = data.analysis || [];

            const breakdownLi = document.createElement('li');
            breakdownLi.style.marginBottom = '15px';
            breakdownLi.style.listStyle = 'none';

            // Data Structure: Date -> Status -> Category -> Subcategory
            const hierarchy = {};

            analysisData.forEach(item => {
                // 1. Normalize Date (simple string matching)
                // The backend returns various formats, but usually fairly consistent. 
                // We'll rely on the string provided.
                const dateKey = item.date ? item.date.split(',')[0].trim() : "Fecha Desconocida";

                // 2. Status
                const statusKey = item.is_read ? "Leídos" : "No Leídos";

                // 3. Category/Subcategory
                const ai = item.ai_data || {};
                const cat = ai.category || 'Otros';
                const sub = ai.subcategory || 'General';
                const prio = ai.priority || 'Baja';

                // Initialize path
                if (!hierarchy[dateKey]) hierarchy[dateKey] = { total: 0, statuses: {} };
                hierarchy[dateKey].total++;

                if (!hierarchy[dateKey].statuses[statusKey]) hierarchy[dateKey].statuses[statusKey] = { total: 0, cats: {} };
                hierarchy[dateKey].statuses[statusKey].total++;

                const statusNode = hierarchy[dateKey].statuses[statusKey];

                if (!statusNode.cats[cat]) statusNode.cats[cat] = { total: 0, subs: {}, priorities: { 'Alta': 0, 'Media': 0, 'Baja': 0 } };
                statusNode.cats[cat].total++;

                if (!statusNode.cats[cat].subs[sub]) statusNode.cats[cat].subs[sub] = { count: 0, items: [] };
                statusNode.cats[cat].subs[sub].count++;
                statusNode.cats[cat].subs[sub].items.push({
                    subject: item.subject,
                    sender: item.sender
                });

                // Priority Count
                if (statusNode.cats[cat].priorities[prio] !== undefined) {
                    statusNode.cats[cat].priorities[prio]++;
                }
            });

            // Helper for Search URL
            const isGmail = (data.source && data.source.includes('gmail'));
            const getSearchLink = (term) => {
                const encoded = encodeURIComponent(term);
                return isGmail
                    ? `https://mail.google.com/mail/u/0/#search/${encoded}`
                    : `https://outlook.live.com/mail/0/options/mail/search/inbox?q=${encoded}`;
            };

            // Build HTML
            let breakdownHtml = '';

            // Iterate Dates
            for (const [date, dateInfo] of Object.entries(hierarchy)) {
                let statusHtml = '';

                // Iterate Statuses
                for (const [status, statusInfo] of Object.entries(dateInfo.statuses)) {
                    let catHtml = '';

                    // Iterate Categories
                    for (const [cat, catInfo] of Object.entries(statusInfo.cats)) {
                        let subHtml = '';
                        // Subcategories
                        for (const [sub, subInfo] of Object.entries(catInfo.subs)) {
                            // Subcategory Items List
                            const itemsHtml = subInfo.items.map(i =>
                                `<li style="margin-bottom:2px;">
                                    <span style="font-weight:500;">${this.escapeHtml(i.subject)}</span> 
                                    <span style="color:#888; font-size:0.9em;">(${this.escapeHtml(i.sender)})</span>
                                 </li>`
                            ).join('');

                            const searchUrl = getSearchLink(sub);
                            const toggleId = `sub-toggle-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

                            subHtml += `
                                <div style="padding-left:15px; font-size:0.85em; color:#666; margin-top:4px; display:flex; align-items:flex-start; flex-direction:column;">
                                    <div style="display:flex; align-items:center; gap:5px;">
                                        <span>• ${this.escapeHtml(sub)} (${subInfo.count})</span>
                                        <a href="${searchUrl}" target="_blank" title="Buscar en Web" style="text-decoration:none; cursor:pointer;">🔗</a>
                                        <span onclick="document.getElementById('${toggleId}').hidden = !document.getElementById('${toggleId}').hidden" title="Ver correos" style="cursor:pointer;">⬇️</span>
                                    </div>
                                    <ul id="${toggleId}" hidden style="margin:5px 0 0 5px; padding-left:15px; border-left:1px dashed #ccc; list-style:none;">
                                        ${itemsHtml}
                                    </ul>
                                </div>`;
                        }

                        // Priority Badges
                        let prioBadges = '';
                        if (catInfo.priorities['Alta'] > 0) prioBadges += `<span style="font-size:0.7em; background:#ffebee; color:#c62828; padding:1px 4px; border-radius:3px; margin-left:4px;">Alta: ${catInfo.priorities['Alta']}</span>`;
                        if (catInfo.priorities['Media'] > 0) prioBadges += `<span style="font-size:0.7em; background:#fff3e0; color:#ef6c00; padding:1px 4px; border-radius:3px; margin-left:4px;">Media: ${catInfo.priorities['Media']}</span>`;

                        catHtml += `
                            <details style="margin-left:10px; margin-bottom:4px;">
                                <summary style="cursor:pointer; font-size:0.9em; color:#1565c0;">${this.escapeHtml(cat)} (${catInfo.total}) ${prioBadges}</summary>
                                <div style="margin-left:10px; border-left:2px solid #eee;">${subHtml}</div>
                            </details>
                        `;
                    }

                    const statusColor = status === "No Leídos" ? "#d32f2f" : "#388e3c";
                    const statusIcon = status === "No Leídos" ? "🔴" : "🟢";

                    statusHtml += `
                        <div style="margin-bottom:8px; margin-left:5px;">
                            <div style="font-weight:600; font-size:0.9em; color:${statusColor}; margin-bottom:3px;">
                                ${statusIcon} ${status} (${statusInfo.total})
                            </div>
                            <div style="margin-left:5px;">${catHtml}</div>
                        </div>
                    `;
                }

                breakdownHtml += `
                    <div style="background:white; border:1px solid #e0e0e0; border-radius:6px; padding:8px; margin-bottom:10px;">
                        <div style="font-weight:bold; color:#333; border-bottom:1px solid #eee; padding-bottom:4px; margin-bottom:6px;">📅 ${this.escapeHtml(date)} (${dateInfo.total})</div>
                        ${statusHtml}
                    </div>
                `;
            }

            if (analysisData.length === 0) {
                breakdownHtml = '<div style="font-size:0.8em; color:#999; font-style:italic; padding:10px;">Sin datos para desglosar.</div>';
            }

            breakdownLi.innerHTML = `
                <div style="background:#f0f7ff; border:1px solid #bbdefb; border-radius:6px; padding:10px;">
                    <div style="font-weight:600; font-size:0.9em; color:#0d47a1; margin-bottom:8px;">🧐 Desglose Avanzado (${analysisData.length}):</div>
                    ${breakdownHtml}
                </div>
            `;
            timelineList.appendChild(breakdownLi);

            if (Array.isArray(items)) {
                items.forEach(day => {
                    const li = document.createElement('li');
                    li.style.marginBottom = '10px';
                    li.style.borderBottom = '1px solid #eee';
                    li.style.paddingBottom = '5px';

                    if (typeof day === 'object') {
                        const dateStr = day.date || 'Fecha desconocida';
                        const counts = day.counts || (day.count ? `${day.count} correos` : '');
                        const senders = day.senders || '';

                        li.innerHTML = `
                                <div style="font-weight:bold; color:#1565c0;">${this.escapeHtml(dateStr)}</div>
                                <div style="font-size:0.9em; margin-bottom:2px;">${this.escapeHtml(counts)}</div>
                                ${senders ? `<div style="font-size:0.85em; color:#666;">📝 ${this.escapeHtml(senders)}</div>` : ''}
                            `;
                    } else {
                        li.textContent = day;
                    }
                    timelineList.appendChild(li);
                });
            }
        }


        // Render AI Cards
        const container = document.getElementById('analysis-results');
        if (!container) return;

        container.innerHTML = '';

        if (!data.analysis || data.analysis.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #666;">No se obtuvieron resultados de análisis (o el filtro es muy restrictivo).</div>';
            return;
        }

        const isGmail = (data.source && data.source.includes('gmail'));

        data.analysis.forEach((item, index) => {
            const ai = item.ai_data || {};
            const el = document.createElement('div');
            el.className = 'email-ai-card';

            // Priority Color
            let borderLeftColor = '#9e9e9e';
            if (ai.priority === 'Alta') borderLeftColor = '#f44336';
            else if (ai.priority === 'Media') borderLeftColor = '#ff9800';
            else if (ai.priority === 'Baja') borderLeftColor = '#4caf50';

            el.style.cssText = `background: white; border: 1px solid #eee; border-radius: 8px; padding: 15px; border-left: 5px solid ${borderLeftColor}; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; position:relative;`;

            // Badges
            let badgeColor = '#607d8b';
            const lowCat = (ai.category || '').toLowerCase();
            if (lowCat === 'trabajo') badgeColor = '#2196f3';
            else if (lowCat === 'factura') badgeColor = '#673ab7';
            else if (lowCat === 'spam') badgeColor = '#9e9e9e';
            else if (lowCat === 'personal') badgeColor = '#e91e63';
            else if (lowCat === 'notificación') badgeColor = '#ff9800';

            // Unique ID for toggle
            const toggleId = `full-body-${index}-${Date.now()}`;

            // External Search Link
            const encodedSubject = encodeURIComponent(item.subject || '');
            const externalLink = isGmail
                ? `https://mail.google.com/mail/u/0/#search/${encodedSubject}`
                : `https://outlook.live.com/mail/0/options/mail/search/inbox?q=${encodedSubject}`;

            el.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                     <strong style="color: #333; font-size: 1.05em;">${this.escapeHtml(item.subject || '(Sin Asunto)')}</strong>
                     <span style="font-size: 0.85em; color: #888;">${this.formatDate(item.date)}</span>
                </div>
                <div style="font-size: 0.9em; color: #555; margin-bottom: 8px;">De: <b>${this.escapeHtml(item.sender || 'Desconocido')}</b></div>
                
                <div style="margin-bottom: 10px; display: flex; flex-wrap: wrap; gap: 5px; align-items: center;">
                    <span style="background: ${badgeColor}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.75em; font-weight: 500;">${this.escapeHtml(ai.category || 'General')}</span>
                    ${ai.subcategory ? `<span style="background: #e0f7fa; color: #006064; padding: 3px 8px; border-radius: 12px; font-size: 0.75em; border: 1px solid #b2ebf2;">${this.escapeHtml(ai.subcategory)}</span>` : ''}
                    <span style="background: #f5f5f5; color: #666; padding: 3px 8px; border-radius: 12px; font-size: 0.75em; border: 1px solid #ddd;">${this.escapeHtml(ai.priority || 'Baja')}</span>
                    ${ai.action_needed ? `<span style="border: 1px solid #ff5722; color: #ff5722; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight: bold;">⚠️ Acción Requerida</span>` : ''}
                </div>

                <div style="font-size: 0.95em; color: #333; line-height: 1.5; background: #fafafa; padding: 12px; border-radius: 6px; border: 1px dashed #e0e0e0; margin-bottom: 15px;">
                    🤖 "${this.escapeHtml(ai.summary || 'Sin resumen')}"
                </div>

                ${item.attachments && item.attachments.length > 0 ? `
                    <div style="margin-bottom:10px; padding: 10px; background: #fff3e0; border: 1px solid #ffe0b2; border-radius: 6px;">
                        <div style="font-weight: 600; color: #e65100; margin-bottom: 8px; display: flex; align-items: center; gap: 5px;">
                            <span>📎</span>
                            <span>Adjuntos (${item.attachments.length})</span>
                        </div>
                        ${item.attachments.map((att, idx) => {
                const sizeKB = (att.size / 1024).toFixed(1);
                const fileIcon = att.content_type.includes('pdf') ? '📄' :
                    att.content_type.includes('image') ? '🖼️' :
                        att.content_type.includes('word') ? '📝' :
                            att.content_type.includes('excel') || att.content_type.includes('spreadsheet') ? '📊' :
                                att.content_type.includes('text') ? '📃' : '📎';

                return `
                                <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 8px; background: white; border: 1px solid #ffcc80; border-radius: 4px; margin-bottom: 5px; font-size: 0.85em;">
                                    <div style="display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0;">
                                        <span>${fileIcon}</span>
                                        <span style="font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${this.escapeHtml(att.filename)}">${this.escapeHtml(att.filename)}</span>
                                        <span style="color: #999; font-size: 0.9em;">(${sizeKB} KB)</span>
                                    </div>
                                    <button class="btn-analyze-attachment" 
                                            data-email-id="${item.id}"
                                            data-attachment-index="${idx}"
                                            data-filename="${this.escapeHtml(att.filename)}"
                                            style="padding: 4px 10px; background: #4caf50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8em; white-space: nowrap;">
                                        🔍 Analizar
                                    </button>
                                </div>
                            `;
            }).join('')}
                    </div>
                ` : ''}

                ${ai.attachments_analysis && ai.attachments_analysis !== 'Sin adjuntos' && ai.attachments_analysis !== 'None' ?
                    `<div style="margin-bottom:10px; font-size: 0.85em; color: #0277bd; padding: 5px; border-radius: 4px; display:flex; align-items:center; gap:5px;">
                        <span>📎</span> <span>${this.escapeHtml(ai.attachments_analysis)}</span>
                     </div>` : ''}
                
                <div class="card-actions" style="display:flex; gap:10px; border-top:1px solid #eee; padding-top:10px;">
                     <button class="btn small secondary" onclick="document.getElementById('${toggleId}').style.display = document.getElementById('${toggleId}').style.display === 'none' ? 'block' : 'none'">📜 Ver correo completo</button>
                     <button class="btn small primary" onclick="window.open('${externalLink}', '_blank')">🔗 Abrir en Web</button>
                     <button class="btn small btn-ai-reply" 
                             style="background:#f3e5f5; color:#4a148c; border:1px solid #d1c4e9;" 
                             data-context="${this.escapeHtml(ai.summary || "Responder al correo")}" 
                             data-sender="${this.escapeHtml(item.sender)}" 
                             data-link="${externalLink}">🤖 Responder con IA</button>
                </div>

                <div id="${toggleId}" style="display:none; margin-top:10px; background:#fff; border:1px solid #eee; padding:10px; font-size:0.85em; font-family:monospace; white-space:pre-wrap; max-height:200px; overflow-y:auto;">
                    ${this.escapeHtml(ai.body_preview || 'Cuerpo no disponible en resumen. Revisa la lista principal.')}
                </div>
            `;
            container.appendChild(el);
        });

        // Event Delegation for AI Reply Buttons
        if (!window.aiReplyHandlerAttached) {
            window.aiReplyHandlerAttached = true;

            document.addEventListener('click', async (e) => {
                if (e.target.classList.contains('btn-ai-reply') || e.target.closest('.btn-ai-reply')) {
                    const btn = e.target.classList.contains('btn-ai-reply') ? e.target : e.target.closest('.btn-ai-reply');
                    const context = btn.dataset.context;
                    const sender = btn.dataset.sender;
                    const link = btn.dataset.link;

                    // Create or show overlay
                    let overlay = document.getElementById('reply-overlay');
                    if (!overlay) {
                        overlay = document.createElement('div');
                        overlay.id = 'reply-overlay';
                        overlay.style.cssText = "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; display:flex; justify-content:center; align-items:center;";
                        document.body.appendChild(overlay);
                    }

                    overlay.style.display = 'flex';
                    overlay.innerHTML = `
                        <div style="background:white; padding:20px; border-radius:8px; width:90%; max-width:600px; box-shadow:0 10px 25px rgba(0,0,0,0.2);">
                            <h3 style="margin-top:0; color:#1565c0; display:flex; align-items:center; gap:10px;">
                                 🤖 Redactando respuesta para ${sender}...
                            </h3>
                            <div id="ai-reply-loading" style="color:#666; font-style:italic;">Conectando con el cerebro del sistema...</div>
                            <textarea id="ai-draft-text" style="width:100%; height:200px; margin:10px 0; padding:10px; border:1px solid #ccc; border-radius:4px; font-family:sans-serif; display:none;"></textarea>
                            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:10px;">
                                <button id="btn-cancel-reply" style="padding:8px 15px; border:none; background:#eee; cursor:pointer; border-radius:4px;">Cancelar</button>
                                <button id="btn-copy-open" disabled style="padding:8px 15px; border:none; background:#1565c0; color:white; cursor:pointer; border-radius:4px; opacity:0.5;">Copiar y Abrir Email</button>
                            </div>
                        </div>
                    `;

                    // Add event listeners
                    overlay.querySelector('#btn-cancel-reply').onclick = () => { overlay.style.display = 'none'; };

                    try {
                        const apiBase = `${window.location.protocol}//${window.location.hostname}:8001/api/outlook`;

                        const res = await fetch(`${apiBase}/reply-suggestion`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ content: context, sender: sender })
                        });
                        const json = await res.json();

                        if (json.success) {
                            const txtArea = overlay.querySelector('#ai-draft-text');
                            const loading = overlay.querySelector('#ai-reply-loading');
                            loading.style.display = 'none';
                            txtArea.style.display = 'block';
                            txtArea.value = json.reply;

                            const btnCopy = overlay.querySelector('#btn-copy-open');
                            btnCopy.textContent = '✉️ Abrir en Gmail/Outlook';
                            btnCopy.disabled = false;
                            btnCopy.style.opacity = '1';
                            btnCopy.onclick = () => {
                                // Use mailto to open default email client with pre-filled content
                                const subject = 'Re: ' + (context.substring(0, 50) || 'Su correo');
                                const mailtoLink = `mailto:${encodeURIComponent(sender)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(txtArea.value)}`;
                                window.location.href = mailtoLink;
                                overlay.style.display = 'none';
                            };
                        } else {
                            alert("Error AI: " + (json.message || 'Error desconocido'));
                            overlay.style.display = 'none';
                        }
                    } catch (e) {
                        alert("Error generando respuesta: " + e.message);
                        overlay.style.display = 'none';
                    }
                }
            });
        }

        // Event Delegation for Analyze Attachment Buttons
        if (!window.attachmentAnalyzeHandlerAttached) {
            window.attachmentAnalyzeHandlerAttached = true;

            document.addEventListener('click', async (e) => {
                if (e.target.classList.contains('btn-analyze-attachment') || e.target.closest('.btn-analyze-attachment')) {
                    const btn = e.target.classList.contains('btn-analyze-attachment') ? e.target : e.target.closest('.btn-analyze-attachment');
                    const emailId = btn.dataset.emailId;
                    const attachmentIndex = parseInt(btn.dataset.attachmentIndex);
                    const filename = btn.dataset.filename;

                    // Create or show overlay
                    let overlay = document.getElementById('attachment-analysis-overlay');
                    if (!overlay) {
                        overlay = document.createElement('div');
                        overlay.id = 'attachment-analysis-overlay';
                        overlay.style.cssText = "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; display:flex; justify-content:center; align-items:center;";
                        document.body.appendChild(overlay);
                    }

                    overlay.style.display = 'flex';
                    overlay.innerHTML = `
                        <div style="background:white; padding:20px; border-radius:8px; width:90%; max-width:700px; max-height:80vh; overflow-y:auto; box-shadow:0 10px 25px rgba(0,0,0,0.2);">
                            <h3 style="margin-top:0; color:#4caf50; display:flex; align-items:center; gap:10px;">
                                 🔍 Analizando: ${filename}
                            </h3>
                            <div id="attachment-analysis-loading" style="color:#666; font-style:italic; padding: 20px; text-align:center;">
                                <div style="margin-bottom:10px;">⏳ Extrayendo y analizando contenido...</div>
                                <div style="font-size:0.85em; color:#999;">Esto puede tardar unos segundos para archivos grandes</div>
                            </div>
                            <div id="attachment-analysis-result" style="display:none; padding:15px; background:#f9f9f9; border-radius:6px; margin:10px 0; white-space:pre-wrap; line-height:1.6;"></div>
                            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:15px;">
                                <button id="btn-close-attachment-analysis" style="padding:8px 15px; border:none; background:#eee; cursor:pointer; border-radius:4px;">Cerrar</button>
                            </div>
                        </div>
                    `;

                    overlay.querySelector('#btn-close-attachment-analysis').onclick = () => { overlay.style.display = 'none'; };

                    try {
                        const apiBase = `${window.location.protocol}//${window.location.hostname}:8001/api/outlook`;

                        const res = await fetch(`${apiBase}/analyze-attachment`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                email_id: emailId,
                                attachment_index: attachmentIndex,
                                email_address: "",
                                password: ""
                            })
                        });
                        const json = await res.json();

                        const loading = overlay.querySelector('#attachment-analysis-loading');
                        const result = overlay.querySelector('#attachment-analysis-result');

                        loading.style.display = 'none';
                        result.style.display = 'block';

                        if (json.success) {
                            result.innerHTML = `
                                <div style="margin-bottom:10px; padding:10px; background:#e8f5e9; border-left:4px solid #4caf50; border-radius:4px;">
                                    <strong>📄 Archivo:</strong> ${json.filename}<br>
                                    <strong>📊 Tipo:</strong> ${json.content_type}<br>
                                    <strong>💾 Tamaño:</strong> ${(json.size / 1024).toFixed(1)} KB
                                </div>
                                <div style="padding:10px; background:white; border:1px solid #ddd; border-radius:4px;">
                                    <strong style="color:#4caf50;">📝 Análisis:</strong><br><br>
                                    ${this.escapeHtml(json.analysis)}
                                </div>
                            `;
                        } else {
                            result.innerHTML = `
                                <div style="padding:10px; background:#ffebee; border-left:4px solid #f44336; border-radius:4px; color:#c62828;">
                                    <strong>❌ Error:</strong> ${this.escapeHtml(json.error || 'Error desconocido')}
                                </div>
                            `;
                        }
                    } catch (e) {
                        const loading = overlay.querySelector('#attachment-analysis-loading');
                        const result = overlay.querySelector('#attachment-analysis-result');
                        loading.style.display = 'none';
                        result.style.display = 'block';
                        result.innerHTML = `
                            <div style="padding:10px; background:#ffebee; border-left:4px solid #f44336; border-radius:4px; color:#c62828;">
                                <strong>❌ Error de conexión:</strong> ${this.escapeHtml(e.message)}
                            </div>
                        `;
                    }
                }
            });
        }
    }

    setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
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
