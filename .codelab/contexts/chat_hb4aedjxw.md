**ESTADO**: Paso 1 de 4.
**EXPLICACIÓN**: Iniciaremos implementando la base de datos de hashes conocidos en el script de Python para detectar troyanos.
**ACCIÓN**:
```python
// ./detector_troyanos.py
import sqlite3
import hashlib

# Conexión a la base de datos
conn = sqlite3.connect('hashes_troyanos.db')
cursor = conn.cursor()

# Crear tabla para almacenar hashes de troyanos
cursor.execute('''
    CREATE TABLE IF NOT EXISTS troyanos
    (id INTEGER PRIMARY KEY, hash TEXT UNIQUE)
''')

# Función para agregar hash a la base de datos
def agregar_hash(hash_troyano):
    cursor.execute('INSERT OR IGNORE INTO troyanos (hash) VALUES (?)', (hash_troyano,))
    conn.commit()

# Ejemplo de uso: Agregar un hash conocido de troyano
hash_conocido = hashlib.md5(b'codigo_troyano_ejemplo').hexdigest()
agregar_hash(hash_conocido)

# Cerrar conexión
conn.close()
```
[[NEXT_ACTION:{"type":"run_command","content":"python detector_troyanos.py","label":"Ejecutar Script"}]]
¡Listo! Dale al botón de abajo para ejecutar el script y empezar a trabajar con la base de datos de hashes de troyanos.