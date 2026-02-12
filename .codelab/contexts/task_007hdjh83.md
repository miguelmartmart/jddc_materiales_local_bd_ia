ESTADO: Paso 1 de 2.
EXPLICACIÓN: Ahora vamos a crear el contenido del archivo `interjddcia/config.py` para definir los parámetros de configuración y las preferencias de escaneo.
ACCIÓN:
```python
// interjddcia/config.py
import sys
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Configuración de la aplicación de detección de troyanos')
    parser.add_argument('-s', '--scan_path', help='Ruta del directorio a escanear', default='/')
    parser.add_argument('-l', '--log_file', help='Ruta del archivo de log', default='interjddcia/log.txt')
    return parser.parse_args()

def main():
    args = parse_args()
    print(f'Ruta de escaneo: {args.scan_path}')
    print(f'Archivo de log: {args.log_file}')

if __name__ == '__main__':
    main()
```
[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/config.py -h","label":"Ver ayuda de la configuración"}]]
¡Listo! Dale al botón de abajo para ver la ayuda de la configuración.