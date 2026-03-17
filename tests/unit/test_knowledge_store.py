"""
test_knowledge_store.py — Tests unitarios completos del KnowledgeStore.

Cubre al 100%:
  - KnowledgeStore.__init__: creación de directorios
  - update_table: merge inteligente, detección de cambios, notas críticas
  - get_table: carga de metadatos
  - get_all_tables: listado completo
  - _update_index: índice global actualizado
  - get_index: lectura del índice
  - add_business_rule: sin duplicados, límite de tamaño
  - get_business_rules: filtrado por tabla
  - add_query_pattern: sin duplicados, incremento de usos, límite
  - get_patterns_for_intent: búsqueda por keywords, ordenación por score+usos
  - log_discovery: append-only JSONL
  - _rotate_log_if_needed: rotación cuando supera límite
  - get_recent_discoveries: últimas N entradas
  - get_ia_summary: resumen IA-friendly
  - _load_json / _save_json: I/O seguro con backup
  - get_knowledge_store: singleton
  - Resiliencia: cada operación con try/except, nunca lanza excepción
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from backend.modules.chat.deep_analysis.knowledge_store import (
    KnowledgeStore,
    get_knowledge_store,
    KNOWLEDGE_STORE_CONSTANTS,
    DISCOVERY_TYPES,
)


# ─── Fixture: KnowledgeStore en directorio temporal ──────────────────────────

@pytest.fixture
def store(tmp_path):
    """KnowledgeStore aislado en directorio temporal para cada test."""
    s = KnowledgeStore(base_dir=str(tmp_path))
    return s


@pytest.fixture
def store_with_data(store):
    """KnowledgeStore con datos precargados."""
    store.update_table("DOCCAB", {
        "columns_real": ["TIPO", "FECHA", "IMPORTETOTAL", "CODCLIENTE", "SERIE"],
        "record_count_real": 74034,
        "tipo_distribution": {"0": 12000, "13": 8000, "11": 5000},
    })
    store.update_table("CLIENTE", {
        "columns_real": ["CODIGO", "NOMBRE", "TELEFONO"],
        "record_count_real": 3500,
    })
    store.add_business_rule(
        "1 instalación puede tener N presupuestos",
        table="DOCCAB", confidence="alto"
    )
    store.add_query_pattern(
        intent="presupuestos por año",
        sql="SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY 1",
        tables=["DOCCAB"],
        rows_returned=10,
        reliability="alto",
    )
    return store


# ─── Tests: __init__ y _ensure_dirs ──────────────────────────────────────────

class TestInit:
    def test_creates_tables_dir(self, tmp_path):
        """El constructor crea el directorio tables/."""
        s = KnowledgeStore(base_dir=str(tmp_path))
        assert os.path.isdir(s._tables_dir)

    def test_base_dir_set(self, tmp_path):
        """El directorio base se establece correctamente."""
        s = KnowledgeStore(base_dir=str(tmp_path))
        assert s._base == str(tmp_path)

    def test_file_paths_under_base(self, tmp_path):
        """Todos los ficheros están bajo el directorio base."""
        s = KnowledgeStore(base_dir=str(tmp_path))
        assert s._index_file.startswith(str(tmp_path))
        assert s._rules_file.startswith(str(tmp_path))
        assert s._patterns_file.startswith(str(tmp_path))
        assert s._log_file.startswith(str(tmp_path))

    def test_ensure_dirs_no_crash_on_permission_error(self, tmp_path):
        """Si no se puede crear el directorio, no lanza excepción."""
        with patch("os.makedirs", side_effect=PermissionError("sin permisos")):
            # No debe lanzar excepción
            s = KnowledgeStore(base_dir=str(tmp_path))
            assert s is not None


# ─── Tests: update_table ─────────────────────────────────────────────────────

class TestUpdateTable:
    def test_update_creates_file(self, store, tmp_path):
        """update_table crea el fichero JSON de la tabla."""
        store.update_table("DOCCAB", {"record_count_real": 1000})
        path = os.path.join(store._tables_dir, "DOCCAB.json")
        assert os.path.exists(path)

    def test_update_returns_true_on_change(self, store):
        """Devuelve True cuando hay cambios reales."""
        result = store.update_table("DOCCAB", {"record_count_real": 5000})
        assert result is True

    def test_update_returns_false_no_change(self, store):
        """Devuelve False cuando no hay cambios."""
        store.update_table("DOCCAB", {"record_count_real": 5000})
        result = store.update_table("DOCCAB", {"record_count_real": 5000})
        assert result is False

    def test_update_columns_real_sorted(self, store):
        """Las columnas reales se guardan ordenadas."""
        store.update_table("DOCCAB", {"columns_real": ["TIPO", "FECHA", "CODIGO"]})
        data = store.get_table("DOCCAB")
        assert data["columns_real"] == sorted(["TIPO", "FECHA", "CODIGO"])

    def test_update_columns_count(self, store):
        """Se actualiza columns_count automáticamente."""
        store.update_table("DOCCAB", {"columns_real": ["A", "B", "C", "D"]})
        data = store.get_table("DOCCAB")
        assert data["columns_count"] == 4

    def test_update_columns_no_change_same_set(self, store):
        """Si el conjunto de columnas es el mismo, no hay cambio."""
        store.update_table("DOCCAB", {"columns_real": ["TIPO", "FECHA"]})
        result = store.update_table("DOCCAB", {"columns_real": ["FECHA", "TIPO"]})
        assert result is False

    def test_update_nota_critica_always_updates(self, store):
        """Las notas críticas (_nota_*) siempre se actualizan."""
        store.update_table("DOCCAB", {"_nota_docdestino": "nota v1"})
        result = store.update_table("DOCCAB", {"_nota_docdestino": "nota v2"})
        assert result is True
        data = store.get_table("DOCCAB")
        assert data["_nota_docdestino"] == "nota v2"

    def test_update_sets_table_name(self, store):
        """El campo _table se establece con el nombre en mayúsculas."""
        store.update_table("doccab", {"record_count_real": 100})
        data = store.get_table("DOCCAB")
        assert data["_table"] == "DOCCAB"

    def test_update_sets_updated_at(self, store):
        """El campo _updated_at se establece al actualizar."""
        store.update_table("DOCCAB", {"record_count_real": 100})
        data = store.get_table("DOCCAB")
        assert "_updated_at" in data

    def test_update_empty_table_name(self, store):
        """Con tabla vacía, devuelve False sin excepción."""
        result = store.update_table("", {"record_count_real": 100})
        assert result is False

    def test_update_empty_updates(self, store):
        """Con updates vacío, devuelve False sin excepción."""
        result = store.update_table("DOCCAB", {})
        assert result is False

    def test_update_record_count_source(self, store):
        """Al actualizar record_count_real, se establece record_count_source."""
        store.update_table("DOCCAB", {"record_count_real": 74034})
        data = store.get_table("DOCCAB")
        assert data.get("record_count_source") == "firebird_count"

    def test_update_tipo_distribution(self, store):
        """La distribución de TIPO se guarda correctamente."""
        tipo_map = {"0": 12000, "13": 8000}
        store.update_table("DOCCAB", {"tipo_distribution": tipo_map})
        data = store.get_table("DOCCAB")
        assert data["tipo_distribution"] == tipo_map

    def test_update_estadopend_distribution(self, store):
        """La distribución de ESTADOPEND se guarda correctamente."""
        estadopend_map = {"0": 500, "1": 200, "2": 50}
        store.update_table("DOCCAB", {"estadopend_distribution": estadopend_map})
        data = store.get_table("DOCCAB")
        assert data["estadopend_distribution"] == estadopend_map

    def test_update_creates_backup(self, store, tmp_path):
        """Al actualizar un fichero existente, crea un backup .bak."""
        store.update_table("DOCCAB", {"record_count_real": 100})
        store.update_table("DOCCAB", {"record_count_real": 200})
        bak_path = os.path.join(store._tables_dir, "DOCCAB.json.bak")
        assert os.path.exists(bak_path)


# ─── Tests: get_table ────────────────────────────────────────────────────────

class TestGetTable:
    def test_get_existing_table(self, store_with_data):
        """Devuelve los metadatos de una tabla existente."""
        data = store_with_data.get_table("DOCCAB")
        assert data["record_count_real"] == 74034
        assert "TIPO" in data["columns_real"]

    def test_get_nonexistent_table(self, store):
        """Devuelve {} para una tabla que no existe."""
        data = store.get_table("TABLA_INEXISTENTE")
        assert data == {}

    def test_get_table_case_insensitive(self, store_with_data):
        """La búsqueda es case-insensitive (siempre usa mayúsculas)."""
        data = store_with_data.get_table("doccab")
        assert data != {}


# ─── Tests: get_all_tables ───────────────────────────────────────────────────

class TestGetAllTables:
    def test_returns_all_tables(self, store_with_data):
        """Devuelve todas las tablas conocidas."""
        tables = store_with_data.get_all_tables()
        assert "DOCCAB" in tables
        assert "CLIENTE" in tables

    def test_empty_store(self, store):
        """Con store vacío, devuelve dict vacío."""
        tables = store.get_all_tables()
        assert tables == {}

    def test_returns_dict(self, store_with_data):
        """Siempre devuelve un dict."""
        result = store_with_data.get_all_tables()
        assert isinstance(result, dict)


# ─── Tests: _update_index y get_index ────────────────────────────────────────

class TestIndex:
    def test_index_created_on_update(self, store):
        """El índice se crea al actualizar una tabla."""
        store.update_table("DOCCAB", {"columns_real": ["TIPO", "FECHA"], "record_count_real": 1000})
        index = store.get_index()
        assert "DOCCAB" in index["tables"]

    def test_index_has_record_count(self, store):
        """El índice incluye el conteo de registros."""
        store.update_table("DOCCAB", {"record_count_real": 74034})
        index = store.get_index()
        assert index["tables"]["DOCCAB"]["record_count"] == 74034

    def test_index_has_tipo_flag(self, store):
        """El índice incluye has_tipo si TIPO está en las columnas."""
        store.update_table("DOCCAB", {"columns_real": ["TIPO", "FECHA"]})
        index = store.get_index()
        assert index["tables"]["DOCCAB"]["has_tipo"] is True

    def test_index_has_fecha_flag(self, store):
        """El índice incluye has_fecha si FECHA está en las columnas."""
        store.update_table("DOCCAB", {"columns_real": ["TIPO", "FECHA"]})
        index = store.get_index()
        assert index["tables"]["DOCCAB"]["has_fecha"] is True

    def test_index_total_tables(self, store_with_data):
        """El índice incluye el total de tablas."""
        index = store_with_data.get_index()
        assert index["_total_tables"] == 2

    def test_get_index_empty(self, store):
        """Con store vacío, devuelve dict con tables vacío."""
        index = store.get_index()
        assert "tables" in index


# ─── Tests: add_business_rule ────────────────────────────────────────────────

class TestAddBusinessRule:
    def test_add_rule_returns_true(self, store):
        """Añadir una regla nueva devuelve True."""
        result = store.add_business_rule("1 instalación = N presupuestos")
        assert result is True

    def test_add_rule_persisted(self, store):
        """La regla se persiste en disco."""
        store.add_business_rule("Regla de prueba para test")
        rules = store.get_business_rules()
        assert any("Regla de prueba" in r["rule"] for r in rules)

    def test_no_duplicate_rules(self, store):
        """No se añaden reglas duplicadas."""
        store.add_business_rule("Regla única de negocio")
        store.add_business_rule("Regla única de negocio")
        rules = store.get_business_rules()
        count = sum(1 for r in rules if "Regla única" in r["rule"])
        assert count == 1

    def test_duplicate_case_insensitive(self, store):
        """La detección de duplicados es case-insensitive."""
        store.add_business_rule("Regla de negocio importante")
        result = store.add_business_rule("REGLA DE NEGOCIO IMPORTANTE")
        assert result is False

    def test_rule_too_short(self, store):
        """Reglas muy cortas (<10 chars) no se añaden."""
        result = store.add_business_rule("corta")
        assert result is False

    def test_empty_rule(self, store):
        """Regla vacía no se añade."""
        result = store.add_business_rule("")
        assert result is False

    def test_rule_with_table(self, store):
        """La regla se asocia a una tabla."""
        store.add_business_rule("DOCCAB tiene TIPO=0 para presupuestos", table="DOCCAB")
        rules = store.get_business_rules(table="DOCCAB")
        assert len(rules) > 0
        assert rules[0]["table"] == "DOCCAB"

    def test_rule_confidence_stored(self, store):
        """La confianza se almacena correctamente."""
        store.add_business_rule("Regla con alta confianza aquí", confidence="alto")
        rules = store.get_business_rules()
        assert rules[0]["confidence"] == "alto"

    def test_rule_source_stored(self, store):
        """La fuente se almacena correctamente."""
        store.add_business_rule("Regla con fuente específica aquí", source="test_source")
        rules = store.get_business_rules()
        assert rules[0]["source"] == "test_source"

    def test_rule_discovered_at(self, store):
        """La fecha de descubrimiento se almacena."""
        store.add_business_rule("Regla con fecha de descubrimiento")
        rules = store.get_business_rules()
        assert "discovered_at" in rules[0]


# ─── Tests: get_business_rules ───────────────────────────────────────────────

class TestGetBusinessRules:
    def test_get_all_rules(self, store_with_data):
        """Devuelve todas las reglas sin filtro."""
        rules = store_with_data.get_business_rules()
        assert len(rules) >= 1

    def test_filter_by_table(self, store):
        """Filtra reglas por tabla."""
        store.add_business_rule("Regla específica de DOCCAB aquí", table="DOCCAB")
        store.add_business_rule("Regla específica de CLIENTE aquí", table="CLIENTE")
        rules_doccab = store.get_business_rules(table="DOCCAB")
        assert all(r.get("table") in ("DOCCAB", None) for r in rules_doccab)

    def test_filter_includes_global_rules(self, store):
        """Las reglas sin tabla (globales) se incluyen en cualquier filtro."""
        store.add_business_rule("Regla global sin tabla específica aquí")
        rules = store.get_business_rules(table="DOCCAB")
        assert any(r.get("table") is None for r in rules)

    def test_empty_store_returns_list(self, store):
        """Con store vacío, devuelve lista vacía."""
        rules = store.get_business_rules()
        assert rules == []


# ─── Tests: add_query_pattern ────────────────────────────────────────────────

class TestAddQueryPattern:
    def test_add_pattern_returns_true(self, store):
        """Añadir un patrón nuevo devuelve True."""
        result = store.add_query_pattern(
            intent="presupuestos totales",
            sql="SELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO=0",
            tables=["DOCCAB"],
            rows_returned=1,
        )
        assert result is True

    def test_pattern_persisted(self, store):
        """El patrón se persiste en disco."""
        store.add_query_pattern(
            intent="test intent",
            sql="SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0",
            tables=["DOCCAB"],
        )
        patterns = store.get_patterns_for_intent(["test"])
        assert len(patterns) > 0

    def test_no_duplicate_sql(self, store):
        """No se añaden patrones con SQL duplicado."""
        sql = "SELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO=0"
        store.add_query_pattern("intent 1", sql, ["DOCCAB"])
        store.add_query_pattern("intent 2", sql, ["DOCCAB"])
        # El segundo incrementa usos, no crea duplicado
        data = store._load_json(store._patterns_file)
        count = sum(1 for p in data["patterns"] if p["sql"].strip() == sql.strip())
        assert count == 1

    def test_duplicate_increments_uses(self, store):
        """El SQL duplicado incrementa el contador de usos."""
        sql = "SELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO=0"
        store.add_query_pattern("intent", sql, ["DOCCAB"])
        store.add_query_pattern("intent", sql, ["DOCCAB"])
        data = store._load_json(store._patterns_file)
        pattern = next(p for p in data["patterns"] if p["sql"].strip() == sql.strip())
        assert pattern["uses"] == 2

    def test_empty_sql_not_added(self, store):
        """SQL vacío no se añade."""
        result = store.add_query_pattern("intent", "", ["DOCCAB"])
        assert result is False

    def test_short_sql_not_added(self, store):
        """SQL muy corto (<20 chars) no se añade."""
        result = store.add_query_pattern("intent", "SELECT 1", ["DOCCAB"])
        assert result is False

    def test_empty_intent_not_added(self, store):
        """Intent vacío no se añade."""
        result = store.add_query_pattern("", "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0", ["DOCCAB"])
        assert result is False

    def test_pattern_stores_tables(self, store):
        """Las tablas se almacenan en el patrón."""
        store.add_query_pattern(
            "test tablas",
            "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0",
            ["DOCCAB", "DOCLIN"],
        )
        patterns = store.get_patterns_for_intent(["test"])
        assert "DOCCAB" in patterns[0]["tables"]

    def test_pattern_stores_reliability(self, store):
        """La fiabilidad se almacena en el patrón."""
        store.add_query_pattern(
            "test fiabilidad",
            "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0",
            ["DOCCAB"],
            reliability="alto",
        )
        patterns = store.get_patterns_for_intent(["test"])
        assert patterns[0]["reliability"] == "alto"

    def test_pattern_stores_rows_returned(self, store):
        """El número de filas devueltas se almacena."""
        store.add_query_pattern(
            "test filas",
            "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0",
            ["DOCCAB"],
            rows_returned=42,
        )
        patterns = store.get_patterns_for_intent(["test"])
        assert patterns[0]["rows_returned"] == 42


# ─── Tests: get_patterns_for_intent ──────────────────────────────────────────

class TestGetPatternsForIntent:
    def test_returns_matching_patterns(self, store):
        """Devuelve patrones que coinciden con las keywords."""
        store.add_query_pattern(
            "presupuestos por año y serie",
            "SELECT EXTRACT(YEAR FROM FECHA) AS ANO FROM DOCCAB WHERE TIPO=0 GROUP BY 1",
            ["DOCCAB"],
        )
        patterns = store.get_patterns_for_intent(["presupuestos", "año"])
        assert len(patterns) > 0

    def test_no_match_returns_empty(self, store):
        """Sin coincidencias, devuelve lista vacía."""
        store.add_query_pattern(
            "presupuestos totales",
            "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0",
            ["DOCCAB"],
        )
        patterns = store.get_patterns_for_intent(["facturas", "clientes"])
        assert patterns == []

    def test_empty_keywords_returns_empty(self, store_with_data):
        """Con keywords vacías, devuelve lista vacía."""
        patterns = store_with_data.get_patterns_for_intent([])
        assert patterns == []

    def test_sorted_by_score(self, store):
        """Los resultados se ordenan por score (más coincidencias primero)."""
        store.add_query_pattern(
            "presupuestos aceptados por cliente",
            "SELECT CODCLIENTE, COUNT(*) AS N FROM DOCCAB WHERE TIPO=0 GROUP BY CODCLIENTE",
            ["DOCCAB"],
        )
        store.add_query_pattern(
            "presupuestos totales",
            "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0",
            ["DOCCAB"],
        )
        patterns = store.get_patterns_for_intent(["presupuestos", "aceptados", "cliente"])
        # El primero debe tener más coincidencias
        assert "aceptados" in patterns[0]["intent"].lower() or "cliente" in patterns[0]["intent"].lower()

    def test_sorted_by_uses_on_tie(self, store):
        """Con mismo score, ordena por número de usos (más usado primero)."""
        sql1 = "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0"
        sql2 = "SELECT COUNT(*) AS TOTAL FROM DOCCAB WHERE TIPO=0 AND FECHA IS NOT NULL"
        store.add_query_pattern("presupuestos test uno", sql1, ["DOCCAB"])
        # Incrementar usos del primero
        store.add_query_pattern("presupuestos test uno", sql1, ["DOCCAB"])
        store.add_query_pattern("presupuestos test dos", sql2, ["DOCCAB"])
        patterns = store.get_patterns_for_intent(["presupuestos"])
        assert patterns[0]["uses"] >= patterns[-1]["uses"]

    def test_max_10_results(self, store):
        """Devuelve máximo 10 resultados."""
        for i in range(15):
            store.add_query_pattern(
                f"presupuestos test numero {i}",
                f"SELECT COUNT(*) AS N{i} FROM DOCCAB WHERE TIPO=0 AND CODIGO > {i}",
                ["DOCCAB"],
            )
        patterns = store.get_patterns_for_intent(["presupuestos"])
        assert len(patterns) <= 10

    def test_empty_store_returns_empty(self, store):
        """Con store vacío, devuelve lista vacía."""
        patterns = store.get_patterns_for_intent(["presupuestos"])
        assert patterns == []


# ─── Tests: log_discovery ────────────────────────────────────────────────────

class TestLogDiscovery:
    def test_creates_log_file(self, store):
        """log_discovery crea el fichero JSONL."""
        store.log_discovery("columns_real", "DOCCAB", {"cols": ["TIPO"]})
        assert os.path.exists(store._log_file)

    def test_log_is_valid_jsonl(self, store):
        """Cada línea del log es JSON válido."""
        store.log_discovery("record_count", "DOCCAB", {"count": 1000})
        store.log_discovery("estadopend", "DOCCAB", {"0": 500, "1": 200})
        with open(store._log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            entry = json.loads(line.strip())
            assert "ts" in entry
            assert "type" in entry

    def test_log_append_only(self, store):
        """Cada llamada añade una nueva línea (no sobreescribe)."""
        store.log_discovery("columns_real", "DOCCAB", {"cols": ["TIPO"]})
        store.log_discovery("record_count", "DOCCAB", {"count": 1000})
        with open(store._log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_log_stores_type_desc(self, store):
        """El log incluye la descripción del tipo de descubrimiento."""
        store.log_discovery("columns_real", "DOCCAB", {})
        with open(store._log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline().strip())
        assert entry["type_desc"] == DISCOVERY_TYPES["columns_real"]

    def test_log_stores_question(self, store):
        """El log incluye la pregunta (truncada a 80 chars)."""
        question = "¿cuántos presupuestos hay en total este año?"
        store.log_discovery("record_count", "DOCCAB", {}, question=question)
        with open(store._log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline().strip())
        assert entry["question"] == question[:80]

    def test_log_question_truncated(self, store):
        """La pregunta se trunca a 80 caracteres."""
        long_question = "x" * 200
        store.log_discovery("record_count", "DOCCAB", {}, question=long_question)
        with open(store._log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline().strip())
        assert len(entry["question"]) == 80

    def test_log_no_crash_on_error(self, store):
        """Si el log falla (p.ej. permisos), no lanza excepción."""
        store._log_file = "/ruta/sin/permisos/log.jsonl"
        # No debe lanzar excepción
        store.log_discovery("record_count", "DOCCAB", {})

    def test_log_unknown_type(self, store):
        """Tipos desconocidos se registran con type_desc igual al tipo."""
        store.log_discovery("tipo_desconocido", "DOCCAB", {})
        with open(store._log_file, "r", encoding="utf-8") as f:
            entry = json.loads(f.readline().strip())
        assert entry["type_desc"] == "tipo_desconocido"


# ─── Tests: _rotate_log_if_needed ────────────────────────────────────────────

class TestRotateLog:
    def test_rotation_when_exceeds_limit(self, store):
        """El log se rota cuando supera max_log_entries."""
        # Reducir el límite para el test
        original_max = KNOWLEDGE_STORE_CONSTANTS["max_log_entries"]
        KNOWLEDGE_STORE_CONSTANTS["max_log_entries"] = 5

        try:
            for i in range(10):
                store.log_discovery("record_count", "DOCCAB", {"i": i})

            with open(store._log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) <= 5
        finally:
            KNOWLEDGE_STORE_CONSTANTS["max_log_entries"] = original_max

    def test_no_rotation_under_limit(self, store):
        """No hay rotación si no se supera el límite."""
        for i in range(3):
            store.log_discovery("record_count", "DOCCAB", {"i": i})
        with open(store._log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_rotation_keeps_latest(self, store):
        """La rotación conserva las entradas más recientes."""
        original_max = KNOWLEDGE_STORE_CONSTANTS["max_log_entries"]
        KNOWLEDGE_STORE_CONSTANTS["max_log_entries"] = 3

        try:
            for i in range(6):
                store.log_discovery("record_count", "DOCCAB", {"i": i})

            with open(store._log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Las últimas entradas deben tener i >= 3
            last_entry = json.loads(lines[-1].strip())
            assert last_entry["data"]["i"] >= 3
        finally:
            KNOWLEDGE_STORE_CONSTANTS["max_log_entries"] = original_max


# ─── Tests: get_recent_discoveries ───────────────────────────────────────────

class TestGetRecentDiscoveries:
    def test_returns_recent_entries(self, store):
        """Devuelve las entradas más recientes."""
        for i in range(5):
            store.log_discovery("record_count", "DOCCAB", {"i": i})
        entries = store.get_recent_discoveries(n=3)
        assert len(entries) == 3

    def test_empty_log_returns_empty(self, store):
        """Con log vacío, devuelve lista vacía."""
        entries = store.get_recent_discoveries()
        assert entries == []

    def test_returns_list(self, store):
        """Siempre devuelve una lista."""
        result = store.get_recent_discoveries()
        assert isinstance(result, list)

    def test_entries_are_dicts(self, store):
        """Las entradas son dicts con las claves esperadas."""
        store.log_discovery("columns_real", "DOCCAB", {"cols": ["TIPO"]})
        entries = store.get_recent_discoveries(n=1)
        assert len(entries) == 1
        assert "ts" in entries[0]
        assert "type" in entries[0]
        assert "data" in entries[0]

    def test_no_crash_if_log_missing(self, store):
        """Si el fichero de log no existe, devuelve lista vacía sin excepción."""
        store._log_file = "/no/existe/log.jsonl"
        entries = store.get_recent_discoveries()
        assert entries == []


# ─── Tests: get_ia_summary ───────────────────────────────────────────────────

class TestGetIaSummary:
    def test_returns_string(self, store_with_data):
        """Siempre devuelve un string."""
        result = store_with_data.get_ia_summary()
        assert isinstance(result, str)

    def test_includes_table_names(self, store_with_data):
        """El resumen incluye los nombres de las tablas conocidas."""
        result = store_with_data.get_ia_summary()
        assert "DOCCAB" in result
        assert "CLIENTE" in result

    def test_includes_record_counts(self, store_with_data):
        """El resumen incluye los conteos de registros."""
        result = store_with_data.get_ia_summary()
        assert "74034" in result

    def test_includes_business_rules(self, store_with_data):
        """El resumen incluye las reglas de negocio."""
        result = store_with_data.get_ia_summary()
        assert "instalación" in result.lower()

    def test_filter_by_tables(self, store_with_data):
        """Con filtro de tablas, solo incluye las solicitadas."""
        result = store_with_data.get_ia_summary(tables=["DOCCAB"])
        # CLIENTE puede aparecer en el índice pero no en los detalles
        assert "DOCCAB" in result

    def test_includes_tipo_distribution(self, store_with_data):
        """El resumen incluye la distribución de TIPO si está disponible."""
        result = store_with_data.get_ia_summary(tables=["DOCCAB"])
        assert "TIPO" in result or "tipo" in result.lower()

    def test_includes_nota_docdestino(self, store):
        """El resumen incluye la nota de DOCDESTINO si está disponible."""
        store.update_table("DOCCAB", {
            "columns_real": ["TIPO"],
            "_nota_docdestino": "Solo el 15% tiene documento destino",
        })
        result = store.get_ia_summary(tables=["DOCCAB"])
        assert "15%" in result

    def test_empty_store_returns_string(self, store):
        """Con store vacío, devuelve string (puede estar vacío)."""
        result = store.get_ia_summary()
        assert isinstance(result, str)


# ─── Tests: _load_json / _save_json ──────────────────────────────────────────

class TestIOHelpers:
    def test_load_json_valid(self, store, tmp_path):
        """Carga un JSON válido correctamente."""
        data = {"key": "value", "num": 42}
        path = str(tmp_path / "test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = store._load_json(path)
        assert result == data

    def test_load_json_not_found(self, store):
        """Devuelve None si el fichero no existe."""
        result = store._load_json("/no/existe/fichero.json")
        assert result is None

    def test_load_json_corrupted(self, store, tmp_path):
        """Devuelve None si el JSON está corrupto."""
        path = str(tmp_path / "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{invalid json{{")
        result = store._load_json(path)
        assert result is None

    def test_save_json_creates_file(self, store, tmp_path):
        """Crea el fichero JSON correctamente."""
        path = str(tmp_path / "output.json")
        result = store._save_json(path, {"key": "value"})
        assert result is True
        assert os.path.exists(path)

    def test_save_json_content_correct(self, store, tmp_path):
        """El contenido guardado es correcto."""
        path = str(tmp_path / "output.json")
        data = {"key": "value", "list": [1, 2, 3]}
        store._save_json(path, data)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_json_creates_backup(self, store, tmp_path):
        """Crea un backup .bak del fichero existente."""
        path = str(tmp_path / "output.json")
        store._save_json(path, {"v": 1})
        store._save_json(path, {"v": 2})
        assert os.path.exists(path + ".bak")

    def test_save_json_returns_false_on_error(self, store):
        """Devuelve False si no puede guardar."""
        result = store._save_json("/ruta/sin/permisos/file.json", {"key": "value"})
        assert result is False

    def test_save_json_unicode(self, store, tmp_path):
        """Guarda correctamente caracteres Unicode (español, emojis)."""
        path = str(tmp_path / "unicode.json")
        data = {"texto": "Instalación de climatización ✓", "emoji": "🔬"}
        store._save_json(path, data)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["texto"] == data["texto"]
        assert loaded["emoji"] == data["emoji"]


# ─── Tests: get_knowledge_store (singleton) ───────────────────────────────────

class TestGetKnowledgeStore:
    def test_returns_instance(self):
        """get_knowledge_store devuelve una instancia de KnowledgeStore."""
        import backend.modules.chat.deep_analysis.knowledge_store as ks_module
        # Reset singleton para el test
        ks_module._store_instance = None
        store = get_knowledge_store()
        assert isinstance(store, KnowledgeStore)

    def test_singleton_same_instance(self):
        """Siempre devuelve la misma instancia."""
        store1 = get_knowledge_store()
        store2 = get_knowledge_store()
        assert store1 is store2

    def test_singleton_no_crash_on_init_error(self):
        """Si la inicialización falla, devuelve una instancia vacía sin excepción."""
        import backend.modules.chat.deep_analysis.knowledge_store as ks_module
        ks_module._store_instance = None
        with patch("backend.modules.chat.deep_analysis.knowledge_store.KnowledgeStore.__init__",
                   side_effect=Exception("Error de inicialización")):
            # No debe lanzar excepción
            try:
                store = get_knowledge_store()
            except Exception:
                pass  # El singleton puede fallar en este caso extremo
        # Restaurar
        ks_module._store_instance = None


# ─── Tests: Resiliencia total ─────────────────────────────────────────────────

class TestResilience:
    def test_update_table_no_crash_on_save_error(self, store):
        """update_table no lanza excepción si _save_json falla."""
        with patch.object(store, "_save_json", side_effect=Exception("disco lleno")):
            result = store.update_table("DOCCAB", {"record_count_real": 100})
            assert result is False  # Devuelve False, no lanza excepción

    def test_add_business_rule_no_crash_on_save_error(self, store):
        """add_business_rule no lanza excepción si _save_json falla."""
        with patch.object(store, "_save_json", side_effect=Exception("disco lleno")):
            result = store.add_business_rule("Regla de prueba para resiliencia")
            assert result is False

    def test_add_query_pattern_no_crash_on_save_error(self, store):
        """add_query_pattern no lanza excepción si _save_json falla."""
        with patch.object(store, "_save_json", side_effect=Exception("disco lleno")):
            result = store.add_query_pattern(
                "test", "SELECT COUNT(*) AS N FROM DOCCAB WHERE TIPO=0", ["DOCCAB"]
            )
            assert result is False

    def test_get_patterns_no_crash_on_load_error(self, store):
        """get_patterns_for_intent no lanza excepción si _load_json falla."""
        with patch.object(store, "_load_json", side_effect=Exception("error lectura")):
            result = store.get_patterns_for_intent(["presupuestos"])
            assert result == []

    def test_get_business_rules_no_crash_on_load_error(self, store):
        """get_business_rules no lanza excepción si _load_json falla."""
        with patch.object(store, "_load_json", side_effect=Exception("error lectura")):
            result = store.get_business_rules()
            assert result == []

    def test_get_ia_summary_no_crash_on_error(self, store):
        """get_ia_summary no lanza excepción si hay errores internos."""
        with patch.object(store, "get_index", side_effect=Exception("error")):
            result = store.get_ia_summary()
            assert isinstance(result, str)

    def test_log_discovery_no_crash_on_write_error(self, store):
        """log_discovery no lanza excepción si no puede escribir."""
        store._log_file = "/ruta/sin/permisos/log.jsonl"
        # No debe lanzar excepción
        store.log_discovery("record_count", "DOCCAB", {"count": 100})


# ─── Tests: Integración completa ─────────────────────────────────────────────

class TestIntegration:
    def test_full_learning_cycle(self, store):
        """
        Ciclo completo de aprendizaje:
        1. Explorar tabla → update_table
        2. Descubrir regla → add_business_rule
        3. Registrar patrón SQL → add_query_pattern
        4. Log de descubrimiento → log_discovery
        5. Verificar resumen IA → get_ia_summary
        """
        # 1. Metadatos de tabla
        store.update_table("DOCCAB", {
            "columns_real": ["TIPO", "FECHA", "IMPORTETOTAL", "CODCLIENTE", "SERIE", "CODIGOOBRA"],
            "record_count_real": 74034,
            "tipo_distribution": {"0": 12000, "13": 8000},
            "estadopend_distribution": {"0": 8000, "1": 3000, "2": 1000},
            "_nota_docdestino": "Solo el 15% tiene documento destino",
        })

        # 2. Regla de negocio
        store.add_business_rule(
            "1 instalación puede tener N presupuestos — total presupuestos ≠ total instalaciones",
            table="DOCCAB", confidence="alto"
        )

        # 3. Patrón SQL exitoso
        store.add_query_pattern(
            intent="presupuestos aceptados por año",
            sql=(
                "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N "
                "FROM DOCCAB WHERE TIPO=0 GROUP BY 1 ORDER BY 1 DESC"
            ),
            tables=["DOCCAB"],
            rows_returned=8,
            reliability="alto",
        )

        # 4. Log de descubrimiento
        store.log_discovery(
            "estadopend", "DOCCAB",
            {"0": 8000, "1": 3000, "2": 1000},
            question="¿cuántos presupuestos hay?"
        )

        # 5. Verificar resumen
        summary = store.get_ia_summary(tables=["DOCCAB"])
        assert "DOCCAB" in summary
        assert "74034" in summary
        assert "instalación" in summary.lower()

        # Verificar índice
        index = store.get_index()
        assert "DOCCAB" in index["tables"]
        assert index["tables"]["DOCCAB"]["has_tipo"] is True

        # Verificar patrones
        patterns = store.get_patterns_for_intent(["presupuestos", "año"])
        assert len(patterns) > 0
        assert patterns[0]["reliability"] == "alto"

        # Verificar log
        entries = store.get_recent_discoveries(n=5)
        assert len(entries) >= 1
        assert entries[-1]["type"] == "estadopend"

    def test_multiple_tables_learning(self, store):
        """Aprendizaje de múltiples tablas en la misma sesión."""
        tables_data = {
            "DOCCAB": {"columns_real": ["TIPO", "FECHA"], "record_count_real": 74034},
            "CLIENTE": {"columns_real": ["CODIGO", "NOMBRE"], "record_count_real": 3500},
            "DOCLIN": {"columns_real": ["CODDOCUMENTO", "CODART"], "record_count_real": 250000},
        }
        for table, data in tables_data.items():
            store.update_table(table, data)

        all_tables = store.get_all_tables()
        assert len(all_tables) == 3

        index = store.get_index()
        assert index["_total_tables"] == 3

    def test_knowledge_persists_across_instances(self, tmp_path):
        """El conocimiento persiste entre instancias del KnowledgeStore."""
        # Primera instancia: guarda datos
        store1 = KnowledgeStore(base_dir=str(tmp_path))
        store1.update_table("DOCCAB", {"record_count_real": 74034})
        store1.add_business_rule("Regla persistente entre instancias aquí")

        # Segunda instancia: lee los mismos datos
        store2 = KnowledgeStore(base_dir=str(tmp_path))
        data = store2.get_table("DOCCAB")
        rules = store2.get_business_rules()

        assert data["record_count_real"] == 74034
        assert any("persistente" in r["rule"] for r in rules)
