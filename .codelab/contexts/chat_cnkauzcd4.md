## Estado 
Paso 1 de 5.
## Explicación 
Se ha iniciado la creación de la estructura básica de la aplicación de escritorio para detectar troyanos.

## Acción
```python
// interjddcia/backend/detect_trojan.py
import hashlib
import os
import sys

def scan_files(directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            with open(file_path, 'rb') as file:
                file_hash = hashlib.sha256(file.read()).hexdigest()
                print(f"Archivo: {filename}, Hash: {file_hash}")

def main():
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = '.'
    scan_files(directory)

if __name__ == "__main__":
    main()
```

## Resumen 
La aplicación de escritorio para detectar troyanos ha sido iniciada con la creación de la estructura básica y la función para escanear archivos en un directorio.

## Detalles Técnicos
- Se ha utilizado la biblioteca `hashlib` para calcular los hashes de los archivos.
- La función `scan_files` recorre los archivos en el directorio especificado y calcula su hash.
- El directorio por defecto es el actual (`.`), pero se puede especificar otro directorio como parámetro al ejecutar el script.

## Archivos Creados
- `interjddcia/backend/detect_trojan.py`

## Resumen y Próximos Pasos
La aplicación ha sido iniciada con la creación de la estructura básica y la función para escanear archivos. Los próximos pasos incluyen agregar funcionalidad para comparar los hashes generados con una base de datos de hashes conocidos de troyanos y malware, y mejorar la interfaz de usuario para una mejor experiencia del usuario.

[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/backend/detect_trojan.py \"C:/Ruta\"","label":"Ejecutar Script"}]]
¡Listo! Dale al botón de abajo para ejecutar el script.