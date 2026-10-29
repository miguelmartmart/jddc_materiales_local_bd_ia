"""Local project graph and in-memory search. No execution, network or secret indexing."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import json, re, os
from . import knowledge, core, delivery_access, use_cases

RELATIVE='CENTROAPPSJDDC/docs/PROYECTOS.json'
MAX_PROJECTS=5000
KINDS=('Familia','Proyecto','Seccion','Codigo','Guia','Entrega','Pendiente','Acceso')
SECTIONS=(('code','Codigo'),('guides','Guias'),('deliveries','Entregas'),('tasks','Pendientes'),('access','Accesos'))

def safe_relative(value):
    value=knowledge.relative(value)
    if value=='.':raise ValueError('Workspace root is not a project source root')
    if any(p.startswith('.') or p.casefold() in {'logs','data','config','node_modules','__pycache__','venv'} for p in Path(value).parts):
        raise ValueError('Private or runtime path')
    return value

def local_path(root,value):
    root=Path(root).absolute();path=root/safe_relative(value)
    current=root
    if core.linked(current):raise ValueError('Linked root')
    for part in path.relative_to(root).parts:
        current=current/part
        if core.linked(current):raise ValueError('Linked path')
    return path

def load(root):
    root=Path(root).absolute()
    raw=core.safe_file(root/RELATIVE,root,8*1024*1024)
    data=json.loads(raw,object_pairs_hook=knowledge._pairs)
    if not isinstance(data,dict) or set(data)!={'schema','reviewed_at','projects'} or data['schema']!='jddc-projects/1':raise ValueError('Project catalog')
    knowledge._stamp(data['reviewed_at'])
    if not isinstance(data['projects'],list) or len(data['projects'])>MAX_PROJECTS:raise ValueError('Project limit')
    ids=set()
    for p in data['projects']:
        if not isinstance(p,dict) or set(p)!={'id','title','family','description','state','roots','resource_ids','delivery_ids','access_ids','task_apps','tags'}:raise ValueError('Project fields')
        for key in ('id','title','description','state'):
            if not isinstance(p[key],str) or not 0<len(p[key])<=2000:raise ValueError('Project text')
        if not re.fullmatch('[a-z0-9_-]{1,80}',p['id']) or p['id'] in ids:raise ValueError('Project id')
        ids.add(p['id'])
        for key in ('family','roots','resource_ids','delivery_ids','access_ids','task_apps','tags'):
            if not isinstance(p[key],list) or len(p[key])>100 or any(not isinstance(v,str) or not 0<len(v)<=400 for v in p[key]):raise ValueError('Project list')
        if not 1<=len(p['family'])<=6:raise ValueError('Family depth')
        for value in p['roots']:safe_relative(value)
    return data

@dataclass
class Node:
    id:str
    title:str
    kind:str
    parent:str='root'
    description:str=''
    path:str=''
    state:str='Referencia local'
    project:str=''
    payload:dict=field(default_factory=dict)

class Catalog:
    def __init__(self,nodes=(),projects=(),warnings=()):
        self.nodes={'root':Node('root','Todos los proyectos','Familia',parent='')}
        self.children=defaultdict(list);self.projects={p['id']:p for p in projects};self.warnings=list(warnings)
        for n in nodes:
            if n.id in self.nodes or n.kind not in KINDS:raise ValueError('Duplicate/invalid node')
            self.nodes[n.id]=n;self.children[n.parent].append(n.id)
        self.ancestors={};self.search_text={};self.grams=defaultdict(set)
        for key,n in self.nodes.items():
            trail=[];current=n
            while current.parent:
                if current.parent not in self.nodes or current.parent in trail or len(trail)>12:raise ValueError('Invalid graph')
                trail.append(current.parent);current=self.nodes[current.parent]
            self.ancestors[key]=tuple(trail)
            tags=' '.join(self.projects.get(n.project,{}).get('tags',[]))
            text=knowledge.normalize(' '.join((n.title,n.description,n.path,n.kind,n.state,tags,' '.join(self.nodes[a].title for a in trail))))
            self.search_text[key]=text
            for gram in {text[i:i+3] for i in range(len(text)-2)}:self.grams[gram].add(key)
        self.project_counts={k:0 for k in self.nodes}
        for n in self.nodes.values():
            if n.kind=='Proyecto':
                for a in self.ancestors[n.id]:self.project_counts[a]+=1

    def search(self,query='',scope='root',kind='Todos',state='Todos',tag='Todas'):
        terms=knowledge.normalize(query).split();candidates=None
        for term in terms:
            for i in range(len(term)-2):
                hits=self.grams.get(term[i:i+3],set())
                candidates=hits.copy() if candidates is None else candidates & hits
                if not candidates:return []
        keys=self.nodes.keys() if candidates is None else candidates
        result=[self.nodes[k] for k in keys if k!='root' and (scope=='root' or scope in self.ancestors[k]) and
                (kind=='Todos' or self.nodes[k].kind==kind) and (state=='Todos' or self.nodes[k].state==state) and
                (tag=='Todas' or tag in self.projects.get(self.nodes[k].project,{}).get('tags',[])) and
                all(t in self.search_text[k] for t in terms)]
        return sorted(result,key=lambda n:(not all(t in knowledge.normalize(n.title) for t in terms),KINDS.index(n.kind),knowledge.normalize(n.title),n.id))

    def trail(self,key):return list(reversed(self.ancestors[key]))+[key]

def build(root):
    root=Path(root).absolute();data=load(root);nodes=[];warnings=[];families={}
    try:resources={r['id']:r for r in knowledge.load(root)['resources']}
    except (OSError,ValueError,TypeError,KeyError):resources={};warnings.append('Indice de guias no disponible')
    try:
        d=delivery_access.load(root);zips={z['id']:z for z in d['deliveries']};access={a['id']:a for a in d['access']}
    except (OSError,ValueError,TypeError,KeyError):zips={};access={};warnings.append('Catalogo de entregas no disponible')
    try:tasks=use_cases.load(root)
    except (OSError,ValueError,TypeError,KeyError):tasks=[];warnings.append('Casos de uso no disponibles')
    def add(n):nodes.append(n);return n.id
    for p in data['projects']:
        parent='root';family=[]
        for name in p['family']:
            family.append(name);key=tuple(family)
            if key not in families:
                fid='family:'+str(len(families));families[key]=fid
                add(Node(fid,name,'Familia',parent,description='Agrupacion del catalogo de proyectos'))
            parent=families[key]
        pid='project:'+p['id'];add(Node(pid,p['title'],'Proyecto',parent,p['description'],state=p['state'],project=p['id'],payload=p))
        for section,title in SECTIONS:
            sid=pid+':'+section;add(Node(sid,title,'Seccion',pid,project=p['id']))
            if section=='code':
                for i,path in enumerate(p['roots']):add(Node(sid+':'+str(i),Path(path).name,'Codigo',sid,'Abrir carpeta o explorar sus subcarpetas sin ejecutar codigo.',path,project=p['id']))
            if section=='guides':
                for id in p['resource_ids']:
                    r=resources.get(id)
                    if r:add(Node(sid+':'+id,r['title'],'Guia',sid,r['description'],r['path'],project=p['id'],payload=r))
                    else:warnings.append(p['title']+':guia no encontrada:'+id)
            if section=='deliveries':
                for id in p['delivery_ids']:
                    z=zips.get(id)
                    if z:add(Node(sid+':'+id,z['title'],'Entrega',sid,z['purpose'],z['path'],z['state'],p['id'],z))
                    else:warnings.append(p['title']+':entrega no encontrada:'+id)
            if section=='access':
                for id in p['access_ids']:
                    a=access.get(id)
                    if a:add(Node(sid+':'+id,a['app'],'Acceso',sid,a['status'],state='Gestion externa',project=p['id'],payload=a))
                    else:warnings.append(p['title']+':acceso no encontrado:'+id)
            if section=='tasks':
                for t in tasks:
                    if t['app'] in p['task_apps']:add(Node(sid+':'+t['id'],t['problem'],'Pendiente',sid,t['solution'],t['source'],t['status'],p['id'],t))
    model=Catalog(nodes,data['projects'],warnings);model.reviewed_at=data['reviewed_at'];return model

def folder_entries(root,relative,limit=500):
    """One level only, no links/private/runtime paths, no content read."""
    folder=local_path(root,relative)
    if not folder.is_dir():raise ValueError('Not a folder')
    result=[];partial=False
    with os.scandir(folder) as stream:
        for i,entry in enumerate(stream):
            if i>=limit:partial=True;break
            rel=(Path(relative)/entry.name).as_posix()
            try:
                path=local_path(root,rel)
                if not (path.is_dir() or path.is_file()):continue
                result.append((rel,path.is_dir()))
            except (OSError,ValueError):continue
    return sorted(result,key=lambda v:(not v[1],v[0].casefold())),partial
