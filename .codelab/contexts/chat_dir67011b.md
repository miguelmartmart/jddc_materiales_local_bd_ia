# Context for Chat: Chat 11:04:56
ID: dir67011b

## Status
Active

## Summary
Se ha iniciado la creación de una aplicación de escritorio básica para detectar troyanos, empezando con una función para escanear directorios y calcular hashes de archivos.

## Technical Details
- Se utiliza el módulo `os` para interactuar con el sistema de archivos y `hashlib` para calcular hashes de archivos.
- La función `escanear_directorio` recorre un directorio y sus subdirectorios, calculando el hash SHA-256 de cada archivo encontrado.
- El script `detector_troyanos.py` solicita al usuario una ruta de directorio para escanear.

## Created Files
- `detector_troyanos.py`

## Resumen y Próximos Pasos
La aplicación de escritorio para detectar troyanos ha sido iniciada con funcionalidad básica. El próximo paso es ejecutar el script `detector_troyanos.py` para probar su funcionalidad. Luego, se necesitará expandir la aplicación para comparar los hashes con bases de datos de malware conocidos y así identificar posibles troyanos.

[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/detector_troyanos.py","label":"Ejecutar Script"}]]
¡Listo! Dale al botón de abajo para ejecutarlo.