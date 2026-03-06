"""
Test rápido del FirebirdSQLNormalizer — ejecutar desde bots/interjddcia/
  python test_normalizer.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Importar directamente sin el prefijo backend.*
import importlib.util, types

# Cargar el módulo directamente por ruta para evitar problemas de PYTHONPATH
spec = importlib.util.spec_from_file_location(
    "firebird_sql_normalizer",
    os.path.join(os.path.dirname(__file__), "backend", "modules", "chat", "firebird_sql_normalizer.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
FirebirdSQLNormalizer = mod.FirebirdSQLNormalizer

n = FirebirdSQLNormalizer()

TESTS = [
    # (descripcion, sql_entrada, fragmento_esperado_en_salida)
    (
        "SQL multilínea con LIMIT → FIRST N en una línea",
        "SELECT\n    CODIGO,\n    NOMBRE,\n    DESCRIPCIONCORTA,\n    PRECIOVENTA,\n    STOCKARTICULO\nFROM ARTICULO\nLIMIT 10",
        "SELECT FIRST 10"
    ),
    (
        "SQL multilínea sin LIMIT → añade FIRST 100",
        "SELECT\n    CODIGO,\n    NOMBRE\nFROM ARTICULO",
        "SELECT FIRST 100"
    ),
    (
        "LIKE sin UPPER → añade UPPER()",
        "SELECT CODIGO FROM ARTICULO WHERE NOMBRE LIKE '%split%'",
        "UPPER(NOMBRE) LIKE UPPER('%split%')"
    ),
    (
        "ILIKE → UPPER(col) LIKE UPPER(val)",
        "SELECT CODIGO FROM ARTICULO WHERE NOMBRE ILIKE '%split%'",
        "UPPER(NOMBRE) LIKE UPPER('%split%')"
    ),
    (
        "STOCK → STOCKARTICULO",
        "SELECT STOCK FROM ARTICULO WHERE STOCK > 0",
        "STOCKARTICULO"
    ),
    (
        "Backticks eliminados",
        "SELECT `CODIGO`, `NOMBRE` FROM `ARTICULO`",
        "SELECT FIRST 100 CODIGO, NOMBRE FROM ARTICULO"
    ),
    (
        "!= → <>",
        "SELECT CODIGO FROM ARTICULO WHERE TIPO != 0",
        "TIPO <> 0"
    ),
    (
        "TRUE/FALSE → 'T'/'F'",
        "SELECT CODIGO FROM ARTICULO WHERE CONTROLSTOCK = TRUE",
        "CONTROLSTOCK = 'T'"
    ),
    (
        "NOW() → CURRENT_TIMESTAMP",
        "SELECT CODIGO FROM DOCCAB WHERE FECHA < NOW()",
        "CURRENT_TIMESTAMP"
    ),
    (
        "CURRENT_DATE() → CURRENT_DATE (sin paréntesis)",
        "SELECT CODIGO FROM DOCCAB WHERE FECHA = CURRENT_DATE()",
        "CURRENT_DATE"
    ),
    (
        "SELECT TOP N → SELECT FIRST N",
        "SELECT TOP 5 CODIGO, NOMBRE FROM ARTICULO",
        "SELECT FIRST 5"
    ),
    (
        "OFFSET eliminado",
        "SELECT FIRST 10 CODIGO FROM ARTICULO OFFSET 20",
        "OFFSET"  # NO debe aparecer
    ),
    (
        "Punto y coma eliminado",
        "SELECT FIRST 10 CODIGO FROM ARTICULO;",
        "ARTICULO"  # sin punto y coma
    ),
    (
        "Agregación COUNT → NO añade FIRST",
        "SELECT COUNT(*) FROM ARTICULO",
        "COUNT(*)"  # sin FIRST
    ),
    (
        "Comentarios eliminados",
        "SELECT CODIGO -- esto es un comentario\nFROM ARTICULO",
        "ARTICULO"
    ),
    (
        "CONCAT(a,b) → a || b",
        "SELECT CONCAT(NOMBRE, DESCRIPCIONCORTA) FROM ARTICULO",
        "||"
    ),
]

print("=" * 70)
print("TEST FirebirdSQLNormalizer")
print("=" * 70)

passed = 0
failed = 0

for desc, sql_in, expected_fragment in TESTS:
    sql_out, changes = n.normalize(sql_in)
    
    # Para el test de OFFSET: verificar que NO aparece en la salida
    if desc == "OFFSET eliminado":
        ok = "OFFSET" not in sql_out.upper()
    # Para el test de punto y coma: verificar que NO hay ; al final
    elif desc == "Punto y coma eliminado":
        ok = not sql_out.rstrip().endswith(';')
    # Para el test de agregación: verificar que NO hay FIRST
    elif "NO añade FIRST" in desc:
        ok = "FIRST" not in sql_out.upper()
    else:
        ok = expected_fragment.upper() in sql_out.upper()
    
    status = "[PASS]" if ok else "[FAIL]"
    if ok:
        passed += 1
    else:
        failed += 1
    
    print(f"\n{status} - {desc}")
    print(f"  IN:  {sql_in[:80].replace(chr(10), '<NL>')}")
    print(f"  OUT: {sql_out[:100]}")
    if changes:
        print(f"  CAMBIOS: {', '.join(changes)}")
    if not ok:
        print(f"  !! Esperaba '{expected_fragment}' en la salida")

print("\n" + "=" * 70)
print(f"RESULTADO: {passed}/{passed+failed} tests pasados")
print("=" * 70)
