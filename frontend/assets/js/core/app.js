import { ArticleModule } from "../modules/articles.js";
import { PromptModule } from "../modules/prompts.js";
import { ChatModule } from "../modules/chat.js";
import { ModelsModule } from "../modules/models.js";
import { DatabaseConfigModule } from "../modules/database_config.js";
import { OutlookModule } from "../modules/outlook.js";
import { AnonymizerModule } from "../modules/anonymizer.js";
import { SimulatorModule } from "../modules/db_simulator.js";

class App {
  constructor() {
    this.currentView = "dashboard";
    this.modules = {
      articles: new ArticleModule(),
      prompts: new PromptModule(),
      chat: new ChatModule(),
      models: new ModelsModule(),
      databaseConfig: new DatabaseConfigModule(),
      outlook: new OutlookModule(),
      anonymizer: new AnonymizerModule(),
      simulator: new SimulatorModule(),
    };
    this._metadataBuilderInited = false;
    this._siuoInited = false;
    this.init();
  }

  init() {
    this.setupNavigation();
    this.modules.articles.init();
    this.modules.prompts.init();
    this.modules.chat.init();
    this.modules.models.init();
    this.modules.databaseConfig.init();
    this.modules.outlook.init();
    this.modules.anonymizer.init();
    this.modules.simulator.init();
  }

  setupNavigation() {
    const navItems = document.querySelectorAll("nav li");
    navItems.forEach((item) => {
      item.addEventListener("click", (e) => {
        const view = e.target.dataset.view;
        this.navigate(view);
      });
    });
  }

  navigate(viewName) {
    // Update Nav
    document
      .querySelectorAll("nav li")
      .forEach((li) => li.classList.remove("active"));
    const navEl = document.querySelector(`nav li[data-view="${viewName}"]`);
    if (navEl) {
      navEl.classList.add("active");
    } else {
      console.warn(`[App.navigate] No nav item found for view="${viewName}"`);
    }

    // Update View
    document
      .querySelectorAll(".view-section")
      .forEach((el) => (el.style.display = "none"));
    const viewEl = document.getElementById(`view-${viewName}`);
    if (viewEl) {
      viewEl.style.display = "block";
    } else {
      console.error(`[App.navigate] No view element found: #view-${viewName}`);
    }

    // Update Header
    const titles = {
      dashboard: "Dashboard",
      articles: "Gestión de Artículos",
      prompts: "Configuración de Prompts",
      models: "Modelos IA",
      chat: "Chat IA",
      "database-config": "Configuración Base de Datos",
      outlook: "Lector de Correos",
      anonymizer: "Anonimizador de Datos",
      "metadata-builder": "Constructor de Metadatos BD",
      "db-simulator": "🎭 BD Simulada — Simulador SQLite",
      siuo: "🧠 Índices SIUO — Sistema de Índices Ultra-Optimizado",
    };
    document.getElementById("page-title").textContent =
      titles[viewName] || "DEVIA";

    // Inicializar Constructor BD la primera vez que se navega a él
    if (viewName === "metadata-builder" && !this._metadataBuilderInited) {
      this._metadataBuilderInited = true;
      if (
        window.MetadataBuilder &&
        typeof window.MetadataBuilder.init === "function"
      ) {
        window.MetadataBuilder.init("mb-root");
      } else {
        console.error("[App.navigate] MetadataBuilder module not available");
        document.getElementById("mb-root").innerHTML =
          '<div style="padding:30px; color:#dc2626; background:#fef2f2; border-radius:8px; margin:20px;">' +
          "<strong>⚠️ Error:</strong> El módulo MetadataBuilder no está disponible.<br>" +
          '<small>Asegúrate de que el backend está corriendo en <a href="http://localhost:8001/api/metadata-builder/status" target="_blank">http://localhost:8001</a></small>' +
          "</div>";
      }
    }

    // Inicializar BD Simulada (lazy-init, se recarga en cada visita)
    if (viewName === "db-simulator") {
      try {
        this.modules.simulator.onEnter();
      } catch (err) {
        console.error("[App.navigate] SimulatorModule.onEnter() failed:", err);
        const root = document.getElementById("sim-root");
        if (root) {
          root.innerHTML =
            '<div style="padding:30px; color:#dc2626; background:#fef2f2; border-radius:8px; margin:20px;">' +
            "<strong>⚠️ Error al cargar BD Simulada:</strong> " +
            (err?.message || String(err)) +
            "<br><small>Revisa la consola del navegador para más detalles.</small>" +
            "</div>";
        }
      }
    }

    // Inicializar SIUO la primera vez que se navega a él (lazy-init)
    if (viewName === "siuo") {
      if (window.SIUOModule && typeof window.SIUOModule.init === "function") {
        window.SIUOModule.init();
      } else {
        console.error("[App.navigate] SIUOModule not available");
        document.getElementById("siuo-root").innerHTML =
          '<div style="padding:30px; color:#dc2626; background:#fef2f2; border-radius:8px; margin:20px;">' +
          "<strong>⚠️ Error:</strong> El módulo SIUO no está disponible.<br>" +
          '<small>Asegúrate de que el backend está corriendo en <a href="http://localhost:8001/api/siuo/stats" target="_blank">http://localhost:8001</a></small>' +
          "</div>";
      }
    }

    this.currentView = viewName;
  }
}

// Initialize App
document.addEventListener("DOMContentLoaded", () => {
  window.app = new App();
});
