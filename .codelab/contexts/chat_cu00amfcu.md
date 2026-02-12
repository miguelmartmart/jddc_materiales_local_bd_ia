**ESTADO**: Paso 1 de 5.
**EXPLICACIÓN**: Ahora vamos a configurar el script de detección de troyanos.
**ACCIÓN**:
```python
// interjddcia/config.py
import sys
import argparse

# Configuración del parser de argumentos
parser = argparse.ArgumentParser(description='Configuración de la aplicación de detección de troyanos')
parser.add_argument('-d', '--directorio', help='Directorio a escanear', required=True)
parser.add_argument('-o', '--output', help='Archivo de salida para los resultados', required=True)

# Parseo de argumentos
args = parser.parse_args()

# Configuración de la aplicación
config = {
    'directorio': args.directorio,
    'output': args.output
}

# Imprimir la configuración
print('Configuración de la aplicación:')
print(f'Directorio: {config["directorio"]}')
print(f'Archivo de salida: {config["output"]}')
```
[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/config.py -d /path/to/directory -o /path/to/output.txt","label":"Ejecutar Configuración"}]]
¡Listo! Dale al botón de abajo para ejecutar la configuración.