export class ModelsModule {
    constructor() {
        this.apiBase = '/api/models';
        this.editingModelId = null;
    }

    init() {
        const addBtn = document.getElementById('btn-add-model');
        const reloadBtn = document.getElementById('btn-reload-models');
        const cancelBtn = document.getElementById('btn-cancel-model');
        const resetBtn = document.getElementById('btn-reset-score');
        const form = document.getElementById('model-form');

        if (addBtn) addBtn.addEventListener('click', () => this.showAddModal());
        if (reloadBtn) reloadBtn.addEventListener('click', () => this.loadModels());
        const discoverBtn = document.getElementById('btn-discover-models');
        if (discoverBtn) discoverBtn.addEventListener('click', () => this.discoverModels());
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.closeModal());
        if (resetBtn) resetBtn.addEventListener('click', () => this.resetScore());
        if (resetBtn) resetBtn.addEventListener('click', () => this.resetScore());
        if (form) form.addEventListener('submit', (e) => this.saveModel(e));

        // Keys UI
        const keysBtn = document.getElementById('btn-manage-keys');
        const saveKeysBtn = document.getElementById('btn-save-keys');
        const cancelKeysBtn = document.getElementById('btn-cancel-keys');

        if (keysBtn) keysBtn.addEventListener('click', () => this.openKeysModal());
        if (saveKeysBtn) saveKeysBtn.addEventListener('click', () => this.saveKeys());
        if (cancelKeysBtn) cancelKeysBtn.addEventListener('click', () => this.closeKeysModal());

        // Add Test All Button (Inject relative to Reload button)
        if (reloadBtn && reloadBtn.parentNode && !document.getElementById('btn-test-all')) {
            const testAllBtn = document.createElement('button');
            testAllBtn.id = 'btn-test-all';
            testAllBtn.className = 'btn secondary';
            testAllBtn.innerHTML = '🧪 Probar Todos';
            testAllBtn.style.marginRight = '10px'; // Spacing
            testAllBtn.onclick = () => this.testAllModels();

            // Insert before reload button
            reloadBtn.parentNode.insertBefore(testAllBtn, reloadBtn);
        }

        this.loadModels();
    }

    bindFilterEvents() {
        const searchInput = document.getElementById('model-search-input');
        const scoreFilter = document.getElementById('model-score-filter');
        const tokensFilter = document.getElementById('model-tokens-filter');
        const quotaFilter = document.getElementById('model-quota-filter');

        // Inputs
        if (searchInput) searchInput.addEventListener('input', () => this.filterModels());
        if (scoreFilter) scoreFilter.addEventListener('input', () => this.filterModels());
        if (tokensFilter) tokensFilter.addEventListener('input', () => this.filterModels());
        if (quotaFilter) quotaFilter.addEventListener('change', () => this.filterModels());

        // Capability Checkboxes
        document.querySelectorAll('.cap-check').forEach(cb => {
            cb.addEventListener('change', () => this.filterModels());
        });
    }

    filterModels() {
        const searchInput = document.getElementById('model-search-input');
        const scoreFilter = document.getElementById('model-score-filter');
        const tokensFilter = document.getElementById('model-tokens-filter');
        const quotaFilter = document.getElementById('model-quota-filter');

        const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const minScore = scoreFilter ? parseInt(scoreFilter.value) || 0 : 0;
        const minTokens = tokensFilter ? parseInt(tokensFilter.value) || 0 : 0;
        const onlyAvailable = quotaFilter ? quotaFilter.checked : false;

        // Get checked capabilities
        const requiredCaps = Array.from(document.querySelectorAll('.cap-check:checked')).map(cb => cb.value);

        if (!this.allModels) return;

        const filtered = this.allModels.filter(model => {
            // Text Search
            const matchesSearch = !searchTerm ||
                (model.name && model.name.toLowerCase().includes(searchTerm)) ||
                (model.model_id && model.model_id.toLowerCase().includes(searchTerm)) ||
                (model.provider && model.provider.toLowerCase().includes(searchTerm));

            // Capability Filter (AND Logic: Must have ALL selected)
            const modelCaps = model.capabilities || [];
            const matchesCapability = requiredCaps.every(cap => modelCaps.includes(cap));

            // Score Filter
            const score = model.score || 0;
            const matchesScore = score >= minScore;

            // Token Filter (Check context_window or max_tokens or generic)
            const context = model.context_window || (model.parameters && model.parameters.max_tokens) || 0;
            const matchesTokens = context >= minTokens;

            // Quota Filter
            let matchesQuota = true;
            if (onlyAvailable) {
                const isBlocked = model.quota && model.quota.blocked;
                const isResetPending = model.quota && model.quota.reset_at && new Date(model.quota.reset_at) > new Date();
                matchesQuota = !isBlocked && !isResetPending;
            }

            return matchesSearch && matchesCapability && matchesScore && matchesTokens && matchesQuota;
        });

        this.renderTable(filtered);
    }

    async testAllModels() {
        if (!confirm('Esto probará la conectividad de TODOS los modelos habilitados. Puede tardar un poco. ¿Continuar?')) return;

        const models = this.models.filter(m => m.enabled);
        let results = { success: [], fail: [] };
        let count = 0;

        // Use a modal or console for progress
        const consoleEl = document.getElementById('test-console');
        this.openTestModal(models[0].id); // Open modal with first model just to show logs
        const log = (msg) => {
            consoleEl.textContent += `\n${msg}`;
            consoleEl.scrollTop = consoleEl.scrollHeight;
        };

        consoleEl.textContent = "🚀 INICIANDO PRUEBA MASIVA DE MODELOS...";

        for (const model of models) {
            count++;
            log(`\n[${count}/${models.length}] Probando ${model.name}...`);
            this.currentTestModel = model;
            document.getElementById('test-model-name').textContent = `Test Masivo: ${model.name}`;

            try {
                // Test Chat (Basic Connectivity)
                const response = await fetch(`/api/models/${model.id}/test`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ capability: 'text' })
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        log(`   ✅ TEXTO: OK`);
                        results.success.push(model.name);
                    } else {
                        log(`   ❌ TEXTO: Falló - ${data.response}`);
                        results.fail.push(`${model.name} (API Error)`);
                    }
                } else {
                    log(`   ❌ TEXTO: Http Error ${response.status}`);
                    results.fail.push(`${model.name} (HTTP ${response.status})`);
                }

                // Optional: Test Vision if supported
                if (model.capabilities.includes('vision')) {
                    // We skip full vision test in mass run to save time/tokens unless critical
                    // Or we can do a quick check? Let's just do text for "Alive" status.
                    log(`   ℹ️ Visión: Saltado en prueba masiva.`);
                }

            } catch (e) {
                log(`   ❌ ERROR: ${e.message}`);
                results.fail.push(`${model.name} (Exception)`);
            }

            // Small delay to prevent rate limits
            await new Promise(r => setTimeout(r, 1000));
        }

        log(`❌ FALLIDOS (${results.fail.length}): ${results.fail.join(', ')}`);
        alert(`Prueba finalizada.\nExitosos: ${results.success.length}\nFallidos: ${results.fail.length}\nRevisa la consola para más detalles.`);
    }

    async discoverModels() {
        if (!confirm('Esto escaneará tus proveedores (OpenAI, Google, etc.) y ACTUALIZARÁ tu lista de modelos automáticamente con los IDs reales encontrados.\n\n¿Continuar?')) return;

        try {
            // Show loading state
            const btn = document.getElementById('btn-discover-models');
            const originalText = btn ? btn.innerText : '';
            if (btn) btn.innerText = '⏳ Escaneando...';

            // Call Sync Endpoint
            const response = await fetch(`${this.apiBase}/discovery/sync`, { method: 'POST' });
            const data = await response.json();

            if (btn) btn.innerText = originalText;

            if (data.success) {
                alert(`¡Éxito! 🌍\n\nNuevos modelos: ${data.stats.added}\nActualizados: ${data.stats.updated}\n\nLa lista se recargará ahora.`);
                this.loadModels(); // Refresh UI
            } else {
                alert('Error en el descubrimiento: ' + JSON.stringify(data));
            }

        } catch (e) {
            console.error(e);
            alert('Error al conectar con el servidor: ' + e.message);
            const btn = document.getElementById('btn-discover-models');
            if (btn && btn.innerText.includes('Escaneando')) btn.innerText = '🌍 Descubrir';
        }
    }

    async loadModels() {
        try {
            const response = await fetch(`${this.apiBase}/`);
            const models = await response.json();
            this.models = models;
            this.allModels = models; // Cache for filtering
            this.renderTable(models);

            // Re-bind events if elements were re-created (though they are in toolbar)
            this.bindFilterEvents();
        } catch (error) {
            console.error('Error loading models:', error);
            // alert('Error al cargar modelos');
        }
    }

    renderTable(models) {
        const container = document.getElementById('models-container');
        container.innerHTML = '';

        if (!models || models.length === 0) {
            container.innerHTML = '<div style="text-align:center; padding:40px; color:#666;">No hay modelos configurados.</div>';
            return;
        }

        // Group by Provider
        const groups = {};
        models.forEach(m => {
            const provider = m.provider || 'other';
            if (!groups[provider]) groups[provider] = [];
            groups[provider].push(m);
        });

        // Provider Display Names
        const providerNames = {
            'openai': 'OpenAI',
            'gemini': 'Google Gemini',
            'anthropic': 'Anthropic (Claude)',
            'groq': 'Groq',
            'deepseek': 'DeepSeek',
            'mistral': 'Mistral AI',
            'cohere': 'Cohere',
            'azure': 'Azure OpenAI',
            'other': 'Otros'
        };

        // Sort Providers (Custom order + alphabetical)
        const providerOrder = ['openai', 'anthropic', 'gemini', 'groq', 'deepseek', 'mistral'];
        const sortedProviders = Object.keys(groups).sort((a, b) => {
            const idxA = providerOrder.indexOf(a);
            const idxB = providerOrder.indexOf(b);
            if (idxA !== -1 && idxB !== -1) return idxA - idxB;
            if (idxA !== -1) return -1;
            if (idxB !== -1) return 1;
            return a.localeCompare(b);
        });

        sortedProviders.forEach(providerKey => {
            const groupModels = groups[providerKey];
            const providerDisplayName = providerNames[providerKey] || providerKey.toUpperCase();

            // Sort Models within group
            const tierOrder = { 'elite': 4, 'high': 3, 'medium': 2, 'low': 1 };
            groupModels.sort((a, b) => {
                const tierDiff = (tierOrder[b.tier] || 0) - (tierOrder[a.tier] || 0);
                if (tierDiff !== 0) return tierDiff;
                return (b.score || 0) - (a.score || 0);
            });

            // Create Details Element
            const details = document.createElement('details');
            details.open = ['openai', 'anthropic', 'gemini'].includes(providerKey); // Open popular ones by default
            details.style.marginBottom = '15px';
            details.style.border = '1px solid #e2e8f0';
            details.style.borderRadius = '8px';
            details.style.overflow = 'hidden';
            details.style.background = 'white';

            // Summary
            const summary = document.createElement('summary');
            summary.style.padding = '15px';
            summary.style.background = '#f8fafc';
            summary.style.cursor = 'pointer';
            summary.style.fontWeight = '600';
            summary.style.display = 'flex';
            summary.style.alignItems = 'center';
            summary.style.gap = '10px';
            summary.innerHTML = `<span style="font-size:1.1em;">${providerDisplayName}</span> <span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:12px; font-size:0.8em;">${groupModels.length}</span>`;

            details.appendChild(summary);

            // Table for this group
            const tableContainer = document.createElement('div');
            tableContainer.className = 'data-grid-container';
            tableContainer.style.boxShadow = 'none';
            tableContainer.style.borderTop = '1px solid #e2e8f0';

            const table = document.createElement('table');
            table.style.width = '100%';
            table.innerHTML = `
                <thead>
                    <tr style="background:white;">
                        <th style="width:25%">Modelo</th>
                        <th>Familia</th>
                        <th>Tier</th>
                        <th>Score</th>
                        <th>Capacidades</th> <!-- Changed column -->
                        <th>Routing (App)</th> <!-- Changed column -->
                        <th>Estado</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody></tbody>
            `;

            const tbody = table.querySelector('tbody');

            groupModels.forEach(model => {
                const tr = document.createElement('tr');

                // Status Logic
                let statusHtml = model.enabled
                    ? `<span style="color:green; font-weight:500;">✓</span>`
                    : `<span style="color:#cbd5e1;">⚪</span>`;
                if (model.quota && model.quota.blocked) statusHtml = `⛔`;

                // Tier Badge
                const tierColors = {
                    'elite': 'background:#e3f2fd; color:#1565c0;',
                    'high': 'background:#e8f5e9; color:#2e7d32;',
                    'medium': 'background:#fff3e0; color:#ef6c00;',
                    'low': 'background:#f5f5f5; color:#616161;'
                };
                const tierStyle = tierColors[model.tier] || tierColors['low'];
                const tierBadge = `<span style="padding:2px 8px; border-radius:12px; font-size:0.8em; font-weight:500; ${tierStyle}">${model.tier.toUpperCase()}</span>`;

                // Score
                const scoreColor = model.score > 80 ? '#22c55e' : model.score > 50 ? '#f59e0b' : '#ef4444';

                // Capabilities Icons (Model features)
                const caps = model.capabilities || [];
                const capIcons = {
                    'vision': '👁️',
                    'audio': '🎤',
                    'video': '🎥',
                    'image_generation': '🎨',
                    'code': '💻',
                    'agents': '🤖',
                    'complex_reasoning': '🧠',
                    'text': '📝'
                };
                const capsHtml = caps.map(c => `<span title="${c}" style="cursor:help; font-size:1.2em; margin-right:4px;">${capIcons[c] || ''}</span>`).join('');

                // Usage Badges (App Routing)
                const usages = model.usage || [];
                const usageHtml = usages.slice(0, 3).map(u => {
                    return `<span style="background:#f1f5f9; color:#475569; padding:2px 6px; border-radius:4px; font-size:0.75em; border:1px solid #e2e8f0; margin-right:2px;">${u}</span>`;
                }).join('');

                tr.innerHTML = `
                    <td>
                        <div style="font-weight:600; color:#334155;">${model.name}</div>
                        <div style="font-size:0.75em; color:#94a3b8; font-family:monospace;">${model.model_id}</div>
                    </td>
                    <td>${model.family}</td>
                    <td>${tierBadge}</td>
                    <td><span style="font-weight:bold; color:${scoreColor}">${model.score}</span></td>
                    <td>${capsHtml}</td>
                    <td>${usageHtml}</td>
                    <td>${statusHtml}</td>
                    <td style="display:flex; gap:5px;">
                         <button class="btn small primary" style="padding:4px 8px;" onclick="window.app.modules.models.openTestModal('${model.id}')" title="Probar Capacidades">🧪</button>
                         <button class="btn small" style="padding:4px 8px;" onclick="window.app.modules.models.editModel('${model.id}')" title="Editar">✏️</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });

            tableContainer.appendChild(table);
            details.appendChild(tableContainer);
            container.appendChild(details);
        });
    }

    openTestModal(modelId) {
        const model = this.models.find(m => m.id === modelId);
        if (!model) return;

        this.currentTestModel = model;
        document.getElementById('test-model-name').textContent = model.name;
        document.getElementById('test-console').textContent = `> Listo para probar ${model.name} (${model.model_id})...\n> Haz click en "Ejecutar Pruebas"`;

        // Reset checkboxes
        document.getElementById('test-check-chat').checked = true; // Default to chat test
        document.getElementById('test-check-vision').checked = false; // Default to unchecked
        document.getElementById('test-check-audio').checked = false; // Default to unchecked

        // Enable/disable checkboxes based on model capabilities
        const caps = model.capabilities || [];
        document.getElementById('test-check-chat').disabled = !caps.includes('text');
        document.getElementById('test-check-vision').disabled = !caps.includes('vision');
        document.getElementById('test-check-audio').disabled = !caps.includes('audio');
        document.getElementById('test-check-video').disabled = !caps.includes('video');
        document.getElementById('test-check-image_generation').disabled = !caps.includes('image_generation');

        // Uncheck all first
        ['vision', 'audio', 'video', 'image_generation'].forEach(c => {
            const el = document.getElementById(`test-check-${c}`);
            if (el) el.checked = false;
        });

        const modal = document.getElementById('test-model-modal');
        if (modal.showModal) modal.showModal();
        else modal.style.display = 'block'; // Fallback
    }

    async runModelTest() {
        const consoleEl = document.getElementById('test-console');
        const model = this.currentTestModel;

        const log = (msg) => {
            consoleEl.textContent += `\n${msg}`;
            consoleEl.scrollTop = consoleEl.scrollHeight;
        };

        log(`\n🚀 Iniciando pruebas avanzadas para: ${model.model_id}`);

        const testCapability = async (capName, prettyName) => {
            if (document.getElementById(`test-check-${capName}`).checked) {
                log(`> [TEST] Verificando ${prettyName}...`);
                try {
                    const response = await fetch(`/api/models/${model.id}/test`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ capability: (capName === 'chat' ? 'text' : capName) })
                    });
                    if (!response.ok) {
                        let errorMsg = response.statusText;
                        try {
                            const errData = await response.json();
                            errorMsg = errData.detail || errData.message || JSON.stringify(errData);
                        } catch (e) { }
                        throw new Error(errorMsg);
                    }

                    const data = await response.json();
                    if (data.success) {
                        log(`✅ [PASS] ${prettyName} Correcto.`);
                        if (data.response) log(`   "${data.response.substring(0, 60)}..."`);
                    } else {
                        log(`❌ [FAIL] ${prettyName} Falló.`);
                    }
                } catch (e) {
                    log(`❌ [ERR] ${prettyName}: ${e.message}`);
                }
            }
        };

        try {
            await testCapability('chat', 'Chat (Texto)');

            if (model.capabilities.includes('vision')) {
                await testCapability('vision', 'Visión (Input)');
            }

            if (model.capabilities.includes('audio')) {
                await testCapability('audio', 'Audio (Input)');
            }

            if (model.capabilities.includes('image_generation')) {
                await testCapability('image_generation', 'Generación de Imagen');
            }

            if (model.capabilities.includes('video')) {
                await testCapability('video', 'Video (Input)');
            }

            log(`\n✨ Pruebas completadas.`);

        } catch (error) {
            log(`\n❌ ERROR FATAL: ${error.message}`);
        }
    }

    showAddModal() {
        this.editingModelId = null;
        document.getElementById('modal-title').textContent = 'Añadir Modelo';
        document.getElementById('model-form').reset();
        document.getElementById('model-id').disabled = false;
        document.getElementById('btn-reset-score').style.display = 'none';

        // Defaults
        document.getElementById('model-tier').value = 'medium';
        document.getElementById('model-family').value = 'other';
        document.getElementById('model-score').value = 100;
        document.querySelectorAll('input[name="usage"]').forEach(cb => cb.checked = cb.value === 'chat');

        document.getElementById('model-modal').style.display = 'block';
        this.updateReferenceScores();
    }

    updateReferenceScores() {
        const list = document.getElementById('ref-scores-list');
        if (!list || !this.allModels) return;

        // Get Top 5 by Score
        const topModels = [...this.allModels]
            .filter(m => m.score !== undefined)
            .sort((a, b) => (b.score || 0) - (a.score || 0))
            .slice(0, 5);

        list.innerHTML = topModels.map(m => `
            <li style="display:flex; justify-content:space-between; margin-bottom:5px; border-bottom:1px solid #f1f5f9; padding-bottom:2px;">
                <span style="font-size:0.9em; colro:#334155;">${m.name}</span> 
                <span style="font-weight:bold; color:${m.score > 80 ? '#16a34a' : '#f59e0b'}">${m.score}</span>
            </li>
        `).join('');
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
            document.getElementById('model-provider').value = model.provider || 'openai_compatible';
            document.getElementById('model-family').value = model.family || 'other';
            document.getElementById('model-tier').value = model.tier || 'medium';

            document.getElementById('model-model-id').value = model.model_id;
            document.getElementById('model-base-url').value = model.base_url || '';
            document.getElementById('model-description').value = model.description || '';
            document.getElementById('model-enabled').checked = model.enabled !== false;
            document.getElementById('model-score').value = model.score || 100;

            this.updateReferenceScores();

            // Parameters
            const params = model.parameters || {};
            document.getElementById('model-temp').value = params.temperature !== undefined ? params.temperature : '';
            document.getElementById('model-max-tokens').value = params.max_tokens || '';
            document.getElementById('model-top-p').value = params.top_p !== undefined ? params.top_p : '';

            // Usage Checkboxes
            const usages = model.usage || ['chat'];
            document.querySelectorAll('input[name="usage"]').forEach(cb => {
                cb.checked = usages.includes(cb.value);
            });

            document.getElementById('model-api-key').value = '';
            document.getElementById('model-api-key').placeholder = model.has_api_key ? '(Configurada - dejar vacío)' : 'Añadir API Key';

            document.getElementById('btn-reset-score').style.display = 'block';
            document.getElementById('model-modal').style.display = 'block';
        } catch (error) {
            console.error('Error loading model:', error);
            alert('Error al cargar modelo');
        }
    }

    async resetScore() {
        if (!this.editingModelId) return;
        if (!confirm('¿Resetear puntuación a 100 y desbloquear modelo?')) return;

        try {
            const response = await fetch(`${this.apiBase}/${this.editingModelId}/reset`, { method: 'POST' });
            if (response.ok) {
                alert('Puntuación reseteada.');
                this.closeModal();
                this.loadModels();
            } else {
                alert('Error al resetear.');
            }
        } catch (e) {
            console.error(e);
            alert('Error al conectar.');
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
            family: document.getElementById('model-family').value,
            tier: document.getElementById('model-tier').value,
            model_id: document.getElementById('model-model-id').value,
            base_url: document.getElementById('model-base-url').value || null,
            description: document.getElementById('model-description').value || null,
            enabled: document.getElementById('model-enabled').checked,
            score: parseInt(document.getElementById('model-score').value) || 100,
            usage: Array.from(document.querySelectorAll('input[name="usage"]:checked')).map(cb => cb.value),
            parameters: {
                temperature: parseFloat(document.getElementById('model-temp').value) || 0.7,
                max_tokens: parseInt(document.getElementById('model-max-tokens').value) || null,
                top_p: parseFloat(document.getElementById('model-top-p').value) || null
            }
        };

        // Cleanup null params
        if (!modelData.parameters.max_tokens) delete modelData.parameters.max_tokens;
        if (!modelData.parameters.top_p) delete modelData.parameters.top_p;

        const apiKey = document.getElementById('model-api-key').value;
        if (apiKey) {
            modelData.api_key = apiKey;
        }

        try {
            const method = this.editingModelId ? 'PUT' : 'POST';
            const url = this.editingModelId ? `${this.apiBase}/${this.editingModelId}` : `${this.apiBase}/`;

            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(modelData)
            });

            if (response.ok) {
                alert('Modelo guardado correctamente');
                this.closeModal();
                this.loadModels();
            } else {
                const result = await response.json();
                alert('Error: ' + (result.detail || 'Error desconocido'));
            }
        } catch (error) {
            console.error('Error saving model:', error);
            alert('Error al guardar modelo');
        }
    }

    async deleteModel(modelId) {
        if (!confirm('¿Estás seguro de eliminar este modelo?')) return;

        try {
            const response = await fetch(`${this.apiBase}/${modelId}`, { method: 'DELETE' });
            if (response.ok) {
                this.loadModels();
            } else {
                alert('Error al eliminar modelo');
            }
        } catch (error) {
            console.error('Error deleting model:', error);
        }
    }


    async openKeysModal() {
        const modal = document.getElementById('keys-modal');
        const list = document.getElementById('keys-list');
        list.innerHTML = '<div style="text-align: center; color: #666;">Cargando claves...</div>';
        modal.style.display = 'block';

        try {
            const response = await fetch(`${this.apiBase}/keys`);
            const data = await response.json();

            list.innerHTML = '';
            data.forEach(item => {
                const row = document.createElement('div');
                row.style.marginBottom = '15px';
                row.style.padding = '10px';
                row.style.background = item.has_value ? '#f0fdf4' : '#fef2f2';
                row.style.border = `1px solid ${item.has_value ? '#86efac' : '#fecaca'}`;
                row.style.borderRadius = '6px';

                row.innerHTML = `
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="font-weight:600; font-family:monospace; color:#334155;">${item.key}</span>
                        <span style="font-size:0.8em; ${item.has_value ? 'color:#15803d' : 'color:#b91c1c'}">
                            ${item.has_value ? '✅ Configurada' : '❌ Vacía'}
                        </span>
                    </div>
                    <input type="text" class="key-input" data-key="${item.key}" 
                        placeholder="${item.has_value ? `Actual: ${item.masked} (Escribe para cambiar)` : 'Escribe la API Key aquí...'}"
                        style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:4px; font-family:monospace;">
                `;
                list.appendChild(row);
            });

        } catch (e) {
            list.innerHTML = '<div style="color:red; text-align:center;">Error al cargar claves.</div>';
            console.error(e);
        }
    }

    async saveKeys() {
        const inputs = document.querySelectorAll('.key-input');
        const updates = {};

        inputs.forEach(input => {
            const val = input.value.trim();
            if (val) {
                updates[input.dataset.key] = val;
            }
        });

        if (Object.keys(updates).length === 0) {
            alert('No has introducido cambios.');
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/keys`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keys: updates })
            });

            if (response.ok) {
                alert('Claves guardadas correctamente. Es posible que debas reiniciar para algunos cambios.');
                this.closeKeysModal();
            } else {
                alert('Error al guardar claves.');
            }
        } catch (e) {
            console.error(e);
            alert('Error de conexión.');
        }
    }

    closeKeysModal() {
        document.getElementById('keys-modal').style.display = 'none';
    }
}
