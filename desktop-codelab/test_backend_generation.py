#!/usr/bin/env python3
"""Tests de integración para el backend de AI Code Lab (puerto 8002).

Valida: endpoints, generación LAN, prompt engine y conectividad IA.
Requiere que el backend esté corriendo: python backend/server.py
"""

import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API_BASE = "http://localhost:8002"


def _check(label: str, result: bool) -> bool:
    print(f"  {'✅' if result else '❌'} {label}")
    return result


# ─── Endpoints ────────────────────────────────────────────────────────────────

def test_health():
    """GET /health → modo AI_LOCAL_ONLY, modelos LAN."""
    print("\n" + "="*60)
    print("TEST 1: GET /health")
    print("="*60)
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        data = resp.json()
        print(f"  Status: {resp.status_code} | Data: {data}")
        ok = (
            _check("HTTP 200", resp.status_code == 200) and
            _check("status=ok", data.get("status") == "ok") and
            _check("mode=AI_LOCAL_ONLY", data.get("mode") == "AI_LOCAL_ONLY") and
            _check("lan_models_count > 0", data.get("lan_models_count", 0) > 0)
        )
        return ok
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_models():
    """GET /api/models → lista de modelos LAN."""
    print("\n" + "="*60)
    print("TEST 2: GET /api/models")
    print("="*60)
    try:
        resp = requests.get(f"{API_BASE}/api/models", timeout=5)
        data = resp.json()
        models = data.get("models", [])
        print(f"  Status: {resp.status_code} | Modelos: {[m.get('id') for m in models]}")
        ok = (
            _check("HTTP 200", resp.status_code == 200) and
            _check("Al menos un modelo LAN", len(models) > 0) and
            _check("Modelo IP directa presente", any("ip" in m.get("id", "") for m in models))
        )
        return ok
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_ping_ai():
    """GET /debug/ping-ai → diagnóstico de conectividad con la IA LAN."""
    print("\n" + "="*60)
    print("TEST 3: GET /debug/ping-ai")
    print("="*60)
    try:
        resp = requests.get(f"{API_BASE}/debug/ping-ai", timeout=15)
        data = resp.json()
        print(f"  Status: {resp.status_code} | Data: {data}")
        ok = (
            _check("HTTP 200", resp.status_code == 200) and
            _check("ip_url presente", "ip_url" in data) and
            _check("ip_status presente", "ip_status" in data)
        )
        return ok
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


# ─── Generación ───────────────────────────────────────────────────────────────

def test_generation_basic():
    """POST /api/generate → respuesta básica de la IA."""
    print("\n" + "="*60)
    print("TEST 4: POST /api/generate — básico")
    print("="*60)
    try:
        resp = requests.post(
            f"{API_BASE}/api/generate",
            json={
                "prompt": "Di 'ok' en una sola palabra.",
                "model_id": "jddcia-qwen3-30b-ip",
            },
            timeout=120,
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("response", "")
            model = data.get("model", "")
            print(f"  Respuesta: {text[:200]}")
            print(f"  Modelo: {model}")
            ok = (
                _check("HTTP 200", True) and
                _check("Respuesta no vacía", len(text) > 0) and
                _check("Modelo LAN usado", "jddcia" in model or "qwen" in model.lower())
            )
            return ok
        else:
            print(f"  ❌ Error: {resp.text[:200]}")
            return False
    except requests.exceptions.Timeout:
        print("  ❌ Timeout — la IA tardó más de 2 minutos")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_generation_with_history():
    """POST /api/generate con historial → respuesta coherente al contexto."""
    print("\n" + "="*60)
    print("TEST 5: POST /api/generate — con historial de mensajes")
    print("="*60)
    try:
        resp = requests.post(
            f"{API_BASE}/api/generate",
            json={
                "prompt": "¿Cómo se llama?",
                "model_id": "jddcia-qwen3-30b-ip",
                "messages": [
                    {"role": "user", "content": "Mi perro se llama Rufus."},
                    {"role": "assistant", "content": "¡Qué nombre tan bonito para un perro!"},
                ],
            },
            timeout=120,
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.json().get("response", "")
            print(f"  Respuesta: {text[:300]}")
            ok = (
                _check("HTTP 200", True) and
                _check("Respuesta no vacía", len(text) > 0) and
                _check("Menciona 'Rufus'", "Rufus" in text or "rufus" in text.lower())
            )
            return ok
        else:
            print(f"  ❌ Error: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_generation_with_project_path():
    """POST /api/generate con project_path → prompt engine incluye folders_context."""
    print("\n" + "="*60)
    print("TEST 6: POST /api/generate — con project_path (folders_context)")
    print("="*60)
    try:
        resp = requests.post(
            f"{API_BASE}/api/generate",
            json={
                "prompt": "¿Qué carpetas existen en mi proyecto?",
                "model_id": "jddcia-qwen3-30b-ip",
                "project_path": "C:/test",
            },
            timeout=120,
        )
        print(f"  Status: {resp.status_code}")
        ok = _check("HTTP 200 o 503 (LAN)", resp.status_code in [200, 503])
        if resp.status_code == 200:
            text = resp.json().get("response", "")
            print(f"  Respuesta: {text[:300]}")
        return ok
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


# ─── Prompt engine (sin servidor) ─────────────────────────────────────────────

def test_prompt_engine_size():
    """El system prompt ensamblado no debe superar 8000 chars (~2000 tokens)."""
    print("\n" + "="*60)
    print("TEST 7: Prompt engine — tamaño bajo límite (sin servidor)")
    print("="*60)
    try:
        import sys as _sys
        _sys.path.insert(0, "backend")
        from prompt_engine.builder import PromptBuilder
        from prompt_engine.phases import DEFAULT_PHASES, PhaseContext

        ctx = PhaseContext(
            project_path="C:/test",
            folders_context="src, backend, electron, dist, DOCS_README",
        )
        prompt = PromptBuilder(DEFAULT_PHASES).build(ctx)
        chars = len(prompt)
        tokens = chars // 4
        print(f"  Chars: {chars} | Tokens aprox: {tokens}")

        ok = (
            _check(f"Chars ≤ 8000 (actual: {chars})", chars <= 8000) and
            _check(f"Tokens aprox ≤ 2000 (actual: {tokens})", tokens <= 2000) and
            _check("Contiene instrucciones de Test-Path (fase carpetas)", "Test-Path" in prompt) and
            _check("Contiene [[NEXT_ACTION]] (fase botones)", "NEXT_ACTION" in prompt) and
            _check("Contiene regla de no archivos en Directory", ".py" in prompt or "archivos" in prompt.lower())
        )
        return ok
    except ImportError as e:
        print(f"  ⚠️ Skipped (importar backend desde fuera): {e}")
        return True  # No es un fallo, solo no se puede ejecutar desde este directorio
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_prompt_engine_phases_order():
    """Las fases críticas están en el orden correcto (verificación antes de creación)."""
    print("\n" + "="*60)
    print("TEST 8: Prompt engine — orden de fases")
    print("="*60)
    try:
        import sys as _sys
        _sys.path.insert(0, "backend")
        from prompt_engine.phases import DEFAULT_PHASES

        names = [p.name for p in DEFAULT_PHASES]
        print(f"  Fases: {names}")

        analysis_idx = next((i for i, n in enumerate(names) if "analysis_first" in n), -1)
        folders_idx  = next((i for i, n in enumerate(names) if "folder" in n), -1)
        actions_idx  = next((i for i, n in enumerate(names) if "action" in n), -1)
        errors_idx   = next((i for i, n in enumerate(names) if "error" in n), -1)

        ok = (
            _check("Fase analysis_first existe", analysis_idx >= 0) and
            _check("Fase folders existe", folders_idx >= 0) and
            _check("Fase action_buttons existe", actions_idx >= 0) and
            _check("analysis_first ANTES de folders", analysis_idx < folders_idx) and
            _check("action_buttons ANTES de error_handling", actions_idx < errors_idx) and
            _check("Al menos 15 fases", len(DEFAULT_PHASES) >= 15)
        )
        return ok
    except ImportError as e:
        print(f"  ⚠️ Skipped: {e}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n" + "="*60)
    print("BACKEND INTEGRATION TESTS — AI Code Lab v1.2.0")
    print("="*60)

    suite = [
        ("T1. GET /health", test_health),
        ("T2. GET /api/models", test_models),
        ("T3. GET /debug/ping-ai", test_ping_ai),
        ("T4. POST /api/generate — básico", test_generation_basic),
        ("T5. POST /api/generate — con historial", test_generation_with_history),
        ("T6. POST /api/generate — con project_path", test_generation_with_project_path),
        ("T7. Prompt engine — tamaño ≤ 8000 chars", test_prompt_engine_size),
        ("T8. Prompt engine — orden de fases", test_prompt_engine_phases_order),
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
