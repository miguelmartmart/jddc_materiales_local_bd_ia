"""
Constantes del sistema DEVIA - Versión Expandida
Centraliza TODOS los valores constantes del sistema
"""

from enum import Enum

# ============================================================================
# CONSTANTES GENERALES DE APLICACIÓN
# ============================================================================

class AppConstants:
    """General application constants."""
    APP_NAME = "DEVIA"
    VERSION = "3.0.0"
    API_PREFIX = "/api"
    DEFAULT_PORT = 8001
    DEFAULT_HOST = "0.0.0.0"


# ============================================================================
# CONSTANTES DE IA
# ============================================================================

class AIConstants(Enum):
    """AI related constants."""
    # Proveedores
    PROVIDER_GEMINI = "gemini"
    PROVIDER_GROQ = "groq"
    PROVIDER_OPENAI = "openai"
    PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"
    PROVIDER_OPENROUTER = "openrouter"
    
    # Tareas
    TASK_ANALYSIS = "analisis_completo"
    TASK_CHAT = "chat"


class AILimits:
    """Límites y timeouts para IA"""
    MAX_PROMPT_TOKENS = 4000
    MAX_RESPONSE_TOKENS = 2000
    API_TIMEOUT = 60  # segundos
    MAX_API_RETRIES = 2


# ============================================================================
# CONSTANTES DE BASE DE DATOS
# ============================================================================

class DBConstants(Enum):
    """Database related constants."""
    TYPE_FIREBIRD = "firebird"
    TYPE_POSTGRES = "postgres"
    TYPE_MYSQL = "mysql"


class DBDefaults:
    """Valores por defecto para conexiones de BD"""
    HOST = "localhost"
    PORT_FIREBIRD = 3050
    PORT_POSTGRESQL = 5432
    PORT_MYSQL = 3306
    USER = "SYSDBA"
    PASSWORD = "masterkey"
    CHARSET = "latin1"
    
    # Límites de consultas
    QUERY_LIMIT = 100
    MAX_QUERY_LIMIT = 1000
    QUERY_TIMEOUT = 30  # segundos
    
    # Reintentos de conexión
    MAX_CONNECTION_RETRIES = 3
    RETRY_WAIT_BASE = 0.5  # segundos
    
    # Reintentos de consultas SQL (auto-corrección)
    MAX_SQL_CORRECTION_RETRIES = 2  # Intentos de corrección con IA
    MAX_SQL_EXECUTION_RETRIES = 3  # Intentos de ejecución por consulta


# ============================================================================
# CONSTANTES DE METADATOS
# ============================================================================

class MetadataFiles:
    """Nombres de archivos de metadatos"""
    FULL = "db_metadata_full.json"
    OPTIMIZED = "db_metadata_optimized.json"


class MetadataLimits:
    """Límites para esquemas de metadatos"""
    MAX_TABLES_IN_SCHEMA = 10
    MAX_COLUMNS_PER_TABLE = 15


class TableCategories:
    """Categorías de tablas"""
    PRODUCTOS = "productos"
    CLIENTES = "clientes"
    VENTAS = "ventas"
    PROVEEDORES = "proveedores"
    COMPRAS = "compras"
    INVENTARIO = "inventario"
    USUARIOS = "usuarios"
    CONFIGURACION = "configuracion"
    OTROS = "otros"


class CategoryKeywords:
    """Keywords para clasificación automática de tablas"""
    PRODUCTOS = ["ARTICULO", "PRODUCTO", "ITEM"]
    CLIENTES = ["CLIENTE", "CUSTOMER"]
    VENTAS = ["FACTURA", "INVOICE", "VENTA", "SALE"]
    PROVEEDORES = ["PROVEEDOR", "SUPPLIER"]
    COMPRAS = ["PEDIDO", "ORDER", "COMPRA"]
    INVENTARIO = ["STOCK", "INVENTARIO", "ALMACEN"]
    USUARIOS = ["USUARIO", "USER", "EMPLEADO"]
    CONFIGURACION = ["CONFIG", "PARAM", "SETTING"]


# ============================================================================
# CONSTANTES DE API
# ============================================================================

class APIEndpoints:
    """Rutas de endpoints de la API"""
    CHAT = "/chat"
    MODELS = "/models"
    PROMPTS = "/prompts"
    ARTICLES = "/articles"
    SEND_CHAT = "/chat/send"


class HTTPStatus:
    """Códigos de estado HTTP"""
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    NOT_FOUND = 404
    INTERNAL_ERROR = 500


class CORSConfig:
    """Configuración de CORS"""
    ALLOWED_ORIGINS = ["http://localhost:8001", "http://127.0.0.1:8001"]


# ============================================================================
# CONSTANTES DE UI
# ============================================================================

class UIMessages:
    """Mensajes de la interfaz de usuario"""
    LOADING = "Cargando..."
    THINKING = "Pensando..."
    ERROR_CONNECTION = "Error de conexión"
    ERROR_GENERIC = "Ha ocurrido un error"
    SUCCESS = "Operación exitosa"
    SELECT_MODEL = "Por favor selecciona un modelo IA"


class ChatRoles:
    """Roles en el chat"""
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class UIColors:
    """Colores para la interfaz"""
    USER_BG = "#e3f2fd"
    AI_BG = "#f5f5f5"
    ERROR_BG = "#ffebee"


class UILimits:
    """Límites de la interfaz"""
    MAX_MESSAGE_LENGTH = 2000
    CHAT_HISTORY_LIMIT = 50


# ============================================================================
# CONSTANTES DE LOGGING
# ============================================================================

class LogLevels:
    """Niveles de logging"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormats:
    """Formatos de logging"""
    STANDARD = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LogPrefixes:
    """Prefijos para logs estructurados"""
    CHAT_SERVICE = "[CHAT SERVICE]"
    DATABASE = "[DATABASE]"
    AI_PROVIDER = "[AI PROVIDER]"
    SQL = "[SQL]"
    MODELO = "[MODELO]"
    EMISOR = "[EMISOR]"
    MENSAJE = "[MENSAJE]"
    CONTEXTO = "[CONTEXTO]"
    ERROR_SQL = "[ERROR SQL]"
    RESPUESTA_FINAL = "[RESPUESTA FINAL]"


class LogEmojis:
    """Emojis para logs"""
    NEW_MESSAGE = "📨"
    SEND = "📤"
    RECEIVE = "📥"
    SUCCESS = "✓"
    ERROR = "❌"
    WARNING = "⚠️"
    SEARCH = "🔍"
    EXECUTE = "🔄"


# ============================================================================
# CONSTANTES DE SQL
# ============================================================================

class SQLDelimiters:
    """Delimitadores de SQL en respuestas de IA"""
    START = "```sql"
    END = "```"


class SQLKeywords:
    """Palabras clave SQL"""
    SELECT = "SELECT"
    FIRST = "FIRST"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    FROM = "FROM"
    WHERE = "WHERE"
    ORDER_BY = "ORDER BY"


class SQLLimits:
    """Límites para consultas SQL"""
    DEFAULT_FIRST = 100
    MAX_RESULTS = 1000


class SQLDangerousCommands:
    """Comandos SQL peligrosos (no permitidos)"""
    COMMANDS = ["DROP", "TRUNCATE", "ALTER", "CREATE", "EXECUTE"]


# ============================================================================
# CONSTANTES DE ARCHIVOS
# ============================================================================

class FileExtensions:
    """Extensiones de archivos"""
    JSON = ".json"
    PYTHON = ".py"
    MARKDOWN = ".md"


class ConfigFiles:
    """Nombres de archivos de configuración"""
    AI_MODELS = "ai_models_config.json"
    DATABASE_METADATA = "database_metadata.py"
    SETTINGS = "settings.py"


class FilePaths:
    """Rutas relativas de directorios"""
    CONFIG = "backend/core/config"
    SCRIPTS = "backend/scripts"
    DRIVERS = "backend/drivers"
    FRONTEND = "frontend"
    ASSETS = "frontend/assets"


class FileLimits:
    """Límites de archivos"""
    MAX_SIZE_MB = 10
    MAX_LINE_LENGTH = 500


# ============================================================================
# CONSTANTES DE ENCODING
# ============================================================================

class EncodingFormats:
    """Formatos de encoding"""
    UTF8 = "utf-8"
    LATIN1 = "latin1"
    CP1252 = "cp1252"
    ISO_8859_15 = "iso-8859-15"
    WIN1252 = "WIN1252"


# ============================================================================
# CONSTANTES DE CACHÉ
# ============================================================================

class CacheTTL:
    """Tiempos de expiración de caché (segundos)"""
    METADATA = 3600  # 1 hora
    MODELS = 300  # 5 minutos
    QUERY_RESULTS = 60  # 1 minuto


class CacheLimits:
    """Límites de caché"""
    MAX_SIZE_MB = 100
    MAX_CACHED_QUERIES = 50
