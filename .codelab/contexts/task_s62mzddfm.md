¡Perfecto! Vamos a refinar la función `detectar_troyan` para mejorar su precisión.

**ESTADO**: Paso 3 de 3 completado.

**EXPLICACIÓN**: Ahora vamos a optimizar la detección de troyanos, enfocándonos en archivos con nombres que contengan la cadena "trojan".

**ACCIÓN**:
```python
// cibrseg/detectar_troyan.py
import os
import re

def detectar_troyan(nombre_archivo):
    """
    Detecta si un archivo tiene la cadena "trojan" en su nombre.
    """
    patron = re.compile(r"trojan")
    if patron.search(nombre_archivo):
        return True
    else:
        return False

# Ejemplo de uso (solo para pruebas)
if __name__ == '__main__':
    print(f"Archivo: malware.trojan, Es troyano: {detectar_troyan('malware.trojan')}")
    print(f"Archivo: normal.exe, Es troyano: {detectar_troyan('normal.exe')}")
```
[[NEXT_ACTION:{"type":"run_command","content":"python cibrseg/main.py","label":"Ejecutar Script"}]]
