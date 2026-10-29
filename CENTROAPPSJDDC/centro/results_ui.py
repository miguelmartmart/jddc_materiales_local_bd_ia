"""Resultados locales, separados del inventario de archivos de tests."""
import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from . import core, evidence


def category(record):
    detail = record['detail']
    if detail.startswith('SINTÉTICO:'):
        return 'Tests ejecutados'
    if detail.startswith(('INTENTO REAL:', 'RED REAL:', 'ERP REAL:')):
        return 'Intentos reales y red'
    return 'Pendientes y planes'


def report_text(record, workspace):
    text = f"{record['name']}\nFecha: {record['checked_at']}\n\n{record['detail']}\n\nArchivo local: {record['path'] or 'No disponible'}"
    if record['detail'].startswith('SINTÉTICO:'):
        try:
            data = json.loads(core.safe_file(Path(record['path']), workspace, 2 * 1024 * 1024))
            records = data['records']
            # Mostrar primero las incidencias, sin tracebacks ni cuerpos privados.
            records = sorted(records, key=lambda r: r.get('status') == 'pass')
            text += '\n\nCASOS (incidencias primero)\n'
            for item in records:
                text += f"{item.get('status', '?')} · {item.get('id', 'Sin identificador')}\n"
        except (OSError, ValueError, TypeError, KeyError):
            text += '\nNo se pudo leer el detalle de casos. Se conserva el resumen.'
    elif record['detail'].startswith('INTENTO REAL:'):
        text += ('\n\nCONVERSACIÓN: estos informes no guardan preguntas ni respuestas. '
                 'No hay transcripción que mostrar en esta evidencia. Un intento o TLS correcto '
                 'no acredita una conversación completada ni exactitud ERP.')
    return text


class ResultsWindow(tk.Toplevel):
    def __init__(self, parent, workspace):
        super().__init__(parent)
        self.workspace = workspace
        self.title('Resultados de pruebas DEVIA · evidencias locales')
        self.geometry('950x650')
        self.minsize(720, 480)
        self.records = evidence.inventory(workspace)
        self.selected = None
        ttk.Label(self, text='Resultados ejecutados y pruebas reales', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=12, pady=8)
        ttk.Label(self, text='Las campañas se muestran por separado. Los archivos de código de tests no son resultados.', wraplength=850).pack(anchor='w', padx=12)
        ttk.Label(self, text='Conversación integrada IA/ERP: aún no acreditada. Consulta las capturas y lecturas reales con el botón inferior.', wraplength=850, foreground='#875400').pack(anchor='w', padx=12, pady=5)
        ttk.Button(self, text='Ver conversaciones y capturar prueba real', command=self.conversations).pack(anchor='w', padx=12, pady=5)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True, padx=12)
        self.details = {}
        for label in ('Tests ejecutados', 'Intentos reales y red', 'Pendientes y planes'):
            frame = ttk.Frame(self.tabs)
            self.tabs.add(frame, text=label)
            panes = ttk.Panedwindow(frame, orient='vertical')
            panes.pack(fill='both', expand=True)
            listing = ttk.Frame(panes)
            tree = ttk.Treeview(listing, columns=('date',), show='tree headings', height=5)
            tree.heading('#0', text='Campaña / evidencia (selecciona para ver resultados)')
            tree.heading('date', text='Fecha de la evidencia')
            tree.column('#0', width=560)
            tree.column('date', width=230)
            scroll = ttk.Scrollbar(listing, command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            tree.pack(side='left', fill='both', expand=True)
            scroll.pack(side='right', fill='y')
            panes.add(listing, weight=1)
            box = ttk.Frame(panes)
            detail = tk.Text(box, wrap='word', font=('Segoe UI', 11), height=12)
            ds = ttk.Scrollbar(box, command=detail.yview)
            detail.configure(yscrollcommand=ds.set, state='disabled')
            detail.pack(side='left', fill='both', expand=True)
            ds.pack(side='right', fill='y')
            panes.add(box, weight=3)
            rows = sorted((r for r in self.records if category(r) == label), key=lambda r: r['checked_at'], reverse=True)
            mapping = {}
            for i, r in enumerate(rows):
                mapping[str(i)] = r
                tree.insert('', 'end', iid=str(i), text=r['name'], values=(r['checked_at'],))
            def select(event=None, t=tree, d=detail, m=mapping):
                if not t.selection():
                    return
                self.selected = m[t.selection()[0]]
                d.configure(state='normal')
                d.delete('1.0', 'end')
                d.insert('1.0', report_text(self.selected, workspace))
                d.configure(state='disabled')
            tree.bind('<<TreeviewSelect>>', select)
            self.details[label] = (tree, detail)
            if rows:
                tree.selection_set('0')
                select()
            else:
                detail.configure(state='normal')
                detail.insert('1.0', 'No se han encontrado resultados de este tipo en las carpetas conocidas.')
                detail.configure(state='disabled')
        self.status = tk.StringVar(value='Lectura local. No ejecuta consultas ERP, inferencias ni envía datos.')
        ttk.Label(self, textvariable=self.status, wraplength=850).pack(anchor='w', padx=12, pady=6)
        ttk.Button(self, text='Abrir carpeta de la evidencia seleccionada', command=self.open_folder).pack(anchor='w', padx=12, pady=(0, 10))
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        self.tab_changed()

    def conversations(self):
        from .conversations_ui import ConversationsWindow
        ConversationsWindow(self, self.workspace)

    def tab_changed(self, event=None):
        self.selected = None
        label = self.tabs.tab(self.tabs.select(), 'text')
        tree, _ = self.details[label]
        tree.event_generate('<<TreeviewSelect>>')

    def open_folder(self):
        try:
            if not self.selected or not self.selected['path']:
                raise ValueError('selection')
            path = Path(self.selected['path'])
            core.safe_file(path, self.workspace, 2 * 1024 * 1024)
            os.startfile(str(path.parent))
        except (OSError, ValueError, AttributeError):
            self.status.set('No se pudo abrir. La ruta se conserva en el detalle para localizarla.')
