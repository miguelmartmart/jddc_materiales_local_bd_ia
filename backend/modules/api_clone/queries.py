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
