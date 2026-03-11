"""
conftest.py raíz del proyecto interjddcia.

Añade el directorio raíz al sys.path para que los imports
del tipo 'from backend.modules...' funcionen correctamente en los tests.

También establece variables de entorno mínimas para que pydantic-settings
pueda instanciar Settings() sin errores durante la carga de módulos.
"""

import sys
import os

# Añadir el directorio raíz del proyecto al path de Python
sys.path.insert(0, os.path.dirname(__file__))

# Forzar variables de entorno mínimas para tests antes de que
# pydantic-settings intente leer el entorno del sistema.
# Esto evita errores como DEBUG=WARN (valor no booleano) en CI/entornos locales.
os.environ["DEBUG"] = "false"
os.environ.setdefault("DB_NAME", "")
os.environ.setdefault("APP_ENV", "test")
