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

        # SQL FIJO 1: Distribución temporal (SIEMPRE para DOCCAB)
        if "DOCCAB" in phase2_data:
            if has_serie:
                fixed.append({
                    "objetivo": "Distribución por año y serie",
                    "sql": (
                        "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, SERIE, COUNT(*) AS N, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                        "FROM DOCCAB WHERE TIPO = 0 AND FECHA IS NOT NULL "
                        "GROUP BY EXTRACT(YEAR FROM FECHA), SERIE "
                        "ORDER BY ANO DESC, N DESC"
                    )
                })
            else:
                fixed.append({
                    "objetivo": "Distribución por año",
                    "sql": (
                        "SELECT EXTRACT(YEAR FROM FECHA) AS ANO, COUNT(*) AS N, "
                        "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                        "FROM DOCCAB WHERE TIPO = 0 AND FECHA IS NOT NULL "
                        "GROUP BY EXTRACT(YEAR FROM FECHA) ORDER BY ANO DESC"
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
