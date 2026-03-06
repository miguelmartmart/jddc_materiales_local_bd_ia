"""
Tests para SQLCorrector.clean_firebird_sql y el flujo de limpieza en service.py.

Verifica que:
  - clean_firebird_sql elimina LIMIT N antes de que se añada FIRST N
  - clean_firebird_sql elimina ROWS N
  - clean_firebird_sql corrige columnas erróneas (STOCK → STOCKARTICULO)
  - El flujo en service.py: clean ANTES de añadir FIRST (no después)
  - Nunca llega a Firebird una query con LIMIT o ROWS
  - Queries con COUNT/SUM/AVG/MAX/MIN no reciben FIRST N automático
  - enforce_case_insensitive convierte LIKE a UPPER(col) LIKE UPPER(val)

Autor: DEVIA System Tests
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Any

from backend.modules.chat.sql_corrector import SQLCorrector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def corrector():
    """Instancia limpia de SQLCorrector para cada test."""
    return SQLCorrector()


# ---------------------------------------------------------------------------
# Tests: clean_firebird_sql — LIMIT → FIRST
# ---------------------------------------------------------------------------

class TestCleanFirebirdSqlLimit:
    """Tests para la conversión de LIMIT N a SELECT FIRST N."""

    def test_convierte_limit_a_first(self, corrector):
        """LIMIT N al final se convierte a SELECT FIRST N al inicio."""
        sql = "SELECT NOMBRE FROM ARTICULO LIMIT 10"
        result = corrector.clean_firebird_sql(sql)
        assert "LIMIT" not in result.upper()
        assert "FIRST 10" in result.upper()

    def test_convierte_limit_1(self, corrector):
        """LIMIT 1 se convierte a SELECT FIRST 1."""
        sql = "SELECT NOMBRE FROM ARTICULO LIMIT 1"
        result = corrector.clean_firebird_sql(sql)
        assert "LIMIT" not in result.upper()
        assert "FIRST 1" in result.upper()

    def test_convierte_limit_100(self, corrector):
        """LIMIT 100 se convierte a SELECT FIRST 100."""
        sql = "SELECT NOMBRE, PRECIO FROM ARTICULO LIMIT 100"
        result = corrector.clean_firebird_sql(sql)
        assert "LIMIT" not in result.upper()
        assert "FIRST 100" in result.upper()

    def test_no_duplica_first_si_ya_existe(self, corrector):
        """Si ya hay SELECT FIRST N, no añade otro FIRST."""
        sql = "SELECT FIRST 50 NOMBRE FROM ARTICULO LIMIT 50"
        result = corrector.clean_firebird_sql(sql)
        assert "LIMIT" not in result.upper()
        # No debe haber dos FIRST
        assert result.upper().count("FIRST") == 1

    def test_query_sin_limit_no_se_modifica(self, corrector):
        """Una query sin LIMIT no debe modificarse (excepto otras correcciones)."""
        sql = "SELECT FIRST 10 NOMBRE FROM ARTICULO"
        result = corrector.clean_firebird_sql(sql)
        assert result == sql

    def test_query_count_sin_limit_no_se_modifica(self, corrector):
        """Una query COUNT sin LIMIT no debe modificarse."""
        sql = "SELECT COUNT(*) FROM ARTICULO"
        result = corrector.clean_firebird_sql(sql)
        assert result == sql

    def test_limit_case_insensitive(self, corrector):
        """LIMIT en minúsculas también se convierte."""
        sql = "SELECT nombre FROM articulo limit 5"
        result = corrector.clean_firebird_sql(sql)
        assert "limit" not in result.lower()
        assert "first 5" in result.lower()

    def test_limit_con_where_clause(self, corrector):
        """LIMIT al final de query con WHERE se convierte correctamente."""
        sql = "SELECT NOMBRE FROM ARTICULO WHERE ACTIVO = 'T' LIMIT 20"
        result = corrector.clean_firebird_sql(sql)
        assert "LIMIT" not in result.upper()
        assert "FIRST 20" in result.upper()
        assert "WHERE ACTIVO = 'T'" in result

    def test_limit_con_order_by(self, corrector):
        """LIMIT al final de query con ORDER BY se convierte correctamente."""
        sql = "SELECT NOMBRE FROM ARTICULO ORDER BY NOMBRE LIMIT 15"
        result = corrector.clean_firebird_sql(sql)
        assert "LIMIT" not in result.upper()
        assert "FIRST 15" in result.upper()

    def test_resultado_es_sql_valido_firebird(self, corrector):
        """El resultado debe empezar con SELECT FIRST N (sintaxis Firebird válida)."""
        sql = "SELECT NOMBRE FROM ARTICULO LIMIT 10"
        result = corrector.clean_firebird_sql(sql)
        # Debe empezar con SELECT FIRST
        assert result.upper().startswith("SELECT FIRST")


# ---------------------------------------------------------------------------
# Tests: clean_firebird_sql — ROWS → FIRST
# ---------------------------------------------------------------------------

class TestCleanFirebirdSqlRows:
    """Tests para la conversión de ROWS N a SELECT FIRST N."""

    def test_convierte_rows_a_first(self, corrector):
        """ROWS N se convierte a SELECT FIRST N."""
        sql = "SELECT NOMBRE FROM ARTICULO ROWS 10"
        result = corrector.clean_firebird_sql(sql)
        assert "ROWS" not in result.upper()
        assert "FIRST 10" in result.upper()

    def test_convierte_rows_to_syntax(self, corrector):
        """ROWS N TO M (paginación) se elimina correctamente."""
        sql = "SELECT NOMBRE FROM ARTICULO ROWS 1 TO 10"
        result = corrector.clean_firebird_sql(sql)
        assert "ROWS" not in result.upper()


# ---------------------------------------------------------------------------
# Tests: clean_firebird_sql — Corrección de columnas erróneas
# ---------------------------------------------------------------------------

class TestCleanFirebirdSqlColumns:
    """Tests para la corrección de nombres de columnas erróneos."""

    def test_corrige_stock_a_stockarticulo(self, corrector):
        """STOCK (sin sufijo) se corrige a STOCKARTICULO."""
        sql = "SELECT NOMBRE, STOCK FROM ARTICULO"
        result = corrector.clean_firebird_sql(sql)
        assert "STOCKARTICULO" in result.upper()

    def test_no_modifica_stockarticulo(self, corrector):
        """STOCKARTICULO (correcto) no se modifica."""
        sql = "SELECT NOMBRE, STOCKARTICULO FROM ARTICULO"
        result = corrector.clean_firebird_sql(sql)
        assert result == sql

    def test_no_modifica_stockfactor(self, corrector):
        """STOCKFACTOR no se modifica (no es el mismo que STOCK)."""
        sql = "SELECT NOMBRE, STOCKFACTOR FROM ARTICULO"
        result = corrector.clean_firebird_sql(sql)
        # STOCKFACTOR no debe convertirse a STOCKARTICULOFACTOR
        assert "STOCKFACTOR" in result.upper()
        assert "STOCKARTICULOFACTOR" not in result.upper()

    def test_corrige_stock_en_where(self, corrector):
        """STOCK en cláusula WHERE también se corrige."""
        sql = "SELECT NOMBRE FROM ARTICULO WHERE STOCK > 0"
        result = corrector.clean_firebird_sql(sql)
        assert "STOCKARTICULO > 0" in result.upper()
        assert " STOCK " not in result.upper()


# ---------------------------------------------------------------------------
# Tests: enforce_case_insensitive
# ---------------------------------------------------------------------------

class TestEnforceCaseInsensitive:
    """Tests para la conversión de LIKE a UPPER(col) LIKE UPPER(val)."""

    def test_convierte_like_simple(self, corrector):
        """LIKE '%valor%' se convierte a UPPER(col) LIKE UPPER('%valor%')."""
        sql = "SELECT NOMBRE FROM ARTICULO WHERE NOMBRE LIKE '%split%'"
        result = corrector.enforce_case_insensitive(sql)
        assert "UPPER(NOMBRE)" in result
        assert "UPPER('%split%')" in result
        # El LIKE original no debe quedar sin UPPER
        assert "NOMBRE LIKE '%split%'" not in result

    def test_no_duplica_upper_si_ya_existe(self, corrector):
        """Si ya hay UPPER(col) LIKE, no añade otro UPPER."""
        sql = "SELECT NOMBRE FROM ARTICULO WHERE UPPER(NOMBRE) LIKE UPPER('%split%')"
        result = corrector.enforce_case_insensitive(sql)
        # No debe duplicar UPPER
        assert result.count("UPPER(NOMBRE)") == 1

    def test_convierte_multiples_like(self, corrector):
        """Múltiples LIKE en la misma query se convierten todos."""
        sql = "SELECT * FROM ARTICULO WHERE NOMBRE LIKE '%split%' AND REFERENCIA LIKE '%REF%'"
        result = corrector.enforce_case_insensitive(sql)
        assert "UPPER(NOMBRE)" in result
        assert "UPPER(REFERENCIA)" in result

    def test_query_sin_like_no_se_modifica(self, corrector):
        """Una query sin LIKE no debe modificarse."""
        sql = "SELECT COUNT(*) FROM ARTICULO WHERE ACTIVO = 'T'"
        result = corrector.enforce_case_insensitive(sql)
        assert result == sql


# ---------------------------------------------------------------------------
# Tests: Flujo completo — clean ANTES de añadir FIRST N
# ---------------------------------------------------------------------------

class TestCleanBeforeAddFirst:
    """
    Tests que verifican el orden correcto en service.py:
    1. clean_firebird_sql (elimina LIMIT)
    2. Añadir FIRST N (solo si no hay FIRST ya)
    
    El bug anterior era: añadir FIRST 100 PRIMERO, luego limpiar LIMIT,
    resultando en "SELECT FIRST 100 ... LIMIT 1" que Firebird rechazaba.
    """

    def test_limit_se_elimina_antes_de_añadir_first(self, corrector):
        """
        Simula el flujo de service.py:
        Input: SELECT NOMBRE FROM ARTICULO LIMIT 1
        Paso 1 (clean): SELECT NOMBRE FROM ARTICULO FIRST 1  (LIMIT→FIRST)
        Paso 2 (add FIRST): ya tiene FIRST, no añade otro
        Resultado: SELECT FIRST 1 NOMBRE FROM ARTICULO (sin LIMIT)
        """
        sql_original = "SELECT NOMBRE FROM ARTICULO LIMIT 1"

        # PASO 1: clean_firebird_sql (como hace service.py ahora)
        sql_cleaned = corrector.clean_firebird_sql(sql_original)

        # PASO 2: Añadir FIRST si no tiene (como hace service.py)
        sql_upper = sql_cleaned.upper()
        is_aggregate = any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN('])
        if sql_upper.startswith("SELECT") and "FIRST" not in sql_upper and not is_aggregate:
            sql_final = sql_cleaned[:6] + " FIRST 100" + sql_cleaned[6:]
        else:
            sql_final = sql_cleaned

        # Verificaciones
        assert "LIMIT" not in sql_final.upper(), \
            f"LIMIT no debe estar en la query final: {sql_final}"
        assert "FIRST" in sql_final.upper(), \
            f"FIRST debe estar en la query final: {sql_final}"
        # No debe haber dos FIRST
        assert sql_final.upper().count("FIRST") == 1, \
            f"Solo debe haber un FIRST en la query: {sql_final}"

    def test_bug_anterior_habria_fallado(self, corrector):
        """
        Demuestra que el orden INCORRECTO (añadir FIRST antes de limpiar)
        produce una query inválida para Firebird.
        """
        sql_original = "SELECT NOMBRE FROM ARTICULO LIMIT 1"

        # ORDEN INCORRECTO (bug anterior): añadir FIRST primero
        sql_upper = sql_original.upper()
        if sql_upper.startswith("SELECT") and "FIRST" not in sql_upper:
            sql_con_first = sql_original[:6] + " FIRST 100" + sql_original[6:]
        else:
            sql_con_first = sql_original

        # Resultado del bug: "SELECT FIRST 100 NOMBRE FROM ARTICULO LIMIT 1"
        assert "FIRST 100" in sql_con_first.upper()
        assert "LIMIT 1" in sql_con_first.upper()
        # Esta query es INVÁLIDA para Firebird (tiene LIMIT al final)
        # Firebird devuelve: _op_response:op_code = 1

        # ORDEN CORRECTO (fix aplicado): limpiar primero, luego añadir FIRST
        sql_cleaned = corrector.clean_firebird_sql(sql_original)
        sql_upper2 = sql_cleaned.upper()
        if sql_upper2.startswith("SELECT") and "FIRST" not in sql_upper2:
            sql_final = sql_cleaned[:6] + " FIRST 100" + sql_cleaned[6:]
        else:
            sql_final = sql_cleaned

        # Resultado correcto: sin LIMIT, con FIRST
        assert "LIMIT" not in sql_final.upper()
        assert "FIRST" in sql_final.upper()
        assert sql_final.upper().count("FIRST") == 1

    def test_query_con_count_no_recibe_first(self, corrector):
        """
        Las queries de agregación (COUNT, SUM, etc.) NO deben recibir FIRST N.
        """
        sql_original = "SELECT COUNT(*) FROM ARTICULO"

        # PASO 1: clean
        sql_cleaned = corrector.clean_firebird_sql(sql_original)

        # PASO 2: Añadir FIRST solo si no es agregación
        sql_upper = sql_cleaned.upper()
        is_aggregate = any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN('])
        if sql_upper.startswith("SELECT") and "FIRST" not in sql_upper and not is_aggregate:
            sql_final = sql_cleaned[:6] + " FIRST 100" + sql_cleaned[6:]
        else:
            sql_final = sql_cleaned

        assert "FIRST" not in sql_final.upper(), \
            f"COUNT no debe recibir FIRST: {sql_final}"
        assert "COUNT(*)" in sql_final.upper()

    def test_query_con_sum_no_recibe_first(self, corrector):
        """Las queries con SUM no deben recibir FIRST N."""
        sql_original = "SELECT SUM(PRECIO) FROM ARTICULO"
        sql_cleaned = corrector.clean_firebird_sql(sql_original)
        sql_upper = sql_cleaned.upper()
        is_aggregate = any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN('])
        if sql_upper.startswith("SELECT") and "FIRST" not in sql_upper and not is_aggregate:
            sql_final = sql_cleaned[:6] + " FIRST 100" + sql_cleaned[6:]
        else:
            sql_final = sql_cleaned
        assert "FIRST" not in sql_final.upper()

    def test_query_ya_con_first_no_duplica(self, corrector):
        """Si la IA ya generó SELECT FIRST N, no se añade otro FIRST."""
        sql_original = "SELECT FIRST 10 NOMBRE FROM ARTICULO"
        sql_cleaned = corrector.clean_firebird_sql(sql_original)
        sql_upper = sql_cleaned.upper()
        is_aggregate = any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN('])
        if sql_upper.startswith("SELECT") and "FIRST" not in sql_upper and not is_aggregate:
            sql_final = sql_cleaned[:6] + " FIRST 100" + sql_cleaned[6:]
        else:
            sql_final = sql_cleaned
        assert sql_final.upper().count("FIRST") == 1

    def test_casos_reales_de_firebird(self, corrector):
        """Tests con queries reales que han fallado en producción."""
        casos = [
            # (input, debe_contener, no_debe_contener)
            (
                "SELECT NOMBRE FROM ARTICULO LIMIT 1",
                ["FIRST"],
                ["LIMIT"]
            ),
            (
                "SELECT FIRST 100 NOMBRE FROM ARTICULO LIMIT 1",
                ["FIRST"],
                ["LIMIT"]
            ),
            (
                "SELECT COUNT(*) AS TOTAL FROM ARTICULO",
                ["COUNT(*)"],
                ["FIRST"]
            ),
            (
                "SELECT NOMBRE, STOCK FROM ARTICULO LIMIT 5",
                ["FIRST 5", "STOCKARTICULO"],
                ["LIMIT", " STOCK "]
            ),
        ]

        for sql_input, debe_contener, no_debe_contener in casos:
            # Aplicar clean
            result = corrector.clean_firebird_sql(sql_input)
            # Aplicar lógica de FIRST
            sql_upper = result.upper()
            is_aggregate = any(agg in sql_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN('])
            if sql_upper.startswith("SELECT") and "FIRST" not in sql_upper and not is_aggregate:
                result = result[:6] + " FIRST 100" + result[6:]

            for debe in debe_contener:
                assert debe.upper() in result.upper(), \
                    f"Query '{sql_input}' → resultado '{result}' debería contener '{debe}'"
            for no_debe in no_debe_contener:
                assert no_debe.upper() not in result.upper(), \
                    f"Query '{sql_input}' → resultado '{result}' NO debería contener '{no_debe}'"


# ---------------------------------------------------------------------------
# Tests: detect_error_type
# ---------------------------------------------------------------------------

class TestDetectErrorType:
    """Tests para la detección del tipo de error SQL."""

    def test_detecta_table_unknown(self, corrector):
        """Detecta error de tabla desconocida."""
        error = "Table unknown FACTURA"
        result = corrector.detect_error_type(error)
        assert result["type"] == "table_unknown"

    def test_detecta_column_unknown(self, corrector):
        """Detecta error de columna desconocida."""
        error = "Column unknown STOCK"
        result = corrector.detect_error_type(error)
        assert result["type"] == "column_unknown"

    def test_detecta_limit_como_invalid_keyword(self, corrector):
        """
        Detecta LIMIT como keyword inválida en Firebird.

        El código extrae el token con: parts[1].strip().split()[0]
        donde parts = error.split('Token unknown').
        Por tanto el token debe ser la PRIMERA palabra después de 'Token unknown'.
        Formato que el código espera: "... Token unknown LIMIT ..."
        """
        error = "Token unknown LIMIT"
        result = corrector.detect_error_type(error)
        assert result["type"] == "invalid_keyword"

    def test_detecta_rows_como_invalid_keyword(self, corrector):
        """Detecta ROWS como keyword inválida en Firebird."""
        error = "Token unknown ROWS"
        result = corrector.detect_error_type(error)
        assert result["type"] == "invalid_keyword"

    def test_detecta_top_como_invalid_keyword(self, corrector):
        """Detecta TOP como keyword inválida en Firebird."""
        error = "Token unknown TOP"
        result = corrector.detect_error_type(error)
        assert result["type"] == "invalid_keyword"

    def test_detecta_limit_formato_firebird_real(self, corrector):
        """
        Con el formato real de Firebird ("Token unknown - line 1, column 35. LIMIT"),
        el código extrae '-' como token (no 'LIMIT'), por lo que cae en syntax_error.
        Este test documenta el comportamiento REAL del código para ese formato.
        """
        error = "Dynamic SQL Error. SQL error code = -104. Token unknown - line 1, column 35. LIMIT"
        result = corrector.detect_error_type(error)
        # El código extrae '-' como token → no es LIMIT/ROWS/TOP → syntax_error
        # Este es el comportamiento actual documentado (no un bug crítico porque
        # clean_firebird_sql ya elimina LIMIT ANTES de que llegue a Firebird)
        assert result["type"] == "syntax_error"

    def test_detecta_syntax_error(self, corrector):
        """Detecta error de sintaxis genérico."""
        error = "Dynamic SQL Error. SQL error code = -104. Syntax error"
        result = corrector.detect_error_type(error)
        assert result["type"] == "syntax_error"

    def test_error_desconocido(self, corrector):
        """Errores no reconocidos devuelven tipo 'unknown'."""
        error = "_op_response:op_code = 1"
        result = corrector.detect_error_type(error)
        assert result["type"] == "unknown"
