"""
MetadataBuilderService — Construcción de metadatos de BD con IA local.

SEGURIDAD: Los datos de la BD SOLO se envían a la IA local LAN (settings.JDDCIA_BASE_URL*).
NUNCA salen a internet. Si la IA local no está disponible, el proceso se cancela.

FLUJO COMPLETO (con trazas):
  [1] Usuario → Router → MetadataBuilderService.check_local_ai()
      EMISOR: Frontend  RECEPTOR: Qwen3 LAN
      → Verifica disponibilidad antes de cualquier operación

  [2] MetadataBuilderService.get_all_tables()
      EMISOR: Service  RECEPTOR: Firebird
      → Lista tablas de usuario + estado de metadatos actuales

  [3] MetadataBuilderService.get_table_structure(table_name)
      EMISOR: Service  RECEPTOR: Firebird
      → Columnas, tipos, PKs, FKs, conteo, muestra sin datos sensibles

  [4] MetadataBuilderService.analyze_table_with_local_ai(table_name, structure)
      EMISOR: Service  RECEPTOR: Qwen3 LAN (SOLO LAN, nunca internet)
      → Genera JSON de metadatos semánticos

  [5] MetadataBuilderService.save_table_metadata(table_name, metadata)
      EMISOR: Service (tras aprobación usuario)  RECEPTOR: db_metadata_optimized.json
      → Persiste los metadatos aprobados

DEPENDENCIAS:
  - settings.py: JDDCIA_BASE_URL, JDDCIA_BASE_URL_FALLBACK, JDDCIA_API_KEY, DB_*
  - constants.py: LocalAITimeouts, LocalAIParams, PrivacyConfig, ProcessingLimits
  - firebird_metadata_queries.py: SQL de introspección
  - metadata_manager.py: lectura/escritura de db_metadata_optimized.json
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

import httpx

from backend.core.config.settings import settings
from backend.core.config.metadata_manager import get_metadata_manager
from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import DBConstants
from backend.drivers.db.firebird_metadata_queries import (
    QUERY_USER_TABLES,
    QUERY_TABLE_COLUMNS_TYPED,
    QUERY_TABLE_PRIMARY_KEYS,
    QUERY_TABLE_FOREIGN_KEYS,
    QUERY_COUNT_TEMPLATE,
    QUERY_SAMPLE_TEMPLATE,
)
from backend.modules.db_explorer.constants import (
    LocalAITimeouts,
    LocalAIParams,
    PrivacyConfig,
    ProcessingLimits,
    TableCategory,
    MetadataBuilderLog,
    MetadataBuilderMessages,
)

logger = logging.getLogger(__name__)

# ─── Helpers de traza ─────────────────────────────────────────────────────────

def _trace(prefix: str, emisor: str, receptor: str, msg: str, data: Any = None) -> None:
    """Traza estructurada: [PREFIX] EMISOR → RECEPTOR: mensaje [DATA]."""
    logger.info(f"{prefix} {emisor} → {receptor}: {msg}")
    if data is not None:
        logger.info(f"{prefix} DATA: {str(data)[:400]}")


# ─── Helpers de validación ────────────────────────────────────────────────────

_VALID_TABLE_NAME = re.compile(r'^[A-Z][A-Z0-9_$]{0,30}$')


def _validate_table_name(name: str) -> bool:
    """Valida que el nombre de tabla sea seguro para usar en SQL dinámico."""
    return bool(_VALID_TABLE_NAME.match(name.upper()))


# ─── Servicio principal ───────────────────────────────────────────────────────

class MetadataBuilderService:
    """
    Analiza tablas Firebird con la IA local Qwen3 y genera entradas
    para db_metadata_optimized.json.

    Todos los parámetros de conexión (IA y BD) vienen de settings.py / .env.
    Ningún valor de IP, puerto, credencial o modelo está hardcodeado aquí.
    """

    def __init__(self):
        self._metadata_manager = get_metadata_manager()
        self._db_params = {
            "host":     settings.DB_HOST,
            "port":     settings.DB_PORT,
            "database": settings.DB_NAME,
            "user":     settings.DB_USER,
            "password": settings.DB_PASSWORD,
        }
        # URLs de la IA local — vienen del .env vía settings
        self._ai_urls: List[str] = [
            url for url in [
                settings.JDDCIA_BASE_URL_FALLBACK,  # IP directa — más fiable
                settings.JDDCIA_BASE_URL,           # mDNS — fallback
            ] if url
        ]
        # Auth header — viene del .env vía settings
        self._ai_auth = f"Basic {settings.JDDCIA_API_KEY}" if settings.JDDCIA_API_KEY else ""
        # Modelo — viene del .env si existe, si no usa el default de constants
        self._ai_model = getattr(settings, "JDDCIA_MODEL", None) or LocalAIParams.MODEL_DEFAULT

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 1: Verificar disponibilidad de la IA local
    # ─────────────────────────────────────────────────────────────────────────

    async def check_local_ai(self) -> Dict[str, Any]:
        """
        Verifica que la IA local LAN está disponible.
        EMISOR: MetadataBuilderService  RECEPTOR: Qwen3 LAN
        SEGURIDAD: Si no está disponible, bloquea todo el flujo.
        """
        _trace(MetadataBuilderLog.CHECK_AI, "Service", "Qwen3 LAN",
               f"Verificando disponibilidad en {self._ai_urls}")

        timeout = httpx.Timeout(LocalAITimeouts.READ, connect=LocalAITimeouts.CONNECT)

        for url in self._ai_urls:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(
                        f"{url}/models",
                        headers={"Authorization": self._ai_auth}
                    )
                if resp.status_code == 200:
                    _trace(MetadataBuilderLog.CHECK_AI, "Qwen3 LAN", "Service",
                           f"✅ IA disponible en {url}")
                    return {"available": True, "url": url, "model": self._ai_model}
            except Exception as exc:
                _trace(MetadataBuilderLog.CHECK_AI, "Qwen3 LAN", "Service",
                       f"❌ No responde en {url}: {exc}")

        msg = MetadataBuilderMessages.AI_NOT_AVAILABLE.format(url=self._ai_urls)
        _trace(MetadataBuilderLog.CHECK_AI, "Service", "Service", f"BLOQUEO: {msg}")
        return {"available": False, "url": None, "error": msg}

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 2: Listar tablas de la BD
    # ─────────────────────────────────────────────────────────────────────────

    def get_all_tables(self) -> Dict[str, Any]:
        """
        Lista todas las tablas de usuario de Firebird con su estado de metadatos.
        EMISOR: Service  RECEPTOR: Firebird
        """
        _trace(MetadataBuilderLog.GET_TABLES, "Service", "Firebird",
               f"Consultando tablas en {settings.DB_HOST}:{settings.DB_PORT}")

        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = DBConfig(**self._db_params)

        try:
            driver.connect(config)
            rows = driver.execute_query(QUERY_USER_TABLES)
            existing = set(self._metadata_manager.metadata.get("tables", {}).keys())

            tables = []
            for r in rows:
                name = r.get("TABLE_NAME", "").strip()
                if not name:
                    continue
                tables.append({
                    "name":         name,
                    "has_metadata": name in existing,
                    "category":     self._metadata_manager.metadata
                                    .get("tables", {}).get(name, {}).get("category", ""),
                })

            _trace(MetadataBuilderLog.GET_TABLES, "Firebird", "Service",
                   f"{len(tables)} tablas, {len(existing)} con metadatos")
            return {
                "success":       True,
                "tables":        tables,
                "total":         len(tables),
                "with_metadata": len(existing),
            }
        except Exception as exc:
            _trace(MetadataBuilderLog.GET_TABLES, "Firebird", "Service", f"ERROR: {exc}")
            return {"success": False, "error": str(exc)}
        finally:
            driver.disconnect()

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 3: Obtener estructura real de una tabla
    # ─────────────────────────────────────────────────────────────────────────

    def get_table_structure(self, table_name: str) -> Dict[str, Any]:
        """
        Obtiene columnas, tipos, PKs, FKs, conteo y muestra sin datos sensibles.
        EMISOR: Service  RECEPTOR: Firebird
        SEGURIDAD: Las columnas sensibles se excluyen de la muestra.
        """
        table_upper = table_name.upper()
        if not _validate_table_name(table_upper):
            return {"success": False, "error": f"Nombre de tabla inválido: {table_name}"}

        _trace(MetadataBuilderLog.GET_STRUCT, "Service", "Firebird",
               f"Consultando estructura de {table_upper}")

        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = DBConfig(**self._db_params)

        try:
            driver.connect(config)

            # Columnas con tipos resueltos
            col_rows = driver.execute_query(QUERY_TABLE_COLUMNS_TYPED, (table_upper,))
            pk_rows  = driver.execute_query(QUERY_TABLE_PRIMARY_KEYS,  (table_upper,))
            fk_rows  = driver.execute_query(QUERY_TABLE_FOREIGN_KEYS,  (table_upper,))

            primary_keys = [r["PK_FIELD"] for r in pk_rows]
            foreign_keys = [
                {"field": r["FK_FIELD"], "ref_table": r["REF_TABLE"], "ref_field": r["REF_FIELD"]}
                for r in fk_rows
            ]

            # Conteo de registros
            try:
                count_res    = driver.execute_query(QUERY_COUNT_TEMPLATE.format(table_name=table_upper))
                record_count = count_res[0]["C"] if count_res else 0
            except Exception:
                record_count = 0

            # Construir lista de columnas con flag de sensibilidad
            columns = []
            for r in col_rows:
                field_name = r.get("FIELD_NAME", "").strip()
                field_type = r.get("DECIMAL_TYPE") or r.get("FIELD_TYPE", "UNKNOWN")
                columns.append({
                    "name":         field_name,
                    "type":         field_type,
                    "nullable":     not r.get("NOT_NULL"),
                    "is_pk":        field_name in primary_keys,
                    "is_sensitive": field_name.upper() in PrivacyConfig.SENSITIVE_COLUMNS,
                })

            # Columnas seguras para muestra (no sensibles, no BLOB)
            safe_cols = [
                c["name"] for c in columns
                if not c["is_sensitive"] and "BLOB" not in c["type"]
            ][:PrivacyConfig.MAX_SAMPLE_COLS]

            # Muestra de datos sin datos sensibles
            sample_data = []
            if safe_cols and record_count > 0:
                try:
                    cols_sql = ", ".join(safe_cols)
                    sample_data = driver.execute_query(
                        QUERY_SAMPLE_TEMPLATE.format(
                            n=PrivacyConfig.MAX_SAMPLE_ROWS,
                            cols=cols_sql,
                            table_name=table_upper,
                        )
                    )
                except Exception as exc:
                    _trace(MetadataBuilderLog.GET_STRUCT, "Firebird", "Service",
                           f"Muestra no disponible: {exc}")

            sensitive_excluded = [c["name"] for c in columns if c["is_sensitive"]]
            _trace(MetadataBuilderLog.GET_STRUCT, "Firebird", "Service",
                   f"{table_upper}: {len(columns)} cols, {record_count} registros, "
                   f"{len(sample_data)} filas muestra, {len(sensitive_excluded)} cols sensibles excluidas")

            return {
                "success":                  True,
                "table_name":               table_upper,
                "columns":                  columns,
                "primary_keys":             primary_keys,
                "foreign_keys":             foreign_keys,
                "record_count":             record_count,
                "sample_data":              sample_data,
                "safe_columns":             safe_cols,
                "sensitive_cols_excluded":  sensitive_excluded,
            }

        except Exception as exc:
            _trace(MetadataBuilderLog.GET_STRUCT, "Firebird", "Service", f"ERROR: {exc}")
            return {"success": False, "error": str(exc)}
        finally:
            driver.disconnect()

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 4: Analizar con IA local → generar metadatos JSON
    # ─────────────────────────────────────────────────────────────────────────

    async def analyze_table_with_local_ai(
        self, table_name: str, structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Envía la estructura de la tabla a la IA local para generar metadatos.
        EMISOR: Service  RECEPTOR: Qwen3 LAN (NUNCA internet)
        DATOS ENVIADOS: nombres de columnas, tipos, PKs, muestra sin datos sensibles.
        """
        ai_check = await self.check_local_ai()
        if not ai_check["available"]:
            return {"success": False, "error": ai_check["error"]}

        working_url = ai_check["url"]
        cols        = structure.get("columns", [])[:ProcessingLimits.MAX_COLUMNS_IN_PROMPT]
        pks         = structure.get("primary_keys", [])
        fks         = structure.get("foreign_keys", [])

        # Construir descripción de columnas para el prompt
        cols_text = "\n".join(
            f"  - {c['name']}: {c['type']}"
            f"{' (PK)' if c['is_pk'] else ''}"
            f"{' [SENSIBLE]' if c['is_sensitive'] else ''}"
            for c in cols
        )

        # FK info para contexto relacional
        fk_text = ""
        if fks:
            fk_text = "\nFOREIGN KEYS:\n" + "\n".join(
                f"  - {fk['field']} → {fk['ref_table']}.{fk['ref_field']}"
                for fk in fks
            )

        # Muestra de datos (ya sin sensibles)
        sample_text = ""
        if structure.get("sample_data"):
            sample_text = (
                f"\nMuestra ({len(structure['sample_data'])} filas, sin datos sensibles):\n"
                + "\n".join(f"  {dict(r)}" for r in structure["sample_data"])
            )

        categories_str = "|".join(TableCategory.ALL)

        system_prompt = f"""Eres un experto en bases de datos Firebird y análisis de esquemas.
Genera metadatos semánticos en JSON para que una IA pueda crear consultas SQL correctas.

REGLAS:
1. Responde SOLO con el objeto JSON, sin texto adicional ni bloques markdown.
2. Estructura exacta requerida:
{{
  "category": "{categories_str}",
  "description": "descripción clara (máx {ProcessingLimits.MAX_DESCRIPTION_CHARS} chars)",
  "primary_keys": ["lista"],
  "columns": {{
    "NOMBRE": "TIPO - descripción útil (máx {ProcessingLimits.MAX_COLUMN_DESC_CHARS} chars)"
  }},
  "consultas_comunes": [
    "descripción: SELECT FIRST N ... (SQL Firebird válido, máx {ProcessingLimits.MAX_QUERIES_PER_TABLE} ejemplos)"
  ],
  "_nota_critica": "advertencia sobre errores comunes o null"
}}
3. SQL: usa FIRST N (no LIMIT), UPPER() para búsquedas de texto.
4. Omite columnas técnicas internas sin valor semántico.
5. Las descripciones deben ayudar a la IA a entender qué datos contiene cada columna."""

        user_prompt = (
            f"TABLA: {table_name}\n"
            f"REGISTROS: {structure.get('record_count', 0):,}\n"
            f"PRIMARY KEYS: {pks}\n"
            f"COLUMNAS ({len(cols)}):\n{cols_text}"
            f"{fk_text}"
            f"{sample_text}\n\n"
            "Genera el JSON de metadatos."
        )

        _trace(MetadataBuilderLog.ANALYZE_AI, "Service", f"Qwen3 LAN ({working_url})",
               f"Enviando estructura de {table_name}",
               {"cols": len(cols), "registros": structure.get("record_count"), "model": self._ai_model})

        payload = {
            "model":       self._ai_model,
            "messages":    [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "max_tokens":  LocalAIParams.MAX_TOKENS,
            "temperature": LocalAIParams.TEMPERATURE,
        }

        raw_response = ""
        try:
            timeout = httpx.Timeout(LocalAITimeouts.READ, connect=LocalAITimeouts.CONNECT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{working_url}/chat/completions",
                    headers={"Authorization": self._ai_auth, "Content-Type": "application/json"},
                    json=payload,
                )

            if resp.status_code != 200:
                raise ValueError(f"Qwen3 error {resp.status_code}: {resp.text[:300]}")

            raw_response = resp.json()["choices"][0]["message"]["content"]
            _trace(MetadataBuilderLog.ANALYZE_AI, f"Qwen3 LAN ({working_url})", "Service",
                   f"✅ Respuesta recibida para {table_name}", raw_response[:300])

            metadata_json = _parse_json_response(raw_response)
            metadata_json["record_count"] = structure.get("record_count", 0)

            return {
                "success":      True,
                "table_name":   table_name,
                "metadata":     metadata_json,
                "ai_url_used":  working_url,
                "ai_model":     self._ai_model,
            }

        except json.JSONDecodeError as exc:
            msg = MetadataBuilderMessages.INVALID_JSON.format(raw=raw_response[:200])
            _trace(MetadataBuilderLog.ANALYZE_AI, "Service", "ERROR", msg)
            return {"success": False, "error": msg, "raw_response": raw_response}
        except Exception as exc:
            _trace(MetadataBuilderLog.ANALYZE_AI, "Service", "ERROR", str(exc))
            return {"success": False, "error": str(exc)}

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 5: Guardar metadatos aprobados
    # ─────────────────────────────────────────────────────────────────────────

    def save_table_metadata(self, table_name: str, metadata: Dict) -> Dict[str, Any]:
        """
        Persiste los metadatos aprobados en db_metadata_optimized.json.
        EMISOR: Service (tras aprobación del usuario)  RECEPTOR: JSON file
        """
        _trace(MetadataBuilderLog.SAVE, "Service", "db_metadata_optimized.json",
               f"Guardando metadatos de {table_name}")
        try:
            current = self._metadata_manager.metadata
            current.setdefault("tables", {})[table_name] = metadata
            self._metadata_manager.save_metadata(current)

            total = len(current["tables"])
            _trace(MetadataBuilderLog.SAVE, "JSON", "Service",
                   f"✅ {table_name} guardada. Total tablas: {total}")
            return {
                "success":      True,
                "table_name":   table_name,
                "total_tables": total,
                "message":      MetadataBuilderMessages.METADATA_SAVED.format(table=table_name),
            }
        except Exception as exc:
            _trace(MetadataBuilderLog.SAVE, "Service", "ERROR", str(exc))
            return {"success": False, "error": str(exc)}

    # ─────────────────────────────────────────────────────────────────────────
    # FLUJO COMPLETO: Pasos 3 + 4 combinados
    # ─────────────────────────────────────────────────────────────────────────

    async def analyze_table(self, table_name: str) -> Dict[str, Any]:
        """
        Flujo completo: Firebird → Qwen3 LAN → metadatos JSON.
        EMISOR: Router  RECEPTOR: Service
        """
        _trace(MetadataBuilderLog.MODULE, "Router", "Service",
               f"Iniciando análisis completo de {table_name}")

        structure = self.get_table_structure(table_name)
        if not structure["success"]:
            return structure

        result = await self.analyze_table_with_local_ai(table_name, structure)
        result["structure"] = structure
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # UTILIDADES
    # ─────────────────────────────────────────────────────────────────────────

    def get_metadata_summary(self) -> Dict[str, Any]:
        """Resumen del estado actual de db_metadata_optimized.json."""
        tables = self._metadata_manager.metadata.get("tables", {})
        return {
            "total_tables": len(tables),
            "tables": [
                {
                    "name":         name,
                    "category":     info.get("category", ""),
                    "record_count": info.get("record_count", 0),
                    "columns":      len(info.get("columns", {})),
                    "has_queries":  bool(info.get("consultas_comunes")),
                    "has_note":     bool(info.get("_nota_critica")),
                }
                for name, info in tables.items()
            ],
        }

    def delete_table_metadata(self, table_name: str) -> Dict[str, Any]:
        """Elimina los metadatos de una tabla del JSON."""
        _trace(MetadataBuilderLog.DELETE, "Service", "db_metadata_optimized.json",
               f"Eliminando metadatos de {table_name}")
        current = self._metadata_manager.metadata
        if table_name not in current.get("tables", {}):
            return {"success": False,
                    "error": MetadataBuilderMessages.METADATA_NOT_FOUND.format(table=table_name)}
        del current["tables"][table_name]
        self._metadata_manager.save_metadata(current)
        return {"success": True,
                "message": MetadataBuilderMessages.METADATA_DELETED.format(table=table_name)}

    def get_table_metadata(self, table_name: str) -> Dict[str, Any]:
        """Obtiene los metadatos actuales de una tabla específica."""
        info = self._metadata_manager.metadata.get("tables", {}).get(table_name)
        if not info:
            return {"success": False,
                    "error": MetadataBuilderMessages.METADATA_NOT_FOUND.format(table=table_name)}
        return {"success": True, "table_name": table_name, "metadata": info}


# ─── Helpers privados ─────────────────────────────────────────────────────────

def _parse_json_response(raw: str) -> Dict:
    """
    Extrae y parsea el JSON de la respuesta de la IA.
    Maneja bloques markdown (```json ... ```) y texto extra.
    """
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    return json.loads(text)
