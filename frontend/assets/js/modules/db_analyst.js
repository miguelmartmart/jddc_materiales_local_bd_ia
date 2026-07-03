/**
 * db_analyst.js — Módulo Analista BD
 *
 * Mejoras v2:
 *  - Layout correcto: columnas con flex, textarea auto-expansible
 *  - Guía de inicio cuando SIUO no está indexado
 *  - Trigger de indexación SIUO con progreso SSE en tiempo real
 *  - Panel de procedencia con pipeline visual (pasos expandibles)
 *  - Historial colapsable
 *  - Preguntas de ejemplo en el chat vacío
 */

const API_BASE = "/api/db-analyst";
const API_SIUO = "/api/siuo";

export class AnalystModule {
  constructor() {
    this.currentSessionId = null;
    this._provPanelVisible = true;
    this._histPanelVisible = true;
    this._inited = false;
    this._siuoReady = false;
    this._indexingController = null;
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  init() {
    if (this._inited) return;
    this._inited = true;

    this._bind("analyst-btn-new",          "click", () => this.newSession());
    this._bind("analyst-btn-send",         "click", () => this.sendMessage());
    this._bind("analyst-btn-justify",      "click", () => this.justify());
    this._bind("analyst-btn-refresh-status","click", () => this.loadStatus());
    this._bind("analyst-btn-toggle-prov",  "click", () => this.toggleProvPanel());
    this._bind("analyst-btn-toggle-hist",  "click", () => this.toggleHistPanel());
    this._bind("analyst-btn-show-guide",   "click", () => this._showGuide(true));
    this._bind("analyst-btn-index",        "click", () => this.startIndexing());

    // Textarea: Enter envía, Shift+Enter nueva línea; auto-resize
    const ta = document.getElementById("analyst-input");
    if (ta) {
      ta.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
      ta.addEventListener("input", () => this._autoResizeTextarea(ta));
    }

    this._initResizeHandles();
    this.loadStatus();
    this.loadSessions();
  }

  _bind(id, evt, fn) {
    document.getElementById(id)?.addEventListener(evt, fn);
  }

  // ── Auto-resize textarea ───────────────────────────────────────────────────

  _autoResizeTextarea(ta) {
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 150) + "px";
  }

  // ── Estado del módulo ──────────────────────────────────────────────────────

  async loadStatus() {
    try {
      const res  = await fetch(`${API_BASE}/status`);
      const data = await res.json();
      this._siuoReady = data.siuo_ready;

      const srcEl  = document.getElementById("analyst-status-source");
      const siuoEl = document.getElementById("analyst-status-siuo");
      const simEl  = document.getElementById("analyst-status-sim");

      if (srcEl)  srcEl.textContent  = `Fuente: ${data.data_source === "simulator" ? "🎭 Simulador" : "🔥 Firebird"}`;
      if (siuoEl) {
        siuoEl.textContent  = data.siuo_ready
          ? `SIUO: ✅ ${data.siuo_tables_indexed} tablas`
          : "SIUO: ⚠️ Sin indexar";
        siuoEl.style.color  = data.siuo_ready ? "#16a34a" : "#d97706";
      }
      if (simEl) {
        simEl.textContent = data.simulator_enabled
          ? `Simulador: 🟢 ${data.simulator_status || "activo"}`
          : "Simulador: ⚫ inactivo";
        simEl.style.color = data.simulator_enabled ? "#16a34a" : "#64748b";
      }

      this._showGuide(!data.siuo_ready);
    } catch (e) {
      console.warn("[AnalystModule] No se pudo cargar el estado:", e);
    }
  }

  _showGuide(show) {
    const el = document.getElementById("analyst-guide");
    if (el) el.style.display = show ? "block" : "none";
  }

  // ── Indexación SIUO con progreso SSE (POST + ReadableStream) ─────────────

  async startIndexing() {
    const btn      = document.getElementById("analyst-btn-index");
    const progress = document.getElementById("analyst-index-progress");
    const bar      = document.getElementById("analyst-progress-bar");
    const text     = document.getElementById("analyst-progress-text");

    if (!btn) return;
    btn.disabled    = true;
    btn.textContent = "⏳ Indexando…";
    if (progress) progress.style.display = "block";
    if (bar) { bar.style.width = "0%"; bar.style.background = "#3b82f6"; }

    // Cancelar petición anterior si existiera
    if (this._indexingController) this._indexingController.abort();
    this._indexingController = new AbortController();

    try {
      const response = await fetch(`${API_SIUO}/analyze/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_size: 5, resume: true }),
        signal: this._indexingController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // conservar línea incompleta

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev   = JSON.parse(line.slice(6));
            const type = ev.type;

            if (type === "start") {
              if (text) text.textContent = `Iniciando… ${ev.total || 0} tablas totales`;
              if (bar) bar.style.width = "2%";
            } else if (type === "progress") {
              const pct = ev.total > 0 ? Math.round((ev.done / ev.total) * 100) : 0;
              if (bar) bar.style.width = pct + "%";
              if (text) text.textContent = `[${ev.done}/${ev.total}] ${ev.table || ""} — ${ev.status || ""}`;
            } else if (type === "phase") {
              if (text) text.textContent = `⚙️ ${ev.message || ev.phase}`;
            } else if (type === "complete") {
              if (bar) { bar.style.width = "100%"; bar.style.background = "#22c55e"; }
              if (text) text.textContent = `✅ Indexación completa — ${ev.done} tablas`;
              btn.textContent = "✅ Indexado";
              setTimeout(() => this.loadStatus(), 1000);
            } else if (type === "error") {
              if (text) text.textContent = `❌ Error: ${ev.message}`;
              btn.disabled    = false;
              btn.textContent = "🔄 Reintentar";
            } else if (type === "reload") {
              if (text) text.textContent = `♻️ ${ev.message}`;
            }
          } catch (_) { /* ignorar líneas no-JSON */ }
        }
      }
    } catch (e) {
      if (e.name === "AbortError") return;
      if (text) text.textContent = `❌ ${e.message}`;
      btn.disabled    = false;
      btn.textContent = "🔄 Reintentar";
    }
  }

  // ── Sesiones ───────────────────────────────────────────────────────────────

  async newSession() {
    try {
      const res = await fetch(`${API_BASE}/session/new`, { method: "POST" });
      const data = await res.json();
      this.currentSessionId = data.session_id;
      this._clearMessages();
      this._clearProvenance();
      await this.loadSessions();
    } catch (e) {
      console.error("[AnalystModule] Error creando sesión:", e);
    }
  }

  async loadSessions() {
    const list = document.getElementById("analyst-sessions-list");
    if (!list) return;
    try {
      const res      = await fetch(`${API_BASE}/sessions?limit=40`);
      const sessions = await res.json();
      if (!sessions.length) {
        list.innerHTML = '<div style="text-align:center;color:#94a3b8;margin-top:20px;font-size:0.82em;">Sin conversaciones</div>';
        return;
      }
      list.innerHTML = sessions.map(s => {
        const active = s.id === this.currentSessionId;
        return `<div class="analyst-sess" data-id="${s.id}"
          style="padding:8px 10px;margin-bottom:3px;border-radius:7px;cursor:pointer;
                 background:${active ? "#eff6ff" : "transparent"};
                 border:1px solid ${active ? "#bfdbfe" : "transparent"};
                 transition:background 0.15s;">
          <div style="font-size:0.83em;color:#1e293b;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${this._esc(s.title)}</div>
          <div style="font-size:0.73em;color:#94a3b8;margin-top:2px;">${this._fmt(s.updated_at)}</div>
        </div>`;
      }).join("");

      list.querySelectorAll(".analyst-sess").forEach(el => {
        el.addEventListener("click",    () => this.openSession(el.dataset.id));
        el.addEventListener("mouseover", () => { if (el.dataset.id !== this.currentSessionId) el.style.background = "#f1f5f9"; });
        el.addEventListener("mouseout",  () => { if (el.dataset.id !== this.currentSessionId) el.style.background = "transparent"; });
      });
    } catch (e) {
      list.innerHTML = '<div style="color:#dc2626;padding:10px;font-size:0.82em;">Error cargando historial</div>';
    }
  }

  async openSession(sessionId) {
    this.currentSessionId = sessionId;
    this._clearMessages();
    this._clearProvenance();
    this.loadSessions(); // resaltar activa

    try {
      const res  = await fetch(`${API_BASE}/session/${sessionId}`);
      const data = await res.json();
      let lastProv = null;
      for (const m of (data.messages || [])) {
        this._appendMessage(m.role, m.content);
        if (m.role === "assistant" && m.provenance) lastProv = m.provenance;
      }
      if (lastProv) this._renderProvenance(lastProv);
    } catch (e) {
      console.error("[AnalystModule] Error cargando sesión:", e);
    }
  }

  // ── Chat ───────────────────────────────────────────────────────────────────

  async sendMessage() {
    const ta  = document.getElementById("analyst-input");
    const msg = ta?.value.trim();
    if (!msg) return;

    ta.value = "";
    ta.style.height = "auto";
    ta.disabled = true;
    const sendBtn = document.getElementById("analyst-btn-send");
    if (sendBtn) sendBtn.disabled = true;

    this._appendMessage("user", msg);
    const thinking = this._appendThinking();

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, session_id: this.currentSessionId, model_id: "jddcia-qwen3-30b" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      this.currentSessionId = data.session_id;
      thinking.remove();
      this._appendMessage("assistant", data.response);
      this._renderProvenance(data.provenance);
      this.loadSessions();
    } catch (e) {
      thinking.remove();
      this._appendMessage("assistant", `❌ Error: ${e.message}`);
    } finally {
      ta.disabled = false;
      if (sendBtn) sendBtn.disabled = false;
      ta.focus();
    }
  }

  async justify() {
    if (!this.currentSessionId) { alert("Primero inicia una conversación."); return; }
    const followup = prompt("¿Qué parte quieres que justifique? (opcional — pulsa OK para justificación completa)") ?? "";
    const btn = document.getElementById("analyst-btn-justify");
    if (btn) { btn.disabled = true; btn.textContent = "⏳…"; }

    const thinking = this._appendThinking("Analizando la evidencia y construyendo justificación…");
    try {
      const res = await fetch(`${API_BASE}/chat/justify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: this.currentSessionId, followup }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data = await res.json();
      thinking.remove();
      this._appendMessage("assistant", data.justification, true);
    } catch (e) {
      thinking.remove();
      this._appendMessage("assistant", `❌ Error al justificar: ${e.message}`);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "🔍 Justificar"; }
    }
  }

  // ── Renderizado de mensajes ────────────────────────────────────────────────

  _appendMessage(role, content, isJustification = false) {
    const container = document.getElementById("analyst-messages");
    if (!container) return null;

    // Ocultar mensaje vacío inicial si existe
    const empty = container.querySelector(".analyst-empty-msg");
    if (empty) empty.remove();

    const div = document.createElement("div");
    div.style.cssText = [
      "margin-bottom:12px",
      "padding:12px 14px",
      "border-radius:10px",
      "line-height:1.55",
      "font-size:0.93em",
      "word-break:break-word",
      role === "user"
        ? "margin-left:auto;max-width:82%;background:#dbeafe;border-left:3px solid #3b82f6;color:#1e3a8a;"
        : isJustification
          ? "max-width:96%;background:#fef9c3;border-left:3px solid #eab308;color:#78350f;"
          : "max-width:96%;background:#f0fdf4;border-left:3px solid #22c55e;color:#14532d;"
    ].join(";");

    if (role === "user") {
      div.textContent = content;
    } else {
      // El backend devuelve HTML con <details> — permitir HTML
      div.innerHTML = typeof marked !== "undefined"
        ? marked.parse(content)
        : content.replace(/\n/g, "<br>");
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  _appendThinking(text = "Consultando la base de datos y procesando con Qwen3…") {
    const container = document.getElementById("analyst-messages");
    const div = document.createElement("div");
    div.style.cssText = "padding:10px 14px;color:#64748b;font-style:italic;font-size:0.87em;display:flex;align-items:center;gap:8px;";
    div.innerHTML = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#3b82f6;animation:pulse 1s infinite;"></span>${this._esc(text)}`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }

  _clearMessages() {
    const c = document.getElementById("analyst-messages");
    if (!c) return;
    c.innerHTML = `<div class="analyst-empty-msg" style="background:#e0f2fe;border-left:3px solid #0ea5e9;padding:12px 14px;border-radius:8px;max-width:88%;font-size:0.93em;color:#0c4a6e;line-height:1.55;">
      <strong>Analista BD</strong> — Haz cualquier pregunta sobre la base de datos.<br>
      <span style="color:#0369a1;font-size:0.88em;">Cada respuesta incluye la procedencia completa: SQL, tablas usadas y datos brutos.</span>
    </div>`;
  }

  // ── Panel de procedencia ───────────────────────────────────────────────────

  _renderProvenance(prov) {
    const el = document.getElementById("analyst-provenance-content");
    if (!el || !prov) return;

    const srcBadge = prov.data_source === "simulator"
      ? '<span style="background:#fde68a;color:#92400e;padding:2px 8px;border-radius:12px;">🎭 Simulador</span>'
      : '<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:12px;">🔥 Firebird</span>';

    // Pipeline steps
    const steps = [
      { icon: "1️⃣", label: "SIUO — Keywords", ok: prov.siuo_keywords?.length > 0,
        detail: prov.siuo_keywords?.length
          ? prov.siuo_keywords.map(k => `<span style="background:#e0f2fe;color:#0369a1;padding:1px 6px;border-radius:10px;">${k}</span>`).join(" ")
          : "<em style='color:#94a3b8'>sin keywords detectadas</em>" },
      { icon: "2️⃣", label: "SIUO — Tablas encontradas", ok: prov.tables_used?.length > 0,
        detail: prov.tables_used?.length
          ? prov.tables_used.map(t => `<code style="background:#f1f5f9;padding:1px 5px;border-radius:3px;">${t}</code>`).join(" ")
          : "<em style='color:#94a3b8'>sin tablas (respuesta conversacional)</em>",
        extra: prov.siuo_source ? `<div style="margin-top:4px;color:#94a3b8;font-size:0.78em;">Índice: <code>${prov.siuo_source}</code> · ${prov.context_tokens} tokens</div>` : "" },
      { icon: "3️⃣", label: "SQL generado por Qwen3", ok: !!prov.sql_generated,
        detail: prov.sql_generated
          ? `<pre style="background:#1e1e1e;color:#a5f3fc;padding:8px;border-radius:5px;overflow-x:auto;font-size:0.76em;white-space:pre-wrap;margin:4px 0;">${this._esc(prov.sql_generated)}</pre>`
          : "<em style='color:#94a3b8'>sin SQL</em>" },
      { icon: "4️⃣", label: "SQL ejecutado (normalizado)", ok: !!prov.sql_executed && prov.sql_executed !== prov.sql_generated,
        detail: prov.sql_executed && prov.sql_executed !== prov.sql_generated
          ? `<pre style="background:#1e1e1e;color:#86efac;padding:8px;border-radius:5px;overflow-x:auto;font-size:0.76em;white-space:pre-wrap;margin:4px 0;">${this._esc(prov.sql_executed)}</pre>`
          : prov.sql_executed
            ? "<em style='color:#94a3b8'>sin cambios tras normalización</em>"
            : "<em style='color:#94a3b8'>sin SQL</em>" },
      { icon: "5️⃣", label: `Datos brutos (${prov.raw_results?.length ?? 0} filas)`, ok: prov.raw_results?.length > 0,
        detail: prov.raw_results?.length
          ? `<details><summary style="cursor:pointer;color:#3b82f6;font-size:0.85em;">Ver datos (${Math.min(prov.raw_results.length,10)} de ${prov.raw_results.length})</summary>
             <pre style="background:#f8fafc;padding:8px;border-radius:4px;overflow:auto;font-size:0.74em;max-height:180px;white-space:pre-wrap;margin:4px 0;">${this._esc(JSON.stringify(prov.raw_results.slice(0,10), null, 2))}</pre>
             </details>`
          : "<em style='color:#94a3b8'>sin datos</em>" },
    ];

    const stepsHtml = steps.map(s => `
      <details style="margin-bottom:6px;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">
        <summary style="cursor:pointer;padding:7px 10px;background:${s.ok ? "#f0fdf4" : "#fafafa"};display:flex;align-items:center;gap:6px;font-weight:500;font-size:0.82em;list-style:none;user-select:none;">
          <span>${s.icon}</span>
          <span style="flex:1;">${s.label}</span>
          <span style="color:${s.ok ? "#22c55e" : "#e5e7eb"};">${s.ok ? "✓" : "—"}</span>
        </summary>
        <div style="padding:8px 10px;background:white;border-top:1px solid #f1f5f9;">
          ${s.detail}
          ${s.extra || ""}
        </div>
      </details>
    `).join("");

    const copySQL = prov.sql_executed
      ? `<button onclick="navigator.clipboard.writeText(${JSON.stringify(prov.sql_executed)})" style="background:none;border:none;cursor:pointer;font-size:0.8em;color:#6366f1;padding:0;" title="Copiar SQL">📋 Copiar SQL</button>`
      : "";

    el.innerHTML = `
      <!-- Header -->
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap;">
        ${srcBadge}
        <span style="color:#94a3b8;font-size:0.78em;">${prov.execution_time_ms}ms</span>
        <span style="flex:1;"></span>
        ${copySQL}
      </div>
      <!-- Modelo -->
      ${prov.model_used ? `<div style="margin-bottom:8px;font-size:0.78em;color:#64748b;">Modelo: <code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;">${prov.model_used}</code></div>` : ""}
      <!-- Pipeline -->
      <div style="font-weight:600;color:#374151;margin-bottom:6px;font-size:0.82em;">⛓️ Cadena de procesado</div>
      ${stepsHtml}
    `;
  }

  _clearProvenance() {
    const el = document.getElementById("analyst-provenance-content");
    if (el) el.innerHTML = `<div id="analyst-prov-empty" style="text-align:center;margin-top:30px;color:#94a3b8;">
      <div style="font-size:2em;margin-bottom:8px;">🔍</div>
      <p style="font-size:0.88em;">La cadena de evidencia de cada respuesta aparecerá aquí.</p>
      <p style="font-size:0.78em;margin-top:6px;color:#cbd5e1;">SQL · tablas SIUO · datos brutos · modelo</p>
    </div>`;
  }

  // ── Toggle paneles laterales ───────────────────────────────────────────────

  toggleProvPanel() {
    const panel = document.getElementById("analyst-provenance-panel");
    const btn   = document.getElementById("analyst-btn-toggle-prov");
    if (!panel || !btn) return;
    this._provPanelVisible = !this._provPanelVisible;
    if (this._provPanelVisible) {
      panel.style.width = "270px";
      panel.style.overflow = "hidden";
      document.getElementById("analyst-provenance-content").style.display = "";
      btn.textContent = "▶";
    } else {
      panel.style.width = "36px";
      document.getElementById("analyst-provenance-content").style.display = "none";
      btn.textContent = "◀";
    }
  }

  toggleHistPanel() {
    const panel = document.getElementById("analyst-sessions-sidebar");
    const btn   = document.getElementById("analyst-btn-toggle-hist");
    const list  = document.getElementById("analyst-sessions-list");
    if (!panel || !btn) return;
    this._histPanelVisible = !this._histPanelVisible;
    if (this._histPanelVisible) {
      panel.style.width = "210px";
      if (list) list.style.display = "";
      btn.textContent = "◀";
    } else {
      panel.style.width = "36px";
      if (list) list.style.display = "none";
      btn.textContent = "▶";
    }
  }

  // ── Resize handles para paneles laterales ────────────────────────────────

  _initResizeHandles() {
    // Handle izquierdo: redimensiona el sidebar de sesiones
    const leftHandle = document.getElementById("analyst-resize-sessions");
    // Handle derecho: redimensiona el panel de procedencia
    const rightHandle = document.getElementById("analyst-resize-prov");

    if (leftHandle) {
      const sidebar = document.getElementById("analyst-sessions-sidebar");
      this._makeResizable(leftHandle, sidebar, "left");
    }
    if (rightHandle) {
      const panel = document.getElementById("analyst-provenance-panel");
      this._makeResizable(rightHandle, panel, "right");
    }
  }

  _makeResizable(handle, targetPanel, side) {
    let dragging = false;
    let startX   = 0;
    let startW   = 0;

    handle.addEventListener("mousedown", (e) => {
      dragging = true;
      startX   = e.clientX;
      startW   = targetPanel.getBoundingClientRect().width;
      targetPanel.style.transition = "none"; // desactivar transición durante drag
      document.body.style.cursor   = "col-resize";
      document.body.style.userSelect = "none";
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const delta = e.clientX - startX;
      // left handle: arrastrar derecha → sidebar más ancho
      // right handle: arrastrar izquierda → panel más ancho
      const newW = side === "left"
        ? Math.max(120, Math.min(420, startW + delta))
        : Math.max(150, Math.min(500, startW - delta));
      targetPanel.style.width = newW + "px";
      // Si el panel estaba colapsado, marcarlo como visible
      if (side === "left" && newW > 80) {
        this._histPanelVisible = true;
        const list = document.getElementById("analyst-sessions-list");
        if (list) list.style.display = "";
        const btn = document.getElementById("analyst-btn-toggle-hist");
        if (btn) btn.textContent = "◀";
      }
      if (side === "right" && newW > 80) {
        this._provPanelVisible = true;
        const content = document.getElementById("analyst-provenance-content");
        if (content) content.style.display = "";
        const btn = document.getElementById("analyst-btn-toggle-prov");
        if (btn) btn.textContent = "▶";
      }
    });

    document.addEventListener("mouseup", () => {
      if (!dragging) return;
      dragging = false;
      targetPanel.style.transition = "width 0.1s";
      document.body.style.cursor   = "";
      document.body.style.userSelect = "";
    });
  }

  // ── Utils ──────────────────────────────────────────────────────────────────

  _esc(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  _fmt(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso.replace(" ", "T") + (iso.includes("Z") ? "" : "Z"));
      return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
    } catch { return iso.substring(0, 10); }
  }
}
