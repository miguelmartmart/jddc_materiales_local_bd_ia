export class ModelsModule {
    constructor() {
        this.apiBase = '/api/models';
        this.editingModelId = null;
    }

    init() {
        const addBtn = document.getElementById('btn-add-model');
        const reloadBtn = document.getElementById('btn-reload-models');
        const cancelBtn = document.getElementById('btn-cancel-model');
        const form = document.getElementById('model-form');

        if (addBtn) {
            addBtn.addEventListener('click', () => this.showAddModal());
        }
        if (reloadBtn) {
            reloadBtn.addEventListener('click', () => this.loadModels());
        }
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeModal());
        }
        if (form) {
            form.addEventListener('submit', (e) => this.saveModel(e));
        }

        this.loadModels();
    }

    async loadModels() {
        try {
            const response = await fetch(`${this.apiBase}/`);
            const models = await response.json();
            this.renderTable(models);
        } catch (error) {
            console.error('Error loading models:', error);
            alert('Error al cargar modelos');
        }
    }

    renderTable(models) {
        const tbody = document.querySelector('#models-table tbody');
        tbody.innerHTML = '';

        models.forEach(model => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${model.name}</td>
                <td>${model.provider}</td>
                <td>${model.model_id}</td>
                <td>
                    <span style="color: ${model.enabled ? 'green' : 'red'}">
                        ${model.enabled ? '✓ Activo' : '✗ Inactivo'}
                    </span>
                </td>
                <td>${model.has_api_key ? '🔑 Configurada' : '⚠️ Sin configurar'}</td>
                <td>
                    <button class="btn small" onclick="window.app.modules.models.editModel('${model.id}')">✏️ Editar</button>
                    <button class="btn small" onclick="window.app.modules.models.deleteModel('${model.id}')">🗑️ Eliminar</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    showAddModal() {
        this.editingModelId = null;
        document.getElementById('modal-title').textContent = 'Añadir Modelo';
        document.getElementById('model-form').reset();
        document.getElementById('model-id').disabled = false;
        document.getElementById('model-modal').style.display = 'block';
    }

    async editModel(modelId) {
        try {
            const response = await fetch(`${this.apiBase}/${modelId}`);
            const model = await response.json();

            this.editingModelId = modelId;
            document.getElementById('modal-title').textContent = 'Editar Modelo';
            document.getElementById('model-id').value = model.id;
            document.getElementById('model-id').disabled = true;
            document.getElementById('model-name').value = model.name;
            document.getElementById('model-provider').value = model.provider;
            document.getElementById('model-model-id').value = model.model_id;
            document.getElementById('model-base-url').value = model.base_url || '';
            document.getElementById('model-description').value = model.description || '';
            document.getElementById('model-enabled').checked = model.enabled;
            document.getElementById('model-api-key').value = '';
            document.getElementById('model-api-key').placeholder = model.has_api_key ? 'Dejar vacío para mantener actual' : 'Añadir API Key';

            document.getElementById('model-modal').style.display = 'block';
        } catch (error) {
            console.error('Error loading model:', error);
            alert('Error al cargar modelo');
        }
    }

    closeModal() {
        document.getElementById('model-modal').style.display = 'none';
        this.editingModelId = null;
    }

    async saveModel(e) {
        e.preventDefault();

        const modelData = {
            id: document.getElementById('model-id').value,
            name: document.getElementById('model-name').value,
            provider: document.getElementById('model-provider').value,
            model_id: document.getElementById('model-model-id').value,
            base_url: document.getElementById('model-base-url').value || null,
            description: document.getElementById('model-description').value || null,
            enabled: document.getElementById('model-enabled').checked
        };

        const apiKey = document.getElementById('model-api-key').value;
        if (apiKey) {
            modelData.api_key = apiKey;
        }

        try {
            let response;
            if (this.editingModelId) {
                response = await fetch(`${this.apiBase}/${this.editingModelId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(modelData)
                });
            } else {
                response = await fetch(`${this.apiBase}/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(modelData)
                });
            }

            const result = await response.json();
            if (response.ok) {
                alert('Modelo guardado correctamente');
                this.closeModal();
                this.loadModels();
            } else {
                alert('Error: ' + (result.detail || 'Error desconocido'));
            }
        } catch (error) {
            console.error('Error saving model:', error);
            alert('Error al guardar modelo');
        }
    }

    async deleteModel(modelId) {
        if (!confirm('¿Estás seguro de eliminar este modelo?')) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/${modelId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                alert('Modelo eliminado');
                this.loadModels();
            } else {
                alert('Error al eliminar modelo');
            }
        } catch (error) {
            console.error('Error deleting model:', error);
            alert('Error al eliminar modelo');
        }
    }
}
