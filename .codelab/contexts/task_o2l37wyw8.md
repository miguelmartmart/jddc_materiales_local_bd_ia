**Estado**: Paso 2 de 5.
**Explicación**: Ahora, necesitamos crear la estructura básica del proyecto para comenzar a implementar las funcionalidades de detección de troyanos.

**Acción**:
```python
// interjddcia/main.py
import sys
import os
from config import Config

# Instancia de configuración
config = Config()

# Crear carpetas si no existen
if not os.path.exists(config.get_ruta_archivos()):
    os.makedirs(config.get_ruta_archivos())

if not os.path.exists(config.get_ruta_firmas()):
    os.makedirs(config.get_ruta_firmas())

print("Estructura básica del proyecto creada.")
```

**Siguiente Paso**: Ahora que tenemos la estructura básica del proyecto, podemos comenzar a implementar las funcionalidades de detección de troyanos. 
[[NEXT_ACTION:{"type":"chat_message","content":"Crear el archivo database.py para almacenar la información de los troyanos","label":"Crear Base de Datos"}]]
¡Listo! Dale al botón de abajo para crear la base de datos.