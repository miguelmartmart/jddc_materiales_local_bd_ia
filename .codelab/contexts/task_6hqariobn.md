# Context for Task: cibe
ID: 6hqariobn

## Status
Active

## Summary
Se ha iniciado el desarrollo de una aplicación de escritorio para detectar troyanos en el equipo, creando el archivo principal `detector_troyanos.py` que incluye funcionalidad básica para escanear directorios y detectar archivos ejecutables.

## Technical Details
- El archivo `detector_troyanos.py` utiliza los módulos `os` y `hashlib` para escanear directorios y calcular hash de archivos ejecutables.
- La función `scan_directories` recorre directorios y subdirectorios a partir de un directorio raíz proporcionado por el usuario.
- La aplicación solicita al usuario que ingrese el directorio raíz a escanear.

## Created Files
- `interjddcia/cibe/detector_troyanos.py`

## Resumen y Próximos Pasos
Se ha completado el primer paso de la aplicación de escritorio para detectar troyanos, creando el archivo `detector_troyanos.py`. Los próximos pasos incluyen la ejecución del script y la posible inclusión de funcionalidades adicionales como la verificación de firmas digitales o la comparación con bases de datos de malware conocido. El usuario debe ejecutar `detector_troyanos.py` y proporcionar el directorio raíz para iniciar el escaneo.