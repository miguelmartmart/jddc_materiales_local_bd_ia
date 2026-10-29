"""Catalogo editorial acotado y filtro por tareas. No ejecuta acciones de negocio."""
import json
from pathlib import Path,PurePosixPath
from . import core,knowledge

RELATIVE='CENTROAPPSJDDC/docs/CASOS-DE-USO-Y-MEJORAS-20261026.json'
STATUSES={'Propuesta','Candidato local','Pendiente servidor','Implementado local'}
FIELDS={'id','priority','roles','app','problem','solution','owner','status','acceptance','source'}


def load(workspace):
    path=knowledge.data_path(workspace,'use_cases',RELATIVE)
    data=json.loads(core.safe_file(path,Path(workspace).absolute()))
    if not isinstance(data,dict) or data.get('schema')!='jddc-use-cases/1':raise ValueError('catalog')
    items=data.get('items')
    if not isinstance(items,list) or not items or len(items)>100:raise ValueError('catalog')
    seen=set()
    for item in items:
        if not isinstance(item,dict) or set(item)!=FIELDS:raise ValueError('catalog')
        if any(not isinstance(item[k],str) or not 0<len(item[k])<=3000 for k in FIELDS-{'roles'}):raise ValueError('catalog')
        if item['priority'] not in {'P0','P1','P2'} or item['status'] not in STATUSES:raise ValueError('catalog')
        roles=item['roles']
        if not isinstance(roles,list) or not 1<=len(roles)<=12 or any(not isinstance(r,str) or not 0<len(r)<=80 for r in roles):raise ValueError('catalog')
        if item['id'] in seen:raise ValueError('catalog')
        seen.add(item['id'])
        source=PurePosixPath(item['source'])
        if source.is_absolute() or '..' in source.parts or ':' in item['source'] or '\\' in item['source']:raise ValueError('catalog')
    return items


def select(items,role='Todos',priority='Todas',status='Todos',app='Todas',query=''):
    terms=query.casefold().split()
    return [item for item in items
            if (role=='Todos' or role in item['roles'])
            and (priority=='Todas' or priority==item['priority'])
            and (status=='Todos' or status==item['status'])
            and (app=='Todas' or app==item['app'])
            and all(term in ' '.join(str(value) for value in item.values()).casefold() for term in terms)]
