"""
helpers.py — Funciones reutilizables para tests e2e.

PROPÓSITO:
  Centralizar helpers comunes a todos los tests e2e.
  Evitar duplicación de código entre test_preguntas_1tabla.py,
  test_preguntas_2tablas.py y test_regresiones.py.

INDEPENDENCIA:
  - Sin IPs hardcodeadas.
  - Sin referencias a tablas específicas de la BD.
  - Funciona con cualquier BD Firebird.
"""

import json
import re
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)
_TRACES_FILE = _LOGS_DIR / "e2e_traces.jsonl"


# ─── Auditor de red ───────────────────────────────────────────────────────────

class NetworkAuditInterceptor:
    """
    Intercepta socket.connect durante un bloque with.
    Registra todas las conexiones y detecta tráfico a internet.
    Reutilizable en cualquier test que necesite auditoría de red.
    """

    def __init__(self, allowed_networks: List[str]):
        self._allowed = allowed_networks
        self._original = None
        self.connections: List[Dict] = []
        self.violations: List[Dict] = []

    def __enter__(self):
        self._original = socket.socket.connect
        interceptor = self

        def _audited(sock, address):
            host = address[0] if isinstance(address, tuple) else str(address)
            port = address[1] if isinstance(address, tuple) else 0
            is_lan = interceptor._is_lan(host)
            entry = {"host": host, "port": port, "is_lan": is_lan,
                     "ts": datetime.now().isoformat()}
            interceptor.connections.append(entry)
            if not is_lan:
                interceptor.violations.append(entry)
            return interceptor._original(sock, address)

        socket.socket.connect = _audited
        return self

    def __exit__(self, *_):
        if self._original:
            socket.socket.connect = self._original

    def _is_lan(self, host: str) -> bool:
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = host
        return any(ip.startswith(p) for p in self._allowed)

    def assert_no_internet(self, test_name: str = ""):
        assert not self.violations, (
            f"🚨 VIOLACIÓN DE PRIVACIDAD en '{test_name}': "
            f"datos enviados a internet → {self.violations}"
        )


# ─── Helper principal de preguntas ───────────────────────────────────────────

async def ask_and_trace(
    chat_svc,
    question: str,
    ctx: Dict,
    test_name: str,
    allowed_networks: List[str],
    expected_keywords: Optional[List[str]] = None,
    forbidden_keywords: Optional[List[str]] = None,
    max_len: int = 10000,
) -> Tuple[str, Dict]:
    """
    Ejecuta una pregunta real con auditoría de red y trazas completas.

    Args:
        chat_svc:           ChatService real
        question:           Pregunta en lenguaje natural
        ctx:                Contexto de chat (metaglass o web)
        test_name:          Nombre del test (para logs)
        allowed_networks:   Prefijos de red LAN permitidos
        expected_keywords:  Palabras que DEBEN aparecer en la respuesta
        forbidden_keywords: Palabras que NO deben aparecer en la respuesta
        max_len:            Longitud máxima de la respuesta

    Returns:
        (respuesta_str, traza_dict)
    """
    start = time.time()

    with NetworkAuditInterceptor(allowed_networks) as auditor:
        resp = await chat_svc.process_message(question, ctx)

    elapsed = time.time() - start
    resp_str = str(resp) if resp else ""

    trace = {
        "test":      test_name,
        "question":  question,
        "response":  resp_str[:500],
        "elapsed_s": round(elapsed, 2),
        "lan_conns": len([c for c in auditor.connections if c["is_lan"]]),
        "inet_conns": len(auditor.violations),
        "ts":        datetime.now().isoformat(),
    }

    # Guardar traza
    with open(_TRACES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")

    # Verificaciones de privacidad
    auditor.assert_no_internet(test_name)

    # Verificaciones de respuesta
    assert resp_str, f"Respuesta vacía para: '{question}'"
    assert len(resp_str) <= max_len, (
        f"Respuesta demasiado larga ({len(resp_str)} > {max_len}) para: '{question}'"
    )

    if expected_keywords:
        for kw in expected_keywords:
            assert kw.lower() in resp_str.lower(), (
                f"Keyword '{kw}' no encontrado en respuesta para '{question}': '{resp_str[:200]}'"
            )

    if forbidden_keywords:
        for kw in forbidden_keywords:
            assert kw not in resp_str, (
                f"Keyword prohibido '{kw}' encontrado en respuesta para '{question}'"
            )

    return resp_str, trace


# ─── Helpers de aserción ─────────────────────────────────────────────────────

def assert_has_number(resp: str, context: str = ""):
    """La respuesta debe contener al menos un número."""
    assert re.search(r'\d+', resp), (
        f"No hay número en la respuesta{' (' + context + ')' if context else ''}: '{resp[:200]}'"
    )


def assert_no_markdown(resp: str):
    """La respuesta no debe tener Markdown (para MetaGlass TTS)."""
    assert "**" not in resp, f"Markdown negrita en respuesta: '{resp[:100]}'"
    assert "```" not in resp, f"Bloque código en respuesta: '{resp[:100]}'"
    assert "##" not in resp, f"Encabezado en respuesta: '{resp[:100]}'"


def assert_response_valid(resp: str, max_len: int, allow_markdown: bool = True):
    """Verifica que la respuesta es válida."""
    assert resp, "Respuesta vacía"
    assert len(resp) > 3, f"Respuesta demasiado corta: '{resp}'"
    assert len(resp) <= max_len, f"Respuesta demasiado larga: {len(resp)} > {max_len}"
    if not allow_markdown:
        assert_no_markdown(resp)
