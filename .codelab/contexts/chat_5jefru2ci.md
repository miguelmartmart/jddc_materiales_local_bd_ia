## Contexto Actual
La aplicación de escritorio para detectar troyanos en el equipo está en desarrollo. Se ha creado un script básico para detectar troyanos explorando el sistema de archivos y calculando hashes MD5 de los archivos encontrados.

## Detalles Técnicos
- Se utiliza la biblioteca `hashlib` para calcular hashes MD5 de los archivos.
- La biblioteca `os` se utiliza para explorar el sistema de archivos.
- El script `detectar_troyanos.py` debe ejecutarse con la ruta a explorar como parámetro, por ejemplo: `python detectar_troyanos.py "C:/path/a/ruta"`.

## Created Files
- `detectar_troyanos.py`

## Resumen y Próximos Pasos
Se ha implementado una función básica para calcular hashes MD5 de archivos y explorar el sistema de archivos. Los próximos pasos incluyen crear una base de datos de hashes conocidos de troyanos y mejorar la interfaz de usuario.

[[NEXT_ACTION:{"type":"chat_message","content":"Crea ahora el archivo bases_de_datos.py para almacenar los hashes conocidos de troyanos","label":"Crear Base de Datos"}]]
¡Listo! Dale al botón de abajo para crear la base de datos de hashes conocidos de troyanos.