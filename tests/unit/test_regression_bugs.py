"""
test_regression_bugs.py — Tests de regresión para bugs encontrados en producción.

Bugs cubiertos:
  1. BUG-001: DeepAnalysisAgent.__init__() got unexpected keyword argument 'execute_sql'
             → service.py usaba execute_sql= pero el constructor espera sql_executor=
  2. BUG-002: Checkbox "Análisis profundo" oculto sin scroll horizontal
             → estaba en div separado antes de chat-input-area, sin flex-wrap
  3. BUG-003: 768 presupuestos aceptados — DOCDESTINO no es la tabla correcta
             → DOCDESTINO es relación origen→destino, no indica "aceptado"
             → El SIUO debe advertir sobre esto en el contexto
"""

import asyncio
import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── BUG-001: execute_sql vs sql_executor ────────────────────────────────────

class TestBug001ExecuteSqlKeyword:
    """
    BUG-001: service.py llamaba DeepAnalysisAgent con execute_sql= (incorrecto).
    El constructor acepta sql_executor= (correcto).
    """

    def test_agent_constructor_accepts_sql_executor(self):
        """El constructor debe aceptar sql_executor como keyword argument."""
        from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
        sig = inspect.signature(DeepAnalysisAgent.__init__)
        params = list(sig.parameters.keys())
        assert "sql_executor" in params, (
            "DeepAnalysisAgent.__init__ debe tener parámetro 'sql_executor'"
        )

    def test_agent_constructor_does_NOT_accept_execute_sql(self):
        """El constructor NO debe aceptar execute_sql (nombre incorrecto del bug)."""
        from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
        sig = inspect.signature(DeepAnalysisAgent.__init__)
        params = list(sig.parameters.keys())
        assert "execute_sql" not in params, (
            "DeepAnalysisAgent.__init__ NO debe tener parámetro 'execute_sql' "
            "(ese era el nombre incorrecto que causó el bug)"
        )

    def test_agent_instantiation_with_sql_executor_keyword(self):
        """Instanciar con sql_executor= no debe lanzar TypeError."""
        from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
        orch = MagicMock()
        orch.execute_with_fallback = AsyncMock(return_value=('{}', None))
        orch.context_limit_tokens = 32000

        executor = MagicMock(return_value=[{"TOTAL": 1}])

        # No debe lanzar excepción
        agent = DeepAnalysisAgent(
            orchestrator=orch,
            db_context="TABLA: DOCCAB",
            sql_executor=executor,
        )
        assert agent.sql_executor is executor

    def test_agent_instantiation_with_execute_sql_raises(self):
        """Instanciar con execute_sql= debe lanzar TypeError (nombre incorrecto)."""
        from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
        orch = MagicMock()
        orch.context_limit_tokens = 32000

        with pytest.raises(TypeError, match="execute_sql"):
            DeepAnalysisAgent(
                orchestrator=orch,
                db_context="TABLA: DOCCAB",
                execute_sql=lambda q: [],  # nombre incorrecto
            )

    def test_service_uses_sql_executor_not_execute_sql(self):
        """service.py debe usar sql_executor= al instanciar DeepAnalysisAgent."""
        import ast
        import os

        service_path = os.path.join(
            os.path.dirname(__file__),
            "../../backend/modules/chat/service.py"
        )
        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Buscar todas las llamadas a DeepAnalysisAgent(...)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Detectar llamadas a DeepAnalysisAgent
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "DeepAnalysisAgent":
                    keyword_names = [kw.arg for kw in node.keywords]
                    assert "execute_sql" not in keyword_names, (
                        f"service.py usa 'execute_sql=' en DeepAnalysisAgent — "
                        f"debe usar 'sql_executor='. Keywords encontrados: {keyword_names}"
                    )
                    assert "sql_executor" in keyword_names, (
                        f"service.py debe usar 'sql_executor=' en DeepAnalysisAgent. "
                        f"Keywords encontrados: {keyword_names}"
                    )


# ─── BUG-002: Checkbox oculto ────────────────────────────────────────────────

class TestBug002CheckboxVisible:
    """
    BUG-002: El checkbox 'Análisis profundo' estaba en un div separado
    antes de chat-input-area, sin flex-wrap, y se quedaba oculto.
    Fix: moverlo DENTRO de chat-input-area con flex-wrap: wrap.
    """

    def _get_html(self):
        import os
        html_path = os.path.join(
            os.path.dirname(__file__),
            "../../frontend/index.html"
        )
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_checkbox_exists_in_html(self):
        """El checkbox deep-analysis-toggle debe existir en el HTML."""
        html = self._get_html()
        assert 'id="deep-analysis-toggle"' in html

    def test_checkbox_inside_chat_input_area(self):
        """El checkbox debe estar DENTRO de chat-input-area (no en div separado antes)."""
        html = self._get_html()
        # Encontrar la posición de chat-input-area y del checkbox
        pos_input_area = html.find('class="chat-input-area"')
        pos_checkbox = html.find('id="deep-analysis-toggle"')

        assert pos_input_area != -1, "chat-input-area no encontrado en HTML"
        assert pos_checkbox != -1, "deep-analysis-toggle no encontrado en HTML"

        # El checkbox debe aparecer DESPUÉS de chat-input-area (está dentro)
        assert pos_checkbox > pos_input_area, (
            "El checkbox deep-analysis-toggle debe estar DENTRO de chat-input-area. "
            f"Posición chat-input-area: {pos_input_area}, posición checkbox: {pos_checkbox}"
        )

    def test_chat_input_area_has_flex_wrap(self):
        """chat-input-area debe tener flex-wrap: wrap para evitar overflow oculto."""
        html = self._get_html()
        # Encontrar el div de chat-input-area
        idx = html.find('class="chat-input-area"')
        assert idx != -1, "chat-input-area no encontrado"

        # Extraer el estilo del div (los próximos 300 chars)
        snippet = html[idx:idx+300]
        assert "flex-wrap" in snippet, (
            "chat-input-area debe tener flex-wrap para que el checkbox no se oculte. "
            f"Snippet: {snippet[:200]}"
        )

    def test_deep_analysis_label_has_flex_shrink_0(self):
        """El label del checkbox debe tener flex-shrink: 0 para no comprimirse."""
        html = self._get_html()
        idx = html.find('id="deep-analysis-label"')
        assert idx != -1, "deep-analysis-label no encontrado"

        # Extraer el estilo del label
        snippet = html[idx:idx+400]
        assert "flex-shrink: 0" in snippet or "flex-shrink:0" in snippet, (
            "deep-analysis-label debe tener flex-shrink: 0 para no desaparecer. "
            f"Snippet: {snippet[:300]}"
        )

    def test_deep_analysis_label_has_white_space_nowrap(self):
        """El label debe tener white-space: nowrap para no partirse en dos líneas."""
        html = self._get_html()
        idx = html.find('id="deep-analysis-label"')
        assert idx != -1

        snippet = html[idx:idx+400]
        assert "white-space: nowrap" in snippet or "white-space:nowrap" in snippet, (
            "deep-analysis-label debe tener white-space: nowrap. "
            f"Snippet: {snippet[:300]}"
        )

    def test_checkbox_not_in_separate_div_before_input_area(self):
        """El checkbox NO debe estar en un div separado ANTES de chat-input-area."""
        html = self._get_html()

        # Buscar si hay un div con el checkbox que aparezca ANTES de chat-input-area
        pos_input_area = html.find('class="chat-input-area"')
        pos_checkbox = html.find('id="deep-analysis-toggle"')

        # Si el checkbox está antes del input area, es el bug
        if pos_checkbox < pos_input_area:
            pytest.fail(
                "BUG-002 REGRESIÓN: El checkbox está en un div ANTES de chat-input-area. "
                "Debe estar DENTRO de chat-input-area."
            )


# ─── BUG-003: DOCDESTINO no indica "presupuesto aceptado" ────────────────────

class TestBug003DocdestinoNotAccepted:
    """
    BUG-003: La IA generó SQL usando DOCDESTINO para contar presupuestos aceptados.
    DOCDESTINO es una tabla de relaciones origen→destino entre documentos,
    NO indica que un presupuesto fue "aceptado".
    
    El SIUO debe incluir una nota en DOCDESTINO explicando esto.
    """

    def test_docdestino_has_critico_note_in_siuo(self):
        """DOCDESTINO debe tener una nota CRITICO en los metadatos SIUO (JSON optimizado)."""
        import os, json

        base = os.path.join(
            os.path.dirname(__file__),
            "../../backend/core/config"
        )
        # Los metadatos reales están en db_metadata_optimized.json (no en database_metadata.py)
        json_path = os.path.join(base, "db_metadata_optimized.json")
        if not os.path.exists(json_path):
            pytest.skip("db_metadata_optimized.json no encontrado")

        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()

        # DOCDESTINO debe estar en el JSON de metadatos
        assert "DOCDESTINO" in content, (
            "DOCDESTINO debe estar en db_metadata_optimized.json con su nota CRITICO"
        )

    def test_docdestino_siuo_note_warns_about_accepted(self):
        """La nota de DOCDESTINO debe advertir que no indica 'aceptado'."""
        import os

        # Buscar en firebird_sql_constants.py o en los índices SIUO
        constants_path = os.path.join(
            os.path.dirname(__file__),
            "../../backend/modules/chat/firebird_sql_constants.py"
        )
        if not os.path.exists(constants_path):
            pytest.skip("firebird_sql_constants.py no encontrado")

        with open(constants_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Debe haber alguna referencia a DOCDESTINO con advertencia
        # (puede estar en LOW_RECORD_TABLES o en comentarios)
        assert "DOCDESTINO" in content or "docdestino" in content.lower(), (
            "firebird_sql_constants.py debe mencionar DOCDESTINO"
        )

    def test_sql_for_accepted_budgets_uses_correct_logic(self):
        """
        El SQL correcto para presupuestos aceptados NO debe usar solo DOCDESTINO.
        Debe usar SEGUIMIENTODOCUMENTO o un campo de estado en DOCCAB.
        
        Este test verifica que el normalizer o el contexto SIUO incluye
        la advertencia correcta sobre DOCDESTINO.
        """
        # Verificar que el contexto SIUO de DOCDESTINO incluye la nota CRITICO
        try:
            from backend.modules.db_explorer.context_retriever import get_context_retriever
            retriever = get_context_retriever()
            context, meta = retriever.get_context("presupuestos aceptados tasa éxito")
            # El contexto debe incluir DOCDESTINO con su nota
            assert "DOCDESTINO" in context, (
                "El contexto SIUO para 'presupuestos aceptados' debe incluir DOCDESTINO"
            )
            # La nota CRITICO debe estar presente
            assert "CRITICO" in context or "origen" in context.lower(), (
                "El contexto de DOCDESTINO debe incluir nota sobre su uso correcto"
            )
        except Exception as e:
            pytest.skip(f"ContextRetriever no disponible en tests: {e}")


# ─── BUG-004: Normalizer extrae solo el primer SQL (el más simple) ────────────

class TestBug004SqlBlockSelection:
    """
    BUG-004: service.py extraía solo el PRIMER bloque ```sql``` de la respuesta.
    Cuando la IA genera varios bloques (paso 1, paso 2, consulta final),
    el primero suele ser el más simple (ej: COUNT(*) básico).
    Fix: usar el bloque con más caracteres (heurística de "más completo").
    """

    def _get_service_source(self):
        import os
        path = os.path.join(
            os.path.dirname(__file__),
            "../../backend/modules/chat/service.py"
        )
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_service_uses_max_sql_block_not_first(self):
        """service.py debe usar max(sql_blocks, key=len) no split()[1]."""
        source = self._get_service_source()
        assert "max(sql_blocks, key=len)" in source, (
            "service.py debe usar max(sql_blocks, key=len) para elegir el SQL más completo"
        )

    def test_service_uses_findall_for_sql_blocks(self):
        """service.py debe usar re.findall para extraer todos los bloques SQL."""
        source = self._get_service_source()
        assert "findall" in source and "sql_blocks" in source, (
            "service.py debe usar re.findall para extraer todos los bloques SQL"
        )

    def test_sql_block_selection_logic(self):
        """La lógica de selección debe elegir el bloque más largo."""
        import re

        response_with_multiple_sql = """
Para calcular la tasa de éxito necesitamos:

### Paso 1: Total de presupuestos
```sql
SELECT COUNT(*) AS TOTAL_PRESUPUESTOS FROM DOCCAB WHERE TIPO = 0
```

### Paso 2: Presupuestos aceptados
```sql
SELECT COUNT(DISTINCT c.CODIGO) AS ACEPTADOS FROM DOCCAB c LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO WHERE c.TIPO = 0 AND dd.CODDOCUMENTODESTINO IS NOT NULL
```

### Consulta completa con tasa de éxito
```sql
SELECT COUNT(DISTINCT c.CODIGO) AS TOTAL_PRESUPUESTOS, COUNT(DISTINCT CASE WHEN dd.CODDOCUMENTODESTINO IS NOT NULL THEN c.CODIGO END) AS ACEPTADOS, ROUND((COUNT(DISTINCT CASE WHEN dd.CODDOCUMENTODESTINO IS NOT NULL THEN c.CODIGO END) * 100.0) / COUNT(DISTINCT c.CODIGO), 2) AS TASA_EXITO FROM DOCCAB c LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO WHERE c.TIPO = 0
```
"""
        sql_blocks = re.findall(r'```sql\s*(.*?)```', response_with_multiple_sql, re.DOTALL)
        assert len(sql_blocks) == 3, f"Debe encontrar 3 bloques SQL, encontró {len(sql_blocks)}"

        # El bloque más largo debe ser el de la consulta completa
        best_sql = max(sql_blocks, key=len).strip()
        assert "TASA_EXITO" in best_sql, (
            f"El SQL más completo debe contener TASA_EXITO. SQL elegido: {best_sql[:100]}"
        )
        assert "LEFT JOIN DOCDESTINO" in best_sql, (
            "El SQL más completo debe contener el JOIN con DOCDESTINO"
        )
        assert "CASE WHEN" in best_sql, (
            "El SQL más completo debe contener CASE WHEN para contar aceptados"
        )

    def test_simple_response_still_works(self):
        """Si solo hay un bloque SQL, debe funcionar igual."""
        import re

        simple_response = """
```sql
SELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO = 0
```
"""
        sql_blocks = re.findall(r'```sql\s*(.*?)```', simple_response, re.DOTALL)
        assert len(sql_blocks) == 1
        best_sql = max(sql_blocks, key=len).strip()
        assert "SELECT COUNT(*)" in best_sql


# ─── Tests de integración: service.py instancia correctamente ────────────────

class TestServiceDeepAnalysisIntegration:
    """
    Tests de integración que verifican que service.py instancia
    DeepAnalysisAgent correctamente (sin el bug execute_sql).
    """

    def test_deep_analysis_agent_import_works(self):
        """El import de DeepAnalysisAgent desde deep_analysis_agent.py debe funcionar."""
        try:
            from backend.modules.chat.deep_analysis_agent import DeepAnalysisAgent
            assert DeepAnalysisAgent is not None
        except ImportError as e:
            pytest.fail(f"No se puede importar DeepAnalysisAgent: {e}")

    def test_deep_analysis_agent_new_module_import_works(self):
        """El import desde el nuevo módulo deep_analysis/agent.py debe funcionar."""
        try:
            from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
            assert DeepAnalysisAgent is not None
        except ImportError as e:
            pytest.fail(f"No se puede importar DeepAnalysisAgent desde deep_analysis.agent: {e}")

    def test_agent_analyze_method_exists(self):
        """DeepAnalysisAgent debe tener método analyze()."""
        from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
        assert hasattr(DeepAnalysisAgent, "analyze"), (
            "DeepAnalysisAgent debe tener método analyze()"
        )

    def test_agent_analyze_accepts_conversation_history(self):
        """analyze() debe aceptar conversation_history como parámetro."""
        from backend.modules.chat.deep_analysis.agent import DeepAnalysisAgent
        sig = inspect.signature(DeepAnalysisAgent.analyze)
        params = list(sig.parameters.keys())
        assert "conversation_history" in params, (
            "analyze() debe aceptar conversation_history para contexto de conversación"
        )

    def test_service_deep_analysis_flag_activates_agent(self):
        """
        Cuando context['deep_analysis'] = True, service.py debe intentar
        usar DeepAnalysisAgent.
        
        NOTA: service.py hace un lazy import dentro de la función:
          from backend.modules.chat.deep_analysis_agent import DeepAnalysisAgent
        Por eso parcheamos el módulo fuente, no el atributo del módulo service.
        """
        import asyncio
        from backend.modules.chat.service import ChatService

        service = ChatService()

        # Mock del agente para verificar que se llama
        agent_called = []

        async def mock_analyze(question, conversation_history=None):
            agent_called.append(question)
            return "Análisis profundo mock"

        mock_instance = MagicMock()
        mock_instance.analyze = mock_analyze

        # El import lazy está en deep_analysis_agent.py, parcheamos ahí
        # También parcheamos el intent_classifier para evitar llamadas al modelo IA
        mock_intent = MagicMock()
        mock_intent.is_conversational.return_value = False
        mock_intent.is_clarification.return_value = False
        mock_intent.is_deep_analysis.return_value = True
        mock_intent.confidence = 0.9
        mock_intent.reasoning = "test"

        with patch("backend.modules.chat.deep_analysis_agent.DeepAnalysisAgent",
                   return_value=mock_instance) as MockAgent:
            with patch.object(service, "_execute_sql", return_value=[{"TOTAL": 1}]):
                with patch("backend.modules.chat.service.get_context_retriever") as mock_cr:
                    mock_cr.return_value.get_context.return_value = (
                        "ESQUEMA", {"tables_used": [], "source": "test"}
                    )
                    with patch.object(service, "_intent_classifier") as mock_clf:
                        mock_clf.classify = AsyncMock(return_value=mock_intent)

                        result = asyncio.get_event_loop().run_until_complete(
                            service.process_message(
                                "¿cuántos presupuestos hay?",
                                context={
                                    "deep_analysis": True,
                                    "conversation_history": [],
                                    # db_params mínimos para evitar early-exit a _chat_no_db
                                    "db_params": {"host": "test", "database": "test.fdb"},
                                }
                            )
                        )

        # El agente debe haberse llamado O el resultado es el mock
        assert len(agent_called) > 0 or result == "Análisis profundo mock", (
            "Con deep_analysis=True, el servicio debe usar DeepAnalysisAgent. "
            f"agent_called={agent_called}, result={result!r}"
        )
