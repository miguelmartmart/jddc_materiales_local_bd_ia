"""
models.py — Dataclasses, Enums, TokenBudget y constantes del DeepAnalysisAgent.

Única fuente de verdad para:
  - AnalysisDepth (niveles de profundidad)
  - DEPTH_CONFIG (configuración por nivel)
  - TokenBudget (gestión exacta de presupuesto de tokens)
  - EpicAnalysisResult, PhaseResult, SubPhaseResult (estructuras de datos)
  - detect_depth() (auto-detección de profundidad)
  - Constantes globales (MAX_SQLS_ABSOLUTE, CHARS_PER_TOKEN, etc.)
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# ─── Constantes globales ──────────────────────────────────────────────────────

# Límite absoluto de SQLs (independientemente del nivel de profundidad)
MAX_SQLS_ABSOLUTE: int = 30

# Tokens reservados para la respuesta del modelo
TOKENS_RESERVED_FOR_RESPONSE: int = 4096

# Tokens por carácter (estimación conservadora: 1 token ≈ 3.5 chars)
CHARS_PER_TOKEN: float = 3.5

# Límite de contexto por defecto si no se puede detectar el modelo
DEFAULT_CONTEXT_LIMIT_TOKENS: int = 32000

# Umbral para activar resumen progresivo (% del presupuesto disponible)
SUMMARY_THRESHOLD: float = 0.75

# Máximo de filas por SQL en el resumen de investigación
MAX_ROWS_IN_SUMMARY: int = 5

# ─── PARÁMETROS DEL BUCLE DE INVESTIGACIÓN ITERATIVA ─────────────────────────
# Número máximo de ciclos del bucle de investigación.
# Cada ciclo ejecuta: Fase 3 (SQLs nuevos) → Fase 4 (análisis) → Fase 3b (resolución).
# La IA puede salir antes si considera que ya no hay más que investigar.
# Centralizado aquí para cumplir el principio de parámetros centralizados.
MAX_INVESTIGATION_CYCLES: int = 4

# Número mínimo de anomalías/inconsistencias para continuar el bucle.
# Si tras un ciclo hay menos de este número de issues sin resolver, el bucle termina.
MIN_ISSUES_TO_CONTINUE: int = 1

# Umbral de fiabilidad para salir del bucle antes del máximo de ciclos.
# Si la IA reporta fiabilidad "alto" y hay pocas anomalías, el bucle termina.
RELIABILITY_EXIT_THRESHOLD: str = "alto"

# Número máximo de SQLs adicionales por ciclo del bucle (para no saturar el contexto)
MAX_SQLS_PER_CYCLE: int = 6


# ─── Enums ────────────────────────────────────────────────────────────────────

class AnalysisDepth(Enum):
    BASIC  = "basic"   # 2 SQLs, respuesta rápida
    MEDIUM = "medium"  # 4 SQLs, análisis moderado
    DEEP   = "deep"    # 8 SQLs, análisis profundo
    EPIC   = "epic"    # 12+ SQLs, análisis épico (ampliable dinámicamente)


# ─── Configuración base por nivel ─────────────────────────────────────────────

DEPTH_CONFIG: Dict[AnalysisDepth, Dict] = {
    AnalysisDepth.BASIC:  {"max_sqls": 2,  "explore_tables": 2, "sub_phases": 2},
    AnalysisDepth.MEDIUM: {"max_sqls": 4,  "explore_tables": 4, "sub_phases": 4},
    AnalysisDepth.DEEP:   {"max_sqls": 8,  "explore_tables": 6, "sub_phases": 6},
    AnalysisDepth.EPIC:   {"max_sqls": 12, "explore_tables": 8, "sub_phases": 8},
}


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class SubPhaseResult:
    """Resultado de una subfase individual."""
    name: str
    success: bool
    data: Any = None
    error: Optional[str] = None


@dataclass
class PhaseResult:
    """Resultado de una fase principal con sus subfases."""
    phase_id: str
    phase_name: str
    success: bool
    sub_phases: List[SubPhaseResult] = field(default_factory=list)
    data: Any = None
    error: Optional[str] = None


@dataclass
class EpicAnalysisResult:
    """Resultado completo del análisis épico multi-fase."""
    question: str
    depth: AnalysisDepth = AnalysisDepth.EPIC
    phases: List[PhaseResult] = field(default_factory=list)
    final_answer: str = ""
    sql_queries: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    business_insights: List[str] = field(default_factory=list)
    data_quality_issues: List[str] = field(default_factory=list)
    # Rutas de ficheros temporales de resúmenes parciales volcados a disco
    partial_summary_files: List[str] = field(default_factory=list)
    # Ciclos del bucle de investigación ejecutados
    investigation_cycles: int = 0
    # True si la IA devolvió None en alguna fase crítica (servidor IA no disponible)
    ai_unavailable: bool = False


# ─── TokenBudget ──────────────────────────────────────────────────────────────

class TokenBudget:
    """
    Gestiona el presupuesto de tokens para cada llamada a la IA.

    Conteo exacto basado en caracteres (1 token ≈ 3.5 chars).
    Garantiza que ninguna llamada supere el límite de contexto del modelo.

    Uso:
        budget = TokenBudget(32000)
        budget.fits(system_prompt, user_message)   → bool
        budget.truncate_to_fit(data, system, user) → str truncado
        budget.usage_pct(data)                     → float 0.0-1.0
    """

    def __init__(self, context_limit_tokens: int = DEFAULT_CONTEXT_LIMIT_TOKENS):
        self.context_limit = context_limit_tokens
        self.available = context_limit_tokens - TOKENS_RESERVED_FOR_RESPONSE
        logger.info(
            f"[TOKEN BUDGET] Límite: {context_limit_tokens} tokens | "
            f"Disponible para contexto: {self.available} tokens"
        )

    def count(self, text: str) -> int:
        """Cuenta tokens de un texto (estimación conservadora)."""
        if not text:
            return 0
        return max(1, int(len(text) / CHARS_PER_TOKEN))

    def fits(self, *texts: str) -> bool:
        """Comprueba si todos los textos caben en el presupuesto disponible."""
        total = sum(self.count(t) for t in texts if t)
        return total <= self.available

    def remaining_chars(self, *reserved_texts: str) -> int:
        """Caracteres disponibles después de reservar los textos dados."""
        used_tokens = sum(self.count(t) for t in reserved_texts if t)
        remaining_tokens = max(0, self.available - used_tokens)
        return int(remaining_tokens * CHARS_PER_TOKEN)

    def truncate_to_fit(self, text: str, *reserved_texts: str) -> str:
        """Trunca text para que quepa junto con los textos reservados."""
        _SUFFIX = "\n...[TRUNCADO POR LÍMITE DE CONTEXTO]"
        max_chars = self.remaining_chars(*reserved_texts)
        if len(text) <= max_chars:
            return text
        # Dejar espacio para el sufijo de truncado
        effective_max = max(0, max_chars - len(_SUFFIX))
        truncated = text[:effective_max]
        logger.warning(
            f"[TOKEN BUDGET] Texto truncado: {len(text)} → {effective_max} chars "
            f"({self.count(text)} → {self.count(truncated)} tokens)"
        )
        return truncated + _SUFFIX

    def usage_pct(self, *texts: str) -> float:
        """Porcentaje de uso del presupuesto (0.0 = vacío, 1.0 = lleno)."""
        used = sum(self.count(t) for t in texts if t)
        return used / self.available if self.available > 0 else 1.0


# ─── Detección automática de profundidad ─────────────────────────────────────

def detect_depth(message: str) -> AnalysisDepth:
    """
    Detecta automáticamente el nivel de profundidad requerido.
    Por defecto EPIC — solo reduce si la pregunta es claramente simple.
    """
    msg = message.lower()

    epic_keywords = [
        "analiza", "análisis", "investiga", "profundidad", "detalle", "completo",
        "exhaustivo", "a fondo", "todo", "tasa", "éxito", "porcentaje", "tendencia",
        "comparativa", "evolución", "histórico", "por qué", "causa", "problema",
        "anomalía", "duplicado", "calidad", "fiabilidad", "perspectiva",
    ]
    if any(k in msg for k in epic_keywords):
        return AnalysisDepth.EPIC

    deep_keywords = [
        "cuántos", "cuánto", "total", "suma", "promedio", "media",
        "más", "menos", "mejor", "peor", "top", "ranking",
        "clientes", "agentes", "familias", "categorías",
    ]
    if any(k in msg for k in deep_keywords):
        return AnalysisDepth.DEEP

    medium_keywords = ["lista", "muestra", "dame", "ver", "mostrar"]
    if any(k in msg for k in medium_keywords):
        return AnalysisDepth.MEDIUM

    # EPIC por defecto — siempre máxima profundidad
    return AnalysisDepth.EPIC
