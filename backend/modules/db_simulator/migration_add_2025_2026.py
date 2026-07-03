"""
migration_add_2025_2026.py — Añade datos de 2025 y 2026 al simulador.

SEGURIDAD:
  - NO llama a SyntheticSeeder ni seed_all().
  - NO borra datos existentes (no DELETE FROM).
  - Es idempotente: comprueba si 2025/2026 ya existen antes de insertar.
  - Usa INSERT directo sobre las tablas de simulator.db.

ESTRATEGIA:
  - Clona todos los documentos de 2024 → 2025 (fecha +1 año, CODIGOs nuevos)
  - Clona 2025 → 2026 (fecha +1 año adicional)
  - Para cada nuevo DOCCAB, genera sus DOCLIN correspondientes
  - Genera RECIBO1 para facturas de venta (TIPO=3)
  - Genera RECIBO3 para facturas de compra (TIPO=13)
  - Añade movimientos de CAJA para cobros/pagos de 2025

PRINCIPIOS:
  - Sin hardcoding: usa los datos reales de 2024 como plantilla
  - Sin valores mock: los importes y cantidades son los mismos (realismo de patrones)
  - Crecimiento realista: +5% en importes para 2025, +3% adicional para 2026
  - Integridad referencial: todos los CODDOCUMENTO en DOCLIN apuntan a DOCCAB existentes

EJECUCION:
  cd bots/interjddcia
  python backend/modules/db_simulator/migration_add_2025_2026.py
"""

import sqlite3
import os
import sys
from datetime import date, timedelta

# ─── Constantes ───────────────────────────────────────────────────────────────
DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "data", "simulator.db"
)

GROWTH_2025 = 1.05   # +5% sobre 2024
GROWTH_2026 = 1.08   # +8% sobre 2025 (≈+13.4% sobre 2024)


def _shift_year(fecha: str | None, years: int) -> str | None:
    """Desplaza una fecha YYYY-MM-DD en N años, manteniendo mes y día."""
    if not fecha:
        return None
    try:
        d = date.fromisoformat(fecha[:10])
        new_year = d.year + years
        # Manejar 29-feb en año no bisiesto
        try:
            return date(new_year, d.month, d.day).isoformat()
        except ValueError:
            return date(new_year, d.month, 28).isoformat()
    except (ValueError, TypeError):
        return fecha


def _scale(value: float | None, factor: float) -> float | None:
    """Aplica el factor de crecimiento redondeando a 2 decimales."""
    if value is None:
        return None
    return round(value * factor, 2)


def run_migration(db_path: str = DB_PATH) -> None:
    print(f"[MIGRATION] Abriendo: {db_path}")
    if not os.path.exists(db_path):
        print("[MIGRATION] ERROR: simulator.db no encontrado. Abortando.")
        sys.exit(1)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ── Verificar si ya existen datos de 2025/2026 ────────────────────────────
    cur.execute("SELECT COUNT(*) FROM DOCCAB WHERE SUBSTR(FECHA,1,4)='2025'")
    already_2025 = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM DOCCAB WHERE SUBSTR(FECHA,1,4)='2026'")
    already_2026 = cur.fetchone()[0]

    if already_2025 > 0:
        print(f"[MIGRATION] DOCCAB ya tiene {already_2025} filas de 2025 — saltando 2025.")
    if already_2026 > 0:
        print(f"[MIGRATION] DOCCAB ya tiene {already_2026} filas de 2026 — saltando 2026.")

    if already_2025 > 0 and already_2026 > 0:
        print("[MIGRATION] Nada que hacer. Para forzar, elimina las filas manualmente.")
        con.close()
        return

    # ── Leer todos los documentos de 2024 ─────────────────────────────────────
    cur.execute("""
        SELECT CODIGO, TIPO, SERIE, NUMERO, REVISION, FECHA, FECHAEMISION,
               CODCLIENTE, CODAGENTE, CODALMACEN, CODALMACENORIGEN, CODFORMAPAGO,
               CODFORMAENVIO, CODASIENTO, DESCRIPCION, DESCUENTOS, DESCUENTOSPP,
               BULTOS, PORTES, PORTESVENTA, GASTOSVARIOS, PORTESTIPO, OBSERVACIONES,
               REGIMENIVA, CRITERIOIVACAJA, PENDIENTEDEVENGO, AJUSTEBASE, AJUSTEIVA,
               IMPORTEBRUTO, IMPORTEDESCUENTO, IMPORTEBASE, IMPORTEIVA,
               IMPORTERECEQUIV, IMPORTEIRPF, IMPORTETOTAL, IMPORTEENTREGADO,
               CODPROYECTO, CODPROYSUBCONTRATA, CODESTACION, CODMESA, CODTURNO,
               HORA, ESTADOPEND, ESTADOPENDVENCOM, CODTIPODIR, CODFABRICA,
               CODREPARA, REFERENCIAEXTERNA, NOFACTURABLE, TIPOFACTURA, ESTADO
        FROM DOCCAB
        WHERE SUBSTR(FECHA,1,4)='2024'
        ORDER BY CODIGO
    """)
    docs_2024 = [dict(r) for r in cur.fetchall()]
    max_codigo_2024 = max(d['CODIGO'] for d in docs_2024) if docs_2024 else 0
    print(f"[MIGRATION] {len(docs_2024)} documentos de 2024 encontrados (max CODIGO={max_codigo_2024})")

    # ── Leer todas las líneas de 2024 ─────────────────────────────────────────
    cur.execute("""
        SELECT l.CODDOCUMENTO, l.CODIGO, l.NIVEL, l.CODARTICULO, l.CANTIDAD,
               l.UNIDADMEDIDACANTIDAD, l.UNIDADMEDIDAFACTOR, l.PRECIO, l.COSTE,
               l.COSTEINDIRECTO, l.TRIBUTACIONIVA, l.TIPOIVA, l.TIPOIRPF,
               l.TIPORECEQUIV, l.DESCUENTOS, l.CODALMACEN, l.PORTES,
               l.GASTOSVARIOS, l.IGNORARPENDIENTES, l.DESCRIPCION,
               l.CODDOCUMENTOORIGEN, l.CODLINEAORIGEN, l.PORCENTAJECOMISION,
               l.IMPORTEDESCUENTO, l.TIPOLINEA
        FROM DOCLIN l
        INNER JOIN DOCCAB c ON l.CODDOCUMENTO = c.CODIGO
        WHERE SUBSTR(c.FECHA,1,4)='2024'
        ORDER BY l.CODDOCUMENTO, l.CODIGO
    """)
    lines_2024 = [dict(r) for r in cur.fetchall()]
    print(f"[MIGRATION] {len(lines_2024)} líneas de 2024 encontradas")

    # ── Leer recibos existentes ────────────────────────────────────────────────
    cur.execute("SELECT MAX(CODIGO) FROM RECIBO1")
    max_recibo1 = cur.fetchone()[0] or 0
    cur.execute("SELECT MAX(CODIGO) FROM RECIBO3")
    max_recibo3 = cur.fetchone()[0] or 0
    cur.execute("SELECT MAX(CODAPUNTE) FROM CAJA")
    max_caja = cur.fetchone()[0] or 0

    # ══════════════════════════════════════════════════════════════════════════
    # GENERAR 2025
    # ══════════════════════════════════════════════════════════════════════════
    if already_2025 == 0:
        print("[MIGRATION] Generando datos 2025...")
        offset_2025 = max_codigo_2024
        docs_2025 = []
        codigo_map_2025 = {}  # old CODIGO → new CODIGO

        for doc in docs_2024:
            new_cod = doc['CODIGO'] + offset_2025
            codigo_map_2025[doc['CODIGO']] = new_cod
            new_doc = dict(doc)
            new_doc['CODIGO'] = new_cod
            new_doc['FECHA'] = _shift_year(doc['FECHA'], 1)
            new_doc['FECHAEMISION'] = _shift_year(doc.get('FECHAEMISION'), 1)
            # Aplicar crecimiento del 5%
            for campo in ('IMPORTEBRUTO', 'IMPORTEDESCUENTO', 'IMPORTEBASE',
                          'IMPORTEIVA', 'IMPORTERECEQUIV', 'IMPORTEIRPF',
                          'IMPORTETOTAL', 'IMPORTEENTREGADO',
                          'AJUSTEBASE', 'AJUSTEIVA', 'PORTES', 'PORTESVENTA',
                          'GASTOSVARIOS'):
                new_doc[campo] = _scale(doc.get(campo), GROWTH_2025)
            docs_2025.append(new_doc)

        # Insertar DOCCAB 2025
        cols = list(docs_2025[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        col_names = ", ".join(cols)
        insert_sql = f"INSERT INTO DOCCAB ({col_names}) VALUES ({placeholders})"
        cur.executemany(insert_sql, [list(d.values()) for d in docs_2025])
        print(f"[MIGRATION]   -> {len(docs_2025)} filas insertadas en DOCCAB (2025)")

        # Insertar DOCLIN 2025
        lines_2025 = []
        for line in lines_2024:
            old_cod = line['CODDOCUMENTO']
            new_cod = codigo_map_2025.get(old_cod)
            if new_cod is None:
                continue
            new_line = dict(line)
            new_line['CODDOCUMENTO'] = new_cod
            # Aplicar crecimiento al precio
            new_line['PRECIO'] = _scale(line.get('PRECIO'), GROWTH_2025)
            new_line['COSTE'] = _scale(line.get('COSTE'), GROWTH_2025)
            new_line['IMPORTEDESCUENTO'] = _scale(line.get('IMPORTEDESCUENTO'), GROWTH_2025)
            lines_2025.append(new_line)

        if lines_2025:
            lcols = list(lines_2025[0].keys())
            lph = ", ".join("?" for _ in lcols)
            lcn = ", ".join(lcols)
            cur.executemany(
                f"INSERT INTO DOCLIN ({lcn}) VALUES ({lph})",
                [list(l.values()) for l in lines_2025]
            )
            print(f"[MIGRATION]   -> {len(lines_2025)} líneas insertadas en DOCLIN (2025)")

        # Insertar RECIBO1 para facturas de venta 2025 (TIPO=3)
        facturas_venta_2025 = [d for d in docs_2025 if d['TIPO'] == 3]
        recibo1_rows = []
        for i, doc in enumerate(facturas_venta_2025):
            fecha_venc = _shift_year(doc['FECHA'], 0)  # misma fecha como vencimiento (simplificado)
            importe = doc.get('IMPORTETOTAL') or 0
            recibo1_rows.append({
                'CODIGO': max_recibo1 + i + 1,
                'CODPAGA': doc['CODCLIENTE'] or 0,
                'CODDOCUMENTO': doc['CODIGO'],
                'FECHA': doc['FECHA'],
                'FECHAVENC': fecha_venc,
                'IMPORTE': importe,
                'COBRADO': importe,
                'PENDIENTE': 0.0,
                'ESTADO': 1,
                'ACTIVO': 1,
                'DEVOLUCION': 0,
                'SERIE': doc.get('SERIE', 'A'),
                'NUMERO': doc.get('NUMERO', 0),
                'CODFORMAPAGO': doc.get('CODFORMAPAGO', 0) or 0,
                'OBSERVACIONES': None,
                'CODUSUARIO': 0,
                'CODASIENTO': 0,
            })
        max_recibo1 += len(recibo1_rows)
        if recibo1_rows:
            rcols = list(recibo1_rows[0].keys())
            rph = ", ".join("?" for _ in rcols)
            rcn = ", ".join(rcols)
            cur.executemany(
                f"INSERT INTO RECIBO1 ({rcn}) VALUES ({rph})",
                [list(r.values()) for r in recibo1_rows]
            )
            print(f"[MIGRATION]   -> {len(recibo1_rows)} recibos insertados en RECIBO1 (2025)")

        # Insertar RECIBO3 para facturas de compra 2025 (TIPO=13)
        facturas_compra_2025 = [d for d in docs_2025 if d['TIPO'] == 13]
        recibo3_rows = []
        for i, doc in enumerate(facturas_compra_2025):
            importe = doc.get('IMPORTETOTAL') or 0
            recibo3_rows.append({
                'CODIGO': max_recibo3 + i + 1,
                'CODPAGADOR': doc.get('CODCLIENTE') or 0,
                'CODDOCUMENTO': doc['CODIGO'],
                'FECHA': doc['FECHA'],
                'FECHAVENC': doc['FECHA'],
                'IMPORTE': importe,
                'PAGADO': importe,
                'PENDIENTE': 0.0,
                'ESTADO': 1,
                'ACTIVO': 1,
                'DEVOLUCION': 0,
                'SERIE': doc.get('SERIE', 'P'),
                'NUMERO': doc.get('NUMERO', 0),
                'CODFORMAPAGO': doc.get('CODFORMAPAGO', 0) or 0,
                'OBSERVACIONES': None,
                'CODUSUARIO': 0,
                'CODASIENTO': 0,
            })
        max_recibo3 += len(recibo3_rows)
        if recibo3_rows:
            rcols = list(recibo3_rows[0].keys())
            rph = ", ".join("?" for _ in rcols)
            rcn = ", ".join(rcols)
            cur.executemany(
                f"INSERT INTO RECIBO3 ({rcn}) VALUES ({rph})",
                [list(r.values()) for r in recibo3_rows]
            )
            print(f"[MIGRATION]   -> {len(recibo3_rows)} recibos insertados en RECIBO3 (2025)")

        # Insertar entradas de CAJA para cobros de facturas de venta 2025
        caja_2025 = []
        for i, doc in enumerate(facturas_venta_2025[:50]):  # máx 50 entradas de caja
            importe = doc.get('IMPORTETOTAL') or 0
            caja_2025.append({
                'FECHA': doc['FECHA'],
                'CODAPUNTE': max_caja + i + 1,
                'TIPO': 2,  # cobro
                'CODCUENTA': 0,
                'DEBE': importe,
                'IMPORTE': 0.0,
                'GASTOS': 0.0,
                'DESCRIPCION': 'Cobro factura',
                'CONCEPTO': None,
                'CODDOCUMENTO': doc['CODIGO'],
                'CODRECIBO': 0,
                'CODCLIENTE': doc['CODCLIENTE'] or 0,
                'CODUSUARIO': 0,
                'CODASIENTO': 0,
                'CODCUENTADESTINO': 0,
                'CUENTACONTABLE': None,
                'CODTFPAGO': 0,
                'CODESTACION': 0,
                'CODARQUEO': 0,
                'HORA': None,
                'SERIE': doc.get('SERIE', 'A'),
            })
        max_caja += len(caja_2025)
        if caja_2025:
            ccols = list(caja_2025[0].keys())
            cph = ", ".join("?" for _ in ccols)
            ccn = ", ".join(ccols)
            cur.executemany(
                f"INSERT INTO CAJA ({ccn}) VALUES ({cph})",
                [list(c.values()) for c in caja_2025]
            )
            print(f"[MIGRATION]   -> {len(caja_2025)} movimientos insertados en CAJA (2025)")

    # ══════════════════════════════════════════════════════════════════════════
    # GENERAR 2026
    # ══════════════════════════════════════════════════════════════════════════
    if already_2026 == 0:
        print("[MIGRATION] Generando datos 2026...")

        # Leer los docs de 2025 que acabamos de insertar (o los existentes)
        cur.execute("""
            SELECT CODIGO, TIPO, SERIE, NUMERO, REVISION, FECHA, FECHAEMISION,
                   CODCLIENTE, CODAGENTE, CODALMACEN, CODALMACENORIGEN, CODFORMAPAGO,
                   CODFORMAENVIO, CODASIENTO, DESCRIPCION, DESCUENTOS, DESCUENTOSPP,
                   BULTOS, PORTES, PORTESVENTA, GASTOSVARIOS, PORTESTIPO, OBSERVACIONES,
                   REGIMENIVA, CRITERIOIVACAJA, PENDIENTEDEVENGO, AJUSTEBASE, AJUSTEIVA,
                   IMPORTEBRUTO, IMPORTEDESCUENTO, IMPORTEBASE, IMPORTEIVA,
                   IMPORTERECEQUIV, IMPORTEIRPF, IMPORTETOTAL, IMPORTEENTREGADO,
                   CODPROYECTO, CODPROYSUBCONTRATA, CODESTACION, CODMESA, CODTURNO,
                   HORA, ESTADOPEND, ESTADOPENDVENCOM, CODTIPODIR, CODFABRICA,
                   CODREPARA, REFERENCIAEXTERNA, NOFACTURABLE, TIPOFACTURA, ESTADO
            FROM DOCCAB
            WHERE SUBSTR(FECHA,1,4)='2025'
            ORDER BY CODIGO
        """)
        docs_2025_db = [dict(r) for r in cur.fetchall()]
        max_codigo_2025 = max(d['CODIGO'] for d in docs_2025_db) if docs_2025_db else max_codigo_2024

        cur.execute("""
            SELECT l.CODDOCUMENTO, l.CODIGO, l.NIVEL, l.CODARTICULO, l.CANTIDAD,
                   l.UNIDADMEDIDACANTIDAD, l.UNIDADMEDIDAFACTOR, l.PRECIO, l.COSTE,
                   l.COSTEINDIRECTO, l.TRIBUTACIONIVA, l.TIPOIVA, l.TIPOIRPF,
                   l.TIPORECEQUIV, l.DESCUENTOS, l.CODALMACEN, l.PORTES,
                   l.GASTOSVARIOS, l.IGNORARPENDIENTES, l.DESCRIPCION,
                   l.CODDOCUMENTOORIGEN, l.CODLINEAORIGEN, l.PORCENTAJECOMISION,
                   l.IMPORTEDESCUENTO, l.TIPOLINEA
            FROM DOCLIN l
            INNER JOIN DOCCAB c ON l.CODDOCUMENTO = c.CODIGO
            WHERE SUBSTR(c.FECHA,1,4)='2025'
            ORDER BY l.CODDOCUMENTO, l.CODIGO
        """)
        lines_2025_db = [dict(r) for r in cur.fetchall()]

        offset_2026 = max_codigo_2025
        docs_2026 = []
        codigo_map_2026 = {}

        for doc in docs_2025_db:
            new_cod = doc['CODIGO'] + (offset_2026 - max_codigo_2024 - (max_codigo_2024 - (docs_2024[0]['CODIGO'] - 1) if docs_2024 else 0))
            # Simplified: just add max_codigo_2024 again
            new_cod = doc['CODIGO'] + max_codigo_2024
            codigo_map_2026[doc['CODIGO']] = new_cod
            new_doc = dict(doc)
            new_doc['CODIGO'] = new_cod
            new_doc['FECHA'] = _shift_year(doc['FECHA'], 1)
            new_doc['FECHAEMISION'] = _shift_year(doc.get('FECHAEMISION'), 1)
            for campo in ('IMPORTEBRUTO', 'IMPORTEDESCUENTO', 'IMPORTEBASE',
                          'IMPORTEIVA', 'IMPORTERECEQUIV', 'IMPORTEIRPF',
                          'IMPORTETOTAL', 'IMPORTEENTREGADO',
                          'AJUSTEBASE', 'AJUSTEIVA', 'PORTES', 'PORTESVENTA',
                          'GASTOSVARIOS'):
                new_doc[campo] = _scale(doc.get(campo), GROWTH_2026)
            docs_2026.append(new_doc)

        # Verificar que no haya colisión de CODIGOs
        existing_codigos = set()
        cur.execute("SELECT CODIGO FROM DOCCAB")
        for r in cur.fetchall():
            existing_codigos.add(r[0])

        docs_2026_ok = []
        for doc in docs_2026:
            if doc['CODIGO'] in existing_codigos:
                # Reasignar
                cur.execute("SELECT MAX(CODIGO) FROM DOCCAB")
                current_max = cur.fetchone()[0] or 0
                doc['CODIGO'] = current_max + 1
            existing_codigos.add(doc['CODIGO'])
            docs_2026_ok.append(doc)

        cols = list(docs_2026_ok[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        col_names = ", ".join(cols)
        cur.executemany(
            f"INSERT INTO DOCCAB ({col_names}) VALUES ({placeholders})",
            [list(d.values()) for d in docs_2026_ok]
        )
        print(f"[MIGRATION]   -> {len(docs_2026_ok)} filas insertadas en DOCCAB (2026)")

        # DOCLIN 2026
        lines_2026 = []
        for line in lines_2025_db:
            old_cod = line['CODDOCUMENTO']
            # Find matching doc in docs_2025_db to get new 2026 codigo
            new_cod = None
            for doc in docs_2026_ok:
                if doc.get('_src_codigo') == old_cod:
                    new_cod = doc['CODIGO']
                    break
            if new_cod is None:
                # Find the 2025 doc and compute the 2026 codigo
                for doc_25 in docs_2025_db:
                    if doc_25['CODIGO'] == old_cod:
                        new_cod = doc_25['CODIGO'] + max_codigo_2024
                        break
            if new_cod is None or new_cod not in existing_codigos:
                continue
            new_line = dict(line)
            new_line['CODDOCUMENTO'] = new_cod
            new_line['PRECIO'] = _scale(line.get('PRECIO'), GROWTH_2026)
            new_line['COSTE'] = _scale(line.get('COSTE'), GROWTH_2026)
            new_line['IMPORTEDESCUENTO'] = _scale(line.get('IMPORTEDESCUENTO'), GROWTH_2026)
            lines_2026.append(new_line)

        if lines_2026:
            lcols = list(lines_2026[0].keys())
            lph = ", ".join("?" for _ in lcols)
            lcn = ", ".join(lcols)
            cur.executemany(
                f"INSERT INTO DOCLIN ({lcn}) VALUES ({lph})",
                [list(l.values()) for l in lines_2026]
            )
            print(f"[MIGRATION]   -> {len(lines_2026)} líneas insertadas en DOCLIN (2026)")

        # RECIBO1 para facturas de venta 2026 (TIPO=3)
        facturas_venta_2026 = [d for d in docs_2026_ok if d['TIPO'] == 3]
        cur.execute("SELECT MAX(CODIGO) FROM RECIBO1")
        max_r1 = cur.fetchone()[0] or 0
        recibo1_2026 = []
        for i, doc in enumerate(facturas_venta_2026):
            importe = doc.get('IMPORTETOTAL') or 0
            recibo1_2026.append({
                'CODIGO': max_r1 + i + 1,
                'CODPAGA': doc['CODCLIENTE'] or 0,
                'CODDOCUMENTO': doc['CODIGO'],
                'FECHA': doc['FECHA'],
                'FECHAVENC': doc['FECHA'],
                'IMPORTE': importe,
                'COBRADO': importe,
                'PENDIENTE': 0.0,
                'ESTADO': 1,
                'ACTIVO': 1,
                'DEVOLUCION': 0,
                'SERIE': doc.get('SERIE', 'A'),
                'NUMERO': doc.get('NUMERO', 0),
                'CODFORMAPAGO': doc.get('CODFORMAPAGO', 0) or 0,
                'OBSERVACIONES': None,
                'CODUSUARIO': 0,
                'CODASIENTO': 0,
            })
        if recibo1_2026:
            rcols = list(recibo1_2026[0].keys())
            cur.executemany(
                f"INSERT INTO RECIBO1 ({', '.join(rcols)}) VALUES ({', '.join('?' for _ in rcols)})",
                [list(r.values()) for r in recibo1_2026]
            )
            print(f"[MIGRATION]   -> {len(recibo1_2026)} recibos insertados en RECIBO1 (2026)")

        # RECIBO3 para facturas de compra 2026 (TIPO=13)
        facturas_compra_2026 = [d for d in docs_2026_ok if d['TIPO'] == 13]
        cur.execute("SELECT MAX(CODIGO) FROM RECIBO3")
        max_r3 = cur.fetchone()[0] or 0
        recibo3_2026 = []
        for i, doc in enumerate(facturas_compra_2026):
            importe = doc.get('IMPORTETOTAL') or 0
            recibo3_2026.append({
                'CODIGO': max_r3 + i + 1,
                'CODPAGADOR': doc.get('CODCLIENTE') or 0,
                'CODDOCUMENTO': doc['CODIGO'],
                'FECHA': doc['FECHA'],
                'FECHAVENC': doc['FECHA'],
                'IMPORTE': importe,
                'PAGADO': importe,
                'PENDIENTE': 0.0,
                'ESTADO': 1,
                'ACTIVO': 1,
                'DEVOLUCION': 0,
                'SERIE': doc.get('SERIE', 'P'),
                'NUMERO': doc.get('NUMERO', 0),
                'CODFORMAPAGO': doc.get('CODFORMAPAGO', 0) or 0,
                'OBSERVACIONES': None,
                'CODUSUARIO': 0,
                'CODASIENTO': 0,
            })
        if recibo3_2026:
            rcols = list(recibo3_2026[0].keys())
            cur.executemany(
                f"INSERT INTO RECIBO3 ({', '.join(rcols)}) VALUES ({', '.join('?' for _ in rcols)})",
                [list(r.values()) for r in recibo3_2026]
            )
            print(f"[MIGRATION]   -> {len(recibo3_2026)} recibos insertados en RECIBO3 (2026)")

    # ── Commit ────────────────────────────────────────────────────────────────
    con.commit()
    con.close()

    # ── Resumen final ─────────────────────────────────────────────────────────
    con2 = sqlite3.connect(db_path)
    cur2 = con2.cursor()
    cur2.execute("""
        SELECT SUBSTR(FECHA,1,4) AS ANIO, COUNT(*) AS N,
               ROUND(SUM(IMPORTETOTAL),2) AS TOTAL
        FROM DOCCAB
        GROUP BY ANIO ORDER BY ANIO
    """)
    print()
    print("[MIGRATION] Estado final DOCCAB:")
    for r in cur2.fetchall():
        print(f"  {r[0]}: {r[1]} docs, importe={r[2]} EUR")

    cur2.execute("SELECT COUNT(*) FROM DOCLIN")
    print(f"[MIGRATION] DOCLIN total: {cur2.fetchone()[0]} lineas")
    cur2.execute("SELECT COUNT(*) FROM RECIBO1")
    print(f"[MIGRATION] RECIBO1 total: {cur2.fetchone()[0]} recibos")
    cur2.execute("SELECT COUNT(*) FROM RECIBO3")
    print(f"[MIGRATION] RECIBO3 total: {cur2.fetchone()[0]} recibos")
    cur2.execute("SELECT COUNT(*) FROM CAJA")
    print(f"[MIGRATION] CAJA total: {cur2.fetchone()[0]} movimientos")
    con2.close()
    print("[MIGRATION] Completado.")


if __name__ == "__main__":
    run_migration()
