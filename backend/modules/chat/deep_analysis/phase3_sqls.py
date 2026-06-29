"""
phase3_sqls.py — SQLs fijos y de resolución para Fase 3 del DeepAnalysisAgent.

Contiene:
  - _build_fixed_sqls(): SQLs que SIEMPRE se incluyen según el contexto
    (distribución temporal, instalaciones únicas, estado de presupuestos)
  - _build_resolution_sqls(): SQLs para RESOLVER inconsistencias detectadas en Fase 4
    (año futurista, tipo incorrecto, importe anómalo, contenido mixto)

Principio: SQLs deterministas, sin llamadas a IA, ultra-resilientes.
"""

import logging
from typing import Dict, List

try:
    from backend.modules.chat.deep_analysis.knowledge_store import get_knowledge_store
except ImportError:
    get_knowledge_store = None  # type: ignore

logger = logging.getLogger(__name__)


# ─── Helpers de módulo (sin estado, reutilizables) ───────────────────────────

def _detect_tipo_filter(msg: str) -> str:
    """
    Detecta el filtro TIPO adecuado según las palabras clave de la pregunta.
    Devuelve la cláusula SQL (ej: 'TIPO = 2') o '' si no se detecta tipo específico.

    MAPEO VERIFICADO (2026-06-25 — confirmado por usuario):
      0=presupuesto_cliente  1=pedido_cliente   2=albarán_cliente   3=factura_cliente
      10=presupuesto_prov   11=pedido_prov      12=albarán_prov     13=factura_prov
      21=mov.almacén   31=recuento   51=certificación   52=producción   61=cert.subcontrata

    ORDEN IMPORTANTE: los tipos más específicos se comprueban antes que los más generales.
    "albaranes sin facturar" → TIPO=2 (albarán de cliente), el verbo "facturar" no cambia esto.
    """
    msg = msg.lower()
    # Proveedor context: distinguir albarán/pedido/factura de proveedor vs cliente
    is_proveedor = any(k in msg for k in ["proveedor", "proveedores", "compra", "compras"])

    # Albarán ANTES que factura (evita que "albaranes sin facturar" → TIPO=13)
    if any(k in msg for k in ["albarán", "albaran", "albaranes"]):
        return "TIPO = 12" if is_proveedor else "TIPO = 2"   # 2=albarán cliente, 12=albarán prov
    if any(k in msg for k in ["presupuesto", "presupuestos"]):
        return "TIPO = 10" if is_proveedor else "TIPO = 0"
    if any(k in msg for k in ["pedido", "pedidos"]):
        return "TIPO = 11" if is_proveedor else "TIPO = 1"   # 11=pedido prov, 1=pedido cliente
    if any(k in msg for k in ["abono", "abonos"]):
        return "TIPO = 3"
    if any(k in msg for k in ["sat", "servicio técnico", "servicio tecnico", "orden de trabajo"]):
        return ""   # SAT no tiene TIPO fijo verificado — no filtrar por TIPO
    # Factura al final — es el más genérico y puede aparecer como verbo ("sin facturar")
    if any(k in msg for k in ["factura ", "facturas", "facturado", "facturación", "facturacion",
                               " factura", "la factura", "las facturas"]):
        return "TIPO = 13" if is_proveedor else "TIPO = 3"   # 3=factura cliente, 13=factura prov
    if any(k in msg for k in ["movimiento de almacén", "movimiento almacen", "mov almacen"]):
        return "TIPO = 21"
    return ""


def _detect_month_number(msg: str) -> int:
    """
    Detecta el número de mes (1-12) mencionado en la pregunta.
    Devuelve 0 si no se detecta ningún mes.
    """
    _MONTHS = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        # Abreviaturas
        "ene": 1, "feb": 2, "mar": 3, "abr": 4,
        "may": 5, "jun": 6, "jul": 7, "ago": 8,
        "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    }
    msg_lower = msg.lower()
    for name, num in _MONTHS.items():
        if name in msg_lower:
            return num
    return 0


class Phase3SqlsMixin:
    """
    Mixin con los SQLs fijos y de resolución para Fase 3.
    No requiere dependencias externas — solo lógica determinista.
    """

    def _build_fixed_sqls(self, question: str, phase2_data: Dict) -> List[Dict]:
        """
        SQLs fijos que SIEMPRE se incluyen según el contexto de la pregunta.
        Enriquece con columnas conocidas del KnowledgeStore si la BD no estaba disponible.
        """
        fixed = []
        msg = question.lower()
        doccab_info = phase2_data.get("DOCCAB", {})
        has_serie = doccab_info.get("has_serie", False)
        has_codigoobra = doccab_info.get("has_codigoobra", False)

        # Enriquecer con columnas conocidas del KnowledgeStore
        if not has_serie or not has_codigoobra:
            try:
                if get_knowledge_store is not None:
                    store = get_knowledge_store()
                    known = store.get_table("DOCCAB")
                    known_cols = [c.upper() for c in known.get("columns_real", [])]
                    if known_cols:
                        if not has_serie and "SERIE" in known_cols:
                            has_serie = True
                        if not has_codigoobra and "CODIGOOBRA" in known_cols:
                            has_codigoobra = True
            except Exception as e:
                logger.debug(f"[DEEP AGENT] KnowledgeStore en _build_fixed_sqls: {e}")

        # ── Detección de tema principal de la pregunta ────────────────────────────
        # Si la pregunta es claramente sobre artículos/productos, los SQLs genéricos
        # de DOCCAB (distribución temporal, instalaciones) son irrelevantes y confunden
        # a la IA en la síntesis. Se suprimen para mantener el foco en el tema real.
        # Mismas listas que art_kw/comp_kw de abajo — deben mantenerse sincronizadas
        _art_kw_early = [
            "artículo", "articulo", "artículos", "artículos",
            "producto", "productos",
            "item", "items",
            "referencia", "referencias",
        ]
        _art_movement_kw = [
            "rotación", "rotacion", "rotan", "rota",
            "negociar", "negociación", "negociacion", "volumen",
            "candidatos", "candidato",
            "frecuencia", "frecuente", "frecuentes",
            "mayor", "mayores", "mejor", "mejores",
            "demanda", "popular", "populares",
            "compra", "venta", "compras", "ventas", "top",
            "vendido", "vendidos", "comprado", "comprados",
            "más", "mas",
        ]
        _is_article_focused = (
            any(k in msg for k in _art_kw_early) and
            any(k in msg for k in _art_movement_kw)
        )

        # SQL FIJO 0: Resumen general por tipo de documento (SIEMPRE para DOCCAB)
        # Útil para CUALQUIER pregunta — da contexto general del volumen de datos
        # EXCEPCIÓN: si la pregunta es sobre artículos, este SQL es irrelevante y confunde.
        # TIPOS verificados (2026-06-25): 0=presupuesto_cli,2=albarán_cli,3=factura_cli,
        #   1=pedido_cli,10=presupuesto_prov,11=pedido_prov,12=albarán_prov,13=factura_prov
        if "DOCCAB" in phase2_data and not _is_article_focused:
            fixed.append({
                "objetivo": "Distribución completa de tipos de documento (TODOS los tipos existentes)",
                "sql": (
                    "SELECT TIPO, COUNT(*) AS N, "
                    "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
                    "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
                    "FROM DOCCAB "
                    "GROUP BY TIPO ORDER BY N DESC"
                )
            })

        # SQL FIJO 1: Distribución temporal — adaptada al tipo de documento preguntado
        # EXCEPCIÓN: si la pregunta es sobre artículos, este SQL es irrelevante y confunde.
        if "DOCCAB" in phase2_data and not _is_article_focused:
            # Detectar tipo de documento según la pregunta
            _tipo_filter = _detect_tipo_filter(msg)
            _tipo_label = _tipo_filter if _tipo_filter else "todos los tipos"

            if has_serie:
                fixed.append({
                    "objetivo": f"Distribución por año y serie ({_tipo_label})",
                    "sql": (
                        "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, SERIE, COUNT(*) AS N, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                        f"FROM DOCCAB WHERE {_tipo_filter + ' AND ' if _tipo_filter else ''}FECHA IS NOT NULL "
                        "GROUP BY EXTRACT(YEAR FROM FECHA), SERIE "
                        "ORDER BY ANO DESC, N DESC"
                    )
                })
            else:
                fixed.append({
                    "objetivo": f"Distribución por año ({_tipo_label})",
                    "sql": (
                        "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                        f"FROM DOCCAB WHERE {_tipo_filter + ' AND ' if _tipo_filter else ''}FECHA IS NOT NULL "
                        "GROUP BY EXTRACT(YEAR FROM FECHA) ORDER BY ANO DESC"
                    )
                })

            # SQL FIJO 1b: Distribución por mes (SIEMPRE — detecta estacionalidad y anomalías)
            fixed.append({
                "objetivo": f"Distribución por mes del año actual ({_tipo_label})",
                "sql": (
                    "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, EXTRACT(MONTH FROM FECHA) AS MES, "
                    "COUNT(*) AS N, CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                    f"FROM DOCCAB WHERE {_tipo_filter + ' AND ' if _tipo_filter else ''}FECHA IS NOT NULL "
                    "AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE) "
                    "GROUP BY EXTRACT(YEAR FROM FECHA), EXTRACT(MONTH FROM FECHA) "
                    "ORDER BY ANO DESC, MES DESC"
                )
            })

            # SQL FIJO 1c: Si la pregunta menciona un mes específico, añadir consulta directa
            _month_num = _detect_month_number(msg)
            if _month_num:
                fixed.append({
                    "objetivo": f"Facturas/documentos en mes {_month_num} del año actual (verificación directa)",
                    "sql": (
                        "SELECT COUNT(*) AS N_DOCS, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
                        "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
                        f"FROM DOCCAB WHERE {_tipo_filter + ' AND ' if _tipo_filter else ''}"
                        f"EXTRACT(MONTH FROM FECHA) = {_month_num} "
                        "AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE)"
                    )
                })
                # También desglose por cliente para ese mes
                fixed.append({
                    "objetivo": f"Top clientes en mes {_month_num} del año actual",
                    "sql": (
                        "SELECT FIRST 10 CODCLIENTE, COUNT(*) AS N_DOCS, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                        f"FROM DOCCAB WHERE {_tipo_filter + ' AND ' if _tipo_filter else ''}"
                        f"EXTRACT(MONTH FROM FECHA) = {_month_num} "
                        "AND EXTRACT(YEAR FROM FECHA) = EXTRACT(YEAR FROM CURRENT_DATE) "
                        "GROUP BY CODCLIENTE ORDER BY TOTAL_EUR DESC"
                    )
                })

        # SQL FIJO 2: Instalaciones únicas vs presupuestos
        if any(k in msg for k in ["presupuesto", "instalación", "instalacion", "tasa", "éxito"]):
            if has_codigoobra:
                fixed.append({
                    "objetivo": "Presupuestos vs instalaciones únicas (CODIGOOBRA)",
                    "sql": (
                        "SELECT COUNT(*) AS TOTAL_PRESUPUESTOS, "
                        "COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS, "
                        "COUNT(DISTINCT CODIGOOBRA) AS OBRAS_DISTINTAS, "
                        "CAST(COUNT(*) AS NUMERIC(15,2)) / NULLIF(COUNT(DISTINCT CODIGOOBRA), 0) "
                        "AS PRESUPUESTOS_POR_OBRA FROM DOCCAB WHERE TIPO = 0"
                    )
                })
            else:
                fixed.append({
                    "objetivo": "Presupuestos vs clientes únicos",
                    "sql": (
                        "SELECT COUNT(*) AS TOTAL_PRESUPUESTOS, "
                        "COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS, "
                        "CAST(COUNT(*) AS NUMERIC(15,2)) / NULLIF(COUNT(DISTINCT CODCLIENTE), 0) "
                        "AS PRESUPUESTOS_POR_CLIENTE FROM DOCCAB WHERE TIPO = 0"
                    )
                })

        # SQLs FIJOS 3a-3h: Estado de presupuestos
        if any(k in msg for k in ["presupuesto", "tasa", "éxito", "exito", "aceptado", "aceptados"]):
            fixed.extend([
                {
                    "objetivo": "Distribución de ESTADOPEND en presupuestos (estado real)",
                    "sql": (
                        "SELECT ESTADOPEND, COUNT(*) AS N FROM DOCCAB "
                        "WHERE TIPO = 0 GROUP BY ESTADOPEND ORDER BY N DESC"
                    )
                },
                {
                    "objetivo": "Presupuestos aceptados por tipo de documento destino (factura/pedido)",
                    "sql": (
                        "SELECT d.TIPO AS TIPO_DESTINO, COUNT(DISTINCT dd.CODDOCUMENTO) AS N_PRESUPUESTOS "
                        "FROM DOCDESTINO dd "
                        "JOIN DOCCAB c ON c.CODIGO = dd.CODDOCUMENTO AND c.TIPO = 0 "
                        "JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO "
                        "GROUP BY d.TIPO ORDER BY N_PRESUPUESTOS DESC"
                    )
                },
                {
                    "objetivo": "Total presupuestos con cualquier documento destino vinculado",
                    "sql": (
                        "SELECT COUNT(DISTINCT c.CODIGO) AS TOTAL_PRESUPUESTOS, "
                        "COUNT(DISTINCT dd.CODDOCUMENTO) AS CON_DESTINO, "
                        "COUNT(DISTINCT c.CODIGO) - COUNT(DISTINCT dd.CODDOCUMENTO) AS SIN_DESTINO "
                        "FROM DOCCAB c LEFT JOIN DOCDESTINO dd ON dd.CODDOCUMENTO = c.CODIGO "
                        "WHERE c.TIPO = 0"
                    )
                },
                {
                    "objetivo": "Columnas de DOCCAB que contienen ESTADO o ACEPTA (metadatos BD)",
                    "sql": (
                        "SELECT FIRST 20 RDB$FIELD_NAME FROM RDB$RELATION_FIELDS "
                        "WHERE RDB$RELATION_NAME = 'DOCCAB' "
                        "AND (UPPER(RDB$FIELD_NAME) LIKE '%ESTADO%' "
                        "OR UPPER(RDB$FIELD_NAME) LIKE '%ACEPTA%' "
                        "OR UPPER(RDB$FIELD_NAME) LIKE '%SEGUIM%' "
                        "OR UPPER(RDB$FIELD_NAME) LIKE '%RESULT%') "
                        "ORDER BY RDB$FIELD_POSITION"
                    )
                },
                {
                    "objetivo": "Distribución de ESTADOPENDVENCOM en presupuestos (estado comercial)",
                    "sql": (
                        "SELECT ESTADOPENDVENCOM, COUNT(*) AS N FROM DOCCAB "
                        "WHERE TIPO = 0 GROUP BY ESTADOPENDVENCOM ORDER BY N DESC"
                    )
                },
                {
                    "objetivo": "Cruce ESTADOPEND x ESTADOPENDVENCOM (definición real de aceptado)",
                    "sql": (
                        "SELECT ESTADOPEND, ESTADOPENDVENCOM, COUNT(*) AS N FROM DOCCAB "
                        "WHERE TIPO = 0 GROUP BY ESTADOPEND, ESTADOPENDVENCOM ORDER BY N DESC"
                    )
                },
                {
                    "objetivo": "Presupuestos convertidos a factura (TIPO=13) o pedido (TIPO=12)",
                    "sql": (
                        "SELECT SUM(CASE WHEN d.TIPO = 13 THEN 1 ELSE 0 END) AS A_FACTURA, "
                        "SUM(CASE WHEN d.TIPO = 12 THEN 1 ELSE 0 END) AS A_PEDIDO, "
                        "SUM(CASE WHEN d.TIPO = 11 THEN 1 ELSE 0 END) AS A_ALBARAN, "
                        "SUM(CASE WHEN d.TIPO NOT IN (11,12,13) THEN 1 ELSE 0 END) AS A_OTRO, "
                        "COUNT(DISTINCT dd.CODDOCUMENTO) AS TOTAL_CON_DESTINO "
                        "FROM DOCDESTINO dd "
                        "JOIN DOCCAB c ON c.CODIGO = dd.CODDOCUMENTO AND c.TIPO = 0 "
                        "JOIN DOCCAB d ON d.CODIGO = dd.CODDOCUMENTODESTINO"
                    )
                },
                {
                    "objetivo": "Muestra de presupuestos con ESTADOPEND y ESTADOPENDVENCOM (valores reales)",
                    "sql": (
                        "SELECT FIRST 10 CODIGO, SERIE, ESTADOPEND, ESTADOPENDVENCOM, "
                        "CAST(IMPORTETOTAL AS NUMERIC(15,2)) AS IMPORTE "
                        "FROM DOCCAB WHERE TIPO = 0 ORDER BY CODIGO DESC"
                    )
                },
            ])

        # ── SQLs FIJOS para preguntas de IMPORTE / MEDIA / PROMEDIO ─────────────
        # Se activan cuando la pregunta menciona importes, medias o promedios.
        importe_kw = ["importe", "media", "promedio", "precio", "facturado", "facturación",
                      "facturacion", "ingreso", "ingresos", "cobro", "cobros", "total"]
        if any(k in msg for k in importe_kw):
            fixed.append({
                "objetivo": "Importe medio, mínimo y máximo por tipo de documento",
                "sql": (
                    "SELECT TIPO, COUNT(*) AS N, "
                    "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR, "
                    "CAST(MIN(IMPORTETOTAL) AS NUMERIC(15,2)) AS MIN_EUR, "
                    "CAST(MAX(IMPORTETOTAL) AS NUMERIC(15,2)) AS MAX_EUR "
                    "FROM DOCCAB WHERE IMPORTETOTAL > 0 "
                    "GROUP BY TIPO ORDER BY N DESC"
                )
            })
            fixed.append({
                "objetivo": "Importe total y medio de facturas (TIPO=13) por año",
                "sql": (
                    "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N_FACTURAS, "
                    "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
                    "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
                    "FROM DOCCAB WHERE TIPO = 13 AND FECHA IS NOT NULL "
                    "GROUP BY EXTRACT(YEAR FROM FECHA) ORDER BY ANO DESC"
                )
            })

        # ── SQLs FIJOS para preguntas de CLIENTES ────────────────────────────────
        # Tipos de documento del lado CLIENTE: 0=presupuesto, 1=pedido, 2=albarán, 3=factura
        # En el simulador solo existen TIPO 0 y 2 → NO filtrar por TIPO=3 solo;
        # usar todos los tipos cliente para maximizar datos disponibles.
        # NOTA: c.NOMBRE no existe → usar NOMBRECOMERCIAL (verificado en esquema real)
        cliente_kw = [
            "cliente", "clientes", "comprador", "compradores",
            "concentración", "concentracion", "riesgo", "dependencia",
            "ranking", "principales", "mayor", "top",
        ]
        if any(k in msg for k in cliente_kw):
            # SQL A: Top 10 clientes con nombre (JOIN con CLIENTE) — todos los tipos cliente
            fixed.append({
                "objetivo": "Top 10 clientes por importe total (todos los documentos cliente)",
                "sql": (
                    "SELECT FIRST 10 d.CODCLIENTE, c.NOMBRECOMERCIAL, "
                    "COUNT(d.CODIGO) AS N_DOCS, "
                    "CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                    "FROM DOCCAB d "
                    "LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
                    "WHERE d.CODCLIENTE IS NOT NULL AND d.CODCLIENTE > 0 "
                    "GROUP BY d.CODCLIENTE, c.NOMBRECOMERCIAL "
                    "ORDER BY TOTAL_EUR DESC"
                )
            })
            # SQL B: Total global + nº de clientes (para calcular % por cliente en síntesis)
            fixed.append({
                "objetivo": "Total global y número de clientes distintos (base para % concentración)",
                "sql": (
                    "SELECT COUNT(DISTINCT CODCLIENTE) AS CLIENTES_DISTINTOS, "
                    "COUNT(*) AS TOTAL_DOCUMENTOS, "
                    "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_GLOBAL_EUR, "
                    "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
                    "FROM DOCCAB WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0"
                )
            })
            # SQL C (solo si pregunta sobre concentración/Pareto/riesgo): cálculo directo
            if any(k in msg for k in ["concentración", "concentracion", "riesgo", "dependencia",
                                       "pareto", "80/20", "top 5", "cinco"]):
                fixed.append({
                    "objetivo": "Concentración: importe acumulado top 5 clientes vs total",
                    "sql": (
                        "SELECT "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_TOP5, "
                        "CAST((SELECT SUM(IMPORTETOTAL) FROM DOCCAB "
                        "  WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0) "
                        "AS NUMERIC(15,2)) AS TOTAL_GLOBAL, "
                        "CAST(SUM(IMPORTETOTAL) * 100.0 / "
                        "  NULLIF((SELECT SUM(IMPORTETOTAL) FROM DOCCAB "
                        "    WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0), 0) "
                        "AS NUMERIC(8,2)) AS PCT_TOP5 "
                        "FROM DOCCAB "
                        "WHERE CODCLIENTE IN ("
                        "  SELECT FIRST 5 CODCLIENTE FROM DOCCAB "
                        "  WHERE CODCLIENTE IS NOT NULL AND CODCLIENTE > 0 "
                        "  GROUP BY CODCLIENTE ORDER BY SUM(IMPORTETOTAL) DESC"
                        ") AND CODCLIENTE IS NOT NULL AND CODCLIENTE > 0"
                    )
                })

        # ── SQLs FIJOS para PROYECTOS / ANÁLISIS ECONÓMICO ──────────────────────
        # Activos cuando la pregunta menciona: proyecto, obra, ejecución, presupuesto
        # proyectado, análisis económico, facturado vs previsto, coste real,
        # porcentaje de ejecución, certificación, retención
        proyecto_kw = ["proyecto", "proyectos", "obra", "obras", "ejecución", "ejecucion",
                       "análisis económico", "analisis economico", "previsto",
                       "certificado", "certificación", "certificacion",
                       "retención", "retencion", "partida", "partidas"]
        if any(k in msg for k in proyecto_kw):
            # PROY-1: Listado de proyectos con nombre y fechas
            fixed.append({
                "objetivo": "Listado de proyectos (código, nombre, fecha inicio/fin, tipo obra)",
                "sql": (
                    "SELECT FIRST 30 CODIGO, NOMBRE, CLIENTE, "
                    "FECHAINICIO, FECHAFIN, TIPOOBRA, TIPORETENCION "
                    "FROM PROYECTOS WHERE CODIGO IS NOT NULL "
                    "ORDER BY FECHAINICIO DESC"
                )
            })
            # PROY-2: Facturado por proyecto (facturas TIPO=13 enlazadas por CODPROYECTO)
            fixed.append({
                "objetivo": "Total facturado por proyecto (DOCCAB TIPO=13 por CODPROYECTO)",
                "sql": (
                    "SELECT FIRST 30 d.CODPROYECTO, p.NOMBRE, "
                    "COUNT(d.CODIGO) AS N_FACTURAS, "
                    "CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS FACTURADO_EUR "
                    "FROM DOCCAB d "
                    "LEFT JOIN PROYECTOS p ON p.CODIGO = d.CODPROYECTO "
                    "WHERE d.TIPO = 13 "
                    "AND d.CODPROYECTO IS NOT NULL AND d.CODPROYECTO <> '' "
                    "GROUP BY d.CODPROYECTO, p.NOMBRE "
                    "ORDER BY FACTURADO_EUR DESC"
                )
            })
            # PROY-3: Presupuesto proyectado por proyecto (via PRESUPROYE → DOCCAB TIPO=0)
            fixed.append({
                "objetivo": "Presupuesto proyectado por proyecto (PRESUPROYE → DOCCAB TIPO=0)",
                "sql": (
                    "SELECT FIRST 30 pre.CODPROYECTO, p.NOMBRE, "
                    "COUNT(pre.CODPRESUPUESTO) AS N_PRESUPUESTOS, "
                    "CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS PRESUPUESTO_EUR "
                    "FROM PRESUPROYE pre "
                    "JOIN DOCCAB d ON d.CODIGO = pre.CODPRESUPUESTO "
                    "LEFT JOIN PROYECTOS p ON p.CODIGO = pre.CODPROYECTO "
                    "WHERE d.TIPO = 0 "
                    "GROUP BY pre.CODPROYECTO, p.NOMBRE "
                    "ORDER BY PRESUPUESTO_EUR DESC"
                )
            })
            # PROY-4: % Ejecución — facturado vs presupuesto (por proyecto)
            # Firebird: subqueries correladas + NULLIF para evitar / 0
            fixed.append({
                "objetivo": "% Ejecución por proyecto: Facturado / Presupuesto × 100",
                "sql": (
                    "SELECT FIRST 30 "
                    "  pr.CODIGO AS PROYECTO, "
                    "  pr.NOMBRE, "
                    "  CAST(fact.FACTURADO AS NUMERIC(15,2)) AS FACTURADO_EUR, "
                    "  CAST(presu.PRESUPUESTO AS NUMERIC(15,2)) AS PRESUPUESTO_EUR, "
                    "  CAST(fact.FACTURADO * 100.0 / NULLIF(presu.PRESUPUESTO, 0) "
                    "    AS NUMERIC(5,2)) AS PORC_EJECUCION "
                    "FROM PROYECTOS pr "
                    "LEFT JOIN ( "
                    "  SELECT CODPROYECTO, SUM(IMPORTETOTAL) AS FACTURADO "
                    "  FROM DOCCAB WHERE TIPO = 13 "
                    "  AND CODPROYECTO IS NOT NULL AND CODPROYECTO <> '' "
                    "  GROUP BY CODPROYECTO "
                    ") fact ON fact.CODPROYECTO = pr.CODIGO "
                    "LEFT JOIN ( "
                    "  SELECT pre2.CODPROYECTO, SUM(d2.IMPORTETOTAL) AS PRESUPUESTO "
                    "  FROM PRESUPROYE pre2 "
                    "  JOIN DOCCAB d2 ON d2.CODIGO = pre2.CODPRESUPUESTO AND d2.TIPO = 0 "
                    "  GROUP BY pre2.CODPROYECTO "
                    ") presu ON presu.CODPROYECTO = pr.CODIGO "
                    "WHERE (fact.FACTURADO IS NOT NULL OR presu.PRESUPUESTO IS NOT NULL) "
                    "ORDER BY PORC_EJECUCION DESC NULLS LAST"
                )
            })
            # PROY-5: Cliente/variante del proyecto (NIF + razón social)
            fixed.append({
                "objetivo": "Cliente y NIF por proyecto (PROYVAR)",
                "sql": (
                    "SELECT FIRST 30 pv.CODPROYECTO, p.NOMBRE AS OBRA, "
                    "pv.RAZONSOCIAL AS CLIENTE, pv.TIPOIDFISCAL "
                    "FROM PROYVAR pv "
                    "LEFT JOIN PROYECTOS p ON p.CODIGO = pv.CODPROYECTO "
                    "ORDER BY pv.CODPROYECTO"
                )
            })

        # ── SQLs FIJOS para ARTÍCULOS más vendidos / comprados / rotación ────────
        # Se activan cuando la pregunta menciona artículos/productos y cualquier
        # indicador de movimiento/volumen (compras, ventas, rotación, negociación...).
        # Usan sintaxis Firebird estándar — el query_translator los convierte
        # automáticamente a SQLite cuando el simulador está activo.
        #
        # ESQUEMA SIMULADOR (schema.py):
        #   DOCLIN: CODDOCUMENTO (FK→DOCCAB.CODIGO), CODIGO (línea), CODARTICULO (FK→ARTICULO.CODIGO)
        #           CANTIDAD, PRECIO, COSTE, DESCUENTOS, TIPOIVA
        #   NOTA: No existe DOCLIN.CODART ni DOCLIN.IMPORTE en el simulador.
        #         IMPORTE = ROUND(CAST(CANTIDAD AS REAL)*CAST(PRECIO AS REAL),2)
        #         JOIN DOCCAB: ON c.CODIGO = d.CODDOCUMENTO (no d.CODIGO)
        art_kw = ["artículo", "articulo", "producto", "item", "referencia", "referencias"]
        comp_kw = [
            "compra", "venta", "vendido", "vendidos", "comprado", "comprados",
            "top", "más", "mas", "compras", "ventas",
            # Rotación y negociación de volumen
            "rotación", "rotacion", "rotan", "rota",
            "negociar", "negociación", "negociacion", "volumen",
            "candidatos", "candidato",
            "frecuencia", "frecuente", "frecuentes",
            "mayor", "mayores", "mejor", "mejores",
            "demanda", "popular", "populares",
        ]
        is_article_question = any(k in msg for k in art_kw) and any(k in msg for k in comp_kw)
        if is_article_question:
            fixed.append({
                "objetivo": "Top artículos por líneas de venta (frecuencia de compra)",
                "sql": (
                    "SELECT FIRST 10 a.NOMBRE, COUNT(d.CODIGO) AS N_LINEAS, "
                    "CAST(SUM(d.CANTIDAD) AS NUMERIC(15,2)) AS CANTIDAD_TOTAL, "
                    "CAST(SUM(CAST(d.CANTIDAD AS REAL)*CAST(d.PRECIO AS REAL)) AS NUMERIC(15,2)) AS IMPORTE_TOTAL "
                    "FROM ARTICULO a "
                    "JOIN DOCLIN d ON d.CODARTICULO = a.CODIGO "
                    "JOIN DOCCAB c ON c.CODIGO = d.CODDOCUMENTO AND c.TIPO = 13 "
                    "GROUP BY a.CODIGO, a.NOMBRE "
                    "ORDER BY N_LINEAS DESC"
                )
            })
            fixed.append({
                "objetivo": "Top artículos por importe total de ventas",
                "sql": (
                    "SELECT FIRST 10 a.NOMBRE, "
                    "CAST(SUM(CAST(d.CANTIDAD AS REAL)*CAST(d.PRECIO AS REAL)) AS NUMERIC(15,2)) AS IMPORTE_TOTAL, "
                    "COUNT(d.CODIGO) AS N_LINEAS "
                    "FROM ARTICULO a "
                    "JOIN DOCLIN d ON d.CODARTICULO = a.CODIGO "
                    "JOIN DOCCAB c ON c.CODIGO = d.CODDOCUMENTO AND c.TIPO = 13 "
                    "GROUP BY a.CODIGO, a.NOMBRE "
                    "ORDER BY IMPORTE_TOTAL DESC"
                )
            })
            fixed.append({
                "objetivo": "Top artículos por cantidad vendida (unidades)",
                "sql": (
                    "SELECT FIRST 10 a.NOMBRE, "
                    "CAST(SUM(d.CANTIDAD) AS NUMERIC(15,2)) AS CANTIDAD_TOTAL, "
                    "COUNT(d.CODIGO) AS N_PEDIDOS "
                    "FROM ARTICULO a "
                    "JOIN DOCLIN d ON d.CODARTICULO = a.CODIGO "
                    "GROUP BY a.CODIGO, a.NOMBRE "
                    "ORDER BY CANTIDAD_TOTAL DESC"
                )
            })

        return fixed

    def _build_resolution_sqls(
        self, issues: List, question: str, anio_actual: int
    ) -> List[Dict]:
        """
        SQLs deterministas para RESOLVER (no solo reportar) las inconsistencias más comunes.
        """
        sqls = []
        issues_text = " ".join(str(i).lower() for i in issues)
        msg = question.lower()

        # Año futurista / datos de año actual
        if any(k in issues_text for k in ["futurista", "futuro", "año", "fecha", str(anio_actual)]):
            sqls.append({
                "objetivo": f"Datos REALES (años <= {anio_actual}, excluyendo futuros)",
                "sql": (
                    f"SELECT EXTRACT(YEAR FROM FECHA) AS ANO, SERIE, COUNT(*) AS N, "
                    f"CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                    f"FROM DOCCAB WHERE FECHA IS NOT NULL "
                    f"AND EXTRACT(YEAR FROM FECHA) <= {anio_actual} "
                    f"AND EXTRACT(YEAR FROM FECHA) >= {anio_actual - 10} "
                    f"GROUP BY EXTRACT(YEAR FROM FECHA), SERIE ORDER BY ANO DESC, N DESC"
                )
            })
            sqls.append({
                "objetivo": f"Cuántos registros tienen fecha futura (> {anio_actual})",
                "sql": (
                    f"SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N_REGISTROS "
                    f"FROM DOCCAB WHERE FECHA IS NOT NULL "
                    f"AND EXTRACT(YEAR FROM FECHA) > {anio_actual} "
                    f"GROUP BY EXTRACT(YEAR FROM FECHA) ORDER BY ANO"
                )
            })

        # Tipo de documento incorrecto para SAT/garantía
        if any(k in issues_text for k in ["tipo", "sat", "garantía", "garantia", "servicio técnico"]):
            sqls.append({
                "objetivo": "Identificar TIPO correcto para SAT/garantía",
                "sql": (
                    "SELECT TIPO, SERIE, COUNT(*) AS N, "
                    "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                    "FROM DOCCAB WHERE UPPER(SERIE) LIKE UPPER('%SAT%') "
                    "OR UPPER(SERIE) LIKE UPPER('%GAR%') OR UPPER(SERIE) LIKE UPPER('%TEC%') "
                    "GROUP BY TIPO, SERIE ORDER BY N DESC"
                )
            })

        # Importe anómalo / mezcla de tipos
        if any(k in issues_text for k in ["importe", "millones", "alto", "anómalo", "mezcla"]):
            sqls.append({
                "objetivo": "Desglose por TIPO para identificar mezcla de documentos",
                "sql": (
                    "SELECT TIPO, COUNT(*) AS N, "
                    "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
                    "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
                    "FROM DOCCAB WHERE FECHA IS NOT NULL GROUP BY TIPO ORDER BY TOTAL_EUR DESC"
                )
            })

        # Contenido mixto / datos en columnas incorrectas
        if any(k in issues_text for k in ["mixto", "columna", "estructura", "heterogéneo"]):
            sqls.append({
                "objetivo": "Muestra de DESCRIPCION en ARTICULO para detectar contenido mixto",
                "sql": (
                    "SELECT FIRST 20 CODIGO, DESCRIPCION, NOMBRE FROM ARTICULO "
                    "WHERE DESCRIPCION IS NOT NULL ORDER BY CODIGO"
                )
            })

        # Tiempo/horas en SAT
        if any(k in msg for k in ["tiempo", "horas", "dedicar", "garantía", "garantia"]):
            sqls.append({
                "objetivo": "Columnas de tiempo/horas en DOCCAB (metadatos BD)",
                "sql": (
                    "SELECT FIRST 20 TRIM(RDB$FIELD_NAME) AS CAMPO FROM RDB$RELATION_FIELDS "
                    "WHERE RDB$RELATION_NAME = 'DOCCAB' "
                    "AND (UPPER(RDB$FIELD_NAME) LIKE '%HORA%' "
                    "OR UPPER(RDB$FIELD_NAME) LIKE '%TIEMPO%' "
                    "OR UPPER(RDB$FIELD_NAME) LIKE '%DURACION%') "
                    "ORDER BY RDB$FIELD_POSITION"
                )
            })

        return sqls
