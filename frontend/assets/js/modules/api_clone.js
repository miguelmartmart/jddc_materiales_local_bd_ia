/**
 * api_clone.js v2 — API Clone: replica API Explorer + Probador Manual con datos reales.
 * Probador Manual: formulario dinámico, lookup de BD, badge de fiabilidad, SQL real visible.
 */
const API = "/api/api-clone";

let _state = {
  status: null, catalogue: null, currentTab: "status",
  selectedClase: null, browseResult: null, readResult: null,
  permisoResult: null, infoResult: null, discoverResult: null,
  history: [], matrix: {},
  browseParams: {}, browseNum: 20, readObjectid: "",
  // Probador Manual
  probadorClase: null,
  probadorParams: {},       // campo -> valor introducido
  probadorLookups: {},      // campo -> [{id, desc}] de BD
  probadorLookupLoading: {},// campo -> true/false
  probadorResultado: null,
  probadorOperacion: "browse",
  probadorNum: 20,
};

async function _fetch(path, opts = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...opts });
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
function _card(html, extra="") {
  return `<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:12px;${extra}">${html}</div>`;
}
function _tabla(filas, cols) {
  if (!filas || !filas.length) return '<div style="color:#94a3b8;font-style:italic;padding:8px">Sin resultados</div>';
  const c = cols || Object.keys(filas[0]);
  const ths = c.map(k=>`<th style="padding:5px 10px;text-align:left;font-size:0.78em;color:#64748b;background:#f8fafc;border-bottom:1px solid #e2e8f0">${k}</th>`).join("");
  const rows = filas.map(row=>`<tr>${c.map(k=>`<td style="padding:5px 10px;font-size:0.83em;border-bottom:1px solid #f1f5f9">${row[k]??'—'}</td>`).join("")}</tr>`).join("");
  return `<div style="overflow-x:auto;border-radius:6px;border:1px solid #e2e8f0"><table style="width:100%;border-collapse:collapse"><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table></div>`;
}
function _render() {
  const root = document.getElementById("api-clone-root");
  if (!root) return;
  root.innerHTML = _buildUI();
}

// ── Build UI ──────────────────────────────────────────────────────────────────
function _buildUI() {
  const TABS = [
    ["status","🔌 Estado"],["catalogo","📋 Catálogo"],["probador","🧪 Probador"],
    ["explorador","🔍 Explorador"],["discover","🚀 Discover All"],["historial","🕐 Historial"],
  ];
  const tabBtns = TABS.map(([id,lbl])=>
    `<button onclick="ApiCloneModule.setTab('${id}')"
      style="padding:8px 14px;border:none;background:${_state.currentTab===id?'#0369a1':'transparent'};
      color:${_state.currentTab===id?'white':'#64748b'};border-radius:6px 6px 0 0;cursor:pointer;
      font-size:0.88em;font-weight:${_state.currentTab===id?'600':'400'}">${lbl}</button>`
  ).join("");
  const st = _state.status;
  const statusBar = st
    ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
        ${st.db_configurada?_badge("#16a34a","BD configurada"):_badge("#dc2626","BD no configurada")}
        ${_badge("#0369a1","firebird_directo")}
        ${_badge("#64748b",st.total_clases+" clases")}
        <span style="font-size:0.82em;color:#64748b">Host: ${st.db_host} | ...${st.db_name_short}</span>
      </div>`
    : `<div style="color:#94a3b8;margin-bottom:8px">Cargando...</div>`;
  return `<div style="padding:12px;font-family:Inter,sans-serif">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
      <h2 style="margin:0;color:#0f172a;font-size:1.1em">🔁 API Clone — Datos Reales Firebird (sin mPYME)</h2>
      <button onclick="ApiCloneModule.onEnter()" style="padding:4px 10px;font-size:0.78em;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:4px;cursor:pointer">↻</button>
    </div>
    <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:0.82em;color:#92400e">
      ⚡ <strong>Sin API mPYME</strong> — Todas las operaciones ejecutan SQL SELECT directo en Firebird.
      Los datos son exactamente los mismos que devolveria la API de Distrito K, obtenidos directamente de la BD.
    </div>
    ${statusBar}
    <div style="border-bottom:2px solid #e2e8f0;margin-bottom:12px">${tabBtns}</div>
    <div id="api-clone-tab">${_buildTab()}</div>
  </div>`;
}

function _buildTab() {
  switch (_state.currentTab) {
    case "status":    return _tabStatus();
    case "catalogo":  return _tabCatalogo();
    case "probador":  return _tabProbador();
    case "explorador":return _tabExplorador();
    case "discover":  return _tabDiscover();
    case "historial": return _tabHistorial();
    default: return "";
  }
}

// ── Tab Status ────────────────────────────────────────────────────────────────
function _tabStatus() {
  const st = _state.status;
  if (!st) return `<div style="color:#94a3b8">Cargando estado...</div>`;
  return _card(`
    <h3 style="margin:0 0 12px;font-size:1em">Estado de la conexion</h3>
    <table style="border-collapse:collapse;width:100%">
      <tr><td style="padding:4px 10px;color:#64748b;font-size:0.85em;width:180px">BD configurada</td>
          <td>${st.db_configurada?_badge("#16a34a","SI"):_badge("#dc2626","NO — configura DB_NAME en .env")}</td></tr>
      <tr><td style="padding:4px 10px;color:#64748b;font-size:0.85em">Host Firebird</td>
          <td style="font-family:monospace;font-size:0.85em">${st.db_host}</td></tr>
      <tr><td style="padding:4px 10px;color:#64748b;font-size:0.85em">Fichero BD</td>
          <td style="font-family:monospace;font-size:0.85em">...${st.db_name_short}</td></tr>
      <tr><td style="padding:4px 10px;color:#64748b;font-size:0.85em">Clases disponibles</td>
          <td style="font-size:0.85em">${st.total_clases} clases</td></tr>
      <tr><td style="padding:4px 10px;color:#64748b;font-size:0.85em">Historial</td>
          <td style="font-size:0.85em">${st.historial_entradas} entradas</td></tr>
    </table>
    <div style="margin-top:12px;background:#f0fdf4;border-left:3px solid #16a34a;padding:8px 12px;border-radius:4px;font-size:0.83em;color:#166534">
      <strong>Sin mPYME:</strong> browse/read/permiso/info/discover-all se ejecutan con SELECT directo
      en Firebird — exactamente los mismos datos que devuelve la API de Distrito K, sin necesidad de login ni sesion.
    </div>
  `);
}

// ── Tab Catalogo ──────────────────────────────────────────────────────────────
function _tabCatalogo() {
  const cat = _state.catalogue;
  if (!cat) {
    return `<button onclick="ApiCloneModule.doCargarCatalogo()" class="btn primary">📋 Cargar catalogo</button>`;
  }
  const claseSeleccionada = _state.selectedClase;
  const por_modulo = cat.catalogue || {};
  const filas = Object.entries(por_modulo).map(([mod, clases]) => {
    const cls = Object.entries(clases).map(([clase, ops]) => {
      const activa = clase === claseSeleccionada;
      return `<tr style="cursor:pointer;background:${activa?'#dbeafe':'transparent'}"
                 onclick="ApiCloneModule.doSeleccionarClase('${clase}')">
                <td style="padding:4px 10px;font-size:0.85em;font-family:monospace">${clase}</td>
                <td style="padding:4px 10px;font-size:0.78em;color:#64748b">${ops.join(", ")}</td>
              </tr>`;
    }).join("");
    return `<tr style="background:#f8fafc"><td colspan="2" style="padding:6px 10px;font-size:0.78em;font-weight:700;color:#0369a1;border-top:1px solid #e2e8f0">${mod}</td></tr>${cls}`;
  }).join("");

  return `
    <div style="margin-bottom:10px">
      <button onclick="ApiCloneModule.doCargarCatalogo()" class="btn secondary" style="font-size:0.82em">↻ Recargar</button>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div>${_card(`
        <div style="max-height:420px;overflow-y:auto;border-radius:6px;border:1px solid #e2e8f0">
          <table style="width:100%;border-collapse:collapse">
            <thead><tr>
              <th style="padding:5px 10px;text-align:left;font-size:0.78em;color:#64748b;background:#f8fafc;border-bottom:1px solid #e2e8f0;position:sticky;top:0">Clase</th>
              <th style="padding:5px 10px;text-align:left;font-size:0.78em;color:#64748b;background:#f8fafc;border-bottom:1px solid #e2e8f0;position:sticky;top:0">Operaciones</th>
            </tr></thead>
            <tbody>${filas}</tbody>
          </table>
        </div>
        <div style="font-size:0.8em;color:#94a3b8;margin-top:6px">Haz clic en una clase para ver sus datos reales</div>
      `)}</div>
      <div id="api-clone-clase-detalle">
        ${claseSeleccionada
          ? `<div style="color:#94a3b8;font-style:italic;padding:20px">Cargando ${claseSeleccionada}...</div>`
          : `<div style="color:#94a3b8;font-style:italic;padding:20px">Selecciona una clase para ver sus datos reales</div>`}
      </div>
    </div>`;
}

// ── Tab Probador Manual — helpers ─────────────────────────────────────────────
function _fiabilidadBadge(f) {
  if (!f) return "";
  return `<div style="background:${f.color}15;border:2px solid ${f.color};border-radius:10px;padding:14px;margin-bottom:16px">
    <div style="display:flex;gap:10px;align-items:flex-start">
      <span style="font-size:1.8em;flex-shrink:0">${f.icono}</span>
      <div style="flex:1">
        <div style="font-weight:700;color:${f.color};margin-bottom:4px">${f.titulo}</div>
        <div style="font-size:0.85em;color:#374151;margin-bottom:8px">${f.explicacion}</div>
        ${(f.detalle||[]).map(d=>`<div style="font-size:0.82em">${d}</div>`).join("")}
        <details style="margin-top:8px">
          <summary style="cursor:pointer;font-size:0.8em;color:#64748b;font-weight:600">Ver SQL real que ejecuta este servicio</summary>
          <pre style="font-size:0.8em;background:#f8fafc;padding:8px;border-radius:6px;margin-top:4px;overflow-x:auto;color:#1e40af">${f.sql_ejemplo}</pre>
        </details>
      </div>
      <div style="background:${f.color};color:white;border-radius:6px;padding:4px 10px;font-size:0.75em;font-weight:700;white-space:nowrap">${f.nivel}</div>
    </div>
  </div>`;
}
function _campoProbadorHtml(campo) {
  const val = _state.probadorParams[campo.n]||"";
  const loading = _state.probadorLookupLoading[campo.n];
  const lookups = _state.probadorLookups[campo.n]||[];
  return `<div style="border:1px solid ${campo.req?'#fca5a5':'#e2e8f0'};border-radius:8px;padding:12px;margin-bottom:10px;background:${campo.req?'#fff5f5':'white'}">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <label style="font-size:0.88em;font-weight:700;font-family:monospace">${campo.n}${campo.req?' <span style="color:#dc2626">*</span>':''}</label>
      <span style="font-size:0.75em;color:#64748b;background:#f1f5f9;padding:2px 6px;border-radius:4px">${campo.tipo}</span>
    </div>
    <div style="font-size:0.83em;color:#374151;margin-bottom:6px">${campo.desc}</div>
    ${campo.nota?`<div style="font-size:0.8em;color:#0369a1;background:#eff6ff;padding:5px 8px;border-radius:4px;margin-bottom:6px">💡 ${campo.nota}</div>`:''}
    <div style="display:flex;gap:6px;align-items:center">
      <input id="prob-campo-${campo.n}" value="${val}" placeholder="${campo.ejemplo?'ej: '+campo.ejemplo:''}"
        onchange="ApiCloneModule.doProbadorParamChange('${campo.n}',this.value)"
        style="flex:1;padding:7px 10px;border:1.5px solid #d1d5db;border-radius:6px;font-size:0.88em;font-family:monospace">
      ${campo.fk_tabla?`<button onclick="ApiCloneModule.doBuscarEnBD('${campo.n}')"
        title="Buscar valores reales en ${campo.fk_tabla}"
        style="padding:7px 12px;background:#0369a1;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.82em;white-space:nowrap">${loading?'⏳':'🔍 BD'}</button>`:''}
    </div>
    ${lookups.length?`<div style="margin-top:6px;border:1px solid #bae6fd;border-radius:6px;background:#f0f9ff;max-height:180px;overflow-y:auto">
      <div style="padding:4px 8px;font-size:0.75em;font-weight:600;color:#0369a1;border-bottom:1px solid #bae6fd">Valores reales de ${campo.fk_tabla} — clic para seleccionar:</div>
      ${lookups.map(v=>`<div onclick="ApiCloneModule.doProbadorParamSelect('${campo.n}','${v.id}')"
        style="padding:5px 10px;cursor:pointer;font-size:0.83em;font-family:monospace;border-bottom:1px solid #e0f2fe"
        onmouseover="this.style.background='#dbeafe'" onmouseout="this.style.background=''">
        <strong>${v.id}</strong>${v.desc&&v.desc!==v.id?` — <span style="color:#64748b">${v.desc}</span>`:''}</div>`).join('')}
    </div>`:''}
  </div>`;
}
function _tabProbador() {
  const cat = _state.catalogue;
  const clases = cat ? Object.keys(cat.catalogue||{}).flatMap(m=>Object.keys(cat.catalogue[m])) : [];
  const pc = _state.probadorClase || clases[0] || "";
  const camposMeta = cat?.campos_por_clase?.[pc] || [];
  const fiab = cat?.fiabilidad_por_clase?.[pc] || null;
  const ops = cat?.catalogue ? (Object.values(cat.catalogue).find(m=>m[pc])||{})[pc]||[] : [];
  const opBtns = ops.map(op => {
    const esEsc = ["write","imputaPro","imputaRep","imputaFab"].includes(op);
    const esTmp = ["new","edit","cancel"].includes(op);
    const c = esEsc?"#dc2626":esTmp?"#ea580c":"#0369a1";
    const act = _state.probadorOperacion===op;
    return `<button onclick="ApiCloneModule.doProbadorOpChange('${op}')" title="${esEsc?'⚠️ ESCRITURA IRREVERSIBLE':esTmp?'Temporal':'Solo lectura'}"
      style="padding:6px 12px;border:2px solid ${act?c:'#e2e8f0'};border-radius:6px;background:${act?c:'white'};color:${act?'white':c};font-size:0.82em;font-weight:${act?700:400};cursor:pointer">${op}</button>`;
  }).join("");
  const camposHtml = camposMeta.length===0
    ? `<div style="color:#94a3b8;font-style:italic;font-size:0.85em;padding:8px">Sin parámetros requeridos — browse devuelve todos los registros disponibles.</div>`
    : camposMeta.map(_campoProbadorHtml).join("");
  const res = _state.probadorResultado;
  const resHtml = res ? _renderProbadorResultado(res) : `<div style="color:#94a3b8;font-style:italic;padding:30px;text-align:center;border:2px dashed #e2e8f0;border-radius:10px">Configura los parámetros y pulsa Ejecutar para ver datos reales de Firebird.</div>`;
  return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div>
      <div style="margin-bottom:14px">
        <label style="font-size:0.85em;font-weight:600;color:#374151;display:block;margin-bottom:4px">Clase de objeto</label>
        <select id="prob-clase" onchange="ApiCloneModule.doProbadorClaseChange(this.value)"
          style="padding:8px 12px;border:2px solid #e2e8f0;border-radius:8px;font-size:0.9em;font-family:monospace;width:100%;max-width:300px">
          ${clases.map(c=>`<option value="${c}" ${c===pc?"selected":""}>${c}</option>`).join("")}
        </select>
      </div>
      ${_fiabilidadBadge(fiab)}
      <div style="margin-bottom:10px">
        <div style="font-size:0.85em;font-weight:600;color:#374151;margin-bottom:6px">Operación a ejecutar</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">${opBtns}</div>
      </div>
      <div style="margin-bottom:12px">
        <div style="font-size:0.85em;font-weight:600;color:#374151;margin-bottom:8px">Parámetros de entrada</div>
        ${camposHtml}
        ${_state.probadorOperacion==='browse'?`<div style="margin-top:8px;display:flex;align-items:center;gap:8px">
          <label style="font-size:0.83em;color:#64748b">Máx. registros:</label>
          <input type="number" value="${_state.probadorNum}" min="1" max="500"
            onchange="ApiCloneModule.doProbadorNumChange(this.value)"
            style="width:70px;padding:5px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:0.85em">
        </div>`:''}
      </div>
      <button onclick="ApiCloneModule.doProbadorEjecutar()"
        style="width:100%;padding:11px;background:#0369a1;color:white;border:none;border-radius:8px;cursor:pointer;font-size:0.9em;font-weight:700;letter-spacing:0.01em">
        ▶ Ejecutar ${_state.probadorOperacion}(${pc})</button>
    </div>
    <div>${resHtml}</div>
  </div>`;
}

function _renderProbadorResultado(r) {
  if (!r) return "";
  const ok = r.estado==="ok"||r.code===0;
  const color = ok?"#16a34a":"#dc2626";
  const items = r.data?.items||[];
  const total = r.data?.total;
  return `<div style="border:2px solid ${color};border-radius:10px;padding:16px">
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
      <span style="font-size:1.3em">${ok?"✅":"❌"}</span>
      <strong style="color:${color};font-size:1em">${ok?"Éxito — datos reales de Firebird":"Error"}</strong>
      <span style="font-size:0.82em;color:#64748b">${r.duracion_ms}ms | firebird_directo</span>
      ${ok&&total!=null?_badge("#16a34a",total.toLocaleString()+" totales"):""}
    </div>
    ${r.error?`<div style="background:#fef2f2;border-left:3px solid #dc2626;padding:8px 12px;border-radius:4px;font-size:0.85em;color:#dc2626;margin-bottom:8px">${r.error}</div>`:""}
    ${items.length?`<div style="margin-bottom:6px;font-size:0.82em;color:#64748b">${items.length} registros${total!=null?` de ${total.toLocaleString()} totales`:""} — 100% datos reales</div>${_tabla(items)}`:""}
    ${r.data&&!items.length&&typeof r.data==="object"&&ok&&!r.data.aviso?`<pre style="font-size:0.82em;background:#f8fafc;padding:10px;border-radius:6px;overflow-x:auto;max-height:350px">${JSON.stringify(r.data,null,2)}</pre>`:""}
    ${r.data?.aviso?`<div style="background:#fffbeb;border-left:3px solid #f59e0b;padding:8px 12px;border-radius:4px;font-size:0.85em">${r.data.aviso}</div>`:""}
  </div>`;
}

function _buildResult(r,t){if(!r)return"";const ok=r.estado==="ok"||r.code===0;const c=ok?"#16a34a":"#dc2626";const it=r.data?.items||[];return _card(`<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><strong style="color:${c}">${ok?"✅":"❌"} ${t}</strong><span style="font-size:0.8em;color:#64748b">${r.duracion_ms}ms</span></div>${r.error?`<div style="color:#dc2626;font-size:0.85em;background:#fef2f2;padding:6px;border-radius:4px">${r.error}</div>`:""}${it.length?`${_tabla(it)}<div style="font-size:0.8em;color:#94a3b8;margin-top:4px">${it.length} items | total: ${r.data?.total||"?"}</div>`:""}${r.data&&!it.length&&typeof r.data==="object"&&ok?`<pre style="font-size:0.8em;background:#f8fafc;padding:8px;border-radius:4px;overflow-x:auto;max-height:280px">${JSON.stringify(r.data,null,2)}</pre>`:""}`,`border-left:3px solid ${c}`);}
function _tabExplorador(){const cat=_state.catalogue;const clases=cat?Object.keys(cat.catalogue||{}).flatMap(m=>Object.keys(cat.catalogue[m])):[];const ca=_state.selectedClase||clases[0]||"";return`<div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap"><select id="ac-clase-sel" onchange="ApiCloneModule.doClaseChange(this.value)" style="padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:0.88em;font-family:monospace">${clases.map(c=>`<option value="${c}" ${c===ca?"selected":""}>${c}</option>`).join("")}</select><button onclick="ApiCloneModule.doPermiso()" class="btn secondary" style="font-size:0.82em">🔑 permiso</button><button onclick="ApiCloneModule.doInfo()" class="btn secondary" style="font-size:0.82em">ℹ️ info</button><button onclick="ApiCloneModule.doBrowse()" class="btn primary">📋 browse</button></div><div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap"><input id="ac-read-id" placeholder="objectid para read..." value="${_state.readObjectid}" style="padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:0.88em;font-family:monospace;flex:1;min-width:150px"><button onclick="ApiCloneModule.doRead()" class="btn secondary">🔍 read</button><input id="ac-browse-num" type="number" value="${_state.browseNum}" min="1" max="200" style="width:70px;padding:6px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:0.88em" onchange="ApiCloneModule.setBrowseNum(this.value)"></div>${_buildResult(_state.browseResult,"browse — datos reales")}${_buildResult(_state.readResult,"read — registro real")}${_buildResult(_state.permisoResult,"permiso — conteo real")}${_buildResult(_state.infoResult,"info — columnas RDB$")}${!_state.browseResult&&!_state.readResult&&!_state.permisoResult&&!_state.infoResult?`<div style="color:#94a3b8;font-style:italic;padding:20px;text-align:center">Selecciona clase y ejecuta. 100% datos reales.</div>`:""}`;}
function _tabDiscover(){const dr=_state.discoverResult;return`<div style="margin-bottom:12px"><button onclick="ApiCloneModule.doDiscoverAll()" class="btn primary" style="font-weight:700">🚀 Discover All</button><span style="font-size:0.82em;color:#64748b;margin-left:8px">Browse real en ${_state.catalogue?.all_classes?.length||17} clases. Sin mPYME.</span></div>${dr?_renderDiscover(dr):'<div style="color:#94a3b8;font-style:italic">Pulsa el boton.</div>'}`;}
function _renderDiscover(dr){const res=dr.resumen||{};const filas=Object.entries(dr.clases||{}).map(([clase,d])=>{const ok=d.browse_code===0;return`<tr><td style="padding:5px 10px;font-family:monospace;font-size:0.85em">${clase}</td><td style="padding:5px 10px;font-size:0.82em;color:#64748b">${d.modulo}</td><td style="padding:5px 10px;text-align:right;font-size:0.85em">${(d.n_registros||0).toLocaleString()}</td><td>${ok?'<span style="color:#16a34a">✅</span>':'<span style="color:#dc2626">❌ '+(d.browse_error||"err").slice(0,30)+'</span>'}</td><td style="font-size:0.78em;color:#64748b;padding:5px 10px">${(d.campos_detectados||[]).slice(0,4).join(", ")}</td><td style="text-align:right;font-size:0.78em;color:#94a3b8;padding:5px 10px">${d.ms}ms</td></tr>`;}).join("");return`<div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">${_badge("#16a34a",res.clases_ok+" OK")} ${_badge("#dc2626",res.clases_error+" err")} ${_badge("#0369a1",(res.total_registros_bd||0).toLocaleString()+" reg")}<span style="font-size:0.82em;color:#64748b">${dr.ms_total}ms | ${dr.timestamp?.slice(0,19)}</span></div><div style="overflow-x:auto;border-radius:8px;border:1px solid #e2e8f0;max-height:400px;overflow-y:auto"><table style="width:100%;border-collapse:collapse"><thead style="position:sticky;top:0;background:#f8fafc"><tr>${["Clase","Modulo","Registros","Browse","Campos","ms"].map(h=>`<th style="padding:5px 10px;text-align:left;font-size:0.78em;color:#64748b;border-bottom:1px solid #e2e8f0">${h}</th>`).join("")}</tr></thead><tbody>${filas}</tbody></table></div>`;}
function _tabHistorial(){const hist=_state.history||[];return`<div style="display:flex;gap:8px;margin-bottom:12px"><button onclick="ApiCloneModule.doCargarHistorial()" class="btn secondary">↻ Refrescar</button><button onclick="ApiCloneModule.doLimpiarHistorial()" style="background:#fef2f2;color:#dc2626;border:1px solid #fecaca;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:0.85em">🗑 Limpiar</button></div>${hist.length===0?'<div style="color:#94a3b8;font-style:italic">Sin historial.</div>':hist.map(h=>`<div style="border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:6px;background:white"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span style="color:${h.estado==="ok"?"#16a34a":"#dc2626"};font-weight:700">${h.estado==="ok"?"✅":"❌"}</span><code style="font-size:0.82em">${h.clase}.${h.operacion}</code><span style="font-size:0.78em;color:#94a3b8">${h.duracion_ms}ms|${h.n_items}items|${h.timestamp?.slice(0,19)}</span></div>${h.error?`<div style="font-size:0.78em;color:#dc2626;margin-top:4px">${h.error}</div>`:""}</div>`).join("")}`;}
// ── Acciones ─────────────────────────────────────────────────────────────────

async function doCargarCatalogo() {
  _state.catalogue = null; _render();
  try { _state.catalogue = await _fetch("/catalogue"); } catch(e) { _state.catalogue = {error:e.message,catalogue:{},all_classes:[]}; }
  _render();
}

function doClaseChange(clase) { _state.selectedClase = clase; _state.browseResult = _state.readResult = _state.permisoResult = _state.infoResult = null; _render(); }
function doClaseDetalle(clase) { _state.selectedClase = clase; _state.currentTab = "explorador"; _render(); }
function setBrowseNum(n) { _state.browseNum = parseInt(n)||20; }
function doSeleccionarClase(clase) {
  _state.selectedClase = clase;
  // Quick browse en detalle del catalogo
  _fetch("/browse", {method:"POST", body:JSON.stringify({clase, params:{}, num:5})})
    .then(r => {
      const el = document.getElementById("api-clone-clase-detalle");
      if (!el) return;
      const ok = r.estado==="ok";
      const items = r.data?.items||[];
      const n = r.data?.total||0;
      const meta_clase = _state.catalogue?.catalogue?Object.values(_state.catalogue.catalogue).find(m=>m[clase]):null;
      const ops = meta_clase?meta_clase[clase]:[];
      el.innerHTML = `<div style="background:white;border:1px solid #e2e8f0;border-radius:8px;padding:14px">
        <div style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
          <h4 style="margin:0;font-family:monospace">${clase}</h4>
          ${_badge("#0369a1",(n).toLocaleString()+" registros")}
        </div>
        <div style="font-size:0.82em;color:#64748b;margin-bottom:8px">Ops: ${ops.join(", ")}</div>
        ${ok&&items.length?`${_tabla(items)}<div style="font-size:0.8em;color:#94a3b8;margin-top:4px">${items.length} muestra | total: ${n}</div>`:""}
        ${!ok?`<div style="color:#dc2626;font-size:0.85em">${r.error}</div>`:""}
        <div style="margin-top:8px;display:flex;gap:6px">
          <button onclick="ApiCloneModule.doClaseDetalle('${clase}')" style="font-size:0.8em;padding:4px 10px;background:#0369a1;color:white;border:none;border-radius:4px;cursor:pointer">Ver en Explorador</button>
        </div>
      </div>`;
    }).catch(e => { const el=document.getElementById("api-clone-clase-detalle"); if(el) el.innerHTML=`<div style="color:#dc2626">${e.message}</div>`; });
  _state.currentTab = "catalogo"; _render();
}

async function doPermiso() {
  const clase = document.getElementById("ac-clase-sel")?.value||_state.selectedClase;
  _state.selectedClase = clase; _state.permisoResult = null;
  try { _state.permisoResult = await _fetch("/permiso",{method:"POST",body:JSON.stringify({clase})}); }
  catch(e) { _state.permisoResult = {estado:"falla",error:e.message,duracion_ms:0,code:-1}; }
  _render();
}
async function doInfo() {
  const clase = document.getElementById("ac-clase-sel")?.value||_state.selectedClase;
  _state.selectedClase = clase; _state.infoResult = null;
  try { _state.infoResult = await _fetch("/info",{method:"POST",body:JSON.stringify({clase})}); }
  catch(e) { _state.infoResult = {estado:"falla",error:e.message,duracion_ms:0,code:-1}; }
  _render();
}
async function doBrowse() {
  const clase = document.getElementById("ac-clase-sel")?.value||_state.selectedClase;
  const num = parseInt(document.getElementById("ac-browse-num")?.value||_state.browseNum)||20;
  _state.selectedClase = clase; _state.browseNum = num; _state.browseResult = null;
  try { _state.browseResult = await _fetch("/browse",{method:"POST",body:JSON.stringify({clase,params:{},num})}); }
  catch(e) { _state.browseResult = {estado:"falla",error:e.message,duracion_ms:0,code:-1}; }
  _render();
}
async function doRead() {
  const clase = document.getElementById("ac-clase-sel")?.value||_state.selectedClase;
  const objectid = document.getElementById("ac-read-id")?.value||_state.readObjectid;
  _state.selectedClase = clase; _state.readObjectid = objectid; _state.readResult = null;
  try { _state.readResult = await _fetch("/read",{method:"POST",body:JSON.stringify({clase,objectid})}); }
  catch(e) { _state.readResult = {estado:"falla",error:e.message,duracion_ms:0,code:-1}; }
  _render();
}
async function doDiscoverAll() {
  _state.discoverResult = null; _state.currentTab = "discover"; _render();
  try { _state.discoverResult = await _fetch("/discover-all",{method:"POST",body:JSON.stringify({num_por_clase:5})}); }
  catch(e) { _state.discoverResult = {error:e.message,resumen:{},clases:{},ms_total:0}; }
  _render();
}
async function doCargarHistorial() {
  try { const r = await _fetch("/history"); _state.history = r.history||[]; _render(); }
  catch(e) { console.error("[ApiClone] historial:",e); }
}
async function doLimpiarHistorial() {
  if(!confirm("Limpiar historial?")) return;
  try { await _fetch("/history",{method:"DELETE"}); _state.history=[]; _render(); }
  catch(e) { console.error("[ApiClone] limpiar:",e); }
}
function setTab(tab) { _state.currentTab = tab; _render(); }
async function onEnter() {
  _render();
  try { _state.status = await _fetch("/status"); _render(); }
  catch(e) { console.error("[ApiClone] onEnter:",e); }
  if (!_state.catalogue) {
    try { _state.catalogue = await _fetch("/catalogue"); _render(); }
    catch(e) { console.error("[ApiClone] catalogue:",e); }
  }
  doCargarHistorial();
}

// ── Probador Manual — acciones ────────────────────────────────────────────────

function doProbadorClaseChange(clase) {
  _state.probadorClase = clase;
  _state.probadorParams = {};
  _state.probadorLookups = {};
  _state.probadorResultado = null;
  _state.probadorOperacion = "browse";
  _render();
}

function doProbadorOpChange(op) {
  _state.probadorOperacion = op;
  _state.probadorResultado = null;
  _render();
}

function doProbadorParamChange(campo, valor) {
  _state.probadorParams[campo] = valor;
}

function doProbadorParamSelect(campo, valor) {
  _state.probadorParams[campo] = valor;
  _state.probadorResultado = null;
  _render();
  // Tras seleccionar valor, auto-ejecutar browse
  setTimeout(() => ApiCloneModule.doProbadorEjecutar(), 80);
}

function doProbadorNumChange(n) {
  _state.probadorNum = parseInt(n) || 20;
}

async function doBuscarEnBD(campo) {
  _state.probadorLookupLoading[campo] = true;
  _render();
  try {
    const r = await _fetch("/valores-campo", {
      method: "POST",
      body: JSON.stringify({ campo, limit: 15 }),
    });
    _state.probadorLookups[campo] = r.ok ? r.valores : [];
    if (!r.ok) console.warn("[ApiClone] lookup:", r.error);
  } catch(e) {
    _state.probadorLookups[campo] = [];
    console.error("[ApiClone] doBuscarEnBD:", e);
  } finally {
    _state.probadorLookupLoading[campo] = false;
    _render();
  }
}

async function doProbadorEjecutar() {
  const clase = _state.probadorClase;
  const op = _state.probadorOperacion;
  if (!clase) return;
  // Leer valores actuales de los inputs
  const camposMeta = _state.catalogue?.campos_por_clase?.[clase] || [];
  camposMeta.forEach(c => {
    const el = document.getElementById(`prob-campo-${c.n}`);
    if (el && el.value) _state.probadorParams[c.n] = el.value;
  });
  _state.probadorResultado = null;
  _render();
  try {
    let r;
    const params = {..._state.probadorParams};
    if (op === "browse") {
      r = await _fetch("/browse", { method:"POST", body:JSON.stringify({clase, params, num:_state.probadorNum}) });
    } else if (op === "read") {
      const objectid = params.codProyecto || params.codOrden || params.codCliente || params.codArticulo || Object.values(params)[0] || "";
      r = await _fetch("/read", { method:"POST", body:JSON.stringify({clase, objectid}) });
    } else if (op === "permiso") {
      r = await _fetch("/permiso", { method:"POST", body:JSON.stringify({clase}) });
    } else if (op === "info") {
      r = await _fetch("/info", { method:"POST", body:JSON.stringify({clase}) });
    } else {
      r = {estado:"falla",error:`Operación '${op}' no disponible en el Probador (requiere escritura activa).`,duracion_ms:0,code:-1};
    }
    _state.probadorResultado = r;
  } catch(e) {
    _state.probadorResultado = {estado:"falla",error:e.message,duracion_ms:0,code:-1};
  }
  _render();
}

window.ApiCloneModule = {
  onEnter, setTab,
  doCargarCatalogo, doSeleccionarClase, doClaseChange, doClaseDetalle,
  doPermiso, doInfo, doBrowse, doRead, doDiscoverAll,
  doCargarHistorial, doLimpiarHistorial, setBrowseNum,
  // Probador Manual
  doProbadorClaseChange, doProbadorOpChange, doProbadorParamChange,
  doProbadorParamSelect, doProbadorNumChange, doBuscarEnBD, doProbadorEjecutar,
};
