 /**
 * api_explorer.js v15 — Plan de pruebas pendientes, segunda pasada en discover, hallazgos del servidor.
 * Explorador/Validador API Distrito K / SQL Obras (mPYME API 1.2).
 * MODO SOLO LECTURA por defecto.
 */
const API = "/api/api-explorer";

let _state = {
  status: null, config: null, catalogue: null,
  history: [], matrix: {}, currentTab: "conexion",
  selectedModulo: null, selectedClase: null, selectedOp: null,
  paramValues: {},
  loginMsg: null,
  catalogueFull: null,      // catálogo completo documentado (operaciones, campos, codigos)
  discoverResult: null,     // resultado del discover-all (permisos+info+browse reales)
  inspectorClase: null,     // clase seleccionada en el Inspector
  inspectorTab: "resumen",  // sub-pestaña del Inspector: resumen | clase | operaciones | codigos
};

async function _fetch(path, opts = {}) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function estadoIcon(e) {
  return { ok:"✅", falla:"❌", sin_permiso:"🔒", sin_licencia:"🚫", bloqueado:"⛔", no_probado:"⬜", precisa_params:"ℹ️" }[e] || "❓";
}
function estadoColor(e) {
  return { ok:"#28a745", falla:"#dc3545", sin_permiso:"#6c757d", sin_licencia:"#dc3545", bloqueado:"#fd7e14", precisa_params:"#0d6efd" }[e] || "#6c757d";
}

// ─── Renderizar datos de respuesta en tabla legible ───────────────────────────
function renderDatos(json, clase, op) {
  if (!json || !Object.keys(json).length) return "";
  const isMock = _state.status && _state.status.use_mock;

  // Banner indicador de origen de datos
  const origenBanner = isMock
    ? `<div style="background:#dbeafe;border-left:3px solid #3b82f6;padding:6px 12px;border-radius:4px;font-size:0.82em;color:#1d4ed8;margin-bottom:8px">
        🔵 <strong>Datos de BD Simulada</strong> — Estos son datos de ejemplo representativos basados en la documentacion de la API.
        No son datos reales de SQL Obras. Sirven para verificar el funcionamiento del modulo.
       </div>`
    : `<div style="background:#dcfce7;border-left:3px solid #16a34a;padding:6px 12px;border-radius:4px;font-size:0.82em;color:#166534;margin-bottom:8px">
        🟢 <strong>Datos de SQL Obras REAL</strong> — Estos datos provienen directamente de vuestra base de datos de produccion.
       </div>`;

  // Si tiene items (browse), renderizar tabla
  const items = json.items || json.data || json.fields;
  if (Array.isArray(items) && items.length > 0) {
    const keys = Object.keys(items[0]);
    const rows = items.map(item =>
      `<tr>${keys.map(k => `<td style="padding:5px 10px;border-bottom:1px solid #f1f5f9;font-size:0.85em">${item[k] ?? "—"}</td>`).join("")}</tr>`
    ).join("");
    return `${origenBanner}
      <div style="overflow-x:auto;border-radius:8px;border:1px solid #e2e8f0">
        <table style="width:100%;border-collapse:collapse;background:white">
          <thead style="background:#f8fafc">
            <tr>${keys.map(k => `<th style="padding:6px 10px;text-align:left;font-size:0.8em;color:#64748b;font-weight:600;border-bottom:1px solid #e2e8f0">${k}</th>`).join("")}</tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p style="color:#64748b;font-size:0.8em;margin-top:6px">${items.length} registro(s) ${json.total !== undefined ? `(total en BD: ${json.total})` : ""}</p>`;
  }

  // Si es un registro individual (read) o resultado de operacion
  const skip = ["code"];
  const displayKeys = Object.keys(json).filter(k => !skip.includes(k));
  if (displayKeys.length === 0) return origenBanner;

  const rows = displayKeys.map(k =>
    `<tr><td style="padding:5px 10px;font-size:0.85em;color:#64748b;font-weight:500;width:35%;background:#f8fafc;border-bottom:1px solid #f1f5f9">${k}</td>
     <td style="padding:5px 10px;font-size:0.85em;border-bottom:1px solid #f1f5f9">${typeof json[k] === "object" ? JSON.stringify(json[k]) : (json[k] ?? "—")}</td></tr>`
  ).join("");

  return `${origenBanner}
    <table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0">
      <tbody>${rows}</tbody>
    </table>`;
}

function renderResult(r) {
  const color = estadoColor(r.estado);
  const bg = r.estado === "ok" ? "#e8f5e9"
    : r.estado === "bloqueado" ? "#fff3e0"
    : r.estado === "precisa_params" ? "#dbeafe"
    : ["sin_permiso","sin_licencia"].includes(r.estado) ? "#f3e5f5"
    : "#ffebee";
  const modo = r.use_mock ? "🔵 Mock" : "🟠 Real";
  let html = `<div style="background:${bg};border-left:4px solid ${color};padding:10px 14px;border-radius:6px;margin:8px 0;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <strong>${estadoIcon(r.estado)} ${r.estado.toUpperCase()}</strong>
    <code style="background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:4px">${r.clase}.${r.operacion}</code>
    <span style="color:#64748b;font-size:0.85em">HTTP ${r.http_status ?? "—"} | code=${r.code ?? "—"} | ${r.duracion_ms}ms | ${modo}</span>
  </div>
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 14px;margin:6px 0;color:#374151">💬 ${r.mensaje}</div>`;

  if (r.nota_doc) html += `<p style="color:#64748b;font-size:0.82em;margin:4px 0">📖 <em>${r.nota_doc}</em></p>`;
  if (r.nota_seguridad) html += `<div style="background:#fff8e1;border:1px solid #ffc107;border-radius:6px;padding:8px 12px;margin:4px 0;color:#856404;font-size:0.85em">⚠️ ${r.nota_seguridad}</div>`;

  // Datos en tabla legible
  if (r.json && r.estado === "ok") {
    const datosHtml = renderDatos(r.json, r.clase, r.operacion);
    if (datosHtml) html += `<div style="margin-top:10px">${datosHtml}</div>`;
  }

  // JSON raw en collapsible
  if (r.json && Object.keys(r.json).length) {
    html += `<details style="margin-top:6px"><summary style="cursor:pointer;color:#64748b;font-size:0.82em;user-select:none">🔧 JSON raw (debug)</summary>
      <pre style="background:#1e293b;color:#e2e8f0;border-radius:6px;padding:12px;font-size:0.78em;overflow-x:auto;margin-top:6px">${JSON.stringify(r.json, null, 2)}</pre>
    </details>`;
  }
  return html;
}

// ─── Info por clase y operacion (tooltips) ────────────────────────────────────
const CLASE_INFO = {
  proyectos:  { emoji:"🏗️", desc:"Obras / Proyectos del ERP", detalle:"Browse lista los proyectos disponibles. Read devuelve detalle por codProyecto (ej: '25/184' = obra 184 del 2025)." },
  partidas:   { emoji:"📋", desc:"Capitulos/partidas de un proyecto", detalle:"Una obra se divide en partidas (capitulos). Necesitas codProyecto primero. Ej: '03.02' = Climatizacion subcap 2." },
  proordutil: { emoji:"⚡", desc:"Utilizados: costes REALES imputados al proyecto", detalle:"Clase clave. Registra materiales y mano de obra realmente consumidos en una obra/partida. new crea objeto temporal; write lo persiste; cancel descarta." },
  proordprev: { emoji:"📐", desc:"Previstos: costes estimados del proyecto", detalle:"Costes planificados (no reales). Similar a proordutil pero para previsiones." },
  reporden:   { emoji:"🔧", desc:"Ordenes de reparacion/mantenimiento", detalle:"Crear, listar y modificar ordenes de reparacion vinculadas a equipos." },
  repobjetos: { emoji:"⚙️", desc:"Equipos / objetos reparables", detalle:"Catalogo de equipos (maquinaria, unidades de clima...) que pueden tener ordenes de reparacion." },
  repinst:    { emoji:"🏢", desc:"Instalaciones donde estan los equipos", detalle:"Ubicaciones fisicas de los equipos." },
  tipostrabajo:{ emoji:"🏷️", desc:"Tipos de trabajo para reparaciones", detalle:"Catalogo: mantenimiento preventivo, averia, revision anual..." },
  repordutil: { emoji:"🔩", desc:"Materiales/horas usados en una reparacion", detalle:"Como proordutil pero para ordenes de reparacion." },
  articulos:  { emoji:"📦", desc:"Catalogo de articulos/materiales", detalle:"Todos los materiales disponibles. codArticulo se usa en proordutil.write." },
  recursos:   { emoji:"👷", desc:"Empleados, maquinaria y otros recursos", detalle:"Recursos imputables con distintas tarifas segun tipo de hora." },
  proveedores:{ emoji:"🏭", desc:"Catalogo de proveedores", detalle:"Util para filtrar documentos de compra." },
  clientes:   { emoji:"🤝", desc:"Catalogo de clientes", detalle:"Propietarios de los proyectos." },
  docalbcom:  { emoji:"📄", desc:"Albaranes de compra + imputaPro a proyectos", detalle:"imputaPro vincula una linea de albaran directamente a obra/partida como coste real. Documentado explicitamente." },
  docfaccom:  { emoji:"🧾", desc:"Facturas de compra + imputaPro a proyectos", detalle:"Igual que docalbcom para facturas. Documentado explicitamente." },
  docpedcom:  { emoji:"📝", desc:"Pedidos de compra (imputaPro incierto)", detalle:"⚠️ La documentacion usa 'previsiblemente' para pedidos. No confirmado. Verificar empiricamente." },
  ordenfab:   { emoji:"🏭", desc:"Ordenes de fabricacion (requiere licencia)", detalle:"Si no teneis el modulo de fabricacion, browse devolvera sin_licencia." },
};
const OP_INFO = {
  browse:    "Listar registros. Devuelve lista con filtros opcionales.",
  read:      "Leer un registro especifico por su codigo.",
  permiso:   "Auditar permisos del usuario API en esta clase. Fundamental para conocer la licencia.",
  info:      "Metadatos de campos: tipos, nombres, descripciones.",
  new:       "🟡 Crea objeto TEMPORAL en sesion. No persiste hasta write. Seguro para ensayar.",
  edit:      "🟡 Igual que new pero para editar un registro existente.",
  write:     "🟠 ESCRITURA REAL. Persiste el objeto temporal en SQL Obras. Irreversible.",
  cancel:    "🟢 Descarta objeto temporal. No persiste nada. Siempre seguro.",
  imputaPro: "🟠 Vincula linea de compra directamente a proyecto/partida como coste real.",
  delete:    "🔴 ELIMINA un registro definitivamente del ERP.",
};

function infoClase(clase) {
  const i = CLASE_INFO[clase]; if(!i) return "";
  return `<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:0.85em">
    <span style="font-size:1.2em">${i.emoji}</span> <strong>${clase}</strong> — ${i.desc}
    <br><span style="color:#64748b;margin-top:4px;display:block">${i.detalle}</span>
  </div>`;
}
function infoOp(op) {
  const d = OP_INFO[op]; if(!d) return "";
  return `<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:0.83em;color:#475569">${d}</div>`;
}

const PARAMS_DB = {
  "proyectos.browse":  [{n:"filtro",t:"text",ph:"Hospital",desc:"Texto libre"},{n:"pagina",t:"number",ph:"1",desc:"Pagina"}],
  "proyectos.read":    [{n:"codProyecto",t:"text",ph:"25/184",req:true,desc:"Codigo del proyecto"}],
  "partidas.browse":   [{n:"codProyecto",t:"text",ph:"25/184",req:true,desc:"Proyecto"}],
  "partidas.read":     [{n:"codProyecto",t:"text",req:true,desc:"Proyecto"},{n:"codPartida",t:"text",ph:"03.02",req:true,desc:"Partida"}],
  "proordutil.browse": [{n:"codProyecto",t:"text",ph:"25/184",req:true,desc:"Proyecto"},{n:"codPartida",t:"text",ph:"03.02",desc:"Partida (opcional)"}],
  "proordutil.read":   [{n:"codDocumento",t:"text",ph:"U-001",req:true,desc:"Codigo utilizado"}],
  "proordutil.new":    [{n:"codProyecto",t:"text",ph:"25/184",req:true,desc:"Proyecto destino"},{n:"codPartida",t:"text",ph:"03.02",req:true,desc:"Partida destino"},{n:"tipo",t:"select",opts:["M","R"],req:true,desc:"M=Material  R=Recurso/mano de obra"}],
  "proordutil.write":  [{n:"objectId",t:"text",req:true,desc:"ID temporal de new"},{n:"codArticulo",t:"text",ph:"1#100142",req:true,desc:"Codigo articulo/recurso"},{n:"cantidad",t:"number",ph:"2",req:true,desc:"Cantidad"},{n:"coste",t:"number",ph:"35.10",req:true,desc:"Coste unitario euros"},{n:"precio",t:"number",ph:"42.00",desc:"Precio venta"},{n:"fecha",t:"text",ph:"20260901",desc:"Fecha AAAAMMDD"}],
  "proordutil.cancel": [{n:"objectId",t:"text",req:true,desc:"ID temporal a descartar"}],
  "reporden.browse":   [{n:"estado",t:"select",opts:["","abierta","cerrada","todas"],desc:"Estado"},{n:"pagina",t:"number",ph:"1",desc:"Pagina"}],
  "reporden.read":     [{n:"codOrden",t:"text",req:true,desc:"Codigo orden"}],
  "repordutil.browse": [{n:"codOrden",t:"text",req:true,desc:"Orden de reparacion"}],
  "repordutil.write":  [{n:"objectId",t:"text",req:true,desc:"ID temporal"},{n:"codRecurso",t:"text",req:true,desc:"Articulo/recurso"},{n:"cantidad",t:"number",req:true,desc:"Cantidad/horas"},{n:"coste",t:"number",req:true,desc:"Coste"},{n:"precio",t:"number",desc:"Precio"},{n:"fecha",t:"text",ph:"20260901",desc:"Fecha AAAAMMDD"}],
  "articulos.browse":  [{n:"filtro",t:"text",ph:"Tubo cobre",desc:"Buscar en catalogo"},{n:"pagina",t:"number",ph:"1",desc:"Pagina"}],
  "articulos.read":    [{n:"codArticulo",t:"text",req:true,desc:"Codigo articulo"}],
  "recursos.browse":   [{n:"filtro",t:"text",desc:"Buscar recursos"}],
  "proveedores.browse":[{n:"filtro",t:"text",ph:"Daikin",desc:"Filtrar"}],
  "clientes.browse":   [{n:"filtro",t:"text",desc:"Filtrar clientes"}],
  "docalbcom.browse":  [{n:"proveedor",t:"text",ph:"Daikin",desc:"Filtrar por proveedor"},{n:"pagina",t:"number",ph:"1",desc:"Pagina"}],
  "docalbcom.read":    [{n:"codDocumento",t:"text",req:true,desc:"Codigo albaran"}],
  "docalbcom.imputaPro":[{n:"codDocumento",t:"text",req:true,desc:"Codigo albaran"},{n:"codLinea",t:"text",req:true,desc:"Numero de linea"},{n:"codMaestro",t:"text",ph:"25/184",req:true,desc:"Proyecto destino"},{n:"codDetalle",t:"text",ph:"03.02",req:true,desc:"Partida destino"},{n:"subcontrata",t:"select",opts:["T","F"],req:true,desc:"T=subcontrata F=no"}],
  "docfaccom.browse":  [{n:"proveedor",t:"text",desc:"Filtrar"},{n:"pagina",t:"number",ph:"1",desc:"Pagina"}],
  "docfaccom.read":    [{n:"codDocumento",t:"text",req:true,desc:"Codigo factura"}],
  "docfaccom.imputaPro":[{n:"codDocumento",t:"text",req:true,desc:"Factura"},{n:"codLinea",t:"text",req:true,desc:"Linea"},{n:"codMaestro",t:"text",req:true,desc:"Proyecto"},{n:"codDetalle",t:"text",req:true,desc:"Partida"},{n:"subcontrata",t:"select",opts:["T","F"],req:true,desc:"T/F"}],
  "docpedcom.browse":  [{n:"pagina",t:"number",ph:"1",desc:"Pagina"}],
  "docpedcom.imputaPro":[{n:"codDocumento",t:"text",req:true,desc:"Pedido"},{n:"codLinea",t:"text",req:true,desc:"Linea"},{n:"codMaestro",t:"text",req:true,desc:"Proyecto"},{n:"codDetalle",t:"text",req:true,desc:"Partida"},{n:"subcontrata",t:"select",opts:["T","F"],req:true,desc:"T/F"}],
};

function renderParamFields(clase, op) {
  const fields = PARAMS_DB[`${clase}.${op}`] || [];
  if (!fields.length) return "";
  return fields.map(f => {
    const lbl = f.req
      ? `<span style="color:#dc3545;font-weight:600">* ${f.n}</span>`
      : `<span style="color:#374151">${f.n}</span>`;
    const descHtml = f.desc ? `<span style="color:#94a3b8;font-size:0.78em;margin-left:4px"> — ${f.desc}</span>` : "";
    const saved = _state.paramValues[f.n] || "";
    if (f.t === "select")
      return `<div><label style="display:block;font-size:0.82em;margin-bottom:3px">${lbl}${descHtml}</label>
        <select id="ae-p-${f.n}" class="form-control" style="width:100%">
          ${(f.opts||[]).map(o=>`<option value="${o}" ${saved===o?'selected':''}>${o||'(ninguno)'}</option>`).join('')}
        </select></div>`;
    return `<div><label style="display:block;font-size:0.82em;margin-bottom:3px">${lbl}${descHtml}</label>
      <input id="ae-p-${f.n}" type="${f.t}" class="form-control" placeholder="${f.ph||''}" value="${saved}" style="width:100%"></div>`;
  }).join('');
}

function collectParams(clase, op) {
  const fields = PARAMS_DB[`${clase}.${op}`] || [];
  const params = {};
  fields.forEach(f => {
    const el = document.getElementById(`ae-p-${f.n}`);
    if (el && el.value !== "") {
      params[f.n] = f.t === "number" ? parseFloat(el.value) : el.value;
      _state.paramValues[f.n] = el.value;
    }
  });
  return params;
}

// ─── Render Main ─────────────────────────────────────────────────────────────
function renderMain() {
  const root = document.getElementById("api-explorer-root");
  if (!root) return;
  const s = _state.status || { session_active:false, use_mock:true, modo_escritura:false, empresa:"", usuario:"", ssid1_masked:"", ssid2_masked:"" };
  const modoBanner = s.modo_escritura
    ? `<div style="background:#fff3e0;border-left:5px solid #fd7e14;padding:10px 16px;border-radius:4px;margin-bottom:12px;font-weight:600;font-size:0.9em">⚠️ MODO ESCRITURA ACTIVO — Las operaciones pueden modificar SQL Obras permanentemente</div>`
    : `<div style="background:#dcfce7;border-left:5px solid #28a745;padding:10px 16px;border-radius:4px;margin-bottom:12px;font-weight:600;font-size:0.9em">🟢 MODO SOLO LECTURA — Sin riesgo de modificar datos</div>`;

  const mockBanner = s.use_mock && s.session_active
    ? `<div style="background:#dbeafe;border-left:4px solid #3b82f6;padding:8px 14px;border-radius:4px;margin-bottom:10px;font-size:0.85em;color:#1d4ed8">🔵 <strong>BD Simulada activa</strong> — Los resultados son datos de ejemplo representativos, NO datos reales de SQL Obras. Sirven para probar el funcionamiento del modulo.</div>`
    : (!s.use_mock && s.session_active
      ? `<div style="background:#dcfce7;border-left:4px solid #16a34a;padding:8px 14px;border-radius:4px;margin-bottom:10px;font-size:0.85em;color:#166534">🟢 <strong>API Real conectada</strong> — Los datos que ves son REALES de SQL Obras.</div>`
      : "");

  const TABS = [["conexion","🔌 Conexion"],["inspector","🔍 Inspector API"],["explorador","⚙️ Explorador"],["probador","🧪 Probador"],["permisos","📋 Permisos"],["matriz","📊 Matriz"],["historial","📜 Historial"],["escritura","🟠 Escritura"]];
  const tabBar = `<div style="display:flex;gap:2px;margin-bottom:18px;border-bottom:2px solid #e2e8f0;flex-wrap:wrap">
    ${TABS.map(([id,lbl])=>`<button onclick="ApiExplorerModule.setTab('${id}')" style="padding:8px 14px;border:none;background:${_state.currentTab===id?'#3b82f6':'transparent'};color:${_state.currentTab===id?'white':'#64748b'};border-radius:6px 6px 0 0;cursor:pointer;font-size:0.88em;font-weight:${_state.currentTab===id?'600':'400'};transition:all 0.15s">${lbl}</button>`).join('')}
  </div>`;

  root.innerHTML = modoBanner + mockBanner + tabBar + `<div id="ae-tab-content">${renderTab(s)}</div>`;
}

function renderTab(s) {
  const cfg = _state.config || {};
  const cat = _state.catalogue;
  const catalogue = cat ? cat.catalogue : {};
  const modulos = Object.keys(catalogue);
  const mod = _state.selectedModulo || modulos[0] || "";
  const clases = catalogue[mod] || {};
  const cls = _state.selectedClase || Object.keys(clases)[0] || "";
  const RIESGO = {browse:0,read:0,permiso:0,info:0,new:1,edit:1,cancel:1,write:2,imputaPro:2,exec:2,delete:3};
  const opsAll = clases[cls] || [];
  const ops = s.modo_escritura ? opsAll : opsAll.filter(o=>(RIESGO[o]||0)<2);
  const op = _state.selectedOp || ops[0] || "";
  const riesgo = RIESGO[op]||0;
  const RLBL = ["🟢 Solo lectura","🟡 Preparacion (sin riesgo)","🟠 ESCRITURA REAL","🔴 DESTRUCTIVO"];
  const hist = _state.history;
  const mat = _state.matrix;
  const permisoR = {}; hist.forEach(r=>{if(r.operacion==="permiso")permisoR[r.clase]=r;});
  const ops_cols = ["browse","read","new","write","cancel","imputaPro"];
  const CLASSES = ["proyectos","partidas","proordutil","proordprev","reporden","repobjetos","repinst","tipostrabajo","repordutil","articulos","recursos","proveedores","clientes","docalbcom","docfaccom","docpedcom","ordenfab"];
  const resumen = {total:hist.length,ok:0,falla:0,sin_permiso:0,sin_licencia:0,bloqueado:0};
  hist.forEach(r=>{if(resumen[r.estado]!==undefined)resumen[r.estado]++;});

  if (_state.currentTab === "conexion") return renderConexion(s, cfg);
  if (_state.currentTab === "inspector") return renderInspector(s);
  if (_state.currentTab === "explorador") return renderExplorador(s, modulos, mod, clases, cls, ops, op, riesgo, RLBL);
  if (_state.currentTab === "probador") return renderProbador(s);
  if (_state.currentTab === "permisos") return !s.session_active ? noSesion() : renderPermisos(CLASSES, ops_cols, permisoR);
  if (_state.currentTab === "matriz") return renderMatriz(catalogue, mat);
  if (_state.currentTab === "historial") return renderHistorial(hist, resumen);
  if (_state.currentTab === "escritura") return renderEscritura(s);
  return "";
}

const noSesion = () => `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:20px;text-align:center;color:#92400e">⚠️ Conectate primero en la pestana <strong>Conexion</strong>.</div>`;


// =============================================================
// PROBADOR VISUAL -- prueba todas las clases con acordeón
// =============================================================
const _ECFG = {
  ok:              {sym:"✅", label:"Funciona",         color:"#166534", bg:"#dcfce7", border:"#86efac"},
  requiere_params: {sym:"🔵", label:"Necesita ID real",  color:"#1e40af", bg:"#dbeafe", border:"#93c5fd"},
  sin_licencia:    {sym:"🚫", label:"Sin licencia",       color:"#991b1b", bg:"#fef2f2", border:"#fca5a5"},
  sin_permiso:     {sym:"🔒", label:"Sin permiso",        color:"#374151", bg:"#f8fafc", border:"#cbd5e1"},
  config_incompleta:{sym:"⚠️",label:"Config incompleta", color:"#92400e", bg:"#fef9c3", border:"#fde047"},
  error:           {sym:"❌", label:"Error",              color:"#991b1b", bg:"#fef2f2", border:"#fca5a5"},
  bloqueado:       {sym:"⛔", label:"Escritura bloq.",   color:"#92400e", bg:"#fff7ed", border:"#fed7aa"},
  pendiente:       {sym:"⬜", label:"Sin probar",         color:"#64748b", bg:"#f8fafc", border:"#e2e8f0"},
};
const _OPDESC = {
  browse:    {riesgo:0,label:"Listar registros",   rl:"Solo lectura",
              desc:"Devuelve lista de registros. Puede necesitar filtros (codProyecto, codOrden...)."},
  read:      {riesgo:0,label:"Leer uno",           rl:"Solo lectura",
              desc:"Lee un registro concreto por su código identificador único."},
  permiso:   {riesgo:0,label:"Ver permisos",       rl:"Solo lectura",
              desc:"Audita qué operaciones permite la licencia para esta clase."},
  info:      {riesgo:0,label:"Ver campos",         rl:"Solo lectura",
              desc:"Devuelve metadatos: nombres y tipos de todos los campos del objeto."},
  new:       {riesgo:1,label:"Crear temporal",     rl:"Preparación (sin riesgo)",
              desc:"Crea un objeto TEMPORAL en sesión. No persiste hasta write. Cancel lo descarta."},
  edit:      {riesgo:1,label:"Editar temporal",    rl:"Preparación (sin riesgo)",
              desc:"Igual que new pero sobre un registro existente."},
  cancel:    {riesgo:0,label:"Cancelar temporal",  rl:"Solo lectura",
              desc:"Descarta el objeto temporal. Siempre seguro. No modifica nada."},
  write:     {riesgo:2,label:"Guardar (REAL)",     rl:"ESCRITURA REAL",
              desc:"PERSISTE en SQL Obras. Irreversible. Requiere activar modo escritura."},
  imputaPro: {riesgo:2,label:"ImputaPro (REAL)",   rl:"ESCRITURA REAL",
              desc:"Vincula compra a proyecto como coste real. ESCRITURA en SQL Obras."},
  delete:    {riesgo:3,label:"Eliminar (DESTR.)",  rl:"DESTRUCTIVO",
              desc:"Elimina definitivamente. Solo en entorno de pruebas."},
};
const _CODEEXP = {
  "0":"Éxito — operación completada correctamente.",
  "1":"Sin licencia — módulo no contratado. Contactar Distrito K.",
  "2":"Sin permiso de usuario — pedir al admin SQL Obras.",
  "3":"Error de validación — un parámetro tiene formato incorrecto.",
  "5":"Config incompleta — empresa/usuario incorrectos en .env.",
  "6":"Requiere identificador — necesita codProyecto, codOrden u otro ID.",
  "10":"No encontrado — el registro con ese ID no existe.",
  "20":"objectId inválido — objeto temporal expirado o ya guardado.",
  "-1":"Error de red — no se pudo conectar al servidor mPYME.",
  "-99":"Bloqueado — escritura desactivada.",
};
const _CAMPOEXP = {
  CODPROYE:"Código del proyecto (ej: 26/001)",DENOMINACION:"Nombre del proyecto",
  CODORDEN:"Código de la orden de reparación",CODRECURSO:"Código del recurso",
  CODPARTIDA:"Código de la partida",CODARTICULO:"Código del artículo/material",
  CANTIDAD:"Cantidad usada o prevista",COSTE:"Coste unitario",
  PRECIO:"Precio de venta unitario",ESTADO:"Estado (A=activo, C=cerrado...)",
  FECHA:"Fecha del registro",NOMBRE:"Nombre del elemento",DESCRIPCION:"Descripción larga",
};
let _probRes = {};   // {clase+"."+op: resultado backend}
let _probLoad = {};  // {clase: bool cargando}




// ── Metadatos de parámetros con descripción doble nivel ──────────────────────
const _PARAM_INFO = {
  codProyecto:{tec:"ID único proyecto. Formato año/número.",emp:"Código de la obra en SQL Obras. Lo ves junto al nombre de la obra.",ej:"26/001"},
  codOrden:{tec:"ID orden de reparación.",emp:"Número de la orden de avería o mantenimiento en el módulo SAT.",ej:"REP-2026-001"},
  codPartida:{tec:"Capítulo presupuestario del proyecto.",emp:"Partida del presupuesto (ej: 03.02 = Climatización subcap 2).",ej:"03.02"},
  codArticulo:{tec:"Referencia artículo en catálogo.",emp:"Referencia del material. La encuentras en el catálogo de artículos.",ej:"1#100142"},
  codRecurso:{tec:"ID del recurso (empleado/maquinaria).",emp:"Código del instalador o técnico. En la ficha del empleado.",ej:"R-INST01"},
  codDocumento:{tec:"ID del documento de compra.",emp:"Número del albarán o factura tal como aparece en SQL Obras.",ej:"ALB-2026-0101"},
  objectId:{tec:"ID temporal de la op 'new'. Usar en write/cancel.",emp:"Número temporal al preparar una entrada. Úsalo para guardar o cancelar.",ej:"TMP_A1B2"},
  codLinea:{tec:"Nº de línea dentro del documento. Base 1.",emp:"Línea del albarán o factura que quieres imputar a la obra.",ej:"1"},
  codMaestro:{tec:"Proyecto destino en imputaPro.",emp:"Obra a la que se cargará el gasto del albarán/factura.",ej:"26/001"},
  codDetalle:{tec:"Partida destino en imputaPro.",emp:"Partida de la obra donde se registrará el gasto.",ej:"03.02"},
  filtro:{tec:"Texto libre para filtrar por nombre.",emp:"Escribe parte del nombre que buscas, ej: 'Hospital'.",ej:"Hospital"},
  pagina:{tec:"Número de página para paginación. Base 1.",emp:"Si hay muchos resultados, usa página 2, 3...",ej:"1"},
  estado:{tec:"Filtro de estado según mPYME.",emp:"abierta = en curso, cerrada = terminada, todas = sin filtro.",ej:"abierta"},
  tipo:{tec:"Tipo de línea: M=Material, R=Recurso.",emp:"M = material o producto · R = mano de obra de un operario.",ej:"M"},
  cantidad:{tec:"Cantidad numérica (unidades o horas).",emp:"Cuántas unidades del material o cuántas horas trabajó el operario.",ej:"2.5"},
  coste:{tec:"Coste unitario en euros.",emp:"Precio de coste de cada unidad o de cada hora de trabajo.",ej:"35.10"},
  precio:{tec:"Precio de venta unitario en euros.",emp:"Precio al que se factura al cliente (0 si no corresponde).",ej:"42.00"},
  fecha:{tec:"Fecha formato AAAAMMDD sin separadores.",emp:"Fecha: año+mes+día sin guiones. Ej: 20260915 = 15 sept 2026.",ej:"20260915"},
  subcontrata:{tec:"T=subcontrata / F=no subcontrata.",emp:"¿Es una compra a empresa subcontratada? T=Sí, F=No.",ej:"F"},
};
const _PARAMS_CON_BD = new Set(["codProyecto","codOrden","codRecurso","codObjeto","codInst","codTrabajo","codArticulo","codProv","codCliente","codDocumento","codPartida"]);


// ─── Base de conocimiento por clase ─────────────────────────────────────────
const _CF = {
  proyectos:{
    flujo:"browse() \u2192 codProyecto \u2192 partidas / proordutil",
    casos:["Dashboard obras activas","Buscar c\u00f3digo antes de imputar","Estado: activa/cerrada/presupuesto"],
    gerente:"Todas las obras: cliente, importe previsto vs real, estado.",
    campos:{codProyecto:"C\u00f3digo \u00fanico (ej: 26/001)",descripcion:"Nombre de la obra",estado:"activo/cerrado/presupuesto",cliente:"Empresa contratante",importePrevisto:"Presupuesto \u20ac",importeRealizado:"Coste real \u20ac"},
    rel:["partidas","proordutil","proordprev","docalbcom"]},
  partidas:{
    flujo:"proyectos.browse \u2192 partidas.browse(codProyecto) \u2192 codPartida",
    casos:["Ver cap\u00edtulos antes de imputar","Control gasto por cap\u00edtulo","Verificar partida"],
    gerente:"Divisi\u00f3n presupuestaria por cap\u00edtulos. Comparar previsto vs real.",
    campos:{codPartida:"C\u00f3digo cap\u00edtulo (ej: 03.02)",descripcion:"Nombre cap\u00edtulo",importePrevisto:"Presupuesto partida",importeRealizado:"Coste real partida"},
    rel:["proyectos","proordutil","proordprev"]},
  proordutil:{
    flujo:"proyectos\u2192partidas\u2192articulos \u2192 new() \u2192 write() \u2192 PERSISTIDO EN ERP",
    casos:["App operario: imputar horas desde m\u00f3vil","Registro diario materiales","Cierre partes de trabajo"],
    gerente:"CLAVE: cada registro = material u hora imputada. Sin esto el ERP no sabe el coste real.",
    campos:{codProyecto:"Obra destino",codPartida:"Cap\u00edtulo destino",codArticulo:"Material o recurso",cantidad:"Unidades o horas",coste:"Coste unitario (\u20ac)",tipo:"M=Material / R=Recurso"},
    rel:["proyectos","partidas","articulos","recursos"]},
  proordprev:{
    flujo:"proyectos.browse \u2192 proordprev.browse(codProyecto) \u2192 comparar con proordutil",
    casos:["Dashboard previsto vs real","Alerta si desviaci\u00f3n >10%","Informe mensual"],
    gerente:"Presupuesto interno por cap\u00edtulo. Comparado con utilizados = desviaci\u00f3n.",
    campos:{codProyecto:"Obra",codPartida:"Cap\u00edtulo",codArticulo:"Material previsto",cantidad:"Cantidad prevista",coste:"Coste previsto"},
    rel:["proyectos","partidas","proordutil"]},
  reporden:{
    flujo:"browse(abierta) \u2192 read(codOrden) \u2192 repordutil.browse \u2192 write(cerrada)",
    casos:["App SAT: ver \u00f3rdenes del t\u00e9cnico","Dashboard aver\u00edas abiertas","Notificaci\u00f3n +48h"],
    gerente:"Gesti\u00f3n servicio t\u00e9cnico: aver\u00edas, t\u00e9cnico asignado, tiempo resoluci\u00f3n.",
    campos:{codOrden:"N\u00famero orden",estado:"abierta/en_proceso/cerrada",codObjeto:"Equipo averiado",tecnico:"T\u00e9cnico asignado",fechaApertura:"Fecha apertura"},
    rel:["repobjetos","repinst","repordutil","tipostrabajo"]},
  repobjetos:{
    flujo:"browse \u2192 filtrar por instalaci\u00f3n \u2192 reporden.browse(codObjeto)",
    casos:["Inventario digital equipos","Historial aver\u00edas por equipo","Detectar equipos con m\u00e1s incidencias"],
    gerente:"Inventario activos mantenibles. Cu\u00e1les dan m\u00e1s aver\u00edas y cu\u00e1nto cuestan.",
    campos:{codObjeto:"C\u00f3digo del equipo",descripcion:"Nombre",codInst:"Instalaci\u00f3n",marca:"Fabricante",modelo:"Modelo",numSerie:"N\u00famero de serie"},
    rel:["repinst","reporden"]},
  repinst:{
    flujo:"browse \u2192 repobjetos.browse(codInst) \u2192 reporden",
    casos:["Lista instalaciones cliente","Mapa cobertura t\u00e9cnica","Asignaci\u00f3n t\u00e9cnicos por zona"],
    gerente:"Instalaciones atendidas: cu\u00e1ntas hay, cu\u00e1les tienen m\u00e1s incidencias.",
    campos:{codInst:"C\u00f3digo instalaci\u00f3n",descripcion:"Nombre",direccion:"Direcci\u00f3n",cliente:"Empresa propietaria"},
    rel:["repobjetos","reporden"]},
  tipostrabajo:{
    flujo:"browse \u2192 elegir tipo \u2192 reporden.new(tipo)",
    casos:["Desplegable al crear orden","% correctivo vs preventivo","Facturaci\u00f3n por tipo"],
    gerente:"Clasifica el trabajo: aver\u00eda (reactivo/caro) vs preventivo (m\u00e1s barato).",
    campos:{codTrabajo:"C\u00f3digo",descripcion:"Nombre del tipo"},
    rel:["reporden"]},
  repordutil:{
    flujo:"reporden.browse \u2192 codOrden \u2192 new() \u2192 write() \u2192 PERSISTIDO",
    casos:["App SAT: registrar piezas y horas","Facturaci\u00f3n autom\u00e1tica","Coste real de reparaci\u00f3n"],
    gerente:"Coste real de cada reparaci\u00f3n: piezas, mano de obra. \u00bfReparar o sustituir?",
    campos:{codOrden:"Orden de reparaci\u00f3n",codRecurso:"Art\u00edculo o recurso",tipo:"M=Material / R=Recurso",cantidad:"Cantidad/horas",coste:"Coste unitario"},
    rel:["reporden","articulos","recursos"]},
  articulos:{
    flujo:"browse(filtro) \u2192 read(codArticulo) \u2192 usar en proordutil/repordutil.write()",
    casos:["Autocompletado materiales","B\u00fasqueda por nombre","Control stock","Precio coste"],
    gerente:"Cat\u00e1logo materiales con precios, stock y proveedor.",
    campos:{codArticulo:"Referencia (ej: 1#100142)",descripcion:"Nombre",familia:"Categor\u00eda",unidad:"Unidad medida",precioCoste:"Coste unitario",precioVenta:"Precio venta",stock:"Existencias"},
    rel:["proordutil","repordutil","proveedores"]},
  recursos:{
    flujo:"browse \u2192 codRecurso \u2192 proordutil.new(tipo=R) \u2192 write(codRecurso, horas)",
    casos:["Selector t\u00e9cnico en app","Coste mano de obra","Horas por t\u00e9cnico"],
    gerente:"T\u00e9cnicos, instaladores y maquinaria con tarifas. Control costes mano de obra.",
    campos:{codRecurso:"C\u00f3digo",descripcion:"Nombre",tipo:"EMPLEADO/MAQUINARIA/OTRO",costeHoraNormal:"\u20ac/h normal",costeHoraExtra:"\u20ac/h extra"},
    rel:["proordutil","repordutil"]},
  proveedores:{
    flujo:"browse(filtro) \u2192 codProv \u2192 docalbcom.browse(proveedor=codProv)",
    casos:["Filtro albaranes por proveedor","Directorio contacto","Volumen por proveedor"],
    gerente:"Directorio proveedores. Analiza compras y negocia condiciones.",
    campos:{codProv:"C\u00f3digo",nombre:"Raz\u00f3n social",cif:"CIF/NIF",telefono:"Tel\u00e9fono",email:"Email"},
    rel:["docalbcom","docfaccom","articulos"]},
  clientes:{
    flujo:"browse \u2192 filtrar proyectos por cliente",
    casos:["Filtro obras por cliente","Facturaci\u00f3n por cliente","Dashboard cliente"],
    gerente:"Cartera de clientes y sus obras.",
    campos:{codCliente:"C\u00f3digo",nombre:"Raz\u00f3n social",cif:"CIF/NIF"},
    rel:["proyectos"]},
  docalbcom:{
    flujo:"browse(proveedor) \u2192 read(codDoc) \u2192 imputaPro(doc, linea, proyecto, partida, F)",
    casos:["Imputar albar\u00e1n sin entrar al ERP","Control albaranes pendientes","Cuadre compras-costes"],
    gerente:"Albaranes recibidos. imputaPro vincula l\u00ednea a obra/partida: automatiza control de costes.",
    campos:{codDocumento:"N\u00famero albar\u00e1n",proveedor:"Empresa proveedora",fecha:"Fecha recepci\u00f3n"},
    rel:["proveedores","proyectos","partidas"]},
  docfaccom:{
    flujo:"browse \u2192 imputaPro \u2192 coste vinculado a obra",
    casos:["Cierre mensual: imputar facturas","Conciliaci\u00f3n factura-albar\u00e1n-obra"],
    gerente:"Facturas de compra. imputaPro automatiza contabilidad de costes.",
    campos:{codDocumento:"N\u00famero factura",proveedor:"Proveedor",fecha:"Fecha"},
    rel:["proveedores","proyectos","partidas","docalbcom"]},
  docpedcom:{
    flujo:"browse \u2192 ver pedidos pendientes de recibir",
    casos:["Control pedidos pendientes","Seguimiento entregas"],
    gerente:"Pedidos enviados a proveedores pendientes.",
    campos:{codDocumento:"N\u00famero pedido",proveedor:"Proveedor",estado:"pendiente/parcial/completo"},
    rel:["proveedores","docalbcom"]},
  ordenfab:{
    flujo:"browse \u2192 si code=1: sin licencia \u2192 contactar Distrito K",
    casos:["Gesti\u00f3n producci\u00f3n propia"],
    gerente:"M\u00f3dulo fabricaci\u00f3n. Requiere licencia espec\u00edfica.",
    campos:{codOrden:"N\u00famero orden fabricaci\u00f3n"},
    rel:[]}
};

// ─── Aplicaciones posibles con la API ────────────────────────────────────────
const _APPS = [
  {emoji:"\ud83d\udcf1",t:"App M\u00f3vil del Operario",s:"Imputaci\u00f3n de horas y materiales desde obra",
   d:"El operario selecciona obra y partida desde el m\u00f3vil, imputa material o horas al ERP en tiempo real.",
   b:"Elimina partes en papel. Costes reales en el ERP al instante, sin esperar al final de semana.",
   cls:["proyectos","partidas","articulos","recursos","proordutil"],ops:["browse","new","write"],
   riesgo:"\u270d\ufe0f Escritura real",flujo:"proyectos.browse \u2192 partidas.browse \u2192 articulos.browse \u2192 proordutil.new() \u2192 write()"},
  {emoji:"\ud83d\udcca",t:"Dashboard de Obras para Gerencia",s:"Desviaci\u00f3n de costes en tiempo real",
   d:"Pantalla con obras activas, importe previsto vs real y % ejecuci\u00f3n. Alerta cuando una obra supera el presupuesto.",
   b:"El gerente ve qu\u00e9 obras van bien y cu\u00e1les se desv\u00edan. Toma decisiones antes de que sea tarde.",
   cls:["proyectos","partidas","proordutil","proordprev"],ops:["browse","read"],
   riesgo:"\ud83d\udfe2 Solo lectura",flujo:"proyectos.browse \u2192 proordutil.browse + proordprev.browse \u2192 calcular desviaci\u00f3n"},
  {emoji:"\ud83d\udd27",t:"App SAT para T\u00e9cnicos",s:"Gesti\u00f3n de \u00f3rdenes de reparaci\u00f3n desde m\u00f3vil",
   d:"El t\u00e9cnico ve sus \u00f3rdenes, registra piezas y horas, y cierra la orden al terminar.",
   b:"El responsable ve el estado en tiempo real y factura m\u00e1s r\u00e1pido.",
   cls:["reporden","repobjetos","repinst","repordutil","tipostrabajo"],ops:["browse","read","new","write"],
   riesgo:"\u270d\ufe0f Escritura real",flujo:"reporden.browse(abierta) \u2192 repordutil.new() \u2192 write() \u2192 reporden.write(cerrada)"},
  {emoji:"\ud83d\uded2",t:"Control de Compras con Imputaci\u00f3n",s:"Albaranes y facturas imputados a obras",
   d:"Al recibir un albar\u00e1n, la app permite seleccionar a qu\u00e9 obra y partida imputarlo. Sin entrar al ERP.",
   b:"Compras imputa albaranes sin entrar al ERP. Control de costes m\u00e1s preciso.",
   cls:["docalbcom","docfaccom","proveedores","proyectos","partidas"],ops:["browse","read","imputaPro"],
   riesgo:"\u270d\ufe0f Escritura real (imputaPro)",flujo:"docalbcom.browse \u2192 read \u2192 imputaPro(doc, linea, proyecto, partida, F)"},
  {emoji:"\ud83d\udce6",t:"App de Almac\u00e9n",s:"Control de materiales y stock",
   d:"El almacenero busca materiales por nombre, ve stock, precio y proveedor habitual.",
   b:"Localizaci\u00f3n instant\u00e1nea de materiales. Sin depender del SQL Obras directamente.",
   cls:["articulos","proveedores","recursos"],ops:["browse","read"],
   riesgo:"\ud83d\udfe2 Solo lectura",flujo:"articulos.browse(filtro) \u2192 read \u2192 ver stock, precio, proveedor"},
  {emoji:"\ud83d\udccb",t:"Informe de Mantenimiento Autom\u00e1tico",s:"Estad\u00edsticas SAT: aver\u00edas, tiempos, costes",
   d:"Informe mensual: \u00f3rdenes abiertas/cerradas, tiempo medio, coste por equipo, t\u00e9cnico m\u00e1s productivo.",
   b:"El responsable recibe el informe sin trabajo manual. Detecta qu\u00e9 equipos dan m\u00e1s problemas.",
   cls:["reporden","repobjetos","repordutil","recursos"],ops:["browse","read"],
   riesgo:"\ud83d\udfe2 Solo lectura",flujo:"reporden.browse(cerrada) \u2192 repordutil.browse \u2192 calcular coste \u2192 agrupar por equipo/t\u00e9cnico"}
];

// ─── Glosario SQL Obras <-> API ───────────────────────────────────────────────
const _GLO = [
  {sql:"Obra / Proyecto",api:"proyectos + codProyecto",desc:"Lo que SQL Obras llama 'obra' = clase 'proyectos'. El c\u00f3digo (ej: 26/001) = codProyecto."},
  {sql:"Cap\u00edtulo / Partida",api:"partidas + codPartida",desc:"Cap\u00edtulos presupuestarios de la obra. C\u00f3digo (ej: 03.02) = codPartida."},
  {sql:"Utilizado / Parte de trabajo",api:"proordutil + new()+write()",desc:"Imputar horas o materiales = proordutil.new() \u2192 write(). El ERP lo llama 'utilizado'."},
  {sql:"Orden de aver\u00eda / Parte SAT",api:"reporden + codOrden",desc:"Partes de aver\u00eda o mantenimiento = clase 'reporden'."},
  {sql:"Art\u00edculo / Material",api:"articulos + codArticulo",desc:"Materiales del cat\u00e1logo. Referencia = codArticulo (ej: 1#100142)."},
  {sql:"T\u00e9cnico / Operario",api:"recursos + codRecurso",desc:"T\u00e9cnicos e instaladores = 'recursos'. Puede ser EMPLEADO, MAQUINARIA u OTRO."},
  {sql:"Albar\u00e1n de compra",api:"docalbcom + imputaPro()",desc:"Albaranes de proveedores. Se imputan a obra con imputaPro(codDoc, linea, obra, partida)."},
  {sql:"Equipo / Unidad",api:"repobjetos + codObjeto",desc:"Equipos mantenibles = 'repobjetos'. Su ubicaci\u00f3n = 'repinst' (instalaci\u00f3n)."},
  {sql:"Sesi\u00f3n de usuario",api:"ssid1 + ssid2 (tokens)",desc:"Al hacer login se obtienen dos tokens temporales que van en cada llamada a la API."},
  {sql:"code=0",api:"\u00c9xito",desc:"Toda respuesta lleva 'code'. code=0 = \u00e9xito. Otro c\u00f3digo = error o condici\u00f3n especial."},
  {sql:"code=6",api:"Necesita identificador",desc:"La API necesita codProyecto, codOrden u otro ID. No es error \u2014 falta el c\u00f3digo de negocio."},
  {sql:"Guardar registro",api:"new() \u2192 write()",desc:"Para crear/modificar: new() crea objeto temporal \u2192 write() persiste. cancel() descarta."}
];


if (!_state.probadorPerfil) _state.probadorPerfil = "tecnico";

function renderProbador(s) {
  const cat = _state.catalogue;
  const catalogue = cat ? cat.catalogue : {};
  const sesion = s.session_active;
  const isMock = s.use_mock;
  const modoEsc = s.modo_escritura;
  const perfil = _state.probadorPerfil || "tecnico";
  const perfiles = [
    {id:"gerente",  lbl:"👔 Gerente"},
    {id:"ingeniero",lbl:"🔧 Ingeniero"},
    {id:"empleado", lbl:"👷 Empleado"},
    {id:"tecnico",  lbl:"💻 Técnico API"},
  ];
  const perfilChips = perfiles.map(p=>`<button onclick="ApiExplorerModule.setProbadorPerfil('${p.id}')"
    style="border:2px solid ${perfil===p.id?'#3b82f6':'#e2e8f0'};background:${perfil===p.id?'#3b82f6':'white'};
    color:${perfil===p.id?'white':'#64748b'};border-radius:20px;padding:4px 12px;cursor:pointer;
    font-size:0.79em;font-weight:${perfil===p.id?'700':'400'};white-space:nowrap">${p.lbl}</button>`).join("");

  // Resumen ejecutivo para gerente
  const totalClases = Object.values(catalogue).reduce((a,m)=>a+Object.keys(m).length,0);
  const nOk  = Object.entries(_probRes).filter(([,v])=>v.estado==="ok").length;
  const nReq = Object.entries(_probRes).filter(([,v])=>v.estado==="requiere_params").length;
  const nLic = Object.entries(_probRes).filter(([,v])=>v.estado==="sin_licencia").length;
  const hayRes = Object.keys(_probRes).length > 0;
  const escAviso = modoEsc
    ? `<div style="background:#fff3e0;border-left:4px solid #f59e0b;border-radius:4px;padding:6px 12px;font-size:0.8em;color:#92400e;font-weight:600;margin-top:8px">
        ⚠️ MODO ESCRITURA ACTIVO — Cada operación de escritura pedirá confirmación expresa antes de ejecutarse.
       </div>`
    : `<div style="background:#dcfce7;border-left:4px solid #16a34a;border-radius:4px;padding:6px 12px;font-size:0.8em;color:#166534;font-weight:600;margin-top:8px">
        🟢 MODO SOLO LECTURA — Las operaciones de escritura están bloqueadas. Totalmente seguro para demostración.
       </div>`;

  let h = `<div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:14px 18px;margin-bottom:12px">
    <div style="display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:10px">
      <div style="flex:1;min-width:220px">
        <h3 style="margin:0 0 3px;font-size:1.02em">🧪 Probador Visual — API mPYME (SQL Obras)</h3>
        <p style="margin:0;font-size:0.79em;color:#64748b">Formulario interactivo por operación · 🔍 autocompleta de BD · ❓ explicación técnica + para el empleado</p>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
         ${sesion
           ? `<button onclick="ApiExplorerModule.doProbarTodoCatalogo(event)" class="btn primary" style="white-space:nowrap;font-size:0.83em">🚀 Probar todas (solo lectura)</button>`
           : `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:5px 10px;font-size:0.8em;color:#92400e">⚠️ Conectarse en <b>Conexión</b></div>`}
         ${sesion?`<button onclick="ApiExplorerModule.doDiagnosticoFirebird()" class="btn secondary" style="white-space:nowrap;font-size:0.83em" title="Comprobar conexion Firebird y ver IDs reales disponibles">🔌 Diagnóstico BD</button>`:""}
         <button onclick="ApiExplorerModule.doExportarProbadorTxt()"
           class="btn secondary" style="white-space:nowrap;font-size:0.83em;${!hayRes?'opacity:0.5':''}"
           ${!hayRes?'title="Pulsa Probar todas primero para tener resultados"':''}>
           📄 Exportar TXT
         </button>
       </div>
    </div>
    <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">
      <span style="font-size:0.76em;color:#94a3b8">👀 Ver como:</span>${perfilChips}
    </div>
    ${escAviso}
    <div id="ae-probador-todo-result" style="margin-top:8px"></div>
    <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">
      ${isMock?`<span style="background:#dbeafe;padding:3px 9px;border-radius:4px;font-size:0.76em;color:#1d4ed8">🔵 BD Simulada</span>`:`<span style="background:#dcfce7;padding:3px 9px;border-radius:4px;font-size:0.76em;color:#166534">🟢 API Real — SQL Obras</span>`}
    </div>
  </div>
  ${perfil==="gerente"&&hayRes?`<div style="background:linear-gradient(135deg,#f0fdf4,#eff6ff);border:1px solid #86efac;border-radius:8px;padding:12px 16px;margin-bottom:12px">
    <p style="font-size:0.88em;font-weight:700;color:#166534;margin:0 0 8px">📊 Resumen ejecutivo — ¿Qué puede hacer la API con vuestra licencia actual?</p>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">
      <div style="background:white;border-radius:8px;padding:8px 14px;border:1px solid #bbf7d0;text-align:center;min-width:90px">
        <p style="font-size:1.5em;margin:0;font-weight:700;color:#166534">${nOk+nReq}</p>
        <p style="font-size:0.74em;color:#166534;margin:0">clases accesibles</p>
      </div>
      <div style="background:white;border-radius:8px;padding:8px 14px;border:1px solid #bfdbfe;text-align:center;min-width:90px">
        <p style="font-size:1.5em;margin:0;font-weight:700;color:#1e40af">${nOk}</p>
        <p style="font-size:0.74em;color:#1e40af;margin:0">funcionando ahora</p>
      </div>
      ${nLic?`<div style="background:white;border-radius:8px;padding:8px 14px;border:1px solid #fca5a5;text-align:center;min-width:90px">
        <p style="font-size:1.5em;margin:0;font-weight:700;color:#991b1b">${nLic}</p>
        <p style="font-size:0.74em;color:#991b1b;margin:0">sin licencia</p>
      </div>`:""}
    </div>
    <p style="font-size:0.79em;color:#374151;margin:0">
      ${nOk+nReq>0?`✅ <b>Podemos implementar:</b> consulta de obras, partes de trabajo, materiales imputados, órdenes de reparación y mantenimiento.`:""}
      ${nLic?`<br>⚠️ <b style="color:#991b1b">Sin licencia Documentos:</b> albaranes, facturas y pedidos bloqueados. Contactar Distrito K para ampliar.`:""}
    </p>
  </div>`:""}
  `;

  if (!cat || !Object.keys(catalogue).length)
    return h + `<div style="background:#fef9c3;border-radius:8px;padding:14px;font-size:0.85em;color:#92400e">⏳ Cargando catálogo…</div>`;

  // ── Sección: Aplicaciones posibles
  if (typeof _APPS !== 'undefined') {
    var _appsHtml = _APPS.map(function(app) {
      var clsH = app.cls.map(function(c){ return '<code style="background:#f1f5f9;padding:1px 5px;border-radius:3px">'+c+'</code>'; }).join(' ');
      var opsH = app.ops.map(function(o){ return '<span style="background:#e0f2fe;color:#0369a1;border-radius:4px;padding:1px 6px">'+o+'</span>'; }).join(' ');
      var _col = app.riesgo.indexOf('Solo')>=0 ? '#166534' : '#92400e';
      return '<div style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">'
        +'<div style="padding:9px 12px;background:#f8fafc;display:flex;align-items:center;gap:7px">'
        +'<span style="font-size:1.3em">'+app.emoji+'</span>'
        +'<div><b style="font-size:0.87em;color:#1e293b">'+app.t+'</b><br>'
        +'<span style="font-size:0.73em;color:#64748b">'+app.s+'</span></div></div>'
        +'<div style="padding:8px 12px;font-size:0.79em;color:#374151">'+app.d+'</div>'
        +'<details style="border-top:1px solid #f1f5f9">'
        +'<summary style="cursor:pointer;padding:5px 12px;font-size:0.74em;color:#3b82f6;background:#f8fafc">Ver detalle técnico ▾</summary>'
        +'<div style="padding:8px 12px;font-size:0.76em;display:grid;gap:4px;background:white">'
        +'<div style="color:#166534"><b>Beneficio:</b> '+app.b+'</div>'
        +'<div style="color:#0369a1"><b>Flujo API:</b><br>'
        +'<code style="background:#f0f9ff;padding:2px 6px;border-radius:3px">'+app.flujo+'</code></div>'
        +'<div><b>Clases necesarias:</b> '+clsH+'</div>'
        +'<div><b>Operaciones:</b> '+opsH+'</div>'
        +'<div><b>Riesgo:</b> <span style="font-weight:600;color:'+_col+'">'+app.riesgo+'</span></div>'
        +'</div></details></div>';
    }).join('');
    h += '<details style="margin-bottom:10px;border:1px solid #bfdbfe;border-radius:10px;overflow:hidden">'
      +'<summary style="cursor:pointer;padding:11px 16px;background:linear-gradient(90deg,#eff6ff,#f0fdf4);display:flex;align-items:center;gap:10px">'
      +'<span style="font-size:1.2em">&#128640;</span>'
      +'<span style="font-weight:700;font-size:0.93em;flex:1;color:#1e293b">Aplicaciones posibles con esta API</span>'
      +'<span style="font-size:0.74em;color:#64748b">6 apps &middot; expandir para ver</span>'
      +'</summary>'
      +'<div style="padding:10px 12px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px;background:white">'
      + _appsHtml + '</div></details>';
  }

  // ── Sección: Aprende sobre SQL Obras y la API ──────────────────────────────
  h += `<details style="margin-bottom:10px;border:1px solid #d1fae5;border-radius:10px;overflow:hidden">
    <summary style="cursor:pointer;padding:11px 16px;background:linear-gradient(90deg,#f0fdf4,#fefce8);display:flex;align-items:center;gap:10px">
      <span style="font-size:1.2em">📚</span>
      <span style="font-weight:700;font-size:0.93em;flex:1;color:#1e293b">Aprende sobre SQL Obras y la API mPYME</span>
      <span style="font-size:0.74em;color:#64748b">Glosario · Ciclo new→write · Códigos · Consejos</span>
    </summary>
    <div style="padding:10px 12px;background:white">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
        <div style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">
          <div style="padding:8px 12px;background:#f8fafc;font-weight:700;font-size:0.84em;color:#374151">📖 Glosario SQL Obras ↔ API</div>
          <div style="max-height:260px;overflow-y:auto">
            ${(typeof _GLO!=='undefined'?_GLO:[]).map(function(g){return '<div style="padding:5px 12px;border-bottom:1px solid #f8fafc;font-size:0.77em"><span style="background:#dbeafe;color:#1e40af;border-radius:3px;padding:1px 5px;font-weight:600">'+g.sql+'</span> &rarr; <code style="background:#f1f5f9;color:#374151;padding:1px 5px;border-radius:3px">'+g.api+'</code><div style="color:#64748b;margin-top:2px">'+g.desc+'</div></div>';}).join("")}
          </div>
        </div>
        <div style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">
          <div style="padding:8px 12px;background:#f8fafc;font-weight:700;font-size:0.84em;color:#374151">🔄 Ciclo: new → write → cancel</div>
          <div style="padding:8px 12px;font-size:0.77em;display:grid;gap:6px">
            <div style="background:#f0fdf4;border-left:3px solid #16a34a;border-radius:4px;padding:6px 10px"><b style="color:#166534">1️⃣ new()</b> — Crea objeto <em>temporal</em>. No persiste. Seguro.</div>
            <div style="background:#fef9c3;border-left:3px solid #fbbf24;border-radius:4px;padding:6px 10px"><b style="color:#78350f">2️⃣ Rellena campos</b> — Indica codProyecto, codPartida, codArticulo, cantidad, coste...</div>
            <div style="background:#fff7ed;border-left:3px solid #f97316;border-radius:4px;padding:6px 10px"><b style="color:#92400e">3️⃣ write()</b> — PERSISTE en SQL Obras. Irreversible. Devuelve codDocumento.</div>
            <div style="background:#fef2f2;border-left:3px solid #ef4444;border-radius:4px;padding:6px 10px"><b style="color:#991b1b">❌ cancel()</b> — Descarta el temporal. No guarda nada.</div>
            <div style="background:#eff6ff;border-left:3px solid #3b82f6;border-radius:4px;padding:6px 10px"><b style="color:#1e40af">🔍 browse() con filtros</b> — Ej: <code style="background:#dbeafe;padding:1px 5px;border-radius:3px">filter={"estado":"activo"}</code></div>
          </div>
        </div>
      </div>
      <details style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;margin-bottom:6px">
        <summary style="cursor:pointer;padding:7px 12px;background:#f8fafc;font-size:0.82em;font-weight:700;color:#374151">📡 Códigos de respuesta — ¿Qué significa cada code?</summary>
        <div style="padding:8px 12px;display:grid;grid-template-columns:repeat(auto-fill,minmax(195px,1fr));gap:5px;background:white">
          ${[["0","✅","#dcfce7","#166534","Operación exitosa."],["1","🚫","#fef2f2","#991b1b","Sin licencia."],["2","🔒","#f8fafc","#64748b","Sin permiso."],["3","⚠️","#fef9c3","#92400e","Error validación."],["5","⚙️","#fff7ed","#92400e","Config incompleta."],["6","🔵","#dbeafe","#1d4ed8","Requiere ID real."],["10","🔍","#f8fafc","#64748b","No encontrado."],["-1","💥","#fef2f2","#991b1b","Error de red."],["-99","⛔","#f8fafc","#374151","Escritura bloqueada."]]
          .map(function(x){var c=x[0],ic=x[1],bg=x[2],cl=x[3],d=x[4];return '<div style="background:'+bg+';border-radius:5px;padding:5px 8px;font-size:0.76em"><b style="color:'+cl+'">'+ic+' code='+c+'</b><div style="color:#475569;margin-top:2px">'+d+'</div></div>';}).join("")}
        </div>
      </details>
      <details style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">
        <summary style="cursor:pointer;padding:7px 12px;background:#f8fafc;font-size:0.82em;font-weight:700;color:#374151">💡 Buenas prácticas</summary>
        <div style="padding:8px 12px;display:grid;gap:5px;font-size:0.78em;background:white">
          <div style="background:#f0fdf4;border-radius:5px;padding:5px 9px;color:#166534"><b>✅ Empieza con permiso()</b> — Antes de usar una clase, ejecuta permiso() para saber qué permite tu licencia.</div>
          <div style="background:#eff6ff;border-radius:5px;padding:5px 9px;color:#1e40af"><b>🔵 code=6: usa 🔍 BD</b> — Pulsa el botón BD en el campo requerido para autocompletar con valores reales de Firebird.</div>
          <div style="background:#fefce8;border-radius:5px;padding:5px 9px;color:#78350f"><b>📌 browse() con pagesize</b> — Usa pagesize=25 y page=1 para paginar grandes listas.</div>
          <div style="background:#f0fdf4;border-radius:5px;padding:5px 9px;color:#166534"><b>🟢 info() descubre la estructura real</b> — info() devuelve todos los campos con tipos. Úsalo para descubrir campos no documentados.</div>
        </div>
      </details>
    </div>
  </details>`;



  Object.entries(catalogue).forEach(([modNombre, claseMap]) => {
    const clasesArr = Object.entries(claseMap);
    const nOk = clasesArr.filter(([c])=>{const r=_probRes[c+".browse"]||_probRes[c+".permiso"];return r&&r.estado==="ok";}).length;
    const modMeta = cat.catalogue[modNombre] || {};
    const modEmoji = modMeta.emoji || "📦";
    const modDesc  = modMeta.desc  || "";
    h += `<details open style="margin-bottom:8px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
      <summary style="padding:10px 16px;background:#f8fafc;cursor:pointer;display:flex;align-items:center;gap:10px;list-style:none">
        <span style="font-size:1.1em">${modEmoji}</span>
        <div style="flex:1;min-width:0">
          <span style="font-weight:700;font-size:0.93em">${modNombre}</span>
          ${modDesc?`<span style="font-size:0.75em;color:#64748b;margin-left:6px">${modDesc}</span>`:""}
        </div>
        <span style="font-size:0.75em;color:#94a3b8">${clasesArr.length} clases</span>
        ${nOk>0?`<span style="background:#dcfce7;color:#166534;border-radius:10px;padding:1px 8px;font-size:0.7em;font-weight:700">${nOk} ✅</span>`:""}
        <span style="color:#94a3b8">▾</span>
      </summary>
      <div style="padding:6px 10px">`;
    clasesArr.forEach(([clase, opsArr]) => {
      const ci = CLASE_INFO[clase]||{emoji:"🔷",desc:clase,detalle:""};
      const opsLec = opsArr.filter(o=>(_OPDESC[o]||{riesgo:0}).riesgo<2);
      const opsEsc = opsArr.filter(o=>(_OPDESC[o]||{riesgo:0}).riesgo>=2);
      let mejor="pendiente";
      opsArr.forEach(op=>{const r=_probRes[`${clase}.${op}`];if(r){if(r.estado==="ok")mejor="ok";else if(mejor==="pendiente")mejor=r.estado;}});
      const ec=_ECFG[mejor]||_ECFG.pendiente;
      h += `<details style="margin-bottom:5px;border:1px solid ${ec.border};border-radius:8px;overflow:hidden">
        <summary style="padding:9px 12px;background:${ec.bg};cursor:pointer;display:flex;align-items:center;gap:8px;list-style:none">
          <span>${ci.emoji}</span>
          <div style="flex:1;min-width:0"><b style="font-size:0.87em;color:#1e293b">${clase}</b><span style="font-size:0.77em;color:#475569;margin-left:7px">${ci.desc}</span></div>
          <span style="border:1px solid ${ec.border};color:${ec.color};border-radius:10px;padding:1px 8px;font-size:0.7em;font-weight:600">${ec.sym} ${ec.label}</span>
          <span style="color:#94a3b8">▾</span>
        </summary>
        <div style="border-top:1px solid ${ec.border}">
          <div style="padding:8px 14px;background:#fafcff;border-bottom:1px solid #f1f5f9;display:flex;flex-direction:column;gap:4px">
            <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:5px;padding:5px 10px;font-size:0.78em;color:#1e40af"><b>🔧 Técnico:</b> ${ci.detalle||ci.desc}</div>
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:5px;padding:5px 10px;font-size:0.78em;color:#166534"><b>👷 Empleado SQL Obras:</b> ${_claseDescEmp(clase)}</div>
            ${(_CF[clase]?.gerente)?`<div style="background:#fefce8;border:1px solid #fde68a;border-radius:5px;padding:5px 10px;font-size:0.78em;color:#78350f"><b>📊 Gerente:</b> ${_CF[clase].gerente}</div>`:""}
          </div>
          ${_CF[clase]?`<details style="margin:0 4px 6px;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">
            <summary style="cursor:pointer;padding:6px 12px;background:#f8fafc;font-size:0.76em;font-weight:600;color:#374151">📖 Flujo, casos de uso y campos clave ▾</summary>
            <div style="padding:8px 12px;display:grid;gap:5px;background:white">
              <div style="background:#f0f9ff;border-radius:5px;padding:5px 9px;font-size:0.75em"><b style="color:#0369a1">🔄 Flujo típico:</b><br><code style="color:#0c4a6e;background:#e0f2fe;padding:1px 5px;border-radius:3px">${_CF[clase].flujo}</code></div>
              <div style="background:#f0fdf4;border-radius:5px;padding:5px 9px;font-size:0.75em"><b style="color:#166534">💡 Casos de uso:</b><ul style="margin:2px 0 0;padding-left:14px">${(_CF[clase].casos||[]).map(c=>`<li style="color:#15803d;margin:1px 0">${c}</li>`).join("")}</ul></div>
              ${Object.keys(_CF[clase].campos||{}).length?`<div style="background:#faf5ff;border-radius:5px;padding:5px 9px;font-size:0.75em"><b style="color:#6b21a8">🗂️ Campos clave:</b><div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:3px">${Object.entries(_CF[clase].campos).map(([k,v])=>`<span title="${v}" style="background:#ede9fe;color:#5b21b6;border-radius:4px;padding:1px 7px;cursor:help;font-family:monospace;font-size:0.93em">${k}</span>`).join("")}</div></div>`:""}
              ${(_CF[clase].rel||[]).length?`<div style="font-size:0.73em;color:#64748b">🔗 Relacionadas: ${_CF[clase].rel.map(r=>`<code style="background:#f1f5f9;padding:1px 5px;border-radius:3px">${r}</code>`).join(" ")}</div>`:""}
            </div>
          </details>`:""}
          <div style="padding:8px 14px">
            <p style="font-size:0.74em;font-weight:700;color:#374151;margin:0 0 5px">OPERACIONES DE LECTURA</p>
            <div style="display:flex;flex-direction:column;gap:5px">${opsLec.map(op=>_mkOpCard(clase,op,sesion)).join("")}</div>
          </div>
          ${opsEsc.length?`<div style="padding:8px 14px;border-top:1px solid #fed7aa;background:#fffbf5">
            <p style="font-size:0.74em;font-weight:700;color:#92400e;margin:0 0 5px">⚠️ ESCRITURA (activar modo escritura primero)</p>
            <div style="display:flex;flex-direction:column;gap:5px">${opsEsc.map(op=>_mkOpCard(clase,op,sesion)).join("")}</div>
          </div>`:""}
        </div>
      </details>`;
    });
    h += `</div></details>`;
  });
  return h;
}
function _claseDescEmp(c) {
  return ({
    proyectos:"Aquí están todas las obras de la empresa. Cada obra tiene un código, cliente, estado e importes. Es el punto de entrada: primero busca la obra.",
    partidas:"El presupuesto de una obra dividido en capítulos: cimentación, instalaciones, etc. Necesitas el código de obra primero.",
    proordutil:"\u26a1 CLASE CLAVE. Aquí se registra todo lo que se consume en una obra: materiales puestos, horas de trabajo. Sin esto el ERP no sabe cuánto cuesta la obra realmente.",
    proordprev:"Lo que se presupuestó para la obra (no lo que se ha gastado). Compararlo con los utilizados muestra si la obra va bien de presupuesto.",
    reporden:"El parte de avería o mantenimiento. Cuando falla algo, se crea una orden, se asigna al técnico y se registra qué se hizo.",
    repobjetos:"El inventario de equipos: calderas, climatizadoras, bombas... Cada equipo tiene marca, modelo y número de serie.",
    repinst:"Los edificios o zonas donde están los equipos. Sirve para saber físicamente dónde ir a reparar.",
    tipostrabajo:"Categorías de trabajo: ¿es una avería (correctivo)? ¿es una revisión anual (preventivo)? ¿instalación nueva?",
    repordutil:"Lo que se ha gastado en una reparación: piezas de repuesto, horas del técnico. Como proordutil pero para el módulo SAT.",
    articulos:"Lista de todos los materiales con precio, stock y proveedor. Se usa para buscar la referencia antes de imputarla a una obra.",
    recursos:"Los técnicos, instaladores y maquinaria con sus tarifas de hora. Se usa para imputar mano de obra a una obra o reparación.",
    proveedores:"Las empresas proveedoras: Daikin, Atlantic, Roca... Sirve para filtrar albaranes y facturas por proveedor.",
    clientes:"Las empresas o personas para las que trabaja la empresa. Cada obra pertenece a un cliente.",
    docalbcom:"Los albaranes de materiales que llegan. Con imputaPro se imputa directamente el gasto al proyecto y partida sin introducir nada manualmente en el ERP.",
    docfaccom:"Las facturas de los proveedores. Con imputaPro se carga automáticamente a la obra como coste real.",
    docpedcom:"Los pedidos que se han hecho a proveedores y aún no han llegado. ⚠️ La imputación a obra en pedidos no está confirmada 100% por Distrito K.",
    ordenfab:"Órdenes de fabricación propia. Solo disponible si se tiene el módulo de fabricación contratado."
  }[c]||"Clase de la API mPYME v1.2 de Distrito K / SQL Obras.");
}



function _mkOpCard(clase, op, sesion) {
  const oi  = _OPDESC[op]||{riesgo:0,label:op,rl:"",desc:op};
  const key = `${clase}.${op}`;
  const res = _probRes[key];
  const ec  = res ? (_ECFG[res.estado]||_ECFG.error) : _ECFG.pendiente;
  const esW = oi.riesgo >= 2;
  const rBG = ["#f0fdf4","#fefce8","#fff7ed","#fef2f2"][oi.riesgo]||"#f8fafc";
  const rCL = ["#166534","#92400e","#c2410c","#991b1b"][oi.riesgo]||"#64748b";
  const modoEscActivo = (_state.status||{}).modo_escritura;
  const bloqueadoPorEsc = esW && !modoEscActivo;
  const btnBg = esW ? "#92400e" : "#3b82f6";
  const urlApi = `mPYME → ${clase}.${op}()`;

  // ── Formulario de parámetros ultra-amigable ─────────────────────────────────
  const params = PARAMS_DB[`${clase}.${op}`] || [];
  let formHtml = "";
  if (params.length > 0) {
    const hasBDParams = params.some(f=>_PARAMS_CON_BD.has(f.n));
    const autoFillAll = hasBDParams
      ? `<button type="button" onclick="ApiExplorerModule.doAutocompletarTodos('${clase}','${op}')"
           style="border:1px solid #3b82f6;background:#3b82f6;color:white;border-radius:5px;padding:3px 10px;font-size:0.77em;cursor:pointer;font-weight:600">
           🔍 Autocompletar todo desde BD</button>`
      : "";
    const fields = params.map(f => {
      const pi  = _PARAM_INFO[f.n];
      const hasBD = _PARAMS_CON_BD.has(f.n);
      const isReq = f.req;
      const reqBadge = isReq
        ? `<span style="background:#fef2f2;color:#dc2626;border-radius:3px;padding:0 4px;font-size:0.72em;font-weight:700" title="Obligatorio — sin él la llamada fallará">REQ</span>`
        : `<span style="background:#f1f5f9;color:#94a3b8;border-radius:3px;padding:0 4px;font-size:0.72em" title="Opcional">OPT</span>`;
      const bdBtn = hasBD
        ? `<button type="button" onclick="ApiExplorerModule.doAutocompletar('${clase}','${op}','${f.n}')"
             title="Buscar valores reales en la BD de SQL Obras"
             style="border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8;border-radius:4px;padding:2px 8px;font-size:0.74em;cursor:pointer">🔍 BD</button>` : "";
      const ejVal = (pi?.ej||f.ph||"").replace(/'/g,"\\'");
      const ejBtn = ejVal
        ? `<button type="button"
             onclick="(function(){var el=document.getElementById('ap-${clase}-${op}-${f.n}');if(el){el.value='${ejVal}';el.style.borderColor='#86efac';}})()"
             title="Rellenar con ejemplo: ${ejVal}"
             style="border:1px solid #d1fae5;background:#f0fdf4;color:#166534;border-radius:4px;padding:2px 8px;font-size:0.74em;cursor:pointer">🎲 Ej</button>`
        : "";
      const clearBtn = `<button type="button"
          onclick="(function(){var el=document.getElementById('ap-${clase}-${op}-${f.n}');if(el){el.value='';el.style.borderColor='${isReq?'#fca5a5':'#e2e8f0'}';}})()"
          title="Limpiar campo"
          style="border:1px solid #e2e8f0;background:#f8fafc;color:#94a3b8;border-radius:4px;padding:2px 6px;font-size:0.74em;cursor:pointer">✕</button>`;
      const helpBtn = pi
        ? `<button type="button" onclick="ApiExplorerModule.toggleParamHelp('${clase}','${op}','${f.n}')"
             title="Explicación técnica y para empleado"
             style="border:1px solid #fde68a;background:#fefce8;color:#92400e;border-radius:4px;padding:2px 7px;font-size:0.74em;cursor:pointer">❓ Ayuda</button>`
        : "";
      const input = f.t==="select"
        ? `<select id="ap-${clase}-${op}-${f.n}" style="width:100%;border:2px solid ${isReq?'#fca5a5':'#e2e8f0'};border-radius:5px;padding:5px 8px;font-size:0.83em;background:white">
             ${(f.opts||[]).map(o=>`<option value="${o}">${o||"(todos — sin filtro)"}</option>`).join("")}
           </select>`
        : `<input id="ap-${clase}-${op}-${f.n}" type="${f.t||"text"}" placeholder="${f.ph||pi?.ej||""}"
             style="width:100%;border:2px solid ${isReq?'#fca5a5':'#e2e8f0'};border-radius:5px;padding:5px 8px;font-size:0.83em;transition:border-color .15s"
             oninput="this.style.borderColor=this.value?'#86efac':'${isReq?'#fca5a5':'#e2e8f0'}'">`;
      const helpPanel = pi ? `<div id="ap-help-${clase}-${op}-${f.n}" style="display:none;border:1px solid #fde68a;border-radius:5px;overflow:hidden;margin-top:3px">
          <div style="background:#fefce8;padding:5px 9px;font-size:0.77em">
            <div style="color:#92400e;margin-bottom:3px"><b>🔧 Técnico:</b> ${pi.tec}</div>
            <div style="color:#166534;margin-bottom:3px"><b>👷 Empleado SQL Obras:</b> ${pi.emp}</div>
            <div style="color:#1e40af"><b>📝 Ejemplo:</b> <code style="background:#dbeafe;padding:1px 5px;border-radius:3px">${pi.ej}</code></div>
          </div>
        </div>` : `<div id="ap-help-${clase}-${op}-${f.n}" style="display:none"></div>`;
      const bdChips = `<div id="ap-bd-${clase}-${op}-${f.n}"
          style="display:none;flex-wrap:wrap;gap:3px;margin-top:3px;padding:4px 6px;background:#eff6ff;border-radius:4px;border:1px solid #bfdbfe"></div>`;
      return `<div style="background:white;border:1px solid ${isReq?'#fecaca':'#f1f5f9'};border-radius:7px;padding:8px 10px">
        <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;margin-bottom:4px">
          ${reqBadge}
          <span style="font-size:0.82em;color:#1e293b;font-weight:700">${f.n}</span>
          <span style="font-size:0.73em;color:#64748b;font-style:italic">${f.desc||""}</span>
        </div>
        ${input}
        <div style="display:flex;gap:3px;flex-wrap:wrap;margin-top:5px">${bdBtn}${ejBtn}${helpBtn}${clearBtn}</div>
        ${helpPanel}${bdChips}
      </div>`;
    }).join("");
    formHtml = `<div style="padding:8px 12px;background:#f8fafc;border-top:1px solid #f1f5f9">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:7px;flex-wrap:wrap;gap:5px">
        <span style="font-size:0.78em;font-weight:700;color:#374151">📋 Parámetros de la llamada</span>
        ${autoFillAll}
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px">${fields}</div>
      <div style="margin-top:6px;padding:5px 8px;background:#f0f9ff;border-radius:4px;font-size:0.74em;color:#0369a1">
        💡 <b>REQ</b>=obligatorio · <b>OPT</b>=opcional · <b>🔍 BD</b>=autocompletar de BD real · <b>🎲 Ej</b>=poner ejemplo · <b>❓ Ayuda</b>=explicación del campo
      </div>
    </div>`;
  }

  // ── Resultado ─────────────────────────────────────────────────────────────
  let resultHtml = "";
  if (res) {
    const codeExp = _CODEEXP[String(res.code)]||"";
    const campos = res.campos_detectados||[];
    const camposHtml = campos.length
      ? `<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:3px">
           ${campos.map(c=>{
             const tt = _CF[clase]?.campos?.[c] || _CAMPOEXP[c.toUpperCase()] || c;
             return `<code title="${tt}" style="background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:0.82em;cursor:help" data-tip="${tt}">${c}</code>`;
           }).join("")}
         </div>` : "";
    const tablaHtml = res.tabla_html || "";
    resultHtml = `<div style="padding:8px 12px;border-top:1px solid ${ec.border};background:white">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
        <span style="font-size:0.81em;font-weight:700;color:${ec.color}">${ec.sym} ${ec.label}</span>
        <code style="font-size:0.75em;background:#f1f5f9;padding:1px 5px;border-radius:3px">code=${res.code??"-"}</code>
        <span style="font-size:0.74em;color:#94a3b8">${res.ms||0}ms</span>
        ${(res.n_items||0)>0?`<span style="font-size:0.74em;color:#166534;font-weight:600">${res.n_items} registros</span>`:""}
        ${res.id_resuelto?`<span style="font-size:0.72em;background:#dcfce7;color:#166534;padding:1px 6px;border-radius:5px">🔍 ID auto-resuelto de BD</span>`:""}
      </div>
      <div style="font-size:0.76em;color:#64748b;margin-bottom:3px">${codeExp}</div>
      <div style="font-size:0.8em;padding:5px 8px;background:${ec.bg};border-left:3px solid ${ec.border};border-radius:0 4px 4px 0">${res.mensaje||""}</div>
      ${res.raw_servidor?`<div style="margin-top:4px;background:#f1f5f9;border-left:3px solid #94a3b8;border-radius:3px;padding:4px 9px;font-size:0.74em;color:#475569;font-family:monospace">Servidor: ${String(res.raw_servidor).slice(0,200)}</div>`:""}
      ${res.necesito_id_real&&!res.id_resuelto?`<div style="margin-top:5px;background:#dbeafe;border:1px solid #93c5fd;border-radius:5px;padding:5px 10px;font-size:0.77em;color:#1e40af">
        🔵 <b>Requiere identificador real</b> — El sistema intentó obtener un ID de la BD pero no pudo (Firebird no configurado o tabla vacía).<br>
        <span style="color:#374151">Solución: rellena el campo <b>codProyecto</b> (u otro) con el botón <b>🔍 BD</b> o escríbelo manualmente y pulsa <b>▶ Ejecutar</b> de nuevo.</span>
      </div>`:""}
      ${campos.length?`<p style="font-size:0.75em;color:#64748b;font-weight:600;margin:5px 0 2px">Campos detectados:</p>${camposHtml}`:""}
      ${tablaHtml}
    </div>`;
  }
  return `<div id="ae-prob-${clase}-${op}" style="background:${ec.bg};border:1px solid ${ec.border};border-radius:7px;overflow:hidden">
    <div style="padding:7px 12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <div style="flex:1;min-width:150px;display:flex;align-items:center;gap:5px;flex-wrap:wrap">
        <b style="font-size:0.85em;color:#1e293b">${oi.label}</b>
        <code style="font-size:0.74em;color:#64748b">.${op}()</code>
        <span style="font-size:0.7em;padding:1px 6px;border-radius:8px;background:${rBG};color:${rCL}">${oi.rl}</span>
      </div>
      ${res?`<span style="font-size:0.73em;color:${ec.color};font-weight:600">${ec.sym} ${ec.label}</span>`:`<span style="font-size:0.71em;color:#94a3b8">⬜ Sin probar</span>`}
      ${bloqueadoPorEsc
        ? `<span style="font-size:0.79em;padding:4px 10px;background:#fef2f2;border:1px solid #fca5a5;border-radius:5px;color:#991b1b;font-weight:600">🔒 Bloqueada — activar escritura</span>`
        : `<button onclick="ApiExplorerModule.doEjecutarProbador('${clase}','${op}')"
             ${!sesion?"disabled":""}
             style="font-size:0.8em;padding:4px 14px;background:${btnBg};color:white;border:none;border-radius:5px;cursor:pointer;font-weight:600;white-space:nowrap">
             ${esW?"⚠️ Ejecutar (escritura)":"▶ Ejecutar"}
           </button>`}
    </div>
    <div style="padding:2px 12px 4px;background:#0f172a;font-family:monospace;font-size:0.71em;color:#64748b">
      <span style="color:#475569">API: </span><span style="color:#7dd3fc">${urlApi}</span>
    </div>
    ${bloqueadoPorEsc?`<div style="padding:5px 12px;background:#fef2f2;border-top:1px solid #fecaca;font-size:0.77em;color:#991b1b">
      🔒 <b>Operación de escritura bloqueada.</b> Para usarla: pestaña <b>🟠 Escritura</b> → activar con confirmación expresa.<br>
      <span style="color:#64748b">Mientras tanto: modo solo lectura — seguro para demostración.</span>
    </div>`:""}
    <details style="border-top:1px solid ${ec.border}">
      <summary style="cursor:pointer;padding:4px 12px;font-size:0.73em;color:#64748b;background:${ec.bg}">❓ ¿Qué hace esta operación? (técnico + empleado SQL Obras)</summary>
      <div style="padding:6px 12px;display:grid;grid-template-columns:1fr 1fr;gap:5px;background:white;border-top:1px solid ${ec.border}">
        <div style="background:#eff6ff;border-radius:4px;padding:5px 8px;font-size:0.77em;color:#1e40af"><b>🔧 Técnico:</b> ${oi.desc}</div>
        <div style="background:#f0fdf4;border-radius:4px;padding:5px 8px;font-size:0.77em;color:#166534"><b>👷 Empleado:</b> ${_opDescEmp(clase,op)}</div>
      </div>
    </details>
    ${formHtml}${resultHtml}
  </div>`;
}

function _opDescEmp(clase, op) {
  return ({
    browse:"Hace una búsqueda en SQL Obras y muestra los resultados en lista. Como buscar registros en pantalla.",
    read:"Abre la ficha completa de un registro concreto. Como pinchar en un registro para ver todos sus datos.",
    permiso:"Comprueba qué acciones puede hacer el usuario de la API. Auditoría de accesos.",
    info:"Muestra qué campos tiene este tipo de registro. Como ver las columnas de una tabla.",
    new:"Prepara una entrada nueva sin guardarla aún. Como rellenar un formulario antes de pulsar Guardar.",
    edit:"Abre un registro existente para modificarlo.",
    cancel:"Cancela la entrada que estabas preparando. No guarda nada. Siempre seguro.",
    write:"⚠️ Guarda definitivamente en SQL Obras. Como pulsar Guardar. Irreversible.",
    imputaPro:"⚠️ Vincula un albarán o factura a una obra como coste real. Se registra el gasto en la obra.",
    delete:"⚠️ Elimina un registro definitivamente de SQL Obras. No se puede deshacer.",
  }[op]||op);
}

function _chipRes(sym, n, label, bg, color) {
  return `<span style="background:${bg};border-radius:8px;padding:3px 10px;font-size:0.8em;font-weight:600;color:${color}">${sym} ${n} ${label}</span>`;
}
function _e2msg(estado, code, ires) {
  return ({ok:`Operación exitosa${ires?" (ID auto-resuelto)":""}`,
    requiere_params:"Necesita identificador real (codProyecto/codOrden)",
    sin_licencia:"Sin licencia — módulo no contratado",
    sin_permiso:"Sin permiso de usuario",
    config_incompleta:"Config incompleta — revisar .env",
    error:`Error code=${code}`, bloqueado:"Escritura bloqueada"})[estado]||`code=${code}`;
}



function renderConexion(s, cfg) {
  const sesion=s.session_active; const modoMock=s.use_mock;
  const loginMsgHtml = _state.loginMsg ? _state.loginMsg.html : "";
  const urlOk = cfg && cfg.api_url && cfg.api_url.length > 4;
  const userOk = cfg && cfg.usuario && cfg.usuario.length > 0;
  const passOk = cfg && cfg.password_set;
  const empresaOk = cfg && cfg.empresa && cfg.empresa.length > 0;
  const todoConfigurado = urlOk && userOk && passOk && empresaOk;
  const dbHint = (cfg && cfg.db_host_hint) || "192.168.0.254";

  const envPanel = modoMock
    ? `<div style="background:#eff6ff;border-radius:10px;border:1px solid #bfdbfe;padding:16px">
        <h3 style="margin:0 0 8px;font-size:1em;color:#1e40af">🔵 Modo BD Simulada activo</h3>
        <p style="font-size:0.83em;color:#3b82f6;margin:0 0 6px">No necesitas ninguna configuracion. Los datos son ejemplos representativos de la API mPYME 1.2 de Distrito K.</p>
        <p style="font-size:0.82em;color:#64748b;margin:0 0 8px">Explora operaciones, permisos y respuestas sin tocar SQL Obras.</p>
        <details style="font-size:0.8em"><summary style="cursor:pointer;color:#3b82f6">Ver que configurar cuando tengas los datos de Distrito K →</summary>
          <div style="margin-top:8px;background:#dbeafe;border-radius:6px;padding:10px;color:#1e3a8a">
            <p style="margin:0 0 5px;font-weight:600">Añade en el .env y reinicia DEVIA:</p>
            <code style="display:block;background:white;padding:2px 6px;border-radius:3px;margin:2px 0">SQLOB_API_URL=http://${dbHint}:8081/</code>
            <code style="display:block;background:white;padding:2px 6px;border-radius:3px;margin:2px 0">SQLOB_EMPRESA=JUANDEDI</code>
            <code style="display:block;background:white;padding:2px 6px;border-radius:3px;margin:2px 0">SQLOB_USUARIO=tu_usuario_api</code>
            <code style="display:block;background:white;padding:2px 6px;border-radius:3px;margin:2px 0">SQLOB_PASSWORD=tu_password</code>
            <code style="display:block;background:white;padding:2px 6px;border-radius:3px;margin:2px 0">SQLOB_USE_MOCK=false</code>
          </div>
        </details>
      </div>`
    : `<div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px">
        <h3 style="margin:0 0 8px;font-size:1em">🟠 API Real — Configuracion</h3>
        <p style="font-size:0.78em;color:#64748b;margin:0 0 8px">Variables del <code>.env</code>. Tras editar el fichero <strong>reinicia DEVIA</strong>.</p>
        <table style="width:100%;font-size:0.82em;border-collapse:collapse">
          <tr style="border-bottom:1px solid #f1f5f9">
            <td style="color:#64748b;padding:5px 0;width:44%">SQLOB_API_URL<br><small style="color:#94a3b8">URL servidor mPYME</small></td>
            <td>${urlOk?`<code style="background:#f0fdf4;padding:2px 5px;border-radius:3px;color:#166534">${cfg.api_url}</code>`:'<span style="color:#dc3545;font-weight:600">❌ Pendiente</span>'}</td>
          </tr>
          <tr style="border-bottom:1px solid #f1f5f9">
            <td style="color:#64748b;padding:5px 0">SQLOB_EMPRESA<br><small style="color:#94a3b8">Codigo empresa</small></td>
            <td>${empresaOk?`<code style="background:#f8fafc;padding:2px 5px;border-radius:3px">${cfg.empresa}</code> <small style="color:#f59e0b">⚠️ confirmar con Distrito K</small>`:'<span style="color:#f59e0b">⚠️ Vacia</span>'}</td>
          </tr>
          <tr style="border-bottom:1px solid #f1f5f9">
            <td style="color:#64748b;padding:5px 0">SQLOB_USUARIO<br><small style="color:#94a3b8">Usuario API (no SYSDBA)</small></td>
            <td>${userOk?`<code style="background:#f8fafc;padding:2px 5px;border-radius:3px">${cfg.usuario}</code>`:'<span style="color:#dc3545;font-weight:600">❌ Pendiente</span>'}</td>
          </tr>
          <tr>
            <td style="color:#64748b;padding:5px 0">SQLOB_PASSWORD</td>
            <td>${passOk?'<span style="color:#166534;font-weight:600">✅ OK</span>':'<span style="color:#dc3545;font-weight:600">❌ Pendiente</span>'}</td>
          </tr>
        </table>
        ${!todoConfigurado?`<div style="margin-top:10px;background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:9px;font-size:0.8em;color:#78350f">
          <strong>Preguntar a Distrito K:</strong>
          <ol style="margin:5px 0 0;padding-left:16px;line-height:1.9">
            ${!urlOk?`<li>¿URL exacta del servicio mPYME? (probablemente <code>http://${dbHint}:8081/</code>)</li>`:""}
            ${!empresaOk?`<li>¿Codigo de empresa? (puede ser numero 1 o texto JUANDEDI)</li>`:""}
            ${!userOk?`<li>¿Usuario API dedicado con permisos minimos?</li>`:""}
            ${!passOk?`<li>Password de ese usuario</li>`:""}
          </ol>
        </div>`:`<div style="margin-top:8px;background:#dcfce7;border-radius:5px;padding:7px;font-size:0.82em;color:#166534;font-weight:600">✅ Configuracion completa</div>`}
        <div style="margin-top:10px;border-top:1px solid #f1f5f9;padding-top:10px">
          <p style="font-size:0.78em;color:#64748b;font-weight:600;margin:0 0 6px">🔎 Autodescubrimiento inteligente</p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:6px">
            <div style="background:#f8fafc;border-radius:6px;padding:8px">
              <p style="font-size:0.73em;color:#64748b;margin:0 0 5px;font-weight:600">1️⃣ URL del servidor mPYME</p>
              <p style="font-size:0.71em;color:#94a3b8;margin:0 0 5px">Prueba puertos 8081, 8080, 80, 443 en ${dbHint}</p>
              <div style="display:flex;gap:4px">
                <button onclick="ApiExplorerModule.doDiscover()" class="btn secondary" style="font-size:0.76em;white-space:nowrap">🔍 Descubrir URL</button>
                <input id="ae-discover-host" type="text" placeholder="IP extra (opcional)" class="form-control" style="font-size:0.76em;flex:1">
              </div>
            </div>
            <div style="background:#f8fafc;border-radius:6px;padding:8px">
              <p style="font-size:0.73em;color:#64748b;margin:0 0 5px;font-weight:600">2️⃣ Usuarios desde Firebird</p>
              <p style="font-size:0.71em;color:#94a3b8;margin:0 0 5px">Solo SELECT. Sin escrituras. Password no descubrible.</p>
              <button onclick="ApiExplorerModule.doDiscoverDb()" class="btn secondary" style="font-size:0.76em;width:100%">👤 Descubrir usuarios y empresa</button>
            </div>
          </div>
          <div id="ae-discover-result" style="margin-top:6px"></div>
          <div id="ae-discover-db-result" style="margin-top:6px"></div>
        </div>
      </div>`;

  return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
    <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px">
      <h3 style="margin:0 0 12px;font-size:1em">Modo de conexion</h3>
      <div style="display:flex;gap:10px;margin-bottom:10px">
        <button onclick="ApiExplorerModule.setModo(true)" class="btn ${modoMock?'primary':'secondary'}" style="flex:1">🔵 BD Simulada</button>
        <button onclick="ApiExplorerModule.setModo(false)" class="btn ${!modoMock?'primary':'secondary'}" style="flex:1">🟠 API Real</button>
      </div>
      <p style="font-size:0.83em;color:#64748b;margin:3px 0">Sesion: ${sesion?`<strong style="color:#166534">${s.empresa}/${s.usuario} ✅</strong>`:'<span style="color:#991b1b">Sin sesion activa</span>'}</p>
      <p style="font-size:0.83em;color:#64748b;margin:3px 0">Escritura: ${s.modo_escritura?'<strong style="color:#d97706">⚠️ ACTIVA</strong>':'<strong style="color:#166534">🟢 Solo lectura</strong>'}</p>
    </div>
    ${envPanel}
  </div>
  <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px">
    <h3 style="margin:0 0 12px;font-size:1em">Login / Logout</h3>
    ${modoMock?'<p style="font-size:0.8em;color:#3b82f6;background:#dbeafe;border-radius:5px;padding:5px 10px;margin-bottom:10px">🔵 Modo simulado: cualquier empresa, usuario y password funcionan.</p>':''}
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px">
      <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">Empresa <small style="color:#94a3b8">(confirmar con Distrito K)</small></label><input id="ae-empresa" type="text" value="${cfg.empresa||'JUANDEDI'}" class="form-control" style="width:100%"></div>
      <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">Usuario API <small style="color:#94a3b8">(pedir a Distrito K)</small></label><input id="ae-usuario" type="text" value="${cfg.usuario||''}" class="form-control" style="width:100%"></div>
      <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">Password</label><input id="ae-password" type="password" value="${modoMock?'simulado':''}" class="form-control" placeholder="${modoMock?'(cualquier valor)':'Password API Distrito K'}" style="width:100%"></div>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <button onclick="ApiExplorerModule.doLogin()" class="btn primary">🔑 Conectar</button>
      <button onclick="ApiExplorerModule.doLogout()" class="btn secondary" ${!sesion?'disabled':''}>🔌 Desconectar</button>
    </div>
    ${loginMsgHtml ? `<div style="margin-top:12px">${loginMsgHtml}</div>` : ""}
  </div>
  ${sesion?`<div style="background:#dcfce7;border-radius:10px;border:1px solid #86efac;padding:12px;margin-top:12px;font-size:0.82em">
    <strong>✅ Sesion activa</strong> &nbsp;|&nbsp; ssid1: <code style="background:#f0fdf4;padding:1px 5px;border-radius:3px">${s.ssid1_masked}</code> &nbsp;
    ssid2: <code style="background:#f0fdf4;padding:1px 5px;border-radius:3px">${s.ssid2_masked}</code>
    <span style="color:#94a3b8;font-size:0.85em">&nbsp;(enmascarados)</span>
  </div>`:''}`;
}



// ═══════════════════════════════════════════════════════════════
// INSPECTOR API — descubrimiento completo con datos reales
// ═══════════════════════════════════════════════════════════════
function renderInspector(s) {
  const cf  = _state.catalogueFull;
  const dr  = _state.discoverResult;
  const iTab = _state.inspectorTab || "resumen";
  const cls  = _state.inspectorClase;

  // Sub-pestañas del Inspector
  const ITABS = [["resumen","📋 Resumen"],["clase","🗂️ Por Clase"],["plan","🎯 Plan pruebas"],["operaciones","⚙️ Operaciones"],["codigos","🔢 Códigos"],["informe","📑 Informe"]];
  const itabBar = `<div style="display:flex;gap:4px;margin-bottom:14px;flex-wrap:wrap;border-bottom:1px solid #f1f5f9;padding-bottom:10px">
    ${ITABS.map(([id,lbl]) => `<button onclick="ApiExplorerModule.setInspectorTab('${id}')"
      style="padding:5px 13px;border:1px solid ${iTab===id?'#3b82f6':'#e2e8f0'};background:${iTab===id?'#3b82f6':'white'};color:${iTab===id?'white':'#64748b'};border-radius:6px;cursor:pointer;font-size:0.82em;transition:all 0.15s">${lbl}</button>`).join('')}
  </div>`;

  // Número de clases del catálogo
  const nCls = cf ? Object.values(cf.catalogue||{}).reduce((a,m)=>a+(m.clases?.length||0),0) : 17;

  // Banner de acción principal
  const btnD = `<div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:14px 16px;margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <div style="flex:1;min-width:200px">
        <p style="margin:0;font-weight:600;font-size:0.95em">🔍 Descubrir todo — permiso + info + datos reales</p>
        <p style="margin:3px 0 0;font-size:0.79em;color:#64748b">
          Consulta las ${nCls} clases documentadas: permisos reales, campos del servidor y muestra de datos.
          Solo lectura. ${s.session_active
            ? `<strong style="color:#166534">Sesión activa ✅</strong>`
            : `<span style="color:#991b1b">Requiere login primero.</span>`}
        </p>
      </div>
      <button onclick="ApiExplorerModule.doDiscoverAll()" class="btn primary"
        ${!s.session_active?'disabled':''} style="white-space:nowrap;font-size:0.85em">
        ${dr ? '🔄 Repetir descubrimiento' : '🚀 Descubrir todo'}</button>
      ${dr ? `<span style="font-size:0.77em;color:${_state._cacheRestored?'#f59e0b':'#94a3b8'}">${_state._cacheRestored?'📂 Cache disco':'✅ Sesión'}: ${(dr.timestamp||'').slice(0,19).replace('T',' ')} · ${dr.empresa||''} · ${dr.usuario||''}</span>` : ''}
    </div>
    <div id="ae-dap-wrap" style="display:none;margin-top:10px">
      <div style="background:#f1f5f9;border-radius:4px;height:7px;overflow:hidden">
        <div id="ae-dap-bar" style="background:#3b82f6;height:100%;width:0%;transition:width 0.4s"></div>
      </div>
      <p id="ae-dap-msg" style="font-size:0.79em;color:#64748b;margin:5px 0 0">Iniciando…</p>
    </div>
    ${dr ? `<div style="margin-top:10px;display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:8px">
      ${[['✅','Con acceso','con_permiso','#dcfce7','#166534'],['🚫','Sin licencia','sin_licencia','#fef2f2','#991b1b'],
         ['🔒','Sin permiso','sin_permiso','#f8fafc','#64748b'],['ℹ️','Requiere params','precisa_params','#dbeafe','#1d4ed8'],['⚠️','Error','error','#fef9c3','#92400e']]
        .map(([ic,lbl,key,bg,cl]) => `<div style="background:${bg};border-radius:8px;padding:8px 10px;text-align:center">
          <p style="margin:0;font-size:1.3em">${ic}</p>
          <p style="margin:2px 0 0;font-size:0.75em;font-weight:700;color:${cl}">${Object.values(dr.clases||{}).filter(c=>c.estado===key).length}</p>
          <p style="margin:0;font-size:0.7em;color:${cl}">${lbl}</p>
        </div>`).join('')}
    </div>` : ''}
  </div>`;

  if (!cf) {
    return btnD + `<div style="background:#fef9c3;border-radius:8px;padding:12px;font-size:0.84em;color:#92400e">
      ⏳ Cargando catálogo documentado…</div>`;
  }

  const cat = cf.catalogue || {};
  let content = '';
  if (iTab === 'resumen')         content = _inspResumen(cat, dr);
  else if (iTab === 'clase')      content = _inspClase(cat, cf, dr, cls);
  else if (iTab === 'plan')       content = `<div id="ae-plan-root"><p style="color:#64748b;font-size:0.85em;padding:12px">⏳ Cargando plan…</p></div>`;
  else if (iTab === 'operaciones') content = _inspOps(cf);
  else if (iTab === 'codigos')     content = _inspCodes(cf);
  else if (iTab === 'informe')     content = _inspInforme();

  return btnD + itabBar + content;
}



// ── Inspector: RESUMEN ─────────────────────────────────────────
function _inspResumen(cat, dr) {
  const BADGE = {
    con_permiso:    `<span style="background:#dcfce7;color:#166534;border-radius:10px;padding:1px 8px;font-size:0.74em">✅ Acceso</span>`,
    sin_licencia:   `<span style="background:#fef2f2;color:#991b1b;border-radius:10px;padding:1px 8px;font-size:0.74em">🚫 Sin licencia</span>`,
    sin_permiso:    `<span style="background:#f8fafc;color:#64748b;border-radius:10px;padding:1px 8px;font-size:0.74em">🔒 Sin permiso</span>`,
    error:          `<span style="background:#fef9c3;color:#92400e;border-radius:10px;padding:1px 8px;font-size:0.74em">⚠️ Error</span>`,
    precisa_params: `<span style="background:#dbeafe;color:#1d4ed8;border-radius:10px;padding:1px 8px;font-size:0.74em">ℹ️ Requiere params</span>`,
  };
  const noBadge = `<span style="background:#f1f5f9;color:#94a3b8;border-radius:10px;padding:1px 8px;font-size:0.74em">⬜ No probado</span>`;
  return Object.entries(cat).map(([mod,md]) => {
    const rows = (md.clases||[]).map(cls => {
      const ops = (md.clases_operaciones||{})[cls]||[];
      const desc = (md.clases_desc||{})[cls]||{};
      const drC = dr?.clases?.[cls];
      const badge = drC?(BADGE[drC.estado]||noBadge):noBadge;
      const tot = drC?.total_registros!=null?`<span style="font-size:0.72em;color:#3b82f6;margin-left:4px">${drC.total_registros} reg.</span>`:'';
      const causa = drC?.causa_real||'';
      const sondaBtn = causa==='requiere_parametros'||causa===''||!drC
        ? `<button onclick="event.stopPropagation();ApiExplorerModule.doSondaClase('${cls}')"
            title="Prueba exhaustiva solo lectura — varios params"
            style="border:1px solid #3b82f6;background:#eff6ff;color:#1d4ed8;border-radius:8px;padding:2px 7px;cursor:pointer;font-size:0.71em;white-space:nowrap">🔬 Sondear</button>`
        : '';
      return `<div style="display:flex;align-items:center;gap:8px;padding:5px 12px;border-bottom:1px solid #f8fafc">
        <span onclick="ApiExplorerModule.setInspectorClase('${cls}')" style="display:flex;align-items:center;gap:8px;flex:1;cursor:pointer"
          onmouseover="this.style.opacity='0.7'" onmouseout="this.style.opacity='1'">
          <span style="font-size:0.88em;min-width:22px">${desc.emoji||'📦'}</span>
          <span style="font-size:0.84em;font-weight:500;flex:1">${cls}</span>
          ${badge}${tot}
          <span style="font-size:0.72em;color:#94a3b8">${ops.length} ops →</span>
        </span>
        ${sondaBtn}
      </div>`;
    }).join('');
    const docB = md.doc_status==='confirmado'
      ? `<span style="font-size:0.71em;color:#166534;background:#dcfce7;border-radius:8px;padding:1px 6px">✅ Confirmado</span>`
      : `<span style="font-size:0.71em;color:#92400e;background:#fef9c3;border-radius:8px;padding:1px 6px">⚠️ Parcial</span>`;
    return `<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;margin-bottom:10px;overflow:hidden">
      <div style="background:#f8fafc;padding:9px 14px;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;gap:8px">
        <span style="font-size:1.1em">${md.emoji||'📦'}</span>
        <span style="font-weight:600;font-size:0.88em">${mod}</span>
        <span style="font-size:0.77em;color:#64748b;flex:1">${md.desc||''}</span>
        ${docB}
      </div>${rows}</div>`;
  }).join('');
}



// ── Inspector: POR CLASE (parte 1: selector + cabecera + ops + permisos) ──────
function _inspClase(cat, cf, dr, isCls) {
  const allCls=Object.values(cat).flatMap(m=>m.clases||[]);
  const cls=isCls||allCls[0];
  const drC=dr?.clases?.[cls];
  const camposDoc=(cf.campos_clase||{})[cls]||[];
  const camposReal=drC?.campos_reales||[];
  const muestra=drC?.muestra||[];
  let modName='',clsDesc={};
  Object.entries(cat).forEach(([m,md])=>{if((md.clases||[]).includes(cls)){modName=m;clsDesc=(md.clases_desc||{})[cls]||{};}});
  const ops=(cat[modName]?.clases_operaciones||{})[cls]||[];

  const sel=`<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px">${allCls.map(c=>`<button onclick="ApiExplorerModule.setInspectorClase('${c}')" style="padding:3px 9px;border:1px solid ${c===cls?'#3b82f6':'#e2e8f0'};background:${c===cls?'#3b82f6':'white'};color:${c===cls?'white':'#64748b'};border-radius:10px;cursor:pointer;font-size:0.74em">${c}</button>`).join('')}</div>`;

  const stBg={con_permiso:'#dcfce7',sin_licencia:'#fef2f2',sin_permiso:'#f8fafc',error:'#fef9c3',precisa_params:'#dbeafe'};
  const stCl={con_permiso:'#166534',sin_licencia:'#991b1b',sin_permiso:'#64748b',error:'#92400e',precisa_params:'#1d4ed8'};
  const stLb={con_permiso:'✅ Acceso',sin_licencia:'🚫 Sin licencia',sin_permiso:'🔒 Sin permiso',error:'⚠️ Diagnóstico',precisa_params:'ℹ️ Requiere parámetros'};

  // Diagnóstico detallado cuando el servidor devolvió código inesperado
  let diagH='';
  if(drC && drC.estado==='error') {
    const rows=[['permiso',drC.permiso_code,drC.permiso_raw],['info',drC.info_code,drC.info_raw],['browse',drC.browse_code,drC.browse_raw]].filter(([,,r])=>r!=null);
    const cBg=c=>c===0?'#dcfce7':c===1?'#fef2f2':c===2?'#f1f5f9':'#fef9c3';
    const cCl=c=>c===0?'#166534':c===1?'#991b1b':c===2?'#64748b':'#92400e';
    diagH=`<div style="background:#fef9c3;border:1px solid #fde68a;border-radius:10px;padding:12px 14px;margin-bottom:10px">
      <p style="margin:0 0 6px;font-weight:600;font-size:0.85em;color:#92400e">⚠️ Diagnóstico — respuesta real del servidor</p>
      ${drC.error?`<p style="margin:0 0 6px;font-size:0.79em;color:#78350f">${drC.error}</p>`:''}
      ${drC.nota_permiso?`<p style="margin:0 0 6px;font-size:0.79em;color:#166534;background:#dcfce7;border-radius:5px;padding:3px 8px">ℹ️ ${drC.nota_permiso}</p>`:''}
      <table style="width:100%;border-collapse:collapse;font-size:0.77em;margin-bottom:6px">
        <thead><tr style="background:#fde68a"><th style="padding:3px 8px;text-align:left">Op</th><th style="padding:3px 8px">code</th><th style="padding:3px 8px;text-align:left">Respuesta servidor</th></tr></thead>
        <tbody>${rows.map(([op,code,raw])=>`<tr style="border-bottom:1px solid #fde68a">
          <td style="padding:3px 8px;font-family:monospace;font-weight:600">${op}</td>
          <td style="padding:3px 8px;text-align:center"><span style="background:${cBg(code)};color:${cCl(code)};border-radius:4px;padding:1px 6px;font-weight:700">${code??'—'}</span></td>
          <td style="padding:3px 8px;font-family:monospace;font-size:0.87em;color:#475569;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${JSON.stringify(raw||{}).replace(/"/g,'&quot;')}">${JSON.stringify(raw||{}).slice(0,100)}${JSON.stringify(raw||{}).length>100?'…':''}</td>
          </tr>`).join('')}
        </tbody></table>
      <details style="font-size:0.78em"><summary style="cursor:pointer;color:#92400e">Ver JSON completo</summary>
        ${rows.map(([op,,raw])=>`<p style="margin:4px 0 2px;font-weight:600;color:#92400e">${op}:</p><pre style="background:#fff7ed;border-radius:4px;padding:6px;overflow:auto;max-height:110px;color:#1e293b;font-size:0.9em">${JSON.stringify(raw,null,2)}</pre>`).join('')}
      </details></div>`;
  }

  const hdr=`<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;margin-bottom:10px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
      <span style="font-size:1.4em">${clsDesc.emoji||'📦'}</span>
      <div style="flex:1"><p style="margin:0;font-weight:700;font-size:0.95em">${cls}</p>
        <p style="margin:2px 0 0;font-size:0.79em;color:#64748b">${clsDesc.desc||''}</p></div>
      <span style="background:${drC?stBg[drC.estado]||'#f1f5f9':'#f1f5f9'};color:${drC?stCl[drC.estado]||'#94a3b8':'#94a3b8'};border-radius:8px;padding:3px 10px;font-size:0.79em">
        ${drC?stLb[drC.estado]||'':'⬜ No probado'}</span></div>
    ${clsDesc.notas?`<div style="background:#f0f9ff;border-left:3px solid #38bdf8;border-radius:0 5px 5px 0;padding:5px 9px;font-size:0.79em;color:#0369a1">💡 ${clsDesc.notas}</div>`:''}
  </div>`;

  const ROP={browse:0,read:0,permiso:0,info:0,new:1,edit:1,cancel:0,write:2,imputaPro:2,delete:3};
  const RC=['#16a34a','#ca8a04','#ea580c','#dc2626'];
  const opsH=`<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;margin-bottom:10px">
    <p style="margin:0 0 8px;font-weight:600;font-size:0.84em">Operaciones disponibles</p>
    <div style="display:flex;flex-wrap:wrap;gap:5px">
      ${ops.map(op=>{const r=ROP[op]||0;const p=drC?.permiso_ops?.[op];const pb=p===true?'✅':p===false?'🔒':'';
        return `<div style="border:1px solid #e2e8f0;border-left:3px solid ${RC[r]};border-radius:6px;padding:4px 10px;font-size:0.79em;background:#f8fafc"><strong>${op}</strong> ${pb}<br><span style="color:#64748b;font-size:0.82em">${['Lectura','Temporal','Escritura','Destructivo'][r]}</span></div>`;
      }).join('')}
    </div></div>`;

  const permH=(drC?.permiso_ops&&Object.keys(drC.permiso_ops).length)?
    `<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;margin-bottom:10px">
    <p style="margin:0 0 8px;font-weight:600;font-size:0.84em">Permisos reales del servidor</p>
    ${drC.nota_permiso?`<p style="margin:0 0 6px;font-size:0.79em;color:#166534">ℹ️ ${drC.nota_permiso}</p>`:''}
    <div style="display:flex;flex-wrap:wrap;gap:5px">${Object.entries(drC.permiso_ops).map(([op,v])=>`<span style="background:${v?'#dcfce7':'#fef2f2'};color:${v?'#166534':'#991b1b'};border-radius:6px;padding:3px 10px;font-size:0.8em">${v?'✅':'❌'} ${op}</span>`).join('')}</div></div>` : '';

  // ── Fix: code=6 no es error — es normal para clases que piden parámetros ─────
  const causaCls = drC?.causa_real||'';
  const browseEsNormal = causaCls==='requiere_parametros' || causaCls==='acceso_confirmado' || drC?.browse_error_code===6;

  // code=6 es NORMAL (clase necesita parámetros) — mostrar azul informativo, no rojo
  const browseErrH2 = browseEsNormal
    ? (drC?.browse_error_code===6 ? `<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:7px 12px;margin-bottom:10px;font-size:0.8em;color:#1d4ed8">🔵 browse sin filtros→code=6 (normal — clase necesita parámetros). Usa el botón 🔬 Sondear para obtener datos reales.</div>` : '')
    : ((drC?.browse_error||drC?.browse_error_code!=null) ? `<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:0.8em;color:#991b1b">⚠️ browse: ${drC?.browse_error||''} ${drC?.browse_error_msg||''} ${drC?.browse_error_code!=null?`(code=${drC.browse_error_code})`:''}</div>` : '');

  const browseErrH=(drC?.browse_error||drC?.browse_error_code!=null)?`<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:0.8em;color:#991b1b">⚠️ browse: ${drC.browse_error||''} ${drC.browse_error_msg||''} ${drC.browse_error_code!=null?`(code=${drC.browse_error_code})`:''}
  </div>`:'';
  // Panel de prueba rápida — valores pre-rellenados con datos reales cuando existen
  const sondaPanel = `<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:12px 14px;margin-bottom:10px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <p style="margin:0;font-weight:600;font-size:0.84em;color:#166534">🔬 Probar esta clase con datos reales</p>
      <span style="font-size:0.74em;color:#64748b">Solo lectura — sin escrituras</span>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <button onclick="ApiExplorerModule.doSondaClase('${cls}')" class="btn primary" style="font-size:0.82em;background:#16a34a;border-color:#16a34a">
        🔬 Sondear con múltiples params
      </button>
      <button onclick="ApiExplorerModule.setInspectorTab('conexion');setTimeout(()=>{const s=document.querySelector('#ae-modulo');if(s){const e=new Event('change');const opts=[...s.options];const i=opts.findIndex(o=>o.value.toLowerCase().includes('${modName.toLowerCase().split(' ')[0]}'));if(i>=0){s.selectedIndex=i;s.dispatchEvent(e);}const sc=document.querySelector('#ae-clase');if(sc){const j=[...sc.options].findIndex(o=>o.value==='${cls}');if(j>=0){sc.selectedIndex=j;sc.dispatchEvent(new Event('change'));}}}})" 
        class="btn secondary" style="font-size:0.82em" title="Ir al Explorador con esta clase pre-seleccionada">
        ⚙️ Abrir en Explorador
      </button>
    </div>
  </div>`;


  return sel+hdr+diagH+opsH+permH+browseErrH2+sondaPanel+_inspClasetabla(drC,camposDoc,camposReal)+_inspClasemuestra(drC,muestra);
}



// ── Inspector: tabla campos y muestra ─────────────────────────
function _inspClasetabla(drC, camposDoc, camposReal) {
  const rM={};camposReal.forEach(f=>{rM[(f.nombre||f.name||f.n||'').toUpperCase()]=f;});
  const dM={};camposDoc.forEach(f=>{dM[(f.n||'').toUpperCase()]=f;});
  const allK=[...new Set([...Object.keys(dM),...Object.keys(rM)])];
  if(!allK.length) return '';
  return `<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;margin-bottom:10px">
    <p style="margin:0 0 8px;font-weight:600;font-size:0.84em">Campos documentados vs reales
      <span style="font-size:0.78em;font-weight:400;color:${camposReal.length?'#3b82f6':'#94a3b8'};margin-left:5px">
        ${camposReal.length?camposReal.length+' campos reales del servidor':'ejecuta Descubrir todo para ver los reales'}</span>
    </p>
    <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:0.77em">
      <thead><tr style="background:#f8fafc">
        <th style="padding:4px 8px;border-bottom:1px solid #e2e8f0">Campo</th>
        <th style="padding:4px 8px;text-align:center;border-bottom:1px solid #e2e8f0">Tipo doc</th>
        <th style="padding:4px 8px;text-align:center;border-bottom:1px solid #e2e8f0">Tipo real</th>
        <th style="padding:4px 8px;text-align:center;border-bottom:1px solid #e2e8f0">Req</th>
        <th style="padding:4px 8px;border-bottom:1px solid #e2e8f0">Descripción</th>
        <th style="padding:4px 8px;text-align:center;border-bottom:1px solid #e2e8f0">≡</th>
      </tr></thead><tbody>
      ${allK.map(k=>{const d=dM[k],r=rM[k],ed=!!d,er=!!r;
        const est=ed&&er?'✅':ed?'🟡':'🔵',bg=ed&&er?'':ed?'#fefce8':'#f0f9ff';
        return `<tr style="border-bottom:1px solid #f8fafc;background:${bg}">
          <td style="padding:3px 7px;font-family:monospace;font-weight:${d?.req?700:400}">${(d?.n||k).toLowerCase()}${d?.req?' <span style="color:#dc2626">*</span>':''}</td>
          <td style="padding:3px 7px;text-align:center;color:#64748b">${d?.tipo||'—'}</td>
          <td style="padding:3px 7px;text-align:center;color:#3b82f6">${r?.tipo||r?.type||'—'}</td>
          <td style="padding:3px 7px;text-align:center">${d?.req?'✱':''}</td>
          <td style="padding:3px 7px;color:#475569;max-width:250px">${d?.desc||''}</td>
          <td style="padding:3px 7px;text-align:center">${est}</td>
        </tr>`;
      }).join('')}
      </tbody></table>
      <p style="margin:5px 0 0;font-size:0.74em;color:#94a3b8">✅ Doc y servidor  🟡 Solo en doc  🔵 Solo en servidor</p>
    </div></div>`;
}
function _inspClasemuestra(drC, muestra) {
  if(!muestra.length) return '';
  const keys=Object.keys(muestra[0]);
  return `<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;margin-bottom:10px">
    <p style="margin:0 0 7px;font-weight:600;font-size:0.84em">🟢 Datos reales de SQL Obras
      <span style="font-size:0.79em;font-weight:400;color:#16a34a;margin-left:5px">${muestra.length} registros mostrados / ${drC?.total_registros??'?'} totales</span>
    </p>
    <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:0.77em">
      <thead><tr style="background:#f0fdf4">${keys.map(k=>`<th style="padding:3px 8px;text-align:left;border-bottom:1px solid #e2e8f0;color:#166534;white-space:nowrap">${k}</th>`).join('')}</tr></thead>
      <tbody>${muestra.map(row=>`<tr style="border-bottom:1px solid #f8fafc">${keys.map(k=>`<td style="padding:3px 8px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${String(row[k]??'')}">${row[k]??'—'}</td>`).join('')}</tr>`).join('')}</tbody>
    </table></div></div>`;
}



// ── Inspector: OPERACIONES globales ───────────────────────────
function _inspOps(cf) {
  const ops=cf.operaciones_globales||{},rCfg=cf.riesgo||{};
  const RC=['#16a34a','#ca8a04','#ea580c','#dc2626'],RB=['#f0fdf4','#fefce8','#fff7ed','#fef2f2'];
  return `<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:14px">
    <p style="margin:0 0 4px;font-weight:600;font-size:0.9em">Operaciones globales — API mPYME v1.2</p>
    <p style="margin:0 0 12px;font-size:0.79em;color:#64748b">Disponibles en cualquier clase. Parámetros específicos varían por clase.</p>
    ${Object.entries(ops).map(([opN,op])=>{const r=op.riesgo||0,rc=rCfg[String(r)]||{};
      return `<details style="margin-bottom:6px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">
        <summary style="padding:9px 14px;background:#f8fafc;cursor:pointer;display:flex;align-items:center;gap:10px;list-style:none">
          <span style="background:${RB[r]};color:${RC[r]};border-radius:4px;padding:2px 8px;font-size:0.72em;font-weight:600;white-space:nowrap">${rc.emoji||''} ${rc.label||''}</span>
          <code style="font-size:0.88em;font-weight:700">${opN}</code>
          <span style="font-size:0.79em;color:#475569;flex:1">${op.desc}</span>
          <span style="color:#94a3b8;font-size:0.75em">▾</span>
        </summary>
        <div style="padding:10px 14px;border-top:1px solid #f1f5f9">
          ${op.notas?`<div style="background:#f0f9ff;border-left:3px solid #38bdf8;border-radius:0 5px 5px 0;padding:5px 9px;font-size:0.79em;color:#0369a1;margin-bottom:8px">💡 ${op.notas}</div>`:''}
          ${(op.params_req||[]).length?`<p style="font-size:0.77em;font-weight:600;color:#dc2626;margin:0 0 4px">Requeridos:</p>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px">${(op.params_req||[]).map(p=>`<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:5px;padding:3px 8px;font-size:0.75em"><code>${p.n}</code> <span style="color:#94a3b8">${p.tipo}</span><br><span style="color:#64748b">${p.desc}</span></div>`).join('')}</div>`:''}
          ${(op.params_opt||[]).length?`<p style="font-size:0.77em;font-weight:600;color:#64748b;margin:0 0 4px">Opcionales:</p>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px">${(op.params_opt||[]).map(p=>`<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:5px;padding:3px 8px;font-size:0.75em"><code>${p.n}</code> <span style="color:#94a3b8">${p.tipo}</span><br><span style="color:#64748b">${p.desc}</span></div>`).join('')}</div>`:''}
          ${op.ejemplo_raw?`<details style="margin-top:4px"><summary style="cursor:pointer;font-size:0.76em;color:#64748b">Ver ejemplo raw</summary>
            <code style="display:block;background:#1e293b;color:#e2e8f0;padding:7px 10px;border-radius:5px;font-size:0.75em;margin-top:4px;overflow-x:auto;white-space:pre-wrap">${op.ejemplo_raw}</code></details>`:''}
        </div></details>`;
    }).join('')}</div>`;
}

// ── Inspector: CÓDIGOS de respuesta ───────────────────────────
function _inspCodes(cf) {
  const codes=cf.codigos_respuesta||{};
  return `<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:14px">
    <p style="margin:0 0 4px;font-weight:600;font-size:0.9em">Códigos de respuesta — API mPYME v1.2</p>
    <p style="margin:0 0 12px;font-size:0.79em;color:#64748b">El campo <code>code</code> siempre aparece en la respuesta JSON.</p>
    <table style="width:100%;border-collapse:collapse;font-size:0.84em">
      <thead><tr style="background:#f8fafc">
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #e2e8f0;width:60px">Code</th>
        <th style="padding:6px 10px;text-align:center;border-bottom:1px solid #e2e8f0;width:50px">Icono</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #e2e8f0">Significado</th>
      </tr></thead><tbody>
      ${Object.entries(codes).map(([c,v])=>`<tr style="border-bottom:1px solid #f8fafc">
        <td style="padding:6px 10px;font-family:monospace;font-weight:700;font-size:1.05em;color:${c==='0'?'#166534':c==='-1'?'#991b1b':'#475569'}">${c}</td>
        <td style="padding:6px 10px;font-size:1.3em;text-align:center">${v.icon}</td>
        <td style="padding:6px 10px;color:#475569">${v.desc}</td>
      </tr>`).join('')}
      </tbody></table>
    <div style="margin-top:12px;background:#f0f9ff;border-radius:6px;padding:9px 12px;font-size:0.79em;color:#0369a1">
      💡 <strong>code=0</strong> → éxito. <strong>code≠0</strong> con HTTP 200 → operación fallida con ese código.
      <strong>code=-1</strong> → error de conexión o excepción del servidor.
    </div></div>`;
}


// ── Inspector: INFORME multi-nivel con Perfil + Nivel ────────────
const _PERFILES = {
  gerente:       {label:"Gerente / Dirección",  emoji:"📊", desc:"Resumen ejecutivo. Sin tecnicismos."},
  ingeniero:     {label:"Ingeniero / Técnico",  emoji:"🔧", desc:"Detalle de clases, operaciones y campos."},
  sas:           {label:"Administración / SAS", emoji:"📋", desc:"Permisos y configuración. Qué funciona."},
  almacen:       {label:"Almacén / Compras",    emoji:"📦", desc:"Artículos, proveedores, albaranes, facturas."},
  operario:      {label:"Operario / Campo",     emoji:"👷", desc:"Obras, partidas, utilizados. Uso diario."},
  mantenimiento: {label:"Mantenimiento / SAT",  emoji:"🛠️", desc:"Reparaciones, equipos, instalaciones."},
  desarrollador: {label:"Desarrollador",        emoji:"💻", desc:"Todo: campos, códigos, raw JSON."},
};
const _NIVELES = {
  principiante: {label:"Principiante", emoji:"🟢", desc:"Sin términos técnicos. Solo lo esencial."},
  normal:       {label:"Normal",       emoji:"🔵", desc:"Lenguaje accesible con algo de detalle."},
  avanzado:     {label:"Avanzado",     emoji:"🟡", desc:"Operaciones, causas, registros. Sin raw."},
  tecnico:      {label:"Técnico",      emoji:"🟠", desc:"Campos reales, códigos exactos, causas."},
  raw:          {label:"Raw / Debug",  emoji:"🔴", desc:"JSON completo del discover_all."},
};

function _inspInforme() {
  const isMock = _state.status && _state.status.use_mock;
  const origenNote = isMock
    ? `<div style="background:#dbeafe;border-left:3px solid #3b82f6;padding:6px 12px;border-radius:4px;font-size:0.8em;color:#1d4ed8;margin-bottom:10px">🔵 Modo BD Simulada — el informe refleja datos simulados, no la licencia real.</div>`
    : `<div style="background:#dcfce7;border-left:3px solid #16a34a;padding:6px 12px;border-radius:4px;font-size:0.8em;color:#166534;margin-bottom:10px">🟢 API Real — el informe refleja lo que vuestra licencia permite realmente.</div>`;

  // Chips de perfil
  let perfilChips = Object.entries(_PERFILES).map(([k,v])=>
    `<button id="chip-p-${k}" onclick="ApiExplorerModule.setPerfilInforme('${k}')"
      title="${v.desc}"
      style="border:2px solid #e2e8f0;background:#f8fafc;border-radius:20px;padding:5px 12px;cursor:pointer;font-size:0.82em;transition:all .15s">
      ${v.emoji} ${v.label}</button>`).join('');

  // Chips de nivel
  let nivelChips = Object.entries(_NIVELES).map(([k,v])=>
    `<button id="chip-n-${k}" onclick="ApiExplorerModule.setNivelInforme('${k}')"
      title="${v.desc}"
      style="border:2px solid #e2e8f0;background:#f8fafc;border-radius:20px;padding:5px 12px;cursor:pointer;font-size:0.82em;transition:all .15s">
      ${v.emoji} ${v.label}</button>`).join('');

  return `<div>
    ${origenNote}
    <div style="background:#fef9c3;border-left:3px solid #fbbf24;padding:7px 12px;border-radius:6px;font-size:0.81em;color:#92400e;margin-bottom:14px">
      ℹ️ El informe usa los datos del <strong>último Descubrir todo</strong>. Si no lo has ejecutado aún, hazlo primero en la sub-pestaña Resumen.
    </div>

    <div style="background:white;border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin-bottom:14px">
      <div style="margin-bottom:10px">
        <p style="margin:0 0 6px;font-size:0.85em;font-weight:700;color:#374151">👤 Perfil — ¿Para quién es el informe?</p>
        <div id="ae-perfil-chips" style="display:flex;flex-wrap:wrap;gap:6px">${perfilChips}</div>
        <p id="ae-perfil-desc" style="margin:6px 0 0;font-size:0.78em;color:#64748b"></p>
      </div>
      <hr style="border:none;border-top:1px solid #f1f5f9;margin:10px 0">
      <div>
        <p style="margin:0 0 6px;font-size:0.85em;font-weight:700;color:#374151">📏 Nivel — ¿Cuánto detalle?</p>
        <div id="ae-nivel-chips" style="display:flex;flex-wrap:wrap;gap:6px">${nivelChips}</div>
        <p id="ae-nivel-desc" style="margin:6px 0 0;font-size:0.78em;color:#64748b"></p>
      </div>
    </div>

    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button onclick="ApiExplorerModule.doInformePerfil()" class="btn primary" style="font-size:0.88em">📑 Generar informe por perfil/nivel</button>
      <button onclick="ApiExplorerModule.doInforme()" class="btn secondary" style="font-size:0.84em">📋 Informe completo (todos)</button>
      <button onclick="ApiExplorerModule.exportarInforme()" class="btn secondary" style="font-size:0.84em">💾 Exportar TXT</button>
    </div>
    <div id="ae-informe-result" style="margin-top:8px"></div>
  </div>`;
}

function renderExplorador(s, modulos, mod, clases, cls, ops, op, riesgo, RLBL) {
  if (!s.session_active) return noSesion();
  const pf = renderParamFields(cls, op);
  const rc = ["#28a745","#ffc107","#fd7e14","#dc3545"][riesgo];
  return `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px">
    <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">📦 Modulo</label>
      <select id="ae-modulo" class="form-control" onchange="ApiExplorerModule.onModuloChange()" style="width:100%">
        ${modulos.map(m=>`<option value="${m}" ${m===mod?'selected':''}>${m}</option>`).join('')}
      </select></div>
    <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">🗂 Clase/Objeto &nbsp;<button onclick="ApiExplorerModule.toggleInfoClase()" style="border:none;background:none;cursor:pointer;color:#3b82f6;font-size:0.82em;padding:0">ℹ️ info</button></label>
      <select id="ae-clase" class="form-control" onchange="ApiExplorerModule.onClaseChange()" style="width:100%">
        ${Object.keys(clases).map(c=>{const i=CLASE_INFO[c];return`<option value="${c}" ${c===cls?'selected':''}>${i?i.emoji+' ':''} ${c} — ${i?i.desc:''}</option>`;}).join('')}
      </select></div>
    <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">⚙️ Operacion &nbsp;<button onclick="ApiExplorerModule.toggleInfoOp()" style="border:none;background:none;cursor:pointer;color:#3b82f6;font-size:0.82em;padding:0">ℹ️ info</button></label>
      <select id="ae-op" class="form-control" onchange="ApiExplorerModule.onOpChange()" style="width:100%">
        ${ops.map(o=>`<option value="${o}" ${o===op?'selected':''}>${o}</option>`).join('')}
      </select>
      ${!s.modo_escritura&&(clases[cls]||[]).length>ops.length?`<p style="font-size:0.74em;color:#94a3b8;margin:2px 0">Activa escritura (tab 🟠) para ver operaciones de escritura</p>`:''}
    </div>
  </div>
  <div id="ae-info-clase" style="display:none">${infoClase(cls)}</div>
  <div id="ae-info-op" style="display:none">${infoOp(op)}</div>
  <div style="background:#f8fafc;border-left:4px solid ${rc};border-radius:0 6px 6px 0;padding:8px 14px;margin-bottom:12px;font-size:0.88em">
    ${RLBL[riesgo]} | <code style="background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:4px">${cls}.${op}</code>
  </div>
  ${pf?`<div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:14px;margin-bottom:12px">
    <h4 style="margin:0 0 10px;font-size:0.88em;color:#374151">Parametros <span style="color:#dc3545;font-size:0.8em">* = requerido</span></h4>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">${pf}</div></div>`
    :`<div style="background:#f8fafc;border-radius:6px;padding:8px 14px;color:#94a3b8;font-size:0.85em;margin-bottom:12px">Sin parametros adicionales.</div>`}
  ${riesgo>=2
    ?`<div style="background:#fff3e0;border:1px solid #fbbf24;border-radius:8px;padding:12px;margin-bottom:12px">
      <p style="margin:0 0 8px;color:#92400e;font-weight:600;font-size:0.9em">⚠️ ESCRITURA REAL — Modifica SQL Obras permanentemente.</p>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <input id="ae-confirm-word" type="text" class="form-control" placeholder="Escribe exactamente: CONFIRMAR" style="flex:1;min-width:180px">
        <button onclick="ApiExplorerModule.doEjecutar(true)" class="btn primary" style="background:#fd7e14;border-color:#fd7e14;white-space:nowrap">🟠 Ejecutar ${cls}.${op}</button>
      </div></div>`
    :`<button onclick="ApiExplorerModule.doEjecutar(false)" class="btn primary">▶️ Probar ${cls}.${op}</button>`}
  <div id="ae-exec-result" style="margin-top:14px"></div>`;
}


function renderPermisos(CLASSES, ops_cols, permisoR) {
  const rows=CLASSES.map(c=>{const r=permisoR[c];const i=CLASE_INFO[c];
    return`<tr style="border-bottom:1px solid #f1f5f9"><td style="font-family:monospace;padding:5px 8px;font-size:0.85em;font-weight:600">${i?i.emoji:''} ${c}</td><td style="font-size:0.78em;color:#64748b;padding:5px 4px">${i?i.desc:''}</td><td style="text-align:center;padding:4px">${r?estadoIcon(r.estado):'⬜'}</td>${ops_cols.map(o=>{if(!r)return`<td style="text-align:center;color:#cbd5e1">—</td>`;const v=r.json?r.json[o]:undefined;return`<td style="text-align:center;padding:4px">${v===true?'✅':v===false?'❌':'—'}</td>`;}).join('')}</tr>`;}).join('');
  return `<div style="margin-bottom:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <button onclick="ApiExplorerModule.doAuditarTodo()" class="btn primary">🚀 Auditar TODAS las clases</button>
    <span style="font-size:0.82em;color:#64748b">Ejecuta permiso para cada clase documentada en la API mPYME v1.2</span>
  </div>
  <div id="ae-permiso-progress" style="display:none;margin-bottom:12px">
    <div style="background:#e2e8f0;border-radius:4px;height:8px"><div id="ae-permiso-bar" style="background:#3b82f6;border-radius:4px;height:8px;width:0%;transition:width 0.2s"></div></div>
    <p id="ae-permiso-msg" style="font-size:0.78em;color:#64748b;margin:4px 0"></p>
  </div>
  <div id="ae-permiso-single-result" style="margin-bottom:12px"></div>
  <div style="overflow-x:auto;border-radius:8px;border:1px solid #e2e8f0;background:white">
    <table style="width:100%;border-collapse:collapse"><thead style="background:#f8fafc"><tr style="border-bottom:2px solid #e2e8f0">
      <th style="text-align:left;padding:7px 8px;font-size:0.82em">Clase</th>
      <th style="text-align:left;padding:7px 4px;font-size:0.82em">Descripcion</th>
      <th style="text-align:center;padding:7px 4px;font-size:0.82em">Estado</th>
      ${ops_cols.map(o=>`<th style="text-align:center;padding:7px 4px;font-family:monospace;font-size:0.78em">${o}</th>`).join('')}
    </tr></thead><tbody>${rows}</tbody></table>
  </div>
  <div style="margin-top:14px;background:white;border-radius:8px;border:1px solid #e2e8f0;padding:12px"><div style="display:flex;gap:10px">
    <select id="ae-perm-cls" class="form-control" style="flex:1">${CLASSES.map(c=>{const i=CLASE_INFO[c];return`<option value="${c}">${i?i.emoji:''} ${c}</option>`;}).join('')}</select>
    <button onclick="ApiExplorerModule.doPermisoIndividual()" class="btn primary">🔍 Consultar permiso</button>
  </div></div>`;
}

function renderMatriz(catalogue, mat) {
  if(!Object.keys(catalogue).length) return `<p style="color:#64748b">Cargando catalogo...</p>`;
  let h=`<p style="color:#64748b;font-size:0.85em;margin-bottom:12px">⬜ no probado | ✅ OK | ❌ falla | 🔒 sin permiso | 🚫 sin licencia</p>`;
  Object.entries(catalogue).forEach(([m,cm])=>{
    const uo=[...new Set(Object.values(cm).flat())].sort();
    h+=`<details open style="margin-bottom:14px"><summary style="cursor:pointer;font-weight:600;padding:8px 0">${m}</summary>
    <div style="overflow-x:auto;margin-top:6px"><table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0">
      <thead style="background:#f8fafc"><tr>
        <th style="text-align:left;padding:6px 10px;font-size:0.82em">Clase</th>
        <th style="text-align:left;padding:6px 4px;font-size:0.82em">Descripcion</th>
        ${uo.map(o=>`<th style="text-align:center;font-family:monospace;font-size:0.78em;padding:6px 4px">${o}</th>`).join('')}
      </tr></thead>
      <tbody>${Object.entries(cm).map(([c,ops])=>{const i=CLASE_INFO[c];return`<tr style="border-bottom:1px solid #f1f5f9"><td style="font-family:monospace;padding:5px 10px;font-weight:600;font-size:0.85em">${i?i.emoji:''} ${c}</td><td style="font-size:0.78em;color:#64748b;padding:5px 4px">${i?i.desc:''}</td>${uo.map(o=>{if(!ops.includes(o))return`<td style="text-align:center;color:#e2e8f0;padding:4px">—</td>`;const e=mat[c]&&mat[c][o];return`<td style="text-align:center;padding:4px">${e?estadoIcon(e.estado):'⬜'}</td>`;}).join('')}</tr>`;}).join('')}</tbody>
    </table></div></details>`;
  });
  return h;
}

function renderHistorial(hist, resumen) {
  const cols = Object.keys(resumen).length;
  let h=`<div style="display:grid;grid-template-columns:repeat(${Math.min(cols,6)},1fr);gap:8px;margin-bottom:12px">
    ${Object.entries(resumen).map(([k,v])=>`<div style="background:white;border-radius:8px;border:1px solid #e2e8f0;padding:8px;text-align:center">
      <div style="font-size:1.3em;font-weight:700">${v}</div>
      <div style="font-size:0.72em;color:#64748b">${k}</div>
    </div>`).join('')}
  </div>
  <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:10px 14px;margin-bottom:10px;font-size:0.82em;color:#166534">
    💾 <strong>Persistencia total activada</strong> — Historial, sondas, discover y matriz se guardan en disco y sobreviven reinicios de DEVIA.
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
    <button onclick="ApiExplorerModule.doExportarTodo()" class="btn primary" style="font-size:0.84em">
      📤 Exportar todo (JSON completo)
    </button>
    <button onclick="ApiExplorerModule.doClearHistory()" class="btn secondary" style="font-size:0.84em">🗑️ Limpiar historial</button>
  </div>`;
  if(!hist.length) return h+`<div style="text-align:center;color:#64748b;padding:30px">Sin llamadas registradas aún. Ve al Explorador y ejecuta operaciones.</div>`;
  return h+hist.slice(0,100).map(r=>`<details style="margin-bottom:6px;background:white;border-radius:8px;border:1px solid #e2e8f0">
    <summary style="cursor:pointer;padding:9px 14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <span>${estadoIcon(r.estado)}</span>
      <code style="font-size:0.86em;background:#f1f5f9;padding:1px 6px;border-radius:4px">${r.clase}.${r.operacion}</code>
      <span style="color:#64748b;font-size:0.78em;margin-left:auto">${(r.timestamp||'').slice(0,19).replace('T',' ')} | ${r.duracion_ms}ms | ${r.use_mock?'🔵 Mock':'🟠 Real'}</span>
    </summary>
    <div style="padding:10px 14px;border-top:1px solid #f1f5f9">${renderResult(r)}</div>
  </details>`).join('');
}


function renderEscritura(s) {
  if(s.modo_escritura) return `<div style="background:#fff3e0;border:2px solid #fd7e14;border-radius:10px;padding:18px;margin-bottom:14px">
    <h3 style="margin:0 0 8px;color:#9a3412">⚠️ MODO ESCRITURA ACTIVO</h3>
    <p style="color:#64748b;margin:0 0 10px;font-size:0.9em">Puede modificar SQL Obras. Cada operacion requiere la palabra CONFIRMAR.</p>
    <button onclick="ApiExplorerModule.doEscritura(false)" class="btn secondary">🔒 Desactivar escritura</button>
  </div>
  <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px">
    <h3 style="margin:0 0 6px;font-size:0.95em">Prueba: proordutil — new → write / cancel</h3>
    <p style="font-size:0.82em;color:#64748b;margin:0 0 12px">Verifica si la licencia permite crear utilizados (costes reales imputados a proyectos).</p>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px">
      <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">codProyecto *</label><input id="wr-codProyecto" type="text" class="form-control" value="25/184" style="width:100%"></div>
      <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">codPartida *</label><input id="wr-codPartida" type="text" class="form-control" value="03.02" style="width:100%"></div>
      <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">tipo *</label><select id="wr-tipo" class="form-control" style="width:100%"><option value="M">M — Material</option><option value="R">R — Recurso</option></select></div>
    </div>
    <button onclick="ApiExplorerModule.doNew()" class="btn primary" style="margin-bottom:12px;font-size:0.88em">1️⃣ new — Crear objeto temporal</button>
    <div id="ae-wr-oid-section" style="display:none">
      <div id="ae-wr-oid-display"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:10px 0">
        <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">codArticulo *</label><input id="wr-codArticulo" type="text" class="form-control" value="1#100142" style="width:100%"></div>
        <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">cantidad *</label><input id="wr-cantidad" type="number" class="form-control" value="2" step="0.1" style="width:100%"></div>
        <div><label style="font-size:0.82em;color:#64748b;display:block;margin-bottom:3px">coste * (euros)</label><input id="wr-coste" type="number" class="form-control" value="35.10" step="0.01" style="width:100%"></div>
      </div>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <input id="wr-confirm" type="text" class="form-control" placeholder='Escribe "CONFIRMAR" para persistir en ERP' style="flex:1;min-width:200px">
        <button onclick="ApiExplorerModule.doWrite()" class="btn primary" style="background:#fd7e14;border-color:#fd7e14;white-space:nowrap">2️⃣ write — PERSISTE</button>
        <button onclick="ApiExplorerModule.doCancel()" class="btn secondary" style="white-space:nowrap">❌ cancel</button>
      </div>
    </div>
    <div id="ae-wr-result" style="margin-top:14px"></div>
  </div>`;
  return `<div style="background:#dcfce7;border:2px solid #86efac;border-radius:10px;padding:18px;margin-bottom:14px">
    <h3 style="margin:0 0 8px;color:#166534">🟢 MODO SOLO LECTURA</h3>
    <p style="color:#64748b;margin:0;font-size:0.9em">Sin riesgo de modificar datos.</p>
  </div>
  <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:18px">
    <h4 style="margin:0 0 8px">Activar modo escritura</h4>
    <p style="color:#64748b;font-size:0.88em;margin-bottom:10px">Solo para pruebas controladas. Cada escritura requiere confirmar con "CONFIRMAR".</p>
    <input id="ae-wr-confirm" type="text" class="form-control" placeholder="Escribe: ACTIVAR ESCRITURA" style="width:100%;margin-bottom:10px">
    <button onclick="ApiExplorerModule.doEscritura(true)" class="btn primary" style="background:#fd7e14;border-color:#fd7e14">🟠 Activar modo escritura</button>
  </div>`;
}


// ─── _renderInforme (parte 1/2) ──────────────────────────────
function _renderInforme(r) {
  const t=r.totales||{},s=r.secciones||{},d=r.detalles||{},apps=r.apps||[];
  const conA=s.con_acceso||[],reqP=s.requiere_parametros||[];
  const sinL=s.sin_licencia||[],sinP=s.sin_permiso||[];
  const cfgI=s.config_incompleta||[],ines=s.respuesta_inesperada||[];
  const cnt=`<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(98px,1fr));gap:7px;margin-bottom:13px">
    <div style="background:#dcfce7;border-radius:8px;padding:7px;text-align:center"><div style="font-size:1.2em">✅</div><b style="color:#166534">${t.con_acceso||0}</b><div style="font-size:0.7em;color:#166534">Confirmado</div></div>
    <div style="background:#dbeafe;border-radius:8px;padding:7px;text-align:center"><div style="font-size:1.2em">🔵</div><b style="color:#1e40af">${t.requiere_parametros||0}</b><div style="font-size:0.7em;color:#1e40af">Req. params</div></div>
    <div style="background:#fef2f2;border-radius:8px;padding:7px;text-align:center"><div style="font-size:1.2em">🚫</div><b style="color:#991b1b">${t.sin_licencia||0}</b><div style="font-size:0.7em;color:#991b1b">Sin licencia</div></div>
    <div style="background:#fef9c3;border-radius:8px;padding:7px;text-align:center"><div style="font-size:1.2em">🔒</div><b style="color:#92400e">${t.sin_permiso||0}</b><div style="font-size:0.7em;color:#92400e">Sin permiso</div></div>
    <div style="background:#f1f5f9;border-radius:8px;padding:7px;text-align:center;font-size:0.7em;color:#64748b"><div>${r.modo||''}</div><div>${r.timestamp||''}</div><div>${r.empresa||''}&nbsp;·&nbsp;${r.usuario||''}</div></div>
  </div>`;
  let n1=`<details open><summary style="cursor:pointer;font-weight:700;font-size:0.94em;padding:8px 0;color:#1e293b">👤 NIVEL 1 — Para cualquier persona</summary><div style="font-size:0.88em;padding:4px 0 8px">`;
  if(conA.length+reqP.length>0){
    n1+=`<p style="font-weight:600;color:#166534;margin:4px 0">✅ SÍ podemos hacer (probado):</p><ul style="margin:0 0 6px;padding-left:18px">`;
    conA.forEach(c=>{const e=d[c]||{};n1+=`<li style="color:#166534;margin:2px 0"><b>${e.desc||c}</b>${e.total_registros!=null?` <span style="color:#64748b;font-size:0.81em">· ${e.total_registros} regs</span>`:''}${e.operaciones&&e.operaciones.length?` <span style="color:#94a3b8;font-size:0.77em">(${e.operaciones.join(', ')})</span>`:''}</li>`;});
    reqP.forEach(c=>{const e=d[c]||{};n1+=`<li style="color:#1e40af;margin:2px 0"><b>${e.desc||c}</b> <span style="color:#64748b;font-size:0.81em">· requiere parámetros</span></li>`;});
    n1+=`</ul>`;
  }else{n1+=`<p style="color:#64748b">Sin acceso confirmado aún. Ejecuta 🚀 Descubrir todo primero.</p>`;}
  if(sinL.length+sinP.length+cfgI.length+ines.length>0){
    n1+=`<p style="font-weight:600;color:#991b1b;margin:7px 0 4px">❌ NO podemos hacer — causa exacta verificada:</p><ul style="margin:0;padding-left:18px">`;
    const _li=(c,ico,lab)=>{const e=d[c]||{};return`<li style="margin:2px 0"><b>${ico} ${e.desc||c}</b> <span style="font-size:0.8em;color:#64748b">— ${lab}</span><details style="font-size:0.79em"><summary style="color:#94a3b8;cursor:pointer">Detalle técnico</summary><span style="color:#475569">${e.causa_explicacion||''}</span></details></li>`;};
    sinL.forEach(c=>n1+=_li(c,'🚫','Sin licencia — no contratada con Distrito K'));
    sinP.forEach(c=>n1+=_li(c,'🔒','Sin permiso — usuario sin acceso en SQL Obras'));
    cfgI.forEach(c=>n1+=_li(c,'⚙️','Config incompleta — faltan valores en .env'));
    ines.forEach(c=>n1+=_li(c,'⚠️','Respuesta inesperada — posible error en la documentación'));
    n1+=`</ul>`;}
  n1+=`</div></details>`;
  // N2 — empleado
  let n2=`<details><summary style="cursor:pointer;font-weight:700;font-size:0.94em;padding:8px 0;color:#1e293b">👷 NIVEL 2 — Para el empleado</summary><div style="padding:4px 0 8px">`;
  apps.forEach(a=>{const ok=a.disponible;n2+=`<div style="border-left:4px solid ${ok?'#22c55e':'#cbd5e1'};background:${ok?'#f0fdf4':'#f8fafc'};border-radius:0 6px 6px 0;padding:9px 13px;margin:5px 0"><b style="color:${ok?'#166534':'#64748b'};font-size:0.87em">${ok?'✅':'⬜'} ${a.nombre}</b><p style="margin:3px 0;font-size:0.83em;color:#475569">${a.desc}</p><p style="margin:0;font-size:0.75em;color:#94a3b8">Requiere: ${(a.requiere||[]).join(' · ')}</p></div>`;});
  n2+=`</div></details>`;
  // N3 — técnico
  let n3=`<details><summary style="cursor:pointer;font-weight:700;font-size:0.94em;padding:8px 0;color:#1e293b">🔧 NIVEL 3 — Para el técnico</summary><div style="padding:4px 0 8px">`;
  [...conA,...reqP].forEach(c=>{const e=d[c]||{};const reg=e.total_registros;
    n3+=`<details style="margin:3px 0;border:1px solid #e2e8f0;border-radius:6px"><summary style="cursor:pointer;padding:7px 12px;font-weight:600;font-size:0.87em;color:#1e293b"><code style="background:#f1f5f9;padding:1px 5px;border-radius:3px">${c}</code>&nbsp;${e.desc||''}${reg!=null?`<span style="float:right;font-size:0.74em;color:#64748b;font-weight:400">${reg} regs</span>`:''}</summary><div style="padding:8px 14px;font-size:0.82em;color:#475569"><b>Causa:</b> <code style="background:#f1f5f9;padding:1px 4px;border-radius:3px">${e.causa_real||''}</code><br><b>Explicación:</b> ${e.causa_explicacion||''}<br>${e.operaciones&&e.operaciones.length?`<b>Ops:</b> <code>${e.operaciones.join(', ')}</code><br>`:''}${e.campos&&e.campos.length?`<b>Campos servidor:</b> <code style="font-size:0.88em">${e.campos.join(', ')}</code><br>`:''}${e.muestra_n>0?`<b>Muestra:</b> ${e.muestra_n} regs<br>`:''}<b>Códigos:</b> permiso=${e.permiso_code??'?'} browse=${e.browse_code??'?'} info=${e.info_code??'?'}</div></details>`;});
  n3+=`</div></details>`;
  // N4 — gerencia
  let n4=`<details><summary style="cursor:pointer;font-weight:700;font-size:0.94em;padding:8px 0;color:#1e293b">📊 NIVEL 4 — Para gerencia</summary><div style="padding:4px 0 8px">`;
  apps.forEach((a,i)=>{const ok=a.disponible;n4+=`<div style="background:${ok?'#ecfdf5':'#f8fafc'};border:1px solid ${ok?'#bbf7d0':'#e2e8f0'};border-radius:8px;padding:10px 14px;margin:5px 0"><b style="color:${ok?'#166534':'#64748b'};font-size:0.87em">${i+1}. ${a.nombre} — ${ok?'✅ DISPONIBLE AHORA':'⬜ Ampliar licencia'}</b><p style="margin:3px 0;font-size:0.83em;color:#1e293b">${a.desc}</p><p style="margin:0;font-size:0.75em;color:#94a3b8">Requiere: ${(a.requiere||[]).join(' · ')}</p></div>`;});
  n4+=`</div></details>`;
  // Ref. códigos
  const codes=`<details><summary style="cursor:pointer;font-weight:700;font-size:0.94em;padding:8px 0;color:#1e293b">🔢 Referencia de códigos mPYME</summary><table style="width:100%;border-collapse:collapse;font-size:0.81em;margin-top:4px"><thead><tr style="background:#f1f5f9"><th style="padding:5px 10px;text-align:left">Code</th><th style="padding:5px 10px;text-align:left">Significado</th><th style="padding:5px 10px;text-align:left">Acción</th></tr></thead><tbody><tr><td style="padding:4px 10px"><b>0</b></td><td>Éxito</td><td style="color:#166534">OK</td></tr><tr style="background:#f8fafc"><td style="padding:4px 10px"><b>1</b></td><td>Sin licencia</td><td style="color:#991b1b">Contactar Distrito K</td></tr><tr><td style="padding:4px 10px"><b>2</b></td><td>Sin permiso</td><td style="color:#c2410c">Revisar permisos SQL Obras</td></tr><tr style="background:#f8fafc"><td style="padding:4px 10px"><b>3</b></td><td>Error validación</td><td>Revisar parámetros</td></tr><tr><td style="padding:4px 10px"><b>5</b></td><td>Config incompleta</td><td>Completar .env</td></tr><tr style="background:#f8fafc"><td style="padding:4px 10px"><b>6</b></td><td>Requiere params</td><td style="color:#1e40af">Normal — la clase necesita datos</td></tr><tr><td style="padding:4px 10px"><b>10</b></td><td>No encontrado</td><td>Registro no existe</td></tr><tr style="background:#f8fafc"><td style="padding:4px 10px"><b>-1</b></td><td>Error red</td><td>Verificar URL y conexión</td></tr></tbody></table></details>`;
  // Botones
  const btns=`<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap"><button onclick="ApiExplorerModule.exportarInforme()" class="btn secondary" style="font-size:0.83em">💾 Exportar TXT</button><button onclick="document.querySelectorAll('#ae-informe-result details').forEach(el=>el.open=true)" class="btn secondary" style="font-size:0.83em">📂 Expandir todo</button><button onclick="document.querySelectorAll('#ae-informe-result details').forEach(el=>el.open=false)" class="btn secondary" style="font-size:0.83em">📁 Colapsar todo</button></div>`;
  return cnt+n1+n2+n3+n4+codes+btns;
}



// ── Render del plan de pruebas pendientes ─────────────────────────
function _renderPlan(r) {
  const obs = r.observaciones_fijas || [];
  const pendientes = r.pruebas_pendientes || [];
  const completadas = r.pruebas_completadas || [];
  const pBg = {'🔴':'#fef2f2','🟡':'#fef9c3','🟠':'#fff7ed','⚪':'#f8fafc'};
  const pCl = {'🔴':'#991b1b','🟡':'#92400e','🟠':'#9a3412','⚪':'#64748b'};

  // ── Contadores + barra de fases ──────────────────────────────────────
  const fases = r.fases || {};
  const f0 = fases.f0 || {label:'FASE 0',total:0,ok:0};
  const f1 = fases.f1 || {label:'FASE 1',total:0,ok:0};
  const f2 = fases.f2 || {label:'FASE 2',total:0,ok:0};
  const f3 = fases.f3 || {label:'FASE 3',total:0,ok:0};
  const investigar = r.investigar || [];

  let h = `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-bottom:10px">
    <div style="background:#fef2f2;border-radius:8px;padding:8px;text-align:center"><div style="font-size:1.2em">⏳</div><b style="color:#991b1b">${r.pendientes||0}</b><div style="font-size:0.7em;color:#991b1b">Pendientes</div></div>
    <div style="background:#dcfce7;border-radius:8px;padding:8px;text-align:center"><div style="font-size:1.2em">✅</div><b style="color:#166534">${completadas.length}</b><div style="font-size:0.7em;color:#166534">Completadas</div></div>
    <div style="background:#f1f5f9;border-radius:8px;padding:8px;text-align:center"><div style="font-size:1.2em">📊</div><b style="color:#475569">${r.total_pruebas||0}</b><div style="font-size:0.7em;color:#64748b">Total</div></div>
    ${r.discover_timestamp?`<div style="background:#f1f5f9;border-radius:8px;padding:8px;text-align:center;font-size:0.72em;color:#64748b"><div>📅 Discover</div><div>${r.discover_timestamp}</div><div>${r.empresa||''}</div></div>`:''}
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:12px">
    <div style="background:#fef2f2;border:2px solid #fca5a5;border-radius:6px;padding:8px 10px">
      <div style="font-size:0.75em;font-weight:700;color:#991b1b">🔴 FASE 0</div>
      <div style="font-size:0.79em;color:#475569;margin-top:2px">Clases code=6 con num=20 — necesitan param obligatorio desconocido</div>
      <div style="font-size:0.82em;color:#991b1b;margin-top:4px"><b>${f0.ok}/${f0.total}</b> desbloqueadas — ver sección abajo</div>
    </div>
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:8px 10px">
      <div style="font-size:0.75em;font-weight:700;color:#166534">🟢 FASE 1</div>
      <div style="font-size:0.79em;color:#475569;margin-top:2px">Browse simple (tablas maestras)</div>
      <div style="font-size:0.82em;color:#166534;margin-top:4px"><b>${f1.ok}/${f1.total}</b> — pulsa ▶ para ejecutar</div>
    </div>
    <div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:8px 10px">
      <div style="font-size:0.75em;font-weight:700;color:#92400e">🟡 FASE 2</div>
      <div style="font-size:0.79em;color:#475569;margin-top:2px">Necesitan codProyecto/codOrden real</div>
      <div style="font-size:0.82em;color:#92400e;margin-top:4px"><b>0/${f2.total}</b> — usar Explorador</div>
    </div>
    <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;padding:8px 10px">
      <div style="font-size:0.75em;font-weight:700;color:#9a3412">🟠 FASE 3</div>
      <div style="font-size:0.79em;color:#475569;margin-top:2px">new+cancel — no persiste en BD</div>
      <div style="font-size:0.82em;color:#9a3412;margin-top:4px"><b>0/${f3.total}</b> — usar Explorador</div>
    </div>
  </div>`;

  // Observaciones del servidor (hallazgos del JSON analizado)
  h += `<details open><summary style="cursor:pointer;font-weight:700;font-size:0.92em;padding:8px 0;color:#1e293b">🔍 Hallazgos del servidor (del análisis del JSON exportado)</summary><div style="padding:4px 0 8px">`;
  obs.forEach(o => {
    const bCol = o.icono==='✅'?'#22c55e':o.icono==='🚫'?'#dc2626':o.icono==='🔵'?'#3b82f6':o.icono==='🚀'?'#7c3aed':'#f59e0b';
    const bgObs = o.icono==='✅'?'#f0fdf4':o.icono==='🚫'?'#fef2f2':o.icono==='🔵'?'#eff6ff':o.icono==='🚀'?'#f5f3ff':'#fffbeb';
    h += `<div style="background:${bgObs};border-left:4px solid ${bCol};border-radius:0 6px 6px 0;padding:9px 13px;margin:5px 0">
      <b style="font-size:0.87em">${o.icono} ${o.titulo}</b>
      <p style="margin:3px 0;font-size:0.82em;color:#475569">${o.detalle}</p>
      <p style="margin:0;font-size:0.78em;color:#166534">→ ${o.accion}</p>
    </div>`;
  });
  h += `</div></details>`;

  // ── FASE 0: Clases code=6 — Investigar parámetro obligatorio ──────────
  if (investigar.length > 0) {
    h += `<details open><summary style="cursor:pointer;font-weight:700;font-size:0.92em;padding:8px 0;color:#991b1b">
      🔴 FASE 0 — Investigar parámetro obligatorio (${investigar.length} clases bloqueadas por code=6)
    </summary><div style="padding:4px 0 10px">
    <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:10px 14px;margin-bottom:10px;font-size:0.82em;color:#7f1d1d">
      <b>¿Por qué aparecen aquí?</b> Estas clases devuelven <code>code=6</code> con cualquier parámetro genérico
      (num, nReg, ejercicio, soloActivos, activo, todos, tipo...).
      El servidor exige un <b>identificador de negocio real</b> (codProyecto, codOrden).
      <br><br>
      <b>🚀 Opción automática:</b> el botón de abajo prueba <b>más de 50 variantes</b> de parámetros
      de una sola vez y te muestra cuál funciona (si existe alguna sin identificador previo).
    </div>
    <div style="margin-bottom:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <button id="btn-sonda-masiva" onclick="ApiExplorerModule.doSondaMasivaFase0()"
        class="btn primary" style="font-size:0.87em;padding:8px 16px;background:#991b1b;border-color:#991b1b">
        🚀 Sonda masiva automática (>50 variantes)
      </button>
      <button id="btn-ids-reales" onclick="ApiExplorerModule.doObtenerIdsReales()"
        class="btn primary" style="font-size:0.87em;padding:8px 16px;background:#1d4ed8;border-color:#1d4ed8">
        🔍 Obtener IDs reales de la BD
      </button>
      <button onclick="ApiExplorerModule.descargarInformeCompleto()"
        class="btn secondary" style="font-size:0.84em">
        📄 Descargar informe completo TXT
      </button>
      <span style="font-size:0.78em;color:#64748b">Solo lectura · Sin modificar BD · ~30-60 seg</span>
    </div>
    <div id="ae-plan-result-fase0"></div>
    <div id="ae-ids-reales-result"></div>`;
    investigar.forEach(inv => {
      const cands = inv.candidatos || [];
      const sondaCands = inv.candidatos_sonda || [];
      h += `<div style="background:#fff;border:1px solid #fca5a5;border-radius:8px;padding:10px 14px;margin:6px 0">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <span style="background:#fef2f2;color:#991b1b;border-radius:10px;padding:1px 8px;font-size:0.72em;font-weight:700">FASE 0</span>
          <code style="font-size:0.88em;font-weight:700">${inv.clase}</code>
          <span style="font-size:0.82em;color:#374151">${inv.descripcion}</span>
        </div>
        <p style="font-size:0.78em;color:#64748b;margin:0 0 8px">${inv.nota||''}</p>
        <p style="font-size:0.78em;font-weight:600;color:#991b1b;margin:0 0 4px">Candidatos a probar en el Explorador (browse, solo lectura):</p>
        <div style="display:flex;flex-wrap:wrap;gap:5px">
          ${sondaCands.map(p => {
            const ps = JSON.stringify(p);
            const pe = ps.replace(/"/g,'&quot;');
            return `<button class="ae-plan-run btn primary"
              data-clase="${inv.clase}" data-op="browse" data-params="${pe}"
              style="font-size:0.75em;padding:3px 9px;background:#991b1b;border-color:#991b1b">
              ▶ ${ps}
            </button>`;
          }).join('')}
        </div>
        <div id="ae-ids-clase-${inv.clase}" style="margin-top:8px"></div>
      </div>`;
    });
    h += `</div></details>`;
  }

  // ── Pruebas pendientes (FASE 1 + 2 + 3) ─────────────────────────────
  h += `<details open><summary style="cursor:pointer;font-weight:700;font-size:0.92em;padding:8px 0;color:#1e293b">⏳ Pruebas pendientes (${pendientes.length}) — en orden de prioridad</summary><div style="padding:4px 0 8px">`;
  if (!pendientes.length) {
    h += `<p style="color:#166534;font-size:0.84em;padding:8px">✅ ¡Todas las pruebas completadas!</p>`;
  } else {
    pendientes.forEach(p => {
      const paramsStr = JSON.stringify(p.params_sugeridos||{});
      const tieneInterrogante = paramsStr.includes('"?"');
      const paramsEsc = paramsStr.replace(/"/g,'&quot;');
      // Etiqueta de fase (viene del backend, fallback calculado aquí)
      const faseLbl = p.fase || (tieneInterrogante ? 'FASE 2' : (p.operacion==='browse' ? 'FASE 1' : 'FASE 3'));
      const faseCol = faseLbl==='FASE 1' ? '#166534' : faseLbl==='FASE 2' ? '#92400e' : '#9a3412';
      const faseBg  = faseLbl==='FASE 1' ? '#dcfce7' : faseLbl==='FASE 2' ? '#fef9c3' : '#fff7ed';
      h += `<div style="background:${pBg[p.prioridad]||'#f8fafc'};border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;margin:5px 0">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px">
          <span style="font-size:1em">${p.prioridad}</span>
          <span style="background:${faseBg};color:${faseCol};border-radius:10px;padding:1px 7px;font-size:0.7em;font-weight:700">${faseLbl}</span>
          <code style="background:rgba(0,0,0,0.06);padding:1px 6px;border-radius:4px;font-size:0.84em">${p.clase}.${p.operacion}</code>
          <b style="font-size:0.86em;color:${pCl[p.prioridad]||'#374151'}">${p.descripcion}</b>
          <span style="margin-left:auto;font-size:0.73em;color:#94a3b8">${p.causa_actual||''}</span>
        </div>
        <p style="margin:2px 0;font-size:0.79em;color:#64748b">${p.por_que}</p>
        <div style="display:flex;gap:6px;align-items:center;margin-top:6px;flex-wrap:wrap">
          <code style="background:#1e293b;color:#e2e8f0;padding:2px 8px;border-radius:4px;font-size:0.77em">${paramsStr}</code>
          ${tieneInterrogante
            ? `<span style="font-size:0.75em;color:#f59e0b">⚠️ ${p.nota_params||'Sustituye ? por valor real en el Explorador'}</span>`
            : `<button class="btn primary ae-plan-run" data-clase="${p.clase}" data-op="${p.operacion}" data-params="${paramsEsc}" style="font-size:0.78em;padding:3px 10px">▶ Ejecutar ahora</button>`}
        </div>
      </div>`;
    });
  }
  h += `</div></details>`;

  // Completadas
  if (completadas.length) {
    h += `<details><summary style="cursor:pointer;font-weight:700;font-size:0.92em;padding:8px 0;color:#166534">✅ Pruebas completadas (${completadas.length})</summary><div style="padding:4px 0 8px">`;
    completadas.forEach(p => {
      const fl = p.fase || 'FASE 1';
      h += `<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:8px 12px;margin:4px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span style="background:#dcfce7;color:#166534;border-radius:10px;padding:1px 7px;font-size:0.7em;font-weight:700">${fl}</span>
        <code style="font-size:0.82em;color:#166534">${p.clase}.${p.operacion}</code>
        <span style="font-size:0.8em;color:#475569">${p.descripcion}</span>
        <span style="font-size:0.78em;color:#94a3b8;margin-left:auto">${p.tiene_sonda?'🔬 Sondeado':'📊 Discover'}</span>
      </div>`;
    });
    h += `</div></details>`;
  }

  return h;
}

// ── Render resultado de sonda exhaustiva ──────────────────────────
function _renderSondaResultado(r) {
  const CA = {'🔵':'#dbeafe','✅':'#dcfce7','🚫':'#fef2f2','🔒':'#f8fafc','⚠️':'#fef9c3','❌':'#fef2f2','ℹ️':'#f0f9ff'};
  const iconCausa = {'acceso_confirmado':'✅','requiere_parametros':'🔵','sin_licencia':'🚫','sin_permiso_usuario':'🔒','config_incompleta':'⚙️','respuesta_inesperada':'⚠️'};
  const ic = iconCausa[r.causa_final] || '❓';
  let h = `<div style="background:${CA[ic]||'#f8fafc'};border-radius:8px;padding:12px 14px;margin-bottom:12px">
    <b style="font-size:0.95em">${ic} ${r.causa_final||'?'}</b>
    <p style="margin:4px 0 0;font-size:0.82em;color:#475569">${r.explicacion_final||''}</p>
    ${r.operaciones_confirmadas.length?`<p style="margin:4px 0 0;font-size:0.8em;color:#166534">Operaciones confirmadas: <code>${r.operaciones_confirmadas.join(', ')}</code></p>`:''}
  </div>`;
  // tabla de intentos
  h+=`<table style="width:100%;border-collapse:collapse;font-size:0.8em;margin-bottom:10px">
    <thead><tr style="background:#f1f5f9">
      <th style="padding:5px 8px;text-align:left">Operación</th>
      <th style="padding:5px 8px;text-align:left">Params</th>
      <th style="padding:5px 8px;text-align:center">Code</th>
      <th style="padding:5px 8px;text-align:center">ms</th>
      <th style="padding:5px 8px;text-align:left">Interpretación</th>
    </tr></thead><tbody>`;
  (r.intentos||[]).forEach(it=>{
    const bg=it.code===0?'#f0fdf4':it.code===6?'#eff6ff':it.code>0?'#fef9c3':'';
    h+=`<tr style="border-bottom:1px solid #f1f5f9;background:${bg}">
      <td style="padding:4px 8px;font-family:monospace;font-weight:600">${it.operacion}</td>
      <td style="padding:4px 8px;font-size:0.88em;color:#64748b">${JSON.stringify(it.params||{})}</td>
      <td style="padding:4px 8px;text-align:center"><code style="background:#f1f5f9;padding:1px 5px;border-radius:3px">${it.code??'?'}</code></td>
      <td style="padding:4px 8px;text-align:center;color:#64748b">${it.ms||0}</td>
      <td style="padding:4px 8px">${it.interpretacion||''}</td>
    </tr>`;
  });
  h+=`</tbody></table>`;
  // datos reales
  if (r.datos_reales&&r.datos_reales.length) {
    h+=`<details open><summary style="cursor:pointer;font-weight:600;font-size:0.88em;padding:6px 0;color:#166534">✅ Datos reales obtenidos (${r.datos_reales.length} registros${r.total_registros?` de ${r.total_registros} totales`:''})</summary><div style="overflow-x:auto;margin-top:6px">`;
    const cols=Object.keys(r.datos_reales[0]);
    h+=`<table style="width:100%;border-collapse:collapse;font-size:0.78em"><thead><tr style="background:#f8fafc">${cols.map(c=>`<th style="padding:4px 8px;text-align:left;border-bottom:1px solid #e2e8f0">${c}</th>`).join('')}</tr></thead><tbody>`;
    r.datos_reales.forEach(row=>{ h+=`<tr style="border-bottom:1px solid #f8fafc">${cols.map(c=>`<td style="padding:3px 8px;font-size:0.92em">${row[c]??''}</td>`).join('')}</tr>`; });
    h+=`</tbody></table></div></details>`;
  }
  // campos del servidor
  if (r.campos_servidor&&r.campos_servidor.length) {
    h+=`<details><summary style="cursor:pointer;font-weight:600;font-size:0.88em;padding:6px 0;color:#1d4ed8">ℹ️ Campos reales del servidor (${r.campos_servidor.length})</summary><div style="font-size:0.8em;color:#475569;padding:6px 0">${r.campos_servidor.map(f=>`<span style="background:#eff6ff;border-radius:4px;padding:1px 6px;margin:2px 2px 2px 0;display:inline-block">${f.n||JSON.stringify(f)}</span>`).join('')}</div></details>`;
  }
  // campos documentados
  if (r.campos_doc&&r.campos_doc.length) {
    h+=`<details><summary style="cursor:pointer;font-weight:600;font-size:0.88em;padding:6px 0;color:#6d28d9">📋 Campos documentados (${r.campos_doc.length})</summary><div style="font-size:0.8em;padding:4px 0">`;
    r.campos_doc.forEach(f=>{ h+=`<div style="display:inline-block;margin:2px;padding:2px 8px;background:${f.req?'#fef3c7':'#f1f5f9'};border-radius:4px;font-size:0.92em">${f.req?'<b>*</b> ':''}${f.n} <span style="color:#94a3b8">(${f.tipo})</span></div>`; });
    h+=`</div></details>`;
  }
  return h;
}

const ApiExplorerModule = {
  async onEnter() {
    const root=document.getElementById("api-explorer-root");
    if(root) root.innerHTML=`<div style="text-align:center;padding:40px;color:#64748b">Cargando...</div>`;
    try {
      const [s,c,cat,hd,catFull,cache]=await Promise.all([
        _fetch("/status"),_fetch("/config"),_fetch("/catalogue"),_fetch("/history"),
        _fetch("/catalogue-full").catch(()=>null),
        _fetch("/discover-cache").catch(()=>null)  // carga discover previo desde disco
      ]);
      _state.status=s;_state.config=c;_state.catalogue=cat;
      _state.history=hd.history||[];_state.matrix=hd.matrix||{};
      if(catFull) _state.catalogueFull=catFull;
      // Restaurar discover previo desde disco (persiste entre reinicios de DEVIA)
      if(cache&&cache.cached&&cache.clases) {
        _state.discoverResult=cache;
        _state._cacheRestored=true;
        _state._cacheTs=cache.timestamp||'';
      }
    } catch(e) {
      if(root) root.innerHTML=`<div style="padding:24px;color:#dc2626;background:#fef2f2;border-radius:8px"><strong>Error al cargar</strong><br>${e.message}</div>`;
      return;
    }
    renderMain();
  },
  setTab(t){_state.currentTab=t;renderMain();},
  setInspectorTab(t){
    _state.inspectorTab=t; renderMain();
    if(t==='plan') setTimeout(()=>ApiExplorerModule._cargarPlan(), 100);
  },
  setInspectorClase(c){_state.inspectorClase=c;_state.inspectorTab='clase';renderMain();},
  onModuloChange(){const el=document.getElementById("ae-modulo");if(el){_state.selectedModulo=el.value;_state.selectedClase=null;_state.selectedOp=null;}renderMain();},
  onClaseChange(){const el=document.getElementById("ae-clase");if(el){_state.selectedClase=el.value;_state.selectedOp=null;}renderMain();},
  onOpChange(){const el=document.getElementById("ae-op");if(el)_state.selectedOp=el.value;renderMain();},
  toggleInfoClase(){const el=document.getElementById("ae-info-clase");if(el)el.style.display=el.style.display==="none"?"block":"none";},
  toggleInfoOp(){const el=document.getElementById("ae-info-op");if(el)el.style.display=el.style.display==="none"?"block":"none";},
  async setModo(m){try{await _fetch("/modo",{method:"POST",body:JSON.stringify({use_mock:m})});_state.status=await _fetch("/status");_state.loginMsg=null;renderMain();}catch(e){alert(e.message);}},


  async doLogin(){
    const emp=document.getElementById("ae-empresa")?.value||"",
          usr=document.getElementById("ae-usuario")?.value||"",
          pwd=document.getElementById("ae-password")?.value||"";
    const isMock = _state.status && _state.status.use_mock;

    // Validar antes de enviar en modo real
    if(!isMock && !_state.config?.api_url) {
      _state.loginMsg = {type:"error", html:`
        <div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:6px;padding:12px 14px;color:#991b1b">
          <strong>❌ URL de API no configurada</strong><br>
          <span style="font-size:0.88em">Para conectar con la API Real necesitas añadir en el archivo <code>.env</code> de la VM:<br><br>
          <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;display:block;margin:4px 0">SQLOB_API_URL=https://tu-servidor.com/api</code>
          <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;display:block;margin:4px 0">SQLOB_EMPRESA=JDDC</code>
          <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;display:block;margin:4px 0">SQLOB_USUARIO=API_JDDC</code>
          <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;display:block;margin:4px 0">SQLOB_PASSWORD=tu_password</code>
          Luego reinicia DEVIA para que lea los nuevos valores.</span>
        </div>`};
      renderMain(); return;
    }
    if(!emp||!usr||!pwd) {
      _state.loginMsg = {type:"error", html:`<div style="background:#fef9c3;border-left:4px solid #fde047;border-radius:6px;padding:10px 14px;color:#92400e">⚠️ Rellena empresa, usuario y password antes de conectar.</div>`};
      renderMain(); return;
    }

    _state.loginMsg = {type:"info", html:`<div style="color:#64748b;font-size:0.88em;padding:8px 0">🔄 Conectando${isMock?" (modo simulado)":""}...</div>`};
    renderMain();

    try{
      const r = await _fetch("/login",{method:"POST",body:JSON.stringify({empresa:emp,usuario:usr,password:pwd})});
      _state.status = await _fetch("/status");
      if(r.estado === "ok") {
        _state.loginMsg = {type:"ok", html:`<div style="background:#dcfce7;border-left:4px solid #16a34a;border-radius:6px;padding:10px 14px;color:#166534"><strong>✅ Sesion iniciada</strong><br><span style="font-size:0.85em">Empresa: ${emp} | Usuario: ${usr}${isMock?" | 🔵 Modo Simulado":""}</span></div>`};
      } else {
        _state.loginMsg = {type:"error", html:`<div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:6px;padding:10px 14px;color:#991b1b"><strong>❌ Login fallido</strong> (code=${r.code})<br><span style="font-size:0.85em">${r.mensaje||"Credenciales incorrectas o sin acceso."}</span></div>`};
      }
    }catch(e){
      const isUrlError = e.message.includes("fetch") || e.message.includes("Failed") || e.message.includes("Network");
      _state.loginMsg = {type:"error", html:`
        <div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:6px;padding:12px 14px;color:#991b1b">
          <strong>❌ Error de conexion</strong><br>
          <span style="font-size:0.88em">${e.message}</span><br>
          ${isUrlError ? `<span style="font-size:0.82em;color:#64748b;margin-top:6px;display:block">
            Posibles causas:<br>
            • La URL de la API no es alcanzable desde este PC<br>
            • El servidor de Distrito K no está accesible<br>
            • Verifica VPN, URL y credenciales en el .env
          </span>` : ""}
        </div>`};
    }
    renderMain();
  },
  async doLogout(){try{await _fetch("/logout",{method:"POST"});_state.status=await _fetch("/status");renderMain();}catch(e){alert(e.message);}},

  async doDiscover() {
    const hostInput = document.getElementById("ae-discover-host");
    const resultDiv = document.getElementById("ae-discover-result");
    const host = hostInput ? hostInput.value.trim() : "";
    if (resultDiv) resultDiv.innerHTML = `<div style="color:#64748b;font-size:0.82em;padding:6px 0">🔍 Buscando servidor mPYME en la red... (puede tardar hasta 30s)</div>`;
    try {
      const r = await fetch("/api/api-explorer/discover", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({host}),
      });
      const d = await r.json();
      if (!resultDiv) return;
      const found = d.encontradas || [];
      let html = `<div style="font-size:0.8em;margin-bottom:6px;color:#64748b">Probadas ${d.total_probadas} URLs en <strong>${d.host_probado}</strong></div>`;
      if (found.length) {
        html += `<div style="background:#dcfce7;border-left:3px solid #16a34a;border-radius:5px;padding:8px 12px;margin-bottom:8px">
          <strong style="color:#166534">✅ Servidor mPYME encontrado</strong><br>
          <code style="background:#f0fdf4;padding:2px 6px;border-radius:3px;font-size:0.95em">${found[0]}</code><br>
          <span style="font-size:0.85em;color:#64748b">Copia esta URL en tu .env como SQLOB_API_URL y reinicia DEVIA</span>
        </div>`;
      } else {
        html += `<div style="background:#fef9c3;border-left:3px solid #fde047;border-radius:5px;padding:8px 12px;margin-bottom:8px;color:#92400e">
          <strong>⚠️ No encontrado automaticamente</strong><br>
          <span style="font-size:0.85em">Posibles causas: el servicio mPYME no esta instalado/arrancado en el servidor,
          o usa un puerto distinto. Pregunta a Distrito K cual es la URL exacta.</span>
        </div>`;
      }
      html += `<details style="margin-top:4px"><summary style="cursor:pointer;font-size:0.78em;color:#64748b">Ver detalle de todas las URLs probadas</summary>
        <table style="width:100%;border-collapse:collapse;font-size:0.75em;margin-top:6px">
          <thead><tr style="background:#f8fafc">
            <th style="text-align:left;padding:3px 6px;border-bottom:1px solid #e2e8f0">URL</th>
            <th style="padding:3px 6px;border-bottom:1px solid #e2e8f0">Estado</th>
            <th style="padding:3px 6px;border-bottom:1px solid #e2e8f0">ms</th>
            <th style="text-align:left;padding:3px 6px;border-bottom:1px solid #e2e8f0">Detalle</th>
          </tr></thead><tbody>
          ${(d.resultados||[]).map(row => {
            const icon = row.estado==="mpyme_encontrado"?"✅":row.estado==="mpyme_posible"?"🟡":row.estado==="no_responde"?"⬜":"ℹ️";
            const bg = row.estado==="mpyme_encontrado"?"#f0fdf4":row.estado==="mpyme_posible"?"#fefce8":"";
            return `<tr style="border-bottom:1px solid #f1f5f9;background:${bg}">
              <td style="padding:3px 6px;font-family:monospace">${row.url}</td>
              <td style="text-align:center;padding:3px 6px">${icon}</td>
              <td style="text-align:center;padding:3px 6px;color:#94a3b8">${row.ms||"—"}</td>
              <td style="padding:3px 6px;color:#64748b">${row.detalle||"—"}</td>
            </tr>`;
          }).join("")}
          </tbody>
        </table>
      </details>`;
      resultDiv.innerHTML = html;
    } catch(e) {
      if (resultDiv) resultDiv.innerHTML = `<div style="color:#dc3545;font-size:0.82em">Error: ${e.message}</div>`;
    }
  },

  async doDiscoverAll() {
    // Carga catálogo full si no está
    if (!_state.catalogueFull) {
      try { _state.catalogueFull = await _fetch("/catalogue-full"); } catch(e) {}
    }
    // Mostrar barra de progreso
    const wrap=document.getElementById("ae-dap-wrap");
    const bar=document.getElementById("ae-dap-bar");
    const msg=document.getElementById("ae-dap-msg");
    if(wrap) wrap.style.display="block";
    if(bar)  bar.style.width="5%";
    if(msg)  msg.textContent="Iniciando descubrimiento…";

    try {
      // Lanzar discover-all al backend (hace permiso+info+browse en todas las clases)
      const r = await fetch(API+"/discover-all",{method:"POST",headers:{"Content-Type":"application/json"}});
      if(bar) bar.style.width="90%";
      if(msg) msg.textContent="Procesando respuesta…";
      if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw new Error(e.detail||`HTTP ${r.status}`);}
      const data = await r.json();
      _state.discoverResult = data;
      if(data.catalogue) _state.catalogueFull = {...(_state.catalogueFull||{}), catalogue: data.catalogue};
      if(bar) bar.style.width="100%";
      if(msg) msg.textContent=`✅ Completado — ${data.resumen?.total||0} clases consultadas`;
      await new Promise(r=>setTimeout(r,800));
      if(wrap) wrap.style.display="none";
      // Recargar también el catálogo full completo (para tener codigos/operaciones)
      try { _state.catalogueFull = await _fetch("/catalogue-full"); } catch(e) {}
      // Ir a la pestaña resumen del inspector
      _state.currentTab = "inspector";
      _state.inspectorTab = "resumen";
      renderMain();
    } catch(e) {
      if(msg) msg.textContent=`❌ Error: ${e.message}`;
      if(bar) bar.style.background="#dc2626";
      setTimeout(()=>{ if(wrap)wrap.style.display="none";renderMain(); }, 3000);
    }
  },


  async doEjecutar(needsConfirm){
    const clase=document.getElementById("ae-clase")?.value||_state.selectedClase||"",op=document.getElementById("ae-op")?.value||_state.selectedOp||"";
    if(needsConfirm&&document.getElementById("ae-confirm-word")?.value!=="CONFIRMAR"){alert("Escribe exactamente: CONFIRMAR");return;}
    const params=collectParams(clase,op),result=document.getElementById("ae-exec-result");
    if(result) result.innerHTML=`<div style="color:#64748b;font-size:0.85em">Ejecutando ${clase}.${op}...</div>`;
    try{
      const r=await _fetch("/ejecutar",{method:"POST",body:JSON.stringify({clase,operacion:op,params})});
      if(result)result.innerHTML=renderResult(r);
      const hd=await _fetch("/history");_state.history=hd.history||[];_state.matrix=hd.matrix||{};
    }catch(e){if(result)result.innerHTML=`<div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:4px;padding:10px;color:#991b1b;font-size:0.88em"><strong>Error</strong><br>${e.message}</div>`;}
  },
  async doAuditarTodo(){
    const CL=["proyectos","partidas","proordutil","proordprev","reporden","repobjetos","repinst","tipostrabajo","repordutil","articulos","recursos","proveedores","clientes","docalbcom","docfaccom","docpedcom","ordenfab"];
    const prog=document.getElementById("ae-permiso-progress"),bar=document.getElementById("ae-permiso-bar"),msg=document.getElementById("ae-permiso-msg");
    if(prog) prog.style.display="block";
    for(let i=0;i<CL.length;i++){
      if(msg) msg.textContent=`Consultando ${CL[i]} (${i+1}/${CL.length})...`;
      await _fetch("/ejecutar",{method:"POST",body:JSON.stringify({clase:CL[i],operacion:"permiso",params:{}})});
      if(bar) bar.style.width=`${((i+1)/CL.length*100).toFixed(0)}%`;
    }
    const hd=await _fetch("/history");_state.history=hd.history||[];_state.matrix=hd.matrix||{};
    if(prog) prog.style.display="none";renderMain();
  },
  async doPermisoIndividual(){
    const cls=document.getElementById("ae-perm-cls")?.value||"",result=document.getElementById("ae-permiso-single-result");if(!cls)return;
    try{const r=await _fetch("/ejecutar",{method:"POST",body:JSON.stringify({clase:cls,operacion:"permiso",params:{}})});if(result)result.innerHTML=renderResult(r);const hd=await _fetch("/history");_state.history=hd.history||[];_state.matrix=hd.matrix||{};}
    catch(e){if(result)result.innerHTML=`<div style="color:#dc3545">${e.message}</div>`;}
  },
  async doClearHistory(){await _fetch("/history",{method:"DELETE"});_state.history=[];renderMain();},
  async doEscritura(activar){
    const conf=activar?(document.getElementById("ae-wr-confirm")?.value||""):"DESACTIVAR";
    try{await _fetch("/escritura",{method:"POST",body:JSON.stringify({activar,confirmacion:conf})});_state.status=await _fetch("/status");renderMain();}
    catch(e){alert(e.message);}
  },


  async doNew(){
    const p={codProyecto:document.getElementById("wr-codProyecto")?.value||"",codPartida:document.getElementById("wr-codPartida")?.value||"",tipo:document.getElementById("wr-tipo")?.value||"M"};
    const result=document.getElementById("ae-wr-result");
    try{
      const r=await _fetch("/ejecutar",{method:"POST",body:JSON.stringify({clase:"proordutil",operacion:"new",params:p})});
      if(result)result.innerHTML=renderResult(r);
      if(r.estado==="ok"&&r.json?.objectId){
        window._ae_objectId=r.json.objectId;
        const sec=document.getElementById("ae-wr-oid-section");if(sec)sec.style.display="block";
        const disp=document.getElementById("ae-wr-oid-display");
        if(disp)disp.innerHTML=`<div style="background:#dcfce7;border-left:4px solid #28a745;border-radius:4px;padding:8px 12px;margin-bottom:10px;font-size:0.88em">objectId: <code>${r.json.objectId}</code> <span style="color:#64748b;font-size:0.82em">— No persiste hasta write. Cancel descarta sin riesgo.</span></div>`;
      }
    }catch(e){if(result)result.innerHTML=`<div style="color:#dc3545">${e.message}</div>`;}
  },
  async doWrite(){
    if(document.getElementById("wr-confirm")?.value!=="CONFIRMAR"){alert("Escribe exactamente: CONFIRMAR");return;}
    const oid=window._ae_objectId||"";if(!oid){alert("Ejecuta new primero.");return;}
    const p={objectId:oid,codArticulo:document.getElementById("wr-codArticulo")?.value||"",cantidad:parseFloat(document.getElementById("wr-cantidad")?.value||"0"),coste:parseFloat(document.getElementById("wr-coste")?.value||"0")};
    const result=document.getElementById("ae-wr-result");
    try{const r=await _fetch("/ejecutar",{method:"POST",body:JSON.stringify({clase:"proordutil",operacion:"write",params:p})});if(result)result.innerHTML=renderResult(r);if(r.estado==="ok"){window._ae_objectId=null;const s=document.getElementById("ae-wr-oid-section");if(s)s.style.display="none";}}
    catch(e){if(result)result.innerHTML=`<div style="color:#dc3545">${e.message}</div>`;}
  },
  async doCancel(){
    const oid=window._ae_objectId||"";if(!oid){alert("No hay objectId.");return;}
    const result=document.getElementById("ae-wr-result");
    try{const r=await _fetch("/ejecutar",{method:"POST",body:JSON.stringify({clase:"proordutil",operacion:"cancel",params:{objectId:oid}})});if(result)result.innerHTML=renderResult(r);window._ae_objectId=null;const s=document.getElementById("ae-wr-oid-section");if(s)s.style.display="none";}
    catch(e){if(result)result.innerHTML=`<div style="color:#dc3545">${e.message}</div>`;}
  },

  // Estado selección perfil/nivel para el informe
  _perfilActual: "gerente",
  _nivelActual: "normal",

  setPerfilInforme(perfil) {
    this._perfilActual = perfil;
    // Actualizar chips visuales
    Object.keys(_PERFILES).forEach(k => {
      const b = document.getElementById(`chip-p-${k}`);
      if (b) {
        b.style.background = k === perfil ? '#3b82f6' : '#f8fafc';
        b.style.color = k === perfil ? '#fff' : '#374151';
        b.style.borderColor = k === perfil ? '#3b82f6' : '#e2e8f0';
        b.style.fontWeight = k === perfil ? '700' : '400';
      }
    });
    const desc = document.getElementById("ae-perfil-desc");
    if (desc) desc.textContent = _PERFILES[perfil]?.desc || '';
  },

  setNivelInforme(nivel) {
    this._nivelActual = nivel;
    const colores = {principiante:'#22c55e',normal:'#3b82f6',avanzado:'#f59e0b',tecnico:'#f97316',raw:'#ef4444'};
    Object.keys(_NIVELES).forEach(k => {
      const b = document.getElementById(`chip-n-${k}`);
      if (b) {
        b.style.background = k === nivel ? (colores[k] || '#3b82f6') : '#f8fafc';
        b.style.color = k === nivel ? '#fff' : '#374151';
        b.style.borderColor = k === nivel ? (colores[k] || '#3b82f6') : '#e2e8f0';
        b.style.fontWeight = k === nivel ? '700' : '400';
      }
    });
    const desc = document.getElementById("ae-nivel-desc");
    if (desc) desc.textContent = _NIVELES[nivel]?.desc || '';
  },

  async _cargarPlan() {
    const root = document.getElementById('ae-plan-root');
    if (!root) return;
    try {
      const r = await _fetch('/plan-pruebas');
      root.innerHTML = _renderPlan(r);
    } catch(e) {
      root.innerHTML = `<div style="color:#dc3545;padding:12px">Error cargando plan: ${e.message}</div>`;
    }
  },

  async doEjecutarPrueba(clase, op, paramsJson) {
    // Lanza una sonda de solo lectura directamente desde el plan de pruebas
    let params = {};
    try { params = JSON.parse(paramsJson||'{}'); } catch(e) {}
    if (op === 'browse') {
      await this.doSondaClase(clase, params);
    } else {
      // Para read/new: abrir el Explorador con esa clase y operación pre-seleccionadas
      _state.selectedClase = clase;
      _state.selectedOp = op;
      _state.currentTab = 'explorador';
      renderMain();
    }
  },

  async doExportarTodo() {
    const btn = event?.target;
    if (btn) { btn.textContent = '⏳ Generando…'; btn.disabled = true; }
    try {
      const r = await _fetch('/exportar-todo');
      const txt = JSON.stringify(r, null, 2);
      const blob = new Blob([txt], { type: 'application/json;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      const fecha = new Date().toISOString().slice(0, 10);
      a.download = `devia_api_explorer_export_${fecha}.json`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
      // Mostrar resumen de lo exportado
      const nLlamadas = r.historial?.total || 0;
      const nSondas   = r.sondas?.total || 0;
      const nClases   = Object.keys(r.discover?.clases || {}).length;
      const ts        = r.discover?.timestamp?.slice(0,19) || 'sin discover';
      alert(`✅ Exportado correctamente.\n\nContenido:\n• Discover: ${nClases} clases (${ts})\n• Historial: ${nLlamadas} llamadas\n• Sondas: ${nSondas} sondas\n• Matriz de capacidades\n\nArchivo: ${a.download}`);
    } catch(e) {
      alert(`Error al exportar: ${e.message}`);
    } finally {
      if (btn) { btn.textContent = '📤 Exportar todo (JSON completo)'; btn.disabled = false; }
    }
  },

  async doSondaClase(clase, paramsExtra) {
    // Muestra modal/panel de sonda. Solo lectura — nunca escribe.
    const existente = document.getElementById('ae-sonda-panel');
    if (existente) existente.remove();
    const panel = document.createElement('div');
    panel.id = 'ae-sonda-panel';
    panel.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px';
    panel.innerHTML = `<div style="background:white;border-radius:12px;padding:20px;max-width:700px;width:100%;max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <div>
          <h3 style="margin:0;font-size:1.05em">🔬 Sonda exhaustiva — <code>${clase}</code></h3>
          <p style="margin:2px 0 0;font-size:0.78em;color:#64748b">Solo lectura • permiso + info + browse(variantes) • sin escrituras</p>
        </div>
        <button onclick="document.getElementById('ae-sonda-panel').remove()" style="border:none;background:#f1f5f9;border-radius:8px;padding:6px 10px;cursor:pointer;font-size:0.9em">✕</button>
      </div>
      <div style="background:#fef9c3;border-left:3px solid #fbbf24;border-radius:4px;padding:7px 12px;font-size:0.8em;color:#92400e;margin-bottom:12px">
        🔒 Esta operación es <strong>100% solo lectura</strong>. Prueba múltiples estrategias de parámetros para descubrir si la clase devuelve datos reales.
      </div>
      <div style="margin-bottom:12px">
        <label style="font-size:0.83em;color:#374151;display:block;margin-bottom:4px">Parámetros extra (JSON, opcional — ej: <code>{"codProyecto":"25/184"}</code>)</label>
        <input id="ae-sonda-params" type="text" class="form-control" placeholder='{"codProyecto":"25/184"}' style="width:100%;font-family:monospace;font-size:0.84em">
      </div>
      <button onclick="ApiExplorerModule._ejecutarSonda('${clase}')" class="btn primary" style="width:100%;margin-bottom:14px">🔬 Ejecutar sonda ahora</button>
      <div id="ae-sonda-result"><p style="color:#64748b;text-align:center;font-size:0.85em">Pulsa el botón para iniciar la sonda.</p></div>
    </div>`;
    document.body.appendChild(panel);
  },

  async _ejecutarSonda(clase) {
    const res_div = document.getElementById('ae-sonda-result');
    if (!res_div) return;
    res_div.innerHTML = `<p style="color:#64748b;text-align:center;padding:12px">⏳ Sondeando <code>${clase}</code>…</p>`;
    let params_extra = {};
    const inp = document.getElementById('ae-sonda-params');
    if (inp && inp.value.trim()) {
      try { params_extra = JSON.parse(inp.value.trim()); }
      catch(e) { res_div.innerHTML=`<div style="color:#dc3545">Error en JSON de parámetros: ${e.message}</div>`; return; }
    }
    try {
      const r = await _fetch('/sonda-clase', { method:'POST', body: JSON.stringify({clase, params_extra}) });
      if (!r.success) { res_div.innerHTML=`<div style="color:#dc3545">Error: ${r.error}</div>`; return; }
      res_div.innerHTML = _renderSondaResultado(r);
    } catch(e) {
      res_div.innerHTML = `<div style="color:#dc3545">Error: ${e.message}</div>`;
    }
  },

  async doSondaTodasRequeridas() {
    // Sonda automática de todas las clases 'requiere_parametros'
    const dr = _state.discoverResult;
    if (!dr) { alert('Ejecuta Descubrir todo primero.'); return; }
    const clases = Object.entries(dr.clases||{})
      .filter(([,d]) => d.causa_real === 'requiere_parametros')
      .map(([c]) => c);
    if (!clases.length) { alert('No hay clases requiere_parametros para sondear.'); return; }
    const panel = document.getElementById('ae-sonda-auto-result');
    if (panel) panel.innerHTML = `<p style="color:#64748b;font-size:0.84em">⏳ Sondeando ${clases.length} clases…</p>`;
    for (const clase of clases) {
      try {
        await _fetch('/sonda-clase', {method:'POST', body: JSON.stringify({clase, params_extra:{}})});
      } catch(e) { /* continuar */ }
      await new Promise(r => setTimeout(r, 200));
    }
    if (panel) panel.innerHTML = `<p style="color:#166534">✅ Sonda completada para: ${clases.join(', ')}</p>`;
  },

  async doInformePerfil() {
    const div = document.getElementById("ae-informe-result");
    if (!div) return;
    const perfil = this._perfilActual || 'gerente';
    const nivel  = this._nivelActual  || 'normal';
    const plab = _PERFILES[perfil]?.emoji + ' ' + _PERFILES[perfil]?.label;
    const nlab = _NIVELES[nivel]?.emoji  + ' ' + _NIVELES[nivel]?.label;
    div.innerHTML = `<p style="color:#64748b;font-size:0.85em;padding:12px">⏳ Generando informe ${plab} / ${nlab}…</p>`;
    try {
      const r = await _fetch("/informe-perfil", {
        method: "POST",
        body: JSON.stringify({ perfil, nivel })
      });
      if (r.error) {
        div.innerHTML = `<div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:6px;padding:12px 16px;color:#991b1b">
          ⚠️ ${r.error}<br><small style="color:#64748b">Ejecuta primero 🚀 Descubrir todo.</small></div>`;
        return;
      }
      window._ae_informe_txt = r.texto || "";
      // Badge del perfil/nivel en cabecera
      const badge = `<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px;padding:10px 14px;background:linear-gradient(135deg,#f0fdf4,#f0f9ff);border-radius:8px;border:1px solid #e2e8f0">
        <span style="font-size:1.1em">${r.perfil_emoji||''}</span>
        <span style="font-weight:700;color:#1e293b">${r.perfil_label||''}</span>
        <span style="color:#94a3b8">·</span>
        <span>${r.nivel_emoji||''}</span>
        <span style="font-weight:700;color:#1e293b">${r.nivel_label||''}</span>
        ${r.totales?.total_filtrado < r.totales?.total_global
          ? `<span style="font-size:0.78em;color:#64748b;margin-left:8px">Mostrando ${r.totales.total_filtrado} de ${r.totales.total_global} clases (foco de perfil)</span>`
          : ''}
        <span style="font-size:0.78em;color:#94a3b8;margin-left:auto">${r.timestamp||''} · ${r.empresa||''}</span>
      </div>`;
      // Si nivel=raw mostrar JSON en pre
      if (r.es_raw) {
        div.innerHTML = badge + `<pre style="background:#1e293b;color:#e2e8f0;border-radius:8px;padding:14px;font-size:0.76em;overflow-x:auto;white-space:pre-wrap;max-height:600px;overflow-y:auto">${JSON.stringify(r.raw_discover,null,2).replace(/</g,'&lt;').substring(0,80000)}</pre>
          <div style="margin-top:8px"><button onclick="ApiExplorerModule.exportarInforme()" class="btn secondary" style="font-size:0.83em">💾 Exportar TXT</button></div>`;
        return;
      }
      div.innerHTML = badge + _renderInforme(r);
    } catch(e) {
      div.innerHTML = `<div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:6px;padding:12px;color:#991b1b">Error: ${e.message}</div>`;
    }
  },

  async doInforme(){
    const div=document.getElementById("ae-informe-result");
    if(!div)return;
    div.innerHTML=`<p style="color:#64748b;font-size:0.85em;padding:12px">⏳ Generando informe…</p>`;
    try{
      const r=await _fetch("/informe");
      if(r.error){
        div.innerHTML=`<div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:6px;padding:12px 16px;color:#991b1b">
          ⚠️ ${r.error}<br><small style="color:#64748b">Ejecuta primero 🚀 Descubrir todo en la pestaña Inspector.</small></div>`;
        return;
      }
      window._ae_informe_txt = r.texto || "";
      div.innerHTML = _renderInforme(r);
    }catch(e){
      div.innerHTML=`<div style="background:#fef2f2;border-left:4px solid #dc3545;border-radius:6px;padding:12px;color:#991b1b">Error: ${e.message}</div>`;
    }
  },

  exportarInforme(){
    const txt=window._ae_informe_txt||"";
    if(!txt){alert("Genera el informe primero.");return;}
    const blob=new Blob([txt],{type:"text/plain;charset=utf-8"});
    const a=document.createElement("a");
    a.href=URL.createObjectURL(blob);
    a.download=`informe_api_${new Date().toISOString().slice(0,10)}.txt`;
    document.body.appendChild(a);a.click();document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  },

  // ── Sonda masiva automática FASE 0 ────────────────────────────────────────
  async doSondaMasivaFase0() {
    const div = document.getElementById('ae-plan-result-fase0');
    const btn = document.getElementById('btn-sonda-masiva');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Sondeando >50 variantes…'; }
    if (div) div.innerHTML = `<div style="padding:12px;color:#64748b;font-size:0.85em">
      ⏳ Probando <b>>50 variantes de parámetros</b> en las 6 clases…
      <br>Esto puede tardar 30-60 segundos. Por favor espera.</div>`;
    try {
      const r = await _fetch('/sonda-masiva-fase0', {method:'POST'});
      if (!div) return;
      const des = r.desbloqueados || [];
      const sig = r.siguen_bloqueados || [];
      const res = r.resultados || {};

      let h = `<div style="background:${des.length?'#f0fdf4':'#fef9c3'};border:1px solid ${des.length?'#86efac':'#fde047'};border-radius:8px;padding:10px 14px;margin-bottom:8px">
        <b>${des.length ? '✅ Resultado: '+des.length+' clase(s) desbloqueada(s)!' : '⚠️ Ninguna clase desbloqueada con variantes automáticas'}</b>
        <br><span style="font-size:0.82em;color:#475569">${des.length ? 'Parámetro correcto encontrado.' : 'El servidor exige un identificador de negocio real (codProyecto, codOrden).'}</span>
      </div>`;

      if (des.length) {
        h += `<div style="margin-bottom:10px">`;
        des.forEach(c => {
          const e = res[c]?.exito || {};
          h += `<div style="background:#dcfce7;border:1px solid #86efac;border-radius:6px;padding:8px 12px;margin:4px 0">
            <code style="font-weight:700">${c}</code> — params: <code>${JSON.stringify(e.params)}</code>
            — ${e.n_items} registros
            ${e.campos?.length ? `<br><span style="font-size:0.78em;color:#166534">Campos: ${e.campos.slice(0,10).join(', ')}</span>` : ''}
          </div>`;
        });
        h += `</div>`;
      }

      if (sig.length) {
        h += `<details style="margin-top:6px"><summary style="cursor:pointer;font-size:0.84em;font-weight:600;color:#92400e">
          📋 Detalle: ${sig.length} clase(s) sin desbloquear (${Object.values(res)[0]?.total_intentos||0}+ variantes probadas)
        </summary><div style="padding:6px 0">`;
        sig.forEach(c => {
          const r2 = res[c] || {};
          const msgs = r2.mensajes_servidor || [];
          h += `<div style="font-size:0.79em;padding:4px 0;border-bottom:1px solid #f1f5f9">
            <code>${c}</code> — ${r2.total_intentos} variantes, code=6 en todas
            ${msgs[0] ? `<br><span style="color:#94a3b8">Servidor: "${msgs[0].slice(0,100)}"</span>` : ''}
          </div>`;
        });
        h += `</div></details>`;
      }

      // Botón descargar TXT de la sonda
      if (r.txt) {
        window._ae_sonda_masiva_txt = r.txt;
        h += `<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
          <button onclick="ApiExplorerModule.descargarTxtSondaMasiva()" class="btn secondary" style="font-size:0.83em">
            💾 Descargar TXT sonda masiva
          </button>
          <button onclick="ApiExplorerModule.descargarInformeCompleto()" class="btn primary" style="font-size:0.83em">
            📄 Descargar informe completo
          </button>
        </div>`;
      }

      div.innerHTML = h;
    } catch(e) {
      if (div) div.innerHTML = `<span style="color:#dc3545">❌ Error: ${e.message}</span>`;
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '🚀 Sonda masiva automática (>50 variantes)'; }
    }
  },

  descargarTxtSondaMasiva() {
    const txt = window._ae_sonda_masiva_txt || '';
    if (!txt) { alert('Ejecuta la sonda masiva primero.'); return; }
    const blob = new Blob([txt], {type: 'text/plain;charset=utf-8'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `sonda_masiva_fase0_${new Date().toISOString().slice(0,10)}.txt`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  },

  async descargarInformeCompleto() {
    try {
      const r = await _fetch('/informe-completo');
      if (!r.txt) { alert('Error al generar el informe.'); return; }
      const blob = new Blob([r.txt], {type: 'text/plain;charset=utf-8'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = r.filename || `informe_completo_jddc_${new Date().toISOString().slice(0,10)}.txt`;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch(e) {
      alert('Error descargando informe: ' + e.message);
    }
  },

  async doDiagnosticoFirebird() {
    const ex = document.getElementById('ae-diag-fb-panel');
    if (ex) ex.remove();
    const panel = document.createElement('div');
    panel.id = 'ae-diag-fb-panel';
    panel.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.55);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px';
    panel.innerHTML = `<div style="background:white;border-radius:12px;padding:20px;max-width:640px;width:100%;max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="margin:0;font-size:1.05em">🔌 Diagnóstico Firebird — Base de datos SQL Obras</h3>
        <button onclick="document.getElementById('ae-diag-fb-panel').remove()" style="border:none;background:#f1f5f9;border-radius:8px;padding:6px 10px;cursor:pointer">✕</button>
      </div>
      <p style="color:#64748b;font-size:0.82em;margin:0 0 12px">Comprueba si el servidor DEVIA puede conectarse a Firebird para obtener IDs reales y probar la API automáticamente.</p>
      <div id="ae-diag-fb-content"><p style="color:#64748b;text-align:center;padding:20px">⏳ Comprobando…</p></div>
    </div>`;
    document.body.appendChild(panel);
    try {
      const r = await _fetch('/diagnostico-firebird');
      window._ae_diag_fb_cache = r; // guardar para el TXT export
      const div = document.getElementById('ae-diag-fb-content');
      if (!div) return;
      const ok=r.conexion_ok, inst=r.firebirdsql_instalado, cfgOk=r.db_name_configurado;
      let html = `<div style="background:${ok?'#dcfce7':'#fef2f2'};border:1px solid ${ok?'#86efac':'#fca5a5'};border-radius:8px;padding:10px 14px;margin-bottom:12px">
        <b style="color:${ok?'#166534':'#991b1b'}">${ok?'✅ Conexión OK — IDs reales disponibles para probar la API':'❌ No se pudo conectar a Firebird'}</b>
        ${r.error?`<p style="margin:4px 0 0;font-size:0.82em;color:#991b1b;font-family:monospace">${r.error}</p>`:''}
      </div>`;
      html += `<table style="width:100%;font-size:0.81em;border-collapse:collapse;margin-bottom:12px">
        <tr style="background:#f8fafc"><th style="padding:4px 9px;text-align:left">Variable .env</th><th style="padding:4px 9px;text-align:left">Valor</th><th style="padding:4px 9px;text-align:center">OK</th></tr>
        <tr style="border-bottom:1px solid #f1f5f9"><td style="padding:4px 9px;color:#64748b">DB_HOST</td><td style="padding:4px 9px;font-family:monospace">${r.db_host||'—'}</td><td style="text-align:center">${r.db_host?'✅':'❌'}</td></tr>
        <tr style="border-bottom:1px solid #f1f5f9"><td style="padding:4px 9px;color:#64748b">DB_PORT</td><td style="padding:4px 9px;font-family:monospace">${r.db_port||3050}</td><td style="text-align:center">✅</td></tr>
        <tr style="border-bottom:1px solid #f1f5f9"><td style="padding:4px 9px;color:#64748b">DB_NAME</td><td style="padding:4px 9px;font-family:monospace;font-size:0.85em;word-break:break-all">${r.db_name||'(vacío)'}</td><td style="text-align:center">${cfgOk?'✅':'❌'}</td></tr>
        <tr style="border-bottom:1px solid #f1f5f9"><td style="padding:4px 9px;color:#64748b">DB_USER</td><td style="padding:4px 9px;font-family:monospace">${r.db_user||'—'}</td><td style="text-align:center">${r.db_user?'✅':'❌'}</td></tr>
        <tr style="border-bottom:1px solid #f1f5f9"><td style="padding:4px 9px;color:#64748b">firebirdsql</td><td style="padding:4px 9px">${inst?'Instalado':'No instalado'}</td><td style="text-align:center">${inst?'✅':'❌'}</td></tr>
        <tr><td style="padding:4px 9px;color:#64748b">Conexión</td><td style="padding:4px 9px">${ok?'Correcta':'Fallida'}</td><td style="text-align:center">${ok?'✅':'❌'}</td></tr>
      </table>`;
      if (ok && r.tablas_probadas) {
        html += `<p style="font-size:0.84em;font-weight:700;color:#374151;margin:0 0 5px">Tablas SQL Obras:</p>
          <div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px">`;
        Object.entries(r.tablas_probadas).forEach(([tbl,info]) => {
          html += `<div style="background:${info.ok?'#f0fdf4':'#fef2f2'};border:1px solid ${info.ok?'#bbf7d0':'#fca5a5'};border-radius:5px;padding:4px 10px;font-size:0.8em">
            <code>${tbl}</code> — ${info.ok?(info.n_registros+' registros'):'❌ '+info.error}
          </div>`;
        });
        html += `</div>`;
      }
      if (!inst) html += `<div style="background:#fef9c3;border-left:4px solid #fbbf24;border-radius:4px;padding:9px 14px;font-size:0.82em;color:#92400e">
        <b>Solución:</b> Ejecutar en el servidor DEVIA (donde corre uvicorn):<br>
        <code style="background:white;padding:2px 6px;border-radius:3px;display:inline-block;margin-top:4px">pip install firebirdsql</code>
        y reiniciar DEVIA.</div>`;
      else if (!cfgOk) html += `<div style="background:#fef9c3;border-left:4px solid #fbbf24;border-radius:4px;padding:9px 14px;font-size:0.82em;color:#92400e">
        <b>Solución:</b> DB_NAME vacío. Añadir en .env:<br>
        <code style="background:white;padding:2px 6px;border-radius:3px;display:inline-block;margin-top:4px">DB_NAME=C:\\Distrito\\OBRAS\\Database\\JUANDEDI\\2021.fdb</code>
        y reiniciar DEVIA.</div>`;
      else if (!ok) html += `<div style="background:#fef2f2;border-left:4px solid #ef4444;border-radius:4px;padding:9px 14px;font-size:0.82em;color:#991b1b">
        <b>Posibles causas del fallo:</b><br>
        • DB_HOST incorrecto — el servidor Firebird no está en <code>${r.db_host}</code><br>
        • DB_PASSWORD incorrecto — revisar en el .env<br>
        • Servicio Firebird no arrancado en el servidor SQL Obras<br>
        • Ruta del .fdb no accesible desde el servidor DEVIA<br>
        • Firewall bloqueando el puerto ${r.db_port||3050}</div>`;
      else html += `<div style="background:#dcfce7;border-left:4px solid #16a34a;border-radius:4px;padding:9px 14px;font-size:0.82em;color:#166534">
        <b>✅ Todo correcto.</b> El botón 🔍 BD en cada campo ya obtiene IDs reales.<br>
        Ahora pulsa <b>🚀 Probar todas</b> — el sistema usará IDs reales de tu BD automáticamente.</div>`;
      div.innerHTML = html;
    } catch(e) {
      const div = document.getElementById('ae-diag-fb-content');
      if (div) div.innerHTML = `<div style="color:#991b1b;padding:12px">Error al contactar el servidor: ${e.message}</div>`;
    }
  },
  async doObtenerIdsReales() {
    // Consulta SOLO LECTURA a Firebird: SELECT FIRST 5 de tablas clave
    // para obtener IDs reales con los que probar las clases FASE 0 (code=6)
    const btn = document.getElementById('btn-ids-reales');
    const resultDiv = document.getElementById('ae-ids-reales-result');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Consultando BD…'; }
    if (resultDiv) resultDiv.innerHTML = `<div style="padding:8px;color:#64748b;font-size:0.82em">
      🔍 Consultando Firebird (SELECT FIRST 5, solo lectura)…</div>`;
    try {
      const r = await _fetch('/obtener-ids-reales', {method: 'POST'});

      // Mostrar aviso global
      if (resultDiv) {
        if (!r.ok && r.error) {
          resultDiv.innerHTML = `<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;
            padding:8px 12px;font-size:0.82em;color:#991b1b;margin-top:4px">
            ❌ No se pudo conectar a Firebird: <b>${r.error}</b><br>
            <span style="font-size:0.9em">Verifica DB_HOST, DB_PORT y DB_NAME en el .env del servidor.</span>
          </div>`;
        } else {
          resultDiv.innerHTML = `<div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:6px;
            padding:6px 12px;font-size:0.8em;color:#1e40af;margin-top:4px">
            ✅ ${r.aviso || 'Solo lectura — datos obtenidos de Firebird.'}
          </div>`;
        }
      }

      // Inyectar IDs en cada tarjeta FASE 0
      if (r.resultados && Array.isArray(r.resultados)) {
        r.resultados.forEach(res => {
          const claseDiv = document.getElementById(`ae-ids-clase-${res.clase}`);
          if (!claseDiv) return;
          if (res.error) {
            claseDiv.innerHTML = `<div style="font-size:0.78em;color:#6b7280;padding:4px 0">
              ⚠️ Error BD para <b>${res.tabla}</b>: ${res.error}</div>`;
            return;
          }
          if (!res.ids || res.ids.length === 0) {
            claseDiv.innerHTML = `<div style="font-size:0.78em;color:#6b7280;padding:4px 0">
              Sin registros en <b>${res.tabla}</b> (tabla vacía).</div>`;
            return;
          }
          // Generar botones con IDs reales
          const btns = res.ids.map(item => {
            const paramObj = {[item.param_api]: item.id};
            const paramStr = JSON.stringify(paramObj);
            const paramEsc = paramStr.replace(/"/g, '&quot;');
            const label = item.desc ? `${item.id} — ${item.desc.substring(0,40)}` : item.id;
            return `<button class="ae-plan-run btn primary"
              data-clase="${res.clase}" data-op="browse" data-params="${paramEsc}"
              title="browse ${res.clase} con ${item.param_api}=${item.id}"
              style="font-size:0.75em;padding:3px 9px;background:#1d4ed8;border-color:#1d4ed8;
                     white-space:nowrap;max-width:260px;overflow:hidden;text-overflow:ellipsis">
              ▶ ${label}
            </button>`;
          }).join('');
          claseDiv.innerHTML = `
            <div style="margin-top:6px">
              <p style="font-size:0.78em;font-weight:600;color:#1d4ed8;margin:0 0 4px">
                🔵 IDs reales de la BD (${res.tabla}) — pulsa para probar:
              </p>
              <div style="display:flex;flex-wrap:wrap;gap:5px">${btns}</div>
            </div>`;
        });
      }
    } catch(e) {
      if (resultDiv) resultDiv.innerHTML = `<div style="background:#fef2f2;border:1px solid #fca5a5;
        border-radius:6px;padding:8px 12px;font-size:0.82em;color:#991b1b;margin-top:4px">
        ❌ Error: ${e.message}</div>`;
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '🔍 Obtener IDs reales de la BD'; }
    }
  },


  // ── Probador Visual ─────────────────────────────────────────────────────────

  async doAutocompletar(clase, op, campo) {
    // Busca valores reales en Firebird y muestra chips clicables bajo el campo
    const bdDiv = document.getElementById(`ap-bd-${clase}-${op}-${campo}`);
    const inputEl = document.getElementById(`ap-${clase}-${op}-${campo}`);
    if (!bdDiv) return;
    bdDiv.style.display = "flex";
    bdDiv.innerHTML = `<span style="font-size:0.76em;color:#3b82f6;padding:2px 0">⏳ Consultando base de datos…</span>`;
    try {
      const r = await _fetch("/valores-param", {method:"POST", body:JSON.stringify({clase, campo})});
      if (!r.ok || !r.valores?.length) {
        bdDiv.innerHTML = `<div style="font-size:0.76em;color:#991b1b;padding:2px 0">
          ❌ ${r.error||"Sin valores en BD"}
          ${r.error?.includes("DB_NAME")||r.error?.includes("no instalado")
            ? `<br><span style="color:#64748b">Pulsa <b>🔌 Diagnóstico BD</b> en el header del Probador para ver el problema.</span>` : ""}
        </div>`;
        return;
      }
      bdDiv.innerHTML = `<div style="width:100%;font-size:0.73em;color:#1e40af;font-weight:600;margin-bottom:3px">
        ✅ ${r.valores.length} valores reales de la BD — pulsa para rellenar el campo:
      </div>` + r.valores.map(v => {
        const lbl = v.desc && v.desc !== v.id && v.desc !== "None" ? `${v.id} — ${v.desc.slice(0,35)}` : v.id;
        const val = v.id.replace(/\\/g,"\\\\").replace(/'/g,"\\'");
        return `<button type="button"
          onclick="(function(){
            var el=document.getElementById('ap-${clase}-${op}-${campo}');
            if(el){el.value='${val}';el.style.borderColor='#86efac';el.dispatchEvent(new Event('input'));}
          })()"
          style="font-size:0.76em;padding:3px 9px;background:#dbeafe;border:1px solid #93c5fd;border-radius:5px;cursor:pointer;color:#1e40af;white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis"
          title="${v.id}${v.desc?' — '+v.desc:''}">${lbl}</button>`;
      }).join("");
    } catch(e) {
      bdDiv.innerHTML = `<span style="font-size:0.76em;color:#991b1b">Error: ${e.message}</span>`;
    }
  },

  async doAutocompletarTodos(clase, op) {
    // Autocompletea todos los campos BD de la operación de una vez
    const params = (typeof PARAMS_DB !== "undefined" ? PARAMS_DB : {})[`${clase}.${op}`] || [];
    const camposBD = params.filter(f => _PARAMS_CON_BD.has(f.n));
    if (!camposBD.length) return;
    for (const f of camposBD) {
      await this.doAutocompletar(clase, op, f.n);
      await new Promise(r => setTimeout(r, 80)); // pequeña pausa entre consultas
    }
  },

  toggleParamHelp(clase, op, campo) {
    const div = document.getElementById(`ap-help-${clase}-${op}-${campo}`);
    if (!div) return;
    const visible = div.style.display !== "none";
    div.style.display = visible ? "none" : "block";
    // Si se muestra y está vacío, rellenarlo con la info de _PARAM_INFO
    if (!visible && div.innerHTML.trim() === "") {
      const pi = _PARAM_INFO[campo];
      if (pi) {
        div.innerHTML = `<div style="background:#fefce8;padding:6px 10px;font-size:0.77em;border-radius:5px">
          <div style="color:#92400e;margin-bottom:3px"><b>🔧 Técnico:</b> ${pi.tec}</div>
          <div style="color:#166534;margin-bottom:3px"><b>👷 Empleado SQL Obras:</b> ${pi.emp}</div>
          <div style="color:#1e40af"><b>📝 Ejemplo:</b> <code style="background:#dbeafe;padding:1px 5px;border-radius:3px">${pi.ej}</code>
            <button type="button"
              onclick="(function(){var el=document.getElementById('ap-${clase}-${op}-${campo}');if(el){el.value='${(pi.ej||'').replace(/'/g,"\\'")}';el.style.borderColor='#86efac';}})()"
              style="margin-left:6px;border:1px solid #93c5fd;background:#dbeafe;color:#1e40af;border-radius:4px;padding:1px 7px;font-size:0.9em;cursor:pointer">
              ← Usar este ejemplo</button>
          </div>
        </div>`;
      }
    }
  },

  setProbadorPerfil(perfil) {
    _state.probadorPerfil = perfil;
    renderMain();
  },

  doExportarProbadorTxt() {
    const s = _state.status || {};
    const cat = _state.catalogue;
    const catalogue = cat ? cat.catalogue : {};
    const perfil = _state.probadorPerfil || "tecnico";
    const isMock = s.use_mock;
    const empresa = s.empresa || "JDDC";
    const usuario = s.usuario || "---";
    const apiUrl = s.api_url || "(no configurada)";
    const ts = new Date().toLocaleString("es-ES");
    const SEP = "=".repeat(72); const sep = "-".repeat(72);
    const hay = Object.keys(_probRes).length > 0;
    if (!hay) { alert("Sin resultados. Pulsa Probar todas primero."); return; }
    const porEst = {};
    Object.values(_probRes).forEach(r => { porEst[r.estado]=(porEst[r.estado]||0)+1; });
    const nOk=porEst.ok||0, nReq=porEst.requiere_params||0;
    const nLic=porEst.sin_licencia||0, nPer=porEst.sin_permiso||0;
    const nErr=porEst.error||0, nCfg=porEst.config_incompleta||0, nBlq=porEst.bloqueado||0;
    const total=Object.keys(_probRes).length;
    const conRegistros   = Object.values(_probRes).filter(r=>r.n_items>0);
    const conAutoResolve = Object.values(_probRes).filter(r=>r.id_resuelto);
    const conError       = Object.entries(_probRes).filter(([,r])=>r.estado==="error"||r.code===-1);
    const clasesProbadasSet = new Set(Object.keys(_probRes).map(k=>k.split(".")[0]));
    const clasesTotalesSet  = new Set(Object.values(catalogue).flatMap(m=>Object.keys(m)));
    const clasesSinProbar   = [...clasesTotalesSet].filter(c=>!clasesProbadasSet.has(c));
    const RIESGO_OP = {browse:0,read:0,permiso:0,info:0,new:1,edit:1,cancel:0,write:2,imputaPro:2,exec:2,delete:3};
    const opsEscritura = [];
    Object.entries(catalogue).forEach(([mod,cm])=>Object.entries(cm).forEach(([cls,ops])=>{
      (ops||[]).forEach(op=>{if((RIESGO_OP[op]||0)>=2) opsEscritura.push({mod,cls,op});});
    }));
    const ELBL = {ok:"OK FUNCIONA",requiere_params:"NECESITA ID REAL",sin_licencia:"SIN LICENCIA",
      sin_permiso:"SIN PERMISO",config_incompleta:"CONFIG INCOMPLETA",error:"ERROR TECNICO",bloqueado:"BLOQUEADO"};
    const OPLN = {browse:"Listar (.browse)",read:"Leer (.read)",permiso:"Permisos (.permiso)",
      info:"Campos (.info)",new:"Crear temp (.new)",edit:"Editar temp (.edit)",cancel:"Cancelar (.cancel)",
      write:"[ESCRITURA] Guardar (.write)",imputaPro:"[ESCRITURA] Imputar obra (.imputaPro)",delete:"[ELIMINAR] (.delete)"};
    const L = []; const ln = x => L.push(x==null?"":String(x));
    ln(SEP);
    ln("INFORME COMPLETO - PROBADOR VISUAL API mPYME v1.2");
    ln("Sistema: SQL Obras (Distrito K) - DEVIA API Explorer");
    ln(SEP);
    ln("Empresa:       "+empresa);
    ln("Usuario API:   "+usuario);
    ln("URL API:       "+apiUrl);
    ln("Modo:          "+(isMock?"BD Simulada (datos de ejemplo, NO la API real)":"API Real - SQL Obras produccion"));
    ln("Generado:      "+ts);
    ln("Perfil:        "+({gerente:"Gerente",ingeniero:"Ingeniero",empleado:"Empleado SQL Obras",tecnico:"Tecnico API"}[perfil]||perfil));
    ln("Operaciones probadas: "+total+"  |  Clases probadas: "+clasesProbadasSet.size+" de "+clasesTotalesSet.size);
    ln(SEP); ln("");

    // ── 0. ESTADO DE LA CONEXIÓN A FIREBIRD (obtenida en el momento del export) ──
    ln("0. ESTADO CONEXION BASE DE DATOS FIREBIRD"); ln(sep);
    ln("  (Firebird es la BD de SQL Obras — se usa para obtener IDs reales al probar la API)");
    try {
      // Llamada sincrona-fake: usamos datos en caché si existen, o indicamos que hay que comprobarlo
      const fbCache = window._ae_diag_fb_cache;
      if (fbCache) {
        ln("  DB_HOST   : " + (fbCache.db_host||"no configurado"));
        ln("  DB_PORT   : " + (fbCache.db_port||3050));
        ln("  DB_NAME   : " + (fbCache.db_name||"(vacío — configurar en .env)"));
        ln("  DB_USER   : " + (fbCache.db_user||"no configurado"));
        ln("  firebirdsql instalado: " + (fbCache.firebirdsql_instalado?"SI":"NO"));
        ln("  Conexion OK          : " + (fbCache.conexion_ok?"SI":"NO - ver error abajo"));
        if (fbCache.error) ln("  ERROR BD  : " + fbCache.error);
        if (fbCache.conexion_ok && fbCache.tablas_probadas) {
          ln("  Tablas verificadas:");
          Object.entries(fbCache.tablas_probadas).forEach(([tbl,info]) => {
            ln("    " + tbl.padEnd(16) + " -> " + (info.ok ? info.n_registros+" registros" : "ERROR: "+info.error));
          });
        }
      } else {
        ln("  No se ha ejecutado el diagnostico Firebird en esta sesion.");
        ln("  ACCION: Pulsar '🔌 Diagnostico BD' en el Probador para comprobar la conexion.");
      }
    } catch(e) { ln("  Error obteniendo estado Firebird: " + e.message); }
    ln(""); ln("");

    ln("1. RESUMEN EJECUTIVO"); ln(sep);
    ln("  Total operaciones probadas   : "+total);
    ln("  OK - Funcionan correctamente : "+nOk);
    ln("  Necesitan ID real (code=6)   : "+nReq);
    ln("  Sin licencia  (code=1)       : "+nLic);
    ln("  Sin permiso   (code=2)       : "+nPer);
    ln("  Config incompleta (code=5)   : "+nCfg);
    ln("  Error tecnico (code=-1/otro) : "+nErr);
    ln("  Escritura bloqueada          : "+nBlq);
    ln("");
    ln("  Con registros reales obtenidos : "+conRegistros.length+" operaciones");
    ln("  Con ID auto-resuelto de BD     : "+conAutoResolve.length+" operaciones");
    ln("  Clases sin probar              : "+clasesSinProbar.length);
    ln("  Ops de escritura en catalogo   : "+opsEscritura.length+" (no probadas automaticamente)");
    ln("");
    if (nOk+nReq>0) {
      ln("  ACCESIBLE: "+(nOk+nReq)+" operaciones con licencia activa.");
      if (nOk>0) ln("    -> "+nOk+" responden correctamente sin parametros adicionales.");
      if (nReq>0) ln("    -> "+nReq+" necesitan un ID real (usar boton BD o introducir manualmente).");
    }
    if (nLic>0) ln("  SIN LICENCIA: "+nLic+" operaciones - contactar Distrito K para ampliar modulos.");
    if (nErr>0) ln("  ERRORES: "+nErr+" operaciones con error tecnico - ver seccion 5 para detalle completo.");
    if (nCfg>0) ln("  CONFIG: "+nCfg+" operaciones reportan config incompleta - revisar .env (empresa, usuario, URL).");
    ln(""); ln("");
    ln("2. TABLA DE ESTADO RAPIDO"); ln(sep);
    ln("  "+("CLASE".padEnd(16))+" "+("browse".padEnd(12))+" "+("permiso".padEnd(12))+" "+("info".padEnd(12))+" "+("read".padEnd(10))+" ESCRITURA");
    ln("  "+"-".repeat(16)+" "+"-".repeat(12)+" "+"-".repeat(12)+" "+"-".repeat(12)+" "+"-".repeat(10)+" ---------");
    clasesProbadasSet.forEach(cls => {
      const g = op => {
        const r = _probRes[cls+"."+op];
        if (!r) return "--";
        if (r.estado==="ok") return r.n_items>0?"OK("+r.n_items+"r)":"OK";
        if (r.estado==="requiere_params") return r.id_resuelto?"OK(autoID)":"NecesitaID";
        if (r.estado==="sin_licencia") return "SinLic";
        if (r.estado==="sin_permiso") return "SinPerm";
        if (r.estado==="error") return "ERR("+r.code+")";
        return (r.estado||"?").slice(0,9);
      };
      const escs = Object.keys(_probRes).filter(k=>k.startsWith(cls+".")&&(RIESGO_OP[k.split(".")[1]]||0)>=2)
        .map(k=>k.split(".")[1]).join(",");
      ln("  "+(cls.padEnd(16))+" "+(g("browse").padEnd(12))+" "+(g("permiso").padEnd(12))+" "+(g("info").padEnd(12))+" "+(g("read").padEnd(10))+" "+(escs||"ninguna"));
    });
    ln(""); ln("");
    ln("3. DETALLE COMPLETO POR MODULO / CLASE / OPERACION"); ln(sep);
    ln("  (Todos los errores, codigos, tiempos, campos y mensajes exactos del servidor)");
    ln("  (Sin valores de datos de BD - solo metadatos y estados. Privacidad garantizada.)");
    ln("");
    Object.entries(catalogue).forEach(([modNombre, claseMap]) => {
      ln("  ===[ MODULO: "+modNombre+" ]"+"=".repeat(Math.max(0,48-modNombre.length)));
      ln("");
      Object.entries(claseMap).forEach(([clase, opsArr]) => {
        const ci = CLASE_INFO[clase]||{emoji:"",desc:clase,detalle:""};
        ln("  -- "+ci.emoji+" "+clase.toUpperCase()+" - "+ci.desc+" --");
        ln("     Tecnico   : "+(ci.detalle||ci.desc));
        ln("     Empleado  : "+_claseDescEmp(clase));
        if (typeof _CF !== "undefined" && _CF[clase]) {
          ln("     Flujo     : "+(_CF[clase].flujo||"--"));
          const campos = Object.entries(_CF[clase].campos||{}).map(([k,v])=>k+": "+v).join(" | ");
          if (campos) ln("     Campos    : "+campos);
          const rel = (_CF[clase].rel||[]).join(", ");
          if (rel) ln("     Relacionadas: "+rel);
        }
        ln("");
        (opsArr||[]).forEach(op => {
          const r = _probRes[clase+"."+op];
          const risg = (RIESGO_OP[op]||0)>=2?" [ESCRITURA]":(RIESGO_OP[op]===1?" [PREP]":"");
          const etiq = r?(ELBL[r.estado]||r.estado):"SIN PROBAR";
          ln("     ["+etiq+"]"+risg+" "+OPLN[op]||op);
          if (r) {
            ln("       code         : "+r.code+"   tiempo: "+(r.ms||0)+"ms   registros obtenidos: "+(r.n_items||0));
            if (r.n_items>0) ln("       DATOS        : Se obtuvieron "+(r.n_items||0)+" registros reales de SQL Obras (valores no mostrados por privacidad)");
            if (r.campos_detectados?.length)
              ln("       CAMPOS BD    : "+r.campos_detectados.join(", "));
            if (r.muestra_tipos && Object.keys(r.muestra_tipos||{}).length)
              ln("       TIPOS        : "+Object.entries(r.muestra_tipos).map(([k,v])=>k+":"+v).join(", "));
            if (r.id_resuelto) ln("       AUTO-ID      : SI - El sistema obtuvo automaticamente un ID real de Firebird y reintento con exito.");
            if (r.necesito_id_real&&!r.id_resuelto) ln("       AUTO-ID      : FALLO - Firebird no disponible o tabla vacia. Introducir ID manualmente con boton BD.");
            if (r.params_usados && Object.keys(r.params_usados||{}).length)
              ln("       PARAMS USADOS: "+JSON.stringify(r.params_usados));
            const rawSrv = (r.raw_servidor||"").trim();
            if (rawSrv) ln("       RESP.SERVIDOR: "+rawSrv.slice(0,250)+(rawSrv.length>250?"...":""));
            const msg = (r.mensaje||"").replace(/<[^>]*>/g,"").trim();
            if (msg) ln("       MENSAJE      : "+msg.slice(0,300)+(msg.length>300?"...":""));
            // Explicacion adicional segun estado
            if (r.estado==="sin_licencia") ln("       ACCION       : Contactar Distrito K para ampliar la licencia del modulo.");
            if (r.estado==="config_incompleta") ln("       ACCION       : Verificar SQLOB_EMPRESA, SQLOB_USUARIO, SQLOB_PASSWORD en el .env del servidor.");
            if (r.estado==="requiere_params"&&!r.id_resuelto) ln("       ACCION       : Pulsar boton BD en el formulario del Probador o configurar Firebird en el .env.");
            if (r.estado==="error") ln("       ACCION       : Verificar que el servidor mPYME esta arrancado y accesible desde DEVIA.");
          } else {
            ln("       (operacion no probada - ejecutar manualmente con el formulario)");
          }
          ln("");
        });
        ln("     "+"-".repeat(65));
        ln("");
      });
    });
    ln("");
    ln("4. OPERACIONES QUE OBTUVIERON REGISTROS REALES DE SQL OBRAS"); ln(sep);
    if (conRegistros.length===0) {
      ln("  Ninguna operacion devolvio registros. Ejecuta las operaciones con IDs reales.");
    } else {
      ln("  (Numero de registros y campos detectados - los VALORES no se muestran por privacidad)");
      ln("");
      conRegistros.forEach(r => {
        const key = Object.entries(_probRes).find(([,v])=>v===r)?.[0]||"?";
        ln("  "+key+" -> "+r.n_items+" registros   "+r.ms+"ms"+(r.id_resuelto?" [ID auto-BD]":""));
        if (r.campos_detectados?.length) ln("    Campos: "+r.campos_detectados.join(", "));
      });
    }
    ln(""); ln("");
    ln("5. ERRORES Y PROBLEMAS DETECTADOS"); ln(sep);
    const todosProblemas = Object.entries(_probRes).filter(([,r])=>
      r.estado!=="ok" || r.code!==0);
    if (todosProblemas.length===0) {
      ln("  Sin errores - todas las operaciones probadas funcionan correctamente.");
    } else {
      todosProblemas.forEach(([key, r]) => {
        const etiq = ELBL[r.estado]||r.estado;
        ln("  ["+etiq+"] "+key+" (code="+r.code+", "+r.ms+"ms)");
        // Causa según estado
        if (r.estado==="sin_licencia") {
          ln("    CAUSA  : Modulo no contratado en la licencia actual.");
          ln("    ACCION : Contactar Distrito K para ampliar la licencia.");
        }
        if (r.estado==="sin_permiso") {
          ln("    CAUSA  : El usuario API no tiene permiso para esta operacion.");
          ln("    ACCION : El administrador de SQL Obras debe dar acceso al usuario "+usuario+".");
        }
        if (r.estado==="config_incompleta") {
          ln("    CAUSA  : Config incompleta. El servidor mPYME devolvio code=5.");
          ln("    ACCION : Verificar SQLOB_EMPRESA, SQLOB_USUARIO, SQLOB_PASSWORD en .env del servidor.");
          ln("    NOTA   : code=5 puede significar tambien 'modulo sin licencia' si el servidor lo indica.");
        }
        if (r.estado==="requiere_params") {
          ln("    CAUSA  : La API necesita un identificador real (codProyecto, codOrden, etc.).");
          if (r.necesito_id_real&&!r.id_resuelto) {
            ln("    AUTO-ID: El sistema intento obtener un ID de Firebird automaticamente pero fallo.");
            const fbErr = window._ae_diag_fb_cache?.error;
            if (fbErr) ln("    BD ERR : "+fbErr);
            else if (!window._ae_diag_fb_cache) ln("    BD ERR : Diagnostico Firebird no ejecutado — usar boton 'Diagnostico BD'.");
            ln("    ACCION : Pulsar boton '🔍 BD' en el campo del Probador o configurar DB_NAME en .env.");
          } else if (r.id_resuelto) {
            ln("    AUTO-ID: ID obtenido de Firebird y reintento exitoso.");
          }
        }
        if (r.estado==="error") {
          ln("    CAUSA  : Error tecnico de conexion o excepcion del servidor mPYME.");
          ln("    ACCION : Verificar que el servidor mPYME esta arrancado. URL: "+apiUrl);
        }
        const rawSrv = (r.raw_servidor||"").trim();
        if (rawSrv) ln("    SERVIDOR: "+rawSrv.slice(0,250)+(rawSrv.length>250?"...":""));
        const msg = (r.mensaje||"").replace(/<[^>]*>/g,"").trim();
        if (msg) ln("    MSG   : "+msg.slice(0,250)+(msg.length>250?"...":""));
        if (r.params_usados && Object.keys(r.params_usados||{}).length)
          ln("    PARAMS: "+JSON.stringify(r.params_usados));
      });
    }
    ln(""); ln("");
    ln("6. OPERACIONES DE ESCRITURA DEL CATALOGO (no probadas automaticamente)"); ln(sep);
    ln("  SEGURIDAD: Las operaciones de escritura NUNCA se prueban automaticamente.");
    ln("  Se deben probar manualmente con confirmacion expresa en el Probador.");
    ln("");
    if (opsEscritura.length===0) {
      ln("  No hay operaciones de escritura en el catalogo actual.");
    } else {
      opsEscritura.forEach(({mod,cls,op}) => {
        const risg = op==="delete"?"DESTRUCTIVO":op==="write"||op==="imputaPro"?"ESCRITURA REAL":"PREPARACION";
        ln("  ["+risg+"] "+cls+"."+op+"()  (modulo: "+mod+")");
      });
      ln("");
      ln("  Para probarlas: Probador > clase > formulario > activar Modo Escritura > Ejecutar + confirmar");
    }
    ln(""); ln("");
    ln("7. CLASES SIN PROBAR"); ln(sep);
    if (clasesSinProbar.length===0) {
      ln("  Todas las clases del catalogo han sido probadas.");
    } else {
      clasesSinProbar.forEach(c => ln("  - "+c));
      ln("");
      ln("  Para probarlas: Probador > Probar todas, o abre la clase y pulsa Ejecutar en cada operacion.");
    }
    ln(""); ln("");
    ln("8. APLICACIONES POSIBLES CON LA LICENCIA ACTUAL"); ln(sep);
    const clOk = new Set(Object.entries(_probRes)
      .filter(([,v])=>v.estado==="ok"||v.estado==="requiere_params")
      .map(([k])=>k.split(".")[0]));
    if (typeof _APPS !== "undefined") {
      _APPS.forEach(app => {
        const accesible = app.cls.some(c => clOk.has(c));
        const estado = accesible ? "POSIBLE" : "REQUIERE LICENCIA/PERMISO";
        ln("  ["+estado+"] "+app.emoji+" "+app.t);
        ln("    "+app.s);
        ln("    Flujo : "+app.flujo);
        ln("    Clases: "+app.cls.join(", ")+" | Ops: "+app.ops.join(", ")+" | "+app.riesgo);
        const missing = app.cls.filter(c=>!clasesProbadasSet.has(c));
        if (missing.length) ln("    FALTA : Clases sin probar: "+missing.join(", "));
        ln("");
      });
    }
    ln(""); ln("");
    ln("9. DIAGNOSTICO Y RECOMENDACIONES"); ln(sep);
    if (nOk===0 && nReq===0) {
      ln("  CRITICO: Ninguna operacion funciona. Posibles causas:");
      ln("    - URL del servidor mPYME incorrecta (revisar SQLOB_API_URL en .env)");
      ln("    - Servidor mPYME no arrancado o no accesible desde DEVIA");
      ln("    - Credenciales incorrectas (empresa, usuario, password)");
      ln("    - Sin licencia para ningun modulo");
    } else {
      if (nReq>0 && conAutoResolve.length===0) {
        ln("  ACCION RECOMENDADA: "+nReq+" ops necesitan ID real.");
        ln("    Usa el boton BD en el formulario de cada operacion para obtener IDs de Firebird,");
        ln("    o configura DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD en el .env del servidor.");
      }
      if (nLic>0) {
        ln("  LICENCIA: "+nLic+" operaciones sin licencia. Modulos posiblemente no contratados:");
        const sinLicCls = new Set(Object.entries(_probRes).filter(([,v])=>v.estado==="sin_licencia").map(([k])=>k.split(".")[0]));
        ln("    Clases afectadas: "+[...sinLicCls].join(", "));
        ln("    Accion: Contactar Distrito K para ampliar la licencia.");
      }
      if (nCfg>0) {
        ln("  CONFIG INCOMPLETA: Revisar variables en el .env del servidor DEVIA:");
        ln("    SQLOB_EMPRESA, SQLOB_USUARIO, SQLOB_PASSWORD, SQLOB_API_URL");
      }
      if (nErr>0) {
        ln("  ERRORES TECNICOS: "+nErr+" operaciones con error de conexion o excepcion.");
        ln("    Verificar que el servicio mPYME esta arrancado y accesible.");
      }
      if (clasesSinProbar.length>0) {
        ln("  SIN PROBAR: "+clasesSinProbar.length+" clases no han sido probadas.");
        ln("    Usa Probar todas en el Probador para completar el diagnostico.");
      }
      if (nOk>0) {
        ln("  FUNCIONANDO: "+nOk+" operaciones OK. Se puede implementar una app con la licencia actual.");
      }
    }
    ln(""); ln("");
    ln(SEP);
    ln("NOTAS DE SEGURIDAD Y PRIVACIDAD");
    ln(sep);
    ln("* Solo lectura automatica. Las ops de escritura NO se prueban automaticamente.");
    ln("* Sin valores de datos (codigos de proyectos, nombres, importes...).");
    ln("* Se muestran: estados, codigos, tiempos, nombres de campos y mensajes de error.");
    ln("* Los IDs auto-resueltos de BD no se incluyen en el informe.");
    ln("* Las ops de escritura requieren: activar modo escritura + confirmacion doble.");
    ln("* Generado por DEVIA API Explorer - "+ts);
    ln(SEP);
    const txt = L.join("\n");
    const blob = new Blob([txt], {type:"text/plain;charset=utf-8"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "informe_completo_api_mpyme_"+empresa+"_"+new Date().toISOString().slice(0,10)+".txt";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    delete window._ae_export_lines_temp;
    delete window._ae_export_ctx_temp;
  },


  async doAutoProbarOp(clase, op) {
    // Prueba automática sin params manuales — auto-resuelve code=6 con BD
    const key = `${clase}.${op}`;
    _probLoad[clase] = true;
    const card = document.getElementById(`ae-prob-${clase}-${op}`);
    if (card) { const b=card.querySelector("button"); if(b){b.textContent="⏳";b.disabled=true;} }
    try {
      const r = await _fetch("/auto-probar",{method:"POST",body:JSON.stringify({clase,operacion:op,params:{}})});
      if (r.items && Array.isArray(r.items) && r.items.length>0) {
        const keys=Object.keys(r.items[0]);
        r.tabla_html=`<div style="margin-top:6px;overflow-x:auto;border-radius:5px;border:1px solid #e2e8f0"><table style="width:100%;border-collapse:collapse;background:white"><thead style="background:#f8fafc"><tr>${keys.map(k=>`<th style="padding:3px 7px;text-align:left;font-size:0.73em;color:#64748b;border-bottom:1px solid #e2e8f0">${k}</th>`).join("")}</tr></thead><tbody>${r.items.slice(0,10).map(row=>`<tr>${keys.map(k=>`<td style="padding:2px 7px;font-size:0.8em;border-bottom:1px solid #f8fafc">${row[k]??""}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
        r.campos_detectados=keys;
      }
      _probRes[key]=r;
    } catch(e) {
      _probRes[key]={code:-1,estado:"error",ms:0,n_items:0,campos_detectados:[],mensaje:`Error: ${e.message}`,necesito_id_real:false,id_resuelto:false,tabla_html:""};
    } finally { _probLoad[clase]=false; }
    const cn=document.getElementById(`ae-prob-${clase}-${op}`);
    if(cn) cn.outerHTML=_mkOpCard(clase,op,(_state.status||{}).session_active||true);
  },

  async doAutoProbarClase(clase, ops) {
    // Prueba todas las ops de lectura de una clase en secuencia
    _probLoad[clase] = true;
    for (const op of ops) {
      await this.doAutoProbarOp(clase, op);
      await new Promise(r => setTimeout(r, 100));
    }
    _probLoad[clase] = false;
  },

  async doProbarTodoCatalogo(event) {
    const btn = event?.target;
    const resDiv = document.getElementById("ae-probador-todo-result");
    if (btn) { btn.textContent = "⏳ Probando (solo lectura)…"; btn.disabled = true; }
    if (resDiv) resDiv.innerHTML = `<div style="background:#eff6ff;border-left:3px solid #3b82f6;border-radius:4px;padding:8px 12px;font-size:0.82em;color:#1e40af;margin-top:6px">
      ⏳ <b>Probando browse + permiso + info</b> en todas las clases… (solo lectura, 1-2 min)<br>
      <span style="font-size:0.9em;color:#64748b">Las operaciones de escritura NO se prueban automáticamente. Usa el formulario de cada una para probarlas manualmente.</span>
    </div>`;
    // Cachear diagnóstico Firebird para incluirlo en el TXT
    _fetch("/diagnostico-firebird").then(r => { window._ae_diag_fb_cache = r; }).catch(()=>{});
    try {
      const r = await _fetch("/probar-todo-catalogo", {
        method: "POST",
        body: JSON.stringify({solo_lectura: true}),
      });
      // Importar resultados al estado local del Probador
      if (r.clases) {
        Object.entries(r.clases).forEach(([clase, entrada]) => {
          Object.entries(entrada.resultados_op||{}).forEach(([op, res]) => {
            _probRes[`${clase}.${op}`] = {
              code: res.code, estado: res.estado, ms: res.ms,
              n_items: res.n_items||0,
              campos_detectados: res.campos||[],
              necesito_id_real: res.necesito_id||false,
              id_resuelto: res.id_resuelto||false,
              muestra_tipos: {},
              mensaje: _e2msg(res.estado, res.code, res.id_resuelto),
            };
          });
        });
      }
      // Resumen visual
      const res = r.resumen||{};
      if (resDiv) resDiv.innerHTML = `
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;margin-top:8px">
          <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:7px">
            <span style="font-weight:700;font-size:0.88em;color:#1e293b">✅ Prueba completada — ${r.total_clases} clases (browse + permiso + info):</span>
            <span style="font-size:0.74em;color:#94a3b8;margin-left:auto">${(r.timestamp||"").slice(0,19)} · ${r.use_mock?"BD Simulada":"API Real"}</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">
            ${_chipRes("✅", res.ok||0,              "Funcionan",           "#dcfce7","#166534")}
            ${_chipRes("🔵", res.requiere_params||0, "Necesitan ID real",   "#dbeafe","#1e40af")}
            ${_chipRes("🚫", res.sin_licencia||0,    "Sin licencia",        "#fef2f2","#991b1b")}
            ${_chipRes("🔒", res.sin_permiso||0,     "Sin permiso usuario", "#f8fafc","#374151")}
            ${_chipRes("❌", res.error||0,           "Error",               "#fef2f2","#991b1b")}
          </div>
          <div style="font-size:0.77em;color:#64748b;background:#f1f5f9;border-radius:4px;padding:5px 8px">
            🔒 <b>No probado automáticamente:</b> write, imputaPro, delete, new — usa el formulario de cada operación para probarlas manualmente con confirmación expresa.
          </div>
        </div>`;
      _state.currentTab = "probador";
      renderMain();
    } catch(e) {
      if (resDiv) resDiv.innerHTML = `<div style="color:#991b1b;font-size:0.82em;padding:4px 0">❌ ${e.message}</div>`;
    } finally {
      if (btn) { btn.textContent = "🚀 Probar todas las clases (solo lectura)"; btn.disabled = false; }
    }
  },


  // ── Ejecutar prueba del Plan inline (delegación de eventos) ────────────────
  // Lanza sonda-rapida y muestra resultado en la tarjeta sin modal
  async _ejecutarPlanPruebaInspector(clase, op, params) {
    if (op !== 'browse') {
      // Para read/new/etc: navegar al Explorador
      _state.selectedClase = clase;
      _state.selectedOp = op;
      _state.currentTab = 'explorador';
      renderMain();
      return;
    }
    // Encontrar el botón activo y su tarjeta padre
    const activeBtn = document.querySelector(
      `.ae-plan-run[data-clase="${clase}"][data-op="${op}"]`
    );
    // Buscar o crear div de resultado dentro de la tarjeta
    const card = activeBtn
      ? activeBtn.closest('div[style*="border-radius"]') || activeBtn.parentElement
      : null;
    let rd = null;
    if (card) {
      rd = card.querySelector('.ae-plan-result');
      if (!rd) {
        rd = document.createElement('div');
        rd.className = 'ae-plan-result';
        rd.style.cssText = [
          'margin-top:8px', 'padding:8px 10px', 'border-radius:6px',
          'background:#f8fafc', 'border:1px solid #e2e8f0', 'font-size:0.8em'
        ].join(';');
        card.appendChild(rd);
      }
    }
    if (rd) rd.innerHTML = '<span style="color:#64748b">&#9203; Consultando API&hellip;</span>';
    if (activeBtn) { activeBtn.disabled = true; activeBtn.textContent = '…'; }

    try {
      const resp = await fetch(API + '/sonda-rapida', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clase, op, params })
      });
      const d = await resp.json();

      if (!rd) {
        // Sin card visible: abrir sonda completa como fallback
        await this.doSondaClase(clase, params);
        return;
      }
      if (!d.success) {
        rd.innerHTML = `<span style="color:#dc3545">&#10060; ${d.error || 'Error'}</span>`;
        return;
      }

      if (d.n_items > 0) {
        const cols = Object.keys(d.datos[0] || {});
        const rows = d.datos.slice(0, 5).map(row =>
          '<tr>' + cols.map(c =>
            `<td style="padding:2px 6px;border-bottom:1px solid #f1f5f9;white-space:nowrap">${row[c] ?? ''}</td>`
          ).join('') + '</tr>'
        ).join('');
        rd.innerHTML = `
          <div style="background:#dcfce7;border-left:3px solid #16a34a;border-radius:4px;padding:5px 10px;margin-bottom:6px">
            &#x2705; <b>Datos reales obtenidos</b> &mdash; ${d.n_items} registros &middot; ${d.duracion_ms}ms
            &middot; modo: <strong>${d.modo}</strong>
          </div>
          <div style="overflow-x:auto;max-height:200px">
            <table style="width:100%;border-collapse:collapse;font-size:0.78em;border:1px solid #e2e8f0;border-radius:4px">
              <thead><tr style="background:#f8fafc">
                ${cols.map(c => `<th style="padding:3px 8px;text-align:left;border-bottom:1px solid #e2e8f0;white-space:nowrap">${c}</th>`).join('')}
              </tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
          <div style="margin-top:6px">
            <button onclick="ApiExplorerModule.doSondaClase('${clase}')" class="btn secondary" style="font-size:0.75em;padding:2px 8px">
              &#x1f52c; Ver sonda completa
            </button>
          </div>`;
      } else {
        const codeColor = d.code === 6 ? '#3b82f6' : d.code === 0 ? '#16a34a' : '#dc3545';
        const codeIcon  = d.code === 0 ? '✅' : d.code === 6 ? '🔵' : '❌';
        rd.innerHTML = `
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span style="color:${codeColor};font-weight:700">${codeIcon} code=${d.code}</span>
            <span style="color:#64748b">${(d.raw_data || '').slice(0, 120)}</span>
            <span style="color:#94a3b8;font-size:0.85em">${d.duracion_ms}ms</span>
          </div>
          ${d.code === 6
            ? `<p style="margin:4px 0 0;color:#64748b;font-size:0.85em">
                &#x1F4C4; <em>code=6: la clase necesita parámetros adicionales (ej: codProyecto real).
                Úsala en la pestaña <b>Sondear</b> con un valor real.</em>
               </p>`
            : ''}
          <div style="margin-top:4px">
            <button onclick="ApiExplorerModule.doSondaClase('${clase}')" class="btn secondary" style="font-size:0.75em;padding:2px 8px">
              &#x1f52c; Sonda completa
            </button>
          </div>`;
      }
    } catch (e) {
      if (rd) rd.innerHTML = `<span style="color:#dc3545">&#10060; Error: ${e.message}</span>`;
    } finally {
      if (activeBtn) {
        activeBtn.disabled = false;
        activeBtn.textContent = '▶ Ejecutar ahora';
      }
    }
  },

};

window.ApiExplorerModule = ApiExplorerModule;

// ── Event delegation para botones ae-plan-run (Plan de pruebas) ──────────
// Evita problemas con comillas en onclick inline
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.ae-plan-run');
  if (!btn) return;
  e.preventDefault();
  const clase = btn.dataset.clase || '';
  const op    = btn.dataset.op   || 'browse';
  let params  = {};
  try {
    // Desescapar &quot; antes de parsear
    const raw = (btn.dataset.params || '{}').replace(/&quot;/g, '"');
    params = JSON.parse(raw);
  } catch(err) { console.warn('ae-plan-run: params inválidos', err); }
  // Ejecutar sonda directamente en el Inspector > Resumen
  ApiExplorerModule._ejecutarPlanPruebaInspector(clase, op, params);
});

