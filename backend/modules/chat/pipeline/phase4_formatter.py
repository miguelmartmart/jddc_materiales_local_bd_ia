"""
phase4_formatter.py — Fase 4 del pipeline de chat: Formateador de Respuesta.

RESPONSABILIDADES:
  1. Interpretar el formato deseado de la respuesta (tabla, lista, texto, JSON...)
  2. Aplicar formato determinista cuando es posible (sin IA)
  3. Usar IA para formateo semántico complejo cuando sea necesario
  4. Añadir metadatos de presentación (unidades, moneda, porcentajes...)

ARQUITECTURA (dos fases independientes):
  Fase 1 — Determinista (instantánea, sin IA):
    - Detecta el tipo de datos del resultado SQL
    - Aplica formato de tabla Markdown para resultados tabulares
    - Formatea números (moneda, porcentajes, unidades)
    - Detecta si el resultado es un KPI único (número grande)

  Fase 2 — IA (solo si use_ai=True y el resultado es complejo):
    - Genera narrativa explicativa del resultado
    - Interpreta tendencias y patrones
    - Añade contexto de negocio
    - Timeout configurable (default 8s)

PRINCIPIOS DEVIA:
  - Módulo independiente (sin imports de otros módulos del pipeline)
  - < 500 líneas
  - Parámetros centralizados en constantes al inicio del fichero
  - Fallback determinista si la IA falla
  - Logging detallado
  - Activable/desactivable desde pipeline_config.py
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES CENTRALIZADAS (única fuente de verdad)
# ─────────────────────────────────────────────────────────────────────────────

# Columnas que representan importes monetarios (para formatear con €)
_MONEY_COLUMNS: frozenset = frozenset({
    "IMPORTETOTAL", "IMPORTEBASE", "IMPORTEIVA", "IMPORTEBRUTO",
    "IMPORTEDESCUENTO", "IMPORTEENTREGADO", "IMPORTEIRPF", "IMPORTERECEQUIV",
    "TOTAL", "TOTAL_EUR", "FACTURACION_TOTAL", "TICKET_MEDIO", "MEDIA_EUR",
    "MINIMO", "MAXIMO", "SUMA_TOTAL", "IMPORTE", "PRECIO", "PRECIOVENTA",
    "PRECIOCOSTE", "VALOR", "MARGEN", "COSTE_TOTAL_SAT", "TOTAL_PENDIENTE",
    "IMPORTE_PENDIENTE", "IMPORTE_PERDIDO", "TOTAL_VENTAS", "TOTAL_IMP",
    "TOTAL_PRIMER_MES", "TOTAL_VENDIDO", "IMPORTE_VENTAS", "IMPORTE_SAT",
    "IMPORTE_ALBARAN", "IMPORTE_PRESUPUESTO", "IMPORTE_PEDIDO",
    "SALDO_CAJA", "SALDO", "TOTAL_ABONOS", "TOTAL_FINAL", "TOTAL_BASE",
    "TOTAL_IVA", "DIFERENCIA", "MEDIA", "PROMEDIO",
})

# Columnas que representan porcentajes
_PCT_COLUMNS: frozenset = frozenset({
    "PCT", "PCT_TOTAL", "PCT_TOP5", "PCT_SAT", "PCT_ABONOS",
    "TASA_CONVERSION_PCT", "TASA_EXITO", "PORCENTAJE",
    "PCT_FACTURA", "PCT_PRESUPUESTO",
})

# Columnas que representan conteos (sin unidades especiales)
_COUNT_COLUMNS: frozenset = frozenset({
    "N", "N_FACTURAS", "N_DOCS", "N_CLIENTES", "N_ALBARANES",
    "N_SATS", "N_PRESUPUESTOS", "N_PEDIDOS", "N_LINEAS",
    "N_PRODUCTOS_DISTINTOS", "N_DOCUMENTOS", "N_AGENTES",
    "N_SATS_PENDIENTES", "N_CADUCADOS", "N_ABONOS",
    "TOTAL_FILAS", "COUNT", "NCOMPRAS",
})

# Columnas de fecha (para formatear como fecha)
_DATE_COLUMNS: frozenset = frozenset({
    "FECHA", "FECHAEMISION", "FECHAASIENTO", "FECHAOPERACION",
    "ULTIMA_COMPRA", "PRIMERA_COMPRA",
})

# Número máximo de filas para mostrar en tabla sin paginación
_MAX_TABLE_ROWS: int = 50

# Número de decimales para importes monetarios
_MONEY_DECIMALS: int = 2

# Símbolo de moneda
_CURRENCY_SYMBOL: str = "€"

# Umbral para considerar un resultado como "KPI único" (1 fila, 1-3 columnas)
_KPI_MAX_COLS: int = 3
_KPI_MAX_ROWS: int = 1


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS Y DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

class ResultType(Enum):
    """Tipo de resultado SQL detectado."""
    EMPTY       = "empty"       # Sin filas
    KPI_SINGLE  = "kpi_single"  # 1 fila, 1-3 columnas (KPI principal)
    TABLE       = "table"       # Tabla de datos (múltiples filas/columnas)
    LIST        = "list"        # Lista de valores (1 columna, múltiples filas)
    ERROR       = "error"       # Error en la consulta


@dataclass
class FormattedResult:
    """Resultado formateado listo para mostrar al usuario."""
    result_type: ResultType
    markdown: str                           # Texto Markdown formateado
    summary: str = ""                       # Resumen en una línea
    ai_narrative: str = ""                  # Narrativa generada por IA (si disponible)
    row_count: int = 0
    col_count: int = 0
    has_ai: bool = False                    # Si se usó IA para el formateo
    warnings: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# FASE 1: FORMATEO DETERMINISTA
# ─────────────────────────────────────────────────────────────────────────────

def _detect_result_type(rows: List[Dict[str, Any]]) -> ResultType:
    """Detecta el tipo de resultado SQL."""
    if not rows:
        return ResultType.EMPTY
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    if n_rows <= _KPI_MAX_ROWS and n_cols <= _KPI_MAX_COLS:
        return ResultType.KPI_SINGLE
    if n_cols == 1:
        return ResultType.LIST
    return ResultType.TABLE


def _format_value(col_name: str, value: Any) -> str:
    """
    Formatea un valor según el tipo de columna.
    Determinista: sin IA, sin dependencias externas.
    """
    if value is None:
        return "—"

    col_upper = col_name.upper()

    # Importes monetarios
    if col_upper in _MONEY_COLUMNS:
        try:
            v = float(value)
            return f"{v:,.{_MONEY_DECIMALS}f} {_CURRENCY_SYMBOL}"
        except (ValueError, TypeError):
            return str(value)

    # Porcentajes
    if col_upper in _PCT_COLUMNS:
        try:
            v = float(value)
            return f"{v:.1f}%"
        except (ValueError, TypeError):
            return str(value)

    # Conteos (enteros)
    if col_upper in _COUNT_COLUMNS:
        try:
            v = int(value)
            return f"{v:,}"
        except (ValueError, TypeError):
            return str(value)

    # Fechas (ya vienen como string YYYY-MM-DD)
    if col_upper in _DATE_COLUMNS and isinstance(value, str):
        # Convertir YYYY-MM-DD → DD/MM/YYYY
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', value)
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
        return value

    # Números genéricos con decimales
    if isinstance(value, float):
        return f"{value:,.2f}"

    # Enteros genéricos
    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


def _rows_to_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """
    Convierte una lista de dicts en tabla Markdown.
    Aplica formateo de valores según tipo de columna.
    """
    if not rows:
        return ""

    cols = list(rows[0].keys())
    # Cabecera
    header = "| " + " | ".join(cols) + " |"
    separator = "| " + " | ".join(["---"] * len(cols)) + " |"

    # Filas (limitadas a _MAX_TABLE_ROWS)
    data_rows = []
    for row in rows[:_MAX_TABLE_ROWS]:
        cells = [_format_value(col, row.get(col)) for col in cols]
        data_rows.append("| " + " | ".join(cells) + " |")

    lines = [header, separator] + data_rows
    if len(rows) > _MAX_TABLE_ROWS:
        lines.append(f"\n*... y {len(rows) - _MAX_TABLE_ROWS} filas más (mostrando primeras {_MAX_TABLE_ROWS})*")

    return "\n".join(lines)


def _format_kpi(rows: List[Dict[str, Any]]) -> str:
    """Formatea un resultado KPI (1 fila, pocas columnas) de forma destacada."""
    if not rows:
        return ""
    row = rows[0]
    parts = []
    for col, val in row.items():
        formatted = _format_value(col, val)
        parts.append(f"**{col}:** {formatted}")
    return "\n\n".join(parts)


def _format_list(rows: List[Dict[str, Any]]) -> str:
    """Formatea una lista de valores (1 columna) como lista Markdown."""
    if not rows:
        return ""
    col = list(rows[0].keys())[0]
    items = [f"- {_format_value(col, row[col])}" for row in rows[:_MAX_TABLE_ROWS]]
    if len(rows) > _MAX_TABLE_ROWS:
        items.append(f"- *... y {len(rows) - _MAX_TABLE_ROWS} más*")
    return "\n".join(items)


def format_deterministic(
    rows: List[Dict[str, Any]],
    query_title: str = "",
    error: Optional[str] = None,
) -> FormattedResult:
    """
    Formatea el resultado de una consulta SQL de forma determinista.

    Args:
        rows: Lista de dicts con los resultados SQL
        query_title: Título de la consulta (para el encabezado)
        error: Mensaje de error si la consulta falló

    Returns:
        FormattedResult con el Markdown formateado
    """
    if error:
        return FormattedResult(
            result_type=ResultType.ERROR,
            markdown=f"❌ **Error en la consulta:** {error}",
            summary=f"Error: {error[:80]}",
            row_count=0,
            col_count=0,
        )

    if not rows:
        return FormattedResult(
            result_type=ResultType.EMPTY,
            markdown="✅ *La consulta no devolvió resultados.*",
            summary="Sin resultados",
            row_count=0,
            col_count=0,
        )

    result_type = _detect_result_type(rows)
    n_rows = len(rows)
    n_cols = len(rows[0])

    # Encabezado
    title_md = f"### {query_title}\n\n" if query_title else ""

    if result_type == ResultType.KPI_SINGLE:
        body = _format_kpi(rows)
        summary = f"KPI: {n_cols} indicador(es)"
    elif result_type == ResultType.LIST:
        body = _format_list(rows)
        summary = f"Lista: {n_rows} elemento(s)"
    else:
        body = _rows_to_markdown_table(rows)
        summary = f"Tabla: {n_rows} fila(s) × {n_cols} columna(s)"

    markdown = title_md + body

    return FormattedResult(
        result_type=result_type,
        markdown=markdown,
        summary=summary,
        row_count=n_rows,
        col_count=n_cols,
    )


# ─────────────────────────────────────────────────────────────────────────────
# FASE 2: NARRATIVA IA
# ─────────────────────────────────────────────────────────────────────────────

async def generate_ai_narrative(
    rows: List[Dict[str, Any]],
    query_title: str,
    user_question: str,
    orchestrator,
    timeout_s: int = 8,
) -> Tuple[str, bool]:
    """
    Genera una narrativa explicativa del resultado usando IA.

    Solo se llama si use_ai=True y el resultado tiene datos.
    Fallback: devuelve ("", False) si la IA falla o hace timeout.

    Returns:
        (narrative_text, success)
    """
    if not rows:
        return "", False

    # Preparar resumen de datos para la IA (máximo 20 filas para no saturar el contexto)
    sample_rows = rows[:20]
    cols = list(rows[0].keys()) if rows else []
    data_summary = f"Columnas: {', '.join(cols)}\n"
    data_summary += f"Total filas: {len(rows)}\n"
    data_summary += "Primeras filas:\n"
    for i, row in enumerate(sample_rows[:5]):
        data_summary += f"  {i+1}. {dict(row)}\n"

    system = (
        "Eres un analista de negocio experto en ERP de climatización. "
        "Tu tarea es interpretar los resultados de una consulta SQL y generar "
        "una narrativa concisa y objetiva en español.\n\n"
        "REGLAS ESTRICTAS:\n"
        "- Máximo 3 párrafos cortos\n"
        "- Solo hechos observables en los datos, sin suposiciones\n"
        "- No uses frases subjetivas como 'esto es bueno/malo'\n"
        "- No hagas recomendaciones de negocio sin datos que las soporten\n"
        "- Si los datos muestran una tendencia, descríbela objetivamente\n"
        "- Usa números concretos del resultado\n"
        "- Responde SOLO con el texto de la narrativa, sin encabezados ni listas"
    )

    user_msg = (
        f"Pregunta del usuario: {user_question}\n\n"
        f"Consulta: {query_title}\n\n"
        f"Resultado:\n{data_summary}"
    )

    try:
        resp, _ = await asyncio.wait_for(
            orchestrator.execute_with_fallback(
                system_prompt=system,
                user_message=user_msg,
                preferred_model_id="jddcia-qwen3-30b",
            ),
            timeout=timeout_s,
        )
        if resp and resp.strip():
            logger.info(f"[FORMATTER] IA generó narrativa ({len(resp)} chars)")
            return resp.strip(), True
    except asyncio.TimeoutError:
        logger.warning(f"[FORMATTER] IA timeout ({timeout_s}s) — usando solo formato determinista")
    except Exception as e:
        logger.warning(f"[FORMATTER] IA error: {e} — usando solo formato determinista")

    return "", False


# ─────────────────────────────────────────────────────────────────────────────
# FORMATEADOR PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class ResponseFormatter:
    """
    Formateador de respuestas del pipeline de chat.

    Uso:
        formatter = ResponseFormatter(orchestrator=orchestrator, use_ai=True)
        result = await formatter.format(rows, query_title, user_question)
        return result.markdown
    """

    def __init__(
        self,
        orchestrator=None,
        use_ai: bool = True,
        ai_timeout_s: int = 8,
    ):
        self.orchestrator = orchestrator
        self.use_ai = use_ai and orchestrator is not None
        self.ai_timeout_s = ai_timeout_s

    async def format(
        self,
        rows: List[Dict[str, Any]],
        query_title: str = "",
        user_question: str = "",
        error: Optional[str] = None,
    ) -> FormattedResult:
        """
        Formatea el resultado de una consulta SQL.

        Proceso:
          1. Formateo determinista (siempre, instantáneo)
          2. Si use_ai=True y hay datos → narrativa IA
          3. Combina y devuelve FormattedResult final
        """
        # ── Fase 1: Determinista ──────────────────────────────────────────────
        result = format_deterministic(rows, query_title, error)

        if result.result_type in (ResultType.ERROR, ResultType.EMPTY):
            return result

        # ── Fase 2: Narrativa IA ──────────────────────────────────────────────
        if self.use_ai and rows:
            narrative, success = await generate_ai_narrative(
                rows=rows,
                query_title=query_title,
                user_question=user_question,
                orchestrator=self.orchestrator,
                timeout_s=self.ai_timeout_s,
            )
            if success and narrative:
                result.ai_narrative = narrative
                result.has_ai = True
                # Añadir narrativa al markdown
                result.markdown = (
                    f"{result.markdown}\n\n"
                    f"---\n"
                    f"**📊 Análisis:**\n\n{narrative}"
                )

        logger.debug(
            f"[FORMATTER] Resultado formateado: type={result.result_type.value} "
            f"rows={result.row_count} ai={result.has_ai}"
        )
        return result

    def format_sync(
        self,
        rows: List[Dict[str, Any]],
        query_title: str = "",
        error: Optional[str] = None,
    ) -> FormattedResult:
        """
        Versión síncrona del formateador (solo fase determinista).
        Útil cuando no hay event loop disponible.
        """
        return format_deterministic(rows, query_title, error)
