**ESTADO**: Paso 1 de 5.
**EXPLICACIÓN**: Ahora que tienes un script básico, es momento de ejecutarlo con una ruta específica para comenzar a detectar archivos sospechosos.
**ACCIÓN**:
```python
// ./detector_troyanos.py
import sys
import os

def detectar_troyanos(carpeta):
    # Aquí irá la lógica para detectar troyanos
    print(f"Detectando troyanos en {carpeta}...")
    for archivo in os.listdir(carpeta):
        print(f"Revisando {archivo}...")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        carpeta = sys.argv[1]
        detectar_troyanos(carpeta)
    else:
        print("Por favor, proporciona la ruta a la carpeta como argumento.")
```
**SIGUIENTE PASO**: Necesitas indicar la ruta de la carpeta que deseas escanear. ¿Cuál es la ruta que deseas utilizar? Por favor, responde con la ruta para que pueda generarte el comando adecuado.
[[NEXT_ACTION:{"type":"chat_message","content":"Indica la ruta de la carpeta","label":"Proporcionar Ruta"}]]
¡Listo! Dale al botón de abajo para continuar.