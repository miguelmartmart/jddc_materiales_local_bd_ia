"""
manager.py — SimulatorManager: orquestador central del módulo db_simulator.

Responsabilidades:
  • Mantener el estado del simulador (status.json)
  • Auto-inicializar con datos sintéticos al primer uso
  • Exponer build_synthetic() y build_snapshot(db_params) para el router
  • Proveer get_status() con métricas de las tablas

Patrón: singleton global `simulator_manager` importable desde cualquier módulo.

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from backend.modules.db_simulator.constants import (
    SimulatorConfig as Cfg,
    SimulatorDisclaimer,
    SimulatorLog,
    SimulatorMode,
    SimulatorStatus,
    SimulatorPaths,
    JDDCTableNames,
)
from backend.modules.db_simulator.driver import SimulatedFirebirdDriver
from backend.modules.db_simulator.schema import TABLE_SCHEMAS

logger = logging.getLogger(__name__)


class SimulatorManager:
    """
    Orquestador del simulador de BD.
    Thread-safe para uso en FastAPI (múltiples workers).
    """

    def __init__(self):
        self._status: Dict[str, Any] = self._load_status()

    # ─── API pública ─────────────────────────────────────────────────────────

    def ensure_ready(self) -> None:
        """
        Garantiza que el simulador tenga datos antes de usarse.
        Si no está inicializado → genera datos sintéticos automáticamente.
        Llamado implícitamente por SimulatedFirebirdDriver.connect() y por el router.
        """
        if self._status.get("status") == SimulatorStatus.READY:
            return

        logger.info(
            f"{SimulatorLog.PREFIX} Auto-inicializando con datos sintéticos "
            f"(primera vez o BD vacía)..."
        )
        try:
            self.build_synthetic()
        except Exception as e:
            logger.error(f"{SimulatorLog.PREFIX} ❌ Auto-init falló: {e}")

    def build_synthetic(self) -> Dict[str, Any]:
        """
        Genera y persiste datos sintéticos en el SQLite local.
        Sobrescribe cualquier dato anterior.
        Returns: dict con resultado de la operación.
        """
        self._set_status(SimulatorStatus.BUILDING, SimulatorMode.SYNTHETIC)
        try:
            from backend.modules.db_simulator.synthetic_seeder import SyntheticSeeder
            driver = SimulatedFirebirdDriver()
            driver.connect()
            seeder = SyntheticSeeder(driver.conn)
            counts = seeder.seed_all()
            driver.disconnect()

            self._set_status(
                SimulatorStatus.READY,
                SimulatorMode.SYNTHETIC,
                row_counts=counts,
            )
            logger.info(f"{SimulatorLog.PREFIX} ✅ Datos sintéticos generados: {counts}")
            return {"success": True, "mode": SimulatorMode.SYNTHETIC, "counts": counts}

        except Exception as e:
            self._set_status(SimulatorStatus.ERROR, SimulatorMode.SYNTHETIC, error=str(e))
            logger.error(f"{SimulatorLog.PREFIX} ❌ Error generando sintéticos: {e}")
            raise

    def build_snapshot(self, db_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Captura datos reales del último mes desde Firebird → SQLite.
        Returns: dict con resultado de la operación.
        """
        self._set_status(SimulatorStatus.BUILDING, SimulatorMode.SNAPSHOT)
        try:
            from backend.modules.db_simulator.snapshot_service import SnapshotService
            service = SnapshotService(db_params)
            counts  = service.run()

            snapshot_date = datetime.now().strftime("%d/%m/%Y %H:%M")
            self._set_status(
                SimulatorStatus.READY,
                SimulatorMode.SNAPSHOT,
                row_counts=counts,
                snapshot_date=snapshot_date,
            )
            logger.info(f"{SimulatorLog.PREFIX} ✅ Snapshot completado: {counts}")
            return {
                "success": True,
                "mode": SimulatorMode.SNAPSHOT,
                "counts": counts,
                "snapshot_date": snapshot_date,
            }

        except Exception as e:
            self._set_status(SimulatorStatus.ERROR, SimulatorMode.SNAPSHOT, error=str(e))
            logger.error(f"{SimulatorLog.PREFIX} ❌ Error en snapshot: {e}")
            raise

    def clear(self) -> Dict[str, Any]:
        """Elimina todos los datos del simulador y reinicia el estado."""
        try:
            driver = SimulatedFirebirdDriver()
            driver.connect()
            cursor = driver.conn.cursor()
            for table in TABLE_SCHEMAS:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                except Exception:
                    pass
            driver.conn.commit()
            driver.disconnect()

            self._set_status(SimulatorStatus.NOT_INITIALIZED, SimulatorMode.EMPTY)
            logger.info(f"{SimulatorLog.PREFIX} BD simuladora limpiada")
            return {"success": True, "message": "BD simuladora vaciada"}
        except Exception as e:
            logger.error(f"{SimulatorLog.PREFIX} Error limpiando: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Devuelve estado actual + métricas de filas por tabla."""
        status = dict(self._status)
        # Métricas en tiempo real
        try:
            driver = SimulatedFirebirdDriver()
            driver.connect()
            counts: Dict[str, int] = {}
            for table in JDDCTableNames.ALL:
                counts[table] = driver.get_row_count(table)
            driver.disconnect()
            status["row_counts"] = counts
            status["total_rows"]  = sum(counts.values())
        except Exception as e:
            status["row_counts_error"] = str(e)
        return status

    def get_table_preview(self, table_name: str, limit: int = 10) -> Dict[str, Any]:
        """Devuelve las primeras `limit` filas de una tabla simulada."""
        table_name = table_name.upper()
        if table_name not in TABLE_SCHEMAS:
            return {"error": f"Tabla '{table_name}' no existe en el simulador"}
        try:
            driver = SimulatedFirebirdDriver()
            driver.connect()
            rows = driver.execute_query(f"SELECT * FROM {table_name} LIMIT {limit}")
            count = driver.get_row_count(table_name)
            driver.disconnect()
            return {
                "table": table_name,
                "total_rows": count,
                "preview": rows,
                "columns": list(rows[0].keys()) if rows else [],
            }
        except Exception as e:
            return {"error": str(e)}

    # ─── Config: activación servidor ─────────────────────────────────────────

    def is_enabled(self) -> bool:
        """
        Lee en caliente config.json para saber si el simulador está activado.
        Patrón de live-reload: no requiere reiniciar el servidor.
        """
        cfg = self._load_config_file()
        return bool(cfg.get("simulator_enabled", False))

    def set_enabled(self, enabled: bool) -> None:
        """Persiste el flag simulator_enabled en config.json."""
        cfg = self._load_config_file()
        cfg["simulator_enabled"] = enabled
        try:
            with open(SimulatorPaths.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            logger.info(
                f"{SimulatorLog.PREFIX} simulator_enabled → {enabled} "
                f"(guardado en config.json)"
            )
        except Exception as e:
            logger.error(f"{SimulatorLog.PREFIX} Error escribiendo config.json: {e}")
            raise

    def get_disclaimer(self, html: bool = True) -> str:
        """
        Devuelve el texto/HTML de aviso de simulación.
        Incluye la fecha del snapshot cuando está disponible.
        """
        mode = self._status.get("mode", "")
        date_str = self._status.get("snapshot_date", "")

        if html:
            extra = ""
            if mode == SimulatorMode.SNAPSHOT and date_str:
                extra = f" Snapshot del <strong>{date_str}</strong>."
            elif mode == SimulatorMode.SYNTHETIC:
                extra = " Datos <em>generados automáticamente</em> (no reales)."
            # Inject extra info into the banner
            banner = SimulatorDisclaimer.HTML_BANNER.replace(
                "para consultar datos reales.",
                f"para consultar datos reales.{extra}",
            )
            return banner

        # Plain text version
        extra = ""
        if mode == SimulatorMode.SNAPSHOT and date_str:
            extra = f" (snapshot {date_str})"
        elif mode == SimulatorMode.SYNTHETIC:
            extra = " (datos sintéticos)"
        return SimulatorDisclaimer.TEXT_PREFIX + extra

    def get_schema_description(self) -> str:
        """
        Devuelve una descripción textual del esquema del simulador SQLite
        para usarla como contexto en el DeepAnalysisAgent.
        Las columnas son DIFERENTES a Firebird real — esto es crítico para
        que el AI genere SQL correcto contra el simulador.
        """
        return (
            "BASE DE DATOS: Simulador SQLite (MODO OFFLINE — no Firebird real)\n"
            "IMPORTANTE: usa las columnas EXACTAS listadas aquí — son DISTINTAS a Firebird.\n\n"
            "Tabla ARTICULO: CODIGO(PK), NOMBRE, DESCRIPCION, DESCRIPCIONCORTA, REFERENCIA,\n"
            "  PRECIOVENTA(REAL), IVA(REAL), CODFAMILIA(FK), PROVEEDDEFECTO(FK),\n"
            "  STOCKARTICULO(REAL), UNIDAD(TEXT)\n\n"
            "Tabla DOCLIN (líneas de documentos): CODIGO(FK→DOCCAB), NUMLINIA(INT),\n"
            "  CODART(TEXT FK→ARTICULO.CODIGO), DESCRIPCION, CANTIDAD(REAL),\n"
            "  PRECIOVENTA(REAL), DESCUENTO(REAL), IMPORTE(REAL)\n"
            "  → JOINS: DOCLIN.CODART = ARTICULO.CODIGO | DOCLIN.CODIGO = DOCCAB.CODIGO\n\n"
            "Tabla DOCCAB (cabecera documentos): CODIGO(PK), TIPO(INT 0=presupuesto,\n"
            "  11=albaran, 12=pedido, 13=factura, 2=SAT), FECHA(TEXT 'YYYY-MM-DD'),\n"
            "  CODCLIENTE(FK), CODAGENTE(FK), CODALMACEN(INT),\n"
            "  IMPORTEBASE(REAL), IVA(REAL), IMPORTETOTAL(REAL),\n"
            "  ESTADO(INT), DESCRIPCION, OBSERVACIONES, CODSERIE(TEXT)\n\n"
            "Tabla CLIENTE: CODIGO(PK), NOMBRE, CIF, EMAIL, TELEFONO, DIRECCION,\n"
            "  POBLACION, PROVINCIA, CP, TIPO(INT), CODAGENTE(FK), ACTIVO(INT)\n\n"
            "Tabla FAMILIA: CODIGO(PK), NOMBRE, DESCRIPCION\n\n"
            "Tabla PROVEED: CODIGO(PK), NOMBRE, CIF, EMAIL, TELEFONO\n\n"
            "Tabla RECURSO (empleados): CODIGO(PK), NOMBRE, ROL, DEPARTAMENTO, EMAIL\n\n"
            "Tabla ALMACEN: CODIGO(PK), NOMBRE, UBICACION\n\n"
            "Tabla CAJA (cobros): CODIGO(PK), FECHA(TEXT), CONCEPTO, IMPORTE(REAL),\n"
            "  TIPO(INT), CODCLIENTE(FK), CODAGENTE(FK)\n\n"
            "Tabla ESTALMACEN (movimientos stock): CODIGO(PK), CODART(FK→ARTICULO.CODIGO),\n"
            "  CODALMACEN(FK), FECHA(TEXT), CANTIDAD(REAL), COSTE(REAL), VENTA(REAL)\n\n"
            "SINTAXIS SQLite (NO Firebird):\n"
            "  - Usar LIMIT N  (NO FIRST N)\n"
            "  - Fechas con strftime('%Y', FECHA), strftime('%m', FECHA)\n"
            "  - date('now') para fecha actual\n"
            "  - No usar EXTRACT() — usar strftime()\n"
            "  - No usar CAST(x AS NUMERIC(15,2)) → ROUND(x, 2)\n"
            "  - GROUP BY debe incluir todas las columnas no agregadas del SELECT\n"
        )

    def _load_config_file(self) -> Dict[str, Any]:
        """Carga config.json del módulo. Devuelve {} si no existe o hay error."""
        try:
            if SimulatorPaths.CONFIG_PATH.exists():
                with open(SimulatorPaths.CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"{SimulatorLog.PREFIX} No se pudo leer config.json: {e}")
        return {"simulator_enabled": False, "show_disclaimer": True}

    # ─── Estado interno ───────────────────────────────────────────────────────

    def _set_status(
        self,
        status: str,
        mode: str,
        row_counts: Optional[Dict[str, int]] = None,
        error: Optional[str] = None,
        snapshot_date: Optional[str] = None,
    ) -> None:
        self._status = {
            "status":        status,
            "mode":          mode,
            "updated_at":    datetime.now().isoformat(),
            "db_path":       str(SimulatorPaths.DB_PATH),
            "row_counts":    row_counts or {},
            "error":         error,
            "snapshot_date": snapshot_date or "",
        }
        self._save_status()

    def _load_status(self) -> Dict[str, Any]:
        try:
            if SimulatorPaths.STATUS_PATH.exists():
                with open(SimulatorPaths.STATUS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"status": SimulatorStatus.NOT_INITIALIZED, "mode": SimulatorMode.EMPTY}

    def _save_status(self) -> None:
        try:
            SimulatorPaths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(SimulatorPaths.STATUS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"{SimulatorLog.PREFIX} No se pudo guardar status: {e}")


# ─── Singleton global ─────────────────────────────────────────────────────────

simulator_manager = SimulatorManager()
