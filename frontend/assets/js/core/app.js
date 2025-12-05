import { ArticleModule } from '../modules/articles.js';
import { PromptModule } from '../modules/prompts.js';
import { ChatModule } from '../modules/chat.js';
import { ModelsModule } from '../modules/models.js';
import { DatabaseConfigModule } from '../modules/database_config.js';

class App {
    constructor() {
        this.currentView = 'dashboard';
        this.modules = {
            articles: new ArticleModule(),
            prompts: new PromptModule(),
            chat: new ChatModule(),
            models: new ModelsModule(),
            databaseConfig: new DatabaseConfigModule()
        };
        this.init();
    }

    init() {
        this.setupNavigation();
        this.modules.articles.init();
        this.modules.prompts.init();
        this.modules.chat.init();
        this.modules.models.init();
        this.modules.databaseConfig.init();
    }

    setupNavigation() {
        const navItems = document.querySelectorAll('nav li');
        navItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const view = e.target.dataset.view;
                this.navigate(view);
            });
        });
    }

    navigate(viewName) {
        // Update Nav
        document.querySelectorAll('nav li').forEach(li => li.classList.remove('active'));
        document.querySelector(`nav li[data-view="${viewName}"]`).classList.add('active');

        // Update View
        document.querySelectorAll('.view-section').forEach(el => el.style.display = 'none');
        const viewEl = document.getElementById(`view-${viewName}`);
        if (viewEl) {
            viewEl.style.display = 'block';
        }

        // Update Header
        const titles = {
            'dashboard': 'Dashboard',
            'articles': 'Gestión de Artículos',
            'prompts': 'Configuración de Prompts',
            'models': 'Modelos IA',
            'chat': 'Chat IA',
            'database-config': 'Configuración Base de Datos'
        };
        document.getElementById('page-title').textContent = titles[viewName] || 'DEVIA';

        this.currentView = viewName;
    }
}

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
