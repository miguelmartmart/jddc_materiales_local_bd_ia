## Contexto Actual
La aplicación de escritorio para detectar troyanos en el equipo está en desarrollo.

## Resumen
Se ha creado el esqueleto básico de la aplicación de escritorio para detectar troyanos en el equipo, incluyendo la obtención de archivos, cálculo de hashes y un método para detectar troyanos que compara los hashes generados con una base de datos simulada de hashes conocidos de troyanos. La lógica para detectar troyanos ha sido implementada en el método `detectar_troyanos`. Además, se ha implementado la notificación al usuario cuando se detecta un troyano y la opción para escanear directorios específicos.

## Technical Details
- Se ha utilizado Python como lenguaje de programación para el desarrollo de la aplicación.
- La clase `TroyanoDetector` se encarga de obtener los archivos del equipo, calcular sus hashes y detectar troyanos.
- La lógica para detectar troyanos se ha implementado comparando los hashes generados con una base de datos de hashes conocidos de troyanos.
- La base de datos de troyanos es simulada mediante una URL que devuelve una lista de hashes conocidos.
- Se ha utilizado la biblioteca `tkinter` para la notificación al usuario cuando se detecta un troyano.
- Se ha agregado un método `escanear_directorio` para permitir al usuario escanear directorios específicos.

## Created Files
- `interjddcia/ciberse/detect_troyanos.py`

## Resumen y Próximos Pasos
Se ha avanzado en la creación de la aplicación de escritorio para detectar troyanos, implementando la lógica de detección en el método `detectar_troyanos` y agregando la notificación al usuario y la opción para escanear directorios específicos. Los próximos pasos incluyen ejecutar el script para probar la funcionalidad de notificación y escaneo de directorios, considerar la integración con sistemas de detección de malware para mejorar la efectividad de la detección, y evaluar la posibilidad de mejorar la interfaz de usuario para una mejor experiencia del usuario.