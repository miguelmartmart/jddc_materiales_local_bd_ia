# Context for Chat: Chat 12:58:42
ID: ld14vn4bg

## Status
Active

## Summary
Se ha iniciado el proyecto de aplicación de escritorio para detectar troyanos, creando la estructura básica con una función para escanear archivos y calcular su hash.

## Technical Details
- Se utiliza Python como lenguaje de programación.
- Se emplea la biblioteca `hashlib` para calcular los hashes de los archivos.
- Se utiliza la biblioteca `os` para interactuar con el sistema de archivos.

## Created Files
- `interjddcia/cib/main.py`

## Resumen y Próximos Pasos
El script actual escanea los archivos en un directorio especificado por el usuario y calcula su hash. El próximo paso es agregar funcionalidades para comparar los hashes generados con una base de datos de hashes conocidos de troyanos y malware, y mejorar la interfaz de usuario para una mejor experiencia del usuario. El usuario debe ejecutar el script con Python, ingresar el directorio que desea escanear y verificar los hashes generados para detectar posibles troyanos.

[[NEXT_ACTION: Ejecutar el script con Python e ingresar el directorio a escanear]]