"""API Clone - Mapeo clase-API -> SQL Firebird real. CERO MOCKS."""
from typing import Dict, List, Optional, Tuple

# (tabla_fb, campo_pk, campo_desc, param_api)
CLASE_TABLA_MAP: Dict[str, Tuple[str, str, str, str]] = {
    # Tablas verificadas con SELECT en BD JDDC real (16/09/2026)
    "proyectos":    ("PROYECTOS",     "CODIGO",        "NOMBRE",         "codProyecto"),
    "partidas":     ("PRESUPROYE",    "CODPRESUPUESTO","CODPROYECTO",    "codProyecto"),
    # OBRALIN = lineas de obra/costes imputados a proyecto (942.084 reg)
    # Equivale a proordutil en mPYME (costes reales imputados)
    "proordutil":   ("OBRALIN",       "CODIGO",        "CODPROYECTO",    "codProyecto"),
    # OBRALIN con ESPREVISION = previsiones (mismo formato, misma tabla)
    "proordprev":   ("OBRALIN",       "CODIGO",        "CODPROYECTO",    "codProyecto"),
    # REPARA = ordenes de reparacion reales (8.412 reg, verificado)
    "reporden":     ("REPARA",        "CODIGO",        "DESCRIPCION",    "codOrden"),
    # REPCAR = lineas/materiales de reparacion (12.091 reg)
    "repordutil":   ("REPCAR",        "CODREPARA",     "CODCLASE",       "codOrden"),
    "repobjetos":   ("REPOBJETO",     "CODIGO",        "NOMBRE",       "codObjeto"),
    "repinst":      ("REPINSTALACION","CODIGO",        "NOMBRE",       "codInst"),
    "tipostrabajo": ("TIPO",          "CODIGO",        "DESCRIPCION",  "codTrabajo"),
    "recursos":     ("RECURSO",       "CODIGO",        "DESCRIPCION",  "codRecurso"),
    "articulos":    ("ARTICULO",      "CODIGO",        "NOMBRE",       "codArticulo"),
    "proveedores":  ("PROVEED",       "CODIGO",        "RAZONSOCIAL",  "codProv"),
    "clientes":     ("CLIENTE",       "CODIGO",        "RAZONSOCIAL",  "codCliente"),
    "docalbcom":    ("DOCCAB",        "CODIGO",        "NUMERO",       "codDocumento"),
    "docfaccom":    ("DOCCAB",        "CODIGO",        "NUMERO",       "codDocumento"),
    "docpedcom":    ("DOCCAB",        "CODIGO",        "NUMERO",       "codDocumento"),
    "ordenfab":     ("FABCAB",        "CODIGO",        "CODIGO",       "codOrden"),
}
CLASE_WHERE: Dict[str, str] = {
    "docalbcom": "TIPO = 2",
    "docfaccom": "TIPO = 3",
    "docpedcom": "TIPO = 11",
}
CLASE_MODULO: Dict[str, Dict[str, str]] = {
    "proyectos":    {"modulo": "Gestion de Proyectos", "licencia": "base"},
    "partidas":     {"modulo": "Gestion de Proyectos", "licencia": "base"},
    "proordutil":   {"modulo": "Gestion de Proyectos", "licencia": "mPyme Proyectos"},
    "proordprev":   {"modulo": "Gestion de Proyectos", "licencia": "mPyme Proyectos"},
    "reporden":     {"modulo": "Reparaciones", "licencia": "mPyme Reparaciones"},
    "repordutil":   {"modulo": "Reparaciones", "licencia": "mPyme Reparaciones"},
    "repobjetos":   {"modulo": "Reparaciones", "licencia": "mPyme Reparaciones"},
    "repinst":      {"modulo": "Reparaciones", "licencia": "mPyme Reparaciones"},
    "tipostrabajo": {"modulo": "Reparaciones", "licencia": "base"},
    "recursos":     {"modulo": "Maestros", "licencia": "base"},
    "articulos":    {"modulo": "Maestros", "licencia": "base"},
    "proveedores":  {"modulo": "Maestros", "licencia": "base"},
    "clientes":     {"modulo": "Maestros", "licencia": "base"},
    "docalbcom":    {"modulo": "Documentos de Compra", "licencia": "mPyme Documentos"},
    "docfaccom":    {"modulo": "Documentos de Compra", "licencia": "mPyme Documentos"},
    "docpedcom":    {"modulo": "Documentos de Compra", "licencia": "mPyme Documentos"},
    "ordenfab":     {"modulo": "Fabricacion", "licencia": "mPyme Fabricacion"},
}
# Operaciones segun documentacion oficial mPYME v1.2 (PDF extraido 16/09/2026)
# Riesgo: 0=lectura, 1=temporal(new/edit/cancel), 2=escritura real(write/imputaPro), 3=destructivo(delete)
CLASE_OPERACIONES: Dict[str, List[str]] = {
    # Gestion de Proyectos — doc pag.40-44
    "proyectos":    ["browse", "read", "new", "edit", "write", "cancel"],
    "partidas":     ["browse", "read"],
    "proordutil":   ["browse", "read", "new", "write"],
    "proordprev":   ["browse", "read", "new", "write"],
    # Reparaciones — doc pag.45-48
    "reporden":     ["browse", "read", "new", "edit", "write", "cancel"],
    "repordutil":   ["browse", "new", "write", "cancel"],
    "repobjetos":   ["browse", "read"],
    "repinst":      ["browse", "read"],
    "tipostrabajo": ["browse"],
    # Maestros — doc pag.11-21
    "recursos":     ["browse", "read"],
    "articulos":    ["browse", "read"],
    "proveedores":  ["browse"],
    "clientes":     ["browse", "read"],
    # Documentos de Compra — doc pag.22-30
    "docalbcom":    ["browse", "read", "imputaPro", "imputaRep"],
    "docfaccom":    ["browse", "read", "imputaPro"],
    "docpedcom":    ["browse"],
    "ordenfab":     ["browse"],
}

# Nivel de riesgo por operacion (segun doc oficial y api_explorer)
RIESGO_OPERACION: Dict[str, int] = {
    "browse":    0,   # Solo lectura
    "read":      0,   # Solo lectura
    "permiso":   0,   # Solo lectura
    "info":      0,   # Solo lectura
    "cancel":    0,   # Descarta objeto temporal — seguro
    "new":       1,   # Crea objeto TEMPORAL — no persiste hasta write
    "edit":      1,   # Modifica objeto temporal — no persiste hasta write
    "write":     2,   # PERSISTE en BD — IRREVERSIBLE
    "imputaPro": 2,   # Vincula linea de compra a proyecto — IRREVERSIBLE
    "imputaRep": 2,   # Vincula linea a reparacion — IRREVERSIBLE
    "imputaFab": 2,   # Vincula linea a fabricacion — IRREVERSIBLE
    "delete":    3,   # Elimina definitivamente — DESTRUCTIVO
}

# Confirmacion requerida segun riesgo
CONFIRMACION_REQUERIDA: Dict[int, str] = {
    0: "",                           # Sin confirmacion
    1: "",                           # Sin confirmacion (temporal, reversible con cancel)
    2: "CONFIRMAR ESCRITURA",        # Texto exacto requerido
    3: "CONFIRMAR BORRADO DEFINITIVO",  # Texto exacto requerido
}

# Operaciones que requieren sesion_escritura activa (riesgo >= 2)
OPERACIONES_ESCRITURA_REAL = {"write", "imputaPro", "imputaRep", "imputaFab", "delete"}
# Operaciones temporales (riesgo 1 — seguras, no necesitan doble confirmacion)
OPERACIONES_TEMPORALES = {"new", "edit", "cancel"}
CLASE_COLS_BROWSE: Dict[str, str] = {
    # Columnas verificadas con SELECT en BD JDDC (16/09/2026)
    "proyectos":    "CODIGO, NOMBRE, CLIENTE, FECHAINICIO, FECHAFIN, TIPOOBRA",
    "partidas":     "CODPRESUPUESTO, CODPROYECTO",
    # OBRALIN: CODCAB, CODIGO, CODPROYECTO, ESPREVISION, FECHA, CODARTICULO, CODRECURSO, NOMBRE
    "proordutil":   "CODCAB, CODIGO, CODPROYECTO, FECHA, CODARTICULO, CODRECURSO, NOMBRE, ESPREVISION",
    "proordprev":   "CODCAB, CODIGO, CODPROYECTO, FECHA, CODARTICULO, CODRECURSO, NOMBRE, ESPREVISION",
    # REPARA: CODIGO, SERIE, NUMERO, DESCRIPCION, FECHA, CODCLIENTE, CODESTADO
    "reporden":     "CODIGO, SERIE, NUMERO, DESCRIPCION, FECHA, CODCLIENTE, CODESTADO",
    # REPCAR: CODREPARA, CODCLASE, CODCARACT, VALOR, CANTIDAD
    "repordutil":   "CODREPARA, CODCLASE, CODCARACT, VALOR, CANTIDAD",
    "repobjetos":   "CODIGO, NOMBRE",
    "repinst":      "CODIGO, NOMBRE",
    "tipostrabajo": "CODIGO, DESCRIPCION",
    "recursos":     "CODIGO, DESCRIPCION",
    "articulos":    "CODIGO, NOMBRE, PRECIOCOSTE, PRECIOVENTA, CODFAMILIA",
    "proveedores":  "CODIGO, RAZONSOCIAL",
    "clientes":     "CODIGO, RAZONSOCIAL, NOMBRECOMERCIAL, TEL, CP",
    "docalbcom":    "CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL, CODCLIENTE",
    "docfaccom":    "CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL, CODCLIENTE",
    "docpedcom":    "CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL",
    "ordenfab":     "CODIGO",
}
CLASE_COLS_READ: Dict[str, str] = {
    # Columnas read verificadas (16/09/2026)
    "proyectos":    "CODIGO, NOMBRE, CLIENTE, FECHAINICIO, FECHAFIN, TIPOOBRA, OBSERVACIONES, PORCRETENCION",
    "partidas":     "CODPRESUPUESTO, CODPROYECTO, CODPROYSUBCONTRATA",
    "proordutil":   "CODCAB, CODIGO, CODPROYECTO, FECHA, FECHAALTA, CODARTICULO, CODRECURSO, NOMBRE, ESPREVISION, PARTIDA",
    "proordprev":   "CODCAB, CODIGO, CODPROYECTO, FECHA, FECHAALTA, CODARTICULO, CODRECURSO, NOMBRE, ESPREVISION, PARTIDA",
    "reporden":     "CODIGO, SERIE, NUMERO, DESCRIPCION, FECHA, CODCLIENTE, CODREPOBJETO, CODTIPOTRABAJO, FECHAINICIO, FECHAFIN, CODESTADO, OBSERVACIONES",
    "repordutil":   "CODREPARA, CODCLASE, CODCARACT, VALOR, CANTIDAD, VALORMEMO",
    "repobjetos":   "CODIGO, NOMBRE",
    "repinst":      "CODIGO, NOMBRE",
    "tipostrabajo": "CODIGO, DESCRIPCION",
    "recursos":     "CODIGO, DESCRIPCION",
    "articulos":    "CODIGO, NOMBRE, DESCRIPCION, PRECIOCOSTE, PRECIOVENTA, CODFAMILIA, CODMARCA, TIPOIVA, UNIDAD",
    "proveedores":  "CODIGO, RAZONSOCIAL",
    "clientes":     "CODIGO, RAZONSOCIAL, NOMBRECOMERCIAL, NIF, TEL, CP, CODFORMAPAGO",
    "docalbcom":    "CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL, IMPORTEBASE, IMPORTEIVA, CODCLIENTE, OBSERVACIONES",
    "docfaccom":    "CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL, IMPORTEBASE, IMPORTEIVA, CODCLIENTE, OBSERVACIONES",
    "docpedcom":    "CODIGO, TIPO, SERIE, NUMERO, FECHA, IMPORTETOTAL",
    "ordenfab":     "CODIGO",
}
CLASE_PARAM_REQUERIDO: Dict[str, Optional[str]] = {
    "proyectos": None, "partidas": "codProyecto",
    "proordutil": "codProyecto", "proordprev": "codProyecto",
    "reporden": None, "repordutil": "codOrden",
    "repobjetos": None, "repinst": None, "tipostrabajo": None,
    "recursos": None, "articulos": None, "proveedores": None,
    "clientes": None, "docalbcom": None, "docfaccom": None,
    "docpedcom": None, "ordenfab": None,
}
PARAM_A_COLUMNA: Dict[str, Dict[str, str]] = {
    "proyectos":    {"codProyecto": "CODIGO"},
    "partidas":     {"codProyecto": "CODPROYECTO"},
    "proordutil":   {"codProyecto": "CODPROYECTO"},   # OBRALIN.CODPROYECTO
    "proordprev":   {"codProyecto": "CODPROYECTO"},   # OBRALIN.CODPROYECTO
    "reporden":     {"codOrden": "CODIGO"},           # REPARA.CODIGO
    "repordutil":   {"codOrden": "CODREPARA"},        # REPCAR.CODREPARA
    "repobjetos":   {"codObjeto": "CODIGO"},
    "repinst":      {"codInst": "CODIGO"},
    "tipostrabajo": {"codTrabajo": "CODIGO"},
    "recursos":     {"codRecurso": "CODIGO"},
    "articulos":    {"codArticulo": "CODIGO"},
    "proveedores":  {"codProv": "CODIGO"},
    "clientes":     {"codCliente": "CODIGO"},
    "docalbcom":    {"codDocumento": "CODIGO"},
    "docfaccom":    {"codDocumento": "CODIGO"},
    "docpedcom":    {"codDocumento": "CODIGO"},
    "ordenfab":     {"codOrden": "CODIGO"},
}
ALL_CLASES = list(CLASE_TABLA_MAP.keys())

# ── Campos para el Probador Manual (desc, tipo, fk, ejemplo) ─────────────────
# Fuente: campos_clase.json + doc mPYME v1.2 + BD real verificada 16/09/2026
CAMPOS_CLASE: Dict[str, List[Dict]] = {
    "proyectos": [
        {"n":"codProyecto","desc":"Código del proyecto (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"45871","fk_tabla":"PROYECTOS","fk_campo":"CODIGO","fk_desc":"NOMBRE",
         "nota":"Dejar vacío para listar todos. Rellenar para filtrar uno."},
    ],
    "partidas": [
        {"n":"codProyecto","desc":"Código del proyecto (obligatorio)","tipo":"str","req":True,
         "ejemplo":"45871","fk_tabla":"PROYECTOS","fk_campo":"CODIGO","fk_desc":"NOMBRE",
         "nota":"Sin este campo no se devuelven datos — filtra las partidas del proyecto."},
    ],
    "proordutil": [
        {"n":"codProyecto","desc":"Código del proyecto cuyos costes reales quieres ver","tipo":"str","req":True,
         "ejemplo":"45871","fk_tabla":"PROYECTOS","fk_campo":"CODIGO","fk_desc":"NOMBRE",
         "nota":"Filtra SOLO los costes imputados a este proyecto. Sin él, 0 resultados."},
    ],
    "proordprev": [
        {"n":"codProyecto","desc":"Código del proyecto cuyas previsiones quieres ver","tipo":"str","req":True,
         "ejemplo":"45871","fk_tabla":"PROYECTOS","fk_campo":"CODIGO","fk_desc":"NOMBRE",
         "nota":"Filtra SOLO las previsiones de costes de este proyecto."},
    ],
    "reporden": [
        {"n":"codOrden","desc":"Código de orden de reparación (vacío = todas)","tipo":"str","req":False,
         "ejemplo":"1234","fk_tabla":"REPARA","fk_campo":"CODIGO","fk_desc":"DESCRIPCION",
         "nota":"Vacío = ver todas las órdenes. Con código = una sola orden."},
    ],
    "repordutil": [
        {"n":"codOrden","desc":"Código de la orden de reparación (obligatorio)","tipo":"str","req":True,
         "ejemplo":"1234","fk_tabla":"REPARA","fk_campo":"CODIGO","fk_desc":"DESCRIPCION",
         "nota":"Filtra SOLO los materiales/horas de esta orden. Sin él, 0 resultados."},
    ],
    "repobjetos": [
        {"n":"codObjeto","desc":"Código del equipo (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"OBJ-001","fk_tabla":"REPOBJETO","fk_campo":"CODIGO","fk_desc":"NOMBRE",
         "nota":"Vacío = catálogo completo de equipos reparables."},
    ],
    "repinst": [
        {"n":"codInst","desc":"Código de instalación (vacío = todas)","tipo":"str","req":False,
         "ejemplo":"INST-01","fk_tabla":"REPINSTALACION","fk_campo":"CODIGO","fk_desc":"NOMBRE",
         "nota":"Vacío = catálogo completo de instalaciones."},
    ],
    "tipostrabajo": [],
    "recursos": [
        {"n":"codRecurso","desc":"Código del recurso/técnico (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"TEC01","fk_tabla":"RECURSO","fk_campo":"CODIGO","fk_desc":"DESCRIPCION",
         "nota":"Recursos = técnicos, maquinaria. Vacío = catálogo completo."},
    ],
    "articulos": [
        {"n":"codArticulo","desc":"Código del artículo (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"CT12F","fk_tabla":"ARTICULO","fk_campo":"CODIGO","fk_desc":"NOMBRE",
         "nota":"Vacío = catálogo completo de artículos."},
    ],
    "proveedores": [
        {"n":"codProv","desc":"Código del proveedor (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"DAIKIN","fk_tabla":"PROVEED","fk_campo":"CODIGO","fk_desc":"RAZONSOCIAL",
         "nota":"Vacío = catálogo completo de proveedores."},
    ],
    "clientes": [
        {"n":"codCliente","desc":"Código del cliente (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"13300","fk_tabla":"CLIENTE","fk_campo":"CODIGO","fk_desc":"RAZONSOCIAL",
         "nota":"Vacío = catálogo completo de clientes."},
    ],
    "docalbcom": [
        {"n":"codDocumento","desc":"Código albarán de compra (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"74","fk_tabla":"DOCCAB","fk_campo":"CODIGO","fk_desc":"NUMERO",
         "nota":"TIPO=2 siempre activo. Solo albaranes de compra, nunca otros documentos."},
    ],
    "docfaccom": [
        {"n":"codDocumento","desc":"Código factura de compra (vacío = todas)","tipo":"str","req":False,
         "ejemplo":"100","fk_tabla":"DOCCAB","fk_campo":"CODIGO","fk_desc":"NUMERO",
         "nota":"TIPO=3 siempre activo. Solo facturas de compra."},
    ],
    "docpedcom": [
        {"n":"codDocumento","desc":"Código pedido de compra (vacío = todos)","tipo":"str","req":False,
         "ejemplo":"200","fk_tabla":"DOCCAB","fk_campo":"CODIGO","fk_desc":"NUMERO",
         "nota":"TIPO=11 siempre activo. Solo pedidos de compra."},
    ],
    "ordenfab": [
        {"n":"codOrden","desc":"Código orden de fabricación (vacío = todas)","tipo":"str","req":False,
         "ejemplo":"FAB001","fk_tabla":"FABCAB","fk_campo":"CODIGO","fk_desc":"CODIGO",
         "nota":"Vacío = todas las órdenes. Módulo fabricación puede no estar activo."},
    ],
}

_U = {"nivel":"ULTRA","icono":"🔒","color":"#16a34a"}
_A = {"nivel":"ALTO", "icono":"✅","color":"#0369a1"}
_M = {"nivel":"MEDIO","icono":"⚠️","color":"#ca8a04"}

FIABILIDAD_CLASE: Dict[str, Dict] = {
    "proyectos":   {**_U,"titulo":"100% fiable — PK directa","explicacion":"PROYECTOS.CODIGO es PK única. Imposible ver proyectos incorrectos.","detalle":["✅ PK única en BD","✅ Sin JOIN — 0 riesgo","✅ 1.213 proyectos reales"],"sql_ejemplo":"SELECT FIRST 20 CODIGO, NOMBRE, CLIENTE FROM PROYECTOS ORDER BY CODIGO"},
    "partidas":    {**_U,"titulo":"100% fiable — FK a PROYECTOS","explicacion":"PRESUPROYE.CODPROYECTO es FK a PROYECTOS.CODIGO. Solo partidas de ESE proyecto.","detalle":["✅ FK a PROYECTOS.CODIGO","✅ WHERE aísla por proyecto","✅ 1.710 partidas reales"],"sql_ejemplo":"SELECT CODPRESUPUESTO, CODPROYECTO FROM PRESUPROYE WHERE CODPROYECTO='45871'"},
    "proordutil":  {**_U,"titulo":"100% fiable — FK garantiza aislamiento total","explicacion":"OBRALIN.CODPROYECTO es FK a PROYECTOS.CODIGO. Los costes del X NUNCA se mezclan con los del Y.","detalle":["✅ OBRALIN.CODPROYECTO = FK a PROYECTOS.CODIGO","✅ WHERE aísla 100%","✅ 942.084 registros reales"],"sql_ejemplo":"SELECT CODIGO, CODPROYECTO, FECHA, CODARTICULO FROM OBRALIN WHERE CODPROYECTO='45871'"},
    "proordprev":  {**_U,"titulo":"100% fiable — FK garantiza aislamiento","explicacion":"Misma tabla OBRALIN. FK a PROYECTOS. Las previsiones del X no se mezclan con las del Y.","detalle":["✅ FK a PROYECTOS.CODIGO","✅ Aislamiento total"],"sql_ejemplo":"SELECT CODIGO, CODPROYECTO FROM OBRALIN WHERE CODPROYECTO='45871'"},
    "reporden":    {**_A,"titulo":"Muy fiable — PK directa","explicacion":"REPARA.CODIGO es PK. 8.412 órdenes SAT reales.","detalle":["✅ REPARA.CODIGO es PK","✅ Sin JOIN","✅ 8.412 órdenes"],"sql_ejemplo":"SELECT CODIGO, DESCRIPCION, FECHA, CODCLIENTE FROM REPARA ORDER BY FECHA DESC"},
    "repordutil":  {**_A,"titulo":"Muy fiable — FK aísla por orden","explicacion":"REPCAR.CODREPARA es FK a REPARA.CODIGO. Solo materiales/horas de esa orden. Imposible ver datos de otra.","detalle":["✅ FK a REPARA.CODIGO","✅ WHERE aísla totalmente","✅ 12.091 registros"],"sql_ejemplo":"SELECT CODREPARA, CODCLASE, VALOR, CANTIDAD FROM REPCAR WHERE CODREPARA='1234'"},
    "repobjetos":  {**_A,"titulo":"Muy fiable — PK directa","explicacion":"REPOBJETO.CODIGO es PK. 445 equipos reales.","detalle":["✅ PK directa","✅ 445 equipos"],"sql_ejemplo":"SELECT CODIGO, NOMBRE FROM REPOBJETO"},
    "repinst":     {**_A,"titulo":"Muy fiable — PK directa","explicacion":"REPINSTALACION.CODIGO es PK. 124 instalaciones reales.","detalle":["✅ PK directa","✅ 124 instalaciones"],"sql_ejemplo":"SELECT CODIGO, NOMBRE FROM REPINSTALACION"},
    "tipostrabajo":{**_A,"titulo":"Muy fiable — tabla maestra","explicacion":"TIPO.CODIGO es PK. Tabla maestra inmutable.","detalle":["✅ PK directa","✅ Tabla maestra"],"sql_ejemplo":"SELECT CODIGO, DESCRIPCION FROM TIPO"},
    "recursos":    {**_A,"titulo":"Muy fiable — PK directa","explicacion":"RECURSO.CODIGO es PK. 186 técnicos/maquinaria reales.","detalle":["✅ PK directa","✅ 186 recursos"],"sql_ejemplo":"SELECT CODIGO, DESCRIPCION FROM RECURSO"},
    "articulos":   {**_A,"titulo":"Muy fiable — PK directa","explicacion":"ARTICULO.CODIGO es PK. 12.377 artículos del catálogo real.","detalle":["✅ PK directa","✅ 12.377 artículos"],"sql_ejemplo":"SELECT CODIGO, NOMBRE, PRECIOCOSTE FROM ARTICULO"},
    "proveedores": {**_A,"titulo":"Muy fiable — PK directa","explicacion":"PROVEED.CODIGO es PK. 1.789 proveedores reales.","detalle":["✅ PK directa","✅ 1.789 proveedores"],"sql_ejemplo":"SELECT CODIGO, RAZONSOCIAL FROM PROVEED"},
    "clientes":    {**_A,"titulo":"Muy fiable — PK directa","explicacion":"CLIENTE.CODIGO es PK. 9.427 clientes reales.","detalle":["✅ PK directa","✅ 9.427 clientes"],"sql_ejemplo":"SELECT CODIGO, RAZONSOCIAL FROM CLIENTE"},
    "docalbcom":   {**_A,"titulo":"Muy fiable — TIPO=2 hardcodeado","explicacion":"DOCCAB con WHERE TIPO=2 siempre activo. Imposible mezclar con facturas. 5.694 albaranes.","detalle":["✅ WHERE TIPO=2 hardcodeado","✅ 5.694 albaranes"],"sql_ejemplo":"SELECT CODIGO, TIPO, SERIE, NUMERO FROM DOCCAB WHERE TIPO=2"},
    "docfaccom":   {**_A,"titulo":"Muy fiable — TIPO=3 hardcodeado","explicacion":"WHERE TIPO=3 siempre activo. Solo facturas. 8.592 reales.","detalle":["✅ WHERE TIPO=3","✅ 8.592 facturas"],"sql_ejemplo":"SELECT CODIGO, TIPO, SERIE, NUMERO FROM DOCCAB WHERE TIPO=3"},
    "docpedcom":   {**_A,"titulo":"Muy fiable — TIPO=11 hardcodeado","explicacion":"WHERE TIPO=11 siempre activo. Solo pedidos. 10.757 reales.","detalle":["✅ WHERE TIPO=11","✅ 10.757 pedidos"],"sql_ejemplo":"SELECT CODIGO, TIPO, SERIE, NUMERO FROM DOCCAB WHERE TIPO=11"},
    "ordenfab":    {**_M,"titulo":"Fiabilidad media — módulo puede no estar activo","explicacion":"FABCAB existe pero el módulo fabricación puede no estar contratado (0 registros diagnóstico 16/09/2026).","detalle":["⚠️ FABCAB puede estar vacía","⚠️ Verificar módulo"],"sql_ejemplo":"SELECT CODIGO FROM FABCAB"},
}
LOOKUP_CAMPO: Dict[str, Dict] = {
    "codProyecto": {"tabla":"PROYECTOS","id":"CODIGO","desc":"NOMBRE","label":"Proyectos"},
    "codOrden":    {"tabla":"REPARA","id":"CODIGO","desc":"DESCRIPCION","label":"Órdenes SAT"},
    "codRecurso":  {"tabla":"RECURSO","id":"CODIGO","desc":"DESCRIPCION","label":"Recursos"},
    "codArticulo": {"tabla":"ARTICULO","id":"CODIGO","desc":"NOMBRE","label":"Artículos"},
    "codProv":     {"tabla":"PROVEED","id":"CODIGO","desc":"RAZONSOCIAL","label":"Proveedores"},
    "codCliente":  {"tabla":"CLIENTE","id":"CODIGO","desc":"RAZONSOCIAL","label":"Clientes"},
    "codDocumento":{"tabla":"DOCCAB","id":"CODIGO","desc":"NUMERO","label":"Documentos"},
    "codObjeto":   {"tabla":"REPOBJETO","id":"CODIGO","desc":"NOMBRE","label":"Equipos"},
    "codInst":     {"tabla":"REPINSTALACION","id":"CODIGO","desc":"NOMBRE","label":"Instalaciones"},
    "codTrabajo":  {"tabla":"TIPO","id":"CODIGO","desc":"DESCRIPCION","label":"Tipos trabajo"},
    "codPartida":  {"tabla":"PRESUPROYE","id":"CODPRESUPUESTO","desc":"CODPROYECTO","label":"Partidas"},
}
