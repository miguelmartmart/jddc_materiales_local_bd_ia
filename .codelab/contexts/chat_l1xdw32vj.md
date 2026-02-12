¡Hola! Soy tu compañero de programación. Vamos a empezar.

**ESTADO**: Paso 1 de 1
**EXPLICACIÓN**: Necesitamos ejecutar el script de monitoreo para verificar si el sistema está funcionando correctamente.
**ACCIÓN**:
```python
// cibrseg/monitor_resources.py
import os
import subprocess

def monitor_resources():
    try:
        process = subprocess.Popen(['psutil', 'cpu_percent'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            print("Uso de CPU: %d%%" % process.cpu_percent())
        else:
            print("Error al monitorear el uso de CPU: %s" % stderr.decode())
    except FileNotFoundError:
        print("El comando 'psutil' no se encuentra. Asegúrate de que esté instalado.")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")

monitor_resources()
```

¡Listo! Dale al botón de abajo para ejecutar el script.
