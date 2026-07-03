/**
 * chat-markdown.js — Renderizado Markdown para el chat IA
 *
 * Responsabilidad única: convertir texto Markdown/HTML de la IA a HTML seguro.
 *
 * Principios DEVIA:
 * - Fichero < 500 líneas, una responsabilidad (SRP)
 * - Funciones puras — sin estado, sin efectos secundarios
 * - Configura marked UNA sola vez (patrón lazy singleton)
 * - Oculta bloques SQL/técnicos al usuario no técnico
 *
 * Exporta:
 *   - renderMarkdown(text) → string HTML
 */

// ── Configuración de marked (lazy, una sola vez) ──────────────────────────────
let _markedConfigured = false;

function _configureMarked() {
  if (_markedConfigured || typeof marked === 'undefined') return;
  _markedConfigured = true;

  const renderer = {
    // Tablas GFM → envueltas en .chat-table-wrapper para scroll horizontal
    table(token) {
      const headerCells = (token.header || [])
        .map((cell) => `<th>${cell.text || cell}</th>`)
        .join('');
      const bodyRows = (token.rows || [])
        .map((row) =>
          `<tr>${row.map((cell) => `<td>${cell.text || cell}</td>`).join('')}</tr>`,
        )
        .join('');
      return (
        `<div class="chat-table-wrapper">` +
        `<table class="chat-table">` +
        `<thead><tr>${headerCells}</tr></thead>` +
        `<tbody>${bodyRows}</tbody>` +
        `</table></div>`
      );
    },
    // Bloques de código técnico → ocultar al usuario no técnico
    code(token) {
      const lang = (token.lang || '').toLowerCase();
      const HIDDEN_LANGS = ['sql', 'python', 'bash', 'sh', 'javascript', 'js'];
      if (HIDDEN_LANGS.includes(lang)) return '';
      const escaped = (token.text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      return `<pre class="chat-code-block"><code>${escaped}</code></pre>`;
    },
  };

  marked.use({ gfm: true, breaks: true, renderer });
}

// ── Reparación de respuestas truncadas ────────────────────────────────────────

/**
 * Repara respuestas truncadas por el modelo:
 * - Elimina bloques de código SQL/técnico
 * - Cierra bloques <details> abiertos
 *
 * @param {string} text
 * @returns {string}
 */
function _repairTruncatedResponse(text) {
  // Eliminar bloques de código técnico
  const HIDDEN_LANGS = ['sql', 'SQL', 'python', 'bash', 'sh', 'javascript', 'js'];
  const hiddenPattern = new RegExp(
    '```(?:' + HIDDEN_LANGS.join('|') + ')[^`]*```',
    'gs',
  );
  text = text.replace(hiddenPattern, '');

  // Eliminar otros bloques técnicos
  text = text.replace(/```[^`]*```/gs, (match) => {
    const lang = (match.match(/```(\w*)/)?.[1] || '').toLowerCase();
    return HIDDEN_LANGS.map((l) => l.toLowerCase()).includes(lang) ? '' : match;
  });

  // Cerrar <details> abiertos (respuesta cortada)
  const openCount  = (text.match(/<details[^>]*>/gi) || []).length;
  const closeCount = (text.match(/<\/details>/gi) || []).length;
  const missing    = openCount - closeCount;
  if (missing > 0) {
    text += '\n\n*(Información adicional disponible — consulta al asistente para más detalles)*\n\n';
    for (let i = 0; i < missing; i++) text += '\n</details>';
  }

  return text;
}

// ── API pública ───────────────────────────────────────────────────────────────

/**
 * Renderiza texto Markdown/HTML de la IA a HTML seguro para el chat.
 *
 * @param {string} text - Texto Markdown/HTML de la IA
 * @returns {string}    - HTML renderizado
 */
export function renderMarkdown(text) {
  if (!text || typeof text !== 'string') return '';

  _configureMarked();
  text = _repairTruncatedResponse(text);

  let html;
  try {
    html = marked.parse(text);
  } catch {
    html = text.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
  }

  // Añadir clase CSS al <details> generado por la IA
  html = html.replace(/<details>/gi, '<details class="chat-justification">');

  return html;
}
