# Context for Chat: Chat 12:52:01
ID: kd26n1ww1

## Status
Active

## Summary
Se ha creado una aplicación de escritorio básica en Python para detectar troyanos en el equipo, calculando hashes MD5 de los archivos y comparándolos con una base de datos de hashes conocidos.

## Technical Details
- La aplicación utiliza la biblioteca `hashlib` para calcular hashes MD5 de los archivos.
- La función `calcular_hash` abre el archivo en modo binario y lee bloques de 4096 bytes para calcular el hash.
- La función `buscar_troyanos` lista los archivos en el directorio especificado y calcula el hash de cada archivo.
- Se utiliza el directorio actual como punto de partida para la búsqueda de troyanos.

## Created Files
- `interjddcia/ciber/detectar_troyanos.py`

## Resumen y Próximos Pasos
Se ha completado el primer paso de la aplicación de escritorio para detectar troyanos. El próximo paso es ejecutar el script `detectar_troyanos.py` en el directorio que se desee buscar y integrar una base de datos de hashes conocidos para comparar los hashes calculados y así identificar posibles troyanos. Luego, se deberá mejorar la aplicación para que pueda alertar al usuario sobre posibles troyanos detectados y ofrecer opciones para eliminar o cuarentena los archivos sospechosos.