"""
Test rápido: verifica que el alias POSITION fue corregido a FIELD_POS
y que ningún código Python referencia el alias antiguo.
"""
import sys

# 1. Verificar la query SQL
from backend.drivers.db.firebird_metadata_queries import QUERY_TABLE_COLUMNS_TYPED

assert "AS POSITION" not in QUERY_TABLE_COLUMNS_TYPED, "ERROR: AS POSITION sigue en la query"
assert "AS FIELD_POS" in QUERY_TABLE_COLUMNS_TYPED, "ERROR: AS FIELD_POS no encontrado"
print("OK: alias POSITION corregido a FIELD_POS en QUERY_TABLE_COLUMNS_TYPED")

# 2. Verificar que el código Python no accede al alias antiguo
import inspect
from backend.modules.db_explorer import metadata_builder_service, deep_indexer_service

src1 = inspect.getsource(metadata_builder_service)
src2 = inspect.getsource(deep_indexer_service)

# Eliminar referencias legítimas a RDB$FIELD_POSITION (nombre de columna del sistema)
# y ORDER BY (que usa el nombre de columna, no el alias)
def strip_legit(src):
    return (src
        .replace("RDB$FIELD_POSITION", "")
        .replace("ORDER BY", "")
        .replace("FIELD_POSITION", "")
    )

src1_clean = strip_legit(src1)
src2_clean = strip_legit(src2)

# Buscar si queda algún acceso al alias "POSITION" (como clave de dict)
import re
bad_refs1 = re.findall(r'["\']POSITION["\']', src1_clean)
bad_refs2 = re.findall(r'["\']POSITION["\']', src2_clean)

if bad_refs1:
    print(f"ERROR: metadata_builder_service referencia alias POSITION: {bad_refs1}")
    sys.exit(1)
if bad_refs2:
    print(f"ERROR: deep_indexer_service referencia alias POSITION: {bad_refs2}")
    sys.exit(1)

print("OK: metadata_builder_service no referencia alias POSITION como clave de dict")
print("OK: deep_indexer_service no referencia alias POSITION como clave de dict")

# 3. Verificar que los campos que SÍ se usan están en la query
for field in ["FIELD_NAME", "FIELD_TYPE", "DECIMAL_TYPE", "NOT_NULL", "FIELD_POS"]:
    assert field in QUERY_TABLE_COLUMNS_TYPED, f"ERROR: campo {field} no encontrado en la query"
    print(f"OK: campo {field} presente en la query")

print()
print("=" * 50)
print("FIX VERIFICADO: el error 'POSITION' de Firebird 2.5 está corregido.")
print("Reinicia el servidor DEVIA para aplicar el cambio.")
print("=" * 50)
