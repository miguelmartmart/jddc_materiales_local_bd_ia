# DEVIA — backend/core/security

## Responsabilidad
Módulo de seguridad de base de datos. Garantiza que NINGUNA consulta SQL
pueda modificar, eliminar, crear o alterar datos en la BD real de producción.

## Principios DEVIA aplicados
- **SOLO LECTURA**: DEVIA es un sistema de consulta, nunca de escritura
- **FAIL-SAFE**: ante cualquier duda, BLOQUEAR (no permitir)
- **DEFENSA EN PROFUNDIDAD**: 6 capas de validación independientes
- **DETERMINISTA**: sin IA, sin heurísticas — reglas exactas y exhaustivas
- **AUDITABLE**: todo bloqueo queda registrado con contexto completo
- **INMUTABLE**: las reglas no se pueden desactivar en tiempo de ejecución
- **CERO EXCEPCIONES**: ni siquiera el admin puede saltarse la validación

## Ficheros

### `db_security_guard.py`
Guardián principal. Valida SQL antes de ejecutarlo.

**Capas de validación:**
1. Validación básica (vacío, longitud máxima 8000 chars)
2. Análisis léxico — primera palabra (SELECT/WITH/EXPLAIN únicos permitidos)
3. Análisis de múltiples sentencias (`;` seguido de escritura)
4. Análisis de patrones compuestos (INSERT INTO, UPDATE tabla, etc.)
5. Análisis de funciones peligrosas (XP_CMDSHELL, EXECUTE_IMMEDIATE, etc.)
6. Análisis de comentarios con escritura oculta (`/* UPDATE ... */`)
7. Validación final de estructura SELECT

**Uso:**
```python
from backend.core.security import get_db_security_guard, DatabaseSecurityError

guard = get_db_security_guard()
guard.validate_or_raise(sql, context="mi_modulo")  # lanza si no es seguro
```

### `__init__.py`
Exporta: `DatabaseSecurityGuard`, `DatabaseSecurityError`, `SecurityResult`, `get_db_security_guard`

## Integración
- `backend/modules/chat/service.py` → `_execute_sql()` llama al guard ANTES de ejecutar
- `backend/modules/db_simulator/driver.py` → TODO: integrar también en el driver simulado
- `backend/modules/chat/sql_corrector.py` → TODO: integrar en cada reintento

## Parámetros centralizados
- `_WRITE_STATEMENT_KEYWORDS`: keywords de escritura (frozenset, inmutable)
- `_WRITE_PATTERNS`: patrones regex compilados una sola vez al arrancar
- `_DANGEROUS_FUNCTIONS`: funciones peligrosas (XP_CMDSHELL, etc.)
- `_ALLOWED_STATEMENT_KEYWORDS`: solo SELECT/WITH/EXPLAIN
- `_MAX_SQL_STATEMENTS`: máximo 1 sentencia por consulta
- `_MAX_SQL_LENGTH`: máximo 8000 chars

## Historial
- 2026-07-09: Creación inicial — 6 capas de validación, singleton, fail-safe
