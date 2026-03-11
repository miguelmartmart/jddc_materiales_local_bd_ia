/**
 * siuo.js — Módulo Frontend: Sistema de Índices Ultra-Optimizado (SIUO)
 *
 * RESPONSABILIDAD:
 *   UI para gestionar el SIUO: iniciar indexación masiva de las 437 tablas
 *   Firebird con Qwen3 LAN, ver progreso en tiempo real (SSE), consultar
 *   estadísticas de los índices y probar el ContextRetriever.
 *
 * SEGURIDAD:
 *   Los datos de la BD SOLO van a la IA local LAN (Qwen3).
 *   El backend bloquea cualquier envío a internet.
 *
 * ENDPOINTS:
 *   POST /api/siuo/analyze/start          → SSE streaming de progreso
 *   GET  /api/siuo/analyze/progress       → Estado actual
 *   GET  /api/siuo/stats                  → Estadísticas de índices
 *   GET  /api/siuo/learning/suggestions   → Sugerencias autoaprendizaje
 *   POST /api/siuo/learning/feedback      → Registrar feedback SQL
 *   POST /api/siuo/reload                 → Recargar índices en memoria
 *   POST /api/siuo/context/test           → Probar ContextRetriever
 *
 * DEPENDENCIAS: Ninguna (vanilla JS, sin módulos externos)
 * PATRÓN: Singleton expuesto en window.SIUOModule
 */

// ─── Constantes ───────────────────────────────────────────────────────────────

const SIUO_API = "/api/siuo";
const SIUO_POLL_MS = 3000; // ms entre actualizaciones de stats en modo idle

// ─── Estado del módulo ────────────────────────────────────────────────────────

const siuoState = {
  analyzing: false, // true mientras hay SSE activo
  eventSource: null, // EventSource activo
  logLines: [], // Líneas del log de progreso
  stats: null, // Últimas estadísticas cargadas
  pollTimer: null, // Timer de polling de stats
  inited: false, // true tras primera inicialización
};

// ─── Inicialización ───────────────────────────────────────────────────────────

/**
 * Inicializa el módulo SIUO. Llamar cuando se activa la pestaña.
 * EMISOR: app.js  RECEPTOR: siuo.js
 */
async function siuoInit() {
  if (siuoState.inited) {
    // Ya inicializado: solo refrescar stats
    await siuoLoadStats();
    return;
  }
  siuoState.inited = true;
  siuoLog("siuoInit", "app.js", "siuo", "Inicializando módulo SIUO");
  siuoRenderSkeleton();
  await siuoLoadStats();
  await siuoLoadProgress();
  siuoStartStatsPoll();
}

// ─── Carga de datos ───────────────────────────────────────────────────────────

async function siuoLoadStats() {
  try {
    const data = await siuoFetch(`${SIUO_API}/stats`);
    siuoState.stats = data;
    siuoRenderStats(data);
  } catch (e) {
    siuoLog("siuoLoadStats", "siuo", "API /stats", `Error: ${e.message}`);
  }
}

async function siuoLoadProgress() {
  try {
    const data = await siuoFetch(`${SIUO_API}/analyze/progress`);
    siuoRenderProgress(data);
  } catch (e) {
    siuoLog("siuoLoadProgress", "siuo", "API /progress", `Error: ${e.message}`);
  }
}

async function siuoLoadSuggestions() {
  try {
    const data = await siuoFetch(`${SIUO_API}/learning/suggestions`);
    siuoRenderSuggestions(data);
  } catch (e) {
    siuoShowToast("Error cargando sugerencias: " + e.message, "error");
  }
}

// ─── Polling de estadísticas ──────────────────────────────────────────────────

function siuoStartStatsPoll() {
  if (siuoState.pollTimer) return;
  siuoState.pollTimer = setInterval(async () => {
    if (!siuoState.analyzing) {
      await siuoLoadStats();
    }
  }, SIUO_POLL_MS);
}

function siuoStopStatsPoll() {
  if (siuoState.pollTimer) {
    clearInterval(siuoState.pollTimer);
    siuoState.pollTimer = null;
  }
}

// ─── Análisis masivo con SSE ──────────────────────────────────────────────────

/**
 * Inicia el análisis completo de todas las tablas con Qwen3 LAN.
 * Usa SSE (Server-Sent Events) para recibir progreso en tiempo real.
 */
async function siuoStartAnalysis() {
  if (siuoState.analyzing) {
    siuoShowToast("⚠️ Ya hay un análisis en curso.", "warning");
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

  // Limpiar log anterior
  siuoState.logLines = [];
  siuoState.analyzing = true;
  siuoRenderAnalyzeButton(true);
  siuoClearLog();
  siuoAppendLog("🚀 Iniciando análisis...", "info");

  try {
    // Enviar POST para iniciar y obtener SSE
    const url = `${SIUO_API}/analyze/start`;
    const response = await fetch(url, {
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

    // Leer el stream SSE manualmente (fetch + ReadableStream)
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Guardar línea incompleta

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const event = JSON.parse(line.slice(6));
            siuoHandleSSEEvent(event);
          } catch (_) {
            // Ignorar líneas mal formadas
          }
        }
      }
    }
  } catch (e) {
    siuoAppendLog(`❌ Error: ${e.message}`, "error");
    siuoShowToast("Error en el análisis: " + e.message, "error");
  } finally {
    siuoState.analyzing = false;
    siuoRenderAnalyzeButton(false);
    await siuoLoadStats();
    await siuoLoadProgress();
  }
}

/**
 * Procesa un evento SSE recibido del backend.
 */
function siuoHandleSSEEvent(event) {
  const type = event.type || "unknown";

  switch (type) {
    case "start":
      siuoAppendLog(
        `📊 ${event.message} (${event.already || 0} ya analizadas)`,
        "info",
      );
      siuoUpdateProgressBar(event.already || 0, event.total || 0);
      break;

    case "progress": {
      const icon = event.status === "ok" ? "✅" : "❌";
      siuoAppendLog(
        `${icon} ${event.message}`,
        event.status === "ok" ? "ok" : "error",
      );
      siuoUpdateProgressBar(event.done || 0, event.total || 0);
      break;
    }

    case "phase":
      siuoAppendLog(`⚙️ ${event.message}`, "phase");
      break;

    case "complete":
      siuoAppendLog(`🎉 ${event.message}`, "success");
      siuoUpdateProgressBar(event.done || 0, event.done || 0);
      siuoShowToast(
        `✅ Análisis completado: ${event.done} tablas OK, ${event.failed} errores`,
        "success",
      );
      break;

    case "reload":
      siuoAppendLog(`🔄 ${event.message}`, "info");
      break;

    case "error":
      siuoAppendLog(`❌ ${event.message}`, "error");
      siuoShowToast("Error: " + event.message, "error");
      break;

    default:
      siuoAppendLog(`ℹ️ ${JSON.stringify(event)}`, "info");
  }
}

// ─── Recargar índices ─────────────────────────────────────────────────────────

async function siuoReloadIndices() {
  siuoLog(
    "siuoReloadIndices",
    "UI",
    "API /reload",
    "Recargando índices en memoria",
  );
  try {
    const data = await siuoFetch(`${SIUO_API}/reload`, { method: "POST" });
    siuoShowToast(`✅ ${data.message}`, "success");
    siuoRenderStats({
      indexer: data.stats ? {} : {},
      retriever: data.stats || {},
    });
    await siuoLoadStats();
  } catch (e) {
    siuoShowToast("Error recargando: " + e.message, "error");
  }
}

// ─── Probar ContextRetriever ──────────────────────────────────────────────────

/**
 * siuoTestContext — Envía la pregunta al backend completo:
 *   1. ContextRetriever obtiene el contexto óptimo (SIUO)
 *   2. Qwen3 LAN genera el SQL
 *   3. Se ejecuta contra Firebird
 *   4. Se muestra la respuesta real al usuario
 *
 * Llama a POST /api/siuo/context/ask (respuesta completa)
 * y también a POST /api/siuo/context/test (metadatos de debug).
 */
async function siuoTestContext() {
  const question = document.getElementById("siuo-test-question")?.value?.trim();
  const maxTokens = parseInt(
    document.getElementById("siuo-test-tokens")?.value || "2000",
  );

  if (!question) {
    siuoShowToast("Escribe una pregunta de prueba.", "warning");
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
    resultEl.innerHTML = `
      <div class="siuo-loading">
        ⏳ Consultando Qwen3 LAN y ejecutando SQL...
        <br><small style="opacity:0.7">Esto puede tardar unos segundos</small>
      </div>`;
    resultEl.style.display = "block";
  }

  // Llamadas en paralelo: respuesta completa + metadatos de debug
  try {
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
      }).catch(() => null), // debug es opcional
    ]);

    if (!resultEl) return;

    const source = askData.source || "siuo";
    const tables = (askData.tables_used || []).join(", ") || "—";
    const keywords = (askData.keywords || []).join(", ") || "—";
    const tokens = askData.tokens || 0;
    const answer = askData.answer || "(sin respuesta)";
    const hasError = !!askData.error;

    // Metadatos de debug (del endpoint /context/test)
    const meta = testData?.meta || {};
    const unknown = (meta.keywords_unknown || []).join(", ") || "ninguno";
    const ctxLen = testData?.context_length || 0;
    const ctxPreview = testData?.context_preview || "";

    // Formatear la respuesta de la IA (Markdown básico → HTML)
    const answerHtml = _markdownToHtml(answer);

    resultEl.innerHTML = `
      <div class="siuo-test-result-card">

        <!-- Badges de metadatos -->
        <div class="siuo-test-meta">
          <span class="siuo-badge siuo-badge-${source === "siuo" ? "ok" : "warn"}">
            Fuente: ${source === "siuo" ? "🧠 SIUO" : source === "error" ? "❌ Error" : "📄 Fallback v1"}
          </span>
          <span class="siuo-badge">~${tokens} tokens</span>
          <span class="siuo-badge">${(askData.tables_used || []).length} tablas</span>
        </div>

        <!-- Respuesta principal de la IA -->
        <div class="siuo-answer-box ${hasError ? "siuo-answer-error" : ""}">
          <div class="siuo-answer-label">💬 Respuesta</div>
          <div class="siuo-answer-content">${answerHtml}</div>
        </div>

        <!-- Metadatos de trazabilidad (colapsable) -->
        <details class="siuo-debug-details">
          <summary>🔍 Detalles de trazabilidad</summary>
          <div class="siuo-test-row"><strong>Tablas usadas:</strong> ${tables}</div>
          <div class="siuo-test-row"><strong>Keywords encontrados:</strong> ${keywords}</div>
          <div class="siuo-test-row siuo-warn"><strong>Keywords desconocidos:</strong> ${unknown}</div>
          ${
            ctxLen > 0
              ? `
          <details style="margin-top:8px">
            <summary style="cursor:pointer; font-weight:600;">📄 Contexto enviado a la IA (${ctxLen} chars)</summary>
            <pre class="siuo-context-preview">${_escapeHtml(ctxPreview)}</pre>
          </details>`
              : ""
          }
        </details>

      </div>`;
  } catch (e) {
    if (resultEl) {
      resultEl.innerHTML = `<div class="siuo-error">❌ Error: ${_escapeHtml(e.message)}</div>`;
    }
    siuoShowToast("Error en la prueba: " + e.message, "error");
  }
}

/**
 * Convierte Markdown básico a HTML seguro para mostrar en el panel.
 * Solo convierte: negrita, cursiva, listas, saltos de línea.
 * NO usa innerHTML con contenido sin escapar (XSS safe).
 */
function _markdownToHtml(text) {
  if (!text) return "";
  let html = _escapeHtml(text);
  // Negrita: **texto** → <strong>texto</strong>
  html = html.replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>");
  // Cursiva: *texto* → <em>texto</em>
  html = html.replace(/\*([^*\n]+?)\*/g, "<em>$1</em>");
  // Código inline: `texto` → <code>texto</code>
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Listas: líneas que empiezan con "- " o "* "
  html = html.replace(/^[-\*]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");
  // Saltos de línea dobles → párrafos
  html = html.replace(/\n\n+/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");
  return `<p>${html}</p>`;
}

// ─── Render: Skeleton principal ───────────────────────────────────────────────

function siuoRenderSkeleton() {
  const root = document.getElementById("siuo-root");
  if (!root) return;

  root.innerHTML = `
    <div class="siuo-layout">

      <!-- Cabecera con stats -->
      <div class="siuo-header-cards" id="siuo-stats-cards">
        <div class="siuo-stat-card siuo-loading-card">
          <div class="siuo-stat-icon">🗄️</div>
          <div class="siuo-stat-value" id="siuo-stat-tables">—</div>
          <div class="siuo-stat-label">Tablas indexadas</div>
        </div>
        <div class="siuo-stat-card siuo-loading-card">
          <div class="siuo-stat-icon">🔗</div>
          <div class="siuo-stat-value" id="siuo-stat-edges">—</div>
          <div class="siuo-stat-label">Relaciones en grafo</div>
        </div>
        <div class="siuo-stat-card siuo-loading-card">
          <div class="siuo-stat-icon">🔑</div>
          <div class="siuo-stat-value" id="siuo-stat-concepts">—</div>
          <div class="siuo-stat-label">Keywords en índice</div>
        </div>
        <div class="siuo-stat-card siuo-loading-card">
          <div class="siuo-stat-icon">📊</div>
          <div class="siuo-stat-value" id="siuo-stat-enums">—</div>
          <div class="siuo-stat-label">Enumerados indexados</div>
        </div>
      </div>

      <!-- Barra de progreso global -->
      <div class="siuo-progress-section" id="siuo-progress-section" style="display:none;">
        <div class="siuo-progress-header">
          <span id="siuo-progress-label">Progreso</span>
          <span id="siuo-progress-pct">0%</span>
        </div>
        <div class="siuo-progress-bar-bg">
          <div class="siuo-progress-bar-fill" id="siuo-progress-fill" style="width:0%"></div>
        </div>
      </div>

      <!-- Dos columnas: Control + Log -->
      <div class="siuo-two-col">

        <!-- Columna izquierda: controles -->
        <div class="siuo-panel siuo-control-panel">

          <!-- Sección: Indexación masiva -->
          <div class="siuo-section">
            <h3 class="siuo-section-title">🚀 Indexación Masiva con Qwen3 LAN</h3>
            <p class="siuo-section-desc">
              Analiza todas las tablas de Firebird con la IA local y construye los índices
              permanentes (table_index, concept_index, db_graph, value_index).
              <strong>Los datos NUNCA salen de la red local.</strong>
            </p>

            <div class="siuo-form-row">
              <label class="siuo-label">Tablas por batch</label>
              <input type="number" id="siuo-batch-size" class="siuo-input siuo-input-sm"
                     value="5" min="1" max="20" title="Tablas que se analizan en paralelo">
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

          <!-- Sección: Estado del proceso -->
          <div class="siuo-section" id="siuo-progress-info">
            <h3 class="siuo-section-title">📈 Estado del Proceso</h3>
            <div id="siuo-progress-detail" class="siuo-progress-detail">
              <div class="siuo-loading">Cargando estado...</div>
            </div>
          </div>

          <!-- Sección: Probar ContextRetriever -->
          <div class="siuo-section">
            <h3 class="siuo-section-title">🧪 Probar ContextRetriever</h3>
            <p class="siuo-section-desc">
              Simula qué contexto recibiría la IA para una pregunta concreta.
              Útil para validar que los índices funcionan correctamente.
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

          <!-- Sección: Autoaprendizaje -->
          <div class="siuo-section">
            <h3 class="siuo-section-title">🎓 Sugerencias de Autoaprendizaje</h3>
            <p class="siuo-section-desc">
              Keywords frecuentes que los usuarios usan pero no están mapeados en el
              concept_index. Añadirlos mejora la precisión del chat IA.
            </p>
            <button class="siuo-btn siuo-btn-secondary"
                    onclick="window.SIUOModule.loadSuggestions()">
              💡 Ver Sugerencias
            </button>
            <div id="siuo-suggestions" class="siuo-suggestions"></div>
          </div>

        </div>

        <!-- Columna derecha: log de progreso -->
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

// ─── Render: Estadísticas ─────────────────────────────────────────────────────

function siuoRenderStats(data) {
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

  // Quitar clase de loading
  document
    .querySelectorAll(".siuo-loading-card")
    .forEach((el) => el.classList.remove("siuo-loading-card"));
}

// ─── Render: Estado del proceso ───────────────────────────────────────────────

function siuoRenderProgress(data) {
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

  const statusIcon =
    {
      running: "🔄",
      completed: "✅",
      paused: "⏸️",
      not_started: "⏸️",
    }[data.status] || "❓";

  const statusColor =
    {
      running: "info",
      completed: "ok",
      paused: "warn",
    }[data.status] || "warn";

  const pct =
    data.total_tables > 0
      ? Math.round((data.analyzed / data.total_tables) * 100)
      : 0;

  el.innerHTML = `
    <div class="siuo-progress-row">
      <span class="siuo-badge siuo-badge-${statusColor}">${statusIcon} ${data.status || "—"}</span>
    </div>
    <div class="siuo-progress-grid">
      <div class="siuo-pg-item"><span class="siuo-pg-val">${data.total_tables || 0}</span><span class="siuo-pg-lbl">Total tablas</span></div>
      <div class="siuo-pg-item"><span class="siuo-pg-val siuo-ok">${data.analyzed || 0}</span><span class="siuo-pg-lbl">Analizadas</span></div>
      <div class="siuo-pg-item"><span class="siuo-pg-val siuo-warn">${data.failed || 0}</span><span class="siuo-pg-lbl">Con error</span></div>
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
    ${data.last_updated ? `<div class="siuo-last-updated">Última actualización: ${_formatDate(data.last_updated)}</div>` : ""}
    ${
      (data.failed_tables || []).length > 0
        ? `
    <details class="siuo-failed-tables">
      <summary>⚠️ ${data.failed_tables.length} tablas con error</summary>
      <ul>${data.failed_tables.map((t) => `<li>${t}</li>`).join("")}</ul>
    </details>`
        : ""
    }`;

  // Mostrar barra de progreso global si hay datos
  if (data.total_tables > 0) {
    siuoUpdateProgressBar(data.analyzed || 0, data.total_tables);
  }
}

// ─── Render: Sugerencias de autoaprendizaje ───────────────────────────────────

function siuoRenderSuggestions(data) {
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
      <div class="siuo-suggestions-meta">
        📊 ${total} consultas registradas en el historial
      </div>

      ${
        unknown.length
          ? `
      <div class="siuo-suggestions-group">
        <h4>🔍 Keywords frecuentes sin mapear</h4>
        <p class="siuo-section-desc">Considera añadir estos al <code>concept_index.json</code>:</p>
        <div class="siuo-kw-list">
          ${unknown
            .map(
              (kw) => `
            <span class="siuo-kw-chip" title="${kw.count} veces">
              ${_escapeHtml(kw.keyword)}
              <span class="siuo-kw-count">${kw.count}</span>
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
              <span class="siuo-rank-name">${_escapeHtml(t.table)}</span>
              <span class="siuo-rank-count">${t.count} consultas</span>
            </div>`,
            )
            .join("")}
        </div>
      </div>`
          : ""
      }

      <div class="siuo-suggestions-note">
        💡 ${data?.suggestion || ""}
      </div>
    </div>`;
}

// ─── Log de progreso ──────────────────────────────────────────────────────────

function siuoAppendLog(msg, type = "info") {
  const el = document.getElementById("siuo-log");
  if (!el) return;

  // Quitar mensaje de vacío
  const empty = el.querySelector(".siuo-log-empty");
  if (empty) empty.remove();

  const line = document.createElement("div");
  line.className = `siuo-log-line siuo-log-${type}`;
  line.textContent = `[${_timeNow()}] ${msg}`;
  el.appendChild(line);

  // Auto-scroll al final
  el.scrollTop = el.scrollHeight;

  // Guardar en estado
  siuoState.logLines.push({ ts: new Date().toISOString(), msg, type });
}

function siuoClearLog() {
  const el = document.getElementById("siuo-log");
  if (el) {
    el.innerHTML = '<div class="siuo-log-empty">Log limpiado.</div>';
  }
  siuoState.logLines = [];
}

// ─── Barra de progreso ────────────────────────────────────────────────────────

function siuoUpdateProgressBar(done, total) {
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

// ─── Botón de análisis ────────────────────────────────────────────────────────

function siuoRenderAnalyzeButton(analyzing) {
  const btn = document.getElementById("siuo-btn-start");
  if (!btn) return;
  btn.disabled = analyzing;
  btn.textContent = analyzing
    ? "⏳ Analizando..."
    : "🚀 Iniciar Análisis Completo";
}

// ─── Toast notifications ──────────────────────────────────────────────────────

function siuoShowToast(msg, type = "info") {
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

// ─── Utilidades ───────────────────────────────────────────────────────────────

function _setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function _timeNow() {
  return new Date().toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function _formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("es-ES");
  } catch (_) {
    return iso;
  }
}

function _escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function siuoFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    try {
      const body = await res.json();
      err.message = body.detail || err.message;
    } catch (_) {}
    throw err;
  }
  return res.json();
}

function siuoLog(step, emisor, receptor, msg) {
  console.log(`[SIUO][${step}] ${emisor} → ${receptor}: ${msg}`);
}

// ─── API pública (expuesta en window) ────────────────────────────────────────

window.SIUOModule = {
  init: siuoInit,
  startAnalysis: siuoStartAnalysis,
  reloadIndices: siuoReloadIndices,
  testContext: siuoTestContext,
  loadSuggestions: siuoLoadSuggestions,
  clearLog: siuoClearLog,
  loadStats: siuoLoadStats,
};
