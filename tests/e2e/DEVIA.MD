# DEVIA: tests/e2e — Tests End-to-End

```json
{
  "capa": "e2e",
  "descripcion": "Tests end-to-end. Flujo completo: pregunta → SIUO → SQL → BD → respuesta. Sin mocks.",
  "hereda_de": "tests/DEVIA.MD",

  "ficheros": {
    "conftest.py":              "Fixtures e2e (helpers de traza, auditor de red)",
    "helpers.py":               "Funciones reutilizables: _ask_and_trace, _assert_response",
    "test_preguntas_1tabla.py": "Preguntas que usan 1 tabla (COUNT, listado simple)",
    "test_preguntas_2tablas.py":"Preguntas que cruzan 2-3 tablas (ventas, facturas+cliente)",
    "test_regresiones.py":      "Regresiones conocidas — tests que detectaron bugs reales"
  },

  "independencia": {
    "sin_hardcode":   "Ninguna tabla, IP o parámetro hardcodeado. Todo desde test.properties.",
    "helpers_comunes":"helpers.py contiene funciones reutilizables por todos los tests e2e.",
    "trazas":         "Cada test genera traza en logs/e2e_traces.jsonl para depuración.",
    "portabilidad":   "Funciona con cualquier BD Firebird que tenga las tablas del esquema."
  },

  "regresiones_documentadas": {
    "REG-001": "artículos más vendidos → antes mapeaba a HISTORICOPRECIOS (incorrecto)",
    "REG-002": "artículos con más compras → antes devolvía FABARTFABASOC (incorrecto)",
    "REG-003": "LIMIT en SQL → Firebird no soporta LIMIT, debe ser FIRST N"
  },

  "ejecutar": ".venv/Scripts/pytest tests/e2e/ -v -s --tb=short",
  "ejecutar_regresiones": ".venv/Scripts/pytest tests/e2e/test_regresiones.py -v -s"
}
```
