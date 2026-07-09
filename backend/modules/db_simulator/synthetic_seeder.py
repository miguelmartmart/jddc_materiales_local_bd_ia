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
        counts["PROYECTOS"]   = self._seed_proyectos()
        counts["DOCCAB"], counts["DOCLIN"] = self._seed_documentos()
        counts["CAJA"]        = self._seed_caja()
        counts["ESTALMACEN"]  = self._seed_estalmacen()
        counts["PRESUPROYE"]  = self._seed_presuproye()

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

    # ─── Proyectos y certificaciones ─────────────────────────────────────────

    def _seed_proyectos(self) -> int:
        """
        Genera proyectos/obras sintéticos realistas para JDDC.
        Incluye datos de retención y tipo de aval para demostrar el módulo.
        """
        # Limpiar primero (no estaba en _clear_all para no romper FK)
        try:
            self._cur.execute("DELETE FROM PRESUPROYE")
        except Exception:
            pass
        try:
            self._cur.execute("DELETE FROM PROYECTOS")
        except Exception:
            pass

        today = date.today()
        proyectos = [
            # (CODIGO, NOMBRE, CLIENTE, FECHAINICIO, FECHAFIN, TIPOOBRA, TIPORETENCION, PORCRETENCION)
            # TIPORETENCION: 0=sin, 1=aval previo, 2=aval al finalizar, 3=sin aval
            ("P2024-001", "Instalación climatización Nave Industrial Etosa",
             "ETOSA S.A.", "2024-01-15", "2024-08-30", 1, 2, 5.0),
            ("P2024-002", "Mantenimiento anual HVAC Oficinas Centrales",
             "Grupo Empresarial Norte S.L.", "2024-03-01", "2025-02-28", 2, 0, 0.0),
            ("P2024-003", "Instalación VRF Edificio Residencial Torre Sur",
             "Promotora Inmobiliaria Sur S.A.", "2024-05-10", "2024-12-15", 1, 1, 5.0),
            ("P2024-004", "Renovación sistema frigorífico Almacén Logístico",
             "Logística Mediterránea S.L.", "2024-06-01", "2024-09-30", 1, 3, 5.0),
            ("P2025-001", "Climatización Centro Comercial Plaza Mayor",
             "Inversiones Comerciales S.A.", "2025-01-10", "2025-07-31", 1, 2, 5.0),
            ("P2025-002", "Instalación geotérmica Complejo Hotelero",
             "Hoteles del Mediterráneo S.L.", "2025-02-15", "2025-11-30", 1, 1, 3.0),
            ("P2025-003", "Mantenimiento preventivo Hospitales Zona Norte",
             "Consorcio Sanitario Regional", "2025-01-01", "2025-12-31", 2, 0, 0.0),
            ("P2025-004", "Instalación solar térmica Polideportivo Municipal",
             "Ayuntamiento de Murcia", "2025-03-01", "2025-09-30", 1, 3, 5.0),
        ]

        rows = []
        for cod, nombre, cliente, fi, ff, tipoobra, tiporetencion, porcretencion in proyectos:
            rows.append((
                cod, nombre, cliente, fi, fi, ff,
                tipoobra, tiporetencion, porcretencion, "N"
            ))

        self._cur.executemany(
            "INSERT OR IGNORE INTO PROYECTOS "
            "(CODIGO,NOMBRE,CLIENTE,FECHAINICIO,FECHAINICIOPREV,FECHAFIN,"
            "TIPOOBRA,TIPORETENCION,PORCRETENCION,ESGASTOSGENERALES) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows
        )
        logger.info(f"[SEEDER] Proyectos insertados: {len(rows)}")
        return len(rows)

    def _seed_presuproye(self) -> int:
        """
        Vincula presupuestos (DOCCAB TIPO=0) a proyectos.
        Se ejecuta DESPUÉS de _seed_documentos para tener los IDs de DOCCAB.
        """
        try:
            # Obtener presupuestos generados
            self._cur.execute("SELECT CODIGO FROM DOCCAB WHERE TIPO=0 ORDER BY CODIGO")
            presupuestos = [r[0] for r in self._cur.fetchall()]

            # Obtener proyectos
            self._cur.execute("SELECT CODIGO FROM PROYECTOS ORDER BY CODIGO")
            proyectos = [r[0] for r in self._cur.fetchall()]

            if not presupuestos or not proyectos:
                return 0

            rows = []
            # Asignar 1-3 presupuestos por proyecto
            pres_idx = 0
            for cod_proy in proyectos:
                n_pres = random.randint(1, 3)
                for _ in range(n_pres):
                    if pres_idx >= len(presupuestos):
                        break
                    rows.append((cod_proy, presupuestos[pres_idx], None))
                    pres_idx += 1

            self._cur.executemany(
                "INSERT OR IGNORE INTO PRESUPROYE "
                "(CODPROYECTO,CODPRESUPUESTO,CODPROYSUBCONTRATA) "
                "VALUES (?,?,?)",
                rows
            )
            logger.info(f"[SEEDER] PRESUPROYE insertados: {len(rows)}")
            return len(rows)
        except Exception as e:
            logger.warning(f"[SEEDER] Error en _seed_presuproye: {e}")
            return 0

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

        # Proyectos disponibles para vincular certificaciones
        # Se leen de la tabla ya insertada por _seed_proyectos()
        _proyectos_codigos: List[str] = []
        try:
            self._cur.execute("SELECT CODIGO FROM PROYECTOS ORDER BY CODIGO")
            _proyectos_codigos = [r[0] for r in self._cur.fetchall()]
        except Exception:
            pass

        doccab_rows: List[tuple] = []
        doclin_rows: List[tuple] = []
        numero_por_tipo: dict = {}

        # Contador de certificaciones por proyecto (para descripción realista)
        _cert_count: dict = {}

        for doc_id in range(1, n_docs + 1):
            tipo       = tipos_list[doc_id - 1]
            numero_por_tipo[tipo] = numero_por_tipo.get(tipo, 0) + 1
            numero     = numero_por_tipo[tipo]
            fecha      = _rand_date(2)
            cod_cli    = random.randint(1, n_clientes)
            cod_agente = random.choice(agente_ids)
            estado     = _doc_estado(tipo)

            # ── Vincular facturas a proyectos (certificaciones de obra) ──────
            # ~40% de las facturas son certificaciones de obra (tienen CODPROYECTO)
            cod_proyecto = None
            descripcion_doc = JDDCDocTipos.LABELS.get(tipo, "")
            if tipo == JDDCDocTipos.FACTURA and _proyectos_codigos and random.random() < 0.40:
                cod_proyecto = random.choice(_proyectos_codigos)
                _cert_count[cod_proyecto] = _cert_count.get(cod_proyecto, 0) + 1
                n_cert = _cert_count[cod_proyecto]
                descripcion_doc = f"Certificación {n_cert} — {cod_proyecto}"

            # Generar líneas (2-5 por documento)
            n_lineas   = random.randint(2, 5)
            arts_sel   = random.sample(art_ids, min(n_lineas, len(art_ids)))
            base       = 0.0
            for linia_num, art_id in enumerate(arts_sel, start=1):
                precio    = art_precios.get(art_id, 100.0)
                # Certificaciones tienen importes más altos (obras grandes)
                multiplier = random.uniform(2.0, 8.0) if cod_proyecto else random.uniform(0.9, 1.15)
                precio    = round(precio * multiplier, 2)
                cantidad  = round(random.choice([1.0, 1.0, 1.0, 2.0, 3.0, 0.5]), 2)
                descuento = round(random.choice([0.0, 0.0, 5.0, 10.0, 15.0]), 2)
                importe   = round(precio * cantidad * (1 - descuento / 100), 2)
                base     += importe
                doclin_rows.append((
                    doc_id, linia_num,
                    str(art_id),
                    art_nombres.get(art_id, ""),
                    cantidad, precio,
                    round(precio * 0.65, 2),
                    descuento,
                ))

            iva_total = round(base * Cfg.IVA_GENERAL / 100, 2)
            total     = round(base + iva_total, 2)

            # DOCCAB con CODPROYECTO para certificaciones
            doccab_rows.append((
                doc_id, tipo, "A", numero, fecha,
                cod_cli, cod_agente, 1,
                descripcion_doc,
                "",
                round(base, 2), iva_total, total,
                estado,
                cod_proyecto,  # CODPROYECTO — None para docs sin proyecto
            ))

        self._cur.executemany(
            "INSERT INTO DOCCAB "
            "(CODIGO,TIPO,SERIE,NUMERO,FECHA,CODCLIENTE,CODAGENTE,CODALMACEN,"
            "DESCRIPCION,OBSERVACIONES,IMPORTEBASE,IMPORTEIVA,IMPORTETOTAL,ESTADO,CODPROYECTO) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            doccab_rows
        )
        self._cur.executemany(
            "INSERT INTO DOCLIN "
            "(CODDOCUMENTO,CODIGO,CODARTICULO,DESCRIPCION,CANTIDAD,PRECIO,COSTE,DESCUENTOS) "
            "VALUES (?,?,?,?,?,?,?,?)",
            doclin_rows
        )
        # Log de certificaciones generadas
        total_cert = sum(_cert_count.values())
        logger.info(
            f"[SEEDER] Certificaciones generadas: {total_cert} "
            f"en {len(_cert_count)} proyectos → {_cert_count}"
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
