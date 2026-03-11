# Firebird SQL Queries — Metadata Builder Module
# Consultas para introspección del esquema de la base de datos Firebird.
# SOLO lectura de metadatos del sistema (RDB$*). Nunca datos de negocio.
# Referencia: Firebird 2.5 System Tables

# ─── Tablas de usuario ────────────────────────────────────────────────────────

QUERY_USER_TABLES = """
    SELECT
        TRIM(RDB$RELATION_NAME) AS TABLE_NAME,
        RDB$DESCRIPTION         AS DESCRIPTION
    FROM RDB$RELATIONS
    WHERE RDB$SYSTEM_FLAG = 0
      AND RDB$VIEW_BLR IS NULL
    ORDER BY RDB$RELATION_NAME
"""

# ─── Columnas de una tabla ────────────────────────────────────────────────────

QUERY_TABLE_COLUMNS_TYPED = """
    SELECT
        TRIM(rf.RDB$FIELD_NAME)  AS FIELD_NAME,
        CASE f.RDB$FIELD_TYPE
            WHEN 7   THEN 'SMALLINT'
            WHEN 8   THEN 'INTEGER'
            WHEN 10  THEN 'FLOAT'
            WHEN 12  THEN 'DATE'
            WHEN 13  THEN 'TIME'
            WHEN 14  THEN 'CHAR(' || f.RDB$FIELD_LENGTH || ')'
            WHEN 16  THEN 'BIGINT'
            WHEN 27  THEN 'DOUBLE'
            WHEN 35  THEN 'TIMESTAMP'
            WHEN 37  THEN 'VARCHAR(' || f.RDB$FIELD_LENGTH || ')'
            WHEN 261 THEN 'BLOB'
            ELSE 'TYPE_' || f.RDB$FIELD_TYPE
        END                      AS FIELD_TYPE,
        CASE
            WHEN f.RDB$FIELD_SCALE < 0
            THEN 'DECIMAL(' || f.RDB$FIELD_PRECISION || ',' || (-f.RDB$FIELD_SCALE) || ')'
            ELSE NULL
        END                      AS DECIMAL_TYPE,
        rf.RDB$NULL_FLAG         AS NOT_NULL,
        rf.RDB$FIELD_POSITION    AS FIELD_POS
    FROM RDB$RELATION_FIELDS rf
    JOIN RDB$FIELDS f ON rf.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
    WHERE TRIM(rf.RDB$RELATION_NAME) = ?
    ORDER BY rf.RDB$FIELD_POSITION
"""

# ─── Primary Keys de una tabla ────────────────────────────────────────────────

QUERY_TABLE_PRIMARY_KEYS = """
    SELECT TRIM(sg.RDB$FIELD_NAME) AS PK_FIELD
    FROM RDB$RELATION_CONSTRAINTS rc
    JOIN RDB$INDEX_SEGMENTS sg ON rc.RDB$INDEX_NAME = sg.RDB$INDEX_NAME
    WHERE rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
      AND TRIM(rc.RDB$RELATION_NAME) = ?
    ORDER BY sg.RDB$FIELD_POSITION
"""

# ─── Foreign Keys de una tabla ────────────────────────────────────────────────

QUERY_TABLE_FOREIGN_KEYS = """
    SELECT
        TRIM(rc.RDB$CONSTRAINT_NAME)        AS FK_NAME,
        TRIM(sg.RDB$FIELD_NAME)             AS FK_FIELD,
        TRIM(rc2.RDB$RELATION_NAME)         AS REF_TABLE,
        TRIM(sg2.RDB$FIELD_NAME)            AS REF_FIELD
    FROM RDB$RELATION_CONSTRAINTS rc
    JOIN RDB$INDEX_SEGMENTS sg  ON rc.RDB$INDEX_NAME  = sg.RDB$INDEX_NAME
    JOIN RDB$REF_CONSTRAINTS rr ON rc.RDB$CONSTRAINT_NAME = rr.RDB$CONSTRAINT_NAME
    JOIN RDB$RELATION_CONSTRAINTS rc2 ON rr.RDB$CONST_NAME_UQ = rc2.RDB$CONSTRAINT_NAME
    JOIN RDB$INDEX_SEGMENTS sg2 ON rc2.RDB$INDEX_NAME = sg2.RDB$INDEX_NAME
    WHERE rc.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY'
      AND TRIM(rc.RDB$RELATION_NAME) = ?
    ORDER BY sg.RDB$FIELD_POSITION
"""

# ─── Conteo de registros ──────────────────────────────────────────────────────
# NOTA: No usar f-string directamente — el nombre de tabla se valida antes de usarlo.
# Plantilla: sustituir {table_name} con el nombre validado.

QUERY_COUNT_TEMPLATE = "SELECT COUNT(*) AS C FROM {table_name}"

# ─── Muestra de datos (sin columnas sensibles) ────────────────────────────────
# Plantilla: sustituir {cols} y {table_name} con valores validados.
# Usa FIRST N (Firebird) — nunca LIMIT.

QUERY_SAMPLE_TEMPLATE = "SELECT FIRST {n} {cols} FROM {table_name}"
