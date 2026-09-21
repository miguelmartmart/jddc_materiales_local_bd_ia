"""Conexión de auditoría: la transacción Firebird impide escrituras."""
from contextlib import contextmanager
import time


@contextmanager
def open_reader():
    import firebirdsql
    from backend.core.config.settings import settings
    connection = firebirdsql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
        user=settings.DB_USER, password=settings.DB_PASSWORD, charset="latin1", timeout=20,
        isolation_level=firebirdsql.ISOLATION_LEVEL_READ_COMMITED_RO)
    def execute(sql):
        if not sql.lstrip().upper().startswith("SELECT ") or ";" in sql:
            raise ValueError("La auditoría solo admite una consulta SELECT")
        start = time.monotonic()
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            fields = [col[0] for col in cursor.description]
            return [dict(zip(fields, row)) for row in cursor.fetchall()], round((time.monotonic()-start)*1000)
        finally:
            cursor.close()
    try:
        yield execute
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
