## Estado Actual
La aplicación de escritorio para detectar troyanos en el equipo ha comenzado a tomar forma con la creación de un script básico para escanear archivos en una carpeta y calcular su hash.

## Descripción del Proyecto
El proyecto consiste en desarrollar una aplicación de escritorio que pueda detectar troyanos en un equipo. La aplicación escaneará los archivos en una carpeta especificada, calculará sus hashes y los comparará con una base de datos de troyanos conocidos para identificar posibles amenazas.

## Código Fuente
```python
// interjddcia/detector_troyanos.py
import os
import hashlib

def scan_files(directory):
    # Función para escanear archivos en una carpeta
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                # Calculamos el hash del archivo
                with open(file_path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                print(f"Archivo: {file_path}, Hash: {file_hash}")
            except Exception as e:
                print(f"Error al escanear {file_path}: {e}")

# Ejemplo de uso
scan_files(".")
```

## Detalles Técnicos
- Se ha utilizado la biblioteca `os` para interactuar con el sistema de archivos y la biblioteca `hashlib` para calcular los hashes de los archivos.
- La función `scan_files` recibe un directorio como parámetro y escanea todos los archivos dentro de él y sus subdirectorios.

## Created Files
- `detector_troyanos.py`: Script Python que contiene la lógica para escanear archivos y calcular sus hashes.

## Resumen y Próximos Pasos
Se ha logrado crear un script básico que escanea archivos y calcula sus hashes. El próximo paso es implementar la lógica para comparar estos hashes con una base de datos de troyanos conocidos y alertar al usuario si se encuentra una coincidencia.

[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/detector_troyanos.py","label":"Ejecutar Script de Detección"}]]
¡Listo! Dale al botón de abajo para ejecutar el script y ver el resultado.