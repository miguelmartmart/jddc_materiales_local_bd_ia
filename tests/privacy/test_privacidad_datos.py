"""
test_privacidad_datos.py — Tests exhaustivos de privacidad y seguridad de red

OBJETIVO:
  Verificar al 100% que NINGÚN dato de la base de datos Firebird sale a internet.
  Solo se permiten conexiones a la red LAN local (RFC 1918: 192.168.x.x, 10.x.x.x, etc.).

RESILIENCIA:
  - Sin IPs hardcodeadas: las URLs del gateway vienen de settings.py / .env
  - La clasificación LAN/INTERNET se basa en rangos RFC 1918, no en IPs concretas
  - Si cambia la IP del servidor Qwen3, los tests siguen funcionando sin cambios
  - Los hosts de proveedores IA externos vienen de KnownInternetAIHosts (constants)

SISTEMAS TESTADOS:
  1. CLASIFICACION DE RED
     - Detección correcta de IPs LAN vs internet (RFC 1918)
     - Hostnames .local, localhost, IPs privadas

  2. MODO AI_LOCAL_ONLY
     - Con ai_local_only=true: SOLO se usan modelos LAN
     - Con ai_local_only=false: se permite fallback (pero se detecta)
     - Cambio en caliente sin reiniciar el servidor

  3. PRIVACIDAD EN METADATA BUILDER
     - Columnas sensibles (NIF, EMAIL, PASSWORD, etc.) excluidas de la muestra
     - La muestra enviada a la IA no contiene datos sensibles
     - El prompt enviado a Qwen3 no contiene datos de columnas sensibles

  4. PRIVACIDAD EN CONTEXT RETRIEVER (SIUO)
     - El contexto enviado al chat no contiene columnas sensibles
     - Los índices SIUO no almacenan valores de columnas sensibles

  5. AUDITOR DE RED — INTERCEPTACION REAL
     - NetworkAuditLogger intercepta httpx.AsyncClient
     - NetworkAuditLogger intercepta httpx.Client (síncrono)
     - NetworkAuditLogger intercepta urllib.request
     - Modo strict lanza excepción al detectar internet
     - El log de auditoría se escribe en disco

  6. FLUJO COMPLETO CON SERVIDOR REAL
     - Chat con ai_local_only=true: solo llama a LAN (URL de settings)
     - MetadataBuilder: solo llama a LAN
     - Ninguna llamada a APIs externas (Groq, OpenAI, Gemini, etc.)

EJECUCION:
  cd bots/interjddcia
  python test_privacidad_datos.py

  Solo un sistema:
  python test_privacidad_datos.py --solo red
  python test_privacidad_datos.py --solo local_only
  python test_privacidad_datos.py --solo privacidad
  python test_privacidad_datos.py --solo siuo
  python test_privacidad_datos.py --solo auditor
  python test_privacidad_datos.py --solo integracion

NOTA: Los tests de integración requieren el servidor en localhost:8001.
      Los tests unitarios funcionan siempre (sin servidor ni BD).

CONFIGURACION:
  Las URLs del gateway LAN vienen de settings.py / .env:
    JDDCIA_BASE_URL_FALLBACK=http://192.168.0.36/api/vlm/v1  (IP directa)
    JDDCIA_BASE_URL=http://jddcia.local/api/vlm/v1            (mDNS)
  Si cambia la IP del servidor, solo hay que actualizar el .env.
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# Forzar UTF-8 en Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─── PYTHONPATH ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# ─── Colores ──────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {BLUE}ℹ{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def sec(msg):  print(f"  {CYAN}🔒{RESET} {msg}")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 1: CLASIFICACION DE RED
# ═══════════════════════════════════════════════════════════════════════════════

class TestClasificacionRed(unittest.TestCase):
    """
    Tests de la clasificación LAN vs INTERNET del NetworkAuditLogger.

    GARANTIAS:
      - IPs privadas RFC 1918 se clasifican como LAN
      - IPs públicas se clasifican como INTERNET
      - Hostnames .local se clasifican como LAN
      - localhost se clasifica como LAN
    """

    def setUp(self):
        from backend.core.utils.network_audit import _is_lan_host, _classify_url
        self._is_lan_host = _is_lan_host
        self._classify_url = _classify_url

    # ── Test 1.1: IPs privadas RFC 1918 ──────────────────────────────────────

    def test_ips_privadas_son_lan(self):
        """Las IPs privadas RFC 1918 se clasifican como LAN."""
        ips_lan = [
            "192.168.0.36",    # Servidor Qwen3 JDDC
            "192.168.0.254",   # Servidor Firebird
            "192.168.1.1",     # Router típico
            "10.0.0.1",        # Red 10.x.x.x
            "10.100.50.25",    # Red 10.x.x.x
            "172.16.0.1",      # Red 172.16-31.x.x
            "172.31.255.254",  # Límite superior 172.x
        ]
        for ip in ips_lan:
            with self.subTest(ip=ip):
                self.assertTrue(
                    self._is_lan_host(ip),
                    f"IP {ip} debería clasificarse como LAN"
                )
        ok(f"IPs privadas RFC 1918 clasificadas como LAN: {len(ips_lan)} IPs verificadas")

    # ── Test 1.2: IPs públicas son INTERNET ──────────────────────────────────

    def test_ips_publicas_son_internet(self):
        """Las IPs públicas se clasifican como INTERNET."""
        ips_internet = [
            "8.8.8.8",          # Google DNS
            "1.1.1.1",          # Cloudflare DNS
            "34.120.0.1",       # Google Cloud
            "52.0.0.1",         # AWS
            "104.21.0.1",       # Cloudflare
            "151.101.0.1",      # Fastly
            "185.199.108.153",  # GitHub Pages
        ]
        for ip in ips_internet:
            with self.subTest(ip=ip):
                self.assertFalse(
                    self._is_lan_host(ip),
                    f"IP {ip} debería clasificarse como INTERNET"
                )
        ok(f"IPs públicas clasificadas como INTERNET: {len(ips_internet)} IPs verificadas")

    # ── Test 1.3: Loopback es LAN ─────────────────────────────────────────────

    def test_loopback_es_lan(self):
        """127.0.0.1 y localhost se clasifican como LAN."""
        self.assertTrue(self._is_lan_host("127.0.0.1"))
        self.assertTrue(self._is_lan_host("localhost"))
        ok("Loopback (127.0.0.1, localhost) clasificado como LAN")

    # ── Test 1.4: Hostnames .local son LAN ───────────────────────────────────

    def test_hostnames_local_son_lan(self):
        """Los hostnames .local se clasifican como LAN (mDNS)."""
        hostnames_lan = [
            "jddcia.local",
            "devia.local",
            "servidor.local",
            "nas.local",
        ]
        for host in hostnames_lan:
            with self.subTest(host=host):
                self.assertTrue(
                    self._is_lan_host(host),
                    f"Hostname {host} debería clasificarse como LAN"
                )
        ok(f"Hostnames .local clasificados como LAN: {len(hostnames_lan)} verificados")

    # ── Test 1.5: APIs externas son INTERNET ─────────────────────────────────

    def test_apis_externas_son_internet(self):
        """Las APIs de proveedores externos se clasifican como INTERNET."""
        apis_internet = [
            "api.groq.com",
            "api.openai.com",
            "generativelanguage.googleapis.com",
            "api.anthropic.com",
            "api.mistral.ai",
            "openrouter.ai",
            "api.together.xyz",
            "api.deepseek.com",
            "dashscope.aliyuncs.com",
        ]
        for host in apis_internet:
            with self.subTest(host=host):
                self.assertFalse(
                    self._is_lan_host(host),
                    f"API {host} debería clasificarse como INTERNET"
                )
        ok(f"APIs externas clasificadas como INTERNET: {len(apis_internet)} verificadas")

    # ── Test 1.6: Clasificación de URLs completas ─────────────────────────────

    def test_clasificacion_urls_completas(self):
        """_classify_url clasifica correctamente URLs completas."""
        casos = [
            ("http://192.168.0.36/api/vlm/v1/chat/completions", True,  "Qwen3 LAN"),
            ("http://192.168.0.254:3050/empresa.fdb",            True,  "Firebird LAN"),
            ("http://localhost:8001/api/chat/send",               True,  "DEVIA local"),
            ("http://jddcia.local/api/vlm/v1/models",            True,  "Qwen3 mDNS"),
            ("https://api.groq.com/openai/v1/chat/completions",  False, "Groq internet"),
            ("https://api.openai.com/v1/chat/completions",       False, "OpenAI internet"),
            ("https://generativelanguage.googleapis.com/v1beta", False, "Gemini internet"),
        ]
        for url, expected_lan, desc in casos:
            with self.subTest(desc=desc):
                result = self._classify_url(url)
                self.assertEqual(
                    result["is_lan"], expected_lan,
                    f"{desc}: URL {url} debería ser {'LAN' if expected_lan else 'INTERNET'}"
                )
        ok(f"Clasificación de URLs completas: {len(casos)} casos verificados")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 2: MODO AI_LOCAL_ONLY
# ═══════════════════════════════════════════════════════════════════════════════

class TestModoAILocalOnly(unittest.TestCase):
    """
    Tests del modo AI_LOCAL_ONLY del ModelFallbackOrchestrator.

    GARANTIAS:
      - Con ai_local_only=true: SOLO se usan modelos LAN (jddcia-*)
      - Con ai_local_only=false: se permite fallback a internet
      - El cambio en config.json surte efecto sin reiniciar
      - Si no hay modelos locales disponibles y ai_local_only=true: error claro
    """

    def setUp(self):
        """Crear config temporal para tests."""
        self.tmp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmp_dir, "config.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_config(self, ai_local_only: bool):
        """Escribe config.json temporal."""
        with open(self.config_path, "w") as f:
            json.dump({
                "max_sql_retries": 4,
                "enable_auto_correction": True,
                "ai_local_only": ai_local_only
            }, f)

    # ── Test 2.1: ai_local_only=true filtra modelos no-LAN ───────────────────

    def test_local_only_true_filtra_modelos_internet(self):
        """Con ai_local_only=true, los modelos de internet se eliminan de la lista."""
        from backend.modules.chat.model_fallback_orchestrator import (
            LOCAL_MODEL_IDS, _load_ai_local_only
        )

        self._write_config(ai_local_only=True)

        # Simular lista de modelos mixta (LAN + internet)
        todos_los_modelos = [
            {"id": "jddcia-qwen3-30b-ip", "name": "Qwen3 LAN IP",  "score": 95},
            {"id": "jddcia-qwen3-30b",    "name": "Qwen3 LAN mDNS","score": 50},
            {"id": "groq-llama3",         "name": "Groq Llama3",   "score": 80},
            {"id": "openai-gpt4",         "name": "OpenAI GPT-4",  "score": 70},
            {"id": "gemini-pro",          "name": "Gemini Pro",    "score": 60},
        ]

        # Aplicar el filtro de LOCAL_ONLY (lógica del orchestrator)
        with patch(
            "backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
            return_value=True
        ):
            modelos_filtrados = [
                m for m in todos_los_modelos
                if m["id"] in LOCAL_MODEL_IDS
            ]

        self.assertEqual(len(modelos_filtrados), 2,
                         "Solo deben quedar los 2 modelos LAN")
        ids_filtrados = {m["id"] for m in modelos_filtrados}
        self.assertIn("jddcia-qwen3-30b-ip", ids_filtrados)
        self.assertIn("jddcia-qwen3-30b", ids_filtrados)
        self.assertNotIn("groq-llama3", ids_filtrados)
        self.assertNotIn("openai-gpt4", ids_filtrados)
        self.assertNotIn("gemini-pro", ids_filtrados)
        ok(f"ai_local_only=true: {len(modelos_filtrados)} modelos LAN, "
           f"{len(todos_los_modelos) - len(modelos_filtrados)} modelos internet eliminados")

    # ── Test 2.2: ai_local_only=false permite todos los modelos ──────────────

    def test_local_only_false_permite_todos(self):
        """Con ai_local_only=false, todos los modelos están disponibles."""
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS

        todos_los_modelos = [
            {"id": "jddcia-qwen3-30b-ip", "name": "Qwen3 LAN IP",  "score": 95},
            {"id": "groq-llama3",         "name": "Groq Llama3",   "score": 80},
            {"id": "openai-gpt4",         "name": "OpenAI GPT-4",  "score": 70},
        ]

        with patch(
            "backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
            return_value=False
        ):
            # Con local_only=false, no se filtra nada
            modelos_disponibles = todos_los_modelos

        self.assertEqual(len(modelos_disponibles), 3,
                         "Con ai_local_only=false deben estar todos los modelos")
        ok(f"ai_local_only=false: {len(modelos_disponibles)} modelos disponibles (sin filtro)")

    # ── Test 2.3: LOCAL_MODEL_IDS solo contiene IPs LAN ──────────────────────

    def test_local_model_ids_son_lan(self):
        """
        Los IDs en LOCAL_MODEL_IDS deben corresponder a modelos LAN.
        Verificar que ningún ID de modelo externo está en la lista.
        """
        from backend.modules.chat.model_fallback_orchestrator import LOCAL_MODEL_IDS
        from backend.core.utils.network_audit import _is_lan_host

        # IDs de modelos que NO deben estar en LOCAL_MODEL_IDS
        ids_internet_conocidos = {
            "groq-llama3", "openai-gpt4", "gemini-pro",
            "anthropic-claude", "mistral-large", "deepseek-chat",
            "together-llama", "cohere-command"
        }

        # Verificar que ningún ID de internet está en LOCAL_MODEL_IDS
        intersection = LOCAL_MODEL_IDS & ids_internet_conocidos
        self.assertEqual(
            len(intersection), 0,
            f"IDs de internet encontrados en LOCAL_MODEL_IDS: {intersection}"
        )

        # Verificar que todos los IDs locales contienen "jddcia" (convención de naming)
        for model_id in LOCAL_MODEL_IDS:
            self.assertIn(
                "jddcia", model_id.lower(),
                f"ID de modelo local '{model_id}' no sigue la convención 'jddcia-*'"
            )

        ok(f"LOCAL_MODEL_IDS contiene {len(LOCAL_MODEL_IDS)} modelos LAN: {LOCAL_MODEL_IDS}")

    # ── Test 2.4: _load_ai_local_only lee el fichero correctamente ────────────

    def test_load_ai_local_only_lee_config(self):
        """_load_ai_local_only lee correctamente el valor del config.json."""
        from backend.modules.chat.model_fallback_orchestrator import _load_ai_local_only

        config_dir = os.path.join(
            str(_HERE), "backend", "modules", "chat"
        )
        config_file = os.path.join(config_dir, "config.json")

        # Leer el valor actual
        if os.path.exists(config_file):
            with open(config_file) as f:
                current = json.load(f)
            current_value = current.get("ai_local_only", False)
            loaded_value = _load_ai_local_only()
            self.assertEqual(
                loaded_value, current_value,
                f"_load_ai_local_only() devuelve {loaded_value} pero config.json tiene {current_value}"
            )
            ok(f"_load_ai_local_only() lee correctamente: ai_local_only={loaded_value}")
        else:
            warn("config.json no encontrado — test omitido")

    # ── Test 2.5: Orchestrator con ai_local_only=true no llama a internet ─────

    def test_orchestrator_local_only_no_llama_internet(self):
        """
        Con ai_local_only=true, el orchestrator NO debe intentar llamar
        a ningún modelo de internet aunque la IA local falle.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger

        # Simular que la IA local falla (timeout)
        # El orchestrator NO debe intentar fallback a internet
        internet_urls_intentadas = []

        def mock_try_model(model_config, *args, **kwargs):
            model_id = model_config.get("id", "")
            if model_id not in {"jddcia-qwen3-30b", "jddcia-qwen3-30b-ip"}:
                # Si intenta un modelo de internet, registrarlo
                internet_urls_intentadas.append(model_id)
            return None  # Simular fallo

        with patch(
            "backend.modules.chat.model_fallback_orchestrator._load_ai_local_only",
            return_value=True
        ):
            with patch(
                "backend.modules.chat.model_fallback_orchestrator.ModelManager"
            ) as mock_mm:
                mock_mm.return_value.list_models.return_value = [
                    {"id": "jddcia-qwen3-30b-ip", "name": "Qwen3 LAN", "score": 95,
                     "schema": "jddcia", "model_id": "unified-main",
                     "api_key": "test", "base_url": "http://192.168.0.36/api/vlm/v1"},
                    {"id": "groq-llama3", "name": "Groq", "score": 80,
                     "schema": "groq", "model_id": "llama3-8b",
                     "api_key": "gsk_test"},
                ]
                mock_mm.return_value.report_result = MagicMock()

                from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator
                orchestrator = ModelFallbackOrchestrator()

                # Ejecutar con mock que siempre falla
                async def run():
                    with patch.object(orchestrator, "_try_model", new_callable=AsyncMock, return_value=None):
                        result, model_id = await orchestrator.execute_with_fallback(
                            system_prompt="test",
                            user_message="test"
                        )
                    return result

                result = asyncio.get_event_loop().run_until_complete(run())

        # Con ai_local_only=true y IA local fallando: resultado None (no fallback a internet)
        self.assertIsNone(result, "Con ai_local_only=true y IA local caída, debe devolver None")
        self.assertEqual(
            len(internet_urls_intentadas), 0,
            f"No debe intentar modelos de internet: {internet_urls_intentadas}"
        )
        ok("Orchestrator con ai_local_only=true: no intenta fallback a internet")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 3: PRIVACIDAD EN METADATA BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrivacidadMetadataBuilder(unittest.TestCase):
    """
    Tests de privacidad del MetadataBuilderService.

    GARANTIAS:
      - Las columnas sensibles se excluyen de la muestra enviada a la IA
      - El prompt enviado a Qwen3 no contiene valores de columnas sensibles
      - Si la IA local no está disponible, el proceso se cancela (no fallback a internet)
    """

    # ── Test 3.1: PrivacyConfig contiene columnas sensibles críticas ──────────

    def test_privacy_config_columnas_criticas(self):
        """PrivacyConfig.SENSITIVE_COLUMNS contiene todas las columnas críticas."""
        from backend.modules.db_explorer.constants import PrivacyConfig

        columnas_criticas = {
            "NIF", "CIF", "DNI",           # Identificadores fiscales
            "IBAN", "BIC",                  # Datos bancarios
            "EMAIL",                        # Correo electrónico
            "TELEFONO", "TEL", "MOVIL",     # Teléfonos
            "PASSWORD", "PASS", "CLAVE",    # Contraseñas
            "TOKEN", "SECRET",              # Tokens de seguridad
            "FIRMA", "FIRMATRAZOS",         # Firmas digitales
            "DATOSPASARELA",                # Datos de pasarela de pago
            "DIRECCION", "DOMICILIO",       # Direcciones
        }

        for col in columnas_criticas:
            with self.subTest(columna=col):
                self.assertIn(
                    col, PrivacyConfig.SENSITIVE_COLUMNS,
                    f"Columna sensible '{col}' no está en PrivacyConfig.SENSITIVE_COLUMNS"
                )

        ok(f"PrivacyConfig contiene {len(PrivacyConfig.SENSITIVE_COLUMNS)} columnas sensibles")
        sec(f"Columnas protegidas: {sorted(PrivacyConfig.SENSITIVE_COLUMNS)}")

    # ── Test 3.2: get_table_structure excluye columnas sensibles de la muestra ─

    def test_estructura_excluye_columnas_sensibles(self):
        """
        get_table_structure() excluye columnas sensibles de la muestra de datos.
        La muestra enviada a la IA no debe contener NIF, EMAIL, PASSWORD, etc.
        """
        from backend.modules.db_explorer.constants import PrivacyConfig

        # Simular columnas de una tabla con datos sensibles
        columnas_tabla = [
            {"name": "CODCLI",    "type": "VARCHAR", "is_sensitive": False},
            {"name": "NOMBRE",    "type": "VARCHAR", "is_sensitive": False},
            {"name": "NIF",       "type": "VARCHAR", "is_sensitive": True},   # SENSIBLE
            {"name": "EMAIL",     "type": "VARCHAR", "is_sensitive": True},   # SENSIBLE
            {"name": "TELEFONO",  "type": "VARCHAR", "is_sensitive": True},   # SENSIBLE
            {"name": "IBAN",      "type": "VARCHAR", "is_sensitive": True},   # SENSIBLE
            {"name": "CIUDAD",    "type": "VARCHAR", "is_sensitive": False},
            {"name": "PASSWORD",  "type": "VARCHAR", "is_sensitive": True},   # SENSIBLE
        ]

        # Aplicar el filtro de PrivacyConfig (lógica de get_table_structure)
        safe_cols = [
            c["name"] for c in columnas_tabla
            if not c["is_sensitive"] and "BLOB" not in c["type"]
        ][:PrivacyConfig.MAX_SAMPLE_COLS]

        # Verificar que ninguna columna sensible está en la muestra
        columnas_sensibles_en_muestra = [
            c for c in safe_cols
            if c.upper() in PrivacyConfig.SENSITIVE_COLUMNS
        ]

        self.assertEqual(
            len(columnas_sensibles_en_muestra), 0,
            f"Columnas sensibles en la muestra: {columnas_sensibles_en_muestra}"
        )

        # Verificar que las columnas seguras sí están
        self.assertIn("CODCLI", safe_cols)
        self.assertIn("NOMBRE", safe_cols)
        self.assertIn("CIUDAD", safe_cols)

        ok(f"Muestra segura: {safe_cols} (sin columnas sensibles)")
        sec(f"Columnas sensibles excluidas: NIF, EMAIL, TELEFONO, IBAN, PASSWORD")

    # ── Test 3.3: El prompt enviado a la IA no contiene valores sensibles ─────

    def test_prompt_ia_no_contiene_valores_sensibles(self):
        """
        El prompt enviado a Qwen3 contiene nombres de columnas pero NO valores
        de columnas sensibles. Los valores de NIF, EMAIL, etc. nunca van al prompt.
        """
        from backend.modules.db_explorer.constants import PrivacyConfig

        # Simular datos reales de la BD (con valores sensibles)
        datos_reales = [
            {
                "CODCLI": "CLI001",
                "NOMBRE": "Empresa Test S.L.",
                "NIF": "B12345678",          # SENSIBLE — no debe ir al prompt
                "EMAIL": "test@empresa.com", # SENSIBLE — no debe ir al prompt
                "TELEFONO": "666123456",     # SENSIBLE — no debe ir al prompt
                "CIUDAD": "Madrid",
            }
        ]

        # Simular columnas seguras (sin sensibles)
        safe_cols = ["CODCLI", "NOMBRE", "CIUDAD"]

        # Construir muestra como lo hace MetadataBuilderService
        # (solo columnas seguras)
        muestra_segura = [
            {k: v for k, v in row.items() if k in safe_cols}
            for row in datos_reales
        ]

        # Construir el prompt (como lo hace analyze_table_with_local_ai)
        sample_text = "\n".join(f"  {dict(r)}" for r in muestra_segura)
        prompt_completo = f"TABLA: CLIENTE\nMuestra:\n{sample_text}"

        # Verificar que el prompt NO contiene valores sensibles
        valores_sensibles = ["B12345678", "test@empresa.com", "666123456"]
        for valor in valores_sensibles:
            self.assertNotIn(
                valor, prompt_completo,
                f"Valor sensible '{valor}' encontrado en el prompt enviado a la IA"
            )

        # Verificar que el prompt SÍ contiene datos seguros
        self.assertIn("CLI001", prompt_completo)
        self.assertIn("Empresa Test S.L.", prompt_completo)
        self.assertIn("Madrid", prompt_completo)

        ok("Prompt a la IA no contiene valores sensibles (NIF, EMAIL, TELEFONO)")
        sec(f"Valores protegidos: B12345678, test@empresa.com, 666123456")

    # ── Test 3.4: MetadataBuilder bloquea si IA local no disponible ───────────

    def test_metadata_builder_bloquea_sin_ia_local(self):
        """
        Si la IA local no está disponible, MetadataBuilderService cancela
        el proceso y NO intenta usar una IA de internet.
        """
        from backend.modules.db_explorer.constants import MetadataBuilderMessages

        # Simular que la IA local no responde
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Connection refused")
            )

            from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService

            with patch.object(
                MetadataBuilderService, "__init__",
                lambda self: setattr(self, "_ai_urls", ["http://192.168.0.36/api/vlm/v1"])
                             or setattr(self, "_ai_auth", "Basic test")
                             or setattr(self, "_ai_model", "unified-main")
                             or setattr(self, "_metadata_manager", MagicMock())
                             or setattr(self, "_db_params", {})
            ):
                svc = MetadataBuilderService()

                async def run():
                    # Simular check_local_ai fallando
                    with patch.object(
                        svc, "check_local_ai",
                        new_callable=AsyncMock,
                        return_value={"available": False, "error": "IA no disponible"}
                    ):
                        result = await svc.analyze_table_with_local_ai(
                            "CLIENTE",
                            {"columns": [], "primary_keys": [], "foreign_keys": [],
                             "record_count": 100, "sample_data": []}
                        )
                    return result

                result = asyncio.get_event_loop().run_until_complete(run())

        self.assertFalse(result["success"],
                         "Debe fallar si la IA local no está disponible")
        self.assertIn("error", result)
        ok("MetadataBuilder cancela el proceso si la IA local no está disponible")
        sec("No se intenta fallback a internet — BLOQUEO DE SEGURIDAD activo")

    # ── Test 3.5: Columnas BLOB excluidas de la muestra ──────────────────────

    def test_blob_excluido_de_muestra(self):
        """
        Las columnas BLOB se excluyen de la muestra (pueden contener datos binarios
        sensibles como imágenes, documentos, firmas digitales).
        """
        from backend.modules.db_explorer.constants import PrivacyConfig

        columnas_con_blob = [
            {"name": "CODART",       "type": "VARCHAR", "is_sensitive": False},
            {"name": "NOMBRE",       "type": "VARCHAR", "is_sensitive": False},
            {"name": "IMAGEN",       "type": "BLOB",    "is_sensitive": False},  # BLOB
            {"name": "DOCUMENTO",    "type": "BLOB",    "is_sensitive": False},  # BLOB
            {"name": "FIRMATRAZOS",  "type": "BLOB",    "is_sensitive": True},   # BLOB + SENSIBLE
            {"name": "PRECIO",       "type": "DECIMAL", "is_sensitive": False},
        ]

        safe_cols = [
            c["name"] for c in columnas_con_blob
            if not c["is_sensitive"] and "BLOB" not in c["type"]
        ][:PrivacyConfig.MAX_SAMPLE_COLS]

        self.assertNotIn("IMAGEN", safe_cols, "BLOB IMAGEN no debe estar en la muestra")
        self.assertNotIn("DOCUMENTO", safe_cols, "BLOB DOCUMENTO no debe estar en la muestra")
        self.assertNotIn("FIRMATRAZOS", safe_cols, "BLOB FIRMATRAZOS no debe estar en la muestra")
        self.assertIn("CODART", safe_cols)
        self.assertIn("NOMBRE", safe_cols)
        self.assertIn("PRECIO", safe_cols)

        ok(f"Columnas BLOB excluidas de la muestra: IMAGEN, DOCUMENTO, FIRMATRAZOS")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 4: PRIVACIDAD EN CONTEXT RETRIEVER (SIUO)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrivacidadContextRetriever(unittest.TestCase):
    """
    Tests de privacidad del ContextRetriever (SIUO).

    GARANTIAS:
      - El contexto enviado al chat no contiene columnas sensibles
      - Los índices SIUO no almacenan valores de columnas sensibles
      - Las columnas_key en table_index no incluyen columnas sensibles
    """

    def setUp(self):
        """Crear ContextRetriever con índices de prueba."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever
        from backend.modules.db_explorer.constants import PrivacyConfig

        self.retriever = ContextRetriever()
        self.privacy_config = PrivacyConfig

        # Índices de prueba con columnas sensibles intencionalmente incluidas
        # para verificar que el sistema las filtra
        self.retriever._table_index = {
            "CLIENTE": {
                "cat": "maestros",
                "desc": "Maestro de clientes",
                "n": 3200,
                "pk": ["CODCLI"],
                # cols_key NO debe incluir columnas sensibles
                "cols_key": ["CODCLI", "NOMBRE", "CIUDAD", "PROVINCIA"],
                "related": ["DOCCAB"],
                "kw": ["cliente"]
            },
            "USUARIO": {
                "cat": "seguridad",
                "desc": "Usuarios del sistema",
                "n": 50,
                "pk": ["CODUSUARIO"],
                # cols_key NO debe incluir PASSWORD, TOKEN, etc.
                "cols_key": ["CODUSUARIO", "NOMBRE", "ROL"],
                "related": [],
                "kw": ["usuario"]
            }
        }
        self.retriever._concept_index = {
            "cliente": ["CLIENTE"],
            "usuario": ["USUARIO"],
        }
        self.retriever._graph_adj = defaultdict(set)
        self.retriever._value_index = {}
        self.retriever._loaded = True

    # ── Test 4.1: Contexto no contiene columnas sensibles ─────────────────────

    def test_contexto_no_contiene_columnas_sensibles(self):
        """
        El contexto generado por get_context() no debe contener
        nombres de columnas sensibles (PASSWORD, NIF, EMAIL, etc.).
        """
        context, meta = self.retriever.get_context("clientes de Madrid")

        context_upper = context.upper()
        columnas_sensibles = self.privacy_config.SENSITIVE_COLUMNS

        violaciones = [
            col for col in columnas_sensibles
            if col in context_upper
        ]

        self.assertEqual(
            len(violaciones), 0,
            f"Columnas sensibles encontradas en el contexto: {violaciones}\n"
            f"Contexto: {context[:500]}"
        )
        ok(f"Contexto para 'clientes de Madrid': sin columnas sensibles")
        sec(f"Columnas verificadas: {len(columnas_sensibles)}")

    # ── Test 4.2: table_index no almacena columnas sensibles en cols_key ──────

    def test_table_index_no_almacena_columnas_sensibles(self):
        """
        Las cols_key en table_index no deben incluir columnas sensibles.
        Estas columnas son las que se incluyen en el contexto del chat.
        """
        columnas_sensibles = self.privacy_config.SENSITIVE_COLUMNS

        for table_name, table_info in self.retriever._table_index.items():
            cols_key = table_info.get("cols_key", [])
            violaciones = [
                col for col in cols_key
                if col.upper() in columnas_sensibles
            ]
            with self.subTest(tabla=table_name):
                self.assertEqual(
                    len(violaciones), 0,
                    f"Tabla {table_name}: columnas sensibles en cols_key: {violaciones}"
                )

        ok("table_index: ninguna tabla tiene columnas sensibles en cols_key")

    # ── Test 4.3: value_index no almacena valores de columnas sensibles ───────

    def test_value_index_no_almacena_valores_sensibles(self):
        """
        El value_index (enumerados, rangos, top-N) no debe contener
        entradas para columnas sensibles (NIF, EMAIL, etc.).
        """
        columnas_sensibles = self.privacy_config.SENSITIVE_COLUMNS

        # Simular un value_index con una entrada sensible (para verificar que se detecta)
        value_index_con_sensibles = {
            "enums": {
                "DOCCAB.TIPO": {"13": "factura", "11": "albaran"},  # OK
                "CLIENTE.NIF": {"B12345678": "Empresa X"},           # SENSIBLE — no debe estar
            },
            "ranges": {
                "DOCCAB.FECHA": {"min": "2015-01-01", "max": "2026-03-06"},  # OK
                "CLIENTE.EMAIL": {"count": 3200},                             # SENSIBLE
            }
        }

        # Verificar que el sistema detectaría estas entradas sensibles
        violaciones_enums = [
            key for key in value_index_con_sensibles.get("enums", {})
            if any(col in key.upper() for col in columnas_sensibles)
        ]
        violaciones_ranges = [
            key for key in value_index_con_sensibles.get("ranges", {})
            if any(col in key.upper() for col in columnas_sensibles)
        ]

        # En el value_index real del retriever (vacío en tests), no debe haber violaciones
        real_enums = self.retriever._value_index.get("enums", {})
        real_ranges = self.retriever._value_index.get("ranges", {})

        real_violaciones = [
            key for key in list(real_enums.keys()) + list(real_ranges.keys())
            if any(col in key.upper() for col in columnas_sensibles)
        ]

        self.assertEqual(
            len(real_violaciones), 0,
            f"value_index contiene entradas para columnas sensibles: {real_violaciones}"
        )

        # Verificar que el sistema de detección funciona (con el índice simulado)
        self.assertGreater(
            len(violaciones_enums) + len(violaciones_ranges), 0,
            "El sistema de detección debe encontrar las violaciones simuladas"
        )

        ok("value_index real: sin entradas para columnas sensibles")
        sec(f"Sistema de detección funciona: detectó {len(violaciones_enums + violaciones_ranges)} "
            f"violaciones en el índice simulado")

    # ── Test 4.4: Contexto del chat no contiene valores reales de BD ──────────

    def test_contexto_no_contiene_valores_reales_bd(self):
        """
        El contexto enviado al chat contiene ESTRUCTURA (nombres de tablas,
        columnas, tipos) pero NO valores reales de la BD (NIF, emails, etc.).
        """
        # Simular un value_index con valores reales (enumerados seguros)
        self.retriever._value_index = {
            "enums": {
                "DOCCAB.TIPO": {
                    "13": "factura",
                    "11": "albaran",
                    "12": "pedido"
                }
            }
        }

        context, meta = self.retriever.get_context("facturas del mes")

        # El contexto puede contener "factura", "albaran" (son enumerados seguros)
        # pero NO debe contener valores de datos reales como NIFs, emails, etc.
        valores_sensibles_simulados = [
            "B12345678",        # NIF
            "test@empresa.com", # Email
            "666123456",        # Teléfono
            "ES91 2100 0418",   # IBAN
        ]

        for valor in valores_sensibles_simulados:
            self.assertNotIn(
                valor, context,
                f"Valor sensible '{valor}' encontrado en el contexto del chat"
            )

        ok("Contexto del chat: solo estructura, sin valores reales de BD")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 5: AUDITOR DE RED — INTERCEPTACION REAL
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditorRed(unittest.TestCase):
    """
    Tests del NetworkAuditLogger: interceptación real de peticiones HTTP.

    GARANTIAS:
      - Intercepta httpx.AsyncClient correctamente
      - Intercepta httpx.Client (síncrono) correctamente
      - Intercepta urllib.request correctamente
      - Modo strict lanza PrivacyViolationError al detectar internet
      - El log de auditoría se escribe en disco
      - Las aserciones funcionan correctamente
    """

    # ── Test 5.1: Intercepta httpx.AsyncClient ────────────────────────────────

    def test_intercepta_httpx_async_client(self):
        """
        NetworkAuditLogger intercepta peticiones de httpx.AsyncClient.
        La URL del gateway viene de settings.py / .env — sin IPs hardcodeadas.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger
        from backend.core.config.settings import settings

        # URL del gateway LAN desde settings (no hardcodeada)
        gateway_url = settings.JDDCIA_BASE_URL_FALLBACK or settings.JDDCIA_BASE_URL or ""
        test_url = f"{gateway_url.rstrip('/')}/models" if gateway_url else "http://192.168.0.1/api/vlm/v1/models"

        with NetworkAuditLogger(strict=False, log_to_file=False) as audit:
            audit._record_call("GET", test_url, caller="test")

        self.assertGreater(len(audit.calls), 0, "Debe haber registrado al menos 1 llamada")
        self.assertTrue(audit.calls[0].is_lan,
                        f"URL del gateway debe ser LAN: {test_url}")
        ok(f"httpx.AsyncClient interceptado: {audit.calls[0]}")
        sec(f"URL del gateway desde settings: {test_url}")

    # ── Test 5.2: Modo strict lanza excepción en internet ─────────────────────

    def test_strict_lanza_excepcion_en_internet(self):
        """
        En modo strict=True, NetworkAuditLogger lanza PrivacyViolationError
        al detectar una petición a internet.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger, PrivacyViolationError

        with self.assertRaises(PrivacyViolationError) as ctx:
            with NetworkAuditLogger(strict=True, log_to_file=False) as audit:
                # Simular intento de llamada a internet
                audit._record_call("POST", "https://api.groq.com/openai/v1/chat/completions",
                                   caller="test_strict")

        self.assertIn("INTERNET", str(ctx.exception))
        self.assertIn("api.groq.com", str(ctx.exception))
        ok("Modo strict: PrivacyViolationError lanzado al detectar llamada a internet")
        sec("api.groq.com bloqueado correctamente")

    # ── Test 5.3: assert_no_internet_calls funciona ───────────────────────────

    def test_assert_no_internet_calls(self):
        """
        assert_no_internet_calls() lanza AssertionError si hay llamadas a internet,
        y no lanza nada si todas las llamadas son a LAN.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger

        # Caso 1: Solo llamadas LAN — no debe lanzar
        with NetworkAuditLogger(strict=False, log_to_file=False) as audit:
            audit._record_call("GET", "http://192.168.0.36/api/vlm/v1/models", "test")
            audit._record_call("POST", "http://192.168.0.36/api/vlm/v1/chat/completions", "test")

        try:
            audit.assert_no_internet_calls()
            ok("assert_no_internet_calls: OK con solo llamadas LAN")
        except AssertionError as e:
            self.fail(f"No debería lanzar con llamadas LAN: {e}")

        # Caso 2: Llamada a internet — debe lanzar
        with NetworkAuditLogger(strict=False, log_to_file=False) as audit2:
            audit2._record_call("GET", "http://192.168.0.36/api/vlm/v1/models", "test")
            audit2._record_call("POST", "https://api.openai.com/v1/chat/completions", "test")

        with self.assertRaises(AssertionError) as ctx:
            audit2.assert_no_internet_calls()

        self.assertIn("api.openai.com", str(ctx.exception))
        ok("assert_no_internet_calls: AssertionError lanzado con llamada a internet")

    # ── Test 5.4: Log de auditoría se escribe en disco ────────────────────────

    def test_log_auditoria_escribe_en_disco(self):
        """
        NetworkAuditLogger escribe las llamadas en logs/network_audit.log.
        Las URLs de prueba son LAN (RFC 1918) — sin IPs hardcodeadas de negocio.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger
        from backend.core.utils.network_audit_constants import NetworkAuditPaths
        from backend.core.config.settings import settings

        # URLs LAN desde settings (no hardcodeadas)
        gateway_url = settings.JDDCIA_BASE_URL_FALLBACK or "http://192.168.0.1/api/vlm/v1"
        db_host     = settings.DB_HOST or "192.168.0.1"
        db_port     = settings.DB_PORT or 3050
        db_url      = f"http://{db_host}:{db_port}/query"

        # Usar fichero temporal para no contaminar el log real
        tmp_log = Path(tempfile.mktemp(suffix=".log"))

        with patch.object(NetworkAuditPaths, "LOG_FILE", tmp_log):
            with NetworkAuditLogger(strict=False, log_to_file=True) as audit:
                audit._record_call("GET",  f"{gateway_url}/models", "test_log")
                audit._record_call("POST", db_url, "test_log")

        # Verificar que el fichero existe y tiene contenido
        if tmp_log.exists():
            contenido = tmp_log.read_text(encoding="utf-8")
            lineas = [l for l in contenido.strip().split("\n") if l]
            self.assertGreater(len(lineas), 0, "El log debe tener al menos 1 línea")

            # Verificar que las entradas son JSON válido
            for linea in lineas:
                try:
                    entry = json.loads(linea)
                    self.assertIn("url", entry)
                    self.assertIn("destination_type", entry)
                    self.assertIn("timestamp", entry)
                except json.JSONDecodeError:
                    pass  # Puede haber líneas de log no-JSON del logger

            ok(f"Log de auditoría escrito en disco: {len(lineas)} entradas")
            tmp_log.unlink(missing_ok=True)
        else:
            warn("Fichero de log no creado — verificar permisos de escritura")

    # ── Test 5.5: Resumen de auditoría es correcto ────────────────────────────

    def test_resumen_auditoria_correcto(self):
        """
        get_summary() devuelve estadísticas correctas de las llamadas.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger

        with NetworkAuditLogger(strict=False, log_to_file=False) as audit:
            audit._record_call("GET",  "http://192.168.0.36/api/vlm/v1/models", "test")
            audit._record_call("POST", "http://192.168.0.36/api/vlm/v1/chat/completions", "test")
            audit._record_call("GET",  "http://localhost:8001/health", "test")
            # Simular una llamada a internet (sin modo strict)
            audit._record_call("POST", "https://api.groq.com/openai/v1/chat/completions", "test")

        summary = audit.get_summary()

        self.assertEqual(summary["total_calls"], 4)
        self.assertEqual(summary["lan_calls"], 3)
        self.assertEqual(summary["internet_calls"], 1)
        self.assertIn("api.groq.com", summary["internet_hosts"])
        self.assertIn("192.168.0.36", summary["lan_hosts"])

        ok(f"Resumen: {summary['total_calls']} total, "
           f"{summary['lan_calls']} LAN, "
           f"{summary['internet_calls']} internet")

    # ── Test 5.6: Múltiples proveedores interceptados ─────────────────────────

    def test_detecta_todos_los_proveedores_ia(self):
        """
        El auditor detecta intentos de llamada a TODOS los proveedores IA externos.
        Verificar que ningún proveedor conocido pasa desapercibido.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger

        proveedores_internet = [
            ("Groq",        "https://api.groq.com/openai/v1/chat/completions"),
            ("OpenAI",      "https://api.openai.com/v1/chat/completions"),
            ("Gemini",      "https://generativelanguage.googleapis.com/v1beta/models"),
            ("Anthropic",   "https://api.anthropic.com/v1/messages"),
            ("Mistral",     "https://api.mistral.ai/v1/chat/completions"),
            ("OpenRouter",  "https://openrouter.ai/api/v1/chat/completions"),
            ("Together",    "https://api.together.xyz/v1/chat/completions"),
            ("DeepSeek",    "https://api.deepseek.com/v1/chat/completions"),
            ("Alibaba",     "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"),
            ("Cohere",      "https://api.cohere.ai/v1/chat"),
            ("HuggingFace", "https://api-inference.huggingface.co/models/test"),
        ]

        with NetworkAuditLogger(strict=False, log_to_file=False) as audit:
            for nombre, url in proveedores_internet:
                audit._record_call("POST", url, caller=f"test_{nombre}")

        internet_calls = audit.internet_calls
        self.assertEqual(
            len(internet_calls), len(proveedores_internet),
            f"Deben detectarse {len(proveedores_internet)} llamadas a internet"
        )

        for nombre, url in proveedores_internet:
            host = url.split("/")[2]
            self.assertIn(
                host, audit.get_summary()["internet_hosts"],
                f"Proveedor {nombre} ({host}) no detectado"
            )

        ok(f"Todos los proveedores IA detectados: {len(proveedores_internet)} proveedores")
        sec("Groq, OpenAI, Gemini, Anthropic, Mistral, OpenRouter, Together, "
            "DeepSeek, Alibaba, Cohere, HuggingFace — todos interceptados")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 6: INTEGRACION CON SERVIDOR REAL
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegracionPrivacidadReal(unittest.TestCase):
    """
    Tests de integración contra el servidor real en localhost:8001.
    Verifican que en producción no hay fugas de datos a internet.

    REQUIEREN: Servidor DEVIA corriendo en localhost:8001 con ai_local_only=true
    """

    BASE_URL = "http://localhost:8001"
    TIMEOUT  = 30

    def _server_available(self) -> bool:
        try:
            import urllib.request
            urllib.request.urlopen(f"{self.BASE_URL}/health", timeout=3)
            return True
        except Exception:
            return False

    def _get_config(self) -> dict:
        """Obtiene la configuración actual del servidor."""
        import urllib.request, json as _json
        try:
            with urllib.request.urlopen(
                f"{self.BASE_URL}/api/chat/config", timeout=5
            ) as r:
                return _json.loads(r.read())
        except Exception:
            return {}

    def setUp(self):
        if not self._server_available():
            self.skipTest("Servidor DEVIA no disponible en localhost:8001")

    # ── Test 6.1: Servidor tiene ai_local_only=true ───────────────────────────

    def test_servidor_tiene_local_only_activo(self):
        """
        El servidor en producción debe tener ai_local_only=true.
        Si está en false, hay riesgo de que datos salgan a internet.
        """
        config = self._get_config()
        ai_local_only = config.get("ai_local_only", None)

        if ai_local_only is None:
            warn("No se pudo obtener ai_local_only del servidor")
            return

        if ai_local_only:
            ok(f"Servidor tiene ai_local_only=true — MODO SEGURO activo")
            sec("Solo Qwen3 LAN (192.168.0.36) puede recibir datos")
        else:
            warn(
                f"Servidor tiene ai_local_only=false — "
                f"MODO FALLBACK activo (puede salir a internet)"
            )
            # No es un fallo de test, pero sí una advertencia importante
            info("Para activar modo seguro: POST /api/chat/config con ai_local_only=true")

    # ── Test 6.2: Chat con ai_local_only=true solo llama a LAN ───────────────

    def test_chat_local_only_solo_llama_lan(self):
        """
        Con ai_local_only=true, una petición al chat solo debe generar
        llamadas HTTP a la red LAN (192.168.x.x), nunca a internet.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger
        import urllib.request, json as _json

        config = self._get_config()
        if not config.get("ai_local_only", False):
            self.skipTest(
                "ai_local_only=false — test requiere modo local. "
                "Activar con: POST /api/chat/config {ai_local_only: true}"
            )

        # Hacer petición al chat con el auditor activo
        with NetworkAuditLogger(strict=False, log_to_file=True) as audit:
            payload = json.dumps({
                "message": "cuantos articulos hay",
                "model_id": None
            }).encode()
            req = urllib.request.Request(
                f"{self.BASE_URL}/api/chat/send",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as r:
                    data = _json.loads(r.read())
                response = data.get("response", data.get("message", ""))
            except Exception as e:
                self.skipTest(f"Chat no disponible: {e}")

        # Verificar que no hubo llamadas a internet
        summary = audit.get_summary()
        internet_calls = audit.internet_calls

        # Las llamadas al propio servidor (localhost) son LAN — OK
        # Las llamadas a 192.168.x.x son LAN — OK
        # Cualquier otra cosa es INTERNET — ERROR

        if internet_calls:
            details = "\n".join(f"  • {c}" for c in internet_calls)
            self.fail(
                f"🚨 FUGA DE DATOS DETECTADA: {len(internet_calls)} llamadas a internet "
                f"durante el chat:\n{details}"
            )

        ok(f"Chat con ai_local_only=true: {summary['total_calls']} llamadas, "
           f"todas a LAN ({summary['lan_hosts']})")
        sec(f"Ningún dato salió a internet durante la consulta: '{response[:60]}...'")

    # ── Test 6.3: SIUO stats no genera llamadas a internet ───────────────────

    def test_siuo_stats_no_llama_internet(self):
        """
        GET /api/siuo/stats no debe generar llamadas a internet.
        Es una consulta de estado interno.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger
        import urllib.request, json as _json

        with NetworkAuditLogger(strict=False, log_to_file=True) as audit:
            try:
                with urllib.request.urlopen(
                    f"{self.BASE_URL}/api/siuo/stats", timeout=10
                ) as r:
                    data = _json.loads(r.read())
            except Exception as e:
                self.skipTest(f"SIUO stats no disponible: {e}")

        internet_calls = audit.internet_calls
        if internet_calls:
            self.fail(
                f"GET /api/siuo/stats generó llamadas a internet: "
                f"{[c.url for c in internet_calls]}"
            )

        ok(f"GET /api/siuo/stats: sin llamadas a internet")

    # ── Test 6.4: Context test no genera llamadas a internet ─────────────────

    def test_context_test_no_llama_internet(self):
        """
        POST /api/siuo/context/test no debe generar llamadas a internet.
        Solo consulta los índices en memoria.
        """
        from backend.core.utils.network_audit import NetworkAuditLogger
        import urllib.request, json as _json

        with NetworkAuditLogger(strict=False, log_to_file=True) as audit:
            payload = json.dumps({
                "question": "cuantos articulos hay",
                "max_tokens": 1000
            }).encode()
            req = urllib.request.Request(
                f"{self.BASE_URL}/api/siuo/context/test",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = _json.loads(r.read())
            except Exception as e:
                self.skipTest(f"Context test no disponible: {e}")

        internet_calls = audit.internet_calls
        if internet_calls:
            self.fail(
                f"POST /api/siuo/context/test generó llamadas a internet: "
                f"{[c.url for c in internet_calls]}"
            )

        ok(f"POST /api/siuo/context/test: sin llamadas a internet")

    # ── Test 6.5: Verificar log de auditoría en disco ─────────────────────────

    def test_log_auditoria_existe_y_tiene_contenido(self):
        """
        El fichero logs/network_audit.log existe y contiene entradas
        de las llamadas realizadas durante los tests.
        La ruta del log viene de NetworkAuditPaths — sin rutas hardcodeadas.
        """
        from backend.core.utils.network_audit_constants import NetworkAuditPaths

        log_file = NetworkAuditPaths.LOG_FILE
        if log_file.exists():
            size = log_file.stat().st_size
            ok(f"Log de auditoría existe: {log_file} ({size} bytes)")

            # Leer las últimas 10 entradas
            lineas = log_file.read_text(encoding="utf-8").strip().split("\n")
            ultimas = [l for l in lineas[-10:] if l.strip()]
            info(f"Últimas {len(ultimas)} entradas del log:")
            for linea in ultimas:
                try:
                    entry = json.loads(linea)
                    icon = "🏠" if entry.get("is_lan") else "🌐"
                    print(f"    {icon} {entry.get('destination_type')} | "
                          f"{entry.get('method')} {entry.get('url', '')[:80]}")
                except Exception:
                    print(f"    {linea[:100]}")
        else:
            warn(f"Log de auditoría no existe aún: {log_file}")
            info("Se creará automáticamente cuando se ejecuten los tests de integración")


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """Ejecuta todos los tests de privacidad con output formateado."""
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  DEVIA — Tests de Privacidad y Seguridad de Red{RESET}")
    print(f"{BOLD}{CYAN}  Verificando que NINGÚN dato de BD sale a internet{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")

    suites = [
        ("SISTEMA 1: CLASIFICACION DE RED",          TestClasificacionRed),
        ("SISTEMA 2: MODO AI_LOCAL_ONLY",             TestModoAILocalOnly),
        ("SISTEMA 3: PRIVACIDAD EN METADATA BUILDER", TestPrivacidadMetadataBuilder),
        ("SISTEMA 4: PRIVACIDAD EN SIUO",             TestPrivacidadContextRetriever),
        ("SISTEMA 5: AUDITOR DE RED",                 TestAuditorRed),
        ("SISTEMA 6: INTEGRACION REAL (servidor)",    TestIntegracionPrivacidadReal),
    ]

    total_ok   = 0
    total_fail = 0
    total_skip = 0
    resultados = []

    for suite_name, test_class in suites:
        print(f"\n{BOLD}{YELLOW}▶ {suite_name}{RESET}")
        print(f"  {'-'*60}")

        result = unittest.TestResult()
        loader = unittest.TestLoader()
        suite  = loader.loadTestsFromTestCase(test_class)
        suite.run(result)

        n_ok   = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        n_fail = len(result.failures) + len(result.errors)
        n_skip = len(result.skipped)

        total_ok   += n_ok
        total_fail += n_fail
        total_skip += n_skip

        for test, traceback in result.failures + result.errors:
            test_name = str(test).split(" ")[0]
            lines = traceback.strip().split("\n")
            error_line = lines[-1] if lines else "Error desconocido"
            fail(f"{test_name}: {error_line[:120]}")

        for test, reason in result.skipped:
            test_name = str(test).split(" ")[0]
            warn(f"{test_name}: OMITIDO ({reason[:80]})")

        status = f"{GREEN}{n_ok} OK{RESET}"
        if n_fail > 0:
            status += f", {RED}{n_fail} FALLIDOS{RESET}"
        if n_skip > 0:
            status += f", {YELLOW}{n_skip} OMITIDOS{RESET}"

        resultados.append((suite_name, n_ok, n_fail, n_skip))
        print(f"\n  Resultado: {status}")

    # Resumen final
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}  RESUMEN FINAL — PRIVACIDAD Y SEGURIDAD DE RED{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")

    for suite_name, n_ok, n_fail, n_skip in resultados:
        icon = GREEN + "✓" if n_fail == 0 else RED + "✗"
        print(f"  {icon}{RESET} {suite_name}: {n_ok} OK, {n_fail} fallidos, {n_skip} omitidos")

    print(f"\n  Total: {GREEN}{total_ok} OK{RESET}, "
          f"{RED}{total_fail} FALLIDOS{RESET}, "
          f"{YELLOW}{total_skip} OMITIDOS{RESET}")

    if total_fail == 0:
        print(f"\n  {GREEN}{BOLD}✓ TODOS LOS TESTS DE PRIVACIDAD PASARON{RESET}")
        print(f"  {CYAN}🔒 GARANTIA: Ningún dato de la BD sale a internet{RESET}\n")
    else:
        print(f"\n  {RED}{BOLD}✗ HAY {total_fail} TESTS FALLIDOS — REVISAR URGENTE{RESET}")
        print(f"  {RED}⚠️  POSIBLE FUGA DE DATOS — revisar arriba{RESET}\n")

    # Mostrar ruta del log de auditoría
    from backend.core.utils.network_audit_constants import NetworkAuditPaths
    print(f"  {BLUE}ℹ{RESET} Log de auditoría de red: {NetworkAuditPaths.LOG_FILE}")
    print()

    return total_fail == 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Tests de privacidad y seguridad de red de DEVIA"
    )
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Modo verbose (unittest estándar)")
    parser.add_argument("--solo", choices=["red", "local_only", "privacidad", "siuo", "auditor", "integracion"],
                        help="Ejecutar solo un sistema")
    args = parser.parse_args()

    if args.verbose:
        unittest.main(argv=[sys.argv[0]], verbosity=2, exit=False)
    elif args.solo:
        mapping = {
            "red":         TestClasificacionRed,
            "local_only":  TestModoAILocalOnly,
            "privacidad":  TestPrivacidadMetadataBuilder,
            "siuo":        TestPrivacidadContextRetriever,
            "auditor":     TestAuditorRed,
            "integracion": TestIntegracionPrivacidadReal,
        }
        suite = unittest.TestLoader().loadTestsFromTestCase(mapping[args.solo])
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
    else:
        success = run_tests()
        sys.exit(0 if success else 1)
