/**
 * chat-recovery.js — Gestión de estado de peticiones IA
 *
 * Responsabilidad única: gestionar el ciclo de vida de una petición IA:
 *   - AbortController + timeout adaptativo
 *   - Heartbeat (ping periódico al backend)
 *   - Detección de connection_drop vs error de red real
 *   - Trazabilidad de intentos
 *
 * Principios DEVIA:
 * - Fichero < 500 líneas, una responsabilidad (SRP)
 * - Sin DOM propio — delega en chat-recovery-ui.js
 * - Constantes centralizadas en constants.js
 * - Patrón Singleton exportado como `chatRecovery`
 *
 * Flujo:
 *   ChatModule.sendMessage()
 *     → chatRecovery.startRequest(payload, thinkingId, onRetry)
 *     → fetch con AbortController + timeout adaptativo
 *     → éxito: chatRecovery.endRequest()
 *     → error: await chatRecovery.failRequest(reason, extra)
 *
 * DETECCIÓN DE ERRORES:
 *   1. AbortError + wasTimeoutAbort=true  → timeout
 *   2. AbortError + wasTimeoutAbort=false → cancelled / network_down
 *   3. TypeError + elapsed ≥ 90% timeout  → timeout enmascarado
 *   4. TypeError + elapsed ≥ 30s + backend vivo → connection_drop
 *   5. TypeError + backend caído           → network
 */

import { TIMEOUTS, RECOVERY_MESSAGES } from '../core/constants.js';
import {
  CANCEL_BTN_ID,
  RETRY_CONTAINER_ID,
  PROGRESS_BAR_ID,
  injectCancelButton,
  injectRetryBlock,
  updateStatusLabel,
} from './chat-recovery-ui.js';

export class ChatRecovery {
  constructor() {
    /** @type {AbortController|null} */
    this._controller = null;
    /** @type {number|null} — handle del setTimeout de timeout */
    this._timeoutHandle = null;
    /** @type {number|null} — handle del setInterval de la barra de progreso */
    this._progressHandle = null;
    /** @type {number|null} — handle del setInterval del heartbeat */
    this._heartbeatHandle = null;
    /** @type {boolean} */
    this._isWaiting = false;
    /** @type {object|null} */
    this._lastPayload = null;
    /** @type {Function|null} */
    this._onRetry = null;
    /** @type {string|null} */
    this._thinkingId = null;
    /** @type {number} */
    this._attemptCount = 0;
    /** @type {number|null} */
    this._startedAt = null;
    /** @type {boolean} */
    this._abortedByTimeout = false;
    /** @type {number} */
    this._configuredTimeout = TIMEOUTS.AI_REQUEST;
    /** @type {number} */
    this._pingFailCount = 0;
    /** @type {boolean} */
    this._lastPingOk = true;
  }

  // ── API pública ─────────────────────────────────────────────────────────────

  /**
   * Inicia el seguimiento de una petición IA.
   * Timeout adaptativo: deep_analysis → AI_REQUEST_DEEP, normal → AI_REQUEST.
   *
   * @param {object}   payload    - Cuerpo JSON que se enviará al backend
   * @param {string}   thinkingId - ID del elemento DOM del bubble "Pensando..."
   * @param {Function} onRetry    - Callback(payload) para el botón Reintentar
   * @returns {AbortController}
   */
  startRequest(payload, thinkingId, onRetry) {
    this._cancelPending('Nueva petición iniciada antes de que terminara la anterior');

    this._controller       = new AbortController();
    this._isWaiting        = true;
    this._lastPayload      = payload;
    this._onRetry          = onRetry;
    this._thinkingId       = thinkingId;
    this._startedAt        = Date.now();
    this._abortedByTimeout = false;
    this._pingFailCount    = 0;
    this._lastPingOk       = true;
    this._attemptCount++;

    const isDeep = !!(payload.deep_analysis);
    this._configuredTimeout = isDeep ? TIMEOUTS.AI_REQUEST_DEEP : TIMEOUTS.AI_REQUEST;

    const trace = this._buildTrace(payload);
    console.group(`[ChatRecovery] Intento #${this._attemptCount}`);
    console.log('Modelo IA:', trace.modelId);
    console.log('Motor LAN:', trace.preferredModel || '(automático)');
    console.log('Modo BD:', trace.dbMode);
    console.log('Análisis profundo:', trace.deepAnalysis);
    console.log('Timeout:', this._configuredTimeout + 'ms', isDeep ? '(DEEP)' : '(normal)');
    console.groupEnd();

    this._scheduleTimeout();

    // Delegar DOM al módulo UI
    this._progressHandle = injectCancelButton(
      thinkingId, trace, isDeep,
      this._configuredTimeout, this._startedAt,
      () => this.cancelByUser(),
    );
    this._startHeartbeat(thinkingId);

    return this._controller;
  }

  /** Marca la petición como completada con éxito. */
  endRequest() {
    const elapsed = this._startedAt ? Date.now() - this._startedAt : null;
    console.log(`[ChatRecovery] ✅ Éxito #${this._attemptCount}`, elapsed ? `(${elapsed}ms)` : '');
    this._cleanup();
    const existing = document.getElementById(RETRY_CONTAINER_ID);
    if (existing) existing.remove();
  }

  /**
   * Marca la petición como fallida.
   * ASYNC: hace ping al backend para detectar connection_drop vs error de red real.
   *
   * @param {string} reason - 'timeout' | 'cancelled' | 'network' | 'http_NNN'
   * @param {object} [extra] - { error, status }
   */
  async failRequest(reason, extra = {}) {
    const elapsed = this._startedAt ? Date.now() - this._startedAt : null;
    const trace   = this._lastPayload ? this._buildTrace(this._lastPayload) : {};

    reason = await this._classifyError(reason, elapsed);

    console.group(`[ChatRecovery] ❌ Fallo #${this._attemptCount} — ${reason}`);
    console.warn('Razón:', reason);
    console.warn('Tiempo:', elapsed ? `${elapsed}ms` : 'desconocido');
    console.warn('Timeout configurado:', this._configuredTimeout + 'ms');
    console.warn('Modelo IA:', trace.modelId || '?');
    if (extra.error)  console.error('Error técnico:', extra.error);
    if (extra.status) console.warn('HTTP status:', extra.status);
    console.groupEnd();

    this._cleanup();
    injectRetryBlock(
      reason, trace, elapsed, extra,
      this._configuredTimeout, this._attemptCount,
      this._onRetry, this._lastPayload,
    );
  }

  /** Cancela la petición en curso (botón Cancelar del usuario). */
  cancelByUser() {
    if (!this._isWaiting) return;
    console.log('[ChatRecovery] Cancelado por el usuario');
    this._controller?.abort('cancelled');
  }

  get isWaiting()       { return this._isWaiting; }
  get wasTimeoutAbort() { return this._abortedByTimeout; }
  get lastPayload()     { return this._lastPayload; }

  // ── Clasificación de errores ─────────────────────────────────────────────────

  /**
   * Clasifica el error recibido en la categoría correcta.
   * Hace ping al backend si es necesario para distinguir connection_drop de network.
   *
   * @param {string}      reason  - Razón inicial
   * @param {number|null} elapsed - Tiempo transcurrido en ms
   * @returns {Promise<string>}   - Razón clasificada
   */
  async _classifyError(reason, elapsed) {
    if (reason !== 'network' || elapsed == null) return reason;

    const ratio          = this._configuredTimeout > 0 ? elapsed / this._configuredTimeout : 0;
    const detectionRatio = TIMEOUTS.TIMEOUT_DETECTION_RATIO ?? 0.90;
    const dropThreshold  = TIMEOUTS.CONNECTION_DROP_THRESHOLD ?? 30000;
    const minAiTimeout   = TIMEOUTS.AI_REQUEST ?? 300000;

    // Caso 1: elapsed ≥ 90% del timeout → timeout enmascarado
    if (ratio >= detectionRatio) {
      console.warn(`[ChatRecovery] Timeout enmascarado (ratio=${ratio.toFixed(2)})`);
      this._abortedByTimeout = true;
      return 'timeout';
    }

    // Caso 2: elapsed ≥ 30s → posible connection_drop, verificar con ping
    if (elapsed >= dropThreshold) {
      console.warn(`[ChatRecovery] Error de red tras ${elapsed}ms — verificando backend...`);
      const alive = await this._pingBackend();
      if (alive) {
        console.warn(`[ChatRecovery] 🔄 Connection drop: backend vivo, conexión TCP cortada`);
        return 'connection_drop';
      }
      console.warn(`[ChatRecovery] Backend no responde → error de red real`);
      return 'network';
    }

    // Caso 3: elapsed ≥ 90% del AI_REQUEST mínimo → timeout enmascarado
    if (elapsed >= minAiTimeout * 0.90) {
      console.warn(`[ChatRecovery] Timeout enmascarado por tiempo (${elapsed}ms)`);
      this._abortedByTimeout = true;
      return 'timeout';
    }

    return 'network';
  }

  // ── Timeout automático ───────────────────────────────────────────────────────

  /**
   * Programa el timeout automático.
   * Si el backend responde al ping → extender timeout (IA sigue trabajando).
   * Si el backend no responde → abortar.
   */
  _scheduleTimeout() {
    if (this._timeoutHandle !== null) {
      clearTimeout(this._timeoutHandle);
      this._timeoutHandle = null;
    }
    this._timeoutHandle = setTimeout(async () => {
      if (!this._isWaiting) return;

      const pingOk = await this._pingBackend();
      if (!this._isWaiting) return;

      if (pingOk) {
        const elapsed = this._startedAt ? Math.round((Date.now() - this._startedAt) / 1000) : '?';
        console.warn(`[ChatRecovery] ⏳ Timeout pero backend vivo (${elapsed}s) — extendiendo`);
        updateStatusLabel(this._thinkingId, `⏳ IA procesando... ${elapsed}s (extendiendo espera)`);
        this._scheduleTimeout();
      } else {
        console.warn(`[ChatRecovery] ❌ Timeout + ping fallido → abortando`);
        this._abortedByTimeout = true;
        this._controller?.abort('timeout');
      }
    }, this._configuredTimeout);
  }

  // ── Heartbeat ────────────────────────────────────────────────────────────────

  /**
   * Ping periódico al backend durante la espera.
   * 3 pings fallidos consecutivos → abortar con error de red.
   */
  _startHeartbeat(thinkingId) {
    this._stopHeartbeat();
    this._pingFailCount = 0;
    this._lastPingOk    = true;

    const interval = TIMEOUTS.HEARTBEAT_INTERVAL ?? 30000;

    this._heartbeatHandle = setInterval(async () => {
      if (!this._isWaiting) { this._stopHeartbeat(); return; }

      const ok      = await this._pingBackend();
      const elapsed = this._startedAt ? Math.round((Date.now() - this._startedAt) / 1000) : '?';

      if (ok) {
        this._pingFailCount = 0;
        this._lastPingOk    = true;
        console.log(`[ChatRecovery] 💓 Heartbeat OK (${elapsed}s)`);
        updateStatusLabel(thinkingId, `💓 Backend activo · IA procesando... ${elapsed}s`);
      } else {
        this._pingFailCount++;
        this._lastPingOk = false;
        console.warn(`[ChatRecovery] ⚠️ Heartbeat FAIL #${this._pingFailCount} (${elapsed}s)`);
        updateStatusLabel(thinkingId, `⚠️ Sin respuesta del backend (${this._pingFailCount}/3)...`);

        if (this._pingFailCount >= 3) {
          console.error(`[ChatRecovery] ❌ 3 pings fallidos → backend caído. Abortando.`);
          this._stopHeartbeat();
          if (this._isWaiting) {
            this._abortedByTimeout = false;
            this._controller?.abort('network_down');
          }
        }
      }
    }, interval);
  }

  _stopHeartbeat() {
    if (this._heartbeatHandle !== null) {
      clearInterval(this._heartbeatHandle);
      this._heartbeatHandle = null;
    }
  }

  // ── Ping al backend ──────────────────────────────────────────────────────────

  /**
   * Ping rápido al endpoint /api/chat/ping.
   * @returns {Promise<boolean>}
   */
  async _pingBackend() {
    try {
      const timeout = TIMEOUTS.HEARTBEAT_PING_TIMEOUT ?? 5000;
      const ctrl    = new AbortController();
      const timer   = setTimeout(() => ctrl.abort(), timeout);
      const r       = await fetch('/api/chat/ping', { signal: ctrl.signal, cache: 'no-store' });
      clearTimeout(timer);
      return r.ok;
    } catch {
      return false;
    }
  }

  // ── Limpieza ─────────────────────────────────────────────────────────────────

  _cancelPending(reason) {
    if (!this._isWaiting) return;
    console.warn('[ChatRecovery] _cancelPending:', reason);
    this._controller?.abort('internal');
    this._cleanup();
  }

  _cleanup() {
    this._isWaiting = false;
    if (this._timeoutHandle !== null) {
      clearTimeout(this._timeoutHandle);
      this._timeoutHandle = null;
    }
    if (this._progressHandle !== null) {
      clearInterval(this._progressHandle);
      this._progressHandle = null;
    }
    this._stopHeartbeat();
    this._controller = null;

    // Limpiar elementos DOM del botón Cancelar y barra de progreso
    document.getElementById(CANCEL_BTN_ID)?.remove();
    const progressBar = document.getElementById(PROGRESS_BAR_ID);
    if (progressBar) progressBar.parentElement?.remove();
  }

  // ── Traza de diagnóstico ─────────────────────────────────────────────────────

  /**
   * Extrae información de diagnóstico del payload.
   * @param {object} payload
   * @returns {object}
   */
  _buildTrace(payload) {
    const hasRealDb = !!(payload.db_params && !payload.no_db);
    let dbMode;
    if (payload.no_db)              dbMode = 'Sin BD (conversacional)';
    else if (payload.simulator_active) dbMode = 'BD simulada (SQLite)';
    else if (hasRealDb)             dbMode = 'BD real (Firebird)';
    else                            dbMode = 'BD simulada (SQLite)';

    return {
      modelId:        payload.model_id           || '?',
      preferredModel: payload.preferred_model_id || null,
      dbMode,
      deepAnalysis:   payload.deep_analysis ? 'Sí' : 'No',
      sessionId:      payload.session_id    || 'nueva sesión',
      hasImages:      (payload.images?.length || 0) > 0,
      isDeep:         !!(payload.deep_analysis),
    };
  }
}

// Singleton — una sola instancia para todo el módulo de chat
export const chatRecovery = new ChatRecovery();
