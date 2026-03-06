"""
Tests del módulo Metadata Builder.

EJECUTAR:
  cd bots/interjddcia
  .venv/Scripts/pytest tests/test_metadata_builder.py -v

COBERTURA:
  - constants.py: valores y tipos correctos
  - firebird_metadata_queries.py: SQL sintácticamente válido
  - metadata_builder_service.py: lógica de negocio (con mocks)
  - metadata_builder_router.py: endpoints HTTP (con TestClient)

PRINCIPIO: Tests unitarios con mocks — no requieren BD ni IA disponibles.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ─── Tests de constants.py ────────────────────────────────────────────────────

class TestConstants:
    """Verifica que las constantes tienen los tipos y valores esperados."""

    def test_local_ai_timeouts_are_positive(self):
        from backend.modules.db_explorer.constants import LocalAITimeouts
        assert LocalAITimeouts.CONNECT > 0
        assert LocalAITimeouts.READ > LocalAITimeouts.CONNECT

    def test_local_ai_params_defaults(self):
        from backend.modules.db_explorer.constants import LocalAIParams
        assert LocalAIParams.MAX_TOKENS > 0
        assert 0.0 <= LocalAIParams.TEMPERATURE <= 1.0
        assert LocalAIParams.MODEL_DEFAULT  # No vacío

    def test_privacy_sensitive_columns_is_frozenset(self):
        from backend.modules.db_explorer.constants import PrivacyConfig
        assert isinstance(PrivacyConfig.SENSITIVE_COLUMNS, frozenset)
        # Columnas críticas siempre presentes
        for col in ("NIF", "IBAN", "PASSWORD", "EMAIL"):
            assert col in PrivacyConfig.SENSITIVE_COLUMNS

    def test_privacy_sample_limits(self):
        from backend.modules.db_explorer.constants import PrivacyConfig
        assert PrivacyConfig.MAX_SAMPLE_ROWS > 0
        assert PrivacyConfig.MAX_SAMPLE_COLS > 0

    def test_processing_limits_positive(self):
        from backend.modules.db_explorer.constants import ProcessingLimits
        assert ProcessingLimits.MAX_COLUMNS_IN_PROMPT > 0
        assert ProcessingLimits.MAX_DESCRIPTION_CHARS > 0
        assert ProcessingLimits.MAX_COLUMN_DESC_CHARS > 0

    def test_table_category_all_is_list(self):
        from backend.modules.db_explorer.constants import TableCategory
        assert isinstance(TableCategory.ALL, list)
        assert len(TableCategory.ALL) > 0
        assert TableCategory.PRODUCTOS in TableCategory.ALL

    def test_log_prefixes_contain_module_name(self):
        from backend.modules.db_explorer.constants import MetadataBuilderLog
        for attr in ("MODULE", "CHECK_AI", "GET_TABLES", "GET_STRUCT", "ANALYZE_AI", "SAVE"):
            val = getattr(MetadataBuilderLog, attr)
            assert "METADATA_BUILDER" in val

    def test_messages_have_format_placeholders(self):
        from backend.modules.db_explorer.constants import MetadataBuilderMessages
        # Verificar que los mensajes con placeholders se pueden formatear
        msg = MetadataBuilderMessages.AI_NOT_AVAILABLE.format(url="http://test")
        assert "http://test" in msg
        msg2 = MetadataBuilderMessages.METADATA_SAVED.format(table="ARTICULO")
        assert "ARTICULO" in msg2


# ─── Tests de firebird_metadata_queries.py ───────────────────────────────────

class TestFirebirdMetadataQueries:
    """Verifica que las queries SQL tienen la estructura correcta."""

    def test_query_user_tables_selects_from_rdb(self):
        from backend.drivers.db.firebird_metadata_queries import QUERY_USER_TABLES
        assert "RDB$RELATIONS" in QUERY_USER_TABLES
        assert "RDB$SYSTEM_FLAG" in QUERY_USER_TABLES
        assert "TABLE_NAME" in QUERY_USER_TABLES

    def test_query_columns_typed_uses_parameter(self):
        from backend.drivers.db.firebird_metadata_queries import QUERY_TABLE_COLUMNS_TYPED
        assert "?" in QUERY_TABLE_COLUMNS_TYPED
        assert "FIELD_NAME" in QUERY_TABLE_COLUMNS_TYPED
        assert "FIELD_TYPE" in QUERY_TABLE_COLUMNS_TYPED

    def test_query_primary_keys_uses_parameter(self):
        from backend.drivers.db.firebird_metadata_queries import QUERY_TABLE_PRIMARY_KEYS
        assert "?" in QUERY_TABLE_PRIMARY_KEYS
        assert "PRIMARY KEY" in QUERY_TABLE_PRIMARY_KEYS

    def test_query_foreign_keys_uses_parameter(self):
        from backend.drivers.db.firebird_metadata_queries import QUERY_TABLE_FOREIGN_KEYS
        assert "?" in QUERY_TABLE_FOREIGN_KEYS
        assert "FOREIGN KEY" in QUERY_TABLE_FOREIGN_KEYS

    def test_count_template_has_placeholder(self):
        from backend.drivers.db.firebird_metadata_queries import QUERY_COUNT_TEMPLATE
        assert "{table_name}" in QUERY_COUNT_TEMPLATE
        # Verificar que se puede formatear
        q = QUERY_COUNT_TEMPLATE.format(table_name="ARTICULO")
        assert "ARTICULO" in q

    def test_sample_template_uses_first_not_limit(self):
        from backend.drivers.db.firebird_metadata_queries import QUERY_SAMPLE_TEMPLATE
        assert "FIRST" in QUERY_SAMPLE_TEMPLATE
        assert "LIMIT" not in QUERY_SAMPLE_TEMPLATE
        q = QUERY_SAMPLE_TEMPLATE.format(n=3, cols="CODIGO, NOMBRE", table_name="ARTICULO")
        assert "FIRST 3" in q
        assert "ARTICULO" in q


# ─── Tests de metadata_builder_service.py ────────────────────────────────────

class TestMetadataBuilderService:
    """Tests unitarios del servicio con mocks (sin BD ni IA reales)."""

    def _make_service(self):
        """Crea una instancia del servicio con settings mockeados."""
        with patch("backend.modules.db_explorer.metadata_builder_service.settings") as mock_settings:
            mock_settings.DB_HOST     = "localhost"
            mock_settings.DB_PORT     = 3050
            mock_settings.DB_NAME     = "test.fdb"
            mock_settings.DB_USER     = "SYSDBA"
            mock_settings.DB_PASSWORD = "masterkey"
            mock_settings.JDDCIA_BASE_URL_FALLBACK = "http://192.168.0.36/api/vlm/v1"
            mock_settings.JDDCIA_BASE_URL          = "http://jddcia.local/api/vlm/v1"
            mock_settings.JDDCIA_API_KEY           = "dGVzdA=="
            from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService
            return MetadataBuilderService()

    def test_service_initializes_ai_urls_from_settings(self):
        """Las URLs de la IA vienen de settings, no hardcodeadas."""
        with patch("backend.modules.db_explorer.metadata_builder_service.settings") as ms:
            ms.DB_HOST = "localhost"; ms.DB_PORT = 3050
            ms.DB_NAME = "test.fdb"; ms.DB_USER = "SYSDBA"; ms.DB_PASSWORD = "mk"
            ms.JDDCIA_BASE_URL_FALLBACK = "http://10.0.0.1/api/vlm/v1"
            ms.JDDCIA_BASE_URL          = "http://myai.local/api/vlm/v1"
            ms.JDDCIA_API_KEY           = "abc123"
            from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService
            svc = MetadataBuilderService()
            assert "http://10.0.0.1/api/vlm/v1" in svc._ai_urls
            assert "http://myai.local/api/vlm/v1" in svc._ai_urls
            assert "Basic abc123" == svc._ai_auth

    def test_validate_table_name_accepts_valid(self):
        from backend.modules.db_explorer.metadata_builder_service import _validate_table_name
        assert _validate_table_name("ARTICULO")
        assert _validate_table_name("DOCCAB")
        assert _validate_table_name("RDB$RELATIONS")  # Firebird system tables

    def test_validate_table_name_rejects_injection(self):
        from backend.modules.db_explorer.metadata_builder_service import _validate_table_name
        assert not _validate_table_name("ARTICULO; DROP TABLE")
        assert not _validate_table_name("../etc/passwd")
        assert not _validate_table_name("")

    def test_parse_json_response_clean_json(self):
        from backend.modules.db_explorer.metadata_builder_service import _parse_json_response
        raw = '{"category": "productos", "description": "test"}'
        result = _parse_json_response(raw)
        assert result["category"] == "productos"

    def test_parse_json_response_with_markdown(self):
        from backend.modules.db_explorer.metadata_builder_service import _parse_json_response
        raw = '```json\n{"category": "ventas"}\n```'
        result = _parse_json_response(raw)
        assert result["category"] == "ventas"

    def test_parse_json_response_with_extra_text(self):
        from backend.modules.db_explorer.metadata_builder_service import _parse_json_response
        raw = 'Aquí está el JSON:\n{"category": "clientes"}\nEspero que ayude.'
        result = _parse_json_response(raw)
        assert result["category"] == "clientes"

    def test_parse_json_response_raises_on_invalid(self):
        from backend.modules.db_explorer.metadata_builder_service import _parse_json_response
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("esto no es json")

    @pytest.mark.asyncio
    async def test_check_local_ai_returns_unavailable_when_server_down(self):
        """Si la IA no responde, devuelve available=False (no lanza excepción)."""
        import httpx
        with patch("backend.modules.db_explorer.metadata_builder_service.settings") as ms:
            ms.DB_HOST = "localhost"; ms.DB_PORT = 3050
            ms.DB_NAME = "test.fdb"; ms.DB_USER = "SYSDBA"; ms.DB_PASSWORD = "mk"
            ms.JDDCIA_BASE_URL_FALLBACK = "http://192.168.0.99/api/vlm/v1"
            ms.JDDCIA_BASE_URL          = "http://192.168.0.99/api/vlm/v1"
            ms.JDDCIA_API_KEY           = "test"
            from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService
            svc = MetadataBuilderService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await svc.check_local_ai()

        assert result["available"] is False
        assert "error" in result

    def test_get_table_structure_rejects_invalid_name(self):
        """Nombres de tabla inválidos se rechazan antes de consultar la BD."""
        with patch("backend.modules.db_explorer.metadata_builder_service.settings") as ms:
            ms.DB_HOST = "localhost"; ms.DB_PORT = 3050
            ms.DB_NAME = "test.fdb"; ms.DB_USER = "SYSDBA"; ms.DB_PASSWORD = "mk"
            ms.JDDCIA_BASE_URL_FALLBACK = "http://x/v1"
            ms.JDDCIA_BASE_URL = "http://x/v1"
            ms.JDDCIA_API_KEY = "x"
            from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService
            svc = MetadataBuilderService()

        result = svc.get_table_structure("'; DROP TABLE ARTICULO; --")
        assert result["success"] is False
        assert "inválido" in result["error"].lower()

    def test_save_metadata_persists_to_json(self):
        """save_table_metadata llama a metadata_manager.save_metadata."""
        with patch("backend.modules.db_explorer.metadata_builder_service.settings") as ms:
            ms.DB_HOST = "localhost"; ms.DB_PORT = 3050
            ms.DB_NAME = "test.fdb"; ms.DB_USER = "SYSDBA"; ms.DB_PASSWORD = "mk"
            ms.JDDCIA_BASE_URL_FALLBACK = "http://x/v1"
            ms.JDDCIA_BASE_URL = "http://x/v1"
            ms.JDDCIA_API_KEY = "x"
            with patch("backend.modules.db_explorer.metadata_builder_service.get_metadata_manager") as mock_mm:
                mock_mgr = MagicMock()
                mock_mgr.metadata = {"tables": {}}
                mock_mm.return_value = mock_mgr
                from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService
                svc = MetadataBuilderService()

        meta = {"category": "productos", "description": "test", "columns": {}}
        result = svc.save_table_metadata("ARTICULO", meta)

        assert result["success"] is True
        mock_mgr.save_metadata.assert_called_once()

    def test_delete_metadata_returns_error_if_not_exists(self):
        with patch("backend.modules.db_explorer.metadata_builder_service.settings") as ms:
            ms.DB_HOST = "localhost"; ms.DB_PORT = 3050
            ms.DB_NAME = "test.fdb"; ms.DB_USER = "SYSDBA"; ms.DB_PASSWORD = "mk"
            ms.JDDCIA_BASE_URL_FALLBACK = "http://x/v1"
            ms.JDDCIA_BASE_URL = "http://x/v1"
            ms.JDDCIA_API_KEY = "x"
            with patch("backend.modules.db_explorer.metadata_builder_service.get_metadata_manager") as mock_mm:
                mock_mgr = MagicMock()
                mock_mgr.metadata = {"tables": {}}
                mock_mm.return_value = mock_mgr
                from backend.modules.db_explorer.metadata_builder_service import MetadataBuilderService
                svc = MetadataBuilderService()

        result = svc.delete_table_metadata("TABLA_INEXISTENTE")
        assert result["success"] is False


# ─── Tests de metadata_builder_router.py ─────────────────────────────────────

class TestMetadataBuilderRouter:
    """Tests de integración de los endpoints HTTP con TestClient."""

    def _get_client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.modules.db_explorer.metadata_builder_router import router
        app = FastAPI()
        app.include_router(router, prefix="/api/metadata-builder")
        return TestClient(app)

    def test_get_tables_returns_200_with_mock(self):
        with patch(
            "backend.modules.db_explorer.metadata_builder_router._service"
        ) as mock_svc:
            mock_svc.get_all_tables.return_value = {
                "success": True, "tables": [], "total": 0, "with_metadata": 0
            }
            client = self._get_client()
            resp = client.get("/api/metadata-builder/tables")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_get_tables_returns_500_on_error(self):
        with patch(
            "backend.modules.db_explorer.metadata_builder_router._service"
        ) as mock_svc:
            mock_svc.get_all_tables.return_value = {
                "success": False, "error": "Connection failed"
            }
            client = self._get_client()
            resp = client.get("/api/metadata-builder/tables")
        assert resp.status_code == 500

    def test_get_structure_returns_404_on_invalid_table(self):
        with patch(
            "backend.modules.db_explorer.metadata_builder_router._service"
        ) as mock_svc:
            mock_svc.get_table_structure.return_value = {
                "success": False, "error": "Nombre de tabla inválido"
            }
            client = self._get_client()
            resp = client.get("/api/metadata-builder/tables/INVALID_TABLE")
        assert resp.status_code == 404

    def test_save_metadata_requires_metadata_field(self):
        with patch(
            "backend.modules.db_explorer.metadata_builder_router._service"
        ) as mock_svc:
            mock_svc.save_table_metadata.return_value = {
                "success": True, "message": "OK", "total_tables": 1
            }
            client = self._get_client()
            # Sin campo metadata → 422 Unprocessable Entity
            resp = client.post("/api/metadata-builder/tables/ARTICULO/save", json={})
        assert resp.status_code == 422

    def test_save_metadata_with_valid_payload(self):
        with patch(
            "backend.modules.db_explorer.metadata_builder_router._service"
        ) as mock_svc:
            mock_svc.save_table_metadata.return_value = {
                "success": True,
                "message": "Metadatos de ARTICULO guardados correctamente.",
                "total_tables": 8,
            }
            client = self._get_client()
            resp = client.post(
                "/api/metadata-builder/tables/ARTICULO/save",
                json={"metadata": {"category": "productos", "description": "test"}},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_metadata_returns_404_if_not_exists(self):
        with patch(
            "backend.modules.db_explorer.metadata_builder_router._service"
        ) as mock_svc:
            mock_svc.delete_table_metadata.return_value = {
                "success": False, "error": "La tabla 'X' no tiene metadatos registrados."
            }
            client = self._get_client()
            resp = client.delete("/api/metadata-builder/tables/X/metadata")
        assert resp.status_code == 404
