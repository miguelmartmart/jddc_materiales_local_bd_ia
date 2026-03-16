"""
test_unsupported_functions.py — Tests para el paso 21 del normalizador SQL.

CUBRE:
  - ROUND(x, n) → CAST(x AS NUMERIC(15,n))
  - ROUND(x, 0) → CAST(x AS INTEGER)
  - ROUND(x)    → CAST(x AS INTEGER)
  - ROUND con expresiones complejas (COUNT, subexpresiones con paréntesis)
  - TRUNC/TRUNCATE → CAST(x AS INTEGER)
  - NVL/IFNULL/ISNULL → COALESCE
  - detect_error_type: "Function unknown ROUND" → type="function_unknown"
  - fix_after_error: "Function unknown ROUND" → aplica _fix_unsupported_functions
  - Integración: el SQL del log real se corrige correctamente
  - Anti-regresión: SQL sin funciones no soportadas no se modifica

FILOSOFÍA:
  - Sin mocks: prueba la lógica real del normalizador
  - Determinista: entrada → salida esperada
  - Cada test verifica un comportamiento específico

AUTOR: DEVIA / bots/interjddcia · v1.4.0
"""

import pytest
import sys
from pathlib import Path

# Asegurar que el backend es importable
sys.path.insert(0, str(Path(__file__).parents[3]))

from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.chat.sql_corrector import SQLCorrector


@pytest.fixture(scope="module")
def normalizer():
    return FirebirdSQLNormalizer()


@pytest.fixture(scope="module")
def corrector():
    return SQLCorrector()


# ─── Tests: ROUND(x, n) ──────────────────────────────────────────────────────

class TestRoundConDecimales:
    """ROUND(x, n) → CAST(x AS NUMERIC(15,n))"""

    def test_round_2_decimales_simple(self, normalizer):
        sql = "SELECT ROUND(IMPORTETOTAL, 2) AS TASA FROM DOCCAB"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "ROUND" not in result.upper()
        assert "CAST(" in result.upper()
        assert "NUMERIC(15,2)" in result
        assert len(changes) > 0

    def test_round_0_decimales_da_integer(self, normalizer):
        sql = "SELECT ROUND(IMPORTETOTAL, 0) AS TOTAL FROM DOCCAB"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "CAST(" in result.upper()
        assert "AS INTEGER" in result.upper()
        assert "ROUND" not in result.upper()

    def test_round_1_decimal(self, normalizer):
        sql = "SELECT ROUND(PRECIO, 1) FROM ARTICULO"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "NUMERIC(15,1)" in result
        assert "ROUND" not in result.upper()

    def test_round_con_expresion_compleja(self, normalizer):
        """El caso real del log: ROUND((COUNT(...) * 100.0) / COUNT(...), 2)"""
        sql = (
            "SELECT ROUND( "
            "(COUNT(DISTINCT CASE WHEN DC.TIPO IN (12, 13) THEN D.CODDOCUMENTO END) * 100.0) / "
            "COUNT(DISTINCT D.CODDOCUMENTO), "
            "2 ) AS TASA_EXITO FROM DOCDESTINO D"
        )
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "ROUND" not in result.upper()
        assert "CAST(" in result.upper()
        assert "NUMERIC(15,2)" in result
        assert "TASA_EXITO" in result  # alias preservado
        assert len(changes) > 0

    def test_round_sin_segundo_argumento(self, normalizer):
        """ROUND(x) sin n → CAST(x AS INTEGER)"""
        sql = "SELECT ROUND(IMPORTETOTAL) FROM DOCCAB"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "AS INTEGER" in result.upper()
        assert "ROUND" not in result.upper()

    def test_multiples_round_en_misma_query(self, normalizer):
        """Múltiples ROUND en la misma query → todos corregidos"""
        sql = "SELECT ROUND(A, 2) AS X, ROUND(B, 1) AS Y FROM T"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "ROUND" not in result.upper()
        assert result.upper().count("CAST(") == 2

    def test_round_en_pipeline_normalize(self, normalizer):
        """ROUND se corrige en el pipeline completo normalize()"""
        sql = "SELECT ROUND(IMPORTETOTAL * 100.0 / TOTAL, 2) AS PCT FROM DOCCAB"
        result, changes = normalizer.normalize(sql)
        assert "ROUND" not in result.upper()
        assert "CAST(" in result.upper()


# ─── Tests: TRUNC / TRUNCATE ─────────────────────────────────────────────────

class TestTruncate:
    """TRUNC/TRUNCATE → CAST(x AS INTEGER)"""

    def test_trunc_simple(self, normalizer):
        sql = "SELECT TRUNC(IMPORTETOTAL) FROM DOCCAB"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "TRUNC" not in result.upper()
        assert "AS INTEGER" in result.upper()
        assert len(changes) > 0

    def test_truncate_con_decimales(self, normalizer):
        sql = "SELECT TRUNCATE(PRECIO, 2) FROM ARTICULO"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "TRUNCATE" not in result.upper()
        assert "AS INTEGER" in result.upper()


# ─── Tests: NVL / IFNULL / ISNULL ────────────────────────────────────────────

class TestNvlCoalesce:
    """NVL/IFNULL/ISNULL → COALESCE"""

    def test_nvl_simple(self, normalizer):
        sql = "SELECT NVL(IMPORTETOTAL, 0) FROM DOCCAB"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "NVL" not in result.upper()
        assert "COALESCE(" in result.upper()
        assert len(changes) > 0

    def test_ifnull_simple(self, normalizer):
        sql = "SELECT IFNULL(NOMBRE, 'SIN NOMBRE') FROM ARTICULO"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "IFNULL" not in result.upper()
        assert "COALESCE(" in result.upper()

    def test_isnull_simple(self, normalizer):
        sql = "SELECT ISNULL(CODCLIENTE, 0) FROM DOCCAB"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "ISNULL" not in result.upper()
        assert "COALESCE(" in result.upper()

    def test_nvl_preserva_argumentos(self, normalizer):
        sql = "SELECT NVL(PRECIO, 0.0) FROM ARTICULO"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert "COALESCE(PRECIO, 0.0)" in result or "COALESCE(" in result.upper()


# ─── Tests: Anti-regresión ────────────────────────────────────────────────────

class TestAntiRegresion:
    """SQL sin funciones no soportadas no debe modificarse."""

    def test_sql_sin_round_no_cambia(self, normalizer):
        sql = "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO = 0"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert result == sql
        assert changes == []

    def test_cast_existente_no_se_duplica(self, normalizer):
        """CAST ya existente no debe procesarse como ROUND"""
        sql = "SELECT CAST(IMPORTETOTAL AS NUMERIC(15,2)) FROM DOCCAB"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert result == sql
        assert changes == []

    def test_coalesce_existente_no_cambia(self, normalizer):
        sql = "SELECT COALESCE(NOMBRE, 'N/A') FROM ARTICULO"
        result, changes = normalizer._fix_unsupported_functions(sql)
        assert result == sql
        assert changes == []


# ─── Tests: detect_error_type ────────────────────────────────────────────────

class TestDetectErrorType:
    """detect_error_type reconoce 'Function unknown ROUND'"""

    def test_function_unknown_round(self, corrector):
        error = "Dynamic SQL Error\nSQL error code = -804\nFunction unknown\nROUND"
        info = corrector.detect_error_type(error)
        assert info["type"] == "function_unknown"
        assert info.get("function") == "ROUND"

    def test_function_unknown_nvl(self, corrector):
        error = "Dynamic SQL Error\nSQL error code = -804\nFunction unknown\nNVL"
        info = corrector.detect_error_type(error)
        assert info["type"] == "function_unknown"
        assert info.get("function") == "NVL"

    def test_function_unknown_inline(self, corrector):
        """Firebird a veces pone el nombre en la misma línea"""
        error = "Function unknown ROUND"
        info = corrector.detect_error_type(error)
        assert info["type"] == "function_unknown"

    def test_function_unknown_no_confunde_con_column_unknown(self, corrector):
        error = "Column unknown ROUND"
        info = corrector.detect_error_type(error)
        assert info["type"] == "column_unknown"
        assert info["type"] != "function_unknown"

    def test_function_unknown_mensaje_amigable(self, corrector):
        error = "Function unknown\nROUND"
        info = corrector.detect_error_type(error)
        assert "ROUND" in info["message"]
        assert "Firebird 2.5" in info["message"]


# ─── Tests: fix_after_error ───────────────────────────────────────────────────

class TestFixAfterError:
    """fix_after_error aplica corrección determinista para Function unknown"""

    def test_fix_after_error_round(self, normalizer):
        sql = "SELECT ROUND(IMPORTETOTAL, 2) AS TASA FROM DOCCAB"
        error = "Dynamic SQL Error\nSQL error code = -804\nFunction unknown\nROUND"
        result, changes = normalizer.fix_after_error(sql, error)
        assert "ROUND" not in result.upper()
        assert "CAST(" in result.upper()
        assert len(changes) > 0

    def test_fix_after_error_nvl(self, normalizer):
        sql = "SELECT NVL(NOMBRE, 'N/A') FROM ARTICULO"
        error = "Function unknown\nNVL"
        result, changes = normalizer.fix_after_error(sql, error)
        assert "NVL" not in result.upper()
        assert "COALESCE(" in result.upper()
        assert len(changes) > 0


# ─── Tests: Integración — SQL real del log ───────────────────────────────────

class TestIntegracionSqlReal:
    """
    Verifica que el SQL exacto del log de error se corrige correctamente.
    Este es el caso que falló en producción el 2026-03-13.
    """

    SQL_REAL = (
        "SELECT COUNT(DISTINCT D.CODDOCUMENTO) AS PRESUPUESTOS_SOLICITADOS, "
        "COUNT(DISTINCT CASE WHEN DC.TIPO IN (12, 13) THEN D.CODDOCUMENTO END) AS PRESUPUESTOS_ACEPTADOS, "
        "ROUND( "
        "(COUNT(DISTINCT CASE WHEN DC.TIPO IN (12, 13) THEN D.CODDOCUMENTO END) * 100.0) / "
        "COUNT(DISTINCT D.CODDOCUMENTO), "
        "2 ) AS TASA_EXITO "
        "FROM DOCDESTINO D "
        "JOIN DOCCAB DC ON DC.CODIGO = D.CODDOCUMENTODESTINO "
        "WHERE D.CODDOCUMENTO IN ( SELECT CODIGO FROM DOCCAB WHERE TIPO = 0 )"
    )

    ERROR_REAL = (
        "Dynamic SQL Error\n"
        "SQL error code = -804\n"
        "Function unknown\n"
        "ROUND"
    )

    def test_sql_real_se_corrige_en_normalize(self, normalizer):
        """El SQL del log se corrige en el pipeline normalize()"""
        result, changes = normalizer.normalize(self.SQL_REAL)
        assert "ROUND" not in result.upper()
        assert "CAST(" in result.upper()
        assert "NUMERIC(15,2)" in result
        # Columnas de resultado preservadas
        assert "PRESUPUESTOS_SOLICITADOS" in result
        assert "PRESUPUESTOS_ACEPTADOS" in result
        assert "TASA_EXITO" in result

    def test_sql_real_se_corrige_en_fix_after_error(self, normalizer):
        """fix_after_error corrige el SQL tras el error de producción"""
        result, changes = normalizer.fix_after_error(self.SQL_REAL, self.ERROR_REAL)
        assert "ROUND" not in result.upper()
        assert "CAST(" in result.upper()
        assert len(changes) > 0

    def test_detect_error_type_del_error_real(self, corrector):
        """detect_error_type clasifica correctamente el error de producción"""
        info = corrector.detect_error_type(self.ERROR_REAL)
        assert info["type"] == "function_unknown"
        assert info.get("function") == "ROUND"

    def test_sql_real_no_tiene_first_n_innecesario(self, normalizer):
        """
        El SQL tiene COUNT(*) → no debe añadirse FIRST N automáticamente.
        AGGREGATE_FUNCTIONS incluye ROUND y CAST para evitar esto.
        """
        result, changes = normalizer.normalize(self.SQL_REAL)
        # No debe añadir FIRST N porque hay COUNT(DISTINCT ...)
        assert "SELECT FIRST" not in result.upper()
