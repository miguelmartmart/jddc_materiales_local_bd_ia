**ESTADO**: Paso 1 de 2.
**EXPLICACIÓN**: Se ha iniciado el proceso para detectar troyanos en una carpeta dada.
**ACCIÓN**:
```python
// ./detector_troyanos.py
import os
import sys

def detectar_troyanos(carpeta):
    # Lista de extensiones sospechosas
    extensiones_sospechosas = ['.exe', '.dll', '.zip']
    
    # Recorrer todos los archivos en la carpeta
    for root, dirs, files in os.walk(carpeta):
        for file in files:
            # Comprobar si el archivo tiene una extensión sospechosa
            if os.path.splitext(file)[1].lower() in extensiones_sospechosas:
                print(f"Archivo sospechoso encontrado: {os.path.join(root, file)}")

# Carpeta a escanear
if len(sys.argv) > 1:
    carpeta = sys.argv[1]
else:
    carpeta = '.'

detectar_troyanos(carpeta)
```
[[NEXT_ACTION:{"type":"run_command","content":"python detector_troyanos.py \"C:/Ruta/Al/Carpeta\"","label":"Ejecutar Detector de Troyanos"}]]
¡Listo! Dale al botón de abajo para ejecutarlo.