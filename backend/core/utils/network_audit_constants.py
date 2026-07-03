"""
network_audit_constants.py — Constantes del auditor de red DEVIA.

PRINCIPIO: Ninguna IP, hostname ni puerto hardcodeado en el código.
Todos los valores configurables están aquí o en settings.py / .env.

RESILIENCIA:
  - Las IPs LAN se detectan automáticamente por rango RFC 1918 (no por IP fija)
  - Los hostnames LAN se detectan por sufijo .local (mDNS) o por lista configurable
  - Si cambia la IP del servidor Qwen3, no hay que tocar ningún fichero de código
  - Solo hay que actualizar JDDCIA_BASE_URL_FALLBACK en el .env

SEGURIDAD:
  - KNOWN_INTERNET_AI_HOSTS: lista de hosts de proveedores IA externos
    Usada en tests para verificar que ninguno es contactado
  - SENSITIVE_COLUMNS: columnas que nunca deben aparecer en contextos enviados a IA
    (centralizado aquí para que network_audit y db_explorer.constants estén sincronizados)
"""

from pathlib import Path


# ─── Rutas de log ─────────────────────────────────────────────────────────────

class NetworkAuditPaths:
    """
    Rutas de ficheros del auditor de red.
    Relativas a la raíz del proyecto (bots/interjddcia/).
    """
    # Directorio de logs (relativo a la raíz del módulo)
    LOG_DIR  = Path(__file__).parent.parent.parent.parent / "logs"
    LOG_FILE = LOG_DIR / "network_audit.log"


# ─── Rangos de red privada (RFC 1918) ─────────────────────────────────────────

class PrivateNetworkRanges:
    """
    Rangos de red privada según RFC 1918 + loopback + link-local.
    Cualquier IP en estos rangos se considera LAN (no internet).

    RESILIENCIA: No depende de IPs concretas — funciona aunque cambie la IP
    del servidor Qwen3, del PC, o de cualquier equipo de la red.
    """
    CIDR_BLOCKS = [
        "10.0.0.0/8",       # Clase A privada
        "172.16.0.0/12",    # Clase B privada (172.16.x.x — 172.31.x.x)
        "192.168.0.0/16",   # Clase C privada (toda la red 192.168.x.x)
        "127.0.0.0/8",      # Loopback IPv4
        "::1/128",          # Loopback IPv6
        "169.254.0.0/16",   # Link-local (APIPA)
        "fc00::/7",         # IPv6 ULA (Unique Local Address)
    ]


# ─── Hostnames LAN conocidos ──────────────────────────────────────────────────

class LanHostnames:
    """
    Hostnames que se consideran LAN aunque no sean IPs privadas.

    RESILIENCIA: Se detectan por sufijo (.local = mDNS) o por lista explícita.
    Añadir nuevos hostnames LAN aquí sin tocar el código.
    """
    # Sufijos que indican red local (mDNS / Bonjour / Avahi)
    LOCAL_SUFFIXES = {".local", ".lan", ".home", ".internal"}

    # Hostnames explícitos de la red JDDC
    # NOTA: No incluir IPs aquí — las IPs se detectan por rango RFC 1918
    EXPLICIT_HOSTS = {
        "localhost",
        "jddcia.local",    # Gateway Qwen3 (mDNS)
        "devia.local",     # Servidor DEVIA (mDNS)
    }


# ─── IDs de modelos IA locales (red LAN JDDC) ────────────────────────────────

class LocalModelIds:
    """
    IDs de los modelos IA que corren en la red LAN de JDDC (sin internet).

    FUENTE ÚNICA DE VERDAD: Este es el único lugar donde se definen estos IDs.
    Importar desde aquí en:
      - backend/modules/chat/model_fallback_orchestrator.py
      - tests/unit/test_lan_only_security.py
      - tests/privacy/test_privacidad_datos.py
      - cualquier otro módulo que necesite distinguir LAN vs internet

    MANTENIMIENTO: Si se añade un nuevo modelo LAN, añadirlo aquí.
    El orchestrator y todos los tests lo recogerán automáticamente.
    """
    # Modelo Qwen3 VL 30B accedido por mDNS (jddcia.local)
    QWEN3_MDNS    = "jddcia-qwen3-30b"
    # Modelo Qwen3 VL 30B accedido por IP directa (192.168.0.36)
    QWEN3_IP      = "jddcia-qwen3-30b-ip"
    # Modelo Qwen3 VL 8B en LM Studio, accedido por mDNS (jddcia.local:1234)
    QWEN3_8B_MDNS = "jddcia-qwen3-8b"
    # Modelo Qwen3 VL 8B en LM Studio, accedido por IP directa (172.19.64.1:1234)
    QWEN3_8B_IP   = "jddcia-qwen3-8b-ip"

    # Set completo para búsquedas O(1)
    ALL: frozenset = frozenset({QWEN3_MDNS, QWEN3_IP, QWEN3_8B_MDNS, QWEN3_8B_IP})


# ─── IDs de modelos IA externos (internet) ───────────────────────────────────

class KnownInternetModelIds:
    """
    IDs de modelos IA externos conocidos (proveedores de internet).
    Usados en tests para verificar que NINGUNO es llamado cuando
    ai_local_only=true está activo.

    MANTENIMIENTO: Añadir nuevos IDs cuando se integren nuevos proveedores.
    """
    IDS: frozenset = frozenset({
        # Groq
        "groq-llama3", "groq-llama-70b",
        "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
        "gemma-3-4b", "gemma-3-1b",
        # Google / Gemini
        "gemini-flash", "gemini-pro", "gemini-1.5-flash",
        # OpenAI
        "gpt-4o", "gpt-4o-mini", "openai-gpt4o",
        # Anthropic
        "claude-3-haiku", "claude-3-5-sonnet",
        # DeepSeek
        "deepseek-v3",
        # Mistral
        "mistral-large",
        # Cohere
        "cohere-command-r",
        # Together / Fireworks
        "together-llama", "fireworks-llama",
    })


# ─── Hosts de proveedores IA externos (internet) ─────────────────────────────

class KnownInternetAIHosts:
    """
    Lista de hosts de proveedores IA externos conocidos.
    Usada en tests para verificar que NINGUNO es contactado cuando
    ai_local_only=true está activo.

    MANTENIMIENTO: Añadir nuevos proveedores aquí cuando se integren.
    """
    HOSTS = frozenset({
        # Groq
        "api.groq.com",
        # OpenAI
        "api.openai.com",
        # Google / Gemini
        "generativelanguage.googleapis.com",
        "aiplatform.googleapis.com",
        # Anthropic
        "api.anthropic.com",
        # Mistral
        "api.mistral.ai",
        # OpenRouter (agregador)
        "openrouter.ai",
        # Together AI
        "api.together.xyz",
        "api.together.ai",
        # DeepSeek
        "api.deepseek.com",
        # Alibaba / DashScope
        "dashscope.aliyuncs.com",
        # Cohere
        "api.cohere.ai",
        "api.cohere.com",
        # HuggingFace
        "api-inference.huggingface.co",
        "huggingface.co",
        # AI21
        "api.ai21.com",
        # Reka
        "api.reka.ai",
        # Yi (01.ai)
        "api.lingyiwanwu.com",
        # Fireworks
        "api.fireworks.ai",
        # Kimi (Moonshot)
        "api.moonshot.cn",
        # ZhipuAI (GLM)
        "open.bigmodel.cn",
        # Snowflake Cortex
        "cortex.snowflakecomputing.com",
        # Perplexity
        "api.perplexity.ai",
        # Replicate
        "api.replicate.com",
        # AWS Bedrock
        "bedrock-runtime.amazonaws.com",
        # Azure OpenAI
        "openai.azure.com",
    })


# ─── Configuración del auditor ────────────────────────────────────────────────

class NetworkAuditConfig:
    """
    Configuración de comportamiento del NetworkAuditLogger.
    Cambiar aquí afecta a todo el sistema de auditoría.
    """
    # Nivel de log para llamadas LAN (INFO) vs internet (WARNING)
    LOG_LEVEL_LAN      = "INFO"
    LOG_LEVEL_INTERNET = "WARNING"
    LOG_LEVEL_CRITICAL = "CRITICAL"

    # Formato del log de auditoría
    LOG_FORMAT_FILE    = "%(asctime)s [%(levelname)s] %(message)s"
    LOG_FORMAT_CONSOLE = "\033[93m[NET-AUDIT]\033[0m %(message)s"
    LOG_DATE_FORMAT    = "%Y-%m-%d %H:%M:%S"

    # Nombre del logger de auditoría
    LOGGER_NAME = "NETWORK_AUDIT"

    # Máximo de entradas en el log antes de rotar (0 = sin límite)
    MAX_LOG_ENTRIES = 0

    # Modo por defecto al instalar globalmente
    DEFAULT_STRICT_MODE = False


# ─── Mensajes del auditor ─────────────────────────────────────────────────────

class NetworkAuditMessages:
    """
    Mensajes de log y error del auditor de red.
    Centralizado para facilitar internacionalización y consistencia.
    """
    PRIVACY_VIOLATION = (
        "VIOLACION DE PRIVACIDAD: Intento de conexion a INTERNET detectado!\n"
        "   URL: {url}\n"
        "   Host: {host}\n"
        "   Caller: {caller}\n"
        "   Timestamp: {timestamp}\n"
        "   NINGUN dato de la BD debe salir a internet."
    )
    AUDIT_STARTED     = "Auditoria iniciada (strict={strict})"
    AUDIT_STOPPED     = "Auditoria finalizada"
    GLOBAL_INSTALLED  = "Auditor global instalado (strict={strict}) — Log: {log_file}"
    GLOBAL_REMOVED    = "Auditor global desinstalado"
    ALREADY_INSTALLED = "Ya hay una instancia global instalada"
    PATCH_INSTALLED   = "Parche instalado en {target}"
    PATCH_FAILED      = "No se pudo parchear {target}: {error}"
    SUMMARY           = (
        "RESUMEN: {total} llamadas totales | "
        "{lan} LAN OK | "
        "{internet} INTERNET {internet_icon}"
    )
    INTERNET_HOSTS    = "Hosts de internet contactados: {hosts}"
    LAN_HOSTS         = "Hosts LAN contactados: {hosts}"

    # Aserciones
    ASSERT_INTERNET_CALLS = (
        "Se detectaron {count} llamadas a INTERNET:\n{details}\n"
        "NINGUN dato de la BD debe salir a internet."
    )
    ASSERT_NON_LAN_CALLS  = (
        "Se detectaron {count} llamadas fuera de la LAN:\n{details}"
    )
    ASSERT_FORBIDDEN_HOST = (
        "Se detectaron llamadas a hosts no permitidos:\n{details}\n"
        "Hosts permitidos: {allowed}"
    )
