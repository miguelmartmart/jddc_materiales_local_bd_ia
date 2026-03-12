/**
 * siuo_constants.js — Constantes, estado y utilidades del módulo SIUO.
 *
 * RESPONSABILIDAD:
 *   Fuente única de verdad para constantes, estado compartido y helpers
 *   reutilizables del módulo SIUO. Importado por siuo.js y siuo_render.js.
 *
 * PATRÓN: Módulo de constantes — sin lógica de negocio ni DOM.
 */

// ─── Constantes de API ────────────────────────────────────────────────────────

export const SIUO_API = "/api/siuo";
export const SIUO_POLL_MS = 3000; // ms entre actualizaciones de stats en idle
export const SIUO_MAX_TOKENS_DEFAULT = 2000;

// ─── Preguntas del banco de pruebas ──────────────────────────────────────────
// Fuente única de verdad: añadir/quitar preguntas aquí.

export const SIUO_TEST_BANK = [
  {
    label: "📦 Artículos y Stock",
    tests: [
      {
        text: "8 artículos más vendidos",
        q: "dime los 8 artículos con más ventas",
      },
      { text: "Stock negativo", q: "artículos con stock negativo" },
      { text: "5 más caros", q: "los 5 artículos más caros" },
      { text: "Sin stock", q: "artículos sin stock" },
      { text: "Total artículos", q: "cuántos artículos hay en total" },
    ],
  },
  {
    label: "🧾 Facturas y Documentos",
    tests: [
      { text: "Facturas este mes", q: "facturas del mes actual" },
      { text: "Total facturado año", q: "total facturado este año" },
      { text: "Últimas 10 facturas", q: "últimas 10 facturas" },
      { text: "Presupuestos pendientes", q: "presupuestos pendientes" },
      { text: "Albaranes mes pasado", q: "albaranes del mes pasado" },
    ],
  },
  {
    label: "👥 Clientes y Agentes",
    tests: [
      { text: "Clientes top año", q: "clientes con más compras este año" },
      { text: "Ventas por agente", q: "ventas por agente este mes" },
      { text: "Total clientes", q: "cuántos clientes hay" },
      { text: "Clientes inactivos", q: "clientes sin facturas este año" },
    ],
  },
  {
    label: "🔧 SAT y Reparaciones",
    tests: [
      { text: "OT abiertas", q: "órdenes de trabajo abiertas" },
      { text: "Reparaciones mes", q: "reparaciones del mes actual" },
      { text: "Equipos más reparados", q: "equipos más reparados" },
    ],
  },
  {
    label: "📊 Estadísticas y Análisis",
    tests: [
      { text: "Ventas por mes", q: "ventas por mes este año" },
      {
        text: "Familias top ventas",
        q: "familias de artículos con más ventas",
      },
      {
        text: "Comparativa meses",
        q: "comparativa ventas este mes vs mes pasado",
      },
      { text: "Proveedores top", q: "proveedores con más compras" },
    ],
  },
];

// ─── Estado compartido del módulo ─────────────────────────────────────────────

export const siuoState = {
  analyzing: false, // true mientras hay SSE activo
  eventSource: null, // EventSource activo
  logLines: [], // Líneas del log de progreso
  stats: null, // Últimas estadísticas cargadas
  pollTimer: null, // Timer de polling de stats
  inited: false, // true tras primera inicialización
};

// ─── Utilidades puras (sin DOM) ───────────────────────────────────────────────

/** Escapa HTML para evitar XSS. */
export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Hora actual formateada HH:MM:SS. */
export function timeNow() {
  return new Date().toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Formatea una fecha ISO a locale español. */
export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("es-ES");
  } catch (_) {
    return iso;
  }
}

/** Fetch con manejo de errores HTTP. */
export async function siuoFetch(url, options = {}) {
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

/** Log de trazabilidad en consola. */
export function siuoLog(step, emisor, receptor, msg) {
  console.log(`[SIUO][${step}] ${emisor} → ${receptor}: ${msg}`);
}

/**
 * Convierte Markdown + bloques <details> a HTML renderizable.
 * Extrae los <details> antes de escapar para que se rendericen como HTML.
 */
export function markdownToHtml(text) {
  if (!text) return "";

  const detailsBlocks = [];
  const PH = "%%DETAILS_BLOCK_%%";
  let processed = text.replace(/<details[\s\S]*?<\/details>/gi, (match) => {
    const withClass = match.replace(
      /<details/i,
      '<details class="chat-justification"',
    );
    detailsBlocks.push(withClass);
    return PH + (detailsBlocks.length - 1) + "%%";
  });

  let html = escapeHtml(processed);
  html = html.replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*\n]+?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/^[-*]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");
  html = html.replace(/\n\n+/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");
  html = `<p>${html}</p>`;

  html = html.replace(
    /%%DETAILS_BLOCK_(\d+)%%/g,
    (_, idx) => `</p>${detailsBlocks[parseInt(idx)]}<p>`,
  );
  html = html.replace(/<p>\s*<\/p>/g, "");
  return html;
}
