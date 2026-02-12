import tkinter as tk
from tkinter import filedialog
from detect_troyanos import buscar_troyanos
import threading

def seleccionar_ruta():
    ruta = filedialog.askdirectory()
    entry_ruta.delete(0, tk.END)
    entry_ruta.insert(0, ruta)

def iniciar_busqueda():
    ruta = entry_ruta.get()
    if ruta:
        button_iniciar.config(state="disabled")
        label_estado.config(text="Búsqueda en progreso...")
        thread = threading.Thread(target=buscar_troyanos, args=(ruta,))
        thread.start()
    else:
        label_estado.config(text="Debes seleccionar una ruta")

root = tk.Tk()
root.title("Detectar Troyanos")

label_ruta = tk.Label(root, text="Ruta:")
label_ruta.pack()

entry_ruta = tk.Entry(root, width=50)
entry_ruta.pack()

button_seleccionar = tk.Button(root, text="Seleccionar Ruta", command=seleccionar_ruta)
button_seleccionar.pack()

button_iniciar = tk.Button(root, text="Iniciar Búsqueda", command=iniciar_busqueda)
button_iniciar.pack()

label_estado = tk.Label(root, text="")
label_estado.pack()

root.mainloop()