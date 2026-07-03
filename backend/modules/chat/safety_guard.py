"""
safety_guard.py — Módulo de seguridad del pipeline de chat.

RESPONSABILIDADES:
  1. Protección de la base de datos: detecta peticiones que podrían
     modificar, borrar o corromper datos (DROP, DELETE, UPDATE, INSERT...).
  2. Filtro ético/legal: detecta peticiones ilegales, antiéticas,
     discriminatorias o que violen la privacidad.
  3. Filtro de privacidad: detecta peticiones que expongan datos personales
     sensibles de forma inapropiada.

ARQUITECTURA (DEVIA):
  - Fase 1 (determinista, instantánea): patrones regex hardcoded → bloqueo inmediato
  - Fase 2 (IA, solo si fase 1 no bloquea): clasificación semántica para casos ambiguos
  - Resultado: SafetyResult con allow/block + razón + nivel de riesgo

PRINCIPIOS DEVIA:
  - Módulo independiente, sin dependencias circulares
  - < 500 líneas
  - Parámetros centralizados en constantes
  - Fallback determinista si la IA falla
  - Logging detallado para auditoría
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES CENTRALIZADAS
# ─────────────────────────────────────────────────────────────────────────────

class RiskLevel(Enum):
    """Nivel de riesgo de una petición."""
    SAFE = "safe"           # Sin riesgo detectado
    LOW = "low"             # Riesgo bajo (advertencia)
    MEDIUM = "medium"       # Riesgo medio (requiere confirmación)
    HIGH = "high"           # Riesgo alto (bloqueado)
    CRITICAL = "critical"   # Riesgo crítico (bloqueado inmediatamente)


class BlockReason(Enum):
    """Razón de bloqueo de una petición."""
    DB_DESTRUCTIVE = "db_destructive"       # Operación destructiva en BD
    DB_SCHEMA_MODIFY = "db_schema_modify"   # Modificación de esquema
    DB_PRIVILEGE_ESCALATION = "db_priv"     # Escalada de privilegios
    ILLEGAL_CONTENT = "illegal"             # Contenido ilegal
    UNETHICAL = "unethical"                 # Contenido antiético
    PRIVACY_VIOLATION = "privacy"           # Violación de privacidad
    PROMPT_INJECTION = "injection"          # Intento de inyección de prompt
    NONE = "none"                           # Sin bloqueo


# ── Patrones SQL destructivos (fase determinista) ─────────────────────────────
# Cualquier SQL que contenga estas palabras clave es bloqueado inmediatamente.
_SQL_DESTRUCTIVE_PATTERNS = [
    r'\bDROP\s+(TABLE|DATABASE|INDEX|VIEW|TRIGGER|PROCEDURE|FUNCTION)\b',
    r'\bDELETE\s+FROM\b',
    r'\bTRUNCATE\s+(TABLE\s+)?\w+',
    r'\bUPDATE\s+\w+\s+SET\b',
    r'\bINSERT\s+INTO\b',
    r'\bALTER\s+(TABLE|DATABASE|INDEX)\b',
    r'\bCREATE\s+(TABLE|DATABASE|INDEX|VIEW|TRIGGER|PROCEDURE|FUNCTION)\b',
    r'\bGRANT\s+\w+\s+ON\b',
    r'\bREVOKE\s+\w+\s+ON\b',
    r'\bEXEC(UTE)?\s+\w+',
    r'\bSP_\w+',                            # Stored procedures del sistema
    r'\bXP_\w+',                            # Extended procedures
    r'\bSHUTDOWN\b',
    r'\bFORMAT\s+\w+',
]

# ── Patrones de inyección de prompt ──────────────────────────────────────────
_PROMPT_INJECTION_PATTERNS = [
    r'ignora\s+(todas?\s+)?(las?\s+)