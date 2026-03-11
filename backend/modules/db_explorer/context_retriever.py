"""
ContextRetriever — Recuperacion de contexto optimo para el ChatService.

RESPONSABILIDAD:
  Dado una pregunta en lenguaje natural, devuelve el contexto minimo y preciso
  que la IA necesita para generar SQL correcto. Usa los indices del SIUO para
  encontrar las tablas relevantes en <1ms sin consultar Firebird.

PRINCIPIOS:
  - Cargado en memoria al arrancar (singleton)
  - Busqueda en O(1) via concept_index
  - Expansion via BFS en db_graph (profundidad configurable)
  - Control estricto de tokens (nunca excede max_tokens)
  - Fallback gracioso: si los indices no existen, usa db_metadata_optimized.json

AUTOAPRENDIZAJE:
  - Registra que tablas se usaron para cada pregunta (query_log.json)
  - Detecta patrones de preguntas frecuentes
  - Sugiere nuevas entradas para concept_index cuando detecta keywords no mapeados
  - Permite feedback del usuario (SQL correcto/incorrecto) para mejorar el indice

FLUJO:
  [1] Normalizar pregunta (lowercase, quitar stopwords)
  [2] Extraer keywords
  [3] Buscar en concept_index -> tablas candidatas
  [4] Expandir con db_graph (BFS profundidad 2)
  [5] Cargar detalles de table_index
  [6] Anadir value_index relevante (enumerados, rangos)
  [7] Calcular tokens y recortar si necesario
  [8] Devolver contexto optimo + metadatos de trazabilidad

DEPENDENCIAS:
  - deep_indexer_service.py: rutas de los ficheros de indices
  - db_metadata_optimized.json: fallback si los indices no existen
"""

import json
import logging
import re
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.modules.db_explorer.deep_indexer_service import (
    TABLE_INDEX_PATH,
    CONCEPT_INDEX_PATH,
    DB_GRAPH_PATH,
    VALUE_INDEX_PATH,
    _load_json,
    _save_json,
)

logger = logging.getLogger(__name__)

# ─── Rutas adicionales ────────────────────────────────────────────────────────

_CONFIG_DIR    = TABLE_INDEX_PATH.parent
QUERY_LOG_PATH = _CONFIG_DIR / "siuo_query_log.json"

# ─── Constantes de configuracion ─────────────────────────────────────────────

MAX_TOKENS_DEFAULT    = 2000   # Tokens maximos del contexto enviado a la IA
MAX_TABLES_IN_CONTEXT = 8      # Maximo de tablas en el contexto
BFS_MAX_DEPTH         = 2      # Profundidad maxima de expansion en el grafo
TOKENS_PER_CHAR       = 0.25   # Estimacion: 1 token ~ 4 chars
MAX_LOG_ENTRIES       = 500    # Maximo de entradas en el query_log

# Stopwords en espanol (no se usan como keywords)
STOPWORDS_ES = frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "en", "con", "por", "para", "que",
    "se", "me", "te", "le", "nos", "os", "les", "lo",
    "es", "son", "hay", "tiene", "tienen", "hay", "dame",
    "dime", "muestra", "lista", "ver", "quiero", "necesito",
    "cuantos", "cuantas", "cual", "cuales", "como", "donde",
    "cuando", "quien", "quienes", "mas", "menos", "todos",
    "todas", "cada", "otro", "otra", "mismo", "misma",
})


# ─── ContextRetriever ─────────────────────────────────────────────────────────

class ContextRetriever:
    """
    Recupera el contexto optimo para una pregunta usando los indices del SIUO.

    Uso:
        retriever = get_context_retriever()
        context, meta = retriever.get_context("articulos con mas compras")
        # context: string listo para el system prompt
        # meta: dict con tablas usadas, tokens, keywords, etc.
    """

    def __init__(self):
        self._table_index:   Dict = {}
        self._concept_index: Dict = {}
        self._graph_adj:     Dict[str, Set[str]] = defaultdict(set)
        self._graph_paths:   Dict[str, List[str]] = {}
        self._value_index:   Dict = {}
        self._loaded:        bool = False
        self._fallback_schema: str = ""

    # ─────────────────────────────────────────────────────────────────────────
    # CARGA DE INDICES
    # ─────────────────────────────────────────────────────────────────────────

    def load(self) -> bool:
        """
        Carga todos los indices en memoria.
        Devuelve True si los indices del SIUO estan disponibles,
        False si solo hay fallback (db_metadata_optimized.json).
        """
        try:
            table_data   = _load_json(TABLE_INDEX_PATH,   {})
            concept_data = _load_json(CONCEPT_INDEX_PATH, {})
            graph_data   = _load_json(DB_GRAPH_PATH,      {})
            value_data   = _load_json(VALUE_INDEX_PATH,   {})

            self._table_index   = table_data.get("tables", {})
            self._concept_index = concept_data.get("index", {})
            self._value_index   = value_data

            # Construir lista de adyacencia del grafo
            self._graph_adj   = defaultdict(set)
            self._graph_paths = graph_data.get("paths", {})
            for edge in graph_data.get("edges", []):
                self._graph_adj[edge["from"]].add(edge["to"])
                self._graph_adj[edge["to"]].add(edge["from"])

            self._loaded = bool(self._table_index)
            n_tables   = len(self._table_index)
            n_concepts = len(self._concept_index)
            n_edges    = sum(len(v) for v in self._graph_adj.values()) // 2

            logger.info(
                f"[ContextRetriever] Indices cargados: "
                f"{n_tables} tablas, {n_concepts} conceptos, {n_edges} relaciones"
            )
            return self._loaded

        except Exception as exc:
            logger.warning(f"[ContextRetriever] Error cargando indices: {exc}")
            self._loaded = False
            return False

    def reload(self) -> bool:
        """Recarga los indices desde disco (tras una nueva indexacion)."""
        self._table_index   = {}
        self._concept_index = {}
        self._graph_adj     = defaultdict(set)
        self._graph_paths   = {}
        self._value_index   = {}
        self._loaded        = False
        return self.load()

    # ─────────────────────────────────────────────────────────────────────────
    # API PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def get_context(
        self,
        question: str,
        max_tokens: int = MAX_TOKENS_DEFAULT,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Devuelve el contexto optimo para una pregunta.

        Returns:
            (context_str, meta)
            - context_str: string listo para insertar en el system prompt
            - meta: {
                "tables_used": [...],
                "keywords_found": [...],
                "keywords_unknown": [...],
                "tokens_estimated": N,
                "source": "siuo"|"fallback",
              }
        """
        if not self._loaded:
            self.load()

        # Si no hay indices SIUO, usar fallback
        if not self._table_index:
            return self._get_fallback_context(), {
                "tables_used":       [],
                "keywords_found":    [],
                "keywords_unknown":  [],
                "tokens_estimated":  0,
                "source":            "fallback",
            }

        # 1. Extraer keywords
        keywords, unknown_kws = self._extract_keywords(question)

        # 2. Buscar tablas candidatas en concept_index
        candidate_tables = self._find_candidate_tables(keywords)

        # 3. Expandir con grafo (BFS)
        expanded_tables = self._expand_with_graph(candidate_tables, depth=BFS_MAX_DEPTH)

        # 4. Ordenar por relevancia
        ordered_tables = self._rank_tables(expanded_tables, candidate_tables)

        # 5. Construir contexto con control de tokens
        context_str, tables_used = self._build_context(
            ordered_tables, keywords, max_tokens
        )

        # 6. Registrar para autoaprendizaje
        self._log_query(question, keywords, tables_used, unknown_kws)

        meta = {
            "tables_used":      tables_used,
            "keywords_found":   keywords,
            "keywords_unknown": unknown_kws,
            "tokens_estimated": self._estimate_tokens(context_str),
            "source":           "siuo",
        }

        logger.info(
            f"[ContextRetriever] '{question[:50]}' -> "
            f"{len(tables_used)} tablas, ~{meta['tokens_estimated']} tokens"
        )

        return context_str, meta

    # ─────────────────────────────────────────────────────────────────────────
    # EXTRACCION DE KEYWORDS
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_word(self, word: str) -> str:
        """
        Normaliza una palabra para busqueda en concept_index.

        Estrategia (en orden de prioridad):
        1. Palabra tal cual (con acento normalizado) -> buscar en concept_index
        2. Plural -> singular (-s, -es): si la raiz esta en el indice
        3. Singular -> plural (+s, +es): si el plural esta en el indice
           (cubre el caso donde Qwen3 genero keywords en plural: 'facturas', 'articulos')
        4. Devolver la forma sin acento (para busqueda exacta posterior)

        Ejemplos:
          'artículos' -> 'articulo'  (tilde + plural, raiz en indice)
          'compras'   -> 'compra'    (plural, raiz en indice)
          'facturas'  -> 'facturas'  (plural en indice generado por Qwen3)
          'factura'   -> 'factura'   (singular en BASE_CONCEPT_INDEX)
        """
        import unicodedata

        # Eliminar acentos
        nfkd = unicodedata.normalize("NFKD", word)
        word_no_accent = "".join(c for c in nfkd if not unicodedata.combining(c))

        # 1. Palabra tal cual (sin acento)
        if word_no_accent in self._concept_index:
            return word_no_accent

        # 2. Plural -> singular: quitar sufijo si la raiz esta en el indice
        if word_no_accent.endswith("es") and len(word_no_accent) > 4:
            stem = word_no_accent[:-2]
            if stem in self._concept_index:
                return stem

        if word_no_accent.endswith("s") and len(word_no_accent) > 3:
            stem = word_no_accent[:-1]
            if stem in self._concept_index:
                return stem

        # 3. Singular -> plural: anadir sufijo si el plural esta en el indice
        #    (cubre keywords generados por Qwen3 en plural: 'facturas', 'articulos')
        for suffix in ("s", "es"):
            plural = word_no_accent + suffix
            if plural in self._concept_index:
                return plural

        # 4. Devolver la palabra sin acento
        return word_no_accent

    def _extract_keywords(self, question: str) -> Tuple[List[str], List[str]]:
        """
        Extrae keywords de la pregunta y los clasifica en:
        - keywords: los que tienen match en concept_index
        - unknown_kws: los que no tienen match (para autoaprendizaje)

        Incluye normalizacion de plurales y acentos para mayor cobertura.
        Ejemplo: "articulos" -> busca "articulo" en concept_index
        """
        # Normalizar
        text = question.lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        words = text.split()

        # Filtrar stopwords
        words = [w for w in words if w not in STOPWORDS_ES and len(w) > 2]

        # Buscar en concept_index (palabras simples y bigramas)
        found    = []
        unknown  = []
        checked  = set()

        # Bigramas primero (mas especificos)
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            norm_bigram = self._normalize_word(bigram)
            if bigram in self._concept_index or norm_bigram in self._concept_index:
                key = bigram if bigram in self._concept_index else norm_bigram
                found.append(key)
                checked.add(words[i])
                checked.add(words[i+1])

        # Palabras simples con normalizacion de plurales/acentos
        for w in words:
            if w in checked:
                continue
            normalized = self._normalize_word(w)
            if normalized in self._concept_index:
                found.append(normalized)
            elif w in self._concept_index:
                found.append(w)
            else:
                unknown.append(w)

        return found, unknown

    # ─────────────────────────────────────────────────────────────────────────
    # BUSQUEDA EN CONCEPT_INDEX
    # ─────────────────────────────────────────────────────────────────────────

    def _find_candidate_tables(self, keywords: List[str]) -> Dict[str, Dict]:
        """
        Busca tablas candidatas en concept_index para los keywords dados.
        Devuelve {table_name: {filter, score, source}}.
        """
        candidates: Dict[str, Dict] = {}

        for kw in keywords:
            entries = self._concept_index.get(kw, [])
            for entry in entries:
                if isinstance(entry, str):
                    table_name = entry
                    table_filter = None
                elif isinstance(entry, dict):
                    table_name   = entry.get("table", "")
                    table_filter = entry.get("filter")
                else:
                    continue

                if not table_name:
                    continue

                if table_name not in candidates:
                    candidates[table_name] = {
                        "filter": table_filter,
                        "score":  1,
                        "source": "concept_index",
                        "kws":    [kw],
                    }
                else:
                    candidates[table_name]["score"] += 1
                    candidates[table_name]["kws"].append(kw)
                    # Actualizar filtro si hay uno mas especifico
                    if table_filter and not candidates[table_name]["filter"]:
                        candidates[table_name]["filter"] = table_filter

        return candidates

    # ─────────────────────────────────────────────────────────────────────────
    # EXPANSION CON GRAFO
    # ─────────────────────────────────────────────────────────────────────────

    def _expand_with_graph(
        self,
        candidates: Dict[str, Dict],
        depth: int = BFS_MAX_DEPTH,
    ) -> Dict[str, Dict]:
        """
        Expande las tablas candidatas con sus vecinas en el grafo (BFS).
        Las tablas expandidas tienen score menor que las candidatas directas.
        """
        expanded = dict(candidates)
        visited  = set(candidates.keys())
        queue    = deque([(table, 0) for table in candidates.keys()])

        while queue:
            table, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            for neighbor in self._graph_adj.get(table, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    # Score decreciente con la profundidad
                    score = max(0.1, 0.5 - current_depth * 0.2)
                    expanded[neighbor] = {
                        "filter": None,
                        "score":  score,
                        "source": f"graph_depth_{current_depth + 1}",
                        "kws":    [],
                    }
                    queue.append((neighbor, current_depth + 1))

        return expanded

    # ─────────────────────────────────────────────────────────────────────────
    # RANKING DE TABLAS
    # ─────────────────────────────────────────────────────────────────────────

    def _rank_tables(
        self,
        tables: Dict[str, Dict],
        direct_candidates: Dict[str, Dict],
    ) -> List[Tuple[str, Dict]]:
        """
        Ordena las tablas por relevancia:
        1. Tablas directas del concept_index (score alto)
        2. Tablas expandidas del grafo (score menor)
        3. Dentro de cada grupo, por numero de registros (mas datos = mas relevante)
        """
        def sort_key(item: Tuple[str, Dict]) -> Tuple[float, int]:
            table_name, info = item
            score      = info.get("score", 0)
            n_records  = self._table_index.get(table_name, {}).get("n", 0)
            return (-score, -n_records)

        return sorted(tables.items(), key=sort_key)[:MAX_TABLES_IN_CONTEXT]

    # ─────────────────────────────────────────────────────────────────────────
    # CONSTRUCCION DEL CONTEXTO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_context(
        self,
        ordered_tables: List[Tuple[str, Dict]],
        keywords: List[str],
        max_tokens: int,
    ) -> Tuple[str, List[str]]:
        """
        Construye el string de contexto con control estricto de tokens.
        Incluye: descripcion de tablas, columnas clave, relaciones, valores relevantes.
        """
        parts      = []
        tables_used = []
        tokens_used = 0

        header = (
            "=== ESQUEMA DE BASE DE DATOS RELEVANTE ===\n"
            "Base de datos: Firebird 2.5 (empresa de climatizacion)\n"
            "REGLAS SQL: usa FIRST N (no LIMIT), UPPER() para busquedas de texto\n\n"
        )
        tokens_used += self._estimate_tokens(header)
        parts.append(header)

        for table_name, info in ordered_tables:
            entry = self._table_index.get(table_name)
            if not entry:
                continue

            # Construir bloque de la tabla
            block = self._build_table_block(table_name, entry, info)

            # Anadir valores relevantes del value_index
            value_block = self._build_value_block(table_name, keywords)
            if value_block:
                block += value_block

            block_tokens = self._estimate_tokens(block)

            # Control de tokens: si no cabe, parar
            if tokens_used + block_tokens > max_tokens:
                # Intentar version compacta
                compact = self._build_table_block_compact(table_name, entry, info)
                compact_tokens = self._estimate_tokens(compact)
                if tokens_used + compact_tokens <= max_tokens:
                    parts.append(compact)
                    tables_used.append(table_name)
                    tokens_used += compact_tokens
                break

            parts.append(block)
            tables_used.append(table_name)
            tokens_used += block_tokens

        parts.append("=== FIN DEL ESQUEMA ===\n")
        return "".join(parts), tables_used

    def _build_table_block(
        self, table_name: str, entry: Dict, info: Dict
    ) -> str:
        """Construye el bloque de descripcion de una tabla (version completa)."""
        lines = [f"TABLA: {table_name}"]

        desc = entry.get("desc", "")
        if desc:
            lines.append(f"  Descripcion: {desc}")

        n = entry.get("n", 0)
        lines.append(f"  Registros: {n:,}")

        pks = entry.get("pk", [])
        if pks:
            lines.append(f"  Primary Keys: {', '.join(pks)}")

        # Filtro SQL si aplica (ej: TIPO=13 para facturas)
        sql_filter = info.get("filter")
        if sql_filter:
            lines.append(f"  FILTRO OBLIGATORIO: WHERE {sql_filter}")

        # Columnas principales (evitar la palabra "clave" que es columna sensible en SENSITIVE_COLUMNS)
        cols_key = entry.get("cols_key", [])
        if cols_key:
            lines.append(f"  Columnas principales: {', '.join(cols_key)}")

        # Tablas relacionadas
        related = entry.get("related", [])
        if related:
            lines.append(f"  Relacionada con: {', '.join(related[:5])}")

        # Nota critica
        note = entry.get("note")
        if note:
            lines.append(f"  NOTA: {note}")

        # Consulta de ejemplo
        queries = entry.get("queries", [])
        if queries:
            lines.append(f"  Ejemplo: {queries[0]}")

        return "\n".join(lines) + "\n\n"

    def _build_table_block_compact(
        self, table_name: str, entry: Dict, info: Dict
    ) -> str:
        """Version compacta del bloque de tabla (cuando hay poco espacio)."""
        desc     = entry.get("desc", "")[:80]
        cols_key = ", ".join(entry.get("cols_key", [])[:4])
        sql_filter = info.get("filter", "")
        filter_str = f" [WHERE {sql_filter}]" if sql_filter else ""
        return f"TABLA: {table_name}{filter_str} — {desc} | Cols: {cols_key}\n"

    def _build_value_block(self, table_name: str, keywords: List[str]) -> str:
        """
        Anade valores reales relevantes del value_index para la tabla.
        Solo incluye los valores que son relevantes para los keywords de la pregunta.
        """
        lines = []

        # Enumerados de la tabla
        for key, values in self._value_index.get("enums", {}).items():
            if key.startswith(f"{table_name}."):
                col_name = key.split(".", 1)[1]
                # Solo incluir si el keyword es relevante
                if any(kw in col_name.lower() or kw in key.lower() for kw in keywords):
                    vals_str = ", ".join(
                        f"{k}={v}" for k, v in list(values.items())[:8]
                    )
                    lines.append(f"  Valores {col_name}: {vals_str}")

        # Rangos de la tabla
        for key, rng in self._value_index.get("ranges", {}).items():
            if key.startswith(f"{table_name}."):
                col_name = key.split(".", 1)[1]
                if any(kw in col_name.lower() for kw in keywords):
                    lines.append(
                        f"  Rango {col_name}: {rng.get('min')} a {rng.get('max')}"
                    )

        return ("\n".join(lines) + "\n") if lines else ""

    # ─────────────────────────────────────────────────────────────────────────
    # FALLBACK
    # ─────────────────────────────────────────────────────────────────────────

    def _get_fallback_context(self) -> str:
        """
        Fallback: usa db_metadata_optimized.json si los indices SIUO no existen.
        Mantiene compatibilidad con el sistema v1.

        PRIVACIDAD: filtra las lineas que contienen nombres de columnas sensibles
        (NIF, EMAIL, TELEFONO, IBAN, etc.) para que no lleguen a la IA.
        Las columnas sensibles son nombres de columna de BD, no valores reales,
        pero igualmente no deben enviarse a la IA para evitar que genere SQL
        que acceda a datos personales.
        """
        if self._fallback_schema:
            return self._fallback_schema

        try:
            from backend.core.config.database_metadata import get_semantic_schema
            from backend.modules.db_explorer.constants import PrivacyConfig
            raw_schema = get_semantic_schema()
            self._fallback_schema = self._filter_sensitive_columns_from_schema(
                raw_schema, PrivacyConfig.SENSITIVE_COLUMNS
            )
            n_raw = len(raw_schema.splitlines())
            n_filtered = len(self._fallback_schema.splitlines())
            logger.info(
                f"[ContextRetriever] Fallback: db_metadata_optimized.json "
                f"({n_raw} lineas -> {n_filtered} tras filtrar columnas sensibles)"
            )
        except Exception as exc:
            logger.warning(f"[ContextRetriever] Fallback tambien fallo: {exc}")
            self._fallback_schema = "Base de datos Firebird 2.5. Usa FIRST N en lugar de LIMIT."

        return self._fallback_schema

    def _filter_sensitive_columns_from_schema(
        self, schema: str, sensitive_columns: set
    ) -> str:
        """
        Filtra del esquema de texto las lineas que contienen nombres de columnas
        sensibles (NIF, EMAIL, TELEFONO, IBAN, BIC, etc.).

        El esquema tiene el formato:
          • NOMBRE_COLUMNA: TIPO - descripcion
        Solo se eliminan las lineas de columna (que empiezan con '•') donde
        el nombre de columna (primera palabra tras '•') esta en SENSITIVE_COLUMNS.

        Esto garantiza que la IA no recibe informacion sobre columnas de datos
        personales, reduciendo el riesgo de que genere SQL que acceda a ellas.
        """
        import re
        filtered_lines = []
        # Patron: linea de columna en el esquema fallback
        # Ejemplos:
        #   "     • NIF: VARCHAR(20) - NIF/CIF"
        #   "     • TELEFONO: VARCHAR(20) - Teléfono de contacto"
        col_pattern = re.compile(r'^\s*[•\*\-]\s+([A-Z0-9_]+)\s*:', re.IGNORECASE)

        for line in schema.splitlines():
            m = col_pattern.match(line)
            if m:
                col_name = m.group(1).upper()
                if col_name in sensitive_columns:
                    # Omitir esta linea — columna sensible
                    logger.debug(
                        f"[ContextRetriever][Privacy] Columna sensible filtrada del fallback: {col_name}"
                    )
                    continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    # ─────────────────────────────────────────────────────────────────────────
    # AUTOAPRENDIZAJE
    # ─────────────────────────────────────────────────────────────────────────

    def _log_query(
        self,
        question:     str,
        keywords:     List[str],
        tables_used:  List[str],
        unknown_kws:  List[str],
    ) -> None:
        """
        Registra la consulta para autoaprendizaje.
        Detecta keywords no mapeados que podrian enriquecer el concept_index.
        """
        try:
            log = _load_json(QUERY_LOG_PATH, {"queries": [], "unknown_keywords": {}})

            # Registrar consulta
            entry = {
                "ts":          datetime.now().isoformat(),
                "question":    question[:200],
                "keywords":    keywords,
                "tables_used": tables_used,
                "unknown_kws": unknown_kws,
            }
            log["queries"].append(entry)

            # Mantener solo las ultimas MAX_LOG_ENTRIES
            if len(log["queries"]) > MAX_LOG_ENTRIES:
                log["queries"] = log["queries"][-MAX_LOG_ENTRIES:]

            # Acumular keywords desconocidos (para sugerir nuevas entradas)
            for kw in unknown_kws:
                if len(kw) > 3:  # Ignorar palabras muy cortas
                    log["unknown_keywords"][kw] = log["unknown_keywords"].get(kw, 0) + 1

            _save_json(QUERY_LOG_PATH, log)

        except Exception as exc:
            logger.debug(f"[ContextRetriever] Error en log: {exc}")

    def get_learning_suggestions(self) -> Dict[str, Any]:
        """
        Devuelve sugerencias de autoaprendizaje:
        - Keywords frecuentes sin mapear -> candidatos para concept_index
        - Tablas mas usadas -> candidatas para analisis prioritario
        - Preguntas frecuentes -> candidatas para consultas de ejemplo
        """
        log = _load_json(QUERY_LOG_PATH, {"queries": [], "unknown_keywords": {}})

        # Keywords desconocidos mas frecuentes
        unknown = sorted(
            log["unknown_keywords"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        # Tablas mas usadas
        table_counts: Dict[str, int] = defaultdict(int)
        for q in log["queries"]:
            for t in q.get("tables_used", []):
                table_counts[t] += 1
        top_tables = sorted(table_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Preguntas mas frecuentes (por similitud de keywords)
        recent = log["queries"][-50:] if len(log["queries"]) > 50 else log["queries"]

        return {
            "unknown_keywords_frequent": [
                {"keyword": kw, "count": cnt} for kw, cnt in unknown
            ],
            "top_tables_used": [
                {"table": t, "count": cnt} for t, cnt in top_tables
            ],
            "total_queries_logged": len(log["queries"]),
            "suggestion": (
                "Considera anadir estos keywords al concept_index para mejorar "
                "la precision de las respuestas."
            ) if unknown else "El concept_index esta bien cubierto.",
        }

    def register_feedback(
        self,
        question:    str,
        sql_used:    str,
        was_correct: bool,
        tables_used: List[str],
    ) -> None:
        """
        Registra feedback del usuario (SQL correcto/incorrecto).
        Permite al sistema aprender de los errores.
        """
        try:
            log = _load_json(QUERY_LOG_PATH, {"queries": [], "unknown_keywords": {}, "feedback": []})
            log.setdefault("feedback", []).append({
                "ts":          datetime.now().isoformat(),
                "question":    question[:200],
                "sql":         sql_used[:500],
                "correct":     was_correct,
                "tables_used": tables_used,
            })
            # Mantener solo los ultimos 200 feedbacks
            log["feedback"] = log["feedback"][-200:]
            _save_json(QUERY_LOG_PATH, log)
        except Exception as exc:
            logger.debug(f"[ContextRetriever] Error en feedback: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # UTILIDADES
    # ─────────────────────────────────────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """Estimacion rapida de tokens (1 token ~ 4 chars)."""
        return max(1, int(len(text) * TOKENS_PER_CHAR))

    def get_stats(self) -> Dict[str, Any]:
        """Estadisticas del retriever para el dashboard."""
        return {
            "loaded":           self._loaded,
            "tables_indexed":   len(self._table_index),
            "concept_keywords": len(self._concept_index),
            "graph_nodes":      len(self._graph_adj),
            "graph_edges":      sum(len(v) for v in self._graph_adj.values()) // 2,
            "value_enums":      len(self._value_index.get("enums", {})),
            "value_ranges":     len(self._value_index.get("ranges", {})),
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_retriever_instance: Optional[ContextRetriever] = None


def get_context_retriever() -> ContextRetriever:
    """Devuelve el singleton del ContextRetriever (cargado en memoria)."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = ContextRetriever()
        _retriever_instance.load()
    return _retriever_instance


def reload_context_retriever() -> ContextRetriever:
    """Fuerza la recarga de los indices (llamar tras una nueva indexacion)."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = ContextRetriever()
    _retriever_instance.reload()
    return _retriever_instance
