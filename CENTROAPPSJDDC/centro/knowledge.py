"""Indice local de continuidad, con rutas relativas y lectura acotada."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path,PurePosixPath
import unicodedata
from . import core

RELATIVE='CENTROAPPSJDDC/docs/CONTINUIDAD.json'
KINDS={'Guia','Resumen','Plan','Regla','Evidencia historica','Incidente'}


def relative(value):
    if not isinstance(value,str) or not value or len(value)>400:raise ValueError('path')
    path=PurePosixPath(value)
    if path.is_absolute() or any(p.casefold() in {'..','.git','.portal_private'} for p in path.parts) or ':' in value or '\\' in value:raise ValueError('path')
    return str(path)


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate')
        result[key]=value
    return result


def _stamp(value):
    if not isinstance(value,str):raise ValueError('date')
    stamp=datetime.fromisoformat(value)
    if stamp.tzinfo is None:raise ValueError('date')
    return stamp


def load(workspace):
    root=Path(workspace).absolute()
    data=json.loads(core.safe_file(root/RELATIVE,root),object_pairs_hook=_pairs)
    if not isinstance(data,dict) or data.get('schema')!='jddc-continuity/1':raise ValueError('index')
    _stamp(data.get('reviewed_at'))
    resources=data.get('resources');pointers=data.get('data_files')
    if not isinstance(resources,list) or not 1<=len(resources)<=60 or not isinstance(pointers,dict):raise ValueError('index')
    required={'equipment_summary','use_cases'}
    if not required.issubset(pointers) or not set(pointers).issubset(required|{'delivery_access'}):raise ValueError('index')
    for value in pointers.values():
        if not relative(value).endswith('.json'):raise ValueError('index')
    seen=set()
    for resource in resources:
        if not isinstance(resource,dict) or set(resource)!={'id','title','kind','description','path','observed_at'}:raise ValueError('resource')
        for key in ('id','title','kind','description','path'):
            if not isinstance(resource[key],str) or not 0<len(resource[key])<=2000:raise ValueError('resource')
        if resource['id'] in seen or resource['kind'] not in KINDS:raise ValueError('resource')
        seen.add(resource['id'])
        if PurePosixPath(relative(resource['path'])).suffix.lower() not in {'.txt','.md','.rst','.json'}:raise ValueError('resource')
        if resource['observed_at'] is not None:_stamp(resource['observed_at'])
    return data


def data_path(workspace,key,fallback):
    root=Path(workspace).absolute()
    # Absence supports earlier standalone layouts; an invalid existing index never falls back silently.
    if not (root/RELATIVE).exists():return root/relative(fallback)
    return root/load(root)['data_files'].get(key,relative(fallback))


def read_resource(workspace,resource):
    root=Path(workspace).absolute()
    return core.safe_file(root/relative(resource['path']),root).decode('utf-8-sig')


def age_text(value,now=None):
    if value is None:return 'Fecha no especificada'
    try:delta=(now or datetime.now(timezone.utc))-_stamp(value)
    except (ValueError,TypeError,OverflowError):return 'Fecha no interpretable'
    if delta < -timedelta(minutes=5):return 'Fecha futura:revisar'
    days=max(0,delta.days)
    return f'{days} dias:requiere revision' if days>30 else f'{days} dias desde revision'


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))


def find(resources,query='',kind='Todos'):
    terms=normalize(query).split()
    return [r for r in resources if (kind=='Todos' or r['kind']==kind)
            and all(term in normalize(' '.join(str(r[k]) for k in ('title','description','path','kind'))) for term in terms)]


def is_file_metadata(record):
    if record.get('source') in {'windows','probe','health','history','evidence','equipment_summary'}:return False
    prefixes=('Documentaci\u00f3n:', 'Dependencias / despliegue:', 'Arranque / operaci\u00f3n:',
              'Pruebas disponibles', 'Cartograf\u00eda / cat\u00e1logo', 'Paquete / posible copia')
    return (record.get('name','').startswith(prefixes)
            or 'Contenido original no examinado' in record.get('detail',''))


def check(workspace):
    """Comprobar indice y enlaces locales; no interpreta salud o identidad remota."""
    root=Path(workspace).absolute()
    data=load(root)
    paths=[('data:'+key,value) for key,value in data['data_files'].items()]
    paths += [(r['id'],r['path']) for r in data['resources']]
    results=[]
    for identifier,value in paths:
        try:
            core.checked_path(root/relative(value),root)
            status='localizado'
        except (OSError,ValueError):status='no_disponible'
        results.append({'id':identifier,'path':value,'status':status})
    return {'schema':'jddc-continuity-check/1','scope':'Indice y rutas locales;no comprueba estado remoto ni aceptacion de produccion',
            'reviewed_at':data['reviewed_at'],'review_age':age_text(data['reviewed_at']),
            'paths':results,'all_paths_available':all(r['status']=='localizado' for r in results)}
