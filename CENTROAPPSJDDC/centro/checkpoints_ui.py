"""Comparacion local explicita: guardar puntos no renueva pruebas historicas."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from . import checkpoints,knowledge


class CheckpointsWindow(tk.Toplevel):
    def __init__(self,parent,workspace):
        super().__init__(parent)
        self.workspace=Path(workspace).absolute();self.current=None;self.diffs=[];self.visible={}
        self.title('Puntos de continuidad | Cambios desde la ultima visita')
        self.geometry(f'{min(1040,self.winfo_screenwidth()-40)}x{min(760,self.winfo_screenheight()-70)}');self.minsize(800,550)
        ttk.Label(self,text='Comparar cambios y conservar contexto',font=('Segoe UI',14,'bold')).pack(anchor='w',padx=12,pady=(10,4))
        ttk.Label(self,text='Solo referencias del indice y hashes. La captura local no renueva evidencias antiguas ni comprueba servicios.',wraplength=920).pack(anchor='w',padx=12)
        toolbar=ttk.Frame(self,padding=10);toolbar.pack(fill='x')
        ttk.Label(toolbar,text='Punto anterior').pack(side='left')
        self.baseline=tk.StringVar();self.combo=ttk.Combobox(toolbar,textvariable=self.baseline,state='readonly',width=35);self.combo.pack(side='left',padx=6)
        self.combo.bind('<<ComboboxSelected>>',lambda _:self.refresh(keep_selection=True))
        ttk.Button(toolbar,text='Comparar ahora',command=lambda:self.refresh(keep_selection=True)).pack(side='left',padx=3)
        self.save_button=ttk.Button(toolbar,text='Guardar punto actual',command=self.save);self.save_button.pack(side='left',padx=3)
        self.changed=tk.BooleanVar(value=True)
        ttk.Checkbutton(self,text='Mostrar solo cambios o contenido no verificable',variable=self.changed,command=self.render).pack(anchor='w',padx=12)
        self.summary=tk.StringVar()
        self.summary_label=ttk.Label(self,textvariable=self.summary,wraplength=920);self.summary_label.pack(anchor='w',padx=12,pady=5)
        self.bind('<Configure>',lambda event:self.summary_label.configure(wraplength=max(500,event.width-30)) if event.widget is self else None)
        panes=ttk.Panedwindow(self,orient='vertical');panes.pack(fill='both',expand=True,padx=12,pady=(0,10))
        table=ttk.Frame(panes);panes.add(table,weight=3)
        self.tree=ttk.Treeview(table,columns=('state','path'),show='tree headings',height=9)
        self.tree.heading('#0',text='Referencia');self.tree.column('#0',width=250,minwidth=170)
        self.tree.heading('state',text='Comparacion');self.tree.column('state',width=280,minwidth=200)
        self.tree.heading('path',text='Ruta relativa');self.tree.column('path',width=360,minwidth=200)
        scroll=ttk.Scrollbar(table,command=self.tree.yview);scroll.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scroll.set);self.tree.pack(fill='both',expand=True)
        panel=ttk.Frame(panes);panes.add(panel,weight=2)
        self.detail=tk.Text(panel,wrap='word',height=10,padx=8,pady=8)
        scroll=ttk.Scrollbar(panel,command=self.detail.yview);scroll.pack(side='right',fill='y')
        self.detail.configure(yscrollcommand=scroll.set);self.detail.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',self.show_selected)
        self.refresh()
        self.after(100,lambda:panes.sashpos(0,max(180,panes.winfo_height()*3//5)) if self.winfo_exists() else None)

    def write(self,text):
        self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.insert('1.0',text);self.detail.configure(state='disabled')

    def refresh(self,keep_selection=False):
        self.current=None;self.diffs=[]
        try:
            current=checkpoints.collect(self.workspace)
            ids=checkpoints.list_ids(self.workspace)
            wanted=self.baseline.get() if keep_selection else ''
            self.combo.configure(values=ids)
            selected=wanted if wanted in ids else (ids[0] if ids else '')
            self.baseline.set(selected)
            self.current=current
            if selected:
                before=checkpoints.read(self.workspace,selected)
                self.diffs=checkpoints.compare(before,current)
                changed=sum(r['status']!='Sin cambios de archivo/referencia' for r in self.diffs)
                self.summary.set(f"Antes:{before['captured_at']} | Ahora:{current['captured_at']}\nVersion cargada:{before['code_version']} -> {current['code_version']} | {changed} referencias con diferencia/no verificables. Las fechas originales se conservan.")
            else:
                self.summary.set('Sin punto anterior. Puedes guardar el estado de referencias actual para compararlo al volver. No acredita correccion o estado remoto.')
            self.save_button.configure(state='normal')
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            self.summary.set('Comparacion no disponible:indice,punto o carpeta no verificables. No se sustituye el ultimo punto por otro anterior ni se presume exito. Revisar originales.')
            self.save_button.configure(state='disabled')
        self.render()

    def render(self):
        self.tree.delete(*self.tree.get_children());self.visible={}
        for index,row in enumerate(self.diffs):
            if self.changed.get() and row['status']=='Sin cambios de archivo/referencia':continue
            key=str(index);self.visible[key]=row
            self.tree.insert('', 'end',iid=key,text=row['title'],values=(row['status'],row['path']))
        self.write('Selecciona una referencia. Un hash distinto indica bytes distintos, no que la nueva version sea mejor o este aceptada. Una referencia retirada no implica que se haya borrado el archivo.')

    def show_selected(self,event=None):
        selection=self.tree.selection()
        if not selection:return
        row=self.visible.get(selection[0])
        if not row:return
        text=f"{row['title']}\n{row['status']}\n"
        for label,item in [('ANTES',row['before']),('AHORA',row['after'])]:
            if item is None:text+=f'\n{label}:referencia no incluida en ese punto\n';continue
            text+=f"\n{label}\nRuta:{item['path']}\nDisponibilidad:{item['status']}\nFecha declarada de evidencia:{item['declared_observed_at'] or 'no especificada'}\n{knowledge.age_text(item['declared_observed_at'])}\nBytes:{item['size_bytes']}\nSHA256:{item['sha256'] or 'no verificable'}\n"
        self.write(text+'\nNo contiene texto original,filas ERP,credenciales ni datos de rendimiento. Los hashes no son firma ni prueba de verdad.')

    def save(self):
        self.save_button.configure(state='disabled')
        try:
            point=checkpoints.save(self.workspace)
            self.refresh()
            self.summary.set('Punto guardado:'+point['captured_at']+'. Los documentos,pendientes y fechas de pruebas no se han modificado.')
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
            self.refresh(keep_selection=True)
            self.summary.set('No se pudo guardar/verificar el punto. Revisar permisos,integridad o limite100. No se borran ni sobrescriben puntos anteriores.')
