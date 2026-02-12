**ESTADO**: Paso 1 de 2.
**EXPLICACIÓN**: Se ha proporcionado un script de Python para detectar troyanos en el equipo, y ahora se necesita ejecutar el script para probar su funcionalidad.
**ACCIÓN**:
```python
// ./detector_troyanos.py
import os
import hashlib

def calcular_hash(archivo):
    md5_hash = hashlib.md5()
    with open(archivo, "rb") as f:
        # Lee el archivo en bloques para evitar cargar todo en memoria
        for byte_block in iter(lambda: f.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()

def detectar_troyanos(directorio):
    lista_archivos = []
    for root, dirs, files in os.walk(directorio):
        for file in files:
            archivo = os.path.join(root, file)
            hash_archivo = calcular_hash(archivo)
            lista_archivos.append((archivo, hash_archivo))
    return lista_archivos

# Recuerda pasar como argumento el directorio a escanear
directorio_a_escanear = sys.argv[1] if len(sys.argv) > 1 else '.'
lista_archivos_con_hash = detectar_troyanos(directorio_a_escanear)

# Imprime la lista de archivos con sus hashes
for archivo, hash_archivo in lista_archivos_con_hash:
    print(f"Archivo: {archivo}, Hash MD5: {hash_archivo}")
```
** IMPORTANTE **: Para ejecutar el script, debes proporcionar el directorio que deseas escanear como argumento. Por ejemplo, si deseas escanear el directorio actual, puedes ejecutar el script con el comando `python detector_troyanos.py .` (el punto representa el directorio actual). Si deseas escanear otro directorio, reemplaza el punto con la ruta del directorio que deseas escanear.

[[NEXT_ACTION:{"type":"run_command","content":"python detector_troyanos.py .","label":"Ejecutar Detector de Troyanos en el Directorio Actual"}]]
¡Listo! Dale al botón de abajo para ejecutar el detector de troyanos en el directorio actual.