"""Inventario de restricciones declaradas; no infiere FKs de nombres parecidos."""
SQL = """SELECT TRIM(rc.RDB$RELATION_NAME) AS TABLA,
 TRIM(rc.RDB$CONSTRAINT_NAME) AS RESTRICCION,
 TRIM(rc.RDB$CONSTRAINT_TYPE) AS TIPO,
 TRIM(s.RDB$FIELD_NAME) AS CAMPO, s.RDB$FIELD_POSITION AS POSICION,
 TRIM(parent.RDB$RELATION_NAME) AS TABLA_REFERIDA,
 TRIM(ps.RDB$FIELD_NAME) AS CAMPO_REFERIDO,
 idx.RDB$INDEX_INACTIVE AS INDICE_INACTIVO
 FROM RDB$RELATION_CONSTRAINTS rc
 LEFT JOIN RDB$INDICES idx ON idx.RDB$INDEX_NAME=rc.RDB$INDEX_NAME
 LEFT JOIN RDB$INDEX_SEGMENTS s ON s.RDB$INDEX_NAME=rc.RDB$INDEX_NAME
 LEFT JOIN RDB$REF_CONSTRAINTS ref ON ref.RDB$CONSTRAINT_NAME=rc.RDB$CONSTRAINT_NAME
 LEFT JOIN RDB$RELATION_CONSTRAINTS parent ON parent.RDB$CONSTRAINT_NAME=ref.RDB$CONST_NAME_UQ
 LEFT JOIN RDB$INDEX_SEGMENTS ps ON ps.RDB$INDEX_NAME=parent.RDB$INDEX_NAME
 AND ps.RDB$FIELD_POSITION=s.RDB$FIELD_POSITION
 WHERE rc.RDB$RELATION_NAME IN ('PROYECTOS','OBRACAB','OBRALIN','RECURSO','PRESUPROYE')
 AND rc.RDB$CONSTRAINT_TYPE IN ('PRIMARY KEY','FOREIGN KEY','UNIQUE')
 ORDER BY rc.RDB$RELATION_NAME,rc.RDB$CONSTRAINT_NAME,s.RDB$FIELD_POSITION"""


def inspect_schema(execute):
    evidence = {"sql": SQL, "alcance": "PROYECTOS, OBRACAB, OBRALIN, RECURSO, PRESUPROYE",
                "estado": "no_verificable", "restricciones": [],
                "nota": "Sin FK declarada no hay garantía del motor sobre esa relación. El inventario no prueba todos los endpoints."}
    try:
        rows, ms = execute(SQL)
        if not rows or any(not r.get("TABLA") or not r.get("TIPO") for r in rows):
            return evidence
        evidence.update(estado="inventariado", restricciones=rows, ms=ms)
    except Exception:
        pass
    return evidence
