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
  SIUO_ADVANCED_BANK,
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

  // Panel avanzado multi-tabla (desplegable con <details>)
  const advancedBankHtml = SIUO_ADVANCED_BANK.map(
    (group) => `
    <div class="siuo-advanced-group">
      <div class="siuo-advanced-group-label">${group.label}</div>
      <div class="siuo-advanced-group-btns">
        ${group.tests
          .map(
            (t) =>
              `<button class="siuo-advanced-chip"
                 title="${escapeHtml(t.desc || t.q)}"
                 onclick="window.SIUOModule.runQuickTest('${escapeHtml(t.q).replace(/'/g, "&#39;")}')">
                 <span class="siuo-advanced-chip-text">${escapeHtml(t.text)}</span>
                 <span class="siuo-advanced-chip-desc">${escapeHtml(t.desc || "")}</span>
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
                     value="8000" min="100" max="16000">
            </div>
            <div class="siuo-btn-group">
              <button class="siuo-btn siuo-btn-secondary"
                      onclick="window.SIUOModule.testContext()">
                🔍 Probar
              </button>
              <button class="siuo-btn siuo-btn-icon siuo-btn-expand" id="siuo-expand-btn"
                      title="Ver respuesta en pantalla completa"
                      onclick="window.SIUOModule.expandResult()"
                      style="display:none;">
                ⛶ Expandir
              </button>
            </div>
            <div id="siuo-test-result" class="siuo-test-result" style="display:none;"></div>
          </div>

          <div class="siuo-section">
            <div class="siuo-section-title-row">
              <h3 class="siuo-section-title">🚦 Banco de Pruebas del Sistema</h3>
            </div>
            <p class="siuo-section-desc">
              Prueba todo el sistema: SIUO → Qwen3 LAN → SQL → Firebird → Respuesta.
            </p>
            <div class="siuo-test-bank" id="siuo-test-bank">${bankHtml}</div>
            <div id="siuo-quicktest-result" class="siuo-test-result"
                 style="display:none; margin-top:12px;"></div>
          </div>

          <div class="siuo-section siuo-advanced-section">
            <details class="siuo-advanced-details" id="siuo-advanced-details">
              <summary class="siuo-advanced-summary">
                <span class="siuo-advanced-icon">🔬</span>
                <span class="siuo-advanced-title">Consultas Avanzadas Multi-tabla</span>
                <span class="siuo-advanced-badge">${SIUO_ADVANCED_BANK.reduce((acc, g) => acc + g.tests.length, 0)} consultas</span>
                <span class="siuo-advanced-arrow">▶</span>
              </summary>
              <div class="siuo-advanced-body">
                <p class="siuo-section-desc siuo-advanced-desc">
                  Consultas que cruzan <strong>2+ tablas</strong> con JOINs, agregaciones y filtros complejos.
                  Ideales para probar la calidad del índice SIUO y la generación SQL de Qwen3.
                </p>
                <div class="siuo-advanced-bank" id="siuo-advanced-bank">
                  ${advancedBankHtml}
                </div>
                <div id="siuo-advanced-result" class="siuo-test-result"
                     style="display:none; margin-top:12px;"></div>
              </div>
            </details>
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
 * Detecta si la respuesta contiene un error de placeholder (<ID_DEL_...>).
 * La IA a veces genera SQL con placeholders literales que Firebird no puede ejecutar.
 */
function _detectPlaceholderError(answer) {
  return (
    typeof answer === "string" &&
    (answer.includes("<ID_DEL_") ||
      answer.includes("<NOMBRE_DEL_") ||
      answer.includes("<CODIGO_DEL_") ||
      /WHERE\s+\w+\s*=\s*<[^>]+>/i.test(answer))
  );
}

/**
 * Convierte un mensaje de error técnico en un mensaje amigable para el usuario.
 * El usuario no tiene por qué entender SQL ni Firebird.
 */
function _friendlyErrorMessage(answer) {
  if (!answer) return null;

  // Placeholder sin valor real (ej: WHERE CODTRABAJADOR = <ID_DEL_TRABAJADOR>)
  if (_detectPlaceholderError(answer)) {
    return {
      icon: "🔍",
      title: "Necesito más información",
      msg:
        "Para responder a esta pregunta necesito que me indiques un dato concreto. " +
        "Por ejemplo: ¿de qué trabajador quieres ver los partes? Dime su nombre o código.",
      hint: 'Prueba a preguntar: <em>"dime los 2 últimos partes de trabajo de Juan García"</em>',
      type: "info",
    };
  }

  // Error de columna desconocida
  if (/column unknown/i.test(answer) || /campo.*no existe/i.test(answer)) {
    return {
      icon: "⚠️",
      title: "La IA usó un campo incorrecto",
      msg:
        "La inteligencia artificial intentó buscar en un campo que no existe en la base de datos. " +
        "Esto puede pasar con preguntas muy específicas. Intenta reformular la pregunta.",
      hint: "Prueba a ser más concreto o usar términos del negocio (ej: 'factura', 'albarán', 'parte de trabajo').",
      type: "warn",
    };
  }

  // Error de sintaxis SQL genérico
  if (
    /dynamic sql error/i.test(answer) ||
    /sql error code/i.test(answer) ||
    /token unknown/i.test(answer)
  ) {
    return {
      icon: "⚠️",
      title: "Error al consultar la base de datos",
      msg:
        "La inteligencia artificial generó una consulta que la base de datos no pudo ejecutar. " +
        "Esto suele ocurrir con preguntas muy complejas o poco habituales.",
      hint: "Intenta reformular la pregunta de forma más sencilla.",
      type: "warn",
    };
  }

  // Error genérico de "intenté ejecutar pero falló"
  if (
    /intenté ejecutar.*falló/i.test(answer) ||
    /error después de/i.test(answer)
  ) {
    return {
      icon: "⚠️",
      title: "No pude obtener la respuesta",
      msg:
        "Intenté consultar la base de datos pero encontré un problema técnico. " +
        "Puede que la pregunta necesite más contexto o que la información no esté disponible.",
      hint: "Prueba a reformular la pregunta o añadir más detalles.",
      type: "warn",
    };
  }

  return null; // Sin error detectado
}

/**
 * Renderiza el resultado de una consulta de prueba en el elemento dado.
 * Reutilizado por siuoTestContext y siuoRunQuickTest.
 *
 * FILOSOFÍA: El usuario no tiene conocimientos técnicos.
 * - La respuesta principal es amigable y clara.
 * - Toda la info técnica (SQL, tablas, contexto) va en desplegables.
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

  // Detectar si hay un error amigable que mostrar
  const friendlyError = _friendlyErrorMessage(answer);

  const badgeClass = source === "siuo" ? "ok" : "warn";
  const badgeLabel =
    source === "siuo"
      ? "🧠 SIUO"
      : source === "error"
        ? "❌ Error"
        : "📄 Fallback";

  // Construir el bloque de respuesta principal
  let answerHtml;
  if (friendlyError) {
    // Respuesta amigable para el usuario
    answerHtml = `
      <div class="siuo-friendly-error siuo-friendly-${friendlyError.type}">
        <div class="siuo-friendly-icon">${friendlyError.icon}</div>
        <div class="siuo-friendly-content">
          <div class="siuo-friendly-title">${friendlyError.title}</div>
          <div class="siuo-friendly-msg">${friendlyError.msg}</div>
          ${friendlyError.hint ? `<div class="siuo-friendly-hint">💡 ${friendlyError.hint}</div>` : ""}
        </div>
      </div>
      <details class="siuo-debug-details siuo-debug-error-raw" style="margin-top:8px">
        <summary>🔧 Ver detalle técnico del error</summary>
        <div class="siuo-answer-content siuo-answer-error">${markdownToHtml(answer)}</div>
      </details>`;
  } else if (hasError) {
    answerHtml = `
      <div class="siuo-answer-box siuo-answer-error">
        <div class="siuo-answer-label">⚠️ Resultado</div>
        <div class="siuo-answer-content">${markdownToHtml(answer)}</div>
      </div>`;
  } else {
    answerHtml = `
      <div class="siuo-answer-box">
        <div class="siuo-answer-label">💬 Respuesta</div>
        <div class="siuo-answer-content">${markdownToHtml(answer)}</div>
      </div>`;
  }

  resultEl.innerHTML = `
    <div class="siuo-test-result-card">
      ${questionLabel ? `<div class="siuo-quicktest-question">🔍 <em>${escapeHtml(questionLabel)}</em></div>` : ""}
      <div class="siuo-test-meta">
        <span class="siuo-badge siuo-badge-${badgeClass}">${badgeLabel}</span>
        <span class="siuo-badge">~${tokens} tokens</span>
        <span class="siuo-badge">${(askData.tables_used || []).length} tablas</span>
      </div>
      ${answerHtml}
      <details class="siuo-debug-details">
        <summary>🔍 Detalles técnicos (para desarrolladores)</summary>
        <div class="siuo-test-row"><strong>Tablas usadas:</strong> ${escapeHtml(tables)}</div>
        <div class="siuo-test-row"><strong>Keywords detectados:</strong> ${escapeHtml(keywords)}</div>
        ${unknown !== "ninguno" ? `<div class="siuo-test-row siuo-warn"><strong>⚠️ Keywords sin mapear:</strong> ${escapeHtml(unknown)}</div>` : ""}
        ${
          ctxLen > 0
            ? `
        <details style="margin-top:8px">
          <summary style="cursor:pointer;font-weight:600;">📄 Contexto enviado a la IA (${ctxLen} chars)</summary>
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
