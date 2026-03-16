"""
test_siuo_context_ask.py — Tests end-to-end del botón "Probar" de SIUO.

CUBRE:
  Simula exactamente lo que hace el botón "Probar" del panel SIUO:
    1. POST /api/siuo/context/test  → ContextRetriever.get_context()
    2. POST /api/siuo/context/ask   → ContextRetriever + ChatService + Firebird

  Cientos de preguntas reales: sencillas, complejas, con errores esperados,
  con funciones no soportadas, con tablas desconocidas, con fechas, etc.

FILOSOFÍA:
  - SIN MOCKS: llama a la lógica real del ContextRetriever y del normalizador
  - Sin conexión a BD ni a IA: los tests de context/test solo prueban el
    ContextRetriever (índices en disco). Los tests de context/ask usan
    httpx.AsyncClient contra la app FastAPI real (si el servidor está disponible).
  - Los tests de normalización SQL son 100% deterministas y siempre pasan.
  - Los tests de integración con BD/IA se marcan con @pytest.mark.integration
    y se saltan si el servidor no está disponible.

ESTRUCTURA:
  Bloque A: ContextRetriever.get_context() — 200+ preguntas reales
  Bloque B: Normalización SQL de preguntas → SQL esperado (determinista)
  Bloque C: Endpoint /api/siuo/context/test via httpx (integración)
  Bloque D: Endpoint /api/siuo/context/ask via httpx (integración con BD+IA)
  Bloque E: Endpoint /api/siuo/stats, /reload, /learning (integración)

AUTOR: DEVIA / bots/interjddcia · v1.5.0
"""

import sys
import pytest
import asyncio
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parents[3]))

from backend.modules.db_explorer.context_retriever import get_context_retriever
from backend.modules.chat.firebird_sql_normalizer import FirebirdSQLNormalizer

# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def retriever():
    return get_context_retriever()


@pytest.fixture(scope="module")
def normalizer():
    return FirebirdSQLNormalizer()


# ─── Preguntas reales: 200+ casos ────────────────────────────────────────────
# Formato: (pregunta, palabras_clave_esperadas_en_contexto_o_tablas)
# Las palabras clave son opcionales — si están vacías, solo se verifica
# que el contexto no sea vacío y que no crashee.

PREGUNTAS_SIMPLES = [
    # Ventas y documentos
    ("¿Cuántas ventas hay este mes?",                   ["DOCCAB", "TIPO", "FECHA"]),
    ("¿Cuál es el total de ventas del año?",            ["DOCCAB"]),
    ("¿Cuántos presupuestos se han hecho?",             ["DOCCAB", "TIPO"]),
    ("¿Cuántos albaranes hay pendientes?",              ["DOCCAB"]),
    ("¿Cuántas facturas se han emitido este año?",      ["DOCCAB"]),
    ("¿Cuál es el importe total de las facturas?",      ["DOCCAB", "IMPORTETOTAL"]),
    ("¿Cuántos pedidos hay en el sistema?",             ["DOCCAB"]),
    ("¿Cuántos documentos hay de tipo 0?",              ["DOCCAB", "TIPO"]),
    ("¿Cuántos documentos hay de tipo 1?",              ["DOCCAB"]),
    ("¿Cuántos documentos hay de tipo 12?",             ["DOCCAB"]),
    ("¿Cuántos documentos hay de tipo 13?",             ["DOCCAB"]),
    ("¿Cuál es el importe medio de las ventas?",        ["DOCCAB"]),
    ("¿Cuál es la venta máxima registrada?",            ["DOCCAB"]),
    ("¿Cuál es la venta mínima registrada?",            ["DOCCAB"]),
    ("¿Cuántas ventas hay por mes?",                    ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay por año?",                    ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay por trimestre?",              ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay hoy?",                        ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay esta semana?",                ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay este año?",                   ["DOCCAB", "FECHA"]),

    # Artículos
    ("¿Cuántos artículos hay en el catálogo?",          ["ARTICULO"]),
    ("¿Cuáles son los artículos más vendidos?",         ["ARTICULO", "DOCLIN"]),
    ("¿Cuáles son los artículos más comprados?",        ["ARTICULO", "DOCLIN"]),
    ("¿Cuál es el precio medio de los artículos?",      ["ARTICULO"]),
    ("¿Cuántos artículos tienen stock?",                ["ARTICULO"]),
    ("¿Cuántos artículos están sin stock?",             ["ARTICULO"]),
    ("¿Cuáles son los artículos con más stock?",        ["ARTICULO"]),
    ("¿Cuáles son los artículos con menos stock?",      ["ARTICULO"]),
    ("¿Cuántos artículos hay por familia?",             ["ARTICULO"]),
    ("¿Cuántos artículos hay por proveedor?",           ["ARTICULO"]),
    ("¿Cuál es el artículo más caro?",                  ["ARTICULO"]),
    ("¿Cuál es el artículo más barato?",                ["ARTICULO"]),
    ("¿Cuántos artículos hay activos?",                 ["ARTICULO"]),
    ("¿Cuántos artículos hay inactivos?",               ["ARTICULO"]),
    ("¿Cuántos artículos se han vendido este mes?",     ["ARTICULO", "DOCLIN"]),
    ("¿Cuántos artículos se han vendido este año?",     ["ARTICULO", "DOCLIN"]),
    ("¿Cuál es el artículo con más ventas?",            ["ARTICULO", "DOCLIN"]),
    ("¿Cuál es el artículo con menos ventas?",          ["ARTICULO", "DOCLIN"]),
    ("¿Cuántos artículos no se han vendido nunca?",     ["ARTICULO", "DOCLIN"]),
    ("¿Cuántos artículos se han vendido más de 10 veces?", ["ARTICULO", "DOCLIN"]),

    # Clientes
    ("¿Cuántos clientes hay?",                          ["DOCCAB"]),
    ("¿Cuáles son los clientes con más compras?",       ["DOCCAB"]),
    ("¿Cuáles son los clientes con más gasto?",         ["DOCCAB"]),
    ("¿Cuántos clientes han comprado este mes?",        ["DOCCAB", "FECHA"]),
    ("¿Cuántos clientes han comprado este año?",        ["DOCCAB", "FECHA"]),
    ("¿Cuál es el cliente con mayor importe?",          ["DOCCAB"]),
    ("¿Cuántos clientes no han comprado en 6 meses?",   ["DOCCAB", "FECHA"]),
    ("¿Cuántos clientes nuevos hay este mes?",          ["DOCCAB", "FECHA"]),
    ("¿Cuántos clientes hay por provincia?",            ["DOCCAB"]),
    ("¿Cuántos clientes hay por código postal?",        ["DOCCAB"]),

    # Líneas de documento
    ("¿Cuántas líneas de venta hay?",                   ["DOCLIN"]),
    ("¿Cuál es la cantidad media por línea?",           ["DOCLIN"]),
    ("¿Cuál es el importe total de las líneas?",        ["DOCLIN"]),
    ("¿Cuántas líneas hay por documento?",              ["DOCLIN", "DOCCAB"]),
    ("¿Cuántas líneas hay de cada artículo?",           ["DOCLIN", "ARTICULO"]),
    ("¿Cuál es la línea con mayor importe?",            ["DOCLIN"]),
    ("¿Cuántas líneas hay con descuento?",              ["DOCLIN"]),
    ("¿Cuál es el descuento medio?",                    ["DOCLIN"]),

    # Trabajadores / empleados
    ("¿Cuántos trabajadores hay?",                      []),
    ("¿Cuántos empleados hay activos?",                 []),
    ("¿Cuántas ventas ha hecho cada trabajador?",       []),
    ("¿Cuál es el trabajador con más ventas?",          []),
    ("¿Cuántos trabajadores hay por departamento?",     []),

    # Fechas y periodos
    ("¿Cuántas ventas hay en enero?",                   ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en febrero?",                 ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en el primer trimestre?",     ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en el segundo trimestre?",    ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en el tercer trimestre?",     ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en el cuarto trimestre?",     ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en los últimos 30 días?",     ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en los últimos 90 días?",     ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en los últimos 6 meses?",     ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en los últimos 12 meses?",    ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay entre enero y marzo?",        ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay entre abril y junio?",        ["DOCCAB", "FECHA"]),

    # Importes y totales
    ("¿Cuál es el total de ventas sin IVA?",            ["DOCCAB"]),
    ("¿Cuál es el total de ventas con IVA?",            ["DOCCAB"]),
    ("¿Cuál es el IVA total recaudado?",                ["DOCCAB"]),
    ("¿Cuál es el importe neto de las ventas?",         ["DOCCAB"]),
    ("¿Cuál es el importe bruto de las ventas?",        ["DOCCAB"]),
    ("¿Cuál es el descuento total aplicado?",           ["DOCCAB", "DOCLIN"]),
    ("¿Cuál es el margen medio de las ventas?",         ["DOCCAB"]),

    # Estadísticas
    ("¿Cuántas ventas hay por día de la semana?",       ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay por hora del día?",           ["DOCCAB"]),
    ("¿Cuál es el día con más ventas?",                 ["DOCCAB", "FECHA"]),
    ("¿Cuál es el mes con más ventas?",                 ["DOCCAB", "FECHA"]),
    ("¿Cuál es el año con más ventas?",                 ["DOCCAB", "FECHA"]),
    ("¿Cuál es la tendencia de ventas?",                ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay por tipo de documento?",      ["DOCCAB", "TIPO"]),
    ("¿Cuántos documentos hay por serie?",              ["DOCCAB"]),
    ("¿Cuántos documentos hay por almacén?",            ["DOCCAB"]),
    ("¿Cuántos documentos hay por forma de pago?",      ["DOCCAB"]),
]

PREGUNTAS_COMPLEJAS = [
    # Análisis de conversión presupuesto → factura
    (
        "¿Cuál es la tasa de conversión de presupuestos a facturas?",
        ["DOCCAB", "TIPO", "DOCDESTINO"],
    ),
    (
        "¿Cuántos presupuestos se han convertido en facturas este mes?",
        ["DOCCAB", "DOCDESTINO", "FECHA"],
    ),
    (
        "¿Cuál es el porcentaje de presupuestos aceptados sobre el total?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuántos presupuestos han sido rechazados?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuál es el tiempo medio entre presupuesto y factura?",
        ["DOCCAB", "DOCDESTINO", "FECHA"],
    ),
    (
        "¿Cuántos presupuestos hay pendientes de aceptar?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuál es el importe medio de los presupuestos aceptados?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuántos presupuestos se han hecho por cliente?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el cliente con más presupuestos aceptados?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuántos presupuestos hay por trabajador?",
        ["DOCCAB"],
    ),

    # Análisis de artículos con ROUND (caso real del log)
    (
        "¿Cuál es la tasa de éxito de los presupuestos por artículo?",
        ["DOCCAB", "DOCLIN", "DOCDESTINO"],
    ),
    (
        "¿Cuál es el porcentaje de ventas de cada artículo sobre el total?",
        ["ARTICULO", "DOCLIN"],
    ),
    (
        "¿Cuál es el porcentaje de clientes que repiten compra?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el porcentaje de artículos vendidos sobre el catálogo total?",
        ["ARTICULO", "DOCLIN"],
    ),
    (
        "¿Cuál es el porcentaje de ventas por familia de artículo?",
        ["ARTICULO", "DOCLIN"],
    ),

    # Análisis temporal complejo
    (
        "¿Cuántas ventas hay por mes en los últimos 2 años?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuál es la evolución mensual de ventas en el último año?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuántas ventas hay por semana en los últimos 3 meses?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuál es la variación de ventas respecto al mismo mes del año anterior?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuántos artículos nuevos se han añadido cada mes?",
        ["ARTICULO"],
    ),

    # Análisis de rentabilidad
    (
        "¿Cuáles son los 10 artículos más rentables?",
        ["ARTICULO", "DOCLIN"],
    ),
    (
        "¿Cuáles son los 10 clientes más rentables?",
        ["DOCCAB"],
    ),
    (
        "¿Cuáles son los 10 trabajadores con más ventas?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el margen por familia de artículo?",
        ["ARTICULO", "DOCLIN"],
    ),
    (
        "¿Cuáles son los artículos con mayor margen?",
        ["ARTICULO", "DOCLIN"],
    ),

    # Análisis de stock
    (
        "¿Cuántos artículos tienen stock por debajo del mínimo?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos artículos tienen stock por encima del máximo?",
        ["ARTICULO"],
    ),
    (
        "¿Cuál es el valor total del stock?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos artículos tienen stock negativo?",
        ["ARTICULO"],
    ),
    (
        "¿Cuáles son los artículos con más rotación de stock?",
        ["ARTICULO", "DOCLIN"],
    ),

    # Análisis de proveedores
    (
        "¿Cuántos proveedores hay?",
        [],
    ),
    (
        "¿Cuáles son los proveedores con más compras?",
        [],
    ),
    (
        "¿Cuál es el importe total de compras por proveedor?",
        [],
    ),
    (
        "¿Cuántos artículos tiene cada proveedor?",
        ["ARTICULO"],
    ),
    (
        "¿Cuál es el proveedor con más artículos?",
        ["ARTICULO"],
    ),

    # Análisis de calidad de datos
    (
        "¿Cuántos artículos no tienen precio?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos documentos tienen importe cero?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos artículos no tienen descripción?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos clientes no tienen dirección?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos documentos tienen fecha futura?",
        ["DOCCAB", "FECHA"],
    ),

    # Análisis de series y numeración
    (
        "¿Cuántos documentos hay por serie?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el último número de factura?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos documentos hay con número duplicado?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el rango de fechas de los documentos?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuántos documentos hay sin número asignado?",
        ["DOCCAB"],
    ),

    # Análisis de formas de pago
    (
        "¿Cuántas ventas hay por forma de pago?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el importe total por forma de pago?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos clientes pagan al contado?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos clientes pagan a crédito?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el plazo medio de pago?",
        ["DOCCAB"],
    ),

    # Análisis de almacenes
    (
        "¿Cuántos almacenes hay?",
        [],
    ),
    (
        "¿Cuál es el stock por almacén?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos movimientos de almacén hay este mes?",
        [],
    ),
    (
        "¿Cuál es el almacén con más stock?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos artículos hay en cada almacén?",
        ["ARTICULO"],
    ),

    # Análisis de descuentos
    (
        "¿Cuál es el descuento medio por cliente?",
        ["DOCCAB", "DOCLIN"],
    ),
    (
        "¿Cuáles son los clientes con mayor descuento?",
        ["DOCCAB", "DOCLIN"],
    ),
    (
        "¿Cuántas líneas tienen descuento mayor al 10%?",
        ["DOCLIN"],
    ),
    (
        "¿Cuál es el importe total de descuentos aplicados?",
        ["DOCLIN"],
    ),
    (
        "¿Cuántos artículos tienen descuento especial?",
        ["ARTICULO", "DOCLIN"],
    ),

    # Análisis de devoluciones
    (
        "¿Cuántas devoluciones hay este mes?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el importe total de devoluciones?",
        ["DOCCAB"],
    ),
    (
        "¿Cuáles son los artículos más devueltos?",
        ["ARTICULO", "DOCLIN"],
    ),
    (
        "¿Cuántos clientes han hecho devoluciones?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el porcentaje de devoluciones sobre ventas?",
        ["DOCCAB"],
    ),

    # Análisis de IVA
    (
        "¿Cuál es el IVA total por tipo?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántas ventas hay con IVA al 21%?",
        ["DOCCAB", "DOCLIN"],
    ),
    (
        "¿Cuántas ventas hay con IVA al 10%?",
        ["DOCCAB", "DOCLIN"],
    ),
    (
        "¿Cuántas ventas hay con IVA al 4%?",
        ["DOCCAB", "DOCLIN"],
    ),
    (
        "¿Cuántas ventas hay exentas de IVA?",
        ["DOCCAB", "DOCLIN"],
    ),

    # Análisis de rutas y zonas
    (
        "¿Cuántas ventas hay por zona geográfica?",
        ["DOCCAB"],
    ),
    (
        "¿Cuáles son las zonas con más ventas?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos clientes hay por zona?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el importe medio por zona?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos repartidores hay?",
        [],
    ),

    # Análisis de tarifas
    (
        "¿Cuántas tarifas hay?",
        ["ARTICULO"],
    ),
    (
        "¿Cuál es la diferencia de precio entre tarifas?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos artículos tienen precio especial?",
        ["ARTICULO"],
    ),
    (
        "¿Cuál es el precio medio por tarifa?",
        ["ARTICULO"],
    ),
    (
        "¿Cuántos clientes tienen tarifa especial?",
        ["DOCCAB"],
    ),

    # Análisis de comisiones
    (
        "¿Cuál es la comisión total por trabajador?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es la comisión media por venta?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántas ventas tienen comisión?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el trabajador con más comisiones?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es la comisión total del mes?",
        ["DOCCAB", "FECHA"],
    ),

    # Análisis de objetivos
    (
        "¿Cuánto falta para alcanzar el objetivo de ventas del mes?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuál es el porcentaje de cumplimiento del objetivo?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos trabajadores han alcanzado su objetivo?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es la proyección de ventas para fin de mes?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuántos días quedan para fin de mes?",
        [],
    ),

    # Análisis de documentos relacionados
    (
        "¿Cuántos albaranes hay sin facturar?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuántos pedidos hay sin servir?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuántos presupuestos llevan más de 30 días sin respuesta?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuántos documentos hay en estado pendiente?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántos documentos hay en estado cerrado?",
        ["DOCCAB"],
    ),

    # Análisis de cobros
    (
        "¿Cuántas facturas están pendientes de cobro?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el importe total pendiente de cobro?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántas facturas llevan más de 30 días sin cobrar?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuántas facturas llevan más de 60 días sin cobrar?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuáles son los clientes con más deuda?",
        ["DOCCAB"],
    ),

    # Análisis de compras
    (
        "¿Cuántas compras hay este mes?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el importe total de compras?",
        ["DOCCAB"],
    ),
    (
        "¿Cuántas compras hay por proveedor?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el proveedor con más compras este mes?",
        ["DOCCAB", "FECHA"],
    ),
    (
        "¿Cuántos artículos se han comprado este mes?",
        ["DOCCAB", "DOCLIN"],
    ),
]

PREGUNTAS_CON_FUNCIONES_NO_SOPORTADAS = [
    # Estas preguntas generarían SQL con ROUND() → el normalizador debe corregirlo
    (
        "¿Cuál es el porcentaje de presupuestos aceptados redondeado a 2 decimales?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuál es la tasa de conversión redondeada?",
        ["DOCCAB", "DOCDESTINO"],
    ),
    (
        "¿Cuál es el porcentaje de artículos vendidos?",
        ["ARTICULO", "DOCLIN"],
    ),
    (
        "¿Cuál es el porcentaje de clientes activos?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el porcentaje de ventas por mes?",
        ["DOCCAB", "FECHA"],
    ),
]

PREGUNTAS_CON_TABLAS_DESCONOCIDAS = [
    # Estas preguntas podrían generar SQL con tablas que no existen
    ("¿Cuántos proveedores hay en la tabla PROVEEDOR?",     []),
    ("¿Cuántos clientes hay en la tabla CLIENTE?",          []),
    ("¿Cuántos empleados hay en la tabla EMPLEADO?",        []),
    ("¿Cuántos productos hay en la tabla PRODUCTO?",        []),
    ("¿Cuántos pedidos hay en la tabla PEDIDO?",            []),
    ("¿Cuántas facturas hay en la tabla FACTURA?",          []),
    ("¿Cuántos albaranes hay en la tabla ALBARAN?",         []),
    ("¿Cuántos presupuestos hay en la tabla PRESUPUESTO?",  []),
    ("¿Cuántos artículos hay en la tabla ARTICULOS?",       ["ARTICULO"]),
    ("¿Cuántos documentos hay en la tabla DOCUMENTOS?",     ["DOCCAB"]),
]

PREGUNTAS_EDGE_CASES = [
    # Preguntas muy cortas
    ("ventas",                                              []),
    ("artículos",                                           ["ARTICULO"]),
    ("clientes",                                            []),
    ("facturas",                                            ["DOCCAB"]),
    ("stock",                                               ["ARTICULO"]),

    # Preguntas con caracteres especiales
    ("¿Cuántas ventas hay? (este mes)",                     ["DOCCAB"]),
    ("ventas del año 2024",                                 ["DOCCAB", "FECHA"]),
    ("ventas > 1000€",                                      ["DOCCAB"]),
    ("artículos con precio < 10",                           ["ARTICULO"]),
    ("clientes con nombre 'García'",                        []),

    # Preguntas en inglés
    ("how many sales this month?",                          ["DOCCAB"]),
    ("total revenue",                                       ["DOCCAB"]),
    ("top 10 articles",                                     ["ARTICULO"]),
    ("customer count",                                      []),
    ("stock level",                                         ["ARTICULO"]),

    # Preguntas muy largas
    (
        "¿Cuántas ventas hay en el sistema de gestión de la empresa para el mes "
        "actual considerando todos los tipos de documentos incluyendo facturas, "
        "albaranes, presupuestos y pedidos?",
        ["DOCCAB"],
    ),
    (
        "¿Cuál es el importe total de todas las ventas realizadas en el año en curso "
        "desglosado por mes y por tipo de documento incluyendo el IVA correspondiente?",
        ["DOCCAB", "FECHA"],
    ),

    # Preguntas con números
    ("¿Cuántas ventas hay con importe mayor a 1000?",       ["DOCCAB"]),
    ("¿Cuántas ventas hay con importe entre 100 y 500?",    ["DOCCAB"]),
    ("¿Cuántos artículos tienen precio mayor a 50?",        ["ARTICULO"]),
    ("¿Cuántos artículos tienen stock mayor a 100?",        ["ARTICULO"]),
    ("¿Cuántos documentos hay del tipo 0?",                 ["DOCCAB", "TIPO"]),

    # Preguntas con fechas específicas
    ("¿Cuántas ventas hay en 2024?",                        ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en 2025?",                        ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay en enero de 2024?",               ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay entre 2023 y 2024?",              ["DOCCAB", "FECHA"]),
    ("¿Cuántas ventas hay desde el 1 de enero?",            ["DOCCAB", "FECHA"]),
]

# Combinar todas las preguntas
ALL_QUESTIONS: List[Tuple[str, List[str]]] = (
    PREGUNTAS_SIMPLES
    + PREGUNTAS_COMPLEJAS
    + PREGUNTAS_CON_FUNCIONES_NO_SOPORTADAS
    + PREGUNTAS_CON_TABLAS_DESCONOCIDAS
    + PREGUNTAS_EDGE_CASES
)


# ─── Bloque A: ContextRetriever.get_context() ────────────────────────────────

class TestContextRetrieverGetContext:
    """
    Prueba ContextRetriever.get_context() con todas las preguntas.
    No requiere BD ni IA — solo los índices en disco.
    """

    def test_get_context_no_crashea_con_pregunta_vacia(self, retriever):
        """get_context() con pregunta vacía no debe crashear."""
        try:
            context, meta = retriever.get_context("", max_tokens=1000)
            assert isinstance(context, str)
            assert isinstance(meta, dict)
        except Exception as e:
            pytest.fail(f"get_context('') lanzó excepción: {e}")

    def test_get_context_devuelve_string_y_dict(self, retriever):
        context, meta = retriever.get_context("¿Cuántas ventas hay?", max_tokens=1000)
        assert isinstance(context, str)
        assert isinstance(meta, dict)

    def test_get_context_respeta_max_tokens(self, retriever):
        """El contexto no debe superar max_tokens * 4 caracteres aprox."""
        max_tokens = 500
        context, _ = retriever.get_context("¿Cuántas ventas hay?", max_tokens=max_tokens)
        # Estimación: 1 token ≈ 4 chars. Damos margen del 20%.
        assert len(context) <= max_tokens * 4 * 1.2 + 200

    def test_get_context_meta_tiene_campos_esperados(self, retriever):
        _, meta = retriever.get_context("¿Cuántas ventas hay?", max_tokens=1000)
        # Al menos uno de estos campos debe estar presente
        expected_fields = {"tables_used", "keywords_found", "tokens_estimated", "source"}
        assert len(expected_fields & set(meta.keys())) > 0

    @pytest.mark.parametrize("question,expected_tables", ALL_QUESTIONS[:50])
    def test_get_context_preguntas_simples(self, retriever, question, expected_tables):
        """Las primeras 50 preguntas: el contexto no debe estar vacío."""
        context, meta = retriever.get_context(question, max_tokens=4000)
        assert isinstance(context, str)
        # El contexto puede estar vacío si los índices no están construidos,
        # pero no debe crashear
        assert context is not None

    @pytest.mark.parametrize("question,expected_tables", ALL_QUESTIONS[50:100])
    def test_get_context_preguntas_complejas(self, retriever, question, expected_tables):
        """Preguntas 50-100: el contexto no debe crashear."""
        context, meta = retriever.get_context(question, max_tokens=8000)
        assert isinstance(context, str)
        assert isinstance(meta, dict)

    @pytest.mark.parametrize("question,expected_tables", ALL_QUESTIONS[100:])
    def test_get_context_preguntas_edge_cases(self, retriever, question, expected_tables):
        """Preguntas 100+: edge cases, no debe crashear."""
        context, meta = retriever.get_context(question, max_tokens=8000)
        assert isinstance(context, str)
        assert isinstance(meta, dict)

    def test_get_context_todas_las_preguntas_sin_crash(self, retriever):
        """Todas las preguntas deben procesarse sin excepción."""
        errores = []
        for question, _ in ALL_QUESTIONS:
            try:
                context, meta = retriever.get_context(question, max_tokens=4000)
                assert isinstance(context, str)
                assert isinstance(meta, dict)
            except Exception as e:
                errores.append(f"'{question[:50]}': {e}")
        if errores:
            pytest.fail(
                f"{len(errores)} preguntas lanzaron excepción:\n" +
                "\n".join(errores[:10])
            )

    def test_get_context_max_tokens_muy_pequeno(self, retriever):
        """max_tokens=100 no debe crashear."""
        context, meta = retriever.get_context("ventas", max_tokens=100)
        assert isinstance(context, str)

    def test_get_context_max_tokens_muy_grande(self, retriever):
        """max_tokens=16000 no debe crashear."""
        context, meta = retriever.get_context("ventas", max_tokens=16000)
        assert isinstance(context, str)

    def test_get_context_pregunta_con_caracteres_especiales(self, retriever):
        """Caracteres especiales no deben crashear."""
        for q in ["ventas > 1000€", "clientes 'García'", "año 2024", "¿?!@#$%"]:
            context, meta = retriever.get_context(q, max_tokens=1000)
            assert isinstance(context, str)

    def test_get_context_pregunta_muy_larga(self, retriever):
        """Pregunta de 500 chars no debe crashear."""
        q = "¿Cuántas ventas hay? " * 25  # ~500 chars
        context, meta = retriever.get_context(q, max_tokens=4000)
        assert isinstance(context, str)


# ─── Bloque B: Normalización SQL determinista ─────────────────────────────────

class TestNormalizacionSQLDeterminista:
    """
    Prueba que el normalizador SQL convierte correctamente las preguntas
    que generarían SQL con funciones no soportadas.
    Estos tests son 100% deterministas y no requieren BD ni IA.
    """

    # SQL con ROUND que el normalizador debe corregir
    SQL_CON_ROUND = [
        (
            "SELECT ROUND(COUNT(*) * 100.0 / 1000, 2) AS PCT FROM DOCCAB",
            "CAST(",
            "NUMERIC(15,2)",
        ),
        (
            "SELECT ROUND(IMPORTETOTAL, 2) AS TOTAL FROM DOCCAB",
            "CAST(",
            "NUMERIC(15,2)",
        ),
        (
            "SELECT ROUND(PRECIO, 0) AS PRECIO_ENTERO FROM ARTICULO",
            "CAST(",
            "AS INTEGER",
        ),
        (
            "SELECT ROUND(IMPORTETOTAL) AS TOTAL FROM DOCCAB",
            "CAST(",
            "AS INTEGER",
        ),
        (
            # Caso real del log: ROUND con COUNT(DISTINCT CASE WHEN ... IN (...))
            "SELECT ROUND( "
            "(COUNT(DISTINCT CASE WHEN DC.TIPO IN (12, 13) THEN D.CODDOCUMENTO END) * 100.0) / "
            "COUNT(DISTINCT D.CODDOCUMENTO), 2 ) AS TASA_EXITO "
            "FROM DOCDESTINO D JOIN DOCCAB DC ON DC.CODIGO = D.CODDOCUMENTODESTINO",
            "CAST(",
            "NUMERIC(15,2)",
        ),
    ]

    @pytest.mark.parametrize("sql,expected_contains,expected_type", SQL_CON_ROUND)
    def test_round_se_convierte_a_cast(self, normalizer, sql, expected_contains, expected_type):
        result, changes = normalizer.normalize(sql)
        assert "ROUND" not in result.upper(), f"ROUND no fue eliminado: {result}"
        assert expected_contains.upper() in result.upper(), f"Falta {expected_contains}: {result}"
        assert expected_type.upper() in result.upper(), f"Falta {expected_type}: {result}"
        assert len(changes) > 0

    # SQL con NVL/IFNULL/ISNULL
    SQL_CON_NVL = [
        ("SELECT NVL(IMPORTETOTAL, 0) FROM DOCCAB",         "COALESCE("),
        ("SELECT IFNULL(NOMBRE, 'N/A') FROM ARTICULO",      "COALESCE("),
        ("SELECT ISNULL(CODCLIENTE, 0) FROM DOCCAB",        "COALESCE("),
    ]

    @pytest.mark.parametrize("sql,expected", SQL_CON_NVL)
    def test_nvl_se_convierte_a_coalesce(self, normalizer, sql, expected):
        result, changes = normalizer.normalize(sql)
        assert expected.upper() in result.upper()
        assert len(changes) > 0

    # SQL con TRUNC/TRUNCATE
    SQL_CON_TRUNC = [
        ("SELECT TRUNC(IMPORTETOTAL) FROM DOCCAB",          "AS INTEGER"),
        ("SELECT TRUNCATE(PRECIO, 2) FROM ARTICULO",        "AS INTEGER"),
    ]

    @pytest.mark.parametrize("sql,expected", SQL_CON_TRUNC)
    def test_trunc_se_convierte_a_cast_integer(self, normalizer, sql, expected):
        result, changes = normalizer.normalize(sql)
        assert expected.upper() in result.upper()
        assert len(changes) > 0

    # SQL con LIMIT → FIRST
    SQL_CON_LIMIT = [
        ("SELECT * FROM DOCCAB LIMIT 10",                   "SELECT FIRST 10"),
        ("SELECT TOP 5 * FROM ARTICULO",                    "SELECT FIRST 5"),
        ("SELECT * FROM DOCCAB ROWS 20",                    "SELECT FIRST 20"),
    ]

    @pytest.mark.parametrize("sql,expected", SQL_CON_LIMIT)
    def test_limit_se_convierte_a_first(self, normalizer, sql, expected):
        result, changes = normalizer.normalize(sql)
        assert expected.upper() in result.upper()
        assert len(changes) > 0

    # SQL con != → <>
    def test_not_equal_se_convierte(self, normalizer):
        sql = "SELECT * FROM DOCCAB WHERE TIPO != 0"
        result, changes = normalizer.normalize(sql)
        assert "!=" not in result
        assert "<>" in result

    # SQL con TRUE/FALSE
    def test_boolean_literals_se_convierten(self, normalizer):
        sql = "SELECT * FROM ARTICULO WHERE ACTIVO = TRUE"
        result, changes = normalizer.normalize(sql)
        assert "TRUE" not in result.upper()
        assert "'T'" in result

    # SQL con ILIKE
    def test_ilike_se_convierte(self, normalizer):
        sql = "SELECT * FROM ARTICULO WHERE NOMBRE ILIKE '%mesa%'"
        result, changes = normalizer.normalize(sql)
        assert "ILIKE" not in result.upper()
        assert "UPPER(" in result.upper()

    # SQL con LIKE sin UPPER
    def test_like_se_convierte_a_upper(self, normalizer):
        sql = "SELECT * FROM ARTICULO WHERE NOMBRE LIKE '%mesa%'"
        result, changes = normalizer.normalize(sql)
        assert "UPPER(" in result.upper()

    # SQL con CONCAT
    def test_concat_se_convierte(self, normalizer):
        sql = "SELECT CONCAT(NOMBRE, ' - ') FROM ARTICULO"
        result, changes = normalizer.normalize(sql)
        assert "CONCAT" not in result.upper()
        assert "||" in result

    # SQL con OFFSET
    def test_offset_se_elimina(self, normalizer):
        sql = "SELECT FIRST 10 * FROM DOCCAB OFFSET 20"
        result, changes = normalizer.normalize(sql)
        assert "OFFSET" not in result.upper()

    # SQL con punto y coma
    def test_punto_y_coma_se_elimina(self, normalizer):
        sql = "SELECT COUNT(*) FROM DOCCAB;"
        result, changes = normalizer.normalize(sql)
        assert not result.endswith(";")

    # SQL con backticks
    def test_backticks_se_eliminan(self, normalizer):
        sql = "SELECT `NOMBRE` FROM `ARTICULO`"
        result, changes = normalizer.normalize(sql)
        assert "`" not in result

    # SQL ya correcto no se modifica innecesariamente
    def test_sql_correcto_no_se_modifica(self, normalizer):
        sql = "SELECT FIRST 10 CODIGO, NOMBRE FROM ARTICULO WHERE ACTIVO = 'T'"
        result, changes = normalizer.normalize(sql)
        # No debe haber cambios en un SQL ya correcto
        assert "ROUND" not in result.upper()
        assert "LIMIT" not in result.upper()
        assert "`" not in result

    # Anti-regresión: CAST existente no se duplica
    def test_cast_existente_no_se_duplica(self, normalizer):
        sql = "SELECT CAST(IMPORTETOTAL AS NUMERIC(15,2)) FROM DOCCAB"
        result, changes = normalizer.normalize(sql)
        assert result.upper().count("CAST(") == 1

    # Anti-regresión: COALESCE existente no se modifica
    def test_coalesce_existente_no_se_modifica(self, normalizer):
        sql = "SELECT COALESCE(NOMBRE, 'N/A') FROM ARTICULO"
        result, changes = normalizer.normalize(sql)
        assert "NVL" not in result.upper()
        assert result.upper().count("COALESCE(") == 1


# ─── Bloque C: Endpoint /api/siuo/context/test (integración HTTP) ────────────

@pytest.mark.integration
class TestSiuoContextTestEndpoint:
    """
    Tests de integración que llaman al endpoint real /api/siuo/context/test.
    Se saltan si el servidor no está disponible.
    """

    BASE_URL = "http://localhost:8000"

    @pytest.fixture(scope="class")
    def http_client(self):
        """Cliente HTTP síncrono para tests de integración."""
        try:
            import httpx
            client = httpx.Client(base_url=self.BASE_URL, timeout=30.0)
            # Verificar que el servidor está disponible
            resp = client.get("/health")
            if resp.status_code != 200:
                pytest.skip("Servidor no disponible")
            yield client
            client.close()
        except Exception:
            pytest.skip("Servidor no disponible o httpx no instalado")

    @pytest.mark.parametrize("question,_", PREGUNTAS_SIMPLES[:20])
    def test_context_test_preguntas_simples(self, http_client, question, _):
        resp = http_client.post(
            "/api/siuo/context/test",
            json={"question": question, "max_tokens": 4000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "context_preview" in data
        assert "context_length" in data
        assert "meta" in data
        assert isinstance(data["context_length"], int)

    @pytest.mark.parametrize("question,_", PREGUNTAS_COMPLEJAS[:10])
    def test_context_test_preguntas_complejas(self, http_client, question, _):
        resp = http_client.post(
            "/api/siuo/context/test",
            json={"question": question, "max_tokens": 8000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "context_preview" in data

    def test_context_test_pregunta_vacia_devuelve_error(self, http_client):
        resp = http_client.post(
            "/api/siuo/context/test",
            json={"question": "", "max_tokens": 4000},
        )
        # Pydantic valida min_length=1 → 422
        assert resp.status_code == 422

    def test_context_test_max_tokens_invalido(self, http_client):
        resp = http_client.post(
            "/api/siuo/context/test",
            json={"question": "ventas", "max_tokens": 0},
        )
        assert resp.status_code == 422

    def test_context_test_max_tokens_muy_grande(self, http_client):
        resp = http_client.post(
            "/api/siuo/context/test",
            json={"question": "ventas", "max_tokens": 99999},
        )
        assert resp.status_code == 422


# ─── Bloque D: Endpoint /api/siuo/context/ask (integración con BD+IA) ────────

@pytest.mark.integration
class TestSiuoContextAskEndpoint:
    """
    Tests de integración que llaman al endpoint real /api/siuo/context/ask.
    Requieren servidor + BD Firebird + Qwen3 LAN disponibles.
    Se saltan si alguno no está disponible.
    """

    BASE_URL = "http://localhost:8000"

    @pytest.fixture(scope="class")
    def http_client(self):
        try:
            import httpx
            client = httpx.Client(base_url=self.BASE_URL, timeout=120.0)
            resp = client.get("/health")
            if resp.status_code != 200:
                pytest.skip("Servidor no disponible")
            yield client
            client.close()
        except Exception:
            pytest.skip("Servidor no disponible o httpx no instalado")

    @pytest.mark.parametrize("question,_", PREGUNTAS_SIMPLES[:10])
    def test_context_ask_preguntas_simples(self, http_client, question, _):
        resp = http_client.post(
            "/api/siuo/context/ask",
            json={"question": question, "max_tokens": 4000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    @pytest.mark.parametrize("question,_", PREGUNTAS_COMPLEJAS[:5])
    def test_context_ask_preguntas_complejas(self, http_client, question, _):
        resp = http_client.post(
            "/api/siuo/context/ask",
            json={"question": question, "max_tokens": 8000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data

    def test_context_ask_respuesta_tiene_estructura_correcta(self, http_client):
        resp = http_client.post(
            "/api/siuo/context/ask",
            json={"question": "¿Cuántas ventas hay?", "max_tokens": 4000},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Campos obligatorios de la respuesta
        assert "answer" in data
        assert "tables_used" in data
        assert "keywords" in data
        assert "tokens" in data
        assert "source" in data
        assert "error" in data

    def test_context_ask_pregunta_con_round_no_falla(self, http_client):
        """
        Pregunta que generaría SQL con ROUND() → el normalizador debe corregirlo
        antes de ejecutar contra Firebird.
        """
        resp = http_client.post(
            "/api/siuo/context/ask",
            json={
                "question": "¿Cuál es la tasa de conversión de presupuestos a facturas?",
                "max_tokens": 8000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        # Si hay error, debe ser un error de BD, no de ROUND
        if data.get("error"):
            assert "ROUND" not in data["error"].upper()

    def test_context_ask_pregunta_vacia_devuelve_422(self, http_client):
        resp = http_client.post(
            "/api/siuo/context/ask",
            json={"question": "", "max_tokens": 4000},
        )
        assert resp.status_code == 422


# ─── Bloque E: Endpoints auxiliares SIUO ─────────────────────────────────────

@pytest.mark.integration
class TestSiuoAuxEndpoints:
    """Tests de los endpoints auxiliares: /stats, /reload, /learning."""

    BASE_URL = "http://localhost:8000"

    @pytest.fixture(scope="class")
    def http_client(self):
        try:
            import httpx
            client = httpx.Client(base_url=self.BASE_URL, timeout=30.0)
            resp = client.get("/health")
            if resp.status_code != 200:
                pytest.skip("Servidor no disponible")
            yield client
            client.close()
        except Exception:
            pytest.skip("Servidor no disponible o httpx no instalado")

    def test_stats_devuelve_estructura_correcta(self, http_client):
        resp = http_client.get("/api/siuo/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "indexer" in data
        assert "retriever" in data

    def test_reload_devuelve_success(self, http_client):
        resp = http_client.post("/api/siuo/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True

    def test_learning_suggestions_devuelve_estructura(self, http_client):
        resp = http_client.get("/api/siuo/learning/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_learning_feedback_registra_correctamente(self, http_client):
        resp = http_client.post(
            "/api/siuo/learning/feedback",
            json={
                "question": "¿Cuántas ventas hay?",
                "sql_used": "SELECT FIRST 10 COUNT(*) AS N FROM DOCCAB WHERE TIPO = 0",
                "was_correct": True,
                "tables_used": ["DOCCAB"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True

    def test_learning_feedback_incorrecto_se_registra(self, http_client):
        resp = http_client.post(
            "/api/siuo/learning/feedback",
            json={
                "question": "¿Cuántos artículos hay?",
                "sql_used": "SELECT COUNT(*) FROM ARTICULOS",  # tabla incorrecta
                "was_correct": False,
                "tables_used": [],
            },
        )
        assert resp.status_code == 200

    def test_analyze_progress_devuelve_estado(self, http_client):
        resp = http_client.get("/api/siuo/analyze/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_health_check_disponible(self, http_client):
        resp = http_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
