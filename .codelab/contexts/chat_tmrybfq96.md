¡Vamos a darle!

**ESTADO**: Paso 2 de 3.

**EXPLICACIÓN**: Ahora vamos a modificar el archivo `detectores_malware.py` para implementar la lógica de detección de troyanos.

**ACCIÓN**:
```// cibrseg/detectores_malware.py
def detectar_trojan(archivo):
    """
    Simula la detección de un troyano en un archivo.
    En una implementación real, se usarían técnicas de análisis estático y dinámico.
    """
    if archivo.endswith(".exe") or archivo.endswith(".dll"):
        return "Posible troyano detectado"
    else:
        return "No se detectó ningún troyano"
```
[[NEXT_ACTION:{"type":"browser","content":"cibrseg/detectores_malware.py","label":"Abrir en Navegador"}]]
¡Listo! Dale al botón de abajo para Abrir en Navegador.