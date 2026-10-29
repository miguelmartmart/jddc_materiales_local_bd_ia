"""Catalogo local de entregas y referencias de acceso. Nunca lee valores del vault."""
import hashlib,json,os,re,subprocess,zipfile
from pathlib import Path
from itertools import islice
from . import core,knowledge

RELATIVE='CENTROAPPSJDDC/docs/ENTREGAS-Y-ACCESOS.json'
MAX_ZIP_BYTES=256*1024*1024
MANAGERS={'windows_vault','certificates','application_admin','ubuntu_admin','erp_admin','mail_admin'}
STATES={'Historica','Sustituida','Candidato','Fuentes locales','Por clasificar'}
ZIP_FIELDS={'id','title','state','purpose','path','expected_sha256'}
ACCESS_FIELDS={'id','app','manager','location','status','next_step','guide'}


def load(workspace):
    root=Path(workspace).absolute();path=knowledge.data_path(root,'delivery_access',RELATIVE)
    data=json.loads(core.safe_file(path,root),object_pairs_hook=knowledge._pairs)
    if not isinstance(data,dict) or set(data)!={'schema','reviewed_at','deliveries','access'} or data['schema']!='jddc-deliveries-access/1':raise ValueError('Catalog')
    knowledge._stamp(data['reviewed_at'])
    for key,fields in [('deliveries',ZIP_FIELDS),('access',ACCESS_FIELDS)]:
        items=data[key]
        if not isinstance(items,list) or len(items)>60:raise ValueError('Catalog size')
        ids=set();paths=set()
        for item in items:
            if not isinstance(item,dict) or set(item)!=fields:raise ValueError('Catalog fields')
            for field in fields-{'expected_sha256'}:
                if not isinstance(item[field],str) or not 0<len(item[field])<=2000:raise ValueError('Catalog text')
            if item['id'] in ids:raise ValueError('Duplicate id')
            ids.add(item['id'])
            if key=='deliveries':
                path=knowledge.relative(item['path'])
                if not path.lower().endswith('.zip') or path.casefold() in paths or item['state'] not in STATES:raise ValueError('Delivery')
                paths.add(path.casefold())
                sha=item['expected_sha256']
                if sha is not None and (not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha)):raise ValueError('SHA256')
            else:
                if item['manager'] not in MANAGERS or Path(knowledge.relative(item['guide'])).suffix.lower() not in {'.txt','.md','.rst'}:raise ValueError('Access reference')
    return data


def deliveries(workspace):
    root=Path(workspace).absolute();data=load(root);items=list(data['deliveries']);seen={x['path'].casefold() for x in items};partial=False
    for relative in ('.','DEVIA_VALIDACION'):
        directory=root/relative
        if not directory.exists():continue
        if core.linked(directory) or not directory.is_dir():partial=True;continue
        paths=list(islice(directory.iterdir(),501))
        if len(paths)>500:partial=True
        for path in paths[:500]:
            if len(items)>=200:partial=True;break
            if path.suffix.lower()!='.zip':continue
            rel=path.relative_to(root).as_posix()
            if rel.casefold() in seen:continue
            seen.add(rel.casefold())
            items.append(dict(id='found:'+str(len(items)),title=path.name,state='Por clasificar',purpose='ZIP localizado sin ficha revisada;existencia no acredita contenido o version activa',path=rel,expected_sha256=None))
    return {'items':items,'discovery_partial':partial,'reviewed_at':data['reviewed_at']}


def available(workspace,item):
    try:core.checked_path(Path(workspace).absolute()/knowledge.relative(item['path']),Path(workspace).absolute(),2**63-1);return True
    except (OSError,ValueError):return False


def _reference(workspace,item):
    root=Path(workspace).absolute();path=root/knowledge.relative(item['path']);pin=item['expected_sha256'];sidecar=path.with_name(path.name+'.sha256')
    local=None
    if sidecar.exists() or sidecar.is_symlink():
        text=core.safe_file(sidecar,root,4096).decode('utf-8-sig').strip()
        match=re.fullmatch(r'([a-fA-F0-9]{64})(?:[ \t]+\*?([^\r\n]+))?',text)
        if not match or (match[2] is not None and match[2]!=path.name):raise ValueError('Invalid local SHA256')
        local=match[1].lower()
    if pin and local and pin!=local:raise ValueError('Catalog/sidecar disagreement')
    return pin or local,('catalogo y SHA local' if pin and local else 'catalogo' if pin else 'SHA local' if local else 'calculada ahora,sin huella previa')


def verify(workspace,item):
    root=Path(workspace).absolute();path=core.checked_path(root/knowledge.relative(item['path']),root,MAX_ZIP_BYTES)
    if path.suffix.lower()!='.zip':raise ValueError('Only ZIP')
    expected,basis=_reference(root,item)
    with path.open('rb') as stream:
        start=os.fstat(stream.fileno())
        if not zipfile.is_zipfile(stream):raise ValueError('ZIP structure not recognized')
        stream.seek(0);digest=hashlib.sha256();size=0
        for block in iter(lambda:stream.read(128*1024),b''):
            size+=len(block)
            if size>MAX_ZIP_BYTES:raise ValueError('ZIP limit')
            digest.update(block)
        end=os.fstat(stream.fileno())
    if (start.st_size,start.st_mtime_ns)!=(end.st_size,end.st_mtime_ns):raise ValueError('Source changed')
    sha=digest.hexdigest()
    if expected and sha!=expected:raise ValueError('ZIP hash mismatch')
    return {'sha256':sha,'bytes':size,'reference':basis,'prior_hash_available':expected is not None,'publisher_signature_verified':False,'zip_contents_extracted':False}


def copy_to(workspace,item,destination):
    verified=verify(workspace,item);root=Path(workspace).absolute();source=core.checked_path(root/knowledge.relative(item['path']),root,MAX_ZIP_BYTES)
    destination=Path(destination)
    if destination.suffix.lower()!='.zip':raise ValueError('Destination must be ZIP')
    created=None
    try:
        with destination.open('x+b') as target:
            created=os.fstat(target.fileno());digest=hashlib.sha256();size=0
            with source.open('rb') as stream:
                for block in iter(lambda:stream.read(128*1024),b''):
                    size+=len(block)
                    if size>MAX_ZIP_BYTES:raise ValueError('ZIP limit')
                    target.write(block);digest.update(block)
            target.flush();os.fsync(target.fileno())
            if digest.hexdigest()!=verified['sha256'] or size!=verified['bytes']:raise ValueError('Source changed while copying')
            target.seek(0);copied=hashlib.sha256()
            for block in iter(lambda:target.read(128*1024),b''):copied.update(block)
            if copied.hexdigest()!=verified['sha256']:raise ValueError('Copied file mismatch')
        return verified
    except Exception:
        if created is not None:
            try:
                current=destination.stat()
                if (current.st_dev,current.st_ino)==(created.st_dev,created.st_ino):destination.unlink()
            except OSError:pass
        raise


def guide(workspace,item):
    root=Path(workspace).absolute();relative=knowledge.relative(item['guide'])
    if Path(relative).suffix.lower() not in {'.txt','.md','.rst'}:raise ValueError('Guide only')
    return core.safe_file(root/relative,root).decode('utf-8-sig')


def open_manager(manager):
    if os.name!='nt' or manager not in {'windows_vault','certificates'}:raise ValueError('Managed externally')
    system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'
    command=[str(system/'control.exe'),'/name','Microsoft.CredentialManager'] if manager=='windows_vault' else [str(system/'mmc.exe'),str(system/'certmgr.msc')]
    return subprocess.Popen(command,shell=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
