¡Perfecto! Empecemos con la creación del script base.

**ESTADO**: Paso 1 de 3 completado.

**EXPLICACIÓN**: Vamos a crear el script `detectores_malware.py` que servirá como base para la detección de troyanos.

**ACCIÓN**:
```python
// cibrseg/detectores_malware.py
import os
import sys

def detectar_troyano(ruta):
    """
    Detecta si un archivo o directorio contiene la palabra "troyano" en su nombre o ruta.
    """
    if "troyano" in ruta.lower():
        return True
    else:
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
        if os.path.exists(ruta):
            if detectar_troyano(ruta):
                print(f"¡Se ha detectado un troyano en: {ruta}!")
            else:
                print(f"No se ha detectado un troyano en: {ruta}")
        else:
            print(f"La ruta no existe: {ruta}")
    else:
        print("Por favor, proporciona una ruta como argumento.")
```
[[NEXT_ACTION:{"type":"run_command","content":"python cibrseg/detectores_malware.py /tmp/test_troyan","label":"Ejecutar Script"}]]
[[NEXT_ACTION:{"type":"chat_message","content":"Ahora, prueba el script con diferentes rutas para verificar su funcionamiento.","label":"Continuar"}]]