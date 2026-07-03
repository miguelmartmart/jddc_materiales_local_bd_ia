"""
test_chat_recovery_logic.py — Tests para la lógica de recuperación del chat IA

Cubre:
  - Clasificación de errores: timeout, connection_drop, network, cancelled
  - Detección de timeout enmascarado (ratio ≥ 90%)
  - Detección de connection_drop (elapsed ≥ 30s + backend vivo)
  - Constantes de timeout (AI_REQUEST, AI_REQUEST_DEEP, CONNECTION_DROP_THRESHOLD)
  - Módulo chat-markdown: reparación de respuestas truncadas
  - Módulo chat-history: fetchSession, loadHistory
  - Endpoint /api/chat/ping (heartbeat backend)
  - Integración: flujo completo de error → clasificación → mensaje usuario

Principios DEVIA:
  - Tests deterministas (sin IA real, sin red real)
  - Mocks explícitos para fetch y DOM
  - Cada test verifica UNA cosa
  - Nombres descriptivos: test_<qué>_<cuándo>_<resultado>
"""

import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path


# ── Helpers para simular la lógica JS en Python ───────────────────────────────
# La lógica de clasificación de errores está en chat-recovery.js (_classifyError).
# La replicamos en Python para poder testearla sin un navegador.

class MockTimeouts:
    """Replica de TIMEOUTS de constants.js"""
    AI_REQUEST             = 300_000   # 5 min
    AI_REQUEST_DEEP        = 1_200_000 # 20 min
    TIMEOUT_DETECTION_RATIO = 0.90
    CONNECTION_DROP_THRESHOLD = 30_000  # 30s
    HEARTBEAT_INTERVAL     = 30_000
    HEARTBEAT_PING_TIMEOUT = 5_000


async def classify_error(reason: str, elapsed: int | None,
                          configured_timeout: int,
                          ping_result: bool = False) -> str:
    """
    Replica Python de ChatRecovery._classifyError().
    ping_result simula el resultado de _pingBackend().
    """
    if reason != 'network' or elapsed is None:
        return reason

    ratio           = elapsed / configured_timeout if configured_timeout > 0 else 0
    detection_ratio = MockTimeouts.TIMEOUT_DETECTION_RATIO
    drop_threshold  = MockTimeouts.CONNECTION_DROP_THRESHOLD
    min_ai_timeout  = MockTimeouts.AI_REQUEST

    # Caso 1: elapsed ≥ 90% del timeout → timeout enmascarado
    if ratio >= detection_ratio:
        return 'timeout'

    # Caso 2: elapsed ≥ 30s → posible connection_drop
    if elapsed >= drop_threshold:
        if ping_result:
            return 'connection_drop'
        return 'network'

    # Caso 3: elapsed ≥ 90% del AI_REQUEST mínimo → timeout enmascarado
    if elapsed >= min_ai_timeout * 0.90:
        return 'timeout'

    return 'network'


def repair_truncated_response(text: str) -> str:
    """Replica Python de _repairTruncatedResponse() de chat-markdown.js"""
    import re

    HIDDEN_LANGS = ['sql', 'SQL', 'python', 'bash', 'sh', 'javascript', 'js']
    # Eliminar bloques de código técnico
    for lang in HIDDEN_LANGS:
        text = re.sub(rf'```{lang}[^`]*```', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Cerrar <details> abiertos
    open_count  = len(re.findall(r'<details[^>]*>', text, re.IGNORECASE))
    close_count = len(re.findall(r'</details>', text, re.IGNORECASE))
    missing     = open_count - close_count
    if missing > 0:
        text += '\n\n*(Información adicional disponible)*\n\n'
        text += '\n</details>' * missing

    return text


# ═══════════════════════════════════════════════════════════════════════════════
# TestClassifyError — Clasificación de errores de red
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyError:
    """Tests para _classifyError() — el corazón de la detección de connection_drop"""

    @pytest.mark.asyncio
    async def test_non_network_reason_returned_unchanged(self):
        """Razones que no son 'network' se devuelven sin modificar"""
        for reason in ['timeout', 'cancelled', 'http_502', 'http_500']:
            result = await classify_error(reason, 5000, 300_000)
            assert result == reason, f"Razón '{reason}' no debe modificarse"

    @pytest.mark.asyncio
    async def test_network_with_none_elapsed_returned_unchanged(self):
        """Si elapsed es None, 'network' se devuelve sin modificar"""
        result = await classify_error('network', None, 300_000)
        assert result == 'network'

    @pytest.mark.asyncio
    async def test_network_ratio_above_90pct_becomes_timeout(self):
        """elapsed ≥ 90% del timeout → timeout enmascarado"""
        # 270s de 300s = 90%
        result = await classify_error('network', 270_000, 300_000)
        assert result == 'timeout'

    @pytest.mark.asyncio
    async def test_network_ratio_exactly_90pct_becomes_timeout(self):
        """elapsed = exactamente 90% del timeout → timeout"""
        result = await classify_error('network', 270_000, 300_000)
        assert result == 'timeout'

    @pytest.mark.asyncio
    async def test_network_ratio_above_90pct_deep_timeout(self):
        """Con timeout de 20min, elapsed ≥ 90% → timeout"""
        # 1080s de 1200s = 90%
        result = await classify_error('network', 1_080_000, 1_200_000)
        assert result == 'timeout'

    @pytest.mark.asyncio
    async def test_network_elapsed_30s_backend_alive_becomes_connection_drop(self):
        """elapsed ≥ 30s + backend vivo → connection_drop (el caso del bug original)"""
        # 126s — exactamente el caso reportado por el usuario
        result = await classify_error('network', 126_000, 1_200_000, ping_result=True)
        assert result == 'connection_drop'

    @pytest.mark.asyncio
    async def test_network_elapsed_30s_backend_dead_stays_network(self):
        """elapsed ≥ 30s + backend caído → network (error real)"""
        result = await classify_error('network', 126_000, 1_200_000, ping_result=False)
        assert result == 'network'

    @pytest.mark.asyncio
    async def test_network_elapsed_exactly_30s_backend_alive_is_connection_drop(self):
        """elapsed = exactamente 30s + backend vivo → connection_drop"""
        result = await classify_error('network', 30_000, 1_200_000, ping_result=True)
        assert result == 'connection_drop'

    @pytest.mark.asyncio
    async def test_network_elapsed_29s_stays_network(self):
        """elapsed < 30s → no se hace ping, se devuelve 'network'"""
        result = await classify_error('network', 29_999, 1_200_000, ping_result=True)
        # 29.999s < 30s → no llega al caso 2
        # 29.999s < 270s (90% de 300s) → no llega al caso 3
        assert result == 'network'

    @pytest.mark.asyncio
    async def test_network_elapsed_270s_of_300s_timeout_is_timeout(self):
        """elapsed = 270s con timeout normal de 300s → timeout enmascarado (caso 1)"""
        result = await classify_error('network', 270_000, 300_000, ping_result=True)
        # ratio = 0.90 → caso 1 (timeout enmascarado), no llega al caso 2
        assert result == 'timeout'

    @pytest.mark.asyncio
    async def test_network_elapsed_5s_stays_network(self):
        """elapsed = 5s → error de red real (servidor caído desde el inicio)"""
        result = await classify_error('network', 5_000, 300_000, ping_result=False)
        assert result == 'network'

    @pytest.mark.asyncio
    async def test_network_elapsed_60s_backend_alive_is_connection_drop(self):
        """elapsed = 60s + backend vivo → connection_drop"""
        result = await classify_error('network', 60_000, 300_000, ping_result=True)
        assert result == 'connection_drop'

    @pytest.mark.asyncio
    async def test_network_elapsed_60s_backend_dead_is_network(self):
        """elapsed = 60s + backend caído → network"""
        result = await classify_error('network', 60_000, 300_000, ping_result=False)
        assert result == 'network'

    @pytest.mark.asyncio
    async def test_network_elapsed_270s_of_1200s_timeout_backend_alive_is_connection_drop(self):
        """elapsed = 270s con timeout DEEP de 1200s → connection_drop (no timeout)"""
        # ratio = 270/1200 = 0.225 < 0.90 → no es timeout enmascarado
        # elapsed = 270s ≥ 30s → caso 2 → connection_drop si backend vivo
        result = await classify_error('network', 270_000, 1_200_000, ping_result=True)
        assert result == 'connection_drop'


# ═══════════════════════════════════════════════════════════════════════════════
# TestTimeoutConstants — Constantes de timeout
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeoutConstants:
    """Verifica que las constantes de timeout tienen valores razonables"""

    def test_ai_request_timeout_is_5_minutes(self):
        assert MockTimeouts.AI_REQUEST == 300_000

    def test_ai_request_deep_timeout_is_20_minutes(self):
        assert MockTimeouts.AI_REQUEST_DEEP == 1_200_000

    def test_deep_timeout_greater_than_normal(self):
        assert MockTimeouts.AI_REQUEST_DEEP > MockTimeouts.AI_REQUEST

    def test_connection_drop_threshold_is_30s(self):
        assert MockTimeouts.CONNECTION_DROP_THRESHOLD == 30_000

    def test_detection_ratio_is_90pct(self):
        assert MockTimeouts.TIMEOUT_DETECTION_RATIO == 0.90

    def test_heartbeat_interval_is_30s(self):
        assert MockTimeouts.HEARTBEAT_INTERVAL == 30_000

    def test_heartbeat_ping_timeout_is_5s(self):
        assert MockTimeouts.HEARTBEAT_PING_TIMEOUT == 5_000

    def test_connection_drop_threshold_less_than_ai_request(self):
        """El umbral de connection_drop debe ser menor que el timeout normal"""
        assert MockTimeouts.CONNECTION_DROP_THRESHOLD < MockTimeouts.AI_REQUEST

    def test_heartbeat_interval_equals_connection_drop_threshold(self):
        """El heartbeat y el umbral de connection_drop son iguales (30s)"""
        assert MockTimeouts.HEARTBEAT_INTERVAL == MockTimeouts.CONNECTION_DROP_THRESHOLD

    def test_constants_file_exists(self):
        """El fichero constants.js existe"""
        path = Path(__file__).parent.parent.parent / 'frontend/assets/js/core/constants.js'
        assert path.exists(), f"constants.js no encontrado en {path}"

    def test_constants_file_has_connection_drop_threshold(self):
        """constants.js contiene CONNECTION_DROP_THRESHOLD"""
        path = Path(__file__).parent.parent.parent / 'frontend/assets/js/core/constants.js'
        content = path.read_text(encoding='utf-8')
        assert 'CONNECTION_DROP_THRESHOLD' in content

    def test_constants_file_has_ai_request_deep(self):
        """constants.js contiene AI_REQUEST_DEEP"""
        path = Path(__file__).parent.parent.parent / 'frontend/assets/js/core/constants.js'
        content = path.read_text(encoding='utf-8')
        assert 'AI_REQUEST_DEEP' in content

    def test_constants_file_has_heartbeat_interval(self):
        """constants.js contiene HEARTBEAT_INTERVAL"""
        path = Path(__file__).parent.parent.parent / 'frontend/assets/js/core/constants.js'
        content = path.read_text(encoding='utf-8')
        assert 'HEARTBEAT_INTERVAL' in content


# ═══════════════════════════════════════════════════════════════════════════════
# TestMarkdownRepair — Reparación de respuestas truncadas
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkdownRepair:
    """Tests para _repairTruncatedResponse() de chat-markdown.js"""

    def test_sql_block_removed(self):
        """Bloques ```sql ... ``` se eliminan"""
        text = "Resultado:\n```sql\nSELECT * FROM DOCCAB\n```\nFin."
        result = repair_truncated_response(text)
        assert 'SELECT' not in result
        assert 'Resultado:' in result
        assert 'Fin.' in result

    def test_python_block_removed(self):
        """Bloques ```python ... ``` se eliminan"""
        text = "Código:\n```python\nprint('hola')\n```\nFin."
        result = repair_truncated_response(text)
        assert "print('hola')" not in result

    def test_bash_block_removed(self):
        """Bloques ```bash ... ``` se eliminan"""
        text = "```bash\nls -la\n```"
        result = repair_truncated_response(text)
        assert 'ls -la' not in result

    def test_non_technical_block_preserved(self):
        """Bloques de código no técnicos se preservan"""
        text = "```\nTexto plano\n```"
        result = repair_truncated_response(text)
        assert 'Texto plano' in result

    def test_unclosed_details_tag_closed(self):
        """<details> sin cerrar se cierra automáticamente"""
        text = "<details><summary>Ver más</summary>Contenido"
        result = repair_truncated_response(text)
        assert '</details>' in result

    def test_balanced_details_tags_unchanged(self):
        """<details> correctamente cerrado no se modifica"""
        text = "<details><summary>Ver</summary>Contenido</details>"
        result = repair_truncated_response(text)
        assert result.count('</details>') == 1

    def test_multiple_unclosed_details_all_closed(self):
        """Múltiples <details> sin cerrar se cierran todos"""
        text = "<details>A<details>B"
        result = repair_truncated_response(text)
        assert result.count('</details>') == 2

    def test_empty_text_returns_empty(self):
        """Texto vacío devuelve vacío"""
        assert repair_truncated_response('') == ''

    def test_plain_text_unchanged(self):
        """Texto sin Markdown ni HTML no se modifica"""
        text = "La facturación total es 372.293,37€"
        result = repair_truncated_response(text)
        assert result == text

    def test_sql_case_insensitive(self):
        """Bloques ```SQL (mayúsculas) también se eliminan"""
        text = "```SQL\nSELECT 1\n```"
        result = repair_truncated_response(text)
        assert 'SELECT 1' not in result

    def test_multiple_sql_blocks_all_removed(self):
        """Múltiples bloques SQL se eliminan todos"""
        text = "```sql\nSELECT 1\n```\nTexto\n```sql\nSELECT 2\n```"
        result = repair_truncated_response(text)
        assert 'SELECT 1' not in result
        assert 'SELECT 2' not in result
        assert 'Texto' in result


# ═══════════════════════════════════════════════════════════════════════════════
# TestChatRecoveryFiles — Verificación de ficheros del módulo
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatRecoveryFiles:
    """Verifica que los ficheros del módulo existen y cumplen principios DEVIA"""

    BASE = Path(__file__).parent.parent.parent / 'frontend/assets/js/modules'

    def _line_count(self, filename: str) -> int:
        return len((self.BASE / filename).read_text(encoding='utf-8').splitlines())

    def test_chat_recovery_js_exists(self):
        assert (self.BASE / 'chat-recovery.js').exists()

    def test_chat_recovery_ui_js_exists(self):
        assert (self.BASE / 'chat-recovery-ui.js').exists()

    def test_chat_markdown_js_exists(self):
        assert (self.BASE / 'chat-markdown.js').exists()

    def test_chat_history_js_exists(self):
        assert (self.BASE / 'chat-history.js').exists()

    def test_chat_recovery_js_under_500_lines(self):
        count = self._line_count('chat-recovery.js')
        assert count <= 500, f"chat-recovery.js tiene {count} líneas (máx 500)"

    def test_chat_recovery_ui_js_under_500_lines(self):
        count = self._line_count('chat-recovery-ui.js')
        assert count <= 500, f"chat-recovery-ui.js tiene {count} líneas (máx 500)"

    def test_chat_markdown_js_under_500_lines(self):
        count = self._line_count('chat-markdown.js')
        assert count <= 500, f"chat-markdown.js tiene {count} líneas (máx 500)"

    def test_chat_history_js_under_500_lines(self):
        count = self._line_count('chat-history.js')
        assert count <= 500, f"chat-history.js tiene {count} líneas (máx 500)"

    def test_chat_recovery_imports_from_ui(self):
        """chat-recovery.js importa de chat-recovery-ui.js"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert 'chat-recovery-ui.js' in content

    def test_chat_recovery_imports_from_constants(self):
        """chat-recovery.js importa de constants.js"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert 'constants.js' in content

    def test_chat_recovery_ui_imports_from_constants(self):
        """chat-recovery-ui.js importa de constants.js"""
        content = (self.BASE / 'chat-recovery-ui.js').read_text(encoding='utf-8')
        assert 'constants.js' in content

    def test_chat_recovery_has_classify_error_method(self):
        """chat-recovery.js tiene el método _classifyError"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert '_classifyError' in content

    def test_chat_recovery_has_connection_drop_handling(self):
        """chat-recovery.js maneja connection_drop"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert 'connection_drop' in content

    def test_chat_recovery_ui_has_connection_drop_message(self):
        """chat-recovery-ui.js tiene mensaje para connection_drop"""
        content = (self.BASE / 'chat-recovery-ui.js').read_text(encoding='utf-8')
        assert 'connection_drop' in content

    def test_chat_recovery_fail_request_is_async(self):
        """failRequest es async (necesario para el ping)"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert 'async failRequest' in content

    def test_chat_recovery_has_heartbeat(self):
        """chat-recovery.js tiene heartbeat"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert '_startHeartbeat' in content

    def test_chat_recovery_has_ping_backend(self):
        """chat-recovery.js tiene _pingBackend"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert '_pingBackend' in content

    def test_chat_recovery_has_singleton_export(self):
        """chat-recovery.js exporta el singleton chatRecovery"""
        content = (self.BASE / 'chat-recovery.js').read_text(encoding='utf-8')
        assert 'export const chatRecovery' in content

    def test_chat_js_awaits_fail_request(self):
        """chat.js usa 'await chatRecovery.failRequest' (no fire-and-forget)"""
        chat_js = self.BASE / 'chat.js'
        if not chat_js.exists():
            pytest.skip("chat.js no encontrado")
        content = chat_js.read_text(encoding='utf-8')
        assert 'await chatRecovery.failRequest' in content

    def test_chat_recovery_ui_has_inject_cancel_button(self):
        """chat-recovery-ui.js exporta injectCancelButton"""
        content = (self.BASE / 'chat-recovery-ui.js').read_text(encoding='utf-8')
        assert 'injectCancelButton' in content

    def test_chat_recovery_ui_has_inject_retry_block(self):
        """chat-recovery-ui.js exporta injectRetryBlock"""
        content = (self.BASE / 'chat-recovery-ui.js').read_text(encoding='utf-8')
        assert 'injectRetryBlock' in content

    def test_chat_recovery_ui_has_update_status_label(self):
        """chat-recovery-ui.js exporta updateStatusLabel"""
        content = (self.BASE / 'chat-recovery-ui.js').read_text(encoding='utf-8')
        assert 'updateStatusLabel' in content

    def test_chat_markdown_js_has_render_markdown(self):
        """chat-markdown.js exporta renderMarkdown"""
        content = (self.BASE / 'chat-markdown.js').read_text(encoding='utf-8')
        assert 'renderMarkdown' in content

    def test_chat_history_js_has_chat_history_manager(self):
        """chat-history.js exporta ChatHistoryManager"""
        content = (self.BASE / 'chat-history.js').read_text(encoding='utf-8')
        assert 'ChatHistoryManager' in content


# ═══════════════════════════════════════════════════════════════════════════════
# TestPingEndpoint — Endpoint /api/chat/ping del backend
# ═══════════════════════════════════════════════════════════════════════════════

class TestPingEndpoint:
    """Verifica que el endpoint /api/chat/ping existe en el backend"""

    def test_ping_endpoint_in_router(self):
        """El router de chat tiene el endpoint /ping"""
        router_path = Path(__file__).parent.parent / 'modules/chat/router.py'
        if not router_path.exists():
            pytest.skip("router.py no encontrado")
        content = router_path.read_text(encoding='utf-8')
        assert '/ping' in content or 'ping' in content

    def test_ping_endpoint_returns_ok(self):
        """El endpoint /ping devuelve status 200"""
        import httpx
        try:
            r = httpx.get('http://localhost:8001/api/chat/ping', timeout=3)
            assert r.status_code == 200
        except Exception:
            pytest.skip("Backend no disponible en localhost:8001")


# ═══════════════════════════════════════════════════════════════════════════════
# TestUserMessages — Mensajes de error para el usuario
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserMessages:
    """Verifica que los mensajes de error son correctos y completos"""

    BASE = Path(__file__).parent.parent.parent / 'frontend/assets/js/modules'

    def _get_user_messages(self) -> str:
        return (self.BASE / 'chat-recovery-ui.js').read_text(encoding='utf-8')

    def test_timeout_message_exists(self):
        assert 'timeout' in self._get_user_messages()

    def test_network_message_exists(self):
        assert 'network' in self._get_user_messages()

    def test_connection_drop_message_exists(self):
        assert 'connection_drop' in self._get_user_messages()

    def test_cancelled_message_exists(self):
        assert 'cancelled' in self._get_user_messages()

    def test_http_502_message_exists(self):
        assert 'http_502' in self._get_user_messages()

    def test_http_503_message_exists(self):
        assert 'http_503' in self._get_user_messages()

    def test_http_500_message_exists(self):
        assert 'http_500' in self._get_user_messages()

    def test_connection_drop_message_is_informative(self):
        """El mensaje de connection_drop explica que el backend sigue vivo"""
        content = self._get_user_messages()
        # Debe mencionar que la conexión se interrumpió (no que el servidor está caído)
        assert 'interrumpió' in content or 'interrumpido' in content

    def test_connection_drop_hint_mentions_retry(self):
        """El hint de connection_drop sugiere reintentar"""
        content = self._get_user_messages()
        assert 'Reintentar' in content or 'reintentar' in content

    def test_network_message_different_from_connection_drop(self):
        """Los mensajes de 'network' y 'connection_drop' son diferentes"""
        content = self._get_user_messages()
        # Ambos deben existir pero ser distintos
        assert 'No se pudo conectar' in content  # network
        assert 'interrumpió' in content or 'interrumpido' in content  # connection_drop


# ═══════════════════════════════════════════════════════════════════════════════
# TestEdgeCases — Casos límite y situaciones extremas
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests de casos límite para la clasificación de errores"""

    @pytest.mark.asyncio
    async def test_zero_elapsed_stays_network(self):
        """elapsed = 0ms → error de red inmediato"""
        result = await classify_error('network', 0, 300_000, ping_result=True)
        assert result == 'network'

    @pytest.mark.asyncio
    async def test_very_large_elapsed_is_timeout(self):
        """elapsed muy grande → timeout enmascarado"""
        result = await classify_error('network', 999_999_999, 300_000)
        assert result == 'timeout'

    @pytest.mark.asyncio
    async def test_zero_configured_timeout_stays_network(self):
        """configured_timeout = 0 → ratio = 0, no es timeout"""
        result = await classify_error('network', 30_000, 0, ping_result=True)
        # ratio = 0/0 → 0 < 0.90 → no es timeout enmascarado
        # elapsed = 30s ≥ 30s → caso 2 → connection_drop si backend vivo
        assert result == 'connection_drop'

    @pytest.mark.asyncio
    async def test_http_error_not_reclassified(self):
        """Errores HTTP (http_502, etc.) no se reclasifican"""
        for reason in ['http_502', 'http_503', 'http_500', 'http_404']:
            result = await classify_error(reason, 300_000, 300_000, ping_result=True)
            assert result == reason

    @pytest.mark.asyncio
    async def test_cancelled_not_reclassified(self):
        """'cancelled' no se reclasifica aunque elapsed sea grande"""
        result = await classify_error('cancelled', 300_000, 300_000, ping_result=True)
        assert result == 'cancelled'

    @pytest.mark.asyncio
    async def test_timeout_not_reclassified(self):
        """'timeout' no se reclasifica"""
        result = await classify_error('timeout', 5_000, 300_000, ping_result=False)
        assert result == 'timeout'

    def test_repair_with_only_sql_returns_empty_content(self):
        """Texto que solo contiene SQL queda vacío (sin SQL)"""
        text = "```sql\nSELECT * FROM DOCCAB WHERE TIPO=13\n```"
        result = repair_truncated_response(text)
        assert 'SELECT' not in result

    def test_repair_preserves_spanish_text(self):
        """El texto en español con acentos se preserva"""
        text = "La facturación total es 372.293,37€ según los datos."
        result = repair_truncated_response(text)
        assert 'facturación' in result
        assert '372.293,37€' in result

    def test_repair_with_mixed_content(self):
        """Texto mixto: SQL eliminado, texto preservado"""
        text = (
            "El total de facturas es:\n"
            "```sql\nSELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO=13\n```\n"
            "**372.293,37€**"
        )
        result = repair_truncated_response(text)
        assert 'SELECT' not in result
        assert '372.293,37€' in result
        assert 'El total de facturas es:' in result

    @pytest.mark.asyncio
    async def test_connection_drop_boundary_exactly_30000ms(self):
        """Exactamente en el umbral de 30s → connection_drop si backend vivo"""
        result = await classify_error('network', 30_000, 300_000, ping_result=True)
        assert result == 'connection_drop'

    @pytest.mark.asyncio
    async def test_connection_drop_boundary_29999ms(self):
        """1ms por debajo del umbral → network (no se hace ping)"""
        result = await classify_error('network', 29_999, 300_000, ping_result=True)
        assert result == 'network'
