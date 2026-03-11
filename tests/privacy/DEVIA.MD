# DEVIA: tests/privacy — Tests de Auditoría de Privacidad

```json
{
  "capa": "privacy",
  "descripcion": "Tests que garantizan que NINGÚN dato sale a internet. Auditoría formal de privacidad.",
  "hereda_de": "tests/DEVIA.MD",

  "ficheros": {
    "test_network_audit.py":   "Intercepta socket.connect y verifica que todo es LAN",
    "test_settings_privacy.py":"Verifica que settings no tiene URLs de internet configuradas",
    "test_lan_detection.py":   "Verifica la detección correcta de IPs LAN vs internet"
  },

  "mecanismo": {
    "interceptor": "NetworkAuditInterceptor parchea socket.socket.connect en tiempo de ejecución",
    "resultado":   "Si se detecta conexión a internet → AssertionError inmediato con detalle",
    "log":         "logs/network_audit.log registra TODAS las conexiones con timestamp y host",
    "verificacion":"grep 'INTERNET' logs/network_audit.log → debe estar vacío"
  },

  "independencia": {
    "sin_hardcode":  "Las IPs permitidas se leen de test.properties (ALLOWED_NETWORKS)",
    "portabilidad":  "Funciona en cualquier red LAN. Cambiar ALLOWED_NETWORKS si la subred es diferente.",
    "autodeteccion": "La subred se detecta automáticamente si QWEN3_HOST=auto"
  },

  "ejecutar": ".venv/Scripts/pytest tests/privacy/ -v -s",
  "verificacion_manual": "grep 'INTERNET' bots/interjddcia/logs/network_audit.log"
}
```
