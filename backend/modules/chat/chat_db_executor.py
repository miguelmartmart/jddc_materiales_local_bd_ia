"""
chat_db_executor.py — Ejecucion de SQL contra Firebird con maxima resiliencia.

RESPONSABILIDAD:
  - Ejecutar consultas SQL contra Firebird con reintentos y backoff
  - Obtener el esquema de la BD para el contexto del chat
  - Gestionar la conexion de forma segura (siempre desconectar en finally)

RESILIENCIA:
  - 3 reintentos con backoff exponencial (0.5s, 1s, 1.5s)
  - Siempre desconecta en finally (nunca deja conexiones abiertas)
  - Fallback a configuracion del .env si no hay db_params en el contexto
  - Filtra parametros no-BD antes de crear DBConfig
  - Maneja todos los tipos de excepcion de Firebird
  - Logs detallados en cada paso para diagnostico

PRINCIPIOS:
  - Sin magic numbers: constantes en este fichero
  - Sin imports circulares
  - Una sola responsabilidad: acceso a BD
"""

import logging
import time
from typing import Dict, Any, List, Optional

from backend.core.factory.db_factory import DBFactory
from backend.core.abstract.database import DBConfig
from backend.core.utils.constants import DBConstants
from backend.drivers.db.firebird_queries import QUERY_TABLES, QUERY_TABLE_COLUMNS

logger = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────────────

MAX_DB_RETRIES      = 3      # Intentos maximos de conexion/ejecucion
RETRY_BASE_WAIT_S   = 0.5    # Espera base entre reintentos (segundos)
MAX_SCHEMA_TABLES   = 10     # Maximo de tablas con esquema detallado
SCHEMA_PRIORITY_TABLES = [   # Tablas prioritarias para el esquema
    'ARTICULO', 'CLIENTE', 'FACTURA', 'PROVEEDOR', 'PEDIDO',
    'DOCCAB', 'DOCLIN', 'ALMACEN', 'PROVEED'
]

# Parametros que NO son de BD y deben filtrarse antes de crear DBConfig
NON_DB_PARAMS = frozenset({
    'confirm_data_sending', 'model_id', 'conversation_history',
    'images', 'client_type', 'session_id'
})


def _build_db_config(db_params: Dict[str, Any]) -> DBConfig:
    """
    Construye un DBConfig filtrando parametros no-BD.
    Normaliza 'username' -> 'user' (compatibilidad con clientes antiguos).

    RESILIENCIA:
      - Filtra todos los parametros no reconocidos por DBConfig
      - Nunca lanza KeyError por parametros extra
    """
    config_params = {
        k: v for k, v in db_params.items()
        if k not in NON_DB_PARAMS
    }
    # Normalizar username -> user
    if 'username' in config_params:
        config_params['user'] = config_params.pop('username')
    return DBConfig(**config_params)


def _get_fallback_db_params() -> Dict[str, Any]:
    """
    Devuelve los parametros de BD desde el .env como fallback.
    Se usa cuando el cliente no envia db_params (ej: gafas Meta).

    RESILIENCIA:
      - Importa settings de forma lazy para evitar imports circulares
      - Si settings falla, devuelve dict vacio (el error se propagara despues)
    """
    try:
        from backend.core.config.settings import settings
        return {
            "host":     settings.DB_HOST,
            "port":     settings.DB_PORT,
            "database": settings.DB_NAME,
            "user":     settings.DB_USER,
            "password": settings.DB_PASSWORD,
        }
    except Exception as e:
        logger.error(f"[DBExecutor] No se pudo cargar settings del .env: {e}")
        return {}


def execute_sql(
    query: str,
    db_params: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Ejecuta una consulta SQL contra Firebird con reintentos y backoff.

    RESILIENCIA:
      - 3 reintentos con espera incremental (0.5s, 1s, 1.5s)
      - Siempre desconecta en finally
      - Fallback a .env si db_params es None o vacio
      - Logs detallados en cada intento

    Args:
        query:     SQL a ejecutar (ya normalizado por FirebirdSQLNormalizer)
        db_params: Parametros de conexion. Si None, usa .env

    Returns:
        Lista de dicts con los resultados

    Raises:
        Exception: Si todos los reintentos fallan
    """
    # Fallback a .env si no hay parametros
    if not db_params:
        logger.info("[DBExecutor] Sin db_params — usando configuracion del .env")
        db_params = _get_fallback_db_params()

    if not db_params:
        raise Exception("No hay parametros de conexion a la BD (ni en contexto ni en .env)")

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_DB_RETRIES + 1):
        driver = None
        try:
            logger.info(f"[DBExecutor] Intento {attempt}/{MAX_DB_RETRIES} — ejecutando SQL")
            logger.debug(f"[DBExecutor] Query: {query[:200]}{'...' if len(query) > 200 else ''}")

            driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
            config = _build_db_config(db_params)
            driver.connect(config)

            results = driver.execute_query(query)
            logger.info(f"[DBExecutor] OK — {len(results)} filas retornadas")
            return results

        except Exception as e:
            last_error = e
            logger.warning(f"[DBExecutor] Error en intento {attempt}/{MAX_DB_RETRIES}: {e}")

            if attempt < MAX_DB_RETRIES:
                wait = RETRY_BASE_WAIT_S * attempt
                logger.info(f"[DBExecutor] Esperando {wait}s antes de reintentar...")
                time.sleep(wait)

        finally:
            if driver is not None:
                try:
                    driver.disconnect()
                    logger.debug("[DBExecutor] Desconectado correctamente")
                except Exception as disc_err:
                    logger.warning(f"[DBExecutor] Error al desconectar: {disc_err}")

    # Todos los intentos fallaron
    error_msg = f"Error despues de {MAX_DB_RETRIES} intentos: {last_error}"
    logger.error(f"[DBExecutor] {error_msg}")
    raise Exception(error_msg)


def get_db_schema_context(db_params: Optional[Dict[str, Any]] = None) -> str:
    """
    Obtiene el esquema de la BD para el contexto del chat (metodo legacy v1).

    NOTA: Este metodo es el fallback cuando el SIUO no esta disponible.
    El sistema preferido es ContextRetriever.get_context() (SIUO v2).

    RESILIENCIA:
      - Maneja errores de conexion graciosamente
      - Limita el numero de tablas para evitar overflow de tokens
      - Siempre desconecta en finally
      - Devuelve string vacio si falla (no lanza excepcion)

    Args:
        db_params: Parametros de conexion. Si None, usa .env

    Returns:
        String con el esquema de la BD para el system prompt
    """
    if not db_params:
        db_params = _get_fallback_db_params()

    if not db_params:
        logger.warning("[DBExecutor] Sin parametros de BD para obtener esquema")
        return "No hay conexion a base de datos definida."

    driver = None
    try:
        logger.info(f"[DBExecutor] Obteniendo esquema de BD: {db_params.get('host')}:{db_params.get('port')}")

        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = _build_db_config(db_params)
        driver.connect(config)

        # Listar todas las tablas de usuario
        tables = driver.execute_query(QUERY_TABLES)
        table_names = [
            t['TABLE_NAME'] for t in tables
            if t.get('TABLE_NAME') and not t['TABLE_NAME'].startswith('RDB$')
        ]
        logger.info(f"[DBExecutor] {len(table_names)} tablas de usuario encontradas")

        # Construir esquema
        schema_parts = [
            f"Base de datos Firebird con {len(table_names)} tablas de usuario.\n",
            f"Tablas disponibles: {', '.join(table_names)}\n"
        ]

        # Esquema detallado solo para tablas prioritarias
        priority = [t for t in SCHEMA_PRIORITY_TABLES if t in table_names]
        logger.info(f"[DBExecutor] Obteniendo esquema detallado de {len(priority)} tablas prioritarias")

        for table_name in priority[:MAX_SCHEMA_TABLES]:
            try:
                columns = driver.execute_query(QUERY_TABLE_COLUMNS, (table_name,))
                if columns:
                    col_details = [
                        f"  - {c['FIELD_NAME']} ({c.get('FIELD_TYPE', '?')})"
                        for c in columns
                    ]
                    schema_parts.append(f"\nTabla: {table_name}")
                    schema_parts.append(f"Columnas ({len(columns)}):")
                    schema_parts.extend(col_details)
                    logger.debug(f"[DBExecutor] {table_name}: {len(columns)} columnas")
            except Exception as col_err:
                logger.warning(f"[DBExecutor] No se pudo obtener esquema de {table_name}: {col_err}")

        return "\n".join(schema_parts)

    except Exception as e:
        logger.error(f"[DBExecutor] Error obteniendo esquema: {e}", exc_info=True)
        return f"Error obteniendo esquema de BD: {e}"

    finally:
        if driver is not None:
            try:
                driver.disconnect()
            except Exception as disc_err:
                logger.warning(f"[DBExecutor] Error al desconectar (esquema): {disc_err}")


def test_connection(db_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Prueba la conexion a la BD y devuelve el estado.

    Util para el endpoint /health y diagnosticos.

    Returns:
        Dict con: connected (bool), error (str|None), tables_count (int)
    """
    if not db_params:
        db_params = _get_fallback_db_params()

    driver = None
    try:
        driver = DBFactory.get_driver(DBConstants.TYPE_FIREBIRD)
        config = _build_db_config(db_params)
        driver.connect(config)

        tables = driver.execute_query(QUERY_TABLES)
        n_tables = len([t for t in tables if not t.get('TABLE_NAME', '').startswith('RDB$')])

        return {
            "connected":    True,
            "error":        None,
            "tables_count": n_tables,
            "host":         db_params.get("host", "?"),
            "database":     db_params.get("database", "?"),
        }

    except Exception as e:
        logger.warning(f"[DBExecutor] Test de conexion fallido: {e}")
        return {
            "connected":    False,
            "error":        str(e),
            "tables_count": 0,
            "host":         db_params.get("host", "?") if db_params else "?",
            "database":     db_params.get("database", "?") if db_params else "?",
        }

    finally:
        if driver is not None:
            try:
                driver.disconnect()
            except Exception:
                pass
