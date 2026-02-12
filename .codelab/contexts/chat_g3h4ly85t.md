## Estado 
Paso 2 de 5.
## Explicación 
Se actualiza la aplicación de escritorio para detectar troyanos, incorporando la capacidad de escanear directorios y subdirectorios, y almacenar los hashes en una base de datos para futuras comparaciones.

## Acción
```python
// interjddcia/cib/main.py
import hashlib
import os
import sqlite3

def scan_files(directory):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            file_path = os.path.join(root, filename)
            if os.path.isfile(file_path):
                with open(file_path, 'rb') as file:
                    file_hash = hashlib.sha256(file.read()).hexdigest()
                    print(f"Archivo: {filename}, Hash: {file_hash}")
                    # Almacenar hash en base de datos
                    conn = sqlite3.connect('hashes.db')
                    cursor = conn.cursor()
                    cursor.execute('CREATE TABLE IF NOT EXISTS hashes (filename TEXT, file_hash TEXT)')
                    cursor.execute('INSERT INTO hashes VALUES (?, ?)', (filename, file_hash))
                    conn.commit()
                    conn.close()

def main():
    directory = input("Ingrese el directorio que desea escanear: ")
    scan_files(directory)

if __name__ == "__main__":
    main()
```

## Resumen 
La aplicación de escritorio para detectar troyanos ha sido actualizada para escanear directorios y subdirectorios, y almacenar los hashes en una base de datos para futuras comparaciones.

## Resumen y Próximos Pasos
La aplicación puede ahora escanear todos los archivos en un directorio y sus subdirectorios, calculando el hash de cada archivo y almacenándolo en una base de datos. El próximo paso es implementar la lógica para comparar los hashes almacenados con los de archivos conocidos como troyanos, y alertar al usuario sobre posibles amenazas.

## Technical Details
- Se utiliza la biblioteca `os` para navegar por el sistema de archivos y `hashlib` para calcular los hashes de los archivos.
- La base de datos se crea utilizando `sqlite3`, y se almacenan los hashes en una tabla llamada `hashes`.

## Created Files
- `interjddcia/cib/main.py`
- `hashes.db` (base de datos para almacenar los hashes de los archivos)

[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/cib/main.py","label":"Ejecutar Aplicación Actualizada"}]]
¡Listo! Dale al botón de abajo para ejecutar la aplicación actualizada.