"""
Fix concept_index.json round 2:
- Ensure 'agentes' maps to AGENTE as first entry
- Ensure 'almacenes' maps to ALMACEN as first entry
- Ensure 'doclin' is in 'ventas' and 'compras' entries
"""
import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "backend" / "core" / "config"
idx_path = CONFIG_DIR / "concept_index.json"

data = json.loads(idx_path.read_text(encoding='utf-8'))
idx = data.get('index', data)

def ensure_first(idx, key, table_name, filter_val=None):
    entries = idx.get(key, [])
    entry = {'table': table_name}
    if filter_val:
        entry['filter'] = filter_val
    
    # Check if already present
    already = any((e.get('table') if isinstance(e, dict) else e) == table_name for e in entries)
    first_table = (entries[0].get('table') if isinstance(entries[0], dict) else entries[0]) if entries else None
    
    if not already:
        idx[key] = [entry] + entries
        print(f"  Added {table_name} to '{key}'")
        return True
    elif first_table != table_name:
        # Move to front
        idx[key] = [entry] + [e for e in entries if (e.get('table') if isinstance(e, dict) else e) != table_name]
        print(f"  Moved {table_name} to front of '{key}'")
        return True
    else:
        print(f"  OK '{key}': {table_name} already first")
        return False

changed = 0

# Debug: print current state
print("Current state:")
for kw in ['agentes', 'almacenes', 'ventas', 'compras']:
    entries = idx.get(kw, [])
    tables = [(e.get('table') if isinstance(e, dict) else e) for e in entries[:3]]
    print(f"  {kw}: {tables}...")

print()

# Fix agentes -> AGENTE
if ensure_first(idx, 'agentes', 'AGENTE'): changed += 1
# Fix almacenes -> ALMACEN  
if ensure_first(idx, 'almacenes', 'ALMACEN'): changed += 1
# Fix ventas -> DOCLIN (for "artículos más vendidos")
if ensure_first(idx, 'ventas', 'DOCLIN'): changed += 1
# Fix compras -> DOCLIN (for "artículos con más compras")
if ensure_first(idx, 'compras', 'DOCLIN'): changed += 1

if changed > 0:
    if 'index' in data:
        data['index'] = idx
    else:
        data = idx
    idx_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nSaved {changed} fixes to {idx_path}")
else:
    print("\nNo changes needed")
