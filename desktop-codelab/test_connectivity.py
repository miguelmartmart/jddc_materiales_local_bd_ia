#!/usr/bin/env python3
"""Test de conectividad para AI Code Lab.

Verifica:
  1. Backend local (puerto 8002) accesible
  2. IA LAN (10.13.79.31) accesible directamente
  3. Diagnóstico completo vía /debug/ping-ai
  4. Generación básica end-to-end

No requiere historial ni context; es un test de "¿está todo encendido?".
"""

import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND_URL = "http://localhost:8002"
LAN_AI_URL  = "http://10.13.79.31/api/vlm/v1"
LAN_CREDS   = ("admin", "aistack2026")


def test_local_backend():
    """Backend FastAPI accesible en localhost:8002."""
    print("\n[TEST 1] Backend local — localhost:8002")
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        data = resp.json()
        print(f"  Status: {resp.status_code} | mode: {data.get('mode')} | models: {data.get('lan_models_count')}")
        print(f"  ✅ Backend OK" if resp.status_code == 200 else f"  ❌ Unexpected status")
        return resp.status_code == 200
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_remote_ai_direct():
    """IA LAN accesible directamente en 10.13.79.31."""
    print("\n[TEST 2] Servidor IA LAN — 10.13.79.31")
    try:
        resp = requests.get(f"{LAN_AI_URL}/models", auth=LAN_CREDS, timeout=8)
        data = resp.json()
        models = [m.get("id") for m in data.get("data", [])]
        print(f"  Status: {resp.status_code} | Modelos: {models[:2]}")
        print(f"  ✅ IA LAN accesible" if resp.status_code == 200 else f"  ❌ IA no responde")
        return resp.status_code == 200
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_ping_ai_endpoint():
    """Diagnóstico vía /debug/ping-ai del backend."""
    print("\n[TEST 3] Diagnóstico /debug/ping-ai")
    try:
        resp = requests.get(f"{BACKEND_URL}/debug/ping-ai", timeout=15)
        data = resp.json()
        ip_status = data.get("ip_status")
        print(f"  IP directa: {data.get('ip_url')} → {ip_status}")
        print(f"  mDNS:       {data.get('mdns_url')} → {data.get('mdns_status')}")
        if data.get("recommendation"):
            print(f"  Recomendación: {data.get('recommendation')}")
        ok = resp.status_code == 200 and ip_status == 200
        print(f"  {'✅ IA alcanzable por IP' if ok else '❌ IA no alcanzable'}")
        return ok
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_generation():
    """Generación end-to-end vía backend."""
    print("\n[TEST 4] Generación end-to-end")
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/generate",
            json={
                "prompt": "Responde solo con la palabra 'ok'.",
                "model_id": "jddcia-qwen3-30b-ip",
            },
            timeout=120,
        )
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("response", "")
            model = data.get("model", "")
            print(f"  Respuesta: {text[:150]}")
            print(f"  Modelo: {model}")
            print(f"  ✅ Generación OK")
            return len(text) > 0
        else:
            print(f"  ❌ Error: {resp.text[:200]}")
            return False
    except requests.exceptions.Timeout:
        print("  ❌ Timeout — la IA tardó más de 2 minutos")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = [
        ("Backend local (puerto 8002)", test_local_backend()),
        ("IA LAN directa (10.13.79.31)", test_remote_ai_direct()),
        ("Diagnóstico /debug/ping-ai", test_ping_ai_endpoint()),
        ("Generación end-to-end", test_generation()),
    ]

    print("\n" + "="*50)
    print("RESUMEN DE CONECTIVIDAD:")
    for name, result in results:
        print(f"  {'✅ PASS' if result else '❌ FAIL'}: {name}")

    all_pass = all(r for _, r in results)
    print(f"\n{'✅ Todo OK' if all_pass else '❌ Hay fallos — revisa logs arriba'}")
    sys.exit(0 if all_pass else 1)
