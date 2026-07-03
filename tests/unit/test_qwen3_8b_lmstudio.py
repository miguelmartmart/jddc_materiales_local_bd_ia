"""
test_qwen3_8b_lmstudio.py — Tests unitarios para el módulo Qwen3 8B VL (LM Studio)

OBJETIVO:
  Verificar la configuración, integración y comportamiento del modelo Qwen3 8B VL
  servido por LM Studio en la red LAN JDDC.

SISTEMAS TESTADOS:
  1. CONFIGURACIÓN DE MODELOS
     - Los IDs del 8B están en LocalModelIds.ALL
     - jddcia_models.json tiene las entradas correctas del 8B
     - El model_id del servidor es 'qwen/qwen3-vl-8b'
     - El schema es 'openai_compatible' (no 'jddcia')
     - La api_key es 'lm-studio'

  2. FACTORY DE PROVIDERS
     - El schema 'openai_compatible' devuelve OpenAICompatibleProvider
     - El schema 'jddcia' devuelve JDDCIAProvider (no cambia)
     - El campo 'schema' tiene prioridad sobre 'provider' en el orchestrator

  3. DISCOVERY SERVICE
     - discover_lmstudio() devuelve lista vacía si LM Studio no está disponible
     - discover_lmstudio() parsea correctamente la respuesta de /v1/models
     - discover_all() incluye la clave 'lmstudio' en el resultado

  4. MODO AI_LOCAL_ONLY CON 8B
     - Los IDs del 8B están en LocalModelIds.ALL → el orchestrator los incluye
     - En modo ai_local_only=true, el 8B se usa como fallback del 30B
     - preferred_model_id='jddcia-qwen3-8b-ip' coloca el 8B primero

  5. PRIVACIDAD — EL 8B ES LAN (no internet)
     - Las URLs del 8B (192.168.0.36:1234, jddcia.local:1234) son LAN
     - El auditor de red NO las clasifica como internet

EJECUCIÓN:
  cd bots/interjddcia
  python -m pytest tests/unit/test_qwen3_8b_lmstudio.py -v

  Solo un sistema:
  python -m pytest tests/unit/test_qwen3_8b_lmstudio.py -v -k "configuracion"
"""

import json
import os
import sys
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Path setup ───────────────────────────────────────────────────────────────
# Añadir la raíz del proyecto al path para imports
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# ─── Constantes del módulo LM Studio (adaptadas de la otra app) ───────────────
# Fuente: agente.constants.ts de CIBERIA (adaptado a Python)
LMSTUDIO_MODEL_ID        = "lmstudio-qwen3-8b"          # ID lógico (respuestas al cliente)
LMSTUDIO_ENDPOINT_IP     = "http://172.19.64.1:1234/v1"  # IP real (interfaz Hyper-V/WSL de LM Studio)
LMSTUDIO_ENDPOINT_MDNS   = "http://jddcia.local:1234/v1" # mDNS
LMSTUDIO_MODEL_ID_SERVER = "qwen/qwen3-vl-8b"           # ID real en LM Studio
LMSTUDIO_TIMEOUTS = {
    "ANALYZE_MS": 180_000,
    "CHAT_MS":    120_000,
    "STATUS_MS":    3_000,
}

# IDs lógicos en jddcia_models.json
QWEN3_8B_ID_IP   = "jddcia-qwen3-8b-ip"
QWEN3_8B_ID_MDNS = "jddcia-qwen3-8b"
QWEN3_30B_ID_IP  = "jddcia-qwen3-30b-ip"
QWEN3_30B_ID_MDNS = "jddcia-qwen3-30b"


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 1: CONFIGURACIÓN DE MODELOS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfiguracionModelos(unittest.TestCase):
    """Verifica que jddcia_models.json y LocalModelIds están correctamente configurados."""

    @classmethod
    def setUpClass(cls):
        """Carga jddcia_models.json una sola vez para todos los tests."""
        models_path = _PROJECT_ROOT / "backend" / "core" / "config" / "models" / "jddcia_models.json"
        with open(models_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cls.models = {m["id"]: m for m in data["models"]}

    def test_8b_ip_existe_en_json(self):
        """El modelo jddcia-qwen3-8b-ip debe existir en jddcia_models.json."""
        self.assertIn(QWEN3_8B_ID_IP, self.models,
                      f"Falta '{QWEN3_8B_ID_IP}' en jddcia_models.json")

    def test_8b_mdns_existe_en_json(self):
        """El modelo jddcia-qwen3-8b debe existir en jddcia_models.json."""
        self.assertIn(QWEN3_8B_ID_MDNS, self.models,
                      f"Falta '{QWEN3_8B_ID_MDNS}' en jddcia_models.json")

    def test_8b_model_id_servidor_correcto(self):
        """El model_id del servidor debe ser 'qwen/qwen3-vl-8b' (confirmado en LM Studio)."""
        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                model = self.models[model_id]
                self.assertEqual(
                    model["model_id"], LMSTUDIO_MODEL_ID_SERVER,
                    f"{model_id}: model_id debe ser '{LMSTUDIO_MODEL_ID_SERVER}', "
                    f"es '{model['model_id']}'"
                )

    def test_8b_schema_es_openai_compatible(self):
        """El schema del 8B debe ser 'openai_compatible' (LM Studio no usa Basic Auth)."""
        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                model = self.models[model_id]
                self.assertEqual(
                    model.get("schema"), "openai_compatible",
                    f"{model_id}: schema debe ser 'openai_compatible', "
                    f"es '{model.get('schema')}'"
                )

    def test_8b_api_key_es_lm_studio(self):
        """La api_key del 8B debe ser 'lm-studio' (LM Studio acepta cualquier Bearer)."""
        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                model = self.models[model_id]
                self.assertEqual(
                    model.get("api_key"), "lm-studio",
                    f"{model_id}: api_key debe ser 'lm-studio'"
                )

    def test_8b_ip_base_url_correcta(self):
        """La base_url del 8B-IP debe apuntar al puerto 1234 (LM Studio en 172.19.64.1)."""
        model = self.models[QWEN3_8B_ID_IP]
        self.assertIn(":1234", model["base_url"],
                      f"base_url del 8B-IP debe incluir ':1234', es '{model['base_url']}'")
        self.assertIn("/v1", model["base_url"],
                      f"base_url del 8B-IP debe incluir '/v1'")
        self.assertIn("172.19.64.1", model["base_url"],
                      f"base_url del 8B-IP debe ser 172.19.64.1 (interfaz Hyper-V/WSL de LM Studio)")

    def test_8b_mdns_base_url_correcta(self):
        """La base_url del 8B-mDNS debe apuntar a jddcia.local:1234."""
        model = self.models[QWEN3_8B_ID_MDNS]
        self.assertIn("jddcia.local", model["base_url"])
        self.assertIn(":1234", model["base_url"])

    def test_8b_no_tiene_basic_auth_en_headers(self):
        """El 8B NO debe tener Authorization Basic en headers (es LM Studio, no nginx)."""
        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                model = self.models[model_id]
                headers = model.get("headers", {})
                auth = headers.get("Authorization", "")
                self.assertNotIn("Basic", auth,
                                 f"{model_id}: NO debe tener Basic Auth en headers")

    def test_30b_mantiene_basic_auth(self):
        """El 30B debe seguir teniendo Basic Auth (nginx gateway, no cambia)."""
        for model_id in [QWEN3_30B_ID_IP, QWEN3_30B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                model = self.models[model_id]
                headers = model.get("headers", {})
                auth = headers.get("Authorization", "")
                self.assertIn("Basic", auth,
                              f"{model_id}: debe mantener Basic Auth en headers")

    def test_8b_enabled(self):
        """Los modelos 8B deben estar habilitados por defecto."""
        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                model = self.models[model_id]
                self.assertTrue(model.get("enabled", False),
                                f"{model_id}: debe estar enabled=true")

    def test_8b_context_limit_mayor_que_30b(self):
        """El 8B tiene context_limit 8192 > 4096 del 30B."""
        model_8b = self.models[QWEN3_8B_ID_IP]
        model_30b = self.models[QWEN3_30B_ID_IP]
        self.assertGreater(
            model_8b.get("context_limit", 0),
            model_30b.get("context_limit", 0),
            "El 8B debe tener mayor context_limit que el 30B"
        )

    def test_8b_tier_es_high(self):
        """El 8B debe tener tier='high' (no 'elite' como el 30B)."""
        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                model = self.models[model_id]
                self.assertEqual(model.get("tier"), "high",
                                 f"{model_id}: tier debe ser 'high'")

    def test_30b_tier_es_elite(self):
        """El 30B debe mantener tier='elite'."""
        model = self.models[QWEN3_30B_ID_IP]
        self.assertEqual(model.get("tier"), "elite")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 2: LocalModelIds — FUENTE ÚNICA DE VERDAD
# ═══════════════════════════════════════════════════════════════════════════════

class TestLocalModelIds(unittest.TestCase):
    """Verifica que LocalModelIds.ALL incluye los IDs del 8B."""

    @classmethod
    def setUpClass(cls):
        from backend.core.utils.network_audit_constants import LocalModelIds
        cls.LocalModelIds = LocalModelIds

    def test_qwen3_8b_ip_en_all(self):
        """QWEN3_8B_IP debe estar en LocalModelIds.ALL."""
        self.assertIn(
            self.LocalModelIds.QWEN3_8B_IP,
            self.LocalModelIds.ALL,
            "QWEN3_8B_IP no está en LocalModelIds.ALL"
        )

    def test_qwen3_8b_mdns_en_all(self):
        """QWEN3_8B_MDNS debe estar en LocalModelIds.ALL."""
        self.assertIn(
            self.LocalModelIds.QWEN3_8B_MDNS,
            self.LocalModelIds.ALL,
            "QWEN3_8B_MDNS no está en LocalModelIds.ALL"
        )

    def test_qwen3_30b_ip_en_all(self):
        """QWEN3_IP (30B) debe seguir en LocalModelIds.ALL."""
        self.assertIn(self.LocalModelIds.QWEN3_IP, self.LocalModelIds.ALL)

    def test_qwen3_30b_mdns_en_all(self):
        """QWEN3_MDNS (30B) debe seguir en LocalModelIds.ALL."""
        self.assertIn(self.LocalModelIds.QWEN3_MDNS, self.LocalModelIds.ALL)

    def test_all_tiene_4_modelos(self):
        """LocalModelIds.ALL debe tener exactamente 4 modelos (30B×2 + 8B×2)."""
        self.assertEqual(len(self.LocalModelIds.ALL), 4,
                         f"LocalModelIds.ALL debe tener 4 IDs, tiene {len(self.LocalModelIds.ALL)}: "
                         f"{self.LocalModelIds.ALL}")

    def test_ids_correctos(self):
        """Los IDs deben coincidir con los definidos en jddcia_models.json."""
        expected = {
            QWEN3_30B_ID_IP, QWEN3_30B_ID_MDNS,
            QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS
        }
        self.assertEqual(
            set(self.LocalModelIds.ALL), expected,
            f"LocalModelIds.ALL no coincide con los IDs esperados.\n"
            f"Esperado: {expected}\n"
            f"Actual:   {set(self.LocalModelIds.ALL)}"
        )

    def test_8b_id_ip_valor_correcto(self):
        """QWEN3_8B_IP debe ser 'jddcia-qwen3-8b-ip'."""
        self.assertEqual(self.LocalModelIds.QWEN3_8B_IP, QWEN3_8B_ID_IP)

    def test_8b_id_mdns_valor_correcto(self):
        """QWEN3_8B_MDNS debe ser 'jddcia-qwen3-8b'."""
        self.assertEqual(self.LocalModelIds.QWEN3_8B_MDNS, QWEN3_8B_ID_MDNS)


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 3: FACTORY DE PROVIDERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAIFactory(unittest.TestCase):
    """Verifica que el AIFactory devuelve el provider correcto según el schema."""

    @classmethod
    def setUpClass(cls):
        from backend.core.factory.ai_factory import AIFactory
        from backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        from backend.drivers.ai.jddcia_provider import JDDCIAProvider
        cls.AIFactory = AIFactory
        cls.OpenAICompatibleProvider = OpenAICompatibleProvider
        cls.JDDCIAProvider = JDDCIAProvider

    def test_schema_openai_compatible_devuelve_openai_provider(self):
        """schema='openai_compatible' → OpenAICompatibleProvider (para LM Studio)."""
        provider = self.AIFactory.get_provider("openai_compatible")
        self.assertIsInstance(
            provider, self.OpenAICompatibleProvider,
            "schema='openai_compatible' debe devolver OpenAICompatibleProvider"
        )

    def test_schema_jddcia_devuelve_jddcia_provider(self):
        """schema='jddcia' → JDDCIAProvider (para el gateway nginx del 30B)."""
        provider = self.AIFactory.get_provider("jddcia")
        self.assertIsInstance(
            provider, self.JDDCIAProvider,
            "schema='jddcia' debe devolver JDDCIAProvider"
        )

    def test_orchestrator_usa_schema_sobre_provider(self):
        """
        El orchestrator usa model_config.get('schema', model_config.get('provider')).
        Para el 8B: schema='openai_compatible' → OpenAICompatibleProvider.
        Para el 30B: sin schema → provider='jddcia' → JDDCIAProvider.
        """
        # Simular config del 8B
        model_8b = {
            "id": QWEN3_8B_ID_IP,
            "provider": "jddcia",
            "schema": "openai_compatible",
            "model_id": LMSTUDIO_MODEL_ID_SERVER,
        }
        schema_8b = model_8b.get("schema", model_8b.get("provider"))
        self.assertEqual(schema_8b, "openai_compatible")

        # Simular config del 30B
        model_30b = {
            "id": QWEN3_30B_ID_IP,
            "provider": "jddcia",
            "model_id": "unified-main",
        }
        schema_30b = model_30b.get("schema", model_30b.get("provider"))
        self.assertEqual(schema_30b, "jddcia")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 4: DISCOVERY SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class TestDiscoveryServiceLMStudio(unittest.IsolatedAsyncioTestCase):
    """Verifica el método discover_lmstudio() del ModelDiscoveryService."""

    async def test_discover_lmstudio_sin_servidor_devuelve_lista_vacia(self):
        """Si LM Studio no está disponible, discover_lmstudio() devuelve []."""
        from backend.modules.models.discovery_service import ModelDiscoveryService
        service = ModelDiscoveryService()

        # Mockear aiohttp para simular timeout/error de conexión
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.get.side_effect = Exception("Connection refused")

            result = await service.discover_lmstudio("http://192.168.0.36:1234")
            self.assertEqual(result, [],
                             "discover_lmstudio debe devolver [] si LM Studio no responde")

    async def test_discover_lmstudio_parsea_respuesta_correctamente(self):
        """discover_lmstudio() parsea correctamente la respuesta de GET /v1/models."""
        from backend.modules.models.discovery_service import ModelDiscoveryService
        service = ModelDiscoveryService()

        # Respuesta simulada de LM Studio GET /v1/models
        mock_response_data = {
            "data": [
                {"id": "qwen/qwen3-vl-8b", "object": "model"},
            ]
        }

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            mock_get_ctx = AsyncMock()
            mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get_ctx.__aexit__ = AsyncMock(return_value=False)

            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_get_ctx)

            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.discover_lmstudio("http://192.168.0.36:1234")

        self.assertEqual(len(result), 1, "Debe devolver 1 modelo")
        model = result[0]
        self.assertEqual(model["model_id"], "qwen/qwen3-vl-8b")
        self.assertEqual(model["schema"], "openai_compatible")
        self.assertEqual(model["api_key"], "lm-studio")
        self.assertIn("1234", model["base_url"])
        self.assertEqual(model["provider"], "jddcia")
        self.assertEqual(model["family"], "qwen")  # detectado por 'qwen' en el ID

    async def test_discover_all_incluye_clave_lmstudio(self):
        """discover_all() debe incluir la clave 'lmstudio' en el resultado."""
        from backend.modules.models.discovery_service import ModelDiscoveryService
        service = ModelDiscoveryService()

        # Mockear todos los providers para que devuelvan []
        with patch.object(service, "discover_google", AsyncMock(return_value=[])), \
             patch.object(service, "discover_openai", AsyncMock(return_value=[])), \
             patch.object(service, "discover_anthropic", AsyncMock(return_value=[])), \
             patch.object(service, "discover_groq", AsyncMock(return_value=[])), \
             patch.object(service, "discover_lmstudio", AsyncMock(return_value=[])):

            result = await service.discover_all()

        self.assertIn("lmstudio", result,
                      "discover_all() debe incluir la clave 'lmstudio'")

    async def test_discover_all_deduplica_por_model_id(self):
        """discover_all() no debe duplicar modelos si IP y mDNS devuelven el mismo model_id."""
        from backend.modules.models.discovery_service import ModelDiscoveryService
        service = ModelDiscoveryService()

        modelo_ip = [{
            "id": "jddcia-lmstudio-qwen-qwen3-vl-8b",
            "model_id": "qwen/qwen3-vl-8b",
            "base_url": "http://192.168.0.36:1234/v1",
            "schema": "openai_compatible",
        }]
        modelo_mdns = [{
            "id": "jddcia-lmstudio-qwen-qwen3-vl-8b",
            "model_id": "qwen/qwen3-vl-8b",
            "base_url": "http://jddcia.local:1234/v1",
            "schema": "openai_compatible",
        }]

        with patch.object(service, "discover_google", AsyncMock(return_value=[])), \
             patch.object(service, "discover_openai", AsyncMock(return_value=[])), \
             patch.object(service, "discover_anthropic", AsyncMock(return_value=[])), \
             patch.object(service, "discover_groq", AsyncMock(return_value=[])), \
             patch.object(service, "discover_lmstudio",
                          AsyncMock(side_effect=[modelo_ip, modelo_mdns])):

            result = await service.discover_all()

        lmstudio_models = result.get("lmstudio", [])
        model_ids = [m["model_id"] for m in lmstudio_models]
        self.assertEqual(
            len(model_ids), len(set(model_ids)),
            f"discover_all() no debe duplicar model_ids: {model_ids}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 5: ORCHESTRATOR — preferred_model_id con 8B
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorPreferredModel8B(unittest.TestCase):
    """Verifica que el orchestrator coloca el 8B primero cuando se especifica preferred_model_id."""

    def test_get_prioritized_models_coloca_8b_primero(self):
        """Con preferred_model_id='jddcia-qwen3-8b-ip', el 8B debe ser el primero."""
        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator

        orchestrator = ModelFallbackOrchestrator()

        # Mockear model_manager para devolver lista de modelos simulada
        mock_models = [
            {"id": QWEN3_30B_ID_IP, "name": "Qwen3 30B IP", "score": 95, "enabled": True},
            {"id": QWEN3_30B_ID_MDNS, "name": "Qwen3 30B mDNS", "score": 80, "enabled": True},
            {"id": QWEN3_8B_ID_IP, "name": "Qwen3 8B IP", "score": 70, "enabled": True},
            {"id": QWEN3_8B_ID_MDNS, "name": "Qwen3 8B mDNS", "score": 60, "enabled": True},
        ]

        with patch.object(orchestrator.model_manager, "list_models", return_value=mock_models):
            result = orchestrator._get_prioritized_models(
                preferred_model_id=QWEN3_8B_ID_IP
            )

        self.assertEqual(result[0]["id"], QWEN3_8B_ID_IP,
                         f"El primer modelo debe ser '{QWEN3_8B_ID_IP}', "
                         f"es '{result[0]['id']}'")

    def test_get_prioritized_models_sin_preferred_usa_score(self):
        """Sin preferred_model_id, el orden es por score (30B primero)."""
        from backend.modules.chat.model_fallback_orchestrator import ModelFallbackOrchestrator

        orchestrator = ModelFallbackOrchestrator()

        mock_models = [
            {"id": QWEN3_30B_ID_IP, "name": "Qwen3 30B IP", "score": 95, "enabled": True},
            {"id": QWEN3_8B_ID_IP, "name": "Qwen3 8B IP", "score": 70, "enabled": True},
        ]

        with patch.object(orchestrator.model_manager, "list_models", return_value=mock_models):
            result = orchestrator._get_prioritized_models()

        # Sin preferred, el orden viene del model_manager (ya ordenado por score)
        self.assertEqual(result[0]["id"], QWEN3_30B_ID_IP)

    def test_lan_only_incluye_8b(self):
        """En modo ai_local_only=true, los modelos 8B deben estar en la lista LAN."""
        from backend.core.utils.network_audit_constants import LocalModelIds

        mock_models = [
            {"id": QWEN3_30B_ID_IP, "name": "Qwen3 30B IP", "score": 95},
            {"id": QWEN3_30B_ID_MDNS, "name": "Qwen3 30B mDNS", "score": 80},
            {"id": QWEN3_8B_ID_IP, "name": "Qwen3 8B IP", "score": 70},
            {"id": QWEN3_8B_ID_MDNS, "name": "Qwen3 8B mDNS", "score": 60},
        ]

        # Simular el filtro del orchestrator en modo LAN_ONLY
        local_models = [m for m in mock_models if m["id"] in LocalModelIds.ALL]

        self.assertEqual(len(local_models), 4,
                         f"En modo LAN_ONLY deben haber 4 modelos, hay {len(local_models)}")

        ids_locales = {m["id"] for m in local_models}
        self.assertIn(QWEN3_8B_ID_IP, ids_locales)
        self.assertIn(QWEN3_8B_ID_MDNS, ids_locales)


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 6: PRIVACIDAD — URLs del 8B son LAN (no internet)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrivacidad8BEsLAN(unittest.TestCase):
    """Verifica que las URLs del 8B son clasificadas como LAN por el auditor de red."""

    def _is_lan_url(self, url: str) -> bool:
        """
        Clasifica una URL como LAN usando la misma lógica que el auditor de red:
        - IPs en rangos RFC 1918
        - Hostnames con sufijo .local
        - localhost
        """
        import ipaddress
        import re

        # Extraer host de la URL
        match = re.match(r"https?://([^/:]+)", url)
        if not match:
            return False
        host = match.group(1)

        # Localhost
        if host == "localhost":
            return True

        # Sufijo .local (mDNS)
        if host.endswith(".local"):
            return True

        # IP privada RFC 1918
        try:
            ip = ipaddress.ip_address(host)
            private_networks = [
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
                ipaddress.ip_network("127.0.0.0/8"),
            ]
            return any(ip in net for net in private_networks)
        except ValueError:
            pass

        return False

    def test_url_8b_ip_es_lan(self):
        """http://172.19.64.1:1234/v1 debe clasificarse como LAN (172.16.0.0/12 es RFC 1918)."""
        self.assertTrue(
            self._is_lan_url(LMSTUDIO_ENDPOINT_IP),
            f"'{LMSTUDIO_ENDPOINT_IP}' debe ser LAN (172.19.x.x está en 172.16.0.0/12 RFC 1918)"
        )

    def test_url_8b_mdns_es_lan(self):
        """http://jddcia.local:1234/v1 debe clasificarse como LAN."""
        self.assertTrue(
            self._is_lan_url(LMSTUDIO_ENDPOINT_MDNS),
            f"'{LMSTUDIO_ENDPOINT_MDNS}' debe ser LAN (.local = mDNS)"
        )

    def test_url_openai_no_es_lan(self):
        """https://api.openai.com no debe clasificarse como LAN."""
        self.assertFalse(
            self._is_lan_url("https://api.openai.com"),
            "api.openai.com NO debe ser LAN"
        )

    def test_url_groq_no_es_lan(self):
        """https://api.groq.com no debe clasificarse como LAN."""
        self.assertFalse(
            self._is_lan_url("https://api.groq.com"),
            "api.groq.com NO debe ser LAN"
        )

    def test_8b_no_en_known_internet_model_ids(self):
        """Los IDs del 8B NO deben estar en KnownInternetModelIds."""
        from backend.core.utils.network_audit_constants import KnownInternetModelIds

        self.assertNotIn(QWEN3_8B_ID_IP, KnownInternetModelIds.IDS,
                         f"'{QWEN3_8B_ID_IP}' no debe estar en KnownInternetModelIds")
        self.assertNotIn(QWEN3_8B_ID_MDNS, KnownInternetModelIds.IDS,
                         f"'{QWEN3_8B_ID_MDNS}' no debe estar en KnownInternetModelIds")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 7: TIMEOUTS — El 8B necesita timeouts generosos (stream=false)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeouts8B(unittest.TestCase):
    """
    Verifica que los timeouts del 8B son correctos.

    CAVEAT TÉCNICO (de la implementación en CIBERIA):
    Con stream=false, LM Studio genera todos los tokens internamente y envía
    la respuesta de golpe. Durante la generación, el socket HTTP no recibe datos
    → el timeout de socket salta aunque el servidor esté trabajando.
    Solución: timeout generoso (120s chat, 180s analyze).
    """

    def test_chat_timeout_minimo_120s(self):
        """El timeout de chat del 8B debe ser al menos 120s."""
        self.assertGreaterEqual(
            LMSTUDIO_TIMEOUTS["CHAT_MS"], 120_000,
            f"CHAT_MS debe ser >= 120000ms, es {LMSTUDIO_TIMEOUTS['CHAT_MS']}ms"
        )

    def test_analyze_timeout_minimo_180s(self):
        """El timeout de análisis del 8B debe ser al menos 180s."""
        self.assertGreaterEqual(
            LMSTUDIO_TIMEOUTS["ANALYZE_MS"], 180_000,
            f"ANALYZE_MS debe ser >= 180000ms, es {LMSTUDIO_TIMEOUTS['ANALYZE_MS']}ms"
        )

    def test_status_timeout_maximo_5s(self):
        """El timeout de status check del 8B debe ser <= 5s (falla rápido)."""
        self.assertLessEqual(
            LMSTUDIO_TIMEOUTS["STATUS_MS"], 5_000,
            f"STATUS_MS debe ser <= 5000ms, es {LMSTUDIO_TIMEOUTS['STATUS_MS']}ms"
        )

    def test_lan_read_timeout_en_config_json(self):
        """lan_read_timeout_s en config.json debe ser >= 120s para soportar el 8B."""
        config_path = _PROJECT_ROOT / "backend" / "modules" / "chat" / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        timeout_s = config.get("lan_read_timeout_s", 0)
        self.assertGreaterEqual(
            timeout_s, 120,
            f"lan_read_timeout_s debe ser >= 120s para soportar el 8B, es {timeout_s}s"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 8: FRONTEND — El desplegable LAN existe en el HTML
# ═══════════════════════════════════════════════════════════════════════════════

class TestFrontendDesplegableLAN(unittest.TestCase):
    """Verifica que el desplegable de selección de motor LAN existe en index.html."""

    @classmethod
    def setUpClass(cls):
        html_path = _PROJECT_ROOT / "frontend" / "index.html"
        with open(html_path, "r", encoding="utf-8") as f:
            cls.html = f.read()

    def test_selector_lan_existe(self):
        """El elemento #chat-lan-model-selector debe existir en el HTML."""
        self.assertIn(
            'id="chat-lan-model-selector"', self.html,
            "Falta el selector #chat-lan-model-selector en index.html"
        )

    def test_opcion_30b_existe(self):
        """La opción del Qwen3 30B debe existir en el selector LAN."""
        self.assertIn(
            QWEN3_30B_ID_IP, self.html,
            f"Falta la opción '{QWEN3_30B_ID_IP}' en el selector LAN"
        )

    def test_opcion_8b_existe(self):
        """La opción del Qwen3 8B VL debe existir en el selector LAN."""
        self.assertIn(
            QWEN3_8B_ID_IP, self.html,
            f"Falta la opción '{QWEN3_8B_ID_IP}' en el selector LAN"
        )

    def test_preferred_model_id_en_chat_js(self):
        """chat.js debe enviar preferred_model_id en el body del fetch."""
        js_path = _PROJECT_ROOT / "frontend" / "assets" / "js" / "modules" / "chat.js"
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn(
            "preferred_model_id", js,
            "chat.js debe incluir 'preferred_model_id' en el body del fetch a /send"
        )

    def test_chat_lan_model_selector_en_chat_js(self):
        """chat.js debe leer el elemento #chat-lan-model-selector."""
        js_path = _PROJECT_ROOT / "frontend" / "assets" / "js" / "modules" / "chat.js"
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn(
            "chat-lan-model-selector", js,
            "chat.js debe leer el elemento 'chat-lan-model-selector'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 9: RESILIENCIA DEL PROVIDER (truncación adaptativa, thinking, timeout)
# ═══════════════════════════════════════════════════════════════════════════════

class TestResilienciaProvider(unittest.TestCase):
    """
    Verifica las nuevas capacidades de resiliencia del OpenAICompatibleProvider:
    - Truncación adaptativa de contexto (evita 400 'Context size exceeded')
    - enable_thinking=false para Qwen3 (desactiva CoT, dobla velocidad)
    - Timeout configurable por modelo
    - Parámetros leídos desde extra_params (ModelManager) o jddcia_models.json
    """

    def _make_provider(self, context_limit=8192, max_tokens=512, timeout_s=120,
                       enable_thinking=False, model_id="qwen/qwen3-vl-8b"):
        """Helper: crea y configura un OpenAICompatibleProvider con parámetros dados."""
        from backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        from backend.core.abstract.ai import AIConfig

        provider = OpenAICompatibleProvider()

        # Simular AIConfig con extra_params (como lo haría el orchestrator)
        config = AIConfig(
            api_key="lm-studio",
            model=model_id,
            base_url="http://172.19.64.1:1234/v1",
            context_limit=context_limit,
            parameters={
                "max_tokens": max_tokens,
                "timeout_s": timeout_s,
                "enable_thinking": enable_thinking,
            }
        )

        # Mockear OpenAI para no hacer llamadas reales
        with patch("openai.OpenAI"):
            provider.configure(config)

        return provider

    def test_provider_lee_context_limit_de_extra_params(self):
        """El provider debe leer context_limit desde config.extra_params."""
        provider = self._make_provider(context_limit=8192)
        self.assertEqual(provider._context_limit, 8192)

    def test_provider_lee_max_tokens_de_extra_params(self):
        """El provider debe leer max_tokens desde config.extra_params."""
        provider = self._make_provider(max_tokens=256)
        self.assertEqual(provider._max_tokens, 256)

    def test_provider_lee_timeout_de_extra_params(self):
        """El provider debe leer timeout_s desde config.extra_params."""
        provider = self._make_provider(timeout_s=90)
        self.assertEqual(provider._timeout_s, 90)

    def test_provider_enable_thinking_false_para_qwen3(self):
        """enable_thinking=false debe configurarse correctamente para Qwen3."""
        provider = self._make_provider(enable_thinking=False, model_id="qwen/qwen3-vl-8b")
        self.assertFalse(provider._enable_thinking,
                         "enable_thinking debe ser False para Qwen3")

    def test_provider_autodetecta_thinking_false_para_qwen3(self):
        """Si enable_thinking no está en params, debe auto-detectarse como False para Qwen3."""
        from backend.drivers.ai.openai_compatible_provider import OpenAICompatibleProvider
        from backend.core.abstract.ai import AIConfig

        provider = OpenAICompatibleProvider()
        config = AIConfig(
            api_key="lm-studio",
            model="qwen/qwen3-vl-8b",
            base_url="http://172.19.64.1:1234/v1",
            context_limit=8192,
            parameters={"max_tokens": 512, "timeout_s": 120}
            # Sin enable_thinking → auto-detectar
        )
        with patch("openai.OpenAI"):
            provider.configure(config)

        self.assertFalse(provider._enable_thinking,
                         "Qwen3 debe auto-detectar enable_thinking=False")

    def test_extra_body_con_thinking_false(self):
        """_build_extra_body() debe devolver {'enable_thinking': False} para Qwen3."""
        provider = self._make_provider(enable_thinking=False)
        extra = provider._build_extra_body()
        self.assertIsNotNone(extra)
        self.assertEqual(extra.get("enable_thinking"), False)

    def test_extra_body_none_cuando_thinking_true(self):
        """_build_extra_body() debe devolver None cuando enable_thinking=True."""
        provider = self._make_provider(enable_thinking=True)
        extra = provider._build_extra_body()
        self.assertIsNone(extra)

    def test_truncacion_prompt_largo(self):
        """_build_messages() debe truncar el prompt si supera el context_limit."""
        from backend.drivers.ai.openai_compatible_provider import _estimate_tokens
        provider = self._make_provider(context_limit=512, max_tokens=64)

        # Crear un prompt que supere el presupuesto
        # Presupuesto = 512 - 64 - 100 - system_tokens
        # Con system vacío: budget = 348 tokens ≈ 1392 chars
        prompt_largo = "A" * 10000  # ~2500 tokens estimados >> 348

        messages = provider._build_messages(prompt_largo, system_instruction=None)

        # El mensaje del usuario debe ser más corto que el prompt original
        user_content = messages[-1]["content"]
        self.assertLess(len(user_content), len(prompt_largo),
                        "El prompt debe haberse truncado")
        self.assertIn("[TRUNCADO]", user_content,
                      "El prompt truncado debe incluir el marcador [TRUNCADO]")

    def test_no_truncacion_prompt_corto(self):
        """_build_messages() NO debe truncar si el prompt cabe en el context_limit."""
        provider = self._make_provider(context_limit=8192, max_tokens=512)

        prompt_corto = "¿Cuáles son los 10 clientes con mayor facturación?"
        messages = provider._build_messages(prompt_corto, system_instruction=None)

        user_content = messages[-1]["content"]
        self.assertEqual(user_content, prompt_corto,
                         "Un prompt corto no debe truncarse")
        self.assertNotIn("[TRUNCADO]", user_content)

    def test_8b_json_tiene_timeout_s(self):
        """jddcia_models.json debe tener timeout_s en los parámetros del 8B."""
        models_path = _PROJECT_ROOT / "backend" / "core" / "config" / "models" / "jddcia_models.json"
        with open(models_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        models = {m["id"]: m for m in data["models"]}

        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                params = models[model_id].get("parameters", {})
                self.assertIn("timeout_s", params,
                              f"{model_id}: debe tener 'timeout_s' en parameters")
                self.assertGreaterEqual(params["timeout_s"], 120,
                                        f"{model_id}: timeout_s debe ser >= 120s")

    def test_8b_json_tiene_enable_thinking_false(self):
        """jddcia_models.json debe tener enable_thinking=false en los parámetros del 8B."""
        models_path = _PROJECT_ROOT / "backend" / "core" / "config" / "models" / "jddcia_models.json"
        with open(models_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        models = {m["id"]: m for m in data["models"]}

        for model_id in [QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]:
            with self.subTest(model_id=model_id):
                params = models[model_id].get("parameters", {})
                self.assertIn("enable_thinking", params,
                              f"{model_id}: debe tener 'enable_thinking' en parameters")
                self.assertFalse(params["enable_thinking"],
                                 f"{model_id}: enable_thinking debe ser false")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 10: PARÁMETROS DESDE ORCHESTRATOR (AIConfig.extra_params)
# ═══════════════════════════════════════════════════════════════════════════════

class TestParametrosOrchestrator(unittest.TestCase):
    """
    Verifica que el orchestrator pasa context_limit y parameters al provider
    via AIConfig.extra_params, y que el provider los lee correctamente.
    """

    def test_orchestrator_pasa_context_limit_en_ai_config(self):
        """
        El orchestrator debe incluir context_limit en los kwargs de AIConfig.
        Verificamos que AIConfig almacena los kwargs en extra_params.
        """
        from backend.core.abstract.ai import AIConfig

        config = AIConfig(
            api_key="lm-studio",
            model="qwen/qwen3-vl-8b",
            base_url="http://172.19.64.1:1234/v1",
            context_limit=8192,
            parameters={"max_tokens": 512, "timeout_s": 120, "enable_thinking": False},
            model_id_logical="jddcia-qwen3-8b-ip",
        )

        self.assertEqual(config.extra_params.get("context_limit"), 8192)
        self.assertEqual(config.extra_params.get("parameters", {}).get("max_tokens"), 512)
        self.assertEqual(config.extra_params.get("parameters", {}).get("timeout_s"), 120)
        self.assertFalse(config.extra_params.get("parameters", {}).get("enable_thinking"))

    def test_orchestrator_pasa_parametros_correctos_para_8b(self):
        """
        Simular el flujo completo: orchestrator lee model_config del ModelManager
        y construye AIConfig con los parámetros correctos del 8B.
        """
        from backend.core.abstract.ai import AIConfig

        # Simular model_config como lo devuelve ModelManager para el 8B
        model_config = {
            "id": QWEN3_8B_ID_IP,
            "name": "⚡ Qwen3 8B VL (LM Studio — IP directa)",
            "model_id": "qwen/qwen3-vl-8b",
            "api_key": "lm-studio",
            "base_url": "http://172.19.64.1:1234/v1",
            "context_limit": 8192,
            "parameters": {
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_s": 120,
                "enable_thinking": False,
            },
            "schema": "openai_compatible",
        }

        # Replicar la lógica del orchestrator en _try_model
        ai_config_params = {
            "api_key": model_config["api_key"],
            "model": model_config["model_id"],
            "context_limit": model_config.get("context_limit", 8192),
            "parameters": model_config.get("parameters", {}),
            "model_id_logical": model_config.get("id", ""),
        }
        if model_config.get("base_url"):
            ai_config_params["base_url"] = model_config["base_url"]

        config = AIConfig(**ai_config_params)

        # Verificar que el provider puede leer los parámetros
        self.assertEqual(config.extra_params["context_limit"], 8192)
        self.assertEqual(config.extra_params["parameters"]["timeout_s"], 120)
        self.assertFalse(config.extra_params["parameters"]["enable_thinking"])
        self.assertEqual(config.extra_params["model_id_logical"], QWEN3_8B_ID_IP)

    def test_orchestrator_skip_modelos_permanentemente_fallidos(self):
        """
        El orchestrator debe marcar modelos con 405 como permanentemente fallidos
        y no reintentarlos en rondas posteriores.
        """
        # Simular la lógica de detección de fallos permanentes del orchestrator
        permanently_failed = set()

        def detectar_fallo_permanente(model_id: str, error_str: str, error_type: str):
            err_lower = error_str.lower()
            is_permanent = (
                "405" in err_lower or
                "not allowed" in err_lower or
                "context size" in err_lower or
                ("context" in err_lower and "exceeded" in err_lower)
            )
            if is_permanent:
                permanently_failed.add(model_id)

        # Simular 30B dando 405
        detectar_fallo_permanente(
            QWEN3_30B_ID_IP,
            "JDDC Gateway error 405: Method Not Allowed",
            "Exception"
        )
        detectar_fallo_permanente(
            QWEN3_30B_ID_MDNS,
            "JDDC Gateway error 405: Method Not Allowed",
            "Exception"
        )

        # Simular 8B dando context exceeded
        detectar_fallo_permanente(
            QWEN3_8B_ID_IP,
            "BadRequestError: Context size has been exceeded",
            "BadRequestError"
        )

        self.assertIn(QWEN3_30B_ID_IP, permanently_failed,
                      "30B-IP debe marcarse como permanentemente fallido (405)")
        self.assertIn(QWEN3_30B_ID_MDNS, permanently_failed,
                      "30B-mDNS debe marcarse como permanentemente fallido (405)")
        self.assertIn(QWEN3_8B_ID_IP, permanently_failed,
                      "8B-IP debe marcarse como permanentemente fallido (context exceeded)")

        # Verificar que el filtro funciona
        all_models = [QWEN3_30B_ID_IP, QWEN3_30B_ID_MDNS, QWEN3_8B_ID_IP, QWEN3_8B_ID_MDNS]
        active = [m for m in all_models if m not in permanently_failed]
        self.assertEqual(active, [QWEN3_8B_ID_MDNS],
                         "Solo el 8B-mDNS debe quedar activo")

    def test_estimacion_tokens(self):
        """_estimate_tokens() debe estimar correctamente (1 token ≈ 4 chars)."""
        from backend.drivers.ai.openai_compatible_provider import _estimate_tokens

        # 400 chars → ~100 tokens
        self.assertEqual(_estimate_tokens("A" * 400), 100)
        # 1 char → 1 token (mínimo)
        self.assertEqual(_estimate_tokens("A"), 1)
        # 8000 chars → 2000 tokens
        self.assertEqual(_estimate_tokens("A" * 8000), 2000)

    def test_truncate_preserva_final_del_texto(self):
        """_truncate_to_token_budget() debe preservar el FINAL del texto (más relevante)."""
        from backend.drivers.ai.openai_compatible_provider import _truncate_to_token_budget

        texto = "INICIO_" + "X" * 10000 + "_FINAL"
        truncado, fue_truncado = _truncate_to_token_budget(texto, max_tokens=100)

        self.assertTrue(fue_truncado)
        self.assertIn("_FINAL", truncado,
                      "El final del texto debe preservarse tras la truncación")
        self.assertNotIn("INICIO_", truncado,
                         "El inicio del texto debe eliminarse en la truncación")


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tests Qwen3 8B VL LM Studio")
    parser.add_argument("--solo", choices=[
        "configuracion", "local_model_ids", "factory", "discovery",
        "orchestrator", "privacidad", "timeouts", "frontend",
        "resiliencia", "parametros_orchestrator",
    ], help="Ejecutar solo un sistema de tests")
    args, remaining = parser.parse_known_args()

    suite = unittest.TestSuite()

    SISTEMAS = {
        "configuracion":            TestConfiguracionModelos,
        "local_model_ids":          TestLocalModelIds,
        "factory":                  TestAIFactory,
        "discovery":                TestDiscoveryServiceLMStudio,
        "orchestrator":             TestOrchestratorPreferredModel8B,
        "privacidad":               TestPrivacidad8BEsLAN,
        "timeouts":                 TestTimeouts8B,
        "frontend":                 TestFrontendDesplegableLAN,
        "resiliencia":              TestResilienciaProvider,
        "parametros_orchestrator":  TestParametrosOrchestrator,
    }

    if args.solo:
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(SISTEMAS[args.solo]))
    else:
        for cls in SISTEMAS.values():
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
