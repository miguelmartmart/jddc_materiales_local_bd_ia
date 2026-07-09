"""
backend/core/security — Módulo de seguridad de base de datos DEVIA.

Exporta:
    - DatabaseSecurityGuard: validador de SQL de solo lectura (6 capas)
    - DatabaseSecurityError: excepción lanzada al bloquear SQL peligroso
    - SecurityResult: resultado inmutable de validación
    - get_db_security_guard(): singleton del guardián

DEVIA: backend/core/security/DEVIA.md
"""

from backend.core.security.db_security_guard import (
    DatabaseSecurityGuard,
    DatabaseSecurityError,
    SecurityResult,
    get_db_security_guard,
)

__all__ = [
    "DatabaseSecurityGuard",
    "DatabaseSecurityError",
    "SecurityResult",
    "get_db_security_guard",
]
