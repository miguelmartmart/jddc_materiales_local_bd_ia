"""
DeepIndexerService — Sistema de Indices Ultra-Optimizado (SIUO)

RESPONSABILIDAD:
  Analiza TODAS las tablas de Firebird con Qwen3 LAN y construye 4 indices
  permanentes que permiten al ChatService encontrar el contexto optimo para
  cualquier pregunta en <1ms, sin enviar todo el esquema a la IA.

INDICES GENERADOS:
  - table_index.json    : resumen ultra-compacto de cada tabla (cargado en RAM)
  - concept_index.json  : mapa concepto/keyword -> tablas relevantes
  - db_graph.json       : grafo de relaciones entre tablas (FKs + implicitas)
  - value_index.json    : valores reales de columnas clave (enumerados, rangos, top-N)
  - siuo_progress.json  : estado del proceso (permite reanudar si se interrumpe)

SEGURIDAD:
  - SOLO usa Qwen3 LAN. Ningun dato sale a internet.
  - Columnas sensibles excluidas de muestras (PrivacyConfig.SENSITIVE_COLUMNS)
  - Si la IA local no esta disponible, el proceso se cancela con error claro.

FLUJO:
  [1] check_local_ai()          -> verifica Qwen3 LAN disponible
  [2] get_all_tables()          -> lista 437 tablas de Firebird
  [3] Para cada tabla:
      [3a] get_table_structure() -> columnas, PKs, FKs, conteo
      [3b] get_column_values()   -> enumerados, rangos, top-N (sin sensibles)
      [3c] analyze_with_ai()     -> Qwen3 genera descripcion semantica
      [3d] update_indices()      -> actualiza los 4 ficheros JSON
  [4] build_graph()             -> construye grafo de relaciones completo
  [5] build_concept_index()     -> construye mapa concepto -> tablas
  [6] save_progress()           -> guarda estado final

EMISION DE PROGRESO:
  El metodo analyze_all_tables_batch() es un generador asincrono que emite
  eventos de progreso (dict) para que el router los envie via SSE al frontend.

DEPENDENCIAS:
  - MetadataBuilderService: reutiliza get_table_structure() y check_local_ai()
  - settings.py: JDDCIA_BASE_URL*, JDDCIA_API_KEY, DB_*
  - constants.py: LocalAITimeouts, PrivacyConfig, ProcessingLimits
  - firebird_metadata_queries.py: SQL de introspeccion
"""

import json
import logging
import re
import asyncio
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

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
)

logger = logging.getLogger(__name__)

# ─── Rutas de los ficheros de indices ─────────────────────────────────────────

_CONFIG_DIR = Path(__file__).parent.parent.parent / "core" / "config"

TABLE_INDEX_PATH   = _CONFIG_DIR / "table_index.json"
CONCEPT_INDEX_PATH = _CONFIG_DIR / "concept_index.json"
DB_GRAPH_PATH      = _CONFIG_DIR / "db_graph.json"
VALUE_INDEX_PATH   = _CONFIG_DIR / "value_index.json"
PROGRESS_PATH      = _CONFIG_DIR / "siuo_progress.json"

# ─── Columnas implicitas conocidas (FK implicitas por nombre) ─────────────────

# Si una columna se llama igual en dos tablas y no es sensible, es probable FK
IMPLICIT_FK_PATTERNS = {
    "CODART":    "ARTICULO",
    "CODCLI":    "CLIENTE",
    "CODPRO":    "PROVEED",
    "NUMDOC":    "DOCCAB",
    "CODALM":    "ALMACEN",
    "CODAGENTE": "AGENTES",
    "CODFAM":    "FAMILIAS",
    "CODTARIFA": "TARIFAS",
    "CODIVA":    "TIPOSIVA",
    "CODPAIS":   "PAISES",
    "CODPROV":   "PROVINCIAS",
    "CODPOBLACION": "POBLACIONES",
}

# ─── Concepto base (reglas manuales que siempre se aplican) ───────────────────
# IMPORTANTE: Cuando se añaden conceptos aquí, regenerar concept_index.json
# ejecutando: POST /api/siuo/reload  (recarga sin re-indexar)
# Para regenerar completamente: POST /api/siuo/analyze/start?resume=false

BASE_CONCEPT_INDEX = {
    # ── Artículos / Productos ──────────────────────────────────────────────────
    "articulo":    [{"table": "ARTICULO"}],
    "producto":    [{"table": "ARTICULO"}],
    "referencia":  [{"table": "ARTICULO"}],
    "split":       [{"table": "ARTICULO"}],
    "equipo":      [{"table": "ARTICULO"}],
    "material":    [{"table": "ARTICULO"}],
    "recambio":    [{"table": "ARTICULO"}],
    "gas":         [{"table": "ARTICULO"}, {"table": "DOCLIN"}],
    "refrigerante":[{"table": "ARTICULO"}],
    "familia":     [{"table": "ARTICULO"}, {"table": "FAMILIAS"}],
    "categoria":   [{"table": "ARTICULO"}, {"table": "FAMILIAS"}],
    "precio":      [{"table": "ARTICULO"}, {"table": "DOCLIN"}],
    "coste":       [{"table": "ARTICULO"}, {"table": "DOCLIN"}],
    "margen":      [{"table": "ARTICULO"}, {"table": "DOCLIN"}],
    "stock":       [{"table": "ARTICULO"}, {"table": "ALMACEN"}, {"table": "ESTALMACEN"}],
    "inventario":  [{"table": "ARTICULO"}, {"table": "ESTALMACEN"}],
    "existencias": [{"table": "ARTICULO"}, {"table": "ESTALMACEN"}],

    # ── Documentos (DOCCAB + DOCLIN) ──────────────────────────────────────────
    "factura":     [{"table": "DOCCAB", "filter": "TIPO=13"}, {"table": "DOCLIN"}],
    "albaran":     [{"table": "DOCCAB", "filter": "TIPO=11"}, {"table": "DOCLIN"}],
    "pedido":      [{"table": "DOCCAB", "filter": "TIPO=12"}, {"table": "DOCLIN"}],
    "presupuesto": [{"table": "DOCCAB", "filter": "TIPO=0"},  {"table": "DOCLIN"}],
    "abono":       [{"table": "DOCCAB", "filter": "TIPO=3"},  {"table": "DOCLIN"}],
    "contrato":    [{"table": "DOCCAB", "filter": "TIPO=10"}, {"table": "DOCLIN"}],
    "sat":         [{"table": "DOCCAB", "filter": "TIPO=2"},  {"table": "DOCLIN"}],
    "instalacion": [{"table": "DOCCAB", "filter": "TIPO=2"},  {"table": "DOCLIN"}],
    "mantenimiento":[{"table": "DOCCAB", "filter": "TIPO=10"},{"table": "DOCLIN"}],
    "recibo":      [{"table": "DOCCAB", "filter": "TIPO=61"}],
    "documento":   [{"table": "DOCCAB"}, {"table": "DOCLIN"}],
    "linea":       [{"table": "DOCLIN"}, {"table": "DOCCAB"}],
    "detalle":     [{"table": "DOCLIN"}, {"table": "DOCCAB"}],
    "cantidad":    [{"table": "DOCLIN"}],
    "importe":     [{"table": "DOCLIN"}, {"table": "DOCCAB"}],
    "total":       [{"table": "DOCCAB"}, {"table": "DOCLIN"}],

    # ── Ventas / Compras — CRÍTICO: incluir DOCLIN para poder calcular ─────────
    "venta":       [{"table": "DOCCAB", "filter": "TIPO IN (11,13)"}, {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "vendido":     [{"table": "DOCCAB", "filter": "TIPO IN (11,13)"}, {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "compra":      [{"table": "DOCCAB", "filter": "TIPO=12"},          {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "comprado":    [{"table": "DOCCAB", "filter": "TIPO=12"},          {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "facturado":   [{"table": "DOCCAB", "filter": "TIPO=13"},          {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "ranking":     [{"table": "DOCCAB"}, {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "mas vendido": [{"table": "DOCCAB", "filter": "TIPO IN (11,13)"}, {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "mas comprado":[{"table": "DOCCAB", "filter": "TIPO=12"},          {"table": "DOCLIN"}, {"table": "ARTICULO"}],
    "movimiento":  [{"table": "DOCCAB"}, {"table": "DOCLIN"}, {"table": "ARTICULO"}],

    # ── Entidades ──────────────────────────────────────────────────────────────
    "cliente":     [{"table": "CLIENTE"}],
    "proveedor":   [{"table": "PROVEED"}],
    "agente":      [{"table": "AGENTE"}],
    "comercial":   [{"table": "AGENTE"}],
    "empleado":    [{"table": "EMPLEADOS"}],
    "tecnico":     [{"table": "EMPLEADOS"}],

    # ── Almacén / Logística ────────────────────────────────────────────────────
    "almacen":     [{"table": "ALMACEN"}, {"table": "ESTALMACEN"}],
    "deposito":    [{"table": "ALMACEN"}, {"table": "ESTALMACEN"}],

    # ── Financiero ─────────────────────────────────────────────────────────────
    "caja":        [{"table": "CAJA"}],
    "cobro":       [{"table": "CAJA"}, {"table": "DOCCAB"}],
    "pago":        [{"table": "CAJA"}, {"table": "DOCCAB"}],
    "impago":      [{"table": "DOCCAB"}, {"table": "CAJA"}],
    "deuda":       [{"table": "DOCCAB"}, {"table": "CAJA"}],
    "banco":       [{"table": "BANCOS"}],
    "forma pago":  [{"table": "FORMASPAGO"}],
    "iva":         [{"table": "TIPOSIVA"}, {"table": "DOCCAB"}],
    "tarifa":      [{"table": "TARIFAS"}],

    # ── Otros ──────────────────────────────────────────────────────────────────
    "aviso":       [{"table": "AVISOS"}],
    "serie":       [{"table": "SERIES"}],
    "comision":    [{"table": "AGENTE"}, {"table": "DOCCAB"}],
}


# ─── Servicio principal ───────────────────────────────────────────────────────

class DeepIndexerService:
    """
    Construye y mantiene el Sistema de Indices Ultra-Optimizado (SIUO).

    Uso tipico:
        service = DeepIndexerService()
        async for event in service.analyze_all_tables_batch():
            # event es un dict con: type, table, progress, message, error
            yield event  # enviar via SSE al frontend
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
        self._ai_urls: List[str] = [
            url for url in [
                settings.JDDCIA_BASE_URL_FALLBACK,
                settings.JDDCIA_BASE_URL,
            ] if url
        ]
        self._ai_auth  = f"Basic {settings.JDDCIA_API_KEY}" if settings.JDDCIA_API_KEY else ""
        self._ai_model = getattr(settings, "JDDCIA_MODEL", None) or LocalAIParams.MODEL_DEFAULT
        self._working_url: Optional[str] = None

        # Indices en memoria (se cargan/actualizan durante el proceso)
        self._table_index:   Dict = {}
        self._concept_index: Dict = {}
        self._graph_nodes:   Dict = {}
        self._graph_edges:   List = []
        self._value_index:   Dict = {"enums": {}, "ranges": {}, "top_values": {}}
        self._progress:      Dict = {}

    # ─────────────────────────────────────────────────────────────────────────
    # PUNTO DE ENTRADA PRINCIPAL: analisis por batches con progreso SSE
    # ─────────────────────────────────────────────────────────────────────────

    async def analyze_all_tables_batch(
        self,
        batch_size: int = 5,
        resume: bool = True,
    ) -> AsyncGenerator[Dict, None]:
        """
        Analiza todas las tablas de Firebird en batches.
        Es un generador asincrono que emite eventos de progreso para SSE.

        Eventos emitidos:
          {"type": "start",    "total": N, "message": "..."}
          {"type": "progress", "table": "X", "done": N, "total": M, "status": "ok"|"error", "message": "..."}
          {"type": "phase",    "phase": "graph"|"concepts"|"values", "message": "..."}
          {"type": "complete", "done": N, "failed": K, "message": "..."}
          {"type": "error",    "message": "..."}
        """
        # 1. Verificar IA local
        ai_check = await self._check_local_ai()
        if not ai_check["available"]:
            yield {"type": "error", "message": f"IA local no disponible: {ai_check.get('error')}"}
            return

        self._working_url = ai_check["url"]

        # 2. Cargar indices existentes (para reanudar)
        self._load_all_indices()

        # 3. Obtener lista de tablas
        all_tables = self._get_all_table_names()
        if not all_tables:
            yield {"type": "error", "message": "No se pudieron obtener las tablas de Firebird"}
            return

        # 4. Determinar tablas pendientes (si resume=True, saltar las ya analizadas)
        analyzed_set: Set[str] = set(self._table_index.keys())
        if resume:
            pending = [t for t in all_tables if t not in analyzed_set]
        else:
            pending = list(all_tables)
            self._table_index   = {}
            self._graph_nodes   = {}
            self._graph_edges   = []
            self._value_index   = {"enums": {}, "ranges": {}, "top_values": {}}

        total   = len(all_tables)
        done    = len(analyzed_set) if resume else 0
        failed  = []

        # Inicializar progreso
        self._progress = {
            "version":      "1.0",
            "started":      datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "total_tables": total,
            "analyzed":     done,
            "failed":       0,
            "pending":      len(pending),
            "failed_tables": [],
            "status":       "running",
        }
        self._save_progress()

        yield {
            "type":    "start",
            "total":   total,
            "pending": len(pending),
            "already": done,
            "message": f"Iniciando analisis: {len(pending)} tablas pendientes de {total} totales",
        }

        # 5. Procesar en batches
        for i in range(0, len(pending), batch_size):
            batch = pending[i: i + batch_size]

            for table_name in batch:
                try:
                    result = await self._analyze_table_deep(table_name)
                    if result["success"]:
                        self._update_indices(table_name, result)
                        done += 1
                        yield {
                            "type":    "progress",
                            "table":   table_name,
                            "done":    done,
                            "total":   total,
                            "status":  "ok",
                            "message": f"[{done}/{total}] {table_name} — {result.get('record_count', 0):,} registros",
                        }
                    else:
                        failed.append(table_name)
                        yield {
                            "type":    "progress",
                            "table":   table_name,
                            "done":    done,
                            "total":   total,
                            "status":  "error",
                            "message": f"[ERROR] {table_name}: {result.get('error', 'desconocido')}",
                        }
                except Exception as exc:
                    failed.append(table_name)
                    yield {
                        "type":    "progress",
                        "table":   table_name,
                        "done":    done,
                        "total":   total,
                        "status":  "error",
                        "message": f"[EXCEPCION] {table_name}: {str(exc)[:200]}",
                    }

                # Guardar progreso parcial cada tabla
                self._progress.update({
                    "last_updated": datetime.now().isoformat(),
                    "analyzed":     done,
                    "failed":       len(failed),
                    "pending":      total - done - len(failed),
                    "failed_tables": failed,
                })
                self._save_progress()
                self._save_table_index()

                # Pequena pausa para no saturar Qwen3
                await asyncio.sleep(0.5)

        # 6. Construir grafo de relaciones
        yield {"type": "phase", "phase": "graph", "message": "Construyendo grafo de relaciones..."}
        self._build_graph()
        self._save_graph()

        # 7. Construir indice de conceptos
        yield {"type": "phase", "phase": "concepts", "message": "Construyendo indice de conceptos..."}
        self._build_concept_index()
        self._save_concept_index()

        # 8. Guardar indice de valores
        yield {"type": "phase", "phase": "values", "message": "Guardando indice de valores..."}
        self._save_value_index()

        # 9. Guardar metadatos completos en db_metadata_optimized.json
        self._flush_to_metadata_optimized()

        # 10. Estado final
        self._progress.update({
            "last_updated": datetime.now().isoformat(),
            "analyzed":     done,
            "failed":       len(failed),
            "pending":      0,
            "failed_tables": failed,
            "status":       "completed",
        })
        self._save_progress()

        yield {
            "type":    "complete",
            "done":    done,
            "failed":  len(failed),
            "message": f"Analisis completado: {done} tablas OK, {len(failed)} errores",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ANALISIS PROFUNDO DE UNA TABLA
    # ─────────────────────────────────────────────────────────────────────────

    async def _analyze_table_deep(self, table_name: str) -> Dict[str, Any]:
        """
        Analiza una tabla en profundidad:
          Paso 1: estructura (columnas, PKs, FKs)
          Paso 2: valores de columnas clave (enumerados, rangos, top-N)
          Paso 3: enviar a Qwen3 para descripcion semantica
          Paso 4: construir entrada del table_index
        """
        table_upper = table_name.upper()
        logger.info(f"[SIUO] Analizando {table_upper}...")

        # Paso 1: estructura
        structure = self._get_table_structure(table_upper)
        if not structure["success"]:
            return structure

        # Paso 2: valores de columnas clave
        col_values = self._get_column_values(table_upper, structure)

        # Paso 3: descripcion semantica con Qwen3
        ai_result = await self._ask_ai_for_description(table_upper, structure, col_values)

        # Paso 4: construir entrada del table_index
        cols_key = self._extract_key_columns(structure)
        related  = self._extract_related_tables(structure)
        keywords = self._extract_keywords(table_upper, structure, ai_result)

        entry = {
            "cat":      ai_result.get("category", "otros"),
            "desc":     ai_result.get("description", f"Tabla {table_upper}"),
            "n":        structure.get("record_count", 0),
            "pk":       structure.get("primary_keys", []),
            "cols_key": cols_key,
            "related":  related,
            "kw":       keywords,
            "fks":      structure.get("foreign_keys", []),
            "cols_all": [c["name"] for c in structure.get("columns", [])],
            "note":     ai_result.get("_nota_critica"),
            "queries":  ai_result.get("consultas_comunes", []),
        }

        # Actualizar value_index con los valores encontrados
        if col_values:
            for col_name, values in col_values.items():
                full_key = f"{table_upper}.{col_name}"
                if values.get("type") == "enum":
                    self._value_index["enums"][full_key] = values.get("values", {})
                elif values.get("type") == "range":
                    self._value_index["ranges"][full_key] = {
                        "min": values.get("min"),
                        "max": values.get("max"),
                        "avg": values.get("avg"),
                    }
                elif values.get("type") == "top_n":
                    self._value_index["top_values"][full_key] = values.get("top", [])

        return {
            "success":      True,
            "table_name":   table_upper,
            "entry":        entry,
            "record_count": structure.get("record_count", 0),
            "ai_desc":      ai_result.get("description", ""),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRUCTURA DE TABLA (reutiliza logica de MetadataBuilderService)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_table_structure(self, table_name: str) -> Dict[str, Any]:
        """Obtiene columnas, PKs, FKs, conteo de registros."""
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = DBConfig(**self._db_params)
        try:
            driver.connect(config)
            col_rows = driver.execute_query(QUERY_TABLE_COLUMNS_TYPED, (table_name,))
            pk_rows  = driver.execute_query(QUERY_TABLE_PRIMARY_KEYS,  (table_name,))
            fk_rows  = driver.execute_query(QUERY_TABLE_FOREIGN_KEYS,  (table_name,))

            primary_keys = [r["PK_FIELD"] for r in pk_rows]
            foreign_keys = [
                {"field": r["FK_FIELD"], "ref_table": r["REF_TABLE"], "ref_field": r["REF_FIELD"]}
                for r in fk_rows
            ]

            try:
                count_res    = driver.execute_query(QUERY_COUNT_TEMPLATE.format(table_name=table_name))
                record_count = count_res[0]["C"] if count_res else 0
            except Exception:
                record_count = 0

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

            return {
                "success":      True,
                "table_name":   table_name,
                "columns":      columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "record_count": record_count,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            driver.disconnect()

    # ─────────────────────────────────────────────────────────────────────────
    # VALORES DE COLUMNAS CLAVE
    # ─────────────────────────────────────────────────────────────────────────

    def _get_column_values(self, table_name: str, structure: Dict) -> Dict[str, Any]:
        """
        Obtiene valores reales de columnas clave:
        - Columnas INTEGER/SMALLINT con pocos valores distintos -> enumerado
        - Columnas DATE/TIMESTAMP -> rango min/max
        - Columnas numericas (PRECIO, TOTAL, IMPORTE) -> min/max/avg
        - Columnas de texto clave (FAMILIA, TIPO, ESTADO) -> top-N valores
        """
        if structure.get("record_count", 0) == 0:
            return {}

        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = DBConfig(**self._db_params)
        result = {}

        try:
            driver.connect(config)
            columns = structure.get("columns", [])

            for col in columns:
                col_name = col["name"]
                col_type = col.get("type", "")

                # Saltar columnas sensibles y BLOBs
                if col["is_sensitive"] or "BLOB" in col_type:
                    continue

                try:
                    # Columnas de fecha -> rango
                    if any(t in col_type for t in ["DATE", "TIMESTAMP", "TIME"]):
                        rows = driver.execute_query(
                            f"SELECT MIN({col_name}) as MINV, MAX({col_name}) as MAXV "
                            f"FROM {table_name}"
                        )
                        if rows and rows[0]["MINV"] is not None:
                            result[col_name] = {
                                "type": "range",
                                "min":  str(rows[0]["MINV"]),
                                "max":  str(rows[0]["MAXV"]),
                            }

                    # Columnas numericas de importe/precio -> rango + avg
                    elif any(kw in col_name.upper() for kw in
                             ["PRECIO", "TOTAL", "IMPORTE", "BASE", "IVA", "DESCUENTO"]):
                        rows = driver.execute_query(
                            f"SELECT MIN({col_name}) as MINV, MAX({col_name}) as MAXV, "
                            f"AVG({col_name}) as AVGV FROM {table_name}"
                        )
                        if rows and rows[0]["MINV"] is not None:
                            result[col_name] = {
                                "type": "range",
                                "min":  float(rows[0]["MINV"] or 0),
                                "max":  float(rows[0]["MAXV"] or 0),
                                "avg":  round(float(rows[0]["AVGV"] or 0), 2),
                            }

                    # Columnas INTEGER/SMALLINT con nombre TIPO, ESTADO, etc. -> enumerado
                    elif any(t in col_type for t in ["INTEGER", "SMALLINT"]) and \
                         any(kw in col_name.upper() for kw in
                             ["TIPO", "ESTADO", "CLASE", "GRUPO", "MODO", "FLAG"]):
                        rows = driver.execute_query(
                            f"SELECT FIRST 30 {col_name} as VAL, COUNT(*) as CNT "
                            f"FROM {table_name} WHERE {col_name} IS NOT NULL "
                            f"GROUP BY {col_name} ORDER BY CNT DESC"
                        )
                        if rows and len(rows) <= 25:  # Solo si hay pocos valores distintos
                            result[col_name] = {
                                "type":   "enum",
                                "values": {str(r["VAL"]): r["CNT"] for r in rows},
                            }

                    # Columnas VARCHAR clave (FAMILIA, CATEGORIA, PROVINCIA) -> top-N
                    elif "VARCHAR" in col_type and \
                         any(kw in col_name.upper() for kw in
                             ["FAMILIA", "CATEGORIA", "PROVINCIA", "PAIS", "GRUPO",
                              "CLASE", "SECCION", "DEPARTAMENTO"]):
                        rows = driver.execute_query(
                            f"SELECT FIRST 20 TRIM({col_name}) as VAL, COUNT(*) as CNT "
                            f"FROM {table_name} WHERE {col_name} IS NOT NULL "
                            f"AND TRIM({col_name}) <> '' "
                            f"GROUP BY TRIM({col_name}) ORDER BY CNT DESC"
                        )
                        if rows:
                            result[col_name] = {
                                "type": "top_n",
                                "top":  [{"val": r["VAL"], "count": r["CNT"]} for r in rows],
                            }

                except Exception:
                    pass  # Si falla una columna, continuar con las demas

        except Exception as exc:
            logger.warning(f"[SIUO] Error obteniendo valores de {table_name}: {exc}")
        finally:
            driver.disconnect()

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # DESCRIPCION SEMANTICA CON QWEN3
    # ─────────────────────────────────────────────────────────────────────────

    async def _ask_ai_for_description(
        self,
        table_name: str,
        structure: Dict,
        col_values: Dict,
    ) -> Dict[str, Any]:
        """
        Envia la estructura de la tabla a Qwen3 LAN para obtener descripcion semantica.
        Si Qwen3 falla, devuelve un resultado minimo generado localmente.
        """
        if not self._working_url:
            return self._fallback_description(table_name, structure)

        cols = structure.get("columns", [])[:ProcessingLimits.MAX_COLUMNS_IN_PROMPT]
        pks  = structure.get("primary_keys", [])
        fks  = structure.get("foreign_keys", [])

        cols_text = "\n".join(
            f"  - {c['name']}: {c['type']}"
            f"{' (PK)' if c['is_pk'] else ''}"
            f"{' [SENSIBLE]' if c['is_sensitive'] else ''}"
            for c in cols
        )

        fk_text = ""
        if fks:
            fk_text = "\nFOREIGN KEYS:\n" + "\n".join(
                f"  - {fk['field']} -> {fk['ref_table']}.{fk['ref_field']}"
                for fk in fks
            )

        values_text = ""
        if col_values:
            parts = []
            for col_name, info in list(col_values.items())[:5]:
                if info["type"] == "enum":
                    vals = list(info["values"].keys())[:10]
                    parts.append(f"  - {col_name}: valores={vals}")
                elif info["type"] == "range":
                    parts.append(f"  - {col_name}: min={info.get('min')}, max={info.get('max')}")
                elif info["type"] == "top_n":
                    top = [v["val"] for v in info["top"][:5]]
                    parts.append(f"  - {col_name}: top={top}")
            if parts:
                values_text = "\nVALORES REALES:\n" + "\n".join(parts)

        categories_str = "|".join(TableCategory.ALL)

        system_prompt = (
            "Eres un experto en bases de datos Firebird de una empresa de climatizacion "
            "(aire acondicionado, splits, gas refrigerante).\n"
            "Genera metadatos JSON para que una IA pueda crear consultas SQL correctas.\n\n"
            "REGLAS:\n"
            "1. Responde SOLO con el objeto JSON, sin texto adicional ni bloques markdown.\n"
            f"2. Estructura exacta:\n"
            "{\n"
            f'  "category": "{categories_str}",\n'
            '  "description": "descripcion clara en espanol (max 200 chars)",\n'
            '  "keywords": ["lista", "de", "palabras", "clave", "en", "espanol"],\n'
            '  "consultas_comunes": ["SELECT FIRST 5 ... (SQL Firebird valido)"],\n'
            '  "_nota_critica": "advertencia sobre errores comunes o null"\n'
            "}\n"
            "3. SQL: usa FIRST N (no LIMIT), UPPER() para busquedas de texto.\n"
            "4. keywords: palabras en espanol que un usuario usaria para preguntar sobre esta tabla.\n"
            "5. Si no hay nota critica, pon null."
        )

        user_prompt = (
            f"TABLA: {table_name}\n"
            f"REGISTROS: {structure.get('record_count', 0):,}\n"
            f"PRIMARY KEYS: {pks}\n"
            f"COLUMNAS ({len(cols)}):\n{cols_text}"
            f"{fk_text}"
            f"{values_text}\n\n"
            "Genera el JSON de metadatos."
        )

        payload = {
            "model":       self._ai_model,
            "messages":    [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "max_tokens":  LocalAIParams.MAX_TOKENS,
            "temperature": LocalAIParams.TEMPERATURE,
        }

        try:
            timeout = httpx.Timeout(LocalAITimeouts.READ, connect=LocalAITimeouts.CONNECT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self._working_url}/chat/completions",
                    headers={
                        "Authorization": self._ai_auth,
                        "Content-Type":  "application/json",
                    },
                    json=payload,
                )

            if resp.status_code != 200:
                logger.warning(f"[SIUO] Qwen3 error {resp.status_code} para {table_name}")
                return self._fallback_description(table_name, structure)

            raw = resp.json()["choices"][0]["message"]["content"]
            return _parse_json_response(raw)

        except Exception as exc:
            logger.warning(f"[SIUO] Qwen3 fallo para {table_name}: {exc}")
            return self._fallback_description(table_name, structure)

    def _fallback_description(self, table_name: str, structure: Dict) -> Dict[str, Any]:
        """Descripcion minima generada localmente si Qwen3 no esta disponible."""
        return {
            "category":         "otros",
            "description":      f"Tabla {table_name} ({structure.get('record_count', 0):,} registros)",
            "keywords":         [table_name.lower()],
            "consultas_comunes": [f"SELECT FIRST 10 * FROM {table_name}"],
            "_nota_critica":    None,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # CONSTRUCCION DE INDICES
    # ─────────────────────────────────────────────────────────────────────────

    def _update_indices(self, table_name: str, result: Dict) -> None:
        """Actualiza table_index y graph_nodes con el resultado del analisis."""
        entry = result["entry"]
        self._table_index[table_name] = entry

        # Actualizar nodos del grafo
        self._graph_nodes[table_name] = {
            "n_records": result.get("record_count", 0),
            "category":  entry.get("cat", "otros"),
            "desc":      entry.get("desc", ""),
        }

    def _build_graph(self) -> None:
        """
        Construye el grafo de relaciones entre tablas.
        Combina FKs explicitas (de Firebird) con FKs implicitas (por nombre de columna).
        """
        edges_set = set()  # Para evitar duplicados
        self._graph_edges = []

        for table_name, entry in self._table_index.items():
            # FKs explicitas
            for fk in entry.get("fks", []):
                key = (table_name, fk["field"], fk["ref_table"], fk["ref_field"])
                if key not in edges_set:
                    edges_set.add(key)
                    self._graph_edges.append({
                        "from":      table_name,
                        "from_col":  fk["field"],
                        "to":        fk["ref_table"],
                        "to_col":    fk["ref_field"],
                        "type":      "fk_explicit",
                        "weight":    entry.get("n", 0),
                    })

            # FKs implicitas (por nombre de columna)
            for col_name in entry.get("cols_all", []):
                col_upper = col_name.upper()
                if col_upper in IMPLICIT_FK_PATTERNS:
                    ref_table = IMPLICIT_FK_PATTERNS[col_upper]
                    if ref_table != table_name and ref_table in self._table_index:
                        key = (table_name, col_name, ref_table, col_name)
                        if key not in edges_set:
                            edges_set.add(key)
                            self._graph_edges.append({
                                "from":      table_name,
                                "from_col":  col_name,
                                "to":        ref_table,
                                "to_col":    col_name,
                                "type":      "fk_implicit",
                                "weight":    entry.get("n", 0),
                            })

        # Calcular caminos mas cortos entre tablas importantes
        paths = self._compute_shortest_paths()

        # Guardar grafo completo
        self._graph_data = {
            "version":  "1.0",
            "generated": datetime.now().isoformat(),
            "nodes":    self._graph_nodes,
            "edges":    self._graph_edges,
            "paths":    paths,
        }

    def _compute_shortest_paths(self) -> Dict[str, List[str]]:
        """
        Calcula caminos mas cortos entre tablas importantes usando BFS.
        Solo calcula para las tablas con mas registros (las mas relevantes).
        """
        # Construir lista de adyacencia
        adj: Dict[str, Set[str]] = defaultdict(set)
        for edge in self._graph_edges:
            adj[edge["from"]].add(edge["to"])
            adj[edge["to"]].add(edge["from"])  # Grafo no dirigido para BFS

        # Tablas importantes (las que tienen mas registros)
        important = sorted(
            self._graph_nodes.items(),
            key=lambda x: x[1].get("n_records", 0),
            reverse=True
        )[:20]
        important_names = [t[0] for t in important]

        paths = {}
        for i, src in enumerate(important_names):
            for dst in important_names[i+1:]:
                path = self._bfs_path(adj, src, dst)
                if path and len(path) <= 5:  # Solo caminos cortos
                    key = f"{src}->{dst}"
                    paths[key] = path

        return paths

    def _bfs_path(self, adj: Dict, src: str, dst: str) -> Optional[List[str]]:
        """BFS para encontrar el camino mas corto entre dos tablas."""
        if src not in adj or dst not in adj:
            return None
        visited = {src}
        queue   = deque([[src]])
        while queue:
            path = queue.popleft()
            node = path[-1]
            if node == dst:
                return path
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def _build_concept_index(self) -> None:
        """
        Construye el indice de conceptos combinando:
        1. Reglas manuales base (BASE_CONCEPT_INDEX)
        2. Keywords generados por Qwen3 para cada tabla
        """
        index: Dict[str, List] = {}

        # 1. Reglas manuales base
        for concept, tables in BASE_CONCEPT_INDEX.items():
            index[concept] = list(tables)

        # 2. Keywords de Qwen3
        for table_name, entry in self._table_index.items():
            for kw in entry.get("kw", []):
                kw_lower = kw.lower().strip()
                if not kw_lower:
                    continue
                if kw_lower not in index:
                    index[kw_lower] = []
                # Anadir si no esta ya
                table_entry = {"table": table_name}
                if table_entry not in index[kw_lower]:
                    index[kw_lower].append(table_entry)

        self._concept_index = {
            "version":   "1.0",
            "generated": datetime.now().isoformat(),
            "index":     index,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_key_columns(self, structure: Dict) -> List[str]:
        """Extrae las columnas mas importantes de una tabla."""
        pks  = set(structure.get("primary_keys", []))
        cols = structure.get("columns", [])
        key_cols = []

        # Primero PKs
        for c in cols:
            if c["name"] in pks and not c["is_sensitive"]:
                key_cols.append(c["name"])

        # Luego columnas con nombres importantes
        important_patterns = [
            "NOMBRE", "DESCRIPCION", "CODIGO", "FECHA", "TOTAL", "IMPORTE",
            "ESTADO", "TIPO", "FAMILIA", "PRECIO", "CANTIDAD", "STOCK",
            "RAZONSOCIAL", "REFERENCIA", "SERIE", "NUMERO",
        ]
        for pattern in important_patterns:
            for c in cols:
                if pattern in c["name"].upper() and not c["is_sensitive"] and c["name"] not in key_cols:
                    key_cols.append(c["name"])
                    if len(key_cols) >= 8:
                        break
            if len(key_cols) >= 8:
                break

        return key_cols[:8]

    def _extract_related_tables(self, structure: Dict) -> List[str]:
        """Extrae tablas relacionadas via FKs explicitas e implicitas."""
        related = set()

        # FKs explicitas
        for fk in structure.get("foreign_keys", []):
            related.add(fk["ref_table"])

        # FKs implicitas por nombre de columna
        for col in structure.get("columns", []):
            col_upper = col["name"].upper()
            if col_upper in IMPLICIT_FK_PATTERNS:
                related.add(IMPLICIT_FK_PATTERNS[col_upper])

        return list(related)

    def _extract_keywords(
        self, table_name: str, structure: Dict, ai_result: Dict
    ) -> List[str]:
        """Combina keywords del nombre de tabla + columnas + Qwen3."""
        kws = set()

        # Del nombre de la tabla
        kws.add(table_name.lower())

        # De Qwen3
        for kw in ai_result.get("keywords", []):
            kws.add(kw.lower().strip())

        # De columnas importantes
        for col in structure.get("columns", [])[:15]:
            col_name = col["name"].lower()
            if len(col_name) > 3 and not col["is_sensitive"]:
                kws.add(col_name)

        return sorted(kws)[:20]

    def _get_all_table_names(self) -> List[str]:
        """Obtiene la lista de todas las tablas de usuario de Firebird."""
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = DBConfig(**self._db_params)
        try:
            driver.connect(config)
            rows = driver.execute_query(QUERY_USER_TABLES)
            return [r.get("TABLE_NAME", "").strip() for r in rows if r.get("TABLE_NAME", "").strip()]
        except Exception as exc:
            logger.error(f"[SIUO] Error obteniendo tablas: {exc}")
            return []
        finally:
            driver.disconnect()

    async def _check_local_ai(self) -> Dict[str, Any]:
        """Verifica que Qwen3 LAN esta disponible."""
        timeout = httpx.Timeout(LocalAITimeouts.READ, connect=LocalAITimeouts.CONNECT)
        for url in self._ai_urls:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(
                        f"{url}/models",
                        headers={"Authorization": self._ai_auth}
                    )
                if resp.status_code == 200:
                    return {"available": True, "url": url, "model": self._ai_model}
            except Exception:
                pass
        return {"available": False, "error": "Qwen3 LAN no responde en ninguna URL"}

    # ─────────────────────────────────────────────────────────────────────────
    # PERSISTENCIA
    # ─────────────────────────────────────────────────────────────────────────

    def _load_all_indices(self) -> None:
        """Carga todos los indices existentes en memoria."""
        self._table_index   = _load_json(TABLE_INDEX_PATH,   {}).get("tables", {})
        self._concept_index = _load_json(CONCEPT_INDEX_PATH, {})
        graph               = _load_json(DB_GRAPH_PATH,      {})
        self._graph_nodes   = graph.get("nodes", {})
        self._graph_edges   = graph.get("edges", [])
        self._value_index   = _load_json(VALUE_INDEX_PATH,   {"enums": {}, "ranges": {}, "top_values": {}})
        self._progress      = _load_json(PROGRESS_PATH,      {})

    def _save_table_index(self) -> None:
        _save_json(TABLE_INDEX_PATH, {
            "version":   "1.0",
            "generated": datetime.now().isoformat(),
            "tables":    self._table_index,
        })

    def _save_graph(self) -> None:
        _save_json(DB_GRAPH_PATH, getattr(self, "_graph_data", {
            "version":  "1.0",
            "generated": datetime.now().isoformat(),
            "nodes":    self._graph_nodes,
            "edges":    self._graph_edges,
            "paths":    {},
        }))

    def _save_concept_index(self) -> None:
        _save_json(CONCEPT_INDEX_PATH, self._concept_index)

    def _save_value_index(self) -> None:
        _save_json(VALUE_INDEX_PATH, {
            "version":   "1.0",
            "generated": datetime.now().isoformat(),
            **self._value_index,
        })

    def _save_progress(self) -> None:
        _save_json(PROGRESS_PATH, self._progress)

    def _flush_to_metadata_optimized(self) -> None:
        """
        Sincroniza los metadatos del SIUO con db_metadata_optimized.json
        para que el ChatService (v1) siga funcionando mientras se implementa v2.
        """
        current = self._metadata_manager.metadata
        tables  = current.setdefault("tables", {})

        for table_name, entry in self._table_index.items():
            if table_name not in tables:
                # Solo anadir tablas nuevas, no sobreescribir las ya aprobadas manualmente
                tables[table_name] = {
                    "category":        entry.get("cat", "otros"),
                    "description":     entry.get("desc", ""),
                    "primary_keys":    entry.get("pk", []),
                    "columns":         {c: c for c in entry.get("cols_key", [])},
                    "consultas_comunes": entry.get("queries", []),
                    "record_count":    entry.get("n", 0),
                    "_nota_critica":   entry.get("note"),
                    "_siuo_generated": True,
                }

        self._metadata_manager.save_metadata(current)

    # ─────────────────────────────────────────────────────────────────────────
    # API PUBLICA: estado del progreso
    # ─────────────────────────────────────────────────────────────────────────

    def get_progress(self) -> Dict[str, Any]:
        """Devuelve el estado actual del proceso de indexacion."""
        return _load_json(PROGRESS_PATH, {
            "status":       "not_started",
            "total_tables": 0,
            "analyzed":     0,
            "failed":       0,
            "pending":      0,
        })

    def get_index_stats(self) -> Dict[str, Any]:
        """Devuelve estadisticas de los indices actuales."""
        table_index = _load_json(TABLE_INDEX_PATH, {}).get("tables", {})
        graph       = _load_json(DB_GRAPH_PATH,    {})
        concept     = _load_json(CONCEPT_INDEX_PATH, {}).get("index", {})
        value       = _load_json(VALUE_INDEX_PATH,  {})

        return {
            "tables_indexed":   len(table_index),
            "graph_nodes":      len(graph.get("nodes", {})),
            "graph_edges":      len(graph.get("edges", [])),
            "concept_keywords": len(concept),
            "enums_indexed":    len(value.get("enums", {})),
            "ranges_indexed":   len(value.get("ranges", {})),
            "top_values":       len(value.get("top_values", {})),
        }


# ─── Helpers de ficheros ──────────────────────────────────────────────────────

def _load_json(path: Path, default: Any) -> Any:
    """
    Carga un fichero JSON de forma robusta.

    Estrategia de recuperacion ante corrupcion:
    1. Intento normal: open + json.load (utf-8)
    2. Si falla: leer bytes, buscar primer '{' o '[', intentar parsear desde ahi
    3. Si sigue fallando: intentar utf-8-sig (BOM) y latin-1
    4. Si todo falla: devolver default y loguear el error

    Esto cubre el caso real detectado el 10/03/2026:
    concept_index.json tenia un byte extra 0x69 ('i') antes del '{',
    causando JSONDecodeError: Expecting value: line 1 column 1 (char 0).
    """
    if not path.exists():
        return default

    # Intento 1: lectura normal
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    except Exception as exc:
        logger.warning(f"[SIUO] Error inesperado cargando {path.name}: {exc}")
        return default

    # Intento 2: leer bytes y buscar el inicio del JSON
    try:
        raw = path.read_bytes()
        # Buscar primer '{' o '['
        start = -1
        for i, b in enumerate(raw):
            if b in (ord("{"), ord("[")):
                start = i
                break
        if start > 0:
            logger.warning(
                f"[SIUO] {path.name}: {start} byte(s) corrupto(s) al inicio "
                f"(0x{raw[0]:02X}). Intentando recuperar desde posicion {start}."
            )
            clean = raw[start:].decode("utf-8", errors="replace")
            result = json.loads(clean)
            # Auto-corregir el fichero para evitar el problema en el futuro
            try:
                path.write_bytes(raw[start:])
                logger.info(f"[SIUO] {path.name}: auto-corregido (bytes corruptos eliminados)")
            except Exception:
                pass
            return result
    except Exception as exc:
        logger.warning(f"[SIUO] Intento 2 fallido para {path.name}: {exc}")

    # Intento 3: utf-8-sig (BOM) y latin-1
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                result = json.load(f)
            logger.info(f"[SIUO] {path.name}: cargado con encoding {enc}")
            return result
        except Exception:
            pass

    logger.error(f"[SIUO] No se pudo cargar {path.name} tras todos los intentos. Usando default.")
    return default


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error(f"[SIUO] No se pudo guardar {path}: {exc}")


def _parse_json_response(raw: str) -> Dict:
    """Extrae y parsea el JSON de la respuesta de la IA."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ─── Singleton ────────────────────────────────────────────────────────────────

_deep_indexer_instance: Optional[DeepIndexerService] = None


def get_deep_indexer() -> DeepIndexerService:
    global _deep_indexer_instance
    if _deep_indexer_instance is None:
        _deep_indexer_instance = DeepIndexerService()
    return _deep_indexer_instance
