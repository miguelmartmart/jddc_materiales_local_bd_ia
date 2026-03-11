"""
tests/unit/test_normalizer.py
Tests unitarios del FirebirdSQLNormalizer.

CUBRE:
  - SQL multilínea → una línea
  - LIMIT/TOP/ROWS → FIRST N
  - Añade FIRST N si falta (no en agregaciones)
  - ILIKE / LIKE → UPPER(col) LIKE UPPER(val)
  - != → <>, TRUE/FALSE → 'T'/'F'
  - NOW()/CURRENT_DATE() → CURRENT_TIMESTAMP/CURRENT_DATE
  - CONCAT(a,b) → a || b
  - OFFSET eliminado, backticks eliminados, punto y coma eliminado
  - Columnas erróneas conocidas (STOCK → STOCKARTICULO)
  - Comentarios eliminados

PRINCIPIOS:
  - Usa import estándar (no importlib con rutas relativas)
  - Compatible con pytest desde cualquier directorio
  - < 200 líneas
"""

import sys
import os
import unittest

# ─── Setup del path ───────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestFirebirdSQLNormalizer(unittest.TestCase):
    """Tests unitarios del FirebirdSQLNormalizer."""

    def setUp(self):
        self.n = FirebirdSQLNormalizer()

    def _normalize(self, sql: str) -> str:
        """Normaliza y devuelve el SQL resultante."""
        result, _ = self.n.normalize(sql)
        return result

    def test_multilinea_con_limit_a_first_n(self):
        """SQL multilínea con LIMIT → FIRST N en una línea."""
        sql = "SELECT\n    CODIGO,\n    NOMBRE\nFROM ARTICULO\nLIMIT 10"
        out = self._normalize(sql)
        self.assertIn("SELECT FIRST 10", out.upper())

    def test_multilinea_sin_limit_anade_first_100(self):
        """SQL multilínea sin LIMIT → añade FIRST 100."""
        sql = "SELECT\n    CODIGO,\n    NOMBRE\nFROM ARTICULO"
        out = self._normalize(sql)
        self.assertIn("FIRST 100", out.upper())

    def test_like_sin_upper_anade_upper(self):
        """LIKE sin UPPER → añade UPPER()."""
        sql = "SELECT CODIGO FROM ARTICULO WHERE NOMBRE LIKE '%split%'"
        out = self._normalize(sql)
        self.assertIn("UPPER(NOMBRE) LIKE UPPER", out.upper())

    def test_ilike_a_upper_like(self):
        """ILIKE → UPPER(col) LIKE UPPER(val)."""
        sql = "SELECT CODIGO FROM ARTICULO WHERE NOMBRE ILIKE '%split%'"
        out = self._normalize(sql)
        self.assertIn("UPPER(NOMBRE) LIKE UPPER", out.upper())

    def test_stock_a_stockarticulo(self):
        """STOCK → STOCKARTICULO."""
        sql = "SELECT STOCK FROM ARTICULO WHERE STOCK > 0"
        out = self._normalize(sql)
        self.assertIn("STOCKARTICULO", out.upper())

    def test_backticks_eliminados(self):
        """Backticks eliminados."""
        sql = "SELECT `CODIGO`, `NOMBRE` FROM `ARTICULO`"
        out = self._normalize(sql)
        self.assertNotIn("`", out)
        self.assertIn("CODIGO", out.upper())
        self.assertIn("ARTICULO", out.upper())

    def test_distinto_a_diferente(self):
        """!= → <>."""
        sql = "SELECT CODIGO FROM ARTICULO WHERE TIPO != 0"
        out = self._normalize(sql)
        self.assertIn("<>", out)
        self.assertNotIn("!=", out)

    def test_true_false_a_t_f(self):
        """TRUE/FALSE → 'T'/'F'."""
        sql = "SELECT CODIGO FROM ARTICULO WHERE CONTROLSTOCK = TRUE"
        out = self._normalize(sql)
        self.assertIn("'T'", out)
        self.assertNotIn("TRUE", out.upper())

    def test_now_a_current_timestamp(self):
        """NOW() → CURRENT_TIMESTAMP."""
        sql = "SELECT CODIGO FROM DOCCAB WHERE FECHA < NOW()"
        out = self._normalize(sql)
        self.assertIn("CURRENT_TIMESTAMP", out.upper())
        self.assertNotIn("NOW()", out.upper())

    def test_current_date_parentesis_eliminados(self):
        """CURRENT_DATE() → CURRENT_DATE (sin paréntesis)."""
        sql = "SELECT CODIGO FROM DOCCAB WHERE FECHA = CURRENT_DATE()"
        out = self._normalize(sql)
        self.assertIn("CURRENT_DATE", out.upper())
        self.assertNotIn("CURRENT_DATE()", out.upper())

    def test_top_n_a_first_n(self):
        """SELECT TOP N → SELECT FIRST N."""
        sql = "SELECT TOP 5 CODIGO, NOMBRE FROM ARTICULO"
        out = self._normalize(sql)
        self.assertIn("SELECT FIRST 5", out.upper())
        self.assertNotIn("TOP", out.upper())

    def test_offset_eliminado(self):
        """OFFSET eliminado."""
        sql = "SELECT FIRST 10 CODIGO FROM ARTICULO OFFSET 20"
        out = self._normalize(sql)
        self.assertNotIn("OFFSET", out.upper())

    def test_punto_y_coma_eliminado(self):
        """Punto y coma al final eliminado."""
        sql = "SELECT FIRST 10 CODIGO FROM ARTICULO;"
        out = self._normalize(sql)
        self.assertFalse(out.rstrip().endswith(";"),
                         f"El SQL no debe terminar en ';': {out!r}")

    def test_agregacion_count_no_anade_first(self):
        """Agregación COUNT → NO añade FIRST."""
        sql = "SELECT COUNT(*) FROM ARTICULO"
        out = self._normalize(sql)
        self.assertNotIn("FIRST", out.upper())
        self.assertIn("COUNT(*)", out.upper())

    def test_comentarios_eliminados(self):
        """Comentarios SQL (--) eliminados."""
        sql = "SELECT CODIGO -- esto es un comentario\nFROM ARTICULO"
        out = self._normalize(sql)
        self.assertNotIn("--", out)
        self.assertIn("ARTICULO", out.upper())

    def test_concat_a_concatenacion_firebird(self):
        """CONCAT(a,b) → a || b."""
        sql = "SELECT CONCAT(NOMBRE, DESCRIPCIONCORTA) FROM ARTICULO"
        out = self._normalize(sql)
        self.assertIn("||", out)

    def test_normalizer_devuelve_cambios(self):
        """normalize() devuelve lista de cambios aplicados."""
        sql = "SELECT CODIGO FROM ARTICULO LIMIT 5"
        result, changes = self.n.normalize(sql)
        self.assertIsInstance(changes, list)
        # Debe haber al menos un cambio (LIMIT → FIRST)
        self.assertGreater(len(changes), 0,
                           f"Se esperaban cambios pero no hubo ninguno. SQL: {result!r}")


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
