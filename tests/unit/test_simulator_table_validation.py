"""
test_simulator_table_validation.py — Tests para la validación de tablas del simulador.

Verifica que:
1. _validate_and_fix_tables_for_simulator detecta tablas desconocidas
2. Sustituye alias conocidos (CLIENTES→CLIENTE, DOCVAR→error, etc.)
3. El usuario NUNCA ve "no such table: X" — el sistema lo detecta antes
4. Cubre todos los tipos de preguntas posibles sobre la BD

Principio DEVIA: el simulador solo tiene tablas reales de JDDC.
La IA no puede inventar tablas que no existen.
"""

import re
import pytest
from typing import Dict, List, Optional, FrozenSet


# ── Replica de la lógica de HelpersAgentMixin para tests unitarios ────────────

SIMULATOR_TABLES: FrozenSet[str] = frozenset({
    "FAMILIA", "ALMACEN", "RECURSO", "PROVEED", "ARTICULO", "CLIENTE",
    "DOCCAB", "DOCLIN", "CAJA", "ESTALMACEN", "PROYECTOS", "PROYVAR",
    "PRESUPROYE", "DOCDESTINO", "AGENTES", "TIPOSIVA", "TARIFAS",
    "FORMASPAGO", "SERIES", "AVISOS",
})

FIREBIRD_TABLE_ALIASES: Dict[str, Optional[str]] = {
    "DOCVAR":       None,
    "C":            "CLIENTE",
    "REPARA":       None,
    "REPARACION":   None,
    "PEDIDOS":      "DOCCAB",
    "FACTURAS":     "DOCCAB",
    "PRESUPUESTOS": "DOCCAB",
    "ALBARANES":    "DOCCAB",
    "COMPRAS":      "DOCCAB",
    "ARTICULOS":    "ARTICULO",
    "CLIENTES":     "CLIENTE",
    "PROVEEDORES":  "PROVEED",
    "AGENTE":       "AGENTES",
}

_SQL_KEYWORDS = frozenset({
    'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS',
    'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'NATURAL',
    'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'CURRENT_TIME',
    'DUAL', 'SYSIBM',
})

_FROM_JOIN_RE = re.compile(r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)', re.IGNORECASE)


def validate_and_fix_tables(sql: str) -> str:
    """Replica de _validate_and_fix_tables_for_simulator para tests."""
    tables_in_sql = [
        m.group(1).upper()
        for m in _FROM_JOIN_RE.finditer(sql)
        if m.group(1).upper() not in _SQL_KEYWORDS
    ]
    unknown_tables = [t for t in tables_in_sql if t not in SIMULATOR_TABLES]
    if not unknown_tables:
        return sql

    fixed_sql = sql
    truly_unknown = []
    for table in unknown_tables:
        alias = FIREBIRD_TABLE_ALIASES.get(table)
        if alias is not None:
            fixed_sql = re.sub(rf'\b{re.escape(table)}\b', alias, fixed_sql, flags=re.IGNORECASE)
        else:
            truly_unknown.append(table)

    if truly_unknown:
        raise ValueError(
            f"Tabla(s) no disponible(s) en el simulador: {', '.join(truly_unknown)}. "
            f"Tablas disponibles: {', '.join(sorted(SIMULATOR_TABLES))}. "
            f"Reescribe la consulta usando solo las tablas disponibles."
        )
    return fixed_sql


def extract_tables(sql: str) -> List[str]:
    """Extrae nombres de tablas de un SQL."""
    return [
        m.group(1).upper()
        for m in _FROM_JOIN_RE.finditer(sql)
        if m.group(1).upper() not in _SQL_KEYWORDS
    ]


# ── Tests: tablas válidas del simulador ───────────────────────────────────────

class TestTablasSoportadas:
    """Verifica que todas las tablas del simulador son aceptadas sin error."""

    def test_doccab_valida(self):
        sql = "SELECT TIPO, COUNT(*) FROM DOCCAB GROUP BY TIPO"
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result

    def test_doclin_valida(self):
        sql = "SELECT CODDOCUMENTO, CANTIDAD FROM DOCLIN LIMIT 10"
        result = validate_and_fix_tables(sql)
        assert "DOCLIN" in result

    def test_cliente_valida(self):
        sql = "SELECT CODIGO, NOMBRECOMERCIAL FROM CLIENTE WHERE BAJA = 0"
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result

    def test_articulo_valida(self):
        sql = "SELECT CODIGO, NOMBRE, STOCKARTICULO FROM ARTICULO"
        result = validate_and_fix_tables(sql)
        assert "ARTICULO" in result

    def test_proveed_valida(self):
        sql = "SELECT CODIGO, NOMBRECOMERCIAL FROM PROVEED"
        result = validate_and_fix_tables(sql)
        assert "PROVEED" in result

    def test_caja_valida(self):
        sql = "SELECT FECHA, IMPORTE FROM CAJA WHERE TIPO = 1"
        result = validate_and_fix_tables(sql)
        assert "CAJA" in result

    def test_proyectos_valida(self):
        sql = "SELECT CODIGO, NOMBRE, CLIENTE FROM PROYECTOS"
        result = validate_and_fix_tables(sql)
        assert "PROYECTOS" in result

    def test_agentes_valida(self):
        sql = "SELECT CODIGO, NOMBRE, COMISION FROM AGENTES"
        result = validate_and_fix_tables(sql)
        assert "AGENTES" in result

    def test_estalmacen_valida(self):
        sql = "SELECT CODIGO, FECHA, IMPCOSTE FROM ESTALMACEN"
        result = validate_and_fix_tables(sql)
        assert "ESTALMACEN" in result

    def test_avisos_valida(self):
        sql = "SELECT CODIGO, DESCRIPCION, ESTADO FROM AVISOS"
        result = validate_and_fix_tables(sql)
        assert "AVISOS" in result

    def test_tiposiva_valida(self):
        sql = "SELECT CODIGO, NOMBRE, PORCENTAJE FROM TIPOSIVA"
        result = validate_and_fix_tables(sql)
        assert "TIPOSIVA" in result

    def test_formaspago_valida(self):
        sql = "SELECT CODIGO, NOMBRE, DIASVENC FROM FORMASPAGO"
        result = validate_and_fix_tables(sql)
        assert "FORMASPAGO" in result

    def test_series_valida(self):
        sql = "SELECT CODIGO, NOMBRE, TIPO FROM SERIES"
        result = validate_and_fix_tables(sql)
        assert "SERIES" in result

    def test_docdestino_valida(self):
        sql = "SELECT CODDOCUMENTO, CODDOCUMENTODESTINO FROM DOCDESTINO"
        result = validate_and_fix_tables(sql)
        assert "DOCDESTINO" in result

    def test_presuproye_valida(self):
        sql = "SELECT CODPROYECTO, CODPRESUPUESTO FROM PRESUPROYE"
        result = validate_and_fix_tables(sql)
        assert "PRESUPROYE" in result

    def test_join_doccab_doclin_valido(self):
        sql = """
        SELECT d.TIPO, l.CODARTICULO, l.CANTIDAD
        FROM DOCCAB d
        JOIN DOCLIN l ON l.CODDOCUMENTO = d.CODIGO
        WHERE d.TIPO = 0
        """
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result
        assert "DOCLIN" in result

    def test_join_triple_valido(self):
        sql = """
        SELECT c.NOMBRECOMERCIAL, d.TIPO, l.CANTIDAD
        FROM CLIENTE c
        JOIN DOCCAB d ON d.CODCLIENTE = c.CODIGO
        JOIN DOCLIN l ON l.CODDOCUMENTO = d.CODIGO
        """
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result
        assert "DOCCAB" in result
        assert "DOCLIN" in result


# ── Tests: alias automáticos (tablas Firebird → simulador) ────────────────────

class TestAliasAutomaticos:
    """Verifica que los alias conocidos se sustituyen automáticamente."""

    def test_clientes_a_cliente(self):
        sql = "SELECT CODIGO FROM CLIENTES WHERE BAJA = 0"
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result
        assert "CLIENTES" not in result

    def test_articulos_a_articulo(self):
        sql = "SELECT CODIGO, NOMBRE FROM ARTICULOS"
        result = validate_and_fix_tables(sql)
        assert "ARTICULO" in result
        assert "ARTICULOS" not in result

    def test_proveedores_a_proveed(self):
        sql = "SELECT CODIGO FROM PROVEEDORES"
        result = validate_and_fix_tables(sql)
        assert "PROVEED" in result
        assert "PROVEEDORES" not in result

    def test_agente_a_agentes(self):
        sql = "SELECT CODIGO, NOMBRE FROM AGENTE"
        result = validate_and_fix_tables(sql)
        assert "AGENTES" in result
        assert "AGENTE " not in result  # espacio para no confundir con AGENTES

    def test_facturas_a_doccab(self):
        sql = "SELECT COUNT(*) FROM FACTURAS WHERE TIPO = 0"
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result
        assert "FACTURAS" not in result

    def test_presupuestos_a_doccab(self):
        sql = "SELECT COUNT(*) FROM PRESUPUESTOS WHERE TIPO = 1"
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result
        assert "PRESUPUESTOS" not in result

    def test_pedidos_a_doccab(self):
        sql = "SELECT COUNT(*) FROM PEDIDOS"
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result
        assert "PEDIDOS" not in result

    def test_albaranes_a_doccab(self):
        sql = "SELECT COUNT(*) FROM ALBARANES"
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result
        assert "ALBARANES" not in result

    def test_compras_a_doccab(self):
        sql = "SELECT COUNT(*) FROM COMPRAS"
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result
        assert "COMPRAS" not in result

    def test_c_alias_a_cliente(self):
        """El alias 'C' (frecuente en Firebird) se sustituye por CLIENTE."""
        sql = "SELECT C.CODIGO, C.NOMBRECOMERCIAL FROM C WHERE C.BAJA = 0"
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result


# ── Tests: tablas que NO existen en el simulador ──────────────────────────────

class TestTablasNoExistentes:
    """Verifica que tablas sin equivalente lanzan ValueError descriptivo."""

    def test_docvar_lanza_error(self):
        sql = "SELECT * FROM DOCVAR WHERE CODDOCUMENTO = 1"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "DOCVAR" in str(exc_info.value)
        assert "no disponible" in str(exc_info.value).lower() or "disponible" in str(exc_info.value)

    def test_repara_lanza_error(self):
        sql = "SELECT * FROM REPARA"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "REPARA" in str(exc_info.value)

    def test_reparacion_lanza_error(self):
        sql = "SELECT * FROM REPARACION WHERE ESTADO = 'PENDIENTE'"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "REPARACION" in str(exc_info.value)

    def test_tabla_inventada_lanza_error(self):
        sql = "SELECT * FROM TABLA_INVENTADA_POR_IA"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "TABLA_INVENTADA_POR_IA" in str(exc_info.value)

    def test_error_incluye_tablas_disponibles(self):
        """El error debe incluir la lista de tablas disponibles para ayudar al corrector."""
        sql = "SELECT * FROM DOCVAR"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        error_msg = str(exc_info.value)
        # Debe mencionar al menos algunas tablas disponibles
        assert "DOCCAB" in error_msg or "CLIENTE" in error_msg or "ARTICULO" in error_msg

    def test_error_pide_reescribir_consulta(self):
        """El error debe indicar que hay que reescribir la consulta."""
        sql = "SELECT * FROM DOCVAR"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "Reescribe" in str(exc_info.value) or "reescribe" in str(exc_info.value).lower()

    def test_multiples_tablas_desconocidas(self):
        """Si hay varias tablas desconocidas, el error las menciona todas."""
        sql = "SELECT * FROM DOCVAR JOIN REPARA ON DOCVAR.ID = REPARA.ID"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        error_msg = str(exc_info.value)
        assert "DOCVAR" in error_msg
        assert "REPARA" in error_msg


# ── Tests: extracción de tablas del SQL ───────────────────────────────────────

class TestExtraccionTablas:
    """Verifica que se extraen correctamente los nombres de tablas del SQL."""

    def test_from_simple(self):
        tables = extract_tables("SELECT * FROM DOCCAB")
        assert "DOCCAB" in tables

    def test_from_con_alias(self):
        tables = extract_tables("SELECT d.TIPO FROM DOCCAB d")
        assert "DOCCAB" in tables

    def test_join_multiple(self):
        tables = extract_tables("""
            SELECT * FROM DOCCAB d
            JOIN DOCLIN l ON l.CODDOCUMENTO = d.CODIGO
            JOIN CLIENTE c ON c.CODIGO = d.CODCLIENTE
        """)
        assert "DOCCAB" in tables
        assert "DOCLIN" in tables
        assert "CLIENTE" in tables

    def test_subquery_no_confunde(self):
        """Las palabras clave SQL no se confunden con nombres de tabla."""
        tables = extract_tables("SELECT * FROM DOCCAB WHERE TIPO IN (SELECT TIPO FROM SERIES)")
        assert "DOCCAB" in tables
        assert "SERIES" in tables
        assert "IN" not in tables
        assert "SELECT" not in tables

    def test_left_join(self):
        tables = extract_tables("""
            SELECT c.NOMBRECOMERCIAL, COUNT(d.CODIGO)
            FROM CLIENTE c
            LEFT JOIN DOCCAB d ON d.CODCLIENTE = c.CODIGO
            GROUP BY c.CODIGO
        """)
        assert "CLIENTE" in tables
        assert "DOCCAB" in tables
        assert "LEFT" not in tables
        assert "JOIN" not in tables


# ── Tests: casos reales de preguntas de negocio ───────────────────────────────

class TestCasosRealesNegocio:
    """
    Verifica que las consultas SQL típicas para preguntas de negocio
    usan solo tablas válidas del simulador.
    """

    def test_presupuestos_sin_convertir(self):
        """Pregunta: ¿Qué clientes tienen más presupuestos pendientes?"""
        # SQL correcto: DOCCAB con TIPO=1 (presupuestos), sin DOCVAR
        sql = """
        SELECT c.NOMBRECOMERCIAL, COUNT(d.CODIGO) AS N_PRESUPUESTOS
        FROM CLIENTE c
        JOIN DOCCAB d ON d.CODCLIENTE = c.CODIGO
        WHERE d.TIPO = 1
        GROUP BY c.CODIGO, c.NOMBRECOMERCIAL
        ORDER BY N_PRESUPUESTOS DESC
        LIMIT 20
        """
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result
        assert "DOCCAB" in result

    def test_facturacion_por_cliente(self):
        """Pregunta: ¿Cuánto ha facturado cada cliente este año?"""
        sql = """
        SELECT c.NOMBRECOMERCIAL, SUM(d.IMPORTETOTAL) AS TOTAL_EUR
        FROM CLIENTE c
        JOIN DOCCAB d ON d.CODCLIENTE = c.CODIGO
        WHERE d.TIPO = 0 AND strftime('%Y', d.FECHA) = '2026'
        GROUP BY c.CODIGO
        ORDER BY TOTAL_EUR DESC
        LIMIT 10
        """
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result
        assert "DOCCAB" in result

    def test_articulos_mas_vendidos(self):
        """Pregunta: ¿Qué artículos se venden más?"""
        sql = """
        SELECT a.NOMBRE, SUM(l.CANTIDAD) AS TOTAL_VENDIDO
        FROM ARTICULO a
        JOIN DOCLIN l ON l.CODARTICULO = a.CODIGO
        JOIN DOCCAB d ON d.CODIGO = l.CODDOCUMENTO
        WHERE d.TIPO = 0
        GROUP BY a.CODIGO, a.NOMBRE
        ORDER BY TOTAL_VENDIDO DESC
        LIMIT 15
        """
        result = validate_and_fix_tables(sql)
        assert "ARTICULO" in result
        assert "DOCLIN" in result
        assert "DOCCAB" in result

    def test_stock_por_familia(self):
        """Pregunta: ¿Cuál es el stock por familia de artículos?"""
        sql = """
        SELECT f.NOMBRE AS FAMILIA, SUM(a.STOCKARTICULO) AS STOCK_TOTAL
        FROM FAMILIA f
        JOIN ARTICULO a ON a.CODFAMILIA = f.CODIGO
        GROUP BY f.CODIGO, f.NOMBRE
        ORDER BY STOCK_TOTAL DESC
        """
        result = validate_and_fix_tables(sql)
        assert "FAMILIA" in result
        assert "ARTICULO" in result

    def test_proyectos_activos(self):
        """Pregunta: ¿Qué proyectos están activos?"""
        sql = """
        SELECT p.NOMBRE, p.CLIENTE, p.FECHAINICIO
        FROM PROYECTOS p
        WHERE p.FECHAFIN IS NULL OR p.FECHAFIN > date('now')
        ORDER BY p.FECHAINICIO DESC
        LIMIT 20
        """
        result = validate_and_fix_tables(sql)
        assert "PROYECTOS" in result

    def test_proveedores_con_mas_compras(self):
        """Pregunta: ¿Qué proveedores tienen más compras?"""
        sql = """
        SELECT p.NOMBRECOMERCIAL, COUNT(d.CODIGO) AS N_COMPRAS
        FROM PROVEED p
        JOIN DOCCAB d ON d.CODPROVEEDOR = p.CODIGO
        WHERE d.TIPO = 2
        GROUP BY p.CODIGO, p.NOMBRECOMERCIAL
        ORDER BY N_COMPRAS DESC
        LIMIT 10
        """
        result = validate_and_fix_tables(sql)
        assert "PROVEED" in result
        assert "DOCCAB" in result

    def test_agentes_con_mas_ventas(self):
        """Pregunta: ¿Qué agentes comerciales tienen más ventas?"""
        sql = """
        SELECT ag.NOMBRE, COUNT(d.CODIGO) AS N_VENTAS, SUM(d.IMPORTETOTAL) AS TOTAL
        FROM AGENTES ag
        JOIN DOCCAB d ON d.CODAGENTE = ag.CODIGO
        WHERE d.TIPO = 0
        GROUP BY ag.CODIGO, ag.NOMBRE
        ORDER BY TOTAL DESC
        """
        result = validate_and_fix_tables(sql)
        assert "AGENTES" in result
        assert "DOCCAB" in result

    def test_caja_movimientos_mes(self):
        """Pregunta: ¿Cuáles son los movimientos de caja del mes actual?"""
        sql = """
        SELECT FECHA, TIPO, IMPORTE, DEBE
        FROM CAJA
        WHERE strftime('%Y-%m', FECHA) = strftime('%Y-%m', 'now')
        ORDER BY FECHA DESC
        LIMIT 50
        """
        result = validate_and_fix_tables(sql)
        assert "CAJA" in result

    def test_avisos_pendientes(self):
        """Pregunta: ¿Qué avisos están pendientes?"""
        sql = """
        SELECT a.DESCRIPCION, a.FECHA, c.NOMBRECOMERCIAL
        FROM AVISOS a
        LEFT JOIN CLIENTE c ON c.CODIGO = a.CODCLIENTE
        WHERE a.ESTADO = 0
        ORDER BY a.FECHA DESC
        """
        result = validate_and_fix_tables(sql)
        assert "AVISOS" in result
        assert "CLIENTE" in result

    def test_formas_pago_mas_usadas(self):
        """Pregunta: ¿Qué formas de pago se usan más?"""
        sql = """
        SELECT fp.NOMBRE, COUNT(d.CODIGO) AS N_DOCS
        FROM FORMASPAGO fp
        JOIN DOCCAB d ON d.CODFORMAPAGO = fp.CODIGO
        GROUP BY fp.CODIGO, fp.NOMBRE
        ORDER BY N_DOCS DESC
        """
        result = validate_and_fix_tables(sql)
        assert "FORMASPAGO" in result
        assert "DOCCAB" in result

    def test_series_documentos(self):
        """Pregunta: ¿Cuántos documentos hay por serie?"""
        sql = """
        SELECT s.NOMBRE AS SERIE, COUNT(d.CODIGO) AS N_DOCS
        FROM SERIES s
        JOIN DOCCAB d ON d.SERIE = s.CODIGO
        GROUP BY s.CODIGO, s.NOMBRE
        ORDER BY N_DOCS DESC
        """
        result = validate_and_fix_tables(sql)
        assert "SERIES" in result
        assert "DOCCAB" in result

    def test_tarifas_aplicadas(self):
        """Pregunta: ¿Qué tarifas se aplican a los clientes?"""
        sql = """
        SELECT t.NOMBRE AS TARIFA, COUNT(c.CODIGO) AS N_CLIENTES
        FROM TARIFAS t
        JOIN CLIENTE c ON c.CODTARIFA = t.CODIGO
        GROUP BY t.CODIGO, t.NOMBRE
        ORDER BY N_CLIENTES DESC
        """
        result = validate_and_fix_tables(sql)
        assert "TARIFAS" in result
        assert "CLIENTE" in result


# ── Tests: SQL con tablas Firebird-only que deben ser rechazadas ──────────────

class TestTablasSoloFirebird:
    """
    Tablas que existen en Firebird real pero NO en el simulador.
    El sistema debe rechazarlas con un error descriptivo.
    """

    def test_docvar_rechazada(self):
        """DOCVAR: tabla de variables de documento — no existe en simulador."""
        sql = "SELECT CODVARIABLE, VALOR FROM DOCVAR WHERE CODDOCUMENTO = 100"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "DOCVAR" in str(exc_info.value)

    def test_repara_rechazada(self):
        """REPARA: tabla de reparaciones — no existe en simulador."""
        sql = "SELECT CODIGO, DESCRIPCION FROM REPARA WHERE ESTADO = 'PENDIENTE'"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "REPARA" in str(exc_info.value)

    def test_join_con_tabla_invalida(self):
        """Un JOIN con tabla inválida debe rechazarse aunque la otra sea válida."""
        sql = """
        SELECT d.CODIGO, v.VALOR
        FROM DOCCAB d
        JOIN DOCVAR v ON v.CODDOCUMENTO = d.CODIGO
        """
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "DOCVAR" in str(exc_info.value)

    def test_tabla_completamente_inventada(self):
        """Una tabla inventada por la IA debe rechazarse."""
        sql = "SELECT * FROM VENTAS_MENSUALES_RESUMEN"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "VENTAS_MENSUALES_RESUMEN" in str(exc_info.value)

    def test_tabla_con_prefijo_inventado(self):
        """Tablas con prefijos inventados deben rechazarse."""
        sql = "SELECT * FROM TMP_CLIENTES_ACTIVOS"
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "TMP_CLIENTES_ACTIVOS" in str(exc_info.value)


# ── Tests: casos edge ─────────────────────────────────────────────────────────

class TestCasosEdge:
    """Casos límite y edge cases del validador."""

    def test_sql_sin_from_no_falla(self):
        """SQL sin FROM (ej: SELECT 1) no debe fallar."""
        sql = "SELECT 1"
        result = validate_and_fix_tables(sql)
        assert result == sql

    def test_sql_vacio_no_falla(self):
        """SQL vacío no debe fallar."""
        result = validate_and_fix_tables("")
        assert result == ""

    def test_case_insensitive_tabla_minusculas(self):
        """Las tablas en minúsculas también se validan correctamente."""
        sql = "SELECT * FROM doccab WHERE tipo = 0"
        result = validate_and_fix_tables(sql)
        assert "doccab" in result.lower()

    def test_case_insensitive_tabla_mixta(self):
        """Las tablas en case mixto también se validan."""
        sql = "SELECT * FROM DocCab WHERE Tipo = 0"
        result = validate_and_fix_tables(sql)
        assert "DocCab" in result or "DOCCAB" in result

    def test_alias_tabla_no_confunde_columna(self):
        """El alias de tabla en SELECT no se confunde con nombre de tabla."""
        sql = "SELECT d.TIPO, d.CODIGO FROM DOCCAB d WHERE d.TIPO = 0"
        result = validate_and_fix_tables(sql)
        assert "DOCCAB" in result

    def test_subquery_tablas_validas(self):
        """Las tablas en subqueries también se validan."""
        sql = """
        SELECT * FROM CLIENTE
        WHERE CODIGO IN (
            SELECT CODCLIENTE FROM DOCCAB WHERE TIPO = 0
        )
        """
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result
        assert "DOCCAB" in result

    def test_subquery_tabla_invalida_detectada(self):
        """Las tablas inválidas en subqueries también se detectan."""
        sql = """
        SELECT * FROM CLIENTE
        WHERE CODIGO IN (
            SELECT CODCLIENTE FROM DOCVAR WHERE TIPO = 0
        )
        """
        with pytest.raises(ValueError) as exc_info:
            validate_and_fix_tables(sql)
        assert "DOCVAR" in str(exc_info.value)

    def test_multiple_joins_todos_validos(self):
        """Múltiples JOINs con tablas válidas no deben fallar."""
        sql = """
        SELECT c.NOMBRECOMERCIAL, a.NOMBRE, d.TIPO, l.CANTIDAD
        FROM CLIENTE c
        JOIN DOCCAB d ON d.CODCLIENTE = c.CODIGO
        JOIN DOCLIN l ON l.CODDOCUMENTO = d.CODIGO
        JOIN ARTICULO a ON a.CODIGO = l.CODARTICULO
        WHERE d.TIPO = 0
        """
        result = validate_and_fix_tables(sql)
        assert "CLIENTE" in result
        assert "DOCCAB" in result
        assert "DOCLIN" in result
        assert "ARTICULO" in result


# ── Tests: verificación del conjunto de tablas del simulador ──────────────────

class TestEsquemaSimulador:
    """Verifica la integridad del conjunto de tablas del simulador."""

    def test_tablas_principales_presentes(self):
        """Las tablas principales de JDDC deben estar en el simulador."""
        tablas_principales = ["DOCCAB", "DOCLIN", "CLIENTE", "ARTICULO", "PROVEED"]
        for tabla in tablas_principales:
            assert tabla in SIMULATOR_TABLES, f"Tabla principal {tabla} no está en el simulador"

    def test_tablas_auxiliares_presentes(self):
        """Las tablas auxiliares deben estar en el simulador."""
        tablas_aux = ["AGENTES", "TIPOSIVA", "TARIFAS", "FORMASPAGO", "SERIES"]
        for tabla in tablas_aux:
            assert tabla in SIMULATOR_TABLES, f"Tabla auxiliar {tabla} no está en el simulador"

    def test_tablas_proyectos_presentes(self):
        """Las tablas de proyectos deben estar en el simulador."""
        tablas_proy = ["PROYECTOS", "PROYVAR", "PRESUPROYE"]
        for tabla in tablas_proy:
            assert tabla in SIMULATOR_TABLES, f"Tabla de proyectos {tabla} no está en el simulador"

    def test_docvar_no_en_simulador(self):
        """DOCVAR NO debe estar en el simulador (es Firebird-only)."""
        assert "DOCVAR" not in SIMULATOR_TABLES

    def test_repara_no_en_simulador(self):
        """REPARA NO debe estar en el simulador."""
        assert "REPARA" not in SIMULATOR_TABLES

    def test_total_tablas_simulador(self):
        """El simulador debe tener exactamente 20 tablas."""
        assert len(SIMULATOR_TABLES) == 20

    def test_alias_docvar_es_none(self):
        """DOCVAR no tiene equivalente en el simulador."""
        assert FIREBIRD_TABLE_ALIASES.get("DOCVAR") is None

    def test_alias_clientes_es_cliente(self):
        """CLIENTES (plural) mapea a CLIENTE (singular)."""
        assert FIREBIRD_TABLE_ALIASES.get("CLIENTES") == "CLIENTE"

    def test_alias_facturas_es_doccab(self):
        """FACTURAS mapea a DOCCAB (con TIPO específico)."""
        assert FIREBIRD_TABLE_ALIASES.get("FACTURAS") == "DOCCAB"
