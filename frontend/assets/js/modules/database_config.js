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
}
