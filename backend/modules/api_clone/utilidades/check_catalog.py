"""Comprobaciones globales de lectura y ayudas para usuarios no técnicos."""

GROUPS = [
    {"id": "estado", "nombre": "Proyecto y estado", "ayuda": "Distingue tener un proyecto registrado de poder trabajar en él. Un proyecto cerrado puede seguir siendo necesario para consultar su histórico."},
    {"id": "pertenencia", "nombre": "Pertenencia de los datos", "ayuda": "Comprueba referencias a proyectos y técnicos. Que un código exista no demuestra que la persona eligiera la obra correcta."},
    {"id": "disponibilidad", "nombre": "Datos disponibles", "ayuda": "Explica cuándo un cero se debe a datos incompletos o al filtro de cantidades, en lugar de ausencia de actividad."},
    {"id": "prevision", "nombre": "Real frente a previsto", "ayuda": "El trabajo presupuestado o previsto debe distinguirse del realizado. No se deben sumar ambos como si fueran ejecución."},
    {"id": "fechas", "nombre": "Fechas y coherencia", "ayuda": "Detecta fechas ausentes o contradictorias. Una incidencia puede tener una explicación de negocio; no se corrige automáticamente."},
    {"id": "totales", "nombre": "Totales y cobertura", "ayuda": "Para confiar en un total hay que conocer qué líneas incluye, los ajustes y si se han consultado todos los resultados."},
]


def counted(id, group, name, explanation, example, action, source, condition, cohort=""):
    return {"id": id, "grupo": group, "nombre": name, "descripcion": explanation,
            "ejemplo": example, "accion": action,
            "sql": f"SELECT COUNT(*) AS TOTAL, COALESCE(SUM(CASE WHEN {condition} THEN 1 ELSE 0 END),0) AS INCIDENCIAS FROM {source}" + (f" WHERE {cohort}" if cohort else "")}


def pending(id, group, name, explanation, example, action):
    return {"id": id, "grupo": group, "nombre": name, "descripcion": explanation,
            "ejemplo": example, "accion": action, "sql": None}


CHECKS = [
    counted("CHK-001", "pertenencia", "Líneas con proyecto identificable",
            "Busca líneas sin código de proyecto o cuyo código no existe. Las líneas sin proyecto se señalan para clasificar su origen, no se atribuyen a otra obra.",
            "Una línea puede existir en la base de datos y no indicar a qué obra pertenece.",
            "Revisar el origen de las líneas señaladas en SQL Obras antes de incluirlas en un informe por proyecto.",
            "OBRALIN ol", "ol.CODPROYECTO IS NULL OR NOT EXISTS (SELECT 1 FROM PROYECTOS p WHERE p.CODIGO=ol.CODPROYECTO)"),
    counted("CHK-002", "pertenencia", "Referencias de técnicos existentes",
            "Comprueba que los códigos informados en líneas de mano de obra existan en el catálogo de recursos. No comprueba la asignación laboral.",
            "Una línea menciona el técnico 123, pero ese código ya no existe en el catálogo.",
            "Contrastar las referencias con el catálogo y el parte original.",
            "OBRALIN ol", "NOT EXISTS (SELECT 1 FROM RECURSO r WHERE r.CODIGO=ol.CODRECURSO)", "ol.TIPOBC3=10 AND ol.CODRECURSO IS NOT NULL"),
    counted("CHK-003", "disponibilidad", "Tipos de línea reconocidos",
            "Señala tipos vacíos o distintos de los actualmente conocidos: 10, 11, 20, 24 y 30. Un tipo nuevo puede ser válido, pero necesita revisión.",
            "Una actualización del programa añade una nueva clase de material.",
            "Confirmar el significado del nuevo tipo antes de clasificar sus importes.",
            "OBRALIN", "TIPOBC3 IS NULL OR TIPOBC3 NOT IN (10,11,20,24,30)"),
    counted("CHK-004", "totales", "Cantidades negativas y ajustes",
            "Localiza cantidades negativas. Pueden ser devoluciones o correcciones legítimas; no son errores por sí mismas.",
            "Se devuelve material y se registra una cantidad negativa.",
            "Comprobar que resumen, ranking y detalle traten igual los ajustes.",
            "OBRALIN", "CANTIDAD<0"),
    counted("CHK-005", "fechas", "Orden de inicio y fin",
            "Compara únicamente proyectos con ambas fechas informadas. No comprueba cuándo se imputó cada trabajo.",
            "La fecha final de una obra aparece antes de su inicio.",
            "Contrastar las dos fechas con la ficha del proyecto.",
            "PROYECTOS", "FECHAFIN<FECHAINICIO", "FECHAFIN IS NOT NULL AND FECHAINICIO IS NOT NULL"),
    counted("CHK-006", "totales", "Cantidad positiva sin coste",
            "Busca líneas de mano de obra con cantidad positiva y coste vacío o cero. Incluye previsiones; no certifica horas realizadas.",
            "Hay una cantidad registrada pero no una tarifa o coste asociado.",
            "Revisar la tarifa y si la línea es prevista o realizada.",
            "OBRALIN", "COSTE IS NULL OR COSTE=0", "TIPOBC3=10 AND CANTIDAD>0"),
    counted("CHK-007", "estado", "Indicador de fin de obra informado",
            "Comprueba que FINOBRA tenga uno de los valores conocidos F o T. Un valor F no descarta otros bloqueos.",
            "Un proyecto tiene el indicador vacío y no podemos interpretar su cierre.",
            "Completar o confirmar el estado en SQL Obras.",
            "PROYECTOS", "FINOBRA IS NULL OR FINOBRA NOT IN ('F','T')"),
    pending("CHK-008", "estado", "Permiso para nuevas imputaciones",
            "Todavía no hay una regla validada que combine borradores, bloqueos, permisos y cierre de ejercicio.",
            "Una obra no finalizada puede estar bloqueada para nuevas imputaciones.",
            "Consultar la elegibilidad en SQL Obras. Este informe no autoriza escrituras."),
    counted("CHK-009", "disponibilidad", "Mano de obra excluida por cantidad",
            "Detecta líneas no previstas, con proyecto informado, que el filtro CANTIDAD>0 oculta. Un cero en pantalla no demuestra ausencia de técnicos.",
            "Existe una línea con técnico informado, pero CANTIDAD vale cero.",
            "Revisar los campos de cantidad y el parte original. No sustituir automáticamente cantidades por horas.",
            "OBRALIN", "CANTIDAD IS NULL OR CANTIDAD<=0", "TIPOBC3=10 AND ESPREVISION=0 AND CODPROYECTO IS NOT NULL"),
    counted("CHK-010", "prevision", "Indicador real o previsto reconocido",
            "Comprueba que cada línea declare el indicador conocido 0 o 1. No comprueba que las consultas los separen.",
            "Una línea sin indicador no puede clasificarse con seguridad.",
            "Confirmar la clasificación antes de sumar ejecución y previsión.",
            "OBRALIN", "ESPREVISION IS NULL OR ESPREVISION NOT IN (0,1)"),
    pending("CHK-011", "prevision", "Separación en los informes",
            "Las consultas actuales de utilidades no separan de forma validada ejecución y previsión. Los resultados no certifican horas reales.",
            "Una cantidad prevista puede aparecer dentro de un total presentado como realizado.",
            "Separar las consultas y contrastarlas con el informe de SQL Obras antes de certificar cifras."),
    counted("CHK-012", "fechas", "Fecha de línea disponible",
            "Señala líneas sin fecha propia. La fecha de cabecera puede representar otro hecho y no debe usarse automáticamente.",
            "Una línea tiene fecha de alta pero no fecha del trabajo.",
            "Confirmar qué fecha usa el informe de negocio.",
            "OBRALIN", "FECHA IS NULL"),
    pending("CHK-013", "totales", "Informe completo y conciliado",
            "No se ha contrastado el conjunto completo con un informe independiente en una misma copia de datos. Las listas limitadas no demuestran cobertura total.",
            "Ver 15 proyectos no significa que solo existan 15. Dos sumas iguales pueden contener líneas distintas.",
            "Comparar claves completas, páginas y totales con SQL Obras sobre una misma instantánea."),
]


# Relaciones lógicas comprobadas aunque no exista una FK declarada en Firebird.
CHECKS += [
    counted("CHK-014", "pertenencia", "Cabecera de línea existente",
            "Comprueba CODCAB frente a OBRACAB.CODIGO, incluidos valores nulos.",
            "Una línea apunta a una cabecera eliminada.", "Contrastar la cabecera original; no reasignar automáticamente.",
            "OBRALIN l", "l.CODCAB IS NULL OR NOT EXISTS (SELECT 1 FROM OBRACAB c WHERE c.CODIGO=l.CODCAB)"),
    counted("CHK-015", "pertenencia", "Proyecto de cabecera y línea coincidentes",
            "Compara proyectos explícitos de cabeceras y líneas vinculadas. La igualdad no certifica el parte original.",
            "La cabecera corresponde a A pero la línea indica B.", "Contrastar ambas referencias con SQL Obras.",
            "OBRALIN l JOIN OBRACAB c ON c.CODIGO=l.CODCAB", "l.CODPROYECTO<>c.CODPROYECTO",
            "l.CODPROYECTO IS NOT NULL AND c.CODPROYECTO IS NOT NULL"),
    counted("CHK-016", "pertenencia", "Proyecto de cabecera existente",
            "Comprueba la referencia de proyecto de cada cabecera.", "Una cabecera apunta a una obra desconocida.",
            "Clasificar las cabeceras sin proyecto y corregir referencias tras contraste.",
            "OBRACAB c", "c.CODPROYECTO IS NULL OR NOT EXISTS (SELECT 1 FROM PROYECTOS p WHERE p.CODIGO=c.CODPROYECTO)"),
    counted("CHK-017", "disponibilidad", "Mano de obra con recurso informado",
            "Detecta mano de obra sin recurso, incluso con cantidad cero o prevista.", "Una línea MO no indica quién la realizó.",
            "No contabilizar líneas sin persona como técnicos distintos.", "OBRALIN", "CODRECURSO IS NULL", "TIPOBC3=10"),
    counted("CHK-018", "prevision", "Previsión de cabecera y línea coincidentes",
            "Contrasta indicadores no nulos entre cabecera y línea.", "Cabecera prevista con línea marcada como real.",
            "Confirmar qué indicador gobierna el informe antes de sumar.",
            "OBRALIN l JOIN OBRACAB c ON c.CODIGO=l.CODCAB", "l.ESPREVISION<>c.ESPREVISION",
            "l.ESPREVISION IS NOT NULL AND c.ESPREVISION IS NOT NULL"),
]
for table, fields, ident in [
    ("PROYECTOS", ["CODIGO"], 19), ("RECURSO", ["CODIGO"], 21),
    ("OBRACAB", ["CODIGO"], 23), ("OBRALIN", ["CODCAB", "CODIGO"], 25),
]:
    key = ",".join(fields)
    CHECKS.append(counted(f"CHK-{ident:03}", "pertenencia", f"Clave completa no nula: {table}",
        f"Comprueba los componentes {key}; no sustituye la inspección de la PK declarada.",
        "Una parte de la clave está vacía.", "Revisar esquema y origen de las filas.", table,
        " OR ".join(f"{field} IS NULL" for field in fields)))
    CHECKS.append(counted(f"CHK-{ident+1:03}", "pertenencia", f"Unicidad de clave completa: {table}",
        f"Agrupa por {key}; cuenta grupos duplicados, no filas afectadas.",
        "Dos filas comparten toda la clave.", "Revisar restricciones antes de confiar en read o JOIN.",
        f"(SELECT {key}, COUNT(*) AS N FROM {table} GROUP BY {key}) K", "K.N>1"))
CHECKS.append(counted("CHK-027", "pertenencia", "CODIGO de línea ambiguo sin cabecera",
    "Cuenta códigos repetidos entre cabeceras. Pueden ser válidos: read debe usar la clave compuesta.",
    "Las cabeceras A y B tienen ambas una línea 1.", "No identificar OBRALIN usando solo CODIGO.",
    "(SELECT CODIGO, COUNT(*) AS N FROM OBRALIN GROUP BY CODIGO) K", "K.N>1"))
