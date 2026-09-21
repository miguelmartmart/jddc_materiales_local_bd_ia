/**
 * api_clone.js v2 — API Clone: replica API Explorer + Probador Manual con datos reales.
 * Probador Manual: formulario dinámico, lookup de BD, badge de fiabilidad, SQL real visible.
 */
const API = "/api/api-clone";

let _state = {
  reportBusy: false, reportError: "",
  status: null, catalogue: null, currentTab: "status",
  selectedClase: null, browseResult: null, readResult: null,
  permisoResult: null, infoResult: null, discoverResult: null,
  history: [], matrix: {},
  browseParams: {}, browseNum: 20, readObjectid: "",
  // Utilidades de Ingeniería
  utilSelected: null,       // id de la utilidad seleccionada
  utilParams: {},           // params del formulario
  utilResultado: null,      // resultado de la última ejecución
  utilLookups: {},          // campo → valores BD (para lookups)
  utilCatalogo: null,       // catálogo de utilidades
  utilBusy: false,
  utilRequestId: 0,
  utilProjectLookup: null,
  utilLookupVersion: 0,
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
    ["utilidades","📐 Utilidades"],
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
      Datos obtenidos de Firebird. Su equivalencia con la API de Distrito K requiere validación independiente.
    </div>
    ${statusBar}
    <div style="padding:12px;background:#eff6ff;border-radius:8px;margin-bottom:12px">
      <button onclick="ApiCloneModule.doExportReport()" ${_state.reportBusy?'disabled':''} style="padding:10px;background:#0369a1;color:white;border:0;border-radius:6px;cursor:pointer">${_state.reportBusy?'Comprobando la base de datos…':'📄 Comprobar y exportar informe TXT'}</button>
      <button onclick="ApiCloneModule.setTab('utilidades');ApiCloneModule.doUtilSelect('verificacion-coherencia')" style="padding:10px;margin:4px">Ver comprobaciones y ayudas</button>
      <details><summary>¿Qué demuestra este informe?</summary><p>Ejecuta las comprobaciones globales disponibles y descarga sus SQL, contadores, incidencias y límites. Incluye pruebas pendientes. No certifica una fiabilidad del 100 %. Puede tardar al consultar toda la base.</p></details>
      <p role="status">${_checkText(_state.reportError)}</p>
      <small>Comprobaciones · versión 2026-09-21.2</small>
    </div>
    <div style="border-bottom:2px solid #e2e8f0;margin-bottom:12px">${tabBtns}</div>
    <div id="api-clone-tab">${_buildTab()}</div>
  </div>`;
}

function _buildTab() {
  switch (_state.currentTab) {
    case "status":    return _tabStatus();
    case "catalogo":  return _tabCatalogo();
    case "probador":  return _tabProbador();
    case "utilidades":return _tabUtilidades();
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
      en Firebird. La conexión correcta no certifica las reglas de negocio ni la equivalencia con Distrito K.
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

// ── Tab Utilidades de Ingeniería ──────────────────────────────────────────────
const UTIL_API = "/api/api-clone/utilidades";
async function _utilFetch(path, opts={}) {
  const res = await fetch(UTIL_API+path,{headers:{"Content-Type":"application/json"},...opts});
  if (!res.ok){const e=await res.json().catch(()=>({detail:res.statusText}));throw new Error(e.detail||`HTTP ${res.status}`);}
  return res.json();
}

// Metadatos de las 8 utilidades
const UTIL_META = {
  "horas-por-tecnico":{icon:"👷",titulo:"Técnicos y actividad registrada",
    desc:"¿Qué recursos aparecen en las líneas de esta obra? Separa registros y previsiones sin dar por verificadas las horas.",
    perfiles:["🏗️ <b>Ingenieros</b>: ver técnicos y carga","💰 <b>Gerencia</b>: coste MO","👷 <b>RRHH</b>: verificar imputación"],
    params:[{n:"cod_proyecto",label:"Código proyecto",tipo:"str",req:true,ejemplo:"45215",fk:"codProyecto",desc:"Código del proyecto en SQL Obras"},{n:"limit",label:"Máx técnicos",tipo:"int",req:false,default:20,desc:"Máximo de recursos mostrados por número de líneas"}],
    rkey:"tecnicos",nota:"Las referencias de técnicos se cuentan aunque la cantidad sea cero.",dato:"Las horas y los costes realizados necesitan una fórmula contrastada con SQL Obras."},
  "resumen-costes":{icon:"📊",titulo:"Resumen MO vs Materiales vs Subcontrata",
    desc:"¿En qué se ha gastado el dinero del proyecto? Desglose y margen real.",
    perfiles:["📊 <b>Dirección</b>: composición de costes","💰 <b>Gerencia</b>: margen real","🏗️ <b>Ingenieros</b>: intensidad MO/Mat"],
    params:[{n:"cod_proyecto",label:"Código proyecto",tipo:"str",req:true,ejemplo:"45215",fk:"codProyecto",desc:"El proyecto a analizar"}],
    rkey:"desglose",nota:"Consulta pendiente de validación de negocio — OBRALIN(TIPOBC3 10/20/30)+PROYECTOS.",dato:"Proyecto 45215: 732.496€ coste total"},
  "top-proyectos":{icon:"🏆",titulo:"Top proyectos por coste total",
    desc:"¿Cuáles son los proyectos más costosos de la empresa?",
    perfiles:["📊 <b>Dirección</b>: proyectos de mayor impacto","💰 <b>Gerencia</b>: priorizar control"],
    params:[{n:"limit",label:"Número de proyectos",tipo:"int",req:false,default:10,desc:"Top N proyectos"}],
    rkey:"proyectos",nota:"Consulta pendiente de validación de negocio — OBRALIN+PROYECTOS. 0 huérfanos.",dato:"#1 Proyecto 45215 'Palacio de Justicia Gandía' = 732.496€"},
  "ranking-tecnicos":{icon:"👷",titulo:"Ranking global de técnicos por horas",
    desc:"¿Quién trabaja más? ¿En cuántos proyectos? ¿Cuánto ha costado en total?",
    perfiles:["👷 <b>RRHH</b>: carga de trabajo","💰 <b>Gerencia</b>: coste total por técnico","🏗️ <b>Ingenieros</b>: técnicos más activos"],
    params:[{n:"limit",label:"Número de técnicos",tipo:"int",req:false,default:20,desc:"Top N técnicos"}],
    rkey:"tecnicos",nota:"Consulta pendiente de validación de negocio — OBRALIN(T=10) JOIN RECURSO. 307.049 líneas MO.",dato:"Técnico 84 'CONESA MARTINEZ' → top 1 en horas"},
  "proyectos-de-tecnico":{icon:"🗂️",titulo:"Proyectos de un técnico específico",
    desc:"¿En qué proyectos ha trabajado este técnico? ¿Cuántas horas en cada uno?",
    perfiles:["👷 <b>El técnico</b>: historial","🏗️ <b>Ingenieros</b>: experiencia","💰 <b>RRHH</b>: movilidad"],
    params:[{n:"cod_recurso",label:"Código técnico (número)",tipo:"int",req:true,ejemplo:"84",desc:"Código numérico del técnico en RECURSO. Úsalo del Ranking."},{n:"limit",label:"Máx proyectos",tipo:"int",req:false,default:20,desc:"Máx proyectos"}],
    rkey:"proyectos",nota:"✅ Muy fiable — OBRALIN(T=10)+PROYECTOS. cod_recurso=INTEGER.",dato:"Técnico 84 'CONESA MARTINEZ' → múltiples proyectos"},
  "materiales-proyecto":{icon:"📦",titulo:"Materiales de un proyecto",
    desc:"¿Qué materiales se han consumido más? ¿A qué coste?",
    perfiles:["🏗️ <b>Ingenieros</b>: consumo materiales","📦 <b>Compras</b>: materiales costosos","💰 <b>Gerencia</b>: coste vs presupuesto"],
    params:[{n:"cod_proyecto",label:"Código proyecto",tipo:"str",req:true,ejemplo:"45215",fk:"codProyecto",desc:"El proyecto a analizar"},{n:"limit",label:"Máx materiales",tipo:"int",req:false,default:20,desc:"Top N materiales por coste"}],
    rkey:"materiales",nota:"✅ Muy fiable — OBRALIN(TIPOBC3=20). 629.488 líneas materiales.",dato:"629.488 líneas de materiales en BD"},
  "evolucion-costes":{icon:"📈",titulo:"Evolución mensual de costes",
    desc:"¿Cómo han evolucionado los costes mes a mes? Curva de ejecución.",
    perfiles:["📊 <b>Dirección</b>: curva ejecución","💰 <b>Gerencia</b>: anticipar desviaciones","🏗️ <b>Ingenieros</b>: meses pico"],
    params:[{n:"cod_proyecto",label:"Código proyecto",tipo:"str",req:true,ejemplo:"45215",fk:"codProyecto",desc:"El proyecto a analizar"}],
    rkey:"evolucion_mensual",nota:"✅ Muy fiable — OBRALIN por EXTRACT(YEAR/MONTH FROM FECHA).",dato:"Datos desde 2022 hasta fecha actual"},
  "verificacion-coherencia":{icon:"🔍",titulo:"Verificación de coherencia y evidencias",
    desc:"Comprueba referencias, estados, cantidades y fechas con explicaciones paso a paso.",
    perfiles:["🔍 <b>Auditoría</b>: evidencias formales","📊 <b>Dirección</b>: validación independiente","🏗️ <b>Ingenieros</b>: garantía de fiabilidad"],
    params:[],
    rkey:"checks",nota:"Alcance global: estos checks no certifican una obra concreta.",dato:"Cada resultado explica qué se comprobó y qué queda por verificar."},
};

function _tabUtilidades() {
  const uid = _state.utilSelected;
  const meta = uid ? UTIL_META[uid] : null;
  const sidebar = Object.entries(UTIL_META).map(([id,m])=>{
    const act = id===uid;
    return `<div onclick="ApiCloneModule.doUtilSelect('${id}')"
      style="padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:4px;
      background:${act?'#0369a1':'transparent'};color:${act?'white':'#374151'};
      border:1px solid ${act?'#0369a1':'#e2e8f0'};transition:all 0.15s"
      onmouseover="if('${id}'!=='${uid||''}')this.style.background='#f1f5f9'"
      onmouseout="if('${id}'!=='${uid||''}')this.style.background='transparent'">
      <div style="font-weight:600;font-size:0.88em">${m.icon} ${m.titulo}</div>
      <div style="font-size:0.76em;opacity:0.8;margin-top:2px">${m.perfiles[0].replace(/<[^>]+>/g,'')}</div>
    </div>`;
  }).join("");
  let panel = `<div style="color:#94a3b8;padding:40px;text-align:center;border:2px dashed #e2e8f0;border-radius:10px">Selecciona una utilidad del panel izquierdo.</div>`;
  if (meta) {
    const badgeDatos = `<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:0.83em">
      <div style="font-weight:600;color:#92400e;margin-bottom:3px">📌 ${meta.nota}</div>
      <div style="color:#78350f">${['verificacion-coherencia','horas-por-tecnico'].includes(uid)?'':'Referencia anterior: '}${meta.dato}</div>
    </div>`;
    const paramsForm = (meta.params||[]).length===0
      ? `<div style="color:#94a3b8;font-style:italic;padding:8px;font-size:0.85em">Sin parámetros — ejecuta directamente.</div>`
      : (meta.params||[]).map(p=>{
          const val = _state.utilParams[p.n]!==undefined?_state.utilParams[p.n]:(p.default!==undefined?p.default:"");
          const lookups = _state.utilLookups[p.n]||[];
          return `<div style="border:1px solid ${p.req?'#fca5a5':'#e2e8f0'};border-radius:8px;padding:12px;margin-bottom:10px;background:${p.req?'#fff5f5':'white'}">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
              <label style="font-size:0.88em;font-weight:700;font-family:monospace">${p.label}${p.req?' <span style="color:#dc2626">*</span>':''}</label>
              <span style="font-size:0.75em;color:#64748b;background:#f1f5f9;padding:2px 6px;border-radius:4px">${p.tipo}</span>
            </div>
            <div style="font-size:0.82em;color:#374151;margin-bottom:6px">${p.desc}</div>
            <div style="display:flex;gap:6px;align-items:center">
              <input id="util-param-${p.n}" type="${p.tipo==='int'?'number':'text'}" value="${_checkText(val)}"
                placeholder="${p.ejemplo?'ej: '+p.ejemplo:p.default||''}"
                onchange="ApiCloneModule.doUtilParamChange('${p.n}',this.value)"
                style="flex:1;padding:7px 10px;border:1.5px solid #d1d5db;border-radius:6px;font-size:0.88em;font-family:monospace">
              ${p.fk?`<button onclick="ApiCloneModule.doUtilBuscarBD('${p.n}','${p.fk}')" title="Buscar en BD"
                style="padding:7px 12px;background:#0369a1;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.82em;white-space:nowrap">🔍 BD</button>`:''}
            </div>
            ${p.fk==='codProyecto'?_renderProjectLookup():''}
            ${lookups.length?`<div style="margin-top:6px;border:1px solid #bae6fd;border-radius:6px;background:#f0f9ff;max-height:160px;overflow-y:auto">
              <div style="padding:4px 8px;font-size:0.75em;font-weight:600;color:#0369a1;border-bottom:1px solid #bae6fd">Valores reales — clic para seleccionar:</div>
              ${lookups.map(v=>`<div onclick="ApiCloneModule.doUtilParamSelect('${p.n}','${v.id}')"
                style="padding:5px 10px;cursor:pointer;font-size:0.83em;font-family:monospace;border-bottom:1px solid #e0f2fe"
                onmouseover="this.style.background='#dbeafe'" onmouseout="this.style.background=''">
                <strong>${v.id}</strong>${v.desc&&v.desc!==v.id?` — <span style="color:#64748b">${v.desc}</span>`:''}</div>`).join('')}
            </div>`:''}
          </div>`;
        }).join("");
    const resHtml = _state.utilResultado ? _renderUtilResult(uid, _state.utilResultado, meta) : "";
    panel = `
      <h3 style="margin:0 0 6px;color:#0f172a;font-size:1em">${meta.icon} ${meta.titulo}</h3>
      <p style="margin:0 0 12px;font-size:0.88em;color:#374151">${meta.desc}</p>
      ${badgeDatos}
      <details style="margin-bottom:12px"><summary style="cursor:pointer;font-size:0.83em;font-weight:600;color:#0369a1">ℹ️ ¿Para quién es esta utilidad?</summary>
        <div style="margin-top:6px">${(meta.perfiles||[]).map(p=>`<div style="font-size:0.83em;margin-bottom:3px">${p}</div>`).join("")}</div>
      </details>
      <div style="margin-bottom:12px">
        <div style="font-size:0.85em;font-weight:600;color:#374151;margin-bottom:8px">Parámetros</div>
        ${paramsForm}
      </div>
      <button onclick="ApiCloneModule.doUtilEjecutar()"
        ${_state.utilBusy?'disabled aria-busy="true"':''}
        style="width:100%;padding:10px;background:#0369a1;color:white;border:none;border-radius:8px;cursor:pointer;font-size:0.9em;font-weight:700;margin-bottom:16px">
        ${_state.utilBusy?'Consultando datos…':'▶ Ejecutar '+meta.icon+' '+meta.titulo}</button>
      ${resHtml}`;
  }
  return `<div style="display:grid;grid-template-columns:280px 1fr;gap:16px">
    <div style="border-right:1px solid #e2e8f0;padding-right:12px">
      <div style="font-size:0.8em;font-weight:600;color:#64748b;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.05em">Utilidades disponibles</div>
      ${sidebar}
      <div style="margin-top:12px;font-size:0.76em;color:#94a3b8;background:#f8fafc;padding:8px;border-radius:6px">
        💡 Datos 100% reales de Firebird. CERO mocks.<br>OBRALIN · PROYECTOS · RECURSO
      </div>
    </div>
    <div>${panel}</div>
  </div>`;
}

function _checkText(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function _renderGroupedChecks(r) {
  const states = {
    correcto: {label:'Correcto',color:'#166534',icon:'✓'},
    revisar: {label:'Revisar',color:'#92400e',icon:'!'},
    no_verificable: {label:'No verificable',color:'#475569',icon:'?'},
    no_aplica: {label:'No aplica',color:'#475569',icon:'—'},
  };
  const badge = code => {const s=states[code]||states.no_verificable;return _badge(s.color,s.icon+' '+s.label);};
  const groups=Array.isArray(r.grupos)?r.grupos:[];
  if (!groups.length) return '<div role="status">No se recibió un informe con grupos de checks. Actualiza el backend y vuelve a ejecutar la comprobación.</div>';
  return `<section aria-label="Comprobaciones de datos" style="border:1px solid #cbd5e1;border-radius:10px;padding:16px;overflow-wrap:anywhere">
    <h3 style="margin-top:0">Resultado de las comprobaciones</h3>
    <p>${_checkText(r.alcance)}</p>
    <p role="status"><strong>${_checkText(r.veredicto)}</strong></p>
    <details style="margin-bottom:12px"><summary style="cursor:pointer;font-weight:600">¿Cómo interpretar los resultados?</summary>
      <p>${badge('correcto')} La regla indicada se cumple en los registros evaluados. No certifica todo el sistema.</p>
      <p>${badge('revisar')} Hay registros que necesitan revisión. Puede haber excepciones legítimas.</p>
      <p>${badge('no_verificable')} Falta una regla validada o no se pudo completar la consulta.</p>
      <p>${badge('no_aplica')} No hay registros que cumplan las condiciones de esta comprobación.</p>
    </details>
    ${groups.map(g=>{
      const checks=Array.isArray(g.checks)?g.checks:[];
      return `<details ${g.estado_codigo!=='correcto'?'open':''} style="border:1px solid #cbd5e1;border-radius:8px;padding:12px;margin-bottom:12px">
        <summary style="cursor:pointer;font-weight:700">${_checkText(g.nombre)} · ${checks.length} checks ${badge(g.estado_codigo)}</summary>
        <details style="margin:10px 0"><summary style="cursor:pointer">¿Qué comprueba este grupo?</summary><p>${_checkText(g.ayuda)}</p></details>
        ${checks.map(c=>`<article style="border-top:1px solid #e2e8f0;padding:12px 0">
          <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center"><strong>${_checkText(c.nombre)}</strong>${badge(c.estado_codigo)}</div>
          <p>${_checkText(c.detalle)}</p>
          <details><summary style="cursor:pointer;font-weight:600">¿Qué comprueba? Ayuda y ejemplo</summary>
            <p>${_checkText(c.descripcion)}</p><p><strong>Ejemplo:</strong> ${_checkText(c.ejemplo)}</p>
            <p><strong>Qué hacer:</strong> ${_checkText(c.accion)}</p>
          </details>
          ${c.sql?`<details style="margin-top:8px"><summary style="cursor:pointer">Detalle técnico (opcional)</summary>
            <p>${_checkText(c.id)} · Registros evaluados: ${_checkText(c.total_evaluado??'No disponible')} · Duración: ${_checkText(c.ms)} ms</p>
            <pre style="white-space:pre-wrap;background:#f8fafc;padding:8px">${_checkText(c.sql)}</pre></details>`:''}
        </article>`).join('')}
      </details>`;
    }).join('')}
    <p style="font-size:0.85em">${_checkText(r.nota)}</p>
    <p style="font-size:0.8em">Fecha de ejecución (UTC): ${_checkText(r.timestamp)} · ${_checkText(r.ms_total)} ms</p>
  </section>`;
}
function _renderProjectLookup() {
  const p=_state.utilProjectLookup;
  if(!p)return '';
  const rows=Array.isArray(p.valores)?p.valores:[];
  return `<section aria-label="Buscar proyecto" style="margin-top:10px;padding:12px;border:1px solid #bae6fd;border-radius:8px">
    <label for="ac-project-search">Buscar por código o nombre</label>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><input id="ac-project-search" value="${_checkText(p.q)}" oninput="ApiCloneModule.doProyectoQuery(this.value)" onkeydown="if(event.key==='Enter'){event.preventDefault();ApiCloneModule.doProyectoBuscar(0)}" style="flex:1;min-width:120px;padding:8px">
    <button onclick="ApiCloneModule.doProyectoBuscar(0)" ${p.loading?'disabled':''}>Buscar</button></div>
    <p role="status">${p.loading?'Consultando proyectos…':p.error?_checkText(p.error):`Mostrando ${rows.length?p.offset+1:0}–${p.offset+rows.length} de ${p.total} proyectos${p.busqueda?' para esta búsqueda':''}.`}</p>
    <div style="max-height:240px;overflow:auto">${rows.map(v=>`<button data-id="${_checkText(v.id)}" onclick="ApiCloneModule.doUtilParamSelect('cod_proyecto',this.dataset.id)" style="display:block;width:100%;text-align:left;padding:10px;margin-bottom:4px"><strong>${_checkText(v.id)}</strong> · ${_checkText(v.desc)} <span>${_checkText(v.estado)}</span></button>`).join('')}</div>
    ${!p.loading&&!p.error&&!rows.length?'<p>No se encontraron proyectos para esta búsqueda.</p>':''}
    <div style="display:flex;gap:8px"><button ${p.loading||!p.offset?'disabled':''} onclick="ApiCloneModule.doProyectoBuscar(${Math.max(0,p.offset-15)})">Anterior</button><button ${p.loading||!p.hay_mas?'disabled':''} onclick="ApiCloneModule.doProyectoBuscar(${p.offset+15})">Siguiente</button></div>
    <details><summary>¿Por qué aparecen proyectos finalizados?</summary><p>Se incluyen para consultar su histórico. El estado no demuestra que tengan líneas o que permitan registrar nuevos trabajos.</p></details>
  </section>`;
}
function doProyectoQuery(value){if(_state.utilProjectLookup)_state.utilProjectLookup.q=value;}
async function doProyectoBuscar(offset=0){
  const q=_state.utilProjectLookup?.q||'';
  const version=++_state.utilLookupVersion;
  _state.utilProjectLookup={q,offset,total:0,valores:[],loading:true};_render();
  try{
    const r=await _utilFetch(`/proyectos-buscar?q=${encodeURIComponent(q)}&offset=${offset}&limit=15`);
    if(version===_state.utilLookupVersion)_state.utilProjectLookup={...r,q,loading:false};
  }catch(e){if(version===_state.utilLookupVersion)_state.utilProjectLookup={q,offset,total:0,valores:[],loading:false,error:e.message};}
  if(version===_state.utilLookupVersion)_render();
}
function _renderProjectActivity(r){
  const a=r.actividad;
  if(!a)return '<p role="alert">Actualiza el backend para obtener el diagnóstico de actividad. Los contadores antiguos no permiten interpretar los ceros.</p>';
  const labels={correcto:'Correcto',revisar:'Revisar',no_verificable:'No verificable',no_aplica:'No aplica'};
  const rows=Array.isArray(r.tecnicos)?r.tecnicos:[];
  const columns={CODRECURSO:'Código recurso',TECNICO:'Recurso / técnico',LINEAS_REGISTRADAS:'Líneas registradas',LINEAS_NO_PREVISTAS:'No previstas',LINEAS_PREVISTAS:'Previstas'};
  return `<section style="border:1px solid #cbd5e1;border-radius:10px;padding:16px">
    <h3>Actividad del proyecto ${_checkText(r.cod_proyecto)}</h3><p>${_checkText(r.proyecto?.NOMBRE)}</p>
    <p role="status"><strong>${_checkText(r.mensaje)}</strong></p>
    ${a.LINEAS?`<dl style="display:flex;gap:18px;flex-wrap:wrap">${Object.entries({LINEAS:'Líneas vinculadas',MO:'Líneas de mano de obra',RECURSOS:'Recursos referenciados',MO_REAL:'Líneas no previstas',MO_PREVISTA:'Líneas previstas',MO_SIN_RECURSO:'Líneas MO sin recurso'}).map(([k,label])=>`<div><dt>${label}</dt><dd style="margin:0;font-weight:700">${_checkText(a[k])}</dd></div>`).join('')}</dl>`:''}
    <p><strong>Horas y costes realizados: no verificados.</strong></p>
    ${(r.grupos||[]).map(g=>`<details open style="border-top:1px solid #e2e8f0;padding:10px 0"><summary>${_checkText(g.nombre)} · ${labels[g.estado_codigo]||'No verificable'}</summary><p>${_checkText(g.detalle)}</p><details><summary>¿Qué significa? Ayuda</summary><p>${_checkText(g.ayuda)}</p></details></details>`).join('')}
    ${rows.length?`<p>Mostrando ${rows.length} de ${_checkText(a.RECURSOS)} recursos referenciados. No es una lista de personal asignado.</p>${_tabla(rows.map(row=>Object.fromEntries(Object.entries(columns).map(([k,label])=>[label,_checkText(row[k])]))))}`:''}
    ${!a.LINEAS?'<p>Usa «BD» para buscar otra obra por nombre o código. Si esperabas actividad aquí, contrasta este código con el parte de SQL Obras.</p>':''}
  </section>`;
}
function _renderUtilResult(uid, r, meta) {
  if (!r) return "";
  if (r.ok===false) return `<div style="background:#fef2f2;border-left:3px solid #dc2626;padding:12px;border-radius:6px;color:#dc2626">❌ ${_checkText(r.error)}</div>`;
  if (uid==="verificacion-coherencia") return _renderGroupedChecks(r);
  if (uid==="horas-por-tecnico") return _renderProjectActivity(r);
  if (uid==="resumen-costes"&&r.desglose) {
    const d=r.desglose,tot=r.totales||{},ct=tot.coste_total||0;
    const bar=(v)=>ct>0?Math.round((v||0)/ct*100):0;
    const fmt=(v)=>(v||0).toLocaleString('es-ES',{minimumFractionDigits:0,maximumFractionDigits:0});
    return `<div style="border:2px solid #16a34a;border-radius:10px;padding:16px">
      <div style="font-weight:700;margin-bottom:12px">${r.proyecto?.NOMBRE||r.cod_proyecto}</div>
      ${[["⏱️ MO",d.mano_obra,"#0369a1"],["📦 Mat",d.materiales,"#16a34a"],["🏭 Sub",d.subcontrata,"#ea580c"]].map(([lbl,s,c])=>
        `<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;margin-bottom:3px">
          <span style="font-size:0.85em;font-weight:600">${lbl}</span>
          <span style="font-size:0.85em;font-weight:600;color:${c}">${fmt(s.coste)} € (${s.pct_coste}%)</span></div>
          <div style="background:#e2e8f0;border-radius:4px;height:8px"><div style="background:${c};width:${bar(s.coste)}%;height:8px;border-radius:4px"></div></div>
          ${lbl.includes('MO')&&s.horas?`<div style="font-size:0.78em;color:#64748b">${(s.horas||0).toLocaleString()} horas</div>`:''}</div>`).join("")}
      <div style="border-top:2px solid #e2e8f0;padding-top:10px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div><div style="font-size:0.78em;color:#64748b">Coste</div><div style="font-weight:700">${fmt(ct)} €</div></div>
        <div><div style="font-size:0.78em;color:#64748b">Precio</div><div style="font-weight:700">${fmt(tot.precio_total)} €</div></div>
        <div><div style="font-size:0.78em;color:#64748b">Margen</div><div style="font-weight:700;color:${(tot.margen||0)>=0?'#16a34a':'#dc2626'}">${fmt(tot.margen)} € (${tot.pct_margen||0}%)</div></div>
        <div><div style="font-size:0.78em;color:#64748b">Técnicos</div><div style="font-weight:700">${tot.n_tecnicos||0}</div></div>
      </div></div>`;
  }
  return _renderUtilResultGenerico(uid, r, meta);
}
function _renderUtilResultGenerico(uid, r, meta) {
  if (uid==="evolucion-costes"&&r.evolucion_mensual) {
    const M=['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
    const fmt=(v)=>(v||0).toLocaleString('es-ES',{maximumFractionDigits:0});
    return `<div style="border:2px solid #16a34a;border-radius:10px;padding:16px">
      <div style="font-weight:700;margin-bottom:10px">📈 ${r.n_meses} meses</div>
      <div style="overflow-x:auto;max-height:350px;overflow-y:auto"><table style="width:100%;border-collapse:collapse;font-size:0.82em">
        <thead style="position:sticky;top:0;background:#f8fafc"><tr>${["Mes","MO","Mat","Sub","Total €","Horas"].map(h=>`<th style="padding:5px 8px;text-align:right;font-size:0.75em;color:#64748b;border-bottom:1px solid #e2e8f0">${h}</th>`).join("")}</tr></thead>
        <tbody>${r.evolucion_mensual.map(m=>`<tr>
          <td style="padding:5px 8px;font-weight:600">${M[parseInt(m.MES)]||m.MES} ${m.ANYO}</td>
          <td style="padding:5px 8px;text-align:right;color:#0369a1">${fmt(m.COSTE_MO)}</td>
          <td style="padding:5px 8px;text-align:right;color:#16a34a">${fmt(m.COSTE_MAT)}</td>
          <td style="padding:5px 8px;text-align:right;color:#ea580c">${fmt(m.COSTE_SUB)}</td>
          <td style="padding:5px 8px;text-align:right;font-weight:700">${fmt(m.COSTE_TOTAL)}</td>
          <td style="padding:5px 8px;text-align:right">${(m.HORAS_MO||0).toLocaleString('es-ES',{maximumFractionDigits:1})}</td>
        </tr>`).join("")}</tbody></table></div></div>`;
  }
  const items=r[meta?.rkey]||[];
  return `<div style="border:2px solid #16a34a;border-radius:10px;padding:16px">
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
      <strong style="color:#16a34a">✅ Datos reales Firebird</strong>${_badge("#16a34a",items.length+" reg")}
      <span style="font-size:0.82em;color:#64748b">${r.ms||0}ms | ${r.fuente||""}</span>
    </div>
    ${r.totales&&typeof r.totales==="object"?`<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px;background:#f8fafc;padding:8px 12px;border-radius:6px">
      ${Object.entries(r.totales).filter(([,v])=>v!=null&&typeof v!=="object").map(([k,v])=>`<div><div style="font-size:0.75em;color:#64748b">${k}</div><div style="font-weight:700;font-size:0.88em">${typeof v==="number"?v.toLocaleString('es-ES',{maximumFractionDigits:2}):v}</div></div>`).join("")}</div>`:""}
    ${items.length?_tabla(items):'<div style="color:#94a3b8;font-style:italic">Sin datos.</div>'}
    ${r.nota?`<div style="margin-top:8px;font-size:0.78em;color:#64748b;background:#f0f9ff;padding:6px 8px;border-radius:4px">ℹ️ ${r.nota}</div>`:""}
  </div>`;
}
function doUtilSelect(id){_state.utilLookupVersion++;_state.utilProjectLookup=null;_state.utilRequestId++;_state.utilBusy=false;_state.utilSelected=id;_state.utilParams={};_state.utilLookups={};_state.utilResultado=null;const m=UTIL_META[id];if(m?.params)m.params.forEach(p=>{if(p.default!==undefined)_state.utilParams[p.n]=p.default;});_render();}
function doUtilParamChange(campo,valor){_state.utilRequestId++;_state.utilBusy=false;_state.utilParams[campo]=valor;_state.utilResultado=null;_render();}
function doUtilParamSelect(campo,valor){_state.utilLookupVersion++;_state.utilProjectLookup=null;doUtilParamChange(campo,valor);_state.utilLookups[campo]=[];const version=_state.utilRequestId;_render();setTimeout(()=>{if(version===_state.utilRequestId)window.ApiCloneModule.doUtilEjecutar();},80);}
async function doUtilBuscarBD(campo,fk){if(fk==="codProyecto"){await doProyectoBuscar(0);return;}try{const r=await _fetch(`/valores-campo`,{method:"POST",body:JSON.stringify({campo:fk,limit:15})});_state.utilLookups[campo]=r.ok?r.valores:[];_render();}catch(e){console.error("[Utils] lookup:",e);}}
async function doUtilEjecutar(){
  const uid=_state.utilSelected; if(!uid||_state.utilBusy)return;
  const requestId=++_state.utilRequestId;
  const meta=UTIL_META[uid];
  (meta?.params||[]).forEach(p=>{const el=document.getElementById(`util-param-${p.n}`);if(el)_state.utilParams[p.n]=p.tipo==='int'?parseInt(el.value)||0:el.value;});
  const pm={..._state.utilParams};
  _state.utilResultado=null; _state.utilBusy=true; _render();
  try{
    let r;
    const GETS=["top-proyectos","ranking-tecnicos","verificacion-coherencia","catalogo"];
    if(GETS.includes(uid)){const qs=pm.limit?`?limit=${pm.limit}`:"";r=await _utilFetch(`/${uid}${qs}`);}
    else if(uid==="proyectos-de-tecnico"){r=await _utilFetch(`/${uid}`,{method:"POST",body:JSON.stringify({cod_recurso:parseInt(pm.cod_recurso)||0,limit:pm.limit||20})});}
    else{r=await _utilFetch(`/${uid}`,{method:"POST",body:JSON.stringify({cod_proyecto:pm.cod_proyecto||"",limit:pm.limit||20})});}
    if(requestId===_state.utilRequestId)_state.utilResultado=r;
  }catch(e){if(requestId===_state.utilRequestId)_state.utilResultado={ok:false,error:e.message};}
  if(requestId===_state.utilRequestId){_state.utilBusy=false;_render();}
}
// ── Tab Probador Manual — helpers ─────────────────────────────────────────────
function _fiabilidadBadge(f) {
  if (!f) return "";
  return `<div style="background:#fffbeb;padding:14px;margin-bottom:16px"><strong>Fiabilidad pendiente de contrastar</strong><p>La clave y la consulta SQL no certifican estados, fechas, filtros ni equivalencia con el ERP. Usa el informe de comprobaciones de la cabecera.</p><details><summary>SQL de referencia (no evidencia de ejecución)</summary><pre style="overflow:auto">${_checkText(f.sql_ejemplo||'No disponible')}</pre></details></div>`;
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

async function doExportReport() {
  if (_state.reportBusy) return;
  _state.reportBusy=true; _state.reportError=''; _render();
  try {
    const response=await fetch(API+'/utilidades/informe-fiabilidad.txt', {cache:'no-store'});
    if (!response.ok) throw new Error(response.status===404 ? 'Este backend no incluye el informe. Actualiza los archivos de Utilidades y reinicia DEVIA.' : `No se pudo generar el informe (HTTP ${response.status}).`);
    if (!(response.headers.get('content-type')||'').includes('text/plain')) throw new Error('El servidor no ha devuelto un informe TXT. Comprueba la versión instalada.');
    const content=await response.text();
    const url=URL.createObjectURL(new Blob(['\ufeff',content],{type:'text/plain;charset=utf-8'}));
    const link=document.createElement('a'); link.href=url; link.download='api-clone-fiabilidad-'+new Date().toISOString().replace(/[:.]/g,'-')+'.txt';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    _state.reportError='Informe generado. Revisa las incidencias y las pruebas no realizadas antes de interpretar los resultados.';
  } catch(e) { _state.reportError=e.message; }
  finally { _state.reportBusy=false; _render(); }
}

window.ApiCloneModule = {
  onEnter, setTab, doExportReport,
  doCargarCatalogo, doSeleccionarClase, doClaseChange, doClaseDetalle,
  doPermiso, doInfo, doBrowse, doRead, doDiscoverAll,
  doCargarHistorial, doLimpiarHistorial, setBrowseNum,
  // Probador Manual
  doProbadorClaseChange, doProbadorOpChange, doProbadorParamChange,
  doProbadorParamSelect, doProbadorNumChange, doBuscarEnBD, doProbadorEjecutar,
  // Utilidades de Ingeniería
  doProyectoQuery, doProyectoBuscar, doUtilSelect, doUtilParamChange, doUtilParamSelect, doUtilBuscarBD, doUtilEjecutar,
};
