"""
Catalogo completo API mPYME v1.2 de Distrito K.
Fuente: documentacion oficial PDF. Combinado con inferencias marcadas 'incierto'.
"""
import json
from pathlib import Path
from typing import Dict, Any

_DIR = Path(__file__).parent / "data"

RIESGO: Dict[int, Dict] = {
    0: {"label":"Solo lectura","emoji":"🟢","color":"#16a34a","bg":"#f0fdf4","desc":"Sin riesgo. No modifica datos."},
    1: {"label":"Preparacion","emoji":"🟡","color":"#ca8a04","bg":"#fefce8","desc":"Objeto temporal. No persiste hasta write. Usar cancel para descartar."},
    2: {"label":"Escritura real","emoji":"🟠","color":"#ea580c","bg":"#fff7ed","desc":"PERSISTE en SQL Obras. Irreversible. Requiere confirmacion."},
    3: {"label":"Destructivo","emoji":"🔴","color":"#dc2626","bg":"#fef2f2","desc":"Elimina definitivamente. Doble confirmacion."},
}

CODIGOS_RESPUESTA: Dict[int, Dict] = {
    0:{"icon":"✅","desc":"Operacion exitosa"},
    1:{"icon":"🚫","desc":"Sin licencia para esta clase/operacion"},
    2:{"icon":"🔒","desc":"Sin permiso (usuario sin acceso)"},
    3:{"icon":"❌","desc":"Error de validacion de datos"},
    5:{"icon":"❌","desc":"Parametros incompletos o incorrectos"},
    10:{"icon":"🔍","desc":"Registro no encontrado"},
    20:{"icon":"❌","desc":"objectId no valido o expirado"},
    -1:{"icon":"💥","desc":"Error de conexion o excepcion del servidor"},
}

def _load(name: str) -> Any:
    p = _DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def get_operaciones_globales() -> Dict:
    return _load("operaciones_globales.json")

def get_campos_clase() -> Dict:
    return _load("campos_clase.json")

def get_catalogue() -> Dict:
    return _load("catalogue.json")
