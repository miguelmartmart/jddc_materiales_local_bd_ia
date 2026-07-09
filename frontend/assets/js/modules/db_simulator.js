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
    // DEVIA — Resiliencia en profundidad:
    // Cada fase de carga es independiente. Si una falla, las demás continúan.
    // El usuario ve lo que funciona, no una pantalla de error total.

    // Fase 1: config + status (críticos — sin ellos no podemos renderizar)
    try {
      const [cfg, status] = await Promise.all([
        this._apiFetch(`${SIM_API}/config`).catch(() => ({})),
        this._apiFetch(`${SIM_API}/status`).catch(() => ({ status: "not_initialized" })),
      ]);
      this._config = cfg;
      this._status = status;
    } catch (e) {
      this._config = {};
      this._status = { status: "not_initialized" };
      console.warn("[SimulatorModule] Config/status no disponibles:", e.message);
    }

    // Fase 2: biblioteca de consultas (no crítica — si falla, la UI sigue)
    try {
      await this._loadDemoQueryLibrary();
    } catch (e) {
      this._libQueries = [];
      this._libCatalog = null;
      console.warn("[SimulatorModule] Biblioteca de consultas no disponible:", e.message);
    }

    // Fase 3: render principal (con protección por sección)
    try {
      this._render();
    } catch (e) {
      console.error("[SimulatorModule] Error en _render():", e);
      // Render de emergencia: muestra lo que se pueda
      this._renderFallback(e.message);
    }

    // Fase 4: demo (no crítica — se carga aparte)
    if (this._status?.status === "ready") {
      this._loadDemo().catch(e => {
        console.warn("[SimulatorModule] Demo no disponible:", e.message);
      });
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

  /**
   * Render de emergencia: muestra la UI básica aunque _render() haya fallado.
   * DEVIA — Resiliencia: nunca mostrar pantalla en blanco o error total.
   * El usuario puede seguir usando los botones de acción aunque la biblioteca falle.
   */
  _renderFallback(errorMsg) {
    if (!this._root) return;
    const cfg    = this._config  || {};
    const status = this._status  || {};
    const enabled   = !!cfg.simulator_enabled;
    const simStatus = status.status || "not_initialized";

    this._root.innerHTML = `
      <div style="padding:16px; color:#92400e; background:#fffbeb; border:1px solid #fcd34d; border-radius:10px; margin-bottom:16px;">
        <strong>⚠️ Aviso:</strong> La biblioteca de consultas no pudo cargarse correctamente.
        <br><small style="color:#78350f;">Detalle técnico: ${errorMsg || "Error desconocido"}</small>
        <br><small>El resto de funcionalidades están disponibles. Pulsa "Actualizar" para reintentar.</small>
      </div>
      <div class="sim-actions">
        <button id="btn-sim-synthetic" class="btn secondary">🎲 Generar Datos Sintéticos</button>
        <div class="sim-sep"></div>
        <button id="btn-sim-snapshot" class="btn secondary" style="background:#1e40af;color:#fff;border-color:#1e40af;">📸 Capturar Snapshot Real</button>
        <div class="sim-sep"></div>
        <button id="btn-sim-refresh" class="btn secondary" style="margin-left:auto;" title="Recargar estado">🔄 Actualizar</button>
      </div>
      <div style="margin-top:12px; padding:12px; background:#f8fafc; border-radius:8px; font-size:0.85em; color:#64748b;">
        Estado: <strong>${simStatus}</strong> | Simulador: <strong>${enabled ? "🟢 Activo" : "⚪ Inactivo"}</strong>
      </div>
      <div id="sim-demo-section" style="margin-top:16px;"></div>`;

    // Registrar eventos básicos
    document.getElementById("btn-sim-synthetic")?.addEventListener("click", () => this._buildSynthetic());
    document.getElementById("btn-sim-snapshot")?.addEventListener("click", () => this._buildSnapshot());
    document.getElementById("btn-sim-refresh")?.addEventListener("click", () => this.onEnter());
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
        <span class="sim-badge ${enabled ? "active" : "inactive"}" title="${enabled ? "Simulador activo: el chat IA usa datos simulados" : "BD Real activa: el chat IA usa Firebird"}">
          ${enabled ? "🟢 SIMULADOR ACTIVO" : "⚪ BD REAL (Firebird)"}
        </span>
        ${simMode !== "empty" ? `<span class="sim-mode-tag" title="Modo de datos actual">${_modeLabel(simMode)}</span>` : ""}
        ${snapDate ? `<span class="sim-snapshot-date" title="Fecha del último snapshot capturado">📅 ${snapDate}</span>` : ""}
        <span style="color:#94a3b8; font-size:0.82em;">Estado: <strong>${_statusLabel(simStatus)}</strong></span>
        <span class="sim-help-tip" data-tip="El simulador permite al chat IA trabajar con datos de prueba sin tocar la BD real Firebird. Actívalo para demos, pruebas o cuando Firebird no esté disponible.">?</span>

        <div class="sim-header-actions">
          <label class="sim-toggle-wrap" title="${enabled ? "Desactivar simulador → volver a BD real" : "Activar simulador → usar datos de prueba"}">
            <span>${enabled ? "Desactivar" : "Activar simulador"}</span>
            <label class="sim-toggle">
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
               data-qid="${q.id}" title="${q.desc || ""}">
            <span class="sim-lib-icon">${q.icono || "📋"}</span>
            <div class="sim-lib-item-body">
              <div class="sim-lib-item-title">${q.title || q.nombre || q.id}</div>
              <div class="sim-lib-item-meta">
                <span class="sim-lib-badge urgencia-${_urgenciaClass(q.urgencia)}">${_urgenciaIcon(q.urgencia)} ${q.urgencia || ""}</span>
                ${_toArray(q.dept).map(d=>`<span class="sim-lib-badge dept">${d}</span>`).join("")}
                <span class="sim-lib-badge tipo">${q.tipo || ""}</span>
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
           data-qid="${q.id}" title="${q.desc || ""}">
        <span class="sim-lib-icon">${q.icono || "📋"}</span>
        <div class="sim-lib-item-body">
          <div class="sim-lib-item-title">${q.title || q.nombre || q.id}</div>
          <div class="sim-lib-item-meta">
            <span class="sim-lib-badge urgencia-${_urgenciaClass(q.urgencia)}">${_urgenciaIcon(q.urgencia)} ${q.urgencia || ""}</span>
            ${_toArray(q.dept).map(d=>`<span class="sim-lib-badge dept">${d}</span>`).join("")}
            <span class="sim-lib-badge tipo">${q.tipo || ""}</span>
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

    // Limpiar resultado anterior y paneles de verificación
    const result = document.getElementById("sim-query-result");
    if (result) result.innerHTML = "";
    const message = document.getElementById("sim-query-message");
    if (message) message.textContent = "";
    // Limpiar paneles de verificación de la consulta anterior
    const verPanel = document.getElementById("sim-verifications-panel");
    if (verPanel) verPanel.innerHTML = "";

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

      // ── Paneles de justificación/verificación ─────────────────────────────
      // Si hay una consulta seleccionada de la biblioteca, cargar sus paneles
      // de verificación debajo del resultado SQL.
      if (this._libSelected?.id) {
        await this._loadAndRenderVerifications(this._libSelected.id);
      }
    } catch (e) {
      if (message) message.textContent = `Error: ${e.message}`;
      result.innerHTML = "";
    }
  }

  /**
   * Carga y renderiza los paneles de justificación/verificación para una consulta.
   * Llama a GET /api/db-simulator/query-library/{id}/verify y ejecuta cada sub-SQL.
   * Los paneles se muestran en #sim-verifications-panel, debajo del resultado SQL.
   *
   * RESILIENCIA: si el endpoint falla o no hay paneles, no rompe nada — simplemente
   * no muestra el panel de verificaciones.
   */
  async _loadAndRenderVerifications(queryId) {
    // Asegurar que existe el contenedor de verificaciones
    let verPanel = document.getElementById("sim-verifications-panel");
    if (!verPanel) {
      const result = document.getElementById("sim-query-result");
      if (!result) return;
      verPanel = document.createElement("div");
      verPanel.id = "sim-verifications-panel";
      result.parentNode.insertBefore(verPanel, result.nextSibling);
    }

    verPanel.innerHTML = `
      <div class="sim-card" style="margin-top:16px;">
        <div class="sim-card-header">
          <span class="sim-card-icon">🔍</span>
          <span class="sim-card-title">Paneles de Verificación</span>
          <span style="margin-left:auto; font-size:0.78em; color:#94a3b8;">Cargando…</span>
        </div>
        <div class="sim-loading" style="padding:16px;"><div class="sim-spinner"></div><span>Ejecutando verificaciones…</span></div>
      </div>`;

    try {
      const data = await this._apiFetch(`${SIM_API}/query-library/${queryId}/verify`);
      const verifications = data.verifications || [];

      if (!verifications.length) {
        verPanel.innerHTML = "";
        return;
      }

      verPanel.innerHTML = this._renderVerificationsPanel(verifications, data.simulator_ready);
    } catch (e) {
      // Fallo silencioso — las verificaciones son opcionales
      verPanel.innerHTML = "";
      console.warn("[SimulatorModule] Verificaciones no disponibles:", e.message);
    }
  }

  /**
   * Renderiza los 10 paneles de verificación como secciones colapsables.
   * Cada panel tiene: icono, label, justificacion, y tabla de resultados (si hay datos).
   */
  _renderVerificationsPanel(verifications, simulatorReady) {
    const panelsHtml = verifications.map((v, idx) => {
      const rows = v.rows || [];
      const cols = v.columns || [];
      const hasData = rows.length > 0 && cols.length > 0;
      const icono = v.icono || "📋";
      const label = v.label || `Panel ${idx + 1}`;
      const justificacion = v.justificacion || "";
      const error = v.error || null;

      let bodyHtml = "";
      if (!simulatorReady) {
        bodyHtml = `<div class="sim-empty" style="padding:8px 0;">Simulador no disponible — actívalo para ver datos.</div>`;
      } else if (error) {
        bodyHtml = `<div class="sim-empty" style="color:#ef4444; padding:8px 0;">⚠️ ${error}</div>`;
      } else if (!hasData) {
        bodyHtml = `<div class="sim-empty" style="padding:8px 0;">Sin datos para este panel.</div>`;
      } else {
        const thead = cols.map(c => `<th>${c}</th>`).join("");
        const tbody = rows.map(row =>
          `<tr>${cols.map(c => `<td>${row[c] ?? "—"}</td>`).join("")}</tr>`
        ).join("");
        bodyHtml = `
          <div style="overflow:auto; max-height:220px;">
            <table class="sim-table" style="width:100%; border-collapse:collapse; font-size:0.85em;">
              <thead><tr>${thead}</tr></thead>
              <tbody>${tbody}</tbody>
            </table>
          </div>`;
      }

      // Panel colapsable — abierto el primero, cerrado el resto
      const isOpen = idx === 0 ? "open" : "";
      return `
        <details class="sim-ver-panel" ${isOpen} style="border:1px solid #e2e8f0; border-radius:8px; margin-bottom:8px; background:#fff;">
          <summary style="padding:10px 14px; cursor:pointer; display:flex; align-items:center; gap:8px; user-select:none; list-style:none; font-weight:600; color:#1e293b;">
            <span style="font-size:1.1em;">${icono}</span>
            <span style="flex:1;">${label}</span>
            <span style="font-size:0.75em; color:#64748b; font-weight:400;">${hasData ? rows.length + " filas" : ""}</span>
          </summary>
          <div style="padding:0 14px 12px 14px;">
            ${justificacion ? `<div style="font-size:0.82em; color:#475569; margin-bottom:8px; padding:6px 10px; background:#f8fafc; border-radius:6px; border-left:3px solid #93c5fd;">${justificacion}</div>` : ""}
            ${bodyHtml}
          </div>
        </details>`;
    }).join("");

    return `
      <div class="sim-card" style="margin-top:16px;">
        <div class="sim-card-header" style="cursor:pointer;" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
          <span class="sim-card-icon">🔍</span>
          <span class="sim-card-title">Paneles de Verificación</span>
          <span style="margin-left:auto; font-size:0.78em; color:#94a3b8;">${verifications.length} paneles · click para colapsar</span>
        </div>
        <div class="sim-card-body" style="padding:12px;">
          ${panelsHtml}
        </div>
      </div>`;
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

/**
 * Normaliza dept/rol: acepta string, array o null/undefined.
 * Siempre devuelve un array, nunca lanza excepción.
 * Resiliente ante cualquier formato que devuelva el backend.
 */
function _toArray(val) {
  if (val == null) return [];
  if (Array.isArray(val)) return val;
  if (typeof val === "string" && val.length > 0) return [val];
  return [];
}

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
