"""Guia local por perfil y problema; abrirla no inicia red, ERP, correo o tareas."""
import tkinter as tk
from tkinter import ttk
from . import use_cases


class UseCasesWindow(tk.Toplevel):
    def __init__(self,parent,workspace):
        super().__init__(parent)
        self.title('Guia por tareas y mejoras | Centro JDDC')
        self.geometry(f'{min(1060,self.winfo_screenwidth()-40)}x{min(760,self.winfo_screenheight()-70)}')
        self.minsize(800,540)
        self.items=[];self.visible={}
        self.role=tk.StringVar(value='Todos');self.priority=tk.StringVar(value='Todas')
        self.status=tk.StringVar(value='Todos');self.app=tk.StringVar(value='Todas');self.query=tk.StringVar()
        self.count=tk.StringVar()
        ttk.Label(self,text='Que necesita hacer cada empleado y que app interviene',font=('Segoe UI',13,'bold')).pack(anchor='w',padx=12,pady=(10,3))
        ttk.Label(self,text='Propuestas, candidatos locales y dependencias del servidor separados. Esta guia no ejecuta acciones.',wraplength=950).pack(anchor='w',padx=12)
        filters=ttk.Frame(self,padding=10);filters.pack(fill='x')
        try:self.items=use_cases.load(workspace)
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            ttk.Label(self,text='No se pudo validar el catalogo local. Consultar el informe de mejoras.').pack(pady=25)
            return
        choices=[('Perfil',self.role,['Todos']+sorted({r for x in self.items for r in x['roles']}),17),
                 ('Prioridad',self.priority,['Todas','P0','P1','P2'],7),
                 ('Estado',self.status,['Todos']+sorted(use_cases.STATUSES),19)]
        for label,var,values,width in choices:
            ttk.Label(filters,text=label).pack(side='left',padx=(0,4))
            ttk.Combobox(filters,textvariable=var,values=values,state='readonly',width=width).pack(side='left',padx=(0,8))
        search=ttk.Frame(self,padding=(10,0,10,8));search.pack(fill='x')
        ttk.Label(search,text='App').pack(side='left')
        ttk.Combobox(search,textvariable=self.app,values=['Todas']+sorted({x['app'] for x in self.items}),state='readonly',width=30).pack(side='left',padx=5)
        ttk.Label(search,text='Buscar').pack(side='left')
        self.search=ttk.Entry(search,textvariable=self.query);self.search.pack(side='left',fill='x',expand=True,padx=5)
        ttk.Button(search,text='Limpiar',command=self.clear).pack(side='left')
        ttk.Label(self,textvariable=self.count).pack(anchor='w',padx=12)
        panes=ttk.Panedwindow(self,orient='vertical');panes.pack(fill='both',expand=True,padx=10,pady=8)
        table=ttk.Frame(panes);panes.add(table,weight=3)
        self.tree=ttk.Treeview(table,columns=('priority','app','state'),show='tree headings',height=10)
        self.tree.heading('#0',text='Necesidad del empleado / sistema');self.tree.column('#0',width=370,minwidth=220)
        for key,title,width in [('priority','Prioridad',65),('app','App',230),('state','Estado',160)]:
            self.tree.heading(key,text=title);self.tree.column(key,width=width,minwidth=60)
        scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);scroll.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scroll.set);self.tree.pack(fill='both',expand=True)
        details=ttk.Frame(panes);panes.add(details,weight=2)
        self.detail=tk.Text(details,wrap='word',height=10,padx=8,pady=6)
        detail_scroll=ttk.Scrollbar(details,orient='vertical',command=self.detail.yview);detail_scroll.pack(side='right',fill='y')
        self.detail.configure(yscrollcommand=detail_scroll.set);self.detail.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',self.show_detail)
        for var in (self.role,self.priority,self.status,self.app,self.query):var.trace_add('write',lambda *_:self.render())
        self.bind('<Control-f>',lambda _:self.search.focus_set())
        self.render()
        self.after(100,lambda:panes.sashpos(0,max(180,panes.winfo_height()*3//5)) if self.winfo_exists() else None)

    def clear(self):
        self.role.set('Todos');self.priority.set('Todas');self.status.set('Todos');self.app.set('Todas');self.query.set('')

    def set_detail(self,text):
        self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.insert('1.0',text);self.detail.configure(state='disabled')

    def render(self):
        selected=use_cases.select(self.items,self.role.get(),self.priority.get(),self.status.get(),self.app.get(),self.query.get())
        self.tree.delete(*self.tree.get_children());self.visible={x['id']:x for x in selected}
        for item in selected:self.tree.insert('', 'end',iid=item['id'],text=item['problem'],values=(item['priority'],item['app'],item['status']))
        self.count.set(f'{len(selected)} de {len(self.items)} casos. P0:incidentes/controles; P1:operacion; P2:evolucion.')
        self.set_detail('Selecciona un caso para ver solucion, responsable propuesto y criterio de cierre. No acredita que la funcion este desplegada.')

    def show_detail(self,event=None):
        selected=self.tree.selection()
        if not selected:return
        item=self.visible.get(selected[0])
        if not item:return
        self.set_detail(f"{item['id']} | {item['priority']} | {item['status']}\nPerfiles: {', '.join(item['roles'])}\nApp: {item['app']}\n\nNecesidad: {item['problem']}\n\nSolucion: {item['solution']}\n\nResponsable propuesto: {item['owner']}\n\nCierre verificable: {item['acceptance']}\n\nReferencia local: {item['source']}\n\nPropuesta editorial. No inicia consultas, envios, cambios Windows ni despliegues.")
