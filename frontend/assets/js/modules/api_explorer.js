/**
 * api_explorer.js v5 — Modulo API Explorer de DEVIA.
 * Explorador/Validador API Distrito K / SQL Obras (mPYME API 1.2).
 * MODO SOLO LECTURA por defecto.
 */
const API = "/api/api-explorer";

let _state = {
  status: null, config: null, catalogue: null,
  history: [], matrix: {}, currentTab: "conexion",
  selectedModulo: null, selectedClase: null, selectedOp: null,
  paramValues: {},
  loginMsg: null,   // {type: "ok"|"error"|"info", html: string} — persiste entre renders
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
  return { ok:"✅", falla:"❌", sin_permiso:"🔒", sin_licencia:"🚫", bloqueado:"⛔", no_probado:"⬜" }[e] || "❓";
}
function estadoColor(e) {
  return { ok:"#28a745", falla:"#dc3545", sin_permiso:"#6c757d", sin_licencia:"#dc3545", bloqueado:"#fd7e14" }[e] || "#6c757d";
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
  const bg = r.estado === "ok" ? "#e8f5e9" : r.estado === "bloqueado" ? "#fff3e0" : ["sin_permiso","sin_licencia"].includes(r.estado) ? "#f3e5f5" : "#ffebee";
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

  const TABS = [["conexion","🔌 Conexion"],["explorador","🔬 Explorador"],["permisos","🔍 Permisos"],["matriz","📊 Matriz"],["historial","📜 Historial"],["escritura","🟠 Escritura"]];
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
          <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;padding:8px 12px;margin-top:6px">
            <p style="font-size:0.73em;color:#92400e;font-weight:600;margin:0 0 4px">3️⃣ Probar credenciales por defecto (opcional)</p>
            <p style="font-size:0.71em;color:#b45309;margin:0 0 6px">
              Prueba hasta 10 combinaciones predeterminadas (SYSDBA/masterkey, admin/admin...) con 1s entre cada intento.
              No es un ataque — son valores de fábrica documentados. Para al primer éxito.
            </p>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px">
              <div>
                <label style="font-size:0.72em;color:#92400e;display:block;margin-bottom:2px">URL del servidor mPYME</label>
                <input id="ae-cred-url" type="text" placeholder="http://192.168.0.254:8081/" class="form-control" style="font-size:0.76em;width:100%">
              </div>
              <div>
                <label style="font-size:0.72em;color:#92400e;display:block;margin-bottom:2px">Empresa (puede quedar vacía)</label>
                <input id="ae-cred-empresa" type="text" placeholder="JUANDEDI o 1" class="form-control" style="font-size:0.76em;width:100%">
              </div>
            </div>
            <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
              <input id="ae-cred-confirm" type="text" placeholder='Escribe: PROBAR CREDENCIALES' class="form-control" style="font-size:0.76em;flex:1;min-width:180px">
              <button onclick="ApiExplorerModule.doDiscoverCreds()" class="btn secondary" style="font-size:0.76em;background:#fff7ed;border-color:#fed7aa;color:#92400e;white-space:nowrap">🔐 Probar defaults</button>
            </div>
            <div id="ae-discover-creds-result" style="margin-top:6px"></div>
          </div>
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


const ApiExplorerModule = {
  async onEnter() {
    const root=document.getElementById("api-explorer-root");
    if(root) root.innerHTML=`<div style="text-align:center;padding:40px;color:#64748b">Cargando...</div>`;
    try {
      const [s,c,cat,hd]=await Promise.all([_fetch("/status"),_fetch("/config"),_fetch("/catalogue"),_fetch("/history")]);
      _state.status=s;_state.config=c;_state.catalogue=cat;_state.history=hd.history||[];_state.matrix=hd.matrix||{};
    } catch(e) {
      if(root) root.innerHTML=`<div style="padding:24px;color:#dc2626;background:#fef2f2;border-radius:8px"><strong>Error al cargar</strong><br>${e.message}</div>`;
      return;
    }
    renderMain();
  },
  setTab(t){_state.currentTab=t;renderMain();},
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

  async doDiscoverDb() {
    const resultDiv = document.getElementById("ae-discover-db-result");
    if (resultDiv) resultDiv.innerHTML = `<div style="color:#64748b;font-size:0.82em;padding:6px 0">👤 Consultando Firebird... (solo SELECT, sin escrituras)</div>`;
    try {
      const resp = await fetch("/api/api-explorer/discover-db", { method: "POST", headers: {"Content-Type":"application/json"} });
      const r = await resp.json();
      if (!resultDiv) return;
      if (r.error && !r.success) {
        resultDiv.innerHTML = `<div style="background:#fef2f2;border-left:3px solid #dc3545;border-radius:5px;padding:8px 12px;font-size:0.82em;color:#991b1b">
          <strong>❌ Error al conectar con Firebird</strong><br>${r.error}<br>
          <span style="font-size:0.9em;color:#64748b">Verifica DB_HOST, DB_NAME, DB_USER y DB_PASSWORD en el .env</span></div>`;
        return;
      }
      let html = `<div style="background:#f0fdf4;border-left:3px solid #16a34a;border-radius:5px;padding:7px 12px;font-size:0.82em;color:#166534;margin-bottom:6px">
        <strong>✅ Consulta Firebird OK</strong> — ${r.tablas_inspeccionadas} tablas inspeccionadas
        <span style="color:#94a3b8;font-size:0.85em"> | Solo lectura. Sin modificaciones.</span></div>`;
      if (r.usuarios_firebird && r.usuarios_firebird.length) {
        html += `<div style="background:white;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:0.82em">
          <p style="margin:0 0 5px;font-weight:600;color:#374151">👥 Usuarios Firebird (RDB$USERS)</p>
          <div style="display:flex;flex-wrap:wrap;gap:5px">
            ${r.usuarios_firebird.map(u => {
              const sys = u.toUpperCase()==="SYSDBA";
              const bg = sys?"#fee2e2":"#dbeafe"; const txt = sys?"#991b1b":"#1e40af";
              return `<span style="background:${bg};color:${txt};border-radius:12px;padding:2px 8px;font-size:0.9em;cursor:pointer"
                onclick="document.getElementById('ae-usuario').value='${u}'" title="Clic para usar como SQLOB_USUARIO">${u} ${sys?"⚠️":"👆"}</span>`;
            }).join("")}
          </div>
          <p style="margin:5px 0 0;font-size:0.82em;color:#94a3b8">Clic en un usuario para rellenar el campo. No uses SYSDBA para la API.</p></div>`;
      }
      if (r.usuarios_sqlobras && r.usuarios_sqlobras.length) {
        const keys = Object.keys(r.usuarios_sqlobras[0]);
        html += `<div style="background:white;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:0.82em">
          <p style="margin:0 0 5px;font-weight:600;color:#374151">🏢 Usuarios SQL Obras (${r.tabla_usuarios_encontrada})</p>
          <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:0.88em">
            <thead><tr style="background:#f8fafc">${keys.map(k=>`<th style="padding:3px 8px;text-align:left;color:#64748b;border-bottom:1px solid #e2e8f0">${k}</th>`).join("")}<th style="padding:3px 8px;color:#64748b;border-bottom:1px solid #e2e8f0">Usar</th></tr></thead>
            <tbody>${r.usuarios_sqlobras.slice(0,20).map(row=>`<tr style="border-bottom:1px solid #f1f5f9">
              ${keys.map(k=>`<td style="padding:3px 8px">${row[k]||"—"}</td>`).join("")}
              <td style="padding:3px 8px"><button onclick="document.getElementById('ae-usuario').value='${Object.values(row)[0]}'" class="btn secondary" style="font-size:0.75em;padding:1px 6px">👆 Usar</button></td>
            </tr>`).join("")}</tbody>
          </table></div></div>`;
      }
      if (r.empresa_inferida) {
        html += `<div style="background:#fefce8;border:1px solid #fde047;border-radius:6px;padding:7px 12px;margin-bottom:6px;font-size:0.82em">
          <strong>🏢 Empresa inferida:</strong>
          <code style="background:white;padding:2px 6px;border-radius:3px;margin:0 6px;cursor:pointer"
            onclick="document.getElementById('ae-empresa').value='${r.empresa_inferida}'" title="Clic para usar">${r.empresa_inferida} 👆</code>
          <span style="color:#92400e;font-size:0.9em">Confirmar con Distrito K el codigo exacto</span></div>`;
      }
      html += `<div>`;
      for (const rec of (r.recomendaciones || [])) {
        const colors = {advertencia:["#fff7ed","#fb923c"], ok:["#f0fdf4","#16a34a"], clave:["#fef2f2","#dc3545"], info:["#f0f9ff","#38bdf8"]};
        const [bg, br] = colors[rec.nivel] || colors.info;
        html += `<div style="background:${bg};border-left:3px solid ${br};border-radius:4px;padding:6px 10px;margin-bottom:4px;font-size:0.8em">
          ${rec.icono} ${rec.texto}`;
        if (rec.usuarios_candidatos && rec.usuarios_candidatos.length) {
          html += `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">
            ${rec.usuarios_candidatos.map(u=>`<code style="background:white;padding:1px 6px;border-radius:10px;font-size:0.9em;cursor:pointer"
              onclick="document.getElementById('ae-usuario').value='${u}'" title="Usar como usuario">${u}</code>`).join("")}</div>`;
        }
        html += `</div>`;
      }
      html += `</div>`;
      resultDiv.innerHTML = html;
    } catch(e) {
      if (resultDiv) resultDiv.innerHTML = `<div style="color:#dc3545;font-size:0.82em">❌ Error: ${e.message}</div>`;
    }
  },



  async doDiscoverCreds() {
    const url = document.getElementById("ae-cred-url")?.value?.trim() || "";
    const empresa = document.getElementById("ae-cred-empresa")?.value?.trim() || "";
    const confirm = document.getElementById("ae-cred-confirm")?.value?.trim() || "";
    const resultDiv = document.getElementById("ae-discover-creds-result");

    if (confirm !== "PROBAR CREDENCIALES") {
      if (resultDiv) resultDiv.innerHTML = `<div style="background:#fef2f2;border-left:3px solid #dc3545;border-radius:4px;padding:8px 12px;font-size:0.82em;color:#991b1b">
        ⛔ Escribe exactamente <strong>PROBAR CREDENCIALES</strong> en el campo de confirmación para ejecutar.</div>`;
      return;
    }
    if (!url) {
      if (resultDiv) resultDiv.innerHTML = `<div style="background:#fef9c3;border-left:3px solid #fde047;border-radius:4px;padding:8px 12px;font-size:0.82em;color:#92400e">
        ⚠️ Introduce la URL del servidor mPYME. Usa primero <strong>🔍 Descubrir URL</strong> para encontrarla.</div>`;
      return;
    }

    if (resultDiv) resultDiv.innerHTML = `<div style="color:#92400e;font-size:0.82em;padding:6px 0">
      🔐 Probando credenciales predeterminadas... (hasta 10 intentos, 1s entre cada uno)</div>`;

    try {
      const resp = await fetch("/api/api-explorer/discover-credentials", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({empresa, url, confirmacion: "PROBAR CREDENCIALES"}),
      });
      const r = await resp.json();
      if (!resultDiv) return;

      let html = "";
      // Resultado principal
      if (r.encontrado) {
        html += `<div style="background:#fef2f2;border:2px solid #dc3545;border-radius:6px;padding:10px 14px;margin-bottom:8px">
          <p style="margin:0 0 5px;font-weight:700;color:#991b1b;font-size:0.9em">🚨 CREDENCIALES POR DEFECTO FUNCIONAN</p>
          <p style="margin:0;font-size:0.85em;color:#991b1b">
            Usuario: <code style="background:#fee2e2;padding:1px 5px;border-radius:3px">${r.encontrado.usuario}</code>
            &nbsp; Password: <code style="background:#fee2e2;padding:1px 5px;border-radius:3px">${r.encontrado.password || "(sin password)"}</code>
          </p>
          <p style="margin:6px 0 0;font-size:0.82em;color:#7f1d1d">Riesgo de seguridad. Cambia la contraseña inmediatamente.</p>
          <button onclick="document.getElementById('ae-usuario').value='${r.encontrado.usuario}';document.getElementById('ae-password').value='${r.encontrado.password}'"
            class="btn secondary" style="font-size:0.76em;margin-top:6px;background:#fee2e2;border-color:#dc3545;color:#991b1b">
            👆 Usar estos datos para conectar ahora
          </button>
        </div>`;
      } else {
        const esBueno = r.intentos && r.intentos.every(i => i.estado === "rechazado");
        html += `<div style="background:${esBueno?"#f0fdf4":"#fefce8"};border-left:3px solid ${esBueno?"#16a34a":"#fde047"};border-radius:5px;padding:8px 12px;margin-bottom:8px;font-size:0.82em">
          ${esBueno?"✅":"ℹ️"} ${r.recomendacion}</div>`;
      }

      // Nota de seguridad
      html += `<div style="background:#f8fafc;border-radius:4px;padding:6px 10px;font-size:0.77em;color:#64748b;margin-bottom:6px">
        🛡️ ${r.nota_seguridad}</div>`;

      // Tabla de intentos
      if (r.intentos && r.intentos.length) {
        html += `<details style="margin-bottom:4px"><summary style="cursor:pointer;font-size:0.8em;color:#64748b;user-select:none">
          Ver detalle de intentos (${r.total_intentos} / ${r.max_intentos} máximo)</summary>
          <div style="overflow-x:auto;margin-top:5px"><table style="width:100%;border-collapse:collapse;font-size:0.78em">
            <thead><tr style="background:#f8fafc">
              <th style="padding:3px 6px;text-align:left;border-bottom:1px solid #e2e8f0">#</th>
              <th style="padding:3px 6px;text-align:left;border-bottom:1px solid #e2e8f0">Usuario</th>
              <th style="padding:3px 6px;text-align:left;border-bottom:1px solid #e2e8f0">Password</th>
              <th style="padding:3px 6px;text-align:center;border-bottom:1px solid #e2e8f0">Estado</th>
              <th style="padding:3px 6px;text-align:left;border-bottom:1px solid #e2e8f0">Detalle</th>
              <th style="padding:3px 6px;text-align:right;border-bottom:1px solid #e2e8f0">ms</th>
            </tr></thead><tbody>
            ${r.intentos.map(it => {
              const icon = it.estado==="ok"?"✅":it.estado==="rechazado"?"❌":it.estado==="timeout"?"⏱️":it.estado==="sin_conexion"?"🔌":"⚠️";
              const bg = it.estado==="ok"?"#fef2f2":"";
              return `<tr style="border-bottom:1px solid #f1f5f9;background:${bg}">
                <td style="padding:3px 6px;color:#94a3b8">${it.n}</td>
                <td style="padding:3px 6px;font-family:monospace">${it.usuario}</td>
                <td style="padding:3px 6px;font-family:monospace;color:#94a3b8">${it.password_display}</td>
                <td style="padding:3px 6px;text-align:center">${icon} ${it.estado}</td>
                <td style="padding:3px 6px;color:#64748b">${it.mensaje||"—"}</td>
                <td style="padding:3px 6px;text-align:right;color:#94a3b8">${it.ms||"—"}</td>
              </tr>`;
            }).join("")}
            </tbody></table></div></details>`;
      }
      resultDiv.innerHTML = html;
    } catch(e) {
      if (resultDiv) resultDiv.innerHTML = `<div style="color:#dc3545;font-size:0.82em">❌ Error: ${e.message}</div>`;
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
};

window.ApiExplorerModule = ApiExplorerModule;

