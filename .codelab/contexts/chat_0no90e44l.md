**ESTADO**: Paso 1 de 5.
**EXPLICACIÓN**: Configuramos la estructura básica del proyecto para una buena organización y escalabilidad.
**ACCIÓN**:
```python
// ./interjddcia/config.py
import os
import sys

# Ruta de archivos
DIRECCION_ARCHIVOS = sys.argv[1] if len(sys.argv) > 1 else '.'

# Ruta de firmas
DIRECCION_FIRMAS = sys.argv[2] if len(sys.argv) > 2 else 'firmas'

# Período de actualización
PERIODO_ACTUALIZACION = 24

# Configuración de la aplicación
CONFIG_APP = {
    'ruta_archivos': DIRECCION_ARCHIVOS,
    'ruta_firmas': DIRECCION_FIRMAS,
    'periodo_actualizacion': PERIODO_ACTUALIZACION
}

print(CONFIG_APP)
```
Para continuar, ejecuta el comando con las rutas deseadas, por ejemplo: `python interjddcia/config.py "C:/Ruta/Archivos" "C:/Ruta/Firmas"`.
[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/config.py \"C:/Ruta/Archivos\" \"C:/Ruta/Firmas\"","label":"Ejecutar Configuración"}]]
¡Listo! Dale al botón de abajo para ejecutarlo.