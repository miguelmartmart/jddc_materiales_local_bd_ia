"""
chat_voice_interpreter.py — Interpretacion determinista para clientes de voz.

RESPONSABILIDAD:
  Convertir resultados de BD a lenguaje natural SIN llamar a la IA.
  Usado por las gafas Meta Ray-Ban y cualquier cliente de voz.

PRINCIPIO:
  Los datos ya estan en 'results'. Solo hay que formatearlos.
  Esto es 100% determinista, rapido (<1ms) y sin dependencias externas.

BENEFICIO:
  Elimina la segunda llamada a IA (~20s), reduciendo el tiempo total
  de ~42s a ~22s y evitando el timeout de 60s en Android.

RESILIENCIA:
  - Nunca lanza excepciones: siempre devuelve un string valido
  - Maneja resultados vacios, None, tipos inesperados
  - Fallback gracioso en cada caso
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Campos prioritarios para mostrar en voz (orden de preferencia)
VOICE_PRIORITY_FIELDS = [
    'NOMBRE', 'DESCRIPCION', 'DESCRIPCIONCORTA', 'RAZONSOCIAL',
    'NOMBRE_CLIENTE', 'NOMBRE_ARTICULO', 'TITULO', 'CONCEPTO',
    'NUMERO', 'CODIGO', 'REFERENCIA', 'REF'
]

# Palabras clave para detectar tipo de consulta COUNT
COUNT_KEYWORDS = ['cuántos', 'cuantos', 'total', 'número', 'numero', 'cantidad']
SUM_KEYWORDS   = ['suma', 'total', 'importe', 'facturado']

# Entidades reconocidas para respuestas de COUNT
ENTITY_KEYWORDS = {
    'artículo':  ['artículo', 'articulo', 'producto'],
    'cliente':   ['cliente'],
    'factura':   ['factura'],
    'proveedor': ['proveedor'],
    'pedido':    ['pedido'],
    'albarán':   ['albarán', 'albaran'],
}


def _format_number(val: Any) -> str:
    """Formatea un numero al estilo europeo (punto miles, coma decimales)."""
    try:
        if isinstance(val, float):
            return f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return str(val)
    except Exception:
        return str(val)


def _detect_entity(msg_lower: str) -> Optional[str]:
    """Detecta la entidad mencionada en el mensaje para respuestas de COUNT."""
    for entity, keywords in ENTITY_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return entity
    return None


def _is_monetary_value(key: str, val: Any) -> bool:
    """Detecta si un campo es un importe monetario (no un COUNT entero)."""
    monetary_keys = {"TOTAL", "IMPORTE", "BASE", "TOTALIVA", "SUMA", "PRECIO",
                     "DESCUENTO", "MARGEN", "COSTE", "FACTURADO"}
    if key.upper() in monetary_keys:
        return True
    # Si el valor es float con decimales, probablemente es monetario
    if isinstance(val, float) and val != int(val):
        return True
    return False


def _interpret_single_value(message: str, key: str, val: Any) -> str:
    """
    Interpreta un resultado de una sola fila y una sola columna.

    PRIORIDAD:
      1. Si el campo es monetario (TOTAL, IMPORTE, etc.) → "El total es X euros"
      2. Si el mensaje pregunta por cantidad (cuántos) → "Hay N entidades"
      3. Fallback → "El resultado es X"
    """
    msg_lower = message.lower()

    # 1. Campos monetarios tienen prioridad — evita confundir TOTAL con COUNT
    if _is_monetary_value(key, val):
        return f"El total es {_format_number(val)} euros."

    # 2. Preguntas de conteo (cuántos, número de...)
    if any(w in msg_lower for w in COUNT_KEYWORDS):
        val_str = _format_number(val)
        entity = _detect_entity(msg_lower)
        if entity:
            plural = {
                'artículo': 'artículos', 'cliente': 'clientes',
                'factura': 'facturas', 'proveedor': 'proveedores',
                'pedido': 'pedidos', 'albarán': 'albaranes'
            }.get(entity, f"{entity}s")
            return f"Hay {val_str} {plural} en la base de datos."
        return f"El resultado es {val_str}."

    # 3. Fallback
    if isinstance(val, float):
        return f"El resultado es {_format_number(val)} euros."
    return f"El resultado es {val}."


def _interpret_single_row(row: Dict[str, Any]) -> str:
    """Interpreta una sola fila con multiples columnas."""
    parts = []
    for key, val in row.items():
        if val is None:
            continue
        key_clean = key.replace('_', ' ').title()
        parts.append(f"{key_clean}: {_format_number(val) if isinstance(val, float) else val}")

    if parts:
        return "El registro encontrado tiene: " + ", ".join(parts) + "."
    return "Se encontró un registro pero sin datos relevantes."


def _find_display_key(results: List[Dict[str, Any]]) -> Optional[str]:
    """Encuentra el campo mas relevante para mostrar en voz."""
    if not results:
        return None
    available_keys = list(results[0].keys())
    for priority_key in VOICE_PRIORITY_FIELDS:
        for avail_key in available_keys:
            if avail_key.upper() == priority_key:
                return avail_key
    return available_keys[0] if available_keys else None


def _interpret_multiple_rows(message: str, results: List[Dict[str, Any]]) -> str:
    """Interpreta multiples filas extrayendo el campo mas relevante."""
    n = len(results)
    display_key = _find_display_key(results)

    if not display_key:
        return f"Se encontraron {n} resultados."

    values = [
        str(row.get(display_key, '')).strip()
        for row in results
        if row.get(display_key) is not None and str(row.get(display_key, '')).strip()
    ]

    if not values:
        return f"Se encontraron {n} resultados pero sin datos de texto."

    if len(values) == 1:
        return f"El resultado es: {values[0]}."
    elif len(values) == 2:
        return f"Los dos resultados son: {values[0]} y {values[1]}."
    elif len(values) <= 5:
        return f"Los {len(values)} resultados son: {', '.join(values[:-1])} y {values[-1]}."
    else:
        primeros = values[:3]
        return (
            f"Encontré {n} resultados. Los primeros son: "
            f"{', '.join(primeros)}, y así sucesivamente."
        )


def interpret_results_for_voice(
    message: str,
    results: List[Dict[str, Any]],
    sql_query: str = ""
) -> str:
    """
    Interpreta resultados de BD de forma DETERMINISTA para clientes de voz.

    RESILIENCIA:
      - Nunca lanza excepciones
      - Maneja None, listas vacias, tipos inesperados
      - Siempre devuelve un string valido

    Args:
        message:   Pregunta original del usuario
        results:   Lista de dicts con los resultados de la BD
        sql_query: SQL ejecutado (para contexto, no se usa en la interpretacion)

    Returns:
        String en lenguaje natural listo para TTS
    """
    try:
        # Validar entrada
        if not results:
            return "No encontré ningún resultado para tu consulta."

        if not isinstance(results, list):
            logger.warning(f"[VoiceInterpreter] results no es lista: {type(results)}")
            return "Se obtuvo un resultado pero en formato inesperado."

        n = len(results)

        # Caso 1: Una fila, una columna (COUNT/SUM/AVG/MAX/MIN)
        if n == 1 and isinstance(results[0], dict) and len(results[0]) == 1:
            try:
                key = list(results[0].keys())[0]
                val = results[0][key]
                return _interpret_single_value(message, key, val)
            except Exception as e:
                logger.warning(f"[VoiceInterpreter] Error en caso 1: {e}")
                return f"El resultado es: {results[0]}."

        # Caso 2: Una fila, multiples columnas
        if n == 1 and isinstance(results[0], dict):
            try:
                return _interpret_single_row(results[0])
            except Exception as e:
                logger.warning(f"[VoiceInterpreter] Error en caso 2: {e}")
                return f"Se encontró un registro: {results[0]}."

        # Caso 3: Multiples filas
        try:
            return _interpret_multiple_rows(message, results)
        except Exception as e:
            logger.warning(f"[VoiceInterpreter] Error en caso 3: {e}")
            return f"Se encontraron {n} resultados."

    except Exception as e:
        # Fallback absoluto: nunca debe llegar aqui
        logger.error(f"[VoiceInterpreter] Error inesperado: {e}", exc_info=True)
        return f"Se obtuvieron {len(results) if results else 0} resultados."


def clean_for_tts(text: str) -> str:
    """
    Limpia el texto de formato Markdown para que el TTS de las gafas Meta
    lo lea de forma natural, sin decir 'asterisco', 'almohadilla', etc.

    Se aplica SIEMPRE a todas las respuestas del backend para clientes de voz.

    RESILIENCIA:
      - Nunca lanza excepciones
      - Si el input no es string, lo convierte
      - Devuelve siempre un string valido

    Args:
        text: Texto con posible formato Markdown

    Returns:
        Texto limpio listo para TTS
    """
    try:
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        if not text:
            return ""

        # 1. Negrita y cursiva: **texto** → texto, *texto* → texto
        text = re.sub(r'\*{1,3}([^*\n]+?)\*{1,3}', r'\1', text)
        text = re.sub(r'_{1,3}([^_\n]+?)_{1,3}', r'\1', text)

        # 2. Codigo inline: `texto` → texto
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # 3. Bloques de codigo: ```...``` → eliminar
        text = re.sub(r'```[\s\S]*?```', '', text, flags=re.MULTILINE)

        # 4. Encabezados: ### Titulo → Titulo
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # 5. Listas numeradas: "1. Elemento" → "1, Elemento"
        text = re.sub(r'^(\d+)\.\s+', r'\1, ', text, flags=re.MULTILINE)

        # 6. Listas con guion o asterisco: "- Elemento" → "Elemento"
        text = re.sub(r'^[\-\*\•]\s+', '', text, flags=re.MULTILINE)

        # 7. Links Markdown: [texto](url) → texto
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # 8. Imagenes Markdown: ![alt](url) → eliminar
        text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)

        # 9. Lineas horizontales: --- o *** → eliminar
        text = re.sub(r'^[\-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)

        # 10. Caracteres especiales que el TTS lee mal
        text = re.sub(r'[^\w\s\.,;:!¡?¿\-\(\)\/€%ñÑáéíóúÁÉÍÓÚüÜ\n]', ' ', text)

        # 11. Multiples espacios → un espacio
        text = re.sub(r'  +', ' ', text)

        # 12. Multiples lineas vacias → una sola
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    except Exception as e:
        logger.error(f"[clean_for_tts] Error inesperado: {e}", exc_info=True)
        # Fallback: devolver el texto original sin procesar
        try:
            return str(text).strip()
        except Exception:
            return ""
