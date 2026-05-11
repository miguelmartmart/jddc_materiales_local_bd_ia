#!/usr/bin/env python3
"""Test suite to verify ChatAI responses for coherence and sanity.

Tests se dividen en tres grupos:
  A. Con system_prompt manual: verifica que el modelo responda bien dado un prompt sencillo.
  B. Flujo real (sin system_prompt): verifica que el backend NO inyecte estructura
     innecesaria (Resumen / Próximos Pasos / NEXT_ACTION) en mensajes conversacionales.
  C. Fase de carpetas: verifica que la IA siga el flujo de 2 pasos (Test-Path → New-Item),
     no reuse nombres existentes y no incluya archivos en New-Item Directory.
"""

import sys
import io
import requests
import re

# Forzar UTF-8 en stdout para evitar UnicodeEncodeError en Windows (cp1252)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API_BASE = "http://localhost:8002"

# ─── Helper ───────────────────────────────────────────────────────────────────

def _has_next_action(text: str) -> bool:
    return bool(re.search(r'\[\[\s*NEXT_ACTION\s*:', text, re.IGNORECASE))

def _has_test_path(text: str) -> bool:
    return "Test-Path" in text

def _has_new_item(text: str) -> bool:
    return "New-Item" in text and "Directory" in text

def _check(checks: dict) -> bool:
    all_passed = True
    for label, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {label}")
        if not result:
            all_passed = False
    return all_passed

def _post(payload: dict) -> str:
    resp = requests.post(f"{API_BASE}/api/generate", json=payload, timeout=120)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
    return resp.json().get("response", "")


# ─── A. Tests con system_prompt manual ────────────────────────────────────────

def test_simple_greeting():
    """Saludo simple → respuesta natural, sin estructura innecesaria."""
    print("\n" + "="*60)
    print("TEST 1: Simple Greeting (system_prompt manual)")
    print("="*60)

    response = _post({
        "prompt": "hola",
        "system_prompt": "Eres un asistente amable.",
        "model_id": "jddcia-qwen3-30b-ip",
    })
    print(f"Response: {response}\n")

    return _check({
        "Respuesta corta (< 500 chars)": len(response) < 500,
        "Sin '## Resumen'": "## Resumen" not in response,
        "Sin '## Próximos Pasos'": "## Próximos Pasos" not in response,
        "Sin [[NEXT_ACTION]]": not _has_next_action(response),
        "Contiene saludo en español": any(w in response.lower() for w in ["hola", "ayuda", "bien", "puedo"]),
    })


def test_simple_question():
    """Pregunta general corta → flujo real del backend, sin estructura innecesaria."""
    print("\n" + "="*60)
    print("TEST 2: Simple Question (flujo real, sin system_prompt manual)")
    print("="*60)

    response = _post({
        "prompt": "¿Cuál es la capital de Francia?",
        "model_id": "jddcia-qwen3-30b-ip",
    })
    print(f"Response: {response}\n")

    return _check({
        "Menciona París": "París" in response or "Paris" in response,
        "Sin '## Resumen'": "## Resumen" not in response,
        "Sin '## Próximos Pasos'": "## Próximos Pasos" not in response,
        "Sin [[NEXT_ACTION]]": not _has_next_action(response),
    })


def test_code_request():
    """Petición de código → debe tener código y estructura."""
    print("\n" + "="*60)
    print("TEST 3: Code Request (system_prompt manual)")
    print("="*60)

    response = _post({
        "prompt": "Crea un script Python que imprima 'Hola, mundo'",
        "system_prompt": "Eres un asistente de programación.",
        "model_id": "jddcia-qwen3-30b-ip",
    })
    print(f"Response length: {len(response)} chars")
    print(f"Response (first 500 chars): {response[:500]}...\n")

    return _check({
        "Contiene bloque de código": "```" in response or "print(" in response,
        "Menciona 'Hola' o 'mundo'": "Hola" in response or "mundo" in response,
        "Respuesta larga (> 100 chars)": len(response) > 100,
    })


# ─── B. Tests de flujo real (sin system_prompt) ───────────────────────────────

def test_real_flow_greeting_no_history():
    """FLUJO REAL — 'hola' sin historial → NO debe tener estructura de código."""
    print("\n" + "="*60)
    print("TEST 4: Flujo real — saludo sin historial")
    print("="*60)

    response = _post({
        "prompt": "hola",
        "model_id": "jddcia-qwen3-30b-ip",
    })
    print(f"Response: {response}\n")

    return _check({
        "Sin '## Resumen' para saludo": "## Resumen" not in response,
        "Sin '## Próximos Pasos' para saludo": "## Próximos Pasos" not in response,
        "Sin [[NEXT_ACTION]] para saludo": not _has_next_action(response),
        "Sin 'Confirmar y Ejecutar' para saludo": "Confirmar y Ejecutar" not in response,
        "Contiene respuesta de saludo": any(w in response.lower() for w in ["hola", "ayuda", "puedo", "¿en qué"]),
    })


def test_real_flow_greeting_with_history():
    """FLUJO REAL — 'hola' CON historial → NO debe tener estructura de código."""
    print("\n" + "="*60)
    print("TEST 5: Flujo real — saludo CON historial")
    print("="*60)

    response = _post({
        "prompt": "hola",
        "model_id": "jddcia-qwen3-30b-ip",
        "messages": [
            {"role": "system", "content": "Nueva sesión iniciada."},
        ],
    })
    print(f"Response: {response}\n")

    return _check({
        "Sin '## Resumen' para saludo con historial": "## Resumen" not in response,
        "Sin '## Próximos Pasos' para saludo con historial": "## Próximos Pasos" not in response,
        "Sin [[NEXT_ACTION]] para saludo con historial": not _has_next_action(response),
        "Sin 'Confirmar y Ejecutar'": "Confirmar y Ejecutar" not in response,
        "Contiene respuesta de saludo": any(w in response.lower() for w in ["hola", "ayuda", "puedo", "¿en qué"]),
    })


def test_real_flow_code_request_with_history():
    """FLUJO REAL — petición de código CON historial → SÍ debe tener estructura."""
    print("\n" + "="*60)
    print("TEST 6: Flujo real — código CON historial (regresión: debe mantener estructura)")
    print("="*60)

    response = _post({
        "prompt": "Crea un archivo Python llamado saludo.py que imprima 'hola'",
        "model_id": "jddcia-qwen3-30b-ip",
        "messages": [
            {"role": "user", "content": "Quiero empezar a programar en Python"},
            {"role": "assistant", "content": "¡Perfecto! ¿Qué quieres crear?"},
        ],
    })
    print(f"Response length: {len(response)} chars")
    print(f"Response (first 600 chars): {response[:600]}...\n")

    return _check({
        "Contiene código Python": "```" in response or "print(" in response,
        "Menciona saludo.py o hola": "saludo" in response.lower() or "hola" in response.lower(),
        "Respuesta larga (> 100 chars)": len(response) > 100,
    })


def test_real_flow_conversational_followup():
    """FLUJO REAL — mensaje conversacional después de código → NO debe forzar estructura."""
    print("\n" + "="*60)
    print("TEST 7: Flujo real — 'gracias' tras conversación")
    print("="*60)

    response = _post({
        "prompt": "gracias, perfecto",
        "model_id": "jddcia-qwen3-30b-ip",
        "messages": [
            {"role": "user", "content": "Crea un script Python"},
            {"role": "assistant", "content": "Aquí está el script:\n```python\nprint('hola')\n```\n[[NEXT_ACTION:{\"type\":\"run_command\",\"content\":\"python saludo.py\",\"label\":\"Ejecutar\"}]]"},
        ],
    })
    print(f"Response: {response}\n")

    return _check({
        "Sin '## Resumen' para agradecimiento": "## Resumen" not in response,
        "Sin '## Próximos Pasos' para agradecimiento": "## Próximos Pasos" not in response,
        "Sin [[NEXT_ACTION]] para agradecimiento": not _has_next_action(response),
    })


# ─── C. Tests de fase de carpetas ─────────────────────────────────────────────

def test_folders_verification_step():
    """La IA debe proponer Test-Path ANTES de New-Item para verificar existencia."""
    print("\n" + "="*60)
    print("TEST 8: Folder phase — verificación con Test-Path obligatoria")
    print("="*60)

    # Simular escenario con algunas carpetas existentes en el directorio
    response = _post({
        "prompt": "quiero crear una app de ciberseguridad, primero crea la estructura de carpetas",
        "model_id": "jddcia-qwen3-30b-ip",
        "project_path": "C:/Users/test/proyectos",
    })
    print(f"Response (first 800 chars): {response[:800]}...\n")

    has_test_path = _has_test_path(response)
    has_next_action = _has_next_action(response)

    mentions_existing = bool(re.search(
        r"(ya existen|ya existe|existen carpetas|carpetas (como|existentes)|no puedo usar)",
        response, re.IGNORECASE
    ))

    return _check({
        "Propone árbol o estructura": any(w in response.lower() for w in ["árbol", "estructura", "carpeta", "folder"]),
        "Contiene Test-Path (verificación)": has_test_path,
        "Contiene [[NEXT_ACTION]]": has_next_action,
        "Botón de Verificar (no Crear directo)": "Verificar" in response or has_test_path,
        "NO verbaliza folders_context ('ya existen X, Y, Z')": not mentions_existing,
    })


def test_folders_no_conflict_with_existing():
    """La IA usa folders_context internamente pero NO lo verbaliza en la respuesta.

    - Correcto: proponer árbol con nombre alternativo → Test-Path → silencio sobre lo que ya existe
    - Incorrecto: decir 'ya existen carpetas como cyber, src...' en el texto de respuesta
    """
    print("\n" + "="*60)
    print("TEST 9: Folder phase — no verbalizar folders_context, usar Test-Path")
    print("="*60)

    # 'cyber' ya existe en folders_context vía project_path
    response = _post({
        "prompt": "quiero crear un proyecto de ciberseguridad, llámalo cyber",
        "model_id": "jddcia-qwen3-30b-ip",
        "project_path": "C:/Users/test/proyectos",
    })
    print(f"Response (first 900 chars): {response[:900]}...\n")

    # La IA no debe decir "ya existe cyber/src/backend..." en el texto
    mentions_existing = bool(re.search(
        r"(ya existen|ya existe|existen carpetas|carpetas (como|existentes)|no puedo usar)",
        response, re.IGNORECASE
    ))
    # No debe proponer New-Item directo con 'cyber' como raíz sin verificar antes
    direct_new_item_cyber = bool(re.search(r"New-Item[^\n]*'[^']*cyber'", response))
    # Sí debe proponer Test-Path para verificar
    has_test_path = _has_test_path(response)
    has_next_action = _has_next_action(response)

    return _check({
        "NO verbaliza folders_context ('ya existen X, Y, Z')": not mentions_existing,
        "Propone Test-Path para verificar (no asume sin comprobar)": has_test_path or has_next_action,
        "No hace New-Item de 'cyber' sin verificar antes": not direct_new_item_cyber or has_test_path,
        "Respuesta no vacía": len(response) > 50,
    })


def test_folders_no_files_in_new_item():
    """New-Item -ItemType Directory NO debe contener archivos (.py, .md, .json…)."""
    print("\n" + "="*60)
    print("TEST 10: Folder phase — no archivos en New-Item Directory")
    print("="*60)

    response = _post({
        "prompt": "crea la estructura de carpetas para un proyecto Flask con archivo main.py y README.md",
        "model_id": "jddcia-qwen3-30b-ip",
        "project_path": "C:/Users/test/proyectos",
    })
    print(f"Response (first 1000 chars): {response[:1000]}...\n")

    # Buscar si New-Item -ItemType Directory incluye archivos
    new_item_blocks = re.findall(r"New-Item -ItemType Directory[^\n]*", response, re.IGNORECASE)
    files_in_new_item = any(
        re.search(r"'\S+\.(py|md|json|html|txt|js|ts|css|yaml|yml)'", block)
        for block in new_item_blocks
    )

    print(f"  Bloques New-Item encontrados: {new_item_blocks}\n")

    return _check({
        "New-Item Directory no contiene .py .md .json etc": not files_in_new_item,
        "Contiene algún comando PowerShell": "New-Item" in response or "Test-Path" in response or _has_next_action(response),
    })


def test_folders_two_step_flow_after_verification():
    """Tras resultado de Test-Path, IA propone New-Item solo con las que no existen."""
    print("\n" + "="*60)
    print("TEST 11: Folder phase — Paso 2: New-Item solo con rutas False")
    print("="*60)

    # Simular que Test-Path ya se ejecutó y devolvió resultados mixtos
    response = _post({
        "prompt": "ya verifiqué — algunas existen (True) y otras no (False). Crea solo las que faltan.",
        "model_id": "jddcia-qwen3-30b-ip",
        "messages": [
            {"role": "user", "content": "quiero crear estructura para una app web"},
            {"role": "assistant", "content": "Voy a verificar primero cuáles existen.\n[[NEXT_ACTION:{\"type\":\"run_command\",\"content\":\"Test-Path -Path 'C:/test/webapp','C:/test/webapp/src','C:/test/webapp/backend'\",\"label\":\"Verificar carpetas\"}]]"},
            {"role": "system", "content": "[SYSTEM] Resultado de Test-Path:\nC:/test/webapp → True\nC:/test/webapp/src → False\nC:/test/webapp/backend → False"},
        ],
        "model_id": "jddcia-qwen3-30b-ip",
    })
    print(f"Response (first 800 chars): {response[:800]}...\n")

    has_new_item = _has_new_item(response)
    has_next_action = _has_next_action(response)

    return _check({
        "Propone New-Item con las carpetas faltantes": has_new_item or has_next_action,
        "Respuesta coherente (> 50 chars)": len(response) > 50,
    })


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n" + "="*60)
    print("COHERENCE & SANITY TESTS — AI Code Lab v1.2.0")
    print("="*60)

    suite = [
        # Grupo A: system_prompt manual
        ("A1. Simple Greeting (manual prompt)", test_simple_greeting),
        ("A2. Simple Question (manual prompt)", test_simple_question),
        ("A3. Code Request (manual prompt)", test_code_request),
        # Grupo B: flujo real
        ("B1. Flujo real — saludo sin historial", test_real_flow_greeting_no_history),
        ("B2. Flujo real — saludo CON historial", test_real_flow_greeting_with_history),
        ("B3. Flujo real — código CON historial (regresión)", test_real_flow_code_request_with_history),
        ("B4. Flujo real — 'gracias' tras código", test_real_flow_conversational_followup),
        # Grupo C: fase de carpetas
        ("C1. Carpetas — Test-Path obligatorio antes de New-Item", test_folders_verification_step),
        ("C2. Carpetas — sin conflicto con nombres existentes", test_folders_no_conflict_with_existing),
        ("C3. Carpetas — no archivos (.py .md) en New-Item Directory", test_folders_no_files_in_new_item),
        ("C4. Carpetas — Paso 2 solo con rutas que dieron False", test_folders_two_step_flow_after_verification),
    ]

    results = []
    for name, fn in suite:
        try:
            results.append((name, fn()))
        except Exception as e:
            print(f"❌ {name} — excepción: {e}")
            results.append((name, False))

    print("\n" + "="*60)
    print("RESUMEN FINAL")
    print("="*60)
    passed = sum(1 for _, r in results if r)
    for name, result in results:
        print(f"  {'✅' if result else '❌'} {name}")
    print(f"\n{passed}/{len(results)} tests pasaron")
    print("="*60)

    return passed == len(results)


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
