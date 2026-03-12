/**
 * siuo_render.js — Funciones de renderizado DOM del módulo SIUO.
 *
 * RESPONSABILIDAD:
 *   Toda la lógica de construcción y actualización del DOM del panel SIUO.
 *   Sin lógica de negocio ni llamadas a API — solo render.
 *
 * DEPENDENCIAS: siuo_constants.js
 * PATRÓN: Módulo de presentación puro.
 */

import {
  escapeHtml,
  formatDate,
  timeNow,
  markdownToHtml,
  SIUO_TEST_BANK,
} from "./siuo_constants.js";

// ─── Skeleton principal ───────────────────────────────────────────────────────

export function renderSkeleton() {
  const root = document.getElementById("siuo-root");
  if (!root) return;

  const bankHtml = SIUO_TEST_BANK.map(
    (group) => `
    <div class="siuo-test-bank-group">
      <div class="siuo-test-bank-label">${group.label}</div>
      <div class="siuo-test-bank-btns">
        ${group.tests
          .map(
            (t) =>
              `<button class="siuo-test-chip"
                 data-question="${escapeHtml(t.q)}"
                 onclick="window.SIUOModule.runQuickTest('${escapeHtml(t.q).replace(/'/g, "&#39;")}')">
                 ${escapeHtml(t.text)}
               </button>`,
          )
          .join("")}
      </div>
    </div>`,
  ).join("");

  root.innerHTML = `
    <div class="siuo-layout">
      <div class="siuo-header-cards" id="siuo-stats-cards">
        ${_statCard("🗄️", "siuo-stat-tables", "Tablas indexadas")}
        ${_statCard("🔗", "siuo-stat-edges", "Relaciones en grafo")}
        ${_statCard("🔑", "siuo-stat-concepts", "Keywords en índice")}
        ${_statCard("📊", "siuo-stat-enums", "Enumerados indexados")}
      </div>

      <div class="siuo-progress-section" id="siuo-progress-section" style="display:none;">
        <div class="siuo-progress-header">
          <span id="siuo-progress-label">Progreso</span>
          <span id="siuo-progress-pct">0%</span>
        </div>
        <div class="siuo-progress-bar-bg">
          <div class="siuo-progress-bar-fill" id="siuo-progress-fill" style="width:0%"></div>
        </div>
      </div>

      <div class="siuo-two-col">
        <div class="siuo-panel siuo-control-panel">

          <div class="siuo-section">
            <h3 class="siuo-section-title">🚀 Indexación Masiva con Qwen3 LAN</h3>
            <p class="siuo-section-desc">
              Analiza todas las tablas de Firebird con la IA local y construye los índices
              permanentes. <strong>Los datos NUNCA salen de la red local.</strong>
            </p>
            <div class="siuo-form-row">
              <label class="siuo-label">Tablas por batch</label>
              <input type="number" id="siuo-batch-size" class="siuo-input siuo-input-sm"
                     value="5" min="1" max="20">
            </div>
            <div class="siuo-form-row">
              <label class="siuo-label siuo-label-check">
                <input type="checkbox" id="siuo-resume" checked>
                Reanudar desde donde se quedó
              </label>
            </div>
            <div class="siuo-btn-group">
              <button id="siuo-btn-start" class="siuo-btn siuo-btn-primary"
                      onclick="window.SIUOModule.startAnalysis()">
                🚀 Iniciar Análisis Completo
              </button>
              <button class="siuo-btn siuo-btn-secondary"
                      onclick="window.SIUOModule.reloadIndices()">
                🔄 Recargar Índices
              </button>
            </div>
          </div>

          <div class="siuo-section" id="siuo-progress-info">
            <h3 class="siuo-section-title">📈 Estado del Proceso</h3>
            <div id="siuo-progress-detail" class="siuo-progress-detail">
              <div class="siuo-loading">Cargando estado...</div>
            </div>
          </div>

          <div class="siuo-section">
            <h3 class="siuo-section-title">🧪 Probar ContextRetriever</h3>
            <p class="siuo-section-desc">
              Simula qué contexto recibiría la IA para una pregunta concreta.
            </p>
            <div class="siuo-form-row">
              <input type="text" id="siuo-test-question" class="siuo-input"
                     placeholder="Ej: artículos con más compras"
                     onkeydown="if(event.key==='Enter') window.SIUOModule.testContext()">
            </div>
            <div class="siuo-form-row">
              <label class="siuo-label">Máx. tokens de contexto</label>
              <input type="number" id="siuo-test-tokens" class="siuo-input siuo-input-sm"
                     value="2000" min="100" max="8000">
            </div>
            <button class="siuo-btn siuo-btn-secondary"
                    onclick="window.SIUOModule.testContext()">
              🔍 Probar
            </button>
            <div id="siuo-test-result" class="siuo-test-result" style="display:none;"></div>
          </div>

          <div class="siuo-section">
            <h3 class="siuo-section-title">🚦 Banco de Pruebas del Sistema</h3>
            <p class="siuo-section-desc">
              Prueba todo el sistema: SIUO → Qwen3 LAN → SQL → Firebird → Respuesta.
            </p>
            <div class="siuo-test-bank" id="siuo-test-bank">${bankHtml}</div>
            <div id="siuo-quicktest-result" class="siuo-test-result"
                 style="display:none; margin-top:12px;"></div>
          </div>

          <div class="siuo-section">
            <h3 class="siuo-section-title">🎓 Sugerencias de Autoaprendizaje</h3>
            <p class="siuo-section-desc">
              Keywords frecuentes sin mapear en el concept_index.
            </p>
            <button class="siuo-btn siuo-btn-secondary"
                    onclick="window.SIUOModule.loadSuggestions()">
              💡 Ver Sugerencias
            </button>
            <div id="siuo-suggestions" class="siuo-suggestions"></div>
          </div>

        </div>

        <div class="siuo-panel siuo-log-panel">
          <div class="siuo-log-header">
            <h3 class="siuo-section-title">📋 Log de Progreso</h3>
            <button class="siuo-btn-icon" onclick="window.SIUOModule.clearLog()"
                    title="Limpiar log">🗑️</button>
          </div>
          <div id="siuo-log" class="siuo-log">
            <div class="siuo-log-empty">El log aparecerá aquí cuando inicies el análisis.</div>
          </div>
        </div>
      </div>
    </div>`;
}

function _statCard(icon, id, label) {
  return `
    <div class="siuo-stat-card siuo-loading-card">
      <div class="siuo-stat-icon">${icon}</div>
      <div class="siuo-stat-value" id="${id}">—</div>
      <div class="siuo-stat-label">${label}</div>
    </div>`;
}

// ─── Estadísticas ─────────────────────────────────────────────────────────────

export function renderStats(data) {
  const indexer = data?.indexer || {};
  const retriever = data?.retriever || {};
  _setText(
    "siuo-stat-tables",
    indexer.tables_indexed ?? retriever.tables_indexed ?? "—",
  );
  _setText(
    "siuo-stat-edges",
    indexer.graph_edges ?? retriever.graph_edges ?? "—",
  );
  _setText(
    "siuo-stat-concepts",
    indexer.concept_keywords ?? retriever.concept_keywords ?? "—",
  );
  _setText("siuo-stat-enums", indexer.enums_indexed ?? "—");
  document
    .querySelectorAll(".siuo-loading-card")
    .forEach((el) => el.classList.remove("siuo-loading-card"));
}

// ─── Estado del proceso ───────────────────────────────────────────────────────

export function renderProgress(data) {
  const el = document.getElementById("siuo-progress-detail");
  if (!el) return;

  if (!data || data.status === "not_started") {
    el.innerHTML = `
      <div class="siuo-progress-row">
        <span class="siuo-badge siuo-badge-warn">⏸️ No iniciado</span>
        <span>Pulsa "Iniciar Análisis Completo" para comenzar.</span>
      </div>`;
    return;
  }

  const ICONS = {
    running: "🔄",
    completed: "✅",
    paused: "⏸️",
    not_started: "⏸️",
  };
  const COLORS = { running: "info", completed: "ok", paused: "warn" };
  const icon = ICONS[data.status] || "❓";
  const color = COLORS[data.status] || "warn";
  const pct =
    data.total_tables > 0
      ? Math.round((data.analyzed / data.total_tables) * 100)
      : 0;

  el.innerHTML = `
    <div class="siuo-progress-row">
      <span class="siuo-badge siuo-badge-${color}">${icon} ${data.status || "—"}</span>
    </div>
    <div class="siuo-progress-grid">
      <div class="siuo-pg-item"><span class="siuo-pg-val">${data.total_tables || 0}</span><span class="siuo-pg-lbl">Total</span></div>
      <div class="siuo-pg-item"><span class="siuo-pg-val siuo-ok">${data.analyzed || 0}</span><span class="siuo-pg-lbl">Analizadas</span></div>
      <div class="siuo-pg-item"><span class="siuo-pg-val siuo-warn">${data.failed || 0}</span><span class="siuo-pg-lbl">Error</span></div>
      <div class="siuo-pg-item"><span class="siuo-pg-val">${data.pending || 0}</span><span class="siuo-pg-lbl">Pendientes</span></div>
    </div>
    ${
      pct > 0
        ? `
    <div class="siuo-mini-progress">
      <div class="siuo-progress-bar-bg">
        <div class="siuo-progress-bar-fill" style="width:${pct}%"></div>
      </div>
      <span class="siuo-pct-label">${pct}%</span>
    </div>`
        : ""
    }
    ${data.last_updated ? `<div class="siuo-last-updated">Actualizado: ${formatDate(data.last_updated)}</div>` : ""}
    ${
      (data.failed_tables || []).length > 0
        ? `
    <details class="siuo-failed-tables">
      <summary>⚠️ ${data.failed_tables.length} tablas con error</summary>
      <ul>${data.failed_tables.map((t) => `<li>${t}</li>`).join("")}</ul>
    </details>`
        : ""
    }`;

  if (data.total_tables > 0)
    updateProgressBar(data.analyzed || 0, data.total_tables);
}

// ─── Sugerencias de autoaprendizaje ──────────────────────────────────────────

export function renderSuggestions(data) {
  const el = document.getElementById("siuo-suggestions");
  if (!el) return;

  const unknown = data?.unknown_keywords_frequent || [];
  const topTables = data?.top_tables_used || [];
  const total = data?.total_queries_logged || 0;

  if (!unknown.length && !topTables.length) {
    el.innerHTML = `
      <div class="siuo-suggestions-empty">
        ✅ ${data?.suggestion || "No hay sugerencias pendientes."}
        <br><small>${total} consultas registradas.</small>
      </div>`;
    return;
  }

  el.innerHTML = `
    <div class="siuo-suggestions-content">
      <div class="siuo-suggestions-meta">📊 ${total} consultas registradas</div>
      ${
        unknown.length
          ? `
      <div class="siuo-suggestions-group">
        <h4>🔍 Keywords frecuentes sin mapear</h4>
        <div class="siuo-kw-list">
          ${unknown
            .map(
              (kw) => `
            <span class="siuo-kw-chip" title="${kw.count} veces">
              ${escapeHtml(kw.keyword)}<span class="siuo-kw-count">${kw.count}</span>
            </span>`,
            )
            .join("")}
        </div>
      </div>`
          : ""
      }
      ${
        topTables.length
          ? `
      <div class="siuo-suggestions-group">
        <h4>📋 Tablas más consultadas</h4>
        <div class="siuo-table-list">
          ${topTables
            .map(
              (t, i) => `
            <div class="siuo-table-rank">
              <span class="siuo-rank-num">${i + 1}</span>
              <span class="siuo-rank-name">${escapeHtml(t.table)}</span>
              <span class="siuo-rank-count">${t.count} consultas</span>
            </div>`,
            )
            .join("")}
        </div>
      </div>`
          : ""
      }
      <div class="siuo-suggestions-note">💡 ${data?.suggestion || ""}</div>
    </div>`;
}

// ─── Resultado de prueba (reutilizable) ───────────────────────────────────────

/**
 * Renderiza el resultado de una consulta de prueba en el elemento dado.
 * Reutilizado por siuoTestContext y siuoRunQuickTest.
 */
export function renderTestResult(
  resultEl,
  askData,
  testData,
  questionLabel = null,
) {
  const source = askData.source || "siuo";
  const tables = (askData.tables_used || []).join(", ") || "—";
  const keywords = (askData.keywords || []).join(", ") || "—";
  const tokens = askData.tokens || 0;
  const answer = askData.answer || "(sin respuesta)";
  const hasError = !!askData.error;
  const meta = testData?.meta || {};
  const unknown = (meta.keywords_unknown || []).join(", ") || "ninguno";
  const ctxLen = testData?.context_length || 0;
  const ctxPrev = testData?.context_preview || "";

  const badgeClass = source === "siuo" ? "ok" : "warn";
  const badgeLabel =
    source === "siuo"
      ? "🧠 SIUO"
      : source === "error"
        ? "❌ Error"
        : "📄 Fallback";

  resultEl.innerHTML = `
    <div class="siuo-test-result-card">
      ${questionLabel ? `<div class="siuo-quicktest-question">🔍 <em>${escapeHtml(questionLabel)}</em></div>` : ""}
      <div class="siuo-test-meta">
        <span class="siuo-badge siuo-badge-${badgeClass}">${badgeLabel}</span>
        <span class="siuo-badge">~${tokens} tokens</span>
        <span class="siuo-badge">${(askData.tables_used || []).length} tablas</span>
      </div>
      <div class="siuo-answer-box ${hasError ? "siuo-answer-error" : ""}">
        <div class="siuo-answer-label">💬 Respuesta</div>
        <div class="siuo-answer-content">${markdownToHtml(answer)}</div>
      </div>
      <details class="siuo-debug-details">
        <summary>🔍 Detalles de trazabilidad</summary>
        <div class="siuo-test-row"><strong>Tablas:</strong> ${tables}</div>
        <div class="siuo-test-row"><strong>Keywords:</strong> ${keywords}</div>
        <div class="siuo-test-row siuo-warn"><strong>Desconocidos:</strong> ${unknown}</div>
        ${
          ctxLen > 0
            ? `
        <details style="margin-top:8px">
          <summary style="cursor:pointer;font-weight:600;">📄 Contexto (${ctxLen} chars)</summary>
          <pre class="siuo-context-preview">${escapeHtml(ctxPrev)}</pre>
        </details>`
            : ""
        }
      </details>
    </div>`;
}

// ─── Log de progreso ──────────────────────────────────────────────────────────

export function appendLog(msg, type = "info", logLines) {
  const el = document.getElementById("siuo-log");
  if (!el) return;
  const empty = el.querySelector(".siuo-log-empty");
  if (empty) empty.remove();
  const line = document.createElement("div");
  line.className = `siuo-log-line siuo-log-${type}`;
  line.textContent = `[${timeNow()}] ${msg}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  if (logLines) logLines.push({ ts: new Date().toISOString(), msg, type });
}

export function clearLog(logLines) {
  const el = document.getElementById("siuo-log");
  if (el) el.innerHTML = '<div class="siuo-log-empty">Log limpiado.</div>';
  if (logLines) logLines.length = 0;
}

// ─── Barra de progreso ────────────────────────────────────────────────────────

export function updateProgressBar(done, total) {
  const section = document.getElementById("siuo-progress-section");
  const fill = document.getElementById("siuo-progress-fill");
  const label = document.getElementById("siuo-progress-label");
  const pct = document.getElementById("siuo-progress-pct");
  if (!section || !fill) return;
  if (total > 0) {
    section.style.display = "block";
    const percent = Math.min(100, Math.round((done / total) * 100));
    fill.style.width = `${percent}%`;
    if (label) label.textContent = `${done} / ${total} tablas`;
    if (pct) pct.textContent = `${percent}%`;
  } else {
    section.style.display = "none";
  }
}

export function renderAnalyzeButton(analyzing) {
  const btn = document.getElementById("siuo-btn-start");
  if (!btn) return;
  btn.disabled = analyzing;
  btn.textContent = analyzing
    ? "⏳ Analizando..."
    : "🚀 Iniciar Análisis Completo";
}

// ─── Toast notifications ──────────────────────────────────────────────────────

export function showToast(msg, type = "info") {
  const container =
    document.getElementById("siuo-toast-container") || _createToastContainer();
  const toast = document.createElement("div");
  toast.className = `siuo-toast siuo-toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function _createToastContainer() {
  const el = document.createElement("div");
  el.id = "siuo-toast-container";
  el.className = "siuo-toast-container";
  document.body.appendChild(el);
  return el;
}

// ─── Utilidad DOM ─────────────────────────────────────────────────────────────

function _setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}
