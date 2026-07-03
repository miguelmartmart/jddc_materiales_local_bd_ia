"""
query_library_constants.py — Constantes centralizadas para la biblioteca de consultas.

PRINCIPIO: Toda constante aquí. Nunca literales en el código.
DEVIA: backend/modules/db_simulator/DEVIA.md
"""

# ─── Tipos de documento DOCCAB (TIPO) ────────────────────────────────────────
# IMPORTANTE: Valores reales verificados en la BD de JDDC (tabla DOCCAB).
# Ventas / Clientes
DOC_TIPO_PRESUPUESTO_CLIENTE   = 0   # Presupuesto de cliente
DOC_TIPO_PEDIDO_CLIENTE        = 1   # Pedido de cliente
DOC_TIPO_ALBARAN_CLIENTE       = 2   # Albarán de cliente
DOC_TIPO_FACTURA_VENTA         = 3   # Factura de venta (cliente)
# Compras / Proveedores
DOC_TIPO_PRESUPUESTO_PROVEEDOR = 10  # Presupuesto de proveedor
DOC_TIPO_PEDIDO_PROVEEDOR      = 11  # Pedido a proveedor
DOC_TIPO_ALBARAN_PROVEEDOR     = 12  # Albarán de proveedor
DOC_TIPO_FACTURA_COMPRA        = 13  # Factura de compra (proveedor)
# Almacén
DOC_TIPO_MOVIMIENTO_ALMACEN    = 21  # Movimiento de almacén
DOC_TIPO_RECUENTO_ALMACEN      = 31  # Recuento de almacén
# Producción y Certificaciones
DOC_TIPO_CERTIFICACION         = 51  # Certificación
DOC_TIPO_PRODUCCION            = 52  # Producción
DOC_TIPO_CERT_SUBCONTRATA      = 61  # Certificación de subcontrata
# Aliases de compatibilidad (nombres anteriores — no usar en código nuevo)
DOC_TIPO_PRESUPUESTO           = 0   # alias → DOC_TIPO_PRESUPUESTO_CLIENTE
DOC_TIPO_ALBARAN               = 2   # alias → DOC_TIPO_ALBARAN_CLIENTE (era 11, incorrecto)
DOC_TIPO_FACTURA               = 13  # alias → DOC_TIPO_FACTURA_COMPRA

# ─── Estados de documento (ESTADO) ───────────────────────────────────────────
DOC_ESTADO_PENDIENTE = 0
DOC_ESTADO_COMPLETADO = 1

# ─── Tipos de movimiento de caja (TIPO en tabla CAJA) ────────────────────────
CAJA_TIPO_ENTRADA = 1
CAJA_TIPO_SALIDA = 2

# ─── Umbrales de negocio (configurables) ─────────────────────────────────────
UMBRAL_FACTURA_ALTO_IMPORTE = 5000       # €: factura considerada de alto valor
UMBRAL_FACTURA_RIESGO_COBRO = 3000      # €: factura con riesgo de impago
UMBRAL_DIAS_PRESUPUESTO_RIESGO = 30     # días sin respuesta = riesgo
UMBRAL_DIAS_PRESUPUESTO_CADUCADO = 60   # días sin respuesta = caducado
UMBRAL_DIAS_CLIENTE_INACTIVO = 90       # días sin compra = cliente inactivo
UMBRAL_DIAS_CLIENTE_FUGA = 60           # días sin compra (cliente recurrente) = riesgo fuga
UMBRAL_STOCK_CRITICO = 2                # unidades: stock crítico
UMBRAL_STOCK_BAJO = 3                   # unidades: stock bajo
UMBRAL_DESCUENTO_EXCESIVO = 20          # %: descuento que erosiona margen
UMBRAL_MARGEN_MINIMO = 10               # %: margen bruto mínimo aceptable
UMBRAL_CONCENTRACION_CLIENTES = 60     # %: top 5 clientes = riesgo concentración
UMBRAL_CONVERSION_MINIMA = 30           # %: tasa conversión presupuesto mínima
UMBRAL_RETENCION_MINIMA = 40            # %: tasa retención clientes mínima
UMBRAL_COMPRAS_RECURRENTE = 2           # n compras para considerar cliente recurrente
UMBRAL_COMPRAS_ALTO_VALOR = 3           # n compras para considerar cliente alto valor
UMBRAL_DIAS_SAT_ESCALADO = 5            # días SAT abierto = escalar
UMBRAL_PEDIDOS_CONSOLIDAR = 3           # n pedidos pequeños = consolidar
UMBRAL_IMPORTE_PEDIDO_PEQUENO = 500     # €: pedido pequeño (candidato a consolidar)
UMBRAL_STOCK_MUERTO_DIAS = 90           # días sin venta = stock muerto
UMBRAL_STOCK_SOBRESTOCK_FACTOR = 2      # factor sobre demanda 90d = sobrestock

# ─── Límites de resultados ────────────────────────────────────────────────────
LIMIT_TOP_CLIENTES = 10
LIMIT_TOP_PRODUCTOS = 10
LIMIT_TOP_PROVEEDORES = 10
LIMIT_ALERTAS = 20
LIMIT_HISTORICO = 30
LIMIT_PREDICCION = 15

# ─── Notas sobre calidad de datos ────────────────────────────────────────────
# ADVERTENCIA: La BD real de JDDC puede tener inconsistencias conocidas:
#   - CODART en DOCLIN puede ser texto o número → usar CAST(CODART AS INTEGER)
#   - PROVINCIA puede estar vacía o NULL → usar COALESCE
#   - FORMAPAGO puede no estar normalizado → agrupar con precaución
#   - CODAGENTE=0 significa sin agente asignado → filtrar con CODAGENTE > 0
#   - ESTADO=0 no siempre significa "pendiente" en todos los tipos de documento
#   - Algunos documentos pueden tener IMPORTETOTAL=0 por error de entrada
DATA_QUALITY_NOTES = {
    "DOCLIN.CODART": "Puede ser texto o número. Usar CAST(CODART AS INTEGER) para JOIN con ARTICULO.",
    "CLIENTE.PROVINCIA": "Puede ser NULL o vacío. Usar COALESCE(PROVINCIA, 'Sin especificar').",
    "DOCCAB.CODAGENTE": "0 = sin agente. Filtrar con CODAGENTE > 0 para análisis de comerciales.",
    "DOCCAB.ESTADO": "0 = pendiente en la mayoría de tipos, pero verificar por tipo de documento.",
    "DOCCAB.IMPORTETOTAL": "Puede ser 0 por error. Filtrar con IMPORTETOTAL > 0 para análisis financiero.",
    "ARTICULO.CODPROVEEDOR": "0 = sin proveedor. Filtrar con PROVEEDDEFECTO > 0 para análisis de compras.",
}

# ─── Clasificaciones ──────────────────────────────────────────────────────────
DEPARTAMENTOS = [
    "Ventas", "Compras", "Almacén", "Finanzas",
    "RRHH", "Dirección", "SAT / Técnico", "Marketing",
    "Produccion",  # Certificaciones (51), Producción (52), Cert. Subcontrata (61)
    "Todos",
]

ROLES = [
    "Director", "Gerente", "Comercial",
    "Técnico", "Administrativo", "Almacenero", "Todos",
]

TIPOS_ANALISIS = [
    "KPI", "Riesgo", "Optimización", "Predicción",
    "Ahorro", "Operacional", "Estratégico",
    "Calidad", "Cliente", "Proveedor", "Producto", "Financiero",
    "Alerta", "Modernización",
    "Certificaciones",  # Documentos TIPO 51 (certificación), 52 (producción), 61 (cert. subcontrata)
]

URGENCIAS = ["Crítico", "Alto", "Medio", "Bajo"]

# ─── Iconos por tipo (para el frontend) ──────────────────────────────────────
TIPO_ICONOS = {
    "KPI":          "📊",
    "Riesgo":       "🔴",
    "Optimización": "⚙️",
    "Predicción":   "🔮",
    "Ahorro":       "💰",
    "Operacional":  "📋",
    "Estratégico":  "🎯",
    "Calidad":      "✅",
    "Cliente":      "👥",
    "Proveedor":    "🏭",
    "Producto":     "📦",
    "Financiero":   "💳",
    "Alerta":            "⚠️",
    "Modernización":     "🚀",
    "Certificaciones":   "📋",  # TIPO 51/52/61
}

URGENCIA_COLORES = {
    "Crítico": "#dc2626",
    "Alto":    "#ea580c",
    "Medio":   "#ca8a04",
    "Bajo":    "#16a34a",
}

DEPT_ICONOS = {
    "Ventas":        "🛒",
    "Compras":       "🏭",
    "Almacén":       "📦",
    "Finanzas":      "💰",
    "RRHH":          "👥",
    "Dirección":     "🎯",
    "SAT / Técnico": "🔧",
    "Marketing":     "📣",
    "Produccion":    "🏗️",  # Certificaciones, Producción, Subcontrata
    "Todos":         "🌐",
}
