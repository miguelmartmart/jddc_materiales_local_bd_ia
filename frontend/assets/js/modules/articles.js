export class ArticleModule {
    constructor() {
        this.apiBase = '/api/articles';
    }

    init() {
        const loadBtn = document.getElementById('btn-load-articles');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => this.loadArticles());
        }

        const analyzeBtn = document.getElementById('btn-analyze-all');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => this.analyzeAll());
        }

        this.loadModels();
    }

    async loadModels() {
        try {
            const response = await fetch('/api/models/?enabled_only=true');
            const models = await response.json();

            const selector = document.getElementById('articles-model-selector');
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

    async loadArticles() {
        try {
            const params = {
                host: "HOST1",
                port: 3050,
                database: "C:\\Distrito\\OBRAS\\Database\\JUANDEDI\\2021.fdb",
                username: "SYSDBA",
                password: "masterkey",
                table_name: "ARTICULO",
                field_name: "NOMBRE"
            };

            const response = await fetch(`${this.apiBase}/list?limit=10`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });

            const data = await response.json();
            if (data.success) {
                this.renderTable(data.results);
            } else {
                const errorMsg = data.error || data.detail || 'Unknown error';
                console.error('Server Error:', data);
                alert('Error loading articles: ' + errorMsg);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error connecting to API. Make sure backend is running.');
        }
    }

    renderTable(articles) {
        const tbody = document.querySelector('#articles-table tbody');
        tbody.innerHTML = '';

        articles.forEach(article => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${article.CODIGO || ''}</td>
                <td>${article.NOMBRE || ''}</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
            `;
            tbody.appendChild(tr);
        });
    }

    async analyzeAll() {
        const rows = document.querySelectorAll('#articles-table tbody tr');
        if (rows.length === 0) {
            alert('Primero carga los artículos.');
            return;
        }

        const modelSelector = document.getElementById('articles-model-selector');
        const selectedModel = modelSelector ? modelSelector.value : null;

        if (!selectedModel) {
            alert('Por favor selecciona un modelo IA');
            return;
        }

        alert(`Iniciando análisis de ${rows.length} artículos con ${modelSelector.options[modelSelector.selectedIndex].text}...`);

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            const nameCell = row.cells[1];
            const articleName = nameCell.textContent;

            row.style.backgroundColor = '#f0f9ff';

            try {
                const response = await fetch(`${this.apiBase}/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        article_name: articleName,
                        model_id: selectedModel
                    })
                });

                const data = await response.json();

                if (data.success && data.result) {
                    row.cells[2].textContent = data.result.material_principal || '-';
                    row.cells[3].textContent = data.result.categoria || '-';
                    row.cells[4].textContent = (data.result.confidence || 0) + '%';
                    row.style.backgroundColor = '#f0fff4';
                } else {
                    row.style.backgroundColor = '#fff5f5';
                }

            } catch (error) {
                console.error('Error analyzing:', articleName, error);
                row.style.backgroundColor = '#fff5f5';

                if (i === 0) {
                    alert('Error al analizar el primer artículo. Verifica tu API Key y conexión.\nDetalle: ' + error.message);
                }
            }
        }
        alert('Análisis completado.');
    }
}
