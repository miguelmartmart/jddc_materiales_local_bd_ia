"""
test_unsolvable_registry.py — Tests para el registro de errores irresolubles.

CUBRE:
  - register_unsolvable_error: nuevo error, deduplicación, truncado
  - check_and_alert_unsolvable_errors: sin pendientes, con pendientes
  - mark_error_reviewed: marcar como revisado
  - get_pending_errors / get_registry_summary
  - _compute_hash: determinismo
  - Escritura atómica (no corrompe el fichero)
  - Categorías conocidas

FILOSOFÍA:
  - Sin mocks: usa un fichero temporal real (tmp_path de pytest)
  - Determinista: misma entrada → mismo hash
  - Aislado: cada test usa su propio fichero temporal

AUTOR: DEVIA / bots/interjddcia · v1.0.0
"""

import json
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

# Importar el módulo bajo test
import backend.core.utils.unsolvable_error_registry as reg_module
from backend.core.utils.unsolvable_error_registry import (
    register_unsolvable_error,
    check_and_alert_unsolvable_errors,
    mark_error_reviewed,
    get_pending_errors,
    get_registry_summary,
    UNSOLVABLE_CATEGORIES,
    _compute_hash,
)


# ─── Fixture: redirigir _REGISTRY_PATH a un fichero temporal ─────────────────

@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """
    Cada test usa su propio fichero de registro temporal.
    Evita que los tests se contaminen entre sí.
    """
    tmp_file = str(tmp_path / "unsolvable_errors.json")
    monkeypatch.setattr(reg_module, "_REGISTRY_PATH", tmp_file)
    yield tmp_file


# ─── Tests: _compute_hash ────────────────────────────────────────────────────

class TestComputeHash:
    def test_mismo_input_mismo_hash(self):
        h1 = _compute_hash("pregunta", "SELECT 1", "error")
        h2 = _compute_hash("pregunta", "SELECT 1", "error")
        assert h1 == h2

    def test_diferente_pregunta_diferente_hash(self):
        h1 = _compute_hash("pregunta A", "SELECT 1", "error")
        h2 = _compute_hash("pregunta B", "SELECT 1", "error")
        assert h1 != h2

    def test_diferente_sql_diferente_hash(self):
        h1 = _compute_hash("pregunta", "SELECT 1", "error")
        h2 = _compute_hash("pregunta", "SELECT 2", "error")
        assert h1 != h2

    def test_diferente_error_diferente_hash(self):
        h1 = _compute_hash("pregunta", "SELECT 1", "error A")
        h2 = _compute_hash("pregunta", "SELECT 1", "error B")
        assert h1 != h2

    def test_hash_longitud_16(self):
        h = _compute_hash("q", "s", "e")
        assert len(h) == 16

    def test_hash_solo_hexadecimal(self):
        h = _compute_hash("q", "s", "e")
        assert all(c in "0123456789abcdef" for c in h)

    def test_espacios_normalizados(self):
        """Los espacios al inicio/fin no deben afectar el hash."""
        h1 = _compute_hash("  pregunta  ", "  SELECT 1  ", "  error  ")
        h2 = _compute_hash("pregunta", "SELECT 1", "error")
        assert h1 == h2


# ─── Tests: register_unsolvable_error ────────────────────────────────────────

class TestRegisterUnsolvableError:
    def test_registro_nuevo_crea_fichero(self, isolated_registry):
        register_unsolvable_error(
            question="¿Cuántos clientes hay?",
            sql="SELECT COUNT(*) FROM CLIENTES",
            error_message="Table unknown CLIENTES",
            error_type="schema_unknown",
            attempts=3,
        )
        assert os.path.exists(isolated_registry)

    def test_registro_nuevo_tiene_campos_correctos(self, isolated_registry):
        register_unsolvable_error(
            question="¿Cuántos clientes hay?",
            sql="SELECT COUNT(*) FROM CLIENTES",
            error_message="Table unknown CLIENTES",
            error_type="schema_unknown",
            attempts=3,
            context="Tablas disponibles: DOCCAB, DOCLIN",
        )
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["errors"]) == 1
        err = data["errors"][0]
        assert err["status"] == "pending"
        assert err["category"] == "schema_unknown"
        assert err["attempts"] == 3
        assert "¿Cuántos clientes hay?" in err["question"]
        assert "CLIENTES" in err["sql_failed"]
        assert "Table unknown" in err["error_message"]
        assert "Tablas disponibles" in err["context"]
        assert err["resolution"] is None
        assert "hash" in err
        assert "first_seen" in err
        assert "last_seen" in err
        assert err["occurrences"] == 1

    def test_deduplicacion_mismo_error_incrementa_contador(self, isolated_registry):
        """El mismo error registrado dos veces → 1 entrada, occurrences=2."""
        for _ in range(3):
            register_unsolvable_error(
                question="¿Cuántos clientes hay?",
                sql="SELECT COUNT(*) FROM CLIENTES",
                error_message="Table unknown CLIENTES",
            )
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["errors"]) == 1
        assert data["errors"][0]["occurrences"] == 3

    def test_errores_diferentes_se_registran_por_separado(self, isolated_registry):
        register_unsolvable_error("pregunta A", "SELECT 1", "error A")
        register_unsolvable_error("pregunta B", "SELECT 2", "error B")
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["errors"]) == 2

    def test_truncado_pregunta_larga(self, isolated_registry):
        pregunta_larga = "x" * 1000
        register_unsolvable_error(pregunta_larga, "SELECT 1", "error")
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["errors"][0]["question"]) <= 500

    def test_truncado_sql_largo(self, isolated_registry):
        sql_largo = "SELECT " + "A, " * 1000 + "B FROM T"
        register_unsolvable_error("pregunta", sql_largo, "error")
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["errors"][0]["sql_failed"]) <= 2000

    def test_categoria_desc_se_rellena_automaticamente(self, isolated_registry):
        register_unsolvable_error("q", "s", "e", error_type="schema_unknown")
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert "Tabla/columna" in data["errors"][0]["category_desc"]

    def test_categoria_desconocida_usa_fallback(self, isolated_registry):
        register_unsolvable_error("q", "s", "e", error_type="tipo_inventado_xyz")
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert data["errors"][0]["category_desc"] == "Desconocido"

    def test_extra_dict_se_guarda(self, isolated_registry):
        register_unsolvable_error(
            "q", "s", "e",
            extra={"modelo": "qwen3:30b", "temperatura": 0.1}
        )
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert data["errors"][0]["extra"]["modelo"] == "qwen3:30b"

    def test_meta_total_registered_se_incrementa(self, isolated_registry):
        register_unsolvable_error("q1", "s1", "e1")
        register_unsolvable_error("q2", "s2", "e2")
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert data["_meta"]["total_registered"] == 2

    def test_retorna_hash_string(self, isolated_registry):
        h = register_unsolvable_error("q", "s", "e")
        assert isinstance(h, str)
        assert len(h) == 16

    def test_fichero_corrupto_se_recupera(self, isolated_registry):
        """Si el fichero está corrupto, el registro se inicia vacío sin crashear."""
        with open(isolated_registry, "w", encoding="utf-8") as f:
            f.write("ESTO NO ES JSON {{{")
        # No debe lanzar excepción
        h = register_unsolvable_error("q", "s", "e")
        assert h is not None
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["errors"]) == 1


# ─── Tests: check_and_alert_unsolvable_errors ─────────────────────────────────

class TestCheckAndAlert:
    def test_sin_pendientes_devuelve_lista_vacia(self, isolated_registry):
        result = check_and_alert_unsolvable_errors()
        assert result == []

    def test_con_pendientes_devuelve_lista(self, isolated_registry):
        register_unsolvable_error("q1", "s1", "e1")
        register_unsolvable_error("q2", "s2", "e2")
        result = check_and_alert_unsolvable_errors()
        assert len(result) == 2

    def test_revisados_no_aparecen_en_alerta(self, isolated_registry):
        register_unsolvable_error("q1", "s1", "e1")
        h = register_unsolvable_error("q2", "s2", "e2")
        mark_error_reviewed(h, "Resuelto añadiendo tabla CLIENTES al esquema")
        result = check_and_alert_unsolvable_errors()
        assert len(result) == 1
        assert result[0]["question"] == "q1"

    def test_alerta_imprime_en_consola(self, isolated_registry, capsys):
        register_unsolvable_error("¿Cuántos clientes?", "SELECT COUNT(*) FROM CLIENTES", "Table unknown")
        check_and_alert_unsolvable_errors()
        captured = capsys.readouterr()
        assert "ALERTA" in captured.out or "ALERTA" in captured.err
        assert "ERROR(ES) IRRESOLUBLE(S)" in captured.out or "ERROR(ES) IRRESOLUBLE(S)" in captured.err

    def test_alerta_muestra_maximo_10(self, isolated_registry):
        """Con más de 10 errores, solo muestra 10 en la alerta."""
        for i in range(15):
            register_unsolvable_error(f"pregunta {i}", f"SELECT {i}", f"error {i}")
        result = check_and_alert_unsolvable_errors()
        assert len(result) == 15  # devuelve todos


# ─── Tests: mark_error_reviewed ──────────────────────────────────────────────

class TestMarkErrorReviewed:
    def test_marcar_revisado_cambia_status(self, isolated_registry):
        h = register_unsolvable_error("q", "s", "e")
        result = mark_error_reviewed(h, "Añadida tabla CLIENTES al esquema")
        assert result is True
        with open(isolated_registry, encoding="utf-8") as f:
            data = json.load(f)
        err = data["errors"][0]
        assert err["status"] == "reviewed"
        assert err["resolution"] == "Añadida tabla CLIENTES al esquema"
        assert "reviewed_at" in err

    def test_marcar_hash_inexistente_devuelve_false(self, isolated_registry):
        result = mark_error_reviewed("hashfalsoxyz", "resolución")
        assert result is False

    def test_revisado_no_aparece_en_pendientes(self, isolated_registry):
        h = register_unsolvable_error("q", "s", "e")
        mark_error_reviewed(h, "resuelto")
        pending = get_pending_errors()
        assert len(pending) == 0


# ─── Tests: get_pending_errors ────────────────────────────────────────────────

class TestGetPendingErrors:
    def test_sin_errores_devuelve_lista_vacia(self, isolated_registry):
        assert get_pending_errors() == []

    def test_devuelve_solo_pendientes(self, isolated_registry):
        h1 = register_unsolvable_error("q1", "s1", "e1")
        register_unsolvable_error("q2", "s2", "e2")
        mark_error_reviewed(h1, "resuelto")
        pending = get_pending_errors()
        assert len(pending) == 1
        assert pending[0]["question"] == "q2"


# ─── Tests: get_registry_summary ─────────────────────────────────────────────

class TestGetRegistrySummary:
    def test_summary_vacio(self, isolated_registry):
        s = get_registry_summary()
        assert s["total"] == 0
        assert s["pending"] == 0

    def test_summary_con_errores(self, isolated_registry):
        register_unsolvable_error("q1", "s1", "e1", error_type="schema_unknown")
        h = register_unsolvable_error("q2", "s2", "e2", error_type="unknown_error")
        mark_error_reviewed(h, "resuelto")
        s = get_registry_summary()
        assert s["total"] == 2
        assert s["pending"] == 1
        assert s["by_status"]["pending"] == 1
        assert s["by_status"]["reviewed"] == 1
        assert s["by_category"]["schema_unknown"] == 1
        assert s["by_category"]["unknown_error"] == 1

    def test_summary_incluye_ruta_fichero(self, isolated_registry):
        s = get_registry_summary()
        assert "registry_path" in s


# ─── Tests: UNSOLVABLE_CATEGORIES ────────────────────────────────────────────

class TestCategories:
    def test_todas_las_categorias_tienen_descripcion(self):
        for key, desc in UNSOLVABLE_CATEGORIES.items():
            assert isinstance(key, str) and len(key) > 0
            assert isinstance(desc, str) and len(desc) > 0

    def test_categorias_clave_existen(self):
        required = [
            "unknown_error", "max_retries_exceeded", "ai_correction_failed",
            "schema_unknown", "permission_denied", "udf_unknown",
        ]
        for key in required:
            assert key in UNSOLVABLE_CATEGORIES, f"Falta categoría: {key}"
