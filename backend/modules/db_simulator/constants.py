"""
constants.py — Fuente única de verdad del módulo db_simulator.

Centraliza TODOS los parámetros, rutas, nombres y flags del módulo.
Ningún otro fichero del módulo debe hardcodear valores aquí definidos.

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

from pathlib import Path

# ─── Rutas del módulo ─────────────────────────────────────────────────────────

class SimulatorPaths:
    """Rutas absolutas usadas por el módulo."""
    MODULE_DIR   = Path(__file__).parent
    DATA_DIR     = MODULE_DIR / "data"
    DB_PATH      = DATA_DIR / "simulator.db"
    STATUS_PATH  = DATA_DIR / "status.json"
    CONFIG_PATH  = MODULE_DIR / "config.json"  # Parámetro servidor: simulator_enabled


# ─── Modos de operación ───────────────────────────────────────────────────────

class SimulatorMode:
    """Modo en que se construyó la BD simulada."""
    SNAPSHOT  = "snapshot"   # Datos reales del último mes capturados de Firebird
    SYNTHETIC = "synthetic"  # Datos generados automáticamente (sin BD real)
    EMPTY     = "empty"      # BD vacía (recién inicializada)


# ─── Estados internos ─────────────────────────────────────────────────────────

class SimulatorStatus:
    NOT_INITIALIZED = "not_initialized"  # Nunca construida
    READY           = "ready"            # Lista para usar
    BUILDING        = "building"         # En proceso de construcción
    ERROR           = "error"            # Error en la última construcción


# ─── Configuración de datos ───────────────────────────────────────────────────

class SimulatorConfig:
    """Parámetros de volumen y comportamiento."""
    # Snapshot de BD real
    SNAPSHOT_MONTHS_BACK   = 1     # Cuántos meses atrás capturar
    MAX_ROWS_PER_TABLE     = 500   # Límite de filas por tabla en snapshot
    MAX_DOCLIN_ROWS        = 2000  # Límite para tabla de líneas de documento

    # Datos sintéticos
    SYNTHETIC_FAMILIAS     = 15
    SYNTHETIC_ALMACENES    = 4
    SYNTHETIC_PROVEEDORES  = 15
    SYNTHETIC_RECURSOS     = 12    # Empleados
    SYNTHETIC_ARTICULOS    = 120
    SYNTHETIC_CLIENTES     = 60
    SYNTHETIC_DOCCAB       = 220   # Documentos (facturas, presupuestos, etc.)
    SYNTHETIC_CAJA         = 90
    SYNTHETIC_ESTALMACEN   = 180

    # Distribución de tipos de documento (porcentaje aprox)
    DOCCAB_PCT_FACTURA     = 0.38  # TIPO=13
    DOCCAB_PCT_PRESUPUESTO = 0.30  # TIPO=0
    DOCCAB_PCT_ALBARAN     = 0.14  # TIPO=11
    DOCCAB_PCT_SAT         = 0.10  # TIPO=2
    DOCCAB_PCT_PEDIDO      = 0.08  # TIPO=12

    # Datos económicos realistas para climatización
    IMPORTE_MIN            = 350.0
    IMPORTE_MAX            = 18000.0
    IVA_GENERAL            = 21.0


# ─── Nombres de tablas JDDC ───────────────────────────────────────────────────

class JDDCTableNames:
    """Nombres exactos de las tablas principales de la BD JDDC."""
    DOCCAB      = "DOCCAB"
    DOCLIN      = "DOCLIN"
    ARTICULO    = "ARTICULO"
    CLIENTE     = "CLIENTE"
    PROVEED     = "PROVEED"
    RECURSO     = "RECURSO"
    FAMILIA     = "FAMILIA"
    ALMACEN     = "ALMACEN"
    CAJA        = "CAJA"
    ESTALMACEN  = "ESTALMACEN"
    # Módulo de proyectos / obras
    PROYECTOS   = "PROYECTOS"
    PROYVAR     = "PROYVAR"
    PRESUPROYE  = "PRESUPROYE"
    # Relación documento→destino (presupuesto→factura/pedido)
    DOCDESTINO  = "DOCDESTINO"

    # Lista ordenada para snapshot (las de referencia primero)
    REFERENCE_TABLES = [FAMILIA, ALMACEN, RECURSO, PROVEED, ARTICULO, CLIENTE,
                        PROYECTOS, PROYVAR, PRESUPROYE]
    DATE_TABLES      = [DOCCAB, CAJA, ESTALMACEN]  # Tienen columna fecha
    LINKED_TABLES    = [DOCLIN, DOCDESTINO]  # Enlazadas vía FK (no filtradas por fecha directamente)
    ALL = REFERENCE_TABLES + DATE_TABLES + LINKED_TABLES


# ─── Tipos de documento DOCCAB ────────────────────────────────────────────────

class JDDCDocTipos:
    """Valores del campo TIPO en la tabla DOCCAB."""
    PRESUPUESTO   = 0
    SAT           = 2
    ABONO         = 3
    CONTRATO      = 10
    ALBARAN       = 11
    PEDIDO        = 12
    FACTURA       = 13
    CERTIFICACION = 51
    RECIBO        = 61

    LABELS = {
        0: "Presupuesto", 2: "SAT", 3: "Abono", 10: "Contrato",
        11: "Albarán", 12: "Pedido", 13: "Factura",
        51: "Certificación", 61: "Recibo",
    }


# ─── Columnas de fecha por tabla (para filtro de snapshot) ────────────────────

class JDDCDateColumns:
    """Columna de fecha principal de cada tabla con fecha."""
    MAP = {
        "DOCCAB":     "FECHA",
        "CAJA":       "FECHA",
        "ESTALMACEN": "FECHA",
    }


# ─── Endpoints de la API ──────────────────────────────────────────────────────

class SimulatorEndpoints:
    PREFIX          = "/db-simulator"
    STATUS          = "/status"
    BUILD_SNAPSHOT  = "/build-snapshot"
    BUILD_SYNTHETIC = "/build-synthetic"
    CLEAR           = "/clear"
    TABLES          = "/tables"
    PREVIEW         = "/preview/{table_name}"
    DEMO_SQL        = "/demo-sql"
    EXECUTE         = "/execute"
    CONFIG          = "/config"   # GET/POST para leer/escribir simulator_enabled


# ─── Disclaimer (aviso de simulación para el usuario) ─────────────────────────

class SimulatorDisclaimer:
    """Textos de aviso para que el usuario sepa que los datos son simulados."""

    # Prefijo plano para respuestas de voz / API
    TEXT_PREFIX = "[SIMULACIÓN - datos NO reales] "

    # Banner HTML para el chat web — se antepone a la respuesta de la IA
    HTML_BANNER = (
        '<div style="'
        "background:#fff3cd;border:1px solid #ffc107;"
        "border-radius:6px;padding:8px 12px;margin-bottom:10px;"
        'font-size:0.85em;color:#856404;">'
        "⚠️ <strong>MODO SIMULACIÓN</strong> — "
        "Los datos mostrados son <strong>simulados</strong> "
        "(no provienen de la base de datos real). "
        "Desactiva el simulador en <em>Configuración → BD Simulada</em> "
        "para consultar datos reales."
        "</div>"
    )

    # Versión corta para respuestas JSON estructuradas
    JSON_KEY    = "sim_disclaimer"
    JSON_TEXT   = (
        "⚠️ MODO SIMULACIÓN: datos NO reales. "
        "Desactiva el simulador para obtener información de la base de datos real."
    )


# ─── Logging ──────────────────────────────────────────────────────────────────

class SimulatorLog:
    PREFIX    = "[DB_SIMULATOR]"
    SNAPSHOT  = "[SNAPSHOT]"
    SYNTHETIC = "[SYNTHETIC]"
    DRIVER    = "[SIM_DRIVER]"
    QUERY     = "[SIM_QUERY]"
    TRANSLATE = "[TRANSLATE]"
