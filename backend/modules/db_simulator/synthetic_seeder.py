"""
synthetic_seeder.py — Generador de datos sintéticos realistas para JDDC.

Genera datos coherentes del sector de climatización (JDDC) en SQLite
sin necesidad de conexión a la BD real. Los datos tienen volumen y
distribución estadística que imita fielmente la BD de producción.

Genera aproximadamente:
  - 15 familias, 4 almacenes, 15 proveedores, 12 empleados
  - 120 artículos (equipos, gas, accesorios, servicios)
  - 60 clientes (empresas e individuales)
  - 220 documentos del último mes (facturas, presupuestos, SATs…)
  - ~660 líneas de documento, 90 movimientos de caja, 180 de stock

Columnas verificadas contra BD real Firebird (simulator.db snapshot).

DEVIA: backend/modules/db_simulator/DEVIA.md
"""

import logging
import random
import sqlite3
from datetime import date, timedelta
from typing import List, Tuple

from backend.modules.db_simulator.constants import (
    SimulatorConfig as Cfg,
    SimulatorLog,
    JDDCDocTipos,
)
from backend.modules.db_simulator.seed_data import (
    FAMILIAS, ALMACENES, PROVEEDORES, RECURSOS,
    ARTICULOS_DATA, CLIENTES_DATA,
)

logger = logging.getLogger(__name__)

# ─── Helpers de fecha ─────────────────────────────────────────────────────────

def _dates_range(months_back: int = 2, n: int = 1) -> List[str]:
    """Genera n fechas aleatorias en los últimos `months_back` meses."""
    today = date.today()
    start = today - timedelta(days=months_back * 31)
    delta = (today - start).days
    return [(start + timedelta(days=random.randint(0, delta))).isoformat()
            for _ in range(n)]

def _rand_date(months_back: int = 2) -> str:
    return _dates_range(months_back, 1)[0]

# ─── Seeder principal ─────────────────────────────────────────────────────────

class SyntheticSeeder:
    """
    Inserta datos sintéticos realistas en la BD SQLite del simulador.
    Limpia las tablas antes de insertar (idempotente).
    Usa nombres de columna idénticos a la BD real Firebird.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._cur = conn.cursor()

    def seed_all(self) -> dict:
        """
        Inserta todos los datos. Devuelve resumen de filas insertadas.
        El orden respeta dependencias FK.
        """
        logger.info(f"{SimulatorLog.SYNTHETIC} Iniciando generación de datos sintéticos...")
        self._clear_all()

        counts = {}
        counts["FAMILIA"]     = self._seed_familias()
        counts["ALMACEN"]     = self._seed_almacenes()
        counts["RECURSO"]     = self._seed_recursos()
        counts["PROVEED"]     = self._seed_proveedores()
        counts["ARTICULO"]    = self._seed_articulos()
        counts["CLIENTE"]     = self._seed_clientes()
        counts["DOCCAB"], counts["DOCLIN"] = self._seed_documentos()
        counts["CAJA"]        = self._seed_caja()
        counts["ESTALMACEN"]  = self._seed_estalmacen()

        self.conn.commit()
        total = sum(counts.values())
        logger.info(
            f"{SimulatorLog.SYNTHETIC} ✅ Generación completada: "
            f"{total} registros en {len(counts)} tablas → {counts}"
        )
        return counts

    # ─── Limpieza ────────────────────────────────────────────────────────────

    def _clear_all(self) -> None:
        tables = [
            "ESTALMACEN", "CAJA", "DOCLIN", "DOCCAB",
            "CLIENTE", "ARTICULO", "PROVEED", "RECURSO", "ALMACEN", "FAMILIA",
        ]
        for t in tables:
            try:
                self._cur.execute(f"DELETE FROM {t}")
            except Exception:
                pass  # Tabla puede no existir aún

    # ─── Tablas de referencia ────────────────────────────────────────────────

    def _seed_familias(self) -> int:
        self._cur.executemany(
            "INSERT INTO FAMILIA (CODIGO, NOMBRE, DESCRIPCION) VALUES (?,?,?)",
            FAMILIAS
        )
        return len(FAMILIAS)

    def _seed_almacenes(self) -> int:
        self._cur.executemany(
            "INSERT INTO ALMACEN (CODIGO, NOMBRE, DIRECCION) VALUES (?,?,?)",
            ALMACENES
        )
        return len(ALMACENES)

    def _seed_recursos(self) -> int:
        rows = [
            (r[0], r[1], r[2], r[3], r[4], r[5])
            for r in RECURSOS
        ]
        self._cur.executemany(
            "INSERT INTO RECURSO (CODIGO,DESCRIPCION,CODPADRE,ORDEN,NIF,TELEFONO) "
            "VALUES (?,?,?,?,?,?)",
            rows
        )
        return len(rows)

    def _seed_proveedores(self) -> int:
        # PROVEED real: CODIGO, NOMBRECOMERCIAL, RAZONSOCIAL, TEL, NIF
        rows = [(p[0], p[1], p[1], p[3], p[2]) for p in PROVEEDORES]
        self._cur.executemany(
            "INSERT INTO PROVEED (CODIGO,NOMBRECOMERCIAL,RAZONSOCIAL,TEL,NIF) "
            "VALUES (?,?,?,?,?)",
            rows
        )
        return len(rows)

    def _seed_articulos(self) -> int:
        # ARTICULO real: CODIGO, CODFAMILIA, NOMBRE, DESCRIPCION, DESCRIPCIONCORTA,
        #                REFERENCIA, PRECIOVENTA, TIPOIVA, PROVEEDDEFECTO, STOCKARTICULO, UNIDAD
        rows = []
        for idx, art in enumerate(ARTICULOS_DATA, start=1):
            ref, nombre, desc_corta, precio, cod_fam, cod_prov, stock = art
            rows.append((
                idx, cod_fam, nombre, nombre, desc_corta, ref,
                precio, Cfg.IVA_GENERAL, cod_prov, stock, "UD"
            ))
        self._cur.executemany(
            "INSERT INTO ARTICULO "
            "(CODIGO,CODFAMILIA,NOMBRE,DESCRIPCION,DESCRIPCIONCORTA,REFERENCIA,"
            "PRECIOVENTA,TIPOIVA,PROVEEDDEFECTO,STOCKARTICULO,UNIDAD) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )
        return len(rows)

    def _seed_clientes(self) -> int:
        # CLIENTE real: CODIGO, NOMBRECOMERCIAL, RAZONSOCIAL, TEL, NIF, CODFORMAPAGO, CODAGENTE
        rows = []
        for idx, c in enumerate(CLIENTES_DATA, start=1):
            nombre, cif, pob, cp, prov, tel, email, agente = c
            rows.append((idx, nombre, nombre, tel, cif, "CONTADO", agente))
        self._cur.executemany(
            "INSERT INTO CLIENTE "
            "(CODIGO,NOMBRECOMERCIAL,RAZONSOCIAL,TEL,NIF,CODFORMAPAGO,CODAGENTE) "
            "VALUES (?,?,?,?,?,?,?)",
            rows
        )
        return len(rows)

    # ─── Documentos (DOCCAB + DOCLIN) ────────────────────────────────────────

    def _seed_documentos(self) -> Tuple[int, int]:
        n_docs = Cfg.SYNTHETIC_DOCCAB
        tipo_dist = [
            (JDDCDocTipos.FACTURA,     int(n_docs * Cfg.DOCCAB_PCT_FACTURA)),
            (JDDCDocTipos.PRESUPUESTO, int(n_docs * Cfg.DOCCAB_PCT_PRESUPUESTO)),
            (JDDCDocTipos.ALBARAN,     int(n_docs * Cfg.DOCCAB_PCT_ALBARAN)),
            (JDDCDocTipos.SAT,         int(n_docs * Cfg.DOCCAB_PCT_SAT)),
            (JDDCDocTipos.PEDIDO,      int(n_docs * Cfg.DOCCAB_PCT_PEDIDO)),
        ]

        tipos_list: List[int] = []
        for tipo, qty in tipo_dist:
            tipos_list.extend([tipo] * qty)
        # Rellenar hasta n_docs con facturas
        while len(tipos_list) < n_docs:
            tipos_list.append(JDDCDocTipos.FACTURA)
        random.shuffle(tipos_list)

        n_clientes  = len(CLIENTES_DATA)
        n_agentes   = [r[0] for r in RECURSOS if r[2] in (2, 3)]  # técnicos/comerciales
        agente_ids  = n_agentes if n_agentes else [5, 6, 7, 9, 10]
        art_ids     = list(range(1, len(ARTICULOS_DATA) + 1))
        art_precios = {i + 1: ARTICULOS_DATA[i][3] for i in range(len(ARTICULOS_DATA))}
        art_nombres = {i + 1: ARTICULOS_DATA[i][1] for i in range(len(ARTICULOS_DATA))}

        doccab_rows: List[tuple] = []
        doclin_rows: List[tuple] = []
        numero_por_tipo: dict = {}

        for doc_id in range(1, n_docs + 1):
            tipo       = tipos_list[doc_id - 1]
            numero_por_tipo[tipo] = numero_por_tipo.get(tipo, 0) + 1
            numero     = numero_por_tipo[tipo]
            fecha      = _rand_date(2)
            cod_cli    = random.randint(1, n_clientes)
            cod_agente = random.choice(agente_ids)
            estado     = _doc_estado(tipo)

            # Generar líneas (2-5 por documento)
            n_lineas   = random.randint(2, 5)
            arts_sel   = random.sample(art_ids, min(n_lineas, len(art_ids)))
            base       = 0.0
            for linia_num, art_id in enumerate(arts_sel, start=1):
                precio    = art_precios.get(art_id, 100.0)
                precio    = round(precio * random.uniform(0.9, 1.15), 2)
                cantidad  = round(random.choice([1.0, 1.0, 1.0, 2.0, 3.0, 0.5]), 2)
                descuento = round(random.choice([0.0, 0.0, 5.0, 10.0, 15.0]), 2)
                importe   = round(precio * cantidad * (1 - descuento / 100), 2)
                base     += importe
                # DOCLIN real: CODDOCUMENTO, CODIGO, CODARTICULO, DESCRIPCION,
                #              CANTIDAD, PRECIO, COSTE, DESCUENTOS
                doclin_rows.append((
                    doc_id, linia_num,
                    str(art_id),
                    art_nombres.get(art_id, ""),
                    cantidad, precio,
                    round(precio * 0.65, 2),  # COSTE ≈ 65% del precio
                    descuento,
                ))

            iva_total = round(base * Cfg.IVA_GENERAL / 100, 2)
            total     = round(base + iva_total, 2)
            # DOCCAB real: CODIGO, TIPO, SERIE, NUMERO, FECHA, CODCLIENTE, CODAGENTE,
            #              CODALMACEN, DESCRIPCION, OBSERVACIONES,
            #              IMPORTEBASE, IMPORTEIVA, IMPORTETOTAL, ESTADO
            doccab_rows.append((
                doc_id, tipo, "A", numero, fecha,
                cod_cli, cod_agente, 1,
                JDDCDocTipos.LABELS.get(tipo, ""),
                "",
                round(base, 2), iva_total, total,
                estado,
            ))

        self._cur.executemany(
            "INSERT INTO DOCCAB "
            "(CODIGO,TIPO,SERIE,NUMERO,FECHA,CODCLIENTE,CODAGENTE,CODALMACEN,"
            "DESCRIPCION,OBSERVACIONES,IMPORTEBASE,IMPORTEIVA,IMPORTETOTAL,ESTADO) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            doccab_rows
        )
        self._cur.executemany(
            "INSERT INTO DOCLIN "
            "(CODDOCUMENTO,CODIGO,CODARTICULO,DESCRIPCION,CANTIDAD,PRECIO,COSTE,DESCUENTOS) "
            "VALUES (?,?,?,?,?,?,?,?)",
            doclin_rows
        )
        return len(doccab_rows), len(doclin_rows)

    # ─── Caja ─────────────────────────────────────────────────────────────────

    def _seed_caja(self) -> int:
        # CAJA real: FECHA, CODAPUNTE, TIPO, IMPORTE, CONCEPTO, CODCLIENTE
        n = Cfg.SYNTHETIC_CAJA
        n_clientes = len(CLIENTES_DATA)
        rows = []
        for i in range(1, n + 1):
            importe = round(random.uniform(300.0, 8000.0), 2)
            rows.append((
                _rand_date(2),
                i,
                random.choice([1, 2]),
                importe if random.random() > 0.2 else -importe,
                random.choice(["Cobro factura", "Anticipo obra", "Pago proveedor", "Devolución"]),
                random.randint(1, n_clientes),
            ))
        self._cur.executemany(
            "INSERT INTO CAJA (FECHA,CODAPUNTE,TIPO,IMPORTE,CONCEPTO,CODCLIENTE) "
            "VALUES (?,?,?,?,?,?)",
            rows
        )
        return len(rows)

    # ─── Estalmacen ──────────────────────────────────────────────────────────

    def _seed_estalmacen(self) -> int:
        # ESTALMACEN real: CODIGO, FECHA, IMPCOSTE, IMPVENTA
        # Es una tabla de estadísticas de almacén por período (no por artículo)
        n = Cfg.SYNTHETIC_ESTALMACEN
        art_precios = {i + 1: ARTICULOS_DATA[i][3] for i in range(len(ARTICULOS_DATA))}
        rows = []
        for i in range(1, n + 1):
            # Simular totales de coste/venta por período
            base_precio = random.choice(list(art_precios.values()))
            qty = random.randint(1, 20)
            coste = round(base_precio * qty * random.uniform(0.55, 0.75), 2)
            venta = round(base_precio * qty * random.uniform(0.90, 1.15), 2)
            rows.append((
                i,
                _rand_date(2),
                coste,
                venta,
            ))
        self._cur.executemany(
            "INSERT INTO ESTALMACEN (CODIGO,FECHA,IMPCOSTE,IMPVENTA) "
            "VALUES (?,?,?,?)",
            rows
        )
        return len(rows)


# ─── Helper estado documento ──────────────────────────────────────────────────

def _doc_estado(tipo: int) -> int:
    """
    Genera estado realista según el tipo de documento.
    Presupuestos: mezcla aceptados/pendientes/rechazados.
    Facturas/albaranes: la mayoría procesados.
    """
    if tipo == JDDCDocTipos.PRESUPUESTO:
        return random.choices([0, 1, 2], weights=[45, 40, 15])[0]
    if tipo == JDDCDocTipos.FACTURA:
        return random.choices([0, 1], weights=[20, 80])[0]
    return random.choices([0, 1], weights=[30, 70])[0]
