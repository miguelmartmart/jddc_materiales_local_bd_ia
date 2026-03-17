"""
knowledge_store.py — Almacén de conocimiento persistente del DeepAnalysisAgent.

Gestiona el aprendizaje permanente del agente: índices, carpetas organizadas,
resúmenes IA-friendly, JSON optimizados y registros de descubrimientos.

Estructura de carpetas generada (bajo core/config/knowledge/):
  knowledge/
    tables/
      DOCCAB.json          ← metadatos ricos por tabla
      CLIENTE.json
      ...
    index.json             ← índice global de tablas conocidas
    business_rules.json    ← reglas de negocio descubiertas
    query_patterns.json    ← patrones SQL exitosos por intención
    discoveries_log.jsonl  ← log append-only de descubrimientos

Principios:
  - Fichero < 500 líneas
  - Parámetros centralizados en KNOWLEDGE_STORE_CONSTANTS
  - Ultra-resiliente: cada operación con try/except independiente
  - LAN_ONLY: nunca envía datos a internet
  - Modular: importable desde cualquier módulo del proyecto
  - IA-friendly: JSON compactos con claves semánticas
"""

import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES CENTRALIZADAS
# ─────────────────────────────────────────────────────────────────────────────

# Directorio raíz del almacén de conocimiento
_BASE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "core", "config", "knowledge"
))

KNOWLEDGE_STORE_CONSTANTS = {
    # Directorios
    "base_dir":          _BASE_DIR,
    "tables_dir":        os.path.join(_BASE_DIR, "tables"),
    # Ficheros de índice y reglas
    "index_file":        os.path.join(_BASE_DIR, "index.json"),
    "business_rules":    os.path.join(_BASE_DIR, "business_rules.json"),
    "query_patterns":    os.path.join(_BASE_DIR, "query_patterns.json"),
    "discoveries_log":   os.path.join(_BASE_DIR, "discoveries_log.jsonl"),
    # Límites
    "max_log_entries":   5000,    # máximo de entradas en discoveries_log.jsonl
    "max_patterns":      200,     # máximo de patrones SQL guardados
    "max_rules":         500,     # máximo de reglas de negocio
    "backup_suffix":     ".bak",
}

# Tipos de descubrimiento reconocidos
DISCOVERY_TYPES = {
    "columns_real":       "Columnas reales desde RDB$RELATION_FIELDS",
    "record_count":       "Conteo real de registros",
    "tipo_distribution":  "Distribución de TIPO en DOCCAB",
    "estadopend":         "Distribución de ESTADOPEND",
    "docdestino":         "Relación presupuestos→documentos destino",
    "columns_estado":     "Columnas de estado/aceptación",
    "business_rule":      "Regla de negocio descubierta",
    "sql_pattern":        "Patrón SQL exitoso",
    "anomaly":            "Anomalía detectada",
    "data_quality":       "Problema de calidad de datos",
}


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeStore:
    """
    Almacén de conocimiento persistente del DeepAnalysisAgent.

    Uso:
        store = KnowledgeStore()
        store.update_table("DOCCAB", {"columns_real": [...], "record_count_real": 74034})
        store.add_business_rule("1 instalación puede tener N presupuestos")
        store.add_query_pattern("presupuestos aceptados", sql, tables=["DOCCAB","DOCDESTINO"])
        store.log_discovery("columns_real", "DOCCAB", {"cols": [...]})
    """

    def __init__(self, base_dir: Optional[str] = None):
        self._base = base_dir or KNOWLEDGE_STORE_CONSTANTS["base_dir"]
        self._tables_dir = os.path.join(self._base, "tables")
        self._index_file = os.path.join(self._base, "index.json")
        self._rules_file = os.path.join(self._base, "business_rules.json")
        self._patterns_file = os.path.join(self._base, "query_patterns.json")
        self._log_file = os.path.join(self._base, "discoveries_log.jsonl")
        self._ensure_dirs()

    # ─── Inicialización ───────────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        """Crea la estructura de carpetas si no existe."""
        try:
            os.makedirs(self._tables_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"[KNOWLEDGE] No se pudo crear directorio: {e}")

    # ─── Tablas ───────────────────────────────────────────────────────────────

    def get_table(self, table: str) -> Dict:
        """Carga los metadatos de una tabla. Devuelve {} si no existe."""
        path = os.path.join(self._tables_dir, f"{table.upper()}.json")
        return self._load_json(path) or {}

    def update_table(self, table: str, updates: Dict) -> bool:
        """
        Actualiza los metadatos de una tabla con los nuevos descubrimientos.
        Solo actualiza campos que han cambiado (merge inteligente).
        Devuelve True si hubo cambios reales.
        """
        if not table or not updates:
            return False
        try:
            path = os.path.join(self._tables_dir, f"{table.upper()}.json")
            current = self._load_json(path) or {}
            changed = False

            for key, value in updates.items():
                if key.startswith("_"):
                    # Notas críticas: siempre actualizar
                    if current.get(key) != value:
                        current[key] = value
                        changed = True
                elif key == "columns_real":
                    # Columnas: actualizar si el conjunto cambió
                    if set(value) != set(current.get("columns_real", [])):
                        current["columns_real"] = sorted(value)
                        current["columns_count"] = len(value)
                        changed = True
                elif key == "record_count_real":
                    # Conteo: actualizar si cambió
                    if current.get("record_count_real") != value:
                        current["record_count_real"] = value
                        current["record_count_source"] = "firebird_count"
                        changed = True
                else:
                    if current.get(key) != value:
                        current[key] = value
                        changed = True

            if changed:
                current["_table"] = table.upper()
                current["_updated_at"] = datetime.now().isoformat()
                self._save_json(path, current)
                self._update_index(table.upper(), current)
                logger.info(f"[KNOWLEDGE] Tabla {table} actualizada")

            return changed
        except Exception as e:
            logger.error(f"[KNOWLEDGE] update_table({table}): {e}")
            return False

    def get_all_tables(self) -> Dict[str, Dict]:
        """Devuelve todos los metadatos de tablas conocidas."""
        result = {}
        try:
            for fname in os.listdir(self._tables_dir):
                if fname.endswith(".json"):
                    table = fname[:-5]
                    data = self._load_json(os.path.join(self._tables_dir, fname))
                    if data:
                        result[table] = data
        except Exception as e:
            logger.warning(f"[KNOWLEDGE] get_all_tables: {e}")
        return result

    # ─── Índice global ────────────────────────────────────────────────────────

    def _update_index(self, table: str, table_data: Dict) -> None:
        """Actualiza el índice global con un resumen de la tabla."""
        try:
            index = self._load_json(self._index_file) or {"tables": {}, "_updated_at": ""}
            index["tables"][table] = {
                "record_count": table_data.get("record_count_real", "?"),
                "columns_count": table_data.get("columns_count", len(table_data.get("columns_real", []))),
                "has_tipo": "TIPO" in table_data.get("columns_real", []),
                "has_fecha": "FECHA" in table_data.get("columns_real", []),
                "has_importe": any(
                    c in table_data.get("columns_real", [])
                    for c in ["IMPORTETOTAL", "IMPORTE", "TOTAL"]
                ),
                "updated_at": table_data.get("_updated_at", ""),
            }
            index["_updated_at"] = datetime.now().isoformat()
            index["_total_tables"] = len(index["tables"])
            self._save_json(self._index_file, index)
        except Exception as e:
            logger.debug(f"[KNOWLEDGE] _update_index: {e}")

    def get_index(self) -> Dict:
        """Devuelve el índice global de tablas conocidas."""
        return self._load_json(self._index_file) or {"tables": {}}

    # ─── Reglas de negocio ────────────────────────────────────────────────────

    def add_business_rule(
        self, rule: str, table: Optional[str] = None,
        confidence: str = "medio", source: str = "deep_analysis"
    ) -> bool:
        """
        Añade una regla de negocio descubierta.
        No añade duplicados (compara por texto normalizado).
        """
        if not rule or len(rule) < 10:
            return False
        try:
            data = self._load_json(self._rules_file) or {"rules": [], "_count": 0}
            rules = data.get("rules", [])

            # Evitar duplicados
            rule_norm = rule.strip().lower()
            for existing in rules:
                if existing.get("rule", "").strip().lower() == rule_norm:
                    return False

            rules.append({
                "rule": rule.strip(),
                "table": table,
                "confidence": confidence,
                "source": source,
                "discovered_at": datetime.now().isoformat(),
            })

            # Limitar tamaño
            max_rules = KNOWLEDGE_STORE_CONSTANTS["max_rules"]
            if len(rules) > max_rules:
                rules = rules[-max_rules:]

            data["rules"] = rules
            data["_count"] = len(rules)
            data["_updated_at"] = datetime.now().isoformat()
            self._save_json(self._rules_file, data)
            logger.info(f"[KNOWLEDGE] Regla añadida: {rule[:60]}")
            return True
        except Exception as e:
            logger.error(f"[KNOWLEDGE] add_business_rule: {e}")
            return False

    def get_business_rules(self, table: Optional[str] = None) -> List[Dict]:
        """Devuelve reglas de negocio, opcionalmente filtradas por tabla."""
        try:
            data = self._load_json(self._rules_file) or {"rules": []}
            rules = data.get("rules", [])
            if table:
                rules = [r for r in rules if r.get("table") == table or r.get("table") is None]
            return rules
        except Exception:
            return []

    # ─── Patrones SQL ─────────────────────────────────────────────────────────

    def add_query_pattern(
        self, intent: str, sql: str, tables: List[str],
        rows_returned: int = 0, reliability: str = "medio"
    ) -> bool:
        """
        Registra un patrón SQL exitoso para una intención dada.
        Útil para que el agente aprenda qué SQLs funcionan bien.
        """
        if not intent or not sql or len(sql) < 20:
            return False
        try:
            data = self._load_json(self._patterns_file) or {"patterns": [], "_count": 0}
            patterns = data.get("patterns", [])

            # Evitar duplicados exactos de SQL
            sql_norm = sql.strip()
            for p in patterns:
                if p.get("sql", "").strip() == sql_norm:
                    # Actualizar conteo de usos
                    p["uses"] = p.get("uses", 1) + 1
                    p["last_used"] = datetime.now().isoformat()
                    data["patterns"] = patterns
                    self._save_json(self._patterns_file, data)
                    return True

            patterns.append({
                "intent": intent[:100],
                "sql": sql_norm[:500],
                "tables": tables,
                "rows_returned": rows_returned,
                "reliability": reliability,
                "uses": 1,
                "discovered_at": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat(),
            })

            # Limitar tamaño — conservar los más usados
            max_p = KNOWLEDGE_STORE_CONSTANTS["max_patterns"]
            if len(patterns) > max_p:
                patterns = sorted(patterns, key=lambda x: x.get("uses", 0), reverse=True)[:max_p]

            data["patterns"] = patterns
            data["_count"] = len(patterns)
            data["_updated_at"] = datetime.now().isoformat()
            self._save_json(self._patterns_file, data)
            return True
        except Exception as e:
            logger.error(f"[KNOWLEDGE] add_query_pattern: {e}")
            return False

    def get_patterns_for_intent(self, intent_keywords: List[str]) -> List[Dict]:
        """Devuelve patrones SQL relevantes para una intención (por palabras clave)."""
        try:
            data = self._load_json(self._patterns_file) or {"patterns": []}
            patterns = data.get("patterns", [])
            keywords_lower = [k.lower() for k in intent_keywords]
            scored = []
            for p in patterns:
                intent_lower = p.get("intent", "").lower()
                score = sum(1 for k in keywords_lower if k in intent_lower)
                if score > 0:
                    scored.append((score, p))
            scored.sort(key=lambda x: (-x[0], -x[1].get("uses", 0)))
            return [p for _, p in scored[:10]]
        except Exception:
            return []

    # ─── Log de descubrimientos ───────────────────────────────────────────────

    def log_discovery(
        self, discovery_type: str, table: Optional[str],
        data: Any, question: Optional[str] = None
    ) -> None:
        """
        Añade una entrada al log append-only de descubrimientos.
        Formato JSONL (una línea JSON por entrada) — fácil de procesar con IA.
        """
        try:
            entry = {
                "ts": datetime.now().isoformat(),
                "type": discovery_type,
                "type_desc": DISCOVERY_TYPES.get(discovery_type, discovery_type),
                "table": table,
                "question": question[:80] if question else None,
                "data": data,
            }
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            # Rotar log si supera el límite
            self._rotate_log_if_needed()
        except Exception as e:
            logger.debug(f"[KNOWLEDGE] log_discovery: {e}")

    def _rotate_log_if_needed(self) -> None:
        """Rota el log si supera max_log_entries."""
        try:
            max_entries = KNOWLEDGE_STORE_CONSTANTS["max_log_entries"]
            if not os.path.exists(self._log_file):
                return
            with open(self._log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > max_entries:
                # Conservar las últimas max_entries líneas
                keep = lines[-max_entries:]
                with open(self._log_file, "w", encoding="utf-8") as f:
                    f.writelines(keep)
                logger.info(f"[KNOWLEDGE] Log rotado: {len(lines)} → {len(keep)} entradas")
        except Exception:
            pass

    def get_recent_discoveries(self, n: int = 20) -> List[Dict]:
        """Devuelve las últimas N entradas del log de descubrimientos."""
        try:
            if not os.path.exists(self._log_file):
                return []
            with open(self._log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            entries = []
            for line in reversed(lines[-n * 2:]):
                try:
                    entries.append(json.loads(line.strip()))
                    if len(entries) >= n:
                        break
                except Exception:
                    pass
            return list(reversed(entries))
        except Exception:
            return []

    # ─── Resumen IA-friendly ──────────────────────────────────────────────────

    def get_ia_summary(self, tables: Optional[List[str]] = None) -> str:
        """
        Genera un resumen compacto IA-friendly del conocimiento acumulado.
        Útil para incluir en prompts del agente.
        """
        try:
            lines = ["# CONOCIMIENTO ACUMULADO (KnowledgeStore)\n"]

            # Índice de tablas
            index = self.get_index()
            known_tables = index.get("tables", {})
            if known_tables:
                lines.append(f"## Tablas conocidas ({len(known_tables)})")
                for tname, tinfo in known_tables.items():
                    if tables and tname not in tables:
                        continue
                    rc = tinfo.get("record_count", "?")
                    cc = tinfo.get("columns_count", "?")
                    lines.append(f"• {tname}: {rc} registros, {cc} columnas")

            # Reglas de negocio relevantes
            rules = self.get_business_rules()
            if rules:
                lines.append(f"\n## Reglas de negocio ({len(rules)})")
                for r in rules[:10]:
                    conf = r.get("confidence", "?")
                    lines.append(f"• [{conf}] {r.get('rule', '')}")

            # Metadatos específicos de tablas solicitadas
            if tables:
                for tname in tables:
                    tdata = self.get_table(tname)
                    if not tdata:
                        continue
                    lines.append(f"\n## {tname}")
                    if tdata.get("columns_real"):
                        lines.append(f"Columnas: {', '.join(tdata['columns_real'][:15])}")
                    if tdata.get("tipo_distribution"):
                        lines.append(f"TIPO dist: {tdata['tipo_distribution']}")
                    if tdata.get("estadopend_distribution"):
                        lines.append(f"ESTADOPEND: {tdata['estadopend_distribution']}")
                    if tdata.get("_nota_docdestino"):
                        lines.append(f"⚠️ {tdata['_nota_docdestino']}")
                    if tdata.get("_nota_estadopend"):
                        lines.append(f"ℹ️ {tdata['_nota_estadopend']}")

            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[KNOWLEDGE] get_ia_summary: {e}")
            return ""

    # ─── Helpers I/O ──────────────────────────────────────────────────────────

    def _load_json(self, path: str) -> Optional[Dict]:
        """Carga un JSON de forma segura. Devuelve None si falla."""
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"[KNOWLEDGE] _load_json({path}): {e}")
        return None

    def _save_json(self, path: str, data: Any) -> bool:
        """Guarda un JSON de forma segura con backup previo."""
        try:
            # Backup
            if os.path.exists(path):
                shutil.copy2(path, path + KNOWLEDGE_STORE_CONSTANTS["backup_suffix"])
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"[KNOWLEDGE] _save_json({path}): {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON (patrón de acceso global)
# ─────────────────────────────────────────────────────────────────────────────

_store_instance: Optional[KnowledgeStore] = None


def get_knowledge_store() -> KnowledgeStore:
    """
    Devuelve la instancia singleton del KnowledgeStore.
    Ultra-resiliente: si falla la inicialización, devuelve una instancia vacía.
    """
    global _store_instance
    if _store_instance is None:
        try:
            _store_instance = KnowledgeStore()
            logger.info(f"[KNOWLEDGE] KnowledgeStore inicializado en: {_store_instance._base}")
        except Exception as e:
            logger.error(f"[KNOWLEDGE] Error inicializando KnowledgeStore: {e}")
            _store_instance = KnowledgeStore.__new__(KnowledgeStore)
            _store_instance._base = ""
            _store_instance._tables_dir = ""
            _store_instance._index_file = ""
            _store_instance._rules_file = ""
            _store_instance._patterns_file = ""
            _store_instance._log_file = ""
    return _store_instance
