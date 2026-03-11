# DEVIA CONFIG CONTEXT: AI Models & Providers
# Configuración de modelos IA, providers y gestión de fallback.

```json
{
  "module": "backend.core.config",
  "description": "Gestión de modelos IA, providers y configuración del sistema.",
  "last_updated": "03/03/2026",

  "ai_mode_actual": {
    "mode": "LOCAL_ONLY",
    "ai_local_only": true,
    "description": "SOLO Qwen3 VL 30B en red LAN JDDC. Fallback multi-modelo DESHABILITADO.",
    "config_file": "backend/modules/chat/config.json"
  },

  "local_models": {
    "primary": {
      "id": "jddcia-qwen3-30b-ip",
      "url": "http://192.168.0.36/api/vlm/v1",
      "model": "unified-main",
      "score": 95,
      "auth": "Basic YWRtaW46YWlzdGFjazIwMjY=",
      "note": "IP directa — USAR ESTA. jddcia.local no resuelve en Windows."
    },
    "fallback_mdns": {
      "id": "jddcia-qwen3-30b",
      "url": "http://jddcia.local/api/vlm/v1",
      "model": "unified-main",
      "score": 50,
      "note": "mDNS — solo funciona si Bonjour/Avahi está activo en el PC"
    }
  },

  "key_files": {
    "jddcia_models.json": "IPs, scores y stats de modelos locales Qwen3. Editar aquí si cambia la IP.",
    "ai_providers_config.json": "Configuración de todos los providers (Groq, Gemini, OpenAI, etc.)",
    "model_manager.py": "Carga y gestiona modelos. Lee jddcia_models.json en cada petición.",
    "settings.py": "Settings globales del sistema"
  },

  "change_ip_server": {
    "description": "Si el servidor IA cambia de IP (actualmente 192.168.0.36):",
    "steps": [
      "1. Editar jddcia_models.json → campo base_url del modelo jddcia-qwen3-30b-ip",
      "2. El cambio surte efecto en la siguiente petición (sin reiniciar)"
    ]
  },

  "timeout": {
    "httpx_timeout": "20s",
    "file": "backend/drivers/ai/jddcia_provider.py",
    "note": "Reducido de 60s a 20s para fallback rápido cuando vLLM está ocupado"
  },

  "related_devia": [
    "bots/interjddcia/DEVIA.MD (documentación principal)",
    "backend/modules/chat/DEVIA.MD (módulo chat)"
  ]
}
```
