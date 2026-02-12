¡Perfecto! Vamos a enfocarnos en la interfaz gráfica.

**ESTADO**: Paso 3 de 2.

**EXPLICACIÓN**: Vamos a crear la interfaz gráfica principal utilizando `tkinter`.

**ACCIÓN**:
```python
// cibrseg/main.py
import tkinter as tk
from tkinter import filedialog
import os
import re

def seleccionar_archivo():
    archivo_path = filedialog.askopenfilename()
    if archivo_path:
        mostrar_resultado(archivo_path)

def mostrar_resultado(archivo_path):
    try:
        with open(archivo_path, 'r') as f:
            contenido = f.read()
            if re.search(r"troyan", contenido, re.IGNORECASE):
                resultado_label.config(text="¡Se detectó un troyano!")
            else:
                resultado_label.config(text="No se detectó ningún troyano.")
    except Exception as e:
        resultado_label.config(text=f"Error al leer el archivo: {e}")

root = tk.Tk()
root.title("Detección de Troyanos")

seleccionar_button = tk.Button(root, text="Seleccionar Archivo", command=seleccionar_archivo)
seleccionar_button.pack(pady=20)

resultado_label = tk.Label(root, text="No se detectó ningún troyano.")
resultado_label.pack(pady=10)

root.mainloop()
```
[[NEXT_ACTION:{"type":"run_command","content":"python cibrseg/main.py","label":"Ejecutar Script"}]]
¡Listo! Dale al botón de abajo para Ejecutar Script.