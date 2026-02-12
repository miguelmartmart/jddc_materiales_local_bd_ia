import { api } from '../core/api.js';
import { showNotification } from '../core/utils.js';
import { DB_CONFIG } from '../core/constants.js';

export class DatabaseConfigModule {
    constructor() {
        this.viewId = 'database-config';
        this.metadataEditor = document.getElementById('metadata-editor');
        this.tableSelector = document.getElementById('db-table-selector');
        this.btnAnalyze = document.getElementById('btn-analyze-table');
        this.btnSave = document.getElementById('btn-save-metadata');
        this.previewContainer = document.getElementById('analysis-preview-container');
        this.analysisPreview = document.getElementById('analysis-preview');
        this.btnAppend = document.getElementById('btn-append-analysis');
        this.btnHistory = document.getElementById('btn-db-history');
        this.btnExportChat = document.getElementById('btn-export-chat-history');
        this.historyModal = document.getElementById('db-history-modal');
        this.historyList = document.getElementById('db-history-list');

        this.currentAnalysis = null;
    }

    async init() {
        console.log('Initializing Database Config Module...');
        this.bindEvents();
        await this.loadMetadata();
        await this.loadTables();
    }

    bindEvents() {
        this.btnSave.addEventListener('click', () => this.saveMetadata());
        this.btnAnalyze.addEventListener('click', () => this.analyzeTable());
        this.btnAppend.addEventListener('click', () => this.appendAnalysis());
        this.btnHistory.addEventListener('click', () => this.showHistory());
        this.btnExportChat.addEventListener('click', () => {
            window.open('/api/chat/export-full', '_blank');
        });
    }

    async loadMetadata() {
        try {
            const metadata = await api.get('/database/metadata');
            this.metadataEditor.value = JSON.stringify(metadata, null, 4);
        } catch (error) {
            console.error('Error loading metadata:', error);
            showNotification('Error cargando metadatos', 'error');
        }
    }

    async saveMetadata() {
        try {
            const jsonContent = this.metadataEditor.value;
            // Validate JSON
            const data = JSON.parse(jsonContent);

            await api.post('/database/metadata', data);
            showNotification('Metadatos guardados correctamente', 'success');
        } catch (error) {
            console.error('Error saving metadata:', error);
            if (error instanceof SyntaxError) {
                showNotification('Error de sintaxis en el JSON', 'error');
            } else {
                showNotification('Error guardando metadatos', 'error');
            }
        }
    }

    async loadTables() {
        try {
            const dbParams = {
                host: DB_CONFIG.HOST,
                port: DB_CONFIG.PORT,
                database: DB_CONFIG.DATABASE,
                username: DB_CONFIG.USERNAME,
                password: DB_CONFIG.PASSWORD
            };

            const response = await api.post('/database/tables', { db_params: dbParams });
            const tables = response.tables;

            this.tableSelector.innerHTML = '<option value="">Seleccionar tabla...</option>';
            tables.forEach(table => {
                const option = document.createElement('option');
                option.value = table;
                option.textContent = table;
                this.tableSelector.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading tables:', error);
            showNotification('Error cargando tablas: ' + error.message, 'error');
        }
    }

    async analyzeTable() {
        const tableName = this.tableSelector.value;
        if (!tableName) {
            showNotification('Por favor selecciona una tabla', 'warning');
            return;
        }

        this.btnAnalyze.disabled = true;
        this.btnAnalyze.textContent = '⏳ Analizando...';
        this.previewContainer.style.display = 'none';

        try {
            const dbParams = {
                host: DB_CONFIG.HOST,
                port: DB_CONFIG.PORT,
                database: DB_CONFIG.DATABASE,
                username: DB_CONFIG.USERNAME,
                password: DB_CONFIG.PASSWORD
            };

            const response = await api.post(`/database/analyze/${tableName}`, { db_params: dbParams });
            this.currentAnalysis = response.data;

            this.analysisPreview.textContent = JSON.stringify(this.currentAnalysis, null, 4);
            this.previewContainer.style.display = 'block';
            showNotification('Análisis completado', 'success');
        } catch (error) {
            console.error('Error analyzing table:', error);
            showNotification('Error analizando tabla: ' + error.message, 'error');
        } finally {
            this.btnAnalyze.disabled = false;
            this.btnAnalyze.textContent = '🤖 Analizar con IA';
        }
    }

    appendAnalysis() {
        if (!this.currentAnalysis) return;

        try {
            const currentMetadata = JSON.parse(this.metadataEditor.value);

            // Merge tables
            if (!currentMetadata.tables) {
                currentMetadata.tables = {};
            }

            // Add new table(s)
            Object.keys(this.currentAnalysis).forEach(key => {
                currentMetadata.tables[key] = this.currentAnalysis[key];
            });

            this.metadataEditor.value = JSON.stringify(currentMetadata, null, 4);
            this.previewContainer.style.display = 'none';
            this.currentAnalysis = null;
            showNotification('Tabla añadida al editor. Recuerda guardar.', 'success');
        } catch (error) {
            console.error('Error appending analysis:', error);
            showNotification('Error al añadir: JSON inválido en el editor', 'error');
        }
    }

    async showHistory() {
        this.historyModal.showModal();
        this.historyList.innerHTML = '<div style="text-align: center; color: #64748b; padding: 20px;">Cargando historial...</div>';

        try {
            // Fetch logs for module=DATABASE and action=ANALYZE_TABLE
            // Prefix is /api/history (main.py) + /logs (router.py) -> /history/logs

            const response = await api.get('/history/logs?module=DATABASE&action=ANALYZE_TABLE&limit=20');
            const data = response.logs || response;

            if (!data || data.length === 0) {
                this.historyList.innerHTML = '<div style="text-align: center; color: #64748b; padding: 20px;">No hay historial de análisis.</div>';
                return;
            }

            this.renderHistory(data);

        } catch (error) {
            console.error('Error loading history:', error);
            this.historyList.innerHTML = '<div style="text-align: center; color: #ef4444; padding: 20px;">Error cargando historial.</div>';
        }
    }

    renderHistory(logs) {
        this.historyList.innerHTML = '';
        logs.forEach(log => {
            const card = document.createElement('div');
            card.className = 'history-card';
            card.style.cssText = 'background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);';

            const date = new Date(log.timestamp).toLocaleString();
            const table = log.metadata?.table || 'Desconocida';
            const model = log.model_id || 'N/A';

            // Format input context (truncated)
            let inputPreview = log.input_context || '';
            if (inputPreview.length > 150) inputPreview = inputPreview.substring(0, 150) + '...';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px;">
                    <span style="font-weight: 600; color: #334155;">📅 ${date}</span>
                    <span style="font-size: 0.9em; background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 12px;">${table}</span>
                </div>
                <div style="font-size: 0.9em; color: #475569; margin-bottom: 8px;">
                    <strong>🧠 Modelo:</strong> ${model}
                </div>
                <div style="background: #f8fafc; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 0.85em; color: #333; margin-bottom: 8px;">
                    <strong>📥 Input (Contexto):</strong><br>
                    ${inputPreview}
                </div>
                <div class="expand-content" style="display: none;">
                    <div style="background: #f0fdf4; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 0.85em; color: #166534; margin-top: 5px; white-space: pre-wrap;">
                        <strong>📤 Output (IA):</strong><br>
                        ${log.output_result}
                    </div>
                </div>
                <button class="btn-toggle-details" style="background: none; border: none; color: #2563eb; cursor: pointer; font-size: 0.9em; padding: 0; text-decoration: underline;">
                    Ver Detalles Completos
                </button>
            `;

            const btnToggle = card.querySelector('.btn-toggle-details');
            const expandContent = card.querySelector('.expand-content');

            btnToggle.addEventListener('click', () => {
                const isHidden = expandContent.style.display === 'none';
                expandContent.style.display = isHidden ? 'block' : 'none';
                btnToggle.textContent = isHidden ? 'Ocultar Detalles' : 'Ver Detalles Completos';
            });

            this.historyList.appendChild(card);
        });
    }
}
