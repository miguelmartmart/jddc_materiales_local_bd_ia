# Context for Task: cibersecuri
ID: dq02tithb

## Status
Active

## Summary
Se ha iniciado el desarrollo de una aplicación de escritorio para detectar troyanos en el equipo. La estructura básica de la aplicación incluye una función para escanear archivos en un directorio y sus subdirectorios, calculando el hash SHA-256 de cada archivo y verificando si coincide con hashes de troyanos conocidos.

## Technical Details
- La función `scan_files` escanea archivos en un directorio y sus subdirectorios.
- Se utiliza el algoritmo SHA-256 para calcular el hash de cada archivo.
- La lista `known_trojan_hashes` almacena los hashes de troyanos conocidos.

## Created Files
- `interjddcia/cibersecuri/detector_troyanos.py`

## Resumen y Próximos Pasos
Se ha creado la estructura básica para la aplicación de escritorio que detecta troyanos. Los próximos pasos incluyen poblar la lista `known_trojan_hashes` con hashes de troyanos conocidos y configurar el path en la función `scan_files` para escanear el directorio deseado. Luego, se debe ejecutar el script para iniciar el escaneo. El usuario debe asegurarse de tener los permisos necesarios para leer los archivos en el directorio objetivo y considerar la implementación de medidas para manejar grandes cantidades de datos y optimizar el rendimiento del escaneo.