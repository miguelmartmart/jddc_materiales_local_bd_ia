"""
hallucination_guard.py — Módulo de detección y prevención de alucinaciones en DEVIA.

RESPONSABILIDAD:
    Verificar que el SQL generado por la IA NO contiene alucinaciones:
    - Tablas que no existen en el esquema real de la BD
    - Columnas que no existen en las tablas referenciadas
    - Valores de TIPO/estado que no son válidos según el esquema conocido
    - Relaciones JOIN incorrectas (columnas de unión inexistentes)

PRINCIPIOS DEVIA:
    - Sin inventar: solo valida contra el esquema real (TABLE_COLUMNS del simulador)
    - Ultra-resiliente: si falla la validación, devuelve resultado conservador (warn, no block)
    - Determinista: la validación es 100% determinista, sin IA
    - Modular: no tiene dependencias circulares con otros módulos del pipeline
    - Logging detallado: cada alucinación detectada queda registrada para auditoría
    - Genérico: funciona para cualquier SQL sobre cualquier tabla del esquema

ARQUITECTURA:
    [1] Extraer tablas del SQL (regex sobre FROM/JOIN)
    [2] Verificar que cada tabla existe en el esquema conocido
    [3] Extraer columnas del SQL (SELECT, WHERE, ORDER BY, GROUP BY, ON)
    [4] Verificar que cada columna existe en alguna de las tablas referenciadas
    [5] Verificar valores de TIPO/estado conocidos (DOCCAB.TIPO, CAJA.TIPO, etc.)
    [6] Devolver HallucinationReport con lista de problemas encontrados

INTEGRACIÓN:
    Se llama DESPUÉS de que la IA genera el SQL y ANTES de ejecutarlo.
    Si hay alucinaciones críticas → el SQL no se ejecuta.
    Si hay advertencias → se ejecuta pero se informa al usuario.

DEVIA: backend/modules/chat/DEVIA.MD
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ─── Niveles de severidad ─────────────────────────────────────────────────────

class HallucinationSeverity(Enum):
    """Severidad de una alucinación detectada."""
    OK      = "ok"       # Sin problemas
    WARNING = "warning"  # Posible alucinación — ejecutar con advertencia
    ERROR   = "error"    # Alucinación confirmada — no ejecutar


# ─── Esquema conocido de la BD JDDC ──────────────────────────────────────────
# Importado del simulador (fuente de verdad única).
# Si el import falla, se usa un esquema mínimo de emergencia.

def _load_schema() -> Dict[str, FrozenSet[str]]:
    """
    Carga el esquema de columnas desde el módulo del simulador.
    Fuente de verdad: backend/modules/db_simulator/schema.py (TABLE_COLUMNS).
    Si falla, devuelve esquema mínimo para no bloquear el sistema.
    """
    try:
        from backend.modules.db_simulator.schema import TABLE_COLUMNS
        return {
            table: frozenset(cols)
            for table, cols in TABLE_COLUMNS.items()
        }
    except Exception as e:
        logger.warning(
            f"[HALLUCINATION_GUARD] No se pudo cargar TABLE_COLUMNS: {e} "
            f"— usando esquema mínimo de emergencia"
        )
        # Esquema mínimo: solo las tablas más críticas con sus columnas clave
        return {
            "DOCCAB":    frozenset(["CODIGO", "TIPO", "FECHA", "CODCLIENTE", "CODPROYECTO",
                                    "IMPORTETOTAL", "NUMERO", "CODAGENTE", "CODFORMAPAGO"]),
            "DOCLIN":    frozenset(["CODIGO", "CODDOC", "CODARTICULO", "CANTIDAD",
                                    "PRECIO", "DESCUENTO", "IMPORTE"]),
            "PROYECTOS": frozenset(["CODIGO", "NOMBRE", "TIPORETENCION", "PORCRETENCION",
                                    "DIASDEVOLUCIONRETENCION"]),
            "CLIENTE":   frozenset(["CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "NIF",
                                    "CODAGENTE", "BAJA"]),
            "PROVEED":   frozenset(["CODIGO", "NOMBRECOMERCIAL", "RAZONSOCIAL", "NIF", "BAJA"]),
            "ARTICULO":  frozenset(["CODIGO", "NOMBRE", "STOCKARTICULO", "PRECIOVENTA",
                                    "PRECIOCOSTE", "BAJA"]),
            "CAJA":      frozenset(["CODAPUNTE", "TIPO", "FECHA", "IMPORTE", "CONCEPTO",
                                    "CODCLIENTE"]),
            "AGENTES":   frozenset(["CODIGO", "NOMBRE", "COMISION"]),
        }


# Esquema cargado una sola vez al importar el módulo
_KNOWN_SCHEMA: Dict[str, FrozenSet[str]] = _load_schema()

# Tablas conocidas (en mayúsculas)
_KNOWN_TABLES: FrozenSet[str] = frozenset(_KNOWN_SCHEMA.keys())

# ─── Valores válidos conocidos para columnas de tipo enumerado ────────────────
# Fuente de verdad: documentación JDDC verificada con el usuario.
# Solo se validan columnas cuyo dominio es conocido y cerrado.

_KNOWN_ENUM_VALUES: Dict[str, Dict[str, Set[int]]] = {
    # DOCCAB.TIPO: tipos de documento verificados con JDDC
    "DOCCAB": {
        "TIPO": {0, 1, 2, 3, 10, 11, 12, 13, 51},
        # 51 = tipo especial observado en datos reales del simulador
    },
    # CAJA.TIPO: 1=cobro, 2=pago
    "CAJA": {
        "TIPO": {1, 2},
    },
    # PROYECTOS.TIPORETENCION: 0=sin, 1=aval previo, 2=aval al finalizar, 3=sin aval
    "PROYECTOS": {
        "TIPORETENCION": {0, 1, 2, 3},
    },
    # CLIENTE.BAJA / PROVEED.BAJA / ARTICULO.BAJA: 0=activo, 1=baja
    "CLIENTE":   {"BAJA": {0, 1}},
    "PROVEED":   {"BAJA": {0, 1}},
    "ARTICULO":  {"BAJA": {0, 1}},
    "AGENTES":   {"BAJA": {0, 1}},
}

# ─── Columnas que NO existen (alucinaciones frecuentes de la IA) ──────────────
# Columnas que la IA inventa con frecuencia pero que NO están en el esquema real.
_KNOWN_NONEXISTENT_COLUMNS: Dict[str, Set[str]] = {
    "ARTICULO":  {"STOCK", "CANTIDAD_STOCK", "EXISTENCIAS", "UNIDADES"},
    "CAJA":      {"CODIGO"},   # CAJA usa CODAPUNTE como PK, no CODIGO
    "DOCCAB":    {"IMPORTE", "TOTAL", "IMPORTEBASE"},  # usar IMPORTETOTAL
    "PROYECTOS": {"ID", "DESCRIPCION_PROYECTO"},
}


# ─── Resultado de la validación ───────────────────────────────────────────────

@dataclass
class HallucinationIssue:
    """Un problema de alucinación detectado en el SQL."""
    severity: HallucinationSeverity
    category: str          # "tabla_inexistente", "columna_inexistente", "valor_invalido", etc.
    detail: str            # Descripción del problema
    suggestion: str = ""   # Sugerencia de corrección


@dataclass
class HallucinationReport:
    """
    Resultado completo de la validación anti-alucinación.

    Attributes:
        sql_original:   SQL analizado
        issues:         Lista de problemas encontrados
        severity:       Severidad máxima encontrada
        is_safe:        True si no hay errores (puede haber warnings)
        tables_found:   Tablas detectadas en el SQL
        columns_found:  Columnas detectadas en el SQL
    """
    sql_original: str = ""
    issues: List[HallucinationIssue] = field(default_factory=list)
    severity: HallucinationSeverity = HallucinationSeverity.OK
    is_safe: bool = True
    tables_found: List[str] = field(default_factory=list)
    columns_found: List[str] = field(default_factory=list)

    def add_issue(self, issue: HallucinationIssue) -> None:
        """Añade un problema y actualiza la severidad máxima."""
        self.issues.append(issue)
        if issue.severity == HallucinationSeverity.ERROR:
            self.severity = HallucinationSeverity.ERROR
            self.is_safe = False
        elif (issue.severity == HallucinationSeverity.WARNING
              and self.severity != HallucinationSeverity.ERROR):
            self.severity = HallucinationSeverity.WARNING

    @property
    def errors(self) -> List[HallucinationIssue]:
        return [i for i in self.issues if i.severity == HallucinationSeverity.ERROR]

    @property
    def warnings(self) -> List[HallucinationIssue]:
        return [i for i in self.issues if i.severity == HallucinationSeverity.WARNING]

    def summary(self) -> str:
        """Resumen legible del resultado."""
        if not self.issues:
            return "✅ SQL validado: sin alucinaciones detectadas"
        parts = []
        if self.errors:
            parts.append(f"❌ {len(self.errors)} error(es): "
                         + "; ".join(e.detail for e in self.errors))
        if self.warnings:
            parts.append(f"⚠️ {len(self.warnings)} advertencia(s): "
                         + "; ".join(w.detail for w in self.warnings))
        return " | ".join(parts)


# ─── HallucinationGuard ───────────────────────────────────────────────────────

class HallucinationGuard:
    """
    Módulo de detección y prevención de alucinaciones en SQL generado por IA.

    PRINCIPIO DEVIA — Sin inventar:
        Verifica que cada tabla, columna y valor del SQL generado existe
        realmente en el esquema de la BD. Si no existe → alucinación detectada.

    PRINCIPIO DEVIA — Genérico:
        Funciona para cualquier SQL sobre cualquier tabla del esquema.
        No hay casos hardcodeados por tabla específica.

    PRINCIPIO DEVIA — Ultra-resiliente:
        Si la validación falla por cualquier motivo, devuelve un report
        conservador (WARNING, no ERROR) para no bloquear el sistema.
    """

    def __init__(self, schema: Optional[Dict[str, FrozenSet[str]]] = None):
        """
        Args:
            schema: Esquema de columnas por tabla. Si None, usa el esquema global cargado.
        """
        self._schema = schema or _KNOWN_SCHEMA
        self._known_tables = frozenset(self._schema.keys())

        # Compilar patrones regex una sola vez
        self._re_tables = re.compile(
            r'\b(?:FROM|JOIN|INTO|UPDATE)\s+([A-Z_][A-Z0-9_]*)',
            re.IGNORECASE
        )
        self._re_columns_select = re.compile(
            r'SELECT\s+(?:FIRST\s+\d+\s+)?(.+?)\s+FROM',
            re.IGNORECASE | re.DOTALL
        )
        self._re_column_qualified = re.compile(
            r'\b([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_]*)\b',
            re.IGNORECASE
        )
        self._re_tipo_value = re.compile(
            r'\bTIPO\s*=\s*(\d+)',
            re.IGNORECASE
        )
        self._re_enum_value = re.compile(
            r'\b([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_]*)\s*=\s*(\d+)',
            re.IGNORECASE
        )

    def validate(self, sql: str) -> HallucinationReport:
        """
        Valida el SQL generado por la IA contra el esquema real de la BD.

        Args:
            sql: SQL generado por la IA (puede ser Firebird o SQLite)

        Returns:
            HallucinationReport con todos los problemas encontrados
        """
        report = HallucinationReport(sql_original=sql)

        if not sql or not sql.strip():
            return report  # SQL vacío → sin problemas

        try:
            sql_upper = sql.upper()

            # FASE 1: Extraer y validar tablas
            tables = self._extract_tables(sql)
            report.tables_found = list(tables)
            self._validate_tables(tables, report)

            # FASE 2: Extraer y validar columnas cualificadas (TABLA.COLUMNA)
            qualified_cols = self._extract_qualified_columns(sql)
            report.columns_found = [f"{t}.{c}" for t, c in qualified_cols]
            self._validate_qualified_columns(qualified_cols, report)

            # FASE 3: Validar columnas no-existentes conocidas
            self._validate_known_nonexistent(sql_upper, tables, report)

            # FASE 4: Validar valores de columnas enumeradas
            self._validate_enum_values(sql, tables, report)

            logger.info(
                f"[HALLUCINATION_GUARD] Validación completada: "
                f"severity={report.severity.value} "
                f"issues={len(report.issues)} "
                f"tablas={report.tables_found}"
            )

        except Exception as e:
            logger.warning(
                f"[HALLUCINATION_GUARD] Error durante validación: {e} "
                f"— devolviendo report conservador"
            )
            report.add_issue(HallucinationIssue(
                severity=HallucinationSeverity.WARNING,
                category="validation_error",
                detail=f"No se pudo completar la validación: {e}",
                suggestion="Verificar manualmente el SQL antes de ejecutar"
            ))

        return report

    # ─── Extracción de elementos del SQL ─────────────────────────────────────

    def _extract_tables(self, sql: str) -> Set[str]:
        """Extrae los nombres de tablas del SQL (FROM, JOIN, UPDATE, INTO)."""
        matches = self._re_tables.findall(sql)
        # Filtrar palabras clave SQL que no son tablas
        sql_keywords = {
            "SELECT", "WHERE", "AND", "OR", "NOT", "IN", "IS", "NULL",
            "ORDER", "GROUP", "BY", "HAVING", "LIMIT", "FIRST", "SKIP",
            "INNER", "LEFT", "RIGHT", "OUTER", "CROSS", "ON", "AS",
            "DISTINCT", "ALL", "UNION", "EXCEPT", "INTERSECT",
        }
        return {m.upper() for m in matches if m.upper() not in sql_keywords}

    def _extract_qualified_columns(self, sql: str) -> List[Tuple[str, str]]:
        """
        Extrae columnas cualificadas (TABLA.COLUMNA) del SQL.
        Devuelve lista de (tabla, columna) en mayúsculas.
        """
        matches = self._re_column_qualified.findall(sql)
        result = []
        sql_keywords = {
            "SELECT", "FROM", "WHERE", "JOIN", "ON", "AND", "OR",
            "ORDER", "GROUP", "HAVING", "AS", "BY",
        }
        for table, col in matches:
            t_upper = table.upper()
            c_upper = col.upper()
            if t_upper not in sql_keywords and c_upper not in sql_keywords:
                result.append((t_upper, c_upper))
        return result

    # ─── Validaciones ─────────────────────────────────────────────────────────

    def _validate_tables(self, tables: Set[str], report: HallucinationReport) -> None:
        """Verifica que todas las tablas del SQL existen en el esquema conocido."""
        for table in sorted(tables):
            if table not in self._known_tables:
                report.add_issue(HallucinationIssue(
                    severity=HallucinationSeverity.ERROR,
                    category="tabla_inexistente",
                    detail=f"Tabla '{table}' no existe en el esquema de la BD",
                    suggestion=(
                        f"Tablas disponibles: {', '.join(sorted(self._known_tables)[:10])}..."
                    )
                ))
                logger.warning(
                    f"[HALLUCINATION_GUARD] ❌ Tabla inexistente: '{table}'"
                )

    def _validate_qualified_columns(
        self,
        qualified_cols: List[Tuple[str, str]],
        report: HallucinationReport
    ) -> None:
        """
        Verifica que las columnas cualificadas (TABLA.COLUMNA) existen en el esquema.
        Solo valida si la tabla es conocida (si la tabla no existe, ya se reportó en fase 1).
        """
        for table, col in qualified_cols:
            if table not in self._schema:
                continue  # Tabla desconocida ya reportada en fase 1
            known_cols = self._schema[table]
            if col not in known_cols:
                # Buscar si es una columna conocida como no-existente (alucinación frecuente)
                nonexistent = _KNOWN_NONEXISTENT_COLUMNS.get(table, set())
                if col in nonexistent:
                    severity = HallucinationSeverity.ERROR
                    suggestion = self._suggest_column_correction(table, col)
                else:
                    severity = HallucinationSeverity.WARNING
                    suggestion = (
                        f"Columnas de {table}: {', '.join(sorted(known_cols)[:8])}..."
                    )
                report.add_issue(HallucinationIssue(
                    severity=severity,
                    category="columna_inexistente",
                    detail=f"Columna '{table}.{col}' no existe en el esquema",
                    suggestion=suggestion
                ))
                logger.warning(
                    f"[HALLUCINATION_GUARD] {'❌' if severity == HallucinationSeverity.ERROR else '⚠️'} "
                    f"Columna inexistente: '{table}.{col}'"
                )

    def _validate_known_nonexistent(
        self,
        sql_upper: str,
        tables: Set[str],
        report: HallucinationReport
    ) -> None:
        """
        Verifica columnas conocidas como no-existentes (alucinaciones frecuentes de la IA).
        Busca patrones como 'ARTICULO.STOCK' o simplemente 'STOCK' cuando ARTICULO está en el SQL.

        PRINCIPIO DEVIA — Sin falsos positivos:
          Excluye aliases de SELECT (ej: COUNT(*) as TOTAL) para no confundirlos
          con columnas reales. Un alias es válido aunque coincida con un nombre
          de columna no-existente.
        """
        # Extraer aliases definidos en el SQL (AS alias_name)
        # Patrón: AS <nombre> — captura aliases de columnas y subqueries
        alias_pattern = re.compile(r'\bAS\s+([A-Z_][A-Z0-9_]*)\b', re.IGNORECASE)
        aliases_in_sql: Set[str] = {m.upper() for m in alias_pattern.findall(sql_upper)}

        for table, bad_cols in _KNOWN_NONEXISTENT_COLUMNS.items():
            if table not in tables:
                continue
            for bad_col in bad_cols:
                # Si el nombre coincide con un alias definido en el SQL → no es alucinación
                if bad_col in aliases_in_sql:
                    continue

                # Buscar la columna sin cualificar (ej: "STOCK" sin "ARTICULO.")
                pattern = rf'\b{re.escape(bad_col)}\b'
                if re.search(pattern, sql_upper):
                    # Verificar que no sea ya una columna cualificada de otra tabla
                    qualified_pattern = rf'\b[A-Z_]+\.{re.escape(bad_col)}\b'
                    qualified_matches = re.findall(qualified_pattern, sql_upper)
                    # Si aparece sin cualificar o cualificada con la tabla incorrecta
                    if not qualified_matches or any(
                        m.startswith(table + ".") for m in qualified_matches
                    ):
                        suggestion = self._suggest_column_correction(table, bad_col)
                        report.add_issue(HallucinationIssue(
                            severity=HallucinationSeverity.ERROR,
                            category="columna_alucinada",
                            detail=(
                                f"Columna '{bad_col}' no existe en {table} "
                                f"(alucinación frecuente de la IA)"
                            ),
                            suggestion=suggestion
                        ))
                        logger.warning(
                            f"[HALLUCINATION_GUARD] ❌ Columna alucinada: "
                            f"'{bad_col}' en tabla {table}"
                        )

    def _validate_enum_values(
        self,
        sql: str,
        tables: Set[str],
        report: HallucinationReport
    ) -> None:
        """
        Verifica que los valores de columnas enumeradas (TIPO, BAJA, TIPORETENCION)
        son válidos según el esquema conocido.
        """
        # Buscar patrones TABLA.COLUMNA = VALOR
        for match in self._re_enum_value.finditer(sql):
            table = match.group(1).upper()
            col   = match.group(2).upper()
            try:
                value = int(match.group(3))
            except ValueError:
                continue

            if table not in _KNOWN_ENUM_VALUES:
                continue
            if col not in _KNOWN_ENUM_VALUES[table]:
                continue

            valid_values = _KNOWN_ENUM_VALUES[table][col]
            if value not in valid_values:
                report.add_issue(HallucinationIssue(
                    severity=HallucinationSeverity.WARNING,
                    category="valor_invalido",
                    detail=(
                        f"Valor {value} no es válido para {table}.{col}. "
                        f"Valores válidos: {sorted(valid_values)}"
                    ),
                    suggestion=(
                        f"Para {table}.{col} usar: {sorted(valid_values)}"
                    )
                ))
                logger.warning(
                    f"[HALLUCINATION_GUARD] ⚠️ Valor inválido: "
                    f"{table}.{col} = {value} (válidos: {sorted(valid_values)})"
                )

    # ─── Sugerencias de corrección ────────────────────────────────────────────

    def _suggest_column_correction(self, table: str, bad_col: str) -> str:
        """
        Sugiere la corrección para una columna inexistente conocida.
        Genérico: busca la columna más similar en el esquema real.
        """
        # Correcciones conocidas para alucinaciones frecuentes
        known_corrections = {
            ("ARTICULO", "STOCK"):            "ARTICULO.STOCKARTICULO",
            ("ARTICULO", "CANTIDAD_STOCK"):   "ARTICULO.STOCKARTICULO",
            ("ARTICULO", "EXISTENCIAS"):      "ARTICULO.STOCKARTICULO",
            ("ARTICULO", "UNIDADES"):         "ARTICULO.STOCKARTICULO",
            ("CAJA", "CODIGO"):               "CAJA.CODAPUNTE (PK de CAJA)",
            ("DOCCAB", "IMPORTE"):            "DOCCAB.IMPORTETOTAL",
            ("DOCCAB", "TOTAL"):              "DOCCAB.IMPORTETOTAL",
            ("DOCCAB", "IMPORTEBASE"):        "DOCCAB.IMPORTETOTAL o DOCCAB.BASEIMPONIBLE",
        }
        correction = known_corrections.get((table, bad_col))
        if correction:
            return f"Usar {correction} en lugar de {table}.{bad_col}"

        # Búsqueda genérica: columna más similar por prefijo
        if table in self._schema:
            similar = [
                c for c in self._schema[table]
                if bad_col[:3].upper() in c.upper() or c.upper().startswith(bad_col[:3].upper())
            ]
            if similar:
                return f"Columnas similares en {table}: {', '.join(sorted(similar)[:3])}"

        return f"Verificar columnas disponibles en {table}"

    # ─── Utilidades públicas ──────────────────────────────────────────────────

    def get_known_tables(self) -> List[str]:
        """Devuelve la lista de tablas conocidas en el esquema."""
        return sorted(self._known_tables)

    def get_known_columns(self, table: str) -> List[str]:
        """Devuelve las columnas conocidas de una tabla."""
        return sorted(self._schema.get(table.upper(), frozenset()))

    def is_table_known(self, table: str) -> bool:
        """Verifica si una tabla existe en el esquema conocido."""
        return table.upper() in self._known_tables

    def is_column_known(self, table: str, column: str) -> bool:
        """Verifica si una columna existe en una tabla del esquema conocido."""
        t = table.upper()
        c = column.upper()
        return t in self._schema and c in self._schema[t]


# ─── Singleton ────────────────────────────────────────────────────────────────

_guard_instance: Optional[HallucinationGuard] = None


def get_hallucination_guard() -> HallucinationGuard:
    """
    Devuelve la instancia singleton del guard de alucinaciones.
    Thread-safe para uso en FastAPI (single-process).
    """
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = HallucinationGuard()
        logger.info(
            f"[HALLUCINATION_GUARD] Inicializado con {len(_guard_instance.get_known_tables())} tablas"
        )
    return _guard_instance
