¡Vamos a darle caña a esta detección de troyanos!

**ESTADO**: Paso 3 de 3.
**EXPLICACIÓN**: Ahora vamos a refinar la función `detectar_troyan` para que sea más precisa en la identificación de troyanos.
**ACCIÓN**:
```python
// cibrseg/detect.py
import os
import re

def detectar_troyan(nombre_archivo):
    """
    Detecta si un archivo es un troyano basándose en patrones en su nombre.

    Args:
        nombre_archivo (str): El nombre del archivo a analizar.

    Returns:
        bool: True si el archivo es un troyano, False en caso contrario.
    """
    troyan_patterns = [
        r"trojan",
        r"agent",
        r"bot",
        r"shell",
        r"worm",
        r"virus",
        r"malware",
        r"spyware"
    ]

    for pattern in troyan_patterns:
        if re.search(pattern, nombre_archivo, re.IGNORECASE):
            return True
    return False
```
[[NEXT_ACTION:{"type":"run_command","content":"python cibrseg/detect.py","label":"Ejecutar Script"}]]
