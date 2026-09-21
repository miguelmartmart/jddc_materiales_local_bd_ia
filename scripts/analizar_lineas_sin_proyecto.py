"""Solo lectura: clasificación de líneas sin obra, sin historial de producción."""
from pathlib import Path
import sys, json
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.modules.api_clone.utilidades.read_only import open_reader
from backend.modules.api_clone.utilidades.unassigned_analysis import classify_unassigned

if __name__=="__main__":
    with open_reader() as execute:
        result=classify_unassigned(execute)
    result["fecha_utc"]=datetime.now(timezone.utc).isoformat()
    (ROOT/"docs"/"clasificacion_sin_proyecto_2026_09_21.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if result["estado"]=="no_verificable": raise SystemExit(1)
