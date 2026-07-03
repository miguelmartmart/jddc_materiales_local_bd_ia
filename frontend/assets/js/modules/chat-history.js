/**
 * chat-history.js — Gestión del historial de sesiones de chat
 *
 * Responsabilidad única: cargar, renderizar y gestionar el historial de sesiones.
 *
 * Principios DEVIA:
 * - Fichero < 500 líneas, una responsabilidad (SRP)
 * - Sin estado global — recibe callbacks para notificar al módulo padre
 * - Importa constantes de constants.js
 *
 * Exporta:
 *   - ChatHistoryManager (clase)
 */

import { API, CHAT_ROLES } from '../core/constants.js';

export class ChatHistoryManager {
  /**
   * @param {object} opts
   * @param {Function} opts.onLoadSession   - Callback(sessionId) al seleccionar sesión
   * @param {string}   opts.chatApiBase     - Base URL del API de chat (/api/chat)
   */
  constructor({ onLoadSession, chatApiBase }) {
    this._onLoadSession = onLoadSession;
    this._apiBase       = chatApiBase;
  }

  // ── Historial lateral (sidebar) ───────────────────────────────────────────

  /**
   * Carga y renderiza la lista de sesiones en el sidebar.
   * @param {string|null} currentSessionId - ID de la sesión activa (para highlight)
   */
  async loadHistory(currentSessionId) {
    const listContainer = document.getElementById('history-list');
    if (!listContainer) return;

    try {
      const response = await fetch(`${this._apiBase}/history`);
      const sessions = await response.json();

      if (sessions.length === 0) {
        listContainer.innerHTML =
          '<div style="text-align:center;color:#94a3b8;font-size:0.9em;margin-top:20px;">No hay historial</div>';
        return;
      }

      listContainer.innerHTML = sessions
        .map((session) => {
          const isActive = session.id === currentSessionId;
          return `<div class="history-item" data-id="${session.id}"
            style="padding:10px;cursor:pointer;border-radius:6px;margin-bottom:5px;
            color:#334155;font-size:0.9em;white-space:nowrap;overflow:hidden;
            text-overflow:ellipsis;
            background:${isActive ? '#e0f2fe' : 'transparent'};
            border:1px solid ${isActive ? '#bae6fd' : 'transparent'};">
            ${session.title || 'Nueva conversación'}
            <div style="font-size:0.75em;color:#94a3b8;">
              ${new Date(session.updated_at).toLocaleDateString()}
            </div>
          </div>`;
        })
        .join('');

      listContainer.querySelectorAll('.history-item').forEach((item) => {
        item.addEventListener('click', () => this._onLoadSession(item.dataset.id));
      });
    } catch (error) {
      console.error('[ChatHistory] Error cargando historial:', error);
    }
  }

  /**
   * Carga los mensajes de una sesión y los devuelve.
   * @param {string} sessionId
   * @returns {Promise<{messages: Array, error: string|null}>}
   */
  async fetchSession(sessionId) {
    try {
      const response = await fetch(`${this._apiBase}/history/${sessionId}`);
      const data     = await response.json();
      return { messages: data.messages || [], error: null };
    } catch (error) {
      return { messages: [], error: error.message };
    }
  }

  // ── Historial completo (modal) ────────────────────────────────────────────

  /** Inicializa el botón y modal de historial completo. */
  initFullHistory() {
    const btnHistory = document.getElementById('btn-chat-full-history');
    const modal      = document.getElementById('chat-full-history-modal');

    if (btnHistory && modal) {
      btnHistory.addEventListener('click', () => {
        this._loadFullHistory();
        modal.showModal();
      });
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.close();
      });
    }
  }

  async _loadFullHistory() {
    const container = document.getElementById('full-history-sessions');
    if (!container) return;
    container.innerHTML =
      '<div style="padding:20px;text-align:center;color:#999;">Cargando historial...</div>';

    try {
      const response = await fetch(`${this._apiBase}/history/all`);
      if (response.ok) {
        const data = await response.json();
        this._renderFullHistorySessions(data);
      } else {
        container.innerHTML =
          '<div style="color:red;padding:20px;">Error cargando historial</div>';
      }
    } catch (error) {
      console.error('[ChatHistory] Error cargando historial completo:', error);
    }
  }

  _renderFullHistorySessions(data) {
    const container = document.getElementById('full-history-sessions');
    if (!container) return;
    container.innerHTML = '';

    if (data.length === 0) {
      container.innerHTML =
        '<div style="padding:20px;text-align:center;color:#999;">No hay historial</div>';
      return;
    }

    data.forEach((item, index) => {
      const div  = document.createElement('div');
      const date = new Date(item.session.created_at).toLocaleString();
      div.style.cssText = 'padding:15px;border-bottom:1px solid #eee;cursor:pointer;transition:background 0.2s;';
      div.className = 'history-session-item';
      div.innerHTML = `
        <div style="font-weight:600;font-size:0.9em;margin-bottom:5px;color:#1e293b;
          overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">
          ${item.session.title || 'Sin título'}
        </div>
        <div style="font-size:0.8em;color:#64748b;">${date}</div>
        <div style="font-size:0.75em;color:#94a3b8;margin-top:3px;">
          ${item.messages.length} mensajes
        </div>`;

      div.addEventListener('click', () => {
        document.querySelectorAll('.history-session-item')
          .forEach((el) => (el.style.background = 'white'));
        div.style.background = '#e0f2fe';
        this._renderFullHistoryMessages(item);
      });

      container.appendChild(div);
      if (index === 0) div.click();
    });
  }

  _renderFullHistoryMessages(item) {
    const container = document.getElementById('full-history-messages');
    if (!container) return;
    container.innerHTML = '';

    const header = document.createElement('div');
    header.style.cssText = 'margin-bottom:20px;padding-bottom:10px;border-bottom:1px solid #e2e8f0;';
    header.innerHTML = `
      <h4 style="margin:0;">${item.session.title}</h4>
      <div style="font-size:0.85em;color:#64748b;">
        Modelo: ${item.session.model_id} | ID: ${item.session.id}
      </div>`;
    container.appendChild(header);

    item.messages.forEach((msg) => {
      const isUser = msg.role === 'user';
      const msgDiv = document.createElement('div');
      msgDiv.style.cssText = [
        'margin-bottom:15px', 'padding:12px 15px', 'border-radius:8px',
        'max-width:85%', `margin-left:${isUser ? 'auto' : '0'}`,
        `margin-right:${isUser ? '0' : 'auto'}`,
        `background:${isUser ? '#dbeafe' : 'white'}`,
        `border:${isUser ? 'none' : '1px solid #e2e8f0'}`,
        'box-shadow:0 1px 2px rgba(0,0,0,0.05)',
      ].join(';');

      let content = msg.content
        .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
      if (content.includes('```')) {
        content = content.replace(
          /```([\s\S]*?)```/g,
          '<pre style="background:#1e293b;color:#fff;padding:10px;border-radius:4px;overflow-x:auto;">$1</pre>',
        );
      }

      msgDiv.innerHTML = `
        <div style="font-weight:600;font-size:0.8em;margin-bottom:5px;
          color:${isUser ? '#1e40af' : '#059669'};">
          ${isUser ? '👤 Usuario' : '🤖 IA'}
        </div>
        <div style="font-size:0.95em;line-height:1.5;color:#334155;">${content}</div>
        <div style="font-size:0.75em;color:#94a3b8;text-align:right;margin-top:5px;">
          ${new Date(msg.created_at).toLocaleTimeString()}
        </div>`;
      container.appendChild(msgDiv);
    });
  }
}
