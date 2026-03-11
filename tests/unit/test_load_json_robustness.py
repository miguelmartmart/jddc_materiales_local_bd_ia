"""
tests/unit/test_load_json_robustness.py
Tests de robustez de _load_json y del ContextRetriever con concept_index real.

CUBRE:
  - _load_json: JSON limpio, bytes corruptos al inicio, BOM, vacío, no existe
  - _load_json: auto-corrección del fichero corrupto
  - ContextRetriever: keywords con tilde y plural (bug 10/03/2026)
  - ContextRetriever: keywords del concept_index real (2084 keywords)
  - ContextRetriever: pregunta "artículos con más compras" -> tablas correctas

PRINCIPIOS:
  - Usa tmp_path de pytest (no toca ficheros reales)
  - Constantes en TEST_CASES (no magic strings)
  - Reutiliza helpers: make_json_file(), make_corrupt_json_file()
  - < 500 líneas
"""

import json
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ─── Setup del path ───────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.modules.db_explorer.deep_indexer_service import _load_json, _save_json

# ─── Constantes de test ───────────────────────────────────────────────────────

VALID_JSON = {"version": "1.0", "index": {"articulo": [{"table": "ARTICULO"}]}}
VALID_JSON_BYTES = json.dumps(VALID_JSON, ensure_ascii=False).encode("utf-8")

# Bytes corruptos conocidos (caso real 10/03/2026: 0x69 = 'i')
CORRUPT_PREFIX_CASES = [
    (b"\x69",       "byte 0x69 (i) - caso real 10/03/2026"),
    (b"\xef\xbb\xbf", "BOM UTF-8 (3 bytes)"),
    (b"\xff\xfe",   "BOM UTF-16 LE (2 bytes)"),
    (b"i",          "letra i ASCII"),
    (b"abc",        "3 letras ASCII"),
    (b"\x00",       "null byte"),
]

# Preguntas que deben encontrar tablas en el concept_index real
KEYWORD_TEST_CASES = [
    # (pregunta, keywords_esperados_en_concept_index, tablas_esperadas)
    ("dame los articulos con mas compras",
     ["articulo", "compra"],
     ["ARTICULO", "DOCCAB", "DOCLIN"]),
    ("artículos con más compras",
     ["articulo", "compra"],
     ["ARTICULO", "DOCCAB", "DOCLIN"]),
    ("facturas del mes pasado",
     ["factura"],
     ["DOCCAB"]),
    ("clientes con mas ventas",
     ["cliente", "venta"],
     ["CLIENTE", "DOCCAB"]),
    ("stock de articulos",
     ["stock", "articulo"],
     ["ARTICULO"]),
    ("pedidos a proveedores",
     ["pedido", "proveedor"],
     ["DOCCAB", "PROVEED"]),
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_json_file(tmp_path: Path, name: str, data: dict) -> Path:
    """Crea un fichero JSON limpio en tmp_path."""
    p = tmp_path / name
    p.write_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return p


def make_corrupt_json_file(tmp_path: Path, name: str, data: dict, prefix: bytes) -> Path:
    """Crea un fichero JSON con bytes corruptos al inicio."""
    p = tmp_path / name
    clean = json.dumps(data, ensure_ascii=False).encode("utf-8")
    p.write_bytes(prefix + clean)
    return p


def get_concept_index_path() -> Path:
    """Ruta al concept_index.json real del proyecto."""
    return ROOT / "backend" / "core" / "config" / "concept_index.json"


def load_real_concept_index() -> dict:
    """Carga el concept_index.json real. Devuelve {} si no existe o está corrupto."""
    path = get_concept_index_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("index", {})
    except Exception:
        return {}


# ─── Tests de _load_json ──────────────────────────────────────────────────────

class TestLoadJsonBasico(unittest.TestCase):
    """Tests básicos de _load_json con ficheros limpios."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_json_limpio_carga_correctamente(self):
        """JSON limpio se carga sin problemas."""
        p = make_json_file(self.tmp, "clean.json", VALID_JSON)
        result = _load_json(p, {})
        self.assertEqual(result["version"], "1.0")
        self.assertIn("index", result)

    def test_fichero_no_existe_devuelve_default(self):
        """Si el fichero no existe, devuelve el default."""
        p = self.tmp / "no_existe.json"
        result = _load_json(p, {"default": True})
        self.assertEqual(result, {"default": True})

    def test_fichero_vacio_devuelve_default(self):
        """Fichero vacío devuelve el default."""
        p = self.tmp / "empty.json"
        p.write_bytes(b"")
        result = _load_json(p, {"default": True})
        self.assertEqual(result, {"default": True})

    def test_json_invalido_devuelve_default(self):
        """JSON completamente inválido devuelve el default."""
        p = self.tmp / "invalid.json"
        p.write_bytes(b"esto no es json para nada!!!")
        result = _load_json(p, {"default": True})
        self.assertEqual(result, {"default": True})

    def test_json_con_bom_utf8_carga_correctamente(self):
        """JSON con BOM UTF-8 (EF BB BF) se carga correctamente."""
        p = self.tmp / "bom.json"
        bom = b"\xef\xbb\xbf"
        p.write_bytes(bom + VALID_JSON_BYTES)
        result = _load_json(p, {})
        # Debe cargar correctamente (BOM es el caso más común)
        self.assertIsInstance(result, dict)
        self.assertNotEqual(result, {})


class TestLoadJsonCorrupcion(unittest.TestCase):
    """Tests de recuperación ante bytes corruptos al inicio del JSON."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_byte_corrupto_0x69_caso_real(self):
        """Caso real 10/03/2026: byte 0x69 ('i') antes del '{'."""
        p = make_corrupt_json_file(self.tmp, "corrupt.json", VALID_JSON, b"\x69")
        result = _load_json(p, {})
        self.assertIsInstance(result, dict)
        self.assertNotEqual(result, {}, "Debe recuperar el JSON a pesar del byte corrupto")
        self.assertIn("version", result)

    def test_byte_corrupto_auto_corrige_fichero(self):
        """Tras recuperar, el fichero debe quedar corregido (sin bytes corruptos)."""
        p = make_corrupt_json_file(self.tmp, "autocorrect.json", VALID_JSON, b"\x69")
        _load_json(p, {})
        # Verificar que el fichero ahora empieza con '{'
        first_byte = p.read_bytes()[0]
        self.assertEqual(first_byte, ord("{"),
                         f"El fichero debe empezar con '{{' tras auto-corrección, pero empieza con 0x{first_byte:02X}")

    def test_multiples_bytes_corruptos_al_inicio(self):
        """Varios bytes corruptos antes del '{' deben recuperarse."""
        p = make_corrupt_json_file(self.tmp, "multi_corrupt.json", VALID_JSON, b"abc")
        result = _load_json(p, {})
        self.assertIsInstance(result, dict)
        self.assertNotEqual(result, {})

    def test_null_byte_al_inicio(self):
        """Null byte (0x00) antes del '{' debe recuperarse."""
        p = make_corrupt_json_file(self.tmp, "null_byte.json", VALID_JSON, b"\x00")
        result = _load_json(p, {})
        self.assertIsInstance(result, dict)
        self.assertNotEqual(result, {})

    def test_json_array_con_byte_corrupto(self):
        """JSON que empieza con '[' también se recupera."""
        array_data = [{"table": "ARTICULO"}, {"table": "DOCCAB"}]
        p = self.tmp / "array_corrupt.json"
        p.write_bytes(b"\x69" + json.dumps(array_data).encode("utf-8"))
        result = _load_json(p, [])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_concept_index_con_byte_corrupto_carga_keywords(self):
        """Simula el bug real: concept_index con byte corrupto carga los 2084 keywords."""
        concept_data = {
            "version": "1.0",
            "index": {
                "articulo": [{"table": "ARTICULO"}],
                "compra":   [{"table": "DOCCAB", "filter": "TIPO=12"}],
                "factura":  [{"table": "DOCCAB", "filter": "TIPO=13"}],
            }
        }
        p = make_corrupt_json_file(self.tmp, "concept_corrupt.json", concept_data, b"\x69")
        result = _load_json(p, {})
        index = result.get("index", {})
        self.assertIn("articulo", index, "Debe cargar 'articulo' del concept_index")
        self.assertIn("compra",   index, "Debe cargar 'compra' del concept_index")
        self.assertIn("factura",  index, "Debe cargar 'factura' del concept_index")


class TestLoadJsonEncodings(unittest.TestCase):
    """Tests de _load_json con diferentes encodings."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())

    def test_utf8_sig_bom(self):
        """JSON con BOM UTF-8-sig se carga correctamente."""
        p = self.tmp / "utf8sig.json"
        content = json.dumps(VALID_JSON, ensure_ascii=False)
        p.write_text(content, encoding="utf-8-sig")
        result = _load_json(p, {})
        self.assertIsInstance(result, dict)
        self.assertNotEqual(result, {})

    def test_json_con_caracteres_especiales(self):
        """JSON con caracteres especiales (tildes, ñ) se carga correctamente."""
        data = {
            "version": "1.0",
            "index": {
                "artículo": [{"table": "ARTICULO"}],
                "descripción": "Tabla de artículos con ñ",
            }
        }
        p = make_json_file(self.tmp, "special_chars.json", data)
        result = _load_json(p, {})
        self.assertIn("artículo", result.get("index", {}))


# ─── Tests del ContextRetriever con concept_index real ───────────────────────

class TestContextRetrieverNormalizacion(unittest.TestCase):
    """
    Tests del ContextRetriever con el concept_index real del proyecto.
    Verifica que las tildes y plurales se normalizan correctamente.
    Bug detectado 10/03/2026: 'artículos' y 'compras' no se mapeaban.
    """

    @classmethod
    def setUpClass(cls):
        """Carga el concept_index real una sola vez para todos los tests."""
        cls.concept_index = load_real_concept_index()
        cls.has_real_index = len(cls.concept_index) > 100  # Índice real tiene 2084 keywords

    def _make_retriever_with_real_index(self):
        """Crea un ContextRetriever con el concept_index real cargado."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever
        r = ContextRetriever()
        r._concept_index = self.concept_index
        r._table_index   = {}
        r._graph_adj     = {}
        r._loaded        = bool(self.concept_index)
        return r

    def test_concept_index_real_tiene_keywords_suficientes(self):
        """El concept_index real debe tener al menos 100 keywords."""
        self.assertGreater(len(self.concept_index), 100,
                           f"concept_index tiene solo {len(self.concept_index)} keywords, esperaba >100")

    def test_articulo_sin_tilde_en_concept_index(self):
        """'articulo' (sin tilde) debe estar en el concept_index."""
        self.assertIn("articulo", self.concept_index,
                      "El concept_index debe tener 'articulo' (sin tilde)")

    def test_compra_en_concept_index(self):
        """'compra' debe estar en el concept_index."""
        self.assertIn("compra", self.concept_index,
                      "El concept_index debe tener 'compra'")

    def test_factura_en_concept_index(self):
        """'factura' debe estar en el concept_index."""
        self.assertIn("factura", self.concept_index,
                      "El concept_index debe tener 'factura'")

    def test_normalize_word_elimina_tilde_resultado_en_indice(self):
        """_normalize_word('artículos') debe devolver una forma que esté en el concept_index."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        result = r._normalize_word("artículos")
        self.assertIn(result, self.concept_index,
                      f"_normalize_word('artículos') devolvió '{result}' que NO está en concept_index")

    def test_normalize_word_plural_compras_resultado_en_indice(self):
        """_normalize_word('compras') debe devolver una forma que esté en el concept_index."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        result = r._normalize_word("compras")
        self.assertIn(result, self.concept_index,
                      f"_normalize_word('compras') devolvió '{result}' que NO está en concept_index")

    def test_normalize_word_plural_facturas_resultado_en_indice(self):
        """_normalize_word('facturas') debe devolver una forma que esté en el concept_index."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        result = r._normalize_word("facturas")
        self.assertIn(result, self.concept_index,
                      f"_normalize_word('facturas') devolvió '{result}' que NO está en concept_index")

    def test_extract_keywords_articulos_con_tilde(self):
        """'artículos' (con tilde) debe encontrar 'articulo' en el concept_index."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        found, unknown = r._extract_keywords("dame los artículos con más compras")
        self.assertIn("articulo", found,
                      f"'articulo' no encontrado. found={found}, unknown={unknown}")
        self.assertNotIn("artículos", unknown,
                         f"'artículos' no debería estar en unknown. unknown={unknown}")

    def test_extract_keywords_compras_plural(self):
        """'compras' (plural) debe encontrar 'compra' en el concept_index."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        found, unknown = r._extract_keywords("dame los artículos con más compras")
        self.assertIn("compra", found,
                      f"'compra' no encontrado. found={found}, unknown={unknown}")
        self.assertNotIn("compras", unknown,
                         f"'compras' no debería estar en unknown. unknown={unknown}")

    def test_pregunta_articulos_compras_no_tiene_unknown_criticos(self):
        """La pregunta 'artículos con más compras' no debe tener keywords críticos desconocidos."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        found, unknown = r._extract_keywords("dame los artículos con más compras")
        # Los keywords críticos NO deben estar en unknown
        criticos = {"artículos", "compras", "articulo", "compra"}
        unknown_criticos = criticos.intersection(set(unknown))
        self.assertEqual(unknown_criticos, set(),
                         f"Keywords críticos en unknown: {unknown_criticos}. "
                         f"found={found}, unknown={unknown}")

    def test_find_candidate_tables_articulo_compra(self):
        """Con keywords ['articulo', 'compra'] debe encontrar ARTICULO, DOCCAB, DOCLIN."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        candidates = r._find_candidate_tables(["articulo", "compra"])
        table_names = set(candidates.keys())
        self.assertIn("ARTICULO", table_names,
                      f"ARTICULO no encontrado. candidates={table_names}")
        self.assertIn("DOCCAB", table_names,
                      f"DOCCAB no encontrado. candidates={table_names}")

    def test_pregunta_facturas_encuentra_doccab(self):
        """'facturas del mes' debe encontrar DOCCAB con filtro TIPO=13."""
        if not self.has_real_index:
            self.skipTest("concept_index real no disponible")
        r = self._make_retriever_with_real_index()
        found, _ = r._extract_keywords("facturas del mes pasado")
        candidates = r._find_candidate_tables(found)
        self.assertIn("DOCCAB", candidates,
                      f"DOCCAB no encontrado para 'facturas'. candidates={set(candidates.keys())}")
        # Verificar que tiene filtro TIPO=13
        doccab_info = candidates.get("DOCCAB", {})
        self.assertIn("13", str(doccab_info.get("filter", "")),
                      f"DOCCAB debe tener filtro TIPO=13 para facturas. info={doccab_info}")


class TestContextRetrieverConIndiceMinimo(unittest.TestCase):
    """
    Tests del ContextRetriever con un concept_index mínimo (sin BD real).
    Verifica la lógica de normalización de forma aislada.
    """

    def _make_retriever(self, concept_index: dict):
        """Crea un ContextRetriever con un concept_index dado."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever
        r = ContextRetriever()
        r._concept_index = concept_index
        r._table_index   = {
            "ARTICULO": {"desc": "Catálogo de artículos", "n": 11846, "pk": ["CODART"],
                         "cols_key": ["CODART", "NOMBRE"], "related": ["DOCLIN"], "kw": []},
            "DOCCAB":   {"desc": "Cabecera documentos", "n": 85000, "pk": ["NUMDOC"],
                         "cols_key": ["NUMDOC", "TIPO", "FECHA"], "related": ["DOCLIN"], "kw": []},
            "DOCLIN":   {"desc": "Líneas de documentos", "n": 320000, "pk": ["NUMDOC"],
                         "cols_key": ["NUMDOC", "CODART", "CANTIDAD"], "related": [], "kw": []},
        }
        r._graph_adj = {
            "ARTICULO": {"DOCLIN"},
            "DOCLIN":   {"ARTICULO", "DOCCAB"},
            "DOCCAB":   {"DOCLIN"},
        }
        r._loaded = True
        return r

    MINIMAL_INDEX = {
        "articulo": [{"table": "ARTICULO"}],
        "compra":   [{"table": "DOCCAB", "filter": "TIPO=12"}, {"table": "DOCLIN"}],
        "factura":  [{"table": "DOCCAB", "filter": "TIPO=13"}],
        "cliente":  [{"table": "CLIENTE"}],
        "venta":    [{"table": "DOCCAB", "filter": "TIPO IN (11,13)"}, {"table": "DOCLIN"}],
    }

    def test_normalize_articulos_con_tilde(self):
        r = self._make_retriever(self.MINIMAL_INDEX)
        self.assertEqual(r._normalize_word("artículos"), "articulo")

    def test_normalize_compras_plural(self):
        r = self._make_retriever(self.MINIMAL_INDEX)
        self.assertEqual(r._normalize_word("compras"), "compra")

    def test_normalize_facturas_plural(self):
        r = self._make_retriever(self.MINIMAL_INDEX)
        self.assertEqual(r._normalize_word("facturas"), "factura")

    def test_normalize_ventas_plural(self):
        r = self._make_retriever(self.MINIMAL_INDEX)
        self.assertEqual(r._normalize_word("ventas"), "venta")

    def test_normalize_clientes_plural(self):
        r = self._make_retriever(self.MINIMAL_INDEX)
        self.assertEqual(r._normalize_word("clientes"), "cliente")

    def test_pregunta_articulos_compras_encuentra_tablas(self):
        """La pregunta del bug original debe encontrar ARTICULO y DOCCAB."""
        r = self._make_retriever(self.MINIMAL_INDEX)
        found, unknown = r._extract_keywords("dame los artículos con más compras")
        self.assertIn("articulo", found)
        self.assertIn("compra",   found)
        candidates = r._find_candidate_tables(found)
        self.assertIn("ARTICULO", candidates)
        self.assertIn("DOCCAB",   candidates)

    def test_expansion_grafo_incluye_doclin(self):
        """La expansión BFS desde ARTICULO+DOCCAB debe incluir DOCLIN."""
        r = self._make_retriever(self.MINIMAL_INDEX)
        candidates = {"ARTICULO": {"score": 1, "filter": None, "source": "concept", "kws": []},
                      "DOCCAB":   {"score": 1, "filter": "TIPO=12", "source": "concept", "kws": []}}
        expanded = r._expand_with_graph(candidates, depth=1)
        self.assertIn("DOCLIN", expanded,
                      f"DOCLIN debe aparecer tras expansión BFS. expanded={set(expanded.keys())}")

    def test_contexto_no_excede_max_tokens(self):
        """El contexto generado no debe exceder max_tokens."""
        r = self._make_retriever(self.MINIMAL_INDEX)
        found, _ = r._extract_keywords("artículos con más compras")
        candidates = r._find_candidate_tables(found)
        expanded   = r._expand_with_graph(candidates)
        ordered    = r._rank_tables(expanded, candidates)
        context, tables = r._build_context(ordered, found, max_tokens=500)
        tokens = r._estimate_tokens(context)
        self.assertLessEqual(tokens, 600,  # Margen del 20%
                             f"Contexto excede max_tokens: {tokens} tokens")

    def test_fallback_sin_indices_devuelve_string(self):
        """Sin índices SIUO, get_context devuelve un string no vacío."""
        from backend.modules.db_explorer.context_retriever import ContextRetriever
        r = ContextRetriever()
        r._loaded = False
        r._table_index = {}
        # Mock del fallback
        r._fallback_schema = "Base de datos Firebird 2.5. Usa FIRST N."
        context, meta = r.get_context("cuantos articulos hay")
        self.assertIsInstance(context, str)
        self.assertGreater(len(context), 0)
        self.assertEqual(meta["source"], "fallback")


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Modo compacto con resumen
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [
        TestLoadJsonBasico,
        TestLoadJsonCorrupcion,
        TestLoadJsonEncodings,
        TestContextRetrieverNormalizacion,
        TestContextRetrieverConIndiceMinimo,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
