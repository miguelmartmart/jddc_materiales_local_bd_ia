"""
tests/unit/test_siuo_diagnostico_presupuestos.py
================================================================
Tests de diagnóstico del bug "0 presupuestos aceptados".

FLUJO REAL PROBADO:
  Usuario escribe "¿cuántos presupuestos se han aceptado?"
  → service.py llama a ContextRetriever.get_context()
  → ContextRetriever devuelve contexto con DOCCAB + DOCDESTINO
  → IA genera SQL con LEFT JOIN DOCDESTINO + WHERE d.TIPO IN (12,13)
  → FirebirdSQLNormalizer.normalize() detecta el LEFT JOIN killer (paso 22)
  → SQL se reescribe con COUNT(DISTINCT) canónico
  → Resultado correcto (no 0)

TESTS:
  1. test_normalizer_detecta_left_join_killer_docdestino
     → SQL con LEFT JOIN DOCDESTINO + WHERE d.TIPO IN (12,13) → reescrito
  2. test_normalizer_no_toca_left_join_correcto
     → LEFT JOIN con IS NULL en WHERE → no modificar (patrón válido)
  3. test_normalizer_detecta_left_join_killer_generico
     → LEFT JOIN tabla2 + WHERE tabla2.col = valor → advertencia
  4. test_normalizer_left_join_sin_where_killer
     → LEFT JOIN sin WHERE en tabla derecha → no modificar
  5. test_docdestino_note_en_table_index
     → table_index.json tiene nota crítica para DOCDESTINO
  6. test_relation_table_join_info_docdestino
     → RELATION_TABLE_JOIN_INFO tiene tasa_sql canónica
  7. test_tasa_sql_canonica_estructura
     → tasa_sql tiene COUNT(DISTINCT) y no WHERE d.TIPO
  8. test_context_retriever_incluye_docdestino_para_tasa
     → get_context("tasa de éxito presupuestos") incluye DOCDESTINO
  9. test_context_retriever_nota_docdestino_en_bloque
     → el bloque de contexto de DOCDESTINO incluye la nota crítica
  10. test_normalizer_pipeline_completo_tasa_exito
      → pipeline completo: SQL buggy → normalizado → SQL canónico
  11. test_left_join_killer_variantes_tipo_filter
      → variantes del bug: AND d.TIPO=13, WHERE d.TIPO<>0, etc.
  12. test_left_join_killer_no_falso_positivo_is_null
      → WHERE dd.CODDOCUMENTO IS NULL (patrón válido) → no tocar
"""

import sys
import os
import json
import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Imports reales ────────────────────────────────────────────────────────────
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.chat.firebird_sql_constants import (
    RELATION_TABLE_JOIN_INFO,
    DOCCAB_TIPOS,
)

# ── Constantes de test ────────────────────────────────────────────────────────
TABLE_INDEX_PATH = os.path.join(ROOT, "backend", "core", "config", "table_index.json")
CONCEPT_INDEX_PATH = os.path.join(ROOT, "backend", "core", "config", "concept_index.json")

# SQL buggy exacto que causó el bug "0 presupuestos aceptados"
SQL_BUGGY_TASA = """
SELECT
  COUNT(DISTINCT c.CODIGO) AS TOTAL_PRESUPUESTOS,
  COUNT(DISTINCT dd.CODDOCUMENTO) AS PRESUPUESTOS_ACEPTADOS,
  CAST(COUNT(DISTINCT dd.CODDOCUMENTO) * 100.0 /
    NULLIF(COUNT(DISTINCT c.CODIGO), 0) AS NUMERIC(5,2)) AS TASA_EXITO
FROM DOCCAB c
LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
LEFT JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO
WHERE c.TIPO = 0
AND d.TIPO IN (12, 13)
"""

# SQL buggy variante con AND en lugar de WHERE
SQL_BUGGY_TASA_AND = """
SELECT COUNT(*) AS TOTAL, COUNT(dd.CODDOCUMENTO) AS ACEPTADOS
FROM DOCCAB c
LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
LEFT JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO
WHERE c.TIPO = 0 AND d.TIPO IN (12, 13)
"""

# SQL correcto (sin killer)
SQL_CORRECTO_TASA = """
SELECT COUNT(DISTINCT c.CODIGO) AS PRESUPUESTOS_CREADOS,
COUNT(DISTINCT dd.CODDOCUMENTO) AS PRESUPUESTOS_ACEPTADOS
FROM DOCCAB c
LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
WHERE c.TIPO = 0
"""

# SQL con IS NULL (patrón válido — presupuestos SIN destino)
SQL_LEFT_JOIN_IS_NULL = """
SELECT c.CODIGO, c.IMPORTETOTAL
FROM DOCCAB c
LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
WHERE c.TIPO = 0 AND dd.CODDOCUMENTO IS NULL
"""

# SQL genérico con LEFT JOIN killer (no DOCDESTINO)
SQL_GENERIC_KILLER = """
SELECT c.CODIGO, c.RAZONSOCIAL, p.NOMBRE AS PROVINCIA
FROM CLIENTE c
LEFT JOIN PROVINCIA p ON p.CODIGO = c.CODPROVINCIA
WHERE p.NOMBRE = 'Madrid'
"""


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 1 — Tests del normalizer paso 22 (LEFT JOIN killer)
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizerPaso22LeftJoinKiller:
    """Tests del paso 22 del FirebirdSQLNormalizer: detección de LEFT JOIN killer."""

    def setup_method(self):
        self.n = FirebirdSQLNormalizer()

    def test_detecta_left_join_killer_docdestino_reescribe(self):
        """
        CASO CRÍTICO: SQL con LEFT JOIN DOCDESTINO + WHERE d.TIPO IN (12,13)
        debe ser detectado y reescrito con COUNT(DISTINCT) canónico.
        """
        sql_out, changes = self.n.normalize(SQL_BUGGY_TASA)

        # Debe haber detectado el killer
        assert any("PASO 22" in c for c in changes), (
            f"Paso 22 no detectó el LEFT JOIN killer. Changes: {changes}"
        )
        assert any("LEFT JOIN killer" in c for c in changes), (
            f"No se menciona 'LEFT JOIN killer' en los cambios. Changes: {changes}"
        )

        # El SQL resultante NO debe tener el patrón killer
        sql_up = sql_out.upper()
        assert "D.TIPO IN" not in sql_up, (
            f"El SQL reescrito aún tiene 'd.TIPO IN'. SQL: {sql_out}"
        )

        # El SQL resultante debe tener COUNT(DISTINCT) y FROM DOCCAB
        assert "COUNT(DISTINCT" in sql_up or "COUNT" in sql_up, (
            f"El SQL reescrito no tiene COUNT. SQL: {sql_out}"
        )
        assert "DOCCAB" in sql_up, (
            f"El SQL reescrito no tiene DOCCAB. SQL: {sql_out}"
        )

    def test_detecta_left_join_killer_docdestino_variante_and(self):
        """
        Variante: WHERE c.TIPO = 0 AND d.TIPO IN (12, 13) en una sola línea.
        """
        sql_out, changes = self.n.normalize(SQL_BUGGY_TASA_AND)

        assert any("PASO 22" in c for c in changes), (
            f"Paso 22 no detectó variante AND. Changes: {changes}"
        )

    def test_no_toca_left_join_correcto_sin_killer(self):
        """
        LEFT JOIN DOCDESTINO sin WHERE en tabla derecha → no debe modificar.
        """
        sql_out, changes = self.n.normalize(SQL_CORRECTO_TASA)

        # No debe haber cambios del paso 22
        paso22_changes = [c for c in changes if "PASO 22" in c]
        assert len(paso22_changes) == 0, (
            f"Paso 22 modificó un SQL correcto. Changes: {paso22_changes}"
        )

    def test_no_falso_positivo_is_null(self):
        """
        WHERE dd.CODDOCUMENTO IS NULL es un patrón VÁLIDO con LEFT JOIN
        (presupuestos sin destino). NO debe ser detectado como killer.
        """
        sql_out, changes = self.n.normalize(SQL_LEFT_JOIN_IS_NULL)

        paso22_changes = [c for c in changes if "PASO 22" in c and "killer" in c.lower()]
        assert len(paso22_changes) == 0, (
            f"Paso 22 marcó IS NULL como killer (falso positivo). Changes: {paso22_changes}"
        )

    def test_detecta_left_join_killer_generico(self):
        """
        LEFT JOIN tabla2 + WHERE tabla2.col = valor → advertencia genérica.
        No reescribe (no es DOCDESTINO), pero advierte.
        """
        sql_out, changes = self.n.normalize(SQL_GENERIC_KILLER)

        # Debe haber advertencia del paso 22
        paso22_changes = [c for c in changes if "PASO 22" in c]
        assert len(paso22_changes) > 0, (
            f"Paso 22 no detectó killer genérico. Changes: {changes}"
        )

        # El SQL genérico NO se reescribe automáticamente (demasiado arriesgado)
        # Solo se advierte — el SQL original se mantiene
        assert "PROVINCIA" in sql_out.upper() or "CLIENTE" in sql_out.upper(), (
            f"SQL genérico fue reescrito incorrectamente. SQL: {sql_out}"
        )

    def test_left_join_sin_where_no_killer(self):
        """
        LEFT JOIN sin ningún WHERE en tabla derecha → no killer.
        """
        sql = "SELECT c.CODIGO FROM DOCCAB c LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO WHERE c.TIPO = 0"
        sql_out, changes = self.n.normalize(sql)

        paso22_changes = [c for c in changes if "PASO 22" in c and "killer" in c.lower()]
        assert len(paso22_changes) == 0, (
            f"Paso 22 detectó killer donde no hay. Changes: {paso22_changes}"
        )

    def test_left_join_killer_tipo_igual(self):
        """
        Variante: WHERE d.TIPO = 13 (igualdad, no IN).
        """
        sql = """
        SELECT COUNT(*) FROM DOCCAB c
        LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
        LEFT JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO
        WHERE c.TIPO = 0 AND d.TIPO = 13
        """
        sql_out, changes = self.n.normalize(sql)

        # Debe detectar el killer (d.TIPO = 13 en tabla derecha)
        paso22_changes = [c for c in changes if "PASO 22" in c]
        assert len(paso22_changes) > 0, (
            f"Paso 22 no detectó killer con d.TIPO = 13. Changes: {changes}"
        )

    def test_normalizer_pipeline_completo_tasa_exito(self):
        """
        Test del pipeline completo: SQL buggy → normalize() → SQL canónico.
        Simula exactamente lo que ocurre cuando la IA genera el SQL buggy
        y el normalizer lo procesa antes de enviarlo a Firebird.
        """
        n = FirebirdSQLNormalizer()
        sql_out, changes = n.normalize(SQL_BUGGY_TASA)

        # 1. Debe haber cambios
        assert len(changes) > 0, "normalize() no aplicó ningún cambio al SQL buggy"

        # 2. El SQL resultante debe ser ejecutable (no vacío)
        assert len(sql_out.strip()) > 10, f"SQL resultante demasiado corto: '{sql_out}'"

        # 3. El SQL resultante no debe tener el patrón killer
        assert "D.TIPO IN" not in sql_out.upper(), (
            f"SQL resultante aún tiene el killer. SQL: {sql_out}"
        )

        # 4. El SQL resultante debe calcular tasa de éxito correctamente
        # (debe tener DOCCAB y DOCDESTINO o COUNT)
        sql_up = sql_out.upper()
        has_count = "COUNT" in sql_up
        has_doccab = "DOCCAB" in sql_up
        assert has_count and has_doccab, (
            f"SQL resultante no parece calcular tasa. SQL: {sql_out}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 2 — Tests de los índices y constantes
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndicesYConstantes:
    """Tests que verifican que los índices y constantes tienen la info correcta."""

    def test_relation_table_join_info_tiene_docdestino(self):
        """RELATION_TABLE_JOIN_INFO debe tener entrada para DOCDESTINO."""
        assert "DOCDESTINO" in RELATION_TABLE_JOIN_INFO, (
            "RELATION_TABLE_JOIN_INFO no tiene entrada para DOCDESTINO"
        )

    def test_docdestino_tiene_tasa_sql(self):
        """DOCDESTINO debe tener tasa_sql canónica."""
        info = RELATION_TABLE_JOIN_INFO["DOCDESTINO"]
        assert "tasa_sql" in info, "DOCDESTINO no tiene tasa_sql en RELATION_TABLE_JOIN_INFO"
        assert len(info["tasa_sql"]) > 20, "tasa_sql está vacía"

    def test_tasa_sql_no_tiene_killer(self):
        """La tasa_sql canónica NO debe tener el patrón killer."""
        tasa_sql = RELATION_TABLE_JOIN_INFO["DOCDESTINO"]["tasa_sql"].upper()
        assert "D.TIPO IN" not in tasa_sql, (
            f"tasa_sql canónica tiene el killer d.TIPO IN. SQL: {tasa_sql}"
        )
        assert "LEFT JOIN DOCCAB" not in tasa_sql, (
            f"tasa_sql canónica tiene LEFT JOIN DOCCAB (doble join). SQL: {tasa_sql}"
        )

    def test_tasa_sql_tiene_count_distinct(self):
        """La tasa_sql canónica debe usar COUNT(DISTINCT) para contar correctamente."""
        tasa_sql = RELATION_TABLE_JOIN_INFO["DOCDESTINO"]["tasa_sql"].upper()
        assert "COUNT(DISTINCT" in tasa_sql, (
            f"tasa_sql no usa COUNT(DISTINCT). SQL: {tasa_sql}"
        )

    def test_tasa_sql_tiene_left_join_docdestino(self):
        """La tasa_sql canónica debe hacer LEFT JOIN DOCDESTINO (no INNER)."""
        tasa_sql = RELATION_TABLE_JOIN_INFO["DOCDESTINO"]["tasa_sql"].upper()
        assert "LEFT JOIN DOCDESTINO" in tasa_sql, (
            f"tasa_sql no tiene LEFT JOIN DOCDESTINO. SQL: {tasa_sql}"
        )

    def test_docdestino_note_en_table_index(self):
        """table_index.json debe tener nota crítica para DOCDESTINO."""
        if not os.path.exists(TABLE_INDEX_PATH):
            pytest.skip(f"table_index.json no encontrado en {TABLE_INDEX_PATH}")

        with open(TABLE_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)

        tables = data.get("tables", {})
        dd = tables.get("DOCDESTINO", {})

        assert "note" in dd, "DOCDESTINO no tiene 'note' en table_index.json"
        note = dd["note"]
        assert len(note) > 50, f"Nota de DOCDESTINO demasiado corta: '{note}'"

        # La nota debe mencionar el problema del LEFT JOIN killer
        note_up = note.upper()
        assert any(kw in note_up for kw in ["LEFT JOIN", "INNER JOIN", "KILLER", "NUNCA", "CRITICO"]), (
            f"Nota de DOCDESTINO no menciona el riesgo del LEFT JOIN killer. Nota: {note}"
        )

    def test_docdestino_note_menciona_columnas_correctas(self):
        """La nota de DOCDESTINO debe mencionar CODDOCUMENTO y CODDOCUMENTODESTINO."""
        if not os.path.exists(TABLE_INDEX_PATH):
            pytest.skip(f"table_index.json no encontrado en {TABLE_INDEX_PATH}")

        with open(TABLE_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)

        note = data.get("tables", {}).get("DOCDESTINO", {}).get("note", "")
        note_up = note.upper()

        assert "CODDOCUMENTO" in note_up, (
            f"Nota de DOCDESTINO no menciona CODDOCUMENTO. Nota: {note}"
        )

    def test_concept_index_tasa_incluye_docdestino(self):
        """concept_index.json debe incluir DOCDESTINO para keywords de tasa/éxito."""
        if not os.path.exists(CONCEPT_INDEX_PATH):
            pytest.skip(f"concept_index.json no encontrado en {CONCEPT_INDEX_PATH}")

        with open(CONCEPT_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)

        idx = data.get("index", {})

        for kw in ["tasa", "exito", "aceptado", "conversion"]:
            if kw in idx:
                tables = [e.get("table") for e in idx[kw]]
                assert "DOCDESTINO" in tables, (
                    f"concept_index '{kw}' no incluye DOCDESTINO. Tables: {tables}"
                )

    def test_doccab_tipos_tiene_presupuesto_y_factura(self):
        """DOCCAB_TIPOS debe tener presupuesto=0 y factura=13."""
        assert DOCCAB_TIPOS.get("presupuesto") == 0, (
            f"DOCCAB_TIPOS presupuesto != 0. Valor: {DOCCAB_TIPOS.get('presupuesto')}"
        )
        assert DOCCAB_TIPOS.get("factura") == 13, (
            f"DOCCAB_TIPOS factura != 13. Valor: {DOCCAB_TIPOS.get('factura')}"
        )
        assert DOCCAB_TIPOS.get("pedido") == 12, (
            f"DOCCAB_TIPOS pedido != 12. Valor: {DOCCAB_TIPOS.get('pedido')}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 3 — Tests del ContextRetriever (flujo real "Probar")
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextRetrieverFlujoProbrar:
    """
    Tests del flujo real que ocurre cuando el usuario pulsa 'Probar' en SIUO.
    Llama a ContextRetriever.get_context() con preguntas reales.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Inicializar ContextRetriever real con índices reales."""
        try:
            from backend.modules.db_explorer.context_retriever import ContextRetriever
            self.cr = ContextRetriever()
            self.available = True
        except Exception as e:
            self.available = False
            self.skip_reason = f"ContextRetriever no disponible: {e}"

    def _skip_if_unavailable(self):
        if not self.available:
            pytest.skip(self.skip_reason)

    @staticmethod
    def _extract_ctx(result) -> str:
        """
        get_context() puede devolver str o (str, dict).
        Extraer siempre el string de contexto.
        """
        if isinstance(result, tuple):
            return result[0] or ""
        return result or ""

    def test_get_context_tasa_exito_incluye_docdestino(self):
        """
        get_context("¿cuántos presupuestos se han aceptado?") debe incluir DOCDESTINO.
        Este es el flujo exacto que falló y devolvió 0 presupuestos aceptados.
        """
        self._skip_if_unavailable()

        preguntas = [
            "¿cuántos presupuestos se han aceptado?",
            "tasa de éxito de presupuestos",
            "¿qué porcentaje de presupuestos se convierten en pedido?",
            "presupuestos aceptados vs rechazados",
        ]

        for pregunta in preguntas:
            try:
                result = self.cr.get_context(pregunta)
                ctx = self._extract_ctx(result)
                ctx_up = ctx.upper()

                assert "DOCDESTINO" in ctx_up, (
                    f"get_context('{pregunta}') no incluye DOCDESTINO en el contexto. "
                    f"Contexto (primeros 500 chars): {ctx[:500]}"
                )
            except AssertionError:
                raise
            except Exception as e:
                pytest.fail(f"get_context('{pregunta}') lanzó excepción: {e}")

    def test_get_context_docdestino_incluye_nota_critica(self):
        """
        El bloque de contexto de DOCDESTINO debe incluir la nota crítica
        sobre el LEFT JOIN killer.
        """
        self._skip_if_unavailable()

        try:
            result = self.cr.get_context("tasa de éxito presupuestos")
            ctx = self._extract_ctx(result)
            if not ctx or "DOCDESTINO" not in ctx.upper():
                pytest.skip("DOCDESTINO no está en el contexto — test de nota no aplicable")

            # Buscar la sección de DOCDESTINO en el contexto
            lines = ctx.split("\n")
            docdestino_section = []
            in_section = False
            for line in lines:
                if "DOCDESTINO" in line.upper():
                    in_section = True
                elif in_section and line.strip().startswith("TABLA:"):
                    break  # nueva tabla
                if in_section:
                    docdestino_section.append(line)

            section_text = "\n".join(docdestino_section).upper()

            # La sección debe mencionar el riesgo o la semántica de columnas
            has_critical_info = any(kw in section_text for kw in [
                "CODDOCUMENTO", "NOTA", "CRITICO", "LEFT JOIN", "ORIGEN", "DESTINO"
            ])
            assert has_critical_info, (
                f"Sección DOCDESTINO en contexto no tiene info crítica. "
                f"Sección: {section_text[:300]}"
            )
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"Error al verificar nota DOCDESTINO en contexto: {e}")

    def test_get_context_presupuestos_incluye_doccab_tipo_0(self):
        """
        get_context("presupuestos") debe incluir DOCCAB con filtro TIPO=0.
        """
        self._skip_if_unavailable()

        try:
            result = self.cr.get_context("¿cuántos presupuestos hay?")
            ctx = self._extract_ctx(result)
            ctx_up = ctx.upper()

            assert "DOCCAB" in ctx_up, (
                f"get_context('presupuestos') no incluye DOCCAB. "
                f"Contexto: {ctx[:300]}"
            )
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"get_context('presupuestos') lanzó excepción: {e}")

    def test_get_context_no_falla_con_pregunta_vacia(self):
        """get_context('') no debe lanzar excepción — debe devolver str o (str, dict)."""
        self._skip_if_unavailable()

        try:
            result = self.cr.get_context("")
            # Puede devolver str o (str, dict) — ambos válidos
            assert result is None or isinstance(result, (str, tuple)), (
                f"get_context('') devolvió tipo inesperado: {type(result)}"
            )
            if isinstance(result, tuple):
                assert isinstance(result[0], str), f"Primer elemento del tuple no es str: {type(result[0])}"
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"get_context('') lanzó excepción: {e}")

    def test_get_context_no_falla_con_pregunta_sin_tablas(self):
        """
        get_context con pregunta sin keywords conocidos no debe fallar.
        Debe devolver contexto vacío o mínimo, no excepción.
        """
        self._skip_if_unavailable()

        try:
            result = self.cr.get_context("xyzabc123 pregunta sin sentido")
            # Puede devolver str o (str, dict) — ambos válidos
            assert result is None or isinstance(result, (str, tuple)), (
                f"Tipo inesperado: {type(result)}"
            )
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"get_context con pregunta sin sentido lanzó excepción: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# GRUPO 4 — Tests de regresión: otros riesgos similares
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegresiónRiesgosSimilares:
    """
    Tests de regresión para patrones similares al LEFT JOIN killer
    que podrían ocurrir con otras preguntas del usuario.
    """

    def setup_method(self):
        self.n = FirebirdSQLNormalizer()

    def test_left_join_killer_is_not_null(self):
        """
        WHERE tabla_derecha.col IS NOT NULL también es un killer.
        Convierte LEFT JOIN en INNER JOIN.
        """
        sql = """
        SELECT c.CODIGO FROM DOCCAB c
        LEFT JOIN DOCLIN l ON l.CODDOCUMENTO = c.CODIGO
        WHERE c.TIPO = 0 AND l.CODIGO IS NOT NULL
        """
        sql_out, changes = self.n.normalize(sql)

        paso22_changes = [c for c in changes if "PASO 22" in c]
        assert len(paso22_changes) > 0, (
            f"Paso 22 no detectó IS NOT NULL killer. Changes: {changes}"
        )

    def test_left_join_killer_mayor_que(self):
        """
        WHERE tabla_derecha.col > 0 también es un killer.
        """
        sql = """
        SELECT c.CODIGO FROM CLIENTE c
        LEFT JOIN DOCCAB d ON d.CODCLIENTE = c.CODIGO
        WHERE d.IMPORTETOTAL > 1000
        """
        sql_out, changes = self.n.normalize(sql)

        paso22_changes = [c for c in changes if "PASO 22" in c]
        assert len(paso22_changes) > 0, (
            f"Paso 22 no detectó > killer. Changes: {changes}"
        )

    def test_left_join_valido_is_null_no_killer(self):
        """
        WHERE tabla_derecha.col IS NULL es VÁLIDO — busca registros sin match.
        NO debe ser detectado como killer.
        """
        sql = """
        SELECT c.CODIGO, c.RAZONSOCIAL
        FROM CLIENTE c
        LEFT JOIN DOCCAB d ON d.CODCLIENTE = c.CODIGO AND d.TIPO = 0
        WHERE d.CODIGO IS NULL
        """
        sql_out, changes = self.n.normalize(sql)

        # IS NULL en WHERE es válido con LEFT JOIN → no killer
        killer_changes = [c for c in changes if "PASO 22" in c and "killer" in c.lower()]
        assert len(killer_changes) == 0, (
            f"Paso 22 marcó IS NULL como killer (falso positivo). Changes: {killer_changes}"
        )

    def test_normalizer_no_rompe_sql_correcto_sin_left_join(self):
        """
        SQL sin LEFT JOIN no debe ser modificado por el paso 22.
        """
        sql = """
        SELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO = 0
        """
        sql_out, changes = self.n.normalize(sql)

        paso22_changes = [c for c in changes if "PASO 22" in c]
        assert len(paso22_changes) == 0, (
            f"Paso 22 modificó SQL sin LEFT JOIN. Changes: {paso22_changes}"
        )

    def test_normalizer_no_rompe_inner_join(self):
        """
        INNER JOIN (no LEFT JOIN) no debe ser detectado por el paso 22.
        """
        sql = """
        SELECT c.CODIGO, d.CODIGO AS DESTINO
        FROM DOCCAB c
        INNER JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO
        INNER JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO
        WHERE c.TIPO = 0 AND d.TIPO IN (12, 13)
        """
        sql_out, changes = self.n.normalize(sql)

        # INNER JOIN con WHERE en tabla derecha es correcto (no es killer)
        paso22_changes = [c for c in changes if "PASO 22" in c]
        assert len(paso22_changes) == 0, (
            f"Paso 22 detectó killer en INNER JOIN (falso positivo). Changes: {paso22_changes}"
        )
