"""Ejecuta el nuevo runner contra Firebird de solo lectura; guarda el informe."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import firebirdsql
    from backend.core.config.settings import settings
    from backend.modules.api_clone.utilidades.report import build_report

    connection = firebirdsql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
        user=settings.DB_USER, password=settings.DB_PASSWORD, charset="latin1",
        timeout=20, isolation_level=firebirdsql.ISOLATION_LEVEL_READ_COMMITED_RO)

    def execute(sql):
        assert sql.lstrip().upper().startswith("SELECT ")
        start = time.monotonic()
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()], round((time.monotonic()-start)*1000)
        finally:
            cursor.close()

    try:
        result = build_report(execute)
    finally:
        connection.close()
    output = ROOT / "docs" / "informe_integridad_ampliada_2026_09_21.txt"
    output.write_text(result, encoding="utf-8")
    print(str(output))
    print(result[:1800])



if __name__ == "__main__":
    main()
