"""
tests/unit/test_siuo_probar_integration.py
Tests de integración REALES del flujo "Probar ContextRetriever" del SIUO.

Llaman a los métodos y funciones REALES del código, tal como lo hace el usuario
al pulsar "Probar" en la pantalla SIUO. No usan mocks para el ContextRetriever
ni para los índices — usan los índices reales cargados en memoria.

MÓDULOS:
  - test_siuo_carga_indices.py       → Carga real de índices SIUO
  - test_siuo_get_context.py         → get_context() con preguntas reales
  - test_siuo_normalizacion.py       → Normalización de keywords
  - test_siuo_grafo.py               → Expansión BFS del grafo
  - test_siuo_autoaprendizaje.py     → Autoaprendizaje y feedback
  - test_siuo_fallback_errores.py    → Fallback y situaciones de error
  - test_siuo_diagnostico_presupuestos.py → Diagnóstico bug "0 aceptados"

Este fichero importa y re-exporta todos los tests para compatibilidad.
"""
# Los sub-módulos SIUO pendientes de creación no existen aún.
# pytest descubre test_siuo_context_ask.py y test_siuo_diagnostico_presupuestos.py
# directamente, por lo que este fichero solo re-exporta lo que ya existe.
from tests.unit.test_siuo_diagnostico_presupuestos import *  # noqa: F401,F403
