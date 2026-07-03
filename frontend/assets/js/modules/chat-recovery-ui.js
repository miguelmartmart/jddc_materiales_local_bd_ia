/**
 * chat-recovery-ui.js — Renderizado DOM del sistema de recuperación de chat
 *
 * Responsabilidad única: inyectar y gestionar los elementos DOM del chat recovery:
 *   - Botón Cancelar en el bubble "Pensando..."
 *   - Barra de progreso para peticiones largas
 *   - Bloque de reintento con mensaje amigable + traza técnica colapsable
 *
 * Principios DEVIA:
 * - Fichero < 500 líneas, una responsabilidad (SRP)
 * - Sin estado propio — recibe todo por parámetros
 * - Estilos inline centralizados en STYLES (sin CSS externo)
 * - Importa constantes de constants.js (no hardcodea valores)
 *
 * Exporta:
 *   - CANCEL_BTN_ID, RETRY_CONTAINER_ID, PROGRESS_BAR_ID  (IDs DOM)
 *   - injectCancelButton(thinkingId, trace, isDeep, configuredTimeout, startedAt, onCancel) → intervalHandle
 *   - injectRetryBlock(reason, trace, elapsed, extra, configuredTimeout, attemptCount, onRetry, lastPayload)
 *   - updateStatusLabel(thinkingId, text)
 */

import { TIMEOUTS, RECOVERY_MESSAGES } from '../core/constants.js';

// ── IDs DOM exportados (usados por ChatRecovery para limpiar) ─────────────────
export const CANCEL_BTN_ID      = 'chat-cancel-btn';
export const RETRY_CONTAINER_ID = 'chat-retry-container';
export const PROGRESS_BAR_ID    = 'chat-progress-bar';

// ── Estilos inline centralizados ──────────────────────────────────────────────
const STYLES = {
  CANCEL_BTN: [
    'display:inline-flex', 'align-items:center', 'gap:4px',
    'padding:4px 10px', 'font-size:0.8em', 'border-radius:4px',
    'border:1px solid #fca5a5', 'background:#fee2e2', 'color:#b91c1c',
    'cursor:pointer', 'margin-left:8px', 'vertical-align:middle',
    'transition:background 0.15s',
  ].join(';'),
  RETRY_BTN: [
    'display:inline-flex', 'align-items:center', 'gap:4px',
    'padding:6px 14px', 'font-size:0.88em', 'border-radius:6px',
    'border:none', 'background:#2563eb', 'color:white',
    'cursor:pointer', 'margin-top:10px', 'font-weight:600',
    'transition:background 0.15s',
  ].join(';'),
  RETRY_CONTAINER: [
    'margin-top:8px', 'padding:12px 14px', 'background:#eff6ff',
    'border:1px solid #bfdbfe', 'border-radius:8px', 'font-size:0.88em',
    'color:#1e40af', 'line-height:1.6', 'max-width:95%',
  ].join(';'),
  TRACE_BLOCK: [
    'margin-top:8px', 'padding:8px 10px', 'background:#f1f5f9',
    'border:1px solid #e2e8f0', 'border-radius:6px',
    'font-size:0.78em', 'color:#475569', 'font-family:monospace',
    'white-space:pre-wrap', 'word-break:break-all',
  ].join(';'),
  TRACE_TOGGLE: [
    'background:none', 'border:none', 'color:#64748b', 'cursor:pointer',
    'font-size:0.78em', 'padding:2px 0', 'margin-top:4px',
    'text-decoration:underline',
  ].join(';'),
  PROGRESS_BAR_WRAP: [
    'margin-top:6px', 'height:4px', 'background:#dbeafe',
    'border-radius:2px', 'overflow:hidden',
  ].join(';'),
  PROGRESS_BAR: [
    'height:100%', 'background:#3b82f6', 'border-radius:2px',
    'transition:width 1s linear',
  ].join(';'),
};

// ── Mapa de razones de error → mensaje amigable para el usuario ───────────────
export const USER_MESSAGES = {
  timeout:          '⏱️ El modelo IA tardó demasiado en responder.',
  cancelled:        '⚠️ Petición cancelada.',
  network:          '🔌 No se pudo conectar con el servidor backend.',
  connection_drop:  '🔄 La conexión se interrumpió mientras la IA procesaba (el modelo sigue activo).',
  backend_timeout:  '⏱️ El backend superó el tiempo máximo de espera de la IA.',
  http_502:         '🔴 El servidor de IA no está disponible (502).',
  http_503:         '🔴 El servidor de IA está sobrecargado (503).',
  http_500:         '🔴 Error interno del servidor de IA (500).',
  default:          '❌ La petición no se completó.',
};

// ── Actualizar label de estado en el bubble "Pensando..." ─────────────────────

/**
 * Actualiza o crea el label de estado en el bubble "Pensando...".
 * @param {string} thinkingId - ID del elemento DOM del bubble
 * @param {string} text       - Texto a mostrar
 */
export function updateStatusLabel(thinkingId, text) {
  const bubble = thinkingId ? document.getElementById(thinkingId) : null;
  if (!bubble) return;
  let label = bubble.querySelector('.devia-status-label');
  if (!label) {
    label = document.createElement('div');
    label.className = 'devia-status-label';
    label.style.cssText = 'font-size:0.72em;color:#64748b;margin-top:4px;font-style:italic;';
    bubble.appendChild(label);
  }
  label.textContent = text;
}

// ── Botón Cancelar + barra de progreso ───────────────────────────────────────

/**
 * Inyecta el botón Cancelar en el bubble "Pensando..." y una barra de progreso
 * para peticiones largas (deep_analysis o timeout ≥ 180s).
 *
 * @param {string}   thinkingId       - ID del elemento DOM del bubble
 * @param {object}   trace            - Traza de diagnóstico (modelId, preferredModel, dbMode)
 * @param {boolean}  isDeep           - Si es análisis profundo
 * @param {number}   configuredTimeout - Timeout configurado en ms
 * @param {number}   startedAt        - Timestamp de inicio (Date.now())
 * @param {Function} onCancel         - Callback al pulsar Cancelar
 * @returns {number|null} Handle del intervalo de la barra de progreso (para limpiar)
 */
export function injectCancelButton(thinkingId, trace, isDeep, configuredTimeout, startedAt, onCancel) {
  let progressHandle = null;

  requestAnimationFrame(() => {
    const bubble = document.getElementById(thinkingId);
    if (!bubble) return;

    // ── Botón Cancelar ────────────────────────────────────────────────────────
    const btn = document.createElement('button');
    btn.id            = CANCEL_BTN_ID;
    btn.style.cssText = STYLES.CANCEL_BTN;
    btn.title         = RECOVERY_MESSAGES.BTN_CANCEL_TITLE;
    btn.textContent   = RECOVERY_MESSAGES.BTN_CANCEL;

    btn.addEventListener('click', () => onCancel());
    btn.addEventListener('mouseenter', () => { btn.style.background = '#fecaca'; });
    btn.addEventListener('mouseleave', () => { btn.style.background = '#fee2e2'; });

    // ── Info de contexto (modelo + BD + modo) ─────────────────────────────────
    const ctxSpan = document.createElement('span');
    ctxSpan.style.cssText = 'font-size:0.78em; color:#64748b; margin-left:6px;';
    const modeTag = isDeep ? ' · 🔬 Análisis profundo' : '';
    ctxSpan.textContent = `[${trace.modelId}${trace.preferredModel ? ' / ' + trace.preferredModel : ''} · ${trace.dbMode}${modeTag}]`;

    bubble.appendChild(ctxSpan);
    bubble.appendChild(btn);

    // ── Barra de progreso para peticiones largas ──────────────────────────────
    if (isDeep || configuredTimeout >= 180000) {
      const barWrap = document.createElement('div');
      barWrap.style.cssText = STYLES.PROGRESS_BAR_WRAP;

      const bar = document.createElement('div');
      bar.id            = PROGRESS_BAR_ID;
      bar.style.cssText = STYLES.PROGRESS_BAR;
      bar.style.width   = '0%';

      barWrap.appendChild(bar);
      bubble.appendChild(barWrap);

      const timeLabel = document.createElement('span');
      timeLabel.style.cssText = 'font-size:0.72em; color:#94a3b8; margin-left:4px;';
      bubble.appendChild(timeLabel);

      progressHandle = setInterval(() => {
        const elapsed = Date.now() - startedAt;
        const pct     = Math.min((elapsed / configuredTimeout) * 100, 99);
        bar.style.width = pct.toFixed(1) + '%';

        const secs    = Math.floor(elapsed / 1000);
        const maxSecs = Math.floor(configuredTimeout / 1000);
        timeLabel.textContent = `${secs}s / ${maxSecs}s`;

        if (pct > 80)      bar.style.background = '#ef4444';
        else if (pct > 60) bar.style.background = '#f59e0b';
        else               bar.style.background = '#3b82f6';
      }, 1000);
    }
  });

  return progressHandle;
}

// ── Bloque de reintento ───────────────────────────────────────────────────────

/**
 * Inyecta el bloque de reintento con mensaje amigable + traza técnica colapsable.
 *
 * @param {string}      reason           - 'timeout' | 'connection_drop' | 'network' | 'cancelled' | ...
 * @param {object}      trace            - Traza de diagnóstico
 * @param {number|null} elapsed          - Tiempo transcurrido en ms
 * @param {object}      extra            - Datos adicionales (status, error)
 * @param {number}      configuredTimeout - Timeout configurado en ms
 * @param {number}      attemptCount     - Número de intento actual
 * @param {Function|null} onRetry        - Callback al pulsar Reintentar
 * @param {object|null} lastPayload      - Payload del último mensaje (para reintentar)
 */
export function injectRetryBlock(reason, trace, elapsed, extra, configuredTimeout, attemptCount, onRetry, lastPayload) {
  const messagesArea = document.getElementById('chat-messages');
  if (!messagesArea) return;

  const existing = document.getElementById(RETRY_CONTAINER_ID);
  if (existing) existing.remove();

  const container = document.createElement('div');
  container.id = RETRY_CONTAINER_ID;
  container.style.cssText = STYLES.RETRY_CONTAINER;

  // ── Mensaje principal ─────────────────────────────────────────────────────
  const userMsg = USER_MESSAGES[reason] || USER_MESSAGES.default;
  const mainMsg = document.createElement('div');
  mainMsg.style.fontWeight = '600';
  mainMsg.textContent = userMsg;
  container.appendChild(mainMsg);

  // ── Sugerencia contextual ─────────────────────────────────────────────────
  const hint = _buildHint(reason, trace, elapsed, configuredTimeout, container);
  container.appendChild(hint);

  // ── Traza técnica colapsable ──────────────────────────────────────────────
  _appendTraceBlock(container, trace, elapsed, extra, configuredTimeout, attemptCount);

  // ── Botón Reintentar ──────────────────────────────────────────────────────
  if (onRetry && lastPayload) {
    _appendRetryButton(container, onRetry, lastPayload, attemptCount);
  }

  messagesArea.appendChild(container);
  messagesArea.scrollTop = messagesArea.scrollHeight;
}

// ── Helpers privados ──────────────────────────────────────────────────────────

function _buildHint(reason, trace, elapsed, configuredTimeout, container) {
  const hint = document.createElement('div');
  hint.style.cssText = 'margin-top:4px; font-size:0.9em; color:#3b82f6;';

  if (reason === 'timeout') {
    const timeoutSecs = Math.round(configuredTimeout / 1000);
    if (trace.isDeep) {
      hint.textContent = (
        `El análisis profundo tardó más de ${timeoutSecs}s. ` +
        `El modelo ${trace.preferredModel || trace.modelId} ejecuta múltiples fases IA ` +
        `(clasificación + SQL + interpretación + análisis). ` +
        `Puedes reintentar — el modelo ya está caliente y será más rápido.`
      );
    } else {
      hint.textContent = (
        `El modelo ${trace.preferredModel || trace.modelId} tardó más de ${timeoutSecs}s. ` +
        `Si acaba de arrancar, espera unos segundos y reintenta.`
      );
    }
  } else if (reason === 'connection_drop') {
    const elapsedSecs = elapsed != null ? Math.round(elapsed / 1000) : '?';
    hint.style.color = '#d97706';
    hint.textContent = (
      `La conexión HTTP se interrumpió tras ${elapsedSecs}s, pero el servidor backend ` +
      `sigue activo y el modelo IA puede haber completado el procesamiento. ` +
      `Pulsa "Reintentar" — la respuesta llegará más rápido (modelo ya caliente).`
    );
    container.style.background   = '#fffbeb';
    container.style.borderColor  = '#fcd34d';
    container.style.color        = '#92400e';
  } else if (reason === 'cancelled') {
    hint.textContent = 'Puedes reintentar cuando el modelo esté disponible.';
  } else if (reason === 'network') {
    hint.textContent = 'Verifica que el servidor backend está activo y vuelve a intentarlo.';
  } else {
    hint.textContent = RECOVERY_MESSAGES.RETRY_HINT;
  }

  return hint;
}

function _appendTraceBlock(container, trace, elapsed, extra, configuredTimeout, attemptCount) {
  const traceLines = [
    `Intento: #${attemptCount}`,
    `Modelo IA: ${trace.modelId}`,
    `Motor LAN: ${trace.preferredModel || '(automático)'}`,
    `Modo BD: ${trace.dbMode}`,
    `Análisis profundo: ${trace.deepAnalysis}`,
    `Tiempo: ${elapsed != null ? elapsed + 'ms' : 'desconocido'}`,
    `Timeout configurado: ${configuredTimeout}ms`,
    `Sesión: ${trace.sessionId}`,
    extra.status ? `HTTP: ${extra.status}` : null,
    extra.error  ? `Error: ${String(extra.error).slice(0, 200)}` : null,
  ].filter(Boolean).join('\n');

  const toggleBtn = document.createElement('button');
  toggleBtn.style.cssText = STYLES.TRACE_TOGGLE;
  toggleBtn.textContent = '▶ Ver detalles técnicos';

  const traceBlock = document.createElement('pre');
  traceBlock.style.cssText = STYLES.TRACE_BLOCK;
  traceBlock.style.display = 'none';
  traceBlock.textContent = traceLines;

  toggleBtn.addEventListener('click', () => {
    const isHidden = traceBlock.style.display === 'none';
    traceBlock.style.display = isHidden ? 'block' : 'none';
    toggleBtn.textContent = isHidden ? '▼ Ocultar detalles técnicos' : '▶ Ver detalles técnicos';
  });

  container.appendChild(toggleBtn);
  container.appendChild(traceBlock);
}

function _appendRetryButton(container, onRetry, lastPayload, attemptCount) {
  const retryBtn = document.createElement('button');
  retryBtn.style.cssText = STYLES.RETRY_BTN;
  retryBtn.title = RECOVERY_MESSAGES.BTN_RETRY_TITLE;
  retryBtn.textContent = RECOVERY_MESSAGES.BTN_RETRY;

  retryBtn.addEventListener('click', () => {
    container.remove();
    console.log(`[ChatRecovery] Reintentando (intento #${attemptCount + 1})`);
    onRetry(lastPayload);
  });
  retryBtn.addEventListener('mouseenter', () => { retryBtn.style.background = '#1d4ed8'; });
  retryBtn.addEventListener('mouseleave', () => { retryBtn.style.background = '#2563eb'; });

  container.appendChild(retryBtn);
}
