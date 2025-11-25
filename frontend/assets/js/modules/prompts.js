export class PromptModule {
    constructor() {
        this.apiBase = '/api/prompts';
    }

    init() {
        const form = document.getElementById('prompt-form');
        if (form) {
            form.addEventListener('submit', (e) => this.savePrompt(e));
        }
        this.loadPrompts();
    }

    async loadPrompts() {
        try {
            const response = await fetch(`${this.apiBase}/`);
            const data = await response.json();

            if (data.success && data.configs) {
                this.renderPromptsList(data.configs);
            }
        } catch (error) {
            console.error('Error loading prompts:', error);
        }
    }

    renderPromptsList(configs) {
        // Create a list container if it doesn't exist
        let listContainer = document.getElementById('prompts-list');
        if (!listContainer) {
            const card = document.querySelector('#view-prompts .card');
            listContainer = document.createElement('div');
            listContainer.id = 'prompts-list';
            listContainer.style.marginTop = '20px';
            card.appendChild(listContainer);
        }

        listContainer.innerHTML = '<h4>Configuraciones Guardadas</h4>';

        if (configs.length === 0) {
            listContainer.innerHTML += '<p>No hay configuraciones guardadas.</p>';
            return;
        }

        const ul = document.createElement('ul');
        ul.style.listStyle = 'none';
        ul.style.padding = '0';

        configs.forEach(config => {
            const li = document.createElement('li');
            li.style.padding = '10px';
            li.style.borderBottom = '1px solid #eee';
            li.style.display = 'flex';
            li.style.justifyContent = 'space-between';
            li.innerHTML = `
                <span><strong>${config.name}</strong> (${config.complexity_level})</span>
                <button class="btn small" onclick="alert('Cargar no implementado')">Cargar</button>
            `;
            ul.appendChild(li);
        });
        listContainer.appendChild(ul);
    }

    async savePrompt(e) {
        e.preventDefault();

        const name = document.getElementById('prompt-name').value;
        const level = document.getElementById('prompt-level').value;
        const system = document.getElementById('prompt-system').value;

        const config = {
            name: name,
            complexity_level: level,
            system_prompt: system,
            user_prompt_template: "{input}" // Default for now
        };

        try {
            const response = await fetch(`${this.apiBase}/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await response.json();
            if (data.success) {
                alert('Configuración guardada correctamente');
            }
        } catch (error) {
            console.error('Error saving prompt:', error);
            alert('Error al guardar');
        }
    }
}
