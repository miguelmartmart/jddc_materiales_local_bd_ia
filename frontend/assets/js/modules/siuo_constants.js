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

/**
 * Consultas avanzadas multi-tabla para el panel de índices SIUO.
 * Cada consulta cruza 2+ tablas y prueba JOINs, agregaciones y filtros complejos.
 * Organizadas por tipo de análisis para máxima utilidad en diagnóstico.
 */
export const SIUO_ADVANCED_BANK = [
  {
    label: "🔗 JOIN Artículos + Ventas",
    icon: "🔗",
    tests: [
      {
        text: "Top 10 artículos vendidos con precio",
        q: "los 10 artículos más vendidos con su precio actual y total de unidades vendidas",
        desc: "ARTICULO JOIN DOCLIN — agrupa por artículo, suma cantidades",
      },
      {
        text: "Artículos vendidos pero sin stock",
        q: "artículos que se han vendido este año pero tienen stock negativo o cero",
        desc: "ARTICULO JOIN DOCLIN JOIN STOCKARTICULO — detecta roturas de stock",
      },
      {
        text: "Artículos nunca vendidos",
        q: "artículos que nunca han sido vendidos (no aparecen en ninguna factura)",
        desc: "ARTICULO LEFT JOIN DOCLIN — detecta artículos muertos",
      },
      {
        text: "Margen por familia",
        q: "margen medio por familia de artículos (precio venta vs precio coste)",
        desc: "ARTICULO GROUP BY FAMILIA — análisis de rentabilidad",
      },
    ],
  },
  {
    label: "🧾 JOIN Facturas + Clientes",
    icon: "🧾",
    tests: [
      {
        text: "Facturación por cliente este año",
        q: "total facturado por cada cliente este año ordenado de mayor a menor",
        desc: "DOCCAB JOIN CLIENTE WHERE TIPO=13 — ranking de clientes",
      },
      {
        text: "Clientes con facturas pendientes de cobro",
        q: "clientes con facturas emitidas pero no cobradas (estado pendiente)",
        desc: "DOCCAB JOIN CLIENTE WHERE TIPO=13 AND ESTADO=pendiente",
      },
      {
        text: "Ticket medio por cliente",
        q: "ticket medio de factura por cliente en los últimos 6 meses",
        desc: "DOCCAB JOIN CLIENTE — AVG(TOTAL) GROUP BY CLIENTE",
      },
      {
        text: "Clientes con más de 5 facturas este mes",
        q: "clientes que tienen más de 5 facturas emitidas este mes",
        desc: "DOCCAB JOIN CLIENTE HAVING COUNT > 5",
      },
    ],
  },
  {
    label: "📦 JOIN Albaranes + Artículos",
    icon: "📦",
    tests: [
      {
        text: "Artículos más albaranados este mes",
        q: "artículos con más unidades en albaranes de este mes",
        desc: "DOCCAB JOIN DOCLIN JOIN ARTICULO WHERE TIPO=11",
      },
      {
        text: "Albaranes sin facturar",
        q: "albaranes del mes pasado que todavía no tienen factura asociada",
        desc: "DOCCAB WHERE TIPO=11 LEFT JOIN facturas — detecta pendientes de facturar",
      },
      {
        text: "Valor total albaranado por cliente",
        q: "valor total de albaranes por cliente en el último trimestre",
        desc: "DOCCAB JOIN DOCLIN JOIN CLIENTE WHERE TIPO=11",
      },
    ],
  },
  {
    label: "🔧 JOIN SAT + Artículos + Clientes",
    icon: "🔧",
    tests: [
      {
        text: "Piezas más usadas en SAT",
        q: "artículos más utilizados en órdenes de trabajo SAT este año",
        desc: "DOCCAB JOIN DOCLIN JOIN ARTICULO WHERE TIPO=2",
      },
      {
        text: "Clientes con más SATs",
        q: "clientes con más órdenes de trabajo abiertas o cerradas este año",
        desc: "DOCCAB JOIN CLIENTE WHERE TIPO=2 GROUP BY CLIENTE",
      },
      {
        text: "Coste medio de reparación por equipo",
        q: "coste medio de las órdenes de trabajo por tipo de equipo o familia",
        desc: "DOCCAB JOIN DOCLIN JOIN ARTICULO WHERE TIPO=2 — AVG(TOTAL)",
      },
      {
        text: "SATs abiertos más de 30 días",
        q: "órdenes de trabajo abiertas hace más de 30 días sin cerrar",
        desc: "DOCCAB WHERE TIPO=2 AND ESTADO=abierto AND FECHA < hoy-30",
      },
    ],
  },
  {
    label: "📊 Análisis Cruzado Multi-tabla",
    icon: "📊",
    tests: [
      {
        text: "Rentabilidad por agente",
        q: "total facturado por agente este año con número de facturas y ticket medio",
        desc: "DOCCAB JOIN AGENTE GROUP BY AGENTE — análisis de rendimiento",
      },
      {
        text: "Evolución ventas por familia mensual",
        q: "ventas mensuales por familia de artículos en los últimos 12 meses",
        desc: "DOCCAB JOIN DOCLIN JOIN ARTICULO GROUP BY FAMILIA, MES",
      },
      {
        text: "Stock vs ventas últimos 3 meses",
        q: "comparativa de stock actual vs unidades vendidas en los últimos 3 meses por artículo",
        desc: "STOCKARTICULO JOIN DOCLIN JOIN ARTICULO — detecta sobrestock/rotura",
      },
      {
        text: "Presupuestos convertidos en factura",
        q: "presupuestos del último trimestre que se convirtieron en factura con su importe",
        desc: "DOCCAB WHERE TIPO=0 JOIN facturas — tasa de conversión",
      },
      {
        text: "Top clientes por familia de producto",
        q: "qué familias de artículos compra más cada uno de los 10 mejores clientes",
        desc: "CLIENTE JOIN DOCCAB JOIN DOCLIN JOIN ARTICULO — análisis de cartera",
      },
    ],
  },
  {
    label: "⚡ Consultas de Diagnóstico",
    icon: "⚡",
    tests: [
      {
        text: "Inconsistencias stock vs movimientos",
        q: "artículos donde el stock actual no cuadra con los movimientos de entrada y salida",
        desc: "STOCKARTICULO vs SUM(DOCLIN) — detecta inconsistencias contables",
      },
      {
        text: "Facturas sin líneas de detalle",
        q: "facturas que no tienen ninguna línea de artículo asociada",
        desc: "DOCCAB LEFT JOIN DOCLIN WHERE DOCLIN.NUMERO IS NULL — datos huérfanos",
      },
      {
        text: "Artículos con precio 0 vendidos",
        q: "artículos que se han vendido con precio 0 o negativo en facturas",
        desc: "DOCLIN JOIN ARTICULO WHERE PRECIO <= 0 — detecta errores de precio",
      },
      {
        text: "Clientes duplicados por nombre",
        q: "clientes con nombre muy similar que podrían estar duplicados",
        desc: "CLIENTE GROUP BY NOMBRE — detecta duplicados",
      },
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
 *
 * Soporta:
 *  - Tablas Markdown (| col | col |) → <table class="md-table">
 *  - Negrita **texto**, cursiva *texto*, código `texto`
 *  - Listas - item, * item
 *  - Bloques <details>...</details> (preservados como HTML)
 *  - Párrafos y saltos de línea
 */
export function markdownToHtml(text) {
  if (!text) return "";

  // ── 0. Si el texto ya es HTML puro (empieza con <), devolverlo tal cual ──
  // Esto evita doble-procesado cuando el backend ya devuelve HTML renderizado.
  const trimmed = text.trim();
  if (
    trimmed.startsWith("<p>") ||
    trimmed.startsWith("<div>") ||
    trimmed.startsWith("<table>")
  ) {
    return text;
  }

  // ── 1. Extraer bloques HTML que NO deben escaparse ────────────────────────
  // Orden: <details>, <p style=...>, <span style=...>, <strong>, <em> con style
  const htmlBlocks = [];
  const HTML_PH = "%%HTML_BLOCK_";

  // Extraer <details>...</details>
  let processed = text.replace(/<details[\s\S]*?<\/details>/gi, (match) => {
    const withClass = match.replace(
      /<details/i,
      '<details class="chat-justification"',
    );
    htmlBlocks.push(withClass);
    return HTML_PH + (htmlBlocks.length - 1) + "%%";
  });

  // Extraer <span style=...>...</span> (colores inline del backend)
  processed = processed.replace(/<span\s[^>]*>[\s\S]*?<\/span>/gi, (match) => {
    htmlBlocks.push(match);
    return HTML_PH + (htmlBlocks.length - 1) + "%%";
  });

  // Extraer <p style=...>...</p> (advertencias de tablas con pocos registros)
  processed = processed.replace(/<p\s[^>]*>[\s\S]*?<\/p>/gi, (match) => {
    htmlBlocks.push(match);
    return HTML_PH + (htmlBlocks.length - 1) + "%%";
  });

  // Mantener compatibilidad con alias anteriores
  const detailsBlocks = htmlBlocks;
  const PH = HTML_PH;

  // ── 2. Extraer bloques de tabla Markdown ANTES de escapar ─────────────────
  // Una tabla Markdown es un bloque de líneas que empiezan con |
  // Ej:  | Col1 | Col2 |
  //      |------|------|
  //      | val1 | val2 |
  const tablePH = "%%TABLE_BLOCK_";
  const tableBlocks = [];
  processed = processed.replace(/((?:[ \t]*\|.+\|[ \t]*\n?)+)/gm, (match) => {
    const lines = match
      .trim()
      .split("\n")
      .filter((l) => l.trim());
    if (lines.length < 2) return match; // No es tabla real

    // Detectar línea separadora (|---|---|)
    const sepIdx = lines.findIndex((l) => /^\s*\|[\s\-:|]+\|\s*$/.test(l));
    if (sepIdx < 0) return match; // Sin separador → no es tabla

    const headerLine = lines[0];
    const bodyLines = lines.slice(sepIdx + 1);

    const parseCells = (line) =>
      line
        .replace(/^\s*\|/, "")
        .replace(/\|\s*$/, "")
        .split("|")
        .map((c) => c.trim());

    const headers = parseCells(headerLine);
    const rows = bodyLines.map(parseCells);

    const thead = `<thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead>`;
    const tbody = `<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${escapeHtml(c)}</td>`).join("")}</tr>`).join("")}</tbody>`;
    const tableHtml = `<div class="md-table-wrap"><table class="md-table">${thead}${tbody}</table></div>`;

    tableBlocks.push(tableHtml);
    return tablePH + (tableBlocks.length - 1) + "%%";
  });

  // ── 3. Escapar HTML del texto restante ────────────────────────────────────
  let html = escapeHtml(processed);

  // ── 4. Inline Markdown ────────────────────────────────────────────────────
  html = html.replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*\n]+?)\*/g, "<em>$1</em>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // ── 5. Listas ─────────────────────────────────────────────────────────────
  html = html.replace(/^[-*]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>");

  // ── 6. Párrafos ───────────────────────────────────────────────────────────
  html = html.replace(/\n\n+/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");
  html = `<p>${html}</p>`;

  // ── 7. Restaurar tablas ───────────────────────────────────────────────────
  html = html.replace(
    /%%TABLE_BLOCK_(\d+)%%/g,
    (_, idx) => `</p>${tableBlocks[parseInt(idx)]}<p>`,
  );

  // ── 8. Restaurar bloques HTML (details, span, p con style) ───────────────
  html = html.replace(
    /%%HTML_BLOCK_(\d+)%%/g,
    (_, idx) => `</p>${htmlBlocks[parseInt(idx)]}<p>`,
  );

  html = html.replace(/<p>\s*<\/p>/g, "");
  return html;
}
