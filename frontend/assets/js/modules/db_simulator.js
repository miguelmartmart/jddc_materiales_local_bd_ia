/**
 * db_simulator.js — Módulo "BD Simulada" del dashboard DEVIA.
 *
 * Responsabilidades:
 *  • Mostrar el estado actual del simulador (modo, fecha, totales)
 *  • Toggle para activar/desactivar el simulador (config.json servidor)
 *  • Botones para generar datos sintéticos o capturar snapshot real
 *  • Panel de demostración: 10 consultas de negocio predefinidas
 *  • Biblioteca de consultas clasificadas por dept/rol/tipo/urgencia
 *
 * API endpoints usados:
 *  GET  /api/db-simulator/config                    → leer estado enabled
 *  POST /api/db-simulator/config                    → activar/desactivar
 *  GET  /api/db-simulator/status                    → estado + row_counts
 *  POST /api/db-simulator/build-synthetic           → generar datos sintéticos
 *  POST /api/db-simulator/build-snapshot            → capturar desde Firebird
 *  GET  /api/db-simulator/demo                      → consultas de negocio
 *  GET  /api/db-simulator/query-library/catalog     → catálogo clasificado
 *  GET  /api/db-simulator/query-library/search      → búsqueda con filtros
 *  GET  /api/db-simulator/query-library/{id}        → detalle + SQL
 *  POST /api/db-simulator/query-library/{id}/execute → ejecutar consulta
 *
 * DEVIA: frontend/assets/js/modules/DEVIA.MD
 */

const SIM_API = "/api/db-simulator";

// ─── Formatters ──────────────────────────────────────────────────────────────

const _fmt = {
  money: (v) =>
    v == null ? "—" :
    new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 }).format(v),
  int:   (v) => v == null ? "—" : Number(v).toLocaleString("es-ES"),
  dec:   (v) => v == null ? "—" : Number(v).toLocaleString("es-ES", { maximumFractionDigits: 2 }),
  pct:   (v) => v == null ? "—" : `${v}%`,
  text:  (v) => v == null ? "—" : String(v),
};

// ─── SimulatorModule ──────────────────────────────────────────────────────────

export class SimulatorModule {
  constructor() {
    this._root          = null;  // contenedor #sim-root
    this._config        = null;  // último config cargado
    this._status        = null;  // último status cargado
    this._demo          = null;  // última respuesta /demo
    this._demoQueries   = null;  // consultas SQL predefinidas (demo-sql legacy)
    this._queryResult   = null;  // resultado de ejecución SQL libre
    this._queryError    = null;
    this._loading       = false;
    // Biblioteca de consultas clasificadas
    this._libCatalog    = null;  // catálogo completo {total, por_departamento, ...}
    this._libQueries    = [];    // lista de consultas del resultado de búsqueda
    this._libFilter     = { dept: "", tipo: "", urgencia: "", text: "" };
    this._libSelected   = null;  // consulta seleccionada actualmente
  }

  // ── Punto de entrada ──────────────────────────────────────────────────────

  init() {
    // El módulo no hace nada hasta que se navega a la vista (lazy init)
    // Llamado desde app.js al navegar a "db-simulator"
  }

  /** Llamado por app.js cada vez que se entra a la vista */
  async onEnter() {
    this._root = document.getElementById("sim-root");
    if (!this._root) return;
    this._renderLoading();
    await this._loadAll();
  }

  // ── Carga de datos ─────────────────────────────────────────────────────────

  async _loadAll() {
    try {
      const [cfg, status] = await Promise.all([
        this._apiFetch(`${SIM_API}/config`),
        this._apiFetch(`${SIM_API}/status`),
      ]);
      this._config = cfg;
      this._status = status;
      await this._loadDemoQueryLibrary();
      this._render();

      // Cargar datos de demostración si el simulador está listo
      if (status?.status === "ready") {
        await this._loadDemo();
      }
    } catch (e) {
      this._renderError(e.message);
    }
  }

  async _loadDemo() {
    try {
      const data = await this._apiFetch(`${SIM_API}/demo`);
      this._demo = data;
      this._renderDemoSection();
    } catch (e) {
      const demoSection = document.getElementById("sim-demo-section");
      if (demoSection) {
        demoSection.innerHTML = `<div class="sim-empty">⚠️ No se pudo cargar la demo: ${e.message}</div>`;
      }
    }
  }

  // ── Render principal ───────────────────────────────────────────────────────

  _renderLoading() {
    this._root.innerHTML = `
      <div class="sim-loading">
        <div class="sim-spinner"></div>
        <span>Cargando BD Simulada…</span>
      </div>`;
  }

  _renderError(msg) {
    this._root.innerHTML = `
      <div style="padding:30px; color:#dc2626; background:#fef2f2; border-radius:10px;">
        <strong>⚠️ Error:</strong> ${msg}
        <br><small>Asegúrate de que el backend está corriendo.</small>
      </div>`;
  }

  _render() {
    const cfg    = this._config  || {};
    const status = this._status  || {};
    const enabled     = !!cfg.simulator_enabled;
    const simStatus   = status.status || "not_initialized";
    const simMode     = status.mode   || "empty";
    const snapDate    = status.snapshot_date || "";
    const rowCounts   = status.row_counts || {};
    const totalRows   = Object.values(rowCounts).reduce((a, b) => a + b, 0);
    const isReady     = simStatus === "ready";

    this._root.innerHTML = `
      <!-- Header de estado -->
      <div class="sim-header">
        <span class="sim-badge ${enabled ? "active" : "inactive"}">
          ${enabled ? "🟢 SIMULADOR ACTIVO" : "⚪ BD REAL (Firebird)"}
        </span>
        ${simMode !== "empty" ? `<span class="sim-mode-tag">${_modeLabel(simMode)}</span>` : ""}
        ${snapDate ? `<span class="sim-snapshot-date">📅 Snapshot: ${snapDate}</span>` : ""}
        <span style="color:#94a3b8; font-size:0.82em;">Estado BD: <strong>${_statusLabel(simStatus)}</strong></span>

        <div class="sim-header-actions">
          <label class="sim-toggle-wrap">
            <span>${enabled ? "Desactivar" : "Activar"}</span>
            <label class="sim-toggle" title="Activar/desactivar el simulador">
              <input type="checkbox" id="sim-toggle-chk" ${enabled ? "checked" : ""}>
              <span class="sim-toggle-slider"></span>
            </label>
          </label>
        </div>
      </div>

      <!-- Disclaimer visible cuando está activo -->
      ${enabled ? `
      <div class="sim-disclaimer">
        <span class="sim-disclaimer-icon">⚠️</span>
        <div>
          <strong>Modo Simulación activo.</strong> El chat IA responderá con datos
          <strong>simulados</strong> (no de la BD real Firebird).
          ${simMode === "snapshot" && snapDate
            ? `Datos capturados el <strong>${snapDate}</strong>.`
            : simMode === "synthetic"
            ? "Los datos son <strong>generados automáticamente</strong>, no reales."
            : ""}
          Desactiva el toggle para volver a la BD real.
        </div>
      </div>` : ""}

      <!-- Acciones -->
      <div class="sim-actions">
        <button id="btn-sim-synthetic" class="btn secondary">
          🎲 Generar Datos Sintéticos
        </button>
        <div class="sim-sep"></div>
        <button id="btn-sim-snapshot" class="btn secondary" style="background:#1e40af;color:#fff;border-color:#1e40af;">
          📸 Capturar Snapshot Real
        </button>
        <div class="sim-sep"></div>
        <button id="btn-sim-refresh" class="btn secondary" style="margin-left:auto;" title="Recargar estado">
          🔄 Actualizar
        </button>
      </div>

      <!-- Stats row (totales por tabla) -->
      ${isReady ? this._renderStatsRow(rowCounts, totalRows) : ""}

      <!-- Editor de consultas SQL predefinidas -->
      ${this._renderQueryRunner()}

      <!-- Sección de demostración -->
      <div id="sim-demo-section">
        ${isReady
          ? `<div class="sim-loading"><div class="sim-spinner"></div><span>Cargando consultas de demostración…</span></div>`
          : `<div class="sim-empty" style="margin-top:20px;">
               <p style="font-size:1.4em;">🗄️</p>
               <p>El simulador no tiene datos todavía.</p>
               <p>Pulsa <strong>"Generar Datos Sintéticos"</strong> para empezar,<br>
               o <strong>"Capturar Snapshot Real"</strong> si tienes acceso a Firebird.</p>
             </div>`
        }
      </div>
    `;

    // Registrar eventos
    document.getElementById("sim-toggle-chk")?.addEventListener("change", (e) => {
      this._toggleEnabled(e.target.checked);
    });
    document.getElementById("btn-sim-synthetic")?.addEventListener("click", () => {
      this._buildSynthetic();
    });
    document.getElementById("btn-sim-snapshot")?.addEventListener("click", () => {
      this._buildSnapshot();
    });
    document.getElementById("btn-sim-refresh")?.addEventListener("click", () => {
      this.onEnter();
    });

    this._attachQueryRunnerEvents();
  }

  _renderStatsRow(rowCounts, totalRows) {
    const importantTables = ["DOCCAB","DOCLIN","ARTICULO","CLIENTE","PROVEED","FAMILIA","CAJA","ESTALMACEN"];
    const cells = importantTables.map(t => {
      const n = rowCounts[t] ?? 0;
      return `<div class="sim-stat-card">
        <span class="stat-label">${t}</span>
        <span class="stat-value">${n.toLocaleString("es-ES")}</span>
      </div>`;
    });
    return `
      <div class="sim-stats-row" style="margin-bottom:16px;">
        ${cells.join("")}
        <div class="sim-stat-card">
          <span class="stat-label">TOTAL FILAS</span>
          <span class="stat-value">${totalRows.toLocaleString("es-ES")}</span>
        </div>
      </div>`;
  }

  // ── Sección demo ──────────────────────────────────────────────────────────

  _renderDemoSection() {
    const section = document.getElementById("sim-demo-section");
    if (!section || !this._demo) return;

    const { queries, simulator_mode, snapshot_date } = this._demo;
    if (!queries) {
      section.innerHTML = `<div class="sim-empty">No hay datos de demostración disponibles.</div>`;
      return;
    }

    // Renderizar bloque intro
    const modeTag = simulator_mode === "snapshot"
      ? `📸 Snapshot${snapshot_date ? ` del ${snapshot_date}` : ""}`
      : "🎲 Datos Sintéticos";

    let html = `
      <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
        <h3 style="margin:0; color:#1e293b; font-size:1.05em;">
          📊 Consultas de Demostración <span style="font-weight:400;color:#64748b;">(${modeTag})</span>
        </h3>
        <button id="btn-sim-reload-demo" class="btn secondary" style="margin-left:auto; padding:5px 12px; font-size:0.82em;">
          🔄 Recargar Demo
        </button>
      </div>
      <div class="sim-demo-grid">`;

    // Stats card (resumen_general) primero como fila completa
    const resumen = queries.resumen_general;
    if (resumen) {
      html += this._renderStatsCard(resumen);
    }

    // Tarjetas de tabla para el resto
    const ORDER = [
      "top_productos", "top_clientes", "ventas_por_mes",
      "documentos_por_tipo", "top_proveedores", "stock_disponible",
      "ultimas_facturas", "presupuestos_pendientes", "sats_recientes",
    ];
    for (const key of ORDER) {
      const q = queries[key];
      if (q) html += this._renderTableCard(q);
    }

    html += `</div>`;  // /sim-demo-grid
    section.innerHTML = html;

    document.getElementById("btn-sim-reload-demo")?.addEventListener("click", () => {
      section.innerHTML = `<div class="sim-loading"><div class="sim-spinner"></div><span>Actualizando demo…</span></div>`;
      this._loadDemo();
    });
  }

  // ── Biblioteca de consultas clasificadas ──────────────────────────────────

  async _loadDemoQueryLibrary() {
    // Carga en paralelo: demo-sql (legacy) + catálogo de la biblioteca
    try {
      const [demoData, catalogData] = await Promise.all([
        this._apiFetch(`${SIM_API}/demo-sql`).catch(() => ({ queries: [] })),
        this._apiFetch(`${SIM_API}/query-library/catalog`).catch(() => null),
      ]);
      this._demoQueries = demoData.queries || [];
      this._libCatalog  = catalogData?.catalog || null;
    } catch (e) {
      this._demoQueries = [];
      this._queryError  = `No se pudo cargar el listado de consultas: ${e.message}`;
    }
    // Cargar todas las consultas de la biblioteca (sin filtro inicial)
    await this._libSearch();
  }

  async _libSearch() {
    const f = this._libFilter;
    const params = new URLSearchParams();
    if (f.dept)     params.set("dept",     f.dept);
    if (f.tipo)     params.set("tipo",     f.tipo);
    if (f.urgencia) params.set("urgencia", f.urgencia);
    if (f.text)     params.set("text",     f.text);
    params.set("limit", "200");
    try {
      const data = await this._apiFetch(`${SIM_API}/query-library/search?${params}`);
      this._libQueries = data.queries || [];
    } catch (e) {
      this._libQueries = [];
    }
  }

  _renderQueryRunner() {
    const cat = this._libCatalog;
    // El backend devuelve by_dept, by_tipo, by_urgencia (nombres en inglés)
    const byDept    = cat?.by_dept    || cat?.por_departamento || {};
    const byTipo    = cat?.by_tipo    || cat?.por_tipo         || {};
    const byUrgencia = cat?.by_urgencia || cat?.por_urgencia   || {};
    const depts    = Object.keys(byDept).sort();
    const tipos    = Object.keys(byTipo).sort();
    const urgencias = ["Crítico", "Alto", "Medio", "Bajo"];
    const total    = cat ? cat.total : 0;
    const f        = this._libFilter;

    // Construir opciones de filtro
    const deptOpts = `<option value="">Todos los departamentos</option>` +
      depts.map(d => `<option value="${d}" ${f.dept===d?"selected":""}>${d} (${byDept[d]})</option>`).join("");
    const tipoOpts = `<option value="">Todos los tipos</option>` +
      tipos.map(t => `<option value="${t}" ${f.tipo===t?"selected":""}>${t} (${byTipo[t]})</option>`).join("");
    const urgOpts  = `<option value="">Todas las urgencias</option>` +
      urgencias.map(u => {
        const n = byUrgencia[u] ?? "";
        return `<option value="${u}" ${f.urgencia===u?"selected":""}>${_urgenciaIcon(u)} ${u}${n?" ("+n+")":""}</option>`;
      }).join("");

    // Lista de consultas
    const listHtml = this._libQueries.length === 0
      ? `<div class="sim-lib-empty">No hay consultas que coincidan con los filtros.</div>`
      : this._libQueries.map(q => `
          <div class="sim-lib-item ${this._libSelected?.id === q.id ? "selected" : ""}"
               data-qid="${q.id}" title="${q.desc}">
            <span class="sim-lib-icon">${q.icono || "📋"}</span>
            <div class="sim-lib-item-body">
              <div class="sim-lib-item-title">${q.title}</div>
              <div class="sim-lib-item-meta">
                <span class="sim-lib-badge urgencia-${_urgenciaClass(q.urgencia)}">${_urgenciaIcon(q.urgencia)} ${q.urgencia}</span>
                ${(q.dept||[]).map(d=>`<span class="sim-lib-badge dept">${d}</span>`).join("")}
                <span class="sim-lib-badge tipo">${q.tipo}</span>
              </div>
            </div>
          </div>`).join("");

    // Panel de detalle de la consulta seleccionada
    const sel = this._libSelected;
    const detailHtml = sel ? `
      <div class="sim-lib-detail-header">
        <span style="font-size:1.4em;">${sel.icono || "📋"}</span>
        <div>
          <div style="font-weight:700; font-size:1em; color:#1e293b;">${sel.title}</div>
          <div style="font-size:0.82em; color:#64748b; margin-top:2px;">${sel.desc}</div>
        </div>
        <span class="sim-lib-badge urgencia-${_urgenciaClass(sel.urgencia)}" style="margin-left:auto; white-space:nowrap;">
          ${_urgenciaIcon(sel.urgencia)} ${sel.urgencia}
        </span>
      </div>
      ${sel.accion ? `
      <div class="sim-lib-accion">
        <span style="font-weight:600;">💡 Acción recomendada:</span> ${sel.accion}
      </div>` : ""}
      ${sel.kpi ? `<div style="font-size:0.82em; color:#7c3aed; margin-bottom:8px;">📊 KPI: <strong>${sel.kpi}</strong></div>` : ""}
    ` : `<div style="color:#94a3b8; font-size:0.9em; padding:8px 0;">← Selecciona una consulta de la lista para ver su descripción y cargar el SQL.</div>`;

    const errorMessage = this._queryError
      ? `<div style="color:#dc2626; font-size:0.9em; padding:6px 0;">${this._queryError}</div>` : "";

    return `
      <div class="sim-card sim-lib-card" style="margin-bottom:20px;">
        <div class="sim-card-header">
          <span class="sim-card-icon">📚</span>
          <span class="sim-card-title">Biblioteca de Consultas SQL</span>
          <span style="margin-left:auto; font-size:0.8em; color:#64748b;">${total} consultas clasificadas</span>
        </div>
        <div class="sim-lib-layout">

          <!-- Panel izquierdo: filtros + lista -->
          <div class="sim-lib-panel-left">
            <!-- Filtros -->
            <div class="sim-lib-filters">
              <input id="sim-lib-search" type="text" placeholder="🔍 Buscar consulta…"
                class="sim-lib-search-input" value="${f.text || ""}">
              <select id="sim-lib-dept" class="sim-lib-select">${deptOpts}</select>
              <select id="sim-lib-tipo" class="sim-lib-select">${tipoOpts}</select>
              <select id="sim-lib-urg"  class="sim-lib-select">${urgOpts}</select>
              <button id="btn-lib-reset" class="btn secondary" style="padding:7px 12px; font-size:0.82em;">✕ Limpiar filtros</button>
            </div>
            <!-- Lista de consultas -->
            <div class="sim-lib-list" id="sim-lib-list">
              ${listHtml}
            </div>
          </div>

          <!-- Panel derecho: detalle + editor + resultado -->
          <div class="sim-lib-panel-right">
            <!-- Detalle de la consulta seleccionada -->
            <div class="sim-lib-detail" id="sim-lib-detail">
              ${detailHtml}
            </div>

            <!-- Editor SQL -->
            <div style="display:flex; gap:8px; align-items:center; margin-bottom:6px; flex-wrap:wrap;">
              <span style="font-weight:600; font-size:0.9em; color:#334155;">SQL (editable):</span>
              <button id="btn-sim-execute-query" class="btn primary" style="padding:7px 16px; font-size:0.88em; margin-left:auto;">
                ▶ Ejecutar
              </button>
              <button id="btn-sim-clear-query" class="btn secondary" style="padding:7px 12px; font-size:0.82em;">
                Limpiar
              </button>
            </div>
            <textarea id="sim-sql-editor" rows="7"
              style="width:100%; font-family:monospace; font-size:0.88em; border:1px solid #cbd5e1; border-radius:8px; padding:12px; resize:vertical; background:#f8fafc;"
              placeholder="Escribe o selecciona una consulta de la biblioteca…">${sel?.sql || ""}</textarea>
            <div id="sim-query-message" style="min-height:18px; color:#dc2626; font-size:0.88em; margin-top:4px;"></div>
            ${errorMessage}
            <div id="sim-query-result" style="margin-top:8px;"></div>
          </div>
        </div>
      </div>`;
  }

  _attachQueryRunnerEvents() {
    // Filtros de la biblioteca
    const doSearch = () => {
      this._libFilter.text     = document.getElementById("sim-lib-search")?.value || "";
      this._libFilter.dept     = document.getElementById("sim-lib-dept")?.value   || "";
      this._libFilter.tipo     = document.getElementById("sim-lib-tipo")?.value   || "";
      this._libFilter.urgencia = document.getElementById("sim-lib-urg")?.value    || "";
      this._libSearch().then(() => this._refreshLibList());
    };

    document.getElementById("sim-lib-search")?.addEventListener("input",  doSearch);
    document.getElementById("sim-lib-dept")?.addEventListener("change",   doSearch);
    document.getElementById("sim-lib-tipo")?.addEventListener("change",   doSearch);
    document.getElementById("sim-lib-urg")?.addEventListener("change",    doSearch);
    document.getElementById("btn-lib-reset")?.addEventListener("click", () => {
      this._libFilter = { dept: "", tipo: "", urgencia: "", text: "" };
      this._libSelected = null;
      this._libSearch().then(() => {
        // Re-render completo del runner para resetear selects
        const runner = document.querySelector(".sim-lib-card");
        if (runner) runner.outerHTML = this._renderQueryRunner();
        this._attachQueryRunnerEvents();
      });
    });

    // Clic en item de la lista
    document.getElementById("sim-lib-list")?.addEventListener("click", (e) => {
      const item = e.target.closest(".sim-lib-item");
      if (!item) return;
      const qid = item.dataset.qid;
      this._libSelectQuery(qid);
    });

    // Ejecutar SQL
    document.getElementById("btn-sim-execute-query")?.addEventListener("click", () => {
      this._executeSql();
    });

    // Limpiar editor
    document.getElementById("btn-sim-clear-query")?.addEventListener("click", () => {
      const editor = document.getElementById("sim-sql-editor");
      if (editor) editor.value = "";
      const message = document.getElementById("sim-query-message");
      if (message) message.textContent = "";
      const result = document.getElementById("sim-query-result");
      if (result) result.innerHTML = "";
    });
  }

  _refreshLibList() {
    const listEl = document.getElementById("sim-lib-list");
    if (!listEl) return;
    if (this._libQueries.length === 0) {
      listEl.innerHTML = `<div class="sim-lib-empty">No hay consultas que coincidan con los filtros.</div>`;
      return;
    }
    listEl.innerHTML = this._libQueries.map(q => `
      <div class="sim-lib-item ${this._libSelected?.id === q.id ? "selected" : ""}"
           data-qid="${q.id}" title="${q.desc}">
        <span class="sim-lib-icon">${q.icono || "📋"}</span>
        <div class="sim-lib-item-body">
          <div class="sim-lib-item-title">${q.title}</div>
          <div class="sim-lib-item-meta">
            <span class="sim-lib-badge urgencia-${_urgenciaClass(q.urgencia)}">${_urgenciaIcon(q.urgencia)} ${q.urgencia}</span>
            ${(q.dept||[]).map(d=>`<span class="sim-lib-badge dept">${d}</span>`).join("")}
            <span class="sim-lib-badge tipo">${q.tipo}</span>
          </div>
        </div>
      </div>`).join("");
  }

  async _libSelectQuery(queryId) {
    try {
      const data = await this._apiFetch(`${SIM_API}/query-library/${queryId}`);
      this._libSelected = data.query;
    } catch (e) {
      this._showToast(`❌ Error cargando consulta: ${e.message}`, "error");
      return;
    }

    // Actualizar editor SQL
    const editor = document.getElementById("sim-sql-editor");
    if (editor) editor.value = this._libSelected.sql || "";

    // Actualizar detalle
    const detailEl = document.getElementById("sim-lib-detail");
    if (detailEl) {
      const sel = this._libSelected;
      detailEl.innerHTML = `
        <div class="sim-lib-detail-header">
          <span style="font-size:1.4em;">${sel.icono || "📋"}</span>
          <div>
            <div style="font-weight:700; font-size:1em; color:#1e293b;">${sel.title}</div>
            <div style="font-size:0.82em; color:#64748b; margin-top:2px;">${sel.desc}</div>
          </div>
          <span class="sim-lib-badge urgencia-${_urgenciaClass(sel.urgencia)}" style="margin-left:auto; white-space:nowrap;">
            ${_urgenciaIcon(sel.urgencia)} ${sel.urgencia}
          </span>
        </div>
        ${sel.accion ? `
        <div class="sim-lib-accion">
          <span style="font-weight:600;">💡 Acción recomendada:</span> ${sel.accion}
        </div>` : ""}
        ${sel.kpi ? `<div style="font-size:0.82em; color:#7c3aed; margin-bottom:8px;">📊 KPI: <strong>${sel.kpi}</strong></div>` : ""}
      `;
    }

    // Limpiar resultado anterior
    const result = document.getElementById("sim-query-result");
    if (result) result.innerHTML = "";
    const message = document.getElementById("sim-query-message");
    if (message) message.textContent = "";

    // Marcar item seleccionado en la lista
    document.querySelectorAll(".sim-lib-item").forEach(el => {
      el.classList.toggle("selected", el.dataset.qid === queryId);
    });
  }

  _loadSelectedQuery(queryId) {
    // Compatibilidad legacy — redirige a la biblioteca
    this._libSelectQuery(queryId);
  }

  async _executeSql() {
    const editor = document.getElementById("sim-sql-editor");
    const message = document.getElementById("sim-query-message");
    const result = document.getElementById("sim-query-result");
    if (!editor || !result) return;

    const sql = editor.value.trim();
    if (!sql) {
      if (message) message.textContent = "Escribe o selecciona una consulta SQL antes de ejecutar.";
      return;
    }

    if (message) message.textContent = "";
    result.innerHTML = `<div class="sim-loading"><div class="sim-spinner"></div><span>Ejecutando consulta…</span></div>`;

    try {
      const payload = await this._apiFetch(`${SIM_API}/execute`, {
        method: "POST",
        body: JSON.stringify({ sql }),
      });
      result.innerHTML = this._formatSqlResult(payload);
    } catch (e) {
      if (message) message.textContent = `Error: ${e.message}`;
      result.innerHTML = "";
    }
  }

  _formatSqlResult(payload) {
    if (!payload || !payload.success) {
      return `<div class="sim-empty">No se recibió resultado válido.</div>`;
    }

    if (payload.type === "select") {
      const rows = payload.rows || [];
      const columns = payload.columns || [];
      if (!rows.length) {
        return `<div class="sim-empty">Consulta ejecutada correctamente, pero no se devolvieron filas.</div>`;
      }
      const header = columns.map((col) => `<th>${col}</th>`).join("");
      const body = rows
        .map((row) => `<tr>${columns.map((col) => `<td>${row[col] ?? ""}</td>`).join("")}</tr>`)
        .join("");
      return `
        <div class="sim-card" style="margin-top:12px;">
          <div class="sim-card-header"><span class="sim-card-title">Resultado SQL</span></div>
          <div class="sim-card-body" style="overflow:auto; max-height:360px;">
            <table class="sim-table" style="width:100%; border-collapse:collapse;">
              <thead><tr>${header}</tr></thead>
              <tbody>${body}</tbody>
            </table>
          </div>
        </div>`;
    }

    return `
      <div class="sim-card" style="margin-top:12px; padding:16px;">
        <div style="font-weight:600; margin-bottom:8px;">Consulta ejecutada</div>
        <div>Filas afectadas: <strong>${payload.affected_rows ?? 0}</strong></div>
        <div style="margin-top:8px; font-size:0.9em; color:#475569;">SQL ejecutado: <code style="white-space: pre-wrap;">${payload.sql ?? ""}</code></div>
      </div>`;
  }

  _renderStatsCard(q) {
    const statsHtml = (q.datos || []).map(d => {
      const fmt = _fmt[d.formato] || _fmt.text;
      const moneyClass = d.formato === "money" ? " money" : "";
      return `
        <div class="sim-stat-card">
          <span class="stat-label">${d.label}</span>
          <span class="stat-value${moneyClass}">${fmt(d.valor)}</span>
        </div>`;
    }).join("");

    return `
      <div class="sim-card" style="grid-column: 1 / -1;">
        <div class="sim-card-header">
          <span class="sim-card-icon">${q.icono}</span>
          <span class="sim-card-title">${q.titulo}</span>
        </div>
        <div class="sim-card-body">
          <div class="sim-stats-row" style="padding:12px 16px; margin:0; gap:10px;">
            ${statsHtml}
          </div>
        </div>
      </div>`;
  }

  _renderTableCard(q) {
    const cols  = q.columnas || [];
    const datos = q.datos    || [];

    if (!datos.length) {
      return `
        <div class="sim-card">
          <div class="sim-card-header">
            <span class="sim-card-icon">${q.icono}</span>
            <span class="sim-card-title">${q.titulo}</span>
          </div>
          <div class="sim-empty">Sin datos disponibles</div>
        </div>`;
    }

    const thead = cols.map(c => `<th>${c.label}</th>`).join("");
    const tbody = datos.map((row, idx) => {
      const tds = cols.map(c => {
        const val = row[c.key];
        const fmt = _fmt[c.formato] || _fmt.text;
        const cls = [c.formato, idx === 0 ? "rank-1" : ""].filter(Boolean).join(" ");
        return `<td class="${cls}" title="${val ?? ""}">${fmt(val)}</td>`;
      }).join("");
      return `<tr>${tds}</tr>`;
    }).join("");

    return `
      <div class="sim-card">
        <div class="sim-card-header">
          <span class="sim-card-icon">${q.icono}</span>
          <span class="sim-card-title">${q.titulo}</span>
          <span style="margin-left:auto; font-size:0.78em; color:#94a3b8;">${datos.length} filas</span>
        </div>
        <div class="sim-card-body">
          <table class="sim-table">
            <thead><tr>${thead}</tr></thead>
            <tbody>${tbody}</tbody>
          </table>
        </div>
      </div>`;
  }

  // ── Acciones ───────────────────────────────────────────────────────────────

  async _toggleEnabled(enabled) {
    try {
      await this._apiFetch(`${SIM_API}/config`, {
        method: "POST",
        body: JSON.stringify({ simulator_enabled: enabled }),
      });
      this._showToast(
        enabled ? "✅ Simulador activado — el chat usará datos simulados" : "✅ Simulador desactivado — usando BD real Firebird",
        enabled ? "success" : ""
      );
      await this._loadAll();
    } catch (e) {
      this._showToast(`❌ Error: ${e.message}`, "error");
      // Revertir el toggle visualmente
      const chk = document.getElementById("sim-toggle-chk");
      if (chk) chk.checked = !enabled;
    }
  }

  async _buildSynthetic() {
    const btn = document.getElementById("btn-sim-synthetic");
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Generando…"; }

    try {
      await this._apiFetch(`${SIM_API}/build-synthetic`, { method: "POST" });
      this._showToast("✅ Datos sintéticos generados correctamente", "success");
      await this._loadAll();
    } catch (e) {
      this._showToast(`❌ Error: ${e.message}`, "error");
      if (btn) { btn.disabled = false; btn.textContent = "🎲 Generar Datos Sintéticos"; }
    }
  }

  async _buildSnapshot() {
    // Los parámetros de conexión Firebird están en el .env del servidor.
    // El backend usa esos valores automáticamente si no se envía nada.
    // Solo preguntar si el usuario quiere confirmar o personalizar.
    const confirmed = confirm(
      "¿Capturar snapshot de la BD Firebird real?\n\n" +
      "Esto reemplazará todos los datos del simulador con datos reales actualizados.\n" +
      "El proceso puede tardar 30-90 segundos."
    );
    if (!confirmed) return;

    const btn = document.getElementById("btn-sim-snapshot");
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Capturando… (30-90s)"; }

    try {
      // Enviar body vacío — el servidor usa los valores del .env
      const result = await this._apiFetch(`${SIM_API}/build-snapshot`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      const counts = result?.data?.counts || {};
      const total  = Object.entries(counts)
        .filter(([k]) => k !== "DOCCAB_PROYECTO")
        .reduce((s, [, v]) => s + v, 0);
      this._showToast(
        `✅ Snapshot completado — ${total.toLocaleString("es-ES")} registros reales capturados`,
        "success"
      );
      await this._loadAll();
    } catch (e) {
      this._showToast(`❌ Error al capturar snapshot: ${e.message}`, "error");
      if (btn) { btn.disabled = false; btn.textContent = "📸 Capturar Snapshot Real"; }
    }
  }

  // ── Utilidades ─────────────────────────────────────────────────────────────

  async _apiFetch(url, opts = {}) {
    const resp = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
  }

  _showToast(msg, type = "") {
    const existing = document.querySelector(".sim-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = `sim-toast ${type}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }
}

// ─── Helpers locales ──────────────────────────────────────────────────────────

function _statusLabel(s) {
  const map = {
    not_initialized: "⬜ No inicializado",
    ready:           "✅ Listo",
    building:        "⏳ Construyendo…",
    error:           "❌ Error",
  };
  return map[s] || s;
}

function _modeLabel(m) {
  const map = {
    snapshot:  "📸 Snapshot real",
    synthetic: "🎲 Sintético",
    empty:     "⬜ Vacío",
  };
  return map[m] || m;
}

function _urgenciaIcon(u) {
  const map = { "Crítico": "🔴", "Alto": "🟠", "Medio": "🟡", "Bajo": "🟢" };
  return map[u] || "⚪";
}

function _urgenciaClass(u) {
  const map = { "Crítico": "critico", "Alto": "alto", "Medio": "medio", "Bajo": "bajo" };
  return map[u] || "bajo";
}
