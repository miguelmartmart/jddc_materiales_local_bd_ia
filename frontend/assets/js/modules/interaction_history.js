export class InteractionHistoryModule {
    constructor() {
        this.apiBase = '/api/history';
    }

    async showHistoryModal() {
        // Remove existing if any
        let modal = document.getElementById('history-modal');
        if (modal) modal.remove();

        modal = document.createElement('div');
        modal.id = 'history-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.6); z-index: 2000;
            display: flex; justify-content: flex-end;
        `;

        modal.innerHTML = `
            <div style="background: white; width: 600px; height: 100%; overflow-y: auto; padding: 25px; box-shadow: -5px 0 25px rgba(0,0,0,0.2); animation: slideInRight 0.3s ease;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid #eee; padding-bottom:15px;">
                    <h2 style="margin:0; color: #1e88e5; display:flex; align-items:center; gap:10px;">📜 Historial de Interacciones</h2>
                    <button id="close-history" style="background:none; border:none; font-size:1.5em; cursor:pointer; color:#666;">&times;</button>
                </div>
                
                <div id="history-content">
                    <div style="text-align:center; padding:30px; color:#666;">⏳ Cargando historial...</div>
                </div>
            </div>
            <style>
                @keyframes slideInRight { from { transform: translateX(100%); } to { transform: translateX(0); } }
                .history-item { border-left: 3px solid #ddd; padding-left: 15px; margin-bottom: 25px; position: relative; }
                .history-item::before { content: ''; position: absolute; left: -8px; top: 0; width: 12px; height: 12px; border-radius: 50%; background: #ddd; border: 2px solid white; }
                
                .h-type-analysis { border-color: #4caf50; } .h-type-analysis::before { background: #4caf50; }
                .h-type-deep { border-color: #2196f3; } .h-type-deep::before { background: #2196f3; }
                .h-type-simulation { border-color: #9c27b0; } .h-type-simulation::before { background: #9c27b0; }
                .h-type-reply { border-color: #ff9800; } .h-type-reply::before { background: #ff9800; }
            </style>
        `;

        document.body.appendChild(modal);

        modal.querySelector('#close-history').onclick = () => modal.remove();
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); }; // Close on click outside

        await this.loadHistory();
    }

    async loadHistory() {
        const container = document.getElementById('history-content');
        try {
            const res = await fetch(`${this.apiBase}/logs?limit=50`);
            const data = await res.json();

            if (!data.success || !data.logs) throw new Error("Format error");
            if (data.logs.length === 0) {
                container.innerHTML = '<div style="text-align:center; color:#999; margin-top:50px;">No hay historial registrado aún.</div>';
                return;
            }

            container.innerHTML = '';

            data.logs.forEach(log => {
                const date = new Date(log.timestamp);
                const timeStr = date.toLocaleTimeString() + ' ' + date.toLocaleDateString();

                let typeClass = 'history-item';
                let icon = '🤖';
                let title = log.action;

                if (log.action === 'ANALYSIS') { typeClass += ' h-type-analysis'; icon = '🔍'; title = "Análisis Automático"; }
                if (log.action === 'DEEP_ANALYSIS') { typeClass += ' h-type-deep'; icon = '🧠'; title = "Análisis Profundo"; }
                if (log.action.includes('SIMULATE')) { typeClass += ' h-type-simulation'; icon = '🔮'; title = "Simulación"; }
                if (log.action.includes('REPLY')) { typeClass += ' h-type-reply'; icon = '✍️'; title = "Sugerencia Respuesta"; }

                const meta = log.metadata || {};
                const contextStr = meta.subject ? `Subject: ${meta.subject}` : (meta.context || 'General Context');

                const el = document.createElement('div');
                el.className = typeClass;

                // Format JSON output nicely
                let outputDisplay = log.output_result;
                if (log.output_result_json) {
                    outputDisplay = JSON.stringify(log.output_result_json, null, 2);
                }

                const toggleId = `h-det-${log.id}`;

                el.innerHTML = `
                    <div style="margin-bottom:5px; font-size:0.85em; color:#888;">${timeStr} • ${log.module}</div>
                    <div style="font-weight:600; font-size:1.1em; color:#333; display:flex; align-items:center; gap:8px;">
                        <span>${icon}</span> ${title}
                        <span style="font-size:0.7em; background:#f0f0f0; padding:2px 6px; border-radius:4px; color:#555;">${log.model_id || 'Unknown Model'}</span>
                    </div>
                    <div style="margin-top:5px; color:#555; font-size:0.95em;">${this.escapeHtml(contextStr)}</div>
                    
                    <button onclick="document.getElementById('${toggleId}').hidden = !document.getElementById('${toggleId}').hidden" 
                        style="margin-top:8px; background:none; border:none; color:#1e88e5; cursor:pointer; font-size:0.9em; padding:0; text-decoration:underline;">
                        Ver Detalles (+ Input/Output)
                    </button>
                    
                    <div id="${toggleId}" hidden style="margin-top:10px; background:#f5f5f5; padding:10px; border-radius:6px; font-family:monospace; font-size:0.85em; white-space:pre-wrap; overflow-x:auto;">
<strong>Input:</strong>
${this.escapeHtml(log.input_context || '')}

<strong>Output:</strong>
${this.escapeHtml(outputDisplay)}
                    </div>
                `;
                container.appendChild(el);
            });

        } catch (e) {
            container.innerHTML = `<div style="color:red; text-align:center;">Error cargando historial: ${e.message}</div>`;
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        if (typeof text !== 'string') text = JSON.stringify(text);
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}
