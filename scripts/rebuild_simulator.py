"""
rebuild_simulator.py — Repuebla el simulador con datos reales de Firebird.

PRIVACIDAD: Este script NUNCA imprime valores de datos reales (DNIs, nombres,
importes…). Solo muestra conteos, tiempos y mensajes de estado.

EJECUCIÓN:
  cd bots/interjddcia
  python scripts/rebuild_simulator.py

PRINCIPIOS DEVIA:
  - Conexión fresca por tabla (evita drops de protocolo Firebird)
  - Excluye columnas BLOB (tipo 261) que corrompen la conexión
  - Reintento automático en caso de error de red
  - INSERT OR REPLACE: los datos reales sobreescriben los sintéticos
  - Nunca escribe en simulator.db sin petición explícita (DEVIA safety rule)
"""

import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Setup de paths ─────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent.parent
sys.path.insert(0, str(_HERE))

from backend.core.config.settings import settings

logging.basicConfig(level=logging.ERROR, format="%(message)s")

# ── Constantes ─────────────────────────────────────────────────────────────────

DB_SIM = str(_HERE / "backend" / "modules" / "db_simulator" / "data" / "simulator.db")

_FB_PARAMS = dict(
    host=settings.DB_HOST,
    port=int(settings.DB_PORT),
    database=settings.DB_NAME,
    user=settings.DB_USER,
    password=settings.DB_PASSWORD,
    charset="latin1",
)

# Firebird field_type codes
_BLOB_TYPE   = 261   # BLOB — se excluye siempre
_SKIP_TYPES  = {261} # tipos que no se transfieren

# Límites de captura por volumen (filas)
_LIMITS = {
    "tiny":   (500,    None),   # todas las filas
    "small":  (5_000,  2_000),
    "medium": (50_000, 3_000),
    "large":  (500_000,5_000),
    "mega":   (None,   1_000),
}

# Tablas de negocio prioritarias en orden topológico (padres antes que hijos)
CAPTURE_PLAN: List[Dict] = [
    # ── Tablas maestras (sin FK) ───────────────────────────────────────────────
    {"table": "UNIDADMEDIDA",   "limit": None},
    {"table": "MARCA",          "limit": None},
    {"table": "SECCION",        "limit": None},
    {"table": "TIPO",           "limit": None},
    {"table": "ALMACEN",        "limit": None},
    {"table": "FORMAPAG",       "limit": None},
    {"table": "AGENTE",         "limit": None},
    {"table": "SERIE",          "limit": 2_000},
    # ── Tablas con FK simples ──────────────────────────────────────────────────
    {"table": "ARTICULO",       "limit": 2_000},
    {"table": "CLIENTE",        "limit": 2_000},
    {"table": "PROVEED",        "limit": 2_000},
    {"table": "RECURSO",        "limit": 500},
    {"table": "CARACT",         "limit": None},
    {"table": "CARVALID",       "limit": None},
    # ── Documentos ────────────────────────────────────────────────────────────
    {"table": "DOCCAB",         "limit": 5_000},
    {"table": "DOCLIN",         "limit": 8_000},
    {"table": "DOCDESTINO",     "limit": 2_000},
    {"table": "DOCREF",         "limit": 3_000},
    # ── Stock y movimientos ────────────────────────────────────────────────────
    {"table": "ESTALMACEN",     "limit": 3_000},
    {"table": "EXISTENC",       "limit": 3_000},
    {"table": "CAJA",           "limit": 2_000},
    {"table": "COMPRA",         "limit": 2_000},
    # ── Proyectos y presupuestos ───────────────────────────────────────────────
    {"table": "PROYECTOS",      "limit": 1_000},
    {"table": "PRESUPROYE",     "limit": 2_000},
    # ── Históricos ────────────────────────────────────────────────────────────
    {"table": "HISTORICOPRECIOS","limit": 2_000},
    # ── Reparaciones ──────────────────────────────────────────────────────────
    {"table": "REPARA",         "limit": 2_000},
    {"table": "REPCAB",         "limit": 2_000},
    {"table": "REPLIN",         "limit": 3_000},
    # ── Financiero ────────────────────────────────────────────────────────────
    {"table": "RECIBO1",        "limit": 2_000},
    {"table": "RECIBO3",        "limit": 2_000},
    {"table": "COMPROMISOVENCIMIENTO", "limit": 2_000},
    {"table": "REMESA",         "limit": None},
]


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers Firebird
# ═══════════════════════════════════════════════════════════════════════════════

def _fb_connect():
    import firebirdsql
    return firebirdsql.connect(**_FB_PARAMS)


def get_non_blob_columns(table: str) -> List[str]:
    """
    Devuelve [col_name, ...] excluyendo columnas BLOB (RDB$FIELD_TYPE=261).
    Usa el filtro SQL directo que funciona correctamente con firebirdsql.
    """
    sql = (
        "SELECT TRIM(rf.RDB$FIELD_NAME) "
        "FROM RDB$RELATION_FIELDS rf "
        "JOIN RDB$FIELDS f ON rf.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME "
        "WHERE TRIM(rf.RDB$RELATION_NAME) = ? "
        "AND f.RDB$FIELD_TYPE != 261 "
        "ORDER BY rf.RDB$FIELD_POSITION"
    )
    conn = _fb_connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, (table,))
        return [r[0] for r in cur.fetchall() if r[0]]
    finally:
        try: conn.close()
        except: pass


def build_select_expressions(col_names: List[str]) -> Tuple[List[str], List[str]]:
    """Para el caso simple (sin BLOBs): select_exprs = col_names."""
    return list(col_names), list(col_names)


def fetch_rows(table: str, select_exprs: List[str], limit: Optional[int],
               retries: int = 3) -> Optional[List[tuple]]:
    """
    Fetch filas de Firebird con expresiones SELECT explícitas.
    Reintenta hasta `retries` veces con delay creciente.
    """
    col_part = ", ".join(select_exprs)
    lim_part = f"FIRST {limit} " if limit else ""
    sql = f"SELECT {lim_part}{col_part} FROM {table}"

    for attempt in range(retries):
        if attempt > 0:
            time.sleep(1.5 * attempt)
        try:
            conn = _fb_connect()
            try:
                cur = conn.cursor()
                cur.execute(sql)
                rows = cur.fetchall()
                return rows
            finally:
                try: conn.close()
                except: pass
        except Exception as e:
            if attempt == retries - 1:
                raise e
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers SQLite
# ═══════════════════════════════════════════════════════════════════════════════

def clean_val(v):
    """
    Normaliza valores de Firebird para SQLite:
      - bytes  → str latin1
      - date/datetime/time → ISO string
      - Decimal → float
      - Todo lo demás pasa tal cual (int, float, None, str)
    """
    import datetime, decimal
    if v is None:
        return None
    if isinstance(v, bytes):
        try:
            return v.decode("latin1", errors="replace").strip()
        except Exception:
            return ""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, datetime.time):
        return str(v)
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def ensure_table_and_columns(sim: sqlite3.Connection, table: str,
                              col_names: List[str]) -> None:
    """
    Garantiza que la tabla existe y tiene todas las columnas de Firebird.

    Si la tabla tiene columnas con NOT NULL que no están en col_names (esquema
    sintético distinto al real), la recrea con esquema Firebird (todo TEXT,
    sin restricciones NOT NULL) para que INSERT OR REPLACE funcione siempre.
    """
    exists = sim.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()

    if not exists:
        col_defs = ", ".join(f"{c} TEXT" for c in col_names)
        sim.execute(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs})")
        sim.commit()
        return

    # Detectar si hay restricciones NOT NULL en columnas que Firebird no proporciona
    pragma_rows = sim.execute(f"PRAGMA table_info({table})").fetchall()
    # pragma_rows: (cid, name, type, notnull, dflt_value, pk)
    fb_upper = {c.upper() for c in col_names}
    has_blocking_constraint = any(
        r[3] == 1 and r[4] is None and r[1].upper() not in fb_upper
        for r in pragma_rows
    )

    if has_blocking_constraint:
        # Recrear tabla con esquema Firebird (sin NOT NULL, sin FK restricciones)
        sim.execute(f"DROP TABLE IF EXISTS {table}")
        col_defs = ", ".join(f"{c} TEXT" for c in col_names)
        sim.execute(f"CREATE TABLE {table} ({col_defs})")
        sim.commit()
        return

    # Añadir columnas Firebird que falten (aditivo, jamás DROP)
    existing = {r[1].upper() for r in pragma_rows}
    for c in col_names:
        if c.upper() not in existing:
            try:
                sim.execute(f"ALTER TABLE {table} ADD COLUMN {c} TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
    sim.commit()


def insert_rows(sim: sqlite3.Connection, table: str,
                col_names: List[str], rows: List[tuple]) -> int:
    """Inserta filas con INSERT OR REPLACE. Devuelve filas insertadas."""
    ph  = ", ".join("?" for _ in col_names)
    sql = f"INSERT OR REPLACE INTO {table} ({', '.join(col_names)}) VALUES ({ph})"
    inserted = 0
    for row in rows:
        vals = [clean_val(v) for v in row]
        try:
            sim.execute(sql, vals)
            inserted += 1
        except Exception:
            pass
    sim.commit()
    return inserted


# ═══════════════════════════════════════════════════════════════════════════════
# Función principal de captura
# ═══════════════════════════════════════════════════════════════════════════════

def capture_table(table: str, limit: Optional[int]) -> Dict:
    """
    Captura una tabla de Firebird → SQLite.
    Devuelve dict con estadísticas (sin datos reales).
    """
    t0 = time.time()

    # 1. Obtener columnas (sin BLOBs) de Firebird
    try:
        time.sleep(0.2)
        col_names = get_non_blob_columns(table)
    except Exception as e:
        return {"table": table, "status": "error_meta", "error": str(e), "elapsed": time.time()-t0}

    if not col_names:
        return {"table": table, "status": "no_columns", "elapsed": time.time()-t0}

    select_exprs, col_names = build_select_expressions(col_names)

    # 2. Fetch de Firebird con conexión fresca y CAST de BLOBs
    try:
        time.sleep(0.2)
        rows = fetch_rows(table, select_exprs, limit, retries=3)
    except Exception as e:
        return {"table": table, "status": "error_fetch", "error": str(e)[:80],
                "cols": len(col_names), "elapsed": time.time()-t0}

    if rows is None:
        return {"table": table, "status": "no_rows", "elapsed": time.time()-t0}

    fb_count = len(rows)

    # 3. Insertar en SQLite
    sim = sqlite3.connect(DB_SIM, check_same_thread=False)
    sim.execute("PRAGMA foreign_keys = OFF")
    try:
        ensure_table_and_columns(sim, table, col_names)
        sim.execute(f"DELETE FROM {table}")
        sim.commit()
        inserted = insert_rows(sim, table, col_names, rows)
    finally:
        sim.close()

    return {
        "table":    table,
        "status":   "ok",
        "fb_rows":  fb_count,
        "inserted": inserted,
        "cols":     len(col_names),
        "elapsed":  round(time.time()-t0, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("REBUILD SIMULATOR - datos reales Firebird -> SQLite")
    print(f"Origen : {settings.DB_HOST}:{settings.DB_PORT}")
    print(f"Destino: {DB_SIM}")
    print("=" * 60)
    print()

    total_inserted = 0
    results = []

    for plan in CAPTURE_PLAN:
        table = plan["table"]
        limit = plan.get("limit")
        print(f"  [{table:<28}] ", end="", flush=True)
        res = capture_table(table, limit)
        results.append(res)

        if res["status"] == "ok":
            total_inserted += res["inserted"]
            print(
                f"OK  {res['fb_rows']:>6} FB | {res['inserted']:>6} SIM"
                f" | {res['cols']} cols | {res['elapsed']}s"
            )
        else:
            print(
                f"{'ERR':3s} {res['status']:<15}"
                f" {res.get('error','')[:40]}"
                f" ({res['elapsed']}s)"
            )

    print()
    print("=" * 60)
    print(f"TOTAL INSERTADO: {total_inserted:,} filas")
    ok = sum(1 for r in results if r["status"] == "ok")
    err = len(results) - ok
    print(f"Tablas OK: {ok} | Errores: {err}")
    print("=" * 60)

    # Estado final del simulador (sin datos reales)
    print()
    print("ESTADO FINAL DEL SIMULADOR:")
    sim = sqlite3.connect(DB_SIM)
    tables = sim.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    with_data = []
    for (t,) in tables:
        cnt = sim.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        if cnt > 0:
            with_data.append((t, cnt))
    sim.close()
    with_data.sort(key=lambda x: -x[1])
    for t, cnt in with_data:
        print(f"  {t:<32} {cnt:>8} filas")
    print(f"\n  Total tablas con datos: {len(with_data)}")


if __name__ == "__main__":
    main()
