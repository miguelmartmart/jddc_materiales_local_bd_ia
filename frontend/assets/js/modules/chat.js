import {
  API,
  DB_CONFIG,
  UI_MESSAGES,
  CHAT_ROLES,
  UI_STYLES,
  EVENTS,
  DOM_SELECTORS,
  HTTP_METHODS,
} from "../core/constants.js";

// ─── Renderer Markdown global (configurado UNA sola vez) ─────────────────────
// Se inicializa la primera vez que se llama a _renderMarkdown().
// Usar una función global evita reconfigurar marked en cada mensaje.
let _markedConfigured = false;

function _configureMarked() {
  if (_markedConfigured || typeof marked === "undefined") return;
  _markedConfigured = true;

  // Renderer personalizado compatible con marked v4+
  const renderer = {
    // Tablas GFM → envueltas en .chat-table-wrapper para scroll horizontal
    table(token) {
      // token.header: array de celdas de cabecera
      // token.rows: array de filas (cada fila es array de celdas)
      const headerCells = (token.header || [])
        .map((cell) => `<th>${cell.text || cell}</th>`)
        .join("");
      const bodyRows = (token.rows || [])
        .map(
          (row) =>
            `<tr>${row.map((cell) => `<td>${cell.text || cell}</td>`).join("")}</tr>`,
        )
        .join("");
      return (
        `<div class="chat-table-wrapper">` +
        `<table class="chat-table">` +
        `<thead><tr>${headerCells}</tr></thead>` +
        `<tbody>${bodyRows}</tbody>` +
        `</table></div>`
      );
    },
    // Bloques de código → NO mostrar al usuario no técnico
    // Los bloques ```sql ... ``` se ocultan completamente
    code(token) {
      const lang = (token.lang || "").toLowerCase();
      if (lang === "sql" || lang === "python" || lang === "bash" || lang === "sh") {
        // Ocultar código técnico — el usuario no sabe programación
        return "";
      }
      // Otros bloques de código: mostrar con estilo discreto
      const escaped = (token.text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      return `<pre class="chat-code-block"><code>${escaped}</code></pre>`;
    },
  };

  marked.use({
    gfm: true,
    breaks: true,
    renderer,
  });
}

/**
 * Renderiza texto Markdown a HTML seguro para el chat.
 * - Configura marked una sola vez (no en cada mensaje).
 * - Cierra bloques <details> abiertos (respuestas cortadas).
 * - Elimina bloques SQL visibles.
 * - Preserva HTML inline (<details>, <summary>, etc.).
 *
 * @param {string} text - Texto Markdown/HTML de la IA
 * @returns {string} HTML renderizado
 */
function _renderMarkdown(text) {
  if (!text || typeof text !== "string") return "";

  // 1. Configurar marked una sola vez
  _configureMarked();

  // 2. Reparar respuestas cortadas: cerrar <details> abiertos
  text = _repairTruncatedResponse(text);

  // 3. Renderizar Markdown → HTML
  let html;
  try {
    html = marked.parse(text);
  } catch (e) {
    // Fallback: escapar y mostrar como texto plano
    html = text.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
  }

  // 4. Post-proceso: añadir clase CSS al <details> generado por la IA
  html = html.replace(
    /<details>/gi,
    '<details class="chat-justification">',
  );

  return html;
}

/**
 * Repara respuestas truncadas por el modelo:
 * - Cierra bloques <details> abiertos
 * - Elimina bloques ```sql ... ``` que el modelo haya incluido por error
 * - Cierra listas/tablas incompletas
 */
function _repairTruncatedResponse(text) {
  // Eliminar bloques de código SQL/técnico que no deben verse
  text = text.replace(/```(?:sql|SQL|python|bash|sh)[^`]*```/gs, "");
  text = text.replace(/```[^`]*```/gs, (match) => {
    // Mantener bloques de código no técnicos (ej: texto plano)
    const lang = match.match(/```(\w*)/)?.[1]?.toLowerCase() || "";
    if (["sql", "python", "bash", "sh", "javascript", "js"].includes(lang)) {
      return "";
    }
    return match;
  });

  // Contar <details> y </details> para cerrar los que faltan
  const openCount = (text.match(/<details[^>]*>/gi) || []).length;
  const closeCount = (text.match(/<\/details>/gi) || []).length;
  const missing = openCount - closeCount;
  if (missing > 0) {
    // La respuesta fue cortada dentro de un <details>
    // Añadir contenido mínimo y cerrar
    text += "\n\n*(Información adicional disponible — consulta al asistente para más detalles)*\n\n";
    for (let i = 0; i < missing; i++) {
      text += "\n</details>";
    }
  }

  return text;
}

export class ChatModule {
  constructor() {
    this.apiBase = API.ENDPOINTS.CHAT;
    this.conversationHistory = [];
    this.pendingImages = [];
    this.currentSessionId = null; // Track active session
  }

  init() {
    const sendBtn = document.getElementById(DOM_SELECTORS.CHAT.SEND_BTN);
    const input = document.getElementById(DOM_SELECTORS.CHAT.INPUT);

    if (sendBtn && input) {
      const newBtn = sendBtn.cloneNode(true);
      sendBtn.parentNode.replaceChild(newBtn, sendBtn);

      const newInput = input.cloneNode(true);
      input.parentNode.replaceChild(newInput, input);

      const attachBtn = document.getElementById(DOM_SELECTORS.CHAT.ATTACH_BTN);
      const fileInput = document.getElementById(DOM_SELECTORS.CHAT.FILE_INPUT);

      if (attachBtn && fileInput) {
        attachBtn.addEventListener(EVENTS.CLICK, () => fileInput.click());
        fileInput.addEventListener("change", (e) => this.handleFileSelect(e));
      }

      newBtn.addEventListener(EVENTS.CLICK, () => this.sendMessage());
      newInput.addEventListener(EVENTS.KEYPRESS, (e) => {
        if (e.key === EVENTS.ENTER_KEY && !e.shiftKey) {
          e.preventDefault(); // Prevent new line on Enter
          this.sendMessage();
        }
      });

      // Initialize paste listener for images
      newInput.addEventListener("paste", (e) => {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (let index in items) {
          const item = items[index];
          if (item.kind === "file" && item.type.startsWith("image/")) {
            const blob = item.getAsFile();
            const reader = new FileReader();
            reader.onload = (event) => {
              this.pendingImages.push(event.target.result);
              this.renderPreview();
            };
            reader.readAsDataURL(blob);
            e.preventDefault(); // Prevent pasting the image filename as text
          }
        }
      });

      // New Chat & History Buttons
      const btnNewChat = document.getElementById("btn-new-chat");
      if (btnNewChat) {
        btnNewChat.addEventListener("click", () => this.startNewChat());
      }

      const btnToggleHistory = document.getElementById("btn-toggle-history");
      if (btnToggleHistory) {
        btnToggleHistory.addEventListener("click", () => {
          const sidebar = document.getElementById("chat-history-sidebar");
          if (sidebar) {
            sidebar.classList.toggle("collapsed");
            btnToggleHistory.title = sidebar.classList.contains("collapsed")
              ? "Mostrar Historial"
              : "Ocultar Historial";
          }
        });
      }
    }

    // ── DB mode selector badge update ────────────────────────────────────────
    const dbModeSelector = document.getElementById("chat-db-mode");
    const dbModeBadge = document.getElementById("chat-db-mode-badge");
    if (dbModeSelector && dbModeBadge) {
      const _updateBadge = () => {
        const mode = dbModeSelector.value;
        const badges = {
          real:      { text: "🔥 Real",      bg: "#d1fae5", color: "#065f46", border: "#a7f3d0" },
          simulator: { text: "🎭 Simulada",  bg: "#fef3c7", color: "#92400e", border: "#fde68a" },
          no_db:     { text: "💬 Sin BD",    bg: "#f1f5f9", color: "#475569", border: "#cbd5e1" },
        };
        const b = badges[mode] || badges.real;
        dbModeBadge.textContent = b.text;
        dbModeBadge.style.background = b.bg;
        dbModeBadge.style.color = b.color;
        dbModeBadge.style.border = `1px solid ${b.border}`;
        // Also update selector border color
        dbModeSelector.style.borderColor = b.border;
        dbModeSelector.style.background = b.bg;
        dbModeSelector.style.color = b.color;
      };
      dbModeSelector.addEventListener("change", _updateBadge);
      _updateBadge(); // Init badge on load
    }

    this.loadModels();
    this.loadHistory(); // Load history on init
    this.initChatConfig();
  }

  initChatConfig() {
    const btnConfig = document.getElementById("btn-chat-config");
    const modal = document.getElementById("chat-config-modal");
    const btnCancel = document.getElementById("btn-cancel-chat-config");
    const btnSave = document.getElementById("btn-save-chat-config");
    const inputRetries = document.getElementById("chat-config-retries");

    if (btnConfig && modal) {
      btnConfig.addEventListener("click", async () => {
        await this.loadChatConfig();
        modal.style.display = "flex";
      });

      if (btnCancel)
        btnCancel.addEventListener(
          "click",
          () => (modal.style.display = "none"),
        );

      if (btnSave) {
        btnSave.addEventListener("click", async () => {
          const retries = parseInt(inputRetries.value, 10);
          if (isNaN(retries) || retries < 0) {
            alert("Por favor ingrese un número válido.");
            return;
          }
          await this.saveChatConfig(retries);
          modal.style.display = "none";
        });
      }

      // Close on click outside
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.style.display = "none";
      });
    }

    this.initFullHistory();
  }

  initFullHistory() {
    const btnHistory = document.getElementById("btn-chat-full-history");
    const modal = document.getElementById("chat-full-history-modal");

    if (btnHistory && modal) {
      btnHistory.addEventListener("click", () => {
        this.loadFullHistory();
        modal.showModal();
      });

      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.close();
      });
    }
  }

  async loadFullHistory() {
    try {
      const container = document.getElementById("full-history-sessions");
      container.innerHTML =
        '<div style="padding:20px; text-align:center; color:#999;">Cargando historial...</div>';

      const response = await fetch(`${this.apiBase}/history/all`);
      if (response.ok) {
        const data = await response.json();
        this.renderFullHistorySessions(data);
      } else {
        container.innerHTML =
          '<div style="color:red; padding:20px;">Error cargando historial</div>';
      }
    } catch (error) {
      console.error("Error loading full history:", error);
    }
  }

  renderFullHistorySessions(data) {
    const container = document.getElementById("full-history-sessions");
    container.innerHTML = "";

    if (data.length === 0) {
      container.innerHTML =
        '<div style="padding:20px; text-align:center; color:#999;">No hay historial</div>';
      return;
    }

    data.forEach((item, index) => {
      const div = document.createElement("div");
      div.style.padding = "15px";
      div.style.borderBottom = "1px solid #eee";
      div.style.cursor = "pointer";
      div.style.transition = "background 0.2s";
      div.className = "history-session-item";

      const date = new Date(item.session.created_at).toLocaleString();
      div.innerHTML = `
                <div style="font-weight:600; font-size:0.9em; margin-bottom:5px; color:#1e293b; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;">
                    ${item.session.title || "Sin título"}
                </div>
                <div style="font-size:0.8em; color:#64748b;">
                    ${date}
                </div>
                <div style="font-size:0.75em; color:#94a3b8; margin-top:3px;">
                    ${item.messages.length} mensajes
                </div>
            `;

      div.addEventListener("click", () => {
        // Highlight active
        document
          .querySelectorAll(".history-session-item")
          .forEach((el) => (el.style.background = "white"));
        div.style.background = "#e0f2fe";
        this.renderFullHistoryMessages(item);
      });

      container.appendChild(div);

      // Auto-select first
      if (index === 0) div.click();
    });
  }

  renderFullHistoryMessages(item) {
    const container = document.getElementById("full-history-messages");
    container.innerHTML = "";

    const header = document.createElement("div");
    header.style.marginBottom = "20px";
    header.style.paddingBottom = "10px";
    header.style.borderBottom = "1px solid #e2e8f0";
    header.innerHTML = `
            <h4 style="margin:0;">${item.session.title}</h4>
            <div style="font-size:0.85em; color:#64748b;">Modelo: ${item.session.model_id} | ID: ${item.session.id}</div>
        `;
    container.appendChild(header);

    item.messages.forEach((msg) => {
      const msgDiv = document.createElement("div");
      const isUser = msg.role === "user";

      msgDiv.style.marginBottom = "15px";
      msgDiv.style.padding = "12px 15px";
      msgDiv.style.borderRadius = "8px";
      msgDiv.style.maxWidth = "85%";
      msgDiv.style.marginLeft = isUser ? "auto" : "0";
      msgDiv.style.marginRight = isUser ? "0" : "auto";
      msgDiv.style.background = isUser ? "#dbeafe" : "white";
      msgDiv.style.border = isUser ? "none" : "1px solid #e2e8f0";
      msgDiv.style.boxShadow = "0 1px 2px rgba(0,0,0,0.05)";

      // Simple markdown-ish rendering for code blocks if needed,
      // but for history modal plain text with scroll is usually safer/cleaner
      // or simple replace for newlines
      let content = msg.content
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>");

      // Basic code block highlighting styling
      if (content.includes("```")) {
        content = content.replace(
          /```([\s\S]*?)```/g,
          '<pre style="background:#1e293b; color:#fff; padding:10px; border-radius:4px; overflow-x:auto;">$1</pre>',
        );
      }

      msgDiv.innerHTML = `
                <div style="font-weight:600; font-size:0.8em; margin-bottom:5px; color:${isUser ? "#1e40af" : "#059669"};">
                    ${isUser ? "👤 Usuario" : "🤖 IA"}
                </div>
                <div style="font-size:0.95em; line-height:1.5; color:#334155;">${content}</div>
                <div style="font-size:0.75em; color:#94a3b8; text-align:right; margin-top:5px;">
                    ${new Date(msg.created_at).toLocaleTimeString()}
                </div>
            `;
      container.appendChild(msgDiv);
    });
  }

  async loadChatConfig() {
    try {
      const response = await fetch(`${this.apiBase}/config`);
      if (response.ok) {
        const config = await response.json();
        const input = document.getElementById("chat-config-retries");
        if (input && config.max_sql_retries !== undefined) {
          input.value = config.max_sql_retries;
        }
      }
    } catch (error) {
      console.error("Error loading chat config:", error);
    }
  }

  async saveChatConfig(retries) {
    try {
      const response = await fetch(`${this.apiBase}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_sql_retries: retries }),
      });

      if (response.ok) {
        // Optional: Show toast
        alert("Configuración guardada correctamente.");
      } else {
        alert("Error guardando configuración.");
      }
    } catch (error) {
      console.error("Error saving chat config:", error);
      alert("Error de conexión.");
    }
  }

  async loadHistory() {
    try {
      const listContainer = document.getElementById("history-list");
      if (!listContainer) return;

      const response = await fetch(`${this.apiBase}/history`);
      const sessions = await response.json();

      if (sessions.length === 0) {
        listContainer.innerHTML =
          '<div style="text-align: center; color: #94a3b8; font-size: 0.9em; margin-top: 20px;">No hay historial</div>';
        return;
      }

      listContainer.innerHTML = sessions
        .map(
          (session) => `
                <div class="history-item" data-id="${session.id}" style="padding: 10px; cursor: pointer; border-radius: 6px; margin-bottom: 5px; color: #334155; font-size: 0.9em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; background: ${session.id === this.currentSessionId ? "#e0f2fe" : "transparent"}; border: 1px solid ${session.id === this.currentSessionId ? "#bae6fd" : "transparent"};">
                    ${session.title || "Nueva conversación"}
                    <div style="font-size: 0.75em; color: #94a3b8;">${new Date(session.updated_at).toLocaleDateString()}</div>
                </div>
            `,
        )
        .join("");

      // Add click listeners
      listContainer.querySelectorAll(".history-item").forEach((item) => {
        item.addEventListener("click", () => this.loadSession(item.dataset.id));
      });
    } catch (error) {
      console.error("Error loading history:", error);
    }
  }

  async loadSession(sessionId) {
    if (this.currentSessionId === sessionId) return;

    this.currentSessionId = sessionId;
    this.conversationHistory = []; // Reset local history/context

    // UI Update: Highlight active
    this.loadHistory(); // Re-render to update highlight

    const messagesArea = document.getElementById("chat-messages");
    messagesArea.innerHTML =
      '<div style="text-align:center; padding:20px; color:#666;">Cargando conversación...</div>';

    try {
      const response = await fetch(`${this.apiBase}/history/${sessionId}`);
      const data = await response.json();

      messagesArea.innerHTML = ""; // Clear loading

      // Replay messages
      if (data.messages) {
        // Initial greeting not from DB, but maybe should be?
        // Let's keep the generic one if empty? No, load real history.

        data.messages.forEach((msg) => {
          let images = null;
          if (msg.meta && msg.meta.images_count) {
            // TODO: store images in DB? or just placeholder?
            // Current impl doesn't return image B64 from history to save space likely.
          }

          // Add to context for next requests
          this.conversationHistory.push({
            role: msg.role,
            content: msg.content,
          });

          // Render
          // Parse if meta indicates structured content?
          let content = msg.content;
          if (msg.meta && msg.meta.is_structured) {
            try {
              const parsed = JSON.parse(content);
              if (parsed.data_preview) {
                content = `[Solicitud de Confirmación] ${parsed.total_rows} registros encontrados.`;
              }
            } catch (e) {}
          }

          this.appendMessage(
            msg.role === "user" ? CHAT_ROLES.USER : CHAT_ROLES.AI,
            content,
          );
        });
      }
    } catch (error) {
      messagesArea.innerHTML = `<div style="color:red; text-align:center;">Error cargando chat: ${error.message}</div>`;
    }
  }

  startNewChat() {
    this.currentSessionId = null;
    this.conversationHistory = [];
    document.getElementById("chat-messages").innerHTML = `
            <div class="message ai" style="background: #f5f5f5; padding: 10px; border-radius: 8px; max-width: 80%;">
                Hola, soy DEVIA. ¿En qué puedo ayudarte hoy?
            </div>
        `;
    this.loadHistory(); // Remove highlight
  }

  async loadModels() {
    try {
      const response = await fetch(API.ENDPOINTS.MODELS_ENABLED);
      const models = await response.json();

      const selector = document.getElementById(
        DOM_SELECTORS.CHAT.MODEL_SELECTOR,
      );
      if (selector) {
        selector.innerHTML = models
          .map((m) => `<option value="${m.id}">${m.name}</option>`)
          .join("");

        if (models.length > 0) {
          // Preseleccionar modelo JDDCIA/Qwen local si está disponible
          // Prioridad: jddcia > qwen > local > primero de la lista
          const PREFERRED_KEYWORDS = ["jddcia", "qwen", "local", "lan"];
          const preferred = models.find((m) =>
            PREFERRED_KEYWORDS.some(
              (kw) =>
                m.id.toLowerCase().includes(kw) ||
                (m.name || "").toLowerCase().includes(kw),
            ),
          );
          selector.value = preferred ? preferred.id : models[0].id;

          // Indicador visual si es modelo local
          if (preferred) {
            selector.title = `🏠 Modelo local seleccionado: ${preferred.name || preferred.id}`;
          }
        }
      }
    } catch (error) {
      console.error("Error loading models:", error);
      // Fallback: mostrar opción manual
      const selector = document.getElementById(
        DOM_SELECTORS.CHAT.MODEL_SELECTOR,
      );
      if (selector) {
        selector.innerHTML =
          '<option value="">Sin conexión — modelos no disponibles</option>';
      }
    }
  }

  async sendMessage() {
    const input = document.getElementById(DOM_SELECTORS.CHAT.INPUT);
    const message = input.value.trim();
    const modelSelector = document.getElementById(
      DOM_SELECTORS.CHAT.MODEL_SELECTOR,
    );
    const selectedModel = modelSelector ? modelSelector.value : null;

    if (!message) return;

    if (!selectedModel) {
      alert(UI_MESSAGES.SELECT_MODEL);
      return;
    }

    this.appendMessage(CHAT_ROLES.USER, message, null, this.pendingImages);
    this.conversationHistory.push({ role: "user", content: message });

    const imagesToSend = [...this.pendingImages];
    this.pendingImages = [];
    this.renderPreview();
    input.value = "";

    const thinkingId = "thinking-" + Date.now();
    this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.THINKING, thinkingId);

    try {
      const dbParams = {
        host: DB_CONFIG.HOST,
        port: DB_CONFIG.PORT,
        database: DB_CONFIG.DATABASE,
        username: DB_CONFIG.USERNAME,
        password: DB_CONFIG.PASSWORD,
      };

      // Leer estado del checkbox de análisis profundo
      const deepToggle = document.getElementById("deep-analysis-toggle");
      const deepAnalysisEnabled = deepToggle ? deepToggle.checked : false;

      // Leer selector de modo BD (real / simulator / no_db)
      const dbModeSelector = document.getElementById("chat-db-mode");
      const dbMode = dbModeSelector ? dbModeSelector.value : "real";

      // Derivar flags de compatibilidad desde el selector unificado
      const noDbMode = dbMode === "no_db";
      const useSimulator = dbMode === "simulator";

      // Leer selector de motor LAN (30B vs 8B)
      const lanSelector = document.getElementById("chat-lan-model-selector");
      const preferred_model_id = lanSelector ? lanSelector.value : null;

      const response = await fetch(`${this.apiBase}/send`, {
        method: HTTP_METHODS.POST,
        headers: { "Content-Type": API.HEADERS.CONTENT_TYPE },
        body: JSON.stringify({
          message: message,
          db_params: noDbMode ? null : dbParams, // Sin BD → no enviar params
          model_id: selectedModel,
          preferred_model_id: preferred_model_id, // Motor LAN preferido (30B / 8B)
          conversation_history: this.conversationHistory,
          images: imagesToSend,
          session_id: this.currentSessionId, // Send current session ID
          deep_analysis: deepAnalysisEnabled, // 🔬 Checkbox análisis profundo
          no_db: noDbMode, // 💬 Checkbox sin BD
          db_mode: dbMode, // 🗄️ Modo BD explícito: real | simulator | no_db
          use_simulator: useSimulator, // 🎭 Forzar simulador aunque haya params reales
        }),
      });

      const data = await response.json();

      // Update Session ID if created new
      if (data.session_id) {
        this.currentSessionId = data.session_id;
        this.loadHistory(); // Refresh list to show new title
      }

      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) thinkingEl.remove();

      if (data.success) {
        // Check if confirmation is required
        if (data.response && data.response.status === "confirmation_required") {
          this.showConfirmationModal(data.response, message, selectedModel);
        } else {
          this.appendMessage(CHAT_ROLES.AI, data.response);
          this.conversationHistory.push({
            role: "assistant",
            content: data.response,
          });
        }
      } else {
        this.appendMessage(
          CHAT_ROLES.AI,
          UI_MESSAGES.ERROR_GENERIC +
            (data.response || UI_MESSAGES.ERROR_UNKNOWN),
        );
      }
    } catch (error) {
      console.error("Chat Error:", error);
      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) thinkingEl.remove();
      this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.ERROR_CONNECTION);
    }
  }

  showConfirmationModal(data, originalMessage, modelId) {
    // Remove existing modal if any
    const existingModal = document.getElementById("confirmation-modal");
    if (existingModal) existingModal.remove();

    const modalOverlay = document.createElement("div");
    modalOverlay.id = "confirmation-modal";
    modalOverlay.style.position = "fixed";
    modalOverlay.style.top = "0";
    modalOverlay.style.left = "0";
    modalOverlay.style.width = "100%";
    modalOverlay.style.height = "100%";
    modalOverlay.style.backgroundColor = "rgba(0,0,0,0.5)";
    modalOverlay.style.display = "flex";
    modalOverlay.style.justifyContent = "center";
    modalOverlay.style.alignItems = "center";
    modalOverlay.style.zIndex = "1000";

    const modalContent = document.createElement("div");
    modalContent.style.backgroundColor = "white";
    modalContent.style.padding = "20px";
    modalContent.style.borderRadius = "8px";
    modalContent.style.maxWidth = "80%";
    modalContent.style.maxHeight = "80%";
    modalContent.style.overflow = "auto";
    modalContent.style.boxShadow = "0 4px 6px rgba(0,0,0,0.1)";

    const title = document.createElement("h3");
    title.textContent = "⚠️ Confirmar Envío de Datos";
    title.style.marginTop = "0";
    title.style.color = "#d32f2f";

    const message = document.createElement("p");
    message.textContent = `Se han encontrado ${data.total_rows} registros. ¿Deseas enviarlos a la IA para su análisis?`;

    const previewTitle = document.createElement("h4");
    previewTitle.textContent = "Vista Previa (Primeros 5 registros):";
    previewTitle.style.marginTop = "15px";

    const pre = document.createElement("pre");
    pre.style.backgroundColor = "#f5f5f5";
    pre.style.padding = "10px";
    pre.style.borderRadius = "4px";
    pre.style.overflowX = "auto";
    pre.style.fontSize = "12px";
    pre.textContent = JSON.stringify(data.data_preview, null, 2);

    const buttonContainer = document.createElement("div");
    buttonContainer.style.display = "flex";
    buttonContainer.style.justifyContent = "flex-end";
    buttonContainer.style.gap = "10px";
    buttonContainer.style.marginTop = "20px";

    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = "Cancelar";
    cancelBtn.style.padding = "8px 16px";
    cancelBtn.style.border = "1px solid #ccc";
    cancelBtn.style.borderRadius = "4px";
    cancelBtn.style.backgroundColor = "white";
    cancelBtn.style.cursor = "pointer";
    cancelBtn.onclick = () => {
      modalOverlay.remove();
      this.appendMessage(
        CHAT_ROLES.AI,
        "❌ Envío de datos cancelado por el usuario.",
      );
    };

    const confirmBtn = document.createElement("button");
    confirmBtn.textContent = "Confirmar y Analizar";
    confirmBtn.style.padding = "8px 16px";
    confirmBtn.style.border = "none";
    confirmBtn.style.borderRadius = "4px";
    confirmBtn.style.backgroundColor = "#1976d2";
    confirmBtn.style.color = "white";
    confirmBtn.style.cursor = "pointer";
    confirmBtn.onclick = () => {
      modalOverlay.remove();
      this.confirmAndSend(originalMessage, modelId);
    };

    buttonContainer.appendChild(cancelBtn);
    buttonContainer.appendChild(confirmBtn);

    modalContent.appendChild(title);
    modalContent.appendChild(message);
    modalContent.appendChild(previewTitle);
    modalContent.appendChild(pre);
    modalContent.appendChild(buttonContainer);
    modalOverlay.appendChild(modalContent);

    document.body.appendChild(modalOverlay);
  }

  async confirmAndSend(message, modelId) {
    const thinkingId = "thinking-confirm-" + Date.now();
    this.appendMessage(
      CHAT_ROLES.AI,
      "✅ Datos confirmados. Analizando...",
      thinkingId,
    );

    try {
      const dbParams = {
        host: DB_CONFIG.HOST,
        port: DB_CONFIG.PORT,
        database: DB_CONFIG.DATABASE,
        username: DB_CONFIG.USERNAME,
        password: DB_CONFIG.PASSWORD,
        confirm_data_sending: true, // FLAG CRITICA
      };

      const response = await fetch(`${this.apiBase}/send`, {
        method: HTTP_METHODS.POST,
        headers: { "Content-Type": API.HEADERS.CONTENT_TYPE },
        body: JSON.stringify({
          message: message,
          db_params: dbParams,
          model_id: modelId,
          conversation_history: this.conversationHistory,
          confirm_data_sending: true,
          session_id: this.currentSessionId,
        }),
      });

      const data = await response.json();

      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) thinkingEl.remove();

      if (data.success) {
        this.appendMessage(CHAT_ROLES.AI, data.response);
        this.conversationHistory.push({
          role: "assistant",
          content: data.response,
        });
      } else {
        this.appendMessage(
          CHAT_ROLES.AI,
          UI_MESSAGES.ERROR_GENERIC +
            (data.response || UI_MESSAGES.ERROR_UNKNOWN),
        );
      }
    } catch (error) {
      console.error("Confirmation Error:", error);
      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) thinkingEl.remove();
      this.appendMessage(CHAT_ROLES.AI, UI_MESSAGES.ERROR_CONNECTION);
    }
  }

  appendMessage(role, text, id = null, images = null) {
    const messagesArea = document.getElementById("chat-messages");
    if (!messagesArea) return;

    const msgDiv = document.createElement("div");
    if (id) msgDiv.id = id;
    msgDiv.className = `message ${role}`;
    msgDiv.style.marginBottom = "10px";
    msgDiv.style.padding = "10px";
    msgDiv.style.borderRadius = "8px";
    msgDiv.style.maxWidth = "80%";

    if (role === "user") {
      msgDiv.style.backgroundColor = "#e3f2fd";
      msgDiv.style.marginLeft = "auto";
      msgDiv.style.textAlign = "right";
    } else {
      msgDiv.style.backgroundColor = "#f5f5f5";
      msgDiv.style.marginRight = "auto";
    }

    if (images && images.length > 0) {
      const imgContainer = document.createElement("div");
      imgContainer.style.display = "flex";
      imgContainer.style.gap = "5px";
      imgContainer.style.marginBottom = "5px";
      imgContainer.style.flexWrap = "wrap";
      imgContainer.style.justifyContent =
        role === "user" ? "flex-end" : "flex-start";

      images.forEach((imgB64) => {
        const img = document.createElement("img");
        img.src = imgB64; // Already has data:image... header from FileReader
        img.style.maxWidth = "100px";
        img.style.maxHeight = "100px";
        img.style.borderRadius = "4px";
        imgContainer.appendChild(img);
      });
      msgDiv.appendChild(imgContainer);
    }

    const textDiv = document.createElement("div");
    textDiv.className = "chat-markdown-body";
    // Render Markdown if available
    if (typeof marked !== "undefined") {
      textDiv.innerHTML = _renderMarkdown(text);

      // Add custom styles for images in markdown
      const imagesInMd = textDiv.querySelectorAll("img");
      imagesInMd.forEach((img) => {
        img.style.maxWidth = "100%";
        img.style.borderRadius = "8px";
        img.style.marginTop = "10px";
        img.style.boxShadow = "0 2px 4px rgba(0,0,0,0.1)";
      });
    } else {
      // Fallback: escapar HTML y mostrar texto plano
      textDiv.textContent = text;
    }
    msgDiv.appendChild(textDiv);

    messagesArea.appendChild(msgDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }

  handleFileSelect(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    // Limit to 5 images
    if (this.pendingImages.length + files.length > 5) {
      alert("Máximo 5 imágenes permitidas.");
      return;
    }

    Array.from(files).forEach((file) => {
      if (!file.type.startsWith("image/")) return;

      const reader = new FileReader();
      reader.onload = (e) => {
        this.pendingImages.push(e.target.result);
        this.renderPreview();
      };
      reader.readAsDataURL(file);
    });

    // Reset input so same file can be selected again if needed
    event.target.value = "";
  }

  renderPreview() {
    const container = document.getElementById(DOM_SELECTORS.CHAT.PREVIEW);
    if (!container) return;

    container.innerHTML = "";
    container.style.display = this.pendingImages.length > 0 ? "flex" : "none";

    this.pendingImages.forEach((imgB64, index) => {
      const wrapper = document.createElement("div");
      wrapper.style.position = "relative";
      wrapper.style.display = "inline-block";

      const img = document.createElement("img");
      img.src = imgB64;
      img.style.height = "60px"; // Thumbnail size
      img.style.borderRadius = "4px";
      img.style.border = "1px solid #ddd";

      const removeBtn = document.createElement("button");
      removeBtn.textContent = "×";
      removeBtn.style.position = "absolute";
      removeBtn.style.top = "-5px";
      removeBtn.style.right = "-5px";
      removeBtn.style.background = "red";
      removeBtn.style.color = "white";
      removeBtn.style.border = "none";
      removeBtn.style.borderRadius = "50%";
      removeBtn.style.width = "18px";
      removeBtn.style.height = "18px";
      removeBtn.style.fontSize = "12px";
      removeBtn.style.cursor = "pointer";
      removeBtn.style.lineHeight = "1";

      removeBtn.onclick = () => {
        this.pendingImages.splice(index, 1);
        this.renderPreview();
      };

      wrapper.appendChild(img);
      wrapper.appendChild(removeBtn);
      container.appendChild(wrapper);
    });
  }
}
