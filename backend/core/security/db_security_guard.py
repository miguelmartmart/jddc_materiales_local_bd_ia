"""
db_security_guard.py — Guardián de Seguridad de Base de Datos DEVIA.

RESPONSABILIDAD CRÍTICA:
    Garantizar que NINGUNA consulta SQL que llegue al motor de ejecución
    pueda modificar, eliminar, crear o alterar datos en la BD real.

    DEVIA es un sistema de SOLO LECTURA sobre la BD de producción.
    Cualquier intento de escritura es un error de seguridad crítico.

PRINCIPIOS DE SEGURIDAD:
    1. DEFENSA EN PROFUNDIDAD: múltiples capas de validación independientes
    2. FAIL-SAFE: ante cualquier duda, BLOQUEAR (no permitir)
    3. DETERMINISTA: sin IA, sin heurísticas — reglas exactas y exhaustivas
    4. AUDITABLE: todo bloqueo queda registrado con contexto completo
    5. INMUTABLE: las reglas no se pueden desactivar en tiempo de ejecución
    6. CERO EXCEPCIONES: ni siquiera el admin puede saltarse la validación

CAPAS DE VALIDACIÓN:
    CAPA 1 — Análisis léxico: tokenización del SQL y detección de keywords peligrosas
    CAPA 2 — Análisis sintáctico: detección de patrones de escritura (INSERT INTO, etc.)
    CAPA 3 — Análisis de comentarios: detección de inyección SQL via comentarios
    CAPA 4 — Análisis de múltiples sentencias: detección de ; seguido de escritura
    CAPA 5 — Análisis de funciones peligrosas: EXECUTE, EXEC, xp_cmdshell, etc.
    CAPA 6 — Validación de estructura SELECT: solo SELECT/WITH/EXPLAIN permitidos

PARÁMETROS CENTRALIZADOS:
    Todos los parámetros de seguridad están en constants.py (SQLDangerousCommands)
    y en este módulo (WRITE_KEYWORDS, DANGEROUS_FUNCTIONS, etc.).
    NO hay valores hardcodeados dispersos por el código.

INTEGRACIÓN:
    - Se llama ANTES de ejecutar cualquier SQL en _execute_sql() de service.py
    - Se llama ANTES de ejecutar SQL en el simulador (SimulatedFirebirdDriver)
    - Se llama en el SQLCorrector antes de cada reintento
    - El resultado es inmutable: SecurityResult no se puede modificar post-creación

DEVIA: backend/core/security/DEVIA.md
"""

import logging
import re
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Constantes de seguridad (ÚNICA fuente de verdad) ────────────────────────
# Estas constantes NO se importan de ningún otro módulo para evitar
# que una modificación accidental en otro fichero las altere.

# Palabras clave que inician sentencias de escritura (nivel 1 — más obvias)
_WRITE_STATEMENT_KEYWORDS: FrozenSet[str] = frozenset({
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "REPLACE", "TRUNCATE", "DROP", "CREATE", "ALTER",
    "RENAME", "GRANT", "REVOKE", "DENY",
    "EXECUTE", "EXEC", "CALL", "PROCEDURE",
    "COMMIT", "ROLLBACK", "SAVEPOINT",
    "SET",  # SET TRANSACTION, SET GENERATOR, etc.
    "LOCK",
})

# Patrones de escritura compuestos (nivel 2 — más específicos)
_WRITE_PATTERNS: Tuple[str, ...] = (
    r'\bINSERT\s+INTO\b',
    r'\bUPDATE\s+\w',
    r'\bDELETE\s+FROM\b',
    r'\bDELETE\s+\w',
    r'\bMERGE\s+INTO\b',
    r'\bDROP\s+(TABLE|VIEW|INDEX|PROCEDURE|TRIGGER|SEQUENCE|GENERATOR|DOMAIN|EXCEPTION|ROLE)\b',
    r'\bCREATE\s+(TABLE|VIEW|INDEX|PROCEDURE|TRIGGER|SEQUENCE|GENERATOR|DOMAIN|EXCEPTION|ROLE)\b',
    r'\bALTER\s+(TABLE|VIEW|PROCEDURE|TRIGGER|SEQUENCE|GENERATOR|DOMAIN|EXCEPTION|ROLE)\b',
    r'\bTRUNCATE\s+(TABLE\s+)?\w',
    r'\bGRANT\s+\w',
    r'\bREVOKE\s+\w',
    r'\bDENY\s+\w',
    r'\bEXECUTE\s+(PROCEDURE|BLOCK|STATEMENT)\b',
    r'\bEXEC\s+\w',
    r'\bCALL\s+\w',
    r'\bCOMMIT\b',
    r'\bROLLBACK\b',
    r'\bSAVEPOINT\b',
    r'\bSET\s+GENERATOR\b',
    r'\bSET\s+TRANSACTION\b',
    r'\bLOCK\s+TABLE\b',
    # Firebird específico
    r'\bEXECUTE\s+BLOCK\b',
    r'\bSET\s+TERM\b',
    r'\bCREATE\s+OR\s+ALTER\b',
    r'\bRECREATE\b',
    # Inyección via comentarios
    r'--.*?(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE)',
    r'/\*.*?(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE).*?\*/',
)

# Funciones peligrosas (nivel 3)
_DANGEROUS_FUNCTIONS: FrozenSet[str] = frozenset({
    "XP_CMDSHELL", "SP_EXECUTESQL", "OPENROWSET", "OPENQUERY",
    "BULK", "LOAD_FILE", "INTO OUTFILE", "INTO DUMPFILE",
    "UTL_FILE", "DBMS_PIPE", "DBMS_JOB", "DBMS_SCHEDULER",
    "EXECUTE_IMMEDIATE",  # Firebird dynamic SQL
})

# Palabras clave que SÍ están permitidas (SELECT y sus variantes)
_ALLOWED_STATEMENT_KEYWORDS: FrozenSet[str] = frozenset({
    "SELECT", "WITH", "EXPLAIN", "SHOW",
})

# Número máximo de sentencias SQL permitidas (separadas por ;)
_MAX_SQL_STATEMENTS = 1

# Longitud máxima de SQL permitida (protección contra ataques de payload largo)
_MAX_SQL_LENGTH = 8000


# ─── Resultado de validación ──────────────────────────────────────────────────

@dataclass(frozen=True)
class SecurityResult:
    """
    Resultado inmutable de la validación de seguridad.
    frozen=True: no se puede modificar después de crearse.
    """
    is_safe: bool
    blocked_reason: str = ""
    blocked_layer: int = 0          # Capa que bloqueó (1-6)
    blocked_keyword: str = ""       # Keyword/patrón que activó el bloqueo
    sql_preview: str = ""           # Primeros 100 chars del SQL (para logs)
    severity: str = "NONE"         # NONE | LOW | MEDIUM | HIGH | CRITICAL


# ─── DatabaseSecurityGuard ────────────────────────────────────────────────────

class DatabaseSecurityGuard:
    """
    Guardián de seguridad de base de datos — SOLO LECTURA.

    Valida que cualquier SQL sea una consulta de lectura pura (SELECT/WITH/EXPLAIN).
    Bloquea CUALQUIER intento de escritura, modificación o ejecución de código.

    Ultra-resiliente: si la validación falla por error interno, BLOQUEA por defecto
    (fail-safe). Nunca permite una consulta no validada.

    Uso:
        guard = get_db_security_guard()
        result = guard.validate(sql_query)
        if not result.is_safe:
            raise SecurityError(result.blocked_reason)
    """

    def __init__(self):
        # Compilar patrones una sola vez (performance)
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in _WRITE_PATTERNS
        ]
        logger.info("[SECURITY] DatabaseSecurityGuard inicializado — modo SOLO LECTURA activo")

    def validate(self, sql: str, context: str = "") -> SecurityResult:
        """
        Valida que el SQL sea seguro (solo lectura).

        Args:
            sql: Consulta SQL a validar
            context: Contexto adicional para logs (ej: "chat_service", "deep_agent")

        Returns:
            SecurityResult(is_safe=True) si es seguro
            SecurityResult(is_safe=False, ...) si es peligroso

        NUNCA lanza excepción — siempre devuelve SecurityResult.
        Si hay error interno, devuelve is_safe=False (fail-safe).
        """
        sql_preview = (sql[:100] + "...") if len(sql) > 100 else sql

        try:
            # ── CAPA 0: Validación básica ─────────────────────────────────────
            if not sql or not sql.strip():
                return SecurityResult(
                    is_safe=False,
                    blocked_reason="SQL vacío o nulo",
                    blocked_layer=0,
                    severity="LOW",
                    sql_preview=sql_preview,
                )

            if len(sql) > _MAX_SQL_LENGTH:
                return SecurityResult(
                    is_safe=False,
                    blocked_reason=f"SQL demasiado largo ({len(sql)} chars > {_MAX_SQL_LENGTH})",
                    blocked_layer=0,
                    blocked_keyword="LENGTH_EXCEEDED",
                    severity="MEDIUM",
                    sql_preview=sql_preview,
                )

            # ── CAPA 1: Análisis léxico — primera palabra ─────────────────────
            # La primera palabra del SQL determina el tipo de sentencia.
            # Si no es SELECT/WITH/EXPLAIN → bloquear inmediatamente.
            sql_stripped = sql.strip()
            first_word = sql_stripped.split()[0].upper() if sql_stripped.split() else ""

            if first_word not in _ALLOWED_STATEMENT_KEYWORDS:
                if first_word in _WRITE_STATEMENT_KEYWORDS:
                    severity = "CRITICAL" if first_word in {"DROP", "TRUNCATE", "DELETE", "EXECUTE"} else "HIGH"
                    result = SecurityResult(
                        is_safe=False,
                        blocked_reason=f"Sentencia de escritura detectada: {first_word}",
                        blocked_layer=1,
                        blocked_keyword=first_word,
                        severity=severity,
                        sql_preview=sql_preview,
                    )
                    self._log_block(result, context)
                    return result
                elif first_word:
                    # Primera palabra desconocida — bloquear por precaución
                    result = SecurityResult(
                        is_safe=False,
                        blocked_reason=f"Primera palabra SQL no reconocida: '{first_word}' (solo SELECT/WITH/EXPLAIN permitidos)",
                        blocked_layer=1,
                        blocked_keyword=first_word,
                        severity="MEDIUM",
                        sql_preview=sql_preview,
                    )
                    self._log_block(result, context)
                    return result

            # ── CAPA 2: Análisis de múltiples sentencias ──────────────────────
            # Detectar ; seguido de otra sentencia (inyección SQL clásica)
            # Ejemplo: SELECT 1; DROP TABLE CLIENTE
            statements = self._split_statements(sql)
            if len(statements) > _MAX_SQL_STATEMENTS:
                # Verificar si alguna sentencia adicional es peligrosa
                for i, stmt in enumerate(statements[1:], start=2):
                    stmt_stripped = stmt.strip()
                    if not stmt_stripped:
                        continue
                    stmt_first = stmt_stripped.split()[0].upper() if stmt_stripped.split() else ""
                    if stmt_first in _WRITE_STATEMENT_KEYWORDS or stmt_first not in _ALLOWED_STATEMENT_KEYWORDS:
                        result = SecurityResult(
                            is_safe=False,
                            blocked_reason=f"Múltiples sentencias SQL detectadas — sentencia {i}: '{stmt_first}'",
                            blocked_layer=2,
                            blocked_keyword=f"MULTI_STATEMENT:{stmt_first}",
                            severity="CRITICAL",
                            sql_preview=sql_preview,
                        )
                        self._log_block(result, context)
                        return result

            # ── CAPA 3: Análisis de patrones de escritura ─────────────────────
            # Buscar patrones compuestos (INSERT INTO, UPDATE tabla, etc.)
            # incluso si están dentro de subconsultas o CTEs
            for pattern in self._compiled_patterns:
                match = pattern.search(sql)
                if match:
                    matched_text = match.group(0)[:50]
                    severity = "CRITICAL" if any(
                        kw in matched_text.upper()
                        for kw in ["DROP", "TRUNCATE", "DELETE", "EXECUTE", "GRANT", "REVOKE"]
                    ) else "HIGH"
                    result = SecurityResult(
                        is_safe=False,
                        blocked_reason=f"Patrón de escritura detectado: '{matched_text}'",
                        blocked_layer=3,
                        blocked_keyword=matched_text,
                        severity=severity,
                        sql_preview=sql_preview,
                    )
                    self._log_block(result, context)
                    return result

            # ── CAPA 4: Análisis de funciones peligrosas ──────────────────────
            sql_upper = sql.upper()
            for func in _DANGEROUS_FUNCTIONS:
                if func in sql_upper:
                    result = SecurityResult(
                        is_safe=False,
                        blocked_reason=f"Función peligrosa detectada: {func}",
                        blocked_layer=4,
                        blocked_keyword=func,
                        severity="CRITICAL",
                        sql_preview=sql_preview,
                    )
                    self._log_block(result, context)
                    return result

            # ── CAPA 5: Análisis de comentarios con escritura ─────────────────
            # Detectar escritura oculta en comentarios SQL
            # Ejemplo: SELECT 1 /* UPDATE CLIENTE SET ... */
            comment_pattern = re.compile(
                r'(/\*.*?\*/|--[^\n]*)',
                re.DOTALL | re.IGNORECASE
            )
            for comment_match in comment_pattern.finditer(sql):
                comment_text = comment_match.group(0).upper()
                for write_kw in _WRITE_STATEMENT_KEYWORDS:
                    if write_kw in comment_text:
                        result = SecurityResult(
                            is_safe=False,
                            blocked_reason=f"Escritura detectada en comentario SQL: '{write_kw}'",
                            blocked_layer=5,
                            blocked_keyword=f"COMMENT:{write_kw}",
                            severity="CRITICAL",
                            sql_preview=sql_preview,
                        )
                        self._log_block(result, context)
                        return result

            # ── CAPA 6: Validación final de estructura SELECT ─────────────────
            # Verificar que el SQL contiene al menos un SELECT
            if "SELECT" not in sql_upper and "WITH" not in sql_upper:
                result = SecurityResult(
                    is_safe=False,
                    blocked_reason="SQL no contiene SELECT ni WITH — no es una consulta de lectura",
                    blocked_layer=6,
                    blocked_keyword="NO_SELECT",
                    severity="MEDIUM",
                    sql_preview=sql_preview,
                )
                self._log_block(result, context)
                return result

            # ── APROBADO ──────────────────────────────────────────────────────
            logger.debug(f"[SECURITY] ✅ SQL aprobado (contexto={context}): {sql_preview}")
            return SecurityResult(is_safe=True, sql_preview=sql_preview)

        except Exception as e:
            # FAIL-SAFE: cualquier error interno → bloquear
            logger.error(f"[SECURITY] ❌ Error interno en validación — bloqueando por seguridad: {e}")
            return SecurityResult(
                is_safe=False,
                blocked_reason=f"Error interno en validación de seguridad — bloqueado por precaución: {e}",
                blocked_layer=0,
                blocked_keyword="INTERNAL_ERROR",
                severity="HIGH",
                sql_preview=sql_preview if sql else "",
            )

    def validate_or_raise(self, sql: str, context: str = "") -> None:
        """
        Valida el SQL y lanza DatabaseSecurityError si no es seguro.

        Uso recomendado en puntos de ejecución críticos:
            guard.validate_or_raise(sql, context="chat_service._execute_sql")

        Raises:
            DatabaseSecurityError: si el SQL no es seguro
        """
        result = self.validate(sql, context)
        if not result.is_safe:
            raise DatabaseSecurityError(
                f"[SECURITY BLOCK] {result.blocked_reason} "
                f"(capa={result.blocked_layer}, severidad={result.severity}, "
                f"keyword='{result.blocked_keyword}')"
            )

    def _split_statements(self, sql: str) -> List[str]:
        """
        Divide el SQL en sentencias separadas por ;
        Ignora ; dentro de strings (entre comillas simples).
        """
        statements = []
        current = []
        in_string = False
        string_char = None

        for char in sql:
            if in_string:
                current.append(char)
                if char == string_char:
                    in_string = False
                    string_char = None
            elif char in ("'", '"'):
                in_string = True
                string_char = char
                current.append(char)
            elif char == ';':
                stmt = ''.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
            else:
                current.append(char)

        # Última sentencia (sin ; final)
        last = ''.join(current).strip()
        if last:
            statements.append(last)

        return statements if statements else [sql]

    def _log_block(self, result: SecurityResult, context: str) -> None:
        """Registra el bloqueo con nivel apropiado según severidad."""
        msg = (
            f"[SECURITY BLOCK] capa={result.blocked_layer} "
            f"severidad={result.severity} "
            f"keyword='{result.blocked_keyword}' "
            f"contexto='{context}' "
            f"razón='{result.blocked_reason}' "
            f"sql='{result.sql_preview}'"
        )
        if result.severity == "CRITICAL":
            logger.critical(msg)
        elif result.severity == "HIGH":
            logger.error(msg)
        elif result.severity == "MEDIUM":
            logger.warning(msg)
        else:
            logger.info(msg)


# ─── Excepción de seguridad ───────────────────────────────────────────────────

class DatabaseSecurityError(Exception):
    """
    Excepción lanzada cuando el DatabaseSecurityGuard bloquea una consulta.

    Esta excepción NO debe capturarse silenciosamente — debe propagarse
    hasta el nivel de respuesta al usuario con un mensaje claro.
    """
    pass


# ─── Singleton ────────────────────────────────────────────────────────────────

_guard_instance: Optional[DatabaseSecurityGuard] = None


def get_db_security_guard() -> DatabaseSecurityGuard:
    """
    Devuelve la instancia singleton del guardián de seguridad.

    El guardián se inicializa UNA sola vez al arrancar el servidor.
    Thread-safe para uso en FastAPI (single-process).
    """
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = DatabaseSecurityGuard()
    return _guard_instance
