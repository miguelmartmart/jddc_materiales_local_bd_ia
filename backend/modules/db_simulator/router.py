"""
router.py — Endpoints FastAPI del módulo db_simulator.

Expone la gestión del simulador via REST para que el frontend
(o scripts externos) puedan consultar el estado, construir
snapshots/datos sintéticos y previsualizar tablas.

Prefix: /api/db-simulator

Endpoints:
  GET  /status               → estado actual + métricas por tabla
  POST /build-synthetic      → genera datos sintéticos (sin BD real)
  POST /build-snapshot       → captura datos reales de Firebird
  DELETE /clear              → vacía el simulador
  GET  /tables               → lista tablas disponibles
  GET  /preview/{table_name} → primeras N filas de una tabla

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from backend.modules.db_simulator.constants import (
    SimulatorDisclaimer,
    SimulatorEndpoints,
    SimulatorLog,
    SimulatorPaths,
    SimulatorStatus,
)
from backend.modules.db_simulator.demo_queries import get_demo_sql_queries
from backend.modules.db_simulator.query_library import (
    get_all_queries,
    get_catalog_summary,
    search_queries,
    get_query_by_id,
)
from backend.modules.db_simulator.query_verifications import get_verifications_for_query
from backend.modules.db_simulator.query_library_constants import (
    TIPO_ICONOS,
    URGENCIA_COLORES,
    DEPT_ICONOS,
)
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.manager  import simulator_manager
from backend.modules.db_simulator.query_translator import translate_firebird_sql
from backend.modules.db_simulator.schema   import TABLE_SCHEMAS

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Modelos Pydantic ─────────────────────────────────────────────────────────

class SnapshotRequest(BaseModel):
    """
    Parámetros de conexión Firebird para capturar snapshot.
    Defaults: valores del .env del servidor (DB_HOST, DB_PORT, DB_NAME…).
    Si el cliente no envía algún campo, se usan los configurados en el servidor.
    """
    host:     str = ""   # "" → usa settings.DB_HOST
    port:     int = 0    # 0  → usa settings.DB_PORT
    database: str = ""   # "" → usa settings.DB_NAME
    user:     str = ""   # "" → usa settings.DB_USER
    password: str = ""   # "" → usa settings.DB_PASSWORD
    charset:  str = "latin1"


class SimulatorConfigUpdate(BaseModel):
    """Cuerpo del POST /config para activar/desactivar el simulador."""
    simulator_enabled: bool
    show_disclaimer:   Optional[bool] = None  # None = no cambiar


class ExecuteSqlRequest(BaseModel):
    """Cuerpo del POST /execute para ejecutar SQL arbitrario en el simulador."""
    sql: str


class SimulatorResponse(BaseModel):
    success: bool
    message: str
    data:    Optional[Dict[str, Any]] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/onboarding-status", summary="Estado de configuración del simulador para el chat IA")
async def get_onboarding_status():
    """
    Devuelve el estado de configuración del simulador con los pasos exactos
    que el usuario debe seguir para que el chat IA funcione correctamente.

    Usado por el frontend para mostrar un panel de onboarding cuando el
    simulador no está listo o no está activado.

    Respuesta:
      • ready: bool — True si el chat IA puede usarse ahora mismo
      • steps: lista de pasos con estado (done/pending/error)
      • message: mensaje amigable para mostrar al usuario
      • simulator_enabled: bool
      • has_data: bool
      • row_counts: dict con filas por tabla
    """
    try:
        status = simulator_manager.get_status()
        is_enabled = simulator_manager.is_enabled()
        sim_status = status.get("status", "not_initialized")
        row_counts = status.get("row_counts", {})
        has_data = sim_status == SimulatorStatus.READY and bool(row_counts) and any(v > 0 for v in row_counts.values())

        steps = [
            {
                "step": 1,
                "title": "Activar el simulador",
                "description": "El simulador permite usar el chat IA sin conexión a Firebird real.",
                "action": "POST /api/db-simulator/config  →  {\"simulator_enabled\": true}",
                "done": is_enabled,
                "required": True,
            },
            {
                "step": 2,
                "title": "Generar datos sintéticos",
                "description": "Crea ~1.200 registros realistas del sector climatización JDDC (facturas, clientes, artículos, etc.).",
                "action": "POST /api/db-simulator/build-synthetic",
                "done": has_data,
                "required": True,
            },
            {
                "step": 3,
                "title": "Usar el chat IA",
                "description": "Ya puedes hacer preguntas como '¿Cuántas facturas hay este mes?' o 'Dame el top 5 de clientes'.",
                "action": "Escribe tu pregunta en el chat",
                "done": is_enabled and has_data,
                "required": True,
            },
        ]

        all_done = all(s["done"] for s in steps if s["required"])

        if all_done:
            message = (
                "✅ **Chat IA listo** — El simulador está activo con datos sintéticos. "
                f"Tablas disponibles: {', '.join(sorted(row_counts.keys()))}. "
                "Puedes hacer preguntas sobre facturas, clientes, artículos, stock, etc."
            )
        elif not is_enabled:
            message = (
                "⚠️ **Simulador no activado** — Para usar el chat IA sin Firebird real, "
                "activa el simulador desde el panel de administración o llama a "
                "`POST /api/db-simulator/config` con `{\"simulator_enabled\": true}`."
            )
        elif not has_data:
            message = (
                "⚠️ **Sin datos** — El simulador está activado pero no tiene datos. "
                "Genera datos sintéticos con `POST /api/db-simulator/build-synthetic` "
                "(tarda ~2 segundos, no requiere Firebird)."
            )
        else:
            message = f"⚠️ Estado del simulador: {sim_status}"

        return {
            "ready": all_done,
            "simulator_enabled": is_enabled,
            "has_data": has_data,
            "simulator_status": sim_status,
            "steps": steps,
            "message": message,
            "row_counts": row_counts,
            "mode": status.get("mode", ""),
            "updated_at": status.get("updated_at", ""),
        }
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /onboarding-status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/demo", summary="Consultas de demostración del simulador")
async def get_demo_data():
    """
    Ejecuta 10 consultas de negocio predefinidas sobre el simulador SQLite
    y devuelve los resultados estructurados para el dashboard frontend.

    Consultas incluidas:
      • Resumen general (totales)
      • Productos más vendidos
      • Mejores clientes
      • Facturación mensual
      • Distribución documentos por tipo
      • Principales proveedores
      • Stock disponible
      • Últimas facturas
      • Presupuestos pendientes
      • SATs recientes
    """
    status = simulator_manager.get_status()
    if status.get("status") != SimulatorStatus.READY:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El simulador no está listo (estado: {status.get('status')}). "
                "Ejecuta POST /build-synthetic o /build-snapshot primero."
            ),
        )
    try:
        from backend.modules.db_simulator.demo_queries import run_demo_queries
        data = run_demo_queries()
        return {
            "success": True,
            "simulator_mode": status.get("mode"),
            "snapshot_date": status.get("snapshot_date", ""),
            "queries": data,
        }
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /demo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(SimulatorEndpoints.DEMO_SQL, summary="Consultas SQL predefinidas para el simulador")
async def get_demo_sql():
    """Devuelve el listado de consultas SQL predefinidas para la vista de prueba de la BD simulada."""
    try:
        queries = get_demo_sql_queries()
        return {"success": True, "queries": queries}
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /demo-sql: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(SimulatorEndpoints.EXECUTE, summary="Ejecutar SQL libre sobre el simulador")
async def execute_sql(request: ExecuteSqlRequest):
    """Ejecuta una consulta SQL arbitraria contra el simulador SQLite y devuelve resultados."""
    sql = request.sql or ""
    if not sql.strip():
        raise HTTPException(status_code=400, detail="Se requiere un SQL válido para ejecutar.")

    simulator_manager.ensure_ready()
    driver = SimulatedFirebirdDriver()
    driver.connect()
    try:
        normalized_sql = sql.strip()
        first_word = normalized_sql.split(None, 1)[0].upper()
        if first_word in ("SELECT", "WITH"):
            rows = driver.execute_query(normalized_sql)
            return {
                "success": True,
                "type": "select",
                "rows": rows,
                "columns": list(rows[0].keys()) if rows else [],
            }

        translated_sql, _ = translate_firebird_sql(normalized_sql)
        affected_rows = driver.execute_command(translated_sql)
        return {
            "success": True,
            "type": "command",
            "sql": translated_sql,
            "affected_rows": affected_rows,
        }
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /execute: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        driver.disconnect()


@router.get(SimulatorEndpoints.STATUS, summary="Estado del simulador")
async def get_status():
    """
    Devuelve el estado actual del simulador y el número de filas por tabla.

    Posibles estados: not_initialized, ready, building, error
    """
    try:
        status = simulator_manager.get_status()
        return status
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(SimulatorEndpoints.BUILD_SYNTHETIC, summary="Generar datos sintéticos")
async def build_synthetic(background_tasks: BackgroundTasks):
    """
    Genera datos sintéticos realistas del sector de climatización JDDC.
    No requiere acceso a BD real. Tarda ~1-2 segundos.

    Genera aproximadamente:
    - 120 artículos (equipos, gas, servicios)
    - 60 clientes (empresas e individuales de Valencia)
    - 220 documentos del último mes (facturas, presupuestos, SATs…)
    - ~660 líneas de documento, 90 movimientos de caja, 180 de stock
    """
    try:
        # Ejecutar en background para no bloquear la respuesta HTTP
        # (aunque es rápido, es buena práctica para operaciones de escritura)
        result = simulator_manager.build_synthetic()
        return SimulatorResponse(
            success=True,
            message="Datos sintéticos generados correctamente",
            data=result,
        )
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error build_synthetic: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando datos: {str(e)}")


@router.post(SimulatorEndpoints.BUILD_SNAPSHOT, summary="Capturar snapshot de BD real")
async def build_snapshot(request: SnapshotRequest):
    """
    Captura datos reales desde la BD Firebird indicada y los persiste en SQLite.
    Requiere acceso a la BD Firebird en ese momento.

    Proceso completo:
    - Sincroniza esquema SQLite con el real de Firebird (mismas columnas, PKs)
    - Tablas de referencia: FAMILIA, ALMACEN, RECURSO, PROVEED, ARTICULO, CLIENTE,
      PROYECTOS, PROYVAR, PRESUPROYE
    - Tablas con fecha (último mes): DOCCAB, CAJA, ESTALMACEN
    - Histórico proyectos: todos los DOCCAB con CODPROYECTO (sin límite fecha)
    - Enlazadas: DOCLIN, DOCDESTINO (de todos los DOCCAB capturados)

    Ejecución en hilo separado para no bloquear el event loop durante el proceso.
    """
    import asyncio
    from backend.core.config.settings import settings as _s
    try:
        # Si el cliente no envía un campo, usar el valor del .env del servidor
        db_params = {
            "host":     request.host     or _s.DB_HOST,
            "port":     request.port     or _s.DB_PORT,
            "database": request.database or _s.DB_NAME,
            "user":     request.user     or _s.DB_USER,
            "password": request.password or _s.DB_PASSWORD,
            "charset":  request.charset,
        }
        # Ejecutar en executor para no bloquear el event loop de FastAPI
        # (el snapshot puede tardar 30-120 segundos conectando a Firebird)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, simulator_manager.build_snapshot, db_params
        )
        return SimulatorResponse(
            success=True,
            message="Snapshot de BD real completado",
            data=result,
        )
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error build_snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error capturando snapshot: {str(e)}"
        )


@router.delete(SimulatorEndpoints.CLEAR, summary="Vaciar simulador")
async def clear_simulator():
    """Elimina todos los datos del simulador. El estado vuelve a not_initialized."""
    try:
        result = simulator_manager.clear()
        return SimulatorResponse(
            success=True,
            message="Simulador vaciado correctamente",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(SimulatorEndpoints.TABLES, summary="Listar tablas simuladas")
async def list_tables():
    """
    Devuelve la lista de tablas disponibles en el simulador
    con el número de filas actual de cada una.
    """
    status = simulator_manager.get_status()
    counts = status.get("row_counts", {})
    tables = []
    for table in TABLE_SCHEMAS:
        tables.append({
            "table":    table,
            "rows":     counts.get(table, 0),
            "ready":    counts.get(table, 0) > 0,
        })
    return {
        "simulator_status": status.get("status"),
        "simulator_mode":   status.get("mode"),
        "tables": tables,
    }


@router.get(
    SimulatorEndpoints.PREVIEW,
    summary="Previsualizar tabla simulada",
)
async def preview_table(
    table_name: str,
    limit: int = Query(default=10, ge=1, le=100),
):
    """
    Devuelve las primeras `limit` filas de una tabla simulada.
    Útil para verificar los datos generados o capturados.
    """
    status = simulator_manager.get_status()
    if status.get("status") != SimulatorStatus.READY:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El simulador no está listo (estado: {status.get('status')}). "
                "Ejecuta POST /build-synthetic o /build-snapshot primero."
            )
        )
    result = simulator_manager.get_table_preview(table_name, limit)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get(SimulatorEndpoints.CONFIG, summary="Leer configuración del simulador")
async def get_simulator_config():
    """
    Lee config.json del módulo db_simulator.

    Campos:
    - simulator_enabled : bool — si True, el chat usará SQLite en lugar de Firebird real
    - show_disclaimer   : bool — si True, la respuesta incluirá aviso de simulación
    - disclaimer_html   : str  — HTML del aviso actual (basado en el estado del simulador)
    - disclaimer_text   : str  — Versión plana del aviso (para voz / API)
    """
    try:
        cfg = simulator_manager._load_config_file()
        return {
            "simulator_enabled": cfg.get("simulator_enabled", False),
            "show_disclaimer":   cfg.get("show_disclaimer", True),
            "disclaimer_html":   simulator_manager.get_disclaimer(html=True),
            "disclaimer_text":   simulator_manager.get_disclaimer(html=False),
            "status":            simulator_manager._status.get("status"),
            "mode":              simulator_manager._status.get("mode"),
            "snapshot_date":     simulator_manager._status.get("snapshot_date", ""),
        }
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en GET /config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(SimulatorEndpoints.CONFIG, summary="Actualizar configuración del simulador")
async def update_simulator_config(config: SimulatorConfigUpdate):
    """
    Actualiza config.json del módulo db_simulator.

    - simulator_enabled=true  → el chat usará SQLite (simulador) en lugar de Firebird
    - simulator_enabled=false → comportamiento normal (BD real Firebird)

    El cambio es inmediato (live-reload). No requiere reiniciar el servidor.
    """
    try:
        simulator_manager.set_enabled(config.simulator_enabled)

        # Actualizar show_disclaimer si se envió explícitamente
        if config.show_disclaimer is not None:
            import json as _json
            cfg = simulator_manager._load_config_file()
            cfg["show_disclaimer"] = config.show_disclaimer
            with open(SimulatorPaths.CONFIG_PATH, "w", encoding="utf-8") as f:
                _json.dump(cfg, f, indent=2, ensure_ascii=False)

        enabled = config.simulator_enabled
        mode_label = (
            "SIMULADOR activo (SQLite local)" if enabled
            else "BD REAL (Firebird normal)"
        )
        return SimulatorResponse(
            success=True,
            message=f"Configuración actualizada → {mode_label}",
            data={
                "simulator_enabled": enabled,
                "disclaimer_html":   simulator_manager.get_disclaimer(html=True) if enabled else "",
            },
        )
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en POST /config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Biblioteca de consultas ──────────────────────────────────────────────────

@router.get("/query-library/catalog", summary="Catálogo de la biblioteca de consultas")
async def get_query_catalog():
    """
    Devuelve el resumen del catálogo: total de consultas, distribución
    por departamento, rol, tipo y urgencia. Incluye iconos y colores para el frontend.
    """
    try:
        summary = get_catalog_summary()
        # Enriquecer con iconos y colores para el frontend
        summary["tipo_iconos"]     = TIPO_ICONOS
        summary["urgencia_colores"] = URGENCIA_COLORES
        summary["dept_iconos"]     = DEPT_ICONOS
        return {"success": True, "catalog": summary}
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /query-library/catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query-library/search", summary="Buscar consultas en la biblioteca")
async def search_query_library(
    dept:     str = Query(default=None, description="Filtrar por departamento"),
    rol:      str = Query(default=None, description="Filtrar por rol"),
    tipo:     str = Query(default=None, description="Filtrar por tipo de análisis"),
    urgencia: str = Query(default=None, description="Filtrar por urgencia"),
    text:     str = Query(default=None, description="Búsqueda libre en título/descripción"),
    limit:    int = Query(default=50, ge=1, le=200, description="Máximo de resultados"),
):
    """
    Busca consultas en la biblioteca con filtros combinados.
    Todos los filtros son opcionales. Se combinan con AND.
    Devuelve las consultas sin el SQL (para el listado). Usar /query-library/{id} para el SQL.
    """
    try:
        results = search_queries(dept=dept, rol=rol, tipo=tipo, urgencia=urgencia, text=text)
        # Devolver sin SQL en el listado (el SQL se obtiene al seleccionar una consulta)
        items = [
            {
                "id":          q["id"],
                "title":       q["title"],
                "desc":        q["desc"],
                "desc_simple": q.get("desc_simple", ""),
                "desc_tecnica": q.get("desc_tecnica", ""),
                "dept":        q.get("dept", []),
                "rol":         q.get("rol", []),
                "tipo":        q.get("tipo", ""),
                "urgencia":    q.get("urgencia", ""),
                "kpi":         q.get("kpi", ""),
                "accion":      q.get("accion", ""),
                "icono":       TIPO_ICONOS.get(q.get("tipo", ""), "📋"),
                "color":       URGENCIA_COLORES.get(q.get("urgencia", ""), "#64748b"),
            }
            for q in results[:limit]
        ]
        return {
            "success": True,
            "total":   len(results),
            "shown":   len(items),
            "queries": items,
        }
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /query-library/search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query-library/{query_id}", summary="Obtener consulta por ID (con SQL)")
async def get_query_detail(query_id: str):
    """
    Devuelve el detalle completo de una consulta, incluyendo el SQL.
    Usar este endpoint al seleccionar una consulta para cargarla en el editor.
    """
    try:
        q = get_query_by_id(query_id)
        return {
            "success": True,
            "query": {
                **q,
                "icono": TIPO_ICONOS.get(q.get("tipo", ""), "📋"),
                "color": URGENCIA_COLORES.get(q.get("urgencia", ""), "#64748b"),
            },
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Consulta '{query_id}' no encontrada.")
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error en /query-library/{query_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-library/{query_id}/execute", summary="Ejecutar consulta de la biblioteca")
async def execute_library_query(query_id: str):
    """
    Ejecuta directamente una consulta de la biblioteca sobre el simulador.
    Equivale a cargar el SQL de la consulta y ejecutarlo en /execute.
    Devuelve el resultado más los metadatos de la consulta (descripción, acción recomendada).
    """
    try:
        q = get_query_by_id(query_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Consulta '{query_id}' no encontrada.")

    simulator_manager.ensure_ready()
    driver = SimulatedFirebirdDriver()
    driver.connect()
    try:
        rows = driver.execute_query(q["sql"])
        return {
            "success":     True,
            "query_id":    query_id,
            "title":       q["title"],
            "desc":        q["desc"],
            "desc_simple": q.get("desc_simple", ""),
            "desc_tecnica": q.get("desc_tecnica", ""),
            "accion":      q.get("accion", ""),
            "kpi":         q.get("kpi", ""),
            "tipo":        q.get("tipo", ""),
            "urgencia":    q.get("urgencia", ""),
            "icono":       TIPO_ICONOS.get(q.get("tipo", ""), "📋"),
            "color":       URGENCIA_COLORES.get(q.get("urgencia", ""), "#64748b"),
            "rows":        rows,
            "columns":     list(rows[0].keys()) if rows else [],
            "n_rows":      len(rows),
        }
    except Exception as e:
        logger.error(f"{SimulatorLog.PREFIX} Error ejecutando consulta '{query_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        driver.disconnect()


@router.get("/query-library/{query_id}/verify", summary="Ejecutar sub-consultas de verificación")
async def verify_library_query(query_id: str):
    """
    Ejecuta todas las sub-consultas de verificación/justificación definidas para una consulta.
    Devuelve los resultados de cada sub-consulta con su justificación textual.
    Si la consulta no tiene verificaciones definidas, devuelve lista vacía.
    Si el simulador no está listo, devuelve los metadatos sin datos.
    """
    # Obtener metadatos de verificaciones (sin ejecutar)
    verifications_meta = get_verifications_for_query(query_id)

    # Comprobar si el simulador tiene datos (en memoria o en disco)
    status = simulator_manager.get_status()
    sim_ready = status.get("status") == SimulatorStatus.READY
    # Fallback: intentar conectar al driver directamente aunque el manager no esté "ready"
    # (ocurre cuando hay un snapshot real en disco pero el servidor acaba de arrancar)
    if not sim_ready:
        try:
            _test_driver = SimulatedFirebirdDriver()
            _test_driver.connect()
            _test_rows = _test_driver.execute_query("SELECT COUNT(*) AS N FROM DOCCAB")
            _test_driver.disconnect()
            sim_ready = bool(_test_rows and _test_rows[0].get("N", 0) > 0)
        except Exception:
            sim_ready = False

    if not sim_ready:
        return {
            "success": True,
            "query_id": query_id,
            "simulator_ready": False,
            "verifications": [
                {
                    "id": v["id"],
                    "label": v["label"],
                    "justificacion": v["justificacion"],
                    "icono": v.get("icono", "📋"),
                    "tipo": v.get("tipo", "tabla"),
                    "rows": [],
                    "columns": [],
                    "error": None,
                    "executed": False,
                }
                for v in verifications_meta
            ],
        }

    driver = SimulatedFirebirdDriver()
    driver.connect()
    results = []
    try:
        for v in verifications_meta:
            item = {
                "id": v["id"],
                "label": v["label"],
                "justificacion": v["justificacion"],
                "icono": v.get("icono", "📋"),
                "tipo": v.get("tipo", "tabla"),
                "max_rows": v.get("max_rows", 20),
                "rows": [],
                "columns": [],
                "error": None,
                "executed": True,
            }
            try:
                rows = driver.execute_query(v["sql"])
                max_r = v.get("max_rows", 20)
                item["rows"] = rows[:max_r]
                item["columns"] = list(rows[0].keys()) if rows else []
                item["n_rows"] = len(rows)
            except Exception as e:
                item["error"] = str(e)
                logger.warning(
                    f"{SimulatorLog.PREFIX} Verificación '{v['id']}' de '{query_id}' falló: {e}"
                )
            results.append(item)
    finally:
        driver.disconnect()

    return {
        "success": True,
        "query_id": query_id,
        "simulator_ready": True,
        "n_verifications": len(results),
        "verifications": results,
    }
