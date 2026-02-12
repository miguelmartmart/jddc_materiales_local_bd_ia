# Context for Chat: Chat 12:58:57
ID: w45bi79yx

## Status
Active

## Summary
Se ha iniciado la aplicación de escritorio para detectar troyanos con la creación de la estructura básica y la función para escanear archivos en un directorio y calcular su hash.

## Technical Details
- Se utiliza la biblioteca `hashlib` para calcular los hashes de los archivos.
- Se utiliza la biblioteca `os` para interactuar con el sistema de archivos.
- El script `main.py` se ejecuta desde el directorio `interjddcia/cib`.

## Created Files
- `interjddcia/cib/main.py`

## Resumen y Próximos Pasos
Se ha creado la estructura básica de la aplicación y se ha implementado la función para escanear archivos y calcular su hash. Los próximos pasos incluyen comparar los hashes generados con una base de datos de hashes conocidos de troyanos y malware, y mejorar la interfaz de usuario para una mejor experiencia del usuario.

[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/cib/main.py","label":"Ejecutar Aplicación"}]]
¡Listo! Dale al botón de abajo para ejecutar la aplicación.