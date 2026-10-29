"""Project dashboard with nested navigation, search and explicit exports."""
from pathlib import Path
import os, queue, threading, tkinter as tk, webbrowser
from tkinter import ttk, filedialog
from . import __version__, knowledge, project_catalog as projects, delivery_access

PAGE_SIZE=100

class HomeWindow(tk.Toplevel):
    def __init__(self,parent,workspace):
        super().__init__(parent)
        self.workspace=Path(workspace).absolute();self.model=projects.Catalog()
        self.current='root';self.folder='';self.page=0;self.visible={};self.selected=None
        self.history=[];self.future=[];self._job=None;self._closed=False;self._changing=False
        self.events=queue.Queue();self.worker=None;self.cancel_export=threading.Event()
        self.title(f'Proyectos | Centro JDDC {__version__}')
        self.geometry(f'{min(1320,self.winfo_screenwidth()-40)}x{min(850,self.winfo_screenheight()-80)}+12+12');self.minsize(860,580)
        self.protocol('WM_DELETE_WINDOW',self.destroy)
        style=ttk.Style(self);style.configure('Hero.TLabel',font=('Segoe UI',21,'bold'),foreground='#103b50')
        style.configure('Metric.TButton',font=('Segoe UI',11,'bold'),padding=(10,10));style.configure('Caption.TLabel',font=('Segoe UI',9),foreground='#526977')
        self.columnconfigure(0,weight=1);self.rowconfigure(4,weight=1)
        hero=ttk.Frame(self,padding=(16,10,16,4));hero.grid(row=0,column=0,sticky='ew');hero.columnconfigure(0,weight=1)
        ttk.Label(hero,text='Tu espacio de proyectos',style='Hero.TLabel').grid(row=0,column=0,sticky='w')
        ttk.Label(hero,text=f'Centro JDDC {__version__}',style='Caption.TLabel').grid(row=0,column=1,sticky='e')
        self.review=tk.StringVar();ttk.Label(hero,textvariable=self.review,style='Caption.TLabel',wraplength=850).grid(row=1,column=0,columnspan=2,sticky='w',pady=(2,0))
        cards=ttk.Frame(self,padding=(14,4));cards.grid(row=1,column=0,sticky='ew');self.metrics=[]
        for i,(label,kind) in enumerate([('Proyectos','Proyecto'),('Guias','Guia'),('Entregas','Entrega'),('Pendientes','Pendiente')]):
            cards.columnconfigure(i,weight=1);b=ttk.Button(cards,text=label,style='Metric.TButton',command=lambda k=kind:self.quick_filter(k));b.grid(row=0,column=i,sticky='ew',padx=3);self.metrics.append((b,label,kind))
        toolbar=ttk.Frame(self,padding=(16,3));toolbar.grid(row=2,column=0,sticky='ew')
        self.back_button=ttk.Button(toolbar,text='\u2190',width=3,command=self.back);self.back_button.pack(side='left')
        self.forward_button=ttk.Button(toolbar,text='\u2192',width=3,command=self.forward);self.forward_button.pack(side='left',padx=3)
        ttk.Button(toolbar,text='Subir',command=self.up).pack(side='left');ttk.Button(toolbar,text='Inicio',command=lambda:self.navigate('root')).pack(side='left',padx=3)
        self.breadcrumb=ttk.Frame(toolbar);self.breadcrumb.pack(side='left',fill='x',expand=True,padx=8)
        more=ttk.Menubutton(toolbar,text='Herramientas \u25be');more.pack(side='right');menu=tk.Menu(more,tearoff=False);more.configure(menu=menu)
        for label,command in [('Guias y continuidad',self.show_continuity),('Guia por tareas',parent.show_use_cases),('Entregas y accesos',parent.show_delivery_access),('Cambios desde otra visita',parent.show_checkpoints),('Inventario de archivos y Windows',self.show_inventory),('Actualizar catalogo local',self.reload)]:menu.add_command(label=label,command=command)
        menu.add_separator();menu.add_command(label='GitHub:codigo y descarga publica',command=lambda:webbrowser.open('https://github.com/miguel-martin-jddc/jddc_materiales_local_bd_ia/tree/centro-jddc-017-20261029/CENTROAPPSJDDC'))
        filters=ttk.Frame(self,padding=(16,5));filters.grid(row=3,column=0,sticky='ew');filters.columnconfigure(1,weight=1)
        ttk.Label(filters,text='Buscar todo').grid(row=0,column=0,sticky='w')
        self.query=tk.StringVar();self.kind=tk.StringVar(value='Todos');self.state_filter=tk.StringVar(value='Todos');self.scope=tk.StringVar(value='Todo el catalogo');self.tag=tk.StringVar(value='Todas')
        self.search=ttk.Entry(filters,textvariable=self.query);self.search.grid(row=0,column=1,sticky='ew',padx=8);ttk.Button(filters,text='Limpiar',command=self.clear_search).grid(row=0,column=2)
        bar=ttk.Frame(filters);bar.grid(row=1,column=0,columnspan=3,sticky='ew',pady=(5,0))
        for label,var,values,width in [('Tipo',self.kind,['Todos']+list(projects.KINDS),12),('Estado',self.state_filter,['Todos'],21),('Buscar en',self.scope,['Todo el catalogo','Nivel y descendientes'],22)]:
            ttk.Label(bar,text=label).pack(side='left',padx=(0,4));box=ttk.Combobox(bar,textvariable=var,values=values,state='readonly',width=width);box.pack(side='left',padx=(0,10))
            if var is self.state_filter:self.state_box=box
        tagbar=ttk.Frame(filters);tagbar.grid(row=2,column=0,columnspan=3,sticky='ew',pady=(4,0))
        ttk.Label(tagbar,text='Etiqueta transversal').pack(side='left');self.tag_box=ttk.Combobox(tagbar,textvariable=self.tag,values=['Todas'],state='readonly',width=22);self.tag_box.pack(side='left',padx=8)
        ttk.Label(tagbar,text='Un proyecto, varias etiquetas:ERP,IA,Seguridad...',style='Caption.TLabel').pack(side='left')
        self.main=ttk.Panedwindow(self,orient='horizontal');self.main.grid(row=4,column=0,sticky='nsew',padx=16,pady=(3,5))
        left=ttk.Frame(self.main);self.main.add(left,weight=1);leftbar=ttk.Frame(left);leftbar.pack(fill='x')
        ttk.Label(leftbar,text='AREAS Y PROYECTOS',style='Caption.TLabel').pack(side='left');ttk.Button(leftbar,text='Plegar',command=self.collapse,width=7).pack(side='right')
        self.nav=self.make_tree(left,(),(),10);self.nav.heading('#0',text='Clasificacion');self.nav.column('#0',width=230,minwidth=140);self.nav.bind('<<TreeviewSelect>>',self.nav_select);self.nav.bind('<<TreeviewOpen>>',lambda _:self.populate_nav(self.nav.focus()))
        middle=ttk.Frame(self.main);self.main.add(middle,weight=4);self.section_title=tk.StringVar(value='Vista general')
        ttk.Label(middle,textvariable=self.section_title,font=('Segoe UI',13,'bold')).pack(anchor='w',pady=(2,5));self.family_bar=ttk.Frame(middle);self.family_bar.pack(fill='x',pady=(0,5))
        self.tree=self.make_tree(middle,('kind','state'),('Tipo','Estado'),11);self.tree.column('#0',width=330,minwidth=160);self.tree.column('kind',width=90,minwidth=65);self.tree.column('state',width=160,minwidth=90)
        self.tree.bind('<<TreeviewSelect>>',self.show_selected);self.tree.bind('<Double-1>',lambda _:self.open_selected());self.tree.bind('<Return>',lambda _:self.open_selected())
        pager=ttk.Frame(middle);pager.pack(fill='x',pady=5);self.previous_page=ttk.Button(pager,text='Anterior',command=lambda:self.turn_page(-1));self.previous_page.pack(side='left')
        self.results_label=tk.StringVar();ttk.Label(pager,textvariable=self.results_label).pack(side='left',padx=8);self.next_page=ttk.Button(pager,text='Siguiente',command=lambda:self.turn_page(1));self.next_page.pack(side='right')
        self.details=ttk.Frame(self.main);self.main.add(self.details,weight=2);ttk.Label(self.details,text='FICHA Y ACCIONES',style='Caption.TLabel').pack(anchor='w',pady=(4,7))
        panel=ttk.Frame(self.details);panel.pack(fill='both',expand=True)
        self.text=tk.Text(panel,wrap='word',height=8,width=30,font=('Segoe UI',10),padx=10,pady=10,relief='flat',background='white',foreground='#193542')
        scroll=ttk.Scrollbar(panel,command=self.text.yview);scroll.pack(side='right',fill='y');self.text.configure(yscrollcommand=scroll.set);self.text.pack(fill='both',expand=True)
        actions=ttk.Frame(self.details);actions.pack(fill='x',pady=5);actions.columnconfigure((0,1),weight=1)
        self.open_button=ttk.Button(actions,text='Explorar / leer',command=self.open_selected);self.open_button.grid(row=0,column=0,sticky='ew',padx=(0,3),pady=2)
        self.locate_button=ttk.Button(actions,text='Abrir carpeta',command=self.locate);self.locate_button.grid(row=0,column=1,sticky='ew',pady=2)
        self.download_button=ttk.Button(actions,text='Descargar ZIP',command=self.download);self.download_button.grid(row=1,column=0,sticky='ew',padx=(0,3),pady=2)
        self.copy_button=ttk.Button(actions,text='Copiar referencia',command=self.copy_reference);self.copy_button.grid(row=1,column=1,sticky='ew',pady=2)
        footer=ttk.Frame(self,padding=(16,2,16,8));footer.grid(row=5,column=0,sticky='ew');footer.columnconfigure(0,weight=1);self.message=tk.StringVar()
        ttk.Label(footer,textvariable=self.message,style='Caption.TLabel',wraplength=650).grid(row=0,column=0,sticky='w')
        self.export_all_button=ttk.Button(footer,text='Descargar todos los proyectos...',command=lambda:self.start_export(True));self.export_all_button.grid(row=0,column=1,padx=5)
        self.cancel_button=ttk.Button(footer,text='Cancelar',command=self.cancel_export.set,state='disabled');self.cancel_button.grid(row=0,column=2)
        for var in (self.query,self.kind,self.state_filter,self.scope,self.tag):var.trace_add('write',self.schedule_search)
        for key,fn in [('<Control-f>',lambda:self.search.focus_set()),('<Alt-Left>',self.back),('<Alt-Right>',self.forward),('<Alt-Up>',self.up),('<Escape>',self.clear_search)]:self.bind(key,lambda _,f=fn:f())
        self.reload();self._poll_job=self.after(100,self.poll_export);self.after_idle(self.initial_layout)

    def make_tree(self,parent,columns,headings,height):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True);tree=ttk.Treeview(frame,columns=columns,show='tree headings',selectmode='browse',height=height)
        for key,label in zip(columns,headings):tree.heading(key,text=label)
        y=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);y.pack(side='right',fill='y');x=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview);x.pack(side='bottom',fill='x')
        tree.configure(yscrollcommand=y.set,xscrollcommand=x.set);tree.pack(fill='both',expand=True);return tree
    def initial_layout(self):
        if not self._closed:
            width=self.main.winfo_width();self.main.sashpos(0,max(160,int(width*.21)));self.main.sashpos(1,max(490,int(width*.72)))
    def reload(self):
        try:
            self.model=projects.build(self.workspace);self.review.set(f'{len(self.model.projects)} proyectos | {len(self.model.nodes)-1} referencias | Revision {self.model.reviewed_at[:10]}. Estado remoto no comprobado.')
            self.message.set('Ctrl+F:buscar. Doble clic:profundizar. Alt+izquierda:volver.'+(' Avisos: '+'; '.join(self.model.warnings[:2]) if self.model.warnings else ''))
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            self.model=projects.Catalog();self.review.set('Catalogo de proyectos no disponible. Herramientas > Guias y continuidad conserva las referencias documentales.')
        self._changing=True;self.query.set('');self.kind.set('Todos');self.state_filter.set('Todos');self.scope.set('Todo el catalogo');self._changing=False
        self.tag_box.configure(values=['Todas']+sorted({t for p in self.model.projects.values() for t in p['tags']}));self.tag.set('Todas')
        self.state_box.configure(values=['Todos']+sorted({n.state for n in self.model.nodes.values()}));self.nav.delete(*self.nav.get_children());self.nav.insert('','end',iid='root',text='Todos los proyectos',open=True)
        self.populate_nav('root')
        for b,label,kind in self.metrics:
            count=len({n.path or n.payload.get('id',n.id) for n in self.model.nodes.values() if n.kind==kind})
            b.configure(text=f'{count}  {label}')
        self.current='root';self.folder='';self.page=0;self.history=[];self.future=[];self.render()
    def snapshot(self):return (self.current,self.folder,self.query.get(),self.kind.get(),self.state_filter.get(),self.scope.get(),self.page,self.tag.get())
    def restore(self,snapshot):
        self.current,self.folder,q,k,s,scope,self.page,tag=snapshot;self._changing=True;self.query.set(q);self.kind.set(k);self.state_filter.set(s);self.scope.set(scope);self.tag.set(tag);self._changing=False;self.render()
    def navigate(self,key,folder=''):
        if key not in self.model.nodes:return
        self.history.append(self.snapshot());self.history=self.history[-150:];self.future=[];self._changing=True;self.query.set('');self.kind.set('Todos');self.state_filter.set('Todos');self.tag.set('Todas');self._changing=False
        self.current=key;self.folder=folder;self.page=0;self.render()
    def back(self):
        if self.history:self.future.append(self.snapshot());self.restore(self.history.pop())
    def forward(self):
        if self.future:self.history.append(self.snapshot());self.restore(self.future.pop())
    def up(self):
        if self.folder:
            n=self.model.nodes[self.current];parent=Path(self.folder).parent.as_posix();self.navigate(self.current,parent if self.folder!=n.path and parent!='.' else '')
        elif self.current!='root':self.navigate(self.model.nodes[self.current].parent)
    def nav_select(self,event=None):
        selected=self.nav.selection()
        if selected and selected[0]!=self.current:self.navigate(selected[0])
    def populate_nav(self,key):
        if key not in self.model.nodes or not self.nav.exists(key):return
        placeholder=key+':nav-placeholder'
        if self.nav.exists(placeholder):self.nav.delete(placeholder)
        for id in self.model.children[key]:
            n=self.model.nodes[id]
            if n.kind not in {'Familia','Proyecto','Seccion'} or self.nav.exists(id):continue
            count=self.model.project_counts[id];self.nav.insert(key,'end',iid=id,text=n.title+(f' ({count})' if count else ''))
            if any(self.model.nodes[k].kind in {'Familia','Proyecto','Seccion'} for k in self.model.children[id]):self.nav.insert(id,'end',iid=id+':nav-placeholder',text='...')
    def sync_nav(self):
        for key in self.model.trail(self.current):
            if self.nav.exists(key):self.populate_nav(key)
        if self.nav.exists(self.current):
            self.nav.selection_set(self.current);self.nav.see(self.current)
    def collapse(self):
        for key in self.model.nodes:
            if key!='root' and self.nav.exists(key):self.nav.item(key,open=False)
    def quick_filter(self,kind):self.navigate('root');self.kind.set(kind);self.flush_search()
    def clear_search(self):
        self._changing=True;self.query.set('');self.kind.set('Todos');self.state_filter.set('Todos');self.tag.set('Todas');self._changing=False;self.page=0;self.render()
    def schedule_search(self,*_):
        if self._changing or self._closed:return
        if self._job:self.after_cancel(self._job)
        self.selected=None;self.action_states();self.write('Actualizando resultados...');self._job=self.after(140,self.flush_search)
    def flush_search(self):
        if self._job:self.after_cancel(self._job);self._job=None
        self.page=0;self.render()
    def render(self):
        if self._closed:return
        if self._job:self.after_cancel(self._job);self._job=None
        self.selected=None;self.visible={};self.tree.delete(*self.tree.get_children());self.action_states();self.back_button.configure(state='normal' if self.history else 'disabled');self.forward_button.configure(state='normal' if self.future else 'disabled')
        self.sync_nav()
        for c in self.breadcrumb.winfo_children():c.destroy()
        trail=self.model.trail(self.current);crumb=ttk.Menubutton(self.breadcrumb,text=' / '.join(self.model.nodes[k].title for k in trail[-2:])+' \u25be');crumb.pack(anchor='w');menu=tk.Menu(crumb,tearoff=False);crumb.configure(menu=menu)
        for key in trail:menu.add_command(label=self.model.nodes[key].title,command=lambda k=key:self.navigate(k))
        for c in self.family_bar.winfo_children():c.destroy()
        active=bool(self.query.get().strip() or self.kind.get()!='Todos' or self.state_filter.get()!='Todos' or self.tag.get()!='Todas');self.section_title.set(('Resultados de busqueda' if active else self.model.nodes[self.current].title)+((' / '+Path(self.folder).name) if self.folder else ''))
        if self.current=='root' and not active:
            for i,key in enumerate(self.model.children['root']):
                self.family_bar.columnconfigure(i%3,weight=1);n=self.model.nodes[key];ttk.Button(self.family_bar,text=f'{n.title} ({self.model.project_counts[key]})',command=lambda k=key:self.navigate(k)).grid(row=i//3,column=i%3,sticky='ew',padx=2,pady=2)
        if active:rows=self.model.search(self.query.get(),self.current if self.scope.get()!='Todo el catalogo' else 'root',self.kind.get(),self.state_filter.get(),self.tag.get())
        elif self.folder:
            try:
                found,partial=projects.folder_entries(self.workspace,self.folder);rows=[projects.Node('file:'+str(i),Path(p).name,'Codigo',self.current,'Subcarpeta' if isdir else 'Archivo local;no se ejecuta desde el explorador.',p,project=self.model.nodes[self.current].project,payload={'is_dir':isdir}) for i,(p,isdir) in enumerate(found)]
                if partial:self.message.set('Carpeta limitada a500 entradas examinadas. Abrir carpeta permite consultar el resto.')
            except (OSError,ValueError):rows=[];self.message.set('Carpeta no disponible o ruta protegida.')
        else:rows=[self.model.nodes[k] for k in self.model.children[self.current]]
        self.total=len(rows);self.page=min(self.page,max(0,(self.total-1)//PAGE_SIZE));start=self.page*PAGE_SIZE
        for n in rows[start:start+PAGE_SIZE]:
            self.visible[n.id]=n;title=n.title+(f' ({self.model.project_counts[n.id]} proyectos)' if n.kind=='Familia' else '');self.tree.insert('','end',iid=n.id,text=title,values=(n.kind,n.state))
        self.results_label.set(f'{start+1 if rows else 0}\u2013{min(start+PAGE_SIZE,self.total)} de {self.total}');self.previous_page.configure(state='normal' if self.page else 'disabled');self.next_page.configure(state='normal' if start+PAGE_SIZE<self.total else 'disabled')
        self.write('Selecciona un elemento para ver su ficha y acciones.\n\n'+self.model.nodes[self.current].description+'\n\nCodigo y documentos locales no acreditan que el servicio este activo. Campanas pausadas;ERP real solo lectura.' if rows else 'Sin resultados. Prueba otra palabra,limpia los filtros o selecciona Todo el catalogo. Los contenidos privados no se indexan.')
    def turn_page(self,direction):self.page=max(0,self.page+direction);self.render()
    def write(self,text):self.text.configure(state='normal');self.text.delete('1.0','end');self.text.insert('1.0',text);self.text.configure(state='disabled')
    def show_selected(self,event=None):
        keys=self.tree.selection();self.selected=self.visible.get(keys[0]) if keys else None;self.action_states();n=self.selected
        if not n:return
        parts=[n.title,n.kind+' | '+n.state,'',n.description]
        if n.project:parts+=['','Proyecto: '+self.model.projects[n.project]['title'],'Etiquetas: '+', '.join(self.model.projects[n.project]['tags'])]
        if n.path:
            try:available=projects.local_path(self.workspace,n.path).exists()
            except (OSError,ValueError):available=False
            parts+=['','Ruta: '+n.path,'Localizado' if available else 'No disponible en esta copia']
        if n.kind=='Guia':parts+=['Fecha de referencia: '+str(n.payload.get('observed_at') or 'no especificada'),'Explorar / leer abre la vista previa.']
        if n.kind=='Acceso':parts+=['',n.payload['location'],'Siguiente paso: '+n.payload['next_step'],'Los valores de credenciales no se recuperan.']
        if n.kind=='Pendiente':parts+=['','Responsable: '+n.payload['owner'],'Aceptacion: '+n.payload['acceptance']]
        if n.kind=='Proyecto':parts+=['','Explorar:codigo,guias,entregas,pendientes y accesos. Descargar ZIP:fuentes y documentos con exclusiones;no instala el proyecto.']
        self.write('\n'.join(parts))
    def action_states(self):
        n=self.selected
        for b in (self.open_button,self.copy_button):b.configure(state='normal' if n else 'disabled')
        self.locate_button.configure(state='normal' if n and (n.path or n.kind=='Proyecto') else 'disabled');self.download_button.configure(state='normal' if n and (n.kind in {'Proyecto','Entrega'} or n.project) and self.worker is None else 'disabled')
    def open_selected(self):
        n=self.selected
        if not n:return
        if n.kind in {'Familia','Proyecto','Seccion'}:self.navigate(n.id)
        elif n.kind=='Codigo':
            try:
                if projects.local_path(self.workspace,n.path).is_dir():self.navigate(n.id if n.id in self.model.nodes else self.current,n.path)
                else:self.message.set('Abrir carpeta localiza el archivo;no se ejecuta desde el Centro.')
            except (OSError,ValueError):self.message.set('Ruta no disponible o protegida.')
        elif n.kind=='Guia':
            try:self.write(n.title+'\n\n'+knowledge.read_resource(self.workspace,n.payload))
            except (OSError,ValueError,UnicodeError):self.write('Recurso ausente o no legible. Revisar su referencia.')
        elif n.kind in {'Entrega','Acceso'}:self.master.show_delivery_access()
        elif n.kind=='Pendiente':self.master.show_use_cases()
    def locate(self):
        n=self.selected
        if not n:return
        relative=n.path or next(iter(self.model.projects[n.project]['roots']),'')
        try:
            path=projects.local_path(self.workspace,relative)
            if not path.is_dir():path=path.parent
            if os.name!='nt':raise ValueError('Windows only')
            os.startfile(str(path));self.message.set('Carpeta solicitada;no se ejecuta ningun archivo.')
        except (OSError,ValueError):self.message.set('Carpeta ausente o protegida.')
    def copy_reference(self):
        n=self.selected
        if n:self.clipboard_clear();self.clipboard_append(n.title+'\n'+(n.path or n.id));self.message.set('Referencia local copiada. Revisar antes de compartir.')
    def show_continuity(self):
        from .continuity_ui import ContinuityWindow
        ContinuityWindow(self.master,self.workspace)
    def show_inventory(self):self.master.deiconify();self.master.lift();self.lower()
    def download(self):
        n=self.selected
        if not n:return
        if n.kind=='Entrega':
            chosen=filedialog.asksaveasfilename(parent=self,title='Guardar copia sin sobrescribir',initialfile=Path(n.path).name,defaultextension='.zip',filetypes=[('ZIP','*.zip')])
            if chosen:self.launch_export(lambda:delivery_access.copy_to(self.workspace,n.payload,chosen))
        else:self.start_export(False)
    def start_export(self,all_projects=False):
        if self.worker is not None:return
        from .project_export import export_sources
        selected=list(self.model.projects.values()) if all_projects else [self.model.projects[self.selected.project]] if self.selected and self.selected.project else []
        if not selected:self.message.set('Selecciona un proyecto.');return
        chosen=filedialog.asksaveasfilename(parent=self,title='Exportar fuentes y documentos;sin configuraciones privadas',initialfile=('PROYECTOS-JDDC' if all_projects else selected[0]['id'])+'-fuentes.zip',defaultextension='.zip',filetypes=[('ZIP','*.zip')])
        if chosen:self.launch_export(lambda:export_sources(self.workspace,selected,chosen,self.cancel_export,lambda text:self.events.put(('progress',text))))
    def launch_export(self,fn):
        if self.worker is not None:return
        self.cancel_export.clear();self.export_all_button.configure(state='disabled');self.cancel_button.configure(state='normal');self.message.set('Preparando copia local en segundo plano...')
        def work():
            try:self.events.put(('done',fn()))
            except Exception as exc:self.events.put(('error',type(exc).__name__))
        self.worker=threading.Thread(target=work,daemon=True);self.action_states();self.worker.start()
    def poll_export(self):
        if self._closed:return
        try:
            while True:
                event,data=self.events.get_nowait()
                if event=='progress':self.message.set(data)
                else:
                    self.worker=None;self.export_all_button.configure(state='normal');self.cancel_button.configure(state='disabled');self.action_states()
                    self.message.set('Copia finalizada y verificada. Revisar el manifiesto antes de compartir.' if event=='done' else 'Copia no completada o cancelada. No se sobrescriben archivos existentes;revisar limites,permisos e integridad.')
        except queue.Empty:pass
        self._poll_job=self.after(100,self.poll_export)
    def destroy(self):
        if self._closed:return
        self._closed=True;self.cancel_export.set()
        for job in (self._job,getattr(self,'_poll_job',None)):
            if job:
                try:self.after_cancel(job)
                except tk.TclError:pass
        super().destroy()
