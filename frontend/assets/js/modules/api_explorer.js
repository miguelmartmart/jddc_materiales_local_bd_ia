 /**
 * api_explorer.js v12 — Sonda exhaustiva por clase, clasificacion correcta sin_licencia/requiere_params.
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

  const TABS = [["conexion","🔌 Conexion"],["inspector","🔍 Inspector API"],["explorador","⚙️ Explorador"],["permisos","📋 Permisos"],["matriz","📊 Matriz"],["historial","📜 Historial"],["escritura","🟠 Escritura"]];
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
  if (_state.currentTab === "permisos") return !s.session_active ? noSesion() : renderPermisos(CLASSES, ops_cols, permisoR);
  if (_state.currentTab === "matriz") return renderMatriz(catalogue, mat);
  if (_state.currentTab === "historial") return renderHistorial(hist, resumen);
  if (_state.currentTab === "escritura") return renderEscritura(s);
  return "";
}

const noSesion = () => `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:8px;padding:20px;text-align:center;color:#92400e">⚠️ Conectate primero en la pestana <strong>Conexion</strong>.</div>`;


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
  const ITABS = [["resumen","📋 Resumen"],["clase","🗂️ Por Clase"],["operaciones","⚙️ Operaciones"],["codigos","🔢 Códigos"],["informe","📑 Informe"]];
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
      ${dr ? `<span style="font-size:0.77em;color:#94a3b8">Último: ${(dr.timestamp||'').slice(0,19).replace('T',' ')}</span>` : ''}
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
  if (iTab === 'resumen')    content = _inspResumen(cat, dr);
  else if (iTab === 'clase') content = _inspClase(cat, cf, dr, cls);
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

  const browseErrH=(drC?.browse_error||drC?.browse_error_code!=null)?`<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:0.8em;color:#991b1b">⚠️ browse: ${drC.browse_error||''} ${drC.browse_error_msg||''} ${drC.browse_error_code!=null?`(code=${drC.browse_error_code})`:''}
  </div>`:'';

  return sel+hdr+diagH+opsH+permH+browseErrH+_inspClasetabla(drC,camposDoc,camposReal)+_inspClasemuestra(drC,muestra);
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
  let h=`<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:14px">${Object.entries(resumen).map(([k,v])=>`<div style="background:white;border-radius:8px;border:1px solid #e2e8f0;padding:8px;text-align:center"><div style="font-size:1.4em;font-weight:700">${v}</div><div style="font-size:0.74em;color:#64748b">${k}</div></div>`).join('')}</div>
  <div style="text-align:right;margin-bottom:10px"><button onclick="ApiExplorerModule.doClearHistory()" class="btn secondary" style="font-size:0.85em">🗑️ Limpiar historial</button></div>`;
  if(!hist.length) return h+`<div style="text-align:center;color:#64748b;padding:40px">Sin pruebas. Ve al Explorador y ejecuta operaciones.</div>`;
  return h+hist.slice(0,50).map(r=>`<details style="margin-bottom:8px;background:white;border-radius:8px;border:1px solid #e2e8f0">
    <summary style="cursor:pointer;padding:10px 14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <span>${estadoIcon(r.estado)}</span>
      <code style="font-size:0.88em;background:#f1f5f9;padding:2px 6px;border-radius:4px">${r.clase}.${r.operacion}</code>
      <span style="color:#64748b;font-size:0.8em;margin-left:auto">${(r.timestamp||'').slice(11,19)} | ${r.duracion_ms}ms | ${r.use_mock?'🔵 Mock':'🟠 Real'}</span>
    </summary>
    <div style="padding:12px 14px;border-top:1px solid #f1f5f9">${renderResult(r)}</div>
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
      const [s,c,cat,hd,catFull]=await Promise.all([
        _fetch("/status"),_fetch("/config"),_fetch("/catalogue"),_fetch("/history"),
        _fetch("/catalogue-full").catch(()=>null)
      ]);
      _state.status=s;_state.config=c;_state.catalogue=cat;
      _state.history=hd.history||[];_state.matrix=hd.matrix||{};
      if(catFull) _state.catalogueFull=catFull;
    } catch(e) {
      if(root) root.innerHTML=`<div style="padding:24px;color:#dc2626;background:#fef2f2;border-radius:8px"><strong>Error al cargar</strong><br>${e.message}</div>`;
      return;
    }
    renderMain();
  },
  setTab(t){_state.currentTab=t;renderMain();},
  setInspectorTab(t){_state.inspectorTab=t;renderMain();},
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


};

window.ApiExplorerModule = ApiExplorerModule;

