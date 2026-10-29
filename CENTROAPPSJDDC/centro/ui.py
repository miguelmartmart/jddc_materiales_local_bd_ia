"""Ventana local: navegación jerárquica, operaciones en segundo plano y exportación."""
from __future__ import annotations

import json
import os
import queue
import threading
from datetime import datetime
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from . import core
from . import evidence
from . import equipment_summary
from . import knowledge
from .search_index import SearchIndex

SECTIONS = {
    'aplicaciones': 'Aplicaciones', 'configuracion': 'Configuración',
    'cuentas': 'Cuentas', 'certificados': 'Certificados',
    'procesos': 'Procesos', 'servicios': 'Servicios', 'red': 'Red', 'firewall': 'Firewall',
    'actualizaciones': 'Actualizaciones',
    'informes': 'Informes', 'pendientes': 'Pendientes',
}
GUIDES = {
    'aplicaciones': 'Despliega cada aplicación para consultar su ficha. Localizar código no significa que esté ejecutándose. Los procesos y puertos se leen por separado; no se atribuye un proceso Python a una app sin evidencia.',
    'configuracion': 'Se muestran categorías de campos presentes. No se muestran valores, contraseñas o tokens. La presencia de configuración no prueba su validez funcional. No se modifica ningún perfil.',
    'cuentas': 'Cuentas Windows mediante Inventario Windows y cuentas SQLite del portal cuando deployment.json apunta a un archivo dentro de la carpeta examinada. No se leen contraseñas ni hashes. No incluye cuentas remotas Ubuntu ni permisos efectivos ERP.',
    'certificados': 'Archivos públicos .crt/.cer y, con Inventario Windows, certificados personales CurrentUser/My y LocalMachine/My. No extrae claves privadas. Fecha y huella no prueban cadena, revocación o servicio. No incluye todos los almacenes Root/CA, PEM ni Ubuntu.',
    'procesos': 'Inventario de procesos Python/Node/DEVIA: PID, nombre y ejecutable. No se recogen argumentos de línea de comandos. Un PID puede reutilizarse. No se detienen ni reinician servicios desde esta versión.',
    'red': 'IPs, interfaces y listeners de este Windows cuando solicitas Inventario Windows. TCP/TLS es una conexión explícita sin HTTP, login, ERP ni inferencia. La IP NAT observada por Ubuntu debe confirmarse allí; no se deduce de la IP de la VM.',
    'firewall': 'Perfiles y hasta 501 reglas habilitadas de ActiveStore. No analiza filtros de puertos/programas ni precedencia efectiva; no incluye filtros de terceros, firewall del anfitrión ni UFW Ubuntu. El inventario no identifica por sí solo la regla causante.',
    'servicios': 'Servicios cuyo nombre menciona JDDC, DEVIA, portal o Firebird. Es una selección por nombre, no una identificación exhaustiva. No inicia ni detiene servicios.',
    'actualizaciones': 'Las versiones detectadas aparecen en Aplicaciones. No se consulta GitHub automáticamente ni se instalan actualizaciones. Los paquetes, firmas y política de activación deben comprobarse antes de integrarlos.',
    'informes': 'Índice de archivos, con ruta y tamaño. No se lee el contenido de logs históricos; pueden contener datos privados. Abrir ubicación permite localizarlos. El ZIP del centro exporta únicamente un resumen depurado, no estos archivos originales.',
    'pendientes': 'Esta versión tiene cobertura acotada. Los límites de profundidad, permisos y cantidad se hacen visibles. Cuentas Ubuntu, broker, permisos ERP y actualizaciones requieren integraciones posteriores y aceptación real.',
}


class Center(tk.Tk):
    def __init__(self, workspace: Path, autoload=True):
        super().__init__()
        self.workspace = workspace.absolute()
        self.state_dir = self.workspace / '.portal_private/control_center'
        self.title(f'Centro de aplicaciones JDDC · {__version__}')
        width = min(1250, max(800, self.winfo_screenwidth() - 50))
        height = min(820, max(570, self.winfo_screenheight() - 100))
        self.geometry(f'{width}x{height}+15+15')
        self.minsize(min(940, width), min(650, height))
        self.rows = []
        self.home_window = None
        self.inventory_loaded = False
        self._context_loaded = False
        self._render_job = None
        self.search_index = SearchIndex()
        self.visible = {}
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.roots = [self.workspace]
        self.table_maximized = False
        self.sorting = {}
        self.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(self)
        style.theme_use('clam')
        self.configure(background='#eef3f7')
        style.configure('.', font=('Segoe UI', 10), background='#eef3f7', foreground='#193542')
        style.configure('TButton', padding=(8, 5))
        style.configure('Treeview', rowheight=27, background='white', fieldbackground='white')
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=6)
        style.map('Treeview', background=[('selected', '#075f73')], foreground=[('selected', 'white')])
        style.configure('Title.TLabel', font=('Segoe UI', 17, 'bold'))
        style.configure('TNotebook.Tab', padding=(7, 5), font=('Segoe UI', 9))
        top = self.top = ttk.Frame(self, padding=(12, 8))
        top.pack(fill='x')
        titlebar = ttk.Frame(top)
        titlebar.pack(fill='x')
        ttk.Label(titlebar, text='Centro de aplicaciones JDDC', style='Title.TLabel').pack(side='left')
        bar = ttk.Frame(top)
        bar.pack(fill='x')
        ttk.Button(bar, text='Inicio y continuidad', command=self.show_home).pack(side='left', padx=(0,5))
        self.refresh_button = ttk.Button(bar, text='Actualizar inventario', command=self.refresh)
        self.refresh_button.pack(side='left')
        ttk.Button(bar, text='Añadir carpeta…', command=self.add_root).pack(side='left', padx=5)
        self.windows_button = ttk.Button(bar, text='Inventario Windows', command=self.read_windows)
        self.windows_button.pack(side='left')
        ttk.Button(bar, text='Guia por tareas', command=self.show_use_cases).pack(side='left', padx=5)
        ttk.Button(bar, text='Entregas y accesos', command=self.show_delivery_access).pack(side='left')
        self.summary = tk.StringVar(value='Sin inventario. Pulsa Actualizar inventario.')
        ttk.Label(top, textvariable=self.summary, wraplength=1150).pack(anchor='w', pady=(5, 0))
        filters = self.filters = ttk.Frame(self, padding=(12, 2, 12, 5))
        filters.pack(fill='x')
        ttk.Label(filters, text='Buscar:').pack(side='left')
        self.search = tk.StringVar()
        self.search_entry = ttk.Entry(filters, textvariable=self.search, width=25)
        self.search_entry.pack(side='left', padx=6, fill='x', expand=True)
        ttk.Label(filters, text='App:').pack(side='left')
        self.family_filter = tk.StringVar(value='Todas')
        ttk.Combobox(filters, state='readonly', textvariable=self.family_filter,
                     values=['Todas', 'DEVIA', 'Portal de Avisos', 'API SQL Obras', 'Windows', 'Centro JDDC', 'Otros / por clasificar'], width=20).pack(side='left', padx=4)
        self.state_filter = tk.StringVar(value='Todos')
        ttk.Label(filters, text='Estado:').pack(side='left')
        ttk.Combobox(filters, state='readonly', textvariable=self.state_filter,
                     values=['Todos'] + sorted(core.STATES), width=20).pack(side='left')
        tools = ttk.Frame(self, padding=(12, 0, 12, 5))
        tools.pack(fill='x')
        ttk.Label(tools, text='Tipo:').pack(side='left')
        self.type_filter = tk.StringVar(value='Todos los tipos')
        self.type_box = ttk.Combobox(tools, textvariable=self.type_filter, state='readonly', width=29,
                                    values=['Todos los tipos'])
        self.type_box.pack(side='left', padx=6)
        self.include_files = tk.BooleanVar(value=False)
        ttk.Checkbutton(tools, text='Incluir archivos y documentacion', variable=self.include_files, command=self.render).pack(side='left', padx=5)
        ttk.Button(tools, text='Limpiar filtros', command=self.clear_filters).pack(side='left')
        self.max_button = ttk.Button(tools, text='Ampliar tabla (F11)', command=self.toggle_table)
        self.max_button.pack(side='right')
        ttk.Button(tools, text='Desplegar', command=lambda: self.expand(True)).pack(side='right', padx=4)
        ttk.Button(tools, text='Plegar', command=lambda: self.expand(False)).pack(side='right')
        self.search.trace_add('write', lambda *_: self.schedule_render())
        self.state_filter.trace_add('write', lambda *_: self.render())
        self.family_filter.trace_add('write', lambda *_: self.render())
        self.type_filter.trace_add('write', lambda *_: self.render())
        self.panes = ttk.Panedwindow(self, orient='vertical')
        self.notebook = ttk.Notebook(self.panes)
        self.panes.add(self.notebook, weight=5)
        self.trees = {}
        for key, title in SECTIONS.items():
            panel = ttk.Frame(self.notebook, padding=9)
            self.notebook.add(panel, text=title)
            guide = ttk.Label(panel, text=GUIDES[key], wraplength=width - 60, justify='left')
            helpbar = ttk.Frame(panel)
            helpbar.pack(fill='x', pady=(0, 3))
            ttk.Button(helpbar, text='Alcance y ayuda ▸', command=lambda g=guide, b=helpbar: self.toggle_help(g, b)).pack(side='right')
            panel.bind('<Configure>', lambda e, label=guide: label.configure(wraplength=max(400, e.width - 30)))
            if key == 'red':
                commands = ttk.Frame(panel)
                commands.pack(fill='x', pady=(0, 7))
                self.url = tk.StringVar(value='http://127.0.0.1:8781/')
                ttk.Entry(commands, textvariable=self.url, width=43).pack(side='left')
                self.ca = tk.StringVar()
                ttk.Button(commands, text='Elegir CA pública…', command=self.choose_ca).pack(side='left', padx=4)
                ttk.Button(commands, text='TCP / TLS estricto', command=self.probe).pack(side='left')
                ttk.Label(panel, textvariable=self.ca, wraplength=1100).pack(anchor='w')
            if key == 'aplicaciones':
                ttk.Button(helpbar, text='Portal Ubuntu', command=lambda: self.open_url('https://192.168.0.62:8444/')).pack(side='left', padx=4)
                ttk.Button(helpbar, text='DEVIA demo local', command=lambda: self.open_url('http://127.0.0.1:8781/')).pack(side='left', padx=4)
                ttk.Button(helpbar, text='Comprobar salud de DEVIA local', command=lambda: self.work('health', lambda: [core.local_health()])).pack(side='left')
            if key == 'informes':
                ttk.Button(helpbar, text='Exportar resumen ZIP…', command=self.export).pack(side='left', padx=4)
                ttk.Button(helpbar, text='Resultados de pruebas', command=self.show_devia_tests).pack(side='left')
                ttk.Button(helpbar, text='Puntos de continuidad', command=self.show_checkpoints).pack(side='left', padx=4)
                ttk.Button(helpbar, text='Historial del centro', command=lambda: self.work('history', lambda: core.read_history(self.state_dir / 'events.jsonl'))).pack(side='left', padx=4)
            container = ttk.Frame(panel)
            container.pack(fill='both', expand=True)
            tree = ttk.Treeview(container, columns=('state', 'time'), show='tree headings', selectmode='browse', height=4)
            tree.heading('#0', text='Elemento ↕', command=lambda t=tree: self.sort_tree(t, '#0'))
            tree.heading('state', text='Estado ↕', command=lambda t=tree: self.sort_tree(t, 'state'))
            tree.heading('time', text='Fecha ↕', command=lambda t=tree: self.sort_tree(t, 'time'))
            tree.column('#0', width=440, minwidth=240)
            tree.column('state', width=145, stretch=False)
            tree.column('time', width=205, stretch=False)
            scroll = ttk.Scrollbar(container, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            horizontal = ttk.Scrollbar(container, orient='horizontal', command=tree.xview)
            tree.configure(xscrollcommand=horizontal.set)
            container.rowconfigure(0, weight=1)
            container.columnconfigure(0, weight=1)
            tree.grid(row=0, column=0, sticky='nsew')
            scroll.grid(row=0, column=1, sticky='ns')
            horizontal.grid(row=1, column=0, sticky='ew')
            tree.bind('<<TreeviewSelect>>', lambda e, t=tree: self.select(t))
            tree.bind('<<TreeviewOpen>>', lambda e, t=tree: self.populate_details(t,t.focus()))
            tree.tag_configure('fallo', foreground='#9c1f1f')
            tree.tag_configure('bloqueado', foreground='#875400')
            tree.tag_configure('correcto', foreground='#006d5b')
            self.trees[key] = tree
        detail = self.detail_panel = ttk.LabelFrame(self.panes, text='Ficha · arrastra el separador para ajustar su altura', padding=6)
        self.panes.add(detail, weight=1)
        self.detail = tk.Text(detail, height=5, wrap='word', font=('Segoe UI', 10))
        scroll = ttk.Scrollbar(detail, command=self.detail.yview)
        self.detail.configure(yscrollcommand=scroll.set, state='disabled')
        self.detail.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        bottom = ttk.Frame(self, padding=(14, 0, 14, 10))
        bottom.pack(fill='x')
        ttk.Button(bottom, text='Abrir ubicación', command=self.open_location).pack(side='left')
        ttk.Button(bottom, text='Copiar ficha local', command=self.copy_detail).pack(side='left', padx=5)
        self.status = tk.StringVar(value='Preparado. Las fichas pueden contener rutas e identidades locales privadas.')
        ttk.Label(bottom, textvariable=self.status, wraplength=max(350, width - 370)).pack(side='left', padx=8)
        bottom.pack_forget()
        bottom.pack(side='bottom', fill='x')
        self.panes.pack(fill='both', expand=True, padx=12, pady=5)
        self.bind('<F11>', lambda _: self.toggle_table())
        self.bind('<Escape>', lambda _: self.toggle_table() if self.table_maximized else None)
        self.bind('<Control-f>', lambda _: self.search_entry.focus_set())
        self.after(150, self.set_initial_sash)
        self.selected = None
        self.load_roots()
        self.after(100, self.poll)
        if autoload:
            self.after(50, self.show_home)
            self.after(100, self.load_context)

    def load_context(self):
        if self.closed or self._context_loaded or self.inventory_loaded or self.busy:
            return
        self._context_loaded = True
        self.rows.extend(equipment_summary.inventory(self.workspace))
        self.rows.append(dict(core.row('pendientes','Inventario de archivos pendiente','no_comprobado',
            'El arranque carga contexto documental. Actualizar inventario recorre las carpetas;Inventario Windows solicita las lecturas del sistema.'),source='startup_context'))
        self.render()
        self.status.set('Contexto documental cargado. Inventario completo pendiente de accion expresa.')

    def schedule_render(self):
        if self.closed:
            return
        if self._render_job is not None:
            self.after_cancel(self._render_job)
        self.selected = None
        self.visible = {}
        self.detail.configure(state='normal')
        self.detail.delete('1.0','end')
        self.detail.insert('1.0','Filtrando;la ficha anterior se ha retirado.')
        self.detail.configure(state='disabled')
        self._render_job = self.after(120,self.render)

    def populate_details(self,tree,iid):
        if not tree.exists(iid):
            return
        record = self.visible.get((str(tree),iid))
        placeholder = iid+':lazy'
        if record is None or not tree.exists(placeholder):
            return
        tree.delete(placeholder)
        self.visible.pop((str(tree),placeholder),None)
        for number,(title,value) in enumerate([('Ubicación',record['path'] or 'No aplica'),('Resultado',record['detail']),('Código',record['code'])]):
            child = tree.insert(iid,'end',iid=iid+':detail:'+str(number),text=title+': '+value)
            self.visible[(str(tree),child)] = record

    def set_initial_sash(self):
        if not self.closed and len(self.panes.panes()) > 1:
            self.panes.sashpos(0, max(180, self.panes.winfo_height() - 130))

    def toggle_help(self, guide, bar):
        if guide.winfo_manager():
            guide.pack_forget()
        else:
            guide.pack(after=bar, fill='x', pady=4)

    def toggle_table(self):
        if self.table_maximized:
            self.top.pack(before=self.filters, fill='x')
            self.panes.add(self.detail_panel, weight=1)
            self.max_button.configure(text='Ampliar tabla (F11)')
            self.after(50, self.set_initial_sash)
        else:
            self.top.pack_forget()
            self.panes.forget(self.detail_panel)
            self.max_button.configure(text='Restaurar ficha (Esc)')
        self.table_maximized = not self.table_maximized

    def clear_filters(self):
        self.search.set('')
        self.family_filter.set('Todas')
        self.state_filter.set('Todos')
        self.type_filter.set('Todos los tipos')

    @staticmethod
    def resource_type(record):
        for prefix in ('Documentación', 'Dependencias / despliegue', 'Arranque / operación',
                       'Pruebas disponibles', 'Cartografía / catálogo geográfico', 'Paquete / posible copia'):
            if record['name'].startswith(prefix):
                return prefix
        if record.get('source') == 'evidence':
            return 'Evidencia de pruebas'
        return SECTIONS.get(record['kind'], 'Otros')

    def sort_tree(self, tree, column, reverse=None):
        previous = self.sorting.get(str(tree))
        if reverse is None:
            reverse = previous == (column, False)
        self.sorting[str(tree)] = (column, reverse)
        def value(iid):
            if column == 'time':
                try:
                    return datetime.fromisoformat(tree.set(iid, column)).timestamp()
                except (ValueError, TypeError):
                    return float('-inf')
            return (tree.item(iid, 'text') if column == '#0' else tree.set(iid, column)).casefold()
        for group in tree.get_children():
            for position, iid in enumerate(sorted(tree.get_children(group), key=value, reverse=reverse)):
                tree.move(iid, group, position)
        for key, label in [('#0', 'Elemento'), ('state', 'Estado'), ('time', 'Fecha')]:
            tree.heading(key, text=label + (' ▼' if reverse else ' ▲') if key == column else label + ' ↕')

    def log(self, event, state, code='OK'):
        try:
            core.audit(self.state_dir / 'events.jsonl', event, state, code)
        except (OSError, ValueError):
            self.status.set('No se pudo guardar la traza local. Conserva el resultado mostrado.')

    def load_roots(self):
        file = self.state_dir / 'roots.json'
        if not file.exists():
            return
        try:
            data = json.loads(core.safe_file(file, self.workspace))
            if not isinstance(data, list) or len(data) > 20:
                raise ValueError('roots')
            for value in data:
                if isinstance(value, str):
                    path = Path(value).absolute()
                    if path.is_dir() and not core.linked(path) and path not in self.roots:
                        self.roots.append(path)
        except (OSError, ValueError, TypeError):
            self.status.set('Registro de carpetas inválido; se conserva la carpeta principal.')

    def add_root(self):
        name = filedialog.askdirectory(title='Carpeta de aplicaciones o informes que quieres inventariar')
        if not name:
            return
        path = Path(name).absolute()
        try:
            if core.linked(path):
                raise ValueError('link')
            if path not in self.roots:
                if len(self.roots) >= 20:
                    raise ValueError('limit')
                self.roots.append(path)
            self.state_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.state_dir / 'roots.tmp'
            tmp.write_text(json.dumps([str(p) for p in self.roots]), encoding='utf-8')
            tmp.replace(self.state_dir / 'roots.json')
            self.refresh()
        except (OSError, ValueError):
            self.status.set('No se pudo registrar esa carpeta. Comprueba permisos y evita enlaces.')

    def work(self, name, fn):
        if self.busy:
            self.status.set('Hay una comprobación en curso. Espera su resultado.')
            return
        self.busy = True
        self.refresh_button.configure(state='disabled')
        self.windows_button.configure(state='disabled')
        self.status.set('En curso: ' + name)
        def run():
            try:
                self.events.put((name, fn(), None))
            except Exception:
                self.events.put((name, [], 'READ_FAILED'))
        threading.Thread(target=run, daemon=True).start()

    def refresh(self):
        roots = list(self.roots)
        def collect():
            result = []
            # La carpeta privada se examina aparte para no perderla por el límite de la raíz.
            for root in roots:
                result.extend(core.scan(root))
            private = self.workspace / '.portal_private'
            if private.is_dir() and private not in roots:
                for name in ('entregas', 'recovery-20261007', 'coordinated', 'startup_reports'):
                    folder = private / name
                    if folder.is_dir():
                        result.extend(core.scan(folder))
            unique = {}
            for r in result:
                unique[(r['kind'], r['name'], r['path'], r['detail'])] = r
            result = list(unique.values())
            result.extend(evidence.inventory(self.workspace))
            result.extend(equipment_summary.inventory(self.workspace))
            result.append(core.row('actualizaciones', 'Catálogo remoto / instalación', 'no_comprobado',
                                   'Pendiente conector autorizado de releases y verificación de firmas. No hay actualización automática.'))
            return result
        self.work('scan', collect)

    def show_home(self):
        from .home_ui import HomeWindow
        if self.home_window is not None and self.home_window.winfo_exists():
            self.home_window.deiconify();self.home_window.lift();return
        self.home_window = HomeWindow(self,self.workspace)

    def show_delivery_access(self):
        from .delivery_access_ui import DeliveryAccessWindow
        DeliveryAccessWindow(self,self.workspace)

    def show_checkpoints(self):
        from .checkpoints_ui import CheckpointsWindow
        CheckpointsWindow(self,self.workspace)

    def show_use_cases(self):
        from .use_cases_ui import UseCasesWindow
        UseCasesWindow(self, self.workspace)

    def read_windows(self):
        self.work('windows', core.windows_inventory)

    def show_devia_tests(self):
        from .results_ui import ResultsWindow
        ResultsWindow(self, self.workspace)

    def choose_ca(self):
        name = filedialog.askopenfilename(title='CA pública existente (no clave privada)', filetypes=[('Certificados', '*.crt *.cer *.pem'), ('Todos', '*')])
        if name:
            self.ca.set(name)

    def probe(self):
        url, ca = self.url.get().strip(), self.ca.get().strip()
        self.work('probe', lambda: [core.probe(url, ca or None)])

    def poll(self):
        if self.closed:
            return
        try:
            name, result, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.refresh_button.configure(state='normal')
            self.windows_button.configure(state='normal')
            if error:
                self.rows.append(core.row('pendientes', name, 'fallo', 'No se completó. Sin mensajes de excepción privados.', code=error))
                self.status.set('Comprobación incompleta. Consulta Cobertura y pendientes.')
                if name not in {'history', 'evidence'}:
                    self.log(name, 'fallo', error)
            else:
                if name == 'scan':
                    self.inventory_loaded = True
                    self.rows = result + [r for r in self.rows if r.get('source') in {'windows', 'health', 'probe', 'history'}]
                elif name in {'windows', 'health', 'history', 'evidence'}:
                    self.rows = [r for r in self.rows if r.get('source') != name]
                    self.rows.extend(dict(r, source=name) for r in result)
                else:
                    self.rows.extend(dict(r, source=name) for r in result)
                self.status.set('Completado: ' + name + '. Consulta el estado de cada elemento.')
                if name not in {'history', 'evidence'}:
                    self.log(name, 'parcial' if any(r['state'] in {'fallo', 'bloqueado', 'parcial'} for r in result) else 'correcto')
            self.render()
        self.after(100, self.poll)

    def render(self):
        if self.closed:
            return
        if self._render_job is not None:
            self.after_cancel(self._render_job)
            self._render_job = None
        self.visible = {}
        self.selected = None
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', 'Selecciona una fila para ver su ficha completa. Ctrl+F: buscar · F11: ampliar tabla.')
        self.detail.configure(state='disabled')
        self.type_box.configure(values=['Todos los tipos'] + sorted({self.resource_type(r) for r in self.rows}))
        for tree in self.trees.values():
            tree.delete(*tree.get_children())
        query, wanted = self.search.get(), self.state_filter.get()
        count = 0
        omitted_files = sum(knowledge.is_file_metadata(r) for r in self.rows) if not self.include_files.get() else 0
        for i, r in self.search_index.select(self.rows,query):
            if not self.include_files.get() and knowledge.is_file_metadata(r):
                continue
            if self.type_filter.get() not in {'Todos los tipos', self.resource_type(r)}:
                continue
            family = core.family(r)
            if self.family_filter.get() not in {'Todas', family}:
                continue
            if wanted != 'Todos' and r['state'] != wanted:
                continue
            tree = self.trees.get(r['kind'], self.trees['pendientes'])
            iid = str(i)
            group = 'group:' + family
            if not tree.exists(group):
                tree.insert('', 'end', iid=group, text=family, open=True)
            tree.insert(group, 'end', iid=iid, text=r['name'], values=(r['state'], r['checked_at']), tags=(r['state'],))
            self.visible[(str(tree), iid)] = r
            child = tree.insert(iid,'end',iid=iid+':lazy',text='Desplegar para ver detalles')
            self.visible[(str(tree),child)] = r
            count += 1
        errors = sum(r['state'] in {'fallo', 'bloqueado'} for r in self.rows)
        for tree in self.trees.values():
            if str(tree) in self.sorting:
                self.sort_tree(tree, *self.sorting[str(tree)])
        inventory_scope = 'inventario de archivos disponible' if self.inventory_loaded else 'inventario de archivos pendiente'
        self.summary.set(f'{len(self.rows)} elementos locales ({inventory_scope}) · {count} visibles · {omitted_files} archivos/documentos ocultos · {errors} fallos/bloqueos · {len(self.roots)} carpeta(s) configurada(s). Producción no acreditada por este inventario.')

    def select(self, tree):
        selection = tree.selection()
        if not selection:
            return
        self.selected = self.visible.get((str(tree), selection[0]))
        if not self.selected:
            return
        r = self.selected
        content = f'{r["name"]}\nEstado: {r["state"]} | Código: {r["code"]}\nFecha: {r["checked_at"]}\nUbicación: {r["path"] or "No aplica"}\n\n{r["detail"]}\n\nAlcance: {GUIDES.get(r["kind"], GUIDES["pendientes"])}'
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        content += '\n\nOrientación: ' + core.ADVICE.get(r['code'], 'Revisa el alcance y conserva el código para soporte.')
        content += '\nGrupo orientativo por nombre/ruta: ' + core.family(r) + '. No acredita asociación con un proceso.'
        self.detail.insert('1.0', content)
        self.detail.configure(state='disabled')

    def expand(self, opened):
        tree = self.trees[list(SECTIONS)[self.notebook.index(self.notebook.select())]]
        for iid in tree.get_children():
            tree.item(iid, open=opened)
            for child in tree.get_children(iid):
                if opened:
                    self.populate_details(tree,child)
                tree.item(child, open=opened)

    def open_location(self):
        if not self.selected or not self.selected['path']:
            self.status.set('Selecciona un elemento con ubicación.')
            return
        try:
            path = Path(self.selected['path'])
            target = path if path.is_dir() else path.parent
            if not target.is_dir() or core.linked(target):
                raise ValueError('location')
            os.startfile(str(target))
            self.status.set('Ubicación solicitada: ' + str(target))
            self.log('open', 'correcto')
        except (OSError, ValueError, AttributeError):
            self.status.set('No se pudo abrir. La ruta se conserva en la ficha para copiarla.')
            self.log('open', 'fallo', 'READ_FAILED')

    def open_url(self, url):
        try:
            if not webbrowser.open(url):
                raise OSError('browser')
            self.status.set('Navegador solicitado. No acredita que el servicio responda.')
        except OSError:
            self.status.set('No se pudo abrir el navegador. URL: ' + url)

    def copy_detail(self):
        self.clipboard_clear()
        self.clipboard_append(self.detail.get('1.0', 'end-1c'))
        self.status.set('Ficha copiada. Contiene información local privada; revisa antes de compartir.')

    def export(self):
        if not self.rows:
            self.status.set('Primero actualiza el inventario.')
            return
        name = filedialog.asksaveasfilename(title='Resumen depurado: sin nombres, red, cuentas, rutas ni logs originales',
                                          defaultextension='.zip', initialfile='JDDC-resumen-' + core.now().replace(':', '-') + '.zip',
                                          filetypes=[('ZIP', '*.zip')])
        if not name:
            return
        try:
            core.export_zip(name, self.rows)
            self.status.set('ZIP verificado: ' + name)
            self.log('export', 'correcto')
        except Exception:
            self.status.set('No se pudo exportar. Usa un nombre nuevo y carpeta con permiso; los originales se conservan.')
            self.log('export', 'fallo', 'EXPORT_FAILED')

    def close(self):
        if self.closed:
            return
        self.closed = True
        # Cancel through the widget that registered each callback. Deleting a
        # child's Tcl command via the root leaves its cleanup registry stale.
        owners = {}
        def collect(widget):
            for command in getattr(widget, '_tclCommands', None) or ():
                owners[command] = widget
            for child in widget.winfo_children():
                collect(child)
        collect(self)
        for timer in self.tk.splitlist(self.tk.call('after', 'info')):
            info = self.tk.call('after', 'info', timer)
            command = self.tk.splitlist(info[0])[0]
            owner = owners.get(command)
            if owner is not None:
                owner.after_cancel(timer)
            else:
                self.tk.call('after', 'cancel', timer)
        self.destroy()
