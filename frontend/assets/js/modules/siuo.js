/**
 * siuo.js — Orquestador principal del módulo SIUO.
 *
 * RESPONSABILIDAD:
 *   Lógica de negocio: llamadas a API, SSE, polling, coordinación entre
 *   siuo_constants.js (datos/utilidades) y siuo_render.js (presentación).
 *
 * ARQUITECTURA:
 *   siuo_constants.js  ← constantes, estado, utilidades puras
 *   siuo_render.js     ← funciones de render DOM
 *   siuo.js            ← orquestador (este fichero)
 *
 * PATRÓN: Singleton expuesto en window.SIUOModule
 */

import {
  SIUO_API,
  SIUO_POLL_MS,
  SIUO_MAX_TOKENS_DEFAULT,
  siuoState,
  siuoFetch,
  siuoLog,
  escapeHtml,
} from "./siuo_constants.js";

import {
  renderSkeleton,
  renderStats,
  renderProgress,
  renderSuggestions,
  renderTestResult,
  renderAnalyzeButton,
  appendLog,
  clearLog,
  showToast,
  updateProgressBar,
} from "./siuo_render.js";

// ─── Inicialización ───────────────────────────────────────────────────────────

async function siuoInit() {
  if (siuoState.inited) {
    await _loadStats();
    return;
  }
  siuoState.inited = true;
  siuoLog("siuoInit", "app.js", "siuo", "Inicializando módulo SIUO");
  renderSkeleton();
  await Promise.all([_loadStats(), _loadProgress()]);
  _startStatsPoll();
}

// ─── Carga de datos ───────────────────────────────────────────────────────────

async function _loadStats() {
  try {
    const data = await siuoFetch(`${SIUO_API}/stats`);
    siuoState.stats = data;
    renderStats(data);
  } catch (e) {
    siuoLog("_loadStats", "siuo", "API /stats", `Error: ${e.message}`);
  }
}

async function _loadProgress() {
  try {
    const data = await siuoFetch(`${SIUO_API}/analyze/progress`);
    renderProgress(data);
  } catch (e) {
    siuoLog("_loadProgress", "siuo", "API /progress", `Error: ${e.message}`);
  }
}

async function siuoLoadSuggestions() {
  try {
    const data = await siuoFetch(`${SIUO_API}/learning/suggestions`);
    renderSuggestions(data);
  } catch (e) {
    showToast("Error cargando sugerencias: " + e.message, "error");
  }
}

// ─── Polling de estadísticas ──────────────────────────────────────────────────

function _startStatsPoll() {
  if (siuoState.pollTimer) return;
  siuoState.pollTimer = setInterval(async () => {
    if (!siuoState.analyzing) await _loadStats();
  }, SIUO_POLL_MS);
}

// ─── Análisis masivo con SSE ──────────────────────────────────────────────────

async function siuoStartAnalysis() {
  if (siuoState.analyzing) {
    showToast("⚠️ Ya hay un análisis en curso.", "warning");
    return;
  }

  const batchSize = parseInt(
    document.getElementById("siuo-batch-size")?.value || "5",
  );
  const resume = document.getElementById("siuo-resume")?.checked !== false;

  siuoLog(
    "siuoStartAnalysis",
    "UI",
    "API /analyze/start",
    `batch=${batchSize}, resume=${resume}`,
  );

  siuoState.logLines = [];
  siuoState.analyzing = true;
  renderAnalyzeButton(true);
  clearLog(siuoState.logLines);
  appendLog("🚀 Iniciando análisis...", "info", siuoState.logLines);

  try {
    const response = await fetch(`${SIUO_API}/analyze/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_size: batchSize, resume }),
    });

    if (!response.ok) {
      const err = await response
        .json()
        .catch(() => ({ detail: `HTTP ${response.status}` }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            _handleSSEEvent(JSON.parse(line.slice(6)));
          } catch (_) {
            /* ignorar líneas mal formadas */
          }
        }
      }
    }
  } catch (e) {
    appendLog(`❌ Error: ${e.message}`, "error", siuoState.logLines);
    showToast("Error en el análisis: " + e.message, "error");
  } finally {
    siuoState.analyzing = false;
    renderAnalyzeButton(false);
    await Promise.all([_loadStats(), _loadProgress()]);
  }
}

function _handleSSEEvent(event) {
  const type = event.type || "unknown";
  const log = (msg, t) => appendLog(msg, t, siuoState.logLines);

  switch (type) {
    case "start":
      log(`📊 ${event.message} (${event.already || 0} ya analizadas)`, "info");
      updateProgressBar(event.already || 0, event.total || 0);
      break;
    case "progress":
      log(
        `${event.status === "ok" ? "✅" : "❌"} ${event.message}`,
        event.status === "ok" ? "ok" : "error",
      );
      updateProgressBar(event.done || 0, event.total || 0);
      break;
    case "phase":
      log(`⚙️ ${event.message}`, "phase");
      break;
    case "complete":
      log(`🎉 ${event.message}`, "success");
      updateProgressBar(event.done || 0, event.done || 0);
      showToast(
        `✅ Análisis completado: ${event.done} OK, ${event.failed} errores`,
        "success",
      );
      break;
    case "reload":
      log(`🔄 ${event.message}`, "info");
      break;
    case "error":
      log(`❌ ${event.message}`, "error");
      showToast("Error: " + event.message, "error");
      break;
    default:
      log(`ℹ️ ${JSON.stringify(event)}`, "info");
  }
}

// ─── Recargar índices ─────────────────────────────────────────────────────────

async function siuoReloadIndices() {
  siuoLog("siuoReloadIndices", "UI", "API /reload", "Recargando índices");
  try {
    const data = await siuoFetch(`${SIUO_API}/reload`, { method: "POST" });
    showToast(`✅ ${data.message}`, "success");
    await _loadStats();
  } catch (e) {
    showToast("Error recargando: " + e.message, "error");
  }
}

// ─── Llamada compartida a la API de prueba ────────────────────────────────────

async function _callTestAPI(question, maxTokens) {
  const [askData, testData] = await Promise.all([
    siuoFetch(`${SIUO_API}/context/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, max_tokens: maxTokens }),
    }),
    siuoFetch(`${SIUO_API}/context/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, max_tokens: maxTokens }),
    }).catch(() => null),
  ]);
  return { askData, testData };
}

// ─── Probar ContextRetriever ──────────────────────────────────────────────────

async function siuoTestContext() {
  const question = document.getElementById("siuo-test-question")?.value?.trim();
  const maxTokens = parseInt(
    document.getElementById("siuo-test-tokens")?.value ||
      String(SIUO_MAX_TOKENS_DEFAULT),
  );

  if (!question) {
    showToast("Escribe una pregunta de prueba.", "warning");
    return;
  }

  siuoLog(
    "siuoTestContext",
    "UI",
    "API /context/ask",
    `question="${question}"`,
  );

  const resultEl = document.getElementById("siuo-test-result");
  if (resultEl) {
    resultEl.style.display = "block";
    resultEl.innerHTML = `
      <div class="siuo-loading">
        ⏳ Consultando Qwen3 LAN y ejecutando SQL...
        <br><small style="opacity:0.7">Esto puede tardar unos segundos</small>
      </div>`;
  }

  try {
    const { askData, testData } = await _callTestAPI(question, maxTokens);
    if (resultEl) renderTestResult(resultEl, askData, testData);
    _showExpandBtn(true);
  } catch (e) {
    if (resultEl)
      resultEl.innerHTML = `<div class="siuo-error">❌ Error: ${escapeHtml(e.message)}</div>`;
    _showExpandBtn(false);
    showToast("Error en la prueba: " + e.message, "error");
  }
}

// ─── Banco de Pruebas Rápidas ─────────────────────────────────────────────────

async function siuoRunQuickTest(question) {
  const resultEl = document.getElementById("siuo-quicktest-result");
  if (resultEl) {
    resultEl.style.display = "block";
    resultEl.innerHTML = `
      <div class="siuo-loading">
        ⏳ <strong>${escapeHtml(question)}</strong>
        <br><small style="opacity:0.7">Consultando Qwen3 LAN → SQL → Firebird...</small>
      </div>`;
    resultEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  try {
    const { askData, testData } = await _callTestAPI(
      question,
      SIUO_MAX_TOKENS_DEFAULT,
    );
    if (resultEl) renderTestResult(resultEl, askData, testData, question);
  } catch (e) {
    if (resultEl)
      resultEl.innerHTML = `<div class="siuo-error">❌ Error: ${escapeHtml(e.message)}</div>`;
    showToast("Error: " + e.message, "error");
  }
}

// ─── Modal de respuesta expandida ────────────────────────────────────────────

/**
 * Abre un modal con el contenido completo del resultado de prueba.
 * Reutiliza el HTML ya renderizado en #siuo-test-result para no re-procesar.
 * Cierra con Escape o clic en el overlay.
 */
function siuoExpandResult() {
  const resultEl = document.getElementById("siuo-test-result");
  if (!resultEl || resultEl.style.display === "none") {
    showToast("Primero ejecuta una consulta de prueba.", "warning");
    return;
  }

  // Clonar el contenido ya renderizado
  const clone = resultEl.cloneNode(true);
  clone.style.display = "block";
  clone.style.border = "none";
  clone.style.margin = "0";

  const overlay = document.createElement("div");
  overlay.className = "siuo-modal-overlay";
  overlay.id = "siuo-modal-overlay";

  const modal = document.createElement("div");
  modal.className = "siuo-modal";

  const header = document.createElement("div");
  header.className = "siuo-modal-header";
  header.innerHTML = `
    <span class="siuo-modal-title">🔍 Resultado completo</span>
    <button class="siuo-modal-close" onclick="window.SIUOModule.closeModal()" title="Cerrar (Esc)">✕</button>`;

  const body = document.createElement("div");
  body.className = "siuo-modal-body";
  body.appendChild(clone);

  modal.appendChild(header);
  modal.appendChild(body);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  // Cerrar con Escape
  const _onKey = (e) => {
    if (e.key === "Escape") siuoCloseModal();
  };
  document.addEventListener("keydown", _onKey);
  overlay._onKey = _onKey;

  // Cerrar al clic en el overlay (fuera del modal)
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) siuoCloseModal();
  });

  // Bloquear scroll del body
  document.body.style.overflow = "hidden";
}

function siuoCloseModal() {
  const overlay = document.getElementById("siuo-modal-overlay");
  if (overlay) {
    if (overlay._onKey) document.removeEventListener("keydown", overlay._onKey);
    overlay.remove();
  }
  document.body.style.overflow = "";
}

// ─── Mostrar botón expandir tras respuesta ────────────────────────────────────

function _showExpandBtn(visible) {
  const btn = document.getElementById("siuo-expand-btn");
  if (btn) btn.style.display = visible ? "inline-flex" : "none";
}

// ─── API pública (expuesta en window) ────────────────────────────────────────

window.SIUOModule = {
  init: siuoInit,
  startAnalysis: siuoStartAnalysis,
  reloadIndices: siuoReloadIndices,
  testContext: siuoTestContext,
  runQuickTest: siuoRunQuickTest,
  loadSuggestions: siuoLoadSuggestions,
  expandResult: siuoExpandResult,
  closeModal: siuoCloseModal,
  clearLog: () => clearLog(siuoState.logLines),
  loadStats: _loadStats,
};
