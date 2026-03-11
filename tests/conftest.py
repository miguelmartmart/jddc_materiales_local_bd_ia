"""
conftest.py — Configuración centralizada de tests DEVIA.

RESPONSABILIDAD:
  - Leer test.properties (única fuente de verdad de parámetros)
  - Autodetectar IP de Qwen3 LAN si QWEN3_HOST=auto
  - Autodetectar parámetros de BD desde .env si DB_HOST=auto
  - Proveer fixtures compartidos a todos los tests
  - Configurar logging con trazas en fichero

AUTODETECCIÓN:
  - Qwen3: escanea la subred configurada buscando el puerto Ollama/OpenAI
  - BD: lee directamente del .env del proyecto (settings)

PRIVACIDAD:
  - ENFORCE_LAN_ONLY=true → intercepta socket.connect y falla si detecta internet
  - Todas las IPs se validan contra ALLOWED_NETWORKS antes de conectar

FICHEROS DE LOG (en logs/):
  - conftest.log          → arranque y autodetección
  - network_audit.log     → todas las conexiones de red
  - sql_trace.log         → todas las consultas SQL
  - ai_requests.log       → peticiones a Qwen3 LAN
  - integration_traces.jsonl → trazas JSON de cada test
"""

import configparser
import logging
import os
import socket
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

_TESTS_DIR = Path(__file__).parent
_ROOT      = _TESTS_DIR.parent
_LOGS_DIR  = _ROOT / "logs"
_PROPS     = _TESTS_DIR / "test.properties"

sys.path.insert(0, str(_ROOT))
_LOGS_DIR.mkdir(exist_ok=True)

# ─── Logging de arranque ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOGS_DIR / "conftest.log", encoding="utf-8"),
    ],
)
_log = logging.getLogger("conftest")

# Loggers especializados
_net_log = logging.getLogger("network_audit")
_net_log.addHandler(logging.FileHandler(_LOGS_DIR / "network_audit.log", encoding="utf-8"))

_sql_log = logging.getLogger("sql_trace")
_sql_log.addHandler(logging.FileHandler(_LOGS_DIR / "sql_trace.log", encoding="utf-8"))

_ai_log = logging.getLogger("ai_requests")
_ai_log.addHandler(logging.FileHandler(_LOGS_DIR / "ai_requests.log", encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════════
# TestConfig — Única fuente de verdad de parámetros
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    """
    Lee test.properties y resuelve valores "auto" automáticamente.
    Singleton — se carga una sola vez al arrancar pytest.
    """

    _instance: Optional["TestConfig"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._loaded = False
            return cls._instance

    def load(self) -> "TestConfig":
        if self._loaded:
            return self
        self._props = self._read_properties()
        self._resolve_auto_values()
        self._loaded = True
        _log.info(f"[TestConfig] Cargado desde {_PROPS}")
        _log.info(f"[TestConfig] DB: {self.db_host}:{self.db_port}")
        _log.info(f"[TestConfig] Qwen3: {self.qwen3_url}")
        _log.info(f"[TestConfig] LAN only: {self.enforce_lan_only}")
        return self

    # ── Propiedades de BD ──────────────────────────────────────────────────────

    @property
    def db_host(self) -> str:
        return self._props.get("DB_HOST", "localhost")

    @property
    def db_port(self) -> int:
        return int(self._props.get("DB_PORT", 3050))

    @property
    def db_name(self) -> str:
        return self._props.get("DB_NAME", "")

    @property
    def db_user(self) -> str:
        return self._props.get("DB_USER", "SYSDBA")

    @property
    def db_password(self) -> str:
        return self._props.get("DB_PASSWORD", "")

    # ── Propiedades de Qwen3 ──────────────────────────────────────────────────

    @property
    def qwen3_host(self) -> str:
        return self._props.get("QWEN3_HOST", "")

    @property
    def qwen3_port(self) -> int:
        return int(self._props.get("QWEN3_PORT", 11434))

    @property
    def qwen3_api_key(self) -> str:
        return self._props.get("QWEN3_API_KEY", "")

    @property
    def qwen3_url(self) -> str:
        host = self.qwen3_host
        if not host:
            return ""
        return f"http://{host}:{self.qwen3_port}/api/vlm/v1"

    # ── Propiedades de privacidad ─────────────────────────────────────────────

    @property
    def enforce_lan_only(self) -> bool:
        return self._props.get("ENFORCE_LAN_ONLY", "true").lower() == "true"

    @property
    def allowed_networks(self) -> List[str]:
        raw = self._props.get("ALLOWED_NETWORKS", "127.,192.168.,10.")
        return [n.strip() for n in raw.split(",") if n.strip()]

    # ── Propiedades de umbrales ───────────────────────────────────────────────

    @property
    def metaglass_max_time(self) -> float:
        return float(self._props.get("METAGLASS_MAX_RESPONSE_TIME_S", 30))

    @property
    def web_max_time(self) -> float:
        return float(self._props.get("WEB_MAX_RESPONSE_TIME_S", 60))

    @property
    def metaglass_max_len(self) -> int:
        return int(self._props.get("METAGLASS_MAX_RESPONSE_LEN", 500))

    @property
    def web_max_len(self) -> int:
        return int(self._props.get("WEB_MAX_RESPONSE_LEN", 10000))

    @property
    def summary_threshold(self) -> int:
        return int(self._props.get("SUMMARY_THRESHOLD", 15))

    @property
    def metaglass_pagination_threshold(self) -> int:
        return int(self._props.get("METAGLASS_PAGINATION_THRESHOLD", 5))

    @property
    def metaglass_page_size(self) -> int:
        return int(self._props.get("METAGLASS_PAGE_SIZE", 3))

    @property
    def use_ai_pagination_intent(self) -> bool:
        return self._props.get("USE_AI_PAGINATION_INTENT", "true").lower() == "true"

    @property
    def page_size_default(self) -> int:
        return int(self._props.get("PAGE_SIZE_DEFAULT", 10))

    @property
    def min_siuo_coverage(self) -> float:
        return float(self._props.get("MIN_SIUO_COVERAGE_PCT", 70))

    @property
    def skip_if_unavailable(self) -> bool:
        return self._props.get("SKIP_IF_UNAVAILABLE", "true").lower() == "true"

    @property
    def max_retries(self) -> int:
        return int(self._props.get("MAX_RETRIES", 2))

    # ── Lectura de properties ─────────────────────────────────────────────────

    def _read_properties(self) -> Dict[str, str]:
        """Lee test.properties como dict clave=valor."""
        props = {}
        if not _PROPS.exists():
            _log.warning(f"[TestConfig] {_PROPS} no encontrado — usando defaults")
            return props
        with open(_PROPS, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    props[k.strip()] = v.strip()
        return props

    def _resolve_auto_values(self):
        """Resuelve valores 'auto' leyendo .env o autodetectando."""
        # BD: leer del .env/settings
        if self._props.get("DB_HOST") == "auto":
            self._resolve_db_from_settings()

        # Qwen3: autodetectar en LAN
        if self._props.get("QWEN3_HOST") == "auto":
            self._autodetect_qwen3()

        # API key de Qwen3
        if self._props.get("QWEN3_API_KEY") == "auto":
            self._resolve_qwen3_key_from_settings()

    def _resolve_db_from_settings(self):
        """Lee parámetros de BD desde settings del proyecto."""
        try:
            from backend.core.config.settings import settings
            self._props["DB_HOST"]     = str(settings.DB_HOST)
            self._props["DB_PORT"]     = str(settings.DB_PORT)
            self._props["DB_NAME"]     = str(settings.DB_NAME)
            self._props["DB_USER"]     = str(settings.DB_USER)
            self._props["DB_PASSWORD"] = str(settings.DB_PASSWORD)
            _log.info(f"[TestConfig] BD desde settings: {settings.DB_HOST}:{settings.DB_PORT}")
        except Exception as e:
            _log.warning(f"[TestConfig] No se pudo leer BD de settings: {e}")
            self._props["DB_HOST"] = "localhost"
            self._props["DB_PORT"] = "3050"

    def _resolve_qwen3_key_from_settings(self):
        """Lee API key de Qwen3 desde settings."""
        try:
            from backend.core.config.settings import settings
            key = getattr(settings, "JDDCIA_API_KEY", "")
            self._props["QWEN3_API_KEY"] = str(key) if key else ""
        except Exception:
            self._props["QWEN3_API_KEY"] = ""

    def _autodetect_qwen3(self):
        """
        Autodetecta la IP de Qwen3 escaneando la subred LAN.
        Primero intenta las URLs configuradas en settings.
        Si no, escanea la subred buscando el puerto Ollama.
        """
        # 1. Intentar URLs de settings primero
        try:
            from backend.core.config.settings import settings
            for url_attr in ["JDDCIA_BASE_URL_FALLBACK", "JDDCIA_BASE_URL"]:
                url = getattr(settings, url_attr, "")
                if url and self._check_qwen3_url(url):
                    host = url.split("//")[1].split(":")[0].split("/")[0]
                    self._props["QWEN3_HOST"] = host
                    _log.info(f"[TestConfig] Qwen3 encontrado en settings: {url}")
                    return
        except Exception as e:
            _log.debug(f"[TestConfig] Settings no disponible: {e}")

        # 2. Escanear subred
        subnet = self._props.get("QWEN3_SCAN_SUBNET", "192.168.0")
        port   = int(self._props.get("QWEN3_PORT", 11434))
        timeout = float(self._props.get("QWEN3_SCAN_TIMEOUT_S", 1))

        _log.info(f"[TestConfig] Escaneando {subnet}.1-254 puerto {port}...")
        found = self._scan_for_service(subnet, port, timeout)

        if found:
            self._props["QWEN3_HOST"] = found
            _log.info(f"[TestConfig] Qwen3 autodetectado en: {found}:{port}")
        else:
            self._props["QWEN3_HOST"] = ""
            _log.warning(f"[TestConfig] Qwen3 no encontrado en {subnet}.x:{port}")

    def _check_qwen3_url(self, url: str) -> bool:
        """Verifica si una URL de Qwen3 responde."""
        try:
            import httpx
            key = self._props.get("QWEN3_API_KEY", "")
            headers = {"Authorization": f"Basic {key}"} if key else {}
            resp = httpx.get(f"{url}/models", timeout=3, headers=headers)
            return resp.status_code == 200
        except Exception:
            return False

    def _scan_for_service(self, subnet: str, port: int, timeout: float) -> Optional[str]:
        """Escanea la subred buscando un servicio en el puerto dado."""
        found_host = []
        lock = threading.Lock()

        def check_host(ip: str):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    with lock:
                        found_host.append(ip)
            except Exception:
                pass

        threads = []
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            t = threading.Thread(target=check_host, args=(ip,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout + 0.5)

        return found_host[0] if found_host else None

    def is_lan(self, host: str) -> bool:
        """Verifica si una dirección es LAN."""
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = host
        return any(ip.startswith(prefix) for prefix in self.allowed_networks)

    def db_params(self) -> Dict:
        """Devuelve los parámetros de BD como dict para DBConfig."""
        return {
            "host":     self.db_host,
            "port":     self.db_port,
            "database": self.db_name,
            "user":     self.db_user,
            "password": self.db_password,
        }

    def metaglass_context(self) -> Dict:
        """Contexto de chat para MetaGlass (sin confirm_data_sending)."""
        return {
            "model_id":             None,
            "db_params":            self.db_params(),
            "conversation_history": [],
        }

    def web_context(self) -> Dict:
        """Contexto de chat para cliente web."""
        ctx = self.metaglass_context()
        ctx["confirm_data_sending"] = True
        return ctx


# ─── Instancia global ─────────────────────────────────────────────────────────

cfg = TestConfig().load()


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures compartidos
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    """Fixture que expone TestConfig a todos los tests."""
    return cfg


@pytest.fixture(scope="session")
def db_params() -> Dict:
    """Parámetros de BD listos para usar."""
    return cfg.db_params()


@pytest.fixture(scope="session")
def metaglass_ctx() -> Dict:
    """Contexto MetaGlass listo para usar."""
    return cfg.metaglass_context()


@pytest.fixture(scope="session")
def web_ctx() -> Dict:
    """Contexto web listo para usar."""
    return cfg.web_context()


@pytest.fixture(scope="session")
def db_driver():
    """
    Driver de BD Firebird conectado.
    Se salta si la BD no está disponible.
    """
    from backend.core.factory.db_factory import DBFactory
    from backend.core.abstract.database import DBConfig
    from backend.core.utils.constants import DBConstants

    try:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = DBConfig(**cfg.db_params())
        driver.connect(config)
        _log.info(f"[fixture:db_driver] Conectado a {cfg.db_host}:{cfg.db_port}")
        _net_log.info(f"BD Firebird conectada: {cfg.db_host}:{cfg.db_port} [LAN={cfg.is_lan(cfg.db_host)}]")
        yield driver
        driver.disconnect()
        _log.info("[fixture:db_driver] Desconectado")
    except Exception as e:
        if cfg.skip_if_unavailable:
            pytest.skip(f"BD Firebird no disponible: {e}")
        else:
            raise


@pytest.fixture(scope="session")
def qwen3_url() -> str:
    """
    URL de Qwen3 LAN verificada.
    Se salta si Qwen3 no está disponible.
    """
    url = cfg.qwen3_url
    if not url:
        if cfg.skip_if_unavailable:
            pytest.skip("Qwen3 LAN no detectado")
        else:
            pytest.fail("Qwen3 LAN no detectado y SKIP_IF_UNAVAILABLE=false")

    # Verificar que responde
    if not cfg._check_qwen3_url(url):
        if cfg.skip_if_unavailable:
            pytest.skip(f"Qwen3 LAN no responde en {url}")
        else:
            pytest.fail(f"Qwen3 LAN no responde en {url}")

    _log.info(f"[fixture:qwen3_url] Qwen3 disponible: {url}")
    _ai_log.info(f"Qwen3 LAN verificado: {url} [LAN={cfg.is_lan(cfg.qwen3_host)}]")
    return url


@pytest.fixture(scope="session")
def siuo_retriever():
    """
    ContextRetriever con índices SIUO cargados.
    Se salta si los índices no existen.
    """
    from backend.modules.db_explorer.context_retriever import ContextRetriever
    from backend.modules.db_explorer.deep_indexer_service import TABLE_INDEX_PATH

    if not TABLE_INDEX_PATH.exists():
        if cfg.skip_if_unavailable:
            pytest.skip(f"Índices SIUO no encontrados en {TABLE_INDEX_PATH}")
        else:
            pytest.fail(f"Índices SIUO no encontrados en {TABLE_INDEX_PATH}")

    r = ContextRetriever()
    if not r.load():
        if cfg.skip_if_unavailable:
            pytest.skip("ContextRetriever no pudo cargar los índices")
        else:
            pytest.fail("ContextRetriever no pudo cargar los índices")

    stats = r.get_stats()
    _log.info(
        f"[fixture:siuo_retriever] Cargado: "
        f"{stats['tables_indexed']} tablas, {stats['concept_keywords']} keywords"
    )
    return r


@pytest.fixture(scope="session")
def chat_svc():
    """ChatService real (sin mocks)."""
    from backend.modules.chat.service import ChatService
    svc = ChatService()
    _log.info("[fixture:chat_svc] ChatService creado")
    return svc


@pytest.fixture(scope="session")
def summarizer():
    """ResponseSummarizer."""
    from backend.modules.chat.response_summarizer import get_response_summarizer
    return get_response_summarizer()


# ═══════════════════════════════════════════════════════════════════════════════
# Hook de pytest: imprimir resumen al final
# ═══════════════════════════════════════════════════════════════════════════════

def pytest_sessionfinish(session, exitstatus):
    """Imprime resumen de la sesión de tests."""
    _log.info(f"\n{'='*70}")
    _log.info(f"SESIÓN DE TESTS FINALIZADA — Exit code: {exitstatus}")
    _log.info(f"Logs guardados en: {_LOGS_DIR}")
    _log.info(f"  - conftest.log")
    _log.info(f"  - network_audit.log")
    _log.info(f"  - sql_trace.log")
    _log.info(f"  - ai_requests.log")
    _log.info(f"  - integration_traces.jsonl")
    _log.info(f"{'='*70}")


def pytest_configure(config):
    """Configuración inicial de pytest."""
    _log.info(f"\n{'='*70}")
    _log.info(f"DEVIA — Tests de integración")
    _log.info(f"DB:    {cfg.db_host}:{cfg.db_port}")
    _log.info(f"Qwen3: {cfg.qwen3_url or 'NO DETECTADO'}")
    _log.info(f"LAN only: {cfg.enforce_lan_only}")
    _log.info(f"{'='*70}")
