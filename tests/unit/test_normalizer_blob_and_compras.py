"""
tests/unit/test_normalizer_blob_and_compras.py
Tests unitarios para las correcciones deterministas nuevas:
  - BLOB en GROUP BY/SELECT → eliminar/sustituir
  - Patrón artículos más comprados sin JOIN → reescribir con JOIN DOCLIN
  - fix_after_error: corrección post-error sin IA

< 150 líneas · sin dependencias externas · pytest desde cualquier directorio
"""

import sys
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer


class TestBlobInGroupBy(unittest.TestCase):
    """Corrección determinista: BLOB en GROUP BY/SELECT."""

    def setUp(self):
        self.n = FirebirdSQLNormalizer()

    def _norm(self, sql):
        result, _ = self.n.normalize(sql)
        return result

    def test_descripcion_eliminada_de_groupby(self):
        """DESCRIPCION (BLOB) se elimina del GROUP BY."""
        sql = "SELECT FIRST 4 CODIGO, DESCRIPCION FROM ARTICULO GROUP BY CODIGO, DESCRIPCION ORDER BY COUNT(*) DESC"
        out = self._norm(sql)
        gb_part = out.upper().split("GROUP BY")[1].split("ORDER")[0] if "GROUP BY" in out.upper() else ""
        self.assertNotIn("DESCRIPCION", gb_part)
        self.assertIn("CODIGO", gb_part)

    def test_descripcion_sustituida_por_nombre_en_select(self):
        """DESCRIPCION (BLOB) en SELECT con GROUP BY → sustituida por NOMBRE."""
        sql = "SELECT FIRST 4 CODIGO, DESCRIPCION FROM ARTICULO GROUP BY CODIGO, DESCRIPCION ORDER BY COUNT(*) DESC"
        out = self._norm(sql)
        sel_part = out.upper().split("FROM")[0] if "FROM" in out.upper() else out.upper()
        self.assertIn("NOMBRE", sel_part)

    def test_sin_groupby_no_modifica(self):
        """Sin GROUP BY, DESCRIPCION no se toca."""
        sql = "SELECT FIRST 10 CODIGO, DESCRIPCION FROM ARTICULO WHERE BAJA = 'N'"
        out = self._norm(sql)
        self.assertIn("DESCRIPCION", out.upper())

    def test_observaciones_eliminada_de_groupby(self):
        """OBSERVACIONES (BLOB) se elimina del GROUP BY en DOCCAB."""
        sql = "SELECT FIRST 5 CODIGO, OBSERVACIONES FROM DOCCAB GROUP BY CODIGO, OBSERVACIONES"
        out = self._norm(sql)
        gb_part = out.upper().split("GROUP BY")[1] if "GROUP BY" in out.upper() else ""
        self.assertNotIn("OBSERVACIONES", gb_part)

    def test_fix_after_error_blob(self):
        """fix_after_error con error BLOB corrige el SQL sin IA."""
        sql = "SELECT FIRST 4 CODIGO, DESCRIPCION FROM ARTICULO GROUP BY CODIGO, DESCRIPCION ORDER BY COUNT(*) DESC"
        error = "conversion error from string BLOB"
        out, changes = self.n.fix_after_error(sql, error)
        self.assertTrue(len(changes) > 0, "Debe haber al menos un cambio")
        if "GROUP BY" in out.upper():
            gb = out.upper().split("GROUP BY")[1].split("ORDER")[0]
            self.assertNotIn("DESCRIPCION", gb)


class TestArticulosMasCompras(unittest.TestCase):
    """Corrección determinista: artículos más comprados sin JOIN → JOIN DOCLIN."""

    def setUp(self):
        self.n = FirebirdSQLNormalizer()

    def _norm(self, sql):
        result, _ = self.n.normalize(sql)
        return result

    def test_patron_sin_join_reescribe_con_doclin(self):
        """SELECT FROM ARTICULO GROUP BY ORDER BY COUNT(*) DESC → JOIN DOCLIN."""
        sql = "SELECT FIRST 4 CODIGO, NOMBRE FROM ARTICULO GROUP BY CODIGO, NOMBRE ORDER BY COUNT(*) DESC"
        out = self._norm(sql)
        self.assertIn("JOIN DOCLIN", out.upper())
        self.assertIn("NCOMPRAS", out.upper())

    def test_preserva_first_n(self):
        """El FIRST N original se preserva en la reescritura."""
        sql = "SELECT FIRST 7 CODIGO, NOMBRE FROM ARTICULO GROUP BY CODIGO, NOMBRE ORDER BY COUNT(*) DESC"
        out = self._norm(sql)
        self.assertIn("FIRST 7", out.upper())

    def test_con_join_existente_no_modifica(self):
        """Si ya tiene JOIN DOCLIN, no se modifica."""
        sql = (
            "SELECT FIRST 4 A.CODIGO, A.NOMBRE, COUNT(*) AS N "
            "FROM ARTICULO A JOIN DOCLIN L ON L.CODIGO = A.CODIGO "
            "GROUP BY A.CODIGO, A.NOMBRE ORDER BY N DESC"
        )
        out = self._norm(sql)
        self.assertEqual(out.upper().count("JOIN DOCLIN"), 1)

    def test_sin_groupby_no_modifica(self):
        """Sin GROUP BY, no se aplica la corrección."""
        sql = "SELECT FIRST 10 CODIGO, NOMBRE FROM ARTICULO ORDER BY NOMBRE"
        out = self._norm(sql)
        self.assertNotIn("JOIN DOCLIN", out.upper())

    def test_cambios_reportados(self):
        """normalize() reporta el cambio aplicado."""
        sql = "SELECT FIRST 4 CODIGO, NOMBRE FROM ARTICULO GROUP BY CODIGO, NOMBRE ORDER BY COUNT(*) DESC"
        _, changes = self.n.normalize(sql)
        self.assertTrue(
            any("DOCLIN" in c.upper() or "COMPRA" in c.upper() for c in changes),
            f"Se esperaba cambio sobre DOCLIN/compras. Cambios: {changes}"
        )


class TestFixAfterError(unittest.TestCase):
    """fix_after_error: correcciones post-error sin IA."""

    def setUp(self):
        self.n = FirebirdSQLNormalizer()

    def test_column_unknown_stock(self):
        """Column unknown STOCK → STOCKARTICULO."""
        sql = "SELECT FIRST 10 CODIGO, STOCK FROM ARTICULO"
        out, changes = self.n.fix_after_error(sql, "Column unknown STOCK")
        self.assertIn("STOCKARTICULO", out.upper())
        self.assertTrue(len(changes) > 0)

    def test_token_unknown_limit(self):
        """Token unknown LIMIT → SELECT FIRST N."""
        sql = "SELECT CODIGO FROM ARTICULO LIMIT 5"
        out, changes = self.n.fix_after_error(sql, "Token unknown LIMIT")
        self.assertIn("FIRST 5", out.upper())
        self.assertTrue(len(changes) > 0)

    def test_error_desconocido_no_cambia(self):
        """Error desconocido → SQL sin cambios."""
        sql = "SELECT FIRST 10 CODIGO FROM ARTICULO"
        out, changes = self.n.fix_after_error(sql, "some random unknown error xyz")
        self.assertEqual(out, sql)
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
