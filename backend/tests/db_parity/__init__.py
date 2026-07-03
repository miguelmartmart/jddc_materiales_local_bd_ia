"""
db_parity — Tests de paridad entre BD Firebird real y BD simulada SQLite.

Principio: la BD simulada debe comportarse como la real para que el chat IA
produzca respuestas equivalentes independientemente del backend activo.

Módulos:
  test_schema_parity.py  — Estructura: tablas, columnas, tipos, índices
  test_query_parity.py   — Resultados: las 77 consultas de la query_library
                           devuelven la misma forma de datos en ambas BDs

DEVIA: backend/tests/db_parity/DEVIA.md
"""
