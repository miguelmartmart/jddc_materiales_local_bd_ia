/**
 * metadata_builder.js — Módulo Frontend: Constructor de Metadatos BD
 *
 * RESPONSABILIDAD: UI para analizar tablas Firebird con la IA local LAN
 * y construir db_metadata_optimized.json.
 *
 * SEGURIDAD: Los datos de la BD SOLO van a la IA local LAN.
 * El backend bloquea cualquier envío a internet.
 *
 * DEPENDENCIAS: api.js (BASE_URL), constants.js
 * ENDPOINTS: /api/metadata-builder/*
 */

// ─── Constantes del módulo ────────────────────────────────────────────────────

const MB = {
  API_BASE: "/api/metadata-builder",
  POLL_MS: 500, // ms entre actualizaciones de progreso en batch
  TOAST_MS: 3500, // ms que se muestra un toast
  DEBOUNCE_MS: 300, // ms de debounce en búsqueda de tablas
};

// ─── Estado del módulo ────────────────────────────────────────────────────────

const mbState = {
  tables: [], // Lista completa de tablas de la BD
  filtered: [], // Lista filtrada por búsqueda
  currentTable: null, // Tabla seleccionada actualmente
  pendingMetadata: null, // Metadatos generados por IA pendientes de aprobación
  aiAvailable: false,
  batchRunning: false,
};

// ─── Inicialización ───────────────────────────────────────────────────────────

/**
 * Inicializa el módulo. Llamar cuando se activa la pestaña "Constructor BD".
 * EMISOR: app.js  RECEPTOR: metadata_builder.js
 */
async function mbInit() {
  mbLog("mbInit", "app.js", "metadata_builder", "Inicializando módulo");
  mbRenderSkeleton();
  await mbLoadStatus();
  await mbLoadTables();
}

// ─── Carga de estado ──────────────────────────────────────────────────────────

async function mbLoadStatus() {
  mbLog(
    "mbLoadStatus",
    "metadata_builder",
    "API /status",
    "Verificando IA local",
  );
  try {
    const data = await mbFetch(`${MB.API_BASE}/status`);
    mbState.aiAvailable = data.ai?.available ?? false;
    mbRenderAIStatus(data.ai, data.metadata);
  } catch (e) {
    mbState.aiAvailable = false;
    mbRenderAIStatus({ available: false, error: e.message }, null);
  }
}

async function mbLoadTables() {
  mbLog(
    "mbLoadTables",
    "metadata_builder",
    "API /tables",
    "Cargando lista de tablas",
  );
  mbShowTableListLoading(true);
  try {
    const data = await mbFetch(`${MB.API_BASE}/tables`);
    mbState.tables = data.tables || [];
    mbState.filtered = [...mbState.tables];
    mbRenderTableList(mbState.filtered);
    mbRenderTableStats(data.total, data.with_metadata);
  } catch (e) {
    mbShowError("Error cargando tablas: " + e.message);
  } finally {
    mbShowTableListLoading(false);
  }
}

// ─── Acciones principales ─────────────────────────────────────────────────────

/**
 * Selecciona una tabla y carga su estructura desde Firebird.
 * EMISOR: UI (click en tabla)  RECEPTOR: API /tables/{name}
 */
async function mbSelectTable(tableName) {
  mbLog(
    "mbSelectTable",
    "UI",
    `API /tables/${tableName}`,
    "Cargando estructura",
  );
  mbState.currentTable = tableName;
  mbState.pendingMetadata = null;

  mbHighlightTable(tableName);
  mbShowStructurePanel(tableName);
  mbShowStructureLoading(true);

  try {
    const data = await mbFetch(`${MB.API_BASE}/tables/${tableName}`);
    mbRenderStructure(data);
    mbRenderAnalyzeButton(tableName, mbState.aiAvailable);
  } catch (e) {
    mbShowStructureError(e.message);
  } finally {
    mbShowStructureLoading(false);
  }
}

/**
 * Analiza la tabla seleccionada con la IA local LAN.
 * EMISOR: UI (botón Analizar)  RECEPTOR: API /tables/{name}/analyze → Qwen3 LAN
 */
async function mbAnalyzeTable(tableName) {
  if (!mbState.aiAvailable) {
    mbShowToast(
      "⚠️ IA local no disponible. Los datos no se enviarán a internet.",
      "warning",
    );
    return;
  }

  mbLog(
    "mbAnalyzeTable",
    "UI",
    `API /tables/${tableName}/analyze`,
    "Iniciando análisis con IA local",
  );
  mbShowAnalyzeLoading(true, tableName);

  try {
    const data = await mbFetch(`${MB.API_BASE}/tables/${tableName}/analyze`, {
      method: "POST",
    });
    mbState.pendingMetadata = data.metadata;
    mbRenderMetadataPreview(data);
    mbShowToast(
      `✅ Análisis completado con ${data.ai_model || "IA local"}`,
      "success",
    );
  } catch (e) {
    const msg =
      e.status === 503
        ? "⚠️ IA local no disponible. Enciende el servidor Qwen3."
        : "Error en el análisis: " + e.message;
    mbShowToast(msg, "error");
    mbShowAnalyzeError(msg);
  } finally {
    mbShowAnalyzeLoading(false, tableName);
  }
}

/**
 * Guarda los metadatos aprobados (generados por IA o editados manualmente).
 * EMISOR: UI (botón Guardar)  RECEPTOR: API /tables/{name}/save
 */
async function mbSaveMetadata(tableName) {
  const metadata = mbGetEditedMetadata();
  if (!metadata) {
    mbShowToast("No hay metadatos para guardar.", "warning");
    return;
  }

  mbLog(
    "mbSaveMetadata",
    "UI",
    `API /tables/${tableName}/save`,
    "Guardando metadatos aprobados",
  );

  try {
    const data = await mbFetch(`${MB.API_BASE}/tables/${tableName}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ metadata }),
    });
    mbShowToast(`✅ ${data.message}`, "success");
    mbMarkTableWithMetadata(tableName);
    await mbLoadTables(); // Refrescar lista
  } catch (e) {
    mbShowToast("Error guardando: " + e.message, "error");
  }
}

/**
 * Elimina los metadatos de una tabla.
 * EMISOR: UI (botón Eliminar)  RECEPTOR: API /tables/{name}/metadata DELETE
 */
async function mbDeleteMetadata(tableName) {
  if (
    !confirm(
      `¿Eliminar metadatos de ${tableName}? El chat IA dejará de conocer esta tabla.`,
    )
  )
    return;

  mbLog(
    "mbDeleteMetadata",
    "UI",
    `API /tables/${tableName}/metadata`,
    "Eliminando metadatos",
  );

  try {
    await mbFetch(`${MB.API_BASE}/tables/${tableName}/metadata`, {
      method: "DELETE",
    });
    mbShowToast(`🗑️ Metadatos de ${tableName} eliminados.`, "info");
    await mbLoadTables();
    mbClearStructurePanel();
  } catch (e) {
    mbShowToast("Error eliminando: " + e.message, "error");
  }
}

// ─── Búsqueda de tablas ───────────────────────────────────────────────────────

let _mbSearchTimer = null;
function mbOnSearch(query) {
  clearTimeout(_mbSearchTimer);
  _mbSearchTimer = setTimeout(() => {
    const q = query.trim().toUpperCase();
    mbState.filtered = q
      ? mbState.tables.filter(
          (t) => t.name.includes(q) || t.category.includes(q),
        )
      : [...mbState.tables];
    mbRenderTableList(mbState.filtered);
  }, MB.DEBOUNCE_MS);
}

// ─── Render: Estado de la IA ──────────────────────────────────────────────────

function mbRenderAIStatus(ai, metadata) {
  const el = document.getElementById("mb-ai-status");
  if (!el) return;

  if (ai?.available) {
    el.innerHTML = `
      <div class="mb-status-badge mb-status-ok">
        <span class="mb-status-dot"></span>
        IA local disponible — ${ai.model || "Qwen3 LAN"}
        <small>${ai.url || ""}</small>
      </div>`;
  } else {
    el.innerHTML = `
      <div class="mb-status-badge mb-status-error">
        <span class="mb-status-dot"></span>
        IA local NO disponible — Los datos NO se enviarán a internet
        <small>${ai?.error || "Servidor apagado"}</small>
      </div>`;
  }

  if (metadata) {
    const pct =
      metadata.total_tables > 0
        ? Math.round(
            (metadata.total_tables / (mbState.tables.length || 1)) * 100,
          )
        : 0;
    const statsEl = document.getElementById("mb-metadata-stats");
    if (statsEl) {
      statsEl.innerHTML = `
        <span class="mb-stat">${metadata.total_tables} tablas con metadatos</span>`;
    }
  }
}

// ─── Render: Lista de tablas ──────────────────────────────────────────────────

function mbRenderTableList(tables) {
  const el = document.getElementById("mb-table-list");
  if (!el) return;

  if (!tables.length) {
    el.innerHTML = '<div class="mb-empty">No se encontraron tablas.</div>';
    return;
  }

  el.innerHTML = tables
    .map(
      (t) => `
    <div class="mb-table-item ${t.name === mbState.currentTable ? "mb-selected" : ""}"
         onclick="mbSelectTable('${t.name}')"
         title="${t.name}">
      <span class="mb-table-name">${t.name}</span>
      <span class="mb-table-badges">
        ${t.category ? `<span class="mb-badge mb-badge-cat">${t.category}</span>` : ""}
        ${
          t.has_metadata
            ? '<span class="mb-badge mb-badge-ok" title="Tiene metadatos">✓</span>'
            : '<span class="mb-badge mb-badge-pending" title="Sin metadatos">○</span>'
        }
      </span>
    </div>
  `,
    )
    .join("");
}

function mbRenderTableStats(total, withMeta) {
  const el = document.getElementById("mb-table-count");
  if (el) el.textContent = `${withMeta}/${total} tablas con metadatos`;
}

// ─── Render: Panel de estructura ──────────────────────────────────────────────

function mbShowStructurePanel(tableName) {
  const el = document.getElementById("mb-structure-panel");
  if (el) el.style.display = "block";
  const title = document.getElementById("mb-structure-title");
  if (title) title.textContent = tableName;
}

function mbClearStructurePanel() {
  const el = document.getElementById("mb-structure-panel");
  if (el) el.style.display = "none";
  mbState.currentTable = null;
  mbState.pendingMetadata = null;
}

function mbRenderStructure(data) {
  const el = document.getElementById("mb-structure-content");
  if (!el) return;

  const cols = data.columns || [];
  const pks = new Set(data.primary_keys || []);
  const sens = new Set(data.sensitive_cols_excluded || []);

  el.innerHTML = `
    <div class="mb-struct-meta">
      <span class="mb-stat">📊 ${(data.record_count || 0).toLocaleString()} registros</span>
      <span class="mb-stat">🔑 PKs: ${(data.primary_keys || []).join(", ") || "—"}</span>
      ${sens.size ? `<span class="mb-stat mb-sensitive">🔒 ${sens.size} cols sensibles excluidas</span>` : ""}
    </div>
    <div class="mb-columns-table">
      <table>
        <thead><tr><th>Columna</th><th>Tipo</th><th>Flags</th></tr></thead>
        <tbody>
          ${cols
            .map(
              (c) => `
            <tr class="${c.is_sensitive ? "mb-row-sensitive" : ""}">
              <td class="mb-col-name">${c.name}</td>
              <td class="mb-col-type">${c.type}</td>
              <td class="mb-col-flags">
                ${pks.has(c.name) ? '<span class="mb-flag mb-flag-pk">PK</span>' : ""}
                ${c.is_sensitive ? '<span class="mb-flag mb-flag-sens">🔒</span>' : ""}
                ${c.nullable ? "" : '<span class="mb-flag mb-flag-nn">NN</span>'}
              </td>
            </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
}

function mbRenderAnalyzeButton(tableName, aiAvailable) {
  const el = document.getElementById("mb-analyze-actions");
  if (!el) return;

  const hasExisting = mbState.tables.find(
    (t) => t.name === tableName,
  )?.has_metadata;

  el.innerHTML = `
    <button class="mb-btn mb-btn-primary" onclick="mbAnalyzeTable('${tableName}')"
            ${aiAvailable ? "" : 'disabled title="IA local no disponible"'}>
      🤖 Analizar con IA local
    </button>
    ${
      hasExisting
        ? `
      <button class="mb-btn mb-btn-danger" onclick="mbDeleteMetadata('${tableName}')">
        🗑️ Eliminar metadatos
      </button>`
        : ""
    }`;
}

// ─── Render: Preview de metadatos generados ───────────────────────────────────

function mbRenderMetadataPreview(data) {
  const el = document.getElementById("mb-metadata-preview");
  if (!el) return;

  el.style.display = "block";
  const meta = data.metadata || {};

  el.innerHTML = `
    <div class="mb-preview-header">
      <h4>📋 Metadatos generados por IA local (${data.ai_model || "Qwen3 LAN"})</h4>
      <span class="mb-preview-note">Revisa y edita antes de guardar</span>
    </div>
    <div class="mb-preview-fields">
      <label>Categoría</label>
      <input id="mb-edit-category" class="mb-input" value="${meta.category || ""}" />

      <label>Descripción</label>
      <textarea id="mb-edit-description" class="mb-textarea" rows="2">${meta.description || ""}</textarea>

      <label>Nota crítica (opcional)</label>
      <input id="mb-edit-note" class="mb-input" value="${meta._nota_critica || ""}" />

      <label>JSON completo (editable)</label>
      <textarea id="mb-edit-json" class="mb-textarea mb-json-editor" rows="12">${JSON.stringify(meta, null, 2)}</textarea>
    </div>
    <div class="mb-preview-actions">
      <button class="mb-btn mb-btn-success" onclick="mbSaveMetadata('${mbState.currentTable}')">
        💾 Guardar metadatos
      </button>
      <button class="mb-btn mb-btn-secondary" onclick="mbSyncJsonFromFields()">
        🔄 Sincronizar campos → JSON
      </button>
    </div>`;
}

/**
 * Obtiene los metadatos del editor (JSON editado por el usuario).
 */
function mbGetEditedMetadata() {
  const jsonEl = document.getElementById("mb-edit-json");
  if (!jsonEl) return mbState.pendingMetadata;
  try {
    return JSON.parse(jsonEl.value);
  } catch (e) {
    mbShowToast("JSON inválido. Corrígelo antes de guardar.", "error");
    return null;
  }
}

function mbSyncJsonFromFields() {
  const cat = document.getElementById("mb-edit-category")?.value || "";
  const desc = document.getElementById("mb-edit-description")?.value || "";
  const note = document.getElementById("mb-edit-note")?.value || null;
  const jsonEl = document.getElementById("mb-edit-json");
  if (!jsonEl) return;
  try {
    const current = JSON.parse(jsonEl.value);
    current.category = cat;
    current.description = desc;
    current._nota_critica = note || null;
    jsonEl.value = JSON.stringify(current, null, 2);
    mbShowToast("Campos sincronizados al JSON.", "info");
  } catch (e) {
    mbShowToast("JSON inválido. No se pudo sincronizar.", "error");
  }
}

// ─── Estados de carga ─────────────────────────────────────────────────────────

function mbShowTableListLoading(show) {
  const el = document.getElementById("mb-table-list");
  if (el && show)
    el.innerHTML = '<div class="mb-loading">Cargando tablas...</div>';
}

function mbShowStructureLoading(show) {
  const el = document.getElementById("mb-structure-content");
  if (el && show)
    el.innerHTML = '<div class="mb-loading">Consultando Firebird...</div>';
}

function mbShowAnalyzeLoading(show, tableName) {
  const btn = document.querySelector("#mb-analyze-actions .mb-btn-primary");
  if (!btn) return;
  btn.disabled = show;
  btn.textContent = show
    ? "⏳ Analizando con IA local..."
    : "🤖 Analizar con IA local";
}

function mbShowStructureError(msg) {
  const el = document.getElementById("mb-structure-content");
  if (el) el.innerHTML = `<div class="mb-error">❌ ${msg}</div>`;
}

function mbShowAnalyzeError(msg) {
  const el = document.getElementById("mb-metadata-preview");
  if (el) el.innerHTML = `<div class="mb-error">❌ ${msg}</div>`;
}

function mbHighlightTable(name) {
  document.querySelectorAll(".mb-table-item").forEach((el) => {
    el.classList.toggle(
      "mb-selected",
      el.querySelector(".mb-table-name")?.textContent === name,
    );
  });
}

function mbMarkTableWithMetadata(name) {
  const t = mbState.tables.find((t) => t.name === name);
  if (t) t.has_metadata = true;
  mbRenderTableList(mbState.filtered);
}

// ─── Toast notifications ──────────────────────────────────────────────────────

function mbShowToast(msg, type = "info") {
  const container =
    document.getElementById("mb-toast-container") || _mbCreateToastContainer();
  const toast = document.createElement("div");
  toast.className = `mb-toast mb-toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), MB.TOAST_MS);
}

function _mbCreateToastContainer() {
  const el = document.createElement("div");
  el.id = "mb-toast-container";
  el.className = "mb-toast-container";
  document.body.appendChild(el);
  return el;
}

function mbShowError(msg) {
  mbShowToast(msg, "error");
}

// ─── Skeleton inicial ─────────────────────────────────────────────────────────

function mbRenderSkeleton() {
  const root = document.getElementById("mb-root");
  if (!root) return;
  root.innerHTML = `
    <div class="mb-layout">
      <!-- Panel izquierdo: lista de tablas -->
      <div class="mb-sidebar">
        <div class="mb-sidebar-header">
          <h3>🗄️ Tablas de la BD</h3>
          <div id="mb-ai-status"></div>
          <input type="text" id="mb-search" class="mb-search"
                 placeholder="Buscar tabla..." oninput="mbOnSearch(this.value)" />
          <div id="mb-table-count" class="mb-table-count"></div>
          <div id="mb-metadata-stats" class="mb-metadata-stats"></div>
        </div>
        <div id="mb-table-list" class="mb-table-list">
          <div class="mb-loading">Cargando...</div>
        </div>
      </div>

      <!-- Panel derecho: estructura + metadatos -->
      <div class="mb-main">
        <div id="mb-structure-panel" class="mb-structure-panel" style="display:none">
          <div class="mb-structure-header">
            <h3 id="mb-structure-title"></h3>
            <div id="mb-analyze-actions" class="mb-analyze-actions"></div>
          </div>
          <div id="mb-structure-content" class="mb-structure-content"></div>
          <div id="mb-metadata-preview" class="mb-metadata-preview" style="display:none"></div>
        </div>
        <div id="mb-empty-state" class="mb-empty-state">
          <div class="mb-empty-icon">🗄️</div>
          <p>Selecciona una tabla para ver su estructura y generar metadatos con la IA local.</p>
          <p class="mb-empty-note">Los datos NUNCA salen de la red local.</p>
        </div>
      </div>
    </div>`;
}

// ─── Fetch helper ─────────────────────────────────────────────────────────────

async function mbFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    try {
      const body = await res.json();
      err.message = body.detail || err.message;
    } catch {}
    throw err;
  }
  return res.json();
}

// ─── Logger ───────────────────────────────────────────────────────────────────

function mbLog(step, emisor, receptor, msg) {
  console.log(`[METADATA_BUILDER][${step}] ${emisor} → ${receptor}: ${msg}`);
}

// ─── Exports (para app.js) ────────────────────────────────────────────────────

window.MetadataBuilder = {
  init: mbInit,
  selectTable: mbSelectTable,
  analyzeTable: mbAnalyzeTable,
  saveMetadata: mbSaveMetadata,
  deleteMetadata: mbDeleteMetadata,
  onSearch: mbOnSearch,
};
