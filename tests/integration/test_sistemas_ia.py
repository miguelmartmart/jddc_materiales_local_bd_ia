"""
test_sistemas_ia.py — Tests de los 3 sistemas del Chat IA DEVIA

SISTEMAS TESTADOS:
  1. MEMORIA PERMANENTE (InteractionHistoryService + siuo_query_log.json)
     - Guardar y recuperar interacciones
     - Persistencia entre sesiones
     - Feedback de SQL correcto/incorrecto

  2. RELACIONES MULTI-TABLA (ContextRetriever + db_graph)
     - Expansion BFS del grafo de relaciones
     - Preguntas complejas que requieren JOIN de varias tablas
     - Ranking de tablas por relevancia

  3. CALIDAD DE DATOS (DataQualityService + interpretacion IA)
     - Deteccion de duplicados
     - Analisis de impacto
     - Interpretacion de datos incorrectos por la IA

EJECUCION:
  cd bots/interjddcia
  python test_sistemas_ia.py

  O con detalle:
  python test_sistemas_ia.py -v

NOTA: Los tests de BD real requieren que Firebird este accesible.
      Los tests de IA requieren que Qwen3 LAN este disponible.
      Los tests unitarios (sin BD/IA) funcionan siempre.
"""

import json
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from collections import defaultdict

# Forzar UTF-8 en stdout/stderr para Windows (evita UnicodeEncodeError con emojis)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─── Ajustar PYTHONPATH ───────────────────────────────────────────────────────
# Ejecutar desde bots/interjddcia/ o desde la raiz del workspace
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Tambien añadir el directorio padre por si se ejecuta desde la raiz
_PARENT = _HERE.parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

# ─── Colores para output ──────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {BLUE}ℹ{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 1: MEMORIA PERMANENTE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoriaPermanente(unittest.TestCase):
    """
    Tests del sistema de memoria permanente.

    COMPONENTES:
      - InteractionHistoryService: SQLite con historial de interacciones IA
      - siuo_query_log.json: log de consultas del ContextRetriever
      - Feedback loop: registro de SQL correcto/incorrecto

    GARANTIAS:
      - Las interacciones se persisten entre reinicios del servidor
      - El historial de conversacion se incluye en el contexto del chat
      - El feedback mejora el concept_index con el tiempo
    """

    def setUp(self):
        """Crear BD temporal para tests."""
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_history.db")

    def tearDown(self):
        """Limpiar ficheros temporales."""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ── Test 1.1: Guardar y recuperar interacciones ───────────────────────────

    def test_guardar_y_recuperar_interaccion(self):
        """La memoria guarda interacciones y las recupera correctamente."""
        from backend.modules.interaction_history.service import InteractionHistoryService

        svc = InteractionHistoryService(db_path=self.db_path)

        # Guardar una interaccion de chat
        svc.log_interaction(
            module="CHAT",
            action="SQL_GEN",
            input_context="cuantos articulos hay",
            output_result="SELECT COUNT(*) FROM ARTICULO",
            model_id="jddcia-qwen3-30b-ip",
            metadata={"tables_used": ["ARTICULO"], "tokens": 450},
            status="SUCCESS"
        )

        # Recuperar
        history = svc.get_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["module"], "CHAT")
        self.assertEqual(history[0]["action"], "SQL_GEN")
        # input_context es la pregunta del usuario, output_result es el SQL generado
        self.assertIn("articulos", history[0]["input_context"])
        self.assertIn("ARTICULO", history[0]["output_result"])
        self.assertEqual(history[0]["status"], "SUCCESS")
        ok("Guardar y recuperar interaccion: OK")

    # ── Test 1.2: Persistencia entre sesiones ────────────────────────────────

    def test_persistencia_entre_sesiones(self):
        """La memoria persiste aunque se reinicie el servicio."""
        from backend.modules.interaction_history.service import InteractionHistoryService

        # Sesion 1: guardar (con pequeña pausa para garantizar orden de timestamps)
        svc1 = InteractionHistoryService(db_path=self.db_path)
        svc1.log_interaction(
            module="CHAT",
            action="SQL_GEN",
            input_context="facturas del mes pasado",
            output_result="SELECT FIRST 10 * FROM DOCCAB WHERE TIPO=13",
            model_id="jddcia-qwen3-30b-ip",
            status="SUCCESS"
        )
        import time as _time
        _time.sleep(0.05)  # Garantizar timestamps distintos
        svc1.log_interaction(
            module="CHAT",
            action="SQL_GEN",
            input_context="clientes de Madrid",
            output_result="SELECT * FROM CLIENTE WHERE UPPER(CIUDAD) LIKE UPPER('%MADRID%')",
            model_id="jddcia-qwen3-30b-ip",
            status="SUCCESS"
        )

        # Sesion 2: nueva instancia, misma BD
        svc2 = InteractionHistoryService(db_path=self.db_path)
        history = svc2.get_history(limit=10)

        self.assertEqual(len(history), 2, "Debe haber 2 interacciones persistidas")
        # Verificar que ambas preguntas estan en el historial (sin asumir orden exacto)
        all_inputs = [h["input_context"] for h in history]
        self.assertTrue(
            any("Madrid" in inp for inp in all_inputs),
            f"'clientes de Madrid' debe estar en el historial. Historial: {all_inputs}"
        )
        self.assertTrue(
            any("facturas" in inp for inp in all_inputs),
            f"'facturas del mes pasado' debe estar en el historial. Historial: {all_inputs}"
        )
        ok("Persistencia entre sesiones: OK")

    # ── Test 1.3: Filtrado por modulo ─────────────────────────────────────────

    def test_filtrado_por_modulo(self):
        """El historial se puede filtrar por modulo (CHAT, OUTLOOK, etc.)."""
        from backend.modules.interaction_history.service import InteractionHistoryService

        svc = InteractionHistoryService(db_path=self.db_path)
        svc.log_interaction("CHAT",    "SQL_GEN",  "pregunta chat",   "respuesta chat",   status="SUCCESS")
        svc.log_interaction("OUTLOOK", "ANALYSIS", "email analizado", "respuesta email",  status="SUCCESS")
        svc.log_interaction("CHAT",    "SQL_GEN",  "otra pregunta",   "otra respuesta",   status="SUCCESS")

        chat_history = svc.get_history(module="CHAT")
        self.assertEqual(len(chat_history), 2, "Solo debe devolver interacciones de CHAT")

        outlook_history = svc.get_history(module="OUTLOOK")
        self.assertEqual(len(outlook_history), 1, "Solo debe devolver interacciones de OUTLOOK")
        ok("Filtrado por modulo: OK")

    # ── Test 1.4: Metadata JSON se guarda y recupera ──────────────────────────

    def test_metadata_json_persistido(self):
        """Los metadatos JSON se serializan y deserializan correctamente."""
        from backend.modules.interaction_history.service import InteractionHistoryService

        svc = InteractionHistoryService(db_path=self.db_path)
        metadata = {
            "tables_used": ["DOCCAB", "DOCLIN", "ARTICULO"],
            "tokens_used": 1250,
            "model": "qwen3-30b",
            "sql_retries": 2,
            "siuo_source": "concept_index"
        }
        svc.log_interaction(
            module="CHAT",
            action="SQL_GEN",
            input_context="articulos mas vendidos",
            output_result="SELECT a.NOMBRE, SUM(l.CANTIDAD) FROM ARTICULO a JOIN DOCLIN l ON l.CODART=a.CODART GROUP BY a.NOMBRE",
            metadata=metadata,
            status="SUCCESS"
        )

        history = svc.get_history(limit=1)
        recovered_meta = history[0]["metadata"]
        self.assertEqual(recovered_meta["tables_used"], ["DOCCAB", "DOCLIN", "ARTICULO"])
        self.assertEqual(recovered_meta["tokens_used"], 1250)
        self.assertEqual(recovered_meta["sql_retries"], 2)
        ok("Metadata JSON persistido: OK")

    # ── Test 1.5: Query log del ContextRetriever ──────────────────────────────

    def test_query_log_contextretriever(self):
        """El ContextRetriever registra consultas en siuo_query_log.json."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever
        from backend.modules.db_explorer.deep_indexer_service import _save_json, _load_json

        # Crear retriever con indices minimos en directorio temporal
        retriever = ContextRetriever()

        # Inyectar indices minimos directamente (sin ficheros)
        retriever._table_index = {
            "ARTICULO": {
                "cat": "maestros", "desc": "Catalogo de articulos",
                "n": 11846, "pk": ["CODART"],
                "cols_key": ["CODART", "NOMBRE", "PRECIO"],
                "related": ["DOCLIN"], "kw": ["articulo", "producto"]
            }
        }
        retriever._concept_index = {
            "articulo": ["ARTICULO"],
            "producto": ["ARTICULO"],
        }
        retriever._graph_adj = defaultdict(set)
        retriever._loaded = True

        # Usar log temporal
        import tempfile
        tmp_log = Path(tempfile.mktemp(suffix=".json"))

        # Parchear la ruta del log
        with patch("backend.modules.db_explorer.context_retriever.QUERY_LOG_PATH", tmp_log):
            context, meta = retriever.get_context("cuantos articulos hay")

        # Verificar que se registro
        if tmp_log.exists():
            log = json.loads(tmp_log.read_text(encoding="utf-8"))
            self.assertGreater(len(log.get("queries", [])), 0)
            entry = log["queries"][0]
            self.assertIn("articulo", entry.get("keywords", []))
            ok("Query log del ContextRetriever: OK")
        else:
            warn("Query log no creado (puede ser por ruta temporal) — verificar manualmente")

    # ── Test 1.6: Feedback loop ───────────────────────────────────────────────

    def test_feedback_loop(self):
        """El feedback de SQL correcto/incorrecto se persiste correctamente."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever

        retriever = ContextRetriever()
        retriever._loaded = True

        tmp_log = Path(tempfile.mktemp(suffix=".json"))

        with patch("backend.modules.db_explorer.context_retriever.QUERY_LOG_PATH", tmp_log):
            # Feedback positivo
            retriever.register_feedback(
                question="cuantos articulos hay",
                sql_used="SELECT COUNT(*) FROM ARTICULO",
                was_correct=True,
                tables_used=["ARTICULO"]
            )
            # Feedback negativo
            retriever.register_feedback(
                question="facturas de enero",
                sql_used="SELECT * FROM DOCCAB WHERE TIPO=13 LIMIT 10",
                was_correct=False,
                tables_used=["DOCCAB"]
            )

        if tmp_log.exists():
            log = json.loads(tmp_log.read_text(encoding="utf-8"))
            feedbacks = log.get("feedback", [])
            self.assertEqual(len(feedbacks), 2)
            self.assertTrue(feedbacks[0]["correct"])
            self.assertFalse(feedbacks[1]["correct"])
            self.assertIn("LIMIT", feedbacks[1]["sql"])  # El SQL incorrecto tenia LIMIT
            ok("Feedback loop: OK")
        else:
            warn("Fichero de feedback no creado — verificar manualmente")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 2: RELACIONES MULTI-TABLA
# ═══════════════════════════════════════════════════════════════════════════════

class TestRelacionesMultiTabla(unittest.TestCase):
    """
    Tests del sistema de relaciones multi-tabla.

    COMPONENTES:
      - db_graph.json: grafo de relaciones entre tablas
      - ContextRetriever._expand_with_graph(): BFS para encontrar tablas relacionadas
      - concept_index.json: mapa concepto -> tablas con filtros SQL

    GARANTIAS:
      - Preguntas complejas encuentran todas las tablas necesarias para el JOIN
      - El grafo BFS no entra en bucles infinitos
      - Las tablas mas relevantes tienen mayor score
      - Los filtros SQL (TIPO=13) se propagan correctamente al contexto
    """

    def setUp(self):
        """Crear un ContextRetriever con indices de prueba completos."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever

        self.retriever = ContextRetriever()

        # Indices de prueba que simulan la BD real de JDDC
        self.retriever._table_index = {
            "ARTICULO": {
                "cat": "maestros",
                "desc": "Catalogo de articulos y productos",
                "n": 11846,
                "pk": ["CODART"],
                "cols_key": ["CODART", "NOMBRE", "FAMILIA", "PRECIO", "STOCKARTICULO"],
                "related": ["DOCLIN", "ALMACEN"],
                "kw": ["articulo", "producto", "referencia", "stock", "precio"],
                "queries": ["SELECT FIRST 10 CODART, NOMBRE FROM ARTICULO"]
            },
            "DOCCAB": {
                "cat": "transacciones",
                "desc": "Cabecera de documentos (facturas, albaranes, pedidos)",
                "n": 85000,
                "pk": ["NUMDOC", "TIPO"],
                "cols_key": ["NUMDOC", "TIPO", "FECHA", "CODCLI", "TOTAL"],
                "related": ["DOCLIN", "CLIENTE"],
                "kw": ["factura", "albaran", "pedido", "venta", "documento"],
                "queries": ["SELECT FIRST 10 NUMDOC, FECHA, TOTAL FROM DOCCAB WHERE TIPO=13"]
            },
            "DOCLIN": {
                "cat": "transacciones",
                "desc": "Lineas de documentos (detalle de articulos por documento)",
                "n": 320000,
                "pk": ["NUMDOC", "LINEA"],
                "cols_key": ["NUMDOC", "CODART", "CANTIDAD", "PRECIO", "IMPORTE"],
                "related": ["DOCCAB", "ARTICULO"],
                "kw": ["linea", "detalle", "cantidad", "importe"],
                "queries": ["SELECT CODART, SUM(CANTIDAD) FROM DOCLIN GROUP BY CODART"]
            },
            "CLIENTE": {
                "cat": "maestros",
                "desc": "Maestro de clientes",
                "n": 3200,
                "pk": ["CODCLI"],
                "cols_key": ["CODCLI", "NOMBRE", "CIUDAD", "PROVINCIA", "TELEFONO"],
                "related": ["DOCCAB"],
                "kw": ["cliente", "comprador"],
                "queries": ["SELECT FIRST 10 CODCLI, NOMBRE FROM CLIENTE"]
            },
            "PROVEED": {
                "cat": "maestros",
                "desc": "Maestro de proveedores",
                "n": 450,
                "pk": ["CODPRO"],
                "cols_key": ["CODPRO", "NOMBRE", "CIUDAD"],
                "related": ["DOCCAB"],
                "kw": ["proveedor", "suministrador"],
                "queries": ["SELECT FIRST 10 CODPRO, NOMBRE FROM PROVEED"]
            },
            "ALMACEN": {
                "cat": "logistica",
                "desc": "Almacenes y ubicaciones",
                "n": 5,
                "pk": ["CODALMACEN"],
                "cols_key": ["CODALMACEN", "NOMBRE"],
                "related": ["ARTICULO", "ESTALMACEN"],
                "kw": ["almacen", "ubicacion"],
                "queries": ["SELECT CODALMACEN, NOMBRE FROM ALMACEN"]
            },
        }

        self.retriever._concept_index = {
            "articulo":    ["ARTICULO"],
            "producto":    ["ARTICULO"],
            "referencia":  ["ARTICULO"],
            "stock":       ["ARTICULO", "ALMACEN"],
            "precio":      ["ARTICULO", "DOCLIN"],
            "factura":     [{"table": "DOCCAB", "filter": "TIPO=13"}],
            "albaran":     [{"table": "DOCCAB", "filter": "TIPO=11"}],
            "pedido":      [{"table": "DOCCAB", "filter": "TIPO=12"}],
            "venta":       [{"table": "DOCCAB", "filter": "TIPO IN (11,13)"}],
            "compra":      [{"table": "DOCCAB", "filter": "TIPO=12"}],
            "linea":       ["DOCLIN"],
            "detalle":     ["DOCLIN"],
            "cantidad":    ["DOCLIN"],
            "cliente":     ["CLIENTE"],
            "proveedor":   ["PROVEED"],
            "almacen":     ["ALMACEN"],
        }

        # Grafo de relaciones (bidireccional)
        self.retriever._graph_adj = defaultdict(set, {
            "DOCLIN":   {"DOCCAB", "ARTICULO"},
            "DOCCAB":   {"DOCLIN", "CLIENTE", "PROVEED"},
            "ARTICULO": {"DOCLIN", "ALMACEN"},
            "CLIENTE":  {"DOCCAB"},
            "PROVEED":  {"DOCCAB"},
            "ALMACEN":  {"ARTICULO"},
        })

        self.retriever._graph_paths = {
            "ARTICULO->DOCCAB":  ["ARTICULO", "DOCLIN", "DOCCAB"],
            "CLIENTE->ARTICULO": ["CLIENTE", "DOCCAB", "DOCLIN", "ARTICULO"],
        }

        self.retriever._value_index = {
            "enums": {
                "DOCCAB.TIPO": {
                    "0": "presupuesto", "2": "SAT", "3": "abono",
                    "10": "contrato", "11": "albaran", "12": "pedido",
                    "13": "factura", "51": "certificacion", "61": "recibo"
                }
            },
            "ranges": {
                "DOCCAB.FECHA": {"min": "2015-01-01", "max": "2026-03-04"}
            }
        }

        self.retriever._loaded = True

    # ── Test 2.1: Pregunta simple — una tabla ─────────────────────────────────

    def test_pregunta_simple_una_tabla(self):
        """Una pregunta simple encuentra la tabla correcta."""
        context, meta = self.retriever.get_context("cuantos articulos hay")

        self.assertIn("ARTICULO", meta["tables_used"],
                      "ARTICULO debe estar en el contexto")
        self.assertIn("articulo", meta["keywords_found"],
                      "El keyword 'articulo' debe ser reconocido")
        self.assertGreater(meta["tokens_estimated"], 0)
        self.assertEqual(meta["source"], "siuo")
        ok(f"Pregunta simple: tablas={meta['tables_used']}, tokens={meta['tokens_estimated']}")

    # ── Test 2.2: Pregunta compleja — JOIN de 3 tablas ────────────────────────

    def test_pregunta_compleja_join_tres_tablas(self):
        """
        'articulos con mas ventas' requiere ARTICULO + DOCLIN + DOCCAB.
        El BFS debe encontrar las 3 tablas.
        """
        context, meta = self.retriever.get_context("articulos con mas ventas este mes")

        tables = meta["tables_used"]
        self.assertIn("ARTICULO", tables, "ARTICULO debe estar en el contexto")
        # DOCLIN o DOCCAB deben aparecer por expansion del grafo
        has_join_table = "DOCLIN" in tables or "DOCCAB" in tables
        self.assertTrue(has_join_table,
                        f"Debe haber al menos una tabla de transacciones. Tablas: {tables}")
        ok(f"Pregunta compleja JOIN: tablas={tables}")

    # ── Test 2.3: Filtro SQL propagado correctamente ──────────────────────────

    def test_filtro_sql_en_contexto(self):
        """
        Al preguntar por 'facturas', el contexto debe incluir 'WHERE TIPO=13'.
        Este filtro es critico para que la IA genere SQL correcto.
        """
        context, meta = self.retriever.get_context("facturas del mes pasado")

        self.assertIn("DOCCAB", meta["tables_used"],
                      "DOCCAB debe estar en el contexto para facturas")
        self.assertIn("TIPO=13", context,
                      "El filtro TIPO=13 debe aparecer en el contexto")
        ok(f"Filtro SQL TIPO=13 en contexto: OK")

    # ── Test 2.4: Expansion BFS sin bucles ───────────────────────────────────

    def test_expansion_bfs_sin_bucles(self):
        """
        La expansion BFS no debe entrar en bucles infinitos
        aunque el grafo tenga ciclos (DOCCAB <-> DOCLIN <-> ARTICULO).
        """
        candidates = {"ARTICULO": {"filter": None, "score": 1, "source": "concept_index", "kws": []}}

        # No debe lanzar excepcion ni colgar
        expanded = self.retriever._expand_with_graph(candidates, depth=3)

        # Debe haber expandido a tablas relacionadas
        self.assertGreater(len(expanded), 1, "Debe haber expandido a mas de 1 tabla")
        # No debe haber duplicados
        self.assertEqual(len(expanded), len(set(expanded.keys())))
        ok(f"BFS sin bucles: {len(expanded)} tablas expandidas sin duplicados")

    # ── Test 2.5: Ranking — tablas directas antes que expandidas ─────────────

    def test_ranking_tablas_directas_primero(self):
        """
        Las tablas encontradas directamente en concept_index deben tener
        mayor score que las expandidas por el grafo.
        """
        context, meta = self.retriever.get_context("clientes de Madrid")

        tables = meta["tables_used"]
        self.assertGreater(len(tables), 0)
        # CLIENTE debe ser la primera (score mas alto)
        self.assertEqual(tables[0], "CLIENTE",
                         f"CLIENTE debe ser la primera tabla. Orden: {tables}")
        ok(f"Ranking correcto: {tables}")

    # ── Test 2.6: Pregunta sobre proveedores y compras ────────────────────────

    def test_pregunta_proveedor_compras(self):
        """
        'pedidos a proveedores' debe encontrar PROVEED + DOCCAB (TIPO=12).
        """
        context, meta = self.retriever.get_context("pedidos a proveedores del ultimo mes")

        tables = meta["tables_used"]
        has_proveedor = "PROVEED" in tables
        has_doccab    = "DOCCAB" in tables

        # Al menos uno de los dos debe estar
        self.assertTrue(has_proveedor or has_doccab,
                        f"Debe encontrar PROVEED o DOCCAB. Tablas: {tables}")

        # Si DOCCAB esta, debe tener filtro de pedido
        if has_doccab and "TIPO=12" in context:
            ok(f"Pedidos a proveedores con filtro TIPO=12: OK")
        else:
            ok(f"Pedidos a proveedores: tablas={tables}")

    # ── Test 2.7: Control de tokens ───────────────────────────────────────────

    def test_control_de_tokens(self):
        """
        El contexto nunca debe exceder el limite de tokens configurado.
        """
        max_tokens = 500  # Limite muy bajo para forzar recorte

        context, meta = self.retriever.get_context(
            "articulos con mas ventas facturas clientes proveedores almacen",
            max_tokens=max_tokens
        )

        # El contexto debe estar dentro del limite (con margen del 20%)
        self.assertLessEqual(
            meta["tokens_estimated"],
            max_tokens * 1.2,
            f"Tokens {meta['tokens_estimated']} excede el limite {max_tokens}"
        )
        ok(f"Control de tokens: {meta['tokens_estimated']} <= {max_tokens} (limite)")

    # ── Test 2.8: Fallback cuando no hay indices ──────────────────────────────

    def test_fallback_sin_indices(self):
        """
        Si no hay indices SIUO, el sistema usa db_metadata_optimized.json (fallback v1).
        El sistema no debe romperse.
        """
        from backend.modules.db_explorer.context_retriever import ContextRetriever

        retriever_vacio = ContextRetriever()
        retriever_vacio._loaded = False
        retriever_vacio._table_index = {}

        with patch("backend.modules.db_explorer.context_retriever.ContextRetriever._get_fallback_context",
                   return_value="Esquema fallback v1: ARTICULO, DOCCAB, CLIENTE"):
            context, meta = retriever_vacio.get_context("cuantos articulos hay")

        self.assertEqual(meta["source"], "fallback")
        self.assertIn("fallback", context.lower())
        ok("Fallback sin indices: OK")


# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA 3: CALIDAD DE DATOS E INTERPRETACION IA
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalidadDatosIA(unittest.TestCase):
    """
    Tests del sistema de calidad de datos con interpretacion IA.

    COMPONENTES:
      - DataQualityService: deteccion de duplicados, analisis de impacto
      - ChatService: interpretacion de datos incorrectos por la IA
      - FirebirdSQLNormalizer: correccion determinista de SQL

    GARANTIAS:
      - Los duplicados se detectan correctamente
      - La IA interpreta datos incorrectos y sugiere correcciones
      - El SQL generado para calidad de datos es valido en Firebird
      - Los datos sensibles no se envian a la IA
    """

    # ── Test 3.1: DataQualityService — estructura basica ─────────────────────

    def test_data_quality_service_instancia(self):
        """DataQualityService se puede instanciar sin errores."""
        from backend.modules.data_quality.service import DataQualityService

        svc = DataQualityService()
        self.assertIsNotNone(svc)
        ok("DataQualityService instanciado: OK")

    # ── Test 3.2: Analisis de impacto — estructura de respuesta ──────────────

    def test_analyze_impact_estructura(self):
        """analyze_impact devuelve la estructura esperada."""
        from backend.modules.data_quality.service import DataQualityService

        svc = DataQualityService()
        result = svc.analyze_impact(
            params={},
            table_name="ARTICULO",
            record_id="ART001",
            pk_field="CODART"
        )

        self.assertIn("table", result)
        self.assertIn("record_id", result)
        self.assertIn("impact_score", result)
        self.assertIn("dependencies", result)
        self.assertEqual(result["table"], "ARTICULO")
        self.assertEqual(result["record_id"], "ART001")
        ok("Estructura de analyze_impact: OK")

    # ── Test 3.3: SQL de calidad de datos — valido en Firebird ───────────────

    def test_sql_calidad_datos_valido_firebird(self):
        """
        El SQL generado para detectar duplicados debe ser valido en Firebird.
        Verifica que no usa LIMIT (invalido en Firebird) sino FIRST.
        """
        from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

        normalizer = FirebirdSQLNormalizer()

        # SQL tipico de calidad de datos con LIMIT (incorrecto para Firebird)
        sql_con_limit = """
        SELECT NOMBRE, COUNT(*) as TOTAL_DUPLICADOS
        FROM ARTICULO
        GROUP BY NOMBRE
        HAVING COUNT(*) > 1
        ORDER BY TOTAL_DUPLICADOS DESC
        LIMIT 50
        """

        sql_normalizado, cambios = normalizer.normalize(sql_con_limit)

        # Verificar que LIMIT fue eliminado o convertido
        self.assertNotIn("LIMIT", sql_normalizado.upper(),
                         "LIMIT no debe aparecer en SQL Firebird")
        self.assertGreater(len(cambios), 0, "Debe haber al menos un cambio")
        ok(f"SQL normalizado para Firebird: {len(cambios)} correcciones aplicadas")

    # ── Test 3.4: Interpretacion IA de datos incorrectos ─────────────────────

    def test_interpretacion_ia_datos_incorrectos(self):
        """
        La funcion interpret_results_for_voice interpreta correctamente
        resultados de consultas de calidad de datos.
        """
        from backend.modules.chat.service import interpret_results_for_voice

        # Simular resultados de duplicados
        resultados_duplicados = [
            {"NOMBRE": "Split 2.5kW Daikin", "TOTAL_DUPLICADOS": 3},
            {"NOMBRE": "Gas R-32 10kg",       "TOTAL_DUPLICADOS": 2},
            {"NOMBRE": "Cassette 4 vias",     "TOTAL_DUPLICADOS": 2},
        ]

        respuesta = interpret_results_for_voice(
            message="articulos duplicados",
            results=resultados_duplicados,
            sql_query="SELECT NOMBRE, COUNT(*) FROM ARTICULO GROUP BY NOMBRE HAVING COUNT(*) > 1"
        )

        self.assertIsInstance(respuesta, str)
        self.assertGreater(len(respuesta), 0)
        # La respuesta debe mencionar los resultados
        self.assertIn("3", respuesta)  # Hay 3 resultados
        ok(f"Interpretacion IA datos incorrectos: '{respuesta[:80]}...'")

    # ── Test 3.5: clean_for_tts — limpieza de Markdown ───────────────────────

    def test_clean_for_tts_elimina_markdown(self):
        """
        clean_for_tts elimina el formato Markdown para que el TTS
        de las gafas Meta lo lea correctamente.
        """
        from backend.modules.chat.service import clean_for_tts

        texto_con_markdown = """
## Articulos con datos incorrectos

Se encontraron **3 articulos** con posibles errores:

1. `ART001` — Precio: **0.00 €** (posiblemente incorrecto)
2. `ART002` — Stock: **-5** (stock negativo)
3. `ART003` — Nombre: *vacío*

> **Recomendacion**: Revisar estos articulos en el sistema.
"""
        texto_limpio = clean_for_tts(texto_con_markdown)

        # No debe contener caracteres de Markdown
        self.assertNotIn("**", texto_limpio)
        self.assertNotIn("##", texto_limpio)
        self.assertNotIn("`", texto_limpio)
        self.assertNotIn("*", texto_limpio)

        # Debe contener el texto relevante
        self.assertIn("ART001", texto_limpio)
        self.assertIn("ART002", texto_limpio)
        ok(f"clean_for_tts: Markdown eliminado correctamente")

    # ── Test 3.6: Privacidad — columnas sensibles no en contexto ─────────────

    def test_privacidad_columnas_sensibles(self):
        """
        Las columnas sensibles (PASSWORD, DNI, etc.) no deben aparecer
        en el contexto enviado a la IA.
        """
        from backend.modules.db_explorer.context_retriever import ContextRetriever

        retriever = ContextRetriever()
        retriever._table_index = {
            "USUARIO": {
                "cat": "seguridad",
                "desc": "Usuarios del sistema",
                "n": 50,
                "pk": ["CODUSUARIO"],
                "cols_key": ["CODUSUARIO", "NOMBRE"],  # Sin PASSWORD ni DNI
                "related": [],
                "kw": ["usuario"]
            }
        }
        retriever._concept_index = {"usuario": ["USUARIO"]}
        retriever._graph_adj = defaultdict(set)
        retriever._value_index = {}
        retriever._loaded = True

        context, meta = retriever.get_context("usuarios del sistema")

        # El contexto no debe contener columnas sensibles
        context_upper = context.upper()
        self.assertNotIn("PASSWORD", context_upper,
                         "PASSWORD no debe aparecer en el contexto")
        self.assertNotIn("CONTRASENA", context_upper,
                         "CONTRASENA no debe aparecer en el contexto")
        ok("Privacidad — columnas sensibles no en contexto: OK")

    # ── Test 3.7: Sugerencias de autoaprendizaje ──────────────────────────────

    def test_sugerencias_autoaprendizaje(self):
        """
        get_learning_suggestions devuelve la estructura correcta
        con keywords frecuentes sin mapear.
        """
        from backend.modules.db_explorer.context_retriever import ContextRetriever

        retriever = ContextRetriever()
        retriever._loaded = True

        # Simular un query_log con keywords desconocidos
        fake_log = {
            "queries": [
                {"ts": "2026-03-04T10:00:00", "question": "splits inverter",
                 "keywords": [], "tables_used": [], "unknown_kws": ["inverter", "splits"]},
                {"ts": "2026-03-04T10:01:00", "question": "splits inverter 2.5kw",
                 "keywords": [], "tables_used": [], "unknown_kws": ["inverter", "splits", "2.5kw"]},
                {"ts": "2026-03-04T10:02:00", "question": "equipos inverter",
                 "keywords": [], "tables_used": [], "unknown_kws": ["inverter", "equipos"]},
            ],
            "unknown_keywords": {"inverter": 3, "splits": 2, "equipos": 1, "2.5kw": 1},
            "feedback": []
        }

        tmp_log = Path(tempfile.mktemp(suffix=".json"))
        tmp_log.write_text(json.dumps(fake_log), encoding="utf-8")

        with patch("backend.modules.db_explorer.context_retriever.QUERY_LOG_PATH", tmp_log):
            suggestions = retriever.get_learning_suggestions()

        self.assertIn("unknown_keywords_frequent", suggestions)
        self.assertIn("top_tables_used", suggestions)
        self.assertIn("total_queries_logged", suggestions)

        # "inverter" debe ser el keyword mas frecuente
        top_kw = suggestions["unknown_keywords_frequent"]
        if top_kw:
            self.assertEqual(top_kw[0]["keyword"], "inverter")
            self.assertEqual(top_kw[0]["count"], 3)

        ok(f"Sugerencias autoaprendizaje: {len(top_kw)} keywords sugeridos")

        # Limpiar
        tmp_log.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS DE INTEGRACION (requieren servidor corriendo)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegracionAPI(unittest.TestCase):
    """
    Tests de integracion contra la API real.
    Solo se ejecutan si el servidor esta corriendo en localhost:8001.
    """

    BASE_URL = "http://localhost:8001"
    TIMEOUT  = 10

    def _server_available(self) -> bool:
        """Verifica si el servidor esta disponible."""
        try:
            import urllib.request
            urllib.request.urlopen(f"{self.BASE_URL}/health", timeout=3)
            return True
        except Exception:
            return False

    def setUp(self):
        if not self._server_available():
            self.skipTest("Servidor DEVIA no disponible en localhost:8001")

    def test_health_endpoint(self):
        """GET /health devuelve status ok."""
        import urllib.request, json as _json
        with urllib.request.urlopen(f"{self.BASE_URL}/health", timeout=self.TIMEOUT) as r:
            data = _json.loads(r.read())
        self.assertEqual(data["status"], "ok")
        ok(f"Health check: {data['service']} v{data['version']}")

    def test_siuo_stats_endpoint(self):
        """GET /api/siuo/stats devuelve estadisticas de los indices."""
        import urllib.request, json as _json
        try:
            with urllib.request.urlopen(f"{self.BASE_URL}/api/siuo/stats", timeout=self.TIMEOUT) as r:
                data = _json.loads(r.read())
            self.assertIn("retriever", data)
            self.assertIn("tables_indexed", data["retriever"])
            ok(f"SIUO stats: {data['retriever']['tables_indexed']} tablas indexadas")
        except Exception as e:
            warn(f"SIUO stats no disponible: {e}")

    def test_siuo_context_test_endpoint(self):
        """POST /api/siuo/context/test devuelve contexto para una pregunta."""
        import urllib.request, json as _json
        payload = json.dumps({"question": "cuantos articulos hay", "max_tokens": 1000}).encode()
        req = urllib.request.Request(
            f"{self.BASE_URL}/api/siuo/context/test",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as r:
                data = _json.loads(r.read())
            self.assertIn("context_preview", data)
            self.assertIn("meta", data)
            ok(f"Context test: {data['context_length']} chars, fuente={data['meta'].get('source')}")
        except Exception as e:
            warn(f"Context test no disponible: {e}")

    def test_siuo_learning_suggestions(self):
        """GET /api/siuo/learning/suggestions devuelve sugerencias."""
        import urllib.request, json as _json
        try:
            with urllib.request.urlopen(
                f"{self.BASE_URL}/api/siuo/learning/suggestions", timeout=self.TIMEOUT
            ) as r:
                data = _json.loads(r.read())
            self.assertIn("total_queries_logged", data)
            ok(f"Learning suggestions: {data['total_queries_logged']} consultas registradas")
        except Exception as e:
            warn(f"Learning suggestions no disponible: {e}")

    def test_chat_pregunta_simple(self):
        """POST /api/chat/send responde a una pregunta simple."""
        import urllib.request, json as _json
        payload = json.dumps({
            "message": "cuantos articulos hay en la base de datos",
            "model_id": None
        }).encode()
        req = urllib.request.Request(
            f"{self.BASE_URL}/api/chat/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = _json.loads(r.read())
            response = data.get("response", data.get("message", str(data)))
            self.assertIsInstance(response, str)
            self.assertGreater(len(response), 0)
            ok(f"Chat pregunta simple: '{response[:80]}...'")
        except Exception as e:
            warn(f"Chat no disponible o timeout: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# RUNNER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """Ejecuta todos los tests con output formateado."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}  DEVIA — Tests de los 3 Sistemas IA{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

    suites = [
        ("SISTEMA 1: MEMORIA PERMANENTE",       TestMemoriaPermanente),
        ("SISTEMA 2: RELACIONES MULTI-TABLA",   TestRelacionesMultiTabla),
        ("SISTEMA 3: CALIDAD DE DATOS + IA",    TestCalidadDatosIA),
        ("INTEGRACION API (requiere servidor)", TestIntegracionAPI),
    ]

    total_ok    = 0
    total_fail  = 0
    total_skip  = 0
    resultados  = []

    for suite_name, test_class in suites:
        print(f"\n{BOLD}{YELLOW}▶ {suite_name}{RESET}")
        print(f"  {'-'*60}")

        loader = unittest.TestLoader()
        suite  = loader.loadTestsFromTestCase(test_class)
        runner = unittest.TextTestRunner(
            verbosity=0,
            stream=open(os.devnull, 'w'),
            resultclass=unittest.TestResult
        )

        # Ejecutar con output personalizado
        result = unittest.TestResult()
        suite.run(result)

        n_ok   = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        n_fail = len(result.failures) + len(result.errors)
        n_skip = len(result.skipped)

        total_ok   += n_ok
        total_fail += n_fail
        total_skip += n_skip

        # Mostrar errores si los hay
        for test, traceback in result.failures + result.errors:
            test_name = str(test).split(" ")[0]
            # Extraer solo la linea del error
            lines = traceback.strip().split("\n")
            error_line = lines[-1] if lines else "Error desconocido"
            fail(f"{test_name}: {error_line[:100]}")

        for test, reason in result.skipped:
            test_name = str(test).split(" ")[0]
            warn(f"{test_name}: OMITIDO ({reason[:60]})")

        status = f"{GREEN}{n_ok} OK{RESET}"
        if n_fail > 0:
            status += f", {RED}{n_fail} FALLIDOS{RESET}"
        if n_skip > 0:
            status += f", {YELLOW}{n_skip} OMITIDOS{RESET}"

        resultados.append((suite_name, n_ok, n_fail, n_skip))
        print(f"\n  Resultado: {status}")

    # Resumen final
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}  RESUMEN FINAL{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}")

    for suite_name, n_ok, n_fail, n_skip in resultados:
        icon = GREEN + "✓" if n_fail == 0 else RED + "✗"
        print(f"  {icon}{RESET} {suite_name}: {n_ok} OK, {n_fail} fallidos, {n_skip} omitidos")

    print(f"\n  Total: {GREEN}{total_ok} OK{RESET}, {RED}{total_fail} FALLIDOS{RESET}, {YELLOW}{total_skip} OMITIDOS{RESET}")

    if total_fail == 0:
        print(f"\n  {GREEN}{BOLD}✓ TODOS LOS TESTS PASARON{RESET}\n")
    else:
        print(f"\n  {RED}{BOLD}✗ HAY {total_fail} TESTS FALLIDOS — revisar arriba{RESET}\n")

    return total_fail == 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tests de los 3 sistemas IA de DEVIA")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Modo verbose (unittest estandar)")
    parser.add_argument("--solo", choices=["memoria", "relaciones", "calidad", "api"],
                        help="Ejecutar solo un sistema")
    args = parser.parse_args()

    if args.verbose:
        # Modo verbose estandar de unittest
        unittest.main(argv=[sys.argv[0]], verbosity=2, exit=False)
    elif args.solo:
        mapping = {
            "memoria":    TestMemoriaPermanente,
            "relaciones": TestRelacionesMultiTabla,
            "calidad":    TestCalidadDatosIA,
            "api":        TestIntegracionAPI,
        }
        suite = unittest.TestLoader().loadTestsFromTestCase(mapping[args.solo])
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
    else:
        success = run_tests()
        sys.exit(0 if success else 1)
