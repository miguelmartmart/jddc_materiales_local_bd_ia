const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/assets/js/modules/api_clone.js'), 'utf8');

function context() {
  const ctx = {window:{},document:{getElementById:()=>null},console,setTimeout};
  vm.createContext(ctx);
  vm.runInContext(source, ctx);
  return ctx;
}

test('groups expose plain help, example, action and optional SQL; escape data', () => {
  const ctx=context();
  const html=ctx._renderGroupedChecks({grupos:[{nombre:'Datos <img>',ayuda:'Ayuda & contexto',estado_codigo:'revisar',checks:[{
    nombre:'Cantidades',estado_codigo:'no_verificable',detalle:'No se pudo comprobar',descripcion:'Descripción',ejemplo:'Ejemplo',accion:'Revisar',sql:'SELECT a < b',
  }]}]});
  for (const text of ['¿Qué comprueba este grupo?', 'Ayuda y ejemplo', 'Qué hacer:', 'Detalle técnico (opcional)', 'No verificable', 'No aplica']) assert.ok(html.includes(text));
  assert.ok(html.includes('Datos &lt;img&gt;'));
  assert.ok(html.includes('SELECT a &lt; b'));
  assert.ok(!html.includes('<img>'));
});

test('old or empty report does not imply success', () => {
  const html=context()._renderGroupedChecks({checks:[]});
  assert.ok(html.includes('No se recibió'));
  assert.ok(!html.includes('DATOS COHERENTES'));
});

test('empty project explains absence instead of certifying zero hours', () => {
  const html=context()._renderProjectActivity({cod_proyecto:'1001331',actividad:{LINEAS:0},tecnicos:[],grupos:[],mensaje:'No tiene líneas'});
  assert.ok(html.includes('No tiene líneas'));
  assert.ok(html.includes('no verificados'));
  assert.ok(!html.includes('Datos reales Firebird'));
  assert.ok(!html.includes('N_TECNICOS'));
});

test('project picker shows total, search and next page safely', () => {
  const ctx=context();
  vm.runInContext('_state.utilProjectLookup={q:"",offset:0,total:1214,hay_mas:true,valores:[{id:"A",desc:"<img>",estado:"Finalizado"}]}',ctx);
  const html=ctx._renderProjectLookup();
  assert.ok(html.includes('de 1214 proyectos'));
  assert.ok(html.includes('Buscar por código o nombre'));
  assert.ok(html.includes('Siguiente'));
  assert.ok(!html.includes('<img>'));
});

test('late result cannot overwrite a different selected utility', async () => {
  const ctx=context();
  let resolve;
  ctx.fetch=()=>new Promise(r=>{resolve=r;});
  ctx.window.ApiCloneModule.doUtilSelect('verificacion-coherencia');
  const pending=ctx.window.ApiCloneModule.doUtilEjecutar();
  ctx.window.ApiCloneModule.doUtilSelect('resumen-costes');
  resolve({ok:true,json:async()=>({grupos:[],veredicto:'OLD'})});
  await pending;
  assert.equal(vm.runInContext('_state.utilResultado',ctx),null);
  assert.equal(vm.runInContext('_state.utilBusy',ctx),false);
});

test('late result cannot overwrite a changed project', async () => {
  const ctx=context();
  let resolve;
  ctx.fetch=()=>new Promise(r=>{resolve=r;});
  ctx.window.ApiCloneModule.doUtilSelect('resumen-costes');
  ctx.window.ApiCloneModule.doUtilParamChange('cod_proyecto','A');
  const pending=ctx.window.ApiCloneModule.doUtilEjecutar();
  ctx.window.ApiCloneModule.doUtilParamChange('cod_proyecto','B');
  resolve({ok:true,json:async()=>({cod_proyecto:'A'})});
  await pending;
  assert.equal(vm.runInContext('_state.utilResultado',ctx),null);
  assert.equal(vm.runInContext('_state.utilParams.cod_proyecto',ctx),'B');
  assert.equal(vm.runInContext('_state.utilBusy',ctx),false);
});


test('report action is visible from initial page and historical guarantee is removed', () => {
  const ctx=context();
  const html=ctx._buildUI();
  assert.ok(html.includes('Comprobar y exportar informe TXT'));
  assert.ok(html.includes('Ver comprobaciones y ayudas'));
  const badge=ctx._fiabilidadBadge({titulo:'100% fiable',nivel:'ULTRA',sql_ejemplo:'SELECT <x>'});
  assert.ok(!badge.includes('100% fiable'));
  assert.ok(badge.includes('&lt;x&gt;'));
});

test('report download explains missing backend and releases busy state', async () => {
  const ctx=context();
  ctx.fetch=async()=>({ok:false,status:404});
  await ctx.window.ApiCloneModule.doExportReport();
  assert.equal(vm.runInContext('_state.reportBusy',ctx),false);
  assert.match(vm.runInContext('_state.reportError',ctx),/reinicia DEVIA/);
});


test('manual read submits the complete line key, not the project code', async () => {
  const ctx=context();
  ctx.document.getElementById=id=>id==='prob-line-key'?{value:'20:1'}:null;
  let body;
  ctx.fetch=async(url,opts)=>{body=JSON.parse(opts.body);return {ok:true,json:async()=>({estado:'ok',data:{}})};};
  vm.runInContext('_state.probadorClase="proordutil";_state.probadorOperacion="read";_state.probadorParams={codProyecto:"A"}',ctx);
  await ctx.window.ApiCloneModule.doProbadorEjecutar();
  assert.equal(body.objectid,'20:1');
});


test('manual browser sends offset and changing scope resets it', async () => {
  const ctx=context();
  let body;
  ctx.fetch=async(url,opts)=>{body=JSON.parse(opts.body);return {ok:true,json:async()=>({estado:'ok',data:{items:[]}})};};
  vm.runInContext('_state.probadorClase="proyectos";_state.probadorOperacion="browse"',ctx);
  ctx.window.ApiCloneModule.doProbadorOffsetChange('20');
  await ctx.window.ApiCloneModule.doProbadorEjecutar();
  assert.equal(body.offset,20);
  ctx.window.ApiCloneModule.doProbadorParamChange('codProyecto','A');
  assert.equal(vm.runInContext('_state.probadorOffset',ctx),0);
});
