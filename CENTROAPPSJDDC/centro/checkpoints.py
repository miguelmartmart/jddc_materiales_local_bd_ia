"""Puntos locales de continuidad: metadatos y hashes, sin contenidos ni red."""
from datetime import datetime,timezone
import hashlib,json,os,re,secrets
from pathlib import Path
from . import __version__,core,knowledge

DIRECTORY=Path('.portal_private/control_center/checkpoints')
MAX_POINTS=100
MAX_ITEMS=70
ID_PATTERN=r'[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}'
ITEM_FIELDS={'id','path','kind','title','declared_observed_at','status','size_bytes','sha256'}
FIELDS={'schema','id','captured_at','code_version','index_reviewed_at','scope','items','content_sha256'}
SCOPE={'local_files_only':True,'file_contents_stored':False,'remote_state_checked':False,
       'historical_evidence_renewed':False,'cross_file_atomic_snapshot_verified':False}


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def _digest(value):return hashlib.sha256(_canonical(value)).hexdigest()


def collect(workspace,*,clock=lambda:datetime.now(timezone.utc)):
    root=Path(workspace).absolute();index_path=root/knowledge.RELATIVE
    first=core.safe_file(index_path,root);index=knowledge.load(root)
    if first!=core.safe_file(index_path,root):raise ValueError('Index changed during capture')
    stamp=clock()
    if stamp.tzinfo is None:raise ValueError('Aware timestamp required')
    stamp=stamp.astimezone(timezone.utc)
    refs=[dict(id='index',path=knowledge.RELATIVE,kind='Indice',title='Indice de continuidad',declared_observed_at=index['reviewed_at'])]
    refs += [dict(id='data:'+key,path=value,kind='Datos de guia',title=key,declared_observed_at=None) for key,value in index['data_files'].items()]
    refs += [dict(id='resource:'+r['id'],path=r['path'],kind=r['kind'],title=r['title'],declared_observed_at=r['observed_at']) for r in index['resources']]
    if len(refs)>MAX_ITEMS:raise ValueError('Too many references')
    for item in refs:
        try:
            raw=core.safe_file(root/knowledge.relative(item['path']),root)
            item.update(status='available',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        except (OSError,ValueError):item.update(status='unavailable',size_bytes=None,sha256=None)
    if first!=core.safe_file(index_path,root):raise ValueError('Index changed during capture')
    result={'schema':'jddc-continuity-point/1','id':stamp.strftime('%Y%m%dT%H%M%S%fZ')+'-'+secrets.token_hex(4),
            'captured_at':stamp.isoformat(),'code_version':__version__,'index_reviewed_at':index['reviewed_at'],
            'scope':dict(SCOPE),'items':refs}
    result['content_sha256']=_digest(result)
    return validate(result)


def validate(value):
    if not isinstance(value,dict) or set(value)!=FIELDS or value['schema']!='jddc-continuity-point/1':raise ValueError('Point schema')
    if not isinstance(value['id'],str) or not re.fullmatch(ID_PATTERN,value['id']):raise ValueError('Point id')
    knowledge._stamp(value['captured_at']);knowledge._stamp(value['index_reviewed_at'])
    if not isinstance(value['code_version'],str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',value['code_version']):raise ValueError('Version')
    if value['scope']!=SCOPE or not isinstance(value['scope'],dict) or any(type(v) is not bool for v in value['scope'].values()):raise ValueError('Point scope')
    if not isinstance(value['items'],list) or not 1<=len(value['items'])<=MAX_ITEMS:raise ValueError('Point items')
    seen=set()
    for item in value['items']:
        if not isinstance(item,dict) or set(item)!=ITEM_FIELDS:raise ValueError('Point item')
        for key in ('id','path','kind','title'):
            if not isinstance(item[key],str) or not 0<len(item[key])<=(2100 if key=='id' else 2000):raise ValueError('Point text')
        knowledge.relative(item['path'])
        if item['id'] in seen:raise ValueError('Duplicate reference')
        seen.add(item['id'])
        if item['declared_observed_at'] is not None:knowledge._stamp(item['declared_observed_at'])
        if item['status']=='available':
            if type(item['size_bytes']) is not int or not 0<=item['size_bytes']<=core.LIMIT:raise ValueError('Size')
            if not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']):raise ValueError('Digest')
        elif item['status']!='unavailable' or item['sha256'] is not None or item['size_bytes'] is not None:raise ValueError('Availability')
    unsigned={k:v for k,v in value.items() if k!='content_sha256'}
    if value['content_sha256']!=_digest(unsigned):raise ValueError('Integrity mismatch')
    return value


def _directory(workspace,create=False):
    root=Path(workspace).absolute()
    if not root.is_dir() or core.linked(root):raise ValueError('Workspace directory')
    current=root
    for part in DIRECTORY.parts:
        current=current/part
        if current.exists() or current.is_symlink():
            if core.linked(current) or not current.is_dir():raise ValueError('Unsafe checkpoint directory')
        elif create:current.mkdir(mode=0o700)
        else:return None
    return current


def list_ids(workspace):
    directory=_directory(workspace)
    if directory is None:return []
    paths=list(directory.iterdir())
    if len(paths)>MAX_POINTS:raise ValueError('Checkpoint limit reached; review existing files')
    if any(not re.fullmatch(ID_PATTERN+r'\.json',p.name) for p in paths):raise ValueError('Unexpected checkpoint file; review directory')
    return sorted([p.stem for p in paths],reverse=True)


def read(workspace,identifier):
    if not isinstance(identifier,str) or not re.fullmatch(ID_PATTERN,identifier):raise ValueError('Invalid point id')
    directory=_directory(workspace)
    if directory is None:raise ValueError('No stored checkpoints')
    raw=core.safe_file(directory/(identifier+'.json'),Path(workspace).absolute())
    result=validate(json.loads(raw,object_pairs_hook=knowledge._pairs))
    if result['id']!=identifier:raise ValueError('File/id mismatch')
    return result


def save(workspace):
    # No automatic baseline at startup. Each saved point requires an explicit local action.
    value=collect(workspace)
    directory=_directory(workspace,create=True)
    ids=list_ids(workspace)
    if len(ids)>=MAX_POINTS:raise ValueError('Checkpoint limit reached; no automatic deletion')
    if ids:
        latest=read(workspace,ids[0])
        if knowledge._stamp(value['captured_at'])<knowledge._stamp(latest['captured_at']):raise ValueError('Clock moved backwards')
    raw=_canonical(value)+b'\n'
    if len(raw)>core.LIMIT:raise ValueError('Checkpoint size limit')
    path=directory/(value['id']+'.json')
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0)
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    read(workspace,value['id'])
    return value


def compare(before,after):
    validate(before);validate(after)
    old={r['id']:r for r in before['items']};new={r['id']:r for r in after['items']};result=[]
    for key in sorted(set(old)|set(new)):
        a=old.get(key);b=new.get(key);item=b or a
        if b is None:status='Referencia retirada'
        elif a is None:status='Referencia nueva' if b['status']=='available' else 'Referencia nueva no disponible'
        elif b['status']!='available':status='Contenido no verificable ahora'
        elif a['status']!='available':status='Ahora disponible;sin contraste previo'
        elif a['path']!=b['path']:status='Destino de referencia cambiado'
        elif a['sha256']!=b['sha256']:status='Archivo cambiado'
        elif any(a[k]!=b[k] for k in ('title','kind','declared_observed_at')):status='Metadatos de referencia cambiados'
        else:status='Sin cambios de archivo/referencia'
        result.append({'id':key,'path':item['path'],'title':item['title'],'status':status,
                       'before':a,'after':b})
    return result
