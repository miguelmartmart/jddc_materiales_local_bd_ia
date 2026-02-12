**ESTADO**: Paso 2 de 5.
**EXPLICACIÓN**: Necesitamos desarrollar las funcionalidades de la aplicación según el sistema operativo detectado.
**ACCIÓN**:
```python
// ./interjddcia/functionalities.py
import sys
from interjddcia.config import get_os

def develop_functionalities(os):
    if os == 'Windows':
        # Desarrollar funcionalidades para Windows
        print('Desarrollando funcionalidades para Windows')
    elif os == 'Linux':
        # Desarrollar funcionalidades para Linux
        print('Desarrollando funcionalidades para Linux')
    elif os == 'Darwin':
        # Desarrollar funcionalidades para macOS
        print('Desarrollando funcionalidades para macOS')
    else:
        print('Sistema operativo no soportado')

if __name__ == '__main__':
    os = get_os()
    develop_functionalities(os)
```
**SIGUIENTE PASO**: Ahora que tenemos el esqueleto para desarrollar funcionalidades según el sistema operativo, debemos ejecutar este script con el sistema operativo como argumento.
[[NEXT_ACTION:{"type":"run_command","content":"python interjddcia/functionalities.py","label":"Ejecutar Funcionalidades"}]]
¡Listo! Dale al botón de abajo para ejecutarlo.