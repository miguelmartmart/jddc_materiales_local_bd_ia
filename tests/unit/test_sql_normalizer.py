"""
test_sql_normalizer.py — Tests unitarios del FirebirdSQLNormalizer.

CAPA: unit (sin BD, sin IA, sin red)
MÓDULO: backend.modules.chat.firebird_sql_normalizer
EJECUTAR: .venv/Scripts/pytest tests/unit/test_sql_normalizer.py -v -s

PROPÓSITO:
  Verificar que el normalizador corrige automáticamente los errores
  más comunes que comete la IA al generar SQL para Firebird:
  - LIMIT/TOP/ROWS → FIRST N
  - LIKE → UPPER(col) LIKE UPPER(val)
  - ILIKE → UPPER(col) LIKE UPPER(val)
  - != → <>
  - NOW()/GETDATE() → CURRENT_TIMESTAMP
  - CONCAT(a,b) → a || b
  - Backticks → sin comillas
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer


@pytest.fixture
def n() -> FirebirdSQLNormalizer:
    return FirebirdSQLNormalizer()


def norm(sql: str):
    """Helper: normaliza y devuelve (sql_normalizado, cambios)."""
    normalizer = FirebirdSQLNormalizer()
    return normalizer.normalize(sql)


# ═══════════════════════════════════════════════════════════════════════════════
# LIMIT → FIRST
# ═══════════════════════════════════════════════════════════════════════════════

class TestLimitToFirst:
    def test_limit_al_final(self):
        sql, changes = norm("SELECT * FROM ARTICULO LIMIT 10")
        assert "LIMIT" not in sql
        assert "FIRST 10" in sql
        assert len(changes) > 0

    def test_limit_con_offset(self):
        sql, changes = norm("SELECT * FROM ARTICULO LIMIT 10 OFFSET 20")
        assert "LIMIT" not in sql
        assert "FIRST 10" in sql

    def test_top_al_inicio(self):
        sql, changes = norm("SELECT TOP 5 * FROM DOCCAB WHERE TIPO=13")
        assert "TOP" not in sql
        assert "FIRST 5" in sql

    def test_rows_firebird_antiguo(self):
        sql, changes = norm("SELECT * FROM ARTICULO ROWS 10")
        assert "ROWS" not in sql or "FIRST" in sql

    def test_sql_ya_con_first_no_cambia(self):
        sql = "SELECT FIRST 10 CODART, NOMBRE FROM ARTICULO ORDER BY NOMBRE"
        result, changes = norm(sql)
        assert "FIRST 10" in result
        # No debe duplicar FIRST
        assert result.count("FIRST") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# LIKE → UPPER (case insensitive)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLikeToUpper:
    def test_like_simple(self):
        sql, changes = norm("SELECT * FROM ARTICULO WHERE NOMBRE LIKE '%split%'")
        assert "UPPER" in sql.upper()

    def test_ilike_se_convierte(self):
        sql, changes = norm("SELECT * FROM CLIENTE WHERE RAZONSOCIAL ILIKE '%garcia%'")
        assert "ILIKE" not in sql
        assert "UPPER" in sql.upper()

    def test_like_ya_con_upper_no_duplica(self):
        sql = "SELECT * FROM ARTICULO WHERE UPPER(NOMBRE) LIKE UPPER('%split%')"
        result, changes = norm(sql)
        # No debe duplicar UPPER
        assert result.upper().count("UPPER(NOMBRE)") <= 2


# ═══════════════════════════════════════════════════════════════════════════════
# Operadores
# ═══════════════════════════════════════════════════════════════════════════════

class TestOperadores:
    def test_distinto_se_convierte(self):
        sql, changes = norm("SELECT * FROM ARTICULO WHERE TIPO != 0")
        assert "!=" not in sql
        assert "<>" in sql

    def test_igual_no_cambia(self):
        sql, changes = norm("SELECT * FROM ARTICULO WHERE TIPO = 13")
        assert "TIPO = 13" in sql or "TIPO=13" in sql


# ═══════════════════════════════════════════════════════════════════════════════
# Funciones de fecha
# ═══════════════════════════════════════════════════════════════════════════════

class TestFechas:
    def test_now_se_convierte(self):
        sql, changes = norm("SELECT * FROM DOCCAB WHERE FECHA > NOW()")
        assert "NOW()" not in sql
        assert "CURRENT" in sql.upper()

    def test_getdate_se_convierte(self):
        sql, changes = norm("SELECT * FROM DOCCAB WHERE FECHA > GETDATE()")
        assert "GETDATE()" not in sql

    def test_sysdate_se_convierte(self):
        sql, changes = norm("SELECT * FROM DOCCAB WHERE FECHA > SYSDATE")
        assert "SYSDATE" not in sql


# ═══════════════════════════════════════════════════════════════════════════════
# Backticks
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackticks:
    def test_backticks_se_eliminan(self):
        sql, changes = norm("SELECT `NOMBRE`, `PRECIO` FROM `ARTICULO`")
        assert "`" not in sql
        assert "NOMBRE" in sql
        assert "ARTICULO" in sql


# ═══════════════════════════════════════════════════════════════════════════════
# SQL correcto no cambia
# ═══════════════════════════════════════════════════════════════════════════════

class TestSQLCorrecto:
    def test_select_first_correcto(self):
        sql = "SELECT FIRST 10 CODART, NOMBRE, PRECIO FROM ARTICULO ORDER BY PRECIO DESC"
        result, changes = norm(sql)
        assert "FIRST 10" in result
        assert "ARTICULO" in result

    def test_join_correcto(self):
        sql = (
            "SELECT FIRST 10 a.NOMBRE, SUM(l.CANTIDAD) as TOTAL "
            "FROM DOCLIN l "
            "JOIN ARTICULO a ON a.CODART = l.CODART "
            "JOIN DOCCAB d ON d.NUMDOC = l.NUMDOC "
            "WHERE d.TIPO IN (11, 13) "
            "GROUP BY a.NOMBRE "
            "ORDER BY TOTAL DESC"
        )
        result, changes = norm(sql)
        assert "FIRST 10" in result
        assert "DOCLIN" in result
        assert "ARTICULO" in result
        assert "DOCCAB" in result

    def test_facturas_tipo_13(self):
        sql = "SELECT FIRST 5 NUMDOC, FECHA, TOTAL FROM DOCCAB WHERE TIPO=13 ORDER BY FECHA DESC"
        result, changes = norm(sql)
        assert "TIPO=13" in result or "TIPO = 13" in result
        assert "FIRST 5" in result

    def test_upper_like_correcto(self):
        sql = "SELECT * FROM ARTICULO WHERE UPPER(NOMBRE) LIKE UPPER('%split%')"
        result, changes = norm(sql)
        assert "UPPER" in result.upper()
        assert "LIKE" in result.upper()

    def test_extract_fecha_correcto(self):
        sql = (
            "SELECT FIRST 10 NUMDOC, TOTAL FROM DOCCAB "
            "WHERE TIPO=13 "
            "AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE) "
            "ORDER BY FECHA DESC"
        )
        result, changes = norm(sql)
        assert "EXTRACT" in result
        assert "CURRENT_DATE" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SQL típicos de preguntas de negocio
# ═══════════════════════════════════════════════════════════════════════════════

class TestSQLNegocio:
    """SQL típicos que genera la IA para preguntas de negocio."""

    def test_articulos_mas_vendidos(self):
        sql = (
            "SELECT a.NOMBRE, SUM(l.CANTIDAD) as TOTAL_VENDIDO "
            "FROM DOCLIN l JOIN ARTICULO a ON a.CODART=l.CODART "
            "JOIN DOCCAB d ON d.NUMDOC=l.NUMDOC "
            "WHERE d.TIPO IN (11,13) "
            "GROUP BY a.NOMBRE ORDER BY TOTAL_VENDIDO DESC LIMIT 10"
        )
        result, changes = norm(sql)
        assert "LIMIT" not in result
        assert "FIRST 10" in result

    def test_ventas_por_agente(self):
        sql = (
            "SELECT TOP 20 ag.NOMBRE, SUM(d.TOTAL) as VENTAS "
            "FROM DOCCAB d JOIN AGENTE ag ON ag.CODAGENTE=d.CODAGENTE "
            "WHERE d.TIPO IN (11,13) GROUP BY ag.NOMBRE ORDER BY VENTAS DESC"
        )
        result, changes = norm(sql)
        assert "TOP" not in result
        assert "FIRST 20" in result

    def test_busqueda_cliente_por_nombre(self):
        sql = "SELECT * FROM CLIENTE WHERE RAZONSOCIAL LIKE '%garcia%'"
        result, changes = norm(sql)
        assert "UPPER" in result.upper()

    def test_stock_articulos(self):
        sql = "SELECT CODART, NOMBRE, STOCK FROM ARTICULO WHERE STOCK > 0 ORDER BY STOCK DESC LIMIT 50"
        result, changes = norm(sql)
        assert "LIMIT" not in result
        assert "FIRST 50" in result
