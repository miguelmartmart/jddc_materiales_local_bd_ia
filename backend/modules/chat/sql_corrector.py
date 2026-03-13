"""
SQL Auto-Correction System — Ultra-Resiliente
Detecta errores SQL, consulta metadatos reales de la BD, extrae muestras de datos
y solicita corrección a la IA con contexto enriquecido.

Flujo de corrección (por orden de prioridad):
  1. Normalización determinista (FirebirdSQLNormalizer) — sin IA
  2. fix_after_error determinista — sin IA (BLOB, column_unknown conocido, LIMIT)
  3. Consulta metadatos reales de la BD (columnas reales de las tablas implicadas)
     3a. Para table_unknown: busca tablas similares en RDB$RELATIONS (fuzzy match)
         y envía a la IA la lista de candidatas reales para que elija la correcta.
  4. Extracción de muestra de datos reales (FIRST 3 filas)
  5. Corrección por IA con contexto enriquecido (metadatos + muestra + error)
  6. Actualización del aprendizaje permanente (db_metadata_optimized.json)

Parámetros configurables (config.json):
  max_sql_retries: número máximo de reintentos SQL (default: 4)

DEVIA: backend/modules/chat/DEVIA_ROBUSTNESS.md
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import re
import json
import os
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer
from backend.modules.chat.firebird_sql_constants import LOW_RECORD_TABLES

logger = logging.getLogger(__name__)

# Instancia compartida del normalizador determinista
_normalizer = FirebirdSQLNormalizer()

# Ruta al fichero de metadatos persistente
_METADATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "core", "config", "db_metadata_optimized.json"
)

# Ruta al config.json del chat (fuente única de verdad para parámetros)
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# Default de reintentos SQL si config.json no está disponible
_SQL_MAX_RETRIES_DEFAULT = 4


def _load_sql_max_retries() -> int:
    """
    Lee max_sql_retries del config.json del chat.
    Permite cambiar el número de reintentos SQL sin reiniciar el servidor.
    """
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            value = cfg.get("max_sql_retries", _SQL_MAX_RETRIES_DEFAULT)
            return int(value)
    except Exception as e:
        logger.warning(
            f"[SQL CORRECTOR] ⚠️ No se pudo leer max_sql_retries de config.json: {e}. "
            f"Usando default {_SQL_MAX_RETRIES_DEFAULT}."
        )
    return _SQL_MAX_RETRIES_DEFAULT


class SQLCorrector:
    """Handles SQL error detection and automatic correction via AI."""

    def __init__(self):
        pass

    # ─── Detección de tipo de error ───────────────────────────────────────────

    def detect_error_type(self, error_message: str) -> Dict[str, Any]:
        """
        Detect the type of SQL error from error message.
        Returns dict with 'type', optional 'table'/'column'/'token', and 'message'.
        """
        error_upper = error_message.upper()

        if "TABLE UNKNOWN" in error_upper:
            table_name = None
            if "Table unknown" in error_message:
                parts = error_message.split("Table unknown")
                if len(parts) > 1:
                    table_name = parts[1].strip().split()[0] if parts[1].strip() else None
            return {
                "type": "table_unknown",
                "table": table_name,
                "message": "La tabla especificada no existe en la base de datos",
            }

        if "COLUMN UNKNOWN" in error_upper:
            column_name = None
            if "Column unknown" in error_message:
                parts = error_message.split("Column unknown")
                if len(parts) > 1:
                    column_name = parts[1].strip().split()[0] if parts[1].strip() else None
            return {
                "type": "column_unknown",
                "column": column_name,
                "message": "La columna especificada no existe en la tabla",
            }

        if "TOKEN UNKNOWN" in error_upper:
            # El token puede estar en la misma línea o en la siguiente
            # Ej: "Token unknown - line 1, column 50\nLIMIT"
            # Ej: "Token unknown LIMIT"
            token = None
            parts = error_message.split("Token unknown")
            if len(parts) > 1:
                rest = parts[1].strip()
                # Buscar en la misma línea primero
                first_line = rest.split("\n")[0].strip()
                # Quitar "- line X, column Y" si está presente
                import re as _re
                first_line_clean = _re.sub(r'-\s*line\s+\d+,\s*column\s+\d+', '', first_line).strip()
                if first_line_clean:
                    token = first_line_clean.split()[0] if first_line_clean.split() else None
                # Si no hay token en la primera línea, buscar en la siguiente
                if not token or not token.isalpha():
                    lines = rest.split("\n")
                    for line in lines[1:]:
                        candidate = line.strip()
                        if candidate and candidate.isalpha():
                            token = candidate
                            break
            if token and token.upper() in ["LIMIT", "ROWS", "TOP"]:
                return {
                    "type": "invalid_keyword",
                    "token": token,
                    "message": f"El comando '{token}' NO existe en Firebird 2.5. Usar 'SELECT FIRST N ...'",
                }
            return {
                "type": "syntax_error",
                "token": token,
                "message": "Error de sintaxis SQL (Token desconocido)",
            }

        if "SYNTAX" in error_upper:
            return {"type": "syntax_error", "message": "Error de sintaxis SQL"}

        if "BLOB" in error_upper and "CONVERSION" in error_upper:
            return {
                "type": "blob_in_groupby",
                "message": (
                    "Columna BLOB no puede usarse en GROUP BY. "
                    "Usa CODIGO, NOMBRE o DESCRIPCIONCORTA en el GROUP BY."
                ),
            }

        return {"type": "unknown", "message": error_message}

    # ─── Consulta de metadatos reales de la BD ────────────────────────────────

    def _get_real_table_columns(
        self, table_name: str, execute_func: callable
    ) -> List[str]:
        """
        Consulta las columnas reales de una tabla en Firebird usando RDB$RELATION_FIELDS.
        Devuelve lista de nombres de columna en mayúsculas.
        """
        try:
            query = (
                f"SELECT FIRST 100 TRIM(RDB$FIELD_NAME) AS FIELD_NAME "
                f"FROM RDB$RELATION_FIELDS "
                f"WHERE TRIM(RDB$RELATION_NAME) = '{table_name.upper()}' "
                f"ORDER BY RDB$FIELD_POSITION"
            )
            rows = execute_func(query)
            cols = [r.get("FIELD_NAME", "").strip() for r in rows if r.get("FIELD_NAME")]
            logger.info(
                f"[SQL CORRECTOR] 🔍 Columnas reales de {table_name}: {cols}"
            )
            return cols
        except Exception as e:
            logger.warning(
                f"[SQL CORRECTOR] ⚠️ No se pudieron obtener columnas de {table_name}: {e}"
            )
            return []

    def _get_real_table_sample(
        self, table_name: str, execute_func: callable, limit: int = 3
    ) -> List[Dict]:
        """
        Extrae una muestra de datos reales de la tabla (FIRST N filas).
        Útil para que la IA entienda qué valores reales hay en cada columna.
        """
        try:
            query = f"SELECT FIRST {limit} * FROM {table_name}"
            rows = execute_func(query)
            logger.info(
                f"[SQL CORRECTOR] 📊 Muestra de {table_name}: {len(rows)} filas"
            )
            return rows
        except Exception as e:
            logger.warning(
                f"[SQL CORRECTOR] ⚠️ No se pudo obtener muestra de {table_name}: {e}"
            )
            return []

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """
        Extrae los nombres de tablas referenciadas en el SQL.
        Detecta: FROM tabla, JOIN tabla, FROM tabla alias, JOIN tabla alias.
        """
        tables = []
        # FROM tabla [alias] y JOIN tabla [alias]
        pattern = re.compile(
            r'\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)\b', re.IGNORECASE
        )
        for m in pattern.finditer(sql):
            name = m.group(1).upper()
            # Excluir palabras clave SQL
            if name not in {
                "SELECT", "WHERE", "GROUP", "ORDER", "HAVING", "UNION",
                "INNER", "LEFT", "RIGHT", "OUTER", "CROSS", "ON", "AS",
            }:
                tables.append(name)
        return list(dict.fromkeys(tables))  # deduplicar preservando orden

    def _find_date_columns(self, columns: List[str]) -> List[str]:
        """Detecta columnas de fecha por nombre (contienen FECHA, DATE, etc.)."""
        date_keywords = ["FECHA", "DATE", "EMISION", "ENTREGA", "VENCIMIENTO"]
        return [c for c in columns if any(kw in c.upper() for kw in date_keywords)]

    def _find_similar_tables_in_db(
        self, unknown_table: str, execute_func: callable, max_candidates: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Busca en RDB$RELATIONS tablas reales cuyo nombre contenga alguna subcadena
        del nombre desconocido, o viceversa. Devuelve lista de candidatas con
        nombre y número de registros para que la IA elija la correcta.

        Estrategia de búsqueda (por orden de prioridad):
          1. Nombre exacto (ya sabemos que no existe, pero por si acaso)
          2. Nombre contiene la raíz del desconocido (ej: PROV → DOCPRO, PROVEED, ESTPROVEED)
          3. Desconocido contiene el nombre de la tabla real (ej: PROVEEDOR → PROV)
          4. Primeras 4 letras en común

        Retorna lista de dicts: [{"table": "DOCPRO", "n_records": 1234, "desc": "..."}]
        """
        if not unknown_table:
            return []

        unknown_upper = unknown_table.upper().strip()
        # Extraer raíces de búsqueda: el nombre completo y subcadenas de 4+ chars
        roots = set()
        roots.add(unknown_upper)
        # Subcadenas de 4+ caracteres del nombre desconocido
        for length in range(4, len(unknown_upper) + 1):
            for start in range(len(unknown_upper) - length + 1):
                roots.add(unknown_upper[start:start + length])

        candidates: Dict[str, Dict] = {}

        for root in sorted(roots, key=len, reverse=True):  # más largas primero
            if len(candidates) >= max_candidates:
                break
            try:
                # Buscar tablas reales que contengan esta raíz en su nombre
                query = (
                    f"SELECT FIRST 20 TRIM(r.RDB$RELATION_NAME) AS TNAME "
                    f"FROM RDB$RELATIONS r "
                    f"WHERE r.RDB$SYSTEM_FLAG = 0 "
                    f"AND r.RDB$VIEW_BLR IS NULL "
                    f"AND UPPER(TRIM(r.RDB$RELATION_NAME)) CONTAINING '{root}' "
                    f"ORDER BY TRIM(r.RDB$RELATION_NAME)"
                )
                rows = execute_func(query)
                for row in rows:
                    tname = (row.get("TNAME") or "").strip()
                    if tname and tname not in candidates:
                        candidates[tname] = {"table": tname, "n_records": None, "desc": ""}
            except Exception as e:
                logger.debug(f"[SQL CORRECTOR] _find_similar_tables: error buscando '{root}': {e}")
                continue

        if not candidates:
            logger.warning(
                f"[SQL CORRECTOR] ⚠️ No se encontraron tablas similares a '{unknown_table}' en RDB$RELATIONS"
            )
            return []

        # Enriquecer con número de registros (COUNT(*)) para las primeras 10 candidatas
        result = []
        for tname in list(candidates.keys())[:max_candidates]:
            entry = {"table": tname, "n_records": None}
            try:
                count_rows = execute_func(f"SELECT COUNT(*) AS N FROM {tname}")
                if count_rows:
                    entry["n_records"] = count_rows[0].get("N", 0)
            except Exception:
                pass
            result.append(entry)

        # Ordenar: primero las que tienen más registros (más probablemente la correcta)
        result.sort(key=lambda x: (x["n_records"] or 0), reverse=True)

        logger.info(
            f"[SQL CORRECTOR] 🔎 Tablas similares a '{unknown_table}': "
            f"{[r['table'] for r in result]}"
        )
        return result

    def _get_all_tables_from_metadata(self) -> List[str]:
        """
        Lee la lista de tablas del db_metadata_optimized.json como fallback
        cuando no hay conexión a la BD.
        """
        try:
            meta_path = os.path.normpath(_METADATA_PATH)
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    metadata = json.load(f)
                return [k for k in metadata.keys() if not k.startswith("_")]
        except Exception as e:
            logger.warning(f"[SQL CORRECTOR] ⚠️ No se pudo leer metadatos: {e}")
        return []

    # ─── Actualización del aprendizaje permanente ─────────────────────────────

    def _update_metadata_learning(
        self,
        table_name: str,
        real_columns: List[str],
        note: Optional[str] = None,
    ) -> None:
        """
        Actualiza db_metadata_optimized.json con las columnas reales descubiertas
        durante la corrección de errores. Aprendizaje permanente.
        """
        try:
            meta_path = os.path.normpath(_METADATA_PATH)
            if not os.path.exists(meta_path):
                logger.warning(f"[SQL CORRECTOR] ⚠️ No existe {meta_path}")
                return

            with open(meta_path, encoding="utf-8") as f:
                metadata = json.load(f)

            table_key = table_name.upper()
            if table_key not in metadata:
                metadata[table_key] = {}

            entry = metadata[table_key]

            # Actualizar columnas con las reales descubiertas
            if real_columns:
                existing_cols = entry.get("columns", {})
                for col in real_columns:
                    if col not in existing_cols:
                        existing_cols[col] = col  # valor mínimo
                entry["columns"] = existing_cols
                entry["_columns_verified"] = True

            # Añadir nota crítica si se proporciona
            if note:
                entry["_nota_critica"] = note

            entry["_auto_corrected"] = True

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.info(
                f"[SQL CORRECTOR] 💾 Metadatos actualizados para {table_name} "
                f"({len(real_columns)} columnas reales)"
            )
        except Exception as e:
            logger.warning(f"[SQL CORRECTOR] ⚠️ No se pudo actualizar metadatos: {e}")

    # ─── Corrección por IA con contexto enriquecido ───────────────────────────

    async def request_correction(
        self,
        failed_query: str,
        original_question: str,
        error_message: str,
        error_info: Dict[str, Any],
        db_context: str,
        ai_provider: Any,
        real_columns_by_table: Optional[Dict[str, List[str]]] = None,
        sample_data_by_table: Optional[Dict[str, List[Dict]]] = None,
        low_record_warnings: Optional[List[str]] = None,
    ) -> str:
        """
        Request SQL correction from AI model with enriched context.

        Incluye:
        - Columnas reales de las tablas implicadas (consultadas en la BD)
        - Muestra de datos reales (FIRST 3 filas)
        - Advertencias de tablas con pocos registros
        """
        # Construir sección de metadatos reales
        real_meta_section = ""
        if real_columns_by_table:
            real_meta_section = "\n\nMETADATOS REALES DE LA BD (consultados en tiempo real):\n"
            for tbl, cols in real_columns_by_table.items():
                date_cols = self._find_date_columns(cols)
                real_meta_section += f"\nTabla {tbl}:\n"
                real_meta_section += f"  Columnas reales: {', '.join(cols)}\n"
                if date_cols:
                    real_meta_section += f"  ⚠️ Columnas de fecha disponibles: {', '.join(date_cols)}\n"
                else:
                    real_meta_section += f"  ⚠️ Esta tabla NO tiene columnas de fecha propias.\n"

        # Construir sección de muestra de datos
        sample_section = ""
        if sample_data_by_table:
            sample_section = "\n\nMUESTRA DE DATOS REALES (para entender la estructura):\n"
            for tbl, rows in sample_data_by_table.items():
                if rows:
                    sample_section += f"\nTabla {tbl} (primeras {len(rows)} filas):\n"
                    for i, row in enumerate(rows[:3]):
                        sample_section += f"  Fila {i+1}: {json.dumps(row, ensure_ascii=False, default=str)}\n"

        # Advertencias de tablas con pocos registros
        low_record_section = ""
        if low_record_warnings:
            low_record_section = "\n\n⚠️ ADVERTENCIAS DE TABLAS CON POCOS REGISTROS:\n"
            for w in low_record_warnings:
                low_record_section += f"  - {w}\n"
            low_record_section += (
                "  → Los datos pueden estar en otra tabla o los metadatos están desactualizados.\n"
                "  → Considera usar tablas con más registros para la consulta.\n"
            )

        correction_prompt = f"""La siguiente consulta SQL falló con un error en Firebird 2.5.

PREGUNTA ORIGINAL DEL USUARIO:
{original_question}

CONSULTA SQL QUE FALLÓ:
```sql
{failed_query}
```

ERROR RECIBIDO:
{error_message}

TIPO DE ERROR: {error_info['type']}
MENSAJE AMIGABLE: {error_info.get('message', '')}

ESQUEMA DE BASE DE DATOS (contexto SIUO):
{db_context}
{real_meta_section}
{sample_section}
{low_record_section}

REGLAS CRÍTICAS DE FIREBIRD 2.5:
1. Para limitar resultados: SELECT FIRST N ... (NO uses LIMIT, ROWS, o TOP)
2. Para calcular fechas:
   - Sintaxis CORRECTA: DATEADD(MONTH, -N, CURRENT_DATE)
   - EXTRACT(MONTH FROM FECHA), EXTRACT(YEAR FROM FECHA)
   - Mes actual: EXTRACT(MONTH FROM FECHA) = EXTRACT(MONTH FROM CURRENT_DATE)
3. DOCLIN no tiene columna FECHA. La fecha del documento está en DOCCAB.FECHA.
   Para filtrar por fecha en DOCLIN: JOIN DOCCAB C ON C.CODIGO = L.CODDOCUMENTO
   y usar C.FECHA en el WHERE.
4. Si una tabla no tiene la columna que necesitas, busca en tablas relacionadas.
5. Usa SOLO columnas que aparezcan en los METADATOS REALES DE LA BD.
6. Si los datos de una tabla tienen pocos registros, considera usar otra tabla.
7. UPPER(col) LIKE UPPER('%val%') para búsquedas de texto (case-insensitive).

INSTRUCCIONES:
1. Analiza el error: "{error_message}"
2. Consulta los METADATOS REALES para saber qué columnas existen realmente.
3. Si la columna no existe en la tabla, búscala en tablas relacionadas.
4. Genera una consulta SQL CORREGIDA que:
   - Use SOLO columnas que existen según los metadatos reales
   - Resuelva el error específico
   - Mantenga la intención original de la pregunta
   - Use sintaxis válida de Firebird 2.5
5. Devuelve SOLO la consulta SQL corregida entre ```sql y ```
6. NO añadas explicaciones

CONSULTA SQL CORREGIDA:"""

        try:
            response = await ai_provider.generate_text(correction_prompt)

            if "```sql" in response:
                corrected_sql = response.split("```sql")[1].split("```")[0].strip()
                corrected_sql = corrected_sql.rstrip(";").strip()
                return corrected_sql
            else:
                lines = [l.strip() for l in response.split("\n") if l.strip()]
                if lines:
                    return lines[0].rstrip(";").strip()

        except Exception as e:
            logger.error(f"[SQL CORRECTOR] ❌ Error solicitando corrección: {str(e)}")

        return None

    # ─── Detección y resolución de placeholders ───────────────────────────────

    _PLACEHOLDER_RE = re.compile(r'<([A-Z_][A-Z0-9_]*)>', re.IGNORECASE)

    def _detect_placeholders(self, sql: str) -> List[str]:
        """
        Detecta placeholders literales del tipo <ID_DEL_TRABAJADOR> en el SQL.
        La IA a veces genera SQL con placeholders cuando no conoce el valor concreto.
        Firebird no puede ejecutar SQL con '<' como token → error inmediato.

        Returns:
            Lista de nombres de placeholder encontrados (ej: ['ID_DEL_TRABAJADOR'])
        """
        return self._PLACEHOLDER_RE.findall(sql)

    async def _resolve_placeholders(
        self,
        sql_query: str,
        original_question: str,
        db_context: str,
        ai_provider: Any,
        execute_func: callable,
        placeholders: List[str],
    ) -> Optional[str]:
        """
        Intenta resolver los placeholders en el SQL de dos formas:

        Estrategia A — Búsqueda por nombre (LIKE):
          Si el placeholder es <ID_DEL_TRABAJADOR> y la pregunta menciona un nombre,
          la IA puede reescribir el SQL usando LIKE '%nombre%' en lugar del ID.

        Estrategia B — Subquery:
          Si la pregunta no menciona un valor concreto, la IA puede usar una subquery
          para buscar el registro por nombre en lugar de por ID.

        Si ninguna estrategia funciona, devuelve None (el caller pedirá el dato al usuario).
        """
        tables_in_sql = self._extract_tables_from_sql(sql_query)
        real_columns_by_table: Dict[str, List[str]] = {}
        sample_data_by_table: Dict[str, List[Dict]] = {}

        for table in tables_in_sql:
            if table.startswith("RDB$"):
                continue
            cols = self._get_real_table_columns(table, execute_func)
            if cols:
                real_columns_by_table[table] = cols
            sample = self._get_real_table_sample(table, execute_func, limit=3)
            if sample:
                sample_data_by_table[table] = sample

        # Construir sección de metadatos reales
        real_meta_section = ""
        if real_columns_by_table:
            real_meta_section = "\n\nMETADATOS REALES DE LA BD:\n"
            for tbl, cols in real_columns_by_table.items():
                real_meta_section += f"\nTabla {tbl}: {', '.join(cols)}\n"

        sample_section = ""
        if sample_data_by_table:
            sample_section = "\n\nMUESTRA DE DATOS REALES:\n"
            for tbl, rows in sample_data_by_table.items():
                if rows:
                    sample_section += f"\nTabla {tbl} (primeras {len(rows)} filas):\n"
                    for i, row in enumerate(rows[:3]):
                        sample_section += f"  Fila {i+1}: {json.dumps(row, ensure_ascii=False, default=str)}\n"

        placeholder_list = ", ".join(f"<{p}>" for p in placeholders)

        prompt = f"""El SQL generado contiene placeholders literales que Firebird no puede ejecutar.

PREGUNTA ORIGINAL DEL USUARIO:
{original_question}

SQL CON PLACEHOLDERS (NO ejecutable):
```sql
{sql_query}
```

PLACEHOLDERS DETECTADOS: {placeholder_list}

PROBLEMA:
La IA generó placeholders como <ID_DEL_TRABAJADOR> porque no conoce el valor concreto.
Firebird falla con "Token unknown <" al intentar ejecutar este SQL.

ESQUEMA DE BASE DE DATOS:
{db_context}
{real_meta_section}
{sample_section}

INSTRUCCIONES PARA RESOLVER:
1. Analiza la pregunta del usuario: ¿menciona un nombre, código o valor concreto?
2. Si SÍ menciona un valor (ej: "Juan García", "código 123"):
   - Reescribe el SQL usando UPPER(col) LIKE UPPER('%valor%') para buscar por nombre
   - O usa una subquery: WHERE CODTRABAJADOR = (SELECT FIRST 1 CODIGO FROM TRABAJADOR WHERE UPPER(NOMBRE) LIKE UPPER('%valor%'))
3. Si NO menciona un valor concreto:
   - Reescribe el SQL para devolver los datos de TODOS los registros (sin filtro por ID)
   - O usa los primeros N registros si tiene sentido
4. USA SOLO columnas que aparezcan en los METADATOS REALES
5. Sintaxis Firebird 2.5: FIRST N (no LIMIT), EXTRACT(YEAR FROM FECHA), etc.

REGLA CRÍTICA: El SQL resultante NO debe contener ningún placeholder <...>.
Devuelve SOLO el SQL corregido entre ```sql y ```. Sin explicaciones.

SQL CORREGIDO:"""

        try:
            response = await ai_provider.generate_text(prompt)
            if "```sql" in response:
                corrected = response.split("```sql")[1].split("```")[0].strip()
                corrected = corrected.rstrip(";").strip()
                # Verificar que no quedan placeholders
                remaining = self._detect_placeholders(corrected)
                if remaining:
                    logger.warning(
                        f"[SQL CORRECTOR] ⚠️ La IA no eliminó todos los placeholders: {remaining}"
                    )
                    return None
                logger.info(f"[SQL CORRECTOR] ✅ Placeholders resueltos por IA: {corrected}")
                return corrected
        except Exception as e:
            logger.error(f"[SQL CORRECTOR] ❌ Error resolviendo placeholders: {type(e).__name__}: {e}")

        return None

    # ─── Ejecución con corrección automática ─────────────────────────────────

    async def execute_with_correction(
        self,
        sql_query: str,
        original_question: str,
        db_context: str,
        ai_provider: Any,
        execute_func: callable,
        max_retries: int = None,
        attempt: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL with automatic ultra-resilient correction on errors.

        max_retries: si None, se lee de config.json (max_sql_retries). Permite
                     sobrescribir desde service.py si se desea, pero el default
                     siempre viene del fichero de configuración centralizado.

        Flujo:
          0. PRE-EJECUCIÓN: detectar placeholders <...> → resolver con IA antes de ejecutar
          1. Normalización determinista (intento 0)
          2. Ejecución
          3. Si falla → detect_error_type()
          4. fix_after_error() determinista
          5a. Para table_unknown: buscar tablas similares en RDB$RELATIONS (fuzzy match)
              → enviar candidatas a la IA para que elija la correcta
          5b. Para otros errores: consultar columnas reales + muestra de datos
          6. Corrección por IA con contexto enriquecido
          7. Actualizar aprendizaje permanente
        """
        # Leer max_retries del config.json si no se especifica explícitamente
        if max_retries is None:
            max_retries = _load_sql_max_retries()
            if attempt == 0:
                logger.info(
                    f"[SQL CORRECTOR] 🔧 max_sql_retries={max_retries} "
                    f"(leído de config.json)"
                )
        # ── PASO 0: Detectar placeholders ANTES de ejecutar ───────────────────
        # La IA a veces genera SQL con <ID_DEL_TRABAJADOR> cuando no conoce el valor.
        # Firebird falla con "Token unknown <" — detectamos esto ANTES de ejecutar
        # para dar a la IA la oportunidad de resolverlo con búsqueda por nombre.
        if attempt == 0:
            placeholders = self._detect_placeholders(sql_query)
            if placeholders:
                logger.warning(
                    f"[SQL CORRECTOR] ⚠️ SQL con placeholders detectados ANTES de ejecutar: "
                    f"{placeholders} — intentando resolver con IA..."
                )
                resolved_sql = await self._resolve_placeholders(
                    sql_query=sql_query,
                    original_question=original_question,
                    db_context=db_context,
                    ai_provider=ai_provider,
                    execute_func=execute_func,
                    placeholders=placeholders,
                )
                if resolved_sql:
                    logger.info(
                        f"[SQL CORRECTOR] ✅ Placeholders resueltos, ejecutando SQL corregido"
                    )
                    # Normalizar y ejecutar el SQL sin placeholders
                    resolved_sql, _ = _normalizer.normalize(resolved_sql)
                    return await self.execute_with_correction(
                        resolved_sql, original_question, db_context, ai_provider,
                        execute_func, max_retries, attempt + 1
                    )
                else:
                    # La IA no pudo resolver los placeholders → informar al usuario
                    placeholder_names = ", ".join(placeholders)
                    raise Exception(
                        f"PLACEHOLDER_UNRESOLVED:{placeholder_names}"
                    )

        # En el primer intento: aplicar normalización determinista completa
        if attempt == 0:
            sql_query, norm_changes = _normalizer.normalize(sql_query)
            if norm_changes:
                logger.info(
                    f"[SQL CORRECTOR] 🔧 {len(norm_changes)} normalizaciones deterministas aplicadas"
                )

        try:
            results = execute_func(sql_query)
            return results

        except Exception as e:
            error_str = str(e)
            logger.error(
                f"[SQL CORRECTOR] ❌ Error en consulta (intento {attempt + 1}/{max_retries + 1}): {error_str}"
            )

            if attempt >= max_retries:
                logger.error(f"[SQL CORRECTOR] ❌ Máximo de intentos alcanzado")
                raise

            error_info = self.detect_error_type(error_str)
            logger.info(f"[SQL CORRECTOR] 🔍 Tipo de error: {error_info['type']}")

            if error_info["type"] == "unknown":
                logger.warning(f"[SQL CORRECTOR] ⚠️ Error desconocido, no se puede corregir")
                raise

            # ── Intento 1: corrección DETERMINISTA (sin IA) ───────────────────
            deterministic_types = {
                "blob_in_groupby", "column_unknown", "invalid_keyword", "syntax_error"
            }
            if error_info["type"] in deterministic_types:
                det_query, det_changes = _normalizer.fix_after_error(sql_query, error_str)
                if det_changes and det_query.strip() != sql_query.strip():
                    logger.info(
                        f"[SQL CORRECTOR] ✅ Corrección DETERMINISTA aplicada ({len(det_changes)} cambios):"
                    )
                    for ch in det_changes:
                        logger.info(f"[SQL CORRECTOR]   • {ch}")
                    return await self.execute_with_correction(
                        det_query, original_question, db_context, ai_provider,
                        execute_func, max_retries, attempt + 1
                    )
                else:
                    logger.info(
                        f"[SQL CORRECTOR] ℹ️ Corrección determinista no aplicable, escalando..."
                    )

            # ── Intento 2: consultar metadatos reales + corrección por IA ─────
            logger.info(
                f"[SQL CORRECTOR] 🔬 Consultando metadatos reales de la BD para enriquecer corrección..."
            )

            # Extraer tablas del SQL fallido
            tables_in_sql = self._extract_tables_from_sql(sql_query)
            logger.info(f"[SQL CORRECTOR] 📋 Tablas en el SQL: {tables_in_sql}")

            # Consultar columnas reales de cada tabla
            real_columns_by_table: Dict[str, List[str]] = {}
            sample_data_by_table: Dict[str, List[Dict]] = {}
            low_record_warnings: List[str] = []

            for table in tables_in_sql:
                # Excluir tablas de sistema Firebird
                if table.startswith("RDB$"):
                    continue

                # Columnas reales
                cols = self._get_real_table_columns(table, execute_func)
                if cols:
                    real_columns_by_table[table] = cols

                    # Actualizar metadatos permanentes con columnas reales
                    self._update_metadata_learning(table, cols)

                # Muestra de datos reales (solo si la tabla tiene datos)
                sample = self._get_real_table_sample(table, execute_func, limit=3)
                if sample:
                    sample_data_by_table[table] = sample

                # Advertencia si la tabla tiene pocos registros
                if table in LOW_RECORD_TABLES:
                    info = LOW_RECORD_TABLES[table]
                    low_record_warnings.append(info["warning"])
                    logger.warning(
                        f"[SQL CORRECTOR] ⚠️ Tabla con pocos registros: {table} — {info['warning']}"
                    )

            # ── Caso especial: TABLE UNKNOWN → buscar tablas similares en RDB$RELATIONS ──
            # Cuando la tabla no existe, consultamos RDB$RELATIONS para encontrar
            # tablas reales con nombre similar y se las enviamos a la IA para que
            # elija la correcta. Esto resuelve casos como PROVEEDOR → DOCPRO/COMPRA.
            similar_tables_section = ""
            if error_info["type"] == "table_unknown" and error_info.get("table"):
                unknown_tbl = error_info["table"]
                logger.info(
                    f"[SQL CORRECTOR] 🔎 Tabla desconocida '{unknown_tbl}' — "
                    f"buscando alternativas en RDB$RELATIONS..."
                )
                similar_tables = self._find_similar_tables_in_db(unknown_tbl, execute_func)

                if similar_tables:
                    similar_tables_section = (
                        f"\n\n🔎 TABLAS REALES SIMILARES A '{unknown_tbl}' (consultadas en RDB$RELATIONS):\n"
                        f"La tabla '{unknown_tbl}' NO EXISTE en la base de datos. "
                        f"Estas son las tablas reales con nombre similar, ordenadas por número de registros:\n"
                    )
                    for entry in similar_tables[:10]:
                        n = entry.get("n_records")
                        n_str = f"{n:,}" if n is not None else "desconocido"
                        similar_tables_section += f"  - {entry['table']} ({n_str} registros)\n"
                    similar_tables_section += (
                        f"\n  → Elige la tabla más apropiada de la lista anterior para reemplazar '{unknown_tbl}'.\n"
                        f"  → Consulta también sus columnas reales con RDB$RELATION_FIELDS si es necesario.\n"
                    )

                    # Obtener columnas de las 3 candidatas con más registros
                    for candidate in similar_tables[:3]:
                        tname = candidate["table"]
                        if tname not in real_columns_by_table:
                            cols = self._get_real_table_columns(tname, execute_func)
                            if cols:
                                real_columns_by_table[tname] = cols
                                self._update_metadata_learning(tname, cols)
                            sample = self._get_real_table_sample(tname, execute_func, limit=2)
                            if sample:
                                sample_data_by_table[tname] = sample

                    logger.info(
                        f"[SQL CORRECTOR] ✅ {len(similar_tables)} tablas candidatas encontradas "
                        f"para '{unknown_tbl}': {[t['table'] for t in similar_tables[:5]]}"
                    )
                else:
                    # No hay tablas similares en RDB$RELATIONS → fallback a metadatos
                    logger.warning(
                        f"[SQL CORRECTOR] ⚠️ No hay tablas similares a '{unknown_tbl}' en RDB$RELATIONS. "
                        f"Usando metadatos almacenados como fallback."
                    )
                    meta_tables = self._get_all_tables_from_metadata()
                    if meta_tables:
                        similar_tables_section = (
                            f"\n\n⚠️ TABLA '{unknown_tbl}' NO EXISTE. "
                            f"Tablas disponibles en metadatos (primeras 50):\n"
                            + ", ".join(meta_tables[:50]) + "\n"
                            + f"  → Elige la tabla más apropiada para reemplazar '{unknown_tbl}'.\n"
                        )

            # ── Detectar si la columna desconocida existe en otra tabla relacionada ──
            if error_info["type"] == "column_unknown" and error_info.get("column"):
                bad_col = error_info["column"].upper()
                found_in = []
                for tbl, cols in real_columns_by_table.items():
                    if bad_col in [c.upper() for c in cols]:
                        found_in.append(tbl)
                if found_in:
                    logger.info(
                        f"[SQL CORRECTOR] 💡 Columna '{bad_col}' encontrada en: {found_in}"
                    )
                    # Actualizar nota en metadatos
                    for tbl in tables_in_sql:
                        if tbl not in found_in:
                            note = (
                                f"La columna {bad_col} NO existe en {tbl}. "
                                f"Está disponible en: {', '.join(found_in)}. "
                                f"Usar JOIN para acceder a ella."
                            )
                            self._update_metadata_learning(tbl, real_columns_by_table.get(tbl, []), note)

            # Solicitar corrección a la IA con contexto enriquecido
            logger.info(f"[SQL CORRECTOR] 🤖 Solicitando corrección al modelo IA con contexto enriquecido...")
            corrected_query = await self.request_correction(
                failed_query=sql_query,
                original_question=original_question,
                error_message=error_str,
                error_info=error_info,
                db_context=db_context + similar_tables_section,
                ai_provider=ai_provider,
                real_columns_by_table=real_columns_by_table,
                sample_data_by_table=sample_data_by_table,
                low_record_warnings=low_record_warnings,
            )

            if not corrected_query or corrected_query.strip() == sql_query.strip():
                logger.warning(
                    f"[SQL CORRECTOR] ⚠️ El modelo no pudo generar una corrección diferente"
                )
                raise Exception(
                    f"Error después de {attempt + 1} intentos: {error_str}\n"
                    f"Consulta: {sql_query}"
                )

            logger.info(f"[SQL CORRECTOR] ✓ Consulta corregida por IA: {corrected_query}")

            # Normalizar la consulta corregida antes de ejecutar
            corrected_query, _ = _normalizer.normalize(corrected_query)

            return await self.execute_with_correction(
                corrected_query,
                original_question,
                db_context,
                ai_provider,
                execute_func,
                max_retries,
                attempt + 1,
            )

    # ─── Utilidades legacy (mantenidas por compatibilidad) ────────────────────

    def enforce_case_insensitive(self, sql: str) -> str:
        """Legacy — usar FirebirdSQLNormalizer.normalize() en su lugar."""
        import re
        pattern = re.compile(
            r'\b([a-zA-Z0-9_.]+)\s+LIKE\s+\'([^\']*)\'', re.IGNORECASE
        )
        def replace_like(match):
            col = match.group(1)
            val = match.group(2)
            return f"UPPER({col}) LIKE UPPER('{val}')"
        return pattern.sub(replace_like, sql)

    def clean_firebird_sql(self, sql: str) -> str:
        """Legacy — usar FirebirdSQLNormalizer.normalize() en su lugar."""
        sql, _ = _normalizer.normalize(sql)
        return sql
