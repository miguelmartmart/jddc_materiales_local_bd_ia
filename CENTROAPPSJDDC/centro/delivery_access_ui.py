"""Punto de entrada a ZIP locales y gestores de acceso; sin secretos en la UI."""
from pathlib import Path
import os
import tkinter as tk
from tkinter import ttk,filedialog
from . import delivery_access,knowledge


class DeliveryAccessWindow(tk.Toplevel):
    def __init__(self,parent,workspace):
        super().__init__(parent);self.workspace=Path(workspace).absolute();self.zips={};self.access={}
        self.title('Entregas y accesos | Centro JDDC')
        self.geometry(f'{min(1060,self.winfo_screenwidth()-40)}x{min(760,self.winfo_screenheight()-70)}');self.minsize(800,550)
        ttk.Label(self,text='Entregas,descargas y gestion de accesos',font=('Segoe UI',14,'bold')).pack(anchor='w',padx=12,pady=(10,4))
        ttk.Label(self,text='ZIP locales:guardar copia,verificar y localizar. Accesos:referencias y gestores del sistema;el Centro no recupera contrasenas.',wraplength=920).pack(anchor='w',padx=12)
        bar=ttk.Frame(self,padding=10);bar.pack(fill='x')
        self.query=tk.StringVar();ttk.Label(bar,text='Buscar').pack(side='left')
        ttk.Entry(bar,textvariable=self.query).pack(side='left',fill='x',expand=True,padx=6)
        ttk.Button(bar,text='Actualizar catalogo',command=self.refresh).pack(side='left')
        self.message=tk.StringVar();ttk.Label(self,textvariable=self.message,wraplength=920).pack(anchor='w',padx=12,pady=(0,6))
        notebook=ttk.Notebook(self);notebook.pack(fill='both',expand=True,padx=10,pady=(0,10))
        self.zip_tree,self.zip_text=self.panel(notebook,'Entregas ZIP',('state','available'),('Estado','Archivo local'))
        self.access_tree,self.access_text=self.panel(notebook,'Credenciales y accesos',('manager','status'),('Gestor','Comprobacion'))
        zipbar=self.zip_actions=ttk.Frame(self.zip_text.master.master.master,padding=5);zipbar.pack(fill='x',side='bottom',before=self.zip_text.master.master)
        ttk.Button(zipbar,text='Verificar ZIP',command=self.verify).pack(side='left')
        ttk.Button(zipbar,text='Guardar / descargar copia...',command=self.copy).pack(side='left',padx=6)
        ttk.Button(zipbar,text='Abrir carpeta',command=self.locate).pack(side='left')
        accessbar=self.access_actions=ttk.Frame(self.access_text.master.master.master,padding=5);accessbar.pack(fill='x',side='bottom',before=self.access_text.master.master)
        self.manager_button=ttk.Button(accessbar,text='Abrir gestor Windows',command=self.manager);self.manager_button.pack(side='left')
        ttk.Button(accessbar,text='Ver guia de accesos',command=self.show_guide).pack(side='left',padx=6)
        self.zip_tree.bind('<<TreeviewSelect>>',lambda _:self.show_zip())
        self.access_tree.bind('<<TreeviewSelect>>',lambda _:self.show_access())
        self.query.trace_add('write',lambda *_:self.render())
        self.refresh()

    def panel(self,notebook,title,columns,headings):
        page=ttk.Frame(notebook,padding=7);notebook.add(page,text=title)
        panes=ttk.Panedwindow(page,orient='vertical');panes.pack(fill='both',expand=True)
        table=ttk.Frame(panes);panes.add(table,weight=3)
        tree=ttk.Treeview(table,columns=columns,show='tree headings',height=9);tree.heading('#0',text='Entrega / sistema');tree.column('#0',width=430,minwidth=260)
        for key,label in zip(columns,headings):tree.heading(key,text=label);tree.column(key,width=200,minwidth=130)
        scroll=ttk.Scrollbar(table,command=tree.yview);scroll.pack(side='right',fill='y');tree.configure(yscrollcommand=scroll.set);tree.pack(fill='both',expand=True)
        bottom=ttk.Frame(panes);panes.add(bottom,weight=2)
        text=tk.Text(bottom,wrap='word',height=10,padx=8,pady=8)
        scroll=ttk.Scrollbar(bottom,command=text.yview);scroll.pack(side='right',fill='y');text.configure(yscrollcommand=scroll.set);text.pack(fill='both',expand=True)
        return tree,text

    def write(self,widget,text):
        widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',text);widget.configure(state='disabled')

    def refresh(self):
        self.zips={};self.access={}
        try:
            catalog=delivery_access.load(self.workspace);found=delivery_access.deliveries(self.workspace)
            self.zips={x['id']:x for x in found['items']};self.access={x['id']:x for x in catalog['access']}
            self.message.set(f"{len(self.zips)} ZIP catalogados/localizados | {len(self.access)} referencias de acceso. Revision:{catalog['reviewed_at']}"+(' | Descubrimiento limitado.' if found['discovery_partial'] else ''))
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            self.message.set('Catalogo no disponible o invalido. Revisar ENTREGAS-Y-ACCESOS.json;no se leen secretos ni se intenta conexion.')
        self.render()

    def render(self):
        for tree in (self.zip_tree,self.access_tree):tree.delete(*tree.get_children())
        terms=knowledge.normalize(self.query.get()).split()
        for key,item in self.zips.items():
            if all(t in knowledge.normalize(' '.join(str(v) for v in item.values())) for t in terms):self.zip_tree.insert('', 'end',iid=key,text=item['title'],values=(item['state'],'Localizado' if delivery_access.available(self.workspace,item) else 'No disponible'))
        for key,item in self.access.items():
            if all(t in knowledge.normalize(' '.join(item.values())) for t in terms):self.access_tree.insert('', 'end',iid=key,text=item['app'],values=(item['manager'],'No comprobado'))
        self.write(self.zip_text,'Selecciona una entrega. Guardar copia no instala ni publica;los paquetes historicos conservan sus limites.')
        self.write(self.access_text,'Selecciona un sistema para ver donde se gestiona el acceso y a quien solicitarlo. No se muestran ni exportan secretos.')
        self.manager_button.configure(state='disabled')

    def selected(self,tree,items):
        keys=tree.selection();return items.get(keys[0]) if keys else None

    def show_zip(self):
        item=self.selected(self.zip_tree,self.zips)
        if item:self.write(self.zip_text,f"{item['title']}\nEstado:{item['state']}\nUso:{item['purpose']}\nRuta:{item['path']}\nSHA256 fijado:{item['expected_sha256'] or 'No fijado;se consulta SHA local si existe'}\n\nVerificar calcula hash y reconoce formato ZIP sin extraerlo. No acredita firma,contenido seguro o despliegue. Guardar crea una copia nueva sin sobrescribir archivos.")

    def show_access(self):
        item=self.selected(self.access_tree,self.access)
        if not item:return
        self.write(self.access_text,f"{item['app']}\nGestor:{item['manager']}\nDonde:{item['location']}\nAlcance:{item['status']}\n\nSiguiente paso:{item['next_step']}\n\nPresencia,permisos y vigencia de la credencial:no comprobados. No se copia ninguna contrasena,token o clave a documentos o ZIP.")
        self.manager_button.configure(state='normal' if os.name=='nt' and item['manager'] in {'windows_vault','certificates'} else 'disabled')

    def verify(self):
        item=self.selected(self.zip_tree,self.zips)
        if not item:self.message.set('Selecciona un ZIP.');return
        self.message.set('Verificando archivo local...');self.update_idletasks()
        try:
            result=delivery_access.verify(self.workspace,item)
            self.message.set('SHA256:'+result['sha256']+' | Referencia:'+result['reference']+'. Sin firma comprobada.')
        except (OSError,ValueError,UnicodeError):self.message.set('No verificable:ausente,limite,formato o SHA no coincidente. No se copia ni ejecuta;revisar archivo y referencias.')

    def copy(self):
        item=self.selected(self.zip_tree,self.zips)
        if not item:self.message.set('Selecciona un ZIP.');return
        chosen=filedialog.asksaveasfilename(parent=self,title='Guardar copia ZIP sin sobrescribir',initialfile=Path(item['path']).name,defaultextension='.zip',filetypes=[('ZIP','*.zip')])
        if not chosen:return
        self.message.set('Verificando y guardando copia local...');self.update_idletasks()
        try:
            result=delivery_access.copy_to(self.workspace,item,chosen)
            self.message.set('Copia guardada y cotejada. SHA256:'+result['sha256']+' | Referencia:'+result['reference'])
        except (OSError,ValueError,UnicodeError):self.message.set('Copia no completada:destino existente,limite,permisos o integridad. No se sobrescriben archivos existentes.')

    def locate(self):
        item=self.selected(self.zip_tree,self.zips)
        if not item:return
        try:
            path=delivery_access.core.checked_path(self.workspace/knowledge.relative(item['path']),self.workspace,2**63-1)
            if os.name!='nt':raise ValueError('Windows only')
            os.startfile(str(path.parent));self.message.set('Carpeta solicitada;no se ejecuta el ZIP.')
        except (OSError,ValueError):self.message.set('Carpeta no disponible;la ruta relativa permanece en la ficha.')

    def manager(self):
        item=self.selected(self.access_tree,self.access)
        if not item:return
        try:delivery_access.open_manager(item['manager']);self.message.set('Gestor Windows solicitado por accion expresa. El Centro no recupera valores ni acredita autenticacion.')
        except (OSError,ValueError):self.message.set('Gestion externa o panel no disponible. Consultar responsable y guia;no se cambia ninguna credencial.')

    def show_guide(self):
        item=self.selected(self.access_tree,self.access)
        if not item:return
        try:self.write(self.access_text,delivery_access.guide(self.workspace,item))
        except (OSError,ValueError,UnicodeError):self.message.set('Guia no disponible. Revisar la ruta en el catalogo.')
