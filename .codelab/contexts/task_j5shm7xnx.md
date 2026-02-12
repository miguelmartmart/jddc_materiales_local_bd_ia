# Context for Task: cib2
ID: j5shm7xnx

## Status
Active

## Summary
Se ha creado un script básico para detectar troyanos en una carpeta dada, comparando los hashes de los archivos con una lista de hashes conocidos de troyanos.

## Technical Details
- La aplicación utiliza el módulo `hashlib` para calcular el hash MD5 de los archivos.
- La función `calcular_hash.archivo` intenta leer un archivo en modo binario y devuelve su hash MD5.
- La función `buscar_troyanos` recorre todos los archivos en una carpeta y sus subcarpetas, comparando sus hashes con una lista de hashes conocidos de troyanos.
- El script se ejecuta desde la línea de comandos, pasando la carpeta a escanear como parámetro.

## Created Files
- `detector_troyanos.py`

## Resumen y Próximos Pasos
Se ha implementado la funcionalidad básica para detectar troyanos en una carpeta. Los próximos pasos incluyen mejorar la lista de hashes conocidos de troyanos y agregar más funcionalidades a la aplicación, como la opción de elegir la carpeta a escanear desde una interfaz gráfica de usuario.

[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/detector_troyanos.py \"C:/Users/Usuario/Desktop\"","label":"Ejecutar Script"}]]
¡Listo! Dale al botón de abajo para ejecutarlo.