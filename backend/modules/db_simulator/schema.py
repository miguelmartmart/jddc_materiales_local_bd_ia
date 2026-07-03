"""
schema.py — Esquemas SQLite de las tablas principales de la BD JDDC.

Define las sentencias CREATE TABLE para SQLite que replican fielmente
la estructura de la BD Firebird, usando nombres de columna idénticos
a los de la BD real (verificados contra simulator.db / snapshot real).

Importado por driver.py y snapshot_service.py.

Notas de compatibilidad:
  - BLOB de Firebird → TEXT en SQLite
  - DATE de Firebird → TEXT (formato 'YYYY-MM-DD') en SQLite
  - INTEGER/FLOAT → INTEGER/REAL en SQLite

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from typing import Dict, List

# ─── Sentencias CREATE TABLE ──────────────────────────────────────────────────

TABLE_SCHEMAS: Dict[str, str] = {

    "FAMILIA": """
        CREATE TABLE IF NOT EXISTS FAMILIA (
            CODIGO      INTEGER PRIMARY KEY,
            NOMBRE      TEXT    NOT NULL,
            DESCRIPCION TEXT
        )
    """,

    "ALMACEN": """
        CREATE TABLE IF NOT EXISTS ALMACEN (
            CODIGO    INTEGER PRIMARY KEY,
            NOMBRE    TEXT    NOT NULL,
            DIRECCION TEXT
        )
    """,

    "RECURSO": """
        CREATE TABLE IF NOT EXISTS RECURSO (
            CODIGO      INTEGER PRIMARY KEY,
            DESCRIPCION TEXT    NOT NULL,
            CODPADRE    INTEGER DEFAULT 0,
            ORDEN       INTEGER DEFAULT 0,
            NIF         TEXT,
            NSS         TEXT,
            TELEFONO    TEXT,
            EMAIL       TEXT
        )
    """,

    # Columnas verificadas contra BD real Firebird (simulator.db snapshot)
    "PROVEED": """
        CREATE TABLE IF NOT EXISTS PROVEED (
            CODIGO          INTEGER PRIMARY KEY,
            NOMBRECOMERCIAL TEXT,
            RAZONSOCIAL     TEXT,
            TEL             TEXT,
            CP              TEXT,
            NIF             TEXT,
            CODFORMAPAGO    TEXT,
            CODAGENTE       INTEGER DEFAULT 0,
            BAJA            INTEGER DEFAULT 0
        )
    """,

    # Columnas verificadas contra BD real Firebird (simulator.db snapshot)
    "ARTICULO": """
        CREATE TABLE IF NOT EXISTS ARTICULO (
            CODIGO           INTEGER PRIMARY KEY,
            CODFAMILIA       INTEGER DEFAULT 0,
            NOMBRE           TEXT    NOT NULL,
            DESCRIPCION      TEXT,
            DESCRIPCIONCORTA TEXT,
            REFERENCIA       TEXT,
            PRECIOCOSTE      REAL    DEFAULT 0.0,
            PRECIOVENTA      REAL    DEFAULT 0.0,
            TIPOIVA          REAL    DEFAULT 21.0,
            CONTROLSTOCK     INTEGER DEFAULT 0,
            BAJA             INTEGER DEFAULT 0,
            UNIDAD           TEXT    DEFAULT 'UD',
            STOCKARTICULO    REAL    DEFAULT 0.0,
            PROVEEDDEFECTO   INTEGER DEFAULT 0
        )
    """,

    # Columnas verificadas contra BD real Firebird (simulator.db snapshot)
    "CLIENTE": """
        CREATE TABLE IF NOT EXISTS CLIENTE (
            CODIGO          INTEGER PRIMARY KEY,
            NOMBRECOMERCIAL TEXT,
            RAZONSOCIAL     TEXT,
            TEL             TEXT,
            CP              TEXT,
            NIF             TEXT,
            CODFORMAPAGO    TEXT    DEFAULT 'CONTADO',
            CODAGENTE       INTEGER DEFAULT 0,
            BAJA            INTEGER DEFAULT 0
        )
    """,

    # Columnas verificadas contra BD real Firebird (simulator.db snapshot)
    # IMPORTEBASE = base imponible, IMPORTEIVA = cuota IVA, IMPORTETOTAL = total
    "DOCCAB": """
        CREATE TABLE IF NOT EXISTS DOCCAB (
            CODIGO            INTEGER PRIMARY KEY,
            TIPO              INTEGER NOT NULL DEFAULT 13,
            SERIE             TEXT    DEFAULT 'A',
            NUMERO            INTEGER DEFAULT 0,
            FECHA             TEXT    NOT NULL,
            CODCLIENTE        INTEGER DEFAULT 0,
            CODAGENTE         INTEGER DEFAULT 0,
            CODALMACEN        INTEGER DEFAULT 1,
            CODFORMAPAGO      TEXT,
            DESCRIPCION       TEXT,
            OBSERVACIONES     TEXT,
            IMPORTEBASE       REAL    DEFAULT 0.0,
            IMPORTEIVA        REAL    DEFAULT 0.0,
            IMPORTETOTAL      REAL    DEFAULT 0.0,
            ESTADO            INTEGER DEFAULT 0,
            ESTADOPEND        INTEGER DEFAULT 0,
            ESTADOPENDVENCOM  INTEGER DEFAULT 0,
            CODPROYECTO       TEXT    DEFAULT NULL
        )
    """,

    # Columnas verificadas contra BD real Firebird (simulator.db snapshot)
    # DESCUENTOS (no DESCUENTO), sin columna IMPORTE directa
    "DOCLIN": """
        CREATE TABLE IF NOT EXISTS DOCLIN (
            CODDOCUMENTO INTEGER NOT NULL,
            CODIGO       INTEGER NOT NULL,
            CODARTICULO  TEXT,
            DESCRIPCION  TEXT,
            CANTIDAD     REAL    DEFAULT 1.0,
            PRECIO       REAL    DEFAULT 0.0,
            COSTE        REAL    DEFAULT 0.0,
            DESCUENTOS   REAL    DEFAULT 0.0,
            PRIMARY KEY (CODDOCUMENTO, CODIGO)
        )
    """,

    # Columnas verificadas contra BD real Firebird (simulator.db snapshot)
    # CODAPUNTE es la PK, CONCEPTO es el texto libre
    "CAJA": """
        CREATE TABLE IF NOT EXISTS CAJA (
            FECHA      TEXT    NOT NULL,
            CODAPUNTE  INTEGER PRIMARY KEY,
            TIPO       INTEGER DEFAULT 1,
            IMPORTE    REAL    DEFAULT 0.0,
            CONCEPTO   TEXT,
            CODCLIENTE INTEGER DEFAULT 0,
            CODUSUARIO INTEGER DEFAULT 0
        )
    """,

    # Columnas verificadas contra BD real Firebird (simulator.db snapshot)
    # ESTALMACEN: estadísticas de almacén por período (CODIGO=período, no artículo)
    # No tiene CODARTICULO ni CODALMACEN — es una tabla de totales por período
    "ESTALMACEN": """
        CREATE TABLE IF NOT EXISTS ESTALMACEN (
            CODIGO   INTEGER PRIMARY KEY,
            FECHA    TEXT    NOT NULL,
            IMPCOSTE REAL    DEFAULT 0.0,
            IMPVENTA REAL    DEFAULT 0.0
        )
    """,

    # ── Módulo de Proyectos ────────────────────────────────────────────────────
    # Tablas de solo lectura — se rellenan SOLO por snapshot (no datos sintéticos)

    "PROYECTOS": """
        CREATE TABLE IF NOT EXISTS PROYECTOS (
            CODIGO          TEXT    PRIMARY KEY,
            NOMBRE          TEXT,
            CLIENTE         TEXT,
            FECHAINICIO     TEXT,
            FECHAINICIOPREV TEXT,
            FECHAFIN        TEXT,
            TIPOOBRA        INTEGER DEFAULT 0,
            TIPORETENCION   INTEGER DEFAULT 0,
            PORCRETENCION   REAL    DEFAULT 0.0,
            ESGASTOSGENERALES TEXT  DEFAULT 'N'
        )
    """,

    "PROYVAR": """
        CREATE TABLE IF NOT EXISTS PROYVAR (
            CODPROYECTO     TEXT    NOT NULL,
            TIPOIDFISCAL    TEXT,
            TIPOPERSONA     TEXT,
            TIPORESIDENCIA  TEXT,
            RAZONSOCIAL     TEXT,
            PRIMARY KEY (CODPROYECTO)
        )
    """,

    "PRESUPROYE": """
        CREATE TABLE IF NOT EXISTS PRESUPROYE (
            CODPROYECTO         TEXT    NOT NULL,
            CODPRESUPUESTO      INTEGER NOT NULL,
            CODPROYSUBCONTRATA  TEXT,
            PRIMARY KEY (CODPROYECTO, CODPRESUPUESTO)
        )
    """,

    # ── Relación documento→documento destino (presupuesto→factura/pedido) ─────
    # Solo lectura — se rellena por snapshot. Necesaria para queries de conversión.

    "DOCDESTINO": """
        CREATE TABLE IF NOT EXISTS DOCDESTINO (
            CODDOCUMENTO        INTEGER NOT NULL,
            CODDOCUMENTODESTINO INTEGER NOT NULL,
            ORDENENVIO          INTEGER DEFAULT 0,
            ORDENRECEPCION      INTEGER DEFAULT 0,
            PRIMARY KEY (CODDOCUMENTO, CODDOCUMENTODESTINO)
        )
    """,

    # ── Tablas auxiliares de referencia ────────────────────────────────────────
    # Esquemas mínimos de fallback — _sync_schema_from_firebird los amplía con
    # las columnas reales de Firebird durante build-snapshot.
    # Vacías en modo sintético; rellenas tras snapshot real.

    "AGENTES": """
        CREATE TABLE IF NOT EXISTS AGENTES (
            CODIGO      INTEGER PRIMARY KEY,
            NOMBRE      TEXT    NOT NULL,
            NIF         TEXT,
            TELEFONO    TEXT,
            EMAIL       TEXT,
            COMISION    REAL    DEFAULT 0.0
        )
    """,

    "TIPOSIVA": """
        CREATE TABLE IF NOT EXISTS TIPOSIVA (
            CODIGO      INTEGER PRIMARY KEY,
            NOMBRE      TEXT    NOT NULL,
            PORCENTAJE  REAL    DEFAULT 21.0,
            PORCENTAJE2 REAL    DEFAULT 0.0
        )
    """,

    "TARIFAS": """
        CREATE TABLE IF NOT EXISTS TARIFAS (
            CODIGO      INTEGER PRIMARY KEY,
            NOMBRE      TEXT    NOT NULL,
            DESCRIPCION TEXT,
            PORCENTAJE  REAL    DEFAULT 0.0
        )
    """,

    "FORMASPAGO": """
        CREATE TABLE IF NOT EXISTS FORMASPAGO (
            CODIGO      TEXT    PRIMARY KEY,
            NOMBRE      TEXT    NOT NULL,
            DIASVENC    INTEGER DEFAULT 0,
            TIPOCOBRO   INTEGER DEFAULT 0
        )
    """,

    "SERIES": """
        CREATE TABLE IF NOT EXISTS SERIES (
            CODIGO      TEXT    PRIMARY KEY,
            NOMBRE      TEXT    NOT NULL,
            TIPO        INTEGER DEFAULT 0
        )
    """,

    "AVISOS": """
        CREATE TABLE IF NOT EXISTS AVISOS (
            CODIGO      INTEGER PRIMARY KEY,
            FECHA       TEXT,
            DESCRIPCION TEXT,
            ESTADO      INTEGER DEFAULT 0,
            CODCLIENTE  INTEGER DEFAULT 0,
            CODAGENTE   INTEGER DEFAULT 0
        )
    """,
}

# Orden de creación (respeta dependencias FK para snapshots)
TABLE_CREATION_ORDER: List[str] = [
    # Maestros (sin dependencias)
    "FAMILIA",
    "ALMACEN",
    "AGENTES",
    "TIPOSIVA",
    "TARIFAS",
    "FORMASPAGO",
    "SERIES",
    "RECURSO",
    "PROVEED",
    "ARTICULO",
    "CLIENTE",
    # Proyectos
    "PROYECTOS",
    "PROYVAR",
    "PRESUPROYE",
    # Documentos (dependen de maestros)
    "DOCCAB",
    "DOCDESTINO",
    "DOCLIN",
    # Movimientos
    "CAJA",
    "ESTALMACEN",
    # Avisos
    "AVISOS",
]

# ─── Índices para mejorar rendimiento de queries frecuentes ──────────────────

TABLE_INDEXES: Dict[str, List[str]] = {
    "DOCCAB": [
        "CREATE INDEX IF NOT EXISTS idx_doccab_tipo     ON DOCCAB (TIPO)",
        "CREATE INDEX IF NOT EXISTS idx_doccab_fecha    ON DOCCAB (FECHA)",
        "CREATE INDEX IF NOT EXISTS idx_doccab_cliente  ON DOCCAB (CODCLIENTE)",
        "CREATE INDEX IF NOT EXISTS idx_doccab_proyecto ON DOCCAB (CODPROYECTO)",
    ],
    "PROYECTOS": [
        "CREATE INDEX IF NOT EXISTS idx_proyectos_codigo ON PROYECTOS (CODIGO)",
    ],
    "PRESUPROYE": [
        "CREATE INDEX IF NOT EXISTS idx_presuproye_proy  ON PRESUPROYE (CODPROYECTO)",
        "CREATE INDEX IF NOT EXISTS idx_presuproye_presu ON PRESUPROYE (CODPRESUPUESTO)",
    ],
    "DOCDESTINO": [
        "CREATE INDEX IF NOT EXISTS idx_docdestino_src  ON DOCDESTINO (CODDOCUMENTO)",
        "CREATE INDEX IF NOT EXISTS idx_docdestino_dst  ON DOCDESTINO (CODDOCUMENTODESTINO)",
    ],
    "DOCLIN": [
        "CREATE INDEX IF NOT EXISTS idx_doclin_coddoc ON DOCLIN (CODDOCUMENTO)",
        "CREATE INDEX IF NOT EXISTS idx_doclin_art    ON DOCLIN (CODARTICULO)",
    ],
    "ARTICULO": [
        "CREATE INDEX IF NOT EXISTS idx_art_familia ON ARTICULO (CODFAMILIA)",
        "CREATE INDEX IF NOT EXISTS idx_art_ref     ON ARTICULO (REFERENCIA)",
    ],
    "ESTALMACEN": [
        "CREATE INDEX IF NOT EXISTS idx_est_fecha ON ESTALMACEN (FECHA)",
    ],
    "CAJA": [
        "CREATE INDEX IF NOT EXISTS idx_caja_fecha ON CAJA (FECHA)",
    ],
}

# ─── Mapeo columnas por tabla (para system queries RDB$) ─────────────────────
# Columnas verificadas contra BD real Firebird (simulator.db snapshot)

TABLE_COLUMNS: Dict[str, List[str]] = {
    "FAMILIA":    ["CODIGO", "NOMBRE", "DESCRIPCION"],
    "ALMACEN":    ["CODIGO", "NOMBRE", "DIRECCION"],
    "RECURSO":    ["CODIGO", "DESCRIPCION", "CODPADRE", "ORDEN", "NIF", "NSS", "TELEFONO", "EMAIL"],
    "PROVEED":    ["CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "TEL", "CP", "NIF",
                   "CODFORMAPAGO", "CODAGENTE", "BAJA"],
    "ARTICULO":   ["CODIGO", "CODFAMILIA", "NOMBRE", "DESCRIPCION", "DESCRIPCIONCORTA",
                   "REFERENCIA", "PRECIOCOSTE", "PRECIOVENTA", "TIPOIVA", "CONTROLSTOCK",
                   "BAJA", "UNIDAD", "STOCKARTICULO", "PROVEEDDEFECTO"],
    "PROYECTOS":  ["CODIGO", "NOMBRE", "CLIENTE", "FECHAINICIO", "FECHAINICIOPREV",
                   "FECHAFIN", "TIPOOBRA", "TIPORETENCION", "PORCRETENCION", "ESGASTOSGENERALES"],
    "PROYVAR":    ["CODPROYECTO", "TIPOIDFISCAL", "TIPOPERSONA", "TIPORESIDENCIA", "RAZONSOCIAL"],
    "PRESUPROYE": ["CODPROYECTO", "CODPRESUPUESTO", "CODPROYSUBCONTRATA"],
    "CLIENTE":    ["CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "TEL", "CP", "NIF",
                   "CODFORMAPAGO", "CODAGENTE", "BAJA"],
    "DOCCAB":     ["CODIGO", "TIPO", "SERIE", "NUMERO", "FECHA", "CODCLIENTE", "CODAGENTE",
                   "CODALMACEN", "CODFORMAPAGO", "DESCRIPCION", "OBSERVACIONES",
                   "IMPORTEBASE", "IMPORTEIVA", "IMPORTETOTAL", "ESTADO",
                   "ESTADOPEND", "ESTADOPENDVENCOM", "CODPROYECTO"],
    "DOCDESTINO": ["CODDOCUMENTO", "CODDOCUMENTODESTINO", "ORDENENVIO", "ORDENRECEPCION"],
    "DOCLIN":     ["CODDOCUMENTO", "CODIGO", "CODARTICULO", "DESCRIPCION",
                   "CANTIDAD", "PRECIO", "COSTE", "DESCUENTOS"],
    "CAJA":       ["FECHA", "CODAPUNTE", "TIPO", "IMPORTE", "CONCEPTO", "CODCLIENTE", "CODUSUARIO"],
    "ESTALMACEN": ["CODIGO", "FECHA", "IMPCOSTE", "IMPVENTA"],
    # Auxiliares
    "AGENTES":    ["CODIGO", "NOMBRE", "NIF", "TELEFONO", "EMAIL", "COMISION"],
    "TIPOSIVA":   ["CODIGO", "NOMBRE", "PORCENTAJE", "PORCENTAJE2"],
    "TARIFAS":    ["CODIGO", "NOMBRE", "DESCRIPCION", "PORCENTAJE"],
    "FORMASPAGO": ["CODIGO", "NOMBRE", "DIASVENC", "TIPOCOBRO"],
    "SERIES":     ["CODIGO", "NOMBRE", "TIPO"],
    "AVISOS":     ["CODIGO", "FECHA", "DESCRIPCION", "ESTADO", "CODCLIENTE", "CODAGENTE"],
}
