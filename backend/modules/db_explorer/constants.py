"""
Constantes del módulo db_explorer / metadata_builder.

PRINCIPIO: Ningún valor literal de IP, puerto, credencial o modelo aquí.
Todos los valores configurables vienen de settings.py (que lee el .env).
Este archivo solo contiene constantes de comportamiento, categorías, límites y mensajes.

SEGURIDAD: Este módulo SOLO envía datos a la IA local LAN (settings.JDDCIA_BASE_URL*).
NUNCA se envían datos de la BD a internet.
"""

# ─── Timeouts de la IA local ──────────────────────────────────────────────────

class LocalAITimeouts:
    """
    Timeouts para llamadas a la IA local.
    Valores en segundos. Cambiar aquí afecta a todo el módulo.
    La IP/URL/auth viene de settings.JDDCIA_BASE_URL / JDDCIA_API_KEY.
    """
    CONNECT = 3.0    # Falla rápido si el host no existe o está apagado
    READ    = 90.0   # Análisis de tabla puede tardar (inferencia Qwen3 30B)


class LocalAIParams:
    """
    Parámetros de generación para la IA local.
    El modelo y las URLs vienen de settings.py / .env.
    """
    MAX_TOKENS  = 2048
    TEMPERATURE = 0.1   # Baja temperatura = respuestas más deterministas y estructuradas
    MODEL_KEY   = "JDDCIA_MODEL"  # Clave en .env (si se añade en el futuro)
    MODEL_DEFAULT = "unified-main"  # Valor por defecto si no está en .env


# ─── Privacidad / Seguridad ───────────────────────────────────────────────────

class PrivacyConfig:
    """
    Columnas que contienen datos sensibles.
    Se excluyen de la muestra enviada a la IA para proteger la privacidad.
    Añadir aquí nuevas columnas sensibles sin tocar el código.
    """
    SENSITIVE_COLUMNS = frozenset({
        "NIF", "CIF", "DNI", "IBAN", "BIC",
        "EMAIL", "TELEFONO", "TEL", "MOVIL",
        "PASSWORD", "PASS", "CLAVE", "TOKEN", "SECRET",
        "FIRMA", "FIRMATRAZOS",
        "DATOSPASARELA", "DATOSPASARELADESTINO",
        "EFACTURACONTENIDO", "EFACTURAREGISTRO",
        "OBSERVACIONES", "OBSERVACIONESWEB",
        "DIRECCION", "DOMICILIO",
    })
    MAX_SAMPLE_ROWS = 3   # Filas de muestra enviadas a la IA (sin datos sensibles)
    MAX_SAMPLE_COLS = 10  # Columnas de muestra (las primeras no sensibles)


# ─── Límites de procesamiento ─────────────────────────────────────────────────

class ProcessingLimits:
    """
    Límites para el procesamiento de tablas y generación de metadatos.
    Ajustar aquí si el contexto de la IA cambia o hay problemas de rendimiento.
    """
    MAX_COLUMNS_IN_PROMPT  = 40   # Máx columnas enviadas al prompt de la IA
    MAX_DESCRIPTION_CHARS  = 200  # Máx chars en descripción de tabla
    MAX_COLUMN_DESC_CHARS  = 80   # Máx chars en descripción de columna
    MAX_QUERIES_PER_TABLE  = 4    # Máx consultas de ejemplo por tabla


# ─── Categorías de tablas ─────────────────────────────────────────────────────

class TableCategory:
    """
    Categorías válidas para clasificar tablas en los metadatos.
    La IA usa estas categorías para clasificar automáticamente cada tabla.
    Añadir nuevas categorías aquí y en el prompt del sistema.
    """
    PRODUCTOS     = "productos"
    VENTAS        = "ventas"
    COMPRAS       = "compras"
    CLIENTES      = "clientes"
    PROVEEDORES   = "proveedores"
    INVENTARIO    = "inventario"
    FINANZAS      = "finanzas"
    DOCUMENTOS    = "documentos"
    EMPLEADOS     = "empleados"
    CONFIGURACION = "configuracion"
    OTROS         = "otros"

    ALL = [
        PRODUCTOS, VENTAS, COMPRAS, CLIENTES, PROVEEDORES,
        INVENTARIO, FINANZAS, DOCUMENTOS, EMPLEADOS, CONFIGURACION, OTROS
    ]


# ─── Tipos de campo Firebird ──────────────────────────────────────────────────

class FirebirdFieldTypes:
    """
    Mapeo de códigos numéricos de tipo Firebird a nombres legibles.
    Referencia: Firebird 2.5 RDB$FIELD_TYPE values.
    """
    TYPE_MAP = {
        7:   "SMALLINT",
        8:   "INTEGER",
        10:  "FLOAT",
        12:  "DATE",
        13:  "TIME",
        14:  "CHAR",
        16:  "BIGINT",
        27:  "DOUBLE",
        35:  "TIMESTAMP",
        37:  "VARCHAR",
        261: "BLOB",
    }
    BLOB_TYPE              = "BLOB"
    DECIMAL_SCALE_THRESHOLD = 0  # Si RDB$FIELD_SCALE < 0, el tipo es DECIMAL


# ─── Logging / Trazas ─────────────────────────────────────────────────────────

class MetadataBuilderLog:
    """
    Prefijos de log para trazabilidad completa del flujo.
    Formato: [METADATA_BUILDER][PASO] EMISOR → RECEPTOR: mensaje
    """
    MODULE     = "[METADATA_BUILDER]"
    CHECK_AI   = "[METADATA_BUILDER][CHECK_AI]"
    GET_TABLES = "[METADATA_BUILDER][GET_TABLES]"
    GET_STRUCT = "[METADATA_BUILDER][GET_STRUCTURE]"
    ANALYZE_AI = "[METADATA_BUILDER][ANALYZE_AI]"
    SAVE       = "[METADATA_BUILDER][SAVE]"
    DELETE     = "[METADATA_BUILDER][DELETE]"
    BATCH      = "[METADATA_BUILDER][BATCH]"


# ─── Mensajes de estado ───────────────────────────────────────────────────────

class MetadataBuilderMessages:
    """
    Mensajes de estado para la UI y logs.
    Usar .format(**kwargs) para sustituir variables.
    """
    AI_NOT_AVAILABLE  = (
        "IA local no disponible en {url}. "
        "Los datos de la BD NO se enviarán a internet. "
        "Enciende el servidor IA local para usar este módulo."
    )
    TABLE_NOT_FOUND    = "Tabla '{table}' no encontrada en la base de datos."
    METADATA_SAVED     = "Metadatos de '{table}' guardados correctamente."
    METADATA_DELETED   = "Metadatos de '{table}' eliminados."
    METADATA_NOT_FOUND = "La tabla '{table}' no tiene metadatos registrados."
    INVALID_JSON       = "La IA no devolvió JSON válido. Respuesta: {raw}"
    BATCH_COMPLETE     = "Análisis por lotes completado: {ok} OK, {fail} errores."
    SECURITY_BLOCK     = (
        "BLOQUEO DE SEGURIDAD: La IA local no está disponible. "
        "Este módulo no envía datos a internet bajo ninguna circunstancia."
    )
