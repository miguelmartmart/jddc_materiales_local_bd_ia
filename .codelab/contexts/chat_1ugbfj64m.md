**ESTADO**: Paso 1 de 3.
**EXPLICACIÓN**: Necesitamos conocer el sistema operativo y las restricciones para continuar con el desarrollo.
**ACCIÓN**:
```python
// ./interjddcia/config.py
import sys

def get_os_details(os_name, restrictions):
    # Lógica para obtener detalles del sistema operativo
    details = {
        "os": os_name,
        "restrictions": restrictions
    }
    return details

if __name__ == "__main__":
    if len(sys.argv) > 2:
        os_name = sys.argv[1]
        restrictions = sys.argv[2]
        details = get_os_details(os_name, restrictions)
        print("Sistema Operativo:", details["os"])
        print("Restricciones:", details["restrictions"])
    else:
        print("No se proporcionaron detalles del sistema operativo o restricciones.")
```
[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/config.py Windows10 none","label":"Proporcionar Detalles"}]]
¡Listo! Dale al botón de abajo para ejecutarlo.