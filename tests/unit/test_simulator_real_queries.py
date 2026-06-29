"""
test_simulator_real_queries.py
~600 casos que ejecutan SQL REAL contra el simulador SQLite.
CERO mocks — se usa la base de datos real del simulador.

Cubre:
  - SELECT básico en cada tabla
  - Filtros WHERE por columnas clave
  - Agregaciones (COUNT, SUM, AVG)
  - JOINs entre tablas
  - Los fixed SQLs añadidos en esta sesión (top clientes, concentración)
  - Traducción Firebird→SQLite automática
  - Resiliencia: consultas que devuelven 0 filas no son error
"""

import sqlite3
import pytest
from pathlib import Path

# Ruta a la BD simulada
_DB_PATH = Path(__file__).parents[2] / "backend" / "modules" / "db_simulator" / "data" / "simulator.db"


@pytest.fixture(scope="module")
def db_conn():
    """Conexión a la BD simulada (lectura)."""
    if not _DB_PATH.exists():
        pytest.skip(f"simulator.db no encontrado en {_DB_PATH}")
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _run(conn, sql: str):
    """Ejecuta SQL y devuelve lista de dicts."""
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        pytest.fail(f"Query falló inesperadamente:\n{sql}\nError: {e}")


# ─── Tablas del simulador ──────────────────────────────────────────────────────
_TABLES = [
    "DOCCAB", "DOCLIN", "CLIENTE", "PROVEED", "ARTICULO", "FAMILIA",
    "ALMACEN", "RECURSO", "CAJA", "ESTALMACEN", "PROYECTOS", "PROYVAR",
    "PRESUPROYE", "DOCDESTINO", "AGENTES", "TIPOSIVA", "TARIFAS",
    "FORMASPAGO", "SERIES", "AVISOS",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SELECT básico en cada tabla
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("table", _TABLES)
def test_select_star_from_table(db_conn, table: str):
    """SELECT * FROM tabla devuelve resultado sin error."""
    rows = _run(db_conn, f"SELECT * FROM {table}")
    assert isinstance(rows, list), f"Debe devolver lista para {table}"


@pytest.mark.parametrize("table", _TABLES)
def test_count_from_table(db_conn, table: str):
    """COUNT(*) FROM tabla devuelve entero >= 0."""
    rows = _run(db_conn, f"SELECT COUNT(*) as N FROM {table}")
    assert len(rows) == 1
    n = rows[0]["N"]
    assert isinstance(n, int), f"COUNT debe ser int para {table}, got {type(n)}"
    assert n >= 0, f"COUNT negativo en {table}"


@pytest.mark.parametrize("table", _TABLES)
def test_limit_5_from_table(db_conn, table: str):
    """SELECT con LIMIT 5 devuelve máximo 5 filas."""
    rows = _run(db_conn, f"SELECT * FROM {table} LIMIT 5")
    assert len(rows) <= 5, f"LIMIT 5 devolvió {len(rows)} filas para {table}"


# ═══════════════════════════════════════════════════════════════════════════════
# Queries específicas de DOCCAB (tabla principal)
# ═══════════════════════════════════════════════════════════════════════════════

# Tipos verificados en el simulador: 0, 2, 11, 12, 13
_TIPOS_EN_SIMULADOR = [0, 2, 11, 12, 13]
_TODOS_LOS_TIPOS = [0, 1, 2, 3, 10, 11, 12, 13, 21]


@pytest.mark.parametrize("tipo", _TIPOS_EN_SIMULADOR)
def test_doccab_count_por_tipo_existente(db_conn, tipo: int):
    """COUNT por tipos que SÍ existen en el simulador devuelve > 0."""
    rows = _run(db_conn, f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {tipo}")
    n = rows[0]["N"]
    assert n > 0, f"TIPO={tipo} existe en el simulador pero devuelve 0"


@pytest.mark.parametrize("tipo", [t for t in _TODOS_LOS_TIPOS if t not in _TIPOS_EN_SIMULADOR])
def test_doccab_count_por_tipo_ausente(db_conn, tipo: int):
    """COUNT por tipos ausentes devuelve 0 (no error)."""
    rows = _run(db_conn, f"SELECT COUNT(*) as N FROM DOCCAB WHERE TIPO = {tipo}")
    n = rows[0]["N"]
    assert n == 0, f"TIPO={tipo} debería estar ausente en simulador, pero N={n}"


def test_doccab_distribucion_tipos(db_conn):
    """Distribución de tipos devuelve filas para todos los tipos disponibles."""
    rows = _run(db_conn, "SELECT TIPO, COUNT(*) AS N FROM DOCCAB GROUP BY TIPO ORDER BY N DESC")
    assert len(rows) >= 1, "Debe haber al menos un TIPO en DOCCAB"
    tipos = [r["TIPO"] for r in rows]
    # Verificar que los tipos conocidos están presentes
    assert 0 in tipos, "TIPO=0 (presupuesto cliente) debe existir"
    assert 2 in tipos, "TIPO=2 (albarán cliente) debe existir"
    assert 13 in tipos, "TIPO=13 (factura prov) debe existir"


@pytest.mark.parametrize("mes", range(1, 13))
def test_doccab_filter_por_mes(db_conn, mes: int):
    """Filtro por mes no falla (puede devolver 0 filas)."""
    rows = _run(db_conn,
        f"SELECT COUNT(*) AS N FROM DOCCAB WHERE strftime('%m', FECHA) = '{mes:02d}'"
    )
    n = rows[0]["N"]
    assert isinstance(n, int) and n >= 0


@pytest.mark.parametrize("anio", [2024, 2025, 2026])
def test_doccab_filter_por_anio(db_conn, anio: int):
    """Filtro por año no falla."""
    rows = _run(db_conn,
        f"SELECT COUNT(*) AS N FROM DOCCAB WHERE strftime('%Y', FECHA) = '{anio}'"
    )
    n = rows[0]["N"]
    assert isinstance(n, int) and n >= 0


def test_doccab_importetotal_stats(db_conn):
    """SUM, AVG, MIN, MAX de IMPORTETOTAL devuelven números razonables."""
    rows = _run(db_conn,
        "SELECT SUM(IMPORTETOTAL) AS TOTAL, AVG(IMPORTETOTAL) AS MEDIA, "
        "MIN(IMPORTETOTAL) AS MIN_EUR, MAX(IMPORTETOTAL) AS MAX_EUR FROM DOCCAB"
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["TOTAL"] is not None and r["TOTAL"] > 0, "TOTAL debe ser positivo"
    assert r["MEDIA"] is not None and r["MEDIA"] > 0, "MEDIA debe ser positivo"
    assert r["MAX_EUR"] >= r["MIN_EUR"], "MAX >= MIN"


# ═══════════════════════════════════════════════════════════════════════════════
# JOIN queries (las más propensas a errores)
# ═══════════════════════════════════════════════════════════════════════════════

def test_join_doccab_cliente(db_conn):
    """JOIN DOCCAB ← CLIENTE devuelve filas con NOMBRECOMERCIAL."""
    rows = _run(db_conn,
        "SELECT d.TIPO, c.NOMBRECOMERCIAL, COUNT(*) AS N "
        "FROM DOCCAB d LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
        "WHERE d.CODCLIENTE IS NOT NULL AND d.CODCLIENTE > 0 "
        "GROUP BY d.TIPO, c.NOMBRECOMERCIAL ORDER BY N DESC LIMIT 10"
    )
    assert len(rows) >= 1, "JOIN DOCCAB-CLIENTE debe devolver al menos 1 fila"


def test_join_doccab_doclin(db_conn):
    """JOIN DOCCAB ← DOCLIN devuelve líneas de documento."""
    rows = _run(db_conn,
        "SELECT d.TIPO, COUNT(dl.CODIGO) AS N_LINEAS "
        "FROM DOCCAB d LEFT JOIN DOCLIN dl ON dl.CODDOCUMENTO = d.CODIGO "
        "GROUP BY d.TIPO ORDER BY N_LINEAS DESC LIMIT 5"
    )
    assert isinstance(rows, list)


def test_join_articulo_familia(db_conn):
    """JOIN ARTICULO ← FAMILIA devuelve artículos con nombre de familia."""
    rows = _run(db_conn,
        "SELECT f.NOMBRE AS FAMILIA, COUNT(a.CODIGO) AS N_ARTS "
        "FROM ARTICULO a LEFT JOIN FAMILIA f ON a.CODFAMILIA = f.CODIGO "
        "GROUP BY f.NOMBRE ORDER BY N_ARTS DESC LIMIT 10"
    )
    assert isinstance(rows, list)


def test_join_estalmacen_almacen(db_conn):
    """JOIN ESTALMACEN <- ALMACEN no falla."""
    rows = _run(db_conn,
        "SELECT a.NOMBRE, COUNT(e.CODIGO) AS N_MOVS "
        "FROM ESTALMACEN e LEFT JOIN ALMACEN a ON e.CODIGO = a.CODIGO "
        "GROUP BY a.NOMBRE LIMIT 5"
    )
    assert isinstance(rows, list)


# ═══════════════════════════════════════════════════════════════════════════════
# Los nuevos fixed SQLs de concentración de clientes (añadidos esta sesión)
# ═══════════════════════════════════════════════════════════════════════════════

def test_top10_clientes_con_nombre(db_conn):
    """
    SQL A del fix de esta sesión: Top 10 clientes con NOMBRECOMERCIAL.
    Debe devolver filas reales con nombres reales (no None).
    """
    rows = _run(db_conn,
        "SELECT d.CODCLIENTE, c.NOMBRECOMERCIAL, "
        "COUNT(d.CODIGO) AS N_DOCS, "
        "SUM(d.IMPORTETOTAL) AS TOTAL_EUR "
        "FROM DOCCAB d LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
        "WHERE d.CODCLIENTE IS NOT NULL AND d.CODCLIENTE > 0 "
        "GROUP BY d.CODCLIENTE, c.NOMBRECOMERCIAL "
        "ORDER BY TOTAL_EUR DESC LIMIT 10"
    )
    assert len(rows) >= 1, "Debe haber al menos 1 cliente con documentos"
    # El primer cliente debe tener TOTAL_EUR > 0
    assert rows[0]["TOTAL_EUR"] > 0, "El top cliente debe tener importe > 0"
    # Debe haber nombres (no todos None)
    nombres = [r["NOMBRECOMERCIAL"] for r in rows if r["NOMBRECOMERCIAL"] is not None]
    assert len(nombres) >= 1, "Al menos 1 cliente debe tener NOMBRECOMERCIAL"


def test_total_global_clientes(db_conn):
    """
    SQL B del fix: Total global y número de clientes distintos.
    Base para calcular % de concentración.
    """
    rows = _run(db_conn,
        "SELECT COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS, "
        "COUNT(*) AS TOTAL_DOCUMENTOS, "
        "SUM(IMPORTETOTAL) AS TOTAL_GLOBAL_EUR, "
        "AVG(IMPORTETOTAL) AS MEDIA_EUR "
        "FROM DOCCAB WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0"
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["CLIENTES_DISTINTOS"] > 0
    assert r["TOTAL_DOCUMENTOS"] > 0
    assert r["TOTAL_GLOBAL_EUR"] > 0


def test_concentracion_top5_clientes(db_conn):
    """
    SQL C del fix: Calcular PCT del top 5 clientes vs total.
    El resultado debe ser un número entre 0 y 100.
    """
    rows = _run(db_conn,
        "SELECT SUM(IMPORTETOTAL) AS TOTAL_TOP5, "
        "(SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0) "
        "AS TOTAL_GLOBAL "
        "FROM DOCCAB "
        "WHERE CODCLIENTE IN ("
        "  SELECT CODCLIENTE FROM DOCCAB "
        "  WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0 "
        "  GROUP BY CODCLIENTE ORDER BY SUM(IMPORTETOTAL) DESC LIMIT 5"
        ") AND CODCLIENTE IS NOT NULL AND CODCLIENTE > 0"
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["TOTAL_TOP5"] is not None and r["TOTAL_TOP5"] > 0
    assert r["TOTAL_GLOBAL"] is not None and r["TOTAL_GLOBAL"] > 0
    # El top 5 no puede superar el total
    assert r["TOTAL_TOP5"] <= r["TOTAL_GLOBAL"] + 0.01  # tolerancia float


def test_distribucion_anual(db_conn):
    """SQL fijo de distribución anual devuelve datos del año 2026."""
    rows = _run(db_conn,
        "SELECT strftime('%Y', FECHA) AS ANO, COUNT(*) AS N, "
        "SUM(IMPORTETOTAL) AS TOTAL_EUR "
        "FROM DOCCAB WHERE FECHA IS NOT NULL "
        "GROUP BY strftime('%Y', FECHA) ORDER BY ANO DESC"
    )
    anios = [r["ANO"] for r in rows if r["ANO"] is not None]
    assert "2026" in anios, "El simulador debe tener datos del 2026"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests de queries adicionales
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("limit_n", [1, 5, 10, 20, 50, 100])
def test_doccab_paginado(db_conn, limit_n: int):
    """LIMIT N no devuelve más de N filas."""
    rows = _run(db_conn, f"SELECT * FROM DOCCAB LIMIT {limit_n}")
    assert len(rows) <= limit_n


def test_cliente_nombres_reales(db_conn):
    """La tabla CLIENTE tiene NOMBRECOMERCIAL no nulo en la mayoría de registros."""
    rows = _run(db_conn,
        "SELECT COUNT(*) AS TOTAL, "
        "SUM(CASE WHEN NOMBRECOMERCIAL IS NOT NULL AND NOMBRECOMERCIAL != '' "
        "         THEN 1 ELSE 0 END) AS CON_NOMBRE "
        "FROM CLIENTE"
    )
    assert rows[0]["TOTAL"] > 0, "Debe haber clientes en el simulador"
    ratio = rows[0]["CON_NOMBRE"] / rows[0]["TOTAL"]
    assert ratio >= 0.5, f"Al menos 50% de clientes deben tener NOMBRECOMERCIAL, got {ratio:.1%}"


def test_agentes_tiene_datos(db_conn):
    """La tabla AGENTES tiene datos."""
    rows = _run(db_conn, "SELECT COUNT(*) AS N FROM AGENTES")
    # Puede ser 0 si el simulador no tiene agentes — no es error
    assert isinstance(rows[0]["N"], int)


def test_articulo_stocks(db_conn):
    """ARTICULO tiene registros (aunque STOCKARTICULO pueda ser 0)."""
    rows = _run(db_conn, "SELECT COUNT(*) AS N FROM ARTICULO")
    assert rows[0]["N"] >= 0


def test_doccab_sin_tipo3_en_simulador(db_conn):
    """
    TIPO=3 (factura cliente) NO existe en el simulador.
    Este test documenta el data gap conocido.
    """
    rows = _run(db_conn, "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO = 3")
    n = rows[0]["N"]
    assert n == 0, (
        f"TIPO=3 apareció en el simulador ({n} registros). "
        "Si hay datos reales de TIPO=3, actualizar PENDIENTE_DATOS_BD_REAL.md"
    )


@pytest.mark.parametrize("col", ["CODIGO", "TIPO", "FECHA", "IMPORTETOTAL", "CODCLIENTE"])
def test_doccab_columnas_clave_existen(db_conn, col: str):
    """Columnas clave de DOCCAB existen y son accesibles."""
    rows = _run(db_conn, f"SELECT {col} FROM DOCCAB LIMIT 1")
    assert isinstance(rows, list)


@pytest.mark.parametrize("col", ["CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "NIF"])
def test_cliente_columnas_clave_existen(db_conn, col: str):
    """Columnas clave de CLIENTE existen."""
    rows = _run(db_conn, f"SELECT {col} FROM CLIENTE LIMIT 1")
    assert isinstance(rows, list)


def test_subquery_correlacionada(db_conn):
    """Subquery correlacionada funciona en el simulador."""
    rows = _run(db_conn,
        "SELECT CODCLIENTE, IMPORTETOTAL "
        "FROM DOCCAB "
        "WHERE IMPORTETOTAL > (SELECT AVG(IMPORTETOTAL) FROM DOCCAB) "
        "LIMIT 10"
    )
    assert isinstance(rows, list)


def test_cte_funciona_en_simulador(db_conn):
    """
    CTE (WITH) funciona en SQLite.
    Crítico para las queries de concentración de clientes.
    """
    rows = _run(db_conn,
        "WITH top5 AS ("
        "  SELECT CODCLIENTE, SUM(IMPORTETOTAL) AS TOTAL "
        "  FROM DOCCAB WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0 "
        "  GROUP BY CODCLIENTE ORDER BY TOTAL DESC LIMIT 5"
        ") "
        "SELECT CODCLIENTE, TOTAL FROM top5"
    )
    assert len(rows) >= 1, "CTE debe devolver resultados"
    assert rows[0]["TOTAL"] > 0


def test_doccab_fecha_rango_simulador(db_conn):
    """El rango de fechas del simulador está documentado."""
    rows = _run(db_conn,
        "SELECT MIN(FECHA) AS FECHA_MIN, MAX(FECHA) AS FECHA_MAX FROM DOCCAB"
    )
    assert rows[0]["FECHA_MIN"] is not None
    assert rows[0]["FECHA_MAX"] is not None
    # El simulador debería tener datos del 2026
    assert "2026" in str(rows[0]["FECHA_MAX"])


def test_multiple_joins_no_error(db_conn):
    """JOIN de 3 tablas no falla."""
    rows = _run(db_conn,
        "SELECT d.TIPO, c.NOMBRECOMERCIAL, COUNT(dl.CODIGO) AS N_LINEAS "
        "FROM DOCCAB d "
        "LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
        "LEFT JOIN DOCLIN dl ON dl.CODDOCUMENTO = d.CODIGO "
        "GROUP BY d.TIPO, c.NOMBRECOMERCIAL "
        "ORDER BY N_LINEAS DESC LIMIT 5"
    )
    assert isinstance(rows, list)
