## Estado: Paso 1 de 5.
## Explicación: El script `virus_total_api.py` está listo para detectar archivos maliciosos en el equipo.
## Acción:
```python
// ./virus_total_api.py
import hashlib
import os
import sys
import requests

def obtener_hash_sha256(ruta_archivo):
    hash_sha256 = hashlib.sha256()
    with open(ruta_archivo, "rb") as archivo:
        for byte_block in iter(lambda: archivo.read(4096), b""):
            hash_sha256.update(byte_block)
    return hash_sha256.hexdigest()

def analizar_archivo(ruta_archivo, api_key):
    hash_sha256 = obtener_hash_sha256(ruta_archivo)
    url = f"https://www.virustotal.com/api/v3/files/{hash_sha256}"
    headers = {
        "Accept": "application/json",
        "x-apikey": api_key
    }
    respuesta = requests.get(url, headers=headers)
    if respuesta.status_code == 200:
        datos = respuesta.json()
        if datos["data"]["attributes"]["last_analysis_stats"]["malicious"] > 0:
            print(f"El archivo {ruta_archivo} es malicioso.")
        else:
            print(f"El archivo {ruta_archivo} no es malicioso.")
    else:
        print(f"Error al analizar el archivo {ruta_archivo}.")

def main():
    if len(sys.argv) < 3:
        print("Usage: python virus_total_api.py <API_KEY> <carpeta>")
        return
    api_key = sys.argv[1]
    carpeta = sys.argv[2]
    for root, dirs, files in os.walk(carpeta):
        for filename in files:
            ruta_archivo = os.path.join(root, filename)
            analizar_archivo(ruta_archivo, api_key)

if __name__ == "__main__":
    main()
```
[[NEXT_ACTION:{"type":"run_command","content":"python virus_total_api.py TU_API_KEY_AQUÍ /path/to/carpeta","label":"Ejecutar Script con Parámetro"}]]
¡Listo! Dale al botón de abajo para ejecutarlo.