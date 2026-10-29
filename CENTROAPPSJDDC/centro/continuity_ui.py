"""Portada de orientacion. Solo lectura de recursos curados; sin red o acciones de negocio."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from . import __version__,knowledge


class ContinuityWindow(tk.Toplevel):
    def __init__(self,parent,workspace):
        super().__init__(parent)
        self.workspace=Path(workspace).absolute();self.resources=[];self.visible={}
        self.title(f'Inicio y continuidad | Centro JDDC {__version__}')
        self.geometry(f'{min(1000,self.winfo_screenwidth()-40)}x{min(780,self.winfo_screenheight()-70)}')
        self.minsize(800,550)
        ttk.Label(self,text='Empezar, encontrar y continuar',font=('Segoe UI',15,'bold')).pack(anchor='w',padx=12,pady=(10,3))
        identity=ttk.Label(self,text=f'Version cargada:{__version__}\nCarpeta del proyecto:{self.workspace}\nCodigo abierto desde:{Path(__file__).resolve().parent.parent}',wraplength=900)
        identity.pack(anchor='w',padx=12)
        self.bind('<Configure>',lambda event:identity.configure(wraplength=max(500,event.width-30)) if event.widget is self else None)
        self.review=tk.StringVar()
        ttk.Label(self,textvariable=self.review,wraplength=900).pack(anchor='w',padx=12,pady=5)
        try:
            index=knowledge.load(self.workspace);self.resources=index['resources']
            self.review.set('Revision del indice:'+index['reviewed_at']+' | '+knowledge.age_text(index['reviewed_at'])+'. No acredita estado actual de servicios.')
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            self.review.set('Indice no disponible o invalido. Leer CENTROAPPSJDDC/docs/EMPEZAR-AQUI.txt y AGENTS.md; comprobar carpeta/version. No se presume continuidad verificada.')
        shortcuts=ttk.Frame(self,padding=(10,2));shortcuts.pack(fill='x')
        for label,key in [('Empezar aqui','start'),('Resumen','summary'),('Retomar','resume'),('Mantener indice','handover')]:
            ttk.Button(shortcuts,text=label,command=lambda target=key:self.choose(target)).pack(side='left',padx=3)
        ttk.Button(shortcuts,text='Guia por tareas',command=parent.show_use_cases).pack(side='left',padx=3)
        ttk.Button(shortcuts,text='Volver al inventario',command=self.destroy).pack(side='right')
        filters=ttk.Frame(self,padding=(12,5));filters.pack(fill='x')
        ttk.Label(filters,text='Buscar en el indice').pack(side='left')
        self.query=tk.StringVar();self.kind=tk.StringVar(value='Todos')
        self.search=ttk.Entry(filters,textvariable=self.query);self.search.pack(side='left',fill='x',expand=True,padx=6)
        ttk.Combobox(filters,textvariable=self.kind,values=['Todos']+sorted(knowledge.KINDS),state='readonly',width=20).pack(side='left')
        ttk.Button(filters,text='Ver cambios',command=parent.show_checkpoints).pack(side='left',padx=(6,0))
        ttk.Button(filters,text='Entregas y accesos',command=parent.show_delivery_access).pack(side='left',padx=(6,0))
        panes=ttk.Panedwindow(self,orient='vertical');panes.pack(fill='both',expand=True,padx=12,pady=(0,10))
        table=ttk.Frame(panes);panes.add(table,weight=2)
        self.tree=ttk.Treeview(table,columns=('kind','age'),show='tree headings',height=6,selectmode='browse')
        self.tree.heading('#0',text='Recurso');self.tree.column('#0',width=360,minwidth=200)
        self.tree.heading('kind',text='Tipo');self.tree.column('kind',width=150,minwidth=100)
        self.tree.heading('age',text='Antiguedad de la referencia');self.tree.column('age',width=210,minwidth=170)
        scroll=ttk.Scrollbar(table,command=self.tree.yview);scroll.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scroll.set);self.tree.pack(fill='both',expand=True)
        panel=ttk.Frame(panes);panes.add(panel,weight=4)
        self.text=tk.Text(panel,wrap='word',height=15,padx=10,pady=8)
        scroll=ttk.Scrollbar(panel,command=self.text.yview);scroll.pack(side='right',fill='y')
        self.text.configure(yscrollcommand=scroll.set);self.text.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',self.show_selected)
        self.query.trace_add('write',lambda *_:self.render());self.kind.trace_add('write',lambda *_:self.render())
        self.bind('<Control-f>',lambda _:self.search.focus_set())
        self.render();self.choose('start')
        self.after(100,lambda:panes.sashpos(0,max(140,panes.winfo_height()//3)) if self.winfo_exists() else None)

    def write(self,text):
        self.text.configure(state='normal');self.text.delete('1.0','end');self.text.insert('1.0',text);self.text.configure(state='disabled')

    def render(self):
        self.tree.delete(*self.tree.get_children())
        self.visible={r['id']:r for r in knowledge.find(self.resources,self.query.get(),self.kind.get())}
        for key,r in self.visible.items():self.tree.insert('', 'end',iid=key,text=r['title'],values=(r['kind'],knowledge.age_text(r['observed_at'])))
        self.write('Selecciona un recurso. La busqueda consulta titulos,descripciones y rutas del indice;el inventario permite ampliar a otros archivos. No se leen logs privados para indexarlos.')

    def choose(self,key):
        self.query.set('');self.kind.set('Todos')
        if key in self.visible:
            self.tree.selection_set(key);self.tree.see(key);self.show_selected()

    def show_selected(self,event=None):
        selected=self.tree.selection()
        if not selected:return
        resource=self.visible.get(selected[0])
        if not resource:return
        header=f"{resource['title']} | {resource['kind']}\nReferencia:{resource['path']}\nFecha de referencia:{resource['observed_at'] or 'no especificada'} | {knowledge.age_text(resource['observed_at'])}\n\n"
        try:content=knowledge.read_resource(self.workspace,resource)
        except (OSError,ValueError,UnicodeError,RecursionError):content='Recurso ausente,no legible o fuera del alcance permitido. Revisar ruta en CONTINUIDAD.json;no se presume encontrado ni se intenta ejecutar.'
        self.write(header+content)
