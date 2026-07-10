"""
adaptive_resilience.py — Motor de Resiliencia Adaptativa para DEVIA.

RESPONSABILIDAD:
    Cuando la IA no está disponible (timeout, red caída, modelo no responde),
    este módulo genera respuestas de ULTRA CALIDAD usando:
    1. Datos reales del simulador SQLite (ejecuta SQLs deterministas)
    2. Razonamiento semántico sobre los resultados (sin IA)
    3. Conocimiento de negocio JDDC hardcodeado (certificaciones, proyectos, etc.)
    4. Formato de respuesta profesional y legible

PRINCIPIOS DEVIA:
    - Ultra-resiliente: NUNCA devuelve "no disponible" si hay datos en el simulador
    - Sin inventar: solo usa datos reales de la BD
    - Determinista: misma pregunta → misma respuesta (sin IA)
    - Adaptable: detecta el dominio de la pregunta y genera la respuesta adecuada
    - Auto-configurable: aprende del esquema real del simulador

FLUJO:
    [1] Detectar dominio de la pregunta (determinista)
    [2] Ejecutar SQLs deterministas según el dominio
    [3] Interpretar resultados con lógica de negocio
    [4] Generar respuesta en lenguaje natural de calidad

DEVIA: backend/modules/chat/DEVIA.MD
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Tipos de dominio (espejo de semantic_reasoning_engine para evitar import circular)
# ═══════════════════════════════════════════════════════════════════════════════

class _Domain:
    PROYECTOS_OBRAS      = "proyectos_obras"
    CERTIFICACIONES      = "certificaciones"
    RETENCIONES          = "retenciones"
    DOCUMENTOS           = "documentos"
    ARTICULOS_STOCK      = "articulos_stock"
    CLIENTES_PROVEEDORES = "clientes_proveedores"
    FINANCIERO           = "financiero"
    GENERAL              = "general"


# ═══════════════════════════════════════════════════════════════════════════════
# Patrones de detección de dominio (deterministas, O(1))
# ═══════════════════════════════════════════════════════════════════════════════

_DOMAIN_PATTERNS: List[Tuple[str, str, List[str]]] = [
    # (regex, dominio, keywords_adicionales)
    # ORDEN IMPORTANTE: los más específicos primero (certificaciones > retenciones > proyectos)
    (
        r'\b(certificaci[oó]n|certificaciones|certificado|certificados|'
        r'facturaci[oó]n parcial|factura parcial|factura de obra|'
        r'periodo de obra|per[ií]odo de obra|liquidaci[oó]n parcial|'
        r'cada proyecto|por proyecto)\b',
        _Domain.CERTIFICACIONES,
        ["DOCCAB", "PROYECTOS", "CODPROYECTO"]
    ),
    (
        r'\b(retenci[oó]n|retenciones|aval|avales|garant[ií]a de obra|'
        r'devoluci[oó]n de retenci[oó]n|periodo de garant[ií]a|per[ií]odo de garant[ií]a|'
        r'fin de garant[ií]a|cobro de retenci[oó]n|porcretencion|tiporetencion|'
        r'garant[ií]a.*obra|obra.*garant[ií]a)\b',
        _Domain.RETENCIONES,
        ["PROYECTOS", "TIPORETENCION", "PORCRETENCION"]
    ),
    (
        r'\b(proyecto|proyectos|obra|obras|instalaci[oó]n|instalaciones|'
        r'contrato de obra|ejecuci[oó]n de obra|obra civil|'
        r'presupuesto de obra|licitaci[oó]n)\b',
        _Domain.PROYECTOS_OBRAS,
        ["PROYECTOS", "OBRACAB", "PRESUPROYE", "DOCCAB"]
    ),
    (
        r'\b(factura|facturas|albar[aá]n|albaranes|pedido|pedidos|'
        r'presupuesto|presupuestos|abono|abonos|contrato|contratos|'
        r'facturado|facturaci[oó]n|hemos facturado|lo facturado)\b',
        _Domain.DOCUMENTOS,
        ["DOCCAB", "DOCLIN"]
    ),
    (
        r'\b(art[ií]culo|art[ií]culos|producto|productos|stock|inventario|'
        r'almac[eé]n|almacenes|existencias|referencia)\b',
        _Domain.ARTICULOS_STOCK,
        ["ARTICULO", "DOCLIN", "ESTALMACEN"]
    ),
    # FINANCIERO antes que CLIENTES para que "cobros de clientes" → FINANCIERO
    (
        r'\b(caja|cobro|cobros|pago|pagos|tesorer[ií]a|tesoreria|'
        r'recibo|recibos|vencimiento|vencimientos|liquidez|'
        r'cobros pendientes|pagos pendientes|nos deben)\b',
        _Domain.FINANCIERO,
        ["CAJA", "DOCCAB"]
    ),
    (
        r'\b(cliente|clientes|proveedor|proveedores|agente|agentes|'
        r'comercial|comerciales)\b',
        _Domain.CLIENTES_PROVEEDORES,
        ["CLIENTE", "PROVEED", "AGENTES"]
    ),
]

_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), domain, tables)
    for pattern, domain, tables in _DOMAIN_PATTERNS
]


# ═══════════════════════════════════════════════════════════════════════════════
# SQLs deterministas por dominio (compatibles con SQLite del simulador)
# ═══════════════════════════════════════════════════════════════════════════════

_SQLS_BY_DOMAIN: Dict[str, List[Dict]] = {

    _Domain.CERTIFICACIONES: [
        {
            "id": "cert_por_proyecto_resumen",
            "objetivo": "Certificaciones agrupadas por proyecto",
            "sql": (
                "SELECT p.CODIGO AS COD_PROYECTO, p.NOMBRE AS NOMBRE_PROYECTO, "
                "d.TIPO, COUNT(d.CODIGO) AS N_CERTIFICACIONES, "
                "CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
                "MIN(d.FECHA) AS PRIMERA, MAX(d.FECHA) AS ULTIMA "
                "FROM PROYECTOS p "
                "JOIN DOCCAB d ON d.CODPROYECTO = p.CODIGO "
                "WHERE d.CODPROYECTO IS NOT NULL AND d.CODPROYECTO <> '' "
                "GROUP BY p.CODIGO, p.NOMBRE, d.TIPO "
                "ORDER BY p.NOMBRE, d.TIPO"
            ),
            "descripcion": "Certificaciones por proyecto (agrupadas)"
        },
        {
            "id": "cert_detalle",
            "objetivo": "Detalle de cada certificación por proyecto",
            "sql": (
                "SELECT p.NOMBRE AS PROYECTO, "
                "d.CODIGO AS NUM_DOC, d.TIPO, d.FECHA, "
                "CAST(d.IMPORTETOTAL AS NUMERIC(15,2)) AS IMPORTE_EUR "
                "FROM PROYECTOS p "
                "JOIN DOCCAB d ON d.CODPROYECTO = p.CODIGO "
                "WHERE d.CODPROYECTO IS NOT NULL AND d.CODPROYECTO <> '' "
                "ORDER BY p.NOMBRE, d.FECHA "
                "LIMIT 100"
            ),
            "descripcion": "Listado individual de certificaciones"
        },
        {
            "id": "proyectos_lista",
            "objetivo": "Lista de proyectos disponibles",
            "sql": (
                "SELECT p.CODIGO, p.NOMBRE, p.CLIENTE, "
                "p.FECHAINICIO, p.FECHAFIN, p.TIPORETENCION, p.PORCRETENCION "
                "FROM PROYECTOS p "
                "ORDER BY p.FECHAINICIO DESC "
                "LIMIT 50"
            ),
            "descripcion": "Proyectos en la BD"
        },
    ],

    _Domain.PROYECTOS_OBRAS: [
        {
            "id": "proyectos_lista",
            "objetivo": "Lista de proyectos/obras",
            "sql": (
                "SELECT p.CODIGO, p.NOMBRE, p.CLIENTE, "
                "p.FECHAINICIO, p.FECHAFIN, p.TIPORETENCION, p.PORCRETENCION "
                "FROM PROYECTOS p "
                "ORDER BY p.FECHAINICIO DESC "
                "LIMIT 50"
            ),
            "descripcion": "Proyectos en la BD"
        },
        {
            "id": "facturado_por_proyecto",
            "objetivo": "Total facturado/certificado por proyecto",
            "sql": (
                "SELECT d.CODPROYECTO, p.NOMBRE, "
                "COUNT(d.CODIGO) AS N_DOCS, "
                "CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                "FROM DOCCAB d "
                "LEFT JOIN PROYECTOS p ON p.CODIGO = d.CODPROYECTO "
                "WHERE d.CODPROYECTO IS NOT NULL AND d.CODPROYECTO <> '' "
                "GROUP BY d.CODPROYECTO, p.NOMBRE "
                "ORDER BY TOTAL_EUR DESC "
                "LIMIT 30"
            ),
            "descripcion": "Facturado por proyecto"
        },
    ],

    _Domain.RETENCIONES: [
        {
            "id": "retenciones_por_proyecto",
            "objetivo": "Retenciones y avales por proyecto",
            "sql": (
                "SELECT CODIGO, NOMBRE, CLIENTE, "
                "TIPORETENCION, PORCRETENCION, DIASDEVOLUCIONRETENCION "
                "FROM PROYECTOS "
                "WHERE TIPORETENCION IS NOT NULL "
                "ORDER BY TIPORETENCION, NOMBRE "
                "LIMIT 50"
            ),
            "descripcion": "Retenciones por proyecto"
        },
    ],

    _Domain.DOCUMENTOS: [
        {
            "id": "distribucion_tipos",
            "objetivo": "Distribución de documentos por tipo",
            "sql": (
                "SELECT TIPO, COUNT(*) AS N, "
                "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR, "
                "CAST(AVG(IMPORTETOTAL) AS NUMERIC(15,2)) AS MEDIA_EUR "
                "FROM DOCCAB "
                "GROUP BY TIPO ORDER BY N DESC"
            ),
            "descripcion": "Tipos de documento"
        },
        {
            "id": "distribucion_anual",
            "objetivo": "Distribución anual de documentos",
            "sql": (
                "SELECT strftime('%Y', FECHA) AS ANO, COUNT(*) AS N, "
                "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                "FROM DOCCAB WHERE FECHA IS NOT NULL "
                "GROUP BY strftime('%Y', FECHA) ORDER BY ANO DESC "
                "LIMIT 10"
            ),
            "descripcion": "Documentos por año"
        },
    ],

    _Domain.ARTICULOS_STOCK: [
        {
            "id": "top_articulos",
            "objetivo": "Top artículos por stock",
            "sql": (
                "SELECT CODIGO, NOMBRE, STOCKARTICULO, PRECIOVENTA, PRECIOCOSTE "
                "FROM ARTICULO "
                "WHERE STOCKARTICULO > 0 "
                "ORDER BY STOCKARTICULO DESC "
                "LIMIT 20"
            ),
            "descripcion": "Artículos con stock"
        },
        {
            "id": "familias",
            "objetivo": "Familias de artículos",
            "sql": (
                "SELECT f.NOMBRE AS FAMILIA, COUNT(a.CODIGO) AS N_ARTICULOS, "
                "CAST(AVG(a.PRECIOVENTA) AS NUMERIC(15,2)) AS PRECIO_MEDIO "
                "FROM FAMILIA f "
                "LEFT JOIN ARTICULO a ON a.CODFAMILIA = f.CODIGO "
                "GROUP BY f.CODIGO, f.NOMBRE "
                "ORDER BY N_ARTICULOS DESC "
                "LIMIT 20"
            ),
            "descripcion": "Familias de artículos"
        },
    ],

    _Domain.CLIENTES_PROVEEDORES: [
        {
            "id": "top_clientes",
            "objetivo": "Top clientes por facturación",
            "sql": (
                "SELECT d.CODCLIENTE, MAX(c.NOMBRECOMERCIAL) AS NOMBRE, "
                "COUNT(d.CODIGO) AS N_DOCS, "
                "CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                "FROM DOCCAB d "
                "LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO "
                "WHERE d.CODCLIENTE IS NOT NULL AND d.CODCLIENTE > 0 "
                "GROUP BY d.CODCLIENTE "
                "ORDER BY TOTAL_EUR DESC "
                "LIMIT 10"
            ),
            "descripcion": "Top clientes"
        },
    ],

    _Domain.FINANCIERO: [
        {
            "id": "caja_resumen",
            "objetivo": "Resumen de caja/cobros",
            "sql": (
                "SELECT strftime('%Y', FECHA) AS ANO, "
                "COUNT(*) AS N_MOVIMIENTOS, "
                "CAST(SUM(IMPORTE) AS NUMERIC(15,2)) AS TOTAL_EUR "
                "FROM CAJA WHERE FECHA IS NOT NULL "
                "GROUP BY strftime('%Y', FECHA) ORDER BY ANO DESC "
                "LIMIT 5"
            ),
            "descripcion": "Movimientos de caja por año"
        },
    ],

    _Domain.GENERAL: [
        {
            "id": "resumen_general",
            "objetivo": "Resumen general de la BD",
            "sql": (
                "SELECT TIPO, COUNT(*) AS N, "
                "CAST(SUM(IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR "
                "FROM DOCCAB GROUP BY TIPO ORDER BY N DESC"
            ),
            "descripcion": "Resumen de documentos"
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Mapeo de tipos de documento JDDC (fuente de verdad)
# ═══════════════════════════════════════════════════════════════════════════════

_TIPO_NOMBRES: Dict[int, str] = {
    0:  "Presupuesto cliente",
    1:  "Pedido cliente",
    2:  "Albarán cliente",
    3:  "Factura cliente",
    10: "Presupuesto proveedor",
    11: "Pedido proveedor",
    12: "Albarán proveedor",
    13: "Factura proveedor",
    21: "Movimiento almacén",
    51: "Certificación de obra",
    61: "Documento especial",
}

_TIPORETENCION_NOMBRES: Dict[int, str] = {
    0: "Sin retención",
    1: "Aval bancario previo (antes de la obra)",
    2: "Aval al finalizar la obra",
    3: "Sin aval — cliente paga al finalizar garantía",
}


# ═══════════════════════════════════════════════════════════════════════════════
# AdaptiveResilienceEngine
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResilienceResult:
    """Resultado del motor de resiliencia adaptativa."""
    response: str = ""
    domain: str = _Domain.GENERAL
    sqls_executed: int = 0
    sqls_successful: int = 0
    data_rows: int = 0
    used_simulator: bool = False
    quality: str = "low"  # "high" | "medium" | "low"
    errors: List[str] = field(default_factory=list)


class AdaptiveResilienceEngine:
    """
    Motor de resiliencia adaptativa para DEVIA.

    Cuando la IA no está disponible, genera respuestas de calidad usando:
    1. Datos reales del simulador SQLite
    2. Razonamiento semántico determinista
    3. Conocimiento de negocio JDDC

    Ultra-resiliente: NUNCA lanza excepciones al caller.
    Si todo falla, devuelve una respuesta mínima con los datos disponibles.
    """

    def __init__(self, sql_executor: Optional[Callable] = None):
        """
        Args:
            sql_executor: Función async que ejecuta SQL y devuelve List[Dict].
                          Si es None, intenta usar el simulador directamente.
        """
        self._sql_executor = sql_executor

    def _detect_domain(self, question: str) -> Tuple[str, List[str]]:
        """Detecta el dominio de negocio de la pregunta (determinista, O(1))."""
        msg = question.lower()
        for compiled, domain, tables in _COMPILED_PATTERNS:
            if compiled.search(msg):
                return domain, tables
        return _Domain.GENERAL, []

    async def _execute_sql(self, sql: str) -> List[Dict]:
        """
        Ejecuta un SQL usando el executor configurado o el simulador directo.
        Ultra-resiliente: devuelve [] si falla.
        """
        if self._sql_executor:
            try:
                result = await self._sql_executor(sql)
                return result or []
            except Exception as e:
                logger.debug(f"[RESILIENCE] SQL executor falló: {e}")
                return []

        # Fallback: usar el simulador directamente (síncrono)
        try:
            from backend.modules.db_simulator.driver import SimulatorDriver
            driver = SimulatorDriver()
            result = driver.execute_query(sql)
            return result or []
        except Exception as e:
            logger.debug(f"[RESILIENCE] SimulatorDriver falló: {e}")
            return []

    def _fmt_eur(self, value: Any) -> str:
        """Formatea un valor como euros en formato europeo."""
        try:
            v = float(value)
            return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            return str(value) if value is not None else "—"

    def _fmt_date(self, value: Any) -> str:
        """Formatea una fecha de forma legible."""
        if not value:
            return "—"
        s = str(value)
        # Formato YYYY-MM-DD → DD/MM/YYYY
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
        return s

    def _tipo_nombre(self, tipo: Any) -> str:
        """Devuelve el nombre legible de un tipo de documento."""
        try:
            return _TIPO_NOMBRES.get(int(tipo), f"Tipo {tipo}")
        except (TypeError, ValueError):
            return f"Tipo {tipo}"

    def _tiporetencion_nombre(self, tipo: Any) -> str:
        """Devuelve el nombre legible de un tipo de retención."""
        try:
            return _TIPORETENCION_NOMBRES.get(int(tipo), f"Tipo retención {tipo}")
        except (TypeError, ValueError):
            return f"Tipo retención {tipo}"

    # ─── Generadores de respuesta por dominio ────────────────────────────────

    def _build_certificaciones_response(
        self, question: str, data: Dict[str, List[Dict]]
    ) -> str:
        """Genera respuesta de calidad para preguntas de certificaciones."""
        lines = ["## 📋 Certificaciones por proyecto\n"]

        cert_data = data.get("cert_por_proyecto_resumen", [])
        detalle_data = data.get("cert_detalle", [])
        proyectos_data = data.get("proyectos_lista", [])

        if not cert_data and not detalle_data:
            if proyectos_data:
                lines.append(
                    f"Se encontraron **{len(proyectos_data)} proyectos** en la base de datos, "
                    f"pero ninguno tiene certificaciones (documentos con CODPROYECTO) registradas.\n"
                )
                lines.append("\n**Proyectos disponibles:**")
                for p in proyectos_data[:10]:
                    nombre = p.get("NOMBRE") or p.get("nombre") or "Sin nombre"
                    codigo = p.get("CODIGO") or p.get("codigo") or "—"
                    lines.append(f"- **{nombre}** (código: {codigo})")
            else:
                lines.append(
                    "No se encontraron proyectos ni certificaciones en la base de datos simulada.\n"
                    "Esto puede indicar que el simulador no tiene datos de proyectos cargados."
                )
            return "\n".join(lines)

        # Agrupar por proyecto
        proyectos: Dict[str, Dict] = {}
        for row in cert_data:
            cod = str(row.get("COD_PROYECTO") or row.get("cod_proyecto") or "")
            nombre = str(row.get("NOMBRE_PROYECTO") or row.get("nombre_proyecto") or cod)
            tipo = row.get("TIPO") or row.get("tipo")
            n = int(row.get("N_CERTIFICACIONES") or row.get("n_certificaciones") or 0)
            total = row.get("TOTAL_CERTIFICADO_EUR") or row.get("total_certificado_eur") or 0
            primera = row.get("PRIMERA") or row.get("primera") or ""
            ultima = row.get("ULTIMA") or row.get("ultima") or ""

            if cod not in proyectos:
                proyectos[cod] = {
                    "nombre": nombre,
                    "tipos": [],
                    "total_certs": 0,
                    "total_eur": 0.0,
                    "primera": primera,
                    "ultima": ultima,
                }
            proyectos[cod]["tipos"].append({
                "tipo": tipo,
                "n": n,
                "total": float(total) if total else 0.0,
            })
            proyectos[cod]["total_certs"] += n
            proyectos[cod]["total_eur"] += float(total) if total else 0.0
            if primera and (not proyectos[cod]["primera"] or primera < proyectos[cod]["primera"]):
                proyectos[cod]["primera"] = primera
            if ultima and ultima > proyectos[cod]["ultima"]:
                proyectos[cod]["ultima"] = ultima

        total_proyectos = len(proyectos)
        total_certs = sum(p["total_certs"] for p in proyectos.values())
        total_eur = sum(p["total_eur"] for p in proyectos.values())

        lines.append(
            f"Se encontraron **{total_proyectos} proyectos** con un total de "
            f"**{total_certs} certificaciones** por un importe total de "
            f"**{self._fmt_eur(total_eur)}**.\n"
        )

        for cod, proy in sorted(proyectos.items(), key=lambda x: x[1]["nombre"]):
            lines.append(f"\n### 🏗️ {proy['nombre']} (código: {cod})")
            lines.append(
                f"- **Total certificaciones:** {proy['total_certs']} "
                f"| **Importe total:** {self._fmt_eur(proy['total_eur'])}"
            )
            if proy["primera"]:
                lines.append(
                    f"- **Período:** {self._fmt_date(proy['primera'])} → "
                    f"{self._fmt_date(proy['ultima'])}"
                )
            for t in proy["tipos"]:
                tipo_nombre = self._tipo_nombre(t["tipo"])
                lines.append(
                    f"  - {tipo_nombre}: **{t['n']} docs** | {self._fmt_eur(t['total'])}"
                )

        # Añadir nota sobre tipos de documento
        lines.append(
            "\n> 💡 **Nota:** Las certificaciones son documentos vinculados a un proyecto "
            "(DOCCAB con CODPROYECTO). En JDDC, el tipo 3 = factura cliente (certificación "
            "estándar) y el tipo 51 = certificación específica de obra."
        )

        return "\n".join(lines)

    def _build_proyectos_response(
        self, question: str, data: Dict[str, List[Dict]]
    ) -> str:
        """Genera respuesta de calidad para preguntas de proyectos/obras."""
        lines = ["## 🏗️ Proyectos y obras\n"]

        proyectos_data = data.get("proyectos_lista", [])
        facturado_data = data.get("facturado_por_proyecto", [])

        if not proyectos_data:
            lines.append("No se encontraron proyectos en la base de datos simulada.")
            return "\n".join(lines)

        lines.append(f"Se encontraron **{len(proyectos_data)} proyectos**:\n")

        # Crear mapa de facturado por proyecto
        facturado_map: Dict[str, float] = {}
        for row in facturado_data:
            cod = str(row.get("CODPROYECTO") or row.get("codproyecto") or "")
            total = float(row.get("TOTAL_EUR") or row.get("total_eur") or 0)
            facturado_map[cod] = total

        for p in proyectos_data:
            cod = str(p.get("CODIGO") or p.get("codigo") or "")
            nombre = p.get("NOMBRE") or p.get("nombre") or "Sin nombre"
            cliente = p.get("CLIENTE") or p.get("cliente") or "—"
            inicio = self._fmt_date(p.get("FECHAINICIO") or p.get("fechainicio"))
            fin = self._fmt_date(p.get("FECHAFIN") or p.get("fechafin"))
            tipor = p.get("TIPORETENCION") or p.get("tiporetencion")
            porcr = p.get("PORCRETENCION") or p.get("porcretencion")
            facturado = facturado_map.get(cod, 0)

            lines.append(f"**{nombre}** (código: {cod})")
            lines.append(f"  - Cliente: {cliente}")
            lines.append(f"  - Período: {inicio} → {fin}")
            if tipor is not None:
                lines.append(
                    f"  - Retención: {self._tiporetencion_nombre(tipor)}"
                    + (f" ({porcr}%)" if porcr else "")
                )
            if facturado > 0:
                lines.append(f"  - Facturado/certificado: {self._fmt_eur(facturado)}")
            lines.append("")

        return "\n".join(lines)

    def _build_retenciones_response(
        self, question: str, data: Dict[str, List[Dict]]
    ) -> str:
        """Genera respuesta de calidad para preguntas de retenciones/avales."""
        lines = ["## 🔒 Retenciones y avales por proyecto\n"]

        ret_data = data.get("retenciones_por_proyecto", [])

        if not ret_data:
            lines.append("No se encontraron proyectos con retenciones en la base de datos.")
            return "\n".join(lines)

        # Agrupar por tipo de retención
        por_tipo: Dict[int, List[Dict]] = {}
        for row in ret_data:
            tipor = int(row.get("TIPORETENCION") or row.get("tiporetencion") or 0)
            if tipor not in por_tipo:
                por_tipo[tipor] = []
            por_tipo[tipor].append(row)

        lines.append(
            f"Se encontraron **{len(ret_data)} proyectos** con retención configurada:\n"
        )

        for tipor in sorted(por_tipo.keys()):
            nombre_tipo = self._tiporetencion_nombre(tipor)
            proyectos = por_tipo[tipor]
            lines.append(f"\n### Tipo {tipor}: {nombre_tipo} ({len(proyectos)} proyectos)")
            for p in proyectos[:10]:
                nombre = p.get("NOMBRE") or p.get("nombre") or "Sin nombre"
                porc = p.get("PORCRETENCION") or p.get("porcretencion") or 0
                dias = p.get("DIASDEVOLUCIONRETENCION") or p.get("diasdevolucionretencion") or "—"
                lines.append(f"  - **{nombre}**: {porc}% retención, {dias} días devolución")

        lines.append(
            "\n> 💡 **Tipos de retención JDDC:**\n"
            "> - Tipo 0: Sin retención\n"
            "> - Tipo 1: Aval bancario previo (antes de la obra)\n"
            "> - Tipo 2: Aval al finalizar la obra\n"
            "> - Tipo 3: Sin aval — el cliente paga al finalizar el período de garantía"
        )

        return "\n".join(lines)

    def _build_documentos_response(
        self, question: str, data: Dict[str, List[Dict]]
    ) -> str:
        """Genera respuesta de calidad para preguntas de documentos."""
        lines = ["## 📄 Documentos en la base de datos\n"]

        tipos_data = data.get("distribucion_tipos", [])
        anual_data = data.get("distribucion_anual", [])

        if not tipos_data:
            lines.append("No se encontraron documentos en la base de datos simulada.")
            return "\n".join(lines)

        total_docs = sum(int(r.get("N") or r.get("n") or 0) for r in tipos_data)
        total_eur = sum(float(r.get("TOTAL_EUR") or r.get("total_eur") or 0) for r in tipos_data)

        lines.append(
            f"La base de datos contiene **{total_docs:,} documentos** "
            f"por un importe total de **{self._fmt_eur(total_eur)}**.\n"
        )
        lines.append("**Distribución por tipo:**")
        for row in tipos_data:
            tipo = row.get("TIPO") or row.get("tipo")
            n = int(row.get("N") or row.get("n") or 0)
            total = float(row.get("TOTAL_EUR") or row.get("total_eur") or 0)
            media = float(row.get("MEDIA_EUR") or row.get("media_eur") or 0)
            nombre = self._tipo_nombre(tipo)
            lines.append(
                f"- **{nombre}** (tipo {tipo}): {n:,} docs | "
                f"{self._fmt_eur(total)} | media {self._fmt_eur(media)}"
            )

        if anual_data:
            lines.append("\n**Distribución anual:**")
            for row in anual_data[:5]:
                ano = row.get("ANO") or row.get("ano") or "—"
                n = int(row.get("N") or row.get("n") or 0)
                total = float(row.get("TOTAL_EUR") or row.get("total_eur") or 0)
                lines.append(f"- **{ano}**: {n:,} docs | {self._fmt_eur(total)}")

        return "\n".join(lines)

    def _build_articulos_response(
        self, question: str, data: Dict[str, List[Dict]]
    ) -> str:
        """Genera respuesta de calidad para preguntas de artículos/stock."""
        lines = ["## 📦 Artículos y stock\n"]

        art_data = data.get("top_articulos", [])
        fam_data = data.get("familias", [])

        if not art_data and not fam_data:
            lines.append("No se encontraron artículos en la base de datos simulada.")
            return "\n".join(lines)

        if art_data:
            lines.append(f"**Top artículos con stock ({len(art_data)} artículos):**")
            for a in art_data[:10]:
                nombre = a.get("NOMBRE") or a.get("nombre") or "Sin nombre"
                stock = a.get("STOCKARTICULO") or a.get("stockarticulo") or 0
                precio = a.get("PRECIOVENTA") or a.get("precioventa") or 0
                lines.append(
                    f"- **{nombre}**: stock {stock} uds | precio venta {self._fmt_eur(precio)}"
                )

        if fam_data:
            lines.append(f"\n**Familias de artículos ({len(fam_data)} familias):**")
            for f in fam_data[:10]:
                nombre = f.get("FAMILIA") or f.get("familia") or "Sin nombre"
                n = int(f.get("N_ARTICULOS") or f.get("n_articulos") or 0)
                precio = f.get("PRECIO_MEDIO") or f.get("precio_medio") or 0
                lines.append(
                    f"- **{nombre}**: {n} artículos | precio medio {self._fmt_eur(precio)}"
                )

        return "\n".join(lines)

    def _build_clientes_response(
        self, question: str, data: Dict[str, List[Dict]]
    ) -> str:
        """Genera respuesta de calidad para preguntas de clientes/proveedores."""
        lines = ["## 👥 Clientes\n"]

        cli_data = data.get("top_clientes", [])

        if not cli_data:
            lines.append("No se encontraron datos de clientes en la base de datos simulada.")
            return "\n".join(lines)

        total_eur = sum(float(r.get("TOTAL_EUR") or r.get("total_eur") or 0) for r in cli_data)
        lines.append(
            f"**Top {len(cli_data)} clientes** por facturación total "
            f"({self._fmt_eur(total_eur)} entre todos):\n"
        )
        for i, c in enumerate(cli_data, 1):
            nombre = c.get("NOMBRE") or c.get("nombre") or f"Cliente {c.get('CODCLIENTE', '—')}"
            n = int(c.get("N_DOCS") or c.get("n_docs") or 0)
            total = float(c.get("TOTAL_EUR") or c.get("total_eur") or 0)
            lines.append(f"{i}. **{nombre}**: {n} docs | {self._fmt_eur(total)}")

        return "\n".join(lines)

    def _build_general_response(
        self, question: str, data: Dict[str, List[Dict]]
    ) -> str:
        """Genera respuesta general cuando no se detecta dominio específico."""
        lines = ["## 📊 Resumen de la base de datos\n"]

        gen_data = data.get("resumen_general", [])

        if not gen_data:
            lines.append(
                "No se pudieron obtener datos de la base de datos simulada. "
                "Verifica que el simulador esté activo y tenga datos cargados."
            )
            return "\n".join(lines)

        total_docs = sum(int(r.get("N") or r.get("n") or 0) for r in gen_data)
        total_eur = sum(float(r.get("TOTAL_EUR") or r.get("total_eur") or 0) for r in gen_data)

        lines.append(
            f"La base de datos simulada contiene **{total_docs:,} documentos** "
            f"por un importe total de **{self._fmt_eur(total_eur)}**.\n"
        )
        lines.append("**Distribución por tipo de documento:**")
        for row in gen_data:
            tipo = row.get("TIPO") or row.get("tipo")
            n = int(row.get("N") or row.get("n") or 0)
            total = float(row.get("TOTAL_EUR") or row.get("total_eur") or 0)
            nombre = self._tipo_nombre(tipo)
            lines.append(f"- {nombre} (tipo {tipo}): {n:,} docs | {self._fmt_eur(total)}")

        lines.append(
            "\n> ⚠️ **Nota:** La IA no está disponible en este momento. "
            "Esta respuesta se generó automáticamente a partir de los datos del simulador. "
            "Para análisis más detallados, verifica que el servidor de IA esté activo."
        )

        return "\n".join(lines)

    # ─── Método principal ────────────────────────────────────────────────────

    async def generate_response(
        self, question: str, context: Optional[Dict] = None
    ) -> ResilienceResult:
        """
        Genera una respuesta de calidad cuando la IA no está disponible.

        Args:
            question: Pregunta del usuario en lenguaje natural
            context: Contexto adicional (db_params, conversation_history, etc.)

        Returns:
            ResilienceResult con la respuesta generada y métricas de calidad
        """
        result = ResilienceResult()

        try:
            # FASE 1: Detectar dominio
            domain, tables = self._detect_domain(question)
            result.domain = domain
            logger.info(f"[RESILIENCE] Dominio detectado: {domain} para pregunta: {question[:80]}")

            # FASE 2: Obtener SQLs para el dominio
            sqls = _SQLS_BY_DOMAIN.get(domain, _SQLS_BY_DOMAIN[_Domain.GENERAL])
            result.sqls_executed = len(sqls)

            # FASE 3: Ejecutar SQLs
            data: Dict[str, List[Dict]] = {}
            for sql_def in sqls:
                sql_id = sql_def["id"]
                sql = sql_def["sql"]
                try:
                    rows = await self._execute_sql(sql)
                    if rows:
                        data[sql_id] = rows
                        result.sqls_successful += 1
                        result.data_rows += len(rows)
                        result.used_simulator = True
                        logger.info(
                            f"[RESILIENCE] SQL '{sql_id}': {len(rows)} filas"
                        )
                    else:
                        logger.debug(f"[RESILIENCE] SQL '{sql_id}': sin resultados")
                except Exception as e:
                    result.errors.append(f"{sql_id}: {e}")
                    logger.debug(f"[RESILIENCE] SQL '{sql_id}' falló: {e}")

            # FASE 4: Generar respuesta según dominio
            if domain == _Domain.CERTIFICACIONES:
                result.response = self._build_certificaciones_response(question, data)
            elif domain == _Domain.PROYECTOS_OBRAS:
                result.response = self._build_proyectos_response(question, data)
            elif domain == _Domain.RETENCIONES:
                result.response = self._build_retenciones_response(question, data)
            elif domain == _Domain.DOCUMENTOS:
                result.response = self._build_documentos_response(question, data)
            elif domain == _Domain.ARTICULOS_STOCK:
                result.response = self._build_articulos_response(question, data)
            elif domain == _Domain.CLIENTES_PROVEEDORES:
                result.response = self._build_clientes_response(question, data)
            elif domain == _Domain.FINANCIERO:
                result.response = self._build_general_response(question, data)
            else:
                result.response = self._build_general_response(question, data)

            # FASE 5: Evaluar calidad
            if result.data_rows > 0 and result.sqls_successful > 0:
                result.quality = "high" if result.data_rows >= 5 else "medium"
            else:
                result.quality = "low"

            # Añadir nota de modo sin IA si la respuesta tiene datos
            if result.quality in ("high", "medium"):
                result.response += (
                    "\n\n---\n"
                    "⚠️ *Respuesta generada automáticamente (modo sin IA). "
                    "El servidor de IA no estaba disponible. "
                    "Los datos provienen del simulador de base de datos JDDC.*"
                )

        except Exception as e:
            logger.error(f"[RESILIENCE] Error en generate_response: {e}")
            result.response = (
                "⚠️ El servidor de IA no está disponible en este momento y no se pudieron "
                "obtener datos del simulador. Por favor, verifica que:\n"
                "1. El servidor Qwen3 30B esté activo (http://jddcia.local)\n"
                "2. El simulador de BD esté habilitado en Configuración → BD Simulada\n"
                "3. La red LAN esté disponible"
            )
            result.quality = "low"
            result.errors.append(str(e))

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════════

_engine_instance: Optional[AdaptiveResilienceEngine] = None


def get_resilience_engine(
    sql_executor: Optional[Callable] = None
) -> AdaptiveResilienceEngine:
    """
    Devuelve el singleton del AdaptiveResilienceEngine.
    Si se pasa sql_executor, crea una nueva instancia con ese executor.
    """
    global _engine_instance
    if sql_executor is not None:
        # Con executor específico → nueva instancia (no singleton)
        return AdaptiveResilienceEngine(sql_executor=sql_executor)
    if _engine_instance is None:
        _engine_instance = AdaptiveResilienceEngine()
    return _engine_instance
