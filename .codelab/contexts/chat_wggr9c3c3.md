# Context for Chat: Chat 13:17:01
ID: wggr9c3c3

## Status
Active

## Summary
Se ha comenzado el desarrollo de una aplicación de escritorio para detectar troyanos en el equipo, creando una estructura básica para escanear archivos en busca de troyanos conocidos por sus hashes SHA-256.

## Technical Details
- La aplicación utiliza el algoritmo SHA-256 para calcular hashes de archivos.
- La función `scan_files` escanea directorios y subdirectorios en busca de archivos potencialmente maliciosos.
- Se requiere poblar la lista `known_trojan_hashes` con hashes de troyanos conocidos.

## Created Files
- `detector_troyanos.py`

## Resumen y Próximos Pasos
Se ha creado el archivo `detector_troyanos.py` como parte de la estructura básica para la aplicación de escritorio. Los próximos pasos incluyen poblar la lista `known_trojan_hashes` con hashes de troyanos conocidos, configurar el path en la función `scan_files` para escanear el directorio deseado, y ejecutar el script para iniciar el escaneo. Esto permitirá a la aplicación detectar y reportar posibles troyanos en el sistema.