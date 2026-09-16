/**
 * bd_clone.js v1 — BD Clone: SQL Directo sobre Firebird Real
 * Explorador SQL sin API mPYME — conexion directa a la BD Firebird del proyecto.
 * Patron: igual que api_explorer.js (window.BDCloneModule, onEnter, render)
 */
const API = "/api/bd-clone";

let _state = {
  status: null,
  currentTab: "conexion",
  catalog: null,
  tablaSeleccionada: null,
  tablaDetalle: null,
  historial: [],
  consultas: null,
  sqlActual: "",
  resultadoSQL: null,
  modoEscritura: false,
};

async function _fetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Helpers UI ────────────────────────────────────────────────────────────────

function _badge(color, txt) {
  return `<span style="background:${color};color:white;border-radius:4px;padding:2px 8px;font-size:0.78em;font-weight:600">${txt}</span>`;
}

function _card(content, extra = "") {
  return `<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:12px;${extra}">${content}</div>`;
}

function _tabla_html(filas, columnas) {
  if (!filas || filas.length === 0) {
    return '<div style="color:#94a3b8;font-style:italic;padding:8px">Sin resultados</div>';
  }
  const cols = columnas || Object.keys(filas[0]);
  const ths = cols.map(c => `<th style="padding:5px 10px;text-align:left;font-size:0.8em;color:#64748b;font-weight:600;border-bottom:1px solid #e2e8f0;background:#f8fafc">${c}</th>`).join("");
  const rows = filas.map(row =>
    `<tr>${cols.map(c => `<td style="padding:5px 10px;border-bottom:1px solid #f1f5f9;font-size:0.85em">${row[c] ?? "—"}</td>`).join("")}</tr>`
  ).join("");
  return `<div style="overflow-x:auto;border-radius:8px;border:1px solid #e2e8f0"><table style="width:100%;border-collapse:collapse"><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function _render() {
  const root = document.getElementById("bd-clone-root");
  if (!root) return;
  root.innerHTML = _buildUI();
  _attachEvents();
}

// ── Build UI ──────────────────────────────────────────────────────────────────

function _buildUI() {
  const st = _state.status;
  const TABS = [
    ["conexion",    "🔌 Conexion"],
    ["catalogo",    "📋 Catalogo"],
    ["sql",         "⚡ SQL Libre"],
    ["predefinidas","📚 Consultas"],
    ["historial",   "🕐 Historial"],
  ];
  const tabButtons = TABS.map(([id, lbl]) =>
    `<button onclick="BDCloneModule.setTab('${id}')"
      style="padding:8px 14px;border:none;background:${_state.currentTab===id?'#0369a1':'transparent'};
      color:${_state.currentTab===id?'white':'#64748b'};border-radius:6px 6px 0 0;cursor:pointer;
      font-size:0.88em;font-weight:${_state.currentTab===id?'600':'400'};transition:all 0.15s">${lbl}</button>`
  ).join("");

  const statusBar = st
    ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
        ${st.db_configurada ? _badge("#16a34a","BD configurada") : _badge("#dc2626","BD no configurada")}
        ${st.modo_escritura ? _badge("#ea580c","ESCRITURA ACTIVA") : _badge("#64748b","Solo lectura")}
        <span style="color:#64748b;font-size:0.82em">Host: ${st.db_host} | User: ${st.db_user} | Max rows: ${st.max_rows}</span>
      </div>`
    : `<div style="color:#94a3b8;margin-bottom:12px">Cargando estado...</div>`;

  return `
    <div style="padding:12px;font-family:Inter,sans-serif">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
        <h2 style="margin:0;color:#0f172a;font-size:1.1em">🗃️ BD Clone — SQL Directo Firebird</h2>
        <button onclick="BDCloneModule.onEnter()" style="padding:4px 10px;font-size:0.78em;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;cursor:pointer">↻ Refrescar</button>
      </div>
      ${statusBar}
      <div style="border-bottom:2px solid #e2e8f0;margin-bottom:12px">${tabButtons}</div>
      <div id="bd-clone-tab-content">${_buildTabContent()}</div>
    </div>`;
}

function _buildTabContent() {
  switch (_state.currentTab) {
    case "conexion":    return _tabConexion();
    case "catalogo":    return _tabCatalogo();
    case "sql":         return _tabSQL();
    case "predefinidas":return _tabPredefinidas();
    case "historial":   return _tabHistorial();
    default: return "";
  }
}

// ── Tab Conexion ──────────────────────────────────────────────────────────────

function _tabConexion() {
  const st = _state.status;
  if (!st) return '<div style="color:#94a3b8">Cargando...</div>';
  return `
    ${_card(`
      <h3 style="margin:0 0 12px;font-size:1em">Estado de la conexion</h3>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:4px 8px;color:#64748b;font-size:0.85em;width:160px">BD configurada</td>
            <td>${st.db_configurada ? _badge("#16a34a","SI") : _badge("#dc2626","NO")}</td></tr>
        <tr><td style="padding:4px 8px;color:#64748b;font-size:0.85em">Host</td>
            <td style="font-size:0.85em;font-family:monospace">${st.db_host}</td></tr>
        <tr><td style="padding:4px 8px;color:#64748b;font-size:0.85em">Puerto</td>
            <td style="font-size:0.85em">${st.db_port}</td></tr>
        <tr><td style="padding:4px 8px;color:#64748b;font-size:0.85em">Fichero BD</td>
            <td style="font-size:0.85em;font-family:monospace">...${st.db_name_short}</td></tr>
        <tr><td style="padding:4px 8px;color:#64748b;font-size:0.85em">Usuario</td>
            <td style="font-size:0.85em;font-family:monospace">${st.db_user}</td></tr>
        <tr><td style="padding:4px 8px;color:#64748b;font-size:0.85em">Historial</td>
            <td style="font-size:0.85em">${st.historial_entradas} entradas</td></tr>
      </table>
      <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
        <button onclick="BDCloneModule.doProbarConexion()" class="btn primary">🔌 Probar conexion</button>
        <button onclick="BDCloneModule.doDiagnostico()" class="btn secondary">🔍 Diagnostico</button>
      </div>
      <div id="bd-clone-conexion-result" style="margin-top:12px"></div>
    `)}
    ${_card(`
      <h3 style="margin:0 0 12px;font-size:1em;color:#ea580c">⚠️ Modo Escritura</h3>
      <p style="font-size:0.85em;color:#64748b;margin:0 0 10px">
        Por defecto solo se permiten SELECT. Para INSERT/UPDATE/DELETE activa el modo escritura.<br>
        <strong>Requiere confirmacion exacta.</strong>
      </p>
      ${st.modo_escritura
        ? `<button onclick="BDCloneModule.doDesactivarEscritura()" style="background:#16a34a;color:white;border:none;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:0.85em">✅ Desactivar escritura</button>`
        : `<div style="display:flex;gap:8px;align-items:center">
            <input id="bd-escritura-confirm" placeholder="Escribe: ACTIVAR ESCRITURA BD" style="flex:1;padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:0.85em">
            <button onclick="BDCloneModule.doActivarEscritura()" style="background:#ea580c;color:white;border:none;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:0.85em">Activar escritura</button>
          </div>`
      }
      <div id="bd-clone-escritura-result" style="margin-top:8px"></div>
    `)}`;
}

// ── Tab Catalogo ──────────────────────────────────────────────────────────────

function _tabCatalogo() {
  const cat = _state.catalog;
  const botones = `
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button onclick="BDCloneModule.doCargarCatalogo()" class="btn primary">📋 Cargar catalogo</button>
      <button onclick="BDCloneModule.doCargarCatalogo(true)" class="btn secondary">↻ Forzar refresco</button>
    </div>`;
  if (!cat) return botones + '<div style="color:#94a3b8;font-style:italic">Pulsa "Cargar catalogo" para ver todas las tablas de la BD.</div>';
  if (cat.error) return botones + `<div style="color:#dc2626;background:#fef2f2;padding:10px;border-radius:6px">${cat.error}</div>`;

  const filaSeleccionada = _state.tablaSeleccionada;
  const tablas = (cat.tablas || []);

  // Filtro de busqueda
  const busqueda = document.getElementById("bd-clone-busq-tabla")?.value?.toUpperCase() || "";
  const tablasFiltradas = busqueda ? tablas.filter(t => t.nombre.includes(busqueda)) : tablas;

  const filas = tablasFiltradas.slice(0, 100).map(t => {
    const activa = t.nombre === filaSeleccionada;
    return `<tr style="cursor:pointer;background:${activa?'#dbeafe':'transparent'}"
               onclick="BDCloneModule.doSeleccionarTabla('${t.nombre}')">
              <td style="padding:4px 10px;font-size:0.85em;font-family:monospace">${t.nombre}</td>
              <td style="padding:4px 10px;font-size:0.82em;color:#64748b;text-align:right">${t.n_columnas}</td>
              <td style="padding:4px 10px;font-size:0.82em;color:#64748b;text-align:right">${t.n_registros ?? "—"}</td>
            </tr>`;
  }).join("");

  const detalle = _state.tablaDetalle ? _renderTablaDetalle(_state.tablaDetalle) : "";

  return `
    ${botones}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div>
        ${_card(`
          <div style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
            <input id="bd-clone-busq-tabla" placeholder="Buscar tabla..." oninput="BDCloneModule.setTab('catalogo')"
              style="flex:1;padding:5px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:0.85em"
              value="${busqueda}">
            <span style="font-size:0.82em;color:#64748b">${tablasFiltradas.length}/${tablas.length} tablas</span>
          </div>
          <div style="max-height:400px;overflow-y:auto;border-radius:6px;border:1px solid #e2e8f0">
            <table style="width:100%;border-collapse:collapse">
              <thead style="position:sticky;top:0;background:#f8fafc">
                <tr>
                  <th style="padding:5px 10px;text-align:left;font-size:0.78em;color:#64748b;border-bottom:1px solid #e2e8f0">TABLA</th>
                  <th style="padding:5px 10px;text-align:right;font-size:0.78em;color:#64748b;border-bottom:1px solid #e2e8f0">COLS</th>
                  <th style="padding:5px 10px;text-align:right;font-size:0.78em;color:#64748b;border-bottom:1px solid #e2e8f0">FILAS</th>
                </tr>
              </thead>
              <tbody>${filas}</tbody>
            </table>
          </div>
          ${tablasFiltradas.length > 100 ? '<div style="font-size:0.8em;color:#94a3b8;margin-top:4px">Mostrando 100 primeras. Usa el filtro para buscar mas.</div>' : ''}
          ${cat.desde_cache ? `<div style="font-size:0.78em;color:#94a3b8;margin-top:4px">Cache: ${cat.cache_ts?.slice(0,19)}</div>` : ""}
        `)}
      </div>
      <div>
        ${detalle || '<div style="color:#94a3b8;font-style:italic;padding:20px">Selecciona una tabla para ver su detalle</div>'}
      </div>
    </div>`;
}

function _renderTablaDetalle(d) {
  if (d.error) return _card(`<div style="color:#dc2626">${d.error}</div>`);
  const cols = d.columnas.map(c =>
    `<tr><td style="padding:3px 8px;font-size:0.82em;font-family:monospace">${c.campo}</td>
         <td style="padding:3px 8px;font-size:0.78em;color:#64748b">${c.tipo}</td></tr>`
  ).join("");
  return _card(`
    <h4 style="margin:0 0 8px;font-size:0.95em;font-family:monospace">${d.tabla}</h4>
    <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap">
      ${_badge("#0369a1", `${d.columnas.length} columnas`)}
      ${d.n_registros !== null ? _badge("#16a34a", `${d.n_registros.toLocaleString()} registros`) : ""}
      <span style="font-size:0.8em;color:#94a3b8">${d.ms}ms</span>
    </div>
    <details open>
      <summary style="cursor:pointer;font-size:0.85em;font-weight:600;margin-bottom:4px">Columnas</summary>
      <div style="max-height:200px;overflow-y:auto;border-radius:4px;border:1px solid #e2e8f0">
        <table style="width:100%;border-collapse:collapse">
          <thead><tr>
            <th style="padding:3px 8px;text-align:left;font-size:0.78em;color:#64748b;background:#f8fafc;border-bottom:1px solid #e2e8f0">Campo</th>
            <th style="padding:3px 8px;text-align:left;font-size:0.78em;color:#64748b;background:#f8fafc;border-bottom:1px solid #e2e8f0">Tipo</th>
          </tr></thead>
          <tbody>${cols}</tbody>
        </table>
      </div>
    </details>
    ${d.muestra && d.muestra.length > 0 ? `
    <details style="margin-top:8px">
      <summary style="cursor:pointer;font-size:0.85em;font-weight:600;margin-bottom:4px">Muestra (${d.muestra.length} filas)</summary>
      ${_tabla_html(d.muestra)}
    </details>` : ""}
    <div style="margin-top:8px;display:flex;gap:6px">
      <button onclick="BDCloneModule.doSQLRapido('SELECT FIRST 50 * FROM ${d.tabla}')" style="font-size:0.8em;padding:4px 8px;background:#0369a1;color:white;border:none;border-radius:4px;cursor:pointer">Ver 50 filas en SQL</button>
    </div>
  `);
}

// ── Tab SQL Libre ─────────────────────────────────────────────────────────────

function _tabSQL() {
  const res = _state.resultadoSQL;
  let resultHtml = "";
  if (res) {
    if (res.ok) {
      const nFilas = res.n_filas ?? res.filas_afectadas ?? 0;
      const truncado = res.truncado ? ` <span style="color:#ea580c">(truncado a 500)</span>` : "";
      resultHtml = `<div style="background:#f0fdf4;border-left:3px solid #16a34a;padding:8px 12px;border-radius:4px;margin-bottom:8px">
          ✅ OK — ${res.escritura ? `${nFilas} filas afectadas` : `${nFilas} filas`}${truncado} — ${res.ms}ms</div>
        ${res.filas ? _tabla_html(res.filas, res.columnas) : ""}`;
    } else {
      resultHtml = `<div style="background:#fef2f2;border-left:3px solid #dc2626;padding:8px 12px;border-radius:4px;font-size:0.85em">
          ❌ ${res.bloqueado ? "⛔ ESCRITURA BLOQUEADA — Activa el modo escritura en Conexion" : res.error}</div>`;
    }
  }
  const ejemplos = [
    "SELECT FIRST 10 * FROM PROYECTOS",
    "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO = 3",
    "SELECT FIRST 20 CODIGO, NOMBRE FROM CLIENTE ORDER BY NOMBRE",
    "SELECT FIRST 5 * FROM REPCAB ORDER BY CODIGO DESC",
    "SELECT COUNT(*) AS N FROM RDB$RELATIONS WHERE RDB$SYSTEM_FLAG = 0",
  ].map(sql => `<button onclick="BDCloneModule.doSQLRapido(${JSON.stringify(sql)})"
    style="text-align:left;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;
    padding:5px 10px;cursor:pointer;font-family:monospace;font-size:0.82em;color:#0369a1">${sql}</button>`).join("");

  return `${_card(`
    <h3 style="margin:0 0 10px;font-size:1em">⚡ SQL Libre sobre Firebird Real</h3>
    <p style="font-size:0.82em;color:#64748b;margin:0 0 8px">Solo SELECT por defecto. Limite: 500 filas. FIRST N se inyecta automaticamente.</p>
    <textarea id="bd-clone-sql-input" rows="6" placeholder="SELECT FIRST 10 * FROM PROYECTOS"
      style="width:100%;box-sizing:border-box;font-family:monospace;font-size:0.88em;
             padding:8px;border:1px solid #e2e8f0;border-radius:6px;resize:vertical"
    >${_state.sqlActual}</textarea>
    <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap">
      <button onclick="BDCloneModule.doEjecutarSQL()" class="btn primary" style="font-weight:700">▶ Ejecutar SQL</button>
      <button onclick="BDCloneModule.doClearSQL()" class="btn secondary">✕ Limpiar</button>
    </div>`)}
  ${resultHtml ? _card(resultHtml) : ""}
  ${_card(`<details><summary style="cursor:pointer;font-size:0.85em;font-weight:600;color:#0369a1">💡 Ejemplos</summary>
    <div style="margin-top:8px;display:flex;flex-direction:column;gap:4px">${ejemplos}</div></details>`, "border-color:#bae6fd")}`;
}

// ── Tab Consultas Predefinidas ────────────────────────────────────────────────

function _tabPredefinidas() {
  const consultas = _state.consultas;
  if (!consultas) {
    return `<div style="margin-bottom:12px">
      <button onclick="BDCloneModule.doCargarConsultas()" class="btn primary">📚 Cargar consultas de la query_library</button>
    </div><div style="color:#94a3b8;font-style:italic">Pulsa el boton para cargar las consultas del proyecto compatibles con Firebird real.</div>`;
  }
  if (consultas.error) {
    return `<div style="color:#dc2626;background:#fef2f2;padding:10px;border-radius:6px">${consultas.error}</div>`;
  }
  const lista = (consultas.consultas || []);
  const busq = document.getElementById("bd-clone-busq-q")?.value?.toLowerCase() || "";
  const filtradas = busq ? lista.filter(q => (q.nombre + q.desc_simple + q.sql).toLowerCase().includes(busq)) : lista;
  const filas = filtradas.slice(0, 80).map(q => {
    const dept = Array.isArray(q.dept) ? q.dept.join(", ") : (q.dept || "");
    return `<div style="border:1px solid #e2e8f0;border-radius:6px;padding:10px;margin-bottom:6px;background:white">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:0.88em">${q.nombre}</div>
          <div style="font-size:0.82em;color:#64748b;margin:2px 0">${q.desc_simple}</div>
          <div style="font-size:0.78em;color:#94a3b8">${dept} | ${q.tipo} | ${q.urgencia}</div>
        </div>
        <button onclick="BDCloneModule.doSQLRapido(${JSON.stringify(q.sql)})"
          style="white-space:nowrap;font-size:0.8em;padding:4px 10px;background:#0369a1;color:white;border:none;border-radius:4px;cursor:pointer">▶ Ejecutar</button>
      </div>
      <details style="margin-top:6px">
        <summary style="cursor:pointer;font-size:0.78em;color:#64748b">Ver SQL</summary>
        <pre style="font-size:0.78em;background:#f8fafc;padding:6px;border-radius:4px;overflow-x:auto;margin:4px 0">${q.sql}</pre>
      </details>
    </div>`;
  }).join("");
  return `<div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap">
    <button onclick="BDCloneModule.doCargarConsultas()" class="btn secondary" style="font-size:0.82em">↻ Recargar</button>
    <input id="bd-clone-busq-q" placeholder="Buscar consulta..." oninput="BDCloneModule.setTab('predefinidas')"
      style="flex:1;min-width:150px;padding:5px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:0.85em" value="${busq}">
    <span style="font-size:0.82em;color:#64748b">${filtradas.length}/${lista.length}</span>
  </div>${filas || '<div style="color:#94a3b8;font-style:italic">Sin resultados</div>'}
  ${filtradas.length > 80 ? '<div style="font-size:0.8em;color:#94a3b8;text-align:center">Mostrando 80 primeras. Usa el filtro.</div>' : ''}`;
}

// ── Tab Historial ─────────────────────────────────────────────────────────────

function _tabHistorial() {
  const hist = _state.historial || [];
  const filas = hist.map(h => {
    const color = h.ok ? "#16a34a" : "#dc2626";
    return `<div style="border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:6px;background:white">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span style="color:${color};font-weight:700">${h.ok ? "✅" : "❌"}</span>
        <code style="font-size:0.82em;flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${h.sql_preview}</code>
        <span style="font-size:0.78em;color:#94a3b8">${h.ms}ms | ${h.n_filas} filas | ${h.ts?.slice(0,19)}</span>
      </div>
      ${h.error ? `<div style="font-size:0.78em;color:#dc2626;margin-top:4px">${h.error}</div>` : ""}
      ${h.nota ? `<div style="font-size:0.78em;color:#ea580c;margin-top:2px">${h.nota}</div>` : ""}
    </div>`;
  }).join("");
  return `<div style="display:flex;gap:8px;margin-bottom:12px">
    <button onclick="BDCloneModule.doCargarHistorial()" class="btn secondary">↻ Refrescar</button>
    <button onclick="BDCloneModule.doLimpiarHistorial()" style="background:#fef2f2;color:#dc2626;border:1px solid #fecaca;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:0.85em">🗑 Limpiar</button>
  </div>
  ${hist.length === 0 ? '<div style="color:#94a3b8;font-style:italic">Sin entradas en el historial.</div>' : filas}`;
}

// ── Acciones ─────────────────────────────────────────────────────────────────

function _attachEvents() {
  const ta = document.getElementById("bd-clone-sql-input");
  if (ta) {
    ta.addEventListener("keydown", e => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault(); BDCloneModule.doEjecutarSQL();
      }
    });
  }
}

async function doProbarConexion() {
  const el = document.getElementById("bd-clone-conexion-result");
  if (el) el.innerHTML = '<span style="color:#64748b">Conectando...</span>';
  try {
    const r = await _fetch("/probar-conexion");
    if (el) el.innerHTML = r.ok
      ? `<div style="background:#f0fdf4;border-left:3px solid #16a34a;padding:8px 12px;border-radius:4px">✅ OK — ${r.n_tablas} tablas — ${r.ms}ms</div>`
      : `<div style="background:#fef2f2;border-left:3px solid #dc2626;padding:8px 12px;border-radius:4px">❌ ${r.error}</div>`;
  } catch (e) { if (el) el.innerHTML = `<div style="color:#dc2626">Error: ${e.message}</div>`; }
}

async function doDiagnostico() {
  const el = document.getElementById("bd-clone-conexion-result");
  if (el) el.innerHTML = '<span style="color:#64748b">Ejecutando diagnostico...</span>';
  try {
    const r = await _fetch("/diagnostico");
    const filas = Object.entries(r.tablas_clave || {}).map(([t, v]) =>
      `<tr><td style="padding:3px 8px;font-family:monospace;font-size:0.82em">${t}</td>
           <td style="padding:3px 8px">${v.ok?`<span style="color:#16a34a">${v.n.toLocaleString()} reg</span>`:`<span style="color:#dc2626">${v.error}</span>`}</td></tr>`
    ).join("");
    const bg = r.conexion_ok ? "background:#f0fdf4;border-left:3px solid #16a34a" : "background:#fef2f2;border-left:3px solid #dc2626";
    if (el) el.innerHTML = `<div style="${bg};padding:8px 12px;border-radius:4px;margin-bottom:8px">
      ${r.conexion_ok?"✅ Conexion OK":`❌ ${r.error}`} — ${r.ms}ms</div>
      ${filas?`<table style="border-collapse:collapse;width:100%"><thead><tr>
        <th style="text-align:left;padding:3px 8px;font-size:0.78em;color:#64748b">Tabla</th>
        <th style="text-align:left;padding:3px 8px;font-size:0.78em;color:#64748b">Registros</th>
      </tr></thead><tbody>${filas}</tbody></table>`:""}`;
  } catch (e) { if (el) el.innerHTML = `<div style="color:#dc2626">Error: ${e.message}</div>`; }
}

async function doCargarCatalogo(force = false) {
  _state.tablaDetalle = null; _state.tablaSeleccionada = null; _render();
  try { _state.catalog = await _fetch("/catalogo", { method: "POST", body: JSON.stringify({ force_refresh: force }) }); }
  catch (e) { _state.catalog = { error: e.message }; }
  _render();
}

async function doSeleccionarTabla(tabla) {
  _state.tablaSeleccionada = tabla; _state.tablaDetalle = null; _render();
  try { _state.tablaDetalle = await _fetch("/tabla-detalle", { method: "POST", body: JSON.stringify({ tabla }) }); }
  catch (e) { _state.tablaDetalle = { tabla, error: e.message, columnas: [], muestra: [] }; }
  _render();
}

async function doEjecutarSQL() {
  const ta = document.getElementById("bd-clone-sql-input");
  const sql = (ta ? ta.value : _state.sqlActual).trim();
  if (!sql) return;
  _state.sqlActual = sql; _state.resultadoSQL = null; _render();
  try { _state.resultadoSQL = await _fetch("/ejecutar-sql", { method: "POST", body: JSON.stringify({ sql }) }); }
  catch (e) { _state.resultadoSQL = { ok: false, error: e.message }; }
  _render();
}

function doClearSQL() { _state.sqlActual = ""; _state.resultadoSQL = null; _render(); }

function doSQLRapido(sql) {
  _state.sqlActual = sql; _state.resultadoSQL = null; _state.currentTab = "sql"; _render();
  setTimeout(() => BDCloneModule.doEjecutarSQL(), 80);
}

async function doCargarConsultas() {
  _state.consultas = null; _render();
  try { _state.consultas = await _fetch("/consultas-predefinidas"); }
  catch (e) { _state.consultas = { error: e.message }; }
  _render();
}

async function doCargarHistorial() {
  try { const r = await _fetch("/historial"); _state.historial = r.historial || []; _render(); }
  catch (e) { console.error("[BDClone] historial:", e); }
}

async function doLimpiarHistorial() {
  if (!confirm("Limpiar todo el historial?")) return;
  try { await _fetch("/historial", { method: "DELETE" }); _state.historial = []; _render(); }
  catch (e) { console.error("[BDClone] limpiar:", e); }
}

async function doActivarEscritura() {
  const input = document.getElementById("bd-escritura-confirm");
  const confirmacion = input ? input.value.trim() : "";
  const el = document.getElementById("bd-clone-escritura-result");
  try {
    const r = await _fetch("/escritura", { method: "POST", body: JSON.stringify({ activar: true, confirmacion }) });
    if (r.ok && _state.status) _state.status.modo_escritura = true;
    if (el) el.innerHTML = r.ok
      ? `<div style="color:#ea580c;font-size:0.85em">⚠️ ${r.mensaje}</div>`
      : `<div style="color:#dc2626;font-size:0.85em">${r.error}</div>`;
    if (r.ok) _render();
  } catch (e) { if (el) el.innerHTML = `<div style="color:#dc2626;font-size:0.85em">${e.message}</div>`; }
}

async function doDesactivarEscritura() {
  try {
    const r = await _fetch("/escritura", { method: "POST", body: JSON.stringify({ activar: false, confirmacion: "" }) });
    if (r.ok && _state.status) _state.status.modo_escritura = false;
    _render();
  } catch (e) { console.error("[BDClone] desactivar escritura:", e); }
}

function setTab(tab) { _state.currentTab = tab; _render(); }

async function onEnter() {
  _render();
  try { _state.status = await _fetch("/status"); _render(); doCargarHistorial(); }
  catch (e) { console.error("[BDClone] onEnter:", e); }
}

// ── Exportar modulo ───────────────────────────────────────────────────────────

window.BDCloneModule = {
  onEnter, setTab,
  doProbarConexion, doDiagnostico,
  doCargarCatalogo, doSeleccionarTabla,
  doEjecutarSQL, doClearSQL, doSQLRapido,
  doCargarConsultas, doCargarHistorial, doLimpiarHistorial,
  doActivarEscritura, doDesactivarEscritura,
};
