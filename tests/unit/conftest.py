"""
conftest.py — Fixtures de datos para tests unitarios.

PROPÓSITO:
  Proveer datos de prueba reutilizables a todos los tests de tests/unit/.
  Ningún fixture aquí hace conexiones de red, BD ni IA.

DATOS:
  - ARTICULOS_SAMPLE: 50 artículos de prueba
  - FACTURAS_SAMPLE:  20 facturas de prueba
  - CLIENTES_SAMPLE:  10 clientes de prueba
  - RESULTADOS_*:     resultados típicos de consultas SQL
"""

from typing import Any, Dict, List
import pytest

# ─── Datos de prueba ──────────────────────────────────────────────────────────

ARTICULOS_SAMPLE: List[Dict[str, Any]] = [
    {"CODART": f"ART{i:04d}", "NOMBRE": f"Split Samsung {i*500}W",
     "PRECIO": float(i * 150), "STOCK": i * 2, "FAMILIA": "SPLITS"}
    for i in range(1, 51)
]

FACTURAS_SAMPLE: List[Dict[str, Any]] = [
    {"NUMDOC": f"F2026-{i:03d}", "FECHA": f"2026-03-{i:02d}",
     "TOTAL": float(i * 500), "TIPO": 13, "CODCLI": f"CLI{i:03d}"}
    for i in range(1, 21)
]

CLIENTES_SAMPLE: List[Dict[str, Any]] = [
    {"CODCLI": f"CLI{i:03d}", "RAZONSOCIAL": f"Empresa {i} S.L.",
     "NOMBRE": f"Cliente {i}", "TELEFONO": f"6{i:08d}"}
    for i in range(1, 11)
]

RESULTADOS_COUNT: List[Dict[str, Any]] = [{"COUNT": 437}]
RESULTADOS_TOTAL: List[Dict[str, Any]] = [{"TOTAL": 45678.90}]
RESULTADOS_VACIO: List[Dict[str, Any]] = []

RESULTADOS_VENTAS: List[Dict[str, Any]] = [
    {"NOMBRE": "Split Samsung 3000W", "TOTAL_VENDIDO": 45},
    {"NOMBRE": "Split LG 5000W",      "TOTAL_VENDIDO": 32},
    {"NOMBRE": "Cassette Daikin 9000","TOTAL_VENDIDO": 28},
]

RESULTADOS_AGENTES: List[Dict[str, Any]] = [
    {"NOMBRE": "Juan García",   "TOTAL_VENTAS": 125000.0},
    {"NOMBRE": "María López",   "TOTAL_VENTAS": 98500.0},
    {"NOMBRE": "Pedro Martínez","TOTAL_VENTAS": 76200.0},
]

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def articulos_sample() -> List[Dict]:
    return list(ARTICULOS_SAMPLE)

@pytest.fixture
def facturas_sample() -> List[Dict]:
    return list(FACTURAS_SAMPLE)

@pytest.fixture
def clientes_sample() -> List[Dict]:
    return list(CLIENTES_SAMPLE)

@pytest.fixture
def resultados_count() -> List[Dict]:
    return list(RESULTADOS_COUNT)

@pytest.fixture
def resultados_total() -> List[Dict]:
    return list(RESULTADOS_TOTAL)

@pytest.fixture
def resultados_vacio() -> List[Dict]:
    return []

@pytest.fixture
def resultados_ventas() -> List[Dict]:
    return list(RESULTADOS_VENTAS)

@pytest.fixture
def resultados_agentes() -> List[Dict]:
    return list(RESULTADOS_AGENTES)

@pytest.fixture
def muchos_resultados() -> List[Dict]:
    """50 artículos — activa la paginación."""
    return [
        {"NOMBRE": f"Artículo {i}", "PRECIO": float(i * 10), "CODIGO": f"ART{i:04d}"}
        for i in range(1, 51)
    ]

@pytest.fixture
def pocos_resultados() -> List[Dict]:
    """5 artículos — NO activa la paginación."""
    return [
        {"NOMBRE": f"Artículo {i}", "PRECIO": float(i * 10)}
        for i in range(1, 6)
    ]
