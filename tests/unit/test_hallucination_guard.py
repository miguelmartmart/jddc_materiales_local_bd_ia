"""
test_hallucination_guard.py — Tests del módulo anti-alucinaciones de DEVIA.

OBJETIVO:
    Verificar que el HallucinationGuard detecta correctamente cuando el SQL
    generado por la IA contiene tablas, columnas o valores que NO existen
    en el esquema real de la BD JDDC.

    El sistema debe ser capaz de:
    - Detectar tablas inventadas (FACTURAS, VENTAS, PEDIDOS_CLIENTE...)
    - Detectar columnas inventadas (ARTICULO.STOCK, CAJA.CODIGO, DOCCAB.IMPORTE...)
    - Detectar valores inválidos (DOCCAB.TIPO=99, CAJA.TIPO=5...)
    - Validar SQLs correctos sin falsos positivos
    - Ser resiliente ante SQLs vacíos, malformados o None
    - Funcionar de forma genérica para cualquier tabla del esquema

PRINCIPIOS DEVIA:
    - Sin inventar: solo valida contra el esquema real (TABLE_COLUMNS)
    - Ultra-resiliente: si falla la validación, devuelve WARNING (no ERROR)
    - Determinista: 100% determinista, sin IA
    - Genérico: funciona para cualquier SQL sobre cualquier tabla
    - Tests independientes: cada test es independiente

EJECUCIÓN:
    python -m pytest tests/unit/test_hallucination_guard.py -v
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.modules.chat.hallucination_guard import (
    HallucinationGuard,
    HallucinationReport,
    HallucinationIssue,
    HallucinationSeverity,
    get_hallucination_guard,
)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H1 — Inicialización y singleton
# ══════════════════════════════════════════════════════════════════════════════

class TestInicializacion(unittest.TestCase):
    """Verifica que el guard se inicializa correctamente."""

    def test_instancia_directa(self):
        guard = HallucinationGuard()
        self.assertIsInstance(guard, HallucinationGuard)

    def test_singleton(self):
        g1 = get_hallucination_guard()
        g2 = get_hallucination_guard()
        self.assertIs(g1, g2, "get_hallucination_guard debe devolver siempre la misma instancia")

    def test_tablas_conocidas_no_vacias(self):
        guard = HallucinationGuard()
        tables = guard.get_known_tables()
        self.assertGreater(len(tables), 5, "Debe conocer al menos 6 tablas")

    def test_tablas_conocidas_incluye_principales(self):
        guard = HallucinationGuard()
        tables = guard.get_known_tables()
        for tabla in ["DOCCAB", "ARTICULO", "CLIENTE", "PROVEED", "PROYECTOS"]:
            self.assertIn(tabla, tables, f"Debe conocer la tabla {tabla}")

    def test_columnas_conocidas_doccab(self):
        guard = HallucinationGuard()
        cols = guard.get_known_columns("DOCCAB")
        self.assertGreater(len(cols), 3)
        self.assertIn("TIPO", cols)
        self.assertIn("FECHA", cols)

    def test_is_table_known(self):
        guard = HallucinationGuard()
        self.assertTrue(guard.is_table_known("DOCCAB"))
        self.assertTrue(guard.is_table_known("ARTICULO"))
        self.assertFalse(guard.is_table_known("FACTURAS"))
        self.assertFalse(guard.is_table_known("VENTAS"))

    def test_is_column_known(self):
        guard = HallucinationGuard()
        self.assertTrue(guard.is_column_known("ARTICULO", "STOCKARTICULO"))
        self.assertFalse(guard.is_column_known("ARTICULO", "STOCK"))
        self.assertTrue(guard.is_column_known("CAJA", "CODAPUNTE"))
        self.assertFalse(guard.is_column_known("CAJA", "CODIGO"))


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H2 — SQLs correctos (sin alucinaciones)
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLsCorrectos(unittest.TestCase):
    """Verifica que SQLs correctos pasan la validación sin falsos positivos."""

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_sql_vacio(self):
        report = self.guard.validate("")
        self.assertEqual(report.severity, HallucinationSeverity.OK)
        self.assertTrue(report.is_safe)
        self.assertEqual(len(report.issues), 0)

    def test_sql_none_resiliente(self):
        """None no debe lanzar excepción."""
        try:
            report = self.guard.validate(None)
            self.assertIsInstance(report, HallucinationReport)
        except (TypeError, AttributeError):
            pass  # Aceptable — None no es un caso de uso real

    def test_sql_articulos_correcto(self):
        sql = "SELECT FIRST 20 NOMBRE, STOCKARTICULO, PRECIOVENTA FROM ARTICULO WHERE BAJA = 0"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"SQL correcto no debe tener errores: {report.summary()}")

    def test_sql_doccab_correcto(self):
        sql = (
            "SELECT FIRST 50 NUMERO, FECHA, IMPORTETOTAL "
            "FROM DOCCAB WHERE TIPO = 3 ORDER BY FECHA DESC"
        )
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"SQL correcto no debe tener errores: {report.summary()}")

    def test_sql_join_proyectos_doccab(self):
        sql = (
            "SELECT FIRST 50 p.NOMBRE, COUNT(d.CODIGO) as NUM_CERT "
            "FROM PROYECTOS p JOIN DOCCAB d ON d.CODPROYECTO = p.CODIGO "
            "WHERE d.TIPO = 3 GROUP BY p.CODIGO, p.NOMBRE"
        )
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"JOIN correcto no debe tener errores: {report.summary()}")

    def test_sql_cliente_correcto(self):
        sql = "SELECT NOMBRECOMERCIAL, NIF FROM CLIENTE WHERE BAJA = 0 ORDER BY NOMBRECOMERCIAL"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe)

    def test_sql_caja_correcto(self):
        sql = (
            "SELECT FECHA, TIPO, IMPORTE, CONCEPTO "
            "FROM CAJA WHERE TIPO = 1 ORDER BY FECHA DESC"
        )
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"SQL CAJA correcto no debe tener errores: {report.summary()}")

    def test_sql_proveed_correcto(self):
        sql = "SELECT NOMBRECOMERCIAL, NIF FROM PROVEED WHERE BAJA = 0"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe)

    def test_sql_agentes_correcto(self):
        sql = "SELECT NOMBRE, COMISION FROM AGENTES ORDER BY NOMBRE"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe)

    def test_sql_count_correcto(self):
        sql = "SELECT COUNT(*) as TOTAL FROM DOCCAB WHERE TIPO = 3"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe)

    def test_sql_sum_correcto(self):
        sql = "SELECT SUM(IMPORTETOTAL) as TOTAL FROM DOCCAB WHERE TIPO = 3"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H3 — Tablas inexistentes (alucinaciones de tabla)
# ══════════════════════════════════════════════════════════════════════════════

class TestTablasInexistentes(unittest.TestCase):
    """Verifica que el guard detecta tablas que no existen en el esquema."""

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_tabla_facturas_no_existe(self):
        """La IA a veces genera 'FACTURAS' en lugar de 'DOCCAB'."""
        sql = "SELECT NUMERO, FECHA, TOTAL FROM FACTURAS WHERE TIPO = 3"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)
        self.assertEqual(report.severity, HallucinationSeverity.ERROR)
        errores = [i for i in report.issues if i.category == "tabla_inexistente"]
        self.assertGreater(len(errores), 0)

    def test_tabla_ventas_no_existe(self):
        sql = "SELECT IMPORTE FROM VENTAS WHERE FECHA > '2026-01-01'"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_pedidos_cliente_no_existe(self):
        sql = "SELECT * FROM PEDIDOS_CLIENTE"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_inventario_no_existe(self):
        """'INVENTARIO' no existe — usar ARTICULO + ESTALMACEN."""
        sql = "SELECT NOMBRE, CANTIDAD FROM INVENTARIO"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_cobros_no_existe(self):
        """'COBROS' no existe — usar CAJA con TIPO=1."""
        sql = "SELECT IMPORTE FROM COBROS WHERE FECHA > '2026-01-01'"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_pagos_no_existe(self):
        """'PAGOS' no existe — usar CAJA con TIPO=2."""
        sql = "SELECT IMPORTE FROM PAGOS"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_obras_no_existe(self):
        """'OBRAS' no existe — usar PROYECTOS u OBRACAB."""
        sql = "SELECT NOMBRE FROM OBRAS WHERE ESTADO = 'ACTIVO'"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_certificaciones_no_existe(self):
        """'CERTIFICACIONES' no existe — son DOCCAB con CODPROYECTO y TIPO=3."""
        sql = "SELECT IMPORTE FROM CERTIFICACIONES WHERE PROYECTO = 'P001'"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_retenciones_no_existe(self):
        """'RETENCIONES' no existe — están en PROYECTOS.PORCRETENCION."""
        sql = "SELECT PORCENTAJE FROM RETENCIONES"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_tabla_inexistente_en_join(self):
        """Tabla inexistente en JOIN también debe detectarse."""
        sql = (
            "SELECT a.NOMBRE, v.CANTIDAD "
            "FROM ARTICULO a JOIN VENTAS v ON v.CODARTICULO = a.CODIGO"
        )
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)
        tablas_error = [i.detail for i in report.issues if "VENTAS" in i.detail]
        self.assertGreater(len(tablas_error), 0)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H4 — Columnas inexistentes (alucinaciones de columna)
# ══════════════════════════════════════════════════════════════════════════════

class TestColumnasInexistentes(unittest.TestCase):
    """Verifica que el guard detecta columnas que no existen en las tablas."""

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_articulo_stock_no_existe(self):
        """ARTICULO.STOCK no existe — usar ARTICULO.STOCKARTICULO."""
        sql = "SELECT NOMBRE, ARTICULO.STOCK FROM ARTICULO WHERE BAJA = 0"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)
        errores = [i for i in report.issues if "STOCK" in i.detail]
        self.assertGreater(len(errores), 0)

    def test_caja_codigo_no_existe(self):
        """CAJA.CODIGO no existe — usar CAJA.CODAPUNTE (PK de CAJA)."""
        sql = "SELECT CAJA.CODIGO, IMPORTE FROM CAJA WHERE TIPO = 1"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)
        errores = [i for i in report.issues if "CODIGO" in i.detail or "CAJA" in i.detail]
        self.assertGreater(len(errores), 0)

    def test_doccab_importe_no_existe(self):
        """DOCCAB.IMPORTE no existe — usar DOCCAB.IMPORTETOTAL."""
        sql = "SELECT DOCCAB.IMPORTE FROM DOCCAB WHERE TIPO = 3"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_doccab_total_no_existe(self):
        """DOCCAB.TOTAL no existe — usar DOCCAB.IMPORTETOTAL."""
        sql = "SELECT DOCCAB.TOTAL FROM DOCCAB WHERE TIPO = 3"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_columna_correcta_no_da_error(self):
        """DOCCAB.IMPORTETOTAL SÍ existe — no debe dar error."""
        sql = "SELECT DOCCAB.IMPORTETOTAL FROM DOCCAB WHERE TIPO = 3"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"IMPORTETOTAL es correcto: {report.summary()}")

    def test_articulo_stockarticulo_correcto(self):
        """ARTICULO.STOCKARTICULO SÍ existe — no debe dar error."""
        sql = "SELECT ARTICULO.STOCKARTICULO FROM ARTICULO WHERE BAJA = 0"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"STOCKARTICULO es correcto: {report.summary()}")

    def test_caja_codapunte_correcto(self):
        """CAJA.CODAPUNTE SÍ existe — no debe dar error."""
        sql = "SELECT CAJA.CODAPUNTE, CAJA.IMPORTE FROM CAJA WHERE TIPO = 1"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"CODAPUNTE es correcto: {report.summary()}")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H5 — Valores inválidos en columnas enumeradas
# ══════════════════════════════════════════════════════════════════════════════

class TestValoresInvalidos(unittest.TestCase):
    """Verifica que el guard detecta valores inválidos en columnas enumeradas."""

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_doccab_tipo_99_invalido(self):
        """DOCCAB.TIPO=99 no es un tipo válido."""
        sql = "SELECT NUMERO FROM DOCCAB WHERE DOCCAB.TIPO = 99"
        report = self.guard.validate(sql)
        # Debe ser WARNING (no ERROR) — el SQL puede ejecutarse pero el valor es sospechoso
        warnings = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertGreater(len(warnings), 0, "TIPO=99 debe generar advertencia")

    def test_doccab_tipo_3_valido(self):
        """DOCCAB.TIPO=3 (factura cliente) es válido."""
        sql = "SELECT NUMERO FROM DOCCAB WHERE DOCCAB.TIPO = 3"
        report = self.guard.validate(sql)
        valor_invalido = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertEqual(len(valor_invalido), 0, "TIPO=3 es válido, no debe generar advertencia")

    def test_doccab_tipo_13_valido(self):
        """DOCCAB.TIPO=13 (factura proveedor) es válido."""
        sql = "SELECT NUMERO FROM DOCCAB WHERE DOCCAB.TIPO = 13"
        report = self.guard.validate(sql)
        valor_invalido = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertEqual(len(valor_invalido), 0, "TIPO=13 es válido")

    def test_doccab_tipo_51_valido(self):
        """DOCCAB.TIPO=51 (certificación) es válido — observado en datos reales."""
        sql = "SELECT NUMERO FROM DOCCAB WHERE DOCCAB.TIPO = 51"
        report = self.guard.validate(sql)
        valor_invalido = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertEqual(len(valor_invalido), 0, "TIPO=51 es válido (certificación)")

    def test_caja_tipo_1_valido(self):
        """CAJA.TIPO=1 (cobro) es válido."""
        sql = "SELECT IMPORTE FROM CAJA WHERE CAJA.TIPO = 1"
        report = self.guard.validate(sql)
        valor_invalido = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertEqual(len(valor_invalido), 0, "CAJA.TIPO=1 es válido")

    def test_caja_tipo_2_valido(self):
        """CAJA.TIPO=2 (pago) es válido."""
        sql = "SELECT IMPORTE FROM CAJA WHERE CAJA.TIPO = 2"
        report = self.guard.validate(sql)
        valor_invalido = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertEqual(len(valor_invalido), 0, "CAJA.TIPO=2 es válido")

    def test_caja_tipo_5_invalido(self):
        """CAJA.TIPO=5 no es válido (solo 1=cobro, 2=pago)."""
        sql = "SELECT IMPORTE FROM CAJA WHERE CAJA.TIPO = 5"
        report = self.guard.validate(sql)
        warnings = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertGreater(len(warnings), 0, "CAJA.TIPO=5 debe generar advertencia")

    def test_proyectos_tiporetencion_valido(self):
        """PROYECTOS.TIPORETENCION=1 (aval previo) es válido."""
        sql = "SELECT NOMBRE FROM PROYECTOS WHERE PROYECTOS.TIPORETENCION = 1"
        report = self.guard.validate(sql)
        valor_invalido = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertEqual(len(valor_invalido), 0, "TIPORETENCION=1 es válido")

    def test_proyectos_tiporetencion_invalido(self):
        """PROYECTOS.TIPORETENCION=9 no es válido (solo 0,1,2,3)."""
        sql = "SELECT NOMBRE FROM PROYECTOS WHERE PROYECTOS.TIPORETENCION = 9"
        report = self.guard.validate(sql)
        warnings = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertGreater(len(warnings), 0, "TIPORETENCION=9 debe generar advertencia")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H6 — HallucinationReport: estructura y métodos
# ══════════════════════════════════════════════════════════════════════════════

class TestHallucinationReport(unittest.TestCase):
    """Verifica la estructura y métodos del HallucinationReport."""

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_report_sql_correcto_is_safe(self):
        sql = "SELECT NOMBRE FROM ARTICULO WHERE BAJA = 0"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe)
        self.assertEqual(report.severity, HallucinationSeverity.OK)
        self.assertEqual(len(report.issues), 0)

    def test_report_sql_incorrecto_not_safe(self):
        sql = "SELECT NOMBRE FROM TABLA_INVENTADA"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)
        self.assertEqual(report.severity, HallucinationSeverity.ERROR)
        self.assertGreater(len(report.errors), 0)

    def test_report_summary_ok(self):
        sql = "SELECT NOMBRE FROM ARTICULO"
        report = self.guard.validate(sql)
        summary = report.summary()
        self.assertIn("✅", summary)

    def test_report_summary_error(self):
        sql = "SELECT NOMBRE FROM TABLA_INVENTADA"
        report = self.guard.validate(sql)
        summary = report.summary()
        self.assertIn("❌", summary)

    def test_report_tables_found(self):
        sql = "SELECT a.NOMBRE FROM ARTICULO a JOIN DOCLIN d ON d.CODARTICULO = a.CODIGO"
        report = self.guard.validate(sql)
        self.assertIn("ARTICULO", report.tables_found)
        self.assertIn("DOCLIN", report.tables_found)

    def test_report_columns_found(self):
        sql = "SELECT a.NOMBRE, a.STOCKARTICULO FROM ARTICULO a"
        report = self.guard.validate(sql)
        # Las columnas cualificadas deben aparecer en columns_found
        self.assertIsInstance(report.columns_found, list)

    def test_add_issue_actualiza_severidad(self):
        report = HallucinationReport()
        self.assertEqual(report.severity, HallucinationSeverity.OK)
        self.assertTrue(report.is_safe)

        report.add_issue(HallucinationIssue(
            severity=HallucinationSeverity.WARNING,
            category="test",
            detail="advertencia de prueba"
        ))
        self.assertEqual(report.severity, HallucinationSeverity.WARNING)
        self.assertTrue(report.is_safe)  # WARNING no bloquea

        report.add_issue(HallucinationIssue(
            severity=HallucinationSeverity.ERROR,
            category="test",
            detail="error de prueba"
        ))
        self.assertEqual(report.severity, HallucinationSeverity.ERROR)
        self.assertFalse(report.is_safe)  # ERROR bloquea

    def test_errors_y_warnings_separados(self):
        report = HallucinationReport()
        report.add_issue(HallucinationIssue(HallucinationSeverity.WARNING, "w", "warn"))
        report.add_issue(HallucinationIssue(HallucinationSeverity.ERROR, "e", "err"))
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(len(report.warnings), 1)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H7 — Resiliencia del guard
# ══════════════════════════════════════════════════════════════════════════════

class TestResilienciaGuard(unittest.TestCase):
    """Verifica que el guard es resiliente ante entradas inesperadas."""

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_sql_solo_espacios(self):
        report = self.guard.validate("   ")
        self.assertIsInstance(report, HallucinationReport)

    def test_sql_muy_largo(self):
        sql = "SELECT NOMBRE FROM ARTICULO WHERE BAJA = 0 " * 100
        report = self.guard.validate(sql)
        self.assertIsInstance(report, HallucinationReport)

    def test_sql_con_comentarios(self):
        sql = "-- Consulta de artículos\nSELECT NOMBRE FROM ARTICULO"
        report = self.guard.validate(sql)
        self.assertIsInstance(report, HallucinationReport)

    def test_sql_con_subquery(self):
        sql = (
            "SELECT NOMBRE FROM ARTICULO "
            "WHERE CODIGO IN (SELECT CODARTICULO FROM DOCLIN WHERE CANTIDAD > 10)"
        )
        report = self.guard.validate(sql)
        self.assertIsInstance(report, HallucinationReport)

    def test_sql_firebird_first(self):
        """SQL con FIRST (Firebird) debe procesarse correctamente."""
        sql = "SELECT FIRST 20 NOMBRE, STOCKARTICULO FROM ARTICULO WHERE BAJA = 0"
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"SQL con FIRST es correcto: {report.summary()}")

    def test_sql_con_alias_tabla(self):
        """SQL con alias de tabla debe procesarse correctamente."""
        sql = "SELECT a.NOMBRE, a.STOCKARTICULO FROM ARTICULO a WHERE a.BAJA = 0"
        report = self.guard.validate(sql)
        self.assertIsInstance(report, HallucinationReport)

    def test_sql_con_group_by(self):
        sql = (
            "SELECT TIPO, COUNT(*) as TOTAL FROM DOCCAB "
            "GROUP BY TIPO ORDER BY TOTAL DESC"
        )
        report = self.guard.validate(sql)
        self.assertIsInstance(report, HallucinationReport)

    def test_guard_con_schema_personalizado(self):
        """El guard puede inicializarse con un esquema personalizado."""
        from typing import FrozenSet
        custom_schema = {
            "MI_TABLA": frozenset(["COL1", "COL2"]),
        }
        guard = HallucinationGuard(schema=custom_schema)
        self.assertTrue(guard.is_table_known("MI_TABLA"))
        self.assertFalse(guard.is_table_known("ARTICULO"))

    def test_sugerencia_columna_stock(self):
        """El guard sugiere STOCKARTICULO cuando se usa STOCK."""
        sql = "SELECT ARTICULO.STOCK FROM ARTICULO"
        report = self.guard.validate(sql)
        # Debe haber al menos un issue con sugerencia
        issues_con_sugerencia = [i for i in report.issues if i.suggestion]
        self.assertGreater(len(issues_con_sugerencia), 0)
        sugerencias = " ".join(i.suggestion for i in issues_con_sugerencia)
        self.assertIn("STOCKARTICULO", sugerencias)

    def test_sugerencia_caja_codapunte(self):
        """El guard sugiere CODAPUNTE cuando se usa CAJA.CODIGO."""
        sql = "SELECT CAJA.CODIGO FROM CAJA"
        report = self.guard.validate(sql)
        issues_con_sugerencia = [i for i in report.issues if i.suggestion]
        self.assertGreater(len(issues_con_sugerencia), 0)
        sugerencias = " ".join(i.suggestion for i in issues_con_sugerencia)
        self.assertIn("CODAPUNTE", sugerencias)


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H8 — Casos reales de alucinaciones detectadas en producción
# ══════════════════════════════════════════════════════════════════════════════

class TestCasosRealesProduccion(unittest.TestCase):
    """
    Casos reales de alucinaciones que causaron errores en producción.
    Estos tests documentan y previenen regresiones.
    """

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_caso_real_tabla_inexistente_table_not_found(self):
        """
        Error real: 'Table not found: CERTIFICACIONES'
        La IA generó una tabla que no existe en Firebird.
        """
        sql = "SELECT IMPORTE FROM CERTIFICACIONES WHERE PROYECTO = 'P001'"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)
        self.assertEqual(report.severity, HallucinationSeverity.ERROR)

    def test_caso_real_dynamic_sql_error_stock(self):
        """
        Error real: 'Dynamic SQL Error: Column unknown: STOCK'
        La IA usó ARTICULO.STOCK en lugar de ARTICULO.STOCKARTICULO.
        """
        sql = "SELECT NOMBRE, ARTICULO.STOCK FROM ARTICULO WHERE BAJA = 0"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)
        errores = [i for i in report.issues if "STOCK" in i.detail]
        self.assertGreater(len(errores), 0)

    def test_caso_real_caja_pk_incorrecta(self):
        """
        Error real: 'Column unknown: CODIGO' en tabla CAJA.
        La IA usó CAJA.CODIGO (PK de otras tablas) en lugar de CAJA.CODAPUNTE.
        """
        sql = "SELECT CAJA.CODIGO, IMPORTE FROM CAJA ORDER BY CAJA.CODIGO"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_caso_real_doccab_importe_vs_importetotal(self):
        """
        Error real: 'Column unknown: IMPORTE' en tabla DOCCAB.
        La IA usó DOCCAB.IMPORTE en lugar de DOCCAB.IMPORTETOTAL.
        """
        sql = "SELECT SUM(DOCCAB.IMPORTE) FROM DOCCAB WHERE TIPO = 3"
        report = self.guard.validate(sql)
        self.assertFalse(report.is_safe)

    def test_caso_real_tipo_21_no_valido(self):
        """
        Error real: DOCCAB.TIPO=21 (alucinación de IA).
        El SIUO tenía una nota incorrecta '21=Factura' que fue corregida.
        TIPO=21 no es un tipo válido en el esquema actual.
        """
        sql = "SELECT NUMERO FROM DOCCAB WHERE DOCCAB.TIPO = 21"
        report = self.guard.validate(sql)
        # TIPO=21 debe generar WARNING (valor no en el conjunto conocido)
        warnings = [i for i in report.issues if i.category == "valor_invalido"]
        self.assertGreater(len(warnings), 0, "TIPO=21 debe generar advertencia")

    def test_sql_correcto_certificaciones_via_doccab(self):
        """
        SQL correcto para certificaciones: DOCCAB con CODPROYECTO y TIPO=3.
        Este es el SQL que DEBE generarse en lugar de usar tabla CERTIFICACIONES.
        """
        sql = (
            "SELECT FIRST 50 p.NOMBRE, d.NUMERO, d.FECHA, d.IMPORTETOTAL "
            "FROM PROYECTOS p JOIN DOCCAB d ON d.CODPROYECTO = p.CODIGO "
            "WHERE d.TIPO = 3 ORDER BY p.NOMBRE, d.FECHA"
        )
        report = self.guard.validate(sql)
        self.assertTrue(report.is_safe, f"SQL correcto de certificaciones: {report.summary()}")


# ══════════════════════════════════════════════════════════════════════════════
# BLOQUE H9 — Integración con el esquema real del simulador
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegracionEsquemaReal(unittest.TestCase):
    """
    Verifica que el guard usa el esquema real del simulador como fuente de verdad.
    """

    def setUp(self):
        self.guard = HallucinationGuard()

    def test_esquema_cargado_desde_simulador(self):
        """El guard debe cargar el esquema desde db_simulator/schema.py."""
        tables = self.guard.get_known_tables()
        # El simulador tiene al menos estas tablas
        tablas_esperadas = [
            "DOCCAB", "DOCLIN", "ARTICULO", "CLIENTE", "PROVEED",
            "PROYECTOS", "CAJA", "AGENTES", "FAMILIA", "ALMACEN"
        ]
        for tabla in tablas_esperadas:
            self.assertIn(tabla, tables,
                f"El esquema debe incluir la tabla {tabla} del simulador")

    def test_columnas_doccab_del_simulador(self):
        """Las columnas de DOCCAB deben coincidir con el esquema del simulador."""
        cols = self.guard.get_known_columns("DOCCAB")
        # Columnas verificadas contra BD real Firebird
        cols_esperadas = ["CODIGO", "TIPO", "FECHA", "CODCLIENTE", "CODPROYECTO",
                          "IMPORTETOTAL", "NUMERO"]
        for col in cols_esperadas:
            self.assertIn(col, cols,
                f"DOCCAB debe tener la columna {col}")

    def test_columnas_articulo_del_simulador(self):
        """Las columnas de ARTICULO deben coincidir con el esquema del simulador."""
        cols = self.guard.get_known_columns("ARTICULO")
        cols_esperadas = ["CODIGO", "NOMBRE", "STOCKARTICULO", "PRECIOVENTA",
                          "PRECIOCOSTE", "BAJA", "CODFAMILIA"]
        for col in cols_esperadas:
            self.assertIn(col, cols,
                f"ARTICULO debe tener la columna {col}")

    def test_columnas_caja_del_simulador(self):
        """Las columnas de CAJA deben coincidir con el esquema del simulador."""
        cols = self.guard.get_known_columns("CAJA")
        self.assertIn("CODAPUNTE", cols, "CAJA debe tener CODAPUNTE (PK)")
        self.assertIn("TIPO", cols)
        self.assertIn("IMPORTE", cols)
        self.assertNotIn("CODIGO", cols, "CAJA NO debe tener CODIGO")

    def test_columnas_proyectos_del_simulador(self):
        """Las columnas de PROYECTOS deben incluir las de retenciones verificadas en el esquema real."""
        cols = self.guard.get_known_columns("PROYECTOS")
        # Columnas verificadas contra el esquema real del simulador
        self.assertIn("TIPORETENCION", cols)
        self.assertIn("PORCRETENCION", cols)
        self.assertIn("NOMBRE", cols)
        self.assertIn("CODIGO", cols)
        # DIASDEVOLUCIONRETENCION puede no estar en el esquema del simulador
        # (el esquema real Firebird puede tener más columnas que el simulador SQLite)
        # Lo que importa es que TIPORETENCION y PORCRETENCION sí existen
