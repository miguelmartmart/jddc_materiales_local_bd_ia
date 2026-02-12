# Context for Task: ciber
ID: o0m930lh1

## Status
Active

## Summary
Se ha iniciado el desarrollo de una aplicación de escritorio en Python para detectar troyanos en el equipo, calculando hashes MD5 de los archivos y comparándolos con una base de datos de hashes conocidos.

## Technical Details
- La aplicación utiliza el módulo `hashlib` para calcular hashes MD5 de los archivos.
- El script `detectar_troyanos.py` busca troyanos en el directorio especificado, calcula el hash de cada archivo y lo compara con una base de datos de hashes conocidos.
- La aplicación se ejecuta en el directorio actual utilizando `os.getcwd()`.

## Created Files
- `detectar_troyanos.py`

## Resumen y Próximos Pasos
Se ha creado la estructura básica de la aplicación de escritorio para detectar troyanos. El próximo paso es integrar una base de datos de hashes conocidos para comparar los hashes calculados y así identificar posibles troyanos. Luego, el usuario debe ejecutar el script `detectar_troyanos.py` en el directorio que desee buscar. También se puede mejorar la aplicación añadiendo más funcionalidades, como la capacidad de actualizar la base de datos de hashes conocidos y notificar al usuario sobre posibles amenazas detectadas.